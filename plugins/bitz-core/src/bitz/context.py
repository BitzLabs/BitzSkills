"""`bitz context`操作（`03_操作仕様/01_context.md`）。

Step 3 Phase 3Bで実装する。単一workspaceだけを対象とする（複合workspaceはStep 5）。
`TargetExpansion(root, purpose)`（`targetexpand.py`）を唯一の閉包契約として再利用し、
Context Bundle（Manifest、Constraint Ledger、coverage、Context Digest、projection）を
組み立てる。
"""

from __future__ import annotations

import time

from . import config as config_mod
from . import digest as digest_mod
from . import document as document_mod
from . import gitutil
from . import messages
from . import relations as relations_mod
from . import targetexpand
from .cliargs import ParsedArgs
from .document import DocEntry
from .errors import CliArgError
from .resultmodel import EXIT_CODE_BY_STATUS, sort_diagnostics, status_from_diagnostics
from .workspace import locate_workspace

_KIND_RANK = {"REQ": 0, "TECH": 1, "ADR": 2, "TASK": 3}
_KIND_LABEL = {"REQ": "requirement", "TECH": "technical", "ADR": "decision", "TASK": "task"}

DEFAULT_MAX_DOCUMENTS = 20
DEFAULT_MAX_BYTES = 131072
HARD_MAX_DOCUMENTS = 100
HARD_MAX_BYTES = 1024 * 1024
PROJECTION_HARD_LIMIT_BYTES = 1024 * 1024
DEFAULT_VERIFY_TIMEOUT = 300


def _null_first(value):
    return (0, "") if value is None else (1, value)


def _normalize_frontmatter(entry: DocEntry) -> dict:
    """§3.1.1: `frontmatter`の完全正規化（全8key既定値付き）。単一workspaceのためqualifyは恒等。

    Digest正規化仕様 §2「3.文字正規化を適用する → 4.重複排除とsortを正規化後の値へ適用する」の
    順序を守る。NFC・path区切り変換より前にsorted(set(...))を行うと、正規化により初めて同一に
    なる値（例: NFC合成前後で異なるbyte列の同じ文字）が別要素のまま残ってしまう。
    """

    nfc = digest_mod.nfc
    fm = entry.frontmatter or {}
    relations_raw = fm.get("relations") or {}
    relations: dict[str, list[str]] = {}
    for key in digest_mod.RELATION_KEY_ORDER:
        vals = [nfc(v) for v in (relations_raw.get(key) or [])]
        relations[key] = sorted(set(vals))

    implements = sorted({digest_mod.to_slash(nfc(p)) for p in (fm.get("implements") or [])})
    changes = sorted({digest_mod.to_slash(nfc(p)) for p in (fm.get("changes") or [])})

    tests_raw = fm.get("tests") or []
    tests: list[dict] = []
    for t in tests_raw:
        path = digest_mod.to_slash(nfc(t.get("path")))
        covers = sorted({nfc(c) for c in (t.get("covers") or [])})
        command_raw = t.get("command")
        command = nfc(command_raw) if command_raw is not None else None
        tests.append({"path": path, "covers": covers, "command": command})
    tests.sort(key=lambda t: (t["path"], _null_first(t["command"]), tuple(t["covers"])))

    verify_raw = fm.get("verify")
    verify = nfc(verify_raw) if isinstance(verify_raw, str) else verify_raw
    title_raw = fm.get("title")
    title = nfc(title_raw) if isinstance(title_raw, str) else title_raw

    return {
        "id": nfc(entry.doc_id),
        "title": title,
        "status": entry.status,
        "relations": relations,
        "implements": implements,
        "tests": tests,
        "verify": verify,
        "changes": changes,
    }


