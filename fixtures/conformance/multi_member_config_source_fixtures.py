"""複合ワークスペースのメンバーの設定の診断の発生元と、ルートの版の非対応の診断を固定する（Coreの公開操作は実行しない）。

実装の確認事項C72・C37とADR-051の追加に対応する。複合ワークスペースの全体事前検査が返すメンバーの設定の診断（上限の超過、読取りの失敗、文字コードの不正、
YAMLの構文、型、必須の不正）は、修正前のCoreでは、メンバー自身の診断のまま`{workspaceId: null, path: .spec/bitz.yaml}`を返し、ルートの設定の診断と区別できなかった。
ユーザーの決定により、結果・診断・終了コード §5は、`workspaceId`を`null`のまま、`path`を複合ワークスペースのルートからの相対パス
（`apps/web/.spec/bitz.yaml`）とし、作業ディレクトリがそのメンバーの中にある単独の操作でも同じとした（未登録の設定の`SPEC-MULTI-UNREGISTERED-001`と同じ形）。
複合ワークスペース仕様 §2・§11は、`SPEC-MULTI-VERSION-001`をメンバーの版の非対応にだけ使い、ルートワークスペース自身の版の非対応は、その設定の読込みの診断
（`SPEC-CONFIG-SCHEMA-001`、`SPEC-EARS-VERSION-001`、`doctor`のEARS-AIは`SPEC-DOCTOR-EARS-001`）とすると明記した（確認事項C37。Coreの既存の挙動の明記）。

この群は、基本のリポジトリ（ルート`platform`〈`.`〉、メンバー`web`〈`apps/web`〉）のメンバーまたはルートの設定を1か所だけ壊し、次の6件で固定する。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-057-01` | `check --all-workspaces --base HEAD`、`.` | `web`の設定の`language`が整数（型の不正）。`error`／3。`SPEC-CONFIG-SCHEMA-001`の1件で`source`は`{null, apps/web/.spec/bitz.yaml, key: language}` |
| `MULTI-057-02` | `check --full --base HEAD`、`apps/web` | `web`の設定のYAMLの構文の不正。単独の操作。`error`／3。`workspace`は`{null, apps/web}`、`source`は`{null, apps/web/.spec/bitz.yaml}` |
| `MULTI-057-03` | `doctor --all-workspaces`、`.` | `web`の設定が文字コードの不正。`failed`／1。`SPEC-INPUT-READ-001`、`source`は`{null, apps/web/.spec/bitz.yaml}`。`checks[]`の`catalog`は`failed` |
| `MULTI-057-04` | `check --all-workspaces --base HEAD`、`.` | 対照（C37）: ルートの`schemaVersion`が非対応。`blocked`／2。`SPEC-CONFIG-SCHEMA-001`、`source`は`{platform, .spec/bitz.yaml, key: schemaVersion}`。修正前のCoreも通る |
| `MULTI-057-05` | `doctor --all-workspaces`、`apps/web` | 対照（C37）: ルートの`earsAi`が非対応。`blocked`／2。`SPEC-DOCTOR-EARS-001`、`source`は`{platform, .spec/bitz.yaml, key: earsAi}`。メンバーの中から実行する。修正前のCoreも通る |
| `MULTI-057-06` | `check --all-workspaces --base HEAD`、`.` | 対照（C37）: メンバー`web`の`earsAi`が非対応。`blocked`／2。`SPEC-MULTI-VERSION-001`、`source`は`{platform, .spec/bitz.yaml, key: multiWorkspace.members}`。修正前のCoreも通る |

`MULTI-057-01`〜`03`が欠陥（修正前のCoreは`source.path`を`.spec/bitz.yaml`で返す）を検出し、`04`〜`06`は修正前後で変わらない挙動の対照である。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- 診断レジストリ: `CONFIG-FIELD-TYPE`・`CONFIG-YAML-SYNTAX`は`SPEC-CONFIG-SCHEMA-001`（`error`／`error`）、`INPUT-UTF8-CONFIG`は`SPEC-INPUT-READ-001`（`error`／`failed`）、
  `CONFIG-SCHEMA-MAJOR`は`SPEC-CONFIG-SCHEMA-001`（`error`／`blocked`）、`EARS-SCHEMA-MAJOR`は`SPEC-EARS-VERSION-001`（`check`）、
  `DOCTOR-EARS-VERSION`は`SPEC-DOCTOR-EARS-001`（`doctor`）、`MULTI-VERSION`は`SPEC-MULTI-VERSION-001`（`error`／`blocked`）。結果の状態が`error`なら終了コード3、`failed`なら1、`blocked`なら2。
- 結果・診断・終了コード §5: 設定の構文、型、文字コードの不正で同一性を構成できない診断は`workspaceId: null`。メンバーの設定の診断の`path`は複合ワークスペースのルートからの相対。
  ルートの設定の診断は`.spec/bitz.yaml`。ルートの`workspace.id`が有効なら、版の非対応の診断の`workspaceId`はそのID。
- 結果・診断・終了コード §2と複合ワークスペース仕様 §9: `multiWorkspace`を`{id: null, path: .}`にするのは、ルートの設定が読めないか、構文、型またはIDが不正なときに限る。
  メンバーの設定の不備、ルートの版の非対応では、確定したルートのID`platform`を使う。単独の操作の`workspace`は、同一性を構成できないとき`id: null`、`path`は候補のパス。
- 複合ワークスペース仕様 §8: 全体事前検査が非成功なら、ワークスペースの処理を始めず`workspaces: []`で結果を返す。§7: 単独の操作も、全体事前検査の診断だけを最上位の`diagnostics`に置いた単独結果を返す。
- 複合ワークスペース仕様 §2・§11（確認事項C37）: メンバーの版の非対応は`SPEC-MULTI-VERSION-001`で、発生元はルートの設定の`multiWorkspace.members`。
- `doctor` §3: 全体事前検査が非成功のときは、ワークスペース固有の検査を行わず、最上位の`checks[]`に`core`、`git`、`catalog`を置く。
  `catalog`の状態は全体事前検査の状態と同じにする（メンバーの非対応のメジャーバージョン〈`blocked`〉、メンバーのパスの不正〈`failed`〉の既存の期待値と同じ扱い）。

診断の文言は、既存の承認済みのものだけを使う（`Coreの出力文言のレビュー記録.md`と、既存のfixtureが固定した文字列）。

- 型の不正: 「設定キーlanguageは文字列で指定してください」（`SINGLE-004-01`）。
- 文字コードの不正: 「設定ファイルをUTF-8として復号できません」（`Coreの出力文言のレビュー記録.md`の行#83）。
- スキーマの非対応: 「未対応のスキーマのメジャーバージョンです」（`MULTI-040-02`）。EARS-AIの非対応: 「未対応のEARS-AIのメジャーバージョンです」と、
  `doctor`の`suggestedAction`「設定キーearsAiをCoreが対応するメジャーバージョン1に合わせてください」（`MULTI-033`）。
- メンバーのEARS-AIの非対応: 「メンバーの設定キーearsAiのメジャーバージョンが未対応です」（同記録の行#119）。
- YAMLの構文の不正: 「設定YAMLの構文が不正です」。この文字列そのものは、同記録の対応表にも既存のfixtureにもない。ただし、同記録の行#32〜#39が、
  設定YAMLの診断の対象名を「設定YAML」のまま変えないと承認しており（「{label}は設定YAML」）、フロントマターの構文の不正の承認済みの文言「フロントマターのYAMLの構文が不正です」
  （行#70）と同じひな形「{対象名}の構文が不正です」である。表記規則に反せず、Coreの現在の文言と同じなので採った。仕様解釈として報告する。

読取りの失敗（`INPUT-IO-CONFIG`、権限の不足）は、適合harnessが作れないので、この群にもfixtureを置かない（`path`は`tests/bitz-core/test_member_config_source_path.py`が固定する）。
上限の超過は`MULTI-049-02`が固定する。
"""
import json
from pathlib import Path
import re
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
ROOT_CONFIG_PATH = multi_reference.ROOT_CONFIG_PATH
ROOT_REQ_PATH = multi_reference.ROOT_REQ_PATH
WEB_CONFIG_PATH = multi_reference.WEB_CONFIG_PATH
ROOT_ID = "platform"
WEB_PATH = "apps/web"
SUPPORTED_MAJOR = 1
CONFIG_LIMIT = 64 * 1024
CAPABILITIES = ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"]
CORE = {"version": "1.0.0", "apiVersion": "1.0", "capabilities": CAPABILITIES}

