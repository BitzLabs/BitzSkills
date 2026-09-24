"""参照harness自身の自己試験用の偽Core生成器(ADR-052 Decision 5)。

期待どおりの出力をそのまま返す偽の`bitz` source treeを、呼び出し側が指定した一時directoryへ
生成する。生成物(source tree、uv.lock、build成果物)はrepositoryへ置かず、この生成器だけを
commit対象にする。生成はfixtures/conformanceの内容だけから決定論的に行い、`bitz`をimportしない
(ADR-049 Decision 6)。`setup.generate`を持つ生成fixtureと`runner: package`は対象外とする
(packageはCore実行体を起動せず`package_check.py`が直接source tree・wheel・venvを検査するため、
pyproject.toml・uv.lockの内容そのものが検査対象になる)。
"""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator

from .harness import setup, snapshot
from .runner import default_python_minor
from .schemas import schema_path

CONFORMANCE_ROOT = Path(__file__).resolve().parent
GIT_VERSION_RE = re.compile(r"git version (\d+\.\d+\.\d+)")
_RESULT_VALIDATOR = None


def _result_validator():
    global _RESULT_VALIDATOR
    if _RESULT_VALIDATOR is None:
        schema = json.loads(schema_path(CONFORMANCE_ROOT, "result").read_text(encoding="utf-8"))
        _RESULT_VALIDATOR = Draft202012Validator(schema)
    return _RESULT_VALIDATOR


class FakeCoreBuildError(Exception):
    """生成時に一意な応答を決定できないことを表す。"""


def _locate_fixture_root(identifier):
    for kind in ("single", "multi"):
        candidate = CONFORMANCE_ROOT / kind / identifier
        if candidate.is_dir():
            return candidate
    raise FakeCoreBuildError(f"fixture directoryが見つかりません: {identifier}")


def _tree_digest(root):
    """cwd配下tree(.git除く)のpath・種別・byte列・実行bitから決まる digest。

    `bitz/_engine.py`(生成物)の`_tree_digest`と同じ算法(snapshotの正規化JSONのSHA-256)を使う。
    アルゴリズムが分岐すると生成時keyと実行時keyが一致しなくなるため、変更する場合は両方を直す。
    """
    data = snapshot(root)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _probe_git_version(path_value):
    try:
        completed = subprocess.run(["git", "--version"], env={"PATH": path_value},
                                    capture_output=True, text=True, timeout=10)
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    match = GIT_VERSION_RE.search(completed.stdout)
    return match.group(1) if match else None


def _git_version_key(invocation, host_path):
    """実行時に偽Coreが観測するGit版と同じ値を、生成時に同じ規則で予測する。"""
    if "gitVersion" in invocation:
        return invocation["gitVersion"]
    path_value = invocation.get("env", {}).get("PATH", host_path)
    return _probe_git_version(path_value)


def _vcs_state_key(setup_plan, git_version):
    """cwd配下treeのdigestだけでは、同じ内容のtreeでGit初期化・commit有無だけが違う
    fixture(例: SINGLE-042とSINGLE-105-01は同じrepo/だが一方はunborn、他方はcommit済み)を
    区別できない。そのため`git rev-parse`相当の観測結果を独立したkey要素として加える。
    Git自体が解決できない(gitVersionがNone)場合は、setup.gitの値によらず"no-repo"として扱う
    (`bitz/_engine.py`の`_detect_vcs_state`と同じ規則)。
    """
    if git_version is None or not setup_plan["git"]:
        return "no-repo"
    return "committed" if "baseCommit" in setup_plan else "unborn"