def _bundle_frontmatter(norm: dict) -> dict:
    """§5: Bundle `documents[].frontmatter`。既定値（空配列・null）は省略する。"""

    out: dict = {"id": norm["id"], "title": norm["title"], "status": norm["status"]}
    rel_pruned = {k: v for k, v in norm["relations"].items() if v}
    if rel_pruned:
        out["relations"] = rel_pruned
    if norm["implements"]:
        out["implements"] = norm["implements"]
    if norm["tests"]:
        pruned_tests = []
        for t in norm["tests"]:
            pt = {"path": t["path"], "covers": t["covers"]}
            if t["command"] is not None:
                pt["command"] = t["command"]
            pruned_tests.append(pt)
        out["tests"] = pruned_tests
    if norm["verify"] is not None:
        out["verify"] = norm["verify"]
    if norm["changes"]:
        out["changes"] = norm["changes"]
    return out


def _digest_activation(d: dict) -> dict:
    text = d.get("text")
    if isinstance(text, str):
        text = digest_mod.nfc(text)
    return {"kind": d["kind"], "text": text}


def _bundle_activation(d: dict) -> dict:
    out = {"kind": d["kind"]}
    if d.get("text") is not None:
        out["text"] = d["text"]
    return out


def _digest_extensions(exts: list[dict]) -> list[dict]:
    nfc = digest_mod.nfc
    out = []
    for e in exts:
        value = e.get("value")
        if isinstance(value, str):
            value = nfc(value)
        out.append({"namespace": nfc(e["namespace"]), "term": nfc(e["term"]), "value": value})
    out.sort(key=lambda e: (e["namespace"], e["term"], _null_first(e["value"])))
    return out


def _digest_statement(stmt: dict) -> dict:
    nfc = digest_mod.nfc
    reason = stmt.get("reason")
    return {
        "id": nfc(stmt["id"]),
        "actor": nfc(stmt["actor"]),
        "activation": _digest_activation(stmt["activation"]),
        "modality": stmt["modality"],
        "reason": nfc(reason) if isinstance(reason, str) else reason,
        "operation": _digest_activation(stmt["operation"]),
        "extensions": _digest_extensions(stmt.get("extensions") or []),
    }


def _strong_relations(entry: DocEntry, id_index: dict[str, DocEntry], statement_index: dict[str, dict]) -> list[dict]:
    nfc = digest_mod.nfc
    out: set[tuple[str, str]] = set()
    relations_raw = (entry.frontmatter or {}).get("relations") or {}
    for relation in ("requires", "refines", "addresses", "supersedes"):
        for ref in relations_raw.get(relation) or []:
            target_entry, _target_doc_id = relations_mod.resolve_ref(ref, id_index, statement_index)
            if target_entry is not None:
                out.add((relation, nfc(ref)))
    return [{"relation": r, "target": t} for r, t in sorted(out)]


def _invocation_diag(code: str, severity: str, status: str, summary: str, argument: str) -> dict:
    return {
        "code": code,
        "severity": severity,
        "resultStatus": status,
        "summary": summary,
        "source": {"kind": "invocation", "argument": argument},
    }


def _file_diag(code: str, severity: str, status: str, summary: str, workspace_id, path: str, *, key: str | None = None) -> dict:
    src: dict = {"kind": "file", "workspaceId": workspace_id, "path": path}
    if key is not None:
        src["key"] = key
    return {"code": code, "severity": severity, "resultStatus": status, "summary": summary, "source": src}


def _empty_bundle(purpose: str, detail: str, workspace_id, workspace_path: str, roots: list[str]) -> dict:
    empty_bucket = {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []}
    return {
        "schemaVersion": "1.0",
        "operation": "context",
        "status": "passed",
        "purpose": purpose,
        "workspace": {"id": workspace_id, "path": workspace_path},
        "roots": roots,
        "contextDigest": None,
        "revision": None,
        "resolution": {"complete": False, "documentCount": 0, "unresolvedStrongRelations": 0},
        "projection": {"detail": detail, "expanded": []},
        "documents": [],
        "constraintLedger": {"statements": []},
        "coverage": {
            "must": dict(empty_bucket),
            "should": dict(empty_bucket),
            "may": dict(empty_bucket),
            "adjacent": [],
        },
        "durationMs": 0,
        "diagnostics": [],
    }


def _resolve_command(name: str | None, config_raw: dict) -> dict | None:
    if name is None:
        return None
    resolved = (config_raw.get("_resolvedCommands") or {}).get(name)
    return resolved


