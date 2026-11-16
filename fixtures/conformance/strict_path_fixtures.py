"""パスを字句で厳密に比べ、シンボリックリンクを辿らないことの追加の適合fixture（Coreの公開操作は実行しない）。

ADR-071 Decision 1（シンボリックリンクを辿らない、パスをNFCで厳密に比べる、字句のパスで所有を判定する）の規範
（[安全な入出力・互換性 §6](../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md#6-正規パス)）を固定する、ADR-051の追加である。
群は、`SINGLE-179-01`〜`24`（単一ワークスペース）と`MULTI-067-01`〜`09`（複合ワークスペース）。既存のfixtureの期待値の訂正は、
`real_path_ownership_fixtures`（`SINGLE-174`、`MULTI-061`）、`command_cwd_fixtures`・`multi_command_cwd_fixtures`（`167`、`051`）、`verify_test_check_fixtures`（`MULTI-062-01`）、
`multi_ownership_fixtures`（`MULTI-008`、`MULTI-010`）が持つ。`SINGLE-167-10`と`MULTI-051-07`（途中のセグメントがシンボリックリンクの`cwd`）は`command_cwd_fixtures`・`multi_command_cwd_fixtures`に置く。

NFCとNFDの名前、NFCで同じ名前になる2つの兄弟の項目は、`repo/`へ直接置かない（macOSのファイルシステムとGitの既定の設定で名前が正規化または衝突するため）。
`repo/`にはASCIIの名前の入力を置き、マニフェストの`setup.materialize`（適合fixture仕様 §3.1の1.5）で、`git init`の前に付け替える。付け替えの後の名前が基準版のコミットに入る。
付け替えの先は、マニフェストへJSONの`\\u`エスケープで書く（`\\u00e9`は`é`のNFC、`e\\u0301`はNFD）。この付け替えは、Linux（NFCとNFDの名前が共存できる）で行う。

入力は、期待値と別に、準備手順の後の作業ツリーから字句の規則だけで導く参照計算（`lexical_path_reference`、このモジュールの`sandbox_*`）と一致することを確かめる。
`realpath`・`resolve`・`samestat`は使わない。Coreの出力は根拠にしない。修正前のCore（`968bc84`）が失敗するものを「欠陥」、通るものを「対照」とする（`defective`）。

各fixtureの入力と期待は、適合fixture仕様 §6.22・§7（`SINGLE-179`、`MULTI-067`）に表で書く。
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unicodedata

from jsonschema import Draft202012Validator, ValidationError

from . import digest_crosscheck, digest_reference, multi_reference
from . import lexical_path_reference as lexical
from . import real_path_ownership_fixtures as real_path
from .harness import git, setup
from .initial_fixtures import CONFIGS, compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
NFC_NAME = "café"
NFD_NAME = "café"
assert unicodedata.normalize("NFC", NFD_NAME) == NFC_NAME != NFD_NAME
CODE = b"# implementation\n"
TEST = b'raise RuntimeError("check must not run test code")\n'
VERIFY_BLOCK = 'verify:\n  commands:\n    default:\n      argv: ["/bin/true"]\n      cwd: .\n'
PATH_SUMMARIES = {"implements": "実装パスが存在しません", "tests": "テストのパスが存在しません"}
# 承認済みの新しい文言（ADR-062。ユーザー承認済み。安全な入出力・互換性 §6.2）。
COLLISION_SUMMARIES = {
    "implements": "NFCで同じ名前になる項目が複数あり、実装パスが一つに決まりません",
    "tests": "NFCで同じ名前になる項目が複数あり、テストのパスが一つに決まりません",
    "member": "NFCで同じ名前になる項目が複数あり、メンバーのパスが一つに決まりません",
}
DRAFT_SUMMARIES = {"implements": "状態draftの実装パスは未作成です", "tests": "状態draftのテストのパスは未作成です"}
OWNERSHIP_SUMMARY = "パス{path}がワークスペース{workspace}の所有領域の外です"
CWD_SUMMARY = "コマンドの作業ディレクトリが利用できません"
# `{tests}`の展開の試験（実在の綴りの引数）のコマンド。引数のファイルがすべて通常のファイルとして開けるときだけ終了コード0で終わる。
ARGV_SCRIPT = "for f; do [ -f $f ] || exit 1; done"
ARGV_YAML = "[\"/bin/sh\", \"-c\", \"" + ARGV_SCRIPT + "\", \"sh\", \"{tests}\"]"
ARGV_TEMPLATE = ["/bin/sh", "-c", ARGV_SCRIPT, "sh", "{tests}"]
OUTSIDE_SUMMARY = "テストのパスが実効の作業ディレクトリの配下にありません"
MEMBER_SUMMARIES = {"collision": COLLISION_SUMMARIES["member"], "duplicate": "メンバーのパスが重複しています",
                    "nested": "メンバーのパスが別のメンバーの配下にあります", "link": "メンバーのパスの経路にシンボリックリンクが含まれています"}
EXIT = {"passed": 0, "passed_with_warnings": 0, "failed": 1, "blocked": 2, "error": 3}
STATEMENTS = ["REQ-001:AC-01", "REQ-001:AC-02"]
TASK_TEXT = ("---\nid: TASK-001\ntitle: 変更境界の検査\nstatus: open\nchanges: [{changes}]\n---\n\n"
             "# TASK-001 変更境界の検査\n\n## Objective\n\n変更境界を確認する。\n")
WEB_TASK_TEXT = ("---\nid: TASK-010\ntitle: 変更境界の検査\nstatus: open\nchanges: [{changes}]\n---\n\n"
                 "# TASK-010 変更境界の検査\n\n## Objective\n\nwebの変更境界を確認する。\n")
MEMBERS = (("web", "apps/web"), ("api", "services/api"))


def yq(text):
    """YAMLの二重引用符の文字列。ASCII以外は`\\uXXXX`で書く（正規化形を変えない）。"""
    escaped = "".join(char if char.isascii() and char not in '"\\' else ("\\" + char if char in '"\\' else f"\\u{ord(char):04x}") for char in text)
    return f'"{escaped}"'


def child(base, name):
    return f"{base}/{name}" if base else name


# --- ケース -------------------------------------------------------------------------------
# kind: path〈`check --full`の`implements`・`tests`の存在〉, verify〈単一の`verify`〉, task〈TASKの`changes`〉, changed〈引数なしの`check`の逆索引〉,
#       explicit〈明示した仕様文書のパス〉, mmembers〈メンバーのパス〉, mimpl〈メンバーの`implements`〉, mtask〈メンバーのTASKの`changes`〉
# 共通: files〈`repo/`の通常のファイル（パス→バイト列）。ASCIIの名前〉, links〈`repo/`のシンボリックリンク〉, materialize〈付け替え(from, to)〉,
#       defective〈修正前のCore（`968bc84`）が違う結果を返すか。陰性対照で確かめた事実〉, step, description
def path_case(field, declared, files, outcome, materialize=(), links=None, status="approved", **extra):
    return dict(kind="path", field=field, declared=declared, files={name: (TEST if field == "tests" else CODE) for name in files},
                outcome=outcome, materialize=list(materialize), links=links or {}, status=status, step=2, **extra)


def verify_case(cwd, tests, files, outcome, materialize=(), links=None, invalid=(), source=None, cwd_yaml=None, argv=False, spelling=False, **extra):
    """`argv`が真なら、コマンドを`ARGV_TEMPLATE`にし、結果へコマンドの実行結果（`commands[]`）を持たせる（outcomeは`passed`）。
    `spelling`は、プロセスへ渡す引数（実在の綴り）が公開結果の引数（宣言の綴り）と異なるか。"""
    if argv:
        extra.update(argvYaml=ARGV_YAML, argv=list(ARGV_TEMPLATE), spelling=spelling)
    return dict(kind="verify", cwd=cwd, cwdYaml=cwd_yaml or cwd, tests=tests, files={name: TEST for name in files}, outcome=outcome,
                materialize=list(materialize), links=links or {}, invalid=list(invalid), source=source, step=4, **extra)


CASES = {
    "SINGLE-179-01": path_case("implements", f"src/{NFC_NAME}.py", ["src/nfc.py", "src/nfd.py"], "collision",
                               materialize=[("src/nfc.py", f"src/{NFC_NAME}.py"), ("src/nfd.py", f"src/{NFD_NAME}.py")], defective=True,
                               description="implementsの末端の項目がNFCで同じ名前になる2つの兄弟を持つとき、存在しない扱いにせず、専用の文言で拒否する（状態approved）"),
    "SINGLE-179-02": path_case("tests", f"tests/{NFC_NAME}.py", ["tests/nfc.py", "tests/nfd.py"], "collision",
                               materialize=[("tests/nfc.py", f"tests/{NFC_NAME}.py"), ("tests/nfd.py", f"tests/{NFD_NAME}.py")], defective=True,
                               description="tests[].pathの末端の項目がNFCで同じ名前になる2つの兄弟を持つとき、存在しない扱いにせず、専用の文言で拒否する（状態approved）"),
    "SINGLE-179-03": path_case("implements", f"lib/{NFC_NAME}/a.py", ["lib/dnfc/a.py", "lib/dnfd/a.py"], "collision",
                               materialize=[("lib/dnfc", f"lib/{NFC_NAME}"), ("lib/dnfd", f"lib/{NFD_NAME}")], defective=True,
                               description="implementsの途中のディレクトリがNFCで同じ名前になる2つの兄弟を持つとき、末端まで辿らず、専用の文言で拒否する"),
    "SINGLE-179-04": path_case("implements", f"src/{NFC_NAME}.py", ["src/nfc.py", "src/nfd.py"], "collision", status="draft",
                               materialize=[("src/nfc.py", f"src/{NFC_NAME}.py"), ("src/nfd.py", f"src/{NFD_NAME}.py")], defective=True,
                               description="NFCの衝突の重大度は不在と同じく状態で分け、状態draftはwarningにし、専用の文言（未作成の文言ではない）を使う"),
    "SINGLE-179-05": path_case("implements", f"src/{NFC_NAME}.py", ["src/n.py"], "ok", materialize=[("src/n.py", f"src/{NFD_NAME}.py")], defective=True,
                               description="NFDの名前のファイルを、NFCで書いたimplementsで宣言したとき、NFCへ正規化して比べ、存在するパスとして受け付ける"),
    "SINGLE-179-06": path_case("tests", f"tests/{NFC_NAME}.py", ["tests/n.py"], "ok", materialize=[("tests/n.py", f"tests/{NFD_NAME}.py")], defective=True,
                               description="NFDの名前のファイルを、NFCで書いたtests[].pathで宣言したとき、存在するパスとして受け付ける"),
    "SINGLE-179-07": path_case("implements", f"src/{NFD_NAME}.py", ["src/n.py"], "ok", materialize=[("src/n.py", f"src/{NFC_NAME}.py")], defective=True,
                               description="NFCの名前のファイルを、NFDで書いたimplementsで宣言したとき、宣言のパスもNFCへ正規化して比べ、存在するパスとして受け付ける"),
    "SINGLE-179-08": path_case("implements", "src/auth.py", ["src/Auth.py"], "missing", defective=False,
                               description="対照: 大文字と小文字だけが違う綴りのパスは、大文字と小文字を区別するファイルシステムでも区別せずに開けるファイルシステムでも、存在しないパスとして扱う"),
    "SINGLE-179-09": path_case("implements", "src/link.py", ["src/real.py"], "missing", links={"src/link.py": "real.py"}, defective=False,
                               description="対照: 末端がシンボリックリンクのimplementsは、リンク先が同じ領域の通常のファイルでも、通常のファイルとして扱わず存在しないパスにする"),
    "SINGLE-179-10": path_case("tests", f"lib/{NFC_NAME}/t.py", ["lib/d/t.py"], "ok", materialize=[("lib/d", f"lib/{NFD_NAME}")], defective=True,
                               description="NFDの名前のディレクトリを経由するパスを、NFCで書いたtests[].pathで宣言したとき、途中のセグメントもNFCで比べ、存在するパスとして受け付ける"),
    "SINGLE-179-11": verify_case(NFC_NAME, [["tests/test_auth.py", "tests/test_session.py"]],
                                 ["tests/test_auth.py", "tests/test_session.py", "dnfc/keep.txt", "dnfd/keep.txt"], "cwd",
                                 materialize=[("dnfc", NFC_NAME), ("dnfd", NFD_NAME)], defective=True,
                                 description="cwdの項目がNFCで同じ名前になる2つの兄弟を持つとき、cwdが利用できないものとして起動前に遮断する（テストのcwdの配下の判定には進まない）"),
    "SINGLE-179-12": verify_case(".", [[f"tests/{NFC_NAME}.py", "tests/test_session.py"]],
                                 ["tests/nfc.py", "tests/nfd.py", "tests/test_session.py"], "failed",
                                 materialize=[("tests/nfc.py", f"tests/{NFC_NAME}.py"), ("tests/nfd.py", f"tests/{NFD_NAME}.py")],
                                 invalid=[("TECH-001", 0, "collision")], defective=True,
                                 description="verifyが使うテストのパスがNFCで同じ名前になる2つの兄弟を持つとき、checkと同じ専用の文言で検証対象をfailedにする"),
    "SINGLE-179-13": verify_case("tests", [["other/test_auth.py", "other/test_session.py"]], ["other/test_auth.py", "other/test_session.py", "tests/keep.txt"], "outside",
                                 source=("TECH-001", 0), defective=False,
                                 description="対照: テストのパスが字句でcwdの配下にないときは、宣言した仕様文書とtests[i].pathを発生元にして起動前に遮断する"),
    "SINGLE-179-14": verify_case("tests", [["tests/test_ok.py", "other/test_auth.py"], ["other/test_auth.py"]], ["tests/test_ok.py", "other/test_auth.py"],
                                 "outside", source=("TECH-001", 1), defective=False,
                                 description="対照: 配下にないテストを複数の文書が宣言するとき、パスの辞書順で最初の文書と、その文書の最小の添字を発生元にして1件で遮断する"),
}


def task_case(changes, files, outcome, links=None, changes_files=None, change_links=None, operations=(), violations=(), **extra):
    return dict(kind="task", changes=changes, files={name: CODE for name in files}, links=links or {}, outcome=outcome,
                changeFiles={name: CODE + b"# changed\n" for name in (changes_files or [])}, changeLinks=change_links or {}, operations=list(operations),
                violations=list(violations), materialize=[], step=3, **extra)


CASES.update({
    "SINGLE-179-15": task_case(["src/"], ["src/a.py"], "ok", links={"src/link": "../../outside"}, change_links={"link": "a.py"},
                               operations=[("update", "src/link", "changes/link")], defective=False,
                               description="TASKの差分のシンボリックリンクのエントリは、エントリ自身の字句のパスだけで許可を判定し、基準版のリンク先（ワークスペースの外）を使わない"),
    "SINGLE-179-16": task_case(["src/"], ["src/a.py", "src/b.py"], "violation", links={"lib/link": "../src/a.py"}, change_links={"link": "../src/b.py"},
                               operations=[("update", "lib/link", "changes/link")], violations=["lib/link"], defective=False,
                               description="TASKの差分のシンボリックリンクのエントリが許可の外の字句のパスなら、リンク先が許可の範囲の中でも、許可を広げずにTASK境界の外とする"),
    "SINGLE-179-17": task_case(["ext/a.py"], ["real/a.py"], "ok", links={"ext": "real"}, defective=False,
                               description="対照: changesに書いたパスの途中のセグメントがシンボリックリンクでも、changesは字句の許可なので拒否しない"),
    "SINGLE-179-18": task_case(["ext/a.py"], ["real/a.py"], "violation", links={"ext": "real"}, changes_files=["a.py"],
                               operations=[("update", "real/a.py", "changes/a.py")], violations=["real/a.py"], defective=False,
                               description="changesの途中のリンクのパスは、シンボリックリンクの先の差分のパスを許可しない（許可は字句のパスの一致だけ）"),
})


def changed_case(field, declared, changed, materialize, **extra):
    return dict(kind="changed", field=field, declared=declared, changed=changed, files={"src/n.py" if field == "implements" else "tests/n.py": (
        CODE if field == "implements" else TEST)}, links={}, materialize=list(materialize), outcome="matched", changeFiles={"c.py": CODE + b"# changed\n"},
                changeLinks={}, step=3, **extra)


CASES.update({
    "SINGLE-179-19": changed_case("implements", f"src/{NFC_NAME}.py", f"src/{NFD_NAME}.py", [("src/n.py", f"src/{NFD_NAME}.py")], defective=True,
                                  description="引数なしのcheckで、Gitが返す変更のパス（NFD）と、NFCで書いたimplementsを、NFCで照合して逆索引でREQを対象にする"),
    "SINGLE-179-20": changed_case("tests", f"tests/{NFC_NAME}.py", f"tests/{NFD_NAME}.py", [("tests/n.py", f"tests/{NFD_NAME}.py")], defective=True,
                                  description="引数なしのcheckで、Gitが返す変更のパス（NFD）と、NFCで書いたtests[].pathを、NFCで照合して逆索引でREQを対象にする"),
    "SINGLE-179-21": changed_case("implements", f"src/{NFD_NAME}.py", f"src/{NFC_NAME}.py", [("src/n.py", f"src/{NFC_NAME}.py")], defective=True,
                                  description="引数なしのcheckで、Gitが返す変更のパス（NFC）と、NFDで書いたimplementsを、NFCで照合して逆索引でREQを対象にする"),
})


def explicit_case(argument, names, outcome, **extra):
    """names: 配置する仕様文書（付け替え前のASCIIの名前, 付け替え後の名前, 文書ID）。"""
    return dict(kind="explicit", argument=argument, names=names, outcome=outcome, files={}, links={}, materialize=[(f".spec/requirements/{a}.md", f".spec/requirements/{b}.md")
                                                                                                           for a, b, _ in names], step=3, **extra)


CASES.update({
    "SINGLE-179-22": explicit_case(f".spec/requirements/REQ-001-{NFC_NAME}.md", [("r1", f"REQ-001-{NFD_NAME}", "REQ-001")], "ok", defective=True,
                                   description="CLIで明示した仕様文書のパス（NFC）を、NFDの名前の仕様文書とNFCで照合し、1件に一致すれば受け付ける"),
    "SINGLE-179-23": explicit_case(f".spec/requirements/REQ-001-{NFD_NAME}.md", [("r1", f"REQ-001-{NFC_NAME}", "REQ-001")], "ok", defective=True,
                                   description="CLIで明示した仕様文書のパス（NFD）を、NFCの名前の仕様文書とNFCで照合し、1件に一致すれば受け付ける"),
    "SINGLE-179-24": explicit_case(f".spec/requirements/REQ-001-{NFC_NAME}.md", [("r1", f"REQ-001-{NFC_NAME}", "REQ-001"), ("r2", f"REQ-001-{NFD_NAME}", "REQ-002")],
                                   "missing", defective=True,
                                   description="CLIで明示した仕様文書のパスがNFCで2つの仕様文書に一致するとき、一致しない場合と同じCTX-ROOT-MISSING-001にし、新しい診断を作らない"),
})

CASES.update({
    "SINGLE-179-25": verify_case(".", [[f"tests/{NFC_NAME}.py", "tests/test_session.py"]], ["tests/n.py", "tests/test_session.py"], "passed",
                                 materialize=[("tests/n.py", f"tests/{NFD_NAME}.py")], argv=True, spelling=True, defective=True,
                                 description="NFDの名前のテストファイルを、NFCで宣言したとき、起動するコマンドの引数は、存在の検査で一致した実在の綴り（NFD）で組み立てる（公開結果の引数は宣言の綴り）"),
    "SINGLE-179-26": verify_case("tests", [[f"tests/{NFC_NAME}/a.py", "tests/test_session.py"]], ["tests/d/a.py", "tests/test_session.py"], "passed",
                                 materialize=[("tests/d", f"tests/{NFD_NAME}")], argv=True, spelling=True, defective=True,
                                 description="NFDの名前のディレクトリを経由するテストを、NFCで宣言したとき、cwd相対の引数も、途中のセグメントを実在の綴り（NFD）で組み立てる"),
    "SINGLE-179-27": verify_case(NFC_NAME, [[f"{NFC_NAME}/test_auth.py", f"{NFC_NAME}/test_session.py"]], ["d/test_auth.py", "d/test_session.py"], "passed",
                                 materialize=[("d", NFD_NAME)], argv=True, defective=True,
                                 description="cwdがNFDの名前のディレクトリで、NFCで宣言したとき、NFCで一致するcwdを実在の綴りで起動し、cwd相対の引数は同じ綴りになるので通る（引数の綴りは変わらない）"),
})


def multi_members_case(members, configs, outcome, materialize=(), links=None, **extra):
    """members: カタログの(ID, 宣言したパス)の列。configs: 付け替え前のASCIIの名前のメンバーの設定のパス→そのワークスペースのID。"""
    return dict(kind="mmembers", members=members, configs=configs, files={}, outcome=outcome, materialize=list(materialize), links=links or {}, step=5, **extra)


API_CONFIG = {"services/api/.spec/bitz.yaml": "api"}
CASES.update({
    "MULTI-067-01": multi_members_case([("web", f"apps/{NFC_NAME}"), ("api", "services/api")],
                                       {"apps/mnfc/.spec/bitz.yaml": "web", "apps/mnfd/.spec/bitz.yaml": "web", **API_CONFIG}, "collision",
                                       materialize=[("apps/mnfc", f"apps/{NFC_NAME}"), ("apps/mnfd", f"apps/{NFD_NAME}")], defective=True,
                                       description="メンバーのパスの項目がNFCで同じ名前になる2つの兄弟を持つとき、存在しない扱いにせず、専用の文言のSPEC-MULTI-PATH-001で全体事前検査を止める"),
    "MULTI-067-02": multi_members_case([("web", f"apps/{NFC_NAME}"), ("api", "services/api")], {"apps/m/.spec/bitz.yaml": "web", **API_CONFIG}, "ok",
                                       materialize=[("apps/m", f"apps/{NFD_NAME}")], defective=True,
                                       description="NFDの名前のディレクトリを、NFCで書いたメンバーのパスで宣言したとき、NFCで比べ、存在するメンバーとして受け付ける"),
    "MULTI-067-03": multi_members_case([("web", f"apps/{NFC_NAME}"), ("dup", f"apps/{NFD_NAME}")], {"apps/m/.spec/bitz.yaml": "web"}, "duplicate",
                                       materialize=[("apps/m", f"apps/{NFC_NAME}")], defective=True,
                                       description="メンバーのパスの同一を、NFCにしたセグメントで判定し、NFCとNFDで書き分けた同じパスを重複として全体事前検査を止める"),
    "MULTI-067-04": multi_members_case([("web", f"apps/{NFC_NAME}"), ("inner", f"apps/{NFD_NAME}/inner")],
                                       {"apps/m/.spec/bitz.yaml": "web", "apps/m/inner/.spec/bitz.yaml": "inner"}, "nested",
                                       materialize=[("apps/m", f"apps/{NFC_NAME}")], defective=True,
                                       description="メンバーのパスの入れ子を、NFCにしたセグメントで判定し、NFCとNFDで書き分けた親子のパスを入れ子として全体事前検査を止める"),
    "MULTI-067-05": multi_members_case([("web", "apps/web"), ("api", "services/api")], {"apps/real/.spec/bitz.yaml": "web", **API_CONFIG}, "link",
                                       links={"apps/web": "real"}, defective=False,
                                       description="対照: メンバーのパスの末端がシンボリックリンクなら、リンク先が実在する別のディレクトリでも全体事前検査を止める"),
    "MULTI-067-06": multi_members_case([("web", "apps/lnk/web"), ("api", "services/api")], {"apps/real/web/.spec/bitz.yaml": "web", **API_CONFIG}, "link",
                                       links={"apps/lnk": "real"}, defective=False,
                                       description="対照: メンバーのパスの途中のセグメントがシンボリックリンクなら、リンク先が実在するメンバーでも全体事前検査を止める"),
})


def multi_impl_case(outcome, field, declared, files, materialize=(), links=None, owner="web", status="approved", **extra):
    """owner: 宣言する文書を所有するワークスペース（`web`はメンバー、`platform`はルート）。outcome: `ok`・`missing`・`collision`・`ownership`（別のワークスペースの所有領域）。"""
    return dict(kind="mimpl", field=field, declared=declared, owner=owner, status=status, files={name: (TEST if field == "tests" else CODE) for name in files},
                outcome=outcome, materialize=list(materialize), links=links or {}, step=5, **extra)


CASES.update({
    "MULTI-067-07": multi_impl_case("missing", "implements", "lnk.py", ["apps/web/real.py"], links={"apps/web/lnk.py": "real.py"}, defective=True,
                                    description="複合ワークスペースでも、メンバーの末端がシンボリックリンクのimplementsは、リンク先が同じ所有領域の中でも通常のファイルとして扱わず、存在しないパスにする（C109）"),
    "MULTI-067-08": dict(kind="mtask", files={"apps/web/real/a.py": CODE, "services/api/src/a.py": CODE}, links={"apps/web/ext": "../../services/api/src"},
                         changes="ext/a.py", outcome="ok", materialize=[], step=5, defective=False,
                         description="メンバーのTASKのchangesに書いた途中のセグメントがシンボリックリンクのパスは、別のメンバーの領域を指していても拒否しない"),
    "MULTI-067-09": multi_impl_case("collision", "implements", f"src/{NFC_NAME}.py", ["apps/web/src/nfc.py", "apps/web/src/nfd.py"],
                                    materialize=[("apps/web/src/nfc.py", f"apps/web/src/{NFC_NAME}.py"), ("apps/web/src/nfd.py", f"apps/web/src/{NFD_NAME}.py")],
                                    defective=True,
                                    description="複合ワークスペースでも、メンバーのimplementsの項目がNFCで同じ名前になる2つの兄弟を持つとき、専用の文言で拒否する"),
    "MULTI-067-10": multi_impl_case("ownership", "implements", "apps/web/src/missing.py", [], owner="platform", defective=True,
                                    description="ルートワークスペースのimplementsが、存在しない別のメンバーの所有領域のパスを指すとき（状態approved）、存在の検査より先に所有を判定し、SPEC-MULTI-OWNERSHIP-001にする"),
    "MULTI-067-11": multi_impl_case("ownership", "implements", "apps/web/src/missing.py", [], owner="platform", status="draft", defective=True,
                                    description="同上で状態draft（未作成の予定）でも、別のワークスペースの所有領域を指す宣言は、SPEC-MULTI-OWNERSHIP-001（error）にし、draftのwarningにしない"),
    "MULTI-067-12": multi_impl_case("ownership", "tests", "services/api/tests/missing.py", [], owner="platform", defective=True,
                                    description="ルートワークスペースのtests[].pathが、存在しない別のメンバーの所有領域のパスを指すとき、implementsと同じく所有を先に判定してSPEC-MULTI-OWNERSHIP-001にする"),
    "MULTI-067-13": multi_impl_case("draft", "implements", "src/missing.py", [], owner="platform", status="draft", defective=False,
                                    description="対照: ルートワークスペースのimplementsが、存在しない自分の所有領域のパス（状態draft）を指すときは、未作成の予定のwarning（SPEC-PATH-INVALID-001）にする"),
})


# --- 入力 -------------------------------------------------------------------------------------

def requirement_text(identifier, status, field=None, declared=None):
    head = f"---\nid: {identifier}\ntitle: 厳密なパス\nstatus: {status}\n"
    if field == "implements":
        head += f"implements: [{yq(declared)}]\n"
    elif field == "tests":
        head += f"tests:\n  - path: {yq(declared)}\n    covers: [{identifier}:AC-01]\n    command: default\n"
    return (head + "---\n\n"
            f"# {identifier} 厳密なパス\n\n## Intent\n\nパスを字句で厳密に比べる。\n\n## Acceptance Criteria\n\n"
            f"- [{identifier}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
            "## Verification\n\nCore実装後に確認する。現時点では未証明。\n")


def multi_root(members):
    return multi_reference.root_config([(identifier, path if path.isascii() else yq(path)) for identifier, path in members])


def reviewed_inputs(identifier):
    """`repo/`の通常のファイル（パス→バイト列）、`repo/`のシンボリックリンク、`changes/`の通常のファイルとシンボリックリンク。名前はASCII（付け替え前）。"""
    case = CASES[identifier]
    kind = case["kind"]
    files, changes = dict(case.get("files", {})), dict(case.get("changeFiles", {}))
    if kind == "path":
        config = CONFIGS["SINGLE-001"] + (VERIFY_BLOCK if case["field"] == "tests" else "")
        files = {".spec/bitz.yaml": config.encode(), **files,
                 ".spec/requirements/REQ-001.md": requirement_text("REQ-001", case["status"], case["field"], case["declared"]).encode()}
    elif kind == "verify":
        files = real_path.verify_inputs(case)
    elif kind == "task":
        files = {".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode(), **files,
                 ".spec/tasks/TASK-001.md": TASK_TEXT.format(changes=", ".join(case["changes"])).encode()}
    elif kind == "changed":
        config = CONFIGS["SINGLE-001"] + (VERIFY_BLOCK if case["field"] == "tests" else "")
        files = {".spec/bitz.yaml": config.encode(), **files,
                 ".spec/requirements/REQ-001.md": requirement_text("REQ-001", "approved", case["field"], case["declared"]).encode()}
    elif kind == "explicit":
        files = {".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode()}
        for placeholder, _, document in case["names"]:
            files[f".spec/requirements/{placeholder}.md"] = requirement_text(document, "approved").encode()
    elif kind == "mmembers":
        files = {".spec/bitz.yaml": multi_root(case["members"]).encode(),
                 ".spec/requirements/REQ-001.md": (multi_reference.REQ_HEAD + "\n" + multi_reference.REQ_BODY).encode()}
        for path, workspace in case["configs"].items():
            files[path] = multi_reference.plain_config(workspace).encode()
    elif kind == "mimpl":
        root = case["owner"] == "platform"
        document = ("REQ-001", ".spec/requirements/REQ-001.md") if root else ("REQ-101", "apps/web/.spec/requirements/REQ-101.md")
        files = {".spec/bitz.yaml": (multi_root(MEMBERS) + (VERIFY_BLOCK if root and case["field"] == "tests" else "")).encode(),
                 "apps/web/.spec/bitz.yaml": multi_reference.plain_config("web").encode(),
                 "services/api/.spec/bitz.yaml": multi_reference.plain_config("api").encode(), **files,
                 document[1]: requirement_text(document[0], case["status"], case["field"], case["declared"]).encode()}
    elif kind == "mtask":
        files = {".spec/bitz.yaml": multi_root(MEMBERS).encode(),
                 multi_reference.ROOT_REQ_PATH: (multi_reference.REQ_HEAD + "\n" + multi_reference.REQ_BODY).encode(),
                 "apps/web/.spec/bitz.yaml": multi_reference.plain_config("web").encode(),
                 "services/api/.spec/bitz.yaml": multi_reference.plain_config("api").encode(), **files,
                 "apps/web/.spec/tasks/TASK-010.md": WEB_TASK_TEXT.format(changes=case["changes"]).encode()}
    return {"files": files, "links": dict(case.get("links", {})), "changes": changes, "changeLinks": dict(case.get("changeLinks", {}))}


def final_name(path, renames):
    """付け替えの後の名前。付け替えは配列順に適用する。"""
    for source, target in renames:
        if path == source or path.startswith(source + "/"):
            path = target + path[len(source):]
    return path


def operations(case):
    if case["kind"] == "verify":
        return [{"op": "stage", "paths": ["."]}]
    if case["kind"] == "changed":
        return [{"op": "update", "path": case["changed"], "source": "changes/c.py"}]
    return [{"op": op, "path": path, "source": source} for op, path, source in case.get("operations", [])]


def argv_of(case):
    kind = case["kind"]
    if kind == "path":
        return ["check", "--full", "--base", "HEAD"]
    if kind == "verify":
        return ["verify", "REQ-001"]
    if kind == "task":
        return ["check", "TASK-001", "--base", "HEAD"]
    if kind == "changed":
        return ["check", "--base", "HEAD"]
    if kind == "explicit":
        return ["check", case["argument"], "--base", "HEAD"]
    if kind == "mtask":
        return ["check", "web::TASK-010", "--base", "HEAD"]
    return ["check", "--all-workspaces", "--base", "HEAD"]


def operation_of(case):
    return "verify" if case["kind"] == "verify" else "check"


def reviewed_manifest(identifier):
    case = CASES[identifier]
    plan = {"git": True}
    if case["materialize"]:
        plan["materialize"] = [{"from": source, "to": target} for source, target in case["materialize"]]
    if case["kind"] != "verify":
        plan["baseCommit"] = {"message": "base", "paths": ["."]}
    plan["operations"] = operations(case)
    status = reviewed_result(identifier)["status"]
    return {"fixtureId": identifier, "description": case["description"], "setup": plan,
            "invocation": {"runner": "bitz", "cwd": ".", "argv": [*argv_of(case), "--format", "json"], "env": {}},
            "expect": {"status": status, "exitCode": EXIT[status], "stdout": "json", "resultFile": f"expected/{operation_of(case)}.json", "reportFileCount": 0}}


# --- 期待結果（ラベルから組み立てる。ラベルは、ケースの定義と、準備手順の後の入力からの参照計算の両方から得る） ----------

def check_envelope(status, scope="full", dirty=False, **extra):
    return {"schemaVersion": "1.0", "operation": "check", "status": status, "scope": scope, "workspace": {"id": "root", "path": "."},
            "revision": {"base": COMMIT, "commit": COMMIT, "dirty": dirty}, "durationMs": 0, **extra}


def path_diagnostic(field, label, status):
    key = "implements" if field == "implements" else "tests[0].path"
    source = {"kind": "file", "workspaceId": "root", "path": ".spec/requirements/REQ-001.md", "key": key}
    if label == "missing":
        return {"code": "SPEC-PATH-INVALID-001", "severity": "error", "resultStatus": "failed", "summary": PATH_SUMMARIES[field], "source": source}
    draft = status == "draft"
    return {"code": "SPEC-PATH-INVALID-001", "severity": "warning" if draft else "error",
            "resultStatus": "passed_with_warnings" if draft else "failed", "summary": COLLISION_SUMMARIES[field], "source": source}


def relative_tests(case):
    """宣言したとおりの綴りのテストのパスの、`cwd`相対（公開結果の`argv`の展開。重複なし、宣言の文字列の昇順。字句のセグメントで相対化する）。"""
    root = [] if case["cwd"] == "." else case["cwd"].split("/")
    declared = sorted({path for tests in case["tests"] for path in tests})
    assert all(path.split("/")[:len(root)] == root for path in declared)
    return declared, ["/".join(path.split("/")[len(root):]) for path in declared]


def actual_spelling(repository, declared):
    """基準のルート`repository`の、宣言したパスの実在の綴り（ディレクトリの項目名。NFCで一致する項目）。存在しなければ`None`。"""
    current, names = Path(repository), []
    for segment in declared.split("/"):
        found = [entry for entry in os.listdir(current) if lexical.segments(entry) == lexical.segments(segment)]
        if len(found) != 1:
            return None
        names.append(found[0])
        current = current / found[0]
    return "/".join(names)


def process_arguments(case, repository):
    """プロセスへ渡す引数（実在の綴りの`cwd`相対のテストのパス）。公開結果の引数（宣言の綴り）とは、NFDの名前の分だけ異なる。"""
    root = [] if case["cwd"] == "." else case["cwd"].split("/")
    declared, _ = relative_tests(case)
    return ["/".join(actual_spelling(repository, path).split("/")[len(root):]) for path in declared]


def passed_verify_result(case):
    """コマンドを起動して通る結果（`{tests}`の展開の試験）。公開結果の`argv`と`tests`は宣言の綴り。"""
    declared, relative = relative_tests(case)
    entry = {"target": "REQ-001", "status": "passed", "contextDigest": real_path.verify_digest(case), "statements": list(STATEMENTS),
             "bindingRefs": ["root::default"], "diagnostics": []}
    command = {"bindingId": "root::default", "workspaceId": "root", "name": "default", "status": "passed", "termination": "exit", "cwd": case["cwd"],
               "argv": [*ARGV_TEMPLATE[:-1], *relative], "tests": declared, "covers": list(STATEMENTS), "exitCode": 0, "timeoutSeconds": 300,
               "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}
    return {"schemaVersion": "1.0", "operation": "verify", "status": "passed", "scope": "selected", "workspace": {"id": "root", "path": "."},
            "targetResults": [entry], "revision": None, "commands": [command], "durationMs": 0, "diagnostics": []}


def verify_result(case, label, aux):
    if label == "passed":
        return passed_verify_result(case)
    top = []
    entry = {"target": "REQ-001", "status": "failed" if label == "failed" else "blocked", "contextDigest": real_path.verify_digest(case),
             "statements": list(STATEMENTS), "bindingRefs": [], "diagnostics": []}
    if label == "failed":
        for document, index, kind in aux:
            entry["diagnostics"].append({"code": "SPEC-PATH-INVALID-001", "severity": "error", "resultStatus": "failed",
                                         "summary": COLLISION_SUMMARIES["tests"] if kind == "collision" else PATH_SUMMARIES["tests"],
                                         "source": {"kind": "file", "workspaceId": "root", "path": f".spec/technical/{document}.md", "key": f"tests[{index}].path"}})
    elif label == "cwd":
        top.append({"code": "SPEC-VERIFY-BLOCKED-001", "severity": "error", "resultStatus": "blocked", "summary": CWD_SUMMARY,
                    "source": {"kind": "file", "workspaceId": "root", "path": ".spec/bitz.yaml", "key": "verify.commands.default.cwd"}})
    else:
        document, index = aux
        top.append({"code": "SPEC-VERIFY-BLOCKED-001", "severity": "error", "resultStatus": "blocked", "summary": OUTSIDE_SUMMARY,
                    "source": {"kind": "file", "workspaceId": "root", "path": f".spec/technical/{document}.md", "key": f"tests[{index}].path"}})
    return {"schemaVersion": "1.0", "operation": "verify", "status": entry["status"], "scope": "selected", "workspace": {"id": "root", "path": "."},
            "targetResults": [entry], "revision": None, "commands": [], "durationMs": 0, "diagnostics": top}


def multi_envelope(status, workspaces, diagnostics):
    return {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": status, "multiWorkspace": {"id": "platform", "path": "."},
            "workspaces": workspaces, "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False}, "durationMs": 0, "diagnostics": diagnostics}


def build_result(case, label, aux=None):
    kind = case["kind"]
    if kind == "path":
        if label == "ok":
            return check_envelope("passed", checkedDocumentCount=1, checkedStatementCount=1, diagnostics=[])
        status = "passed_with_warnings" if label == "collision" and case["status"] == "draft" else "failed"
        return check_envelope(status, checkedDocumentCount=1, checkedStatementCount=1, diagnostics=[path_diagnostic(case["field"], label, case["status"])])
    if kind == "verify":
        return verify_result(case, label, aux)
    if kind == "task":
        diagnostics = [{"code": "SPEC-TASK-BOUNDARY-001", "severity": "error", "resultStatus": "failed", "summary": f"パス{path}はTASK-001の変更許可パスの外です",
                        "source": {"kind": "file", "workspaceId": "root", "path": path}} for path in aux]
        return check_envelope("failed" if aux else "passed", scope="selected", dirty=bool(case["operations"]), checkedDocumentCount=1, checkedStatementCount=0,
                              diagnostics=diagnostics)
    if kind == "changed":
        return check_envelope("passed", scope="changed", dirty=True, diagnostics=[],
                              selection={"changedPathCount": aux[0], "targetDocumentCount": aux[1], "excludedCodeTestPathCount": aux[2]})
    if kind == "explicit":
        if label == "ok":
            return check_envelope("passed", scope="selected", checkedDocumentCount=1, checkedStatementCount=1, diagnostics=[])
        return check_envelope("failed", scope="selected", checkedDocumentCount=0, checkedStatementCount=0, diagnostics=[
            {"code": "CTX-ROOT-MISSING-001", "severity": "error", "resultStatus": "failed", "summary": f"起点{case['argument']}が存在しません",
             "source": {"kind": "invocation", "argument": case["argument"]}}])
    if kind == "mmembers":
        if label == "ok":
            entries = [{"id": "platform", "path": ".", "status": "passed", "checkedDocumentCount": 1, "checkedStatementCount": 2, "durationMs": 0, "diagnostics": []}]
            entries += [{"id": identifier, "path": path, "status": "passed", "checkedDocumentCount": 0, "checkedStatementCount": 0, "durationMs": 0, "diagnostics": []}
                        for identifier, path in sorted(case["members"])]
            return multi_envelope("passed", entries, [])
        return multi_envelope("failed", [], [{"code": "SPEC-MULTI-PATH-001", "severity": "error", "resultStatus": "failed", "summary": MEMBER_SUMMARIES[label],
                                              "source": {"kind": "file", "workspaceId": "platform", "path": ".spec/bitz.yaml", "key": "multiWorkspace.members"}}])
    if kind == "mimpl":
        owner = case["owner"]
        document = "REQ-001" if owner == "platform" else "REQ-101"
        key = "implements" if case["field"] == "implements" else "tests[0].path"
        source = {"kind": "file", "workspaceId": owner, "path": f".spec/requirements/{document}.md", "key": key}
        # 重大度と状態: 不在と衝突は文書の状態で分ける（approvedはerror／failed、draftはwarning／passed_with_warnings）。所有の違反は状態によらずerror／failed。
        draft = case["status"] == "draft"
        warned = label in ("draft", "collision") and draft
        diagnostic = None
        if label == "ownership":
            diagnostic = {"code": "SPEC-MULTI-OWNERSHIP-001", "severity": "error", "resultStatus": "failed",
                          "summary": OWNERSHIP_SUMMARY.format(path=case["declared"], workspace=owner), "source": source}
        elif label in ("missing", "collision", "draft"):
            summary = COLLISION_SUMMARIES[case["field"]] if label == "collision" else (DRAFT_SUMMARIES if label == "draft" else PATH_SUMMARIES)[case["field"]]
            diagnostic = {"code": "SPEC-PATH-INVALID-001", "severity": "warning" if warned else "error",
                          "resultStatus": "passed_with_warnings" if warned else "failed", "summary": summary, "source": source}
        state = "passed" if diagnostic is None else ("passed_with_warnings" if warned else "failed")
        entries = []
        for identifier_, path in (("platform", "."), ("api", "services/api"), ("web", "apps/web")):
            declares = identifier_ == owner
            entries.append({"id": identifier_, "path": path, "status": state if declares else "passed", "checkedDocumentCount": 1 if declares else 0,
                            "checkedStatementCount": 1 if declares else 0, "durationMs": 0, "diagnostics": [diagnostic] if declares and diagnostic else []})
        return multi_envelope(state, entries, [])
    return {"schemaVersion": "1.0", "operation": "check", "scope": "selected", "status": "failed" if aux else "passed", "workspace": {"id": "web", "path": "apps/web"},
            "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False}, "checkedDocumentCount": 1, "checkedStatementCount": 0, "durationMs": 0, "diagnostics": []}


def reviewed_aux(case):
    kind = case["kind"]
    if kind == "verify":
        return case["invalid"] if case["outcome"] == "failed" else case["source"]
    if kind == "task":
        return list(case["violations"])
    if kind == "changed":
        return (1, 1, 0)
    if kind == "mtask":
        return []
    return None


def reviewed_result(identifier):
    case = CASES[identifier]
    return build_result(case, case["outcome"], reviewed_aux(case))


# --- 準備手順の後の入力からの参照計算（字句の規則だけ。Coreにも`realpath`にも依存しない） ---------------

def changed_paths(repository):
    return [name for name in git(repository, "diff", "--name-only", "-z", "HEAD").decode().split("\0") if name]


def allowed_by(name, entries):
    """TASKの`changes`の許可（字句のパス。ファイルは完全一致、末尾が`/`のディレクトリはセグメント単位の子孫一致）。"""
    own = lexical.segments(name)
    for entry in entries:
        rule = lexical.segments(entry)
        if entry.endswith("/"):
            if own[:len(rule)] == rule and len(own) > len(rule):
                return True
        elif own == rule:
            return True
    return False


def sandbox_label(identifier, repository):
    """準備手順の後の作業ツリーから、ラベルと補助の値を導く。"""
    case = CASES[identifier]
    kind = case["kind"]
    if kind == "path":
        found = lexical.lookup(repository, case["declared"], "file")
        return {"ok": "ok", "collision": "collision"}.get(found, "missing"), None
    if kind == "verify":
        declared = real_path.tech_documents(case)
        invalid = []
        for document in sorted(declared):
            for index, (path, _) in enumerate(declared[document]):
                found = lexical.lookup(repository, path, "file")
                if found != "ok":
                    invalid.append((document, index, "collision" if found == "collision" else "missing"))
        if invalid:
            return "failed", invalid
        if lexical.lookup(repository, case["cwd"], "directory") != "ok":
            return "cwd", None
        for document in sorted(declared):
            for index, (path, _) in enumerate(declared[document]):
                if not lexical.within(path, case["cwd"]):
                    return "outside", (document, index)
        return "passed", None
    if kind == "task":
        violations = sorted(name for name in changed_paths(repository) if not allowed_by(name, case["changes"]))
        return ("violation" if violations else "ok"), violations
    if kind == "changed":
        changed = changed_paths(repository)
        matched = [name for name in changed if lexical.segments(name) == lexical.segments(case["declared"])]
        return "matched", (len(changed), 1 if matched else 0, len(changed) - len(matched))
    if kind == "explicit":
        names = sorted(path.name for path in (repository / ".spec/requirements").iterdir())
        target = lexical.segments(case["argument"])
        matches = [name for name in names if lexical.segments(f".spec/requirements/{name}") == target]
        return ("ok" if len(matches) == 1 else "missing"), None
    if kind == "mmembers":
        return member_label(case, repository), None
    if kind == "mimpl":
        # 所有の判定（字句のパス）を存在の検査より先に行う（複合ワークスペース仕様 §5.1）。
        prefix = "" if case["owner"] == "platform" else "apps/web"
        declared = f"{prefix}/{case['declared']}" if prefix else case["declared"]
        roots = {"platform": ".", "web": "apps/web", "api": "services/api"}
        if lexical.owner(declared, roots) != case["owner"]:
            return "ownership", None
        found = lexical.lookup(repository / prefix if prefix else repository, case["declared"], "file")
        if found == "ok":
            return "ok", None
        if found == "collision":
            return "collision", None
        return ("draft" if case["status"] == "draft" else "missing"), None
    # mtask: `changes`は存在の検査も所有の判定も行わず、差分のパスだけを許可と照合する。
    violations = sorted(name for name in changed_paths(repository) if not allowed_by(name, [f"apps/web/{case['changes']}"]))
    return ("violation" if violations else "ok"), violations


def member_label(case, repository):
    """メンバーのパスの検査（複合ワークスペース仕様 §2・§5.1）。衝突、リンク、重複、入れ子の順に、最初の不適合を返す。"""
    paths = [path for _, path in case["members"]]
    found = [lexical.lookup(repository, path, "directory") for path in paths]
    if "collision" in found:
        return "collision"
    if "link" in found:
        return "link"
    names = [lexical.segments(path) for path in paths]
    if len(set(names)) != len(names):
        return "duplicate"
    if any(a != b and b[:len(a)] == a for a in names for b in names):
        return "nested"
    return "ok"


# --- 準備手順の後の入力の検査 ---------------------------------------------------------------

def expected_entries(identifier):
    """付け替えの後の、追跡する通常のファイルとシンボリックリンクの期待値。"""
    case = CASES[identifier]
    reviewed = reviewed_inputs(identifier)
    renames = case["materialize"]
    return ({final_name(path, renames): data for path, data in reviewed["files"].items()},
            {final_name(path, renames): target for path, target in reviewed["links"].items()})


def check_conditions(identifier, repository, manifest, result):
    case = CASES[identifier]
    entries = real_path.tracked_entries(repository)
    files = {path: data for path, (mode, data) in entries.items() if mode == "100644"}
    links = {path: data.decode() for path, (mode, data) in entries.items() if mode == "120000"}
    if {path for path, (mode, _) in entries.items() if mode not in ("100644", "120000")}:
        raise ValueError("追跡するエントリは通常のファイルとシンボリックリンクだけである必要があります")
    if (files, links) != expected_entries(identifier):
        raise ValueError("インデックスが、付け替えの後のレビュー済みの入力と異なります")
    modified = {op["path"] for op in operations(case) if op["op"] == "update"}
    for path, target in links.items():
        if not (repository / path).is_symlink() or (path not in modified and os.readlink(repository / path) != target):
            raise ValueError("作業ツリーのシンボリックリンクがレビュー済みの入力と異なります")
    if case["kind"] != "verify":
        tree = git(repository, "ls-tree", "-r", "-z", "HEAD").decode().split("\0")[:-1]
        if {line.split("\t", 1)[1] for line in tree} != set(entries):
            raise ValueError("基準版のコミットとインデックスの追跡するパスが異なります")
    label, aux = sandbox_label(identifier, repository)
    if label != case["outcome"]:
        raise ValueError(f"入力から導く結果が期待と異なります: {label}")
    if build_result(case, label, aux) != result:
        raise ValueError("完全結果が、準備手順の後の入力から導く結果と異なります")
    if (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (result["status"], EXIT[result["status"]]):
        raise ValueError("状態または終了コードが参照計算と異なります")
    if case["kind"] == "path" and case["outcome"] == "missing" and case["links"]:
        # リンクを辿れば存在する入力にする（辿らないことだけが原因になる）。
        if not os.path.isfile(repository / case["declared"]):
            raise ValueError("リンクを辿れば存在する入力である必要があります")
    if case["kind"] == "mimpl" and case["outcome"] in ("ownership", "draft"):
        # 存在しない予定のパスである（存在の検査より先に所有を判定することだけが原因になる）。
        joined = case["declared"] if case["owner"] == "platform" else f"apps/web/{case['declared']}"
        if os.path.lexists(repository / joined):
            raise ValueError("対象のパスは存在しない予定である必要があります")
    if case["kind"] == "verify" and case["outcome"] == "passed":
        # 実在の綴りの引数は、通常のファイルとして実在する。宣言の綴りの引数と異なるのは、実在の綴りがNFDのとき（欠陥）だけである。
        arguments = process_arguments(case, repository)
        if any(not os.path.isfile(repository / ("" if case["cwd"] == "." else actual_spelling(repository, case["cwd"])) / argument) for argument in arguments):
            raise ValueError("実在の綴りの引数が通常のファイルとして開ける必要があります")
        if (arguments != relative_tests(case)[1]) != case["spelling"]:
            raise ValueError("実在の綴りの引数が宣言の綴りと異なるかが、ケースの定義と食い違います")
    if case["kind"] in ("task", "changed"):
        wanted = {op["path"] for op in operations(case)}
        if set(changed_paths(repository)) != wanted:
            raise ValueError("差分のパスが準備手順の操作と異なります")
    if case["kind"] == "verify":
        derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository))
        if digest_crosscheck.digest(derived) != result["targetResults"][0]["contextDigest"]:
            raise ValueError("検証対象のハッシュ値が参照計算Bと一致しません")
        if digest_reference.canonical_bytes(real_path.verify_digest_input(case)) != derived:
            raise ValueError("検証対象のハッシュ値の参照計算AとBが一致しません")


# --- 書き出しと監査 ---------------------------------------------------------------------------

def dump(value):
    """JSON。結合文字（U+0301）は`\\u0301`で書き、エディタやツールの正規化の影響を受けないようにする。"""
    return json.dumps(value, ensure_ascii=False, indent=2).replace("́", "\\u0301") + "\n"


def fixture_dir(root, identifier):
    return root / ("multi" if identifier.startswith("MULTI-") else "single") / identifier


def write_inputs(fixture, reviewed):
    for name, content in reviewed["files"].items():
        path = fixture / "repo" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    for name, target in reviewed["links"].items():
        link = fixture / "repo" / name
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            link.unlink()
        link.symlink_to(target)
    for name, content in reviewed["changes"].items():
        path = fixture / "changes" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    for name, target in reviewed["changeLinks"].items():
        link = fixture / "changes" / name
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            link.unlink()
        link.symlink_to(target)


def generate(root=HERE):
    for identifier, case in CASES.items():
        fixture = fixture_dir(root, identifier)
        write_inputs(fixture, reviewed_inputs(identifier))
        manifest = reviewed_manifest(identifier)
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "manifest.json").write_text(dump(manifest))
        (fixture / f"expected/{operation_of(case)}.json").write_text(dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-strict-path-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def actual_entries(fixture, directory):
    files, links = {}, {}
    base = fixture / directory
    for current, names, filenames in os.walk(base, followlinks=False):
        for name in [*names, *filenames]:
            path = Path(current) / name
            relative = path.relative_to(base).as_posix()
            if path.is_symlink():
                links[relative] = os.readlink(path)
            elif path.is_file():
                if path.stat().st_mode & 0o111:
                    raise ValueError(f"{relative}は実行ビットを持ってはいけません")
                files[relative] = path.read_bytes()
    return files, links


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text())) for name in ("manifest", "result", "side-effects")}
    for identifier, case in CASES.items():
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = fixture_dir(root, identifier)
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / f"expected/{operation_of(case)}.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            if {p.name for p in (fixture / "expected").glob("*")} != {f"{operation_of(case)}.json"}:
                raise ValueError("期待結果のファイルの構成がレビュー済みの形と異なります")
            reviewed = reviewed_inputs(identifier)
            if actual_entries(fixture, "repo") != (reviewed["files"], reviewed["links"]):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            wants_changes = bool(reviewed["changes"] or reviewed["changeLinks"])
            if (fixture / "changes").exists() != wants_changes or (
                    wants_changes and actual_entries(fixture, "changes") != (reviewed["changes"], reviewed["changeLinks"])):
                raise ValueError("`changes`がレビュー済みの入力と異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("パスの検査はファイルを書いてはいけません")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-strict-path-") as temporary:
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
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run", "references": 2,
            "status": "Passed" if not errors else "Failed", "errors": errors}
