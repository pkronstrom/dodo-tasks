"""AI-assisted todo formatting."""

import json
import subprocess

DEFAULT_SCHEMA = json.dumps(
    {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 1,
    }
)


def build_command(
    template: str,
    prompt: str,
    system: str,
    schema: str,
) -> str:
    """Build command string from template."""
    return (
        template.replace("{{prompt}}", prompt)
        .replace("{{system}}", system)
        .replace("{{schema}}", schema)
    )


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

    # Escape for shell
    escaped_prompt = full_prompt.replace("'", "'\"'\"'")
    escaped_system = system_prompt.replace("'", "'\"'\"'")

    cmd = build_command(
        template=command,
        prompt=escaped_prompt,
        system=escaped_system,
        schema=schema or DEFAULT_SCHEMA,
    )

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            return []

        # Parse JSON array from output
        output = result.stdout.strip()

        # Try to extract JSON array if there's surrounding text
        if "[" in output:
            start = output.index("[")
            end = output.rindex("]") + 1
            output = output[start:end]

        items = json.loads(output)

        if isinstance(items, list):
            return [str(item) for item in items if item]

        return []

    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        return []
