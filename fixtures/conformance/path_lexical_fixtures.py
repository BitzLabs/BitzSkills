"""パスの字句の禁止（空のセグメント、末尾の`/`、制御文字、`.`のセグメント）を固定する（Coreの公開操作は実行しない）。

実装の確認事項C101〜C103とADR-051の追加に対応する。ユーザーの決定（2026-11-04）により、規範は次のとおりに明記された。

- ワークスペース・設定仕様 §9: 仕様文書に記録するパスは、絶対パス、`.`と`..`のセグメント、空のセグメント（`a//b`と末尾の`/`。ただしTASKの`changes`の
  ディレクトリの接頭辞の末尾の`/`1つだけを除く）、NULを含む制御文字（U+0000〜U+001F、U+007F）、globの文字`*?[]`、ルートの外のシンボリックリンクを禁止する。
  字句の違反は`SPEC-FM-SCHEMA-001`とする。
- 同 §6: `cwd`の字句に制御文字を加える。違反は`SPEC-CONFIG-SCHEMA-001`（承認済みの文言「作業ディレクトリのパスの形式が不正です」）。
- 複合ワークスペース仕様 §2: メンバーのパスと除外のパスの字句に制御文字を加える。違反は、メンバーのパスが`SPEC-MULTI-PATH-001`、除外のパスが
  `SPEC-MULTI-CONFIG-001`。§5.1の手順3も同じ。
- `frontmatter.schema.json`: `pathString`は空のセグメント、末尾の`/`、制御文字を拒否し、`changesPathString`（`changes`用）は末尾の`/`1つだけを許す。

修正前のCoreは、フロントマターのパスの空のセグメントと末尾の`/`（C101）、NUL以外の制御文字（C102。`cwd`、メンバーのパス、除外のパスを含む）を受理していた。
`.`のセグメントは、修正前から拒否していたが、規範の禁止の列挙になかった（C103）ので、フロントマターのパスの`.`の拒否を固定する対照を置く。
次の「診断の文言」は、承認済みの文言だけを使う。

| fixture | 操作 | 入力 | 期待 |
|---|---|---|---|
| `SINGLE-173-01` | `check --full --base HEAD` | REQの`implements: ["src//a.py"]`（空のセグメント。実ファイル`src/a.py`あり） | `failed`／1。`SPEC-FM-SCHEMA-001`、キー`implements`。修正前のCoreは`passed`／0 |
| `SINGLE-173-02` | 同上 | REQの`tests[0].path`が`tests/t.py/`（末尾の`/`。実ファイル`tests/t.py`あり） | `failed`／1。キー`tests[0].path`。修正前のCoreは不在の診断 |
| `SINGLE-173-03` | 同上 | TASKの`changes: ["src//"]`（空のセグメント。実ファイル`src/a.py`あり） | `failed`／1。キー`changes`。修正前のCoreは`passed`／0 |
| `SINGLE-173-04` | 同上 | TASKの`changes: ["src/"]`（ディレクトリの接頭辞の末尾の`/`1つ。対照） | `passed`／0。診断なし。修正前のCoreも通る |
| `SINGLE-173-05` | 同上 | REQの`implements: ["src/a\\tb.py"]`（タブ。実ファイルなし） | `failed`／1。キー`implements`。修正前のCoreは不在の診断 |
| `SINGLE-173-06` | 同上 | TASKの`changes: ["src/a\\nb/"]`（改行。`changes`は対象の存在を要求しない） | `failed`／1。キー`changes`。修正前のCoreは`passed`／0 |
| `SINGLE-173-07` | 同上 | REQの`tests[0].path`が`tests/t\\u007f.py`（DEL U+007F。実ファイルなし） | `failed`／1。キー`tests[0].path`。修正前のCoreは不在の診断 |
| `SINGLE-173-08` | 同上 | REQの`implements: ["src/a\\0b.py"]`（NUL。対照） | `failed`／1。キー`implements`。修正前のCoreも拒否する |
| `SINGLE-173-09` | 同上 | REQの`implements: ["src/a b.py"]`（空白U+0020は制御文字ではない。対照。実ファイルあり） | `passed`／0。診断なし。修正前のCoreも通る |
| `SINGLE-173-10` | 同上 | REQの`implements: ["src/./a.py"]`（`.`のセグメント。確認事項C103。対照。実ファイル`src/a.py`あり） | `failed`／1。キー`implements`。修正前のCoreも拒否する |
| `SINGLE-173-11` | `verify REQ-001` | `SINGLE-167-01`の入力の`cwd`だけを`"tests\\t"`（タブ）に替える | `error`／3。`SPEC-CONFIG-SCHEMA-001`（`SINGLE-167-01`と同じ診断）。修正前のCoreは設定の検査を通す |
| `SINGLE-173-12` | `verify REQ-001` | 同上。`cwd`が`"tests\\0"`（NUL。対照） | `error`／3。`SINGLE-167-01`と同じ。修正前のCoreも拒否する |
| `MULTI-060-01` | `check --all-workspaces --base HEAD` | `MULTI-037-09`と同じ入力。`multiWorkspace.exclude`が`["cases\\tx"]`（タブ。除外のパスは実在しなくてよい） | `failed`／1。`MULTI-037-09`と同じ診断（`SPEC-MULTI-CONFIG-001`）。修正前のCoreは`passed`／0 |
| `MULTI-060-02` | 同上 | 同じ設定で、メンバー`web`のパスが`"apps/we\\nb"`（改行。メンバーの実体は置かない） | `failed`／1。`MULTI-037-16`と同じ形で、summaryが「メンバーのパスの形式が不正です」（`SPEC-MULTI-PATH-001`）。修正前のCoreはメンバーの設定の不在 |

パスの字句の違反は、フロントマターが`SPEC-FM-SCHEMA-001`（`error`／`failed`）の1件で、診断の`source`は`{kind: file, workspaceId: root, path: <仕様文書>, key: <フィールド>}`、
文書をスキップするので`checkedDocumentCount`と`checkedStatementCount`は0になる（`SINGLE-171`と同じ形）。診断の`summary`は、承認済みの文言「フロントマターのフィールド{key}のパスの形式が不正です」
（`Coreの出力文言のレビュー記録.md`の2026-11-04の節、C85）である。`cwd`は`SINGLE-167-01`、除外のパスは`MULTI-037-09`、メンバーのパスは`MULTI-037-16`のレビュー済みの結果の形を引き継ぎ、
メンバーのパスだけsummaryを既存の承認済みの文言「メンバーのパスの形式が不正です」に替える。

制御文字を含むパスは、YAMLの二重引用符のエスケープ（`\\t`、`\\n`、`\\0`、`\\u007f`）で書く（YAML 1.2のエスケープで、Coreの部分集合も許す）。生のDELをファイルへ書くと
YAMLの印字可能文字の集合から外れるので、`\\u007f`のエスケープで書く。制御文字を含むファイル名は、シェルやツールが解釈しうるので、リポジトリへ置かない
（`SINGLE-171-04`〜`06`と同じ理由）。そのため、制御文字のケースの修正前のCoreは、パスの字句を通した後の実在の検査で別の診断になるものがある（上の表）。

期待値の根拠は規範文と、このモジュールの参照計算（`violations`）だけである（Coreの出力は根拠にしない）。

規範から決まらず、既存の形を引き継いだ点:
- メンバーのパスの字句の違反のときの結果の形（`check --all-workspaces`の全体事前検査の停止。`workspaces`は空、診断は`SPEC-MULTI-PATH-001`の1件、キー`multiWorkspace.members`）は、
  同じ診断コードの`MULTI-037-16`の形を引き継いだ。
- Stepの割当ては、同じ操作・同じ診断の既存のfixtureに合わせた（フロントマター: Step 2、`cwd`: Step 4、複合ワークスペース: Step 5）。
"""
import copy
import json
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import command_cwd_fixtures as command_cwd
from . import digest_reference, multi_exclude_fixtures as multi_exclude, multi_reference
from .document_fixtures import AC, INTENT, VERIFICATION
from .frontmatter_glob_fixtures import (CODE_CONTENT, KINDS, SUMMARY_TEMPLATE, TASK_BODY, TEST_CONTENT, TITLE, decode_header,
                                        listed_paths)
