"""変更集合を名前の変更の検出なしに求め、`selection`の件数をパスごとに数えることを固定する（Coreの公開操作は実行しない）。

[ADR-083](../../docs/02.設計書/10_決定記録/ADR-083_変更集合をGitの名前の変更の検出なしに求め、Gitの読取りの失敗をblockedにする.md)、
[`check` §5、§6、§9](../../docs/03.詳細設計/03_操作仕様/02_check.md#5-git基準版と変更集合)を根拠とする。

変更集合は、Gitの名前の変更とコピーの検出をせずに求め、名前の変更は移動元のパスの削除と移動先のパスの追加として入れる（§5）。
`selection.changedPathCount`は変更集合のパスの数、`selection.excludedCodeTestPathCount`はどの逆索引にも該当しないコードまたはテストのパスの数で、
名前の変更は2つのパスとして数える（§9）。`selection.targetDocumentCount`は、変更されたパスから写像した所有文書の数である（§9。削除した仕様文書は基準版のIDへ写像する）。

| fixture | 入力と変更 | 期待 |
|---|---|---|
| `SINGLE-190-01` | どの文書にも所有されないコード`src/old.py`を`src/new.py`へ移す（作業ツリーだけ） | `passed`／0。`changed 2`、`target 0`、`excluded 2` |
| `SINGLE-190-02` | 同じ移動をステージする（インデックス。Gitは名前の変更として検出し得る） | 同上 |
| `SINGLE-190-03` | `approved`のREQ-001が`implements: [src/old.py]`で所有するコードを移し、ステージする | `failed`／1。`changed 2`、`target 1`（移動元だけが逆索引でREQ-001に写る）、`excluded 1`。REQ-001の実装パスが存在しない`SPEC-PATH-INVALID-001`の1件 |
| `SINGLE-190-04` | 仕様文書`REQ-001.md`のパスだけを`REQ-001-renamed.md`へ移し、ステージする | `passed`／0。`changed 2`、`target 1`、`excluded 0` |
| `SINGLE-190-05` | 同じ移動を作業ツリーだけで行う | 同上 |
| `MULTI-072-01` | 複合ワークスペースのメンバー`web`で、所有されないコードの移動をステージする（`apps/web`で実行） | `passed`／0。`workspace`は`web`、`changed 2`、`target 0`、`excluded 2` |

期待値の根拠は規範文と、このモジュールの参照計算（`reference_selection`）だけである。Coreの出力は根拠にしない。参照計算は、準備した後のリポジトリから
`--no-renames`で変更集合を求め、ワークスペースのパスを仕様文書（フロントマターのID、削除なら基準版のID）、`implements`の逆索引、どれにも当たらないパスへ分けて数える。
"""
import copy
import json
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .approved_history_fixtures import (CONFIG, CONFIG_PATH, MULTI_REPO, WEB, _dump, read_tree, req, write_tree)
from .document_fixtures import DOCUMENT, REQ_PATH
from .harness import git, setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
OLD, NEW = "src/old.py", "src/new.py"
CODE = b"# implementation that is moved\n"
RENAMED_REQ = ".spec/requirements/REQ-001-renamed.md"
OWNING_REQ = DOCUMENT.replace("status: approved\n---", f"status: approved\nimplements: [{OLD}]\n---", 1).encode()
PATH_SUMMARY = "実装パスが存在しません"
SPEC_ROOTS = (".spec/requirements/", ".spec/technical/", ".spec/decisions/", ".spec/tasks/")
# 参照計算の読み方。`detect`は名前の変更を検出し、移動先のパスだけを数える（ADR-083の前の読み方）。監査の自己試験がミュータントとして使う。
READING = {"renames": "none"}


def rename(source, target, stage):
    operations = [{"op": "rename", "from": source, "to": target}]
    if stage:
        operations.append({"op": "stage", "paths": [source, target]})
    return operations


def case(repo, operations, selection, description, diagnostics=(), cwd=".", workspace=("root", ".")):
    return dict(repo=repo, operations=operations, selection=selection, description=description,
                diagnostics=list(diagnostics), cwd=cwd, workspace=workspace)


