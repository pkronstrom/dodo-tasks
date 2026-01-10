# Graph Plugin

Track dependencies between todos - block tasks until their prerequisites are done.

## Use Case

- Define task dependencies (A blocks B)
- See which tasks are ready to work on (no blockers)
- Visualize task hierarchy as a tree
- Prevent working on blocked tasks

## Prerequisites

Requires the **sqlite adapter**. The graph plugin stores dependency relationships in the same SQLite database as your todos.

## Setup

1. Enable both plugins:
   ```bash
   dodo plugins enable sqlite
   dodo plugins enable graph
   ```

2. Set sqlite as your adapter:
   ```bash
   dodo config
   # Navigate to "Adapter" and select "sqlite"
   ```

## Usage

### Managing Dependencies

```bash
# Add a dependency: "setup" blocks "build"
dodo plugins graph dep add <setup-id> <build-id>

# Remove a dependency
dodo plugins graph dep rm <setup-id> <build-id>

# List all dependencies
dodo plugins graph dep list
```

### Viewing Tasks

```bash
# Show tasks ready to work on (no uncompleted blockers)
dodo plugins graph ready

# Show blocked tasks
dodo plugins graph blocked
```

### List Output

When listing todos, blocked tasks show their blockers:

```
ID       Done   Todo              Blocked by
abc123   [ ]    Setup project
def456   [ ]    Build feature     abc123
```

### Tree View

View dependencies as a hierarchy:

```bash
dodo plugins graph dep list --tree
```

Output:
```
○ Setup project
└── ○ Build feature
    └── ○ Write tests
○ Update docs
```

## How It Works

The graph plugin wraps the sqlite adapter with a `GraphWrapper` that:
1. Stores dependencies in a `dependencies` table
2. Attaches `blocked_by` info to todos when listing
3. Provides ready/blocked filtering
