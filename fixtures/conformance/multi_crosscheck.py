"""複合workspaceのContext Digestの参照計算B: 入力treeから導出する。

参照計算A（multi_reference）は、review済みのDigest材料をliteralで記述する。本moduleはそのliteralを
読み込まない。fixture自身のrepo/ treeからroot設定のcatalogを読み、workspaceごとに文書を読み、
修飾ID、横断edge、到達workspaceだけの設定射影を自分で組み立てる。文書1件を読む処理と
RFC 8785 serializerは単一workspaceの参照計算Bと同じものを使い、複合workspace固有の解決だけを別に書く。
"""
from .digest_crosscheck import (KIND_BY_DIRECTORY, RELATION_KEYS, STRONG, APPLICABLE_STATUS,
                                canonical_bytes, digest, normalize_body, normalize_strings,
                                read_statements, read_yaml, split_document, _sorted_extensions)

APPLICABLE = APPLICABLE_STATUS


def catalog(repository):
    """root設定のcatalogを(root workspace ID, [(member ID, path)])として読む。"""
    config = read_yaml((repository / ".spec/bitz.yaml").read_text(encoding="utf-8"))
    if "multiWorkspace" not in config:
        raise ValueError("root設定が複合workspaceのcatalogを持っていません")
    members = [(entry["id"], entry["path"]) for entry in config["multiWorkspace"]["members"]]
    return config["workspace"]["id"], members


def qualify(workspace_id, reference):
    return reference if "::" in reference else f"{workspace_id}::{reference}"


def owner(reference):
    workspace_id, _, local = reference.partition("::")
    return f"{workspace_id}::{local.split(':')[0]}"


def load_workspaces(repository):
    """catalogの各workspaceの設定と文書を、修飾IDで1つの索引へまとめる。"""
    root_id, members = catalog(repository)
    workspaces, documents = {}, {}
    for workspace_id, path in [(root_id, ".")] + members:
        root = repository if path == "." else repository / path
        config = read_yaml((root / ".spec/bitz.yaml").read_text(encoding="utf-8"))
        if config["workspace"]["id"] != workspace_id:
            raise ValueError("catalogのIDとworkspace設定のIDが一致しません")
        workspaces[workspace_id] = {"path": path, "config": config}
        for directory, kind in KIND_BY_DIRECTORY.items():
            folder = root / ".spec" / directory
            if not folder.is_dir():
                continue
            for document in sorted(folder.glob("*.md")):
                frontmatter, raw = split_document(document.read_text(encoding="utf-8"))
                identifier = f"{workspace_id}::{frontmatter['id']}"
                if identifier in documents:
                    raise ValueError("修飾IDが重複しています")
                documents[identifier] = {
                    "workspaceId": workspace_id,
                    "kind": kind,
                    "frontmatter": frontmatter,
                    "body": normalize_body(raw),
                }
    return root_id, workspaces, documents


def relations(document):
    """宣言したrelationを、所有workspaceを基準に修飾形式へ展開する。"""
    declared = document["frontmatter"].get("relations", {})
    return {key: sorted({qualify(document["workspaceId"], target) for target in declared.get(key, [])})
            for key in RELATION_KEYS}


def tests(document):
    entries = []
    for entry in document["frontmatter"].get("tests", []):
        entries.append({
            "path": entry["path"].replace("\\", "/"),
            "covers": sorted({qualify(document["workspaceId"], target) for target in entry["covers"]}),
            "command": entry.get("command"),
        })
    return sorted(entries, key=lambda item: (item["path"], item["command"] is not None,
                                             item["command"] or "", item["covers"]))


def paths(values):
    return sorted({value.replace("\\", "/") for value in values})


def closure(documents, root):
    """`purpose=verify`のreview済み閉包。起点の文書と、それを具体化する適用対象の文書をたどる。

    このcorpusはTASK起点とdraftを持たない。単一workspaceの参照計算Bと同じく、規則で説明できない
    強いedgeが閉包に触れていれば、黙って取り込まずに拒否する。
    """
    owned = {identifier: [f"{document['workspaceId']}::{statement['id']}"
                          for statement in read_statements(document["body"])]
             for identifier, document in documents.items()}
    known = {statement for ids in owned.values() for statement in ids}
    root_document = owner(root)
    if root_document not in documents or (root != root_document and root not in known):
        raise ValueError("起点がこのcorpusに存在しません")
    reached, accounted, frontier = {root_document: 0}, set(), [root_document]
    while frontier:
        current = frontier.pop(0)
        edges = relations(documents[current])
        for key in ("requires", "refines"):
            for target in edges[key]:
                accounted.add((current, key, target))
                if owner(target) not in reached:
                    reached[owner(target)] = reached[current] + 1
                    frontier.append(owner(target))
        mine = {current, *owned.get(current, [])}
        for identifier, document in sorted(documents.items()):
            refined = [target for target in relations(document)["refines"] if target in mine]
            if not refined or identifier in reached:
                continue
            if document["frontmatter"]["status"] not in APPLICABLE:
                continue
            for target in refined:
                accounted.add((identifier, "refines", target))
            reached[identifier] = reached[current] + 1
            frontier.append(identifier)
    for identifier, document in documents.items():
        for key in STRONG:
            for target in relations(document)[key]:
                if not (target in documents or target in known):
                    continue
                touches = identifier in reached or owner(target) in reached
                if touches and (identifier, key, target) not in accounted:
                    raise ValueError("corpusに審査済み閉包の外の強いedgeがあります")
    return sorted(reached), owned


