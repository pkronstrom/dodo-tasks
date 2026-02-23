# MCP Tool Design: Lessons from goose

Practical patterns for designing MCP tool interfaces that LLMs can use effectively.

## 1. Single tool with action dispatch > many tools

Exposing dozens of tools pollutes the client's tool namespace and wastes context. A single tool with an explicit `action` parameter is cleaner:

```python
@mcp.tool()
async def my_tool(action: str, params: dict | None = None) -> dict | list:
    data = {"action": action, **(params or {})}
    return await handle_action(data, ops)
```

The `action` string is visible in the MCP schema. The `params` dict carries action-specific arguments. Clients see exactly two fields, not 30 tools.

## 2. Make action a schema-level parameter, not hidden in JSON

**Bad** — opaque JSON string hides structure:
```python
async def my_tool(request: str) -> str:
    data = json.loads(request)  # LLM can't see what's inside
```

**Good** — action is a visible schema field:
```python
async def my_tool(action: str, params: dict | None = None) -> dict:
    data = {"action": action, **(params or {})}
```

MCP inputSchema becomes `{"action": {"type": "string"}, "params": {"type": "object"}}`. LLMs can see and autocomplete the action name.

## 3. Return structured data, not JSON strings

**Bad** — double-encoded JSON:
```python
async def my_tool(action: str) -> str:
    return json.dumps({"status": "ok"})
# Client sees: {"result": "{\"status\": \"ok\"}"}  — string inside string
```

**Good** — return dict/list, let FastMCP serialize:
```python
async def my_tool(action: str) -> dict:
    result_str = await handle_action(data, ops)  # internal JSON string
    return json.loads(result_str)                 # parse back to dict
# Client sees: {"result": {"status": "ok"}}  — clean structured data
```

If your internal dispatch returns JSON strings (useful for tests), parse them back to dicts in the tool function before returning.

## 4. Provide a describe/introspect action

LLMs need to know valid parameter values _before_ calling `run`. A `describe` action returns:
- Parameter names, types, defaults, enum values
- Hints from structured metadata (e.g. `when_to_change`)
- No full definition payload — just what the caller needs

```
action=describe_pipeline, params={name: "research"}
→ {parameters: {depth: {type: "enum", enum: ["xs","s","m","l"], default: "m", hint: "Use xs for fast drafts"}}}
```

The server instructions should tell callers: "Use describe before run to see valid parameters."

## 5. Support blocking (wait) mode for run actions

Non-blocking `run` returns immediately with a `run_id` — good for long pipelines. But many callers want to just get the result. Add `wait: true`:

```python
if data.get("wait") and run_id:
    entry = active_tasks.get(run_id)
    if entry:
        await entry[0]  # await the asyncio.Task
    run = ops.get_run(run_id)
    result["status"] = run["status"]
    result["outputs"] = run["outputs"]
```

This way callers choose: fire-and-forget or blocking. Same action, one extra flag.

## 6. Echo resolved inputs in responses

When defaults are applied or values coerced, include `resolved_inputs` in the run response:

```json
{
  "run_id": "abc",
  "status": "running",
  "resolved_inputs": {"prompt": "test", "depth": "m"}
}
```

The caller sees exactly what values were used, including defaults they didn't explicitly set. This prevents "why did it use that model?" confusion.

## 7. Trim list responses — summaries over raw payloads

`list` actions should return metadata + terse parameter summaries, not raw definitions:

```json
[{
  "name": "research",
  "description": "Deep research with critic loop",
  "inputs": {
    "prompt": {"type": "string", "required": true},
    "depth": {"type": "enum", "enum": ["xs","s","m","l"], "default": "m"}
  }
}]
```

Drop heavy fields (`definition`, `trace`) from list results. Callers can use `load` or `describe` to get full details.

## 8. Merge related status actions

Instead of separate `status` and `result` actions, use one `pipeline_status` with an `include_trace` flag:

```
action=pipeline_status, params={run_id: "abc"}                    → progress + status
action=pipeline_status, params={run_id: "abc", include_trace: true} → + full trace
```

Keep old action names as aliases for backward compatibility:
```python
elif action in ("status", "result", "pipeline_status"):
    include_trace = data.get("include_trace", action == "result")
```

## 9. Enriched validation errors

When input validation fails, include enough context for the LLM to self-correct:

**Bad**: `Parameter 'depth' must be one of: xs, s, m, l`

**Good**: `Parameter 'depth' must be one of: xs, s, m, l (got 'standard'). Hint: Use xs/s for fast drafts, m for balanced production runs.`

Include:
- The invalid value that was provided (`got 'standard'`)
- Allowed values (enum list)
- Hints from parameter metadata (`details.when_to_change`)
- Constraint text for range violations

This turns a failed call into a learning opportunity — the LLM retries with the right value.

## 10. Strip internal state from responses

Internal tracking data (`_shared`, `_trace`, `_run_log_path`) must never leak through the MCP interface:

```python
result.pop("_shared", None)  # not serializable, not useful to caller
```

Check every action handler — including `restart` which goes through the same `run_async()` path as `run`.

## 11. FastMCP Context parameter ordering

When using FastMCP's injected `Context` parameter alongside optional parameters, give it a default:

```python
# Bad — SyntaxError: non-default after default
async def my_tool(action: str, params: dict | None = None, ctx: Context) -> dict:

# Good
async def my_tool(action: str, params: dict | None = None, ctx: Context = None) -> dict:
```

FastMCP injects `ctx` automatically, but Python syntax requires it has a default when it follows optional params.

## 12. Write server instructions that guide tool usage

FastMCP `instructions` are the first thing a client sees. Use them to set the workflow:

```python
mcp = FastMCP("my-server", instructions=(
    "Use action='describe' before 'run' to see valid parameters. "
    "Use action='status' with run_id to check progress. "
    "Use wait=true in run params for blocking execution."
))
```

Don't just list actions — tell the caller the optimal sequence.

## 13. Keep handle_action testable independently

The dispatch function should take a plain dict and return a JSON string. The MCP tool function is a thin wrapper:

```python
# Testable without MCP
async def handle_action(data: dict, ops: Ops) -> str:
    ...

# MCP wrapper
@mcp.tool()
async def my_tool(action: str, params: dict | None = None) -> dict:
    data = {"action": action, **(params or {})}
    result_str = await handle_action(data, ops)
    return json.loads(result_str)
```

Tests call `handle_action()` directly with dicts. No MCP setup needed.

## Summary checklist

- [ ] Single tool with `action` + `params` (not many tools, not opaque JSON string)
- [ ] Return dict/list, not JSON string (avoid double-encoding)
- [ ] Provide `describe` action for parameter introspection
- [ ] Support `wait: true` for blocking run
- [ ] Echo `resolved_inputs` in run responses
- [ ] Trim list responses (summaries, not full payloads)
- [ ] Merge related actions with flags (not proliferating action names)
- [ ] Enriched validation errors (got value, allowed values, hints)
- [ ] Strip internal state (`_shared`, `_trace`) from responses
- [ ] Server instructions guide the caller workflow
- [ ] Dispatch function testable without MCP