# 承認済みの診断の文言（モジュールの説明を参照）。
TYPE_SUMMARY = "設定キーlanguageは文字列で指定してください"
SYNTAX_SUMMARY = "設定YAMLの構文が不正です"
UTF8_SUMMARY = "設定ファイルをUTF-8として復号できません"
SCHEMA_SUMMARY = "未対応のスキーマのメジャーバージョンです"
EARS_SUMMARY = "未対応のEARS-AIのメジャーバージョンです"
EARS_ACTION = "設定キーearsAiをCoreが対応するメジャーバージョン1に合わせてください"
MEMBER_EARS_SUMMARY = "メンバーの設定キーearsAiのメジャーバージョンが未対応です"

# 原因: 診断コードの種類、状態、終了コード、要約、発生元の種類。コードは`check`と`doctor`で異なるものがある（`root-ears`）。
EXIT_BY_STATUS = {"error": 3, "failed": 1, "blocked": 2}
CAUSES = {
    "member-type": dict(code={"check": "SPEC-CONFIG-SCHEMA-001", "doctor": "SPEC-CONFIG-SCHEMA-001"}, status="error", summary=TYPE_SUMMARY),
    "member-syntax": dict(code={"check": "SPEC-CONFIG-SCHEMA-001", "doctor": "SPEC-CONFIG-SCHEMA-001"}, status="error", summary=SYNTAX_SUMMARY),
    "member-utf8": dict(code={"check": "SPEC-INPUT-READ-001", "doctor": "SPEC-INPUT-READ-001"}, status="failed", summary=UTF8_SUMMARY),
    "root-schema": dict(code={"check": "SPEC-CONFIG-SCHEMA-001", "doctor": "SPEC-CONFIG-SCHEMA-001"}, status="blocked", summary=SCHEMA_SUMMARY),
    "root-ears": dict(code={"check": "SPEC-EARS-VERSION-001", "doctor": "SPEC-DOCTOR-EARS-001"}, status="blocked", summary=EARS_SUMMARY),
    "member-version": dict(code={"check": "SPEC-MULTI-VERSION-001", "doctor": "SPEC-MULTI-VERSION-001"}, status="blocked",
                           summary=MEMBER_EARS_SUMMARY),
}
# 修正前のCoreが欠陥を持つ原因。メンバーの設定を読めない・構文・型の不正（確認事項C72）。ほかは修正前後で変わらない対照。
DEFECTIVE = {"member-type", "member-syntax", "member-utf8"}

