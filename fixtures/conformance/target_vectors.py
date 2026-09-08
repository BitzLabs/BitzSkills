"""Reference calculation over resolved, applicable test graphs; no Core parser/CLI."""
import copy
import hashlib
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
KINDS = ["REQ", "TECH", "TECH_EMPTY", "STATEMENT", "TASK", "ADR"]
PURPOSES = ["interpret", "implement", "verify"]


def reference(case):
    nodes = {n["id"]: n for n in case["graph"]}
    statements = {s["id"]: (n["id"], s["line"]) for n in nodes.values() for s in n["statements"]}
    if len(nodes) != len(case["graph"]) or len(statements) != sum(len(n["statements"]) for n in nodes.values()):
        raise ValueError("duplicate graph identity")

    def owner(identifier):
        if identifier in nodes:
            return identifier
        if identifier in statements:
            return statements[identifier][0]
        raise ValueError(f"unresolved reference: {identifier}")

    for n in nodes.values():
        allowed = {"REQ": {"approved"}, "TECH": {"approved"}, "ADR": {"accepted"}, "TASK": {"open", "done"}}
        if n["status"] not in allowed[n["kind"]]:
            raise ValueError("state outside applicable reference graph scope")
        if not re.fullmatch(r"(?:[a-z][a-z0-9-]{0,31}::)?" + n["kind"] + r"-[0-9]{3,}", n["id"]):
            raise ValueError("document ID/kind mismatch")
        if n["kind"] in {"ADR", "TASK"} and n["statements"]:
            raise ValueError("ADR/TASK cannot own statements")
        for s in n["statements"]:
            if not s["id"].startswith(n["id"] + ":"):
                raise ValueError("statement owner mismatch")
        for relation in ("requires", "refines", "addresses", "related"):
            for target in n[relation]:
                target_owner = owner(target)
                if relation == "requires" and target not in nodes:
                    raise ValueError("requires must target a document")
                if relation == "addresses" and (n["kind"] != "TASK" or (target not in statements and not (nodes[target_owner]["kind"] == "TECH" and not nodes[target_owner]["statements"]))):
                    raise ValueError("invalid addresses type")
                if relation == "refines" and (n["kind"] not in {"REQ", "TECH"} or nodes[target_owner]["kind"] not in ({"REQ"} if n["kind"] == "REQ" else {"REQ", "TECH"})):
                    raise ValueError("invalid refines type")
    active, visited = set(), set()

    def acyclic(identifier):
        if identifier in active:
            raise ValueError("strong dependency cycle")
        if identifier in visited:
            return
        active.add(identifier)
        for target in nodes[identifier]["requires"] + nodes[identifier]["refines"]:
            acyclic(owner(target))
        active.remove(identifier)
        visited.add(identifier)

    for identifier in nodes:
        acyclic(identifier)
    roots = sorted(set(case["roots"]))
    root_docs = sorted({owner(r) for r in roots})
    purpose = case["purpose"]
    if purpose == "implement" and any(nodes[r]["kind"] == "TASK" and nodes[r]["status"] != "open" for r in root_docs):
        raise ValueError("inapplicable TASK root outside reference graph scope")
    if case["id"].startswith("BASIC-"):
        r = roots[0]
        n = nodes[owner(r)]
        kind = "STATEMENT" if r in statements else "TECH_EMPTY" if n["kind"] == "TECH" and not n["statements"] else n["kind"]
        if len(roots) != 1 or case["rootKind"] != kind:
            raise ValueError("basic root kind mismatch")
    if purpose != "interpret" and any(nodes[r]["kind"] == "ADR" for r in root_docs):
        return {"outcome": "invocation_error", "exitCode": 4}

    selected = set()
    for r in roots:
        if r in statements:
            selected.add(r)
        elif nodes[r]["kind"] == "TASK":
            if purpose != "interpret":
                selected.update(nodes[r]["addresses"])
        elif nodes[r]["kind"] in {"REQ", "TECH"}:
            selected.add(r)
            selected.update(s["id"] for s in nodes[r]["statements"])
    changed = True
    while changed:
        previous = selected.copy()
        for n in nodes.values():
            if any(t in selected for t in n["refines"]):
                selected.add(n["id"])
                selected.update(s["id"] for s in n["statements"])
        changed = selected != previous
    targets = set() if purpose == "interpret" else selected & statements.keys()

    # Shortest distances in the purpose-specific context traversal graph.
    distances = {r: 0 for r in root_docs}
    queue = list(root_docs)
    while queue:
        current = queue.pop(0)
        n = nodes[current]
        neighbors = {owner(t) for t in n["requires"] + n["refines"]}
        if current in root_docs and n["kind"] == "TASK" and purpose != "interpret":
            neighbors.update(owner(t) for t in n["addresses"])
        for candidate in nodes.values():
            if any(owner(t) == current for t in candidate["refines"]):
                neighbors.add(candidate["id"])
            if purpose == "implement" and candidate["kind"] == "TASK" and candidate["status"] == "open" and any(t in targets and owner(t) == current for t in candidate["addresses"]):
                neighbors.add(candidate["id"])
        for neighbor in sorted(neighbors):
            if neighbor not in distances:
                distances[neighbor] = distances[current] + 1
                queue.append(neighbor)
    rank = {kind: i for i, kind in enumerate(["REQ", "TECH", "ADR", "TASK"])}
    context = sorted(distances, key=lambda d: (distances[d], rank[nodes[d]["kind"]], d))
    positions = {identifier: index for index, identifier in enumerate(context)}
    target_order = sorted(targets, key=lambda s: (positions[owner(s)], statements[s][1], s))
    adjacent = {s["id"] for r in roots if r in statements for s in nodes[owner(r)]["statements"] if s["id"] != r}
    adjacent -= targets
    return {"outcome": "expanded", "rootDocuments": root_docs, "contextDocuments": context,
            "targetStatements": target_order, "adjacentStatements": sorted(adjacent, key=lambda s: (statements[s][1], s))}


