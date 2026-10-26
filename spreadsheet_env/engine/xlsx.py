"""Read/write workbooks as .xlsx with openpyxl (formulas kept as text).

openpyxl never evaluates formulas; values are computed by this package's
engine (or by Excel / LibreOffice when the file is opened there).
"""

from __future__ import annotations

from typing import Optional

from .workbook import Workbook


def save_xlsx(wb: Workbook, path: str, values: Optional[dict] = None) -> None:
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    out = openpyxl.Workbook()
    out.remove(out.active)
    blue = Font(color="0000CC")
    for name in wb.sheet_names:
        ws = out.create_sheet(title=name)
        for _, r, c, raw in wb.cells(name):
            cell = ws.cell(row=r, column=c, value=raw)
            if isinstance(raw, float) and c > 2:
                cell.font = blue  # inputs in blue, the usual modelling convention
        ws.column_dimensions["A"].width = 36
    if wb.iterative:
        out.calculation.iterate = True
        out.calculation.iterateCount = 1000
        out.calculation.iterateDelta = 1e-9
    out.calculation.fullCalcOnLoad = True
    out.save(path)


def load_xlsx(path: str) -> Workbook:
    import openpyxl

    src = openpyxl.load_workbook(path, data_only=False)
    wb = Workbook(iterative=bool(getattr(src.calculation, "iterate", False)))
    for ws in src.worksheets:
        wb.add_sheet(ws.title)
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if v is None:
                    continue
                if hasattr(v, "text"):  # ArrayFormula
                    v = v.text
                if isinstance(v, int) and not isinstance(v, bool):
                    v = float(v)
                wb.set_rc(ws.title, cell.row, cell.column, v)
    return wb
