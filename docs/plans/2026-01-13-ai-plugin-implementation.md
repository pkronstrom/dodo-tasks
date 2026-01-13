# AI Plugin Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract AI functionality from core into a separate plugin with nested config structure.

**Architecture:** Move `ai.py` and `ai_commands.py` into `plugins/ai/`, migrate all plugin configs to nested `plugins.<name>` structure, add `call_hook()` for cross-plugin communication.

**Tech Stack:** Python, Typer CLI, JSON config

---

## Task 1: Add `get_plugin_config()` helper to config.py

**Files:**
- Modify: `src/dodo/config.py:115-123`

**Step 1: Add the helper method to Config class**

Add after `__getattr__` method (around line 123):

```python
def get_plugin_config(self, plugin_name: str, key: str, default: Any = None) -> Any:
    """Get config value for a plugin from nested plugins.<name> structure."""
    plugins = self._data.get("plugins", {})
    plugin_config = plugins.get(plugin_name, {})
    return plugin_config.get(key, default)

def set_plugin_config(self, plugin_name: str, key: str, value: Any) -> None:
    """Set config value for a plugin in nested plugins.<name> structure."""
    if "plugins" not in self._data:
        self._data["plugins"] = {}
    if plugin_name not in self._data["plugins"]:
        self._data["plugins"][plugin_name] = {}
    self._data["plugins"][plugin_name][key] = value
    self._save()
```

**Step 2: Run tests**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (existing tests still pass)

**Step 3: Commit**

```bash
git add src/dodo/config.py
git commit -m "feat(config): add get_plugin_config and set_plugin_config helpers"
```

---

## Task 2: Add `call_hook()` to plugin system

**Files:**
- Modify: `src/dodo/plugins/__init__.py:20-28` (add to __all__)
- Modify: `src/dodo/plugins/__init__.py:284` (add function after apply_hooks)

**Step 1: Add call_hook to __all__**

Update the `__all__` list to include `call_hook`:

```python
__all__ = [
    # Public API
    "apply_hooks",
    "call_hook",
    "clear_plugin_cache",
    "get_all_plugins",
    "load_registry",
    "import_plugin",
    "scan_and_save",
]
```

**Step 2: Add call_hook function**

Add after `apply_hooks` function (after line 284):

```python
def call_hook(hook_name: str, config: Config, *args, **kwargs) -> Any | None:
    """Call a named hook from any enabled plugin that provides it.

    Unlike apply_hooks which chains transformations, this calls a specific
    hook function and returns its result directly. Used for cross-plugin
    communication (e.g., AI plugin calling graph plugin's add_dependencies).

    Args:
        hook_name: The hook name to call (e.g., "add_dependencies")
        config: The Config instance
        *args, **kwargs: Arguments to pass to the hook function

    Returns:
        The hook function's return value, or None if no plugin provides it.
    """
    registry = load_registry(config.config_dir)
    enabled = config.enabled_plugins

    for name, info in registry.items():
        if "register_hooks" not in info.get("hooks", []):
            continue
        if name not in enabled:
            continue

        path = None if info.get("builtin") else info.get("path")
        plugin = import_plugin(name, path)

        register_hooks = getattr(plugin, "register_hooks", None)
        if not register_hooks:
            continue

        hooks = register_hooks()
        if hook_name not in hooks:
            continue

        # Import and call the hook function
        hook_ref = hooks[hook_name]
        module_path, func_name = hook_ref.rsplit(":", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        return func(*args, **kwargs)

    return None
```

**Step 3: Add register_hooks to known hooks list**

Update `_KNOWN_HOOKS` (around line 48):

```python
_KNOWN_HOOKS = [
    "register_commands",
    "register_root_commands",
    "register_config",
    "register_backend",
    "register_hooks",
    "extend_backend",
    "extend_formatter",
]
```

**Step 4: Add missing import**

Add to imports at top (line 9):

```python
import importlib
import importlib.util
```

Note: `importlib` is already imported via `importlib.util`, but we need the base module for `import_module`.

**Step 5: Run tests**

Run: `uv run pytest tests/test_plugins.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/dodo/plugins/__init__.py
git commit -m "feat(plugins): add call_hook for cross-plugin communication"
```

---

## Task 3: Add `register_hooks` to graph plugin

**Files:**
- Modify: `src/dodo/plugins/graph/__init__.py`
- Modify: `src/dodo/plugins/graph/wrapper.py`

**Step 1: Add register_hooks function to graph/__init__.py**

Add after `extend_formatter` function (end of file):

```python
def register_hooks() -> dict[str, str]:
    """Register callable hooks for cross-plugin communication."""
    return {
        "add_dependencies": "dodo.plugins.graph.wrapper:add_dependencies_hook",
    }
```

**Step 2: Add add_dependencies_hook to wrapper.py**

Add at end of `src/dodo/plugins/graph/wrapper.py`:

```python
def add_dependencies_hook(backend, pairs: list[tuple[str, str]]) -> int:
    """Add dependency pairs via hook interface.

    Called by AI plugin's `ai dep` command to store detected dependencies.

    Args:
        backend: The backend instance (should be GraphWrapper)
        pairs: List of (blocked_id, blocker_id) tuples

    Returns:
        Number of dependencies added
    """
    if not isinstance(backend, GraphWrapper):
        return 0

    count = 0
    for blocked_id, blocker_id in pairs:
        try:
            backend.add_dependency(blocker_id, blocked_id)
            count += 1
        except Exception:
            pass  # Skip invalid dependencies
    return count
```

**Step 3: Run tests**

Run: `uv run pytest tests/test_graph.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/dodo/plugins/graph/__init__.py src/dodo/plugins/graph/wrapper.py
git commit -m "feat(graph): add register_hooks for cross-plugin dependency storage"
```

---

## Task 4: Create AI plugin directory structure

**Files:**
- Create: `src/dodo/plugins/ai/__init__.py`
- Create: `src/dodo/plugins/ai/schemas.py`
- Create: `src/dodo/plugins/ai/prompts.py`
- Create: `src/dodo/plugins/ai/engine.py`
- Create: `src/dodo/plugins/ai/cli.py`

**Step 1: Create the directory**

```bash
mkdir -p src/dodo/plugins/ai
```

**Step 2: Create schemas.py**

Copy schemas from `ai.py` to `src/dodo/plugins/ai/schemas.py`:

```python
"""JSON schemas for AI command outputs."""

import json

DEFAULT_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {"tasks": {"type": "array", "items": {"type": "string"}}},
        "required": ["tasks"],
    }
)

ADD_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "priority": {
                            "type": ["string", "null"],
                            "enum": ["critical", "high", "normal", "low", "someday", None],
                        },
                        "tags": {"type": ["array", "null"], "items": {"type": "string"}},
                    },
                    "required": ["text"],
                },
            }
        },
        "required": ["tasks"],
    }
)

PRIORITIZE_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "assignments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "priority": {
                            "type": "string",
                            "enum": ["critical", "high", "normal", "low", "someday"],
                        },
                        "reason": {"type": "string"},
                    },
                    "required": ["id", "priority"],
                },
            }
        },
        "required": ["assignments"],
    }
)

TAG_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "suggestions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "tags"],
                },
            }
        },
        "required": ["suggestions"],
    }
)

REWORD_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "rewrites": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["id", "text"],
                },
            }
        },
        "required": ["rewrites"],
    }
)

RUN_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "Only include todos that changed, with changed fields + id",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "text": {"type": "string"},
                        "status": {"enum": ["pending", "done"]},
                        "priority": {
                            "type": ["string", "null"],
                            "enum": ["critical", "high", "normal", "low", "someday", None],
                        },
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "IDs of todos this one depends on (blockers)",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Brief explanation of why this change is needed",
                        },
                    },
                    "required": ["id", "reason"],
                },
            },
            "delete": {
                "type": "array",
                "description": "Todos to delete - ONLY when user explicitly requests",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "reason": {
                            "type": "string",
                            "description": "Why this should be deleted (must cite user request)",
                        },
                    },
                    "required": ["id", "reason"],
                },
            },
            "create": {
                "type": "array",
                "description": "New todos to create",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "priority": {
                            "type": ["string", "null"],
                            "enum": ["critical", "high", "normal", "low", "someday", None],
                        },
                        "tags": {"type": ["array", "null"], "items": {"type": "string"}},
                        "reason": {
                            "type": "string",
                            "description": "Why this new todo should be created",
                        },
                    },
                    "required": ["text", "reason"],
                },
            },
        },
        "required": ["todos", "delete", "create"],
    }
)

DEP_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "dependencies": {
                "type": "array",
                "description": "List of dependency relationships to add",
                "items": {
                    "type": "object",
                    "properties": {
                        "blocked_id": {
                            "type": "string",
                            "description": "ID of todo that is blocked (depends on another)",
                        },
                        "blocker_id": {
                            "type": "string",
                            "description": "ID of todo that blocks (must be done first)",
                        },
                    },
                    "required": ["blocked_id", "blocker_id"],
                },
            }
        },
        "required": ["dependencies"],
    }
)
```

**Step 3: Create prompts.py**

Copy prompts from `ai.py` to `src/dodo/plugins/ai/prompts.py`:

```python
"""Default prompts for AI operations."""

DEFAULT_ADD_PROMPT = """Create todo items from user input. The tasks array must NEVER be empty.
CRITICAL: Even single words like "test" or "foo" become todos with that exact text.
For each task:
- Text: Use the input directly. Apply imperative mood if possible ("Fix X", "Add Y").
- Priority: Only set if explicitly indicated. Default to null.
- Tags: Infer from context. Use existing tags when relevant: {existing_tags}

Output ONLY the JSON object with tasks array. Never ask questions or add commentary.
"""

DEFAULT_PRIORITIZE_PROMPT = """Analyze these pending todos and suggest priority levels.
Consider:
- Urgency (deadlines, blocking issues)
- Impact (user-facing, core functionality)
- Dependencies (what blocks other work)

Current todos:
{todos}

Output assignments with id, priority (critical/high/normal/low/someday), and brief reason.
"""

DEFAULT_TAG_PROMPT = """Suggest tags for these todos based on content.
Use existing project tags when relevant: {existing_tags}
Keep tags lowercase, use hyphens for multi-word.

Current todos:
{todos}

Output suggestions with id and array of tags.
"""

DEFAULT_REWORD_PROMPT = """Improve clarity of these todo descriptions.
- Use imperative mood ("Fix X" not "Fixing X")
- Be specific but concise
- Preserve original intent

Current todos:
{todos}

Output rewrites with id and improved text.
"""

DEFAULT_RUN_PROMPT = """You are a todo list assistant with tool access. Execute the user instruction.
You can use tools to read files, search code, check git history, and search the web for context.

For existing todos:
- Modify: Include in "todos" array with id and changed fields only
- Delete: ONLY when user EXPLICITLY requests deletion (e.g., "delete", "remove", "clean up duplicates")
  NEVER delete items just because they seem redundant, old, or unclear.
  When in doubt, keep the item.

For new todos:
- Create: Add to "create" array with text (required), priority and tags (optional)

Available fields:
- text: The todo description
- status: pending or done
- priority: critical, high, normal, low, someday, or null
- tags: Array of tag strings (lowercase, hyphens for multi-word)
- dependencies: Array of IDs this todo depends on (blockers)

IMPORTANT: Be conservative. Only make changes directly requested by the instruction.
Do not "clean up" or "improve" items unless explicitly asked.

Current todos:
{todos}

User instruction: {instruction}
"""

DEFAULT_DEP_PROMPT = """Analyze these todos and detect logical dependencies.
A dependency means one task should be completed before another can start.
Only suggest dependencies where the relationship is clear and meaningful.

Look for:
- Sequential tasks (step 1 before step 2)
- Prerequisites (need X before Y)
- Blocking relationships (cannot do Y until X is done)

Current todos:
{todos}

Return dependencies as pairs: blocked_id depends on blocker_id.
"""

DEFAULT_SYS_PROMPT = (
    "Convert user input into a JSON array of todo strings. "
    "NEVER ask questions or add commentary. Output ONLY the JSON array, nothing else. "
    'If input is one task, return ["task"]. If multiple, split into separate items. '
    "Keep each item under 100 chars."
)
```

**Step 4: Commit the schemas and prompts**

```bash
git add src/dodo/plugins/ai/schemas.py src/dodo/plugins/ai/prompts.py
git commit -m "feat(ai-plugin): add schemas and prompts modules"
```

---

## Task 5: Create AI plugin engine.py

**Files:**
- Create: `src/dodo/plugins/ai/engine.py`

**Step 1: Create engine.py**

Copy execution logic from `ai.py` to `src/dodo/plugins/ai/engine.py`:

```python
"""AI execution engine for todo operations."""

import json
import shlex
import subprocess
import sys
from typing import Any

from dodo.plugins.ai.schemas import (
    ADD_SCHEMA,
    DEFAULT_SCHEMA,
    DEP_SCHEMA,
    PRIORITIZE_SCHEMA,
    REWORD_SCHEMA,
    RUN_SCHEMA,
    TAG_SCHEMA,
)

# Constants
AI_COMMAND_TIMEOUT = 60  # seconds


def _escape_single_quotes(s: str) -> str:
    """Escape single quotes for shell single-quoted strings."""
    return s.replace("'", "'\"'\"'")


def build_command(
    template: str,
    prompt: str,
    system: str,
    schema: str,
    model: str = "haiku",
) -> list[str]:
    """Build command arguments from template."""
    cmd_str = (
        template.replace("{{prompt}}", _escape_single_quotes(prompt))
        .replace("{{system}}", _escape_single_quotes(system))
        .replace("{{schema}}", _escape_single_quotes(schema))
        .replace("{{model}}", model)
    )
    return shlex.split(cmd_str)


def _execute_ai_command(cmd_args: list[str], timeout: int = AI_COMMAND_TIMEOUT) -> str | None:
    """Execute AI command and return stdout, or None on error."""
    try:
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            print(f"AI command failed (exit {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return None

        return result.stdout.strip()

    except subprocess.TimeoutExpired:
        print("AI command timed out", file=sys.stderr)
        return None


def _extract_ai_result(output: str, result_key: str) -> list[Any] | None:
    """Extract result list from AI JSON output."""
    try:
        data = json.loads(output)

        if isinstance(data, dict) and "structured_output" in data:
            return data["structured_output"].get(result_key, [])
        elif isinstance(data, dict) and result_key in data:
            return data[result_key]
        elif isinstance(data, list):
            return data
        else:
            print(f"Unexpected output format. Raw: {output[:500]}", file=sys.stderr)
            return None

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Failed to parse AI output: {e}", file=sys.stderr)
        return None


def run_ai(
    user_input: str,
    command: str,
    system_prompt: str,
    piped_content: str | None = None,
    schema: str | None = None,
    model: str = "haiku",
) -> list[str]:
    """Run AI command and return list of todo items."""
    prompt_parts = []
    if piped_content:
        prompt_parts.append(f"[Piped input]:\n{piped_content}\n\n[User request]:")
    prompt_parts.append(user_input)
    full_prompt = "\n".join(prompt_parts)

    cmd_args = build_command(
        template=command,
        prompt=full_prompt,
        system=system_prompt,
        schema=schema or DEFAULT_SCHEMA,
        model=model,
    )

    output = _execute_ai_command(cmd_args)
    if output is None:
        return []

    tasks = _extract_ai_result(output, "tasks")
    if tasks is None:
        return []

    todos = [str(item) for item in tasks if item]
    if not todos:
        print(f"AI returned empty list. Raw output: {output[:500]}", file=sys.stderr)
    return todos


def run_ai_structured(
    command: str,
    system_prompt: str,
    user_prompt: str,
    schema: str,
    result_key: str,
    model: str = "haiku",
) -> list[dict]:
    """Run AI command and return structured result."""
    cmd_args = build_command(
        template=command,
        prompt=user_prompt,
        system=system_prompt,
        schema=schema,
        model=model,
    )

    output = _execute_ai_command(cmd_args)
    if output is None:
        return []

    items = _extract_ai_result(output, result_key)
    if items is None:
        return []

    return [item for item in items if isinstance(item, dict)]


def run_ai_add(
    user_input: str,
    command: str,
    system_prompt: str,
    existing_tags: list[str] | None = None,
    piped_content: str | None = None,
    model: str = "haiku",
) -> list[dict]:
    """Run AI command for adding todos. Returns list of {text, priority, tags}."""
    prompt = system_prompt.format(existing_tags=existing_tags or [])

    input_parts = []
    if piped_content:
        input_parts.append(f"[Piped input]:\n{piped_content}\n\n[User request]:")
    input_parts.append(user_input)
    full_input = "\n".join(input_parts)

    cmd_args = build_command(
        template=command,
        prompt=full_input,
        system=prompt,
        schema=ADD_SCHEMA,
        model=model,
    )

    output = _execute_ai_command(cmd_args)
    if output is None:
        return []

    tasks = _extract_ai_result(output, "tasks")
    if tasks is None:
        return []

    return [task for task in tasks if isinstance(task, dict) and task.get("text")]


def run_ai_prioritize(
    todos: list[dict],
    command: str,
    system_prompt: str,
    model: str = "haiku",
) -> list[dict]:
    """Run AI to suggest priority changes. Returns list of {id, priority, reason}."""
    todos_text = "\n".join(
        f"- [{t['id']}] {t['text']} (current: {t.get('priority', 'none')})" for t in todos
    )
    prompt = system_prompt.format(todos=todos_text)

    return run_ai_structured(
        command=command,
        system_prompt=prompt,
        user_prompt="Analyze and suggest priority changes",
        schema=PRIORITIZE_SCHEMA,
        result_key="assignments",
        model=model,
    )


def run_ai_tag(
    todos: list[dict],
    command: str,
    system_prompt: str,
    existing_tags: list[str] | None = None,
    model: str = "haiku",
) -> list[dict]:
    """Run AI to suggest tags. Returns list of {id, tags}."""
    todos_text = "\n".join(
        f"- [{t['id']}] {t['text']} (current tags: {t.get('tags', [])})" for t in todos
    )
    prompt = system_prompt.format(todos=todos_text, existing_tags=existing_tags or [])

    return run_ai_structured(
        command=command,
        system_prompt=prompt,
        user_prompt="Suggest tags for these todos",
        schema=TAG_SCHEMA,
        result_key="suggestions",
        model=model,
    )


def run_ai_reword(
    todos: list[dict],
    command: str,
    system_prompt: str,
    model: str = "haiku",
) -> list[dict]:
    """Run AI to suggest rewording. Returns list of {id, text}."""
    todos_text = "\n".join(f"- [{t['id']}] {t['text']}" for t in todos)
    prompt = system_prompt.format(todos=todos_text)

    return run_ai_structured(
        command=command,
        system_prompt=prompt,
        user_prompt="Improve these todo descriptions",
        schema=REWORD_SCHEMA,
        result_key="rewrites",
        model=model,
    )


def _extract_ai_run_result(output: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Extract todos, delete list, and create list from AI run output."""
    try:
        data = json.loads(output)

        if isinstance(data, dict) and "structured_output" in data:
            data = data["structured_output"]

        if not isinstance(data, dict):
            print(f"Unexpected output type: {type(data).__name__}", file=sys.stderr)
            return ([], [], [])

        todos = data.get("todos", [])
        delete = data.get("delete", [])
        create = data.get("create", [])

        delete_items = []
        for d in delete:
            if isinstance(d, str):
                delete_items.append({"id": d, "reason": ""})
            elif isinstance(d, dict) and d.get("id"):
                delete_items.append(d)

        return (
            [t for t in todos if isinstance(t, dict) and t.get("id")],
            delete_items,
            [c for c in create if isinstance(c, dict) and c.get("text")],
        )

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Failed to parse AI output: {e}", file=sys.stderr)
        return ([], [], [])


def run_ai_run(
    todos: list[dict],
    instruction: str,
    command: str,
    system_prompt: str,
    piped_content: str | None = None,
    model: str = "sonnet",
) -> tuple[list[dict], list[dict], list[dict]]:
    """Run AI with user instruction on todos."""
    todos_text = "\n".join(
        f"- [{t['id']}] {t['text']} "
        f"(status: {t.get('status', 'pending')}, "
        f"priority: {t.get('priority', 'none')}, "
        f"tags: {t.get('tags', [])}, "
        f"deps: {t.get('dependencies', [])})"
        for t in todos
    )

    full_instruction = instruction
    if piped_content:
        full_instruction = f"[Piped context]:\n{piped_content}\n\n[Instruction]: {instruction}"

    prompt = system_prompt.format(todos=todos_text, instruction=full_instruction)

    cmd_args = build_command(
        template=command,
        prompt=full_instruction,
        system=prompt,
        schema=RUN_SCHEMA,
        model=model,
    )

    output = _execute_ai_command(cmd_args)
    if output is None:
        return ([], [], [])

    return _extract_ai_run_result(output)


def run_ai_dep(
    todos: list[dict],
    command: str,
    system_prompt: str,
    model: str = "haiku",
) -> list[dict]:
    """Run AI to detect dependencies. Returns list of {blocked_id, blocker_id}."""
    todos_text = "\n".join(f"- [{t['id']}] {t['text']}" for t in todos)
    prompt = system_prompt.format(todos=todos_text)

    return run_ai_structured(
        command=command,
        system_prompt=prompt,
        user_prompt="Analyze and suggest dependencies",
        schema=DEP_SCHEMA,
        result_key="dependencies",
        model=model,
    )
```