from .harness import git, setup
from .initial_fixtures import CONFIGS, compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
MEMBER_PATH_SUMMARY = "メンバーのパスの形式が不正です"  # 承認済みの既存の文言（`messages.MULTI_PATH_INVALID`。出力文言のレビュー記録の#108）
GLOB_CHARACTERS = "*?[]"

# id: dict(group, description, ...)。
#   group: `frontmatter`（`check --full`）、`cwd`（`verify`）、`exclude`・`member`（複合ワークスペースの`check --all-workspaces`）。
#   frontmatter: kind〈文書の種類〉, field, paths〈そのフィールドのパス〉, files〈実ファイルを置くパス〉
#   共通: rejected〈字句を拒否するか〉, cause〈拒否する原因。`violations`の名前〉, defective〈修正前のCoreが違う結果を返すか〉, step
CASES = {
    "SINGLE-173-01": dict(group="frontmatter", kind="REQ", field="implements", paths=["src//a.py"], files=["src/a.py"],
                          rejected=True, cause="empty-segment", defective=True, step=2,
                          description="implementsに空のセグメントがあれば、フロントマターのスキーマが拒否する"),
    "SINGLE-173-02": dict(group="frontmatter", kind="REQ", field="tests", paths=["tests/t.py/"], files=["tests/t.py"],
                          rejected=True, cause="trailing-slash", defective=True, step=2,
                          description="tests[].pathの末尾が/であれば、フロントマターのスキーマが拒否する"),
    "SINGLE-173-03": dict(group="frontmatter", kind="TASK", field="changes", paths=["src//"], files=["src/a.py"],
                          rejected=True, cause="empty-segment", defective=True, step=2,
                          description="changesに空のセグメントがあれば、末尾の/1つを許す場合も拒否する"),
    "SINGLE-173-04": dict(group="frontmatter", kind="TASK", field="changes", paths=["src/"], files=["src/a.py"],
                          rejected=False, cause=None, defective=False, step=2,
                          description="対照: changesのディレクトリの接頭辞の末尾の/1つは受理する"),
    "SINGLE-173-05": dict(group="frontmatter", kind="REQ", field="implements", paths=["src/a\tb.py"], files=[],
                          rejected=True, cause="control", defective=True, step=2,
                          description="implementsにタブがあれば、制御文字としてフロントマターのスキーマが拒否する"),
    "SINGLE-173-06": dict(group="frontmatter", kind="TASK", field="changes", paths=["src/a\nb/"], files=[],
                          rejected=True, cause="control", defective=True, step=2,
                          description="changesに改行があれば、制御文字としてフロントマターのスキーマが拒否する"),
    "SINGLE-173-07": dict(group="frontmatter", kind="REQ", field="tests", paths=["tests/t\x7f.py"], files=[],
                          rejected=True, cause="control", defective=True, step=2,
                          description="tests[].pathにDEL(U+007F)があれば、制御文字としてフロントマターのスキーマが拒否する"),
    "SINGLE-173-08": dict(group="frontmatter", kind="REQ", field="implements", paths=["src/a\x00b.py"], files=[],
                          rejected=True, cause="control", defective=False, step=2,
                          description="対照: implementsにNULがあれば、制御文字としてフロントマターのスキーマが拒否する"),
    "SINGLE-173-09": dict(group="frontmatter", kind="REQ", field="implements", paths=["src/a b.py"], files=["src/a b.py"],
                          rejected=False, cause=None, defective=False, step=2,
                          description="対照: implementsの空白(U+0020)は制御文字ではないので受理する"),
    "SINGLE-173-10": dict(group="frontmatter", kind="REQ", field="implements", paths=["src/./a.py"], files=["src/a.py"],
                          rejected=True, cause="dot-segment", defective=False, step=2,
                          description="対照: implementsに.のセグメントがあれば、フロントマターのスキーマが拒否する"),
    "SINGLE-173-11": dict(group="cwd", cwd="tests\t", rejected=True, cause="control", defective=True, step=4,
                          description="cwdにタブがあれば、制御文字として設定の検査が止めverifyはコマンドを起動しない"),
    "SINGLE-173-12": dict(group="cwd", cwd="tests\x00", rejected=True, cause="control", defective=False, step=4,
                          description="対照: cwdにNULがあれば、制御文字として設定の検査が止める"),
    "MULTI-060-01": dict(group="exclude", path="cases\tx", rejected=True, cause="control", defective=True, step=5,
                         description="タブを含む除外のパスを設定不適合にする"),
    "MULTI-060-02": dict(group="member", path="apps/we\nb", rejected=True, cause="control", defective=True, step=5,
                         description="改行を含むメンバーのパスをパスの不適合にする"),
}
SUMMARIES = {key: SUMMARY_TEMPLATE.format(key=key) for key in ("implements", "changes", "tests[0].path")}
FRONTMATTER_KEY = {"implements": "implements", "changes": "changes", "tests": "tests[0].path"}


