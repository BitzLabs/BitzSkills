"""複合ワークスペースの`context`が、文書と規範文の並びを出力と同じ修飾IDの辞書順で比べることの単体試験（確認事項 C46）。

欠陥: 複合ワークスペースの`context`は、`documents`・`constraintLedger.statements`・`coverage`の各配列を、起点ワークスペースの文書と規範文を
修飾しない内部のID（`TECH-005`）のまま辞書順に比べていた。他のメンバーの文書は修飾したID（`api::TECH-010`）で比べるので、
同じ距離・同じ種別の文書が、出力のID（`platform::TECH-005`と`api::TECH-010`）の辞書順と食い違って並んだ（大文字の`T`が小文字の`a`より前）。

規範:
- 関係・トレースモデル §7の6.: 「最短距離、種別の順REQ／TECH／ADR／TASK、IDの辞書順で並べる」。7.: 規範文は文書順、行番号、IDの順。
  §6.4: `targetStatements`は`contextDocuments`の順、行番号、IDの順。
- 複合ワークスペース仕様 §4・§6: 複合ワークスペースの各文書IDとエッジのIDは修飾IDで出力する。
- `context` §5: コンテキストの`documents`は上の順で出力する。
- コンテキストのハッシュ値の正規化仕様 §3: 提示の順は材料に含めない（文書は修飾IDの順に材料へ置く）。ハッシュ値は並びの修正で変わらない。

この試験の対象:
1. 同じ距離・同じ種別の文書の並びが、修飾IDの辞書順になる（`documents`、目的`implement`の`constraintLedger`と`coverage`の各配列）。
2. 距離・種別が違う文書の並びは今までどおり（距離、種別が先で、修飾IDは同じ距離・同じ種別の間だけ）。
3. 複数の起点（統合の経路）でも同じ。単一ワークスペースの並びは変わらない（対照）。
4. `contextDigest`は並びの修正で変わらない（独立の参照計算で導いた値との一致）。
5. `check`と`verify`の出力は変わらない（対照）。
6. 結果は`result.schema.json`に適合し、`PYTHONHASHSEED`を変えても出力は同じ。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bitz import check as check_mod
from bitz import context as context_mod
from bitz import verify as verify_mod
from bitz.cliargs import parse_argv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = REPO_ROOT / "docs" / "03.詳細設計" / "schemas" / "result.schema.json"

CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
# `verify`が実行できるよう、どのワークスペースにも成功するコマンドを置く。
VERIFY = 'verify:\n  commands:\n    t:\n      argv: ["/bin/true", "{tests}"]\n      cwd: .\n'
_GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
_KIND_RANK = {"REQ": 0, "TECH": 1, "ADR": 2, "TASK": 3}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, env={**os.environ, **_GIT_ENV}, check=True, capture_output=True, text=True
    )


def _write(root: Path, rel: str, content: str) -> None:
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def _root_yaml(ws_id: str, members: list[tuple[str, str]]) -> str:
    text = CONFIG + f"workspace:\n  id: {ws_id}\nmultiWorkspace:\n  members:\n"
    for mid, mpath in members:
        text += f"    - id: {mid}\n      path: {mpath}\n"
    return text + VERIFY


def _single_yaml(ws_id: str) -> str:
    return CONFIG + f"workspace:\n  id: {ws_id}\n" + VERIFY


def _front(doc_id: str, status: str, *, relations: dict[str, list[str]] | None = None, covers: str | None = None,
           changes: bool = False) -> str:
    text = f"---\nid: {doc_id}\ntitle: {doc_id}の文書\nstatus: {status}\n"
    if relations:
        text += "relations:\n" + "".join(f"  {key}: [{', '.join(values)}]\n" for key, values in relations.items())
    if covers is not None:
        text += f"tests:\n  - path: tests/t.py\n    covers: [{covers}]\n    command: t\n"
    if changes:
        text += "changes: [src/work.py]\n"
    return text + "---\n\n"


def _statement(doc_id: str, label: str) -> str:
    return f"- [{doc_id}:{label}] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] {doc_id}を守る。\n"


def _req(doc_id: str, *, requires: list[str] | None = None, tested: bool = True) -> str:
    relations = {"requires": requires} if requires else None
    return (
        _front(doc_id, "approved", relations=relations, covers=f"{doc_id}:AC-01" if tested else None)
        + f"# {doc_id} {doc_id}の文書\n\n## Intent\n\n意図。\n\n## Acceptance Criteria\n\n{_statement(doc_id, 'AC-01')}\n## Verification\n\n未証明。\n"
    )


def _tech(doc_id: str, refines: str, *, tested: bool = True) -> str:
    return (
        _front(doc_id, "approved", relations={"refines": [refines]}, covers=f"{doc_id}:C-01" if tested else None)
        + f"# {doc_id} {doc_id}の文書\n\n## Context\n\n本文。\n\n## Constraints\n\n{_statement(doc_id, 'C-01')}"
    )


def _task(doc_id: str, addresses: list[str]) -> str:
    return (
        _front(doc_id, "open", relations={"addresses": addresses}, changes=True)
        + f"# {doc_id} {doc_id}の文書\n\n## Objective\n\n目的。\n"
    )


def _validate_against_schema(results: list[dict]) -> None:
    """結果が公開スキーマに適合することを確かめる。Coreの環境に`jsonschema`がないため、`uv`で一時的に用意して別プロセスで検証する。"""

    uv = shutil.which("uv")
    if uv is None:
        raise unittest.SkipTest("uvがないためスキーマ適合を確認できません")
    script = (
        "import json, sys\n"
        "from jsonschema import Draft202012Validator\n"
        "schema = json.load(open(sys.argv[1], encoding='utf-8'))\n"
        "validator = Draft202012Validator(schema)\n"
        "bad = []\n"
        "for item in json.load(sys.stdin):\n"
        "    errors = [e.message for e in validator.iter_errors(item)]\n"
        "    if errors:\n"
        "        bad.append(errors[:3])\n"
        "print(json.dumps(bad, ensure_ascii=False))\n"
    )
    proc = subprocess.run(
        [uv, "run", "--quiet", "--no-project", "--with", "jsonschema==4.23.0", "python", "-I", "-c", script, str(RESULT_SCHEMA)],
        input=json.dumps(results),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise unittest.SkipTest(f"jsonschemaを用意できません: {proc.stderr.strip()[-200:]}")
    bad = json.loads(proc.stdout)
    if bad:
        raise AssertionError(f"result.schema.jsonに適合しません: {bad}")


def _without_durations(value):
    """実行時間（`durationMs`）は実行ごとに変わるため、比較から除く。"""

    if isinstance(value, dict):
        return {k: _without_durations(v) for k, v in value.items() if k != "durationMs"}
    if isinstance(value, list):
        return [_without_durations(v) for v in value]
    return value


def _run_cli(cwd: Path, seed: str, *argv: str) -> str:
    """CLIを別プロセスで実行し、`durationMs`を除いた出力を返す。"""

    proc = subprocess.run(
        [sys.executable, "-m", "bitz.cli", *argv, "--format", "json"], cwd=cwd,
        env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": os.pathsep.join(sys.path)},
        capture_output=True, text=True,
    )
    return json.dumps([proc.returncode, _without_durations(json.loads(proc.stdout))], ensure_ascii=False)


class _Base(unittest.TestCase):
    """一時のGitリポジトリを作り、各操作を同一プロセスで実行して結果をスキーマ適合の検証へ集める。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(os.path.realpath(tmp.name))
        self.env = dict(os.environ)
        self.results: list[dict] = []
        _git(self.root, "init", "-q", "--initial-branch=main")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        self.build()
        _git(self.root, "add", ".")
        _git(self.root, "commit", "-q", "-m", "base")

    def build(self) -> None:
        raise NotImplementedError

    def tearDown(self):
        if self.results:
            _validate_against_schema(self.results)

    def _run(self, module, name: str, argv: tuple[str, ...], cwd: str = "."):
        parsed = parse_argv([name, *argv, "--format", "json"])
        result, code = module.run(parsed, str(self.root / cwd), self.env)
        self.results.append(result)
        return result, code

    def context(self, *argv, cwd: str = "."):
        return self._run(context_mod, "context", argv, cwd)

    def check(self, *argv):
        return self._run(check_mod, "check", argv)

    def verify(self, *argv):
        return self._run(verify_mod, "verify", argv)

    @staticmethod
    def doc_ids(result: dict) -> list[str]:
        return [d["id"] for d in result["documents"]]

    @staticmethod
    def ledger_ids(result: dict) -> list[str]:
        return [s["id"] for s in result["constraintLedger"]["statements"]]


