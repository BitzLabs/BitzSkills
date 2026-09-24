"""Digest材料の完全順序とreverse solidus保持を固定するfixture（Core操作は実行しない）。

`SINGLE-122`は同一pathのtest対応を`(path, commandSortKey, covers)`、`SINGLE-123`は同一namespace／termの
extensionを`(namespace, term, valueSortKey)`で並べる。`SINGLE-124`はpath型以外のstring
（title、statement text、argv template）のreverse solidusを変換しない。

goldenの`SINGLE-042` corpusを1点だけ変え、Canonical JSONを`expected/context.canonical.json`へ置く。
reference A（本moduleのliteral）とreference B（digest_crosscheckが入力treeから導出）のbyte一致を要求する。
根拠は[Context Digest正規化仕様 §3・§4]と[context仕様 §4・§5]である。
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from .digest_fixtures import reviewed_result as golden_result
from .harness import git, setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
REQ_PATH = digest_reference.REQ_PATH
TECH_PATH = digest_reference.TECH_PATH
CONFIG_PATH = digest_reference.CONFIG_PATH


def replaced(text, old, new):
    if old not in text:
        raise ValueError("golden corpusの置換対象が見つかりません")
    return text.replace(old, new, 1)


# --- 122: 同一pathのtest対応 -------------------------------------------------------
# 宣言順は正規順と異なる。command省略は文書のverifyで解決し、Digestではnullとして先頭に並ぶ。
DECLARED_TESTS = (
    "tests:\n"
    "  - path: tests/test_auth.py\n    covers: [REQ-001:AC-02]\n    command: other\n"
    "  - path: tests/test_auth.py\n    covers: [REQ-001:AC-01, REQ-001:AC-02]\n    command: default\n"
    "  - path: tests/test_auth.py\n    covers: [REQ-001:AC-01]\n"
    "  - path: tests/test_auth.py\n    covers: [REQ-001:AC-01]\n    command: default\n"
)
ORDERED_TESTS = [
    {"path": "tests/test_auth.py", "covers": ["REQ-001:AC-01"], "command": None},
    {"path": "tests/test_auth.py", "covers": ["REQ-001:AC-01"], "command": "default"},
    {"path": "tests/test_auth.py", "covers": ["REQ-001:AC-01", "REQ-001:AC-02"], "command": "default"},
    {"path": "tests/test_auth.py", "covers": ["REQ-001:AC-02"], "command": "other"},
]
OTHER_COMMAND = '    other:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
TECH_122_FIELDS = (
    "id: TECH-001\ntitle: 認証の実装方針\nstatus: approved\n"
    "relations:\n  refines: [REQ-001]\n  related: [ADR-001]\n"
    "verify: default\n"
    "implements: [src/auth.py]\n" + DECLARED_TESTS
)

# --- 123: 同一namespace／termのextension -----------------------------------------
EXTENSIONS_RAW = '[quality:LEVEL="b"] [quality:LEVEL] [perf:LEVEL="x"] [quality:LEVEL="a"] [quality:AREA="z"] '
ORDERED_EXTENSIONS = [
    {"namespace": "perf", "term": "LEVEL", "value": "x"},
    {"namespace": "quality", "term": "AREA", "value": "z"},
    {"namespace": "quality", "term": "LEVEL", "value": None},
    {"namespace": "quality", "term": "LEVEL", "value": "a"},
    {"namespace": "quality", "term": "LEVEL", "value": "b"},
]
REQ_123_BODY = replaced(digest_reference.REQ_BODY, "[REQ-001:AC-01] [ACTOR:", "[REQ-001:AC-01] " + EXTENSIONS_RAW + "[ACTOR:")

# --- 124: path型以外のreverse solidus -------------------------------------------
CONFIG_124 = replaced(digest_reference.CONFIG, '["/bin/true", "{tests}"]', '["/bin/true", --pattern=src\\auth, "{tests}"]')
ARGV_124 = ["/bin/true", "--pattern=src\\auth", "{tests}"]
TITLE_124 = "認証の実装方針\\補足"
TECH_BODY_124 = replaced(digest_reference.TECH_BODY, "# TECH-001 認証の実装方針\n", f"# TECH-001 {TITLE_124}\n")
TEXT_124_RAW = "値 a\\\\b を出力しない"
TEXT_124 = "値 a\\b を出力しない"
REQ_124_BODY = replaced(digest_reference.REQ_BODY, "秘密情報を出力しない", TEXT_124_RAW)

CASES = {
    "SINGLE-122": "同一pathでcommand／coversが異なるtest対応を完全順序で並べる",
    "SINGLE-123": "同一namespace／termでvalueが異なるextensionを完全順序で並べる",
    "SINGLE-124": "path型以外のstringとargvのreverse solidusを変換しない",
}


def req_line(body):
    head = digest_reference.REQ_HEAD + "\n"
    for number, line in enumerate((head + body).split("\n"), 1):
        if line.startswith("- [REQ-001:AC-01]"):
            return number, line
    raise ValueError("AC-01行が見つかりません")


def reviewed_inputs(identifier):
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    tech_head = digest_reference.TECH_HEAD_FIELDS + "x-owners: [team-auth]\n"
    if identifier == "SINGLE-122":
        inputs[CONFIG_PATH] = (digest_reference.CONFIG + OTHER_COMMAND).encode()
        inputs[TECH_PATH] = ("---\n" + TECH_122_FIELDS + "---\n\n" + digest_reference.TECH_BODY).encode()
    elif identifier == "SINGLE-123":
        inputs[REQ_PATH] = (digest_reference.REQ_HEAD + "\n" + REQ_123_BODY).encode()
    else:
        inputs[CONFIG_PATH] = CONFIG_124.encode()
        inputs[REQ_PATH] = (digest_reference.REQ_HEAD + "\n" + REQ_124_BODY).encode()
        head = replaced(tech_head, "title: 認証の実装方針\n", f"title: {TITLE_124}\n")
        inputs[TECH_PATH] = ("---\n" + head + "---\n\n" + TECH_BODY_124).encode()
    return inputs


def reviewed_manifest(identifier):
    return {"fixtureId": identifier, "description": CASES[identifier],
            "setup": {"git": True, "operations": []},
            "invocation": {"runner": "bitz", "cwd": ".",
                           "argv": ["context", "REQ-001", "--purpose", "verify", "--format", "json"], "env": {}},
            "expect": {"status": "passed_with_warnings" if identifier == "SINGLE-123" else "passed",
                       "exitCode": 0, "stdout": "json", "resultFile": "expected/context.json",
                       "reportFileCount": 0}}


def reviewed_digest_input(identifier):
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    req, tech = payload["documents"]
    if identifier == "SINGLE-122":
        tech["frontmatter"].update(verify="default", implements=["src/auth.py"], tests=copy.deepcopy(ORDERED_TESTS))
        payload["settings"]["commands"].append(
            {"workspaceId": "root", "name": "other", "argv": ["/bin/true", "{tests}"], "cwd": "."})
    elif identifier == "SINGLE-123":
        req["bodyText"] = REQ_123_BODY
        req["statements"][0]["extensions"] = copy.deepcopy(ORDERED_EXTENSIONS)
    else:
        req["bodyText"] = REQ_124_BODY
        req["statements"][0]["operation"]["text"] = TEXT_124
        tech["frontmatter"]["title"] = TITLE_124
        tech["bodyText"] = TECH_BODY_124
        payload["settings"]["commands"][0]["argv"] = ARGV_124
    return payload


def canonical(identifier):
    return digest_reference.canonical_bytes(reviewed_digest_input(identifier))


def unknown_extension_diagnostics():
    number, line = req_line(REQ_123_BODY)
    diagnostics, cursor = [], 0
    for token in EXTENSIONS_RAW.split("] ")[:-1]:
        column = line.index(token + "]", cursor) + 1
        cursor = column
        diagnostics.append({"code": "EAI-EXT-UNKNOWN-001", "severity": "warning",
                            "resultStatus": "passed_with_warnings", "summary": "未知namespaceのextensionを保持します",
                            "source": {"kind": "file", "workspaceId": "root", "path": REQ_PATH,
                                       "line": number, "column": column}})
    return diagnostics


def reviewed_result(identifier):
    result = golden_result("SINGLE-042", digest_reference.digest(canonical(identifier)))
    req, tech = result["documents"]
    if identifier == "SINGLE-122":
        # Bundleのfrontmatterはnullと空配列を省略する（SINGLE-042のverify・空relationと同じ規則）。
        tech["frontmatter"] = {
            "id": "TECH-001", "title": "認証の実装方針", "status": "approved",
            "relations": {"refines": ["REQ-001"], "related": ["ADR-001"]}, "verify": "default", "implements": ["src/auth.py"],
            "tests": [{key: value for key, value in test.items() if value is not None} for test in ORDERED_TESTS]}
    elif identifier == "SINGLE-123":
        result["status"] = "passed_with_warnings"
        req["bodyText"] = REQ_123_BODY
        result["diagnostics"] = unknown_extension_diagnostics()
    else:
        req["bodyText"] = REQ_124_BODY
        tech["frontmatter"]["title"] = TITLE_124
        tech["bodyText"] = TECH_BODY_124
        # LEDGERの入れ子objectは共有されているため、置き換えて共有値を変更しない。
        result["constraintLedger"]["statements"][0]["operation"] = {"kind": "CONSTRAINT", "text": TEXT_124}
    return result


def check_contract(identifier, result, canonical_bytes):
    value = json.loads(canonical_bytes.decode("utf-8"))
    if identifier == "SINGLE-122":
        tests = value["documents"][1]["frontmatter"]["tests"]
        keys = [(t["path"], t["command"] is not None, t["command"] or "", t["covers"]) for t in tests]
        if keys != sorted(keys) or len(tests) != 4 or tests[0]["command"] is not None:
            raise ValueError("test対応が(path, commandSortKey, covers)の完全順序ではありません")
        if [c["name"] for c in value["settings"]["commands"]] != ["default", "other"]:
            raise ValueError("参照される2 commandだけを名前順に収録する必要があります")
        if [t.get("command") for t in result["documents"][1]["frontmatter"]["tests"]] != [None, "default", "default", "other"]:
            raise ValueError("Bundleのtest対応もDigestと同じ順序である必要があります")
    elif identifier == "SINGLE-123":
        extensions = value["documents"][0]["statements"][0]["extensions"]
        keys = [(e["namespace"], e["term"], e["value"] is not None, e["value"] or "") for e in extensions]
        if keys != sorted(keys) or len(extensions) != 5:
            raise ValueError("extensionが(namespace, term, valueSortKey)の完全順序ではありません")
        columns = [d["source"]["column"] for d in result["diagnostics"]]
        if columns != sorted(columns) or len(set(columns)) != 5:
            raise ValueError("未知extensionのwarningは出現位置ごとに1件ずつ位置順で返す必要があります")
    else:
        if value["settings"]["commands"][0]["argv"][1] != "--pattern=src\\auth":
            raise ValueError("argv templateのreverse solidusを保持する必要があります")
        if value["documents"][1]["frontmatter"]["title"] != TITLE_124:
            raise ValueError("titleのreverse solidusを保持する必要があります")
        if value["documents"][0]["statements"][0]["operation"]["text"] != TEXT_124:
            raise ValueError("statement textはescape解除後のreverse solidusを保持する必要があります")
        if "\\" in "".join(value["documents"][1]["frontmatter"]["implements"]):
            raise ValueError("path型fieldにreverse solidusを残してはいけません")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads(schema_path(root, "frontmatter").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/context.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            committed = (fixture / "expected/context.canonical.json").read_bytes()
            if committed != canonical(identifier) or committed.endswith(b"\n") or committed.startswith(b"\xef\xbb\xbf"):
                raise ValueError("Canonical JSONが審査済みのDigest材料と異なります")
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("起動条件または完全結果が審査済み期待値と異なります")
            check_contract(identifier, result, committed)
            golden = (root / "single/SINGLE-042/expected/context.canonical.json")
            if golden.exists() and golden.read_bytes() == committed:
                raise ValueError("Digest材料がgoldenと同じです")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            for path, kind in ((REQ_PATH, "reqFrontmatter"), (TECH_PATH, "techFrontmatter")):
                parsed, _ = digest_crosscheck.split_document(inputs[path].decode())
                Draft202012Validator({"$ref": "#/$defs/" + kind, "$defs": schema["$defs"]}).validate(parsed)
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-ordering-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    if git(repository, "ls-files", "-z"):
                        raise ValueError("context fixtureのindexは空である必要があります")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
                    derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository))
                    if derived != committed:
                        raise ValueError("reference AとBのCanonical JSONが一致しません")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
