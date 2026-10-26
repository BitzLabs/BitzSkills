"""公開metadataの合成fixtureだけでproposalのDAG/原bytes/固定予算を検査する。"""
import copy
from pathlib import Path
import sys
from types import MappingProxyType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'evals/skills/routing'))
import production_heldout_phase_registry as registry
import production_heldout_execution as execution
import production_heldout_preflight as preflight
import test_production_heldout_launch as launch_fixture

p, io = registry.phases, registry.io


class PhaseProposalTests(unittest.TestCase):
    def setUp(self):
        self.genesis = p.anchor()
        g = self.genesis
        rows = []
        # I/O層から受け取る検証済snapshotを表すin-memory fixture。私的原は読まない。
        for ordinal in [2, 3]:
            for stage in p.legacy.STAGES:
                rows.append(MappingProxyType(dict(stage=stage, ordinal=ordinal,
                    artifactSha256=None if stage.endswith(('_reserved', '_started')) else 'd'*64,
                    measuredCorrect=True if stage == 'parent_verified' else None)))
        self.snapshots = [p.JournalSnapshot(io.encoded(g['genesisContracts']['ledger']), 2,
            tuple(rows), g['genesisJournalHeadSha256'], None)]
        self.prior = dict(phaseIndex=0, ordinal=3, role='independent',
            executionSha256=g['genesisSha256']['execution'], sourceCommit=g['genesisContracts']['execution']['sourceCommit'],
            receiptSha256='d'*64, pacingSha256='8'*64, wallSeconds=1000)
        self.header = dict(version=p.HEADER_VERSION, purposeAnchorSha256=p.ANCHOR_SHA256,
            index=1, previousActivationSha256=p.ANCHOR_SHA256,
            previousJournalHeadSha256=g['genesisJournalHeadSha256'], firstOrdinal=4, priorLaunch=self.prior)
        self.context = dict(g['stableContext'], date='2026-10-26', calibrationSource='e'*40,
            calibrationRequestSha256='6'*64, calibrationReceiptSha256='7'*64)
        self.input = dict(g['genesisContracts']['input'], sourceCommit='f'*40)
        self.deployment = copy.deepcopy(g['genesisContracts']['deployment'])
        self.deployment.update(sourceCommit='f'*40, manifestSha256='5'*64,
            snapshotRelativePath='.venv/heldout-routing-preparation-synthetic-phase-01/snapshot',
            calibrationManifestSha256='4'*64)
        self.contract = copy.deepcopy(g['genesisContracts']['execution'])
        self.contract.update(version=execution.PHASE_VERSION, sourceCommit='f'*40, conditionPhase=self.header)
        self.contract['pins'].update(snapshotManifest='5'*64, calibrationManifest='4'*64)
        self.proof = dict.fromkeys(preflight.PROOF_KEYS)
        self.proof.update(status='heldout_resources_verified_not_launchable', sourceCommit='f'*40,
            casesSha256=g['stableInputSha256']['cases'], baselineProductSource=g['baselineProductSource'],
            productResourcesSha256=g['stableProductResourcesSha256'], sdkTreeSha256=g['stablePins']['sdk'],
            decisionSchemaSha256=g['stablePins']['decisionSchema'],
            originalCalibration=dict(status='original_local_calibration_matches', calibrationManifestSha256='4'*64),
            models=0, reservations=0, launchEnabled=False, certifiesSkillGate=False, certifiesRelease=False)

    def raws(self):
        context = io.encoded(self.context)
        self.deployment['contextProfileSha256'] = io.sha(context)
        deployment = io.encoded(self.deployment)
        inputs = io.encoded(self.input)
        self.contract.update(deploymentSha256=io.sha(deployment), inputContractSha256=io.sha(inputs))
        self.contract['pins']['contextProfile'] = io.sha(context)
        raw = io.encoded(self.contract)
        self.proof.update(executionSha256=io.sha(raw), deploymentSha256=io.sha(deployment),
            inputContractSha256=io.sha(inputs), contextProfileSha256=io.sha(context), contextDate=self.context['date'])
        return raw, deployment, inputs, io.encoded(self.proof), context

    def propose(self):
        return registry.proposal(*self.raws(), self.genesis, self.snapshots, '2026-10-25', self.prior)

    def review(self, proposed):
        current = proposed['current']
        bound = SimpleNamespace(execution_raw=current['execution'].encode(),
            deployment_raw=current['deployment'].encode(), contract=registry.finite_json(current['execution'].encode()))
        review, report, isolation = launch_fixture.review_bytes(bound)
        value = registry.finite_json(report)
        value['conditionPhaseProposalSha256'] = io.sha(io.encoded(proposed))
        # reportの空白/改行もレビューhashへ束縛し、そのまま保持させる。
        import json
        report = (json.dumps(value, indent=2)+'\n').encode()
        review = io.encoded(dict(registry.finite_json(review), reviewReportSha256=io.sha(report)))
        return review, report, isolation

    def test_proposal_preserves_purpose_consumption_and_is_readonly(self):
        with patch.object(p.io, 'read_regular', side_effect=AssertionError('unexpected read')):
            proposed = self.propose()
        self.assertEqual((proposed['carry']['primaryReserved'], proposed['carry']['independentReserved']), (3, 2))
        self.assertEqual((proposed['carry']['correct'], proposed['carry']['nextOrdinal']), (2, 4))
        self.assertNotIn('reviewSha256', proposed)
        self.assertNotIn('sealSha256', proposed)
        self.assertEqual(proposed['current']['ledger'], io.encoded(p.legacy.contract(
            proposed['current']['ledger'].encode())).decode())

    def test_admission_preserves_original_review_bytes_and_has_no_hash_cycle(self):
        proposed = self.propose()
        review, report, isolation = self.review(proposed)
        raw = registry.admission(proposed, review, report, isolation)
        admitted = registry.verify_admission(raw, self.genesis, self.snapshots, '2026-10-25', self.prior)
        self.assertEqual(admitted['report'].encode(), report)
        self.assertEqual(admitted['review'].encode(), review)
        seal = registry.seal_record(admitted)
        activated = registry.activation_record(admitted)
        self.assertEqual(seal['proposalSha256'], io.sha(io.encoded(proposed)))
        self.assertEqual(activated['sealSha256'], io.sha(io.encoded(seal)))
        self.assertNotIn('activationSha256', seal)
        self.assertEqual(activated['previousActivationSha256'], p.ANCHOR_SHA256)

    def test_rehashed_claimed_carry_is_rejected_by_reconstruction(self):
        proposed = self.propose()
        proposed['carry']['primaryReserved'] = 0
        raw = registry.admission(proposed, *self.review(proposed))
        with self.assertRaises(ValueError):
            registry.verify_admission(raw, self.genesis, self.snapshots, '2026-10-25', self.prior)

    def test_changed_input_cannot_be_rebound_under_the_same_purpose(self):
        self.input['inputSha256'] = dict(self.input['inputSha256'], cases='0'*64)
        with self.assertRaises(ValueError):
            self.propose()

    def test_changed_context_cannot_be_hidden_by_new_hashes(self):
        key = next(iter(self.genesis['stableContext']))
        self.context[key] = 'CHANGED_PUBLIC_SYNTHETIC_CONTEXT'
        with self.assertRaises(ValueError):
            self.propose()

    def test_changed_sdk_and_calibration_rejection_flags_are_rejected(self):
        self.contract['pins']['sdk'] = '0'*64
        self.deployment['sdkTreeSha256'] = '0'*64
        with self.assertRaises(ValueError):
            self.propose()
        self.contract['pins']['sdk'] = self.genesis['stablePins']['sdk']
        self.deployment['sdkTreeSha256'] = self.genesis['stablePins']['sdk']
        self.proof['originalCalibration']['status'] = 'unverified'
        with self.assertRaises(ValueError):
            self.propose()

    def test_wrong_boundary_head_or_old_completed_receipt_is_rejected(self):
        self.header['previousJournalHeadSha256'] = '0'*64
        with self.assertRaises(ValueError):
            self.propose()
        self.header['previousJournalHeadSha256'] = self.genesis['genesisJournalHeadSha256']
        self.header['firstOrdinal'] = 5
        with self.assertRaises(ValueError):
            self.propose()
        self.header['firstOrdinal'] = 4
        self.prior['receiptSha256'] = '0'*64
        with self.assertRaises(ValueError):
            self.propose()

    def test_current_or_older_day_cannot_create_a_new_phase(self):
        for day in ['2026-10-25', '2026-10-24']:
            self.context['date'] = day
            with self.subTest(day=day), self.assertRaises(ValueError):
                self.propose()

    def test_missing_proposal_binding_cannot_be_rehashed_into_a_review(self):
        proposed = self.propose()
        review, report, isolation = self.review(proposed)
        changed = registry.finite_json(report)
        changed.pop('conditionPhaseProposalSha256')
        report = io.encoded(changed)
        review = io.encoded(dict(registry.finite_json(review), reviewReportSha256=io.sha(report)))
        with self.assertRaises(ValueError):
            registry.admission(proposed, review, report, isolation)

    def test_admission_unknown_fields_or_changed_raw_bytes_are_rejected(self):
        proposed = self.propose()
        raw = registry.admission(proposed, *self.review(proposed))
        value = registry.finite_json(raw)
        with self.assertRaises(ValueError):
            registry.verify_admission(io.encoded(dict(value, allowRetry=True)), self.genesis,
                self.snapshots, '2026-10-25', self.prior)
        value['proposal']['current']['ledger'] += ' '
        with self.assertRaises(ValueError):
            registry.verify_admission(io.encoded(value), self.genesis, self.snapshots, '2026-10-25', self.prior)

    def test_phase_ledger_opening_is_explicitly_blocked_until_connection_is_verified(self):
        raw, deployment, inputs, proof, _ = self.raws()
        bound = execution.BoundExecution(raw, deployment, inputs, ())
        with self.assertRaisesRegex(ValueError, 'not connected'):
            bound.ledger_contract(proof)
        legacy_raw = io.encoded(self.genesis['genesisContracts']['execution'])
        self.assertEqual(execution.execution_contract(legacy_raw)['version'], execution.VERSION)
        self.assertEqual(io.sha(legacy_raw), self.genesis['genesisSha256']['execution'])


if __name__ == '__main__':
    unittest.main()
