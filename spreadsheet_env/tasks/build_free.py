"""Task family ``build_free``: build a whole model from scratch in any layout.

The agent gets locked input sheets (``Assumptions`` and ``Actuals``), an empty
``Model`` sheet to lay out as it likes, and an ``Outputs`` sheet: the
contract, a fixed grid of labelled cells that must link to the agent's model.

Because the layout is free, grading happens through the contract only:

* golden match of every Outputs cell under perturbed inputs;
* reference-free identities among the outputs (assets = L&E, BS cash = CFS
  ending cash, retained-earnings roll-forward);
* structure: every output must depend on the inputs its logic requires.

Known limitation (documented in the README): the grader cannot see the
agent's internal line items, so a balancing plug that is numerically identical
to the correct logic cannot be told apart from it. A plug that *hides* an
error still fails the golden and identity checks.
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import Dict, List

from ..engine.refs import addr, index_to_col
from ..engine.workbook import Key, Workbook
from ..model.spec import FIRST_PERIOD_COL, HEADER_ROW, render
from ..model.three_statement import ModelConfig, generate_model
from .base import Fixup, IdentityCheck, InputInfo, Task
from .common import ALLOWED_FUNCTIONS_TEXT, SCALE_FACTOR, scenarios_for

IS_OUT = [("rev", "Revenue"), ("ebitda", "EBITDA"), ("ebit", "EBIT"), ("ni", "Net income")]
FULL_OUT = IS_OUT + [
    ("cash", "Cash (balance sheet)"), ("ta", "Total assets"), ("debt", "Term debt"),
    ("re", "Retained earnings"), ("tle", "Total liabilities & equity"),
    ("cfo", "Cash flow from operations"), ("cf_div", "Dividends paid (negative)"),
    ("cf_end", "Ending cash (cash flow statement)"),
]

FREE_LEVELS = {
    1: dict(cfg=ModelConfig(n_forecast=3, single_sheet=True, tax_floor=False, dividends=False, inventory=False),
            outputs=IS_OUT, max_steps=40),
    2: dict(cfg=ModelConfig(n_forecast=4, single_sheet=True, dividends=True), outputs=FULL_OUT, max_steps=80),
    3: dict(cfg=ModelConfig(n_forecast=5, single_sheet=True, revolver=True), outputs=FULL_OUT + [("revolver", "Revolver")],
            max_steps=100),
    4: dict(cfg=ModelConfig(n_forecast=5, single_sheet=True, revolver=True, interest_income=True),
            outputs=FULL_OUT + [("revolver", "Revolver")], max_steps=120),
    5: dict(cfg=ModelConfig(n_forecast=6, single_sheet=True, revolver=True, interest_income=True,
                            average_balances=True), outputs=FULL_OUT + [("revolver", "Revolver")], max_steps=150),
}


def build_free_task(seed: int, difficulty: int = 2) -> Task:
    level = FREE_LEVELS[difficulty]
    rng = random.Random(f"build_free:{difficulty}:{seed}")
    gm = generate_model(rng, replace(level["cfg"]))
    spec = gm.spec
    model_wb, lay = render(spec)  # sheets: Assumptions, Model
    n_p, n_h = lay.n_periods, spec.n_hist
    outputs = [(lid, lab) for lid, lab in level["outputs"] if lid in lay.rows]
    if not gm.cfg.dividends:
        outputs = [o for o in outputs if o[0] != "cf_div"]

    # ---------------- Actuals sheet (historical inputs) -------------------------
    ref = Workbook(iterative=spec.iterative)
    for s in ("Assumptions", "Actuals", "Model", "Outputs"):
        ref.add_sheet(s)
    for _, r, c, raw in model_wb.cells("Assumptions"):
        ref.set_rc("Assumptions", r, c, raw)
    ref.set_rc("Actuals", 1, 1, f"{spec.title} - historical actuals ({spec.currency})")
    ref.set_rc("Actuals", HEADER_ROW, 1, "Line item")
    for p in range(n_h):
        ref.set_rc("Actuals", HEADER_ROW, FIRST_PERIOD_COL + p, lay.periods[p])
    actual_row: Dict[str, int] = {}
    r = 4
    for ln in spec.lines:
        if ln.hist == "input" and ln.history is not None and ln.sheet != "Assumptions":
            ref.set_rc("Actuals", r, 1, ln.label)
            for p, v in enumerate(ln.history):
                ref.set_rc("Actuals", r, FIRST_PERIOD_COL + p, float(v))
            actual_row[ln.id] = r
            r += 1
    # ---------------- reference model on "Model", linked to Actuals -------------
    for _, rr, c, raw in model_wb.cells("Model"):
        ref.set_rc("Model", rr, c, raw)
    for lid, ar in actual_row.items():
        _, mr = lay.rows[lid]
        for p in range(n_h):
            ref.set_rc("Model", mr, lay.col(p), f"=Actuals!{addr(ar, FIRST_PERIOD_COL + p)}")
    # ---------------- Outputs contract ------------------------------------------
    ref.set_rc("Outputs", 1, 1, "OUTPUTS - link every cell to your model (forecast years)")
    ref.set_rc("Outputs", HEADER_ROW, 1, "Output")
    fc_cols = [lay.col(p) for p in lay.forecast_indices]
    for p in lay.forecast_indices:
        ref.set_rc("Outputs", HEADER_ROW, lay.col(p), lay.periods[p])
    out_row: Dict[str, int] = {}
    for i, (lid, lab) in enumerate(outputs):
        orow = 4 + i
        out_row[lid] = orow
        ref.set_rc("Outputs", orow, 1, lab)
        _, mr = lay.rows[lid]
        for c in fc_cols:
            ref.set_rc("Outputs", orow, c, f"=Model!{addr(mr, c)}")

    initial = Workbook(iterative=spec.iterative)
    for s in ref.sheet_names:
        initial.add_sheet(s)
    for sheet, rr, c, raw in ref.cells():
        if sheet in ("Assumptions", "Actuals") or (sheet == "Outputs" and (c < FIRST_PERIOD_COL or rr <= HEADER_ROW)):
            initial.set_rc(sheet, rr, c, raw)
    initial.set_rc("Model", 1, 1, "Build your model here (any layout).")

    targets: List[Key] = [("outputs", out_row[lid], c) for lid, _ in outputs for c in fc_cols]

    # ---------------- inputs, fixups, scenarios ---------------------------------
    scale = float(spec.line("rev").history[-1])
    kinds = {"tax_rate": "tax", "payout": "payout", "int_rate": "interest", "rev_rate": "interest",
             "cash_rate": "interest"}
    inputs: List[InputInfo] = []
    for s in spec.scalars:
        inputs.append(InputInfo(lay.scalar_key(s.id), kinds.get(s.id, s.kind), float(s.value), scale, lo=0.0))
    for ln in spec.lines:
        if ln.is_input_series and ln.forecast is not None:
            for i, v in enumerate(ln.forecast):
                inputs.append(InputInfo(lay.key(ln.id, n_h + i), "growth", float(v), scale))
    akey = lambda lid, p: ("actuals", actual_row[lid], FIRST_PERIOD_COL + p)  # noqa: E731
    for lid in actual_row:
        if lid == "re":
            continue
        for p in range(n_h):
            inputs.append(InputInfo(akey(lid, p), "money", float(spec.line(lid).history[p]), scale, lo=0.0))
    assets = [i for i in ("cash", "ar", "inv", "ppe") if i in actual_row]
    liabs = [i for i in ("ap", "debt", "revolver") if i in actual_row]
    fixups = [Fixup(akey("re", p), [(1.0, akey(a, p)) for a in assets] + [(-1.0, akey(b, p)) for b in liabs]
                    + [(-1.0, akey("cs", p))]) for p in range(n_h)]
    all_formulas = [k for k, v in ref.snapshot().items() if isinstance(v, str) and v.startswith("=")]
    scenarios = scenarios_for(ref, inputs, fixups, all_formulas, seed)

    # ---------------- reference-free identities on the outputs -------------------
    ok = lambda lid, p: ("outputs", out_row[lid], lay.col(p))  # noqa: E731
    fcs = list(lay.forecast_indices)
    ids = []
    if {"ta", "tle"} <= out_row.keys():
        ids.append(IdentityCheck("balance_sheet_balances", "total assets = total L&E",
                                 [[(1, ok("ta", p)), (-1, ok("tle", p))] for p in fcs]))
    if {"cash", "cf_end"} <= out_row.keys():
        ids.append(IdentityCheck("cash_ties_to_cfs", "BS cash = CFS ending cash",
                                 [[(1, ok("cash", p)), (-1, ok("cf_end", p))] for p in fcs]))
    if {"re", "ni"} <= out_row.keys():
        per = []
        for p in fcs[1:]:
            t = [(1, ok("re", p)), (-1, ok("re", p - 1)), (-1, ok("ni", p))]
            if "cf_div" in out_row:
                t.append((-1, ok("cf_div", p)))
            per.append(t)
        ids.append(IdentityCheck("re_rollforward", "RE = prior RE + net income + dividend cash flow", per))

    labels = {("outputs", out_row[lid], c): f"Outputs!{addr(out_row[lid], c)} ({lab} {lay.periods[c - FIRST_PERIOD_COL]})"
              for lid, lab in outputs for c in fc_cols}
    memo = "\n".join(f"- {ln.label}: {ln.desc}" for ln in spec.lines if ln.fc is not None and ln.kind != "check")
    f0, f1 = index_to_col(fc_cols[0]), index_to_col(fc_cols[-1])
    a_map = "; ".join(f"row {ar} {spec.line(lid).label}" for lid, ar in actual_row.items())
    instr = [
        f"Build a {spec.title.lower()} from scratch (amounts in {spec.currency}).",
        "",
        "INPUTS (locked, do not change):",
        f"- Assumptions: drivers in column C (rows 4+); revenue growth by forecast year in row "
        f"{lay.rows['g_rev'][1]}, columns {f0}:{f1}.",
        f"- Actuals: historical years {', '.join(lay.periods[:n_h])} in columns "
        f"{index_to_col(FIRST_PERIOD_COL)}:{index_to_col(FIRST_PERIOD_COL + n_h - 1)}: {a_map}.",
        "",
        f"TASK: build the forecast for {', '.join(lay.periods[n_h:])} on the Model sheet in any layout you like "
        f"(you may use any empty cells of Model), then fill the Outputs sheet: every cell of Outputs!{f0}4:{f1}"
        f"{3 + len(outputs)} must be a formula linking to your model (output name in column A, forecast year in "
        f"row {HEADER_ROW}). Use the same column for the same year everywhere.",
        "",
        "METHODOLOGY (follow exactly):", memo,
        "",
        "RULES:",
        "- Live formulas only: the model will be re-calculated with different inputs.",
        "- Sign convention: income-statement costs are positive and subtracted; cash outflows on the cash flow "
        "statement are negative. Prior-year values come from the Actuals sheet for the first forecast year.",
        f"- Allowed functions: {ALLOWED_FUNCTIONS_TEXT}.",
    ]
    if spec.iterative:
        instr.append("- Iterative calculation is enabled (the average-balance interest makes the model circular).")
    instr += ["", "Use the tools to build the model. Call submit when you are done."]
    from ..grader.grader import MAX_EXTRA_CELLS  # noqa: F401  (free builds write many cells)

    locked = {k: v for k, v in initial.snapshot().items()}
    return Task(
        task_id=f"build_free-d{difficulty}-s{seed}", family="build_free", difficulty=difficulty, seed=seed,
        instructions="\n".join(instr), initial=initial, reference=ref, inputs=inputs, target_keys=targets,
        locked=locked, scenarios=scenarios, identities=ids,
        money_inputs=[i.key for i in inputs if i.kind == "money"],
        money_targets=list(targets), fixups=fixups, labels=labels, max_steps=level["max_steps"],
        meta={"scale_factor": SCALE_FACTOR, "sector": gm.sector.name, "layout": lay, "spec": spec,
              "outputs": outputs, "model_layout_note": "reference model lives on Model sheet"},
    )
