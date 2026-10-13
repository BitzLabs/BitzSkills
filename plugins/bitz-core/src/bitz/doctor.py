"""`bitz doctor`操作（`03_操作仕様/04_doctor.md`）。

単一ワークスペースと複合ワークスペースで、設定・バージョン・コマンドの診断の処理を共有する。
"""

from __future__ import annotations

import os
import sys

from . import activews
from . import config as config_mod
from . import execfile
from . import gitutil
from . import messages
from . import multiws
from .cliargs import ParsedArgs, api_version_key, parse_core_api_range
from .errors import CliArgError
from .resultmodel import doctor_status, sort_diagnostics, worst_status
from .workspace import WorkspaceLocation, locate_workspace

CORE_VERSION = "1.0.0"
CORE_API_VERSION = "1.0"
CORE_CAPABILITIES = ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"]

_GIT_LOST_GUARANTEES = [
    "approved-diff-protection",
    "deletion-detection",
    "status-transition",
    "task-boundary",
]


_COMPARATORS = {
    ">=": lambda a, b: a >= b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    "<": lambda a, b: a < b,
    "=": lambda a, b: a == b,
}


def _core_api_satisfies(required: str) -> bool:
    """Core APIのバージョンが範囲のすべての比較子を満たすか。(MAJOR, MINOR)の数値の組で比べる。"""
    comparators = parse_core_api_range(required)
    assert comparators is not None  # 字句は`parse_doctor`で検査済み
    core = api_version_key(*CORE_API_VERSION.split("."))
    return all(_COMPARATORS[op](core, version) for op, version in comparators)


def _plugin_request_checks(parsed: ParsedArgs) -> tuple[list[dict], list[dict]]:
    """検査2（`plugin`）と検査3（`capability`）。`doctor.md` §3・§4.1、ADR-061。

    4種のオプションのどれも指定しなければ、検査項目も診断も置かない。ワークスペースや
    Gitの状態に依存せず、後続の検査の失敗とも独立に行う。
    """
    plugin = parsed.single.get("--plugin")
    plugin_version = parsed.single.get("--plugin-version")
    core_api = parsed.single.get("--require-core-api")
    capabilities = parsed.repeat.get("--require-capability", [])
    if plugin is None and plugin_version is None and core_api is None and not capabilities:
        return [], []

    source: dict = {"kind": "environment", "component": "plugin"}
    if plugin is not None:
        source["identifier"] = plugin

    given = {"--plugin": plugin, "--plugin-version": plugin_version, "--require-core-api": core_api}
    missing_options = sorted(name for name, value in given.items() if value is None)
    if missing_options:
        return [{"name": "plugin", "status": "failed"}], [{
            "code": "SPEC-DOCTOR-PLUGIN-001",
            "severity": "error",
            "resultStatus": "failed",
            "summary": messages.DOCTOR_PLUGIN_REQUEST_INCOMPLETE,
            "source": source,
            "evidence": {"missing": missing_options},
            "suggestedAction": messages.DOCTOR_PLUGIN_REQUEST_ACTION,
        }]

    assert core_api is not None
    checks: list[dict] = []
    diagnostics: list[dict] = []
    if _core_api_satisfies(core_api):
        checks.append({"name": "plugin", "status": "passed"})
    else:
        checks.append({"name": "plugin", "status": "blocked"})
        diagnostics.append({
            "code": "SPEC-DOCTOR-API-001",
            "severity": "error",
            "resultStatus": "blocked",
            "summary": messages.DOCTOR_API_INCOMPATIBLE,
            "source": dict(source),
            "evidence": {"coreApi": CORE_API_VERSION, "required": core_api},
            "suggestedAction": messages.doctor_api_incompatible_action(core_api, CORE_API_VERSION),
        })

    missing_capabilities = sorted(name for name in set(capabilities) if name not in CORE_CAPABILITIES)
    if missing_capabilities:
        checks.append({"name": "capability", "status": "blocked"})
        diagnostics.append({
            "code": "SPEC-DOCTOR-CAPABILITY-001",
            "severity": "error",
            "resultStatus": "blocked",
            "summary": messages.DOCTOR_CAPABILITY_MISSING,
            "source": dict(source),
            "evidence": {"missing": missing_capabilities},
            "suggestedAction": messages.doctor_capability_missing_action(missing_capabilities),
        })
    else:
        checks.append({"name": "capability", "status": "passed"})
    return checks, diagnostics


