"""Engine semantics, Excel-compatibility corner cases, and robustness fuzzing."""

import math
import random

import pytest

from spreadsheet_env.engine import Workbook, parse_formula, to_formula, translate_formula
from spreadsheet_env.engine.parser import FormulaSyntaxError
from spreadsheet_env.engine.refs import CIRC, DIV0, NAME, NUM, VALUE, ExcelError


def calc(formula, cells=None, iterative=False):
    wb = Workbook(iterative=iterative)
    wb.add_sheet("S")
    for c, v in (cells or {}).items():
        wb.set("S", c, v)
    wb.set("S", "Z1", formula)
    return wb.calculate()[("s", 1, 26)]


@pytest.mark.parametrize("formula,expected", [
    ("=-2^2", 4.0),             # unary minus binds tighter than ^ (Excel)
    ("=2^3^2", 64.0),           # ^ is left-associative in Excel
    ("=1+2*3", 7.0),
    ("=(1+2)*3", 9.0),
    ("=50%*4", 2.0),
    ("=ROUND(2.5,0)", 3.0),     # half away from zero
    ("=ROUND(-2.5,0)", -3.0),
    ("=ROUND(1.005,2)", 1.01),  # decimal rounding as Excel shows it
    ("=ROUNDDOWN(-1.99,0)", -1.0),
    ("=MOD(-3,2)", 1.0),        # sign of the divisor
    ("=INT(-1.5)", -2.0),
    ("=IF(1>2,1,2)", 2.0),
    ("=IFERROR(1/0,7)", 7.0),
    ("=AND(TRUE,1)", True),
    ("=NPV(0.1,100,200)", 100 / 1.1 + 200 / 1.21),
    ("=MAX(0,-5)", 0.0),
    ("=\"a\"&1&TRUE", "a1TRUE"),
])
def test_scalar_semantics(formula, expected):
    v = calc(formula)
    if isinstance(expected, float):
        assert v == pytest.approx(expected, rel=1e-12)
    else:
        assert v == expected


def test_errors_and_coercion():
    assert calc("=1/0") == DIV0
    assert calc("=A1+1", {"A1": "abc"}) == VALUE
    assert calc("=A1+1", {"A1": "3"}) == 4.0            # numeric text coerces in arithmetic
    assert calc("=SUM(A1:A3)", {"A1": 1, "A2": "x", "A3": True}) == 1.0  # ranges skip text/bool
    assert calc("=SUM(\"3\",TRUE)") == 4.0              # direct args coerce
    assert calc("=AVERAGE(A1:A2)") == DIV0
    assert calc("=A1:A2*2", {"A1": 1, "A2": 2}) == VALUE  # no implicit intersection
    assert calc("=SUMPRODUCT(A1:A2,B1:B2)", {"A1": 1, "A2": 2, "B1": 3, "B2": 4}) == 11.0
    assert calc("=SUMPRODUCT((A1:A2>1)*B1:B2)", {"A1": 1, "A2": 2, "B1": 3, "B2": 4}) == 4.0
    assert calc("=OFFSET(A1,1,0)") == NAME               # forbidden (volatile / dynamic refs)
    assert calc("=FOO(1)") == NAME


def test_pmt_irr_match_excel():
    assert calc("=PMT(0.05,10,1000)") == pytest.approx(-129.50457496545661, rel=1e-12)
    assert calc("=IRR(A1:A3)", {"A1": -100, "A2": 60, "A3": 60}) == pytest.approx(0.13066238629180732, rel=1e-9)


def test_circularity_and_iteration():
    assert calc("=Z1+1") == CIRC
    v = calc("=A1+0.1*Z1", {"A1": 100}, iterative=True)
    assert v == pytest.approx(100 / 0.9, rel=1e-12)


def test_translate_copy_semantics():
    assert translate_formula("=A1+$B$2+B$3+$C4", 1, 2) == "=C2+$B$2+D$3+$C5"
    assert translate_formula("=A1", -1, 0) == "=#REF!"


@pytest.mark.parametrize("src", ["=-(A1^2)", "=(1+2)*3-(4-5)", "=1-(2-3)", "=-A1%", "='My Sheet'!A1*2",
                                 "=SUM(A1:B2,3)", "=IF(A1>=2,\"x\",FALSE)"])
def test_print_roundtrip(src):
    ast = parse_formula(src)
    assert parse_formula(to_formula(ast)) == ast


def test_overflow_and_nesting_never_raise():
    assert calc("=SUM(1E308,1E308)") == NUM
    assert calc("=10^400") == NUM
    with pytest.raises(FormulaSyntaxError):
        parse_formula("=" + "(" * 100 + "1" + ")" * 100)
    with pytest.raises(FormulaSyntaxError):
        parse_formula("=" + "*".join(["1"] * 400))


@pytest.mark.parametrize("seed", range(4))
def test_fuzz_random_formulas_never_crash(seed):
    """Random token soup: parse may reject it, but evaluation must never raise."""
    rng = random.Random(seed)
    atoms = ["1", "0", "-1", "1E308", "1E17", "-1E17", "A1", "B2", "A1:B3", "\"t\"", "TRUE", "#DIV/0!", "S!A1", "0.5"]
    ops = ["+", "-", "*", "/", "^", "&", "=", "<", ">=", "%"]
    funcs = ["SUM", "IF", "MAX", "MIN", "NPV", "PMT", "IRR", "INDEX", "MATCH", "ROUND", "SUMPRODUCT",
             "AVERAGE", "IFERROR", "MOD", "CHOOSE", "LN", "SQRT"]

    def expr(d):
        r = rng.random()
        if d > 4 or r < 0.3:
            return rng.choice(atoms)
        if r < 0.6:
            return f"{expr(d + 1)}{rng.choice(ops)}{expr(d + 1)}"
        if r < 0.7:
            return f"({expr(d + 1)})"
        f = rng.choice(funcs)
        return f"{f}({','.join(expr(d + 1) for _ in range(rng.randint(1, 3)))})"

    for _ in range(3000):
        src = "=" + expr(0)
        try:
            parse_formula(src)
        except FormulaSyntaxError:
            continue
        v = calc(src, {"A1": 2, "B2": -3, "A2": "x", "B3": 0})
        assert v is None or isinstance(v, (float, str, bool, ExcelError))
        if isinstance(v, float):
            assert math.isfinite(v)
