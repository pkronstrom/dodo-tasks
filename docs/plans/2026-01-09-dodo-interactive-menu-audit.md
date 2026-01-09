# Code Audit: Dodo Interactive Menu

**Date**: 2026-01-09
**Scope**: Recent commits related to interactive menu functionality (~29 commits since d27bca7)
**Health Score**: Needs Work

## Executive Summary

The interactive menu code has functional UI but accumulated technical debt from iterative development. Main concerns: (1) **Python version compatibility bug** - uses 3.12+ syntax despite 3.11 requirement, (2) significant **code duplication** between `InteractiveList` and `_todos_loop`, (3) **dead code** - `InteractiveList` class is defined but never used, and (4) **magic numbers** scattered throughout. Quick wins available to improve maintainability without major refactoring.

## Findings by Category

### Dead Code

**`InteractiveList` and `ListContext` classes are never used** (`src/dodo/ui/rich_menu.py:15-176`)

These ~160 lines define a reusable interactive list component with customizable keybindings, but:
- No code imports or instantiates `InteractiveList`
- `_todos_loop` in `interactive.py` duplicates this functionality instead of using it
- Likely an abandoned abstraction attempt or intended future refactor

**Impact**: Adds maintenance burden, confuses developers about intended architecture.

### Code Smells

**1. Python 3.12+ syntax in 3.11-compatible codebase** (`rich_menu.py:152`)

```python
class ListContext[T]:  # PEP 695 syntax - Python 3.12+
```

The project declares `requires-python = ">=3.11"` but uses syntax only available in 3.12+. This will cause `SyntaxError` on Python 3.11.

**Impact**: Critical - breaks installation for 3.11 users.

**2. Long function: `_todos_loop`** (`interactive.py:80-291`)

This function is ~210 lines containing:
- A nested dataclass definition
- A nested function (`build_display`)
- Multiple nested while loops
- Editor integration
- Add mode handling

**Impact**: Hard to test, understand, and modify. Violates single responsibility.

**3. Long function: `_config_loop`** (`interactive.py:379-463`)

~85 lines with nested function and complex state management.

**4. Magic numbers throughout**

| Value | Occurrences | Meaning |
|-------|-------------|---------|
| `[:30]` | 7 times | Truncate status messages |
| `[:35]` | 1 time | Truncate config display |
| `20` | 2 times | `refresh_per_second` |
| `80`, `84`, `24` | Multiple | Terminal dimensions |
| `-6`, `-9`, `-3` | Multiple | Panel height calculations |

**5. Imports inside functions** (`interactive.py:82-89, 207`)

```python
def _todos_loop(...):
    from dataclasses import dataclass  # Line 82
    from rich.console import Console   # Line 84
    ...
    import readchar                     # Line 207
```

While sometimes intentional for lazy loading, here it adds inconsistency (same modules imported at top level elsewhere).

### DRY Violations

**1. Panel building logic duplicated**

`InteractiveList.build_panel()` (rich_menu.py:71-123) and `_todos_loop.build_display()` (interactive.py:105-201) share nearly identical:
- Scroll offset calculations
- Visible range computation
- "↑ N more" / "↓ N more" indicators
- Panel height calculations
- Line padding logic

**2. Status message formatting repeated**

Seven instances of `f"[dim]...{text[:30]}[/dim]"` pattern.

**3. Config.load() called repeatedly**

13+ calls to `Config.load()` across the codebase. While not always avoidable, some calls reload config unnecessarily (e.g., `interactive.py:265` reloads inside a loop).

### Coupling & Modularity

**1. `RichTerminalMenu` wraps `simple-term-menu` but `_todos_loop` uses raw `readchar`**

The `RichTerminalMenu` class provides a clean abstraction over `simple-term-menu`, but the todo management loop bypasses it entirely and uses `readchar` directly. This creates two parallel input handling approaches.

