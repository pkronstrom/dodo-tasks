# Dodo

![dodo banner](docs/dodo_banner.png)

[![PyPI version](https://img.shields.io/pypi/v/dodo-tasks)](https://pypi.org/project/dodo-tasks/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Part of NDD](https://img.shields.io/badge/NDD-minimum%20viable%20workflow-blue)](https://github.com/pkronstrom/nest-driven-development)

**The todo list that knows which project you're in.**

Part of [**Nest-Driven Development**](https://github.com/pkronstrom/nest-driven-development) — the minimum viable workflow.

---

## The Problem

You have todos scattered across sticky notes, a global task file, three different project READMEs, and a Jira board nobody updates. When you `cd` into a project, you have no idea what "in progress" even means.

Your AI agents have it worse — they have no idea what you were working on, what's blocked, or what matters next.

## The Solution

Dodo routes tasks automatically based on where you are in the filesystem. Open a terminal in any project directory and your scoped task list is already there. Your AI agents get the same context you do — no setup, no configuration, no syncing.

```bash
~/projects/webapp $ dodo list    # shows webapp tasks
~/random-folder   $ dodo list    # shows global tasks
```

No Jira. No setup. Just tasks that know where they belong.

---

## Quick Start

```bash
# Install (uv recommended)
uv tool install git+https://github.com/pkronstrom/dodo-tasks

# Add a task to the current project
dodo add "Fix the bug"

# List tasks
dodo list

# Mark done (partial ID works)
dodo done abc123

# Interactive TUI
dodo
```

---

## Features

- **Land in any directory, see the right tasks** — project routing is automatic, based on where you `cd`
- **Capture fast, triage later** — add todos in seconds with priority prefixes (`!!:`) and `#hashtags`
- **Works how your team stores things** — SQLite, Markdown, or Obsidian vault, your call
- **A full TUI when you need to dig in** — vim-style navigation, no mouse required
- **AI agents get the same context you do** — plugin system lets agents process, link, and act on tasks

---

## How Dodo Finds Your Todos

**Detection order:**

| Priority | Source | How it works |
|----------|--------|--------------|
| 1 | **Local** | `.dodo/` in current dir or parents |
| 2 | **Mapped** | Directory set via `dodo use` |
| 3 | **Global** | `~/.config/dodo/` fallback |

```bash
dodo new          # Create dodo (auto-named from git/dir)
dodo new --local  # Create .dodo/ at project root
dodo use myname   # Point this dir to existing dodo
dodo show         # Show detected dodos and current default
```

**Override flags:**

| Flag | Effect |
|------|--------|
| `-g` / `--global` | Force global, skip detection |
| `-d name` | Target specific dodo by name |

---

## Bulk Operations (for AI agents)

```bash
# Bulk add from JSONL
echo '{"text": "Task 1", "priority": "high"}
{"text": "Task 2", "tags": ["work"]}' | dodo bulk add

# Bulk done/rm with multiple IDs
dodo bulk done abc123 def456
dodo bulk rm abc123 def456
```

See [examples/dodo-command.md](examples/dodo-command.md) for agentic workflow patterns.

---

## Plugins

```bash
dodo plugins list           # Show available plugins
dodo plugins enable ai      # Enable a plugin
dodo config                 # Configure plugins
```

| Plugin | What it does |
|--------|-------------|
| `ai` | AI-assisted formatting (claude, gemini, llm) |
| `graph` | Dependency tracking with `dodo dep add` |
| `server` | REST API + Web UI + MCP endpoint |
| `ntfy-inbox` | Receive todos via ntfy.sh (works with Siri) |
| `obsidian` | Obsidian vault backend |

### Server plugin (REST / Web UI / MCP)

```bash
dodo plugins enable server
pip install -e ".[server]"
dodo server start
```

Exposes three channels (each individually toggleable):
- **Web UI** at `/` — mobile-first task manager with dark mode
- **REST API** at `/api/v1/` — full CRUD, multi-dodo
- **MCP** at `/mcp` — drop-in AI agent integration

### ntfy-inbox (Siri integration)

```bash
dodo plugins enable ntfy-inbox
dodo config                       # Set your ntfy topic
dodo plugins ntfy-inbox run       # Start listener
```

Send todos from anywhere:
```bash
curl -d "Buy milk #errands" ntfy.sh/your-topic
```

---

## Configuration

```bash
dodo config     # Interactive config menu
```

Config stored at `~/.config/dodo/config.json`:

```json
{
  "default_backend": "sqlite",
  "plugins": {
    "ntfy-inbox": { "topic": "your-secret" },
    "ai": { "command": "claude -p ..." }
  }
}
```

---

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

---

## License

MIT
