# Code Audit: Backend Restructure Branch

**Date**: 2026-01-12
**Scope**: Files changed in feature/backend-restructure (18 commits, 37 files)
**Health Score**: Needs Work
**Auditors**: Gemini 0.23.0, Codex 0.80.0

## Executive Summary

The restructure is well-executed with clean terminology changes and good test coverage. However, both auditors identified **data integrity risks** (race conditions, ID collisions), **coupling issues** (hardcoded paths, private attribute access), and **incomplete features** (migration stub). The highest priority items are the ID collision risk and file locking for markdown backends.

## Findings by Category

### High Severity

#### 1. ID Collision Risk (Gemini + Codex)
**Files:** `src/dodo/backends/utils.py:18`, `src/dodo/backends/markdown.py`
**Issue:** `generate_todo_id` uses `sha1(text + timestamp_minute_precision)`. Adding identical tasks within the same minute produces duplicate IDs.
**Impact:** Duplicate IDs cause unpredictable delete/update behavior.
**Fix:** Include random salt or nanosecond precision in hash input.

#### 2. Race Conditions in File Backends (Gemini)
**Files:** `src/dodo/backends/markdown.py`, `src/dodo/plugins/obsidian/backend.py`
**Issue:** Read-modify-write cycles without file locking.
**Impact:** Data loss when concurrent processes (or external editors) modify the file.
**Fix:** Implement file locking (`flock` or lockfile) during write operations.

### Medium Severity

#### 3. Project Config Path Mismatch (Codex)
**Files:** `src/dodo/cli.py:430`, `src/dodo/core.py:130`
**Issue:** `backend` command writes to `config_dir/projects` even when `local_storage=true`, but core looks in `.dodo/`.
**Impact:** Backend selection ignored for local storage projects.
**Fix:** Centralize path calculation in `project_config.py` and use everywhere.

#### 4. Hardcoded Config Dir in CLI (Codex)
**Files:** `src/dodo/cli.py:61`, `src/dodo/cli.py:76`
**Issue:** Plugin command routing hardcodes `~/.config/dodo`, bypassing Config.load().
**Impact:** Custom config dirs and `DODO_*` env overrides not respected.
**Fix:** Use `Config.load().config_dir` consistently.

#### 5. Graph Plugin Tight Coupling (Gemini + Codex)
**Files:** `src/dodo/plugins/graph/cli.py`, `src/dodo/plugins/graph/__init__.py`
**Issue:** Hard-checks for SQLite backend and accesses private `_backend` attribute.
**Impact:** Brittle to refactors, violates TodoBackend protocol abstraction.
**Fix:** Define a `GraphCapable` protocol/mixin and check with `isinstance`.

#### 6. SQLite Connection Overhead (Gemini)
**Files:** `src/dodo/backends/sqlite.py`
**Issue:** New connection opened/closed for every operation.
**Impact:** Performance overhead, especially for batch operations.
**Fix:** Connection pooling or reuse within a command execution.

#### 7. Inconsistent ID Behavior on Edit (Codex)
**Files:** `src/dodo/backends/markdown.py:82`, `src/dodo/backends/sqlite.py`
**Issue:** `update_text` in markdown generates new ID (hash changes), but sqlite keeps stable ID.
**Impact:** Cross-backend inconsistency; references break on edit in markdown.
**Fix:** Keep IDs stable across all backends (use UUID or random component).

#### 8. Ntfy Plugin Subprocess Inefficiency (Gemini)
**Files:** `src/dodo/plugins/ntfy_inbox/inbox.py`
**Issue:** Spawns new `subprocess.run(["dodo", ...])` for every message.
**Impact:** Performance overhead, startup cost per message.
**Fix:** Use `TodoService` directly within the same process.

### Low Severity

#### 9. Unimplemented Migration (Gemini + Codex)
**Files:** `src/dodo/cli.py` (`backend` command)
**Issue:** `--migrate` flag prints "not yet implemented".
**Fix:** Implement using `export_all`/`import_all` or remove flag until ready.

#### 10. Unused Code: ProjectConfig.ensure (Codex)
**Files:** `src/dodo/project_config.py:42`
**Issue:** `ensure()` method is defined but never called.
**Fix:** Remove or integrate into core backend resolution.

#### 11. Info Command Shows Global Default (Codex)
**Files:** `src/dodo/cli.py:405`
**Issue:** Shows `cfg.default_backend` not the resolved project backend.
**Fix:** Surface resolved backend from TodoService.

#### 12. DRY Violation in Graph Plugin (Codex)
**Files:** `src/dodo/plugins/graph/__init__.py:67,85`
**Issue:** `register_commands` and `register_root_commands` duplicate setup logic.
**Fix:** Extract shared builder function.

## Priority Matrix

| Issue | Severity | Effort | Action |
|-------|----------|--------|--------|
| ID Collision Risk | High | Small | Add random salt to ID generation |
| File Backend Race Conditions | High | Medium | Add file locking |
| Project Config Path Mismatch | Medium | Small | Centralize path helper |
| Hardcoded Config Dir | Medium | Small | Use Config.load() |
| Graph Plugin Coupling | Medium | Medium | Define GraphCapable protocol |
| SQLite Connection Overhead | Medium | Medium | Connection reuse |
| Inconsistent ID on Edit | Medium | Medium | Stabilize IDs |
| Ntfy Subprocess | Medium | Small | Use TodoService directly |
| Unimplemented Migration | Low | Medium | Implement or remove flag |
| Unused ProjectConfig.ensure | Low | Small | Remove or use |
| Info Shows Wrong Backend | Low | Small | Use resolved backend |
| Graph DRY Violation | Low | Small | Extract builder |

## Recommended Cleanup Plan

### Phase 1: Quick Wins (Low effort, high impact)
1. **Fix ID collision** - Add random component to `generate_todo_id`
2. **Fix config path hardcoding** - Use `Config.load().config_dir` in CLI
3. **Centralize project config path** - Add helper to `project_config.py`
4. **Remove or use `ProjectConfig.ensure`**

### Phase 2: Core Improvements
1. **Add file locking** to markdown backend
2. **Stabilize IDs on edit** for markdown/obsidian
3. **Fix info command** to show resolved backend
4. **Implement migration** or remove `--migrate` flag

### Phase 3: Architectural Changes
1. **Define GraphCapable protocol** for graph plugin
2. **Add connection pooling** to SQLite backend
3. **Refactor ntfy plugin** to use internal API
4. **Extract shared builder** in graph plugin registration
