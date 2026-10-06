"""製品本文の提供境界と一次読取りログを検査する。"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("production_routing_host", ROOT / "evals/skills/routing/host.py")
host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host)


class RoutingHostTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".venv").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".venv")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.snapshot = self.base / "snapshot"
        self.snapshot.mkdir()
        skills, resources = [], {}
        for name in sorted(host.SKILLS):
            package = "bitz-core" if name == "bitz-core" else "bitz-sdd" if name.startswith("sdd-") else "bitz-quality"
            relative = f"resources/{package}/skills/{name}/SKILL.md"
            path = self.snapshot / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {name}\nこれは合成の固定本文。", encoding="utf-8")
            resources[relative] = host.sha(path.read_bytes())
            skills.append({"name": name, "description": "合成説明", "version": "0.1.0", "path": relative})
        self.manifest = {"schemaVersion": "1.0", "scope": "production-resource-snapshot-only", "sourceCommit": "a" * 40,
                         "candidateVersion": "synthetic", "skills": skills, "resources": resources,
                         "notForModel": "HIDDEN_EXPECTATION_SENTINEL"}
        self.log = self.base / "host.jsonl"
        self.persist_manifest()

    def persist_manifest(self):
        raw = json.dumps(self.manifest, ensure_ascii=False).encode()
        (self.snapshot / "manifest.json").write_bytes(raw)
        self.digest = hashlib.sha256(raw).hexdigest()

    def open_host(self):
        value = host.Host(self.snapshot, self.digest, self.log)
        self.addCleanup(value.close)
        return value

    def test_exact_reads_and_logs_have_actual_source_and_hash(self):
        value = self.open_host()
        self.assertEqual({t["name"] for t in value.tools}, {"list_resources", "read_resource"})
        listing = value.call("list_resources", {})
        self.assertNotIn("HIDDEN_EXPECTATION_SENTINEL", json.dumps(listing))
        path = self.manifest["skills"][0]["path"]
        response = value.call("read_resource", {"path": path})
        self.assertFalse(response["isError"])
        result = json.loads(response["content"][0]["text"])
        self.assertEqual(result["content"], (self.snapshot / path).read_text())
        self.assertEqual(result["sha256"], self.manifest["resources"][path])
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual([c["sequence"] for c in calls], [1, 2])
        self.assertEqual(calls[-1]["result"], result)
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o600)

    def test_hidden_files_absolute_traversal_and_commands_are_not_opened(self):
        value = self.open_host()
        hidden = self.snapshot / "cases.json"
        hidden.write_text("HIDDEN_INPUT_SENTINEL")
        with patch.object(Path, "read_bytes", side_effect=AssertionError("unexpected read")):
            for path in ["cases.json", str(hidden), "../cases.json", "resources/bitz-core/../../cases.json", "resources/bitz-core/.env"]:
                result = value.call("read_resource", {"path": path})
                self.assertTrue(result["isError"])
                self.assertNotIn("HIDDEN_INPUT_SENTINEL", json.dumps(result))
            for name, arguments in [("run_bitz", {}), ("run_fixture_test", {}), ("shell", {"command": "cat cases.json"}),
                                    ("read_resource", {"path": self.manifest["skills"][0]["path"], "extra": True}),
                                    ("list_resources", {"path": "cases.json"}), ("read_resource", [])]:
                self.assertTrue(value.call(name, arguments)["isError"])

    def test_changed_body_is_rejected_after_initial_validation(self):
        value = self.open_host()
        path = self.manifest["skills"][0]["path"]
        (self.snapshot / path).write_text("UNTRUSTED_REPLACEMENT")
        response = value.call("read_resource", {"path": path})
        self.assertTrue(response["isError"])
        self.assertNotIn("UNTRUSTED_REPLACEMENT", json.dumps(response))
        self.assertFalse(json.loads(self.log.read_text().splitlines()[-1])["accepted"])

    def test_manifest_pin_and_resource_pin_fail_before_log_creation(self):
        with self.assertRaises(ValueError):
            host.Host(self.snapshot, "0" * 64, self.log)
        self.assertFalse(self.log.exists())
        (self.snapshot / self.manifest["skills"][0]["path"]).write_text("changed")
        with self.assertRaises(ValueError):
            self.open_host()
        self.assertFalse(self.log.exists())

    def test_symlink_resource_and_parent_are_rejected_even_for_same_bytes(self):
        path = self.snapshot / self.manifest["skills"][0]["path"]
        outside = self.base / "same-body.md"
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.open_host()
        path.unlink()
        path.write_bytes(outside.read_bytes())
        parent = path.parent
        moved = self.base / "moved-skill"
        parent.rename(moved)
        parent.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.open_host()
        self.assertFalse(self.log.exists())

    def test_invalid_manifest_path_is_rejected_before_any_resource_read(self):
        self.manifest["resources"]["resources/bitz-core/.env"] = "0" * 64
        self.persist_manifest()
        with patch.object(host.Host, "read", side_effect=AssertionError("opened a resource")):
            with self.assertRaises(ValueError):
                self.open_host()
        self.assertFalse(self.log.exists())

    def test_existing_log_and_log_inside_candidate_are_never_overwritten(self):
        self.log.write_text("ORIGINAL_LOG")
        with self.assertRaises(FileExistsError):
            self.open_host()
        self.assertEqual(self.log.read_text(), "ORIGINAL_LOG")
        with self.assertRaises(ValueError):
            host.Host(self.snapshot, self.digest, self.snapshot / "new-log.jsonl")
        self.assertFalse((self.snapshot / "new-log.jsonl").exists())

    def test_symlink_log_parent_is_rejected_without_write(self):
        link = self.base / "link"
        link.symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(ValueError):
            host.Host(self.snapshot, self.digest, link / "new.jsonl")
        self.assertFalse((self.base / "new.jsonl").exists())

    def test_stdio_rpc_round_trip_and_unknown_method(self):
        value = self.open_host()
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "read_resource", "arguments": {"path": self.manifest["skills"][0]["path"]}}},
            {"jsonrpc": "2.0", "id": 4, "method": "resources/read"},
        ]
        output = io.StringIO()
        with patch.object(sys, "stdin", io.StringIO("\n".join(json.dumps(r) for r in requests))), patch.object(sys, "stdout", output):
            host.serve(value)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([r["id"] for r in responses], [1, 2, 3, 4])
        self.assertEqual(responses[0]["result"]["serverInfo"]["version"], host.VERSION)
        self.assertFalse(responses[2]["result"]["isError"])
        self.assertEqual(responses[3]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
