"""実Host/Coreを取得し、合成native原証拠の欠測・破損を拒否する。モデル0。"""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_quality_evaluation as support

evaluation = support.evaluate


class QualityNativeEvidenceTests(unittest.TestCase):
    setUp = support.QualityEvaluationTests.setUp
    tearDown = support.QualityEvaluationTests.tearDown
    prepared = support.QualityEvaluationTests.prepared
    record_from_actual_host = support.QualityEvaluationTests.record_from_actual_host

    def current_record(self):
        record, calls = self.record_from_actual_host()
        old = evaluation.jsonl(self.directory / "trace.jsonl")
        events = [{"type": "thread.started", "thread_id": "synthetic-no-model"}, {"type": "turn.started"}]
        for index, event in enumerate(old):
            item = copy.deepcopy(event["item"])
            item["id"] = f"item_{index}"
            if item["type"] == "mcp_tool_call":
                started = copy.deepcopy(item)
                started.update(status="in_progress", result=None)
                events.append({"type": "item.started", "item": started})
            events.append({"type": "item.completed", "item": item})
        events.append({"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 20,
            "cache_write_input_tokens": 0, "output_tokens": 30, "reasoning_output_tokens": 5}})
        record["identity"]["executionVersion"] = evaluation.EXECUTION_VERSION
        record["usage"] = [events[-1]["usage"]]
        control = evaluation.load(self.directory / "control.json")
        evaluation.write(self.directory / "model-config.json", evaluation.model_configs(self.directory, self.directory / self.cases[0]["caseId"]))
        (self.directory / "prompt.txt").write_text(evaluation.prompt(self.cases[0], "baseline"))
        (self.directory / "stderr.log").write_bytes(b"")
        self.trace(record, events)
        record["artifacts"] = {name: support.sha(evaluation.read_original(self.directory / name)) for name in evaluation.REQUIRED_ARTIFACTS}
        self.record, self.events = record, events
        return record

    def trace(self, record, events):
        raw = ("\n".join(json.dumps(e) for e in events) + "\n").encode()
        (self.directory / "trace.jsonl").write_bytes(raw)
        record["artifacts"]["trace.jsonl"] = support.sha(raw)

    def inspect(self, record=None):
        return evaluation.inspect_record(self.directory, self.cases[0], record or self.record)

    def rejected(self, record=None):
        errors, document = self.inspect(record)
        self.assertTrue(any(errors.values()), errors)
        self.assertIsNone(document)

    def test_complete_native_and_real_core_preserve_usage(self):
        self.current_record()
        errors, document = self.inspect()
        self.assertFalse(any(errors.values()), errors)
        self.assertEqual(2, len(document["coreResults"]))
        self.assertEqual(self.events[-1]["usage"], self.record["usage"][0])

    def test_closed_inventory_cannot_be_empty_missing_extended_or_traversed(self):
        self.current_record()
        inventories = [{}, {k:v for k,v in self.record["artifacts"].items() if k != "stderr.log"},
                       {**self.record["artifacts"], "unexpected.json": "a"*64},
                       {**self.record["artifacts"], "../outside.json": "a"*64}]
        for inventory in inventories:
            with self.subTest(inventory=list(inventory)):
                changed = copy.deepcopy(self.record)
                changed["artifacts"] = inventory
                self.rejected(changed)

    def test_missing_duplicate_failed_and_unknown_lifecycle_is_rejected(self):
        self.current_record()
        variants = [self.events[1:], self.events[:-1], self.events[:2]+self.events[3:],
                    self.events[:2]+[self.events[1]]+self.events[2:],
                    self.events+[self.events[-2]],
                    self.events[:-1]+[{"type":"turn.failed","error":{"message":"synthetic"}}],
                    self.events[:-1]+[{"type":"unknown.future"}]+[self.events[-1]]]
        for events in variants:
            with self.subTest(events=len(events)):
                self.trace(self.record, events)
                self.rejected()

    def test_bool_negative_missing_string_overflow_and_unknown_usage_is_rejected(self):
        self.current_record()
        variants = [("input_tokens", True), ("input_tokens", -1), ("input_tokens", "100"),
                    ("cached_input_tokens", 101), ("reasoning_output_tokens", 31), ("unknown", 0)]
        for key, value in variants:
            with self.subTest(key=key, value=value):
                events = copy.deepcopy(self.events)
                events[-1]["usage"][key] = value
                self.trace(self.record, events)
                self.record["usage"] = [events[-1]["usage"]]
                self.rejected()
        events = copy.deepcopy(self.events)
        del events[-1]["usage"]["cache_write_input_tokens"]
        self.trace(self.record, events)
        self.record["usage"] = [events[-1]["usage"]]
        self.rejected()

    def test_retyped_record_usage_cannot_override_original_counters(self):
        self.current_record()
        self.record["usage"][0]["input_tokens"] = 100.0
        self.rejected()

    def test_checked_original_buffers_are_parsed_without_second_read(self):
        self.current_record()
        expected = {self.directory / name: evaluation.read_original(self.directory / name) for name in self.record["artifacts"]}
        counts = {path:0 for path in expected}
        reader = evaluation.read_original
        def read(path):
            if path in expected:
                counts[path] += 1
                if counts[path] > 1:
                    return b"null"
                return expected[path]
            return reader(path)
        with patch.object(evaluation, "read_original", side_effect=read):
            errors, _ = self.inspect()
        self.assertFalse(any(errors.values()), errors)
        self.assertEqual({1}, set(counts.values()))

    def test_saved_advice_must_match_original_response_and_core_transfer(self):
        self.current_record()
        errors, document = self.inspect()
        self.assertFalse(any(errors.values()), errors)
        evaluation.write(self.directory / "advice.json", document)
        self.record["artifacts"]["advice.json"] = support.sha(evaluation.read_original(self.directory / "advice.json"))
        self.assertFalse(any(self.inspect()[0].values()))
        document["subjectCommit"] = "f"*40
        evaluation.write(self.directory / "advice.json", document)
        self.record["artifacts"]["advice.json"] = support.sha(evaluation.read_original(self.directory / "advice.json"))
        errors, _ = self.inspect()
        self.assertIn("saved advice differs from original response and Core transfer", errors["evidence"])

    def test_duplicate_nonfinite_deep_nonobject_json_and_link_are_rejected(self):
        self.current_record()
        path = self.directory / "response.json"
        for raw in [b"null", b"[]", b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', ("["*10000+"0"+"]"*10000).encode()]:
            with self.subTest(raw=raw[:20]):
                path.write_bytes(raw)
                self.record["artifacts"]["response.json"] = support.sha(raw)
                self.rejected()
        path.unlink()
        path.symlink_to(self.directory / "control.json")
        self.rejected()

    def test_legacy_partial_trace_stays_legacy_and_cannot_claim_current_version(self):
        record, _ = self.record_from_actual_host()
        errors, _ = self.inspect(record)
        self.assertFalse(any(errors.values()), errors)
        record["identity"]["executionVersion"] = evaluation.EXECUTION_VERSION
        self.rejected(record)


if __name__ == "__main__":
    unittest.main()
