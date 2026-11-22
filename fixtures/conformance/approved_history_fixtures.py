"""承認済みの契約の保護をTECHへ広げ、途中のコミットで再承認を判定することを固定する（Coreの公開操作は実行しない）。

[ADR-072](../../docs/02.設計書/10_決定記録/ADR-072_承認済みの契約の保護をTECHへ広げ、途中のコミットの状態で再承認を判定する.md)、
[ADR-078](../../docs/02.設計書/10_決定記録/ADR-078_承認済みの契約の保護で認める途中の版を変更したコミットに限り、履歴の読取りに上限を設ける.md)、
[ADR-079](../../docs/02.設計書/10_決定記録/ADR-079_承認済みの契約の保護の途中のコミットの読み方と診断の形を定める.md)、
[文書・フロントマター・状態仕様 §8、§8.1、§8.2](../../docs/03.詳細設計/02_仕様文書モデル/02_文書・フロントマター・状態仕様.md#8-承認済み要求の保護)、
[`check` §5](../../docs/03.詳細設計/03_操作仕様/02_check.md#5-git基準版と変更集合)、
[安全な入出力・互換性 §4.1](../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md#41-上限の設定)、
診断レジストリの`CHECK-APPROVED-MEANING`と`CHECK-APPROVED-MEANING-HISTORY`を根拠とする。

群は次の4つである。

- `SINGLE-186-*`: TECHの保護と`source.key`。基準版は`HEAD`で、途中のコミットはない（端点の比較だけ。§8.1）。
- `SINGLE-187-*`: 途中のコミット（§8.1）。準備の処理`commit`、`branch`、`checkout`、`merge`で履歴を作る（ADR-080）。
- `SINGLE-188-*`: 途中のコミットを完全には読めない場合（シャロークローンの境界、`limits.historyCommitCount`）、保護を無効にした設定、
  明示対象、`--base`なし、`--format text`。
- `MULTI-071-*`: 複合ワークスペースの作業ワークスペースと`--all-workspaces`。

期待値の根拠は規範文と、このモジュールの参照計算（`reference_diagnostics`）だけである。Coreの出力は根拠にしない。
参照計算は、隔離した準備手順の後のGitのリポジトリから、基準版と現在版（作業ツリー）の仕様文書をIDで対応付け、意味の変わった`approved`の文書
（違反の候補）を求め、途中のコミット（`HEAD`から到達でき基準版から到達できないコミット）とその親の仕様文書から§8.1の判定をし、
レビュー済みのリテラルの診断と一致することを確かめる。仕様文書の読み方は、このfixtureの入力に限った字句の読み方であり、汎用のYAMLの構文解析器ではない。
"""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .document_fixtures import DOCUMENT, REQ_PATH
from .harness import git, setup
from .initial_fixtures import CONFIGS, compare_state, observe
from .schemas import schema_path
from .trace_fixtures import TECH as NO_STATEMENT_TECH

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
CONFIG_PATH = ".spec/bitz.yaml"
CONFIG = CONFIGS["SINGLE-001"].encode()
TECH_PATH = ".spec/technical/TECH-001.md"
REQ2_PATH = ".spec/requirements/REQ-002.md"
CODE = "SPEC-SAFETY-APPROVED-001"
# 承認済みの文言（ADR-078の決定5。Coreの出力文言のレビュー記録.mdの2026-11-21の節）。
SUMMARY = "状態approvedの{kind}の意味変更時に文書の状態が戻されていません"
HISTORY_SUMMARY = "状態approvedの{kind}の意味変更時に文書の状態が戻されていません（途中のコミットを完全には読めません）"
# §8.2の`source.key`の順。関係型は関係・トレースモデル §3の表の順。
KEY_ORDER = ("title", "relations.requires", "relations.refines", "relations.addresses", "relations.supersedes", "statements")
STRONG = ("requires", "refines", "addresses", "supersedes")
LIMIT_HISTORY = 10000
LIMIT_SPEC_BYTES = 1048576
LIMIT_FRONTMATTER_BYTES = 32768
LIMIT_ARRAY_ITEMS = 1000
ABSOLUTE_LIMITS = (LIMIT_SPEC_BYTES, LIMIT_FRONTMATTER_BYTES, LIMIT_ARRAY_ITEMS)
# 参照計算の読み方。既定は規範文の読み方で、監査の自己試験は別の読み方（ミュータント）へ差し替え、どのfixtureが拒否するかを確かめる。
# - `recognize`: `state`は途中の版の状態を`draft`または`outdated`へ変えた版だけを認める（§8.1、ADR-081）。`content`はADR-081の前の定義
#   （文書を変更した`draft`または`outdated`の版を認める。ADR-078の決定1）。
# - `boundary`: `spec`は境界のコミットが`HEAD`または基準版から到達できれば完全に得られないとする（§8.1）。`head`は`HEAD`から到達できる場合だけ、
#   `adjacent`は境界が途中のコミットまたはその親である場合だけとする（検収で示された、通ってしまう2つの読み方）。
# - `duplicates`: `skip`は同じIDの文書が2つ以上ある親との比較で状態を変えたとしない（§8.1）。`absent`はその親に文書がないとみなす。
# - `recognize`の`differs`は、版の状態が親の状態と異なれば状態を変えたとする（`outdated`から`draft`への変更も含む。再検収のG-2）。
# - `walk`: `all`はすべての途中のコミット（§8.1）。`first-parent`は1つ目の親の列だけをたどる（G-1）。
# - `parents`: `all`はすべての親と比べる（§8.1「親の少なくとも1つ」）。`first`はマージコミットの1つ目の親とだけ比べる（G-1）。
# - `unreadable`: `absent`はIDを読めない親の版を、同じIDの文書がない親とする（§8.1。索引に入らない版と同じ）。
#   `unchanged`はその親との比較で状態を変えたとしない（G-3）。
# - `protection`（ADR-082の決定4）: `either`は基準版と現在版のどちらかの設定で有効なら有効（§8）。`current`は現在版の設定だけ、`base`は基準版の設定だけで決める。
#   `lenient`は、値が真偽値でない`"false"`もfalseと読む（スキーマに適合しない基準版の設定を有効とみなさない）。
# - `array`（ADR-082の決定3）: `apply`は途中の版にも`documentArrayItemCount`を当てる（§4.1）。`ignore`は当てない。
READING = {"recognize": "state", "boundary": "spec", "duplicates": "skip", "walk": "all", "parents": "all", "unreadable": "absent",
           "protection": "either", "array": "apply", "protection_workspace": "own"}
# - `protection_workspace`（ADR-082の決定5）: `own`は各ワークスペース自身の設定で判定する。`root`はルートワークスペースの設定で判定する。


# --- 入力の文書 ---------------------------------------------------------------------------------

REQ_TITLE, REQ_TITLE_CHANGED = "文書の検査", "変更後の文書検査"
REQ_OPERATION, REQ_OPERATION_CHANGED = "秘密情報を出力しない。", "秘密情報をログへ出力しない。"
TECH_TITLE, TECH_TITLE_CHANGED = "出力の制約", "改訂した出力の制約"
TECH_DOC = ("---\nid: TECH-001\ntitle: 出力の制約\nstatus: approved\n---\n\n# TECH-001 出力の制約\n\n"
            "## Context\n\n出力の技術契約。\n\n## Contract\n\n"
            "- [TECH-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n")


def status(document, value):
    if document.count("status: approved\n") != 1:
        raise ValueError("文書の状態の行がレビュー済みの形と異なります")
    return document.replace("status: approved\n", f"status: {value}\n", 1)


def relations(document, lines):
    """フロントマターの最後へ`relations`を足す。`lines`は`requires: [TECH-001]`のような行。"""
    block = "relations:\n" + "".join(f"  {line}\n" for line in lines)
    marker = "\n---\n"
    end = document.index(marker, 4)
    return document[:end + 1] + block + document[end + 1:]


def req(title=REQ_TITLE, state="approved", operation=REQ_OPERATION, extra=(), identifier="REQ-001", verification=None):
    document = DOCUMENT.replace(REQ_TITLE, title).replace(REQ_OPERATION, operation)
    if verification is not None:
        document = document.replace("Core実装後に確認する。現時点では未証明。", verification)
    if extra:
        document = relations(document, extra)
    if state != "approved":
        document = status(document, state)
    return document.replace("REQ-001", identifier).encode()


def tech(title=TECH_TITLE, state="approved", operation=REQ_OPERATION, extra=(), context=None, identifier="TECH-001"):
    document = TECH_DOC.replace(TECH_TITLE, title).replace(REQ_OPERATION, operation)
    if context is not None:
        document = document.replace("出力の技術契約。", context)
    if extra:
        document = relations(document, extra)
    if state != "approved":
        document = status(document, state)
    return document.replace("TECH-001", identifier).encode()


def no_statement_tech(title="前提技術", context=None):
    document = NO_STATEMENT_TECH.replace("前提技術", title)
    if context is not None:
        document = document.replace(f"規範文を持たない{title}。", context)
    return document.encode()


def limits_config(**values):
    return CONFIG + b"limits:\n" + b"".join(f"  {key}: {value}\n".encode() for key, value in values.items())


UNPROTECTED_CONFIG = CONFIG + b"safety:\n  protectApprovedRequirements: false\n"
# IDを読めない途中の版（YAMLの構文の不正。`check` §5の索引に入らない版）。状態の行は`draft`である。
BROKEN_DRAFT = ("---\nid: REQ-001\ntitle: [閉じていない\nstatus: draft\n---\n\n# REQ-001 閉じていない\n\n"
                "## Intent\n\n文書構造を検査する。\n").encode()
