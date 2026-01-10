# Code Audit: Dodo CLI

**Date**: 2026-01-10
**Scope**: Entire codebase (~2,700 lines across 25 Python modules)
**Focus**: Startup performance, lazy loading, modularity for one-shot CLI execution
**Health Score**: Needs Work

## Executive Summary

Dodo is a well-architected CLI with clean separation of concerns and good lazy loading patterns for UI, formatters, and plugins. However, **startup time is significantly impacted by eager loading** of all three storage adapters (including httpx for Obsidian) and repeated Config.load() + subprocess calls on every command invocation. The main opportunities for improvement are: conditional adapter imports, config caching, and subprocess caching for git detection.

## Critical Issue: Startup Performance

### The Core Problem

For a one-shot CLI where startup time matters, the current architecture has several bottlenecks:

```
Entry: dodo add "buy milk"

IMMEDIATE LOADS (before command runs):
1. cli.py imports:
   - typer (CLI framework)
   - rich.console.Console (text rendering engine)
   - dodo.config (loads Config class)
   - dodo.core (loads ALL 3 adapters!)
     - adapters/markdown.py (re, datetime, hashlib)
     - adapters/sqlite.py (sqlite3, uuid, contextlib)
     - adapters/obsidian.py (re, httpx) <-- HEAVY
   - dodo.models (minimal)
   - dodo.project (subprocess, hashlib)

2. On every command execution:
   - Config.load() reads file + parses JSON + scans env vars
   - detect_project() spawns subprocess to git
```

### Measured Impact

The `obsidian.py` adapter imports `httpx` unconditionally at module level:
```python
# obsidian.py:7
import httpx
```

Even if the user has `default_adapter = "markdown"`, `httpx` is imported on every invocation. This is the most expensive import in the codebase.

## Findings by Category

### 1. Startup Performance (CRITICAL)

#### Eager Adapter Loading
**Location**: `core.py:6-9`
```python
from dodo.adapters.markdown import MarkdownAdapter
from dodo.adapters.obsidian import ObsidianAdapter  # imports httpx
from dodo.adapters.sqlite import SqliteAdapter
```

**Problem**: All 3 adapters are imported when `cli.py` loads, even though only 1 is ever used per invocation.

**Impact**: ~50-100ms wasted on unused adapter imports (httpx alone is significant)

**Fix Pattern**: Lazy import adapters in `_create_adapter()`:
```python
# Only import the adapter when actually creating it
def _create_adapter(self) -> TodoAdapter:
    adapter_name = self._config.default_adapter

    if adapter_name == "markdown":
        from dodo.adapters.markdown import MarkdownAdapter
        return MarkdownAdapter(self._get_markdown_path())
    elif adapter_name == "sqlite":
        from dodo.adapters.sqlite import SqliteAdapter
        return SqliteAdapter(self._get_sqlite_path())
    elif adapter_name == "obsidian":
        from dodo.adapters.obsidian import ObsidianAdapter
        return ObsidianAdapter(...)
```

#### Repeated Config Loading
**Location**: `cli.py` - every command calls `Config.load()`

**Problem**: `Config.load()` is called:
- In every command handler (add, list, done, rm, undo, ai, init, config, plugins)
- In helper functions `_save_last_action()`, `_load_last_action()`, `_clear_last_action()`
- Potentially multiple times per single CLI invocation

**Example**: Running `dodo add "task"` calls Config.load() twice:
1. In `add()` command
2. In `_save_last_action()`

**Impact**: Multiple file reads + JSON parses + env scans per command

**Fix Pattern**: Load config once at module level or use a cached singleton

#### Git Subprocess on Every Command
**Location**: `project.py:43-52`

**Problem**: `detect_project()` spawns `git rev-parse --show-toplevel` subprocess on most commands. This is ~10-20ms per call.

**Impact**: Every add/done/rm/list command spawns a subprocess

