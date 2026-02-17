# Graph Plugin

Track dependencies between todos - block tasks until their prerequisites are done.

## Use Case

- Define task dependencies (A blocks B)
- See which tasks are ready to work on (no blockers)
- Visualize task hierarchy as a tree
- Prevent working on blocked tasks

## Prerequisites

Requires the **sqlite backend** (the default). The graph plugin stores dependency relationships in the same SQLite database as your todos.

## Setup

1. Enable the plugin:
   ```bash
   dodo plugins enable graph
   ```

2. Ensure sqlite is your backend (it's the default):
   ```bash
   dodo config
   # Check "Backend" is set to "sqlite"
   ```

## Usage

### Managing Dependencies

```bash
# Add a dependency: "setup" blocks "build"
dodo dep add <setup-id> <build-id>

# Remove a dependency
dodo dep rm <setup-id> <build-id>

# List all dependencies
dodo dep list
```

### Viewing Tasks

```bash
# Show tasks ready to work on (no uncompleted blockers)
dodo graph ready

# Show blocked tasks
dodo graph blocked

# Machine-readable output (for scripting/agents)
dodo graph ready -f jsonl
dodo graph blocked -f jsonl
```

### List Output

When listing todos, blocked tasks show their blockers:

```
ID       Done   Todo              Blocked by
abc123   [ ]    Setup project
def456   [ ]    Build feature     abc123
```

### Tree View

View dependencies as a tree:

```bash
dodo list -f tree
```

Output:
```
○ abc123   Setup project →1
└── ○ def456   Build feature →1
    └── ○ ghi789   Write tests
○ jkl012   Update docs
```

The `→N` indicator shows how many tasks are blocked by this one. Due dates are shown as `@YYYY-MM-DD` (red if overdue).

## How It Works

The graph plugin wraps the sqlite backend with a `GraphWrapper` that:
1. Stores dependencies in a `dependencies` table
2. Attaches `blocked_by` info to todos when listing
3. Provides ready/blocked filtering

## Plugin Interface

This plugin demonstrates the full plugin API:

```python
# Static declarations (scanned without importing)
COMMANDS = ["graph", "dep", "plugins/graph"]
FORMATTERS = ["tree"]

# Hooks
def register_commands(app, config)       # Nested: dodo plugins graph
def register_root_commands(app, config)  # Root: dodo graph, dodo dep
def register_formatters()                # Provides: tree formatter
def register_config()                    # Config: graph_tree_view
def extend_backend(backend, config)      # Wraps sqlite with GraphWrapper
def extend_formatter(formatter, config)  # Adds blocked_by column to table
```