NOTE = "# 作業のメモ\n".encode()
# ファイルごとの上限を超える途中の版。現在版より長い説明文を持つ`draft`の版。
PADDED_DRAFT = req(REQ_TITLE_CHANGED, "draft", verification="Core実装後に確認する。現時点では未証明。再承認の前に確認の手順を追記した。")
SIZE_LIMIT = len(PADDED_DRAFT)


def update(path, source):
    return {"op": "update", "path": path, "source": source}


def commit(message):
    return {"op": "commit", "message": message}


def change(path, source, message):
    """`path`を`source`で置換し、ステージしてコミットする。"""
    return [update(path, source), {"op": "stage", "paths": [path]}, commit(message)]


def create(path, source, message):
    return [{"op": "create", "path": path, "source": source}, {"op": "stage", "paths": [path]}, commit(message)]


def branch(name):
    return {"op": "branch", "name": name}


def checkout(name):
    return {"op": "checkout", "name": name}


def merge(name):
    return {"op": "merge", "name": name}


def shallow(*revisions):
    return {"op": "shallow", "revisions": list(revisions)}


def full(base="base"):
    return ["check", "--full", "--base", base, "--format", "json"]


def violation(path, key, kind, history=False, workspace="root"):
    return dict(path=path, key=key, kind=kind, history=history, workspace=workspace)


# --- ケース ---------------------------------------------------------------------------------
# id -> dict(repo, changes, operations, argv, cwd, documents（checkedDocumentCount）, statements, scope, dirty, violations, description)

BASE_REQ = {CONFIG_PATH: CONFIG, REQ_PATH: req()}
BASE_TECH = {CONFIG_PATH: CONFIG, TECH_PATH: tech()}


def endpoint(repo, current, violations, documents, statements, description, path=None):
    """基準版`HEAD`の作業ツリーだけを変える（途中のコミットはない。§8.1）。"""
    path = path or next(iter(current))
    return dict(repo=repo, changes={"current.md": current[path]}, operations=[update(path, "changes/current.md")],
                argv=full("HEAD"), documents=documents, statements=statements, dirty=True, violations=violations,
                description=description)


CASES = {
    # --- TECHの保護と`source.key`（SINGLE-186） ---
    "SINGLE-186-01": endpoint(BASE_TECH, {TECH_PATH: tech(TECH_TITLE_CHANGED)}, [violation(TECH_PATH, "title", "TECH")], 1, 1,
                              "状態approvedのTECHのtitleを、状態を戻さずに変えると保護の違反になる"),
    "SINGLE-186-02": endpoint(BASE_TECH, {TECH_PATH: tech(operation=REQ_OPERATION_CHANGED)},
                              [violation(TECH_PATH, "statements", "TECH")], 1, 1,
                              "状態approvedのTECHの規範文だけを、状態を戻さずに変えるとsource.keyがstatementsの違反になる"),
    "SINGLE-186-03": endpoint({**BASE_TECH, REQ_PATH: req()}, {TECH_PATH: tech(extra=["requires: [REQ-001]"])},
                              [violation(TECH_PATH, "relations.requires", "TECH")], 2, 2,
                              "状態approvedのTECHの強い関係だけを、状態を戻さずに変えるとsource.keyがrelations.requiresの違反になる"),
    "SINGLE-186-04": endpoint({CONFIG_PATH: CONFIG, TECH_PATH: no_statement_tech()}, {TECH_PATH: no_statement_tech("改訂した前提技術")},
                              [violation(TECH_PATH, "title", "TECH")], 1, 0,
                              "基準版と現在版のどちらにも規範文がないTECHも、titleの変更を保護の違反にする"),
    "SINGLE-186-05": endpoint(BASE_TECH, {TECH_PATH: tech(TECH_TITLE_CHANGED, "outdated")}, [], 1, 1,
                              "状態approvedのTECHのtitleを変え、状態をoutdatedへ戻した変更は通過する"),
    "SINGLE-186-06": endpoint(BASE_TECH, {TECH_PATH: tech(context="出力の技術契約。説明だけを補足する。")}, [], 1, 1,
                              "状態approvedのTECHの説明文だけの変更は保護の対象外で通過する"),
    "SINGLE-186-07": endpoint(BASE_REQ, {REQ_PATH: req(operation=REQ_OPERATION_CHANGED)},
                              [violation(REQ_PATH, "statements", "REQ")], 1, 1,
                              "状態approvedのREQの規範文だけを、状態を戻さずに変えるとsource.keyがstatementsの違反になる"),
    "SINGLE-186-08": endpoint({**BASE_REQ, TECH_PATH: no_statement_tech()}, {REQ_PATH: req(extra=["requires: [TECH-001]"])},
                              [violation(REQ_PATH, "relations.requires", "REQ")], 2, 1,
                              "状態approvedのREQの強い関係だけを、状態を戻さずに変えるとsource.keyがrelations.requiresの違反になる"),
    "SINGLE-186-09": endpoint({**BASE_REQ, TECH_PATH: no_statement_tech()},
                              {REQ_PATH: req(REQ_TITLE_CHANGED, operation=REQ_OPERATION_CHANGED, extra=["requires: [TECH-001]"])},
                              [violation(REQ_PATH, "title", "REQ")], 2, 1,
                              "title、強い関係、規範文を変えても診断は1件で、source.keyは最初の項目のtitleになる"),
    "SINGLE-186-10": endpoint({**BASE_REQ, REQ2_PATH: req(identifier="REQ-002"), TECH_PATH: no_statement_tech()},
                              {REQ_PATH: req(operation=REQ_OPERATION_CHANGED,
                                             extra=["refines: [REQ-002:AC-01]", "requires: [TECH-001]"])},
                              [violation(REQ_PATH, "relations.requires", "REQ")], 3, 2,
                              "規範文、refines、requiresを変えても診断は1件で、source.keyは関係型の順で最初のrelations.requiresになる"),
    "SINGLE-186-11": endpoint({**BASE_TECH, REQ_PATH: req()},
                              {TECH_PATH: tech(operation=REQ_OPERATION_CHANGED, extra=["refines: [REQ-001:AC-01]"])},
                              [violation(TECH_PATH, "relations.refines", "TECH")], 2, 2,
                              "TECHの規範文とrefinesを変えると、source.keyは規範文より前のrelations.refinesになる"),
}


def history(repo, changes, operations, violations, description, argv=None, documents=1, statements=1, dirty=False, **extra):
    return dict(repo=repo, changes=changes, operations=[branch("base"), *operations], argv=argv or full(),
                documents=documents, statements=statements, dirty=dirty, violations=violations, description=description, **extra)


REQ_VIOLATION = [violation(REQ_PATH, "title", "REQ")]
REQ_HISTORY = [violation(REQ_PATH, "title", "REQ", history=True)]
TECH_HISTORY = [violation(TECH_PATH, "title", "TECH", history=True)]
CHANGED = {"draft.md": req(REQ_TITLE_CHANGED, "draft"), "approved.md": req(REQ_TITLE_CHANGED)}
REAPPROVE = [*change(REQ_PATH, "changes/draft.md", "draft"), *change(REQ_PATH, "changes/approved.md", "approve")]
RENAMED_PATH = ".spec/requirements/REQ-001-renamed.md"
COPY_PATH = ".spec/requirements/REQ-001-copy.md"
# 承認の前（`draft`）の状態から始める履歴。基準版は承認したコミット（枝`base`）である。
PRE_APPROVAL = {CONFIG_PATH: CONFIG, REQ_PATH: req(state="draft")}
APPROVE = [branch("old"), *change(REQ_PATH, "changes/approved-a.md", "approve")]