def _workspace_missing_diagnostic() -> dict:
    return {
        "code": "SPEC-DOCTOR-WORKSPACE-001",
        "severity": "error",
        "resultStatus": "blocked",
        "summary": ".spec/bitz.yamlがありません",
        "source": {"kind": "environment", "component": "workspace", "identifier": "."},
        "suggestedAction": (
            ".spec/bitz.yamlを次の内容で作成してください:\n"
            'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
            ".gitignoreへ.spec/reports/を追加し、bitz check --fullを実行してください"
        ),
    }


def _config_check_status(outcome: config_mod.ConfigOutcome) -> str:
    """設定の検査項目`config`（`doctor.md` §3検査5）の状態。

    停止する診断の結果への効果（`error`または`failed`）で決まり、停止なしで警告
    （BOM、未知のキー、`profiles`）だけがあれば`warning`、どちらもなければ`passed`とする。
    `checks[].status`の語彙は`passed_with_warnings`を持たないため、ここでは
    警告だけの場合を、`doctor`の検査項目の語彙`warning`へ写像する。
    """
    if outcome.stop_stage == "config":
        return worst_status([d.resultStatus for d in outcome.diagnostics])
    if outcome.warnings:
        return "warning"
    return "passed"


def _append_git_check(git: gitutil.GitInfo | None, checks: list[dict], diagnostics: list[dict]) -> None:
    # 全体操作ではGitの診断を最上位に1回だけ置く。
    if git is None:
        return
    if git.available:
        checks.append({"name": "git", "status": "passed"})
        return
    checks.append({"name": "git", "status": "warning", "lostGuarantees": list(_GIT_LOST_GUARANTEES)})
    diagnostics.append(
        {
            "code": "SPEC-DOCTOR-GIT-001",
            "severity": "warning",
            "resultStatus": "passed_with_warnings",
            "summary": "Git不在のため差分に依存する保証を提供できません",
            "source": {"kind": "environment", "component": "git", "identifier": "git"},
            "suggestedAction": messages.DOCTOR_GIT_DEGRADED_ACTION,
        }
    )


def _resolve_command_file(argv0: str, cwd: str, env: dict[str, str]) -> bool:
    return execfile.resolve_executable(argv0, cwd, env) is not None