# --- パスの字句の参照計算（Coreにも`frontmatter.schema.json`にも依存しない） ------------------

def violations(path, directory_prefix=False):
    """ワークスペース・設定仕様 §9のパスの字句の違反を、名前の集合で返す。

    `directory_prefix`は、末尾の`/`1つを許すTASKの`changes`である。`src//`は、空のセグメント（`empty-segment`）を持つので、許されない。
    """
    if path == "":
        return {"empty"}
    found = set()
    if path.startswith("/"):
        found.add("absolute")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in path):
        found.add("control")
    if any(character in path for character in GLOB_CHARACTERS):
        found.add("glob")
    segments = path.split("/")
    for index, segment in enumerate(segments):
        if segment == ".":
            found.add("dot-segment")
        elif segment == "..":
            found.add("dotdot-segment")
        elif segment == "" and index > 0:
            if index == len(segments) - 1:
                if not directory_prefix:
                    found.add("trailing-slash")
            else:
                found.add("empty-segment")
    return found


def old_rejected(path, empty_segments):
    """修正前のCoreの読み方。空、絶対パス、NUL、globの文字、`.`と`..`のセグメントを拒否し、NUL以外の制御文字を拒否しない。
    空のセグメントと末尾の`/`は、`cwd`、メンバーのパス、除外のパスでは拒否し（`empty_segments`）、フロントマターのパスでは拒否しなかった（C101）。"""
    if path == "" or path.startswith("/") or "\x00" in path or any(character in path for character in GLOB_CHARACTERS):
        return True
    segments = path.split("/")
    if any(segment in (".", "..") for segment in segments):
        return True
    return empty_segments and "" in segments


