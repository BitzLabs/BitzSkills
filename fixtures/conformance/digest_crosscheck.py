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
    r'(?P<extensions>(?:\[[a-z][a-z0-9]*:[A-Z][A-Z0-9_]*(?:="(?:[^"\\\r\n]|\\[\[\]\\`"])*")?\] )*)'
    r"\[ACTOR:(?P<actor>[A-Za-z][A-Za-z0-9_\-]*)\] "
    r"(?P<activation>\[ALWAYS\]|\[(?:WHEN|WHILE|WHERE|IF_ERROR)\] .+?) "
    r"\[(?P<modality>MUST|SHOULD|MAY)\](?P<reason> \[REASON\] .+?)? "
    r"\[(?P<operation>THEN|GENERATE|CONSTRAINT)\] (?P<text>.+)[.。]$")


def unescape_text(text):
    """A narrow fixture-side text decoder; never used as the production Parser."""
    out, index = [], 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 1
            if index == len(text) or text[index] not in '[]\\`"':
                raise ValueError("unknown or trailing escape in reference corpus")
            out.append(text[index])
        elif char == "`":
            start = index
            while index < len(text) and text[index] == "`":
                index += 1
            width, content_start = index - start, index
            while index < len(text):
                if text[index] != "`":
                    index += 1
                    continue
                run_start = index
                while index < len(text) and text[index] == "`":
                    index += 1
                if index - run_start == width:
                    out.append(text[content_start:run_start])
                    break
            else:
                raise ValueError("unclosed code span in reference corpus")
            continue
        else:
            out.append(char)
        index += 1
    return re.sub(r"[ \t]+", " ", "".join(out).strip(" \t"))


EXTENSION = re.compile(r'\[(?P<namespace>[a-z][a-z0-9]*):(?P<term>[A-Z][A-Z0-9_]*)(?:="(?P<value>(?:[^"\\\r\n]|\\[\[\]\\`"])*)")?\] ')


def read_extensions(raw):
    entries, cursor = [], 0
    for match in EXTENSION.finditer(raw):
        if match.start() != cursor:
            raise ValueError("unsupported extension in reference corpus")
        value = match.group("value")
        # Quoted values decode only escapes; unlike text their spaces are opaque.
        if value is not None:
            value = re.sub(r'\\([\[\]\\`"])', r'\1', value)
        entries.append({"namespace": match.group("namespace"), "term": match.group("term"), "value": value})
        cursor = match.end()
    if cursor != len(raw):
        raise ValueError("unsupported extension in reference corpus")
    return entries


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
            "activation": {"kind": kind, "text": unescape_text(text) if text is not None else None},
            "modality": match.group("modality"),
            "reason": unescape_text(reason[len(" [REASON] "):]) if reason else None,
            "operation": {"kind": match.group("operation"), "text": unescape_text(match.group("text"))},
            "extensions": read_extensions(match.group("extensions")),
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


