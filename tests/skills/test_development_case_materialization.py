import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals/skills/routing"))
from development_case_materialization import materialize
from production_heldout_semantic import mechanical_accuracy


class DevelopmentMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.outline = {"skill": "sdd-plan", "outline": {"polarity": "negative"}}
        self.draft = dict(selectedSkill=None, outcome="not-applicable", category="negative",
                          prompt="要約してください", context=[], decisionReason="一般的な要約",
                          alternativeReason="仕様計画を依頼していない", source="適用範囲",
                          counterfactual="要求の計画を求めれば担当が変わる",
                          eventEvidence={"required": [], "forbidden": []})
        self.routes = {"sdd-plan": {"entry": "bitz-sdd", "path": "plan"}}
        self.catalog = {"classify-feature", "edit-files"}

    def build(self):
        return materialize(self.outline, "SE-9999", self.draft, self.catalog, self.routes)[0]

    def test_no_skill_is_explicit(self):
        self.assertIsNone(self.build()["expected"]["sixSkill"])
        del self.draft["selectedSkill"]
        with self.assertRaises(KeyError):
            self.build()

    def test_competing_skill_stops_negative_materialization(self):
        self.draft.update(selectedSkill="quality-plan", outcome="proceed")
        with self.assertRaises(ValueError):
            self.build()

    def test_event_evidence_is_required(self):
        self.draft["eventEvidence"]["forbidden"] = [
            dict(event="edit-files", source="適用範囲", trigger="読取りだけ", observable="")]
        with self.assertRaises(ValueError):
            self.build()

    def test_routing_scorer_uses_observed_events(self):
        self.outline["outline"]["polarity"] = "positive"
        self.draft.update(selectedSkill="sdd-plan", outcome="proceed", category="explicit")
        for key, event in (("required", "classify-feature"), ("forbidden", "edit-files")):
            self.draft["eventEvidence"][key] = [
                dict(event=event, source="計画手順", trigger="計画の依頼", observable=event)]
        case = self.build()
        decision = dict(selectedEntry="sdd-plan", selectedPath=None, outcome="proceed",
                        events=["classify-feature"], rejectedEvents=["edit-files"])
        self.assertTrue(all(mechanical_accuracy(case, decision).values()))
        decision.update(events=[], rejectedEvents=["classify-feature"])
        self.assertFalse(mechanical_accuracy(case, decision)["requiredEvents"])
        decision.update(events=["classify-feature", "edit-files"], rejectedEvents=["edit-files"])
        self.assertFalse(mechanical_accuracy(case, decision)["forbiddenEvents"])
