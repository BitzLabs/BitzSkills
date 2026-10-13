from pathlib import Path,PurePosixPath
import hashlib,io,json,subprocess,tarfile
root=Path.cwd();out=root/'.venv/r09-resource-validation-01'
refs={'old':'ee3a1f1d6963a917bbf9425c55f64413db7e4ab1','candidate':'123c89baf6efc094aaa8065cee1f7adaf4286fea'}
plugins=['bitz-core','bitz-sdd','bitz-quality'];sha=lambda raw:hashlib.sha256(raw).hexdigest()
records={}
def export(label,ref):
 raw=subprocess.check_output(['git','archive','--format=tar',ref,*['plugins/'+n for n in plugins]],cwd=root)
 (out/(label+'.tar')).write_bytes(raw);base=out/label;base.mkdir();expected={}
 with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
  members=archive.getmembers()
  for member in members:
   path=PurePosixPath(member.name)
   assert not path.is_absolute() and all(part not in {'.','..',''} for part in path.parts)
   assert path.parts[0]=='plugins' and (len(path.parts)==1 or path.parts[1] in plugins)
   assert member.isdir() or member.isfile()
  for member in members:
   path=base/member.name
   if member.isdir():path.mkdir(parents=True,exist_ok=True);continue
   assert Path(member.name).name not in {'.env','auth.json','credentials.json'}
   data=archive.extractfile(member).read();path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);expected[member.name]=sha(data)
 versions={n:json.loads((base/'plugins'/n/'plugin.json').read_bytes())['version'] for n in plugins}
 records[label]=dict(sourceCommit=ref,archiveSha256=sha(raw),fileSha256=expected,versions=versions,skillEntries=sorted(str(p.relative_to(base)) for p in base.glob('plugins/*/skills/*/SKILL.md')))
 return base,expected
def verify(base,expected):
 actual={}
 for p in base.rglob('*'):
  assert not p.is_symlink()
  if p.is_file():
   name=str(p.relative_to(base));assert name in expected,'unknown resource';actual[name]=sha(p.read_bytes())
 assert actual==expected,'missing or changed resource'
 return len(actual)
old,oldhash=export('old',refs['old']);candidate,newhash=export('candidate',refs['candidate'])
assert len(records['candidate']['skillEntries'])==6
assert verify(candidate,newhash)>0;assert verify(old,oldhash)>0
active=out/'active.json';active.write_text(json.dumps(dict(sourceCommit=refs['old'],directory='old')))
active.write_text(json.dumps(dict(sourceCommit=refs['candidate'],directory='candidate')))
assert json.loads(active.read_text())['sourceCommit']==refs['candidate'];verify(candidate,newhash)
active.write_text(json.dumps(dict(sourceCommit=refs['old'],directory='old')))
assert json.loads(active.read_text())['sourceCommit']==refs['old'];verify(old,oldhash)
# 複製した不適合だけを壊す。原候補と旧資源は保持する。
bad=out/'negative';bad.mkdir();name=next(iter(newhash));target=bad/name;target.parent.mkdir(parents=True);target.write_bytes(b'corrupt public resource copy')
try:verify(bad,newhash)
except AssertionError as exc:negative=dict(rejected=True,reason=str(exc))
else:raise AssertionError('corrupt copy accepted')
verify(candidate,newhash);verify(old,oldhash)
summary=dict(status='local_resource_export_update_pointer_rollback_hash_checks_passed',records=records,negative=negative,oldBytesUnchanged=True,candidateBytesUnchanged=True,modelInvocations=0,actualHostInstallation=False,actualHostUpdate=False,actualHostRollback=False,coreWheelInstallationTestedByThisRun=False,coreMissingModelBehaviorTested=False,coreMismatchModelBehaviorTested=False,certifiesDistribution=False)
(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(status=summary['status'],counts={k:len(v['fileSha256']) for k,v in records.items()},versions={k:v['versions'] for k,v in records.items()},sixSkills=len(records['candidate']['skillEntries']),negative=negative),ensure_ascii=False))
