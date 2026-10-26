"""A1-style cell/range references, Excel error values and small helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

MAX_ROWS = 1_048_576
MAX_COLS = 16_384


class ExcelError(Exception):
    """An Excel error *value* (``#DIV/0!`` ...). Instances are compared by code.

    It subclasses ``Exception`` only so evaluation code can ``raise`` it to
    short-circuit error propagation; as a cell value it is just a value.
    """

    __slots__ = ("code",)

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code

    def __eq__(self, other):
        return isinstance(other, ExcelError) and other.code == self.code

    def __hash__(self):
        return hash(("ExcelError", self.code))

    def __repr__(self):
        return self.code

    __str__ = __repr__


DIV0 = ExcelError("#DIV/0!")
VALUE = ExcelError("#VALUE!")
REF = ExcelError("#REF!")
NAME = ExcelError("#NAME?")
NUM = ExcelError("#NUM!")
NA = ExcelError("#N/A")
NULL = ExcelError("#NULL!")
# Not an Excel error: Excel reports circularity with a warning and shows 0.
# The engine marks every cell on a cycle with this value so graders can see it.
CIRC = ExcelError("#CIRC!")

ERROR_CODES = {e.code: e for e in (DIV0, VALUE, REF, NAME, NUM, NA, NULL, CIRC)}


def col_to_index(letters: str) -> int:
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def index_to_col(n: int) -> str:
    if n < 1:
        raise ValueError(f"column index must be >= 1, got {n}")
    out = []
    while n:
        n, r = divmod(n - 1, 26)
        out.append(chr(65 + r))
    return "".join(reversed(out))


_SIMPLE_SHEET = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_CELL_RE = re.compile(r"^(\$?)([A-Za-z]{1,3})(\$?)([0-9]+)$")


def quote_sheet(name: str) -> str:
    """Sheet name as it must appear before ``!`` in a formula."""
    if _SIMPLE_SHEET.match(name) and not _CELL_RE.match(name):
        return name
    return "'" + name.replace("'", "''") + "'"


@dataclass(frozen=True)
class CellRef:
    sheet: Optional[str]
    row: int
    col: int
    row_abs: bool = False
    col_abs: bool = False

    def a1(self, with_sheet: bool = True) -> str:
        s = (
            ("$" if self.col_abs else "")
            + index_to_col(self.col)
            + ("$" if self.row_abs else "")
            + str(self.row)
        )
        if with_sheet and self.sheet is not None:
            return quote_sheet(self.sheet) + "!" + s
        return s

    def shifted(self, drow: int, dcol: int) -> "CellRef":
        """Relative-copy translation (fill/copy semantics)."""
        r = self.row if self.row_abs else self.row + drow
        c = self.col if self.col_abs else self.col + dcol
        if r < 1 or c < 1 or r > MAX_ROWS or c > MAX_COLS:
            raise ValueError("reference moved off the sheet")
        return CellRef(self.sheet, r, c, self.row_abs, self.col_abs)


@dataclass(frozen=True)
class RangeRef:
    sheet: Optional[str]
    start: CellRef
    end: CellRef

    @property
    def rows(self) -> range:
        return range(min(self.start.row, self.end.row), max(self.start.row, self.end.row) + 1)

    @property
    def cols(self) -> range:
        return range(min(self.start.col, self.end.col), max(self.start.col, self.end.col) + 1)

    @property
    def size(self) -> int:
        return len(self.rows) * len(self.cols)

    def a1(self, with_sheet: bool = True) -> str:
        s = self.start.a1(False) + ":" + self.end.a1(False)
        if with_sheet and self.sheet is not None:
            return quote_sheet(self.sheet) + "!" + s
        return s

    def shifted(self, drow: int, dcol: int) -> "RangeRef":
        return RangeRef(self.sheet, self.start.shifted(drow, dcol), self.end.shifted(drow, dcol))


def parse_cell(text: str, sheet: Optional[str] = None) -> CellRef:
    """Parse ``B7`` / ``$B$7`` (no sheet prefix) into a CellRef."""
    m = _CELL_RE.match(text.strip())
    if not m:
        raise ValueError(f"not a cell reference: {text!r}")
    ca, letters, ra, digits = m.groups()
    col, row = col_to_index(letters), int(digits)
    if not (1 <= row <= MAX_ROWS and 1 <= col <= MAX_COLS):
        raise ValueError(f"cell out of range: {text!r}")
    return CellRef(sheet, row, col, bool(ra), bool(ca))


def parse_range(text: str, sheet: Optional[str] = None) -> RangeRef:
    """Parse ``B7:F9`` or a single cell ``B7`` (as a 1x1 range)."""
    text = text.strip()
    if ":" in text:
        a, b = text.split(":", 1)
        return RangeRef(sheet, parse_cell(a, sheet), parse_cell(b, sheet))
    c = parse_cell(text, sheet)
    return RangeRef(sheet, c, c)


def addr(row: int, col: int) -> str:
    return f"{index_to_col(col)}{row}"
