"""`bitz check` 操作（`03_操作仕様/02_check.md`）。

Step 2 Phase Bで`scope: full`（catalog全体の軽量Frontmatter索引・EARS-AI・style検査）、
Step 2 Phase Cでrelation・path・coverage検査と明示対象（`scope: selected`）・明示TASK境界検査を
実装した。Step 3 Phase 3Aは残りを実装する。

- `scope: changed`（引数なしのGit変更起点、`check.md §6`）
- 状態遷移と管理済みSPEC削除検出（`02_文書・Frontmatter・状態仕様.md §6・§9`）
- 承認済みREQ保護（同 §8）
- 影響候補（`check.md §8`）
- Git不在時の全体check縮退（`SPEC-GIT-DEGRADED-001`）
- 明示`--report`の保存（`00_共通契約/02_安全な入出力・互換性.md §8`）

状態遷移・管理済みSPEC削除・承認済みREQ保護・影響候補は`basecompare.py`、report保存は
`reportio.py`に切り出す。
"""

from __future__ import annotations

import os
import time

from . import basecompare
from . import config as config_mod
from . import document as document_mod
from . import gitutil
from . import messages
from . import multirelate
from . import multiws
from . import relations as relations_mod
from . import reportio
from . import targetexpand
from .cliargs import ParsedArgs
from .config import Diagnostic
from .document import DocEntry
from .errors import CliArgError
from .resultmodel import EXIT_CODE_BY_STATUS, sort_diagnostics, status_from_diagnostics, worst_status
from .workspace import WorkspaceLocation, locate_workspace


def _resolve_target(
    target: str,
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
    path_index: dict[str, str],
    *,
    active_ws_id: str | None = None,
) -> str | None:
    """構文検査済みの明示対象文字列を所有文書IDへ正規化する（`check.md §2`）。

    文書ID、statement ID、SPEC Markdown pathのいずれかで解決を試みる。catalogに存在しなければ
    ``None``を返す（呼び出し側が`CTX-ROOT-MISSING-001`を返す）。

    ``active_ws_id``を渡すと、``target``がactive workspace自身を指す修飾ID
    （``"<active_ws_id>::localId"``）の場合だけ修飾子を外し、active workspace自身の非修飾索引
    （``id_index``）で解決する（複合workspace仕様 §3「修飾IDを起点にする場合は、その所有workspaceを
    選択する」。選択後はactive workspace自身の文書IDとして通常どおり解決する）。別workspaceだけに
    ある修飾ID（例: ``api::REQ-009``でactiveがapiでも該当IDが無い場合）は、修飾子を外した後の
    ローカルIDで``id_index``を引いても見つからず、解決失敗として扱う（`CTX-ROOT-MISSING-001`）。
    """

    lookup = target
    if active_ws_id is not None:
        q = multirelate.parse_qualified(target)
        if q is not None and q[0] == active_ws_id:
            lookup = q[1]

    if lookup in id_index:
        return lookup
    stmt = statement_index.get(lookup)
    if stmt is not None:
        return stmt["documentId"]
    return path_index.get(lookup)


def _task_own_path_allows(path: str, allowed: list) -> bool:
    for a in allowed:
        if not isinstance(a, str):
            continue
        if a.endswith("/"):
            if path.startswith(a):
                return True
        else:
            if path == a:
                return True
    return False


def _task_change_ownership_diag(
    git: gitutil.GitInfo,
    cwd: str,
    env: dict[str, str],
    base_commit: str | None,
    workspace_id: str,
    workspace_root: str,
    real_roots: dict[str, str],
    path: str,
    status: str,
) -> Diagnostic | None:
    """TASK変更pathの所有境界をbase／current双方のsymlinkで判定する（複合workspace仕様 §5.2）。

    ``status``が``"A"``（追加）ならcurrentだけ、``"D"``（削除）ならbaseだけを検査する。それ以外
    （変更・rename）はbase／current双方を検査する。symlinkでなければ所有境界違反は成立しない
    （宣言済みpathは既にworkspace root相対で構成されているため）。
    """

    own_real = real_roots.get(workspace_id)
    if own_real is None:
        return None

    base_violation = False
    if status != "A" and base_commit is not None and git.available and git.executable:
        mode = gitutil.base_tree_entry_mode(git.executable, cwd, env, base_commit, workspace_root, path)
        if mode == "120000":
            raw = gitutil.show_base_file(git.executable, cwd, env, base_commit, workspace_root, path)
            target_text: str | None = None
            if raw is not None:
                try:
                    target_text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    target_text = None
            if target_text:
                base_dir = os.path.dirname(os.path.join(workspace_root, path))
                resolved = os.path.normpath(os.path.join(base_dir, target_text))
                if os.path.exists(resolved):
                    real = os.path.realpath(resolved)
                    if not (real == own_real or real.startswith(own_real + os.sep)):
                        base_violation = True

    current_violation = False
    if status != "D":
        abs_current = os.path.join(workspace_root, path)
        if os.path.islink(abs_current):
            real = os.path.realpath(abs_current)
            if os.path.exists(real) and not (real == own_real or real.startswith(own_real + os.sep)):
                current_violation = True

    if base_violation:
        return Diagnostic(
            code="SPEC-MULTI-OWNERSHIP-001", severity="error", resultStatus="failed",
            summary=messages.multi_ownership_symlink_base(path, workspace_id),
            source={"kind": "file", "workspaceId": workspace_id, "path": path},
        )
    if current_violation:
        return Diagnostic(
            code="SPEC-MULTI-OWNERSHIP-001", severity="error", resultStatus="failed",
            summary=messages.multi_ownership_symlink_current(path, workspace_id),
            source={"kind": "file", "workspaceId": workspace_id, "path": path},
        )
    return None


