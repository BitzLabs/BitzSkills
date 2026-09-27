"""Gate C Phase 1の証拠集約を偽の成功報告で通せないことを検査する。"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

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
    "environmentId": "core-1-linux-reference",
    "comparisonKey": {
        "os": "Linux",
        "architecture": "x86_64",
        "cpuModel": "Reference CPU",
        "logicalCores": 16,
        "minimumRamBytes": 8_053_063_680,
        "storageClass": "local-ssd",
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
            "kernel": "6.8.0",
            "cpuModel": "Reference CPU",
            "logicalCores": 16,
            "ramBytes": 16_106_127_360,
            "storageClass": "local-ssd",
            "filesystem": "ext4",
            "memoryAccounting": "cgroup-v2-process-tree",
        },
        "conformance": {"exitCode": 0, "report": report, "stderrSha256": EMPTY},
        "unit": {"exitCode": 0, "testsRun": 552,
                 "stdoutSha256": EMPTY, "stderrSha256": EMPTY},
        "errors": [],
    }


def collected(rows=None):
    return gate_c.collect(rows or [evidence("minimum"), evidence("reference")],
                          commit=COMMIT, fixture_ids=IDS,
                          reference_manifest=REFERENCE_MANIFEST)


class CollectionTests(unittest.TestCase):
    def test_two_environment_roles_pass_foundation_but_leave_gate_c_pending(self):
        result = collected()
        self.assertEqual(result["gateCFoundation"], "Passed")
        self.assertEqual(result["gateC"], "Pending")
        self.assertEqual(result["fixtureCount"], 320)
        self.assertEqual(result["referenceManifestSha256"],
                         gate_c.manifest_digest(REFERENCE_MANIFEST))
        self.assertEqual(result["pending"], gate_c.PENDING)
        self.assertEqual(set(result["environments"]), {"minimum", "reference"})

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

    def test_unit_count_parser_accepts_unittest_summary_only(self):
        self.assertEqual(certify_gate_c.unit_test_count(
            b"", b"Ran 552 tests in 3.000s\n\nOK\n"), 552)
        self.assertIsNone(certify_gate_c.unit_test_count(b"552 passed", b""))


if __name__ == "__main__":
    unittest.main()
