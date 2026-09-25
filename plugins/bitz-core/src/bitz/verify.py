"""`bitz verify` 操作（`03_操作仕様/03_verify.md`）。

Step 4で単一workspaceを実装した。Step 5Cで複合workspace（修飾target、`--all-workspaces`、
`02_SPECモデル/05_複合workspace仕様.md` §10）を追加する。`TargetExpansion(root, verify)`
（`targetexpand.py`）を唯一の展開契約として再利用し、targetごとにContextを解決してtest対応を
確認し、`bitz.yaml`のcommandをshellを介さず実行する。

複合workspaceのbinding計画は``(workspace_id, commandName)``を単位に集約する（同じcommand名でも
workspaceが異なれば別binding。verify.md §4「異なるcommand名はargv/cwdが同じでも別bindingとして
実行する…workspaceが異なればcommand名と内容が同じでも別bindingとする」）。coverage・binding判定の
target/statement/covers参照は、request（またはmember自身の）workspaceを基準にした内部表現
（active workspace自身はbare、他workspaceは`ws::local`修飾）のまま比較し、出力を組み立てる最終段で
だけ複合workspace正規形式へqualifyする（`context.py`と同じ設計。`context_mod._canon`/`_owner_of`を
再利用する）。
"""

from __future__ import annotations

import os
import time

from . import config as config_mod
from . import context as context_mod
from . import digest as digest_mod
from . import document as document_mod
from . import execfile
from . import gitutil
from . import messages
from . import multirelate
from . import multiws
from . import procrun
from . import relations as relations_mod
from . import reportio
from . import targetexpand
from .cliargs import ParsedArgs
from .document import DocEntry
from .errors import CliArgError
from .resultmodel import EXIT_CODE_BY_STATUS, sort_diagnostics, status_from_diagnostics, worst_status
from .workspace import WorkspaceLocation, locate_workspace

_ARGV_ELEMENT_LIMIT = 32 * 1024
_ARGV_TOTAL_LIMIT = 1024 * 1024
_ARGV_COUNT_LIMIT = 10000
_VERIFY_BINDING_LIMIT = multiws.HARD_LIMITS["verifyBindingCount"]


def _invocation_diag(code: str, severity: str, status: str, summary: str, argument: str | None = None) -> dict:
    src: dict = {"kind": "invocation"}
    if argument is not None:
        src["argument"] = argument
    return {"code": code, "severity": severity, "resultStatus": status, "summary": summary, "source": src}


def _file_diag(
    code: str, severity: str, status: str, summary: str, workspace_id, path: str, *, key: str | None = None
) -> dict:
    src: dict = {"kind": "file", "workspaceId": workspace_id, "path": path}
    if key is not None:
        src["key"] = key
    return {"code": code, "severity": severity, "resultStatus": status, "summary": summary, "source": src}


def _env_diag(code: str, severity: str, status: str, summary: str, component: str, identifier: str | None = None) -> dict:
    src: dict = {"kind": "environment", "component": component}
    if identifier is not None:
        src["identifier"] = identifier
    return {"code": code, "severity": severity, "resultStatus": status, "summary": summary, "source": src}


def _resolve_target(
    target: str,
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
    path_index: dict[str, str],
    *,
    active_ws_id: str | None = None,
) -> str | None:
    """明示targetを正規IDへ解決する。statement IDはstatement IDのまま返す（statement粒度を保つ）。

    ``active_ws_id``を渡すと、``target``がactive workspace自身を指す修飾ID（``"<active_ws_id>::local"``）
    の場合だけ修飾子を外し、active workspace自身の索引で解決する（複合workspace仕様 §3。`check.py`の
    `_resolve_target`と同じ規則）。
    """

    lookup = target
    if active_ws_id is not None:
        q = multirelate.parse_qualified(target)
        if q is not None and q[0] == active_ws_id:
            lookup = q[1]
    if lookup in id_index:
        return lookup
    if lookup in statement_index:
        return lookup
    return path_index.get(lookup)


def _default_roots(id_index: dict[str, DocEntry]) -> list[str]:
    roots = []
    for doc_id, entry in id_index.items():
        if entry.kind == "REQ" and entry.status == "approved":
            roots.append(doc_id)
        elif entry.kind == "TECH" and entry.status == "approved":
            if entry.statements or (entry.frontmatter.get("tests") or []):
                roots.append(doc_id)
    return sorted(roots)


def _default_roots_all(catalog_entries: list[DocEntry], valid_id_index: dict[str, DocEntry]) -> list[str]:
    """`--all-workspaces`のmember単位既定対象（verify.md §7）。catalog検証で除外された（`hard`）
    文書も、frontmatterだけで同じ既定対象基準を満たせば候補へ含める。

    `--all-workspaces`は暗黙にmemberを除外しない。frontmatterのid/status/tests自体はEARS-AI本文の
    構文検査（`entry.hard`）より前に読めているため、当該文書自身のcatalog Diagnostic（例:
    `EAI-CORE-ID-002`）をそのtargetの結果として返せる（MULTI-012「invalid文書へ強く依存するtargetを
    遮断し独立targetを実行する」）。
    """

    roots: set[str] = set()
    for doc_id, entry in valid_id_index.items():
        if entry.kind == "REQ" and entry.status == "approved":
            roots.add(doc_id)
        elif entry.kind == "TECH" and entry.status == "approved":
            if entry.statements or (entry.frontmatter.get("tests") or []):
                roots.add(doc_id)
    for e in catalog_entries:
        if e.hard is None or e.duplicate or e.doc_id is None or e.doc_id in valid_id_index:
            continue
        fm = e.frontmatter or {}
        if e.kind == "REQ" and fm.get("status") == "approved":
            roots.add(e.doc_id)
        elif e.kind == "TECH" and fm.get("status") == "approved":
            if fm.get("tests"):
                roots.add(e.doc_id)
    return sorted(roots)


def _total_command_definition_count(config_by_ws: dict[str, dict], workspaces) -> int:
    """全workspaceの`verify.commands`定義数の単純和（複合workspace仕様 §10「commandDefinitionCount」）。

    `multiws._check_resource_limits`と同じ数え方（bitz.yamlの設定だけを見る。SPEC Markdown本文の
    厳密parseを要しないため、`--all-workspaces`の全体事前検査で`commandDefinitionCount`を
    `skip_limit_dimensions`により後回しにしても、ここで安価に再計算できる）。
    """

    total = 0
    for wid, _root, _rel in workspaces:
        wconfig = config_by_ws[wid]
        verify_cfg = wconfig.get("verify") if isinstance(wconfig.get("verify"), dict) else {}
        commands = (verify_cfg or {}).get("commands")
        if isinstance(commands, dict):
            total += len(commands)
    return total


def _hard_entry_target_result(entry: DocEntry, key: str) -> dict:
    """catalog検証で除外された（`entry.hard`）文書を、そのまま自身のDiagnosticを持つtarget結果にする。"""

    diags = sort_diagnostics([d.to_dict() for d in (entry.hard or [])])
    status = worst_status([d["resultStatus"] for d in diags]) if diags else "failed"
    return {"target": key, "status": status, "contextDigest": None, "statements": [], "bindingRefs": [], "diagnostics": diags}


