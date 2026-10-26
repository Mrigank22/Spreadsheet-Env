"""Tool schemas (JSON Schema) and a dispatcher shared by every agent interface.

The MCP server, the Anthropic/OpenAI-style agent loop and local chat-template
agents all expose exactly these tools, implemented by ``Session``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .session import Session

TOOL_SPECS: List[Dict[str, Any]] = [
    {
        "name": "list_sheets",
        "description": "List the workbook's sheets with their used ranges and formula counts.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "read_range",
        "description": ("Read cells of one sheet. Formula cells are shown as '=formula -> value'. "
                        "Use show='values' or 'formulas' for a compact view."),
        "parameters": {
            "type": "object",
            "properties": {
                "sheet": {"type": "string", "description": "sheet name, e.g. 'IS'"},
                "cell_range": {"type": "string", "description": "A1-style range, e.g. 'A1:J30', or one cell"},
                "show": {"type": "string", "enum": ["both", "values", "formulas", "compact"], "default": "both"},
            },
            "required": ["sheet", "cell_range"],
        },
    },
    {
        "name": "write_cell",
        "description": ("Write one cell: a formula starting with '=', a number, or text (empty string clears). "
                        "Returns the new value."),
        "parameters": {
            "type": "object",
            "properties": {
                "sheet": {"type": "string"},
                "cell": {"type": "string", "description": "e.g. 'E5'"},
                "content": {"type": "string", "description": "e.g. '=D5*(1+Assumptions!E18)'"},
            },
            "required": ["sheet", "cell", "content"],
        },
    },
    {
        "name": "write_cells",
        "description": ("Write several cells in one call. Each edit is {'cell': 'IS!E5', 'content': '=...'} "
                        "(sheet prefix required)."),
        "parameters": {
            "type": "object",
            "properties": {
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"cell": {"type": "string"}, "content": {"type": "string"}},
                        "required": ["cell", "content"],
                    },
                },
            },
            "required": ["edits"],
        },
    },
    {
        "name": "copy_cell",
        "description": ("Copy one cell into every cell of target_range with relative references adjusted "
                        "(Excel copy-paste / fill right). target_range may name another sheet, e.g. 'IS!F5:J5'."),
        "parameters": {
            "type": "object",
            "properties": {
                "sheet": {"type": "string", "description": "sheet of the source cell"},
                "source": {"type": "string", "description": "e.g. 'E5'"},
                "target_range": {"type": "string", "description": "e.g. 'F5:J5'"},
            },
            "required": ["sheet", "source", "target_range"],
        },
    },
    {
        "name": "trace",
        "description": "Show a cell's formula, value, direct precedents and direct dependents.",
        "parameters": {
            "type": "object",
            "properties": {"sheet": {"type": "string"}, "cell": {"type": "string"}},
            "required": ["sheet", "cell"],
        },
    },
    {
        "name": "find",
        "description": "Find label/text cells containing the given text (case-insensitive).",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "submit",
        "description": "Submit the workbook for grading. This ends the episode.",
        "parameters": {
            "type": "object",
            "properties": {"notes": {"type": "string", "description": "optional: what you changed"}},
            "required": [],
        },
    },
]

TOOL_NAMES = [t["name"] for t in TOOL_SPECS]


def call_tool(session: Session, name: str, args: Dict[str, Any]) -> str:
    """Execute a tool call; never raises (errors are returned as text)."""
    if name not in TOOL_NAMES:
        return f"error: unknown tool {name!r}; tools are {', '.join(TOOL_NAMES)}"
    if not isinstance(args, dict):
        try:
            args = json.loads(args) if isinstance(args, str) else {}
        except json.JSONDecodeError:
            return "error: arguments must be a JSON object"
    fn = getattr(session, name)
    try:
        return fn(**args)
    except TypeError as e:
        return f"error: bad arguments for {name}: {e}"
    except Exception as e:  # noqa: BLE001 - tools must never crash the episode
        return f"error: {type(e).__name__}: {e}"


def anthropic_tools() -> List[Dict[str, Any]]:
    return [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
            for t in TOOL_SPECS]


def openai_tools() -> List[Dict[str, Any]]:
    return [{"type": "function", "function": t} for t in TOOL_SPECS]