class _MultiCorpus(_Base):
    """起点`platform::REQ-001`を、3つのワークスペースの文書が距離1と距離2で具体化する。

    ```
    platform  REQ-001 (requires web::REQ-003)   REQ-002   TECH-005 (refines REQ-001:AC-01)   TECH-006 (refines REQ-002:AC-01)
              TECH-002 (refines TECH-005:C-01)  TASK-001 (REQ-001・REQ-002と、platformの具体化の規範文をaddresses)
    api       TECH-010 (refines platform::REQ-001:AC-01)   TECH-011 (refines platform::REQ-002:AC-01)
              TECH-020 (refines platform::TECH-005:C-01)   TASK-001 (api・webの具体化と、platformの2つのREQの規範文をaddresses)
    web       REQ-003    TECH-010 (refines platform::REQ-001:AC-01)
    ```

    具体化の関係は規範文IDで宣言する。文書IDだけで`refines`した文書の規範文が対象規範文に入るかは、関係・トレースモデル §6.4の文面
    （「選択済みの文書または規範文を`refines`する」）からは決まらないので、この試験は扱わない（宣言をどちらの読みでも同じ結果になる形にそろえる）。

    距離1の同じ種別（TECH）は`platform::TECH-005`・`api::TECH-010`・`web::TECH-010`の3文書で、内部のIDで比べると`TECH-005`が先頭になる。
    """

    tasks_and_tests = True

    def build(self) -> None:
        r = self.root
        with_tests = self.tasks_and_tests
        _write(r, ".spec/bitz.yaml", _root_yaml("platform", [("web", "apps/web"), ("api", "services/api")]))
        _write(r, "apps/web/.spec/bitz.yaml", _single_yaml("web"))
        _write(r, "services/api/.spec/bitz.yaml", _single_yaml("api"))
        for base in (".", "apps/web", "services/api"):
            _write(r, f"{base}/tests/t.py", "def test_t():\n    assert True\n")
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001", requires=["web::REQ-003"], tested=with_tests))
        _write(r, ".spec/requirements/REQ-002.md", _req("REQ-002", tested=with_tests))
        _write(r, ".spec/technical/TECH-005.md", _tech("TECH-005", "REQ-001:AC-01", tested=with_tests))
        _write(r, ".spec/technical/TECH-006.md", _tech("TECH-006", "REQ-002:AC-01", tested=with_tests))
        _write(r, ".spec/technical/TECH-002.md", _tech("TECH-002", "TECH-005:C-01", tested=with_tests))
        _write(r, "services/api/.spec/technical/TECH-010.md", _tech("TECH-010", "platform::REQ-001:AC-01", tested=with_tests))
        _write(r, "services/api/.spec/technical/TECH-011.md", _tech("TECH-011", "platform::REQ-002:AC-01", tested=with_tests))
        _write(r, "services/api/.spec/technical/TECH-020.md", _tech("TECH-020", "platform::TECH-005:C-01", tested=with_tests))
        _write(r, "apps/web/.spec/requirements/REQ-003.md", _req("REQ-003", tested=with_tests))
        _write(r, "apps/web/.spec/technical/TECH-010.md", _tech("TECH-010", "platform::REQ-001:AC-01", tested=with_tests))
        # 起点ワークスペースが`web`のとき（`apps/web`で実行）の同順位: `web::REQ-003`を3つのワークスペースのTECHが具体化する。
        _write(r, ".spec/technical/TECH-007.md", _tech("TECH-007", "web::REQ-003:AC-01", tested=with_tests))
        _write(r, "services/api/.spec/technical/TECH-030.md", _tech("TECH-030", "web::REQ-003:AC-01", tested=with_tests))
        _write(r, "apps/web/.spec/technical/TECH-001.md", _tech("TECH-001", "REQ-003:AC-01", tested=with_tests))
        if with_tests:
            _write(r, ".spec/tasks/TASK-001.md", _task("TASK-001", [
                "REQ-001:AC-01", "REQ-002:AC-01", "TECH-005:C-01", "TECH-006:C-01", "TECH-002:C-01"]))
            _write(r, "services/api/.spec/tasks/TASK-001.md", _task("TASK-001", [
                "platform::REQ-001:AC-01", "platform::REQ-002:AC-01", "TECH-010:C-01", "TECH-011:C-01",
                "TECH-020:C-01", "web::TECH-010:C-01"]))

    IMPLEMENT_TARGETS = [
        "platform::REQ-001:AC-01",
        "api::TECH-010:C-01", "platform::TECH-005:C-01", "web::TECH-010:C-01",
        "api::TECH-020:C-01", "platform::TECH-002:C-01",
    ]


