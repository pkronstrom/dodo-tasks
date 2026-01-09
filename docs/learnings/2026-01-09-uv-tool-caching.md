# UV Tool Installation Caching

**Date**: 2026-01-09

## Problem

When developing a Python CLI tool installed via `uv tool install .`, code changes may not take effect even after running `uv tool install . --force`.

### Symptoms

- Code changes aren't reflected in the installed tool
- Debug logging added to source files never executes
- `uv run <tool>` works correctly but `<tool>` (installed version) uses stale code

### Root Cause

UV caches installed tool packages in `~/.local/share/uv/tools/<package>/`. The `--force` flag may not fully clear this cache, leaving stale Python files.

## Solution

Force a completely fresh installation:

```bash
rm -rf ~/.local/share/uv/tools/<package>
uv cache clean
uv tool install .
```

For dodo specifically:

```bash
rm -rf ~/.local/share/uv/tools/dodo && uv cache clean && uv tool install .
```

## Verification

Confirm the installed version uses your source:

```bash
# Check where the executable points
cat ~/.local/bin/<tool>

# Verify source location
uv run python -c "import <package>; import inspect; print(inspect.getsourcefile(<package>))"
```

## Key Insight

`uv run <tool>` uses the local source directly, while `uv tool install` copies files to the tools directory. When debugging installation issues, compare behavior between these two modes.
