"""Task family ``build``: complete the forecast formulas of a three-statement model.

The agent receives the workbook with some forecast rows blanked and the
model's methodology memo for those rows. It must write live formulas: the
grader re-runs the model under perturbed inputs and checks every blanked cell
against the hidden reference, plus the accounting identities.
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import List

from ..model.spec import render
from ..model.three_statement import ModelConfig, generate_model
from .base import Task
from .common import (
    ALLOWED_FUNCTIONS_TEXT, SCALE_FACTOR, balance_fixups, forbidden_dep_rules, identity_checks, inputs_for,
    labels_for, locked_cells, model_map, money_keys, scenarios_for,
)

IS_LINES = ["rev", "cogs", "gp", "sga", "ebitda", "da", "ebit", "int_exp", "int_inc", "ebt", "tax", "ni"]
BS_LINES = ["cash", "ar", "inv", "tca", "ppe", "ta", "ap", "debt", "revolver", "tl", "cs", "re",
            "te", "tle", "check"]
CFS_LINES = ["cf_ni", "cf_da", "cf_ar", "cf_inv", "cf_ap", "cfo", "cf_capex", "cfi", "cf_debt",
             "cf_div", "cf_rev", "cff", "cf_net", "cf_beg", "cf_end", "cash_pre"]

BUILD_LEVELS = {
    1: dict(cfg=ModelConfig(n_forecast=3, single_sheet=True, tax_floor=False, dividends=False,
                            inventory=False), scope="some_is", n_lines=(2, 3), map=True, max_steps=30),
    2: dict(cfg=ModelConfig(n_forecast=4, tax_floor=True, dividends=True), scope="some_any",
            n_lines=(4, 6), map=True, max_steps=40),
    3: dict(cfg=ModelConfig(n_forecast=5, revolver=True), scope="statement", n_lines=None, map=True,
            max_steps=60),
    4: dict(cfg=ModelConfig(n_forecast=5, revolver=True, interest_income=True), scope="all",
            n_lines=None, map=True, max_steps=90),
    5: dict(cfg=ModelConfig(n_forecast=6, revolver=True, interest_income=True, average_balances=True),
            scope="all", n_lines=None, map=False, max_steps=120),
}


def _choose_lines(rng: random.Random, spec, level: dict) -> List[str]:
    formula_lines = [ln.id for ln in spec.lines if ln.fc is not None]
    scope = level["scope"]
    if scope == "some_is":
        pool = [i for i in IS_LINES if i in formula_lines]
        return sorted(rng.sample(pool, rng.randint(*level["n_lines"])), key=formula_lines.index)
    if scope == "some_any":
        return sorted(rng.sample(formula_lines, rng.randint(*level["n_lines"])), key=formula_lines.index)
    if scope == "statement":
        group = rng.choice([IS_LINES, BS_LINES, CFS_LINES])
        return [i for i in formula_lines if i in group]
    return list(formula_lines)


def build_task(seed: int, difficulty: int = 2) -> Task:
    level = BUILD_LEVELS[difficulty]
    rng = random.Random(f"build:{difficulty}:{seed}")
    gm = generate_model(rng, replace(level["cfg"]))
    spec = gm.spec
    reference, lay = render(spec, None)
    chosen = _choose_lines(rng, spec, level)

    initial = reference.copy()
    targets = []
    for lid in chosen:
        for p in lay.forecast_indices:
            k = lay.key(lid, p)
            targets.append(k)
            initial.set_rc(lay.rows[lid][0], k[1], k[2], None)

    inputs = inputs_for(gm, lay)
    fixups = balance_fixups(gm, lay)
    all_formula_targets = [k for k in reference.snapshot() if reference.is_formula(reference.sheet_name(k[0]), k[1], k[2])]
    scenarios = scenarios_for(reference, inputs, fixups, all_formula_targets, seed)

    from ..engine.refs import index_to_col

    f0 = index_to_col(lay.col(spec.n_hist))
    f1 = index_to_col(lay.col(lay.n_periods - 1))
    rows_text = []
    for lid in chosen:
        ln = spec.line(lid)
        sheet, r = lay.rows[lid]
        rows_text.append(f"- {sheet}!{f0}{r}:{f1}{r} \"{ln.label}\": {ln.desc}")
    other = [ln for ln in spec.lines if ln.fc is not None and ln.id not in chosen]
    context = "\n".join(
        f"- {lay.rows[ln.id][0]} row {lay.rows[ln.id][1]} \"{ln.label}\": {ln.desc}" for ln in other
    )
    instr = [
        f"You are completing a {spec.title.lower()} in a spreadsheet workbook "
        f"(sheets: {', '.join(spec.sheets)}). Amounts are in {spec.currency}.",
        "",
        "TASK: the forecast cells of the rows below are empty. Write a formula in every one of them, "
        "following the model's methodology:",
        *rows_text,
        "",
        "RULES:",
        "- Every forecast cell must be a live formula that links to the inputs and other lines. "
        "The model will be re-calculated with different input values, so typed numbers will be wrong.",
        "- Do not change any non-empty cell (inputs, actuals, labels, existing formulas). You may use "
        "empty cells for helper calculations.",
        "- Sign convention: income-statement costs are positive numbers that are subtracted; "
        "cash outflows on the cash flow statement are negative.",
        f"- Allowed functions: {ALLOWED_FUNCTIONS_TEXT}.",
    ]
    if spec.iterative:
        instr.append("- Iterative calculation is enabled in this workbook (circular references are "
                     "intended where the methodology requires average balances).")
    instr += ["", "Methodology of the rest of the model (already built):", context or "(none)"]
    if level["map"]:
        instr += ["", "MODEL MAP:", model_map(spec, lay)]
    instr += ["", "Use the tools to inspect and edit the workbook. Call submit when you are done."]

    labels = labels_for(spec, lay)
    return Task(
        task_id=f"build-d{difficulty}-s{seed}",
        family="build",
        difficulty=difficulty,
        seed=seed,
        instructions="\n".join(instr),
        initial=initial,
        reference=reference,
        inputs=inputs,
        target_keys=targets,
        locked=locked_cells(initial),
        scenarios=scenarios,
        identities=identity_checks(gm, lay),
        money_inputs=[i.key for i in inputs if i.kind == "money"],
        money_targets=money_keys(spec, lay, targets),
        fixups=fixups,
        forbidden_deps=forbidden_dep_rules(gm, lay),
        labels=labels,
        max_steps=level["max_steps"],
        meta={"scale_factor": SCALE_FACTOR, "sector": gm.sector.name, "lines": chosen,
              "layout": lay, "spec": spec},
    )