def _mutation_candidates(payload):
    """statusを変えずSchema適合を保てそうな改変の候補を、operationの形に応じて列挙する。

    候補ごとに実際に適用してresult.schema.jsonで検証し、最初に適合したものを採用する
    (どのfieldが存在するかはoperationごとに違うため、決め打ちにせず候補を並べて安全側を選ぶ)。
    """
    candidates = []
    if payload.get("diagnostics"):
        def _apply(p):
            first = p["diagnostics"][0]
            first["summary"] = (first.get("summary") or "") + "(mutated)"
        candidates.append(_apply)
    if payload.get("checks"):
        def _apply(p):
            current = p["checks"][0]["status"]
            alternative = next(value for value in ("passed", "info", "warning", "blocked") if value != current)
            p["checks"][0]["status"] = alternative
        candidates.append(_apply)
    if payload.get("scope") in ("full", "selected"):
        def _apply(p):
            p["scope"] = "selected" if p["scope"] == "full" else "full"
        candidates.append(_apply)
    if isinstance(payload.get("checkedDocumentCount"), int):
        def _apply(p):
            p["checkedDocumentCount"] = p["checkedDocumentCount"] + 1
        candidates.append(_apply)
    if isinstance(payload.get("checkedStatementCount"), int):
        def _apply(p):
            p["checkedStatementCount"] = p["checkedStatementCount"] + 1
        candidates.append(_apply)
    if payload.get("targetResults") and payload["targetResults"][0].get("statements"):
        def _apply(p):
            statements = p["targetResults"][0]["statements"]
            p["targetResults"][0]["statements"] = statements + [statements[-1]]
        candidates.append(_apply)
    return candidates


def _mutate_json_bytes(payload_bytes, identifier):
    payload = json.loads(payload_bytes.decode("utf-8"))
    validator = _result_validator()
    for apply in _mutation_candidates(payload):
        candidate = copy.deepcopy(payload)
        apply(candidate)
        if candidate != payload and validator.is_valid(candidate):
            return (json.dumps(candidate, ensure_ascii=False) + "\n").encode("utf-8")
    raise FakeCoreBuildError(f"mutate対象のJSONを安全に改変できる既知の候補がありません: {identifier}")


def _mutate_text_bytes(text_bytes, identifier):
    text = text_bytes.decode("utf-8")
    for index, character in enumerate(text):
        if character.isalnum():
            mutated_character = "X" if character != "X" else "Y"
            return (text[:index] + mutated_character + text[index + 1:]).encode("utf-8")
    raise FakeCoreBuildError(f"mutate対象のtextに変更できる文字がありません: {identifier}")


def _entry_for_fixture(identifier, host_path, mutate, mutate_report):
    fixture_root = _locate_fixture_root(identifier)
    manifest = json.loads((fixture_root / "manifest.json").read_text(encoding="utf-8"))
    if "generate" in manifest["setup"]:
        return None
    invocation = manifest["invocation"]
    runner = invocation["runner"]
    if runner == "package":
        # package runnerはCore実行体を起動しない。package_check.pyが検査対象のsource tree、
        # wheel、venvを直接検査するため、応答表に載せる出力そのものが存在しない。
        return None
    expect = manifest["expect"]

    with tempfile.TemporaryDirectory(prefix=f"bitz-fakecore-gen-{identifier}-") as sandbox_text:
        sandbox = Path(sandbox_text)
        repository = setup(fixture_root, manifest, sandbox / "repo")
        cwd_path = repository if invocation["cwd"] == "." else repository / invocation["cwd"]
        tree_digest = _tree_digest(cwd_path)

    git_version = _git_version_key(invocation, host_path)
    python_minor = invocation.get("python") or default_python_minor()
    vcs_state = _vcs_state_key(manifest["setup"], git_version)

    if runner == "bitz":
        module, response_runner = "cli", "bitz"
    else:
        module, response_runner = "compat", runner
    argv = list(invocation["argv"])

    stdout_kind = expect["stdout"]
    stdout_bytes, stderr_bytes, report_bytes = b"", b"", b""
    report_operation = None

    if stdout_kind == "json":
        original_bytes = (fixture_root / expect["resultFile"]).read_bytes()
        stdout_bytes = _mutate_json_bytes(original_bytes, identifier) if identifier == mutate else original_bytes
        # reportはCoreが標準出力とは別に保存する結果JSON(結果契約8)。標準出力とは独立に改変できる
        # ようにする(mutate_reportは標準出力を変えず、report file内容だけを改変する自己試験用)。
        report_bytes = (_mutate_json_bytes(original_bytes, identifier)
                        if identifier == mutate_report else original_bytes)
    elif stdout_kind in ("text", "markdown"):
        stdout_bytes = (fixture_root / expect["textFile"]).read_bytes()
        if identifier == mutate:
            stdout_bytes = _mutate_text_bytes(stdout_bytes, identifier)
    else:  # "none"
        cli_output = json.loads((fixture_root / "cli-output.json").read_text(encoding="utf-8"))
        line_count = cli_output["stderrLineCount"]
        if identifier == mutate:
            line_count += 1
        line = f"{cli_output['stderrPrefix']}偽Coreによる拒否\n"
        stderr_bytes = (line * line_count).encode("utf-8")

    if expect["reportFileCount"] > 0:
        report_operation = argv[0] if argv else response_runner

    return {
        "id": identifier, "module": module, "runner": response_runner, "argv": argv,
        "treeDigest": tree_digest, "gitVersion": git_version, "pythonMinor": python_minor,
        "vcsState": vcs_state,
        "exitCode": expect["exitCode"], "stdoutKind": stdout_kind,
        "stdoutBase64": base64.b64encode(stdout_bytes).decode("ascii"),
        "stderrBase64": base64.b64encode(stderr_bytes).decode("ascii"),
        "reportBase64": base64.b64encode(report_bytes).decode("ascii"),
        "reportFileCount": expect["reportFileCount"], "reportOperation": report_operation,
    }


