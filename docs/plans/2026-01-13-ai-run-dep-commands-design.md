# AI Run and Dep Commands Design

## Overview

Add two new AI commands for bulk todo modifications:

1. **`dodo ai run "<instruction>"`** - General-purpose bulk modifications via natural language
2. **`dodo ai dep`** - Auto-detect and add dependencies between todos

## Command: `dodo ai run`

### Interface

```bash
dodo ai run "<instruction>"
dodo ai run "remove all test items"
dodo ai run "add #work tag to meeting-related todos"
dodo ai run "mark all groceries as done"
```

### Options

- `-y, --yes` - Apply without confirmation
- `-g, --global` - Operate on global todos
- `-d, --dodo <name>` - Target specific dodo

### Flow

1. Load all todos (respecting -g/--dodo flags)
2. Send todos + instruction to AI
3. AI returns modified todos + deletions
4. Display compact diff preview
5. Confirm → apply changes

### AI Response Schema

```json
{
  "type": "object",
  "properties": {
    "todos": {
      "type": "array",
      "description": "Only include todos that changed, with changed fields + id",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "string"},
          "text": {"type": "string"},
          "status": {"enum": ["pending", "done", "cancelled"]},
          "priority": {"enum": ["critical", "high", "normal", "low", "someday", null]},
          "tags": {"type": "array", "items": {"type": "string"}},
          "dependencies": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["id"]
      }
    },
    "delete": {
      "type": "array",
      "description": "IDs of todos to delete",
      "items": {"type": "string"}
    }
  }
}
```

**Logic:**
- `todos` array contains only items that changed (with just changed fields + id)
- `status: "done"` marks complete
- `dependencies` is just a field like any other
- `delete` array lists IDs to remove
- Items not mentioned = unchanged

### Diff Output

Compact diff style matching existing AI commands:

```
Running: "add #work to meeting todos, mark test items done"

Proposed changes (4 todos):
  abc123: "Schedule team meeting"
    + #work
  def456: "Review meeting notes"
    + #work
  test01: "test item"
    pending → done
  test02: "another test"
    pending → done

Delete (1):
  xyz999: "old test garbage"

Apply changes? [y/N]
```

## Command: `dodo ai dep`

### Interface

```bash
dodo ai dep
```

### Options

Same as other commands: `-y, --yes`, `-g, --global`, `-d, --dodo`

### Behavior

1. Analyze all pending todos
2. Detect logical dependencies ("X should be done before Y")
3. Show proposed dependency additions
4. Confirm to apply

### Diff Output

```
Analyzing dependencies...

Proposed dependencies (3):
  "Deploy to production"
    → "Run integration tests"
    → "Update changelog"
  "Write documentation"
    → "Finalize API design"

Apply changes? [y/N]
```

Each dependency on its own line, indented under the parent task. Long task names wrap within terminal width.

## Implementation Notes

### Waiting Messages

- `dodo ai run` → "Processing instruction..."
- `dodo ai dep` → "Analyzing dependencies..."

### Plugin Field Support

The schema includes `dependencies` for the graph plugin. Additional plugin fields can be added to the schema as needed. The service layer routes field updates to the appropriate plugin.

### Safety

- Preview + confirm by default prevents accidental data loss
- `-y/--yes` flag for scripting/automation
- Full lifecycle control (modify, delete, done) acceptable with preview gate