def old_empty_segments(identifier):
    return CASES[identifier]["group"] != "frontmatter"


def case_paths(identifier):
    case = CASES[identifier]
    return case["paths"] if case["group"] == "frontmatter" else [case["cwd"] if case["group"] == "cwd" else case["path"]]


def is_changes(identifier):
    return CASES[identifier].get("field") == "changes"


def reference_rejected(identifier):
    return any(violations(path, is_changes(identifier)) for path in case_paths(identifier))


# --- 入力 -------------------------------------------------------------------------------

_RAW_CONTROLS = re.compile("[\x7f-\x9f]")


def flow(value):
    """JSON構文の値を、YAMLのフロー値として書く。YAMLの印字可能文字から外れる`U+007F`〜`U+009F`はエスケープで書く。"""
    return _RAW_CONTROLS.sub(lambda match: "\\u%04x" % ord(match.group()), json.dumps(value, ensure_ascii=False))


def spec_path(identifier):
    case = CASES[identifier]
    return f".spec/{KINDS[case['kind']][0]}/{case['kind']}-001.md"


def fields(identifier):
    """デコードした後のフロントマターのフィールド。"""
    case = CASES[identifier]
    value = {"id": f"{case['kind']}-001", "title": TITLE, "status": KINDS[case["kind"]][2]}
    if case["field"] == "tests":
        value["tests"] = [{"path": case["paths"][0], "covers": ["REQ-001:AC-01"], "command": "default"}]
    else:
        value[case["field"]] = list(case["paths"])
    return value


