"""参照適合harnessの実行部(ADR-046, ADR-052)。

検査対象CoreをCLI引数で受け取り、fixtureごとに準備手順、起動、比較、副作用検査を行う。
`bitz`をインポートしない(ADR-049 Decision 6)。Coreに固有の手順(ビルド、構文解析器のアダプター)は持たず、
参照実装が要る箇所(パッケージのランナー)だけをここに置く。
"""
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_reference, multi_generator, package_check
from .harness import git, safe_path, setup, snapshot, tree_digest_bytes
from .initial_fixtures import compare_state, observe
from .schemas import schema_path
from .timing import timed_call

HERE = Path(__file__).resolve().parent
FIXTURES_ROOT = HERE.parent
DEFAULT_TIMEOUT = 120
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DURATION_TOKEN = re.compile(r"\([0-9]+ms\)")


class FixtureError(Exception):
    """fixtureやharnessの側で比較を成立させられないことを表す。`passed`へ数えない。"""


class CoreEnvironmentError(FixtureError):
    """検査対象の導入に失敗したことを表す。該当するfixtureを`error`にする。"""


def default_python_minor():
    """基準環境のCPythonのマイナーバージョンを、性能基準環境定義から読み取る(適合fixture仕様 3.5)。"""
    reference = FIXTURES_ROOT / "performance/environments/core-1-reference.json"
    data = json.loads(reference.read_text(encoding="utf-8"))
    major, minor = data["requiredTools"]["pythonVersion"].split(".")[:2]
    return f"{major}.{minor}"


def venv_python(venv_dir):
    posix = Path(venv_dir) / "bin" / "python"
    if posix.exists():
        return posix
    return Path(venv_dir) / "Scripts" / "python.exe"


def venv_bin(venv_dir, name):
    posix = Path(venv_dir) / "bin" / name
    if posix.exists():
        return posix
    return Path(venv_dir) / "Scripts" / f"{name}.exe"


def _run(argv, **kwargs):
    return subprocess.run(argv, capture_output=True, text=True, timeout=kwargs.pop("timeout", 300), **kwargs)


