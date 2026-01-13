"""Default prompts for AI operations."""

DEFAULT_ADD_PROMPT = """Create todo items from user input. The tasks array must NEVER be empty.
CRITICAL: Even single words like "test" or "foo" become todos with that exact text.
For each task:
- Text: Use the input directly. Apply imperative mood if possible ("Fix X", "Add Y").
- Priority: Only set if explicitly indicated. Default to null.
- Tags: Infer from context. Use existing tags when relevant: {existing_tags}

Output ONLY the JSON object with tasks array. Never ask questions or add commentary.
"""

DEFAULT_PRIORITIZE_PROMPT = """Analyze these pending todos and suggest priority levels.
Consider:
- Urgency (deadlines, blocking issues)
- Impact (user-facing, core functionality)
- Dependencies (what blocks other work)

Current todos:
{todos}

Output assignments with id, priority (critical/high/normal/low/someday), and brief reason.
"""

DEFAULT_TAG_PROMPT = """Suggest tags for these todos based on content.
Use existing project tags when relevant: {existing_tags}
Keep tags lowercase, use hyphens for multi-word.

Current todos:
{todos}

Output suggestions with id and array of tags.
"""

DEFAULT_REWORD_PROMPT = """Improve clarity of these todo descriptions.
- Use imperative mood ("Fix X" not "Fixing X")
- Be specific but concise
- Preserve original intent

Current todos:
{todos}

Output rewrites with id and improved text.
"""

DEFAULT_RUN_PROMPT = """You are a todo list assistant with tool access. Execute the user instruction.
You can use tools to read files, search code, check git history, and search the web for context.

For existing todos:
- Modify: Include in "todos" array with id and changed fields only
- Delete: ONLY when user EXPLICITLY requests deletion (e.g., "delete", "remove", "clean up duplicates")
  NEVER delete items just because they seem redundant, old, or unclear.
  When in doubt, keep the item.

For new todos:
- Create: Add to "create" array with text (required), priority and tags (optional)

Available fields:
- text: The todo description
- status: pending or done
- priority: critical, high, normal, low, someday, or null
- tags: Array of tag strings (lowercase, hyphens for multi-word)
- dependencies: Array of IDs this todo depends on (blockers)

IMPORTANT: Be conservative. Only make changes directly requested by the instruction.
Do not "clean up" or "improve" items unless explicitly asked.

Current todos:
{todos}

User instruction: {instruction}
"""

DEFAULT_DEP_PROMPT = """Analyze these todos and detect logical dependencies.
A dependency means one task should be completed before another can start.
Only suggest dependencies where the relationship is clear and meaningful.

Look for:
- Sequential tasks (step 1 before step 2)
- Prerequisites (need X before Y)
- Blocking relationships (cannot do Y until X is done)

Current todos:
{todos}

Return dependencies as pairs: blocked_id depends on blocker_id.
"""

DEFAULT_SYS_PROMPT = (
    "Convert user input into a JSON array of todo strings. "
    "NEVER ask questions or add commentary. Output ONLY the JSON array, nothing else. "
    'If input is one task, return ["task"]. If multiple, split into separate items. '
    "Keep each item under 100 chars."
)
