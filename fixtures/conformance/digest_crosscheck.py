"""Context Digest reference computation B: derived from the input tree.

Reference A (digest_reference) states the reviewed digest input as literals.
This module never imports those literals. It reads the fixture's own repo/ tree,
recovers Frontmatter, body and normative statements with a deliberately narrow
reader for the corpus shape, applies the ordering rules itself, and emits
canonical bytes through a second, separately written RFC 8785 emitter. Agreement
between the two is the Gate A cross-check; neither is a Core implementation.
"""
import hashlib
import re
import unicodedata

KIND_BY_DIRECTORY = {
    "requirements": "requirement",
    "technical": "technical",
    "decisions": "decision",
    "tasks": "task",
}
KIND_RANK = {"requirement": 0, "technical": 1, "decision": 2, "task": 3}
STRONG = ("requires", "refines", "addresses", "supersedes")
RELATION_KEYS = ("requires", "refines", "addresses", "supersedes", "related")
APPLICABLE_STATUS = {"approved", "accepted", "open", "done"}
CORE_FRONTMATTER = ("id", "title", "status", "relations", "implements", "tests", "verify", "changes")


# --- restricted readers ------------------------------------------------------------

def _scalar(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def _flow_sequence(text):
    inner = text.strip()[1:-1].strip()
    return [_scalar(item) for item in inner.split(",")] if inner else []


def _value(text):
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        return _flow_sequence(text)
    return _scalar(text)


def read_block(lines, index, indent):
    """Read one block sequence or block map whose members sit at `indent`."""
    if index < len(lines) and lines[index].startswith(" " * indent + "- "):
        items = []
        while index < len(lines) and lines[index].startswith(" " * indent + "- "):
            block = [" " * (indent + 2) + lines[index][indent + 2:]]
            index += 1
            while (index < len(lines) and lines[index].startswith(" " * (indent + 2))
                   and not lines[index].startswith(" " * indent + "- ")):
                block.append(lines[index])
                index += 1
            entry, _ = read_block(block, 0, indent + 2)
            items.append(entry)
        return items, index
    mapping = {}
    while index < len(lines):
        line = lines[index]
        current = len(line) - len(line.lstrip(" "))
        if current < indent:
            break
        if current > indent:
            raise ValueError("unexpected indentation in fixture YAML")
        key, _, rest = line.strip().partition(":")
        if rest.strip():
            mapping[key] = _value(rest)
            index += 1
        else:
            mapping[key], index = read_block(lines, index + 1, indent + 2)
    return mapping, index


def read_yaml(text):
    lines = [line for line in text.split("\n") if line.strip()]
    mapping, _ = read_block(lines, 0, 0)
    return mapping


def split_document(text):
    if not text.startswith("---\n"):
        raise ValueError("fixture document must start with a Frontmatter block")
    end = text.index("\n---\n", 3)
    return read_yaml(text[4:end + 1]), text[end + 5:]


def normalize_body(raw):
    body = raw.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip(" \t") for line in body.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n" if lines else ""


STATEMENT = re.compile(
    r"^- \[(?P<id>[A-Za-z0-9:\-]+)\] "
    r"\[ACTOR:(?P<actor>[A-Za-z][A-Za-z0-9_\-]*)\] "
    r"(?P<activation>\[ALWAYS\]|\[(?:WHEN|WHILE|WHERE|IF_ERROR)\] .+?) "
    r"\[(?P<modality>MUST|SHOULD|MAY)\](?P<reason> \[REASON\] .+?)? "
    r"\[(?P<operation>THEN|GENERATE|CONSTRAINT)\] (?P<text>.+)[.。]$")


def read_statements(body):
    statements = []
    for line in body.split("\n"):
        if not line.startswith("- ["):
            continue
        match = STATEMENT.match(line)
        if not match:
            raise ValueError(f"corpus statement is not in canonical form: {line}")
        activation = match.group("activation")
        if activation == "[ALWAYS]":
            kind, text = "ALWAYS", None
        else:
            kind, _, text = activation[1:].partition("] ")
        reason = match.group("reason")
        # should-modality = "[SHOULD]", [ SP, reason ]; MUST and MAY take no reason.
        if reason and match.group("modality") != "SHOULD":
            raise ValueError(f"[REASON] is only valid with [SHOULD]: {line}")
        statements.append({
            "id": match.group("id"),
            "actor": match.group("actor"),
            "activation": {"kind": kind, "text": text},
            "modality": match.group("modality"),
            "reason": reason[len(" [REASON] "):] if reason else None,
            "operation": {"kind": match.group("operation"), "text": match.group("text")},
            "extensions": [],
        })
    return statements


# --- digest input assembly ---------------------------------------------------------

def _relations(frontmatter):
    declared = frontmatter.get("relations", {})
    return {key: sorted(set(declared.get(key, []))) for key in RELATION_KEYS}


def _paths(values):
    return sorted({value.replace("\\", "/") for value in values})


def _tests(frontmatter):
    entries = []
    for entry in frontmatter.get("tests", []):
        entries.append({
            "path": entry["path"].replace("\\", "/"),
            "covers": sorted(set(entry["covers"])),
            "command": entry.get("command"),
        })
    return sorted(entries, key=lambda item: (item["path"], item["command"] is not None,
                                             item["command"] or "", item["covers"]))


def load_documents(repository):
    documents = {}
    for directory, kind in KIND_BY_DIRECTORY.items():
        folder = repository / ".spec" / directory
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md")):
            frontmatter, raw = split_document(path.read_text(encoding="utf-8"))
            documents[frontmatter["id"]] = {
                "kind": kind,
                "frontmatter": frontmatter,
                "body": normalize_body(raw),
                "path": path.relative_to(repository).as_posix(),
            }
    return documents


def closure(documents, root):
    """Reviewed verify/interpret closure for this corpus: the root plus every
    applicable document that refines it. The corpus is asserted to contain no
    other strong edge, so no general expansion rule is implemented here."""
    reached = {root: 0}
    for identifier, document in documents.items():
        relations = _relations(document["frontmatter"])
        if root in relations["refines"] and document["frontmatter"]["status"] in APPLICABLE_STATUS:
            reached[identifier] = 1
        for key in STRONG:
            for target in relations[key]:
                if identifier != root and target != root and target in documents:
                    raise ValueError("corpus holds a strong edge outside the reviewed closure")
    return sorted(reached, key=lambda identifier: (reached[identifier],
                                                   KIND_RANK[documents[identifier]["kind"]], identifier))


def build(repository, root="REQ-001", purpose="verify", workspace_id="root"):
    config = read_yaml((repository / ".spec/bitz.yaml").read_text(encoding="utf-8"))
    documents = load_documents(repository)
    selected = closure(documents, root)
    commands, entries = config.get("verify", {}).get("commands", {}), []
    used = set()
    for identifier in selected:
        for test in _tests(documents[identifier]["frontmatter"]):
            if test["command"] is not None:
                used.add(test["command"])
    for name in sorted(used):
        command = commands[name]
        entries.append({"workspaceId": workspace_id, "name": name,
                        "argv": list(command["argv"]), "cwd": command.get("cwd", ".")})
    timeout = int(config.get("verify", {}).get("timeoutSeconds", 300))
    payload = {
        "digestVersion": "1.0",
        "specSchemaVersion": config["schemaVersion"],
        "earsAiVersion": config["earsAi"],
        "resolverVersion": "1.0",
        "purpose": purpose,
        "requestWorkspaceId": workspace_id,
        "roots": [root],
        "workspaces": [{"id": workspace_id, "path": "."}],
        "documents": [],
        "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": workspace_id, "schemaVersion": config["schemaVersion"],
                            "earsAi": config["earsAi"], "language": config["language"]}],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": workspace_id, "timeoutSeconds": timeout}] if entries else [],
            "commands": entries,
        },
    }
    for identifier in sorted(selected):
        document = documents[identifier]
        frontmatter = document["frontmatter"]
        relations = _relations(frontmatter)
        strong = sorted({(key, target) for key in STRONG for target in relations[key]})
        payload["documents"].append({
            "id": identifier,
            "workspaceId": workspace_id,
            "kind": document["kind"],
            "status": frontmatter["status"],
            "applicability": "applicable",
            "frontmatter": {
                "id": frontmatter["id"],
                "title": frontmatter["title"],
                "status": frontmatter["status"],
                "relations": relations,
                "implements": _paths(frontmatter.get("implements", [])),
                "tests": _tests(frontmatter),
                "verify": frontmatter.get("verify"),
                "changes": _paths(frontmatter.get("changes", [])),
            },
            "bodyText": document["body"],
            "statements": sorted(read_statements(document["body"]), key=lambda item: item["id"]),
            "strongRelations": [{"relation": key, "target": target} for key, target in strong],
        })
    return normalize_strings(payload)


