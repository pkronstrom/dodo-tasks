# CLI Enhancements Design

## Overview

Enhancements to dodo CLI for better UX, bulk operations, undo, export formats, and simplified project detection.

---

## 1. Add Command Flag Changes

**New short flags:**
- `-p` / `--priority` (was `-P`)
- `-t` / `--tag` for tags

**Tag parsing:**
- Comma-separated: `-t work,urgent`
- Multiple flags: `-t work -t urgent`
- Mixed: `-t work,urgent -t home`
- All sources merged

Old `--tags` becomes alias for backward compatibility.

**Example:**
```bash
dodo add "Task" -p high -t work,urgent
dodo add "Task" --priority high --tag work --tag urgent
```

---

## 2. Bulk Subcommand

**Structure:**
```
dodo bulk add       # JSONL from stdin
dodo bulk edit      # IDs as args + flags, OR JSONL from stdin
dodo bulk done      # IDs as args OR from stdin
dodo bulk rm        # IDs as args OR from stdin
dodo bulk remove    # alias for rm
```

**Smart input parser** auto-detects format:
- JSONL: lines starting with `{`
- JSON array: input starts with `[`
- Plain IDs: one per line
- Comma-separated: `id1, id2, id3`
- Arguments: `dodo bulk done id1 id2 id3`

**Bulk edit modes:**
```bash
# Args + flags (same change to all)
dodo bulk edit abc123 def456 -p high -t work

# JSONL (per-item changes)
echo '{"id": "abc", "priority": "high"}
{"id": "def", "tags": null}' | dodo bulk edit
```

**Partial updates:**
- Only present fields are updated
- Missing fields unchanged
- Explicit `null` clears a field
- Flag mode cannot clear fields

**Output:** All bulk commands print affected items, support `--quiet` for IDs-only.

---

## 3. Enhanced Undo

**Storage:** Full snapshot of affected item(s) before mutation in `~/.config/dodo/.last_action`:

```json
{
  "action": "done",
  "target": "webapp",
  "items": [
    {"id": "abc123", "text": "Task", "status": "pending", "priority": "high", ...}
  ]
}
```

**Supported operations:**
- `add` → deletes the added item(s)
- `done` → restores previous status
- `rm` → re-creates the deleted item(s)
- `edit` → restores previous field values

**Behavior:**
- Single level (no redo)
- Global scope (restores to correct dodo regardless of current dir)
- Works on bulk operations (stores array of snapshots)
- Undo clears after execution
- If item deleted externally, skip with warning

**Example:**
```bash
dodo bulk done abc def ghi
# Done: 3 items

dodo undo
# Undid done: 3 items restored to pending

dodo undo
# Nothing to undo
```

---

## 4. Export Format Options

**Command:**
```bash
dodo export                     # default: jsonl
dodo export -f jsonl            # explicit
dodo export -f csv
dodo export -f tsv
dodo export -f txt
dodo export -f md
dodo export -f md -o todos.md   # output to file
```

**New formatters:**

**txt** - simple list with priority and tags:
```
Fix the bug !high #work #urgent
Buy groceries #errands
Review PR
```

**md** - checkbox list with priority and tags:
```
- [ ] Fix the bug !high #work #urgent
- [ ] Buy groceries #errands
- [x] Review PR
```

Priority as `!level`, tags as `#tag`. Only appended if present.

---

## 5. Simplified Project Detection

### Mental Model

**`dodo new` = CREATE a dodo**

| Command | Storage location |
|---------|-----------------|
| `dodo new` | Central `~/.config/dodo/<name>/` |
| `dodo new --local` | Local `<project-root>/.dodo/` |
| `dodo new myname` | Central `~/.config/dodo/myname/` |
| `dodo new myname --local` | Local `<project-root>/.dodo/myname/` |

**Auto-naming:**
- In git repo: name from git repo
- Not in git: name from current directory

**Project root detection:**
- In git repo: git root (even from subdirectory)
- Not in git: current directory

**`dodo use` = POINT this dir to existing dodo**
```bash
dodo use myname     # this dir now uses "myname"
dodo unuse          # remove the pointer
```

### Detection Order (for reads)

1. Local `.dodo/` in current dir or parents
2. `use` mapping
3. Global (fallback)