def closure(documents, root, purpose):
    """Reviewed closure for these corpora (関係・トレースモデル §6.1〜§6.4).

    The root document, and for a TASK root outside interpret the documents owning
    what it addresses. From every applicable document reached: its `requires`
    targets (except the root TASK's under verify, §6.3), its `refines` targets,
    and the applicable documents that refine it or one of its statements. Under
    interpret a draft refiner is kept as advisory and not expanded (§6.1 6.).
    Under implement every open TASK addressing a target statement is added. Any
    strong edge touching the closure that the rule does not account for is
    rejected rather than silently absorbed, so this stays a corpus reader and not
    a general target-expansion implementation.

    Returns (ordered document IDs, advisory document IDs).
    """
    def owner(reference):
        return reference.split(":")[0]

    owned = {identifier: [statement["id"] for statement in read_statements(document["body"])]
             for identifier, document in documents.items()}
    known_statements = {identifier for ids in owned.values() for identifier in ids}
    root_document = owner(root)
    if root_document not in documents or (root != root_document and root not in known_statements):
        raise ValueError("the root is not owned by this corpus")
    root_kind = documents[root_document]["kind"]
    reached, advisory, accounted = {root_document: 0}, set(), set()
    frontier = [root_document]

    def reach(identifier, distance):
        if identifier not in documents:
            raise ValueError("a strong edge leaves this corpus")
        if identifier not in reached:
            reached[identifier] = distance
            frontier.append(identifier)

    if root_kind == "task" and purpose != "interpret":
        for target in _relations(documents[root_document]["frontmatter"])["addresses"]:
            accounted.add((root_document, "addresses", target))
            reach(owner(target), 1)
        if purpose == "verify":
            # §6.3: verifyの起点TASKはrequires閉包を含めない。辿らない辺として記録する。
            for target in _relations(documents[root_document]["frontmatter"])["requires"]:
                accounted.add((root_document, "requires", target))
    while frontier:
        current = frontier.pop(0)
        if current in advisory:
            continue
        relations = _relations(documents[current]["frontmatter"])
        for key in ("requires", "refines"):
            for target in relations[key]:
                if (current, key, target) in accounted:
                    continue
                accounted.add((current, key, target))
                reach(owner(target), reached[current] + 1)
        mine = {current, *owned.get(current, [])}
        for identifier, document in sorted(documents.items()):
            refined = [target for target in _relations(document["frontmatter"])["refines"] if target in mine]
            if not refined or identifier in reached:
                continue
            status = document["frontmatter"]["status"]
            if status in APPLICABLE_STATUS:
                pass
            elif status == "draft" and purpose == "interpret":
                advisory.add(identifier)
            else:
                continue
            for target in refined:
                accounted.add((identifier, "refines", target))
            reach(identifier, reached[current] + 1)
    if purpose == "implement":
        targets = target_statements(documents, owned, root, reached, advisory)
        for identifier, document in sorted(documents.items()):
            if document["kind"] != "task" or document["frontmatter"]["status"] != "open":
                continue
            for target in _relations(document["frontmatter"])["addresses"]:
                if target in targets:
                    accounted.add((identifier, "addresses", target))
                    if identifier not in reached:
                        reached[identifier] = reached[owner(target)] + 1
    # A workspace may hold several independent roots. Only an edge that touches
    # this closure has to be accounted for; one entirely outside it belongs to a
    # different Context and is not this computation's business.
    for identifier, document in documents.items():
        for key in STRONG:
            for target in _relations(document["frontmatter"])[key]:
                if not (target in documents or target in known_statements):
                    continue
                touches = identifier in reached or target in reached or owner(target) in reached
                if touches and (identifier, key, target) not in accounted:
                    raise ValueError("corpus holds a strong edge outside the reviewed closure")
    ordered = sorted(reached, key=lambda identifier: (reached[identifier],
                                                      KIND_RANK[documents[identifier]["kind"]], identifier))
    return ordered, advisory


def target_statements(documents, owned, root, reached, advisory):
    """§6.4: 文書起点は所有句、statement起点は指定句。applicable refinementの句を推移的に加える。"""
    if root in owned:
        selected = {root, *owned[root]} if documents[root]["kind"] != "task" else set(
            _relations(documents[root]["frontmatter"])["addresses"])
    else:
        selected = {root}
    changed = True
    while changed:
        changed = False
        for identifier in reached:
            if identifier in advisory or documents[identifier]["kind"] == "task":
                continue
            if identifier not in selected and any(
                    target in selected for target in _relations(documents[identifier]["frontmatter"])["refines"]):
                selected.update({identifier, *owned[identifier]})
                changed = True
    known = {statement for ids in owned.values() for statement in ids}
    return selected & known


def build(repository, root="REQ-001", purpose="verify", workspace_id="root"):
    config = read_yaml((repository / ".spec/bitz.yaml").read_text(encoding="utf-8"))
    documents = load_documents(repository)
    selected, advisory = closure(documents, root, purpose)
    commands, entries = config.get("verify", {}).get("commands", {}), []
    used = set()
    # Only `verify` names command in its closure, so only `verify` can make the
    # Bundle reference one; `interpret` and `implement` record no binding.
    for identifier in selected if purpose == "verify" else []:
        if identifier in advisory:
            continue
        frontmatter = documents[identifier]["frontmatter"]
        for test in _tests(frontmatter):
            # command名はtests[].command、文書のverifyの順で解決する。
            name = test["command"] if test["command"] is not None else frontmatter.get("verify")
            if name is not None:
                used.add(name)
    for name in sorted(used):
        command = commands[name]
        entries.append({"workspaceId": workspace_id, "name": name,
                        "argv": list(command["argv"]), "cwd": command.get("cwd", ".")})
    timeout = int(config.get("verify", {}).get("timeoutSeconds", 300))
    limits = config.get("context", {})
    context_settings = {"maxDocuments": int(limits.get("maxDocuments", 20)),
                        "maxBytes": int(limits.get("maxBytes", 131072))}
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
            "context": context_settings,
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
            "applicability": "advisory" if identifier in advisory else "applicable",
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
            "statements": sorted((_sorted_extensions(item) for item in read_statements(document["body"])),
                                 key=lambda item: item["id"]),
            "strongRelations": [{"relation": key, "target": target} for key, target in strong],
        })
    return normalize_strings(payload)


def _sorted_extensions(statement):
    """Digest正規化 §3.1.3: extensionを(namespace, term, valueSortKey)で並べる。nullはstringより前。"""
    ordered = sorted(statement["extensions"], key=lambda item: (
        item["namespace"], item["term"], item["value"] is not None, item["value"] or ""))
    return {**statement, "extensions": ordered}


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
