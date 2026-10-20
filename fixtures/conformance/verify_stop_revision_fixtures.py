"""`verify`の早期に返す結果（設定の停止、対象が0件）の`revision`と`--report`を固定する（Coreの公開操作は実行しない）。

実装の確認事項C41に対応する。`verify`は、検証対象を解決して各テスト割当てを実行する前に結果を返す場合がある。
ワークスペースの設定が停止した場合（スキーマのメジャーバージョンの非対応、YAMLの構文の不正）と、検証対象が0件の場合である。
この早期に返す結果も、ほかの`verify`の結果と同じ2つの規則に従う。

- `revision`（結果・診断・終了コード §2）: 単一ワークスペースでGit不在、またはコミットのないリポジトリだけ`null`とする。
  それ以外は`commit`と`dirty`を持つ。`dirty`は実行時の作業ツリーの状態であり、レポートの保存より前に求める。
- `--report`（同 §8）: `check`と`verify`は、状態にかかわらず、指定された場合だけ`.spec/reports/`へ結果のJSONを保存する。
  設定の停止や対象が0件の`blocked`／`error`でも保存する。`--report`がなければ何も作らない。

| fixture | 原因 | 起動 | Git | 期待 |
|---|---|---|---|---|
| `SINGLE-165-01` | スキーマのメジャーバージョンが非対応 | `--report` | コミットあり、クリーン | `blocked`／2、`revision`は`dirty: false`、レポート1件 |
| `SINGLE-165-02` | YAMLのアンカー（構文の不正） | `--report` | コミットあり、クリーン | `error`／3、`workspace.id`は`null`、`revision`あり、レポート1件 |
| `SINGLE-165-03` | 検証対象が0件（`approved`のREQがない） | `--report` | コミットあり、クリーン | `blocked`／2、`revision`あり、レポート1件 |
| `SINGLE-165-04` | 検証対象が0件 | なし | コミットあり、クリーン | `revision`あり、レポート0件 |
| `SINGLE-165-05` | スキーマのメジャーバージョンが非対応 | なし | コミットあり、未追跡のファイルあり | `revision`は`dirty: true`、レポート0件 |
| `SINGLE-165-06` | スキーマのメジャーバージョンが非対応 | `--report` | コミットなし（ステージのみ） | `revision: null`だが、レポート1件 |
| `SINGLE-165-07` | 検証対象が0件 | `--report` | Git不在 | `revision: null`だが、レポート1件 |

期待値の根拠は規範文（結果・診断・終了コード §2・§3・§7・§8、診断レジストリ）と、このモジュールの参照計算だけである。
参照計算`reference_expected`は、設定の本文、REQの`status`、準備手順の後のGitの状態（コミットの有無と作業ツリーの変更の有無）、
`--report`の有無から、停止の種類、状態、終了コード、診断のコード、`revision`の有無と`dirty`、レポートの件数を導く。
Coreの出力は期待値の根拠にしない。診断の文言は、`Coreの出力文言のレビュー記録.md`の承認済みの文字列（既存のfixtureが固定済みのもの）である。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference, report_absent_fixtures
from .harness import git, setup
from .initial_fixtures import compare_state
from .multi_catalog_fixtures import observe_state
from .multi_doctor_git_fixtures import SCHEMA_SUMMARY, classify_root_config
from .multi_single_precheck_fixtures import ANCHOR
from .report_write_fixtures import NAME_PATTERN, REPORT_DIRECTORY

HERE = Path(__file__).resolve().parent
EXISTING_REPORT = report_absent_fixtures.EXISTING_REPORT
CONFIG_PATH = digest_reference.CONFIG_PATH
REQ_PATH = digest_reference.REQ_PATH
NOTES_PATH = "docs/notes.md"
RESULT_FILE = "expected/verify.json"
GIT_ABSENT_ENV = {"PATH": "/dev/null"}
COMMIT = "0" * 40
EXIT_BY_STATUS = {"blocked": 2, "error": 3}

# stop: 設定の停止の種類（`schema`、`anchor`）または`None`（停止せず、対象が0件で返る）。
# git: `committed`（コミットあり）、`staged`（ステージのみでコミットなし）、`absent`（Git不在）。
# untracked: 基準版のコミットに含めない未追跡のファイルを作業ツリーに置く（`dirty: true`を作る）。
CASES = {
    "SINGLE-165-01": dict(stop="schema", report=True, git="committed", untracked=False,
                          description="スキーマのメジャーバージョンが非対応のverifyが、revisionを返し--reportのレポートを保存する"),
    "SINGLE-165-02": dict(stop="anchor", report=True, git="committed", untracked=False,
                          description="設定の構文が不正のverifyが、revisionを返し--reportのレポートを保存する"),
    "SINGLE-165-03": dict(stop=None, report=True, git="committed", untracked=False,
                          description="対象が0件のverifyが、revisionを返し--reportのレポートを保存する"),
    "SINGLE-165-04": dict(stop=None, report=False, git="committed", untracked=False,
                          description="対象が0件のverifyが、--reportなしでもコミットがあればrevisionを返し、レポートを作らない"),
    "SINGLE-165-05": dict(stop="schema", report=False, git="committed", untracked=True,
                          description="設定が停止したverifyのrevisionは、作業ツリーに未追跡のファイルがあればdirtyがtrueになる"),
    "SINGLE-165-06": dict(stop="schema", report=True, git="staged", untracked=False,
                          description="コミットのないリポジトリで設定が停止したverifyは、revisionがnullでも--reportのレポートを保存する"),
    "SINGLE-165-07": dict(stop=None, report=True, git="absent", untracked=False,
                          description="Git不在で対象が0件のverifyは、revisionがnullでも--reportのレポートを保存する"),
}


# --- 入力 -------------------------------------------------------------------------------

def stopped_config(stop):
    """設定は、停止の原因になる1か所だけが`digest_reference.CONFIG`と異なる。"""
    config = digest_reference.CONFIG
    if stop is None:
        return config
    if stop == "schema":
        replaced = config.replace('schemaVersion: "1.0"', 'schemaVersion: "2.0"', 1)
    elif stop == "anchor":
        replaced = config.replace("language: ja", "language: &label ja", 1)
    else:
        raise ValueError(f"未知の停止の種類です: {stop}")
    if replaced == config:
        raise ValueError("レビュー済みの設定に置換の対象がありません")
    return replaced


def draft_requirement():
    """`status: draft`のREQ。`approved`の文書がないので、引数なしの`verify`の検証対象は0件になる。"""
    return (digest_reference.REQ_HEAD.replace("status: approved", "status: draft")
            + "\n" + digest_reference.REQ_BODY)


def reviewed_inputs(identifier):
    case = CASES[identifier]
    inputs = {
        CONFIG_PATH: stopped_config(case["stop"]).encode(),
        REQ_PATH: draft_requirement().encode(),
        # 排他的な作成と置換を区別するため、既存のレポートを置く（`SINGLE-071`と同じ）。
        EXISTING_REPORT: report_absent_fixtures.EXISTING_REPORT_BODY,
    }
    if case["untracked"]:
        inputs[NOTES_PATH] = "# 覚え書き\n\n仕様文書ではない。\n".encode()
    return inputs


def reviewed_manifest(identifier):
    case = CASES[identifier]
    result_status = reference_status(case["stop"])
    if case["git"] == "absent":
        plan = {"git": False, "operations": []}
    elif case["git"] == "staged":
        plan = {"git": True, "operations": [{"op": "stage", "paths": ["."]}]}
    else:
        # 未追跡のファイルは基準版のコミットに含めない。
        plan = {"git": True, "baseCommit": {"message": "base", "paths": [".spec"] if case["untracked"] else ["."]},
                "operations": []}
    argv = ["verify", "--format", "json"] + (["--report"] if case["report"] else [])
    return {
        "fixtureId": identifier,
        "description": case["description"],
        "setup": plan,
        "invocation": {"runner": "bitz", "cwd": ".", "argv": argv,
                       "env": dict(GIT_ABSENT_ENV) if case["git"] == "absent" else {}},
        "expect": {"status": result_status, "exitCode": EXIT_BY_STATUS[result_status], "stdout": "json",
                   "resultFile": RESULT_FILE, "reportFileCount": 1 if case["report"] else 0},
    }


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def reference_status(stop):
    """設定の構文の不正は`error`、版の非対応と対象0件は`blocked`（診断レジストリ、結果・診断・終了コード §3）。"""
    return "error" if stop == "anchor" else "blocked"


def diagnostic(stop):
    path = ".spec/bitz.yaml"
    if stop == "schema":
        return {"code": "SPEC-CONFIG-SCHEMA-001", "severity": "error", "resultStatus": "blocked", "summary": SCHEMA_SUMMARY,
                "source": {"kind": "file", "workspaceId": "root", "path": path, "key": "schemaVersion"}}
    if stop == "anchor":
        # 同一性を構成する前に停止したので`workspaceId`は`null`（結果・診断・終了コード §5）。
        return {"code": "SPEC-CONFIG-SCHEMA-001", "severity": "error", "resultStatus": "error", "summary": ANCHOR,
                "source": {"kind": "file", "workspaceId": None, "path": path, "key": "language"}}
    return {"code": "SPEC-VERIFY-BLOCKED-002", "severity": "error", "resultStatus": "blocked",
            "summary": "検証対象がありません", "source": {"kind": "invocation"}}


def reviewed_result(identifier):
    case = CASES[identifier]
    # 単一ワークスペースの`revision`は、Git不在とコミットのないリポジトリだけ`null`（結果・診断・終了コード §2）。
    # `dirty`は実行時の作業ツリーの状態で、レポートの保存より前に求める（既存のレポートは基準版にある）。
    revision = {"commit": COMMIT, "dirty": bool(case["untracked"])} if case["git"] == "committed" else None
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": reference_status(case["stop"]), "scope": "all",
        "workspace": {"id": None if case["stop"] == "anchor" else "root", "path": "."},
        "targetResults": [], "revision": revision, "commands": [], "durationMs": 0,
        "diagnostics": [diagnostic(case["stop"])],
    }


def reviewed_effects(identifier, state):
    effects = {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}
    if CASES[identifier]["report"]:
        effects["policy"] = "explicit-report"
        effects["report"] = {"directory": REPORT_DIRECTORY, "createdCount": 1,
                             "namePattern": NAME_PATTERN, "temporaryFilesRemaining": 0}
    return effects


# --- 参照計算 --------------------------------------------------------------------------------

def default_targets(requirements):
    """引数なしの`verify`の検証対象。この群のcorpusはREQだけを持つので、`approved`のREQの件数である（`verify` §3）。"""
    count = 0
    for text in requirements:
        frontmatter, _ = digest_crosscheck.split_document(text)
        if frontmatter.get("status") == "approved":
            count += 1
    return count


def git_state(repository):
    """準備手順の後のGitの状態: (コミットがあるか, 作業ツリーに変更または未追跡のファイルがあるか)。Gitがなければ`None`。"""
    if not (repository / ".git").exists():
        return None
    try:
        git(repository, "rev-parse", "--verify", "-q", "HEAD")
        committed = True
    except subprocess.CalledProcessError:
        committed = False
    dirty = bool(git(repository, "status", "--porcelain=v1", "--untracked-files=all").strip())
    return committed, dirty


def reference_expected(config_text, requirements, git_value, report):
    """参照計算: 設定の本文、REQの本文、Gitの状態、`--report`の有無から、停止の種類、状態、終了コード、診断のコード、
    `revision`の有無と`dirty`、レポートの件数を導く。

    - 設定が止まれば（構文の不正、スキーマのメジャーバージョンの非対応の順に分類）、その診断の1件だけを返す。
    - 設定が止まらず、検証対象が0件なら`SPEC-VERIFY-BLOCKED-002`の1件だけ。検証対象があるなら、この群の対象外である。
    - `revision`は、コミットのあるリポジトリだけ`commit`と`dirty`を持つ。Git不在とコミットのないリポジトリは`null`。
    - レポートは、状態にかかわらず、`--report`があるときだけ1件を保存する。
    """
    stop = classify_root_config(config_text)
    if stop is not None:
        kind = stop[0]
        code, status = "SPEC-CONFIG-SCHEMA-001", ("error" if kind == "anchor" else "blocked")
    elif default_targets(requirements) == 0:
        kind, code, status = None, "SPEC-VERIFY-BLOCKED-002", "blocked"
    else:
        raise ValueError("検証対象が0件でも、設定が止まってもいません")
    revision = None
    if git_value is not None and git_value[0]:
        revision = {"dirty": git_value[1]}
    return {"stop": kind, "code": code, "status": status, "exit": EXIT_BY_STATUS[status],
            "revision": revision, "reports": 1 if report else 0,
            "workspaceId": None if kind == "anchor" else "root"}


def check_against_reference(identifier, result, manifest, repository):
    case = CASES[identifier]
    config = (repository / CONFIG_PATH).read_text(encoding="utf-8")
    requirements = [path.read_text(encoding="utf-8") for path in sorted(repository.glob(".spec/requirements/*.md"))]
    reference = reference_expected(config, requirements, git_state(repository), "--report" in manifest["invocation"]["argv"])
    if reference["stop"] != case["stop"]:
        raise ValueError("停止の種類が設定の本文からの参照計算と異なります")
    if [item["code"] for item in result["diagnostics"]] != [reference["code"]]:
        raise ValueError("診断が参照計算と異なります")
    if (result["status"], manifest["expect"]["exitCode"]) != (reference["status"], reference["exit"]):
        raise ValueError("状態または終了コードが参照計算と異なります")
    if manifest["expect"]["reportFileCount"] != reference["reports"]:
        raise ValueError("レポートの件数が参照計算と異なります")
    if result["workspace"] != {"id": reference["workspaceId"], "path": "."}:
        raise ValueError("ワークスペースが参照計算と異なります")
    if (result["revision"] is None) != (reference["revision"] is None):
        raise ValueError("`revision`の有無が参照計算と異なります")
    if result["revision"] is not None and result["revision"]["dirty"] != reference["revision"]["dirty"]:
        raise ValueError("`revision.dirty`が作業ツリーの状態からの参照計算と異なります")
    if result["targetResults"] or result["commands"]:
        raise ValueError("早期に返す結果は検証対象もコマンドも持ちません")


def check_conditions(identifier, repository, manifest):
    """原因の構成を、散文ではなく準備手順の後の入力とGitの状態から確かめる。"""
    case = CASES[identifier]
    state = git_state(repository)
    if case["git"] == "absent":
        if state is not None or manifest["invocation"]["env"] != GIT_ABSENT_ENV:
            raise ValueError("Git不在のケースはGitのメタデータがなく、実行ファイルを見つけられない環境である必要があります")
    elif state is None or state[0] != (case["git"] == "committed"):
        raise ValueError("コミットの有無が期待と異なります")
    elif case["git"] == "committed" and state[1] != case["untracked"]:
        raise ValueError("作業ツリーの変更の有無が期待と異なります")
    # 設定の原因は1か所だけである。それ以外は、停止しない設定と同じである。
    text = (repository / CONFIG_PATH).read_text(encoding="utf-8")
    original = {"schema": 'schemaVersion: "2.0"', "anchor": "language: &label ja"}.get(case["stop"])
    if original is not None:
        restored = {"schema": 'schemaVersion: "1.0"', "anchor": "language: ja"}[case["stop"]]
        if text.count(original) != 1 or text.replace(original, restored) != digest_reference.CONFIG:
            raise ValueError("設定は、原因の1か所以外が停止しない設定と同じである必要があります")
    elif text != digest_reference.CONFIG:
        raise ValueError("停止しないケースの設定が、停止しない設定と異なります")
    existing = repository / EXISTING_REPORT
    if not existing.is_file() or existing.read_bytes() != report_absent_fixtures.EXISTING_REPORT_BODY:
        raise ValueError("既存のレポートがないと、排他的な作成を検査できません")


def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = root / "single" / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / RESULT_FILE).write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-verify-stop-revision-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe_state(manifest, repository, external)
        (fixture / "side-effects.json").write_text(_dump(reviewed_effects(identifier, state)))


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / RESULT_FILE).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for key, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[key].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            if effects != reviewed_effects(identifier, effects["before"]):
                raise ValueError("副作用の期待値がレビュー済みのポリシーと異なります")
            entries = {path.relative_to(fixture / "repo").as_posix(): path.read_bytes()
                       for path in (fixture / "repo").rglob("*") if path.is_file() or path.is_symlink()}
            if entries != reviewed_inputs(identifier):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if {path.relative_to(fixture).as_posix() for path in (fixture / "expected").glob("*")} != {RESULT_FILE}:
                raise ValueError("期待値のファイルがレビュー済みの集合と異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("既に存在したパスはすべて不変である必要があります")
            if CASES[identifier]["report"]:
                created = effects["report"]
                if created["createdCount"] != manifest["expect"]["reportFileCount"] or created["temporaryFilesRemaining"] != 0:
                    raise ValueError("作成したレポートの件数がマニフェストと異なります")
                if EXISTING_REPORT not in effects["before"]["repository"]:
                    raise ValueError("既存のレポートがないと排他的な作成を検査できません")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-verify-stop-revision-") as temporary:
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
                    check_conditions(identifier, repository, manifest)
                    check_against_reference(identifier, result, manifest, repository)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 1, "status": "Passed" if not errors else "Failed", "errors": errors}
