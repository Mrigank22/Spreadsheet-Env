"""Semantics-preserving rewrites of a correct model (false-positive testing).

A grader that rejects correct work is as harmful as one that accepts cheats:
it teaches the policy that only the reference's exact phrasing pays. These
rewrites produce many differently-written but equivalent solutions. Every one
of them must be graded as solved (``tests/test_equivalence.py``,
``scripts/exp_false_positives.py``).
"""

from __future__ import annotations

import random
from typing import Dict, Optional

from ..engine.parser import (
    Binary, Call, Node, Num, Ref, Rng, Unary, parse_formula, to_formula,
)
from ..engine.refs import CellRef
from ..engine.workbook import Key, Workbook


def _rewrite(node: Node, rng: random.Random, p: float) -> Node:
    """Recursively apply random equivalence-preserving transformations."""
    if isinstance(node, Unary):
        return Unary(node.op, _rewrite(node.operand, rng, p))
    if isinstance(node, Binary):
        left, right = _rewrite(node.left, rng, p), _rewrite(node.right, rng, p)
        op = node.op
        if op in ("+", "*") and rng.random() < p:
            left, right = right, left  # commutativity
        if op == "-" and rng.random() < p * 0.5:
            return Binary("+", left, Unary("-", right))  # a-b == a+(-b)
        if op == "*" and rng.random() < p * 0.3:
            return Binary("/", left, Binary("/", Num(1.0), right)) if not _is_zero_possible(right) else Binary(op, left, right)
        return Binary(op, left, right)
    if isinstance(node, Call):
        args = tuple(_rewrite(a, rng, p) for a in node.args)
        if node.name == "MAX" and len(args) == 2 and isinstance(args[0], Num) and args[0].value == 0 and rng.random() < p:
            x = args[1]
            return Call("IF", (Binary(">", x, Num(0.0)), x, Num(0.0)))
        if node.name == "MIN" and len(args) == 2 and rng.random() < p:
            a, b = args
            return Call("IF", (Binary("<", a, b), a, b))
        if node.name == "SUM" and len(args) == 1 and isinstance(args[0], Rng) and rng.random() < p:
            r = args[0].ref
            terms = [Ref(CellRef(r.sheet, row, col)) for row in r.rows for col in r.cols]
            expr: Node = terms[0]
            for t in terms[1:]:
                expr = Binary("+", expr, t)
            return expr
        if node.name == "AVERAGE" and len(args) == 2 and rng.random() < p:
            return Binary("/", Binary("+", args[0], args[1]), Num(2.0))
        return Call(node.name, args)
    if isinstance(node, Ref) and rng.random() < p * 0.3:
        r = node.ref
        return Ref(CellRef(r.sheet, r.row, r.col, True, r.col_abs))  # extra $ on the row
    return node


def _is_zero_possible(node: Node) -> bool:
    # dividing by a reference that might be zero would change semantics
    return not (isinstance(node, Num) and node.value != 0)


def equivalent_rewrite(reference: Workbook, keys, rng: random.Random, p: float = 0.5,
                       helper_p: float = 0.2, helper_col_offset: Optional[int] = None) -> Workbook:
    """Rewrite every formula in ``keys``; optionally move it into a helper cell.

    Helper cells are placed ``helper_col_offset`` columns to the right (by
    default far enough to clear every used column, so wide monthly models are
    not overwritten) and the original cell becomes ``=helper``; this changes
    the layout of the dependency graph but not the semantics.
    """
    if helper_col_offset is None:
        helper_col_offset = max(30, max((c for _, _, c, _ in reference.cells()), default=0) + 2)
    wb = reference.copy()
    for k in keys:
        raw = reference.raw(k)
        if not (isinstance(raw, str) and raw.startswith("=")):
            continue
        new = _rewrite(parse_formula(raw), rng, p)
        sheet = wb.sheet_name(k[0])
        if rng.random() < helper_p:
            hc = k[2] + helper_col_offset
            # relative references must still point at the same cells from the helper
            from ..engine.parser import translate

            wb.set_rc(sheet, k[1], hc, to_formula(_absolutise(new)))
            wb.set_rc(sheet, k[1], k[2], to_formula(Ref(CellRef(None, k[1], hc))))
        else:
            wb.set_rc(sheet, k[1], k[2], to_formula(new))
    return wb


def _absolutise(node: Node) -> Node:
    from ..engine.parser import map_refs
    from ..engine.refs import RangeRef

    def f(n):
        if isinstance(n, Ref):
            r = n.ref
            return Ref(CellRef(r.sheet, r.row, r.col, True, True))
        r = n.ref
        return Rng(RangeRef(r.sheet, CellRef(r.start.sheet, r.start.row, r.start.col, True, True),
                            CellRef(r.end.sheet, r.end.row, r.end.col, True, True)))

    return map_refs(node, f)
