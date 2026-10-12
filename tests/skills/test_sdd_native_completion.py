"""単一turnと既知CLI0.160.1 envelopeの実失敗/欠測を拒否。モデル0。"""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('sdd_native_completion_eval',ROOT/'evals/skills/sdd/evaluate.py')
evaluation=importlib.util.module_from_spec(spec);spec.loader.exec_module(evaluation)


class SddNativeCompletionTests(unittest.TestCase):
    def setUp(self):
        item=dict(id='item_0',type='mcp_tool_call',server='sdd_eval',tool='read_file',arguments={'path':'src/input.py'},result=None,error=None,status='in_progress')
        final=dict(item,status='completed',result={'content':[{'type':'text','text':'{}'}],'structured_content':None})
        self.events=[dict(type='thread.started',thread_id='synthetic-unit-only'),dict(type='turn.started'),dict(type='item.started',item=item),
            dict(type='item.completed',item=final),dict(type='item.completed',item=dict(id='item_1',type='agent_message',text='{}')),
            dict(type='turn.completed',usage=dict(input_tokens=100,cached_input_tokens=20,cache_write_input_tokens=0,output_tokens=10,reasoning_output_tokens=2))]

    def test_known_complete_original_envelope_preserves_usage(self):
        self.assertEqual(evaluation.native_completion(self.events),self.events[-1]['usage'])
        self.assertEqual(self.events[2]['item']['status'],'in_progress')

    def test_failed_unknown_and_post_terminal_events_rejected(self):
        for event in [dict(type='turn.failed',error={'message':'synthetic failure'}),dict(type='error',message='failure'),
                dict(type='unknown.future.event'),dict(type='item.completed',item={'id':'other','type':'unknown_action'})]:
            for position in [-1,len(self.events)]:
                events=copy.deepcopy(self.events);events.insert(position,event)
                with self.subTest(event=event,position=position),self.assertRaises(ValueError):evaluation.native_completion(events)

    def test_missing_duplicate_lifecycle_and_unfinished_or_reused_items_rejected(self):
        variants=[self.events[1:],self.events[:-1],self.events[:3]+self.events[4:],self.events[:2]+self.events[3:],
                  self.events[:2]+[self.events[1]]+self.events[2:],self.events[:-1]+[self.events[4],self.events[-1]]]
        for events in variants:
            with self.subTest(events=events),self.assertRaises(ValueError):evaluation.native_completion(events)

    def test_mcp_failure_changed_arguments_unknown_tool_and_fields_rejected(self):
        for key,value in [('error',{'message':'failed'}),('status','failed'),('server','other'),('tool','external_send'),('arguments',{'path':'outside.py'}),('unknown',True)]:
            events=copy.deepcopy(self.events);events[3]['item'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):evaluation.native_completion(events)

    def test_duplicate_and_nonfinite_json_raw_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory(dir=ROOT/'.venv/test-temp') as tmp:
            path=Path(tmp)/'trace.jsonl'
            for raw in ['{"type":"turn.started","type":"turn.completed"}', '{"type":"turn.completed","usage":NaN}', '{"overflow":1e999}', '{"nested":[{"overflow":-1e999}]}']:
                path.write_text(raw)
                with self.subTest(raw=raw),self.assertRaises(ValueError):evaluation.read_events(path)

    def test_nested_core_stdout_duplicate_status_and_overflow_rejected(self):
        for raw in ['{"status":"failed","status":"passed"}', '{"status":"passed","extra":1e999}', '{"status":"passed","nested":{"extra":NaN}}']:
            call={"tool":"run_bitz","accepted":True,"result":{"stdout":raw}}
            with self.subTest(raw=raw):
                self.assertIsNone(evaluation.core_results([call])[0][1])
        raw='{"schemaVersion":"1.0","operation":"check","status":"passed"}'
        call={"tool":"run_bitz","accepted":True,"result":{"stdout":raw}}
        self.assertEqual(evaluation.core_results([call])[0][1]["status"],"passed")

    def test_finite_metadata_numbers_remain_observable(self):
        value=evaluation.parse_json('{"_meta":{"fraction":1.25,"small":1e-9},"count":1000000000000000000000}')
        self.assertEqual(value["_meta"],{"fraction":1.25,"small":1e-9})
        self.assertEqual(value["count"],1000000000000000000000)

    def test_unknown_missing_bool_and_out_of_bounds_usage_rejected(self):
        for key,value in [('input_tokens',True),('input_tokens',0),('output_tokens',0),('output_tokens',None),('input_tokens',-1),('cached_input_tokens',101),('reasoning_output_tokens',11),('unknown',0)]:
            events=copy.deepcopy(self.events);events[-1]['usage'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):evaluation.native_completion(events)
        events=copy.deepcopy(self.events);del events[-1]['usage']['cache_write_input_tokens']
        with self.assertRaises(ValueError):evaluation.native_completion(events)
