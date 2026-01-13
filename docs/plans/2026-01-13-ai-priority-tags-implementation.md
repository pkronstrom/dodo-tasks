# AI Priority & Tags Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add priority and tags fields to todos, sorting/filtering to list, and expand `dodo ai` to a command group with prioritize, reword, tag, and sync subcommands.

**Architecture:** Extend TodoItem dataclass with optional priority/tags fields. Update SQLite schema with migration. Modify markdown parser to handle `!priority` and `#tag` syntax. Create ai.py subcommand handlers with configurable prompts.

**Tech Stack:** Python 3.11+, Typer CLI, SQLite, regex for markdown parsing

---

## Task 1: Add Priority Enum to Models

**Files:**
- Modify: `src/dodo/models.py`
- Test: `tests/test_models.py`

**Step 1: Write the failing test**

```python
# tests/test_models.py - add to existing file

from dodo.models import Priority


class TestPriority:
    def test_priority_values(self):
        assert Priority.CRITICAL.value == "critical"
        assert Priority.HIGH.value == "high"
        assert Priority.NORMAL.value == "normal"
        assert Priority.LOW.value == "low"
        assert Priority.SOMEDAY.value == "someday"

    def test_priority_sort_order(self):
        # critical > high > normal > low > someday
        assert Priority.CRITICAL.sort_order == 5
        assert Priority.HIGH.sort_order == 4
        assert Priority.NORMAL.sort_order == 3
        assert Priority.LOW.sort_order == 2
        assert Priority.SOMEDAY.sort_order == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py::TestPriority -v`
Expected: FAIL with "cannot import name 'Priority'"

**Step 3: Write minimal implementation**

```python
# src/dodo/models.py - add after Status enum

class Priority(Enum):
    """Todo priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    SOMEDAY = "someday"

    @property
    def sort_order(self) -> int:
        """Higher number = higher priority for sorting."""
        return {
            Priority.CRITICAL: 5,
            Priority.HIGH: 4,
            Priority.NORMAL: 3,
            Priority.LOW: 2,
            Priority.SOMEDAY: 1,
        }[self]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py::TestPriority -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/models.py tests/test_models.py
git commit -m "feat(models): add Priority enum with sort order"
```

---

## Task 2: Extend TodoItem with Priority and Tags

**Files:**
- Modify: `src/dodo/models.py`
- Test: `tests/test_models.py`

**Step 1: Write the failing test**

```python
# tests/test_models.py - add to TestTodoItem class or create new

class TestTodoItemPriorityTags:
    def test_todoitem_with_priority(self):
        from datetime import datetime
        from dodo.models import Priority, Status, TodoItem

        item = TodoItem(
            id="abc12345",
            text="Test",
            status=Status.PENDING,
            created_at=datetime.now(),
            priority=Priority.HIGH,
        )
        assert item.priority == Priority.HIGH

    def test_todoitem_with_tags(self):
        from datetime import datetime
        from dodo.models import Status, TodoItem

        item = TodoItem(
            id="abc12345",
            text="Test",
            status=Status.PENDING,
            created_at=datetime.now(),
            tags=["backend", "urgent"],
        )
        assert item.tags == ["backend", "urgent"]

    def test_todoitem_defaults_none(self):
        from datetime import datetime
        from dodo.models import Status, TodoItem

        item = TodoItem(
            id="abc12345",
            text="Test",
            status=Status.PENDING,
            created_at=datetime.now(),
        )
        assert item.priority is None
        assert item.tags is None

    def test_todoitem_to_dict_includes_priority_tags(self):
        from datetime import datetime
        from dodo.models import Priority, Status, TodoItem

        item = TodoItem(
            id="abc12345",
            text="Test",
            status=Status.PENDING,
            created_at=datetime.now(),
            priority=Priority.HIGH,
            tags=["api"],
        )
        d = item.to_dict()
        assert d["priority"] == "high"
        assert d["tags"] == ["api"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py::TestTodoItemPriorityTags -v`
Expected: FAIL with "unexpected keyword argument 'priority'"

**Step 3: Write minimal implementation**

```python
# src/dodo/models.py - modify TodoItem dataclass

@dataclass(frozen=True)
class TodoItem:
    """Immutable todo item."""

    id: str
    text: str
    status: Status
    created_at: datetime
    completed_at: datetime | None = None
    project: str | None = None
    priority: Priority | None = None
    tags: list[str] | None = None

    def to_dict(self) -> dict:
        """Serialize to dict for formatters."""
        return {
            "id": self.id,
            "text": self.text,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "project": self.project,
            "priority": self.priority.value if self.priority else None,
            "tags": self.tags,
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py::TestTodoItemPriorityTags -v`
Expected: PASS

**Step 5: Also update TodoItemView to expose priority/tags**

```python
# src/dodo/models.py - add to TodoItemView class

    @property
    def priority(self) -> Priority | None:
        return self.item.priority

    @property
    def tags(self) -> list[str] | None:
        return self.item.tags
```

And update `to_dict`:

```python
    def to_dict(self) -> dict:
        """Serialize to dict, including extension fields."""
        d = self.item.to_dict()
        if self.blocked_by is not None:
            d["blocked_by"] = self.blocked_by
        return d
```

**Step 6: Run all model tests**

Run: `pytest tests/test_models.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add src/dodo/models.py tests/test_models.py
git commit -m "feat(models): add priority and tags fields to TodoItem"
```

---

## Task 3: Update SQLite Backend Schema

**Files:**
- Modify: `src/dodo/backends/sqlite.py`
- Test: `tests/test_backends/test_sqlite.py`

**Step 1: Write the failing test**

