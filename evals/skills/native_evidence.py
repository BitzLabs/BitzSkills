"""固定CLI0.160.1の原JSONと単一turnを検査する。製品Coreの判定器ではない。"""
import json
import math
from pathlib import Path
import sys

ROUTING = Path(__file__).resolve().parent / "routing"
_original_search_path = list(sys.path)
try:
    sys.path.insert(0, str(ROUTING))
    from production_ledger import read_regular
finally:
    sys.path[:] = _original_search_path


def read_original(path):
    return read_regular(Path(path).absolute())


def parse_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError("non-finite JSON value: " + value)
    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("non-finite JSON number: " + value)
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=finite_float)
    except RecursionError as error:
        raise ValueError("JSON nesting exceeds decoder capacity") from error



def native_completion(events, *, server, tools):
    """固定CLI0.160.1の単一turn・許可item・原usageだけを認める。"""
    def require(condition, message):
        if not condition:
            raise ValueError("native trace: " + message)
    require(isinstance(events, list) and len(events) >= 4, "incomplete lifecycle")
    require(isinstance(events[0], dict) and set(events[0]) == {"type", "thread_id"}
            and events[0]["type"] == "thread.started" and isinstance(events[0]["thread_id"], str)
            and bool(events[0]["thread_id"].strip()), "thread start")
    require(events[1] == {"type": "turn.started"}, "single turn start")
    terminal = events[-1]
    require(isinstance(terminal, dict) and set(terminal) == {"type", "usage"}
            and terminal["type"] == "turn.completed", "normal terminal")
    usage = terminal["usage"]
    require(isinstance(usage, dict) and set(usage) == {"input_tokens", "cached_input_tokens",
            "cache_write_input_tokens", "output_tokens", "reasoning_output_tokens"}
            and all(type(v) is int and v >= 0 for v in usage.values()), "original usage fields")
    require(usage["input_tokens"] > 0 and usage["output_tokens"] > 0
            and usage["cached_input_tokens"] <= usage["input_tokens"]
            and usage["reasoning_output_tokens"] <= usage["output_tokens"], "usage bounds")
    pending, completed = {}, set()
    for event in events[2:-1]:
        require(isinstance(event, dict) and set(event) == {"type", "item"}
                and event["type"] in {"item.started", "item.updated", "item.completed"}, "unknown or failed event")
        item = event["item"]
        require(isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip(), "item identity")
        identity, kind = item["id"], item.get("type")
        require(identity not in completed, "duplicate or post-completion item")
        if kind in {"agent_message", "reasoning"}:
            require(set(item) == {"id", "type", "text"} and isinstance(item["text"], str)
                    and event["type"] == "item.completed" and identity not in pending, "message item")
        elif kind == "mcp_tool_call":
            require(set(item) == {"id", "type", "server", "tool", "arguments", "result", "error", "status"}
                    and item["server"] == server and item["tool"] in tools
                    and isinstance(item["arguments"], dict) and item["error"] is None, "MCP item fields or failed tool")
            binding = json.dumps({k:item[k] for k in ("server", "tool", "arguments")}, sort_keys=True)
            if event["type"] == "item.started":
                require(identity not in pending and item["status"] == "in_progress"
                        and item["result"] is None, "MCP start")
                pending[identity] = binding
            elif event["type"] == "item.updated":
                require(pending.get(identity) == binding and item["status"] == "in_progress"
                        and item["result"] is None, "MCP update")
            else:
                require(pending.pop(identity, None) == binding and item["status"] == "completed", "MCP completion lifecycle")
                result = item["result"]
                require(isinstance(result, dict) and {"content", "structured_content"} <= set(result)
                        <= {"content", "structured_content", "_meta"} and isinstance(result["content"], list)
                        and len(result["content"]) == 1 and result["structured_content"] is None, "MCP result")
                content = result["content"][0]
                require(isinstance(content, dict) and set(content) == {"type", "text"}
                        and content["type"] == "text" and isinstance(content["text"], str), "MCP content")
        else:
            raise ValueError("native trace: forbidden or unknown item")
        if event["type"] == "item.completed":
            completed.add(identity)
    require(not pending, "unfinished MCP item")
    final = events[-2]
    require(final.get("type") == "item.completed" and final.get("item", {}).get("type") == "agent_message", "final agent response")
    return usage

