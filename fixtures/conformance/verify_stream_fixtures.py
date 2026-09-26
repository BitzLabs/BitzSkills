"""verifyのprocess終了・出力変換fixture（SINGLE-126-12〜16）の審査済み証跡。Coreは実行しない。

126-12はtimeout後に直接processが終了しても、別sessionへ逃げた子孫がstdout／stderrを保持し続けるcase、
126-13はtimeoutしたbindingの後に独立bindingを実行するcaseである。
126-14〜16は安全な入出力 §9の出力変換とredactionを固定する。auditはfixture自身のscriptを直接起動して
raw出力を観測し、独立に実装した変換で期待抜粋を再計算する。
"""
import copy
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import subprocess
import time

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_reference, verify_fixtures, verify_process_fixtures
from .verify_argv_fixtures import check_inputs, check_setups

HERE = Path(__file__).resolve().parent
TEST_PATHS = ["tests/test_auth.py", "tests/test_session.py"]
STATEMENTS = ["REQ-001:AC-01", "REQ-001:AC-02"]
BASE_ARGV = '"/bin/true", "{tests}"'
LIMIT = 65536
REDACTED = "[REDACTED]"
TIMEOUT_SUMMARY = "commandが実効timeout 1秒で終了しませんでした"

ORPHAN_READY = "orphan-ready"
# 直接processはTERMで終了するが、setsidで別sessionへ移った子孫がTERMを無視し、
# 継承したstdout／stderrを8秒保持する。EOFを待つ実装は5秒以内に結果を確定できない。
ORPHAN_SCRIPT = (
    "#!/bin/sh\n"
    # 子孫が別sessionへ移りtrapを設定した後にだけreadiness行を出し、TERMとの競合を避ける。
    f"setsid sh -c 'trap \"\" TERM; echo {ORPHAN_READY}; exec sleep 8' &\n"
    "i=0\n"
    'while [ "$i" -lt 60 ]; do\n'
    "    sleep 1\n"
    "    i=$((i + 1))\n"
    "done\n"
)
CONTROL_SCRIPT = (
    "#!/bin/sh\n"
    "printf 'bad:\\377\\r\\nlone\\rtab:\\tend\\n'\n"
    "printf 'esc:\\033[31mred\\033[0m\\n'\n"
    "printf 'c0:\\001 del:\\177 c1:\\302\\205\\n'\n"
    "printf 'err\\r\\n' >&2\n"
)
CONTROL_STDOUT = ("bad:\ufffd\nlone\ntab:\tend\n"
                  "esc:\\u001b[31mred\\u001b[0m\n"
                  "c0:\\u0001 del:\\u007f c1:\\u0085\n")
CONTROL_STDERR = "err\n"
SECRET_ENV = {"BITZ_FIXTURE_TOKEN": "s3cr3t-env-value-0123456789"}
# 各一致の途中でsleepを挟み、別々のreadへ分かれるようにする。
SECRET_SCRIPT = (
    "#!/bin/sh\n"
    "printf 'probe s3cr3t-env-'\n"
    "sleep 0.2\n"
    "printf 'value-0123456789 end\\nAuthor'\n"
    "sleep 0.2\n"
    "printf 'ization:dXNlcjpwYXNz\\ncall Bea'\n"
    "sleep 0.2\n"
    "printf 'rer abc.def-123 done\\npass'\n"
    "sleep 0.2\n"
    "printf 'word=hunter2\\n-----BEGIN RSA PRIVATE KEY-----\\nMIIBOgIBAAJB'\n"
    "sleep 0.2\n"
    "printf 'AKj34\\n-----END RSA PRIV'\n"
    "sleep 0.2\n"
    "printf 'ATE KEY-----\\nafter\\n'\n"
)
SECRET_STDOUT = (f"probe {REDACTED} end\n"
                 f"Authorization:{REDACTED}\n"
                 f"call Bearer {REDACTED} done\n"
                 f"password={REDACTED}\n"
                 f"{REDACTED}\n"
                 "after\n")
