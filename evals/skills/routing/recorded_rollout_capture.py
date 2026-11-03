"""保存済み要求の原ファイル集合と入力の役割を照合する。"""
import production_trace as trace


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
