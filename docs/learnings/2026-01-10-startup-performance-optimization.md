# Learnings: Startup Performance Optimization for One-Shot CLI

**Date**: 2026-01-10
**Objective**: Optimize dodo CLI startup time through lazy loading, caching, and DRY improvements
**Outcome**: Success - httpx import avoided for markdown users (~53ms savings), code deduplicated

## Summary

Optimized a one-shot CLI tool's startup time by implementing lazy adapter loading (avoiding 53ms httpx import for non-Obsidian users), adding in-memory caching for config and git detection within single invocations, and extracting shared adapter utilities to reduce code duplication. The key insight is that for run-once CLIs, lazy loading of heavy dependencies provides the biggest wins, while in-memory caching helps with redundant work within a single command execution.

## What We Tried

### Approach 1: Lazy Load Adapters
- **Description**: Move adapter imports from module-level to inside `_create_adapter()` method, only importing the configured adapter
- **Result**: Worked
- **Why**: Python's import system is lazy by default at the statement level - moving imports inside conditional branches means they only execute when that branch is taken

### Approach 2: Module-Level Caching for Config and Git Detection
- **Description**: Cache `Config.load()` and `detect_project()` results in module-level variables
- **Result**: Worked with caveats
- **Why**: Within a single CLI invocation, config and git state don't change, so caching avoids redundant file reads and subprocess calls. However, this required careful test isolation (clearing caches between tests).

### Approach 3: Shared Adapter Utilities
- **Description**: Extract duplicated code (ID generation, line parsing, formatting) into `adapters/utils.py`
- **Result**: Worked
- **Why**: Standard DRY refactoring - both markdown and obsidian adapters had identical implementations

## Final Solution

Implemented a 9-task cleanup plan:
1. **Lazy adapter loading** - Only import the adapter that's actually configured
2. **Config caching** - Single file read per invocation
3. **Git detection caching** - Single subprocess per invocation
4. **Unused import removal** - Minor cleanup
5. **Shared utils module** - `adapters/utils.py` with common functions
6. **Updated markdown adapter** - Use shared utils
7. **Updated obsidian adapter** - Use shared utils
8. **Test fixture for cache clearing** - `conftest.py` with autouse fixture
9. **Performance verification** - Confirmed httpx not imported for markdown users

## Key Learnings

- **Lazy loading >> in-memory caching for one-shot CLIs**: The 53ms saved by not importing httpx dwarfs the 1-5ms saved by caching within an invocation
- **Package `__init__.py` can defeat lazy loading**: Even if you lazy-load in your code, if the package's `__init__.py` eagerly imports, you've lost. We had to also clean up `adapters/__init__.py`
- **In-memory caching needs test isolation**: Adding module-level caches broke test isolation until we added `conftest.py` with autouse cache-clearing fixtures
- **Cache invalidation isn't needed for run-once CLIs**: The cache lives only for the process lifetime, so no TTL or invalidation logic needed
- **`python -X importtime` is invaluable**: Shows exactly what's being imported and how long each import takes

## Issues & Resolutions

| Issue | Root Cause | Resolution |
|-------|------------|------------|
| Lazy loading test still failed after fixing core.py | `adapters/__init__.py` was eagerly importing all adapters | Removed eager imports from `__init__.py` |
| Tests started polluting each other after adding caching | Module-level caches persist across tests | Added `conftest.py` with autouse fixture to clear caches |
| Existing tests in `test_project.py` didn't clear cache | Cache was added after tests were written | Added `_clear_cache` autouse fixture to test classes |
| `test_lazy_loading.py` failed with config cache | Test changed HOME but got cached config from old HOME | Added `clear_config_cache()` call in test |

## Gotchas & Warnings

- **Check `__init__.py` files when implementing lazy loading** - They execute on any import from the package
- **Autouse fixtures in `conftest.py` run for ALL tests** - Make sure cache clearing is idempotent
- **Module-level caches using dicts need `.clear()` not `= {}`** - The latter creates a new dict but other references still point to the old one
- **Custom config_dir parameter should bypass cache** - Tests often use custom directories; caching those would break test isolation

## Performance Results

| Metric | Value |
|--------|-------|
| httpx import (now avoided) | ~53ms |
| dodo.cli import (current) | ~38ms |
| Full command execution | ~100ms |

## References

- `docs/plans/2026-01-10-dodo-audit.md` - Full audit findings
- `docs/plans/2026-01-10-dodo-cleanup-plan.md` - Detailed implementation plan
- `python -X importtime` - Built-in Python import profiling
- `src/dodo/adapters/utils.py` - New shared utilities module
- `tests/conftest.py` - Cache-clearing fixtures
