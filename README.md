# Dodo

Todo router - manage todos across multiple backends.

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

```bash
# Add a todo (smart routing: local project or global)
dodo add "fix the bug"

# Add to global explicitly
dodo add -g "remember to buy milk"

# List todos
dodo list

# Mark done
dodo done <id>

# Interactive menu
dodo
```

## Plugins

Plugins are standalone scripts in `~/.config/dodo/plugins/` or `./plugins/`.

```bash
# List installed plugins
dodo plugins list

# Run a plugin
dodo plugins run ntfy-inbox
```

### ntfy-inbox

Receive todos via [ntfy.sh](https://ntfy.sh) - enables "Hey Siri, add to my dodo".

```bash
export DODO_NTFY_TOPIC="dodo-your-secret"
dodo plugins run ntfy-inbox
```

See `plugins/ntfy-inbox/README.md` for iPhone Shortcut setup.

## Configuration

Copy `.env.template` to `~/.config/dodo/.env` and customize.

## AI Backends

### llm (default)
```bash
DODO_AI_COMMAND="llm '{{prompt}}' -s '{{system}}' --schema '{{schema}}'"
```

### Claude CLI
```bash
DODO_AI_COMMAND="claude -p '{{prompt}}' --system-prompt '{{system}}' --json-schema '{{schema}}' --output-format json --model haiku --tools ''"
```

### Gemini CLI (no schema enforcement)
```bash
DODO_AI_COMMAND="gemini '{{prompt}}' --output-format json"
```

### Codex CLI (requires schema file)
```bash
DODO_AI_COMMAND="codex exec '{{prompt}}' --output-schema ~/.config/dodo/schema.json"
```
