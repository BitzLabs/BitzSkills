"""性能ランナーの集約、閾値、環境の比較を偽の成功で通せないことを検査する。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "run_benchmarks", ROOT / "fixtures/performance/run_benchmarks.py")
run_benchmarks = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run_benchmarks
SPEC.loader.exec_module(run_benchmarks)

Measurement = run_benchmarks.Measurement
Series = run_benchmarks.Series


def measurement(wall: float = 10, memory: int = 100, code: int = 0) -> Measurement:
    return Measurement(wall_ms=wall, peak_rss_bytes=memory, exit_code=code)


def series(walls=(10, 11, 12, 13, 14), memory: int = 100, code: int = 0) -> Series:
    return Series(
        cold=measurement(20, memory, code),
        measured=tuple(measurement(wall, memory, code) for wall in walls),
    )


def accepted_baseline():
    manifest = {
        "environmentId": "reference",
        "comparisonKey": {
            "os": "Linux",
            "platformClass": "WSL2",
            "architecture": "x86_64",
            "cpuModel": "Expected",
            "logicalCores": 24,
            "minimumRamBytes": 8_000,
            "storageClass": "wsl2-virtual-disk",
            "filesystem": "ext4",
        },
        "requiredTools": {
            "pythonVersion": "3.12.x",
            "minimumGitVersion": "2.30",
            "memoryAccounting": "cgroup-v2-process-tree",
        },
    }
    plan = {
        "cases": [
            {
                "id": "fixed",
                "maxMedianWallMs": 20,
                "maxPeakRssBytes": 200,
            },
            {
                "id": "derived",
                "baseline": ["python3", "noop.py"],
                "maxDerivedOverheadMs": 5,
                "maxPeakRssBytes": 200,
            },
        ],
    }
    fixed = {
        "id": "fixed",
        "coldWallMs": 20,
        "wallMs": [10, 11, 12, 13, 14],
        "medianWallMs": 12,
        "peakRssBytes": [100] * 5,
        "maximumPeakRssBytes": 100,
        "exitCodes": [0] * 5,
        "status": "passed",
    }
    derived = {
        "id": "derived",
        "coldWallMs": 20,
        "wallMs": [10, 11, 12, 13, 14],
        "medianWallMs": 12,
        "peakRssBytes": [100] * 5,
        "maximumPeakRssBytes": 100,
        "exitCodes": [0] * 5,
        "baselineWallMs": [8, 9, 10, 11, 12],
        "baselineMedianWallMs": 10,
        "baselineExitCodes": [0] * 5,
        "derivedOverheadMs": 2,
        "status": "passed",
    }
    result = {
        "environmentId": "reference",
        "datasetDigests": {"dataset": "sha256:" + "a" * 64},
        "observedEnvironment": {
            "os": "Linux", "platformClass": "WSL2", "architecture": "x86_64",
            "cpuModel": "Expected", "logicalCores": 24, "ramBytes": 16_000,
            "storageClass": "wsl2-virtual-disk", "filesystem": "ext4",
            "python": "3.12.3", "git": "git version 2.43.0",
            "memoryAccounting": "cgroup-v2-process-tree",
        },
        "comparability": "comparable",
        "comparisonMismatches": [],
        "coreCommit": "a" * 40,
        "cases": [fixed, derived],
    }
    datasets = {"dataset": {"expectedTreeDigest": "sha256:" + "a" * 64}}
    return result, plan, manifest, datasets


class FakeExecutor:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = []

    def measure(self, argv, cwd, environment):
        self.calls.append((argv, cwd, environment))
        return next(self.values)


class PerformanceRunnerTests(unittest.TestCase):
    def test_fixed_budget_case_passes_and_fails_closed(self):
        case = {
            "id": "fixed",
            "maxMedianWallMs": 20,
            "maxPeakRssBytes": 200,
        }
        result = run_benchmarks.build_case_result(case, series(), None, True)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["medianWallMs"], 12)

        for changed in (
            series(walls=(20, 21, 22, 23, 24)),
            series(memory=201),
            series(code=1),
        ):
            with self.subTest(changed=changed):
                result = run_benchmarks.build_case_result(case, changed, None, True)
                self.assertEqual(result["status"], "failed")

    def test_not_comparable_does_not_hide_execution_failure(self):
        case = {
            "id": "fixed",
            "maxMedianWallMs": 20,
            "maxPeakRssBytes": 200,
        }
        self.assertEqual(
            run_benchmarks.build_case_result(case, series(), None, False)["status"],
            "not_comparable",
        )
        self.assertEqual(
            run_benchmarks.build_case_result(case, series(code=1), None, False)["status"],
            "failed",
        )

    def test_derived_overhead_retains_both_series_and_clamps_at_zero(self):
        case = {
            "id": "derived",
            "maxDerivedOverheadMs": 5,
            "maxPeakRssBytes": 200,
        }
        result = run_benchmarks.build_case_result(
            case, series(walls=(5, 5, 5, 5, 5)),
            series(walls=(10, 10, 10, 10, 10)), True)
        self.assertEqual(result["derivedOverheadMs"], 0)
        self.assertEqual(result["baselineWallMs"], [10, 10, 10, 10, 10])
        self.assertEqual(result["baselineExitCodes"], [0] * 5)
        self.assertEqual(result["status"], "passed")

        failed = run_benchmarks.build_case_result(
            case, series(walls=(20, 20, 20, 20, 20)),
            series(walls=(10, 10, 10, 10, 10)), True)
        self.assertEqual(failed["derivedOverheadMs"], 10)
        self.assertEqual(failed["status"], "failed")

    def test_series_excludes_cold_and_warmup_from_measured_values(self):
        values = [measurement(number) for number in range(7)]
        executor = FakeExecutor(values)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            measured = run_benchmarks.measure_series(
                executor, ["/bin/true"], root, root / "environment", 1, 5)
        self.assertEqual(measured.cold.wall_ms, 0)
        self.assertEqual([sample.wall_ms for sample in measured.measured],
                         [2, 3, 4, 5, 6])
        self.assertEqual(len(executor.calls), 7)

    def test_environment_comparison_reports_each_mismatch(self):
        manifest = {
            "comparisonKey": {
                "os": "Linux",
                "platformClass": "WSL2",
                "architecture": "x86_64",
                "cpuModel": "Expected",
                "logicalCores": 24,
                "minimumRamBytes": 8_000,
                "storageClass": "wsl2-virtual-disk",
                "filesystem": "ext4",
            },
            "requiredTools": {
                "pythonVersion": "3.12.x",
                "minimumGitVersion": "2.30",
                "memoryAccounting": "cgroup-v2-process-tree",
            },
        }
        environment = {
            "os": "Linux",
            "platformClass": "native-linux",
            "architecture": "x86_64",
            "cpuModel": "Other",
            "logicalCores": 4,
            "ramBytes": 1,
            "storageClass": "local-ssd",
            "filesystem": "xfs",
            "python": "3.13.0",
            "git": "git version 2.29.9",
            "memoryAccounting": "unsupported",
        }
        self.assertEqual(
            run_benchmarks.comparison_mismatches(environment, manifest),
            ["cpuModel", "filesystem", "git", "logicalCores", "memoryAccounting",
             "platformClass", "python", "ramBytes", "storageClass"],
        )

    def test_accepted_baseline_recomputes_all_gate_values(self):
        result, plan, manifest, datasets = accepted_baseline()
        self.assertEqual(
            run_benchmarks.validate_accepted_baseline(
                result, plan, manifest, datasets),
            {
                "coreCommit": "a" * 40,
                "environmentId": "reference",
                "cases": 2,
                "status": "Passed",
            },
        )

    def test_accepted_baseline_rejects_forged_success(self):
        for mutate in (
            lambda result: result["cases"][0].update(medianWallMs=999),
            lambda result: result["cases"][0].update(maximumPeakRssBytes=201),
            lambda result: result["cases"][1].update(derivedOverheadMs=0),
            lambda result: result["cases"][0]["exitCodes"].__setitem__(0, 1),
            lambda result: result["observedEnvironment"].update(cpuModel="Other"),
            lambda result: result.update(datasetDigests={"dataset": "sha256:" + "b" * 64}),
        ):
            with self.subTest(mutate=mutate):
                result, plan, manifest, datasets = accepted_baseline()
                mutate(result)
                with self.assertRaises(run_benchmarks.BenchmarkError):
                    run_benchmarks.validate_accepted_baseline(
                        result, plan, manifest, datasets)

    def test_cgroup_path_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "user.slice/unit.service"
            target.mkdir(parents=True)
            self.assertEqual(
                run_benchmarks.resolve_cgroup_path("/user.slice/unit.service", root),
                target.resolve(),
            )
            with self.assertRaises(run_benchmarks.BenchmarkError):
                run_benchmarks.resolve_cgroup_path("/../../outside", root)

    def test_repository_stages_only_generated_top_level_paths(self):
        calls = []
        original = run_benchmarks.checked

        def record(argv, **kwargs):
            calls.append(argv)
            class Result:
                stdout = ""
            return Result()

        try:
            run_benchmarks.checked = record
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / ".spec").mkdir()
                (root / "tests").mkdir()
                run_benchmarks.initialize_repository(root)
        finally:
            run_benchmarks.checked = original
        self.assertIn(["git", "add", "--", ".spec", "tests"], calls)
        self.assertFalse(any(argv[:2] == ["git", "add"] and "--all" in argv
                             for argv in calls))


if __name__ == "__main__":
    unittest.main()