**No implicit creation on `add`** - falls back to global if no dodo exists.

### Command Output Examples

**dodo new:**
```
~/projects/webapp/src $ dodo new
Detected git repo 'webapp' at ~/projects/webapp
Created dodo 'webapp' at ~/.config/dodo/webapp/

~/projects/webapp $ dodo new --local
Detected git repo 'webapp' at ~/projects/webapp
Created local dodo at ~/projects/webapp/.dodo/

~/projects/webapp $ dodo new myname
Created dodo 'myname' at ~/.config/dodo/myname/

~/projects/webapp $ dodo new myname --local
Detected git repo 'webapp' at ~/projects/webapp
Created local dodo 'myname' at ~/projects/webapp/.dodo/myname/

~/random $ dodo new
Created dodo 'random' at ~/.config/dodo/random/

~/random $ dodo new --local
Created local dodo at ~/random/.dodo/
```

**dodo show:**
```
~/projects/webapp/src $ dodo show

Context:
  Git repo: webapp (~/projects/webapp)
  Directory: ~/projects/webapp/src

Available dodos:
  → webapp        ~/.config/dodo/webapp/       (default - git detected)
    myname        ~/.config/dodo/myname/       (use: dodo -d myname)
    local         ~/projects/webapp/.dodo/     (use: dodo -d local)

Current: webapp (12 pending, 3 done)
```

```
~/random $ dodo show

Context:
  Directory: ~/random

Available dodos:
  → global        ~/.config/dodo/              (default - no project detected)

Current: global (5 pending, 0 done)
```

**dodo add:**
```
~/projects/webapp $ dodo add "Fix login bug"
Added to 'webapp': Fix login bug (abc123)

~/projects/webapp $ dodo add "Task" -p high -t urgent,backend
Added to 'webapp': Task !high #urgent #backend (abc123)

~/projects/webapp $ dodo add -g "Buy groceries"
Added to 'global': Buy groceries (def456)

# First add when no dodo exists (hint shown once):
~/projects/newrepo $ dodo add "First task"
Added to 'global': First task (abc123)
Hint: Run 'dodo new' to create a project dodo
```

---

## 6. README Clarification

### How Dodo Finds Your Todos

**Default behavior** - Dodo picks the right list automatically:

```
~/projects/webapp $ dodo list    → webapp (if dodo exists)
~/random-folder   $ dodo list    → global
```

**Detection order:**

| Priority | Source | How it works |
|----------|--------|--------------|
| 1 | **Local** | `.dodo/` in current dir or parents |
| 2 | **Mapped** | Directory set via `dodo use` |
| 3 | **Global** | `~/.config/dodo/` fallback |

**Notes:**
- Dodos must be explicitly created with `dodo new`
- `dodo add` without existing dodo uses global (with one-time hint)
- Use `dodo show` to see what dodo would be used

**Commands:**

| Command | Effect |
|---------|--------|
| `dodo new` | Create dodo (auto-named from git/dir) |
| `dodo new --local` | Create `.dodo/` at project root |
| `dodo new myname` | Create named dodo |
| `dodo use myname` | Point this dir to existing dodo |
| `dodo unuse` | Remove the pointer |
| `dodo show` | Show detected dodos and current default |

**Override flags:**

| Flag | Effect |
|------|--------|
| `-g` / `--global` | Force global, skip detection |
| `-d name` | Target specific dodo by name |

---

## Implementation Notes

### Files to modify:
- `src/dodo/cli.py` - add command flags, bulk subcommand, undo enhancement, export formats
- `src/dodo/resolve.py` - simplify detection logic, remove git auto-creation
- `src/dodo/formatters/` - add txt.py, markdown.py
- `src/dodo/bulk.py` - new file for bulk input parser
- `README.md` - rewrite project detection section

### Files to add:
- `src/dodo/formatters/txt.py`
- `src/dodo/formatters/markdown.py`
- `src/dodo/bulk.py` (smart input parser)
- `src/dodo/cli_bulk.py` (bulk subcommand)

### Backward compatibility:
- `--tags` remains as alias for `--tag`
- `dodo link` → alias for `dodo use`
- `dodo unlink` → alias for `dodo unuse`
- `dodo add-bulk` → alias for `dodo bulk add`
