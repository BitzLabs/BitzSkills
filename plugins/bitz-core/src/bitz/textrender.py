"""`--format text` の出力（結果・診断・終了コード §7）。"""

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
    workspaces = result.get("workspaces", [])
    n_targets = len(result.get("checks", [])) + sum(len(w["checks"]) for w in workspaces)
    diagnostics = list(result.get("diagnostics", []))
    for workspace in workspaces:
        diagnostics.extend(workspace["diagnostics"])
    n_diag = len(diagnostics)
    lines = [
        f"doctor {result['status']} targets={n_targets} diagnostics={n_diag} "
        f"({result['durationMs']}ms)"
    ]
    for d in diagnostics:
        lines.extend(_diagnostic_line(d))
    return "\n".join(lines) + "\n"


def _tree_diagnostics(result: dict) -> list[dict]:
    """結果の木構造に実在する診断を、§7の順で集める（診断を複製しない）。

    最上位の診断を先に置き、続けて最上位の検証対象（`targetResults`）の診断、その後にワークスペースの処理順で
    各ワークスペースの診断と、そのワークスペースの検証対象の診断を、検証対象の並びのまま置く。
    """
    diagnostics = list(result.get("diagnostics", []))
    for target in result.get("targetResults", []):
        diagnostics.extend(target.get("diagnostics", []))
    for workspace in result.get("workspaces", []):
        diagnostics.extend(workspace.get("diagnostics", []))
        for target in workspace.get("targetResults", []):
            diagnostics.extend(target.get("diagnostics", []))
    return diagnostics


def render_check_text(result: dict) -> str:
    scope = result.get("scope")
    if scope == "changed":
        n_targets = result["selection"]["targetDocumentCount"]
    elif scope in ("selected", "full"):
        n_targets = result.get("checkedDocumentCount", 0)
    else:
        n_targets = sum(w.get("checkedDocumentCount", 0) for w in result.get("workspaces", []))
    diagnostics = _tree_diagnostics(result)
    lines = [
        f"check {result['status']} scope={scope} targets={n_targets} diagnostics={len(diagnostics)} "
        f"({result['durationMs']}ms)"
    ]
    for d in diagnostics:
        lines.extend(_diagnostic_line(d))
    return "\n".join(lines) + "\n"


def render_verify_text(result: dict) -> str:
    scope = result.get("scope")
    if scope == "all-workspaces":
        n_targets = sum(len(w.get("targetResults", [])) for w in result.get("workspaces", []))
    else:
        n_targets = len(result.get("targetResults", []))
    diagnostics = _tree_diagnostics(result)
    lines = [
        f"verify {result['status']} scope={scope} targets={n_targets} "
        f"diagnostics={len(diagnostics)} ({result['durationMs']}ms)"
    ]
    for d in diagnostics:
        lines.extend(_diagnostic_line(d))
    return "\n".join(lines) + "\n"
