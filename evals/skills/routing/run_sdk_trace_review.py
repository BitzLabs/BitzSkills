"""承認済みSOLの独立静的検分を単一の有限CLI文脈で行う。一次評価は行わない。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess

import production_cli_probe as cli
import production_trace as trace
import production_review_ledger as review_ledger
import source_guard

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = 'evals/skills/routing/sdk-trace-review-v0.19.json'
YIELDED_CONTRACT = 'evals/skills/routing/sdk-trace-review-v0.20.json'
YIELDED_REMEDIATION_CONTRACT = 'evals/skills/routing/sdk-trace-review-v0.21.json'
SEQUENTIAL_CONTRACT = 'evals/skills/routing/sdk-trace-review-v0.22.json'
RAW_TWO_STAGE_CONTRACT = 'evals/skills/routing/sdk-trace-review-v0.23.json'
CANARY_DESIGN_CONTRACT = 'evals/skills/routing/sdk-trace-review-v0.24.json'
CANARY_DESIGN_REMEDIATION_CONTRACT = 'evals/skills/routing/sdk-trace-review-v0.25.json'
RAW_CONTRACTS = {'evals/skills/routing/sdk-raw-response-review-v0.1.json',
                 'evals/skills/routing/sdk-raw-response-review-v0.2.json',
                 'evals/skills/routing/sdk-raw-response-review-v0.3.json',
                 'evals/skills/routing/sdk-raw-response-review-v0.4.json',
                 'evals/skills/routing/sdk-raw-response-review-v0.5.json',
                 'evals/skills/routing/sdk-raw-response-review-v0.6.json',
                 'evals/skills/routing/sdk-raw-response-review-v0.7.json',
                 'evals/skills/routing/sdk-raw-response-review-v0.8.json'}
require = trace.require


def review_response(base: Path, stdout: bytes, source: str, schema: bytes, contract: dict):
    events = [trace.strict_json(line) for line in stdout.splitlines()]
    startup_warnings = []
    thread = started = finished = final = False
    ids = set()
    messages = []
    usage = None
    allowed_startup_warning = ('Code Mode is unavailable because code-mode host is disabled. '
                              'Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`.')
    for event in events:
        require(isinstance(event, dict) and not finished, 'review event outside lifecycle')
        kind = event.get('type')
        if kind == 'thread.started':
            require(set(event) == {'type', 'thread_id'} and not thread and not started and
                    isinstance(event['thread_id'], str) and bool(event['thread_id'].strip()), 'review thread start')
            thread = True
        elif kind == 'turn.started':
            require(set(event) == {'type'} and thread and not started, 'review turn start')
            started = True
        elif kind == 'item.completed':
            require(set(event) == {'type', 'item'} and thread and isinstance(event['item'], dict), 'review item fields')
            item = event['item']
            ident = item.get('id')
            require(isinstance(ident, str) and bool(ident.strip()) and ident not in ids, 'review item identity')
            ids.add(ident)
            if item.get('type') == 'error':
                require(set(item) == {'id', 'type', 'message'} and not started and
                        item['message'] == allowed_startup_warning and not startup_warnings, 'unknown or late review error')
                startup_warnings.append(hashlib.sha256(cli.encoded(event)).hexdigest())
            else:
                # CLI0.160.1 exec --jsonはmessage/reasoningをcompletedだけで通知する。
                # 未観測のitem.startedを合成せず、この既知の短縮profileだけを許可する。
                require(started and not final and set(item) == {'id', 'type', 'text'} and
                        item['type'] in {'agent_message', 'reasoning'} and isinstance(item['text'], str), 'unknown review item')
                if item['type'] == 'agent_message':
                    messages.append(item)
                    final = True
        elif kind == 'turn.completed':
            require(set(event) == {'type', 'usage'} and started and final, 'review terminal order')
            usage = event['usage']
            require(isinstance(usage, dict) and set(usage) == {'input_tokens', 'cached_input_tokens',
                    'cache_write_input_tokens', 'output_tokens', 'reasoning_output_tokens'} and
                    all(type(value) is int and value >= 0 for value in usage.values()), 'review usage fields')
            finished = True
        else:
            raise ValueError('unknown review event')
    require(thread and started and finished and len(messages) == 1, 'review terminal missing')
    response = trace.strict_json((base / 'response.json').read_bytes())
    require(response == trace.strict_json(messages[0]['text']), 'review final mismatch')
    trace.jsonschema.Draft202012Validator(trace.strict_json(schema)).validate(response)
    require(response['sourceCommit'] == source and response['scope'] == contract['scope'] and
            all(f['path'] in contract['payloadFiles'] for f in response['findings']) and
            response['verdict'] == ('findings' if response['findings'] else 'pass'), 'review response binding')
    return response, usage, startup_warnings


def run(source: str, contract_name: str = CONTRACT):
    require(contract_name in {CONTRACT, YIELDED_CONTRACT, YIELDED_REMEDIATION_CONTRACT, SEQUENTIAL_CONTRACT, RAW_TWO_STAGE_CONTRACT, CANARY_DESIGN_CONTRACT, CANARY_DESIGN_REMEDIATION_CONTRACT, *RAW_CONTRACTS}, 'unknown static review contract')
    require(source_guard.git(ROOT, 'status', '--porcelain') == b'', 'clean tree required')
    contract_raw = source_guard.git(ROOT, 'show', source + ':' + contract_name)
    contract = trace.strict_json(contract_raw)
    before = source_guard.verify(ROOT, source, contract['sourceFiles'])
    previous = contract.get('previousReview', contract.get('previousFailure'))
    if previous is not None:
        old_name = previous.get('outputRelativeRoot', '.venv/sdk-trace-independent-review-01')
        require(old_name in {'.venv/sdk-trace-independent-review-01', '.venv/sdk-trace-independent-review-02',
                             '.venv/sdk-trace-independent-review-03', '.venv/sdk-trace-independent-review-04',
                             '.venv/sdk-trace-independent-review-05', '.venv/sdk-trace-independent-review-06',
                             '.venv/sdk-trace-independent-review-07', '.venv/sdk-trace-independent-review-08',
                             '.venv/sdk-trace-independent-review-09', '.venv/sdk-trace-independent-review-10',
                             '.venv/sdk-trace-independent-review-11', '.venv/sdk-trace-independent-review-12',
                             '.venv/sdk-trace-independent-review-13', '.venv/sdk-trace-independent-review-14',
                             '.venv/sdk-trace-independent-review-15', '.venv/sdk-trace-independent-review-16',
                             '.venv/sdk-trace-independent-review-17', '.venv/sdk-trace-independent-review-18',
                             '.venv/sdk-trace-independent-review-19',
                             '.venv/sdk-trace-independent-review-20',
                             '.venv/sdk-trace-independent-review-21',
                             '.venv/sdk-trace-independent-review-22',
                             '.venv/sdk-trace-independent-review-23',
                             '.venv/sdk-trace-independent-review-24',
                             '.venv/sdk-raw-response-independent-review-01',
                             '.venv/sdk-raw-response-independent-review-02',
                             '.venv/sdk-raw-response-independent-review-03',
                             '.venv/sdk-raw-response-independent-review-04',
                             '.venv/sdk-raw-response-independent-review-05',
                             '.venv/sdk-raw-response-independent-review-06',
                             '.venv/sdk-raw-response-independent-review-07'},
                'unknown previous review')
        old = ROOT / old_name
        require(not any(p.is_symlink() for p in (old, *old.parents)), 'old review symlink')
        for name, key in (('receipt.json', 'receiptSha256'), ('response.json', 'responseSha256')):
            require(hashlib.sha256((old / name).read_bytes()).hexdigest() == previous[key], 'old review artifact drift')
        require(trace.strict_json((old / 'receipt.json').read_bytes())['sourceCommit'] == previous['sourceCommit'],
                'old review source mismatch')
    require(contract['maximumInvocations'] == 1 and contract['automaticRetries'] == 0 and
            contract['primaryModelTrajectories'] == 0, 'finite review required')
    base = ROOT / contract['outputRelativeRoot']
    require(not any(p.is_symlink() for p in (base, *base.parents)), 'review path symlink')
    require(not base.exists(), 'review output already exists')
    shared_reservation = review_ledger.reserve_static_review(ROOT, contract_name, source, contract_raw)
    base.mkdir(mode=0o700)
    for name in ('work', 'tmp', 'codex-home', 'state', 'logs'):
        (base / name).mkdir(mode=0o700)
    cli.exclusive(base / 'reservation.json', cli.encoded({'sourceCommit': source, 'maximumInvocations': 1,
                  'attemptReserved': 1, 'automaticRetry': False, 'scope': contract['scope']}))
    prompt = ('あなたは作業者と別の独立したコード検分者です。日本語で回答してください。'
              '次の確定bytesだけを静的検分してください。tool、追加モデル、委譲、ファイル読取り、試験実行は禁止です。'
              '診断が偽の通過となる具体的な入力、入力相関、開始完了順序、親セルと子ID、未知/禁止操作、'
              '証拠の欠落や改変、範囲を広げた認定の有無を評価してください。'
              '固定1exec/2読取りだけの診断でeligibleForMeasurement=falseが維持される限定を考慮し、'
              '一般のprovider互換性を未実装という理由だけで欠陥にしないでください。'
              '再現可能な指摘のみP1/P2/P3としてpath/line/条件/是正案を示してください。'
              'あなたが実行していない試験や原証拠の検分を成功と書かないでください。'
              '指定schemaのJSONだけを回答してください。\n'
              f'sourceCommit={source}\nscope={contract["scope"]}\n')
    if contract_name in {CANARY_DESIGN_CONTRACT, CANARY_DESIGN_REMEDIATION_CONTRACT}:
        prompt = ('あなたは作業者と別の独立した設計検分者です。日本語で回答してください。'
                  '次の確定した公開本文だけから実provider公開canaryと一次台帳の統合設計を静的検分してください。'
                  'tool、追加モデル、委譲、ファイル読取り、試験実行は禁止です。'
                  '設計の具体的矛盾、証拠と判定の束縛、有限枠と停止、未知入力の扱いを評価してください。'
                  '未実装であること自体や未確定と明示して起動を止める前提だけを欠陥にしないでください。'
                  '再現可能な指摘だけをP1/P2/P3としてpath/line/条件/是正案に示してください。'
                  'あなたが実行していない試験や原証拠の検分を成功と書かないでください。'
                  '指定schemaのJSONだけを回答してください。\n'
                  f'sourceCommit={source}\nscope={contract["scope"]}\n')
    if contract_name in RAW_CONTRACTS or contract_name in {CONTRACT, YIELDED_CONTRACT, YIELDED_REMEDIATION_CONTRACT, SEQUENTIAL_CONTRACT, RAW_TWO_STAGE_CONTRACT, CANARY_DESIGN_CONTRACT, CANARY_DESIGN_REMEDIATION_CONTRACT}:
        prompt += '\nこの検分の固定制約:\n' + '\n'.join(contract['constraints']) + '\n'
    for name in contract['payloadFiles']:
        raw = source_guard.git(ROOT, 'show', source + ':' + name)
        lines = raw.decode('utf-8').splitlines()
        prompt += f'\nFILE {name} SHA256 {hashlib.sha256(raw).hexdigest()}\n'
        prompt += '\n'.join(f'{i}: {line}' for i, line in enumerate(lines, 1)) + '\nEND FILE\n'
    prompt_raw = prompt.encode()
    cli.exclusive(base / 'prompt.txt', prompt_raw)
    schema = source_guard.git(ROOT, 'show', source + ':evals/skills/routing/sdk-trace-review.schema.json')
    cli.exclusive(base / 'schema.json', schema)
    # CLI自身の認証だけをROで戻す。内容を読取り/コピー/出力しない。modelにrepo/homeを渡さない。
    auth = Path('/home/hide/.codex/auth.json')
    require(auth.is_file() and not auth.is_symlink(), 'CLI runtime authentication unavailable')
    config = {'approval_policy': 'never', 'web_search': 'disabled', 'apps._default.enabled': False,
              'log_dir': str(base / 'logs'), 'sqlite_home': str(base / 'state'),
              'suppress_unstable_features_warning': True, 'agents.enabled': False,
              'tools.experimental_request_user_input.enabled': False, 'tools.update_plan.enabled': False,
              'model_reasoning_effort': 'medium'}
    for feature in ('shell_tool', 'unified_exec', 'shell_snapshot', 'apply_patch_freeform', 'apps',
                    'enable_mcp_apps', 'plugins', 'remote_plugin', 'code_mode', 'code_mode_host',
                    'multi_agent', 'multi_agent_v2', 'memories', 'hooks', 'browser_use', 'computer_use', 'goals'):
        config['features.' + feature] = False
    argv = [contract['codexPath'], 'exec', '--json', '--ephemeral', '--ignore-user-config', '--ignore-rules', '--skip-git-repo-check',
            '--sandbox', 'read-only', '--cd', str(base / 'work'), '--model', contract['model'],
            '--output-schema', str(base / 'schema.json'), '--output-last-message', str(base / 'response.json')]
    for key, value in config.items():
        argv += ['-c', key + '=' + json.dumps(value)]
    argv += ['-']
    node_root = Path(contract['codexPath']).parents[1]
    command = ['bwrap', '--die-with-parent', '--ro-bind', '/', '/', '--tmpfs', '/home', '--tmpfs', '/root',
               '--tmpfs', '/tmp', '--tmpfs', '/run', '--proc', '/proc', '--dev', '/dev',
               '--ro-bind', str(node_root), str(node_root), '--bind', str(base), str(base),
               '--bind', str(base / 'codex-home'), '/home/hide/.codex',
               '--ro-bind', str(auth), '/home/hide/.codex/auth.json', '--chdir', str(base / 'work'), '--', *argv]
    cli.exclusive(base / 'invocation.json', cli.encoded({'argv': command, 'sourceCommit': source,
                  'model': contract['model'], 'maximumInvocations': 1, 'promptSha256': hashlib.sha256(prompt_raw).hexdigest()}))
    invoke_guard = source_guard.verify(ROOT, source, contract['sourceFiles'])
    require(invoke_guard == before, 'pre-invocation source drift')
    env = {'PATH': str(node_root / 'bin') + ':/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TMPDIR': str(base / 'tmp')}
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=env, start_new_session=True)
    timed_out = False
    try:
        stdout, stderr = process.communicate(prompt_raw, timeout=contract['timeoutSeconds'])
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
    cli.exclusive(base / 'trace.jsonl', stdout)
    cli.exclusive(base / 'stderr.bin', stderr)
    after = source_guard.verify(ROOT, source, contract['sourceFiles'])
    value = {'status': 'review_stopped', 'sourceCommit': source, 'model': contract['model'],
             'scope': contract['scope'], 'exitCode': process.returncode, 'timedOut': timed_out,
             'independentReviewerSolInvocations': 1, 'primaryModelTrajectories': 0, 'automaticRetries': 0,
             'promptSha256': hashlib.sha256(prompt_raw).hexdigest(), 'stdoutSha256': hashlib.sha256(stdout).hexdigest(),
             'stderrSha256': hashlib.sha256(stderr).hexdigest(), 'sourceGuards': {'before': before, 'invoke': invoke_guard, 'after': after},
             'sharedReservation': shared_reservation,
             'certifiesRuntimeEvidence': False, 'certifiesPhaseCompletion': False}
    if process.returncode == 0 and not timed_out and before == after:
        try:
            response, usage, warnings = review_response(base, stdout, source, schema, contract)
            value.update(status='review_findings' if response['findings'] else 'static_review_passed',
                         findings=response['findings'], responseSha256=hashlib.sha256((base / 'response.json').read_bytes()).hexdigest(),
                         usage=usage, acceptedStartupWarningHashes=warnings)
        except Exception as error:
            value['terminalErrorType'] = type(error).__name__
    cli.exclusive(base / 'receipt.json', cli.encoded(value))
    print(json.dumps({k: v for k, v in value.items() if k not in {'sourceGuards', 'findings'}}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    raw = parser.add_mutually_exclusive_group()
    raw.add_argument('--raw-capture', action='store_true')
    raw.add_argument('--raw-capture-remediation', action='store_true')
    raw.add_argument('--raw-verifier-remediation', action='store_true')
    raw.add_argument('--yielded-capture-review', action='store_true')
    raw.add_argument('--yielded-capture-remediation', action='store_true')
    raw.add_argument('--yielded-wait-remediation', action='store_true')
    raw.add_argument('--yielded-parent-review', action='store_true')
    raw.add_argument('--yielded-parent-remediation', action='store_true')
    raw.add_argument('--sequential-capture-review', action='store_true')
    raw.add_argument('--sequential-capture-remediation', action='store_true')
    raw.add_argument('--sequential-parent-review', action='store_true')
    raw.add_argument('--raw-two-stage-review', action='store_true')
    raw.add_argument('--canary-design-review', action='store_true')
    raw.add_argument('--canary-design-remediation', action='store_true')
    args = parser.parse_args()
    contract_name = (CANARY_DESIGN_REMEDIATION_CONTRACT if args.canary_design_remediation else
                     CANARY_DESIGN_CONTRACT if args.canary_design_review else
                     RAW_TWO_STAGE_CONTRACT if args.raw_two_stage_review else
                     SEQUENTIAL_CONTRACT if args.sequential_parent_review else
                     'evals/skills/routing/sdk-raw-response-review-v0.8.json' if args.sequential_capture_remediation else
                     'evals/skills/routing/sdk-raw-response-review-v0.7.json' if args.sequential_capture_review else
                     YIELDED_REMEDIATION_CONTRACT if args.yielded_parent_remediation else
                     YIELDED_CONTRACT if args.yielded_parent_review else
                     'evals/skills/routing/sdk-raw-response-review-v0.6.json' if args.yielded_wait_remediation else
                     'evals/skills/routing/sdk-raw-response-review-v0.5.json' if args.yielded_capture_remediation else
                     'evals/skills/routing/sdk-raw-response-review-v0.4.json' if args.yielded_capture_review else
                     'evals/skills/routing/sdk-raw-response-review-v0.3.json' if args.raw_verifier_remediation else
                     'evals/skills/routing/sdk-raw-response-review-v0.2.json' if args.raw_capture_remediation else
                     'evals/skills/routing/sdk-raw-response-review-v0.1.json' if args.raw_capture else CONTRACT)
    run(args.source, contract_name)
