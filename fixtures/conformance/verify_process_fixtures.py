"""processの終了を固定するreview済みのverify vector（Core操作は実行しない）。

`SINGLE-057`、`SINGLE-058`、`SINGLE-059`はいずれも事前検査の通過後に失敗するので、
spawn前の停止ではなく`commands[]`の要素を記録する。監査は各fixture自身のcommand fileを、
Coreを介さず直接実行し、入力が実際にreview済みの終了を起こすことを確認する。期待値は
主張するだけのものではない。
"""
import copy
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import tempfile
import time

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
TEST_PATHS = ["tests/test_auth.py", "tests/test_session.py"]
STATEMENTS = ["REQ-001:AC-01", "REQ-001:AC-02"]
# 実行bitを持つが、kernelが形式を拒否する通常file。
# ELFのmagicもshebangもないので、事前検査の通過後にexecveがENOEXECで失敗する。
BAD_FORMAT = "this file is executable but is not a program\n"
SIGNAL_SCRIPT = "#!/bin/sh\nkill -TERM $$\n"
# SIGTERMを無視し、継承した標準出力・標準エラー出力のpipeを保持する子processを残す。
# そのためgraceful terminationでもEOFでもbindingを終えられない。準備完了の
# 行はtrapの設定後にだけ出力し、生き残った子processがその後もpipeを開いたままにするので、
# EOFを待つ読取り側は終わらない。
READY = "hang-ready"
HANG_SCRIPT = (
    "#!/bin/sh\n"
    "trap '' TERM\n"
    # 子processもTERMを無視するので、process group全体へのgraceful terminationの後も
    # 継承したpipeを開いたままにする。
    "sh -c \"trap '' TERM; sleep 60\" &\n"
    "echo " + READY + "\n"
    # 前景のsleepが終了されてもscriptを終えてはいけない。そうしないとprocess groupへの
    # TERMで足りてしまい、fixtureが強制終了を必要としなくなる。
    "i=0\n"
    "while [ \"$i\" -lt 60 ]; do\n"
    "    sleep 1\n"
    "    i=$((i + 1))\n"
    "done\n"
)
COMMANDS = {
    "SINGLE-057": ("bin/badformat", BAD_FORMAT, "spawn_error", "SPEC-VERIFY-COMMAND-001", 300),
    "SINGLE-058": ("bin/signal.sh", SIGNAL_SCRIPT, "signal", "SPEC-VERIFY-COMMAND-001", 300),
    "SINGLE-059": ("bin/hang.sh", HANG_SCRIPT, "timeout", "SPEC-VERIFY-TIMEOUT-001", 1),
}
SUMMARIES = {
    "SINGLE-057": "commandの実行形式をOSが拒否しprocessを生成できません",
    "SINGLE-058": "commandがsignalで終了しました",
    "SINGLE-059": "commandが実効timeout 1秒で終了しませんでした",
}
DESCRIPTIONS = {
    "SINGLE-057": "事前検査通過後のprocess生成失敗をspawn_errorで記録する",
    "SINGLE-058": "commandのsignal終了をterminationへ記録する",
    "SINGLE-059": "timeout後も終了しない直接processを有限時間で確定する",
}
CASES = tuple(COMMANDS)


def config(identifier):
    path, _, _, _, timeout = COMMANDS[identifier]
    body = digest_reference.CONFIG.replace('"/bin/true", "{tests}"', f'"{path}", "{{tests}}"')
    if timeout != 300:
        body = body.replace("verify:\n", f"verify:\n  timeoutSeconds: {timeout}\n", 1)
    return body


def reviewed_inputs(identifier):
    path, content, _, _, _ = COMMANDS[identifier]
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    inputs[digest_reference.CONFIG_PATH] = config(identifier).encode()
    inputs[path] = content.encode()
    return inputs


def executables(identifier):
    return {COMMANDS[identifier][0]}


def reviewed_digest_input(identifier):
    path, _, _, _, timeout = COMMANDS[identifier]
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    payload["settings"]["commands"][0]["argv"] = [path, "{tests}"]
    payload["settings"]["verifyTimeouts"][0]["timeoutSeconds"] = timeout
    return payload


