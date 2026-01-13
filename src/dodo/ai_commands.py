"""AI-assisted todo management commands."""

import sys
from typing import Annotated

import typer
from rich.console import Console

ai_app = typer.Typer(
    name="ai",
    help="AI-assisted todo management.",
)

console = Console()


def _get_prompt(cfg, key: str, default: str) -> str:
    """Get prompt from config or use default."""
    custom = getattr(cfg, key, "")
    return custom if custom else default


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
    from dodo.ai import DEFAULT_ADD_PROMPT, run_ai_add
    from dodo.cli_context import get_service_context
    from dodo.models import Priority

    piped = None
    if not sys.stdin.isatty():
        piped = sys.stdin.read()

    if not text and not piped:
        console.print("[red]Error:[/red] Provide text or pipe input")
        raise typer.Exit(1)

    cfg, project_id, svc = get_service_context(global_=global_)

    # Get existing tags for context
    existing_items = svc.list()
    existing_tags: set[str] = set()
    for item in existing_items:
        if item.tags:
            existing_tags.update(item.tags)

    prompt = _get_prompt(cfg, "ai_add_prompt", DEFAULT_ADD_PROMPT)

    _print_waiting("Creating todos")
    tasks = run_ai_add(
        user_input=text or "",
        piped_content=piped,
        command=cfg.ai_command,
        system_prompt=prompt,
        existing_tags=list(existing_tags),
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
    from dodo.ai import DEFAULT_PRIORITIZE_PROMPT, run_ai_prioritize
    from dodo.cli_context import get_service_context
    from dodo.models import Priority, Status

    cfg, project_id, svc = get_service_context(global_=global_)

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

    prompt = _get_prompt(cfg, "ai_prioritize_prompt", DEFAULT_PRIORITIZE_PROMPT)

    _print_waiting("Analyzing priorities")
    assignments = run_ai_prioritize(
        todos=todos_data,
        command=cfg.ai_command,
        system_prompt=prompt,
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
    from dodo.ai import DEFAULT_REWORD_PROMPT, run_ai_reword
    from dodo.cli_context import get_service_context
    from dodo.models import Status

    cfg, project_id, svc = get_service_context(global_=global_)

    # Get pending todos
    items = svc.list(status=Status.PENDING)
    if not items:
        console.print("[yellow]No pending todos[/yellow]")
        return

    todos_data = [{"id": item.id, "text": item.text} for item in items]

    prompt = _get_prompt(cfg, "ai_reword_prompt", DEFAULT_REWORD_PROMPT)

    _print_waiting("Improving descriptions")
    rewrites = run_ai_reword(
        todos=todos_data,
        command=cfg.ai_command,
        system_prompt=prompt,
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
    from dodo.ai import DEFAULT_TAG_PROMPT, run_ai_tag
    from dodo.cli_context import get_service_context
    from dodo.models import Status

    cfg, project_id, svc = get_service_context(global_=global_)

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

    prompt = _get_prompt(cfg, "ai_tag_prompt", DEFAULT_TAG_PROMPT)

    _print_waiting("Suggesting tags")
    suggestions = run_ai_tag(
        todos=todos_data,
        command=cfg.ai_command,
        system_prompt=prompt,
        existing_tags=list(existing_tags),
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
    """Execute natural language instructions on todos."""
    from dodo.ai import DEFAULT_RUN_PROMPT, run_ai_run
    from dodo.cli_context import get_service_context
    from dodo.models import Priority, Status

    cfg, project_id, svc = get_service_context(global_=global_)

    # Get all todos with their current state
    items = svc.list()
    if not items:
        console.print("[yellow]No todos to modify[/yellow]")
        return

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
        if hasattr(item, "blocked_by"):
            data["dependencies"] = item.blocked_by or []
        todos_data.append(data)

    prompt = _get_prompt(cfg, "ai_run_prompt", DEFAULT_RUN_PROMPT)

    _print_waiting("Processing instruction")
    modified, to_delete = run_ai_run(
        todos=todos_data,
        instruction=instruction,
        command=cfg.ai_command,
        system_prompt=prompt,
    )

    if not modified and not to_delete:
        console.print("[green]No changes needed[/green]")
        return

    # Build lookup for current state
    current_by_id = {t["id"]: t for t in todos_data}
    items_by_id = {item.id: item for item in items}

    # Show diff
    total_changes = len(modified) + len(to_delete)
    console.print(f"\n[bold]Proposed changes ({total_changes}):[/bold]")

    for mod in modified:
        item_id = mod["id"]
        if item_id not in current_by_id:
            continue
        current = current_by_id[item_id]
        item = items_by_id.get(item_id)
        text_preview = current["text"][:40] + ("..." if len(current["text"]) > 40 else "")
        console.print(f'  [dim]{item_id}[/dim]: "{text_preview}"')

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
        for del_id in to_delete:
            item = items_by_id.get(del_id)
            if item:
                console.print(f'  [red]x[/red] [dim]{del_id}[/dim]: "{item.text}"')

    # Confirm
    if not yes:
        confirm = typer.confirm("\nApply changes?", default=False)
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Apply changes
    applied = 0
    backend = svc.backend

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

    for del_id in to_delete:
        try:
            svc.delete(del_id)
            applied += 1
        except KeyError as e:
            console.print(f"[red]Failed to delete {del_id}: {e}[/red]")

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
    from dodo.ai import DEFAULT_DEP_PROMPT, run_ai_dep
    from dodo.cli_context import get_service_context
    from dodo.models import Status

    cfg, project_id, svc = get_service_context(global_=global_)
    backend = svc.backend

    # Check if graph plugin is available
    if not hasattr(backend, "add_dependency"):
        console.print(
            "[red]Error:[/red] Graph plugin not enabled. Run: dodo config set enabled_plugins graph"
        )
        raise typer.Exit(1)

    # Get pending todos
    items = svc.list(status=Status.PENDING)
    if not items:
        console.print("[yellow]No pending todos[/yellow]")
        return

    todos_data = [{"id": item.id, "text": item.text} for item in items]
    items_by_id = {item.id: item for item in items}

    prompt = _get_prompt(cfg, "ai_dep_prompt", DEFAULT_DEP_PROMPT)

    _print_waiting("Analyzing dependencies")
    suggestions = run_ai_dep(
        todos=todos_data,
        command=cfg.ai_command,
        system_prompt=prompt,
    )

    if not suggestions:
        console.print("[green]No dependencies detected[/green]")
        return

    # Filter out invalid IDs and existing dependencies
    valid_suggestions = []
    for sug in suggestions:
        blocked_id = sug.get("blocked_id")
        blocker_id = sug.get("blocker_id")
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

    # Apply changes
    applied = 0
    for sug in valid_suggestions:
        try:
            backend.add_dependency(sug["blocker_id"], sug["blocked_id"])
            applied += 1
        except Exception as e:
            console.print(f"[red]Failed to add dependency: {e}[/red]")

    console.print(f"[green]+[/green] Added {applied} dependencies")
