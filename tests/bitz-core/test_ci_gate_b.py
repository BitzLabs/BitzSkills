"""CI分割・集約の陰性対照。欠落や改変された成功報告でGate Bを通さない。"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/bitz-core"))
import ci_gate_b as ci
import plan_conformance as planning
from conformance.reports import merge_reports
from conformance.selection import partition, partition_plan, predicted_seconds, selected_ids, step_ids
from conformance.timing import timed_call


def evidence_set(step=5, shards=4, replicas=2):
    groups = partition(step_ids(step), shards)
    result = []
    for replica in range(1, replicas + 1):
        for shard, group in enumerate(groups, 1):
            report = {"core": f"/checkout-{replica}-{shard}/plugins/bitz-core", "environment": {"python": "3.12.3"},
                      "fixtures": [{"id": i, "result": "passed", "differences": []} for i in group],
                      "counts": {"passed": len(group), "failed": 0, "error": 0}, "allPassed": True}
            result.append({"schemaVersion": 1, "commit": "a" * 40, "step": step,
                           "replica": replica, "shard": shard, "shards": shards,
                           "runId": "run-1", "checkoutId": f"{replica}-{shard}",
                           "cleanBefore": True, "cleanAfter": True, "errors": [],
                           "conformance": {"exitCode": 0, "report": report},
                           "parserAdapter": {"exitCode": 0, "stdout": 'all parser fixtures passed\n',
                                             "error": None, "stderr": ""} if step >= 2 and shard == 1 else None})
    return result


def collect(evidence, **kwargs):
    return ci.collect(evidence, step=5, shards=4, replicas=kwargs.get("replicas", 2),
                      commit="a" * 40, run_id="run-1")


class ShardingTests(unittest.TestCase):
    def test_all_steps_have_exact_coverage_and_stable_order(self):
        for step in range(1, 6):
            ids = step_ids(step)
            groups = partition(ids, 4)
            self.assertEqual(groups, partition(ids, 4))
            self.assertEqual(sorted(i for group in groups for i in group), sorted(ids))
            for group in groups:
                self.assertEqual(group, [i for i in ids if i in group])

    def test_heaviest_limit_cases_are_distributed(self):
        groups = partition(step_ids(5), 4)
        heavy = {"MULTI-020-09", "MULTI-020-10", "MULTI-020-11", "MULTI-020-12"}
        self.assertEqual([len(heavy.intersection(group)) for group in groups], [1, 1, 1, 1])

    def test_ci_measurements_produce_balanced_predictions(self):
        groups = partition(step_ids(5), 4)
        fixture_seconds = [predicted_seconds(group) for group in groups]
        self.assertLess(max(fixture_seconds) - min(fixture_seconds), 0.2)
        plan = partition_plan(step_ids(5), 4)
        self.assertTrue(all(200 <= row["predictedSeconds"] <= 230 for row in plan))
        self.assertEqual(sum(row["fixtureCount"] for row in plan), 318)

    def test_ci_plan_displays_prediction_for_every_worker(self):
        plan = planning.build_plan(step=5, shards=4, replicas=2)
        workers = plan["matrix"]["include"]
        self.assertEqual([(row["replica"], row["shard"]) for row in workers],
                         [(replica, shard) for replica in (1, 2) for shard in range(1, 5)])
        self.assertEqual({row["predicted"] for row in workers}, {"3分35秒"})
        summary = planning.markdown(plan)
        self.assertIn("GitHub Actions run 36248419060", summary)
        self.assertEqual(summary.count("| 3分35秒 |"), 4)
        pull_request = planning.build_plan(step=5, shards=4, replicas=1)
        self.assertEqual([(row["replica"], row["shard"])
                          for row in pull_request["matrix"]["include"]],
                         [(1, shard) for shard in range(1, 5)])

    def test_standard_and_scale_are_disjoint_and_exhaustive(self):
        ids = step_ids(5)
        normal = selected_ids(ids, "standard")
        scale = selected_ids(ids, "scale")
        self.assertFalse(set(normal) & set(scale))
        self.assertEqual(set(normal) | set(scale), set(ids))
        self.assertEqual(len(scale), 24)

    def test_invalid_step_and_shard_fail_closed(self):
        for step in (0, 6, -1):
            with self.assertRaises(ValueError):
                step_ids(step)
        for shard, shards in ((0, 4), (5, 4), (1, 0), (1, 999)):
            with self.assertRaises(ValueError):
                selected_ids(step_ids(5), shard=shard, shards=shards)


class CollectionTests(unittest.TestCase):
    def test_two_independent_complete_rounds_pass_gate_b(self):
        result = collect(evidence_set())
        self.assertEqual(result["gateB"], {"step": 5, "result": "Passed"})
        self.assertEqual(result["fixtureCount"], len(step_ids(5)))
        self.assertEqual(result["reports"][0], result["reports"][1])

    def test_pull_request_does_not_claim_gate_b(self):
        result = collect(evidence_set(replicas=1), replicas=1)
        self.assertEqual(result["result"], "Passed")
        self.assertNotIn("gateB", result)

    def test_step_one_needs_no_parser(self):
        result = ci.collect(evidence_set(step=1), step=1, shards=4, replicas=2,
                            commit="a" * 40, run_id="run-1")
        self.assertEqual(result["gateB"]["result"], "Passed")

    def test_missing_duplicate_and_extra_workers_rejected(self):
        rows = evidence_set()
        for altered in ([], rows[:-1], rows + [rows[0]]):
            with self.assertRaises(ValueError):
                collect(altered)

    def test_wrong_provenance_dirty_or_failed_worker_rejected(self):
        mutations = {"commit": "b" * 40, "runId": "another-run", "step": 4, "shards": 3,
                     "schemaVersion": 2, "checkoutId": "1-2", "cleanBefore": False,
                     "cleanAfter": False, "errors": ["timeout"]}
        for key, value in mutations.items():
            with self.subTest(key=key):
                rows = evidence_set()
                rows[0][key] = value
                with self.assertRaises(ValueError):
                    collect(rows)

    def test_missing_duplicate_unknown_fixture_rejected(self):
        for mode in ("missing", "duplicate", "unknown", "swapped"):
            with self.subTest(mode=mode):
                rows = evidence_set()
                entries = rows[0]["conformance"]["report"]["fixtures"]
                if mode == "missing": entries.pop()
                elif mode == "duplicate": entries.append(copy.deepcopy(entries[0]))
                elif mode == "unknown": entries[0]["id"] = "SINGLE-999"
                else: entries[0], entries[1] = entries[1], entries[0]
                with self.assertRaises(ValueError):
                    collect(rows)

    def test_forged_pass_and_nonzero_exit_rejected(self):
        for mode in ("counts", "difference", "failed", "allPassed", "exit"):
            with self.subTest(mode=mode):
                rows = evidence_set()
                conformance = rows[0]["conformance"]
                report = conformance["report"]
                if mode == "counts": report["counts"]["passed"] += 1
                elif mode == "difference": report["fixtures"][0]["differences"] = ["wrong output"]
                elif mode == "failed": report["fixtures"][0]["result"] = "failed"
                elif mode == "allPassed": report["allPassed"] = False
                else: conformance["exitCode"] = 1
                with self.assertRaises(ValueError):
                    collect(rows)

    def test_failed_results_with_consistent_counts_still_rejected(self):
        rows = evidence_set()
        r = rows[0]["conformance"]["report"]
        r["fixtures"][0].update(result="failed", differences=["wrong"])
        r["counts"]["passed"] -= 1
        r["counts"]["failed"] += 1
        r["allPassed"] = False
        with self.assertRaises(ValueError): collect(rows)

    def test_environment_must_match_within_and_across_rounds(self):
        for indexes in ([0], [0, 1, 2, 3]):
            rows = evidence_set()
            for index in indexes:
                rows[index]["conformance"]["report"]["environment"]["python"] = "3.13.0"
            with self.assertRaises(ValueError): collect(rows)

    def test_parser_missing_failed_wrong_location_and_mismatch_rejected(self):
        for mode in ("missing", "failed", "mismatch", "wrong-location", "empty"):
            with self.subTest(mode=mode):
                rows = evidence_set()
                if mode == "missing": rows[0]["parserAdapter"] = None
                elif mode == "failed": rows[0]["parserAdapter"]["exitCode"] = 1
                elif mode == "mismatch": rows[0]["parserAdapter"]["stdout"] = "different result"
                elif mode == "empty": rows[0]["parserAdapter"]["stdout"] = ""
                else: rows[1]["parserAdapter"] = rows[0]["parserAdapter"]
                with self.assertRaises(ValueError): collect(rows)

    def test_merge_is_equivalent_to_unsplit_fixture_order(self):
        rows = evidence_set(replicas=1)
        ids = step_ids(5)
        report = merge_reports([r["conformance"]["report"] for r in rows], partition(ids, 4), ids)
        self.assertEqual([r["id"] for r in report["fixtures"]], ids)


class TimingTests(unittest.TestCase):
    def test_timing_preserves_result_and_records_failure(self):
        timings = {}
        self.assertEqual(timed_call(timings, "ok", lambda: 42), 42)
        def fail():
            raise RuntimeError("expected")
        with self.assertRaisesRegex(RuntimeError, "expected"):
            timed_call(timings, "failed", fail)
        self.assertEqual(set(timings), {"ok", "failed"})
        self.assertTrue(all(value >= 0 for value in timings.values()))
        self.assertEqual(timed_call(None, "unused", lambda: 42), 42)


if __name__ == "__main__":
    unittest.main()
