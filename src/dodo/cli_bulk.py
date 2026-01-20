"""Bulk CLI commands."""

from __future__ import annotations

import sys
from typing import Annotated

import typer
from rich.console import Console

console = Console()

bulk_app = typer.Typer(
    name="bulk",
    help="Bulk operations on todos.",
    no_args_is_help=True,
)


def _get_config():
    from dodo.config import Config
    return Config.load()


def _resolve_dodo(config, dodo_name=None, global_=False):
    from dodo.resolve import resolve_dodo
    result = resolve_dodo(config, dodo_name, global_)
    return result.name, result.path


def _get_service(config, project_id):
    from dodo.core import TodoService
    return TodoService(config, project_id)


def _get_service_with_path(config, path):
    from dodo.core import TodoService
    return TodoService(config, project_id=None, storage_path=path)


def _get_ids_from_input(args: list[str]) -> list[str]:
    """Get IDs from args or stdin."""
    from dodo.bulk import parse_bulk_args, parse_bulk_input

    if args:
        return parse_bulk_args(args).items

    # Read from stdin if no args
    if not sys.stdin.isatty():
        text = sys.stdin.read()
        result = parse_bulk_input(text)
        # For non-JSONL input, items are IDs
        if result.items and isinstance(result.items[0], str):
            return result.items
        # For JSONL, extract IDs
        return [item.get("id") for item in result.items if item.get("id")]

    return []


def _save_bulk_undo(action: str, items: list, target: str):
    """Save undo state for bulk operation."""
    import json
    from dodo.config import Config

    cfg = Config.load()
    state_file = cfg.config_dir / ".last_action"
    state_file.parent.mkdir(parents=True, exist_ok=True)

    # Convert TodoItem objects to dicts
    items_data = []
    for item in items:
        if hasattr(item, "to_dict"):
            items_data.append(item.to_dict())
        elif isinstance(item, dict):
            items_data.append(item)

    state_file.write_text(json.dumps({
        "action": action,
        "target": target,
        "items": items_data,
    }))


@bulk_app.command()
def done(
    ids: Annotated[list[str] | None, typer.Argument(help="Todo IDs")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo")] = None,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Only output IDs")] = False,
):
    """Mark multiple todos as done."""
    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    target = dodo_id or "global"
    id_list = _get_ids_from_input(ids or [])

    if not id_list:
        console.print("[yellow]No IDs provided[/yellow]")
        raise typer.Exit(1)

    # Store snapshots for undo
    snapshots = []
    completed = 0

    for id_ in id_list:
        item = svc.get(id_)
        if item:
            snapshots.append(item)
            svc.complete(id_)
            completed += 1
            if quiet:
                console.print(id_)
            else:
                console.print(f"[green]✓[/green] {id_}: {item.text[:50]}")
        else:
            if not quiet:
                console.print(f"[yellow]![/yellow] {id_}: not found")

    if snapshots:
        _save_bulk_undo("done", snapshots, target)

    if not quiet:
        console.print(f"[dim]Completed {completed} todos[/dim]")


@bulk_app.command()
def rm(
    ids: Annotated[list[str] | None, typer.Argument(help="Todo IDs")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo")] = None,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Only output IDs")] = False,
):
    """Remove multiple todos."""
    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    target = dodo_id or "global"
    id_list = _get_ids_from_input(ids or [])

    if not id_list:
        console.print("[yellow]No IDs provided[/yellow]")
        raise typer.Exit(1)

    # Store snapshots for undo
    snapshots = []
    removed = 0

    for id_ in id_list:
        item = svc.get(id_)
        if item:
            snapshots.append(item)
            svc.delete(id_)
            removed += 1
            if quiet:
                console.print(id_)
            else:
                console.print(f"[yellow]✓[/yellow] {id_}: {item.text[:50]}")
        else:
            if not quiet:
                console.print(f"[yellow]![/yellow] {id_}: not found")

    if snapshots:
        _save_bulk_undo("rm", snapshots, target)

    if not quiet:
        console.print(f"[dim]Removed {removed} todos[/dim]")


@bulk_app.command()
def remove(
    ids: Annotated[list[str] | None, typer.Argument(help="Todo IDs")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo")] = None,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Only output IDs")] = False,
):
    """Remove multiple todos (alias for rm)."""
    rm(ids, global_, dodo, quiet)