class CoreEnvironment:
    """`--core`が指すソースのディレクトリまたはwheelを、CPythonのマイナーバージョンごとの隔離した仮想環境へ導入する。"""

    def __init__(self, core_argument, work_root):
        self.core_path = Path(core_argument).resolve()
        self.work_root = Path(work_root)
        self.is_wheel = self.core_path.is_file() and self.core_path.suffix == ".whl"
        if not self.is_wheel and not self.core_path.is_dir():
            raise CoreEnvironmentError(f"`--core`はソースのディレクトリまたは`.whl`ファイルである必要があります: {self.core_path}")
        self._prepared = None
        self._venvs = {}

    @property
    def source_dir(self):
        return None if self.is_wheel else self.core_path

    def _prepare(self):
        """wheelとロック済みの依存(requirements.txt)を一度だけ用意する。"""
        if self._prepared is not None:
            return self._prepared
        if self.is_wheel:
            self._verify_exact_pins(self.core_path)
            self._prepared = (self.core_path, None)
            return self._prepared
        build_dir = self.work_root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        result = _run(["uv", "build", "--wheel", "--out-dir", str(build_dir), str(self.core_path)], timeout=600)
        if result.returncode != 0:
            raise CoreEnvironmentError(f"Coreのwheelのビルドに失敗しました: {result.stderr.strip()[:2000]}")
        wheels = sorted(build_dir.glob("*.whl"))
        if len(wheels) != 1:
            raise CoreEnvironmentError(f"ビルドの成果物のwheelを1件に特定できません: {[w.name for w in wheels]}")
        requirements = self.work_root / "requirements.txt"
        result = _run(["uv", "export", "--project", str(self.core_path), "--frozen", "--no-dev",
                       "--no-emit-project", "--no-hashes", "-o", str(requirements)], timeout=300)
        if result.returncode != 0:
            raise CoreEnvironmentError(f"ロック済みの依存の書き出しに失敗しました: {result.stderr.strip()[:2000]}")
        self._prepared = (wheels[0], requirements)
        return self._prepared

    @staticmethod
    def _verify_exact_pins(wheel_path):
        import email
        import zipfile
        with zipfile.ZipFile(wheel_path) as archive:
            names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            if len(names) != 1:
                raise CoreEnvironmentError("wheelの`METADATA`を1件に特定できません")
            metadata = email.message_from_string(archive.read(names[0]).decode("utf-8"))
        for requirement in metadata.get_all("Requires-Dist", []):
            clause = requirement.split(";", 1)[0].strip()
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\s*(?:\[[^\]]*\])?\s*==\s*[^\s,]+", clause):
                raise CoreEnvironmentError(f"wheelのみの入力では厳密なバージョン固定でない依存を導入できません: {requirement!r}")

    def wheel_path(self):
        wheel, _requirements = self._prepare()
        return wheel

    def venv(self, minor):
        if minor not in self._venvs:
            self._venvs[minor] = self._build_venv(minor)
        return self._venvs[minor]

    def _build_venv(self, minor):
        wheel, requirements = self._prepare()
        venv_dir = self.work_root / f"env-{minor}"
        result = _run(["uv", "venv", "--python", minor, "--no-python-downloads", str(venv_dir)], timeout=120)
        if result.returncode != 0:
            raise CoreEnvironmentError(f"CPython {minor}の仮想環境を作成できません: {result.stderr.strip()[:2000]}")
        python = venv_python(venv_dir)
        if requirements is None:
            install = ["uv", "pip", "install", "--python", str(python), str(wheel)]
        else:
            install = ["uv", "pip", "install", "--python", str(python), "--no-deps", "-r", str(requirements), str(wheel)]
        result = _run(install, timeout=600)
        if result.returncode != 0:
            raise CoreEnvironmentError(f"検査対象の導入に失敗しました: {result.stderr.strip()[:2000]}")
        return venv_dir


