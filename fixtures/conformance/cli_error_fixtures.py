"""引数不正を固定するreview済みvector（Core操作は実行しない）。

`SINGLE-073-01/02`は、reportを書かない操作に渡した`--report`を拒否する。
`SINGLE-074-01/02/03`は、排他optionの組、code pathのtarget、字句上不正なIDを拒否する。
SINGLE-127は、重複、空値、timeout、reportの構文の境界を加える。いずれも共通結果を返さず、
終了コード4、JSON本文なし、標準エラー出力1行、reportなしとなる。

SINGLE-112-02/04は、字句上妥当でcorpusに存在するADR-001を`interpret`以外の
起点に指定した場合を拒否する。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_reference
from .git_environment_fixtures import check_cli_error_output
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
# id: (操作, argvの残り, 説明)
CASES = {
    "SINGLE-073-01": ("context", ["REQ-001", "--report"],
                      "contextは--reportを未知optionとして拒否する"),
    "SINGLE-073-02": ("doctor", ["--report"],
                      "doctorは--reportを未知optionとして拒否する"),
    "SINGLE-074-01": ("check", ["REQ-001", "--full", "--format", "json"],
                      "明示対象と--fullの排他違反を拒否する"),
    "SINGLE-074-02": ("verify", ["src/auth.py", "--format", "json"],
                      "verify targetへのcode path指定を拒否する"),
    "SINGLE-074-03": ("check", ["REQ-1", "--format", "json"],
                      "構文不正な文書IDを拒否する"),
    "SINGLE-112-02": ("context", ["ADR-001", "--purpose", "implement", "--format", "json"],
                      "ADR起点のimplement contextを引数不正として拒否する"),
    "SINGLE-112-04": ("verify", ["ADR-001", "--format", "json"],
                      "ADR起点のverifyを引数不正として拒否する"),
    "SINGLE-127-01": ("check", ["--format", "json", "--format", "json"],
                      "同値の--format重複を操作開始前に拒否する"),
    "SINGLE-127-02": ("check", ["--full", "--full", "--format", "json"],
                      "--fullの重複を操作開始前に拒否する"),
    "SINGLE-127-05": ("check", ["", "--format", "json"],
                      "空stringの明示targetを引数なしcheckへ置換せず拒否する"),
    "SINGLE-127-06": ("context", ["--format", "json"],
                      "起点0件のcontextを操作開始前に拒否する"),
    "SINGLE-127-07": ("doctor", ["--workspace", "", "--format", "json"],
                      "空stringのworkspace値を操作開始前に拒否する"),
    "SINGLE-127-08": ("verify", ["REQ-001", "--timeout", "0", "--format", "json"],
                      "timeoutの下限外0を拒否する"),
    "SINGLE-127-09": ("verify", ["REQ-001", "--timeout", "3601", "--format", "json"],
                      "timeoutの上限外3601を拒否する"),
    "SINGLE-127-10": ("verify", ["REQ-001", "--timeout", "+1", "--format", "json"],
                      "timeoutの非canonical十進表記+1を拒否する"),
    "SINGLE-127-11": ("check", ["--report=out.json", "--format", "json"],
                      "reportの任意path指定形式を拒否する"),
    "SINGLE-127-14": ("doctor", ["--workspace", "missing", "--format", "json"],
                      "catalogにないworkspaceを探索後に終了コード4で拒否する"),
}


def cli_output(identifier):
    operation = CASES[identifier][0]
    return {"exitCode": 4, "stdout": "", "stderrPrefix": f"bitz: {operation}: ",
            "stderrLineCount": 1, "stderrReasonRequired": True, "stderrTerminalControls": False}


def reviewed_inputs(identifier):
    return dict(digest_reference.reviewed_inputs("SINGLE-042"))


def reviewed_manifest(identifier):
    operation, tail, description = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": {"git": True, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": [operation, *tail], "env": {}},
        # statusを持たない: 共通結果ができる前にargvを拒否する。
        "expect": {"exitCode": 4, "stdout": "none", "reportFileCount": 0},
    }


def check_contract(identifier, manifest):
    if "status" in manifest["expect"] or "resultFile" in manifest["expect"]:
        raise ValueError("引数不正は共通結果を作りません")
    if manifest["expect"]["reportFileCount"] != 0:
        raise ValueError("引数不正はreportを書いてはいけません")
    operation = CASES[identifier][0]
    if manifest["invocation"]["argv"][0] != operation:
        raise ValueError("manifestの操作が審査済みcaseと異なります")
    if identifier.startswith("SINGLE-073") and "--report" not in manifest["invocation"]["argv"]:
        raise ValueError("report flagのcaseは--reportを渡す必要があります")
    if identifier.startswith("SINGLE-112"):
        argv = manifest["invocation"]["argv"]
        # ADR-001は存在するため、起点を不正にする原因はpurposeまたは操作だけである。
        if argv[1] != "ADR-001" or digest_reference.ADR_PATH not in reviewed_inputs(identifier):
            raise ValueError("ADR起点caseは存在するADR-001を指定する必要があります")
        if argv[0] == "context" and argv[argv.index("--purpose") + 1] == "interpret":
            raise ValueError("ADR起点はinterpretでは妥当です")
    # 標準エラー出力の契約は共通helperが持つ。この操作で動かし、接頭辞や理由が一致しなくなった
    # ことを見逃さないようにする。
    check_cli_error_output(4, b"", f"bitz: {operation}: reason\n".encode(), operation)
    for bad in (f"bitz: {operation}: \n", f"bitz: other: reason\n",
                f"bitz: {operation}: reason\nextra\n"):
        try:
            check_cli_error_output(4, b"", bad.encode(), operation)
        except ValueError:
            continue
        raise ValueError("標準エラー出力の契約が拒否すべき出力を受理しています")


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
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件が審査済み期待値と異なります")
            if json.loads((fixture / "cli-output.json").read_text()) != cli_output(identifier):
                raise ValueError("CLI出力の期待値が審査済みの契約と異なります")
            check_contract(identifier, manifest)
            if (fixture / "expected").exists():
                raise ValueError("引数不正fixtureは期待結果fileを持ちません")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-cli-error-") as temporary:
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
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
