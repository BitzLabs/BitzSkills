"""verifyのargv検査・実行環境fixture（SINGLE-126-01〜05、07、09〜11）の審査済み証跡。Coreは実行しない。

全caseはSINGLE-042のcorpusを基にcommand定義だけを替え、indexへstageしてから`verify REQ-001`を実行する。
126-01〜05はargv templateの型・値域違反で操作全体を停止し、Contextもcommandも作らない。
126-07、10、11はcommandを実行し、auditがfixture自身のscriptを直接起動して、期待した入力でだけ
成功することを観測する。126-09はPATHから実行fileを解決できずspawn前にblockedとなる。
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_crosscheck, digest_reference
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
TEST_PATHS = ["tests/test_auth.py", "tests/test_session.py"]
STATEMENTS = ["REQ-001:AC-01", "REQ-001:AC-02"]
BASE_ARGV = '"/bin/true", "{tests}"'
ARGV_KEY = "verify.commands.default.argv"
ELEMENT_LIMIT = 32 * 1024
# 名前にredaction keywordを含まない環境変数だけを使い、公開抜粋へ影響させない。
PROBE_ENV = {"BITZ_FIXTURE_PROBE": "inherited-value", "LANG": "C.UTF-8", "LC_COLLATE": "C",
             "PWD": "/bitz-fixture-stale-pwd"}
ABSENT_COMMAND = "bitz-fixture-absent-command"
REDACTION_WORDS = ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "API_KEY", "PRIVATE_KEY", "CREDENTIAL", "AUTH")

ARGS_SCRIPT = (
    "#!/bin/sh\n"
    "# 空stringのargv[1]を1引数として受け取った場合だけ成功する。\n"
    '[ "$#" -eq 3 ] || exit 1\n'
    '[ -z "$1" ] || exit 1\n'
    '[ "$2" = tests/test_auth.py ] && [ "$3" = tests/test_session.py ] || exit 1\n'
    "exit 0\n"
)
STDIN_SCRIPT = (
    "#!/bin/sh\n"
    "# stdinが即時EOFで、1byteも読めない場合だけ成功する。\n"
    "if IFS= read -r line; then exit 1; fi\n"
    '[ -z "$line" ] || exit 1\n'
    "exit 0\n"
)
PROBE_SCRIPT = (
    "#!/usr/bin/awk -f\n"
    "# 起動環境を継承し、PWDだけが実効cwdの絶対pathへ置き換わった場合だけ成功する。\n"
    "# shはPWDを起動時に再計算するため、環境をそのまま読めるawkで観測する。\n"
    "BEGIN {\n"
    "    if (ENVIRON[\"BITZ_FIXTURE_PROBE\"] != \"inherited-value\") exit 11\n"
    "    if (ENVIRON[\"LANG\"] != \"C.UTF-8\") exit 12\n"
    "    if (ENVIRON[\"LC_COLLATE\"] != \"C\") exit 13\n"
    "    pwd = ENVIRON[\"PWD\"]\n"
    "    if (pwd == \"/bitz-fixture-stale-pwd\") exit 14\n"
    "    if (substr(pwd, 1, 1) != \"/\") exit 15\n"
    "    if ((getline line < (pwd \"/probe.awk\")) <= 0) exit 16\n"
    "    count = split(pwd, parts, \"/\")\n"
    "    if (parts[count] != \"tests\") exit 17\n"
    "    if (ARGC != 3 || ARGV[1] != \"test_auth.py\" || ARGV[2] != \"test_session.py\") exit 18\n"
    "    exit 0\n"
    "}\n"
)

# id: (説明, argv template text, 期待status)
CASES = {
    "SINGLE-126-01": ("argv要素が非stringならcommandを起動しない", '"/bin/true", 42, "{tests}"', "error"),
    "SINGLE-126-02": ("argv[0]が空stringならcommandを起動しない", '"", "{tests}"', "error"),
    "SINGLE-126-03": ("argv要素にNULがあればcommandを起動しない", '"/bin/true", "a\\0b", "{tests}"', "error"),
    "SINGLE-126-04": ("argv templateが256要素を超えればcommandを起動しない",
                      '"/bin/true", ' + '"-v", ' * 255 + '"{tests}"', "error"),
    "SINGLE-126-05": ("argv templateの1要素が32 KiBを超えればcommandを起動しない",
                      '"/bin/true", "' + "a" * (ELEMENT_LIMIT + 1) + '", "{tests}"', "error"),
    "SINGLE-126-07": ("argv[1:]の空stringを1引数として変更せず渡す", '"bin/args.sh", "", "{tests}"', "passed"),
    "SINGLE-126-09": ("PATH上に実行fileがなければspawn前にblockedとする",
                      f'"{ABSENT_COMMAND}", "{{tests}}"', "blocked"),
    "SINGLE-126-10": ("stdinをnull deviceへ接続し即時EOFとする", '"bin/stdin.sh", "{tests}"', "passed"),
    "SINGLE-126-11": ("起動環境を継承しPWDだけを実効cwdへ合わせる", '"./probe.awk", "{tests}"', "passed"),
}
# 設定違反caseの(key, summary)。
CONFIG_ERRORS = {
    "SINGLE-126-01": (ARGV_KEY + "[1]", "argvの要素はstringで指定してください"),
    "SINGLE-126-02": (ARGV_KEY + "[0]", "argv[0]は空stringにできません"),
    "SINGLE-126-03": (ARGV_KEY + "[1]", "argvの要素にNULは使用できません"),
    "SINGLE-126-04": (ARGV_KEY, "argv templateは256要素以下で指定してください"),
    "SINGLE-126-05": (ARGV_KEY + "[1]", "argvの各要素はUTF-8で32 KiB以下で指定してください"),
}
SCRIPTS = {
    "SINGLE-126-07": ("bin/args.sh", ARGS_SCRIPT),
    "SINGLE-126-10": ("bin/stdin.sh", STDIN_SCRIPT),
    "SINGLE-126-11": ("tests/probe.awk", PROBE_SCRIPT),
}
ENVIRONMENTS = {"SINGLE-126-11": PROBE_ENV}
BLOCKED_SUMMARY = "command実行fileをPATHから解決できません"


def cwd(identifier):
    return "tests" if identifier == "SINGLE-126-11" else "."


def config(identifier):
    body = digest_reference.CONFIG.replace(BASE_ARGV, CASES[identifier][1])
    if identifier == "SINGLE-126-11":
        body = body.replace("      cwd: .\n", "      cwd: tests\n")
    return body


def template(identifier):
    """設定のflow配列を独立にdecodeする。YAMLの`\\0`だけをJSONの`\\u0000`へ読み替える。"""
    return json.loads("[" + CASES[identifier][1].replace("\\0", "\\u0000") + "]")


def template_violations(argv):
    """workspace・設定仕様 §6のargv template規則を独立に適用し、(key)の一覧を返す。"""
    violations = []
    if not 1 <= len(argv) <= 256:
        violations.append(ARGV_KEY)
    for index, value in enumerate(argv):
        if not isinstance(value, str):
            violations.append(f"{ARGV_KEY}[{index}]")
        elif "\0" in value or len(value.encode()) > ELEMENT_LIMIT or (index == 0 and value == ""):
            violations.append(f"{ARGV_KEY}[{index}]")
    if sum(len(v.encode()) for v in argv if isinstance(v, str)) > 1024 * 1024:
        violations.append(ARGV_KEY)
    return violations


def reviewed_inputs(identifier):
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    inputs[digest_reference.CONFIG_PATH] = config(identifier).encode()
    if identifier in SCRIPTS:
        path, content = SCRIPTS[identifier]
        inputs[path] = content.encode()
    return inputs


def executables(identifier):
    return {SCRIPTS[identifier][0]} if identifier in SCRIPTS else set()


def reviewed_digest_input(identifier):
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    command = payload["settings"]["commands"][0]
    command["argv"] = template(identifier)
    command["cwd"] = cwd(identifier)
    return payload


def context_digest(identifier):
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


def reviewed_manifest(identifier):
    status = CASES[identifier][2]
    return {
        "fixtureId": identifier,
        "description": CASES[identifier][0],
        "setup": {"git": True, "operations": [{"op": "stage", "paths": ["."]}]},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": ["verify", "REQ-001", "--format", "json"],
                       "env": dict(ENVIRONMENTS.get(identifier, {}))},
        "expect": {"status": status, "exitCode": {"passed": 0, "blocked": 2, "error": 3}[status],
                   "stdout": "json", "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def expanded_argv(identifier):
    argv = template(identifier)
    # cwd指定時はtest pathをcwd相対で展開する。
    paths = [path.removeprefix("tests/") for path in TEST_PATHS] if cwd(identifier) == "tests" else TEST_PATHS
    index = argv.index("{tests}")
    return argv[:index] + paths + argv[index + 1:]


def reviewed_result(identifier):
    status = CASES[identifier][2]
    result = {"schemaVersion": "1.0", "operation": "verify", "status": status, "scope": "selected",
              "workspace": {"id": "root", "path": "."}, "targetResults": [], "revision": None,
              "commands": [], "durationMs": 0, "diagnostics": []}
    if identifier in CONFIG_ERRORS:
        # workspace identityを構成する前に停止するため、idはnull、派生配列は空とする。
        key, summary = CONFIG_ERRORS[identifier]
        result["workspace"]["id"] = None
        result["diagnostics"] = [{"code": "SPEC-CONFIG-SCHEMA-001", "severity": "error", "resultStatus": "error",
                                  "summary": summary, "source": {"kind": "file", "workspaceId": None,
                                                                 "path": digest_reference.CONFIG_PATH, "key": key}}]
        return result
    executed = status == "passed"
    result["targetResults"] = [{"target": "REQ-001", "status": status, "contextDigest": context_digest(identifier),
                                "statements": list(STATEMENTS),
                                "bindingRefs": ["root::default"] if executed else [], "diagnostics": []}]
    if executed:
        result["commands"] = [{
            "bindingId": "root::default", "workspaceId": "root", "name": "default", "status": "passed",
            "termination": "exit", "cwd": cwd(identifier), "argv": expanded_argv(identifier),
            "tests": list(TEST_PATHS), "covers": list(STATEMENTS), "exitCode": 0, "timeoutSeconds": 300,
            "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False, "stderrTruncated": False,
            "durationMs": 0}]
    else:
        # spawn前のblockedは単一workspaceではtop-levelへ1件だけ置き、targetへ複製しない。
        result["diagnostics"] = [{"code": "SPEC-VERIFY-BLOCKED-001", "severity": "error", "resultStatus": "blocked",
                                  "summary": BLOCKED_SUMMARY,
                                  "source": {"kind": "environment", "component": "command",
                                             "identifier": "root::default"}}]
    return result


def run_script(repository, identifier, argv, env=None, stdin=subprocess.DEVNULL, directory=None):
    path = repository / SCRIPTS[identifier][0]
    if not (path.is_file() and os.access(path, os.X_OK)):
        raise ValueError("command fileは実行可能な通常fileである必要があります")
    return subprocess.run([str(path), *argv], cwd=directory or repository, env=env, stdin=stdin,
                          capture_output=True, timeout=10)


def observe_command(identifier, repository):
    """fixture自身のcommand入力を直接観測する。Core verifyの実行ではない。"""
    if identifier == "SINGLE-126-09":
        if shutil.which(ABSENT_COMMAND) is not None or (repository / ABSENT_COMMAND).exists():
            raise ValueError("不在のはずのcommandがPATHから解決できてしまいます")
        return
    if identifier == "SINGLE-126-07":
        if run_script(repository, identifier, ["", *TEST_PATHS]).returncode != 0:
            raise ValueError("審査済みargvをscriptが拒否しています")
        if run_script(repository, identifier, TEST_PATHS).returncode == 0:
            raise ValueError("空引数のないargvをscriptが受理しています")
    elif identifier == "SINGLE-126-10":
        if run_script(repository, identifier, TEST_PATHS).returncode != 0:
            raise ValueError("即時EOFでscriptが成功しません")
        if run_script(repository, identifier, TEST_PATHS, stdin=subprocess.PIPE).returncode != 0:
            raise ValueError("空で閉じたpipeもEOFとして読める必要があります")
        with subprocess.Popen([str(repository / SCRIPTS[identifier][0])], cwd=repository, stdin=subprocess.PIPE,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
            process.communicate(b"typed\n", timeout=10)
            if process.returncode == 0:
                raise ValueError("読めるstdinをscriptが無視しています")
    elif identifier == "SINGLE-126-11":
        if not os.access("/usr/bin/awk", os.X_OK):
            raise ValueError("probeには/usr/bin/awkが必要です")
        directory = repository / "tests"
        arguments = ["test_auth.py", "test_session.py"]
        good = {**os.environ, **PROBE_ENV, "PWD": str(directory.resolve())}
        if run_script(repository, identifier, arguments, env=good, directory=directory).returncode != 0:
            raise ValueError("実効PWDを持つ継承環境をscriptが拒否しています")
        for broken in ({**good, "PWD": PROBE_ENV["PWD"]}, {k: v for k, v in good.items() if k != "BITZ_FIXTURE_PROBE"},
                       {**good, "LANG": "C"}):
            if run_script(repository, identifier, arguments, env=broken, directory=directory).returncode == 0:
                raise ValueError("Coreが作ってはならない環境をscriptが受理しています")


def check_host_environment(expected_outputs):
    """redaction対象名の環境変数値が期待出力に現れないことを確認する。現れれば抜粋が実行環境へ依存する。"""
    for name, value in os.environ.items():
        if value and any(word in name.upper() for word in REDACTION_WORDS):
            if any(value in output for output in expected_outputs):
                raise ValueError(f"実行環境の変数{name}が審査済み抜粋を変えてしまいます")


def check_inputs(fixture, inputs, expected_executables):
    files = {p.relative_to(fixture / "repo").as_posix(): p
             for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
    if set(files) != set(inputs):
        raise ValueError("入力が審査済みcorpusと異なります")
    for name, path in files.items():
        if path.is_symlink() or path.read_bytes() != inputs[name]:
            raise ValueError("入力が審査済みcorpusと異なります")
        if bool(path.stat().st_mode & 0o111) != (name in expected_executables):
            raise ValueError(f"{name}の実行bitが審査済み入力と異なります")


def check_setups(fixture, manifest, effects, identifier, digest, observe_once, prefix):
    """隔離setupを2回行い、snapshot、2系統Digest、直接観測後の不変を確認する。"""
    if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
        raise ValueError("read-only期待が書込みを許しています")
    previous = None
    with tempfile.TemporaryDirectory(prefix=prefix) as temporary:
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
            if digest is not None:
                derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository))
                if digest_crosscheck.digest(derived) != digest:
                    raise ValueError("target Digestが2系統のreferenceで一致しません")
            if run == 0:
                observe_once(identifier, repository)
            if compare_state(effects["after"], observe(repository, external)):
                raise ValueError("commandの観測がfixtureの状態を変えました")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
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
            violations = template_violations(template(identifier))
            expected_violations = [CONFIG_ERRORS[identifier][0]] if identifier in CONFIG_ERRORS else []
            if violations != expected_violations:
                raise ValueError(f"argv templateの違反が審査済みの単一原因と異なります: {violations}")
            if len(config(identifier).encode()) > 64 * 1024:
                raise ValueError("設定fileは64 KiBの入力上限内である必要があります")
            if any(command["argv"] != expanded_argv(identifier) for command in result["commands"]):
                raise ValueError("公開argvはtemplateを保持し{tests}だけを展開する必要があります")
            check_inputs(fixture, reviewed_inputs(identifier), executables(identifier))
            digest = None if identifier in CONFIG_ERRORS else context_digest(identifier)
            check_setups(fixture, manifest, effects, identifier, digest,
                         lambda i, r: None if i in CONFIG_ERRORS else observe_command(i, r), "bitz-verify-argv-")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "observed_commands": True,
            "status": "Passed" if not errors else "Failed", "errors": errors}