# id: dict(op, cwd, argv〈`--format json`の前〉, inputs〈入力の種類〉, cause, description)
CASES = {
    "MULTI-057-01": dict(op="check", cwd=".", argv=["check", "--all-workspaces", "--base", "HEAD"], cause="member-type",
                         description="メンバーの設定の型の不正の診断のpathを、複合ワークスペースのルートからの相対にする"),
    "MULTI-057-02": dict(op="check", cwd=WEB_PATH, argv=["check", "--full", "--base", "HEAD"], cause="member-syntax",
                         description="メンバーの中の単独のcheckも、設定のYAMLの構文の不正の診断のpathをルートからの相対にする"),
    "MULTI-057-03": dict(op="doctor", cwd=".", argv=["doctor", "--all-workspaces"], cause="member-utf8",
                         description="メンバーの設定の文字コードの不正の診断のpathを、doctor --all-workspacesでもルートからの相対にする"),
    "MULTI-057-04": dict(op="check", cwd=".", argv=["check", "--all-workspaces", "--base", "HEAD"], cause="root-schema",
                         description="対照: ルートのスキーマの版の非対応は、設定の読込みの診断で、pathはルートの設定のまま"),
    "MULTI-057-05": dict(op="doctor", cwd=WEB_PATH, argv=["doctor", "--all-workspaces"], cause="root-ears",
                         description="対照: ルートのEARS-AIの版の非対応は、メンバーの中から実行しても、doctorの設定の診断でルートの設定を指す"),
    "MULTI-057-06": dict(op="check", cwd=".", argv=["check", "--all-workspaces", "--base", "HEAD"], cause="member-version",
                         description="対照: メンバーのEARS-AIの版の非対応だけがSPEC-MULTI-VERSION-001で、発生元はルートの設定のカタログ"),
}
RESULT_FILES = {"check": "expected/check.json", "doctor": "expected/doctor.json"}


# --- 入力 -------------------------------------------------------------------------------

