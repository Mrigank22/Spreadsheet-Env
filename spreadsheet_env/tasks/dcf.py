"""Task family ``dcf``: build a DCF valuation and its WACC x growth sensitivity grid."""

from __future__ import annotations

import random
from typing import Dict, List

from ..engine.refs import addr, index_to_col
from ..engine.workbook import Key
from ..model.dcf import GRID_SHEET, DCFConfig, generate_dcf, render_dcf
from .base import IdentityCheck, InputInfo, Task
from .common import ALLOWED_FUNCTIONS_TEXT, SCALE_FACTOR, locked_cells, scenarios_for

FCF_LINES = ["rev", "ebitda", "da", "ebit", "tax", "nopat", "capex", "nwc", "d_nwc", "ufcf"]
DISC_LINES = ["period", "disc_t", "df", "pv"]
CALCS = ["sum_pv", "tv", "pv_tv", "ev", "equity", "price"]

DCF_LEVELS = {
    1: dict(cfg=DCFConfig(n_forecast=5), lines=["df", "pv"], calcs=True, grid=False, max_steps=30),
    2: dict(cfg=DCFConfig(n_forecast=5), lines=FCF_LINES + DISC_LINES, calcs=True, grid=False, max_steps=50),
    3: dict(cfg=DCFConfig(n_forecast=5), lines=[], calcs=False, grid=True, max_steps=40),
    4: dict(cfg=DCFConfig(n_forecast=6), lines=FCF_LINES + DISC_LINES, calcs=True, grid=True, max_steps=80),
    5: dict(cfg=DCFConfig(n_forecast=7, mid_year=True, tax_floor=True), lines=FCF_LINES + DISC_LINES,
            calcs=True, grid=True, max_steps=100),
}

_KIND = {"wacc": ("wacc", 0.07, 0.16), "tg": ("tg", 0.0, 0.035)}


def _inputs(gen, lay) -> List[InputInfo]:
    spec = gen.spec
    scale = float(spec.line("rev").history[-1])
    out = []
    for s in spec.scalars:
        kind, lo, hi = _KIND.get(s.id, (s.kind, 0.0 if s.id != "net_debt" else None, None))
        out.append(InputInfo(lay.scalar_key(s.id), kind, float(s.value), scale, lo=lo, hi=hi))
    for ln in spec.lines:
        if ln.is_input_series and ln.forecast is not None:
            for i, v in enumerate(ln.forecast):
                out.append(InputInfo(lay.key(ln.id, spec.n_hist + i), "growth", float(v), scale))
        if ln.hist == "input" and ln.history is not None and ln.id != "period":
            for p, v in enumerate(ln.history):
                out.append(InputInfo(lay.key(ln.id, p), "money", float(v), scale, lo=0.0))
    return out


