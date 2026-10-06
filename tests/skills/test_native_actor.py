"""実providerを呼ばず、枠の再利用拒否・capture中断・mount境界を検査する。"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("native_actor_tested", ROOT / "evals/skills/routing/native_actor.py")
actor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actor)


class NativeActorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="native-actor-test-", dir=ROOT / ".venv")
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)

    def launch(self, script, timeout=10):
        return actor.invoke(["/usr/bin/python3", "-c", script], b"", self.directory, timeout)

    def test_success_preserves_non_utf8_raw_bytes(self):
        result = self.launch("import os; os.write(1,b'\\xff\\x00raw'); os.write(2,b'\\xfeerr')")
        self.assertEqual(result["status"], "native_completed")
        self.assertEqual(result["actualExitCode"], 0)
        self.assertEqual((self.directory / "trace.jsonl").read_bytes(), b"\xff\x00raw")
        self.assertEqual((self.directory / "stderr.log").read_bytes(), b"\xfeerr")
        self.assertEqual(os.stat(self.directory / "trace.jsonl").st_mode & 0o777, 0o600)

    def test_nonzero_exit_does_not_become_semantic_pass(self):
        result = self.launch("import os; os.write(2,b'private error'); raise SystemExit(7)")
        self.assertEqual((result["status"], result["actualExitCode"]), ("native_stopped", 7))
        self.assertNotIn("private error", json.dumps(result))
        self.assertFalse(result["automaticRetry"])

    def test_timeout_retains_partial_output(self):
        result = self.launch("import os,time; os.write(1,b'partial'); time.sleep(10)", timeout=0.5)
        self.assertEqual(result["errorType"], "TimeoutExpired")
        self.assertEqual(result["status"], "native_stopped")
        self.assertEqual((self.directory / "trace.jsonl").read_bytes(), b"partial")
        self.assertIsNotNone(result["actualExitCode"])

    def test_keyboard_interrupt_retains_file_backed_bytes(self):
        class Interrupted:
            returncode = None
            pid = 999999999
            def communicate(child, **kwargs):
                raise KeyboardInterrupt()
            def poll(child): return None
        def popen(command, **kwargs):
            kwargs["stdout"].write(b"interrupt-partial")
            return Interrupted()
        with patch.object(actor.subprocess, "Popen", side_effect=popen), \
                patch.object(actor, "stop_process", side_effect=lambda p: setattr(p, "returncode", -15)):
            result = actor.invoke(["fake"], b"", self.directory, 1)
        self.assertEqual((result["errorType"], result["actualExitCode"]), ("KeyboardInterrupt", -15))
        self.assertEqual((self.directory / "trace.jsonl").read_bytes(), b"interrupt-partial")

    def test_spawn_failure_and_result_save_failure_remain_stopped(self):
        with patch.object(actor.subprocess, "Popen", side_effect=FileNotFoundError("private-path")):
            result = actor.invoke(["missing"], b"", self.directory, 1)
        self.assertEqual(result["errorType"], "FileNotFoundError")
        self.assertIsNone(result["actualExitCode"])
        self.assertNotIn("private-path", json.dumps(result))
        other = self.directory / "other"; other.mkdir()
        with patch.object(actor, "exclusive", side_effect=OSError(28, "full")):
            result = actor.invoke(["/usr/bin/true"], b"", other, 1)
        self.assertEqual(result["status"], "native_stopped")
        self.assertEqual(result["resultSaveError"]["errno"], 28)
        self.assertTrue(result["nativeOutputAvailable"])

    def test_fsync_failure_is_not_success(self):
        with patch.object(actor.os, "fsync", side_effect=OSError(28, "full")):
            result = self.launch("print('partial capture')")
        self.assertEqual(result["status"], "native_stopped")
        self.assertGreaterEqual(len(result["outputSaveErrors"]), 1)
        self.assertIn(b"partial capture", (self.directory / "trace.jsonl").read_bytes())

    def test_role_reservation_is_global_across_sources(self):
        ledger = self.directory / "ledger"
        actor.reserve("creator", "a" * 40, ledger)
        with self.assertRaises(FileExistsError): actor.reserve("creator", "b" * 40, ledger)
        actor.reserve("reviewer", "a" * 40, ledger)
        with self.assertRaises(ValueError): actor.reserve("unknown", "a" * 40, ledger)

    def test_namespace_only_writes_approved_phase_and_test_scratch(self):
        repo = self.directory / "repo"; (repo / ".venv/snapshot").mkdir(parents=True)
        ledger = repo / ".venv/ledger"; ledger.mkdir()
        private = self.directory / "private"; private.mkdir()
        (private / "retention.json").write_text("fixed")
        phase = private / "native-authoring-01/creator"; phase.mkdir(parents=True)
        command = actor.namespace(phase, ledger, ["codex", "exec"], repo=repo, private=private)
        writable = [command[i+1] for i, item in enumerate(command) if item == "--bind"]
        self.assertEqual(writable, [str(repo / ".venv"), str(private), str(phase)])
        readonly = [command[i+1] for i, item in enumerate(command) if item == "--ro-bind"]
        self.assertIn(str(private / "retention.json"), readonly)
        self.assertIn(str(repo / ".venv/snapshot"), readonly)
        self.assertIn(str(ledger), readonly)
        self.assertIn(str(phase / "trace.jsonl"), readonly)
        self.assertIn(str(phase / "invocation.json"), readonly)
        with self.assertRaises(ValueError): actor.namespace(private, ledger, ["codex"], repo=repo, private=private)

    def test_existing_files_and_symlinks_cannot_be_overwritten(self):
        target = self.directory / "existing"
        actor.exclusive(target, b"original")
        with self.assertRaises(FileExistsError): actor.exclusive(target, b"replacement")
        link = self.directory / "link"; link.symlink_to(target)
        with self.assertRaises((OSError, ValueError)): actor.exclusive(link, b"replacement")
        self.assertEqual(target.read_bytes(), b"original")

    def test_configuration_closes_external_and_delegation_tools(self):
        config = actor.configurations(self.directory)
        for feature in ["multi_agent", "plugins", "apps", "browser_use", "image_generation"]:
            self.assertFalse(config["features." + feature])
        self.assertEqual(config["approval_policy"], "never")
        self.assertEqual(config["web_search"], "disabled")
        self.assertTrue(config["features.skip_host_skill_discovery"])

    def gate_fixture(self):
        repo, private = self.directory / "gate-repo", self.directory / "gate-private"
        repo.mkdir(); private.mkdir(mode=0o700)
        ledger = repo / ".venv/routing-native-authoring-01"; ledger.mkdir(parents=True)
        parent = private / "native-authoring-01"; parent.mkdir(mode=0o700)
        preparation = parent / "preparation"; preparation.mkdir(mode=0o700)
        source, collection_source = "a" * 40, "b" * 40
        def save(path, value):
            actor.exclusive(path, actor.encoded(value))
        actor.exclusive(preparation / "trace.jsonl", b"native-proof")
        actor.exclusive(preparation / "stderr.log", b"\xffnative-stderr")
        save(preparation / "response.json", {"status": "completed", "severityCounts": {"P1": 0, "P2": 0}, "note": "集計"})
        hashes = {n: actor.collection.digest((preparation / n).read_bytes()) for n in ["trace.jsonl", "stderr.log", "response.json"]}
        execution = {"sourceCommit": source, "role": "preparation", "status": "native_completed",
                     "postSourceMatched": True, "phaseConditionsMatched": True, "actualExitCode": 0,
                     "artifactSha256": hashes}
        save(ledger / "preparation-result.json", execution)
        save(preparation / "native-preparation-receipt.json", {"status": "passed", "severityCounts": {"P1": 0, "P2": 0},
              "sourceCommit": source, "collectionSource": collection_source})
        return repo, private, ledger, preparation, source, collection_source, execution

    def test_previous_success_claim_cannot_override_native_failure(self):
        repo, private, ledger, prep, source, collection_source, execution = self.gate_fixture()
        execution["actualExitCode"] = 7
        (ledger / "preparation-result.json").write_bytes(actor.encoded(execution))
        with patch.multiple(actor, ROOT=repo, PRIVATE=private), patch.object(actor.collection.legacy, "ROOT", repo):
            with self.assertRaisesRegex(ValueError, "native preparation execution"):
                actor.require_previous("creator", source, {"collectionSource": collection_source})

    def test_previous_artifact_drift_is_rejected_despite_passed_receipt(self):
        repo, private, ledger, prep, source, collection_source, execution = self.gate_fixture()
        with patch.multiple(actor, ROOT=repo, PRIVATE=private), patch.object(actor.collection.legacy, "ROOT", repo):
            actor.require_previous("creator", source, {"collectionSource": collection_source})
            (prep / "trace.jsonl").write_bytes(b"changed-native")
            with self.assertRaisesRegex(ValueError, "output drift"):
                actor.require_previous("creator", source, {"collectionSource": collection_source})

    def test_creation_missing_artifact_inventory_cannot_start_reviewer(self):
        repo, private, ledger, prep, source, collection_source, execution = self.gate_fixture()
        creator = private / "native-authoring-01/creator"; creator.mkdir(mode=0o700)
        for name in ["trace.jsonl", "stderr.log", "response.json"]:
            actor.exclusive(creator / name, (prep / name).read_bytes())
        execution = {**execution, "role": "creator"}
        actor.exclusive(ledger / "creator-result.json", actor.encoded(execution))
        actor.exclusive(private / "creation-receipt.json", actor.encoded({
            "status": "created-mechanical-pass-awaiting-independent-review", "sourceCommit": collection_source,
            "executionSource": source, "creatorSolConsumed": 1, "primaryModelTrajectories": 0,
            "automaticRetries": 0, "filesSha256": {}}))
        with patch.multiple(actor, ROOT=repo, PRIVATE=private), patch.object(actor.collection.legacy, "ROOT", repo):
            with self.assertRaisesRegex(ValueError, "artifact inventory"):
                actor.require_previous("reviewer", source, {"collectionSource": collection_source})

    def terminal_fixture(self):
        response = {"status": "completed", "severityCounts": {"P1": 0, "P2": 0}, "note": "集計"}
        events = [{"type": "thread.started", "thread_id": "synthetic"},
                  {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(response)}},
                  {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 2}}]
        actor.exclusive(self.directory / "response.json", actor.encoded(response))
        return events

    def write_trace(self, events):
        (self.directory / "trace.jsonl").write_bytes(b"\n".join(json.dumps(e).encode() for e in events))

    def test_terminal_checks_final_response_and_successful_turn(self):
        events = self.terminal_fixture(); self.write_trace(events)
        result = actor.terminal_result(self.directory)
        self.assertTrue(result["nativeTurnCompleted"])
        self.assertTrue(result["nativeFinalResponseMatched"])
        self.assertEqual(result["usage"], {"input_tokens": 1, "output_tokens": 2})

    def test_terminal_rejects_missing_failed_or_multiple_completion(self):
        events = self.terminal_fixture()
        variants = [events[:-1], events + [{"type": "turn.failed"}], events + [events[-1]],
                    events + [{"type": "error", "message": "PRIVATE_SENTINEL"}]]
        for variant in variants:
            self.write_trace(variant)
            with self.assertRaisesRegex(ValueError, "not successful"): actor.terminal_result(self.directory)

    def test_terminal_rejects_changed_agent_response(self):
        events = self.terminal_fixture()
        events[1]["item"]["text"] = '{"different":true}'
        self.write_trace(events)
        with self.assertRaisesRegex(ValueError, "response mismatch"): actor.terminal_result(self.directory)


if __name__ == "__main__":
    unittest.main()
