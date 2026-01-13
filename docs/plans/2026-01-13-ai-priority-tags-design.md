# AI-Assisted Todo Management: Priority, Tags & Bulk Operations

## Overview

Expand `dodo ai` from single-purpose "add via AI" to a full command group for AI-assisted todo management. Add priority and tags fields to the data model.

## Data Model Changes

### New Fields

```
priority: "critical" | "high" | "normal" | "low" | "someday" | null
tags: string[]  (freeform, e.g. ["backend", "docs", "v2"])
```

Default priority is `null` (no priority until set).

### Priority Sort Order

For sorting: critical=5, high=4, normal=3, low=2, someday=1, null=0

### Storage Per Backend

**SQLite:**
```sql
ALTER TABLE todos ADD COLUMN priority TEXT;
ALTER TABLE todos ADD COLUMN tags TEXT;  -- JSON array
```

**Markdown:**
```markdown
- [ ] Fix login bug !critical #backend #urgent
- [ ] Update docs !low #docs
- [ ] Random task #idea
```

Syntax: `!priority` for priority, `#tag` for tags. Visually distinct, easy to parse.

**Obsidian:** Out of scope for now.

## CLI Changes

### `dodo list` Sorting

```bash
dodo list --sort created     # Default, by creation time
dodo list --sort priority    # Priority desc (nulls last), then alphabetical
dodo list --sort tag         # Alphabetical by first tag
```

### `dodo list` Filtering

```bash
dodo list --filter prio:high
dodo list --filter prio:critical,high
dodo list --filter tag:backend
dodo list --filter tag:backend,api
dodo list -f prio:high -f tag:backend   # Combine filters
```

Short alias: `-f`

### `dodo ai` Command Group

```bash
dodo ai add [TEXT]      # Add with inferred priority/tags
dodo ai prio            # Alias: prioritize - bulk assign priorities
dodo ai reword          # Clarify unclear todos
dodo ai tag             # Bulk add/suggest tags
dodo ai sync            # Check git/code, mark completed todos
```

**Common flags:**
- `--yes` / `-y` - auto-apply without confirmation

**Default behavior:** Show diff of modified items only, ask for confirmation.

## AI Schemas

### `ai add` Output

```json
{
  "tasks": [
    {
      "text": "string",
      "priority": "critical|high|normal|low|someday|null",
      "tags": ["string"]
    }
  ]
}
```

### `ai prio` / `ai reword` / `ai tag` Output

```json
{
  "changes": [
    {
      "id": "abc123",
      "priority": "high",
      "text": "Updated text if reworded",
      "tags": ["new", "tags"]
    }
  ]
}
```

Only include fields that changed. Sparse updates.

### `ai sync` Output

```json
{
  "completed": ["abc123", "def456"],
  "reasoning": "abc123: commit 3fa2b fixed login bug"
}
```

## AI Prompts

### `ai add`

```
You are a todo assistant. Extract actionable tasks from user input.
For each task:
- Write clear, concise text (imperative mood: "Fix X", "Add Y")
- Infer priority only if clearly indicated (urgent/critical/blocking = critical, nice-to-have/someday = low/someday). Default to null.
- Infer tags from context (technology, area, type). Use existing tags when relevant: {{existing_tags}}
```

### `ai prio`

```
Analyze these todos and assign priorities where missing or clearly wrong.
Priority levels: critical (fires/blockers), high (important soon), normal (standard work), low (nice-to-have), someday (ideas/backlog).
Only return todos that need priority changes. Be conservative - most todos are "normal" or don't need explicit priority.
```

### `ai reword`

```
Review these todos for clarity. Reword only items that are:
- Unclear or ambiguous
- Too vague to act on
- Contain typos

Keep rewrites concise. Preserve original intent. Only return items that need changes.
```

### `ai tag`

```
Suggest tags for these todos based on content.
Existing tags in use: {{existing_tags}}
Prefer existing tags over new ones. Only return todos that benefit from tagging.
```

### `ai sync`

```
You have access to git and file tools. Check if any of these todos have been completed.
Start with: git log --oneline -20
Dig deeper if needed. Only mark done if you find clear evidence (commit message, code exists, etc).
Return completed todo IDs with brief reasoning.
```

## AI Configuration

Prompts are configurable via `~/.config/dodo/prompts.toml` (optional):

```toml
[ai.add]
system = "Your custom prompt..."

[ai.prio]
system = "Your custom prompt..."
```

Missing keys fall back to built-in defaults. File only loaded when `dodo ai` commands run (lazy load for performance).

## `ai sync` Tool Access

Uses Claude CLI with enabled tools:

```python
SYNC_TOOLS = ["Bash(git log*)", "Bash(git show*)", "Bash(git diff*)", "Read", "Grep"]
```

Sensible defaults, no configuration needed.

## Files to Modify

| File | Changes |
|------|---------|
| `src/dodo/models.py` | Add `priority`, `tags` fields |
| `src/dodo/backends/sqlite.py` | Schema migration, store priority/tags |
| `src/dodo/backends/markdown.py` | Parse/write `!priority` and `#tags` |
| `src/dodo/ai.py` | New schemas, prompts, subcommand logic |
| `src/dodo/cli.py` | `ai` becomes command group with subcommands |
| `src/dodo/formatters/` | Display priority/tags in list output |

## Out of Scope

- Obsidian backend support
- `dodo ai edit` (single item AI edit)
- `--group` flag for list
- `--sort` and `--filter` combined edge cases

## Example Usage

```bash
# Add with AI inference
dodo ai add "urgent: fix prod login bug, also update the docs sometime"
# → Adds: "Fix prod login bug" !critical #auth
# → Adds: "Update docs" !someday #docs

# Bulk prioritize
dodo ai prio
# Proposed changes (3 of 42 todos):
#   abc123: "fix login bug"         → priority: critical
#   def456: "add dark mode"         → priority: low
#   ghi789: "update README"         → priority: low
# Apply changes? [y/N]

# Sync with git
dodo ai sync
# Checking git history...
# Proposed completions (2 todos):
#   abc123: "fix login bug" - commit 3fa2b "fix: login redirect issue"
#   def456: "add tests" - commit 8cd1e "test: add auth tests"
# Mark as done? [y/N]

# Filter and sort
dodo list --filter prio:critical,high --sort priority
```