CASES.update({
    # --- 途中のコミット（SINGLE-187） ---
    "SINGLE-187-01": history(BASE_REQ, CHANGED, REAPPROVE, [],
                             "途中のコミットでdraftへ戻してコミットし、再びapprovedにした変更は通過する"),
    "SINGLE-187-02": dict(history(BASE_REQ, {"outdated.md": req(state="outdated"), "approved.md": req(REQ_TITLE_CHANGED)},
                                  [*change(REQ_PATH, "changes/outdated.md", "outdated"),
                                   *change(REQ_PATH, "changes/approved.md", "approve")], [],
                                  "途中のコミットの版がoutdatedなら通過する。基準版はリビジョンの式HEAD~2で指定する",
                                  argv=full("HEAD~2")), operations=[*change(REQ_PATH, "changes/outdated.md", "outdated"),
                                                                   *change(REQ_PATH, "changes/approved.md", "approve")]),
    "SINGLE-187-03": history(BASE_REQ, {"rejected.md": req(state="rejected"), "approved.md": req(REQ_TITLE_CHANGED)},
                             [*change(REQ_PATH, "changes/rejected.md", "rejected"), *change(REQ_PATH, "changes/approved.md", "approve")],
                             REQ_VIOLATION, "途中のコミットの版がrejectedなら、draftまたはoutdatedの版として認めず違反のままにする"),
    "SINGLE-187-04": history(BASE_REQ, CHANGED,
                             [*change(REQ_PATH, "changes/approved.md", "change"), update(REQ_PATH, "changes/draft.md"),
                              {"op": "stage", "paths": [REQ_PATH]}, update(REQ_PATH, "changes/approved.md")],
                             REQ_VIOLATION, "draftの版をインデックスにだけ置いても途中の状態として認めず違反のままにする", dirty=True),
    "SINGLE-187-05": history(PRE_APPROVAL, {"approved-a.md": req(), "approved.md": req(REQ_TITLE_CHANGED), "note.md": NOTE},
                             [*APPROVE[1:], branch("base"), checkout("old"), *create("docs/note.md", "changes/note.md", "old"),
                              checkout("fixture"), *change(REQ_PATH, "changes/approved.md", "change"), merge("old"),
                              commit("merge old")],
                             REQ_VIOLATION,
                             "承認の前に分かれ、その文書に触れていない枝を取り込んでも、枝のdraftの版は途中の状態として認めない",
                             initial=[branch("old")]),
    "SINGLE-187-06": history(PRE_APPROVAL, {"approved-a.md": req(), "approved.md": req(REQ_TITLE_CHANGED),
                                            "draft-edit.md": req(state="draft", verification="Core実装後に確認する。手順を追記した。")},
                             [*APPROVE[1:], branch("base"), checkout("old"), *change(REQ_PATH, "changes/draft-edit.md", "old"),
                              checkout("fixture"), *change(REQ_PATH, "changes/approved.md", "change"), merge("old"),
                              commit("merge old")],
                             REQ_VIOLATION, "承認の前に分かれた枝でdraftの文書を編集したコミットは、状態をdraftへ変えていないので途中の状態として認めない",
                             initial=[branch("old")], merged=req(REQ_TITLE_CHANGED, verification="Core実装後に確認する。手順を追記した。")),
    "SINGLE-187-07": history(PRE_APPROVAL, {"approved-a.md": req(), "draft.md": req(state="draft"),
                                            "approved.md": req(REQ_TITLE_CHANGED), "note.md": NOTE},
                             [*APPROVE[1:], branch("base"), checkout("old"), *create("docs/note.md", "changes/note.md", "old"),
                              checkout("fixture"), merge("old"), update(REQ_PATH, "changes/draft.md"),
                              {"op": "stage", "paths": [REQ_PATH]}, commit("merge old"),
                              *change(REQ_PATH, "changes/approved.md", "approve")],
                             [], "マージコミットの版が2つ目の親と同じで1つ目の親と異なれば、文書を変更した版として認める",
                             initial=[branch("old")]),
    "SINGLE-187-08": history(BASE_REQ, CHANGED,
                             [*change(REQ_PATH, "changes/draft.md", "draft"), {"op": "rename", "from": REQ_PATH, "to": RENAMED_PATH},
                              update(RENAMED_PATH, "changes/approved.md"), {"op": "stage", "paths": [REQ_PATH, RENAMED_PATH]},
                              commit("rename and approve")],
                             [], "途中のコミットのdraftの版と現在版のパスが異なっても、IDで対応付けて途中の状態として認める",
                             current_path=RENAMED_PATH),
    "SINGLE-187-09": history(PRE_APPROVAL, {"approved-a.md": req(), "approved.md": req(REQ_TITLE_CHANGED)},
                             [*APPROVE[1:], branch("base"), checkout("old"), {"op": "rename", "from": REQ_PATH, "to": RENAMED_PATH},
                              {"op": "stage", "paths": [REQ_PATH, RENAMED_PATH]}, commit("old rename"), checkout("fixture"),
                              *change(REQ_PATH, "changes/approved.md", "change"), merge("old"), commit("merge old")],
                             [violation(RENAMED_PATH, "title", "REQ")],
                             "パスだけを変えたコミットは文書を変更していないので、その版のdraftを途中の状態として認めない",
                             initial=[branch("old")], current_path=RENAMED_PATH),
    "SINGLE-187-10": history(BASE_REQ, {"broken.md": BROKEN_DRAFT, "approved.md": req(REQ_TITLE_CHANGED)},
                             [*change(REQ_PATH, "changes/broken.md", "broken"), *change(REQ_PATH, "changes/approved.md", "approve")],
                             REQ_VIOLATION, "途中の版のフロントマターのYAMLの構文が不正でIDを読めなければ、draftの版として認めない"),
    "SINGLE-187-11": history({CONFIG_PATH: limits_config(specBytes=SIZE_LIMIT - 1), REQ_PATH: req()},
                             {"draft.md": PADDED_DRAFT, "approved.md": req(REQ_TITLE_CHANGED)},
                             [*change(REQ_PATH, "changes/draft.md", "draft"), *change(REQ_PATH, "changes/approved.md", "approve")],
                             REQ_VIOLATION, "途中の版がlimits.specBytesを超えればIDを読めない版とし、draftの版として認めない"),
    "SINGLE-187-12": history({CONFIG_PATH: limits_config(specBytes=SIZE_LIMIT), REQ_PATH: req()},
                             {"draft.md": PADDED_DRAFT, "approved.md": req(REQ_TITLE_CHANGED)},
                             [*change(REQ_PATH, "changes/draft.md", "draft"), *change(REQ_PATH, "changes/approved.md", "approve")],
                             [], "途中の版がlimits.specBytesちょうどなら読み、draftの版として認めて通過する"),
    "SINGLE-187-13": history(BASE_REQ, CHANGED,
                             [update(REQ_PATH, "changes/draft.md"), {"op": "create", "path": COPY_PATH, "source": "changes/draft.md"},
                              {"op": "stage", "paths": [REQ_PATH, COPY_PATH]}, commit("draft with copy"),
                              {"op": "delete", "path": COPY_PATH}, update(REQ_PATH, "changes/approved.md"),
                              {"op": "stage", "paths": [REQ_PATH, COPY_PATH]}, commit("approve")],
                             REQ_VIOLATION, "途中のコミットに同じIDの文書が2つあれば、そのコミットの版を途中の状態として認めない"),
    "SINGLE-187-14": history({**BASE_REQ, REQ2_PATH: req(identifier="REQ-002")},
                             {**CHANGED, "req2.md": req(REQ_TITLE_CHANGED, identifier="REQ-002")},
                             [update(REQ_PATH, "changes/draft.md"), update(REQ2_PATH, "changes/req2.md"),
                              {"op": "stage", "paths": [REQ_PATH, REQ2_PATH]}, commit("draft REQ-001 and change REQ-002"),
                              *change(REQ_PATH, "changes/approved.md", "approve")],
                             [violation(REQ2_PATH, "title", "REQ")],
                             "途中の状態は文書ごとに判定し、draftの版がないREQ-002だけを違反にする", documents=2, statements=2),
    "SINGLE-187-15": history(BASE_TECH, {"draft.md": tech(TECH_TITLE_CHANGED, "draft"), "approved.md": tech(TECH_TITLE_CHANGED)},
                             [*change(TECH_PATH, "changes/draft.md", "draft"), *change(TECH_PATH, "changes/approved.md", "approve")],
                             [], "TECHも、途中のコミットでdraftへ戻して再びapprovedにした変更は通過する"),
})
# 承認の前の枝`old`は、基準版のコミットの直後（承認の前）に作る。`history`は先頭に枝`base`を置くので、承認の後へ移す。
for _identifier in ("SINGLE-187-05", "SINGLE-187-06", "SINGLE-187-07", "SINGLE-187-09"):
    _case = CASES[_identifier]
    _case["operations"] = [*_case.pop("initial"), *_case["operations"][1:]]
for _case in CASES.values():
    _case["changes"] = dict(_case["changes"])

# 状態を戻した後の同じ枝の編集（ADR-081の`Consequences`）と、重複したIDの親（§8.1）、途中の版のフロントマターの上限（§4.1）。
DRAFT_EDIT = req(REQ_TITLE_CHANGED, "draft", verification="Core実装後に確認する。手順を追記した。")
APPROVED_EDIT = req(REQ_TITLE_CHANGED, verification="Core実装後に確認する。手順を追記した。")
LONG_NOTE = "x-note: " + "再承認の前に確認する手順と観点を、レビューの依頼に合わせてここへ書き足した。" * 2
FRONTMATTER_DRAFT = req(REQ_TITLE_CHANGED, "draft").replace(b"status: draft\n", f"status: draft\n{LONG_NOTE}\n".encode(), 1)
FRONTMATTER_LIMIT = len(FRONTMATTER_DRAFT.split(b"\n---\n", 1)[0]) - 3
CASES.update({
    "SINGLE-187-16": history(BASE_REQ, {"draft.md": req(REQ_TITLE_CHANGED, "draft"), "draft-edit.md": DRAFT_EDIT,
                                        "approved.md": APPROVED_EDIT},
                             [*change(REQ_PATH, "changes/draft.md", "draft"), *change(REQ_PATH, "changes/draft-edit.md", "edit draft"),
                              *change(REQ_PATH, "changes/approved.md", "approve")],
                             [], "draftへ戻した後に同じ枝で本文を編集しても、状態を戻したコミットが別にあるので通過する"),
    "SINGLE-187-17": history(BASE_REQ, CHANGED,
                             [update(REQ_PATH, "changes/draft.md"), {"op": "create", "path": COPY_PATH, "source": "changes/draft.md"},
                              {"op": "stage", "paths": [REQ_PATH, COPY_PATH]}, commit("draft with copy"),
                              {"op": "delete", "path": COPY_PATH}, {"op": "stage", "paths": [COPY_PATH]}, commit("remove copy"),
                              *change(REQ_PATH, "changes/approved.md", "approve")],
                             REQ_VIOLATION,
                             "同じIDの文書が2つある親との比較では状態を変えたとしないので、複製だけを削除したコミットのdraftの版も途中の状態として認めない"),
    "SINGLE-187-18": history({CONFIG_PATH: limits_config(frontmatterBytes=FRONTMATTER_LIMIT - 1), REQ_PATH: req()},
                             {"draft.md": FRONTMATTER_DRAFT, "approved.md": req(REQ_TITLE_CHANGED)},
                             [*change(REQ_PATH, "changes/draft.md", "draft"), *change(REQ_PATH, "changes/approved.md", "approve")],
                             REQ_VIOLATION, "途中の版のフロントマターがlimits.frontmatterBytesを超えればIDを読めない版とし、draftの版として認めない"),
    "SINGLE-187-19": history({CONFIG_PATH: limits_config(frontmatterBytes=FRONTMATTER_LIMIT), REQ_PATH: req()},
                             {"draft.md": FRONTMATTER_DRAFT, "approved.md": req(REQ_TITLE_CHANGED)},
                             [*change(REQ_PATH, "changes/draft.md", "draft"), *change(REQ_PATH, "changes/approved.md", "approve")],
                             [], "途中の版のフロントマターがlimits.frontmatterBytesちょうどなら読み、draftの版として認めて通過する"),
})