@bulk_app.command()
def add(
    global_: Annotated[bool, typer.Option("-g", "--global", help="Force global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Only output IDs")] = False,
):
    """Bulk add todos from JSONL stdin."""
    from dodo.models import Priority

    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    target = dodo_id or "global"

    if sys.stdin.isatty():
        console.print("[yellow]No input provided. Pipe JSONL to stdin.[/yellow]")
        raise typer.Exit(1)

    text = sys.stdin.read().strip()
    if not text:
        console.print("[yellow]Empty input[/yellow]")
        raise typer.Exit(1)

    from dodo.bulk import parse_bulk_input
    result = parse_bulk_input(text)

    added_items = []
    prev_id = None
    errors = 0

    for data in result.items:
        if not isinstance(data, dict):
            errors += 1
            continue

        item_text = data.get("text", "")
        if not item_text:
            errors += 1
            continue

        # Replace $prev placeholder
        if prev_id and "$prev" in item_text:
            item_text = item_text.replace("$prev", prev_id)

        # Parse priority
        parsed_priority = None
        if prio_str := data.get("priority"):
            try:
                parsed_priority = Priority(prio_str.lower())
            except ValueError:
                pass

        # Parse tags
        parsed_tags = data.get("tags")
        if parsed_tags and not isinstance(parsed_tags, list):
            parsed_tags = None

        item = svc.add(item_text, priority=parsed_priority, tags=parsed_tags)
        added_items.append(item)
        prev_id = item.id

        if quiet:
            console.print(item.id)
        else:
            console.print(f"[green]✓[/green] {item.id}: {item.text[:50]}")

    if added_items:
        _save_bulk_undo("add", added_items, target)

    if not quiet:
        console.print(f"[dim]Added {len(added_items)} todos ({errors} errors)[/dim]")


@bulk_app.command()
def edit(
    ids: Annotated[list[str] | None, typer.Argument(help="Todo IDs")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global", help="Use global list")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo")] = None,
    priority: Annotated[str | None, typer.Option("-p", "--priority", help="Set priority")] = None,
    tag: Annotated[list[str] | None, typer.Option("-t", "--tag", help="Set tags")] = None,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Only output IDs")] = False,
):
    """Edit multiple todos.

    With args: applies same changes to all IDs.
    With stdin JSONL: applies per-item changes (partial updates).
    """
    from dodo.models import Priority

    cfg = _get_config()
    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    target = dodo_id or "global"
    snapshots = []
    edited = 0

    # Mode 1: IDs as args with flags
    if ids:
        if not priority and not tag:
            console.print("[yellow]No changes specified. Use -p or -t flags.[/yellow]")
            raise typer.Exit(1)

        parsed_priority = None
        if priority:
            try:
                parsed_priority = Priority(priority.lower())
            except ValueError:
                console.print(f"[red]Error:[/red] Invalid priority '{priority}'")
                raise typer.Exit(1)

        parsed_tags = None
        if tag:
            parsed_tags = []
            for t in tag:
                parsed_tags.extend(x.strip() for x in t.split(",") if x.strip())

        for id_ in ids:
            item = svc.get(id_)
            if item:
                snapshots.append(item)
                if parsed_priority is not None:
                    svc.update_priority(id_, parsed_priority)
                if parsed_tags is not None:
                    svc.update_tags(id_, parsed_tags)
                edited += 1
                if quiet:
                    console.print(id_)
                else:
                    console.print(f"[green]✓[/green] {id_}: updated")
            else:
                if not quiet:
                    console.print(f"[yellow]![/yellow] {id_}: not found")

    # Mode 2: JSONL from stdin
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
        if not text:
            console.print("[yellow]Empty input[/yellow]")
            raise typer.Exit(1)

        from dodo.bulk import parse_bulk_input
        result = parse_bulk_input(text)

        for data in result.items:
            if not isinstance(data, dict):
                continue

            id_ = data.get("id")
            if not id_:
                continue

            item = svc.get(id_)
            if not item:
                if not quiet:
                    console.print(f"[yellow]![/yellow] {id_}: not found")
                continue

            snapshots.append(item)

            # Update priority if present (null clears)
            if "priority" in data:
                prio_val = data["priority"]
                if prio_val is None:
                    svc.update_priority(id_, None)
                else:
                    try:
                        svc.update_priority(id_, Priority(prio_val.lower()))
                    except ValueError:
                        pass

            # Update tags if present (null clears)
            if "tags" in data:
                tags_val = data["tags"]
                if tags_val is None:
                    svc.update_tags(id_, None)
                elif isinstance(tags_val, list):
                    svc.update_tags(id_, tags_val)

            # Update text if present
            if "text" in data and data["text"]:
                svc.update_text(id_, data["text"])

            edited += 1
            if quiet:
                console.print(id_)
            else:
                console.print(f"[green]✓[/green] {id_}: updated")

    else:
        console.print("[yellow]Provide IDs as arguments or pipe JSONL to stdin.[/yellow]")
        raise typer.Exit(1)

    if snapshots:
        _save_bulk_undo("edit", snapshots, target)

    if not quiet:
        console.print(f"[dim]Edited {edited} todos[/dim]")
