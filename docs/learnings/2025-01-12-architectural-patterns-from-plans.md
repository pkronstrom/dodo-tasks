# Learnings: Architectural Patterns from Historical Plans

**Date**: 2025-01-12
**Objective**: Extract key architectural patterns and decision-making methodologies from plan documents
**Outcome**: Success - Identified 3 high-value patterns worth preserving

## Summary

Review of 16 plan documents revealed three major architectural patterns: (1) Protocol Extension for optional capabilities, (2) Pragmatic Refactoring alongside feature development, and (3) Circular Dependency Resolution via service extraction. These patterns are transferable across projects.

---

## Pattern 1: Protocol Extension for Optional Capabilities

**Source**: `floofy-sparking-hanrahan.md` - Dodo Dependency Tracking

### The Problem

Adding new capabilities (like task dependencies) to a system with multiple backend adapters. Some backends can support the feature, others cannot.

### Approaches Evaluated

| Approach | Description | Verdict |
|----------|-------------|---------|
| **Model Extension** | Add `blocked_by` field to core `TodoItem` | Breaks backward compatibility, forces all adapters to change |
| **Side-Channel Service** | Separate `DependencyService` alongside adapters | Two sources of truth, orphaned data risk |
| **Pure Adapter** | New adapter with deps, ignore others | Storage only, no feature integration |
| **Protocol Extension** | Optional `DependencyCapable` protocol | Clean separation, graceful degradation |

### Winning Pattern: Protocol Extension

```python
# Base protocol unchanged
class TodoAdapter(Protocol):
    def list(self) -> list[TodoItem]: ...

# Optional capability protocol
@runtime_checkable
class DependencyCapable(Protocol):
    def add_dependency(self, child: str, parent: str) -> None: ...
    def list_ready(self) -> list[TodoItem]: ...

# Rich adapter implements both
class SqliteAdapter(TodoAdapter, DependencyCapable):
    ...

# Simple adapters stay simple
class MarkdownAdapter(TodoAdapter):
    ...

# CLI gracefully handles capability detection
if isinstance(adapter, DependencyCapable):
    show_dependency_commands()
else:
    hide_or_warn()
```

### Key Insight

**"Keep the core pure, extend via composition."** Don't pollute base interfaces with optional features. Use runtime type checking to detect capabilities.

### When to Apply

- Multi-backend systems where not all backends support all features
- Optional features that shouldn't break existing code
- Gradual capability rollout across implementations

---

## Pattern 2: Pragmatic Refactoring Alongside Features

**Source**: `greedy-crafting-river.md` - Script Scheduling

### The Problem

Need to add a new feature (script scheduling) to a codebase with technical debt (duplicated timezone logic, validation scattered across routers).

### The Anti-Pattern

- **"Refactor first, then add feature"** - Delays delivery, refactoring scope creeps
- **"Just add feature, ignore debt"** - Compounds technical debt, harder to maintain

### Winning Pattern: Interleaved Refactoring

**Phase 1: Extract utilities NEEDED by new feature**
```
core/scheduler_utils.py  <- timezone logic (used by both old + new code)
core/task_types.py       <- enums for task type system
```

**Phase 2: Schema migration (additive only)**
```sql
ALTER TABLE scheduled_tasks ADD COLUMN task_type TEXT DEFAULT 'prompt';
ALTER TABLE scheduled_tasks ADD COLUMN script_path TEXT;
```

**Phase 3: Implement feature using new utilities**
```python
async def run_scheduled_task(task):
    task_type = TaskType(task.get("task_type", "prompt"))
    if task_type == TaskType.SCRIPT:
        await _run_script_task(task)
    else:
        await _run_prompt_task(task)  # existing logic, moved
```

**Phase 4: Migrate old code to use new utilities (opportunistic)**

### Key Insight

**"Refactor the path you're walking."** Only clean up code you need to touch for the feature. Extract utilities that serve both old and new code.

### When to Apply

- Adding features to legacy codebases
- When refactoring scope is unclear
- Time-boxed development cycles

---

## Pattern 3: Circular Dependency Resolution via Service Extraction

**Source**: `hashed-juggling-origami.md` - Session Helpers Extraction

### The Problem

Business logic in router layer causing circular imports:
```
routers/api.py imports core/sessions.py
core/scheduler.py imports routers/api.py  # for build_context_prompt
app.py imports both
```

### The Fix: Three-Step Extraction

**Step 1: Identify router functions that are actually business logic**
```python
# These don't belong in routers:
def build_context_prompt(session, prompt) -> str
def should_auto_generate_name(source) -> bool
def generate_session_name(session_id, prompt)
```

**Step 2: Create `core/session_helpers.py`**
```python
# New home for business logic
from core.sessions import load_session, save_session
from core.config import get_config

def build_context_prompt(session, prompt) -> str:
    ...
```

**Step 3: Update imports atomically**
```python
# Before (routers/api.py):
from routers.api import build_context_prompt  # circular!

# After:
from core.session_helpers import build_context_prompt  # clean
```

### Key Insight

**"Routers should only route."** If a function could be called from multiple places (API, scheduler, bot), it's not a router function.

### Dependency Direction Rule

```
routers → core → (external libs)
       ↘     ↗
         app
```

Never: `core → routers`

---

## Gotchas & Warnings

1. **Protocol Extension gotcha**: `@runtime_checkable` has overhead. Only use `isinstance()` checks in setup/CLI, not hot paths.

2. **Migration gotcha**: Always make DB migrations idempotent:
   ```python
   if 'column_name' not in existing_columns:
       cursor.execute("ALTER TABLE ...")
   ```

3. **Extraction gotcha**: When moving functions between modules, grep for ALL import sites before committing.

---

## Checklist for Future Architectural Decisions

- [ ] Does this change affect all backends, or just some?
- [ ] Can the feature be optional (Protocol Extension pattern)?
- [ ] Am I adding to technical debt, or cleaning the path I'm walking?
- [ ] Does business logic live in the right layer?
- [ ] Are my migrations idempotent?

---

## References

- Dodo codebase: Plugin system with `extend_adapter`, `extend_formatter` hooks
- Python `@runtime_checkable` Protocol: https://docs.python.org/3/library/typing.html#typing.runtime_checkable