def _task_boundary_diagnostics(
    entry: DocEntry,
    git: gitutil.GitInfo,
    cwd: str,
    env: dict[str, str],
    base_commit: str | None,
    workspace_id: str,
    workspace_root: str,
    *,
    real_roots: dict[str, str] | None = None,
) -> list[Diagnostic]:
    """明示TASK境界検査（`check.md §7`）。TASK ID/pathを明示した場合だけ呼び出す。

    ``real_roots``（複合workspace内での明示TASK check）を渡すと、所有境界不適合
    （`SPEC-MULTI-OWNERSHIP-001`）をTASK境界外変更より先に判定し、同じpathへ両方のDiagnosticを
    重複させない（複合workspace仕様 §5.2）。複合workspace内では、summaryに埋め込むTASK IDを
    複合workspace正規形式（`ws::local`）にする（複合workspace仕様 §4）。
    """

    display_doc_id = f"{workspace_id}::{entry.doc_id}" if real_roots is not None else entry.doc_id

    if not git.available or git.executable is None or base_commit is None:
        return [
            Diagnostic(
                code="SPEC-TASK-BOUNDARY-002",
                severity="error",
                resultStatus="blocked",
                summary=messages.task_boundary_no_git(display_doc_id),
                source={"kind": "environment", "component": "git", "identifier": "git"},
            )
        ]

    changed = gitutil.collect_changed_paths(git.executable, cwd, env, base_commit, workspace_root)
    allowed = (entry.frontmatter or {}).get("changes") or []

    diags: list[Diagnostic] = []
    reported: set[str] = set()
    for c in changed:
        # renameはsourceとdestinationの2 pathを検査する（安全な入出力 §6、check.md §7）。
        candidates = [c.old_path, c.path] if c.status == "R" else [c.path]
        for p in candidates:
            if p is None or p == entry.path or p.startswith(".spec/reports/") or p in reported:
                continue
            if real_roots is not None:
                ownership_diag = _task_change_ownership_diag(
                    git, cwd, env, base_commit, workspace_id, workspace_root, real_roots, p, c.status
                )
                if ownership_diag is not None:
                    reported.add(p)
                    diags.append(ownership_diag)
                    continue
            if not _task_own_path_allows(p, allowed):
                reported.add(p)
                diags.append(
                    Diagnostic(
                        code="SPEC-TASK-BOUNDARY-001",
                        severity="error",
                        resultStatus="failed",
                        summary=messages.task_boundary_violation(p, display_doc_id),
                        source={"kind": "file", "workspaceId": workspace_id, "path": p},
                    )
                )
    return diags


def _direct_reverse_references(
    context_ids: set[str],
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
    *,
    source_index: dict[str, DocEntry] | None = None,
) -> set[str]:
    """``context_ids``内のいずれかを直接参照する文書ID集合を返す（`check.md §3`「直接逆参照」）。

    参照は`relations`の全relation（`requires`/`refines`/`addresses`/`supersedes`/`related`）を
    対象とする。target解決は関係の型が妥当かを問わない（存在するIDへの直接参照であれば、明示対象の
    完全検査対象へ含める。型不適合そのものは`relations.check_relations`が別途Diagnosticにする）。

    ``source_index``を渡すと、逆参照の走査元（＝完全検査対象へ加える候補）をその索引だけへ絞る
    （複合workspace内のworkspace単独check。`複合workspace仕様 §7`「無関係memberを完全検査しない」。
    target解決自体は``id_index``全体（修飾aliasを含む）から行い、他workspaceの文書が偶然同じ
    targetを参照していても、active workspace以外の文書を完全検査対象へ引き込まない）。
    """

    result: set[str] = set()
    for doc_id, entry in (source_index if source_index is not None else id_index).items():
        if doc_id in context_ids:
            continue
        relations = (entry.frontmatter or {}).get("relations") or {}
        for relation_name in ("requires", "refines", "addresses", "supersedes", "related"):
            hit = False
            for ref in relations.get(relation_name) or []:
                _target_entry, target_doc_id = relations_mod.resolve_ref(ref, id_index, statement_index)
                if target_doc_id is not None and target_doc_id in context_ids:
                    result.add(doc_id)
                    hit = True
                    break
            if hit:
                break
    return result