def host_tool_versions():
    """報告用の実行環境情報(harness自身が動くホストの`python`/`uv`/`git`のバージョン)。"""
    python_version = sys.version.split()[0]
    uv_version = None
    git_version = None
    try:
        uv_version = _run(["uv", "--version"], timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        git_version = _run(["git", "--version"], timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return {"python": python_version, "uv": uv_version, "git": git_version}


def build_git_shim(shim_dir, git_version):
    real_git = shutil.which("git")
    if real_git is None:
        raise FixtureError("実Gitが見つからないため`gitVersion`のシムを作成できません")
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim = shim_dir / "git"
    shim.write_text(
        "#!/bin/sh\n"
        'if [ "$#" -eq 1 ] && [ "$1" = "--version" ]; then\n'
        f'  printf \'git version {git_version}\\n\'\n'
        "  exit 0\n"
        "fi\n"
        f'exec "{real_git}" "$@"\n',
        encoding="utf-8")
    mode = shim.stat().st_mode
    shim.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return shim_dir


def _load_manifest(fixture_root, validators):
    manifest_path = fixture_root / "manifest.json"
    if not manifest_path.is_file():
        raise FixtureError("`manifest.json`がありません")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    try:
        validators["manifest"].validate(manifest)
    except ValidationError as error:
        raise FixtureError(f"マニフェストがスキーマに適合しません: {error.message}") from error
    return manifest


def _referenced_files(fixture_root, manifest):
    """3.3の実成果物との対応: マニフェストが参照する全ファイルの存在を確認する。"""
    expect = manifest["expect"]
    paths = []
    if "resultFile" in expect:
        paths.append(expect["resultFile"])
    if "textFile" in expect:
        paths.append(expect["textFile"])
    if expect.get("stdout") == "none":
        paths.append("cli-output.json")
    for name in paths:
        if not (fixture_root / name).is_file():
            raise FixtureError(f"マニフェストが参照するファイルがありません: {name}")
    side_effects_path = fixture_root / "side-effects.json"
    if not side_effects_path.is_file():
        raise FixtureError("`side-effects.json`がありません")


def _validate_expected_result(fixture_root, manifest, validators):
    expect = manifest["expect"]
    if "resultFile" not in expect:
        return None
    payload = json.loads((fixture_root / expect["resultFile"]).read_text(encoding="utf-8"))
    if manifest["invocation"]["runner"] == "bitz":
        try:
            validators["result"].validate(payload)
        except ValidationError as error:
            raise FixtureError(f"期待結果が`result.schema.json`に適合しません: {error.message}") from error
    else:
        if set(payload) != {"outcome"} or payload["outcome"] not in {"accepted", "rejected", "passed"}:
            raise FixtureError("期待結果が`outcome`の外形と一致しません")
    return payload


def _normalize(node, warnings, top, zero_duration=False):
    if isinstance(node, dict):
        if zero_duration:
            # 生成fixtureの`resultDigest`は、`durationMs`をリテラル0で固定した正規JSONの
            # SHA-256としてレビュー済み(`multi_limit_fixtures.canonical_digest`)である。実結果側も
            # 除外(`pop`)ではなく0へ置換し、同じ正規JSONを再現する(比較範囲は広げない)。
            if "durationMs" in node:
                node["durationMs"] = 0
        else:
            node.pop("durationMs", None)
        # `revision`と`core`は公開結果スキーマ上、文書のルート(最上位)にしか出現しない
        # (`result.schema.json`の各操作の定義。fixtureのcorpus全件で実測済み)。
        # 入れ子の位置に同名のキーが現れても対象にしない。
        if top:
            revision = node.get("revision")
            if isinstance(revision, dict):
                for key in ("base", "commit"):
                    value = revision.get(key)
                    if isinstance(value, str):
                        if COMMIT_PATTERN.fullmatch(value):
                            revision[key] = "0" * 40
                        else:
                            warnings.append(f"`revision.{key}`が40桁の小文字16進ではありません: {value!r}")
            core = node.get("core")
            if isinstance(core, dict) and isinstance(core.get("version"), str):
                parts = core["version"].split(".")
                if len(parts) >= 2:
                    core["version"] = ".".join(parts[:2])
        for value in node.values():
            _normalize(value, warnings, top=False, zero_duration=zero_duration)
    elif isinstance(node, list):
        for item in node:
            _normalize(item, warnings, top=False, zero_duration=zero_duration)
    return node


def normalize_result(value, zero_duration=False):
    """共通の正規化器(適合fixture仕様 4)。`durationMs`の除外、コミット形式の検査、`core.version`のパッチバージョンの除外。

    `durationMs`は名前が一致すれば任意の深さで除外する(仕様が明示する最上位・`workspaces[]`・
    `commands[]`の3位置に加え、fixtureのcorpusの実測で他の位置に出現しないことを確認済みの超集合)。
    `revision`と`core`は文書のルートだけに出現するため、ルートでだけ処理する。
    実行環境に依存するプロセス出力の抜粋の正規化はTODO: 未実装(仕様4の最後の除外項目)。
    レポートのファイル名の生成時刻と連番の正規化は、公開結果のJSONに現れないため未使用(レポートの本文の比較を行わないため)。

    `zero_duration`は生成fixtureの`resultDigest`の比較だけに使う(既定は`False`で従来どおり`pop`する)。
    """
    import copy
    warnings = []
    normalized = _normalize(copy.deepcopy(value), warnings, top=True, zero_duration=zero_duration)
    return normalized, warnings


def normalize_text(text):
    return DURATION_TOKEN.sub("(<duration>ms)", text)


def diff_json(expected, actual, path="$"):
    """短い差分列(JSON pointer風のパス、期待値、実際の値)を返す。"""
    diffs = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                diffs.append((f"{path}/{key}", "<absent>", _short(actual[key])))
            elif key not in actual:
                diffs.append((f"{path}/{key}", _short(expected[key]), "<absent>"))
            else:
                diffs.extend(diff_json(expected[key], actual[key], f"{path}/{key}"))
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            diffs.append((path, f"length={len(expected)}", f"length={len(actual)}"))
        else:
            for index, (e_item, a_item) in enumerate(zip(expected, actual)):
                diffs.extend(diff_json(e_item, a_item, f"{path}/{index}"))
    elif expected != actual:
        diffs.append((path, _short(expected), _short(actual)))
    return diffs


def _short(value):
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return text if len(text) <= 120 else text[:117] + "..."


def _format_diffs(diffs, limit=20):
    formatted = [f"{path}: 期待={expected} 実際={actual}" for path, expected, actual in diffs[:limit]]
    if len(diffs) > limit:
        formatted.append(f"...他{len(diffs) - limit}件の差分")
    return formatted


CLI_CONTROL_FORBIDDEN = re.compile(
    "[\u0000-\u0009\u000b-\u001f\u007f\u0080-\u009f]")


def _check_cli_output(fixture_root, manifest, exit_code, stdout_bytes, stderr_bytes):
    """終了コード4の出力規則(結果・診断・終了コード §3)を検査する。"""
    differences = []
    cli_output = json.loads((fixture_root / "cli-output.json").read_text(encoding="utf-8"))
    expect_exit = manifest["expect"]["exitCode"]
    if exit_code != expect_exit or exit_code != cli_output["exitCode"]:
        differences.append(f"`exitCode`: 期待={expect_exit} 実際={exit_code}")
    if stdout_bytes != cli_output["stdout"].encode("utf-8"):
        differences.append("標準出力: 空でなければならないが出力がありました")
    try:
        text = stderr_bytes.decode("utf-8")
    except UnicodeDecodeError:
        differences.append("標準エラー出力: UTF-8として解読できません")
        return differences
    if not text.endswith("\n"):
        differences.append("標準エラー出力: 末尾がLFで終わっていません")
        return differences
    body = text[:-1]
    lines = body.split("\n") if body else []
    if len(lines) != cli_output["stderrLineCount"]:
        differences.append(f"`stderrLineCount`: 期待={cli_output['stderrLineCount']} 実際={len(lines)}")
    prefix = cli_output["stderrPrefix"]
    for index, line in enumerate(lines):
        if not line.startswith(prefix):
            differences.append(f"標準エラー出力の行{index}が`stderrPrefix`で始まりません: {line!r}")
        elif cli_output["stderrReasonRequired"] and not line[len(prefix):].strip():
            differences.append(f"標準エラー出力の行{index}に空でない理由がありません")
    if not cli_output["stderrTerminalControls"]:
        # 各行末のLFは行区切りとして許可し、それ以外のC0・DEL・C1制御文字だけを禁止する。
        without_separators = body.replace("\n", "")
        if CLI_CONTROL_FORBIDDEN.search(without_separators):
            differences.append("標準エラー出力に端末の制御文字が含まれています")
    return differences


def _build_argv(manifest, venv_dir):
    invocation = manifest["invocation"]
    runner = invocation["runner"]
    if runner == "bitz":
        return [str(venv_bin(venv_dir, "bitz")), *invocation["argv"]]
    if runner in ("consumer", "migration"):
        return [str(venv_python(venv_dir)), "-m", "bitz.compat", runner, *invocation["argv"]]
    raise FixtureError(f"未知のランナーです: {runner}")


def _observe_state(repository, external, git_enabled):
    if git_enabled:
        return observe(repository, external)
    return {"repository": snapshot(repository), "git": None,
            **{name: snapshot(path) for name, path in external.items()}}


def _new_report_files(before_state, after_state):
    before = {k for k, v in before_state["repository"].items()
              if k.startswith(".spec/reports/") and v.get("kind") == "file"}
    after = {k for k, v in after_state["repository"].items()
             if k.startswith(".spec/reports/") and v.get("kind") == "file"}
    return sorted(after - before)


def _filter_git_status_for_new_reports(status_text, allowed_new):
    """`git status --porcelain`の出力から、新規に許可したレポートファイルの`??`行だけを取り除く。

    レポートのファイル名は生成時刻と連番を含み、fixtureの`after`は執筆時点で存在しなかった
    ファイルの行を書けない(そもそも名前が決まらない)。そのため`--report`ありのfixtureの
    期待する`git status`は、新規のレポートファイルを除いた状態を表す(適合fixture仕様5の
    明示したレポートの記述と整合させるための、レポートのファイル名だけを対象にした限定的な除外)。
    """
    if not status_text:
        return status_text
    kept = []
    for line in status_text.splitlines(keepends=True):
        content = line.rstrip("\n")
        if content.startswith("??") and content[3:] in allowed_new:
            continue
        kept.append(line)
    return "".join(kept)


def _state_diff_allowing_new_reports(expected_state, actual_state, allowed_new):
    diffs = []
    expected_repo, actual_repo = expected_state["repository"], actual_state["repository"]
    for path in sorted(set(expected_repo) | set(actual_repo)):
        if path in allowed_new and path not in expected_repo:
            continue
        if expected_repo.get(path) != actual_repo.get(path):
            diffs.append(f"repository:{path}")
    expected_git, actual_git = expected_state.get("git"), actual_state.get("git")
    if isinstance(expected_git, dict) and isinstance(actual_git, dict):
        filtered_status = _filter_git_status_for_new_reports(actual_git.get("status", ""), allowed_new)
        if expected_git.get("status") != filtered_status or expected_git.get("index") != actual_git.get("index"):
            diffs.append("git")
    elif expected_git != actual_git:
        diffs.append("git")
    for name in ("home", "cache", "temporary"):
        if expected_state.get(name) != actual_state.get(name):
            diffs.append(name)
    return diffs


def _generate_and_verify(fixture_root, generate_spec):
    """生成fixtureの入力の木構造をデータセットのマニフェストから決定論的に作り、`treeDigest`を照合する(仕様3.4・3.5)。

    生成器(`multi_generator`)はfixtureのharness側の参照実装であり(仕様3.4)、ここでの再利用は
    二重実装を避けるためのものであってCoreの実装ではない。ハッシュ値が一致しなければ、そのfixtureを`error`とする。
    """
    dataset_path = fixture_root / generate_spec["dataset"]
    if not dataset_path.is_file():
        raise FixtureError(f"データセットのマニフェストがありません: {generate_spec['dataset']}")
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    try:
        entries = multi_generator.generate(dataset)
    except ValueError as error:
        raise FixtureError(f"生成入力がデータセットのマニフェストと一致しません: {error}") from error
    computed = tree_digest_bytes(entries)
    if computed != generate_spec["treeDigest"]:
        raise FixtureError(
            f"`treeDigest`がマニフェストと一致しません: 期待={generate_spec['treeDigest']} 実際={computed}")
    return entries


def _state_digest(state):
    """副作用の`stateDigest`(仕様5)。観測した状態のRFC 8785の正規JSONのSHA-256。"""
    return digest_reference.digest(digest_reference.canonical_bytes(state))


def _compare_side_effects_digest(side_effects, expect, after_state, new_reports):
    differences = []
    if len(new_reports) != expect["reportFileCount"]:
        differences.append(
            f"`reportFileCount`: 期待={expect['reportFileCount']} 実際={len(new_reports)}（{new_reports}）")
    after_digest = _state_digest(after_state)
    if after_digest != side_effects["stateDigest"]:
        differences.append(
            f"副作用: 実行後の状態（`stateDigest`）が期待と一致しません: "
            f"期待={side_effects['stateDigest']} 実際={after_digest}")
    return differences


def run_fixture(fixture_root, fixture_id, core_environment, validators, base_tmp, *, timings=None):
    """1つのfixtureを実行して{"id", "result", "differences"}を返す。例外を送出しない。"""
    differences = []
    try:
        manifest = _load_manifest(fixture_root, validators)
        _referenced_files(fixture_root, manifest)
        expected_result = _validate_expected_result(fixture_root, manifest, validators)
        side_effects = json.loads((fixture_root / "side-effects.json").read_text(encoding="utf-8"))
        try:
            validators["side-effects"].validate(side_effects)
        except ValidationError as error:
            raise FixtureError(f"`side-effects.json`がスキーマに適合しません: {error.message}") from error
        generated_entries = None
        if "generate" in manifest["setup"]:
            generated_entries = timed_call(timings, "generate", _generate_and_verify, fixture_root, manifest["setup"]["generate"])
        if "stateDigest" in side_effects and side_effects["policy"] != "read-only":
            # `stateDigest`は実行の前後の観測値が同じ1つのハッシュ値になることを要求する(仕様3.4・5)。
            # 方針`explicit-report`と`stateDigest`の組合せは、レポートのファイル名に生成時刻・連番を含み、実行後の状態を単一のハッシュ値で
            # 事前に固定できないため未対応とする(方針が`read-only`の`stateDigest`だけに対応する)。
            raise FixtureError("`read-only`以外の`policy`を持つ`stateDigest`形式の副作用の期待値は未対応です")

        with tempfile.TemporaryDirectory(prefix=f"bitz-run-{fixture_id}-", dir=base_tmp) as sandbox_text:
            sandbox = Path(sandbox_text)
            repository = timed_call(timings, "setup", setup, fixture_root, manifest, sandbox / "repo", generated=generated_entries)
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            git_enabled = manifest["setup"]["git"]
            before_state = timed_call(timings, "snapshotBefore", _observe_state, repository, external, git_enabled)
            if "stateDigest" in side_effects:
                before_digest = timed_call(timings, "stateDigestBefore", _state_digest, before_state)
                if before_digest != side_effects["stateDigest"]:
                    raise FixtureError(
                        f"準備手順の後の状態（`stateDigest`）が期待前提と一致しません: "
                        f"期待={side_effects['stateDigest']} 実際={before_digest}")
            else:
                setup_diff = compare_state(side_effects["before"], before_state)
                if setup_diff:
                    raise FixtureError(f"準備手順の後の状態が期待前提と一致しません: {setup_diff}")

            invocation = manifest["invocation"]
            minor = invocation.get("python") or default_python_minor()
            venv_dir = timed_call(timings, "environment", core_environment.venv, minor)

            env = {"PATH": os.environ.get("PATH", ""), "HOME": str(external["home"]),
                   "XDG_CACHE_HOME": str(external["cache"]), "TMPDIR": str(external["temporary"])}
            if "gitVersion" in invocation:
                shim_dir = build_git_shim(sandbox / "git-shim", invocation["gitVersion"])
                env["PATH"] = str(shim_dir) + os.pathsep + env["PATH"]
            env.update(invocation.get("env", {}))
            cwd_path = safe_path(repository, invocation["cwd"], allow_dot=True)

            if invocation["runner"] == "package":
                try:
                    outcome, reasons = timed_call(timings, "package", package_check.check,
                        invocation["argv"][0], core_environment.source_dir, core_environment.wheel_path(), venv_dir)
                except package_check.PackageCheckError as error:
                    raise FixtureError(f"`package`の検査を実行できません: {error}") from error
                exit_code = 0 if outcome in ("accepted", "passed") else 1
                stdout_bytes = (json.dumps({"outcome": outcome}) + "\n").encode("utf-8")
                stderr_bytes = b""
                differences.extend(f"`package`: {reason}" for reason in reasons)
            else:
                argv = _build_argv(manifest, venv_dir)
                try:
                    completed = timed_call(timings, "process", subprocess.run, argv, cwd=cwd_path, env=env, stdin=subprocess.DEVNULL,
                                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                timeout=DEFAULT_TIMEOUT)
                except subprocess.TimeoutExpired as error:
                    raise FixtureError(f"`invocation`がタイムアウトの上限（{DEFAULT_TIMEOUT}秒）を超過しました") from error
                except OSError as error:
                    raise FixtureError(f"`invocation`を起動できません: {error}") from error
                exit_code, stdout_bytes, stderr_bytes = completed.returncode, completed.stdout, completed.stderr

            expect = manifest["expect"]
            if expect["stdout"] == "none":
                differences.extend(_check_cli_output(fixture_root, manifest, exit_code, stdout_bytes, stderr_bytes))
            elif expect["stdout"] == "json":
                differences.extend(timed_call(timings, "compare", _compare_json, manifest, expect, expected_result, exit_code, stdout_bytes, validators))
            else:
                differences.extend(_compare_text(fixture_root, expect, exit_code, stdout_bytes))

            after_state = timed_call(timings, "snapshotAfter", _observe_state, repository, external, git_enabled)
            new_reports = _new_report_files(before_state, after_state)
            if "stateDigest" in side_effects:
                differences.extend(timed_call(timings, "compareSideEffects", _compare_side_effects_digest, side_effects, expect, after_state, new_reports))
            else:
                differences.extend(timed_call(timings, "compareSideEffects", _compare_side_effects, side_effects, expect, before_state, after_state, new_reports))
            if new_reports and manifest["invocation"]["runner"] == "bitz" and expect["stdout"] == "json":
                differences.extend(_validate_report_contents(repository, new_reports, expected_result, validators))

        status = "passed" if not differences else "failed"
        return {"id": fixture_id, "result": status, "differences": differences}
    except FixtureError as error:
        return {"id": fixture_id, "result": "error", "differences": [str(error)]}
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        return {"id": fixture_id, "result": "error", "differences": [f"harnessの例外: {error}"]}


def _compare_json(manifest, expect, expected_result, exit_code, stdout_bytes, validators):
    differences = []
    if exit_code != expect["exitCode"]:
        differences.append(f"`exitCode`: 期待={expect['exitCode']} 実際={exit_code}")
    try:
        actual_result = json.loads(stdout_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FixtureError(f"標準出力をJSONとして解析できません: {error}") from error
    if manifest["invocation"]["runner"] == "bitz":
        try:
            validators["result"].validate(actual_result)
        except ValidationError as error:
            raise FixtureError(f"実結果が`result.schema.json`に適合しません: {error.message}") from error
        if expect.get("status") is not None and actual_result.get("status") != expect["status"]:
            differences.append(f"`status`: 期待={expect['status']} 実際={actual_result.get('status')}")
        if "resultDigest" in expect:
            # 生成fixture(仕様3.4・3.5)。期待結果のファイルを持たないため、実結果側を`durationMs`=0固定の
            # 同じ正規化器で正規JSON化し、レビュー済みのハッシュ値と文字列で比較する(緩和ではなく、
            # `multi_limit_fixtures.canonical_digest`が計算した期待のハッシュ値の再現)。
            normalized_actual, warnings_a = normalize_result(actual_result, zero_duration=True)
            differences.extend(f"正規化器: {message}" for message in warnings_a)
            actual_digest = digest_reference.digest(digest_reference.canonical_bytes(normalized_actual))
            if actual_digest != expect["resultDigest"]:
                differences.append(f"`resultDigest`: 期待={expect['resultDigest']} 実際={actual_digest}")
        else:
            normalized_actual, warnings_a = normalize_result(actual_result)
            normalized_expected, warnings_e = normalize_result(expected_result)
            differences.extend(f"正規化器: {message}" for message in (*warnings_a, *warnings_e))
            differences.extend(_format_diffs(diff_json(normalized_expected, normalized_actual)))
    else:
        if set(actual_result) != {"outcome"}:
            raise FixtureError(f"`consumer`／`migration`／`package`の標準出力は`outcome`だけを持つ必要があります: {actual_result!r}")
        outcome = actual_result["outcome"]
        if outcome not in {"accepted", "rejected", "passed"}:
            raise FixtureError(f"未知の`outcome`です: {outcome!r}")
        expected_exit = 0 if outcome in ("accepted", "passed") else 1
        if exit_code != expected_exit:
            raise FixtureError(f"終了コードが`outcome`と整合しません: outcome={outcome} exitCode={exit_code}")
        if outcome != expect["outcome"]:
            differences.append(f"`outcome`: 期待={expect['outcome']} 実際={outcome}")
        if expected_result is not None and actual_result != expected_result:
            differences.append(f"`resultFile`と標準出力が一致しません: {expected_result!r} != {actual_result!r}")
    return differences


def _compare_text(fixture_root, expect, exit_code, stdout_bytes):
    differences = []
    if exit_code != expect["exitCode"]:
        differences.append(f"`exitCode`: 期待={expect['exitCode']} 実際={exit_code}")
    try:
        actual_text = stdout_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FixtureError(f"標準出力をUTF-8として解読できません: {error}") from error
    expected_text = (fixture_root / expect["textFile"]).read_bytes().decode("utf-8")
    if normalize_text(actual_text) != normalize_text(expected_text):
        differences.append("`textFile`と標準出力（所要時間のトークンを正規化した後）が一致しません")
    return differences


def _validate_report_contents(repository, new_reports, expected_result, validators):
    """新規レポートの内容を検査する(適合fixture仕様2、結果・診断・終了コード 8)。

    レポートは結果JSONそのものであるため、期待結果と同じスキーマで、正規化器を適用する前に検証し、適用した後に
    完全な構造として比較する。スキーマに不適合ならfixtureの比較自体を`error`にする(仕様2)。差分は`failed`として報告する。
    """
    differences = []
    for relative_path in new_reports:
        report_path = repository / relative_path
        try:
            text = report_path.read_text(encoding="utf-8")
        except OSError as error:
            raise FixtureError(f"レポート（{relative_path}）を読み取れません: {error}") from error
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise FixtureError(f"レポート（{relative_path}）をJSONとして解析できません: {error}") from error
        try:
            validators["result"].validate(payload)
        except ValidationError as error:
            raise FixtureError(f"レポート（{relative_path}）が`result.schema.json`に適合しません: {error.message}") from error
        normalized_report, warnings_report = normalize_result(payload)
        normalized_expected, warnings_expected = normalize_result(expected_result)
        differences.extend(f"レポート（{relative_path}）の正規化器: {message}"
                            for message in (*warnings_report, *warnings_expected))
        differences.extend(f"レポート（{relative_path}）: " + message
                            for message in _format_diffs(diff_json(normalized_expected, normalized_report)))
    return differences


def _compare_side_effects(side_effects, expect, before_state, after_state, new_reports):
    differences = []
    if len(new_reports) != expect["reportFileCount"]:
        differences.append(
            f"`reportFileCount`: 期待={expect['reportFileCount']} 実際={len(new_reports)}（{new_reports}）")
    pattern = side_effects.get("report", {}).get("namePattern")
    if pattern:
        unmatched = [p for p in new_reports if not re.search(pattern, Path(p).name)]
        if unmatched:
            differences.append(f"レポートのファイル名が`namePattern`に一致しません: {unmatched}")
    allowed_new = set(new_reports)
    state_diff = _state_diff_allowing_new_reports(side_effects["after"], after_state, allowed_new)
    if state_diff:
        differences.append(f"副作用: 実行後の状態が期待と一致しません: {state_diff}")
    return differences
