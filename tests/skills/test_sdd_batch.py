"""外部モデルを起動せず、再起動・失敗・費用制限の停止を検査する。"""
import argparse
import copy
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("sdd_batch", ROOT / "evals/skills/sdd/batch.py")
batch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(batch)


class SddBatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="bitz-sdd-batch-tests-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.args = argparse.Namespace(output=self.root / ".venv/output", case=["SI-001"],
                                       variant="skill", repetition=1, jobs=1, resume=False, timeout=240,
                                       model="gpt-6.1-sol", model_version="test-alias", pythonpath=str(self.root),
                                       batch=self.root / "evals/skills/sdd/batches/implement-safety-01.json")
        self.cases = [{"id": "SI-001"}, {"id": "SI-007"}]
        self.checks = {key: {"passed": True, "errors": []} for key in ("deterministic", "safety", "workflow", "observation")}
        self.evaluation = SimpleNamespace(ROOT=self.root, HERE=self.root / "evals/skills/sdd",
            load=lambda p: json.loads(Path(p).read_text()), digest=lambda b: hashlib.sha256(b).hexdigest(),
            json_digest=lambda v: hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest(),
            identity=lambda args, case: {"model": args.model, "modelVersion": args.model_version,
                "subjectCommit": "a" * 40, "variant": args.variant, "repetition": args.repetition, "caseId": case["id"]},
            inspect=lambda record, case, target: record["checks"], run_one=self.fake_model)
        self.fixed = json.loads((ROOT / "evals/skills/sdd/batches/implement-safety-01.json").read_text())
        self.conditions = {"output": str(self.args.output), "source": "a" * 40}
        self.calls = []
        self.fail = False
        self.error = None
        self.ledger_path = self.root / ".venv/sdd-batch-ledgers/implement-safety-01.json"

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def fake_model(self, args, case):
        # 起動前に費用枠を消費したかをモデル境界で確認する。
        ledger = self.evaluation.load(self.ledger_path)
        self.assertEqual(ledger["attemptCount"], len(self.calls) + 1)
        self.assertEqual(ledger["attempts"][-1]["status"], "started")
        self.calls.append(case["id"])
        if self.error:
            raise self.error
        record = {"identity": {"subjectCommit": "a" * 40}, "checks": copy.deepcopy(self.checks)}
        if self.fail:
            record["checks"]["safety"] = {"passed": False, "errors": ["synthetic failure"]}
        slot = {"caseId": case["id"], "variant": args.variant, "repetition": args.repetition}
        self.write(batch.directory(args, slot) / "run.json", record)
        return record

    def measure(self):
        with patch.object(batch, "plan", return_value=(self.fixed, self.conditions)), redirect_stdout(io.StringIO()):
            return batch.run(self.evaluation, self.args, self.cases)

    def receipt(self):
        attempt = self.evaluation.load(self.ledger_path)["attempts"][0]
        receipt = {"schemaVersion": "1.0", "status": "passed", "independent": True,
                   "implementationPrivateHistoryInherited": False, "evaluationRunId": attempt["evaluationRunId"],
                   "reviewRunId": "independent-review-1", "subjectCommit": "a" * 40,
                   "runSha256": attempt["runSha256"], "checks": {key: "passed" for key in set(self.checks) | {"semantic"}},
                   "directChecks": ["合成の検査。実モデル・実意味検分ではない"], "reason": "合成の意味適合記録"}
        path = batch.directory(self.args, attempt["slot"]) / "independent-review.json"
        self.write(path, receipt)
        return path, receipt

    def next(self):
        self.args.case = ["SI-007"]

    def test_missing_receipt_blocks_next_process(self):
        self.assertEqual(0, self.measure())
        self.next()
        with self.assertRaises(FileNotFoundError):
            self.measure()
        self.assertEqual(["SI-001"], self.calls)

    def test_independent_pass_allows_exact_next_slot_and_exhausts_budget(self):
        self.measure()
        self.receipt()
        self.next()
        self.assertEqual(0, self.measure())
        last = self.evaluation.load(self.ledger_path)["attempts"][-1]
        path, receipt = self.receipt()
        receipt.update(evaluationRunId=last["evaluationRunId"], runSha256=last["runSha256"], reviewRunId="review-2")
        self.write(batch.directory(self.args, last["slot"]) / "independent-review.json", receipt)
        with self.assertRaisesRegex(ValueError, "上限"):
            self.measure()
        self.assertEqual(["SI-001", "SI-007"], self.calls)

    def test_failure_consumes_budget_and_blocks_restart_with_different_case(self):
        self.fail = True
        self.assertEqual(1, self.measure())
        self.next()
        with self.assertRaisesRegex(ValueError, "自動再開"):
            self.measure()
        self.assertEqual(1, self.evaluation.load(self.ledger_path)["attemptCount"])
        self.assertEqual(1, len(self.calls))

    def test_timeout_or_interrupt_never_refunds_call(self):
        for error in (subprocess.TimeoutExpired("synthetic", 240), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                self.error = error
                with self.assertRaises(type(error)):
                    self.measure()
                self.assertEqual("interrupted", self.evaluation.load(self.ledger_path)["attempts"][-1]["status"])
                with self.assertRaisesRegex(ValueError, "自動再開"):
                    self.measure()
                # 次の異なる例外条件は別の合成台帳で検査する。
                self.ledger_path.unlink()
                self.calls.clear()

    def test_changed_output_cannot_reset_budget(self):
        self.measure()
        self.args.output = self.root / ".venv/another-output"
        self.conditions = self.conditions | {"output": str(self.args.output)}
        with self.assertRaisesRegex(ValueError, "リセット"):
            self.measure()
        self.assertEqual(1, len(self.calls))

    def test_tampered_ledger_count_is_rejected(self):
        self.measure()
        ledger = self.evaluation.load(self.ledger_path)
        ledger["attemptCount"] = 0
        self.write(self.ledger_path, ledger)
        with self.assertRaisesRegex(ValueError, "呼出し数"):
            self.measure()
        self.assertEqual(1, len(self.calls))

    def test_changed_run_evidence_blocks_next(self):
        self.measure()
        self.receipt()
        path = batch.directory(self.args, self.fixed["slots"][0]) / "run.json"
        record = self.evaluation.load(path)
        record["changed"] = True
        self.write(path, record)
        self.next()
        with self.assertRaisesRegex(ValueError, "実証拠"):
            self.measure()
        self.assertEqual(1, len(self.calls))

    def test_self_review_failed_or_stale_receipt_blocks_next(self):
        self.measure()
        path, valid = self.receipt()
        self.next()
        changes = [{"independent": False}, {"implementationPrivateHistoryInherited": True},
                   {"reviewRunId": valid["evaluationRunId"]}, {"status": "unknown"},
                   {"subjectCommit": "b" * 40}, {"runSha256": "b" * 64},
                   {"checks": valid["checks"] | {"semantic": "failed"}}, {"directChecks": []}]
        for change in changes:
            with self.subTest(change=change):
                self.write(path, valid | change)
                with self.assertRaisesRegex(ValueError, "実検分"):
                    self.measure()
        self.assertEqual(1, len(self.calls))

    def test_concurrent_process_lock_prevents_a_second_call(self):
        with batch.locked(self.ledger_path.with_suffix(".lock")):
            with self.assertRaisesRegex(ValueError, "別プロセス"):
                self.measure()
        self.assertEqual([], self.calls)

    def prepare_plan(self):
        here = self.evaluation.HERE
        for relative in ("protocol.json", "cases.json"):
            source = ROOT / "evals/skills/sdd" / relative
            destination = here / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
        self.write(self.args.batch, self.fixed)
        self.write(here.parent / "sol-authorization.json", json.loads((ROOT / "evals/skills/sol-authorization.json").read_text()))
        self.write(self.root / "plugins/bitz-sdd/plugin.json", {"version": "0.3.0"})
        self.check_output = patch.object(batch.subprocess, "check_output", side_effect=lambda cmd, **kw:
            self.args.batch.read_bytes() if cmd[0] == "git" else "codex test\n")
        self.check_ignore = patch.object(batch.subprocess, "run", return_value=SimpleNamespace(returncode=0))
        self.check_output.start()
        self.check_ignore.start()
        self.addCleanup(self.check_output.stop)
        self.addCleanup(self.check_ignore.stop)

    def test_plan_binds_each_slot_variant_and_repetition(self):
        self.prepare_plan()
        self.fixed["slots"][1].update(variant="baseline", repetition=2)
        self.write(self.args.batch, self.fixed)
        fixed, conditions = batch.plan(self.evaluation, self.args, self.cases)
        self.assertEqual([("skill", 1), ("baseline", 2)], [(i["variant"], i["repetition"]) for i in conditions["identities"]])

    def test_invalid_model_authorization_or_protocol_rejected_before_writes(self):
        self.prepare_plan()
        for alteration in ("model", "authorization", "protocol", "budget", "timeout", "resume", "output"):
            with self.subTest(alteration=alteration):
                args = copy.deepcopy(self.args)
                approval = self.evaluation.load(self.evaluation.HERE.parent / "sol-authorization.json")
                fixed = copy.deepcopy(self.fixed)
                if alteration == "model": args.model = "gpt-6-astra"
                if alteration == "authorization": approval["scope"] = "別の用途"
                if alteration == "protocol": fixed["protocolSha256"] = "0" * 64
                if alteration == "budget": fixed["maximumPrimaryCalls"] = 3
                if alteration == "timeout": args.timeout = 241
                if alteration == "resume": args.resume = True
                if alteration == "output": args.output = self.root / "tracked-output"
                self.write(args.batch, fixed)
                self.write(self.evaluation.HERE.parent / "sol-authorization.json", approval)
                with self.assertRaises(ValueError):
                    batch.plan(self.evaluation, args, self.cases)
                self.assertFalse((self.root / ".venv").exists())
                self.write(self.evaluation.HERE.parent / "sol-authorization.json", json.loads((ROOT / "evals/skills/sol-authorization.json").read_text()))


if __name__ == "__main__":
    unittest.main()
