"""参照適合harness全体(`run_conformance.py`)の自己試験(ADR-052 Decision 5)。

`fake_core.py`が生成する偽Coreに対して、実際にwheelをビルドし、隔離した仮想環境へ導入し、
サブプロセスとして起動する一連の流れを通しで確かめる。期待どおりの偽Coreでは
選んだfixtureがすべて`passed`になること、出力を1箇所改変した偽Coreでは改変した
fixtureだけが`failed`になり(`error`にならない)、他は`passed`のままであることを検査する。

実行方法(リポジトリのルートから):
`uv run --with jsonschema==4.23.0 python -m unittest fixtures.conformance.test_fake_core`

ネットワーク(PyPIからのruamel.yamlの解決)と`uv`コマンドを必要とする。実行時間は
通常数十秒程度(`uv`のキャッシュがあれば数秒)。
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

import run_conformance  # noqa: E402  (fixtures/直下のscript。上のsys.path操作の後でimportする)
from conformance.fake_core import build_fake_core  # noqa: E402

CONFORMANCE_ROOT = Path(__file__).resolve().parent


def _step1_fixture_ids():
    steps = json.loads((CONFORMANCE_ROOT / "steps.json").read_text(encoding="utf-8"))["steps"]
    return steps[0]["fixtures"]


# Step 1の34件(`doctor`/`check`/`context`/`package`、`json`/`none`/`text`の標準出力、`gitVersion`・`python`の指定、
# `PATH`の上書きによるGit不在を含む)に、Step 1にはない代表のfixture(`verify`の各状態、レポートあり、
# Markdown、Git不在の`verify`、コンテキストのハッシュ値)を加え、単一ワークスペースの生成でないfixtureから
# 各操作・各標準出力の種類・レポートあり・`git:false`・`gitVersion`の指定を代表させる。
EXTRA_FIXTURE_IDS = [
    "SINGLE-055", "SINGLE-056", "SINGLE-060", "SINGLE-068",
    "SINGLE-071-01", "SINGLE-071-02", "SINGLE-071-03", "SINGLE-071-04",
    "SINGLE-104-01", "SINGLE-104-02", "SINGLE-104-03",
    "SINGLE-105-01", "SINGLE-105-02", "SINGLE-042",
]
REPRESENTATIVE_FIXTURE_IDS = _step1_fixture_ids() + EXTRA_FIXTURE_IDS

# 改変の3種(`json`/`text`/`none`)を検査する最小の部分集合。
MUTATION_SUBSET = ["SINGLE-001", "SINGLE-104-04", "SINGLE-073-01"]


def _run_harness(core_dir, fixture_ids):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
        output_path = Path(handle.name)
    try:
        argv = ["--core", str(core_dir), "--output", str(output_path)]
        for identifier in fixture_ids:
            argv += ["--fixture", identifier]
        run_conformance.main(argv)
        return json.loads(output_path.read_text(encoding="utf-8"))
    finally:
        output_path.unlink(missing_ok=True)


class FakeCoreSelfTests(unittest.TestCase):
    """ADR-052 Decision 5の前段: 期待どおりの偽Coreでは選んだfixtureが全件`passed`になる。"""

    def test_representative_fixture_count_is_within_specified_range(self):
        self.assertGreaterEqual(len(REPRESENTATIVE_FIXTURE_IDS), 34)
        self.assertLessEqual(len(REPRESENTATIVE_FIXTURE_IDS), 60)

    def test_representative_fixtures_all_pass_against_matching_fake_core(self):
        with tempfile.TemporaryDirectory(prefix="bitz-fakecore-self-") as tmp:
            core_dir = Path(tmp) / "core"
            build_fake_core(core_dir, REPRESENTATIVE_FIXTURE_IDS)
            report = _run_harness(core_dir, REPRESENTATIVE_FIXTURE_IDS)
        failing = [entry for entry in report["fixtures"] if entry["result"] != "passed"]
        self.assertEqual(failing, [])
        self.assertEqual(report["counts"], {"passed": len(REPRESENTATIVE_FIXTURE_IDS), "failed": 0, "error": 0})
        self.assertTrue(report["allPassed"])

    def test_step1_alone_all_pass(self):
        step1 = _step1_fixture_ids()
        with tempfile.TemporaryDirectory(prefix="bitz-fakecore-step1-") as tmp:
            core_dir = Path(tmp) / "core"
            build_fake_core(core_dir, step1)
            report = _run_harness(core_dir, step1)
        self.assertTrue(report["allPassed"])
        self.assertEqual(report["counts"]["passed"], len(step1))


class FakeCoreMutationTests(unittest.TestCase):
    """出力を1箇所改変した偽Coreでは、改変したfixtureだけが`failed`になり他は`passed`のまま。"""

    def _run_mutation(self, mutate_id):
        with tempfile.TemporaryDirectory(prefix=f"bitz-fakecore-mutate-{mutate_id}-") as tmp:
            core_dir = Path(tmp) / "core"
            build_fake_core(core_dir, MUTATION_SUBSET, mutate=mutate_id)
            return _run_harness(core_dir, MUTATION_SUBSET)

    def _assert_only_one_failed(self, report, mutated_id):
        results = {entry["id"]: entry["result"] for entry in report["fixtures"]}
        self.assertEqual(results.get(mutated_id), "failed", results)
        for identifier, result in results.items():
            if identifier != mutated_id:
                self.assertEqual(result, "passed", results)

    def test_mutated_json_stdout_fixture_fails_alone(self):
        self._assert_only_one_failed(self._run_mutation("SINGLE-001"), "SINGLE-001")

    def test_mutated_text_stdout_fixture_fails_alone(self):
        self._assert_only_one_failed(self._run_mutation("SINGLE-104-04"), "SINGLE-104-04")

    def test_mutated_none_stdout_fixture_fails_alone(self):
        self._assert_only_one_failed(self._run_mutation("SINGLE-073-01"), "SINGLE-073-01")

    def test_mutated_report_content_fails_alone(self):
        """標準出力は正しいまま、`.spec/reports/`へ保存するレポートの内容だけを改変した場合。

        レポートの内容も結果・診断・終了コード 8の結果JSONそのものとして、正規化器を適用した後に期待結果と
        完全な構造で比較する(適合fixture仕様2)。標準出力は正しいので標準出力の比較は一致するが、
        レポートの内容の不一致で当該のfixtureだけが`failed`になるはずである。
        """
        subset = ["SINGLE-001", "SINGLE-071-01", "SINGLE-073-01"]
        with tempfile.TemporaryDirectory(prefix="bitz-fakecore-mutate-report-") as tmp:
            core_dir = Path(tmp) / "core"
            build_fake_core(core_dir, subset, mutate_report="SINGLE-071-01")
            report = _run_harness(core_dir, subset)
        self._assert_only_one_failed(report, "SINGLE-071-01")
        mutated = next(entry for entry in report["fixtures"] if entry["id"] == "SINGLE-071-01")
        self.assertTrue(any("report(" in difference for difference in mutated["differences"]), mutated)


# 生成fixture(適合fixture仕様3.4・3.5)の代表: `check`(`memberCount`の境界、`passed`)、
# `verify`(`verifyBindingCount`の境界、`passed`)、`blocked`(`memberCount`の超過)の3形状を1件ずつ。
# `specFileCount`・`inputBytes`など実寸の生成が重い次元は避け、`memberCount`と`verifyBindingCount`の
# 境界(13ワークスペース程度)だけを選ぶ。生成fixtureは期待結果をファイルとして持たないため、
# 偽Coreの応答は`multi_generator`と`multi_limit_fixtures`(fixtureのharness側のレビュー済みの参照計算。
# Coreの実装ではない)から`fake_core.py`が再構成する。
GENERATE_FIXTURE_IDS = ["MULTI-020-01", "MULTI-020-16", "MULTI-021-01"]


class GenerateFixtureSelfTests(unittest.TestCase):
    """生成fixtureのharnessの判定能力の自己試験(ADR-052 Decision 5と同じ考え方)。

    `runner.py`が`setup.generate`(入力の木構造の決定論的な生成と`treeDigest`の照合)、`resultDigest`
    (正規JSONのSHA-256による期待結果の比較)、`stateDigest`(副作用の期待値の比較)を
    仕様どおりに判定できることを、実際にwheelをビルドして確かめる。
    """

    def test_generate_fixtures_pass_against_matching_fake_core(self):
        with tempfile.TemporaryDirectory(prefix="bitz-fakecore-generate-") as tmp:
            core_dir = Path(tmp) / "core"
            build_fake_core(core_dir, GENERATE_FIXTURE_IDS)
            report = _run_harness(core_dir, GENERATE_FIXTURE_IDS)
        failing = [entry for entry in report["fixtures"] if entry["result"] != "passed"]
        self.assertEqual(failing, [], report["fixtures"])
        self.assertEqual(report["counts"], {"passed": len(GENERATE_FIXTURE_IDS), "failed": 0, "error": 0})
        self.assertTrue(report["allPassed"])

    def test_generate_fixture_mutated_result_fails_alone(self):
        """`resultDigest`が固定する期待結果を1箇所改変すると、`error`ではなく`failed`になる。"""
        mutate_id = "MULTI-021-01"
        with tempfile.TemporaryDirectory(prefix="bitz-fakecore-generate-mutate-") as tmp:
            core_dir = Path(tmp) / "core"
            build_fake_core(core_dir, GENERATE_FIXTURE_IDS, mutate=mutate_id)
            report = _run_harness(core_dir, GENERATE_FIXTURE_IDS)
        results = {entry["id"]: entry["result"] for entry in report["fixtures"]}
        self.assertEqual(results.get(mutate_id), "failed", results)
        for identifier, result in results.items():
            if identifier != mutate_id:
                self.assertEqual(result, "passed", results)
        mutated = next(entry for entry in report["fixtures"] if entry["id"] == mutate_id)
        self.assertTrue(any("resultDigest" in difference for difference in mutated["differences"]), mutated)

    def test_generate_fixture_extra_side_effect_fails_alone(self):
        """読取り専用の前提(`stateDigest`)へ、実行がファイルを1件足すと`failed`になる(`error`にならない)。"""
        mutate_id = "MULTI-020-01"
        with tempfile.TemporaryDirectory(prefix="bitz-fakecore-generate-effect-") as tmp:
            core_dir = Path(tmp) / "core"
            build_fake_core(core_dir, GENERATE_FIXTURE_IDS, mutate_side_effect=mutate_id)
            report = _run_harness(core_dir, GENERATE_FIXTURE_IDS)
        results = {entry["id"]: entry["result"] for entry in report["fixtures"]}
        self.assertEqual(results.get(mutate_id), "failed", results)
        for identifier, result in results.items():
            if identifier != mutate_id:
                self.assertEqual(result, "passed", results)
        mutated = next(entry for entry in report["fixtures"] if entry["id"] == mutate_id)
        self.assertTrue(any("stateDigest" in difference for difference in mutated["differences"]), mutated)


if __name__ == "__main__":
    unittest.main()
