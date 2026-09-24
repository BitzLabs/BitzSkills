"""複数bindingのverifyを固定するreview済みvector（Core操作は実行しない）。

`SINGLE-063`と`SINGLE-064`は、2つのtargetが同じcommand名を要求できるよう、起点を2つ持つ
workspaceを使う。`SINGLE-065`はcommand templateから`{tests}`の置換位置を除く。各targetは
固有のContextを解決するので固有のDigestを持ち、commandは1回だけ実行する。
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

HERE = Path(__file__).resolve().parent
SHARED_TEST = "tests/test_shared.py"
CONFIG_NO_PLACEHOLDER = digest_reference.CONFIG.replace('"/bin/true", "{tests}"', '"/bin/true"')
TITLES = {"1": "認証Contextの基準", "2": "session Contextの基準"}
TECH_TITLES = {"1": "認証の実装方針", "2": "sessionの実装方針"}
CODE = {"1": "src/auth.py", "2": "src/session.py"}


def requirement(number):
    title = TITLES[number]
    return (f"---\nid: REQ-00{number}\ntitle: {title}\nstatus: approved\n---\n"
            f"\n# REQ-00{number} {title}\n"
            f"\n## Intent\n\nbinding共有の検査に使う固定要求を定義する。\n"
            f"\n## Acceptance Criteria\n"
            f"\n- [REQ-00{number}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n"
            f"\n## Verification\n\n{SHARED_TEST}で確認する。\n")


def technical(number, with_tests=True):
    title = TECH_TITLES[number]
    tests = ("tests:\n"
             f"  - path: {SHARED_TEST}\n"
             f"    covers: [REQ-00{number}:AC-01]\n"
             "    command: default\n") if with_tests else ""
    return (f"---\nid: TECH-00{number}\ntitle: {title}\nstatus: approved\n"
            f"relations:\n  refines: [REQ-00{number}]\n"
            f"implements: [{CODE[number]}]\n" + tests + "---\n"
            f"\n# TECH-00{number} {title}\n\n## Context\n\n規範文を持たない実装方針。\n")


# id: (targets, status, 終了コード, TECH-001がtestsを宣言するか)
CASES = {
    "SINGLE-063": (["REQ-001", "REQ-002"], "passed", 0, True),
    "SINGLE-064": (["REQ-001", "REQ-002"], "blocked", 2, False),
    "SINGLE-065": (["REQ-001"], "passed", 0, True),
}
DESCRIPTIONS = {
    "SINGLE-063": "2 targetが同じcommand名を要求し実体を1回だけ実行する",
    "SINGLE-064": "非成功targetと通過targetが混在しても通過分を実行する",
    "SINGLE-065": "{tests}なしcommandを複数test pathでも1回だけ実行する",
}


def reviewed_inputs(identifier):
    if identifier == "SINGLE-065":
        inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
        inputs[digest_reference.CONFIG_PATH] = CONFIG_NO_PLACEHOLDER.encode()
        return inputs
    _, _, _, first_has_tests = CASES[identifier]
    return {
        digest_reference.CONFIG_PATH: digest_reference.CONFIG.encode(),
        ".spec/requirements/REQ-001.md": requirement("1").encode(),
        ".spec/requirements/REQ-002.md": requirement("2").encode(),
        ".spec/technical/TECH-001.md": technical("1", first_has_tests).encode(),
        ".spec/technical/TECH-002.md": technical("2").encode(),
        CODE["1"]: digest_reference.CODE_FILES["src/auth.py"].encode(),
        CODE["2"]: digest_reference.CODE_FILES["src/session.py"].encode(),
        SHARED_TEST: "def test_shared():\n    assert True\n".encode(),
    }


def pair_digest_input(identifier, root):
    number = root[-1]
    _, _, _, first_has_tests = CASES[identifier]
    has_tests = first_has_tests if number == "1" else True
    tests = ([{"path": SHARED_TEST, "covers": [f"REQ-00{number}:AC-01"], "command": "default"}]
             if has_tests else [])
    requirement_body = requirement(number)
    technical_body = technical(number, has_tests)
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0",
        "resolverVersion": "1.0", "purpose": "verify", "requestWorkspaceId": "root",
        "roots": [root], "workspaces": [{"id": "root", "path": "."}],
        "documents": [
            {"id": root, "workspaceId": "root", "kind": "requirement", "status": "approved",
             "applicability": "applicable",
             "frontmatter": {"id": root, "title": TITLES[number], "status": "approved",
                             "relations": dict(digest_reference.EMPTY_RELATIONS),
                             "implements": [], "tests": [], "verify": None, "changes": []},
             "bodyText": requirement_body[requirement_body.index("\n---\n") + 5:].lstrip("\n"),
             "statements": [{**digest_reference.STATEMENTS[0], "id": f"REQ-00{number}:AC-01"}],
             "strongRelations": []},
            {"id": f"TECH-00{number}", "workspaceId": "root", "kind": "technical",
             "status": "approved", "applicability": "applicable",
             "frontmatter": {"id": f"TECH-00{number}", "title": TECH_TITLES[number],
                             "status": "approved",
                             "relations": {**digest_reference.EMPTY_RELATIONS, "refines": [root]},
                             "implements": [CODE[number]], "tests": tests,
                             "verify": None, "changes": []},
             "bodyText": technical_body[technical_body.index("\n---\n") + 5:].lstrip("\n"),
             "statements": [], "strongRelations": [{"relation": "refines", "target": root}]},
        ],
        "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": "root", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": "root", "timeoutSeconds": 300}] if has_tests else [],
            "commands": ([{"workspaceId": "root", "name": "default",
                           "argv": ["/bin/true", "{tests}"], "cwd": "."}] if has_tests else []),
        },
    }


def reviewed_digest_input(identifier, root):
    if identifier == "SINGLE-065":
        payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
        payload["settings"]["commands"][0]["argv"] = ["/bin/true"]
        return payload
    return pair_digest_input(identifier, root)


def context_digest(identifier, root):
    return digest_reference.digest(
        digest_reference.canonical_bytes(reviewed_digest_input(identifier, root)))


def reviewed_manifest(identifier):
    targets, status, exit_code, _ = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        "setup": {"git": True, "operations": [{"op": "stage", "paths": ["."]}]},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["verify", *targets, "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def reviewed_result(identifier):
    targets, status, _, first_has_tests = CASES[identifier]
    if identifier == "SINGLE-065":
        target_results = [{
            "target": "REQ-001", "status": "passed",
            "contextDigest": context_digest(identifier, "REQ-001"),
            "statements": ["REQ-001:AC-01", "REQ-001:AC-02"],
            "bindingRefs": ["root::default"], "diagnostics": []}]
        command = {
            "bindingId": "root::default", "workspaceId": "root", "name": "default",
            "status": "passed", "termination": "exit", "cwd": ".",
            # {tests}の置換位置がないので、pathを追加せず、argvを1回実行する。
            "argv": ["/bin/true"],
            "tests": ["tests/test_auth.py", "tests/test_session.py"],
            "covers": ["REQ-001:AC-01", "REQ-001:AC-02"],
            "exitCode": 0, "timeoutSeconds": 300, "stdoutExcerpt": "", "stderrExcerpt": "",
            "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}
    else:
        target_results = []
        for root in targets:
            blocked = root == "REQ-001" and not first_has_tests
            target_results.append({
                "target": root,
                "status": "blocked" if blocked else "passed",
                "contextDigest": context_digest(identifier, root),
                "statements": [f"{root}:AC-01"],
                "bindingRefs": [] if blocked else ["root::default"],
                "diagnostics": [{
                    "code": "CTX-COVERAGE-TEST-001", "severity": "error", "resultStatus": "blocked",
                    "summary": f"対象MUST {root}:AC-01にtest対応がありません",
                    "source": {"kind": "file", "workspaceId": "root",
                               "path": f".spec/requirements/{root}.md"}}] if blocked else [],
            })
        covers = sorted(f"{root}:AC-01" for root in targets
                        if not (root == "REQ-001" and not first_has_tests))
        command = {
            "bindingId": "root::default", "workspaceId": "root", "name": "default",
            "status": "passed", "termination": "exit", "cwd": ".",
            # 共有pathは展開前に重複排除するので、1回だけ現れる。
            "argv": ["/bin/true", SHARED_TEST], "tests": [SHARED_TEST], "covers": covers,
            "exitCode": 0, "timeoutSeconds": 300, "stdoutExcerpt": "", "stderrExcerpt": "",
            "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": status, "scope": "selected",
        "workspace": {"id": "root", "path": "."},
        "targetResults": target_results,
        "revision": None,
        "commands": [command],
        "durationMs": 0,
        "diagnostics": [],
    }


def check_sharing(identifier, result):
    """要求したtargetすべてに対してcommand実体を1つにし、1回だけ実行し、
    参照するtest pathを重複排除する。"""
    commands = result["commands"]
    if len(commands) != 1:
        raise ValueError("共有bindingは単一のcommand実体である必要があります")
    command = commands[0]
    if len(command["tests"]) != len(set(command["tests"])):
        raise ValueError("test pathが重複排除されていません")
    if command["argv"].count(SHARED_TEST) > 1:
        raise ValueError("重複排除したpathが複数回展開されています")
    requesting = [target for target in result["targetResults"] if target["bindingRefs"]]
    if {ref for target in requesting for ref in target["bindingRefs"]} != {command["bindingId"]}:
        raise ValueError("要求したtargetがすべて単一のbindingを参照していません")
    digests = [target["contextDigest"] for target in result["targetResults"]]
    if len(set(digests)) != len(digests) or None in digests:
        raise ValueError("各targetは固有のnullでないContext Digestを解決する必要があります")
    for target in result["targetResults"]:
        if target["status"] != "passed" and target["bindingRefs"]:
            raise ValueError("非成功のtargetはbindingを要求してはいけません")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/verify.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("起動条件または完全結果が審査済み期待値と異なります")
            if identifier != "SINGLE-065":
                check_sharing(identifier, result)
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-verify-binding-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
                    for target in result["targetResults"]:
                        derived = digest_crosscheck.canonical_bytes(
                            digest_crosscheck.build(repository, root=target["target"]))
                        if digest_crosscheck.digest(derived) != target["contextDigest"]:
                            raise ValueError(f"参照計算どうしで{target['target']}のDigestが一致しません")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
