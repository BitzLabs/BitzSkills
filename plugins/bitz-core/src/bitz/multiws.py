"""複合workspaceの全体事前検査（`02_SPECモデル/05_複合workspace仕様.md`）。

Step 5A範囲: §2（catalog）、§3（workspace決定・`--workspace`終了コード4）、§5.1（member path
canonical判定のうちsegment境界・symlink・submodule・別worktree／repository）、§8（全体操作の発見と
Git既知設定の事前検査）、§10（snapshot全体のresource上限と早期停止）を実装する。

事前検査が非成功なら :func:`precheck` は ``ok=False`` を返し、呼び出し側（`check.py`／`doctor.py`）は
member処理（横断relation解決、member単位のcheck/verify/context）を一切開始せず、`workspaces: []`の
全体結果を返す（複合workspace仕様 §8「非成功ならmember処理、Context解決、verify commandを開始せず、
workspaces: []で結果を返す」）。member処理そのものはStep 5B・5Cで実装するため、事前検査を通過した
場合は呼び出し側が既存の:class:`~bitz.notimpl.NotImplementedOperation`の作法で明示的に停止する。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import config as config_mod
from . import gitutil
from . import lex
from . import messages
from .config import Diagnostic
from .earsai.scanner import scan_candidates
from .resultmodel import worst_status
from .yamlsafe import YamlForbiddenError, YamlSyntaxError, parse_yaml_subset

# 優先順位（`Diagnostic registry` §7・複合workspace仕様 §11）。同じmember／同じraw原因に複数の
# 候補codeが成立する場合、最小priorityの1件だけを残す（`_PRIORITY.get`未知codeは0＝最優先として
# 扱う。member配下から返る一般的なSPEC-CONFIG-*系はmulti系codeより常に優先する）。
_PRIORITY = {
    "SPEC-MULTI-CONFIG-001": 900,
    "SPEC-MULTI-MEMBER-001": 910,
    "SPEC-MULTI-ID-001": 920,
    "SPEC-MULTI-PATH-001": 930,
    "SPEC-MULTI-GIT-001": 940,
    "SPEC-MULTI-VERSION-001": 950,
    "SPEC-MULTI-UNREGISTERED-001": 960,
    "SPEC-MULTI-LIMIT-001": 970,
}

ROOT_CONFIG_PATH = config_mod.CONFIG_PATH  # ".spec/bitz.yaml"

_SPEC_KIND_DIRS = ("requirements", "technical", "decisions", "tasks")

HARD_LIMITS: dict[str, int] = {
    "memberCount": 100,
    "specFileCount": 10_000,
    "inputBytes": 256 * 1024 * 1024,
    "statementCount": 100_000,
    "relationEdgeCount": 1_000_000,
    "traceEntryCount": 1_000_000,
    "commandDefinitionCount": 10_000,
    # `verifyBindingCount`は事前検査（catalog全体のsnapshot走査）では計数しない。1回のverify
    # 実行計画のbinding数だけに適用するため`verify.py`が自分で数える（複合workspace仕様 §10）。
    "verifyBindingCount": 10_000,
}

# 早期停止時にどのdimensionを優先して報告するか（§10「複数のdimensionが同時に超過する場合は…」の
# 一般化。Step 5Aの範囲ではverifyBindingCountを計算しないため対象外とする）。
_LIMIT_DIMENSION_ORDER = (
    "specFileCount",
    "inputBytes",
    "statementCount",
    "relationEdgeCount",
    "traceEntryCount",
    "commandDefinitionCount",
)


@dataclass
class MemberRecord:
    id: str
    path: str  # repository root相対（"/"区切り、正規化済み）
    root: str  # 絶対path
    config: dict


@dataclass
class PrecheckResult:
    discovery_failed: bool = False
    ok: bool = False
    root_id: str | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    git_status: str = "blocked"  # doctorのchecks[]用（"passed"／"blocked"）
    catalog_status: str | None = None  # doctorのchecks[]用（Noneならcatalog checkを出力しない）
    members: list[MemberRecord] = field(default_factory=list)
    repo_root: str | None = None


def _diag(code: str, status: str, summary: str, source: dict, evidence: object = None) -> Diagnostic:
    return Diagnostic(code=code, severity="error", resultStatus=status, summary=summary, source=source, evidence=evidence)


def _root_source(root_id: str | None, key: str | None = None) -> dict:
    src: dict = {"kind": "file", "workspaceId": root_id, "path": ROOT_CONFIG_PATH}
    if key:
        src["key"] = key
    return src


def _locate_root(cwd: str, git: gitutil.GitInfo, env: dict[str, str]) -> tuple[str | None, str | None, bool]:
    """複合workspace全体操作の候補root(絶対path)と`.spec/bitz.yaml`を発見する（`複合workspace仕様 §8`）。

    戻り値は``(repo_root, config_path, git_boundary_confirmed)``。候補を発見できなければ
    ``(None, None, False)``（呼び出し側はinvocation error・終了コード4）。
    """

    if git.available and git.executable:
        top = gitutil.show_toplevel(git.executable, cwd, env)
        if top:
            root = os.path.abspath(top)
            cfg = os.path.join(root, ".spec", "bitz.yaml")
            if os.path.isfile(cfg) and not os.path.islink(os.path.join(root, ".spec")):
                return root, cfg, True
            return None, None, False

    # Git不在、またはGit toplevelを解決できない場合のfallback: current directory自身を候補にする
    # （member配下からの広域探索はGitに依存するため提供できないが、cwd自身に候補があれば
    # `SPEC-MULTI-GIT-001`／blockedとして境界確定不能を報告できる。`複合workspace仕様 §10`）。
    root = os.path.abspath(cwd)
    cfg = os.path.join(root, ".spec", "bitz.yaml")
    if os.path.isfile(cfg) and not os.path.islink(os.path.join(root, ".spec")):
        return root, cfg, False
    return None, None, False


def _path_lexically_valid(path: str) -> bool:
    if not isinstance(path, str) or path == "" or path == ".":
        return False
    if os.path.isabs(path) or path.startswith("/"):
        return False
    if "\x00" in path:
        return False
    segments = path.split("/")
    for seg in segments:
        if seg in ("", ".", ".."):
            return False
        if any(ch in seg for ch in "*?[]"):
            return False
    return True


def _is_ancestor(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    return len(a) < len(b) and b[: len(a)] == a


def _validate_multiworkspace_shape(root_config: dict, root_id: str | None) -> tuple[Diagnostic | None, list[tuple[str, str]] | None]:
    mw = root_config.get("multiWorkspace")
    if mw is None:
        return None, []
    if not isinstance(mw, dict):
        return _diag(
            "SPEC-MULTI-CONFIG-001", "failed", messages.MULTI_CONFIG_NOT_MAP,
            _root_source(root_id, "multiWorkspace"),
        ), None

    max_members = mw.get("maxMembers", 20)
    if not isinstance(max_members, int) or isinstance(max_members, bool) or not (1 <= max_members <= 100):
        return _diag(
            "SPEC-MULTI-CONFIG-001", "failed", messages.MULTI_CONFIG_MAX_MEMBERS_RANGE,
            _root_source(root_id, "multiWorkspace.maxMembers"),
        ), None

    members_raw = mw.get("members", [])
    if not isinstance(members_raw, list):
        return _diag(
            "SPEC-MULTI-CONFIG-001", "failed", messages.MULTI_CONFIG_MEMBERS_TYPE,
            _root_source(root_id, "multiWorkspace.members"),
        ), None
    if len(members_raw) == 0:
        return _diag(
            "SPEC-MULTI-CONFIG-001", "failed", messages.MULTI_CONFIG_MEMBERS_REQUIRED,
            _root_source(root_id, "multiWorkspace.members"),
        ), None

    members: list[tuple[str, str]] = []
    for raw in members_raw:
        if (
            not isinstance(raw, dict)
            or not isinstance(raw.get("id"), str)
            or not isinstance(raw.get("path"), str)
        ):
            return _diag(
                "SPEC-MULTI-CONFIG-001", "failed", messages.MULTI_CONFIG_MEMBER_ENTRY_TYPE,
                _root_source(root_id, "multiWorkspace.members"),
            ), None
        members.append((raw["id"], raw["path"]))
    return None, members


def _member_config_check(
    root_id: str, root: str, mid: str, mpath: str, *, check_id_match: bool = True
) -> tuple[Diagnostic | None, dict | None]:
    """member自身の`.spec/bitz.yaml`を検証する（MEMBER stage、910）。``mpath``はlexically有効な前提。

    ``check_id_match``は呼び出し側が``mid``自体の構文を既に不正と判定済みのとき``False``にする
    （catalogのid形式不正はID stage、920が単独のprimaryになれるよう、無意味なmismatch比較を
    しない。priorityどおりMEMBER(910)をID(920)より優先するのは、両者が独立に成立する場合だけに限る）。
    """

    member_root = os.path.join(root, *mpath.split("/"))
    member_cfg = os.path.join(member_root, ".spec", "bitz.yaml")
    if not os.path.isfile(member_cfg) or os.path.islink(os.path.join(member_root, ".spec")):
        return _diag(
            "SPEC-MULTI-MEMBER-001", "failed", messages.MEMBER_CONFIG_MISSING,
            _root_source(root_id, "multiWorkspace.members"),
        ), None

    m_outcome = config_mod.read_config(member_cfg)
    if m_outcome.stop:
        if m_outcome.stop_stage in ("schema-major", "ears-major"):
            code = "SPEC-MULTI-VERSION-001"
            msg = (
                messages.MULTI_VERSION_SCHEMA_MAJOR
                if m_outcome.stop_stage == "schema-major"
                else messages.MULTI_VERSION_EARS_MAJOR
            )
            return _diag(code, "blocked", msg, _root_source(root_id, "multiWorkspace.members")), None
        # 一般的な設定不適合（YAML構文・型・必須field・I/O）はmember自身のDiagnosticをそのまま返す。
        all_diags = m_outcome.diagnostics + m_outcome.warnings
        return (all_diags[0] if all_diags else _diag(
            "SPEC-CONFIG-SCHEMA-001", "error", "member設定が不正です", _root_source(root_id, "multiWorkspace.members")
        )), None

    assert m_outcome.config is not None
    if check_id_match and m_outcome.workspace_id != mid:
        return _diag(
            "SPEC-MULTI-MEMBER-001", "failed", messages.MEMBER_ID_MISMATCH,
            _root_source(root_id, "multiWorkspace.members"),
        ), None
    if m_outcome.config.get("multiWorkspace") is not None:
        return _diag(
            "SPEC-MULTI-MEMBER-001", "failed", messages.MEMBER_NESTED_MULTIWORKSPACE,
            _root_source(root_id, "multiWorkspace.members"),
        ), None
    return None, m_outcome.config


@dataclass
class _LocalMember:
    id: str
    path: str
    parts: tuple[str, ...]
    config: dict


def _evaluate_member_local(
    root: str, root_id: str, mid: str, mpath: str
) -> tuple[Diagnostic | None, _LocalMember | None]:
    """1つのmemberについて、他memberとの比較を伴わないcandidateを集め、最小priorityの1件を選ぶ。

    同じmemberに複数条件が成立しても、返すDiagnosticは1件だけにする
    （`Diagnostic registry` §2「1つのraw原因から同義Diagnosticを複数生成しない」の運用として、
    "1つのmember"を単位に適用する）。
    """

    candidates: list[Diagnostic] = []

    id_valid = isinstance(mid, str) and bool(lex.WORKSPACE_ID_RE.match(mid))
    if not id_valid:
        candidates.append(_diag(
            "SPEC-MULTI-ID-001", "failed", messages.MULTI_ID_INVALID,
            _root_source(root_id, "multiWorkspace.members"),
        ))
    elif mid == root_id:
        candidates.append(_diag(
            "SPEC-MULTI-ID-001", "failed", messages.MULTI_ID_DUPLICATE,
            _root_source(root_id, "multiWorkspace.members"),
        ))

    path_valid = _path_lexically_valid(mpath)
    parts = tuple(mpath.split("/")) if path_valid else ()
    if not path_valid:
        candidates.append(_diag(
            "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_INVALID,
            _root_source(root_id, "multiWorkspace.members"),
        ))

    config: dict | None = None
    if path_valid:
        d, config = _member_config_check(root_id, root, mid, mpath, check_id_match=id_valid)
        if d is not None:
            candidates.append(d)

    if candidates:
        candidates.sort(key=lambda d: _PRIORITY.get(d.code, 0))
        return candidates[0], None

    assert config is not None
    return None, _LocalMember(id=mid, path=mpath, parts=parts, config=config)


def _deep_path_check(
    root: str,
    root_id: str,
    rec: _LocalMember,
    submodule_paths: set[str],
    worktree_paths: set[str],
) -> Diagnostic | None:
    """symlink祖先・submodule・別worktree・別repositoryを検証する（PATH stage、930・Git依存）。"""

    if rec.path in submodule_paths:
        return _diag(
            "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_SUBMODULE,
            _root_source(root_id, "multiWorkspace.members"),
        )
    member_root = os.path.join(root, *rec.parts)
    if os.path.abspath(member_root) in worktree_paths:
        return _diag(
            "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_WORKTREE,
            _root_source(root_id, "multiWorkspace.members"),
        )
    cur = root
    for seg in rec.parts:
        cur = os.path.join(cur, seg)
        if os.path.islink(cur):
            return _diag(
                "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_SYMLINK,
                _root_source(root_id, "multiWorkspace.members"),
            )
    if os.path.isdir(os.path.join(member_root, ".git")):
        return _diag(
            "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_SEPARATE_REPO,
            _root_source(root_id, "multiWorkspace.members"),
        )
    return None


def _validate_catalog(
    root: str,
    root_id: str,
    root_config: dict,
    git: gitutil.GitInfo,
    cwd: str,
    env: dict[str, str],
    extra_config_revs: list[str],
    *,
    skip_limit_dimensions: frozenset[str] = frozenset(),
) -> tuple[list[Diagnostic], list[MemberRecord] | None]:
    """catalog・ID・path・version・未登録設定を検証する（優先順位900〜960。GITは呼び出し側で解決済み）。

    独立したraw原因はそれぞれ1件のDiagnosticを持つ（`Diagnostic registry` §2）。同じmemberに
    複数条件が成立する場合や、2 member間の同一raw原因（重複ID・重複／入れ子path）は1件に絞る。
    catalog自体が構成できない場合（`multiWorkspace`の形状不正）だけ、単独のhard stopとして
    1件のDiagnosticを返す。問題がなければ ``([], member_records)`` を返す。
    """

    shape_diag, members_raw = _validate_multiworkspace_shape(root_config, root_id)
    if shape_diag is not None:
        return [shape_diag], None
    assert members_raw is not None

    # --- PASS A: memberごとの独立検証（ID構文・path lexical・member設定） -----------------
    local_diags: list[Diagnostic] = []
    locals_: list[_LocalMember | None] = []
    for mid, mpath in members_raw:
        d, rec = _evaluate_member_local(root, root_id, mid, mpath)
        if d is not None:
            local_diags.append(d)
        locals_.append(rec)

    clean_indices = [i for i, rec in enumerate(locals_) if rec is not None]

    # --- PASS B: 2 member間のpairwise raw原因（重複ID・重複／入れ子path）を1件ずつに絞る -------
    consumed: set[int] = set()
    pairwise_diags: list[Diagnostic] = []
    for pos_i in range(len(clean_indices)):
        i = clean_indices[pos_i]
        if i in consumed:
            continue
        a = locals_[i]
        assert a is not None
        for pos_j in range(pos_i + 1, len(clean_indices)):
            j = clean_indices[pos_j]
            if j in consumed:
                continue
            b = locals_[j]
            assert b is not None
            if a.id == b.id:
                pairwise_diags.append(_diag(
                    "SPEC-MULTI-ID-001", "failed", messages.MULTI_ID_DUPLICATE,
                    _root_source(root_id, "multiWorkspace.members"),
                ))
                consumed.add(i)
                consumed.add(j)
                break
            if a.parts == b.parts:
                pairwise_diags.append(_diag(
                    "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_DUPLICATE,
                    _root_source(root_id, "multiWorkspace.members"),
                ))
                consumed.add(i)
                consumed.add(j)
                break
            if _is_ancestor(a.parts, b.parts) or _is_ancestor(b.parts, a.parts):
                pairwise_diags.append(_diag(
                    "SPEC-MULTI-PATH-001", "failed", messages.MULTI_PATH_NESTED,
                    _root_source(root_id, "multiWorkspace.members"),
                ))
                consumed.add(i)
                consumed.add(j)
                break

    # --- PASS C: 残ったmemberだけGit依存の深い判定（symlink／submodule／worktree／別repository） ---
    deep_diags: list[Diagnostic] = []
    members: list[MemberRecord] = []
    remaining = [i for i in clean_indices if i not in consumed]
    if git.available and git.executable:
        submodule_paths = gitutil.list_submodule_paths(git.executable, cwd, env)
        worktree_paths = gitutil.list_worktree_paths(git.executable, cwd, env)
        for i in remaining:
            rec = locals_[i]
            assert rec is not None
            d = _deep_path_check(root, root_id, rec, submodule_paths, worktree_paths)
            if d is not None:
                deep_diags.append(d)
            else:
                members.append(MemberRecord(
                    id=rec.id, path=rec.path, root=os.path.join(root, *rec.parts), config=rec.config
                ))
    else:
        for i in remaining:
            rec = locals_[i]
            assert rec is not None
            members.append(MemberRecord(
                id=rec.id, path=rec.path, root=os.path.join(root, *rec.parts), config=rec.config
            ))

    all_diags = local_diags + pairwise_diags + deep_diags
    if all_diags:
        return all_diags, None

    # --- UNREGISTERED stage（960） --------------------------------------------------
    # 各snapshotは自身のcatalogとだけ比較する（複合workspace仕様 §8「各snapshot自身のroot設定が
    # multiWorkspaceを宣言する場合だけ、そのsnapshot自身のcatalogとの差分を検査する」）。base
    # snapshotがcurrentと異なるmember構成（例: member pathのrename）を持つ場合、base snapshotの
    # 既知設定はbase snapshot自身のcatalogへ照合し、current側の既知設定はcurrent catalogへ照合する
    # （どちらか一方の集合だけで比較すると、IDを保ったmember移動を誤ってunregisteredにする）。
    if git.available and git.executable:
        catalog_paths = {".spec/bitz.yaml"} | {f"{rec.path}/.spec/bitz.yaml" for rec in members}
        extra_set: set[str] = set()
        for rev in extra_config_revs:
            rev_map = base_workspace_map(git, cwd, env, rev, root)
            if not rev_map:
                # このrevはmultiWorkspaceを宣言していない（単一workspaceから複合workspace化する前の
                # snapshot）。repository全体の不存在保証を遡及適用しない（複合workspace仕様 §8）。
                continue
            rev_catalog_paths = {
                ".spec/bitz.yaml" if p == "." else f"{p}/.spec/bitz.yaml" for p in rev_map.values()
            }
            rev_known = set(gitutil.list_tree_config_paths(git.executable, cwd, env, rev))
            extra_set |= rev_known - rev_catalog_paths
        current_known = set(gitutil.list_working_config_paths(git.executable, cwd, env))
        extra_set |= current_known - catalog_paths
        extra = sorted(extra_set)
        if extra:
            return [
                _diag(
                    "SPEC-MULTI-UNREGISTERED-001", "blocked", messages.MULTI_UNREGISTERED,
                    {"kind": "file", "workspaceId": None, "path": p},
                )
                for p in extra
            ], None

    # --- LIMIT stage（970） -------------------------------------------------------
    # 上限超過は複合workspace全体を停止する単一のraw原因であり、`複合workspace仕様 §10`のとおり
    # 最初に検出したdimensionで早期停止する（複数member個別の独立raw原因とは扱いが異なる）。
    limit_diag = _check_resource_limits(root, root_id, root_config, members, skip_dimensions=skip_limit_dimensions)
    if limit_diag is not None:
        return [limit_diag], None

    return [], members


def _iter_spec_md_files(workspace_root: str):
    spec_dir = os.path.join(workspace_root, ".spec")
    for kind_dir in _SPEC_KIND_DIRS:
        base = os.path.join(spec_dir, kind_dir)
        if os.path.islink(base) or not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if not os.path.islink(os.path.join(dirpath, d)))
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                if os.path.islink(full):
                    continue
                if name.endswith(".md"):
                    yield full


def _extract_frontmatter_dict(text: str) -> dict:
    if not (text.startswith("---\n") or text == "---"):
        return {}
    lines = text.split("\n")
    if lines[0] != "---":
        return {}
    for i in range(1, len(lines)):
        if lines[i] == "---":
            raw = "\n".join(lines[1:i])
            try:
                value = parse_yaml_subset(raw)
            except (YamlSyntaxError, YamlForbiddenError):
                return {}
            return value if isinstance(value, dict) else {}
    return {}


def _scan_document_counts(text: str) -> tuple[int, int, int]:
    """``(statementCount, relationEdgeCount, traceEntryCount)``をこの1文書分だけ返す。

    本文全体を保持せず、この関数の呼び出しが終われば``text``は解放できる（複合workspace仕様
    §10.1「全file本文を索引として同時保持しない」）。
    """

    candidates = scan_candidates(text)
    fm = _extract_frontmatter_dict(text)

    rel_count = 0
    relations = fm.get("relations")
    if isinstance(relations, dict):
        for v in relations.values():
            if isinstance(v, list):
                rel_count += len(v)

    trace_count = 0
    implements = fm.get("implements")
    if isinstance(implements, list):
        trace_count += len(implements)
    tests = fm.get("tests")
    if isinstance(tests, list):
        for t in tests:
            trace_count += 1
            if isinstance(t, dict) and isinstance(t.get("covers"), list):
                trace_count += len(t["covers"])
    changes = fm.get("changes")
    if isinstance(changes, list):
        trace_count += len(changes)

    return len(candidates), rel_count, trace_count


def _first_exceeded(totals: dict[str, int], skip_dimensions: frozenset[str] = frozenset()) -> str | None:
    for dim in _LIMIT_DIMENSION_ORDER:
        if dim in skip_dimensions:
            continue
        if totals[dim] > HARD_LIMITS[dim]:
            return dim
    return None


def _limit_diag(root_id: str, dimension: str, limit: int, observed: int) -> Diagnostic:
    return _diag(
        "SPEC-MULTI-LIMIT-001", "blocked", messages.multi_limit_exceeded(dimension, limit),
        _root_source(root_id),
        evidence={"dimension": dimension, "limit": limit, "observedAtLeast": observed},
    )


def _check_resource_limits(
    root: str,
    root_id: str,
    root_config: dict,
    members: list[MemberRecord],
    *,
    skip_dimensions: frozenset[str] = frozenset(),
) -> Diagnostic | None:
    # memberCountは`multiWorkspace.maxMembers`（既定20、範囲1〜100）の実効上限で判定し、Core hard limit
    # 100を超えない（複合workspace仕様 §2・§10）。値域は_validate_catalogで検査済み。
    member_count = len(members)
    max_members = (root_config.get("multiWorkspace") or {}).get("maxMembers", 20)
    member_limit = min(max_members, HARD_LIMITS["memberCount"])
    if member_count > member_limit:
        return _limit_diag(root_id, "memberCount", member_limit, member_count)

    totals = {k: 0 for k in _LIMIT_DIMENSION_ORDER}

    workspaces = [(root, root_config)] + [(rec.root, rec.config) for rec in members]
    for wroot, wconfig in workspaces:
        cfg_path = os.path.join(wroot, ".spec", "bitz.yaml")
        try:
            totals["inputBytes"] += os.path.getsize(cfg_path)
        except OSError:
            pass
        commands = ((wconfig.get("verify") or {}) if isinstance(wconfig.get("verify"), dict) else {}).get("commands")
        if isinstance(commands, dict):
            totals["commandDefinitionCount"] += len(commands)

        dim = _first_exceeded(totals, skip_dimensions)
        if dim:
            return _limit_diag(root_id, dim, HARD_LIMITS[dim], totals[dim])

        for md_path in _iter_spec_md_files(wroot):
            try:
                size = os.path.getsize(md_path)
            except OSError:
                continue
            totals["specFileCount"] += 1
            totals["inputBytes"] += size
            dim = _first_exceeded(totals, skip_dimensions)
            if dim:
                return _limit_diag(root_id, dim, HARD_LIMITS[dim], totals[dim])

            try:
                with open(md_path, "rb") as f:
                    raw = f.read()
            except OSError:
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            del raw
            stmt_count, rel_count, trace_count = _scan_document_counts(text)
            del text
            totals["statementCount"] += stmt_count
            totals["relationEdgeCount"] += rel_count
            totals["traceEntryCount"] += trace_count
            dim = _first_exceeded(totals, skip_dimensions)
            if dim:
                return _limit_diag(root_id, dim, HARD_LIMITS[dim], totals[dim])

    dim = _first_exceeded(totals, skip_dimensions)
    if dim:
        return _limit_diag(root_id, dim, HARD_LIMITS[dim], totals[dim])
    return None


def ordered_workspaces(pre: "PrecheckResult") -> list[tuple[str, str, str]]:
    """``(workspace_id, root_abs, repository_root相対path)``をroot先頭、以降ID辞書順で返す(§8)。"""

    out: list[tuple[str, str, str]] = [(pre.root_id, pre.repo_root, ".")]
    for m in sorted(pre.members, key=lambda r: r.id):
        out.append((m.id, m.root, m.path))
    return out


def base_workspace_map(
    git: gitutil.GitInfo,
    cwd: str,
    env: dict[str, str],
    base_rev: str | None,
    repo_root: str,
    *,
    current_root_id: str | None = None,
) -> dict[str, str]:
    """``base_rev``時点のroot／member catalogを``{workspace_id: repository_root相対path}``で返す。

    root workspaceのIDは基準版のFrontmatter``workspace.id``をそのまま使う。基準版のroot設定が
    ``multiWorkspace``を宣言していない場合は、``current_root_id``が与えられ、かつ基準版が
    ``workspace.id``を省略しているときに限り、単一workspaceから初めて複合workspace化するGit比較の
    写像（複合workspace仕様 §4.1後段）として基準版の実効ID`root`を``current_root_id``へ
    一方向写像した``{current_root_id: "."}``を返す（状態遷移・削除検出・承認済みREQ保護の
    base/current対応にだけ使う）。``current_root_id``を渡さない呼び出し（全体事前検査のGit既知設定
    比較。複合workspace仕様 §8「初回複合workspace化前の単一workspace snapshotへrepository全体の
    不存在保証を遡及適用しない」）では、この写像を行わず引き続き空dictを返す。
    """

    if base_rev is None or not git.available or git.executable is None:
        return {}
    raw = gitutil.show_base_file(git.executable, cwd, env, base_rev, repo_root, ROOT_CONFIG_PATH)
    if raw is None:
        return {}
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {}
    try:
        value = parse_yaml_subset(text)
    except (YamlSyntaxError, YamlForbiddenError):
        return {}
    if not isinstance(value, dict):
        return {}
    mw = value.get("multiWorkspace")
    if not isinstance(mw, dict):
        if current_root_id is not None:
            ws_block = value.get("workspace")
            has_explicit_id = isinstance(ws_block, dict) and isinstance(ws_block.get("id"), str)
            if not has_explicit_id:
                return {current_root_id: "."}
        return {}
    members_raw = mw.get("members")
    if not isinstance(members_raw, list):
        return {}
    ws_block = value.get("workspace")
    root_id = ws_block.get("id") if isinstance(ws_block, dict) and isinstance(ws_block.get("id"), str) else "root"
    result: dict[str, str] = {root_id: "."}
    for raw_member in members_raw:
        if (
            isinstance(raw_member, dict)
            and isinstance(raw_member.get("id"), str)
            and isinstance(raw_member.get("path"), str)
        ):
            result[raw_member["id"]] = raw_member["path"]
    return result


def precheck(
    cwd: str,
    git: gitutil.GitInfo,
    env: dict[str, str],
    *,
    extra_config_revs: list[str] | None = None,
    skip_limit_dimensions: frozenset[str] = frozenset(),
) -> PrecheckResult:
    """`--all-workspaces`の全体事前検査（`複合workspace仕様 §8`）。

    ``extra_config_revs``は現在snapshotに加えてGit既知設定を比較するrevisionの一覧
    （checkの`--base`、doctorのHEADなど。§8「checkは指定base snapshot、doctorはHEAD snapshotも
    対象にする」）。

    ``skip_limit_dimensions``は全体事前検査のresource上限判定から除外するdimension名の集合
    （空集合が既定＝従来どおり全dimensionを判定する）。`verifyBindingCount`は
    `commandDefinitionCount`の部分集合であり両方が同時に超過し得るが、複数dimensionが同時に
    超過する場合はverify実行計画のdimensionを優先して報告する（複合workspace仕様 §10）。
    `verify --all-workspaces`は自分のbinding計画からverifyBindingCountを直接数えるため、
    ここでは`commandDefinitionCount`を渡して一般事前検査の早期停止を避け、verify側の判定を
    優先させる。check／doctorは空集合のまま呼び出し、この判定順を変えない。
    """

    root, cfg_path, git_confirmed = _locate_root(cwd, git, env)
    if root is None:
        return PrecheckResult(discovery_failed=True)

    outcome = config_mod.read_config(cfg_path)
    if outcome.stop:
        diags = outcome.diagnostics + outcome.warnings
        return PrecheckResult(
            ok=False,
            root_id=outcome.workspace_id,
            diagnostics=diags,
            git_status="passed" if git_confirmed else "blocked",
            catalog_status=None,
            repo_root=root,
        )

    root_id = outcome.workspace_id
    assert outcome.config is not None

    if not git_confirmed:
        diag = _diag(
            "SPEC-MULTI-GIT-001", "blocked", messages.MULTI_GIT_BOUNDARY_UNKNOWN,
            {"kind": "environment", "component": "git"},
        )
        return PrecheckResult(
            ok=False, root_id=root_id, diagnostics=[diag], git_status="blocked", catalog_status=None, repo_root=root
        )

    revs = list(extra_config_revs or [])
    catalog_diags, members = _validate_catalog(
        root, root_id, outcome.config, git, cwd, env, revs, skip_limit_dimensions=skip_limit_dimensions
    )
    if catalog_diags:
        status = worst_status([d.resultStatus for d in catalog_diags])
        return PrecheckResult(
            ok=False,
            root_id=root_id,
            diagnostics=catalog_diags,
            git_status="passed",
            catalog_status=status,
            repo_root=root,
        )

    assert members is not None
    return PrecheckResult(
        ok=True,
        root_id=root_id,
        diagnostics=[],
        git_status="passed",
        catalog_status="passed",
        members=members,
        repo_root=root,
    )
