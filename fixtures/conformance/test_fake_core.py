"""参照適合harness全体(`run_conformance.py`)の自己試験(ADR-052 Decision 5)。

`fake_core.py`が生成する偽Coreに対して、実際にwheelをbuildし、隔離venvへ導入し、
subprocessとして起動する一連の流れをend-to-endで確かめる。期待どおりの偽Coreでは
選んだfixtureがすべて`passed`になること、出力を1箇所改変した偽Coreでは改変した
fixtureだけが`failed`になり(`error`にならない)、他は`passed`のままであることを検査する。

実行方法(repository rootから):
`uv run --with jsonschema==4.23.0 python -m unittest fixtures.conformance.test_fake_core`

ネットワーク(PyPIからのruamel.yaml解決)と`uv`コマンドを必要とする。実行時間は
通常数十秒程度(uvのcacheがあれば数秒)。
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


# Step 1の34件(doctor/check/context/package、json/none/text stdout、gitVersion・python指定、
# PATH上書きによるGit不在を含む)に、Step 1にはない代表fixture(verifyの各status、reportあり、
# markdown、Git不在のverify、Context Digest)を加え、単一workspaceの非生成fixtureから
# 各operation・各stdout種別・reportあり・git:false・gitVersion指定を代表させる。
EXTRA_FIXTURE_IDS = [
    "SINGLE-055", "SINGLE-056", "SINGLE-060", "SINGLE-068",
    "SINGLE-071-01", "SINGLE-071-02", "SINGLE-071-03", "SINGLE-071-04",
    "SINGLE-104-01", "SINGLE-104-02", "SINGLE-104-03",
    "SINGLE-105-01", "SINGLE-105-02", "SINGLE-042",
]
REPRESENTATIVE_FIXTURE_IDS = _step1_fixture_ids() + EXTRA_FIXTURE_IDS

# mutateの3種(json/text/none)を検査する最小subset。
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
    """ADR-052 Decision 5前段: 期待どおりの偽Coreでは選んだfixtureが全件passedになる。"""

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
    """出力を1箇所改変した偽Coreでは、改変したfixtureだけがfailedになり他はpassedのまま。"""

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
        """標準出力は正しいまま、`.spec/reports/`へ保存するreport内容だけを改変した場合。

        report内容もCore結果契約8の結果JSONそのものとして、normalizer適用後に期待JSONと
        完全構造比較する(適合fixture仕様2)。標準出力は正しいのでstdout比較は一致するが、
        report内容の不一致で当該fixtureだけがfailedになるはずである。
        """
        subset = ["SINGLE-001", "SINGLE-071-01", "SINGLE-073-01"]
        with tempfile.TemporaryDirectory(prefix="bitz-fakecore-mutate-report-") as tmp:
            core_dir = Path(tmp) / "core"
            build_fake_core(core_dir, subset, mutate_report="SINGLE-071-01")
            report = _run_harness(core_dir, subset)
        self._assert_only_one_failed(report, "SINGLE-071-01")
        mutated = next(entry for entry in report["fixtures"] if entry["id"] == "SINGLE-071-01")
        self.assertTrue(any("report(" in difference for difference in mutated["differences"]), mutated)


if __name__ == "__main__":
    unittest.main()
