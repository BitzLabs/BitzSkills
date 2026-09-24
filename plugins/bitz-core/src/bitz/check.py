"""`bitz check` 操作（`03_操作仕様/02_check.md`）。

Step 2 Phase Bで`scope: full`（catalog全体の軽量Frontmatter索引・EARS-AI・style検査）を実装した。
Phase Cは同じcatalogを使って次を追加する。

- `scope: full`向けのrelation（存在・型・legacy `refs`・循環）・`implements`/`tests[].path`存在・
  `tests[].covers`妥当性検査（`relations.py`）
- 明示対象（`scope: selected`）: 構文検査済みの対象を catalog で解決し、
  :func:`bitz.targetexpand.target_expansion` （`関係・トレースモデル §6.4`）で
  `contextDocuments` を求める
- 明示TASK境界検査（`check.md §7`）

`scope: changed`（引数なしのGit変更起点）、状態遷移・削除検出・承認済みREQ保護・影響候補は
Step 3以降で実装するため、引数なしはStep 1と同じ`NotImplementedOperation`のままとする。
"""

from __future__ import annotations

import time

from . import config as config_mod
from . import document as document_mod
from . import gitutil
from . import messages
from . import relations as relations_mod
from . import targetexpand
from .cliargs import ParsedArgs
from .config import Diagnostic
from .document import DocEntry
from .errors import CliArgError
from .notimpl import NotImplementedOperation
from .resultmodel import EXIT_CODE_BY_STATUS, sort_diagnostics, status_from_diagnostics
from .workspace import locate_workspace

NOT_IMPLEMENTED_REASON = "check: scope=changedの本体処理はStep 3以降で実装する"


def _resolve_target(
    target: str,
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
    path_index: dict[str, str],
) -> str | None:
    """構文検査済みの明示対象文字列を所有文書IDへ正規化する（`check.md §2`）。

    文書ID、statement ID、SPEC Markdown pathのいずれかで解決を試みる。catalogに存在しなければ
    ``None``を返す（呼び出し側が`CTX-ROOT-MISSING-001`を返す）。
    """

    if target in id_index:
        return target
    stmt = statement_index.get(target)
    if stmt is not None:
        return stmt["documentId"]
    return path_index.get(target)


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


