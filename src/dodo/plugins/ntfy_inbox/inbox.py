"""ntfy inbox subscription command."""

from __future__ import annotations

import json
import time
import urllib.request

from rich.console import Console

console = Console()


def inbox() -> None:
    """Listen for todos from ntfy.sh and add them automatically."""
    from dodo.config import Config

    cfg = Config.load()

    topic = cfg.get_plugin_config("ntfy-inbox", "topic", "")
    if not topic:
        console.print("[red]Error:[/red] ntfy-inbox topic not configured")
        console.print("[dim]Set it with: dodo config[/dim]")
        raise SystemExit(1)

    server = cfg.get_plugin_config("ntfy-inbox", "server", "https://ntfy.sh").rstrip("/")

    console.print(f"[dim]Listening for todos on {server}/{topic}...[/dim]")
    console.print("[dim]Send messages to add todos. Use 'ai:' prefix for AI processing.[/dim]")
    console.print("[dim]Press Ctrl+C to stop.[/dim]\n")

    _subscribe(topic, server)


def _subscribe(topic: str, server: str) -> None:
    """Subscribe with automatic reconnection."""
    retry_delay = 5

    while True:
        try:
            if not _subscribe_once(topic, server):
                console.print(f"[yellow]Reconnecting in {retry_delay}s...[/yellow]")
                time.sleep(retry_delay)
                continue
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped.[/dim]")
            break


def _subscribe_once(topic: str, server: str) -> bool:
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
                    _process_message(msg)
                except json.JSONDecodeError:
                    continue
    except KeyboardInterrupt:
        raise
    except Exception as e:
        console.print(f"[red]Connection error:[/red] {e}")
        return False
    return True


def _process_message(msg: dict) -> None:
    """Process a single ntfy message and add to dodo."""
    from dodo.config import Config
    from dodo.core import TodoService

    # Skip non-message events (open, keepalive, etc.)
    if msg.get("event") != "message":
        return

    text = msg.get("message", "").strip()
    if not text:
        return

    # Title = project name (empty = global)
    project = msg.get("title", "").strip() or None

    # Check for ai: prefix
    use_ai = False
    if text.lower().startswith("ai:"):
        use_ai = True
        text = text[3:].strip()

    if not text:
        return

    try:
        cfg = Config.load()
        svc = TodoService(cfg, project)
        proj_info = f" [cyan][{project}][/cyan]" if project else ""

        if use_ai:
            # Try to use AI plugin if enabled
            if "ai" in cfg.enabled_plugins:
                try:
                    from dodo.plugins.ai import DEFAULT_COMMAND
                    from dodo.plugins.ai.engine import run_ai
                    from dodo.plugins.ai.prompts import DEFAULT_SYS_PROMPT
                except ModuleNotFoundError:
                    console.print("[yellow]AI plugin not installed, adding as-is[/yellow]")
                    item = svc.add(text)
                    console.print(f"[green]Added:[/green] {item.text}{proj_info}")
                    return

                ai_command = cfg.get_plugin_config("ai", "command", DEFAULT_COMMAND)
                todo_texts = run_ai(
                    user_input=text,
                    piped_content=None,
                    command=ai_command,
                    system_prompt=DEFAULT_SYS_PROMPT,
                )
                for todo_text in todo_texts:
                    item = svc.add(todo_text)
                    console.print(f"[green]Added:[/green] {item.text}{proj_info}")
            else:
                console.print("[yellow]AI plugin not enabled, adding as-is[/yellow]")
                item = svc.add(text)
                console.print(f"[green]Added:[/green] {item.text}{proj_info}")
        else:
            item = svc.add(text)
            console.print(f"[green]Added:[/green] {item.text}{proj_info}")
    except Exception as e:
        console.print(f"[red]Error adding todo:[/red] {e}")