def context_digest(identifier):
    return digest_reference.digest(
        digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


def expected_stdout(identifier):
    """書き込むのはtimeoutのfixtureだけで、子孫がpipeを開いたまま保持する前に、
    準備完了の行をちょうど1行書く。"""
    return READY + "\n" if identifier == "SINGLE-059" else ""


def reviewed_manifest(identifier):
    return {
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        "setup": {"git": True, "operations": [{"op": "stage", "paths": ["."]}]},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["verify", "REQ-001", "--format", "json"], "env": {}},
        "expect": {"status": "error", "exitCode": 3, "stdout": "json",
                   "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def reviewed_result(identifier):
    path, _, termination, code, timeout = COMMANDS[identifier]
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "error", "scope": "selected",
        "workspace": {"id": "root", "path": "."},
        "targetResults": [{
            "target": "REQ-001", "status": "error",
            "contextDigest": context_digest(identifier),
            "statements": list(STATEMENTS),
            "bindingRefs": ["root::default"], "diagnostics": []}],
        "revision": None,
        "commands": [{
            "bindingId": "root::default", "workspaceId": "root", "name": "default",
            "status": "error", "termination": termination, "cwd": ".",
            "argv": [path, *TEST_PATHS], "tests": list(TEST_PATHS), "covers": list(STATEMENTS),
            "exitCode": None, "timeoutSeconds": timeout,
            "stdoutExcerpt": expected_stdout(identifier), "stderrExcerpt": "",
            "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}],
        "durationMs": 0,
        "diagnostics": [{
            "code": code, "severity": "error", "resultStatus": "error",
            "summary": SUMMARIES[identifier],
            "source": {"kind": "environment", "component": "command", "identifier": "root::default"}}],
    }


def observe_termination(identifier, repository):
    """fixture自身のcommand fileを直接実行し、review済みの原因を確認する。
    入力のfixture側の観測であり、Coreのverifyの実行ではない。"""
    path, _, termination, _, _ = COMMANDS[identifier]
    executable = repository / path
    if not (executable.is_file() and os.access(executable, os.X_OK)):
        raise ValueError("command fileはspawn前に通常の実行可能fileである必要があります")
    if termination == "spawn_error":
        try:
            subprocess.run([str(executable)], cwd=repository, capture_output=True, timeout=10)
        except OSError:
            return
        raise ValueError("command fileをOSが受理したので、spawn errorが起きません")
    if termination == "signal":
        completed = subprocess.run([str(executable)], cwd=repository, capture_output=True, timeout=10)
        if completed.returncode != -signal.SIGTERM:
            raise ValueError("commandがsignalで終了しませんでした")
        return
    # timeout: graceful terminationでは足りず、強制終了で終わらなければならない。
    process = subprocess.Popen([str(executable)], cwd=repository, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True, text=True)
    try:
        deadline = time.monotonic() + 5
        # trapが設定済みになるよう、準備完了の行を待つ。それより前にsignalを送っても、
        # 保護されていない起動直後を終了できることしか示せない。
        if not select.select([process.stdout], [], [], 5)[0]:
            raise ValueError("commandが準備完了の行を出力しませんでした")
        if process.stdout.readline().strip() != READY:
            raise ValueError("commandが準備完了を知らせませんでした")
        os.killpg(process.pid, signal.SIGTERM)
        time.sleep(0.5)
        if process.poll() is not None:
            raise ValueError("commandがgraceful terminationで停止したので、強制終了が必要ありません")
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=max(0.1, deadline - time.monotonic()))
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()


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
            command = result["commands"][0]
            if command["exitCode"] is not None or command["status"] != "error":
                raise ValueError("exit以外の終了は、終了コードなしとerror statusを返す必要があります")
            if command["stdoutExcerpt"] != expected_stdout(identifier) or command["stderrExcerpt"]:
                raise ValueError("commandの抜粋がreview済みの出力と異なります")
            inputs = reviewed_inputs(identifier)
            expected_executables = executables(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs):
                raise ValueError("入力が審査済みcorpusと異なります")
            for name, path in files.items():
                if path.is_symlink() or path.read_bytes() != inputs[name]:
                    raise ValueError("入力が審査済みcorpusと異なります")
                if bool(path.stat().st_mode & 0o111) != (name in expected_executables):
                    raise ValueError(f"{name}の実行bitが審査済み入力と異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-verify-process-") as temporary:
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
                        observe_termination(identifier, repository)
                    if compare_state(effects["after"], observe(repository, external)):
                        raise ValueError("commandの観測でfixtureの状態が変わりました")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "observed_terminations": True,
            "status": "Passed" if not errors else "Failed", "errors": errors}
