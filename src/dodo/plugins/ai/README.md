# AI Plugin

AI-assisted todo management using Claude, Gemini, or other LLMs.

## Use Case

- Create todos with AI-inferred priority and tags
- Bulk assign priorities based on context
- Auto-suggest tags for todos
- Reword todos for clarity
- Execute natural language instructions on your todo list
- Auto-detect dependencies between tasks

## Prerequisites

Requires an AI CLI tool. Default is [Claude CLI](https://docs.anthropic.com/en/docs/claude-code):
```bash
npm install -g @anthropic-ai/claude-code
```

## Setup

1. Enable the plugin:
   ```bash
   dodo plugins enable ai
   ```

2. Configure (optional):
   ```bash
   dodo config
   ```
   Settings under **ai**:
   - `command`: Command template for AI operations
   - `run_command`: Command template for `ai run` (with tools)
   - `model`: Model for basic commands (haiku, sonnet, opus)
   - `run_model`: Model for `ai run` command

## Usage

### Add with AI

Create todos with AI-inferred priority and tags:

```bash
dodo ai add "fix the critical auth bug and update docs"
# Creates: "Fix critical auth bug" !high #security
#          "Update authentication docs" #docs
```

### Prioritize

AI assigns priorities to your existing todos:

```bash
dodo ai prio
# Shows suggestions, apply with 'y'
```

### Tag

AI suggests tags for untagged todos:

```bash
dodo ai tag
```

### Reword

AI improves todo wording for clarity:

```bash
dodo ai reword
```

### Run (Advanced)

Execute natural language instructions with tool access:

```bash
dodo ai run "mark all docs tasks as done"
dodo ai run "split the large refactor task into smaller steps"
```

The `run` command can:
- Modify existing todos
- Create new todos
- Delete todos (with confirmation)
- Access git history for context

### Dependencies

Auto-detect task dependencies (requires graph plugin):

```bash
dodo plugins enable graph
dodo ai dep
```

## Configuration

Default command templates use Claude CLI:

```json
{
  "plugins": {
    "ai": {
      "command": "claude -p '{{prompt}}' --system-prompt '{{system}}' ...",
      "model": "sonnet"
    }
  }
}
```

Template placeholders:
- `{{prompt}}` - User input
- `{{system}}` - System prompt
- `{{schema}}` - JSON schema for output
- `{{model}}` - Selected model

## Tips

- Use `haiku` for fast, simple operations (tag, reword)
- Use `sonnet` for complex reasoning (prioritize, run)
- Pipe content for context: `cat spec.md | dodo ai add "tasks from this spec"`