```python
# tests/test_backends/test_sqlite.py - add new test class

class TestSqliteBackendPriorityTags:
    def test_add_with_priority(self, tmp_path: Path):
        from dodo.models import Priority
        backend = SqliteBackend(tmp_path / "dodo.db")

        item = backend.add("Test", priority=Priority.HIGH)

        assert item.priority == Priority.HIGH
        # Verify persisted
        retrieved = backend.get(item.id)
        assert retrieved.priority == Priority.HIGH

    def test_add_with_tags(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")

        item = backend.add("Test", tags=["backend", "api"])

        assert item.tags == ["backend", "api"]
        retrieved = backend.get(item.id)
        assert retrieved.tags == ["backend", "api"]

    def test_add_defaults_none(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")

        item = backend.add("Test")

        assert item.priority is None
        assert item.tags is None

    def test_update_priority(self, tmp_path: Path):
        from dodo.models import Priority
        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("Test")

        updated = backend.update_priority(item.id, Priority.CRITICAL)

        assert updated.priority == Priority.CRITICAL

    def test_update_tags(self, tmp_path: Path):
        backend = SqliteBackend(tmp_path / "dodo.db")
        item = backend.add("Test")

        updated = backend.update_tags(item.id, ["new-tag"])

        assert updated.tags == ["new-tag"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_backends/test_sqlite.py::TestSqliteBackendPriorityTags -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/dodo/backends/sqlite.py - update SCHEMA

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS todos (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            project TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            priority TEXT,
            tags TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_project ON todos(project);
        CREATE INDEX IF NOT EXISTS idx_status ON todos(status);
        CREATE INDEX IF NOT EXISTS idx_priority ON todos(priority);
    """

    MIGRATIONS = [
        # Migration 1: Add priority and tags columns
        """
        ALTER TABLE todos ADD COLUMN priority TEXT;
        ALTER TABLE todos ADD COLUMN tags TEXT;
        CREATE INDEX IF NOT EXISTS idx_priority ON todos(priority);
        """,
    ]
```

Update `_ensure_schema` to run migrations:

```python
    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)
            self._run_migrations(conn)

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        """Run any pending migrations."""
        # Check if priority column exists
        cursor = conn.execute("PRAGMA table_info(todos)")
        columns = {row[1] for row in cursor.fetchall()}

        if "priority" not in columns:
            # Run migration - split statements since ALTER TABLE can't be batched
            conn.execute("ALTER TABLE todos ADD COLUMN priority TEXT")
            conn.execute("ALTER TABLE todos ADD COLUMN tags TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_priority ON todos(priority)")
```

Update `add` method:

```python
    def add(
        self,
        text: str,
        project: str | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
    ) -> TodoItem:
        item = TodoItem(
            id=uuid.uuid4().hex[:8],
            text=text,
            status=Status.PENDING,
            created_at=datetime.now(),
            project=project,
            priority=priority,
            tags=tags,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO todos (id, text, status, project, created_at, priority, tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    item.id,
                    item.text,
                    item.status.value,
                    item.project,
                    item.created_at.isoformat(),
                    item.priority.value if item.priority else None,
                    json.dumps(item.tags) if item.tags else None,
                ),
            )
        return item
```

Add import at top:

```python
import json
```

Update `_row_to_item`:

```python
    def _row_to_item(self, row: tuple) -> TodoItem:
        id, text, status, project, created_at, completed_at, priority, tags = row
        return TodoItem(
            id=id,
            text=text,
            status=Status(status),
            project=project,
            created_at=datetime.fromisoformat(created_at),
            completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
            priority=Priority(priority) if priority else None,
            tags=json.loads(tags) if tags else None,
        )
```

Update SELECT queries to include new columns:

```python
    def list(self, ...) -> list[TodoItem]:
        query = "SELECT id, text, status, project, created_at, completed_at, priority, tags FROM todos WHERE 1=1"
        # ... rest unchanged

    def get(self, id: str) -> TodoItem | None:
        query = """
            SELECT id, text, status, project, created_at, completed_at, priority, tags
            FROM todos WHERE id = ?
        """
        # ... rest unchanged
```

Add update methods:

```python
    def update_priority(self, id: str, priority: Priority | None) -> TodoItem:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE todos SET priority = ? WHERE id = ?",
                (priority.value if priority else None, id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Todo not found: {id}")

        item = self.get(id)
        if not item:
            raise KeyError(f"Todo not found: {id}")
        return item

    def update_tags(self, id: str, tags: list[str] | None) -> TodoItem:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE todos SET tags = ? WHERE id = ?",
                (json.dumps(tags) if tags else None, id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Todo not found: {id}")

        item = self.get(id)
        if not item:
            raise KeyError(f"Todo not found: {id}")
        return item
```

Add Priority import:

```python
from dodo.models import Priority, Status, TodoItem
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_backends/test_sqlite.py::TestSqliteBackendPriorityTags -v`
Expected: PASS

**Step 5: Run all sqlite tests to check for regressions**

Run: `pytest tests/test_backends/test_sqlite.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/dodo/backends/sqlite.py tests/test_backends/test_sqlite.py
git commit -m "feat(sqlite): add priority and tags columns with migration"
```

---

## Task 4: Update Backend Protocol

**Files:**
- Modify: `src/dodo/backends/base.py`
- Test: `tests/test_backends/test_base.py`

**Step 1: Update the protocol**

```python
# src/dodo/backends/base.py - update TodoBackend protocol

from dodo.models import Priority, Status, TodoItem


@runtime_checkable
class TodoBackend(Protocol):
    """Protocol for todo storage backends."""

    def add(
        self,
        text: str,
        project: str | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
    ) -> TodoItem:
        """Create a new todo item."""
        ...

    def list(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoItem]:
        """List todos, optionally filtered."""
        ...

    def get(self, id: str) -> TodoItem | None:
        """Get single todo by ID."""
        ...

    def update(self, id: str, status: Status) -> TodoItem:
        """Update todo status."""
        ...

    def update_text(self, id: str, text: str) -> TodoItem:
        """Update todo text."""
        ...

    def update_priority(self, id: str, priority: Priority | None) -> TodoItem:
        """Update todo priority."""
        ...

    def update_tags(self, id: str, tags: list[str] | None) -> TodoItem:
        """Update todo tags."""
        ...

    def delete(self, id: str) -> None:
        """Delete a todo."""
        ...
```