EXPAND_ENV = {"BITZ_FIXTURE_SECRET": "qz"}
EXPAND_COUNT = 6553
# 「あ」(3 byte)の後に2 byteの値を6553回、最後に"end\n"。redaction後は65,537 byteとなり、
# 末尾65,536 byteの切れ目が「あ」の途中へ落ちるため、code point境界で65,534 byteを保持する。
EXPAND_SCRIPT = (
    "#!/bin/sh\n"
    "printf '\\343\\201\\202'\n"
    "i=0\n"
    f'while [ "$i" -lt {EXPAND_COUNT} ]; do\n'
    "    printf 'qz'\n"
    "    i=$((i + 1))\n"
    "done\n"
    "printf 'end\\n'\n"
)
EXPAND_STDOUT = REDACTED * EXPAND_COUNT + "end\n"

# id: (説明, 期待status, script path, script, 追加環境, timeout)
CASES = {
    "SINGLE-126-12": ("子孫processがstdout／stderrを保持してもtimeoutから5秒以内に確定する",
                      "error", "bin/orphan.sh", ORPHAN_SCRIPT, {}, 1),
    "SINGLE-126-13": ("timeoutしたbindingの後も独立bindingを実行して結果を保持する",
                      "error", "bin/hang.sh", verify_process_fixtures.HANG_SCRIPT, {}, 1),
    "SINGLE-126-14": ("不正UTF-8、CR、ESC、C0／DEL／C1を決定論的に変換する",
                      "passed", "bin/controls.sh", CONTROL_SCRIPT, {}, 300),
    "SINGLE-126-15": ("chunk境界をまたぐ環境secretと定型secretをすべて置換する",
                      "passed", "bin/secrets.sh", SECRET_SCRIPT, SECRET_ENV, 300),
    "SINGLE-126-16": ("redactionで64 KiBを超えた公開文字列をcode point境界の末尾で保持する",
                      "passed", "bin/expand.sh", EXPAND_SCRIPT, EXPAND_ENV, 300),
}
EXPECTED_OUTPUT = {
    "SINGLE-126-12": (ORPHAN_READY + "\n", ""),
    "SINGLE-126-13": (verify_process_fixtures.READY + "\n", ""),
    "SINGLE-126-14": (CONTROL_STDOUT, CONTROL_STDERR),
    "SINGLE-126-15": (SECRET_STDOUT, ""),
    "SINGLE-126-16": (EXPAND_STDOUT, ""),
}
# 126-13のbinding。alphaがtimeoutし、辞書順で後のbetaが続けて実行される。
TWO_COMMANDS = ("verify:\n  timeoutSeconds: 1\n  commands:\n"
                "    alpha:\n      argv: [\"bin/hang.sh\", \"{tests}\"]\n      cwd: .\n"
                "    beta:\n      argv: [\"/bin/true\", \"{tests}\"]\n      cwd: .\n")
TWO_TESTS = verify_fixtures.BOTH_TESTS.replace("command: default", "command: alpha", 1).replace(
    "command: default", "command: beta", 1)


def config(identifier):
    _, _, path, _, _, timeout = CASES[identifier]
    if identifier == "SINGLE-126-13":
        head = digest_reference.CONFIG[:digest_reference.CONFIG.index("verify:\n")]
        return head + TWO_COMMANDS
    body = digest_reference.CONFIG.replace(BASE_ARGV, f'"{path}", "{{tests}}"')
    if timeout != 300:
        body = body.replace("verify:\n", f"verify:\n  timeoutSeconds: {timeout}\n", 1)
    return body


def reviewed_inputs(identifier):
    _, _, path, script, _, _ = CASES[identifier]
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    inputs[digest_reference.CONFIG_PATH] = config(identifier).encode()
    inputs[path] = script.encode()
    if identifier == "SINGLE-126-13":
        inputs[digest_reference.TECH_PATH] = verify_fixtures.technical_document(TWO_TESTS).encode()
    return inputs


def executables(identifier):
    return {CASES[identifier][2]}


def reviewed_digest_input(identifier):
    _, _, path, _, _, timeout = CASES[identifier]
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    payload["settings"]["verifyTimeouts"][0]["timeoutSeconds"] = timeout
    if identifier == "SINGLE-126-13":
        payload["settings"]["commands"] = [
            {"workspaceId": "root", "name": "alpha", "argv": [path, "{tests}"], "cwd": "."},
            {"workspaceId": "root", "name": "beta", "argv": ["/bin/true", "{tests}"], "cwd": "."}]
        technical = next(d for d in payload["documents"] if d["id"] == "TECH-001")
        for test, name in zip(technical["frontmatter"]["tests"], ("alpha", "beta")):
            test["command"] = name
    else:
        payload["settings"]["commands"][0]["argv"] = [path, "{tests}"]
    return payload


