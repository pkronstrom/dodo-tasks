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
    """Escape single quotes for shell single-quoted strings.

    In shell, to include a literal ' inside '...', you do: '...'\\''...'
    (end quote, escaped single quote, start new quote)
    """
    return s.replace("'", "'\"'\"'")


def build_command(
    template: str,
    prompt: str,
    system: str,
    schema: str,
    model: str = "haiku",
) -> list[str]:
    """Build command arguments from template.

    Returns a list of arguments suitable for subprocess.run without shell=True.

    Security: All parameters are escaped for shell single-quoted strings to prevent
    command injection when the template is parsed by shlex.split().
    """
    cmd_str = (
        template.replace("{{prompt}}", _escape_single_quotes(prompt))
        .replace("{{system}}", _escape_single_quotes(system))
        .replace("{{schema}}", _escape_single_quotes(schema))
        .replace("{{model}}", _escape_single_quotes(model))
    )
    return shlex.split(cmd_str)


def _execute_ai_command(cmd_args: list[str], timeout: int = AI_COMMAND_TIMEOUT) -> str | None:
    """Execute AI command and return stdout, or None on error.

    Handles subprocess execution, timeout, and error logging.
    """
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
    """Extract result list from AI JSON output.

    Handles both direct output and claude's structured_output wrapper.
    Returns None on parse error.
    """
    try:
        data = json.loads(output)

        # Extract from structured_output (claude --output-format json)
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
    """Run AI command and return list of todo items.

    Args:
        user_input: User's text input
        command: Command template with {{prompt}}, {{system}}, {{schema}}, {{model}}
        system_prompt: System prompt for the AI
        piped_content: Optional piped stdin content
        schema: Optional JSON schema (defaults to array of strings)
        model: AI model to use (e.g., haiku, sonnet, opus)

    Returns:
        List of todo item strings, or empty list on error
    """
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
    """Run AI command and return structured result.

    Args:
        command: Command template with {{prompt}}, {{system}}, {{schema}}, {{model}}
        system_prompt: System prompt for the AI
        user_prompt: User's input prompt
        schema: JSON schema for output validation
        result_key: Key to extract from result (e.g., "tasks", "assignments")
        model: AI model to use (e.g., haiku, sonnet, opus)

    Returns:
        List of dicts from AI output, or empty list on error
    """
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

    # Build the full input
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
    """Extract todos, delete list, and create list from AI run output.

    Returns (modified_todos, delete_items, create_todos) tuple.
    Delete items are dicts with 'id' and 'reason'.
    """
    try:
        data = json.loads(output)

        # Handle structured_output wrapper
        if isinstance(data, dict) and "structured_output" in data:
            data = data["structured_output"]

        # Type guard: ensure we have a dict before accessing fields
        if not isinstance(data, dict):
            print(f"Unexpected output type: {type(data).__name__}", file=sys.stderr)
            return ([], [], [])

        todos = data.get("todos", [])
        delete = data.get("delete", [])
        create = data.get("create", [])

        # Handle both old format (list of strings) and new format (list of objects)
        delete_items = []
        for d in delete:
            if isinstance(d, str):
                # Old format: just ID
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
    """Run AI with user instruction on todos.

    Returns (modified_todos, delete_items, create_todos) tuple.
    Delete items are dicts with 'id' and 'reason'.
    """
    todos_text = "\n".join(
        f"- [{t['id']}] {t['text']} "
        f"(status: {t.get('status', 'pending')}, "
        f"priority: {t.get('priority', 'none')}, "
        f"tags: {t.get('tags', [])}, "
        f"deps: {t.get('dependencies', [])})"
        for t in todos
    )

    # Build full instruction with piped content
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