BASE = {CONFIG_PATH: CONFIG, REQ_PATH: req(), OLD: CODE}
CASES = {
    "SINGLE-190-01": case(BASE, rename(OLD, NEW, False), (2, 0, 2),
                          "作業ツリーだけで移した所有されないコードは、移動元と移動先の2つのパスとしてchangedPathCountとexcludedCodeTestPathCountに数える"),
    "SINGLE-190-02": case(BASE, rename(OLD, NEW, True), (2, 0, 2),
                          "ステージした名前の変更も検出せず、所有されないコードの移動元と移動先を2つのパスとして数える"),
    "SINGLE-190-03": case({CONFIG_PATH: CONFIG, REQ_PATH: OWNING_REQ, OLD: CODE}, rename(OLD, NEW, True), (2, 1, 1),
                          "implementsで所有するコードを移すと、移動元だけが逆索引でREQに写り、移動先は所有されないパスとして数える",
                          diagnostics=[{"code": "SPEC-PATH-INVALID-001", "severity": "error", "resultStatus": "failed",
                                        "summary": PATH_SUMMARY,
                                        "source": {"kind": "file", "workspaceId": "root", "path": REQ_PATH, "key": "implements"}}]),
    "SINGLE-190-04": case({CONFIG_PATH: CONFIG, REQ_PATH: req()}, rename(REQ_PATH, RENAMED_REQ, True), (2, 1, 0),
                          "ステージした仕様文書のパスだけの名前の変更は、2つのパスを同じ文書IDの1文書へ写す"),
    "SINGLE-190-05": case({CONFIG_PATH: CONFIG, REQ_PATH: req()}, rename(REQ_PATH, RENAMED_REQ, False), (2, 1, 0),
                          "作業ツリーだけの仕様文書のパスだけの名前の変更も、2つのパスを同じ文書IDの1文書へ写す"),
    "MULTI-072-01": case({**MULTI_REPO, f"{WEB}/{OLD}": CODE}, rename(f"{WEB}/{OLD}", f"{WEB}/{NEW}", True), (2, 0, 2),
                         "複合ワークスペースのメンバーでも、ステージした所有されないコードの名前の変更を2つのパスとして数える",
                         cwd=WEB, workspace=("web", WEB)),
}


def fixture_dir(root, identifier):
    return root / ("multi" if identifier.startswith("MULTI-") else "single") / identifier


def reviewed_manifest(identifier):
    case_ = CASES[identifier]
    status = "failed" if case_["diagnostics"] else "passed"
    return {"fixtureId": identifier, "description": case_["description"],
            "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": copy.deepcopy(case_["operations"])},
            "invocation": {"runner": "bitz", "cwd": case_["cwd"], "argv": ["check", "--base", "HEAD", "--format", "json"], "env": {}},
            "expect": {"status": status, "exitCode": 1 if status == "failed" else 0, "stdout": "json",
                       "resultFile": "expected/check.json", "reportFileCount": 0}}


def reviewed_result(identifier):
    case_ = CASES[identifier]
    changed, target, excluded = case_["selection"]
    workspace_id, path = case_["workspace"]
    return {"schemaVersion": "1.0", "operation": "check", "status": "failed" if case_["diagnostics"] else "passed",
            "scope": "changed", "workspace": {"id": workspace_id, "path": path},
            "revision": {"base": COMMIT, "commit": COMMIT, "dirty": True},
            "selection": {"changedPathCount": changed, "targetDocumentCount": target, "excludedCodeTestPathCount": excluded},
            "durationMs": 0, "diagnostics": copy.deepcopy(case_["diagnostics"])}


# --- 参照計算 -------------------------------------------------------------------------------

def _paths(output):
    return [path for path in output.decode().split("\0") if path]


def change_set(repository):
    """§5の変更集合（名前の変更とコピーを検出しない）。リポジトリ相対のパスの集合。"""
    flag = "--find-renames" if READING["renames"] == "detect" else "--no-renames"
    paths = set(_paths(git(repository, "diff", "--cached", flag, "--name-only", "-z", "HEAD")))
    paths |= set(_paths(git(repository, "diff", flag, "--name-only", "-z")))
    paths |= set(_paths(git(repository, "ls-files", "--others", "--exclude-standard", "-z")))
    return paths


