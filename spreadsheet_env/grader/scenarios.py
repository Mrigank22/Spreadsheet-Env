"""Perturbation scenarios for metamorphic grading.

A scenario is a dict {input cell -> value}. The grader recalculates both the
agent's workbook and the hidden reference under each scenario and compares the
target cells. Wrong formulas that happen to give the right number at the base
inputs (stale hard-codes, a wrong reference to a cell with the same value, an
``IF`` branch that is not active at the base case ...) disagree somewhere.

Scenario *selection* is coverage-guided: we sample many candidates, run the
reference with branch instrumentation, and greedily keep the candidates that
exercise IF/MAX/MIN arms not yet covered (e.g. a loss year, so ``MAX(0, EBT)``
takes its zero arm; a cash shortfall, so the revolver draws). The remaining
slots are filled with random candidates. ``scripts/exp_scenario_selection.py``
measures whether this beats purely random selection.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence

from ..engine.refs import ExcelError
from ..engine.workbook import Key, Workbook
from ..task import Fixup, InputInfo

WIDE = {
    "rate": (0.0, 1.0),
    "tax": (0.0, 0.6),
    "payout": (0.0, 1.0),
    "growth": (-0.35, 0.45),
    "days": (0.0, 160.0),
    "interest": (0.0, 0.25),
    "wacc": (0.07, 0.16),
    "tg": (0.0, 0.035),
    "multiple": (3.0, 16.0),
}

# For circular models a scenario is kept only if the reference converges
# quickly (a strong contraction); then any sensible formulation of the same
# cycle also converges, so non-convergence cannot be blamed on the agent.
MAX_REFERENCE_ITERATIONS = 200
EXTRA_ROUND = 40  # candidates per coverage-directed search round


def _clip(x: float, info: InputInfo) -> float:
    if info.lo is not None:
        x = max(info.lo, x)
    if info.hi is not None:
        x = min(info.hi, x)
    return x


def perturb_one(info: InputInfo, rng: random.Random, mode: str) -> float:
    b = info.base
    k = info.kind
    if k in ("fixed", "money_fixed"):  # structural inputs are never perturbed (money_fixed still scales
        return b                         # with the currency unit in the homogeneity scenario)
    if mode == "extreme":
        # every input moves independently over a very wide range: money log-uniform
        # over three orders of magnitude, rates/days over their whole plausible range.
        # Reaches branch arms the other modes rarely touch (e.g. debt that is nearly
        # repaid, so MIN(repayment, debt) switches to the debt side).
        if k in ("money", "count"):
            if b == 0:
                return round(rng.uniform(0, 0.5) * info.scale, 4)
            return _clip(round(b * 10 ** rng.uniform(-1.5, 1.5), 4), info)
        mode = "wide"
    if k == "money":
        if b == 0:
            return round(rng.uniform(0, 0.3) * info.scale, 4) if mode == "wide" else 0.0
        f = rng.uniform(0.8, 1.25) if mode == "local" else rng.uniform(0.15, 3.5)
        return _clip(round(b * f, 4), info)
    if k == "count":  # share counts etc.: multiplicative, never scaled with currency
        f = rng.uniform(0.8, 1.25) if mode == "local" else rng.uniform(0.3, 3.0)
        return _clip(round(b * f, 4), info)
    if k == "growth":
        x = b + rng.gauss(0, 0.03) if mode == "local" else rng.uniform(*WIDE["growth"])
        return _clip(round(x, 5), info)
    if k == "days":
        x = b * rng.uniform(0.75, 1.3) if mode == "local" else rng.uniform(*WIDE["days"])
        return _clip(round(x, 3), info)
    lo, hi = WIDE.get(k, WIDE["rate"])
    if mode == "local":
        x = b * (1 + rng.gauss(0, 0.15)) if b else rng.uniform(lo, (hi - lo) * 0.1)
    else:
        x = rng.uniform(lo, hi)
    return _clip(round(x, 5), info)


def apply_fixups(sc: Dict[Key, float], base: Dict[Key, float], fixups: Sequence[Fixup]) -> None:
    for fx in fixups:
        sc[fx.target] = round(sum(s * sc.get(k, base.get(k, 0.0)) for s, k in fx.terms), 6)


def sample_candidate(inputs: Sequence[InputInfo], fixups: Sequence[Fixup], rng: random.Random,
                     mode: str) -> Dict[Key, float]:
    base = {i.key: i.base for i in inputs}
    if mode == "single":
        info = rng.choice(list(inputs))
        sc = {info.key: perturb_one(info, rng, rng.choice(["local", "wide"]))}
    else:
        sc = {i.key: perturb_one(i, rng, mode) for i in inputs}
    _sort_groups(sc, base, inputs)
    apply_fixups(sc, base, fixups)
    return sc


def _sort_groups(sc: Dict[Key, float], base: Dict[Key, float], inputs: Sequence[InputInfo]) -> None:
    """Re-sort each ascending grid (``InputInfo.group``) after independent moves:
    "the highest exit" is the last column of such a grid in every scenario, as in
    the base case (HACK_LOG #20)."""
    groups: Dict[str, List[Key]] = {}
    for i in inputs:
        if i.group:
            groups.setdefault(i.group, []).append(i.key)
    for keys in groups.values():
        for k, v in zip(keys, sorted(sc.get(k, base[k]) for k in keys)):
            if k in sc or v != base[k]:
                sc[k] = v


def scale_scenario(inputs: Sequence[InputInfo], fixups: Sequence[Fixup], factor: float) -> Dict[Key, float]:
    """Every money input times ``factor`` (rates/days unchanged).

    Financial models are homogeneous of degree one in the currency unit, so
    every money output must scale by the same factor. Embedded money
    constants ("+1000" fudges, pasted values) break this.
    """
    base = {i.key: i.base for i in inputs}
    sc = {i.key: round(i.base * factor, 6) for i in inputs if i.kind in ("money", "money_fixed")}
    apply_fixups(sc, base, fixups)
    return sc


def _valid(vals: Dict[Key, object], targets: Sequence[Key]) -> bool:
    for k in targets:
        v = vals.get(k)
        if isinstance(v, ExcelError) or not isinstance(v, float) or abs(v) > 1e13:
            return False
    return True


def select_scenarios(reference: Workbook, inputs: Sequence[InputInfo], fixups: Sequence[Fixup],
                     targets: Sequence[Key], rng: random.Random, k: int = 10,
                     n_candidates: int = 80, coverage: bool = True,
                     scale_factor: Optional[float] = 3.7,
                     modes: Sequence[str] = ("local", "wide", "single", "extreme")) -> List[Dict[Key, float]]:
    """Pick ``k`` scenarios (plus the scale scenario) for a task."""
    cw = reference.compile(instrument=coverage)
    base_vals = cw.run()
    base_arms = set(cw.trace)
    cands = []

    def draw(n, mode_seq):
        found = set()
        for i in range(n):
            sc = sample_candidate(inputs, fixups, rng, mode_seq[i % len(mode_seq)])
            cw.trace.clear()
            vals = cw.run(sc)
            if not _valid(vals, targets) or getattr(cw, "iterations_used", 0) > MAX_REFERENCE_ITERATIONS:
                continue
            arms = set(cw.trace)
            cands.append((sc, arms))
            found |= arms
        return found

    reached = draw(n_candidates, list(modes)) | base_arms
    if coverage:
        # coverage-directed search: extra rounds of extreme candidates while they keep
        # reaching branch arms no earlier candidate reached (rare regions such as
        # "debt nearly repaid" in MIN(repayment, debt))
        for _ in range(2):
            new = draw(EXTRA_ROUND, ["extreme"]) - reached
            if not new:
                break
            reached |= new
    chosen: List[Dict[Key, float]] = []
    covered = set(base_arms)
    if coverage:
        pool = list(cands)
        while pool and len(chosen) < k:
            best = max(pool, key=lambda c: len(c[1] - covered))
            gain = len(best[1] - covered)
            if gain == 0:
                break
            chosen.append(best[0])
            covered |= best[1]
            pool.remove(best)
        rest = [c for c in cands if c[0] not in chosen]
    else:
        rest = list(cands)
    rng.shuffle(rest)
    # keep a mix: prefer joint (all-input) scenarios for the random fill
    rest.sort(key=lambda c: len(c[0]) < len(inputs) // 2)
    for sc, _ in rest:
        if len(chosen) >= k:
            break
        chosen.append(sc)
    if scale_factor:
        sc = scale_scenario(inputs, fixups, scale_factor)
        if _valid(cw.run(sc), targets):
            chosen.append(sc)
    del base_vals
    return chosen


def branch_coverage(reference: Workbook, scenarios: Sequence[Dict[Key, float]]) -> Dict[str, int]:
    """How many (branch point, arm) pairs the base case + scenarios exercise."""
    cw = reference.compile(instrument=True)
    cw.run()
    for sc in scenarios:
        cw.run(sc)
    points = {(k, i) for k, i, _ in cw.trace}
    return {"branch_points": len(points), "arms_covered": len(cw.trace)}
