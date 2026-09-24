"""結果外形の共通ヘルパー。

`結果・Diagnostic・終了コード仕様` の status集約、Diagnostic sort、終了コード対応を実装する。
"""

from __future__ import annotations

_STATUS_ORDER = ["error", "failed", "blocked", "passed_with_warnings", "passed"]

EXIT_CODE_BY_STATUS = {
    "passed": 0,
    "passed_with_warnings": 0,
    "failed": 1,
    "blocked": 2,
    "error": 3,
}


def worst_status(statuses: list[str]) -> str:
    if not statuses:
        return "passed"
    best_rank = len(_STATUS_ORDER) - 1
    for s in statuses:
        rank = _STATUS_ORDER.index(s)
        if rank < best_rank:
            best_rank = rank
    return _STATUS_ORDER[best_rank]


def status_from_diagnostics(diagnostics: list[dict]) -> str:
    return worst_status([d["resultStatus"] for d in diagnostics]) if diagnostics else "passed"


_DOCTOR_CHECK_TO_RESULT_STATUS = {
    "passed": "passed",
    "info": "passed",
    "warning": "passed_with_warnings",
    "failed": "failed",
    "blocked": "blocked",
    "error": "error",
}


def doctor_status(checks: list[dict], diagnostics: list[dict]) -> str:
    statuses = [d["resultStatus"] for d in diagnostics]
    for c in checks:
        statuses.append(_DOCTOR_CHECK_TO_RESULT_STATUS[c["status"]])
    return worst_status(statuses)


def diagnostic_sort_key(d: dict):
    src = d["source"]
    if src.get("kind") == "file":
        wid = src.get("workspaceId")
        wid_key = (0, "") if wid is None else (1, wid)
        path = src.get("path", "")
        line = src.get("line", 0)
        column = src.get("column", 0)
    else:
        wid_key = (1, "")
        path = ""
        line = 0
        column = 0
    code = d["code"]
    spec_refs = tuple(d.get("specRefs", []))
    return (wid_key, path, line, column, code, spec_refs)


def sort_diagnostics(diagnostics: list[dict]) -> list[dict]:
    return sorted(diagnostics, key=diagnostic_sort_key)
