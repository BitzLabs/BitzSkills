"""SDK 0.160.1の単一・無操作診断の原RPC相関。未知profileを補完しない。"""
from production_trace import require

NOTIFICATIONS = {'remoteControl/status/changed', 'thread/started', 'thread/status/changed', 'warning',
                 'account/rateLimits/updated', 'turn/started', 'turn/completed', 'item/started', 'item/completed',
                 'item/agentMessage/delta', 'item/reasoning/summaryTextDelta', 'item/reasoning/summaryPartAdded',
                 'item/reasoning/textDelta', 'rawResponseItem/completed', 'rawResponse/completed', 'error'}


def ident(value):
    require(type(value) in {str, int} and (type(value) is int or bool(value.strip())), 'RPC id type')
    return type(value), value


def correlate(sent, received, *, allow_turn_error=False):
    require(isinstance(sent, list) and all(isinstance(f, dict) for f in sent) and
            [f.get('method') for f in sent] == ['initialize', 'initialized', 'thread/start', 'turn/start'],
            'closed caller method sequence')
    require(set(sent[1]) == {'method'} or set(sent[1]) == {'method', 'params'}, 'initialized notification envelope')
    require(sent[1].get('params') in (None, {}), 'initialized notification params')
    requests = [sent[i] for i in [0, 2, 3]]
    require(all(set(f) == {'id', 'method', 'params'} and isinstance(f['params'], dict) for f in requests),
            'caller request envelope')
    ids = [ident(f['id']) for f in requests]
    require(len(set(ids)) == 3, 'unique caller request ids')
    require(isinstance(received, list) and all(isinstance(f, dict) for f in received), 'received RPC list')
    reply_frames = [f for f in received if 'id' in f]
    require(len(reply_frames) == 3 and
            all(set(f) == {'id', 'result'} and isinstance(f['result'], dict) for f in reply_frames),
            'exact response envelopes; errors and server requests stop')
    reply_ids = [ident(f['id']) for f in reply_frames]
    require(len(set(reply_ids)) == 3 and set(reply_ids) == set(ids), 'unique complete caller reply ids')
    replies = {ident(f['id']): f['result'] for f in reply_frames}
    thread = replies[ids[1]]['thread']['id']
    turn = replies[ids[2]]['turn']['id']
    require(isinstance(thread, str) and bool(thread) and isinstance(turn, str) and bool(turn) and
            sent[3]['params']['threadId'] == thread, 'caller/native thread and turn')
    reply_positions = [next(i for i, f in enumerate(received) if 'id' in f and ident(f['id']) == value) for value in ids]
    require(reply_positions == sorted(reply_positions), 'serial caller reply order')
    starts = [i for i, f in enumerate(received) if f.get('method') == 'turn/started']
    ends = [i for i, f in enumerate(received) if f.get('method') == 'turn/completed']
    require(len(starts) == len(ends) == 1 and reply_positions[1] < starts[0] < ends[0] and
            reply_positions[2] < ends[0], 'one native turn lifecycle')
    thread_starts = [i for i, f in enumerate(received) if f.get('method') == 'thread/started']
    require(len(thread_starts) == 1 and reply_positions[0] < thread_starts[0] < starts[0],
            'native thread after initialization and before turn')
    active, completed = {}, set()
    summaries, deltas = {}, {}
    for i, frame in enumerate(received):
        if 'id' in frame:
            continue
        require(set(frame) in ({'method', 'params'}, {'method', 'params', 'emittedAtMs'}) and
                isinstance(frame.get('params'), dict) and frame.get('method') in NOTIFICATIONS,
                'known notification envelope')
        if 'emittedAtMs' in frame:
            require(type(frame['emittedAtMs']) is int and frame['emittedAtMs'] >= 0, 'notification timestamp')
        method, params = frame['method'], frame['params']
        require(('threadId' not in params or params['threadId'] == thread) and
                ('turnId' not in params or params['turnId'] == turn), 'explicit notification context')
        if method == 'thread/started':
            require(params['thread']['id'] == thread, 'native thread start context')
        elif method in {'turn/started', 'turn/completed'}:
            require(params['threadId'] == thread and params['turn']['id'] == turn, 'native turn context')
        elif method.startswith(('item/', 'rawResponse')) or method == 'error':
            require(params['threadId'] == thread and params['turnId'] == turn and starts[0] < i < ends[0],
                    'turn notification context and order')
        if method == 'error':
            require(allow_turn_error and params.get('willRetry') is False, 'unexpected or retriable turn error')
        if method in {'item/agentMessage/delta', 'item/reasoning/summaryTextDelta',
                      'item/reasoning/summaryPartAdded', 'item/reasoning/textDelta'}:
            kind = 'agentMessage' if method == 'item/agentMessage/delta' else 'reasoning'
            require(isinstance(params.get('itemId'), str) and active.get(params['itemId']) == kind,
                    'delta belongs to active matching item')
            key = params['itemId']
            if method != 'item/reasoning/summaryPartAdded':
                require(isinstance(params.get('delta'), str), 'text delta payload')
            if method in {'item/reasoning/summaryPartAdded', 'item/reasoning/summaryTextDelta'}:
                index = params.get('summaryIndex')
                require(type(index) is int and index >= 0, 'summary delta index')
                if method == 'item/reasoning/summaryPartAdded':
                    require(index == len(summaries[key]), 'ordered unique summary part')
                    summaries[key].add(index)
                else:
                    require(index in summaries[key], 'started summary part')
            if method == 'item/reasoning/textDelta':
                require(type(params.get('contentIndex')) is int and params['contentIndex'] >= 0, 'reasoning content index')
            if method == 'item/agentMessage/delta':
                deltas.setdefault(key, []).append(params['delta'])
        if method in {'item/started', 'item/completed'}:
            item = params['item']
            require(isinstance(item, dict) and item.get('type') in {'userMessage', 'reasoning', 'agentMessage'} and
                    isinstance(item.get('id'), str) and bool(item['id']), 'no unknown or action item')
            key = item['id']
            if method == 'item/started':
                require(key not in active and key not in completed, 'unique item start')
                active[key] = item['type']
                summaries[key] = set()
            else:
                require(active.get(key) == item['type'] and key not in completed, 'matching item completion')
                if key in deltas:
                    require(''.join(deltas[key]) == item.get('text'), 'streamed and completed agent text')
                del active[key]
                completed.add(key)
    require(not active, 'unresolved native item')
    return dict(threadId=thread, turnId=turn)
