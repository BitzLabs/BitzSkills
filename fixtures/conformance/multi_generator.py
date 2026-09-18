"""複合workspaceのresource上限fixtureの入力を決定論的に生成する（Core操作は実装しない）。

[ADR-048](../../docs/02.設計書/10_決定記録/ADR-048_適合fixtureの生成入力とGit構造operationを確定する.md)に従い、
上限境界のfixtureは`repo/`の代わりにdataset manifestを持つ。本moduleはfixture harness側の参照実装であり、
dataset manifestから入力treeを(path, 内容)の列として流す。同じmanifestからは常に同じ列を返す。

計数（`count`）は生成計画を読まず、生成したbyte列だけからdimensionを数え直す。dataset manifestの宣言値と
この計数の一致が、fixtureがちょうど1つのdimensionだけを狙った規模にしていることの証拠になる。
"""
import re

# 複合workspace仕様 §10のhard limit。
LIMITS = {
    "memberCount": 100,
    "specFileCount": 10000,
    "inputBytes": 256 * 1024 * 1024,
    "statementCount": 100000,
    "relationEdgeCount": 1000000,
    "traceEntryCount": 1000000,
    "commandDefinitionCount": 10000,
    "verifyBindingCount": 10000,
}
DIMENSIONS = tuple(LIMITS)
# 安全な入出力・互換性 §4の入力上限。1文書の配列項目と規範文は1,000、設定は64 KiB、SPECは1 MiB。
ITEMS_PER_DOCUMENT = 1000
COMMANDS_PER_WORKSPACE = 800
PADDING_PER_DOCUMENT = 900000
BASE_MEMBERS = 2
PADDING_LINE = "この段落は入力byte数を上限の境界へ合わせるための固定文である。\n"
FILLER_BODY = "## Context\n\n上限境界の入力を満たすための固定文書である。\n"


def workspace_ids(members):
    return ["platform"] + [f"m{index:03d}" for index in range(1, members + 1)]


def workspace_path(workspace_id):
    return "." if workspace_id == "platform" else f"members/{workspace_id}"


def split(total, buckets):
    """totalをbuckets個へできるだけ均等に分け、余りを前から配る。"""
    if buckets <= 0:
        return []
    base, extra = divmod(total, buckets)
    return [base + (1 if index < extra else 0) for index in range(buckets)]


def chunks(total, cap):
    """totalをcap以下の塊へ分ける。"""
    if total <= 0:
        return []
    count, remainder = divmod(total, cap)
    return [cap] * count + ([remainder] if remainder else [])


