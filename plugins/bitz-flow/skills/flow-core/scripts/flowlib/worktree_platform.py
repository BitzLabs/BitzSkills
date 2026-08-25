"""Local Safety Profileのplatform evidence adapter（FLW-TSK-111）。

OS固有probeの観測結果をclosed evidenceへ写し、コード同梱allowlistとsemantic
self-testの両方が成立した場合だけsupportedにする。外部profileや署名policyは扱わない。
"""

from __future__ import annotations

import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .worktree_contract import (
    CONTRACT_VERSION,
    ContractError,
    canonical_json_bytes,
    native_component_from_posix,
    native_component_from_windows,
    native_component_to_posix,
    native_component_to_windows,
    sha256_digest,
    validate_digest,
)

PROFILE_VERSION = 1
SUPPORTED = "SUPPORTED"
UNSUPPORTED_FILESYSTEM = "UNSUPPORTED_FILESYSTEM"
PLATFORMS = frozenset({"linux", "macos", "windows"})

#: 保証対象の platform（裁定 2026-08-24。`FLW-REV-028:GP-003`）。
#: macOS / Windows の probe 実装は残すが保証しない。macOS は既定 APFS が
#: case-insensitive で `collision_key` の folded_component を導出できず、Windows は
#: SID 取得手段が無い。対象外は理由付きで `UNSUPPORTED_FILESYSTEM` へ閉じる。
#: 再開条件は `.spec/reports/decision-2026-08-24-linux-only-scope.md` を参照。
SUPPORTED_SCOPE = frozenset({"linux"})
FILESYSTEM_CLASSES = frozenset({"local", "network", "unknown"})
CASE_SEMANTICS = frozenset({"sensitive", "insensitive"})


@dataclass(frozen=True)
class SupportProfile:
    platform: str
    filesystem_types: frozenset[str]
    owner_model: str
    lock_primitive: str
    file_durability: str
    directory_durability: str
    child_supervision: str


@dataclass(frozen=True)
class PlatformObservation:
    platform: str
    filesystem_type: str
    filesystem_class: str
    owner_principal: str | None
    owner_matches: bool
    acl_owner_only: bool
    non_follow_walk: bool
    resource_kind: str
    resource_identity: str
    native_component: Mapping[str, str]
    case_semantics: str
    os_lock: bool
    file_durability: bool
    directory_durability: bool
    child_supervision: bool


@dataclass(frozen=True)
class PlatformEvidence:
    observation: PlatformObservation
    support_code: str
    reasons: tuple[str, ...]

    @property
    def supported(self) -> bool:
        return self.support_code == SUPPORTED

    def as_mapping(self) -> dict[str, object]:
        value = {
            "contract_version": CONTRACT_VERSION,
            "profile_version": PROFILE_VERSION,
            **self.observation.__dict__,
            "native_component": dict(self.observation.native_component),
            "support_code": self.support_code,
            "reasons": list(self.reasons),
        }
        return value