# 再検収（G-1〜G-3）: 2つ目の親の側だけにある状態を戻したコミット、マージコミットの2つ目の親とだけ状態が異なる版、
# `outdated`から`draft`への変更、IDを読めない親の版（§8.1、ADR-081）。
PRE_OUTDATED = {CONFIG_PATH: CONFIG, REQ_PATH: req(state="outdated")}
CASES.update({
    "SINGLE-187-20": history(BASE_REQ, CHANGED,
                             [branch("feat"), checkout("feat"), *REAPPROVE, checkout("fixture"), merge("feat"), commit("merge feat")],
                             [], "状態を戻したコミットがマージした枝（2つ目の親の側）だけにあっても、途中のコミットなので通過する"),
    "SINGLE-187-21": dict(history(PRE_APPROVAL, {"approved-a.md": req(), "draft.md": req(state="draft"),
                                                 "approved.md": req(REQ_TITLE_CHANGED), "note.md": NOTE},
                                  [branch("old"), *change(REQ_PATH, "changes/approved-a.md", "approve"), branch("base"),
                                   checkout("old"), *create("docs/note.md", "changes/note.md", "old"), merge("base"),
                                   update(REQ_PATH, "changes/draft.md"), {"op": "stage", "paths": [REQ_PATH]}, commit("merge base"),
                                   *change(REQ_PATH, "changes/approved.md", "approve")],
                                  [], "マージコミットのdraftの版は、1つ目の親もdraftでも、2つ目の親がapprovedなら状態を変えた版として認める")),
    "SINGLE-187-22": dict(history(PRE_OUTDATED, {"approved-a.md": req(), "draft.md": req(state="draft"),
                                                 "approved.md": req(REQ_TITLE_CHANGED)},
                                  [branch("old"), *change(REQ_PATH, "changes/approved-a.md", "approve"), branch("base"),
                                   checkout("old"), *change(REQ_PATH, "changes/draft.md", "old"), checkout("fixture"),
                                   *change(REQ_PATH, "changes/approved.md", "change"), merge("old"),
                                   update(REQ_PATH, "changes/approved.md"), {"op": "stage", "paths": [REQ_PATH]}, commit("merge old")],
                                  REQ_VIOLATION, "outdatedからdraftへの変更は、親の状態がoutdatedなので状態を変えた版ではなく、途中の状態として認めない")),
    "SINGLE-187-23": history(BASE_REQ, {"broken.md": BROKEN_DRAFT, **CHANGED},
                             [*change(REQ_PATH, "changes/broken.md", "broken"), *change(REQ_PATH, "changes/draft.md", "draft"),
                              *change(REQ_PATH, "changes/approved.md", "approve")],
                             [], "親の版のIDを読めなければ親に同じIDの文書がないとし、読めるdraftの版を状態を変えた版として認める"),
})
# 枝`base`を承認したコミットに作るケース。`history`が先頭に置いた枝`base`を除く。
for _identifier in ("SINGLE-187-21", "SINGLE-187-22"):
    CASES[_identifier]["operations"] = CASES[_identifier]["operations"][1:]

# ADR-082: 途中の版の`documentArrayItemCount`（決定3）。途中の`draft`の版だけが関係の配列を持つ。
ARRAY_DRAFT = req(REQ_TITLE_CHANGED, "draft", extra=["related: [REQ-002, REQ-003, REQ-004]"])
CASES.update({
    "SINGLE-189-05": history({CONFIG_PATH: limits_config(documentArrayItemCount=2), REQ_PATH: req()},
                             {"draft.md": ARRAY_DRAFT, "approved.md": req(REQ_TITLE_CHANGED)},
                             [*change(REQ_PATH, "changes/draft.md", "draft"), *change(REQ_PATH, "changes/approved.md", "approve")],
                             REQ_VIOLATION, "途中の版の関係の配列がlimits.documentArrayItemCountを超えればIDを読めない版とし、draftの版として認めない"),
    "SINGLE-189-06": history({CONFIG_PATH: limits_config(documentArrayItemCount=3), REQ_PATH: req()},
                             {"draft.md": ARRAY_DRAFT, "approved.md": req(REQ_TITLE_CHANGED)},
                             [*change(REQ_PATH, "changes/draft.md", "draft"), *change(REQ_PATH, "changes/approved.md", "approve")],
                             [], "途中の版の関係の配列がlimits.documentArrayItemCountちょうどなら読み、draftの版として認めて通過する"),
})
# ADR-082の決定4: 保護の有無を基準版と現在版の設定で判定する。どれも基準版は`HEAD`で、作業ツリーで設定とREQ-001の`title`を変える。
INVALID_PROTECTION_CONFIG = CONFIG + b'safety:\n  protectApprovedRequirements: "false"\n'


def setting_case(base_config, current_config, violations, description):
    changes = {"current.md": req(REQ_TITLE_CHANGED)}
    operations = [update(REQ_PATH, "changes/current.md")]
    if current_config != base_config:
        changes["bitz.yaml"] = current_config
        operations.insert(0, update(CONFIG_PATH, "changes/bitz.yaml"))
    return dict(repo={CONFIG_PATH: base_config, REQ_PATH: req()}, changes=changes, operations=operations, argv=full("HEAD"),
                documents=1, statements=1, dirty=True, violations=violations, description=description)


CASES.update({
    "SINGLE-189-01": setting_case(CONFIG, UNPROTECTED_CONFIG, REQ_VIOLATION,
                                  "基準版で有効な保護を、意味を変える同じ変更でfalseにしても、基準版の設定で有効なので違反にする"),
    "SINGLE-189-02": setting_case(UNPROTECTED_CONFIG, CONFIG, REQ_VIOLATION,
                                  "基準版でfalseの保護を現在版で有効に戻せば、現在版の設定で有効なので違反にする"),
    "SINGLE-189-03": setting_case(UNPROTECTED_CONFIG, UNPROTECTED_CONFIG, [],
                                  "基準版と現在版の両方の設定でfalseを明示した場合だけ、保護を無効にして通過する"),
    "SINGLE-189-04": setting_case(INVALID_PROTECTION_CONFIG, UNPROTECTED_CONFIG, REQ_VIOLATION,
                                  "基準版の設定がスキーマに適合しなければ基準版の側を有効とみなし、現在版でfalseにしても違反にする"),
})

FOUR_COMMITS = [branch("side"), *change(TECH_PATH, "changes/draft.md", "draft"), checkout("side"),
                *create("docs/note.md", "changes/note.md", "side"), checkout("fixture"), merge("side"), commit("merge side"),
                *change(TECH_PATH, "changes/approved.md", "approve")]
TECH_CHANGED = {"draft.md": tech(TECH_TITLE_CHANGED, "draft"), "approved.md": tech(TECH_TITLE_CHANGED), "note.md": NOTE}

CASES.update({
    # --- 完全には読めない場合、上限、範囲（SINGLE-188） ---
    "SINGLE-188-01": history(BASE_REQ, CHANGED, [*REAPPROVE, shallow("HEAD~1")], REQ_HISTORY,
                             "シャロークローンの境界がHEADから到達できれば、途中にdraftの版があっても完全には読めない違反にする"),
    "SINGLE-188-02": dict(history(BASE_REQ, {**CHANGED, "note.md": NOTE},
                                  [*create("docs/note.md", "changes/note.md", "note"), branch("base"), *REAPPROVE, shallow("base~1")],
                                  REQ_HISTORY, "シャロークローンの境界が基準版から到達できれば、途中のコミットとその親でなくても完全には読めない違反にする")),
    "SINGLE-188-03": history(BASE_REQ, {**CHANGED, "note.md": NOTE},
                             [branch("other"), checkout("other"), *create("docs/note.md", "changes/note.md", "other"),
                              checkout("fixture"), *REAPPROVE, shallow("other")],
                             [], "シャロークローンの境界がHEADからも基準版からも到達できなければ、通常どおり判定して通過する"),
    "SINGLE-188-04": dict(endpoint(BASE_REQ, {REQ_PATH: req(REQ_TITLE_CHANGED)}, REQ_VIOLATION, 1, 1,
                                   "基準版がHEADと同じ深さ1のシャロークローンでは、境界を見ずに端点の比較の通常の文言にする"),
                          operations=[shallow("HEAD"), update(REQ_PATH, "changes/current.md")]),
    "SINGLE-188-05": dict(history(BASE_REQ, {"approved.md": req(REQ_TITLE_CHANGED), "note.md": NOTE},
                                  [*create("docs/note.md", "changes/note.md", "note"), branch("old"),
                                   *change(REQ_PATH, "changes/approved.md", "change"), branch("base"), checkout("old"),
                                   shallow("HEAD")],
                                  REQ_VIOLATION, "HEADが基準版の祖先なら、境界を見ずに端点の比較の通常の文言にする")),
    "SINGLE-188-06": history({CONFIG_PATH: limits_config(historyCommitCount=3), TECH_PATH: tech()}, TECH_CHANGED, FOUR_COMMITS,
                             TECH_HISTORY, "途中のコミットの数がlimits.historyCommitCountを超えれば、draftの版があっても完全には読めない違反にする"),
    "SINGLE-188-07": history({CONFIG_PATH: limits_config(historyCommitCount=4), TECH_PATH: tech()}, TECH_CHANGED, FOUR_COMMITS,
                             [], "途中のコミットの数がlimits.historyCommitCountちょうどなら、通常どおり判定して通過する"),
    "SINGLE-188-08": history({CONFIG_PATH: UNPROTECTED_CONFIG, REQ_PATH: req()}, {"approved.md": req(REQ_TITLE_CHANGED)},
                             [*change(REQ_PATH, "changes/approved.md", "change"), shallow("HEAD")], [],
                             "保護を無効にした設定では、履歴を読まないのでシャロークローンでも違反にしない"),
    "SINGLE-188-09": history(BASE_REQ, CHANGED, [*REAPPROVE, shallow("HEAD~1")], REQ_HISTORY,
                             "明示対象のcheckでも途中のコミットを読み、境界がHEADから到達できれば完全には読めない違反にする",
                             argv=["check", "REQ-001", "--base", "base", "--format", "json"], scope="selected"),
    # `--base`の省略そのものを確かめる例外（適合fixture仕様 §3。監査の`BASE_OMISSION_EXCEPTIONS`）。最初のコミットは`setup.baseCommit`で作る。
    "SINGLE-188-10": dict(repo=BASE_REQ, changes={"current.md": req(REQ_TITLE_CHANGED)},
                          operations=[shallow("HEAD"), update(REQ_PATH, "changes/current.md")],
                          argv=["check", "REQ-001", "--format", "json"], scope="selected", documents=1, statements=1, dirty=True,
                          violations=REQ_VIOLATION,
                          description="--baseなしでは基準版をHEADとし、深さ1のシャロークローンでも通常の文言にする"),
    "SINGLE-188-11": dict(CASES["SINGLE-186-01"], text=True, description="TECHの保護の違反をテキスト出力で表示する"),
    "SINGLE-188-12": dict(history(BASE_REQ, CHANGED, [*REAPPROVE, shallow("HEAD~1")], REQ_HISTORY,
                                  "途中のコミットを完全には読めない違反をテキスト出力で表示する"), text=True),
})
for _identifier in ("SINGLE-188-11", "SINGLE-188-12"):
    CASES[_identifier]["argv"] = [*CASES[_identifier]["argv"][:-1], "text"]
