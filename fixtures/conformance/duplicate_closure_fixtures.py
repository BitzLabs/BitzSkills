"""閉包を作るときに辿る文書IDの重複と、IDを読めない現在版のファイルの扱いを固定する（Coreの公開操作は実行しない）。

実装の確認事項C96・C105と、ADR-051の追加に対応する。ユーザーの決定により、規範は次のとおりに明記された。

- C96（関係・トレースモデル §5.1）: 文書IDの重複（`SPEC-ID-DUPLICATE-001`、`failed`）は、`context`、`verify`、`check`のどれでも、閉包を作るときに辿るID
  （起点、`requires`、`refines`、`addresses`、置換の参照先、逆参照で閉包に入る文書のID。`related`の参照先は含めない）が重複していれば、その結果
  （`verify`は当該の検証対象）へ返す。起点のIDが重複している場合は`CTX-ROOT-MISSING-001`に併記する。閉包と無関係な重複は、`check`の完全検査の対象
  （`check` §3）にだけ返す。診断の文言と発生元は`check`の完全検査の診断と同じ（複合ワークスペースでは、重複した文書を所有するワークスペース）。
- C105（`check` §5、文書・フロントマター・状態仕様 §9）: 基準版の文書と同じパスに、現在版でIDを読めない（フロントマターの不正などで索引に入らない）ファイルが
  存在する場合は、削除（`SPEC-STATE-TRANSITION-001`）とせず、その文書の状態遷移、承認済み要求の保護、影響候補（`SPEC-IMPACT-OUTDATED-001`）の比較も行わない。
  そのファイル自身の診断は、引数なしの`check`でも、変更されたパスの診断として返す。IDでもパスでも現在版と対応しない場合（パスの変更とIDを読めない破損が同時に
  起きた場合を含む）は削除とする。

修正前のCoreは、閉包を作るときに重複したIDを黙って辿らず（重複した文書はどちらも索引に入らない）、`context`と`verify`は重複を返さずに通過した。IDを読めない現在版は
削除として返し、依存元へ影響候補を返し、そのファイル自身の診断を引数なしの`check`で返さなかった。
欠陥の18件（SINGLE-177-01・02・04・05・06・10・11・12・14〜17、MULTI-065-01〜05・08）は修正前のCoreが失敗し、対照の7件（SINGLE-177-03・07・08・09・13、MULTI-065-06・07）は通る。

| fixture | 操作 | 入力 | 期待 | 修正前のCore |
|---|---|---|---|---|
| `SINGLE-177-01` | `context REQ-001 --purpose verify` | `TECH-001`を`refines`する`TECH-002`が2ファイル（逆参照で閉包に入る） | `failed`／1。`SPEC-ID-DUPLICATE-001`の1件 | `passed` |
| `SINGLE-177-02` | `verify REQ-001` | 同上 | `failed`／1。検証対象の`diagnostics`に重複の1件。テストを起動しない | `passed` |
| `SINGLE-177-03` | `check REQ-001` | 同上 | `failed`／1。重複の1件（対照） | 通る |
| `SINGLE-177-04` | `context REQ-001 --purpose verify` | 起点`REQ-001`が2ファイル | `failed`／1。`CTX-ROOT-MISSING-001`と重複 | 重複を返さない |
| `SINGLE-177-05` | `verify REQ-001` | 同上 | `failed`／1。検証対象に`CTX-ROOT-MISSING-001`と重複 | 重複を返さない |
| `SINGLE-177-06` | `context REQ-001 --purpose verify` | `REQ-001`が`requires`する`TECH-003`が2ファイル | `failed`／1。`SPEC-RELATION-MISSING-001`と重複 | 重複を返さない |
| `SINGLE-177-07` | `verify REQ-001` | 閉包の`REQ-001`を`related`するだけの`TECH-009`が2ファイル | `passed`／0。重複を返さない（対照） | 通る |
| `SINGLE-177-08` | `verify REQ-001` | `SINGLE-168-03`の入力に、`related`の参照先の`ADR-099`を2ファイル | `SINGLE-168-03`と同じ`passed_with_warnings`／0（対照） | 通る |
| `SINGLE-177-09` | `context REQ-001 --purpose verify` | `SINGLE-042`の入力に、閉包と無関係な`TECH-008`が2ファイル | `SINGLE-042`と同じ結果（対照） | 通る |
| `SINGLE-177-10` | `check`（引数なし） | 作業ツリーで`REQ-001`のフロントマターが不正（基準版は`approved`）。`TECH-001`が`REQ-001`を`refines` | `failed`／1。`REQ-001`自身の`SPEC-FM-SCHEMA-001`と、直接の逆参照`TECH-001`の`SPEC-RELATION-MISSING-001`。削除と影響候補は返さない | 削除と影響候補を返し、自身の診断を返さない |
| `SINGLE-177-11` | `check --full` | 同上 | `failed`／1。`SPEC-FM-SCHEMA-001`と、索引にない`REQ-001`の`SPEC-RELATION-MISSING-001`（削除は返さない） | 削除も返す |
| `SINGLE-177-12` | `check`（引数なし） | `REQ-001.md`を削除し、別のパスにフロントマターが不正な`REQ-001-moved.md`を置く | `failed`／1。移動後の自身の診断と、旧パスの削除と影響候補 | 自身の診断を返さない |
| `SINGLE-177-13` | `check`（引数なし） | `REQ-001`を`approved`から`outdated`へ（IDを読める変更） | `passed_with_warnings`／0。依存元の影響候補（対照） | 通る |
| `SINGLE-177-14` | `check`（引数なし） | 基準版にない新規の`TECH-009.md`でフロントマターが不正 | `failed`／1。`SPEC-FM-SCHEMA-001`の1件。`targetDocumentCount`は0 | 診断を返さず`passed` |
| `SINGLE-177-15` | `check`（引数なし） | `REQ-001`を`REQ-001-moved.md`へ移して意味（`title`）を変え、元のパスに壊れたファイルを置く | `failed`／1。移動後の`SPEC-SAFETY-APPROVED-001`、元のパスの`SPEC-FM-SCHEMA-001`、`TECH-001`の影響候補 | 元のパスの診断を返さない |
| `SINGLE-177-16` | `context REQ-002 --purpose verify` | `REQ-002`が`supersedes`する旧文書`REQ-001`が2ファイル | `failed`／1。重複と`SPEC-RELATION-MISSING-001` | 後者だけ |
| `SINGLE-177-17` | `verify REQ-002` | `SINGLE-177-16`と同じ入力 | `failed`／1。検証対象に重複と`SPEC-RELATION-MISSING-001` | 後者だけ |
| `MULTI-065-01` | `context REQ-001 --purpose verify` | `platform::REQ-001`を`refines`する`web::TECH-005`が2ファイル | `failed`／1。`web`が所有する重複の1件 | `passed` |
| `MULTI-065-02` | `verify REQ-001` | 同上 | `failed`／1。`platform::REQ-001`に重複の1件 | `passed` |
| `MULTI-065-03` | `check REQ-001` | 同上 | `failed`／1。`web`が所有する重複の1件 | `passed` |
| `MULTI-065-04` | `verify --all-workspaces` | 同上 | `failed`／1。`platform`の検証対象に重複 | `passed` |
| `MULTI-065-05` | `context web::TECH-010 --purpose verify` | `platform::REQ-001`が2ファイル。`web::TECH-010`が`refines`する | `failed`／1。`platform`が所有する重複と`SPEC-RELATION-MISSING-001` | 重複を返さない |
| `MULTI-065-06` | `check REQ-001` | `REQ-001`が`related`で指す`web::TECH-007`が2ファイル | `passed_with_warnings`／0。重複を返さない（対照） | 通る |
| `MULTI-065-07` | `check REQ-001` | 閉包と無関係な`web::TECH-008`が2ファイル | `passed`／0（対照） | 通る |
| `MULTI-065-08` | `check --all-workspaces` | 作業ツリーで`web::TECH-001`のフロントマターが不正 | `failed`／1。`web`に`SPEC-FM-SCHEMA-001`だけ。削除を返さない | 削除も返す |

期待値は、規範と承認済みの文言から導く。参照計算（`reference_duplicates`、`reference_base_comparison`）は、入力の木構造だけから、閉包を作るときに辿る重複と、
基準版の文書の削除の有無を求め、期待する診断の集合と一致することを要求する（Coreの出力は根拠にしない）。ハッシュ値は、`SINGLE-042`と`SINGLE-168-03`の
レビュー済みの参照計算の値をそのまま使う（閉包が変わらない対照だけが通過のハッシュ値を持つ）。
"""
import copy
import json
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_reference, multi_reference
from . import related_advisory_fixtures as related
from .digest_fixtures import reviewed_result as digest_result
from .document_fixtures import DOCUMENT
from .harness import setup
from .initial_fixtures import CONFIGS, compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
EXIT = {"passed": 0, "passed_with_warnings": 0, "failed": 1}
DUPLICATE = "SPEC-ID-DUPLICATE-001"
ROOT_MISSING = "CTX-ROOT-MISSING-001"
RELATION_MISSING = "SPEC-RELATION-MISSING-001"
SCHEMA = "SPEC-FM-SCHEMA-001"
TRANSITION = "SPEC-STATE-TRANSITION-001"
IMPACT = "SPEC-IMPACT-OUTDATED-001"
ADVISORY = "SPEC-RELATION-ADVISORY-MISSING-001"
REQ_PATH = ".spec/requirements/REQ-001.md"
TECH_PATH = ".spec/technical/TECH-001.md"
EMPTY_BUCKET = {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []}

