# Obsidian Plugin Enhancements Design

## Overview

Enhance the Obsidian plugin with configurable display formats, cleaner task rendering (no visible IDs), tag-based header organization, and dependency support.

## Goals

1. **Cleaner display** - Remove visible IDs and timestamps from task lists
2. **Flexible formatting** - Support multiple syntax styles (symbols, emoji, dataview)
3. **Better organization** - Group tasks under headers by tag
4. **Bidirectional sync** - Edit in Obsidian or CLI, changes sync both ways
5. **Dependency rendering** - Show task hierarchies as indented lists

## Configuration

All settings configurable via `dodo config` menu using existing `ConfigVar` pattern.

### New Settings

```python
def register_config() -> list[ConfigVar]:
    return [
        # Connection (existing)
        ConfigVar("api_url", "https://localhost:27124", label="API URL",
                  description="Obsidian Local REST API"),
        ConfigVar("api_key", "", label="API Key",
                  description="Bearer token"),
        ConfigVar("vault_path", "dodo/{project}.md", label="Vault path",
                  description="Path template in vault"),

        # Display syntax
        ConfigVar("priority_syntax", "symbols", label="Priority", kind="cycle",
                  options=["hidden", "symbols", "emoji", "dataview"],
                  description="How to display priority"),
        ConfigVar("timestamp_syntax", "hidden", label="Timestamp", kind="cycle",
                  options=["hidden", "plain", "emoji", "dataview"],
                  description="How to display timestamp"),
        ConfigVar("tags_syntax", "hashtags", label="Tags", kind="cycle",
                  options=["hidden", "hashtags", "dataview"],
                  description="How to display tags"),

        # Organization
        ConfigVar("group_by_tags", "true", label="Group by tags", kind="toggle",
                  description="Organize under headers by tag"),
        ConfigVar("default_header_level", "3", label="Header level", kind="cycle",
                  options=["1", "2", "3", "4"],
                  description="Level for new headers"),
        ConfigVar("sort_by", "priority", label="Sort by", kind="cycle",
                  options=["priority", "date", "content", "tags", "status", "manual"],
                  description="Task ordering within sections"),
    ]
```

### Settings Menu Display

```
  obsidian                     0.2.0
    API URL                    https://localhost:27124
    API Key                    ********
    Vault path                 dodo/{project}.md
    Priority                   symbols          How to display priority
    Timestamp                  hidden           How to display timestamp
    Tags                       hashtags         How to display tags
    Group by tags              ✓                Organize under headers by tag
    Header level               3                Level for new headers
    Sort by                    priority         Task ordering within sections
```

## Display Formats

### Priority Syntax

| Option | Critical | High | Normal | Low | Someday |
|--------|----------|------|--------|-----|---------|
| `hidden` | (none) | (none) | (none) | (none) | (none) |
| `symbols` | `!!!` | `!!` | `!` | (none) | `~` |
| `emoji` | `⏫` | `🔼` | (none) | `🔽` | `⏬` |
| `dataview` | `[priority:: critical]` | `[priority:: high]` | `[priority:: normal]` | `[priority:: low]` | `[priority:: someday]` |

Priority always appears at the **end** of task text.

### Timestamp Syntax

| Option | Example |
|--------|---------|
| `hidden` | (none) |
| `plain` | `2024-01-15 10:30` |
| `emoji` | `📅 2024-01-15` |
| `dataview` | `[created:: 2024-01-15]` |

### Tags Syntax

| Option | Example |
|--------|---------|
| `hidden` | (none) |
| `hashtags` | `#work #urgent` |
| `dataview` | `[tags:: work, urgent]` |

### Example Output

With defaults (`priority: symbols`, `timestamp: hidden`, `tags: hashtags`, `group_by_tags: true`):

```markdown
### work
- [ ] Ship the feature !!!
    - [ ] Write tests !!
    - [ ] Update docs
- [ ] Review PRs !

### home
- [ ] Buy groceries #errand
- [ ] Call mom ~
```

## Tag-Based Organization

When `group_by_tags: true`, tasks are organized under headers based on their **first tag**.

### Behavior

1. **Scan** existing headers in Obsidian file
2. **Match** headers to tags (first word, lowercase): `## Work Projects` → tag `work`
3. **Place** task under matching header
4. **Create** new header at configured level if no match exists
5. **Preserve** user's header customizations (level, capitalization, extra text)

### Multiple Tags

First tag determines the section, remaining tags shown inline:

```markdown
### home
- [ ] Buy groceries #errand     ← #home is first tag, #errand shown inline

### errand
- [ ] Pick up dry cleaning       ← only has #errand
```

User controls placement by tag order:
- `#home #errand` → appears under `### home`
- `#errand #home` → appears under `### errand`

### Header Association Storage

Header mappings stored in sync file to preserve user customizations:

```json
{
  "headers": {
    "work": "## Work Projects",
    "home": "### home"
  }
}
```