def _dependency_scan(
    context_documents, id_index: dict[str, DocEntry], invalid_by_ws: dict[str, set[str]]
) -> dict | None:
    """closure内のいずれかの文書が、他workspaceの無効（`hard`）文書を修飾refで参照していないか調べる。

    見つかれば``{"dependencyWorkspaces": [...], "dependencySpecRefs": [...]}``（重複なし辞書順）を返す
    （複合workspace仕様 §8。既に具体的Diagnosticがあるunit自身への派生遮断は呼び出し側が避ける。ここは
    closureに引き込まれた**他**workspaceの無効文書だけを検出し、rootまたはrefiner自身の構文・型不正は
    別途`relations`側のDiagnosticが担う）。
    """

    dep_ws: set[str] = set()
    dep_refs: set[str] = set()
    for doc_id in context_documents:
        entry = id_index[doc_id]
        relations_raw = (entry.frontmatter or {}).get("relations") or {}
        refs: list[str] = []
        for rel in ("requires", "refines", "addresses", "supersedes"):
            refs.extend(relations_raw.get(rel) or [])
        for ref in refs:
            q = multirelate.parse_qualified(ref)
            if q is None:
                continue
            ws, local = q
            if ws not in invalid_by_ws:
                continue
            local_doc = local.split(":", 1)[0]
            if local_doc in invalid_by_ws[ws]:
                dep_ws.add(ws)
                dep_refs.add(f"{ws}::{local_doc}")
    if not dep_ws:
        return None
    return {"dependencyWorkspaces": sorted(dep_ws), "dependencySpecRefs": sorted(dep_refs)}


def _make_covering_tests(context_documents, id_index: dict[str, DocEntry], workspace_id: str, multi_active: bool):
    """``cover_id``（target自身のworkspaceを基準にした内部表現）を対象句にするtestを検索する関数を返す。

    複合workspaceでは、``cover_id``と各testの``covers``宣言をどちらも複合workspace正規形式へ
    qualifyしてから比較する（宣言側は自workspaceを基準に非修飾／修飾のどちらでも書けるため、
    素の文字列比較では同じ対象を指す異表記を取りこぼす）。
    """

    def _covering_tests(cover_id: str) -> list[tuple[DocEntry, int, dict, str]]:
        target_canon = context_mod._canon(cover_id, workspace_id) if multi_active else cover_id
        out: list[tuple[DocEntry, int, dict, str]] = []
        for doc_id in context_documents:
            doc_entry = id_index[doc_id]
            owner = context_mod._owner_of(doc_id, workspace_id) if multi_active else workspace_id
            for idx, t in enumerate(doc_entry.frontmatter.get("tests") or []):
                for c in (t.get("covers") or []):
                    c_canon = context_mod._canon(c, owner) if multi_active else c
                    if c_canon == target_canon:
                        out.append((doc_entry, idx, t, owner))
                        break
        return out

    return _covering_tests


def _relation_check_diagnostics(
    context_documents,
    workspace_id: str,
    catalog_entries: list[DocEntry],
    local_id_indices: dict[str, dict[str, DocEntry]],
    local_stmt_indices: dict[str, dict[str, dict]],
    known_ws_ids: set[str],
    multi_active: bool,
):
    """targetの完全解決対象（request workspace自身が所有する閉包内文書）のrelation Diagnosticを返す。"""

    if multi_active:
        scoped_entries = [e for e in relations_mod.valid_entries(catalog_entries) if e.doc_id in context_documents]
        diags = []
        for e in scoped_entries:
            diags.extend(
                multirelate.field_diagnostics(e, workspace_id, local_id_indices, local_stmt_indices, known_ws_ids)
            )
        return diags
    id_index = local_id_indices[workspace_id]
    statement_index = local_stmt_indices[workspace_id]
    return relations_mod.check_relations(catalog_entries, workspace_id, source_ids=set(context_documents))


