"""`{tests}`展開後argvの上限超過fixture（SINGLE-126-08）の審査済み証跡。Coreは実行しない。

要素32 KiBはpath長上限のため超過できず、10,000要素は約1万fileを要するため、byte総和1 MiBの超過を使う。
約3,770 byteのtest pathを280件、Frontmatter 32 KiB上限に収まるよう規範文なしTECH 35文書へ8件ずつ置く。
引数なし`verify`は35文書をtargetにし、同じ`default` bindingへ全pathを集めるため、展開後argvだけが1 MiBを超える。
bindingは起動せず、top-levelの`SPEC-VERIFY-BLOCKED-001`1件と、全targetの`bindingRefs: []`で表す。
"""
import copy
import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from .initial_fixtures import CONFIGS
from .verify_argv_fixtures import check_inputs, check_setups

HERE = Path(__file__).resolve().parent
IDENTIFIER = "SINGLE-126-08"
CASES = {IDENTIFIER: "{tests}展開後argvがbyte総和1 MiBを超えればbindingを起動しない"}
DOCUMENT_COUNT = 35
TESTS_PER_DOCUMENT = 8
SEGMENT = "d" * 250
DEPTH = 14
NAME_LENGTH = 250
ARGV_LIMIT = 1024 * 1024
ELEMENT_LIMIT = 32 * 1024
ELEMENT_COUNT_LIMIT = 10000
FRONTMATTER_LIMIT = 32 * 1024
CONFIG = CONFIGS["SINGLE-001"] + 'verify:\n  commands:\n    default:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
TITLE = "長いtest path群"
BODY_TEMPLATE = "# {id} " + TITLE + "\n\n## Context\n\n展開後argvの上限を検査する。\n"
SUMMARY = "{tests}展開後のargvがbyte上限1 MiBを超えます"
ARGV_KEY = "verify.commands.default.argv"


def document_id(index):
    return f"TECH-{index:03d}"


def test_path(document, position):
    directory = "tests/" + "/".join([SEGMENT] * DEPTH)
    stem = f"t{document:03d}_{position}_"
    return f"{directory}/{stem}{'x' * (NAME_LENGTH - len(stem) - 3)}.py"


def document_tests(index):
    return [{"path": test_path(index, position), "covers": [document_id(index)], "command": "default"}
            for position in range(TESTS_PER_DOCUMENT)]


def frontmatter_text(index):
    lines = [f"id: {document_id(index)}", f"title: {TITLE}", "status: approved", "tests:"]
    for test in document_tests(index):
        lines += [f"  - path: {test['path']}", f"    covers: [{test['covers'][0]}]", "    command: default"]
    return "\n".join(lines) + "\n"


def body_text(index):
    return BODY_TEMPLATE.format(id=document_id(index))


def reviewed_inputs(identifier=IDENTIFIER):
    inputs = {digest_reference.CONFIG_PATH: CONFIG.encode()}
    for index in range(1, DOCUMENT_COUNT + 1):
        inputs[f".spec/technical/{document_id(index)}.md"] = (
            "---\n" + frontmatter_text(index) + "---\n\n" + body_text(index)).encode()
        for test in document_tests(index):
            inputs[test["path"]] = b"def test_placeholder():\n    assert True\n"
    return inputs


def executables(identifier=IDENTIFIER):
    return set()


def reviewed_digest_input(index):
    """規範文なしTECH 1文書だけのverify Context。Digest入力は参照Aとして手で組み立てる。"""
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    payload["roots"] = [document_id(index)]
    payload["documents"] = [{
        "id": document_id(index), "workspaceId": "root", "kind": "technical", "status": "approved",
        "applicability": "applicable",
        "frontmatter": {"id": document_id(index), "title": TITLE, "status": "approved",
                        "relations": dict(digest_reference.EMPTY_RELATIONS), "implements": [],
                        "tests": document_tests(index), "verify": None, "changes": []},
        "bodyText": body_text(index), "statements": [], "strongRelations": []}]
    return payload