def validate(data=None):
    data = json.loads((HERE / "targets/cases.json").read_text()) if data is None else data
    schema = json.loads((HERE / "targets/cases.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    errors = []
    for error in Draft202012Validator(schema).iter_errors(data):
        errors.append(error.message)
    if errors:
        return {"status": "Failed", "errors": errors}
    contract = HERE.parents[1] / "docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md"
    if hashlib.sha256(contract.read_bytes()).hexdigest() != data["contractSha256"]:
        errors.append("target contract changed: review fixed expectations before updating hash")
    ids = [case["id"] for case in data["cases"]]
    if len(ids) != len(set(ids)):
        errors.append("duplicate case ID")
    pairs = {(case["rootKind"], case["purpose"]) for case in data["cases"] if case["id"].startswith("BASIC-")}
    if pairs != {(k, p) for k in KINDS for p in PURPOSES}:
        errors.append("missing basic kind/purpose combination")
    matrix = (HERE.parents[1] / "docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md").read_text()
    families = set(re.findall(r"\| `((?:SINGLE|MONO)-\d{3})(?:-\d{2})?`", matrix))
    for case in data["cases"]:
        try:
            if not set(case["matrixFamilies"]) <= families:
                raise ValueError("unknown matrix family")
            actual = reference(case)
            if actual != case["expected"]:
                errors.append(f"{case['id']}: expected {case['expected']}, got {actual}")
            shuffled = copy.deepcopy(case)
            shuffled["graph"].reverse()
            shuffled["roots"].reverse()
            for node in shuffled["graph"]:
                for key in ("statements", "requires", "refines", "addresses", "related"):
                    node[key].reverse()
            if reference(shuffled) != actual:
                errors.append(f"{case['id']}: input order changes result")
        except (ValueError, KeyError) as error:
            errors.append(f"{case['id']}: {error}")
    return {"status": "Passed" if not errors else "Failed", "cases": len(ids), "basicCombinations": len(pairs), "errors": errors}
