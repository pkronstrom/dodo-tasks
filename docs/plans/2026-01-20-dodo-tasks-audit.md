# Code Audit: dodo-tasks

**Date**: 2026-01-20
**Scope**: Full codebase audit of `src/dodo/`
**Health Score**: Needs Work
**Audited by**: Codex (gpt-5.2-codex), Gemini (gemini-2.5-pro)

## Executive Summary

The codebase is functional and well-structured but has accumulated technical debt. The main concerns are: a monolithic CLI module that mixes too many responsibilities, duplicated dodo resolution logic across 5+ modules, unused dead code, and inconsistent error handling that can silently fail. Quick wins include removing dead code and fixing the undefined `project_id` variable bug.

## Findings by Category

### Dead Code

| Issue | Severity | Effort | Details |
|-------|----------|--------|---------|
| Unused `_detect_project` and `_resolve_project` in cli.py | Low | Small | Functions defined but never called; mislead readers and add maintenance cost |
| Unused `ConfigMeta.SETTINGS` in config.py | Low | Small | Stale metadata suggests abandoned UI feature; risks drift |
| Unused `worktree_shared` parameter | Low | Small | Accepted in `storage.py` and `project_config.py` but never used; implies unimplemented behavior |

**Why it matters**: Dead code increases cognitive load when navigating the codebase and creates false assumptions about what's actually being used.

### Code Smells

| Issue | Severity | Effort | Details |
|-------|----------|--------|---------|
| `cli.py` is a god module | Med | Large | Mixes CLI commands, plugin routing, undo serialization, and config resolution (~1200+ lines) |
| `ui/interactive.py` has deeply nested `_todos_loop` | Med | Large | Heavy nesting with mutable state makes testing and reasoning difficult |
| `core.py` uses dynamic backend instantiation | Med | Med | String registries and `inspect`-based constructor probing make debugging brittle |

**Why it matters**: God modules are hard to test, understand, and modify safely. Changes in one area can unexpectedly affect others.

### DRY Violations

| Issue | Severity | Effort | Details |
|-------|----------|--------|---------|
| Dodo resolution duplicated across 5+ files | Med | Med | `cli.py`, `cli_bulk.py`, `ui/interactive.py`, `cli_context.py`, `plugins/ai/cli.py` all have similar resolution logic with subtle differences |
| Undo state persistence duplicated | Low | Small | Both `cli.py` and `cli_bulk.py` save undo state with slightly different formats |
| Priority/tag parsing repeated | Low | Small | Parsing logic in CLI, bulk commands, and AI plugin with inconsistent validation |

**Why it matters**: Duplicated logic means bugs must be fixed in multiple places and behavior can diverge unexpectedly.

### Coupling & Modularity

| Issue | Severity | Effort | Details |
|-------|----------|--------|---------|
| Private backend internals accessed directly | Med | Med | `cli.py` and `core.py` access `_backend`, `_path` bypassing service layer |
| GraphWrapper coupled to SQLite schema | Med | Med | Assumes `todos` table structure and backend `_path`; blocks other backends |
| Formatter discovery ignores `DODO_CONFIG_DIR` | Med | Small | `formatters/__init__.py` hardcodes `Path.home()` instead of using Config |

**Why it matters**: Tight coupling makes it hard to swap implementations, test in isolation, or evolve the architecture.

### Clarity & Maintainability

| Issue | Severity | Effort | Details |
|-------|----------|--------|---------|
| **Undefined `project_id` in backend command** | **High** | Small | `cli.py` backend command references `project_id` without defining it - runtime crash |
| Mismatched command name in warning | Low | Small | `resolve.py` warns about `dodo unlink` but CLI uses `dodo unuse` |
| Misleading `project` parameter in markdown backend | Low | Small | Accepts `project` but never filters by it; differs from SQLite behavior |
| Inconsistent naming: dodo/project_id/target | Low | Small | Ambiguous terms across modules complicate maintenance |

**Why it matters**: Clarity issues slow down development and cause user confusion. The undefined variable is a potential crash bug.

### Error Handling Gaps

| Issue | Severity | Effort | Details |
|-------|----------|--------|---------|
| Undo flows swallow exceptions | Med | Small | Silent failures in `cli.py` and `cli_bulk.py` can leave data partially updated |
| Name validation only on new/destroy | Med | Small | `--dodo` flag accepts unvalidated names; path traversal risk on other commands |
| Silent registry parse errors | Low | Small | `formatters/__init__.py` ignores JSON decode errors, masking corruption |

**Why it matters**: Silent failures are hard to debug and can leave the system in inconsistent states.

## Priority Matrix

| Category | Severity | Effort | Recommended Action |
|----------|----------|--------|-------------------|
| Undefined `project_id` bug | High | Small | Fix immediately - runtime crash |
| Name validation gap | Med | Small | Apply validation to all `--dodo` usage |
| Undo exception handling | Med | Small | Add proper error handling and user feedback |
| Dead code cleanup | Low | Small | Remove unused functions and params |
| Mismatched command names | Low | Small | Update warning message to say `dodo unuse` |
| DRY: dodo resolution | Med | Med | Centralize in `cli_context.py`, use everywhere |
| DRY: undo persistence | Low | Small | Extract to shared module |
| Formatter config coupling | Med | Small | Use Config class instead of hardcoded path |
| CLI god module | Med | Large | Split into focused modules |
| Interactive UI nesting | Med | Large | Refactor to reduce state and nesting |

## Recommended Cleanup Plan

### Phase 1: Quick Wins (Low effort, high impact)

1. **Fix undefined `project_id` bug** in `cli.py` backend command
2. **Remove dead code**: `_detect_project`, `_resolve_project`, `ConfigMeta.SETTINGS`
3. **Remove unused parameters**: `worktree_shared` in storage.py and project_config.py
4. **Fix warning message** in `resolve.py`: change "dodo unlink" to "dodo unuse"
5. **Apply name validation** to all commands accepting `--dodo` parameter

### Phase 2: Core Improvements

1. **Centralize dodo resolution**: Make `cli_context.py` the single source of truth
2. **Extract undo persistence** to shared module with consistent format
3. **Add proper error handling** to undo flows - don't swallow exceptions
4. **Fix formatter discovery** to use Config class and respect DODO_CONFIG_DIR
5. **Extract priority/tag parsing** to shared utilities with consistent validation

### Phase 3: Architectural Changes

1. **Split cli.py** into focused modules (commands, undo, utils)
2. **Refactor interactive.py** to reduce nesting and mutable state
3. **Add backend interface** for storage path instead of private attribute access
4. **Decouple GraphWrapper** from SQLite internals

## Open Questions

1. Is `DODO_CONFIG_DIR` intended to control plugin/formatter discovery everywhere?
2. Is Markdown backend meant to be single-project only? Should `project` param be removed?
3. Should direct `print` calls in library code be replaced by logging?

---

*Audit performed using Codex (gpt-5.2-codex) in read-only mode with 74,848 tokens analyzed.*
