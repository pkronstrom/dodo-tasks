# Beads Analysis & Dodo Integration Report

## What is Beads?

Beads is a **dependency-aware issue tracker designed for AI coding agents**. Its core insight: AI agents working on multi-step coding tasks need to track task dependencies, not just task lists.

### How It Works
1. Stores issues as JSONL in `.beads/` directory (git-versioned)
2. Uses hash-based IDs (`bd-a1b2`) to prevent merge conflicts
3. SQLite cache for performance with background sync daemon
4. Tracks dependency graph between tasks

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