def _merge_expansions(
    expansions: list, id_index: dict[str, DocEntry], statement_index: dict[str, dict]
):
    """複数起点の`TargetExpansionResult`を和集合へ統合する（関係・トレースモデル §6.4末尾）。

    重複排除後の各結果を統合し、`targetStatements`／`adjacentStatements`は
    `contextDocuments`順（距離・種別順REQ/TECH/ADR/TASK・ID辞書順）、source line、ID順で
    同じ順序規則を再適用する。1起点だけの呼び出しでも同じ経路を通る。
    """

    root_documents: set[str] = set()
    context_documents: set[str] = set()
    document_edges: dict[str, list[tuple[str, str]]] = {}
    document_distance: dict[str, int] = {}
    draft_advisory: set[str] = set()
    target_statements_set: set[str] = set()
    target_statements: list[str] = []
    adjacent_statements_set: set[str] = set()
    adjacent_statements: list[str] = []
    superseded_origin = None

    for exp in expansions:
        root_documents.update(exp.root_documents)
        context_documents.update(exp.context_documents)
        for doc_id, edges in exp.document_edges.items():
            bucket = document_edges.setdefault(doc_id, [])
            for e in edges:
                if e not in bucket:
                    bucket.append(e)
        for doc_id, dist in exp.document_distance.items():
            if doc_id not in document_distance or dist < document_distance[doc_id]:
                document_distance[doc_id] = dist
        draft_advisory |= exp.draft_advisory
        for s in exp.target_statements:
            if s not in target_statements_set:
                target_statements_set.add(s)
                target_statements.append(s)
        if len(expansions) == 1 and exp.superseded_origin is not None:
            superseded_origin = exp.superseded_origin

    for exp in expansions:
        for s in exp.adjacent_statements:
            if s in target_statements_set or s in adjacent_statements_set:
                continue
            adjacent_statements_set.add(s)
            adjacent_statements.append(s)

    def _sort_key(stmt_id: str):
        stmt = statement_index[stmt_id]
        doc_id = stmt["documentId"]
        dist = document_distance.get(doc_id, 0)
        kind_rank = _KIND_RANK[id_index[doc_id].kind]
        line = stmt.get("source", {}).get("line", 0)
        return (dist, kind_rank, doc_id, line, stmt_id)

    target_statements.sort(key=_sort_key)
    adjacent_statements.sort(key=_sort_key)

    merged = targetexpand.TargetExpansionResult(
        root_documents=sorted(root_documents),
        context_documents=sorted(context_documents),
        target_statements=target_statements,
        adjacent_statements=adjacent_statements,
        document_edges=document_edges,
        document_distance=document_distance,
        draft_advisory=draft_advisory,
        superseded_origin=superseded_origin,
    )
    return merged


