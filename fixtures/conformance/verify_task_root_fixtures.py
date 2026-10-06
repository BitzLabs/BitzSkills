"""TASKを起点とする`verify`のレビュー済みの入力と期待値（Coreの公開操作は実行しない）。

`SINGLE-068`は、状態が`done`のTASKを`verify`する。`cancelled`の起点を遮断する`SINGLE-067`に
対応する成功側のfixtureである。コンテキストは[関係・トレースモデル §6.3]に従い、TASKの起点は
`addresses`の対象を所有する文書を`contextDocuments`に加える。

`SINGLE-137`と`SINGLE-138`は、状態が`open`の起点のTASK-001が`requires`で先行のTASK-002を参照する。
目的`verify`でも先行TASKがすべて`done`でなければ`blocked`とする（関係・トレースモデル §6.3、ADR-029）。
`SINGLE-137`は先行TASKが`open`で`CTX-TASK-DEPENDENCY-001`の`blocked`、`SINGLE-138`は先行TASKが`done`で
`passed`である。`verify`の起点のTASKは`requires`の閉包を含めないので、先行TASKはコンテキストへ入らず、
その`addresses`の参照先も検証対象の義務へ加えない。

`SINGLE-146`は、状態が`done`の起点のTASK-001が、状態が`draft`のREQ-002を`requires`する。起点の`requires`の閉包の文書
（TASKを除く）はコンテキストへ含めないが、通常の適用可能性を検査するので（関係・トレースモデル §6.3、ADR-034）、
適用できないREQ-002の`CTX-STATE-001`で`blocked`とする。
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from .harness import setup
from .initial_fixtures import observe, compare_state
from .expansion_fixtures import CONFIG, ROOT_ONE_TEST_YAML, TEST_BODY, requirement, task as task_document_parts

HERE = Path(__file__).resolve().parent
IDENTIFIER = "SINGLE-068"
STATE_IDENTIFIER = "SINGLE-146"
IDENTIFIERS = ("SINGLE-068", "SINGLE-137", "SINGLE-138", STATE_IDENTIFIER)
INAPPLICABLE_PATH = ".spec/requirements/REQ-002.md"
ADDRESSED_PATH = ".spec/requirements/REQ-001.md"
TASK_PATH = ".spec/tasks/TASK-001.md"
PREREQUISITE_PATH = ".spec/tasks/TASK-002.md"
# `SINGLE-137`と`SINGLE-138`の先行TASK-002の状態。
PREREQUISITE_STATUS = {"SINGLE-137": "open", "SINGLE-138": "done"}
TITLE = "完了済みの実装作業"
TASK_DOCUMENT = (
    "---\n"
    f"id: TASK-001\ntitle: {TITLE}\nstatus: done\n"
    "relations:\n  addresses: [REQ-001:AC-01]\n"
    "changes: [src/auth.py]\n"
    "---\n"
    f"\n# TASK-001 {TITLE}\n"
    "\n## Objective\n\nAC-01を実装した。done TASKは再検証できる。\n"
)
TASK_BODY = TASK_DOCUMENT[TASK_DOCUMENT.index("\n---\n") + 5:].lstrip("\n")
DEPENDENT_TITLE = "先行作業のある実装作業"
DEPENDENT_DOCUMENT = (
    "---\n"
    f"id: TASK-001\ntitle: {DEPENDENT_TITLE}\nstatus: open\n"
    "relations:\n  requires: [TASK-002]\n  addresses: [REQ-001:AC-01]\n"
    "changes: [src/auth.py]\n"
    "---\n"
    f"\n# TASK-001 {DEPENDENT_TITLE}\n"
    "\n## Objective\n\nAC-01を実装する。先行TASK-002の状態でverifyの結果が決まる。\n"
)
DEPENDENT_BODY = DEPENDENT_DOCUMENT[DEPENDENT_DOCUMENT.index("\n---\n") + 5:].lstrip("\n")
PREREQUISITE_TITLE = "先行作業"


# `SINGLE-138`の先行TASK-002は、起点のTASK-001が`addresses`しない`REQ-001:AC-02`を`addresses`する。
# 先行TASKの`addresses`の参照先を起点の義務へ加えないこと（`verify` §3、関係・トレースモデル §6.4の4.）を判別する。
PREREQUISITE_ADDRESSES = {"SINGLE-138": ["REQ-001:AC-02"]}


def prerequisite_document(identifier):
    relations = ""
    if identifier in PREREQUISITE_ADDRESSES:
        relations = "relations:\n  addresses: [" + ", ".join(PREREQUISITE_ADDRESSES[identifier]) + "]\n"
    return (
        "---\n"
        f"id: TASK-002\ntitle: {PREREQUISITE_TITLE}\nstatus: {PREREQUISITE_STATUS[identifier]}\n"
        f"{relations}"
        "---\n"
        f"\n# TASK-002 {PREREQUISITE_TITLE}\n"
        "\n## Objective\n\nTASK-001より先に完了する作業。"
        + ("AC-02を実装した。\n" if identifier in PREREQUISITE_ADDRESSES else "\n")
    )


# AC-01だけを`addresses`するので、AC-02は検証対象ではなく、そのテストも解決しない。
TARGET_STATEMENTS = ["REQ-001:AC-01"]
TEST_PATHS = ["tests/test_auth.py"]


def state_documents():
    """`SINGLE-146`の入力。TASK-001（`done`）は、REQ-002（`draft`）を`requires`し、REQ-001:AC-01を`addresses`する。
    REQ-001（`approved`）はテスト対応を持つので、REQ-002の適用可能性だけが結果を決める。"""
    head, body = requirement("REQ-001", "対象要求", [("REQ-001:AC-01", "入力を検証する")], ROOT_ONE_TEST_YAML)
    req001 = head + "\n" + body
    head, body = requirement(
        "REQ-002", "検討中の前提要求", [("REQ-002:AC-01", "前提を満たす")], verification="テスト対応は宣言しない。")
    req002 = head.replace("status: approved", "status: draft") + "\n" + body
    head, body = task_document_parts(
        "TASK-001", "検討中の前提を持つ完了済みの作業", "done",
        "relations:\n  requires: [REQ-002]\n  addresses: [REQ-001:AC-01]\n")
    return {ADDRESSED_PATH: req001, INAPPLICABLE_PATH: req002, TASK_PATH: head + "\n" + body}


def reviewed_inputs(identifier=IDENTIFIER):
    if identifier == STATE_IDENTIFIER:
        return {digest_reference.CONFIG_PATH: CONFIG.encode(), "tests/test_root.py": TEST_BODY.encode(),
                **{path: text.encode() for path, text in state_documents().items()}}
    base = digest_reference.reviewed_inputs("SINGLE-042")
    if identifier == IDENTIFIER:
        return {**base, TASK_PATH: TASK_DOCUMENT.encode()}
    return {**base, TASK_PATH: DEPENDENT_DOCUMENT.encode(),
            PREREQUISITE_PATH: prerequisite_document(identifier).encode()}


def reviewed_digest_input(identifier=IDENTIFIER):
    """目的`verify`のコンテキスト。起点のTASK-001の`requires`の閉包は含めないので、`SINGLE-138`でも
    先行のTASK-002は`documents[]`へ入らない。TASK-001の`strongRelations`には宣言どおり`requires`が残る。"""
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    payload["roots"] = ["TASK-001"]
    if identifier == IDENTIFIER:
        task = {
            "id": "TASK-001", "workspaceId": "root", "kind": "task", "status": "done",
            "applicability": "applicable",
            "frontmatter": {
                "id": "TASK-001", "title": TITLE, "status": "done",
                "relations": {**digest_reference.EMPTY_RELATIONS, "addresses": ["REQ-001:AC-01"]},
                "implements": [], "tests": [], "verify": None, "changes": ["src/auth.py"]},
            "bodyText": TASK_BODY, "statements": [],
            "strongRelations": [{"relation": "addresses", "target": "REQ-001:AC-01"}],
        }
    else:
        task = {
            "id": "TASK-001", "workspaceId": "root", "kind": "task", "status": "open",
            "applicability": "applicable",
            "frontmatter": {
                "id": "TASK-001", "title": DEPENDENT_TITLE, "status": "open",
                "relations": {**digest_reference.EMPTY_RELATIONS,
                              "requires": ["TASK-002"], "addresses": ["REQ-001:AC-01"]},
                "implements": [], "tests": [], "verify": None, "changes": ["src/auth.py"]},
            "bodyText": DEPENDENT_BODY, "statements": [],
            # `relation`、`target`の順でコードポイント辞書順: addresses < requires。
            "strongRelations": [{"relation": "addresses", "target": "REQ-001:AC-01"},
                                {"relation": "requires", "target": "TASK-002"}],
        }
    # `documents[]`はコードポイント辞書順: REQ-001 < TASK-001 < TECH-001。
    payload["documents"].insert(1, task)
    return payload


def context_digest(identifier=IDENTIFIER):
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


DESCRIPTIONS = {
    "SINGLE-068": "done TASK起点の再検証を許可する",
    "SINGLE-137": "先行TASKが未完了のTASK起点のverifyをblockedにする",
    "SINGLE-138": "先行TASKがdoneのTASK起点のverifyを許可する",
    "SINGLE-146": "requiresの閉包に適用できない文書があるTASK起点のverifyをblockedにする",
}


def reviewed_manifest(identifier=IDENTIFIER):
    blocked = identifier in {"SINGLE-137", STATE_IDENTIFIER}
    return {
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        "setup": {"git": True, "operations": [{"op": "stage", "paths": ["."]}]},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["verify", "TASK-001", "--format", "json"], "env": {}},
        "expect": {"status": "blocked" if blocked else "passed", "exitCode": 2 if blocked else 0,
                   "stdout": "json", "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def blocked_diagnostic():
    """診断レジストリの`CTX-TASK-DEPENDENCY`: `CTX-TASK-DEPENDENCY-001`、`error`、`blocked`、発生元`file`、
    継続単位`skip-target`（検証対象の`diagnostics`）。`summary`と`source.key`は`SINGLE-051`（`context`）と同じ。"""
    return {
        "code": "CTX-TASK-DEPENDENCY-001", "severity": "error", "resultStatus": "blocked",
        "summary": "先行TASK-002が完了していません",
        "source": {"kind": "file", "workspaceId": "root", "path": TASK_PATH,
                   "key": "relations.requires"},
    }


def inapplicable_diagnostic():
    """診断レジストリの`CTX-STATE-INAPPLICABLE`: `CTX-STATE-001`、`error`、`blocked`、発生元`file`、継続単位`skip-target`
    （検証対象の`diagnostics`）。適用できない文書の発生元はその文書のファイルとする（`SINGLE-052-02`の依存先と同じ）。
    `summary`は規範文を持たず、Coreの既存の文言（`context`と`verify`の`CTX-STATE-001`の依存先）にそろえた。"""
    return {
        "code": "CTX-STATE-001", "severity": "error", "resultStatus": "blocked",
        "summary": "REQ-002は現在のpurposeに適用できません",
        "source": {"kind": "file", "workspaceId": "root", "path": INAPPLICABLE_PATH},
    }


def reviewed_result(identifier=IDENTIFIER):
    if identifier in {"SINGLE-137", STATE_IDENTIFIER}:
        # コンテキストを構成する前に止まるので、`contextDigest`、`statements`、`bindingRefs`、`commands`は空である
        # （`verify` §9、`SINGLE-067`と同じ理由）。
        return {
            "schemaVersion": "1.0", "operation": "verify", "status": "blocked", "scope": "selected",
            "workspace": {"id": "root", "path": "."},
            "targetResults": [{
                "target": "TASK-001", "status": "blocked", "contextDigest": None,
                "statements": [], "bindingRefs": [],
                "diagnostics": [inapplicable_diagnostic() if identifier == STATE_IDENTIFIER
                                else blocked_diagnostic()]}],
            "revision": None,
            "commands": [],
            "durationMs": 0,
            "diagnostics": [],
        }
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "passed", "scope": "selected",
        "workspace": {"id": "root", "path": "."},
        "targetResults": [{
            "target": "TASK-001", "status": "passed", "contextDigest": context_digest(identifier),
            "statements": list(TARGET_STATEMENTS),
            "bindingRefs": ["root::default"], "diagnostics": []}],
        "revision": None,
        "commands": [{
            "bindingId": "root::default", "workspaceId": "root", "name": "default",
            "status": "passed", "termination": "exit", "cwd": ".",
            "argv": ["/bin/true", *TEST_PATHS], "tests": list(TEST_PATHS),
            "covers": list(TARGET_STATEMENTS),
            "exitCode": 0, "timeoutSeconds": 300, "stdoutExcerpt": "", "stderrExcerpt": "",
            "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}],
        "durationMs": 0,
        "diagnostics": [],
    }


def check_done_root(result):
    target = result["targetResults"][0]
    if target["status"] != "passed" or target["diagnostics"]:
        raise ValueError("`done`のTASKの起点は診断なしで再検証できる必要があります")
    if target["statements"] != TARGET_STATEMENTS:
        raise ValueError("対象規範文はTASKの`addresses`だけから来る必要があります")
    command = result["commands"][0]
    if "tests/test_session.py" in command["tests"] or "REQ-001:AC-02" in command["covers"]:
        raise ValueError("`addresses`していない規範文のテストをテスト割当てへ入れてはいけません")


def check_inapplicable_closure(result):
    """起点の`requires`の閉包の文書が適用できないとき、`verify`は`CTX-STATE-001`だけで`blocked`にする
    （関係・トレースモデル §6.3、ADR-034の`Decision`の5番目の項目、ADR-029の`Decision`の4番目の項目）。"""
    target = result["targetResults"][0]
    codes = [item["code"] for item in target["diagnostics"]]
    if (result["status"], target["status"]) != ("blocked", "blocked") or codes != ["CTX-STATE-001"]:
        raise ValueError("`requires`の閉包に適用できない文書がある起点は`CTX-STATE-001`だけで`blocked`になる必要があります")
    if (target["contextDigest"] is not None or target["statements"] or target["bindingRefs"] or result["commands"]):
        raise ValueError("`blocked`の検証対象は、ハッシュ値、規範文、テスト割当てを持たず、テストを実行してはいけません")
    source = target["diagnostics"][0]["source"]
    if source["path"] != INAPPLICABLE_PATH or "key" in source or result["diagnostics"]:
        raise ValueError("診断の発生元は適用できない文書のファイルで、検証対象の`diagnostics`に置く必要があります")


def check_state_inputs(inputs, schema):
    """原因は、`done`の起点が`requires`する、状態`draft`のREQ-002だけである。"""
    documents = {}
    for path, kind in ((TASK_PATH, "taskFrontmatter"), (ADDRESSED_PATH, "reqFrontmatter"),
                       (INAPPLICABLE_PATH, "reqFrontmatter")):
        documents[path], _ = digest_crosscheck.split_document(inputs[path].decode())
        Draft202012Validator({"$ref": "#/$defs/" + kind, "$defs": schema["$defs"]}).validate(documents[path])
    task, addressed, inapplicable = documents[TASK_PATH], documents[ADDRESSED_PATH], documents[INAPPLICABLE_PATH]
    if task["status"] != "done" or task["relations"]["requires"] != ["REQ-002"]:
        raise ValueError("起点のTASK-001は、状態が`done`で、REQ-002だけを`requires`する必要があります")
    if task["relations"]["addresses"] != ["REQ-001:AC-01"] or addressed["status"] != "approved" or not addressed.get("tests"):
        raise ValueError("`addresses`の参照先は、状態`approved`でテスト対応を持つREQ-001:AC-01だけである必要があります")
    if inapplicable["status"] != "draft" or inapplicable["id"] != "REQ-002":
        raise ValueError("適用できない原因は、状態`draft`のREQ-002である必要があります")


def check_prerequisite(identifier, result):
    """先行TASKの状態が、起点のTASKの`verify`の結果を決める（関係・トレースモデル §6.3、ADR-029）。"""
    target = result["targetResults"][0]
    codes = [item["code"] for item in target["diagnostics"]]
    if PREREQUISITE_STATUS[identifier] != "done":
        if (result["status"], target["status"]) != ("blocked", "blocked") or codes != ["CTX-TASK-DEPENDENCY-001"]:
            raise ValueError("先行TASKが未完了の起点は`CTX-TASK-DEPENDENCY-001`だけで`blocked`になる必要があります")
        if (target["contextDigest"] is not None or target["statements"] or target["bindingRefs"]
                or result["commands"]):
            raise ValueError("`blocked`の検証対象は、ハッシュ値、規範文、テスト割当てを持たず、テストを実行してはいけません")
        source = target["diagnostics"][0]["source"]
        if (source["path"] != TASK_PATH or source.get("key") != "relations.requires"
                or result["diagnostics"]):
            raise ValueError("診断の発生元は起点のTASKの`relations.requires`で、検証対象の`diagnostics`に置く必要があります")
        return
    if result["status"] != "passed" or target["status"] != "passed" or codes:
        raise ValueError("先行TASKがすべて`done`の起点は、診断なしで`passed`になる必要があります")
    if target["statements"] != TARGET_STATEMENTS or target["bindingRefs"] != ["root::default"]:
        raise ValueError("対象規範文は起点のTASKの`addresses`だけで、テスト割当てを1件参照する必要があります")
    command = result["commands"][0]
    if command["tests"] != TEST_PATHS or command["covers"] != TARGET_STATEMENTS:
        raise ValueError("先行TASKの`addresses`の参照先（REQ-001:AC-02）とそのテストを対象規範文・テスト割当てへ入れてはいけません")


def validate(root=HERE, identifiers=None):
    selected = [name for name in IDENTIFIERS if identifiers is None or name in identifiers]
    if not selected:
        return {"prepared": [], "setups_per_fixture": 2, "core_execution": "Not run",
                "status": "Passed", "errors": []}
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads(schema_path(root, "frontmatter").read_text())
    for identifier in selected:
        try:
            validate_fixture(root, identifier, validators, schema)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}


def validate_fixture(root, identifier, validators, schema):
    fixture = root / "single" / identifier
    manifest = json.loads((fixture / "manifest.json").read_text())
    result = json.loads((fixture / "expected/verify.json").read_text())
    effects = json.loads((fixture / "side-effects.json").read_text())
    for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
        validators[name].validate(value)
    if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
        raise ValueError("起動条件または完全結果がレビュー済みの期待値と異なります")
    if identifier == IDENTIFIER:
        check_done_root(result)
    elif identifier == STATE_IDENTIFIER:
        check_inapplicable_closure(result)
    else:
        check_prerequisite(identifier, result)
    inputs = reviewed_inputs(identifier)
    frontmatter, _ = digest_crosscheck.split_document(inputs[TASK_PATH].decode())
    Draft202012Validator({"$ref": "#/$defs/taskFrontmatter",
                          "$defs": schema["$defs"]}).validate(frontmatter)
    if frontmatter["status"] != ("done" if identifier in {IDENTIFIER, STATE_IDENTIFIER} else "open"):
        raise ValueError("レビュー済みの原因と起点のTASKの状態が異なります")
    if identifier == STATE_IDENTIFIER:
        check_state_inputs(inputs, schema)
    elif identifier != IDENTIFIER:
        prerequisite, _ = digest_crosscheck.split_document(inputs[PREREQUISITE_PATH].decode())
        Draft202012Validator({"$ref": "#/$defs/taskFrontmatter",
                              "$defs": schema["$defs"]}).validate(prerequisite)
        if (frontmatter["relations"]["requires"] != ["TASK-002"]
                or prerequisite["status"] != PREREQUISITE_STATUS[identifier]):
            raise ValueError("レビュー済みの原因には、状態が指定どおりの先行TASKが必要です")
        if (prerequisite.get("relations", {}).get("addresses", []) != PREREQUISITE_ADDRESSES.get(identifier, [])
                or "REQ-001:AC-02" in frontmatter["relations"]["addresses"]):
            raise ValueError("先行TASKの`addresses`は、起点のTASKが`addresses`しない規範文を指す必要があります")
    files = {p.relative_to(fixture / "repo").as_posix(): p
             for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
    if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                        for name, p in files.items()):
        raise ValueError("入力がレビュー済みのcorpusと異なります")
    if effects["before"] != effects["after"]:
        raise ValueError("読取り専用の期待値が書込みを許しています")
    previous = None
    with tempfile.TemporaryDirectory(prefix="bitz-verify-task-root-") as temporary:
        for run in range(2):
            sandbox = Path(temporary) / str(run)
            sandbox.mkdir()
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            actual = observe(repository, external)
            if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
            previous = actual
            if identifier in {"SINGLE-137", STATE_IDENTIFIER}:
                # コンテキストを構成しないので、ハッシュ値の材料は作らない。
                continue
            derived = digest_crosscheck.canonical_bytes(
                digest_crosscheck.build(repository, root="TASK-001"))
            if derived != digest_reference.canonical_bytes(reviewed_digest_input(identifier)):
                raise ValueError("参照計算AとBの正規JSONが一致しません")