**Step 2: Run existing tests**

Run: `pytest tests/test_backends/ -v`
Expected: PASS (protocol is just a type hint)

**Step 3: Commit**

```bash
git add src/dodo/backends/base.py
git commit -m "feat(backends): update protocol with priority/tags methods"
```

---

## Task 5: Update Markdown Backend - Parsing

**Files:**
- Modify: `src/dodo/backends/utils.py`
- Test: `tests/test_backends/test_utils.py`

**Step 1: Write the failing test**

```python
# tests/test_backends/test_utils.py - add new tests

from dodo.backends.utils import parse_todo_line, format_todo_line
from dodo.models import Priority, Status, TodoItem
from datetime import datetime


class TestParseTodoLinePriorityTags:
    def test_parse_with_priority(self):
        line = "- [ ] 2024-01-15 10:30 [abc12345] - Fix bug !critical"
        item = parse_todo_line(line)

        assert item is not None
        assert item.text == "Fix bug"
        assert item.priority == Priority.CRITICAL

    def test_parse_with_tags(self):
        line = "- [ ] 2024-01-15 10:30 [abc12345] - Fix bug #backend #urgent"
        item = parse_todo_line(line)

        assert item is not None
        assert item.text == "Fix bug"
        assert item.tags == ["backend", "urgent"]

    def test_parse_with_priority_and_tags(self):
        line = "- [ ] 2024-01-15 10:30 [abc12345] - Fix bug !high #backend #api"
        item = parse_todo_line(line)

        assert item is not None
        assert item.text == "Fix bug"
        assert item.priority == Priority.HIGH
        assert item.tags == ["backend", "api"]

    def test_parse_no_priority_or_tags(self):
        line = "- [ ] 2024-01-15 10:30 [abc12345] - Fix bug"
        item = parse_todo_line(line)

        assert item is not None
        assert item.text == "Fix bug"
        assert item.priority is None
        assert item.tags is None


class TestFormatTodoLinePriorityTags:
    def test_format_with_priority(self):
        item = TodoItem(
            id="abc12345",
            text="Fix bug",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15, 10, 30),
            priority=Priority.CRITICAL,
        )
        line = format_todo_line(item)

        assert line == "- [ ] 2024-01-15 10:30 [abc12345] - Fix bug !critical"

    def test_format_with_tags(self):
        item = TodoItem(
            id="abc12345",
            text="Fix bug",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15, 10, 30),
            tags=["backend", "api"],
        )
        line = format_todo_line(item)

        assert line == "- [ ] 2024-01-15 10:30 [abc12345] - Fix bug #backend #api"

    def test_format_with_priority_and_tags(self):
        item = TodoItem(
            id="abc12345",
            text="Fix bug",
            status=Status.PENDING,
            created_at=datetime(2024, 1, 15, 10, 30),
            priority=Priority.HIGH,
            tags=["backend"],
        )
        line = format_todo_line(item)

        assert line == "- [ ] 2024-01-15 10:30 [abc12345] - Fix bug !high #backend"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_backends/test_utils.py::TestParseTodoLinePriorityTags -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/dodo/backends/utils.py - update imports and add parsing

import re
import uuid
from datetime import datetime

from dodo.models import Priority, Status, TodoItem

# Pattern matches: - [ ] 2024-01-15 10:30 [abc12345] - Todo text !priority #tag1 #tag2
# Groups: (checkbox_char, timestamp, optional_id, text_with_metadata)
TODO_LINE_PATTERN = re.compile(
    r"^- \[([ xX])\] (\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2})(?: \[([a-f0-9]{8})\])? - (.+)$"
)

# Patterns for extracting priority and tags from text
PRIORITY_PATTERN = re.compile(r"\s*!(critical|high|normal|low|someday)\s*")
TAG_PATTERN = re.compile(r"\s*#(\w+)")

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M"

PRIORITY_MAP = {
    "critical": Priority.CRITICAL,
    "high": Priority.HIGH,
    "normal": Priority.NORMAL,
    "low": Priority.LOW,
    "someday": Priority.SOMEDAY,
}


def generate_todo_id(text: str, timestamp: datetime) -> str:
    """Generate a unique 8-char hex ID."""
    return uuid.uuid4().hex[:8]


def format_todo_line(item: TodoItem, timestamp_fmt: str = TIMESTAMP_FORMAT) -> str:
    """Format a TodoItem as a markdown checkbox line with embedded ID."""
    checkbox = "x" if item.status == Status.DONE else " "
    ts = item.created_at.strftime(timestamp_fmt)

    # Build text with priority and tags appended
    text_parts = [item.text]
    if item.priority:
        text_parts.append(f"!{item.priority.value}")
    if item.tags:
        text_parts.extend(f"#{tag}" for tag in item.tags)

    full_text = " ".join(text_parts)
    return f"- [{checkbox}] {ts} [{item.id}] - {full_text}"


def parse_todo_line(line: str) -> TodoItem | None:
    """Parse a markdown todo line into a TodoItem."""
    match = TODO_LINE_PATTERN.match(line.strip())
    if not match:
        return None

    checkbox, ts_str, todo_id, text_with_metadata = match.groups()
    ts_str = ts_str.replace("/", "-").replace("T", " ")
    timestamp = datetime.strptime(ts_str, TIMESTAMP_FORMAT)

    final_id = todo_id if todo_id else generate_todo_id(text_with_metadata, timestamp)

    # Extract priority
    priority = None
    priority_match = PRIORITY_PATTERN.search(text_with_metadata)
    if priority_match:
        priority = PRIORITY_MAP.get(priority_match.group(1))

    # Extract tags
    tags = TAG_PATTERN.findall(text_with_metadata)
    tags = tags if tags else None

    # Clean text by removing priority and tags
    text = text_with_metadata
    text = PRIORITY_PATTERN.sub("", text)
    text = TAG_PATTERN.sub("", text)
    text = text.strip()

    return TodoItem(
        id=final_id,
        text=text,
        status=Status.DONE if checkbox.lower() == "x" else Status.PENDING,
        created_at=timestamp,
        priority=priority,
        tags=tags,
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_backends/test_utils.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/backends/utils.py tests/test_backends/test_utils.py
git commit -m "feat(markdown): parse and format !priority #tags in todo lines"
```

