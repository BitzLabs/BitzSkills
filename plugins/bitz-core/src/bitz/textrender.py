"""`--format text` の出力（`結果・Diagnostic・終了コード仕様 §7`）。"""

from __future__ import annotations

from .textutil import sanitize_control_chars


def _diagnostic_line(d: dict) -> list[str]:
    src = d["source"]
    if src.get("kind") == "file":
        wid = src.get("workspaceId")
        wid_s = "" if wid is None else sanitize_control_chars(wid)
        path = sanitize_control_chars(src.get("path", ""))
        line = str(src["line"]) if "line" in src else ""
        column = str(src["column"]) if "column" in src else ""
        head = f"{wid_s}:{path}:{line}:{column}"
    elif src.get("kind") == "environment":
        head = f"{src.get('component', '')}:::"
    else:
        head = "invocation:::"
    summary = sanitize_control_chars(d["summary"])
    code = sanitize_control_chars(d["code"])
    line1 = f"{head}: {d['severity']}: {code}: {summary}"
    lines = [line1]
    action = d.get("suggestedAction")
    if action:
        lines.append(f"  -> {sanitize_control_chars(action)}")
    return lines


def render_doctor_text(result: dict) -> str:
    n_targets = len(result.get("checks", []))
    n_diag = len(result.get("diagnostics", []))
    lines = [
        f"doctor {result['status']} targets={n_targets} diagnostics={n_diag} "
        f"({result['durationMs']}ms)"
    ]
    for d in result.get("diagnostics", []):
        lines.extend(_diagnostic_line(d))
    return "\n".join(lines) + "\n"


def render_check_text(result: dict) -> str:
    scope = result.get("scope")
    if scope == "changed":
        n_targets = result["selection"]["targetDocumentCount"]
    elif scope in ("selected", "full"):
        n_targets = result.get("checkedDocumentCount", 0)
    else:
        n_targets = sum(w.get("checkedDocumentCount", 0) for w in result.get("workspaces", []))
    n_diag = len(result.get("diagnostics", []))
    lines = [
        f"check {result['status']} scope={scope} targets={n_targets} diagnostics={n_diag} "
        f"({result['durationMs']}ms)"
    ]
    for d in result.get("diagnostics", []):
        lines.extend(_diagnostic_line(d))
    return "\n".join(lines) + "\n"


def render_verify_text(result: dict) -> str:
    target_results = result.get("targetResults", [])
    n_targets = len(target_results)
    diags = list(result.get("diagnostics", []))
    for t in target_results:
        diags.extend(t.get("diagnostics", []))
    lines = [
        f"verify {result['status']} scope={result.get('scope')} targets={n_targets} "
        f"diagnostics={len(diags)} ({result['durationMs']}ms)"
    ]
    for d in diags:
        lines.extend(_diagnostic_line(d))
    return "\n".join(lines) + "\n"