PYPROJECT_TOML = """[project]
name = "bitz"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = ["ruamel.yaml==0.19.1"]

[project.scripts]
bitz = "bitz.cli:main"

[build-system]
requires = ["uv_build>=0.4.0,<1.0.0"]
build-backend = "uv_build"
"""

ENGINE_PY = '''"""偽Coreの応答engine(生成物。ADR-052 Decision 5。fixtures/conformance/fake_core.pyが生成)。

このfileはCoreの実装ではなく、参照harnessの自己試験のためだけに存在する。埋め込まれた
_responses.jsonから、起動条件(argv・cwd配下treeのdigest・Git版・Python版)が一致する応答を
探して返す。fixtures/conformanceには依存しない(隔離venvへ導入されて単独で動く)。
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

_HERE = Path(__file__).resolve().parent
_RESPONSES = json.loads((_HERE / "_responses.json").read_text(encoding="utf-8"))
_GIT_VERSION_RE = re.compile(r"git version (\\d+\\.\\d+\\.\\d+)")


def _snapshot_tree(root):
    result = {}
    root = Path(root)
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if ".git" in relative.split("/"):
            continue
        if path.is_symlink():
            result[relative] = {"kind": "symlink", "target": os.readlink(path)}
        elif path.is_file():
            result[relative] = {"kind": "file", "executable": bool(path.stat().st_mode & 0o111),
                                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        else:
            result[relative] = {"kind": "directory"}
    return result


def _tree_digest(root):
    data = _snapshot_tree(root)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _detect_git_version():
    try:
        completed = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=10)
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    match = _GIT_VERSION_RE.search(completed.stdout)
    return match.group(1) if match else None


def _python_minor():
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _detect_vcs_state(git_version):
    """cwd配下treeのdigestだけでは、同じ内容のtreeでGit初期化・commit有無だけが違う起動を
    区別できないため、`git rev-parse`相当の観測を独立したkey要素にする
    (`fake_core.py`の`_vcs_state_key`と同じ規則)。"""
    if git_version is None:
        return "no-repo"
    try:
        inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                                 capture_output=True, text=True, timeout=10)
    except OSError:
        return "no-repo"
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return "no-repo"
    try:
        head = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"],
                               capture_output=True, text=True, timeout=10)
    except OSError:
        return "unborn"
    return "committed" if head.returncode == 0 else "unborn"


def _find_response(module, runner, argv):
    key_tree = _tree_digest(Path.cwd())
    key_git = _detect_git_version()
    key_python = _python_minor()
    key_vcs = _detect_vcs_state(key_git)
    for entry in _RESPONSES:
        if (entry["module"] == module and entry["runner"] == runner and entry["argv"] == list(argv)
                and entry["treeDigest"] == key_tree and entry["gitVersion"] == key_git
                and entry["pythonMinor"] == key_python and entry["vcsState"] == key_vcs):
            return entry
    return None


def _write_report_if_needed(entry):
    count = entry.get("reportFileCount", 0)
    if not count:
        return
    reports_dir = Path(".spec/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    operation = entry["reportOperation"]
    payload = base64.b64decode(entry["reportBase64"])
    suffix = 0
    while True:
        name = f"{timestamp}-{operation}.json" if suffix == 0 else f"{timestamp}-{operation}-{suffix}.json"
        candidate = reports_dir / name
        try:
            descriptor = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            suffix += 1
            continue
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
        return


def dispatch(module, runner, argv):
    entry = _find_response(module, runner, argv)
    if entry is None:
        sys.stderr.write("fake-core: 応答表にない起動です(argv/tree/git/pythonの組合せが未登録)\\n")
        return 99
    _write_report_if_needed(entry)
    if entry["stdoutKind"] == "none":
        sys.stderr.buffer.write(base64.b64decode(entry["stderrBase64"]))
    else:
        sys.stdout.buffer.write(base64.b64decode(entry["stdoutBase64"]))
    return entry["exitCode"]
'''