def plan(dimension, value):
    """1つのdimensionだけを指定の値にし、ほかを通常規模へ保つ生成計画を返す。"""
    if dimension not in LIMITS:
        raise ValueError(f"未知のdimensionです: {dimension}")
    members = BASE_MEMBERS
    bindings = None
    commands = None
    if dimension == "memberCount":
        members = value
    if dimension in {"commandDefinitionCount", "verifyBindingCount"}:
        # 設定fileの64 KiB上限があるため、commandはworkspaceへ分けて置く。
        needed = -(-value // COMMANDS_PER_WORKSPACE)
        members = max(BASE_MEMBERS, needed - 1)
    workspaces = workspace_ids(members)
    if dimension == "verifyBindingCount":
        bindings = split(value, len(workspaces))
    else:
        bindings = [1] * len(workspaces)
    if dimension == "commandDefinitionCount":
        commands = split(value, len(workspaces))
    else:
        commands = [max(1, count) for count in bindings]
    profile = {
        "dimension": dimension,
        "value": value,
        "workspaces": workspaces,
        "bindings": bindings,
        "commands": commands,
        "statementDocuments": [],
        "edgeDocuments": [],
        "traceDocuments": [],
        "fillerDocuments": 0,
        "paddingBytes": 0,
    }
    if dimension == "statementCount":
        profile["statementDocuments"] = chunks(value - sum(bindings), ITEMS_PER_DOCUMENT)
    if dimension == "relationEdgeCount":
        profile["edgeDocuments"] = chunks(value, ITEMS_PER_DOCUMENT)
    if dimension == "traceEntryCount":
        # bindingのtest対応も2件ずつ数えるので、TASKのchangesで残りを満たす。
        profile["traceDocuments"] = chunks(value - 2 * sum(bindings), ITEMS_PER_DOCUMENT)
    if dimension == "specFileCount":
        documents = len(workspaces)
        profile["fillerDocuments"] = value - documents
    if dimension == "inputBytes":
        profile["paddingBytes"] = value
    return profile


def render_config(profile, index):
    workspaces = profile["workspaces"]
    workspace_id = workspaces[index]
    lines = ['schemaVersion: "1.0"\n', "language: ja\n", 'earsAi: "1.0"\n',
             "workspace:\n", f"  id: {workspace_id}\n"]
    if index == 0 and len(workspaces) > 1:
        lines.append("multiWorkspace:\n")
        lines.append("  members:\n")
        for member in workspaces[1:]:
            lines.append(f"    - id: {member}\n")
            lines.append(f"      path: {workspace_path(member)}\n")
    lines.append("verify:\n")
    lines.append("  commands:\n")
    for number in range(1, profile["commands"][index] + 1):
        lines.append(f"    c{number:05d}:\n")
        lines.append('      argv: ["/bin/true", "{tests}"]\n')
        lines.append("      cwd: .\n")
    return "".join(lines).encode("utf-8")


def statement_line(document_id, number, text="秘密情報を出力しない"):
    return (f"- [{document_id}:AC-{number:04d}] [ACTOR:TargetSystem] [ALWAYS] [MUST] "
            f"[CONSTRAINT] {text}。\n")


def render_binding_document(document_id, statements, first_command, first_test):
    """1文書に、statements件の規範文と同数のtest対応を置く。1対応が1 bindingになる。"""
    head = [f"---\nid: {document_id}\ntitle: 上限境界の実装方針\nstatus: approved\ntests:\n"]
    for offset in range(statements):
        head.append(f"  - path: tests/test_{first_test + offset:05d}.py\n")
        head.append(f"    covers: [{document_id}:AC-{offset + 1:04d}]\n")
        head.append(f"    command: c{first_command + offset:05d}\n")
    head.append("---\n")
    body = [f"\n# {document_id} 上限境界の実装方針\n\n## Contract\n\n"]
    for offset in range(statements):
        body.append(statement_line(document_id, offset + 1))
    return ("".join(head) + "".join(body)).encode("utf-8")


def render_statement_document(document_id, statements):
    head = f"---\nid: {document_id}\ntitle: 上限境界の規範\nstatus: approved\n---\n"
    body = [f"\n# {document_id} 上限境界の規範\n\n## Contract\n\n"]
    for offset in range(statements):
        body.append(statement_line(document_id, offset + 1))
    return (head + "".join(body)).encode("utf-8")


def render_edge_document(document_id, target, edges):
    head = [f"---\nid: {document_id}\ntitle: 上限境界の関係\nstatus: approved\nrelations:\n  requires: ["]
    head.append(", ".join([target] * edges))
    head.append("]\n---\n")
    return ("".join(head) + f"\n# {document_id} 上限境界の関係\n\n## Context\n\n関係の件数を満たす。\n").encode("utf-8")


def render_trace_document(document_id, first_path, entries):
    head = [f"---\nid: {document_id}\ntitle: 上限境界の変更計画\nstatus: open\nchanges: ["]
    head.append(", ".join(f"src/gen/a{first_path + offset:07d}.py" for offset in range(entries)))
    head.append("]\n---\n")
    return ("".join(head) + f"\n# {document_id} 上限境界の変更計画\n\n## Objective\n\n変更pathの件数を満たす。\n").encode("utf-8")


def render_filler_document(document_id):
    return (f"---\nid: {document_id}\ntitle: 上限境界の補充文書\nstatus: approved\n---\n"
            f"\n# {document_id} 上限境界の補充文書\n\n{FILLER_BODY}").encode("utf-8")


def render_padding_document(document_id, size):
    head = (f"---\nid: {document_id}\ntitle: 上限境界の補充文書\nstatus: approved\n---\n"
            f"\n# {document_id} 上限境界の補充文書\n\n## Context\n\n").encode("utf-8")
    line = PADDING_LINE.encode("utf-8")
    if size < len(head) + len(line):
        raise ValueError("補充文書の大きさが小さすぎます")
    body = line * ((size - len(head)) // len(line))
    remainder = size - len(head) - len(body)
    # 端数は空白で埋め、最後の1 byteを改行にする。
    return head + body + (b" " * (remainder - 1) + b"\n" if remainder else b"")


def emit(profile):
    """(repository root相対path, 内容)をpath昇順に依存しない決定論的な順序で流す。"""
    workspaces = profile["workspaces"]
    entries = []
    command_cursor, test_cursor, document_number = 1, 1, 1
    for index, workspace_id in enumerate(workspaces):
        prefix = "" if index == 0 else f"{workspace_path(workspace_id)}/"
        entries.append((f"{prefix}.spec/bitz.yaml", render_config(profile, index)))
        statements = profile["bindings"][index]
        document_id = f"TECH-{document_number:06d}"
        document_number += 1
        for offset in range(statements):
            entries.append((f"{prefix}tests/test_{test_cursor + offset:05d}.py",
                            b"def test_generated():\n    assert True\n"))
        entries.append((f"{prefix}.spec/technical/{document_id}.md",
                        render_binding_document(document_id, statements, 1, test_cursor)))
        test_cursor += statements
        command_cursor = 1
    anchor = "TECH-000001"
    for statements in profile["statementDocuments"]:
        document_id = f"TECH-{document_number:06d}"
        document_number += 1
        entries.append((f".spec/technical/{document_id}.md",
                        render_statement_document(document_id, statements)))
    for edges in profile["edgeDocuments"]:
        document_id = f"TECH-{document_number:06d}"
        document_number += 1
        entries.append((f".spec/technical/{document_id}.md",
                        render_edge_document(document_id, anchor, edges)))
    path_cursor = 1
    for items in profile["traceDocuments"]:
        document_id = f"TASK-{document_number:06d}"
        document_number += 1
        entries.append((f".spec/tasks/{document_id}.md",
                        render_trace_document(document_id, path_cursor, items)))
        path_cursor += items
    for _ in range(profile["fillerDocuments"]):
        document_id = f"TECH-{document_number:06d}"
        document_number += 1
        entries.append((f".spec/technical/{document_id}.md", render_filler_document(document_id)))
    if profile["paddingBytes"]:
        current = sum(len(content) for path, content in entries if is_input(path))
        remaining = profile["paddingBytes"] - current
        if remaining < 0:
            raise ValueError("既定の入力が指定byte数を超えています")
        while remaining > 0:
            document_id = f"TECH-{document_number:06d}"
            document_number += 1
            size = min(PADDING_PER_DOCUMENT, remaining)
            entries.append((f".spec/technical/{document_id}.md",
                            render_padding_document(document_id, size)))
            remaining -= size
    return entries


def is_input(path):
    """inputBytesが数えるのは、設定とSPEC Markdownだけである。"""
    return path.endswith("/bitz.yaml") or path == ".spec/bitz.yaml" or path.endswith(".md")


STATEMENT = re.compile(r"^- \[[A-Za-z0-9:\-]+\] ")
COMMAND = re.compile(r"^    ([a-z][a-z0-9]*):$")


def count(entries):
    """生成したbyte列だけから8つのdimensionを数え直す。生成計画は読まない。"""
    totals = {name: 0 for name in DIMENSIONS}
    bindings = set()
    for path, content in entries:
        if is_input(path):
            totals["inputBytes"] += len(content)
        text = content.decode("utf-8")
        if path.endswith("bitz.yaml"):
            workspace_id = None
            in_members = False
            for line in text.split("\n"):
                if line.startswith("  id: ") and workspace_id is None:
                    workspace_id = line[len("  id: "):]
                if line.startswith("  members:"):
                    in_members = True
                if in_members and line.startswith("    - id: "):
                    totals["memberCount"] += 1
                if COMMAND.match(line):
                    totals["commandDefinitionCount"] += 1
            continue
        if not path.endswith(".md"):
            continue
        totals["specFileCount"] += 1
        workspace_id = path.rsplit("/.spec/", 1)[0] if "/.spec/" in path else "."
        head, _, body = text.partition("\n---\n")
        for line in body.split("\n"):
            if STATEMENT.match(line):
                totals["statementCount"] += 1
        for line in head.split("\n"):
            if line.startswith("  requires: ["):
                totals["relationEdgeCount"] += len(line[len("  requires: ["):-1].split(", "))
            if line.startswith("changes: ["):
                totals["traceEntryCount"] += len(line[len("changes: ["):-1].split(", "))
            if line.startswith("  - path: "):
                totals["traceEntryCount"] += 1
            if line.startswith("    covers: ["):
                totals["traceEntryCount"] += len(line[len("    covers: ["):-1].split(", "))
            if line.startswith("    command: "):
                bindings.add((workspace_id, line[len("    command: "):]))
    totals["verifyBindingCount"] = len(bindings)
    return totals


def workspace_counts(entries):
    """workspaceごとの(完全検査する文書数, 規範文数)を、生成したbyte列から数える。"""
    counts = {}
    for path, content in entries:
        if path.endswith("bitz.yaml"):
            workspace = path[: -len("/.spec/bitz.yaml")] if path != ".spec/bitz.yaml" else "."
            counts.setdefault(workspace, [0, 0])
        if not path.endswith(".md"):
            continue
        workspace = path.rsplit("/.spec/", 1)[0] if "/.spec/" in path else "."
        entry = counts.setdefault(workspace, [0, 0])
        entry[0] += 1
        _, _, body = content.decode("utf-8").partition("\n---\n")
        entry[1] += sum(1 for line in body.split("\n") if STATEMENT.match(line))
    return {workspace: tuple(value) for workspace, value in counts.items()}


def dataset(fixture_id, dimension, value):
    """fixtureへcommitするdataset manifest。宣言値は生成物の計数と一致する。"""
    profile = plan(dimension, value)
    totals = count(emit(profile))
    if totals[dimension] != value:
        raise ValueError(f"生成計画が{dimension}を満たしていません")
    return {
        "schemaVersion": "1.0",
        "fixtureId": fixture_id,
        "dimension": dimension,
        "value": value,
        "limit": LIMITS[dimension],
        "crosses": value > LIMITS[dimension],
        "dimensions": {name: totals[name] for name in DIMENSIONS},
    }


def reduced(manifest, factor=100):
    """縮小profile。上限も同じ比率で縮め、越える／越えないの関係をそのまま保つ。"""
    dimension, value = manifest["dimension"], manifest["value"]
    limit = LIMITS[dimension]
    if dimension == "memberCount":
        scaled_limit = max(4, limit // 10)
    elif dimension == "inputBytes":
        scaled_limit = max(200000, limit // (factor * 10))
    else:
        scaled_limit = max(6, limit // factor)
    offset = value - limit
    return {"dimension": dimension, "value": scaled_limit + offset, "limit": scaled_limit,
            "crosses": value > limit, "reducedFrom": value}


def generate(manifest):
    """dataset manifestから入力treeを流し、宣言した全dimensionと一致することを確かめる。"""
    entries = emit(plan(manifest["dimension"], manifest["value"]))
    totals = count(entries)
    if totals != manifest["dimensions"]:
        raise ValueError("生成物のdimensionがdataset manifestと一致しません")
    return entries
