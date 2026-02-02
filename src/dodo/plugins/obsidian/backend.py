"""Obsidian Local REST API backend."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import httpx

from dodo.models import Priority, Status, TodoItem, TodoItemView
from dodo.plugins.obsidian.formatter import (
    ObsidianDocument,
    ObsidianFormatter,
    ParsedTask,
    Section,
    format_header,
    get_section_key,
    sort_tasks,
)
from dodo.plugins.obsidian.sync import SyncManager, normalize_text


class ObsidianBackend:
    """Obsidian Local REST API backend.

    Requires: obsidian-local-rest-api plugin running.
    Docs: https://github.com/coddingtonbear/obsidian-local-rest-api
    """

    DEFAULT_API_URL = "https://localhost:27124"

    DEFAULT_VAULT_PATH = "dodo/todos.md"

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str = "",
        vault_path: str = DEFAULT_VAULT_PATH,
        project: str | None = None,
        verify_ssl: bool | None = None,
        # Formatter options
        priority_syntax: str = "symbols",
        timestamp_syntax: str = "hidden",
        tags_syntax: str = "hashtags",
        group_by_tags: bool = True,
        default_header_level: int = 3,
        sort_by: str = "priority",
        # Sync file path (optional, defaults to vault-adjacent)
        sync_file: Path | None = None,
    ):
        """Initialize Obsidian backend.

        Args:
            api_url: Obsidian REST API URL (default: https://localhost:27124)
            api_key: API key for authentication
            vault_path: Path to todo file within vault. Supports {project} template
                        for named dodos (e.g., "dodo/{project}.md" creates separate
                        files per project). Without template, all projects share one file.
            project: Project/named-dodo identifier for template resolution
            verify_ssl: Whether to verify SSL certificates. Default: True for remote
                        connections, False for localhost (Obsidian Local REST API
                        typically uses self-signed certificates on localhost).
            priority_syntax: How to display priority ("hidden", "symbols", "emoji", "dataview")
            timestamp_syntax: How to display timestamp ("hidden", "plain", "emoji", "dataview")
            tags_syntax: How to display tags ("hidden", "hashtags", "dataview")
            group_by_tags: Whether to organize tasks under headers by tag
            default_header_level: Header level for new sections (1-4)
            sort_by: Task ordering within sections
            sync_file: Path to sync file for ID mappings (defaults to ~/.dodo/obsidian-sync.json)

        Security note: When verify_ssl=False, the connection is vulnerable to
        man-in-the-middle attacks. This is acceptable for localhost connections
        but should be True for remote connections. Set DODO_OBSIDIAN_VERIFY_SSL=true
        to override the localhost auto-detection.
        """
        # Auto-detect SSL verification based on URL
        resolved_url = (api_url or self.DEFAULT_API_URL).rstrip("/")
        if verify_ssl is None:
            # Safe default: only disable SSL verification for localhost
            import os
            from urllib.parse import urlparse
            host = urlparse(resolved_url).hostname or ""
            is_localhost = host in ("localhost", "127.0.0.1", "::1")
            env_override = os.environ.get("DODO_OBSIDIAN_VERIFY_SSL", "").lower()
            if env_override in ("true", "1", "yes"):
                verify_ssl = True
            elif env_override in ("false", "0", "no"):
                verify_ssl = False
            else:
                verify_ssl = not is_localhost
        self._api_url = resolved_url
        self._api_key = api_key
        self._vault_path_template = vault_path
        self._project = project
        self._vault_path = self._resolve_vault_path(vault_path, project)
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            verify=verify_ssl,
            timeout=10.0,
        )

        # Formatter configuration
        self._formatter = ObsidianFormatter(
            priority_syntax=priority_syntax,
            timestamp_syntax=timestamp_syntax,
            tags_syntax=tags_syntax,
        )
        self._group_by_tags = group_by_tags
        self._default_header_level = default_header_level
        self._sort_by = sort_by

        # Sync manager for ID tracking
        if sync_file is None:
            sync_file = Path.home() / ".dodo" / "obsidian-sync.json"
        self._sync_manager = SyncManager(sync_file)

    def _resolve_vault_path(self, template: str, project: str | None) -> str:
        """Resolve vault path template with project name.

        If template contains {project} and project is provided, substitute it.
        If template contains {project} but no project, use 'default' as fallback.
        If template has no {project} placeholder, return as-is.
        """
        if "{project}" not in template:
            return template
        project_name = project or "default"
        return template.format(project=project_name)

    def _sort_and_render(self, doc: ObsidianDocument) -> str:
        """Sort tasks in all sections and render the document.

        Args:
            doc: The ObsidianDocument to sort and render

        Returns:
            Rendered markdown content with sorted tasks
        """
        for section in doc.sections.values():
            section.tasks = sort_tasks(section.tasks, self._sort_by)
        return doc.render(self._formatter)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def add(
        self,
        text: str,
        project: str | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
    ) -> TodoItem:
        timestamp = datetime.now()
        item_id = self._sync_manager.get_or_create_id(text)

        item = TodoItem(
            id=item_id,
            text=text,
            status=Status.PENDING,
            created_at=timestamp,
            project=project,
            priority=priority,
            tags=tags,
        )

        # Read existing content
        content = self._read_note()

        # Parse existing document
        doc = ObsidianDocument.parse(content, self._formatter) if content else ObsidianDocument()

        # Add task to appropriate section
        task = ParsedTask(
            text=text,
            status=Status.PENDING,
            priority=priority,
            tags=tags or [],
            created_at=timestamp,
        )

        if self._group_by_tags and tags:
            # Find or create section based on first tag
            section_tag = tags[0].lower()
            section_key = None

            # Look for existing section with matching tag or exact key
            for key, section in doc.sections.items():
                if section.tag == section_tag or key == section_tag:
                    section_key = key
                    break

            if section_key is None:
                # Create new section - key is the simple tag
                header = format_header(section_tag, self._default_header_level)
                section_key = section_tag
                doc.sections[section_key] = Section(tag=section_tag, header=header)

            doc.sections[section_key].tasks.append(task)
        else:
            # Add to default section
            if "_default" not in doc.sections:
                doc.sections["_default"] = Section(tag="_default", header="")
            doc.sections["_default"].tasks.append(task)

        # Write updated content (sorted)
        self._write_note(self._sort_and_render(doc))

        # Save sync data
        self._sync_manager.save()

        return item

    def list(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoItem]:
        content = self._read_note()
        items = self._parse_content(content)

        if status:
            items = [i for i in items if i.status == status]
        return items

    def get(self, id: str) -> TodoItem | None:
        return next((i for i in self.list() if i.id == id), None)

    def update(self, id: str, status: Status) -> TodoItem:
        content = self._read_note()
        doc = ObsidianDocument.parse(content, self._formatter)
        updated_item = None

        # Find and update task
        for section in doc.sections.values():
            for task in section.tasks:
                # Use legacy ID if present, otherwise use sync manager
                task_id = task.legacy_id if task.legacy_id else self._sync_manager.get_or_create_id(task.text)
                if task_id == id:
                    task.status = status
                    updated_item = TodoItem(
                        id=task_id,
                        text=task.text,
                        status=status,
                        created_at=datetime.now(),
                        completed_at=datetime.now() if status == Status.DONE else None,
                        priority=task.priority,
                        tags=task.tags if task.tags else None,
                    )
                    break
            if updated_item:
                break

        if not updated_item:
            raise KeyError(f"Todo not found: {id}")

        self._write_note(self._sort_and_render(doc))
        self._sync_manager.save()
        return updated_item

    def update_text(self, id: str, text: str) -> TodoItem:
        content = self._read_note()
        doc = ObsidianDocument.parse(content, self._formatter)
        updated_item = None

        # Find and update task
        for section in doc.sections.values():
            for task in section.tasks:
                # Use legacy ID if present, otherwise use sync manager
                task_id = task.legacy_id if task.legacy_id else self._sync_manager.get_or_create_id(task.text)
                if task_id == id:
                    # Update the sync manager with new text
                    old_normalized = normalize_text(task.text)
                    if old_normalized in self._sync_manager.ids:
                        del self._sync_manager.ids[old_normalized]
                    self._sync_manager.ids[normalize_text(text)] = id

                    task.text = text
                    task.legacy_id = None  # Clear legacy ID, now tracked in sync manager
                    updated_item = TodoItem(
                        id=id,
                        text=text,
                        status=task.status,
                        created_at=datetime.now(),
                        priority=task.priority,
                        tags=task.tags if task.tags else None,
                    )
                    break
            if updated_item:
                break

        if not updated_item:
            raise KeyError(f"Todo not found: {id}")

        self._write_note(self._sort_and_render(doc))
        self._sync_manager.save()
        return updated_item

    def update_priority(self, id: str, priority: Priority | None) -> TodoItem:
        content = self._read_note()
        doc = ObsidianDocument.parse(content, self._formatter)
        updated_item = None

        # Find and update task
        for section in doc.sections.values():
            for task in section.tasks:
                # Use legacy ID if present, otherwise use sync manager
                task_id = task.legacy_id if task.legacy_id else self._sync_manager.get_or_create_id(task.text)
                if task_id == id:
                    task.priority = priority
                    updated_item = TodoItem(
                        id=task_id,
                        text=task.text,
                        status=task.status,
                        created_at=datetime.now(),
                        priority=priority,
                        tags=task.tags if task.tags else None,
                    )
                    break
            if updated_item:
                break

        if not updated_item:
            raise KeyError(f"Todo not found: {id}")

        self._write_note(self._sort_and_render(doc))
        self._sync_manager.save()
        return updated_item

    def update_tags(self, id: str, tags: list[str] | None) -> TodoItem:
        content = self._read_note()
        doc = ObsidianDocument.parse(content, self._formatter)
        updated_item = None

        # Find and update task
        for section in doc.sections.values():
            for task in section.tasks:
                # Use legacy ID if present, otherwise use sync manager
                task_id = task.legacy_id if task.legacy_id else self._sync_manager.get_or_create_id(task.text)
                if task_id == id:
                    task.tags = tags or []
                    updated_item = TodoItem(
                        id=task_id,
                        text=task.text,
                        status=task.status,
                        created_at=datetime.now(),
                        priority=task.priority,
                        tags=tags,
                    )
                    break
            if updated_item:
                break

        if not updated_item:
            raise KeyError(f"Todo not found: {id}")

        self._write_note(self._sort_and_render(doc))
        self._sync_manager.save()
        return updated_item

    def delete(self, id: str) -> None:
        content = self._read_note()
        doc = ObsidianDocument.parse(content, self._formatter)
        found = False

        # Find and remove task
        for section in doc.sections.values():
            for i, task in enumerate(section.tasks):
                # Use legacy ID if present, otherwise use sync manager
                task_id = task.legacy_id if task.legacy_id else self._sync_manager.get_or_create_id(task.text)
                if task_id == id:
                    section.tasks.pop(i)
                    found = True
                    # Remove from sync manager
                    normalized = normalize_text(task.text)
                    if normalized in self._sync_manager.ids:
                        del self._sync_manager.ids[normalized]
                    break
            if found:
                break

        if not found:
            raise KeyError(f"Todo not found: {id}")

        self._write_note(self._sort_and_render(doc))
        self._sync_manager.save()

    def export_all(self) -> list[TodoItem]:
        """Export all todos for migration."""
        return self.list()

    def import_all(self, items: list[TodoItem]) -> tuple[int, int]:
        """Import todos. Returns (imported, skipped)."""
        existing_ids = {i.id for i in self.list()}
        imported, skipped = 0, 0
        for item in items:
            if item.id in existing_ids:
                skipped += 1
            else:
                # Use add method with the full item details
                self.add(
                    text=item.text,
                    project=item.project,
                    priority=item.priority,
                    tags=item.tags,
                )
                imported += 1
        return imported, skipped

    # REST API calls

    def _read_note(self) -> str:
        """GET /vault/{path}"""
        try:
            resp = self._client.get(f"{self._api_url}/vault/{self._vault_path}")
            if resp.status_code == 404:
                return ""
            resp.raise_for_status()
            return resp.text
        except httpx.RequestError as e:
            raise ConnectionError(f"Obsidian API error: {e}") from e

    def _write_note(self, content: str) -> None:
        """PUT /vault/{path}"""
        resp = self._client.put(
            f"{self._api_url}/vault/{self._vault_path}",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        resp.raise_for_status()

    def _append_to_note(self, line: str) -> None:
        """POST /vault/{path} with append."""
        resp = self._client.post(
            f"{self._api_url}/vault/{self._vault_path}",
            content=line + "\n",
            headers={
                "Content-Type": "text/markdown",
                "X-Append": "true",
            },
        )
        resp.raise_for_status()

    # Helper methods

    def _parse_content(self, content: str) -> list[TodoItemView]:
        """Parse content using the new formatter.

        Returns TodoItemView objects with blocked_by set based on indentation.
        Indented tasks are considered blocked by their parent (less-indented) task.
        """
        if not content:
            return []

        doc = ObsidianDocument.parse(content, self._formatter)
        items: list[TodoItemView] = []
        # Track parent stack: list of (indent_level, task_id)
        parent_stack: list[tuple[int, str]] = []

        for section in doc.sections.values():
            # Reset parent stack for each section
            parent_stack = []

            # Infer section tag to use for tasks without explicit tags
            section_tag = section.tag if section.tag != "_default" else None

            for task in section.tasks:
                # Use legacy ID if present (for backward compat), otherwise generate
                if task.legacy_id:
                    task_id = task.legacy_id
                    # Also register in sync manager for future lookups
                    normalized = normalize_text(task.text)
                    if normalized not in self._sync_manager.ids:
                        self._sync_manager.ids[normalized] = task_id
                else:
                    task_id = self._sync_manager.get_or_create_id(task.text)

                # Combine explicit task tags with section tag
                tags = list(task.tags) if task.tags else []
                if section_tag and section_tag not in [t.lower() for t in tags]:
                    tags.insert(0, section_tag)

                # Determine parent based on indentation
                # Pop parents that are at same or deeper indentation
                while parent_stack and parent_stack[-1][0] >= task.indent:
                    parent_stack.pop()

                # If there's a parent, this task is blocked by it
                blocked_by = [parent_stack[-1][1]] if parent_stack else None

                todo_item = TodoItem(
                    id=task_id,
                    text=task.text,
                    status=task.status,
                    created_at=task.created_at or datetime.now(),
                    priority=task.priority,
                    tags=tags if tags else None,
                )
                items.append(TodoItemView(item=todo_item, blocked_by=blocked_by))

                # Push this task as potential parent for subsequent indented tasks
                parent_stack.append((task.indent, task_id))

        # Persist any ID mappings created during parsing
        self._sync_manager.save()

        return items
