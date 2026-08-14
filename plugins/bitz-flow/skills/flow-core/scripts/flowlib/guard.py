"""write の target guard プロトコル（FLW-DSN-015 / FLW-NFR-012 / FLW-NFR-006）。

guard key は `guard_identity × canonical_mutation_target` であり、**operation family を含めない**。
family を key に混ぜると、`stage` と `commit` が同じ index を触るのに別 guard を取ってしまい、
cross-family の同時 mutation を許してしまう。

安全側に倒す既定:

- **一意化できない target では write しない**。symlink・case 差・別 worktree・remote alias を
  正規化して同じ target へ収束させ、収束できなければ副作用 0 で BLOCKED。
- **取得は canonical key の昇順**に固定する。順序が崩れると deadlock と二重 mutation の
  両方が起きうる。途中で失敗したら取得済みを逆順で解放し、副作用 0 で戻る。
- **target guard を family lock より先に取る**。逆順は許さない。
- Git storage 自体が fencing token を原子的に検証するとは主張しない。token は「誰が今の所有者か」を
  coordinator 側で決めるためのもので、実際の排他は OS lock と CAS が担う。
"""

from __future__ import annotations

import dataclasses
import os
import re
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence

from . import result as R

CODE_BLOCKED = "BLOCKED"
CODE_UNSUPPORTED = "UNSUPPORTED"
CODE_INVALID_INPUT = "INVALID_INPUT"

KIND_INDEX = "index"
KIND_LOCAL_REF = "local-ref"
KIND_REMOTE_TRACKING_REF = "remote-tracking-ref"
KIND_FETCH_HEAD = "fetch-head"
KIND_REMOTE_REF = "remote-ref"
KIND_WORKTREE_DIR = "worktree-dir"
KIND_WORKTREE_REGISTRY = "worktree-registry"
GUARD_IDENTITY_KINDS = (
    KIND_INDEX,
    KIND_LOCAL_REF,
    KIND_REMOTE_TRACKING_REF,
    KIND_FETCH_HEAD,
    KIND_REMOTE_REF,
    KIND_WORKTREE_DIR,
    KIND_WORKTREE_REGISTRY,
)

#: local target は OS exclusive lock と CAS、remote target は server-side CAS が排他の実体。
_LOCAL_KINDS = frozenset(
    {
        KIND_INDEX,
        KIND_LOCAL_REF,
        KIND_REMOTE_TRACKING_REF,
        KIND_FETCH_HEAD,
        KIND_WORKTREE_DIR,
        KIND_WORKTREE_REGISTRY,
    }
)

_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
)


class CanonicalizationError(ValueError):
    """M2 targetを安全に一意化できない。呼び出し側は副作用0でBLOCKEDへ写像する。"""


@dataclasses.dataclass(frozen=True, init=False)
class WorktreeId:
    """registry entry名だけから生成できるopaqueなworktree ID。"""

    value: str

    @classmethod
    def _from_registry_name(cls, name: str) -> "WorktreeId":
        item = object.__new__(cls)
        object.__setattr__(item, "value", name)
        return item


def derive_worktree_id(common_dir: str | Path, registry_entry: str | Path) -> WorktreeId:
    """FLW-CON-006: common-dir/worktrees直下のentry名からのみIDを導出する。"""
    common = Path(common_dir).resolve()
    registry_root = (common / "worktrees").resolve(strict=False)
    entry = Path(registry_entry).resolve(strict=False)
    if entry.parent != registry_root or not entry.name or entry.name in {".", ".."}:
        raise CanonicalizationError("registry entryはcommon-dir/worktrees直下でなければならない")
    return WorktreeId._from_registry_name(entry.name)


def main_worktree_id() -> WorktreeId:
    """registry entryを持たないmain worktree専用sentinel。"""
    return WorktreeId._from_registry_name("@main")


@dataclasses.dataclass(frozen=True)
class GuardFailure:
    code: str
    reason: str
    stage: str = "validate"


@dataclasses.dataclass(frozen=True)
class Target:
    """canonical 化済みの mutation target。"""

    kind: str
    canonical_key: str

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "canonical_key": self.canonical_key}


