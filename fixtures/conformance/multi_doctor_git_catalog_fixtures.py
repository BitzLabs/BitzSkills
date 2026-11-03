"""Gitの境界を確定できない`doctor`が、Gitを使わずに判定できるカタログの不適合も並べて返すことを固定する（Coreの公開操作は実行しない）。

実装の確認事項C50（ADR-051の追加）に対応する。`doctor`仕様 §3は、設定の不適合とGitの不在を独立した原因とし、Gitの境界を確定できずに止まる場合も、
Gitを使わずに判定できるカタログの不適合（ルートの`workspace.id`の省略、`multiWorkspace`の形状、除外のパスの不正。いずれも`SPEC-MULTI-CONFIG-001`）を
`SPEC-MULTI-GIT-001`と並べて返し、検査項目`catalog`を`failed`とする。メンバーの設定、パス、未登録の設定などGitを使う検査は行わない。
単独の`doctor`の全体事前検査も同じである。ほかの操作（`check`、`verify`）は、`SPEC-MULTI-GIT-001`だけを返す（複合ワークスペース仕様 §3）。
修正前のCoreは、Gitがないと`doctor`も`SPEC-MULTI-GIT-001`だけを返し、カタログの不適合を隠した。
この群は、その併記と、併記しない境界を、6件で固定する。基本のリポジトリは`MULTI-040`と同じ形（ルート`platform`、
メンバー`web`〈`apps/web`〉と`api`〈`services/api`〉）で、ルートの設定だけを変える。Git不在の作り方も`MULTI-040`と同じ
（`setup.git: false`、`invocation.env.PATH`は`/dev/null`）。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-058-01` | `doctor --all-workspaces`、`.`。Git不在 | `multiWorkspace.members: []`。`SPEC-MULTI-GIT-001`と`SPEC-MULTI-CONFIG-001`（`multiWorkspace.members`）の両方。`catalog`は`failed`。`failed`／1 |
| `MULTI-058-02` | `doctor`（単独）、`.`。Git不在 | 除外のパス`../x`が不正。`SPEC-MULTI-GIT-001`と`SPEC-MULTI-CONFIG-001`（`multiWorkspace.exclude`）の両方。単独結果（`workspace`）。`failed`／1 |
| `MULTI-058-03` | `doctor --all-workspaces`、`.`。Git不在 | ルートの`workspace.id`の省略。`SPEC-MULTI-CONFIG-001`（`workspace.id`、`workspaceId: null`）と`SPEC-MULTI-GIT-001`の両方。`multiWorkspace.id`は`null`。`failed`／1 |
| `MULTI-058-04` | `doctor --all-workspaces`、`.`。Git不在 | 対照: カタログが妥当。`SPEC-MULTI-GIT-001`だけ。`catalog`を置かない。`blocked`／2。修正前のCoreも通る |
| `MULTI-058-05` | `doctor --all-workspaces`、`.`。Git不在 | 対照: カタログの形状は妥当で、Gitを使う検査の不備（メンバー`web`のIDの不一致、未登録の設定）がある。`SPEC-MULTI-GIT-001`だけ。`blocked`／2。修正前のCoreも通る |
| `MULTI-058-06` | `check --all-workspaces`、`.`。Git不在 | 対照: `058-01`と同じ入力。`check`は`SPEC-MULTI-GIT-001`だけ。`blocked`／2。修正前のCoreも通る |

期待値の根拠は規範文（`doctor` §3、複合ワークスペース仕様 §3、結果・診断・終了コード §2.3・§3・§7、診断レジストリ）と、
このモジュールの参照計算だけである。参照計算`reference_expected`は、ルートの設定の本文と、準備手順の後のGitの有無、操作の種別から、診断の集合と並び、
最上位の`checks`、状態、終了コード、`multiWorkspace`または`workspace`のIDを導く。Coreの出力は期待値の根拠にしない。
診断の文言は、`Coreの出力文言のレビュー記録.md`の承認済みの文字列（既存のfixtureが固定済みのもの）である。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .digest_crosscheck import read_yaml
from .harness import setup
from .initial_fixtures import compare_state
from .multi_catalog_fixtures import observe_state
from .multi_doctor_fixtures import CORE
from .multi_doctor_git_fixtures import GIT_ABSENT_ENV, reference_order
from .multi_exclude_fixtures import EXCLUDE_FORMAT, MEMBERS_REQUIRED
from .multi_single_precheck_fixtures import NO_GIT, TOOLS_CONFIG_PATH, base_files
from .multi_workspace_id_fixtures import ROOT_ID_REQUIRED
from .schemas import schema_path
from . import multi_reference

HERE = Path(__file__).resolve().parent
ROOT_CONFIG_PATH = multi_reference.ROOT_CONFIG_PATH
WEB_CONFIG_PATH = multi_reference.WEB_CONFIG_PATH
API_CONFIG_PATH = multi_reference.API_CONFIG_PATH
ROOT_ID = "platform"
HEADER = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
MEMBER_LINES = "    - id: web\n      path: apps/web\n    - id: api\n      path: services/api\n"
# 診断の重大度の順（結果・診断・終了コード §3の最悪値の集約）と、状態ごとの終了コード（同 §3）。
STATUS_RANK = {"blocked": 1, "failed": 2, "error": 3}
EXIT_CODE = {"blocked": 2, "failed": 1, "error": 3}

# 操作: all=`--all-workspaces`、single=単独。inputs: ルートの設定の種類。defect: Gitを使わずに判定できるカタログの不適合の種類
# （`members`、`exclude`、`root-id`）。`None`は併記する不適合がない対照。
CASES = {
    "MULTI-058-01": dict(op="doctor", form="all", cwd=".", inputs="members-empty", defect="members", status="failed", exit=1,
                         description="Git不在で、membersが0件のとき、doctorはGitの不在とカタログの不適合の両方を返す"),
    "MULTI-058-02": dict(op="doctor", form="single", cwd=".", inputs="exclude-invalid", defect="exclude", status="failed", exit=1,
                         description="Git不在で、除外のパスが不正のとき、単独のdoctorもGitの不在とカタログの不適合の両方を返す"),
    "MULTI-058-03": dict(op="doctor", form="all", cwd=".", inputs="root-id-omitted", defect="root-id", status="failed", exit=1,
                         description="Git不在で、ルートのworkspace.idが省略されているとき、doctorはGitの不在とカタログの不適合の両方を返す"),
    "MULTI-058-04": dict(op="doctor", form="all", cwd=".", inputs="valid", defect=None, status="blocked", exit=2,
                         description="Git不在でもカタログが妥当なら、doctorはGitの不在の診断だけを返す"),
    "MULTI-058-05": dict(op="doctor", form="all", cwd=".", inputs="member-defects", defect=None, status="blocked", exit=2,
                         description="Git不在では、メンバーのIDの不一致と未登録の設定を検査せず、doctorはGitの不在の診断だけを返す"),
    "MULTI-058-06": dict(op="check", form="all", cwd=".", inputs="members-empty", defect=None, status="blocked", exit=2,
                         description="Git不在では、カタログの不適合があってもcheckはGitの不在の診断だけを返す"),
}
# 入力の種類ごとの、ルートの設定に含まれるカタログの不適合（操作にかかわらない）。
INPUT_DEFECT = {"members-empty": "members", "exclude-invalid": "exclude", "root-id-omitted": "root-id", "valid": None, "member-defects": None}
RESULT_FILES = {"check": "expected/check.json", "doctor": "expected/doctor.json"}
# 承認済みの診断の文言。`defect`ごとに、診断の`source.key`と文言を持つ。
DEFECT_DIAGNOSTICS = {
    "members": ("multiWorkspace.members", MEMBERS_REQUIRED),
    "exclude": ("multiWorkspace.exclude", EXCLUDE_FORMAT),
    "root-id": ("workspace.id", ROOT_ID_REQUIRED),
}


def operation(identifier):
    return CASES[identifier]["op"]


# --- 入力 -------------------------------------------------------------------------------

def root_text(kind):
    """ルートの設定の本文。それぞれ、原因になる1か所だけが妥当なカタログと異なる。"""
    identity = f"workspace:\n  id: {ROOT_ID}\n"
    if kind in {"valid", "member-defects"}:
        return HEADER + identity + "multiWorkspace:\n  members:\n" + MEMBER_LINES
    if kind == "members-empty":
        return HEADER + identity + "multiWorkspace:\n  members: []\n"
    if kind == "exclude-invalid":
        return HEADER + identity + "multiWorkspace:\n  members:\n" + MEMBER_LINES + "  exclude:\n    - ../x\n"
    if kind == "root-id-omitted":
        return HEADER + "multiWorkspace:\n  members:\n" + MEMBER_LINES
    raise ValueError(f"未知の入力の種類です: {kind}")


def reviewed_inputs(identifier):
    kind = CASES[identifier]["inputs"]
    repo = base_files()
    repo[ROOT_CONFIG_PATH] = root_text(kind)
    if kind == "member-defects":
        # メンバー`web`の設定のIDがカタログと異なり、カタログにない`tools/x`に設定がある。どちらもGitを使う検査の対象である。
        repo[WEB_CONFIG_PATH] = multi_reference.plain_config("frontend")
        repo[TOOLS_CONFIG_PATH] = multi_reference.plain_config("x")
    return {name: (data if isinstance(data, bytes) else data.encode()) for name, data in repo.items()}


def argv_of(identifier):
    case = CASES[identifier]
    if case["op"] == "doctor":
        return ["doctor", "--all-workspaces"] if case["form"] == "all" else ["doctor"]
    return ["check", "--all-workspaces"]


def reviewed_manifest(identifier):
    return {
        "fixtureId": identifier,
        "description": CASES[identifier]["description"],
        "setup": {"git": False, "operations": []},
        "invocation": {"runner": "bitz", "cwd": CASES[identifier]["cwd"], "argv": [*argv_of(identifier), "--format", "json"],
                       "env": dict(GIT_ABSENT_ENV)},
        "expect": {"status": CASES[identifier]["status"], "exitCode": CASES[identifier]["exit"], "stdout": "json",
                   "resultFile": RESULT_FILES[CASES[identifier]["op"]], "reportFileCount": 0},
    }


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def git_diagnostic():
    """Gitの境界を確定できない診断。`MULTI-019`、`MULTI-040`と同じ文言と発生元である。"""
    return {"code": "SPEC-MULTI-GIT-001", "severity": "error", "resultStatus": "blocked", "summary": NO_GIT,
            "source": {"kind": "environment", "component": "git"}}


def catalog_diagnostic(defect):
    """カタログの不適合の診断。ルートの`workspace.id`の省略だけ、同一性を構成できないので`workspaceId`は`null`（結果・診断・終了コード §5）。"""
    key, summary = DEFECT_DIAGNOSTICS[defect]
    return {"code": "SPEC-MULTI-CONFIG-001", "severity": "error", "resultStatus": "failed", "summary": summary,
            "source": {"kind": "file", "workspaceId": None if defect == "root-id" else ROOT_ID,
                       "path": ".spec/bitz.yaml", "key": key}}


def diagnostics_of(identifier):
    """診断の並びは結果・診断・終了コード §7による。`workspaceId: null`のファイルの発生元、環境の発生元、文字列のIDの発生元の順。"""
    defect = CASES[identifier]["defect"]
    if defect is None:
        return [git_diagnostic()]
    catalog = catalog_diagnostic(defect)
    return [catalog, git_diagnostic()] if defect == "root-id" else [git_diagnostic(), catalog]


def subject(identifier):
    """全体結果の`multiWorkspace`、または単独結果の`workspace`。ルートの`workspace.id`を省略していれば`id`は`null`（結果・診断・終了コード §2.3）。"""
    return {"id": None if CASES[identifier]["defect"] == "root-id" else ROOT_ID, "path": "."}


def doctor_checks(identifier):
    checks = [{"name": "core", "status": "passed"}, {"name": "git", "status": "blocked"}]
    if CASES[identifier]["defect"] is not None:
        checks.append({"name": "catalog", "status": "failed"})
    return checks


def reviewed_doctor_result(identifier):
    case = CASES[identifier]
    result = {"schemaVersion": "1.0", "operation": "doctor", "status": case["status"]}
    result["multiWorkspace" if case["form"] == "all" else "workspace"] = subject(identifier)
    result.update({"core": dict(CORE), "checks": doctor_checks(identifier)})
    if case["form"] == "all":
        result["workspaces"] = []
    result.update({"durationMs": 0, "diagnostics": diagnostics_of(identifier)})
    return result


def reviewed_check_result(identifier):
    """`check --all-workspaces`の停止結果。Git不在は`revision: null`、`workspaces`は空（結果・診断・終了コード §2）。"""
    return {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": CASES[identifier]["status"],
            "multiWorkspace": subject(identifier), "workspaces": [], "revision": None, "durationMs": 0,
            "diagnostics": diagnostics_of(identifier)}


def reviewed_result(identifier):
    return {"doctor": reviewed_doctor_result, "check": reviewed_check_result}[operation(identifier)](identifier)


# --- 参照計算 --------------------------------------------------------------------------------

def classify_catalog(text):
    """ルートの設定の本文から、Gitを使わずに判定できるカタログの不適合の種類を導く。ない場合は`None`。

    複合ワークスペース仕様 §2・§2.1とADR-064: ルートの`workspace.id`の省略が最優先（ほかのカタログの不備より優先）、次に`multiWorkspace.members`の形状、
    次に除外のパス。除外のパスの不正は、字句の規則に反するもの（空、絶対パス、`..`の要素）とする。
    """
    config = read_yaml(text)
    workspace = config.get("workspace")
    if not isinstance(workspace, dict) or not isinstance(workspace.get("id"), str):
        return "root-id"
    members = config["multiWorkspace"].get("members")
    if not isinstance(members, list) or not members:
        return "members"
    lines = text.splitlines()
    if "  exclude:" in lines:
        items = [line.strip()[2:] for line in lines[lines.index("  exclude:") + 1:] if line.startswith("    - ")]
        if any(item.startswith("/") or ".." in item.split("/") or not item for item in items):
            return "exclude"
    return None


def reference_expected(text, op, form):
    """参照計算: ルートの設定の本文、操作から、診断のコードと並び、最上位の`checks`、状態、終了コード、対象のIDを導く。

    - この群はいずれもGit不在で、Gitの境界を確定できずに止まる。`SPEC-MULTI-GIT-001`（`blocked`）は全操作が返す。
    - `doctor`だけが、Gitを使わずに判定できるカタログの不適合（`SPEC-MULTI-CONFIG-001`、`failed`）を並べて返し、`catalog`を`failed`とする（`doctor` §3）。
    - 状態は診断の効果の最悪値（`failed`>`blocked`）。
    """
    defect = classify_catalog(text) if op == "doctor" else None
    entries = [{"name": "git", "kind": "environment", "status": "blocked"}]
    if defect is not None:
        entries.append({"name": "config", "kind": "file", "workspaceId": None if defect == "root-id" else ROOT_ID, "status": "failed"})
    status = max((entry["status"] for entry in entries), key=STATUS_RANK.__getitem__)
    result = {"defect": defect, "diagnostics": reference_order(entries), "status": status, "exit": EXIT_CODE[status],
              "subjectId": None if classify_catalog(text) == "root-id" else ROOT_ID}
    if op == "doctor":
        result["checks"] = [("core", "passed"), ("git", "blocked")] + ([("catalog", "failed")] if defect is not None else [])
    return result


def check_against_reference(identifier, result, text):
    case = CASES[identifier]
    reference = reference_expected(text, case["op"], case["form"])
    if reference["defect"] != case["defect"]:
        raise ValueError("カタログの不適合の種類がルートの設定の本文からの参照計算と異なります")
    names = {"config": "SPEC-MULTI-CONFIG-001", "git": "SPEC-MULTI-GIT-001"}
    if [item["code"] for item in result["diagnostics"]] != [names[name] for name in reference["diagnostics"]]:
        raise ValueError("診断の集合または並びが参照計算と異なります")
    if (result["status"], case["exit"]) != (reference["status"], reference["exit"]):
        raise ValueError("状態または終了コードが参照計算と異なります")
    subject_value = result["multiWorkspace"] if case["form"] == "all" else result["workspace"]
    if subject_value != {"id": reference["subjectId"], "path": "."}:
        raise ValueError("対象のIDが参照計算と異なります")
    if case["op"] == "doctor":
        if [(item["name"], item["status"]) for item in result["checks"]] != reference["checks"]:
            raise ValueError("最上位の検査項目が参照計算と異なります")
        if case["form"] == "all" and (result["workspaces"] != [] or "workspace" in result):
            raise ValueError("全体事前検査が非成功の全体結果は、空の`workspaces`と`multiWorkspace`を持つ必要があります")
        if case["form"] == "single" and ("multiWorkspace" in result or "workspaces" in result):
            raise ValueError("単独結果は`multiWorkspace`も`workspaces`も持ちません")
    elif result["revision"] is not None or any(item["code"] == "SPEC-MULTI-CONFIG-001" for item in result["diagnostics"]):
        raise ValueError("`check`は`SPEC-MULTI-GIT-001`だけを返し、`revision`は`null`です")


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力とGitの状態から確かめる。"""
    case = CASES[identifier]
    if (repository / ".git").exists():
        raise ValueError("この群はGitのリポジトリにしません")
    text = (repository / ROOT_CONFIG_PATH).read_text(encoding="utf-8")
    if text != root_text(case["inputs"]):
        raise ValueError("ルートの設定は、原因の1か所以外が妥当なカタログと同じである必要があります")
    if classify_catalog(text) != INPUT_DEFECT[case["inputs"]]:
        raise ValueError("ルートの設定のカタログの不適合の種類が期待と異なります")
    if case["inputs"] == "member-defects":
        # カタログの形状は妥当で、Gitを使う検査の不備だけがある。
        if classify_catalog(text) is not None:
            raise ValueError("カタログの形状は妥当である必要があります")
        if read_yaml((repository / WEB_CONFIG_PATH).read_text(encoding="utf-8"))["workspace"]["id"] == "web":
            raise ValueError("メンバー`web`の設定のIDはカタログのIDと異なる必要があります")
        if not (repository / TOOLS_CONFIG_PATH).is_file():
            raise ValueError("カタログにない設定が必要です")
    # 単独の`doctor`が複合ワークスペースと判定されるには、最も近い設定が`multiWorkspace`を宣言する必要がある。
    if "multiWorkspace" not in read_yaml(text):
        raise ValueError("ルートの設定は`multiWorkspace`を宣言する必要があります")
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
        with tempfile.TemporaryDirectory(prefix="bitz-multi-doctor-git-catalog-") as temporary:
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
            with tempfile.TemporaryDirectory(prefix="bitz-multi-doctor-git-catalog-") as temporary:
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
                    check_against_reference(identifier, result, text)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 1, "status": "Passed" if not errors else "Failed", "errors": errors}