def front_id(content):
    match = re.search(rb"^id: (\S+)$", content, re.M)
    return match.group(1).decode() if match else None


def implements_index(repository, prefix):
    """現在版の仕様文書の`implements`の逆索引（このfixtureの入力の流れの形の配列に限った読み方）。"""
    index = {}
    for path in sorted((repository / prefix / ".spec").rglob("*.md")) if (repository / prefix / ".spec").is_dir() else []:
        content = path.read_bytes()
        match = re.search(rb"^implements: \[([^\]]*)\]$", content, re.M)
        if match:
            for item in match.group(1).decode().split(","):
                index.setdefault(item.strip(), set()).add(front_id(content))
    return index


def reference_selection(repository, prefix):
    """ワークスペース（`prefix`はリポジトリ相対のルートと`/`）の`selection`の3つの件数（§6、§9）。"""
    paths = sorted(path[len(prefix):] for path in change_set(repository) if path.startswith(prefix))
    index = implements_index(repository, prefix)
    documents, excluded = set(), 0
    for path in paths:
        if path.startswith(SPEC_ROOTS) and path.endswith(".md"):
            current = repository / prefix / path
            if current.is_file():
                documents.add(front_id(current.read_bytes()))
            else:
                documents.add(front_id(git(repository, "show", f"HEAD:{prefix}{path}")))
        elif path in index:
            documents |= index[path]
        elif not path.startswith(".spec/"):
            excluded += 1
    return len(paths), len(documents), excluded


def inspector(identifier):
    case_ = CASES[identifier]

    def inspect(repository):
        prefix = "" if case_["workspace"][1] == "." else case_["workspace"][1] + "/"
        if reference_selection(repository, prefix) != case_["selection"]:
            raise ValueError("selectionの件数が参照計算と異なります")
        source, target = case_["operations"][0]["from"], case_["operations"][0]["to"]
        staged = len(case_["operations"]) == 2
        detected = git(repository, "diff", "--cached", "--find-renames", "--name-status", "HEAD").decode()
        # ステージした移動はGitが名前の変更として検出し得る形（同じ内容）であり、作業ツリーだけの移動はインデックスに現れない。
        if staged != detected.startswith("R100") or (repository / source).exists() or not (repository / target).is_file():
            raise ValueError("名前の変更の準備がレビュー済みの形と異なります")
    return inspect


# --- 生成と監査 ---------------------------------------------------------------------------

def prepared_states(fixture, manifest, inspect=None):
    states = []
    with tempfile.TemporaryDirectory(prefix="bitz-change-set-") as temporary:
        for run in range(2):
            sandbox = Path(temporary) / str(run)
            sandbox.mkdir()
            repository = setup(fixture, manifest, sandbox / "repo")
            if inspect is not None:
                inspect(repository)
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            states.append(observe(repository, external))
    if states[0] != states[1]:
        raise ValueError("隔離した2回の準備手順が一致しません")
    return states[0]


def generate(root=HERE, identifiers=None):
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = fixture_dir(root, identifier)
        fixture.mkdir(parents=True, exist_ok=False)
        write_tree(fixture / "repo", CASES[identifier]["repo"])
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir()
        (fixture / "expected/check.json").write_text(_dump(reviewed_result(identifier)))
        state = prepared_states(fixture, manifest, inspector(identifier))
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
            result = json.loads((fixture / "expected/check.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("マニフェストまたは期待結果がレビュー済みの期待値と異なります")
            if {path.name for path in (fixture / "expected").iterdir()} != {"check.json"}:
                raise ValueError("期待値のファイルがレビュー済みの1件と異なります")
            if read_tree(fixture / "repo") != CASES[identifier]["repo"] or (fixture / "changes").exists():
                raise ValueError("入力がレビュー済みの入力と異なります")
            if {path.name for path in fixture.iterdir()} - {"repo", "expected", "manifest.json", "side-effects.json"}:
                raise ValueError("fixtureにレビューしていないファイルがあります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            state = prepared_states(fixture, manifest, inspector(identifier))
            if compare_state(effects["before"], state):
                raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).splitlines()[0] if str(error) else type(error).__name__}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
