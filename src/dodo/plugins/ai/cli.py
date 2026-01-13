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

        # Format output
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

    # Get pending todos
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

    # Show diff
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

    # Confirm
    if not yes:
        confirm = typer.confirm("\nApply changes?", default=False)
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Apply changes
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

    # Get pending todos
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

    # Show diff
    console.print(f"\n[bold]Proposed rewrites ({len(rewrites)} of {len(items)} todos):[/bold]")
    for rewrite in rewrites:
        item = next((i for i in items if i.id == rewrite["id"]), None)
        if item:
            console.print(f"  [dim]{item.id}[/dim]:")
            console.print(f"    [red]- {item.text}[/red]")
            console.print(f"    [green]+ {rewrite['text']}[/green]")

    # Confirm
    if not yes:
        confirm = typer.confirm("\nApply changes?", default=False)
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Apply changes
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

    # Get pending todos
    items = svc.list(status=Status.PENDING)
    if not items:
        console.print("[yellow]No pending todos[/yellow]")
        return

    # Collect existing tags for context
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

    # Show diff
    console.print(f"\n[bold]Proposed tags ({len(suggestions)} of {len(items)} todos):[/bold]")
    for suggestion in suggestions:
        item = next((i for i in items if i.id == suggestion["id"]), None)
        if item:
            old_tags = " ".join(f"#{t}" for t in (item.tags or []))
            new_tags = " ".join(f"#{t}" for t in suggestion["tags"])
            console.print(f"  [dim]{item.id}[/dim]: {item.text[:30]}...")
            console.print(f"    [red]- {old_tags or '(none)'}[/red]")
            console.print(f"    [green]+ {new_tags}[/green]")

    # Confirm
    if not yes:
        confirm = typer.confirm("\nApply changes?", default=False)
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Apply changes
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

    # Read piped input if available
    piped = None
    if not sys.stdin.isatty():
        piped = sys.stdin.read()

    cfg, project_id, svc = get_service_context(global_=global_)
    ai_config = _get_ai_config(cfg)

    # Check if graph plugin is available
    backend = svc.backend
    has_graph = hasattr(backend, "add_dependency")

    # Get all todos with their current state (can be empty - we can create new ones)
    items = svc.list()

    # Build todo data including dependencies if available
    todos_data = []
    for item in items:
        data = {
            "id": item.id,
            "text": item.text,
            "status": item.status.value if item.status else "pending",
            "priority": item.priority.value if item.priority else None,
            "tags": item.tags or [],
        }
        # Include dependencies if available (graph plugin)
        if has_graph and hasattr(item, "blocked_by"):
            data["dependencies"] = item.blocked_by or []
        todos_data.append(data)

    prompt = _get_prompt(ai_config, "run", DEFAULT_RUN_PROMPT)
    # Remove dependency instructions if graph plugin not available
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

    # Build lookup for current state
    current_by_id = {t["id"]: t for t in todos_data}
    items_by_id = {item.id: item for item in items}

    # Show diff
    total_changes = len(modified) + len(to_delete) + len(to_create)
    console.print(f"\n[bold]Proposed changes ({total_changes}):[/bold]")

    for mod in modified:
        item_id = mod["id"]
        if item_id not in current_by_id:
            continue
        current = current_by_id[item_id]
        text_preview = current["text"][:40] + ("..." if len(current["text"]) > 40 else "")
        console.print(f'  [dim]{item_id}[/dim]: "{text_preview}"')

        # Show reason if provided
        if mod.get("reason"):
            console.print(f"    [italic cyan]Reason: {mod['reason']}[/italic cyan]")

        # Show field changes
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
                # Show reason for deletion
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
            # Show reason for creation
            if new_todo.get("reason"):
                console.print(f"    [italic cyan]Reason: {new_todo['reason']}[/italic cyan]")

    # Confirm
    if not yes:
        confirm = typer.confirm("\nApply changes?", default=False)
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Apply changes
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
                # Handle dependency changes
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

    # Check if graph plugin is available
    if not hasattr(backend, "add_dependency"):
        console.print(
            "[red]Error:[/red] Graph plugin required. Enable with: dodo plugins enable graph"
        )
        raise typer.Exit(1)

    # Get pending todos
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

    # Filter out invalid IDs, self-dependencies, and existing dependencies
    valid_suggestions = []
    for sug in suggestions:
        blocked_id = sug.get("blocked_id")
        blocker_id = sug.get("blocker_id")
        # Skip self-dependencies (a todo cannot block itself)
        if blocked_id == blocker_id:
            continue
        if blocked_id in items_by_id and blocker_id in items_by_id:
            # Check if dependency already exists
            existing = backend.get_blockers(blocked_id) if hasattr(backend, "get_blockers") else []
            if blocker_id not in existing:
                valid_suggestions.append(sug)

    if not valid_suggestions:
        console.print("[green]No new dependencies to add[/green]")
        return

    # Group by blocked item for display
    by_blocked: dict[str, list[str]] = {}
    for sug in valid_suggestions:
        blocked_id = sug["blocked_id"]
        blocker_id = sug["blocker_id"]
        if blocked_id not in by_blocked:
            by_blocked[blocked_id] = []
        by_blocked[blocked_id].append(blocker_id)

    # Show diff
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

    # Confirm
    if not yes:
        confirm = typer.confirm("\nApply changes?", default=False)
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Use hook to add dependencies (or fallback to direct access)
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
