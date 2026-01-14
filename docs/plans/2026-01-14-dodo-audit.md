# Code Audit: Dodo Project

**Date**: 2026-01-14
**Scope**: Recent changes (directory mapping, priority/tags display, ntfy-inbox priority parsing)
**Health Score**: Needs Work

## Executive Summary

The recent changes implement directory-to-dodo mapping and priority/tags display across formatters. The core functionality works, but there are several edge cases with silent failures, inconsistent tag limits across components, and a scroll calculation bug in the UI. Quick wins are available in consistent constants and input validation.

## Findings by Category

### Dead Code

No dead code identified in the reviewed changes.

### Code Smells

**Regex imported inside functions** (inbox.py:62)
- `re.findall` is called but `re` is imported at module level - this is fine
- However, repeated regex compilation could be optimized with `re.compile` at module level

**Magic numbers for tag limits**
- 5 tags in ntfy-inbox parsing (inbox.py:64)
- 3 tags in tree formatter (tree.py `_format_tags`)
- 2 tags in interactive UI
- Should be a single constant

### DRY Violations

**Priority formatting duplicated**
- `format_priority()` in `interactive.py`
- `_format_priority()` in `tree.py`
- Same logic with slightly different Rich markup

**Tag formatting duplicated**
- `format_tags()` in `interactive.py`
- `_format_tags()` in `tree.py`
- Same logic with different tag count limits

### Coupling & Modularity

**resolve_dodo return value complexity**
- Returns `tuple[str | None, Path | None]` with multiple meanings
- `(None, None)` = global
- `(name, path)` = explicit path
- `(name, None)` = use project storage
- Consider a dataclass or named tuple for clarity

### Clarity & Maintainability

**Silent failures in directory mapping** (resolve.py:77-80)
- If mapped dodo path doesn't exist, silently falls through to other detection
- User may not realize their mapping is broken

**_remove_by_id input handling** (interactive.py)
- No validation that input is numeric before int() conversion
- Will raise ValueError on invalid input (caught by try/except but not user-friendly)

### Error Handling

**DODO_DIR environment variable silently ignored**
- If the path doesn't exist, detection falls through without warning

**Curses state not always restored**
- If exception occurs in interactive mode, terminal state may not be properly restored

## Priority Matrix

| Category | Severity | Effort | Recommended Action |
|----------|----------|--------|-------------------|
| Tag limit inconsistency | Medium | Small | Create shared constant |
| Priority/tag format duplication | Medium | Small | Extract to shared module |
| Silent mapping failures | High | Small | Add warning when mapping invalid |
| _remove_by_id validation | Medium | Small | Validate numeric input |
| resolve_dodo return type | Low | Medium | Consider dataclass |
| Terminal state restoration | Medium | Medium | Add finally block |

## Recommended Cleanup Plan

### Phase 1: Quick Wins (Low effort, high impact)

1. **Create shared constants for tag limits**
   - Add `MAX_DISPLAY_TAGS = 3` to a constants module
   - Update tree.py, interactive.py, inbox.py to use it

2. **Extract priority/tag formatting to shared module**
   - Create `src/dodo/ui/formatting.py`
   - Move `format_priority()` and `format_tags()` there
   - Update tree.py and interactive.py to import from shared module

3. **Add warning for invalid directory mappings**
   - In resolve.py, log warning when mapped path doesn't exist
   - Helps users diagnose broken mappings

4. **Validate _remove_by_id input**
   - Check `remove_buffer.isdigit()` before conversion
   - Show error message for invalid input

### Phase 2: Core Improvements

5. **Improve resolve_dodo return type**
   - Create `@dataclass ResolvedDodo` with clear fields
   - `dodo_name`, `storage_path`, `source` (enum: mapping/local/git/global)

6. **Add terminal state restoration**
   - Wrap interactive loop in try/finally
   - Ensure cursor visibility and terminal settings restored

### Phase 3: Architectural Changes

7. **Consider unified formatter interface**
   - Abstract base class for formatters
   - Consistent priority/tag handling across all output formats

## Files Reviewed

- src/dodo/cli.py (link/unlink commands, _resolve_dodo usage)
- src/dodo/cli_context.py (get_service_context with resolve_dodo)
- src/dodo/config.py (directory mapping methods)
- src/dodo/resolve.py (_auto_detect_dodo with mappings)
- src/dodo/ui/interactive.py (remove mode, priority/tags toggles)
- src/dodo/plugins/graph/tree.py (priority/tags in tree output)
- src/dodo/plugins/ntfy_inbox/inbox.py (priority prefix/tag parsing)