def _run_all_workspaces(parsed: ParsedArgs, cwd: str, env: dict[str, str]) -> tuple[dict, int]:
    """全体事前検査を通過したルートワークスペースとすべてのメンバーを診断する（複合ワークスペース仕様 §8）。"""

    started = _now_ms()
    git = gitutil.detect_git(cwd, env)

    checks: list[dict] = []
    python_ok = sys.version_info[:2] >= (3, 12)
    checks.append({"name": "core", "status": "passed" if python_ok else "blocked"})
    # プラグインの要求の検査（検査2・3）は、Coreの検査項目の結果やワークスペースに依存しない。
    plugin_checks, plugin_diagnostics = _plugin_request_checks(parsed)
    checks.extend(plugin_checks)
    if not python_ok:
        diagnostics = [
            {
                "code": "SPEC-DOCTOR-CORE-001",
                "severity": "error",
                "resultStatus": "blocked",
                "summary": "実行環境のCPythonのバージョンが下限未満です",
                "source": {"kind": "environment", "component": "core"},
                "suggestedAction": messages.DOCTOR_RUNTIME_VERSION_ACTION,
            },
            *plugin_diagnostics,
        ]
        return _build_multi_result(None, checks, diagnostics, started)

    pre = multiws.precheck(cwd, git, env, extra_config_revs=["HEAD"], ears_version_code="SPEC-DOCTOR-EARS-001")
    if pre.discovery_failed:
        raise CliArgError("doctor", "複合ワークスペースのルートワークスペースの設定を発見できません")

    checks.append({"name": "git", "status": pre.git_status})
    if pre.catalog_status is not None:
        checks.append({"name": "catalog", "status": pre.catalog_status})

    diagnostics = [d.to_dict() for d in pre.diagnostics] + plugin_diagnostics
    workspaces = []
    if pre.ok:
        for wid, root, path in multiws.ordered_workspaces(pre):
            member_started = _now_ms()
            config_path = os.path.join(root, config_mod.CONFIG_PATH)
            outcome = config_mod.read_config(config_path, ears_version_code="SPEC-DOCTOR-EARS-001")
            local, _ = _diagnose_workspace(
                WorkspaceLocation(root, config_path), outcome, None, env, [], [], member_started
            )
            # 設定の読取りに失敗したときの既定のIDではなく、カタログで確定済みの所有者を使う。
            for diagnostic in local["diagnostics"]:
                if diagnostic["source"]["kind"] == "file":
                    diagnostic["source"]["workspaceId"] = wid
            # 事前検査の後に設定を読めなくなった場合も、別の検査項目の依存の失敗を明示する。
            if outcome.stop:
                completed = {check["name"] for check in local["checks"]}
                for name in ("schema", "ears", "command", "impact"):
                    if name in completed:
                        continue
                    local["checks"].append({"name": name, "status": "blocked"})
                    local["diagnostics"].append({
                        "code": "SPEC-MULTI-DEPENDENCY-001", "severity": "error", "resultStatus": "blocked",
                        "summary": f"検査項目{name}に必要な設定の出力を取得できません",
                        "evidence": {"stage": name, "dependencyWorkspaces": [wid], "dependencySpecRefs": []},
                        "source": {"kind": "file", "workspaceId": wid, "path": config_mod.CONFIG_PATH},
                    })
                local["diagnostics"] = sort_diagnostics(local["diagnostics"])
                local["status"] = doctor_status(local["checks"], local["diagnostics"])
            workspaces.append({
                "id": wid, "path": path, "status": local["status"], "checks": local["checks"],
                "durationMs": _elapsed_ms(member_started), "diagnostics": local["diagnostics"],
            })
    return _build_multi_result(pre.root_id, checks, diagnostics, started, workspaces)


def _build_multi_result(
    root_id: str | None, checks: list[dict], diagnostics: list[dict], started: int,
    workspaces: list[dict] | None = None,
) -> tuple[dict, int]:
    diagnostics = sort_diagnostics(diagnostics)
    workspaces = workspaces or []
    status = worst_status([doctor_status(checks, diagnostics), *[w["status"] for w in workspaces]])
    result = {
        "schemaVersion": "1.0",
        "operation": "doctor",
        "status": status,
        "multiWorkspace": {"id": root_id, "path": "."},
        "core": {
            "version": CORE_VERSION,
            "apiVersion": CORE_API_VERSION,
            "capabilities": list(CORE_CAPABILITIES),
        },
        "checks": checks,
        "workspaces": workspaces,
        "durationMs": _elapsed_ms(started),
        "diagnostics": diagnostics,
    }
    return result, _exit_code(status)


