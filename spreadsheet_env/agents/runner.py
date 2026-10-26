"""Episode runners: multi-turn tool use and single-turn patch mode.

A *policy* is any object with ``act(messages, tools) -> AgentTurn``; the
runner owns the Session, executes tool calls, appends results, and stops on
``submit``, on the step budget, or when the policy stops calling tools (then
the workbook is submitted as-is). Everything the agent saw and did is kept in
the returned transcript, so episodes can be audited.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..engine.refs import addr
from ..grader.grader import Grader
from ..session import Session, fmt_value, parse_patch_text
from ..tasks import make_task
from ..tools import TOOL_SPECS, call_tool

SYSTEM_PROMPT = (
    "You are an expert financial modeller working in a spreadsheet through tools. Inspect the workbook, "
    "make the required changes with live formulas, check your work, then call submit. Keep tool calls "
    "focused: read only the ranges you need and batch edits with write_cells or copy_cell."
)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class AgentTurn:
    text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: Any = None  # provider-specific assistant message, replayed verbatim
    usage: Dict[str, int] = field(default_factory=dict)


@dataclass
class EpisodeResult:
    task_id: str
    family: str
    difficulty: int
    reward: float
    solved: bool
    components: Dict[str, float]
    steps: int
    turns: int
    seconds: float
    usage: Dict[str, int]
    submitted: bool
    violations: List[str]
    failing: List[str]
    transcript: List[Dict[str, Any]]
    error: str = ""

    def to_json(self, with_transcript: bool = True) -> Dict[str, Any]:
        d = dict(self.__dict__)
        if not with_transcript:
            d.pop("transcript")
        return d


def run_tool_episode(policy, task_id: str, grader: Optional[Grader] = None, max_turns: Optional[int] = None,
                     system_prompt: str = SYSTEM_PROMPT) -> EpisodeResult:
    task = make_task(task_id)
    session = Session(task, grader or Grader())
    messages: List[Dict[str, Any]] = [{"role": "user", "content": task.instructions}]
    transcript: List[Dict[str, Any]] = [{"role": "user", "content": task.instructions}]
    usage: Dict[str, int] = {}
    t0 = time.time()
    turns = 0
    err = ""
    max_turns = max_turns or task.max_steps
    try:
        while not session.done and turns < max_turns:
            turns += 1
            turn: AgentTurn = policy.act(system_prompt, messages, TOOL_SPECS)
            for k, v in turn.usage.items():
                usage[k] = usage.get(k, 0) + v
            messages.append(policy.assistant_message(turn))
            transcript.append({"role": "assistant", "text": turn.text,
                               "tool_calls": [{"name": c.name, "arguments": c.arguments} for c in turn.tool_calls]})
            if not turn.tool_calls:
                messages.append(policy.user_nudge())
                if turns >= 2 and transcript[-2].get("role") == "nudge":
                    break  # the model stopped using tools twice: submit as-is
                transcript.append({"role": "nudge"})
                continue
            results = []
            for c in turn.tool_calls:
                out = call_tool(session, c.name, c.arguments)
                results.append((c, out))
                transcript.append({"role": "tool", "name": c.name, "content": out[:4000]})
                if session.done:
                    break
            messages.extend(policy.tool_result_messages(results))
    except Exception as e:  # noqa: BLE001 - provider/network errors end the episode
        err = f"{type(e).__name__}: {e}"
    submitted = session.done
    if not session.done:
        session.submit("(auto-submitted by runner)")
    res = session.result
    return EpisodeResult(task.task_id, task.family, task.difficulty, res.reward, res.solved, dict(res.components),
                         session.steps, turns, round(time.time() - t0, 1), usage, submitted, res.violations,
                         res.failing[:20], transcript, err)


# --------------------------------------------------------------------------- single-turn
PATCH_FORMAT = (
    "Answer with your reasoning (optional) followed by ONE fenced code block containing one edit per line, "
    "in the form\n```\nSheet!Cell := content\n```\nwhere content is a formula starting with '=' (or a number). "
    "A range on the left (e.g. IS!E5:J5) writes the formula into the first cell and fills it right with "
    "relative references adjusted, exactly like Excel's fill. Example:\n```\nIS!E5:J5 := =D5*(1+Assumptions!E18)\n"
    "BS!F9 := =E9-CFS!F11-IS!F10\n```\nOnly the last code block is applied."
)


def render_workbook(session: Session, max_cells: int = 4000, compact: bool = False) -> str:
    """Every non-empty cell of every sheet, formula cells with their values
    (``compact``: filled-right formula runs collapsed, no computed values)."""
    if compact:
        from ..session import compact_rows

        out = []
        for sheet in session.wb.sheet_names:
            out.append(f"=== Sheet {sheet} ===")
            out.extend(compact_rows(session.wb, sheet))
        return "\n".join(out)
    vals = session._values()
    out = []
    n = 0
    for sheet in session.wb.sheet_names:
        out.append(f"=== Sheet {sheet} ===")
        rows: Dict[int, List[str]] = {}
        for _, r, c, raw in session.wb.cells(sheet):
            n += 1
            if n > max_cells:
                break
            a = addr(r, c)
            if isinstance(raw, str) and raw.startswith("="):
                rows.setdefault(r, []).append(f"{a} {raw} -> {fmt_value(vals.get((sheet.casefold(), r, c)))}")
            else:
                rows.setdefault(r, []).append(f"{a} {fmt_value(raw)}")
        for r in sorted(rows):
            out.append(f"r{r}: " + " | ".join(rows[r]))
    return "\n".join(out)


def patch_prompt(task_id: str, compact: bool = True) -> str:
    task = make_task(task_id)
    s = Session(task)
    view = ("compact view: a run of cells holding the same formula filled right is shown once as "
            "'E5:J5 =formula [filled right]' (the formula as written in the first cell)" if compact
            else "every non-empty cell, formulas shown as '=formula -> value'")
    instr = task.instructions
    # the model map duplicates the workbook view shown below
    if "\nMODEL MAP:\n" in instr:
        head, _, tail = instr.partition("\nMODEL MAP:\n")
        rest = tail.split("\n\n", 1)
        instr = head + ("\n\n" + rest[1] if len(rest) > 1 else "")
    instr = instr.replace("Use the tools to inspect and edit the workbook. Call submit when you are done.", "")
    # a concrete, task-specific example of the edit syntax (small models copy generic
    # placeholders such as "Sheet!Cell" literally)
    k = task.target_keys[0]
    example = (f"\nThe sheet name must be a real sheet of this workbook ({', '.join(task.initial.sheet_names)}), "
               f"e.g. a line starting with {task.reference.sheet_name(k[0])}!{addr(k[1], k[2])} := = ...")
    return (instr.rstrip() + f"\n\nTHE WORKBOOK ({view}):\n" + render_workbook(s, compact=compact)
            + "\n\n" + PATCH_FORMAT + example)


def grade_patch(task_id: str, completion: str, grader: Optional[Grader] = None):
    task = make_task(task_id)
    s = Session(task, grader or Grader(), max_steps=10_000)
    edits = parse_patch_text(completion)
    errors = s.apply_patch(edits)
    s.submit()
    return s.result, edits, errors


def to_jsonl(results: List[EpisodeResult], path: str, with_transcript: bool = True) -> None:
    with open(path, "a", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r.to_json(with_transcript), default=str) + "\n")
