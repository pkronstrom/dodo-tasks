# AI-Friendly Dodo Management

## Overview

Enable AI agents to create and manage ephemeral dodos for task tracking, particularly for parallel subagent coordination using the dependency graph feature.

## Terminology Change

Rename "project" to "dodo" throughout the codebase and UI. A "dodo" is a todo list/tracker instance.

## Commands

### `dodo new`

Create a new dodo.

```bash
dodo new                              # Create default dodo in ~/.config/dodo/
dodo new my-session                   # Create named dodo in ~/.config/dodo/my-session/
dodo new --local                      # Create default dodo in .dodo/
dodo new my-session --local           # Create named dodo in .dodo/my-session/
dodo new my-session --backend sqlite  # Specify backend (sqlite, markdown, obsidian)
```

**Behavior:**
- Default location: `~/.config/dodo/` (centralized)
- `--local` flag: `.dodo/` in current directory
- Named dodos create subdirectories
- Idempotent: if dodo exists, confirm and suggest creating a named one

**Output examples:**
```
$ dodo new
✓ Created dodo in ~/.config/dodo/

$ dodo new
✓ Dodo already exists in ~/.config/dodo/
  Hint: Use `dodo new <name>` to create a named dodo

$ dodo new agent-task-123 --local --backend sqlite
✓ Created dodo in .dodo/agent-task-123/
```

### `dodo destroy`

Remove a dodo and its data.

```bash
dodo destroy my-session               # Remove from ~/.config/dodo/my-session/
dodo destroy my-session --local       # Remove from .dodo/my-session/
dodo destroy --local                  # Remove default local dodo (.dodo/)
```

### Targeting dodos

All existing commands accept `--dodo` flag to target a specific dodo:

```bash
dodo add "Task 1" --dodo my-session
dodo add "Task 2" --after 1 --dodo my-session
dodo list --dodo my-session
dodo done 1 --dodo my-session
```

## Auto-Detection (Resolution Precedence)

When no `--dodo` flag is provided, resolve in this order:

1. **Local first**: Check for `.dodo/` in current directory, then parent directories up to filesystem root
2. **Centralized fallback**: Check `~/.config/dodo/` for git-based or default dodo
3. **Error**: If nothing found, error with hint to run `dodo new`

```
$ dodo add "task"
Error: No dodo found.
  Run `dodo new` to create one, or `dodo new --local` for a local dodo.
```

### Local dodo structure

```
.dodo/
  dodo.db              # Default local dodo
  agent-session-1/
    dodo.db            # Named local dodo
  agent-session-2/
    dodo.db
```

When `.dodo/` contains multiple dodos, `dodo add` (no flags) targets the root `.dodo/dodo.db`. Named dodos require explicit `--dodo agent-session-1`.

## Storage Locations

| Command | Location |
|---------|----------|
| `dodo new` | `~/.config/dodo/dodo.db` |
| `dodo new foo` | `~/.config/dodo/foo/dodo.db` |
| `dodo new --local` | `.dodo/dodo.db` |
| `dodo new foo --local` | `.dodo/foo/dodo.db` |

## Interactive Menu Changes

### Remove stateful "Switch Projects"

The current "Switch Projects" menu maintains state about which project is "active". Remove this - dodo should always auto-detect based on current directory.

### New "New dodo" menu option

Replace with a "New dodo" option that offers:

```
[New dodo]
  → Create in ~/.config/dodo/ (Recommended)
  → Create locally in .dodo/
  → Create for this git repo (detects repo, creates in ~/.config/dodo/{repo_id}/)
```

### Rename throughout UI

- "Project" → "Dodo"
- "Switch Projects" → removed
- "Projects" list → "Dodos" (read-only, shows detected dodos)

## Config Changes

### Remove `local_storage` setting

The global `local_storage` boolean is confusing. Remove it. Location is now explicit:
- Default: centralized (`~/.config/dodo/`)
- `--local` flag: local (`.dodo/`)

### Keep other settings

- `default_backend`: Still useful as default for `dodo new`
- `worktree_shared`: Still relevant for git-based dodo detection

## AI Usage Example

Parallel subagent task tracking with dependencies:

```bash
# Parent agent creates ephemeral dodo
dodo new task-session-abc123 --local --backend sqlite

# Add tasks with dependencies
dodo add "Fetch user data" --dodo task-session-abc123
dodo add "Fetch product data" --dodo task-session-abc123
dodo add "Generate report" --after 1,2 --dodo task-session-abc123

# Subagents check/complete tasks
dodo list --dodo task-session-abc123
dodo done 1 --dodo task-session-abc123

# View dependency graph
dodo graph --dodo task-session-abc123

# Cleanup when done
dodo destroy task-session-abc123 --local
```

## Migration Path

1. Rename `--project` flag to `--dodo` (keep `--project` as hidden alias for backwards compatibility)
2. Rename internal references from "project" to "dodo"
3. Update CLI help text and error messages
4. Update interactive menu
5. Remove `local_storage` config option
6. Deprecate `dodo init` (keep as hidden alias for `dodo new --local` with git detection)

## Files to Modify

- `src/dodo/cli.py` - Add `new`/`destroy` commands, rename flags
- `src/dodo/project.py` → `src/dodo/dodo.py` - Rename module
- `src/dodo/project_config.py` → `src/dodo/dodo_config.py` - Rename module
- `src/dodo/config.py` - Remove `local_storage` setting
- `src/dodo/core.py` - Update resolution logic
- `src/dodo/ui/interactive.py` - Update menu structure
- Tests throughout