class MultiWorkspaceOrderTests(_MultiCorpus):
    """TASKとテスト対応を持つ入力: 距離・種別・修飾IDの順は、`documents`・制約台帳・カバレッジの各配列で同じである。"""

    # --- 1. documents -------------------------------------------------------------------------

    def test_interpret_documents_are_ordered_by_qualified_id_within_distance_and_kind(self):
        result, code = self.context("REQ-001", "--purpose", "interpret")
        self.assertEqual((result["status"], code), ("passed", 0))
        self.assertEqual(
            self.doc_ids(result),
            [
                "platform::REQ-001",
                # 距離1: 種別REQ、種別TECH。種別TECHの3文書は出力のID（修飾ID）の辞書順。
                "web::REQ-003",
                "api::TECH-010",
                "platform::TECH-005",
                "web::TECH-010",
                # 距離2（TECH-005を具体化する）。`platform::TECH-002`のIDは`TECH-005`より小さいが、距離が遠いので後ろ。
                "api::TECH-020",
                "platform::TECH-002",
            ],
        )

    def test_the_issue_reproduction_with_only_the_tie(self):
        """調査の再現: platformのTECH-005、apiのTECH-010、webのTECH-010がすべて距離1でREQ-001をrefinesする。"""
        result, _ = self.context("REQ-002", "--purpose", "interpret")
        self.assertEqual(
            self.doc_ids(result), ["platform::REQ-002", "api::TECH-011", "platform::TECH-006"]
        )
        result, _ = self.context("platform::REQ-001", "--purpose", "interpret", "--detail", "compact")
        tie = [i for i in self.doc_ids(result) if i.endswith("TECH-005") or i.endswith("TECH-010")]
        self.assertEqual(tie, ["api::TECH-010", "platform::TECH-005", "web::TECH-010"])

    def test_documents_are_sorted_by_distance_then_kind_then_id(self):
        """出力の`documents`は、(距離, 種別の順REQ/TECH/ADR/TASK, 修飾ID)の昇順である（距離は`reachedBy`の辺から独立に数える）。"""
        distance = {
            "platform::REQ-001": 0, "web::REQ-003": 1, "api::TECH-010": 1, "platform::TECH-005": 1, "web::TECH-010": 1,
            "api::TECH-020": 2, "platform::TECH-002": 2, "api::TASK-001": 1, "platform::TASK-001": 1,
        }
        for purpose in ("interpret", "implement"):
            with self.subTest(purpose=purpose):
                result, _ = self.context("REQ-001", "--purpose", purpose)
                ids = self.doc_ids(result)
                expected_keys = sorted(
                    ids, key=lambda i: (distance[i], _KIND_RANK[i.partition("::")[2].partition("-")[0]], i)
                )
                self.assertEqual(ids, expected_keys)

    def test_implement_documents_put_tasks_after_the_technical_documents_of_the_same_distance(self):
        result, _ = self.context("REQ-001", "--purpose", "implement")
        self.assertEqual(
            self.doc_ids(result),
            [
                "platform::REQ-001",
                "web::REQ-003",
                "api::TECH-010", "platform::TECH-005", "web::TECH-010",
                "api::TASK-001", "platform::TASK-001",
                "api::TECH-020", "platform::TECH-002",
            ],
        )

    def test_the_order_does_not_depend_on_which_workspace_the_origin_belongs_to(self):
        """起点ワークスペースが`web`（`apps/web`で実行）のときも、web自身の文書だけを内部のIDで比べない。"""
        result, code = self.context("REQ-003", "--purpose", "interpret", cwd="apps/web")
        self.assertEqual((result["status"], code), ("passed", 0))
        self.assertEqual(result["workspace"], {"id": "web", "path": "apps/web"})
        self.assertEqual(
            self.doc_ids(result), ["web::REQ-003", "api::TECH-030", "platform::TECH-007", "web::TECH-001"]
        )
        result, code = self.context("REQ-003", "--purpose", "implement", cwd="apps/web")
        # この起点を`addresses`するTASKはないので、未対応の警告が出る。並びだけを確かめる。
        self.assertEqual((result["status"], code), ("passed_with_warnings", 0))
        self.assertEqual(
            self.ledger_ids(result),
            ["web::REQ-003:AC-01", "api::TECH-030:C-01", "platform::TECH-007:C-01", "web::TECH-001:C-01"],
        )

    # --- 2. constraintLedger と coverage ---------------------------------------------------------

    def test_implement_ledger_and_coverage_are_ordered_by_qualified_id(self):
        result, code = self.context("REQ-001", "--purpose", "implement")
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
        self.assertEqual(self.ledger_ids(result), self.IMPLEMENT_TARGETS)
        self.assertEqual(
            [s["documentId"] for s in result["constraintLedger"]["statements"]],
            [s.rpartition(":")[0] for s in self.IMPLEMENT_TARGETS],
        )
        must = result["coverage"]["must"]
        self.assertEqual(must["total"], self.IMPLEMENT_TARGETS)
        # `web::REQ-003`は`requires`で到達しただけなので、規範文は対象規範文へ昇格しない（関係・トレースモデル §6.4の4.）。
        self.assertNotIn("web::REQ-003:AC-01", must["total"])
        self.assertEqual(must["addressed"], self.IMPLEMENT_TARGETS)
        self.assertEqual(must["tested"], self.IMPLEMENT_TARGETS)
        self.assertEqual((must["unaddressed"], must["untested"]), ([], []))
        self.assertEqual(result["coverage"]["adjacent"], [])

    def test_verify_purpose_has_the_same_ledger_and_coverage_order(self):
        result, _ = self.context("REQ-001", "--purpose", "verify")
        self.assertEqual(self.ledger_ids(result), self.IMPLEMENT_TARGETS)
        self.assertEqual(result["coverage"]["must"]["total"], self.IMPLEMENT_TARGETS)

    def test_ledger_and_coverage_keep_distance_before_the_qualified_id(self):
        """距離が遠い文書の規範文は、IDが小さくても後ろ（`platform::TECH-002`は距離2）。"""
        result, _ = self.context("REQ-001", "--purpose", "implement")
        ids = self.ledger_ids(result)
        self.assertLess(ids.index("platform::TECH-005:C-01"), ids.index("platform::TECH-002:C-01"))
        self.assertLess(ids.index("web::TECH-010:C-01"), ids.index("api::TECH-020:C-01"))
        self.assertEqual(ids[0], "platform::REQ-001:AC-01")

    # --- 3. 複数の起点（統合の経路） -----------------------------------------------------------------

    def test_multiple_roots_merge_in_the_same_order(self):
        result, code = self.context("REQ-001", "REQ-002", "--purpose", "interpret")
        self.assertEqual((result["status"], code), ("passed", 0))
        self.assertEqual(result["roots"], ["platform::REQ-001", "platform::REQ-002"])
        self.assertEqual(
            self.doc_ids(result),
            [
                "platform::REQ-001", "platform::REQ-002",
                "web::REQ-003",
                "api::TECH-010", "api::TECH-011", "platform::TECH-005", "platform::TECH-006", "web::TECH-010",
                "api::TECH-020", "platform::TECH-002",
            ],
        )
        # 起点の順を入れ替えても結果は同じ（起点は正規IDの辞書順に正規化する）。
        again, _ = self.context("REQ-002", "REQ-001", "--purpose", "interpret")
        self.assertEqual(_without_durations(result), _without_durations(again))

    def test_multiple_roots_merge_the_ledger_and_coverage_in_the_same_order(self):
        result, code = self.context("REQ-001", "REQ-002", "--purpose", "implement")
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
        expected = [
            "platform::REQ-001:AC-01", "platform::REQ-002:AC-01",
            "api::TECH-010:C-01", "api::TECH-011:C-01", "platform::TECH-005:C-01", "platform::TECH-006:C-01",
            "web::TECH-010:C-01",
            "api::TECH-020:C-01", "platform::TECH-002:C-01",
        ]
        self.assertEqual(self.ledger_ids(result), expected)
        must = result["coverage"]["must"]
        self.assertEqual((must["total"], must["addressed"], must["tested"]), (expected, expected, expected))

    # --- 4. contextDigest -----------------------------------------------------------------------

    # 並びの修正の前後で同じ値であること。独立の参照計算（fixtures/conformance/multi_closure_alias_fixtures.derived_material）が、
    # この入力の木構造から導いた正規JSONのsha256である（Coreの出力を写した値ではない）。
    DIGESTS = {
        ("interpret",): "sha256:81b58c15fe2cfe50f50f0b7e9c3efcab4573d09b03a3993005be43ac970707be",
        ("implement",): "sha256:d48ed4f528202f6440765b23ca30b8e3162e49f77ec461fa4debf43361c9c65c",
    }

    def test_context_digest_does_not_depend_on_the_presentation_order(self):
        for purpose in ("interpret", "implement"):
            with self.subTest(purpose=purpose):
                result, _ = self.context("REQ-001", "--purpose", purpose)
                self.assertEqual(result["contextDigest"], self.DIGESTS[(purpose,)])
                # `--detail compact`は提示形式だけを変え、ハッシュ値を変えない。
                compact, _ = self.context("REQ-001", "--purpose", purpose, "--detail", "compact")
                self.assertEqual(compact["contextDigest"], self.DIGESTS[(purpose,)])

    # --- 5. check / verify（対照） -----------------------------------------------------------------

    def test_check_and_verify_still_pass_with_the_same_statement_set(self):
        """対照: `check`と`verify`の状態と、`verify`の対象規範文の集合とハッシュ値を確かめる（並びは確かめない。`verify`の`statements`の並びは実装の確認事項C52）。"""
        result, code = self.check("REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
        result, code = self.verify("REQ-001")
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
        (target,) = result["targetResults"]
        self.assertEqual(target["target"], "platform::REQ-001")
        self.assertEqual(sorted(target["statements"]), sorted(self.IMPLEMENT_TARGETS))
        # `verify`の検証対象のハッシュ値は、同じ起点の目的`verify`のコンテキストと同じ（同じ閉包の材料から作る）。
        context, _ = self.context("REQ-001", "--purpose", "verify")
        self.assertEqual(target["contextDigest"], context["contextDigest"])

    # --- 6. 決定性 ------------------------------------------------------------------------------

    def test_output_is_independent_of_hash_seed(self):
        cases = [
            ("context", "REQ-001", "--purpose", "interpret"),
            ("context", "REQ-001", "--purpose", "implement"),
            ("context", "REQ-001", "REQ-002", "--purpose", "implement"),
            ("verify", "REQ-001"),
        ]
        for argv in cases:
            outputs = {seed: _run_cli(self.root, seed, *argv) for seed in ("0", "1", "12345")}
            with self.subTest(argv=argv):
                self.assertEqual(len(set(outputs.values())), 1, outputs)


class MultiWorkspaceUncoveredOrderTests(_MultiCorpus):
    """対応済み・テスト済みの宣言がない同じ入力: `unaddressed`と`untested`の並びも、修飾IDの辞書順になる。"""

    tasks_and_tests = False

    def test_unaddressed_and_untested_are_ordered_by_qualified_id(self):
        result, code = self.context("REQ-001", "--purpose", "implement")
        self.assertEqual((result["status"], code), ("passed_with_warnings", 0))
        self.assertEqual(self.ledger_ids(result), self.IMPLEMENT_TARGETS)
        must = result["coverage"]["must"]
        self.assertEqual(must["total"], self.IMPLEMENT_TARGETS)
        self.assertEqual((must["addressed"], must["tested"]), ([], []))
        self.assertEqual(must["unaddressed"], self.IMPLEMENT_TARGETS)
        self.assertEqual(must["untested"], self.IMPLEMENT_TARGETS)
        self.assertEqual(
            sorted({d["code"] for d in result["diagnostics"]}), ["CTX-COVERAGE-TASK-001", "CTX-COVERAGE-TEST-001"]
        )


class SingleWorkspaceControlTests(_Base):
    """対照: 単一ワークスペースの並びは変わらない（IDは修飾しない）。"""

    def build(self) -> None:
        r = self.root
        _write(r, ".spec/bitz.yaml", _single_yaml("solo"))
        _write(r, "tests/t.py", "def test_t():\n    assert True\n")
        _write(r, ".spec/requirements/REQ-001.md", _req("REQ-001"))
        _write(r, ".spec/technical/TECH-005.md", _tech("TECH-005", "REQ-001:AC-01"))
        _write(r, ".spec/technical/TECH-010.md", _tech("TECH-010", "REQ-001:AC-01"))
        _write(r, ".spec/technical/TECH-002.md", _tech("TECH-002", "TECH-005:C-01"))
        _write(r, ".spec/tasks/TASK-001.md", _task("TASK-001", [
            "REQ-001:AC-01", "TECH-005:C-01", "TECH-010:C-01", "TECH-002:C-01"]))

    def test_order_is_unchanged(self):
        result, code = self.context("REQ-001", "--purpose", "implement")
        self.assertEqual((result["status"], code), ("passed", 0), result["diagnostics"])
        self.assertEqual(self.doc_ids(result), ["REQ-001", "TECH-005", "TECH-010", "TASK-001", "TECH-002"])
        targets = ["REQ-001:AC-01", "TECH-005:C-01", "TECH-010:C-01", "TECH-002:C-01"]
        self.assertEqual(self.ledger_ids(result), targets)
        must = result["coverage"]["must"]
        self.assertEqual((must["total"], must["addressed"], must["tested"]), (targets, targets, targets))
        self.assertNotIn("workspaceId", result["documents"][0])

    def test_order_is_independent_of_hash_seed(self):
        outputs = {seed: _run_cli(self.root, seed, "context", "REQ-001", "--purpose", "implement") for seed in ("0", "1", "12345")}
        self.assertEqual(len(set(outputs.values())), 1, outputs)


if __name__ == "__main__":
    unittest.main()