# 枝`base`を履歴の途中で作るケース。`history`が先頭に置いた枝`base`を除く。
for _identifier in ("SINGLE-188-02", "SINGLE-188-05"):
    CASES[_identifier]["operations"] = CASES[_identifier]["operations"][1:]

# 分かれた枝の先端を基準版にし、`HEAD`から到達できない境界を置く（F-2）。途中のコミットはdraftへ戻して再承認した2つである。
DIVERGED_BASE = [branch("side"), checkout("side"), *create("docs/note.md", "changes/note.md", "side 1")]
CASES.update({
    "SINGLE-188-13": history(BASE_REQ, {**CHANGED, "note.md": NOTE},
                             [*DIVERGED_BASE, branch("base"), checkout("fixture"), *REAPPROVE, shallow("base")],
                             REQ_HISTORY, "HEADから到達できない分かれた枝の先端の基準版が境界なら、完全には読めない違反にする"),
    "SINGLE-188-14": history(BASE_REQ, {**CHANGED, "note.md": NOTE, "note2.md": "# 作業のメモ\n\n追記した。\n".encode()},
                             [*DIVERGED_BASE, *change("docs/note.md", "changes/note2.md", "side 2"), branch("base"),
                              checkout("fixture"), *REAPPROVE, shallow("base~1")],
                             REQ_HISTORY, "HEADから到達できない基準版の枝の祖先が境界でも、基準版から到達できるので完全には読めない違反にする"),
})
for _identifier in ("SINGLE-188-13", "SINGLE-188-14"):
    CASES[_identifier]["operations"] = CASES[_identifier]["operations"][1:]

# --- 複合ワークスペース（MULTI-071） ---
ROOT_CONFIG = (CONFIG + b"workspace:\n  id: platform\nmultiWorkspace:\n  members:\n    - id: web\n      path: apps/web\n"
               b"    - id: api\n      path: services/api\n")
WEB, API = "apps/web", "services/api"
WEB_REQ, API_TECH = f"{WEB}/.spec/requirements/REQ-010.md", f"{API}/.spec/technical/TECH-020.md"
MULTI_REPO = {CONFIG_PATH: ROOT_CONFIG, f"{WEB}/{CONFIG_PATH}": CONFIG + b"workspace:\n  id: web\n",
              f"{API}/{CONFIG_PATH}": CONFIG + b"workspace:\n  id: api\n",
              WEB_REQ: req(identifier="REQ-010"), API_TECH: tech(identifier="TECH-020")}
MULTI_CHANGES = {"draft.md": req(REQ_TITLE_CHANGED, "draft", identifier="REQ-010"),
                 "approved.md": req(REQ_TITLE_CHANGED, identifier="REQ-010"),
                 "tech.md": tech(TECH_TITLE_CHANGED, identifier="TECH-020")}
WEB_REAPPROVE = [*change(WEB_REQ, "changes/draft.md", "draft web"), *change(WEB_REQ, "changes/approved.md", "approve web")]
CASES.update({
    "MULTI-071-01": history(MULTI_REPO, {key: MULTI_CHANGES[key] for key in ("draft.md", "approved.md")}, WEB_REAPPROVE, [],
                            "作業ワークスペースのメンバーでも、途中のコミットでdraftへ戻して再びapprovedにした変更は通過する",
                            cwd=WEB, workspace=("web", WEB), documents=1, statements=1),
    "MULTI-071-02": history(MULTI_REPO, MULTI_CHANGES, [*WEB_REAPPROVE, *change(API_TECH, "changes/tech.md", "change api")],
                            [violation(".spec/technical/TECH-020.md", "title", "TECH", workspace="api")],
                            "--all-workspacesでは、ワークスペースごとに途中のコミットを判定し、draftの版のないapiのTECHだけを違反にする",
                            argv=["check", "--all-workspaces", "--base", "base", "--format", "json"], scope="all-workspaces"),
})
# 各ワークスペースの完全検査の件数（--all-workspaces）。ルートの`platform`は仕様文書を持たない。
ALL_WORKSPACES = (("platform", ".", 0, 0), ("api", API, 1, 1), ("web", WEB, 1, 1))
# メンバーのルートを途中のコミットで移す（§8.1、ADR-078の決定4）。現在版のカタログでは`web`は`apps/site`にある。
SITE = "apps/site"
SITE_REQ = f"{SITE}/.spec/requirements/REQ-010.md"
MOVED_CONFIG = ROOT_CONFIG.replace(b"path: apps/web", b"path: apps/site")
MOVE = [{"op": "rename", "from": WEB, "to": SITE}, update(CONFIG_PATH, "changes/root.yaml")]
MOVED_WORKSPACES = (("platform", ".", 0, 0), ("api", API, 1, 1), ("web", SITE, 1, 1, WEB))
ALL = ["check", "--all-workspaces", "--base", "base", "--format", "json"]
CASES.update({
    "MULTI-071-03": history(MULTI_REPO, {**{key: MULTI_CHANGES[key] for key in ("draft.md", "approved.md")}, "root.yaml": MOVED_CONFIG},
                            [*change(WEB_REQ, "changes/draft.md", "draft web"), *MOVE, update(SITE_REQ, "changes/approved.md"),
                             {"op": "stage", "paths": [WEB, SITE, CONFIG_PATH]}, commit("move web and approve")],
                            [violation(".spec/requirements/REQ-010.md", "title", "REQ", workspace="web")],
                            "途中のコミットの間にメンバーのルートを移せば、移す前のコミットのdraftの版を対応付けず違反のままにする",
                            argv=ALL, scope="all-workspaces", workspaces=MOVED_WORKSPACES),
    "MULTI-071-04": history(MULTI_REPO, {**{key: MULTI_CHANGES[key] for key in ("draft.md", "approved.md")}, "root.yaml": MOVED_CONFIG},
                            [*change(WEB_REQ, "changes/draft.md", "draft web"), *MOVE,
                             {"op": "stage", "paths": [WEB, SITE, CONFIG_PATH]}, commit("move web"),
                             *change(SITE_REQ, "changes/approved.md", "approve web")],
                            [], "メンバーのルートを移したコミットのdraftの版は、移す前の親に同じIDの文書がないので状態を変えた版として認める",
                            argv=ALL, scope="all-workspaces", workspaces=MOVED_WORKSPACES),
    "MULTI-071-05": history({**MULTI_REPO, CONFIG_PATH: ROOT_CONFIG + b"limits:\n  historyCommitCount: 1\n"},
                            {key: MULTI_CHANGES[key] for key in ("draft.md", "approved.md")}, WEB_REAPPROVE,
                            [violation(".spec/requirements/REQ-010.md", "title", "REQ", history=True, workspace="web")],
                            "複合ワークスペースではルートの設定のlimits.historyCommitCountを使い、超えれば完全には読めない違反にする",
                            argv=ALL, scope="all-workspaces"),
})


# ADR-082の決定5: `--all-workspaces`では、各ワークスペース自身の基準版と現在版の設定で判定する。`web`だけが両方でfalseにする。
UNPROTECTED_WEB = {**MULTI_REPO, f"{WEB}/{CONFIG_PATH}": CONFIG + b"workspace:\n  id: web\nsafety:\n  protectApprovedRequirements: false\n"}
CASES["MULTI-071-06"] = dict(repo=UNPROTECTED_WEB, changes={"approved.md": MULTI_CHANGES["approved.md"]},
                             operations=[update(WEB_REQ, "changes/approved.md")], argv=["check", "--all-workspaces", "--base", "HEAD", "--format", "json"],
                             scope="all-workspaces", documents=1, statements=1, dirty=True, violations=[],
                             description="--all-workspacesでは、ルートで有効でも、メンバー自身の基準版と現在版の設定でfalseなら、そのメンバーの保護を無効にする")