def _compute_verify_digest(
    root_id: str,
    expansion: targetexpand.TargetExpansionResult,
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
    workspace_id: str,
    workspace_path: str,
    config_raw: dict,
    resolved_commands: dict,
    *,
    multi_active: bool = False,
    config_for=None,
    ws_path_by_id: dict[str, str] | None = None,
) -> str:
    context_documents = expansion.context_documents
    body_texts = {
        doc_id: digest_mod.normalize_body_text(id_index[doc_id].body or "") for doc_id in context_documents
    }

    def _owner(d: str) -> str:
        return context_mod._owner_of(d, workspace_id) if multi_active else workspace_id

    norm_frontmatters = {
        doc_id: context_mod._normalize_frontmatter(
            id_index[doc_id], owner_ws_id=(_owner(doc_id) if multi_active else None)
        )
        for doc_id in context_documents
    }

    ctx_cfg = config_raw.get("context") or {}
    verify_cfg = config_raw.get("verify") or {}

    if multi_active:
        assert config_for is not None and ws_path_by_id is not None
        reached = sorted({_owner(d) for d in context_documents} - {workspace_id})
        referenced_commands_multi: set[tuple[str, str]] = set()
        for doc_id in context_documents:
            owner = _owner(doc_id)
            for t in id_index[doc_id].frontmatter.get("tests") or []:
                name = t.get("command")
                if name:
                    referenced_commands_multi.add((owner, name))
        # `purpose=verify`のBundleがbindingとして実際に収録した場合だけcommand/timeoutを含める
        # （context仕様 §6）。command名が定義未解決（bindingを構成できない）なら含めない。
        commands_settings = []
        binding_ws_ids: set[str] = set()
        for wid, name in sorted(referenced_commands_multi):
            cfg = config_for(wid)
            resolved = (cfg.get("_resolvedCommands") or {}).get(name)
            if resolved is None:
                continue
            binding_ws_ids.add(wid)
            commands_settings.append(
                {"workspaceId": wid, "name": name, "argv": list(resolved["argv"]), "cwd": resolved.get("cwd", ".")}
            )
        verify_timeouts = []
        for wid in sorted(binding_ws_ids):
            cfg = config_for(wid)
            vcfg = cfg.get("verify") or {}
            verify_timeouts.append(
                {"workspaceId": wid, "timeoutSeconds": vcfg.get("timeoutSeconds", context_mod.DEFAULT_VERIFY_TIMEOUT)}
            )
        settings_ws_ids = sorted(set(reached) | {workspace_id})
        settings_workspaces = []
        for wid in settings_ws_ids:
            cfg = config_for(wid)
            settings_workspaces.append(
                {
                    "id": wid,
                    "schemaVersion": str(cfg.get("schemaVersion", "1.0")),
                    "earsAi": str(cfg.get("earsAi", "1.0")),
                    "language": str(cfg.get("language", "en")),
                }
            )
        top_workspaces = [{"id": workspace_id, "path": workspace_path}] + [
            {"id": w, "path": ws_path_by_id.get(w, ".")} for w in reached
        ]
    else:
        referenced_commands: set[str] = set()
        for doc_id in context_documents:
            for t in id_index[doc_id].frontmatter.get("tests") or []:
                name = t.get("command")
                if name:
                    referenced_commands.add(name)
        # `purpose=verify`のBundleがbindingとして実際に収録した場合だけcommand/timeoutを含める
        # （context仕様 §6）。command名が定義未解決（bindingを構成できない）なら含めない。
        commands_settings = []
        for name in sorted(referenced_commands):
            resolved = resolved_commands.get(name)
            if resolved is None:
                continue
            commands_settings.append(
                {"workspaceId": workspace_id, "name": name, "argv": list(resolved["argv"]), "cwd": resolved.get("cwd", ".")}
            )
        has_binding = bool(commands_settings)
        verify_timeouts = (
            [{"workspaceId": workspace_id, "timeoutSeconds": verify_cfg.get("timeoutSeconds", context_mod.DEFAULT_VERIFY_TIMEOUT)}]
            if has_binding
            else []
        )
        settings_workspaces = [
            {
                "id": workspace_id,
                "schemaVersion": str(config_raw.get("schemaVersion", "1.0")),
                "earsAi": str(config_raw.get("earsAi", "1.0")),
                "language": str(config_raw.get("language", "en")),
            }
        ]
        top_workspaces = [{"id": workspace_id, "path": "."}]

    cross_edges: list[dict] = []
    if multi_active:
        seen_edges: set[tuple[str, str, str]] = set()
        for doc_id in context_documents:
            owner = _owner(doc_id)
            entry = id_index[doc_id]
            for sr in context_mod._strong_relations(entry, id_index, statement_index, owner_ws_id=owner):
                rel, target_ref = sr["relation"], sr["target"]
                q = multirelate.parse_qualified(target_ref)
                target_owner = q[0] if q is not None else owner
                if target_owner == owner:
                    continue
                source_qid = context_mod._canon(doc_id, workspace_id)
                key = (source_qid, rel, target_ref)
                if key in seen_edges:
                    continue
                seen_edges.add(key)
                cross_edges.append({"relation": rel, "source": source_qid, "target": target_ref})
        cross_edges.sort(key=lambda e: (e["source"], e["relation"], e["target"]))

    if multi_active:
        canon_to_internal = {context_mod._canon(d, workspace_id): d for d in context_documents}
        doc_order = sorted(canon_to_internal)
    else:
        doc_order = sorted(context_documents)
        canon_to_internal = {d: d for d in context_documents}

    digest_documents = []
    for cid in doc_order:
        d = canon_to_internal[cid]
        entry = id_index[d]
        owner = _owner(d)
        digest_documents.append(
            {
                "id": cid,
                "workspaceId": owner,
                "kind": context_mod._KIND_LABEL[entry.kind],
                "status": entry.status,
                "applicability": "applicable",
                "frontmatter": norm_frontmatters[d],
                "bodyText": body_texts[d],
                "statements": [
                    context_mod._digest_statement(s, owner_ws_id=(owner if multi_active else None))
                    for s in entry.statements
                ],
                "strongRelations": context_mod._strong_relations(
                    entry, id_index, statement_index, owner_ws_id=(owner if multi_active else None)
                ),
            }
        )

    roots_out = [context_mod._canon(root_id, workspace_id)] if multi_active else [root_id]

    digest_materials = {
        "digestVersion": digest_mod.DIGEST_VERSION,
        "specSchemaVersion": str(config_raw.get("schemaVersion", "1.0")),
        "earsAiVersion": str(config_raw.get("earsAi", "1.0")),
        "resolverVersion": digest_mod.RESOLVER_VERSION,
        "purpose": "verify",
        "requestWorkspaceId": workspace_id,
        "roots": roots_out,
        "workspaces": top_workspaces,
        "documents": digest_documents,
        "crossWorkspaceEdges": cross_edges,
        "settings": {
            "workspaces": settings_workspaces,
            "context": {
                "maxDocuments": ctx_cfg.get("maxDocuments", context_mod.DEFAULT_MAX_DOCUMENTS),
                "maxBytes": ctx_cfg.get("maxBytes", context_mod.DEFAULT_MAX_BYTES),
            },
            "verifyTimeouts": verify_timeouts,
            "commands": commands_settings,
        },
    }
    return digest_mod.compute_digest(digest_materials)


def _expand_argv(argv_template: list[str], tests_workspace_rel: list[str], cwd_abs: str, workspace_root: str) -> list[str]:
    if "{tests}" not in argv_template:
        return list(argv_template)
    rel_tests = []
    for t in tests_workspace_rel:
        test_abs = os.path.normpath(os.path.join(workspace_root, t))
        rel = os.path.relpath(test_abs, cwd_abs)
        rel_tests.append(rel.replace(os.sep, "/"))
    index = argv_template.index("{tests}")
    return list(argv_template[:index]) + rel_tests + list(argv_template[index + 1 :])


