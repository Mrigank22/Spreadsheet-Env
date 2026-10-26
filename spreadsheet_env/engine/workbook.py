"""Workbook model, formula compilation and recalculation.

``Workbook`` holds raw cell contents (constants or ``=formula`` strings).
``Workbook.compile()`` returns a ``CompiledWorkbook``: every formula parsed
and compiled to a Python closure, a dependency graph, and an evaluation order.
``CompiledWorkbook.run(overrides)`` recalculates the whole model with some
constant cells replaced, which is what the grader does many times per
submission (perturbation scenarios). Compilation happens once, so a scenario
costs one pass over the formula cells.

Circular references: by default every cell on a cycle evaluates to
``#CIRC!``. With ``iterative=True`` (Excel's "enable iterative calculation")
each strongly connected component is solved by Gauss-Seidel iteration to a
tight tolerance, so two workbooks with the same fixed point agree regardless
of evaluation order.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from . import functions as F
from .functions import Arr
from .parser import (
    Binary, Bool, Call, Err, FormulaSyntaxError, Node, Num, Percent, Ref, Rng,
    Str, Unary, parse_formula, walk,
)
from .refs import CIRC, NAME, REF, VALUE, ExcelError, addr, parse_cell

Key = Tuple[str, int, int]  # (sheet key = casefolded name, row, col)
Value = object

MAX_RANGE_CELLS = 20_000


def _is_formula(raw) -> bool:
    return isinstance(raw, str) and raw.startswith("=") and len(raw) > 1


def normalise_constant(raw):
    """Constants are stored as float/str/bool. Ints become floats."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return float(raw)
    if isinstance(raw, float):
        return raw + 0.0
    return raw


class Workbook:
    """An ordered set of sheets, each a sparse map (row, col) -> raw content."""

    def __init__(self, iterative: bool = False):
        self._sheets: Dict[str, Dict[Tuple[int, int], object]] = {}
        self._names: Dict[str, str] = {}  # key -> display name
        self.iterative = iterative

    # -- sheets ------------------------------------------------------------
    def add_sheet(self, name: str) -> None:
        k = name.casefold()
        if k in self._sheets:
            raise ValueError(f"sheet {name!r} already exists")
        self._sheets[k] = {}
        self._names[k] = name

    @property
    def sheet_names(self) -> List[str]:
        return [self._names[k] for k in self._sheets]

    def has_sheet(self, name: str) -> bool:
        return name.casefold() in self._sheets

    def sheet_name(self, key: str) -> str:
        return self._names[key]

    def _sheet(self, name: str) -> Dict[Tuple[int, int], object]:
        try:
            return self._sheets[name.casefold()]
        except KeyError:
            raise KeyError(f"no sheet named {name!r}") from None

    # -- cells -------------------------------------------------------------
    def set(self, sheet: str, cell: str, raw) -> None:
        """Set a cell. ``raw`` is a number, text, bool, ``=formula`` or None (clear)."""
        ref = parse_cell(cell)
        self.set_rc(sheet, ref.row, ref.col, raw)

    def set_rc(self, sheet: str, row: int, col: int, raw) -> None:
        cells = self._sheet(sheet)
        if raw is None or (isinstance(raw, str) and raw == ""):
            cells.pop((row, col), None)
        else:
            cells[(row, col)] = normalise_constant(raw)

    def get(self, sheet: str, cell: str):
        ref = parse_cell(cell)
        return self._sheet(sheet).get((ref.row, ref.col))

    def get_rc(self, sheet: str, row: int, col: int):
        return self._sheet(sheet).get((row, col))

    def raw(self, key: Key):
        """Raw content at an engine key (None if blank or the sheet is missing)."""
        return self._sheets.get(key[0], {}).get((key[1], key[2]))

    def cells(self, sheet: Optional[str] = None) -> Iterable[Tuple[str, int, int, object]]:
        """Yield (sheet display name, row, col, raw) in sheet/row/col order."""
        keys = [sheet.casefold()] if sheet else list(self._sheets)
        for k in keys:
            for (r, c), raw in sorted(self._sheets[k].items()):
                yield self._names[k], r, c, raw

    def used_range(self, sheet: str) -> Optional[Tuple[int, int, int, int]]:
        cells = self._sheet(sheet)
        if not cells:
            return None
        rows = [r for r, _ in cells]
        cols = [c for _, c in cells]
        return min(rows), min(cols), max(rows), max(cols)

    def is_formula(self, sheet: str, row: int, col: int) -> bool:
        return _is_formula(self.get_rc(sheet, row, col))

    def copy(self) -> "Workbook":
        wb = Workbook(self.iterative)
        wb._sheets = {k: dict(v) for k, v in self._sheets.items()}
        wb._names = dict(self._names)
        return wb

    def snapshot(self) -> Dict[Key, object]:
        return {(k, r, c): raw for k, cells in self._sheets.items() for (r, c), raw in cells.items()}

    def compile(self, instrument: bool = False) -> "CompiledWorkbook":
        return CompiledWorkbook(self, instrument=instrument)

    def calculate(self, overrides: Optional[Dict[Key, object]] = None) -> Dict[Key, Value]:
        return self.compile().run(overrides)


