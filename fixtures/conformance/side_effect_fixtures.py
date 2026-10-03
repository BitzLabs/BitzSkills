"""Coreの副作用のfixture（SINGLE-125-01〜06）のレビュー済みの証跡。Coreは実行しない。

各ケースは、別モジュールで監査済みの元のfixtureと同じ入力・起動・期待結果を使い、
副作用の観点だけを独立に固定する。125-01〜04は`.spec/reports/`自体を置かず、
Coreがレポートのディレクトリや一時ファイルを暗黙に作成しないことをスナップショットで失敗させられるようにする。
125-05は明示したレポート付きの`check`で、最終のレポート1件だけを許し、一時ファイルの残存0件を要求する。
125-06は`.spec/reports`をリポジトリ内のディレクトリへのシンボリックリンクにし、Coreが解決せず保存失敗とすること、
リンク先の既存ファイルを変えず、一時ファイルを残さないことを固定する。
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import report_absent_fixtures, report_write_fixtures
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
REPORT_DIRECTORY = report_write_fixtures.REPORT_DIRECTORY
# id: (元のfixture, 操作, 説明)
CASES = {
    "SINGLE-125-01": ("SINGLE-042", "context", "contextがrepository・HOME・cache・tempへ書き込まない"),
    "SINGLE-125-02": ("SINGLE-001", "doctor", "doctorがrepository・HOME・cache・tempへ書き込まない"),
    "SINGLE-125-03": ("SINGLE-070-01", "check", "reportなしcheckがrepository・HOME・cache・tempへ書き込まない"),
    "SINGLE-125-04": ("SINGLE-055", "verify", "書込みなしcommandのverifyでCoreが何も書き込まない"),
    "SINGLE-125-05": ("SINGLE-071-01", "check", "明示report付きcheckが最終report 1件だけを作り一時fileを残さない"),
    # 保存失敗の結果はSINGLE-072と同一。失敗させる入力だけをシンボリックリンクへ替える。
    "SINGLE-125-06": ("SINGLE-072", "check", "symlinkのreport directoryを解決せず保存失敗とし既存fileと一時fileを残さない"),
}
# 125-06のリンク先。リポジトリ内に置き、既存レポートの不変をスナップショットで検査できるようにする。
LINK_TARGET = "../report-store"
STORE_REPORT = "report-store/existing.json"
# 125-04のテストコマンドはファイルを書かない固定のコマンドに限る。テストのプロセス自身の副作用と分離するため。
NO_WRITE_COMMAND = 'argv: ["/bin/true", "{tests}"]'


def read_tree(directory):
    """通常ファイルはバイト列、シンボリックリンクは`("symlink", リンクの文字列)`で返す。シンボリックリンクは辿らない。"""
    tree = {}
    for current, directories, files in os.walk(directory):
        for name in directories + files:
            path = Path(current) / name
            if path.is_symlink():
                tree[path.relative_to(directory).as_posix()] = ("symlink", os.readlink(path))
            elif path.is_file():
                tree[path.relative_to(directory).as_posix()] = path.read_bytes()
    return tree


def reviewed_inputs(identifier, root=HERE):
    """元のfixtureの入力。125-01〜04では既存レポートとレポートのディレクトリを除き、125-06ではシンボリックリンクへ替える。"""
    source = CASES[identifier][0]
    inputs = read_tree(root / "single" / source / "repo")
    if identifier == "SINGLE-125-06":
        # SINGLE-072の「レポート位置の通常ファイル」を、ディレクトリへのシンボリックリンクと既存レポートへ置き換える。
        del inputs[REPORT_DIRECTORY]
        inputs[REPORT_DIRECTORY] = ("symlink", LINK_TARGET)
        inputs[STORE_REPORT] = report_absent_fixtures.EXISTING_REPORT_BODY
        return inputs
    if identifier != "SINGLE-125-05":
        inputs = {name: content for name, content in inputs.items()
                  if not name.startswith(REPORT_DIRECTORY + "/")}
    return inputs


def reviewed_manifest(identifier, root=HERE):
    source, _, description = CASES[identifier]
    manifest = json.loads((root / "single" / source / "manifest.json").read_text())
    return {**manifest, "fixtureId": identifier, "description": description}


def reviewed_effects(identifier, state):
    if identifier == "SINGLE-125-05":
        return report_write_fixtures.reviewed_effects("SINGLE-071-01", state)
    return {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}


def check_policy(identifier, manifest, effects, inputs):
    """副作用の観点だけを、元のfixtureの監査とは独立に確認する。"""
    _, operation, _ = CASES[identifier]
    argv = manifest["invocation"]["argv"]
    if argv[0] != operation or manifest["invocation"]["env"]:
        raise ValueError("起動はレビュー済みの操作を追加環境なしで実行する必要があります")
    if effects["before"] != effects["after"]:
        raise ValueError("既存のパスはすべて不変である必要があります")
    if any(effects["before"][name] for name in ("home", "cache", "temporary")):
        raise ValueError("`HOME`、キャッシュ、一時ディレクトリの木構造は空で開始する必要があります")
    repository = effects["before"]["repository"]
    if identifier == "SINGLE-125-06":
        if "--report" not in argv or manifest["expect"]["reportFileCount"] != 0 or effects["policy"] != "read-only":
            raise ValueError("保存失敗のケースはレポートを要求し、何も作らない必要があります")
        if repository.get(REPORT_DIRECTORY) != {"kind": "symlink", "target": LINK_TARGET}:
            raise ValueError("レポートのディレクトリは辿らないシンボリックリンクである必要があります")
        if repository.get("report-store", {}).get("kind") != "directory" or STORE_REPORT not in repository:
            raise ValueError("シンボリックリンクはレポートを持つ既存のディレクトリへ解決する必要があります")
        return
    if identifier == "SINGLE-125-05":
        if "--report" not in argv or manifest["expect"]["reportFileCount"] != 1:
            raise ValueError("明示したレポートのケースはレポートをちょうど1件要求する必要があります")
        report_write_fixtures.check_report_contract("SINGLE-071-01", manifest, effects, None)
        return
    if "--report" in argv or manifest["expect"]["reportFileCount"] != 0 or effects["policy"] != "read-only":
        raise ValueError("読取り専用のケースはレポートを要求も許可もできません")
    if any(name == REPORT_DIRECTORY or name.startswith(REPORT_DIRECTORY + "/") for name in repository):
        raise ValueError("読取り専用のケースはレポートのディレクトリなしで開始する必要があります")
    if identifier == "SINGLE-125-04" and NO_WRITE_COMMAND.encode() not in inputs[".spec/bitz.yaml"]:
        raise ValueError("`verify`は書込みをしない固定のテストコマンドを使う必要があります")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        source, operation, _ = CASES[identifier]
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result_bytes = (fixture / f"expected/{operation}.json").read_bytes()
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", json.loads(result_bytes)), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier, root):
                raise ValueError("マニフェストが監査済みの元のfixtureの起動と異なります")
            # 期待結果は元のfixtureの監査済みファイルとバイト単位で一致させ、副作用の観点で結果を変えない。
            if result_bytes != (root / "single" / source / f"expected/{operation}.json").read_bytes():
                raise ValueError("期待結果が監査済みの元のfixtureの結果と異なります")
            if sorted(p.name for p in (fixture / "expected").iterdir()) != [f"{operation}.json"]:
                raise ValueError("参照されない期待結果のファイルは許可しません")
            if effects != reviewed_effects(identifier, effects["before"]):
                raise ValueError("副作用の期待値がレビュー済みのポリシーと異なります")
            inputs = reviewed_inputs(identifier, root)
            if read_tree(fixture / "repo") != inputs:
                raise ValueError("入力が監査済みの元のfixtureのcorpusと異なります")
            if (fixture / "changes").exists():
                raise ValueError("このケースは変更ファイルを適用しません")
            check_policy(identifier, manifest, effects, inputs)
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-side-effects-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