@dataclasses.dataclass(frozen=True)
class HeldGuard:
    target: Target
    fencing_token: int


@dataclasses.dataclass
class GuardSet:
    """1 operation が保持する guard の束。"""

    operation_id: str
    held: tuple[HeldGuard, ...]
    family_lock: str | None = None

    def token_for(self, canonical_key: str) -> int | None:
        for guard in self.held:
            if guard.target.canonical_key == canonical_key:
                return guard.fencing_token
        return None

    @property
    def targets(self) -> tuple[Target, ...]:
        return tuple(g.target for g in self.held)


# --- canonical 化 -------------------------------------------------------------


def canonical_index_target(common_dir: str | Path, worktree_id: WorktreeId | str) -> Target:
    """M1互換入口。M2 worktree操作はstrictなcanonical_worktree_index_targetを使う。"""
    resolved = _resolve(common_dir)
    value = worktree_id.value if isinstance(worktree_id, WorktreeId) else worktree_id
    return Target(KIND_INDEX, f"{KIND_INDEX}:{_digest(resolved)}:{value}")


def canonical_worktree_index_target(common_dir: str | Path, worktree_id: WorktreeId) -> Target:
    """M2用入口。literal IDを拒否しregistry由来のopaque IDだけを受け取る。"""
    if not isinstance(worktree_id, WorktreeId):
        raise TypeError("worktree_idはderive_worktree_id()で導出する")
    return canonical_index_target(common_dir, worktree_id)


def canonical_worktree_dir_target(
    path: str | Path, *, approved_root: str | Path, case_sensitive: bool
) -> Target:
    """worktree directoryを実体identityまたは最寄り祖先identityへ収束させる。"""
    return _canonical_filesystem_target(
        KIND_WORKTREE_DIR, path, approved_root=approved_root, case_sensitive=case_sensitive
    )


def canonical_worktree_registry_target(
    common_dir: str | Path, registry_entry: str | Path, *, case_sensitive: bool
) -> Target:
    return _canonical_filesystem_target(
        KIND_WORKTREE_REGISTRY,
        registry_entry,
        approved_root=common_dir,
        case_sensitive=case_sensitive,
    )


def worktree_guard_targets(
    *,
    common_dir: str | Path,
    worktree_root: str | Path,
    worktree_path: str | Path,
    registry_entry: str | Path,
    local_ref: str,
    case_sensitive: bool,
    require_binding: bool = True,
) -> tuple[Target, ...]:
    """M2の3者+indexを一括導出し、index包含規約を呼出側から隠蔽する。"""
    worktree_id = derive_worktree_id(common_dir, registry_entry)
    if require_binding:
        verify_worktree_binding(common_dir, registry_entry, worktree_path)
    return tuple(
        order(
            [
                canonical_worktree_dir_target(
                    worktree_path, approved_root=worktree_root, case_sensitive=case_sensitive
                ),
                canonical_worktree_registry_target(
                    common_dir, registry_entry, case_sensitive=case_sensitive
                ),
                canonical_local_ref_target(common_dir, local_ref),
                canonical_worktree_index_target(common_dir, worktree_id),
            ]
        )
    )


def verify_worktree_binding(
    common_dir: str | Path, registry_entry: str | Path, worktree_path: str | Path
) -> None:
    """registryのgitdirとworktree側.git fileの双方向一致を検証する。"""
    entry = Path(registry_entry).resolve(strict=False)
    derive_worktree_id(common_dir, entry)
    gitdir_record = entry / "gitdir"
    worktree_dotgit = Path(worktree_path).resolve(strict=False) / ".git"
    try:
        recorded_dotgit = Path(gitdir_record.read_text(encoding="utf-8").strip()).resolve()
        reverse_text = worktree_dotgit.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise CanonicalizationError("worktree bindingの片側が欠落または読取不能") from exc
    if not reverse_text.startswith("gitdir:"):
        raise CanonicalizationError("worktree .git fileの形式が不正")
    reverse_entry = Path(reverse_text.split(":", 1)[1].strip()).resolve()
    if recorded_dotgit != worktree_dotgit.resolve() or reverse_entry != entry.resolve():
        raise CanonicalizationError("registry entryとworktree .gitの相互参照が一致しない")


