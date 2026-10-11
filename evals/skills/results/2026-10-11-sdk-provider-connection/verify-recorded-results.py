"""停止前の原結果と静的検分原証拠を照合する。認証ファイルを読まない。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_ledger as ledger
import production_connection_probe as connection
import production_connection_evidence as evidence
import production_trace as trace
import source_guard as guard


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def run():
    public = trace.strict_json((Path(__file__).parent / 'summary.json').read_bytes())
    base = ROOT / public['outputRelativeRoot']
    ledger.safe_tree(base)
    raw = (base / 'receipt.json').read_bytes()
    trace.require(sha(raw) == public['receiptSha256'], 'original stopped receipt drift')
    receipt = trace.strict_json(raw)
    protected = 'codex-home/auth.json'
    required = {'contract.json', 'config.json', 'rpc-in.jsonl', 'rpc-out.jsonl', 'runtime-result.json',
                'runtime-stderr.bin', 'trace-safe.jsonl', 'isolated-result.json', 'reservation.json', 'invocation.json'}
    trace.require(required <= set(receipt['artifactSha256']), 'required original artifact membership')
    for relative, expected in receipt['artifactSha256'].items():
        trace.require(not Path(relative).is_absolute() and '..' not in Path(relative).parts, 'artifact escape')
        path = base / relative
        ledger.safe_tree(path)
        if relative == protected:
            # 原receiptの集計対象は広すぎた。空mount先はstatだけで確認し、内容を読まない。
            trace.require(path.stat().st_size == 0 and expected == sha(b''), 'empty host mount placeholder')
            continue
        trace.require(Path(relative).name == relative, 'unexpected nested original artifact')
        trace.require(sha(path.read_bytes()) == expected, 'original stopped artifact drift')
    source = public['sourceCommit']
    contract_raw = guard.git(ROOT, 'show', source + ':' + public['contractPath'])
    contract = trace.strict_json(contract_raw)
    trace.require((base / 'contract.json').read_bytes() == contract_raw, 'original contract drift')
    expected_sources = {p: sha(guard.git(ROOT, 'show', source + ':' + p)) for p in contract['sourceFiles']}
    guards = receipt['sourceGuards']
    trace.require(trace.json_equal(guards['before'], guards['invoke']) and trace.json_equal(guards['before'], guards['after']) and
                  guards['before']['sourceCommit'] == guards['before']['observedHead'] == receipt['sourceCommit'] == source and
                  guards['before']['sourceSha256'] == expected_sources, 'original source guards')
    reservation = trace.strict_json((base / 'reservation.json').read_bytes())
    shared = ledger.common_ledger_path(ROOT).parent / 'production-provider-diagnostic-ledger' / 'production-connection-probe-v0.1.json'
    ledger.safe_tree(shared)
    trace.require(reservation['path'] == str(shared) and sha(shared.read_bytes()) == reservation['sha256'] and
                  trace.json_equal(trace.strict_json(shared.read_bytes()), {k: v for k, v in reservation.items() if k not in {'path', 'sha256'}}) and
                  reservation['sourceCommit'] == source and reservation['contractSha256'] == sha(contract_raw) and
                  reservation['consumedReservations'] == reservation['maximumInvocations'] == 1 and
                  reservation['automaticRetry'] is False, 'consumed original common reservation')
    sent = [trace.strict_json(line) for line in (base / 'rpc-in.jsonl').read_bytes().splitlines()]
    trace.require([f.get('method') for f in sent] == ['initialize'] and
                  (base / 'rpc-out.jsonl').read_bytes() == (base / 'trace-safe.jsonl').read_bytes() == b'' and
                  not list((base / 'rollout-traces').rglob('manifest.json')), 'stopped before model input')
    error = (base / 'runtime-stderr.bin').read_bytes()
    trace.require(error == b'Error: model_providers contains reserved built-in provider IDs: `openai`. Built-in providers cannot be overridden. Rename your custom provider (for example, `openai-custom`).\nin `model_providers`\n\n',
                  'original provider configuration failure')
    trace.require(trace.json_equal(trace.strict_json((base / 'runtime-result.json').read_bytes()),
                      {'exitCode': 1, 'forcedShutdown': False}) and
                  receipt['status'] == 'connection_diagnostic_stopped' and receipt['namespaceExitCode'] == 0 and
                  receipt['timedOut'] is False and receipt['sdkErrorType'] == 'TransportClosedError', 'original stopped outcome')
    review = module('connection_review', 'evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-recorded-results.py')
    preparation = module('connection_preparation', 'evals/skills/results/2026-10-10-production-canary-design/verify-recorded-results.py')
    for stage in public['staticReviewStages']:
        preparation.check_stage(stage, review)
    for row in public.get('startupDiagnostics', []):
        startup = ROOT / row['outputRelativeRoot']
        ledger.safe_tree(startup)
        trace.require(sha((startup / 'receipt.json').read_bytes()) == row['receiptSha256'], 'startup receipt drift')
        original = trace.strict_json((startup / 'receipt.json').read_bytes())
        startup_contract_raw = guard.git(ROOT, 'show', row['sourceCommit'] + ':' + row['contractPath'])
        startup_contract = trace.strict_json(startup_contract_raw)
        trace.require((startup / 'contract.json').read_bytes() == startup_contract_raw and
                      original['sourceCommit'] == row['sourceCommit'] and original['status'] == row['status'] and
                      original['namespaceExitCode'] == row['namespaceExitCode'] and original['paidModelCalls'] == 0,
                      'startup original scope and outcome')
        expected_sources = {p: sha(guard.git(ROOT, 'show', row['sourceCommit'] + ':' + p)) for p in startup_contract['sourceFiles']}
        before, after = original['sourceGuards']['before'], original['sourceGuards']['after']
        trace.require(trace.json_equal(before, after) and before['sourceCommit'] == before['observedHead'] == row['sourceCommit'] and
                      before['sourceSha256'] == expected_sources, 'startup original source guards')
        paths = connection.original_artifact_paths(startup)
        trace.require({str(p.relative_to(startup)) for p in paths} == set(original['artifactSha256']), 'startup complete original inventory')
        for path in paths:
            ledger.safe_tree(path)
            trace.require(sha(path.read_bytes()) == original['artifactSha256'][str(path.relative_to(startup))], 'startup original hash')
        if row['status'] == 'unpaid_sdk_initialization_captured':
            trace.require({'rpc-in.jsonl', 'rpc-out.jsonl', 'runtime-result.json', 'trace-safe.jsonl', 'config.json'} <=
                          set(original['artifactSha256']), 'required initialization originals')
            caller = [trace.strict_json(line) for line in (startup / 'rpc-in.jsonl').read_bytes().splitlines()]
            incoming = [trace.strict_json(line) for line in (startup / 'rpc-out.jsonl').read_bytes().splitlines()]
            replies = [f for f in incoming if 'id' in f]
            trace.require([f.get('method') for f in caller] == ['initialize', 'initialized'] and len(replies) == 1 and
                          set(replies[0]) == {'id', 'result'} and replies[0]['id'] == caller[0]['id'] and
                          isinstance(replies[0]['result'], dict) and original['sdkErrorType'] is None and
                          trace.json_equal(trace.strict_json((startup / 'runtime-result.json').read_bytes()),
                                           {'exitCode': 0, 'forcedShutdown': False}) and
                          (startup / 'trace-safe.jsonl').read_bytes() == b'' and
                          trace.json_equal(trace.strict_json((startup / 'config.json').read_bytes()), connection.http_config_for(startup)) and
                          not (startup / 'codex-home/auth.json').exists(), 'unpaid isolated initialization')
        else:
            trace.require((startup / 'namespace.stderr').read_bytes() ==
                          b'bwrap: loopback: Failed to create NETLINK_ROUTE socket: Operation not permitted\n' and
                          not (startup / 'rpc-in.jsonl').exists(), 'original pre-SDK namespace failure')
    captures = []
    for row in public.get('connectionCaptures', []):
        captured = evidence.inspect(ROOT / row['outputRelativeRoot'], source=row['sourceCommit'],
                                    contract_path=row['contractPath'], receipt_sha=row['receiptSha256'])
        for key, value in row.items():
            if key not in {'sourceCommit', 'contractPath', 'outputRelativeRoot', 'receiptSha256'}:
                trace.require(trace.json_equal(captured[key], value), 'public connection value differs from originals')
        captures.append(captured)
    trace.require(len(public['staticReviewStages']) == public['staticSolInvocations'] == 5 and
                  public['observedModelApiRequests'] == public['primaryModelTrajectories'] == public['automaticRetries'] == 0 and
                  public['consumedConnectionReservations'] == public['connectionStartupInvocations'] == 1 and
                  all(public[k] is False for k in ['certifiesNativeProvider', 'eligibleForMeasurement', 'phaseComplete']), 'limited scope')
    print(json.dumps(dict(status='recorded_connection_history_matches_original_bytes', staticSolInvocations=5,
                         unpaidStartupDiagnostics=len(public.get('startupDiagnostics', [])),
                         consumedConnectionReservations=1 + len(captures),
                         stoppedDiagnosticModelApiRequests=0,
                         capturedModelApiRequests=sum(c['modelApiRequests'] for c in captures),
                         capturedTotalServiceApiRequests=sum(c['totalServiceApiRequests'] for c in captures),
                         originalOneTotalApiCriterionMet=False, eligibleForMeasurement=False)))


if __name__ == '__main__':
    run()
