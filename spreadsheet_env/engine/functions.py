"""Excel value semantics (coercion, comparison) and the whitelisted functions.

Values are: ``float``, ``str``, ``bool``, ``None`` (blank cell) or
``ExcelError``. A range argument arrives as an ``Arr`` (rows of values).
"""

from __future__ import annotations

import math
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal
from typing import Callable, Dict, List

from .refs import DIV0, NA, NUM, REF, VALUE, ExcelError


class Arr:
    """A rectangular block of values (a range, or an array intermediate)."""

    __slots__ = ("rows",)

    def __init__(self, rows: List[list]):
        self.rows = rows

    @property
    def shape(self):
        return (len(self.rows), len(self.rows[0]) if self.rows else 0)

    def flat(self):
        for r in self.rows:
            yield from r


# --------------------------------------------------------------------------
# Coercion
# --------------------------------------------------------------------------

def num_result(x: float):
    """Normalise an arithmetic result (inf/nan -> #NUM!, -0.0 -> 0.0)."""
    if math.isnan(x) or math.isinf(x):
        return NUM
    return x + 0.0


def fsum(xs) -> object:
    """math.fsum that returns #NUM! instead of raising on overflow."""
    try:
        return num_result(math.fsum(xs))
    except (OverflowError, ValueError):
        return NUM


def to_number(v):
    """Scalar -> float, or an ExcelError. Mirrors Excel's arithmetic coercion."""
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, float):
        return v
    if isinstance(v, int):
        return float(v)
    if isinstance(v, ExcelError):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return VALUE
        try:
            if s.endswith("%"):
                return float(s[:-1]) / 100.0
            return float(s)
        except ValueError:
            return VALUE
    if isinstance(v, Arr):
        return VALUE
    return VALUE


def to_bool(v):
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, ExcelError):
        return v
    if isinstance(v, str):
        u = v.strip().upper()
        if u == "TRUE":
            return True
        if u == "FALSE":
            return False
        return VALUE
    return VALUE


