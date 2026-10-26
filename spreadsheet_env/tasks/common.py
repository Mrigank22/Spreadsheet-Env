"""Helpers that turn a generated model into grading metadata."""

from __future__ import annotations

import random
from typing import Dict, Iterable, List, Sequence

from ..engine.refs import addr
from ..engine.workbook import Key, Workbook
from ..grader.scenarios import select_scenarios
from ..model.spec import Layout, ModelSpec
from ..model.three_statement import GeneratedModel
from .base import Fixup, IdentityCheck, InputInfo

SCALE_FACTOR = 3.7
ALLOWED_FUNCTIONS_TEXT = (
    "SUM, AVERAGE, MIN, MAX, COUNT, IF, IFERROR, AND, OR, NOT, ABS, ROUND, ROUNDUP, "
    "ROUNDDOWN, INT, MOD, POWER, SQRT, LN, EXP, SIGN, SUMPRODUCT, NPV, PMT, IRR, INDEX, "
    "MATCH, CHOOSE"
)

_SCALAR_KIND = {"tax_rate": "tax", "payout": "payout", "int_rate": "interest",
                "rev_rate": "interest", "cash_rate": "interest"}


def inputs_for(gm: GeneratedModel, lay: Layout) -> List[InputInfo]:
    spec = gm.spec
    rev_line = spec.line("rev")
    scale = float(rev_line.history[-1]) if rev_line.history else 100.0
    out: List[InputInfo] = []
    for s in spec.scalars:
        kind = _SCALAR_KIND.get(s.id, s.kind)
        out.append(InputInfo(lay.scalar_key(s.id), kind, float(s.value), scale, lo=0.0))
    for ln in spec.lines:
        if ln.is_input_series and ln.forecast is not None:
            for i, v in enumerate(ln.forecast):
                kind = "growth" if ln.kind == "rate" else ln.kind
                out.append(InputInfo(lay.key(ln.id, spec.n_hist + i), kind, float(v), scale))
        if ln.hist == "input" and ln.history is not None:
            for p, v in enumerate(ln.history):
                if ln.id == "re":
                    continue  # residual, set by the fixup
                lo = 0.0 if ln.id != "re" else None
                out.append(InputInfo(lay.key(ln.id, p), "money", float(v), scale, lo=lo))
    return out


def balance_fixups(gm: GeneratedModel, lay: Layout) -> List[Fixup]:
    """Historical retained earnings = assets - liabilities - common stock."""
    spec = gm.spec
    ids = {ln.id for ln in spec.lines}
    assets = [i for i in ("cash", "ar", "inv", "ppe") if i in ids]
    liabs = [i for i in ("ap", "debt", "revolver") if i in ids]
    fx = []
    for p in range(spec.n_hist):
        terms = [(1.0, lay.key(a, p)) for a in assets]
        terms += [(-1.0, lay.key(lb, p)) for lb in liabs]
        terms.append((-1.0, lay.key("cs", p)))
        fx.append(Fixup(lay.key("re", p), terms))
    return fx


def identity_checks(gm: GeneratedModel, lay: Layout) -> List[IdentityCheck]:
    out = []
    for idn in gm.identities:
        per = []
        for p in lay.forecast_indices:
            per.append([(sign, lay.key(lid, p + off)) for sign, lid, off in idn.terms])
        out.append(IdentityCheck(idn.name, idn.desc, per))
    return out


def forbidden_dep_rules(gm: GeneratedModel, lay: Layout):
    """Instantiate the generator's structural rules on concrete cells."""
    out = []
    for srcs, bans, why in gm.forbidden:
        a = [lay.key(i, p) for i in srcs for p in lay.forecast_indices]
        b = [lay.key(i, p) for i in bans for p in range(lay.n_periods)]
        out.append((a, b, why))
    return out


def labels_for(spec: ModelSpec, lay: Layout) -> Dict[Key, str]:
    out: Dict[Key, str] = {}
    for s in spec.scalars:
        sheet, r, c = lay.scalars[s.id]
        out[lay.scalar_key(s.id)] = f"{sheet}!{addr(r, c)} ({s.label})"
    for ln in spec.lines:
        sheet, r = lay.rows[ln.id]
        for p, name in enumerate(lay.periods):
            out[lay.key(ln.id, p)] = f"{sheet}!{addr(r, lay.col(p))} ({ln.label} {name})"
    return out


def money_keys(spec: ModelSpec, lay: Layout, keys: Iterable[Key]) -> List[Key]:
    money_lines = {lay.rows[ln.id] for ln in spec.lines if ln.kind == "money"}
    return [k for k in keys if any(k[0] == s.casefold() and k[1] == r for s, r in money_lines)]


def locked_cells(initial: Workbook, editable: Iterable[Key] = ()) -> Dict[Key, object]:
    ed = set(editable)
    return {k: v for k, v in initial.snapshot().items() if k not in ed}


def scenarios_for(reference: Workbook, inputs: Sequence[InputInfo], fixups: Sequence[Fixup],
                  targets: Sequence[Key], seed: int, k: int = 10, coverage: bool = True):
    rng = random.Random(f"scenarios:{seed}")
    # 80 candidates even for (slow) circular models: tested 40 vs 80 on 8 circular
    # models - 40 lost branch arms in 5 of 8 (46-47 vs 48 arms covered)
    return select_scenarios(reference, inputs, fixups, targets, rng, k=k, coverage=coverage,
                            n_candidates=80, scale_factor=SCALE_FACTOR)


def model_map(spec: ModelSpec, lay: Layout) -> str:
    """A compact description of where everything lives."""
    lines = []
    hist = ", ".join(lay.periods[: spec.n_hist])
    fc = ", ".join(lay.periods[spec.n_hist:])
    from ..engine.refs import index_to_col

    c0, c1 = index_to_col(lay.col(0)), index_to_col(lay.col(spec.n_hist - 1))
    f0, f1 = index_to_col(lay.col(spec.n_hist)), index_to_col(lay.col(lay.n_periods - 1))
    lines.append(f"Period columns (same on every sheet): actuals {c0}:{c1} ({hist}); "
                 f"forecast {f0}:{f1} ({fc}). Column A = labels, B = units.")
    by_sheet: Dict[str, List[str]] = {}
    for s in spec.scalars:
        sheet, r, c = lay.scalars[s.id]
        by_sheet.setdefault(sheet, []).append(f"{addr(r, c)} {s.label} = {s.value:g}")
    for ln in spec.lines:
        sheet, r = lay.rows[ln.id]
        by_sheet.setdefault(sheet, []).append(f"row {r} {ln.label}")
    for sheet in spec.sheets:
        if sheet in by_sheet:
            lines.append(f"{sheet}: " + "; ".join(by_sheet[sheet]))
    return "\n".join(lines)
