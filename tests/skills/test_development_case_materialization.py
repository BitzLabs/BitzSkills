import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals/skills/routing"))
from development_case_materialization import development_events, materialize
from development_case_review import novelty_blockers
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

    def test_reviewed_conflict_requires_the_selected_route(self):
        self.outline["outline"]["polarity"] = "conflict"
        self.draft.update(selectedSkill="sdd-plan", outcome="proceed", category="conflict")
        case = self.build()
        self.assertEqual(case["mode"], "use")
        self.assertEqual(case["expected"]["threeEntry"], self.routes["sdd-plan"])
        self.draft["selectedSkill"] = "quality-plan"
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

    def test_development_decisions_are_scored_even_with_the_correct_route(self):
        original = set(self.catalog)
        self.catalog = development_events(original)
        for polarity, category, outcome, required, forbidden in (
            ("conflict", "conflict", "proceed", "select-simplified-flow", "select-full-flow"),
            ("safety", "safety", "stop", "retain-risk-band", "lower-risk-band"),
        ):
            with self.subTest(category=category):
                self.outline["outline"]["polarity"] = polarity
                self.draft.update(selectedSkill="sdd-plan", outcome=outcome, category=category)
                for key, event in (("required", required), ("forbidden", forbidden)):
                    self.draft["eventEvidence"][key] = [
                        dict(event=event, source="選択規則", trigger="条件成立", observable=event)]
                case = self.build()
                for events, correct in (([required], True), ([], False), ([forbidden], False),
                                        ([required, forbidden], False)):
                    decision = dict(selectedEntry="sdd-plan", selectedPath=None,
                                    outcome=outcome, events=events)
                    self.assertEqual(all(mechanical_accuracy(case, decision).values()), correct)
                self.assertNotIn(required, original)
                self.assertNotIn(forbidden, original)

    def test_draft_schema_requires_every_outline_and_known_outcome(self):
        import json
        from jsonschema import Draft202012Validator
        from development_case_materialization import draft_schema

        case_schema = json.loads((ROOT / "evals/skills/schemas/case.schema.json").read_text())
        schema = draft_schema(["first", "second"], case_schema, sorted(self.catalog))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        response = {"first": self.draft, "second": dict(self.draft)}
        self.assertTrue(validator.is_valid(response))
        self.assertFalse(validator.is_valid({"first": self.draft}))
        response["second"]["outcome"] = "a free-form justification"
        self.assertFalse(validator.is_valid(response))


class DevelopmentReviewTests(unittest.TestCase):
    def test_distinct_and_empty_comparisons_do_not_block(self):
        for distinct in ({1, 2}, set()):
            self.assertEqual(novelty_blockers("A", {"N": distinct, "D": set(), "U": set()}), set())

    def test_duplicate_and_unknown_block_the_affected_cases(self):
        judgments = {"N": set(), "D": {2}, "U": {3}}
        self.assertEqual(novelty_blockers("A", judgments), {"A"})
        self.assertEqual(novelty_blockers("A", judgments, ["A", "B", "C"]), {"A", "B", "C"})