CLI_PY = '''"""偽Coreの`bitz` console script(生成物。ADR-052 Decision 5)。"""
import sys

from bitz._engine import dispatch


def main():
    return dispatch("cli", "bitz", sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
'''

COMPAT_PY = '''"""偽Coreの`bitz.compat`(生成物。ADR-052 Decision 5)。`python -m bitz.compat <runner> <argv...>`用。"""
import sys

from bitz._engine import dispatch


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv:
        sys.stderr.write("bitz.compat: runnerの指定が必要です\\n")
        return 99
    runner, rest = argv[0], argv[1:]
    return dispatch("compat", runner, rest)


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _write_source_tree(destination, responses):
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise FakeCoreBuildError(f"destinationが空ではありません: {destination}")
    (destination / "pyproject.toml").write_text(PYPROJECT_TOML, encoding="utf-8")
    src = destination / "src" / "bitz"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "_engine.py").write_text(ENGINE_PY, encoding="utf-8")
    (src / "cli.py").write_text(CLI_PY, encoding="utf-8")
    (src / "compat.py").write_text(COMPAT_PY, encoding="utf-8")
    (src / "_responses.json").write_text(
        json.dumps(responses, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    result = subprocess.run(["uv", "lock"], cwd=destination, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise FakeCoreBuildError(f"偽Coreのuv lockに失敗しました: {result.stderr.strip()[:2000]}")


def build_fake_core(destination, fixture_ids, mutate=None, mutate_report=None):
    """偽Coreのsource treeを`destination`(空にできるdir)へ生成し、`destination`をPathで返す。

    `fixture_ids`はsingle/またはmulti/のfixture ID列。`mutate`を指定すると、そのfixtureの
    標準出力(json/text/none)だけを1箇所改変する(仕様に適合したまま値を変え、`error`ではなく
    `failed`になることを確かめる自己試験に使う)。`mutate_report`を指定すると、そのfixtureの
    標準出力は正しいまま、`.spec/reports/`へ保存するreport fileの内容だけを改変する
    (report内容の検証(適合fixture仕様2、結果契約8)を自己試験するためのもの。`reportFileCount`が
    0のfixtureを指定しても効果がない)。
    """
    host_path = os.environ.get("PATH", "")
    responses = []
    seen = {}
    for identifier in fixture_ids:
        entry = _entry_for_fixture(identifier, host_path, mutate, mutate_report)
        if entry is None:
            continue
        key = (entry["module"], entry["runner"], tuple(entry["argv"]), entry["treeDigest"],
               entry["gitVersion"], entry["pythonMinor"], entry["vcsState"])
        comparable = {name: value for name, value in entry.items() if name != "id"}
        if key in seen and seen[key][0] != comparable:
            raise FakeCoreBuildError(
                f"同じ起動条件で異なる期待出力を持つfixtureがあります: {seen[key][1]} と {identifier}")
        seen[key] = (comparable, identifier)
        responses.append(entry)
    _write_source_tree(Path(destination), responses)
    return Path(destination)