## ID Management

Task IDs are stored in a **sidecar file**, not in the visible markdown.

### File Structure

```
~/.config/dodo/projects/<name>/
├── dodo.json               # {"backend": "obsidian"}
└── obsidian-sync.json      # ID mappings + header associations
```

### Sync File Format

```json
{
  "ids": {
    "ship the feature": "abc12345",
    "write tests": "def67890",
    "buy groceries": "ghi11223"
  },
  "headers": {
    "work": "## Work Projects",
    "home": "### home"
  }
}
```

Keys are **normalized** task text.

### Normalization

```python
import re

def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)  # punctuation → space
    text = re.sub(r'\s+', ' ', text)       # collapse whitespace
    return text.strip()
```

| Original | Normalized |
|----------|------------|
| `"Ship the feature!"` | `"ship the feature"` |
| `"Ship  the   feature"` | `"ship the feature"` |
| `"Ship-the-feature"` | `"ship the feature"` |

### Matching Algorithm

On reading from Obsidian:

```
For each task line:
  1. Parse task text, strip priority/tags
  2. Normalize text
  3. Exact match in ids? → use that ID
  4. No exact match? → fuzzy match (difflib.SequenceMatcher ≥ 85%)
  5. Still no match? → generate new ID
```

### Fuzzy Matching

Using Python stdlib `difflib.SequenceMatcher`:

```python
from difflib import SequenceMatcher

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

# Match if ≥ 0.85
```

Optimizations:
- Skip if text length differs by >30%
- Early exit on first match ≥90%
- Only compare against unmatched IDs

### Stale ID Cleanup

After processing all tasks:
1. Rewrite `obsidian-sync.json` with only matched IDs
2. Orphaned IDs automatically pruned
3. **Safety check**: Skip pruning if Obsidian returns empty/error

## Dependency Rendering

When the **graph plugin** is enabled, task dependencies render as indented children.

### Format

4 spaces per indentation level (Obsidian default):

```markdown
### work
- [ ] Ship the feature !!!
    - [ ] Write tests !!
    - [ ] Update docs
        - [ ] Screenshots
- [ ] Review PRs !
```

### Bidirectional Sync

| Direction | Behavior |
|-----------|----------|
| Dodo → Obsidian | Query graph for children, render indented under parent |
| Obsidian → Dodo | Parse indentation, create/update dependency relationships |

### Implementation

```python
INDENT = "    "  # 4 spaces

def render_with_deps(task, depth=0):
    line = f"{INDENT * depth}- [ ] {format_task(task)}"
    if graph_enabled:
        for child in graph_backend.get_children(task.id):
            line += "\n" + render_with_deps(child, depth + 1)
    return line

def parse_indentation(line: str) -> int:
    spaces = len(line) - len(line.lstrip())
    return spaces // 4
```

### Edge Cases

- **Circular dependencies**: Warn and skip (don't render)
- **Graph plugin disabled**: Flat list only, ignore indentation on read
- **Orphan children**: Tasks indented under non-existent parent → treat as top-level

## Sorting

Tasks sorted within each section according to `sort_by` setting.

| Value | Sorts by | Default direction |
|-------|----------|-------------------|
| `priority` | Critical → Someday | Descending |
| `date` | Created timestamp | Descending (newest first) |
| `content` | Alphabetical | Ascending (A-Z) |
| `tags` | Primary tag alphabetically | Ascending |
| `status` | Pending → Done | Ascending |
| `manual` | Preserve file order | N/A |

When `manual` is selected, tasks maintain their order from the Obsidian file.

## Implementation Notes

### Formatter Architecture

```
TodoItem ←→ ObsidianFormatter(settings) ←→ Markdown string
```

Single formatter class handles all syntax variations based on config:

```python
class ObsidianFormatter:
    def __init__(self, config: dict):
        self.priority_syntax = config.get("priority_syntax", "symbols")
        self.timestamp_syntax = config.get("timestamp_syntax", "hidden")
        self.tags_syntax = config.get("tags_syntax", "hashtags")

    def to_markdown(self, todo: TodoItem) -> str:
        ...

    def from_markdown(self, line: str) -> TodoItem:
        # Parser handles all syntax variations
        ...
```

### Parser Flexibility

When reading, the parser accepts **any** syntax format. This allows:
- Mixed formats in a single file
- Format migration without breaking existing files
- Manual edits in any style

### Graph Plugin Integration

Check if graph plugin is enabled before querying dependencies:

```python
from dodo.plugins import is_plugin_enabled

if is_plugin_enabled("graph"):
    from dodo.plugins.graph import get_backend
    graph = get_backend()
    children = graph.get_children(task.id)
```

## Migration Path

Existing Obsidian backend users will see:
1. Old format tasks (with visible IDs) still parse correctly
2. On first write with new settings, tasks reformat to new style
3. IDs migrate to sidecar file automatically

No manual migration required.
