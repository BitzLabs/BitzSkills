"""固定入力と原SDK/native/host/finalの接続を合成原bytesで検証する。"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals/skills/routing'))
import production_canary_review as review
import test_production_canary_evidence as evidence_fixture
import test_production_canary_trace as trace_fixture


class CanaryReviewTests(unittest.TestCase):
    def setUp(self):
        self.capture = evidence_fixture.CanaryEvidenceTests(methodName='runTest')
        self.capture.setUp()
        self.addCleanup(self.capture.doCleanups)
        self.trace = trace_fixture.PrimaryCanaryTraceTests(methodName='runTest')
        self.trace.setUp()
        self.addCleanup(self.trace.doCleanups)
        primary = self.trace.fixture
        primary.sent[2]['params'].update(cwd=str(self.capture.base / 'work'),
            baseInstructions=review.evidence.capture.BASE, developerInstructions=review.evidence.capture.DEVELOPER)
        primary.sent[3]['params']['input'][0]['text'] = self.capture.originals['model-input.json'].decode()
        for frame in primary.received:
            if frame.get('params', {}).get('item', {}).get('type') == 'userMessage':
                frame['params']['item']['content'][0]['text'] = primary.sent[3]['params']['input'][0]['text']

    def save(self, profile='single-exec', *, sent=None, received=None, events=None, host=None):
        primary = self.trace.fixture
        sent = copy.deepcopy(primary.sent if sent is None else sent)
        received = copy.deepcopy(primary.received if received is None else received)
        events = primary.events(profile) if events is None else events
        if not any(f.get('method') in review.sdk.RAW_METHODS for f in received):
            raw = [dict(method='rawResponseItem/completed', params=dict(threadId='t', turnId='u',
                       item=dict(type='message', id='raw-public-input', role='user', content=[dict(type='input_text', text='public raw')])), emittedAtMs=1),
                   dict(method='rawResponse/completed', params=dict(threadId='t', turnId='u', responseId='response', usage=None, usageMetadata=None), emittedAtMs=1)]
            received[-1:-1] = raw
        host = primary.host if host is None else host
        originals = {'rpc-in.jsonl': sent, 'rpc-out.jsonl': received, 'host.jsonl': host,
                     'runtime-stderr.bin': events, 'trace-safe.jsonl': events}
        for name, values in originals.items():
            self.capture.rewrite(name, b''.join(review.evidence.ledger.encoded(value) + b'\n' for value in values))
        return review.evidence.load_verified_capture(self.capture.repository, self.capture.source, 1)

    def test_consumed_bytes_and_binding_cannot_be_mutated_after_loading(self):
        from dataclasses import replace
        context = self.save()
        with self.assertRaises(TypeError):
            context.originals['rpc-out.jsonl'] = b'changed'
        report = context.result
        report['artifactSha256']['rpc-out.jsonl'] = '0' * 64
        self.assertNotEqual(context.result, report)
        originals = dict(context.originals)
        originals['rpc-out.jsonl'] += review.evidence.ledger.encoded(dict(method='account/updated',
            params=dict(authMode='chatgpt', planType='plus'))) + b'\n'
        tampered = replace(context, original_items=tuple(originals.items()))
        with self.assertRaisesRegex(ValueError, 'consumed original artifact binding drift'):
            review.verify_native(tampered)

    def test_known_primary_profiles_use_fixed_input_host_and_native_final(self):
        for profile in ['single-exec', 'two-exec', 'exec-wait']:
            with self.subTest(profile=profile):
                result = review.verify_native(self.save(profile))
                self.assertEqual(result['native']['profile'], profile)
                self.assertEqual(result['native']['hostCalls'], 2)
                self.assertFalse(result['rawPayloadCorrelationVerified'])
                self.assertFalse(result['eligibleForMeasurement'])
                self.assertFalse(result['ledgerFinalized'])

    def test_catalog_api_is_bound_and_does_not_displace_model_order(self):
        events = self.trace.fixture.events('two-exec')
        catalog = {'level':'INFO', 'target':'codex_otel.trace_safe', 'fields':{
            'event.name':'codex.api_request', 'endpoint':'/models', 'success':True,
            'auth.header_attached':True, 'attempt':0, 'http.response.status_code':200}}
        result = review.verify_native(self.save('two-exec', events=[catalog, copy.deepcopy(catalog), *events]))
        self.assertEqual(result['native']['apiRequests'], 3)
        self.assertEqual(result['native']['modelCatalogApiRequests'], 2)
        for fault in ['third', 'endpoint', 'context', 'retry', 'success']:
            values = [copy.deepcopy(catalog), *events]
            if fault == 'third': values = [catalog, copy.deepcopy(catalog), copy.deepcopy(catalog), *events]
            elif fault == 'endpoint': values[0]['fields']['endpoint'] = '/unknown'
            elif fault == 'context': values[0]['fields']['conversation.id'] = 'other'
            elif fault == 'retry': values[0]['fields']['attempt'] = 1
            else: values[0]['fields']['success'] = False
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                review.verify_native(self.save('two-exec', events=values))

    def test_native_input_and_schema_drift_rejected_even_with_rehashed_artifacts(self):
        for fault in ['input', 'schema', 'provider']:
            sent = copy.deepcopy(self.trace.fixture.sent)
            if fault == 'input': sent[3]['params']['input'][0]['text'] += ' extra'
            elif fault == 'schema': sent[3]['params']['outputSchema'] = {}
            else: sent[2]['params']['modelProvider'] = 'openai'
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                review.verify_native(self.save(sent=sent))

    def test_raw_context_unknown_fields_and_missing_or_late_raw_stop(self):
        context = self.save()
        received = review.json_lines(context.originals['rpc-out.jsonl'])
        raw_index = next(i for i,f in enumerate(received) if f.get('method') == 'rawResponseItem/completed')
        for fault in ['missing', 'context', 'extra', 'late']:
            frames = copy.deepcopy(received)
            if fault == 'missing': frames = [f for f in frames if f.get('method') not in review.sdk.RAW_METHODS]
            elif fault == 'context': frames[raw_index]['params']['turnId'] = 'another'
            elif fault == 'extra': frames[raw_index]['params']['unknown'] = True
            else: frames.append(frames.pop(raw_index))
            # missingの場合、saveの自動raw追加を避け、原JSONLを直接差し替える。
            self.capture.rewrite('rpc-out.jsonl', b''.join(review.evidence.ledger.encoded(f)+b'\n' for f in frames))
            checked = review.evidence.load_verified_capture(self.capture.repository,self.capture.source,1)
            with self.subTest(fault=fault), self.assertRaises(ValueError): review.verify_native(checked)

    def test_account_metadata_is_typed_without_allowing_unknown_action(self):
        frames = copy.deepcopy(self.trace.fixture.received)
        frames.insert(1, dict(method='account/updated', params=dict(authMode='chatgpt', planType='plus')))
        self.assertFalse(review.verify_native(self.save(received=frames))['eligibleForMeasurement'])
        frames[1]['params']['authMode'] = 'unknown'
        with self.assertRaises(ValueError): review.verify_native(self.save(received=frames))

    def test_host_body_and_final_mismatch_and_unverified_context_are_rejected(self):
        host = copy.deepcopy(self.trace.fixture.host)
        host[-1]['result']['content'] += 'untrusted extra'
        with self.assertRaises(ValueError): review.verify_native(self.save(host=host))
        with self.assertRaises(ValueError): review.verify_native({})


if __name__ == '__main__':
    unittest.main()
