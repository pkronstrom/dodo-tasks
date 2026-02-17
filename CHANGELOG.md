# Changelog

## v0.6.0

### New Features

- **Due dates**: `dodo add "Task" --due 2026-03-01` and `dodo due <id> <date>` to set/clear deadlines
- **Metadata**: Arbitrary key-value pairs via `dodo meta set <id> <key> <val>` / `dodo meta rm` / `dodo meta show`
- **Atomic tag operations**: `dodo tag add <id> <tag>` / `dodo tag rm <id> <tag>` — no more replace-all-tags
- **Due date display**: All formatters (table, tree, txt, md, csv, jsonl) show `@YYYY-MM-DD` with overdue highlighting
- **Webhook wrapper**: Optional outbound webhooks on todo CRUD events (`server` plugin)

### API & MCP

- REST API: `due_at` and `metadata` fields on POST/PATCH, atomic `/tag` and `/meta` endpoints, `?overdue=true` filter
- MCP tools: `add_todo`/`update_todo` accept `due_at`/`metadata`, new `add_tag`/`remove_tag`/`set_metadata_key`/`remove_metadata_key` tools
- Remote backend: Full support for all new fields and atomic operations

### Backend Protocol

- `TodoBackend` protocol extended with: `update_due_at`, `update_metadata`, `add_tag`, `remove_tag`, `set_metadata_key`, `remove_metadata_key`
- SQLite: Full implementation of all new methods
- Markdown: Stubs raising `NotImplementedError` (read-only for new fields)
- GraphWrapper: Delegates all new methods to wrapped backend

### Breaking Changes

- **Removed `dodo wip` command** — use `dodo meta set <id> status wip` instead for the same effect
- `TodoItem` dataclass gains `due_at: datetime | None` and `metadata: dict` fields

### Fixes

- Timezone-safe due date comparisons (no more crashes with timezone-aware datetimes)
- Metadata validated as dict at API/MCP boundaries
- PATCH endpoint uses validate-then-mutate pattern (no partial state on validation errors)
- CLI gracefully handles `NotImplementedError` from backends that don't support new features

## v0.5.0

Internal version bump during development (not released).

## v0.4.1

- Fix server plugin code review findings

## v0.4.0

- Server plugin: REST API, Web UI, MCP endpoint, remote backend
