"""入れ子fixtureのsetup例外が原照合や共通台帳のmockを後続へ残さない。"""
import unittest
from unittest.mock import patch

import test_production_canary_evidence as evidence_fixture
import test_production_canary_review as review_fixture
import test_production_canary_score as score_fixture


class NestedFixtureCleanupTests(unittest.TestCase):
    def test_setup_error_unwinds_shared_source_and_ledger_patches(self):
        evidence = evidence_fixture.evidence
        original_guard = evidence.guard.verify
        original_storage = evidence.ledger.common_ledger_path
        for kind in (review_fixture.CanaryReviewTests, review_fixture.CanaryCompleteReviewTests, score_fixture.CanaryScoreTests):
            with self.subTest(fixture=kind.__name__):
                started = []
                def failing_setup(child):
                    for target, name in ((evidence.guard, "verify"), (evidence.ledger, "common_ledger_path")):
                        mocked = patch.object(target, name, return_value="synthetic leaked state")
                        child.addCleanup(mocked.stop)
                        mocked.start()
                        started.append(mocked)
                    raise RuntimeError("synthetic fixture failure after shared patches")
                outer = kind(methodName="runTest")
                try:
                    with patch.object(evidence_fixture.CanaryEvidenceTests, "setUp", failing_setup):
                        with self.assertRaisesRegex(RuntimeError, "after shared patches"):
                            outer.setUp()
                        self.assertEqual(len(started), 2)
                        outer.doCleanups()
                        self.assertIs(evidence.guard.verify, original_guard)
                        self.assertIs(evidence.ledger.common_ledger_path, original_storage)
                finally:
                    outer.doCleanups()
                    for mocked in reversed(started):
                        mocked.stop()


if __name__ == "__main__":
    unittest.main()
