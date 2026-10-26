"""Tokenizer, Pratt parser, printer and copy-translation for Excel formulas.

The accepted language is a deliberately *portable* subset of Excel: things
whose meaning is the same in Excel and LibreOffice Calc. Anything outside it
(whole-column ranges, intersection, structured references, named ranges, R1C1,
array constants) is a parse error rather than a silent approximation.

Precedence (high -> low), matching Excel::

    unary - +      (so -2^2 = 4)
    %              (postfix)
    ^              (left associative: 2^3^2 = 64)
    * /
    + -
    &
    = <> < > <= >=
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

from .refs import ERROR_CODES, CellRef, ExcelError, RangeRef, parse_cell


class FormulaSyntaxError(ValueError):
    pass


# --------------------------------------------------------------------------
# AST
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Num:
    value: float


@dataclass(frozen=True)
class Str:
    value: str


@dataclass(frozen=True)
class Bool:
    value: bool


@dataclass(frozen=True)
class Err:
    value: ExcelError


@dataclass(frozen=True)
class Ref:
    ref: CellRef


@dataclass(frozen=True)
class Rng:
    ref: RangeRef


@dataclass(frozen=True)
class Unary:
    op: str  # "-" or "+"
    operand: "Node"


@dataclass(frozen=True)
class Percent:
    operand: "Node"


@dataclass(frozen=True)
class Binary:
    op: str
    left: "Node"
    right: "Node"


@dataclass(frozen=True)
class Call:
    name: str
    args: Tuple["Node", ...]


Node = Union[Num, Str, Bool, Err, Ref, Rng, Unary, Percent, Binary, Call]

BINARY_PREC = {
    "=": 1, "<>": 1, "<": 1, ">": 1, "<=": 1, ">=": 1,
    "&": 2,
    "+": 3, "-": 3,
    "*": 4, "/": 4,
    "^": 5,
}
PERCENT_PREC = 6
UNARY_PREC = 7

# --------------------------------------------------------------------------
# Tokenizer
# --------------------------------------------------------------------------

_SHEET = r"(?:'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_.]*)"
_CELL = r"\$?[A-Za-z]{1,3}\$?[0-9]+"
_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<string>"(?:[^"]|"")*")
  | (?P<error>\#DIV/0!|\#N/A|\#REF!|\#NAME\?|\#VALUE!|\#NUM!|\#NULL!|\#CIRC!)
  | (?P<ref>(?:(?P<sheet>""" + _SHEET + r""")!)?(?P<c1>""" + _CELL + r""")(?::(?P<c2>""" + _CELL + r"""))?)(?![A-Za-z0-9_(.!])
  | (?P<number>(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)
  | (?P<func>[A-Za-z_][A-Za-z0-9_.]*)(?=\s*\()
  | (?P<ident>[A-Za-z_][A-Za-z0-9_.]*)
  | (?P<op><>|<=|>=|[-+*/^&=<>%])
  | (?P<lparen>\()
  | (?P<rparen>\))
  | (?P<comma>,)
    """,
    re.VERBOSE,
)


@dataclass
class Token:
    kind: str
    text: str
    pos: int
    node: Optional[Node] = None


def _unquote_sheet(s: str) -> str:
    if s.startswith("'"):
        return s[1:-1].replace("''", "'")
    return s


def tokenize(src: str) -> List[Token]:
    out: List[Token] = []
    pos = 0
    n = len(src)
    while pos < n:
        m = _TOKEN_RE.match(src, pos)
        if not m:
            raise FormulaSyntaxError(f"unexpected character {src[pos]!r} at {pos}")
        kind = m.lastgroup
        text = m.group(0)
        if m.group("ref") is not None:
            kind = "ref"
        if kind == "ws":
            pos = m.end()
            continue
        tok = Token(kind, text, pos)
        if kind == "ref":
            sheet = m.group("sheet")
            sheet = _unquote_sheet(sheet) if sheet else None
            try:
                c1 = parse_cell(m.group("c1"), sheet)
                c2 = parse_cell(m.group("c2"), sheet) if m.group("c2") else None
            except ValueError as e:
                raise FormulaSyntaxError(str(e)) from None
            tok.node = Rng(RangeRef(sheet, c1, c2)) if c2 else Ref(c1)
        elif kind == "ident":
            up = text.upper()
            if up in ("TRUE", "FALSE"):
                tok.kind = "bool"
                tok.node = Bool(up == "TRUE")
            else:
                raise FormulaSyntaxError(
                    f"unknown name {text!r} at {pos} (named ranges are not supported)"
                )
        elif kind == "number":
            tok.node = Num(float(text))
        elif kind == "string":
            tok.node = Str(text[1:-1].replace('""', '"'))
        elif kind == "error":
            tok.node = Err(ERROR_CODES[text])
        out.append(tok)
        pos = m.end()
    out.append(Token("eof", "", n))
    return out


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------