def normalize_strings(value):
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [normalize_strings(item) for item in value]
    if isinstance(value, dict):
        return {unicodedata.normalize("NFC", key): normalize_strings(item) for key, item in value.items()}
    return value


# --- RFC 8785 emitter (reference B) ------------------------------------------------

def _code_units(text):
    return [int.from_bytes(text.encode("utf-16-be")[position:position + 2], "big")
            for position in range(0, len(text.encode("utf-16-be")), 2)]


def _emit_string(text, out):
    out += b'"'
    short = {0x08: b"\\b", 0x09: b"\\t", 0x0A: b"\\n", 0x0C: b"\\f", 0x0D: b"\\r"}
    for character in text:
        point = ord(character)
        if character == '"':
            out += b'\\"'
        elif character == "\\":
            out += b"\\\\"
        elif point in short:
            out += short[point]
        elif point < 0x20:
            out += ("\\u%04x" % point).encode("ascii")
        else:
            out += character.encode("utf-8")
    out += b'"'


def _emit(value, out):
    if value is None:
        out += b"null"
    elif isinstance(value, bool):
        out += b"true" if value else b"false"
    elif isinstance(value, int):
        out += str(value).encode("ascii")
    elif isinstance(value, str):
        _emit_string(value, out)
    elif isinstance(value, list):
        out += b"["
        for position, item in enumerate(value):
            if position:
                out += b","
            _emit(item, out)
        out += b"]"
    elif isinstance(value, dict):
        out += b"{"
        for position, key in enumerate(sorted(value, key=_code_units)):
            if position:
                out += b","
            _emit_string(key, out)
            out += b":"
            _emit(value[key], out)
        out += b"}"
    else:
        raise TypeError("unsupported digest input value")


def canonical_bytes(value):
    out = bytearray()
    _emit(value, out)
    return bytes(out)


def digest(canonical):
    return "sha256:" + hashlib.sha256(canonical).hexdigest()
