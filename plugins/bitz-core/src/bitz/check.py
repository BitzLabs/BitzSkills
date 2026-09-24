"""`bitz check` 操作（`03_操作仕様/02_check.md`）。

Step 1範囲: 設定・workspace段階で文書を読まずに停止する経路と、`--full`でrevisionを解決し
文書0件を検査する経路だけを実装する。`scope: changed`（Git変更集合からの選択）と
`scope: selected`（明示対象のContext解決）はStep 2以降で実装する。
"""

from __future__ import annotations

import time

from . import config as config_mod
from . import gitutil
from .cliargs import ParsedArgs
from .errors import CliArgError
from .notimpl import NotImplementedOperation
from .resultmodel import EXIT_CODE_BY_STATUS, sort_diagnostics, status_from_diagnostics
from .workspace import locate_workspace

NOT_IMPLEMENTED_REASON = (
    "check: scope=selected/changedの本体処理はStep 2以降で実装する"
)


def run(parsed: ParsedArgs, cwd: str, env: dict[str, str]) -> tuple[dict, int]:
    if parsed.positionals:
        raise NotImplementedOperation(NOT_IMPLEMENTED_REASON)
    if "--full" not in parsed.flags:
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
        # TODO(Step2以降): 全SPECのEARS-AI／Schema／関係／状態検査を実装し、
        # checkedDocumentCount／checkedStatementCountを実件数へ置き換える。

    diagnostics = sort_diagnostics(diagnostics)
    status = status_from_diagnostics(diagnostics)
    result = {
        "schemaVersion": "1.0",
        "operation": "check",
        "status": status,
        "scope": "full",
        "workspace": {"id": workspace_id, "path": "."},
        "revision": revision,
        "checkedDocumentCount": 0,
        "checkedStatementCount": 0,
        "durationMs": max(0, time.monotonic_ns() // 1_000_000 - started),
        "diagnostics": diagnostics,
    }
    return result, EXIT_CODE_BY_STATUS[status]
