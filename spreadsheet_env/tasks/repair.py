"""Task family ``repair``: find and fix injected errors in a three-statement model.

The agent gets the full methodology memo (the model's documentation) and a
workbook in which some formulas deviate from it. Bugs are drawn from the
evidence-weighted operators in ``mutations.py``; at higher levels some are
*latent* (values correct today, wrong once an input changes), the number of
bugs is not disclosed, and a share of tasks contain no bug at all (a canary:
the right behaviour is to change nothing material).

Grading: every formula cell of the model must match the reference under every
scenario (so collateral damage to correct cells is caught), inputs must be
untouched, and the accounting identities must hold.
"""

from __future__ import annotations

import random
from dataclasses import replace

from ..engine.refs import addr
from ..model.spec import render
from ..model.three_statement import ModelConfig, generate_model
from .base import Task
from .common import (
    ALLOWED_FUNCTIONS_TEXT, SCALE_FACTOR, balance_fixups, forbidden_dep_rules, identity_checks, inputs_for, labels_for,
    locked_cells, model_map, money_keys, scenarios_for,
)
from .mutations import apply_bugs, sample_bugs

REPAIR_LEVELS = {
    1: dict(cfg=ModelConfig(n_forecast=3, single_sheet=True, tax_floor=False, dividends=False,
                            inventory=False), bugs=(1, 1), latent=0, hint="rows", canary=0.0,
            row_p=0.3, max_steps=30),
    2: dict(cfg=ModelConfig(n_forecast=4, tax_floor=True, dividends=True), bugs=(1, 2), latent=0,
            hint="count", canary=0.0, row_p=0.3, max_steps=40),
    3: dict(cfg=ModelConfig(n_forecast=5, revolver=True), bugs=(2, 2), latent=1, hint="count",
            canary=0.0, row_p=0.35, max_steps=60),
    4: dict(cfg=ModelConfig(n_forecast=5, revolver=True, interest_income=True), bugs=(2, 3), latent=1,
            hint="none", canary=0.15, row_p=0.4, max_steps=80),
    5: dict(cfg=ModelConfig(n_forecast=6, revolver=True, interest_income=True, average_balances=True),
            bugs=(3, 4), latent=2, hint="none", canary=0.15, row_p=0.5, max_steps=100),
}


def repair_task(seed: int, difficulty: int = 2, force_canary: bool | None = None) -> Task:
    level = REPAIR_LEVELS[difficulty]
    rng = random.Random(f"repair:{difficulty}:{seed}")
    gm = generate_model(rng, replace(level["cfg"]))
    spec = gm.spec
    reference, lay = render(spec)

    targets = [k for k, v in reference.snapshot().items() if isinstance(v, str) and v.startswith("=")]
    inputs = inputs_for(gm, lay)
    fixups = balance_fixups(gm, lay)
    scenarios = scenarios_for(reference, inputs, fixups, targets, seed)

    canary = (rng.random() < level["canary"]) if force_canary is None else force_canary
    bugs = []
    if not canary:
        n = rng.randint(*level["bugs"])
        bugs = sample_bugs(reference, spec, lay, targets, scenarios, rng, n,
                           min_latent=min(level["latent"], n), row_scope_p=level["row_p"])
    initial = apply_bugs(reference, bugs)
    labels = labels_for(spec, lay)

    memo = "\n".join(
        f"- {lay.rows[ln.id][0]} row {lay.rows[ln.id][1]} \"{ln.label}\": {ln.desc}"
        for ln in spec.lines if ln.fc is not None
    )
    hint = level["hint"]
    if hint == "rows" and bugs:
        rows = sorted({lay.row_label(m.line) + f" ({spec.line(m.line).label})" for m in bugs})
        hint_text = (f"A reviewer found {len(bugs)} error(s) in the forecast formulas, located in: "
                     + "; ".join(rows) + ".")
    elif hint == "count" and bugs:
        hint_text = (f"A reviewer found exactly {len(bugs)} error(s) in the forecast formulas "
                     "(an error may affect one cell or a whole row).")
    else:
        hint_text = ("The model may contain errors in its forecast formulas, or it may be correct. "
                     "Fix every formula that deviates from the methodology; if the model is correct, "
                     "do not change it.")
    instr = [
        f"You are reviewing a {spec.title.lower()} (sheets: {', '.join(spec.sheets)}; amounts in "
        f"{spec.currency}). Historical columns are actuals; forecast columns are formulas.",
        "",
        "TASK: " + hint_text,
        "",
        "RULES:",
        "- The methodology below is authoritative. A formula is an error if it deviates from it.",
        "- Do not change inputs, actuals or labels. Fix formulas only; keep them live (no typed numbers): "
        "the model will be re-calculated with different input values.",
        "- Sign convention: income-statement costs are positive numbers that are subtracted; "
        "cash outflows on the cash flow statement are negative.",
        f"- Allowed functions: {ALLOWED_FUNCTIONS_TEXT}.",
    ]
    if spec.iterative:
        instr.append("- Iterative calculation is enabled (circular references through average balances "
                     "are intended).")
    instr += ["", "METHODOLOGY (forecast formulas):", memo, "", "MODEL MAP:", model_map(spec, lay), "",
              "Use the tools to inspect and edit the workbook. Call submit when you are done "
              "(you may list the cells you fixed in the notes)."]

    label = lambda k: labels.get(k) or f"{k[0]}!{addr(k[1], k[2])}"  # noqa: E731
    return Task(
        task_id=f"repair-d{difficulty}-s{seed}",
        family="repair",
        difficulty=difficulty,
        seed=seed,
        instructions="\n".join(instr),
        initial=initial,
        reference=reference,
        inputs=inputs,
        target_keys=targets,
        locked=locked_cells(initial, editable=targets),
        scenarios=scenarios,
        identities=identity_checks(gm, lay),
        money_inputs=[i.key for i in inputs if i.kind == "money"],
        money_targets=money_keys(spec, lay, targets),
        fixups=fixups,
        forbidden_deps=forbidden_dep_rules(gm, lay),
        labels=labels,
        bugs=[m.to_dict(label) for m in bugs],
        expect_no_change=canary,
        max_steps=level["max_steps"],
        meta={"scale_factor": SCALE_FACTOR, "sector": gm.sector.name, "layout": lay, "spec": spec,
              "n_bugs": len(bugs), "n_latent": sum(m.effect == "latent" for m in bugs),
              "bug_cells": sorted({k for m in bugs for k in m.cells})},
    )
