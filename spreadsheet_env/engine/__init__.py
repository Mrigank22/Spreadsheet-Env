"""A small, deterministic, Excel-compatible formula engine (portable subset)."""

from .functions import FORBIDDEN_FUNCTIONS, FUNCTIONS, Arr
from .parser import FormulaSyntaxError, parse_formula, to_formula, translate_formula
from .refs import ExcelError, addr, col_to_index, index_to_col, parse_cell, parse_range
from .workbook import CompiledWorkbook, Key, Workbook, key_label, key_of

__all__ = [
    "Arr", "CompiledWorkbook", "ExcelError", "FORBIDDEN_FUNCTIONS", "FUNCTIONS",
    "FormulaSyntaxError", "Key", "Workbook", "addr", "col_to_index", "index_to_col",
    "key_label", "key_of", "parse_cell", "parse_formula", "parse_range", "to_formula",
    "translate_formula",
]
