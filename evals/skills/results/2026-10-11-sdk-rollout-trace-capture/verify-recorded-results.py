"""原receiptのhashから全artifact・source・要求JSON値を再照合する。有料起動0。"""
import hashlib
import importlib.util
from pathlib import Path
import sys
import json

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_ledger as ledger
import production_rollout_trace as rollout
import production_trace as trace
import source_guard as guard


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require_artifact_membership(inventory, count):
    trace.require(isinstance(inventory, dict) and type(count) is int and 1 <= count <= 3,
                  'bounded capture inventory')
    required = {'contract.json', 'rpc-out.jsonl', *(f'request-{i}.json' for i in range(1, count + 1))}
    trace.require(required <= set(inventory), 'required original artifact not hashed')


def input_roles(request):
    items = request.get('input')
    trace.require(isinstance(items, list) and bool(items), 'original input missing')
    roles = []
    for item in items:
        trace.require(isinstance(item, dict), 'original input item')
        role = item['role'] if 'role' in item else item.get('type')
        trace.require(isinstance(role, str) and bool(role), 'original input role or type missing')
        allowed = {'developer', 'user'} if 'role' in item else {'custom_tool_call', 'custom_tool_call_output'}
        trace.require(role in allowed, 'unknown original input role or type')
        roles.append(role)
    return roles


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def run():
    public = trace.strict_json((Path(__file__).parent / 'summary.json').read_bytes())
    base = ROOT / public['outputRelativeRoot']
    ledger.safe_tree(base)
    receipt_raw = (base / 'receipt.json').read_bytes()
    trace.require(sha(receipt_raw) == public['receiptSha256'], 'original receipt drift')
    receipt = trace.strict_json(receipt_raw)
    require_artifact_membership(receipt['artifactSha256'], public['localHttpRequests'])
    source = public['sourceCommit']
    contract_raw = guard.git(ROOT, 'show', source + ':' + public['contractPath'])
    trace.require((base / 'contract.json').read_bytes() == contract_raw or
                  trace.json_equal(trace.strict_json((base / 'contract.json').read_bytes()),
                                   trace.strict_json(contract_raw)), 'original contract drift')
    contract = trace.strict_json(contract_raw)
    before, after = receipt['sourceGuards']['before'], receipt['sourceGuards']['after']
    expected_sources = {p: sha(guard.git(ROOT, 'show', source + ':' + p)) for p in contract['sourceFiles']}
    trace.require(trace.json_equal(before, after) and before['sourceCommit'] == before['observedHead'] == source and
                  before['sourceSha256'] == expected_sources and receipt['sourceCommit'] == source, 'original source guards')
    for inventory in [receipt['artifactSha256'], receipt['rolloutArtifactSha256']]:
        for relative, expected in inventory.items():
            trace.require(isinstance(relative, str) and not Path(relative).is_absolute() and
                          '..' not in Path(relative).parts, 'artifact path escape')
            path = base / relative
            ledger.safe_tree(path)
            trace.require(sha(path.read_bytes()) == expected, 'original artifact drift')
    bundles = list((base / 'rollout-traces').glob('*/trace.jsonl'))
    trace.require(len(bundles) == public['rolloutBundles'] == 1, 'one original bundle required')
    bundle = bundles[0].parent
    files = {str(p.relative_to(base)) for p in (base / 'rollout-traces').rglob('*') if p.is_file()}
    trace.require(files == set(receipt['rolloutArtifactSha256']) and len(files) == public['rolloutArtifacts'],
                  'complete rollout artifact inventory')
    events_raw = (bundle / 'trace.jsonl').read_bytes()
    events = [trace.strict_json(line) for line in events_raw.splitlines()]
    received = [trace.strict_json(line) for line in (base / 'rpc-out.jsonl').read_bytes().splitlines()]
    started = [f['params'] for f in received if f.get('method') == 'turn/started']
    trace.require(len(started) == 1, 'one original SDK turn')
    thread, turn = started[0]['threadId'], started[0]['turn']['id']
    wire = [(base / f'request-{i}.json').read_bytes() for i in range(1, public['localHttpRequests'] + 1)]
    projection = rollout.compare_requests((bundle / 'manifest.json').read_bytes(), events_raw,
        {str(p.relative_to(bundle)): p.read_bytes() for p in (bundle / 'payloads').glob('*.json')}, wire,
        thread_id=thread, turn_id=turn, model=contract['model'], provider_name='Isolated local simulator')
    first = trace.strict_json(wire[0])
    roles = input_roles(first)
    completions = sum(e['payload']['type'] == 'inference_completed' for e in events)
    trace.require(projection['requests'] == public['requestValuesMatched'] == public['inferenceRequests'] == 3 and
                  completions == public['inferenceCompletions'] == 3 and len(events) == public['rolloutEvents'] and
                  roles == public['initialInputRoles'], 'original inference counts')
    trace.require(receipt['namespaceExitCode'] == public['namespaceExitCode'] == 0 and
                  receipt['runtime']['exitCode'] == public['runtimeExitCode'] == 0 and
                  receipt['runtime']['forcedShutdown'] is False and receipt['sdkErrorType'] is None and
                  receipt['localErrors'] == [] and receipt['status'] == 'operation_diagnostic_captured' and
                  receipt['localHttpRequestCount'] == public['localHttpRequests'] == 3 and
                  receipt['hostEventCount'] == public['hostCalls'] == 2 and
                  receipt['rawResponseItemNotificationCount'] == receipt['sdkRawResponseItemNotificationCount'] ==
                  public['rawResponseItemNotifications'] == 8 and all(receipt['isolationChecks'].values()), 'capture outcome')
    trace.require(all(public[key] == 0 for key in ['paidModelCalls', 'primaryModelTrajectories', 'automaticRetries']) and
                  all(public[key] is False for key in ['independentReviewPerformed', 'certifiesWholeTrace',
                      'certifiesProviderWireBodies', 'eligibleForMeasurement', 'phaseComplete']), 'limited local scope')
    stages = public.get('staticReviewStages', [])
    if stages:
        review = module('rollout_raw_review', 'evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-recorded-results.py')
        preparation = module('rollout_preparation', 'evals/skills/results/2026-10-10-production-canary-design/verify-recorded-results.py')
        for stage in stages:
            preparation.check_stage(stage, review)
    trace.require(public.get('staticSolInvocations', 0) == len(stages), 'finite static review count')
    print(json.dumps(dict(status='recorded_rollout_capture_matches_original_bytes', requests=projection['requests'],
        rolloutEvents=len(events), rolloutArtifacts=len(files), initialInputRoles=roles,
        staticSolInvocations=len(stages), paidModelCalls=0, eligibleForMeasurement=False), ensure_ascii=False))


if __name__ == '__main__':
    run()