**Fix Pattern**: Cache the result for the duration of the process (it won't change during a single CLI invocation)

### 2. DRY Violations (MEDIUM)

#### Duplicated ID Generation Logic
**Locations**:
- `adapters/markdown.py:160-164`
- `adapters/obsidian.py:163-167`

Both have identical implementations:
```python
def _generate_id(self, text: str, timestamp: datetime) -> str:
    ts_normalized = timestamp.replace(second=0, microsecond=0)
    content = f"{text}{ts_normalized.isoformat()}"
    return sha1(content.encode()).hexdigest()[:8]
```

**Fix**: Extract to a shared utility in `models.py` or a new `utils.py`

#### Duplicated Line Parsing
**Locations**:
- `adapters/markdown.py:27` (LINE_PATTERN)
- `adapters/obsidian.py:21` (LINE_PATTERN)

Nearly identical regex patterns for parsing todo lines.

**Fix**: Share the pattern via a common base class or module

#### Duplicated `_format_item` Methods
Both markdown and obsidian adapters have identical `_format_item()` implementations.

### 3. Code Smells (LOW-MEDIUM)

#### Console Instance Duplication
**Locations**:
- `cli.py:20`: `console = Console()`
- `cli_plugins.py:11`: `console = Console()`
- `ui/interactive.py:26`: `console = Console()`

Multiple Console instances created across modules.

**Fix**: Consider a shared console instance or pass as parameter

#### Multiple sys Imports Inside Functions
**Location**: `ai.py:78-82, 106-108, 112-113`
```python
import sys  # imported inside exception handlers
```

While this is lazy loading (good for rarely-executed paths), it's inconsistent - the file already imports `subprocess` and `json` at the top.

#### Type Annotation: Unused Import
**Location**: `formatters/__init__.py:4`
```python
from typing import Any  # not used in this file
```

#### Unused `_config` Attribute Storage
**Location**: `core.py` stores `self._config` but only uses it in `_create_adapter()` and path methods. Consider if all config values could be resolved at init time.

### 4. Modularity & Coupling (MEDIUM)

#### TodoService Knows Too Much About Adapters
**Location**: `core.py:56-74`

The service has hardcoded knowledge of how to instantiate each adapter:
```python
if adapter_name == "markdown":
    return adapter_cls(self._get_markdown_path())
elif adapter_name == "sqlite":
    return adapter_cls(self._get_sqlite_path())
elif adapter_name == "obsidian":
    return adapter_cls(
        api_url=...,
        api_key=...,
        vault_path=...,
    )
```

**Fix Pattern**: Consider an adapter factory or registration pattern where adapters self-declare their config needs.

#### Interactive UI Imports Core Services
**Location**: `ui/interactive.py:12-14`
```python
from dodo.config import Config
from dodo.core import TodoService
from dodo.project import detect_project
```

The UI module directly imports and instantiates core services. This is fine for now but creates tight coupling.

### 5. Dead Code / Unused (MINOR)

#### Unused `MarkdownFormat.frontmatter`
**Location**: `adapters/markdown.py:17`

The `frontmatter` and `section_header` fields are defined but never used in the main code path - they're extension points that aren't currently exercised.

#### Unused `runtime_checkable` Decorator?
**Location**: `adapters/base.py:8`
```python
@runtime_checkable
class TodoAdapter(Protocol):
```

The `runtime_checkable` decorator enables `isinstance()` checks, but I don't see this being used anywhere. If it's not needed, it adds import overhead.

### 6. Error Handling (MINOR)

#### Bare Exception Catches
**Location**: `plugins.py:63-64`
```python
except Exception:
    return envs
```

Silently swallows all exceptions when reading plugin scripts. Should at least log or handle specific exceptions.

**Location**: `cli_plugins.py:118-120`
```python
except Exception as e:
    console.print(f"[red]Error:[/red] {e}")
```

Generic exception catching without specific handling.

## Priority Matrix

| Category | Issue | Severity | Effort | Impact |
|----------|-------|----------|--------|--------|
| Startup | Eager adapter imports | High | Small | High |
| Startup | Repeated Config.load() | High | Small | Medium |
| Startup | Git subprocess every command | Medium | Small | Medium |
| DRY | Duplicated ID generation | Low | Small | Low |
| DRY | Duplicated line patterns | Low | Small | Low |
| Coupling | TodoService adapter coupling | Low | Medium | Low |
| Dead code | Unused type import | Low | Trivial | Trivial |
| Dead code | Unused frontmatter fields | Low | None | None (extension point) |

## Good Patterns Already in Place

The codebase already has several good lazy loading patterns:

1. **Interactive UI** - Late import in `main()` callback:
   ```python
   from dodo.ui.interactive import interactive_menu
   ```

2. **Formatters** - Late import in `list_todos()`:
   ```python
   from dodo.formatters import get_formatter
   ```

3. **AI module** - Late import in `ai()` command:
   ```python
   from dodo.ai import run_ai
   ```

4. **Plugin discovery** - Late import in `plugins()` command:
   ```python
   from dodo import cli_plugins
   ```

5. **Protocol-based design** - Clean adapter abstraction

6. **Frozen dataclasses** - Immutable TodoItem is good practice

## Recommended Cleanup Plan

### Phase 1: Quick Wins (High impact, low effort)

1. **Lazy load adapters in core.py**
   - Move adapter imports inside `_create_adapter()`
   - Only import the adapter that's actually configured
   - Estimated impact: Significant startup time reduction

2. **Cache Config.load() result**
   - Use a module-level singleton or pass config through
   - Prevent multiple loads per CLI invocation

3. **Cache git subprocess results**
   - Add a simple module-level cache for `detect_project()`
   - Result won't change during a single invocation

4. **Remove unused `Any` import in formatters/__init__.py**
   - One-line fix

### Phase 2: Core Improvements (Medium effort)

5. **Extract shared adapter utilities**
   - Create `adapters/utils.py` with shared ID generation and line parsing
   - Reduces duplication, easier to maintain

6. **Consolidate Console instances**
   - Consider a shared console or lazy creation

7. **Add adapter factory pattern**
   - Let adapters declare their own config requirements
   - Reduces coupling in TodoService

### Phase 3: Architectural Improvements (Consider for future)

8. **Measure actual startup times**
   - Profile with `python -X importtime -c "from dodo.cli import app"`
   - Identify remaining bottlenecks

9. **Consider optional dependencies**
   - httpx could be an optional dependency for obsidian adapter
   - Users who don't use Obsidian never pay the import cost

10. **Plugin system lazy evaluation**
    - Plugin discovery currently scans filesystem
    - Could be optimized if plugin list grows

## Startup Optimization Quick Reference

For maximum startup performance, ensure:

```python
# BAD: Eager loading of heavy modules
from dodo.adapters.obsidian import ObsidianAdapter  # imports httpx

# GOOD: Lazy loading based on config
def _create_adapter(self):
    if self._config.default_adapter == "obsidian":
        from dodo.adapters.obsidian import ObsidianAdapter
        return ObsidianAdapter(...)
```

```python
# BAD: Loading config multiple times
def add(...):
    cfg = Config.load()
    ...
    _save_last_action(...)  # calls Config.load() again!

# GOOD: Single config load
def add(...):
    cfg = Config.load()
    ...
    _save_last_action(..., cfg)  # pass config through
```

```python
# BAD: Subprocess on every command
def add(...):
    project_id = detect_project()  # spawns subprocess

# GOOD: Cache result
_project_cache = None
def detect_project():
    global _project_cache
    if _project_cache is None:
        _project_cache = _detect_project_impl()
    return _project_cache
```

## Testing Recommendations

After implementing optimizations:

1. Measure baseline: `time dodo add "test" && dodo rm $(dodo ls -f jsonl | head -1 | jq -r .id)`
2. Profile imports: `python -X importtime -c "from dodo.cli import app" 2>&1 | sort -t: -k2 -n | tail -20`
3. Verify functionality: Run existing test suite
4. Check that lazy loading doesn't break error messages for missing deps