**Step 2: Commit**

```bash
git add src/dodo/plugins/ai/engine.py
git commit -m "feat(ai-plugin): add engine module with AI execution logic"
```

---

## Task 6: Create AI plugin cli.py

**Files:**
- Create: `src/dodo/plugins/ai/cli.py`

**Step 1: Create cli.py**

Copy and adapt commands from `ai_commands.py` to `src/dodo/plugins/ai/cli.py`. Key changes:
- Use `config.get_plugin_config("ai", ...)` for config access
- Use `call_hook` for `ai dep` command instead of direct backend access

```python
"""AI-assisted todo management commands."""

import sys
from typing import Annotated

import typer
from rich.console import Console

from dodo.plugins.ai.prompts import (
    DEFAULT_ADD_PROMPT,
    DEFAULT_DEP_PROMPT,
    DEFAULT_PRIORITIZE_PROMPT,
    DEFAULT_REWORD_PROMPT,
    DEFAULT_RUN_PROMPT,
    DEFAULT_SYS_PROMPT,
    DEFAULT_TAG_PROMPT,
)

ai_app = typer.Typer(
    name="ai",
    help="AI-assisted todo management.",
)

console = Console()

# Default config values
DEFAULT_COMMAND = "claude -p '{{prompt}}' --system-prompt '{{system}}' --json-schema '{{schema}}' --output-format json --model {{model}} --tools ''"
DEFAULT_RUN_COMMAND = "claude -p '{{prompt}}' --system-prompt '{{system}}' --json-schema '{{schema}}' --output-format json --model {{model}} --tools 'Read,Glob,Grep,WebSearch,Bash(git log:*,git status:*,git diff:*,git show:*,git blame:*,git branch:*)'"
DEFAULT_MODEL = "sonnet"


def _get_ai_config(cfg):
    """Get AI plugin config values."""
    return {
        "command": cfg.get_plugin_config("ai", "command", DEFAULT_COMMAND),
        "run_command": cfg.get_plugin_config("ai", "run_command", DEFAULT_RUN_COMMAND),
        "model": cfg.get_plugin_config("ai", "model", DEFAULT_MODEL),
        "run_model": cfg.get_plugin_config("ai", "run_model", DEFAULT_MODEL),
        "prompts": cfg.get_plugin_config("ai", "prompts", {}),
    }


def _get_prompt(ai_config: dict, key: str, default: str) -> str:
    """Get prompt from config or use default."""
    prompts = ai_config.get("prompts", {})
    return prompts.get(key, "") or default


def _print_waiting(action: str) -> None:
    """Print a friendly waiting message."""
    console.print(f"[dim italic]{action}...[/dim italic]")


@ai_app.command(name="add")
def ai_add(
    text: Annotated[str | None, typer.Argument(help="Input text")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Add to global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo")] = None,
):
    """Add todos with AI-inferred priority and tags."""
    from dodo.cli_context import get_service_context
    from dodo.models import Priority
    from dodo.plugins.ai.engine import run_ai_add

    piped = None
    if not sys.stdin.isatty():
        piped = sys.stdin.read()

    if not text and not piped:
        console.print("[red]Error:[/red] Provide text or pipe input")
        raise typer.Exit(1)

    cfg, project_id, svc = get_service_context(global_=global_)
    ai_config = _get_ai_config(cfg)

    # Get existing tags for context
    existing_items = svc.list()
    existing_tags: set[str] = set()
    for item in existing_items:
        if item.tags:
            existing_tags.update(item.tags)

    prompt = _get_prompt(ai_config, "add", DEFAULT_ADD_PROMPT)

    _print_waiting("Creating todos")
    tasks = run_ai_add(
        user_input=text or "",
        piped_content=piped,
        command=ai_config["command"],
        system_prompt=prompt,
        existing_tags=list(existing_tags),
        model=ai_config["model"],
    )

    if not tasks:
        console.print("[red]Error:[/red] AI returned no todos")
        raise typer.Exit(1)

    target = dodo or project_id or "global"
    for task in tasks:
        priority = None
        if task.get("priority"):
            try:
                priority = Priority(task["priority"])
            except ValueError:
                pass

        item = svc.add(
            text=task["text"],
            priority=priority,
            tags=task.get("tags"),
        )

        priority_str = f" !{item.priority.value}" if item.priority else ""
        tags_str = " " + " ".join(f"#{t}" for t in item.tags) if item.tags else ""
        dest = f"[cyan]{target}[/cyan]" if target != "global" else "[dim]global[/dim]"

        console.print(
            f"[green]+[/green] Added to {dest}: {item.text}{priority_str}{tags_str} [dim]({item.id})[/dim]"
        )


@ai_app.command(name="prio")
@ai_app.command(name="prioritize")
def ai_prioritize(
    yes: Annotated[
        bool, typer.Option("-y", "--yes", help="Auto-apply without confirmation")
    ] = False,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo")] = None,
):
    """AI-assisted bulk priority assignment."""
    from dodo.cli_context import get_service_context
    from dodo.models import Priority, Status
    from dodo.plugins.ai.engine import run_ai_prioritize

    cfg, project_id, svc = get_service_context(global_=global_)
    ai_config = _get_ai_config(cfg)

    items = svc.list(status=Status.PENDING)
    if not items:
        console.print("[yellow]No pending todos[/yellow]")
        return

    todos_data = [
        {
            "id": item.id,
            "text": item.text,
            "priority": item.priority.value if item.priority else None,
        }
        for item in items
    ]

    prompt = _get_prompt(ai_config, "prioritize", DEFAULT_PRIORITIZE_PROMPT)

    _print_waiting("Analyzing priorities")
    assignments = run_ai_prioritize(
        todos=todos_data,
        command=ai_config["command"],
        system_prompt=prompt,
        model=ai_config["model"],
    )

    if not assignments:
        console.print("[green]No priority changes suggested[/green]")
        return

    console.print(f"\n[bold]Proposed changes ({len(assignments)} of {len(items)} todos):[/bold]")
    for assignment in assignments:
        item = next((i for i in items if i.id == assignment["id"]), None)
        if item:
            old_prio = item.priority.value if item.priority else "none"
            text_preview = item.text[:40] + ("..." if len(item.text) > 40 else "")
            reason = f" - {assignment.get('reason', '')}" if assignment.get("reason") else ""
            console.print(
                f'  [dim]{item.id}[/dim]: "{text_preview}" '
                f"[red]{old_prio}[/red] -> [green]{assignment['priority']}[/green]{reason}"
            )

    if not yes:
        confirm = typer.confirm("\nApply changes?", default=False)
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    applied = 0
    for assignment in assignments:
        try:
            priority = Priority(assignment["priority"])
            svc.update_priority(assignment["id"], priority)
            applied += 1
        except (ValueError, KeyError) as e:
            console.print(f"[red]Failed to update {assignment['id']}: {e}[/red]")

    console.print(f"[green]+[/green] Applied {applied} priority changes")


@ai_app.command(name="reword")
def ai_reword(
    yes: Annotated[
        bool, typer.Option("-y", "--yes", help="Auto-apply without confirmation")
    ] = False,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo")] = None,
):
    """AI-assisted todo rewording for clarity."""
    from dodo.cli_context import get_service_context
    from dodo.models import Status
    from dodo.plugins.ai.engine import run_ai_reword

    cfg, project_id, svc = get_service_context(global_=global_)
    ai_config = _get_ai_config(cfg)

    items = svc.list(status=Status.PENDING)
    if not items:
        console.print("[yellow]No pending todos[/yellow]")
        return

    todos_data = [{"id": item.id, "text": item.text} for item in items]

    prompt = _get_prompt(ai_config, "reword", DEFAULT_REWORD_PROMPT)

    _print_waiting("Improving descriptions")
    rewrites = run_ai_reword(
        todos=todos_data,
        command=ai_config["command"],
        system_prompt=prompt,
        model=ai_config["model"],
    )

    if not rewrites:
        console.print("[green]No rewording suggestions[/green]")
        return

    console.print(f"\n[bold]Proposed rewrites ({len(rewrites)} of {len(items)} todos):[/bold]")
    for rewrite in rewrites:
        item = next((i for i in items if i.id == rewrite["id"]), None)
        if item:
            console.print(f"  [dim]{item.id}[/dim]:")
            console.print(f"    [red]- {item.text}[/red]")
            console.print(f"    [green]+ {rewrite['text']}[/green]")

    if not yes:
        confirm = typer.confirm("\nApply changes?", default=False)
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    applied = 0
    for rewrite in rewrites:
        try:
            svc.update_text(rewrite["id"], rewrite["text"])
            applied += 1
        except KeyError as e:
            console.print(f"[red]Failed to update {rewrite['id']}: {e}[/red]")

    console.print(f"[green]+[/green] Applied {applied} rewrites")


@ai_app.command(name="tag")
def ai_tag(
    yes: Annotated[
        bool, typer.Option("-y", "--yes", help="Auto-apply without confirmation")
    ] = False,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo")] = None,
):
    """AI-assisted tag suggestions."""
    from dodo.cli_context import get_service_context
    from dodo.models import Status
    from dodo.plugins.ai.engine import run_ai_tag

    cfg, project_id, svc = get_service_context(global_=global_)
    ai_config = _get_ai_config(cfg)

    items = svc.list(status=Status.PENDING)
    if not items:
        console.print("[yellow]No pending todos[/yellow]")
        return

    existing_tags: set[str] = set()
    for item in items:
        if item.tags:
            existing_tags.update(item.tags)

    todos_data = [{"id": item.id, "text": item.text, "tags": item.tags or []} for item in items]

    prompt = _get_prompt(ai_config, "tag", DEFAULT_TAG_PROMPT)

    _print_waiting("Suggesting tags")
    suggestions = run_ai_tag(
        todos=todos_data,
        command=ai_config["command"],
        system_prompt=prompt,
        existing_tags=list(existing_tags),
        model=ai_config["model"],
    )

    if not suggestions:
        console.print("[green]No tag suggestions[/green]")
        return

    console.print(f"\n[bold]Proposed tags ({len(suggestions)} of {len(items)} todos):[/bold]")
    for suggestion in suggestions:
        item = next((i for i in items if i.id == suggestion["id"]), None)
        if item:
            old_tags = " ".join(f"#{t}" for t in (item.tags or []))
            new_tags = " ".join(f"#{t}" for t in suggestion["tags"])
            console.print(f"  [dim]{item.id}[/dim]: {item.text[:30]}...")
            console.print(f"    [red]- {old_tags or '(none)'}[/red]")
            console.print(f"    [green]+ {new_tags}[/green]")

    if not yes:
        confirm = typer.confirm("\nApply changes?", default=False)
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    applied = 0
    for suggestion in suggestions:
        try:
            svc.update_tags(suggestion["id"], suggestion["tags"])
            applied += 1
        except KeyError as e:
            console.print(f"[red]Failed to update {suggestion['id']}: {e}[/red]")

    console.print(f"[green]+[/green] Applied tags to {applied} todos")


@ai_app.command(name="sync")
def ai_sync():
    """Sync all AI suggestions (priority + tags + reword)."""
    console.print("[yellow]AI sync not yet implemented[/yellow]")
    console.print("[dim]This will run prioritize, tag, and reword in sequence.[/dim]")


@ai_app.command(name="run")
def ai_run(
    instruction: Annotated[str, typer.Argument(help="Natural language instruction")],
    yes: Annotated[
        bool, typer.Option("-y", "--yes", help="Auto-apply without confirmation")
    ] = False,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo")] = None,
):
    """Execute natural language instructions on todos with tool access."""
    from dodo.cli_context import get_service_context
    from dodo.models import Priority, Status
    from dodo.plugins.ai.engine import run_ai_run

    piped = None
    if not sys.stdin.isatty():
        piped = sys.stdin.read()

    cfg, project_id, svc = get_service_context(global_=global_)
    ai_config = _get_ai_config(cfg)

    backend = svc.backend
    has_graph = hasattr(backend, "add_dependency")

    items = svc.list()

    todos_data = []
    for item in items:
        data = {
            "id": item.id,
            "text": item.text,
            "status": item.status.value if item.status else "pending",
            "priority": item.priority.value if item.priority else None,
            "tags": item.tags or [],
        }
        if has_graph and hasattr(item, "blocked_by"):
            data["dependencies"] = item.blocked_by or []
        todos_data.append(data)

    prompt = _get_prompt(ai_config, "run", DEFAULT_RUN_PROMPT)
    if not has_graph:
        prompt = prompt.replace(
            "- dependencies: Array of IDs this todo depends on (blockers)\n", ""
        )

    _print_waiting("Processing instruction")
    modified, to_delete, to_create = run_ai_run(
        todos=todos_data,
        instruction=instruction,
        command=ai_config["run_command"],
        system_prompt=prompt,
        piped_content=piped,
        model=ai_config["run_model"],
    )

    if not modified and not to_delete and not to_create:
        console.print("[green]No changes needed[/green]")
        return

    current_by_id = {t["id"]: t for t in todos_data}
    items_by_id = {item.id: item for item in items}

    total_changes = len(modified) + len(to_delete) + len(to_create)
    console.print(f"\n[bold]Proposed changes ({total_changes}):[/bold]")

    for mod in modified:
        item_id = mod["id"]
        if item_id not in current_by_id:
            continue
        current = current_by_id[item_id]
        text_preview = current["text"][:40] + ("..." if len(current["text"]) > 40 else "")
        console.print(f'  [dim]{item_id}[/dim]: "{text_preview}"')

        if mod.get("reason"):
            console.print(f"    [italic cyan]Reason: {mod['reason']}[/italic cyan]")

        if "text" in mod and mod["text"] != current["text"]:
            console.print(f"    [red]- {current['text']}[/red]")
            console.print(f"    [green]+ {mod['text']}[/green]")
        if "status" in mod and mod["status"] != current.get("status"):
            console.print(
                f"    {current.get('status', 'pending')} [dim]→[/dim] [green]{mod['status']}[/green]"
            )
        if "priority" in mod and mod["priority"] != current.get("priority"):
            old_p = current.get("priority") or "none"
            new_p = mod["priority"] or "none"
            console.print(f"    priority: [red]{old_p}[/red] [dim]→[/dim] [green]{new_p}[/green]")
        if "tags" in mod:
            old_tags = set(current.get("tags", []))
            new_tags = set(mod["tags"])
            added = new_tags - old_tags
            removed = old_tags - new_tags
            if added:
                console.print(f"    [green]+ {' '.join(f'#{t}' for t in added)}[/green]")
            if removed:
                console.print(f"    [red]- {' '.join(f'#{t}' for t in removed)}[/red]")
        if "dependencies" in mod:
            old_deps = set(current.get("dependencies", []))
            new_deps = set(mod["dependencies"])
            added = new_deps - old_deps
            removed = old_deps - new_deps
            if added:
                console.print(f"    [green]+ depends on: {', '.join(added)}[/green]")
            if removed:
                console.print(f"    [red]- depends on: {', '.join(removed)}[/red]")

    if to_delete:
        console.print(f"\n[bold]Delete ({len(to_delete)}):[/bold]")
        for del_item in to_delete:
            del_id = del_item["id"] if isinstance(del_item, dict) else del_item
            item = items_by_id.get(del_id)
            if item:
                console.print(f'  [red]x[/red] [dim]{del_id}[/dim]: "{item.text}"')
                reason = del_item.get("reason", "") if isinstance(del_item, dict) else ""
                if reason:
                    console.print(f"    [italic cyan]Reason: {reason}[/italic cyan]")

    if to_create:
        console.print(f"\n[bold]Create ({len(to_create)}):[/bold]")
        for new_todo in to_create:
            priority_str = f" !{new_todo['priority']}" if new_todo.get("priority") else ""
            tags_str = (
                " " + " ".join(f"#{t}" for t in new_todo["tags"]) if new_todo.get("tags") else ""
            )
            console.print(f"  [green]+[/green] {new_todo['text']}{priority_str}{tags_str}")
            if new_todo.get("reason"):
                console.print(f"    [italic cyan]Reason: {new_todo['reason']}[/italic cyan]")

    if not yes:
        confirm = typer.confirm("\nApply changes?", default=False)
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    applied = 0

    for mod in modified:
        item_id = mod["id"]
        try:
            if "text" in mod:
                svc.update_text(item_id, mod["text"])
            if "status" in mod:
                status = Status(mod["status"])
                backend.update(item_id, status)
            if "priority" in mod:
                priority = Priority(mod["priority"]) if mod["priority"] else None
                svc.update_priority(item_id, priority)
            if "tags" in mod:
                svc.update_tags(item_id, mod["tags"])
            if "dependencies" in mod and hasattr(backend, "add_dependency"):
                current_deps = set(current_by_id.get(item_id, {}).get("dependencies", []))
                new_deps = set(mod["dependencies"])
                for dep_id in new_deps - current_deps:
                    backend.add_dependency(dep_id, item_id)
                for dep_id in current_deps - new_deps:
                    backend.remove_dependency(dep_id, item_id)
            applied += 1
        except (ValueError, KeyError) as e:
            console.print(f"[red]Failed to update {item_id}: {e}[/red]")

    for del_item in to_delete:
        del_id = del_item["id"] if isinstance(del_item, dict) else del_item
        try:
            svc.delete(del_id)
            applied += 1
        except KeyError as e:
            console.print(f"[red]Failed to delete {del_id}: {e}[/red]")

    for new_todo in to_create:
        try:
            priority = None
            if new_todo.get("priority"):
                try:
                    priority = Priority(new_todo["priority"])
                except ValueError:
                    pass
            item = svc.add(
                text=new_todo["text"],
                priority=priority,
                tags=new_todo.get("tags"),
            )
            console.print(f"  [green]+[/green] Created: {item.text} [dim]({item.id})[/dim]")
            applied += 1
        except Exception as e:
            console.print(f"[red]Failed to create todo: {e}[/red]")

    console.print(f"[green]+[/green] Applied {applied} changes")


@ai_app.command(name="dep")
def ai_dep(
    yes: Annotated[
        bool, typer.Option("-y", "--yes", help="Auto-apply without confirmation")
    ] = False,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo")] = None,
):
    """AI-assisted dependency detection."""
    from dodo.cli_context import get_service_context
    from dodo.models import Status
    from dodo.plugins import call_hook
    from dodo.plugins.ai.engine import run_ai_dep

    cfg, project_id, svc = get_service_context(global_=global_)
    ai_config = _get_ai_config(cfg)
    backend = svc.backend

    # Check if graph plugin is available via hook
    if not hasattr(backend, "add_dependency"):
        console.print(
            "[red]Error:[/red] Graph plugin required. Enable with: dodo plugins enable graph"
        )
        raise typer.Exit(1)

    items = svc.list(status=Status.PENDING)
    if not items:
        console.print("[yellow]No pending todos[/yellow]")
        return

    todos_data = [{"id": item.id, "text": item.text} for item in items]
    items_by_id = {item.id: item for item in items}

    prompt = _get_prompt(ai_config, "dep", DEFAULT_DEP_PROMPT)

    _print_waiting("Analyzing dependencies")
    suggestions = run_ai_dep(
        todos=todos_data,
        command=ai_config["command"],
        system_prompt=prompt,
        model=ai_config["model"],
    )

    if not suggestions:
        console.print("[green]No dependencies detected[/green]")
        return

    # Filter invalid suggestions
    valid_suggestions = []
    for sug in suggestions:
        blocked_id = sug.get("blocked_id")
        blocker_id = sug.get("blocker_id")
        if blocked_id == blocker_id:
            continue
        if blocked_id in items_by_id and blocker_id in items_by_id:
            existing = backend.get_blockers(blocked_id) if hasattr(backend, "get_blockers") else []
            if blocker_id not in existing:
                valid_suggestions.append(sug)

    if not valid_suggestions:
        console.print("[green]No new dependencies to add[/green]")
        return

    # Group by blocked item
    by_blocked: dict[str, list[str]] = {}
    for sug in valid_suggestions:
        blocked_id = sug["blocked_id"]
        blocker_id = sug["blocker_id"]
        if blocked_id not in by_blocked:
            by_blocked[blocked_id] = []
        by_blocked[blocked_id].append(blocker_id)

    console.print(f"\n[bold]Proposed dependencies ({len(valid_suggestions)}):[/bold]")
    for blocked_id, blocker_ids in by_blocked.items():
        blocked_item = items_by_id[blocked_id]
        text_preview = blocked_item.text[:50] + ("..." if len(blocked_item.text) > 50 else "")
        console.print(f'  "{text_preview}"')
        for blocker_id in blocker_ids:
            blocker_item = items_by_id[blocker_id]
            blocker_preview = blocker_item.text[:45] + (
                "..." if len(blocker_item.text) > 45 else ""
            )
            console.print(f'    [dim]→[/dim] "{blocker_preview}"')

    if not yes:
        confirm = typer.confirm("\nApply changes?", default=False)
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Use hook to add dependencies
    pairs = [(sug["blocked_id"], sug["blocker_id"]) for sug in valid_suggestions]
    result = call_hook("add_dependencies", cfg, backend, pairs)

    if result is None:
        # Fallback to direct backend access if hook not available
        applied = 0
        for sug in valid_suggestions:
            try:
                backend.add_dependency(sug["blocker_id"], sug["blocked_id"])
                applied += 1
            except Exception as e:
                console.print(f"[red]Failed to add dependency: {e}[/red]")
        console.print(f"[green]+[/green] Added {applied} dependencies")
    else:
        console.print(f"[green]+[/green] Added {result} dependencies")
```

