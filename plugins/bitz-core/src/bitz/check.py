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

import time

from . import basecompare
from . import config as config_mod
from . import document as document_mod
from . import gitutil
from . import messages
from . import multiws
from . import relations as relations_mod
from . import reportio
from . import targetexpand
from .cliargs import ParsedArgs
from .config import Diagnostic
from .document import DocEntry
from .errors import CliArgError
from .notimpl import NotImplementedOperation
from .resultmodel import EXIT_CODE_BY_STATUS, sort_diagnostics, status_from_diagnostics
from .workspace import locate_workspace


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


def _run_all_workspaces(parsed: ParsedArgs, cwd: str, env: dict[str, str]) -> tuple[dict, int]:
    """`check --all-workspaces`（`複合workspace仕様 §8`）。

    Step 5Aは全体事前検査だけを実装する。事前検査通過後のmember単位のcheck（横断relation解決、
    checkedDocumentCount／checkedStatementCountの集計）はStep 5B以降で実装するため、通過した場合は
    既存のNotImplementedOperationの作法で明示的に停止する（黙って成功にしない）。
    """

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
        raise NotImplementedOperation("check --all-workspaces: member処理はStep 5B以降で実装する")

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

            id_index = relations_mod.build_id_index(catalog.entries)
            statement_index = relations_mod.build_statement_index(catalog.entries)
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

                task_diags: list[Diagnostic] = []
                for task_entry in task_roots:
                    task_diags.extend(
                        _task_boundary_diagnostics(
                            task_entry, git, cwd, env, base_commit, workspace_id, loc.root
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
        "workspace": {"id": workspace_id, "path": "."},
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