def run(parsed: ParsedArgs, cwd: str, env: dict[str, str]) -> tuple[dict, int]:
    if "--all-workspaces" in parsed.flags:
        return _run_all_workspaces(parsed, cwd, env)

    started = _now_ms()
    git = gitutil.detect_git(cwd, env)
    loc = locate_workspace(cwd, git, env)

    requested_workspace = parsed.single.get("--workspace")

    # 複合ワークスペースを宣言していれば、`--workspace`（ルートまたはメンバーのID）で作業ワークスペースを置き換える（複合ワークスペース仕様 §3の5）。
    sel = activews.select_active("doctor", [], requested_workspace, cwd, git, env, loc)
    loc = sel.loc
    workspace_path = sel.rel_path

    outcome: config_mod.ConfigOutcome | None = None
    if loc.config_path is not None:
        outcome = config_mod.read_config(loc.config_path, ears_version_code="SPEC-DOCTOR-EARS-001")

    if requested_workspace is not None:
        effective_id = outcome.workspace_id if outcome is not None else None
        if effective_id != requested_workspace:
            raise CliArgError("doctor", f"指定したワークスペースが見つかりません: {requested_workspace}")

    checks: list[dict] = []
    diagnostics: list[dict] = []

    # 1. core
    python_ok = sys.version_info[:2] >= (3, 12)
    checks.append({"name": "core", "status": "passed" if python_ok else "blocked"})
    # プラグインの要求の検査（検査2・3）は、Coreの検査項目の結果やワークスペースに依存しない。
    plugin_checks, plugin_diagnostics = _plugin_request_checks(parsed)
    checks.extend(plugin_checks)
    diagnostics.extend(plugin_diagnostics)
    if not python_ok:
        diagnostics.append(
            {
                "code": "SPEC-DOCTOR-CORE-001",
                "severity": "error",
                "resultStatus": "blocked",
                "summary": "実行環境のCPythonのバージョンが下限未満です",
                "source": {"kind": "environment", "component": "core"},
                "suggestedAction": messages.DOCTOR_RUNTIME_VERSION_ACTION,
            }
        )
        result = _build_result(None, checks, diagnostics, started)
        return result, _exit_code(result["status"])

    result, exit_code = _diagnose_workspace(
        loc, outcome, git, env, checks, diagnostics, started, catalog_status="passed" if sel.multi_active else None
    )
    # 複合ワークスペース内の単独操作の`workspace.path`は、リポジトリのルートからの相対パス（結果・診断・終了コード §2）。
    result["workspace"]["path"] = workspace_path
    return result, exit_code


