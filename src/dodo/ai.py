"""AI-assisted todo formatting."""

import json
import shlex
import subprocess
import sys
from typing import Any

# Constants - can be overridden via config
AI_COMMAND_TIMEOUT = 60  # seconds

DEFAULT_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {"tasks": {"type": "array", "items": {"type": "string"}}},
        "required": ["tasks"],
    }
)

# Schema for AI add with priority/tags
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

# Schema for priority assignment
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

# Schema for tag suggestions
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

# Schema for reword suggestions
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


def build_command(
    template: str,
    prompt: str,
    system: str,
    schema: str,
) -> list[str]:
    """Build command arguments from template.

    Returns a list of arguments suitable for subprocess.run without shell=True.
    """
    cmd_str = (
        template.replace("{{prompt}}", prompt)
        .replace("{{system}}", system)
        .replace("{{schema}}", schema)
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
) -> list[str]:
    """Run AI command and return list of todo items.

    Args:
        user_input: User's text input
        command: Command template with {{prompt}}, {{system}}, {{schema}}
        system_prompt: System prompt for the AI
        piped_content: Optional piped stdin content
        schema: Optional JSON schema (defaults to array of strings)

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
) -> list[dict]:
    """Run AI command and return structured result.

    Args:
        command: Command template with {{prompt}}, {{system}}, {{schema}}
        system_prompt: System prompt for the AI
        user_prompt: User's input prompt
        schema: JSON schema for output validation
        result_key: Key to extract from result (e.g., "tasks", "assignments")

    Returns:
        List of dicts from AI output, or empty list on error
    """
    cmd_args = build_command(
        template=command,
        prompt=user_prompt,
        system=system_prompt,
        schema=schema,
    )

    output = _execute_ai_command(cmd_args)
    if output is None:
        return []

    items = _extract_ai_result(output, result_key)
    if items is None:
        return []

    return [item for item in items if isinstance(item, dict)]


# Default prompts for AI operations
DEFAULT_ADD_PROMPT = """Convert user input into a JSON array of todo objects.
For each task:
- Write clear, concise text (imperative mood: "Fix X", "Add Y")
- Infer priority only if clearly indicated (urgent/critical/blocking = critical, nice-to-have/someday = low/someday). Default to null.
- Infer tags from context (technology, area, type). Use existing tags when relevant: {existing_tags}

Output ONLY the JSON object with tasks array, nothing else.
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


def run_ai_add(
    user_input: str,
    command: str,
    system_prompt: str,
    existing_tags: list[str] | None = None,
    piped_content: str | None = None,
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
    )


def run_ai_tag(
    todos: list[dict],
    command: str,
    system_prompt: str,
    existing_tags: list[str] | None = None,
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
    )


def run_ai_reword(
    todos: list[dict],
    command: str,
    system_prompt: str,
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
    )