def _canonical_filesystem_target(
    kind: str,
    raw_path: str | Path,
    *,
    approved_root: str | Path,
    case_sensitive: bool,
) -> Target:
    if not isinstance(case_sensitive, bool):
        raise CanonicalizationError("rootのcase感度が確定していない")
    raw_text = os.fspath(raw_path)
    _validate_portable_path(raw_text)
    root = Path(approved_root).resolve(strict=True)
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise CanonicalizationError("targetが承認済みroot外へescapeする") from exc

    if resolved.exists():
        if not resolved.is_dir():
            raise CanonicalizationError("worktree filesystem targetはdirectoryでなければならない")
        try:
            stat = resolved.stat()
            root_stat = root.stat()
        except OSError as exc:
            raise CanonicalizationError("stable filesystem identityを取得できない") from exc
        if stat.st_dev != root_stat.st_dev:
            raise CanonicalizationError("targetが承認済みrootと異なるvolumeへ解決された")
        return Target(kind, f"{kind}:{stat.st_dev}:{stat.st_ino}")

    ancestor = resolved
    suffix: list[str] = []
    while not ancestor.exists():
        if ancestor == root:
            break
        suffix.append(ancestor.name)
        parent = ancestor.parent
        if parent == ancestor:
            raise CanonicalizationError("存在する祖先へ到達できない")
        ancestor = parent
    try:
        ancestor.relative_to(root)
        stat = ancestor.stat()
    except (ValueError, OSError) as exc:
        raise CanonicalizationError("承認済みroot内の祖先identityを取得できない") from exc
    normalized = "/".join(
        _normalize_component(part, case_sensitive=case_sensitive) for part in reversed(suffix)
    )
    if not normalized:
        raise CanonicalizationError("不在targetの相対pathを一意化できない")
    return Target(kind, f"{kind}:{stat.st_dev}:{stat.st_ino}:{_digest(normalized)}")


def _normalize_component(component: str, *, case_sensitive: bool) -> str:
    normalized = unicodedata.normalize("NFC", component)
    return normalized if case_sensitive else normalized.casefold()


def _validate_portable_path(text: str) -> None:
    normalized = text.replace("\\", "/")
    if normalized.startswith(("//?/", "//./")) or normalized.startswith("//"):
        raise CanonicalizationError("device namespaceまたはroot外UNCは許可しない")
    components = [part for part in normalized.split("/") if part]
    if ".." in components:
        raise CanonicalizationError("parent traversalは許可しない")
    for index, component in enumerate(components):
        if component.endswith((".", " ")):
            raise CanonicalizationError("末尾dot/spaceは許可しない")
        stem = component.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED:
            raise CanonicalizationError("Windows予約device名は許可しない")
        if re.search(r"~[1-9](?:\.|$)", component, re.IGNORECASE):
            raise CanonicalizationError("8.3 short-name aliasは許可しない")
        if ":" in component and not (index == 0 and re.fullmatch(r"[A-Za-z]:", component)):
            raise CanonicalizationError("ADSを作るcolonは許可しない")


def canonical_local_ref_target(common_dir: str | Path, ref: str) -> Target:
    resolved = _resolve(common_dir)
    return Target(KIND_LOCAL_REF, f"{KIND_LOCAL_REF}:{_digest(resolved)}:{_normalize_ref(ref)}")


def canonical_fetch_head_target(common_dir: str | Path) -> Target:
    resolved = _resolve(common_dir)
    return Target(KIND_FETCH_HEAD, f"{KIND_FETCH_HEAD}:{_digest(resolved)}")


def canonical_remote_tracking_target(common_dir: str | Path, ref: str) -> Target:
    resolved = _resolve(common_dir)
    return Target(
        KIND_REMOTE_TRACKING_REF,
        f"{KIND_REMOTE_TRACKING_REF}:{_digest(resolved)}:{_normalize_ref(ref)}",
    )


