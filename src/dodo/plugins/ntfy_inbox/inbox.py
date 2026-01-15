"""ntfy inbox subscription command."""

from __future__ import annotations

import json
import re
import time
import urllib.request

import typer
from rich.console import Console

console = Console()

# Priority prefixes (text-based)
PRIORITY_PREFIXES = {
    "!!!!:": "critical",
    "!!!:": "critical",
    "!!:": "high",
    "!:": "high",
    "normal:": "normal",
    "low:": "low",
    "someday:": "someday",
}

# ntfy priority header to dodo priority mapping
# None (no header) = unprioritized (null)
NTFY_PRIORITY_MAP = {
    5: "critical",  # max/urgent
    4: "high",
    3: "normal",  # default
    2: "low",
    1: "someday",  # min
}


def _parse_priority_and_tags(
    text: str, ntfy_priority: int | None = None
) -> tuple[str, str | None, list[str]]:
    """Parse priority prefix and tags from text.

    Returns: (cleaned_text, priority, tags)

    Priority sources (in order):
    1. Text prefix (!!:, !:, low:, someday:)
    2. ntfy priority header

    Tags: extracted from #hashtags in text
    """
    priority = None
    tags = []

    # Check text prefixes first
    for prefix, prio in PRIORITY_PREFIXES.items():
        if text.lower().startswith(prefix):
            priority = prio
            text = text[len(prefix) :].strip()
            break

    # Fall back to ntfy priority header
    if priority is None and ntfy_priority is not None:
        priority = NTFY_PRIORITY_MAP.get(ntfy_priority)

    # Extract tags (#tag format)
    from dodo.ui.formatting import MAX_PARSE_TAGS

    tag_matches = re.findall(r"#(\w+)", text)
    if tag_matches:
        tags = tag_matches[:MAX_PARSE_TAGS]
        # Remove tags from text
        text = re.sub(r"\s*#\w+", "", text).strip()

    return text, priority, tags


def inbox(
    global_: bool = typer.Option(False, "-g", "--global", help="Use global dodo"),
) -> None:
    """Listen for todos from ntfy.sh and add them automatically.

    By default, uses the dodo for the current directory. Use --global to force global dodo.
    """
    from dodo.config import Config
    from dodo.resolve import resolve_dodo

    cfg = Config.load()

    topic = cfg.get_plugin_config("ntfy-inbox", "topic", "")
    if not topic:
        console.print("[red]Error:[/red] ntfy-inbox topic not configured")
        console.print("[dim]Set it with: dodo config[/dim]")
        raise SystemExit(1)

    server = cfg.get_plugin_config("ntfy-inbox", "server", "https://ntfy.sh").rstrip("/")

    # Resolve default dodo at startup
    if global_:
        default_dodo_name = None
        default_dodo_label = "global"
    else:
        result = resolve_dodo(cfg, None)
        default_dodo_name = result.name
        default_dodo_label = result.name or "global"

    console.print(f"[dim]Listening for todos on {server}/{topic}...[/dim]")
    console.print(
        f"[dim]Default dodo: [cyan]{default_dodo_label}[/cyan] (set Title to override)[/dim]"
    )
    console.print(
        "[dim]Priority: !!: (critical), !: (high), normal:, low:, someday: or ntfy header 1-5.[/dim]"
    )
    console.print("[dim]Tags: #tag1 #tag2 in message text.[/dim]")
    console.print("[dim]Use 'ai:' prefix for AI processing.[/dim]")
    console.print("[dim]Press Ctrl+C to stop.[/dim]\n")

    _subscribe(topic, server, default_dodo_name)


def _subscribe(topic: str, server: str, default_dodo: str | None) -> None:
    """Subscribe with automatic reconnection."""
    retry_delay = 5

    while True:
        try:
            if not _subscribe_once(topic, server, default_dodo):
                console.print(f"[yellow]Reconnecting in {retry_delay}s...[/yellow]")
                time.sleep(retry_delay)
                continue
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped.[/dim]")
            break


def _subscribe_once(topic: str, server: str, default_dodo: str | None) -> bool:
    """Subscribe to ntfy topic and process messages. Returns False on error."""
    url = f"{server}/{topic}/json"

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            for line in response:
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                    _process_message(msg, default_dodo)
                except json.JSONDecodeError:
                    continue
    except KeyboardInterrupt:
        raise
    except Exception as e:
        console.print(f"[red]Connection error:[/red] {e}")
        return False
    return True


