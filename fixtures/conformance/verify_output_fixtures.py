"""出力の切り詰めを固定するreview済みのverify vector（Core操作は実行しない）。

`SINGLE-069-01/02`は、標準出力と標準エラー出力の両方が64 KiBの抜粋上限を超えるcommandを固定する。
期待する抜粋はstreamの末尾なので、corpusは最初と最後の行に異なる目印を置く。末尾ではなく
先頭を残す抜粋や、すべてを残す抜粋では、期待値を満たせない。
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
COMMAND_PATH = "bin/output.sh"
TEST_PATHS = ["tests/test_auth.py", "tests/test_session.py"]
STATEMENTS = ["REQ-001:AC-01", "REQ-001:AC-02"]
LIMIT = 65536
# 各行を64 byteに固定し、64 KiBの末尾がちょうど行の境界に来るようにして、
# 期待する抜粋が行の途中を仮定しないようにする。
LINE_BYTES = 64
HEAD = "verify-output-head" + "-" * 45
FILLER = "verify-output-filler" + "-" * 43
TAIL = "verify-output-tail" + "-" * 45
FILLER_COUNT = 1098
TOTAL_LINES = FILLER_COUNT + 2
EXCERPT_LINES = LIMIT // LINE_BYTES
EXCERPT = (FILLER + "\n") * (EXCERPT_LINES - 1) + TAIL + "\n"
SCRIPT = (
    "#!/bin/sh\n"
    f'head="{HEAD}"\n'
    f'filler="{FILLER}"\n'
    f'tail="{TAIL}"\n'
    'echo "$head"\n'
    'echo "$head" >&2\n'
    "i=1\n"
    f'while [ "$i" -le {FILLER_COUNT} ]; do\n'
    '    echo "$filler"\n'
    '    echo "$filler" >&2\n'
    "    i=$((i + 1))\n"
    "done\n"
    'echo "$tail"\n'
    'echo "$tail" >&2\n'
)
CASES = {
    "SINGLE-069-01": (0, "passed", 0),
    "SINGLE-069-02": (1, "failed", 1),
}
DESCRIPTIONS = {
    "SINGLE-069-01": "成功commandの64 KiB超の出力を末尾抜粋とtruncated flagで保持する",
    "SINGLE-069-02": "非0終了commandの64 KiB超の出力を末尾抜粋とtruncated flagで保持する",
}


def script(identifier):
    exit_code, _, _ = CASES[identifier]
    return SCRIPT + f"exit {exit_code}\n"


def reviewed_inputs(identifier):
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    inputs[digest_reference.CONFIG_PATH] = digest_reference.CONFIG.replace(
        '"/bin/true", "{tests}"', f'"{COMMAND_PATH}", "{{tests}}"').encode()
    inputs[COMMAND_PATH] = script(identifier).encode()
    return inputs


def executables(identifier):
    return {COMMAND_PATH}


def reviewed_digest_input(identifier):
    """scriptの本文はDigest材料ではないので、両fixtureは1つのContextを共有する。"""
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    payload["settings"]["commands"][0]["argv"] = [COMMAND_PATH, "{tests}"]
    return payload


def context_digest(identifier):
    return digest_reference.digest(
        digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


def reviewed_manifest(identifier):
    _, status, exit_code = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        "setup": {"git": True, "operations": [{"op": "stage", "paths": ["."]}]},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["verify", "REQ-001", "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def reviewed_result(identifier):
    command_exit, status, _ = CASES[identifier]
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": status, "scope": "selected",
        "workspace": {"id": "root", "path": "."},
        "targetResults": [{
            "target": "REQ-001", "status": status,
            "contextDigest": context_digest(identifier),
            "statements": list(STATEMENTS),
            "bindingRefs": ["root::default"], "diagnostics": []}],
        "revision": None,
        "commands": [{
            "bindingId": "root::default", "workspaceId": "root", "name": "default",
            "status": status, "termination": "exit", "cwd": ".",
            "argv": [COMMAND_PATH, *TEST_PATHS], "tests": list(TEST_PATHS),
            "covers": list(STATEMENTS),
            "exitCode": command_exit, "timeoutSeconds": 300,
            "stdoutExcerpt": EXCERPT, "stderrExcerpt": EXCERPT,
            "stdoutTruncated": True, "stderrTruncated": True, "durationMs": 0}],
        "durationMs": 0,
        "diagnostics": [],
    }


def check_excerpt_shape():
    """review済みの抜粋は、上限を超えるstreamの行の境界上の末尾であり、
    末尾の目印を含み、先頭の目印を含まない必要がある。"""
    if len(HEAD) + 1 != LINE_BYTES or len(FILLER) + 1 != LINE_BYTES or len(TAIL) + 1 != LINE_BYTES:
        raise ValueError("各行はちょうど固定の幅である必要があります")
    if TOTAL_LINES * LINE_BYTES <= LIMIT:
        raise ValueError("streamは抜粋の上限を超える必要があります")
    if len(EXCERPT.encode()) != LIMIT:
        raise ValueError("抜粋はちょうど64 KiBの末尾である必要があります")
    if HEAD in EXCERPT or TAIL not in EXCERPT:
        raise ValueError("抜粋は先頭の目印を落とし、末尾の目印を残す必要があります")
    for keyword in ("token", "secret", "password", "passwd", "api_key", "private_key",
                    "credential", "auth"):
        if keyword in EXCERPT.lower():
            raise ValueError("固定した出力はredactionのpatternと衝突してはいけません")


def observe_output(identifier, repository):
    """fixture自身のcommand fileを実行し、review済みの抜粋が実際に生成されるものであることを
    確認する。fixture側の観測であり、Coreのverifyの実行ではない。"""
    executable = repository / COMMAND_PATH
    if not (executable.is_file() and os.access(executable, os.X_OK)):
        raise ValueError("command fileは通常の実行可能fileである必要があります")
    completed = subprocess.run([str(executable)], cwd=repository, capture_output=True, timeout=60)
    command_exit = CASES[identifier][0]
    if completed.returncode != command_exit:
        raise ValueError("commandの終了コードが審査済み期待値と異なります")
    for stream in (completed.stdout, completed.stderr):
        if len(stream) <= LIMIT:
            raise ValueError("commandが抜粋の上限を超えませんでした")
        if stream[-LIMIT:].decode("utf-8") != EXCERPT:
            raise ValueError("生成した末尾がreview済みの抜粋と異なります")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            check_excerpt_shape()
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/verify.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("起動条件または完全結果が審査済み期待値と異なります")
            command = result["commands"][0]
            if not (command["stdoutTruncated"] and command["stderrTruncated"]):
                raise ValueError("上限を超えるstreamは切り詰めflagを立てる必要があります")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs):
                raise ValueError("入力が審査済みcorpusと異なります")
            for name, path in files.items():
                if path.is_symlink() or path.read_bytes() != inputs[name]:
                    raise ValueError("入力が審査済みcorpusと異なります")
                if bool(path.stat().st_mode & 0o111) != (name in executables(identifier)):
                    raise ValueError(f"{name}の実行bitが審査済み入力と異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-verify-output-") as temporary:
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
                    derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository))
                    if digest_crosscheck.digest(derived) != context_digest(identifier):
                        raise ValueError("参照計算どうしでtargetのDigestが一致しません")
                    if run == 0:
                        observe_output(identifier, repository)
                    if compare_state(effects["after"], observe(repository, external)):
                        raise ValueError("commandの観測でfixtureの状態が変わりました")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "observed_output": True,
            "status": "Passed" if not errors else "Failed", "errors": errors}
