"""契約と追加ソースの接続を実Git/実guardで検査する。モデル・CLI起動0。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'evals/skills/routing'))
import production_canary_evidence as evidence
import production_canary_score as score
import source_guard as guard


class ProductionSourceIntegrationTests(unittest.TestCase):
    def test_real_git_guard_accepts_full_composed_source_sets_and_still_rejects_duplicates(self):
        contract=json.loads((ROOT/evidence.capture.CONTRACT).read_bytes())
        canonical=contract['sourceFiles']
        self.assertIn(evidence.AUDIT_SOURCES[0],canonical)
        self.assertTrue(set(score.SOURCES)<=set(canonical))
        with tempfile.TemporaryDirectory(dir=ROOT/'.venv/test-temp') as temporary:
            repository=Path(temporary)
            def git(*args):
                return subprocess.check_output(['git','-c','core.hooksPath=/dev/null','-c','user.name=Public Test',
                    '-c','user.email=public-test@example.invalid',*args],cwd=repository,stderr=subprocess.DEVNULL)
            git('init','--initial-branch=codex/public-source-fixture')
            names=list(dict.fromkeys([*canonical,*evidence.AUDIT_SOURCES,*score.SOURCES]))
            for name in names:
                path=repository/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'public source guard fixture\n')
            git('add','--',*names);git('commit','-m','test: 公開ソース集合の検査用fixtureを固定する')
            source=git('rev-parse','HEAD').decode().strip()
            for actual in [evidence.audit_sources(contract),score.source_names(contract)]:
                verified=guard.verify(repository,source,actual)
                self.assertEqual(set(verified['sourceSha256']),set(actual))
                self.assertEqual(verified['sourceCommit'],source)
            with self.assertRaisesRegex(ValueError,'duplicate'):
                guard.verify(repository,source,[*canonical,*score.SOURCES])
            changed=repository/score.SOURCES[0];changed.write_bytes(b'changed public fixture\n')
            with self.assertRaisesRegex(ValueError,'drift'):guard.verify(repository,source,score.source_names(contract))


if __name__=='__main__':unittest.main()