---

## Task 6: Update Markdown Backend Methods

**Files:**
- Modify: `src/dodo/backends/markdown.py`
- Test: `tests/test_backends/test_markdown.py`

**Step 1: Write the failing test**

```python
# tests/test_backends/test_markdown.py - add new tests

class TestMarkdownBackendPriorityTags:
    def test_add_with_priority(self, tmp_path: Path):
        from dodo.models import Priority
        backend = MarkdownBackend(tmp_path / "todos.md")

        item = backend.add("Test", priority=Priority.HIGH)

        assert item.priority == Priority.HIGH
        # Check file content
        content = (tmp_path / "todos.md").read_text()
        assert "!high" in content

    def test_add_with_tags(self, tmp_path: Path):
        backend = MarkdownBackend(tmp_path / "todos.md")

        item = backend.add("Test", tags=["backend", "api"])

        assert item.tags == ["backend", "api"]
        content = (tmp_path / "todos.md").read_text()
        assert "#backend" in content
        assert "#api" in content

    def test_update_priority(self, tmp_path: Path):
        from dodo.models import Priority
        backend = MarkdownBackend(tmp_path / "todos.md")
        item = backend.add("Test")

        updated = backend.update_priority(item.id, Priority.CRITICAL)

        assert updated.priority == Priority.CRITICAL

    def test_update_tags(self, tmp_path: Path):
        backend = MarkdownBackend(tmp_path / "todos.md")
        item = backend.add("Test")

        updated = backend.update_tags(item.id, ["new-tag"])

        assert updated.tags == ["new-tag"]

    def test_roundtrip_priority_tags(self, tmp_path: Path):
        from dodo.models import Priority
        backend = MarkdownBackend(tmp_path / "todos.md")

        item = backend.add("Test", priority=Priority.HIGH, tags=["api"])

        retrieved = backend.get(item.id)
        assert retrieved.priority == Priority.HIGH
        assert retrieved.tags == ["api"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_backends/test_markdown.py::TestMarkdownBackendPriorityTags -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/dodo/backends/markdown.py - update add method signature and implementation

from dodo.models import Priority, Status, TodoItem

# ... (keep existing imports and _file_lock)

class MarkdownBackend:
    # ... existing code ...

    def add(
        self,
        text: str,
        project: str | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
    ) -> TodoItem:
        timestamp = datetime.now()
        item = TodoItem(
            id=generate_todo_id(text, timestamp),
            text=text,
            status=Status.PENDING,
            created_at=timestamp,
            project=project,
            priority=priority,
            tags=tags,
        )
        with _file_lock(self._lock_path):
            self._append_item(item)
        return item

    def update_priority(self, id: str, priority: Priority | None) -> TodoItem:
        with _file_lock(self._lock_path):
            lines, items = self._read_lines_with_items()
            updated_item = None

            for idx, (line, item) in enumerate(zip(lines, items)):
                if item and item.id == id:
                    updated_item = TodoItem(
                        id=item.id,
                        text=item.text,
                        status=item.status,
                        created_at=item.created_at,
                        completed_at=item.completed_at,
                        project=item.project,
                        priority=priority,
                        tags=item.tags,
                    )
                    lines[idx] = format_todo_line(updated_item, self._format.timestamp_fmt)
                    break

            if not updated_item:
                raise KeyError(f"Todo not found: {id}")

            self._write_lines(lines)
            return updated_item

    def update_tags(self, id: str, tags: list[str] | None) -> TodoItem:
        with _file_lock(self._lock_path):
            lines, items = self._read_lines_with_items()
            updated_item = None

            for idx, (line, item) in enumerate(zip(lines, items)):
                if item and item.id == id:
                    updated_item = TodoItem(
                        id=item.id,
                        text=item.text,
                        status=item.status,
                        created_at=item.created_at,
                        completed_at=item.completed_at,
                        project=item.project,
                        priority=item.priority,
                        tags=tags,
                    )
                    lines[idx] = format_todo_line(updated_item, self._format.timestamp_fmt)
                    break

            if not updated_item:
                raise KeyError(f"Todo not found: {id}")

            self._write_lines(lines)
            return updated_item
```

Also update `update` and `update_text` methods to preserve priority/tags:

```python
    def update(self, id: str, status: Status) -> TodoItem:
        with _file_lock(self._lock_path):
            lines, items = self._read_lines_with_items()
            updated_item = None

            for idx, (line, item) in enumerate(zip(lines, items)):
                if item and item.id == id:
                    updated_item = TodoItem(
                        id=item.id,
                        text=item.text,
                        status=status,
                        created_at=item.created_at,
                        completed_at=datetime.now() if status == Status.DONE else None,
                        project=item.project,
                        priority=item.priority,
                        tags=item.tags,
                    )
                    lines[idx] = format_todo_line(updated_item, self._format.timestamp_fmt)
                    break

            if not updated_item:
                raise KeyError(f"Todo not found: {id}")

            self._write_lines(lines)
            return updated_item

    def update_text(self, id: str, text: str) -> TodoItem:
        with _file_lock(self._lock_path):
            lines, items = self._read_lines_with_items()
            updated_item = None

            for idx, (line, item) in enumerate(zip(lines, items)):
                if item and item.id == id:
                    updated_item = TodoItem(
                        id=item.id,
                        text=text,
                        status=item.status,
                        created_at=item.created_at,
                        completed_at=item.completed_at,
                        project=item.project,
                        priority=item.priority,
                        tags=item.tags,
                    )
                    lines[idx] = format_todo_line(updated_item, self._format.timestamp_fmt)
                    break

            if not updated_item:
                raise KeyError(f"Todo not found: {id}")

            self._write_lines(lines)
            return updated_item
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_backends/test_markdown.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/backends/markdown.py tests/test_backends/test_markdown.py
git commit -m "feat(markdown): add priority/tags support to markdown backend"
```