# --------------------------------------------------------------------------
# Compilation
# --------------------------------------------------------------------------

@dataclass
class CompiledCell:
    key: Key
    formula: str
    ast: Optional[Node]
    fn: Callable[[dict], Value]
    deps: Set[Key] = field(default_factory=set)
    error: str = ""  # parse / compile problem, if any


class CompiledWorkbook:
    def __init__(self, wb: Workbook, instrument: bool = False):
        self.wb = wb
        self.iterative = wb.iterative
        # Branch instrumentation (used on reference models only): every IF /
        # IFERROR / MAX / MIN records which arm it took, so scenario selection
        # can aim for branch coverage.
        self.instrument = instrument
        self.trace: Set[Tuple[Key, int, object]] = set()
        self._branch_ids = 0
        self._cur: Optional[Key] = None
        self.constants: Dict[Key, Value] = {}
        self.cells: Dict[Key, CompiledCell] = {}
        for k, cells in wb._sheets.items():
            for (r, c), raw in cells.items():
                key = (k, r, c)
                if _is_formula(raw):
                    self.cells[key] = self._compile_cell(key, raw)
                else:
                    self.constants[key] = raw
        self.order: List[List[Key]] = self._order()
        self.cyclic: Set[Key] = {k for comp in self.order if self._is_cycle(comp) for k in comp}

    # -- compile a single formula -------------------------------------------
    def _compile_cell(self, key: Key, formula: str) -> CompiledCell:
        try:
            ast = parse_formula(formula)
        except FormulaSyntaxError as e:
            return CompiledCell(key, formula, None, lambda v: NAME, set(), f"syntax: {e}")
        deps: Set[Key] = set()
        problems: List[str] = []
        self._cur = key
        fn = self._compile(ast, key[0], deps, problems, array=False)
        return CompiledCell(key, formula, ast, fn, deps, "; ".join(problems))

    def _sheet_key(self, sheet: Optional[str], home: str) -> Optional[str]:
        if sheet is None:
            return home
        k = sheet.casefold()
        return k if k in self.wb._sheets else None

    def _compile(self, node: Node, home: str, deps: Set[Key], problems: List[str],
                 array: bool, as_range: bool = False):
        c = self._compile
        if isinstance(node, Num):
            v = node.value
            return lambda vals: v
        if isinstance(node, Str):
            v = node.value
            return lambda vals: v
        if isinstance(node, Bool):
            v = node.value
            return lambda vals: v
        if isinstance(node, Err):
            v = node.value
            return lambda vals: v
        if isinstance(node, Ref):
            sk = self._sheet_key(node.ref.sheet, home)
            if sk is None:
                problems.append(f"unknown sheet {node.ref.sheet!r}")
                return lambda vals: REF
            key = (sk, node.ref.row, node.ref.col)
            deps.add(key)
            if as_range:
                return lambda vals: Arr([[vals.get(key)]])
            return lambda vals: vals.get(key)
        if isinstance(node, Rng):
            sk = self._sheet_key(node.ref.sheet, home)
            if sk is None:
                problems.append(f"unknown sheet {node.ref.sheet!r}")
                return lambda vals: REF
            if node.ref.size > MAX_RANGE_CELLS:
                problems.append("range too large")
                return lambda vals: REF
            grid = [[(sk, r, cc) for cc in node.ref.cols] for r in node.ref.rows]
            for row in grid:
                deps.update(row)
            if as_range or array:
                return lambda vals: Arr([[vals.get(k) for k in row] for row in grid])
            # A multi-cell range where one value is expected: Excel's implicit
            # intersection / dynamic-array spill differ between apps, so the
            # portable subset rejects it.
            if node.ref.size == 1:
                k0 = grid[0][0]
                return lambda vals: vals.get(k0)
            return lambda vals: VALUE
        if isinstance(node, Unary):
            f = c(node.operand, home, deps, problems, array)
            if node.op == "-":
                def neg(vals):
                    x = f(vals)
                    if array and isinstance(x, Arr):
                        return _amap(x, lambda e: _neg(e))
                    return _neg(x)
                return neg
            def pos(vals):
                return f(vals)
            return pos
        if isinstance(node, Percent):
            f = c(node.operand, home, deps, problems, array)
            def pct(vals):
                x = f(vals)
                if array and isinstance(x, Arr):
                    return _amap(x, lambda e: F.arith("/", e, 100.0))
                return F.arith("/", x, 100.0)
            return pct
        if isinstance(node, Binary):
            fl = c(node.left, home, deps, problems, array)
            fr = c(node.right, home, deps, problems, array)
            op = node.op
            if op in ("+", "-", "*", "/", "^"):
                scalar = lambda a, b: F.arith(op, a, b)
            elif op == "&":
                scalar = F.concat
            else:
                scalar = lambda a, b: F.compare(op, a, b)

            def binop(vals):
                a = fl(vals)
                b = fr(vals)
                if isinstance(a, Arr) or isinstance(b, Arr):
                    if not array:
                        return VALUE
                    return _abroadcast(a, b, scalar)
                if isinstance(a, ExcelError):
                    return a
                if isinstance(b, ExcelError):
                    return b
                return scalar(a, b)
            return binop
        if isinstance(node, Call):
            return self._compile_call(node, home, deps, problems, array)
        raise TypeError(node)

    def _compile_call(self, node: Call, home, deps, problems, array):
        name = node.name
        if name in F.FORBIDDEN_FUNCTIONS:
            problems.append(f"forbidden function {name}")
            return lambda vals: NAME
        spec = F.FUNCTIONS.get(name)
        if spec is None:
            problems.append(f"unsupported function {name}")
            return lambda vals: NAME
        impl, lo, hi, _ = spec
        n = len(node.args)
        if not (lo <= n <= hi):
            problems.append(f"{name} takes {lo}..{hi} arguments, got {n}")
            return lambda vals: VALUE
        sub_array = array or name == "SUMPRODUCT"
        args = [
            self._compile(a, home, deps, problems, sub_array, as_range=F.is_range_arg(name, i))
            for i, a in enumerate(node.args)
        ]
        record = None
        if self.instrument and name in ("IF", "IFERROR", "MAX", "MIN"):
            self._branch_ids += 1
            tag = (self._cur, self._branch_ids)
            trace = self.trace
            record = lambda arm: trace.add((tag[0], tag[1], arm))  # noqa: E731
        if name == "IF":
            cond = args[0]
            then = args[1]
            other = args[2] if n == 3 else (lambda vals: False)

            def _if(vals):
                b = F.to_bool(cond(vals))
                if isinstance(b, ExcelError):
                    return b
                if record:
                    record(bool(b))
                return then(vals) if b else other(vals)
            return _if
        if name == "IFERROR":
            first, alt = args

            def _iferror(vals):
                v = first(vals)
                if record:
                    record(isinstance(v, ExcelError))
                return alt(vals) if isinstance(v, ExcelError) else v
            return _iferror

        def call(vals):
            vs = [a(vals) for a in args]
            for i, v in enumerate(vs):
                if isinstance(v, Arr) and not F.is_range_arg(name, i):
                    return VALUE
            try:
                out = impl(*vs)
            except (ArithmeticError, ValueError, TypeError):
                return F.NUM
            if record and isinstance(out, float):
                # which argument "won" (first one equal to the result), and whether it
                # won with a non-zero value: an arm that only ever wins at 0 (e.g. the
                # debt side of MIN(repayment, debt) once debt is fully repaid) is a
                # degenerate cover that misses bugs in that argument
                flat = [x for v in vs for x in (v.flat() if isinstance(v, Arr) else [v])]
                won = next((i for i, x in enumerate(flat) if x == out), -1)
                record((won, out != 0.0))
            return _blank_to_zero(out)
        return call

    # -- ordering ------------------------------------------------------------
    def _order(self) -> List[List[Key]]:
        """Strongly connected components of the formula graph, in dependency order."""
        graph = {k: [d for d in cc.deps if d in self.cells] for k, cc in self.cells.items()}
        index: Dict[Key, int] = {}
        low: Dict[Key, int] = {}
        on_stack: Set[Key] = set()
        stack: List[Key] = []
        comps: List[List[Key]] = []
        counter = [0]

        for root in sorted(graph):
            if root in index:
                continue
            # iterative Tarjan
            work = [(root, iter(sorted(graph[root])))]
            index[root] = low[root] = counter[0]
            counter[0] += 1
            stack.append(root)
            on_stack.add(root)
            while work:
                v, it = work[-1]
                advanced = False
                for w in it:
                    if w not in index:
                        index[w] = low[w] = counter[0]
                        counter[0] += 1
                        stack.append(w)
                        on_stack.add(w)
                        work.append((w, iter(sorted(graph[w]))))
                        advanced = True
                        break
                    elif w in on_stack:
                        low[v] = min(low[v], index[w])
                if advanced:
                    continue
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[v])
                if low[v] == index[v]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on_stack.discard(w)
                        comp.append(w)
                        if w == v:
                            break
                    comps.append(sorted(comp))
        return comps  # Tarjan emits components in reverse topological order of the reversed graph = dependency order

    def _is_cycle(self, comp: List[Key]) -> bool:
        if len(comp) > 1:
            return True
        k = comp[0]
        return k in self.cells[k].deps

    # -- evaluation ------------------------------------------------------------
    def run(self, overrides: Optional[Dict[Key, object]] = None,
            max_iter: int = 5000, tol: float = 1e-14) -> Dict[Key, Value]:
        self.iterations_used = 0
        vals: Dict[Key, Value] = dict(self.constants)
        if overrides:
            for k, v in overrides.items():
                vals[k] = normalise_constant(v)
        cells = self.cells
        for comp in self.order:
            if len(comp) == 1 and comp[0] not in self.cyclic:
                k = comp[0]
                if overrides and k in overrides:
                    continue
                vals[k] = _finalise(cells[k].fn(vals))
                continue
            # a cycle
            if not self.iterative:
                for k in comp:
                    vals[k] = CIRC
                continue
            start = {k: (vals.get(k) if isinstance(vals.get(k), float) else 0.0) for k in comp}
            converged = False
            # Plain Gauss-Seidel first; if it does not converge, retry with
            # under-relaxation, which converges for more equation orderings
            # (so the result does not depend on how the agent wrote the cycle).
            for omega in (1.0, 0.5, 0.25):
                for k in comp:
                    vals[k] = start[k]
                for it in range(max_iter):
                    delta = 0.0
                    for k in comp:
                        new = _finalise(cells[k].fn(vals))
                        old = vals.get(k)
                        if isinstance(new, float) and isinstance(old, float):
                            if omega != 1.0:
                                new = old + omega * (new - old)
                            delta = max(delta, abs(new - old) / max(1.0, abs(new)))
                        elif new != old:
                            delta = float("inf")
                        vals[k] = new
                    if delta <= tol:
                        converged = True
                        break
                self.iterations_used = max(self.iterations_used, it + 1 + (0 if omega == 1.0 else max_iter))
                if converged:
                    break
            if not converged:
                for k in comp:
                    vals[k] = CIRC
        return vals

    # -- introspection -----------------------------------------------------------
    def precedents(self, key: Key) -> Set[Key]:
        cc = self.cells.get(key)
        return set(cc.deps) if cc else set()

    def closures(self) -> Dict[Key, frozenset]:
        """Transitive precedents of every formula cell (constants included),
        computed once per strongly connected component in dependency order."""
        if getattr(self, "_closures", None) is not None:
            return self._closures
        out: Dict[Key, frozenset] = {}
        for comp in self.order:
            acc: Set[Key] = set()
            for k in comp:
                for d in self.cells[k].deps:
                    acc.add(d)
                    if d in out:
                        acc |= out[d]
            fs = frozenset(acc)
            for k in comp:
                out[k] = fs
        self._closures = out
        return out

    def transitive_precedents(self, key: Key) -> Set[Key]:
        seen: Set[Key] = set()
        todo = [key]
        while todo:
            k = todo.pop()
            for d in self.precedents(k):
                if d not in seen:
                    seen.add(d)
                    todo.append(d)
        return seen

    def dependents_map(self) -> Dict[Key, Set[Key]]:
        out: Dict[Key, Set[Key]] = {}
        for k, cc in self.cells.items():
            for d in cc.deps:
                out.setdefault(d, set()).add(k)
        return out

    def functions_used(self, key: Key) -> Set[str]:
        cc = self.cells.get(key)
        if not cc or cc.ast is None:
            return set()
        return {n.name for n in walk(cc.ast) if isinstance(n, Call)}

    def problems(self) -> Dict[Key, str]:
        return {k: cc.error for k, cc in self.cells.items() if cc.error}


