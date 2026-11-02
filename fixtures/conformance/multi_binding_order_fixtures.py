"""複合ワークスペースのテスト割当ての実行の順と`commands[]`の並びを固定する（Coreの公開操作は実行しない）。

実装の確認事項C62・C61に対応する。`verify`はテスト割当てを、ワークスペースID・コマンド名の素の辞書順で実行し、単独の操作の`commands[]`も同じ順に並べていた。
ルートワークスペースのIDがメンバーのIDより辞書順で後ろ（または間）にあると、ルートのテスト割当てより先にメンバーのテスト割当てを実行し、
`verify` §4の6.・§10の「ルートワークスペースを先頭、その後をワークスペースIDの辞書順」と食い違った。

- `verify` §4の6.: ワークスペースの処理順、コマンド名の辞書順でテスト割当てを逐次実行する。ワークスペースの処理順は、複合ワークスペースではルートワークスペースを先頭、
  その後をワークスペースIDの辞書順とし、単独の操作でも`--all-workspaces`（§10）と同じとする。起点のワークスペースを先頭にはしない。
- `verify` §8: `commands[]`は§4の6.の実行の順に並べる。`tests`と`covers`は、重複なしの辞書順とする。複合ワークスペースの中では`covers`のIDを修飾IDで返す。
  一方、`targetResults[].bindingRefs`は「重複なし辞書順」であり、実行の順とは別の並びである。
- `verify` §10: `--all-workspaces`はルートワークスペースを先頭、その後をワークスペースIDの辞書順に処理し、各ワークスペースの`commands[]`にそのワークスペースが所有するコマンドを置く。
- 複合ワークスペース仕様 §8・結果・診断・終了コード §2: ワークスペースの結果の並びは、ルートワークスペースを先頭、その後をワークスペースIDの辞書順。

実行の順の観測。適合fixtureの副作用の方針は`read-only`と`explicit-report`だけで、テストのコマンドが追記したファイルの内容を期待値にはできない。そこで、各コマンドが
共有の連番ファイル（環境変数`TMPDIR`の下。ランナーは空の外部ディレクトリを渡す）を読んで1を足し、`<ラベル> <連番>`を標準出力へ出力し、全コマンドの最後（連番が総数に達したとき）に
そのファイルを削除する。標準出力は`commands[].stdoutExcerpt`に入るので、実行の順が結果の完全一致で固定される。実行前後の状態は同じになる（`read-only`の前後の比較を満たす）。
コマンドは各ワークスペースのルートの`seq.sh`（実行ビットなし）を`/bin/sh`で起動する。`argv`は`["/bin/sh", "seq.sh", <ワークスペース>::<コマンド名>, <総数>, "{tests}"]`である。

| fixture | 操作と実行ディレクトリ | 構成 | 期待 |
|---|---|---|---|
| `MULTI-052-01` | `verify --all-workspaces`、`.` | ルート`zeta`、メンバー`beta`・`alpha`（この順で宣言）。ルートのコマンドは`b`・`a`。`REQ-001`を`alpha`、`REQ-002`を`beta`の`TECH-001`が具体化する | 実行は`zeta::a`、`zeta::b`、`alpha::t`、`beta::t`の順。修正前は`alpha::t`が先頭 |
| `MULTI-052-02` | `verify REQ-001`、`.`（ルート） | ルート`zeta`、メンバー`beta`・`alpha`。ルートの`REQ-001`を`alpha`と`beta`の`TECH-001`が具体化し、3つのワークスペースのテスト割当てを要求する | `commands[]`は実行の順（`zeta::a`、`zeta::b`、`alpha::t`、`beta::t`）。`bindingRefs`は辞書順（`alpha::t`が先頭） |
| `MULTI-052-03` | `verify --workspace beta beta::REQ-201`、`.` | メンバー`beta`の`REQ-201`を、ルート`zeta`とメンバー`alpha`の具体化文書が`refines`する | 起点のワークスペース`beta`を先頭にせず、`zeta::a`、`alpha::t`、`beta::t`の順 |
| `MULTI-052-04` | `verify REQ-001`、`.`（ルート） | ルート`zeta`だけがテスト割当てを持つ。宣言の順を辞書順の逆にした`tests`と`covers`（メンバー`alpha`の規範文の`covers`を含む） | `tests`と`covers`は修飾IDの辞書順。修正前も同じ（対照） |
| `MULTI-052-05` | `verify --all-workspaces`、`.` | `MULTI-052-01`と同じ形で、ルート`aaa`、メンバー`ccc`・`bbb`（対照。ルートが辞書順で最初） | 実行は`aaa::a`、`aaa::b`、`bbb::t`、`ccc::t`の順。修正前も同じ |
| `MULTI-052-06` | `verify --all-workspaces`、`.` | `MULTI-052-01`と同じ形で、ルート`mid`、メンバー`zeta`・`alpha`（ルートが辞書順で間） | 実行は`mid::a`、`mid::b`、`alpha::t`、`zeta::t`の順。修正前は`alpha::t`が先頭 |

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。参照計算は、準備手順の後の入力の木構造から、検証対象ごとの規範文とテスト割当てを導き、
ワークスペースの処理順（ルート先頭、その後はID辞書順）、コマンド名の辞書順で実行の順を導く。さらに、修正前の並び（`(ワークスペースID, コマンド名)`の素の辞書順）を導き、
欠陥を持つ4件では実行の順と異なること（この入力が欠陥を検出できること）、対照では同じであることを要求する。ハッシュ値は、独立に書いた2系統の参照計算
（このモジュールのリテラルA、入力の木構造から導出するB。`multi_crosscheck`）のバイト列の一致を要求する。

全体の操作の構成（`MULTI-052-01`・`05`・`06`）は、ルートの`REQ-001`と`REQ-002`をそれぞれ別のメンバーの`TECH-001`が具体化し、どの検証対象の閉包も、その検証対象と
具体化関係でつながる1件の相手だけにする。関係・トレースモデル §6.1は、閉包の逆参照の出発点を起点を所有する文書だけとするので、メンバーの`TECH-001`を起点にした閉包は
ルートの`REQ`を含むが、同じ`REQ`を具体化する別のメンバーの文書を含まない。参照計算Bの閉包（`multi_crosscheck.closure`）は、`refines`の参照先からも逆参照を辿るため、
同じ`REQ`を具体化する文書が複数あると別のメンバーの文書まで含めてしまい、規範と異なる。この群は、その構成を避け、閉包をリテラルで書いて参照計算Bの閉包と照合する。
単独の操作（`MULTI-052-02`・`03`）は起点を所有する文書から逆参照を辿るので、複数の具体化文書を持つ構成にできる。
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import (multi_closure_alias_fixtures as alias, multi_context_order_fixtures as order, multi_crosscheck, multi_reference,
               multi_verify_fixtures as verify_fixtures)
from .harness import setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = alias.COMMIT
TEST_BYTES = alias.TEST_BYTES
SEQ_PATH = "seq.sh"
SEQ_SCRIPT = (
    'f="$TMPDIR/bitz-order"\n'
    'n=$(cat "$f" 2>/dev/null)\n'
    "n=$((${n:-0} + 1))\n"
    "printf '%s %s\\n' \"$1\" \"$n\"\n"
    'if [ "$n" = "$2" ]; then rm -f "$f"; else printf \'%s\\n\' "$n" > "$f"; fi\n'
)
KIND_DIRECTORY = order.KIND_DIRECTORY
TITLE = "認証の基準"
STATEMENT_TEXT = "秘密情報を出力しない"


def workspace_path(root, workspace):
    return "." if workspace == root else f"apps/{workspace}"


def kind_of(local):
    return {"REQ": "requirement", "TECH": "technical"}[local.partition("-")[0]]


# --- 構成（ワークスペースごとの文書とコマンド。宣言どおりの表記で書く） ---------------------------------------------
#
# 文書: {(ワークスペース, ローカルID): dict(title, refines=宣言した参照, statements=[(ラベル, 文)], tests=[(パス, covers（宣言どおり）, コマンド名)])}。
# コマンド: {ワークスペース: [コマンド名（設定に書く順）]}。


def sibling_shape(root, low, high):
    """ルートの`REQ-001`（AC-01、AC-02）を、`low`の`TECH-001`が`AC-01`、`high`の`TECH-001`が`AC-02`について具体化する（どちらも規範文なし）。
    ルートのコマンドは`b`、`a`の順に宣言し、`tests`の宣言も`b`が先。単独の操作の起点は`REQ-001`で、閉包は3つの文書すべてを含む。"""
    documents = {
        (root, "REQ-001"): dict(title=TITLE, statements=[("AC-01", STATEMENT_TEXT), ("AC-02", "入力を検証する")],
                                tests=[("tests/b.py", ["REQ-001:AC-02", "REQ-001:AC-01"], "b"), ("tests/a.py", ["REQ-001:AC-02"], "a")]),
        (low, "TECH-001"): dict(title="AC-01の実装方針", refines=[f"{root}::REQ-001:AC-01"],
                                tests=[("tests/t.py", [f"{root}::REQ-001:AC-01"], "t")]),
        (high, "TECH-001"): dict(title="AC-02の実装方針", refines=[f"{root}::REQ-001:AC-02"],
                                 tests=[("tests/t.py", [f"{root}::REQ-001:AC-02"], "t")]),
    }
    commands = {root: ["b", "a"], low: ["t"], high: ["t"]}
    return documents, commands, {f"{root}::REQ-001": sorted(f"{workspace}::{local}" for workspace, local in documents)}


def pair_shape(root, low, high):
    """全体の操作の構成。ルートの`REQ-001`（AC-01、AC-02）を`low`の`TECH-001`が、ルートの`REQ-002`（AC-01）を`high`の`TECH-001`が具体化する（どちらも規範文なし）。
    `REQ-001`は具体化文書を1件だけ持つので、どの検証対象の閉包も、その検証対象と、具体化関係でつながる1件の相手だけからなる（関係・トレースモデル §6.1）。
    ルートのコマンドは`b`、`a`の順に宣言し、`tests`の宣言も`b`が先。`REQ-002`のテスト対応は`high`の`TECH-001`が宣言する。"""
    documents = {
        (root, "REQ-001"): dict(title=TITLE, statements=[("AC-01", STATEMENT_TEXT), ("AC-02", "入力を検証する")],
                                tests=[("tests/b.py", ["REQ-001:AC-02", "REQ-001:AC-01"], "b"), ("tests/a.py", ["REQ-001:AC-02"], "a")]),
        (root, "REQ-002"): dict(title="監査の基準", statements=[("AC-01", "監査logを記録する")]),
        (low, "TECH-001"): dict(title="REQ-001:AC-01の実装方針", refines=[f"{root}::REQ-001:AC-01"],
                                tests=[("tests/t.py", [f"{root}::REQ-001:AC-01"], "t")]),
        (high, "TECH-001"): dict(title="REQ-002:AC-01の実装方針", refines=[f"{root}::REQ-002:AC-01"],
                                 tests=[("tests/t.py", [f"{root}::REQ-002:AC-01"], "t")]),
    }
    commands = {root: ["b", "a"], low: ["t"], high: ["t"]}
    closure = {f"{root}::REQ-001": [f"{root}::REQ-001", f"{low}::TECH-001"], f"{root}::REQ-002": [f"{root}::REQ-002", f"{high}::TECH-001"],
               f"{low}::TECH-001": [f"{root}::REQ-001", f"{low}::TECH-001"], f"{high}::TECH-001": [f"{root}::REQ-002", f"{high}::TECH-001"]}
    return documents, commands, {target: sorted(names) for target, names in closure.items()}


def member_shape():
    """起点は`beta`の`REQ-201`。ルート`zeta`の`TECH-900`と`alpha`の`TECH-100`が、`beta::REQ-201:AC-01`を具体化する（どちらも規範文なし）。"""
    documents = {
        ("beta", "REQ-201"): dict(title=TITLE, statements=[("AC-01", STATEMENT_TEXT)], tests=[("tests/t.py", ["REQ-201:AC-01"], "t")]),
        ("zeta", "TECH-900"): dict(title="ルートの具体化", refines=["beta::REQ-201:AC-01"], tests=[("tests/z.py", ["beta::REQ-201:AC-01"], "a")]),
        ("alpha", "TECH-100"): dict(title="alphaの具体化", refines=["beta::REQ-201:AC-01"], tests=[("tests/t.py", ["beta::REQ-201:AC-01"], "t")]),
    }
    return documents, {"zeta": ["a"], "alpha": ["t"], "beta": ["t"]}, {"beta::REQ-201": sorted(f"{workspace}::{local}" for workspace, local in documents)}


def sorted_shape():
    """ルート`zeta`だけがテスト割当てを持つ。`tests`と`covers`の宣言の順は、辞書順の逆にする（`z2.py`が先、`covers`は`REQ-001:AC-02`、`alpha::TECH-001:C-01`、`REQ-001:AC-01`の順）。
    `alpha`の`TECH-001`は規範文`C-01`を持ち、`REQ-001:AC-01`を具体化する。その規範文のテスト対応はルートの`REQ-001`が宣言する。"""
    documents = {
        ("zeta", "REQ-001"): dict(title=TITLE, statements=[("AC-01", STATEMENT_TEXT), ("AC-02", "入力を検証する")],
                                  tests=[("tests/z2.py", ["REQ-001:AC-02", "alpha::TECH-001:C-01"], "a"), ("tests/z1.py", ["REQ-001:AC-01"], "a")]),
        ("alpha", "TECH-001"): dict(title="AC-01の実装方針", refines=["zeta::REQ-001:AC-01"], statements=[("C-01", "結果を記録する")]),
    }
    return documents, {"zeta": ["a"]}, {"zeta::REQ-001": ["alpha::TECH-001", "zeta::REQ-001"]}


# id: 説明、操作の引数、ルートのID、カタログの宣言の順のメンバー、構成、欠陥を検出するか。`target`は単独の操作の起点（修飾ID）。
CASES = {
    "MULTI-052-01": dict(argv=["verify", "--all-workspaces"], root="zeta", members=["beta", "alpha"], shape=lambda: pair_shape("zeta", "alpha", "beta"),
                         target=None, defect=True,
                         description="全体のverifyは、ルートのIDが辞書順で最後でも、ルートのテスト割当てを先頭に実行し、その後をID辞書順、コマンド名の辞書順で実行する"),
    "MULTI-052-02": dict(argv=["verify", "REQ-001"], root="zeta", members=["beta", "alpha"], shape=lambda: sibling_shape("zeta", "alpha", "beta"),
                         target="zeta::REQ-001", defect=True,
                         description="単独のverifyのcommandsは、ルートのIDが辞書順で最後でも、ルートのテスト割当てを先頭に、その後をID辞書順に並べ、bindingRefsは辞書順のままにする"),
    "MULTI-052-03": dict(argv=["verify", "--workspace", "beta", "beta::REQ-201"], root="zeta", members=["beta", "alpha"], shape=member_shape,
                         target="beta::REQ-201", defect=True,
                         description="メンバーを起点にした単独のverifyも、起点のワークスペースを先頭にせず、ルートを先頭にID辞書順でテスト割当てを実行する"),
    "MULTI-052-04": dict(argv=["verify", "REQ-001"], root="zeta", members=["alpha"], shape=sorted_shape, target="zeta::REQ-001", defect=False, unsorted=True,
                         description="対照: commandsのtestsとcoversは、宣言の順ではなく（修飾IDの）重複なし辞書順に並べる。修正の前後で同じ"),
    "MULTI-052-05": dict(argv=["verify", "--all-workspaces"], root="aaa", members=["ccc", "bbb"], shape=lambda: pair_shape("aaa", "bbb", "ccc"),
                         target=None, defect=False,
                         description="対照: ルートのIDが辞書順で最初なら、全体のverifyはルート、メンバーのID辞書順に実行する。修正の前後で同じ"),
    "MULTI-052-06": dict(argv=["verify", "--all-workspaces"], root="mid", members=["zeta", "alpha"], shape=lambda: pair_shape("mid", "alpha", "zeta"),
                         target=None, defect=True,
                         description="全体のverifyは、ルートのIDが辞書順でメンバーの間にあっても、ルートのテスト割当てを先頭に実行する"),
}



def is_all(identifier):
    return "--all-workspaces" in CASES[identifier]["argv"]


def workspace_ids(identifier):
    case = CASES[identifier]
    return [case["root"], *sorted(case["members"])]


def total_of(identifier):
    return len(literal_order(identifier))


# --- レビュー済みの期待値（リテラル。参照計算の結果と一致することを要求する） ------------------------------
#
# 実行の順（規範から: ルート先頭、その後はID辞書順、同じワークスペースの中はコマンド名の辞書順）。
def _sibling_expected(root, low, high):
    order_ = [f"{root}::a", f"{root}::b", f"{low}::t", f"{high}::t"]
    bindings = {
        f"{root}::a": (["tests/a.py"], [f"{root}::REQ-001:AC-02"]),
        f"{root}::b": (["tests/b.py"], [f"{root}::REQ-001:AC-01", f"{root}::REQ-001:AC-02"]),
        f"{low}::t": (["tests/t.py"], [f"{root}::REQ-001:AC-01"]),
        f"{high}::t": (["tests/t.py"], [f"{root}::REQ-001:AC-02"]),
    }
    # `bindingRefs`は重複なし辞書順であり、実行の順とは別の並びである。
    targets = {f"{root}::REQ-001": ([f"{root}::REQ-001:AC-01", f"{root}::REQ-001:AC-02"], sorted(order_))}
    return order_, bindings, targets


def _pair_expected(root, low, high):
    order_ = [f"{root}::a", f"{root}::b", f"{low}::t", f"{high}::t"]
    bindings = {
        f"{root}::a": (["tests/a.py"], [f"{root}::REQ-001:AC-02"]),
        f"{root}::b": (["tests/b.py"], [f"{root}::REQ-001:AC-01", f"{root}::REQ-001:AC-02"]),
        f"{low}::t": (["tests/t.py"], [f"{root}::REQ-001:AC-01"]),
        f"{high}::t": (["tests/t.py"], [f"{root}::REQ-002:AC-01"]),
    }
    targets = {
        f"{root}::REQ-001": ([f"{root}::REQ-001:AC-01", f"{root}::REQ-001:AC-02"], sorted([f"{root}::a", f"{root}::b", f"{low}::t"])),
        f"{root}::REQ-002": ([f"{root}::REQ-002:AC-01"], [f"{high}::t"]),
        f"{low}::TECH-001": ([], [f"{low}::t"]),
        f"{high}::TECH-001": ([], [f"{high}::t"]),
    }
    return order_, bindings, targets


EXPECTED = {
    "MULTI-052-01": _pair_expected("zeta", "alpha", "beta"),
    "MULTI-052-02": _sibling_expected("zeta", "alpha", "beta"),
    "MULTI-052-03": (
        ["zeta::a", "alpha::t", "beta::t"],
        {"zeta::a": (["tests/z.py"], ["beta::REQ-201:AC-01"]), "alpha::t": (["tests/t.py"], ["beta::REQ-201:AC-01"]),
         "beta::t": (["tests/t.py"], ["beta::REQ-201:AC-01"])},
        {"beta::REQ-201": (["beta::REQ-201:AC-01"], ["alpha::t", "beta::t", "zeta::a"])}),
    "MULTI-052-04": (
        ["zeta::a"],
        {"zeta::a": (["tests/z1.py", "tests/z2.py"], ["alpha::TECH-001:C-01", "zeta::REQ-001:AC-01", "zeta::REQ-001:AC-02"])},
        {"zeta::REQ-001": (["alpha::TECH-001:C-01", "zeta::REQ-001:AC-01", "zeta::REQ-001:AC-02"], ["zeta::a"])}),
    "MULTI-052-05": _pair_expected("aaa", "bbb", "ccc"),
    "MULTI-052-06": _pair_expected("mid", "alpha", "zeta"),
}


def literal_order(identifier):
    return EXPECTED[identifier][0]


def expected_targets(identifier):
    """期待する検証対象: 全体の操作はすべての文書、単独の操作は起点の1件。"""
    targets = EXPECTED[identifier][2]
    case = CASES[identifier]
    return targets if case["target"] is None else {case["target"]: targets[case["target"]]}


def defective_order(identifier):
    """修正前の並び: `(ワークスペースID, コマンド名)`の素の辞書順（欠陥の再現。期待値の根拠にしない）。"""
    return sorted(EXPECTED[identifier][0], key=lambda binding: tuple(binding.split("::")))


# --- 入力 -------------------------------------------------------------------------------

def render(local, spec):
    """文書の(ファイルの全文, 正規化した本文)。"""
    head = f"---\nid: {local}\ntitle: {spec['title']}\nstatus: approved\n"
    if spec.get("refines"):
        head += f"relations:\n  refines: [{', '.join(spec['refines'])}]\n"
    if spec.get("tests"):
        head += "tests:\n" + "".join(f"  - path: {path}\n    covers: [{', '.join(covers)}]\n    command: {command}\n"
                                     for path, covers, command in spec["tests"])
    lines = "".join(f"- [{local}:{label}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {text}。\n" for label, text in spec.get("statements", []))
    body = f"# {local} {spec['title']}\n\n"
    if kind_of(local) == "requirement":
        body += f"## Intent\n\n{spec['title']}の規範を定める。\n\n## Acceptance Criteria\n\n{lines}\n## Verification\n\nそれぞれのtestで確認する。\n"
    elif lines:
        body += f"## Context\n\n{spec['title']}を定める。\n\n## Constraints\n\n{lines}"
    else:
        body += f"## Context\n\n{spec['title']}を定める。\n"
    return head + "---\n\n" + body, body


def argv_template(workspace, name, total):
    return ["/bin/sh", SEQ_PATH, f"{workspace}::{name}", str(total), "{tests}"]


def command_block(workspace, names, total):
    lines = "verify:\n  commands:\n"
    for name in names:
        argv = ", ".join(f'"{part}"' for part in argv_template(workspace, name, total))
        lines += f"    {name}:\n      argv: [{argv}]\n      cwd: .\n"
    return lines


def reviewed_inputs(identifier):
    case = CASES[identifier]
    root, total = case["root"], total_of(identifier)
    documents, commands, _ = case["shape"]()
    files = {}
    members = [(member, workspace_path(root, member)) for member in case["members"]]
    for workspace in [root, *case["members"]]:
        base = "" if workspace == root else workspace_path(root, workspace) + "/"
        config = (multi_reference.root_config(members, root) if workspace == root else multi_reference.plain_config(workspace))
        if workspace in commands:
            config += command_block(workspace, commands[workspace], total)
            files[f"{base}{SEQ_PATH}"] = SEQ_SCRIPT
        files[f"{base}.spec/bitz.yaml"] = config
    for (workspace, local), spec in documents.items():
        base = "" if workspace == root else workspace_path(root, workspace) + "/"
        files[f"{base}.spec/{KIND_DIRECTORY[kind_of(local)]}/{local}.md"] = render(local, spec)[0]
        for path, _, _ in spec.get("tests", []):
            files[f"{base}{path}"] = TEST_BYTES.decode()
    return {name: text.encode() for name, text in files.items()}


def reviewed_manifest(identifier):
    return {
        "fixtureId": identifier, "description": CASES[identifier]["description"],
        # `verify`はテスト割当てを所有するワークスペースの設定がインデックスで未追跡だと起動を遮断するため、入力をコミットする。
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": [*CASES[identifier]["argv"], "--format", "json"], "env": {}},
        "expect": {"status": "passed", "exitCode": 0, "stdout": "json", "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def reviewed_effects(state):
    return {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}


# --- ハッシュ値の参照計算A（リテラル） ---------------------------------------------------------------

def _material(identifier, workspace, local, spec):
    """文書1件のハッシュ値の材料。関係の参照先と`covers`は修飾IDにそろえ、辞書順に置く（正規化仕様 §3）。"""
    def qualified(value):
        return value if "::" in value else f"{workspace}::{value}"

    name = f"{workspace}::{local}"
    relations = {"refines": sorted(qualified(value) for value in spec["refines"])} if spec.get("refines") else {}
    statements = sorted((verify_fixtures.statement_material(f"{name}:{label}", text) for label, text in spec.get("statements", [])),
                        key=lambda item: item["id"])
    document = verify_fixtures.document_material(None, name, workspace, kind_of(local), spec["title"], render(local, spec)[1],
                                                 relations=relations, statements=statements)
    document["frontmatter"]["tests"] = sorted(
        ({"path": path, "covers": sorted(qualified(value) for value in covers), "command": command} for path, covers, command in spec.get("tests", [])),
        key=lambda item: (item["path"], item["covers"]))
    return document


def reviewed_digest_input(identifier, target):
    """検証対象`target`の、目的`verify`のハッシュ値の材料。"""
    case = CASES[identifier]
    root = case["root"]
    documents, _, closure = case["shape"]()
    total = total_of(identifier)
    # 閉包の文書。リテラルで書き、監査が参照計算Bの閉包と照合する。
    included = {(workspace, local): spec for (workspace, local), spec in documents.items() if f"{workspace}::{local}" in closure[target]}
    reached = sorted({workspace for workspace, _ in included})
    request = target.partition("::")[0]
    workspaces = [request, *sorted(set(reached) - {request})]
    material = [_material(identifier, workspace, local, spec) for (workspace, local), spec in included.items()]
    used = {workspace: sorted({command for (owner, _), spec in included.items() if owner == workspace for _, _, command in spec.get("tests", [])})
            for workspace in reached}
    edges = sorted((f"{workspace}::{local}", "refines", reference) for (workspace, local), spec in included.items()
                   for reference in spec.get("refines", []) if reference.partition("::")[0] != workspace)
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": "verify", "requestWorkspaceId": request, "roots": [target],
        "workspaces": [{"id": workspace, "path": workspace_path(root, workspace)} for workspace in workspaces],
        "documents": sorted(material, key=lambda item: item["id"]),
        "crossWorkspaceEdges": [{"relation": relation, "source": source, "target": reference} for source, relation, reference in edges],
        "settings": {
            "workspaces": [{"id": workspace, "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"} for workspace in reached],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": workspace, "timeoutSeconds": 300} for workspace in reached if used[workspace]],
            "commands": [{"workspaceId": workspace, "name": name, "argv": argv_template(workspace, name, total), "cwd": "."}
                         for workspace in reached for name in used[workspace]],
        },
    }


def expected_digest(identifier, target):
    return multi_reference.digest(multi_reference.canonical_bytes(reviewed_digest_input(identifier, target)))


# --- レビュー済みの期待結果 ---------------------------------------------------------------

def command_entry(identifier, binding):
    workspace, name = binding.split("::")
    tests, covers = EXPECTED[identifier][1][binding]
    number = literal_order(identifier).index(binding) + 1
    return {
        "bindingId": binding, "workspaceId": workspace, "name": name, "status": "passed", "termination": "exit", "cwd": ".",
        "argv": [*argv_template(workspace, name, total_of(identifier))[:-1], *tests], "tests": list(tests), "covers": list(covers),
        "exitCode": 0, "timeoutSeconds": 300, "stdoutExcerpt": f"{binding} {number}\n", "stderrExcerpt": "",
        "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}


def target_entry(identifier, target):
    statements, refs = expected_targets(identifier)[target]
    return {"target": target, "status": "passed", "contextDigest": expected_digest(identifier, target),
            "statements": list(statements), "bindingRefs": list(refs), "diagnostics": []}


def reviewed_result(identifier):
    case = CASES[identifier]
    revision = {"commit": COMMIT, "dirty": False}
    bindings = literal_order(identifier)
    if not is_all(identifier):
        workspace = case["target"].partition("::")[0]
        return {"schemaVersion": "1.0", "operation": "verify", "status": "passed", "scope": "selected",
                "workspace": {"id": workspace, "path": workspace_path(case["root"], workspace)},
                "targetResults": [target_entry(identifier, case["target"])], "revision": revision,
                "commands": [command_entry(identifier, binding) for binding in bindings], "durationMs": 0, "diagnostics": []}
    entries = []
    for workspace in workspace_ids(identifier):
        targets = sorted(target for target in expected_targets(identifier) if target.partition("::")[0] == workspace)
        entries.append({
            "id": workspace, "path": workspace_path(case["root"], workspace), "status": "passed",
            "targetResults": [target_entry(identifier, target) for target in targets],
            "commands": [command_entry(identifier, binding) for binding in bindings if binding.partition("::")[0] == workspace],
            "durationMs": 0, "diagnostics": []})
    return {"schemaVersion": "1.0", "operation": "verify", "scope": "all-workspaces", "status": "passed",
            "multiWorkspace": {"id": case["root"], "path": "."}, "workspaces": entries, "revision": revision,
            "durationMs": 0, "diagnostics": []}


# --- 参照計算（準備手順の後の入力から導く） -----------------------------------------------------

def reference_targets(documents, selected=None):
    """検証対象（`selected`が`None`なら、各ワークスペースの引数なしの`verify`が検証するすべての文書。`verify` §2）。"""
    return sorted(documents) if selected is None else [selected]


def reference_plan(documents, targets):
    """検証対象ごとの規範文とテスト割当てを導く（関係・トレースモデル §6.4、`verify` §3・§4）。

    対象規範文は、起点の文書が所有する規範文と具体化文書の規範文。テスト割当ては、閉包の文書のテスト対応のうち、対象規範文を`covers`するもの
    （規範文のない文書は、自身の文書単位のテスト対応）を、`(所有ワークスペース, コマンド名)`ごとにまとめる。全`MUST`にテスト対応があることを要求する。
    戻り値は(検証対象→(規範文, テスト割当て), テスト割当て→(テストのパス, `covers`))。
    """
    per_target, bindings = {}, {}
    for root in targets:
        ordered, edges, _ = order.reference_order(documents, root, "interpret")
        wanted = sorted(set(order.reference_targets(documents, ordered, edges, root)))
        covered, chosen = set(), set()
        for name in ordered:
            document = documents[name]
            workspace = document["workspaceId"]
            for entry in document["frontmatter"].get("tests", []):
                covers = {multi_crosscheck.qualify(workspace, text) for text in entry["covers"]}
                if wanted:
                    if not covers & set(wanted):
                        continue
                elif name != root:
                    continue
                key = (workspace, entry.get("command") or document["frontmatter"].get("verify"))
                chosen.add(key)
                covered |= covers & set(wanted)
                slot = bindings.setdefault(key, {"tests": set(), "covers": set()})
                slot["tests"].add(entry["path"])
                slot["covers"] |= covers & set(wanted)
        if covered != set(wanted):
            raise ValueError("対象のすべての`MUST`にテスト対応がある必要があります")
        per_target[root] = (wanted, sorted(f"{workspace}::{command}" for workspace, command in chosen))
    return per_target, {f"{workspace}::{command}": (sorted(slot["tests"]), sorted(slot["covers"]))
                        for (workspace, command), slot in bindings.items()}


def declaration_order(documents, key):
    """テスト割当て`key`（`<ワークスペース>::<コマンド名>`）の`tests`と`covers`を、宣言の順（重複は最初の位置）で返す。`covers`は修飾IDにする。"""
    tests, covers = [], []
    for name in sorted(documents):
        document = documents[name]
        workspace = document["workspaceId"]
        for entry in document["frontmatter"].get("tests", []):
            if f"{workspace}::{entry.get('command') or document['frontmatter'].get('verify')}" != key:
                continue
            tests += [entry["path"]] if entry["path"] not in tests else []
            covers += [item for item in (multi_crosscheck.qualify(workspace, text) for text in entry["covers"]) if item not in covers]
    return tests, covers


def reference_order(root_id, bindings):
    """実行の順: ワークスペースの処理順（ルートを先頭、その後をワークスペースIDの辞書順）、コマンド名の辞書順（`verify` §4の6.・§10）。"""
    def key(binding):
        workspace, name = binding.split("::")
        return (0 if workspace == root_id else 1, workspace, name)

    return sorted(bindings, key=key)


def check_conditions(identifier, repository, manifest, result):
    """原因の構成と期待結果を、散文ではなく準備手順の後の入力から確かめる。"""
    case = CASES[identifier]
    single, root_id, workspaces, documents = alias.load_tree(repository)
    if single or root_id != case["root"] or sorted(workspaces) != sorted(workspace_ids(identifier)):
        raise ValueError("ワークスペースの構成が入力と異なります")
    declared = [member for member, _ in multi_crosscheck.catalog(repository)[1]]
    if declared != case["members"]:
        raise ValueError("カタログのメンバーの宣言の順がレビュー済みの入力と異なります")
    targets = reference_targets(documents, case["target"])
    per_target, bindings = reference_plan(documents, targets)
    derived = reference_order(root_id, bindings)
    if derived != literal_order(identifier):
        raise ValueError("期待する実行の順が入力からの参照計算と異なります")
    # この入力が欠陥を検出できる（修正前の並びと異なる）か、対照として同じである。
    plain = sorted(bindings, key=lambda binding: tuple(binding.split("::")))
    if (plain != derived) != case["defect"] or plain != defective_order(identifier):
        raise ValueError("修正前の並びとの関係がfixtureの名乗る種類と異なります")
    # 辞書順の対照は、宣言の順が辞書順でない`tests`と`covers`を持つ（宣言の順に出力する実装を区別できる）。
    if case.get("unsorted"):
        tests, covers = declaration_order(documents, "zeta::a")
        if tests == sorted(tests) or covers == sorted(covers):
            raise ValueError("`tests`と`covers`の宣言の順が辞書順です（宣言の順に出力する実装を区別できません）")
    if len(workspaces) < 3 and not case.get("unsorted"):
        raise ValueError("実行の順のfixtureは3つ以上のワークスペースを持つ必要があります")
    if {target: (statements, refs) for target, (statements, refs) in per_target.items()} != {
            target: (list(statements), list(refs)) for target, (statements, refs) in expected_targets(identifier).items()}:
        raise ValueError("検証対象の規範文またはbindingRefsが入力からの参照計算と異なります")
    if bindings != {binding: (list(tests), list(covers)) for binding, (tests, covers) in EXPECTED[identifier][1].items()}:
        raise ValueError("テストのパスまたはcoversが入力からの参照計算と異なります")
    if result["status"] != "passed" or (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != ("passed", 0):
        raise ValueError("この入力は診断を持たない通過の結果になります")
    # 結果: `commands[]`の並び、連番（実行の順の観測）、diagnostics。
    if "workspaces" in result:
        if [entry["id"] for entry in result["workspaces"]] != [root_id, *sorted(set(workspaces) - {root_id})]:
            raise ValueError("ワークスペースの結果の並びがルート先頭、ID辞書順ではありません")
        commands = [command for entry in result["workspaces"] for command in entry["commands"]]
        entries = [target for entry in result["workspaces"] for target in entry["targetResults"]]
        diagnostics = result["diagnostics"] + [item for entry in result["workspaces"] for item in entry["diagnostics"]]
    else:
        commands, entries, diagnostics = result["commands"], result["targetResults"], result["diagnostics"]
    if [command["bindingId"] for command in commands] != derived:
        raise ValueError("`commands[]`の並びが実行の順と異なります")
    if [command["stdoutExcerpt"] for command in commands] != [f"{binding} {index}\n" for index, binding in enumerate(derived, 1)]:
        raise ValueError("実行の順の観測（連番）が参照計算と異なります")
    for command in commands:
        tests, covers = bindings[command["bindingId"]]
        if command["tests"] != tests or command["covers"] != covers or command["tests"] != sorted(set(command["tests"])) \
                or command["covers"] != sorted(set(command["covers"])):
            raise ValueError("`tests`または`covers`が重複なし辞書順ではありません")
    if diagnostics or any(entry["diagnostics"] or entry["status"] != "passed" for entry in entries):
        raise ValueError("この入力は診断を持たない通過の結果になります")
    if sorted(entry["target"] for entry in entries) != sorted(targets):
        raise ValueError("検証対象が入力からの参照計算と異なります")
    if all(entry["bindingRefs"] != sorted(set(entry["bindingRefs"])) for entry in entries):
        raise ValueError("`bindingRefs`が重複なし辞書順ではありません")


def check_digests(identifier, repository, result):
    entries = [target for entry in result.get("workspaces", []) for target in entry["targetResults"]] + list(result.get("targetResults", []))
    loaded = multi_crosscheck.load_workspaces(repository)
    for entry in entries:
        selected, _ = multi_crosscheck.closure(loaded[2], entry["target"])
        if selected != CASES[identifier]["shape"]()[2][entry["target"]]:
            raise ValueError(f"{entry['target']}の閉包がレビュー済みの閉包と異なります")
        derived = multi_crosscheck.canonical_bytes(multi_crosscheck.build(repository, entry["target"], loaded=loaded))
        if multi_crosscheck.digest(derived) != entry["contextDigest"]:
            raise ValueError(f"{entry['target']}のハッシュ値が参照計算Bと一致しません")
        if multi_reference.canonical_bytes(reviewed_digest_input(identifier, entry["target"])) != derived:
            raise ValueError(f"{entry['target']}のハッシュ値の参照計算AとBが一致しません")
    return len(entries)


# --- 書き出しと監査 ---------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    for identifier in CASES:
        fixture = root / "multi" / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected/verify.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-binding-order-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(_dump(reviewed_effects(state)))


def actual_entries(fixture):
    files = {}
    for path in sorted((fixture / "repo").rglob("*")):
        relative = path.relative_to(fixture / "repo").as_posix()
        if path.is_symlink():
            raise ValueError(f"{relative}はシンボリックリンクであってはいけません")
        if path.is_file():
            if path.stat().st_mode & 0o111:
                raise ValueError(f"{relative}は実行ビットを持ってはいけません")
            files[relative] = path.read_bytes()
    return files


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
            result = json.loads((fixture / "expected/verify.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            if effects != reviewed_effects(effects["before"]):
                raise ValueError("副作用の期待値がレビュー済みのポリシーと異なります")
            if actual_entries(fixture) != reviewed_inputs(identifier):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if {path.relative_to(fixture).as_posix() for path in (fixture / "expected").glob("*")} != {"expected/verify.json"}:
                raise ValueError("期待値のファイルがレビュー済みの集合と異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("既に存在したパスはすべて不変である必要があります")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-binding-order-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {key: sandbox / key for key in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
                    check_conditions(identifier, repository, manifest, result)
                    check_digests(identifier, repository, result)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
