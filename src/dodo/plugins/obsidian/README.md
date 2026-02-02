# Obsidian Plugin

Sync todos with your Obsidian vault via the Local REST API.

## Use Case

- Keep todos in your Obsidian vault as markdown
- Access todos from both dodo CLI and Obsidian
- Use Obsidian's search, linking, and graph features with your todos

## Prerequisites

Install the **Local REST API** plugin in Obsidian:
1. Open Obsidian Settings -> Community Plugins
2. Search for "Local REST API"
3. Install and enable it
4. Copy the API key from the plugin settings

## Setup

1. Enable the plugin:
   ```bash
   dodo plugins enable obsidian
   ```

2. Configure the connection:
   ```bash
   dodo config
   ```
   Set these values:
   - `obsidian_api_url`: API endpoint (default: `https://localhost:27124`)
   - `obsidian_api_key`: Your API key from the Obsidian plugin
   - `obsidian_vault_path`: Path to todo file in vault (default: `dodo/{project}.md`)

3. Set as your backend:
   ```bash
   dodo config
   # Navigate to "Backend" and select "obsidian"
   ```

## Usage

Once configured, all standard dodo commands sync with Obsidian:

```bash
dodo add "Review meeting notes"
dodo ls
dodo done abc123
```

Todos appear in your vault at the configured path (e.g., `dodo/todos.md`).

## Configuration Options

### Display Syntax

Control how task metadata appears in your markdown files.

| Option | Default | Values | Description |
|--------|---------|--------|-------------|
| `priority_syntax` | `symbols` | `hidden`, `symbols`, `emoji`, `dataview` | How to display priority |
| `timestamp_syntax` | `hidden` | `hidden`, `plain`, `emoji`, `dataview` | How to display timestamp |
| `tags_syntax` | `hashtags` | `hidden`, `hashtags`, `dataview` | How to display tags |

### Organization

Control how tasks are organized in the file.

| Option | Default | Values | Description |
|--------|---------|--------|-------------|
| `group_by_tags` | `true` | `true`, `false` | Organize tasks under headers by first tag |
| `default_header_level` | `3` | `1`, `2`, `3`, `4` | Markdown header level for tag sections |
| `sort_by` | `priority` | `priority`, `date`, `content`, `tags`, `status`, `manual` | Task ordering within sections |

## Example Output Formats

### Priority Display

**Symbols (default):**
```markdown
- [ ] Critical task !!!
- [ ] High priority task !!
- [ ] Normal task !
- [ ] Someday task ~
```

**Emoji:**
```markdown
- [ ] Critical task 🔴
- [ ] High priority task 🟠
- [ ] Normal task 🟡
- [ ] Someday task 🔵
```

**Dataview:**
```markdown
- [ ] High priority task [priority:: high]
- [ ] Normal task [priority:: normal]
```

### Timestamp Display

**Plain:**
```markdown
- [ ] Review PR 2024-01-15 10:30
```

**Emoji:**
```markdown
- [ ] Review PR 📅 2024-01-15
```

**Dataview:**
```markdown
- [ ] Review PR [created:: 2024-01-15]
```

### Tags Display

**Hashtags (default):**
```markdown
- [ ] Review PR #work #urgent
```

**Dataview:**
```markdown
- [ ] Review PR [tags:: work, urgent]
```

### Tag-Based Organization

When `group_by_tags` is enabled, tasks are grouped under headers by their first tag.
Tasks without tags appear at the top of the file without a header:

```markdown
- [ ] Random thought

### work
- [ ] Review PR !!
- [ ] Update documentation

### home
- [ ] Buy groceries
- [ ] Call plumber ~
```

## Migration Notes

### ID Storage Change

Task IDs are no longer visible in the markdown file. They are now stored separately in `~/.dodo/obsidian-sync.json`.

**Benefits:**
- Cleaner markdown without `[id:abc123]` clutter
- Edits in Obsidian are matched via fuzzy text matching
- No need to preserve cryptic ID markers

**Migration:**
- Automatic on first sync - no action required
- Old format with `[id]` markers is recognized and migrated
- IDs are preserved, just stored externally

### Editing in Obsidian

You can freely edit tasks in Obsidian:
- Check/uncheck boxes
- Edit task text
- Add/remove tags
- Reorder tasks

Changes sync back to dodo via fuzzy text matching. The system finds the best match for edited text and updates the corresponding task.

## Troubleshooting

**Connection refused**: Make sure Obsidian is running and the Local REST API plugin is enabled.

**Unauthorized**: Check that your API key is correctly set in dodo config.

**Tasks not syncing**: Verify the vault path exists and is writable. Check that Obsidian has the file open or at least the vault loaded.