def _resolve_selected_roots(
    parsed: ParsedArgs,
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
    *,
    active_ws_id: str | None = None,
    local_entries: list[DocEntry] | None = None,
) -> tuple[list[Diagnostic], set[str], list[DocEntry]]:
    """明示対象を解決し、`TargetExpansion(root, interpret)`の和集合を求める。

    戻り値は``(root解決Diagnostic, contextDocuments和集合, TASK root一覧)``。``local_entries``を
    渡すと、明示path対象の解決をactive workspace自身の文書だけへ限定する（複合workspace仕様 §7
    「明示pathは選択workspace root相対で解決する」。省略時は``id_index``全体から作る＝単一workspace
    時の既存挙動）。
    """

    path_source = local_entries if local_entries is not None else list(id_index.values())
    path_index = {e.path: e.doc_id for e in path_source if e.doc_id is not None}

    diags: list[Diagnostic] = []
    context_ids: set[str] = set()
    task_roots: list[DocEntry] = []

    for target in parsed.positionals:
        root_id = _resolve_target(target, id_index, statement_index, path_index, active_ws_id=active_ws_id)
        if root_id is None:
            diags.append(
                Diagnostic(
                    code="CTX-ROOT-MISSING-001",
                    severity="error",
                    resultStatus="failed",
                    summary=messages.root_missing_explicit(target),
                    source={"kind": "invocation", "argument": target},
                )
            )
            continue
        expansion = targetexpand.target_expansion(root_id, "interpret", id_index, statement_index)
        if expansion is not None:
            context_ids.update(expansion.context_documents)
        entry = id_index[root_id]
        if entry.kind == "TASK":
            task_roots.append(entry)

    return diags, context_ids, task_roots


_ALWAYS_KEEP_CATALOG_CODES = {"SPEC-WORKSPACE-UNKNOWN-001", "SPEC-ID-DUPLICATE-001"}


def _filter_catalog_diagnostics_for_scope(
    diags: list[Diagnostic], entries: list[DocEntry], checked_paths: set[str]
) -> list[Diagnostic]:
    """`scope: selected`向けに、catalog全体のDiagnosticを完全検査対象文書だけへ絞る（`check.md §3`）。

    workspace単位のDiagnostic（設定・`.spec/`内未知entry・SPEC file数上限）と、ID重複のように
    軽量索引の構築自体に関わるDiagnosticは、対象文書に関わらず常に残す（
    :data:`_ALWAYS_KEEP_CATALOG_CODES`）。それ以外の`source.kind == "file"`かつpathがcatalog内の
    いずれかの文書に一致するDiagnostic（Frontmatter・EARS-AI・style等、文書ごとの完全検査結果）は、
    そのpathが``checked_paths``（完全検査対象文書のpath集合）に含まれる場合だけ残す。
    catalog内のどの文書pathにも一致しないfile Diagnostic（`.spec`のSPEC数上限、
    `.spec/<kind>/`直下の未知entryなど、文書として解析されなかったもの）は常に残す。
    """

    doc_paths_all = {e.path for e in entries}
    out: list[Diagnostic] = []
    for d in diags:
        if d.code in _ALWAYS_KEEP_CATALOG_CODES:
            out.append(d)
            continue
        src = d.source
        if src.get("kind") != "file":
            out.append(d)
            continue
        path = src.get("path")
        if path not in doc_paths_all:
            out.append(d)
            continue
        if path in checked_paths:
            out.append(d)
    return out


def _base_root_for_git(repo_root: str, base_path: str) -> str:
    """base workspace mapの``path``（repository root相対、``.``を含む）から絶対pathを組み立てる。

    ``base_path``のdirectoryが現在の作業treeに存在しなくてもよい（rename／削除後でもGit tree
    参照は経路の文字列演算だけで完結する。`gitutil._repo_root_relative_offset`参照）。
    """

    if base_path == ".":
        return repo_root
    return os.path.join(repo_root, *base_path.split("/"))


def _member_check_diagnostics(
    entries: list[DocEntry],
    ws_id: str,
    ws_root_abs: str,
    local_id_indices: dict[str, dict[str, DocEntry]],
    local_stmt_indices: dict[str, dict[str, dict]],
    known_ws_ids: set[str],
    real_roots: dict[str, str],
) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    for entry in relations_mod.valid_entries(entries):
        diags.extend(
            multirelate.field_diagnostics(entry, ws_id, local_id_indices, local_stmt_indices, known_ws_ids)
        )
    diags.extend(multirelate.path_diagnostics(entries, ws_id, ws_root_abs, real_roots))
    diags.extend(
        multirelate.coverage_diagnostics(entries, ws_id, local_id_indices, local_stmt_indices, known_ws_ids)
    )
    return diags