def _require_fields(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if not isinstance(value, Mapping) or set(value) != expected:
        actual = set(value) if isinstance(value, Mapping) else set()
        raise ContractError(
            f"{label} fields mismatch: missing={sorted(expected-actual)}, unknown={sorted(actual-expected)}"
        )


def load_support_profiles(path: str | Path) -> dict[str, SupportProfile]:
    """コード同梱static registryをclosed形式で読む。"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    _require_fields(raw, {"schema_version", "profiles"}, "platform support registry")
    if raw["schema_version"] != PROFILE_VERSION or not isinstance(raw["profiles"], list):
        raise ContractError("unsupported platform support registry")
    fields = {
        "platform", "filesystem_types", "owner_model", "lock_primitive",
        "file_durability", "directory_durability", "child_supervision",
    }
    profiles: dict[str, SupportProfile] = {}
    for item in raw["profiles"]:
        _require_fields(item, fields, "platform support profile")
        platform = item["platform"]
        filesystems = item["filesystem_types"]
        if platform not in PLATFORMS or platform in profiles:
            raise ContractError("unknown or duplicate platform support profile")
        if not isinstance(filesystems, list) or not filesystems or any(
            not isinstance(name, str) or not name or name.lower() != name for name in filesystems
        ) or len(filesystems) != len(set(filesystems)):
            raise ContractError("filesystem allowlist must be unique lowercase names")
        values = [item[name] for name in fields - {"platform", "filesystem_types"}]
        if any(not isinstance(value, str) or not value for value in values):
            raise ContractError("platform primitive identifiers must be non-empty strings")
        profiles[platform] = SupportProfile(
            platform,
            frozenset(filesystems),
            item["owner_model"],
            item["lock_primitive"],
            item["file_durability"],
            item["directory_durability"],
            item["child_supervision"],
        )
    if set(profiles) != PLATFORMS:
        raise ContractError("platform support registry must cover the three registered platforms")
    return profiles


def support_registry_digest(profiles: Mapping[str, SupportProfile]) -> str:
    value = [
        {
            "platform": profile.platform,
            "filesystem_types": sorted(profile.filesystem_types),
            "owner_model": profile.owner_model,
            "lock_primitive": profile.lock_primitive,
            "file_durability": profile.file_durability,
            "directory_durability": profile.directory_durability,
            "child_supervision": profile.child_supervision,
        }
        for profile in sorted(profiles.values(), key=lambda item: item.platform)
    ]
    return sha256_digest(canonical_json_bytes({"schema_version": PROFILE_VERSION, "profiles": value}))


def _validate_native_component(platform: str, value: Mapping[str, str]) -> None:
    if platform in {"linux", "macos"}:
        native_component_to_posix(value)
    else:
        native_component_to_windows(value)


def evaluate_platform(
    observation: PlatformObservation,
    *,
    profiles: Mapping[str, SupportProfile],
) -> PlatformEvidence:
    """観測不能を推測で補わず、理由をclosed evidenceへ残す。"""
    boolean_fields = (
        "owner_matches", "acl_owner_only", "non_follow_walk", "os_lock",
        "file_durability", "directory_durability", "child_supervision",
    )
    if any(type(getattr(observation, name)) is not bool for name in boolean_fields):
        raise ContractError("platform observation flags must be booleans")
    if observation.platform not in PLATFORMS:
        raise ContractError("unknown platform discriminator")
    if (
        not isinstance(observation.filesystem_type, str)
        or not observation.filesystem_type
        or observation.filesystem_type.lower() != observation.filesystem_type
    ):
        raise ContractError("filesystem type must be a non-empty lowercase name")
    if observation.filesystem_class not in FILESYSTEM_CLASSES:
        raise ContractError("unknown filesystem class")
    if observation.case_semantics not in CASE_SEMANTICS:
        raise ContractError("unknown case semantics")
    if observation.resource_kind not in {"file", "directory"}:
        raise ContractError("unknown resource identity kind")
    validate_digest(observation.resource_identity)
    _validate_native_component(observation.platform, observation.native_component)
    profile = profiles.get(observation.platform)
    reasons: list[str] = []
    if observation.platform not in SUPPORTED_SCOPE:
        # 実装があることと保証することは別である（`FLW-REV-028:GP-003`）。
        reasons.append("platform-out-of-scope")
    if observation.case_semantics == "insensitive":
        # `collision_key` は case-insensitive のとき folded_component を要求するが、
        # 実物の case-insensitive volume を観測できない環境で folding 規則を作ると
        # 「検証していない性質の主張」になり、§3.1 の畳み込み禁止にも触れる。
        # 案 B（裁定済み）に従い閉じる。`collision_key` へ到達させない。
        reasons.append("case-insensitive-unsupported")
    if profile is None:
        reasons.append("platform-not-allowlisted")
    if observation.filesystem_class != "local":
        reasons.append(f"filesystem-class-{observation.filesystem_class}")
    if profile is not None and observation.filesystem_type.lower() not in profile.filesystem_types:
        reasons.append("filesystem-type-not-allowlisted")
    checks = {
        "owner-unobservable": (
            isinstance(observation.owner_principal, str)
            and bool(observation.owner_principal)
        ),
        "owner-mismatch": observation.owner_matches,
        "acl-not-owner-only": observation.acl_owner_only,
        "non-follow-walk-unavailable": observation.non_follow_walk,
        "os-lock-unavailable": observation.os_lock,
        "file-durability-unavailable": observation.file_durability,
        "directory-durability-unavailable": observation.directory_durability,
        "child-supervision-unavailable": observation.child_supervision,
    }
    reasons.extend(reason for reason, passed in checks.items() if not passed)
    return PlatformEvidence(
        observation,
        SUPPORTED if not reasons else UNSUPPORTED_FILESYSTEM,
        tuple(sorted(reasons)),
    )


def collision_key(
    *,
    parent_identity: str,
    native_component: Mapping[str, str],
    case_semantics: str,
    folded_component: Mapping[str, str] | None = None,
) -> str:
    """不在targetをparent identityとnative componentへ束縛する。"""
    validate_digest(parent_identity)
    if case_semantics not in CASE_SEMANTICS:
        raise ContractError("unknown case semantics")
    platform = native_component.get("platform")
    if platform == "posix":
        native_component_to_posix(native_component)
    elif platform == "windows":
        native_component_to_windows(native_component)
    else:
        raise ContractError("unknown native component platform")
    selected = native_component
    if case_semantics == "insensitive":
        if folded_component is None or folded_component.get("platform") != platform:
            raise ContractError("case-insensitive target requires a platform-derived folded component")
        if platform == "posix":
            native_component_to_posix(folded_component)
        else:
            native_component_to_windows(folded_component)
        selected = folded_component
    return sha256_digest(canonical_json_bytes({
        "parent_identity": parent_identity,
        "case_semantics": case_semantics,
        "component": dict(selected),
    }))


# --- 実環境probe（FLW-TSK-116 / SI-FLW-084） ---------------------------------
#
# `evaluate_platform` は観測を評価するだけで、観測そのものは行わない。probe が無い間、
# production から `PlatformObservation` を構築する経路が存在せず、`plan()` は必ず
# `platform evidence is required` で停止していた（`FLW-REV-027:SYN-001`）。
#
# probe は **read-only** である。対象 filesystem へ書き込まない。durability と lock は
# 「この runtime で primitive が利用可能か」を検査し、書き込みによる実証は行わない。

#: 明らかに network / 非ローカルな filesystem。allowlist とは別に class を決める。
NETWORK_FILESYSTEMS = frozenset({
    "9p", "afs", "ceph", "cifs", "davfs", "ftpfs", "fuse.sshfs", "glusterfs",
    "ncpfs", "nfs", "nfs4", "smb2", "smb3", "smbfs", "sshfs", "vboxsf", "virtiofs",
})


def current_platform() -> str | None:
    """OS 判別子。未知の OS は推測せず None を返す。"""
    if os.name == "nt":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    return None


def classify_filesystem(filesystem_type: str | None) -> tuple[str, str]:
    """(filesystem_type, filesystem_class) を返す。判別できなければ unknown へ閉じる。"""
    if not filesystem_type:
        return "unknown", "unknown"
    name = filesystem_type.strip().lower()
    if not name:
        return "unknown", "unknown"
    if name in NETWORK_FILESYSTEMS or name.startswith("fuse."):
        return name, "network"
    if name == "unknown":
        return "unknown", "unknown"
    return name, "local"


def _unescape_mountinfo(value: str) -> str:
    """mountinfo の 8 進 escape（`\\040` 等）を解く。"""
    out, index = [], 0
    while index < len(value):
        if value[index] == "\\" and value[index + 1:index + 4].isdigit():
            out.append(chr(int(value[index + 1:index + 4], 8)))
            index += 4
        else:
            out.append(value[index])
            index += 1
    return "".join(out)


def select_mount_type(lines, target: Path) -> str | None:
    """mountinfo の行集合から target が属する mount の fstype を選ぶ。

    **mount point の最長一致**で選ぶ。st_dev（major:minor）は bind mount 間で共有される
    ため識別子として不十分であり、先頭一致では親マウントの種別を返してしまう
    （`FLW-REV-028:SYN-010`）。行順に依存しないよう深さで比較する。

    file 読み取りから分離してあるのは、bind mount を作るには root が要り、
    振る舞いを実環境で対照できないためである（合成データで検証する）。
    """
    absolute = Path(os.path.abspath(str(target)))
    best_type, best_depth = None, -1
    for line in lines:
        fields = line.split()
        if len(fields) < 5 or "-" not in fields:
            continue
        mount_point = Path(_unescape_mountinfo(fields[4]))
        try:
            absolute.relative_to(mount_point)
        except ValueError:
            continue
        depth = len(mount_point.parts)
        if depth <= best_depth:
            continue
        separator = fields.index("-")
        if len(fields) <= separator + 1:
            continue
        best_type, best_depth = fields[separator + 1], depth
    return best_type


def _linux_filesystem_type(target: Path) -> str | None:
    """`/proc/self/mountinfo` から target が属する mount の fstype を求める。"""
    try:
        lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    try:
        return select_mount_type(lines, target)
    except (OSError, ValueError, IndexError):
        return None


def _macos_filesystem_type(target: Path) -> str | None:
    """`statfs(2)` の `f_fstypename` を ctypes で読む。"""
    try:
        import ctypes

        class _Statfs(ctypes.Structure):
            _fields_ = [
                ("f_bsize", ctypes.c_uint32), ("f_iosize", ctypes.c_int32),
                ("f_blocks", ctypes.c_uint64), ("f_bfree", ctypes.c_uint64),
                ("f_bavail", ctypes.c_uint64), ("f_files", ctypes.c_uint64),
                ("f_ffree", ctypes.c_uint64), ("f_fsid", ctypes.c_int32 * 2),
                ("f_owner", ctypes.c_uint32), ("f_type", ctypes.c_uint32),
                ("f_flags", ctypes.c_uint32), ("f_fssubtype", ctypes.c_uint32),
                ("f_fstypename", ctypes.c_char * 16),
                ("f_mntonname", ctypes.c_char * 1024),
                ("f_mntfromname", ctypes.c_char * 1024),
                ("f_reserved", ctypes.c_uint32 * 8),
            ]

        libc = ctypes.CDLL("libc.dylib", use_errno=True)
        buffer = _Statfs()
        if libc.statfs(os.fsencode(str(target)), ctypes.byref(buffer)) != 0:
            return None
        return buffer.f_fstypename.decode("ascii", "replace") or None
    except (OSError, AttributeError, ValueError):
        return None


def _windows_volume(target: Path) -> tuple[str | None, bool]:
    """`GetVolumeInformationW` から (filesystem 名, case-sensitive か) を得る。"""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        root = ctypes.c_wchar_p(str(Path(target).anchor))
        name = ctypes.create_unicode_buffer(261)
        flags = wintypes.DWORD()
        ok = kernel32.GetVolumeInformationW(
            root, None, 0, None, None, ctypes.byref(flags), name, ctypes.sizeof(name)
        )
        if not ok:
            return None, False
        # FILE_CASE_SENSITIVE_SEARCH = 0x00000001
        return (name.value or None), bool(flags.value & 0x1)
    except (OSError, AttributeError, ValueError):
        return None, False


def _case_semantics(target: Path) -> str | None:
    """対象 entry が属する directory の lookup semantics を判定する。

    以前は **絶対 path 全体** を swapcase して存在確認していたため、祖先の case 差に
    引きずられて mount 単位の semantics を測れなかった（`FLW-REV-028:SYN-010`）。
    誤って `sensitive` と判定すると `collision_key` が case alias を畳めず、
    同一資源への競合が直列化されない。

    判定は対象 entry 名だけを反転して**同一 parent 内**で引き、見つかった場合は
    `(st_dev, st_ino)` の一致で同一 entry かを確かめる（同名の別 entry を
    insensitive と誤認しないため）。書き込みは行わない。
    判定材料が無ければ None を返す（推測しない）。
    """
    probe = target if target.exists() else target.parent
    name = probe.name
    if not name or name.swapcase() == name:
        return None      # 英字が無く判定材料がない
    sibling = probe.parent / name.swapcase()
    try:
        if not sibling.exists():
            return "sensitive"
        here, there = os.stat(probe), os.stat(sibling)
        if (here.st_dev, here.st_ino) == (there.st_dev, there.st_ino):
            return "insensitive"
        return "sensitive"   # 同名の別 entry が存在するだけ
    except OSError:
        return None


def _owner(target: Path) -> tuple[str | None, bool, bool]:
    """(owner_principal, owner_matches, acl_owner_only) を返す。"""
    try:
        info = os.stat(target)
    except OSError:
        return None, False, False
    if os.name == "nt":
        # SID を取得できる保証が無い。取得できないものを owner として名乗らない。
        return None, False, False
    try:
        principal = str(info.st_uid)
        matches = info.st_uid == os.geteuid()
    except (AttributeError, OSError):
        return None, False, False
    acl_owner_only = not (info.st_mode & 0o077)
    return principal, matches, acl_owner_only


def _primitives(platform: str, profile: SupportProfile | None) -> dict[str, bool]:
    """registry が宣言する primitive が、この runtime で実際に使えるかを検査する。"""
    if os.name == "nt":
        lock = _has_windows_locking()
        directory_durability = hasattr(os, "replace")
        supervision = _has_windows_job_object()
    else:
        try:
            import fcntl
            lock = hasattr(fcntl, "flock")
        except ImportError:
            lock = False
        directory_durability = hasattr(os, "fsync") and hasattr(os, "O_DIRECTORY")
        supervision = hasattr(os, "killpg") and hasattr(os, "getpgid")
    values = {
        "os_lock": bool(lock),
        "file_durability": hasattr(os, "fsync"),
        "directory_durability": bool(directory_durability),
        "child_supervision": bool(supervision),
        "non_follow_walk": _has_non_follow_walk(),
    }
    if profile is not None:
        # registry の宣言と実際に使える primitive が食い違う場合は supported にしない。
        expected_supervision = {"waitpid": not _is_nt(), "job-object": _is_nt()}
        values["child_supervision"] = bool(
            values["child_supervision"]
            and expected_supervision.get(profile.child_supervision, False)
        )
    return values


def _is_nt() -> bool:
    return os.name == "nt"


def _has_non_follow_walk() -> bool:
    """symlink を追わない走査に必要な primitive が使えるか（能力の検査）。"""
    if not hasattr(os, "scandir") or not hasattr(os, "lstat"):
        return False
    if _is_nt():
        return True
    return hasattr(os, "O_NOFOLLOW")


def path_is_symlink_free(target: Path) -> bool | None:
    """root から target まで component 単位に lstat し、symlink が無いことを**実証**する。

    以前は primitive の存在確認だけで `non_follow_walk=True` を主張していたため、
    symlink 経由の root が `SUPPORTED` になった（`FLW-REV-028:SYN-008`）。§1.2 は
    「非 symlink/reparse-point の namespace」を信頼すると規定しており、追跡した path で
    その性質を名乗ってはならない。

    True=symlink 無し / False=symlink あり / None=観測不能（推測しない）。
    """
    try:
        absolute = Path(os.path.abspath(str(target)))
        current = Path(absolute.anchor or os.sep)
        for part in absolute.relative_to(current).parts:
            current = current / part
            try:
                info = os.lstat(current)
            except FileNotFoundError:
                # 未作成の create target 以降は観測対象にしない。
                return True
            if stat.S_ISLNK(info.st_mode):
                return False
        return True
    except (OSError, ValueError, RuntimeError):
        return None


def _has_windows_locking() -> bool:
    try:
        import ctypes

        return hasattr(ctypes.WinDLL("kernel32", use_last_error=True), "LockFileEx")
    except (OSError, AttributeError, ValueError):
        return False


def _has_windows_job_object() -> bool:
    try:
        import ctypes

        return hasattr(ctypes.WinDLL("kernel32", use_last_error=True), "CreateJobObjectW")
    except (OSError, AttributeError, ValueError):
        return False


def _native_component(platform: str, target: Path) -> Mapping[str, str] | None:
    try:
        if platform == "windows":
            return native_component_from_windows(target.name).as_mapping()
        return native_component_from_posix(os.fsencode(target.name)).as_mapping()
    except (ContractError, ValueError, TypeError):
        return None


def _resource_identity(target: Path) -> tuple[str, str] | None:
    try:
        info = os.stat(target)
    except OSError:
        return None
    kind = "directory" if os.path.isdir(target) else "file"
    return kind, sha256_digest(f"{info.st_dev}:{info.st_ino}".encode("ascii"))


#: 同梱 support registry。plan と doctor はこの1本を共有する（`SI-FLW-084`）。
SUPPORT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2] / "references" / "worktree-v2-platform-support.json"
)


#: 不支持理由ごとの operator action。`human-stop` の `required_human_input` へ載せる
#: （`FLW-REV-028:GP-001`）。理由を出すだけでは利用者が自力で復帰できない。
OPERATOR_ACTIONS = {
    "acl-not-owner-only": "worktree root を owner-only にする（mode 0700。group/other の権限を落とす）",
    "owner-mismatch": "worktree root の所有者を実行ユーザーへ変更する",
    "owner-unobservable": "所有者を観測できる filesystem 上へ worktree root を置く",
    "platform-out-of-scope": "保証対象は Linux のみである。Linux 上で実行する",
    "platform-not-allowlisted": "同梱 registry に登録された platform 上で実行する",
    "case-insensitive-unsupported": "case-sensitive な filesystem 上へ worktree root を置く",
    "filesystem-type-not-allowlisted": "永続 filesystem（btrfs / ext4 / xfs）上へ worktree root を置く。tmpfs は再起動で消えるため対象外",
    "non-follow-walk-unavailable": "symlink を含まない path へ worktree root を置く",
    "os-lock-unavailable": "OS lock が使える filesystem 上へ worktree root を置く",
    "file-durability-unavailable": "fsync が使える filesystem 上へ worktree root を置く",
    "directory-durability-unavailable": "directory fsync が使える filesystem 上へ worktree root を置く",
    "child-supervision-unavailable": "child process を監督できる環境で実行する",
    "support-registry-unreadable": "bitz-flow の配布物が破損している。再インストールする",
    "target-path-unobservable": "worktree root の親 directory が存在し読み取り可能であることを確認する",
    "resource-identity-unobservable": "worktree root を stat できる filesystem 上へ置く",
    "native-component-unobservable": "worktree root の名前に使えない byte 列が含まれていないか確認する",
}


def operator_action(reasons, *, target: str | Path | None = None) -> str:
    """不支持理由から行動可能な operator action を組み立てる。

    理由をそのまま返すだけでは「なぜ動かないか」は判っても「どうすれば動くか」が
    判らない。既知の理由には具体的な是正を、未知の理由には doctor への誘導を返す。
    """
    known = [OPERATOR_ACTIONS[r] for r in reasons if r in OPERATOR_ACTIONS]
    if not known:
        known = ["doctor で環境診断を実行し、報告された理由を解消する"]
    prefix = f"対象: {target}。" if target is not None else ""
    return prefix + " / ".join(dict.fromkeys(known))


def platform_evidence_for(path: str | Path) -> PlatformEvidence:
    """production 共通の evidence 生成器。

    plan と doctor が別々に観測すると、doctor が緑でも plan が別判定になりうる。
    生成器を1本にして、両者が同じ registry と同じ probe を通ることを保証する。
    registry が読めない場合も例外にせず closed evidence へ閉じる。
    """
    try:
        profiles = load_support_profiles(SUPPORT_REGISTRY_PATH)
    except (OSError, ValueError, ContractError, json.JSONDecodeError):
        return _unobservable("support-registry-unreadable")
    return probe_platform(path, profiles=profiles)


def probe_platform(
    path: str | Path, *, profiles: Mapping[str, SupportProfile]
) -> PlatformEvidence:
    """実環境を read-only で観測し closed evidence を返す。

    **例外を送出しない。** 観測できない項目は supported へ格上げせず、
    `UNSUPPORTED_FILESYSTEM` と理由へ閉じる。呼び出し側は `evidence.supported` と
    `evidence.reasons` だけを見ればよい。
    """
    platform = current_platform()
    if platform is None:
        return _unobservable("unknown-platform")
    # symlink 実証は **解決前の path** に対して行う。resolve() は symlink を解いて
    # しまうため、解決後を検査しても常に「symlink 無し」になる。
    requested = Path(path)
    symlink_free = path_is_symlink_free(requested)
    try:
        # 相対 path のままだと case 判定材料（英字）が無いことがある。存在しない
        # create target も扱うため strict=False で解決する。
        target = Path(path).resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return _unobservable("target-path-unobservable", platform=platform)
    anchor = target if target.exists() else target.parent
    if not anchor.exists():
        return _unobservable("target-path-unobservable", platform=platform)

    if platform == "linux":
        raw_type, case_flag = _linux_filesystem_type(anchor), None
    elif platform == "macos":
        raw_type, case_flag = _macos_filesystem_type(anchor), None
    else:
        raw_type, case_flag = _windows_volume(anchor)
    filesystem_type, filesystem_class = classify_filesystem(raw_type)

    case_semantics = _case_semantics(anchor)
    if case_semantics is None and case_flag is not None:
        case_semantics = "sensitive" if case_flag else "insensitive"
    if case_semantics is None:
        return _unobservable("case-semantics-unobservable", platform=platform)

    identity = _resource_identity(anchor)
    if identity is None:
        return _unobservable("resource-identity-unobservable", platform=platform)
    resource_kind, resource_identity = identity

    component = _native_component(platform, target)
    if component is None:
        return _unobservable("native-component-unobservable", platform=platform)

    principal, owner_matches, acl_owner_only = _owner(anchor)
    profile = profiles.get(platform)
    primitives = _primitives(platform, profile)
    # 能力の有無だけでなく、要求された path が実際に symlink を含まないことを実証する。
    primitives["non_follow_walk"] = bool(primitives["non_follow_walk"] and symlink_free)

    observation = PlatformObservation(
        platform=platform,
        filesystem_type=filesystem_type,
        filesystem_class=filesystem_class,
        owner_principal=principal,
        owner_matches=owner_matches,
        acl_owner_only=acl_owner_only,
        non_follow_walk=primitives["non_follow_walk"],
        resource_kind=resource_kind,
        resource_identity=resource_identity,
        native_component=component,
        case_semantics=case_semantics,
        os_lock=primitives["os_lock"],
        file_durability=primitives["file_durability"],
        directory_durability=primitives["directory_durability"],
        child_supervision=primitives["child_supervision"],
    )
    try:
        return evaluate_platform(observation, profiles=profiles)
    except ContractError as exc:
        return _unobservable(f"observation-rejected-{type(exc).__name__}", platform=platform)


def _unobservable(reason: str, *, platform: str | None = None) -> PlatformEvidence:
    """観測不能を closed evidence として表す（例外にしない）。"""
    observation = PlatformObservation(
        platform=platform or "linux", filesystem_type="unknown", filesystem_class="unknown",
        owner_principal=None, owner_matches=False, acl_owner_only=False,
        non_follow_walk=False, resource_kind="directory",
        resource_identity=sha256_digest(b"unobservable"),
        native_component=native_component_from_posix(b"unobservable").as_mapping(),
        case_semantics="sensitive", os_lock=False, file_durability=False,
        directory_durability=False, child_supervision=False,
    )
    return PlatformEvidence(observation, UNSUPPORTED_FILESYSTEM, (reason,))