def _process_message(msg: dict, default_dodo: str | None) -> None:
    """Process a single ntfy message and add to dodo."""
    from dodo.config import Config
    from dodo.core import TodoService
    from dodo.models import Priority
    from dodo.resolve import resolve_dodo

    # Skip non-message events (open, keepalive, etc.)
    if msg.get("event") != "message":
        return

    text = msg.get("message", "").strip()
    if not text:
        return

    # Handle JSON-encoded message body (iOS Shortcuts workaround)
    # If message looks like {"message": "..."}, parse it
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "message" in parsed:
                text = parsed.get("message", "").strip()
                # Also check for title/priority in the JSON
                if not msg.get("title") and parsed.get("title"):
                    msg["title"] = parsed["title"]
                if not msg.get("priority") and parsed.get("priority"):
                    msg["priority"] = parsed["priority"]
        except json.JSONDecodeError:
            pass  # Not valid JSON, use as-is

    if not text:
        return

    # Title = dodo name (empty = use default)
    dodo_name = msg.get("title", "").strip() or None

    # Get ntfy priority header (1-5 scale)
    ntfy_priority = msg.get("priority")

    # Check for ai: prefix
    use_ai = False
    if text.lower().startswith("ai:"):
        use_ai = True
        text = text[3:].strip()

    if not text:
        return

    # Parse priority prefix and tags from text
    text, priority_str, tags = _parse_priority_and_tags(text, ntfy_priority)

    # Convert priority string to Priority enum
    priority = None
    if priority_str:
        try:
            priority = Priority(priority_str)
        except ValueError:
            pass

    try:
        cfg = Config.load()

        # Resolve dodo: title overrides default, otherwise use default_dodo
        if dodo_name:
            # Explicit title - resolve it
            result = resolve_dodo(cfg, dodo_name)
            if result.path:
                svc = TodoService(cfg, project_id=None, storage_path=result.path)
            else:
                svc = TodoService(cfg, result.name)
            dodo_label = result.name or "global"
            dodo_info = f" [cyan][{dodo_label}][/cyan]" if result.name else ""
        else:
            # No title - use pre-resolved default
            svc = TodoService(cfg, default_dodo)
            dodo_label = default_dodo or "global"
            dodo_info = f" [cyan][{dodo_label}][/cyan]" if default_dodo else ""
        prio_info = f" [yellow][{priority.value}][/yellow]" if priority else ""
        tags_info = f" [dim]{' '.join('#' + t for t in tags)}[/dim]" if tags else ""

        if use_ai:
            # Try to use AI plugin if enabled
            if "ai" in cfg.enabled_plugins:
                try:
                    from dodo.plugins.ai import DEFAULT_COMMAND
                    from dodo.plugins.ai.engine import run_ai
                    from dodo.plugins.ai.prompts import DEFAULT_SYS_PROMPT
                except ModuleNotFoundError:
                    console.print("[yellow]AI plugin not installed, adding as-is[/yellow]")
                    item = svc.add(text, priority=priority, tags=tags or None)
                    console.print(
                        f"[green]Added:[/green] {item.text}{prio_info}{tags_info}{dodo_info}"
                    )
                    return

                ai_command = cfg.get_plugin_config("ai", "command", DEFAULT_COMMAND)
                todo_texts = run_ai(
                    user_input=text,
                    piped_content=None,
                    command=ai_command,
                    system_prompt=DEFAULT_SYS_PROMPT,
                )
                for todo_text in todo_texts:
                    # Apply priority/tags to AI-generated items too
                    item = svc.add(todo_text, priority=priority, tags=tags or None)
                    console.print(
                        f"[green]Added:[/green] {item.text}{prio_info}{tags_info}{dodo_info}"
                    )
            else:
                console.print("[yellow]AI plugin not enabled, adding as-is[/yellow]")
                item = svc.add(text, priority=priority, tags=tags or None)
                console.print(f"[green]Added:[/green] {item.text}{prio_info}{tags_info}{dodo_info}")
        else:
            item = svc.add(text, priority=priority, tags=tags or None)
            console.print(f"[green]Added:[/green] {item.text}{prio_info}{tags_info}{dodo_info}")
    except Exception as e:
        console.print(f"[red]Error adding todo:[/red] {e}")
