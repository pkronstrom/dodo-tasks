# Obsidian Plugin

Sync todos with your Obsidian vault via the Local REST API.

## Use Case

- Keep todos in your Obsidian vault as markdown
- Access todos from both dodo CLI and Obsidian
- Use Obsidian's search, linking, and graph features with your todos

## Prerequisites

Install the **Local REST API** plugin in Obsidian:
1. Open Obsidian Settings → Community Plugins
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
   - `obsidian_vault_path`: Path to todo file in vault (default: `dodo/todos.md`)

3. Set as your adapter:
   ```bash
   dodo config
   # Navigate to "Adapter" and select "obsidian"
   ```

## Usage

Once configured, all standard dodo commands sync with Obsidian:

```bash
dodo add "Review meeting notes"
dodo ls
dodo done abc123
```

Todos appear in your vault at the configured path (e.g., `dodo/todos.md`).

## Troubleshooting

**Connection refused**: Make sure Obsidian is running and the Local REST API plugin is enabled.

**Unauthorized**: Check that your API key is correctly set in dodo config.