def reviewed_inputs(identifier):
    """`repo/`の全入力。パス→バイト列。原因ごとに、ルートまたは`web`の設定を1か所だけ壊す。"""
    cause = CASES[identifier]["cause"]
    root = multi_reference.root_config((("web", WEB_PATH),), root_id=ROOT_ID)
    web = multi_reference.plain_config("web").encode()
    if cause == "root-schema":
        root = root.replace('schemaVersion: "1.0"', 'schemaVersion: "2.0"')
    elif cause == "root-ears":
        root = root.replace('earsAi: "1.0"', 'earsAi: "2.0"')
    elif cause == "member-version":
        web = web.replace(b'earsAi: "1.0"', b'earsAi: "2.0"')
    elif cause == "member-type":
        # `SINGLE-004-01`と同じ整数の値。
        web = web.replace(b"language: ja", b"language: 42")
    elif cause == "member-syntax":
        # 閉じられていないフロー配列。YAMLの構文として不正で、禁止された構文（アンカーなど）ではない。
        web = web.replace(b"workspace:\n  id: web\n", b"workspace: [\n")
    elif cause == "member-utf8":
        # コメント行の中の不正なバイト。置換文字で読み続けても設定の内容は有効なので、文字コードの不正だけが原因になる。
        web = web + b"# \xff\n"
    files = {
        ROOT_CONFIG_PATH: root.encode(),
        WEB_CONFIG_PATH: web,
        ROOT_REQ_PATH: (multi_reference.REQ_HEAD + "\n" + multi_reference.REQ_BODY).encode(),
    }
    return files


def reviewed_manifest(identifier):
    case = CASES[identifier]
    status = CAUSES[case["cause"]]["status"]
    return {
        "fixtureId": identifier,
        "description": case["description"],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": case["cwd"], "argv": [*case["argv"], "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": EXIT_BY_STATUS[status], "stdout": "json",
                   "resultFile": RESULT_FILES[case["op"]], "reportFileCount": 0},
    }


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def is_all_workspaces(identifier):
    return "--all-workspaces" in CASES[identifier]["argv"]


def reviewed_source(cause):
    """診断の発生元。メンバーの設定の診断は、同一性を構成できないので`workspaceId: null`、`path`は複合ワークスペースのルートからの相対。"""
    member = {"kind": "file", "workspaceId": None, "path": WEB_CONFIG_PATH}
    return {
        "member-type": {**member, "key": "language"},
        "member-syntax": member,
        "member-utf8": member,
        "root-schema": {"kind": "file", "workspaceId": ROOT_ID, "path": ROOT_CONFIG_PATH, "key": "schemaVersion"},
        "root-ears": {"kind": "file", "workspaceId": ROOT_ID, "path": ROOT_CONFIG_PATH, "key": "earsAi"},
        "member-version": {"kind": "file", "workspaceId": ROOT_ID, "path": ROOT_CONFIG_PATH, "key": "multiWorkspace.members"},
    }[cause]


def reviewed_diagnostic(identifier):
    case = CASES[identifier]
    cause = CAUSES[case["cause"]]
    diagnostic = {"code": cause["code"][case["op"]], "severity": "error", "resultStatus": cause["status"],
                  "summary": cause["summary"], "source": reviewed_source(case["cause"])}
    if case["cause"] == "root-ears" and case["op"] == "doctor":
        diagnostic["suggestedAction"] = EARS_ACTION
    return diagnostic


def reviewed_result(identifier):
    case = CASES[identifier]
    status = CAUSES[case["cause"]]["status"]
    diagnostics = [reviewed_diagnostic(identifier)]
    revision = {"base": COMMIT, "commit": COMMIT, "dirty": False}
    if case["op"] == "check" and is_all_workspaces(identifier):
        return {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": status,
                "multiWorkspace": {"id": ROOT_ID, "path": "."}, "workspaces": [], "revision": revision, "durationMs": 0,
                "diagnostics": diagnostics}
    if case["op"] == "check":
        # 単独の操作。作業ワークスペースは`web`だが、設定を読めないので同一性を構成できず`id: null`、`path`は候補のパス。
        return {"schemaVersion": "1.0", "operation": "check", "status": status, "scope": "full",
                "workspace": {"id": None, "path": WEB_PATH}, "revision": revision, "durationMs": 0,
                "diagnostics": diagnostics, "checkedDocumentCount": 0, "checkedStatementCount": 0}
    # `doctor --all-workspaces`。ワークスペース固有の検査を行わず、最上位の検査項目を置く。`catalog`の状態は全体事前検査の状態と同じ。
    return {"schemaVersion": "1.0", "operation": "doctor", "status": status, "multiWorkspace": {"id": ROOT_ID, "path": "."},
            "core": dict(CORE),
            "checks": [{"name": "core", "status": "passed"}, {"name": "git", "status": "passed"}, {"name": "catalog", "status": status}],
            "workspaces": [], "durationMs": 0, "diagnostics": diagnostics}