def _process_single_target(
    key: str,
    root_id: str | None,
    raw: str,
    *,
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
    workspace_id: str,
    known_ws_ids: set[str],
    catalog_entries: list[DocEntry],
    local_id_indices: dict[str, dict[str, DocEntry]],
    local_stmt_indices: dict[str, dict[str, dict]],
    multi_active: bool,
    invalid_by_ws: dict[str, set[str]] | None,
    digest_fn,
    resolved_commands_for,
) -> tuple[dict, list[tuple[str, str, str, str]]]:
    """1 targetを解決する。``(entry_out, needed_pairs)``を返す。

    ``needed_pairs``は``(command所有workspace ID, command名, workspace相対test path,
    複合workspace正規形式のcover tag)``。呼び出し側がこれを``needs``（binding計画）へ集約する。
    ``entry_out``はbinding実行前の中間形で、``bindingRefs``に必要なbindingを列挙し、
    ``_needed``（``(ws, name)``の集合）を一時fieldとして持つ（呼び出し側がbinding blocked／実行結果を
    反映した後に取り除く）。
    """

    entry_out: dict = {
        "target": key,
        "status": "passed",
        "contextDigest": None,
        "statements": [],
        "bindingRefs": [],
        "diagnostics": [],
    }
    needed_pairs: list[tuple[str, str, str, str]] = []

    def _canon_id(x: str) -> str:
        return context_mod._canon(x, workspace_id) if multi_active else x

    if root_id is None:
        entry_out["diagnostics"] = [_invocation_diag("CTX-ROOT-MISSING-001", "error", "failed", messages.root_missing_explicit(raw), raw)]
        entry_out["status"] = "failed"
        return entry_out, needed_pairs

    expansion = targetexpand.target_expansion(root_id, "verify", id_index, statement_index)
    if expansion is None:
        entry_out["diagnostics"] = [_invocation_diag("CTX-ROOT-MISSING-001", "error", "failed", messages.root_missing_explicit(raw), raw)]
        entry_out["status"] = "failed"
        return entry_out, needed_pairs

    if expansion.errors:
        diags = []
        for err in expansion.errors:
            if err.get("doc_id") is None:
                diags.append(
                    _invocation_diag(err["code"], err["severity"], err["resultStatus"], err["summary"], err.get("root_arg", raw))
                )
            else:
                doc_id = err["doc_id"]
                owner = context_mod._owner_of(doc_id, workspace_id) if multi_active else workspace_id
                doc_path = id_index[doc_id].path
                diags.append(
                    _file_diag(err["code"], err["severity"], err["resultStatus"], err["summary"], owner, doc_path, key=err.get("key"))
                )
        entry_out["diagnostics"] = sort_diagnostics(diags)
        entry_out["status"] = worst_status([d["resultStatus"] for d in diags])
        return entry_out, needed_pairs

    context_documents = expansion.context_documents

    if multi_active and invalid_by_ws:
        dep_evidence = _dependency_scan(context_documents, id_index, invalid_by_ws)
        if dep_evidence is not None:
            root_entry = id_index[root_id]
            diag = _file_diag(
                "SPEC-MULTI-DEPENDENCY-001", "error", "blocked", messages.MULTI_DEPENDENCY_CONTEXT, workspace_id, root_entry.path
            )
            diag["evidence"] = {"stage": "context", **dep_evidence}
            entry_out["diagnostics"] = [diag]
            entry_out["status"] = "blocked"
            return entry_out, needed_pairs

    relation_error_diags = [
        d.to_dict()
        for d in _relation_check_diagnostics(
            context_documents, workspace_id, catalog_entries, local_id_indices, local_stmt_indices, known_ws_ids, multi_active
        )
        if d.severity == "error"
    ]
    if relation_error_diags:
        entry_out["diagnostics"] = sort_diagnostics(relation_error_diags)
        entry_out["status"] = worst_status([d["resultStatus"] for d in relation_error_diags])
        return entry_out, needed_pairs

    target_statements = expansion.target_statements
    covering_tests = _make_covering_tests(context_documents, id_index, workspace_id, multi_active)

    must_untested = []
    should_untested = []
    for stmt_id in target_statements:
        modality = statement_index[stmt_id]["modality"]
        if covering_tests(stmt_id):
            continue
        if modality == "MUST":
            must_untested.append(stmt_id)
        elif modality == "SHOULD":
            should_untested.append(stmt_id)

    coverage_diags = []
    for stmt_id in must_untested:
        doc_id = statement_index[stmt_id]["documentId"]
        owner = context_mod._owner_of(doc_id, workspace_id) if multi_active else workspace_id
        coverage_diags.append(
            _file_diag("CTX-COVERAGE-TEST-001", "error", "blocked", messages.verify_coverage_untested("MUST", _canon_id(stmt_id)), owner, id_index[doc_id].path)
        )
    for stmt_id in should_untested:
        doc_id = statement_index[stmt_id]["documentId"]
        owner = context_mod._owner_of(doc_id, workspace_id) if multi_active else workspace_id
        coverage_diags.append(
            _file_diag("CTX-COVERAGE-TEST-001", "warning", "passed_with_warnings", messages.verify_coverage_untested("SHOULD", _canon_id(stmt_id)), owner, id_index[doc_id].path)
        )

    context_digest = digest_fn(expansion)
    entry_out["contextDigest"] = context_digest
    entry_out["statements"] = [_canon_id(s) for s in target_statements]

    if must_untested:
        entry_out["diagnostics"] = sort_diagnostics(coverage_diags)
        entry_out["status"] = "blocked"
        return entry_out, needed_pairs

    # --- binding候補の決定（関係・トレースモデル §6.4「規範文なしTECHは文書単位bindingを保持」） ---
    # ``root_id``はstatement ID（例: "REQ-001:AC-01"）の場合があり、その場合``id_index``に
    # keyが無い。statement起点はtarget_statementsが非空になるため、doc-unit判定（TECH文書ID
    # keyが必要）に入る前に短絡させる（元の単一workspace実装と同じ`elif`規則を保つ）。
    doc_unit = False
    root_entry: DocEntry | None = None
    if not target_statements:
        root_entry = id_index[root_id]
        doc_unit = root_entry.kind == "TECH" and not root_entry.statements

    # skip-target（VERIFY-BINDING-MISSING）: testまたはcommand定義そのものが不足しbindingを
    # 構成できない条件。独立した原因（testエントリ単位）はそれぞれDiagnosticを返す（同一エントリを
    # 複数statementが指しても、同じraw原因（同じpath/key）へは1件に畳む）。
    binding_missing_diags: list[dict] = []
    seen_missing_keys: set[tuple[str, str]] = set()

    def _add_binding_missing(owner: str, path: str, idx: int, name: str | None) -> None:
        seen_key = (path, f"tests[{idx}].command")
        if seen_key in seen_missing_keys:
            return
        seen_missing_keys.add(seen_key)
        label = name if name else "(未指定)"
        binding_missing_diags.append(
            _file_diag(
                "SPEC-VERIFY-BLOCKED-001", "error", "blocked", messages.verify_command_undefined(label),
                owner, path, key=f"tests[{idx}].command",
            )
        )

    if doc_unit:
        for idx, t in enumerate(root_entry.frontmatter.get("tests") or []):
            name = t.get("command") or root_entry.frontmatter.get("verify")
            cmds = resolved_commands_for(workspace_id)
            if not name or name not in cmds:
                _add_binding_missing(workspace_id, root_entry.path, idx, name)
                continue
            for c in (t.get("covers") or []):
                needed_pairs.append((workspace_id, name, t["path"], _canon_id(c)))
    else:
        cover_ids = list(target_statements)
        for cover_id in cover_ids:
            for doc_entry, idx, t, owner in covering_tests(cover_id):
                name = t.get("command") or doc_entry.frontmatter.get("verify")
                cmds = resolved_commands_for(owner)
                if not name or name not in cmds:
                    _add_binding_missing(owner, doc_entry.path, idx, name)
                    continue
                needed_pairs.append((owner, name, t["path"], _canon_id(cover_id)))

    if binding_missing_diags:
        entry_out["diagnostics"] = sort_diagnostics(binding_missing_diags)
        entry_out["status"] = "blocked"
        entry_out["bindingRefs"] = []
        entry_out["contextDigest"] = context_digest
        return entry_out, []

    entry_out["bindingRefs"] = sorted({f"{ws}::{name}" for ws, name, _p, _c in needed_pairs})
    entry_out["_needed"] = sorted({(ws, name) for ws, name, _p, _c in needed_pairs})
    if should_untested:
        entry_out["diagnostics"] = sort_diagnostics(coverage_diags)
        entry_out["status"] = "passed_with_warnings"
    return entry_out, needed_pairs