def frontmatter_inputs(identifier):
    case = CASES[identifier]
    value = fields(identifier)
    header = "".join(f"{key}: {flow(item)}\n" for key, item in value.items())
    body = f"# {value['id']} {TITLE}\n\n" + (INTENT + AC + VERIFICATION if case["kind"] == "REQ" else TASK_BODY)
    config = CONFIGS["SINGLE-001"].encode()
    if "tests" in value:
        config += b"verify:\n  commands:\n    default:\n      argv: [\"/bin/true\"]\n      cwd: .\n"
    inputs = {".spec/bitz.yaml": config, spec_path(identifier): ("---\n" + header + "---\n\n" + body).encode()}
    for path in case["files"]:
        inputs[path] = TEST_CONTENT if path.startswith("tests/") else CODE_CONTENT
    return inputs


def cwd_inputs(identifier):
    """`SINGLE-167-01`の入力のコマンドの`cwd`だけを替える。"""
    inputs = dict(command_cwd.reviewed_inputs("SINGLE-167-01"))
    inputs[command_cwd.CONFIG_PATH] = digest_reference.CONFIG.replace(
        command_cwd.CWD_LINE, f"      cwd: {flow(CASES[identifier]['cwd'])}\n").encode()
    return inputs


def multi_config(identifier):
    """`MULTI-037-09`の設定の、除外のパスまたはメンバー`web`のパスだけを替える。"""
    case = CASES[identifier]
    if case["group"] == "exclude":
        members = multi_exclude.MEMBERS
        return multi_reference.root_config(members, multi_exclude.ROOT_ID) + f"  exclude:\n    - {flow(case['path'])}\n"
    members = [(member, flow(case["path"]) if member == "web" else path) for member, path in multi_exclude.MEMBERS]
    return multi_reference.root_config(members, multi_exclude.ROOT_ID)


def multi_inputs(identifier):
    case = CASES[identifier]
    repo = multi_exclude.reviewed_inputs("MULTI-037-09")[0]
    repo[multi_reference.ROOT_CONFIG_PATH] = multi_config(identifier).encode()
    if case["group"] == "member":
        # 制御文字を含むメンバーのパスの実体は置かない。`web`の設定が残ると、未登録の設定として別の診断が重なる。
        del repo[multi_reference.WEB_CONFIG_PATH]
    return repo


def reviewed_inputs(identifier):
    """`repo/`の全入力。パス→バイト列。"""
    group = CASES[identifier]["group"]
    return {"frontmatter": frontmatter_inputs, "cwd": cwd_inputs, "exclude": multi_inputs, "member": multi_inputs}[group](identifier)


def directory_of(identifier):
    return "multi" if identifier.startswith("MULTI-") else "single"


def result_name(identifier):
    return "expected/verify.json" if CASES[identifier]["group"] == "cwd" else "expected/check.json"


def reviewed_manifest(identifier):
    case = CASES[identifier]
    if case["group"] == "frontmatter":
        rejected = case["rejected"]
        return {"fixtureId": identifier, "description": case["description"],
                "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
                "invocation": {"runner": "bitz", "cwd": ".", "argv": ["check", "--full", "--base", "HEAD", "--format", "json"], "env": {}},
                "expect": {"status": "failed" if rejected else "passed", "exitCode": 1 if rejected else 0, "stdout": "json",
                           "resultFile": "expected/check.json", "reportFileCount": 0}}
    base = {"cwd": "SINGLE-167-01", "exclude": "MULTI-037-09", "member": "MULTI-037-16"}[case["group"]]
    manifest = copy.deepcopy((command_cwd if case["group"] == "cwd" else multi_exclude).reviewed_manifest(base))
    manifest.update(fixtureId=identifier, description=case["description"])
    return manifest


