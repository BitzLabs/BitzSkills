"""`doctor`のGit不在とルートの設定の停止が独立した原因として両方返ることを固定する（Coreの公開操作は実行しない）。

実装の確認事項C33に対応する（ADR-065、ADR-051の追加）。`doctor`仕様 §3は、Gitの利用可否を設定と独立した検査（検査9）とし、
ルートワークスペースの設定（構文、型、必須フィールド、スキーマまたはEARS-AIのメジャーバージョン）で全体事前検査が止まった場合も、
Gitの境界を確定できなければ、設定の診断に加えて`SPEC-MULTI-GIT-001`（`blocked`）を返すと定める。単独の`doctor`の全体事前検査も同じである。
ほかの操作は、設定の停止の診断だけを返す（複合ワークスペース仕様 §3、ADR-063の決定5。`doctor`についてだけADR-065が部分改訂した）。
この群は、その2つの原因の併記と、併記しない境界を、10件で固定する。基本のリポジトリは`MULTI-036`と同じ形（ルート`platform`、
メンバー`web`〈`apps/web`〉と`api`〈`services/api`〉）で、ルートの設定だけを変える。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-040-01` | `doctor --all-workspaces`、`.`。Git不在 | ルートの`earsAi`が非対応。`SPEC-MULTI-GIT-001`と`SPEC-DOCTOR-EARS-001`の両方。`checks`は`core`、`git`（`blocked`）、`catalog`（`blocked`） |
| `MULTI-040-02` | `doctor --all-workspaces`、`.`。Git不在 | ルートの`schemaVersion`が非対応。`SPEC-MULTI-GIT-001`と`SPEC-CONFIG-SCHEMA-001`（`blocked`）の両方。`checks`は`040-01`と同じ |
| `MULTI-040-03` | `doctor --all-workspaces`、`.`。Git不在 | ルートの設定にYAMLのアンカー（構文の不正）。`SPEC-CONFIG-SCHEMA-001`（`error`）と`SPEC-MULTI-GIT-001`。`multiWorkspace.id`は`null`、`catalog`なし。`error`／3 |
| `MULTI-040-04` | `doctor`（単独）、`.`。Git不在 | `040-01`と同じ入力。単独の`doctor`の全体事前検査も両方を返す。単独結果（`workspace`） |
| `MULTI-040-05` | `doctor`（単独）、`docs`。Git不在 | `040-02`と同じ入力を、設定を持たないサブディレクトリから実行する。最も近い設定はルートの設定 |
| `MULTI-040-06` | `check`、`.`。Git不在 | 対照: `040-01`と同じ入力。`check`は`SPEC-EARS-VERSION-001`だけを返す |
| `MULTI-040-07` | `verify`、`.`。Git不在 | 対照: `040-02`と同じ入力。`verify`は`SPEC-CONFIG-SCHEMA-001`だけを返す |
| `MULTI-040-08` | `context REQ-001`、`.`。Git不在 | 対照: `040-01`と同じ入力。`context`は`SPEC-EARS-VERSION-001`だけを返す |
| `MULTI-040-09` | `doctor`（単独）、`.`。Gitあり | 対照: `040-02`と同じ入力。Gitがあれば設定の診断だけで、`git`は`passed` |
| `MULTI-040-10` | `doctor --all-workspaces`、`.`。Gitあり | 対照: `040-03`と同じ入力。Gitがあれば設定の診断だけで、`git`は`passed` |

期待値の根拠は規範文（`doctor` §3、ADR-065、ADR-063の決定4〜6、複合ワークスペース仕様 §3・§8、結果・診断・終了コード §2.3・§3・§5・§7、診断レジストリ）と、
このモジュールの参照計算だけである。参照計算`reference_expected`は、ルートの設定の本文と、準備手順の後のGitの有無、操作の種別から、診断の集合と並び、
最上位の`checks`、状態、終了コード、`multiWorkspace`または`workspace`のIDを導く。Coreの出力は期待値の根拠にしない。
診断の文言は、`Coreの出力文言のレビュー記録.md`の承認済みの文字列（既存のfixtureが固定済みのもの）である。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .harness import setup
from .digest_crosscheck import split_document
from .initial_fixtures import compare_state
from .multi_catalog_fixtures import observe_state
from .multi_doctor_fixtures import CORE, EARS_ACTION, EARS_SUMMARY
from .multi_single_precheck_fixtures import ANCHOR, NO_GIT, base_files, empty_coverage, forbidden_yaml, root_requirement
from .multi_single_precheck_fixtures import ROOT_REQ_PATH
from .schemas import schema_path
from . import multi_crosscheck, multi_reference

HERE = Path(__file__).resolve().parent
SUPPORTED_MAJOR = 1
SCHEMA_SUMMARY = "未対応のスキーマのメジャーバージョンです"
GIT_ABSENT_ENV = {"PATH": "/dev/null"}
NOTES_PATH = "docs/notes.md"
ROOT_CONFIG_PATH = multi_reference.ROOT_CONFIG_PATH

# 操作: all=`doctor --all-workspaces`、single=`doctor`、ほかは操作名。stop: ルートの設定の停止の種類（`ears`、`schema`、`anchor`）。
# 診断の並びのうち、環境の発生元と`workspaceId: null`のファイルの発生元の相対順は結果・診断・終了コード §7による（`ENVIRONMENT_AFTER_NULL_FILE`）。
CASES = {
    "MULTI-040-01": dict(op="doctor", form="all", cwd=".", git=False, stop="ears", status="blocked", exit=2,
                         description="Git不在で、ルートのEARS-AIのメジャーバージョンが非対応のとき、doctorはGitの不在と設定の診断の両方を返す"),
    "MULTI-040-02": dict(op="doctor", form="all", cwd=".", git=False, stop="schema", status="blocked", exit=2,
                         description="Git不在で、ルートのスキーマのメジャーバージョンが非対応のとき、doctorはGitの不在と設定の診断の両方を返す"),
    "MULTI-040-03": dict(op="doctor", form="all", cwd=".", git=False, stop="anchor", status="error", exit=3,
                         description="Git不在で、ルートの設定の構文が不正のとき、doctorはGitの不在と設定の診断の両方を返す"),
    "MULTI-040-04": dict(op="doctor", form="single", cwd=".", git=False, stop="ears", status="blocked", exit=2,
                         description="Git不在で、ルートのEARS-AIのメジャーバージョンが非対応のとき、単独のdoctorもGitの不在と設定の診断の両方を返す"),
    "MULTI-040-05": dict(op="doctor", form="single", cwd="docs", git=False, stop="schema", status="blocked", exit=2,
                         description="Git不在で、設定のないサブディレクトリの単独のdoctorも、ルートの設定の停止とGitの不在の両方を返す"),
    "MULTI-040-06": dict(op="check", form="single", cwd=".", git=False, stop="ears", status="blocked", exit=2,
                         description="Git不在でもcheckは、ルートのEARS-AIのメジャーバージョンの非対応の診断だけを返す"),
    "MULTI-040-07": dict(op="verify", form="single", cwd=".", git=False, stop="schema", status="blocked", exit=2,
                         description="Git不在でもverifyは、ルートのスキーマのメジャーバージョンの非対応の診断だけを返す"),
    "MULTI-040-08": dict(op="context", form="single", cwd=".", git=False, stop="ears", status="blocked", exit=2,
                         description="Git不在でもcontextは、ルートのEARS-AIのメジャーバージョンの非対応の診断だけを返す"),
    "MULTI-040-09": dict(op="doctor", form="single", cwd=".", git=True, stop="schema", status="blocked", exit=2,
                         description="Gitがあれば、単独のdoctorはルートのスキーマのメジャーバージョンの非対応の診断だけを返す"),
    "MULTI-040-10": dict(op="doctor", form="all", cwd=".", git=True, stop="anchor", status="error", exit=3,
                         description="Gitがあれば、doctor --all-workspacesはルートの設定の構文の不正の診断だけを返す"),
}
RESULT_FILES = {"check": "expected/check.json", "context": "expected/context.json",
                "verify": "expected/verify.json", "doctor": "expected/doctor.json"}
# 診断の順序: 結果・診断・終了コード §7は、診断を発生元のワークスペースID、`path`、...の辞書順とし、同一性が確定する前の`workspaceId: null`の発生元を
# 文字列のIDより前に置き、ワークスペースIDを持たない発生元（環境、起動）を`workspaceId: null`の発生元の後、文字列のIDの前に置く（2026-10-20にユーザーが決定）。
# この群は`MULTI-040-03`だけがこの順序に依存する。
ENVIRONMENT_AFTER_NULL_FILE = True


def operation(identifier):
    return CASES[identifier]["op"]


# --- 入力 -------------------------------------------------------------------------------

def stopped_root_config(stop):
    """ルートの設定は、停止の原因になる1か所だけが正しい最小のカタログと異なる。"""
    config = base_files()[ROOT_CONFIG_PATH]
    if stop == "ears":
        return config.replace('earsAi: "1.0"', 'earsAi: "2.0"')
    if stop == "schema":
        return config.replace('schemaVersion: "1.0"', 'schemaVersion: "2.0"')
    if stop == "anchor":
        return config.replace("language: ja\n", "language: &label ja\n")
    raise ValueError(f"未知の停止の種類です: {stop}")


def reviewed_inputs(identifier):
    case = CASES[identifier]
    repo = base_files()
    repo[ROOT_CONFIG_PATH] = stopped_root_config(case["stop"])
    if case["cwd"] == "docs":
        repo[NOTES_PATH] = "# 覚え書き\n\n仕様文書ではない。\n"
    if case["op"] == "context":
        repo[ROOT_REQ_PATH] = root_requirement()
    return {name: (data if isinstance(data, bytes) else data.encode()) for name, data in repo.items()}


def argv_of(identifier):
    case = CASES[identifier]
    if case["op"] == "doctor":
        return ["doctor", "--all-workspaces"] if case["form"] == "all" else ["doctor"]
    if case["op"] == "context":
        return ["context", "REQ-001"]
    return [case["op"]]


def reviewed_manifest(identifier):
    case = CASES[identifier]
    setup_plan = {"git": case["git"], "operations": []}
    if case["git"]:
        setup_plan["baseCommit"] = {"message": "base", "paths": ["."]}
    return {
        "fixtureId": identifier,
        "description": case["description"],
        "setup": setup_plan,
        "invocation": {"runner": "bitz", "cwd": case["cwd"], "argv": [*argv_of(identifier), "--format", "json"],
                       "env": dict(GIT_ABSENT_ENV) if not case["git"] else {}},
        "expect": {"status": case["status"], "exitCode": case["exit"], "stdout": "json",
                   "resultFile": RESULT_FILES[case["op"]], "reportFileCount": 0},
    }


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def git_diagnostic():
    """Gitの境界を確定できない診断。`MULTI-019`、`MULTI-036-04`と同じ文言と発生元である。"""
    return {"code": "SPEC-MULTI-GIT-001", "severity": "error", "resultStatus": "blocked", "summary": NO_GIT,
            "source": {"kind": "environment", "component": "git"}}


def config_diagnostic(identifier):
    """ルートの設定の診断。`doctor`のEARS-AIの非対応だけ、診断のコードと修復手順が異なる（診断レジストリの`DOCTOR-EARS-VERSION`）。"""
    case = CASES[identifier]
    path = ".spec/bitz.yaml"
    if case["stop"] == "ears":
        item = {"code": "SPEC-DOCTOR-EARS-001" if case["op"] == "doctor" else "SPEC-EARS-VERSION-001", "severity": "error",
                "resultStatus": "blocked", "summary": EARS_SUMMARY,
                "source": {"kind": "file", "workspaceId": "platform", "path": path, "key": "earsAi"}}
        if case["op"] == "doctor":
            item["suggestedAction"] = EARS_ACTION
        return item
    if case["stop"] == "schema":
        return {"code": "SPEC-CONFIG-SCHEMA-001", "severity": "error", "resultStatus": "blocked", "summary": SCHEMA_SUMMARY,
                "source": {"kind": "file", "workspaceId": "platform", "path": path, "key": "schemaVersion"}}
    return {"code": "SPEC-CONFIG-SCHEMA-001", "severity": "error", "resultStatus": "error", "summary": ANCHOR,
            "source": {"kind": "file", "workspaceId": None, "path": path, "key": "language"}}


def diagnostics_of(identifier):
    case = CASES[identifier]
    config = config_diagnostic(identifier)
    if case["op"] != "doctor" or case["git"]:
        return [config]
    # `doctor`はGitの不在を加える。並びは`reference_order`の規則。
    if case["stop"] == "anchor":
        return [config, git_diagnostic()] if ENVIRONMENT_AFTER_NULL_FILE else [git_diagnostic(), config]
    return [git_diagnostic(), config]


def doctor_checks(identifier):
    case = CASES[identifier]
    checks = [{"name": "core", "status": "passed"}, {"name": "git", "status": "passed" if case["git"] else "blocked"}]
    if case["stop"] in {"ears", "schema"}:
        checks.append({"name": "catalog", "status": "blocked"})
    return checks


def subject(identifier):
    """全体結果の`multiWorkspace`、または単独結果の`workspace`。有効なルートのIDを構成できなければ`id`は`null`（結果・診断・終了コード §2.3）。"""
    return {"id": None if CASES[identifier]["stop"] == "anchor" else "platform", "path": "."}


def reviewed_doctor_result(identifier):
    case = CASES[identifier]
    result = {"schemaVersion": "1.0", "operation": "doctor", "status": case["status"]}
    if case["form"] == "all":
        result["multiWorkspace"] = subject(identifier)
    else:
        result["workspace"] = subject(identifier)
    result.update({"core": dict(CORE), "checks": doctor_checks(identifier)})
    if case["form"] == "all":
        result["workspaces"] = []
    result.update({"durationMs": 0, "diagnostics": diagnostics_of(identifier)})
    return result


def reviewed_check_result(identifier):
    """`check`。Git不在は`scope: full`、`revision: null`。処理を始める前の停止なので件数は0。"""
    return {"schemaVersion": "1.0", "operation": "check", "status": CASES[identifier]["status"], "scope": "full",
            "workspace": subject(identifier), "revision": None, "checkedDocumentCount": 0, "checkedStatementCount": 0,
            "durationMs": 0, "diagnostics": diagnostics_of(identifier)}


def reviewed_verify_result(identifier):
    return {"schemaVersion": "1.0", "operation": "verify", "status": CASES[identifier]["status"], "scope": "all",
            "workspace": subject(identifier), "targetResults": [], "revision": None, "commands": [], "durationMs": 0,
            "diagnostics": diagnostics_of(identifier)}


def reviewed_context_result(identifier):
    """`context`の停止結果。到達ワークスペースを確定しないので、複合固有のフィールドを持たない。"""
    return {"schemaVersion": "1.0", "operation": "context", "status": CASES[identifier]["status"], "purpose": "interpret",
            "workspace": subject(identifier), "roots": ["REQ-001"], "contextDigest": None, "revision": None,
            "resolution": {"complete": False, "documentCount": 0, "unresolvedStrongRelations": 0},
            "projection": {"detail": "standard", "expanded": []}, "documents": [], "constraintLedger": {"statements": []},
            "coverage": empty_coverage(), "durationMs": 0, "diagnostics": diagnostics_of(identifier)}


def reviewed_result(identifier):
    return {"doctor": reviewed_doctor_result, "check": reviewed_check_result, "verify": reviewed_verify_result,
            "context": reviewed_context_result}[operation(identifier)](identifier)


# --- 参照計算 --------------------------------------------------------------------------------

def major(value):
    return int(str(value).split(".")[0])


def classify_root_config(text):
    """ルートの設定の本文から停止の種類とキーを導く。禁止されたYAML（構文の不正）、スキーマ、EARS-AIの順に調べる。止まらなければ`None`。"""
    if forbidden_yaml(text):
        line = next(line for line in text.splitlines() if any(token[:1] in {"&", "*", "!"} for token in line.split("#", 1)[0].split()))
        return "anchor", line.split(":", 1)[0].strip()
    config = multi_crosscheck.read_yaml(text)
    if major(config["schemaVersion"]) != SUPPORTED_MAJOR:
        return "schema", "schemaVersion"
    if major(config["earsAi"]) != SUPPORTED_MAJOR:
        return "ears", "earsAi"
    return None


def reference_order(entries):
    """結果・診断・終了コード §7: 発生元のワークスペースID、`path`...の辞書順で、`null`のIDは文字列のIDより前。
    環境の発生元はIDを持たない。`null`のファイルの発生元との相対順は`ENVIRONMENT_AFTER_NULL_FILE`の仮定による。"""
    def key(entry):
        kind, workspace_id = entry["kind"], entry.get("workspaceId")
        if kind == "environment":
            return (1 if ENVIRONMENT_AFTER_NULL_FILE else -2, "")
        return (-1 if workspace_id is None else 2, workspace_id or "")
    return [entry["name"] for entry in sorted(entries, key=key)]


def reference_expected(text, git_present, op, form):
    """参照計算: ルートの設定の本文、Gitの有無、操作から、診断のコードと並び、最上位の`checks`、状態、終了コード、対象のIDを導く。

    - 設定の診断は、停止の種類ごとに1件（`SPEC-CONFIG-SCHEMA-001`、`doctor`のEARS-AIは`SPEC-DOCTOR-EARS-001`、ほかの操作は`SPEC-EARS-VERSION-001`）。
    - `doctor`だけが、設定の停止の後も、Gitの境界を確定できなければ`SPEC-MULTI-GIT-001`を加える（ADR-065の決定2・3）。
    - 状態は診断の効果と検査項目の最悪値（`error`>`blocked`）。構文などの不正は`error`、版の非対応とGitの不在は`blocked`。
    - 検査項目`catalog`は版の非対応のときだけ`blocked`で置く（`doctor` §3）。構文などの不正は有効なルートのIDを構成できないので`id`は`null`。
    """
    stop = classify_root_config(text)
    if stop is None:
        raise ValueError("ルートの設定が止まっていません")
    kind, _ = stop
    entries = [{"name": "config", "kind": "file", "workspaceId": None if kind == "anchor" else "platform",
                "status": "error" if kind == "anchor" else "blocked"}]
    git_reported = op == "doctor" and not git_present
    if git_reported:
        entries.append({"name": "git", "kind": "environment", "status": "blocked"})
    status = "error" if any(entry["status"] == "error" for entry in entries) else "blocked"
    result = {"stop": kind, "diagnostics": reference_order(entries), "status": status, "exit": {"error": 3, "blocked": 2}[status],
              "subjectId": None if kind == "anchor" else "platform"}
    if op == "doctor":
        result["checks"] = [("core", "passed"), ("git", "passed" if git_present else "blocked")]
        if kind in {"schema", "ears"}:
            result["checks"].append(("catalog", "blocked"))
    return result


def check_against_reference(identifier, result, text, git_present):
    case = CASES[identifier]
    reference = reference_expected(text, git_present, case["op"], case["form"])
    if reference["stop"] != case["stop"]:
        raise ValueError("停止の種類がルートの設定の本文からの参照計算と異なります")
    names = {"config": config_diagnostic(identifier)["code"], "git": "SPEC-MULTI-GIT-001"}
    if [item["code"] for item in result["diagnostics"]] != [names[name] for name in reference["diagnostics"]]:
        raise ValueError("診断の集合または並びが参照計算と異なります")
    if (result["status"], case["exit"]) != (reference["status"], reference["exit"]):
        raise ValueError("状態または終了コードが参照計算と異なります")
    subject_value = result["multiWorkspace"] if case["form"] == "all" and case["op"] == "doctor" else result["workspace"]
    if subject_value != {"id": reference["subjectId"], "path": "."}:
        raise ValueError("対象のIDが参照計算と異なります")
    if case["op"] == "doctor":
        if [(item["name"], item["status"]) for item in result["checks"]] != reference["checks"]:
            raise ValueError("最上位の検査項目が参照計算と異なります")
        # 全体結果は`multiWorkspace`と空の`workspaces`、単独結果は`workspace`だけを持つ（結果・診断・終了コード §2.3。メンバーの診断を開始しない）。
        if case["form"] == "all" and (result["workspaces"] != [] or "workspace" in result):
            raise ValueError("全体事前検査が非成功の全体結果は、空の`workspaces`と`multiWorkspace`を持つ必要があります")
        if case["form"] == "single" and ("multiWorkspace" in result or "workspaces" in result):
            raise ValueError("単独結果は`multiWorkspace`も`workspaces`も持ちません")
    else:
        if result["revision"] is not None and not git_present:
            raise ValueError("Gitを利用できない状態の停止の`revision`は`null`です")
        if any(item["code"] == "SPEC-MULTI-GIT-001" for item in result["diagnostics"]):
            raise ValueError("`doctor`以外の操作は、設定の停止の診断だけを返します")


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力とGitの状態から確かめる。"""
    case = CASES[identifier]
    if (repository / ".git").exists() != case["git"]:
        raise ValueError("Gitの有無が期待と異なります")
    text = (repository / ROOT_CONFIG_PATH).read_text(encoding="utf-8")
    stop = classify_root_config(text)
    if stop is None:
        raise ValueError("ルートの設定が停止していません")
    kind, key = stop
    if kind != case["stop"]:
        raise ValueError("ルートの設定の停止の種類が期待と異なります")
    # 原因は1か所だけである。それ以外は、`MULTI-036`と同じ最小のカタログと同じである。
    minimal = base_files()[ROOT_CONFIG_PATH]
    original = {"ears": 'earsAi: "2.0"', "schema": 'schemaVersion: "2.0"', "anchor": "language: &label ja"}[kind]
    restored = {"ears": 'earsAi: "1.0"', "schema": 'schemaVersion: "1.0"', "anchor": "language: ja"}[kind]
    if text.count(original) != 1 or text.replace(original, restored) != minimal:
        raise ValueError("ルートの設定は、原因の1か所以外が最小のカタログと同じである必要があります")
    if kind == "anchor" and key != "language":
        raise ValueError("構文の不正の発生元のキーが想定と異なります")
    # 停止はルートの設定だけが原因である。メンバーの設定は正しく、版の非対応を持たない。
    for path in (multi_reference.WEB_CONFIG_PATH, multi_reference.API_CONFIG_PATH):
        member = (repository / path).read_text(encoding="utf-8")
        if classify_root_config(member) is not None:
            raise ValueError("メンバーの設定が停止してはいけません")
    if case["cwd"] == "docs":
        if not (repository / "docs").is_dir() or (repository / "docs/.spec").exists():
            raise ValueError("`docs`は設定を持たないサブディレクトリである必要があります")
    if case["op"] == "context" and not (repository / ROOT_REQ_PATH).is_file():
        raise ValueError("`context`の起点REQ-001が必要です")
    # 単独の`doctor`が複合ワークスペースと判定されるには、読める最も近い設定が`multiWorkspace`を宣言する必要がある（ADR-063の決定4・5）。
    if case["form"] == "single" and case["op"] == "doctor" and kind != "anchor":
        if "multiWorkspace" not in multi_crosscheck.read_yaml(text):
            raise ValueError("単独の`doctor`の対象は`multiWorkspace`を宣言する設定である必要があります")
    return text


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
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / RESULT_FILES[operation(identifier)]).write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-doctor-git-") as temporary:
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
    frontmatter = json.loads(schema_path(root, "frontmatter").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        kind = operation(identifier)
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / RESULT_FILES[kind]).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for key, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[key].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            entries = {path.relative_to(fixture / "repo").as_posix(): path.read_bytes()
                       for path in (fixture / "repo").rglob("*") if path.is_file() or path.is_symlink()}
            if entries != reviewed_inputs(identifier):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if {path.relative_to(fixture).as_posix() for path in (fixture / "expected").glob("*")} != {RESULT_FILES[kind]}:
                raise ValueError("期待値のファイルがレビュー済みの集合と異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-doctor-git-") as temporary:
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
                    text = check_conditions(identifier, repository)
                    check_against_reference(identifier, result, text, (repository / ".git").exists())
                    for path in sorted(repository.glob(".spec/requirements/*.md")):
                        frontmatter_value, _ = split_document(path.read_text(encoding="utf-8"))
                        Draft202012Validator({"$ref": "#/$defs/reqFrontmatter", "$defs": frontmatter["$defs"]}).validate(frontmatter_value)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 1, "status": "Passed" if not errors else "Failed", "errors": errors}