def build(repository, root="platform::REQ-001", purpose="verify"):
    root_id, workspaces, documents = load_workspaces(repository)
    request = root.partition("::")[0]
    if request not in workspaces:
        raise ValueError("起点のworkspaceがcatalogにありません")
    selected, owned = closure(documents, root)
    reached_workspaces = {documents[identifier]["workspaceId"] for identifier in selected}
    # request workspaceを先頭、以降はID辞書順。到達しなかったworkspaceは材料へ入れない。
    ordered_workspaces = [request] + sorted(reached_workspaces - {request})

    commands, timeouts = [], []
    for workspace_id in sorted(reached_workspaces):
        config = workspaces[workspace_id]["config"]
        defined = config.get("verify", {}).get("commands", {})
        used = set()
        for identifier in selected:
            document = documents[identifier]
            if document["workspaceId"] != workspace_id:
                continue
            for entry in tests(document):
                name = entry["command"] if entry["command"] is not None else document["frontmatter"].get("verify")
                if name is not None:
                    used.add(name)
        if not used:
            continue
        timeouts.append({"workspaceId": workspace_id,
                         "timeoutSeconds": int(config.get("verify", {}).get("timeoutSeconds", 300))})
        for name in sorted(used):
            command = defined[name]
            commands.append({"workspaceId": workspace_id, "name": name,
                             "argv": list(command["argv"]), "cwd": command.get("cwd", ".")})

    request_config = workspaces[request]["config"]
    limits = request_config.get("context", {})
    payload = {
        "digestVersion": "1.0",
        "specSchemaVersion": request_config["schemaVersion"],
        "earsAiVersion": request_config["earsAi"],
        "resolverVersion": "1.0",
        "purpose": purpose,
        "requestWorkspaceId": request,
        "roots": [root],
        "workspaces": [{"id": workspace_id, "path": workspaces[workspace_id]["path"]}
                       for workspace_id in ordered_workspaces],
        "documents": [],
        "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": workspace_id,
                            "schemaVersion": workspaces[workspace_id]["config"]["schemaVersion"],
                            "earsAi": workspaces[workspace_id]["config"]["earsAi"],
                            "language": workspaces[workspace_id]["config"]["language"]}
                           for workspace_id in sorted(reached_workspaces)],
            "context": {"maxDocuments": int(limits.get("maxDocuments", 20)),
                        "maxBytes": int(limits.get("maxBytes", 131072))},
            "verifyTimeouts": timeouts,
            "commands": commands,
        },
    }
    edges = set()
    for identifier in selected:
        document = documents[identifier]
        workspace_id = document["workspaceId"]
        declared = relations(document)
        strong = sorted({(key, target) for key in STRONG for target in declared[key]})
        for key in RELATION_KEYS:
            for target in declared[key]:
                if target.partition("::")[0] != workspace_id:
                    edges.add((identifier, key, target))
        payload["documents"].append({
            "id": identifier,
            "workspaceId": workspace_id,
            "kind": document["kind"],
            "status": document["frontmatter"]["status"],
            "applicability": "applicable",
            "frontmatter": {
                "id": identifier,
                "title": document["frontmatter"]["title"],
                "status": document["frontmatter"]["status"],
                "relations": declared,
                "implements": paths(document["frontmatter"].get("implements", [])),
                "tests": tests(document),
                "verify": document["frontmatter"].get("verify"),
                "changes": paths(document["frontmatter"].get("changes", [])),
            },
            "bodyText": document["body"],
            "statements": sorted((_sorted_extensions(dict(statement, id=f"{workspace_id}::{statement['id']}"))
                                  for statement in read_statements(document["body"])),
                                 key=lambda item: item["id"]),
            "strongRelations": [{"relation": key, "target": target} for key, target in strong],
        })
    payload["documents"].sort(key=lambda item: item["id"])
    payload["crossWorkspaceEdges"] = [{"relation": key, "source": source, "target": target}
                                      for source, key, target in sorted(edges)]
    return normalize_strings(payload)


def references(repository, root="platform::REQ-001"):
    """同じDigest材料を、独立に書いた2系統で計算する。"""
    from . import multi_reference

    literal = multi_reference.canonical_bytes(multi_reference.reviewed_digest_input())
    derived = canonical_bytes(build(repository, root))
    if literal != derived:
        raise ValueError("reference AとBのCanonical JSONが一致しません")
    if multi_reference.digest(literal) != digest(derived):
        raise ValueError("reference AとBのDigestが一致しません")
    return literal
