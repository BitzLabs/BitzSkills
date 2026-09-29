"""Gate Cの証拠集約を偽の成功報告で通せないことを検査する。"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/bitz-core"))
sys.path.insert(0, str(ROOT / "fixtures"))

import gate_c
from conformance.selection import step_ids

SPEC = importlib.util.spec_from_file_location(
    "certify_gate_c", ROOT / "tests/bitz-core/certify_gate_c.py")
certify_gate_c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(certify_gate_c)

COMMIT = "a" * 40
IDS = step_ids(5)
EMPTY = hashlib.sha256(b"").hexdigest()
REFERENCE_MANIFEST = {
    "schemaVersion": "1.0",
    "environmentId": "core-1-linux-wsl2-ryzen-9-9900x",
    "comparisonKey": {
        "os": "Linux",
        "platformClass": "WSL2",
        "architecture": "x86_64",
        "cpuModel": "AMD Ryzen 9 9900X 12-Core Processor",
        "logicalCores": 24,
        "minimumRamBytes": 8_053_063_680,
        "storageClass": "wsl2-virtual-disk",
        "filesystem": "ext4",
    },
    "requiredTools": {
        "pythonImplementation": "CPython",
        "pythonVersion": "3.12.x",
        "minimumGitVersion": "2.30",
        "memoryAccounting": "cgroup-v2-process-tree",
    },
    "isolation": {"networkDisabled": True, "persistentCoreCache": False,
                  "report": False, "parallelCases": False},
}


def evidence(role: str) -> dict:
    environment_id = ("minimum-cpython-3-12" if role == "minimum"
                      else REFERENCE_MANIFEST["environmentId"])
    host = ({
        "kernel": "6.6.87.2-microsoft-standard-WSL2",
        "cpuModel": "AMD Ryzen 9 9900X 12-Core Processor",
        "logicalCores": 24,
        "platformClass": "WSL2",
        "storageClass": "wsl2-virtual-disk",
    } if role == "reference" else {
        "kernel": "6.8.0-generic",
        "cpuModel": "Minimum CI CPU",
        "logicalCores": 4,
        "platformClass": "native-linux",
        "storageClass": "local-ssd",
    })
    report = {
        "core": f"/{role}/plugins/bitz-core",
        "environment": {"python": "3.12.3", "git": "git version 2.43.0"},
        "fixtures": [{"id": identifier, "result": "passed", "differences": []}
                     for identifier in IDS],
        "counts": {"passed": len(IDS), "failed": 0, "error": 0},
        "allPassed": True,
    }
    return {
        "schemaVersion": 1,
        "commit": COMMIT,
        "role": role,
        "environmentId": environment_id,
        "referenceManifestSha256": (gate_c.manifest_digest(REFERENCE_MANIFEST)
                                    if role == "reference" else None),
        "requestedPython": "3.12",
        "checkoutId": f"checkout-{role}",
        "cleanBefore": True,
        "cleanAfter": True,
        "environment": {
            "system": "Linux",
            "machine": "x86_64",
            "python": "3.12.3",
            "implementation": "CPython",
            "executable": f"/{role}/bin/python",
            "git": "git version 2.43.0",
            "ramBytes": 16_106_127_360,
            "filesystem": "ext4",
            "memoryAccounting": "cgroup-v2-process-tree",
            **host,
        },
        "conformance": {"exitCode": 0, "report": report, "stderrSha256": EMPTY},
        "unit": {"exitCode": 0, "testsRun": 552,
                 "stdoutSha256": EMPTY, "stderrSha256": EMPTY},
        "errors": [],
    }


def performance_evidence() -> dict:
    report = {
        "status": "Passed",
        "schemas": 8,
        "inputs": 12,
        "generationRunsPerDataset": 2,
        "shapeRejectionChecks": 2,
        "datasets": [{"datasetId": "core-single-v1"}],
        "baselines": [{
            "coreCommit": "b" * 40,
            "environmentId": REFERENCE_MANIFEST["environmentId"],
            "cases": 7,
            "status": "Passed",
            "sha256": EMPTY,
        }],
    }
    encoded = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    return {
        "schemaVersion": 1,
        "commit": COMMIT,
        "checkoutId": "checkout-performance",
        "cleanBefore": True,
        "cleanAfter": True,
        "exitCode": 0,
        "report": report,
        "stdoutSha256": hashlib.sha256(encoded).hexdigest(),
        "stderrSha256": EMPTY,
        "errors": [],
    }


def collected(rows=None):
    return gate_c.collect(rows or [evidence("minimum"), evidence("reference")],
                          commit=COMMIT, fixture_ids=IDS,
                          reference_manifest=REFERENCE_MANIFEST,
                          performance_evidence=performance_evidence())


class CollectionTests(unittest.TestCase):
    def test_foundation_and_performance_pass_but_leave_gate_c_pending(self):
        result = collected()
        self.assertEqual(result["gateCFoundation"], "Passed")
        self.assertEqual(result["gateCPerformance"], "Passed")
        self.assertEqual(result["gateC"], "Pending")
        self.assertEqual(result["fixtureCount"], 320)
        self.assertEqual(result["referenceManifestSha256"],
                         gate_c.manifest_digest(REFERENCE_MANIFEST))
        self.assertEqual(result["pending"], ["unresolved P0/P1 closure"])
        self.assertEqual(set(result["environments"]), {"minimum", "reference"})
        self.assertEqual(result["performance"]["baselines"][0]["cases"], 7)

    def test_forged_performance_success_is_rejected(self):
        def assert_rejected(performance):
            with self.assertRaises(ValueError):
                gate_c.collect(
                    [evidence("minimum"), evidence("reference")],
                    commit=COMMIT, fixture_ids=IDS,
                    reference_manifest=REFERENCE_MANIFEST,
                    performance_evidence=performance,
                )

        mutations = {
            "schemaVersion": 2,
            "commit": "c" * 40,
            "cleanBefore": False,
            "cleanAfter": False,
            "exitCode": 1,
            "errors": ["failure"],
            "stdoutSha256": "bad",
            "stderrSha256": "",
        }
        for key, value in mutations.items():
            with self.subTest(key=key):
                performance = performance_evidence()
                performance[key] = value
                assert_rejected(performance)

        report_mutations = {
            "status": "Failed",
            "schemas": 0,
            "inputs": 0,
            "generationRunsPerDataset": 1,
            "shapeRejectionChecks": 0,
            "baselines": [],
        }
        for key, value in report_mutations.items():
            with self.subTest(report=key):
                performance = performance_evidence()
                performance["report"][key] = value
                assert_rejected(performance)

        baseline_mutations = {
            "coreCommit": "bad",
            "environmentId": "another-environment",
            "cases": 0,
            "status": "Failed",
            "sha256": "bad",
        }
        for key, value in baseline_mutations.items():
            with self.subTest(baseline=key):
                performance = performance_evidence()
                performance["report"]["baselines"][0][key] = value
                assert_rejected(performance)

        duplicate = performance_evidence()
        duplicate["report"]["baselines"].append(
            copy.deepcopy(duplicate["report"]["baselines"][0]))
        assert_rejected(duplicate)

    def test_missing_duplicate_or_reused_environment_is_rejected(self):
        cases = [
            [evidence("minimum")],
            [evidence("minimum"), evidence("minimum")],
            [evidence("minimum"), evidence("reference"), evidence("reference")],
        ]
        same_id = [evidence("minimum"), evidence("reference")]
        same_id[1]["environmentId"] = same_id[0]["environmentId"]
        cases.append(same_id)
        same_checkout = [evidence("minimum"), evidence("reference")]
        same_checkout[1]["checkoutId"] = same_checkout[0]["checkoutId"]
        cases.append(same_checkout)
        wrong_id = [evidence("minimum"), evidence("reference")]
        wrong_id[1]["environmentId"] = "another-reference"
        cases.append(wrong_id)
        same_host = [evidence("minimum"), evidence("reference")]
        same_host[0]["environment"] = copy.deepcopy(same_host[1]["environment"])
        cases.append(same_host)
        for rows in cases:
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError):
                collected(rows)

    def test_wrong_provenance_dirty_or_reported_error_is_rejected(self):
        mutations = {
            "commit": "b" * 40,
            "schemaVersion": 2,
            "cleanBefore": False,
            "cleanAfter": False,
            "errors": ["failure"],
        }
        for key, value in mutations.items():
            with self.subTest(key=key):
                rows = [evidence("minimum"), evidence("reference")]
                rows[0][key] = value
                with self.assertRaises(ValueError):
                    collected(rows)

    def test_non_linux_non_cpython_or_wrong_minor_is_rejected(self):
        mutations = {"system": "Darwin", "implementation": "PyPy", "python": "3.13.0",
                     "executable": ""}
        for key, value in mutations.items():
            with self.subTest(key=key):
                rows = [evidence("minimum"), evidence("reference")]
                rows[0]["environment"][key] = value
                with self.assertRaises(ValueError):
                    collected(rows)

    def test_reference_manifest_hash_is_required(self):
        rows = [evidence("minimum"), evidence("reference")]
        rows[1]["referenceManifestSha256"] = EMPTY
        with self.assertRaises(ValueError):
            collected(rows)

    def test_reference_environment_must_match_manifest(self):
        mutations = {
            "system": "Darwin",
            "machine": "aarch64",
            "cpuModel": "Another CPU",
            "logicalCores": 8,
            "platformClass": "native-linux",
            "ramBytes": REFERENCE_MANIFEST["comparisonKey"]["minimumRamBytes"] - 1,
            "storageClass": "unknown",
            "filesystem": "xfs",
            "implementation": "PyPy",
            "memoryAccounting": "unsupported",
            "python": "3.13.0",
            "git": "git version 2.29.9",
        }
        for key, value in mutations.items():
            with self.subTest(key=key):
                rows = [evidence("minimum"), evidence("reference")]
                rows[1]["environment"][key] = value
                with self.assertRaises(ValueError):
                    collected(rows)

    def test_forged_conformance_success_is_rejected(self):
        modes = ("exit", "allPassed", "count", "missing", "duplicate",
                 "unknown", "failed", "difference", "python")
        for mode in modes:
            with self.subTest(mode=mode):
                rows = [evidence("minimum"), evidence("reference")]
                conformance = rows[0]["conformance"]
                report = conformance["report"]
                if mode == "exit":
                    conformance["exitCode"] = 1
                elif mode == "allPassed":
                    report["allPassed"] = False
                elif mode == "count":
                    report["counts"]["passed"] -= 1
                elif mode == "missing":
                    report["fixtures"].pop()
                elif mode == "duplicate":
                    report["fixtures"][-1] = copy.deepcopy(report["fixtures"][0])
                elif mode == "unknown":
                    report["fixtures"][0]["id"] = "SINGLE-999"
                elif mode == "failed":
                    report["fixtures"][0]["result"] = "failed"
                elif mode == "difference":
                    report["fixtures"][0]["differences"] = ["wrong"]
                else:
                    report["environment"]["python"] = "3.13.0"
                with self.assertRaises(ValueError):
                    collected(rows)

    def test_failed_or_empty_unit_run_is_rejected(self):
        for key, value in (("exitCode", 1), ("testsRun", 0), ("testsRun", 551),
                           ("requestedPython", ""),
                           ("stdoutSha256", "bad"), ("stderrSha256", "")):
            with self.subTest(key=key):
                rows = [evidence("minimum"), evidence("reference")]
                target = rows[0] if key == "requestedPython" else rows[0]["unit"]
                target[key] = value
                with self.assertRaises(ValueError):
                    collected(rows)

    def test_collect_command_runs_performance_audit_for_target_commit(self):
        performance = performance_evidence()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = []
            for role in gate_c.ROLES:
                path = root / f"{role}.json"
                path.write_text(json.dumps(evidence(role)), encoding="utf-8")
                inputs.extend(["--input", str(path)])
            output = root / "result.json"
            with (mock.patch.object(certify_gate_c, "load_reference_manifest_at",
                                    return_value=REFERENCE_MANIFEST),
                  mock.patch.object(certify_gate_c, "run_performance_evidence",
                                    return_value=(performance, [])) as audit):
                code = certify_gate_c.main([
                    "collect", *inputs, "--commit", COMMIT, "--output", str(output),
                ])
            self.assertEqual(code, 0)
            audit.assert_called_once_with(COMMIT)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["gateCPerformance"], "Passed")
            self.assertEqual(result["pending"], gate_c.PENDING)

    def test_unit_count_parser_accepts_unittest_summary_only(self):
        self.assertEqual(certify_gate_c.unit_test_count(
            b"", b"Ran 552 tests in 3.000s\n\nOK\n"), 552)
        self.assertIsNone(certify_gate_c.unit_test_count(b"552 passed", b""))

    def test_platform_and_storage_class_for_wsl2(self):
        self.assertEqual(certify_gate_c.platform_class(
            "6.6.87.2-microsoft-standard-WSL2"), "WSL2")
        self.assertEqual(certify_gate_c.platform_class("6.8.0-generic"),
                         "native-linux")
        self.assertEqual(certify_gate_c.storage_class("/dev/sdc", "WSL2"),
                         "wsl2-virtual-disk")


if __name__ == "__main__":
    unittest.main()