# id: dict(group, op, argv, description, 修正前のCoreが失敗する欠陥か)。入力と期待結果は下の関数が作る。
CASES = {
    "SINGLE-177-01": dict(op="context", argv=["context", "REQ-001", "--purpose", "verify"], defect=True,
                          description="contextは、逆参照のrefinesで閉包に入る文書のIDの重複をSPEC-ID-DUPLICATE-001で返す"),
    "SINGLE-177-02": dict(op="verify", argv=["verify", "REQ-001"], defect=True,
                          description="verifyは、逆参照のrefinesで閉包に入る文書のIDの重複を当該の検証対象へ返し、テストを起動しない"),
    "SINGLE-177-03": dict(op="check", argv=["check", "REQ-001", "--base", "HEAD"], defect=False,
                          description="対照: 明示対象のcheckは、逆参照のrefinesで閉包に入る文書のIDの重複を返す"),
    "SINGLE-177-04": dict(op="context", argv=["context", "REQ-001", "--purpose", "verify"], defect=True,
                          description="contextは、起点のIDが重複しているときCTX-ROOT-MISSING-001に重複を併記する"),
    "SINGLE-177-05": dict(op="verify", argv=["verify", "REQ-001"], defect=True,
                          description="verifyは、起点のIDが重複しているとき検証対象のCTX-ROOT-MISSING-001に重複を併記する"),
    "SINGLE-177-06": dict(op="context", argv=["context", "REQ-001", "--purpose", "verify"], defect=True,
                          description="contextは、requiresの参照先のIDの重複を強い関係の参照先の不在と並べて返す"),
    "SINGLE-177-07": dict(op="verify", argv=["verify", "REQ-001"], defect=False,
                          description="対照: 閉包の文書をrelatedで指すだけの重複した文書は、閉包に入らないので返さない"),
    "SINGLE-177-08": dict(op="verify", argv=["verify", "REQ-001"], defect=False,
                          description="対照: relatedの参照先の重複は閉包を作るときに辿らないので返さず、参照切れの警告だけを返す"),
    "SINGLE-177-09": dict(op="context", argv=["context", "REQ-001", "--purpose", "verify"], defect=False,
                          description="対照: 閉包と無関係な重複はcontextの結果へ返さない"),
    "SINGLE-177-10": dict(op="check", argv=["check", "--base", "HEAD"], defect=True,
                          description="基準版の文書と同じパスでIDを読めない現在版を、削除にも影響候補にもせず、自身の診断を返す"),
    "SINGLE-177-11": dict(op="check", argv=["check", "--full", "--base", "HEAD"], defect=True,
                          description="全体の検査でも、基準版の文書と同じパスでIDを読めない現在版を削除とみなさない"),
    "SINGLE-177-12": dict(op="check", argv=["check", "--base", "HEAD"], defect=True,
                          description="パスの変更とIDを読めない破損が同時に起きた場合は削除とし、破損したファイル自身の診断も返す"),
    "SINGLE-177-13": dict(op="check", argv=["check", "--base", "HEAD"], defect=False,
                          description="対照: IDを読める変更では、依存元の影響候補を返す"),
    "SINGLE-177-14": dict(op="check", argv=["check", "--base", "HEAD"], defect=True,
                          description="基準版にない新規のファイルでIDを読めなければ、引数なしのcheckはそのファイル自身の診断を返す"),
    "SINGLE-177-15": dict(op="check", argv=["check", "--base", "HEAD"], defect=True,
                          description="基準版のIDが現在版の別のパスにあれば、元のパスに壊れたファイルがあっても、IDで対応付けて承認済み要求の保護と影響候補を返す"),
    "SINGLE-177-16": dict(op="context", argv=["context", "REQ-002", "--purpose", "verify"], defect=True,
                          description="contextは、閉包の文書がsupersedesで置き換える旧文書のIDの重複を、強い関係の参照先の不在と並べて返す"),
    "SINGLE-177-17": dict(op="verify", argv=["verify", "REQ-002"], defect=True,
                          description="verifyは、閉包の文書がsupersedesで置き換える旧文書のIDの重複を、当該の検証対象へ返す"),
    "MULTI-065-01": dict(op="context", argv=["context", "REQ-001", "--purpose", "verify"], defect=True,
                         description="複合ワークスペースのcontextは、他のメンバーが所有する、逆参照で閉包に入る文書の重複を返す"),
    "MULTI-065-02": dict(op="verify", argv=["verify", "REQ-001"], defect=True,
                         description="複合ワークスペースのverifyは、他のメンバーが所有する重複を当該の検証対象へ返す"),
    "MULTI-065-03": dict(op="check", argv=["check", "REQ-001", "--base", "HEAD"], defect=True,
                         description="複合ワークスペースのcheckは、他のメンバーが所有する、閉包に入る文書の重複を返す"),
    "MULTI-065-04": dict(op="verify", argv=["verify", "--all-workspaces"], defect=True,
                         description="全体のverifyは、閉包を作るときに辿る他のメンバーの文書の重複を当該の検証対象へ返す"),
    "MULTI-065-05": dict(op="context", argv=["context", "web::TECH-010", "--purpose", "verify"], defect=True,
                         description="複合ワークスペースのcontextは、refinesの参照先である他のワークスペースの文書の重複を返す"),
    "MULTI-065-06": dict(op="check", argv=["check", "REQ-001", "--base", "HEAD"], defect=False,
                         description="対照: relatedの参照先の他のメンバーの重複は、閉包を作るときに辿らないので返さない"),
    "MULTI-065-07": dict(op="check", argv=["check", "REQ-001", "--base", "HEAD"], defect=False,
                         description="対照: 閉包と無関係な他のメンバーの重複はcheckの明示対象へ返さない"),
    "MULTI-065-08": dict(op="check", argv=["check", "--all-workspaces", "--base", "HEAD"], defect=True,
                         description="全体のcheckでも、メンバーの基準版の文書と同じパスでIDを読めない現在版を削除とみなさない"),
}