# --- 参照計算 --------------------------------------------------------------------------------

def read_config_bytes(repository, relative):
    path = repository / relative
    return path.read_bytes() if path.is_file() else None


def top_level_scalars(text):
    """設定のトップレベルの`キー: 値`（スカラー）を、引用符を外して返す。この参照計算は、fixtureの入力が使う限られた形だけを扱う。"""
    values = {}
    for line in text.split("\n"):
        match = re.match(r"^([A-Za-z][A-Za-z0-9]*):[ \t]*(.*)$", line)
        if match is not None:
            values[match.group(1)] = match.group(2).split(" #", 1)[0].strip().strip('"')
    return values


def unclosed_flow(text):
    """YAMLのフロー配列・フロー写像が閉じられていないか（構文の不正）。コメントを除いた括弧の対応で判定する。"""
    code = "\n".join(line.split(" #", 1)[0] if not line.lstrip().startswith("#") else "" for line in text.split("\n"))
    return code.count("[") != code.count("]") or code.count("{") != code.count("}")


def explicit_workspace_id(text):
    """設定が明示した`workspace.id`（`workspace:`の直下の`id:`）。省略は`None`。"""
    match = re.search(r"^workspace:\n  id: (\S+)$", text, re.MULTILINE)
    return match.group(1) if match is not None else None


def major(value):
    return int(str(value).split(".")[0])


def forbidden_yaml(text):
    """禁止されたYAML（アンカー、エイリアス、タグ。`CONFIG-YAML-FORBIDDEN`）。この参照計算は、fixtureの入力が使う限られた形だけを扱う。"""
    for line in text.split("\n"):
        code = line.split(" #", 1)[0] if not line.lstrip().startswith("#") else ""
        if any(token[:1] in {"&", "*", "!"} for token in code.split()):
            return True
    return False


def config_defects(data):
    """設定のバイト列にある不備を、診断レジストリの条件の順（上限、文字コード、構文、型、版）にすべて返す。不備がなければ空。

    文字コードの不正は、置換文字で読み直して、残りの不備も数える（原因が1か所だけであることを監査で確かめるため）。
    """
    defects = []
    if len(data) > CONFIG_LIMIT:
        defects.append("limit")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        defects.append("utf8")
        text = data.decode("utf-8", errors="replace")
    if unclosed_flow(text):
        defects.append("syntax")
    if forbidden_yaml(text):
        defects.append("forbidden")
    values = top_level_scalars(text)
    if re.fullmatch(r"-?[0-9]+", values.get("language", "")) and not re.search(r'^language:[ \t]*"', text, re.MULTILINE):
        defects.append("type")
    for key, defect in (("schemaVersion", "schema-major"), ("earsAi", "ears-major")):
        if key in values and major(values[key]) != SUPPORTED_MAJOR:
            defects.append(defect)
    return defects


def config_defect(data):
    """最初の不備（診断が報告する不備）。なければ`None`。"""
    defects = config_defects(data)
    return defects[0] if defects else None


def nearest_directory(repository, cwd):
    """複合ワークスペース仕様 §3の手順2: 現在のディレクトリからリポジトリのルートへ親の方向に探索して、最も近い設定のディレクトリを返す。"""
    current = Path(cwd)
    while True:
        if (repository / current / ".spec/bitz.yaml").is_file():
            return current.as_posix()
        if current.as_posix() == ".":
            return None
        current = current.parent