def context_digest(identifier):
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


def reviewed_manifest(identifier):
    description, status, _, _, env, _ = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": {"git": True, "operations": [{"op": "stage", "paths": ["."]}]},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": ["verify", "REQ-001", "--format", "json"],
                       "env": dict(env)},
        "expect": {"status": status, "exitCode": 0 if status == "passed" else 3, "stdout": "json",
                   "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def command(name, path, tests, covers, status, termination, timeout, stdout, stderr):
    return {"bindingId": f"root::{name}", "workspaceId": "root", "name": name, "status": status,
            "termination": termination, "cwd": ".", "argv": [path, *tests], "tests": list(tests),
            "covers": list(covers), "exitCode": 0 if termination == "exit" else None,
            "timeoutSeconds": timeout, "stdoutExcerpt": stdout, "stderrExcerpt": stderr,
            "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}


def reviewed_result(identifier):
    _, status, path, _, _, timeout = CASES[identifier]
    stdout, stderr = EXPECTED_OUTPUT[identifier]
    diagnostics = []
    if identifier == "SINGLE-126-13":
        commands = [command("alpha", path, TEST_PATHS[:1], STATEMENTS[:1], "error", "timeout", timeout, stdout, stderr),
                    command("beta", "/bin/true", TEST_PATHS[1:], STATEMENTS[1:], "passed", "exit", timeout, "", "")]
    elif status == "error":
        commands = [command("default", path, TEST_PATHS, STATEMENTS, "error", "timeout", timeout, stdout, stderr)]
    else:
        commands = [command("default", path, TEST_PATHS, STATEMENTS, "passed", "exit", timeout, stdout, stderr)]
    for entry in commands:
        if entry["termination"] == "timeout":
            diagnostics.append({"code": "SPEC-VERIFY-TIMEOUT-001", "severity": "error", "resultStatus": "error",
                                "summary": TIMEOUT_SUMMARY,
                                "source": {"kind": "environment", "component": "command",
                                           "identifier": entry["bindingId"]}})
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": status, "scope": "selected",
        "workspace": {"id": "root", "path": "."},
        "targetResults": [{"target": "REQ-001", "status": status, "contextDigest": context_digest(identifier),
                           "statements": list(STATEMENTS),
                           "bindingRefs": [entry["bindingId"] for entry in commands], "diagnostics": []}],
        "revision": None, "commands": commands, "durationMs": 0, "diagnostics": diagnostics,
    }


def convert_controls(raw):
    """安全な入出力 §9の制御文字処理を独立に適用する。"""
    text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    return "".join(f"\\u{ord(c):04x}" if (ord(c) < 32 and c not in "\t\n") or 127 <= ord(c) <= 159 else c
                   for c in text)


REDACTION_WORDS = ("token", "secret", "password", "passwd", "api_key", "private_key", "credential", "auth")
LINE_VALUE = re.compile("(" + "|".join(REDACTION_WORDS) + r")([:=])[^\n]+", re.IGNORECASE)
AUTHORIZATION = re.compile(r"(Authorization:)[^\n]+")
BEARER = re.compile(r"(Bearer )[^\s]+", re.IGNORECASE)
PEM = re.compile(r"-----BEGIN [^\n]*PRIVATE KEY-----.*?-----END [^\n]*PRIVATE KEY-----", re.DOTALL)


def redact(text, env):
    """全文を一括で処理する参照実装。chunk分割に依存しない期待値を与える。

    値は区切り記号の直後から行末までとし、区切り記号自体とBearer語は残す。PEMは開始行から終了行までを1つに置換する。
    """
    secrets = sorted(((name, value) for name, value in env.items()
                      if value and any(word.upper() in name.upper() for word in REDACTION_WORDS)),
                     key=lambda item: (-len(convert_controls(item[1].encode()).encode()), item[0]))
    for _, value in secrets:
        text = text.replace(convert_controls(value.encode()), REDACTED)
    text = PEM.sub(REDACTED, text)
    text = AUTHORIZATION.sub(lambda m: m.group(1) + REDACTED, text)
    text = BEARER.sub(lambda m: m.group(1) + REDACTED, text)
    return LINE_VALUE.sub(lambda m: m.group(1) + m.group(2) + REDACTED, text)


def excerpt(text):
    """UTF-8末尾65,536 byteをcode point境界で保持する。"""
    data = text.encode()[-LIMIT:]
    while data and (data[0] & 0xC0) == 0x80:
        data = data[1:]
    return data.decode()


def observation_env(env):
    """観測に使う環境。PATHとfixtureのenvだけにし、実行環境へ依存させない。

    runnerがCoreへ渡す環境はこれにHOME・XDG_CACHE_HOME・TMPDIRを加えたもので、どれもredaction対象名ではないため、
    redactionする値の集合はCoreと一致する。実行環境を継承すると、redaction対象名の変数（値`1`など）が
    観測側の抜粋だけを変えてしまう。
    """
    return {"PATH": os.environ.get("PATH", ""), **env}


def run_script(repository, identifier, env):
    path = repository / CASES[identifier][2]
    if not (path.is_file() and os.access(path, os.X_OK)):
        raise ValueError("command fileは実行可能な通常fileである必要があります")
    return subprocess.run([str(path), *TEST_PATHS], cwd=repository, env=observation_env(env),
                          stdin=subprocess.DEVNULL, capture_output=True, timeout=30)


def observe_orphan(repository):
    """直接processはTERMで終わるが、別sessionの子孫がpipeを保持しEOFが来ないことを観測する。"""
    if shutil.which("setsid") is None:
        raise ValueError("このfixtureにはsetsidが必要です")
    process = subprocess.Popen([str(repository / CASES["SINGLE-126-12"][2])], cwd=repository,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        if not select.select([process.stdout], [], [], 5)[0]:
            raise ValueError("commandからreadiness行が届きません")
        if process.stdout.readline().decode().strip() != ORPHAN_READY:
            raise ValueError("commandがreadiness行を出しませんでした")
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)
        if process.returncode != -signal.SIGTERM:
            raise ValueError("直接processはgraceful terminationで終了する必要があります")
        # 直接processの終了後も、子孫が保持するpipeは5秒以上EOFにならない。
        started = time.monotonic()
        while time.monotonic() - started < 5.5:
            if select.select([process.stdout], [], [], 0.5)[0] and not process.stdout.read1(1):
                raise ValueError("pipeがEOFになり、子孫processが保持していません")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if select.select([process.stdout], [], [], 0.5)[0] and not process.stdout.read1(1):
                return
        raise ValueError("子孫processが有限時間内にpipeを解放しませんでした")
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()


def observe_command(identifier, repository):
    """fixture自身のcommandを直接起動し、raw出力から期待抜粋を独立に再計算する。Core verifyの実行ではない。"""
    if identifier == "SINGLE-126-12":
        observe_orphan(repository)
        return
    if identifier == "SINGLE-126-13":
        verify_process_fixtures.observe_termination("SINGLE-059", repository)
        if subprocess.run(["/bin/true", TEST_PATHS[1]], cwd=repository, timeout=10).returncode != 0:
            raise ValueError("独立bindingは成功する必要があります")
        return
    env = CASES[identifier][4]
    completed = run_script(repository, identifier, env)
    if completed.returncode != 0:
        raise ValueError("commandは終了コード0で終わる必要があります")
    raw_limit_ok = all(len(stream) <= LIMIT for stream in (completed.stdout, completed.stderr))
    if not raw_limit_ok:
        raise ValueError("truncatedをfalseに保つため、raw streamは上限内である必要があります")
    actual = tuple(excerpt(redact(convert_controls(stream), observation_env(env)))
                   for stream in (completed.stdout, completed.stderr))
    if actual != EXPECTED_OUTPUT[identifier]:
        raise ValueError("独立に変換した出力が審査済み抜粋と異なります")
    if identifier == "SINGLE-126-16":
        redacted = redact(convert_controls(completed.stdout), env).encode()
        if not len(redacted) > LIMIT >= len(completed.stdout) or len(actual[0].encode()) != LIMIT - 2:
            raise ValueError("redaction後のstreamは上限を超え、切れ目がcode pointの途中に落ちる必要があります")
    for value in env.values():
        if value in "".join(actual):
            raise ValueError("抜粋にsecretの生値が残っています")


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
            check_inputs(fixture, reviewed_inputs(identifier), executables(identifier))
            check_setups(fixture, manifest, effects, identifier, context_digest(identifier),
                         observe_command, "bitz-verify-stream-")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "observed_commands": True,
            "status": "Passed" if not errors else "Failed", "errors": errors}