def fixture_dir(root, identifier):
    return root / ("multi" if identifier.startswith("MULTI-") else "single") / identifier


def case(identifier):
    return CASES[identifier]


# --- 期待値 ---------------------------------------------------------------------------------

def diagnostic(item):
    template = HISTORY_SUMMARY if item["history"] else SUMMARY
    return {"code": CODE, "severity": "error", "resultStatus": "failed", "summary": template.format(kind=item["kind"]),
            "source": {"kind": "file", "workspaceId": item["workspace"], "path": item["path"], "key": item["key"]}}


def reviewed_manifest(identifier):
    case_ = case(identifier)
    status = "failed" if case_["violations"] else "passed"
    plan = {"git": True, "operations": copy.deepcopy(case_["operations"])}
    if case_.get("base_commit", True):
        plan = {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": plan["operations"]}
    expect = {"status": status, "exitCode": 1 if status == "failed" else 0}
    if case_.get("text"):
        expect.update(stdout="text", textFile="expected/check.txt")
    else:
        expect.update(stdout="json", resultFile="expected/check.json")
    expect["reportFileCount"] = 0
    return {"fixtureId": identifier, "description": case_["description"], "setup": plan,
            "invocation": {"runner": "bitz", "cwd": case_.get("cwd", "."), "argv": list(case_["argv"]), "env": {}},
            "expect": expect}


def reviewed_result(identifier):
    case_ = case(identifier)
    status = "failed" if case_["violations"] else "passed"
    revision = {"base": COMMIT, "commit": COMMIT, "dirty": case_["dirty"]}
    diagnostics = [diagnostic(item) for item in sorted(case_["violations"], key=lambda item: item["path"])]
    if case_.get("scope") == "all-workspaces":
        workspaces = []
        for workspace_id, path, documents, statements, *_ in case_.get("workspaces", ALL_WORKSPACES):
            own = [item for item in diagnostics if item["source"]["workspaceId"] == workspace_id]
            workspaces.append({"id": workspace_id, "path": path, "status": "failed" if own else "passed",
                               "checkedDocumentCount": documents, "checkedStatementCount": statements,
                               "durationMs": 0, "diagnostics": own})
        return {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": status,
                "multiWorkspace": {"id": "platform", "path": "."}, "workspaces": workspaces, "revision": revision,
                "durationMs": 0, "diagnostics": []}
    workspace_id, path = case_.get("workspace", ("root", "."))
    return {"schemaVersion": "1.0", "operation": "check", "status": status, "scope": case_.get("scope", "full"),
            "workspace": {"id": workspace_id, "path": path}, "revision": revision,
            "checkedDocumentCount": case_["documents"], "checkedStatementCount": case_["statements"],
            "durationMs": 0, "diagnostics": diagnostics}


def reviewed_text(identifier):
    """結果・診断・終了コード §7のテキスト出力。`key`は表示しない。"""
    result = reviewed_result(identifier)
    lines = [f"check {result['status']} scope={result['scope']} targets={result['checkedDocumentCount']} "
             f"diagnostics={len(result['diagnostics'])} (0ms)\n"]
    for item in result["diagnostics"]:
        source = item["source"]
        lines.append(f"{source['workspaceId']}:{source['path']}::: {item['severity']}: {item['code']}: {item['summary']}\n")
    return "".join(lines).encode()


def expected_name(identifier):
    return "expected/check.txt" if case(identifier).get("text") else "expected/check.json"


def reviewed_inputs(identifier):
    case_ = case(identifier)
    return dict(case_["repo"]), dict(case_["changes"])


# --- 参照計算 -------------------------------------------------------------------------------

FRONTMATTER_LINE = re.compile(r"([a-z][a-z-]*): ([^\[\]{}&*!|>'\"%@`#].*)")
RELATION_LINE = re.compile(r"  ([a-z]+): \[([A-Z0-9:, -]*)\]")
STATEMENT_LINE = re.compile(r"- \[((?:REQ|TECH)-\d{3}:[A-Z]+-\d{2})\] (.+)")


def frontmatter_size(text):
    """区切りの行の間の各行を、改行を含めて数えたUTF-8のバイト数（文書・フロントマター・状態仕様 §11。このfixtureの入力はLFだけ）。"""
    end = text.index("\n---\n", 3)
    return len(text[4:end + 1].encode("utf-8"))


def read_document(content, spec_bytes, frontmatter_bytes=LIMIT_FRONTMATTER_BYTES, array_items=LIMIT_ARRAY_ITEMS):
    """このfixtureの入力に限った字句の読み方で、ID、状態、意味の項目を返す。IDを読めない版は`None`。"""
    if len(content) > spec_bytes:
        return None
    try:
        text = content.decode("utf-8")
        if not text.startswith("---\n"):
            return None
        end = text.index("\n---\n", 3)
    except (UnicodeDecodeError, ValueError):
        return None
    if frontmatter_size(text) > frontmatter_bytes:
        return None
    fields, relations_ = {}, {}
    in_relations = False
    for line in text[4:end].split("\n"):
        if line == "relations:":
            in_relations = True
            continue
        match = RELATION_LINE.fullmatch(line)
        if in_relations and match:
            relations_[match.group(1)] = tuple(part.strip() for part in match.group(2).split(",") if part.strip())
            # 関係の配列の項目数の上限（`documentArrayItemCount`。途中の版にも当てる。§4.1、ADR-082）。
            if len(relations_[match.group(1)]) > array_items:
                return None
            continue
        match = FRONTMATTER_LINE.fullmatch(line)
        if match is None:
            return None
        in_relations = False
        fields[match.group(1)] = match.group(2)
    if not {"id", "title", "status"} <= fields.keys():
        return None
    statements = {}
    for line in text[end + 5:].split("\n"):
        match = STATEMENT_LINE.fullmatch(line)
        if match:
            statements[match.group(1)] = match.group(2)
    return {"id": fields["id"], "title": fields["title"], "status": fields["status"],
            "relations": {name: relations_.get(name, ()) for name in STRONG}, "statements": statements}


def _git_text(repository, *args):
    return git(repository, *args).decode()


def _succeeds(repository, *args):
    try:
        git(repository, *args)
    except subprocess.CalledProcessError:
        return False
    return True


def spec_paths(paths, prefix):
    roots = (f"{prefix}.spec/requirements/", f"{prefix}.spec/technical/")
    return sorted(path for path in paths if path.startswith(roots) and path.endswith(".md"))


def documents_at(repository, revision, prefix, limits=ABSOLUTE_LIMITS):
    """IDから(パス, バイト列, 読んだ値)の一覧。`revision`が`None`なら作業ツリー。"""
    if revision is None:
        paths = [path.relative_to(repository).as_posix() for path in repository.rglob("*.md")
                 if path.is_file() and ".git" not in path.relative_to(repository).parts]
        contents = {path: (repository / path).read_bytes() for path in spec_paths(paths, prefix)}
    else:
        listing = _git_text(repository, "ls-tree", "-r", "--name-only", "-z", revision).split("\0")[:-1]
        contents = {path: git(repository, "cat-file", "blob", f"{revision}:{path}") for path in spec_paths(listing, prefix)}
    result = {}
    for path, content in contents.items():
        document = read_document(content, *limits)
        if document is not None:
            result.setdefault(document["id"], []).append((path[len(prefix):], content, document))
        else:
            result.setdefault(None, []).append(path[len(prefix):])
    return result


def changed_items(base, current):
    """§8の比較の項目のうち変わったものを、§8.2の順に返す。"""
    items = []
    if base["title"] != current["title"]:
        items.append("title")
    items += [f"relations.{name}" for name in STRONG if base["relations"][name] != current["relations"][name]]
    if base["statements"] != current["statements"]:
        items.append("statements")
    return items


PROTECTION_OFF = re.compile(r"^safety:\n  protectApprovedRequirements: false$", re.M)
PROTECTION_OFF_LENIENT = re.compile(r"^safety:\n  protectApprovedRequirements: \"?false\"?$", re.M)


def explicitly_unprotected(text):
    """設定が`safety.protectApprovedRequirements: false`を明示する（このfixtureの入力に限った字句の読み方）。
    値が真偽値でない（`"false"`のような文字列）設定は、スキーマに適合しないので明示とみなさない（§8、ADR-082）。"""
    pattern = PROTECTION_OFF_LENIENT if READING["protection"] == "lenient" else PROTECTION_OFF
    return text is not None and pattern.search(text) is not None


def config_values(repository, prefix, root_prefix="", base=None, base_prefix=None):
    """保護の有無（基準版と現在版の作業ワークスペースの設定のどちらかで有効なら有効。§8、ADR-082の決定4）と、
    ルートワークスペースの設定の`limits`（複合ワークスペースではルートの値。§4.1）。"""
    if READING["protection_workspace"] == "root":
        prefix = base_prefix = root_prefix
    current = (repository / prefix / CONFIG_PATH).read_text()
    base_text = None
    if base is not None:
        path = f"{prefix if base_prefix is None else base_prefix}{CONFIG_PATH}"
        try:
            base_text = git(repository, "cat-file", "blob", f"{base}:{path}").decode("utf-8")
        except (subprocess.CalledProcessError, UnicodeDecodeError):
            base_text = None
    protect = {"current": not explicitly_unprotected(current),
               "base": base is None or not explicitly_unprotected(base_text)}.get(
        READING["protection"], not (explicitly_unprotected(current) and explicitly_unprotected(base_text)))
    text = (repository / root_prefix / CONFIG_PATH).read_text()

    def limit(key, default):
        match = re.search(rf"^  {key}: (\d+)$", text, re.M)
        return int(match.group(1)) if match else default
    return protect, (limit("specBytes", LIMIT_SPEC_BYTES), limit("frontmatterBytes", LIMIT_FRONTMATTER_BYTES),
                     limit("documentArrayItemCount", LIMIT_ARRAY_ITEMS)), limit("historyCommitCount", LIMIT_HISTORY)


def resolve(repository, revision):
    return _git_text(repository, "rev-parse", "--verify", f"{revision}^{{commit}}").strip()


def history_state(repository, base):
    """途中のコミットと、その集合が空であるとGitの履歴から確定するか（基準版が`HEAD`と同じか、`HEAD`が基準版の祖先）。"""
    head = resolve(repository, "HEAD")
    if head == base or _succeeds(repository, "merge-base", "--is-ancestor", head, base):
        return [], True
    walk = ["--first-parent"] if READING["walk"] == "first-parent" else []
    commits = _git_text(repository, "rev-list", *walk, head, "--not", base).split()
    return commits, False


def parents_of(repository, commit):
    return _git_text(repository, "rev-list", "--parents", "-n", "1", commit).split()[1:]


def shallow_reachable(repository, base, commits=()):
    """シャロークローンの境界のコミットのいずれかが、`HEAD`または基準版から到達できる（§8.1）。"""
    path = repository / ".git/shallow"
    if not path.exists():
        return False
    boundaries = path.read_text().split()
    if READING["boundary"] == "adjacent":
        nearby = set(commits) | {parent for commit in commits for parent in parents_of(repository, commit)}
        return any(commit in nearby for commit in boundaries)
    tips = ["HEAD"] if READING["boundary"] == "head" else ["HEAD", base]
    reachable = set(_git_text(repository, "rev-list", *tips).split())
    return any(commit in reachable for commit in boundaries)


DRAFT_STATES = {"draft", "outdated"}


def has_intermediate_state(repository, commits, identifier, prefix, limits):
    """途中のコミットのうち少なくとも1つが、文書の状態を`draft`または`outdated`へ変えた（§8.1、ADR-081）。"""
    cache = {}

    if READING["array"] == "ignore":
        limits = (*limits[:2], LIMIT_ARRAY_ITEMS)

    def at(revision):
        if revision not in cache:
            cache[revision] = documents_at(repository, revision, prefix, limits)
        return cache[revision]

    for commit in commits:
        versions = at(commit).get(identifier, [])
        if len(versions) != 1 or versions[0][2]["status"] not in DRAFT_STATES:
            continue
        parents = parents_of(repository, commit)
        if not parents:
            return True
        if READING["parents"] == "first":
            parents = parents[:1]
        for parent in parents:
            previous = at(parent).get(identifier, [])
            if len(previous) >= 2:
                if READING["duplicates"] == "absent":
                    return True
                continue
            if not previous:
                if READING["unreadable"] == "unchanged" and versions[0][0] in at(parent).get(None, []):
                    continue
                return True
            if READING["recognize"] == "content":
                if previous[0][1] != versions[0][1]:
                    return True
            elif READING["recognize"] == "differs":
                if previous[0][2]["status"] != versions[0][2]["status"]:
                    return True
            elif previous[0][2]["status"] not in DRAFT_STATES:
                return True
    return False


def reference_diagnostics(repository, base_revision, prefix, workspace, base_prefix=None, root_prefix=""):
    """作業ワークスペース（`prefix`は現在版のリポジトリ相対のルートと`/`）の保護の違反を、§8、§8.1、§8.2から求める。

    `base_prefix`は基準版のカタログでのそのワークスペースのルート（メンバーを移した場合）。途中のコミットは現在版のルートの配下だけを読む（§8.1）。
    """
    base = resolve(repository, base_revision)
    protect, limits, history_limit = config_values(repository, prefix, root_prefix, base, base_prefix)
    if not protect:
        return []
    before = documents_at(repository, base, prefix if base_prefix is None else base_prefix, limits)
    after = documents_at(repository, None, prefix, limits)
    candidates = []
    for identifier, versions in sorted((key, value) for key, value in after.items() if key is not None):
        if len(versions) != 1 or len(before.get(identifier, [])) != 1:
            continue
        old, new = before[identifier][0][2], versions[0][2]
        items = changed_items(old, new)
        if old["status"] == "approved" and new["status"] == "approved" and items:
            candidates.append((identifier, versions[0][0], items[0]))
    if not candidates:
        return []
    commits, empty = history_state(repository, base)
    incomplete = not empty and (shallow_reachable(repository, base, commits) or len(commits) > history_limit)
    result = []
    for identifier, path, key in candidates:
        if not empty and not incomplete and has_intermediate_state(repository, commits, identifier, prefix, limits):
            continue
        result.append(violation(path, key, identifier.split("-")[0], history=incomplete, workspace=workspace))
    return sorted(result, key=lambda item: item["path"])


def reference_counts(repository, prefix):
    documents = {key: value for key, value in documents_at(repository, None, prefix).items() if key is not None}
    return sum(len(v) for v in documents.values()), sum(len(d[2]["statements"]) for v in documents.values() for d in v)


def base_revision(identifier):
    argv = case(identifier)["argv"]
    return argv[argv.index("--base") + 1] if "--base" in argv else "HEAD"


def inspector(identifier):
    case_ = case(identifier)

    def inspect(repository):
        base = base_revision(identifier)
        if case_.get("scope") == "all-workspaces":
            actual, members = [], []
            for workspace_id, path, documents, statements, *rest in case_.get("workspaces", ALL_WORKSPACES):
                prefix = "" if path == "." else path + "/"
                base_prefix = (rest[0] + "/") if rest else None
                # ルートワークスペースは仕様文書を持たない（下で確かめる）。`limits`はルートの設定の値を使う（§4.1）。
                actual += reference_diagnostics(repository, base, prefix, workspace_id, base_prefix) if prefix else []
                if prefix:
                    members.append(prefix)
                    if reference_counts(repository, prefix) != (documents, statements):
                        raise ValueError("ワークスペースの件数が参照計算と異なります")
            if reference_counts(repository, "") != (0, 0) or any(
                    not path.startswith(tuple(members)) for path in spec_paths(
                        [p.relative_to(repository).as_posix() for p in repository.rglob("*.md")], "")):
                raise ValueError("ルートワークスペースが仕様文書を持っています")
        else:
            workspace_id, path = case_.get("workspace", ("root", "."))
            prefix = "" if path == "." else path + "/"
            actual = reference_diagnostics(repository, base, prefix, workspace_id)
            if case_.get("scope", "full") == "full" and reference_counts(repository, prefix) != (case_["documents"], case_["statements"]):
                raise ValueError("完全検査の件数が参照計算と異なります")
        expected = sorted(case_["violations"], key=lambda item: item["path"])
        if actual != expected:
            raise ValueError(f"保護の違反が参照計算と異なります: {actual}")
        dirty = _git_text(repository, "status", "--porcelain=v1", "--untracked-files=all") != ""
        if dirty != case_["dirty"]:
            raise ValueError("作業ツリーの状態（dirty）がレビュー済みの期待値と異なります")
        if "merged" in case_ and (repository / REQ_PATH).read_bytes() != case_["merged"]:
            raise ValueError("マージの結果の文書がレビュー済みの内容と異なります")
        current_path = case_.get("current_path")
        if current_path is not None and not (repository / current_path).is_file():
            raise ValueError("現在版の文書のパスがレビュー済みのパスと異なります")
        inspect_history(repository, identifier)
    return inspect


def inspect_history(repository, identifier):
    """ケースが固定する履歴の形（途中のコミットの数、境界、親）を、参照計算とは別に確かめる。"""
    base = resolve(repository, base_revision(identifier))
    commits, empty = history_state(repository, base)
    shallow_file = repository / ".git/shallow"
    boundaries = shallow_file.read_text().split() if shallow_file.exists() else []
    expected = {
        "SINGLE-187-05": 3, "SINGLE-187-06": 3, "SINGLE-187-07": 3, "SINGLE-187-09": 3,
        "SINGLE-188-06": 4, "SINGLE-188-07": 4,
        "SINGLE-187-20": 3, "SINGLE-187-21": 3, "SINGLE-187-22": 3, "SINGLE-187-23": 3,
    }
    if identifier in expected and len(commits) != expected[identifier]:
        raise ValueError("途中のコミットの数がレビュー済みの履歴と異なります")
    if identifier.startswith("SINGLE-186-") and (commits or not empty):
        raise ValueError("端点の比較のケースに途中のコミットがあります")
    if identifier in {"SINGLE-188-04", "SINGLE-188-05", "SINGLE-188-10"} and not (empty and boundaries):
        raise ValueError("途中のコミットがないシャロークローンのケースではありません")
    if identifier == "SINGLE-188-03" and (not boundaries or shallow_reachable(repository, base)):
        raise ValueError("境界のコミットがHEADまたは基準版から到達できます")
    if identifier == "SINGLE-188-02":
        nearby = set(commits) | {parent for commit in commits for parent in parents_of(repository, commit)}
        if boundaries != [resolve(repository, "base~1")] or boundaries[0] in nearby:
            raise ValueError("境界のコミットが、途中のコミットとその親でない基準版の祖先ではありません")
    if identifier in {"SINGLE-188-13", "SINGLE-188-14"}:
        head_reachable = set(_git_text(repository, "rev-list", "HEAD").split())
        expected_boundary = base if identifier == "SINGLE-188-13" else resolve(repository, "base~1")
        if (_succeeds(repository, "merge-base", "--is-ancestor", base, "HEAD") or boundaries != [expected_boundary]
                or expected_boundary in head_reachable):
            raise ValueError("境界のコミットが、HEADから到達できない分かれた枝の基準版の側にありません")
    if identifier == "SINGLE-187-16":
        statuses = [read_document(git(repository, "cat-file", "blob", f"{commit}:{REQ_PATH}"), LIMIT_SPEC_BYTES)["status"]
                    for commit in commits]
        if statuses != ["approved", "draft", "draft"]:
            raise ValueError("draftへ戻した後に同じ枝で編集した履歴ではありません")
    if identifier == "SINGLE-187-17":
        copy_in = [COPY_PATH in _git_text(repository, "ls-tree", "--name-only", commit, ".spec/requirements/").split()
                   for commit in commits]
        same = (git(repository, "cat-file", "blob", f"{commits[1]}:{REQ_PATH}")
                == git(repository, "cat-file", "blob", f"{commits[2]}:{REQ_PATH}"))
        if copy_in != [False, False, True] or not same:
            raise ValueError("複製だけを削除したコミットの形ではありません")
    if identifier in {"SINGLE-187-18", "SINGLE-187-19"}:
        sizes = [frontmatter_size(git(repository, "cat-file", "blob", f"{revision}:{REQ_PATH}").decode())
                 for revision in (base, commits[1], "HEAD")]
        limit = FRONTMATTER_LIMIT - 1 if identifier == "SINGLE-187-18" else FRONTMATTER_LIMIT
        if sizes[1] != FRONTMATTER_LIMIT or max(sizes[0], sizes[2]) > limit:
            raise ValueError("途中の版だけがlimits.frontmatterBytesの境界にある形ではありません")
    if identifier in {"MULTI-071-03", "MULTI-071-04"}:
        listing = _git_text(repository, "ls-tree", "-r", "--name-only", "HEAD").split()
        if any(path.startswith(WEB + "/") for path in listing) or SITE_REQ not in listing or WEB_REQ not in _git_text(
                repository, "ls-tree", "-r", "--name-only", base).split():
            raise ValueError("メンバーのルートを途中のコミットで移した形ではありません")
    if identifier in {"SINGLE-188-01", "SINGLE-188-09", "SINGLE-188-12"} and boundaries != [commits[1]]:
        raise ValueError("境界のコミットがdraftの途中のコミットではありません")
    if identifier == "SINGLE-187-04" and (git(repository, "show", f":{REQ_PATH}") != req(REQ_TITLE_CHANGED, "draft")
                                          or (repository / REQ_PATH).read_bytes() != req(REQ_TITLE_CHANGED)
                                          or git(repository, "show", f"HEAD:{REQ_PATH}") != req(REQ_TITLE_CHANGED)):
        raise ValueError("draftの版がインデックスにだけある形ではありません")
    if identifier == "SINGLE-187-13":
        listing = _git_text(repository, "ls-tree", "--name-only", commits[1], ".spec/requirements/").split()
        if listing != [COPY_PATH, REQ_PATH] or COPY_PATH in _git_text(repository, "ls-tree", "--name-only", "HEAD", ".spec/requirements/").split():
            raise ValueError("途中のコミットに同じIDの文書が2つある形ではありません")
    if identifier in {"SINGLE-187-11", "SINGLE-187-12"}:
        draft = git(repository, "cat-file", "blob", f"{commits[1]}:{REQ_PATH}")
        limit = SIZE_LIMIT - 1 if identifier == "SINGLE-187-11" else SIZE_LIMIT
        sizes = [len(git(repository, "cat-file", "blob", f"{revision}:{REQ_PATH}")) for revision in (base, "HEAD")]
        if len(draft) != SIZE_LIMIT or max(sizes) > limit:
            raise ValueError("途中の版だけがlimits.specBytesの境界にある形ではありません")
    if identifier in {"SINGLE-187-20", "SINGLE-187-21", "SINGLE-187-22"}:
        merge_commit = commits[1] if identifier == "SINGLE-187-21" else commits[0]
        parents = parents_of(repository, merge_commit)
        status = lambda revision: (read_document(git(repository, "cat-file", "blob", f"{revision}:{REQ_PATH}"), LIMIT_SPEC_BYTES)
                                   or {"status": None})["status"]
        shape = {"SINGLE-187-20": (["approved", "approved", "approved"], parents[:1] == [base]),
                 "SINGLE-187-21": (["draft", "draft", "approved"], parents[1:] == [base]),
                 "SINGLE-187-22": (["approved", "approved", "draft"], True)}[identifier]
        if len(parents) != 2 or [status(revision) for revision in (merge_commit, *parents)] != shape[0] or not shape[1]:
            raise ValueError("マージコミットと親の状態がレビュー済みの形と異なります")
        if identifier == "SINGLE-187-22" and status(f"{parents[1]}^") != "outdated":
            raise ValueError("枝oldのコミットの親がoutdatedではありません")
    if identifier == "SINGLE-187-23" and (git(repository, "cat-file", "blob", f"{commits[2]}:{REQ_PATH}") != BROKEN_DRAFT
                                          or read_document(BROKEN_DRAFT, LIMIT_SPEC_BYTES) is not None):
        raise ValueError("IDを読めない版のコミットの形ではありません")
    if identifier == "SINGLE-187-07":
        merge_commit = commits[1]
        parents = _git_text(repository, "rev-list", "--parents", "-n", "1", merge_commit).split()[1:]
        versions = [git(repository, "cat-file", "blob", f"{revision}:{REQ_PATH}") for revision in (merge_commit, *parents)]
        if len(parents) != 2 or versions[0] != versions[2] or versions[0] == versions[1]:
            raise ValueError("マージコミットの版が、2つ目の親と同じで1つ目の親と異なる形ではありません")


# --- 生成と監査 ---------------------------------------------------------------------------

def read_tree(directory):
    tree = {}
    if not directory.is_dir():
        return tree
    for path in sorted(directory.rglob("*")):
        if path.is_symlink() or not path.is_file():
            if path.is_symlink():
                raise ValueError("入力にシンボリックリンクがあります")
            continue
        if path.stat().st_mode & 0o111:
            raise ValueError("入力に実行ビットがあります")
        tree[path.relative_to(directory).as_posix()] = path.read_bytes()
    return tree


def write_tree(directory, tree):
    for relative, value in sorted(tree.items()):
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        path.chmod(0o644)


def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def prepared_states(fixture, manifest, inspect=None):
    states = []
    with tempfile.TemporaryDirectory(prefix="bitz-approved-history-") as temporary:
        heads = []
        for run in range(2):
            sandbox = Path(temporary) / str(run)
            sandbox.mkdir()
            repository = setup(fixture, manifest, sandbox / "repo")
            if inspect is not None:
                inspect(repository)
            heads.append(_git_text(repository, "rev-list", "--all", "--parents"))
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            states.append(observe(repository, external))
    if states[0] != states[1] or heads[0] != heads[1]:
        raise ValueError("隔離した2回の準備手順が一致しません")
    return states[0]


def generate(root=HERE, identifiers=None):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = fixture_dir(root, identifier)
        fixture.mkdir(parents=True, exist_ok=False)
        tree, changes = reviewed_inputs(identifier)
        write_tree(fixture / "repo", tree)
        write_tree(fixture / "changes", changes)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir()
        if case(identifier).get("text"):
            (fixture / expected_name(identifier)).write_bytes(reviewed_text(identifier))
        else:
            (fixture / expected_name(identifier)).write_text(_dump(reviewed_result(identifier)))
        state = prepared_states(fixture, manifest, inspector(identifier))
        (fixture / "side-effects.json").write_text(
            _dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads(schema_path(root, "frontmatter").read_text())
    frontmatter = {kind: Draft202012Validator({"$ref": f"#/$defs/{kind}Frontmatter", "$defs": schema["$defs"]})
                   for kind in ("req", "tech")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = fixture_dir(root, identifier)
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("マニフェストがレビュー済みの起動と異なります")
            validators["result"].validate(reviewed_result(identifier))
            if case(identifier).get("text"):
                if (fixture / expected_name(identifier)).read_bytes() != reviewed_text(identifier):
                    raise ValueError("期待するテキストがレビュー済みの期待値と異なります")
            else:
                result = json.loads((fixture / expected_name(identifier)).read_text())
                validators["result"].validate(result)
                if result != reviewed_result(identifier):
                    raise ValueError("期待結果がレビュー済みの期待値と異なります")
            if {path.name for path in (fixture / "expected").iterdir()} != {Path(expected_name(identifier)).name}:
                raise ValueError("期待値のファイルがレビュー済みの1件と異なります")
            tree, changes = reviewed_inputs(identifier)
            if read_tree(fixture / "repo") != tree:
                raise ValueError("`repo`の入力がレビュー済みの入力と異なります")
            if read_tree(fixture / "changes") != changes:
                raise ValueError("`changes`の入力がレビュー済みの入力と異なります")
            if {path.name for path in fixture.iterdir()} - {"repo", "changes", "expected", "manifest.json", "side-effects.json"}:
                raise ValueError("fixtureにレビューしていないファイルがあります")
            for content in [*tree.values(), *changes.values()]:
                document = read_document(content, LIMIT_SPEC_BYTES) if content.startswith(b"---\n") else None
                if document is None:
                    continue
                kind = document["id"].split("-")[0].lower()
                value = {"id": document["id"], "title": document["title"], "status": document["status"]}
                declared = {name: list(targets) for name, targets in document["relations"].items() if targets}
                if declared:
                    value["relations"] = declared
                frontmatter[kind].validate(value)
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            state = prepared_states(fixture, manifest, inspector(identifier))
            if compare_state(effects["before"], state):
                raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError, StopIteration, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).splitlines()[0] if str(error) else type(error).__name__}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
