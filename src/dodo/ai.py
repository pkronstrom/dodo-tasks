"""AI-assisted todo formatting."""

import json
import shlex
import subprocess

DEFAULT_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {"tasks": {"type": "array", "items": {"type": "string"}}},
        "required": ["tasks"],
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
    # Substitute placeholders
    cmd_str = (
        template.replace("{{prompt}}", prompt)
        .replace("{{system}}", system)
        .replace("{{schema}}", schema)
    )
    # Parse into argument list (handles quoting properly)
    return shlex.split(cmd_str)


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
    # Build the full prompt
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

    try:
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            import sys

            print(f"AI command failed (exit {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return []

        # Parse JSON output
        output = result.stdout.strip()
        data = json.loads(output)

        # Extract tasks from structured_output (claude --output-format json)
        if isinstance(data, dict) and "structured_output" in data:
            tasks = data["structured_output"].get("tasks", [])
        elif isinstance(data, dict) and "tasks" in data:
            tasks = data["tasks"]
        elif isinstance(data, list):
            tasks = data
        else:
            print(f"Unexpected output format. Raw: {output[:500]}", file=sys.stderr)
            return []

        todos = [str(item) for item in tasks if item]
        if not todos:
            print(f"AI returned empty list. Raw output: {output[:500]}", file=sys.stderr)
        return todos

    except subprocess.TimeoutExpired:
        import sys

        print("AI command timed out", file=sys.stderr)
        return []
    except (json.JSONDecodeError, ValueError) as e:
        import sys

        print(f"Failed to parse AI output: {e}", file=sys.stderr)
        print(f"Raw output: {result.stdout[:500]}", file=sys.stderr)
        return []
