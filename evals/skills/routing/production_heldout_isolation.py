"""合成1入力だけの局所namespace検査。network遮断・認証mountなし・SDK/model起動0。"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import time

import production_heldout_launch as launch

x, p = launch.x, launch.preflight.public
io, require = launch.io, launch.require
ROOT = Path(__file__).resolve().parents[3]
PROMPT = 'LOCAL_HELDOUT_NAMESPACE_PROBE_ONLY'


def local_root(repository, base):
    require(isinstance(repository, Path) and repository.is_absolute() and '..' not in repository.parts
        and isinstance(base, Path) and base.parent == repository/'.venv'
        and re.fullmatch(r'heldout-local-isolation-[a-z0-9]+(?:-[a-z0-9]+)*', base.name) is not None,
        'heldout local probe boundary')
    io.safe_tree(repository)
    io.safe_tree(base)


def command(repository, execution_raw, deployment_raw, base):
    local_root(repository, base)
    original = launch.namespace_command(repository, execution_raw, deployment_raw, 1)
    primary = str(launch.stage_root(execution_raw, 1))
    args, index = [], 0
    while index < len(original):
        # 有料構成の標準CLI認証mountだけを除く。認証内容は読まない。
        if original[index:index+3] == ['--ro-bind', str(launch.AUTH), '/home/hide/.codex/auth.json']:
            index += 3
            continue
        value = original[index]
        if value.startswith(primary):
            value = str(base)+value[len(primary):]
        if value == str(repository/'evals/skills/routing/production_heldout_capture.py'):
            value = str(repository/'evals/skills/routing/production_heldout_isolation.py')
        if value == '--isolated':
            value = '--probe'
        args.append(value)
        index += 1
    args.insert(1, '--unshare-net')
    require(str(launch.AUTH) not in args and '--unshare-net' in args and args[-2:] == ['--probe', str(base)],
        'heldout local credential/network boundary')
    return args


def environment(execution_raw, deployment_raw, base):
    primary = str(launch.stage_root(execution_raw, 1))
    return {key: str(base)+value[len(primary):] if value.startswith(primary) else value
        for key, value in launch.environment(execution_raw, deployment_raw, 1).items()}


def probe(base):
    os.umask(0o077)
    local_root(ROOT, base)
    execution_raw, deployment_raw = (io.read_regular(base/name) for name in ['contract.json', 'deployment.json'])
    d = x.deployment_for_execution(execution_raw, deployment_raw)
    hidden = not any((ROOT/name).exists() for name in ['.git', '.spec', 'docs', 'tests', 'evals/skills/results'])
    hidden = hidden and not x.inputs.PRIVATE_CASES.exists()
    credentials_hidden = not launch.AUTH.exists()
    payload = x.inputs.parse(io.read_regular(base/'model-input.json'))
    require(payload == dict(instructions='LOCAL_ONLY_NO_MODEL', eventCatalog={}, case=dict(prompt=PROMPT, context=[])),
        'heldout local synthetic payload only')
    sdk = p.sdk_manifest(io.read_regular(base/'sdk-manifest.json'), d)
    require({name: io.sha(raw) for name, raw in p.exact_tree(ROOT/d['sdkRelativePath'], sdk).items()} == sdk,
        'heldout probe SDK drift')
    p.capture.fixed_runtime.verify(io.read_regular(base/'runtime-manifest.json'), d)
    snapshot = ROOT/d['snapshotRelativePath']
    manifest_raw = io.read_regular(snapshot/'manifest.json')
    require(io.sha(manifest_raw) == d['manifestSha256'], 'heldout probe manifest drift')
    manifest = x.inputs.parse(manifest_raw)
    expected = dict(manifest['resources'], **{'manifest.json': d['manifestSha256']})
    require(len(manifest['resources']) == 72 and
        {name: io.sha(raw) for name, raw in p.exact_tree(snapshot, expected).items()} == expected,
        'heldout probe resource drift')
    host_net = x.inputs.parse(io.read_regular(base/'parent-network.json'))['inode']
    isolated = type(host_net) is int and os.stat('/proc/self/ns/net').st_ino != host_net
    result = dict(status='heldout_primary_local_probe_completed', networkNamespaceIsolated=isolated,
        credentialsHidden=credentials_hidden, privateCorpusHidden=hidden, primaryPayloadProjectionVerified=True,
        sdkFileCount=len(sdk), snapshotResourceCount=72, models=0, reservations=0)
    require(isolated and hidden and credentials_hidden, 'heldout probe isolation failed')
    io.exclusive(base/'probe-result.json', io.encoded(result))


def run(repository, execution_raw, deployment_raw, sdk_manifest_raw, base):
    """固定公開sourceと合成入力だけ。private台帳/ケースを読まない局所processを1回起動。"""
    local_root(repository, base)
    c = x.execution_contract(execution_raw)
    x.deployment_for_execution(execution_raw, deployment_raw)
    p.guard.verify(repository, c['sourceCommit'], list(launch.preflight.SOURCE_FILES))
    base.mkdir(mode=0o700)
    for name in ['work', 'tmp', 'codex-home', 'logs', 'state', 'rollout-traces']:
        (base/name).mkdir(mode=0o700)
    argv = command(repository, execution_raw, deployment_raw, base)
    plan = dict(argv=argv, environment=environment(execution_raw, deployment_raw, base),
        timeoutSeconds=60, processUmask=0o077, models=0, reservations=0)
    for name, raw in [('contract.json', execution_raw), ('deployment.json', deployment_raw),
        ('sdk-manifest.json', sdk_manifest_raw), ('runtime-manifest.json', p.guard.git(repository, 'show',
            c['sourceCommit']+':'+p.capture.fixed_runtime.MANIFEST)),
        ('model-input.json', io.encoded(dict(instructions='LOCAL_ONLY_NO_MODEL', eventCatalog={}, case=dict(prompt=PROMPT, context=[])))),
        ('parent-network.json', io.encoded(dict(inode=os.stat('/proc/self/ns/net').st_ino))),
        ('invocation.json', io.encoded(plan))]:
        io.exclusive(base/name, raw)
    begin = time.monotonic()
    error, result = None, None
    try:
        result = subprocess.run(argv, env=plan['environment'], capture_output=True, timeout=60, umask=0o077)
        io.exclusive(base/'stdout.bin', result.stdout)
        io.exclusive(base/'stderr.bin', result.stderr)
        require(result.returncode == 0 and result.stdout == result.stderr == b'', 'heldout local probe process failed')
        observed = x.inputs.parse(io.read_regular(base/'probe-result.json'))
        require(observed['status'] == 'heldout_primary_local_probe_completed'
            and all(observed[key] is True for key in ['networkNamespaceIsolated', 'credentialsHidden',
                'privateCorpusHidden', 'primaryPayloadProjectionVerified']), 'heldout local probe result')
        require(io.read_regular(base/'invocation.json') == io.encoded(plan), 'heldout actual local argv drift')
    except Exception as exc:
        error = type(exc).__name__
    proof = dict(status='heldout_primary_local_isolation_verified' if error is None else 'heldout_primary_local_isolation_failed',
        sourceCommit=c['sourceCommit'], conditionSha256=launch.condition_sha256(execution_raw, deployment_raw),
        actualExitCode=None if result is None else result.returncode, errorType=error, elapsedSeconds=time.monotonic()-begin,
        models=0, reservations=0, privateCaseContentsRead=False, actualArgvVerified=error is None,
        certifiesHeldoutLaunch=False)
    if error is None:
        proof.update({key: observed[key] for key in ['networkNamespaceIsolated', 'credentialsHidden',
            'privateCorpusHidden', 'primaryPayloadProjectionVerified']})
    io.exclusive(base/'local-proof.json', io.encoded(proof))
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', type=Path, required=True)
    args = parser.parse_args()
    try:
        probe(args.probe)
    except Exception:
        raise SystemExit(1)
