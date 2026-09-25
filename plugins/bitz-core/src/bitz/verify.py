"""`bitz verify` 操作（`03_操作仕様/03_verify.md`）。

Step 4範囲: 単一workspaceだけを扱う（`--all-workspaces`と複合workspaceはStep 5）。
`TargetExpansion(root, verify)`（`targetexpand.py`）を唯一の展開契約として再利用し、targetごとに
Contextを解決してtest対応を確認し、`bitz.yaml`のcommandをshellを介さず実行する。
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
from . import procrun
from . import relations as relations_mod
from . import reportio
from . import targetexpand
from .cliargs import ParsedArgs
from .document import DocEntry
from .errors import CliArgError
from .notimpl import NotImplementedOperation
from .resultmodel import EXIT_CODE_BY_STATUS, sort_diagnostics, worst_status
from .workspace import locate_workspace

_ARGV_ELEMENT_LIMIT = 32 * 1024
_ARGV_TOTAL_LIMIT = 1024 * 1024
_ARGV_COUNT_LIMIT = 10000


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
    target: str, id_index: dict[str, DocEntry], statement_index: dict[str, dict], path_index: dict[str, str]
) -> str | None:
    """明示targetを正規IDへ解決する。statement IDはstatement IDのまま返す（statement粒度を保つ）。"""

    if target in id_index:
        return target
    if target in statement_index:
        return target
    return path_index.get(target)


def _default_roots(id_index: dict[str, DocEntry]) -> list[str]:
    roots = []
    for doc_id, entry in id_index.items():
        if entry.kind == "REQ" and entry.status == "approved":
            roots.append(doc_id)
        elif entry.kind == "TECH" and entry.status == "approved":
            if entry.statements or (entry.frontmatter.get("tests") or []):
                roots.append(doc_id)
    return sorted(roots)


def _compute_verify_digest(
    root_id: str,
    expansion: targetexpand.TargetExpansionResult,
    id_index: dict[str, DocEntry],
    statement_index: dict[str, dict],
    workspace_id: str,
    config_raw: dict,
    resolved_commands: dict,
) -> str:
    context_documents = expansion.context_documents
    body_texts = {
        doc_id: digest_mod.normalize_body_text(id_index[doc_id].body or "") for doc_id in context_documents
    }
    norm_frontmatters = {doc_id: context_mod._normalize_frontmatter(id_index[doc_id]) for doc_id in context_documents}

    referenced_commands: set[str] = set()
    for doc_id in context_documents:
        for t in id_index[doc_id].frontmatter.get("tests") or []:
            name = t.get("command")
            if name:
                referenced_commands.add(name)

    commands_settings = []
    for name in sorted(referenced_commands):
        resolved = resolved_commands.get(name)
        if resolved is None:
            continue
        commands_settings.append(
            {"workspaceId": workspace_id, "name": name, "argv": list(resolved["argv"]), "cwd": resolved.get("cwd", ".")}
        )

    has_binding = any((id_index[d].frontmatter.get("tests") or []) for d in context_documents)
    ctx_cfg = config_raw.get("context") or {}
    verify_cfg = config_raw.get("verify") or {}

    digest_materials = {
        "digestVersion": digest_mod.DIGEST_VERSION,
        "specSchemaVersion": str(config_raw.get("schemaVersion", "1.0")),
        "earsAiVersion": str(config_raw.get("earsAi", "1.0")),
        "resolverVersion": digest_mod.RESOLVER_VERSION,
        "purpose": "verify",
        "requestWorkspaceId": workspace_id,
        "roots": [root_id],
        "workspaces": [{"id": workspace_id, "path": "."}],
        "documents": [
            {
                "id": doc_id,
                "workspaceId": workspace_id,
                "kind": context_mod._KIND_LABEL[id_index[doc_id].kind],
                "status": id_index[doc_id].status,
                "applicability": "applicable",
                "frontmatter": norm_frontmatters[doc_id],
                "bodyText": body_texts[doc_id],
                "statements": [context_mod._digest_statement(s) for s in id_index[doc_id].statements],
                "strongRelations": context_mod._strong_relations(id_index[doc_id], id_index, statement_index),
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
            "context": {
                "maxDocuments": ctx_cfg.get("maxDocuments", context_mod.DEFAULT_MAX_DOCUMENTS),
                "maxBytes": ctx_cfg.get("maxBytes", context_mod.DEFAULT_MAX_BYTES),
            },
            "verifyTimeouts": (
                [{"workspaceId": workspace_id, "timeoutSeconds": verify_cfg.get("timeoutSeconds", context_mod.DEFAULT_VERIFY_TIMEOUT)}]
                if has_binding
                else []
            ),
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


def run(parsed: ParsedArgs, cwd: str, env: dict[str, str]) -> tuple[dict, int]:
    started = time.monotonic_ns() // 1_000_000

    if "--all-workspaces" in parsed.flags:
        raise NotImplementedOperation("verify --all-workspaces: Step 5で実装する")

    want_report = "--report" in parsed.flags
    cli_timeout = parsed.single.get("--timeout")
    scope = "selected" if parsed.positionals else "all"

    git = gitutil.detect_git(cwd, env)
    loc = locate_workspace(cwd, git, env)
    requested_workspace = parsed.single.get("--workspace")

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
            "workspace": {"id": workspace_id, "path": "."},
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

    catalog = document_mod.build_catalog(workspace_root, workspace_id)
    id_index = relations_mod.build_id_index(catalog.entries)
    statement_index = relations_mod.build_statement_index(catalog.entries)
    path_index = {e.path: e.doc_id for e in id_index.values()}

    verify_cfg = config_raw.get("verify") or {}
    default_timeout = verify_cfg.get("timeoutSeconds", 300)
    effective_timeout = default_timeout
    if cli_timeout is not None:
        effective_timeout = min(int(cli_timeout), default_timeout)

    resolved_commands = config_raw.get("_resolvedCommands") or {}

    # --- 対象解決（verify.md §3） ------------------------------------------
    if parsed.positionals:
        pending: list[tuple[str, str | None, str]] = []
        seen_keys: set[str] = set()
        for raw in parsed.positionals:
            root_id = _resolve_target(raw, id_index, statement_index, path_index)
            key = root_id if root_id is not None else raw
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
    # binding需要: command名 -> {"tests": set[path], "covers": set[str]}
    needs: dict[str, dict] = {}

    for key, root_id, raw in pending:
        entry_out: dict = {
            "target": key,
            "status": "passed",
            "contextDigest": None,
            "statements": [],
            "bindingRefs": [],
            "diagnostics": [],
        }
        needed_pairs: list[tuple[str, str, str]] = []
        target_entries.append(entry_out)

        if root_id is None:
            d = _invocation_diag("CTX-ROOT-MISSING-001", "error", "failed", messages.root_missing_explicit(raw), raw)
            entry_out["diagnostics"] = [d]
            entry_out["status"] = "failed"
            continue

        expansion = targetexpand.target_expansion(root_id, "verify", id_index, statement_index)
        if expansion is None:
            d = _invocation_diag("CTX-ROOT-MISSING-001", "error", "failed", messages.root_missing_explicit(raw), raw)
            entry_out["diagnostics"] = [d]
            entry_out["status"] = "failed"
            continue

        if expansion.errors:
            diags = []
            for err in expansion.errors:
                if err.get("doc_id") is None:
                    diags.append(
                        _invocation_diag(err["code"], err["severity"], err["resultStatus"], err["summary"], err.get("root_arg", raw))
                    )
                else:
                    doc_path = id_index[err["doc_id"]].path
                    diags.append(
                        _file_diag(
                            err["code"], err["severity"], err["resultStatus"], err["summary"], workspace_id, doc_path,
                            key=err.get("key"),
                        )
                    )
            entry_out["diagnostics"] = sort_diagnostics(diags)
            entry_out["status"] = worst_status([d["resultStatus"] for d in diags])
            continue

        context_documents = expansion.context_documents
        relation_diags_raw = relations_mod.check_relations(catalog.entries, workspace_id, source_ids=set(context_documents))
        relation_error_diags = [d.to_dict() for d in relation_diags_raw if d.severity == "error"]
        if relation_error_diags:
            entry_out["diagnostics"] = sort_diagnostics(relation_error_diags)
            entry_out["status"] = worst_status([d["resultStatus"] for d in relation_error_diags])
            continue

        target_statements = expansion.target_statements

        def _covering_tests(cover_id: str) -> list[tuple[DocEntry, int, dict]]:
            out = []
            for doc_id in context_documents:
                doc_entry = id_index[doc_id]
                for idx, t in enumerate(doc_entry.frontmatter.get("tests") or []):
                    if cover_id in (t.get("covers") or []):
                        out.append((doc_entry, idx, t))
            return out

        must_untested = []
        should_untested = []
        for stmt_id in target_statements:
            modality = statement_index[stmt_id]["modality"]
            if _covering_tests(stmt_id):
                continue
            if modality == "MUST":
                must_untested.append(stmt_id)
            elif modality == "SHOULD":
                should_untested.append(stmt_id)

        coverage_diags = []
        for stmt_id in must_untested:
            doc_id = statement_index[stmt_id]["documentId"]
            coverage_diags.append(
                _file_diag(
                    "CTX-COVERAGE-TEST-001", "error", "blocked", messages.verify_coverage_untested("MUST", stmt_id),
                    workspace_id, id_index[doc_id].path,
                )
            )
        for stmt_id in should_untested:
            doc_id = statement_index[stmt_id]["documentId"]
            coverage_diags.append(
                _file_diag(
                    "CTX-COVERAGE-TEST-001", "warning", "passed_with_warnings",
                    messages.verify_coverage_untested("SHOULD", stmt_id), workspace_id, id_index[doc_id].path,
                )
            )

        context_digest = _compute_verify_digest(
            root_id, expansion, id_index, statement_index, workspace_id, config_raw, resolved_commands
        )
        entry_out["contextDigest"] = context_digest
        entry_out["statements"] = list(target_statements)

        if must_untested:
            entry_out["diagnostics"] = sort_diagnostics(coverage_diags)
            entry_out["status"] = "blocked"
            continue

        # --- binding候補の決定（関係・トレースモデル §6.4「規範文なしTECHは文書単位bindingを保持」） ---
        cover_ids: list[str]
        if target_statements:
            cover_ids = list(target_statements)
        elif id_index[root_id].kind == "TECH" and not id_index[root_id].statements:
            cover_ids = [root_id]
        else:
            cover_ids = []

        # skip-target継続単位: 1 targetにつきbinding不足の原因は最初の1件だけ報告し、
        # それ以上のtest対応の解決は試みない（`SINGLE-061`。Diagnostic registry §2「同一原因から
        # 同義Diagnosticを複数生成しない」と同じ趣旨をtarget単位へ適用する）。
        binding_missing_diag: dict | None = None
        for cover_id in cover_ids:
            if binding_missing_diag is not None:
                break
            for doc_entry, idx, t in _covering_tests(cover_id):
                name = t.get("command") or doc_entry.frontmatter.get("verify")
                if not name or name not in resolved_commands:
                    label = name if name else "(未指定)"
                    binding_missing_diag = _file_diag(
                        "SPEC-VERIFY-BLOCKED-001", "error", "blocked", messages.verify_command_undefined(label),
                        workspace_id, doc_entry.path, key=f"tests[{idx}].command",
                    )
                    break
                needed_pairs.append((name, t["path"], cover_id))

        if binding_missing_diag is not None:
            entry_out["diagnostics"] = [binding_missing_diag]
            entry_out["status"] = "blocked"
            entry_out["bindingRefs"] = []
            # binding計画を確定できないtargetはContextを構成できたとしてもDigestを返さない
            # （`SINGLE-061`が審査済みの正）。
            entry_out["contextDigest"] = None
            continue

        for name, path, cover_id in needed_pairs:
            bucket = needs.setdefault(name, {"tests": set(), "covers": set()})
            bucket["tests"].add(path)
            bucket["covers"].add(cover_id)

        entry_out["bindingRefs"] = sorted({f"{workspace_id}::{name}" for name, _p, _c in needed_pairs})
        entry_out["_needed_names"] = sorted({name for name, _p, _c in needed_pairs})
        if should_untested:
            entry_out["diagnostics"] = sort_diagnostics(coverage_diags)
            entry_out["status"] = "passed_with_warnings"

    # --- binding事前検査（spawn前blocked。verify.md §5.1・§6） -------------------
    plan: dict[str, dict] = {}
    binding_blocked: dict[str, dict] = {}

    config_untracked = False
    if needs and git.available and git.executable:
        config_untracked = not gitutil.is_config_tracked(git.executable, workspace_root, env, config_mod.CONFIG_PATH)

    for name in sorted(needs):
        cmd_def = resolved_commands.get(name)
        bucket = needs[name]
        tests_sorted = sorted(bucket["tests"])
        covers_sorted = sorted(bucket["covers"])
        if cmd_def is None:
            continue

        cmd_cwd_rel = cmd_def.get("cwd", ".")
        cwd_abs = (
            cmd_cwd_rel if os.path.isabs(cmd_cwd_rel) else os.path.normpath(os.path.join(workspace_root, cmd_cwd_rel))
        )

        diag: dict | None = None
        if config_untracked:
            diag = _file_diag(
                "SPEC-VERIFY-BLOCKED-001", "error", "blocked", messages.VERIFY_CONFIG_UNTRACKED,
                workspace_id, config_mod.CONFIG_PATH,
            )
        elif not os.path.isdir(cwd_abs):
            diag = _file_diag(
                "SPEC-VERIFY-BLOCKED-001", "error", "blocked", messages.verify_cwd_unavailable(),
                workspace_id, config_mod.CONFIG_PATH, key=f"verify.commands.{name}.cwd",
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
                    workspace_id, config_mod.CONFIG_PATH, key=f"verify.commands.{name}.cwd",
                )
            else:
                argv_template = cmd_def["argv"]
                expanded = _expand_argv(argv_template, tests_sorted, cwd_abs, workspace_root)
                total_bytes = sum(len(a.encode("utf-8")) for a in expanded)
                if len(expanded) > _ARGV_COUNT_LIMIT:
                    diag = _file_diag(
                        "SPEC-VERIFY-BLOCKED-001", "error", "blocked", messages.verify_argv_expanded_count_limit(),
                        workspace_id, config_mod.CONFIG_PATH, key=f"verify.commands.{name}.argv",
                    )
                elif any(len(a.encode("utf-8")) > _ARGV_ELEMENT_LIMIT for a in expanded):
                    diag = _file_diag(
                        "SPEC-VERIFY-BLOCKED-001", "error", "blocked", messages.VERIFY_ARGV_EXPANDED_LIMIT,
                        workspace_id, config_mod.CONFIG_PATH, key=f"verify.commands.{name}.argv",
                    )
                elif total_bytes > _ARGV_TOTAL_LIMIT:
                    diag = _file_diag(
                        "SPEC-VERIFY-BLOCKED-001", "error", "blocked", messages.VERIFY_ARGV_EXPANDED_LIMIT,
                        workspace_id, config_mod.CONFIG_PATH, key=f"verify.commands.{name}.argv",
                    )
                else:
                    resolved_exec = execfile.resolve_executable(argv_template[0], cwd_abs, env)
                    if resolved_exec is None:
                        summary = (
                            messages.VERIFY_EXECUTABLE_UNAVAILABLE
                            if "/" not in argv_template[0]
                            else messages.verify_executable_unavailable_path()
                        )
                        diag = _env_diag(
                            "SPEC-VERIFY-BLOCKED-001", "error", "blocked", summary, "command", f"{workspace_id}::{name}"
                        )

        if diag is not None:
            binding_blocked[name] = diag
            top_diagnostics.append(diag)
            continue

        plan[name] = {
            "argv": expanded,
            "cwd_rel": cmd_cwd_rel,
            "cwd_abs": cwd_abs,
            "tests": tests_sorted,
            "covers": covers_sorted,
        }

    for entry_out in target_entries:
        needed_names = entry_out.pop("_needed_names", None)
        if not needed_names:
            continue
        blocked_names = {n for n in needed_names if n in binding_blocked}
        if blocked_names:
            entry_out["status"] = worst_status([entry_out["status"], "blocked"])
            entry_out["bindingRefs"] = sorted(
                ref for ref in entry_out["bindingRefs"] if ref.split("::", 1)[1] not in blocked_names
            )

    # --- binding実行（verify.md §5・§6） -----------------------------------
    commands_out: list[dict] = []
    command_status_by_name: dict[str, str] = {}
    for name in sorted(plan):
        info = plan[name]
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
            top_diagnostics.append(_env_diag(code, "error", "error", summary, "command", f"{workspace_id}::{name}"))
        command_status_by_name[name] = status

        stdout_excerpt = outcome_run["stdout_excerpt"]
        stderr_excerpt = outcome_run["stderr_excerpt"]
        stdout_truncated = outcome_run["stdout_truncated"]
        stderr_truncated = outcome_run["stderr_truncated"]

        commands_out.append(
            {
                "bindingId": f"{workspace_id}::{name}",
                "workspaceId": workspace_id,
                "name": name,
                "status": status,
                "termination": termination,
                "cwd": info["cwd_rel"],
                "argv": info["argv"],
                "tests": info["tests"],
                "covers": info["covers"],
                "exitCode": exit_code,
                "timeoutSeconds": effective_timeout,
                "stdoutExcerpt": stdout_excerpt,
                "stderrExcerpt": stderr_excerpt,
                "stdoutTruncated": stdout_truncated,
                "stderrTruncated": stderr_truncated,
                "durationMs": outcome_run["duration_ms"],
            }
        )

    for entry_out in target_entries:
        statuses = [entry_out["status"]]
        for ref in entry_out["bindingRefs"]:
            name = ref.split("::", 1)[1]
            if name in command_status_by_name:
                statuses.append(command_status_by_name[name])
        entry_out["status"] = worst_status(statuses)

    diagnostics = sort_diagnostics(top_diagnostics)
    all_statuses = [d["resultStatus"] for d in diagnostics] + [t["status"] for t in target_entries]
    status = worst_status(all_statuses)

    result = {
        "schemaVersion": "1.0",
        "operation": "verify",
        "status": status,
        "scope": scope,
        "workspace": {"id": workspace_id, "path": "."},
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
