# ntfy-inbox Plugin

Receive todos via push notifications from ntfy.sh.

## Use Case

- Add todos from your phone without opening a terminal
- Capture ideas instantly via push notification
- Share a topic with others to receive their task suggestions
- Integration with automation tools (IFTTT, Shortcuts, etc.)

## Setup

1. Enable the plugin:
   ```bash
   dodo plugins enable ntfy-inbox
   ```

2. Configure your topic:
   ```bash
   dodo config
   ```
   Set these values:
   - `ntfy_topic`: Your secret topic name (e.g., `my-secret-todos-abc123`)
   - `ntfy_server`: Server URL (default: `https://ntfy.sh`)

   **Important**: Use a unique, hard-to-guess topic name. Anyone who knows your topic can send you todos.

## Usage

### Start Listening

```bash
dodo plugins ntfy-inbox run
```

This subscribes to your topic and adds incoming messages as todos.

### Send Todos

From any device, send a notification to your topic:

**Using curl:**
```bash
curl -d "Buy milk" ntfy.sh/my-secret-todos-abc123
```

**Using the ntfy app:**
1. Install ntfy app on your phone
2. Subscribe to your topic
3. Send a message - it becomes a todo

**Using the web:**
1. Go to `https://ntfy.sh/my-secret-todos-abc123`
2. Type your todo and send

### Example Workflow

Terminal 1 (keep running):
```bash
dodo plugins ntfy-inbox run
```

Terminal 2 or phone:
```bash
curl -d "Call dentist" ntfy.sh/my-topic
curl -d "Review PR #42" ntfy.sh/my-topic
```

Terminal 1 output:
```
Added: Call dentist (abc123)
Added: Review PR #42 (def456)
```

## Tips

- Run the listener in a tmux/screen session or as a systemd service
- Use a long random string as your topic for security
- The listener adds todos to your current project (or global if not in a project)