def _member_base_diagnostics(
    git: gitutil.GitInfo,
    cwd: str,
    env: dict[str, str],
    base_commit: str,
    repo_root: str,
    base_path: str,
    ws_id: str,
    ws_root_abs: str,
    entries: list[DocEntry],
    current_by_id: dict[str, DocEntry],
) -> list[Diagnostic]:
    base_root = _base_root_for_git(repo_root, base_path)
    base_by_id = basecompare.load_base_catalog(git, cwd, env, base_commit, base_root, ws_id)
    current_ids_present = {e.doc_id for e in entries if e.doc_id is not None}
    diags: list[Diagnostic] = []
    diags.extend(
        basecompare.state_transition_diagnostics(
            base_by_id, current_by_id, ws_id, current_ids_present=current_ids_present
        )
    )
    diags.extend(basecompare.approved_protection_diagnostics(base_by_id, current_by_id, ws_id))
    current_by_path = {e.path: e for e in relations_mod.valid_entries(entries)}
    base_by_path = {e.path: e for e in base_by_id.values()}
    changed_paths_ws: list[gitutil.ChangedPath] = []
    if git.available and git.executable:
        changed_paths_ws = gitutil.collect_changed_paths(git.executable, cwd, env, base_commit, ws_root_abs)
    changed_doc_ids = basecompare.changed_spec_document_ids(changed_paths_ws, current_by_path, base_by_path)
    diags.extend(basecompare.impact_candidate_diagnostics(changed_doc_ids, current_by_id, ws_id))
    return diags


