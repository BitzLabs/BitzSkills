"""明示`--report`のreport書出し（`00_共通契約/02_安全な入出力・互換性.md` §8、`01_結果・…` §8）。

`.spec/reports/`（workspace root相対）へ排他的に作成する。`.spec`または`.spec/reports`が
symlinkならlstatで検出し解決しない（辿らない）。原子的作成は同じdirectory内の一時fileへ書き、
成功時は排他的なhard linkで最終report名へ確定し、一時fileを除去する。操作終了後に
最終report以外の一時fileを残さない。
"""

from __future__ import annotations

import json
import os
import stat
import time

from . import messages
from .config import Diagnostic


def _report_write_failed(workspace_id: str | None) -> Diagnostic:
    return Diagnostic(
        code="SPEC-REPORT-WRITE-001",
        severity="error",
        resultStatus="error",
        summary=messages.REPORT_WRITE_FAILED,
        source={"kind": "file", "workspaceId": workspace_id, "path": ".spec/reports"},
    )


def write_report(workspace_root: str, workspace_id: str | None, operation: str, result: dict) -> Diagnostic | None:
    """``result``をJSONのままreportへ書き出す。成功なら``None``、失敗ならDiagnosticを返す。"""

    spec_dir = os.path.join(workspace_root, ".spec")
    reports_dir = os.path.join(workspace_root, ".spec", "reports")

    try:
        spec_lst = os.lstat(spec_dir)
    except OSError:
        return _report_write_failed(workspace_id)
    if not stat.S_ISDIR(spec_lst.st_mode):
        return _report_write_failed(workspace_id)

    try:
        reports_lst = os.lstat(reports_dir)
    except FileNotFoundError:
        try:
            os.mkdir(reports_dir)
        except OSError:
            return _report_write_failed(workspace_id)
    except OSError:
        return _report_write_failed(workspace_id)
    else:
        if not stat.S_ISDIR(reports_lst.st_mode):
            return _report_write_failed(workspace_id)

    payload = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    tmp_name = f".bitz-report-{os.getpid()}-{time.monotonic_ns()}.tmp"
    tmp_path = os.path.join(reports_dir, tmp_name)
    try:
        fd = os.open(tmp_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except OSError:
        return _report_write_failed(workspace_id)

    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
    except OSError:
        _silent_remove(tmp_path)
        return _report_write_failed(workspace_id)

    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    seq = 0
    while True:
        name = f"{timestamp}-{operation}.json" if seq == 0 else f"{timestamp}-{operation}-{seq}.json"
        final_path = os.path.join(reports_dir, name)
        try:
            os.link(tmp_path, final_path)
        except FileExistsError:
            seq += 1
            continue
        except OSError:
            _silent_remove(tmp_path)
            return _report_write_failed(workspace_id)
        else:
            _silent_remove(tmp_path)
            return None


def _silent_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