def reviewed_result(identifier):
    case = CASES[identifier]
    if case["group"] == "cwd":
        return copy.deepcopy(command_cwd.reviewed_result("SINGLE-167-01"))
    if case["group"] == "exclude":
        return copy.deepcopy(multi_exclude.reviewed_check_result("MULTI-037-09"))
    if case["group"] == "member":
        result = copy.deepcopy(multi_exclude.reviewed_check_result("MULTI-037-16"))
        result["diagnostics"][0]["summary"] = MEMBER_PATH_SUMMARY
        return result
    rejected = case["rejected"]
    status = "failed" if rejected else "passed"
    diagnostics = []
    if rejected:
        key = FRONTMATTER_KEY[case["field"]]
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

def configured_value(text, prefix):
    """設定の1行の値を独立にデコードする（この群は、二重引用符で書く値だけを使う）。"""
    value = text.strip()[len(prefix):].strip()
    return json.loads(value) if value[:1] == '"' else value


def configured_paths(identifier, repository):
    """準備手順の後の入力から、字句を検査する対象のパスを読む。"""
    case = CASES[identifier]
    if case["group"] == "frontmatter":
        decoded = decode_header((repository / spec_path(identifier)).read_text(encoding="utf-8"))
        if decoded != fields(identifier):
            raise ValueError("固定したYAMLのフロー値が独立にデコードしたフィールドと異なります")
        return [path for _, path in listed_paths(decoded)]
    if case["group"] == "cwd":
        lines = [line for line in (repository / command_cwd.CONFIG_PATH).read_text(encoding="utf-8").splitlines() if line.strip().startswith("cwd:")]
        if len(lines) != 1:
            raise ValueError("設定は`cwd`を1件だけ持つ必要があります")
        return [configured_value(lines[0], "cwd:")]
    lines = (repository / multi_reference.ROOT_CONFIG_PATH).read_text(encoding="utf-8").splitlines()
    if case["group"] == "exclude":
        start = lines.index("  exclude:")
        return [configured_value(line, "-") for line in lines[start + 1:]]
    return [configured_value(line, "path:") for line in lines if line.startswith("      path: ")]


def expected_files(identifier):
    """リポジトリが追跡するパスの集合。ケースの定義と、引き継ぐ元のfixtureの入力から導く（`reviewed_inputs`とは独立）。"""
    case = CASES[identifier]
    if case["group"] == "frontmatter":
        return {".spec/bitz.yaml", spec_path(identifier), *case["files"]}
    if case["group"] == "cwd":
        return set(command_cwd.reviewed_inputs("SINGLE-167-01"))
    # 制御文字を含むメンバーのパスの実体は置かない（`web`の設定が残ると、未登録の設定として別の診断が重なる）。
    names = set(multi_exclude.reviewed_inputs("MULTI-037-09")[0])
    return names - {multi_reference.WEB_CONFIG_PATH} if case["group"] == "member" else names