def _neg(x):
    y = F.to_number(x)
    if isinstance(y, ExcelError):
        return y
    return -y + 0.0


def _amap(a: Arr, fn) -> Arr:
    return Arr([[fn(v) for v in row] for row in a.rows])


def _abroadcast(a, b, fn):
    if isinstance(a, Arr) and isinstance(b, Arr):
        if a.shape != b.shape:
            return VALUE
        return Arr([[fn(x, y) for x, y in zip(ra, rb)] for ra, rb in zip(a.rows, b.rows)])
    if isinstance(a, Arr):
        return Arr([[fn(x, b) for x in row] for row in a.rows])
    return Arr([[fn(a, y) for y in row] for row in b.rows])


def _blank_to_zero(v):
    return 0.0 if v is None else v


def _finalise(v):
    """A formula cell's final value: blanks read as 0, arrays are not allowed."""
    if v is None:
        return 0.0
    if isinstance(v, Arr):
        return VALUE
    if isinstance(v, int) and not isinstance(v, bool):
        return float(v)
    return v


def key_of(wb: Workbook, sheet: str, cell: str) -> Key:
    ref = parse_cell(cell)
    if not wb.has_sheet(sheet):
        raise KeyError(f"no sheet named {sheet!r}")
    return (sheet.casefold(), ref.row, ref.col)


def key_label(wb: Workbook, key: Key) -> str:
    return f"{wb.sheet_name(key[0])}!{addr(key[1], key[2])}"
