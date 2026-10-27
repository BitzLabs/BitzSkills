"""値が空の`multiWorkspace:`の宣言を、ルートではメンバー0件の設定不適合、メンバーでは宣言の拒否として止めることを固定する（Coreの公開操作は実行しない）。

実装の確認事項C58・C63とADR-051の追加に対応する。複合ワークスペース仕様 §2.1は、設定が`multiWorkspace`を宣言するかをキー`multiWorkspace`の有無で判定すると定め、
§2は、メンバーが0件の`multiWorkspace`を設定不適合とし、メンバーが`multiWorkspace`を宣言できないと定める。
修正前のCoreは、カタログの形の検査が値の空（`multiWorkspace:`）を「不備なし・メンバー0件」とみなした。ルートが`workspace.id`を明示していると、
メンバー0件の複合ワークスペースとして成功した（C58）。メンバーの設定が`multiWorkspace:`だけを持っても、宣言の拒否にならず通った（C63）。
この群は、その停止と、`members: []`との同値の対照を5件で固定する。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-048-01` | `check --all-workspaces --base HEAD`、`.` | ルートが`workspace.id: platform`を明示し、`multiWorkspace:`が値のない宣言。`SPEC-MULTI-CONFIG-001`の1件（`multiWorkspace.members`）、`multiWorkspace`は`{platform, .}`、`workspaces`は空。`failed`／1 |
| `MULTI-048-02` | `doctor --all-workspaces`、`.` | 同じ入力。`catalog`が`failed`、`suggestedAction`なし |
| `MULTI-048-03` | `check --base HEAD`、`apps/web` | `01`の入力に、カタログ未登録の`apps/web`の設定（`workspace.id: web`）を足す。単独の`check`が`SPEC-MULTI-CONFIG-001`の1件だけを返す（900が`SPEC-MULTI-UNREGISTERED-001`の960より前）。`workspace`は`{null, apps/web}` |
| `MULTI-048-04` | `check --all-workspaces --base HEAD`、`.` | ルートが`web`（`apps/web`）をメンバーとして登録し、`web`の設定が`multiWorkspace:`（値が空）を持つ。`SPEC-MULTI-MEMBER-001`の1件（メンバーは宣言できない） |
| `MULTI-048-05` | `check --all-workspaces --base HEAD`、`.` | 対照: `multiWorkspace`が`members: []`。`01`と同じ結果（値の空と空の配列は同じ設定不適合）。修正前のCoreも通る |

基本のリポジトリは、ルート（`.`）の`.spec/bitz.yaml`と`.spec/requirements/REQ-001.md`である。入力の種類は次のとおりである。

| 種類 | 内容 |
|---|---|
| `root-null` | ルートが`workspace.id: platform`を明示し、`multiWorkspace:`をキーだけ（値なし）で宣言する。メンバーの設定は置かない |
| `root-null-unregistered` | `root-null`に、カタログ未登録の`apps/web/.spec/bitz.yaml`（`workspace.id: web`）を足す |
| `member-null` | ルートが`members`に`web`（`apps/web`）を登録する。`apps/web`の設定が`workspace.id: web`と、キーだけの`multiWorkspace:`を持つ |
| `root-empty-members` | ルートの`multiWorkspace`が`members: []`（対照） |

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- 複合ワークスペース仕様 §2.1: 設定が`multiWorkspace`を宣言するかは、キー`multiWorkspace`の有無で判定する。
  §2: メンバーが0件の`multiWorkspace`は設定不適合とする。メンバーは`multiWorkspace`を宣言できない（§2.1の入れ子の複合ワークスペースとは別）。
- 診断レジストリ: `MULTI-CONFIG`（`SPEC-MULTI-CONFIG-001`、`error`／`failed`、`stop-multi-workspace`、900）、
  `MULTI-MEMBER`（`SPEC-MULTI-MEMBER-001`、910、「`multiWorkspace`を宣言したメンバー」）、`MULTI-UNREGISTERED`（960）。優先順位は数の小さいほうが先。
- 結果・診断・終了コード §2: 停止した単独結果の`workspace.id`は、選択した設定がカタログに登録されていて、明示した有効なIDがカタログのIDと一致するときだけそのID、
  未登録のときは`null`。`path`は選択した設定のワークスペースの候補の複合ワークスペースのルートからの相対パス。
  §5: 診断の`source.workspaceId`は所有ワークスペースのID。ルートが有効な`workspace.id`を明示していればルートのIDを使う。
- ユーザーの決定（2026-10-26）: 値が空の宣言は、`members: []`と同じく、既存の承認済みの文言「設定キーmultiWorkspace.membersは1件以上指定してください」で止める。
  発生元の`key`は`multiWorkspace.members`。メンバーの空の宣言は、既存の承認済みの文言「メンバーは設定キーmultiWorkspaceを宣言できません」の`SPEC-MULTI-MEMBER-001`で止める。
  文言は`Coreの出力文言のレビュー記録.md`の行#86と#104であり、新しい文言ではない。
- `SPEC-MULTI-MEMBER-001`の発生元は、メンバー自身の設定ではなくカタログの宣言（ルートの`.spec/bitz.yaml`の`multiWorkspace.members`）である
  （`MULTI-036-03`、`MULTI-043-10`と同じ。ルートのIDは明示されているので`workspaceId`は`platform`）。
- `doctor` §3の`catalog`は`failed`。`suggestedAction`は付けない（`doctor`仕様 §8の表の診断ではない。`MULTI-043-03`と同じ）。終了コードは`failed`なので1。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .digest_crosscheck import read_yaml
from .harness import git, setup
from .initial_fixtures import compare_state
from .multi_catalog_fixtures import observe_state
from .schemas import schema_path
from . import multi_reference

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
CAPABILITIES = ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"]
CORE = {"version": "1.0.0", "apiVersion": "1.0", "capabilities": CAPABILITIES}
ROOT_CONFIG_PATH = multi_reference.ROOT_CONFIG_PATH
WEB_CONFIG_PATH = multi_reference.WEB_CONFIG_PATH
ROOT_ID = "platform"

# 承認済みの診断の文言。`Coreの出力文言のレビュー記録.md`の行#86と#104（2026-10-12）。
MEMBERS_REQUIRED = "設定キーmultiWorkspace.membersは1件以上指定してください"
MEMBER_NESTED = "メンバーは設定キーmultiWorkspaceを宣言できません"

# id: dict(op, scope, cwd, argv〈`--format json`の前〉, inputs, cause, status, exit, description)
# scope: `all`は`--all-workspaces`、`single`は単独の操作。cause: `members-required`（ルートがメンバー0件）、`member-nested`（メンバーが宣言）。
CASES = {
    "MULTI-048-01": dict(op="check", scope="all", cwd=".", argv=["check", "--all-workspaces", "--base", "HEAD"], inputs="root-null",
                         cause="members-required", status="failed", exit=1,
                         description="ルートの値が空のmultiWorkspaceの宣言を、メンバー0件の設定不適合として止める"),
    "MULTI-048-02": dict(op="doctor", scope="all", cwd=".", argv=["doctor", "--all-workspaces"], inputs="root-null",
                         cause="members-required", status="failed", exit=1,
                         description="ルートの値が空のmultiWorkspaceの宣言を、doctor --all-workspacesのcatalogの失敗として止める"),
    "MULTI-048-03": dict(op="check", scope="single", cwd="apps/web", argv=["check", "--base", "HEAD"], inputs="root-null-unregistered",
                         cause="members-required", status="failed", exit=1,
                         description="ルートの値が空のmultiWorkspaceの宣言は、未登録の設定より先に、単独のcheckを設定不適合の1件で止める"),
    "MULTI-048-04": dict(op="check", scope="all", cwd=".", argv=["check", "--all-workspaces", "--base", "HEAD"], inputs="member-null",
                         cause="member-nested", status="failed", exit=1,
                         description="メンバーの値が空のmultiWorkspaceの宣言を、メンバーはmultiWorkspaceを宣言できないとして止める"),
    "MULTI-048-05": dict(op="check", scope="all", cwd=".", argv=["check", "--all-workspaces", "--base", "HEAD"], inputs="root-empty-members",
                         cause="members-required", status="failed", exit=1,
                         description="対照: multiWorkspaceがmembers: []のときも、値が空の宣言と同じ設定不適合で止める"),
}
RESULT_FILES = {"check": "expected/check.json", "doctor": "expected/doctor.json"}
ROOT_NULL = ("root-null", "root-null-unregistered")
CONFIG_HEAD = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\nworkspace:\n  id: platform\n'
WEB_NULL_CONFIG = multi_reference.plain_config("web") + "multiWorkspace:\n"


# --- 入力 -------------------------------------------------------------------------------

def root_config(inputs):
    """ルートの設定。`workspace.id`は明示する。`multiWorkspace`の値だけが入力ごとに異なる。"""
    if inputs in ROOT_NULL:
        return CONFIG_HEAD + "multiWorkspace:\n"
    if inputs == "root-empty-members":
        return CONFIG_HEAD + "multiWorkspace:\n  members: []\n"
    return multi_reference.root_config((("web", "apps/web"),), root_id=ROOT_ID)


def reviewed_inputs(identifier):
    """`repo/`の全入力。パス→バイト列。"""
    inputs = CASES[identifier]["inputs"]
    files = {
        ROOT_CONFIG_PATH: root_config(inputs),
        multi_reference.ROOT_REQ_PATH: multi_reference.REQ_HEAD + "\n" + multi_reference.REQ_BODY,
    }
    if inputs == "root-null-unregistered":
        files[WEB_CONFIG_PATH] = multi_reference.plain_config("web")
    if inputs == "member-null":
        files[WEB_CONFIG_PATH] = WEB_NULL_CONFIG
    return {name: data.encode() for name, data in files.items()}


def reviewed_manifest(identifier):
    case = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": case["description"],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": case["cwd"], "argv": [*case["argv"], "--format", "json"], "env": {}},
        "expect": {"status": case["status"], "exitCode": case["exit"], "stdout": "json",
                   "resultFile": RESULT_FILES[case["op"]], "reportFileCount": 0},
    }


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def diagnostic(identifier):
    # どちらの原因も、発生元はルートの`.spec/bitz.yaml`の`multiWorkspace.members`。ルートのIDは明示されているので`workspaceId`は`platform`。
    code, summary = {
        "members-required": ("SPEC-MULTI-CONFIG-001", MEMBERS_REQUIRED),
        "member-nested": ("SPEC-MULTI-MEMBER-001", MEMBER_NESTED),
    }[CASES[identifier]["cause"]]
    return {"code": code, "severity": "error", "resultStatus": "failed", "summary": summary,
            "source": {"kind": "file", "workspaceId": ROOT_ID, "path": ".spec/bitz.yaml", "key": "multiWorkspace.members"}}


# 単独の操作の`workspace`。選択した設定がカタログに未登録なので`id`は`null`（結果・診断・終了コード §2）。
SINGLE_WORKSPACES = {"MULTI-048-03": {"id": None, "path": "apps/web"}}


def reviewed_check_result(identifier):
    case = CASES[identifier]
    revision = {"base": COMMIT, "commit": COMMIT, "dirty": False}
    if case["scope"] == "all":
        return {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": case["status"],
                "multiWorkspace": {"id": ROOT_ID, "path": "."}, "workspaces": [], "revision": revision, "durationMs": 0,
                "diagnostics": [diagnostic(identifier)]}
    # 引数なしの単独の`check`は`scope: changed`。処理を始める前の停止なので件数は0。
    return {"schemaVersion": "1.0", "operation": "check", "scope": "changed", "status": case["status"],
            "workspace": dict(SINGLE_WORKSPACES[identifier]), "revision": revision, "durationMs": 0,
            "selection": {"changedPathCount": 0, "targetDocumentCount": 0, "excludedCodeTestPathCount": 0},
            "diagnostics": [diagnostic(identifier)]}


def reviewed_doctor_result(identifier):
    # `catalog`は`failed`（`doctor`仕様 §3、`MULTI-043-03`）。`doctor --all-workspaces`の停止結果は`multiWorkspace`と空の`workspaces`を持つ。
    status = CASES[identifier]["status"]
    return {"schemaVersion": "1.0", "operation": "doctor", "status": status, "core": json.loads(json.dumps(CORE)),
            "checks": [{"name": "core", "status": "passed"}, {"name": "git", "status": "passed"}, {"name": "catalog", "status": status}],
            "durationMs": 0, "diagnostics": [diagnostic(identifier)],
            "multiWorkspace": {"id": ROOT_ID, "path": "."}, "workspaces": []}


def reviewed_result(identifier):
    return {"check": reviewed_check_result, "doctor": reviewed_doctor_result}[CASES[identifier]["op"]](identifier)


# --- 参照計算 --------------------------------------------------------------------------------

def load_config(repository, directory):
    path = repository / directory / ".spec/bitz.yaml"
    return read_yaml(path.read_text(encoding="utf-8")) if path.is_file() else None


def explicit_id(config):
    """設定が明示した`workspace.id`。省略は`None`。"""
    workspace = config.get("workspace") if config is not None else None
    value = workspace.get("id") if isinstance(workspace, dict) else None
    return value if isinstance(value, str) else None


def nearest_directory(repository, cwd):
    """複合ワークスペース仕様 §3の手順2: 現在のディレクトリからリポジトリのルートへ探索して、最も近い設定のディレクトリを返す。"""
    current = Path(cwd)
    while True:
        if (repository / current / ".spec/bitz.yaml").is_file():
            return current.as_posix()
        if current.as_posix() == ".":
            raise ValueError("最も近い設定がありません")
        current = current.parent


def reference_decision(repository, cwd):
    """参照計算: 入力の木構造から、全体事前検査の停止の原因と、停止結果の`workspace`を導く（複合ワークスペース仕様 §2・§2.1・§7、結果・診断・終了コード §2）。

    宣言はキー`multiWorkspace`の有無で判定する（値が空でも宣言する）。原因は、`members-required`（宣言したルートのメンバーが0件）、
    `member-nested`（登録したメンバーの設定が`multiWorkspace`を宣言する）、`None`。優先は、ルートの設定不適合（900）がメンバーの不備（910）より先。
    """
    root = load_config(repository, ".")
    if root is None or "multiWorkspace" not in root:
        raise ValueError("複合ワークスペースのルートの設定が必要です")
    root_id = explicit_id(root)
    if root_id is None:
        raise ValueError("このfixtureのルートは`workspace.id`を明示します")
    declaration = root["multiWorkspace"]
    # 値が空の宣言（`{}`）は、`members`を持たない宣言と同じ。`members: []`も0件。
    members = [(item["id"], item["path"]) for item in declaration.get("members", [])] if isinstance(declaration, dict) else []
    cause = None
    if not members:
        cause = "members-required"
    else:
        for _, path in members:
            config = load_config(repository, path)
            if config is not None and "multiWorkspace" in config:
                cause = "member-nested"
                break
    nearest = nearest_directory(repository, cwd)
    registered = {path: member_id for member_id, path in members}
    if nearest == ".":
        workspace_id = root_id
    elif nearest in registered and explicit_id(load_config(repository, nearest)) == registered[nearest]:
        workspace_id = registered[nearest]
    else:
        workspace_id = None
    return {"cause": cause, "multiWorkspaceId": root_id, "workspace": {"id": workspace_id, "path": nearest}}


def defective_decision(repository, cwd):
    """修正前のCoreの読み方の再現: 値が空の宣言（`multiWorkspace:`）を「不備なし」とみなす。

    ルートでは値が空の宣言を「メンバー0件」の設定不適合にせず、メンバーでは値が空の宣言を拒否しなかった。
    値のある宣言（`members: []`など）は修正前も修正後も同じ原因を持つ。
    """
    reference = reference_decision(repository, cwd)
    root = load_config(repository, ".")
    if reference["cause"] == "members-required" and root["multiWorkspace"] == {}:
        return {**reference, "cause": None}
    if reference["cause"] == "member-nested":
        declarations = [load_config(repository, item["path"])["multiWorkspace"] for item in root["multiWorkspace"]["members"]
                        if (load_config(repository, item["path"]) or {}).get("multiWorkspace") is not None]
        if all(value == {} for value in declarations):
            return {**reference, "cause": None}
    return reference


def check_against_reference(identifier, result, reference):
    """リテラルの期待値が、参照計算と一致することを要求する。"""
    case = CASES[identifier]
    if reference["cause"] != case["cause"]:
        raise ValueError("停止の原因が入力からの参照計算と異なります")
    table = {"members-required": ("SPEC-MULTI-CONFIG-001", MEMBERS_REQUIRED), "member-nested": ("SPEC-MULTI-MEMBER-001", MEMBER_NESTED)}
    code, summary = table[case["cause"]]
    if [(item["code"], item["resultStatus"]) for item in result["diagnostics"]] != [(code, "failed")] or result["status"] != "failed":
        raise ValueError("診断または状態が停止の原因と異なります")
    diagnostic_item = result["diagnostics"][0]
    if diagnostic_item["summary"] != summary or diagnostic_item["source"] != {
            "kind": "file", "workspaceId": reference["multiWorkspaceId"], "path": ".spec/bitz.yaml", "key": "multiWorkspace.members"}:
        raise ValueError("診断の文言、発生元が入力からの参照計算と異なります")
    if case["scope"] == "all":
        if result["multiWorkspace"] != {"id": reference["multiWorkspaceId"], "path": "."} or result["workspaces"] != []:
            raise ValueError("`multiWorkspace`または`workspaces`が入力からの参照計算と異なります")
        if "workspace" in result:
            raise ValueError("`--all-workspaces`の結果は`workspace`を持ちません")
    else:
        if result["workspace"] != reference["workspace"] or "multiWorkspace" in result or "workspaces" in result:
            raise ValueError("`workspace`が入力からの参照計算と異なります")
    if case["op"] == "doctor" and ([item["name"] for item in result["checks"]] != ["core", "git", "catalog"]
                                   or result["checks"][2]["status"] != "failed" or "suggestedAction" in diagnostic_item):
        raise ValueError("`doctor`の検査項目が全体事前検査の停止結果と異なります")


def git_dirty(repository):
    return bool(git(repository, "status", "--porcelain=v1", "--untracked-files=all").strip())


def only_key(text, key):
    """設定のテキストが、キー`key`を値の子なしの1行（`key:`）で持つこと。値が空の宣言は、`key: {}`などの別の形ではない。"""
    lines = text.split("\n")
    if lines.count(f"{key}:") != 1:
        return False
    after = lines[lines.index(f"{key}:") + 1:]
    return not any(line.strip() and line[:1] in " \t" for line in after[:1])


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力とGitの状態から確かめる。原因以外のカタログの不備を持たないことも要求する。"""
    case = CASES[identifier]
    inputs = case["inputs"]
    if not (repository / ".git").exists():
        raise ValueError("Gitのリポジトリが必要です")
    if git_dirty(repository):
        raise ValueError("このfixtureの作業ツリーはコミット済みと同じである必要があります")
    reference = reference_decision(repository, case["cwd"])
    root = load_config(repository, ".")
    root_text = (repository / ROOT_CONFIG_PATH).read_text(encoding="utf-8")
    web = load_config(repository, "apps/web")
    if explicit_id(root) != ROOT_ID or str(root["earsAi"]) != "1.0" or str(root["schemaVersion"]) != "1.0":
        raise ValueError("ルートは`workspace.id: platform`を明示し、版は対応するメジャーバージョンである必要があります")
    tracked_web = bool(git(repository, "ls-files", "--", WEB_CONFIG_PATH).strip())
    if inputs in ROOT_NULL:
        # 値が空の宣言: キーはあるが値は空。`members`のキーも持たない。
        if root["multiWorkspace"] != {} or not root_text.endswith("multiWorkspace:\n"):
            raise ValueError("`multiWorkspace`は、キーだけで値のない宣言である必要があります")
    if inputs == "root-null" and (web is not None or tracked_web):
        raise ValueError("メンバーの設定を持ってはいけません")
    if inputs == "root-null-unregistered":
        # 未登録の設定はGitで追跡される。カタログは0件なので、どのメンバーにも登録されていない。
        if explicit_id(web) != "web" or "multiWorkspace" in web or not tracked_web:
            raise ValueError("`apps/web`の設定は、明示したIDを持ち、`multiWorkspace`を宣言せず、Gitで追跡される必要があります")
    if inputs == "root-empty-members" and (root["multiWorkspace"] != {"members": []} or web is not None):
        raise ValueError("`multiWorkspace`は`members: []`である必要があります")
    if inputs == "member-null":
        members = [(item["id"], item["path"]) for item in root["multiWorkspace"]["members"]]
        if members != [("web", "apps/web")]:
            raise ValueError("カタログはメンバー`web`（`apps/web`）だけを宣言する必要があります")
        # メンバーは明示したIDがカタログと一致し、原因は値が空の`multiWorkspace`の宣言だけである。
        if explicit_id(web) != "web" or web.get("multiWorkspace") != {} or not only_key((repository / WEB_CONFIG_PATH).read_text(encoding="utf-8"), "multiWorkspace"):
            raise ValueError("`web`の設定は、`workspace.id: web`と、キーだけで値のない`multiWorkspace`を持つ必要があります")
    if case["scope"] == "single" and case["cwd"] != nearest_directory(repository, case["cwd"]):
        raise ValueError("単独の操作は、実行ディレクトリ自身の設定を最も近い設定にします")
    return reference


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
        (fixture / RESULT_FILES[CASES[identifier]["op"]]).write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-null-declaration-") as temporary:
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
            result = json.loads((fixture / RESULT_FILES[CASES[identifier]["op"]]).read_text())
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
            with tempfile.TemporaryDirectory(prefix="bitz-multi-null-declaration-") as temporary:
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
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 1, "status": "Passed" if not errors else "Failed", "errors": errors}
