"""Declarative financial-model specification and its rendering to a workbook.

A ``ModelSpec`` is the single source of truth for a generated task. From it
we derive:

* the reference workbook (Excel formulas, FAST-style: one formula per row,
  consistent across forecast columns, same period columns on every sheet);
* the layout (line item id -> sheet/row; period -> column), which tells the
  grader where inputs, outputs and invariants live;
* the natural-language specification shown to the agent.

Formula templates use placeholders::

    {rev}        the same period of line ``rev``
    {rev[-1]}    the previous period
    {$tax_rate}  a scalar assumption (rendered as an absolute reference)
    {a:b}        the same-period column range from line ``a`` to line ``b``
                 (both on one sheet, e.g. ``SUM({cf_ni:cf_ap})``)
    {x@last}     line ``x`` in the last period (absolute reference)
    {x@fc}       line ``x`` across all forecast periods (absolute row range)
    {x@all}      line ``x`` across every period, history included (absolute row range)
    {x@3}        line ``x`` in period index 3 (absolute)
    {x[-11..0]}  line ``x`` over the 12 periods ending this one (relative column range)
    {ev}         a single-cell calculation (``Calc``), absolute reference

Example: ``"{rev[-1]}*(1+{g_rev})"`` renders in column F of sheet IS as
``=E5*(1+Assumptions!F8)``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..engine.refs import index_to_col, quote_sheet
from ..engine.workbook import Key, Workbook

LABEL_COL = 1
UNIT_COL = 2
FIRST_PERIOD_COL = 3
SCALAR_VALUE_COL = 3
HEADER_ROW = 2
FIRST_ITEM_ROW = 4

_PH = re.compile(r"\{(\$?)([a-z_][a-z0-9_]*)(?:\[(-?\d+)(?:\.\.(-?\d+))?\])?(?::([a-z_][a-z0-9_]*))?(?:@(last|fc|all|\d+))?\}")


@dataclass
class Scalar:
    id: str
    label: str
    value: float
    unit: str = ""
    kind: str = "rate"  # rate | days | money | ratio | count
    desc: str = ""
    sheet: str = "Assumptions"


@dataclass
class Line:
    """A row with one value per period."""

    id: str
    label: str
    sheet: str
    unit: str = "$m"
    # forecast-period template (None: input series given in ``forecast``)
    fc: Optional[str] = None
    # first-forecast-period template, when it differs (rare; FAST discourages it)
    fc_first: Optional[str] = None
    # last-forecast-period template, when it differs (e.g. a look-ahead such as
    # "next year's debt service" that has no next year in the final column)
    fc_last: Optional[str] = None
    # historical periods: "input" (actuals given), "formula" (use ``hist_fc`` or
    # ``fc``), or "blank"
    hist: str = "input"
    hist_fc: Optional[str] = None
    history: Optional[List[float]] = None
    forecast: Optional[List[float]] = None  # values when this is an input series
    kind: str = "money"  # money | rate | days | ratio | check
    desc: str = ""
    section: str = ""  # a section header printed above this row, if any
    total: bool = False  # styling hint only

    @property
    def is_input_series(self) -> bool:
        return self.fc is None


@dataclass
class Calc:
    """A single-cell calculation (e.g. enterprise value)."""

    id: str
    label: str
    sheet: str
    tpl: str
    unit: str = "$m"
    kind: str = "money"
    desc: str = ""
    section: str = ""


@dataclass
class Layout:
    """Where everything was placed by ``render``."""

    sheets: List[str]
    periods: List[str]
    n_hist: int
    rows: Dict[str, Tuple[str, int]] = field(default_factory=dict)  # line id -> (sheet, row)
    scalars: Dict[str, Tuple[str, int, int]] = field(default_factory=dict)  # id -> (sheet,row,col)
    calcs: Dict[str, Tuple[str, int, int]] = field(default_factory=dict)  # id -> (sheet,row,col)

    @property
    def n_periods(self) -> int:
        return len(self.periods)

    def col(self, period_index: int) -> int:
        return FIRST_PERIOD_COL + period_index

    @property
    def forecast_indices(self) -> range:
        return range(self.n_hist, self.n_periods)

    @property
    def hist_indices(self) -> range:
        return range(0, self.n_hist)

    def key(self, line_id: str, period_index: int) -> Key:
        sheet, row = self.rows[line_id]
        return (sheet.casefold(), row, self.col(period_index))

    def scalar_key(self, sid: str) -> Key:
        sheet, row, col = self.scalars[sid]
        return (sheet.casefold(), row, col)

    def a1(self, line_id: str, period_index: int, absolute: bool = False) -> str:
        sheet, row = self.rows[line_id]
        c = index_to_col(self.col(period_index))
        return f"{quote_sheet(sheet)}!{'$' if absolute else ''}{c}{'$' if absolute else ''}{row}"

    def calc_key(self, cid: str) -> Key:
        sheet, row, col = self.calcs[cid]
        return (sheet.casefold(), row, col)

    def scalar_a1(self, sid: str) -> str:
        sheet, row, col = self.scalars[sid]
        return f"{quote_sheet(sheet)}!${index_to_col(col)}${row}"

    def row_label(self, line_id: str) -> str:
        sheet, row = self.rows[line_id]
        return f"{sheet} row {row}"


@dataclass
class ModelSpec:
    title: str
    periods: List[str]
    n_hist: int
    sheets: List[str]
    scalars: List[Scalar] = field(default_factory=list)
    lines: List[Line] = field(default_factory=list)
    calcs: List[Calc] = field(default_factory=list)
    iterative: bool = False
    currency: str = "$m"

    def scalar(self, sid: str) -> Scalar:
        for s in self.scalars:
            if s.id == sid:
                return s
        raise KeyError(sid)

    def line(self, lid: str) -> Line:
        for ln in self.lines:
            if ln.id == lid:
                return ln
        raise KeyError(lid)

    def ids(self) -> List[str]:
        return [s.id for s in self.scalars] + [ln.id for ln in self.lines]


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render_template(tpl: str, spec_layout: Layout, home_sheet: str, period: Optional[int],
                    scalar_ids: Sequence[str]) -> str:
    """Render one template for one period column into an Excel formula."""

    def sub(m):
        absolute, ident, off, off2, end, at = (m.group(1), m.group(2), m.group(3), m.group(4), m.group(5),
                                               m.group(6))
        if off2 is not None:  # relative column range {x[a..b]}: periods p+a .. p+b of line x
            if ident not in spec_layout.rows or period is None:
                raise KeyError(f"bad column range {m.group(0)!r} in {tpl!r}")
            sheet, row = spec_layout.rows[ident]
            p0, p1 = period + int(off), period + int(off2)
            if not (0 <= p0 <= p1 < spec_layout.n_periods):
                raise ValueError(f"{tpl!r}: column range out of range in period {period}")
            ref = f"{index_to_col(spec_layout.col(p0))}{row}:{index_to_col(spec_layout.col(p1))}{row}"
            return ref if sheet.casefold() == home_sheet.casefold() else f"{quote_sheet(sheet)}!{ref}"
        if at is not None:
            if ident not in spec_layout.rows:
                raise KeyError(f"unknown line {ident!r} in {tpl!r}")
            sheet, row = spec_layout.rows[ident]
            if at in ("fc", "all"):
                c0 = index_to_col(spec_layout.col(spec_layout.n_hist if at == "fc" else 0))
                c1 = index_to_col(spec_layout.col(spec_layout.n_periods - 1))
                ref = f"${c0}${row}:${c1}${row}"
            else:
                p = spec_layout.n_periods - 1 if at == "last" else int(at)
                ref = f"${index_to_col(spec_layout.col(p))}${row}"
        elif end:
            (s1, r1), (s2, r2) = spec_layout.rows[ident], spec_layout.rows[end]
            if s1 != s2:
                raise ValueError(f"range {ident}:{end} spans sheets")
            c = index_to_col(spec_layout.col(period + (int(off) if off else 0)))
            ref = f"{c}{min(r1, r2)}:{c}{max(r1, r2)}"
            return ref if s1.casefold() == home_sheet.casefold() else f"{quote_sheet(s1)}!{ref}"
        elif ident in spec_layout.calcs:
            sheet, row, col = spec_layout.calcs[ident]
            ref = f"${index_to_col(col)}${row}"
        elif absolute or ident in scalar_ids:
            if ident not in spec_layout.scalars:
                raise KeyError(f"unknown scalar {ident!r} in {tpl!r}")
            sheet, row, col = spec_layout.scalars[ident]
            ref = f"${index_to_col(col)}${row}"
        else:
            if ident not in spec_layout.rows:
                raise KeyError(f"unknown line {ident!r} in {tpl!r}")
            if period is None:
                raise ValueError(f"{tpl!r}: a single-cell calc must use @last/@fc/@all/@N for lines")
            sheet, row = spec_layout.rows[ident]
            p = period + (int(off) if off else 0)
            if not 0 <= p < spec_layout.n_periods:
                raise ValueError(f"{tpl!r}: period offset out of range in period {period}")
            ref = f"{index_to_col(spec_layout.col(p))}{row}"
        if sheet.casefold() != home_sheet.casefold():
            ref = f"{quote_sheet(sheet)}!{ref}"
        return ref

    return "=" + _PH.sub(sub, tpl)


def template_refs(tpl: str) -> List[Tuple[str, int, bool]]:
    """(id, offset, is_scalar_syntax) for every placeholder in a template
    (a range placeholder contributes both of its end lines)."""
    out = []
    for m in _PH.finditer(tpl):  # noqa: B007
        out.append((m.group(2), int(m.group(3) or 0), bool(m.group(1))))
        if m.group(5):
            out.append((m.group(5), int(m.group(3) or 0), False))
    return out


def layout_spec(spec: ModelSpec) -> Layout:
    lay = Layout(sheets=list(spec.sheets), periods=list(spec.periods), n_hist=spec.n_hist)
    next_row = {s: FIRST_ITEM_ROW for s in spec.sheets}
    # scalars first (top of their sheet), then lines in declaration order
    for s in spec.scalars:
        r = next_row[s.sheet]
        lay.scalars[s.id] = (s.sheet, r, SCALAR_VALUE_COL)
        next_row[s.sheet] = r + 1
    seen_sections: Dict[str, str] = {}
    for s in spec.sheets:
        if any(sc.sheet == s for sc in spec.scalars) and any(ln.sheet == s for ln in spec.lines):
            next_row[s] += 1  # blank row between scalar block and series block
    for ln in spec.lines:
        r = next_row[ln.sheet]
        if ln.section and seen_sections.get(ln.sheet) != ln.section:
            if r > FIRST_ITEM_ROW:
                r += 1  # blank spacer
            r += 1  # section header row
            seen_sections[ln.sheet] = ln.section
        lay.rows[ln.id] = (ln.sheet, r)
        next_row[ln.sheet] = r + 1
    for c in spec.calcs:
        r = next_row[c.sheet]
        if c.section and seen_sections.get(c.sheet) != c.section:
            if r > FIRST_ITEM_ROW:
                r += 1
            r += 1
            seen_sections[c.sheet] = c.section
        lay.calcs[c.id] = (c.sheet, r, SCALAR_VALUE_COL)
        next_row[c.sheet] = r + 1
    return lay


def render(spec: ModelSpec, lay: Optional[Layout] = None) -> Tuple[Workbook, Layout]:
    """Render the full reference workbook."""
    lay = lay or layout_spec(spec)
    wb = Workbook(iterative=spec.iterative)
    for s in spec.sheets:
        wb.add_sheet(s)
        wb.set_rc(s, 1, 1, f"{spec.title} - {s}")
        wb.set_rc(s, HEADER_ROW, LABEL_COL, "Line item")
        wb.set_rc(s, HEADER_ROW, UNIT_COL, "Unit")
    has_series = {ln.sheet for ln in spec.lines}
    for s in spec.sheets:
        if s in has_series:
            for p, name in enumerate(spec.periods):
                wb.set_rc(s, HEADER_ROW, lay.col(p), name)
    for s in spec.scalars:
        sheet, row, col = lay.scalars[s.id]
        wb.set_rc(sheet, row, LABEL_COL, s.label)
        wb.set_rc(sheet, row, UNIT_COL, s.unit)
        wb.set_rc(sheet, row, col, float(s.value))
    # section headers
    seen: Dict[str, str] = {}
    for ln in spec.lines:
        if ln.section and seen.get(ln.sheet) != ln.section:
            sheet, row = lay.rows[ln.id]
            wb.set_rc(sheet, row - 1, LABEL_COL, ln.section)
            seen[ln.sheet] = ln.section
    scalar_ids = [s.id for s in spec.scalars]
    for ln in spec.lines:
        sheet, row = lay.rows[ln.id]
        wb.set_rc(sheet, row, LABEL_COL, ln.label)
        wb.set_rc(sheet, row, UNIT_COL, ln.unit)
        for p in range(lay.n_periods):
            col = lay.col(p)
            raw = cell_content(spec, lay, ln, p, scalar_ids)
            if raw is not None:
                wb.set_rc(sheet, row, col, raw)
    seen_c: Dict[str, str] = dict(seen)
    for c in spec.calcs:
        sheet, row, col = lay.calcs[c.id]
        if c.section and seen_c.get(c.sheet) != c.section:
            wb.set_rc(sheet, row - 1, LABEL_COL, c.section)
            seen_c[c.sheet] = c.section
        wb.set_rc(sheet, row, LABEL_COL, c.label)
        wb.set_rc(sheet, row, UNIT_COL, c.unit)
        wb.set_rc(sheet, row, col, render_template(c.tpl, lay, sheet, None, scalar_ids))
    return wb, lay


def cell_content(spec: ModelSpec, lay: Layout, ln: Line, p: int, scalar_ids=None):
    """Reference content of line ``ln`` in period ``p`` (formula, number or None)."""
    scalar_ids = scalar_ids if scalar_ids is not None else [s.id for s in spec.scalars]
    if p < spec.n_hist:
        if ln.hist == "input":
            if ln.history is None:
                return None
            return float(ln.history[p])
        if ln.hist == "formula":
            tpl = ln.hist_fc or ln.fc
            return render_template(tpl, lay, ln.sheet, p, scalar_ids)
        return None
    fi = p - spec.n_hist
    if ln.is_input_series:
        return float(ln.forecast[fi]) if ln.forecast is not None else None
    tpl = ln.fc_first if (fi == 0 and ln.fc_first) else ln.fc
    if ln.fc_last and p == lay.n_periods - 1:
        tpl = ln.fc_last
    return render_template(tpl, lay, ln.sheet, p, scalar_ids)


def input_keys(spec: ModelSpec, lay: Layout) -> List[Key]:
    """Every constant numeric input cell of the model (assumptions + actuals)."""
    keys = [lay.scalar_key(s.id) for s in spec.scalars]
    for ln in spec.lines:
        for p in range(lay.n_periods):
            if p < spec.n_hist and ln.hist == "input" and ln.history is not None:
                keys.append(lay.key(ln.id, p))
            elif p >= spec.n_hist and ln.is_input_series and ln.forecast is not None:
                keys.append(lay.key(ln.id, p))
    return keys


def formula_keys(spec: ModelSpec, lay: Layout) -> List[Key]:
    keys = [lay.calc_key(c.id) for c in spec.calcs]
    for ln in spec.lines:
        for p in range(lay.n_periods):
            c = cell_content(spec, lay, ln, p)
            if isinstance(c, str) and c.startswith("="):
                keys.append(lay.key(ln.id, p))
    return keys
