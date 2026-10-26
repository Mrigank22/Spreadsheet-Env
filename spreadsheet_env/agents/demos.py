"""Expert demonstrations in patch format, generated from the hidden reference.

Used for (a) SFT warm-starts before RL and (b) testing that every task is
solvable through the single-turn interface. Runs of filled-right formulas are
written as range edits; each edit is preceded by a ``#`` comment stating the
methodology it implements (comment lines are ignored by the patch parser).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from ..engine.refs import addr
from ..session import r1c1_signature
from ..task import Task


def _runs(task: Task, keys) -> List[Tuple[str, int, int, int, str]]:
    """(sheet, row, first col, last col, formula) runs of filled-right formulas."""
    by_row: Dict[Tuple[str, int], List[int]] = defaultdict(list)
    for k in keys:
        by_row[(k[0], k[1])].append(k[2])
    out = []
    for (sk, r), cols in sorted(by_row.items()):
        cols.sort()
        i = 0
        while i < len(cols):
            c0 = cols[i]
            f0 = task.reference.raw((sk, r, c0))
            sig = r1c1_signature(f0, r, c0) if isinstance(f0, str) else None
            j = i
            while (j + 1 < len(cols) and cols[j + 1] == cols[j] + 1 and sig is not None
                   and isinstance(task.reference.raw((sk, r, cols[j + 1])), str)
                   and r1c1_signature(task.reference.raw((sk, r, cols[j + 1])), r, cols[j + 1]) == sig):
                j += 1
            out.append((task.reference.sheet_name(sk), r, c0, cols[j], f0))
            i = j + 1
    return out


def _comment(task: Task, sheet: str, row: int) -> str:
    spec = task.meta.get("spec")
    lay = task.meta.get("layout")
    if spec is not None and lay is not None:
        for ln in spec.lines:
            if lay.rows.get(ln.id) == (sheet, row) or (ln.id in lay.rows and lay.rows[ln.id][0].casefold() == sheet.casefold()
                                                      and lay.rows[ln.id][1] == row):
                return f"# {ln.label}: {ln.desc}"
        for c in getattr(spec, "calcs", []):
            s, r, _ = lay.calcs[c.id]
            if s.casefold() == sheet.casefold() and r == row:
                return f"# {c.label}: {c.desc}"
    label = task.reference.get_rc(sheet, row, 1)
    return f"# {label}" if isinstance(label, str) else ""


def expert_patch(task: Task, with_comments: bool = True) -> str:
    if task.family == "repair" or task.family.endswith("_repair"):
        keys = sorted({tuple(k) for k in task.meta.get("bug_cells", [])})
        if not keys:
            return "I checked every forecast formula against the methodology; the model is correct.\n```\n```"
        intro = "These formulas deviate from the methodology; corrected versions:"
    elif task.family == "build_free" or task.family.endswith("_free"):
        # the whole model (reference layout) plus the output links
        keys = [k for k, v in task.reference.snapshot().items()
                if k[0] == "model" and isinstance(v, str) and v.startswith("=")] + list(task.target_keys)
        intro = "Model built on the Model sheet (one row per line item, same columns as the inputs), then linked:"
    else:
        keys = task.target_keys
        intro = "Formulas for the empty cells, following the methodology:"
    lines = []
    for sheet, r, c0, c1, f in _runs(task, keys):
        if with_comments:
            cm = _comment(task, sheet, r)
            if cm:
                lines.append(cm)
        target = addr(r, c0) if c0 == c1 else f"{addr(r, c0)}:{addr(r, c1)}"
        lines.append(f"{sheet}!{target} := {f}")
    return intro + "\n```\n" + "\n".join(lines) + "\n```"
