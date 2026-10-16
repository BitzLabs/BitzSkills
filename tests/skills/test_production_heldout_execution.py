"""合成ケース/資源だけで保持24枠の実行・配備・台帳の結合を検証。モデル0。"""
import copy
from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'evals/skills/routing'))
import production_heldout_preflight as preflight
import test_production_heldout_inputs as input_fixture
import test_production_matrix_preflight as public_fixture

x = preflight.execution
io = preflight.io


class HeldoutExecutionTests(unittest.TestCase):
    def setUp(self):
        self.old = public_fixture.MatrixPreflightTests(methodName='runTest')
        self.old.setUp()
        self.addCleanup(self.old.doCleanups)
        self.repository = self.old.repository
        self.input_fixture = input_fixture.HeldoutInputTests(methodName='runTest')
        self.input_fixture.setUp()
        self.raws = self.input_fixture.raws
        self.input_contract = self.input_fixture.contract
        self.input_raw = io.encoded(self.input_contract)
        for name in preflight.SOURCE_FILES:
            raw = (ROOT/name).read_bytes()
            if name not in self.old.originals:
                self.old.originals[name] = raw
        self.old.originals[x.inputs.REVIEW_PATH] = self.raws['reviewedSet']
        for name in preflight.SOURCE_FILES:
            path = self.repository/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.old.originals[name])
        self.snapshot_relative = '.venv/heldout-routing-preparation-synthetic/snapshot'
        self.snapshot = self.repository/self.snapshot_relative
        self.snapshot.parent.mkdir()
        self.old.snapshot.rename(self.snapshot)
        manifest = copy.deepcopy(self.old.manifest)
        for index in range(66):
            name = f'resources/bitz-core/support/synthetic-{index:02d}.txt'
            raw = f'public resource {index}'.encode()
            path = self.snapshot/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            self.old.originals['plugins/'+name.removeprefix('resources/')] = raw
            manifest['resources'][name] = io.sha(raw)
        manifest_raw = io.encoded(manifest)
        (self.snapshot/'manifest.json').write_bytes(manifest_raw)
        self.deployment = copy.deepcopy(self.old.deployment)
        self.deployment.pop('executionSha256')
        self.deployment.update(version=x.DEPLOYMENT_VERSION, snapshotRelativePath=self.snapshot_relative,
            snapshotResourceCount=72, manifestSha256=io.sha(manifest_raw))
        self.execution = copy.deepcopy(self.old.execution)
        self.execution.update(version=x.VERSION, campaignId='heldout-matrix-synthetic-01',
            outputRelativeRoot='measurements/heldout-matrix-synthetic-01',
            inputContractSha256=io.sha(self.input_raw), deploymentSha256=io.sha(io.encoded(self.deployment)),
            budget=dict(primary=24, independent=24, automaticRetries=0, delegations=0))
        self.execution['pins'].pop('prelaunchReview')
        self.execution['pins']['snapshotManifest'] = io.sha(manifest_raw)
        self.reader = self.patch(x.inputs, 'private_bytes', return_value=self.raws['cases'])

    def patch(self, target, name, **kwargs):
        item = patch.object(target, name, **kwargs)
        self.addCleanup(item.stop)
        return item.start()

    def bind(self):
        return x.bind(io.encoded(self.execution), io.encoded(self.deployment), self.input_raw, **self.raws)

    def verify(self):
        return preflight.verify_resources(self.repository, self.bind(), self.old.sdk_manifest_raw)

    def repin_deployment(self):
        self.execution['deploymentSha256'] = io.sha(io.encoded(self.deployment))

    def test_exact_24_slots_and_private_stage_roots_without_primary_expectations(self):
        bound = self.bind()
        self.assertEqual(len({(bound.slot(n)['caseId'],bound.slot(n)['repetition']) for n in range(1,25)}),24)
        self.assertEqual(bound.slot(24)['caseId'],'SE-1211')
        for role in ['primary','independent']:
            self.assertEqual(bound.stage_root(1,role), x.inputs.PRIVATE_CASES.parent/
                'measurements/heldout-matrix-synthetic-01'/role/'attempt-0001')
        for ordinal in [0,25,True,1.0]:
            with self.subTest(ordinal=ordinal),self.assertRaises(ValueError):bound.slot(ordinal)
        for raw in bound.matrix.payloads:
            self.assertEqual(set(x.inputs.parse(raw)['case']), {'prompt','context'})
        self.assertNotIn('SYNTHETIC_PRIVATE_PROMPT',repr(bound))
        self.reader.assert_not_called()

    def test_source_product_sdk_calibration_verified_without_writes_or_launch(self):
        before = sorted(p.relative_to(self.repository).as_posix() for p in self.repository.rglob('*'))
        proof = self.verify()
        self.assertEqual(proof['snapshotResourceCount'],72)
        self.assertEqual(proof['sdkFileCount'],2)
        self.assertFalse(proof['launchEnabled'])
        self.assertEqual(proof['models'],0)
        self.assertEqual(proof['reservations'],0)
        self.assertEqual(before,sorted(p.relative_to(self.repository).as_posix() for p in self.repository.rglob('*')))
        self.reader.assert_called_once_with(x.inputs.PRIVATE_CASES)
        ledger = x.ledger.contract(self.bind().ledger_contract(io.encoded(proof)))
        self.assertEqual(ledger['resourceProofSha256'],io.sha(io.encoded(proof)))
        self.assertEqual(ledger['budget']['primary'],24)

    def test_source_dependency_drift_rejected_before_private_case_read(self):
        for name in ['host.py','production_heldout_ledger.py','production_heldout_execution.py','production_heldout_preflight.py']:
            path = self.repository/'evals/skills/routing'/name
            raw = path.read_bytes()
            path.write_bytes(raw+b'changed')
            with self.subTest(name=name),self.assertRaises(ValueError):self.verify()
            self.reader.assert_not_called()
            path.write_bytes(raw)

    def test_unadopted_or_changed_private_original_is_rejected(self):
        self.reader.return_value = self.raws['cases']+b' '
        with self.assertRaisesRegex(ValueError,'original set drift'):self.verify()

    def test_public_input_rehash_cannot_avoid_source_binding(self):
        self.raws['instructions'] += b'changed'
        self.input_contract['inputSha256']['instructions'] = io.sha(self.raws['instructions'])
        self.input_raw = io.encoded(self.input_contract)
        self.execution['inputContractSha256'] = io.sha(self.input_raw)
        with self.assertRaisesRegex(ValueError,'outside fixed Git'):self.verify()
        self.reader.assert_not_called()

    def test_private_conditions_cannot_be_public_92_or_expand_budgets(self):
        original = copy.deepcopy(self.execution)
        variants = [('version',preflight.public.matrix.VERSION),('campaignId','public-matrix-test'),
            ('outputRelativeRoot','.venv/matrix-test'),('sourceCommit','main'),('model','other'),('certifiesSkillGate',True)]
        for key,value in variants:
            self.execution = copy.deepcopy(original)
            self.execution[key] = value
            with self.subTest(key=key),self.assertRaises(ValueError):self.bind()
        for value in [True,23,25,92]:
            self.execution = copy.deepcopy(original)
            self.execution['budget']['primary'] = value
            with self.subTest(value=value),self.assertRaises(ValueError):self.bind()
        self.reader.assert_not_called()

    def test_deployment_cannot_escape_private_snapshot_or_change_pinned_versions(self):
        original = copy.deepcopy(self.deployment)
        for key,value in [('snapshotRelativePath','.venv/../snapshot'),('snapshotResourceCount',True),
            ('snapshotResourceCount',71),('sdkRelativePath','/outside'),('codexPath','/outside/codex'),
            ('sdkVersion','other'),('sourceCommit','b'*40),('executionSha256','c'*64)]:
            self.deployment = copy.deepcopy(original)
            self.deployment[key] = value
            self.repin_deployment()
            with self.subTest(key=key),self.assertRaises(ValueError):self.bind()
        self.reader.assert_not_called()

    def test_snapshot_and_sdk_drift_unknown_members_and_hardlinks_rejected(self):
        for path in [self.snapshot/next(iter(self.old.manifest['resources'])),self.old.sdk/'openai_codex/__init__.py']:
            raw = path.read_bytes()
            path.write_bytes(raw+b'changed')
            with self.subTest(path=path.name),self.assertRaises(ValueError):self.verify()
            self.reader.assert_not_called()
            path.write_bytes(raw)
        unknown = self.snapshot/'unknown-public-file'
        unknown.write_bytes(b'synthetic')
        with self.assertRaises(ValueError):self.verify()
        self.reader.assert_not_called()

    def test_expired_context_date_rejected_before_private_original_read(self):
        with patch.object(preflight, 'datetime') as clock:
            clock.now.return_value = datetime.now(preflight.ZoneInfo('Asia/Tokyo'))+timedelta(days=1)
            with self.assertRaisesRegex(ValueError,'current calibration date'):self.verify()
        self.reader.assert_not_called()

    def test_calibration_failure_rejected_before_private_original_read(self):
        self.old.calibration_mock.side_effect = ValueError('synthetic original calibration failure')
        with self.assertRaisesRegex(ValueError,'original calibration failure'):self.verify()
        self.reader.assert_not_called()

    def test_execution_and_deployment_raw_tampering_rejected(self):
        with self.assertRaises(ValueError):
            x.bind(io.encoded(self.execution),io.encoded(self.deployment)+b' ',self.input_raw,**self.raws)
        self.execution['inputContractSha256'] = '0'*64
        with self.assertRaises(ValueError):self.bind()

    def test_wrong_resource_proof_identity_cannot_bind_ledger(self):
        proof = self.verify()
        for key,value in [('status','public_resources_verified'),('sourceCommit','b'*40),
            ('inputContractSha256','0'*64),('executionSha256','1'*64)]:
            changed = dict(proof)
            changed[key] = value
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.bind().ledger_contract(io.encoded(changed))
