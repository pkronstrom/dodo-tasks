# ntfy-inbox Plugin Design

## Overview

A plugin that receives todos from ntfy.sh, enabling "Hey Siri, add to my dodo" via iPhone Shortcuts.

## Architecture

### Plugin System Philosophy

Plugins are **standalone scripts** that live in `plugins/<name>/` and interact with dodo via CLI. This keeps the core clean while allowing extensibility.

```
plugins/ntfy-inbox/
├── dodo-ntfy-inbox      # Executable script (bash or python)
└── README.md            # Usage docs + Shortcut setup instructions
```

### Self-Describing Config

Scripts declare their required env vars via magic comments:

```bash
#!/bin/bash
# @env DODO_NTFY_TOPIC: Your secret ntfy topic (required)
# @env DODO_NTFY_SERVER: ntfy server URL (default: https://ntfy.sh)
```

dodo can later scan these for `dodo plugins list` and config menu integration.

## ntfy Field Mapping

| ntfy field | dodo use | Example |
|------------|----------|---------|
| `topic` | Inbox queue (secret) | `dodo-a7f3b2c9` |
| `title` | Project name (empty → global) | `work` |
| `message` | Todo text, `ai:` prefix for AI mode | `ai: buy milk and eggs` |
| `tags` | Reserved for labels (future) | `["urgent", "shopping"]` |
| `priority` | Reserved for priority (future) | `4` |

## Message Processing Logic

```
receive message from ntfy:
  project = message.title or None (global)
  text = message.message

  if text.startswith("ai:"):
    text = text[3:].strip()
    if project:
      run: dodo ai "{text}" -p {project}
    else:
      run: dodo ai "{text}"
  else:
    if project:
      run: dodo add "{text}" -p {project}
    else:
      run: dodo add "{text}"
```

## Configuration

**Required:**
- `DODO_NTFY_TOPIC` - The secret topic name (acts as auth)

**Optional:**
- `DODO_NTFY_SERVER` - Server URL (default: `https://ntfy.sh`)

## Plugin Env Parsing

dodo core will include a utility to scan plugin directories and extract `@env` declarations:

```python
# src/dodo/plugins.py

def scan_plugin_envs(plugin_dir: Path) -> list[PluginEnv]:
    """Scan plugin scripts for @env declarations."""
    ...
```

This enables:
1. `dodo plugins list` - show installed plugins and their config status
2. Future: integrate plugin config into `dodo config` menu

## iPhone Shortcut Setup

1. Create Shortcut named "Add Dodo"
2. Action: "Get text from input" (for Siri dictation)
3. Action: "Get contents of URL"
   - URL: `https://ntfy.sh/YOUR_TOPIC`
   - Method: POST
   - Headers: `Title: work` (optional, for project)
   - Body: Text from step 2
4. Say "Hey Siri, Add Dodo" → dictate → done

## Running the Listener

```bash
# Set config
export DODO_NTFY_TOPIC="dodo-your-secret-here"

# Run listener (foreground)
./plugins/ntfy-inbox/dodo-ntfy-inbox

# Or via dodo (future)
dodo plugins run ntfy-inbox
```

For persistence: launchd plist on macOS, systemd unit on Linux.

## Future Enhancements

- [ ] `dodo plugins list` - discover and show status
- [ ] `dodo plugins run <name>` - run a plugin
- [ ] Config menu integration for plugin env vars
- [ ] Tag → todo labels mapping
- [ ] Priority → todo priority mapping
- [ ] Confirmation notification back to phone
