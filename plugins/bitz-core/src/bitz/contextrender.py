"""`bitz context`の既定Markdown提示（`03_操作仕様/01_context.md` §9）。

結果JSONだけを入力とする決定的な変換。呼び出し側（`cli.py`）は`--format markdown`
（既定）のときにこのmoduleを使う。
"""

from __future__ import annotations

import re

from . import digest as digest_mod
from .textrender import _diagnostic_line

_FENCE_RUN_RE = re.compile(r"`+")


def _bool_str(b: bool) -> str:
    return "true" if b else "false"


def _join_or_none(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


def _join_blocks(blocks: list[list[str]]) -> list[str]:
    out: list[str] = []
    for i, b in enumerate(blocks):
        if i > 0:
            out.append("")
        out.extend(b)
    return out


def _fence_for(text: str) -> str:
    runs = _FENCE_RUN_RE.findall(text)
    longest = max((len(r) for r in runs), default=0)
    return "`" * max(longest + 1, 3)


def _manifest_lines(result: dict) -> list[str]:
    lines = [
        f"- operation: {result['operation']}",
        f"- status: {result['status']}",
        f"- purpose: {result['purpose']}",
    ]
    ws = result["workspace"]
    lines.append(f"- workspace: {ws['id']} ({ws['path']})")
    lines.append(f"- roots: {_join_or_none(result['roots'])}")
    digest_value = result["contextDigest"] if result["contextDigest"] is not None else "null"
    lines.append(f"- contextDigest: {digest_value}")
    rev = result["revision"]
    rev_s = "null" if rev is None else f"{rev['commit']} dirty={_bool_str(rev['dirty'])}"
    lines.append(f"- revision: {rev_s}")
    res = result["resolution"]
    lines.append(
        "- resolution: complete={}, documentCount={}, unresolvedStrongRelations={}".format(
            _bool_str(res["complete"]), res["documentCount"], res["unresolvedStrongRelations"]
        )
    )
    proj = result["projection"]
    lines.append(f"- projection: detail={proj['detail']}, expanded={_join_or_none(proj['expanded'])}")
    return lines


def _diag_md_lines(d: dict) -> list[str]:
    raw = _diagnostic_line(d)
    return ["- " + raw[0]] + list(raw[1:])


def _diagnostics_lines(result: dict) -> list[str]:
    lines: list[str] = []
    for d in result.get("diagnostics", []):
        lines.extend(_diag_md_lines(d))
    for modality_key, modality_label in (("must", "MUST"), ("should", "SHOULD"), ("may", "MAY")):
        bucket_data = result["coverage"][modality_key]
        for bucket in ("unaddressed", "untested"):
            ids = bucket_data[bucket]
            if ids:
                lines.append(f"- coverage: {modality_label} {bucket}: {', '.join(ids)}")
    return lines


def _kind_text_str(d: dict) -> str:
    if d.get("text") is not None:
        return f"{d['kind']} {d['text']}"
    return d["kind"]


def _ledger_block(stmt: dict) -> list[str]:
    reason = stmt["reason"] if stmt["reason"] is not None else "null"
    return [
        f"### {stmt['id']}",
        "",
        f"- documentId: {stmt['documentId']}",
        f"- documentRole: {stmt['documentRole']}",
        f"- modality: {stmt['modality']}",
        f"- reason: {reason}",
        f"- actor: {stmt['actor']}",
        f"- activation: {_kind_text_str(stmt['activation'])}",
        f"- operation: {_kind_text_str(stmt['operation'])}",
    ]


def _doc_block(doc: dict, detail: str) -> list[str]:
    lines = [f"### {doc['id']} — {doc['path']}"]
    lines.append("")
    if detail == "compact":
        lines.append(f"- {doc['id']}: {doc['path']}")
        return lines
    lines.append(f"- kind: {doc['kind']}")
    lines.append(f"- status: {doc['status']}")
    lines.append(f"- projection: {doc['projection']}")
    lines.append(f"- reachedBy: {_join_or_none(doc['reachedBy'])}")
    if doc["projection"] in ("full", "normative"):
        lines.append(f"- statementRefs: {_join_or_none(doc.get('statementRefs') or [])}")
    if doc["projection"] == "full":
        fm_json = digest_mod.canonical_bytes(doc.get("frontmatter") or {}).decode("utf-8")
        lines.append(f"- frontmatter: {fm_json}")
    lines.append(f"- untrustedText: {_bool_str(doc['untrustedText'])}")
    if doc["projection"] == "full":
        lines.append("- bodyText:")
        lines.append("")
        body = doc.get("bodyText", "")
        fence = _fence_for(body)
        lines.append(fence + "markdown")
        lines.extend(body.splitlines())
        lines.append(fence)
    if doc["projection"] == "reference":
        lines.append(f"- expandable: {_bool_str(doc.get('expandable', True))}")
    return lines


def _verification_lines(documents: list[dict]) -> list[str]:
    lines: list[str] = []
    for doc in documents:
        if doc.get("projection") != "full":
            continue
        tests = (doc.get("frontmatter") or {}).get("tests") or []
        for t in tests:
            covers = _join_or_none(t.get("covers") or [])
            command = t.get("command") or "none"
            lines.append(f"- {t['path']}: covers {covers} (command: {command})")
    return lines


def render_context_markdown(result: dict) -> str:
    lines: list[str] = ["# Context Bundle", ""]

    def add_section(title: str, body: list[str]) -> None:
        lines.append(f"## {title}")
        lines.append("")
        lines.extend(body if body else ["- none"])
        lines.append("")

    add_section("Bundle Manifest", _manifest_lines(result))
    add_section("Diagnostics and Coverage Gaps", _diagnostics_lines(result))

    ledger = result["constraintLedger"]["statements"]
    add_section("Normative Constraint Ledger", _join_blocks([_ledger_block(s) for s in ledger]))

    docs = result["documents"]
    detail = result["projection"]["detail"]

    def docs_for(*roles: str) -> list[dict]:
        return [d for d in docs if d["role"] in roles]

    add_section("Root Intent", _join_blocks([_doc_block(d, detail) for d in docs_for("root")]))
    add_section(
        "Required Context",
        _join_blocks([_doc_block(d, detail) for d in docs_for("requirement", "constraint")]),
    )
    add_section("Applicable Refinements", _join_blocks([_doc_block(d, detail) for d in docs_for("refinement")]))
    add_section("Replacement Candidates", _join_blocks([_doc_block(d, detail) for d in docs_for("replacement")]))
    add_section("Work Boundary", _join_blocks([_doc_block(d, detail) for d in docs_for("work")]))
    add_section("Verification Bindings", _verification_lines(docs))
    add_section("Advisory Documents", _join_blocks([_doc_block(d, detail) for d in docs_for("advisory")]))

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"