---

## Task 7: Add Sorting to List Command

**Files:**
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_cli.py - add new test

from typer.testing import CliRunner
from dodo.cli import app

runner = CliRunner()


class TestListSorting:
    def test_list_sort_priority(self, tmp_path, monkeypatch):
        # Setup: create todos with different priorities
        monkeypatch.setenv("DODO_CONFIG_DIR", str(tmp_path))

        # Add todos
        runner.invoke(app, ["add", "Low priority task"])
        runner.invoke(app, ["add", "High priority task"])

        # This test will be more meaningful after we can set priorities via CLI
        result = runner.invoke(app, ["list", "--sort", "priority"])

        assert result.exit_code == 0

    def test_list_sort_created(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DODO_CONFIG_DIR", str(tmp_path))

        runner.invoke(app, ["add", "First"])
        runner.invoke(app, ["add", "Second"])

        result = runner.invoke(app, ["list", "--sort", "created"])

        assert result.exit_code == 0
        # First should appear before Second (default order)
        assert result.output.index("First") < result.output.index("Second")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::TestListSorting -v`
Expected: FAIL with "No such option: --sort"

**Step 3: Write minimal implementation**

```python
# src/dodo/cli.py - update list_todos function

from dodo.models import Priority

@app.command(name="ls")
@app.command(name="list")
def list_todos(
    project: Annotated[str | None, typer.Option("-p", "--project")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
    done: Annotated[bool, typer.Option("--done", help="Show completed")] = False,
    all_: Annotated[bool, typer.Option("-a", "--all", help="Show all")] = False,
    format_: Annotated[str | None, typer.Option("-f", "--format", help="Output format")] = None,
    sort: Annotated[str | None, typer.Option("--sort", "-s", help="Sort by: created, priority, tag")] = None,
):
    """List todos."""
    from dodo.formatters import get_formatter
    from dodo.models import Status

    cfg = _get_config()

    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    status = None if all_ else (Status.DONE if done else Status.PENDING)
    items = svc.list(status=status)

    # Apply sorting
    if sort:
        items = _sort_items(items, sort)

    format_str = format_ or cfg.default_format
    try:
        formatter = get_formatter(format_str)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    from dodo.plugins import apply_hooks
    formatter = apply_hooks("extend_formatter", formatter, cfg)

    output = formatter.format(items)
    console.print(output)


def _sort_items(items: list, sort_by: str) -> list:
    """Sort items by specified field."""
    if sort_by == "created":
        return sorted(items, key=lambda x: x.created_at)
    elif sort_by == "priority":
        # Higher priority first, then alphabetical; null priority last
        def priority_key(item):
            if item.priority is None:
                return (0, item.text.lower())
            return (item.priority.sort_order, item.text.lower())
        return sorted(items, key=priority_key, reverse=True)
    elif sort_by == "tag":
        # Sort by first tag alphabetically, then by text
        def tag_key(item):
            first_tag = item.tags[0] if item.tags else "zzz"
            return (first_tag.lower(), item.text.lower())
        return sorted(items, key=tag_key)
    else:
        console.print(f"[yellow]Unknown sort option: {sort_by}. Using default.[/yellow]")
        return items
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py::TestListSorting -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/cli.py tests/test_cli.py
git commit -m "feat(cli): add --sort flag to list command"
```

---

## Task 8: Add Filtering to List Command

**Files:**
- Modify: `src/dodo/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_cli.py - add new test

class TestListFiltering:
    def test_list_filter_priority(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DODO_CONFIG_DIR", str(tmp_path))

        result = runner.invoke(app, ["list", "--filter", "prio:high"])

        assert result.exit_code == 0

    def test_list_filter_tag(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DODO_CONFIG_DIR", str(tmp_path))

        result = runner.invoke(app, ["list", "--filter", "tag:backend"])

        assert result.exit_code == 0

    def test_list_filter_multiple(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DODO_CONFIG_DIR", str(tmp_path))

        result = runner.invoke(app, ["list", "-f", "prio:high", "-f", "tag:api"])

        # Note: -f conflicts with --format, need different flag
        # This test documents the issue
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::TestListFiltering -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Note: `--filter` conflicts with `-f` for `--format`. Use `--filter` only, no short form, or use `--where`.

```python
# src/dodo/cli.py - update list_todos

@app.command(name="ls")
@app.command(name="list")
def list_todos(
    project: Annotated[str | None, typer.Option("-p", "--project")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d", help="Target dodo name")] = None,
    done: Annotated[bool, typer.Option("--done", help="Show completed")] = False,
    all_: Annotated[bool, typer.Option("-a", "--all", help="Show all")] = False,
    format_: Annotated[str | None, typer.Option("-f", "--format", help="Output format")] = None,
    sort: Annotated[str | None, typer.Option("--sort", "-s", help="Sort by: created, priority, tag")] = None,
    filter_: Annotated[list[str] | None, typer.Option("--filter", help="Filter: prio:<level>, tag:<name>")] = None,
):
    """List todos."""
    from dodo.formatters import get_formatter
    from dodo.models import Status

    cfg = _get_config()

    dodo_id, explicit_path = _resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = _get_service_with_path(cfg, explicit_path)
    else:
        svc = _get_service(cfg, dodo_id)

    status = None if all_ else (Status.DONE if done else Status.PENDING)
    items = svc.list(status=status)

    # Apply filters
    if filter_:
        items = _filter_items(items, filter_)

    # Apply sorting
    if sort:
        items = _sort_items(items, sort)

    format_str = format_ or cfg.default_format
    try:
        formatter = get_formatter(format_str)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    from dodo.plugins import apply_hooks
    formatter = apply_hooks("extend_formatter", formatter, cfg)

    output = formatter.format(items)
    console.print(output)


def _filter_items(items: list, filters: list[str]) -> list:
    """Filter items by specified criteria."""
    result = items

    for f in filters:
        if f.startswith("prio:") or f.startswith("priority:"):
            # Extract priority values (comma-separated)
            _, values = f.split(":", 1)
            priority_values = {v.strip().lower() for v in values.split(",")}
            result = [
                item for item in result
                if item.priority and item.priority.value in priority_values
            ]
        elif f.startswith("tag:"):
            _, values = f.split(":", 1)
            tag_values = {v.strip().lower() for v in values.split(",")}
            result = [
                item for item in result
                if item.tags and any(t.lower() in tag_values for t in item.tags)
            ]
        else:
            console.print(f"[yellow]Unknown filter: {f}[/yellow]")

    return result
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py::TestListFiltering -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/cli.py tests/test_cli.py
git commit -m "feat(cli): add --filter flag for priority and tag filtering"
```

---

## Task 9: Create AI Command Group Structure

**Files:**
- Modify: `src/dodo/cli.py`
- Create: `src/dodo/ai_commands.py`
- Test: `tests/test_ai_commands.py`

**Step 1: Create the ai commands module**

```python
# src/dodo/ai_commands.py

"""AI-assisted todo management commands."""

import typer
from typing import Annotated
from rich.console import Console

ai_app = typer.Typer(
    name="ai",
    help="AI-assisted todo management.",
)

console = Console()


@ai_app.command(name="add")
def ai_add(
    text: Annotated[str | None, typer.Argument(help="Input text")] = None,
):
    """Add todos with AI-inferred priority and tags."""
    console.print("[yellow]AI add not yet implemented[/yellow]")


@ai_app.command(name="prio")
@ai_app.command(name="prioritize")
def ai_prioritize(
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Auto-apply without confirmation")] = False,
):
    """AI-assisted bulk priority assignment."""
    console.print("[yellow]AI prioritize not yet implemented[/yellow]")


@ai_app.command(name="reword")
def ai_reword(
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Auto-apply without confirmation")] = False,
):
    """AI-assisted todo rewording for clarity."""
    console.print("[yellow]AI reword not yet implemented[/yellow]")


@ai_app.command(name="tag")
def ai_tag(
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Auto-apply without confirmation")] = False,
):
    """AI-assisted bulk tagging."""
    console.print("[yellow]AI tag not yet implemented[/yellow]")


@ai_app.command(name="sync")
def ai_sync(
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Auto-apply without confirmation")] = False,
):
    """Sync todos with git history - mark completed items."""
    console.print("[yellow]AI sync not yet implemented[/yellow]")
```

**Step 2: Register in cli.py**

```python
# src/dodo/cli.py - replace the old ai command

# Remove the old @app.command() def ai() function

# Add at the end, before plugin registration:
from dodo.ai_commands import ai_app
app.add_typer(ai_app, name="ai")
```

**Step 3: Write the test**

```python
# tests/test_ai_commands.py

from typer.testing import CliRunner
from dodo.cli import app

runner = CliRunner()


class TestAiCommandGroup:
    def test_ai_help(self):
        result = runner.invoke(app, ["ai", "--help"])
        assert result.exit_code == 0
        assert "add" in result.output
        assert "prio" in result.output
        assert "reword" in result.output
        assert "tag" in result.output
        assert "sync" in result.output

    def test_ai_add_placeholder(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DODO_CONFIG_DIR", str(tmp_path))
        result = runner.invoke(app, ["ai", "add", "test input"])
        # Placeholder should work without error
        assert result.exit_code == 0

    def test_ai_prio_placeholder(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DODO_CONFIG_DIR", str(tmp_path))
        result = runner.invoke(app, ["ai", "prio"])
        assert result.exit_code == 0

    def test_ai_prioritize_alias(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DODO_CONFIG_DIR", str(tmp_path))
        result = runner.invoke(app, ["ai", "prioritize"])
        assert result.exit_code == 0
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_ai_commands.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/ai_commands.py src/dodo/cli.py tests/test_ai_commands.py
git commit -m "feat(ai): create ai command group with subcommands"
```

---

## Task 10: Implement AI Add with Priority/Tags

**Files:**
- Modify: `src/dodo/ai.py`
- Modify: `src/dodo/ai_commands.py`
- Test: `tests/test_ai.py`

**Step 1: Update AI schema and prompts**

```python
# src/dodo/ai.py - update schemas

ADD_SCHEMA = json.dumps({
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
                        "enum": ["critical", "high", "normal", "low", "someday", None]
                    },
                    "tags": {
                        "type": ["array", "null"],
                        "items": {"type": "string"}
                    }
                },
                "required": ["text"]
            }
        }
    },
    "required": ["tasks"]
})

DEFAULT_ADD_PROMPT = """Convert user input into a JSON array of todo objects.
For each task:
- Write clear, concise text (imperative mood: "Fix X", "Add Y")
- Infer priority only if clearly indicated (urgent/critical/blocking = critical, nice-to-have/someday = low/someday). Default to null.
- Infer tags from context (technology, area, type). Use existing tags when relevant: {existing_tags}

Output ONLY the JSON object with tasks array, nothing else.
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

    # ... similar to run_ai but returns dicts instead of strings
```

**Step 2: Update ai_commands.py ai_add**

```python
# src/dodo/ai_commands.py - implement ai_add

@ai_app.command(name="add")
def ai_add(
    text: Annotated[str | None, typer.Argument(help="Input text")] = None,
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d")] = None,
):
    """Add todos with AI-inferred priority and tags."""
    import sys
    from dodo.config import Config
    from dodo.core import TodoService
    from dodo.resolve import resolve_dodo
    from dodo.ai import run_ai_add
    from dodo.models import Priority

    piped = None
    if not sys.stdin.isatty():
        piped = sys.stdin.read()

    if not text and not piped:
        console.print("[red]Error:[/red] Provide text or pipe input")
        raise typer.Exit(1)

    cfg = Config.load()
    dodo_id, explicit_path = resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = TodoService(cfg, project_id=None, storage_path=explicit_path)
    else:
        svc = TodoService(cfg, dodo_id)

    # Get existing tags for context
    existing_items = svc.list()
    existing_tags = set()
    for item in existing_items:
        if item.tags:
            existing_tags.update(item.tags)

    tasks = run_ai_add(
        user_input=text or "",
        piped_content=piped,
        command=cfg.ai_command,
        system_prompt=cfg.ai_add_prompt,
        existing_tags=list(existing_tags),
    )

    if not tasks:
        console.print("[red]Error:[/red] AI returned no todos")
        raise typer.Exit(1)

    target = dodo_id or "global"
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

        console.print(f"[green]✓[/green] Added to {dest}: {item.text}{priority_str}{tags_str} [dim]({item.id})[/dim]")
```

**Step 3: Write test**

```python
# tests/test_ai.py - add new test

class TestRunAiAdd:
    @patch("dodo.ai.subprocess.run")
    def test_returns_structured_tasks(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"tasks": [{"text": "Fix bug", "priority": "high", "tags": ["backend"]}]}',
            stderr="",
        )

        from dodo.ai import run_ai_add

        result = run_ai_add(
            user_input="test",
            command="llm '{{prompt}}'",
            system_prompt="format todos",
        )

        assert len(result) == 1
        assert result[0]["text"] == "Fix bug"
        assert result[0]["priority"] == "high"
        assert result[0]["tags"] == ["backend"]
```

**Step 4: Run tests**

Run: `pytest tests/test_ai.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/ai.py src/dodo/ai_commands.py tests/test_ai.py
git commit -m "feat(ai): implement ai add with priority and tags inference"
```

---

## Task 11: Implement AI Prioritize

**Files:**
- Modify: `src/dodo/ai.py`
- Modify: `src/dodo/ai_commands.py`
- Test: `tests/test_ai_commands.py`

**Step 1: Add schema and function to ai.py**

```python
# src/dodo/ai.py

PRIORITIZE_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["critical", "high", "normal", "low", "someday"]
                    }
                },
                "required": ["id", "priority"]
            }
        }
    },
    "required": ["changes"]
})

DEFAULT_PRIORITIZE_PROMPT = """Analyze these todos and assign priorities where missing or clearly wrong.
Priority levels: critical (fires/blockers), high (important soon), normal (standard work), low (nice-to-have), someday (ideas/backlog).
Only return todos that need priority changes. Be conservative - most todos are "normal" or don't need explicit priority.

Current todos:
{todos}

Return ONLY a JSON object with changes array containing {id, priority} for items to update.
"""


def run_ai_prioritize(
    todos: list[dict],
    command: str,
    system_prompt: str,
) -> list[dict]:
    """Run AI to suggest priority changes. Returns list of {id, priority}."""
    # Format todos for prompt
    todos_text = "\n".join(
        f"- [{t['id']}] {t['text']} (current: {t.get('priority', 'none')})"
        for t in todos
    )
    prompt = system_prompt.format(todos=todos_text)

    # ... call AI and parse response
```

**Step 2: Implement in ai_commands.py**

```python
# src/dodo/ai_commands.py

@ai_app.command(name="prio")
@ai_app.command(name="prioritize")
def ai_prioritize(
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Auto-apply")] = False,
    global_: Annotated[bool, typer.Option("-g", "--global")] = False,
    dodo: Annotated[str | None, typer.Option("--dodo", "-d")] = None,
):
    """AI-assisted bulk priority assignment."""
    from dodo.config import Config
    from dodo.core import TodoService
    from dodo.resolve import resolve_dodo
    from dodo.ai import run_ai_prioritize
    from dodo.models import Priority, Status

    cfg = Config.load()
    dodo_id, explicit_path = resolve_dodo(cfg, dodo, global_)

    if explicit_path:
        svc = TodoService(cfg, project_id=None, storage_path=explicit_path)
    else:
        svc = TodoService(cfg, dodo_id)

    # Get pending todos
    items = svc.list(status=Status.PENDING)
    if not items:
        console.print("[yellow]No pending todos[/yellow]")
        return

    todos_data = [
        {"id": item.id, "text": item.text, "priority": item.priority.value if item.priority else None}
        for item in items
    ]

    changes = run_ai_prioritize(
        todos=todos_data,
        command=cfg.ai_command,
        system_prompt=cfg.ai_prioritize_prompt,
    )

    if not changes:
        console.print("[green]No priority changes suggested[/green]")
        return

    # Show diff
    console.print(f"\n[bold]Proposed changes ({len(changes)} of {len(items)} todos):[/bold]")
    for change in changes:
        item = next((i for i in items if i.id == change["id"]), None)
        if item:
            old_prio = item.priority.value if item.priority else "none"
            console.print(f"  {item.id}: \"{item.text[:40]}...\" → priority: {change['priority']} (was: {old_prio})")

    # Confirm
    if not yes:
        confirm = typer.confirm("\nApply changes?", default=False)
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Apply changes
    for change in changes:
        try:
            priority = Priority(change["priority"])
            svc._backend.update_priority(change["id"], priority)
        except (ValueError, KeyError) as e:
            console.print(f"[red]Failed to update {change['id']}: {e}[/red]")

    console.print(f"[green]✓[/green] Applied {len(changes)} priority changes")
```

**Step 3: Write test**

```python
# tests/test_ai_commands.py - add

class TestAiPrioritize:
    @patch("dodo.ai.subprocess.run")
    def test_prioritize_shows_diff(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.setenv("DODO_CONFIG_DIR", str(tmp_path))

        # Add a todo first
        runner.invoke(app, ["add", "Test todo"])

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"changes": []}',
            stderr="",
        )

        result = runner.invoke(app, ["ai", "prio"])
        assert result.exit_code == 0
```

**Step 4: Run tests**

Run: `pytest tests/test_ai_commands.py::TestAiPrioritize -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dodo/ai.py src/dodo/ai_commands.py tests/test_ai_commands.py
git commit -m "feat(ai): implement ai prioritize with diff and confirm"
```

---

## Task 12: Implement AI Reword

Similar structure to Task 11. Create schema, prompt, function in ai.py, implement in ai_commands.py.

**Commit message:** `feat(ai): implement ai reword for todo clarification`

---

## Task 13: Implement AI Tag

Similar structure to Task 11. Create schema, prompt, function in ai.py, implement in ai_commands.py.

**Commit message:** `feat(ai): implement ai tag for bulk tagging`

---

## Task 14: Implement AI Sync

**Files:**
- Modify: `src/dodo/ai.py`
- Modify: `src/dodo/ai_commands.py`
- Test: `tests/test_ai_commands.py`

**Step 1: Add schema and function**

```python
# src/dodo/ai.py

SYNC_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "completed": {
            "type": "array",
            "items": {"type": "string"}
        },
        "reasoning": {"type": "string"}
    },
    "required": ["completed"]
})

SYNC_TOOLS = ["Bash(git log*)", "Bash(git show*)", "Bash(git diff*)", "Read", "Grep"]

DEFAULT_SYNC_PROMPT = """You have access to git and file tools. Check if any of these todos have been completed.
Start with: git log --oneline -20
Dig deeper if needed. Only mark done if you find clear evidence (commit message, code exists, etc).

Todos to check:
{todos}

Return completed todo IDs with brief reasoning.
"""


def run_ai_sync(
    todos: list[dict],
    command: str,
    system_prompt: str,
) -> dict:
    """Run AI sync with tools enabled. Returns {completed: [ids], reasoning: str}."""
    # Build command with tools enabled
    # This requires modifying the command template to include --allowedTools
    # ...
```

**Step 2: Implement in ai_commands.py**

Similar to prioritize but marks items as done instead of updating priority.

**Commit message:** `feat(ai): implement ai sync with git tool access`

---

## Task 15: Add Configurable Prompts

**Files:**
- Modify: `src/dodo/config.py`
- Create: `src/dodo/prompts.py`
- Test: `tests/test_prompts.py`

**Step 1: Create prompts.py**

```python
# src/dodo/prompts.py

"""AI prompt configuration with lazy loading."""

import tomllib
from pathlib import Path
from typing import Any

# Default prompts (built-in)
DEFAULTS = {
    "ai.add": "...",
    "ai.prioritize": "...",
    "ai.reword": "...",
    "ai.tag": "...",
    "ai.sync": "...",
}

_prompts_cache: dict[str, str] | None = None


def get_prompt(key: str, config_dir: Path) -> str:
    """Get prompt by key, with user override support."""
    global _prompts_cache

    if _prompts_cache is None:
        _prompts_cache = _load_prompts(config_dir)

    return _prompts_cache.get(key, DEFAULTS.get(key, ""))


def _load_prompts(config_dir: Path) -> dict[str, str]:
    """Load prompts from config file, merged with defaults."""
    prompts = dict(DEFAULTS)

    prompts_file = config_dir / "prompts.toml"
    if prompts_file.exists():
        try:
            with prompts_file.open("rb") as f:
                user_prompts = tomllib.load(f)
                # Flatten nested structure: ai.add -> "ai.add"
                for section, values in user_prompts.items():
                    if isinstance(values, dict):
                        for key, value in values.items():
                            prompts[f"{section}.{key}"] = value
        except Exception:
            pass  # Use defaults on error

    return prompts
```

**Commit message:** `feat(config): add configurable AI prompts via prompts.toml`

---

## Task 16: Update Core Service

**Files:**
- Modify: `src/dodo/core.py`
- Test: `tests/test_core.py`

Update TodoService.add() to accept priority and tags parameters and pass them to the backend.

**Commit message:** `feat(core): pass priority and tags through service layer`

---

## Task 17: Update Formatters to Display Priority/Tags

**Files:**
- Modify: `src/dodo/formatters/table.py`
- Test: `tests/test_formatters.py`

Add priority and tags columns to table output.

**Commit message:** `feat(formatters): display priority and tags in table output`

---

## Task 18: Run Full Test Suite

**Step 1: Run all tests**

```bash
pytest tests/ -v --tb=short
```

**Step 2: Run type checking**

```bash
mypy src/dodo/
```

**Step 3: Fix any issues**

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: fix test and type issues"
```

---

## Summary

**Total tasks:** 18
**New files:** 2 (`src/dodo/ai_commands.py`, `src/dodo/prompts.py`)
**Modified files:** ~12

**Key changes:**
1. Models: Priority enum, TodoItem with priority/tags
2. SQLite: Schema migration, new columns and methods
3. Markdown: Parse/format `!priority #tags` syntax
4. CLI: `--sort`, `--filter` flags for list; ai command group
5. AI: Subcommands for add, prio, reword, tag, sync with diff+confirm
6. Config: Lazy-loaded prompts.toml for customization
