"""実providerを使わず、shadow homeと追加準備の承認・旧停止保持を検査する。"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('native_actor_v03_tested',ROOT/'evals/skills/routing/native_actor_v03.py')
actor=importlib.util.module_from_spec(spec)
spec.loader.exec_module(actor)


class NativeShadowTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='native-shadow-test-',dir=ROOT/'.venv')
        self.addCleanup(temp.cleanup)
        self.directory=Path(temp.name)
        self.phase=self.directory/'phase';self.phase.mkdir(mode=0o700)
        (self.phase/'codex-home').mkdir(mode=0o700)
        self.home=self.directory/'original-home';self.home.mkdir(mode=0o700)
        for name in ['config.toml','installation_id','authentication-placeholder']:
            actor.exclusive(self.home/name,b'original-placeholder')
        (self.home/'tmp').mkdir();(self.home/'skills').mkdir()

    def test_only_initialization_state_is_fresh_and_existing_home_is_readonly(self):
        command=actor.shadow_home_bindings(self.phase,self.home)
        self.assertEqual(command[:3],['--bind',str(self.phase/'codex-home'),str(self.home)])
        readonly={command[i+1] for i,word in enumerate(command) if word=='--ro-bind'}
        self.assertEqual(readonly,{str(self.home/'authentication-placeholder'),str(self.home/'skills')})
        self.assertEqual(list((self.phase/'codex-home').iterdir()),[])

    def test_home_contents_are_not_read_or_copied(self):
        with patch.object(Path,'read_bytes',side_effect=AssertionError('do not read existing home')):
            command=actor.shadow_home_bindings(self.phase,self.home)
        self.assertIn(str(self.home/'skills'),command)
        self.assertEqual((self.home/'config.toml').read_bytes(),b'original-placeholder')

    def test_shadow_symlink_and_non_owner_only_destination_are_rejected(self):
        (self.phase/'codex-home').rmdir()
        (self.phase/'codex-home').symlink_to(self.home,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'shadow home destination'):
            actor.shadow_home_bindings(self.phase,self.home)
        (self.phase/'codex-home').unlink();(self.phase/'codex-home').mkdir(mode=0o755)
        (self.phase/'codex-home').chmod(0o755)
        with self.assertRaisesRegex(ValueError,'shadow home permissions'):
            actor.shadow_home_bindings(self.phase,self.home)

    def test_namespace_keeps_old_artifacts_and_current_captures_readonly(self):
        repo=self.directory/'repo';(repo/'.venv/snapshot').mkdir(parents=True)
        for name in actor.CONTROL_DIRS:(repo/name).mkdir(mode=0o700)
        ledger=repo/'.venv/routing-native-authoring-03';ledger.mkdir()
        private=self.directory/'private';private.mkdir()
        actor.exclusive(private/'retention.json',b'fixed')
        (private/'native-authoring-01').mkdir()
        phase=private/'native-authoring-03/creator';phase.mkdir(parents=True)
        (phase/'codex-home').mkdir(mode=0o700)
        shadow=['--bind',str(phase/'codex-home'),str(self.home)]
        with patch.object(actor,'shadow_home_bindings',return_value=shadow):
            command=actor.namespace(phase,ledger,['codex','exec'],repo=repo,private=private)
        readonly={command[i+1] for i,word in enumerate(command) if word=='--ro-bind'}
        for path in [private/'native-authoring-01',private/'retention.json',repo/'.venv/snapshot',ledger,phase/'trace.jsonl']:
            self.assertIn(str(path),readonly)
        with self.assertRaises(ValueError):
            actor.namespace(private/'native-authoring-01',ledger,['codex'],repo=repo,private=private)

    def approval(self,source):
        return {'status':'remaining_roles_authorized','executionSource':source,'maximumNewInvocations':2,
                'additionalPreparationModelCalls':0,'creatorSol':1,'reviewerSol':1,
                'previousAttemptsPreserved':True,'transmissionScope':'2026-10-06-private-sol-transmission'}

    def test_missing_or_wrong_source_approval_blocks_before_launch(self):
        ledger=self.directory/'ledger';ledger.mkdir()
        with self.assertRaises(FileNotFoundError):actor.require_budget_approval('a'*40,ledger)
        actor.exclusive(ledger/'budget-approval.json',actor.encoded(self.approval('b'*40)))
        with self.assertRaisesRegex(ValueError,'additional preparation approval'):
            actor.require_budget_approval('a'*40,ledger)

    def test_approval_is_bound_to_exact_budget_and_owner_only_record(self):
        ledger=self.directory/'ledger';ledger.mkdir()
        path=ledger/'budget-approval.json';source='a'*40
        actor.exclusive(path,actor.encoded(self.approval(source)))
        actor.require_budget_approval(source,ledger)
        value=self.approval(source);value['maximumNewInvocations']=4
        path.write_bytes(actor.encoded(value))
        with self.assertRaisesRegex(ValueError,'additional preparation approval'):
            actor.require_budget_approval(source,ledger)
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError,'approval permissions'):
            actor.require_budget_approval(source,ledger)

    def test_new_role_cap_cannot_be_reused_by_changing_source(self):
        ledger=self.directory/'ledger'
        actor.reserve('creator','a'*40,ledger)
        with self.assertRaises(FileExistsError):actor.reserve('creator','b'*40,ledger)
        self.assertEqual(json.loads((ledger/'creator.json').read_bytes())['attemptReserved'],1)

    def test_preparation_preserves_previous_stop_and_rejects_created_cases(self):
        private=self.directory/'private';private.mkdir()
        actor.exclusive(private/'retention.json',b'fixed')
        (private/'native-authoring-01').mkdir();(private/'native-authoring-02').mkdir();(private/'native-authoring-03').mkdir()
        for name in actor.CONTROL_DIRS:(private/name).mkdir()
        actor.check_preparation_outputs(private)
        actor.exclusive(private/'cases.json',b'unexpected-output')
        with self.assertRaisesRegex(ValueError,'preparation produced collection output'):
            actor.check_preparation_outputs(private)

    def test_previous_stop_and_native_bytes_cannot_be_discarded(self):
        repo=self.directory/'repo';ledger=repo/'.venv/routing-native-authoring-02';ledger.mkdir(parents=True)
        private=self.directory/'private';phase=private/'native-authoring-02/preparation';phase.mkdir(parents=True,mode=0o700)
        actor.exclusive(phase/'trace.jsonl',b'')
        actor.exclusive(phase/'stderr.log',b'\xfforiginal-native-error')
        actor.exclusive(phase/'response.json',actor.encoded({'status':'stopped'}))
        hashes={name:actor.collection.digest((phase/name).read_bytes()) for name in ['trace.jsonl','stderr.log','response.json']}
        value={'sourceCommit':actor.OLD_SOURCE,'role':'preparation','status':'native_completed',
               'actualExitCode':0,'artifactSha256':hashes}
        raw=actor.encoded(value);actor.exclusive(ledger/'preparation-result.json',raw)
        contract={'previousFailure':{'executionReceiptSha256':actor.collection.digest(raw),'captureSha256':hashes}}
        with patch.object(actor.collection.legacy,'ROOT',repo):
            actor.verify_previous_failure(contract,repo=repo,private=private)
            (phase/'stderr.log').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'old capture drift'):
                actor.verify_previous_failure(contract,repo=repo,private=private)


if __name__=='__main__':unittest.main()