def check_conditions(identifier, repository):
    """準備手順の後のリポジトリの実体から、参照計算が期待と一致し、意図した1つの原因だけを持つことを確かめる。"""
    case = CASES[identifier]
    paths = configured_paths(identifier, repository)
    if case["group"] == "member":
        # カタログは`web`と`api`の2件で、制御文字を含むのは`web`のパスだけである。
        if paths != [case["path"], "services/api"]:
            raise ValueError("メンバーのパスがレビュー済みのケースと異なります")
        paths = paths[:1]
    elif paths != case_paths(identifier):
        raise ValueError("対象のパスがレビュー済みのケースと異なります")
    verdicts = [violations(path, is_changes(identifier)) for path in paths]
    if any(verdicts) != case["rejected"] or (case["rejected"] and len(paths) != 1):
        raise ValueError("パスの字句の参照計算が期待の受理と一致しません")
    # 拒否するパスは、意図した1つの原因だけを持つ（ほかの原因を重ねない）。
    if case["rejected"] and verdicts[0] != {case["cause"]}:
        raise ValueError("拒否するパスが意図した1つの原因だけを持ちません")
    # 修正前のCoreの読み方は、欠陥を検出するケースだけ結果が異なる。
    old = any(old_rejected(path, old_empty_segments(identifier)) for path in paths)
    if (old != case["rejected"]) != case["defective"]:
        raise ValueError("修正前のCoreの欠陥を検出できる入力、または対照の入力ではありません")
    tracked = set(git(repository, "ls-files", "-z").decode().split("\0")[:-1])
    if any(ord(character) < 0x20 or ord(character) == 0x7F for name in tracked for character in name):
        raise ValueError("制御文字を含むファイル名は置いてはいけません")
    if tracked != set(reviewed_inputs(identifier)) or tracked != expected_files(identifier):
        raise ValueError("インデックスのパスがレビュー済みの基準版と異なります")
    if case["group"] == "frontmatter":
        # 実ファイルは、置くと決めたパスだけを置く（上で追跡するパスの集合を確かめた）。通常のファイルで、基準版のコミットに追跡される。
        for path in case["files"]:
            if not (repository / path).is_file() or (repository / path).is_symlink():
                raise ValueError("実ファイルの有無がレビュー済みのケースと異なります")
        if "tests" in fields(identifier) and b"default:" not in (repository / ".spec/bitz.yaml").read_bytes():
            raise ValueError("testsのコマンドの定義がありません")
    if case["group"] in ("frontmatter", "exclude", "member"):
        status = git(repository, "status", "--porcelain=v1", "--untracked-files=all", "-z")
        if status:
            raise ValueError("作業ツリーは基準版のコミットと同じである必要があります")
        for path, content in reviewed_inputs(identifier).items():
            if git(repository, "show", "HEAD:" + path) != content or git(repository, "show", ":" + path) != content:
                raise ValueError("`HEAD`またはインデックスのバイト列がレビュー済みの基準版と異なります")
    else:
        # `verify`は入力をインデックスへステージして実行する（`SINGLE-167`と同じ）。
        for path, content in reviewed_inputs(identifier).items():
            if git(repository, "show", ":" + path) != content:
                raise ValueError("インデックスのバイト列がレビュー済みの入力と異なります")


def schema_verdict(identifier, schema):
    """`frontmatter.schema.json`の文書種別ごとの定義の合否（フロントマターのケースだけ）。"""
    definition = KINDS[CASES[identifier]["kind"]][1]
    validator = Draft202012Validator({"$ref": "#/$defs/" + definition, "$defs": schema["$defs"]})
    return bool(list(validator.iter_errors(fields(identifier))))


# --- 生成と監査 ---------------------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = root / directory_of(identifier) / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / result_name(identifier)).write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-path-lexical-") as temporary:
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
        fixture = root / directory_of(identifier) / identifier
        try:
            case = CASES[identifier]
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / result_name(identifier)).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("マニフェストまたは結果がレビュー済みの単一条件と異なります")
            if {p.name for p in (fixture / "expected").glob("*")} != {Path(result_name(identifier)).name} or any(
                    (fixture / name).exists() for name in ("changes", "cli-output.json")):
                raise ValueError("期待結果のファイルの構成がレビュー済みの形と異なります")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name] or p.stat().st_mode & 0o111
                                                for name, p in files.items()):
                raise ValueError("入力のバイト列またはファイルモードがレビュー済みのcorpusと異なります")
            if reference_rejected(identifier) != case["rejected"]:
                raise ValueError("パスの字句の参照計算がレビュー済みの受理と一致しません")
            if case["group"] == "frontmatter":
                if schema_verdict(identifier, schema) != case["rejected"]:
                    raise ValueError("フロントマターのスキーマの判定がレビュー済みの受理と一致しません")
                if result["checkedDocumentCount"] != (0 if case["rejected"] else 1):
                    raise ValueError("拒否した文書は件数に数えません")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("パスの字句の検査はファイルを書いてはいけません")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-path-lexical-") as temporary:
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
