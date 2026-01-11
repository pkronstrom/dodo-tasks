# Learnings: Interactive UI Enhancements

**Date**: 2025-01-11
**Objective**: Enhance dodo's interactive TUI with quick-add, improved projects menu, and various UX polish
**Outcome**: Success - All requested features implemented with several bug fixes along the way

## Summary

This session focused on TUI improvements for the dodo todo app: inline quick-add input, projects menu enhancements (filtering, actions, path display), and fixing various bugs discovered during testing. Key insight: when building interactive UIs with Rich's Live context, manual keystroke capture with `readchar` works well for modal input without leaving the panel.

## What We Tried

### Approach 1: Quick-Add Outside Live Context
- **Description**: Initially implemented quick-add input below the Rich panel
- **Result**: Failed
- **Why**: User wanted input to appear inside the panel as a bullet item, not outside/below

### Approach 2: Quick-Add Inside Live Context with Manual Keystroke Capture
- **Description**: Added `input_mode` flag, captured keystrokes with `readchar`, rendered input as a bullet item with blinking cursor
- **Result**: Worked
- **Why**: Rich's Live context can render any content including input fields; readchar handles raw input cleanly

### Approach 3: Sort Order DESC (newest first)
- **Description**: SQLite used `ORDER BY created_at DESC`, putting new items at top
- **Result**: Changed per user preference
- **Why**: User wanted new items at bottom to align with quick-add input appearing at bottom of list

## Final Solution

### Quick-Add Feature
- `a` key enters input mode
- Input renders as `> ○ text_` with blinking cursor inside the panel
- Footer changes to show `enter save · esc cancel`
- After saving, cursor jumps to end (new item at bottom)
- `A` key still opens editor for longer entries

### Projects Menu Enhancements
- Renamed to "Projects" (from "Switch Project")
- Added filtering: shows current-dir relevant projects by default with toggle for all
- Added actions: `o` manage todos, `l` open location, `d` delete with confirmation
- Shortened paths: removes `~/.config/dodo/projects/` prefix for cleaner display
- "New" option shows no path (was showing confusing template path)

### Bug Fixes
- Fixed double cursor during input mode
- Fixed list collapsing after adding (cursor clamping in scroll calculation)
- Fixed delete not finding files with different backend (checks both .db and .md)
- Added error handling for delete operations

## Key Learnings

- Rich's `Live` context works well with manual keystroke capture for modal input
- `calculate_visible_range` must clamp cursor BEFORE calculating scroll offset, not after
- Projects can have mismatched backends (created with markdown, now using sqlite) - always check for both file types
- Path display in menus should be concise - showing full `~/.config/dodo/projects/xxx/dodo.db` is redundant when project name already visible
- `\033[H\033[J` (move to top + clear) is better than just `\033[H` (move to top) when UI elements collapse

## Issues & Resolutions

| Issue | Root Cause | Resolution |
|-------|------------|------------|
| Double cursor when adding | Selection marker shown during input mode | Added `and not input_mode` check to selection display |
| List collapses after add | Cursor set to 999999, scroll calculated before clamping | Added cursor clamping at start of `calculate_visible_range` |
| Can't delete some projects | Backend mismatch - looking for .db when project has .md | Check for both file extensions on delete |
| Ghost image when hiding projects | Screen not fully cleared | Changed `\033[H` to `\033[H\033[J` |
| "New" option wraps badly | Showing full template path | Removed path display for "New" option |

## User Steering

Key moments where user direction shaped the outcome:

| User Said | Impact | Lesson for Next Time |
|-----------|--------|---------------------|
| "input should be inside the rectangle, not outside/below" | Redesigned to render input as bullet item inside panel | Ask upfront: "inline in panel or separate input area?" |
| "change sort so newest at bottom" | Changed SQLite from DESC to ASC | Ask about sort preference when it affects UX |
| "should we compact the paths somehow" | Simplified `_shorten_path` to remove config dir prefix | Default to concise paths, don't show redundant info |
| "rethink this at some point" (re: adapter design) | Noted as future work, added to todos | Some design issues are okay to defer with acknowledgment |
| "l shows file in dir but can't delete" | Revealed backend mismatch bug | Test with projects created under different configurations |

## Gotchas & Warnings

- **Backend mismatch**: Projects created with one adapter (markdown) may exist while user's current config uses another (sqlite). Always check for both file types.
- **Cursor position after add**: New items may sort to different positions depending on sort order. Set cursor based on where item will actually appear.
- **Screen clearing in alternate buffer**: When using `console.screen()`, partial clears can leave ghost images. Use full clear `\033[J` when UI structure changes.
- **Path.with_suffix vs Path.with_name**: `with_suffix(".db")` changes extension; `with_name("dodo.db")` replaces entire filename. Easy to confuse.

## References

- `/src/dodo/ui/interactive.py` - Main interactive UI implementation
- `/src/dodo/ui/panel_builder.py` - Scroll calculation utilities
- `/src/dodo/plugins/sqlite/adapter.py` - SQLite adapter with sort order
- Rich library docs for Live context and Panel rendering
- `readchar` library for raw keystroke capture
