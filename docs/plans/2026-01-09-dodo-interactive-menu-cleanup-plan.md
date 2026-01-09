# Interactive Menu Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clean up the interactive menu codebase to be "not ashamed to publish on GitHub" quality.

**Architecture:** Fix Python compatibility, eliminate dead code, extract constants, refactor long functions into testable classes, and standardize patterns across UI modules.

**Tech Stack:** Python 3.11+, Rich, readchar, simple-term-menu, pytest

---

## Phase 1: Quick Wins

### Task 1: Fix Python 3.12+ Syntax for 3.11 Compatibility

**Files:**
- Modify: `src/dodo/ui/rich_menu.py:12,152`

**Step 1: Run ruff to confirm the issue**

Run: `uv run --extra dev ruff check src/dodo/ui/rich_menu.py --select E999`
Expected: Error about type parameter syntax on line 152

**Step 2: Fix the TypeVar at top of file**

In `src/dodo/ui/rich_menu.py`, the existing `T = TypeVar("T")` on line 12 is correct.
Change line 152 from:
```python
class ListContext[T]:
```
to:
```python
class ListContext(Generic[T]):
```

Also add `Generic` to the import on line 3:
```python
from typing import Any, Generic, TypeVar
```

**Step 3: Run ruff to verify fix**

Run: `uv run --extra dev ruff check src/dodo/ui/rich_menu.py`
Expected: No errors (or only unrelated warnings)

**Step 4: Commit**

```bash
git add src/dodo/ui/rich_menu.py
git commit -m "fix: use Python 3.11 compatible Generic syntax for ListContext"
```

---

### Task 2: Extract Magic Numbers to Constants

**Files:**
- Modify: `src/dodo/ui/interactive.py`
- Modify: `src/dodo/ui/rich_menu.py`

**Step 1: Add constants to rich_menu.py**

Add after imports (around line 13):
```python
# UI Constants
LIVE_REFRESH_RATE = 20
DEFAULT_PANEL_WIDTH = 80
DEFAULT_TERMINAL_HEIGHT = 24
```

**Step 2: Replace magic numbers in rich_menu.py**

- Line 64-65: Replace `80` and `24` with `DEFAULT_PANEL_WIDTH` and `DEFAULT_TERMINAL_HEIGHT`
- Line 126: Replace `20` with `LIVE_REFRESH_RATE`

**Step 3: Add constants to interactive.py**

Add after imports (around line 15):
```python
# UI Constants
LIVE_REFRESH_RATE = 20
DEFAULT_PANEL_WIDTH = 80
DEFAULT_TERMINAL_HEIGHT = 24
STATUS_MSG_MAX_LEN = 30
CONFIG_DISPLAY_MAX_LEN = 35
```

**Step 4: Replace magic numbers in interactive.py**

- Line 110-111: Replace `80` and `24` with constants
- Line 211: Replace `20` with `LIVE_REFRESH_RATE`
- Lines 233, 241, 246, 249, 252, 275, 286: Replace `[:30]` with `[:STATUS_MSG_MAX_LEN]`
- Line 406: Replace `[:35]` with `[:CONFIG_DISPLAY_MAX_LEN]`

**Step 5: Run tests to verify nothing broke**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 6: Commit**

```bash
git add src/dodo/ui/interactive.py src/dodo/ui/rich_menu.py
git commit -m "refactor: extract magic numbers to named constants"
```

---

### Task 3: Move Inline Imports to Top of Module

**Files:**
- Modify: `src/dodo/ui/interactive.py`

**Step 1: Move imports from inside _todos_loop to top**

Move these imports from inside `_todos_loop` (lines 82-89, 207) to top of file with other imports:
```python
from dataclasses import dataclass

import readchar
from rich.live import Live
from rich.markup import escape
```

Note: `Console` and `Panel` are already imported at top.

**Step 2: Remove duplicate/inline imports from _todos_loop**

Remove these lines from inside `_todos_loop`:
- Lines 82-89 (the from/import block)
- Line 207 (`import readchar`)

**Step 3: Move import from inside _config_loop to top**

Move `import readchar` from line 420 (inside `_config_loop`) - it's now at top.

**Step 4: Run tests to verify nothing broke**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 5: Commit**

```bash
git add src/dodo/ui/interactive.py
git commit -m "refactor: move inline imports to module level"
```

---

### Task 4: Handle Dead InteractiveList Code

**Files:**
- Modify: `src/dodo/ui/rich_menu.py`

