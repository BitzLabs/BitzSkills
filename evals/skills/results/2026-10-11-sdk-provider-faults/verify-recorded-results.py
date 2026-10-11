"""無課金故障診断の原ファイル・APIログ・SDK失敗終端を再照合する。通信しない。"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_fault_probe as probe
import production_ledger as ledger
import production_trace as trace
import source_guard as guard


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run():
    public = trace.strict_json((Path(__file__).parent / 'summary.json').read_bytes())
    source = public['sourceCommit']
    contract_raw = guard.git(ROOT, 'show', source + ':' + public['contractPath'])
    contract = trace.strict_json(contract_raw)
    trace.require([c['case'] for c in public['cases']] == list(probe.CASES), 'four fixed cases required')
    expected_sources = {p: sha(guard.git(ROOT, 'show', source + ':' + p)) for p in contract['sourceFiles']}
    totals = {'requests': 0, 'apiRequests': 0}
    for row in public['cases']:
        base = ROOT / public['outputRelativeRoot'] / row['case']
        ledger.safe_tree(base)
        raw = (base / 'receipt.json').read_bytes()
        trace.require(sha(raw) == row['receiptSha256'], 'original receipt drift')
        receipt = trace.strict_json(raw)
        fault, retries, expected = probe.policy(contract, row['case'])
        inventory = receipt['artifactSha256']
        required = {'contract.json', 'config.json', 'rpc-in.jsonl', 'rpc-out.jsonl', 'runtime-result.json',
                    'runtime-stderr.bin', 'trace-safe.jsonl', 'isolated-result.json', 'version.stdout', 'case.txt',
                    *(f'{kind}-{i}.{suffix}' for i in range(1, expected + 1)
                      for kind, suffix in [('request', 'json'), ('response', 'bin')])}
        trace.require(required <= set(inventory), 'required original not hashed')
        files = {p.name for p in base.iterdir() if p.is_file() and p.name != 'receipt.json'}
        trace.require(files == set(inventory), 'complete top-level inventory required')
        for relative, digest in inventory.items():
            trace.require(Path(relative).name == relative and relative not in {'.', '..'}, 'artifact escape')
            path = base / relative
            ledger.safe_tree(path)
            trace.require(sha(path.read_bytes()) == digest, 'original artifact drift')
        trace.require((base / 'contract.json').read_bytes() == contract_raw and
                      (base / 'case.txt').read_text() == row['case'] and
                      (base / 'version.stdout').read_text().strip() == contract['codexVersion'], 'fixed original configuration')
        before, after = receipt['sourceGuards']['before'], receipt['sourceGuards']['after']
        trace.require(trace.json_equal(before, after) and
                      before['sourceCommit'] == before['observedHead'] == receipt['sourceCommit'] == source and
                      before['sourceSha256'] == expected_sources, 'original fixed source guards')
        config = trace.strict_json((base / 'config.json').read_bytes())
        trace.require(type(config['model_providers.bitz_local_probe.request_max_retries']) is int and
                      config['model_providers.bitz_local_probe.request_max_retries'] == retries and
                      type(config['model_providers.bitz_local_probe.stream_max_retries']) is int and
                      config['model_providers.bitz_local_probe.stream_max_retries'] == 0 and
                      all(config[key] is False for key in ['model_providers.bitz_local_probe.supports_websockets',
                          'features.unbounded_connection_retries', 'features.system_proxy_fallback',
                          'features.respect_system_proxy']) and
                      not any(key.startswith('mcp_servers.') for key in config), 'effective retry configuration')
        sent = [trace.strict_json(line) for line in (base / 'rpc-in.jsonl').read_bytes().splitlines()]
        received = [trace.strict_json(line) for line in (base / 'rpc-out.jsonl').read_bytes().splitlines()]
        starts = [f['params'] for f in received if f.get('method') == 'turn/started']
        trace.require(len(starts) == 1 and sum(f.get('method') == 'turn/start' for f in sent) == 1,
                      'one original logical turn')
        runtime = trace.strict_json((base / 'runtime-result.json').read_bytes())
        originals = list(base.glob('request-*.json'))
        result = probe.outcome(received, starts[0]['threadId'], starts[0]['turn']['id'],
                               len(originals), expected, runtime, None)
        trace.require(result['status'] == 'bounded_fault_diagnostic_captured', 'original failure terminal')
        raw_trace = (base / 'runtime-stderr.bin').read_bytes()
        selected = []
        for line in raw_trace.splitlines(keepends=True):
            try:
                event = trace.strict_json(line)
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(event, dict) and event.get('target') in {'codex_otel.trace_safe', 'codex_code_mode::timing'}:
                selected.append(line)
        trace.require(b''.join(selected) == (base / 'trace-safe.jsonl').read_bytes(), 'complete raw log projection')
        api = [e['fields'] for line in selected if
               (e := trace.strict_json(line)).get('fields', {}).get('event.name') == 'codex.api_request']
        statuses = [e.get('http.response.status_code') for e in api]
        trace.require(len(api) == row['apiRequests'] and statuses == row['httpStatuses'] and
                      all(type(e.get('attempt')) is int and e['attempt'] == i and
                          e.get('auth.header_attached') is False for i, e in enumerate(api)), 'original API attempts')
        for i in range(1, expected + 1):
            request = trace.strict_json((base / f'request-{i}.json').read_bytes())
            trace.require(request['model'] == contract['model'] and
                          'PUBLIC_LOCAL_TRANSPORT_FAULT' in json.dumps(request['input']), 'public local input')
        trace.require(len(originals) == row['requests'] == expected and
                      receipt['status'] == result['status'] and receipt['sdkErrorType'] is None and
                      receipt['namespaceExitCode'] == 0 and receipt['overflows'] == [] and
                      receipt['apiRequests'] == len(api) and receipt['httpStatuses'] == statuses,
                      'recorded original outcome')
        for key in totals:
            totals[key] += row[key]
    trace.require(public['paidModelCalls'] == public['primaryModelTrajectories'] == 0 and
                  all(public[key] is False for key in ['certifiesAuthorizationRecovery', 'certifiesNativeProvider',
                      'eligibleForMeasurement', 'phaseComplete']), 'limited diagnostic scope')
    print(json.dumps(dict(status='recorded_provider_faults_match_original_bytes', cases=4, **totals,
                          paidModelCalls=0, eligibleForMeasurement=False)))


if __name__ == '__main__':
    run()