def reference_decision(repository, op, argv, cwd):
    """参照計算: 入力の木構造から、全体事前検査が止まる原因と、診断の発生元、結果の同一性を導く（診断レジストリ、結果・診断・終了コード §2・§5、複合ワークスペース仕様 §3・§7〜§9）。

    ルートの設定が先（読めなければ、カタログも同一性も分からない）。ルートの不備は、ルートのIDが有効なら発生元の`workspaceId`にそのIDを使う。
    ルートを読めたときは、カタログのメンバーの設定を順に見る。メンバーの設定を読めない・構文・型の不正の診断は`workspaceId: null`、`path`はルートからの相対パス。
    メンバーの版の非対応は、発生元がルートの設定の`multiWorkspace.members`。返す辞書は`cause`、`code`、`status`、`exit`、`summary`、`source`、`multiWorkspaceId`
    （全体操作のとき）、`workspace`（単独の操作のとき）を持つ。
    """
    root_bytes = read_config_bytes(repository, ROOT_CONFIG_PATH)
    if root_bytes is None:
        raise ValueError("複合ワークスペースのルートの設定が必要です")
    root_text = root_bytes.decode("utf-8")
    root_id = explicit_workspace_id(root_text)
    if root_id is None:
        raise ValueError("このfixtureのルートは`workspace.id`を明示します")
    members = re.findall(r"- id: (\S+)\n\s+path: (\S+)", root_text)
    cause, member_path = None, None
    root_defect = config_defect(root_bytes)
    if root_defect == "schema-major":
        cause = "root-schema"
    elif root_defect == "ears-major":
        cause = "root-ears"
    elif root_defect is not None:
        raise ValueError("このfixtureのルートの設定の不備は、版の非対応だけです")
    else:
        for _, path in members:
            data = read_config_bytes(repository, f"{path}/.spec/bitz.yaml")
            defect = config_defect(data) if data is not None else None
            if defect == "utf8":
                cause = "member-utf8"
            elif defect == "syntax":
                cause = "member-syntax"
            elif defect == "type":
                cause = "member-type"
            elif defect in {"schema-major", "ears-major"}:
                cause = "member-version"
            elif defect is not None:
                raise ValueError(f"このfixtureが扱わないメンバーの設定の不備です: {defect}")
            if cause is not None:
                member_path = path
                break
    if cause is None:
        return {"cause": None}
    spec = CAUSES[cause]
    op_key = "doctor" if op == "doctor" else "check"
    # メンバーの設定を読めない・構文・型の不正は、メンバーのIDも構成できないので`workspaceId: null`、`path`は複合ワークスペースのルートからの相対。
    # 版の非対応は、同一性を構成できるので、ルートのIDを使う（メンバーの版の非対応は、発生元がルートの設定）。
    unreadable = cause in DEFECTIVE
    source = {"kind": "file", "workspaceId": None if unreadable else root_id,
              "path": f"{member_path}/.spec/bitz.yaml" if unreadable else ROOT_CONFIG_PATH}
    if cause == "member-type":
        source["key"] = "language"
    elif cause == "root-schema":
        source["key"] = "schemaVersion"
    elif cause == "root-ears":
        source["key"] = "earsAi"
    elif cause == "member-version":
        source["key"] = "multiWorkspace.members"
    decision = {"cause": cause, "code": spec["code"][op_key], "status": spec["status"], "exit": EXIT_BY_STATUS[spec["status"]],
                "summary": spec["summary"], "source": source}
    if "--all-workspaces" in argv:
        decision["multiWorkspaceId"] = root_id
    else:
        # 単独の操作の作業ワークスペースは、最も近い設定のディレクトリ。その設定を読めないなら同一性を構成できない。
        # この群の単独の操作は、作業ディレクトリが、設定を読めないメンバーの中にある場合だけである。
        nearest = nearest_directory(repository, cwd)
        if not unreadable or nearest != member_path:
            raise ValueError("この参照計算が扱わない単独の操作です")
        decision["workspace"] = {"id": None, "path": nearest}
    return decision


def defective_decision(repository, op, argv, cwd):
    """修正前のCoreの読み方の再現: メンバーの設定の診断（読めない・構文・型の不正）の`path`を、メンバーのディレクトリからの相対の`.spec/bitz.yaml`のままにする。

    ルートの設定の診断と区別できなかった（確認事項C72の欠陥）。ほかの原因（ルートの版の非対応、メンバーの版の非対応）は修正前後で変わらない。
    """
    reference = reference_decision(repository, op, argv, cwd)
    if reference["cause"] in DEFECTIVE:
        return {**reference, "source": {**reference["source"], "path": ROOT_CONFIG_PATH}}
    return reference