**Step 1: Add deprecation TODO comment**

Since `InteractiveList` was designed as an abstraction but never integrated, add a comment explaining the situation. Add above the class (around line 15):

```python
# TODO: InteractiveList is an unused abstraction. Options:
# 1. Delete if not needed
# 2. Refactor _todos_loop in interactive.py to use this
# Decision pending - keeping for potential Phase 2 refactor
```

**Step 2: Commit**

```bash
git add src/dodo/ui/rich_menu.py
git commit -m "docs: add TODO explaining unused InteractiveList abstraction"
```

---

## Phase 2: Core Improvements

### Task 5: Extract UndoAction Dataclass to models.py

**Files:**
- Modify: `src/dodo/models.py`
- Modify: `src/dodo/ui/interactive.py`
- Create: `tests/test_ui/__init__.py`
- Create: `tests/test_ui/test_undo.py`

**Step 1: Write the test for UndoAction**

Create `tests/test_ui/__init__.py`:
```python
"""UI tests."""
```

Create `tests/test_ui/test_undo.py`:
```python
"""Tests for UndoAction model."""

from datetime import datetime

from dodo.models import Status, TodoItem, UndoAction


def test_undo_action_toggle():
    """UndoAction stores toggle information."""
    item = TodoItem(
        id="abc123",
        text="Test todo",
        status=Status.PENDING,
        created_at=datetime.now(),
    )
    action = UndoAction(kind="toggle", item=item)
    assert action.kind == "toggle"
    assert action.item == item
    assert action.new_id is None


def test_undo_action_edit_with_new_id():
    """UndoAction stores edit with new ID."""
    item = TodoItem(
        id="abc123",
        text="Original text",
        status=Status.PENDING,
        created_at=datetime.now(),
    )
    action = UndoAction(kind="edit", item=item, new_id="def456")
    assert action.kind == "edit"
    assert action.new_id == "def456"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_undo.py -v`
Expected: FAIL with ImportError (UndoAction not defined)

**Step 3: Add UndoAction to models.py**

Add to `src/dodo/models.py` after TodoItem class:
```python
@dataclass
class UndoAction:
    """Represents an undoable action in the UI."""

    kind: str  # "toggle" | "delete" | "edit"
    item: TodoItem
    new_id: str | None = None  # For edit: track new ID after text change
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_undo.py -v`
Expected: PASS

**Step 5: Update interactive.py to use imported UndoAction**

In `src/dodo/ui/interactive.py`:
- Add to imports: `from dodo.models import Status, TodoItem, UndoAction`
- Remove the inline `@dataclass class UndoAction` definition (lines 93-97)
- Update the type hint on line 101: `undo_stack: list[UndoAction] = []`

**Step 6: Run all tests**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 7: Commit**

```bash
git add src/dodo/models.py src/dodo/ui/interactive.py tests/test_ui/
git commit -m "refactor: extract UndoAction to models.py for testability"
```

---

### Task 6: Standardize Console Usage

**Files:**
- Modify: `src/dodo/ui/interactive.py`

**Step 1: Remove redundant console creation in _todos_loop**

In `_todos_loop`, remove line 91:
```python
live_console = Console()
```

**Step 2: Replace live_console with console throughout _todos_loop**

Replace all occurrences of `live_console` with `console`:
- Line 110, 111: `console.width`, `console.height`
- Line 209: `console.clear()`
- Line 211: `console=console`
- Line 261: `console.clear()`

**Step 3: Run tests**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 4: Commit**

```bash
git add src/dodo/ui/interactive.py
git commit -m "refactor: use module-level console consistently in _todos_loop"
```

---

### Task 7: Add Editor Failure Feedback

**Files:**
- Modify: `src/dodo/ui/interactive.py`

**Step 1: Update _edit_in_editor to show fallback message**

In `_edit_in_editor` function, update the fallback logic (around lines 340-349):

```python
        except (FileNotFoundError, OSError, subprocess.CalledProcessError) as e:
            # Editor failed, try fallbacks
            original_editor = editor
            for fallback in ["nano", "vi"]:
                try:
                    subprocess.run([fallback, tmp_path], check=True)
                    console.print(f"[yellow]Note:[/yellow] '{original_editor}' failed, used {fallback}")
                    break
                except (FileNotFoundError, OSError):
                    continue
            else:
                console.print(f"[red]Error:[/red] No editor found (tried {editor}, nano, vi)")
                return None
```