class _Parser:
    def __init__(self, tokens: List[Token]):
        self.toks = tokens
        self.i = 0

    def peek(self) -> Token:
        return self.toks[self.i]

    def next(self) -> Token:
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect(self, kind: str) -> Token:
        t = self.next()
        if t.kind != kind:
            raise FormulaSyntaxError(f"expected {kind} at {t.pos}, got {t.text!r}")
        return t

    def parse(self) -> Node:
        node = self.expr(0)
        if self.peek().kind != "eof":
            t = self.peek()
            raise FormulaSyntaxError(f"unexpected {t.text!r} at {t.pos}")
        return node

    def expr(self, min_prec: int) -> Node:
        left = self.prefix()
        while True:
            t = self.peek()
            if t.kind == "op" and t.text == "%":
                if PERCENT_PREC < min_prec:
                    break
                self.next()
                left = Percent(left)
                continue
            if t.kind != "op" or t.text not in BINARY_PREC:
                break
            prec = BINARY_PREC[t.text]
            if prec < min_prec:
                break
            self.next()
            right = self.expr(prec + 1)  # all binary operators are left-associative
            left = Binary(t.text, left, right)
        return left

    def prefix(self) -> Node:
        t = self.next()
        if t.kind == "op" and t.text in "+-":
            operand = self.expr(UNARY_PREC)
            return Unary(t.text, operand)
        if t.kind in ("number", "string", "bool", "error", "ref"):
            return t.node  # type: ignore[return-value]
        if t.kind == "lparen":
            node = self.expr(0)
            self.expect("rparen")
            return node
        if t.kind == "func":
            name = t.text.upper()
            self.expect("lparen")
            args: List[Node] = []
            if self.peek().kind != "rparen":
                while True:
                    if self.peek().kind in ("comma", "rparen"):
                        raise FormulaSyntaxError(
                            f"empty argument in {name}() at {self.peek().pos}"
                        )
                    args.append(self.expr(0))
                    if self.peek().kind == "comma":
                        self.next()
                        continue
                    break
            self.expect("rparen")
            return Call(name, tuple(args))
        raise FormulaSyntaxError(f"unexpected {t.text or 'end of formula'!r} at {t.pos}")


MAX_FORMULA_LEN = 2000
MAX_NESTING = 64


def parse_formula(src: str) -> Node:
    """Parse a formula. A leading ``=`` is optional."""
    s = src.strip()
    if s.startswith("="):
        s = s[1:]
    if not s:
        raise FormulaSyntaxError("empty formula")
    if len(s) > MAX_FORMULA_LEN:
        raise FormulaSyntaxError(f"formula longer than {MAX_FORMULA_LEN} characters")
    toks = tokenize(s)
    depth = 0
    for t in toks:  # bound recursion depth for the parser and the compiled closures
        if t.kind == "lparen":
            depth += 1
            if depth > MAX_NESTING:
                raise FormulaSyntaxError(f"formula nested deeper than {MAX_NESTING} levels")
        elif t.kind == "rparen":
            depth -= 1
    if sum(1 for t in toks if t.kind in ("op", "func")) > 300:
        raise FormulaSyntaxError("too many operators in one formula")
    try:
        return _Parser(toks).parse()
    except RecursionError:
        raise FormulaSyntaxError("formula nested too deeply") from None


# --------------------------------------------------------------------------
# Printer
# --------------------------------------------------------------------------

def _fmt_num(x: float) -> str:
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    r = repr(x)
    return r.upper() if "e" in r else r


