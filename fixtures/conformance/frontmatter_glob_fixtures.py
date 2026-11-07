"""フロントマターのパスが禁止するglobの文字`*?[]`を固定する（Coreの公開操作は実行しない）。

実装の確認事項C43とADR-051の追加に対応する。修正前のCoreは、メンバーのパス、除外のパス、`verify.commands.<名前>.cwd`では`*?[]`の4つを拒否していたが、
フロントマターのパス（`implements`、`changes`、`tests[].path`）は閉じ括弧`]`を除く`*?[`の3つしか拒否せず、`]`だけを含むパスを受理した。
ユーザーの決定により、規範は次のとおりに「globの文字`*?[]`」と明記された。

- ワークスペース・設定仕様 §9: 仕様文書に記録するパスは、絶対パス、`..`、NUL、globの文字`*?[]`、ルートの外のシンボリックリンクを禁止する。
- 文書種別・本文テンプレート（`changes`）: globの文字`*?[]`、絶対パス、`..`を禁止する。
- 複合ワークスペース仕様 §2・§5.1: メンバーのパスと除外のパスも「globの文字`*?[]`」。
- `frontmatter.schema.json`の`pathString`のパターンは`*?[]`を拒否する。

フロントマターの拒否は`SPEC-FM-SCHEMA-001`（`error`／`failed`）で、診断の`source`は`{kind: file, workspaceId: root, path: <仕様文書>, key: <フィールド>}`、
文書をスキップするので`checkedDocumentCount`と`checkedStatementCount`は0になる（`SINGLE-117-03`・`SINGLE-120-04`と同じ形）。
診断の`summary`は、承認済みの文言「フロントマターのフィールド{key}のパスの形式が不正です」を使う
（`Coreの出力文言のレビュー記録.md`の2026-11-04の節、C85。型の不正の文言#48〜#49とは区別する）。

| fixture | フィールド | パス | 期待 |
|---|---|---|---|
| `SINGLE-171-01` | REQの`implements` | `src/a]b.py`（閉じ括弧だけ。実ファイルあり） | `failed`／1。キー`implements`。修正前のCoreは`passed`／0 |
| `SINGLE-171-02` | TASKの`changes` | `src/a]b.py`（実ファイルあり） | `failed`／1。キー`changes`。修正前のCoreは`passed`／0 |
| `SINGLE-171-03` | REQの`tests[0].path` | `tests/t]x.py`（実ファイルあり） | `failed`／1。キー`tests[0].path`。修正前のCoreは`passed`／0 |
| `SINGLE-171-04` | REQの`implements` | `src/a*b.py`（`*`） | `failed`／1。キー`implements`。修正前のCoreも拒否する（対照） |
| `SINGLE-171-05` | TASKの`changes` | `src/a?b.py`（`?`） | `failed`／1。キー`changes`。修正前のCoreも拒否する（対照） |
| `SINGLE-171-06` | REQの`tests[0].path` | `tests/t[x.py`（`[`） | `failed`／1。キー`tests[0].path`。修正前のCoreも拒否する（対照） |
| `SINGLE-171-07` | REQの`implements`と`tests[0].path` | `*?[]`以外の記号`(){}!`を含む（実ファイルあり） | `passed`／0。診断なし |
| `SINGLE-171-08` | TASKの`changes` | `*?[]`以外の記号`(){}!`を含む（実ファイルあり） | `passed`／0。診断なし |

`04`〜`06`のC85の修正前のCoreは、拒否はするが`summary`が旧い文言（型の不正と同じ）なので、期待と一致しない。
`04`〜`06`は、パスの字句の検査が実在の検査より前なので、実ファイルを置かない（ファイル名に`*?[`を含む入力は、シェルやツールが解釈しうるので避ける）。
`01`〜`03`は、修正前のCoreが`]`以外の原因（実ファイルの不在、ほかの不正な字句）で非成功にならないよう、実ファイルを基準版のコミットへ入れる。
実ファイルがなければ、`approved`のREQの`implements`と`tests[].path`は不在の診断を返す（関係・トレースモデル §9）。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .document_fixtures import AC, INTENT, VERIFICATION
from .harness import git, setup
from .initial_fixtures import CONFIGS, compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
TITLE = "フロントマターのパス"
CODE_PATH = "src/a]b.py"
STAR_PATH = "src/a*b.py"
QUESTION_PATH = "src/a?b.py"
BRACKET_TEST_PATH = "tests/t[x.py"
CLOSE_TEST_PATH = "tests/t]x.py"
SYMBOL_CODE_PATH = "src/a(1){2}!.py"
SYMBOL_TEST_PATH = "tests/t(1){2}!.py"
CODE_CONTENT = b"# implementation\n"
TEST_CONTENT = b'raise RuntimeError("check must not run test code")\n'
TASK_BODY = "## Objective\n\nパスの記号を確認する。\n\n## Completion Criteria\n\n検査が完了する。\n"

GLOB_CHARACTERS = "*?[]"
# 修正前のCoreが拒否していた、閉じ括弧を除く3つ。
OLD_GLOB_CHARACTERS = "*?["
# 承認済みの文言（`Coreの出力文言のレビュー記録.md`の2026-11-04の節、C85。ADR-062 Decision 2）。
# パスの字句の拒否は、型の不正（#48: `…は文字列が必要です`、#49: `…は文字列の配列が必要です`）と区別する。
# 旧い文言（修正前のCoreの出力）は、型の不正と同じ文言で、監査の回帰試験が拒否する。
SUMMARY_TEMPLATE = "フロントマターのフィールド{key}のパスの形式が不正です"
SUMMARIES = {key: SUMMARY_TEMPLATE.format(key=key) for key in ("implements", "changes", "tests[0].path")}
KINDS = {"REQ": ("requirements", "reqFrontmatter", "approved"), "TASK": ("tasks", "taskFrontmatter", "open")}

# id: dict(kind〈文書の種類〉, field〈対象のフロントマターのフィールド〉, paths〈そのフィールドのパス〉,
#          rejected〈フロントマターを拒否するか〉, defective〈修正前のCoreが違う結果を返すか〉, files〈実ファイルを置くパス〉, description)
CASES = {
    "SINGLE-171-01": dict(kind="REQ", field="implements", paths=[CODE_PATH], rejected=True, defective=True, files=[CODE_PATH],
                          description="implementsに閉じ括弧だけを含むパスがあれば、globの文字としてフロントマターのスキーマが拒否する"),
    "SINGLE-171-02": dict(kind="TASK", field="changes", paths=[CODE_PATH], rejected=True, defective=True, files=[CODE_PATH],
                          description="changesに閉じ括弧だけを含むパスがあれば、globの文字としてフロントマターのスキーマが拒否する"),
    "SINGLE-171-03": dict(kind="REQ", field="tests", paths=[CLOSE_TEST_PATH], rejected=True, defective=True, files=[CLOSE_TEST_PATH],
                          description="tests[].pathに閉じ括弧だけを含むパスがあれば、globの文字としてフロントマターのスキーマが拒否する"),
    "SINGLE-171-04": dict(kind="REQ", field="implements", paths=[STAR_PATH], rejected=True, defective=False, files=[],
                          description="対照: implementsにアスタリスクを含むパスは、globの文字として拒否する"),
    "SINGLE-171-05": dict(kind="TASK", field="changes", paths=[QUESTION_PATH], rejected=True, defective=False, files=[],
                          description="対照: changesに疑問符を含むパスは、globの文字として拒否する"),
    "SINGLE-171-06": dict(kind="REQ", field="tests", paths=[BRACKET_TEST_PATH], rejected=True, defective=False, files=[],
                          description="対照: tests[].pathに開き括弧を含むパスは、globの文字として拒否する"),
    "SINGLE-171-07": dict(kind="REQ", field="both", paths=[SYMBOL_CODE_PATH, SYMBOL_TEST_PATH], rejected=False, defective=False,
                          files=[SYMBOL_CODE_PATH, SYMBOL_TEST_PATH],
                          description="対照: globの文字以外の記号を含むimplementsとtests[].pathは受理する"),
    "SINGLE-171-08": dict(kind="TASK", field="changes", paths=[SYMBOL_CODE_PATH], rejected=False, defective=False, files=[SYMBOL_CODE_PATH],
                          description="対照: globの文字以外の記号を含むchangesは受理する"),
}


# --- パスの字句の参照計算（Coreにも`frontmatter.schema.json`にも依存しない） ------------------

def path_rejected(path, characters=GLOB_CHARACTERS):
    """仕様文書に記録するパスの字句の違反（ワークスペース・設定仕様 §9、文書・フロントマター・状態仕様のスキーマ）。

    空、絶対パス、制御文字（U+0000〜U+001F、U+007F）、globの文字、空のセグメント（`a//b`と末尾の`/`）、`.`または`..`のセグメントを違反とする
    （空のセグメントと制御文字は、確認事項C101・C102の規範の明記による。`path_lexical_fixtures.violations`が詳細な参照計算）。
    `characters`は、globの文字とみなす集合である。TASKの`changes`のディレクトリの接頭辞の末尾の`/`は、この関数の対象外である（`SINGLE-171`は使わない）。
    """
    if not isinstance(path, str) or path == "" or path.startswith("/") or any(ord(character) < 0x20 or ord(character) == 0x7F for character in path):
        return True
    if any(character in path for character in characters):
        return True
    return any(segment in ("", ".", "..") for segment in path.split("/"))


def single_cause(path):
    """パスが、globの文字を1文字だけ含み、それを除けば字句の違反がないこと（ほかの原因を混ぜない）。"""
    present = [character for character in GLOB_CHARACTERS if character in path]
    return len(present) == 1 and not path_rejected(path.replace(present[0], "x"))


# --- 入力 -------------------------------------------------------------------------------

def spec_path(identifier):
    directory, _, _ = KINDS[CASES[identifier]["kind"]]
    return f".spec/{directory}/{fields(identifier)['id']}.md"


def fields(identifier):
    """デコードした後のフロントマターのフィールド。"""
    case = CASES[identifier]
    kind = case["kind"]
    _, _, status = KINDS[kind]
    value = {"id": f"{kind}-001", "title": TITLE, "status": status}
    if case["field"] == "implements":
        value["implements"] = list(case["paths"])
    elif case["field"] == "changes":
        value["changes"] = list(case["paths"])
    elif case["field"] == "tests":
        value["tests"] = [{"path": case["paths"][0], "covers": ["REQ-001:AC-01"], "command": "default"}]
    else:
        value["implements"] = [case["paths"][0]]
        value["tests"] = [{"path": case["paths"][1], "covers": ["REQ-001:AC-01"], "command": "default"}]
    return value


def reviewed_inputs(identifier):
    """`repo/`の全入力。パス→バイト列。各フィールドを、JSON構文のYAMLのフロー値として1行ずつ書く（`frontmatter_boundary_fixtures`と同じ）。"""
    case = CASES[identifier]
    value = fields(identifier)
    header = "".join(f"{key}: {json.dumps(item, ensure_ascii=False)}\n" for key, item in value.items())
    body = f"# {value['id']} {TITLE}\n\n" + (INTENT + AC + VERIFICATION if case["kind"] == "REQ" else TASK_BODY)
    config = CONFIGS["SINGLE-001"].encode()
    if "tests" in value:
        config += b"verify:\n  commands:\n    default:\n      argv: [\"/bin/true\"]\n      cwd: .\n"
    inputs = {".spec/bitz.yaml": config, spec_path(identifier): ("---\n" + header + "---\n\n" + body).encode()}
    for path in case["files"]:
        inputs[path] = TEST_CONTENT if path.startswith("tests/") else CODE_CONTENT
    return inputs


def key_of(identifier):
    """診断の`source.key`。`tests`はパスを持つ要素の添字まで指す（`SINGLE-117-03`の`tests[0].covers`と同じ形）。"""
    field = CASES[identifier]["field"]
    return "tests[0].path" if field == "tests" else field


def reviewed_manifest(identifier):
    rejected = CASES[identifier]["rejected"]
    return {"fixtureId": identifier, "description": CASES[identifier]["description"],
            "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
            "invocation": {"runner": "bitz", "cwd": ".", "argv": ["check", "--full", "--base", "HEAD", "--format", "json"], "env": {}},
            "expect": {"status": "failed" if rejected else "passed", "exitCode": 1 if rejected else 0, "stdout": "json",
                       "resultFile": "expected/check.json", "reportFileCount": 0}}


def reviewed_result(identifier):
    case = CASES[identifier]
    rejected = case["rejected"]
    status = "failed" if rejected else "passed"
    diagnostics = []
    if rejected:
        key = key_of(identifier)
        diagnostics.append({"code": "SPEC-FM-SCHEMA-001", "severity": "error", "resultStatus": status, "summary": SUMMARIES[key],
                            "source": {"kind": "file", "workspaceId": "root", "path": spec_path(identifier), "key": key}})
    # 拒否した文書はスキップし、件数に数えない。受理したREQは規範文1件、TASKは0件（`SINGLE-115-01`・`SINGLE-115-04`）。
    documents = 0 if rejected else 1
    statements = 1 if not rejected and case["kind"] == "REQ" else 0
    return {"schemaVersion": "1.0", "operation": "check", "status": status, "scope": "full",
            "workspace": {"id": "root", "path": "."},
            "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
            "checkedDocumentCount": documents, "checkedStatementCount": statements, "durationMs": 0, "diagnostics": diagnostics}


# --- 参照計算と入力の構成の検査 --------------------------------------------------------------

def decode_header(text):
    """フロントマターの各行を`json.loads`で独立にデコードする。"""
    header = text.split("---\n")[1]
    return {key: json.loads(item) for key, item in (line.split(": ", 1) for line in header.splitlines())}


def listed_paths(decoded):
    """フロントマターのフィールドから、パスを列挙する（`(フィールド, パス)`の並び）。"""
    result = [("implements", path) for path in decoded.get("implements", [])]
    result += [("changes", path) for path in decoded.get("changes", [])]
    result += [("tests", test["path"]) for test in decoded.get("tests", [])]
    return result


def check_conditions(identifier, repository):
    """準備手順の後のリポジトリの実体から、参照計算が期待と一致し、意図した1つの原因だけを持つことを確かめる。"""
    case = CASES[identifier]
    decoded = decode_header((repository / spec_path(identifier)).read_text(encoding="utf-8"))
    paths = listed_paths(decoded)
    verdicts = [path_rejected(path) for _, path in paths]
    if any(verdicts) != case["rejected"]:
        raise ValueError("パスの字句の参照計算が期待の受理と一致しません")
    if case["rejected"]:
        # 拒否するパスは、globの文字1つだけが原因である。実ファイルの不在や`..`などを重ねない。
        if not all(single_cause(path) for (_, path), verdict in zip(paths, verdicts) if verdict):
            raise ValueError("拒否するパスがglobの文字1つだけを原因としていません")
        if len(paths) != 1:
            raise ValueError("拒否するケースのパスは1件である必要があります")
    # 修正前のCoreの読み方（`*?[`の3つ）は、欠陥のあるケースだけ結果が異なる。
    old = any(path_rejected(path, OLD_GLOB_CHARACTERS) for _, path in paths)
    if (old != case["rejected"]) != case["defective"]:
        raise ValueError("修正前のCoreの欠陥を検出できる入力、または対照の入力ではありません")
    if decoded != fields(identifier):
        raise ValueError("固定したYAMLのフロー値が独立にデコードしたフィールドと異なります")
    if [path for _, path in paths] != case["paths"]:
        raise ValueError("対象のパスがレビュー済みのケースと異なります")
    # 実ファイルは、置くと決めたパスだけを置く。通常のファイルで、基準版のコミットに追跡される。
    tracked = set(git(repository, "ls-files", "-z").decode().split("\0")[:-1])
    for _, path in paths:
        present = (repository / path).is_file() and not (repository / path).is_symlink()
        if present != (path in case["files"]) or (present and path not in tracked):
            raise ValueError("実ファイルの有無がレビュー済みのケースと異なります")
    if case["defective"] and not all((repository / path).is_file() for _, path in paths):
        raise ValueError("欠陥を検出するケースは、パスの実ファイルを置く必要があります")
    # `]`以外の原因を混ぜない: REQの`tests`には、コマンド`default`の定義がある。
    if "tests" in decoded and b"default:" not in (repository / ".spec/bitz.yaml").read_bytes():
        raise ValueError("testsのコマンドの定義がありません")
    status = git(repository, "status", "--porcelain=v1", "--untracked-files=all", "-z")
    if status:
        raise ValueError("作業ツリーは基準版のコミットと同じである必要があります")
    if set(tracked) != set(reviewed_inputs(identifier)):
        raise ValueError("インデックスのパスがレビュー済みの基準版と異なります")
    for path, content in reviewed_inputs(identifier).items():
        if git(repository, "show", "HEAD:" + path) != content or git(repository, "show", ":" + path) != content:
            raise ValueError("`HEAD`またはインデックスのバイト列がレビュー済みの基準版と異なります")


def schema_verdict(identifier, schema):
    """`frontmatter.schema.json`の文書種別ごとの定義の合否。"""
    definition = KINDS[CASES[identifier]["kind"]][1]
    validator = Draft202012Validator({"$ref": "#/$defs/" + definition, "$defs": schema["$defs"]})
    return bool(list(validator.iter_errors(fields(identifier))))


# --- 生成と監査 ---------------------------------------------------------------------------------

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
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "expected/check.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-fm-glob-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(
            _dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads(schema_path(root, "frontmatter").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/check.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("マニフェストまたは結果がレビュー済みの単一条件と異なります")
            if {p.name for p in (fixture / "expected").glob("*")} != {"check.json"} or any(
                    (fixture / name).exists() for name in ("changes", "cli-output.json")):
                raise ValueError("期待結果のファイルの構成がレビュー済みの形と異なります")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name] or p.stat().st_mode & 0o111
                                                for name, p in files.items()):
                raise ValueError("入力のバイト列またはファイルモードがレビュー済みのcorpusと異なります")
            if schema_verdict(identifier, schema) != CASES[identifier]["rejected"]:
                raise ValueError("フロントマターのスキーマの判定がレビュー済みの受理と一致しません")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("フロントマターの検査はファイルを書いてはいけません")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-fm-glob-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    check_conditions(identifier, repository)
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run", "references": 2,
            "status": "Passed" if not errors else "Failed", "errors": errors}
