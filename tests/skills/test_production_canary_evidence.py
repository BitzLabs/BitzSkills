"""原artifactの読取り境界と固定入力・予約の改変拒否。モデル呼出し0。"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_canary_evidence as evidence
import test_routing_host as host_fixture
import test_production_canary_runtime as runtime_fixture

ledger, capture, trace = evidence.ledger, evidence.capture, evidence.trace


class CanaryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.venv' / 'test-temp')
        self.addCleanup(self.temp.cleanup)
        self.repository = Path(self.temp.name)
        self.source = 'b' * 40
        fixture = host_fixture.RoutingHostTests(methodName='runTest')
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        self.contract = json.loads((ROOT / capture.CONTRACT).read_bytes())
        context_raw = getattr(self, 'context_profile_raw', (ROOT / evidence.CONTEXT).read_bytes())
        self.contract['contextProfileSha256'] = ledger.sha(context_raw)
        runtime_root=self.repository/'fixed-runtime'
        runtime_raw=runtime_fixture.fixture(runtime_root,self.contract)
        self.patch(capture.fixed_runtime,'ROOT',new=runtime_root)
        runtime_proof=capture.fixed_runtime.verify(runtime_raw,self.contract)
        self.snapshot = self.repository / evidence.SNAPSHOT
        self.snapshot.mkdir(parents=True)
        manifest_raw = (fixture.snapshot / 'manifest.json').read_bytes()
        self.contract['manifestSha256'] = ledger.sha(manifest_raw)
        self.git_raws = {
            capture.CONTRACT: ledger.encoded(self.contract),
            evidence.CASES: getattr(self,'cases_raw',(ROOT / evidence.CASES).read_bytes()),
            evidence.CATALOG: (ROOT / evidence.CATALOG).read_bytes(),
            evidence.INSTRUCTIONS: getattr(self,'instructions_raw',(ROOT / evidence.INSTRUCTIONS).read_bytes()),
            evidence.SCHEMA: (ROOT / evidence.SCHEMA).read_bytes(),
            evidence.CONTEXT: context_raw,
            capture.fixed_runtime.MANIFEST: runtime_raw,
        }
        for name in fixture.manifest['resources']:
            raw = (fixture.snapshot / name).read_bytes()
            path = self.snapshot / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            self.git_raws['plugins/' + str(Path(name).relative_to('resources'))] = raw
        (self.snapshot / 'manifest.json').write_bytes(manifest_raw)
        self.source_evidence = {'status': 'fixed_source_matches', 'sourceCommit': self.source,
            'observedHead': self.source, 'headIsCondition': False,
            'sourceSha256': {p: '1' * 64 for p in self.contract['sourceFiles']}}
        self.patch(evidence.guard, 'git', side_effect=self.git)
        self.patch(evidence.guard, 'verify', return_value=self.source_evidence)
        self.git_raws[capture.calibration.MANIFEST]=b'public synthetic calibration manifest'
        self.patch(capture.calibration,'verify',return_value=dict(status='original_local_calibration_matches'))
        self.storage = self.repository / 'ledger'
        self.patch(ledger, 'common_ledger_path', return_value=self.storage)
        self.patch(ledger,'verify_predecessor',return_value=dict(status='public synthetic predecessor'))
        self.fixed = evidence.load_fixed_inputs(self.repository, self.source)
        self.bound = self.fixed.bound
        self.instance = ledger.Ledger(self.storage, self.bound, require_independent_reviews=True)
        self.attempt = self.instance.reserve()
        self.base = self.repository / self.attempt['outputRelativePath']
        self.base.mkdir(parents=True)
        self.originals = {name: b'' for name in evidence.FIXED_ARTIFACTS}
        self.originals.update({
            'contract.json': self.bound.contract_raw, 'reservation.json': ledger.encoded(self.attempt),
            'model-input.json': self.bound.payloads[0], 'decision-schema.json': self.fixed.decision_schema_raw,
            'runtime-result.json': ledger.encoded(dict(exitCode=0, forcedShutdown=False, captureIntegrity=True)),
            'isolated-result.json': b'{"sdkErrorType":null}',
            'version.stdout': (self.contract['codexVersion'] + '\n').encode(),
            'config.json': ledger.encoded(capture.config_for(self.base, self.bound.contract, repository=self.repository)),
            'invocation.json': ledger.encoded(dict(argv=capture.namespace_command(self.base, self.bound.contract, repository=self.repository), sourceCommit=self.source,
                maximumLogicalTurns=1, modelInputSha256=self.attempt['modelInputSha256'])),
            'rollout-traces/synthetic/manifest.json': b'{}',
            'rollout-traces/synthetic/trace.jsonl': b'{}\n',
            'rollout-traces/synthetic/payloads/1.json': b'{}',
        })
        for name, raw in self.originals.items():
            path = self.base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.receipt = dict(status='primary_capture_awaits_parent_and_independent_review',
            sourceCommit=self.source, attempt=self.attempt,
            sourceGuards=dict.fromkeys(['before', 'invoke', 'after'], self.source_evidence),
            runtimeGuards=dict.fromkeys(['before','invoke','after'],runtime_proof),
            namespaceExitCode=0, timedOut=False, elapsedSeconds=2.5,
            artifactSha256={name: ledger.sha(raw) for name, raw in self.originals.items()},
            primaryModelTrajectories=1, independentReviewPerformed=False, automaticRetries=0,
            certifiesApiRequestHardCap=False, eligibleForMeasurement=False, phaseComplete=False)
        self.persist()

    def patch(self, target, name, **kwargs):
        value = patch.object(target, name, **kwargs)
        self.addCleanup(value.stop)
        return value.start()

    def git(self, repository, *args):
        self.assertEqual(repository, self.repository)
        if args == ('rev-parse', self.source + '^{commit}'):
            return self.source.encode() + b'\n'
        self.assertEqual(args[0], 'show')
        self.assertTrue(args[1].startswith(self.source + ':'))
        return self.git_raws[args[1].split(':', 1)[1]]

    def persist(self):
        (self.base / 'receipt.json').write_bytes(ledger.encoded(self.receipt))

    def verify(self):
        return evidence.verify_capture(self.repository, self.source, 1)

    def rewrite(self, name, raw):
        (self.base / name).write_bytes(raw)
        self.receipt['artifactSha256'][name] = ledger.sha(raw)
        self.persist()

    def test_original_inputs_and_shared_reservation_pass_without_certification(self):
        result = self.verify()
        self.assertEqual(result['status'], 'primary_artifacts_and_fixed_inputs_verified')
        for key in ['eligibleForMeasurement', 'certifiesBehavior', 'certifiesSkillGate',
                    'independentReviewPerformed', 'ledgerFinalized']:
            self.assertIs(result[key], False)
        self.assertIs(result['invocationArgvVerified'], True)
        self.assertEqual(result['sharedReservationSha256'], ledger.sha(ledger.encoded(self.attempt)))
        self.assertFalse((self.storage / 'review-0001.json').exists())
        with self.assertRaises(ValueError): self.instance.reserve()

    def test_verification_never_initializes_reserves_or_finalizes_ledger(self):
        with patch.object(ledger.Ledger, '__init__', side_effect=AssertionError('ledger mutation')), \
             patch.object(ledger.Ledger, 'reserve', side_effect=AssertionError('primary invocation')), \
             patch.object(ledger.Ledger, 'reserve_independent_review', side_effect=AssertionError('review invocation')), \
             patch.object(ledger.Ledger, 'record_verified_review', side_effect=AssertionError('ledger finalization')):
            self.verify()

    def test_opaque_auth_cache_state_contents_are_never_read(self):
        for directory in evidence.OPAQUE_DIRECTORIES:
            path = self.base / directory
            path.mkdir()
            (path / 'NEVER_READ_SECRET').write_bytes(b'private sentinel')
        original_read = evidence.read_original
        def limited_read(path):
            self.assertFalse(any(part in evidence.OPAQUE_DIRECTORIES for part in path.relative_to(self.repository).parts))
            return original_read(path)
        with patch.object(evidence, 'read_original', side_effect=limited_read): self.verify()

    def test_untrusted_receipt_paths_are_rejected_before_artifact_reads(self):
        for name in ['codex-home/auth.json', 'state/manifest.json', '.env', '/tmp/outside', '../outside',
                     'rollout-traces/session/payloads/../auth.json', 'rollout-traces/auth/manifest.json',
                     'rollout-traces/session/payloads/0.json', 'rollout-traces/session/payloads/.env',
                     'rpc-in.jsonl/../.env', 'rpc-in.jsonl\\..\\.env']:
            bad = copy.deepcopy(self.receipt)
            bad['artifactSha256'][name] = '1' * 64
            (self.base / 'receipt.json').write_bytes(ledger.encoded(bad))
            original_read = evidence.read_original
            allowed = {self.base / 'receipt.json', self.snapshot / 'manifest.json'} | {
                self.snapshot / p for p in trace.strict_json(self.bound.raw_inputs[2])['resources']}
            def limited_read(path):
                self.assertIn(path, allowed, 'artifact read before allowlist validation')
                return original_read(path)
            with self.subTest(name=name), patch.object(evidence, 'read_original', side_effect=limited_read), self.assertRaises(ValueError):
                self.verify()
        self.persist()

    def test_missing_or_unlisted_artifacts_and_unknown_actual_files_reject(self):
        path = self.base / 'rpc-out.jsonl'
        path.unlink()
        with self.assertRaises(ValueError): self.verify()
        path.write_bytes(self.originals['rpc-out.jsonl'])
        del self.receipt['artifactSha256']['rpc-out.jsonl']
        self.persist()
        with self.assertRaises(ValueError): self.verify()
        self.receipt['artifactSha256']['rpc-out.jsonl'] = ledger.sha(path.read_bytes())
        self.persist()
        (self.base / '.env').touch()
        with self.assertRaises(ValueError): self.verify()

    def test_symlink_original_and_parent_and_payload_are_rejected(self):
        for name in ['rpc-out.jsonl', 'rollout-traces/synthetic/payloads/1.json']:
            path = self.base / name
            path.unlink()
            path.symlink_to(self.base / 'namespace.stdout')
            with self.subTest(name=name), self.assertRaises(ValueError): self.verify()
            path.unlink()
            path.write_bytes(self.originals[name])
        payloads = self.base / 'rollout-traces/synthetic/payloads'
        payloads.rename(payloads.with_name('original-payloads'))
        payloads.symlink_to(payloads.with_name('original-payloads'), target_is_directory=True)
        with self.assertRaises(ValueError): self.verify()
        with self.assertRaises(OSError): evidence.read_original(payloads / '1.json')

    def test_hash_and_fixed_original_inputs_reject_even_with_rehashed_receipt(self):
        for name in ['contract.json', 'reservation.json', 'model-input.json', 'decision-schema.json']:
            original = self.originals[name]
            (self.base / name).write_bytes(original + b' ')
            with self.subTest(name=name, level='hash'), self.assertRaises(ValueError): self.verify()
            self.rewrite(name, original + b' ')
            with self.subTest(name=name, level='fixed'), self.assertRaises(ValueError): self.verify()
            self.rewrite(name, original)

    def test_receipt_source_attempt_policy_runtime_and_elapsed_drift_reject(self):
        for key, value in [('sourceCommit', 'a' * 40), ('namespaceExitCode', False), ('timedOut', True),
                           ('primaryModelTrajectories', True), ('elapsedSeconds', True), ('elapsedSeconds', -1),
                           ('independentReviewPerformed', True), ('phaseComplete', True),
                           ('attempt', {**self.attempt, 'attempt': True})]:
            bad = copy.deepcopy(self.receipt)
            bad[key] = value
            (self.base / 'receipt.json').write_bytes(ledger.encoded(bad))
            with self.subTest(key=key), self.assertRaises(ValueError): self.verify()
        self.persist()
        self.rewrite('runtime-result.json', b'{"exitCode":0,"forcedShutdown":false,"captureIntegrity":false}')
        with self.assertRaises(ValueError): self.verify()

    def test_stop_markers_and_incomplete_or_extra_rollout_reject(self):
        for name in evidence.STOP_FILES:
            path = self.base / name
            path.write_bytes(b'{}')
            with self.subTest(name=name), self.assertRaises(ValueError): self.verify()
            path.unlink()
        extra = self.base / 'rollout-traces/other'
        extra.mkdir()
        with self.assertRaises(ValueError): self.verify()
        extra.rmdir()
        # rollout全体をreceiptから落としても受理しない。
        with self.assertRaises(ValueError):
            evidence.artifact_inventory(self.base, {k: v for k, v in self.receipt['artifactSha256'].items()
                if not k.startswith('rollout-traces/')})
        path = self.base / 'rollout-traces/synthetic/trace.jsonl'
        path.unlink()
        del self.receipt['artifactSha256'][str(path.relative_to(self.base))]
        self.persist()
        with self.assertRaises(ValueError): self.verify()

    def test_shared_campaign_reservation_and_later_attempt_drift_reject(self):
        path = self.storage / 'attempt-0001.json'
        path.write_bytes(ledger.encoded({**self.attempt, 'modelInputSha256': '9' * 64}))
        with self.assertRaises(ValueError): self.verify()
        path.write_bytes(ledger.encoded(self.attempt))
        later = self.storage / 'attempt-0002.json'
        later.write_bytes(ledger.encoded(self.bound.attempt(2)))
        later.chmod(0o600)
        with self.assertRaises(ValueError): self.verify()
        later.unlink()
        self.storage.chmod(0o755)
        with self.assertRaises(ValueError): self.verify()
        self.storage.chmod(0o700)
        campaign = self.storage / 'campaign.json'
        value = trace.strict_json(campaign.read_bytes())
        value['reviewReservationRequired'] = False
        campaign.write_bytes(ledger.encoded(value))
        with self.assertRaises(ValueError): self.verify()

    def test_fixed_git_schema_manifest_resources_and_snapshot_path_binding(self):
        self.git_raws[evidence.SCHEMA] = b'{"properties":{"selectedEntry":{"enum":[]}},"changed":true}'
        with self.assertRaises(ValueError): self.verify()
        self.git_raws[evidence.SCHEMA] = (ROOT / evidence.SCHEMA).read_bytes()
        resource = next(iter(trace.strict_json(self.bound.raw_inputs[2])['resources']))
        path = self.snapshot / resource
        path.write_bytes(b'changed resource')
        with self.assertRaises(ValueError): self.verify()
        path.write_bytes(self.git_raws['plugins/' + str(Path(resource).relative_to('resources'))])
        self.contract['snapshotRelativePath'] = 'codex-home/auth.json'
        self.git_raws[capture.CONTRACT] = ledger.encoded(self.contract)
        with self.assertRaises(ValueError): self.verify()

    def test_version_config_and_source_guard_drift_reject(self):
        for name, raw in [('version.stdout', b'codex-cli 0.162.1\n'), ('version.stderr', b'unknown warning'),
                          ('config.json', b'{"model":"other"}')]:
            self.rewrite(name, raw)
            with self.subTest(name=name), self.assertRaises(ValueError): self.verify()
            self.rewrite(name, self.originals[name])
        self.receipt['sourceGuards']['after'] = {**self.source_evidence, 'sourceSha256': {}}
        self.persist()
        with self.assertRaises(ValueError): self.verify()

    def test_exponent_overflow_elapsed_is_rejected(self):
        raw = ledger.encoded(self.receipt).replace(b'"elapsedSeconds":2.5', b'"elapsedSeconds":1e999')
        (self.base / 'receipt.json').write_bytes(raw)
        with self.assertRaises(ValueError): self.verify()

    def test_elapsed_receipt_includes_post_capture_hashing_and_is_not_cli_deadline(self):
        self.receipt['elapsedSeconds'] = 301.5
        self.persist()
        self.assertEqual(self.verify()['status'], 'primary_artifacts_and_fixed_inputs_verified')

    def test_current_head_move_does_not_replace_fixed_capture_source(self):
        self.source_evidence['observedHead'] = 'c' * 40
        # receipt保存bytesの観測HEADは取得時sourceのまま。
        self.assertEqual(self.verify()['sourceCommit'], self.source)

    def test_forbidden_actual_rollout_group_is_rejected_before_listing(self):
        group = self.base / 'rollout-traces/synthetic'
        forbidden = group.with_name('auth')
        group.rename(forbidden)
        original_iterdir = Path.iterdir
        def limited_iterdir(path):
            self.assertNotEqual(path, forbidden, 'forbidden rollout directory enumerated')
            return original_iterdir(path)
        with patch.object(Path, 'iterdir', limited_iterdir), self.assertRaises(ValueError):
            self.verify()

    def test_shared_campaign_hardlink_is_rejected_before_read(self):
        campaign = self.storage / 'campaign.json'
        alias = self.repository / 'public-campaign-alias.json'
        alias.hardlink_to(campaign)
        original_read = Path.read_bytes
        def limited_read(path):
            self.assertNotEqual(path, campaign, 'shared hardlink was read')
            return original_read(path)
        with patch.object(Path, 'read_bytes', limited_read), self.assertRaises(ValueError):
            self.verify()

    def test_invocation_argv_override_rejects_even_if_rehashed(self):
        invocation = trace.strict_json(self.originals['invocation.json'])
        invocation['argv'].extend(['--unexpected'])
        self.rewrite('invocation.json', ledger.encoded(invocation))
        with self.assertRaises(ValueError): self.verify()

    def test_original_regular_file_boundary_rejects_hardlinks_and_directories(self):
        source = self.base / 'namespace.stdout'
        target = self.base / 'hardlink'
        target.hardlink_to(source)
        with self.assertRaises(ValueError): evidence.read_original(source)
        with self.assertRaises(ValueError): evidence.read_original(self.base / 'rollout-traces')
        with self.assertRaises(ValueError): evidence.read_original(Path('relative'))


if __name__ == '__main__':
    unittest.main()
