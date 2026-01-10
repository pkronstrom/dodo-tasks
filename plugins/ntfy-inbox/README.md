# ntfy-inbox

Receive todos via [ntfy.sh](https://ntfy.sh) for dodo. Enables "Hey Siri, add to my dodo" via iPhone Shortcuts.

## Setup

### 1. Choose a secret topic

Your topic name acts as authentication. Use something unguessable:

```bash
# Generate a random topic name
openssl rand -hex 8
# Example output: a7f3b2c9d1e48f6a
```

Your topic will be: `dodo-a7f3b2c9d1e48f6a`

### 2. Configure the environment

```bash
export DODO_NTFY_TOPIC="dodo-a7f3b2c9d1e48f6a"
```

Add this to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.) for persistence.

### 3. Run the listener

```bash
./dodo-ntfy-inbox
```

For background operation, see [Running as a Service](#running-as-a-service).

## iPhone Shortcut Setup

### Basic "Add Dodo" Shortcut

1. Open **Shortcuts** app
2. Create new shortcut named "Add Dodo"
3. Add action: **Dictate Text**
4. Add action: **Get Contents of URL**
   - URL: `https://ntfy.sh/dodo-YOUR-SECRET-HERE`
   - Method: `POST`
   - Request Body: `Text` → select "Dictated Text" from step 3

Now say "Hey Siri, Add Dodo" → dictate your todo → done!

### With Project Support

To add to a specific project, include a Title header:

1. Same as above, but in the URL action:
   - Headers: Add `Title` = `work` (or your project name)

Or create multiple shortcuts: "Add to Work", "Add to Personal", etc.

### With AI Parsing

For AI to split your input into multiple todos:

1. Same as above, but prefix your message with `ai:`
2. Or create an "AI Add Dodo" shortcut that prepends `ai: ` to the dictated text

Example: "ai: buy milk and also call mom" → creates two separate todos.

## Message Format

| ntfy Field | dodo Use |
|------------|----------|
| `message` | Todo text. Prefix with `ai:` for AI parsing |
| `title` | Project name (empty = global) |
| `tags` | Reserved for future (todo labels) |
| `priority` | Reserved for future (todo priority) |

## Testing

Send a test message:

```bash
# Simple todo
curl -d "buy milk" ntfy.sh/dodo-YOUR-SECRET

# With project
curl -H "Title: shopping" -d "buy eggs" ntfy.sh/dodo-YOUR-SECRET

# AI parsing
curl -d "ai: buy milk and call mom" ntfy.sh/dodo-YOUR-SECRET
```

## Running as a Service

### macOS (launchd)

Create `~/Library/LaunchAgents/com.dodo.ntfy-inbox.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dodo.ntfy-inbox</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/plugins/ntfy-inbox/dodo-ntfy-inbox</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>DODO_NTFY_TOPIC</key>
        <string>dodo-YOUR-SECRET-HERE</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/dodo-ntfy-inbox.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/dodo-ntfy-inbox.err</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.dodo.ntfy-inbox.plist
```

### Linux (systemd)

Create `~/.config/systemd/user/dodo-ntfy-inbox.service`:

```ini
[Unit]
Description=dodo ntfy inbox listener
After=network.target

[Service]
ExecStart=/path/to/plugins/ntfy-inbox/dodo-ntfy-inbox
Environment=DODO_NTFY_TOPIC=dodo-YOUR-SECRET-HERE
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

Enable it:

```bash
systemctl --user enable --now dodo-ntfy-inbox
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DODO_NTFY_TOPIC` | Yes | — | Your secret ntfy topic |
| `DODO_NTFY_SERVER` | No | `https://ntfy.sh` | ntfy server URL |

## Limitations

- Messages are lost if the listener isn't running (ntfy caches briefly, but don't rely on it)
- No confirmation notification back to phone (yet)
- Rate limited to 250 messages/day on free ntfy.sh tier
