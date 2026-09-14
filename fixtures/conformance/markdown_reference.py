"""Reference rendering of the Markdown presentation fixed by context仕様 §9.

This is fixture-side reference computation, not a Core renderer: it consumes a
reviewed result JSON and produces the byte sequence §9 prescribes, so a committed
expectation can be compared against an independently written derivation.
"""
import re

from . import digest_reference

SECTIONS = ["Bundle Manifest", "Diagnostics and Coverage Gaps", "Normative Constraint Ledger",
            "Root Intent", "Required Context", "Applicable Refinements", "Replacement Candidates",
            "Work Boundary", "Verification Bindings", "Advisory Documents"]
ROLES = {"Root Intent": ("root",), "Required Context": ("requirement", "constraint"),
         "Applicable Refinements": ("refinement",), "Replacement Candidates": ("replacement",),
         "Work Boundary": ("work",), "Advisory Documents": ("advisory",)}


def joined(values):
    return ", ".join(values) if values else "none"


def fence(body):
    """Longer than every backtick run inside the body, and never shorter than three."""
    longest = max((len(run) for run in re.findall(r"`+", body)), default=0)
    return "`" * max(3, longest + 1)


def manifest_lines(result):
    revision, projection, resolution = result["revision"], result["projection"], result["resolution"]
    return [
        f"- operation: {result['operation']}",
        f"- status: {result['status']}",
        f"- purpose: {result['purpose']}",
        f"- workspace: {result['workspace']['id']} ({result['workspace']['path']})",
        f"- roots: {joined(result['roots'])}",
        f"- contextDigest: {result['contextDigest']}",
        "- revision: " + ("null" if revision is None
                          else f"{revision['commit']} dirty={str(revision['dirty']).lower()}"),
        f"- resolution: complete={str(resolution['complete']).lower()}, "
        f"documentCount={resolution['documentCount']}, "
        f"unresolvedStrongRelations={resolution['unresolvedStrongRelations']}",
        f"- projection: detail={projection['detail']}, expanded={joined(projection['expanded'])}",
    ]


def diagnostic_lines(result):
    """Diagnostic rows reuse the common text line shape; see 共通結果契約 §7."""
    lines = []
    for diagnostic in result["diagnostics"]:
        source = diagnostic["source"]
        head = (f"{source['workspaceId']}:{source['path']}:{source.get('line', '')}:{source.get('column', '')}"
                if source["kind"] == "file" else f"{source.get('component', 'invocation')}:::")
        lines.append(f"- {head}: {diagnostic['severity']}: {diagnostic['code']}: {diagnostic['summary']}")
        if "suggestedAction" in diagnostic:
            lines.append("  -> " + diagnostic["suggestedAction"])
    return lines


def coverage_lines(result):
    lines = []
    for modality in ("must", "should", "may"):
        bucket = result["coverage"][modality]
        for name in ("unaddressed", "untested"):
            if bucket[name]:
                lines.append(f"- coverage: {modality.upper()} {name}: {joined(bucket[name])}")
    return lines


def ledger_blocks(result):
    blocks = []
    for statement in result["constraintLedger"]["statements"]:
        activation, operation = statement["activation"], statement["operation"]
        blocks.append("\n".join([
            f"### {statement['id']}", "",
            f"- documentId: {statement['documentId']}",
            f"- documentRole: {statement['documentRole']}",
            f"- modality: {statement['modality']}",
            "- reason: " + ("null" if statement["reason"] is None else statement["reason"]),
            f"- actor: {statement['actor']}",
            "- activation: " + activation["kind"] + (f" {activation['text']}" if activation.get("text") else ""),
            "- operation: " + operation["kind"] + (f" {operation['text']}" if operation.get("text") else ""),
        ]) + "\n")
    return blocks


def document_block(document, detail="standard"):
    heading = f"### {document['id']} — {document['path']}"
    if detail == "compact":
        return heading + "\n\n" + f"- {document['id']}: {document['path']}\n"
    lines = [heading, "", f"- kind: {document['kind']}", f"- status: {document['status']}",
             f"- projection: {document['projection']}",
             f"- reachedBy: {joined(document['reachedBy'])}"]
    if "statementRefs" in document:
        lines.append(f"- statementRefs: {joined(document['statementRefs'])}")
    if "frontmatter" in document:
        lines.append("- frontmatter: "
                     + digest_reference.canonical_bytes(document["frontmatter"]).decode())
    if "expandable" in document:
        lines.append(f"- expandable: {str(document['expandable']).lower()}")
    lines.append("- untrustedText: true")
    if "bodyText" not in document:
        return "\n".join(lines) + "\n"
    body = document["bodyText"]
    marker = fence(body)
    return ("\n".join(lines + ["- bodyText:", "", marker + "markdown"]) + "\n"
            + (body if body.endswith("\n") else body + "\n") + marker + "\n")


def bindings_lines(result):
    lines = []
    for document in result["documents"]:
        for test in document.get("frontmatter", {}).get("tests", []):
            lines.append(f"- {test['path']}: covers {joined(test['covers'])} "
                         f"(command: {test.get('command', 'none')})")
    return lines


def render(result):
    """The complete Markdown byte sequence for one reviewed context result."""
    detail = result["projection"]["detail"]
    parts = ["# Context Bundle\n"]
    for section in SECTIONS:
        parts.append(f"## {section}\n")
        if section == "Bundle Manifest":
            body = "\n".join(manifest_lines(result)) + "\n"
        elif section == "Diagnostics and Coverage Gaps":
            lines = diagnostic_lines(result) + coverage_lines(result)
            body = ("\n".join(lines) + "\n") if lines else "- none\n"
        elif section == "Normative Constraint Ledger":
            blocks = ledger_blocks(result)
            body = "\n".join(blocks) if blocks else "- none\n"
        elif section == "Verification Bindings":
            lines = bindings_lines(result)
            body = ("\n".join(lines) + "\n") if lines else "- none\n"
        else:
            documents = [d for d in result["documents"] if d["role"] in ROLES[section]]
            body = ("\n".join(document_block(d, detail) for d in documents)
                    if documents else "- none\n")
        parts.append(body)
    return "\n".join(parts)