def dcf_task(seed: int, difficulty: int = 2) -> Task:
    level = DCF_LEVELS[difficulty]
    rng = random.Random(f"dcf:{difficulty}:{seed}")
    gen = generate_dcf(rng, level["cfg"])
    spec = gen.spec
    reference, lay = render_dcf(gen)

    target_lines = [lid for lid in level["lines"] if lid in lay.rows]
    targets: List[Key] = [lay.key(lid, p) for lid in target_lines for p in lay.forecast_indices]
    if level["calcs"]:
        targets += [lay.calc_key(c) for c in CALCS]
    if level["grid"]:
        targets += [k for row in gen.grid_keys for k in row]
    initial = reference.copy()
    for k in targets:
        initial.set_rc(initial.sheet_name(k[0]), k[1], k[2], None)

    inputs = _inputs(gen, lay)
    all_formulas = [k for k, v in reference.snapshot().items() if isinstance(v, str) and v.startswith("=")]
    scenarios = scenarios_for(reference, inputs, [], all_formulas, seed)

    # ---------------- reference-free checks ------------------------------------
    ids = []
    ids.append(IdentityCheck("ufcf_definition", "UFCF = NOPAT + D&A - capex - increase in NWC", [
        [(1, lay.key("ufcf", p)), (-1, lay.key("nopat", p)), (-1, lay.key("da", p)),
         (1, lay.key("capex", p)), (1, lay.key("d_nwc", p))] for p in lay.forecast_indices]))
    ids.append(IdentityCheck("ev_bridge", "EV = sum of PV of FCF + PV of terminal value; equity = EV - net debt", [
        [(1, lay.calc_key("ev")), (-1, lay.calc_key("sum_pv")), (-1, lay.calc_key("pv_tv"))],
        [(1, lay.calc_key("equity")), (-1, lay.calc_key("ev")), (1, lay.scalar_key("net_debt"))],
    ]))
    price = lay.calc_key("price")
    relations = [
        {"type": "grid", "name": "grid_matches_own_model", "cells": gen.grid_keys,
         "row_headers": gen.row_header_keys, "col_headers": gen.col_header_keys,
         "row_input": lay.scalar_key("wacc"), "col_input": lay.scalar_key("tg"), "output": price,
         "runs": [0, 1, 2]},
        {"type": "monotone", "name": "price_falls_with_wacc", "output": price,
         "input": lay.scalar_key("wacc"), "delta": 0.005, "sign": -1},
        {"type": "monotone", "name": "price_rises_with_growth", "output": price,
         "input": lay.scalar_key("tg"), "delta": 0.0025, "sign": 1},
    ]
    # a monotone relation is only a law of *correct* models where it holds for the
    # reference (e.g. growth raises value only while final cash flow is positive)
    ref_cw = reference.compile()
    ref_runs = [ref_cw.run()] + [ref_cw.run(sc) for sc in scenarios]
    from ..grader.grader import _relation_holds

    for rel in relations:
        if rel["type"] == "monotone":
            rel["runs"] = [i for i in range(len(ref_runs))
                           if _relation_holds(ref_cw, rel, {} if i == 0 else scenarios[i - 1], ref_runs[i])]

    labels: Dict[Key, str] = {}
    for ln in spec.lines:
        sheet, r = lay.rows[ln.id]
        for p, name in enumerate(lay.periods):
            labels[lay.key(ln.id, p)] = f"{sheet}!{addr(r, lay.col(p))} ({ln.label} {name})"
    for c in spec.calcs:
        sheet, r, col = lay.calcs[c.id]
        labels[lay.calc_key(c.id)] = f"{sheet}!{addr(r, col)} ({c.label})"
    for i, row in enumerate(gen.grid_keys):
        for j, k in enumerate(row):
            labels[k] = f"{GRID_SHEET}!{addr(k[1], k[2])} (price at WACC row {i + 1}, growth col {j + 1})"

    money_lines = {lay.rows[ln.id] for ln in spec.lines if ln.kind == "money"}
    money_targets = [k for k in targets if any(k[0] == s.casefold() and k[1] == r for s, r in money_lines)]
    money_targets += [k for k in targets if k in {lay.calc_key(c) for c in CALCS}]
    money_targets += [k for k in targets if k[0] == GRID_SHEET.casefold()]

    # ---------------- instructions ------------------------------------------------
    f0, f1 = index_to_col(lay.col(spec.n_hist)), index_to_col(lay.col(lay.n_periods - 1))
    todo = []
    for lid in target_lines:
        ln = spec.line(lid)
        sheet, r = lay.rows[lid]
        todo.append(f"- {sheet}!{f0}{r}:{f1}{r} \"{ln.label}\": {ln.desc}")
    if level["calcs"]:
        for cid in CALCS:
            c = next(x for x in spec.calcs if x.id == cid)
            sheet, r, col = lay.calcs[cid]
            todo.append(f"- {sheet}!{addr(r, col)} \"{c.label}\": {c.desc}")
    if level["grid"]:
        g0, g1 = gen.grid_keys[0][0], gen.grid_keys[-1][-1]
        todo.append(
            f"- {GRID_SHEET}!{addr(g0[1], g0[2])}:{addr(g1[1], g1[2])} share-price sensitivity: each cell is the "
            f"implied share price when WACC = the value in column B of its row and terminal growth = the value "
            f"in row {g0[1] - 1} of its column, everything else unchanged, using exactly the DCF sheet's "
            f"methodology. Write formulas (data tables are not available).")
    context = [f"- {lay.rows[ln.id][0]} row {lay.rows[ln.id][1]} \"{ln.label}\": {ln.desc}"
               for ln in spec.lines if ln.fc is not None and ln.id not in target_lines]
    if not level["calcs"]:
        context += [f"- {lay.calcs[c.id][0]}!{addr(lay.calcs[c.id][1], lay.calcs[c.id][2])} \"{c.label}\": {c.desc}"
                    for c in spec.calcs]
    convention = ("Cash flows are discounted with the mid-year convention (discount period = year number - 0.5); "
                  "the terminal value uses the final year's discount factor."
                  if gen.cfg.mid_year else
                  "Cash flows arrive at year end (discount period = year number); the terminal value uses the final "
                  "year's discount factor.")
    instr = [
        f"You are completing a {spec.title.lower()} (sheets: {', '.join(spec.sheets)}; amounts in $m, share "
        f"price in $). Column {index_to_col(lay.col(0))} is the last actual year; columns {f0}:{f1} are forecasts.",
        "", "TASK: the cells below are empty. Write a formula in every one of them:", *todo, "",
        "RULES:",
        "- Every cell must be a live formula linked to the inputs; the model will be re-calculated with "
        "different input values, so typed numbers will be wrong.",
        "- Do not change any non-empty cell. You may use empty cells for helper calculations.",
        f"- {convention}",
        f"- Allowed functions: {ALLOWED_FUNCTIONS_TEXT}.",
        "", "Methodology of the parts already built:", *(context or ["(none)"]),
        "", "Inputs are on the Assumptions sheet (column C), revenue growth by year in its forecast columns.",
        "", "Use the tools to inspect and edit the workbook. Call submit when you are done.",
    ]
    return Task(
        task_id=f"dcf-d{difficulty}-s{seed}", family="dcf", difficulty=difficulty, seed=seed,
        instructions="\n".join(instr), initial=initial, reference=reference, inputs=inputs,
        target_keys=targets, locked=locked_cells(initial), scenarios=scenarios, identities=ids,
        money_inputs=[i.key for i in inputs if i.kind == "money"], money_targets=money_targets,
        labels=labels, relations=relations, max_steps=level["max_steps"],
        meta={"scale_factor": SCALE_FACTOR, "sector": gen.sector.name, "layout": lay, "spec": spec},
    )
