# Learnings: Terminal UI and Editor Integration

**Date**: 2026-01-09
**Objective**: Improve dodo's interactive terminal UI with better editor integration and config UX
**Outcome**: Success - Implemented configurable editor, auto-save config, and robust editor fallbacks

## Summary

Building terminal UIs that integrate with external editors requires careful handling of subprocess lifecycle, especially for GUI editors that fork to background. Config changes that auto-save need to consider the implications of intermediate states during cycling through options.

## What We Tried

### Approach 1: Simple subprocess.run for editors
- **Description**: Called `subprocess.run([editor, tmp_path])` directly
- **Result**: Failed for GUI editors
- **Why**: GUI editors like VS Code and Cursor fork to background and return immediately, so the temp file gets read before the user finishes editing

### Approach 2: Require users to add --wait flag manually
- **Description**: Document that users need to set editor to "code --wait"
- **Result**: Poor UX
- **Why**: Users shouldn't need to know implementation details; they expect "code" to just work

### Approach 3: Auto-detect GUI editors and add --wait
- **Description**: Maintain a set of known GUI editors and automatically append `--wait` flag
- **Result**: Worked
- **Why**: Covers the common case transparently while still allowing custom flags

### Approach 4: Basic exception handling for editor failures
- **Description**: Catch `FileNotFoundError` when editor command doesn't exist
- **Result**: Partially worked
- **Why**: Some failures raise `OSError` instead; needed broader exception handling

## Final Solution

Implemented a multi-layered editor handling system:

1. **Configurable editor**: `config.editor` setting overrides `$EDITOR` env var
2. **GUI auto-detection**: Known GUI editors (`code`, `cursor`, `subl`, `atom`, `zed`) automatically get `--wait` appended
3. **Command parsing**: Use `shlex.split()` to properly handle editor commands with arguments
4. **Fallback chain**: If configured editor fails, try `nano`, then `vi`
5. **Broad exception handling**: Catch `FileNotFoundError`, `OSError`, and `CalledProcessError`

For config UX, changed from explicit "Save & Exit" to immediate save on each change. This works because:
- Adapter changes don't take effect until `TodoService` is re-instantiated (on menu exit)
- Toggle changes are atomic and safe to save immediately
- Edit fields already required explicit save (editor exit)

## Key Learnings

- **GUI editors need `--wait`**: VS Code, Cursor, Sublime, Atom, and Zed all fork to background by default. The `--wait` flag makes them block until the file is closed.

- **shlex.split() for command parsing**: When a command string may contain arguments (e.g., "code --wait"), use `shlex.split()` to properly tokenize it before passing to `subprocess.run()`. Don't just split on spaces.

- **Exception types vary by platform**: `FileNotFoundError` is common but `OSError` can also occur. Catch both for robustness.

- **Fallback editors matter**: When the configured editor fails, falling back to common editors like `nano` and `vi` prevents the user from being stuck.

- **Auto-save timing**: For config settings that affect backend connections (like adapter type), auto-save is safe because the connection is lazy - it only instantiates when actually used.

- **Config loop re-entry**: When shelling out to an editor from within a `console.screen()` context (alternate screen buffer), you must exit the context, run the editor, then re-enter. This prevents screen corruption.

## Issues & Resolutions

| Issue | Root Cause | Resolution |
|-------|------------|------------|
| GUI editors return immediately | They fork to background process | Auto-detect and add `--wait` flag |
| Editor command with args fails | `subprocess.run(["code --wait", file])` treats whole string as command name | Use `shlex.split()` to tokenize |
| FileNotFoundError not caught | Some failures raise OSError instead | Catch both `FileNotFoundError` and `OSError` |
| Editor setting not taking effect | Config loaded once at startup | Reload config (`Config.load()`) before each editor invocation |
| Broken editor config locks user out | Can't edit config to fix editor if editor is broken | Config editing uses `$EDITOR` directly, not config.editor |

## Gotchas & Warnings

- **Config editor uses $EDITOR, not config.editor**: This is intentional! If the user sets a broken editor in config, they can still edit the config using their system `$EDITOR` to fix it.

- **The `--wait` flag is editor-specific**: While most GUI editors use `--wait`, some might use different flags. The current implementation assumes `--wait` works universally for the detected editors.

- **Temp file cleanup**: The `_edit_in_editor` function uses `finally` to ensure temp files are deleted even if the editor fails. Don't remove this.

- **Rich Live context and editors don't mix**: Never shell out to an editor while inside a `Live()` context. Exit the context first, run the editor, then re-enter with a fresh `Live()` instance.

## References

- `src/dodo/ui/interactive.py:310-355` - `_edit_in_editor()` function with all the editor handling logic
- `src/dodo/ui/interactive.py:357-453` - `_config_loop()` with auto-save implementation
- `src/dodo/config.py` - Config class with `editor` setting