**Step 2: Run tests**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 3: Commit**

```bash
git add src/dodo/ui/interactive.py
git commit -m "fix: show feedback when configured editor fails and fallback is used"
```

---

### Task 8: Standardize KeyboardInterrupt Handling

**Files:**
- Modify: `src/dodo/ui/interactive.py`
- Create: `tests/test_ui/test_keyboard_interrupt.py`

**Step 1: Document the intended behavior**

The intended behavior for KeyboardInterrupt:
- In menu selection: return `None` (cancel selection)
- In todo loop: exit cleanly to main menu
- In config loop: exit cleanly to main menu

This is already mostly consistent. The only issue is `_config_loop` uses `break` in the inner loop which only exits that loop, not the outer one.

**Step 2: Fix _config_loop KeyboardInterrupt handling**

In `_config_loop`, around line 427-428, change:
```python
                except KeyboardInterrupt:
                    break
```
to:
```python
                except KeyboardInterrupt:
                    return  # Exit config cleanly
```

**Step 3: Run tests**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 4: Commit**

```bash
git add src/dodo/ui/interactive.py
git commit -m "fix: standardize KeyboardInterrupt to exit config menu cleanly"
```

---

## Phase 3: Architectural Improvements

### Task 9: Extract build_display Logic to Shared Utility

**Files:**
- Create: `src/dodo/ui/panel_builder.py`
- Modify: `src/dodo/ui/interactive.py`
- Modify: `src/dodo/ui/rich_menu.py`
- Create: `tests/test_ui/test_panel_builder.py`

**Step 1: Write tests for panel builder**

Create `tests/test_ui/test_panel_builder.py`:
```python
"""Tests for panel builder utilities."""

from dodo.ui.panel_builder import calculate_visible_range, format_scroll_indicator


def test_calculate_visible_range_no_scroll():
    """No scroll needed when items fit."""
    start, end = calculate_visible_range(
        cursor=2, total_items=5, max_visible=10, scroll_offset=0
    )
    assert start == 0
    assert end == 5


def test_calculate_visible_range_scroll_down():
    """Scroll down when cursor exceeds visible area."""
    start, end = calculate_visible_range(
        cursor=15, total_items=20, max_visible=10, scroll_offset=0
    )
    assert start == 6  # Scrolled to show cursor
    assert end == 16


def test_format_scroll_indicator_above():
    """Show count of items above."""
    result = format_scroll_indicator(hidden_above=5, hidden_below=0)
    assert "↑ 5 more" in result


def test_format_scroll_indicator_below():
    """Show count of items below."""
    result = format_scroll_indicator(hidden_above=0, hidden_below=3)
    assert "↓ 3 more" in result
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_panel_builder.py -v`
Expected: FAIL with ImportError

**Step 3: Create panel_builder.py**

Create `src/dodo/ui/panel_builder.py`:
```python
"""Shared utilities for building Rich panels with scrolling lists."""


def calculate_visible_range(
    cursor: int,
    total_items: int,
    max_visible: int,
    scroll_offset: int,
) -> tuple[int, int, int]:
    """Calculate visible range for a scrolling list.

    Args:
        cursor: Current cursor position
        total_items: Total number of items
        max_visible: Maximum items that fit on screen
        scroll_offset: Current scroll offset

    Returns:
        Tuple of (new_scroll_offset, visible_start, visible_end)
    """
    if total_items == 0:
        return 0, 0, 0

    # Adjust scroll to keep cursor visible
    if cursor < scroll_offset:
        scroll_offset = cursor
    elif cursor >= scroll_offset + max_visible:
        scroll_offset = cursor - max_visible + 1

    scroll_offset = max(0, min(scroll_offset, total_items - 1))
    visible_end = min(scroll_offset + max_visible, total_items)

    return scroll_offset, scroll_offset, visible_end


def format_scroll_indicator(hidden_above: int, hidden_below: int) -> tuple[str | None, str | None]:
    """Format scroll indicators.

    Returns:
        Tuple of (above_indicator, below_indicator) - None if no items hidden
    """
    above = f"[dim]  ↑ {hidden_above} more[/dim]" if hidden_above > 0 else None
    below = f"[dim]  ↓ {hidden_below} more[/dim]" if hidden_below > 0 else None
    return above, below
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_panel_builder.py -v`
Expected: PASS

**Step 5: Update __init__.py exports**