def canonical_remote_ref_target(host: str, repository_id: str, ref: str) -> Target:
    """remote は canonical host + provider repository ID + ref name のみから導出する。

    local の clone 位置・remote alias・URL 形式を混ぜない（同じ remote ref を別 target に
    見せてしまい、同時 publish を許すため）。
    """
    return Target(
        KIND_REMOTE_REF,
        f"{KIND_REMOTE_REF}:{host.strip().lower()}:{repository_id.strip()}:{_normalize_ref(ref)}",
    )


def _resolve(path: str | Path) -> str:
    """symlink・相対 path・case 差を吸収する。"""
    resolved = Path(path).resolve()
    text = PurePosixPath(resolved).as_posix()
    if not _case_sensitive_filesystem(resolved):
        text = text.lower()
    return text


def _case_sensitive_filesystem(path: Path) -> bool:
    """大文字小文字を区別しない filesystem では case 差を同一視する必要がある。

    実際に case を反転した path が見えるかで判定する（マウント単位で異なるため、
    OS 名では決められない）。
    """
    probe = path if path.exists() else path.parent
    swapped = str(probe).swapcase()
    if swapped == str(probe):
        return True  # 英字が無く判定材料がない。case-sensitive 側（変換しない）に倒す。
    try:
        return not os.path.exists(swapped)
    except OSError:
        return True


def _normalize_ref(ref: str) -> str:
    text = ref.strip()
    for prefix in ("refs/heads/", "refs/remotes/", "refs/tags/"):
        if text.startswith(prefix):
            return text
    if text.startswith("refs/"):
        return text
    return f"refs/heads/{text}"


def _digest(text: str) -> str:
    return R.sha256_of(text.encode("utf-8"))[7:23]


def order(targets: Iterable[Target]) -> list[Target]:
    """canonical key の bytewise 昇順。重複は畳む（alias が同じ target へ収束するため）。"""
    unique: dict[str, Target] = {}
    for target in targets:
        unique.setdefault(target.canonical_key, target)
    return sorted(unique.values(), key=lambda t: t.canonical_key.encode("utf-8"))


# --- capability ---------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Capability:
    """platform が提供できる排他手段。"""

    advisory_lock: bool = True
    owner_only_area: bool = True
    fsync: bool = True
    remote_cas: bool = True

    def missing_for(self, targets: Sequence[Target]) -> list[str]:
        missing: list[str] = []
        if not self.advisory_lock:
            missing.append("advisory lock")
        if not self.owner_only_area:
            missing.append("owner-only 永続領域")
        if not self.fsync:
            missing.append("fsync")
        if not self.remote_cas and any(t.kind == KIND_REMOTE_REF for t in targets):
            missing.append("remote の server-side CAS")
        return missing


# --- guard 取得 ---------------------------------------------------------------