def _run_all_workspaces_members(
    parsed: ParsedArgs,
    cwd: str,
    env: dict[str, str],
    git: gitutil.GitInfo,
    pre: multiws.PrecheckResult,
    revision: dict | None,
    resolved_base: str | None,
    started: int,
) -> tuple[dict, int]:
    """事前検査を通過した`--all-workspaces`のmember処理（`複合workspace仕様 §6・§8・§9`）。"""

    workspaces = multiws.ordered_workspaces(pre)
    known_ws_ids = {wid for wid, _, _ in workspaces}
    real_roots = {wid: os.path.realpath(root) for wid, root, _ in workspaces}

    per_ws_entries: dict[str, list[DocEntry]] = {}
    per_ws_catalog_diags: dict[str, list[Diagnostic]] = {}
    per_ws_stmt_count: dict[str, int] = {}
    local_id_indices: dict[str, dict[str, DocEntry]] = {}
    local_stmt_indices: dict[str, dict[str, dict]] = {}

    for wid, root, _relpath in workspaces:
        catalog = document_mod.build_catalog(root, wid)
        for e in catalog.entries:
            e.body = None
        per_ws_entries[wid] = catalog.entries
        # `SPEC-FILE-NAME-001`は`--all-workspaces`member結果ではsourceに`key`を持たない
        # （fixture MULTI-011。file名不一致はFrontmatterの特定fieldではなくfile全体の性質のため、
        # 複合workspace全体結果ではkeyを省く。単一workspace`scope: full`（SINGLE-014）は既存どおり
        # `key: "id"`を保つ。document.pyの生成規則は変えず、ここで複合workspace結果だけ調整する）。
        for d in catalog.diagnostics:
            if d.code == "SPEC-FILE-NAME-001" and "key" in d.source:
                d.source = {k: v for k, v in d.source.items() if k != "key"}
        per_ws_catalog_diags[wid] = catalog.diagnostics
        per_ws_stmt_count[wid] = catalog.checked_statement_count
        local_id_indices[wid] = relations_mod.build_id_index(catalog.entries)
        local_stmt_indices[wid] = relations_mod.build_statement_index(catalog.entries)

    # 横断edge（修飾IDで解決したedge）を含めた循環検査は複合workspace全体を1つのgraphとして
    # 1回だけ計算し、循環に参加するedgeの宣言元workspaceへ結果を配る（関係・トレースモデル §4）。
    cycle_diags_by_ws: dict[str, list[Diagnostic]] = {wid: [] for wid, _root, _rel in workspaces}
    for d in multirelate.global_cycle_diagnostics(per_ws_entries):
        cycle_diags_by_ws.setdefault(d.source.get("workspaceId"), []).append(d)

    base_map: dict[str, str] = {}
    if resolved_base is not None:
        base_map = multiws.base_workspace_map(
            git, cwd, env, resolved_base, pre.repo_root, current_root_id=pre.root_id
        )
    current_map = {wid: relpath for wid, _root, relpath in workspaces}

    top_level_diags: list[Diagnostic] = []
    for deleted_id in sorted(set(base_map) - set(current_map)):
        base_root = _base_root_for_git(pre.repo_root, base_map[deleted_id])
        base_by_id = basecompare.load_base_catalog(git, cwd, env, resolved_base, base_root, deleted_id)
        top_level_diags.extend(
            basecompare.state_transition_diagnostics(base_by_id, {}, deleted_id, current_ids_present=set())
        )

    ws_results: list[dict] = []
    for wid, root, relpath in workspaces:
        entries = per_ws_entries[wid]
        diags: list[Diagnostic] = list(per_ws_catalog_diags[wid])
        diags.extend(
            _member_check_diagnostics(
                entries, wid, root, local_id_indices, local_stmt_indices, known_ws_ids, real_roots
            )
        )
        diags.extend(cycle_diags_by_ws.get(wid, []))
        if resolved_base is not None and wid in base_map:
            diags.extend(
                _member_base_diagnostics(
                    git, cwd, env, resolved_base, pre.repo_root, base_map[wid], wid, root, entries,
                    local_id_indices[wid],
                )
            )

        diag_dicts = sort_diagnostics([d.to_dict() for d in diags])
        ws_status = status_from_diagnostics(diag_dicts)
        ws_results.append(
            {
                "id": wid,
                "path": relpath,
                "status": ws_status,
                # 単一workspaceと同じく、skip-document（Frontmatter・file名・EARS構文のhard、ID重複）の
                # 文書は数えない（check仕様 §9「全SPECを完全検査した文書数」、SINGLE-014・MULTI-011）。
                "checkedDocumentCount": sum(
                    1 for e in entries if e.counted and e.hard is None and not e.duplicate
                ),
                "checkedStatementCount": per_ws_stmt_count[wid],
                "durationMs": 0,
                "diagnostics": diag_dicts,
            }
        )

    top_level_dicts = sort_diagnostics([d.to_dict() for d in top_level_diags])
    overall_status = worst_status([w["status"] for w in ws_results] + [status_from_diagnostics(top_level_dicts)])

    result: dict = {
        "schemaVersion": "1.0",
        "operation": "check",
        "status": overall_status,
        "scope": "all-workspaces",
        "multiWorkspace": {"id": pre.root_id, "path": "."},
        "workspaces": ws_results,
        "revision": revision,
        "durationMs": max(0, time.monotonic_ns() // 1_000_000 - started),
        "diagnostics": top_level_dicts,
    }

    if "--report" in parsed.flags:
        failure = reportio.write_report(pre.repo_root, pre.root_id, "check", result)
        if failure is not None:
            diags_top = list(result["diagnostics"])
            diags_top.append(failure.to_dict())
            result["diagnostics"] = diags_top
            overall_status = worst_status([w["status"] for w in ws_results] + [status_from_diagnostics(diags_top)])
            result["status"] = overall_status

    return result, EXIT_CODE_BY_STATUS[overall_status]


def _run_all_workspaces(parsed: ParsedArgs, cwd: str, env: dict[str, str]) -> tuple[dict, int]:
    """`check --all-workspaces`（`複合workspace仕様 §8`）。"""

    started = time.monotonic_ns() // 1_000_000
    git = gitutil.detect_git(cwd, env)
    base_arg = parsed.single.get("--base", "HEAD")

    revision: dict | None = None
    resolved_base: str | None = None
    if git.available and git.executable:
        head_commit = gitutil.resolve_commit(git.executable, cwd, env, "HEAD")
        resolved_base = head_commit
        if "--base" in parsed.single:
            resolved_base = gitutil.resolve_commit(git.executable, cwd, env, base_arg)
            if resolved_base is None:
                raise CliArgError("check", f"--baseを解決できません: {base_arg}")
        if head_commit is not None:
            dirty = gitutil.is_dirty(git.executable, cwd, env)
            revision = {"base": resolved_base, "commit": head_commit, "dirty": dirty}
    else:
        if "--base" in parsed.single:
            raise CliArgError("check", f"--baseを解決できません: {base_arg}")

    extra_revs = [resolved_base] if resolved_base is not None else []
    pre = multiws.precheck(cwd, git, env, extra_config_revs=extra_revs)
    if pre.discovery_failed:
        raise CliArgError("check", "複合workspaceのroot設定を発見できません")

    if pre.ok:
        return _run_all_workspaces_members(parsed, cwd, env, git, pre, revision, resolved_base, started)

    diagnostics = sort_diagnostics([d.to_dict() for d in pre.diagnostics])
    status = status_from_diagnostics(diagnostics)
    result: dict = {
        "schemaVersion": "1.0",
        "operation": "check",
        "status": status,
        "scope": "all-workspaces",
        "multiWorkspace": {"id": pre.root_id, "path": "."},
        "workspaces": [],
        "revision": revision,
        "durationMs": max(0, time.monotonic_ns() // 1_000_000 - started),
        "diagnostics": diagnostics,
    }
    return result, EXIT_CODE_BY_STATUS[status]


def run(parsed: ParsedArgs, cwd: str, env: dict[str, str]) -> tuple[dict, int]:
    if "--all-workspaces" in parsed.flags:
        return _run_all_workspaces(parsed, cwd, env)

    scope_requested: str
    if parsed.positionals:
        scope_requested = "selected"
    elif "--full" in parsed.flags:
        scope_requested = "full"
    else:
        scope_requested = "changed"
    want_report = "--report" in parsed.flags

    started = time.monotonic_ns() // 1_000_000
    git = gitutil.detect_git(cwd, env)
    base_arg = parsed.single.get("--base", "HEAD")

    revision: dict | None = None
    if git.available and git.executable:
        # 終了コード4になるのは明示した--baseを解決できない場合だけである（結果契約 §2）。
        # --base省略時のHEADが解決できないunborn repositoryはrevision: nullへ縮退する。
        head_commit = gitutil.resolve_commit(git.executable, cwd, env, "HEAD")
        base_commit = head_commit
        if "--base" in parsed.single:
            base_commit = gitutil.resolve_commit(git.executable, cwd, env, base_arg)
            if base_commit is None:
                raise CliArgError("check", f"--baseを解決できません: {base_arg}")
        if head_commit is None:
            # unborn repository: revisionをnullへ縮退する（安全な入出力仕様 §8）。
            revision = None
        else:
            dirty = gitutil.is_dirty(git.executable, cwd, env)
            revision = {"base": base_commit, "commit": head_commit, "dirty": dirty}
    else:
        if "--base" in parsed.single:
            raise CliArgError("check", f"--baseを解決できません: {base_arg}")
        revision = None

    # `scope: changed`（引数なし）はGit基準版が解決できない場合`scope: full`へ縮退する
    # （check.md §10、安全な入出力仕様 §8）。Git不在の縮退だけ`SPEC-GIT-DEGRADED-001`／warningで
    # 示す。unborn repository（Git利用可能だがHEAD不在）は黙って全体checkへ縮退する。
    scope = scope_requested
    git_degraded = False
    if scope_requested == "changed" and revision is None:
        scope = "full"
        if not git.available:
            git_degraded = True

    base_commit: str | None = revision["base"] if revision is not None else None

    loc = locate_workspace(cwd, git, env)

    # --- 修飾IDを起点にする場合のworkspace決定（複合workspace仕様 §3）。--------------------
    # 明示対象のいずれかが修飾ID（`ws::local`）なら、その所有workspaceをactiveへ切り替える。
    # 複数の修飾起点が異なるworkspaceを持てば引数不正（終了コード4）。`--all-workspaces`は別経路
    # （`_run_all_workspaces`）が処理するためここには来ない。qualifierを持たない通常のcheckは
    # ここを一切通らず、既存の単一workspace経路（cwd起点の`locate_workspace`）をそのまま使う。
    multi_pre: multiws.PrecheckResult | None = None
    workspace_rel_path = "."
    qualified_prefixes = {
        q[0] for t in parsed.positionals if (q := multirelate.parse_qualified(t)) is not None
    }
    if qualified_prefixes:
        if len(qualified_prefixes) > 1:
            raise CliArgError("check", "複数の起点が異なるworkspaceに属しています")
        target_ws_id = next(iter(qualified_prefixes))
        multi_pre = multiws.precheck(
            cwd, git, env, extra_config_revs=[base_commit] if base_commit is not None else []
        )
        if multi_pre.ok:
            if target_ws_id == multi_pre.root_id:
                loc = WorkspaceLocation(
                    root=multi_pre.repo_root,
                    config_path=os.path.join(multi_pre.repo_root, ".spec", "bitz.yaml"),
                )
                workspace_rel_path = "."
            else:
                member = next((m for m in multi_pre.members if m.id == target_ws_id), None)
                if member is not None:
                    loc = WorkspaceLocation(
                        root=member.root, config_path=os.path.join(member.root, ".spec", "bitz.yaml")
                    )
                    workspace_rel_path = member.path

    requested_workspace = parsed.single.get("--workspace")

    outcome: config_mod.ConfigOutcome | None = None
    if loc.config_path is not None:
        outcome = config_mod.read_config(loc.config_path)

    if requested_workspace is not None:
        effective_id = outcome.workspace_id if outcome is not None else None
        if effective_id != requested_workspace:
            raise CliArgError("check", f"指定したworkspaceが見つかりません: {requested_workspace}")

    diagnostics: list[dict] = []
    workspace_id: str | None
    checked_document_count = 0
    checked_statement_count = 0
    selection: dict | None = None

    if git_degraded:
        diagnostics.append(
            {
                "code": "SPEC-GIT-DEGRADED-001",
                "severity": "warning",
                "resultStatus": "passed_with_warnings",
                "summary": messages.GIT_DEGRADED_FULL_FALLBACK,
                "source": {"kind": "environment", "component": "git", "identifier": "git"},
            }
        )

    if loc.config_path is None:
        workspace_id = None
        diagnostics.append(
            {
                "code": "SPEC-WORKSPACE-MISSING-001",
                "severity": "error",
                "resultStatus": "blocked",
                "summary": ".spec/bitz.yamlがありません",
                "source": {"kind": "environment", "component": "workspace", "identifier": "."},
            }
        )
    else:
        assert outcome is not None
        workspace_id = outcome.workspace_id
        # 停止有無にかかわらずBOM／未知key／profilesのwarning（`continue`継続単位）を残す。
        diagnostics.extend(d.to_dict() for d in outcome.diagnostics)
        diagnostics.extend(d.to_dict() for d in outcome.warnings)
        # 全体事前検査（設定）が非成功なら文書検査を開始しない（check.md §4「1」）。
        if not outcome.stop:
            assert loc.root is not None
            catalog = document_mod.build_catalog(loc.root, workspace_id)
            catalog_diags = catalog.diagnostics

            multi_active = multi_pre is not None and multi_pre.ok
            if multi_active:
                assert multi_pre is not None
                (
                    id_index,
                    statement_index,
                    local_id_indices,
                    local_stmt_indices,
                    known_ws_ids,
                ) = multirelate.build_multi_context(workspace_id, catalog.entries, multi_pre)
                real_roots = {
                    wid: os.path.realpath(root) for wid, root, _rel in multiws.ordered_workspaces(multi_pre)
                }
            else:
                id_index = relations_mod.build_id_index(catalog.entries)
                statement_index = relations_mod.build_statement_index(catalog.entries)
                local_id_indices = {workspace_id: id_index}
                local_stmt_indices = {workspace_id: statement_index}
                known_ws_ids = {workspace_id}
                real_roots = {}
            current_by_path = {e.path: e for e in relations_mod.valid_entries(catalog.entries)}

            # --- Git基準版が解決できた場合だけの横断検査（`check.md §5・§6・§8`）の下ごしらえ。
            # 実際のDiagnostic生成はscope別の完全検査対象（`full_check_ids`）確定後に行う
            # （`scope: selected`は完全検査対象だけへ絞る。`check.md §5`「同じ基準版を対象選択、
            # 状態遷移、削除検出、REQ保護、TASK境界へ使用」）。
            base_by_id: dict[str, DocEntry] = {}
            changed_paths: list[gitutil.ChangedPath] = []
            if base_commit is not None:
                base_by_id = basecompare.load_base_catalog(
                    git, cwd, env, base_commit, loc.root, workspace_id
                )
                if git.available and git.executable:
                    changed_paths = gitutil.collect_changed_paths(
                        git.executable, cwd, env, base_commit, loc.root
                    )
            base_by_path = {e.path: e for e in base_by_id.values()}

            current_ids_present = {e.doc_id for e in catalog.entries if e.doc_id is not None}

            if scope == "full":
                # `--full`はcatalog全体が完全検査対象（check.md §3）。sourceを絞らない。
                source_ids: set[str] | None = None
                checked_document_count = catalog.checked_document_count
                checked_statement_count = catalog.checked_statement_count
                extra_diags: list[Diagnostic] = []
            elif scope == "selected":
                # `scope: selected`の完全検査対象は`TargetExpansion(root, interpret).contextDocuments`と
                # それらへの直接逆参照の和集合だけに限る（check.md §3）。
                root_diags, context_ids, task_roots = _resolve_selected_roots(
                    parsed,
                    id_index,
                    statement_index,
                    active_ws_id=workspace_id if multi_active else None,
                    local_entries=catalog.entries if multi_active else None,
                )
                full_check_ids = context_ids | _direct_reverse_references(
                    context_ids, id_index, statement_index,
                    source_index=local_id_indices[workspace_id] if multi_active else None,
                )
                source_ids = full_check_ids
                checked_paths = {e.path for e in catalog.entries if e.doc_id in full_check_ids}

                checked_document_count = 0
                checked_statement_count = 0
                for doc_id in full_check_ids:
                    entry = id_index.get(doc_id)
                    if entry is not None and entry.counted:
                        checked_document_count += 1
                        checked_statement_count += entry.statement_count

                task_diags: list[Diagnostic] = []
                for task_entry in task_roots:
                    task_diags.extend(
                        _task_boundary_diagnostics(
                            task_entry, git, cwd, env, base_commit, workspace_id, loc.root,
                            real_roots=real_roots if multi_active else None,
                        )
                    )
                extra_diags = root_diags + task_diags
                catalog_diags = _filter_catalog_diagnostics_for_scope(catalog_diags, catalog.entries, checked_paths)
            else:
                # `scope: changed`: Git変更集合から選んだ所有文書、強い依存閉包、直接逆参照が
                # 完全検査対象（check.md §3・§6）。
                implements_index = basecompare.build_reverse_index(id_index, "implements")
                tests_index = basecompare.build_reverse_index(id_index, "tests")
                owning_ids, changed_path_count, excluded_count = basecompare.changed_selection(
                    changed_paths, current_by_path, base_by_path, implements_index, tests_index
                )
                strong_closure = basecompare.strong_dependency_closure(owning_ids, id_index)
                full_check_ids = owning_ids | strong_closure
                full_check_ids |= _direct_reverse_references(full_check_ids, id_index, statement_index)
                source_ids = full_check_ids
                checked_paths = {e.path for e in catalog.entries if e.doc_id in full_check_ids}
                catalog_diags = _filter_catalog_diagnostics_for_scope(catalog_diags, catalog.entries, checked_paths)
                extra_diags = []
                selection = {
                    "changedPathCount": changed_path_count,
                    "targetDocumentCount": len(owning_ids),
                    "excludedCodeTestPathCount": excluded_count,
                }

            if multi_active:
                # 複合workspace内のworkspace単独check（明示修飾対象）: 修飾ID解決の優先順位
                # （関係・トレースモデル §5.1）と所有境界（複合workspace仕様 §5.1）を適用する。
                # Diagnosticはactive workspace自身の完全検査対象文書（source_ids）だけへ生成する
                # （`relations.py`の``_source_entries``と同じ絞り込みをentries側で行う）。
                scoped_entries = (
                    catalog.entries if source_ids is None
                    else [e for e in catalog.entries if e.doc_id in source_ids]
                )
                relation_diags = []
                for e in relations_mod.valid_entries(scoped_entries):
                    relation_diags.extend(
                        multirelate.field_diagnostics(e, workspace_id, local_id_indices, local_stmt_indices, known_ws_ids)
                    )
                # 横断edgeを含めたgraphで循環を検査する（関係・トレースモデル §4）。ロード済みの
                # 全workspace（active＋修飾参照で読み込んだ他workspace）を1つのgraphとして計算し、
                # activeへ帰属するedgeだけをこの結果へ残す（このworkspace単独checkが返すのは
                # active workspace自身のDiagnosticだけ）。
                cycle_entries_by_ws = {wid: list(idx.values()) for wid, idx in local_id_indices.items()}
                relation_diags.extend(
                    d
                    for d in multirelate.global_cycle_diagnostics(cycle_entries_by_ws)
                    if d.source.get("workspaceId") == workspace_id
                )
                path_diags = multirelate.path_diagnostics(scoped_entries, workspace_id, loc.root, real_roots)
                coverage_diags = multirelate.coverage_diagnostics(
                    scoped_entries, workspace_id, local_id_indices, local_stmt_indices, known_ws_ids
                )
            else:
                relation_diags = relations_mod.check_relations(catalog.entries, workspace_id, source_ids=source_ids)
                path_diags = relations_mod.check_paths(catalog.entries, loc.root, workspace_id, source_ids=source_ids)
                coverage_diags = relations_mod.check_coverage(catalog.entries, workspace_id, source_ids=source_ids)

            # `scope: selected`は完全検査対象（`full_check_ids`＝`source_ids`）だけへ状態遷移・
            # 承認済みREQ保護・影響候補を絞る（検収指摘: `check.md §5`はscopeを限定しない）。
            # `scope: full`・`changed`は従来どおり絞らない（未変更文書は基準版と現在版が同一内容の
            # ため、これらの検査は自然にno-opになり安全）。
            base_source_ids = full_check_ids if scope == "selected" else None
            base_diags: list[Diagnostic] = []
            if base_commit is not None:
                base_diags.extend(
                    basecompare.state_transition_diagnostics(
                        base_by_id,
                        id_index,
                        workspace_id,
                        current_ids_present=current_ids_present,
                        source_ids=base_source_ids,
                    )
                )
                base_diags.extend(
                    basecompare.approved_protection_diagnostics(
                        base_by_id, id_index, workspace_id, source_ids=base_source_ids
                    )
                )
                changed_doc_ids = basecompare.changed_spec_document_ids(
                    changed_paths, current_by_path, base_by_path
                )
                base_diags.extend(
                    basecompare.impact_candidate_diagnostics(
                        changed_doc_ids, id_index, workspace_id, source_ids=base_source_ids
                    )
                )

            diagnostics.extend(d.to_dict() for d in catalog_diags)
            diagnostics.extend(d.to_dict() for d in relation_diags)
            diagnostics.extend(d.to_dict() for d in path_diags)
            diagnostics.extend(d.to_dict() for d in coverage_diags)
            diagnostics.extend(d.to_dict() for d in extra_diags)
            diagnostics.extend(d.to_dict() for d in base_diags)

    diagnostics = sort_diagnostics(diagnostics)
    status = status_from_diagnostics(diagnostics)
    result: dict = {
        "schemaVersion": "1.0",
        "operation": "check",
        "status": status,
        "scope": scope,
        "workspace": {"id": workspace_id, "path": workspace_rel_path},
        "revision": revision,
    }
    if scope == "changed":
        result["selection"] = selection if selection is not None else {
            "changedPathCount": 0,
            "targetDocumentCount": 0,
            "excludedCodeTestPathCount": 0,
        }
    else:
        result["checkedDocumentCount"] = checked_document_count
        result["checkedStatementCount"] = checked_statement_count
    result["durationMs"] = max(0, time.monotonic_ns() // 1_000_000 - started)
    result["diagnostics"] = diagnostics

    if want_report:
        write_workspace_root = loc.root if loc.root is not None else cwd
        failure = reportio.write_report(write_workspace_root, workspace_id, "check", result)
        if failure is not None:
            diagnostics = list(result["diagnostics"])
            diagnostics.append(failure.to_dict())
            result["diagnostics"] = diagnostics
            status = status_from_diagnostics(diagnostics)
            result["status"] = status

    return result, EXIT_CODE_BY_STATUS[status]
