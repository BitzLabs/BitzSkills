"""SHA-256のリポジトリで動くことを固定する（Coreの公開操作は実行しない）。

[ADR-084](../../docs/02.設計書/10_決定記録/ADR-084_Gitの読取りの既知の問題を解消し、SHA-256のリポジトリに対応する.md)の決定5、
[適合fixture仕様 §3.1](../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#31-準備手順の適用順序)の`setup.objectFormat`、
[Core実行環境・CLI基盤契約 §4](../../docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md#4-git)、
[`doctor` §6](../../docs/03.詳細設計/03_操作仕様/04_doctor.md)を根拠とする。

| fixture | 入力 | 期待 |
|---|---|---|
| `SINGLE-191-01` | `SINGLE-001`の入力を、`setup.objectFormat: sha256`のリポジトリにコミットする | `doctor`。`SINGLE-001`と同じ結果（検査項目`git`は`passed`、`SPEC-DOCTOR-GIT-001`なし） |
| `MULTI-073-01` | `MULTI-026-01`の入力を、`setup.objectFormat: sha256`のリポジトリにコミットする（`apps/web`で実行） | `doctor --all-workspaces`。`MULTI-026-01`と同じ結果 |

`doctor`の結果は`revision`を持たないので、コミットIDの桁数に依存しない（結果・診断・終了コード §2）。Core 1.0はSHA-1とSHA-256のリポジトリを対象とし、
ほかの規則はオブジェクトの形式によらず同じである（ADR-084の決定5）ので、期待結果は基のfixtureの結果と同じとする。基のfixtureが変われば、この群の監査が失敗する。

`revision`を持つ`check`、`context`、`verify`のSHA-256のfixtureは、適合fixture仕様 §4の共通正規化器が`revision.base`と`revision.commit`を「40桁の小文字16進」としか
検査しないので、64桁のコミットIDの扱いが決まるまで置かない（報告の対象）。
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .approved_history_fixtures import _dump, read_tree, write_tree
from .harness import git, setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
CASES = {
    "SINGLE-191-01": dict(base="single/SINGLE-001",
                          description="SHA-256のリポジトリでもdoctorの検査項目gitは成功し、SHA-1のリポジトリと同じ結果を返す"),
    "MULTI-073-01": dict(base="multi/MULTI-026-01",
                         description="SHA-256のリポジトリでもdoctor --all-workspacesはSHA-1のリポジトリと同じ結果を返す"),
}


def fixture_dir(root, identifier):
    return root / ("multi" if identifier.startswith("MULTI-") else "single") / identifier


def base_manifest(identifier):
    return json.loads((HERE / CASES[identifier]["base"] / "manifest.json").read_text())


def reviewed_inputs(identifier):
    return read_tree(HERE / CASES[identifier]["base"] / "repo")


def reviewed_manifest(identifier):
    manifest = copy.deepcopy(base_manifest(identifier))
    manifest["fixtureId"] = identifier
    manifest["description"] = CASES[identifier]["description"]
    # コミットのあるリポジトリにする（`HEAD`の解決を含むGitの読取りを確かめる。`doctor` §6）。
    manifest["setup"] = {"git": True, "objectFormat": "sha256", "baseCommit": {"message": "base", "paths": ["."]},
                         "operations": copy.deepcopy(manifest["setup"]["operations"])}
    return manifest


def reviewed_result(identifier):
    return json.loads((HERE / CASES[identifier]["base"] / "expected/doctor.json").read_text())


def inspect(repository):
    if git(repository, "rev-parse", "--show-object-format").decode().strip() != "sha256":
        raise ValueError("リポジトリのオブジェクトの形式がsha256ではありません")
    if len(git(repository, "rev-parse", "HEAD").decode().strip()) != 64:
        raise ValueError("コミットIDが64桁ではありません")
    if git(repository, "status", "--porcelain=v1", "--untracked-files=all").decode():
        raise ValueError("作業ツリーがクリーンではありません")


def prepared_states(fixture, manifest):
    states = []
    with tempfile.TemporaryDirectory(prefix="bitz-object-format-") as temporary:
        for run in range(2):
            sandbox = Path(temporary) / str(run)
            sandbox.mkdir()
            repository = setup(fixture, manifest, sandbox / "repo")
            inspect(repository)
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            states.append((observe(repository, external), git(repository, "rev-parse", "HEAD")))
    if states[0] != states[1]:
        raise ValueError("隔離した2回の準備手順が一致しません")
    return states[0][0]


def generate(root=HERE, identifiers=None):
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = fixture_dir(root, identifier)
        fixture.mkdir(parents=True, exist_ok=False)
        write_tree(fixture / "repo", reviewed_inputs(identifier))
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir()
        (fixture / "expected/doctor.json").write_text(_dump(reviewed_result(identifier)))
        state = prepared_states(fixture, manifest)
        (fixture / "side-effects.json").write_text(
            _dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = fixture_dir(root, identifier)
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/doctor.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("マニフェストまたは期待結果がレビュー済みの期待値（基のfixture）と異なります")
            if {path.name for path in (fixture / "expected").iterdir()} != {"doctor.json"}:
                raise ValueError("期待値のファイルがレビュー済みの1件と異なります")
            if read_tree(fixture / "repo") != reviewed_inputs(identifier) or (fixture / "changes").exists():
                raise ValueError("入力が基のfixtureの入力と異なります")
            if {path.name for path in fixture.iterdir()} - {"repo", "expected", "manifest.json", "side-effects.json"}:
                raise ValueError("fixtureにレビューしていないファイルがあります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            if compare_state(effects["before"], prepared_states(fixture, manifest)):
                raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).splitlines()[0] if str(error) else type(error).__name__}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
