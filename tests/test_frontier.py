"""Frontier tier: every domain x variant generates a valid, gradeable task."""

import random

import pytest

from spreadsheet_env.agents.demos import expert_patch
from spreadsheet_env.agents.runner import grade_patch
from spreadsheet_env.engine.refs import addr
from spreadsheet_env.frontier import all_families
from spreadsheet_env.grader.equivalence import equivalent_rewrite
from spreadsheet_env.grader.grader import Grader, cell_budget
from spreadsheet_env.session import Session
from spreadsheet_env.tasks import make_task

G = Grader()
FAMILIES = sorted(all_families())
IDS = [f"{fam}-d{d}-s0" for fam in FAMILIES for d in (1, 5)]


def full_reference(task):
    """Every target cell plus every reference cell the task leaves empty (the whole
    model in free-layout variants)."""
    keys = set(task.target_keys) | {k for k in task.reference.snapshot() if task.initial.raw(k) is None}
    return keys


def reference_submission(task):
    sub = task.initial.copy()
    for k in full_reference(task):
        sub.set_rc(sub.sheet_name(k[0]), k[1], k[2], task.reference.raw(k))
    return sub


@pytest.mark.parametrize("tid", IDS)  # one test per task, so pytest-xdist spreads them over cores
def test_reference_solves_noop_and_paste_fail(tid):
    t = make_task(tid)
    assert G.grade(t, reference_submission(t)).solved
    assert G.grade(t, t.initial.copy()).solved == t.expect_no_change
    vals = t.reference.calculate()
    paste = t.initial.copy()
    for k in t.target_keys:
        paste.set_rc(paste.sheet_name(k[0]), k[1], k[2], vals[k])
    assert not G.grade(t, paste).solved


@pytest.mark.parametrize("tid", IDS)
def test_expert_patch_solves(tid):
    t = make_task(tid)
    res, _, errs = grade_patch(tid, expert_patch(t))
    assert not errs and res.solved


@pytest.mark.parametrize("tid", [i for i in IDS if "_build" in i])
def test_equivalent_rewrites_are_accepted(tid):
    t = make_task(tid)
    keys = full_reference(t)
    full = equivalent_rewrite(t.reference, sorted(keys), random.Random(tid))
    sub = t.initial.copy()
    for k in keys:
        sub.set_rc(sub.sheet_name(k[0]), k[1], k[2], full.raw(k))
    for sheet, r, c, raw in full.cells():
        key = (sheet.casefold(), r, c)
        if t.initial.raw(key) is None and t.reference.raw(key) is None:
            sub.set_rc(sheet, r, c, raw)  # helper cells
    res = G.grade(t, sub)
    assert res.solved, res.summary()


def test_frontier_tasks_are_deterministic():
    a, b = make_task("tax_build-d4-s3"), make_task("tax_build-d4-s3")
    assert a.reference.snapshot() == b.reference.snapshot() and a.scenarios == b.scenarios


def test_inputs_that_cancel_exactly_are_not_required():
    # CTA movement written as the CTA analysis identity (td_open + td_inc - td_div) never
    # references the PP&E/liability inputs the reference's plug passes through; they
    # cancel (LC cash balances), so the equivalent model must be solved (HACK_LOG #19)
    t = make_task("fx_build-d3-s0")
    lay = t.meta["layout"]
    sub = reference_submission(t)
    for p in lay.forecast_indices:
        c = lay.col(p)
        a = lambda ident: addr(lay.rows[ident][1], c)  # noqa: E731
        sub.set_rc("Model", lay.rows["cta_move"][1], c, f"={a('td_open')}+{a('td_inc')}-{a('td_div')}")
    assert G.grade(t, sub).solved


def test_typed_zero_check_row_still_fails_structure():
    # the relaxation above must not reopen HACK_LOG #4: a target whose reference is
    # constant keeps the syntactic rule
    t = make_task("build-d3-s0")
    sub = reference_submission(t)
    checks = [k for k in t.target_keys
              if all(r.get(k) == 0.0 for r in G._reference_runs(t)) and (t.labels.get(k) or "").lower().find("check") >= 0]
    assert checks
    for k in checks:
        sub.set_rc(sub.sheet_name(k[0]), k[1], k[2], 0.0)
    res = G.grade(t, sub)
    assert not res.solved and res.components["structure"] == 0.0


