"""隔離namespace内の保持一次SDK worker。親側の予約・開始許可・証拠検査は別工程。"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

import production_heldout_launch as launch

x, p = launch.x, launch.preflight.public
io, require, trace = x.io, x.require, x.trace
ROOT = Path(__file__).resolve().parents[3]


def child_inputs(base):
    """コーパス/期待値を持たない子が検査できる固定bytesだけを検査する。"""
    execution_raw = io.read_regular(base/'contract.json')
    deployment_raw = io.read_regular(base/'deployment.json')
    c = x.execution_contract(execution_raw)
    d = x.deployment_for_execution(execution_raw, deployment_raw)
    identity = x.inputs.parse(io.read_regular(base/'reservation.json'))
    ordinal = launch.checked_identity(execution_raw, identity)
    require(base == launch.stage_root(execution_raw, ordinal), 'heldout child canonical root')
    require(not any((ROOT/name).exists() for name in ['.git', '.spec', 'docs', 'tests', 'evals/skills/results'])
        and not x.inputs.PRIVATE_CASES.exists(), 'heldout evaluation corpus visible in child')
    launch.prelaunch_review(execution_raw, deployment_raw, io.read_regular(base/'prelaunch-review.json'),
        io.read_regular(base/'prelaunch-report.json'), io.read_regular(base/'local-isolation-proof.json'))
    payload_raw = io.read_regular(base/'model-input.json')
    require(io.sha(payload_raw) == identity['payloadSha256'], 'heldout child input hash')
    payload = x.inputs.parse(payload_raw)
    require(isinstance(payload, dict) and set(payload) == {'instructions', 'eventCatalog', 'case'}
        and isinstance(payload['case'], dict) and set(payload['case']) == {'prompt', 'context'}
        and trace.project_case(payload['case']) == payload['case'], 'heldout child primary projection')
    require(io.read_regular(base/'invocation.json') == io.encoded(
        launch.invocation(ROOT, execution_raw, deployment_raw, identity)), 'heldout child invocation drift')
    sdk = p.sdk_manifest(io.read_regular(base/'sdk-manifest.json'), d)
    require({name: io.sha(raw) for name, raw in p.exact_tree(ROOT/d['sdkRelativePath'], sdk).items()} == sdk,
        'heldout child SDK drift')
    p.capture.fixed_runtime.verify(io.read_regular(base/'runtime-manifest.json'), d)
    schema_raw = io.read_regular(base/'decision-schema.json')
    require(io.sha(schema_raw) == c['pins']['decisionSchema'], 'heldout child schema drift')
    snapshot = ROOT/d['snapshotRelativePath']
    manifest_raw = io.read_regular(snapshot/'manifest.json')
    require(io.sha(manifest_raw) == d['manifestSha256'], 'heldout child snapshot drift')
    manifest, _, _ = trace.manifest_view(manifest_raw)
    require(manifest['sourceCommit'] == c['sourceCommit'] and len(manifest['resources']) == 72,
        'heldout child product identity')
    expected = dict(manifest['resources'], **{'manifest.json': d['manifestSha256']})
    require({name: io.sha(raw) for name, raw in p.exact_tree(snapshot, expected).items()} == expected,
        'heldout child product byte drift')
    require(io.read_regular(base/'launch-settings.json') == launch.launch_settings(execution_raw, deployment_raw),
        'heldout child launch settings drift')
    return c, d, payload_raw, schema_raw


def isolated(base):
    os.umask(0o077)
    c, d, payload_raw, schema_raw = child_inputs(base)
    sys.path.insert(0, str(ROOT/d['sdkRelativePath']))
    from openai_codex import CodexConfig, __version__
    from openai_codex.client import CodexClient
    require(__version__ == d['sdkVersion'], 'heldout child SDK version')
    version = subprocess.run([d['codexPath'], '--version'], capture_output=True, timeout=10)
    io.exclusive(base/'version.stdout', version.stdout)
    io.exclusive(base/'version.stderr', version.stderr)
    require(version.returncode == 0 and version.stdout == (d['codexVersion']+'\n').encode() and not version.stderr,
        'heldout child CLI version')
    io.exclusive(base/'config.json', io.encoded(p.capture.config_for(base, d, repository=ROOT)))
    def deny(*_):
        raise ValueError('unexpected heldout SDK request')
    client = CodexClient(CodexConfig(launch_args_override=(sys.executable, '-B', str(Path(__file__)), '--proxy', str(base)),
        cwd=str(base/'work')), approval_handler=deny)
    error = None
    try:
        client.start()
        client.initialize()
        thread = client.thread_start(dict(model=c['model'], modelProvider='bitz_openai_http', allowProviderModelFallback=False,
            cwd=str(base/'work'), sandbox='read-only', approvalPolicy='never', ephemeral=True,
            baseInstructions=p.capture.BASE, developerInstructions=p.capture.DEVELOPER, experimentalRawEvents=True))
        turn = client.turn_start(thread.thread.id, payload_raw.decode(),
            dict(outputSchema=p.capture.execution_schema(trace.strict_json(schema_raw)), effort='low'))
        while client.next_turn_notification(turn.turn.id).method != 'turn/completed':
            pass
    except Exception as exc:
        error = type(exc).__name__
    finally:
        client.close()
    io.exclusive(base/'isolated-result.json', io.encoded(dict(sdkErrorType=error)))


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--isolated', type=Path)
    mode.add_argument('--proxy', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.proxy:
            # proxyも開始前検分と入力/資源の検査を経る。SDKからの再起動で迂回しない。
            child_inputs(args.proxy)
            p.capture.sdk.proxy(args.proxy, reject_questions=True, capture_guard=p.capture.CaptureGuard(args.proxy),
                launch_contract_raw=io.read_regular(args.proxy/'launch-settings.json'))
        else:
            isolated(args.isolated)
        return 0
    except Exception:
        # 非公開のpayload/schema値・SDK例外本文をstderrへ展開しない。
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
