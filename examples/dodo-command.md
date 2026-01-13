# Dodo Command Reference

Commands for managing multiple dodo instances - creating, using, and destroying named dodos.

## dodo new

Create new dodo instances.

```bash
dodo new                              # Create default dodo in ~/.config/dodo/
dodo new <name>                       # Create named dodo in ~/.config/dodo/<name>/
dodo new --local                      # Create local dodo in .dodo/
dodo new <name> --local               # Create named local dodo in .dodo/<name>/
dodo new -b sqlite                    # Specify backend (-b or --backend)
```

### Examples

```bash
# Create a named global dodo
dodo new feature-auth

# Create a local dodo for this project
dodo new project-tasks --local

# Create with SQLite backend (recommended for AI agents)
dodo new ai-session -b sqlite --local
```

## dodo destroy

Remove dodo instances. **Auto-detects** local vs global location.

```bash
dodo destroy <name>                   # Auto-detects and removes
dodo destroy --local                  # Remove default .dodo/ (no name)
```

### Examples

```bash
# Remove a named dodo (auto-detects location)
dodo destroy feature-auth
dodo destroy project-tasks

# Remove default local dodo
dodo destroy --local
```

## -d / --dodo flag

Target a specific dodo. **Auto-detects** local vs global - checks `.dodo/<name>/` first, then `~/.config/dodo/<name>/`.

```bash
dodo add "task" -d my-session         # Add to specific dodo
dodo list -d my-session               # List from specific dodo
dodo done 1 -d my-session             # Complete task in specific dodo
```

### Examples

```bash
# Full workflow with shorthand
dodo new ci-tasks --local
dodo add "Fix build" -d ci-tasks
dodo add "Run tests" -d ci-tasks
dodo list -d ci-tasks
dodo done 1 -d ci-tasks
dodo destroy ci-tasks
```

## AI Agent Usage

AI agents can use ephemeral dodos for task tracking during autonomous operations.

### Ephemeral Session

```bash
# Create
dodo new agent-123 --local -b sqlite

# Add tasks
dodo add "Fetch data" -d agent-123
dodo add "Process data" -d agent-123
dodo add "Generate report" -d agent-123

# Work
dodo list -d agent-123
dodo done 1 -d agent-123

# Cleanup
dodo destroy agent-123
```

### Why Named Dodos for AI?

1. **Isolation** - Each session has its own task list
2. **Cleanup** - Easy removal when done
3. **Tracking** - Separation from human tasks
4. **Local scope** - `--local` keeps tasks in project directory

### Multi-Agent Workflow

```bash
# Agent 1: Research
dodo new research -b sqlite --local
dodo add "Analyze codebase" -d research
dodo add "Identify patterns" -d research

# Agent 2: Implementation
dodo new impl -b sqlite --local
dodo add "Implement feature" -d impl
dodo add "Write tests" -d impl

# Check progress
dodo list -d research
dodo list -d impl

# Cleanup
dodo destroy research
dodo destroy impl
```

## Backend Selection

```bash
dodo new my-dodo -b sqlite      # Fast, concurrent access (default)
dodo new my-dodo -b markdown    # Human-readable, git-friendly
```

- **sqlite**: Recommended for AI agents, frequent updates
- **markdown**: Good for shared tasks, manual editing
