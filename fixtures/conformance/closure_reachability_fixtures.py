"""閉包を、下方向の出発点から具体化を辿り上方向へ依存を辿る到達可能性で定める規則を固定する（Coreの公開操作は実行しない）。

実装の確認事項C106・C107・C112と、ADR-071 Decision 2の閉包の規則に対応する（ADR-051の追加）。閉包は、下方向の出発点（起点がREQ・TECH・ADRなら起点文書、
規範文なら所有文書、TASKならその`addresses`の参照先の所有文書）から`refines`の逆向きに具体化文書を辿り、出発点と具体化文書をSとして、Sから`requires`・`refines`・`addresses`の
参照先を、辺の種類を区別せず終端まで辿って得る。上方向の辺がSの文書へ戻る場合は、その文書へ着いたとはみなさず、役割・`reachedBy`・距離に使わない。
状態`draft`のadvisoryは、Sの文書またはその規範文を`refines`する文書だけで、上方向でも着く文書（起点のTASKの`requires`の上方向を含む）はadvisoryにせず、上方向で着いた文書として扱う
（強い関係を優先する。§6.1の6.）。TASKを起点にすると、目的`interpret`・`implement`・`verify`のすべてで、
`addresses`の参照先の所有文書を下方向の出発点にする。起点のTASKの`requires`は、`interpret`と`implement`では上方向の辺として閉包に含め、`verify`では
コンテキストに含めず、同じ範囲の文書（TASKとADRを除く）の適用可能性だけを検査する。目的`implement`の起点がTASKのとき、ほかの状態`open`のTASKは加えない。

| fixture | 操作 | 入力 | 期待 | 修正前のCore |
|---|---|---|---|---|
| `SINGLE-178-01` | `context TECH-003 --purpose interpret` | `TECH-003`が`TECH-002`を、`TECH-002`が`REQ-001`を`refines`し`REQ-002`を`requires`、`REQ-001`が`REQ-003`を`requires`する | 閉包は5文書。`refines`の参照先の`requires`と祖父の`refines`も辿る。役割は`TECH-002`と`REQ-001`が`refinement`、`REQ-002`と`REQ-003`が`requirement` | `TECH-003`と`TECH-002`だけ |
| `SINGLE-178-02` | `context TECH-004 --purpose interpret` | `TECH-004`→`TECH-003`（規範文あり）→`TECH-002`（規範文なし）→`REQ-001`（規範文あり）と`refines`が連なる | 上方向に`refines`で着いた文書は役割`refinement`。距離2で規範文を持たない`TECH-002`は`normative`、距離1の`TECH-003`と、規範文が制約台帳にない距離3の`REQ-001`は`full` | `TECH-004`と`TECH-003`だけ |
| `SINGLE-178-03` | `context REQ-001 --purpose interpret` | `TECH-010`が`REQ-001`と`REQ-002`を、`TECH-011`が`REQ-001`を`refines`し、`REQ-002`が`REQ-003`を`requires`する | 具体化文書`TECH-010`が`refines`する別の親`REQ-002`と、その`requires`の`REQ-003`も含める。`REQ-002`は役割`refinement` | `REQ-002`と`REQ-003`を含めない |
| `SINGLE-178-04` | `context TECH-010 --purpose interpret` | `SINGLE-178-03`と同じ入力 | `TECH-010`、`REQ-001`、`REQ-002`、`REQ-003`。兄弟の`TECH-011`を含めない | `REQ-003`を含めない |
| `SINGLE-178-05` | `context TECH-010 --purpose interpret` | `REQ-001`を`TECH-010`と`TECH-011`が`refines`する | `TECH-010`と`REQ-001`だけ。兄弟の`TECH-011`を含めない（対照） | 通る |
| `SINGLE-178-06` | `context REQ-001 --purpose interpret` | `TECH-010`・`TECH-011`が`REQ-001`を、`TECH-012`が`TECH-011`を、`TECH-013`が`TECH-012`を`refines`し、`TECH-010`が`REQ-001`と`TECH-013`を`requires`する | Sへ戻る`requires`の辺は着いたとみなさない。`TECH-013`は距離3で`reachedBy`は`refines:TECH-013`だけ。起点の役割は`root` | `TECH-013`の`reachedBy`に`requires:TECH-010`を加え、距離2 |
| `SINGLE-178-07` | `context REQ-001 --purpose interpret` | `SINGLE-178-06`から`TECH-010`の`requires`を除く | `SINGLE-178-06`と同じ文書、距離、`reachedBy`（対照） | 通る |
| `SINGLE-178-08` | `context TASK-001 --purpose interpret` | `TASK-001`が`REQ-001:AC-01`を`addresses`し、`TECH-010`が`REQ-001`を`refines`する | `REQ-001`は距離1、役割`requirement`、`reachedBy`は`addresses:TASK-001`だけ（`TECH-010`の`refines`が戻る辺で役割を`refinement`にしない）。`TECH-010`は距離2 | `TASK-001`だけ |
| `SINGLE-178-09` | `context TECH-001 --purpose interpret` | `TECH-001`が`REQ-001`を`refines`し、`draft`の`TECH-005`が`REQ-001`を、`draft`の`TECH-006`が`TECH-001`を`refines`する | advisoryは`TECH-006`だけ。上方向で着いた`REQ-001`の`draft`の具体化文書`TECH-005`は含めない | `TECH-005`も`advisory` |
| `SINGLE-178-10` | `context REQ-001 --purpose interpret` | `SINGLE-178-09`と同じ入力 | `TECH-005`と`TECH-006`がどちらもadvisory（`REQ-001`と`TECH-001`はS）（対照） | 通る |
| `SINGLE-178-11` | `context TASK-001 --purpose interpret` | `TASK-001`が`TASK-002`（`done`）を`requires`し`REQ-001:AC-01`を`addresses`。`REQ-001`が`REQ-004`を`requires`し、`TECH-002`が`REQ-001`を`refines`して`TECH-007`を`requires`。`TASK-002`が`REQ-009:AC-01`を`addresses`し、`REQ-009`が`REQ-008`を`requires`する | `addresses`の参照先の所有文書`REQ-001`と具体化文書`TECH-002`、先行TASK`TASK-002`が`addresses`する`REQ-009`と、それらの上方向の閉包を含める。ほかの状態`open`の`TASK-003`は含めない | `TASK-001`と`TASK-002`だけ |
| `SINGLE-178-12` | `context TASK-001 --purpose implement` | `SINGLE-178-11`と同じ入力。`REQ-001`は自身の規範文を`covers`するテスト対応を持つ | 閉包は`SINGLE-178-11`と同じ。先行TASKの`addresses`の参照先`REQ-009`は文書にあるが対象規範文にない。ほかの状態`open`の`TASK-003`を加えない | `REQ-004`・`TECH-002`などを含めない |
| `SINGLE-178-13` | `context REQ-001 --purpose implement` | `SINGLE-178-12`と同じ入力 | 対象規範文を`addresses`する状態`open`のTASK（`TASK-001`、`TASK-003`）を役割`work`で加え、`done`の`TASK-002`は加えない。加えたTASKからは辿らない（対照） | 通る |
| `SINGLE-178-14` | `context TASK-001 --purpose verify` | `SINGLE-178-11`と同じ入力で、`REQ-009`の状態が`outdated` | 先行TASKが`addresses`する`REQ-009`は適用可能性の検査の範囲なので、`CTX-STATE-001`（`blocked`）の1件。`REQ-009`をコンテキストに含めない | 検査せず通過 |
| `SINGLE-178-15` | `context TASK-001 --purpose verify` | `SINGLE-178-11`と同じ入力 | `REQ-009`・`REQ-008`・`TASK-002`をコンテキストに含めない。閉包は`TASK-001`、`REQ-001`、`REQ-004`、`TECH-002`、`TECH-007`（対照） | 通る |
| `SINGLE-178-16` | `context REQ-001 --purpose interpret` | `TECH-010`が`REQ-001`を`refines`して`TECH-020`を`requires`し、`draft`の`TECH-020`も`REQ-001`を`refines`する | 上方向の`requires`でも着く`draft`の`TECH-020`は`advisory`にせず、上方向で着いた文書として扱う。役割`constraint`、提示形式`full`、`reachedBy`は`requires:TECH-010`だけ、距離2（強い関係を優先する。§6.1の6.） | 通る（今の挙動の固定） |
| `SINGLE-178-17` | `context REQ-001 --purpose interpret` | `SINGLE-178-16`から`TECH-010`の`requires`を除く | 上方向で着かない`draft`の`TECH-020`は、Sの文書`REQ-001`を`refines`するので役割`advisory`、提示形式`reference`、`reachedBy`は`refines:TECH-020`（対照） | 通る |

期待値は、規範（関係・トレースモデル §6.1〜§6.3・§7、`context` §5、ADR-071 Decision 2）から導く。Coreの出力は根拠にしない。ハッシュ値の材料は、独立に書いた2系統の参照計算
（このモジュールのリテラルA、入力の木構造から導出するB。`digest_crosscheck`が`closure_reference`で閉包を導く）のバイト列の一致を要求する。
修正前のCoreは、`refines`の参照先を1段だけ含めてその`requires`を辿らず、閉包の全文書から`draft`のadvisoryを辿り、TASK起点の`interpret`と`implement`で
`addresses`の参照先の上方向を辿らず、`verify`で先行TASKの`addresses`の参照先の適用可能性を検査しなかった。欠陥は10件（01・02・03・04・06・08・09・11・12・14）、対照は7件である（16・17は、上方向でも着く`draft`の文書を`advisory`にしない今の挙動の固定で、修正前のCoreも通る）。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_crosscheck, digest_reference
from . import expansion_fixtures as ex
from .harness import git, setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
CONFIG = digest_reference.CONFIG
EMPTY = digest_reference.EMPTY_RELATIONS
KIND = ex.KIND
TEST_BODY = ex.TEST_BODY
STATEMENT_TEXT = "入力を検証する"
ROOT_TEST = {"path": "tests/test_root.py", "covers": ["REQ-001:AC-01"], "command": "default"}


# --- 入力 -------------------------------------------------------------------------------------

def entry(identifier, *, title="文書", status="approved", relations=None, statement=None, tested=False):
    """REQ（規範文`<ID>:AC-01`を1件持つ）、規範文を持つ（`statement`）または持たないTECH、TASKを組み立てる。`tested`はREQ-001のテスト対応を足す。"""
    relations = relations or {}
    fields = "".join(f"  {key}: [{', '.join(values)}]\n" for key, values in relations.items())
    fields = f"relations:\n{fields}" if fields else ""
    value = {"id": identifier, "title": title, "status": status}
    if relations:
        value["relations"] = relations
    kind = identifier.partition("-")[0]
    path = {"REQ": ".spec/requirements/", "TECH": ".spec/technical/", "TASK": ".spec/tasks/"}[kind] + identifier + ".md"
    if kind == "TASK":
        return ex.document(path, ex.task(identifier, title, status, fields), value, [])
    statements = [(f"{identifier}:AC-01", STATEMENT_TEXT)] if kind == "REQ" or statement else []
    if tested:
        fields += "tests:\n  - path: tests/test_root.py\n    covers: [REQ-001:AC-01]\n    command: default\n"
        value["tests"] = [dict(ROOT_TEST)]
    if kind == "REQ":
        head, body = ex.requirement(identifier, title, statements, fields)
        return ex.document(path, (head.replace("status: approved", f"status: {status}", 1), body), value, statements)
    if statements:
        return ex.document(path, ex.technical(identifier, title, statements, fields, status), value, statements)
    head = f"---\nid: {identifier}\ntitle: {title}\nstatus: {status}\n{fields}---\n"
    return ex.document(path, (head, f"# {identifier} {title}\n\n## Context\n\n規範文を持たない。\n"), value, [])


def corpus_ladder():
    """01: `TECH-003`が`TECH-002`を、`TECH-002`が`REQ-001`を`refines`し`REQ-002`を`requires`、`REQ-001`が`REQ-003`を`requires`する。"""
    return [entry("REQ-001", relations={"requires": ["REQ-003"]}), entry("REQ-002"), entry("REQ-003"),
            entry("TECH-002", relations={"refines": ["REQ-001"], "requires": ["REQ-002"]}),
            entry("TECH-003", relations={"refines": ["TECH-002"]})]


def corpus_presentation():
    """02: `TECH-004`（規範文なし）→`TECH-003`（規範文あり）→`TECH-002`（規範文なし）→`REQ-001`（規範文あり）と`refines`が連なる。"""
    return [entry("REQ-001"), entry("TECH-002", relations={"refines": ["REQ-001"]}),
            entry("TECH-003", relations={"refines": ["TECH-002"]}, statement=True),
            entry("TECH-004", relations={"refines": ["TECH-003"]})]


def corpus_two_parents():
    """03・04: `TECH-010`が`REQ-001`と`REQ-002`を、`TECH-011`が`REQ-001`を`refines`し、`REQ-002`が`REQ-003`を`requires`する。"""
    return [entry("REQ-001"), entry("REQ-002", relations={"requires": ["REQ-003"]}), entry("REQ-003"),
            entry("TECH-010", relations={"refines": ["REQ-001", "REQ-002"]}),
            entry("TECH-011", relations={"refines": ["REQ-001"]})]


def corpus_siblings():
    """05: `REQ-001`を`TECH-010`と`TECH-011`が`refines`する。"""
    return [entry("REQ-001"), entry("TECH-010", relations={"refines": ["REQ-001"]}), entry("TECH-011", relations={"refines": ["REQ-001"]})]


def corpus_returning(returning=True):
    """06・07: `TECH-010`・`TECH-011`が`REQ-001`を、`TECH-012`が`TECH-011`を、`TECH-013`が`TECH-012`を`refines`する。06は`TECH-010`が`REQ-001`と`TECH-013`を`requires`する（Sへ戻る辺）。"""
    ten = {"refines": ["REQ-001"], **({"requires": ["REQ-001", "TECH-013"]} if returning else {})}
    return [entry("REQ-001"), entry("TECH-010", relations=ten), entry("TECH-011", relations={"refines": ["REQ-001"]}),
            entry("TECH-012", relations={"refines": ["TECH-011"]}), entry("TECH-013", relations={"refines": ["TECH-012"]})]


def corpus_returning_task():
    """08: `TASK-001`が`REQ-001:AC-01`を`addresses`し、`TECH-010`が`REQ-001`を`refines`する。"""
    return [entry("REQ-001"), entry("TECH-010", relations={"refines": ["REQ-001"]}),
            entry("TASK-001", title="作業", status="open", relations={"addresses": ["REQ-001:AC-01"]})]


def corpus_draft():
    """09・10: `TECH-001`が`REQ-001`を`refines`し、`draft`の`TECH-005`が`REQ-001`を、`draft`の`TECH-006`が`TECH-001`を`refines`する。"""
    return [entry("REQ-001"), entry("TECH-001", relations={"refines": ["REQ-001"]}),
            entry("TECH-005", status="draft", relations={"refines": ["REQ-001"]}),
            entry("TECH-006", status="draft", relations={"refines": ["TECH-001"]})]


def corpus_draft_upward(required=True):
    """16・17: `TECH-010`が`REQ-001`を`refines`し、`draft`の`TECH-020`も`REQ-001`を`refines`する。16は`TECH-010`が`TECH-020`を`requires`する（上方向でも着く）。17は`requires`がない（対照）。"""
    ten = {"refines": ["REQ-001"], **({"requires": ["TECH-020"]} if required else {})}
    return [entry("REQ-001"), entry("TECH-010", relations=ten), entry("TECH-020", status="draft", relations={"refines": ["REQ-001"]})]


def corpus_task(outdated=False):
    """11〜15: `TASK-001`が`TASK-002`（`done`）を`requires`し`REQ-001:AC-01`を`addresses`する。`REQ-001`（テスト対応あり）は`REQ-004`を`requires`し、
    `TECH-002`が`REQ-001`を`refines`して`TECH-007`を`requires`する。`TASK-002`は`REQ-009:AC-01`を`addresses`し、`REQ-009`は`REQ-008`を`requires`する。
    `TASK-003`（`open`）も`REQ-001:AC-01`を`addresses`する。`outdated`は`REQ-009`の状態を`outdated`にする（14）。"""
    return [entry("REQ-001", relations={"requires": ["REQ-004"]}, tested=True), entry("REQ-004"),
            entry("REQ-008"), entry("REQ-009", status="outdated" if outdated else "approved", relations={"requires": ["REQ-008"]}),
            entry("TECH-002", relations={"refines": ["REQ-001"], "requires": ["TECH-007"]}), entry("TECH-007"),
            entry("TASK-001", title="作業", status="open", relations={"requires": ["TASK-002"], "addresses": ["REQ-001:AC-01"]}),
            entry("TASK-002", title="先行作業", status="done", relations={"addresses": ["REQ-009:AC-01"]}),
            entry("TASK-003", title="別の作業", status="open", relations={"addresses": ["REQ-001:AC-01"]})]


# id: (corpus, 引数列, 説明, 修正前のCoreが失敗する欠陥か)
CASES = {
    "SINGLE-178-01": (corpus_ladder, ["context", "TECH-003", "--purpose", "interpret", "--format", "json"],
                      "refinesの参照先のrequiresと祖父のrefinesも上方向に終端まで辿る", True),
    "SINGLE-178-02": (corpus_presentation, ["context", "TECH-004", "--purpose", "interpret", "--format", "json"],
                      "上方向にrefinesで着いた文書は役割refinementで、規範文が制約台帳にあるものだけnormativeにする", True),
    "SINGLE-178-03": (corpus_two_parents, ["context", "REQ-001", "--purpose", "interpret", "--format", "json"],
                      "具体化文書がrefinesする別の親と、その親のrequiresも含める", True),
    "SINGLE-178-04": (corpus_two_parents, ["context", "TECH-010", "--purpose", "interpret", "--format", "json"],
                      "具体化文書を起点にすると、兄弟の具体化文書を含めずrefinesの参照先のrequiresを辿る", True),
    "SINGLE-178-05": (corpus_siblings, ["context", "TECH-010", "--purpose", "interpret", "--format", "json"],
                      "対照: 具体化文書を起点にしても、同じ親をrefinesする兄弟の文書は含めない", False),
    "SINGLE-178-06": (corpus_returning, ["context", "REQ-001", "--purpose", "interpret", "--format", "json"],
                      "具体化文書の集合Sへ戻る上方向の辺は着いたとみなさず、reachedByと距離に使わない", True),
    "SINGLE-178-07": (lambda: corpus_returning(False), ["context", "REQ-001", "--purpose", "interpret", "--format", "json"],
                      "対照: Sへ戻る辺がなければ、具体化の鎖の文書は距離とreachedByがrefinesだけで決まる", False),
    "SINGLE-178-08": (corpus_returning_task, ["context", "TASK-001", "--purpose", "interpret", "--format", "json"],
                      "TASK起点のinterpretはaddressesの参照先の所有文書と具体化文書を含め、戻る辺で出発点の役割を変えない", True),
    "SINGLE-178-09": (corpus_draft, ["context", "TECH-001", "--purpose", "interpret", "--format", "json"],
                      "draftのadvisoryは下方向の出発点と具体化文書だけから辿り、上方向で着いた文書のdraftの具体化文書は含めない", True),
    "SINGLE-178-10": (corpus_draft, ["context", "REQ-001", "--purpose", "interpret", "--format", "json"],
                      "対照: 起点とその具体化文書をrefinesするdraftの文書はどちらもadvisoryにする", False),
    "SINGLE-178-11": (corpus_task, ["context", "TASK-001", "--purpose", "interpret", "--format", "json"],
                      "TASK起点のinterpretはaddressesの参照先の所有文書と具体化文書、先行TASKのaddressesの参照先とそれらの上方向の閉包を含める", True),
    "SINGLE-178-12": (corpus_task, ["context", "TASK-001", "--purpose", "implement", "--format", "json"],
                      "TASK起点のimplementは先行TASKのaddresses先を文書に含めて対象規範文に入れず、ほかのopenのTASKを加えない", True),
    "SINGLE-178-13": (corpus_task, ["context", "REQ-001", "--purpose", "implement", "--format", "json"],
                      "対照: REQ起点のimplementは対象規範文をaddressesするopenのTASKを役割workで加える", False),
    "SINGLE-178-14": (lambda: corpus_task(True), ["context", "TASK-001", "--purpose", "verify", "--format", "json"],
                      "TASK起点のverifyは先行TASKのaddresses先の適用可能性を検査し、適用できなければblockedにする", True),
    "SINGLE-178-15": (corpus_task, ["context", "TASK-001", "--purpose", "verify", "--format", "json"],
                      "対照: TASK起点のverifyは先行TASKのaddresses先と先行TASKをコンテキストに含めない", False),
    "SINGLE-178-16": (corpus_draft_upward, ["context", "REQ-001", "--purpose", "interpret", "--format", "json"],
                      "Sの文書をrefinesするdraftの文書でも、上方向のrequiresで着くならadvisoryにせず、上方向で着いた文書として扱う（強い関係を優先する）", False),
    "SINGLE-178-17": (lambda: corpus_draft_upward(False), ["context", "REQ-001", "--purpose", "interpret", "--format", "json"],
                      "対照: 上方向で着かないdraftの文書は、Sの文書をrefinesするのでadvisoryにする", False),
}
BLOCKED = {"SINGLE-178-14": ("REQ-009", "verify")}
PLANS_ROOT = {"SINGLE-178-14": "TASK-001"}


# --- レビュー済みの期待値（規範から導いたリテラル） -------------------------------------------------
#
# 文書は(ID, 役割, 提示形式, reachedBy)。並びは距離、種別の順（REQ、TECH、ADR、TASK）、IDの順。
# `reachedBy`は`<関係>:<関係を宣言した文書>`で、起点は`root`。ledgerは対象規範文、advisoryは役割`advisory`の文書。
PLANS = {
    "SINGLE-178-01": {"purpose": "interpret", "root": "TECH-003",
                      "documents": [("TECH-003", "root", "full", ["root"]),
                                    ("TECH-002", "refinement", "full", ["refines:TECH-003"]),
                                    ("REQ-001", "refinement", "full", ["refines:TECH-002"]),
                                    ("REQ-002", "requirement", "full", ["requires:TECH-002"]),
                                    ("REQ-003", "requirement", "full", ["requires:REQ-001"])]},
    "SINGLE-178-02": {"purpose": "interpret", "root": "TECH-004",
                      "documents": [("TECH-004", "root", "full", ["root"]),
                                    ("TECH-003", "refinement", "full", ["refines:TECH-004"]),
                                    ("TECH-002", "refinement", "normative", ["refines:TECH-003"]),
                                    ("REQ-001", "refinement", "full", ["refines:TECH-002"])]},
    "SINGLE-178-03": {"purpose": "interpret", "root": "REQ-001",
                      "documents": [("REQ-001", "root", "full", ["root"]),
                                    ("TECH-010", "refinement", "full", ["refines:TECH-010"]),
                                    ("TECH-011", "refinement", "full", ["refines:TECH-011"]),
                                    ("REQ-002", "refinement", "full", ["refines:TECH-010"]),
                                    ("REQ-003", "requirement", "full", ["requires:REQ-002"])]},
    "SINGLE-178-04": {"purpose": "interpret", "root": "TECH-010",
                      "documents": [("TECH-010", "root", "full", ["root"]),
                                    ("REQ-001", "refinement", "full", ["refines:TECH-010"]),
                                    ("REQ-002", "refinement", "full", ["refines:TECH-010"]),
                                    ("REQ-003", "requirement", "full", ["requires:REQ-002"])]},
    "SINGLE-178-05": {"purpose": "interpret", "root": "TECH-010",
                      "documents": [("TECH-010", "root", "full", ["root"]),
                                    ("REQ-001", "refinement", "full", ["refines:TECH-010"])]},
    "SINGLE-178-06": {"purpose": "interpret", "root": "REQ-001",
                      "documents": [("REQ-001", "root", "full", ["root"]),
                                    ("TECH-010", "refinement", "full", ["refines:TECH-010"]),
                                    ("TECH-011", "refinement", "full", ["refines:TECH-011"]),
                                    ("TECH-012", "refinement", "normative", ["refines:TECH-012"]),
                                    ("TECH-013", "refinement", "normative", ["refines:TECH-013"])]},
    "SINGLE-178-07": {"purpose": "interpret", "root": "REQ-001",
                      "documents": [("REQ-001", "root", "full", ["root"]),
                                    ("TECH-010", "refinement", "full", ["refines:TECH-010"]),
                                    ("TECH-011", "refinement", "full", ["refines:TECH-011"]),
                                    ("TECH-012", "refinement", "normative", ["refines:TECH-012"]),
                                    ("TECH-013", "refinement", "normative", ["refines:TECH-013"])]},
    "SINGLE-178-08": {"purpose": "interpret", "root": "TASK-001",
                      "documents": [("TASK-001", "root", "full", ["root"]),
                                    ("REQ-001", "requirement", "full", ["addresses:TASK-001"]),
                                    ("TECH-010", "refinement", "normative", ["refines:TECH-010"])]},
    "SINGLE-178-09": {"purpose": "interpret", "root": "TECH-001", "advisory": ["TECH-006"],
                      "documents": [("TECH-001", "root", "full", ["root"]),
                                    ("REQ-001", "refinement", "full", ["refines:TECH-001"]),
                                    ("TECH-006", "advisory", "reference", ["refines:TECH-006"])]},
    "SINGLE-178-10": {"purpose": "interpret", "root": "REQ-001", "advisory": ["TECH-005", "TECH-006"],
                      "documents": [("REQ-001", "root", "full", ["root"]),
                                    ("TECH-001", "refinement", "full", ["refines:TECH-001"]),
                                    ("TECH-005", "advisory", "reference", ["refines:TECH-005"]),
                                    ("TECH-006", "advisory", "reference", ["refines:TECH-006"])]},
    "SINGLE-178-11": {"purpose": "interpret", "root": "TASK-001",
                      "documents": [("TASK-001", "root", "full", ["root"]),
                                    ("REQ-001", "requirement", "full", ["addresses:TASK-001"]),
                                    ("TASK-002", "work", "full", ["requires:TASK-001"]),
                                    ("REQ-004", "requirement", "full", ["requires:REQ-001"]),
                                    ("REQ-009", "requirement", "full", ["addresses:TASK-002"]),
                                    ("TECH-002", "refinement", "normative", ["refines:TECH-002"]),
                                    ("REQ-008", "requirement", "full", ["requires:REQ-009"]),
                                    ("TECH-007", "constraint", "full", ["requires:TECH-002"])]},
    "SINGLE-178-12": {"purpose": "implement", "root": "TASK-001", "ledger": ["REQ-001:AC-01"], "tested": ["REQ-001:AC-01"],
                      "addressed": ["REQ-001:AC-01"],
                      "documents": [("TASK-001", "root", "full", ["root"]),
                                    ("REQ-001", "requirement", "full", ["addresses:TASK-001"]),
                                    ("TASK-002", "work", "full", ["requires:TASK-001"]),
                                    ("REQ-004", "requirement", "full", ["requires:REQ-001"]),
                                    ("REQ-009", "requirement", "full", ["addresses:TASK-002"]),
                                    ("TECH-002", "refinement", "normative", ["refines:TECH-002"]),
                                    ("REQ-008", "requirement", "full", ["requires:REQ-009"]),
                                    ("TECH-007", "constraint", "full", ["requires:TECH-002"])]},
    "SINGLE-178-13": {"purpose": "implement", "root": "REQ-001", "ledger": ["REQ-001:AC-01"], "tested": ["REQ-001:AC-01"],
                      "addressed": ["REQ-001:AC-01"],
                      "documents": [("REQ-001", "root", "full", ["root"]),
                                    ("REQ-004", "requirement", "full", ["requires:REQ-001"]),
                                    ("TECH-002", "refinement", "full", ["refines:TECH-002"]),
                                    ("TASK-001", "work", "full", ["addresses:TASK-001"]),
                                    ("TASK-003", "work", "full", ["addresses:TASK-003"]),
                                    ("TECH-007", "constraint", "full", ["requires:TECH-002"])]},
    "SINGLE-178-15": {"purpose": "verify", "root": "TASK-001", "ledger": ["REQ-001:AC-01"], "tested": ["REQ-001:AC-01"],
                      "addressed": ["REQ-001:AC-01"],
                      "documents": [("TASK-001", "root", "full", ["root"]),
                                    ("REQ-001", "requirement", "full", ["addresses:TASK-001"]),
                                    ("REQ-004", "requirement", "full", ["requires:REQ-001"]),
                                    ("TECH-002", "refinement", "normative", ["refines:TECH-002"]),
                                    ("TECH-007", "constraint", "full", ["requires:TECH-002"])]},
    "SINGLE-178-16": {"purpose": "interpret", "root": "REQ-001",
                      "documents": [("REQ-001", "root", "full", ["root"]),
                                    ("TECH-010", "refinement", "full", ["refines:TECH-010"]),
                                    ("TECH-020", "constraint", "full", ["requires:TECH-010"])]},
    "SINGLE-178-17": {"purpose": "interpret", "root": "REQ-001", "advisory": ["TECH-020"],
                      "documents": [("REQ-001", "root", "full", ["root"]),
                                    ("TECH-010", "refinement", "full", ["refines:TECH-010"]),
                                    ("TECH-020", "advisory", "reference", ["refines:TECH-020"])]},
}
# 4つの集合の要点: (rootDocuments, contextDocuments, targetStatements)。`context`の結果から独立に読み戻す。
LITERAL_SETS = {identifier: ([plan["root"].partition(":")[0]], [row[0] for row in plan["documents"]], plan.get("ledger", []))
                for identifier, plan in PLANS.items()}


# --- 入力と起動条件 ---------------------------------------------------------------------------

def documents(identifier):
    return {entry["path"]: entry for entry in CASES[identifier][0]()}


def by_id(identifier):
    return {entry["frontmatter"]["id"]: entry for entry in documents(identifier).values()}


def reviewed_inputs(identifier):
    inputs = {digest_reference.CONFIG_PATH: CONFIG.encode(), **{path: entry["bytes"] for path, entry in documents(identifier).items()}}
    for entry in documents(identifier).values():
        for test in entry["frontmatter"].get("tests", []):
            inputs[test["path"]] = TEST_BODY.encode()
    return inputs


def reviewed_manifest(identifier):
    _, argv, description, _ = CASES[identifier]
    blocked = identifier in BLOCKED
    return {"fixtureId": identifier, "description": description, "setup": {"git": True, "operations": []},
            "invocation": {"runner": "bitz", "cwd": ".", "argv": list(argv), "env": {}},
            "expect": {"status": "blocked" if blocked else "passed", "exitCode": 2 if blocked else 0, "stdout": "json",
                       "resultFile": "expected/context.json", "reportFileCount": 0}}


# --- 参照計算A: ハッシュ値の材料のリテラル ----------------------------------------------------

def digest_input(identifier):
    plan = PLANS[identifier]
    corpus = by_id(identifier)
    verify = plan["purpose"] == "verify"
    commands = [{"workspaceId": "root", "name": "default", "argv": ["/bin/true", "{tests}"], "cwd": "."}]
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": plan["purpose"], "requestWorkspaceId": "root", "roots": [plan["root"]],
        "workspaces": [{"id": "root", "path": "."}],
        "documents": [ex.digest_document(corpus[name], plan.get("advisory", []), []) for name in sorted(row[0] for row in plan["documents"])],
        "crossWorkspaceEdges": [],
        "settings": {"workspaces": [{"id": "root", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
                     "context": {"maxDocuments": 20, "maxBytes": 131072},
                     "verifyTimeouts": [{"workspaceId": "root", "timeoutSeconds": 300}] if verify else [],
                     "commands": commands if verify else []},
    }


def context_digest(identifier):
    return digest_reference.digest(digest_reference.canonical_bytes(digest_input(identifier)))


# --- 完全期待結果 -----------------------------------------------------------------------------

def bundle_document(identifier, name, role, projection, reached):
    entry = by_id(identifier)[name]
    value = {"id": name, "kind": KIND[name.split("-")[0]], "status": entry["frontmatter"]["status"], "role": role,
             "path": entry["path"], "projection": projection, "reachedBy": reached}
    if projection == "reference":
        value["expandable"] = True
    else:
        value["statementRefs"] = [statement_id for statement_id, _ in entry["statements"]]
    if projection == "full":
        value["frontmatter"] = ex.bundle_frontmatter(entry["frontmatter"])
        value["bodyText"] = entry["body"]
    value["untrustedText"] = True
    return value


def blocked_result(identifier):
    name, purpose = BLOCKED[identifier]
    status = by_id(identifier)[name]["frontmatter"]["status"]
    return {"schemaVersion": "1.0", "operation": "context", "status": "blocked", "purpose": purpose,
            "workspace": {"id": "root", "path": "."}, "roots": [PLANS_ROOT[identifier]], "contextDigest": None, "revision": None,
            "resolution": {"complete": False, "documentCount": 0, "unresolvedStrongRelations": 0},
            "projection": {"detail": "standard", "expanded": []}, "documents": [], "constraintLedger": {"statements": []},
            "coverage": {**{modality: {key: [] for key in ("total", "addressed", "tested", "unaddressed", "untested")}
                            for modality in ("must", "should", "may")}, "adjacent": []},
            "durationMs": 0,
            "diagnostics": [{"code": "CTX-STATE-001", "severity": "error", "resultStatus": "blocked",
                             "summary": f"{name}は状態{status}のため目的{purpose}に適用できません",
                             "source": {"kind": "file", "workspaceId": "root", "path": by_id(identifier)[name]["path"]}}]}


def reviewed_result(identifier):
    if identifier in BLOCKED:
        return blocked_result(identifier)
    plan = PLANS[identifier]
    corpus = by_id(identifier)
    roles = {name: role for name, role, _, _ in plan["documents"]}
    texts = {sid: text for entry in corpus.values() for sid, text in entry["statements"]}
    ledger = [{"id": sid, "documentId": sid.split(":")[0], "documentRole": roles[sid.split(":")[0]], "modality": "MUST", "reason": None,
               "actor": "TargetSystem", "activation": {"kind": "ALWAYS"}, "operation": {"kind": "CONSTRAINT", "text": texts[sid]}}
              for sid in plan.get("ledger", [])]
    wanted = plan.get("ledger", [])
    must = {"total": list(wanted), "addressed": list(plan.get("addressed", [])), "tested": list(plan.get("tested", [])),
            "unaddressed": [s for s in wanted if s not in plan.get("addressed", [])],
            "untested": [s for s in wanted if s not in plan.get("tested", [])]}
    empty = {key: [] for key in ("total", "addressed", "tested", "unaddressed", "untested")}
    return {"schemaVersion": "1.0", "operation": "context", "status": "passed", "purpose": plan["purpose"],
            "workspace": {"id": "root", "path": "."}, "roots": [plan["root"]], "contextDigest": context_digest(identifier), "revision": None,
            "resolution": {"complete": True, "documentCount": len(plan["documents"]), "unresolvedStrongRelations": 0},
            "projection": {"detail": "standard", "expanded": []},
            "documents": [bundle_document(identifier, *row) for row in plan["documents"]],
            "constraintLedger": {"statements": ledger},
            "coverage": {"must": must, "should": dict(empty), "may": dict(empty), "adjacent": []},
            "durationMs": 0, "diagnostics": []}


# --- 検証 ---------------------------------------------------------------------------------

def four_sets(result):
    roots = sorted({root.split(":")[0] for root in result["roots"]})
    return (roots, [d["id"] for d in result["documents"]], [s["id"] for s in result["constraintLedger"]["statements"]])


def check_contract(identifier, result):
    """完全比較とは別に、裁定済みの閉包の規則を結果から直接確かめる。"""
    if identifier in BLOCKED:
        codes = [d["code"] for d in result["diagnostics"]]
        name, _ = BLOCKED[identifier]
        if codes != ["CTX-STATE-001"] or result["status"] != "blocked" or name in json.dumps(result["documents"]) or result["contextDigest"] is not None:
            raise ValueError("先行TASKが`addresses`する文書が適用できないとき、`CTX-STATE-001`の1件だけで`blocked`にし、その文書をコンテキストに含めてはいけません")
        return
    if (list(four_sets(result)[0]), four_sets(result)[1], four_sets(result)[2]) != LITERAL_SETS[identifier]:
        raise ValueError("閉包と対象規範文がレビュー済みの集合と異なります")
    lookup = {d["id"]: d for d in result["documents"]}
    for entry in result["documents"]:
        if entry["role"] == "advisory" and entry["projection"] != "reference":
            raise ValueError("役割`advisory`の文書は提示形式`reference`で提示する必要があります")
        if entry["projection"] == "normative" and not set(entry["statementRefs"]) <= {s["id"] for s in result["constraintLedger"]["statements"]}:
            raise ValueError("制約台帳にない規範文を持つ文書を提示形式`normative`にしてはいけません")
    if identifier in {"SINGLE-178-04", "SINGLE-178-05"} and "TECH-011" in lookup:
        raise ValueError("具体化文書を起点にしたとき、兄弟の具体化文書を含めてはいけません")
    if identifier in {"SINGLE-178-06", "SINGLE-178-07"}:
        # Sへ戻る辺（`requires`）は着いたとみなさない。具体化の鎖の文書は`refines`の1件だけで到達する。
        if any(len(d["reachedBy"]) != 1 or not d["reachedBy"][0].startswith(("root", "refines:")) for d in result["documents"]):
            raise ValueError("Sへ戻る上方向の辺を`reachedBy`に記録してはいけません")
    if identifier == "SINGLE-178-08" and (lookup["REQ-001"]["role"], lookup["REQ-001"]["reachedBy"]) != ("requirement", ["addresses:TASK-001"]):
        raise ValueError("下方向の出発点の役割は、戻る`refines`の辺で`refinement`にしてはいけません")
    if identifier in {"SINGLE-178-09", "SINGLE-178-10"}:
        advisory = sorted(d["id"] for d in result["documents"] if d["role"] == "advisory")
        if advisory != PLANS[identifier]["advisory"]:
            raise ValueError("役割`advisory`の文書は、Sの文書またはその規範文を`refines`する`draft`の文書だけである必要があります")
    if identifier == "SINGLE-178-12":
        if "REQ-009:AC-01" in json.dumps(result["constraintLedger"]) or "TASK-003" in lookup:
            raise ValueError("先行TASKの`addresses`の参照先を対象規範文に入れず、ほかのTASKを加えてはいけません")
        if lookup["REQ-009"]["role"] != "requirement":
            raise ValueError("先行TASKの`addresses`の参照先は役割`requirement`で文書に含める必要があります")
    if identifier == "SINGLE-178-13" and {d["id"] for d in result["documents"] if d["role"] == "work"} != {"TASK-001", "TASK-003"}:
        raise ValueError("対象規範文を`addresses`する状態`open`のTASKだけを役割`work`で加える必要があります")
    if identifier == "SINGLE-178-16" and ([d["id"] for d in result["documents"] if d["role"] == "advisory"]
                                          or (lookup["TECH-020"]["role"], lookup["TECH-020"]["projection"], lookup["TECH-020"]["reachedBy"])
                                          != ("constraint", "full", ["requires:TECH-010"])):
        raise ValueError("上方向でも着く`draft`の文書は`advisory`にせず、上方向で着いた文書（役割`constraint`、`reachedBy`は`requires`だけ）として扱う必要があります")
    if identifier == "SINGLE-178-15" and {"REQ-009", "REQ-008", "TASK-002"} & set(lookup):
        raise ValueError("目的`verify`の起点TASKの`requires`の上方向の範囲をコンテキストに含めてはいけません")


def check_git_state(identifier, repository):
    if git(repository, "ls-files", "-z").decode().split("\0")[:-1]:
        raise ValueError("インデックスのパスがレビュー済みの準備手順と異なります")
    try:
        git(repository, "rev-parse", "--verify", "HEAD")
    except subprocess.CalledProcessError:
        return
    raise ValueError("対象展開のfixtureはコミットを持ってはいけません")


def reviewed_effects(state):
    return {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}


def generate(root=HERE, identifiers=None):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        (fixture / manifest["expect"]["resultFile"]).write_text(json.dumps(reviewed_result(identifier), ensure_ascii=False, indent=2) + "\n")
        with tempfile.TemporaryDirectory(prefix="bitz-closure-reachability-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(json.dumps(reviewed_effects(state), ensure_ascii=False, indent=2) + "\n")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text())) for name in ("manifest", "result", "side-effects")}
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
            check_contract(identifier, result)
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name] for name, p in files.items()):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            for path, item in documents(identifier).items():
                parsed, _ = digest_crosscheck.split_document(inputs[path].decode())
                if parsed != json.loads(json.dumps(item["frontmatter"])):
                    raise ValueError(f"{path}のフロントマターの値がレビュー済みの解釈と異なります")
                Draft202012Validator({"$ref": "#/$defs/" + kinds[item["frontmatter"]["id"].split("-")[0]], "$defs": schema["$defs"]}).validate(parsed)
            if effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            target = manifest["invocation"]["argv"][1]
            with tempfile.TemporaryDirectory(prefix="bitz-closure-reachability-") as temporary:
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
                    if identifier in BLOCKED:
                        continue
                    purpose = PLANS[identifier]["purpose"]
                    derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository, root=target, purpose=purpose))
                    if derived != digest_reference.canonical_bytes(digest_input(identifier)):
                        raise ValueError(f"{target}: 参照計算AとBの正規JSONが一致しません")
                    ordered, advisory = digest_crosscheck.closure(digest_crosscheck.load_documents(repository), target, purpose)
                    if ordered != [row[0] for row in PLANS[identifier]["documents"]] or sorted(advisory) != PLANS[identifier].get("advisory", []):
                        raise ValueError(f"{target}: 参照計算Bの閉包の並びがレビュー済みの並びと異なります")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run", "references": 2,
            "status": "Passed" if not errors else "Failed", "errors": errors}