**Step 2: Commit**

```bash
git add src/dodo/plugins/ai/cli.py
git commit -m "feat(ai-plugin): add CLI commands module"
```

---

## Task 7: Create AI plugin __init__.py

**Files:**
- Create: `src/dodo/plugins/ai/__init__.py`

**Step 1: Create __init__.py**

```python
"""AI plugin for todo management.

This plugin adds AI-assisted commands for todo creation and management:
- `dodo ai add` - Create todos with AI-inferred priority and tags
- `dodo ai prio` - AI-assisted bulk priority assignment
- `dodo ai tag` - AI-assisted tag suggestions
- `dodo ai reword` - AI-assisted todo rewording
- `dodo ai run` - Execute natural language instructions
- `dodo ai dep` - AI-assisted dependency detection (requires graph plugin)

Requires explicit enabling: `dodo plugins enable ai`
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typer

    from dodo.config import Config

# Commands this plugin registers at root level
COMMANDS = ["ai"]


@dataclass
class ConfigVar:
    """Configuration variable declaration."""

    name: str
    default: str
    label: str | None = None
    kind: str = "edit"
    options: list[str] | None = None
    description: str | None = None


def register_config() -> list[ConfigVar]:
    """Declare config variables for this plugin.

    Note: These are registered for display in the config UI.
    Actual config is stored under plugins.ai in the config file.
    """
    return [
        ConfigVar(
            "ai_command",
            "claude -p '{{prompt}}' --system-prompt '{{system}}' --json-schema '{{schema}}' --output-format json --model {{model}} --tools ''",
            label="AI Command",
            description="Command template for AI operations",
        ),
        ConfigVar(
            "ai_model",
            "sonnet",
            label="AI Model",
            kind="cycle",
            options=["haiku", "sonnet", "opus"],
            description="Model for basic AI commands",
        ),
        ConfigVar(
            "ai_run_model",
            "sonnet",
            label="AI Run Model",
            kind="cycle",
            options=["haiku", "sonnet", "opus"],
            description="Model for ai run command",
        ),
    ]


def register_root_commands(app: typer.Typer, config: Config) -> None:
    """Register AI commands at root level (dodo ai ...)."""
    from dodo.plugins.ai.cli import ai_app

    app.add_typer(ai_app, name="ai")
```