def context_digest(index):
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(index)))


def reviewed_manifest(identifier=IDENTIFIER):
    return {
        "fixtureId": identifier,
        "description": CASES[identifier],
        "setup": {"git": True, "operations": [{"op": "stage", "paths": ["."]}]},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": ["verify", "--format", "json"], "env": {}},
        "expect": {"status": "blocked", "exitCode": 2, "stdout": "json",
                   "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def reviewed_result(identifier=IDENTIFIER):
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "blocked", "scope": "all",
        "workspace": {"id": "root", "path": "."},
        "targetResults": [{"target": document_id(index), "status": "blocked",
                           "contextDigest": context_digest(index), "statements": [],
                           "bindingRefs": [], "diagnostics": []}
                          for index in range(1, DOCUMENT_COUNT + 1)],
        "revision": None, "commands": [], "durationMs": 0,
        # spawn前のblockedは単一workspaceではtop-levelへ1件だけ置き、targetへ複製しない。
        "diagnostics": [{"code": "SPEC-VERIFY-BLOCKED-001", "severity": "error", "resultStatus": "blocked",
                         "summary": SUMMARY,
                         "source": {"kind": "file", "workspaceId": "root",
                                    "path": digest_reference.CONFIG_PATH, "key": ARGV_KEY}}],
    }


def check_single_limit(inputs):
    """入力上限はすべて内側に保ち、展開後argvのbyte総和だけが超過することを独立に確認する。"""
    if len(inputs[digest_reference.CONFIG_PATH]) > 64 * 1024:
        raise ValueError("設定fileが自身の入力上限を超えています")
    paths = set()
    for index in range(1, DOCUMENT_COUNT + 1):
        document = inputs[f".spec/technical/{document_id(index)}.md"].decode()
        frontmatter = document.split("---\n")[1]
        if len(frontmatter.encode()) > FRONTMATTER_LIMIT or len(document.encode()) > ARGV_LIMIT:
            raise ValueError("文書がFrontmatterまたはfileの入力上限を超えています")
        paths.update(line.removeprefix("  - path: ") for line in frontmatter.splitlines()
                     if line.startswith("  - path: "))
    argv = ["/bin/true", *sorted(paths)]
    if any(len(value.encode()) > ELEMENT_LIMIT for value in argv) or len(argv) > ELEMENT_COUNT_LIMIT:
        raise ValueError("要素長または要素数の上限も超えています")
    total = sum(len(value.encode()) for value in argv)
    if total <= ARGV_LIMIT:
        raise ValueError("展開後argvがbyte上限を超えていません")
    # 1文書分を除けば上限内に戻り、超過が全target分の和集合で初めて生じることを示す。
    if total - sum(len(test["path"].encode()) for test in document_tests(1)) > ARGV_LIMIT:
        raise ValueError("全targetの和集合でなくてもbyte上限を超えています")
    if any(len(path.encode()) >= 4000 for path in paths):
        raise ValueError("test pathはplatformのpath長上限未満である必要があります")


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
                raise ValueError("起動または完全な結果が審査済み期待と異なります")
            inputs = reviewed_inputs(identifier)
            check_single_limit(inputs)
            check_inputs(fixture, inputs, executables(identifier))

            def cross_check(_, repository):
                # 各targetのDigestを参照Bでも計算し、参照Aの期待値と一致させる。
                for index in range(1, DOCUMENT_COUNT + 1):
                    derived = digest_crosscheck.canonical_bytes(
                        digest_crosscheck.build(repository, root=document_id(index)))
                    if digest_crosscheck.digest(derived) != context_digest(index):
                        raise ValueError(f"{document_id(index)}のDigestが2系統のreferenceで一致しません")
                for path in inputs:
                    if not (repository / path).is_file():
                        raise ValueError("setup後に宣言済みtest pathが存在しません")

            check_setups(fixture, manifest, effects, identifier, None, cross_check, "bitz-verify-argv-limit-")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
