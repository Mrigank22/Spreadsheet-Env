"""Evidence-grounded bug injection for repair tasks.

Each operator mimics one real-world spreadsheet error class (see
``docs/research/01_error_taxonomy.md`` for sources and frequencies). Operators
act on the Excel AST of reference formulas, either on one period cell
("cell" scope: an inconsistent cell in the row, the classic slip) or on the
whole forecast row ("row" scope: a consistent but wrong formula, which
inconsistency detectors like ExceLint cannot see).

Every candidate mutant is recalculated against the reference under the task's
scenarios and classified:

* ``equivalent`` - no target cell changes in any scenario -> rejected
* ``visible``    - some value differs at the base inputs
* ``latent``     - base values identical, but some scenario differs
                   (stale hard-codes, coincident references, branch errors).
                   A value-matching grader cannot see these.

Mutants that create errors (#VALUE!, #DIV/0! ...) or circular references at
the base case are rejected, so every bug is a plausible silent error.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from ..engine.parser import (
    Binary, Call, Node, Num, Ref, Rng, Unary, parse_formula, to_formula, translate, walk,
)
from ..engine.refs import CellRef, ExcelError, RangeRef, addr
from ..engine.workbook import Key, Workbook
from ..grader.grader import close
from ..model.spec import Layout, ModelSpec

# Powell et al. (2009) wrong-result mix -> operator sampling weights.
OPERATORS: Dict[str, dict] = {
    "REF_SHIFT": dict(category="reference", weight=0.16, latent_prone=False),
    "PERIOD_OFFSET": dict(category="reference", weight=0.12, latent_prone=False),
    "RANGE_TRUNCATE": dict(category="reference", weight=0.08, latent_prone=False),
    "ANCHOR_DROP": dict(category="reference", weight=0.07, latent_prone=False),
    "COINCIDENT_REF": dict(category="reference", weight=0.07, latent_prone=True),
    "RANGE_EXTEND": dict(category="logic", weight=0.06, latent_prone=False),
    "SIGN_FLIP": dict(category="logic", weight=0.08, latent_prone=False),
    "OPERATOR_SWAP": dict(category="logic", weight=0.08, latent_prone=False),
    "FLOOR_REMOVAL": dict(category="logic", weight=0.07, latent_prone=True),
    "UNIT_ERROR": dict(category="logic", weight=0.03, latent_prone=False),
    "HARDCODE_PASTE": dict(category="hard-coding", weight=0.07, latent_prone=True),
    "JAMMED_CONSTANT": dict(category="hard-coding", weight=0.06, latent_prone=True),
    "LINK_OMISSION": dict(category="omission", weight=0.05, latent_prone=False),
}


@dataclass
class Mutation:
    operator: str
    scope: str  # cell | row
    line: str
    cells: Dict[Key, object]  # key -> new raw content
    original: Dict[Key, object]
    effect: str = ""  # visible | latent | equivalent | invalid
    description: str = ""
    category: str = ""
    meta: dict = field(default_factory=dict)

    def to_dict(self, label: Callable[[Key], str]) -> dict:
        return {
            "operator": self.operator, "category": self.category, "scope": self.scope,
            "line": self.line, "effect": self.effect,
            "cells": {label(k): {"bug": v, "correct": self.original[k]} for k, v in self.cells.items()},
        }


# --------------------------------------------------------------------------
# AST helpers
# --------------------------------------------------------------------------

def _nodes(ast: Node, cls) -> List[Node]:
    return [n for n in walk(ast) if isinstance(n, cls)]


def _replace(ast: Node, target: Node, new: Node) -> Node:
    """Replace the first occurrence (by identity) of ``target``."""
    done = [False]

    def rec(n):
        if n is target and not done[0]:
            done[0] = True
            return new
        if isinstance(n, Unary):
            return Unary(n.op, rec(n.operand))
        if isinstance(n, Binary):
            return Binary(n.op, rec(n.left), rec(n.right))
        if isinstance(n, Call):
            return Call(n.name, tuple(rec(a) for a in n.args))
        return n

    return rec(ast)


def _ref_with(r: CellRef, row: Optional[int] = None, col: Optional[int] = None,
              row_abs: Optional[bool] = None, col_abs: Optional[bool] = None) -> CellRef:
    return CellRef(r.sheet, r.row if row is None else row, r.col if col is None else col,
                   r.row_abs if row_abs is None else row_abs, r.col_abs if col_abs is None else col_abs)


class _Ctx:
    """What operators need to know about the model."""

    def __init__(self, wb: Workbook, spec: ModelSpec, lay: Layout, base: Dict[Key, object]):
        self.wb, self.spec, self.lay, self.base = wb, spec, lay, base
        self.period_cols = {lay.col(p) for p in range(lay.n_periods)}
        self.forecast_cols = {lay.col(p) for p in lay.forecast_indices}

    def sheet_of(self, r: CellRef, home: str) -> str:
        return (r.sheet or home).casefold()

    def numeric_at(self, sheet_key: str, row: int, col: int) -> bool:
        return isinstance(self.base.get((sheet_key, row, col)), float)


# --------------------------------------------------------------------------
# Operators: each returns a new AST (or None) for one formula
# --------------------------------------------------------------------------

def op_ref_shift(ast, ctx: _Ctx, home: str, rng: random.Random):
    refs = [n for n in _nodes(ast, Ref)]
    rng.shuffle(refs)
    for n in refs:
        sk = ctx.sheet_of(n.ref, home)
        for d in rng.sample([-1, 1], 2):
            row = n.ref.row + d
            if row >= 4 and ctx.numeric_at(sk, row, n.ref.col):
                return _replace(ast, n, Ref(_ref_with(n.ref, row=row))), f"{n.ref.a1()} -> row {row}"
    return None


def op_period_offset(ast, ctx: _Ctx, home: str, rng: random.Random):
    refs = [n for n in _nodes(ast, Ref) if not n.ref.col_abs and n.ref.col in ctx.period_cols]
    rng.shuffle(refs)
    for n in refs:
        for d in rng.sample([-1, 1], 2):
            col = n.ref.col + d
            if col in ctx.period_cols and ctx.numeric_at(ctx.sheet_of(n.ref, home), n.ref.row, col):
                return _replace(ast, n, Ref(_ref_with(n.ref, col=col))), f"{n.ref.a1()} period {d:+d}"
    return None


def op_range_truncate(ast, ctx, home, rng):
    for n in _nodes(ast, Rng):
        r = n.ref
        if len(r.rows) >= 2:
            if rng.random() < 0.7:
                new = RangeRef(r.sheet, r.start, _ref_with(r.end, row=r.end.row - 1))
            else:
                new = RangeRef(r.sheet, _ref_with(r.start, row=r.start.row + 1), r.end)
            return _replace(ast, n, Rng(new)), f"{r.a1()} -> {new.a1()}"
    return None


def op_range_extend(ast, ctx: _Ctx, home, rng):
    for n in _nodes(ast, Rng):
        r = n.ref
        sk = ctx.sheet_of(r.start, home)
        row = r.end.row + 1
        if ctx.numeric_at(sk, row, r.end.col):
            new = RangeRef(r.sheet, r.start, _ref_with(r.end, row=row))
            return _replace(ast, n, Rng(new)), f"{r.a1()} -> {new.a1()} (double count)"
    return None


def op_sign_flip(ast, ctx, home, rng):
    bins = [n for n in _nodes(ast, Binary) if n.op in "+-"]
    unas = [n for n in _nodes(ast, Unary) if n.op == "-"]
    if unas and (not bins or rng.random() < 0.4):
        n = rng.choice(unas)
        return _replace(ast, n, n.operand), "dropped a minus sign"
    if bins:
        n = rng.choice(bins)
        new = Binary("-" if n.op == "+" else "+", n.left, n.right)
        return _replace(ast, n, new), f"'{n.op}' -> '{new.op}'"
    return None


def op_operator_swap(ast, ctx, home, rng):
    calls = [n for n in _nodes(ast, Call) if n.name in ("SUM", "MAX", "MIN")]
    bins = [n for n in _nodes(ast, Binary) if n.op in "*/"]
    if calls and (not bins or rng.random() < 0.5):
        n = rng.choice(calls)
        swap = {"SUM": "AVERAGE", "MAX": "MIN", "MIN": "MAX"}[n.name]
        return _replace(ast, n, Call(swap, n.args)), f"{n.name} -> {swap}"
    if bins:
        n = rng.choice(bins)
        new = Binary("/" if n.op == "*" else "*", n.left, n.right)
        return _replace(ast, n, new), f"'{n.op}' -> '{new.op}'"
    return None


def op_floor_removal(ast, ctx, home, rng):
    for n in _nodes(ast, Call):
        if n.name in ("MAX", "MIN") and len(n.args) == 2:
            keep = n.args[1] if isinstance(n.args[0], Num) else n.args[0]
            if n.name == "MIN":
                keep = n.args[0]  # e.g. -MIN(repay, debt) -> -repay
            return _replace(ast, n, keep), f"removed {n.name}() guard"
    return None


def op_unit_error(ast, ctx, home, rng):
    for n in _nodes(ast, Num):
        if n.value == 365.0:
            return _replace(ast, n, Num(360.0)), "365 -> 360 day basis"
    return None


def op_link_omission(ast, ctx, home, rng):
    bins = [n for n in _nodes(ast, Binary) if n.op in "+-"]
    if not bins:
        return None
    n = rng.choice(bins)
    return _replace(ast, n, n.left), "dropped a term"


def op_jammed_constant(ast, ctx: _Ctx, home, rng):
    refs = [n for n in _nodes(ast, Ref) if n.ref.col_abs and n.ref.row_abs]
    if not refs:
        return None
    n = rng.choice(refs)
    v = ctx.base.get((ctx.sheet_of(n.ref, home), n.ref.row, n.ref.col))
    if not isinstance(v, float):
        return None
    if rng.random() < 0.6:
        lit = v  # latent: the literal equals today's input
        why = "assumption typed into formula (equal to current input)"
    else:
        lit = round(v * rng.choice([0.8, 0.9, 1.1, 1.25]), 4)  # stale value
        why = "stale assumption typed into formula"
    return _replace(ast, n, Num(lit)), why


def op_coincident_ref(ast, ctx: _Ctx, home, rng):
    """Point a reference at a different cell that happens to hold the same value."""
    refs = _nodes(ast, Ref)
    rng.shuffle(refs)
    for n in refs:
        sk = ctx.sheet_of(n.ref, home)
        v = ctx.base.get((sk, n.ref.row, n.ref.col))
        if not isinstance(v, float) or v == 0.0:
            continue
        for (s2, r2, c2), v2 in ctx.base.items():
            if (s2, r2, c2) == (sk, n.ref.row, n.ref.col) or not isinstance(v2, float):
                continue
            if v2 == v and (s2 != sk or r2 != n.ref.row or c2 != n.ref.col):
                sheet = ctx.wb.sheet_name(s2)
                new = CellRef(sheet if s2 != home.casefold() else None, r2, c2, n.ref.row_abs, n.ref.col_abs)
                return _replace(ast, n, Ref(new)), f"{n.ref.a1()} -> {new.a1()} (same value today)"
    return None


AST_OPS = {
    "REF_SHIFT": op_ref_shift,
    "PERIOD_OFFSET": op_period_offset,
    "RANGE_TRUNCATE": op_range_truncate,
    "RANGE_EXTEND": op_range_extend,
    "SIGN_FLIP": op_sign_flip,
    "OPERATOR_SWAP": op_operator_swap,
    "FLOOR_REMOVAL": op_floor_removal,
    "UNIT_ERROR": op_unit_error,
    "LINK_OMISSION": op_link_omission,
    "JAMMED_CONSTANT": op_jammed_constant,
    "COINCIDENT_REF": op_coincident_ref,
}


# --------------------------------------------------------------------------
# Candidate generation
# --------------------------------------------------------------------------

def _line_cells(spec: ModelSpec, lay: Layout, lid: str) -> List[Key]:
    return [lay.key(lid, p) for p in lay.forecast_indices]


def propose(op: str, scope: str, lid: str, wb: Workbook, spec: ModelSpec, lay: Layout,
            base: Dict[Key, object], rng: random.Random) -> Optional[Mutation]:
    ctx = _Ctx(wb, spec, lay, base)
    sheet = lay.rows[lid][0]
    keys = _line_cells(spec, lay, lid)
    if scope == "cell":
        keys = [rng.choice(keys)]
    original = {k: wb.raw(k) for k in keys}
    if not all(isinstance(v, str) and v.startswith("=") for v in original.values()):
        return None
    cells: Dict[Key, object] = {}
    desc = ""
    if op == "HARDCODE_PASTE":
        for k in keys:
            cells[k] = base[k]
        desc = "formula replaced by its current value"
    elif op == "ANCHOR_DROP":
        if scope != "row":
            return None
        first = keys[0]
        ast = parse_formula(original[first])
        absr = [n for n in _nodes(ast, Ref) if n.ref.col_abs]
        if not absr:
            return None
        n = rng.choice(absr)
        ast0 = _replace(ast, n, Ref(_ref_with(n.ref, col_abs=False, row_abs=False)))
        for k in keys:
            cells[k] = to_formula(translate(ast0, 0, k[2] - first[2]))
        desc = f"missing $ on {n.ref.a1()}, then filled right"
    else:
        fn = AST_OPS[op]
        if scope == "row":
            # derive the change once on the first cell, then fill right
            first = keys[0]
            res = fn(parse_formula(original[first]), ctx, sheet, random.Random(rng.random()))
            if res is None:
                return None
            ast0, desc = res
            for k in keys:
                cells[k] = to_formula(translate(ast0, 0, k[2] - first[2]))
        else:
            k = keys[0]
            res = fn(parse_formula(original[k]), ctx, sheet, rng)
            if res is None:
                return None
            ast1, desc = res
            cells[k] = to_formula(ast1)
    if all(_same(cells[k], original[k]) for k in cells):
        return None
    return Mutation(op, scope, lid, cells, original, description=desc,
                    category=OPERATORS[op]["category"])


def _same(a, b) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return a.replace(" ", "").upper() == b.replace(" ", "").upper()
    return a == b


def classify(mut: Mutation, reference: Workbook, targets: Sequence[Key],
             scenarios: Sequence[Dict[Key, float]], ref_runs: Sequence[Dict[Key, object]]) -> str:
    wb = reference.copy()
    for k, v in mut.cells.items():
        wb.set_rc(wb.sheet_name(k[0]), k[1], k[2], v)
    cw = wb.compile()
    if cw.problems() or (cw.cyclic and not reference.iterative):
        return "invalid"
    base = cw.run()
    for k in targets:
        if isinstance(base.get(k), ExcelError):
            return "invalid"
    if any(not close(base.get(k), ref_runs[0].get(k)) for k in targets):
        return "visible"
    for sc, rr in zip(scenarios, ref_runs[1:]):
        run = cw.run(sc)
        if any(not close(run.get(k), rr.get(k)) for k in targets):
            return "latent"
    return "equivalent"


def sample_bugs(reference: Workbook, spec: ModelSpec, lay: Layout, targets: Sequence[Key],
                scenarios: Sequence[Dict[Key, float]], rng: random.Random, n_bugs: int,
                min_latent: int = 0, row_scope_p: float = 0.35, max_tries: int = 400) -> List[Mutation]:
    """Draw ``n_bugs`` effective, non-overlapping bugs (at least ``min_latent`` latent)."""
    cw = reference.compile()
    ref_runs = [cw.run()] + [cw.run(sc) for sc in scenarios]
    base = ref_runs[0]
    lines = [ln.id for ln in spec.lines if ln.fc is not None and ln.kind != "check"]
    ops = list(OPERATORS)
    weights = [OPERATORS[o]["weight"] for o in ops]
    chosen: List[Mutation] = []
    used_lines = set()
    tries = 0
    while len(chosen) < n_bugs and tries < max_tries:
        tries += 1
        n_latent = sum(m.effect == "latent" for m in chosen)
        need_latent = n_latent < min_latent
        must_be_latent = need_latent and (n_bugs - len(chosen)) <= (min_latent - n_latent)
        if need_latent and rng.random() < 0.85:
            op = rng.choices(list(LATENT_MIX), list(LATENT_MIX.values()))[0]
        else:
            op = rng.choices(ops, weights)[0]
        scope = "row" if (rng.random() < row_scope_p or op == "ANCHOR_DROP") else "cell"
        # Try this operator on every free line (random order) until one sticks.
        # Operators that need a specific construct (a MAX, a range ...) would
        # otherwise rarely be placed, skewing the bug mix toward pastes.
        free = [x for x in lines if x not in used_lines] or lines
        rng.shuffle(free)
        for lid in free:
            mut = propose(op, scope, lid, reference, spec, lay, base, rng)
            if mut is None:
                continue
            mut.effect = classify(mut, reference, targets, scenarios, ref_runs)
            if mut.effect in ("invalid", "equivalent"):
                continue
            if must_be_latent and mut.effect != "latent":
                continue
            chosen.append(mut)
            used_lines.add(lid)
            break
    return chosen


# Latent bugs are drawn from a fixed mix so that stale pastes (the easiest to
# spot: a typed number in a formula row) do not dominate.
LATENT_MIX = {"HARDCODE_PASTE": 0.30, "JAMMED_CONSTANT": 0.25, "FLOOR_REMOVAL": 0.25,
              "COINCIDENT_REF": 0.20}


def apply_bugs(reference: Workbook, bugs: Sequence[Mutation]) -> Workbook:
    wb = reference.copy()
    for m in bugs:
        for k, v in m.cells.items():
            wb.set_rc(wb.sheet_name(k[0]), k[1], k[2], v)
    return wb
