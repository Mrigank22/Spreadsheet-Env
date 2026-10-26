"""TRL integration.

Two ways to train with ``trl.GRPOTrainer``:

1. Multi-turn tool use (``environment_factory=SpreadsheetToolEnv``): every
   public method below becomes a tool; ``reset(task_id=...)`` receives the
   dataset row and returns the task instructions; ``get_reward()`` grades the
   workbook (submitting it if the model never called ``submit``).

2. Single-turn patch mode (``reward_funcs=[patch_reward]``): the dataset holds
   ``prompt`` (from ``patch_prompt``) and ``task_id``; the completion is a block
   of ``Sheet!Cell := content`` edits that is applied and graded.

The grader used for the reward is configurable, which is how the reward
ablation (value-only vs. full grader) is run: ``set_reward_oracles([...])``.
"""

from __future__ import annotations

from typing import List, Optional

from .grader.grader import ALL_ORACLES, Grader
from .session import Session
from .tasks import make_task

_GRADER = Grader()


def set_reward_oracles(oracles=ALL_ORACLES, value_only_tolerance: bool = False, reward_mode: str = "binary"):
    """Choose the grader that produces training rewards (e.g. ``["base"]`` for a value-only ablation)."""
    global _GRADER
    _GRADER = Grader(oracles=oracles, value_only_tolerance=value_only_tolerance, reward_mode=reward_mode)


class SpreadsheetToolEnv:
    """One spreadsheet episode exposed as tools for TRL's multi-turn GRPO."""

    def __init__(self):
        self._session: Optional[Session] = None

    def reset(self, **kwargs) -> str:
        task = make_task(kwargs["task_id"])
        self._session = Session(task, _GRADER)
        return "\n\n" + task.instructions

    def list_sheets(self) -> str:
        """List the workbook's sheets with their used ranges and formula counts.

        Returns:
            One line per sheet.
        """
        return self._session.list_sheets()

    def read_range(self, sheet: str, cell_range: str, show: str = "compact") -> str:
        """Read cells of one sheet.

        Args:
            sheet: Sheet name, e.g. "IS".
            cell_range: A1-style range such as "A1:J30", or a single cell.
            show: "compact" (filled-right formula runs collapsed), "both" (formula and value),
                "values" or "formulas".

        Returns:
            The cells, one line per row.
        """
        return self._session.read_range(sheet, cell_range, show)

    def write_cell(self, sheet: str, cell: str, content: str) -> str:
        """Write one cell: a formula starting with "=", a number, or text.

        Args:
            sheet: Sheet name.
            cell: Cell address such as "E5".
            content: Formula like "=D5*(1+Assumptions!E18)", a number, or "" to clear.

        Returns:
            The cell's new value, or an error message.
        """
        return self._session.write_cell(sheet, cell, content)

    def copy_cell(self, sheet: str, source: str, target_range: str) -> str:
        """Copy one cell into a range with relative references adjusted (Excel fill right).

        Args:
            sheet: Sheet of the source cell.
            source: Source cell such as "E5".
            target_range: Target range such as "F5:J5" (may be prefixed with another sheet).

        Returns:
            The pasted formulas and values.
        """
        return self._session.copy_cell(sheet, source, target_range)

    def trace(self, sheet: str, cell: str) -> str:
        """Show a cell's formula, value, direct precedents and direct dependents.

        Args:
            sheet: Sheet name.
            cell: Cell address.

        Returns:
            The audit trail of the cell.
        """
        return self._session.trace(sheet, cell)

    def submit(self, notes: str = "") -> str:
        """Submit the workbook for grading. This ends the episode.

        Args:
            notes: Optional summary of the changes.

        Returns:
            The grading summary.
        """
        return self._session.submit(notes)

    def get_reward(self) -> float:
        if self._session is None:
            return 0.0
        if not self._session.done:
            self._session.submit("(auto-submitted)")
        return float(self._session.reward)


def patch_reward(prompts=None, completions=None, task_id: Optional[List[str]] = None, **kwargs) -> List[float]:
    """Reward for single-turn patch mode (TRL reward-function signature)."""
    from .agents.runner import grade_patch

    out = []
    for comp, tid in zip(completions, task_id):
        text = comp if isinstance(comp, str) else comp[-1]["content"]
        try:
            res, _, _ = grade_patch(tid, text, _GRADER)
            out.append(float(res.reward))
        except Exception:  # noqa: BLE001 - an ungradable completion scores 0
            out.append(0.0)
    return out
