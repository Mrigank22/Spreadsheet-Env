"""OpenEnv Action/Observation models."""

from __future__ import annotations

from typing import Dict, List

from openenv.core.env_server.types import Action, Observation
from pydantic import Field


class PatchAction(Action):
    """Single-turn mode: apply a list of cell edits, then (by default) submit.

    Each edit is ``{"sheet": "IS", "cell": "E5", "content": "=D5*(1+Assumptions!E18)"}``.
    Multi-turn agents use the MCP tools instead (``CallToolAction``).
    """

    edits: List[Dict[str, str]] = Field(default_factory=list)
    submit: bool = Field(default=True)
    notes: str = Field(default="")


class SpreadsheetObservation(Observation):
    task_id: str = Field(default="")
    family: str = Field(default="")
    difficulty: int = Field(default=0)
    text: str = Field(default="", description="instructions on reset; tool/grade text afterwards")
    solved: bool = Field(default=False)
    components: Dict[str, float] = Field(default_factory=dict)
