"""解決済みで適用可能なtest graphに対する参照計算（CoreのParser／CLIではない）。"""
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
        raise ValueError("graphの同一性が重複しています")

    def owner(identifier):
        if identifier in nodes:
            return identifier
        if identifier in statements:
            return statements[identifier][0]
        raise ValueError(f"未解決の参照です: {identifier}")

    for n in nodes.values():
        allowed = {"REQ": {"approved"}, "TECH": {"approved"}, "ADR": {"accepted"}, "TASK": {"open", "done"}}
        if n["status"] not in allowed[n["kind"]]:
            raise ValueError("状態が適用可能な参照graphの範囲外です")
        if not re.fullmatch(r"(?:[a-z][a-z0-9-]{0,31}::)?" + n["kind"] + r"-[0-9]{3,}", n["id"]):
            raise ValueError("文書IDと種別が一致しません")
        if n["kind"] in {"ADR", "TASK"} and n["statements"]:
            raise ValueError("ADRとTASKは規範文を持てません")
        for s in n["statements"]:
            if not s["id"].startswith(n["id"] + ":"):
                raise ValueError("規範文の所有者が一致しません")
        for relation in ("requires", "refines", "addresses", "related"):
            for target in n[relation]:
                target_owner = owner(target)
                if relation == "requires" and target not in nodes:
                    raise ValueError("requiresの参照先は文書である必要があります")
                if relation == "addresses" and (n["kind"] != "TASK" or (target not in statements and not (nodes[target_owner]["kind"] == "TECH" and not nodes[target_owner]["statements"]))):
                    raise ValueError("addressesの型が不正です")
                if relation == "refines" and (n["kind"] not in {"REQ", "TECH"} or nodes[target_owner]["kind"] not in ({"REQ"} if n["kind"] == "REQ" else {"REQ", "TECH"})):
                    raise ValueError("refinesの型が不正です")
    active, visited = set(), set()

    def acyclic(identifier):
        if identifier in active:
            raise ValueError("強い依存が循環しています")
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
        raise ValueError("適用できないTASK起点が参照graphの範囲外です")
    if case["id"].startswith("BASIC-"):
        r = roots[0]
        n = nodes[owner(r)]
        kind = "STATEMENT" if r in statements else "TECH_EMPTY" if n["kind"] == "TECH" and not n["statements"] else n["kind"]
        if len(roots) != 1 or case["rootKind"] != kind:
            raise ValueError("基本caseの起点の種別が一致しません")
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

    # purposeごとのContextの探索graphにおける最短距離。
    distances = {r: 0 for r in root_docs}
    queue = list(root_docs)
    while queue:
        current = queue.pop(0)
        n = nodes[current]
        task_root = current in root_docs and n["kind"] == "TASK" and purpose != "interpret"
        # 関係・トレースモデル §6.3: verifyの起点TASKはrequires閉包を含めない。
        followed = [] if task_root and purpose == "verify" else n["requires"]
        neighbors = {owner(t) for t in followed + n["refines"]}
        if task_root:
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
        errors.append("target契約が変わりました。hashを更新する前に固定した期待値をreviewしてください")
    ids = [case["id"] for case in data["cases"]]
    if len(ids) != len(set(ids)):
        errors.append("ケースIDが重複しています")
    pairs = {(case["rootKind"], case["purpose"]) for case in data["cases"] if case["id"].startswith("BASIC-")}
    if pairs != {(k, p) for k in KINDS for p in PURPOSES}:
        errors.append("基本の種別とpurposeの組合せが欠けています")
    matrix = (HERE.parents[1] / "docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md").read_text()
    families = set(re.findall(r"\| `((?:SINGLE|MULTI)-\d{3})(?:-\d{2})?`", matrix))
    for case in data["cases"]:
        try:
            if not set(case["matrixFamilies"]) <= families:
                raise ValueError("未知のmatrix familyです")
            actual = reference(case)
            if actual != case["expected"]:
                errors.append(f"{case['id']}: 期待値 {case['expected']}、実際 {actual}")
            shuffled = copy.deepcopy(case)
            shuffled["graph"].reverse()
            shuffled["roots"].reverse()
            for node in shuffled["graph"]:
                for key in ("statements", "requires", "refines", "addresses", "related"):
                    node[key].reverse()
            if reference(shuffled) != actual:
                errors.append(f"{case['id']}: 入力順で結果が変わります")
        except (ValueError, KeyError) as error:
            errors.append(f"{case['id']}: {error}")
    return {"status": "Passed" if not errors else "Failed", "cases": len(ids), "basicCombinations": len(pairs), "errors": errors}
