"""Generic machinery for the frontier task tier.

A domain generator (LBO, fund waterfall, project finance, SaaS cohorts, ABS ...)
returns a ``Bundle``: the model spec (single source of truth), a business-
language term sheet describing the same logic, the accounting identities and
monotone (metamorphic) relations any correct model satisfies, input ranges for
perturbation, and the output contract for free-layout builds.

From a bundle this module derives three task variants, each graded by the same
seven-oracle grader:

``build``   fixed layout, forecast formula rows empty. Spec = per-row formula
            memo (``spec="memo"``) or only the term sheet (``spec="brief"``:
            the agent must turn business terms into formulas).
``repair``  full model with injected bugs (evidence-weighted operators), spec =
            term sheet only, number of bugs not disclosed, no-bug canaries.
``free``    empty Model sheet, any layout, Outputs contract; spec = term sheet.

All inputs of frontier models live on the ``Assumptions`` sheet and the model
on a single ``Model`` sheet, so free-layout tasks need no data re-plumbing.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union

from ..engine.refs import addr, index_to_col
from ..engine.workbook import Key, Workbook
from ..model.spec import FIRST_PERIOD_COL, HEADER_ROW, Layout, ModelSpec, render
from ..task import Fixup, IdentityCheck, InputInfo, Task
from ..tasks.common import ALLOWED_FUNCTIONS_TEXT, SCALE_FACTOR, locked_cells, scenarios_for

Off = Union[int, str]  # relative offset (int) for per-period identities; "last"/"first"/int for "once"


@dataclass
class IdSpec:
    """Reference-free identity ``sum(sign * value) == 0``.

    ``when="forecast"``: checked in every forecast period, ``off`` relative.
    ``when="forecast2"``: every forecast period except the first.
    ``when="once"``: checked once; ``off`` is an absolute period ("first",
    "last" or an int) for lines and ignored for single-cell calcs.
    """

    name: str
    desc: str
    terms: List[Tuple[float, str, Off]]
    when: str = "forecast"


@dataclass
class MonoSpec:
    """Metamorphic relation: raising ``input`` by ``delta`` moves ``output``
    in direction ``sign``. Only checked in scenarios where it holds for the
    reference (it is a law of correct models only there)."""

    name: str
    output: str  # calc id, or "line@last"
    input: str  # scalar id
    delta: float
    sign: int


@dataclass
class Bundle:
    domain: str
    noun: str  # "leveraged buyout model", used in instructions
    spec: ModelSpec
    term_sheet: str
    conventions: List[str]
    identities: List[IdSpec] = field(default_factory=list)
    monotone: List[MonoSpec] = field(default_factory=list)
    kinds: Dict[str, Tuple[str, Optional[float], Optional[float]]] = field(default_factory=dict)
    fixups: Optional[Callable[[Layout], List[Fixup]]] = None
    forbidden: List[Tuple[List[str], List[str], str]] = field(default_factory=list)
    outputs: List[Tuple[str, str]] = field(default_factory=list)  # (line or calc id, label)
    scale: float = 100.0
    # input series whose zero entries are structural (e.g. construction capex in operating
    # years): those cells are never perturbed, the non-zero ones are
    fixed_when_zero: Tuple[str, ...] = ()
    # input series given as an ascending grid (exit values): scenarios keep them ascending
    ascending: Tuple[str, ...] = ()
    # groups of scalars that must stay in ascending order (pricing-grid thresholds,
    # grid rates): each tuple lists scalar ids in ascending order of value, in the
    # order they are declared in the spec
    ascending_scalars: List[Tuple[str, ...]] = field(default_factory=list)
    level: int = 1
    meta: Dict[str, object] = field(default_factory=dict)


# --------------------------------------------------------------------------
# grading metadata
# --------------------------------------------------------------------------

def _key(lay: Layout, ident: str, period: Optional[int]) -> Key:
    if ident in lay.calcs:
        return lay.calc_key(ident)
    if ident in lay.scalars:
        return lay.scalar_key(ident)
    return lay.key(ident, period)


def _abs_period(lay: Layout, off: Off) -> int:
    if off == "last":
        return lay.n_periods - 1
    if off == "first":
        return lay.n_hist
    return int(off)


def identity_checks(b: Bundle, lay: Layout) -> List[IdentityCheck]:
    out = []
    fc = list(lay.forecast_indices)
    for idn in b.identities:
        per = []
        if idn.when == "once":
            per.append([(s, _key(lay, i, _abs_period(lay, o) if i in lay.rows else None)) for s, i, o in idn.terms])
        else:
            periods = fc[1:] if idn.when == "forecast2" else fc
            for p in periods:
                per.append([(s, _key(lay, i, p + int(o))) for s, i, o in idn.terms])
        out.append(IdentityCheck(idn.name, idn.desc, per))
    return out


def relations_for(b: Bundle, lay: Layout, reference: Workbook, scenarios) -> List[dict]:
    from ..grader.grader import _relation_holds

    rels = []
    for m in b.monotone:
        if m.output.endswith("@last"):
            out_key = lay.key(m.output[:-5], lay.n_periods - 1)
        else:
            out_key = _key(lay, m.output, None)
        rels.append({"type": "monotone", "name": m.name, "output": out_key,
                     "input": lay.scalar_key(m.input), "delta": m.delta, "sign": m.sign})
    if rels:
        cw = reference.compile()
        runs = [cw.run()] + [cw.run(sc) for sc in scenarios]
        for rel in rels:
            rel["runs"] = [i for i in range(len(runs))
                           if _relation_holds(cw, rel, {} if i == 0 else scenarios[i - 1], runs[i])]
    return [r for r in rels if r.get("runs")]


def inputs_for(b: Bundle, lay: Layout) -> List[InputInfo]:
    spec = b.spec
    out = []
    group_of = {sid: f"scalars{gi}" for gi, grp in enumerate(b.ascending_scalars) for sid in grp}
    for grp in b.ascending_scalars:
        vals = [next(s.value for s in spec.scalars if s.id == sid) for sid in grp]
        order = [s.id for s in spec.scalars if s.id in grp]
        if vals != sorted(vals) or order != list(grp):
            raise ValueError(f"ascending scalar group {grp} must be declared in ascending order")
    for s in spec.scalars:
        kind, lo, hi = b.kinds.get(s.id, (s.kind, 0.0 if s.kind != "money" else 0.0, None))
        out.append(InputInfo(lay.scalar_key(s.id), kind, float(s.value), b.scale, lo=lo, hi=hi,
                             group=group_of.get(s.id)))
    for ln in spec.lines:
        kind, lo, hi = b.kinds.get(ln.id, (None, None, None))
        if ln.is_input_series and ln.forecast is not None:
            k = kind or ("growth" if ln.kind == "rate" else ln.kind)
            for i, v in enumerate(ln.forecast):
                kk = "fixed" if (ln.id in b.fixed_when_zero and v == 0) else k
                out.append(InputInfo(lay.key(ln.id, spec.n_hist + i), kk, float(v), b.scale, lo=lo, hi=hi,
                                     group=ln.id if ln.id in b.ascending else None))
        if ln.hist == "input" and ln.history is not None:
            k = kind or ln.kind
            for p, v in enumerate(ln.history):
                # a zero opening balance of a model corkscrew (undrawn revolver, empty reserve account, no
                # carried-forward shortfall) is a structural fact stated in the term sheet, not an assumption:
                # perturbing it builds states the spec rules out (HACK_LOG: frontier false positives)
                kk = "fixed" if (ln.fc is not None and v == 0) else k
                out.append(InputInfo(lay.key(ln.id, p), kk, float(v), b.scale,
                                     lo=lo if lo is not None else (0.0 if kk == "money" else None), hi=hi))
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
    for c in spec.calcs:
        sheet, r, col = lay.calcs[c.id]
        out[lay.calc_key(c.id)] = f"{sheet}!{addr(r, col)} ({c.label})"
    return out


def money_keys(spec: ModelSpec, lay: Layout, keys: Sequence[Key]) -> List[Key]:
    money_rows = {(s.casefold(), r) for ln in spec.lines if ln.kind == "money" for s, r in [lay.rows[ln.id]]}
    money_calcs = {lay.calc_key(c.id) for c in spec.calcs if c.kind == "money"}
    return [k for k in keys if (k[0], k[1]) in money_rows or k in money_calcs]


def forbidden_rules(b: Bundle, lay: Layout):
    out = []
    for srcs, bans, why in b.forbidden:
        a = [lay.key(i, p) for i in srcs if i in lay.rows for p in lay.forecast_indices]
        a += [lay.calc_key(i) for i in srcs if i in lay.calcs]
        z = [lay.key(i, p) for i in bans if i in lay.rows for p in range(lay.n_periods)]
        z += [lay.calc_key(i) for i in bans if i in lay.calcs]
        out.append((a, z, why))
    return out


def formula_keys(wb: Workbook) -> List[Key]:
    return [k for k, v in wb.snapshot().items() if isinstance(v, str) and v.startswith("=")]


# --------------------------------------------------------------------------
# instruction text
# --------------------------------------------------------------------------

def _rows_memo(spec: ModelSpec, lay: Layout, ids: Sequence[str]) -> List[str]:
    f0, f1 = index_to_col(lay.col(spec.n_hist)), index_to_col(lay.col(lay.n_periods - 1))
    out = []
    for i in ids:
        if i in lay.rows:
            ln = spec.line(i)
            sheet, r = lay.rows[i]
            out.append(f"- {sheet}!{f0}{r}:{f1}{r} \"{ln.label}\": {ln.desc}")
        else:
            c = next(x for x in spec.calcs if x.id == i)
            sheet, r, col = lay.calcs[i]
            out.append(f"- {sheet}!{addr(r, col)} \"{c.label}\": {c.desc}")
    return out


def _rows_labels(spec: ModelSpec, lay: Layout, ids: Sequence[str]) -> List[str]:
    f0, f1 = index_to_col(lay.col(spec.n_hist)), index_to_col(lay.col(lay.n_periods - 1))
    out = []
    for i in ids:
        if i in lay.rows:
            sheet, r = lay.rows[i]
            out.append(f"- {sheet}!{f0}{r}:{f1}{r} \"{spec.line(i).label}\"")
        else:
            sheet, r, col = lay.calcs[i]
            out.append(f"- {sheet}!{addr(r, col)} \"{next(x for x in spec.calcs if x.id == i).label}\"")
    return out


def _common_rules(b: Bundle) -> List[str]:
    rules = [
        "- Every formula must be live and linked to the inputs: the model will be re-calculated with different "
        "input values, so typed numbers will be wrong.",
        "- Do not change inputs (the Assumptions sheet and any given values), labels or headers.",
        f"- Allowed functions: {ALLOWED_FUNCTIONS_TEXT}.",
    ]
    if b.spec.iterative:
        rules.append("- Iterative calculation is enabled in this workbook (the circularity described in the "
                     "terms is intended).")
    return rules


def _assumption_map(spec: ModelSpec, lay: Layout) -> str:
    parts = []
    for s in spec.scalars:
        sheet, r, c = lay.scalars[s.id]
        parts.append(f"{addr(r, c)} {s.label}")
    series = [ln for ln in spec.lines if ln.sheet == "Assumptions"]
    for ln in series:
        sheet, r = lay.rows[ln.id]
        f0 = index_to_col(lay.col(spec.n_hist))
        f1 = index_to_col(lay.col(lay.n_periods - 1))
        parts.append(f"row {r} {ln.label} ({f0}:{f1})")
    return "Assumptions sheet: " + "; ".join(parts)


# --------------------------------------------------------------------------
# task builders
# --------------------------------------------------------------------------

def _base_task_fields(b: Bundle, reference: Workbook, lay: Layout, targets, seed: int):
    inputs = inputs_for(b, lay)
    fixups = b.fixups(lay) if b.fixups else []
    scenarios = scenarios_for(reference, inputs, fixups, formula_keys(reference), seed)
    return dict(
        inputs=inputs, fixups=fixups, scenarios=scenarios,
        identities=identity_checks(b, lay),
        relations=relations_for(b, lay, reference, scenarios),
        money_inputs=[i.key for i in inputs if i.kind == "money"],
        money_targets=money_keys(b.spec, lay, targets),
        forbidden_deps=forbidden_rules(b, lay),
        labels=labels_for(b.spec, lay),
    )


def formula_ids(spec: ModelSpec) -> List[str]:
    return [ln.id for ln in spec.lines if ln.fc is not None] + [c.id for c in spec.calcs]


def build_task(b: Bundle, family: str, seed: int, difficulty: int, spec_style: str, max_steps: int) -> Task:
    spec = b.spec
    reference, lay = render(spec)
    ids = formula_ids(spec)
    initial = reference.copy()
    targets: List[Key] = []
    for i in ids:
        if i in lay.rows:
            for p in lay.forecast_indices:
                k = lay.key(i, p)
                targets.append(k)
                initial.set_rc(lay.rows[i][0], k[1], k[2], None)
        else:
            k = lay.calc_key(i)
            targets.append(k)
            initial.set_rc(lay.calcs[i][0], k[1], k[2], None)
    fields = _base_task_fields(b, reference, lay, targets, seed)
    f0, f1 = index_to_col(lay.col(spec.n_hist)), index_to_col(lay.col(lay.n_periods - 1))
    instr = [f"You are building a {b.noun} in a spreadsheet (sheets: {', '.join(spec.sheets)}; amounts in "
             f"{spec.currency}). Column {index_to_col(lay.col(0))} holds the starting point, columns {f0}:{f1} "
             f"the projection ({', '.join(lay.periods[spec.n_hist:])})."]
    if spec_style == "memo":
        instr += ["", "TASK: the cells below are empty. Write a formula in every one, following the methodology:",
                  *_rows_memo(spec, lay, ids)]
    else:
        instr += ["", "TASK: the cells below are empty. Write a formula in every one so that the model implements "
                  "the TERMS below exactly. Work out each row's logic from the terms and the row labels.",
                  *_rows_labels(spec, lay, ids), "", "TERMS:", b.term_sheet]
    instr += ["", "CONVENTIONS:", *[f"- {c}" for c in b.conventions], "", "RULES:", *_common_rules(b),
              "- You may use empty cells for helper calculations.",
              "", _assumption_map(spec, lay), "", "Use the tools to inspect and edit the workbook. Call submit "
              "when you are done."]
    return Task(task_id=f"{family}-d{difficulty}-s{seed}", family=family, difficulty=difficulty, seed=seed,
                instructions="\n".join(instr), initial=initial, reference=reference, target_keys=targets,
                locked=locked_cells(initial), max_steps=max_steps,
                meta={"scale_factor": SCALE_FACTOR, "layout": lay, "spec": spec, "domain": b.domain,
                      "spec_style": spec_style, **b.meta}, **fields)


def repair_task(b: Bundle, family: str, seed: int, difficulty: int, n_bugs: Tuple[int, int], min_latent: int,
                canary_p: float, max_steps: int, rng: random.Random) -> Task:
    from ..tasks.mutations import apply_bugs, sample_bugs

    spec = b.spec
    reference, lay = render(spec)
    targets = formula_keys(reference)
    fields = _base_task_fields(b, reference, lay, targets, seed)
    canary = rng.random() < canary_p
    bugs = []
    if not canary:
        n = rng.randint(*n_bugs)
        bugs = sample_bugs(reference, spec, lay, targets, fields["scenarios"], rng, n,
                           min_latent=min(min_latent, n), row_scope_p=0.45)
    initial = apply_bugs(reference, bugs)
    labels = fields["labels"]
    label = lambda k: labels.get(k) or f"{k[0]}!{addr(k[1], k[2])}"  # noqa: E731
    instr = [f"You are reviewing a {b.noun} (sheets: {', '.join(spec.sheets)}; amounts in {spec.currency}).",
             "", "TASK: the model may contain errors in its formulas, or it may be correct. Compare every formula "
             "with the TERMS below and fix each one that does not implement them; if the model is correct, change "
             "nothing. An error may affect one cell or a whole row.", "", "TERMS:", b.term_sheet, "",
             "CONVENTIONS:", *[f"- {c}" for c in b.conventions], "", "RULES:", *_common_rules(b),
             "- Fix formulas only; keep them live.", "", _assumption_map(spec, lay), "",
             "Use the tools to inspect and edit the workbook. Call submit when you are done."]
    return Task(task_id=f"{family}-d{difficulty}-s{seed}", family=family, difficulty=difficulty, seed=seed,
                instructions="\n".join(instr), initial=initial, reference=reference, target_keys=targets,
                locked=locked_cells(initial, editable=targets), bugs=[m.to_dict(label) for m in bugs],
                expect_no_change=canary, max_steps=max_steps,
                meta={"scale_factor": SCALE_FACTOR, "layout": lay, "spec": spec, "domain": b.domain,
                      "n_bugs": len(bugs), "n_latent": sum(m.effect == "latent" for m in bugs),
                      "bug_cells": sorted({k for m in bugs for k in m.cells}), **b.meta}, **fields)


def free_task(b: Bundle, family: str, seed: int, difficulty: int, max_steps: int) -> Task:
    """Empty Model sheet, any layout; graded through the Outputs contract."""
    spec = b.spec
    model_wb, lay = render(spec)
    ref = Workbook(iterative=spec.iterative)
    for s in ("Assumptions", "Model", "Outputs"):
        ref.add_sheet(s)
    for sheet, r, c, raw in model_wb.cells():
        ref.set_rc(sheet, r, c, raw)
    # outputs contract: line outputs over forecast columns, calc outputs in column C
    ref.set_rc("Outputs", 1, 1, "OUTPUTS - link every cell to your model")
    ref.set_rc("Outputs", HEADER_ROW, 1, "Output")
    fc_cols = [lay.col(p) for p in lay.forecast_indices]
    for p in lay.forecast_indices:
        ref.set_rc("Outputs", HEADER_ROW, lay.col(p), lay.periods[p])
    targets: List[Key] = []
    out_pos: Dict[str, Tuple[int, List[int]]] = {}
    outputs = [(oid, _output_label(b, oid, lab)) for oid, lab in b.outputs]
    for i, (oid, lab) in enumerate(outputs):
        row = 4 + i
        ref.set_rc("Outputs", row, 1, lab)
        if oid in lay.rows:
            msheet, mr = lay.rows[oid]  # usually Model; an input line output links to Assumptions
            for c in fc_cols:
                ref.set_rc("Outputs", row, c, f"={msheet}!{addr(mr, c)}")
                targets.append(("outputs", row, c))
            out_pos[oid] = (row, fc_cols)
        else:
            _, cr, cc = lay.calcs[oid]
            ref.set_rc("Outputs", row, FIRST_PERIOD_COL, f"=Model!{addr(cr, cc)}")
            targets.append(("outputs", row, FIRST_PERIOD_COL))
            out_pos[oid] = (row, [FIRST_PERIOD_COL])
    initial = Workbook(iterative=spec.iterative)
    for s in ref.sheet_names:
        initial.add_sheet(s)
    for sheet, r, c, raw in ref.cells():
        if sheet == "Assumptions" or (sheet == "Outputs" and (c < FIRST_PERIOD_COL or r <= HEADER_ROW)):
            initial.set_rc(sheet, r, c, raw)
    # the starting-point column of the model (closing balances, actuals) is given on the Model sheet
    for ln in spec.lines:
        if ln.sheet == "Model" and ln.hist == "input" and ln.history is not None:
            sheet, r = lay.rows[ln.id]
            initial.set_rc("Model", r, 1, ln.label + " (starting value)")
            for p in range(spec.n_hist):
                initial.set_rc("Model", r, lay.col(p), float(ln.history[p]))
    initial.set_rc("Model", 1, 1, "Build your model here (any layout). Starting values are given below.")
    ref_model_given = {(r, c): v for _, r, c, v in initial.cells("Model")}
    for (r, c), v in ref_model_given.items():
        ref.set_rc("Model", r, c, v)  # same given cells in the reference so integrity holds
    fields = _base_task_fields(b, ref, lay, targets, seed)
    fields["money_targets"] = [t for t in targets]  # all outputs are money unless stated otherwise
    non_money = {oid for oid, _ in b.outputs
                 if (oid in lay.rows and b.spec.line(oid).kind != "money")
                 or (oid in lay.calcs and next(c for c in spec.calcs if c.id == oid).kind != "money")}
    fields["money_targets"] = [t for oid, _ in b.outputs if oid not in non_money
                               for t in [("outputs", out_pos[oid][0], c) for c in out_pos[oid][1]]]
    # identities and relations are re-expressed on the Outputs cells where possible
    fields["identities"] = _output_identities(b, lay, out_pos)
    fields["relations"] = _output_relations(b, lay, ref, fields["scenarios"], out_pos)
    fields["forbidden_deps"] = []
    out_lines = [f"- row {out_pos[o][0]}: {lab}" + (" (forecast years)" if o in lay.rows else " (single value in "
                 f"column {index_to_col(FIRST_PERIOD_COL)})") for o, lab in outputs]
    instr = [f"Build a {b.noun} from scratch in a spreadsheet (amounts in {spec.currency}).", "",
             "TASK: build the whole model on the Model sheet in any layout you like, then link every cell of the "
             f"Outputs sheet to it. Projection periods: {', '.join(lay.periods[spec.n_hist:])} (use Outputs "
             f"columns {index_to_col(fc_cols[0])}:{index_to_col(fc_cols[-1])} for them, same order).",
             "Outputs to fill:", *out_lines, "", "TERMS:", b.term_sheet, "", "CONVENTIONS:",
             *[f"- {c}" for c in b.conventions], "", "RULES:", *_common_rules(b),
             "- Use only the Model sheet (and Outputs) for your work; the starting values on Model are given.",
             "", _assumption_map(spec, lay), "", "Use the tools to build the model. Call submit when you are done."]
    return Task(task_id=f"{family}-d{difficulty}-s{seed}", family=family, difficulty=difficulty, seed=seed,
                instructions="\n".join(instr), initial=initial, reference=ref, target_keys=targets,
                locked={k: v for k, v in initial.snapshot().items()}, max_steps=max_steps,
                meta={"scale_factor": SCALE_FACTOR, "layout": lay, "spec": spec, "domain": b.domain,
                      "outputs": outputs, "spec_style": "free", **b.meta}, **fields)


def _output_label(b: Bundle, oid: str, lab: str) -> str:
    """The Outputs contract names each output by its model line's full label
    ("Deferred tax expense/(credit)", not "Deferred tax expense"), unless the
    contract label already contains it and adds to it (a sign convention). A
    shortened label dropped sign conventions and was graded against a correct
    model (HACK_LOG #21)."""
    full = (next((ln.label for ln in b.spec.lines if ln.id == oid), None)
            or next((c.label for c in b.spec.calcs if c.id == oid), lab))
    return lab if full.casefold() in lab.casefold() else full


def _output_identities(b: Bundle, lay: Layout, out_pos) -> List[IdentityCheck]:
    """Identities whose every term is an output can be checked in free-layout tasks."""
    out = []
    for idn in b.identities:
        if not all(i in out_pos for _, i, _ in idn.terms):
            continue
        per = []
        fc = list(lay.forecast_indices)
        if idn.when == "once":
            terms = []
            for s, i, o in idn.terms:
                row, cols = out_pos[i]
                if i in lay.rows:
                    p = _abs_period(lay, o)
                    if p < lay.n_hist:
                        terms = None
                        break
                    terms.append((s, ("outputs", row, lay.col(p))))
                else:
                    terms.append((s, ("outputs", row, cols[0])))
            if terms:
                per.append(terms)
        else:
            periods = fc[1:] if idn.when == "forecast2" else fc
            for p in periods:
                terms = []
                for s, i, o in idn.terms:
                    q = p + int(o)
                    if i in lay.rows and q < lay.n_hist:
                        terms = None
                        break
                    row, cols = out_pos[i]
                    terms.append((s, ("outputs", row, lay.col(q) if i in lay.rows else cols[0])))
                if terms:
                    per.append(terms)
        if per:
            out.append(IdentityCheck(idn.name, idn.desc, per))
    return out


def _output_relations(b: Bundle, lay: Layout, ref: Workbook, scenarios, out_pos) -> List[dict]:
    from ..grader.grader import _relation_holds

    rels = []
    for m in b.monotone:
        oid = m.output[:-5] if m.output.endswith("@last") else m.output
        if oid not in out_pos:
            continue
        row, cols = out_pos[oid]
        rels.append({"type": "monotone", "name": m.name, "output": ("outputs", row, cols[-1]),
                     "input": lay.scalar_key(m.input), "delta": m.delta, "sign": m.sign})
    if rels:
        cw = ref.compile()
        runs = [cw.run()] + [cw.run(sc) for sc in scenarios]
        for rel in rels:
            rel["runs"] = [i for i in range(len(runs))
                           if _relation_holds(cw, rel, {} if i == 0 else scenarios[i - 1], runs[i])]
    return [r for r in rels if r.get("runs")]