def directory_of(identifier):
    return "multi" if identifier.startswith("MULTI-") else "single"


def number(identifier):
    return int(identifier.rpartition("-")[2])


# --- 入力 -------------------------------------------------------------------------------------

def text_of(doc_id, kind, *, status="approved", title="文書", relations=None, ac=False, tests=None):
    """最小の仕様文書。`relations`は{関係: [参照...]}、`ac`は規範文AC-01を1件持つREQ、`tests`は[(path, covers)]。"""
    head = f"---\nid: {doc_id}\ntitle: {title}\nstatus: {status}\n"
    if relations:
        head += "relations:\n" + "".join(f"  {name}: [{', '.join(refs)}]\n" for name, refs in relations.items())
    if tests:
        head += "tests:\n" + "".join(f"  - path: {path}\n    covers: [{', '.join(covers)}]\n    command: default\n" for path, covers in tests)
    head += "---\n\n"
    if kind == "requirement":
        return (head + f"# {doc_id} {title}\n\n## Intent\n\n意図を定める。\n\n## Acceptance Criteria\n\n"
                f"- [{doc_id}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n## Verification\n\n未証明。\n")
    if kind == "decision":
        return head + f"# {doc_id} {title}\n\n## Context\n\n背景。\n\n## Decision\n\n採用する。\n\n## Consequences\n\n影響。\n"
    return head + f"# {doc_id} {title}\n\n## Context\n\n本文を定める。\n"


def copies(path, content):
    """同じ内容の2ファイル。重複の診断の発生元は、パスの辞書順で最初の`-copy`（`-`は`.`より前）。"""
    return {path: content.encode(), path[:-3] + "-copy.md": content.encode()}


def first_copy(path):
    return path[:-3] + "-copy.md"


def single_base():
    return dict(digest_reference.reviewed_inputs("SINGLE-042"))