def run(parsed: ParsedArgs, cwd: str, env: dict[str, str]) -> tuple[dict, int]:
    started = time.monotonic_ns() // 1_000_000
    purpose = parsed.single.get("--purpose", "interpret")
    detail = parsed.single.get("--detail", "standard")
    expand_ids = sorted({digest_mod.nfc(e) for e in parsed.repeat.get("--expand", [])})
    expect_digest = parsed.single.get("--expect-digest")
    roots_raw = sorted({digest_mod.nfc(p) for p in parsed.positionals})

    git = gitutil.detect_git(cwd, env)
    loc = locate_workspace(cwd, git, env)
    requested_workspace = parsed.single.get("--workspace")

    outcome: config_mod.ConfigOutcome | None = None
    if loc.config_path is not None:
        outcome = config_mod.read_config(loc.config_path)

    if requested_workspace is not None:
        effective_id = outcome.workspace_id if outcome is not None else None
        if effective_id != requested_workspace:
            raise CliArgError("context", f"指定したworkspaceが見つかりません: {requested_workspace}")

    workspace_id = outcome.workspace_id if outcome is not None else "root"
    workspace_path = "."

    if loc.config_path is None or outcome is None or outcome.stop or outcome.config is None:
        bundle = _empty_bundle(purpose, detail, workspace_id, workspace_path, roots_raw)
        bundle["status"] = "blocked"
        bundle["diagnostics"] = [
            _file_diag(
                "SPEC-WORKSPACE-MISSING-001",
                "error",
                "blocked",
                ".spec/bitz.yamlがありません",
                workspace_id,
                ".spec/bitz.yaml",
            )
        ]
        bundle["durationMs"] = max(0, time.monotonic_ns() // 1_000_000 - started)
        return bundle, EXIT_CODE_BY_STATUS["blocked"]

    config_raw = outcome.config
    assert loc.root is not None

    revision: dict | None = None
    if git.available and git.executable:
        head_commit = gitutil.resolve_commit(git.executable, cwd, env, "HEAD")
        if head_commit is not None:
            revision = {"commit": head_commit, "dirty": gitutil.is_dirty(git.executable, cwd, env)}

    catalog = document_mod.build_catalog(loc.root, workspace_id)
    id_index = relations_mod.build_id_index(catalog.entries)
    statement_index = relations_mod.build_statement_index(catalog.entries)

    # --- 起点解決 ---------------------------------------------------------
    missing = [r for r in roots_raw if r not in id_index and r not in statement_index]
    if missing:
        bundle = _empty_bundle(purpose, detail, workspace_id, workspace_path, roots_raw)
        bundle["status"] = "failed"
        bundle["diagnostics"] = [
            _invocation_diag(
                "CTX-ROOT-MISSING-001", "error", "failed", messages.root_missing_explicit(m), m
            )
            for m in missing
        ]
        bundle["durationMs"] = max(0, time.monotonic_ns() // 1_000_000 - started)
        return bundle, EXIT_CODE_BY_STATUS["failed"]

    # 複数起点: 各起点でTargetExpansionを実行し、正規ID重複排除後の和集合を同じ順序規則で
    # 再構成する（context.md §2「複数起点は重複排除して正規ID辞書順に正規化」、
    # 関係・トレースモデル §6.4末尾「起点を正規ID化して重複排除した後に各結果の和集合を取り、
    # 同じ順序規則を再適用する」）。
    expansions: list[targetexpand.TargetExpansionResult] = []
    all_errors: list[dict] = []
    for r in roots_raw:
        exp = targetexpand.target_expansion(r, purpose, id_index, statement_index)
        if exp is None:
            # `missing`で存在確認済みのため通常到達しないが、念のため同じcodeで扱う。
            all_errors.append(
                {
                    "code": "CTX-ROOT-MISSING-001",
                    "severity": "error",
                    "resultStatus": "failed",
                    "summary": messages.root_missing_explicit(r),
                    "doc_id": None,
                    "root_arg": r,
                }
            )
            continue
        expansions.append(exp)
        all_errors.extend(exp.errors)

    if all_errors:
        diags = []
        for err in all_errors:
            if err.get("doc_id") is None:
                diags.append(
                    _invocation_diag(
                        err["code"], err["severity"], err["resultStatus"], err["summary"], err.get("root_arg", "")
                    )
                )
            else:
                doc_path = id_index[err["doc_id"]].path
                diags.append(
                    _file_diag(
                        err["code"], err["severity"], err["resultStatus"], err["summary"], workspace_id, doc_path,
                        key=err.get("key"),
                    )
                )
        worst = status_from_diagnostics(diags)
        bundle = _empty_bundle(purpose, detail, workspace_id, workspace_path, roots_raw)
        bundle["status"] = worst
        bundle["diagnostics"] = sort_diagnostics(diags)
        bundle["durationMs"] = max(0, time.monotonic_ns() // 1_000_000 - started)
        return bundle, EXIT_CODE_BY_STATUS[worst]

    expansion = _merge_expansions(expansions, id_index, statement_index)
    context_documents = expansion.context_documents

    # --- 強い関係の解決検査（context.md §3「ID、型、状態、強い関係、循環を検査する」）。
    # 閉包内文書が宣言する強い関係のうち解決できないものが1件でもあれば、部分Bundleを
    # 成功結果として返さない（同 §3末尾）。
    relation_diags_raw = relations_mod.check_relations(
        catalog.entries, workspace_id, source_ids=set(context_documents)
    )
    relation_error_diags = [d for d in relation_diags_raw if d.severity == "error"]
    if relation_error_diags:
        diags = [d.to_dict() for d in relation_error_diags]
        worst = status_from_diagnostics(diags)
        bundle = _empty_bundle(purpose, detail, workspace_id, workspace_path, roots_raw)
        bundle["status"] = worst
        bundle["diagnostics"] = sort_diagnostics(diags)
        unresolved_count = len(
            [d for d in relation_error_diags if d.code in ("SPEC-RELATION-MISSING-001", "CTX-RELATION-TYPE-001")]
        )
        bundle["resolution"]["unresolvedStrongRelations"] = unresolved_count
        bundle["durationMs"] = max(0, time.monotonic_ns() // 1_000_000 - started)
        return bundle, EXIT_CODE_BY_STATUS[worst]

    body_texts: dict[str, str] = {
        doc_id: digest_mod.normalize_body_text(id_index[doc_id].body or "") for doc_id in context_documents
    }

    # --- role割当て（§7） ----------------------------------------------------
    root_id_set = set(expansion.root_documents)
    superseded_origin_id, superseded_successor_id = (
        expansion.superseded_origin if expansion.superseded_origin is not None else (None, None)
    )
    roles: dict[str, str] = {}
    for doc_id in context_documents:
        entry = id_index[doc_id]
        if doc_id == superseded_origin_id:
            # §6.1「5.」: 置換済み起点はroleをrootからadvisoryへ差し替える。
            roles[doc_id] = "advisory"
        elif doc_id == superseded_successor_id:
            roles[doc_id] = "replacement"
        elif doc_id in root_id_set:
            roles[doc_id] = "root"
        elif doc_id in expansion.draft_advisory:
            roles[doc_id] = "advisory"
        elif entry.kind == "TASK":
            roles[doc_id] = "work"
        else:
            edge_relations = {rel for rel, _src in expansion.document_edges.get(doc_id, [])}
            if "refines" in edge_relations:
                roles[doc_id] = "refinement"
            elif entry.kind == "REQ":
                roles[doc_id] = "requirement"
            else:
                roles[doc_id] = "constraint"

    def _projection_for(doc_id: str, use_detail: str) -> str:
        if use_detail == "full":
            return "full"
        if use_detail == "compact":
            return "reference"
        role = roles[doc_id]
        if role == "advisory":
            return "reference"
        if role in ("root", "work", "replacement"):
            return "full"
        if expansion.document_distance.get(doc_id, 0) <= 1:
            return "full"
        if role in ("refinement", "constraint"):
            return "normative"
        return "full"

    # --- 上限検査（§8）。閉包規模はdetail=standardでの提示量（既定・設定に依存しない基準）で測る。 ---
    ctx_cfg = config_raw.get("context") or {}
    max_documents = min(ctx_cfg.get("maxDocuments", DEFAULT_MAX_DOCUMENTS), HARD_MAX_DOCUMENTS)
    max_bytes = min(ctx_cfg.get("maxBytes", DEFAULT_MAX_BYTES), HARD_MAX_BYTES)

    standard_bytes = sum(
        len(body_texts[d].encode("utf-8")) for d in context_documents if _projection_for(d, "standard") == "full"
    )

    if len(context_documents) > max_documents or standard_bytes > max_bytes:
        summary = messages.CTX_LIMIT_DOCUMENTS if len(context_documents) > max_documents else messages.CTX_LIMIT_BYTES
        root_path = id_index[expansion.root_documents[0]].path
        bundle = _empty_bundle(purpose, detail, workspace_id, workspace_path, roots_raw)
        bundle["status"] = "blocked"
        bundle["diagnostics"] = [
            _file_diag("CTX-LIMIT-001", "error", "blocked", summary, workspace_id, root_path)
        ]
        bundle["durationMs"] = max(0, time.monotonic_ns() // 1_000_000 - started)
        return bundle, EXIT_CODE_BY_STATUS["blocked"]

    # --- Constraint Ledger、coverage（§6.4、関係・トレースモデル §8） ----------------
    ledger_statements = []
    for stmt_id in expansion.target_statements:
        stmt = statement_index[stmt_id]
        ledger_statements.append(
            {
                "id": stmt["id"],
                "documentId": stmt["documentId"],
                "documentRole": roles.get(stmt["documentId"], "root"),
                "modality": stmt["modality"],
                "reason": stmt.get("reason"),
                "actor": stmt["actor"],
                "activation": _bundle_activation(stmt["activation"]),
                "operation": _bundle_activation(stmt["operation"]),
            }
        )

    def _bucket(modality: str) -> dict:
        total = [s for s in expansion.target_statements if statement_index[s]["modality"] == modality]
        addressed_set: set[str] = set()
        for doc_id in context_documents:
            entry = id_index[doc_id]
            if entry.kind != "TASK":
                continue
            for ref in (entry.frontmatter.get("relations") or {}).get("addresses") or []:
                if ref in total:
                    addressed_set.add(ref)
        tested_set: set[str] = set()
        for doc_id in context_documents:
            entry = id_index[doc_id]
            for t in (entry.frontmatter.get("tests") or []):
                for c in (t.get("covers") or []):
                    if c in total:
                        tested_set.add(c)
        addressed = [s for s in total if s in addressed_set]
        tested = [s for s in total if s in tested_set]
        unaddressed = [s for s in total if s not in addressed_set]
        untested = [s for s in total if s not in tested_set]
        return {"total": total, "addressed": addressed, "tested": tested, "unaddressed": unaddressed, "untested": untested}

    coverage = {
        "must": _bucket("MUST"),
        "should": _bucket("SHOULD"),
        "may": _bucket("MAY"),
        "adjacent": list(expansion.adjacent_statements),
    }

    def _stmt_source(stmt_id: str) -> dict:
        doc_id = statement_index[stmt_id]["documentId"]
        return {"kind": "file", "workspaceId": workspace_id, "path": id_index[doc_id].path}

    coverage_diags: list[dict] = []
    if purpose == "implement":
        for modality_key, modality_label in (("must", "MUST"), ("should", "SHOULD")):
            for stmt_id in coverage[modality_key]["unaddressed"]:
                coverage_diags.append(
                    {
                        "code": "CTX-COVERAGE-TASK-001",
                        "severity": "warning",
                        "resultStatus": "passed_with_warnings",
                        "summary": messages.coverage_task_unaddressed(modality_label, stmt_id),
                        "source": _stmt_source(stmt_id),
                    }
                )
        for stmt_id in coverage["must"]["untested"]:
            coverage_diags.append(
                {
                    "code": "CTX-COVERAGE-TEST-001",
                    "severity": "warning",
                    "resultStatus": "passed_with_warnings",
                    "summary": messages.coverage_test_untested("MUST", stmt_id),
                    "source": _stmt_source(stmt_id),
                }
            )
        for stmt_id in coverage["should"]["untested"]:
            coverage_diags.append(
                {
                    "code": "CTX-COVERAGE-TEST-001",
                    "severity": "warning",
                    "resultStatus": "passed_with_warnings",
                    "summary": messages.coverage_test_untested("SHOULD", stmt_id),
                    "source": _stmt_source(stmt_id),
                }
            )
    elif purpose == "verify":
        for stmt_id in coverage["must"]["untested"]:
            coverage_diags.append(
                {
                    "code": "CTX-COVERAGE-TEST-001",
                    "severity": "error",
                    "resultStatus": "blocked",
                    "summary": messages.coverage_test_untested("MUST", stmt_id),
                    "source": _stmt_source(stmt_id),
                }
            )
        for stmt_id in coverage["should"]["untested"]:
            coverage_diags.append(
                {
                    "code": "CTX-COVERAGE-TEST-001",
                    "severity": "warning",
                    "resultStatus": "passed_with_warnings",
                    "summary": messages.coverage_test_untested("SHOULD", stmt_id),
                    "source": _stmt_source(stmt_id),
                }
            )

    # --- catalog Diagnostic（EARS-AI等）: context文書のものだけを含める -----------------
    catalog_diags: list[dict] = []
    for doc_id in context_documents:
        entry = id_index[doc_id]
        for w in entry.warnings:
            catalog_diags.append(w.to_dict())

    all_diags = sort_diagnostics(catalog_diags + coverage_diags)
    status = status_from_diagnostics(all_diags)

    # --- Digest materials（§3） -----------------------------------------------
    norm_frontmatters = {doc_id: _normalize_frontmatter(id_index[doc_id]) for doc_id in context_documents}

    # commands／verifyTimeoutsは`verify`のBundleだけが参照する（実行に使う実効設定であり、
    # interpret／implementはtestを実行しないため含めない）。
    verify_cfg = config_raw.get("verify") or {}
    timeout_seconds = verify_cfg.get("timeoutSeconds", DEFAULT_VERIFY_TIMEOUT)
    has_binding = purpose == "verify" and any(
        (id_index[d].frontmatter.get("tests") or []) for d in context_documents
    )

    referenced_commands: set[str] = set()
    if purpose == "verify":
        for doc_id in context_documents:
            for t in id_index[doc_id].frontmatter.get("tests") or []:
                name = t.get("command")
                if name:
                    referenced_commands.add(name)

    commands_settings = []
    for name in sorted(referenced_commands):
        resolved = _resolve_command(name, config_raw)
        if resolved is None:
            continue
        commands_settings.append(
            {
                "workspaceId": workspace_id,
                "name": name,
                "argv": list(resolved["argv"]),
                "cwd": resolved.get("cwd", "."),
            }
        )

    digest_materials = {
        "digestVersion": digest_mod.DIGEST_VERSION,
        "specSchemaVersion": str(config_raw.get("schemaVersion", "1.0")),
        "earsAiVersion": str(config_raw.get("earsAi", "1.0")),
        "resolverVersion": digest_mod.RESOLVER_VERSION,
        "purpose": purpose,
        "requestWorkspaceId": workspace_id,
        "roots": roots_raw,
        "workspaces": [{"id": workspace_id, "path": "."}],
        "documents": [
            {
                "id": doc_id,
                "workspaceId": workspace_id,
                "kind": _KIND_LABEL[id_index[doc_id].kind],
                "status": id_index[doc_id].status,
                "applicability": roles.get(doc_id) if roles.get(doc_id) in ("advisory", "replacement") else "applicable",
                "frontmatter": norm_frontmatters[doc_id],
                "bodyText": body_texts[doc_id],
                "statements": [_digest_statement(s) for s in id_index[doc_id].statements],
                "strongRelations": _strong_relations(id_index[doc_id], id_index, statement_index),
            }
            for doc_id in sorted(context_documents)
        ],
        "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [
                {
                    "id": workspace_id,
                    "schemaVersion": str(config_raw.get("schemaVersion", "1.0")),
                    "earsAi": str(config_raw.get("earsAi", "1.0")),
                    "language": str(config_raw.get("language", "en")),
                }
            ],
            "context": {"maxDocuments": ctx_cfg.get("maxDocuments", DEFAULT_MAX_DOCUMENTS), "maxBytes": ctx_cfg.get("maxBytes", DEFAULT_MAX_BYTES)},
            "verifyTimeouts": [{"workspaceId": workspace_id, "timeoutSeconds": timeout_seconds}] if has_binding else [],
            "commands": commands_settings,
        },
    }
    context_digest = digest_mod.compute_digest(digest_materials)

    documents_sorted = sorted(
        context_documents,
        key=lambda d: (expansion.document_distance.get(d, 0), _KIND_RANK[id_index[d].kind], d),
    )

    # --- projection割当て（§5） ------------------------------------------------
    projections = {doc_id: _projection_for(doc_id, detail) for doc_id in context_documents}

    bad_expand = [e for e in expand_ids if e not in set(context_documents)]
    if bad_expand:
        bundle = _empty_bundle(purpose, detail, workspace_id, workspace_path, roots_raw)
        bundle["status"] = "failed"
        bundle["contextDigest"] = context_digest
        bundle["resolution"] = {
            "complete": True,
            "documentCount": len(context_documents),
            "unresolvedStrongRelations": 0,
        }
        bundle["diagnostics"] = [
            _invocation_diag(
                "CTX-PROJECTION-001", "error", "failed", messages.projection_outside(e), e
            )
            for e in bad_expand
        ]
        bundle["durationMs"] = max(0, time.monotonic_ns() // 1_000_000 - started)
        return bundle, EXIT_CODE_BY_STATUS["failed"]

    for e in expand_ids:
        projections[e] = "full"

    presented_bytes = sum(
        len(body_texts[d].encode("utf-8")) for d in context_documents if projections[d] == "full"
    )
    if presented_bytes > PROJECTION_HARD_LIMIT_BYTES:
        bundle = _empty_bundle(purpose, detail, workspace_id, workspace_path, roots_raw)
        bundle["status"] = "failed"
        bundle["contextDigest"] = context_digest
        bundle["resolution"] = {
            "complete": True,
            "documentCount": len(context_documents),
            "unresolvedStrongRelations": 0,
        }
        bundle["diagnostics"] = [
            _invocation_diag(
                "CTX-PROJECTION-LIMIT-001", "error", "failed", messages.projection_limit_exceeded(detail), "--detail"
            )
        ]
        bundle["durationMs"] = max(0, time.monotonic_ns() // 1_000_000 - started)
        return bundle, EXIT_CODE_BY_STATUS["failed"]

    if expect_digest is not None and expect_digest != context_digest:
        bundle = _empty_bundle(purpose, detail, workspace_id, workspace_path, roots_raw)
        bundle["status"] = "blocked"
        bundle["contextDigest"] = context_digest
        bundle["resolution"] = {
            "complete": True,
            "documentCount": len(context_documents),
            "unresolvedStrongRelations": 0,
        }
        bundle["diagnostics"] = [
            _invocation_diag(
                "CTX-STALE-001", "error", "blocked", messages.CTX_STALE_MISMATCH, "--expect-digest"
            )
        ]
        bundle["durationMs"] = max(0, time.monotonic_ns() // 1_000_000 - started)
        return bundle, EXIT_CODE_BY_STATUS["blocked"]

    # --- documents[]組み立て -----------------------------------------------
    documents_out = []
    for doc_id in documents_sorted:
        entry = id_index[doc_id]
        projection = projections[doc_id]
        if doc_id in root_id_set:
            reached_by = ["root"]
        else:
            reached_by = sorted({f"{rel}:{src}" for rel, src in expansion.document_edges.get(doc_id, [])})
        doc_out: dict = {
            "id": doc_id,
            "kind": _KIND_LABEL[entry.kind],
            "status": entry.status,
            "role": roles[doc_id],
            "path": entry.path,
            "projection": projection,
            "reachedBy": reached_by,
        }
        if projection in ("full", "normative"):
            doc_out["statementRefs"] = [s["id"] for s in entry.statements]
        if projection == "full":
            doc_out["frontmatter"] = _bundle_frontmatter(norm_frontmatters[doc_id])
            doc_out["bodyText"] = body_texts[doc_id]
        if projection == "reference":
            doc_out["expandable"] = True
        doc_out["untrustedText"] = True
        documents_out.append(doc_out)

    result: dict = {
        "schemaVersion": "1.0",
        "operation": "context",
        "status": status,
        "purpose": purpose,
        "workspace": {"id": workspace_id, "path": workspace_path},
        "roots": roots_raw,
        "contextDigest": context_digest,
        "revision": revision,
        "resolution": {
            "complete": True,
            "documentCount": len(context_documents),
            "unresolvedStrongRelations": 0,
        },
        "projection": {"detail": detail, "expanded": expand_ids},
        "documents": documents_out,
        "constraintLedger": {"statements": ledger_statements},
        "coverage": coverage,
        "durationMs": max(0, time.monotonic_ns() // 1_000_000 - started),
        "diagnostics": all_diags,
    }
    return result, EXIT_CODE_BY_STATUS[status]
