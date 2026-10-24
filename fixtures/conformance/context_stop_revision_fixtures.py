"""`context`の早期に返す結果の`revision`を固定する（Coreの公開操作は実行しない）。

実装の確認事項C45に対応する。`context`は、コンテキスト一式を作る前に結果を返す場合がある。設定がない、設定の停止、起点がない、
強い関係の検査の失敗、閉包の上限の超過、集合外の`--expand`、提示の絶対上限の超過、`--expect-digest`の不一致である。
この早期に返す結果も、ほかの`context`の結果と同じ`revision`の規則に従う。

- `revision`（結果・診断・終了コード §2）: `context`の`null`でないオブジェクトは、40桁の小文字16進数の`commit`と真偽値の`dirty`だけを持つ。
  単一ワークスペースでGit不在、またはコミットのないリポジトリだけ`null`とする。`dirty`は実行時の作業ツリーの状態である。
  `context`が成功した場合だけ`revision`を返す、という規則はない。

この群は、`revision`以外の期待値を既存のfixtureから引き継ぐ。既存のfixtureは、準備手順がコミットを作らない（コミットのないリポジトリ）ので、
`revision: null`が正しい対照である。この群は、同じ入力・同じ起動に、Gitの状態だけを加える。期待値の`revision`以外（状態、終了コード、
診断、`resolution`、`contextDigest`）は、元のfixtureがレビュー済みの値と一致する必要がある。診断の文言は新しく足さない。

| fixture | 元のfixture | 原因（早期に返す結果） | Git | 期待 |
|---|---|---|---|---|
| `SINGLE-166-01` | `SINGLE-152` | 設定がない | コミットあり、クリーン | `blocked`／2、`revision`は`dirty: false` |
| `SINGLE-166-02` | `SINGLE-150` | 設定の停止（型の不正） | コミットあり、クリーン | `error`／3、`workspace.id`は`null`、`revision`あり |
| `SINGLE-166-03` | `SINGLE-050` | 起点がない | コミットあり、クリーン | `failed`／1、`revision`あり |
| `SINGLE-166-04` | `SINGLE-020`の入力 | 強い関係の参照切れ（展開は誤りを返さない） | コミットあり、クリーン | `failed`／1、`revision`あり |
| `SINGLE-166-05` | `SINGLE-148` | 状態の診断と型制約の診断が重なる | コミットあり、クリーン | `failed`／1、`revision`あり |
| `SINGLE-166-06` | `SINGLE-048-01` | 閉包の文書数の上限の超過 | コミットあり、クリーン | `blocked`／2、`revision`あり |
| `SINGLE-166-07` | `SINGLE-047` | 集合外の`--expand` | コミットあり、クリーン | `failed`／1、`revision`あり、`contextDigest`は元のまま |
| `SINGLE-166-08` | `SINGLE-046` | `--expect-digest`の不一致 | コミットあり、クリーン | `blocked`／2、`revision`あり、`contextDigest`は元のまま |
| `SINGLE-166-09` | `SINGLE-050` | 起点がない | コミットあり、未追跡のファイルあり | `revision`は`dirty: true` |
| `SINGLE-166-10` | `SINGLE-020`の入力 | 強い関係の参照切れ | コミットなし（ステージのみ） | `revision: null` |
| `SINGLE-166-11` | `SINGLE-050` | 起点がない | Git不在 | `revision: null` |

提示の絶対上限の超過（`SINGLE-049`）は、入力が約1 MiBあるので、この群に複製しない（単体試験で確かめる）。

期待値の根拠は規範文（結果・診断・終了コード §2・§3・§5、`context` §3、診断レジストリ）と、このモジュールの参照計算だけである。
参照計算は、準備手順の後のGitの状態（コミットの有無と作業ツリーの変更の有無）から`revision`の有無と`dirty`を導く。
Coreの出力は期待値の根拠にしない。
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from .harness import git, setup
from .initial_fixtures import compare_state
from .multi_catalog_fixtures import observe_state

HERE = Path(__file__).resolve().parent
SINGLE = HERE / "single"
RESULT_FILE = "expected/context.json"
NOTES_PATH = "docs/notes.md"
GIT_ABSENT_ENV = {"PATH": "/dev/null"}
COMMIT = "0" * 40
EXIT_BY_STATUS = {"passed": 0, "passed_with_warnings": 0, "failed": 1, "blocked": 2, "error": 3}
EMPTY_BUCKETS = {name: {key: [] for key in ("total", "addressed", "tested", "unaddressed", "untested")}
                 for name in ("must", "should", "may")}
# `SINGLE-020`（`check`）がレビュー済みの診断。`SINGLE-166-04`は、同じ入力を`context`で解決する。
RELATION_MISSING_SOURCE = "SINGLE-020"
RELATION_MISSING = {
    "code": "SPEC-RELATION-MISSING-001", "severity": "error", "resultStatus": "failed",
    "summary": "強い関係の参照先が存在しません",
    "source": {"kind": "file", "workspaceId": "root", "path": ".spec/requirements/REQ-001.md", "key": "relations.requires"},
    "evidence": "REQ-999",
}

# base: 期待値を引き継ぐ元のfixture。`None`は、元のfixtureがない参照切れの入力（`RELATION_MISSING_SOURCE`）。
# git: `committed`（コミットあり）、`staged`（ステージのみでコミットなし）、`absent`（Git不在）。
# untracked: 基準版のコミットに含めない未追跡のファイルを作業ツリーに置く（`dirty: true`を作る）。
CASES = {
    "SINGLE-166-01": dict(base="SINGLE-152", git="committed", untracked=False,
                          description="設定がないcontextが、コミットがあればrevisionを返す"),
    "SINGLE-166-02": dict(base="SINGLE-150", git="committed", untracked=False,
                          description="設定の型が不正で停止したcontextが、コミットがあればrevisionを返す"),
    "SINGLE-166-03": dict(base="SINGLE-050", git="committed", untracked=False,
                          description="起点がないcontextが、コミットがあればrevisionを返す"),
    "SINGLE-166-04": dict(base=None, git="committed", untracked=False,
                          description="強い関係の参照先がないcontextが、コミットがあればrevisionを返す"),
    "SINGLE-166-05": dict(base="SINGLE-148", git="committed", untracked=False,
                          description="状態の診断と型制約の診断が重なるcontextが、コミットがあればrevisionを返す"),
    "SINGLE-166-06": dict(base="SINGLE-048-01", git="committed", untracked=False,
                          description="閉包の文書数の上限を超えたcontextが、コミットがあればrevisionを返す"),
    "SINGLE-166-07": dict(base="SINGLE-047", git="committed", untracked=False,
                          description="解決集合外のexpandを拒否したcontextが、コミットがあればrevisionを返す"),
    "SINGLE-166-08": dict(base="SINGLE-046", git="committed", untracked=False,
                          description="expect-digestが不一致のcontextが、コミットがあればrevisionを返す"),
    "SINGLE-166-09": dict(base="SINGLE-050", git="committed", untracked=True,
                          description="起点がないcontextのrevisionは、作業ツリーに未追跡のファイルがあればdirtyがtrueになる"),
    "SINGLE-166-10": dict(base=None, git="staged", untracked=False,
                          description="コミットのないリポジトリで強い関係の参照先がないcontextは、revisionがnullになる"),
    "SINGLE-166-11": dict(base="SINGLE-050", git="absent", untracked=False,
                          description="Git不在で起点がないcontextは、revisionがnullになる"),
}


# --- 元のfixture ------------------------------------------------------------------------------

def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_of(identifier):
    """入力と起動を引き継ぐ元のfixtureのID。"""
    return CASES[identifier]["base"] or RELATION_MISSING_SOURCE


def source_inputs(source):
    root = SINGLE / source / "repo"
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def source_manifest(source):
    return _load(SINGLE / source / "manifest.json")


def base_body(identifier):
    """`revision`を除いた期待結果。元のfixtureがレビュー済みの結果（`revision`は`null`）か、参照切れの結果である。"""
    base = CASES[identifier]["base"]
    if base is not None:
        body = _load(SINGLE / base / RESULT_FILE)
        if body["revision"] is not None:
            raise ValueError(f"{base}は、コミットのないリポジトリの対照として`revision: null`である必要があります")
    else:
        body = relation_missing_body()
    body.pop("revision")
    return body


def relation_missing_body():
    """`SINGLE-020`の入力（REQ-001が存在しないREQ-999を`requires`する）を`context REQ-001`で解決した結果。
    対象展開は誤りを返さず、強い関係の検査だけが失敗する。`contextDigest`は`null`、`unresolvedStrongRelations`は1
    （`context` §3、診断レジストリ、`MULTI-038-08`と同じ形）。"""
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "failed", "purpose": "interpret",
        "workspace": {"id": "root", "path": "."}, "roots": ["REQ-001"],
        "contextDigest": None, "revision": None,
        "resolution": {"complete": False, "documentCount": 0, "unresolvedStrongRelations": 1},
        "projection": {"detail": "standard", "expanded": []},
        "documents": [], "constraintLedger": {"statements": []},
        "coverage": {**copy.deepcopy(EMPTY_BUCKETS), "adjacent": []},
        "durationMs": 0, "diagnostics": [copy.deepcopy(RELATION_MISSING)],
    }


def revision_for(git_value):
    """参照計算: コミットのあるリポジトリだけ`commit`と`dirty`を持つ。Git不在とコミットのないリポジトリは`null`。"""
    if git_value is None or not git_value[0]:
        return None
    return {"commit": COMMIT, "dirty": git_value[1]}


def plan_state(identifier):
    """準備手順の計画から導く、Gitの状態: (コミットがあるか, 作業ツリーに変更または未追跡のファイルがあるか)。Git不在は`None`。"""
    case = CASES[identifier]
    if case["git"] == "absent":
        return None
    return case["git"] == "committed", bool(case["untracked"])


# --- 入力 -------------------------------------------------------------------------------

def reviewed_inputs(identifier):
    inputs = source_inputs(source_of(identifier))
    if CASES[identifier]["untracked"]:
        inputs[NOTES_PATH] = "# 覚え書き\n\n仕様文書ではない。\n".encode()
    return inputs


def reviewed_manifest(identifier):
    case = CASES[identifier]
    if case["base"] is not None:
        manifest = source_manifest(case["base"])
        if manifest["setup"] != {"git": True, "operations": []} or manifest["invocation"]["env"] != {}:
            raise ValueError(f"{case['base']}は、コミットのないGitのリポジトリで環境変数なしの対照である必要があります")
    else:
        # `SINGLE-020`の入力を`context REQ-001`で解決する（目的は省略時の`interpret`）。
        manifest = {
            "fixtureId": identifier, "description": "",
            "setup": {"git": True, "operations": []},
            "invocation": {"runner": "bitz", "cwd": ".", "argv": ["context", "REQ-001", "--format", "json"], "env": {}},
            "expect": {"status": "failed", "exitCode": 1, "stdout": "json", "resultFile": RESULT_FILE, "reportFileCount": 0},
        }
    manifest = copy.deepcopy(manifest)
    manifest["fixtureId"] = identifier
    manifest["description"] = case["description"]
    if case["git"] == "absent":
        manifest["setup"] = {"git": False, "operations": []}
        manifest["invocation"]["env"] = dict(GIT_ABSENT_ENV)
    elif case["git"] == "staged":
        manifest["setup"] = {"git": True, "operations": [{"op": "stage", "paths": ["."]}]}
    else:
        # 未追跡のファイルは基準版のコミットに含めない。
        manifest["setup"] = {"git": True, "baseCommit": {"message": "base", "paths": [".spec"] if case["untracked"] else ["."]},
                             "operations": []}
    return manifest


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def reviewed_result(identifier):
    # 単一ワークスペースの`revision`は、Git不在とコミットのないリポジトリだけ`null`（結果・診断・終了コード §2）。
    result = base_body(identifier)
    result["revision"] = revision_for(plan_state(identifier))
    return result


def reviewed_effects(identifier, state):
    return {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}


# --- 参照計算 --------------------------------------------------------------------------------

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


def reference_expected(identifier, git_value):
    """参照計算: 元のfixtureの`revision`以外の期待値に、準備手順の後のGitの状態から導く`revision`を加える。"""
    result = base_body(identifier)
    result["revision"] = revision_for(git_value)
    return result


def check_against_reference(identifier, result, manifest, repository):
    reference = reference_expected(identifier, git_state(repository))
    if result != reference:
        differing = sorted(key for key in set(result) | set(reference) if result.get(key) != reference.get(key))
        raise ValueError(f"完全結果が参照計算と異なります（{', '.join(differing)}）")
    if (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (result["status"], EXIT_BY_STATUS[result["status"]]):
        raise ValueError("状態または終了コードが参照計算と異なります")
    if result["documents"]:
        raise ValueError("早期に返す結果は、コンテキスト一式の文書を持ちません")


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
    # 元のfixtureの起動（`argv`）を変えない。原因は元の入力と起動にある。
    if case["base"] is not None and manifest["invocation"]["argv"] != source_manifest(case["base"])["invocation"]["argv"]:
        raise ValueError("起動が元のfixtureと異なります")
    if case["base"] is None:
        # 参照切れの診断は、元の入力を`check`で検査した`SINGLE-020`のレビュー済みの診断と同じである。
        diagnostics = _load(SINGLE / RELATION_MISSING_SOURCE / "expected/check.json")["diagnostics"]
        if diagnostics != [RELATION_MISSING]:
            raise ValueError("参照切れの診断が、レビュー済みの診断と異なります")
    elif _load(SINGLE / case["base"] / RESULT_FILE)["diagnostics"] != reviewed_result(identifier)["diagnostics"]:
        raise ValueError("診断が元のfixtureと異なります")


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
        with tempfile.TemporaryDirectory(prefix="bitz-context-stop-revision-") as temporary:
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
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-context-stop-revision-") as temporary:
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