**2. `_todos_loop` tightly coupled to multiple concerns**
- UI rendering
- State management (undo stack)
- Editor integration
- Config loading
- Service calls

**3. `interactive_config` and `_config_loop` could be one class**

Similar to how `InteractiveList` was designed but abandoned.

### Clarity & Maintainability

**1. Inconsistent console usage**

- `interactive.py` creates `console = Console()` at module level (line 15)
- `_todos_loop` creates its own `live_console = Console()` (line 91)
- `_config_loop` uses the module-level `console`

**2. Complex control flow in `_todos_loop`**

Three nested while loops with multiple break/continue paths:
```python
while True:  # Outer loop - editor re-entry
    while True:  # Main input loop
        ...
        if edit_item:
            break  # Exit to editor
        elif add_mode:
            break  # Exit to add
        ...
    if add_mode:
        continue  # Re-enter
    if edit_item:
        continue  # Re-enter
    break  # Normal exit
```

**3. `UndoAction` dataclass defined inside function**

Makes it impossible to type-hint or test independently.

### Error Handling

**1. Silent editor fallback** (`interactive.py:340-349`)

If the configured editor fails, silently tries `nano`, then `vi`. User gets no feedback about why their editor didn't work.

**2. KeyboardInterrupt handling inconsistent**

- In `RichTerminalMenu.show()`: returns `None`
- In `_todos_loop`: calls `return` (exits function)
- In `_config_loop`: calls `break` (exits inner loop only)

## Priority Matrix

| Issue | Severity | Effort | Recommended Action |
|-------|----------|--------|-------------------|
| Python 3.12 syntax on 3.11 project | High | Small | Fix immediately - use `TypeVar` syntax |
| Dead `InteractiveList` code | Medium | Small | Delete or integrate |
| Magic numbers | Medium | Small | Extract constants |
| `_todos_loop` complexity | Medium | Medium | Extract nested dataclass, consider using `InteractiveList` |
| DRY violations in panel building | Medium | Medium | Use `InteractiveList` or extract shared logic |
| Imports inside functions | Low | Small | Move to top of module |
| Inconsistent error handling | Low | Small | Standardize KeyboardInterrupt behavior |
| Silent editor fallback | Low | Small | Add user feedback |

## Recommended Cleanup Plan

### Phase 1: Quick Wins (Low effort, high impact)

1. **Fix Python 3.12 syntax** - Change `class ListContext[T]:` to use `TypeVar` for 3.11 compatibility:
   ```python
   from typing import TypeVar, Generic
   T = TypeVar("T")
   class ListContext(Generic[T]):
   ```

2. **Extract magic numbers** - Create constants at module level:
   ```python
   STATUS_MSG_MAX_LEN = 30
   CONFIG_DISPLAY_MAX_LEN = 35
   LIVE_REFRESH_RATE = 20
   ```

3. **Move imports to top of modules** - Clean up `readchar`, `dataclass` imports in `_todos_loop`

4. **Delete or document `InteractiveList`** - Either:
   - Delete if not planned for use
   - Add TODO comment explaining future integration plan

### Phase 2: Core Improvements

1. **Extract `UndoAction` dataclass** - Move to `models.py` or top of `interactive.py`

2. **Refactor `_todos_loop` to use `InteractiveList`** - The class already exists with the right abstractions:
   ```python
   list_view = InteractiveList(
       items=items,
       keybindings={"d": delete_handler, " ": toggle_handler, ...}
   )
   ```

3. **Standardize console usage** - Use single console instance or pass as parameter

4. **Add editor failure feedback** - Print message when falling back to alternative editor

### Phase 3: Architectural Changes

1. **Create `TodoListUI` class** - Encapsulate `_todos_loop` functionality:
   - Separate state management from rendering
   - Make undo stack testable
   - Enable unit testing without terminal

2. **Create `ConfigUI` class** - Similar refactor for config menu

3. **Consider dependency injection for `Config`** - Pass config instead of calling `Config.load()` repeatedly