**Step 2: Commit**

```bash
git add src/dodo/plugins/ai/__init__.py
git commit -m "feat(ai-plugin): add plugin init with hook registrations"
```

---

## Task 8: Remove AI from core cli.py

**Files:**
- Modify: `src/dodo/cli.py`

**Step 1: Remove the AI subapp registration**

Delete lines 713-721 (the `_register_ai_subapp` function and its call):

```python
# DELETE THIS BLOCK:
# Register AI commands subapp
def _register_ai_subapp() -> None:
    """Register the AI commands subapp lazily."""
    from dodo.ai_commands import ai_app

    app.add_typer(ai_app, name="ai")


_register_ai_subapp()
```

**Step 2: Remove the standalone `ai` command**

Delete the `ai` command function (lines 401-435):

```python
# DELETE THIS BLOCK:
@app.command()
def ai(
    text: Annotated[str | None, typer.Argument(help="Input text")] = None,
):
    """AI-assisted todo creation."""
    # ... entire function body
```

**Step 3: Run tests**

Run: `uv run pytest tests/test_cli.py -v`
Expected: Some tests may fail (AI-related) - that's expected

**Step 4: Commit**

```bash
git add src/dodo/cli.py
git commit -m "refactor(cli): remove AI commands from core (moved to plugin)"
```

