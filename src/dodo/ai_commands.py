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
