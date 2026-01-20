# Dodo Commands for AI Agents

## Use Case 1: Project Task Tracking

Track your own work in the project's `.dodo/` at git root:

```bash
# Track progress as you work
dodo add "Implement user auth"
dodo add "Write tests" -p high
dodo list -f jsonl                       # Machine-readable status
dodo done <id>                           # Mark complete
```

Simple, persistent. Tasks live with the project.

---

## Use Case 2: Agentic Workflow with Subagents

Orchestrate parallel subagents with dependency-aware task distribution.

### Step 1: Create ephemeral dodo

```bash
dodo new workflow-abc --local -b sqlite
```

### Step 2: Bulk insert tasks with dependencies

```bash
# Add all tasks
echo '{"text": "Setup database schema", "priority": "high", "tags": ["db"]}
{"text": "Implement user model", "tags": ["backend"]}
{"text": "Implement auth endpoints", "tags": ["backend"]}
{"text": "Write integration tests", "tags": ["test"]}' | dodo bulk add -d workflow-abc -q > task_ids.txt

# Add dependencies (auth depends on user model, tests depend on auth)
echo '{"blocker": "<user-model-id>", "blocked": "<auth-endpoints-id>"}
{"blocker": "<auth-endpoints-id>", "blocked": "<integration-tests-id>"}' | dodo dep add-bulk -d workflow-abc
```

### Step 3: Dispatch subagents with ready tasks

Pass these instructions to each subagent:

```
Track your work with dodo:
- See ready tasks: dodo graph ready -d workflow-abc
- Mark done when complete: dodo done <id> -d workflow-abc

Only work on tasks shown by 'dodo graph ready'. Dependencies are tracked automatically.
```

Subagents pull ready tasks, complete them, and blocked tasks become unblocked.

### Step 4: Cleanup when done

```bash
dodo destroy workflow-abc --local
```

Ephemeral dodos prevent stale task accumulation.

---

## JSONL Schema

**bulk add** fields:
- `text` (required): Todo text
- `priority`: critical/high/normal/low/someday
- `tags`: ["tag1", "tag2"]

**dep add-bulk** fields:
- `blocker` (required): ID of blocking todo
- `blocked` (required): ID of blocked todo

## Command Reference

```bash
# Single operations
dodo add "task" [-d name] [-g] [-p priority] [-t tags]
dodo list [-d name] [-g] [-f jsonl|table|tree]
dodo done <id> [-d name] [-g]
dodo rm <id> [-d name] [-g]
dodo undo                                    # Undo last operation

# Dependencies (requires graph plugin)
dodo graph ready [-d name]                   # Tasks with no blockers
dodo graph blocked [-d name]                 # Tasks that are blocked
dodo dep add <blocker> <blocked> [-d name]
dodo dep add-bulk [-d name]                  # JSONL stdin
dodo dep rm <blocker> <blocked> [-d name]
dodo dep list [-d name] [--tree]             # --tree for tree view

# Bulk operations
dodo bulk add [-d name] [-g] [-q]            # JSONL stdin
dodo bulk done <id>... [-d name]             # Multiple IDs
dodo bulk rm <id>... [-d name]               # Multiple IDs

# Dodo management
dodo new [name] [--local] [-b sqlite|markdown]
dodo destroy <name> [--local]
dodo use <name>                              # Map current dir to dodo
dodo unuse                                   # Remove mapping
dodo show                                    # Show detected dodos

# Export
dodo export [-f jsonl|txt|md|csv]

# AI-assisted (requires ai plugin)
dodo ai add "natural language tasks"
dodo ai run "mark all docs tasks done"
dodo ai prio                                 # Suggest priorities
dodo ai tag                                  # Suggest tags
```

### Flags

- `-d, --dodo`: Target specific dodo by name
- `-g, --global`: Use global dodo (~/.config/dodo/)
- `-q, --quiet`: Minimal output (IDs only for bulk ops)
- `-f, --format`: Output format (table/jsonl/tree/txt/md/csv)
- `-p, --priority`: Priority level (critical/high/normal/low/someday)
- `-t, --tag`: Tag (can repeat, or comma-separated)