def _prec(node: Node) -> int:
    if isinstance(node, Binary):
        return BINARY_PREC[node.op]
    if isinstance(node, Percent):
        return PERCENT_PREC
    if isinstance(node, Unary):
        return UNARY_PREC
    return 99


def to_formula(node: Node, top: bool = True) -> str:
    """Print an AST back to Excel syntax (with a leading ``=`` when ``top``)."""
    s = _print(node)
    return "=" + s if top else s


def _print(node: Node) -> str:
    if isinstance(node, Num):
        return _fmt_num(node.value)
    if isinstance(node, Str):
        return '"' + node.value.replace('"', '""') + '"'
    if isinstance(node, Bool):
        return "TRUE" if node.value else "FALSE"
    if isinstance(node, Err):
        return node.value.code
    if isinstance(node, Ref):
        return node.ref.a1()
    if isinstance(node, Rng):
        return node.ref.a1()
    if isinstance(node, Unary):
        inner = _print(node.operand)
        if _prec(node.operand) < UNARY_PREC:
            inner = "(" + inner + ")"
        return node.op + inner
    if isinstance(node, Percent):
        inner = _print(node.operand)
        if _prec(node.operand) < PERCENT_PREC:
            inner = "(" + inner + ")"
        return inner + "%"
    if isinstance(node, Binary):
        p = BINARY_PREC[node.op]
        left = _print(node.left)
        right = _print(node.right)
        if _prec(node.left) < p:
            left = "(" + left + ")"
        if _prec(node.right) <= p:
            right = "(" + right + ")"
        return f"{left}{node.op}{right}"
    if isinstance(node, Call):
        return node.name + "(" + ",".join(_print(a) for a in node.args) + ")"
    raise TypeError(f"unknown node {node!r}")


# --------------------------------------------------------------------------
# Tree utilities
# --------------------------------------------------------------------------

def walk(node: Node):
    """Yield every node in the tree (pre-order)."""
    yield node
    if isinstance(node, (Unary, Percent)):
        yield from walk(node.operand)
    elif isinstance(node, Binary):
        yield from walk(node.left)
        yield from walk(node.right)
    elif isinstance(node, Call):
        for a in node.args:
            yield from walk(a)


def map_refs(node: Node, fn) -> Node:
    """Return a copy of ``node`` with every Ref/Rng replaced by ``fn(node)``."""
    if isinstance(node, (Ref, Rng)):
        return fn(node)
    if isinstance(node, Unary):
        return Unary(node.op, map_refs(node.operand, fn))
    if isinstance(node, Percent):
        return Percent(map_refs(node.operand, fn))
    if isinstance(node, Binary):
        return Binary(node.op, map_refs(node.left, fn), map_refs(node.right, fn))
    if isinstance(node, Call):
        return Call(node.name, tuple(map_refs(a, fn) for a in node.args))
    return node


def translate(node: Node, drow: int, dcol: int) -> Node:
    """Excel copy/fill semantics: shift relative parts of every reference.

    A reference pushed off the sheet becomes ``#REF!`` (as in Excel).
    """

    def shift(n):
        try:
            return Ref(n.ref.shifted(drow, dcol)) if isinstance(n, Ref) else Rng(n.ref.shifted(drow, dcol))
        except ValueError:
            return Err(ERROR_CODES["#REF!"])

    return map_refs(node, shift)


def translate_formula(formula: str, drow: int, dcol: int) -> str:
    return to_formula(translate(parse_formula(formula), drow, dcol))


def with_sheet(node: Node, sheet: str) -> Node:
    """Make every sheet-less reference explicit (relative to ``sheet``)."""

    def fill(n):
        if isinstance(n, Ref) and n.ref.sheet is None:
            r = n.ref
            return Ref(CellRef(sheet, r.row, r.col, r.row_abs, r.col_abs))
        if isinstance(n, Rng) and n.ref.sheet is None:
            r = n.ref
            s = CellRef(sheet, r.start.row, r.start.col, r.start.row_abs, r.start.col_abs)
            e = CellRef(sheet, r.end.row, r.end.col, r.end.row_abs, r.end.col_abs)
            return Rng(RangeRef(sheet, s, e))
        return n

    return map_refs(node, fill)