---

## Task 9: Remove core AI files

**Files:**
- Delete: `src/dodo/ai.py`
- Delete: `src/dodo/ai_commands.py`

**Step 1: Delete the files**

```bash
rm src/dodo/ai.py src/dodo/ai_commands.py
```

**Step 2: Commit**

```bash
git add -A
git commit -m "refactor: remove core AI modules (moved to ai plugin)"
```

---

## Task 10: Update config.py to remove AI defaults

**Files:**
- Modify: `src/dodo/config.py`

**Step 1: Remove AI-related keys from DEFAULTS**

Update `Config.DEFAULTS` to remove AI-specific keys (keep only core config):

```python
DEFAULTS: dict[str, Any] = {
    # Toggles
    "worktree_shared": True,
    "timestamps_enabled": True,
    # Settings
    "default_backend": "sqlite",
    "default_format": "table",
    "editor": "",
    # Plugin system
    "enabled_plugins": "",
}
```

**Step 2: Remove AI keys from ConfigMeta.SETTINGS**

Update `ConfigMeta.SETTINGS`:

```python
SETTINGS: dict[str, str] = {
    "default_backend": "Backend (markdown|sqlite|obsidian)",
    "default_format": "Output format (table|jsonl|tsv)",
    "editor": "Editor command (empty = use $EDITOR)",
}
```

