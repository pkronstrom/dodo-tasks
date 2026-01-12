# Dodo Command Reference

This document provides examples for managing multiple dodo instances, including creating, using, and destroying named dodos.

## dodo new

Create new dodo instances for session-based task tracking.

```bash
dodo new                              # Create default dodo in ~/.config/dodo/
dodo new <name>                       # Create named dodo in ~/.config/dodo/<name>/
dodo new --local                      # Create local dodo in .dodo/
dodo new <name> --local               # Create named local dodo in .dodo/<name>/
dodo new --backend sqlite             # Specify backend (sqlite or markdown)
```

### Examples

```bash
# Create a named session for a project
dodo new feature-auth

# Create a local dodo for the current project
dodo new project-tasks --local

# Create with explicit SQLite backend for better performance
dodo new ai-session --backend sqlite --local
```

## dodo destroy

Remove dodo instances when they are no longer needed.

```bash
dodo destroy <name>                   # Remove dodo from ~/.config/dodo/<name>/
dodo destroy <name> --local           # Remove local dodo from .dodo/<name>/
dodo destroy --local                  # Remove default local dodo
```

### Examples

```bash
# Remove a global named dodo
dodo destroy feature-auth

# Remove a local project dodo
dodo destroy project-tasks --local

# Clean up default local dodo
dodo destroy --local
```

## --dodo flag

Target a specific dodo instance for any command.

```bash
dodo add "task" --dodo my-session     # Add to specific dodo
dodo list --dodo my-session           # List from specific dodo
dodo done 1 --dodo my-session         # Complete task in specific dodo
dodo add "task" --dodo my-session --local  # Use local .dodo/<name>/
```

### Examples

```bash
# Add task to a specific session
dodo add "Implement login form" --dodo feature-auth

# List tasks from a specific session
dodo list --dodo feature-auth

# Mark task done in a specific session
dodo done 1 --dodo feature-auth

# Work with local project dodo
dodo add "Fix build error" --dodo ci-tasks --local
dodo list --dodo ci-tasks --local
```

## AI Agent Usage

AI agents can use ephemeral dodo instances to track tasks during autonomous operations.

### Creating an Ephemeral Session

```bash
# Create ephemeral dodo for task tracking
dodo new agent-session-123 --local --backend sqlite

# Add tasks with dependencies
dodo add "Fetch data" --dodo agent-session-123 --local
dodo add "Process data" --after 1 --dodo agent-session-123 --local
dodo add "Generate report" --after 2 --dodo agent-session-123 --local

# List and manage tasks
dodo list --dodo agent-session-123 --local

# Mark tasks complete as work progresses
dodo done 1 --dodo agent-session-123 --local

# Cleanup when done
dodo destroy agent-session-123 --local
```

### Why Use Named Dodos for AI Agents?

1. **Isolation**: Each agent session has its own task list, preventing conflicts
2. **Cleanup**: Easy to remove all tasks when the session ends
3. **Tracking**: Clear separation between human tasks and AI-generated tasks
4. **Local scope**: Using `--local` keeps agent tasks in the project directory

### Multi-Agent Workflow

```bash
# Agent 1: Research phase
dodo new research-agent --local --backend sqlite
dodo add "Analyze codebase" --dodo research-agent --local
dodo add "Identify patterns" --after 1 --dodo research-agent --local

# Agent 2: Implementation phase
dodo new impl-agent --local --backend sqlite
dodo add "Implement feature X" --dodo impl-agent --local
dodo add "Write tests" --after 1 --dodo impl-agent --local

# Check progress of each agent
dodo list --dodo research-agent --local
dodo list --dodo impl-agent --local

# Cleanup after agents complete
dodo destroy research-agent --local
dodo destroy impl-agent --local
```

## Backend Selection

When creating a new dodo, you can specify the storage backend:

- **sqlite** (default): Fast, supports concurrent access, good for frequent updates
- **markdown**: Human-readable files, good for version control and manual editing

```bash
# SQLite backend (recommended for AI agents)
dodo new ai-session --backend sqlite --local

# Markdown backend (good for shared project tasks)
dodo new shared-tasks --backend markdown --local
```
