# Dodo Dependency Tracking - Implementation Plan

## Architecture Decision

**Chosen approach: Optional fields on TodoItem**

- Add `blocked_by: frozenset[str] = frozenset()` to TodoItem
- Simple adapters (Markdown, Obsidian) return empty frozenset - they work unchanged
- SQLite adapter persists and loads dependencies
- CLI detects adapter capability at runtime for UX (hide dep commands if adapter doesn't support)

**Why this approach:**
- One model everywhere (no TodoItem vs TodoWithDeps juggling)
- Backward compatible (default = empty)
- Pythonic (duck typing - field exists, use it or ignore it)
- Minimal changes to existing code

---

## Implementation Plan

### Phase 1: Model Changes (Low Risk)

**File: `src/dodo/models.py`**

```python
@dataclass(frozen=True)
class TodoItem:
    id: str
    text: str
    status: Status
    created_at: datetime
    completed_at: datetime | None = None
    project: str | None = None
    blocked_by: frozenset[str] = frozenset()  # NEW - IDs of blocking tasks
```

**Tests:** Update existing tests to ensure default `blocked_by=frozenset()` works.

---

### Phase 2: Adapter Capability Protocol (Optional Detection)

**File: `src/dodo/adapters/base.py`**

```python
@runtime_checkable
class DependencyCapable(Protocol):
    """Marker protocol for adapters that persist dependencies."""

    def add_dependency(self, child_id: str, parent_id: str) -> None: ...
    def remove_dependency(self, child_id: str, parent_id: str) -> None: ...
```

This is NOT required for adapters to implement. It's for CLI to detect "should I show dep commands?"

---

### Phase 3: SQLite Adapter Extension

**File: `src/dodo/adapters/sqlite.py`**

1. Add `dependencies` table:
```sql
CREATE TABLE IF NOT EXISTS dependencies (
    child_id TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (child_id, parent_id),
    FOREIGN KEY (child_id) REFERENCES todos(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES todos(id) ON DELETE CASCADE
);
```

2. Update `list()` to JOIN and populate `blocked_by`
3. Implement `DependencyCapable` methods:
   - `add_dependency(child_id, parent_id)`
   - `remove_dependency(child_id, parent_id)`

4. Add helper methods:
   - `list_ready(project)` - items where all blockers are DONE
   - `list_blocked(project)` - items with open blockers

---

### Phase 4: CLI Commands

**File: `src/dodo/cli.py`**

New commands (only shown if adapter is DependencyCapable):

```bash
dodo dep add <child> <parent>   # child blocked by parent
dodo dep rm <child> <parent>    # remove dependency
dodo ready                      # list unblocked tasks
dodo blocked                    # list blocked tasks
```

Modify existing:
- `dodo list --deps` flag to show blockers inline
- `dodo show <id>` to display blocked_by/blocks info
- `dodo add --blocked-by <id>` option

**Capability check pattern:**
```python
def _supports_deps() -> bool:
    return isinstance(get_adapter(), DependencyCapable)

@app.command()
def ready():
    if not _supports_deps():
        console.print("[yellow]Dependency tracking not supported by current adapter[/yellow]")
        raise typer.Exit(1)
    # ...
```

---

### Phase 5: UI Integration (Optional)

**File: `src/dodo/ui/interactive.py`**

- Show blocked status in todo list (e.g., grayed out or with indicator)
- Add "Show ready only" filter option
- Add dependency management submenu

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/dodo/models.py` | Add `blocked_by` field |
| `src/dodo/adapters/base.py` | Add `DependencyCapable` protocol |
| `src/dodo/adapters/sqlite.py` | Add deps table, implement protocol |
| `src/dodo/cli.py` | Add dep/ready/blocked commands |
| `src/dodo/ui/interactive.py` | Show blocked status (optional) |
| `tests/test_models.py` | Test new field default |
| `tests/test_adapters/test_sqlite.py` | Test dependency methods |
| `tests/test_cli.py` | Test new commands |

---

## Verification

1. `uv run pytest tests/` - all existing tests pass
2. `uv run dodo add "task a"` - works as before
3. `uv run dodo add "task b"` - works as before
4. `uv run dodo dep add <b-id> <a-id>` - b blocked by a
5. `uv run dodo ready` - only shows a (b is blocked)
6. `uv run dodo done <a-id>` - complete a
7. `uv run dodo ready` - now shows b (unblocked)
8. `uv run ruff check src/` - no lint errors
9. `uv run mypy src/dodo/` - type checks pass

---

## What Stays Unchanged

- `MarkdownAdapter` - returns items with `blocked_by=frozenset()`, works fine
- `ObsidianAdapter` - same, no changes needed
- Existing CLI commands without `--deps` flag
- Config system
- AI features
- Project detection

---

# Reference: Beads Analysis

(Original research below for context)

---

# Beads Analysis & Dodo Integration Report

## What is Beads?

Beads is a **dependency-aware issue tracker designed for AI coding agents**. Its core insight: AI agents working on multi-step coding tasks need to track task dependencies, not just task lists.

### How It Works
1. Stores issues as JSONL in `.beads/` directory (git-versioned)
2. Uses hash-based IDs (`bd-a1b2`) to prevent merge conflicts
3. SQLite cache for performance with background sync daemon
4. Tracks dependency graph between tasks

---

## Beads MCP Tools (Agent Interface)

These are the functions beads exposes to AI agents via MCP:

| Tool | Parameters | Description |
|------|-----------|-------------|
| `init` | workspace_root? | Initialize beads in directory |
| `create` | title, priority, type | Create new issue |
| `list` | status?, priority?, type?, assignee? | List issues with filters |
| `ready` | - | **Find tasks with no blockers** |
| `show` | issue_id | Show issue with dependencies |
| `update` | issue_id, status?, priority?, notes? | Update issue fields |
| `close` | issue_id | Close completed issue |
| `reopen` | issue_id, reason? | Reopen closed issue |
| `dep` | issue_ids, type (blocks/related/parent) | **Add dependency between issues** |
| `blocked` | - | **Get blocked issues** |
| `stats` | - | Project statistics |
| `set_context` | workspace_root | Set default workspace |

**Core agent-facing tools (the 3 that matter):**
1. `ready` - "What can I work on now?"
2. `dep` - "This task depends on that task"
3. `blocked` - "What's stuck?"

---

## Cutting Through the Bloat: Core vs Nice-to-Have

### CORE Features (What Makes Beads Different)

| Feature | Why It Matters |
|---------|----------------|
| **Dependency Tracking** | "Task B is blocked by Task A" - prevents agents from starting work with unmet prerequisites |
| **Ready Detection** | `bd ready` shows tasks with no open blockers - agent knows what it can work on NOW |
| **Git-backed Storage** | Tasks live with code, can be branched/merged |
| **Hash-based IDs** | No conflicts when multiple agents work in parallel |

### NICE-TO-HAVE (Can Skip)

| Feature | Reality |
|---------|---------|
| SQLite cache + daemon | Optimization, not required |
| Semantic compaction | Context window management - separate concern |
| Hierarchical IDs | Epics/subtasks - adds complexity, questionable value |
| Stealth mode | Edge case |
| JSON output format | Any tool can do this |
| Priority levels | Standard todo feature |

---

## Minimum Viable "Beads-like" Product

You need **3 things**:

### 1. Dependency Relationship Storage
```
task_a blocks task_b
task_b blocked_by task_a
```

### 2. Ready Task Detection
```python
def is_ready(task) -> bool:
    return task.status == PENDING and all(
        blocker.status == DONE for blocker in task.blocked_by
    )
```

### 3. Commands
- `add "task" --blocked-by <id>` - Create with dependency
- `dep add <child> <parent>` - Link existing tasks
- `ready` - List unblocked tasks
- `show <id>` - Show task with its blockers

That's it. Everything else is polish.

---

## Dodo Integration Analysis

### Current Dodo Model
```python
@dataclass(frozen=True)
class TodoItem:
    id: str
    text: str
    status: Status  # PENDING | DONE
    created_at: datetime
    completed_at: datetime | None
    project: str | None
```

### What Would Need to Change

**1. Extended Model:**
```python
@dataclass(frozen=True)
class TodoItem:
    id: str
    text: str
    status: Status
    created_at: datetime
    completed_at: datetime | None
    project: str | None
    blocked_by: frozenset[str] = frozenset()  # IDs of blockers
```

**2. Extended Adapter Protocol:**
```python
class TodoAdapter(Protocol):
    # ... existing methods ...

    def add_dependency(self, child_id: str, parent_id: str) -> None:
        """Make child blocked by parent."""
        ...

    def remove_dependency(self, child_id: str, parent_id: str) -> None:
        """Remove blocking relationship."""
        ...

    def list_ready(self, project: str | None = None) -> list[TodoItem]:
        """List tasks with no open blockers."""
        ...
```

**3. New CLI Commands:**
```bash
dodo add "task" --blocked-by abc123  # Create with blocker
dodo dep add <child> <parent>        # Link tasks
dodo ready                           # Show unblocked
dodo show <id>                       # Show with dependencies
```

### Implementation Complexity

| Change | Effort | Notes |
|--------|--------|-------|
| Model extension | Low | Add `blocked_by: frozenset[str]` |
| SQLite adapter | Medium | Add `dependencies` table |
| Markdown adapter | Medium | Add `blocked_by: [ids]` frontmatter |
| Obsidian adapter | Medium | Depends on Obsidian API |
| CLI commands | Low | 3-4 new Typer commands |
| Ready logic | Low | Filter on dependency status |
| UI integration | Low | Add "ready" view to interactive menu |

---

## Recommendation: Extend Dodo vs Separate App

### Extend Dodo (Recommended)

**Pros:**
- Dodo already has project isolation, git awareness, multi-backend support
- Protocol-based adapters make extension clean
- Shared infrastructure (config, AI, UI)
- One tool to rule them all

**Cons:**
- Increases complexity of "simple" todo app
- Not all backends may support dependencies well (Obsidian?)

### Separate App

**Pros:**
- Keep dodo simple
- Beads-clone can be agent-focused from day 1

**Cons:**
- Duplicate infrastructure
- Context switching between tools
- Harder to use dependencies with non-project todos

---

## Verdict

**Extend Dodo.** The dependency feature is additive - users who don't need it won't notice it. The architecture already supports it.

### Minimal Implementation Path

1. Add `blocked_by: frozenset[str]` to TodoItem
2. Add `dependencies` table to SQLite adapter
3. Add `dodo dep add/rm` commands
4. Add `dodo ready` filter
5. Update `dodo show` to display blockers

Skip: hierarchical IDs, compaction, daemon, stealth mode.

---

## Could This Be Implemented as a Dodo Adapter?

### Short Answer: Partially, but not cleanly.

### The Constraint

Dodo's architecture flows like this:
```
CLI -> TodoService -> TodoAdapter -> Storage
                          |
                          v
                     TodoItem (shared model)
```

All adapters return `TodoItem`. The model is shared. If `TodoItem` doesn't have `blocked_by`, no adapter can provide that data to the CLI/UI.

### Three Approaches

#### Option 1: Pure Adapter (JSONL Backend)
Create a `BeadsAdapter` that stores in `.beads/` JSONL format.

**What Works:**
- Storage format matches beads
- Git-versioned tasks
- Hash-based IDs

**What Doesn't:**
- `TodoAdapter.list()` returns `list[TodoItem]`
- `TodoItem` has no `blocked_by` field
- Dependencies are stored but invisible to dodo's CLI/UI
- `dodo ready` command impossible without model change

**Verdict:** You'd have beads storage, but no beads features.

---

#### Option 2: Side-Channel DependencyService
Keep adapters unchanged. Add a separate `DependencyService` that tracks relationships.

```python
# New file: src/dodo/dependencies.py
class DependencyService:
    """Tracks task dependencies independently of adapters."""

    def __init__(self, db_path: Path):
        self.db = sqlite3.connect(db_path)
        # Creates: dependencies(child_id, parent_id)

    def add(self, child_id: str, parent_id: str) -> None: ...
    def remove(self, child_id: str, parent_id: str) -> None: ...
    def get_blockers(self, task_id: str) -> set[str]: ...
    def is_ready(self, task_id: str, open_tasks: set[str]) -> bool: ...
```

**What Works:**
- Zero changes to TodoItem or adapters
- Works with any backend (SQLite, Markdown, Obsidian)
- `dodo ready` possible: query adapters for open tasks, filter through DependencyService

**What Doesn't:**
- Two sources of truth (adapter + dependency db)
- Orphaned dependencies if task deleted in one but not other
- More complex CLI layer

**Verdict:** Feasible. The cleanest adapter-only option.

---

#### Option 3: Extend TodoItem (Recommended Earlier)
Add optional `blocked_by: frozenset[str] = frozenset()` to model.

**What Works:**
- Single source of truth
- Adapters that don't support dependencies just return empty set
- Clean extension of existing architecture

**What Doesn't:**
- Changes shared model (breaking change for type hints)
- Adapters must update to persist/load field

---

### Comparison

| Approach | Model Change | Adapter Change | Complexity | Feature Complete |
|----------|--------------|----------------|------------|------------------|
| Pure Adapter | None | New adapter | Low | No (storage only) |
| DependencyService | None | None | Medium | Yes |
| Extend TodoItem | Yes | Yes | Medium | Yes |

### Recommendation for Adapter-Only

If you want **zero model changes**, use **Option 2: DependencyService**.

Implementation outline:
```
src/dodo/
├── dependencies.py    # New: DependencyService class
├── cli.py             # Add: dep, ready commands
└── core.py            # Wire DependencyService alongside adapters
```

The dependencies live in `~/.config/dodo/dependencies.db` (or `.dodo/dependencies.db` per-project). Completely separate from todo storage. Works with SQLite, Markdown, Obsidian, or any future adapter.

Downside: `dodo show <id>` needs to query both adapter AND dependency service to display full picture. Small price for zero adapter changes.

---

## Option 4: Protocol Extension Pattern (Recommended)

Keep dodo's core architecture pure. Extend via optional protocol that rich adapters can implement.

### Architecture

```
                    TodoAdapter (base protocol)
                          │
                          │ implements
                          ▼
    ┌─────────────────────┼─────────────────────┐
    │                     │                     │
MarkdownAdapter     SQLiteAdapter          ObsidianAdapter
                          │
                          │ also implements
                          ▼
               DependencyCapable (optional protocol)
```

### Code Structure

**Keep TodoItem pure:**
```python
# models.py - UNCHANGED
@dataclass(frozen=True)
class TodoItem:
    id: str
    text: str
    status: Status
    created_at: datetime
    completed_at: datetime | None = None
    project: str | None = None
```

**Add new model for rich results:**
```python
# models.py - ADD
@dataclass(frozen=True)
class TodoWithDeps:
    """Extended todo with dependency info. Only from DependencyCapable adapters."""
    item: TodoItem
    blocked_by: frozenset[str] = frozenset()  # IDs of blocking tasks
    blocks: frozenset[str] = frozenset()       # IDs this task blocks
```

**Keep base adapter pure:**
```python
# adapters/base.py - UNCHANGED
@runtime_checkable
class TodoAdapter(Protocol):
    def add(self, text: str, project: str | None = None) -> TodoItem: ...
    def list(self, project: str | None = None, status: Status | None = None) -> list[TodoItem]: ...
    def get(self, id: str) -> TodoItem | None: ...
    def update(self, id: str, status: Status) -> TodoItem: ...
    def update_text(self, id: str, text: str) -> TodoItem: ...
    def delete(self, id: str) -> None: ...
```

**Add optional capability protocol:**
```python
# adapters/base.py - ADD
@runtime_checkable
class DependencyCapable(Protocol):
    """Optional protocol for adapters that support dependencies."""

    def add_dependency(self, child_id: str, parent_id: str) -> None:
        """Make child blocked by parent."""
        ...

    def remove_dependency(self, child_id: str, parent_id: str) -> None:
        """Remove blocking relationship."""
        ...

    def list_with_deps(
        self,
        project: str | None = None,
        status: Status | None = None,
    ) -> list[TodoWithDeps]:
        """List todos with dependency info."""
        ...

    def list_ready(self, project: str | None = None) -> list[TodoItem]:
        """List tasks with no open blockers."""
        ...

    def list_blocked(self, project: str | None = None) -> list[TodoWithDeps]:
        """List tasks that are blocked."""
        ...
```

**SQLite adapter implements both:**
```python
# adapters/sqlite.py
class SqliteAdapter(TodoAdapter, DependencyCapable):
    """SQLite backend with full dependency support."""

    # TodoAdapter methods (existing)
    def add(self, text, project=None): ...
    def list(self, project=None, status=None): ...
    # ...

    # DependencyCapable methods (new)
    def add_dependency(self, child_id, parent_id): ...
    def list_with_deps(self, project=None, status=None): ...
    def list_ready(self, project=None): ...
    def list_blocked(self, project=None): ...
```

**Markdown adapter stays simple:**
```python
# adapters/markdown.py
class MarkdownAdapter(TodoAdapter):
    """Markdown backend. No dependency support."""
    # Only implements TodoAdapter
```

### CLI Changes

```python
# cli.py
@app.command()
def list(
    deps: bool = typer.Option(False, "--deps", help="Show dependencies"),
):
    adapter = get_adapter()

    if deps:
        if not isinstance(adapter, DependencyCapable):
            console.print("[red]Current adapter doesn't support dependencies[/red]")
            raise typer.Exit(1)
        items = adapter.list_with_deps(project=project)
        # Rich display with blocked_by/blocks
    else:
        items = adapter.list(project=project)
        # Normal display


@app.command()
def ready():
    """List tasks with no open blockers."""
    adapter = get_adapter()
    if not isinstance(adapter, DependencyCapable):
        console.print("[red]Current adapter doesn't support dependencies[/red]")
        raise typer.Exit(1)

    items = adapter.list_ready(project=project)
    # Display ready tasks


@app.command()
def dep():
    """Manage dependencies."""
    # Only available if adapter is DependencyCapable
```

### Benefits

| Aspect | Result |
|--------|--------|
| TodoItem | Unchanged, pure |
| TodoAdapter | Unchanged, pure |
| MarkdownAdapter | Unchanged, still works |
| ObsidianAdapter | Unchanged, still works |
| SQLiteAdapter | Extended with DependencyCapable |
| New commands | Gracefully fail on non-capable adapters |
| `--deps` flag | Only works with capable adapters |

### What This Enables

```bash
# Works with any adapter
dodo add "fix bug"
dodo list
dodo done abc123

# Only with DependencyCapable adapters (SQLite)
dodo add "write tests" --blocked-by abc123
dodo list --deps          # Shows blockers inline
dodo ready                # Tasks with no blockers
dodo blocked              # Tasks that are stuck
dodo dep add xyz abc123   # xyz blocked by abc123
dodo dep rm xyz abc123    # Remove dependency
dodo show abc123          # Shows what it blocks/blocked by
```

### SQLite Schema Addition

```sql
-- Existing tables unchanged

-- New table for dependencies
CREATE TABLE IF NOT EXISTS dependencies (
    child_id TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (child_id, parent_id),
    FOREIGN KEY (child_id) REFERENCES todos(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES todos(id) ON DELETE CASCADE
);

CREATE INDEX idx_deps_child ON dependencies(child_id);
CREATE INDEX idx_deps_parent ON dependencies(parent_id);
```

### MCP Integration

If dodo exposes MCP tools, the same pattern applies:

```python
# mcp/tools.py
@mcp.tool()
def ready(workspace: str | None = None) -> list[dict]:
    """List tasks with no open blockers."""
    adapter = get_adapter(workspace)
    if not isinstance(adapter, DependencyCapable):
        return {"error": "Adapter doesn't support dependencies"}
    return [asdict(t) for t in adapter.list_ready()]

@mcp.tool()
def dep_add(child_id: str, parent_id: str, workspace: str | None = None):
    """Add dependency: child is blocked by parent."""
    adapter = get_adapter(workspace)
    if not isinstance(adapter, DependencyCapable):
        return {"error": "Adapter doesn't support dependencies"}
    adapter.add_dependency(child_id, parent_id)
    return {"ok": True}
```

---

## Final Recommendation

**Use Option 4: Protocol Extension Pattern.**

- Core stays pure (TodoItem, TodoAdapter unchanged)
- Markdown/Obsidian adapters work as before
- SQLiteAdapter gains DependencyCapable superpowers
- CLI gracefully handles capability detection
- Future adapters choose their capability level

This is the "have your cake and eat it too" solution.
