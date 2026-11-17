"""`--help`と`--version`の起動を固定するレビュー済みの入力と期待値（Coreの公開操作は実行しない）。

[ADR-075](../../docs/02.設計書/10_決定記録/ADR-075_CLIへ--helpと--versionを加える.md)と
[Core実行環境・CLI基盤契約 §5.1](../../docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md#51---helpと--version)を根拠とする。
CLIの引数の境界の群（`SINGLE-127-*`）の続きとして、`SINGLE-127-20`〜`46`の27件を置く。

| fixture | 引数列 | 入力 | 期待 |
|---|---|---|---|
| `SINGLE-127-20` | `--help` | ワークスペース | 0。標準出力は空でなく改行で終わるUTF-8、標準エラー出力は空 |
| `SINGLE-127-21`、`22` | `--help --no-such-option`、`--help --version` | 同上 | 0。最初の要素が`--help`なら後に続く要素を見ない |
| `SINGLE-127-23`〜`26` | `check`、`context`、`verify`、`doctor`の`--help` | 同上 | 0 |
| `SINGLE-127-27`〜`31` | 操作の`--help`と、未知のオプション、値の不足、値の位置の`--help`、重複、空文字列の位置引数 | 同上 | 0。`--help`がほかの引数の検査より優先する |
| `SINGLE-127-32` | `doctor --help --help` | 同上 | 0。`--help`の反復を重複として扱わない |
| `SINGLE-127-33` | `foo --help` | 同上 | 4。未知の操作 |
| `SINGLE-127-34` | `--version` | 同上 | 0。標準出力はちょうど`bitz <core.version>`とLF |
| `SINGLE-127-35`、`37` | `--version check`、`--version --version` | 同上 | 4。未知の操作 |
| `SINGLE-127-36`、`38` | `check --version`、`check --help=1` | 同上 | 4。`check`の未知のオプション |
| `SINGLE-127-39`、`40` | `--help`、`--version` | `.spec/bitz.yaml`のないGitのリポジトリ | 0 |
| `SINGLE-127-41`、`42` | `doctor --help`、`--version` | `.spec/bitz.yaml`のない、Gitのリポジトリでないディレクトリ | 0 |
| `SINGLE-127-43`、`44` | `check --help`、`--version` | YAMLの構文が不正な設定（`SINGLE-170-01`と同じ設定） | 0。設定を読まない |
| `SINGLE-127-45`、`46` | `check --format json --report --help`、`verify REQ-001 --report --help` | ワークスペース | 0。レポートを作らない |

すべての起動は読取り専用で、`reportFileCount`は0、副作用の期待値は実行前と実行後が同じ状態である（§5.1: 結果のJSONとレポートを作らない）。
`--help`の文言は契約にしないので、`cli-output.json`の`stdoutNonEmptyText`で、空でなく、UTF-8で、改行で終わることだけを比べる。
`--version`の1行は、`doctor`の結果の`core.version`と同じ値を使う（§5.1）。値は、レビュー済みの`doctor`のfixtureの期待結果から読み、
すべての`doctor`の期待結果で同じ値であることを確かめる。

終了コード4の標準エラー出力は、結果・診断・終了コード §3の`bitz: <operation-or-argv-context>: <reason>`の1行である。
操作が公開の操作の名前である場合（`SINGLE-127-36`、`38`）は、既存の未知のオプションのfixture（`SINGLE-073-*`、`SINGLE-127-11`）と同じく
接頭辞`bitz: check: `で比べる。最初の要素が公開の操作の名前でない場合（`SINGLE-127-33`、`35`、`37`）は、`<operation-or-argv-context>`に
何を書くかを仕様が定めないので、接頭辞`bitz: `と、空でない残り、1行、端末の制御文字なしだけを比べる。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_reference
from .harness import setup, snapshot
from .initial_fixtures import compare_state, observe
from .runner import FixtureError, _check_cli_output
from .schemas import schema_path
from .workspace_selection_fixtures import SYNTAX_CONFIG

HERE = Path(__file__).resolve().parent
CONFIG_PATH = ".spec/bitz.yaml"
OPERATIONS = ("check", "context", "verify", "doctor")
# `core.version`の正本の値を読む`doctor`のfixture（Step 1の`doctor`の成功）。
VERSION_SOURCE = "SINGLE-001"

# id: (引数列, 入力の種類, 期待の種類, 説明)
# 入力の種類: `workspace`（`SINGLE-042`の入力。Gitのリポジトリでコミットなし）、`outside-git`（`.spec`を除いた同じ入力のGitのリポジトリ）、
# `outside`（同じ入力で、Gitのリポジトリでないディレクトリ）、`syntax`（設定のYAMLの構文が不正）。
# 期待の種類: `help`、`version`、`unknown-operation`、`unknown-option`。
CASES = {
    "SINGLE-127-20": (["--help"], "workspace", "help",
                      "bitz --helpは操作の一覧を標準出力へ書き、終了コード0で終わる"),
    "SINGLE-127-21": (["--help", "--no-such-option"], "workspace", "help",
                      "最初の要素が--helpなら、後に続く未知のオプションを見ずに終了コード0で終わる"),
    "SINGLE-127-22": (["--help", "--version"], "workspace", "help",
                      "最初の要素が--helpなら、後に続く--versionを見ずに--helpとして終了コード0で終わる"),
    "SINGLE-127-23": (["check", "--help"], "workspace", "help",
                      "check --helpはcheckの公開構文を標準出力へ書き、終了コード0で終わる"),
    "SINGLE-127-24": (["context", "--help"], "workspace", "help",
                      "context --helpは起点がなくてもcontextの公開構文を標準出力へ書き、終了コード0で終わる"),
    "SINGLE-127-25": (["verify", "--help"], "workspace", "help",
                      "verify --helpはverifyの公開構文を標準出力へ書き、終了コード0で終わる"),
    "SINGLE-127-26": (["doctor", "--help"], "workspace", "help",
                      "doctor --helpはdoctorの公開構文を標準出力へ書き、終了コード0で終わる"),
    "SINGLE-127-27": (["check", "--no-such-option", "--help"], "workspace", "help",
                      "操作の--helpは未知のオプションより優先し、終了コード0で終わる"),
    "SINGLE-127-28": (["verify", "REQ-001", "--help", "--timeout"], "workspace", "help",
                      "操作の--helpは値の不足した--timeoutより優先し、終了コード0で終わる"),
    "SINGLE-127-29": (["context", "REQ-001", "--purpose", "--help"], "workspace", "help",
                      "オプションの値の位置にある--helpも--helpとして扱い、終了コード0で終わる"),
    "SINGLE-127-30": (["check", "--full", "--full", "--help"], "workspace", "help",
                      "操作の--helpは重複したフラグより優先し、終了コード0で終わる"),
    "SINGLE-127-31": (["check", "", "--help"], "workspace", "help",
                      "操作の--helpは空文字列の位置引数より優先し、終了コード0で終わる"),
    "SINGLE-127-32": (["doctor", "--help", "--help"], "workspace", "help",
                      "--helpが2回現れても重複として扱わず、終了コード0で終わる"),
    "SINGLE-127-33": (["foo", "--help"], "workspace", "unknown-operation",
                      "最初の要素が公開の操作の名前でなければ、--helpがあっても未知の操作として終了コード4にする"),
    "SINGLE-127-34": (["--version"], "workspace", "version",
                      "bitz --versionはbitzとCoreのバージョンの1行を標準出力へ書き、終了コード0で終わる"),
    "SINGLE-127-35": (["--version", "check"], "workspace", "unknown-operation",
                      "--versionがほかの要素を伴えば、未知の操作として終了コード4にする"),
    "SINGLE-127-36": (["check", "--version"], "workspace", "unknown-option",
                      "操作の後の--versionは、未知のオプションとして終了コード4にする"),
    "SINGLE-127-37": (["--version", "--version"], "workspace", "unknown-operation",
                      "--versionの反復は、未知の操作として終了コード4にする"),
    "SINGLE-127-38": (["check", "--help=1"], "workspace", "unknown-option",
                      "--helpと完全に一致しない--help=1は、--name=value形式の未知のオプションとして終了コード4にする"),
    "SINGLE-127-39": (["--help"], "outside-git", "help",
                      "設定のないGitのリポジトリでも、bitz --helpは何も読まず何も作らずに終了コード0で終わる"),
    "SINGLE-127-40": (["--version"], "outside-git", "version",
                      "設定のないGitのリポジトリでも、bitz --versionは何も読まず何も作らずに終了コード0で終わる"),
    "SINGLE-127-41": (["doctor", "--help"], "outside", "help",
                      "設定がなくGitのリポジトリでもないディレクトリで、doctor --helpは何も作らずに終了コード0で終わる"),
    "SINGLE-127-42": (["--version"], "outside", "version",
                      "設定がなくGitのリポジトリでもないディレクトリで、bitz --versionは何も作らずに終了コード0で終わる"),
    "SINGLE-127-43": (["check", "--help"], "syntax", "help",
                      "設定のYAMLの構文が不正でも、check --helpは設定を読まずに終了コード0で終わる"),
    "SINGLE-127-44": (["--version"], "syntax", "version",
                      "設定のYAMLの構文が不正でも、bitz --versionは設定を読まずに終了コード0で終わる"),
    "SINGLE-127-45": (["check", "--format", "json", "--report", "--help"], "workspace", "help",
                      "check --reportに--helpがあれば、操作を始めずレポートを作らずに終了コード0で終わる"),
    "SINGLE-127-46": (["verify", "REQ-001", "--report", "--help"], "workspace", "help",
                      "verify --reportに--helpがあれば、操作を始めずレポートを作らずに終了コード0で終わる"),
}
GIT_BY_INPUTS = {"workspace": True, "outside-git": True, "outside": False, "syntax": True}


def core_version():
    """`doctor`の結果の`core.version`（§5.1）。リポジトリのレビュー済みの`doctor`のfixtureの期待結果から読み、全件で1つの値であることを確かめる。

    改変したコピーを監査するときも、値の出典はリポジトリの`doctor`のfixtureとする（この群の外の期待値である）。
    """
    root = HERE
    values = set()
    for path in sorted((root / "single").glob("*/expected/doctor.json")) + sorted((root / "multi").glob("*/expected/doctor.json")):
        value = json.loads(path.read_text()).get("core", {}).get("version")
        if value is not None:
            values.add(value)
    source = json.loads((root / "single" / VERSION_SOURCE / "expected/doctor.json").read_text())["core"]["version"]
    if not isinstance(source, str) or not source or values != {source}:
        raise ValueError("`doctor`の期待結果の`core.version`が1つの値に定まりません")
    return source


def reviewed_inputs(identifier):
    corpus = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    kind = CASES[identifier][1]
    if kind in ("outside-git", "outside"):
        return {path: content for path, content in corpus.items() if not path.startswith(".spec/")}
    if kind == "syntax":
        corpus[CONFIG_PATH] = SYNTAX_CONFIG.encode()
    return corpus


def reviewed_manifest(identifier):
    argv, kind, outcome, description = CASES[identifier]
    exit_code = 4 if outcome.startswith("unknown") else 0
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": {"git": GIT_BY_INPUTS[kind], "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": list(argv), "env": {}},
        # 結果の状態を持たない: どの起動も操作を始めず、結果のJSONを作らない。
        "expect": {"exitCode": exit_code, "stdout": "none", "reportFileCount": 0},
    }


def reviewed_cli_output(identifier):
    outcome = CASES[identifier][2]
    if outcome == "help":
        return {"exitCode": 0, "stdoutNonEmptyText": True, "stderrLineCount": 0}
    if outcome == "version":
        return {"exitCode": 0, "stdout": f"bitz {core_version()}\n", "stderrLineCount": 0}
    prefix = "bitz: " if outcome == "unknown-operation" else f"bitz: {CASES[identifier][0][0]}: "
    return {"exitCode": 4, "stdout": "", "stderrPrefix": prefix, "stderrLineCount": 1,
            "stderrReasonRequired": True, "stderrTerminalControls": False}


def check_case(identifier):
    """引数列が、期待の種類を決める§5.1の条件を満たすことを確かめる（説明だけが変わった改変を拒否する）。"""
    argv, kind, outcome, _ = CASES[identifier]
    first_help = argv[0] == "--help"
    operation_help = argv[0] in OPERATIONS and "--help" in argv[1:]
    version = argv == ["--version"]
    expected = ("help" if first_help or operation_help else "version" if version
                else "unknown-option" if argv[0] in OPERATIONS else "unknown-operation")
    if outcome != expected:
        raise ValueError("期待の種類が引数列から§5.1で導いた種類と異なります")
    if kind not in GIT_BY_INPUTS:
        raise ValueError("入力の種類がレビュー済みの種類と異なります")


def check_comparison(identifier, fixture):
    """harnessの比較（`runner._check_cli_output`）を、このfixtureの期待値で陽性と陰性の対照に当てる。"""
    manifest = {"expect": {"exitCode": reviewed_manifest(identifier)["expect"]["exitCode"]}}
    cli_output = json.loads((fixture / "cli-output.json").read_text())
    outcome = CASES[identifier][2]
    if outcome == "help":
        good = [(0, b"usage: bitz\n", b""), (0, "使い方\r\n".encode(), b"")]
        bad = [(0, b"", b""), (0, b"usage: bitz", b""), (0, b"\xff\n", b""), (0, b"usage: bitz\n", b"bitz: note\n"),
               (4, b"usage: bitz\n", b"")]
    elif outcome == "version":
        line = cli_output["stdout"].encode()
        good = [(0, line, b"")]
        bad = [(0, line.rstrip(b"\n"), b""), (0, line + b"\n", b""), (0, line.replace(b" ", b"  "), b""),
               (0, line.replace(b"bitz ", b"bitz version "), b""), (0, line, b"warning\n"), (4, line, b"")]
    else:
        prefix = cli_output["stderrPrefix"].encode()
        good = [(4, b"", prefix + b"x: reason\n")]
        bad = [(0, b"", prefix + b"x: reason\n"), (4, b"usage\n", prefix + b"x: reason\n"), (4, b"", prefix + b"\n"),
               (4, b"", prefix + b"a\n" + prefix + b"b\n"), (4, b"", b"error: reason\n"), (4, b"", b"")]
    for exit_code, stdout, stderr in good:
        if _check_cli_output(fixture, manifest, exit_code, stdout, stderr):
            raise ValueError("harnessの比較が契約に合う出力を拒否しています")
    for exit_code, stdout, stderr in bad:
        if not _check_cli_output(fixture, manifest, exit_code, stdout, stderr):
            raise ValueError("harnessの比較が契約に反する出力を受理しています")


def observe_state(repository, external, git_enabled):
    if git_enabled:
        return observe(repository, external)
    # Gitのリポジトリでないディレクトリは、Gitの状態を明示的な不在として扱う（runnerと同じ）。
    return {"repository": snapshot(repository), "git": None, **{name: snapshot(path) for name, path in external.items()}}


def observed_states(fixture, manifest):
    states = []
    with tempfile.TemporaryDirectory(prefix="bitz-help-version-") as temporary:
        for run in range(2):
            sandbox = Path(temporary) / str(run)
            sandbox.mkdir()
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            if not manifest["setup"]["git"] and ((repository / ".git").exists() or (repository / ".git").is_symlink()):
                raise ValueError("Gitのリポジトリでないディレクトリのfixtureが`.git`を持っています")
            states.append(observe_state(repository, external, manifest["setup"]["git"]))
    if states[0] != states[1]:
        raise ValueError("隔離した2回の準備手順が一致しません")
    return states[0]


def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE, identifiers=None):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        fixture.mkdir(parents=True, exist_ok=False)
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "cli-output.json").write_text(_dump(reviewed_cli_output(identifier)))
        state = observed_states(fixture, manifest)
        (fixture / "side-effects.json").write_text(
            _dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["manifest"].validate(manifest)
            validators["side-effects"].validate(effects)
            check_case(identifier)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if json.loads((fixture / "cli-output.json").read_text()) != reviewed_cli_output(identifier):
                raise ValueError("CLI出力の期待値がレビュー済みの契約と異なります")
            present = {path.name for path in fixture.iterdir()}
            if present != {"repo", "manifest.json", "cli-output.json", "side-effects.json"}:
                raise ValueError("この群は`repo`、マニフェスト、`cli-output.json`、副作用の期待値だけを持ちます")
            check_comparison(identifier, fixture)
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if CASES[identifier][1] != "syntax" and CASES[identifier][1] != "workspace" and CONFIG_PATH in files:
                raise ValueError("ワークスペースの外のfixtureが設定を持っています")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            if any(name.startswith(".spec/reports") for name in effects["after"]["repository"]):
                raise ValueError("`--help`と`--version`の起動はレポートを作りません")
            state = observed_states(fixture, manifest)
            if compare_state(effects["before"], state):
                raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, FixtureError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
