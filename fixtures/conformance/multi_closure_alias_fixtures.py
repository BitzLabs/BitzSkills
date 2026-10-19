"""複合ワークスペースの閉包と統合索引の別名に関する欠陥を固定する（Coreの公開操作は実行しない）。

実装の確認事項C18・C21・C19とユーザーの決定D7・D8に対応する（ADR-051の追加）。複合ワークスペースの`context`と`verify`が、
単一ワークスペースと同じ規則で、閉包の文書の強い関係を検査し、起点ワークスペースの文書を別名で二重に収録しないことを、22件で固定する。

| fixture | 操作と実行ディレクトリ | 原因と期待 |
|---|---|---|
| `MULTI-038-01` | `context web::REQ-001`、`.` | 閉包の外（到達できない`web`の2文書）にだけ`requires`の循環がある。`context`は閉包の文書だけを検査するので通る |
| `MULTI-038-02` | `context web::REQ-001`、`.` | 閉包の中に`requires`の循環がある。`CTX-CYCLE-001`を循環に参加するエッジの宣言元ごとに返す |
| `MULTI-038-03` | `verify web::REQ-001`、`.` | 同じ入力。`verify`も閉包の中の循環を検証対象の`diagnostics`に返す |
| `MULTI-038-04` | `verify --all-workspaces`、`.` | 同じ入力。全体の`verify`も、`web`の検証対象に循環を返す |
| `MULTI-038-05` | `context REQ-001`、`.`（単一） | 対照: 単一ワークスペースも、閉包の外の循環で`context`は失敗しない |
| `MULTI-038-06` | `verify REQ-001`、`.`（単一） | 対照: 単一ワークスペースの`verify`は、閉包の中の循環を検出する |
| `MULTI-038-07` | `context web::REQ-001 --detail compact`、`.` | `web`の文書`TECH-010`が、非修飾の宣言と、`api`の文書からの修飾した宣言（`web::TECH-010`）の両方で到達される。1件だけ収録する |
| `MULTI-038-08` | `context web::REQ-001`、`.` | 修飾した宣言（別名）だけで到達する`web`の文書の、強い関係の参照切れを検出する |
| `MULTI-038-09` | `verify web::REQ-001`、`.` | 同じ入力。`verify`も検出する |
| `MULTI-038-10` | `context web::REQ-001`、`.` | 対照: 非修飾の宣言で到達する同じ誤り。`MULTI-038-08`と同じ診断 |
| `MULTI-038-11` | `context REQ-001 --purpose interpret`、`apps/web` | 目的`interpret`でも、他のメンバーの文書の`requires`が承認されていないADRを指せば`CTX-RELATION-TYPE-001` |
| `MULTI-038-12` | `context REQ-001 --purpose implement`、`apps/web` | 他のメンバーの文書が自ワークスペースを修飾した参照（`api::ADR-001`）の`evidence`は宣言どおり |
| `MULTI-038-13` | `verify web::REQ-001`、`.` | 同じ入力。`verify`の`evidence`も宣言どおり |
| `MULTI-038-14` | `context REQ-001 --purpose interpret`、`.`（単一） | 対照: 単一ワークスペースの`interpret`は承認されていないADRへの`requires`を検出する |
| `MULTI-038-15` | `context web::REQ-001 --purpose interpret`、`.` | `api`の文書が`web`の起点を修飾した宣言（`refines: [web::REQ-001]`）で具体化する。別名でも閉包に含める（含めるとハッシュ値が変わる。D8） |
| `MULTI-038-16` | `context web::REQ-001 --detail compact`、`.` | 起点と同じワークスペースの文書が、非修飾で起点を`refines`する。具体化する文書を1件だけ収録する |
| `MULTI-038-17` | `context web::REQ-001 --detail compact`、`.` | 同じワークスペースの`REQ-002`が`REQ-001`を`supersedes`する（有効な後継は1つ）。後継を二重に数えず、起点を`advisory`、後継を`replacement`で示す |
| `MULTI-038-18` | `context web::REQ-001 --purpose implement`、`.` | 状態`open`のTASKが、自ワークスペースを修飾した規範文ID（`web::REQ-001:AC-01`）を`addresses`する。TASKを閉包に含めて対応済みにする（警告なし。含めるとハッシュ値が変わる。D8） |
| `MULTI-038-19` | `context web::REQ-001 --detail compact`、`.` | 他のメンバー`api`の`REQ-009`が`supersedes: [web::REQ-001]`（有効な後継は1つ）。起点を`advisory`、後継を`replacement`で示す（含めるとハッシュ値が変わる） |
| `MULTI-038-20` | `verify web::REQ-001`、`.` | 同じ入力。置換済みの起点の`verify`は`CTX-STATE-SUPERSEDED-001`で`blocked`（修正前は`passed`） |
| `MULTI-038-21` | `context web::REQ-001`、`.` | 状態`draft`の`api`の`TECH-040`が`refines: [web::REQ-001]`。`advisory`として含める（含めるとハッシュ値が変わる） |
| `MULTI-038-22` | `context web::REQ-001 --purpose implement`、`.` | 状態`open`の`api`の`TASK-009`が`addresses: [web::REQ-001:AC-01]`。閉包に含めて対応済みにする（含めるとハッシュ値が変わる） |

基本のリポジトリは、ルート`platform`（`.`、文書なし）、メンバー`web`（`apps/web`）と`api`（`services/api`）である。
単一ワークスペースの対照は、ルートの設定が`multiWorkspace`を持たない（ワークスペースIDは`root`）。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。

- 関係・トレースモデル §3・§4: 強い関係の参照切れ、型違反、禁止された循環は`failed`。`requires`と`refines`を合わせた依存グラフの循環を禁止する。
  `requires`の参照先のADRは状態`accepted`だけを許す。
- 同 §6: 閉包は起点から強い関係を辿って得る文書の集合で、型、状態、循環、上限を満たさない場合は閉包の全体を非成功とする。
  同 §7: 同じ文書が複数の経路から到達しても1回だけ収録し、到達したエッジを保持する。
- 同 §5・§5.1、複合ワークスペース仕様 §4: 複合ワークスペースでは`(workspace-id, local-id)`の組が索引のキーである。同じ文書を修飾した宣言と修飾していない宣言で
  参照しても同じ文書であり、別の文書として二重に収録しない。
- `context` §3: ID、型、状態、強い関係、循環を検査してから、目的ごとの閉包を完全解決する。強い関係の一部を解決できないコンテキスト一式を成功にしない。
  `verify` §9: 検証対象ごとに目的`verify`のコンテキストを完全解決するので、`CTX-CYCLE-001`などを検証対象の`diagnostics`へ返し得る。
- 結果・診断・終了コード §4: 関係のエッジを単位とする診断の`evidence`は、参照先を宣言どおりの文字列で持つ。
- コンテキストのハッシュ値の正規化仕様 §3: 閉包の文書ごとの材料。同じ文書を二重に含めない。ハッシュ値は、独立に書いた2系統の参照計算
  （このモジュールのリテラルA、入力の木構造から導出するB）のバイト列の一致を要求する。

参照計算`reference_*`は、入力の木構造から、閉包、到達したエッジ、距離、循環に参加するエッジ、参照切れ、型違反を導く。
Coreの出力は期待値の根拠にしない。
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import (digest_crosscheck, digest_reference, multi_crosscheck, multi_reference,
               multi_relation_type_fixtures as relation_type, multi_verify_fixtures as verify_fixtures)
from .context_failure_fixtures import PROPOSED_ADR, PROPOSED_ADR_PATH
from .digest_crosscheck import KIND_BY_DIRECTORY, KIND_RANK, normalize_body, read_statements, read_yaml, split_document
from .harness import setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
MEMBERS = [("web", "apps/web"), ("api", "services/api")]
WEB_TEST_PATH = "apps/web/tests/test_login.py"
SINGLE_TEST_PATH = "tests/test_login.py"
TEST_BYTES = b"def test_login():\n    assert True\n"
REQ_TITLE = "認証の基準"
REQ_TEXT = "秘密情報を出力しない"
FIXTURE_KINDS = {"requirement": "reqFrontmatter", "technical": "techFrontmatter",
                 "decision": "adrFrontmatter", "task": "taskFrontmatter"}
KIND_LABEL = {"requirement": "REQ", "technical": "TECH", "decision": "ADR", "task": "TASK"}
CYCLE_SUMMARY = "関係型requiresに禁止された循環があります"
MISSING_SUMMARY = "強い関係の参照先が存在しません"
NO_TARGET = verify_fixtures.NO_TARGET

# id: {op, cwd, argv, corpus, single, root, ...}。`root`は起点の正規ID（複合ワークスペースでは修飾ID）、`outcome`は期待する状態。
CASES = {
    "MULTI-038-01": dict(op="context", cwd=".", argv=["context", "web::REQ-001", "--purpose", "interpret"], corpus="cycle-outside",
                         single=False, root="web::REQ-001", outcome="passed",
                         description="閉包の外にだけ強い関係の循環があるとき、複合ワークスペースのcontextは失敗しない"),
    "MULTI-038-02": dict(op="context", cwd=".", argv=["context", "web::REQ-001", "--purpose", "interpret"], corpus="cycle-inside",
                         single=False, root="web::REQ-001", outcome="failed",
                         description="閉包の中に強い関係の循環があるとき、複合ワークスペースのcontextはCTX-CYCLE-001で失敗する"),
    "MULTI-038-03": dict(op="verify", cwd=".", argv=["verify", "web::REQ-001"], corpus="cycle-inside",
                         single=False, root="web::REQ-001", outcome="failed",
                         description="閉包の中に強い関係の循環があるとき、複合ワークスペースの明示対象のverifyはCTX-CYCLE-001で失敗する"),
    "MULTI-038-04": dict(op="verify", cwd=".", argv=["verify", "--all-workspaces"], corpus="cycle-inside",
                         single=False, root="web::REQ-001", outcome="failed",
                         description="閉包の中に強い関係の循環があるとき、複合ワークスペース全体のverifyはCTX-CYCLE-001で失敗する"),
    "MULTI-038-05": dict(op="context", cwd=".", argv=["context", "REQ-001", "--purpose", "interpret"], corpus="cycle-outside",
                         single=True, root="REQ-001", outcome="passed",
                         description="単一ワークスペースのcontextは、閉包の外の強い関係の循環で失敗しない"),
    "MULTI-038-06": dict(op="verify", cwd=".", argv=["verify", "REQ-001"], corpus="cycle-inside",
                         single=True, root="REQ-001", outcome="failed",
                         description="単一ワークスペースのverifyは、閉包の中の強い関係の循環をCTX-CYCLE-001で検出する"),
    "MULTI-038-07": dict(op="context", cwd=".", argv=["context", "web::REQ-001", "--purpose", "interpret", "--detail", "compact"],
                         corpus="alias-duplicate", single=False, root="web::REQ-001", outcome="passed",
                         description="起点ワークスペースの文書を非修飾と修飾の両方で参照しても、contextは1件だけ収録する"),
    "MULTI-038-08": dict(op="context", cwd=".", argv=["context", "web::REQ-001", "--purpose", "interpret"], corpus="alias-error",
                         single=False, root="web::REQ-001", outcome="failed",
                         description="修飾した宣言で到達した起点ワークスペースの文書の参照切れを、contextが検出する"),
    "MULTI-038-09": dict(op="verify", cwd=".", argv=["verify", "web::REQ-001"], corpus="alias-error",
                         single=False, root="web::REQ-001", outcome="failed",
                         description="修飾した宣言で到達した起点ワークスペースの文書の参照切れを、verifyが検出する"),
    "MULTI-038-10": dict(op="context", cwd=".", argv=["context", "web::REQ-001", "--purpose", "interpret"], corpus="direct-error",
                         single=False, root="web::REQ-001", outcome="failed",
                         description="非修飾の宣言で到達した同じ参照切れの対照。修飾した宣言と同じ診断を返す"),
    "MULTI-038-11": dict(op="context", cwd="apps/web", argv=["context", "REQ-001", "--purpose", "interpret"], corpus="adr-proposed",
                         single=False, root="web::REQ-001", outcome="failed",
                         description="目的interpretでも、他のメンバーの文書が承認されていないADRをrequiresするとき型制約でcontextを失敗にする"),
    "MULTI-038-12": dict(op="context", cwd="apps/web", argv=["context", "REQ-001", "--purpose", "implement"], corpus="adr-qualified",
                         single=False, root="web::REQ-001", outcome="failed",
                         description="他のメンバーの文書が自ワークスペースを修飾した参照で承認されていないADRをrequiresするとき、evidenceは宣言どおりにする"),
    "MULTI-038-13": dict(op="verify", cwd=".", argv=["verify", "web::REQ-001"], corpus="adr-qualified",
                         single=False, root="web::REQ-001", outcome="failed",
                         description="他のメンバーの文書が自ワークスペースを修飾した参照で承認されていないADRをrequiresするとき、verifyのevidenceは宣言どおりにする"),
    "MULTI-038-14": dict(op="context", cwd=".", argv=["context", "REQ-001", "--purpose", "interpret"], corpus="adr-single",
                         single=True, root="REQ-001", outcome="failed", commit=False,
                         description="単一ワークスペースのinterpretは、承認されていないADRへのrequiresを型制約で検出する"),
    "MULTI-038-15": dict(op="context", cwd=".", argv=["context", "web::REQ-001", "--purpose", "interpret"], corpus="alias-refines",
                         single=False, root="web::REQ-001", outcome="passed",
                         description="他のメンバーの文書が起点を修飾した宣言でrefinesするとき、起点を具体化する文書として閉包に含める"),
    "MULTI-038-16": dict(op="context", cwd=".", argv=["context", "web::REQ-001", "--purpose", "interpret", "--detail", "compact"],
                         corpus="same-refines", single=False, root="web::REQ-001", outcome="passed",
                         description="起点を同じワークスペースの文書がrefinesするとき、具体化する文書を1件だけ収録する"),
    "MULTI-038-17": dict(op="context", cwd=".", argv=["context", "web::REQ-001", "--purpose", "interpret", "--detail", "compact"],
                         corpus="supersede", single=False, root="web::REQ-001", outcome="passed",
                         description="同じワークスペースの有効な後継が1つのとき、後継を二重に数えず置換済みの起点を後継つきで示す"),
    "MULTI-038-18": dict(op="context", cwd=".", argv=["context", "web::REQ-001", "--purpose", "implement"],
                         corpus="task-addresses", single=False, root="web::REQ-001", outcome="passed",
                         description="自ワークスペースを修飾した規範文をaddressesする状態openのTASKを、implementの閉包に含めて対応済みにする"),
    "MULTI-038-19": dict(op="context", cwd=".", argv=["context", "web::REQ-001", "--purpose", "interpret", "--detail", "compact"],
                         corpus="other-supersede", single=False, root="web::REQ-001", outcome="passed",
                         description="他のメンバーの文書が起点をsupersedesするとき、起点をadvisory、後継をreplacementとして示す"),
    "MULTI-038-20": dict(op="verify", cwd=".", argv=["verify", "web::REQ-001"], corpus="other-supersede",
                         single=False, root="web::REQ-001", outcome="blocked",
                         description="他のメンバーの文書が起点をsupersedesするとき、verifyはCTX-STATE-SUPERSEDED-001でblockedにする"),
    "MULTI-038-21": dict(op="context", cwd=".", argv=["context", "web::REQ-001", "--purpose", "interpret"],
                         corpus="other-draft-refines", single=False, root="web::REQ-001", outcome="passed",
                         description="状態draftの他のメンバーの文書が起点を修飾してrefinesするとき、advisoryとして含める"),
    "MULTI-038-22": dict(op="context", cwd=".", argv=["context", "web::REQ-001", "--purpose", "implement"],
                         corpus="other-task", single=False, root="web::REQ-001", outcome="passed",
                         description="他のメンバーの状態openのTASKが起点の規範文をaddressesするとき、implementの閉包に含めて対応済みにする"),
}
RESULT_FILES = {"context": "expected/context.json", "verify": "expected/verify.json"}
EMPTY_BUCKET = {key: [] for key in ("total", "addressed", "tested", "unaddressed", "untested")}


def is_all(identifier):
    return "--all-workspaces" in CASES[identifier]["argv"]


# --- 入力 -------------------------------------------------------------------------------

def requirement(identifier, title, requires=(), tests=False, supersedes=()):
    """`approved`のREQ（`MUST`の規範文1件）。(ファイルの全文, 正規化した本文)を返す。

    `tests`が`True`なら非修飾の`covers`、ワークスペースIDの文字列ならそのIDで修飾した`covers`のテスト対応を1件置く。
    """
    head = f"---\nid: {identifier}\ntitle: {title}\nstatus: approved\n"
    if requires or supersedes:
        head += "relations:\n"
        if requires:
            head += f"  requires: [{', '.join(requires)}]\n"
        if supersedes:
            head += f"  supersedes: [{', '.join(supersedes)}]\n"
    if tests:
        prefix = f"{tests}::" if isinstance(tests, str) else ""
        head += f"tests:\n  - path: tests/test_login.py\n    covers: [{prefix}{identifier}:AC-01]\n    command: frontend\n"
    body = (f"# {identifier} {title}\n\n## Intent\n\n{title}の規範を定める。\n\n## Acceptance Criteria\n\n"
            f"- [{identifier}:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {REQ_TEXT}。\n\n"
            "## Verification\n\nwebのtestで確認する。\n")
    return head + "---\n\n" + body, body


def technical(identifier, title, requires=(), refines=(), status="approved"):
    """規範文を持たないTECH（既定は`approved`）。(ファイルの全文, 正規化した本文)を返す。"""
    head = f"---\nid: {identifier}\ntitle: {title}\nstatus: {status}\n"
    if requires or refines:
        head += "relations:\n"
        if requires:
            head += f"  requires: [{', '.join(requires)}]\n"
        if refines:
            head += f"  refines: [{', '.join(refines)}]\n"
    body = f"# {identifier} {title}\n\n## Context\n\n{title}を定める。\n"
    return head + "---\n\n" + body, body


def task(identifier, title, addresses, changes):
    """状態`open`のTASK。(ファイルの全文, 正規化した本文)を返す。"""
    head = (f"---\nid: {identifier}\ntitle: {title}\nstatus: open\nrelations:\n  addresses: [{', '.join(addresses)}]\n"
            f"changes: [{', '.join(changes)}]\n")
    body = f"# {identifier} {title}\n\n## Objective\n\n{title}を実装する。\n"
    return head + "---\n\n" + body, body


def _tree(single, documents, tests=False, api_documents=None):
    """設定とテストを加えた入力。documentsは{ワークスペース相対のパス: 本文}。"""
    files = {}
    if single:
        files[".spec/bitz.yaml"] = multi_reference.member_config("root", "frontend")
        files.update(documents)
        if tests:
            files[SINGLE_TEST_PATH] = TEST_BYTES.decode()
        return files
    files[multi_reference.ROOT_CONFIG_PATH] = multi_reference.root_config(MEMBERS)
    files[multi_reference.WEB_CONFIG_PATH] = multi_reference.member_config("web", "frontend")
    files[multi_reference.API_CONFIG_PATH] = multi_reference.plain_config("api")
    files.update({f"apps/web/{path}": text for path, text in documents.items()})
    files.update({f"services/api/{path}": text for path, text in (api_documents or {}).items()})
    if tests:
        files[WEB_TEST_PATH] = TEST_BYTES.decode()
    return files


def corpus_files(corpus, single):
    """fixtureの`repo/`の入力（パス→文字列）。"""
    req_dir, tech_dir = ".spec/requirements", ".spec/technical"
    if corpus == "cycle-outside":
        # 閉包は`REQ-001`だけ。`TECH-020`と`TECH-021`は互いを`requires`する循環だが、どこからも到達できない。
        docs = {f"{req_dir}/REQ-001.md": requirement("REQ-001", REQ_TITLE)[0],
                f"{tech_dir}/TECH-020.md": technical("TECH-020", "循環の一方", ["TECH-021"])[0],
                f"{tech_dir}/TECH-021.md": technical("TECH-021", "循環の他方", ["TECH-020"])[0]}
        return _tree(single, docs)
    if corpus == "cycle-inside":
        # `REQ-001`→`TECH-010`→`TECH-011`→`TECH-010`。循環は閉包の中にある。
        docs = {f"{req_dir}/REQ-001.md": requirement("REQ-001", REQ_TITLE, ["TECH-010"], tests=True)[0],
                f"{tech_dir}/TECH-010.md": technical("TECH-010", "前提の一方", ["TECH-011"])[0],
                f"{tech_dir}/TECH-011.md": technical("TECH-011", "前提の他方", ["TECH-010"])[0]}
        return _tree(single, docs, tests=True)
    if corpus == "alias-duplicate":
        # `web::REQ-001`は`web::TECH-010`と`web::TECH-011`を非修飾で`requires`し、`web::TECH-011`は`api::TECH-020`を、
        # `api::TECH-020`は`web::TECH-010`を修飾して`requires`する。`web::TECH-010`は距離1（非修飾）と距離3（修飾）の2つの表記で到達される。
        docs = {f"{req_dir}/REQ-001.md": requirement("REQ-001", REQ_TITLE, ["TECH-010", "TECH-011"])[0],
                f"{tech_dir}/TECH-010.md": technical("TECH-010", "起点側の前提")[0],
                f"{tech_dir}/TECH-011.md": technical("TECH-011", "起点側の経路", ["api::TECH-020"])[0]}
        return _tree(False, docs, api_documents={f"{tech_dir}/TECH-020.md": technical("TECH-020", "API側の前提", ["web::TECH-010"])[0]})
    if corpus == "alias-error":
        # `web::TECH-010`には、`api::TECH-020`からの修飾した宣言（別名）だけで到達する。`TECH-010`は存在しない`TECH-999`を`requires`する。
        docs = {f"{req_dir}/REQ-001.md": requirement("REQ-001", REQ_TITLE, ["api::TECH-020"], tests=True)[0],
                f"{tech_dir}/TECH-010.md": technical("TECH-010", "起点側の前提", ["TECH-999"])[0]}
        return _tree(False, docs, tests=True,
                     api_documents={f"{tech_dir}/TECH-020.md": technical("TECH-020", "API側の前提", ["web::TECH-010"])[0]})
    if corpus == "alias-refines":
        # `api::TECH-030`が、起点の`web::REQ-001`を修飾した宣言で`refines`する（起点を所有するワークスペースの文書への別名）。
        docs = {f"{req_dir}/REQ-001.md": requirement("REQ-001", REQ_TITLE)[0]}
        return _tree(False, docs, api_documents={f"{tech_dir}/TECH-030.md": technical("TECH-030", "API側の具体化", refines=["web::REQ-001"])[0]})
    if corpus == "same-refines":
        # 起点と同じワークスペースの`web::TECH-001`が、非修飾で起点を`refines`する。
        docs = {f"{req_dir}/REQ-001.md": requirement("REQ-001", REQ_TITLE)[0],
                f"{tech_dir}/TECH-001.md": technical("TECH-001", "起点の具体化", refines=["REQ-001"])[0]}
        return _tree(False, docs)
    if corpus == "supersede":
        # `REQ-002`が`REQ-001`を（非修飾で）`supersedes`する。有効な後継は1つ。
        docs = {f"{req_dir}/REQ-001.md": requirement("REQ-001", REQ_TITLE)[0],
                f"{req_dir}/REQ-002.md": requirement("REQ-002", "後継の基準", supersedes=["REQ-001"])[0]}
        return _tree(False, docs)
    if corpus == "task-addresses":
        # `TASK-001`が、起点の規範文を自ワークスペースを修飾した`web::REQ-001:AC-01`で`addresses`する。起点はテスト対応を持つ。
        docs = {f"{req_dir}/REQ-001.md": requirement("REQ-001", REQ_TITLE, tests="web")[0],
                ".spec/tasks/TASK-001.md": task("TASK-001", "認証の実装", ["web::REQ-001:AC-01"], ["src/login.py"])[0]}
        return _tree(False, docs, tests=True)
    if corpus == "other-supersede":
        # `api::REQ-009`が、起点の`web::REQ-001`を修飾して`supersedes`する（有効な後継は他のメンバーの文書1つ）。起点はテスト対応を持つ。
        docs = {f"{req_dir}/REQ-001.md": requirement("REQ-001", REQ_TITLE, tests=True)[0]}
        return _tree(False, docs, tests=True,
                     api_documents={f"{req_dir}/REQ-009.md": requirement("REQ-009", "後継の基準", supersedes=["web::REQ-001"])[0]})
    if corpus == "other-draft-refines":
        # 状態`draft`の`api::TECH-040`が、起点の`web::REQ-001`を修飾して`refines`する。
        docs = {f"{req_dir}/REQ-001.md": requirement("REQ-001", REQ_TITLE)[0]}
        return _tree(False, docs, api_documents={
            f"{tech_dir}/TECH-040.md": technical("TECH-040", "検討中の具体化", refines=["web::REQ-001"], status="draft")[0]})
    if corpus == "other-task":
        # 状態`open`の`api::TASK-009`が、起点の規範文を`web::REQ-001:AC-01`で`addresses`する。起点はテスト対応を持つ。
        docs = {f"{req_dir}/REQ-001.md": requirement("REQ-001", REQ_TITLE, tests="web")[0]}
        return _tree(False, docs, tests=True, api_documents={
            ".spec/tasks/TASK-009.md": task("TASK-009", "APIの実装", ["web::REQ-001:AC-01"], ["src/login.py"])[0]})
    if corpus == "direct-error":
        docs = {f"{req_dir}/REQ-001.md": requirement("REQ-001", REQ_TITLE, ["TECH-010"])[0],
                f"{tech_dir}/TECH-010.md": technical("TECH-010", "起点側の前提", ["TECH-999"])[0]}
        return _tree(False, docs)
    if corpus in {"adr-proposed", "adr-qualified"}:
        inputs = {name: data.decode() for name, data in relation_type.reviewed_inputs().items()}
        if corpus == "adr-qualified":
            inputs[relation_type.TECH_PATH] = inputs[relation_type.TECH_PATH].replace("requires: [ADR-001]", "requires: [api::ADR-001]")
        return inputs
    if corpus == "adr-single":
        docs = {f"{req_dir}/REQ-001.md": requirement("REQ-001", REQ_TITLE, ["TECH-020"])[0],
                f"{tech_dir}/TECH-020.md": technical("TECH-020", "未承認の判断を前提にする方針", ["ADR-001"])[0],
                PROPOSED_ADR_PATH: PROPOSED_ADR}
        return _tree(True, docs)
    raise ValueError(f"未知の入力の種類です: {corpus}")


def reviewed_inputs(identifier):
    return {name: (text if isinstance(text, bytes) else text.encode()) for name, text in
            corpus_files(CASES[identifier]["corpus"], CASES[identifier]["single"]).items()}


def reviewed_manifest(identifier):
    case = CASES[identifier]
    status, exit_code = {"failed": ("failed", 1), "blocked": ("blocked", 2), "passed": ("passed", 0)}[case["outcome"]]
    return {
        "fixtureId": identifier,
        "description": case["description"],
        "setup": ({"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []} if case.get("commit", True)
                  else {"git": True, "operations": [{"op": "stage", "paths": ["."]}]}),
        "invocation": {"runner": "bitz", "cwd": case["cwd"], "argv": [*case["argv"], "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": RESULT_FILES[case["op"]], "reportFileCount": 0},
    }


# --- 診断（レビュー済みのリテラル） -----------------------------------------------------------------

def _source(workspace_id, path, key="relations.requires"):
    return {"kind": "file", "workspaceId": workspace_id, "path": path, "key": key}


def cycle_diagnostic(workspace_id, name):
    return {"code": "CTX-CYCLE-001", "severity": "error", "resultStatus": "failed", "summary": CYCLE_SUMMARY,
            "source": _source(workspace_id, f".spec/technical/{name}.md")}


def missing_diagnostic(workspace_id, name, evidence):
    return {"code": "SPEC-RELATION-MISSING-001", "severity": "error", "resultStatus": "failed", "summary": MISSING_SUMMARY,
            "source": _source(workspace_id, f".spec/technical/{name}.md"), "evidence": evidence}


def type_diagnostic(workspace_id, name, evidence):
    return {"code": "CTX-RELATION-TYPE-001", "severity": "error", "resultStatus": "failed",
            "summary": "TECHから状態proposedのADRへの関係型requiresは許可されません",
            "source": _source(workspace_id, f".spec/technical/{name}.md"), "evidence": evidence}


def reviewed_diagnostics(identifier):
    """失敗するfixtureの診断。cycle-insideは循環に参加する2文書、alias-errorとdirect-errorは`TECH-010`の参照切れ、adr-*は`TECH-020`の型制約。"""
    corpus, single = CASES[identifier]["corpus"], CASES[identifier]["single"]
    if corpus == "cycle-inside":
        workspace = "root" if single else "web"
        return [cycle_diagnostic(workspace, "TECH-010"), cycle_diagnostic(workspace, "TECH-011")]
    if corpus in {"alias-error", "direct-error"}:
        return [missing_diagnostic("web", "TECH-010", "TECH-999")]
    if corpus == "adr-proposed":
        return [type_diagnostic("api", "TECH-020", "ADR-001")]
    if corpus == "adr-qualified":
        return [type_diagnostic("api", "TECH-020", "api::ADR-001")]
    if corpus == "adr-single":
        return [type_diagnostic("root", "TECH-020", "ADR-001")]
    if corpus == "other-supersede":
        # 置換済みの起点の状態の診断。IDは複合ワークスペースの正規形式（修飾ID）で書く（規範が定めていない点。報告に記す）。
        return [{"code": "CTX-STATE-SUPERSEDED-001", "severity": "error", "resultStatus": "blocked",
                 "summary": "起点web::REQ-001はapi::REQ-009に置換されています",
                 "source": {"kind": "file", "workspaceId": "web", "path": ".spec/requirements/REQ-001.md"}}]
    raise ValueError("この入力に失敗の診断はありません")


def unresolved_count(identifier):
    """`resolution.unresolvedStrongRelations`。参照切れと型違反は解決できない強い関係の件数。禁止された循環は数えない（規範が定めていない点。報告に記す）。"""
    return sum(1 for item in reviewed_diagnostics(identifier) if item["code"] in {"SPEC-RELATION-MISSING-001", "CTX-RELATION-TYPE-001"})


# --- 期待結果 ---------------------------------------------------------------------------------

def revision(identifier):
    """コミットのある準備手順では`{commit, dirty}`、コミットのない準備手順（`commit=False`）では`null`（結果・診断・終了コード §2）。"""
    return {"commit": COMMIT, "dirty": False} if CASES[identifier].get("commit", True) else None


def workspace_of(identifier):
    case = CASES[identifier]
    if case["single"]:
        return {"id": "root", "path": "."}
    return {"id": "web", "path": "apps/web"}


def bucket(key=None):
    return {name: dict(EMPTY_BUCKET) for name in ("must", "should", "may")}


def failed_context_result(identifier):
    """完全解決が成立しないので、ハッシュ値を計算せず空のコンテキスト一式を返す（`MULTI-004-01`、`MULTI-027-01`と同じ形）。"""
    case = CASES[identifier]
    purpose = case["argv"][case["argv"].index("--purpose") + 1]
    resolution = {"complete": False, "documentCount": 0, "unresolvedStrongRelations": unresolved_count(identifier)}
    if not case["single"]:
        resolution.update(workspaces=[{"id": "web", "path": "apps/web"}], crossWorkspaceEdges=[])
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "failed", "purpose": purpose,
        "workspace": workspace_of(identifier), "roots": [case["root"]], "contextDigest": None,
        "revision": revision(identifier), "resolution": resolution,
        "projection": {"detail": "standard", "expanded": []},
        "documents": [], "constraintLedger": {"statements": []},
        "coverage": {**bucket(), "adjacent": []},
        "durationMs": 0, "diagnostics": reviewed_diagnostics(identifier),
    }


def failed_verify_selected_result(identifier):
    """診断は検証対象の`diagnostics`に置き、ハッシュ値、規範文、テスト割当てを持たず、テストを開始しない（`MULTI-027-02`、`SINGLE-149`と同じ形）。"""
    case = CASES[identifier]
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": case["outcome"], "scope": "selected",
        "workspace": workspace_of(identifier),
        "targetResults": [{"target": case["root"], "status": case["outcome"], "contextDigest": None, "statements": [],
                           "bindingRefs": [], "diagnostics": reviewed_diagnostics(identifier)}],
        "revision": revision(identifier), "commands": [], "durationMs": 0, "diagnostics": [],
    }


def failed_verify_all_result(identifier):
    """`platform`と`api`は検証対象がなく警告、`web`は検証対象`web::REQ-001`が失敗する（`web`の`TECH-010`と`TECH-011`は規範文もテストも持たず対象にならない）。"""
    def no_target(workspace_id, path):
        return verify_fixtures.workspace_result(workspace_id, path, "passed_with_warnings", diagnostics=[
            {**NO_TARGET, "source": {"kind": "file", "workspaceId": workspace_id, "path": ".spec/bitz.yaml"}}])

    target = verify_fixtures.target("web::REQ-001", "failed", diagnostics=reviewed_diagnostics(identifier))
    return {
        "schemaVersion": "1.0", "operation": "verify", "scope": "all-workspaces", "status": "failed",
        "multiWorkspace": {"id": "platform", "path": "."},
        "workspaces": [no_target("platform", "."), no_target("api", "services/api"),
                       verify_fixtures.workspace_result("web", "apps/web", "failed", targets=[target])],
        "revision": revision(identifier), "durationMs": 0, "diagnostics": [],
    }


def bundle_document(qualified, workspace_id, kind, role, path, reached, projection, frontmatter=None, body=None, statement_refs=()):
    """`workspaceId`は複合ワークスペースの結果だけが持つ（単一ワークスペースでは省略する。複合ワークスペース仕様 §6）。"""
    document = {"id": qualified, "kind": kind, "status": "approved", "role": role, "path": path,
                "projection": projection, "reachedBy": reached}
    if workspace_id is not None:
        document["workspaceId"] = workspace_id
    if projection == "reference":
        document["expandable"] = True
    else:
        document["statementRefs"] = list(statement_refs)
        document["frontmatter"] = frontmatter
        document["bodyText"] = body
    document["untrustedText"] = True
    return document


def passed_context_result(identifier, context_digest):
    case = CASES[identifier]
    single = case["single"]
    owner = "root" if single else "web"

    def name(local):
        return local if single else f"web::{local}"

    document_status, ledger, coverage = {}, [], None
    if case["corpus"] == "cycle-outside":
        body = requirement("REQ-001", REQ_TITLE)[1]
        documents = [bundle_document(name("REQ-001"), None if single else owner, "requirement", "root", ".spec/requirements/REQ-001.md", ["root"], "full",
                                     frontmatter={"id": name("REQ-001"), "title": REQ_TITLE, "status": "approved"}, body=body,
                                     statement_refs=[name("REQ-001:AC-01")])]
        resolution = {"complete": True, "documentCount": 1, "unresolvedStrongRelations": 0}
        detail = "standard"
        if not single:
            resolution.update(workspaces=[{"id": "web", "path": "apps/web"}], crossWorkspaceEdges=[])
    elif case["corpus"] == "alias-duplicate":
        documents = [
            bundle_document("web::REQ-001", "web", "requirement", "root", ".spec/requirements/REQ-001.md", ["root"], "reference"),
            bundle_document("web::TECH-010", "web", "technical", "constraint", ".spec/technical/TECH-010.md",
                            ["requires:api::TECH-020", "requires:web::REQ-001"], "reference"),
            bundle_document("web::TECH-011", "web", "technical", "constraint", ".spec/technical/TECH-011.md",
                            ["requires:web::REQ-001"], "reference"),
            bundle_document("api::TECH-020", "api", "technical", "constraint", ".spec/technical/TECH-020.md",
                            ["requires:web::TECH-011"], "reference"),
        ]
        resolution = {"complete": True, "documentCount": 4, "unresolvedStrongRelations": 0,
                      "workspaces": [{"id": "web", "path": "apps/web"}, {"id": "api", "path": "services/api"}],
                      "crossWorkspaceEdges": [{"relation": "requires", "source": "api::TECH-020", "target": "web::TECH-010"},
                                              {"relation": "requires", "source": "web::TECH-011", "target": "api::TECH-020"}]}
        detail = "compact"
    elif case["corpus"] == "alias-refines":
        title = "API側の具体化"
        body = technical("TECH-030", title, refines=["web::REQ-001"])[1]
        documents = [
            bundle_document("web::REQ-001", "web", "requirement", "root", ".spec/requirements/REQ-001.md", ["root"], "full",
                            frontmatter={"id": "web::REQ-001", "title": REQ_TITLE, "status": "approved"},
                            body=requirement("REQ-001", REQ_TITLE)[1], statement_refs=["web::REQ-001:AC-01"]),
            bundle_document("api::TECH-030", "api", "technical", "refinement", ".spec/technical/TECH-030.md",
                            ["refines:api::TECH-030"], "full",
                            frontmatter={"id": "api::TECH-030", "title": title, "status": "approved",
                                         "relations": {"refines": ["web::REQ-001"]}}, body=body, statement_refs=[]),
        ]
        resolution = {"complete": True, "documentCount": 2, "unresolvedStrongRelations": 0,
                      "workspaces": [{"id": "web", "path": "apps/web"}, {"id": "api", "path": "services/api"}],
                      "crossWorkspaceEdges": [{"relation": "refines", "source": "api::TECH-030", "target": "web::REQ-001"}]}
        detail = "standard"
    elif case["corpus"] == "same-refines":
        documents = [
            bundle_document("web::REQ-001", "web", "requirement", "root", ".spec/requirements/REQ-001.md", ["root"], "reference"),
            bundle_document("web::TECH-001", "web", "technical", "refinement", ".spec/technical/TECH-001.md",
                            ["refines:web::TECH-001"], "reference"),
        ]
        resolution = {"complete": True, "documentCount": 2, "unresolvedStrongRelations": 0,
                      "workspaces": [{"id": "web", "path": "apps/web"}], "crossWorkspaceEdges": []}
        detail = "compact"
    elif case["corpus"] == "supersede":
        # 置換済みの起点は役割`advisory`、後継は役割`replacement`（関係・トレースモデル §6.1の5.）。後継へ起点を差し替えない。
        documents = [
            bundle_document("web::REQ-001", "web", "requirement", "advisory", ".spec/requirements/REQ-001.md", ["root"], "reference"),
            bundle_document("web::REQ-002", "web", "requirement", "replacement", ".spec/requirements/REQ-002.md",
                            ["supersedes:web::REQ-002"], "reference"),
        ]
        resolution = {"complete": True, "documentCount": 2, "unresolvedStrongRelations": 0,
                      "workspaces": [{"id": "web", "path": "apps/web"}], "crossWorkspaceEdges": []}
        detail = "compact"
    elif case["corpus"] == "task-addresses":
        task_body = task("TASK-001", "認証の実装", ["web::REQ-001:AC-01"], ["src/login.py"])[1]
        documents = [
            bundle_document("web::REQ-001", "web", "requirement", "root", ".spec/requirements/REQ-001.md", ["root"], "full",
                            frontmatter={"id": "web::REQ-001", "title": REQ_TITLE, "status": "approved",
                                         "tests": [{"path": "tests/test_login.py", "covers": ["web::REQ-001:AC-01"], "command": "frontend"}]},
                            body=requirement("REQ-001", REQ_TITLE, tests="web")[1], statement_refs=["web::REQ-001:AC-01"]),
            bundle_document("web::TASK-001", "web", "task", "work", ".spec/tasks/TASK-001.md", ["addresses:web::TASK-001"], "full",
                            frontmatter={"id": "web::TASK-001", "title": "認証の実装", "status": "open",
                                         "relations": {"addresses": ["web::REQ-001:AC-01"]}, "changes": ["src/login.py"]},
                            body=task_body, statement_refs=[]),
        ]
        document_status["web::TASK-001"] = "open"
        resolution = {"complete": True, "documentCount": 2, "unresolvedStrongRelations": 0,
                      "workspaces": [{"id": "web", "path": "apps/web"}], "crossWorkspaceEdges": []}
        detail = "standard"
        # 目的`implement`の対象規範文は起点の規範文1件。状態`open`のTASKが対応済みにし、テスト対応が宣言されているので、警告はない。
        ledger = [{"id": "web::REQ-001:AC-01", "documentId": "web::REQ-001", "documentRole": "root", "modality": "MUST",
                   "reason": None, "actor": "TargetSystem", "activation": {"kind": "ALWAYS"},
                   "operation": {"kind": "CONSTRAINT", "text": REQ_TEXT}}]
        total = ["web::REQ-001:AC-01"]
        coverage = {"must": {"total": total, "addressed": total, "tested": total, "unaddressed": [], "untested": []},
                    "should": dict(EMPTY_BUCKET), "may": dict(EMPTY_BUCKET), "adjacent": []}
    elif case["corpus"] == "other-supersede":
        documents = [
            bundle_document("web::REQ-001", "web", "requirement", "advisory", ".spec/requirements/REQ-001.md", ["root"], "reference"),
            bundle_document("api::REQ-009", "api", "requirement", "replacement", ".spec/requirements/REQ-009.md",
                            ["supersedes:api::REQ-009"], "reference"),
        ]
        resolution = {"complete": True, "documentCount": 2, "unresolvedStrongRelations": 0,
                      "workspaces": [{"id": "web", "path": "apps/web"}, {"id": "api", "path": "services/api"}],
                      "crossWorkspaceEdges": [{"relation": "supersedes", "source": "api::REQ-009", "target": "web::REQ-001"}]}
        detail = "compact"
    elif case["corpus"] == "other-draft-refines":
        title = "検討中の具体化"
        documents = [
            bundle_document("web::REQ-001", "web", "requirement", "root", ".spec/requirements/REQ-001.md", ["root"], "full",
                            frontmatter={"id": "web::REQ-001", "title": REQ_TITLE, "status": "approved"},
                            body=requirement("REQ-001", REQ_TITLE)[1], statement_refs=["web::REQ-001:AC-01"]),
            # 状態`draft`の文書は規範として適用しないので、役割`advisory`・提示形式`reference`で示す（関係・トレースモデル §6.1の6.）。
            bundle_document("api::TECH-040", "api", "technical", "advisory", ".spec/technical/TECH-040.md",
                            ["refines:api::TECH-040"], "reference"),
        ]
        document_status["api::TECH-040"] = "draft"
        resolution = {"complete": True, "documentCount": 2, "unresolvedStrongRelations": 0,
                      "workspaces": [{"id": "web", "path": "apps/web"}, {"id": "api", "path": "services/api"}],
                      "crossWorkspaceEdges": [{"relation": "refines", "source": "api::TECH-040", "target": "web::REQ-001"}]}
        detail = "standard"
    elif case["corpus"] == "other-task":
        task_body = task("TASK-009", "APIの実装", ["web::REQ-001:AC-01"], ["src/login.py"])[1]
        documents = [
            bundle_document("web::REQ-001", "web", "requirement", "root", ".spec/requirements/REQ-001.md", ["root"], "full",
                            frontmatter={"id": "web::REQ-001", "title": REQ_TITLE, "status": "approved",
                                         "tests": [{"path": "tests/test_login.py", "covers": ["web::REQ-001:AC-01"], "command": "frontend"}]},
                            body=requirement("REQ-001", REQ_TITLE, tests="web")[1], statement_refs=["web::REQ-001:AC-01"]),
            bundle_document("api::TASK-009", "api", "task", "work", ".spec/tasks/TASK-009.md", ["addresses:api::TASK-009"], "full",
                            frontmatter={"id": "api::TASK-009", "title": "APIの実装", "status": "open",
                                         "relations": {"addresses": ["web::REQ-001:AC-01"]}, "changes": ["src/login.py"]},
                            body=task_body, statement_refs=[]),
        ]
        document_status["api::TASK-009"] = "open"
        resolution = {"complete": True, "documentCount": 2, "unresolvedStrongRelations": 0,
                      "workspaces": [{"id": "web", "path": "apps/web"}, {"id": "api", "path": "services/api"}],
                      "crossWorkspaceEdges": [{"relation": "addresses", "source": "api::TASK-009", "target": "web::REQ-001:AC-01"}]}
        detail = "standard"
        ledger = [{"id": "web::REQ-001:AC-01", "documentId": "web::REQ-001", "documentRole": "root", "modality": "MUST",
                   "reason": None, "actor": "TargetSystem", "activation": {"kind": "ALWAYS"},
                   "operation": {"kind": "CONSTRAINT", "text": REQ_TEXT}}]
        total = ["web::REQ-001:AC-01"]
        coverage = {"must": {"total": total, "addressed": total, "tested": total, "unaddressed": [], "untested": []},
                    "should": dict(EMPTY_BUCKET), "may": dict(EMPTY_BUCKET), "adjacent": []}
    else:
        raise ValueError("この入力に成功のコンテキストはありません")
    for document in documents:
        document["status"] = document_status.get(document["id"], "approved")
    purpose = case["argv"][case["argv"].index("--purpose") + 1]
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "passed", "purpose": purpose,
        "workspace": workspace_of(identifier), "roots": [case["root"]], "contextDigest": context_digest,
        "revision": revision(identifier), "resolution": resolution,
        "projection": {"detail": detail, "expanded": []},
        "documents": documents,
        # 目的`interpret`は対象規範文を持たない（関係・トレースモデル §6.4）ので、制約台帳とカバレッジは空である。
        "constraintLedger": {"statements": ledger}, "coverage": coverage if coverage is not None else {**bucket(), "adjacent": []},
        "durationMs": 0, "diagnostics": [],
    }


# --- ハッシュ値の参照計算A（リテラル） ---------------------------------------------------------------

def _material_request(single, workspaces, documents, cross_edges, root, purpose="interpret"):
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": purpose, "requestWorkspaceId": workspaces[0][0], "roots": [root],
        "workspaces": [{"id": workspace_id, "path": path} for workspace_id, path in workspaces],
        "documents": sorted(documents, key=lambda item: item["id"]),
        "crossWorkspaceEdges": cross_edges,
        "settings": {"workspaces": [{"id": workspace_id, "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}
                                    for workspace_id, _ in sorted(workspaces)],
                     "context": {"maxDocuments": 20, "maxBytes": 131072}, "verifyTimeouts": [], "commands": []},
    }


def reviewed_digest_input(identifier):
    """目的`interpret`のレビュー済みのハッシュ値の材料（参照計算A）。到達ワークスペースの文書だけを置き、同じ文書を二重に含めない。"""
    case = CASES[identifier]
    technical_document = verify_fixtures.document_material
    if case["corpus"] == "cycle-outside":
        single = case["single"]
        owner, path = ("root", ".") if single else ("web", "apps/web")
        prefix = "" if single else "web::"
        document = technical_document(None, f"{prefix}REQ-001", owner, "requirement", REQ_TITLE, requirement("REQ-001", REQ_TITLE)[1],
                                      statements=[verify_fixtures.statement_material(f"{prefix}REQ-001:AC-01", REQ_TEXT)])
        return _material_request(single, [(owner, path)], [document], [], f"{prefix}REQ-001")
    if case["corpus"] == "alias-duplicate":
        request = technical_document(None, "web::REQ-001", "web", "requirement", REQ_TITLE,
                                     requirement("REQ-001", REQ_TITLE, ["TECH-010", "TECH-011"])[1],
                                     relations={"requires": ["web::TECH-010", "web::TECH-011"]},
                                     statements=[verify_fixtures.statement_material("web::REQ-001:AC-01", REQ_TEXT)])
        own = technical_document(None, "web::TECH-010", "web", "technical", "起点側の前提", technical("TECH-010", "起点側の前提")[1])
        path = technical_document(None, "web::TECH-011", "web", "technical", "起点側の経路",
                                  technical("TECH-011", "起点側の経路", ["api::TECH-020"])[1],
                                  relations={"requires": ["api::TECH-020"]})
        other = technical_document(None, "api::TECH-020", "api", "technical", "API側の前提",
                                   technical("TECH-020", "API側の前提", ["web::TECH-010"])[1],
                                   relations={"requires": ["web::TECH-010"]})
        edges = [{"relation": "requires", "source": "api::TECH-020", "target": "web::TECH-010"},
                 {"relation": "requires", "source": "web::TECH-011", "target": "api::TECH-020"}]
        return _material_request(False, [("web", "apps/web"), ("api", "services/api")], [request, own, path, other], edges, "web::REQ-001")
    if case["corpus"] == "alias-refines":
        request = technical_document(None, "web::REQ-001", "web", "requirement", REQ_TITLE, requirement("REQ-001", REQ_TITLE)[1],
                                     statements=[verify_fixtures.statement_material("web::REQ-001:AC-01", REQ_TEXT)])
        refiner = technical_document(None, "api::TECH-030", "api", "technical", "API側の具体化",
                                     technical("TECH-030", "API側の具体化", refines=["web::REQ-001"])[1],
                                     relations={"refines": ["web::REQ-001"]})
        edges = [{"relation": "refines", "source": "api::TECH-030", "target": "web::REQ-001"}]
        return _material_request(False, [("web", "apps/web"), ("api", "services/api")], [request, refiner], edges, "web::REQ-001")
    if case["corpus"] == "same-refines":
        request = technical_document(None, "web::REQ-001", "web", "requirement", REQ_TITLE, requirement("REQ-001", REQ_TITLE)[1],
                                     statements=[verify_fixtures.statement_material("web::REQ-001:AC-01", REQ_TEXT)])
        refiner = technical_document(None, "web::TECH-001", "web", "technical", "起点の具体化",
                                     technical("TECH-001", "起点の具体化", refines=["REQ-001"])[1],
                                     relations={"refines": ["web::REQ-001"]})
        return _material_request(False, [("web", "apps/web")], [request, refiner], [], "web::REQ-001")
    if case["corpus"] == "supersede":
        # 置換済みの起点の適用可能性は`advisory`、後継は`replacement`（正規化仕様 §3）。
        old = technical_document(None, "web::REQ-001", "web", "requirement", REQ_TITLE, requirement("REQ-001", REQ_TITLE)[1],
                                 statements=[verify_fixtures.statement_material("web::REQ-001:AC-01", REQ_TEXT)])
        new = technical_document(None, "web::REQ-002", "web", "requirement", "後継の基準",
                                 requirement("REQ-002", "後継の基準", supersedes=["REQ-001"])[1],
                                 relations={"supersedes": ["web::REQ-001"]},
                                 statements=[verify_fixtures.statement_material("web::REQ-002:AC-01", REQ_TEXT)])
        old["applicability"], new["applicability"] = "advisory", "replacement"
        return _material_request(False, [("web", "apps/web")], [old, new], [], "web::REQ-001")
    if case["corpus"] == "task-addresses":
        # 目的`implement`は、テスト割当てのコマンドを材料に含めない（`verifyTimeouts`と`commands`は空）。
        request = technical_document(None, "web::REQ-001", "web", "requirement", REQ_TITLE,
                                     requirement("REQ-001", REQ_TITLE, tests="web")[1],
                                     tests=[("tests/test_login.py", "web::REQ-001:AC-01", "frontend")],
                                     statements=[verify_fixtures.statement_material("web::REQ-001:AC-01", REQ_TEXT)])
        work = technical_document(None, "web::TASK-001", "web", "task", "認証の実装",
                                  task("TASK-001", "認証の実装", ["web::REQ-001:AC-01"], ["src/login.py"])[1],
                                  relations={"addresses": ["web::REQ-001:AC-01"]})
        work["status"] = work["frontmatter"]["status"] = "open"
        work["frontmatter"]["changes"] = ["src/login.py"]
        return _material_request(False, [("web", "apps/web")], [request, work], [], "web::REQ-001", purpose="implement")
    if case["corpus"] == "other-supersede":
        old = technical_document(None, "web::REQ-001", "web", "requirement", REQ_TITLE, requirement("REQ-001", REQ_TITLE, tests=True)[1],
                                 tests=[("tests/test_login.py", "web::REQ-001:AC-01", "frontend")],
                                 statements=[verify_fixtures.statement_material("web::REQ-001:AC-01", REQ_TEXT)])
        new = technical_document(None, "api::REQ-009", "api", "requirement", "後継の基準",
                                 requirement("REQ-009", "後継の基準", supersedes=["web::REQ-001"])[1],
                                 relations={"supersedes": ["web::REQ-001"]},
                                 statements=[verify_fixtures.statement_material("api::REQ-009:AC-01", REQ_TEXT)])
        old["applicability"], new["applicability"] = "advisory", "replacement"
        edges = [{"relation": "supersedes", "source": "api::REQ-009", "target": "web::REQ-001"}]
        return _material_request(False, [("web", "apps/web"), ("api", "services/api")], [old, new], edges, "web::REQ-001")
    if case["corpus"] == "other-draft-refines":
        request = technical_document(None, "web::REQ-001", "web", "requirement", REQ_TITLE, requirement("REQ-001", REQ_TITLE)[1],
                                     statements=[verify_fixtures.statement_material("web::REQ-001:AC-01", REQ_TEXT)])
        draft = technical_document(None, "api::TECH-040", "api", "technical", "検討中の具体化",
                                   technical("TECH-040", "検討中の具体化", refines=["web::REQ-001"], status="draft")[1],
                                   relations={"refines": ["web::REQ-001"]})
        draft["status"] = draft["frontmatter"]["status"] = "draft"
        draft["applicability"] = "advisory"
        edges = [{"relation": "refines", "source": "api::TECH-040", "target": "web::REQ-001"}]
        return _material_request(False, [("web", "apps/web"), ("api", "services/api")], [request, draft], edges, "web::REQ-001")
    if case["corpus"] == "other-task":
        request = technical_document(None, "web::REQ-001", "web", "requirement", REQ_TITLE,
                                     requirement("REQ-001", REQ_TITLE, tests="web")[1],
                                     tests=[("tests/test_login.py", "web::REQ-001:AC-01", "frontend")],
                                     statements=[verify_fixtures.statement_material("web::REQ-001:AC-01", REQ_TEXT)])
        work = technical_document(None, "api::TASK-009", "api", "task", "APIの実装",
                                  task("TASK-009", "APIの実装", ["web::REQ-001:AC-01"], ["src/login.py"])[1],
                                  relations={"addresses": ["web::REQ-001:AC-01"]})
        work["status"] = work["frontmatter"]["status"] = "open"
        work["frontmatter"]["changes"] = ["src/login.py"]
        edges = [{"relation": "addresses", "source": "api::TASK-009", "target": "web::REQ-001:AC-01"}]
        return _material_request(False, [("web", "apps/web"), ("api", "services/api")], [request, work], edges, "web::REQ-001",
                                 purpose="implement")
    raise ValueError("この入力にハッシュ値の材料はありません")


def reference_digest(identifier, repository):
    """独立に書いた2系統の参照計算のバイト列の一致を要求し、ハッシュ値を返す。"""
    case = CASES[identifier]
    literal = digest_reference.canonical_bytes(reviewed_digest_input(identifier))
    purpose = case["argv"][case["argv"].index("--purpose") + 1]
    if case["corpus"] in {"same-refines", "supersede", "task-addresses", "other-supersede", "other-draft-refines", "other-task"}:
        derived = multi_crosscheck.canonical_bytes(derived_material(repository, case["root"], purpose))
    elif case["single"]:
        derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository, case["root"], "interpret", workspace_id="root"))
    else:
        derived = multi_crosscheck.canonical_bytes(multi_crosscheck.build(repository, case["root"], "interpret"))
    if literal != derived:
        raise ValueError("参照計算AとBの正規JSONが一致しません")
    return digest_reference.digest(literal)


def expected_digest(identifier):
    """生成と監査が使う、リテラルの参照計算Aのハッシュ値。"""
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


def reviewed_result(identifier):
    case = CASES[identifier]
    if case["outcome"] == "passed":
        return passed_context_result(identifier, expected_digest(identifier))
    if case["op"] == "context":
        return failed_context_result(identifier)
    return failed_verify_all_result(identifier) if is_all(identifier) else failed_verify_selected_result(identifier)


# --- 参照計算（入力の木構造から導く） -----------------------------------------------------------------

def load_tree(repository):
    """(単一か, ルートワークスペースのID, ワークスペース, 文書)。文書のキーは`<ワークスペース>::<ID>`、単一ワークスペースはIDが`root`。"""
    config = read_yaml((repository / ".spec/bitz.yaml").read_text(encoding="utf-8"))
    single = "multiWorkspace" not in config
    root_id = config["workspace"]["id"]
    members = [] if single else multi_crosscheck.catalog(repository)[1]
    workspaces, documents = {}, {}
    for workspace_id, path in [(root_id, ".")] + members:
        root = repository if path == "." else repository / path
        workspaces[workspace_id] = {"path": path, "config": read_yaml((root / ".spec/bitz.yaml").read_text(encoding="utf-8"))}
        for directory, kind in KIND_BY_DIRECTORY.items():
            folder = root / ".spec" / directory
            if not folder.is_dir():
                continue
            for file in sorted(folder.glob("*.md")):
                frontmatter, raw = split_document(file.read_text(encoding="utf-8"))
                documents[f"{workspace_id}::{frontmatter['id']}"] = {
                    "workspaceId": workspace_id, "kind": kind, "frontmatter": frontmatter,
                    "body": normalize_body(raw), "path": file.relative_to(root).as_posix()}
    return single, root_id, workspaces, documents


def derived_material(repository, root, purpose):
    """入力の木構造から導くハッシュ値の材料（参照計算B）。`multi_crosscheck.build`と同じ材料を、置換・TASKを含む閉包と適用可能性で組み立てる。
    目的`interpret`と`implement`は、コマンドとタイムアウトを材料に含めない（正規化仕様 §3）。"""
    _, _, workspaces, documents = load_tree(repository)
    order, edges, _ = interpret_closure(documents, root, purpose)
    request = root.partition("::")[0]
    reached = {documents[name]["workspaceId"] for name in order}
    limits = workspaces[request]["config"].get("context", {})
    payload = {
        "digestVersion": "1.0", "specSchemaVersion": workspaces[request]["config"]["schemaVersion"],
        "earsAiVersion": workspaces[request]["config"]["earsAi"], "resolverVersion": "1.0", "purpose": purpose,
        "requestWorkspaceId": request, "roots": [root],
        "workspaces": [{"id": name, "path": workspaces[name]["path"]} for name in [request, *sorted(reached - {request})]],
        "documents": [], "crossWorkspaceEdges": [],
        "settings": {"workspaces": [{"id": name, "schemaVersion": workspaces[name]["config"]["schemaVersion"],
                                     "earsAi": workspaces[name]["config"]["earsAi"], "language": workspaces[name]["config"]["language"]}
                                    for name in sorted(reached)],
                     "context": {"maxDocuments": int(limits.get("maxDocuments", 20)), "maxBytes": int(limits.get("maxBytes", 131072))},
                     "verifyTimeouts": [], "commands": []},
    }
    cross = set()
    for name in order:
        document = documents[name]
        declared = multi_crosscheck.relations(document)
        role = role_of(documents, root, name, edges)
        for relation in digest_crosscheck.RELATION_KEYS:
            cross |= {(name, relation, target) for target in declared[relation] if target.partition("::")[0] != document["workspaceId"]}
        payload["documents"].append({
            "id": name, "workspaceId": document["workspaceId"], "kind": document["kind"],
            "status": document["frontmatter"]["status"],
            "applicability": role if role in {"advisory", "replacement"} else "applicable",
            "frontmatter": {
                "id": name, "title": document["frontmatter"]["title"], "status": document["frontmatter"]["status"],
                "relations": declared, "implements": multi_crosscheck.paths(document["frontmatter"].get("implements", [])),
                "tests": multi_crosscheck.tests(document), "verify": document["frontmatter"].get("verify"),
                "changes": multi_crosscheck.paths(document["frontmatter"].get("changes", []))},
            "bodyText": document["body"],
            "statements": sorted((digest_crosscheck._sorted_extensions(dict(item, id=f"{document['workspaceId']}::{item['id']}"))
                                  for item in read_statements(document["body"])), key=lambda item: item["id"]),
            "strongRelations": [{"relation": relation, "target": target} for relation, target in
                                sorted({(relation, target) for relation in digest_crosscheck.STRONG for target in declared[relation]})],
        })
    payload["documents"].sort(key=lambda item: item["id"])
    payload["crossWorkspaceEdges"] = [{"relation": relation, "source": source, "target": target} for source, relation, target in sorted(cross)]
    return digest_crosscheck.normalize_strings(payload)


def edges_of(documents, identifier, relation):
    """文書1件の`relation`のエッジ: (宣言どおりの参照, 修飾した参照先の文書ID, 参照先が存在するか)。"""
    document = documents[identifier]
    result = []
    for text in document["frontmatter"].get("relations", {}).get(relation, []):
        target = multi_crosscheck.owner(multi_crosscheck.qualify(document["workspaceId"], text))
        result.append((text, target, target in documents))
    return result


def reachable(documents, start, relations=("requires", "refines")):
    """`start`から強い関係（循環の対象の関係型）を辿って到達できる文書の集合（`start`自身は循環で戻るときだけ含む）。"""
    seen, frontier = set(), [start]
    while frontier:
        current = frontier.pop()
        for relation in relations:
            for _, target, exists in edges_of(documents, current, relation):
                if exists and target not in seen:
                    seen.add(target)
                    frontier.append(target)
    return seen


def cyclic_edges(documents):
    """禁止された循環に参加するエッジの(宣言元の文書, 関係型)。エッジ`u→v`は、`v`から`u`へ到達できる（自己参照を含む）とき循環に参加する（関係・トレースモデル §4）。"""
    pairs = set()
    for identifier in documents:
        for relation in ("requires", "refines"):
            for _, target, exists in edges_of(documents, identifier, relation):
                if exists and (target == identifier or identifier in reachable(documents, target)):
                    pairs.add((identifier, relation))
    return pairs


def statement_ids(documents, identifier):
    document = documents[identifier]
    return [f"{document['workspaceId']}::{item['id']}" for item in read_statements(document["body"])]


def interpret_closure(documents, root, purpose="interpret"):
    """目的`interpret`の閉包（関係・トレースモデル §6.1）。起点から`requires`を終端まで辿り、起点を所有する文書またはその規範文を`refines`する
    適用可能な文書を逆参照で（推移的に）含めて、含めた文書の`requires`を辿る。置換済みの起点（有効な後継が1つ）は後継を距離1で含める。
    目的`implement`は、起点と具体化文書の規範文を`addresses`する状態`open`のTASKを距離1で加える（同 §6.2）。

    戻り値は(幅優先の順の文書, 文書→到達したエッジ{(関係型, 宣言した文書)}, 文書→起点からの最短の段数)。同じ文書が複数の経路や複数の表記で
    到達しても1回だけ収録する（同 §7）。このcorpusは、状態`draft`の文書、置換、TASKを使わない。
    """
    edges, distance, order = {root: set()}, {root: 0}, [root]

    def follow_requires(start):
        frontier = [start]
        while frontier:
            current = frontier.pop(0)
            for _, target, exists in edges_of(documents, current, "requires"):
                if not exists:
                    continue
                edges.setdefault(target, set()).add(("requires", current))
                if target not in distance:
                    distance[target] = distance[current] + 1
                    order.append(target)
                    frontier.append(target)

    follow_requires(root)
    refined, refiners = [root], []
    while refined:
        target = refined.pop(0)
        mine = {target, *statement_ids(documents, target)}
        for candidate in sorted(documents):
            if candidate in distance or documents[candidate]["frontmatter"]["status"] != "approved":
                continue
            if documents[candidate]["kind"] not in {"requirement", "technical"}:
                continue
            declared = {multi_crosscheck.qualify(documents[candidate]["workspaceId"], text)
                        for text in documents[candidate]["frontmatter"].get("relations", {}).get("refines", [])}
            if declared & mine:
                edges.setdefault(candidate, set()).add(("refines", candidate))
                distance[candidate] = distance[target] + 1
                order.append(candidate)
                refined.append(candidate)
                refiners.append(candidate)
    for refiner in refiners:
        follow_requires(refiner)
    if purpose == "interpret":
        # 閉包内の文書（またはその規範文）を`refines`する状態`draft`の文書は役割`advisory`として含め、その`requires`と具体化する文書は辿らない（§6.1の6.）。
        context = list(order)
        for name in context:
            mine = {name, *statement_ids(documents, name)}
            for candidate in sorted(documents):
                document = documents[candidate]
                if candidate in distance or document["kind"] not in {"requirement", "technical"} or document["frontmatter"]["status"] != "draft":
                    continue
                declared = {multi_crosscheck.qualify(document["workspaceId"], text)
                            for text in document["frontmatter"].get("relations", {}).get("refines", [])}
                if declared & mine:
                    edges.setdefault(candidate, set()).add(("refines", candidate))
                    distance[candidate] = distance[name] + 1
                    order.append(candidate)
        successor = successors_of(documents, root)
        if len(successor) > 1:
            raise ValueError("このcorpusは有効な後継が複数の入力を扱いません")
        for name in successor:
            edges.setdefault(name, set()).add(("supersedes", name))
            distance[name] = 1
            order.append(name)
    elif purpose == "implement":
        targets = {item for name in [root, *refiners] for item in statement_ids(documents, name)}
        for name in sorted(documents):
            document = documents[name]
            declared = {multi_crosscheck.qualify(document["workspaceId"], text)
                        for text in document["frontmatter"].get("relations", {}).get("addresses", [])}
            if document["kind"] == "task" and document["frontmatter"]["status"] == "open" and declared & targets:
                edges.setdefault(name, set()).add(("addresses", name))
                distance[name] = 1
                order.append(name)
    return order, edges, distance


def successors_of(documents, root):
    """`root`を`supersedes`する、同じ種別の適用可能（`approved`）な文書。"""
    return sorted(name for name, document in documents.items()
                  if document["kind"] == documents[root]["kind"] and document["frontmatter"]["status"] == "approved"
                  and root in {multi_crosscheck.owner(multi_crosscheck.qualify(document["workspaceId"], text))
                               for text in document["frontmatter"].get("relations", {}).get("supersedes", [])})


def diagnostic_key(item):
    return (item["source"]["workspaceId"], item["source"]["path"], item["code"], item.get("evidence", ""))


DIRECTORY_BY_KIND = {"requirement": "requirements", "technical": "technical", "decision": "decisions", "task": "tasks"}


def reference_diagnostics(documents, closure):
    """閉包の文書が宣言するエッジのうち、診断になるものを導く。循環に参加するエッジ、存在しない参照先、承認されていないADRへの`requires`。

    診断の発生元は関係を宣言した文書、`evidence`（循環を除く）は宣言どおりの参照先である（結果・診断・終了コード §4）。
    """
    cyclic = cyclic_edges(documents)
    found = []
    for identifier in closure:
        document = documents[identifier]
        path = f".spec/{DIRECTORY_BY_KIND[document['kind']]}/{document['frontmatter']['id']}.md"
        source = {"kind": "file", "workspaceId": document["workspaceId"], "path": path, "key": "relations.requires"}
        for pair in sorted(cyclic):
            if pair[0] == identifier:
                found.append({"code": "CTX-CYCLE-001", "severity": "error", "resultStatus": "failed",
                              "summary": f"関係型{pair[1]}に禁止された循環があります", "source": dict(source, key=f"relations.{pair[1]}")})
        for text, target, exists in edges_of(documents, identifier, "requires"):
            if not exists:
                found.append({"code": "SPEC-RELATION-MISSING-001", "severity": "error", "resultStatus": "failed",
                              "summary": MISSING_SUMMARY, "source": dict(source), "evidence": text})
            elif documents[target]["kind"] == "decision" and documents[target]["frontmatter"]["status"] != "accepted":
                found.append({"code": "CTX-RELATION-TYPE-001", "severity": "error", "resultStatus": "failed",
                              "summary": relation_type.type_summary(document["kind"], documents[target]),
                              "source": dict(source), "evidence": text})
    return sorted(found, key=diagnostic_key)


def role_of(documents, root, identifier, edges):
    """役割（関係・トレースモデル §7の表。上から最初に該当するもの）。"""
    kinds = {relation for relation, _ in edges[identifier]}
    if identifier == root:
        return "advisory" if successors_of(documents, root) else "root"
    if documents[identifier]["frontmatter"]["status"] == "draft":
        return "advisory"
    if "supersedes" in kinds:
        return "replacement"
    if documents[identifier]["kind"] == "task":
        return "work"
    if "refines" in kinds:
        return "refinement"
    return "requirement" if documents[identifier]["kind"] == "requirement" else "constraint"


def reference_state_diagnostics(documents, root):
    """目的`verify`の起点が置換済み（有効な後継が1つ）なら`CTX-STATE-SUPERSEDED-001`（`blocked`。関係・トレースモデル §10、診断レジストリ）。"""
    successors = successors_of(documents, root)
    if len(successors) != 1:
        return []
    document = documents[root]
    return [{"code": "CTX-STATE-SUPERSEDED-001", "severity": "error", "resultStatus": "blocked",
             "summary": f"起点{root}は{successors[0]}に置換されています",
             "source": {"kind": "file", "workspaceId": document["workspaceId"],
                        "path": f".spec/{DIRECTORY_BY_KIND[document['kind']]}/{document['frontmatter']['id']}.md"}}]


def reference_context(documents, workspaces, request, root, purpose="interpret"):
    """成功するコンテキストの文書・到達ワークスペース・横断するエッジ。"""
    order, edges, distance = interpret_closure(documents, root, purpose)
    ranked = sorted(order, key=lambda item: (distance[item], KIND_RANK[documents[item]["kind"]], item))
    entries = []
    for identifier in ranked:
        document = documents[identifier]
        role = role_of(documents, root, identifier, edges)
        reached = ["root"] if identifier == root else sorted(f"{relation}:{source}" for relation, source in edges[identifier])
        entries.append({"id": identifier, "workspaceId": document["workspaceId"], "kind": document["kind"], "role": role,
                        "path": document["path"], "reachedBy": reached, "statementRefs": statement_ids(documents, identifier)})
    reached_workspaces = {documents[item]["workspaceId"] for item in order}
    # 横断するエッジは、閉包の文書が宣言する強い関係のうち、参照先が別のワークスペースのもの（複合ワークスペース仕様 §6）。
    cross = sorted((identifier, relation, multi_crosscheck.qualify(documents[identifier]["workspaceId"], text))
                   for identifier in order for relation in ("requires", "refines", "addresses", "supersedes")
                   for text in documents[identifier]["frontmatter"].get("relations", {}).get(relation, [])
                   if multi_crosscheck.qualify(documents[identifier]["workspaceId"], text).partition("::")[0]
                   != documents[identifier]["workspaceId"])
    return {"documents": entries,
            "workspaces": [{"id": request, "path": workspaces[request]["path"]}] + [
                {"id": item, "path": workspaces[item]["path"]} for item in sorted(reached_workspaces - {request})],
            "edges": [{"relation": relation, "source": source, "target": target} for source, relation, target in cross]}


def spellings(documents, target):
    """`target`の文書を指す宣言の文字列（`requires`）の集合。同じ文書を表す、修飾した表記と修飾していない表記を区別する。"""
    return {text for identifier in documents for text, resolved, _ in edges_of(documents, identifier, "requires") if resolved == target}


def unqualified(identifier):
    return identifier.partition("::")[2]


def check_against_reference(identifier, repository, result):
    """リテラルの期待値が、入力から導いた閉包・診断・ハッシュ値と一致することを要求する。"""
    case = CASES[identifier]
    single, root_id, workspaces, documents = load_tree(repository)
    if single != case["single"]:
        raise ValueError("単一ワークスペースか複合ワークスペースかが入力と異なります")
    root = f"{root_id}::{case['root']}" if single else case["root"]
    request = root_id if single else case["root"].partition("::")[0]
    purpose = case["argv"][case["argv"].index("--purpose") + 1] if "--purpose" in case["argv"] else "interpret"
    order, _, _ = interpret_closure(documents, root, purpose)
    diagnostics = reference_diagnostics(documents, order)
    if is_all(identifier):
        if [item["id"] for item in result["workspaces"]] != ["platform", "api", "web"]:
            raise ValueError("全体の`verify`のワークスペースの順が異なります")
        actual = result["workspaces"][2]["targetResults"][0]["diagnostics"]
    elif case["op"] == "verify":
        actual = result["targetResults"][0]["diagnostics"]
    else:
        actual = result["diagnostics"]
    if case["outcome"] == "blocked":
        if actual != reference_state_diagnostics(documents, root) or diagnostics or not actual:
            raise ValueError("状態の診断が入力からの参照計算と異なります")
        if result["targetResults"][0]["status"] != "blocked" or result["status"] != "blocked":
            raise ValueError("状態が置換済みの起点の`blocked`と異なります")
        return
    if case["outcome"] == "failed":
        if actual != diagnostics:
            raise ValueError("診断が入力からの参照計算と異なります")
        if case["op"] == "context":
            counted = sum(1 for item in diagnostics if item["code"] in {"SPEC-RELATION-MISSING-001", "CTX-RELATION-TYPE-001"})
            if result["resolution"]["unresolvedStrongRelations"] != counted:
                raise ValueError("`unresolvedStrongRelations`が入力からの参照計算と異なります")
        return
    if diagnostics or actual != []:
        raise ValueError("成功するfixtureは診断を持ちません")
    expected = reference_context(documents, workspaces, request, root, purpose)
    if result["resolution"]["documentCount"] != len(expected["documents"]) or len(result["documents"]) != len(expected["documents"]):
        raise ValueError("文書数が入力からの参照計算と異なります")
    if len({item["id"] for item in result["documents"]}) != len(result["documents"]):
        raise ValueError("同じ文書を二重に収録してはいけません")
    compact = result["projection"]["detail"] == "compact"
    for shown, wanted in zip(result["documents"], expected["documents"]):
        # 単一ワークスペースは修飾しない表現（`workspaceId`も持たない）で返す。
        view = {"id": shown["id"], "kind": shown["kind"], "role": shown["role"], "path": shown["path"], "reachedBy": shown["reachedBy"]}
        if shown["status"] != documents[wanted["id"]]["frontmatter"]["status"]:
            raise ValueError("文書の状態が入力と異なります")
        reference = {"id": unqualified(wanted["id"]) if single else wanted["id"], "kind": wanted["kind"], "role": wanted["role"],
                     "path": wanted["path"],
                     "reachedBy": [ref.replace(f"{root_id}::", "") for ref in wanted["reachedBy"]] if single else wanted["reachedBy"]}
        if not single:
            view["workspaceId"], reference["workspaceId"] = shown["workspaceId"], wanted["workspaceId"]
        if not compact and shown["projection"] != "reference":
            view["statementRefs"] = shown["statementRefs"]
            reference["statementRefs"] = [unqualified(ref) for ref in wanted["statementRefs"]] if single else wanted["statementRefs"]
        if view != reference:
            raise ValueError("文書が入力からの参照計算と異なります")
    if not single and (result["resolution"]["workspaces"] != expected["workspaces"]
                       or result["resolution"]["crossWorkspaceEdges"] != expected["edges"]):
        raise ValueError("到達ワークスペースまたは横断するエッジが入力からの参照計算と異なります")
    check_coverage(result, documents, order, root, purpose)
    if result["contextDigest"] != reference_digest(identifier, repository):
        raise ValueError("ハッシュ値が参照計算と異なります")


def check_coverage(result, documents, closure, root, purpose):
    """目的`implement`の制約台帳とカバレッジ（関係・トレースモデル §6.4・§8）。目的`interpret`は対象規範文を持たない。

    このcorpusは対象規範文がすべて`MUST`で、未対応・未テストの警告を持たない。
    """
    if purpose == "interpret":
        wanted_total = []
    else:
        wanted_total = statement_ids(documents, root)
    addressed = {multi_crosscheck.qualify(documents[name]["workspaceId"], text) for name in closure
                 if documents[name]["kind"] == "task" for text in documents[name]["frontmatter"]["relations"]["addresses"]}
    tested = {multi_crosscheck.qualify(documents[name]["workspaceId"], text) for name in closure
              for entry in documents[name]["frontmatter"].get("tests", []) for text in entry["covers"]}
    must = result["coverage"]["must"]
    if [item["id"] for item in result["constraintLedger"]["statements"]] != wanted_total or must["total"] != wanted_total:
        raise ValueError("対象規範文が入力からの参照計算と異なります")
    if (must["addressed"], must["tested"]) != ([s for s in wanted_total if s in addressed], [s for s in wanted_total if s in tested]):
        raise ValueError("対応済みまたはテスト済みが入力からの参照計算と異なります")
    if must["unaddressed"] != [s for s in wanted_total if s not in addressed] or must["untested"] != [s for s in wanted_total if s not in tested]:
        raise ValueError("未対応または未テストが入力からの参照計算と異なります")
    if (must["unaddressed"] or must["untested"]) and not result["diagnostics"]:
        raise ValueError("未対応または未テストの警告が必要です")


def check_conditions(identifier, repository):
    """原因の構成を、散文ではなく準備手順の後の入力とGitの状態から確かめる。"""
    case = CASES[identifier]
    single, root_id, workspaces, documents = load_tree(repository)
    corpus = case["corpus"]
    root = f"{root_id}::{case['root']}" if single else case["root"]
    purpose = case["argv"][case["argv"].index("--purpose") + 1] if "--purpose" in case["argv"] else "interpret"
    order, edges, _ = interpret_closure(documents, root, purpose)
    cyclic = {name for name, _ in cyclic_edges(documents)}
    owner = root_id if single else "web"
    expected_cycle = {f"{owner}::TECH-010", f"{owner}::TECH-011"}
    if corpus == "cycle-outside":
        # 循環は存在するが、閉包の外にある（陰性対照: 循環の文書は到達できない）。
        if cyclic != {f"{owner}::TECH-020", f"{owner}::TECH-021"} or set(order) != {root} or cyclic & set(order):
            raise ValueError("循環は閉包の外の2文書だけにある必要があります")
    elif corpus == "cycle-inside":
        if cyclic != expected_cycle or not cyclic <= set(order) or len(order) != 3:
            raise ValueError("循環は閉包の中の2文書にある必要があります")
        if (repository / (SINGLE_TEST_PATH if single else WEB_TEST_PATH)).read_bytes() != TEST_BYTES:
            raise ValueError("起点はテスト対応が通る入力である必要があります")
    elif corpus == "alias-duplicate":
        # `web::TECH-010`を非修飾と修飾の両方の表記で参照している（二重収録の条件）。ほかの原因はない。
        if spellings(documents, "web::TECH-010") != {"TECH-010", "web::TECH-010"} or cyclic or reference_diagnostics(documents, order):
            raise ValueError("`web::TECH-010`は非修飾と修飾の両方で参照され、ほかの原因はない必要があります")
        if set(order) != {"web::REQ-001", "web::TECH-010", "web::TECH-011", "api::TECH-020"}:
            raise ValueError("閉包は4文書である必要があります")
    elif corpus == "alias-refines":
        # 起点を具体化する文書は、修飾した宣言だけで起点を指す。ほかの原因はない。
        declared = documents["api::TECH-030"]["frontmatter"]["relations"]["refines"]
        if declared != ["web::REQ-001"] or set(order) != {"web::REQ-001", "api::TECH-030"} or cyclic or reference_diagnostics(documents, order):
            raise ValueError("`api::TECH-030`は修飾した宣言で起点を`refines`し、ほかの原因はない必要があります")
    elif corpus == "same-refines":
        # 起点を具体化する文書は同じワークスペースにあり、非修飾の宣言で起点を指す。統合索引の別名の数だけ二重に数えられる条件。
        if documents["web::TECH-001"]["frontmatter"]["relations"]["refines"] != ["REQ-001"] or set(order) != {"web::REQ-001", "web::TECH-001"}:
            raise ValueError("`web::TECH-001`は同じワークスペースの起点を非修飾で`refines`する必要があります")
    elif corpus == "supersede":
        # 有効な後継は`REQ-002`の1つだけ。起点は置換済みで、後継を暗黙に起点へ差し替えない。
        if successors_of(documents, root) != ["web::REQ-002"] or set(order) != {"web::REQ-001", "web::REQ-002"}:
            raise ValueError("有効な後継は`web::REQ-002`の1つだけである必要があります")
        if role_of(documents, root, root, edges) != "advisory":
            raise ValueError("置換済みの起点は役割`advisory`である必要があります")
    elif corpus == "task-addresses":
        # TASKは自ワークスペースを修飾した規範文IDだけで起点の規範文を指し、状態は`open`。起点のMUSTはテスト対応を持つ。
        work = documents["web::TASK-001"]["frontmatter"]
        if work["relations"]["addresses"] != ["web::REQ-001:AC-01"] or work["status"] != "open" or set(order) != {"web::REQ-001", "web::TASK-001"}:
            raise ValueError("`web::TASK-001`は修飾した規範文IDで起点を`addresses`する状態`open`のTASKである必要があります")
        if (repository / WEB_TEST_PATH).read_bytes() != TEST_BYTES:
            raise ValueError("起点はテスト対応が通る入力である必要があります")
    elif corpus == "other-supersede":
        # 有効な後継は他のメンバーの`api::REQ-009`の1つだけ。起点は置換済み。
        if successors_of(documents, root) != ["api::REQ-009"] or set(order) != {"web::REQ-001", "api::REQ-009"}:
            raise ValueError("有効な後継は他のメンバーの`api::REQ-009`の1つだけである必要があります")
        if documents["api::REQ-009"]["frontmatter"]["relations"]["supersedes"] != ["web::REQ-001"]:
            raise ValueError("後継は起点を修飾して`supersedes`する必要があります")
    elif corpus == "other-draft-refines":
        # 他のメンバーの状態`draft`の文書が起点を修飾して`refines`する。適用可能ではないので具体化文書にならず、`advisory`だけ。
        draft = documents["api::TECH-040"]
        if draft["frontmatter"]["status"] != "draft" or draft["frontmatter"]["relations"]["refines"] != ["web::REQ-001"]:
            raise ValueError("`api::TECH-040`は状態`draft`で起点を修飾して`refines`する必要があります")
        if set(order) != {"web::REQ-001", "api::TECH-040"} or role_of(documents, root, "api::TECH-040", edges) != "advisory":
            raise ValueError("`api::TECH-040`は役割`advisory`で閉包に入る必要があります")
    elif corpus == "other-task":
        work = documents["api::TASK-009"]["frontmatter"]
        if work["relations"]["addresses"] != ["web::REQ-001:AC-01"] or work["status"] != "open" or set(order) != {"web::REQ-001", "api::TASK-009"}:
            raise ValueError("`api::TASK-009`は修飾した規範文IDで起点を`addresses`する状態`open`のTASKである必要があります")
        if (repository / WEB_TEST_PATH).read_bytes() != TEST_BYTES:
            raise ValueError("起点はテスト対応が通る入力である必要があります")
    elif corpus == "alias-error":
        # 参照切れを持つ`web::TECH-010`には、修飾した表記だけで到達する（陰性対照は`direct-error`）。
        if spellings(documents, "web::TECH-010") != {"web::TECH-010"} or "web::TECH-010" not in order:
            raise ValueError("`web::TECH-010`は修飾した表記だけで到達される必要があります")
        if [item["evidence"] for item in reference_diagnostics(documents, order)] != ["TECH-999"]:
            raise ValueError("原因は`TECH-010`の参照切れの1件だけである必要があります")
    elif corpus == "direct-error":
        if spellings(documents, "web::TECH-010") != {"TECH-010"} or "web::TECH-010" not in order:
            raise ValueError("`web::TECH-010`は非修飾の表記だけで到達される必要があります")
    elif corpus in {"adr-proposed", "adr-qualified"}:
        wanted = {"adr-proposed": "ADR-001", "adr-qualified": "api::ADR-001"}[corpus]
        if spellings(documents, "api::ADR-001") != {wanted}:
            raise ValueError("ADR-001は宣言どおりの表記だけで参照される必要があります")
        if documents["api::ADR-001"]["frontmatter"]["status"] != "proposed" or cyclic:
            raise ValueError("原因は状態`proposed`のADR-001への`requires`だけである必要があります")
        if case["root"].partition("::")[0] == "api":
            raise ValueError("起点は呼び出し側のワークスペースの文書である必要があります")
    elif corpus == "adr-single":
        if not single or documents[f"{root_id}::ADR-001"]["frontmatter"]["status"] != "proposed":
            raise ValueError("単一ワークスペースの状態`proposed`のADR-001が必要です")
    if case["outcome"] == "failed" and not reference_diagnostics(documents, order):
        raise ValueError("失敗するfixtureには診断になるエッジが必要です")
    return order


# --- 生成と監査 ---------------------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = root / "multi" / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / RESULT_FILES[CASES[identifier]["op"]]).write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-closure-alias-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(_dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    frontmatter = json.loads(schema_path(root, "frontmatter").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / RESULT_FILES[CASES[identifier]["op"]]).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for key, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[key].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[key] for key, p in files.items()):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if (fixture / "changes").exists() or (fixture / "cli-output.json").exists():
                raise ValueError("このfixtureは`changes/`と`cli-output.json`を持ちません")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-closure-alias-") as temporary:
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
                    check_conditions(identifier, repository)
                    check_against_reference(identifier, repository, result)
                    for path in sorted(repository.rglob("*.md")):
                        if path.parent.parent.name == ".spec" and path.parent.name in KIND_BY_DIRECTORY:
                            value, _ = split_document(path.read_text(encoding="utf-8"))
                            Draft202012Validator({"$ref": "#/$defs/" + FIXTURE_KINDS[
                                {"requirements": "requirement", "technical": "technical", "decisions": "decision",
                                 "tasks": "task"}[path.parent.name]], "$defs": frontmatter["$defs"]}).validate(value)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run", "references": 2,
            "status": "Passed" if not errors else "Failed", "errors": errors}
