"""JSON schemas for AI command outputs."""

import json

DEFAULT_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {"tasks": {"type": "array", "items": {"type": "string"}}},
        "required": ["tasks"],
    }
)

ADD_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "priority": {
                            "type": ["string", "null"],
                            "enum": ["critical", "high", "normal", "low", "someday", None],
                        },
                        "tags": {"type": ["array", "null"], "items": {"type": "string"}},
                    },
                    "required": ["text"],
                },
            }
        },
        "required": ["tasks"],
    }
)

PRIORITIZE_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "assignments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "priority": {
                            "type": "string",
                            "enum": ["critical", "high", "normal", "low", "someday"],
                        },
                        "reason": {"type": "string"},
                    },
                    "required": ["id", "priority"],
                },
            }
        },
        "required": ["assignments"],
    }
)

TAG_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "suggestions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "tags"],
                },
            }
        },
        "required": ["suggestions"],
    }
)

REWORD_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "rewrites": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["id", "text"],
                },
            }
        },
        "required": ["rewrites"],
    }
)

RUN_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "Only include todos that changed, with changed fields + id",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "text": {"type": "string"},
                        "status": {"enum": ["pending", "done"]},
                        "priority": {
                            "type": ["string", "null"],
                            "enum": ["critical", "high", "normal", "low", "someday", None],
                        },
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "IDs of todos this one depends on (blockers)",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Brief explanation of why this change is needed",
                        },
                    },
                    "required": ["id", "reason"],
                },
            },
            "delete": {
                "type": "array",
                "description": "Todos to delete - ONLY when user explicitly requests",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "reason": {
                            "type": "string",
                            "description": "Why this should be deleted (must cite user request)",
                        },
                    },
                    "required": ["id", "reason"],
                },
            },
            "create": {
                "type": "array",
                "description": "New todos to create",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "priority": {
                            "type": ["string", "null"],
                            "enum": ["critical", "high", "normal", "low", "someday", None],
                        },
                        "tags": {"type": ["array", "null"], "items": {"type": "string"}},
                        "reason": {
                            "type": "string",
                            "description": "Why this new todo should be created",
                        },
                    },
                    "required": ["text", "reason"],
                },
            },
        },
        "required": ["todos", "delete", "create"],
    }
)

DEP_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "dependencies": {
                "type": "array",
                "description": "List of dependency relationships to add",
                "items": {
                    "type": "object",
                    "properties": {
                        "blocked_id": {
                            "type": "string",
                            "description": "ID of todo that is blocked (depends on another)",
                        },
                        "blocker_id": {
                            "type": "string",
                            "description": "ID of todo that blocks (must be done first)",
                        },
                    },
                    "required": ["blocked_id", "blocker_id"],
                },
            }
        },
        "required": ["dependencies"],
    }
)