class TargetGuardManager:
    """target guard の取得・解放・照合。

    `cas_acquire` は「その target を今から自分が所有してよいか」を linearizable に決める関数で、
    coordinator core 側の CAS を渡す想定。lock file の存在を所有証明にしない。
    """

    def __init__(self, *, capability: Capability | None = None) -> None:
        self._capability = capability or Capability()
        self._owners: dict[str, str] = {}
        self._tokens: dict[str, int] = {}
        self._families: dict[str, str] = {}
        self._pending: dict[str, str] = {}
        self._quarantined: dict[str, str] = {}

    # -- 既存 pending / quarantine -------------------------------------------

    def mark_pending(self, target: Target, operation_id: str) -> None:
        self._pending[target.canonical_key] = operation_id

    def mark_quarantined(self, target: Target, reason: str) -> None:
        self._quarantined[target.canonical_key] = reason

    def clear(self, target: Target) -> None:
        self._pending.pop(target.canonical_key, None)
        self._quarantined.pop(target.canonical_key, None)

    def existing_block(self, targets: Sequence[Target]) -> GuardFailure | None:
        for target in targets:
            if target.canonical_key in self._quarantined:
                return GuardFailure(
                    CODE_BLOCKED,
                    f"quarantine 中の target には新しい intent を作らない: {target.canonical_key}",
                )
            if target.canonical_key in self._pending:
                return GuardFailure(
                    CODE_BLOCKED,
                    f"pending intent が残る target には新しい intent を作らない: {target.canonical_key}",
                )
        return None

    # -- 取得 ----------------------------------------------------------------

    def acquire(
        self,
        raw_targets: Sequence[Target],
        *,
        operation_id: str,
        next_token,
        family_lock: str | None = None,
        family_lock_already_held: bool = False,
    ) -> tuple[GuardSet | None, GuardFailure | None]:
        """target guard を canonical 昇順で取得する。

        `family_lock_already_held` が真なら順序違反として拒否する
        （target guard は family lock より**先**に取らなければならない）。
        """
        if not raw_targets:
            return None, GuardFailure(CODE_INVALID_INPUT, "target が空")
        for target in raw_targets:
            if target.kind not in GUARD_IDENTITY_KINDS:
                return None, GuardFailure(
                    CODE_INVALID_INPUT, f"未知の guard identity: {target.kind}"
                )
            if not target.canonical_key:
                return None, GuardFailure(
                    CODE_BLOCKED, "target を一意化できないため write しない"
                )

        ordered = order(raw_targets)

        missing = self._capability.missing_for(ordered)
        if missing:
            return None, GuardFailure(
                CODE_UNSUPPORTED,
                "排他手段を提供できない platform では write しない: " + ", ".join(missing),
            )

        if family_lock_already_held:
            return None, GuardFailure(
                CODE_BLOCKED,
                "family lock を先に取得している（target guard を先に取らなければならない）",
            )

        blocked = self.existing_block(ordered)
        if blocked is not None:
            return None, blocked

        held: list[HeldGuard] = []
        for target in ordered:
            owner = self._owners.get(target.canonical_key)
            if owner is not None and owner != operation_id:
                # 途中失敗 → 取得済みを逆順で解放し、副作用 0 で戻る。
                self._release(held, operation_id)
                return None, GuardFailure(
                    CODE_BLOCKED,
                    f"target guard が競合した: {target.canonical_key}",
                )
            token = next_token(target.canonical_key)
            self._owners[target.canonical_key] = operation_id
            self._tokens[target.canonical_key] = token
            held.append(HeldGuard(target=target, fencing_token=token))

        if family_lock is not None:
            current = self._families.get(family_lock)
            if current is not None and current != operation_id:
                self._release(held, operation_id)
                return None, GuardFailure(
                    CODE_BLOCKED, f"family lock が競合した: {family_lock}"
                )
            self._families[family_lock] = operation_id

        return GuardSet(operation_id=operation_id, held=tuple(held), family_lock=family_lock), None

    def _release(self, held: Sequence[HeldGuard], operation_id: str) -> None:
        for guard in reversed(list(held)):
            if self._owners.get(guard.target.canonical_key) == operation_id:
                self._owners.pop(guard.target.canonical_key, None)
                self._tokens.pop(guard.target.canonical_key, None)

    def release(self, guard_set: GuardSet) -> None:
        """解放は逆順。冪等。"""
        self._release(guard_set.held, guard_set.operation_id)
        if guard_set.family_lock is not None:
            if self._families.get(guard_set.family_lock) == guard_set.operation_id:
                self._families.pop(guard_set.family_lock, None)

    # -- 副作用直前の再照合 --------------------------------------------------

    def verify_before_mutation(
        self, guard_set: GuardSet, target: Target
    ) -> GuardFailure | None:
        """各副作用の直前に identity・所有・fencing token を再照合する。"""
        key = target.canonical_key
        if guard_set.token_for(key) is None:
            return GuardFailure(CODE_BLOCKED, f"guard を保持していない target への mutation: {key}")
        if self._owners.get(key) != guard_set.operation_id:
            return GuardFailure(CODE_BLOCKED, f"guard の所有者が変わっている: {key}")
        if self._tokens.get(key) != guard_set.token_for(key):
            return GuardFailure(
                CODE_BLOCKED, f"fencing token が発行時から変わっている: {key}"
            )
        return None

    def held_targets(self) -> list[str]:
        return sorted(self._owners)