In `src/dodo/ui/__init__.py`, add:
```python
from .panel_builder import calculate_visible_range, format_scroll_indicator
```

And update `__all__`:
```python
__all__ = [
    "MenuUI",
    "RichTerminalMenu",
    "interactive_menu",
    "interactive_config",
    "calculate_visible_range",
    "format_scroll_indicator",
]
```

**Step 6: Commit**

```bash
git add src/dodo/ui/panel_builder.py src/dodo/ui/__init__.py tests/test_ui/test_panel_builder.py
git commit -m "feat: add shared panel builder utilities for scrolling lists"
```

---

### Task 10: Integrate Panel Builder into _todos_loop

**Files:**
- Modify: `src/dodo/ui/interactive.py`

**Step 1: Import panel builder utilities**

Add to imports in `interactive.py`:
```python
from dodo.ui.panel_builder import calculate_visible_range, format_scroll_indicator
```

**Step 2: Refactor build_display to use utilities**

In `_todos_loop`, update the `build_display` function's scroll logic (around lines 130-166) to use the new utilities:

```python
        # Calculate visible range
        new_offset, visible_start, visible_end = calculate_visible_range(
            cursor=cursor,
            total_items=len(items),
            max_visible=max_items,
            scroll_offset=scroll_offset,
        )
        scroll_offset = new_offset

        # Add scroll indicators
        above_indicator, below_indicator = format_scroll_indicator(
            hidden_above=scroll_offset,
            hidden_below=len(items) - visible_end,
        )
        if above_indicator:
            lines.append(above_indicator)

        for i in range(visible_start, visible_end):
            # ... existing item rendering ...

        if below_indicator:
            lines.append(below_indicator)
```

**Step 3: Run tests**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 4: Commit**

```bash
git add src/dodo/ui/interactive.py
git commit -m "refactor: use panel_builder utilities in _todos_loop"
```

---

### Task 11: Integrate Panel Builder into InteractiveList

**Files:**
- Modify: `src/dodo/ui/rich_menu.py`

**Step 1: Import panel builder utilities**

Add to imports in `rich_menu.py`:
```python
from dodo.ui.panel_builder import calculate_visible_range, format_scroll_indicator
```

**Step 2: Refactor build_panel to use utilities**

In `InteractiveList.show()`, update the `build_panel` function (around lines 78-97):

```python
            # Calculate visible range
            new_offset, visible_start, visible_end = calculate_visible_range(
                cursor=self.cursor,
                total_items=len(self.items),
                max_visible=max_items,
                scroll_offset=self.scroll_offset,
            )
            self.scroll_offset = new_offset

            above_indicator, below_indicator = format_scroll_indicator(
                hidden_above=self.scroll_offset,
                hidden_below=len(self.items) - visible_end,
            )
            if above_indicator:
                lines.append(above_indicator)

            for i in range(visible_start, visible_end):
                selected = i == self.cursor
                rendered = self.render_item(self.items[i], selected)
                lines.append(rendered)

            if below_indicator:
                lines.append(below_indicator)
```

**Step 3: Run tests**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 4: Commit**

```bash
git add src/dodo/ui/rich_menu.py
git commit -m "refactor: use panel_builder utilities in InteractiveList"
```

---

### Task 12: Final Cleanup - Run Full Test Suite and Lint

**Files:**
- All modified files

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 2: Run ruff**

Run: `uv run --extra dev ruff check src/dodo/ui/ --fix`
Expected: No errors (or auto-fixed)

**Step 3: Run mypy**

Run: `uv run --extra dev mypy src/dodo/ui/`
Expected: No errors (some warnings OK given mypy config)

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup after interactive menu refactor"
```

---

## Summary

After completing all tasks:

| Metric | Before | After |
|--------|--------|-------|
| Python 3.11 compatible | No | Yes |
| Magic numbers | 15+ | 0 |
| Dead code documented | No | Yes |
| UndoAction testable | No | Yes |
| Shared scroll logic | Duplicated | DRY |
| Editor failure feedback | Silent | Visible |
| KeyboardInterrupt handling | Inconsistent | Standardized |

**Files modified:**
- `src/dodo/ui/rich_menu.py`
- `src/dodo/ui/interactive.py`
- `src/dodo/ui/__init__.py`
- `src/dodo/models.py`

**Files created:**
- `src/dodo/ui/panel_builder.py`
- `tests/test_ui/__init__.py`
- `tests/test_ui/test_undo.py`
- `tests/test_ui/test_panel_builder.py`