def _task_boundary_diagnostics(
    entry: DocEntry,
    git: gitutil.GitInfo,
    cwd: str,
    env: dict[str, str],
    base_commit: str | None,
    workspace_id: str,
    workspace_root: str,
) -> list[Diagnostic]:
    """明示TASK境界検査（`check.md §7`）。TASK ID/pathを明示した場合だけ呼び出す。"""

    if not git.available or git.executable is None or base_commit is None:
        return [
            Diagnostic(
                code="SPEC-TASK-BOUNDARY-002",
                severity="error",
                resultStatus="blocked",
                summary=messages.task_boundary_no_git(entry.doc_id),
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
            if not _task_own_path_allows(p, allowed):
                reported.add(p)
                diags.append(
                    Diagnostic(
                        code="SPEC-TASK-BOUNDARY-001",
                        severity="error",
                        resultStatus="failed",
                        summary=messages.task_boundary_violation(p, entry.doc_id),
                        source={"kind": "file", "workspaceId": workspace_id, "path": p},
                    )
                )
    return diags


def _direct_reverse_references(
    context_ids: set[str], id_index: dict[str, DocEntry], statement_index: dict[str, dict]
) -> set[str]:
    """``context_ids``内のいずれかを直接参照する文書ID集合を返す（`check.md §3`「直接逆参照」）。

    参照は`relations`の全relation（`requires`/`refines`/`addresses`/`supersedes`/`related`）を
    対象とする。target解決は関係の型が妥当かを問わない（存在するIDへの直接参照であれば、明示対象の
    完全検査対象へ含める。型不適合そのものは`relations.check_relations`が別途Diagnosticにする）。
    """

    result: set[str] = set()
    for doc_id, entry in id_index.items():
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
) -> tuple[list[Diagnostic], set[str], list[DocEntry]]:
    """明示対象を解決し、`TargetExpansion(root, interpret)`の和集合を求める。

    戻り値は``(root解決Diagnostic, contextDocuments和集合, TASK root一覧)``。
    """

    path_index = {e.path: e.doc_id for e in id_index.values()}

    diags: list[Diagnostic] = []
    context_ids: set[str] = set()
    task_roots: list[DocEntry] = []

    for target in parsed.positionals:
        root_id = _resolve_target(target, id_index, statement_index, path_index)
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


def run(parsed: ParsedArgs, cwd: str, env: dict[str, str]) -> tuple[dict, int]:
    scope: str
    if parsed.positionals:
        scope = "selected"
    elif "--full" in parsed.flags:
        scope = "full"
    else:
        raise NotImplementedOperation(NOT_IMPLEMENTED_REASON)
    if "--report" in parsed.flags:
        # TODO(Step 3): 明示reportの排他的作成を実装する。黙って無視するとreportがあるように見えるため止める。
        raise NotImplementedOperation("check: --reportの保存はStep 3以降で実装する")

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
            # TODO(Step 3): unborn repositoryの全体check縮退（SINGLE-039）を実装する。
            revision = None
        else:
            dirty = gitutil.is_dirty(git.executable, cwd, env)
            revision = {"base": base_commit, "commit": head_commit, "dirty": dirty}
    else:
        if "--base" in parsed.single:
            raise CliArgError("check", f"--baseを解決できません: {base_arg}")
        revision = None

    loc = locate_workspace(cwd, git, env)
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

            id_index = relations_mod.build_id_index(catalog.entries)
            statement_index = relations_mod.build_statement_index(catalog.entries)

            if scope == "full":
                # `--full`はcatalog全体が完全検査対象（check.md §3）。sourceを絞らない。
                source_ids: set[str] | None = None
                checked_document_count = catalog.checked_document_count
                checked_statement_count = catalog.checked_statement_count
                extra_diags: list[Diagnostic] = []
            else:
                # `scope: selected`の完全検査対象は`TargetExpansion(root, interpret).contextDocuments`と
                # それらへの直接逆参照の和集合だけに限る（check.md §3）。
                root_diags, context_ids, task_roots = _resolve_selected_roots(parsed, id_index, statement_index)
                full_check_ids = context_ids | _direct_reverse_references(context_ids, id_index, statement_index)
                source_ids = full_check_ids
                checked_paths = {e.path for e in catalog.entries if e.doc_id in full_check_ids}

                checked_document_count = 0
                checked_statement_count = 0
                for doc_id in full_check_ids:
                    entry = id_index.get(doc_id)
                    if entry is not None and entry.counted:
                        checked_document_count += 1
                        checked_statement_count += entry.statement_count

                base_commit = revision["base"] if revision is not None else None
                task_diags: list[Diagnostic] = []
                for task_entry in task_roots:
                    task_diags.extend(
                        _task_boundary_diagnostics(
                            task_entry, git, cwd, env, base_commit, workspace_id, loc.root
                        )
                    )
                extra_diags = root_diags + task_diags
                catalog_diags = _filter_catalog_diagnostics_for_scope(catalog_diags, catalog.entries, checked_paths)

            relation_diags = relations_mod.check_relations(catalog.entries, workspace_id, source_ids=source_ids)
            path_diags = relations_mod.check_paths(catalog.entries, loc.root, workspace_id, source_ids=source_ids)
            coverage_diags = relations_mod.check_coverage(catalog.entries, workspace_id, source_ids=source_ids)

            diagnostics.extend(d.to_dict() for d in catalog_diags)
            diagnostics.extend(d.to_dict() for d in relation_diags)
            diagnostics.extend(d.to_dict() for d in path_diags)
            diagnostics.extend(d.to_dict() for d in coverage_diags)
            diagnostics.extend(d.to_dict() for d in extra_diags)
        # TODO(Step 3以降): 状態遷移、承認済みREQ保護、changed-only対象選択、影響候補を実装する。

    diagnostics = sort_diagnostics(diagnostics)
    status = status_from_diagnostics(diagnostics)
    result = {
        "schemaVersion": "1.0",
        "operation": "check",
        "status": status,
        "scope": scope,
        "workspace": {"id": workspace_id, "path": "."},
        "revision": revision,
        "checkedDocumentCount": checked_document_count,
        "checkedStatementCount": checked_statement_count,
        "durationMs": max(0, time.monotonic_ns() // 1_000_000 - started),
        "diagnostics": diagnostics,
    }
    return result, EXIT_CODE_BY_STATUS[status]
