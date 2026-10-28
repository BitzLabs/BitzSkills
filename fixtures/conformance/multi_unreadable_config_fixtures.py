"""複合ワークスペースで設定が64 KiBの上限を超えたときの、ワークスペースの同一性を固定する（Coreの公開操作は実行しない）。

実装の確認事項C59とADR-051の追加に対応する。設定ファイルが64 KiBを超える（`SPEC-INPUT-LIMIT-001`、診断レジストリ`INPUT-LIMIT-CONFIG`）と、設定を読まずに止まる。
このとき明示した`workspace.id`も分からない。それでも修正前のCoreは、設定の読込みが既定値`root`を同一性に補い、単独結果の`workspace.id`、全体結果の`multiWorkspace.id`、
診断の`source.workspaceId`に`root`を置いた。構文の誤りや文字コードの不正で止まるときは、もともと`null`だった。
この群は、複合ワークスペースの全体操作で、上限の超過が同一性を構成する前に止まる原因として、構文や型の不正と同じ扱いになることを2件で固定する。
単独の`SINGLE-078`は期待値を訂正した（同じ欠陥。[上限と未知のエントリのレビュー記録](../single/上限と未知のエントリのレビュー記録.md)）。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-049-01` | `check --all-workspaces --base HEAD`、`.` | ルートの設定が64 KiBを超える。`multiWorkspace`は`{null, .}`、`workspaces`は空、`SPEC-INPUT-LIMIT-001`の1件で`source.workspaceId`は`null` |
| `MULTI-049-02` | `check --all-workspaces --base HEAD`、`.` | メンバー`web`の設定が64 KiBを超える。ルートの同一性は確定しているので`multiWorkspace`は`{platform, .}`。`source.workspaceId`は`null` |

基本のリポジトリは、ルート`platform`（`.`）の設定とREQ-001、メンバー`web`（`apps/web`）の設定である。入力の種類は次のとおりである。

| 種類 | 内容 |
|---|---|
| `root-oversized` | ルートの設定が、有効な設定にコメント行を足して64 KiBを超える。`web`の設定は上限内 |
| `member-oversized` | `web`の設定が、有効な設定にコメント行を足して64 KiBを超える。ルートの設定は上限内 |

コメント行だけで上限を超えるので、設定のキーを増やさず、設定スキーマの原因を重ねない（`SINGLE-078`と同じ作り方）。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- 診断レジストリ: `INPUT-LIMIT-CONFIG`（`SPEC-INPUT-LIMIT-001`、`error`／`failed`、`stop-operation`）。結果の状態は`failed`、終了コードは1（`SINGLE-078`と同じ）。
- 結果・診断・終了コード §2・§5と複合ワークスペース仕様 §9（ユーザーの決定、2026-10-26）: 設定を読めないこと（上限の超過、読取りの失敗、文字コードの不正）で
  同一性を構成する前に止まった結果は、`workspace.id`、`multiWorkspace.id`、`source.workspaceId`を`null`にする。
  `path`は発見済みのワークスペースの候補からの相対パスで、設定は`.spec/bitz.yaml`である（メンバーの設定は、メンバーのディレクトリからの相対）。
- 複合ワークスペース仕様 §8: 全体事前検査が非成功なら、ワークスペースの処理を始めず`workspaces: []`で結果を返す。
  §9: `multiWorkspace`を`{"id": null, "path": "."}`にするのは、ルートの設定が読めない（または構文、型、IDが不正な）ときに限る。
  それ以外は有効なIDを必須とするので、メンバーの設定が読めなくても、確定したルートのID（`platform`）を使う。
- 本書はメンバーの設定の診断に`workspaceId: null`を置く。メンバー自身のIDも、設定を読めないので構成できないためである（ユーザーの決定、2026-10-26）。
- 読取りの失敗（`INPUT-IO-CONFIG`、権限の不足など）は、適合harnessが作れないので、この群にもfixtureを置かない。単体試験
  （`tests/bitz-core/test_unreadable_config_identity.py`）が固定する。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .digest_crosscheck import read_yaml
from .harness import git, setup
from .initial_fixtures import compare_state
from .input_limit_fixtures import COMMENT_LINE, CONFIG_LIMIT, LIMIT_CODE, repeat
from .multi_catalog_fixtures import observe_state
from .schemas import schema_path
from . import multi_reference

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
ROOT_CONFIG_PATH = multi_reference.ROOT_CONFIG_PATH
WEB_CONFIG_PATH = multi_reference.WEB_CONFIG_PATH
ROOT_ID = "platform"
CONFIG_SOURCE_PATH = ".spec/bitz.yaml"
# 承認済みの診断の文言。`Coreの出力文言のレビュー記録.md`の行#77（SINGLE-078と同じ）。
LIMIT_SUMMARY = "設定ファイルが64 KiB上限を超過しました"
# 修正前のCoreが同一性に補った既定値。
DEFAULT_ID = "root"

# id: dict(inputs, cause, description)。cause: `root-limit`（ルートの設定が上限超過）、`member-limit`（メンバーの設定が上限超過）。
CASES = {
    "MULTI-049-01": dict(inputs="root-oversized", cause="root-limit",
                         description="ルートの設定が64 KiBを超えたとき、multiWorkspace.idを既定値rootにせずnullにする"),
    "MULTI-049-02": dict(inputs="member-oversized", cause="member-limit",
                         description="メンバーの設定が64 KiBを超えたとき、診断のsource.workspaceIdを既定値rootにせずnullにする"),
}
ARGV = ["check", "--all-workspaces", "--base", "HEAD"]


# --- 入力 -------------------------------------------------------------------------------

def oversized(config):
    """有効な設定に、コメント行だけを足して64 KiBを超えさせる。"""
    return config + repeat(COMMENT_LINE, CONFIG_LIMIT)


def reviewed_inputs(identifier):
    """`repo/`の全入力。パス→バイト列。"""
    inputs = CASES[identifier]["inputs"]
    root = multi_reference.root_config((("web", "apps/web"),), root_id=ROOT_ID)
    web = multi_reference.plain_config("web")
    files = {
        ROOT_CONFIG_PATH: oversized(root) if inputs == "root-oversized" else root,
        WEB_CONFIG_PATH: oversized(web) if inputs == "member-oversized" else web,
        multi_reference.ROOT_REQ_PATH: multi_reference.REQ_HEAD + "\n" + multi_reference.REQ_BODY,
    }
    return {name: data.encode() for name, data in files.items()}


def reviewed_manifest(identifier):
    return {
        "fixtureId": identifier,
        "description": CASES[identifier]["description"],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": [*ARGV, "--format", "json"], "env": {}},
        "expect": {"status": "failed", "exitCode": 1, "stdout": "json", "resultFile": "expected/check.json", "reportFileCount": 0},
    }


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def reviewed_result(identifier):
    # ルートの設定を読めないときだけ、全体の同一性を構成できない（複合ワークスペース仕様 §9）。メンバーの設定が読めないときは、ルートのIDを確定している。
    multi_id = None if CASES[identifier]["cause"] == "root-limit" else ROOT_ID
    return {
        "schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": "failed",
        "multiWorkspace": {"id": multi_id, "path": "."}, "workspaces": [],
        "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False}, "durationMs": 0,
        "diagnostics": [{"code": LIMIT_CODE, "severity": "error", "resultStatus": "failed", "summary": LIMIT_SUMMARY,
                         "source": {"kind": "file", "workspaceId": None, "path": CONFIG_SOURCE_PATH}}],
    }


# --- 参照計算 --------------------------------------------------------------------------------

def read_config_bytes(repository, relative):
    path = repository / relative
    return path.read_bytes() if path.is_file() else None


def reference_decision(repository):
    """参照計算: 入力の木構造から、止まる原因と、結果の同一性を導く（診断レジストリ`INPUT-LIMIT-CONFIG`、結果・診断・終了コード §2・§5、複合ワークスペース仕様 §8・§9）。

    設定のバイト数が64 KiBを超えるものを探す。ルートが先（ルートの設定を読めなければ、ルートのIDも、メンバーの一覧も分からない）。
    ルートが読めれば、カタログのメンバーの設定を順に見る。読めない設定の診断は`workspaceId: null`。`multiWorkspace.id`は、ルートを読めたときだけ確定したルートのID。
    """
    root_bytes = read_config_bytes(repository, ROOT_CONFIG_PATH)
    if root_bytes is None:
        raise ValueError("複合ワークスペースのルートの設定が必要です")
    if len(root_bytes) > CONFIG_LIMIT:
        return {"cause": "root-limit", "multiWorkspaceId": None, "sourceWorkspaceId": None}
    root = read_yaml(root_bytes.decode("utf-8"))
    root_id = explicit_id(root)
    if root_id is None:
        raise ValueError("このfixtureのルートは`workspace.id`を明示します")
    declaration = root.get("multiWorkspace")
    members = [(item["id"], item["path"]) for item in declaration.get("members", [])] if isinstance(declaration, dict) else []
    for _, path in members:
        data = read_config_bytes(repository, f"{path}/.spec/bitz.yaml")
        if data is not None and len(data) > CONFIG_LIMIT:
            return {"cause": "member-limit", "multiWorkspaceId": root_id, "sourceWorkspaceId": None}
    return {"cause": None, "multiWorkspaceId": root_id, "sourceWorkspaceId": None}


def defective_decision(repository):
    """修正前のCoreの読み方の再現: 設定を読めずに止まる診断の同一性に、既定値`root`を補う。

    ルートを読めないとき、`multiWorkspace.id`も`source.workspaceId`も`root`になった。メンバーの設定を読めないときは、`multiWorkspace.id`はルートのID、
    診断の`source.workspaceId`だけが`root`になった。
    """
    reference = reference_decision(repository)
    if reference["cause"] is None:
        return reference
    return {**reference, "sourceWorkspaceId": DEFAULT_ID,
            "multiWorkspaceId": DEFAULT_ID if reference["cause"] == "root-limit" else reference["multiWorkspaceId"]}


def explicit_id(config):
    """設定が明示した`workspace.id`。省略は`None`。"""
    workspace = config.get("workspace") if config is not None else None
    value = workspace.get("id") if isinstance(workspace, dict) else None
    return value if isinstance(value, str) else None


def check_against_reference(identifier, result, reference):
    """リテラルの期待値が、参照計算と一致することを要求する。"""
    case = CASES[identifier]
    if reference["cause"] != case["cause"]:
        raise ValueError("停止の原因が入力からの参照計算と異なります")
    if result["status"] != "failed" or [(item["code"], item["resultStatus"], item["summary"]) for item in result["diagnostics"]] != [
            (LIMIT_CODE, "failed", LIMIT_SUMMARY)]:
        raise ValueError("診断または状態が停止の原因と異なります")
    if result["diagnostics"][0]["source"] != {"kind": "file", "workspaceId": reference["sourceWorkspaceId"], "path": CONFIG_SOURCE_PATH}:
        raise ValueError("診断の発生元が入力からの参照計算と異なります")
    if result["multiWorkspace"] != {"id": reference["multiWorkspaceId"], "path": "."} or result["workspaces"] != [] or "workspace" in result:
        raise ValueError("`multiWorkspace`または`workspaces`が入力からの参照計算と異なります")


def git_dirty(repository):
    return bool(git(repository, "status", "--porcelain=v1", "--untracked-files=all").strip())


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力とGitの状態から確かめる。上限の超過以外の不備を持たないことも要求する。"""
    case = CASES[identifier]
    if not (repository / ".git").exists():
        raise ValueError("Gitのリポジトリが必要です")
    if git_dirty(repository):
        raise ValueError("このfixtureの作業ツリーはコミット済みと同じである必要があります")
    sizes = {name: len(read_config_bytes(repository, name)) for name in (ROOT_CONFIG_PATH, WEB_CONFIG_PATH)}
    over = {name for name, size in sizes.items() if size > CONFIG_LIMIT}
    wanted = {ROOT_CONFIG_PATH} if case["inputs"] == "root-oversized" else {WEB_CONFIG_PATH}
    if over != wanted:
        raise ValueError(f"上限を超える設定が{sorted(wanted)}ではなく{sorted(over)}です")
    # 超過した設定は、上限を超える以外の原因（キーの追加、構文の不正）を持たない。上限内の有効な設定の後ろに、コメント行だけを繰り返した形である。
    block = repeat(COMMENT_LINE, CONFIG_LIMIT)
    configs = {}
    for name in sizes:
        text = read_config_bytes(repository, name).decode("utf-8")
        if name in over:
            if not text.endswith(block):
                raise ValueError("超過した設定は、有効な設定の後ろにコメント行を繰り返した形である必要があります")
            text = text[:-len(block)]
            if len(text.encode()) > CONFIG_LIMIT:
                raise ValueError("コメント行を除いた設定は上限内である必要があります")
        configs[name] = read_yaml(text)
    root, web = configs[ROOT_CONFIG_PATH], configs[WEB_CONFIG_PATH]
    if explicit_id(root) != ROOT_ID or [(member["id"], member["path"]) for member in root["multiWorkspace"]["members"]] != [("web", "apps/web")]:
        raise ValueError("ルートは`workspace.id: platform`を明示し、メンバー`web`（`apps/web`）だけを登録する必要があります")
    if explicit_id(web) != "web" or "multiWorkspace" in web:
        raise ValueError("`web`の設定は、`workspace.id: web`を明示し、`multiWorkspace`を宣言してはいけません")
    for config in (root, web):
        if str(config["earsAi"]) != "1.0" or str(config["schemaVersion"]) != "1.0":
            raise ValueError("版は対応するメジャーバージョンである必要があります")
    return reference_decision(repository)


# --- 生成と監査 ---------------------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = root / "multi" / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "expected/check.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-unreadable-config-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe_state(manifest, repository, external)
        (fixture / "side-effects.json").write_text(
            _dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/check.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for key, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[key].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[key] for key, p in files.items()):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if (fixture / "changes").exists() or (fixture / "cli-output.json").exists():
                raise ValueError("このfixtureは`changes/`と`cli-output.json`を持ちません")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-unreadable-config-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {key: sandbox / key for key in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe_state(manifest, repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
                    reference = check_conditions(identifier, repository)
                    check_against_reference(identifier, result, reference)
                    # 欠陥を検出できる入力であること: 修正前の読み方の同一性は、期待値と異なる。
                    broken = defective_decision(repository)
                    if (broken["sourceWorkspaceId"], broken["multiWorkspaceId"]) == (reference["sourceWorkspaceId"], reference["multiWorkspaceId"]):
                        raise ValueError("この入力は修正前のCoreの欠陥を検出できません")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 1, "status": "Passed" if not errors else "Failed", "errors": errors}