def test_exit_grid_stays_ascending_in_every_scenario():
    # "MOIC at the highest exit" is the last column only if the grid stays sorted (HACK_LOG #20)
    t = make_task("vc_build-d5-s0")
    keys = [i.key for i in t.inputs if i.group == "exit"]
    assert len(keys) > 2
    base = {i.key: i.base for i in t.inputs}
    for sc in t.scenarios:
        vals = [sc.get(k, base[k]) for k in keys]
        assert vals == sorted(vals)


def test_patch_budget_matches_the_grader_budget():
    # a full-size 60-month free build writes more than 3,000 cells; the patch writer must
    # accept what the integrity oracle accepts
    t = make_task("abs_free-d5-s0")
    budget = cell_budget(t)
    assert budget > 3000
    s = Session(t, max_steps=10_000)
    rows = [{"sheet": "Model", "cell": f"D{r}:BK{r}", "content": "=1"} for r in range(100, 100 + 3200 // 60 + 1)]
    msgs = s.apply_patch(rows)
    assert not [m for m in msgs if "budget" in m]


DOC_IDS = [f"{d}_build-d{lv}-s0" for d in ("ca", "lpa", "indenture", "charter") for lv in range(1, 6)]
_DOC_WORDS = {"include", "includes", "including", "Holdings", "Borrower", "Issuer", "Notes", "Partnership",
              "General Partner", "Limited Partners", "Partners", "Corporation", "series", "Interest Rate",
              "without limitation"}


@pytest.mark.parametrize("tid", DOC_IDS)
def test_document_captions_exist(tid):
    """Every quoted caption in a generated document is a defined term or an Assumptions label,
    so a document can never refer to an input the workbook does not have; documents are ASCII."""
    import re

    t = make_task(tid)
    assert t.instructions.isascii()
    doc = t.instructions[t.instructions.index("TERMS:"):t.instructions.index("CONVENTIONS:")]
    defined = set(re.findall(r'^"([^"]+)"', doc, flags=re.M))
    defined |= set(re.findall(r'\((?:the |a |an |such declined amounts, )?"([^"]+)"', doc))
    defined |= set(re.findall(r'"([^"]+)" occurs', doc))  # inline definition: a "Financial Covenant Default" occurs
    labels = {str(v) for sheet, r, c, v in t.initial.cells("Assumptions") if c == 1 and isinstance(v, str)}
    series = {re.sub(r" (shares outstanding|Original Issue Price).*", "", lab) for lab in labels}
    for cap in set(re.findall(r'"([^"]+)"', doc)) - defined - _DOC_WORDS:
        if "<series>" in cap:
            assert any(cap.replace("<series>", s) in labels for s in series), cap
        else:
            assert cap in labels or cap in defined, f"{tid}: caption not on the Assumptions sheet: {cap!r}"


def test_structural_zero_openings_are_never_perturbed():
    # an undrawn revolver at close is a fact of the term sheet, not an assumption
    t = make_task("lbo_build-d3-s0")
    lay = t.meta["layout"]
    key = lay.key("rev_close", 0)
    assert all(sc.get(key, 0.0) == 0.0 for sc in t.scenarios)


def test_branch_only_in_the_submission_faces_hidden_scenarios():
    # Red-team round 2 (HACK_LOG #26): an extra arm IF(tax rate > 50%, 0, ...) that the
    # reference does not have. The graded scenarios reach both arms, but their only high-tax
    # scenario has a pre-tax loss, where the answer is 0 either way.
    t = make_task("build_free-d2-s1000003")
    sub = reference_submission(t)
    assert G.grade(t, sub).solved
    tax = next(i for i in t.inputs if i.kind == "tax")
    ref_tax = f"Assumptions!${addr(tax.key[1], tax.key[2])[0]}${tax.key[1]}"
    cells = [(sh, r, c, raw) for sh, r, c, raw in t.reference.cells()
             if isinstance(raw, str) and raw.startswith("=MAX(0,") and ref_tax in raw]
    assert cells
    for sh, r, c, raw in cells:
        sub.set_rc(sh, r, c, f"=IF({ref_tax}>0.5,0,{raw[1:]})")
    res = G.grade(t, sub)
    assert not res.solved and res.components["perturb"] < 1.0
    assert res.diagnostics["hidden_scenarios"] > 100
