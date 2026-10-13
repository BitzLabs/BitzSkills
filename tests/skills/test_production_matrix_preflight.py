"""行列開始前の現物drift・未知ファイル・日付・固定Gitの検査。モデル0。"""
import copy
from datetime import timedelta
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'evals/skills/routing'))
import production_matrix_preflight as preflight
import test_production_matrix_inputs as inputs_fixture
import test_production_canary_runtime as runtime_fixture


class MatrixPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'.venv/test-temp');self.addCleanup(self.temp.cleanup)
        self.repository = Path(self.temp.name);self.source = 'a'*40
        fixture = inputs_fixture.MatrixInputTests(methodName='runTest');fixture.setUp()
        self.raws = fixture.raws;self.input_contract = fixture.contract
        self.originals = {name:(ROOT/name).read_bytes() for name in preflight.SOURCE_FILES}
        self.runtime_root = self.repository/'.venv/runtime';runtime_d = {}
        runtime_raw = runtime_fixture.fixture(self.runtime_root, runtime_d)
        self.originals[preflight.capture.fixed_runtime.MANIFEST] = runtime_raw
        context = preflight.trace.strict_json(self.originals[preflight.inventory.CONTEXT])
        context['date'] = preflight.datetime.now(preflight.ZoneInfo('Asia/Tokyo')).date().isoformat()
        self.originals[preflight.inventory.CONTEXT] = preflight.io.encoded(context)
        for name, raw in self.originals.items():
            path = self.repository/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        self.snapshot_relative = '.venv/matrix-routing-preparation-synthetic/snapshot'
        self.snapshot = self.repository/self.snapshot_relative;self.snapshot.mkdir(parents=True)
        skills = [];resources = {}
        for name in sorted(preflight.trace.SKILLS):
            package = 'bitz-core' if name == 'bitz-core' else 'bitz-sdd' if name.startswith('sdd-') else 'bitz-quality'
            relative = f'resources/{package}/skills/{name}/SKILL.md';raw = ('public synthetic '+name).encode()
            path = self.snapshot/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            self.originals['plugins/'+Path(relative).relative_to('resources').as_posix()] = raw
            resources[relative] = preflight.io.sha(raw)
            skills.append(dict(name=name,description='public synthetic',version='0.1.0',path=relative))
        self.manifest = dict(schemaVersion='1.0',scope='production-resource-snapshot-only',sourceCommit=self.source,
            candidateVersion='synthetic',skills=skills,resources=resources)
        self.manifest_raw = preflight.io.encoded(self.manifest);(self.snapshot/'manifest.json').write_bytes(self.manifest_raw)
        self.sdk_relative = '.venv/matrix-codex-python-sdk-deps-synthetic'
        self.sdk = self.repository/self.sdk_relative
        sdk_files = {}
        for name, raw in [('openai_codex/__init__.py',b'public synthetic sdk'),
                          ('openai_codex-0.160.1.dist-info/METADATA',b'Version: 0.160.1')]:
            path = self.sdk/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);sdk_files[name]=preflight.io.sha(raw)
        digest = hashlib.sha256()
        for name, value in sorted(sdk_files.items(), key=lambda item: Path(item[0]).parts):digest.update(name.encode()+b'\0');digest.update(bytes.fromhex(value))
        self.sdk_manifest = dict(version='0.160.1',files=sdk_files,treeSha256=digest.hexdigest())
        self.sdk_manifest_raw = preflight.io.encoded(self.sdk_manifest)
        input_raw = preflight.io.encoded(self.input_contract)
        rt = preflight.trace.strict_json(runtime_raw)
        pins = dict(snapshotManifest=preflight.io.sha(self.manifest_raw),runtimeManifest=preflight.io.sha(runtime_raw),
            calibrationManifest=preflight.io.sha(self.originals[preflight.capture.calibration.MANIFEST]),
            prelaunchReview='b'*64,sdk=digest.hexdigest(),cli=rt['files'][preflight.capture.fixed_runtime.VENDOR+'bin/codex'],
            contextProfile=preflight.io.sha(self.originals[preflight.inventory.CONTEXT]),
            decisionSchema=preflight.io.sha(preflight.decision_schema(self.originals[preflight.inventory.SCHEMA])))
        self.execution = dict(version=preflight.matrix.VERSION,campaignId='public-matrix-synthetic',sourceCommit=self.source,
            model='gpt-6.1-sol',inputContractSha256=preflight.io.sha(input_raw),outputRelativeRoot='.venv/matrix-synthetic',pins=pins,
            budget=dict(primary=92,independent=92,automaticRetries=0,delegations=0),
            timeoutSeconds=dict(primary=240,independent=300),cliVersion='0.160.1',certifiesSkillGate=False)
        self.input_raw = input_raw;self.bound = self.bind()
        self.deployment = dict(version=preflight.VERSION,sourceCommit=self.source,executionSha256=preflight.io.sha(self.bound.execution_raw),
            **runtime_d,codexVersion='codex-cli 0.160.1',sdkVersion='0.160.1',sdkRelativePath=self.sdk_relative,
            sdkTreeSha256=digest.hexdigest(),sdkManifestSha256=preflight.io.sha(self.sdk_manifest_raw),
            snapshotRelativePath=self.snapshot_relative,manifestSha256=preflight.io.sha(self.manifest_raw),snapshotResourceCount=6,
            contextProfileSha256=pins['contextProfile'],calibrationManifestSha256=pins['calibrationManifest'],certifiesSkillGate=False)
        self.patch(preflight.capture.fixed_runtime,'ROOT',self.runtime_root)
        self.git_mock = self.patch(preflight.guard,'git',side_effect=self.git)
        self.calibration_mock = self.patch(preflight.capture.calibration,'verify',return_value=dict(status='synthetic_old_calibration',sourceCommit='c'*40))

    def patch(self, target, name, *args, **kwargs):
        item=patch.object(target,name,*args,**kwargs);self.addCleanup(item.stop);return item.start()

    def git(self, repository, *args):
        self.assertEqual(repository,self.repository)
        if args == ('rev-parse',self.source+'^{commit}'):return (self.source+'\n').encode()
        if args == ('ls-tree','-r','-z',self.source,'--','plugins/bitz-core','plugins/bitz-sdd','plugins/bitz-quality'):
            return b''.join(('100644 blob '+'0'*40+'\t'+name+'\0').encode() for name in self.originals if name.startswith('plugins/'))
        self.assertEqual(args[0],'show');ref,name=args[1].split(':',1);self.assertEqual(ref,self.source)
        return self.originals[name]

    def bind(self):
        return preflight.matrix.bind(preflight.io.encoded(self.execution),self.input_raw,**self.raws)

    def verify(self):
        return preflight.verify_resources(self.repository,self.bound,preflight.io.encoded(self.deployment),self.sdk_manifest_raw)

    def test_public_resources_and_runtime_are_verified_without_launch_or_shared_writes(self):
        before = sorted(p.relative_to(self.repository).as_posix() for p in self.repository.rglob('*'))
        result = self.verify()
        self.assertEqual(result['sdkFileCount'],2);self.assertEqual(result['snapshotResourceCount'],6)
        self.assertEqual(result['sdkTreeSha256'],preflight.capture.sdk.tree_hash(self.sdk))
        self.assertEqual(result['runtime']['status'],'fixed_runtime_bytes_match')
        self.assertEqual(result['originalCalibration']['sourceCommit'],'c'*40)
        for name in ['launchEnabled','eligibleForMeasurement','physicalMatrixIsolationAndArgvTested','independentPrelaunchReviewPerformed','certifiesSkillGate']:
            self.assertFalse(result[name])
        self.assertEqual(result['realReservations'],0)
        self.assertEqual(before,sorted(p.relative_to(self.repository).as_posix() for p in self.repository.rglob('*')))

    def test_closed_deployment_paths_boolean_count_source_and_execution_rejected_before_reads(self):
        original = copy.deepcopy(self.deployment)
        for key,value in [('sourceCommit','f'*40),('executionSha256','e'*64),('snapshotResourceCount',True),
                          ('snapshotRelativePath','.venv/../snapshot'),('sdkRelativePath','.venv/other'),
                          ('codexPath','/outside/cli'),('sdkVersion','other'),('certifiesSkillGate',True),('unknown',True)]:
            self.deployment=copy.deepcopy(original);self.deployment[key]=value
            with self.subTest(key=key),patch.object(preflight.io,'read_regular',side_effect=AssertionError('early read')),self.assertRaises(ValueError):self.verify()

    def test_rehashed_expectations_still_must_match_fixed_git_before_snapshot_reads(self):
        cases=preflight.trace.strict_json(self.raws['routing']);cases[0]['expected']['outcome']='stop'
        self.raws['routing']=preflight.io.encoded(cases);self.input_contract['inputSha256']['routing']=preflight.io.sha(self.raws['routing'])
        self.input_raw=preflight.io.encoded(self.input_contract);self.execution['inputContractSha256']=preflight.io.sha(self.input_raw)
        self.bound=self.bind();self.deployment['executionSha256']=preflight.io.sha(self.bound.execution_raw)
        with self.assertRaisesRegex(ValueError,'outside fixed Git'):self.verify()

    def test_fixed_source_hardlink_and_changed_driver_are_rejected(self):
        path=self.repository/'evals/skills/routing/production_matrix_preflight.py';original=path.read_bytes();path.write_bytes(original+b'changed')
        with self.assertRaisesRegex(ValueError,'fixed source drift'):self.verify()
        path.write_bytes(original);os.link(path,self.repository/'public-linked.py')
        with self.assertRaisesRegex(ValueError,'single-link'):self.verify()

    def test_snapshot_unknown_protected_member_is_never_read(self):
        path=self.snapshot/'.env';path.write_bytes(b'SYNTHETIC_DO_NOT_READ');read=preflight.io.read_regular
        def monitor(p):
            self.assertNotEqual(p,path);return read(p)
        with patch.object(preflight.io,'read_regular',side_effect=monitor),self.assertRaisesRegex(ValueError,'unknown matrix'):self.verify()

    def test_sdk_unknown_protected_or_cached_member_is_never_read(self):
        for name in ['.env','__pycache__/synthetic.pyc','openai_codex/auth.json']:
            path=self.sdk/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'SYNTHETIC_DO_NOT_READ');read=preflight.io.read_regular
            def monitor(p):self.assertNotEqual(p,path);return read(p)
            with self.subTest(name=name),patch.object(preflight.io,'read_regular',side_effect=monitor),self.assertRaisesRegex(ValueError,'unknown matrix'):self.verify()
            path.unlink()
            if '__pycache__' in name:path.parent.rmdir()

    def test_snapshot_and_sdk_bytes_links_and_missing_member_are_rejected(self):
        for root,relative in [(self.snapshot,next(iter(self.manifest['resources']))),(self.sdk,'openai_codex/__init__.py')]:
            path=root/relative;original=path.read_bytes()
            for fault in ['bytes','missing','symlink','hardlink']:
                if fault=='bytes':path.write_bytes(b'changed')
                elif fault=='missing':path.unlink()
                elif fault=='symlink':path.unlink();path.symlink_to(root/'missing')
                else:os.link(path,self.repository/'public-link')
                with self.subTest(root=root.name,fault=fault),self.assertRaises((ValueError,OSError)):self.verify()
                if fault=='symlink':path.unlink()
                if fault=='hardlink':(self.repository/'public-link').unlink()
                path.write_bytes(original)

    def test_snapshot_rehashed_from_another_source_or_wrong_count_is_rejected(self):
        for key,value in [('sourceCommit','d'*40),('resources',{})]:
            changed=copy.deepcopy(self.manifest);changed[key]=value;raw=preflight.io.encoded(changed)
            (self.snapshot/'manifest.json').write_bytes(raw);self.deployment['manifestSha256']=preflight.io.sha(raw)
            self.execution['pins']['snapshotManifest']=preflight.io.sha(raw);self.bound=self.bind();self.deployment['executionSha256']=preflight.io.sha(self.bound.execution_raw)
            with self.subTest(key=key),self.assertRaises(ValueError):self.verify()
        (self.snapshot/'manifest.json').write_bytes(self.manifest_raw)
        self.execution['pins']['snapshotManifest']=preflight.io.sha(self.manifest_raw);self.bound=self.bind()
        self.deployment.update(manifestSha256=preflight.io.sha(self.manifest_raw),snapshotResourceCount=7,executionSha256=preflight.io.sha(self.bound.execution_raw))
        with self.assertRaisesRegex(ValueError,'count drift'):self.verify()

    def test_rehashed_snapshot_cannot_omit_tracked_git_resources(self):
        self.originals['plugins/bitz-quality/README.md']=b'public missing from manifest'
        with self.assertRaisesRegex(ValueError,'complete Git resources'):self.verify()

    def test_date_and_cli_binary_pin_are_checked_separately_from_old_calibration(self):
        tomorrow=preflight.datetime.now(preflight.ZoneInfo('Asia/Tokyo'))+timedelta(days=1)
        with patch.object(preflight,'datetime') as clock:
            clock.now.return_value=tomorrow
            with self.assertRaisesRegex(ValueError,'date differs'):self.verify()
        self.execution['pins']['cli']='d'*64;self.bound=self.bind();self.deployment['executionSha256']=preflight.io.sha(self.bound.execution_raw)
        with self.assertRaisesRegex(ValueError,'CLI executable pin'):self.verify()
        self.calibration_mock.assert_not_called()

    def test_sdk_manifest_unknown_name_or_tree_rehash_cannot_bypass_execution_pin(self):
        original=copy.deepcopy(self.sdk_manifest)
        for name in ['openai_codex/auth.json','openai_codex/../outside.py','other/__init__.py']:
            value=copy.deepcopy(original);value['files'][name]='c'*64;raw=preflight.io.encoded(value)
            self.deployment['sdkManifestSha256']=preflight.io.sha(raw)
            with self.subTest(name=name),self.assertRaises(ValueError):preflight.sdk_manifest(raw,self.deployment)
        value=copy.deepcopy(original);value['files']['openai_codex/__init__.py']='c'*64;raw=preflight.io.encoded(value)
        self.deployment['sdkManifestSha256']=preflight.io.sha(raw)
        with self.assertRaisesRegex(ValueError,'pinned tree'):preflight.sdk_manifest(raw,self.deployment)


if __name__=='__main__':unittest.main()
