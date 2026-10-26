"""OpenEnv environment: multi-turn spreadsheet editing through MCP tools.

``reset`` picks a task (by ``task_id``, or sampled from ``families`` /
``difficulties`` with ``seed``) and returns its instructions. The agent then
calls tools (``list_sheets``, ``read_range``, ``write_cell``, ``copy_cell``,
``trace``, ``find``, ``submit``) through ``CallToolAction``. The episode ends
on ``submit`` or when the step budget runs out; the observation returned then
carries ``done=True``, the reward and the per-oracle components.

A single-turn ``PatchAction`` (a list of edits) is also accepted, for training
small models without a multi-turn tool loop.
"""

from __future__ import annotations

import random
from typing import Any, List, Optional, Sequence
from uuid import uuid4

from fastmcp import FastMCP
from openenv.core.env_server.mcp_environment import MCPEnvironment
from openenv.core.env_server.types import Action, Observation, State

from .grader.grader import ALL_ORACLES, Grader
from .models import PatchAction, SpreadsheetObservation
from .session import Session
from .tasks import make_task, sample_task_id


class SpreadsheetEnvironment(MCPEnvironment):
    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self, families: Optional[Sequence[str]] = None,
                 difficulties: Optional[Sequence[int]] = None, split: str = "train",
                 reward_mode: str = "binary", oracles: Sequence[str] = ALL_ORACLES):
        mcp = FastMCP("spreadsheet-env")
        self.families = list(families) if families else None
        self.difficulties = list(difficulties) if difficulties else None
        self.split = split
        self.grader = Grader(oracles=oracles, reward_mode=reward_mode)
        self.session: Optional[Session] = None
        self._state = State(episode_id=str(uuid4()), step_count=0)
        env = self

        def _s() -> Session:
            if env.session is None:
                raise RuntimeError("call reset() first")
            return env.session

        @mcp.tool
        def list_sheets() -> str:
            """List the workbook's sheets with their used ranges and formula counts."""
            return _s().list_sheets()

        @mcp.tool
        def read_range(sheet: str, cell_range: str, show: str = "both") -> str:
            """Read cells. ``cell_range`` like "A1:J20" (or one cell). ``show`` is "both"
            (formula and value), "values" or "formulas"."""
            return _s().read_range(sheet, cell_range, show)

        @mcp.tool
        def write_cell(sheet: str, cell: str, content: str) -> str:
            """Write one cell: a formula starting with "=", a number, or text. Empty clears it.
            Returns the cell's new value."""
            return _s().write_cell(sheet, cell, content)

        @mcp.tool
        def write_cells(edits: List[dict]) -> str:
            """Write several cells in one call. ``edits`` is a list of objects
            {"cell": "IS!E5", "content": "=D5*(1+Assumptions!E18)"} (sheet prefix required
            unless "sheet" is given as a separate key)."""
            return _s().write_cells(edits)

        @mcp.tool
        def copy_cell(sheet: str, source: str, target_range: str) -> str:
            """Copy one cell's content into every cell of ``target_range`` with relative
            references adjusted (Excel copy-paste / fill-right). ``target_range`` may be
            prefixed with another sheet, e.g. "IS!F5:J5"."""
            return _s().copy_cell(sheet, source, target_range)

        @mcp.tool
        def trace(sheet: str, cell: str) -> str:
            """Show a cell's formula, value, direct precedents and direct dependents."""
            return _s().trace(sheet, cell)

        @mcp.tool
        def find(text: str) -> str:
            """Find label/text cells containing ``text`` (case-insensitive)."""
            return _s().find(text)

        @mcp.tool
        def submit(notes: str = "") -> str:
            """Submit the workbook for grading. This ends the episode."""
            return _s().submit(notes)

        super().__init__(mcp)

    # ------------------------------------------------------------------
    def reset(self, seed: Optional[int] = None, episode_id: Optional[str] = None,
              task_id: Optional[str] = None, **kwargs: Any) -> SpreadsheetObservation:
        if task_id is None:
            rng = random.Random(seed)
            task_id = sample_task_id(rng, self.families, self.difficulties, self.split)
        task = make_task(task_id)
        self.session = Session(task, self.grader)
        self._state = State(episode_id=episode_id or str(uuid4()), step_count=0)
        self._state.task_id = task.task_id  # type: ignore[attr-defined]
        return SpreadsheetObservation(
            task_id=task.task_id, family=task.family, difficulty=task.difficulty,
            text=task.instructions, done=False, reward=0.0,
        )

    def _finish(self, obs: Observation) -> Observation:
        s = self.session
        self._state.step_count += 1
        if s is not None and s.done:
            obs.done = True
            obs.reward = s.reward
            if s.result is not None:
                obs.metadata = dict(obs.metadata or {})
                obs.metadata.update({"solved": s.result.solved, "components": s.result.components,
                                     "task_id": s.task.task_id})
        return obs

    def step(self, action: Action, timeout_s: Optional[float] = None, **kwargs: Any) -> Observation:
        return self._finish(super().step(action, timeout_s=timeout_s, **kwargs))

    async def step_async(self, action: Action, timeout_s: Optional[float] = None, **kwargs: Any) -> Observation:
        return self._finish(await super().step_async(action, timeout_s=timeout_s, **kwargs))

    def _step_impl(self, action: Action, timeout_s: Optional[float] = None, **kwargs: Any) -> Observation:
        if self.session is None:
            raise RuntimeError("call reset() first")
        if not isinstance(action, PatchAction):
            raise ValueError(f"unsupported action type {type(action).__name__}")
        s = self.session
        msgs: List[str] = s.apply_patch(action.edits)
        text = "\n".join(msgs)
        if action.submit:
            text = (text + "\n" if text else "") + s.submit(action.notes)
        res = s.result
        return SpreadsheetObservation(
            task_id=s.task.task_id, family=s.task.family, difficulty=s.task.difficulty, text=text,
            done=s.done, reward=s.reward, solved=bool(res and res.solved),
            components=dict(res.components) if res else {},
        )

    @property
    def state(self) -> State:
        return self._state