def single_inputs(identifier):
    n = number(identifier)
    inputs = single_base()
    if n in (1, 2, 3):
        inputs.update(copies(".spec/technical/TECH-002.md", text_of("TECH-002", "technical", relations={"refines": ["TECH-001"]})))
    elif n in (4, 5):
        del inputs[REQ_PATH]
        inputs.update(copies(REQ_PATH, DOCUMENT))
    elif n == 6:
        req = inputs[REQ_PATH].decode().replace("status: approved\n", "status: approved\nrelations:\n  requires: [TECH-003]\n", 1)
        inputs[REQ_PATH] = req.encode()
        inputs.update(copies(".spec/technical/TECH-003.md", text_of("TECH-003", "technical")))
    elif n == 7:
        inputs.update(copies(".spec/technical/TECH-009.md", text_of("TECH-009", "technical", relations={"related": ["REQ-001"]})))
    elif n == 8:
        inputs = dict(related.reviewed_inputs("SINGLE-168-03"))
        inputs.update(copies(".spec/decisions/ADR-099.md", text_of("ADR-099", "decision", status="accepted")))
    elif n == 9:
        inputs.update(copies(".spec/technical/TECH-008.md", text_of("TECH-008", "technical")))
    elif n in (16, 17):
        inputs = {digest_reference.CONFIG_PATH: digest_reference.CONFIG.encode(),
                  ".spec/requirements/REQ-002.md": text_of("REQ-002", "requirement", title="後継の基準", relations={"supersedes": ["REQ-001"]}).encode()}
        inputs.update(copies(REQ_PATH, DOCUMENT))
    else:
        inputs = {digest_reference.CONFIG_PATH: CONFIGS["SINGLE-001"].encode(), REQ_PATH: DOCUMENT.encode(),
                  TECH_PATH: text_of("TECH-001", "technical", relations={"refines": ["REQ-001"]}).encode()}
    return inputs


BROKEN_REQ = DOCUMENT.replace("title: 文書の検査", "title: [文書の検査", 1)
OUTDATED_REQ = DOCUMENT.replace("status: approved", "status: outdated", 1)
CHANGED_REQ = DOCUMENT.replace("文書の検査", "変更後の文書検査")
MOVED_PATH = ".spec/requirements/REQ-001-moved.md"
NEW_TECH_PATH = ".spec/technical/TECH-009.md"
BROKEN_NEW_TECH = text_of("TECH-009", "technical").replace("title: 文書", "title: [文書", 1)
WEB_TECH = ".spec/technical/TECH-001.md"
BROKEN_WEB_TECH = text_of("TECH-001", "technical").replace("title: 文書", "title: [文書", 1)

PLATFORM_REQ_TEXT = text_of("REQ-001", "requirement", title="認証の基準", ac=True, tests=[("tests/root.py", ["REQ-001:AC-01"])])
MEMBERS = [("web", "apps/web"), ("api", "services/api")]


def multi_inputs(identifier):
    n = number(identifier)
    root_config = multi_reference.root_config(MEMBERS) + "verify:\n  commands:\n    default:\n      argv: [\"/bin/true\", \"{tests}\"]\n      cwd: .\n"
    inputs = {".spec/bitz.yaml": root_config.encode(), "apps/web/.spec/bitz.yaml": multi_reference.member_config("web", "default").encode(),
              "services/api/.spec/bitz.yaml": multi_reference.plain_config("api").encode(), "tests/root.py": b"x = 1\n"}
    platform_req = PLATFORM_REQ_TEXT
    web = {}
    if n in (1, 2, 3, 4):
        web.update(copies("apps/web/.spec/technical/TECH-005.md", text_of("TECH-005", "technical", relations={"refines": ["platform::REQ-001"]})))
    elif n == 5:
        platform_req = None
        inputs.update(copies(".spec/requirements/REQ-001.md", PLATFORM_REQ_TEXT))
        web["apps/web/.spec/technical/TECH-010.md"] = text_of("TECH-010", "technical", relations={"refines": ["platform::REQ-001"]}).encode()
    elif n == 6:
        platform_req = text_of("REQ-001", "requirement", title="認証の基準", ac=True, relations={"related": ["web::TECH-007"]},
                               tests=[("tests/root.py", ["REQ-001:AC-01"])])
        web.update(copies("apps/web/.spec/technical/TECH-007.md", text_of("TECH-007", "technical")))
    elif n == 7:
        web.update(copies("apps/web/.spec/technical/TECH-008.md", text_of("TECH-008", "technical")))
    elif n == 8:
        platform_req = None
        web["apps/web/" + WEB_TECH] = text_of("TECH-001", "technical").encode()
    if platform_req is not None:
        inputs[REQ_PATH] = platform_req.encode()
    inputs.update(web)
    return inputs


def reviewed_inputs(identifier):
    return single_inputs(identifier) if directory_of(identifier) == "single" else multi_inputs(identifier)


def reviewed_changes(identifier):
    """準備手順の`changes/`の入力（作業ツリーの変更の元）。"""
    return {"SINGLE-177-10": {"changes/REQ-001-broken.md": BROKEN_REQ.encode()},
            "SINGLE-177-11": {"changes/REQ-001-broken.md": BROKEN_REQ.encode()},
            "SINGLE-177-12": {"changes/REQ-001-moved.md": BROKEN_REQ.encode()},
            "SINGLE-177-13": {"changes/REQ-001-outdated.md": OUTDATED_REQ.encode()},
            "SINGLE-177-14": {"changes/TECH-009-broken.md": BROKEN_NEW_TECH.encode()},
            "SINGLE-177-15": {"changes/REQ-001-broken.md": BROKEN_REQ.encode(), "changes/REQ-001-moved.md": CHANGED_REQ.encode()},
            "MULTI-065-08": {"changes/TECH-001-broken.md": BROKEN_WEB_TECH.encode()}}.get(identifier, {})