def _diagnose_workspace(
    loc: WorkspaceLocation, outcome: config_mod.ConfigOutcome | None, git: gitutil.GitInfo | None,
    env: dict[str, str], checks: list[dict], diagnostics: list[dict], started: int,
    catalog_status: str | None = None,
) -> tuple[dict, int]:
    """ワークスペース固有の検査。全体操作ではGitの独立した検査を呼出し側へ任せる。

    ``catalog_status``は、複合ワークスペース内の単独操作で全体事前検査が成功したときの検査項目`catalog`
    （`doctor.md` §3検査6。検査5の`config`の後、検査7の`schema`の前）の状態。``None``なら置かない。
    """
    # 2. workspace
    workspace_found = loc.config_path is not None
    checks.append({"name": "workspace", "status": "passed" if workspace_found else "blocked"})
    if not workspace_found:
        diagnostics.append(_workspace_missing_diagnostic())
        _append_git_check(git, checks, diagnostics)
        result = _build_result(None, checks, diagnostics, started)
        return result, _exit_code(result["status"])

    assert outcome is not None

    # 3. config（YAMLの構文・禁止された構文・型・必須フィールド、I/O、上限。`doctor.md` §3検査5）
    config_status = _config_check_status(outcome)
    checks.append({"name": "config", "status": config_status})
    if catalog_status is not None:
        checks.append({"name": "catalog", "status": catalog_status})

    if outcome.stop_stage == "config":
        # `config`の時点で停止。`schema`／`ears`／`command`／`impact`は依存する出力がないため出さない。
        diagnostics.extend(d.to_dict() for d in outcome.diagnostics)
        diagnostics.extend(d.to_dict() for d in outcome.warnings)
        _append_git_check(git, checks, diagnostics)
        result = _build_result(outcome.workspace_id, checks, diagnostics, started)
        return result, _exit_code(result["status"])

    # 4. schema（`schemaVersion`のメジャーバージョン。`doctor.md` §3検査7）
    if outcome.stop_stage == "schema-major":
        checks.append({"name": "schema", "status": "blocked"})
        diagnostics.extend(d.to_dict() for d in outcome.diagnostics)
        diagnostics.extend(d.to_dict() for d in outcome.warnings)
        _append_git_check(git, checks, diagnostics)
        result = _build_result(outcome.workspace_id, checks, diagnostics, started)
        return result, _exit_code(result["status"])
    checks.append({"name": "schema", "status": "passed"})

    # 5. ears（`earsAi`のメジャーバージョン。`doctor.md` §3検査8）
    if outcome.stop_stage == "ears-major":
        checks.append({"name": "ears", "status": "blocked"})
        diagnostics.extend(d.to_dict() for d in outcome.diagnostics)
        diagnostics.extend(d.to_dict() for d in outcome.warnings)
        _append_git_check(git, checks, diagnostics)
        result = _build_result(outcome.workspace_id, checks, diagnostics, started)
        return result, _exit_code(result["status"])
    checks.append({"name": "ears", "status": "passed"})

    assert outcome.stop_stage is None

    # 6. git（独立した検査）
    _append_git_check(git, checks, diagnostics)

    # 7. command
    assert outcome.config is not None
    commands: dict = outcome.config.get("_resolvedCommands", {})
    command_status = "passed"
    for name in sorted(commands):
        cmd = commands[name]
        cmd_cwd = cmd["cwd"]
        cwd_abs = cmd_cwd if os.path.isabs(cmd_cwd) else os.path.join(loc.root, cmd_cwd)
        if not os.path.isdir(cwd_abs):
            command_status = "blocked"
            diagnostics.append(
                {
                    "code": "SPEC-DOCTOR-COMMAND-001",
                    "severity": "error",
                    "resultStatus": "blocked",
                    "summary": "コマンドの作業ディレクトリを解決できません",
                    "source": {
                        "kind": "file",
                        "workspaceId": outcome.workspace_id,
                        "path": config_mod.CONFIG_PATH,
                        "key": f"verify.commands.{name}.cwd",
                    },
                    "suggestedAction": messages.doctor_command_cwd_action(name),
                }
            )
            continue
        if not _resolve_command_file(cmd["argv"][0], cwd_abs, env):
            command_status = "blocked"
            diagnostics.append(
                {
                    "code": "SPEC-DOCTOR-COMMAND-001",
                    "severity": "error",
                    "resultStatus": "blocked",
                    "summary": "コマンドの実行可能ファイルを解決できません",
                    "source": {
                        "kind": "file",
                        "workspaceId": outcome.workspace_id,
                        "path": config_mod.CONFIG_PATH,
                        "key": f"verify.commands.{name}.argv",
                    },
                    "suggestedAction": messages.doctor_command_file_action(name),
                }
            )
    checks.append({"name": "command", "status": command_status})

    # 8. impact（Step 1では影響候補の実処理は未実装。常に検査項目の状態`info`で骨格だけ返す）
    # TODO(Step2以降): 変更された文書へ強く依存する`approved`の文書の実際の件数を数える。
    checks.append({"name": "impact", "status": "info"})

    for d in outcome.warnings:
        diagnostics.append(d.to_dict())

    result = _build_result(outcome.workspace_id, checks, diagnostics, started)
    return result, _exit_code(result["status"])


def _build_result(
    workspace_id: str | None,
    checks: list[dict],
    diagnostics: list[dict],
    started: int,
) -> dict:
    diagnostics = sort_diagnostics(diagnostics)
    status = doctor_status(checks, diagnostics)
    return {
        "schemaVersion": "1.0",
        "operation": "doctor",
        "status": status,
        "workspace": {"id": workspace_id, "path": "."},
        "durationMs": _elapsed_ms(started),
        "diagnostics": diagnostics,
        "core": {
            "version": CORE_VERSION,
            "apiVersion": CORE_API_VERSION,
            "capabilities": list(CORE_CAPABILITIES),
        },
        "checks": checks,
    }


def _exit_code(status: str) -> int:
    from .resultmodel import EXIT_CODE_BY_STATUS

    return EXIT_CODE_BY_STATUS[status]


def _now_ms() -> int:
    import time

    return time.monotonic_ns() // 1_000_000


def _elapsed_ms(started: int) -> int:
    return max(0, _now_ms() - started)