def _plan_and_run_bindings(
    needs: dict[tuple[str, str], dict],
    *,
    ws_root_by_id: dict[str, str],
    resolved_commands_for,
    git: gitutil.GitInfo,
    env: dict[str, str],
    effective_timeout_for,
):
    """``needs``（``(workspace_id, command名) -> {"tests": set, "covers": set}``）からbinding実行計画を
    作り、workspace処理順（``ws_root_by_id``の挿入順）、command名辞書順で逐次実行する。

    戻り値は``(commands_by_key, status_by_key, blocked_keys, top_diagnostics)``。
    """

    plan: dict[tuple[str, str], dict] = {}
    blocked: dict[tuple[str, str], dict] = {}
    top_diagnostics: list[dict] = []
    config_untracked_cache: dict[str, bool] = {}

    def _config_untracked(ws_id: str) -> bool:
        if ws_id not in config_untracked_cache:
            root = ws_root_by_id[ws_id]
            if git.available and git.executable:
                config_untracked_cache[ws_id] = not gitutil.is_config_tracked(git.executable, root, env, config_mod.CONFIG_PATH)
            else:
                config_untracked_cache[ws_id] = False
        return config_untracked_cache[ws_id]

    for ws_id, name in sorted(needs):
        bucket = needs[(ws_id, name)]
        tests_sorted = sorted(bucket["tests"])
        covers_sorted = sorted(bucket["covers"])
        cmd_def = resolved_commands_for(ws_id).get(name)
        workspace_root = ws_root_by_id[ws_id]
        if cmd_def is None:
            continue

        cmd_cwd_rel = cmd_def.get("cwd", ".")
        cwd_abs = cmd_cwd_rel if os.path.isabs(cmd_cwd_rel) else os.path.normpath(os.path.join(workspace_root, cmd_cwd_rel))

        diag: dict | None = None
        expanded: list[str] = []
        if _config_untracked(ws_id):
            diag = _file_diag("SPEC-VERIFY-BLOCKED-001", "error", "blocked", messages.VERIFY_CONFIG_UNTRACKED, ws_id, config_mod.CONFIG_PATH)
        elif not os.path.isdir(cwd_abs):
            diag = _file_diag(
                "SPEC-VERIFY-BLOCKED-001", "error", "blocked", messages.verify_cwd_unavailable(),
                ws_id, config_mod.CONFIG_PATH, key=f"verify.commands.{name}.cwd",
            )
        else:
            outside = []
            for t in tests_sorted:
                test_abs = os.path.normpath(os.path.join(workspace_root, t))
                rel = os.path.relpath(test_abs, cwd_abs)
                if rel.startswith("..") or os.path.isabs(rel):
                    outside.append(t)
            if outside:
                diag = _file_diag(
                    "SPEC-VERIFY-BLOCKED-001", "error", "blocked", messages.VERIFY_TEST_OUTSIDE_CWD,
                    ws_id, config_mod.CONFIG_PATH, key=f"verify.commands.{name}.cwd",
                )
            else:
                argv_template = cmd_def["argv"]
                expanded = _expand_argv(argv_template, tests_sorted, cwd_abs, workspace_root)
                total_bytes = sum(len(a.encode("utf-8")) for a in expanded)
                if len(expanded) > _ARGV_COUNT_LIMIT:
                    diag = _file_diag(
                        "SPEC-VERIFY-BLOCKED-001", "error", "blocked", messages.verify_argv_expanded_count_limit(),
                        ws_id, config_mod.CONFIG_PATH, key=f"verify.commands.{name}.argv",
                    )
                elif any(len(a.encode("utf-8")) > _ARGV_ELEMENT_LIMIT for a in expanded):
                    diag = _file_diag(
                        "SPEC-VERIFY-BLOCKED-001", "error", "blocked", messages.VERIFY_ARGV_EXPANDED_LIMIT,
                        ws_id, config_mod.CONFIG_PATH, key=f"verify.commands.{name}.argv",
                    )
                elif total_bytes > _ARGV_TOTAL_LIMIT:
                    diag = _file_diag(
                        "SPEC-VERIFY-BLOCKED-001", "error", "blocked", messages.VERIFY_ARGV_EXPANDED_LIMIT,
                        ws_id, config_mod.CONFIG_PATH, key=f"verify.commands.{name}.argv",
                    )
                else:
                    resolved_exec = execfile.resolve_executable(argv_template[0], cwd_abs, env)
                    if resolved_exec is None:
                        summary = (
                            messages.VERIFY_EXECUTABLE_UNAVAILABLE
                            if "/" not in argv_template[0]
                            else messages.verify_executable_unavailable_path()
                        )
                        diag = _env_diag("SPEC-VERIFY-BLOCKED-001", "error", "blocked", summary, "command", f"{ws_id}::{name}")

        if diag is not None:
            blocked[(ws_id, name)] = diag
            top_diagnostics.append(diag)
            continue

        plan[(ws_id, name)] = {
            "argv": expanded, "cwd_rel": cmd_cwd_rel, "cwd_abs": cwd_abs, "tests": tests_sorted, "covers": covers_sorted,
        }

    commands_by_key: dict[tuple[str, str], dict] = {}
    status_by_key: dict[tuple[str, str], str] = {}
    for ws_id, name in sorted(plan):
        info = plan[(ws_id, name)]
        effective_timeout = effective_timeout_for(ws_id)
        child_env = dict(env)
        child_env["PWD"] = info["cwd_abs"]
        outcome_run = procrun.run(info["argv"], info["cwd_abs"], child_env, effective_timeout)
        termination = outcome_run["termination"]
        exit_code = outcome_run["exit_code"]
        if termination == "exit":
            status = "passed" if exit_code == 0 else "failed"
        else:
            status = "error"
            if termination == "spawn_error":
                summary = messages.VERIFY_SPAWN_ERROR
                code = "SPEC-VERIFY-COMMAND-001"
            elif termination == "signal":
                summary = messages.VERIFY_SIGNAL
                code = "SPEC-VERIFY-COMMAND-001"
            else:
                summary = messages.verify_timeout(effective_timeout)
                code = "SPEC-VERIFY-TIMEOUT-001"
            top_diagnostics.append(_env_diag(code, "error", "error", summary, "command", f"{ws_id}::{name}"))
        status_by_key[(ws_id, name)] = status
        commands_by_key[(ws_id, name)] = {
            "bindingId": f"{ws_id}::{name}",
            "workspaceId": ws_id,
            "name": name,
            "status": status,
            "termination": termination,
            "cwd": info["cwd_rel"],
            "argv": info["argv"],
            "tests": info["tests"],
            "covers": info["covers"],
            "exitCode": exit_code,
            "timeoutSeconds": effective_timeout,
            "stdoutExcerpt": outcome_run["stdout_excerpt"],
            "stderrExcerpt": outcome_run["stderr_excerpt"],
            "stdoutTruncated": outcome_run["stdout_truncated"],
            "stderrTruncated": outcome_run["stderr_truncated"],
            "durationMs": outcome_run["duration_ms"],
        }

    return commands_by_key, status_by_key, set(blocked), top_diagnostics


def _apply_binding_results(target_entries: list[dict], blocked_keys: set[tuple[str, str]], status_by_key: dict[tuple[str, str], str]) -> None:
    for entry_out in target_entries:
        needed = entry_out.pop("_needed", None)
        if not needed:
            continue
        blocked_here = {k for k in needed if k in blocked_keys}
        if blocked_here:
            entry_out["status"] = worst_status([entry_out["status"], "blocked"])
            entry_out["bindingRefs"] = sorted(
                ref for ref in entry_out["bindingRefs"] if tuple(ref.split("::", 1)) not in blocked_here
            )
    for entry_out in target_entries:
        statuses = [entry_out["status"]]
        for ref in entry_out["bindingRefs"]:
            ws_id, name = ref.split("::", 1)
            if (ws_id, name) in status_by_key:
                statuses.append(status_by_key[(ws_id, name)])
        entry_out["status"] = worst_status(statuses)