def reviewed_manifest(identifier):
    case = CASES[identifier]
    n = number(identifier)
    status = reviewed_result(identifier)["status"]
    operations = []
    if directory_of(identifier) == "single" and (n <= 9 or n in (16, 17)) and case["op"] != "check":
        # `verify`は、テスト割当てを所有するワークスペースの設定がインデックスで未追跡だと起動を遮断するため、入力をステージする（`SINGLE-176`と同じ）。
        setup_plan = {"git": True, "operations": [{"op": "stage", "paths": ["."]}] if case["op"] == "verify" else []}
    else:
        if n == 10 or n == 11:
            operations = [{"op": "update", "path": REQ_PATH, "source": "changes/REQ-001-broken.md"}]
        elif n == 14 and directory_of(identifier) == "single":
            operations = [{"op": "create", "path": NEW_TECH_PATH, "source": "changes/TECH-009-broken.md"}]
        elif n == 15 and directory_of(identifier) == "single":
            operations = [{"op": "update", "path": REQ_PATH, "source": "changes/REQ-001-broken.md"},
                          {"op": "create", "path": MOVED_PATH, "source": "changes/REQ-001-moved.md"}]
        elif n == 12 and directory_of(identifier) == "single":
            operations = [{"op": "delete", "path": REQ_PATH}, {"op": "create", "path": MOVED_PATH, "source": "changes/REQ-001-moved.md"}]
        elif n == 13 and directory_of(identifier) == "single":
            operations = [{"op": "update", "path": REQ_PATH, "source": "changes/REQ-001-outdated.md"}]
        elif identifier == "MULTI-065-08":
            operations = [{"op": "update", "path": "apps/web/" + WEB_TECH, "source": "changes/TECH-001-broken.md"}]
        setup_plan = {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": operations}
    return {"fixtureId": identifier, "description": case["description"], "setup": setup_plan,
            "invocation": {"runner": "bitz", "cwd": ".", "argv": [*case["argv"], "--format", "json"], "env": {}},
            "expect": {"status": status, "exitCode": EXIT[status], "stdout": "json", "resultFile": f"expected/{case['op']}.json", "reportFileCount": 0}}


# --- 期待する診断（規範と承認済みの文言から導く） ----------------------------------------------------

def duplicate(doc_id, path, workspace="root", qualified=False):
    shown = f"{workspace}::{doc_id}" if qualified else doc_id
    return {"code": DUPLICATE, "severity": "error", "resultStatus": "failed", "summary": f"文書ID {shown}が重複しています",
            "source": {"kind": "file", "workspaceId": workspace, "path": path, "key": "id"}}


def root_missing(argument):
    return {"code": ROOT_MISSING, "severity": "error", "resultStatus": "failed", "summary": f"起点{argument}が存在しません",
            "source": {"kind": "invocation", "argument": argument}}


def relation_missing(evidence, path, workspace, key):
    return {"code": RELATION_MISSING, "severity": "error", "resultStatus": "failed", "summary": "強い関係の参照先が存在しません",
            "source": {"kind": "file", "workspaceId": workspace, "path": path, "key": key}, "evidence": evidence}


def schema_error(path, workspace="root"):
    return {"code": SCHEMA, "severity": "error", "resultStatus": "failed", "summary": "フロントマターのYAMLの構文が不正です",
            "source": {"kind": "file", "workspaceId": workspace, "path": path, "key": "title"}}


def transition_deleted(path, workspace="root"):
    return {"code": TRANSITION, "severity": "error", "resultStatus": "failed", "summary": "管理済みの仕様文書が削除されています",
            "source": {"kind": "file", "workspaceId": workspace, "path": path}}


def safety_changed(path):
    return {"code": "SPEC-SAFETY-APPROVED-001", "severity": "error", "resultStatus": "failed",
            "summary": "状態approvedのREQの意味変更時に文書の状態が戻されていません",
            "source": {"kind": "file", "workspaceId": "root", "path": path, "key": "title"}}


def impact(path, dependent, changed, key):
    return {"code": IMPACT, "severity": "warning", "resultStatus": "passed_with_warnings",
            "summary": f"{dependent}が強く依存する{changed}が変更されています。再確認してください",
            "source": {"kind": "file", "workspaceId": "root", "path": path, "key": key}}


def reviewed_diagnostics(identifier):
    """検証対象・結果の診断。並びは発生元のワークスペースID、`path`、`code`の辞書順（結果・診断・終了コード §7。発生元が`invocation`のものは先頭）。
    `path`は文字コード順なので、`-copy.md`は`.md`より前、`.spec/requirements/`は`.spec/technical/`より前になる。"""
    n = number(identifier)
    if directory_of(identifier) == "single":
        if n in (1, 2, 3):
            return [duplicate("TECH-002", first_copy(".spec/technical/TECH-002.md"))]
        if n in (4, 5):
            return [root_missing("REQ-001"), duplicate("REQ-001", first_copy(REQ_PATH))]
        if n == 6:
            return [relation_missing("TECH-003", REQ_PATH, "root", "relations.requires"), duplicate("TECH-003", first_copy(".spec/technical/TECH-003.md"))]
        if n == 8:
            return related.reviewed_diagnostics("SINGLE-168-03")
        if n in (16, 17):
            return [duplicate("REQ-001", first_copy(REQ_PATH)), relation_missing("REQ-001", ".spec/requirements/REQ-002.md", "root", "relations.supersedes")]
        if n == 10:
            # `TECH-001`は索引に入らない`REQ-001`を`refines`する、その文書への直接の逆参照として完全検査の対象に入る（`check` §5）。
            return [schema_error(REQ_PATH), relation_missing("REQ-001", TECH_PATH, "root", "relations.refines")]
        if n == 14:
            return [schema_error(NEW_TECH_PATH)]
        if n == 15:
            return [safety_changed(MOVED_PATH), schema_error(REQ_PATH), impact(TECH_PATH, "TECH-001", "REQ-001", "relations.refines")]
        if n == 11:
            return [schema_error(REQ_PATH), relation_missing("REQ-001", TECH_PATH, "root", "relations.refines")]
        if n == 12:
            return [schema_error(MOVED_PATH), transition_deleted(REQ_PATH), impact(TECH_PATH, "TECH-001", "REQ-001", "relations.refines")]
        if n == 13:
            return [impact(TECH_PATH, "TECH-001", "REQ-001", "relations.refines")]
        return []
    if n in (1, 2, 3, 4):
        return [duplicate("TECH-005", first_copy(".spec/technical/TECH-005.md"), "web", True)]
    if n == 5:
        return [duplicate("REQ-001", first_copy(REQ_PATH), "platform", True),
                relation_missing("platform::REQ-001", ".spec/technical/TECH-010.md", "web", "relations.refines")]
    if n == 6:
        return [{"code": ADVISORY, "severity": "warning", "resultStatus": "passed_with_warnings", "summary": "関係型relatedの参照先が存在しません",
                 "source": {"kind": "file", "workspaceId": "platform", "path": REQ_PATH, "key": "relations.related"}, "evidence": "web::TECH-007"}]
    return []


# --- 期待結果 ---------------------------------------------------------------------------------

def status_of(diagnostics):
    if any(d["resultStatus"] == "failed" for d in diagnostics):
        return "failed"
    return "passed_with_warnings" if diagnostics else "passed"


def context_failure(roots, diagnostics, workspace, unresolved, multi=False, revision=None):
    result = {
        "schemaVersion": "1.0", "operation": "context", "status": "failed", "purpose": "verify", "workspace": workspace, "roots": roots,
        "contextDigest": None, "revision": revision,
        "resolution": {"complete": False, "documentCount": 0, "unresolvedStrongRelations": unresolved},
        "projection": {"detail": "standard", "expanded": []}, "documents": [], "constraintLedger": {"statements": []},
        "coverage": {"must": dict(EMPTY_BUCKET), "should": dict(EMPTY_BUCKET), "may": dict(EMPTY_BUCKET), "adjacent": []},
        "durationMs": 0, "diagnostics": diagnostics}
    if multi:
        result["resolution"]["workspaces"] = [dict(workspace)]
        result["resolution"]["crossWorkspaceEdges"] = []
    return result


def single_digest():
    return digest_reference.digest(digest_reference.canonical_bytes(digest_reference.reviewed_digest_input("SINGLE-042")))


def reviewed_single_result(identifier):
    n = number(identifier)
    case = CASES[identifier]
    diagnostics = reviewed_diagnostics(identifier)
    root = {"id": "root", "path": "."}
    if case["op"] == "context":
        if n == 9:
            return digest_result("SINGLE-042", single_digest())
        if n == 16:
            return context_failure(["REQ-002"], diagnostics, root, 1)
        return context_failure(["REQ-001"], diagnostics, root, 1 if n == 6 else 0)
    if case["op"] == "verify":
        if n == 8:
            return related.reviewed_verify_success("SINGLE-168-03")
        if n == 7:
            entry = {"target": "REQ-001", "status": "passed", "contextDigest": single_digest(), "statements": list(related.STATEMENTS),
                     "bindingRefs": ["root::default"], "diagnostics": []}
            result = copy.deepcopy(related.reviewed_verify_success("SINGLE-168-03"))
            result.update({"status": "passed", "targetResults": [entry]})
            return result
        entry = {"target": "REQ-002" if n == 17 else "REQ-001", "status": "failed", "contextDigest": None, "statements": [], "bindingRefs": [],
                 "diagnostics": diagnostics}
        return {"schemaVersion": "1.0", "operation": "verify", "status": "failed", "scope": "selected", "workspace": root,
                "targetResults": [entry], "revision": None, "commands": [], "durationMs": 0, "diagnostics": []}
    status = status_of(diagnostics)
    result = {"schemaVersion": "1.0", "operation": "check", "status": status, "workspace": root, "durationMs": 0, "diagnostics": diagnostics}
    if n == 3:
        result.update(scope="selected", revision={"base": COMMIT, "commit": COMMIT, "dirty": False}, checkedDocumentCount=2, checkedStatementCount=2)
    elif n == 11:
        # 全体の検査: `REQ-001`は索引に入らないので、検査する文書は`TECH-001`の1件（規範文なし）。
        result.update(scope="full", revision={"base": COMMIT, "commit": COMMIT, "dirty": True}, checkedDocumentCount=1, checkedStatementCount=0)
    else:
        # 変更されたパスの数と、所有文書の数（基準版のIDを含む。基準版にない新規のファイルは所有文書を持たない）。
        selected = {"changedPathCount": 2 if n in (12, 15) else 1, "targetDocumentCount": 0 if n == 14 else 1, "excludedCodeTestPathCount": 0}
        result.update(scope="changed", revision={"base": COMMIT, "commit": COMMIT, "dirty": True}, selection=selected)
    return result


def command(workspace, tests, covers):
    return {"bindingId": f"{workspace}::default", "workspaceId": workspace, "name": "default", "status": "passed", "termination": "exit", "cwd": ".",
            "argv": ["/bin/true", *tests], "tests": list(tests), "covers": list(covers), "exitCode": 0, "timeoutSeconds": 300,
            "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}


def reviewed_multi_result(identifier):
    n = number(identifier)
    case = CASES[identifier]
    diagnostics = reviewed_diagnostics(identifier)
    platform = {"id": "platform", "path": "."}
    revision = {"commit": COMMIT, "dirty": False}
    if case["op"] == "context":
        if n == 5:
            return context_failure(["web::TECH-010"], diagnostics, {"id": "web", "path": "apps/web"}, 1, True, revision)
        return context_failure(["platform::REQ-001"], diagnostics, platform, 0, True, revision)
    if case["op"] == "verify" and n == 2:
        entry = {"target": "platform::REQ-001", "status": "failed", "contextDigest": None, "statements": [], "bindingRefs": [], "diagnostics": diagnostics}
        return {"schemaVersion": "1.0", "operation": "verify", "status": "failed", "scope": "selected", "workspace": platform,
                "targetResults": [entry], "revision": revision, "commands": [], "durationMs": 0, "diagnostics": []}
    if case["op"] == "verify":
        entry = {"target": "platform::REQ-001", "status": "failed", "contextDigest": None, "statements": [], "bindingRefs": [], "diagnostics": diagnostics}
        no_target = lambda ws: [{"code": "SPEC-VERIFY-BLOCKED-002", "severity": "warning", "resultStatus": "passed_with_warnings", "summary": "検証対象がありません",
                                 "source": {"kind": "file", "workspaceId": ws, "path": ".spec/bitz.yaml"}}]
        workspaces = [{"id": "platform", "path": ".", "status": "failed", "targetResults": [entry], "commands": [], "durationMs": 0, "diagnostics": []},
                      {"id": "api", "path": "services/api", "status": "passed_with_warnings", "targetResults": [], "commands": [], "durationMs": 0, "diagnostics": no_target("api")},
                      {"id": "web", "path": "apps/web", "status": "passed_with_warnings", "targetResults": [], "commands": [], "durationMs": 0, "diagnostics": no_target("web")}]
        return {"schemaVersion": "1.0", "operation": "verify", "scope": "all-workspaces", "status": "failed", "multiWorkspace": platform,
                "workspaces": workspaces, "revision": revision, "durationMs": 0, "diagnostics": []}
    if n == 8:
        web_diagnostics = [schema_error(WEB_TECH, "web")]
        workspaces = [{"id": "platform", "path": ".", "status": "passed", "checkedDocumentCount": 0, "checkedStatementCount": 0, "durationMs": 0, "diagnostics": []},
                      {"id": "api", "path": "services/api", "status": "passed", "checkedDocumentCount": 0, "checkedStatementCount": 0, "durationMs": 0, "diagnostics": []},
                      {"id": "web", "path": "apps/web", "status": "failed", "checkedDocumentCount": 0, "checkedStatementCount": 0, "durationMs": 0, "diagnostics": web_diagnostics}]
        return {"schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": "failed", "multiWorkspace": platform, "workspaces": workspaces,
                "revision": {"base": COMMIT, "commit": COMMIT, "dirty": True}, "durationMs": 0, "diagnostics": []}
    return {"schemaVersion": "1.0", "operation": "check", "status": status_of(diagnostics), "scope": "selected", "workspace": platform,
            "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False}, "checkedDocumentCount": 1, "checkedStatementCount": 1,
            "durationMs": 0, "diagnostics": diagnostics}


def reviewed_result(identifier):
    return reviewed_single_result(identifier) if directory_of(identifier) == "single" else reviewed_multi_result(identifier)


# --- 参照計算（入力の木構造だけから導く） ------------------------------------------------------------

FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def parse(text):
    """フロントマターから`id`、`status`、`relations`の{関係: [参照...]}を読む。読めなければ`None`（IDを読めないファイル）。"""
    match = FRONT.match(text)
    if match is None:
        return None
    fields, relations, in_relations = {}, {}, False
    for line in match.group(1).split("\n"):
        if in_relations and line.startswith("  ") and not line.startswith("   "):
            name, _, value = line.strip().partition(": ")
            relations[name] = [item.strip() for item in value.strip("[]").split(",") if item.strip()]
            continue
        in_relations = False
        key, _, value = line.partition(": ")
        if line == "relations:":
            in_relations = True
        elif key in ("id", "status", "title"):
            fields[key] = value
    if "id" not in fields or fields.get("title", "").startswith("[") or fields.get("status") not in ("approved", "draft", "outdated", "rejected", "accepted"):
        return None
    return {"id": fields["id"], "status": fields["status"], "relations": relations}


def load_documents(files):
    """{(ワークスペースID, 文書ID): [写しの関係...]}と、IDを読めないファイルのパス。複合ワークスペースでは先頭のメンバーのパスでワークスペースを決める。"""
    owners = {"apps/web/": "web", "services/api/": "api"}
    documents, unreadable = {}, []
    for path, content in sorted(files.items()):
        if ".spec/" not in path or not path.endswith(".md"):
            continue
        workspace = next((name for prefix, name in owners.items() if path.startswith(prefix)), "platform" if any(p.startswith(("apps/", "services/")) for p in files) else "root")
        parsed = parse(content.decode())
        if parsed is None:
            unreadable.append(path)
            continue
        documents.setdefault((workspace, parsed["id"]), []).append(parsed["relations"])
    return documents, unreadable


def owner_of(ref, workspace):
    qualified, _, local = ref.rpartition("::")
    return (qualified or workspace, local.partition(":")[0])


def reference_duplicates(files, root, purpose="verify"):
    """起点`(ワークスペース, ID)`の閉包を作るときに辿る重複したID（`related`は辿らない）。重複した文書は、写しのどれか1つでも辿れば辿る。"""
    documents, _ = load_documents(files)
    duplicated = {key for key, group in documents.items() if len(group) > 1}
    if root in duplicated:
        return {root}
    traversed = {root}

    def declared(key):
        return [relations for relations in documents.get(key, [])]

    # 起点から`requires`を終端まで、起点の`refines`の参照先（その`requires`は辿らない）。
    stack = [root]
    while stack:
        current = stack.pop()
        for relations in declared(current):
            for ref in relations.get("requires", []):
                target = owner_of(ref, current[0])
                if target not in traversed:
                    traversed.add(target)
                    if target not in duplicated:
                        stack.append(target)
    for relations in declared(root):
        for ref in relations.get("refines", []) + relations.get("supersedes", []):
            traversed.add(owner_of(ref, root[0]))
    # 逆参照: 起点を所有する文書を`refines`する文書を推移的に（出発点は起点だけ）。起点を`supersedes`する後継も辿る。
    frontier = [root]
    while frontier:
        target = frontier.pop()
        for key, group in documents.items():
            if key == root or key in traversed:
                continue
            if any(owner_of(ref, key[0]) == target for relations in group for ref in relations.get("refines", [])):
                traversed.add(key)
                frontier.append(key)
    for key, group in documents.items():
        if any(owner_of(ref, key[0]) == root for relations in group for ref in relations.get("supersedes", [])):
            traversed.add(key)
    return traversed & duplicated


def reference_base_comparison(base_files, current_files):
    """基準版の文書のうち、削除とみなす文書のパス（現在版にIDもパスも対応しないもの）と、IDを読めない現在版のパス。"""
    base_documents, _ = load_documents(base_files)
    current_documents, unreadable = load_documents(current_files)
    base_paths = {}
    for path, content in base_files.items():
        parsed = parse(content.decode()) if ".spec/" in path and path.endswith(".md") else None
        if parsed is not None:
            base_paths[path] = parsed["id"]
    current_ids = {key[1] for key in current_documents}
    deleted = sorted(path for path, doc_id in base_paths.items() if doc_id not in current_ids and path not in unreadable)
    return deleted, sorted(unreadable)


# --- 検査 -------------------------------------------------------------------------------------

def result_diagnostics(result):
    """結果の木構造に実在する診断の全体（最上位、ワークスペース、検証対象）。"""
    found = list(result.get("diagnostics", []))
    for entry in result.get("targetResults", []):
        found += entry["diagnostics"]
    for workspace in result.get("workspaces", []):
        found += workspace["diagnostics"]
        for entry in workspace.get("targetResults", []):
            found += entry["diagnostics"]
    return found


def duplicate_roots(identifier):
    """C96の欠陥・対照が使う起点`(ワークスペース, ID)`。"""
    n = number(identifier)
    if directory_of(identifier) == "single":
        return ("root", "REQ-002" if number(identifier) in (16, 17) else "REQ-001")
    return ("web", "TECH-010") if n == 5 else ("platform", "REQ-001")


def check_conditions(identifier, repository, manifest, result):
    """名乗る条件を、準備手順の後の入力から確かめる（Coreの出力は根拠にしない）。"""
    n = number(identifier)
    files = {p.relative_to(repository).as_posix(): p.read_bytes() for p in repository.rglob("*") if p.is_file() and ".git" not in p.relative_to(repository).parts}
    codes = [d["code"] for d in result_diagnostics(result)]
    if (directory_of(identifier) == "single" and (n <= 9 or n in (16, 17))) or (directory_of(identifier) == "multi" and n <= 7):
        documents, _ = load_documents(files)
        if not any(len(group) > 1 for group in documents.values()):
            raise ValueError("文書IDが重複した入力が必要です")
        returned = {(d["source"]["workspaceId"], d["summary"].rpartition("::")[2].replace("文書ID ", "").replace("が重複しています", ""))
                    for d in result_diagnostics(result) if d["code"] == DUPLICATE}
        derived = reference_duplicates(files, duplicate_roots(identifier))
        if derived != returned:
            raise ValueError(f"閉包を作るときに辿る重複が、入力から導く結果と期待で異なります: {sorted(derived)} / {sorted(returned)}")
        if CASES[identifier]["defect"] and not returned:
            raise ValueError("欠陥のfixtureは重複を返す期待を持つ必要があります")
    else:
        base_files = {}
        names = subprocess.run(["git", "ls-tree", "-r", "--name-only", "-z", "HEAD"], cwd=repository, capture_output=True, check=True).stdout.decode().split("\0")[:-1]
        for name in names:
            base_files[name] = subprocess.run(["git", "show", "HEAD:" + name], cwd=repository, capture_output=True, check=True).stdout
        deleted, unreadable = reference_base_comparison(base_files, files)
        # 診断のパスはワークスペースのルートからの相対。
        relative = lambda paths: sorted(p.removeprefix("apps/web/") for p in paths)
        if sorted(d["source"]["path"] for d in result_diagnostics(result) if d["code"] == TRANSITION) != relative(deleted):
            raise ValueError("削除の診断が、入力から導く結果と異なります")
        if sorted(d["source"]["path"] for d in result_diagnostics(result) if d["code"] == SCHEMA) != relative(unreadable):
            raise ValueError("IDを読めないファイル自身の診断が、入力から導く結果と異なります")
        if identifier in ("SINGLE-177-10", "SINGLE-177-11", "MULTI-065-08") and (deleted or IMPACT in codes or not unreadable):
            raise ValueError("同じパスでIDを読めない現在版は、削除にも影響候補にもしない入力と期待である必要があります")
    if (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (result["status"], EXIT[result["status"]]):
        raise ValueError("状態または終了コードが期待と異なります")


# --- 書き出しと監査 ---------------------------------------------------------------------------

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
        for name, content in reviewed_changes(identifier).items():
            path = fixture / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / f"expected/{CASES[identifier]['op']}.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-duplicate-closure-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(_dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def actual_files(fixture, directory):
    """`directory`の通常のファイル(パス→バイト列)。シンボリックリンクと実行ビットを拒否する。"""
    files = {}
    base = fixture / directory
    if not base.exists():
        return files
    for path in sorted(base.rglob("*")):
        relative = path.relative_to(fixture / ("repo" if directory == "repo" else ".")).as_posix()
        if path.is_symlink():
            raise ValueError(f"{relative}はシンボリックリンクであってはいけません")
        if path.is_file():
            if path.stat().st_mode & 0o111:
                raise ValueError(f"{relative}は実行ビットを持ってはいけません")
            files[relative] = path.read_bytes()
    return files


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text())) for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / directory_of(identifier) / identifier
        try:
            op = CASES[identifier]["op"]
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / f"expected/{op}.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            if {p.name for p in (fixture / "expected").glob("*")} != {f"{op}.json"}:
                raise ValueError("期待結果のファイルの構成がレビュー済みの形と異なります")
            if actual_files(fixture, "repo") != reviewed_inputs(identifier):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if actual_files(fixture, "changes") != reviewed_changes(identifier):
                raise ValueError("変更の元がレビュー済みの入力と異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("検査はファイルを書いてはいけません")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-duplicate-closure-") as temporary:
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
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