def check_against_reference(identifier, result, reference):
    """リテラルの期待値が、参照計算と一致することを要求する。"""
    case = CASES[identifier]
    if reference["cause"] != case["cause"]:
        raise ValueError("停止の原因が入力からの参照計算と異なります")
    diagnostic = {key: value for key, value in result["diagnostics"][0].items() if key != "suggestedAction"}
    expected = {"code": reference["code"], "severity": "error", "resultStatus": reference["status"], "summary": reference["summary"],
                "source": reference["source"]}
    if len(result["diagnostics"]) != 1 or diagnostic != expected:
        raise ValueError("診断が入力からの参照計算と異なります")
    if result["status"] != reference["status"]:
        raise ValueError("結果の状態が入力からの参照計算と異なります")
    if "multiWorkspaceId" in reference:
        if result["multiWorkspace"] != {"id": reference["multiWorkspaceId"], "path": "."} or "workspace" in result:
            raise ValueError("`multiWorkspace`が入力からの参照計算と異なります")
    elif result["workspace"] != reference["workspace"] or "multiWorkspace" in result:
        raise ValueError("`workspace`が入力からの参照計算と異なります")
    if result.get("workspaces", []) != []:
        raise ValueError("全体事前検査が非成功なので`workspaces`は空である必要があります")
    if case["op"] == "doctor" and result["checks"][-1] != {"name": "catalog", "status": reference["status"]}:
        raise ValueError("`catalog`の状態が全体事前検査の状態と異なります")


def git_dirty(repository):
    return bool(git(repository, "status", "--porcelain=v1", "--untracked-files=all").strip())


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力とGitの状態から確かめる。意図した1か所以外に不備を持たないことも要求する。"""
    case = CASES[identifier]
    if not (repository / ".git").exists():
        raise ValueError("Gitのリポジトリが必要です")
    if git_dirty(repository):
        raise ValueError("このfixtureの作業ツリーはコミット済みと同じである必要があります")
    root_data = read_config_bytes(repository, ROOT_CONFIG_PATH)
    web_data = read_config_bytes(repository, WEB_CONFIG_PATH)
    if root_data is None or web_data is None:
        raise ValueError("ルートと`web`の設定が必要です")
    expected_root = {"root-schema": "schema-major", "root-ears": "ears-major"}.get(case["cause"])
    expected_web = {"member-type": "type", "member-syntax": "syntax", "member-utf8": "utf8", "member-version": "ears-major"}.get(case["cause"])
    if config_defects(root_data) != ([expected_root] if expected_root else []) or config_defects(web_data) != ([expected_web] if expected_web else []):
        raise ValueError(f"設定の不備が意図した1か所ではありません: ルート={config_defects(root_data)}、web={config_defects(web_data)}")
    root_text = root_data.decode("utf-8")
    if not re.search(r"^workspace:\n  id: platform\n", root_text, re.MULTILINE) or re.findall(r"- id: (\S+)\n\s+path: (\S+)", root_text) != [("web", WEB_PATH)]:
        raise ValueError("ルートは`workspace.id: platform`を明示し、メンバー`web`（`apps/web`）だけを登録する必要があります")
    if b"multiWorkspace" in web_data:
        raise ValueError("`web`の設定は`multiWorkspace`を宣言してはいけません")
    return reference_decision(repository, case["op"], case["argv"], case["cwd"])


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
        with tempfile.TemporaryDirectory(prefix="bitz-multi-member-config-source-") as temporary:
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
        case = CASES[identifier]
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / RESULT_FILES[case["op"]]).read_text())
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
            others = {name for name in ("expected/check.json", "expected/doctor.json") if (fixture / name).exists()}
            if others != {RESULT_FILES[case["op"]]}:
                raise ValueError("期待結果のファイルが操作と異なります")
            if (fixture / "changes").exists() or (fixture / "cli-output.json").exists():
                raise ValueError("このfixtureは`changes/`と`cli-output.json`を持ちません")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-member-config-source-") as temporary:
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
                    # 欠陥を検出できる入力であること。修正前の読み方の発生元は、欠陥のある原因では期待値と異なり、対照では同じである。
                    broken = defective_decision(repository, case["op"], case["argv"], case["cwd"])
                    differs = broken["source"] != reference["source"]
                    if differs != (case["cause"] in DEFECTIVE):
                        raise ValueError("修正前のCoreの欠陥を検出できる入力、または対照の入力ではありません")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 1, "status": "Passed" if not errors else "Failed", "errors": errors}