def run(parsed: ParsedArgs, cwd: str, env: dict[str, str]) -> tuple[dict, int]:
    started = time.monotonic_ns() // 1_000_000

    if "--all-workspaces" in parsed.flags:
        return _run_all_workspaces(parsed, cwd, env)

    want_report = "--report" in parsed.flags
    cli_timeout = parsed.single.get("--timeout")
    scope = "selected" if parsed.positionals else "all"

    git = gitutil.detect_git(cwd, env)
    loc = locate_workspace(cwd, git, env)
    requested_workspace = parsed.single.get("--workspace")

    # --- workspace決定（複合workspace仕様 §3）。修飾targetの所有workspaceをactiveにする。 ---
    multi_pre: multiws.PrecheckResult | None = None
    workspace_path = "."
    qualified_prefixes = {
        q[0] for t in parsed.positionals if (q := multirelate.parse_qualified(t)) is not None
    }
    if qualified_prefixes:
        if len(qualified_prefixes) > 1:
            raise CliArgError("verify", "複数の対象が異なるworkspaceに属しています")
        target_ws_id = next(iter(qualified_prefixes))
        if requested_workspace is not None and requested_workspace != target_ws_id:
            raise CliArgError("verify", f"対象のworkspaceと--workspaceが一致しません: {target_ws_id}")
        multi_pre = multiws.precheck(cwd, git, env)
        if multi_pre.ok:
            if target_ws_id == multi_pre.root_id:
                loc = WorkspaceLocation(
                    root=multi_pre.repo_root, config_path=os.path.join(multi_pre.repo_root, ".spec", "bitz.yaml")
                )
                workspace_path = "."
            else:
                member = next((m for m in multi_pre.members if m.id == target_ws_id), None)
                if member is not None:
                    loc = WorkspaceLocation(
                        root=member.root, config_path=os.path.join(member.root, ".spec", "bitz.yaml")
                    )
                    workspace_path = member.path

    outcome: config_mod.ConfigOutcome | None = None
    if loc.config_path is not None:
        outcome = config_mod.read_config(loc.config_path)

    if requested_workspace is not None:
        effective_id = outcome.workspace_id if outcome is not None else None
        if effective_id != requested_workspace:
            raise CliArgError("verify", f"指定したworkspaceが見つかりません: {requested_workspace}")

    def _empty(workspace_id, status: str, diagnostics: list[dict]) -> tuple[dict, int]:
        result = {
            "schemaVersion": "1.0",
            "operation": "verify",
            "status": status,
            "scope": scope,
            "workspace": {"id": workspace_id, "path": workspace_path},
            "targetResults": [],
            "revision": None,
            "commands": [],
            "durationMs": max(0, time.monotonic_ns() // 1_000_000 - started),
            "diagnostics": sort_diagnostics(diagnostics),
        }
        return result, EXIT_CODE_BY_STATUS[status]

    if loc.config_path is None:
        return _empty(
            None,
            "blocked",
            [
                _env_diag(
                    "SPEC-WORKSPACE-MISSING-001", "error", "blocked", ".spec/bitz.yamlがありません", "workspace", "."
                )
            ],
        )

    assert outcome is not None
    workspace_id = outcome.workspace_id
    if outcome.stop:
        diags = [d.to_dict() for d in outcome.diagnostics] + [d.to_dict() for d in outcome.warnings]
        status = worst_status([d["resultStatus"] for d in diags]) if diags else "error"
        return _empty(workspace_id, status, diags)

    config_raw = outcome.config
    assert loc.root is not None
    workspace_root = loc.root

    revision = None
    if git.available and git.executable:
        head_commit = gitutil.resolve_commit(git.executable, cwd, env, "HEAD")
        if head_commit is not None:
            revision = {"commit": head_commit, "dirty": gitutil.is_dirty(git.executable, cwd, env)}

    multi_active = multi_pre is not None and multi_pre.ok

    catalog = document_mod.build_catalog(workspace_root, workspace_id)
    if multi_active:
        assert multi_pre is not None
        (
            id_index,
            statement_index,
            local_id_indices,
            local_stmt_indices,
            known_ws_ids,
        ) = multirelate.build_multi_context(workspace_id, catalog.entries, multi_pre, keep_body=True)
        ws_root_by_id = {wid: root for wid, root, _rel in multiws.ordered_workspaces(multi_pre)}
        ws_path_by_id = {wid: relpath for wid, _root, relpath in multiws.ordered_workspaces(multi_pre)}
    else:
        id_index = relations_mod.build_id_index(catalog.entries)
        statement_index = relations_mod.build_statement_index(catalog.entries)
        local_id_indices = {workspace_id: id_index}
        local_stmt_indices = {workspace_id: statement_index}
        known_ws_ids = {workspace_id}
        ws_root_by_id = {workspace_id: workspace_root}
        ws_path_by_id = {workspace_id: "."}

    def _config_for(wid: str) -> dict:
        if wid == workspace_id:
            return config_raw
        cache = _config_for.__dict__.setdefault("_cache", {})
        if wid in cache:
            return cache[wid]
        cfg: dict = {}
        if multi_pre is not None:
            for w, root, _rel in multiws.ordered_workspaces(multi_pre):
                if w == wid:
                    cfg_outcome = config_mod.read_config(os.path.join(root, ".spec", "bitz.yaml"))
                    cfg = cfg_outcome.config or {}
                    break
        cache[wid] = cfg
        return cfg

    path_index = (
        {e.path: e.doc_id for e in catalog.entries if e.doc_id is not None}
        if multi_active
        else {e.path: e.doc_id for e in id_index.values()}
    )

    verify_cfg = config_raw.get("verify") or {}
    default_timeout = verify_cfg.get("timeoutSeconds", 300)
    effective_timeout = default_timeout
    if cli_timeout is not None:
        effective_timeout = min(int(cli_timeout), default_timeout)

    resolved_commands = config_raw.get("_resolvedCommands") or {}

    def _resolved_commands_for(wid: str) -> dict:
        if not multi_active or wid == workspace_id:
            return resolved_commands
        return _config_for(wid).get("_resolvedCommands") or {}

    def _effective_timeout_for(wid: str) -> int:
        if not multi_active or wid == workspace_id:
            return effective_timeout
        cfg = _config_for(wid).get("verify") or {}
        ws_default = cfg.get("timeoutSeconds", 300)
        return min(int(cli_timeout), ws_default) if cli_timeout is not None else ws_default

    # --- 対象解決（verify.md §3） ------------------------------------------
    if parsed.positionals:
        pending: list[tuple[str, str | None, str]] = []
        seen_keys: set[str] = set()
        for raw in parsed.positionals:
            root_id = _resolve_target(
                raw, id_index, statement_index, path_index, active_ws_id=(workspace_id if multi_active else None)
            )
            key = context_mod._canon(root_id, workspace_id) if (root_id is not None and multi_active) else (root_id if root_id is not None else raw)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            pending.append((key, root_id, raw))
        pending.sort(key=lambda item: item[0])
    else:
        pending = [(doc_id, doc_id, doc_id) for doc_id in _default_roots(id_index)]

    if not pending:
        diag = _invocation_diag("SPEC-VERIFY-BLOCKED-002", "error", "blocked", messages.VERIFY_TARGETS_EMPTY)
        return _empty(workspace_id, "blocked", [diag])

    top_diagnostics: list[dict] = []
    target_entries: list[dict] = []
    needs: dict[tuple[str, str], dict] = {}

    for key, root_id, raw in pending:
        def digest_fn(exp, _root_id=root_id):
            return _compute_verify_digest(
                _root_id, exp, id_index, statement_index, workspace_id, workspace_path, config_raw, resolved_commands,
                multi_active=multi_active, config_for=(_config_for if multi_active else None),
                ws_path_by_id=(ws_path_by_id if multi_active else None),
            )

        entry_out, needed_pairs = _process_single_target(
            key, root_id, raw,
            id_index=id_index, statement_index=statement_index, workspace_id=workspace_id,
            known_ws_ids=known_ws_ids, catalog_entries=catalog.entries,
            local_id_indices=local_id_indices, local_stmt_indices=local_stmt_indices,
            multi_active=multi_active, invalid_by_ws=None,
            digest_fn=digest_fn, resolved_commands_for=_resolved_commands_for,
        )
        target_entries.append(entry_out)
        for ws_id, name, path, cover in needed_pairs:
            bucket = needs.setdefault((ws_id, name), {"tests": set(), "covers": set()})
            bucket["tests"].add(path)
            bucket["covers"].add(cover)

    commands_by_key, status_by_key, blocked_keys, binding_top_diags = _plan_and_run_bindings(
        needs, ws_root_by_id=ws_root_by_id, resolved_commands_for=_resolved_commands_for,
        git=git, env=env, effective_timeout_for=_effective_timeout_for,
    )
    top_diagnostics.extend(binding_top_diags)
    _apply_binding_results(target_entries, blocked_keys, status_by_key)

    commands_out = [commands_by_key[k] for k in sorted(commands_by_key)]

    diagnostics = sort_diagnostics(top_diagnostics)
    all_statuses = [d["resultStatus"] for d in diagnostics] + [t["status"] for t in target_entries]
    status = worst_status(all_statuses)

    result = {
        "schemaVersion": "1.0",
        "operation": "verify",
        "status": status,
        "scope": scope,
        "workspace": {"id": workspace_id, "path": workspace_path},
        "targetResults": target_entries,
        "revision": revision,
        "commands": commands_out,
        "durationMs": max(0, time.monotonic_ns() // 1_000_000 - started),
        "diagnostics": diagnostics,
    }

    if want_report:
        failure = reportio.write_report(workspace_root, workspace_id, "verify", result)
        if failure is not None:
            new_diags = list(result["diagnostics"])
            new_diags.append(failure.to_dict())
            result["diagnostics"] = sort_diagnostics(new_diags)
            status = worst_status([d["resultStatus"] for d in result["diagnostics"]] + [t["status"] for t in target_entries])
            result["status"] = status

    return result, EXIT_CODE_BY_STATUS[status]


def _run_all_workspaces(parsed: ParsedArgs, cwd: str, env: dict[str, str]) -> tuple[dict, int]:
    """`verify --all-workspaces`（`複合workspace仕様 §8`、`03_操作仕様/03_verify.md §10`）。"""

    started = time.monotonic_ns() // 1_000_000
    git = gitutil.detect_git(cwd, env)

    revision: dict | None = None
    if git.available and git.executable:
        head_commit = gitutil.resolve_commit(git.executable, cwd, env, "HEAD")
        if head_commit is not None:
            revision = {"commit": head_commit, "dirty": gitutil.is_dirty(git.executable, cwd, env)}

    # `commandDefinitionCount`は全体事前検査から除外し、`verifyBindingCount`優先の判定を
    # `_run_all_workspaces_members`自身のbinding計画集計に委ねる（複合workspace仕様 §10）。
    pre = multiws.precheck(cwd, git, env, skip_limit_dimensions=frozenset({"commandDefinitionCount"}))
    if pre.discovery_failed:
        raise CliArgError("verify", "複合workspaceのroot設定を発見できません")

    if not pre.ok:
        diagnostics = sort_diagnostics([d.to_dict() for d in pre.diagnostics])
        status = status_from_diagnostics(diagnostics)
        result: dict = {
            "schemaVersion": "1.0",
            "operation": "verify",
            "status": status,
            "scope": "all-workspaces",
            "multiWorkspace": {"id": pre.root_id, "path": "."},
            "workspaces": [],
            "revision": revision,
            "durationMs": max(0, time.monotonic_ns() // 1_000_000 - started),
            "diagnostics": diagnostics,
        }
        return result, EXIT_CODE_BY_STATUS[status]

    return _run_all_workspaces_members(parsed, cwd, env, git, pre, revision, started)


def _run_all_workspaces_members(
    parsed: ParsedArgs,
    cwd: str,
    env: dict[str, str],
    git: gitutil.GitInfo,
    pre: multiws.PrecheckResult,
    revision: dict | None,
    started: int,
) -> tuple[dict, int]:
    want_report = "--report" in parsed.flags
    cli_timeout = parsed.single.get("--timeout")
    cli_cap = int(cli_timeout) if cli_timeout is not None else None

    workspaces = multiws.ordered_workspaces(pre)
    ws_root_by_id = {wid: root for wid, root, _rel in workspaces}
    ws_path_by_id = {wid: relpath for wid, _root, relpath in workspaces}

    config_by_ws: dict[str, dict] = {}
    for wid, root, _rel in workspaces:
        if wid == pre.root_id:
            root_outcome = config_mod.read_config(os.path.join(root, ".spec", "bitz.yaml"))
            config_by_ws[wid] = root_outcome.config or {}
        else:
            member = next(m for m in pre.members if m.id == wid)
            config_by_ws[wid] = member.config

    def _resolved_commands_for(wid: str) -> dict:
        return config_by_ws[wid].get("_resolvedCommands") or {}

    def _effective_timeout_for(wid: str) -> int:
        cfg = config_by_ws[wid].get("verify") or {}
        ws_default = cfg.get("timeoutSeconds", 300)
        return min(cli_cap, ws_default) if cli_cap is not None else ws_default

    per_ws_catalog: dict[str, document_mod.CatalogResult] = {}
    for wid, root, _rel in workspaces:
        per_ws_catalog[wid] = document_mod.build_catalog(root, wid)

    entries_by_ws = {wid: cat.entries for wid, cat in per_ws_catalog.items()}
    invalid_by_ws = {
        wid: {e.doc_id for e in cat.entries if e.hard is not None and e.doc_id is not None}
        for wid, cat in per_ws_catalog.items()
    }

    top_diagnostics: list[dict] = []
    per_ws_target_entries: dict[str, list[dict]] = {wid: [] for wid, _, _ in workspaces}
    per_ws_extra_diags: dict[str, list[dict]] = {wid: [] for wid, _, _ in workspaces}
    needs: dict[tuple[str, str], dict] = {}
    any_targets = False
    limit_diag: dict | None = None

    for wid, root, _rel in workspaces:
        id_index, statement_index, local_id_indices, local_stmt_indices, known_ws_ids = multirelate.merge_indices(
            wid, entries_by_ws
        )
        catalog = per_ws_catalog[wid]
        default_roots = _default_roots_all(catalog.entries, local_id_indices[wid])
        if not default_roots:
            per_ws_extra_diags[wid].append(
                _file_diag(
                    "SPEC-VERIFY-BLOCKED-002", "warning", "passed_with_warnings", messages.MULTI_VERIFY_TARGETS_EMPTY,
                    wid, config_mod.CONFIG_PATH,
                )
            )
            continue
        any_targets = True
        config_raw = config_by_ws[wid]
        resolved_commands = _resolved_commands_for(wid)

        for root_key in default_roots:
            local_entry = local_id_indices[wid].get(root_key)
            qualified_key = f"{wid}::{root_key}"
            if local_entry is None:
                hard_entry = next(e for e in catalog.entries if e.doc_id == root_key)
                per_ws_target_entries[wid].append(_hard_entry_target_result(hard_entry, qualified_key))
                continue

            def digest_fn(exp, _root_id=root_key, _wid=wid, _cfg=config_raw, _cmds=resolved_commands):
                return _compute_verify_digest(
                    _root_id, exp, id_index, statement_index, _wid, ws_path_by_id[_wid], _cfg, _cmds,
                    multi_active=True, config_for=lambda w: config_by_ws[w], ws_path_by_id=ws_path_by_id,
                )

            entry_out, needed_pairs = _process_single_target(
                qualified_key, root_key, qualified_key,
                id_index=id_index, statement_index=statement_index, workspace_id=wid,
                known_ws_ids=known_ws_ids, catalog_entries=catalog.entries,
                local_id_indices=local_id_indices, local_stmt_indices=local_stmt_indices,
                multi_active=True, invalid_by_ws=invalid_by_ws,
                digest_fn=digest_fn, resolved_commands_for=_resolved_commands_for,
            )
            per_ws_target_entries[wid].append(entry_out)
            for cws, name, path, cover in needed_pairs:
                bucket = needs.setdefault((cws, name), {"tests": set(), "covers": set()})
                bucket["tests"].add(path)
                bucket["covers"].add(cover)

    binding_count = len(needs)
    if binding_count > _VERIFY_BINDING_LIMIT:
        limit_diag = _file_diag(
            "SPEC-MULTI-LIMIT-001", "error", "blocked",
            messages.multi_limit_exceeded("verifyBindingCount", _VERIFY_BINDING_LIMIT),
            pre.root_id, config_mod.CONFIG_PATH,
        )
        limit_diag["evidence"] = {"dimension": "verifyBindingCount", "limit": _VERIFY_BINDING_LIMIT, "observedAtLeast": binding_count}
    else:
        # `commandDefinitionCount`は全体事前検査から除外している（`skip_limit_dimensions`）ため、
        # ここで実行計画確定後に自分で判定する。verifyBindingCountが超過していなければ、
        # commandDefinitionCount単独の超過をここで遮断する（複合workspace仕様 §10「両方が同時に
        # 超過する場合は…verifyBindingCountを優先」の裏を返せば、verifyBindingCountが超過しない
        # 限りcommandDefinitionCountの超過はそのまま報告する）。command を1件も起動する前
        # （`_plan_and_run_bindings`より前）に判定する。
        command_definition_count = _total_command_definition_count(config_by_ws, workspaces)
        limit = multiws.HARD_LIMITS["commandDefinitionCount"]
        if command_definition_count > limit:
            limit_diag = _file_diag(
                "SPEC-MULTI-LIMIT-001", "error", "blocked",
                messages.multi_limit_exceeded("commandDefinitionCount", limit),
                pre.root_id, config_mod.CONFIG_PATH,
            )
            limit_diag["evidence"] = {
                "dimension": "commandDefinitionCount", "limit": limit, "observedAtLeast": command_definition_count,
            }

    if limit_diag is not None:
        diagnostics = sort_diagnostics([limit_diag])
        status = status_from_diagnostics(diagnostics)
        result = {
            "schemaVersion": "1.0",
            "operation": "verify",
            "status": status,
            "scope": "all-workspaces",
            "multiWorkspace": {"id": pre.root_id, "path": "."},
            "workspaces": [],
            "revision": revision,
            "durationMs": max(0, time.monotonic_ns() // 1_000_000 - started),
            "diagnostics": diagnostics,
        }
        return result, EXIT_CODE_BY_STATUS[status]

    if not any_targets:
        top_diagnostics.append(
            _file_diag(
                "SPEC-VERIFY-BLOCKED-002", "error", "blocked", messages.MULTI_VERIFY_TARGETS_EMPTY,
                pre.root_id, config_mod.CONFIG_PATH,
            )
        )

    commands_by_key, status_by_key, blocked_keys, binding_top_diags = _plan_and_run_bindings(
        needs, ws_root_by_id=ws_root_by_id, resolved_commands_for=_resolved_commands_for,
        git=git, env=env, effective_timeout_for=_effective_timeout_for,
    )
    top_diagnostics.extend(binding_top_diags)

    all_target_entries = [e for wid, _, _ in workspaces for e in per_ws_target_entries[wid]]
    _apply_binding_results(all_target_entries, blocked_keys, status_by_key)

    per_ws_commands: dict[str, list[dict]] = {wid: [] for wid, _, _ in workspaces}
    for (ws_id, name), cmd in commands_by_key.items():
        per_ws_commands[ws_id].append(cmd)
    for wid in per_ws_commands:
        per_ws_commands[wid].sort(key=lambda c: c["name"])

    ws_results = []
    for wid, root, relpath in workspaces:
        target_results = sorted(per_ws_target_entries[wid], key=lambda t: t["target"])
        commands_list = per_ws_commands[wid]
        diags = sort_diagnostics(per_ws_extra_diags[wid])
        ws_status = worst_status(
            [t["status"] for t in target_results] + [c["status"] for c in commands_list] + [d["resultStatus"] for d in diags]
        )
        ws_results.append(
            {
                "id": wid,
                "path": relpath,
                "status": ws_status,
                "targetResults": target_results,
                "commands": commands_list,
                "durationMs": 0,
                "diagnostics": diags,
            }
        )

    top_diagnostics_sorted = sort_diagnostics(top_diagnostics)
    overall_status = worst_status([w["status"] for w in ws_results] + [status_from_diagnostics(top_diagnostics_sorted)])

    result = {
        "schemaVersion": "1.0",
        "operation": "verify",
        "status": overall_status,
        "scope": "all-workspaces",
        "multiWorkspace": {"id": pre.root_id, "path": "."},
        "workspaces": ws_results,
        "revision": revision,
        "durationMs": max(0, time.monotonic_ns() // 1_000_000 - started),
        "diagnostics": top_diagnostics_sorted,
    }

    if want_report:
        failure = reportio.write_report(pre.repo_root, pre.root_id, "verify", result)
        if failure is not None:
            diags2 = list(result["diagnostics"])
            diags2.append(failure.to_dict())
            result["diagnostics"] = sort_diagnostics(diags2)
            overall_status = worst_status([w["status"] for w in ws_results] + [status_from_diagnostics(diags2)])
            result["status"] = overall_status

    return result, EXIT_CODE_BY_STATUS[overall_status]
