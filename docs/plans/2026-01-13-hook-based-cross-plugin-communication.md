# Hook-Based Cross-Plugin Communication

> **Status:** Future enhancement
> **Priority:** Low
> **Related:** ntfy_inbox → ai plugin coupling

## Problem

Currently `ntfy_inbox/inbox.py` directly imports from the AI plugin:
```python
from dodo.plugins.ai import DEFAULT_COMMAND
from dodo.plugins.ai.engine import run_ai
from dodo.plugins.ai.prompts import DEFAULT_SYS_PROMPT
```

This creates tight coupling between plugins. If AI plugin internals change (e.g., `engine.py` renamed), ntfy_inbox breaks even if AI is installed.

## Proposed Solution

Use the existing `call_hook` mechanism for cross-plugin communication.

### AI Plugin Changes

```python
# ai/__init__.py
def register_hooks() -> dict[str, str]:
    return {"process_ai_text": "process_ai_text"}

def process_ai_text(cfg, text: str, piped_content: str | None = None) -> list[str]:
    """Hook for other plugins to request AI text processing.

    Returns list of processed todo texts.
    """
    from dodo.plugins.ai.engine import run_ai
    from dodo.plugins.ai.prompts import DEFAULT_SYS_PROMPT

    ai_command = cfg.get_plugin_config("ai", "command", DEFAULT_COMMAND)
    return run_ai(
        user_input=text,
        piped_content=piped_content,
        command=ai_command,
        system_prompt=DEFAULT_SYS_PROMPT,
    )
```

### ntfy_inbox Changes

```python
# ntfy_inbox/inbox.py
from dodo.plugins import call_hook

# Instead of direct imports:
result = call_hook("process_ai_text", cfg, text)
if result is not None:
    for todo_text in result:
        item = svc.add(todo_text)
        console.print(f"[green]Added:[/green] {item.text}{proj_info}")
else:
    console.print("[yellow]AI plugin not available, adding as-is[/yellow]")
    item = svc.add(text)
```

## Benefits

- Full decoupling: ntfy_inbox has zero knowledge of AI plugin internals
- Resilient: No try/except needed, `call_hook` returns None if unavailable
- Extensible: Other plugins could provide alternative AI processing

## When to Implement

Consider implementing when:
- Adding more cross-plugin interactions
- AI plugin undergoes major refactoring
- New plugins need AI processing capability