def to_text(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return format(v, ".15g")
    if isinstance(v, ExcelError):
        return v
    if isinstance(v, str):
        return v
    return VALUE


def _type_rank(v) -> int:
    if isinstance(v, bool):
        return 2
    if isinstance(v, str):
        return 1
    return 0


def compare(op: str, a, b):
    """Excel comparison: numbers < text < logicals; text is case-insensitive."""
    if isinstance(a, ExcelError):
        return a
    if isinstance(b, ExcelError):
        return b
    # Blank cells take the "empty" value of the other side's type.
    if a is None:
        a = "" if isinstance(b, str) else (False if isinstance(b, bool) else 0.0)
    if b is None:
        b = "" if isinstance(a, str) else (False if isinstance(a, bool) else 0.0)
    ra, rb = _type_rank(a), _type_rank(b)
    if ra != rb:
        c = (ra > rb) - (ra < rb)
    else:
        if isinstance(a, str):
            x, y = a.casefold(), b.casefold()
        else:
            x, y = float(a), float(b)
        c = (x > y) - (x < y)
    return {
        "=": c == 0, "<>": c != 0, "<": c < 0, ">": c > 0, "<=": c <= 0, ">=": c >= 0,
    }[op]


def arith(op: str, a, b):
    x = to_number(a)
    if isinstance(x, ExcelError):
        return x
    y = to_number(b)
    if isinstance(y, ExcelError):
        return y
    if op == "+":
        return num_result(x + y)
    if op == "-":
        return num_result(x - y)
    if op == "*":
        return num_result(x * y)
    if op == "/":
        if y == 0:
            return DIV0
        return num_result(x / y)
    if op == "^":
        if x == 0 and y == 0:
            return NUM
        if x == 0 and y < 0:
            return DIV0
        if x < 0 and y != int(y):
            return NUM
        try:
            return num_result(math.pow(x, y))
        except (OverflowError, ValueError):
            return NUM
    raise ValueError(op)


def concat(a, b):
    x = to_text(a)
    if isinstance(x, ExcelError):
        return x
    y = to_text(b)
    if isinstance(y, ExcelError):
        return y
    return x + y


# --------------------------------------------------------------------------
# Argument collection helpers
# --------------------------------------------------------------------------

def _numbers(args, *, direct_coerce: bool = True):
    """Collect numbers the way SUM/AVERAGE/MIN/MAX do.

    Inside ranges only real numbers count (text, logicals, blanks ignored);
    direct scalar arguments are coerced (``SUM("3", TRUE)`` = 4).
    Returns a list of floats, or the first ExcelError met.
    """
    out = []
    for a in args:
        if isinstance(a, Arr):
            for v in a.flat():
                if isinstance(v, ExcelError):
                    return v
                if isinstance(v, float) and not isinstance(v, bool):
                    out.append(v)
        elif a is None:
            continue
        else:
            if isinstance(a, ExcelError):
                return a
            if not direct_coerce and isinstance(a, str):
                continue
            x = to_number(a)
            if isinstance(x, ExcelError):
                return x
            out.append(x)
    return out


def _sum(*args):
    xs = _numbers(args)
    if isinstance(xs, ExcelError):
        return xs
    return fsum(xs)


def _average(*args):
    xs = _numbers(args)
    if isinstance(xs, ExcelError):
        return xs
    if not xs:
        return DIV0
    t = fsum(xs)
    return t if isinstance(t, ExcelError) else num_result(t / len(xs))


def _min(*args):
    xs = _numbers(args)
    if isinstance(xs, ExcelError):
        return xs
    return min(xs) if xs else 0.0


def _max(*args):
    xs = _numbers(args)
    if isinstance(xs, ExcelError):
        return xs
    return max(xs) if xs else 0.0


def _count(*args):
    n = 0
    for a in args:
        if isinstance(a, Arr):
            n += sum(1 for v in a.flat() if isinstance(v, float) and not isinstance(v, bool))
        elif isinstance(a, (float, bool)) and not isinstance(a, ExcelError):
            n += 1
        elif isinstance(a, str) and not isinstance(to_number(a), ExcelError):
            n += 1
    return float(n)


def _logicals(args):
    out = []
    for a in args:
        vals = a.flat() if isinstance(a, Arr) else [a]
        for v in vals:
            if isinstance(v, ExcelError):
                return v
            if v is None or (isinstance(a, Arr) and isinstance(v, str)):
                continue
            b = to_bool(v)
            if isinstance(b, ExcelError):
                return b
            out.append(b)
    if not out:
        return VALUE
    return out


def _and(*args):
    bs = _logicals(args)
    return bs if isinstance(bs, ExcelError) else all(bs)


def _or(*args):
    bs = _logicals(args)
    return bs if isinstance(bs, ExcelError) else any(bs)


def _not(v):
    b = to_bool(v)
    return b if isinstance(b, ExcelError) else (not b)


def _num_args(fn):
    """Wrap a float function: coerce every argument, propagate errors."""

    def wrapped(*args):
        xs = []
        for a in args:
            x = to_number(a)
            if isinstance(x, ExcelError):
                return x
            xs.append(x)
        try:
            return fn(*xs)
        except (ValueError, ArithmeticError):
            return NUM
        except TypeError:
            return VALUE

    return wrapped


def _round_mode(x: float, d: float, mode) -> float:
    d = max(-308, min(308, int(d)))  # beyond float precision rounding is a no-op
    q = Decimal(1).scaleb(-d)
    r = Decimal(repr(x)).quantize(q, rounding=mode) if d >= 0 else (
        (Decimal(repr(x)) / Decimal(10) ** (-d)).quantize(Decimal(1), rounding=mode) * Decimal(10) ** (-d)
    )
    return float(r) + 0.0


def _mod(a, b):
    if b == 0:
        return DIV0
    return num_result(a - b * math.floor(a / b))


def _sqrt(x):
    return NUM if x < 0 else math.sqrt(x)


def _ln(x):
    return NUM if x <= 0 else math.log(x)


def _sign(x):
    return float((x > 0) - (x < 0))


def _sumproduct(*arrays):
    shapes = set()
    mats = []
    for a in arrays:
        if not isinstance(a, Arr):
            a = Arr([[a]])
        shapes.add(a.shape)
        mats.append(list(a.flat()))
    if len(shapes) != 1:
        return VALUE
    total = []
    for vals in zip(*mats):
        p = 1.0
        for v in vals:
            if isinstance(v, ExcelError):
                return v
            if isinstance(v, bool) or not isinstance(v, float):
                p = 0.0  # SUMPRODUCT treats non-numeric entries as zero
            else:
                p *= v
        total.append(p)
    return fsum(total)


def _npv(rate, *values):
    r = to_number(rate)
    if isinstance(r, ExcelError):
        return r
    if r == -1:
        return DIV0
    xs = _numbers(values)
    if isinstance(xs, ExcelError):
        return xs
    try:
        return fsum([x / (1 + r) ** (i + 1) for i, x in enumerate(xs)])
    except (OverflowError, ZeroDivisionError):
        return NUM


def _pmt(rate, nper, pv, fv=0.0, typ=0.0):
    if nper == 0:
        return NUM
    typ = 1.0 if typ else 0.0
    if rate == 0:
        return num_result(-(pv + fv) / nper)
    f = (1 + rate) ** nper
    return num_result(-(rate * (fv + pv * f)) / ((1 + rate * typ) * (f - 1)))


def _irr(values, guess=None):
    xs = _numbers([values], direct_coerce=False)
    if isinstance(xs, ExcelError):
        return xs
    if not xs or not (any(x > 0 for x in xs) and any(x < 0 for x in xs)):
        return NUM
    g = 0.1 if guess is None else to_number(guess)
    if isinstance(g, ExcelError):
        return g
    r = g
    for _ in range(100):  # Newton, as Excel; 20 iterations there, more here
        f = sum(x / (1 + r) ** i for i, x in enumerate(xs))
        df = sum(-i * x / (1 + r) ** (i + 1) for i, x in enumerate(xs))
        if df == 0:
            return NUM
        nr = r - f / df
        if nr <= -1:
            return NUM
        if abs(nr - r) < 1e-12:
            return nr
        r = nr
    return NUM


def _index(arr, row, col=None):
    if not isinstance(arr, Arr):
        arr = Arr([[arr]])
    r = to_number(row)
    if isinstance(r, ExcelError):
        return r
    nrows, ncols = arr.shape
    if col is None:
        if nrows == 1:  # one index into a single row selects a column
            r, c = 1.0, r
        elif ncols == 1:
            c = 1.0
        else:
            return REF
    else:
        c = to_number(col)
        if isinstance(c, ExcelError):
            return c
    r, c = int(r), int(c)
    if r < 1 or c < 1 or r > nrows or c > ncols:
        return REF
    return arr.rows[r - 1][c - 1]


def _match(value, arr, mtype=1.0):
    if isinstance(value, ExcelError):
        return value
    if not isinstance(arr, Arr):
        arr = Arr([[arr]])
    nrows, ncols = arr.shape
    if nrows != 1 and ncols != 1:
        return NA
    vals = list(arr.flat())
    t = to_number(mtype)
    if isinstance(t, ExcelError):
        return t
    if t == 0:
        for i, v in enumerate(vals):
            if v is not None and compare("=", value, v) is True:
                return float(i + 1)
        return NA
    best = None
    for i, v in enumerate(vals):  # assumes sorted data, like Excel
        if v is None or _type_rank(v) != _type_rank(value):
            continue
        ok = compare("<=", v, value) if t > 0 else compare(">=", v, value)
        if ok is True:
            best = i
        else:
            break
    return NA if best is None else float(best + 1)


def _choose(idx, *options):
    i = to_number(idx)
    if isinstance(i, ExcelError):
        return i
    i = int(i)
    if i < 1 or i > len(options):
        return VALUE
    return options[i - 1]


# name -> (callable, min_args, max_args, range_args)
# ``range_args``: argument positions that receive Arr (refs become 1x1 Arr);
# "all" means every argument.
FUNCTIONS: Dict[str, tuple] = {
    "SUM": (_sum, 1, 255, "all"),
    "AVERAGE": (_average, 1, 255, "all"),
    "MIN": (_min, 1, 255, "all"),
    "MAX": (_max, 1, 255, "all"),
    "COUNT": (_count, 1, 255, "all"),
    "AND": (_and, 1, 255, "all"),
    "OR": (_or, 1, 255, "all"),
    "NOT": (_not, 1, 1, ()),
    "ABS": (_num_args(lambda x: abs(x)), 1, 1, ()),
    "ROUND": (_num_args(lambda x, d: _round_mode(x, d, ROUND_HALF_UP)), 2, 2, ()),
    "ROUNDUP": (_num_args(lambda x, d: _round_mode(x, d, ROUND_UP)), 2, 2, ()),
    "ROUNDDOWN": (_num_args(lambda x, d: _round_mode(x, d, ROUND_DOWN)), 2, 2, ()),
    "INT": (_num_args(lambda x: float(math.floor(x))), 1, 1, ()),
    "MOD": (_num_args(_mod), 2, 2, ()),
    "POWER": (lambda a, b: arith("^", a, b), 2, 2, ()),
    "SQRT": (_num_args(_sqrt), 1, 1, ()),
    "LN": (_num_args(_ln), 1, 1, ()),
    "EXP": (_num_args(lambda x: num_result(math.exp(x))), 1, 1, ()),
    "SIGN": (_num_args(_sign), 1, 1, ()),
    "SUMPRODUCT": (_sumproduct, 1, 255, "all"),
    "NPV": (_npv, 2, 255, "rest"),
    "PMT": (_num_args(_pmt), 3, 5, ()),
    "IRR": (_irr, 1, 2, (0,)),
    "INDEX": (_index, 2, 3, (0,)),
    "MATCH": (_match, 2, 3, (1,)),
    "CHOOSE": (_choose, 2, 255, ()),
    # IF / IFERROR are lazy and handled by the compiler.
    "IF": (None, 2, 3, ()),
    "IFERROR": (None, 2, 2, ()),
}

# Functions that are recognised but refused: volatile, or able to build
# references dynamically (both defeat dependency analysis and perturbation
# grading). The engine evaluates them to #NAME?; the grader reports them.
FORBIDDEN_FUNCTIONS = frozenset({
    "INDIRECT", "OFFSET", "RAND", "RANDBETWEEN", "RANDARRAY", "NOW", "TODAY",
    "CELL", "INFO", "HYPERLINK", "WEBSERVICE", "FILTERXML", "RTD", "CALL",
    "REGISTER.ID", "EVALUATE", "LAMBDA", "LET", "TABLE",
})


def is_range_arg(name: str, pos: int) -> bool:
    spec = FUNCTIONS[name][3]
    if spec == "all":
        return True
    if spec == "rest":
        return pos >= 1
    return pos in spec


FuncImpl = Callable[..., object]
