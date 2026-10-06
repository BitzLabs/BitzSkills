"""共通の対象展開と`advisory`の提示を固定するfixture（Coreの公開操作は実行しない）。

matrix §6.11の`SINGLE-106-03`、`SINGLE-106-06`〜`07`と§6.12の`SINGLE-107`〜`110`、`113`、`134`〜`136`、`139`〜`143`を扱う。
`context`の期待値は4つの集合（rootDocuments、contextDocuments、targetStatements、adjacentStatements）を
`roots`、`documents[]`、制約台帳、`coverage.adjacent`として完全比較し、同じ起点の`verify`は
`context`と同じ対象規範文の集合を返すことを確認する。

ハッシュ値の材料は参照計算A（このモジュールのリテラル）と参照計算B（digest_crosscheckが入力の木構造から導出）の
2系統で計算し、バイト列の一致を要求する。根拠は[関係・トレースモデル §6・§7]、[`bitz context`仕様 §4・§5]、
[`bitz verify`仕様 §3・§4]である。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from .harness import git, setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
CONFIG = digest_reference.CONFIG
EMPTY = digest_reference.EMPTY_RELATIONS
TEST_BODY = "def test_fixture():\n    assert True\n"

# --- 入力corpus -----------------------------------------------------------------------
# 文書ごとに (パス, フロントマターのYAML, フロントマターの値, 本文, 規範文[(ID, テキスト)]) を固定する。
# フロントマターの値はYAMLのレビュー済みの解釈であり、YAMLの構文解析器から導出しない。


def statement_line(identifier, text):
    return f"- [{identifier}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n"


def requirement(identifier, title, statements, fields="", verification="宣言したtestで確認する。"):
    head = f"---\nid: {identifier}\ntitle: {title}\nstatus: approved\n{fields}---\n"
    body = (f"# {identifier} {title}\n\n## Intent\n\ntarget展開の検査に使う固定要求。\n\n"
            "## Acceptance Criteria\n\n" + "".join(statement_line(*s) for s in statements)
            + f"\n## Verification\n\n{verification}\n")
    return head, body


def technical(identifier, title, statements, fields="", status="approved"):
    head = f"---\nid: {identifier}\ntitle: {title}\nstatus: {status}\n{fields}---\n"
    body = (f"# {identifier} {title}\n\n## Context\n\n具体化する技術契約。\n\n"
            "## Contract\n\n" + "".join(statement_line(*s) for s in statements))
    return head, body


def task(identifier, title, status, fields):
    head = f"---\nid: {identifier}\ntitle: {title}\nstatus: {status}\n{fields}---\n"
    body = f"# {identifier} {title}\n\n## Objective\n\n対象句を実装する。\n"
    return head, body


def document(path, parts, frontmatter, statements):
    head, body = parts
    return {"path": path, "bytes": (head + "\n" + body).encode(), "frontmatter": frontmatter,
            "body": body, "statements": statements}


ROOT_STATEMENTS = [("REQ-001:AC-01", "入力を検証する"), ("REQ-001:AC-02", "結果を記録する")]
ROOT_TESTS = [{"path": "tests/test_root.py", "covers": ["REQ-001:AC-01", "REQ-001:AC-02"], "command": "default"}]
ROOT_ONE_TEST_YAML = "tests:\n  - path: tests/test_root.py\n    covers: [REQ-001:AC-01]\n    command: default\n"
ROOT_TESTS_YAML = ("tests:\n  - path: tests/test_root.py\n"
                   "    covers: [REQ-001:AC-01, REQ-001:AC-02]\n    command: default\n")


def fm(identifier, title, status="approved", **fields):
    value = {"id": identifier, "title": title, "status": status}
    value.update(fields)
    return value


def corpus_refinement():
    """107・113: REQ-001がREQ-009をrequires、REQ-099をrelated。TECH-002・003が推移的に具体化する。"""
    return [
        document(".spec/requirements/REQ-001.md", requirement(
            "REQ-001", "展開の起点要求", ROOT_STATEMENTS,
            "relations:\n  requires: [REQ-009]\n  related: [REQ-099]\n" + ROOT_TESTS_YAML),
            fm("REQ-001", "展開の起点要求", relations={"requires": ["REQ-009"], "related": ["REQ-099"]},
               tests=ROOT_TESTS), ROOT_STATEMENTS),
        document(".spec/requirements/REQ-009.md", requirement(
            "REQ-009", "前提要求", [("REQ-009:AC-01", "前提を満たす")]),
            fm("REQ-009", "前提要求"), [("REQ-009:AC-01", "前提を満たす")]),
        document(".spec/requirements/REQ-099.md", requirement(
            "REQ-099", "閲覧用の関連要求", [("REQ-099:AC-01", "関連情報を示す")]),
            fm("REQ-099", "閲覧用の関連要求"), [("REQ-099:AC-01", "関連情報を示す")]),
        document(".spec/technical/TECH-002.md", technical(
            "TECH-002", "直接の具体化", [("TECH-002:AC-01", "入力形式を固定する")],
            "relations:\n  refines: [REQ-001:AC-01]\ntests:\n  - path: tests/test_direct.py\n"
            "    covers: [TECH-002:AC-01]\n    command: default\n"),
            fm("TECH-002", "直接の具体化", relations={"refines": ["REQ-001:AC-01"]},
               tests=[{"path": "tests/test_direct.py", "covers": ["TECH-002:AC-01"], "command": "default"}]),
            [("TECH-002:AC-01", "入力形式を固定する")]),
        document(".spec/technical/TECH-003.md", technical(
            "TECH-003", "間接の具体化", [("TECH-003:AC-01", "形式違反を拒否する")],
            "relations:\n  refines: [TECH-002:AC-01]\ntests:\n  - path: tests/test_indirect.py\n"
            "    covers: [TECH-003:AC-01]\n    command: default\n"),
            fm("TECH-003", "間接の具体化", relations={"refines": ["TECH-002:AC-01"]},
               tests=[{"path": "tests/test_indirect.py", "covers": ["TECH-003:AC-01"], "command": "default"}]),
            [("TECH-003:AC-01", "形式違反を拒否する")]),
    ]


def corpus_technical():
    """108: 規範文ありTECH-001がTECH-009をrequiresし、TECH-004が規範文1件を具体化する。"""
    root = [("TECH-001:AC-01", "応答形式を固定する"), ("TECH-001:AC-02", "応答時間を記録する")]
    return [
        document(".spec/technical/TECH-001.md", technical(
            "TECH-001", "規範文を持つ技術契約", root,
            "relations:\n  requires: [TECH-009]\ntests:\n  - path: tests/test_contract.py\n"
            "    covers: [TECH-001:AC-01, TECH-001:AC-02]\n    command: default\n"),
            fm("TECH-001", "規範文を持つ技術契約", relations={"requires": ["TECH-009"]},
               tests=[{"path": "tests/test_contract.py", "covers": ["TECH-001:AC-01", "TECH-001:AC-02"],
                       "command": "default"}]), root),
        document(".spec/technical/TECH-004.md", technical(
            "TECH-004", "契約の具体化", [("TECH-004:AC-01", "形式の詳細を定める")],
            "relations:\n  refines: [TECH-001:AC-01]\ntests:\n  - path: tests/test_detail.py\n"
            "    covers: [TECH-004:AC-01]\n    command: default\n"),
            fm("TECH-004", "契約の具体化", relations={"refines": ["TECH-001:AC-01"]},
               tests=[{"path": "tests/test_detail.py", "covers": ["TECH-004:AC-01"], "command": "default"}]),
            [("TECH-004:AC-01", "形式の詳細を定める")]),
        document(".spec/technical/TECH-009.md", technical(
            "TECH-009", "前提技術契約", [("TECH-009:AC-01", "前提形式を定義する")]),
            fm("TECH-009", "前提技術契約"), [("TECH-009:AC-01", "前提形式を定義する")]),
    ]


def corpus_statement():
    """109: AC-01だけを具体化するTECH-002と、対象規範文2件をaddressesするopenのTASK-001。"""
    return [
        document(".spec/requirements/REQ-001.md", requirement(
            "REQ-001", "兄弟句を持つ要求", ROOT_STATEMENTS, ROOT_TESTS_YAML),
            fm("REQ-001", "兄弟句を持つ要求", tests=ROOT_TESTS), ROOT_STATEMENTS),
        document(".spec/technical/TECH-002.md", technical(
            "TECH-002", "直接の具体化", [("TECH-002:AC-01", "入力形式を固定する")],
            "relations:\n  refines: [REQ-001:AC-01]\ntests:\n  - path: tests/test_direct.py\n"
            "    covers: [TECH-002:AC-01]\n    command: default\n"),
            fm("TECH-002", "直接の具体化", relations={"refines": ["REQ-001:AC-01"]},
               tests=[{"path": "tests/test_direct.py", "covers": ["TECH-002:AC-01"], "command": "default"}]),
            [("TECH-002:AC-01", "入力形式を固定する")]),
        document(".spec/tasks/TASK-001.md", task(
            "TASK-001", "指定句の実装", "open",
            "relations:\n  addresses: [REQ-001:AC-01, TECH-002:AC-01]\nchanges: [src/validate.py]\n"),
            fm("TASK-001", "指定句の実装", "open",
               relations={"addresses": ["REQ-001:AC-01", "TECH-002:AC-01"]}, changes=["src/validate.py"]), []),
    ]


def corpus_task():
    """110: open TASK-001がdone TASK-002をrequiresし、各TASKが別REQの規範文をaddressesする。"""
    only = [("REQ-001:AC-01", "入力を検証する")]
    tests_yaml = "tests:\n  - path: tests/test_root.py\n    covers: [REQ-001:AC-01]\n    command: default\n"
    return [
        document(".spec/requirements/REQ-001.md", requirement("REQ-001", "TASKの対象要求", only, tests_yaml),
                 fm("REQ-001", "TASKの対象要求", tests=[{"path": "tests/test_root.py", "covers": ["REQ-001:AC-01"],
                                                    "command": "default"}]), only),
        document(".spec/requirements/REQ-009.md", requirement(
            "REQ-009", "先行TASKの対象要求", [("REQ-009:AC-01", "前提を満たす")]),
            fm("REQ-009", "先行TASKの対象要求"), [("REQ-009:AC-01", "前提を満たす")]),
        document(".spec/tasks/TASK-001.md", task(
            "TASK-001", "対象句の実装", "open",
            "relations:\n  requires: [TASK-002]\n  addresses: [REQ-001:AC-01]\n"),
            fm("TASK-001", "対象句の実装", "open",
               relations={"requires": ["TASK-002"], "addresses": ["REQ-001:AC-01"]}), []),
        document(".spec/tasks/TASK-002.md", task(
            "TASK-002", "先行作業", "done", "relations:\n  addresses: [REQ-009:AC-01]\n"),
            fm("TASK-002", "先行作業", "done", relations={"addresses": ["REQ-009:AC-01"]}), []),
    ]


def corpus_done_prerequisite():
    """134: open TASK-001が、done TASK-002をrequiresし、テスト対応のないREQ-001:AC-01をaddressesする。
    先行TASKがすべて`done`なので、起点にした目的`implement`は止まらず、テスト対応が無いことだけが警告になる。"""
    only = [("REQ-001:AC-01", "入力を検証する")]
    return [
        document(".spec/requirements/REQ-001.md", requirement("REQ-001", "テスト対応のない対象要求", only, verification="テスト対応は宣言しない。"),
                 fm("REQ-001", "テスト対応のない対象要求"), only),
        document(".spec/tasks/TASK-001.md", task(
            "TASK-001", "対象句の実装", "open",
            "relations:\n  requires: [TASK-002]\n  addresses: [REQ-001:AC-01]\n"),
            fm("TASK-001", "対象句の実装", "open",
               relations={"requires": ["TASK-002"], "addresses": ["REQ-001:AC-01"]}), []),
        document(".spec/tasks/TASK-002.md", task("TASK-002", "完了済みの先行作業", "done", ""),
                 fm("TASK-002", "完了済みの先行作業", "done"), []),
    ]


def corpus_refines_target_by_requires():
    """135: REQ-001がREQ-002をrequiresし、REQ-003をrefinesする。REQ-002もREQ-003をrequiresする。
    REQ-003は、起点の`refines`の参照先であり、`requires`の鎖でも到達する。表の上から最初に該当する役割は`refinement`であり、
    その規範文`REQ-003:AC-01`は対象規範文にならない（関係・トレースモデル §6.4の4.）ので、制約台帳に収録されない。"""
    root = [("REQ-001:AC-01", "入力を検証する")]
    tests_yaml = "tests:\n  - path: tests/test_root.py\n    covers: [REQ-001:AC-01]\n    command: default\n"
    return [
        document(".spec/requirements/REQ-001.md", requirement(
            "REQ-001", "起点要求", root,
            "relations:\n  requires: [REQ-002]\n  refines: [REQ-003]\n" + tests_yaml),
            fm("REQ-001", "起点要求", relations={"requires": ["REQ-002"], "refines": ["REQ-003"]},
               tests=[{"path": "tests/test_root.py", "covers": ["REQ-001:AC-01"], "command": "default"}]), root),
        document(".spec/requirements/REQ-002.md", requirement(
            "REQ-002", "前提要求", [("REQ-002:AC-01", "前提を満たす")], "relations:\n  requires: [REQ-003]\n"),
            fm("REQ-002", "前提要求", relations={"requires": ["REQ-003"]}), [("REQ-002:AC-01", "前提を満たす")]),
        document(".spec/requirements/REQ-003.md", requirement(
            "REQ-003", "起点が具体化する要求", [("REQ-003:AC-01", "秘密鍵を保持しない")]),
            fm("REQ-003", "起点が具体化する要求"), [("REQ-003:AC-01", "秘密鍵を保持しない")]),
    ]


def corpus_document_refinement_chain():
    """136: TECH-002が文書単位でREQ-001を具体化し、TECH-003が文書単位でTECH-002を具体化する。
    目的`interpret`は対象規範文が空で制約台帳も空なので、距離2のTECH-003の`MUST`は制約台帳に収録されない。"""
    root = [("REQ-001:AC-01", "入力を検証する")]
    return [
        document(".spec/requirements/REQ-001.md", requirement("REQ-001", "起点要求", root),
                 fm("REQ-001", "起点要求"), root),
        document(".spec/technical/TECH-002.md", technical(
            "TECH-002", "直接の具体化", [("TECH-002:AC-01", "入力形式を固定する")],
            "relations:\n  refines: [REQ-001]\n"),
            fm("TECH-002", "直接の具体化", relations={"refines": ["REQ-001"]}),
            [("TECH-002:AC-01", "入力形式を固定する")]),
        document(".spec/technical/TECH-003.md", technical(
            "TECH-003", "間接の具体化", [("TECH-003:AC-01", "形式違反を拒否する")],
            "relations:\n  refines: [TECH-002]\n"),
            fm("TECH-003", "間接の具体化", relations={"refines": ["TECH-002"]}),
            [("TECH-003:AC-01", "形式違反を拒否する")]),
    ]


def corpus_shorter_refines_path():
    """139: REQ-001がREQ-003をrequiresし、REQ-002をrefinesする。REQ-003もREQ-002をrequiresする。
    REQ-002は、起点の`refines`の参照先（距離1）であり、`requires`の鎖（REQ-001、REQ-003、REQ-002）でも距離2で到達する。
    距離は閉包を作るときに辿ったエッジによる最短の段数なので、REQ-002は距離1で、REQ-003と同じ距離になり、IDの順に並ぶ
    （関係・トレースモデル §7の6.）。表の上から最初に該当する役割は、REQ-002が`refinement`、REQ-003が`requirement`である。"""
    root = [("REQ-001:AC-01", "入力を検証する")]
    return [
        document(".spec/requirements/REQ-001.md", requirement(
            "REQ-001", "起点要求", root, "relations:\n  requires: [REQ-003]\n  refines: [REQ-002]\n"),
            fm("REQ-001", "起点要求", relations={"requires": ["REQ-003"], "refines": ["REQ-002"]}), root),
        document(".spec/requirements/REQ-002.md", requirement(
            "REQ-002", "起点が具体化する要求", [("REQ-002:AC-01", "秘密鍵を保持しない")]),
            fm("REQ-002", "起点が具体化する要求"), [("REQ-002:AC-01", "秘密鍵を保持しない")]),
        document(".spec/requirements/REQ-003.md", requirement(
            "REQ-003", "前提要求", [("REQ-003:AC-01", "前提を満たす")], "relations:\n  requires: [REQ-002]\n"),
            fm("REQ-003", "前提要求", relations={"requires": ["REQ-002"]}), [("REQ-003:AC-01", "前提を満たす")]),
    ]


def corpus_task_refinement_chain():
    """140: open TASK-001がREQ-001:AC-01をaddressesし、TECH-002が規範文REQ-001:AC-01を、TECH-003が規範文TECH-002:AC-01を
    具体化する。距離は、TASK-001が0、REQ-001が1（`addresses`の1段）、TECH-002が2、TECH-003が3である（§7の6.）。
    TECH-002とTECH-003は距離2以上の具体化文書で、所有する規範文は目的`implement`の対象規範文（§6.4の3.）として
    制約台帳に収録されるので、提示形式は`normative`になる（`context` §5）。"""
    root = [("REQ-001:AC-01", "入力を検証する")]
    return [
        document(".spec/requirements/REQ-001.md", requirement(
            "REQ-001", "TASKの対象要求", root, ROOT_ONE_TEST_YAML),
            fm("REQ-001", "TASKの対象要求", tests=[{"path": "tests/test_root.py", "covers": ["REQ-001:AC-01"],
                                                "command": "default"}]), root),
        document(".spec/technical/TECH-002.md", technical(
            "TECH-002", "直接の具体化", [("TECH-002:AC-01", "入力形式を固定する")],
            "relations:\n  refines: [REQ-001:AC-01]\ntests:\n  - path: tests/test_direct.py\n"
            "    covers: [TECH-002:AC-01]\n    command: default\n"),
            fm("TECH-002", "直接の具体化", relations={"refines": ["REQ-001:AC-01"]},
               tests=[{"path": "tests/test_direct.py", "covers": ["TECH-002:AC-01"], "command": "default"}]),
            [("TECH-002:AC-01", "入力形式を固定する")]),
        document(".spec/technical/TECH-003.md", technical(
            "TECH-003", "間接の具体化", [("TECH-003:AC-01", "形式違反を拒否する")],
            "relations:\n  refines: [TECH-002:AC-01]\ntests:\n  - path: tests/test_indirect.py\n"
            "    covers: [TECH-003:AC-01]\n    command: default\n"),
            fm("TECH-003", "間接の具体化", relations={"refines": ["TECH-002:AC-01"]},
               tests=[{"path": "tests/test_indirect.py", "covers": ["TECH-003:AC-01"], "command": "default"}]),
            [("TECH-003:AC-01", "形式違反を拒否する")]),
        document(".spec/tasks/TASK-001.md", task(
            "TASK-001", "対象句の実装", "open", "relations:\n  addresses: [REQ-001:AC-01]\n"),
            fm("TASK-001", "対象句の実装", "open", relations={"addresses": ["REQ-001:AC-01"]}), []),
    ]


def corpus_superseded_origin():
    """141: TECH-005がTECH-007をrequiresし、TECH-009がTECH-005をsupersedesする（TECH-005は置換済みの起点）。
    目的`interpret`は、起点を役割`advisory`、後継のTECH-009を役割`replacement`として示す（§6.1の5.）。
    後継は起点から`supersedes`のエッジを1本辿った距離1（§7の6.）で、起点の`requires`の参照先TECH-007も距離1なので、
    距離1の2件はIDの順（TECH-007、TECH-009）に並ぶ。"""
    return [
        document(".spec/technical/TECH-005.md", technical(
            "TECH-005", "置換される技術契約", [("TECH-005:AC-01", "旧形式を使う")],
            "relations:\n  requires: [TECH-007]\n"),
            fm("TECH-005", "置換される技術契約", relations={"requires": ["TECH-007"]}),
            [("TECH-005:AC-01", "旧形式を使う")]),
        document(".spec/technical/TECH-007.md", technical(
            "TECH-007", "前提技術契約", [("TECH-007:AC-01", "前提形式を定義する")]),
            fm("TECH-007", "前提技術契約"), [("TECH-007:AC-01", "前提形式を定義する")]),
        document(".spec/technical/TECH-009.md", technical(
            "TECH-009", "後継の技術契約", [("TECH-009:AC-01", "新形式を使う")],
            "relations:\n  supersedes: [TECH-005]\n"),
            fm("TECH-009", "後継の技術契約", relations={"supersedes": ["TECH-005"]}),
            [("TECH-009:AC-01", "新形式を使う")]),
    ]


def corpus_advisory():
    """106-03: approved REQ-001の規範文を、draftのTECH-005が具体化する。"""
    only = [("REQ-001:AC-01", "入力を検証する")]
    return [
        document(".spec/requirements/REQ-001.md", requirement("REQ-001", "advisory提示の起点", only),
                 fm("REQ-001", "advisory提示の起点"), only),
        document(".spec/technical/TECH-005.md", technical(
            "TECH-005", "検討中の具体化", [("TECH-005:AC-01", "候補形式を示す")],
            "relations:\n  refines: [REQ-001:AC-01]\n", status="draft"),
            fm("TECH-005", "検討中の具体化", "draft", relations={"refines": ["REQ-001:AC-01"]}),
            [("TECH-005:AC-01", "候補形式を示す")]),
    ]


def corpus_draft_excluded():
    """142: approved REQ-001の規範文を、draftのTECH-005が`refines`し、そのテスト対応がREQ-001:AC-01を`covers`する。
    REQ-001自身はテスト対応を持たない。目的`implement`はdraftの文書を閉包へ含めないので（関係・トレースモデル §6.1の末尾）、
    REQ-001:AC-01は未テストのままである。"""
    only = [("REQ-001:AC-01", "入力を検証する")]
    candidate = [("TECH-005:AC-01", "候補形式を示す")]
    tests = [{"path": "tests/test_candidate.py", "covers": ["REQ-001:AC-01", "TECH-005:AC-01"], "command": "default"}]
    tests_yaml = ("tests:\n  - path: tests/test_candidate.py\n"
                  "    covers: [REQ-001:AC-01, TECH-005:AC-01]\n    command: default\n")
    return [
        document(".spec/requirements/REQ-001.md", requirement("REQ-001", "draftの具体化を含めない起点", only),
                 fm("REQ-001", "draftの具体化を含めない起点"), only),
        document(".spec/technical/TECH-005.md", technical(
            "TECH-005", "検討中の具体化", candidate,
            "relations:\n  refines: [REQ-001:AC-01]\n" + tests_yaml, status="draft"),
            fm("TECH-005", "検討中の具体化", "draft", relations={"refines": ["REQ-001:AC-01"]}, tests=tests),
            candidate),
    ]


def corpus_draft_excluded_task():
    """143: open TASK-001がapproved REQ-001:AC-01を`addresses`する。REQ-001はテスト対応を持ち、draftのTECH-005が
    REQ-001を文書単位で`refines`する。TECH-005のテスト対応もREQ-001:AC-01を`covers`するが、目的`verify`はdraftの文書を
    閉包へ含めないので（関係・トレースモデル §6.1の末尾）、その状態を検査せず、テストも実行しない。"""
    only = [("REQ-001:AC-01", "入力を検証する")]
    candidate = [("TECH-005:AC-01", "候補形式を示す")]
    root_tests = [{"path": "tests/test_root.py", "covers": ["REQ-001:AC-01"], "command": "default"}]
    draft_tests = [{"path": "tests/test_candidate.py", "covers": ["REQ-001:AC-01", "TECH-005:AC-01"],
                    "command": "default"}]
    draft_tests_yaml = ("tests:\n  - path: tests/test_candidate.py\n"
                        "    covers: [REQ-001:AC-01, TECH-005:AC-01]\n    command: default\n")
    return [
        document(".spec/requirements/REQ-001.md", requirement(
            "REQ-001", "draftの具体化を含めない対象要求", only, ROOT_ONE_TEST_YAML),
            fm("REQ-001", "draftの具体化を含めない対象要求", tests=root_tests), only),
        document(".spec/technical/TECH-005.md", technical(
            "TECH-005", "検討中の具体化", candidate,
            "relations:\n  refines: [REQ-001]\n" + draft_tests_yaml, status="draft"),
            fm("TECH-005", "検討中の具体化", "draft", relations={"refines": ["REQ-001"]}, tests=draft_tests),
            candidate),
        document(".spec/tasks/TASK-001.md", task(
            "TASK-001", "対象句の検証", "open", "relations:\n  addresses: [REQ-001:AC-01]\n"),
            fm("TASK-001", "対象句の検証", "open", relations={"addresses": ["REQ-001:AC-01"]}), []),
    ]


def corpus_distance():
    """106-06: REQ-001がTECH-010をrequiresし、TECH-010がREQ-020をrequires。距離2以上の
    役割`requirement`と`constraint`は、距離だけを理由に具体化文書のように`normative`へ落とさず、役割に基づき
    `full`で提示する（`bitz context`仕様 §5、ADR-014 `Decision` 4・5）。"""
    deep_statements = [("REQ-020:AC-01", "秘密鍵を保持しない")]
    tech_head, tech_body = technical("TECH-010", "距離1の前提契約", [], "relations:\n  requires: [REQ-020]\n")
    # 規範文0件のTECHは末尾に空の節だけの空行を残さない（ハッシュ値の材料の末尾の正規化と一致させる）。
    tech_body = tech_body.rstrip("\n") + "\n"
    return [
        document(".spec/requirements/REQ-001.md", requirement(
            "REQ-001", "距離2依存の起点要求", ROOT_STATEMENTS,
            "relations:\n  requires: [TECH-010]\n" + ROOT_TESTS_YAML),
            fm("REQ-001", "距離2依存の起点要求", relations={"requires": ["TECH-010"]}, tests=ROOT_TESTS),
            ROOT_STATEMENTS),
        document(".spec/technical/TECH-010.md", (tech_head, tech_body),
            fm("TECH-010", "距離1の前提契約", relations={"requires": ["REQ-020"]}), []),
        document(".spec/requirements/REQ-020.md", requirement(
            "REQ-020", "距離2の前提要求", deep_statements),
            fm("REQ-020", "距離2の前提要求"), deep_statements),
    ]


# ID: (corpus, 引数列, 期待する状態, 説明)
CASES = {
    "SINGLE-106-03": (corpus_advisory, ["context", "REQ-001", "--purpose", "interpret", "--format", "json"],
                      "interpretでdraft refinementをadvisoryのreference projectionで提示する"),
    "SINGLE-107-01": (corpus_refinement, ["context", "REQ-001", "--purpose", "verify", "--format", "json"],
                      "REQ起点のrefinementはtarget、requires先はContextだけにする"),
    "SINGLE-107-02": (corpus_refinement, ["verify", "REQ-001", "--format", "json"],
                      "REQ起点のverifyはcontextと同じtarget statement集合を使う"),
    "SINGLE-108-01": (corpus_technical, ["context", "TECH-001", "--purpose", "verify", "--format", "json"],
                      "規範文ありTECH起点の4集合を完全比較する"),
    "SINGLE-108-02": (corpus_technical, ["verify", "TECH-001", "--format", "json"],
                      "規範文ありTECH起点のverifyはcontextと同じtarget statement集合を使う"),
    "SINGLE-109": (corpus_statement, ["context", "REQ-001:AC-01", "--purpose", "implement", "--format", "json"],
                   "statement起点の指定句とrefinementをtarget、兄弟句をadjacentにする"),
    "SINGLE-110": (corpus_task, ["context", "TASK-001", "--purpose", "verify", "--format", "json"],
                   "verifyの起点TASKはaddresses先だけをtargetとし、requires先TASKを含めない"),
    "SINGLE-134": (corpus_done_prerequisite, ["context", "TASK-001", "--purpose", "implement", "--format", "json"],
                   "implementの起点TASKは、先行TASKがdoneなら止まらず、未テストのMUSTだけを警告にする"),
    "SINGLE-135": (corpus_refines_target_by_requires, ["context", "REQ-001", "--purpose", "implement", "--format", "json"],
                   "起点のrefinesの参照先にrequiresの鎖でも到達しても、役割refinementのMUSTの本文を提示から落とさない"),
    "SINGLE-136": (corpus_document_refinement_chain, ["context", "REQ-001", "--purpose", "interpret", "--format", "json"],
                   "文書単位で具体化した距離2の文書は、対象規範文が空のinterpretでMUSTの本文を提示から落とさない"),
    "SINGLE-139": (corpus_shorter_refines_path, ["context", "REQ-001", "--purpose", "interpret", "--format", "json"],
                   "起点のrefinesの参照先にrequiresの鎖より短い経路で到達したら、距離を最短にして並べる"),
    "SINGLE-140": (corpus_task_refinement_chain, ["context", "TASK-001", "--purpose", "implement", "--format", "json"],
                   "TASK起点の具体化の鎖は、起点からの最短の距離で並べ、距離2以上の文書をnormativeで提示する"),
    "SINGLE-141": (corpus_superseded_origin, ["context", "TECH-005", "--purpose", "interpret", "--format", "json"],
                   "置換済みの起点の後継は距離1で、起点のrequires先とIDの順に並べる"),
    "SINGLE-142": (corpus_draft_excluded, ["context", "REQ-001", "--purpose", "implement", "--format", "json"],
                   "implementでは、refinesする状態draftの文書をadvisoryとしても閉包へ含めず、そのテスト対応を数えない"),
    "SINGLE-143": (corpus_draft_excluded_task, ["verify", "TASK-001", "--format", "json"],
                   "TASK起点のverifyは、refinesする状態draftの文書を閉包へ含めず、状態を検査しない"),
    "SINGLE-113": (corpus_refinement, ["verify", "REQ-001:AC-01", "REQ-001", "REQ-001:AC-01", "--format", "json"],
                   "文書IDと同文書のstatement IDを重複指定してもtargetとbindingを重複排除する"),
    "SINGLE-106-06": (corpus_distance, ["context", "REQ-001", "--purpose", "verify", "--format", "json"],
                      "距離2以上のrequirementとconstraintをroleに基づきfullで提示する"),
    "SINGLE-106-07": (corpus_refinement, ["context", "REQ-001", "--purpose", "verify",
                                          "--detail", "compact", "--format", "json"],
                      "compact detailは全文書をreference提示にしContext Digestを変えない"),
}
# `context`の期待展開（レビュー済み）。`verify`は同じ起点の`context`のfixtureの集合を参照する。
EXPANSIONS = {
    "SINGLE-106-03": {"purpose": "interpret", "root": "REQ-001",
                      "documents": [("REQ-001", "root", "full", ["root"]),
                                    ("TECH-005", "advisory", "reference", ["refines:TECH-005"])],
                      "ledger": [], "tested": [], "addressed": [], "adjacent": [], "advisory": ["TECH-005"]},
    "SINGLE-107-01": {"purpose": "verify", "root": "REQ-001",
                      "documents": [("REQ-001", "root", "full", ["root"]),
                                    ("REQ-009", "requirement", "full", ["requires:REQ-001"]),
                                    ("TECH-002", "refinement", "full", ["refines:TECH-002"]),
                                    ("TECH-003", "refinement", "normative", ["refines:TECH-003"])],
                      "ledger": ["REQ-001:AC-01", "REQ-001:AC-02", "TECH-002:AC-01", "TECH-003:AC-01"],
                      "tested": ["REQ-001:AC-01", "REQ-001:AC-02", "TECH-002:AC-01", "TECH-003:AC-01"],
                      "addressed": [], "adjacent": [], "advisory": []},
    "SINGLE-108-01": {"purpose": "verify", "root": "TECH-001",
                      "documents": [("TECH-001", "root", "full", ["root"]),
                                    ("TECH-004", "refinement", "full", ["refines:TECH-004"]),
                                    ("TECH-009", "constraint", "full", ["requires:TECH-001"])],
                      "ledger": ["TECH-001:AC-01", "TECH-001:AC-02", "TECH-004:AC-01"],
                      "tested": ["TECH-001:AC-01", "TECH-001:AC-02", "TECH-004:AC-01"],
                      "addressed": [], "adjacent": [], "advisory": []},
    "SINGLE-109": {"purpose": "implement", "root": "REQ-001:AC-01",
                   "documents": [("REQ-001", "root", "full", ["root"]),
                                 ("TECH-002", "refinement", "full", ["refines:TECH-002"]),
                                 ("TASK-001", "work", "full", ["addresses:TASK-001"])],
                   "ledger": ["REQ-001:AC-01", "TECH-002:AC-01"],
                   "tested": ["REQ-001:AC-01", "TECH-002:AC-01"],
                   "addressed": ["REQ-001:AC-01", "TECH-002:AC-01"], "adjacent": ["REQ-001:AC-02"],
                   "advisory": []},
    "SINGLE-110": {"purpose": "verify", "root": "TASK-001",
                   "documents": [("TASK-001", "root", "full", ["root"]),
                                 ("REQ-001", "requirement", "full", ["addresses:TASK-001"])],
                   "ledger": ["REQ-001:AC-01"], "tested": ["REQ-001:AC-01"],
                   "addressed": ["REQ-001:AC-01"], "adjacent": [], "advisory": []},
    # 134は、起点のTASKが`requires`する先行TASKがすべて`done`である。対象規範文REQ-001:AC-01は起点のTASK-001が
    # `addresses`するので対応済み、閉包にテスト対応がないので未テストであり、目的`implement`の`MUST`の
    # 未テストは警告になる（関係・トレースモデル §8、診断レジストリの`CTX-COVERAGE-TEST-MUST-IMPLEMENT`）。
    "SINGLE-134": {"purpose": "implement", "root": "TASK-001", "status": "passed_with_warnings",
                   "documents": [("TASK-001", "root", "full", ["root"]),
                                 ("REQ-001", "requirement", "full", ["addresses:TASK-001"]),
                                 ("TASK-002", "work", "full", ["requires:TASK-001"])],
                   "ledger": ["REQ-001:AC-01"], "tested": [], "addressed": ["REQ-001:AC-01"],
                   "adjacent": [], "advisory": [],
                   "diagnostics": [{"code": "CTX-COVERAGE-TEST-001", "severity": "warning",
                                    "resultStatus": "passed_with_warnings",
                                    "summary": "MUST REQ-001:AC-01がtestされていません",
                                    "source": {"kind": "file", "workspaceId": "root",
                                               "path": ".spec/requirements/REQ-001.md"}}]},
    # 135は、起点REQ-001の`refines`の参照先REQ-003が`requires`の鎖（REQ-001、REQ-002、REQ-003）でも到達する。役割の表は
    # 上から最初に該当する行なので、REQ-003は`requirement`ではなく`refinement`である。目的`implement`の対象規範文は
    # 起点の規範文だけ（§6.4の1.）で、`requires`の参照先と起点が`refines`する先の規範文は昇格しない（§6.4の4.）。
    # REQ-003:AC-01は制約台帳にないので、提示形式`normative`にすると`MUST`の文面が出力から失われる。
    # 距離は、起点が`refines`する先なので最短で1であり（関係・トレースモデル §7の6.）、REQ-002と同じ距離1で、種別とIDの順に並ぶ。
    # 対象規範文は対応するTASKがないので未対応であり、`CTX-COVERAGE-TASK-001`が警告になる（`SINGLE-054`と同じ条件）。
    "SINGLE-135": {"purpose": "implement", "root": "REQ-001", "status": "passed_with_warnings",
                   "documents": [("REQ-001", "root", "full", ["root"]),
                                 ("REQ-002", "requirement", "full", ["requires:REQ-001"]),
                                 ("REQ-003", "refinement", "full", ["refines:REQ-001", "requires:REQ-002"])],
                   "ledger": ["REQ-001:AC-01"], "tested": ["REQ-001:AC-01"], "addressed": [],
                   "adjacent": [], "advisory": [],
                   "diagnostics": [{"code": "CTX-COVERAGE-TASK-001", "severity": "warning",
                                    "resultStatus": "passed_with_warnings",
                                    "summary": "implement対象のMUST REQ-001:AC-01を実装するTASKがありません",
                                    "source": {"kind": "file", "workspaceId": "root",
                                               "path": ".spec/requirements/REQ-001.md"}}]},
    # 136は、TECH-002（距離1）とTECH-003（距離2）が文書単位で具体化の鎖を作る。目的`interpret`の対象規範文は空
    # （§6.4）なので制約台帳も空であり、どの具体化文書の規範文も制約台帳に収録されない。TECH-003を`normative`にすると
    # その`MUST`の文面が出力から失われるので、距離2でも`full`で提示する。
    "SINGLE-136": {"purpose": "interpret", "root": "REQ-001",
                   "documents": [("REQ-001", "root", "full", ["root"]),
                                 ("TECH-002", "refinement", "full", ["refines:TECH-002"]),
                                 ("TECH-003", "refinement", "full", ["refines:TECH-003"])],
                   "ledger": [], "tested": [], "addressed": [], "adjacent": [], "advisory": []},
    # 139は、起点REQ-001が`requires`でREQ-003、`refines`でREQ-002を参照し、REQ-003も`requires`でREQ-002を参照する。
    # REQ-002には、`refines`の1段（距離1）と、`requires`の2段（REQ-001、REQ-003、REQ-002。距離2）の経路があり、
    # 距離は最短の1である（関係・トレースモデル §7の6.）。REQ-003も`requires`の1段で距離1なので、距離1の2件は種別（ともにREQ）
    # の次にIDの辞書順（REQ-002、REQ-003）に並ぶ。役割は表の上から最初に該当する行で、REQ-002は`refinement`、REQ-003は
    # `requirement`。どちらも距離1なので提示形式は`full`。目的`interpret`の対象規範文は空（§6.4）なので制約台帳は空である。
    "SINGLE-139": {"purpose": "interpret", "root": "REQ-001",
                   "documents": [("REQ-001", "root", "full", ["root"]),
                                 ("REQ-002", "refinement", "full", ["refines:REQ-001", "requires:REQ-003"]),
                                 ("REQ-003", "requirement", "full", ["requires:REQ-001"])],
                   "ledger": [], "tested": [], "addressed": [], "adjacent": [], "advisory": []},
    # 140は、起点がTASKの目的`implement`。TASK-001（距離0）が`addresses`するREQ-001を所有する文書として含め（距離1、
    # `addresses`で到達したREQなので役割`requirement`）、REQ-001:AC-01を具体化するTECH-002（距離2）と、TECH-002:AC-01を
    # 具体化するTECH-003（距離3）を、逆参照で推移的に加える（§6.1の4.、§6.3）。距離は閉包を作るときに辿ったエッジの段数
    # （§7の6.）で、具体化文書の距離は、具体化される規範文を所有する文書の距離+1になる。対象規範文は、TASKが`addresses`する
    # REQ-001:AC-01と、その具体化文書の規範文（§6.4の3.）で、制約台帳はこの3件を文書の順に収録する。TECH-002とTECH-003は
    # 距離2以上の具体化文書で、所有する規範文がすべて制約台帳にあるので、提示形式は`normative`（`context` §5）。
    # REQ-001は役割`requirement`なので`full`。カバレッジは、TASK-001がREQ-001:AC-01だけを`addresses`するので対応済みは1件、
    # 3件とも文書が`tests[].covers`で宣言するのでテスト済み。未対応のTECH-002:AC-01とTECH-003:AC-01が、
    # `CTX-COVERAGE-TASK-001`の警告になる。診断は、発生元の`path`の辞書順（TECH-002、TECH-003）に並ぶ。
    "SINGLE-140": {"purpose": "implement", "root": "TASK-001", "status": "passed_with_warnings",
                   "documents": [("TASK-001", "root", "full", ["root"]),
                                 ("REQ-001", "requirement", "full", ["addresses:TASK-001"]),
                                 ("TECH-002", "refinement", "normative", ["refines:TECH-002"]),
                                 ("TECH-003", "refinement", "normative", ["refines:TECH-003"])],
                   "ledger": ["REQ-001:AC-01", "TECH-002:AC-01", "TECH-003:AC-01"],
                   "tested": ["REQ-001:AC-01", "TECH-002:AC-01", "TECH-003:AC-01"], "addressed": ["REQ-001:AC-01"],
                   "adjacent": [], "advisory": [],
                   "diagnostics": [{"code": "CTX-COVERAGE-TASK-001", "severity": "warning",
                                    "resultStatus": "passed_with_warnings",
                                    "summary": f"implement対象のMUST {statement}を実装するTASKがありません",
                                    "source": {"kind": "file", "workspaceId": "root", "path": path}}
                                   for statement, path in (("TECH-002:AC-01", ".spec/technical/TECH-002.md"),
                                                           ("TECH-003:AC-01", ".spec/technical/TECH-003.md"))]},
    # 141は、置換済みの起点TECH-005（距離0）の目的`interpret`。TECH-005は役割`advisory`（表の`root`は置換済みの起点を除く）で
    # 提示形式`reference`、後継TECH-009は役割`replacement`で提示形式`full`である。TECH-009は起点から`supersedes`のエッジを
    # 1本辿った距離1（§7の6.）で、TECH-005が`requires`するTECH-007（役割`constraint`）も距離1なので、距離1の2件は
    # IDの辞書順（TECH-007、TECH-009）に並ぶ。ハッシュ値の材料の適用可能性は、TECH-005が`advisory`、TECH-009が
    # `replacement`、TECH-007が`applicable`（正規化仕様 §3.1）。目的`interpret`の制約台帳は空である。
    "SINGLE-141": {"purpose": "interpret", "root": "TECH-005",
                   "documents": [("TECH-005", "advisory", "reference", ["root"]),
                                 ("TECH-007", "constraint", "full", ["requires:TECH-005"]),
                                 ("TECH-009", "replacement", "full", ["supersedes:TECH-009"])],
                   "ledger": [], "tested": [], "addressed": [], "adjacent": [],
                   "advisory": ["TECH-005"], "replacement": ["TECH-009"]},
    # 142は、目的`implement`で、approvedのREQ-001:AC-01を`refines`する状態`draft`のTECH-005がある。`implement`は`refines`する
    # 状態`draft`の文書を閉包へ含めないので（関係・トレースモデル §6.1の末尾）、閉包はREQ-001だけで、役割`advisory`の文書はない。
    # 対象規範文は起点REQ-001の規範文REQ-001:AC-01だけ（§6.4の1.）で、TECH-005は具体化文書として加えない（`draft`は適用可能でない）。
    # TECH-005のテスト対応はREQ-001:AC-01を`covers`するが、閉包の文書ではないのでテスト済みに数えない（§8）。REQ-001自身は
    # テスト対応を持たないので、REQ-001:AC-01は未対応（対応するTASKがない）かつ未テストで、目的`implement`の`MUST`の
    # 未対応と未テストはどちらも警告になる（§8、診断レジストリの`CTX-COVERAGE-TASK-MUST`、`CTX-COVERAGE-TEST-MUST-IMPLEMENT`）。
    # 診断の順は、発生元（同じREQ-001.md）が同じなので、`code`の辞書順（`CTX-COVERAGE-TASK-001`、`CTX-COVERAGE-TEST-001`）。
    "SINGLE-142": {"purpose": "implement", "root": "REQ-001", "status": "passed_with_warnings",
                   "documents": [("REQ-001", "root", "full", ["root"])],
                   "ledger": ["REQ-001:AC-01"], "tested": [], "addressed": [], "adjacent": [], "advisory": [],
                   "diagnostics": [{"code": code, "severity": "warning", "resultStatus": "passed_with_warnings",
                                    "summary": summary,
                                    "source": {"kind": "file", "workspaceId": "root",
                                               "path": ".spec/requirements/REQ-001.md"}}
                                   for code, summary in (
                                       ("CTX-COVERAGE-TASK-001",
                                        "implement対象のMUST REQ-001:AC-01を実装するTASKがありません"),
                                       ("CTX-COVERAGE-TEST-001", "MUST REQ-001:AC-01がtestされていません"))]},
    # 143は、起点がTASKの目的`verify`。TASK-001（距離0）が`addresses`するREQ-001を所有する文書として含め（距離1、役割
    # `requirement`）、REQ-001を文書単位で`refines`する状態`draft`のTECH-005は閉包へ含めない（§6.1の末尾）。含めると
    # 適用可能でない文書を強い関係が要求することになり`CTX-STATE-001`の`blocked`になるが、`draft`の文書は閉包の外なので
    # 状態を検査しない（§10）。対象規範文はTASK-001が`addresses`するREQ-001:AC-01だけで、REQ-001のテスト対応が
    # テスト済みにする。TECH-005のテスト対応（tests/test_candidate.py）は閉包の外なのでコマンドへ入れない。
    "SINGLE-143": {"purpose": "verify", "root": "TASK-001",
                   "documents": [("TASK-001", "root", "full", ["root"]),
                                 ("REQ-001", "requirement", "full", ["addresses:TASK-001"])],
                   "ledger": ["REQ-001:AC-01"], "tested": ["REQ-001:AC-01"], "addressed": ["REQ-001:AC-01"],
                   "adjacent": [], "advisory": []},
    # 113の文書を起点にする検証対象は107-01、規範文を起点にする検証対象は次の展開を使う。
    "REQ-001:AC-01": {"purpose": "verify", "root": "REQ-001:AC-01",
                      "ledger": ["REQ-001:AC-01", "TECH-002:AC-01", "TECH-003:AC-01"], "advisory": []},
    "SINGLE-106-06": {"purpose": "verify", "root": "REQ-001",
                      "documents": [("REQ-001", "root", "full", ["root"]),
                                    ("TECH-010", "constraint", "full", ["requires:REQ-001"]),
                                    ("REQ-020", "requirement", "full", ["requires:TECH-010"])],
                      "ledger": ["REQ-001:AC-01", "REQ-001:AC-02"],
                      "tested": ["REQ-001:AC-01", "REQ-001:AC-02"],
                      "addressed": [], "adjacent": [], "advisory": []},
    # 詳細度`compact`は提示形式を`reference`へ統一するだけで、107-01と同じcorpus・目的・
    # 閉包を使うのでコンテキストのハッシュ値は変わらない（`bitz context`仕様 §5・§6）。
    "SINGLE-106-07": {"purpose": "verify", "root": "REQ-001", "detail": "compact",
                      "documents": [("REQ-001", "root", "reference", ["root"]),
                                    ("REQ-009", "requirement", "reference", ["requires:REQ-001"]),
                                    ("TECH-002", "refinement", "reference", ["refines:TECH-002"]),
                                    ("TECH-003", "refinement", "reference", ["refines:TECH-003"])],
                      "ledger": ["REQ-001:AC-01", "REQ-001:AC-02", "TECH-002:AC-01", "TECH-003:AC-01"],
                      "tested": ["REQ-001:AC-01", "REQ-001:AC-02", "TECH-002:AC-01", "TECH-003:AC-01"],
                      "addressed": [], "adjacent": [], "advisory": []},
}
KIND = {"REQ": "requirement", "TECH": "technical", "ADR": "decision", "TASK": "task"}


def documents(identifier):
    return {entry["path"]: entry for entry in CASES[identifier][0]()}


def by_id(identifier):
    return {entry["frontmatter"]["id"]: entry for entry in documents(identifier).values()}


def reviewed_inputs(identifier):
    inputs = {digest_reference.CONFIG_PATH: CONFIG.encode(),
              **{path: entry["bytes"] for path, entry in documents(identifier).items()}}
    for entry in documents(identifier).values():
        for test in entry["frontmatter"].get("tests", []):
            inputs[test["path"]] = TEST_BODY.encode()
    return inputs


def reviewed_manifest(identifier):
    _, argv, description = CASES[identifier]
    operation = argv[0]
    # `verify`は設定がインデックスに無いと起動前に停止するため、コミットせずステージする。
    operations = [{"op": "stage", "paths": ["."]}] if operation == "verify" else []
    return {"fixtureId": identifier, "description": description,
            "setup": {"git": True, "operations": operations},
            "invocation": {"runner": "bitz", "cwd": ".", "argv": list(argv), "env": {}},
            "expect": {"status": EXPANSIONS.get(identifier, {}).get("status", "passed"), "exitCode": 0,
                       "stdout": "json", "resultFile": f"expected/{operation}.json", "reportFileCount": 0}}


# --- 参照計算A: ハッシュ値の材料のリテラル ----------------------------------------------


def semantic(statement_id, text):
    return {"id": statement_id, "actor": "TargetSystem", "activation": {"kind": "ALWAYS", "text": None},
            "modality": "MUST", "reason": None, "operation": {"kind": "CONSTRAINT", "text": text},
            "extensions": []}


def digest_document(entry, advisory, replacement=()):
    value = entry["frontmatter"]
    identifier = value["id"]
    relations = {**EMPTY, **value.get("relations", {})}
    strong = sorted((key, target) for key in ("addresses", "refines", "requires", "supersedes")
                    for target in relations[key])
    return {
        "id": identifier, "workspaceId": "root", "kind": KIND[identifier.split("-")[0]],
        "status": value["status"],
        "applicability": ("advisory" if identifier in advisory
                          else "replacement" if identifier in replacement else "applicable"),
        "frontmatter": {"id": identifier, "title": value["title"], "status": value["status"],
                        "relations": relations, "implements": [], "tests": value.get("tests", []),
                        "verify": None, "changes": value.get("changes", [])},
        "bodyText": entry["body"],
        "statements": [semantic(*s) for s in sorted(entry["statements"])],
        "strongRelations": [{"relation": key, "target": target} for key, target in strong],
    }


def expansion(identifier, target=None):
    """`verify`は同じ起点の`context`の展開を使う。113だけは検証対象ごとに展開を選ぶ。"""
    if identifier == "SINGLE-113":
        return EXPANSIONS["SINGLE-107-01" if target == "REQ-001" else target]
    if identifier in {"SINGLE-107-02", "SINGLE-108-02"}:
        return EXPANSIONS[identifier.replace("-02", "-01")]
    return EXPANSIONS[identifier]


def context_documents(identifier, target=None):
    plan = expansion(identifier, target)
    if "documents" in plan:
        return [name for name, _, _, _ in plan["documents"]]
    # 規範文が起点の場合は、所有文書と到達した文書が、文書が起点の場合と同じである。
    return context_documents("SINGLE-107-01")


def reviewed_digest_input(identifier, target=None):
    plan = expansion(identifier, target)
    corpus = by_id(identifier)
    verify = plan["purpose"] == "verify"
    commands = [{"workspaceId": "root", "name": "default", "argv": ["/bin/true", "{tests}"], "cwd": "."}]
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": plan["purpose"], "requestWorkspaceId": "root", "roots": [plan["root"]],
        "workspaces": [{"id": "root", "path": "."}],
        "documents": [digest_document(corpus[name], plan["advisory"], plan.get("replacement", []))
                      for name in sorted(context_documents(identifier, target))],
        "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": "root", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": "root", "timeoutSeconds": 300}] if verify else [],
            "commands": commands if verify else [],
        },
    }


def context_digest(identifier, target=None):
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(identifier, target)))


# --- 完全期待結果 ---------------------------------------------------------------------


def bundle_frontmatter(value):
    """`bitz context`仕様 §5: 許可するフィールドを正規化し、空の関係のキーと空配列を省略する。"""
    result = {"id": value["id"], "title": value["title"], "status": value["status"]}
    relations = {key: targets for key, targets in value.get("relations", {}).items() if targets}
    if relations:
        result["relations"] = relations
    for key in ("implements", "tests", "changes"):
        if value.get(key):
            result[key] = value[key]
    return result


def bundle_document(identifier, name, role, projection, reached):
    entry = by_id(identifier)[name]
    value = {"id": name, "kind": KIND[name.split("-")[0]], "status": entry["frontmatter"]["status"],
             "role": role, "path": entry["path"], "projection": projection, "reachedBy": reached}
    if projection == "reference":
        value["expandable"] = True
    else:
        value["statementRefs"] = [statement_id for statement_id, _ in entry["statements"]]
    if projection == "full":
        value["frontmatter"] = bundle_frontmatter(entry["frontmatter"])
        value["bodyText"] = entry["body"]
    value["untrustedText"] = True
    return value


def reviewed_context(identifier):
    plan = EXPANSIONS[identifier]
    corpus = by_id(identifier)
    roles = {name: role for name, role, _, _ in plan["documents"]}
    texts = {sid: text for entry in corpus.values() for sid, text in entry["statements"]}
    ledger = [{"id": sid, "documentId": sid.split(":")[0], "documentRole": roles[sid.split(":")[0]],
               "modality": "MUST", "reason": None, "actor": "TargetSystem", "activation": {"kind": "ALWAYS"},
               "operation": {"kind": "CONSTRAINT", "text": texts[sid]}} for sid in plan["ledger"]]
    must = {"total": list(plan["ledger"]), "addressed": list(plan["addressed"]), "tested": list(plan["tested"]),
            "unaddressed": [s for s in plan["ledger"] if s not in plan["addressed"]],
            "untested": [s for s in plan["ledger"] if s not in plan["tested"]]}
    empty = {key: [] for key in ("total", "addressed", "tested", "unaddressed", "untested")}
    return {
        "schemaVersion": "1.0", "operation": "context", "status": plan.get("status", "passed"),
        "purpose": plan["purpose"],
        "workspace": {"id": "root", "path": "."}, "roots": [plan["root"]],
        "contextDigest": context_digest(identifier), "revision": None,
        "resolution": {"complete": True, "documentCount": len(plan["documents"]), "unresolvedStrongRelations": 0},
        "projection": {"detail": plan.get("detail", "standard"), "expanded": []},
        "documents": [bundle_document(identifier, *row) for row in plan["documents"]],
        "constraintLedger": {"statements": ledger},
        "coverage": {"must": must, "should": dict(empty), "may": dict(empty), "adjacent": list(plan["adjacent"])},
        "durationMs": 0, "diagnostics": list(plan.get("diagnostics", [])),
    }


def reviewed_verify(identifier):
    argv = CASES[identifier][1]
    targets = sorted({value for value in argv[1:] if not value.startswith("--") and value != "json"})
    corpus = by_id(identifier)
    results, tests, covers = [], set(), set()
    for target in targets:
        statements = expansion(identifier, target)["ledger"]
        results.append({"target": target, "status": "passed", "contextDigest": context_digest(identifier, target),
                        "statements": list(statements), "bindingRefs": ["root::default"], "diagnostics": []})
        closure = set(context_documents(identifier, target))
        for entry in corpus.values():
            if entry["frontmatter"]["id"] not in closure:
                continue
            for test in entry["frontmatter"].get("tests", []):
                if set(test["covers"]) & set(statements):
                    tests.add(test["path"])
                    covers.update(set(test["covers"]) & set(statements))
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "passed", "scope": "selected",
        "workspace": {"id": "root", "path": "."}, "targetResults": results, "revision": None,
        "commands": [{"bindingId": "root::default", "workspaceId": "root", "name": "default", "status": "passed",
                      "termination": "exit", "cwd": ".", "argv": ["/bin/true", *sorted(tests)],
                      "tests": sorted(tests), "covers": sorted(covers), "exitCode": 0, "timeoutSeconds": 300,
                      "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False,
                      "stderrTruncated": False, "durationMs": 0}],
        "durationMs": 0, "diagnostics": [],
    }


def reviewed_result(identifier):
    return reviewed_context(identifier) if CASES[identifier][1][0] == "context" else reviewed_verify(identifier)


# --- 検証 ---------------------------------------------------------------------------

LITERAL_SETS = {
    # 4つの集合を`context`の結果から独立に読み戻す。targets/cases.jsonの対応するtarget vectorと同じ内容である。
    "SINGLE-107-01": (["REQ-001"], ["REQ-001", "REQ-009", "TECH-002", "TECH-003"],
                      ["REQ-001:AC-01", "REQ-001:AC-02", "TECH-002:AC-01", "TECH-003:AC-01"], []),
    "SINGLE-108-01": (["TECH-001"], ["TECH-001", "TECH-004", "TECH-009"],
                      ["TECH-001:AC-01", "TECH-001:AC-02", "TECH-004:AC-01"], []),
    "SINGLE-109": (["REQ-001"], ["REQ-001", "TECH-002", "TASK-001"],
                   ["REQ-001:AC-01", "TECH-002:AC-01"], ["REQ-001:AC-02"]),
    "SINGLE-110": (["TASK-001"], ["TASK-001", "REQ-001"], ["REQ-001:AC-01"], []),
    "SINGLE-134": (["TASK-001"], ["TASK-001", "REQ-001", "TASK-002"], ["REQ-001:AC-01"], []),
    "SINGLE-135": (["REQ-001"], ["REQ-001", "REQ-002", "REQ-003"], ["REQ-001:AC-01"], []),
    "SINGLE-136": (["REQ-001"], ["REQ-001", "TECH-002", "TECH-003"], [], []),
    # 並びは距離（最短の段数）、種別、IDの順であり、139はREQ-002とREQ-003が距離1、141はTECH-007とTECH-009が距離1で、
    # 140は距離がTASK-001、REQ-001、TECH-002、TECH-003の順に0、1、2、3になる。
    "SINGLE-139": (["REQ-001"], ["REQ-001", "REQ-002", "REQ-003"], [], []),
    "SINGLE-140": (["TASK-001"], ["TASK-001", "REQ-001", "TECH-002", "TECH-003"],
                   ["REQ-001:AC-01", "TECH-002:AC-01", "TECH-003:AC-01"], []),
    "SINGLE-141": (["TECH-005"], ["TECH-005", "TECH-007", "TECH-009"], [], []),
    # 142は、`refines`する状態`draft`のTECH-005を含めないので、閉包は起点REQ-001だけである。
    "SINGLE-142": (["REQ-001"], ["REQ-001"], ["REQ-001:AC-01"], []),
}


# 目的`implement`と`verify`で、`refines`する状態`draft`の文書を閉包へ含めないfixture。
DRAFT_EXCLUDED = ("SINGLE-142", "SINGLE-143")

# 距離に基づく並びと提示形式、役割の要点（名前: (役割, 提示形式, reachedBy)）。
DISTANCE_CHECKS = {
    # 起点の`refines`の参照先は`requires`の鎖でも到達するが、距離は最短の1で、REQ-003と同じ距離1のまま`full`で提示する。
    "SINGLE-139": {"REQ-002": ("refinement", "full", ["refines:REQ-001", "requires:REQ-003"]),
                   "REQ-003": ("requirement", "full", ["requires:REQ-001"])},
    # 距離2以上で、所有する規範文がすべて制約台帳にある具体化文書だけが`normative`になる。
    "SINGLE-140": {"REQ-001": ("requirement", "full", ["addresses:TASK-001"]),
                   "TECH-002": ("refinement", "normative", ["refines:TECH-002"]),
                   "TECH-003": ("refinement", "normative", ["refines:TECH-003"])},
    # 置換済みの起点は`advisory`、後継は`replacement`で距離1。
    "SINGLE-141": {"TECH-005": ("advisory", "reference", ["root"]),
                   "TECH-007": ("constraint", "full", ["requires:TECH-005"]),
                   "TECH-009": ("replacement", "full", ["supersedes:TECH-009"])},
}


def check_draft_excluded(identifier, result):
    """目的`implement`と`verify`は、`refines`する状態`draft`の文書を閉包へ含めない（関係・トレースモデル §6.1の末尾）。
    結果のどこにも`draft`の文書（TECH-005）とそのテストが現れず、状態を理由に`blocked`にしない。"""
    text = json.dumps(result, ensure_ascii=False)
    if "TECH-005" in text or "test_candidate" in text:
        raise ValueError("目的`implement`と`verify`の結果へ、`refines`する状態`draft`の文書とそのテストを含めてはいけません")
    if "CTX-STATE-001" in text:
        raise ValueError("閉包へ含めない状態`draft`の文書の状態を検査して`CTX-STATE-001`にしてはいけません")
    if identifier == "SINGLE-142":
        if [d["id"] for d in result["documents"]] != ["REQ-001"] or any(
                d["role"] == "advisory" for d in result["documents"]):
            raise ValueError("`142`の閉包は役割`advisory`の文書を持たず、REQ-001だけである必要があります")
        if result["status"] != "passed_with_warnings" or [d["code"] for d in result["diagnostics"]] != [
                "CTX-COVERAGE-TASK-001", "CTX-COVERAGE-TEST-001"]:
            raise ValueError("`142`の診断は未対応と未テストの警告の2件だけである必要があります")
        must = result["coverage"]["must"]
        if must["tested"] != [] or must["untested"] != ["REQ-001:AC-01"]:
            raise ValueError("状態`draft`の文書のテスト対応をテスト済みに数えてはいけません")
        return
    target = result["targetResults"][0]
    if result["status"] != "passed" or target["status"] != "passed" or target["diagnostics"] or result["diagnostics"]:
        raise ValueError("`143`は診断なしで`passed`になる必要があります")
    if target["statements"] != ["REQ-001:AC-01"] or target["bindingRefs"] != ["root::default"]:
        raise ValueError("`143`の対象規範文は起点のTASKが`addresses`する規範文だけで、テスト割当ては1件である必要があります")
    command = result["commands"][0]
    if command["tests"] != ["tests/test_root.py"] or command["argv"] != ["/bin/true", "tests/test_root.py"]:
        raise ValueError("`143`のコマンドはREQ-001のテスト対応だけを実行する必要があります")


def four_sets(result):
    roots = sorted({root.split(":")[0] for root in result["roots"]})
    return (roots, [d["id"] for d in result["documents"]],
            [s["id"] for s in result["constraintLedger"]["statements"]], result["coverage"]["adjacent"])


def check_contract(identifier, result, root):
    """完全比較とは別に、裁定済みの展開規則を結果から直接確かめる。"""
    if identifier in LITERAL_SETS and four_sets(result) != LITERAL_SETS[identifier]:
        raise ValueError("4集合がレビュー済みの展開と異なります")
    if identifier in DRAFT_EXCLUDED:
        check_draft_excluded(identifier, result)
    if result["operation"] == "context":
        for entry in result["documents"]:
            if entry["role"] == "advisory" and entry["projection"] != "reference":
                raise ValueError("役割`advisory`の文書は提示形式`reference`で提示する必要があります")
        if identifier == "SINGLE-106-03":
            if [d["projection"] for d in result["documents"]] != ["full", "reference"]:
                raise ValueError("`106-03`は提示形式`reference`を1件含む必要があります")
            if result["constraintLedger"]["statements"]:
                raise ValueError("役割`advisory`の文書の規範文を制約台帳へ入れてはいけません")
        if identifier == "SINGLE-110" and any(d["id"] in {"TASK-002", "REQ-009"} for d in result["documents"]):
            raise ValueError("目的`verify`の起点TASKの`requires`の参照先とその`addresses`の参照先をコンテキストへ含めてはいけません")
        if identifier == "SINGLE-134":
            codes = [d["code"] for d in result["diagnostics"]]
            if codes != ["CTX-COVERAGE-TEST-001"] or result["status"] != "passed_with_warnings":
                raise ValueError("先行TASKがすべて`done`のとき、診断は未テストの`MUST`の警告1件だけである必要があります")
            if {d["id"]: d["role"] for d in result["documents"]}.get("TASK-002") != "work":
                raise ValueError("目的`implement`の起点TASKの`requires`の先行TASKは役割`work`でコンテキストへ含める必要があります")
        # 提示形式`normative`は本文を省くので、所有する規範文がすべて制約台帳にある文書だけに許す
        # （`bitz context`仕様 §5、ADR-014の`Decision`の4番目の項目）。
        ledger_ids = {s["id"] for s in result["constraintLedger"]["statements"]}
        for entry in result["documents"]:
            if entry["projection"] == "normative" and not set(entry["statementRefs"]) <= ledger_ids:
                raise ValueError("制約台帳にない規範文を持つ文書を提示形式`normative`にして`MUST`の本文を落としてはいけません")
        if identifier in {"SINGLE-135", "SINGLE-136"}:
            lookup = {d["id"]: d for d in result["documents"]}
            name, text = (("REQ-003", "秘密鍵を保持しない") if identifier == "SINGLE-135"
                          else ("TECH-003", "形式違反を拒否する"))
            target = lookup[name]
            if target["role"] != "refinement":
                raise ValueError(f"{name}は役割`refinement`である必要があります")
            if target["projection"] != "full" or text not in target.get("bodyText", ""):
                raise ValueError(f"{name}は提示形式`full`で、その`MUST`の本文が提示に現れる必要があります")
            if f"{name}:AC-01" in ledger_ids:
                raise ValueError(f"{name}:AC-01は対象規範文ではないので制約台帳へ収録してはいけません")
        if identifier in DISTANCE_CHECKS:
            lookup = {d["id"]: d for d in result["documents"]}
            for name, (role, projection, reached) in DISTANCE_CHECKS[identifier].items():
                entry = lookup[name]
                if (entry["role"], entry["projection"], entry["reachedBy"]) != (role, projection, reached):
                    raise ValueError(f"{name}の役割、提示形式、到達したエッジがレビュー済みの距離に基づく値と異なります")
        if identifier == "SINGLE-107-01" and "REQ-099" in [d["id"] for d in result["documents"]]:
            raise ValueError("`related`の参照先をコンテキストへ追加してはいけません")
        if identifier == "SINGLE-106-06":
            lookup = {d["id"]: d for d in result["documents"]}
            for name, role in (("TECH-010", "constraint"), ("REQ-020", "requirement")):
                if lookup[name]["role"] != role or lookup[name]["projection"] != "full":
                    raise ValueError("距離2以上の役割`requirement`または`constraint`の文書は提示形式`full`である必要があります")
            if "秘密鍵を保持しない" not in lookup["REQ-020"]["bodyText"]:
                raise ValueError("距離2の規範文の`MUST`の本文がコンテキスト一式へ現れる必要があります")
        if identifier == "SINGLE-106-07":
            if result["projection"]["detail"] != "compact":
                raise ValueError("`106-07`は詳細度`compact`を返す必要があります")
            if any(d["projection"] != "reference" for d in result["documents"]):
                raise ValueError("詳細度`compact`は全文書を提示形式`reference`にする必要があります")
            expected = json.loads((root / "single/SINGLE-107-01/expected/context.json").read_text())
            if result["contextDigest"] != expected["contextDigest"]:
                raise ValueError("詳細度`compact`はコンテキストのハッシュ値を変えてはいけません")
        return
    if identifier in DRAFT_EXCLUDED:
        return
    for target in result["targetResults"]:
        source = "SINGLE-113" if identifier == "SINGLE-113" else identifier.replace("-02", "-01")
        expected = (json.loads((root / "single/SINGLE-107-01/expected/context.json").read_text())
                    if identifier == "SINGLE-113" and target["target"] == "REQ-001"
                    else json.loads((root / f"single/{source}/expected/context.json").read_text())
                    if identifier != "SINGLE-113" else None)
        if expected is not None:
            if target["statements"] != [s["id"] for s in expected["constraintLedger"]["statements"]]:
                raise ValueError("`verify`の対象規範文が同じ起点の`context`と異なります")
            if target["contextDigest"] != expected["contextDigest"]:
                raise ValueError("`verify`のコンテキストのハッシュ値が同じ起点の`context`と異なります")
    if identifier == "SINGLE-113":
        if [t["target"] for t in result["targetResults"]] != ["REQ-001", "REQ-001:AC-01"]:
            raise ValueError("`113`は重複排除した2つの検証対象を辞書順で返す必要があります")
        if len(result["commands"]) != 1 or len(set(result["commands"][0]["tests"])) != len(result["commands"][0]["tests"]):
            raise ValueError("`113`は共有のテスト割当てを1回だけ、テストのパスを重複なしで実行する必要があります")


def check_git_state(identifier, repository):
    listed = set(git(repository, "ls-files", "-z").decode().split("\0")[:-1])
    expected = set(reviewed_inputs(identifier)) if CASES[identifier][1][0] == "verify" else set()
    if listed != expected:
        raise ValueError("インデックスのパスがレビュー済みの準備手順と異なります")
    try:
        git(repository, "rev-parse", "--verify", "HEAD")
    except subprocess.CalledProcessError:
        return
    raise ValueError("対象展開のfixtureはコミットを持ってはいけません")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads(schema_path(root, "frontmatter").read_text())
    kinds = {"REQ": "reqFrontmatter", "TECH": "techFrontmatter", "TASK": "taskFrontmatter"}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / manifest["expect"]["resultFile"]).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("起動条件または完全結果がレビュー済みの期待値と異なります")
            check_contract(identifier, result, root)
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            for path, entry in documents(identifier).items():
                parsed, _ = digest_crosscheck.split_document(inputs[path].decode())
                if parsed != json.loads(json.dumps(entry["frontmatter"])):
                    raise ValueError(f"{path}のフロントマターの値がレビュー済みの解釈と異なります")
                kind = kinds[entry["frontmatter"]["id"].split("-")[0]]
                Draft202012Validator({"$ref": "#/$defs/" + kind, "$defs": schema["$defs"]}).validate(parsed)
            if effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            argv = manifest["invocation"]["argv"]
            targets = ([argv[1]] if argv[0] == "context"
                       else sorted({v for v in argv[1:] if not v.startswith("--") and v != "json"}))
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-expansion-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    check_git_state(identifier, repository)
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
                    for target in targets:
                        purpose = expansion(identifier, target)["purpose"]
                        derived = digest_crosscheck.canonical_bytes(
                            digest_crosscheck.build(repository, root=target, purpose=purpose))
                        if derived != digest_reference.canonical_bytes(reviewed_digest_input(identifier, target)):
                            raise ValueError(f"{target}: 参照計算AとBの正規JSONが一致しません")
                        # 参照計算Bの閉包が、辿ったエッジによる最短の距離、種別、IDの順に並べた文書の並びも一致させる。
                        ordered, _ = digest_crosscheck.closure(
                            digest_crosscheck.load_documents(repository), target, purpose)
                        if ordered != context_documents(identifier, target):
                            raise ValueError(f"{target}: 参照計算Bが距離で並べた文書の並びがレビュー済みの並びと異なります")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
