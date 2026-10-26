"""One episode: a task, the agent's working copy of the workbook, and the tools.

The same ``Session`` backs every interface (OpenEnv MCP server, the TRL
``environment_factory`` adapter, the single-turn patch mode and the
evaluation scripts), so tool behaviour and grading are identical everywhere.
Tool methods return plain text for the model and never raise for agent
mistakes; errors are reported in the text.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .engine.functions import FORBIDDEN_FUNCTIONS, FUNCTIONS
from .engine.parser import Call, FormulaSyntaxError, parse_formula, translate, to_formula, walk
from .engine.refs import ExcelError, addr, index_to_col, parse_cell, parse_range
from .engine.workbook import CompiledWorkbook, Key, Workbook
from .grader.grader import Grader, GradeResult, cell_budget
from .task import Task

MAX_READ_CELLS = 600
MAX_COPY_CELLS = 400


def fmt_value(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        if abs(v) >= 1e6:
            return f"{v:.2f}"
        s = f"{v:.6f}".rstrip("0").rstrip(".")
        return s if s not in ("-0", "") else "0"
    if isinstance(v, ExcelError):
        return v.code
    return str(v)


def parse_content(content) -> Tuple[object, Optional[str]]:
    """Agent input -> raw cell content, or an error message."""
    if content is None:
        return None, None
    if isinstance(content, bool):
        return content, None
    if isinstance(content, (int, float)):
        return float(content), None
    s = str(content).strip()
    if s == "":
        return None, None
    if s.startswith("="):
        try:
            ast = parse_formula(s)
        except FormulaSyntaxError as e:
            return None, f"formula syntax error: {e}"
        for n in walk(ast):
            if isinstance(n, Call):
                if n.name in FORBIDDEN_FUNCTIONS:
                    return None, f"function {n.name} is not allowed in this workbook"
                if n.name not in FUNCTIONS:
                    return None, f"unsupported function {n.name}"
        return to_formula(ast), None
    try:
        return float(s.replace(",", "")), None
    except ValueError:
        pass
    if s.upper() in ("TRUE", "FALSE"):
        return s.upper() == "TRUE", None
    return s, None


def r1c1_signature(formula: str, row: int, col: int) -> str:
    """Formula with relative references expressed as offsets (Excel's R1C1 idea):
    two cells share a signature iff one is the other filled/copied."""
    from .engine.parser import map_refs, Ref, Rng
    from .engine.refs import CellRef, RangeRef

    def rel(r: CellRef) -> CellRef:
        return CellRef(r.sheet, r.row if r.row_abs else r.row - row, r.col if r.col_abs else r.col - col,
                       r.row_abs, r.col_abs)

    try:
        ast = parse_formula(formula)
    except FormulaSyntaxError:
        return formula
    norm = map_refs(ast, lambda n: Ref(rel(n.ref)) if isinstance(n, Ref)
                    else Rng(RangeRef(n.ref.sheet, rel(n.ref.start), rel(n.ref.end))))
    return repr(norm)


def compact_rows(wb: Workbook, sheet: str, rows=None, cols=None) -> List[str]:
    """One line per row; runs of filled-right formulas collapse to one entry."""
    out = []
    by_row: Dict[int, List[Tuple[int, object]]] = {}
    for _, r, c, raw in wb.cells(sheet):
        if (rows is None or r in rows) and (cols is None or c in cols):
            by_row.setdefault(r, []).append((c, raw))
    for r in sorted(by_row):
        cells = by_row[r]
        parts = []
        i = 0
        while i < len(cells):
            c, raw = cells[i]
            if isinstance(raw, str) and raw.startswith("="):
                sig = r1c1_signature(raw, r, c)
                j = i
                while (j + 1 < len(cells) and cells[j + 1][0] == cells[j][0] + 1
                       and isinstance(cells[j + 1][1], str) and cells[j + 1][1].startswith("=")
                       and r1c1_signature(cells[j + 1][1], r, cells[j + 1][0]) == sig):
                    j += 1
                if j > i:
                    parts.append(f"{addr(r, c)}:{addr(r, cells[j][0])} {raw} [filled right]")
                else:
                    parts.append(f"{addr(r, c)} {raw}")
                i = j + 1
            else:
                parts.append(f"{addr(r, c)} {fmt_value(raw)}")
                i += 1
        out.append(f"r{r}: " + " | ".join(parts))
    return out


class Session:
    def __init__(self, task: Task, grader: Optional[Grader] = None, max_steps: Optional[int] = None):
        self.task = task
        self.grader = grader or Grader()
        self.wb: Workbook = task.initial.copy()
        self.max_steps = max_steps or task.max_steps
        self.steps = 0
        self.done = False
        self.result: Optional[GradeResult] = None
        self.edits: List[Tuple[str, str, object]] = []
        self.notes: str = ""
        self._cw: Optional[CompiledWorkbook] = None
        self._vals: Optional[Dict[Key, object]] = None

    # ------------------------------------------------------------------
    def _values(self) -> Dict[Key, object]:
        if self._vals is None:
            self._cw = self.wb.compile()
            self._vals = self._cw.run()
        return self._vals

    def _invalidate(self):
        self._cw = None
        self._vals = None

    def _sheet(self, sheet: str) -> str:
        sheet = (sheet or "").strip().strip("'")
        if not self.wb.has_sheet(sheet):
            raise ValueError(f"no sheet named {sheet!r}; sheets are {', '.join(self.wb.sheet_names)}")
        return self.wb.sheet_name(sheet.casefold())

    def _tick(self) -> Optional[str]:
        if self.done:
            return "The episode is over (already submitted)."
        self.steps += 1
        if self.steps > self.max_steps:
            self.submit()
            return f"Step limit ({self.max_steps}) reached; the workbook was submitted automatically.\n" + (
                self.result.summary() if self.result else "")
        return None

    def _split_cell(self, sheet: Optional[str], cell: str) -> Tuple[str, str]:
        cell = (cell or "").strip()
        if "!" in cell:
            sh, cell = cell.rsplit("!", 1)
            sheet = sh
        return self._sheet(sheet), cell.replace("$", "")

    # ------------------------------------------------------------------ tools
    def list_sheets(self) -> str:
        msg = self._tick()
        if msg:
            return msg
        out = []
        for name in self.wb.sheet_names:
            ur = self.wb.used_range(name)
            n_f = sum(1 for _, r, c, raw in self.wb.cells(name) if isinstance(raw, str) and raw.startswith("="))
            if ur:
                r0, c0, r1, c1 = ur
                rng = f"{addr(r0, c0)}:{addr(r1, c1)}"
            else:
                rng = "(empty)"
            out.append(f"{name}: used range {rng}, {n_f} formulas")
        return "\n".join(out)

    def read_range(self, sheet: str, cell_range: str, show: str = "both") -> str:
        msg = self._tick()
        if msg:
            return msg
        try:
            sheet, rng_text = self._split_cell(sheet, cell_range)
            rr = parse_range(rng_text)
        except ValueError as e:
            return f"error: {e}"
        vals = self._values()
        k = sheet.casefold()
        if show == "compact":
            body = compact_rows(self.wb, sheet, set(rr.rows), set(rr.cols))
            return "\n".join([f"[{sheet}] {rr.a1(False)}  (compact: filled-right formula runs collapsed, "
                              "no computed values)"] + (body or ["(all cells empty)"]))
        lines = [f"[{sheet}] {rr.a1(False)}  (formula cells shown as =formula -> value)"]
        n = 0
        truncated = False
        for r in rr.rows:
            parts = []
            for c in rr.cols:
                raw = self.wb.get_rc(sheet, r, c)
                if raw is None:
                    continue
                n += 1
                if n > MAX_READ_CELLS:
                    truncated = True
                    break
                a = addr(r, c)
                if isinstance(raw, str) and raw.startswith("="):
                    v = fmt_value(vals.get((k, r, c)))
                    if show == "values":
                        parts.append(f"{a} {v}")
                    elif show == "formulas":
                        parts.append(f"{a} {raw}")
                    else:
                        parts.append(f"{a} {raw} -> {v}")
                else:
                    parts.append(f"{a} {fmt_value(raw)}")
            if parts:
                lines.append(f"r{r}: " + " | ".join(parts))
            if truncated:
                lines.append(f"... truncated at {MAX_READ_CELLS} cells; read a smaller range")
                break
        if len(lines) == 1:
            lines.append("(all cells empty)")
        return "\n".join(lines)

    def write_cell(self, sheet: str, cell: str, content: str) -> str:
        msg = self._tick()
        if msg:
            return msg
        try:
            sheet, cell = self._split_cell(sheet, cell)
            ref = parse_cell(cell)
        except ValueError as e:
            return f"error: {e}"
        raw, err = parse_content(content)
        if err:
            return f"error: {err} (cell not changed)"
        self.wb.set_rc(sheet, ref.row, ref.col, raw)
        self.edits.append((sheet, cell, raw))
        self._invalidate()
        if raw is None:
            return f"{sheet}!{cell} cleared"
        v = self._values().get((sheet.casefold(), ref.row, ref.col))
        shown = raw if isinstance(raw, str) else fmt_value(raw)
        return f"{sheet}!{cell} = {shown} -> {fmt_value(v)}"

    def write_cells(self, edits: List[Dict[str, str]]) -> str:
        """Batch write: ``[{"cell": "IS!E5", "content": "=D5*1.1"}, ...]`` (one step)."""
        msg = self._tick()
        if msg:
            return msg
        if not isinstance(edits, list) or not edits:
            return "error: edits must be a non-empty list of {cell, content}"
        if len(edits) > MAX_COPY_CELLS:
            return f"error: at most {MAX_COPY_CELLS} edits per call"
        out = []
        changed = []
        for e in edits:
            if not isinstance(e, dict):
                out.append("error: each edit must be an object {cell, content}")
                continue
            try:
                sheet, cell = self._split_cell(e.get("sheet"), str(e.get("cell", "")))
                ref = parse_cell(cell)
            except ValueError as ex:
                out.append(f"error: {ex}")
                continue
            raw, err = parse_content(e.get("content"))
            if err:
                out.append(f"{sheet}!{cell}: error: {err} (not changed)")
                continue
            self.wb.set_rc(sheet, ref.row, ref.col, raw)
            self.edits.append((sheet, cell, raw))
            changed.append((sheet, ref.row, ref.col))
        self._invalidate()
        vals = self._values()
        for sheet, r, c in changed[:40]:
            out.append(f"{sheet}!{addr(r, c)} -> {fmt_value(vals.get((sheet.casefold(), r, c)))}")
        if len(changed) > 40:
            out.append(f"... (+{len(changed) - 40} more)")
        return "\n".join([f"wrote {len(changed)} cell(s)"] + out)

    def copy_cell(self, sheet: str, source: str, target_range: str) -> str:
        """Paste ``source`` into every cell of ``target_range`` with relative references
        adjusted (Excel copy/paste or fill-right semantics)."""
        msg = self._tick()
        if msg:
            return msg
        try:
            sheet, source = self._split_cell(sheet, source)
            sref = parse_cell(source)
            tsheet, trng = self._split_cell(sheet, target_range)
            rr = parse_range(trng)
        except ValueError as e:
            return f"error: {e}"
        if rr.size > MAX_COPY_CELLS:
            return f"error: target range larger than {MAX_COPY_CELLS} cells"
        raw = self.wb.get_rc(sheet, sref.row, sref.col)
        if raw is None:
            return f"error: {sheet}!{source} is empty"
        written = []
        for r in rr.rows:
            for c in rr.cols:
                if isinstance(raw, str) and raw.startswith("="):
                    node = translate(parse_formula(raw), r - sref.row, c - sref.col)
                    new = to_formula(node)
                else:
                    new = raw
                self.wb.set_rc(tsheet, r, c, new)
                self.edits.append((tsheet, addr(r, c), new))
                written.append((r, c, new))
        self._invalidate()
        vals = self._values()
        k = tsheet.casefold()
        shown = [f"{addr(r, c)} {new} -> {fmt_value(vals.get((k, r, c)))}" for r, c, new in written[:12]]
        more = f" ... (+{len(written) - 12} more)" if len(written) > 12 else ""
        return f"pasted into {len(written)} cell(s) on {tsheet}: " + " | ".join(shown) + more

    def trace(self, sheet: str, cell: str) -> str:
        """Direct precedents and dependents of a cell (Excel's formula auditing)."""
        msg = self._tick()
        if msg:
            return msg
        try:
            sheet, cell = self._split_cell(sheet, cell)
            ref = parse_cell(cell)
        except ValueError as e:
            return f"error: {e}"
        vals = self._values()
        cw = self._cw
        key = (sheet.casefold(), ref.row, ref.col)
        raw = self.wb.get_rc(sheet, ref.row, ref.col)
        lab = lambda k: f"{self.wb.sheet_name(k[0])}!{addr(k[1], k[2])}"  # noqa: E731

        def describe(k):
            label = self.wb.get_rc(self.wb.sheet_name(k[0]), k[1], 1)
            return f"{lab(k)} ({label}) = {fmt_value(vals.get(k))}" if isinstance(label, str) else \
                f"{lab(k)} = {fmt_value(vals.get(k))}"

        prec = sorted(cw.precedents(key))
        deps = sorted(cw.dependents_map().get(key, ()))
        lines = [f"{lab(key)}: {raw if raw is not None else '(empty)'} -> {fmt_value(vals.get(key))}"]
        lines.append("precedents: " + ("; ".join(describe(k) for k in prec[:30]) or "none"))
        lines.append("dependents: " + ("; ".join(describe(k) for k in deps[:30]) or "none"))
        return "\n".join(lines)

    def find(self, text: str) -> str:
        """Find cells whose text contains ``text`` (case-insensitive)."""
        msg = self._tick()
        if msg:
            return msg
        q = (text or "").strip().casefold()
        if not q:
            return "error: empty search text"
        hits = []
        for sheet, r, c, raw in self.wb.cells():
            if isinstance(raw, str) and not raw.startswith("=") and q in raw.casefold():
                hits.append(f"{sheet}!{addr(r, c)} {raw}")
        return "\n".join(hits[:40]) or "no matches"

    def submit(self, notes: str = "") -> str:
        if self.done:
            return "Already submitted.\n" + (self.result.summary() if self.result else "")
        self.notes = notes or ""
        self.result = self.grader.grade(self.task, self.wb)
        self.done = True
        return "Submitted.\n" + self.result.summary()

    # ------------------------------------------------------------------ patch mode
    def apply_patch(self, edits: List[Dict[str, str]]) -> List[str]:
        """Apply a list of {sheet, cell, content} edits (single-turn mode)."""
        msgs = []
        written = 0
        budget = cell_budget(self.task)
        for e in edits[:2000]:
            raw, err = parse_content(e.get("content"))
            try:
                sheet, cell = self._split_cell(e.get("sheet"), e.get("cell", ""))
                rr = parse_range(cell)  # "E5" or "E5:J5" (fill from the top-left cell)
            except ValueError as ex:
                msgs.append(f"error: {ex}")
                continue
            if err:
                msgs.append(f"{sheet}!{cell}: {err}")
                continue
            if rr.size > MAX_COPY_CELLS:
                msgs.append(f"{sheet}!{cell}: range too large (at most {MAX_COPY_CELLS} cells per edit)")
                continue
            if written + rr.size > budget:
                msgs.append(f"{sheet}!{cell}: cell budget exhausted ({budget} cells per submission)")
                continue
            r0, c0 = rr.rows[0], rr.cols[0]
            for r in rr.rows:
                for c in rr.cols:
                    new = raw
                    if isinstance(raw, str) and raw.startswith("=") and (r, c) != (r0, c0):
                        new = to_formula(translate(parse_formula(raw), r - r0, c - c0))
                    self.wb.set_rc(sheet, r, c, new)
                    self.edits.append((sheet, addr(r, c), new))
                    written += 1
        self._invalidate()
        return msgs

    @property
    def reward(self) -> float:
        return self.result.reward if self.result else 0.0


_EDIT_LINE = re.compile(r"^\s*(?:(?P<sheet>'[^']+'|[A-Za-z_][\w .]*)!)?(?P<cell>\$?[A-Za-z]{1,3}\$?\d+(?::\$?[A-Za-z]{1,3}\$?\d+)?)\s*(?::=|=>)\s*(?P<content>.*?)\s*$")


def parse_patch_text(text: str, default_sheet: Optional[str] = None) -> List[Dict[str, str]]:
    """Parse single-turn answers of the form ``Sheet!E5 := =D5*(1+Assumptions!E18)``.

    Only lines inside the last fenced block are used when a fence is present.
    """
    blocks = re.findall(r"```[a-zA-Z]*\n(.*?)```", text, flags=re.S)
    body = blocks[-1] if blocks else text
    edits = []
    for line in body.splitlines():
        m = _EDIT_LINE.match(line)
        if not m:
            continue
        sheet = (m.group("sheet") or default_sheet or "").strip("'")
        edits.append({"sheet": sheet, "cell": m.group("cell"), "content": m.group("content")})
    return edits
