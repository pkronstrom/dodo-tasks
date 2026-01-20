# Dodo

![dodo banner](docs/dodo_banner.png)

A fast, flexible todo manager with smart project routing and plugin support.

## Features

- **Smart routing**: Todos automatically go to the right project based on your current directory
- **Multiple backends**: SQLite (default), Markdown, Obsidian
- **Plugin system**: Extend with AI processing, dependency graphs, ntfy.sh integration
- **Interactive UI**: Full TUI with vim-style navigation
- **Priority & tags**: Organize with `!!:` prefixes and `#hashtags`

## Installation

```bash
# With uv (recommended)
uv tool install git+https://github.com/pkronstrom/dodo-tasks

# With pipx
pipx install git+https://github.com/pkronstrom/dodo-tasks

# Development
git clone https://github.com/pkronstrom/dodo-tasks
cd dodo
uv sync
```

## Quick Start

```bash
dodo add "Fix the bug"              # Add to current project's dodo
dodo add -g "Buy groceries"         # Add to global dodo
dodo list                           # List todos
dodo done abc123                    # Mark done (partial ID works)
dodo                                # Interactive menu
```

## How Dodo Finds Your Todos

**Default behavior** - Dodo picks the right list automatically:

```bash
~/projects/webapp $ dodo list    # uses webapp (if dodo exists)
~/random-folder   $ dodo list    # uses global
```

**Detection order:**

| Priority | Source | How it works |
|----------|--------|--------------|
| 1 | **Local** | `.dodo/` in current dir or parents |
| 2 | **Mapped** | Directory set via `dodo use` |
| 3 | **Global** | `~/.config/dodo/` fallback |

**Notes:**
- Dodos must be explicitly created with `dodo new`
- `dodo add` without existing dodo uses global (with one-time hint)
- Use `dodo show` to see what dodo would be used

**Commands:**

| Command | Effect |
|---------|--------|
| `dodo new` | Create dodo (auto-named from git/dir) |
| `dodo new --local` | Create `.dodo/` at project root |
| `dodo new myname` | Create named dodo |
| `dodo use myname` | Point this dir to existing dodo |
| `dodo unuse` | Remove the pointer |
| `dodo show` | Show detected dodos and current default |

**Override flags:**

| Flag | Effect |
|------|--------|
| `-g` / `--global` | Force global, skip detection |
| `-d name` | Target specific dodo by name |

## Plugins

```bash
dodo plugins list                   # Show available plugins
dodo plugins enable ai              # Enable a plugin
dodo config                         # Configure plugins
```

### Built-in Plugins

| Plugin | Description |
|--------|-------------|
| `ai` | AI-assisted todo formatting (claude, gemini, llm) |
| `graph` | Dependency tracking with `dodo dep add` |
| `ntfy-inbox` | Receive todos via ntfy.sh (Siri integration) |
| `obsidian` | Obsidian vault backend |

### ntfy-inbox (Siri Integration)

```bash
dodo plugins enable ntfy-inbox
dodo config                         # Set your ntfy topic
dodo plugins ntfy-inbox run         # Start listener
dodo plugins ntfy-inbox run -g      # Force global dodo
```

Send todos via curl or iOS Shortcuts:
```bash
curl -d "Buy milk #errands" ntfy.sh/your-topic
curl -d '{"message":"Task","priority":4}' ntfy.sh/your-topic
```

## Configuration

```bash
dodo config                         # Interactive config menu
```

Config stored in `~/.config/dodo/config.json`. Plugin config uses nested structure:
```json
{
  "default_backend": "sqlite",
  "plugins": {
    "ntfy-inbox": { "topic": "your-secret" },
    "ai": { "command": "claude -p ..." }
  }
}
```

## License

MIT