**Step 3: Commit**

```bash
git add src/dodo/config.py
git commit -m "refactor(config): remove AI config from core defaults"
```

---

## Task 11: Migrate existing plugin configs to nested structure

**Files:**
- Modify: `src/dodo/plugins/graph/__init__.py`
- Modify: `src/dodo/plugins/ntfy_inbox/__init__.py`
- Modify: `src/dodo/plugins/obsidian/__init__.py`

**Step 1: Update graph plugin config access**

The graph plugin uses `graph_tree_view` config. Update `extend_formatter` in `graph/__init__.py`:

```python
def extend_formatter(formatter, config: Config):
    """Wrap formatter to add blocked_by column, or switch to tree view."""
    from dodo.plugins.graph.formatter import GraphFormatter
    from dodo.plugins.graph.tree import TreeFormatter

    if isinstance(formatter, TreeFormatter):
        return formatter

    # Use nested config access
    tree_view = config.get_plugin_config("graph", "tree_view", "false")
    if str(tree_view).lower() in ("true", "1", "yes"):
        return TreeFormatter()

    return GraphFormatter(formatter)
```

Also update `register_config`:

```python
def register_config() -> list[ConfigVar]:
    """Declare config variables for this plugin."""
    return [
        ConfigVar(
            "tree_view",  # Changed from graph_tree_view
            "false",
            label="Tree view",
            kind="toggle",
            description="Show deps as tree in list view",
        ),
    ]
```

**Step 2: Update ntfy_inbox plugin config**

Update `src/dodo/plugins/ntfy_inbox/inbox.py` to use nested config. First check current implementation:

```bash
cat src/dodo/plugins/ntfy_inbox/inbox.py
```

Update to use `config.get_plugin_config("ntfy_inbox", "topic")` etc.

**Step 3: Update obsidian plugin config**

Update `src/dodo/plugins/obsidian/backend.py` to use nested config access.

**Step 4: Run tests**

Run: `uv run pytest -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add src/dodo/plugins/
git commit -m "refactor(plugins): migrate to nested config structure"
```

---

## Task 12: Update tests for new structure

**Files:**
- Modify: `tests/test_ai.py` (if exists)
- Modify: `tests/test_config.py`

**Step 1: Update test imports**

Find and update any tests that import from `dodo.ai` or `dodo.ai_commands`:

```bash
grep -r "from dodo.ai" tests/
grep -r "from dodo.ai_commands" tests/
```

Update imports to use `dodo.plugins.ai.*` instead.

**Step 2: Add test for get_plugin_config**

Add to `tests/test_config.py`:

```python
def test_get_plugin_config():
    """Test nested plugin config access."""
    config = Config()
    config._data = {
        "plugins": {
            "ai": {"model": "opus", "command": "test-cmd"},
            "graph": {"tree_view": "true"},
        }
    }

    assert config.get_plugin_config("ai", "model") == "opus"
    assert config.get_plugin_config("ai", "command") == "test-cmd"
    assert config.get_plugin_config("ai", "missing", "default") == "default"
    assert config.get_plugin_config("graph", "tree_view") == "true"
    assert config.get_plugin_config("unknown", "key") is None


def test_set_plugin_config():
    """Test setting nested plugin config."""
    config = Config()
    config._data = {}

    config.set_plugin_config("ai", "model", "haiku")
    assert config._data["plugins"]["ai"]["model"] == "haiku"

    config.set_plugin_config("ai", "command", "new-cmd")
    assert config._data["plugins"]["ai"]["command"] == "new-cmd"
```

**Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS

**Step 4: Commit**

```bash
git add tests/
git commit -m "test: update tests for AI plugin and nested config"
```

---

## Task 13: Rescan plugin registry

**Files:**
- None (runtime operation)

**Step 1: Rescan plugins to register the new AI plugin**

```bash
uv run python -c "from dodo.plugins import scan_and_save; from dodo.config import get_default_config_dir; scan_and_save(get_default_config_dir())"
```

**Step 2: Verify AI plugin is registered**

```bash
cat ~/.config/dodo/plugin_registry.json | grep -A5 '"ai"'
```

Expected output should show the AI plugin with its hooks.

**Step 3: Commit (if registry needs updating)**

No commit needed - registry is generated.

---

## Task 14: Run full test suite and fix any failures

**Files:**
- Various (depending on failures)

**Step 1: Run all tests**

```bash
uv run pytest -v
```

**Step 2: Fix any failures**

Address any test failures that arise from the refactoring.

**Step 3: Commit fixes**

```bash
git add -A
git commit -m "fix: address test failures from AI plugin extraction"
```

---

## Task 15: Run /post-work-review

**Step 1: Run the post-work-review skill**

Execute `/post-work-review` to have parallel subagents review the changes.
