# SQLite Plugin

Store todos in a SQLite database instead of markdown files.

## Use Case

- Better performance with large todo lists (1000+ items)
- Faster filtering and querying
- Required for dependency tracking (graph plugin)

## Setup

1. Enable the plugin:
   ```bash
   dodo plugins enable sqlite
   ```

2. Set as your adapter:
   ```bash
   dodo config
   # Navigate to "Adapter" and select "sqlite"
   ```

   Or via command line:
   ```bash
   echo '{"default_adapter": "sqlite"}' > ~/.config/dodo/config.json
   ```

## Usage

Once enabled, all standard dodo commands work the same:

```bash
dodo add "Buy groceries"
dodo ls
dodo done abc123
```

Todos are stored in:
- Global: `~/.config/dodo/dodo.db`
- Per-project: `~/.config/dodo/projects/<project-id>/dodo.db`

## Migration

To migrate existing markdown todos to SQLite:

```bash
# Export from markdown
dodo export -o backup.jsonl

# Switch adapter to sqlite
dodo config  # Change adapter

# Import (coming soon)
```
