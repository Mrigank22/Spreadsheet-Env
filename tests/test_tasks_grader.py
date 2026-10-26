"""Task generation and grading guarantees (each one is a claim in the README)."""

import random

import pytest

from spreadsheet_env.engine.refs import addr
from spreadsheet_env.grader.equivalence import equivalent_rewrite
from spreadsheet_env.grader.grader import Grader
from spreadsheet_env.session import Session, parse_patch_text
from spreadsheet_env.tasks import TEST_SEEDS, TRAIN_SEEDS, make_task
from spreadsheet_env.tasks.build import build_task
from spreadsheet_env.tasks.repair import repair_task

G = Grader()
IDS = [f"{fam}-d{d}-s{s}" for fam in ("build", "repair") for d in (1, 2, 3, 4) for s in (0, 1)]
IDS += ["build-d5-s0", "repair-d5-s0"]
IDS += [f"dcf-d{d}-s{s}" for d in (1, 2, 3, 4, 5) for s in (0, 1)]
FREE_IDS = [f"build_free-d{d}-s0" for d in (1, 2, 3, 4, 5)]


def reference_submission(task):
    sub = task.initial.copy()
    for k in task.target_keys:
        sub.set_rc(sub.sheet_name(k[0]), k[1], k[2], task.reference.raw(k))
    return sub


@pytest.mark.parametrize("tid", IDS)
def test_reference_solves_and_noop_fails(tid):
    t = make_task(tid)
    assert G.grade(t, reference_submission(t)).solved
    noop = G.grade(t, t.initial.copy())
    assert noop.solved == t.expect_no_change


@pytest.mark.parametrize("tid", IDS[:6])
def test_tasks_are_deterministic(tid):
    fam, d, s = tid.split("-")
    fn = build_task if fam == "build" else repair_task
    a, b = fn(int(s[1:]), int(d[1:])), fn(int(s[1:]), int(d[1:]))
    assert a.initial.snapshot() == b.initial.snapshot()
    assert a.reference.snapshot() == b.reference.snapshot()
    assert a.scenarios == b.scenarios
    assert a.instructions == b.instructions


@pytest.mark.parametrize("tid", IDS)  # one test per task, so pytest-xdist spreads them over cores
def test_reference_satisfies_identities_in_every_scenario(tid):
    t = make_task(tid)
    res = Grader(oracles=["identities", "homogeneity", "structure"]).grade(t, t.reference.copy())
    assert res.solved, (tid, res.summary())


def test_pasted_values_are_rejected_but_fool_a_value_only_grader():
    t = make_task("build-d3-s0")
    vals = t.reference.calculate()
    sub = t.initial.copy()
    for k in t.target_keys:
        sub.set_rc(sub.sheet_name(k[0]), k[1], k[2], vals[k])
    assert not G.grade(t, sub).solved
    assert Grader(oracles=["base"], value_only_tolerance=True).grade(t, sub).solved


def test_balancing_plug_is_rejected():
    t = make_task("build-d4-s1")
    lay = t.meta["layout"]
    sub = reference_submission(t)
    sheet, row = lay.rows["cash"]
    from spreadsheet_env.engine.refs import index_to_col
    for p in lay.forecast_indices:
        c = index_to_col(lay.col(p))
        others = "-".join(f"{c}{lay.rows[o][1]}" for o in ("ar", "inv", "ppe") if o in lay.rows)
        sub.set_rc(sheet, row, lay.col(p), f"={c}{lay.rows['tle'][1]}-{others}")
    res = G.grade(t, sub)
    assert not res.solved and res.components["structure"] == 0.0


def test_hardcoded_balance_check_is_rejected():
    t = make_task("build-d4-s1")  # check row is a target at d4
    lay = t.meta["layout"]
    sub = reference_submission(t)
    sheet, row = lay.rows["check"]
    for p in lay.forecast_indices:
        sub.set_rc(sheet, row, lay.col(p), 0.0)
    res = G.grade(t, sub)
    assert not res.solved and res.components["structure"] == 0.0


def test_editing_an_input_is_rejected():
    t = make_task("repair-d2-s0")
    sub = reference_submission(t)
    k = t.inputs[0].key
    sub.set_rc(sub.sheet_name(k[0]), k[1], k[2], t.inputs[0].base * 1.01)
    assert G.grade(t, sub).components["integrity"] == 0.0


@pytest.mark.parametrize("tid", IDS)
def test_equivalent_rewrites_are_accepted(tid):
    t = make_task(tid)
    for v in range(2):
        full = equivalent_rewrite(t.reference, t.target_keys, random.Random(v))
        sub = t.initial.copy()
        for k in t.target_keys:
            sub.set_rc(sub.sheet_name(k[0]), k[1], k[2], full.raw(k))
        for sheet, r, c, raw in full.cells():
            key = (sheet.casefold(), r, c)
            if t.initial.raw(key) is None and t.reference.raw(key) is None:
                sub.set_rc(sheet, r, c, raw)
        res = G.grade(t, sub)
        assert res.solved, (tid, v, res.summary())


def test_latent_bugs_exist_and_are_invisible_at_base():
    t = repair_task(3, 3)
    assert t.meta["n_latent"] >= 1
    latent = [b for b in t.bugs if b["effect"] == "latent"]
    assert latent
    assert Grader(oracles=["base"]).grade(t, t.initial.copy()).components["base"] < 1.0 or len(latent) == len(t.bugs)


def test_session_tools_roundtrip():
    t = make_task("build-d2-s0")
    s = Session(t)
    k = t.target_keys[0]
    sheet = t.reference.sheet_name(k[0])
    out = s.write_cell(sheet, addr(k[1], k[2]), t.reference.raw(k))
    assert "->" in out
    out = s.copy_cell(sheet, addr(k[1], k[2]), f"{addr(k[1], k[2] + 1)}:{addr(k[1], k[2] + 2)}")
    assert "pasted into 2 cell(s)" in out
    assert "error" in s.write_cell(sheet, "E5", "=INDIRECT(\"A1\")")
    assert "error" in s.write_cell(sheet, "E5", "=SUM(")
    assert s.read_range(sheet, "A1:C3").startswith(f"[{sheet}]")
    assert "submitted" in s.submit().lower() and s.done


def test_patch_text_parser():
    text = "reasoning...\n```\nIS!E5 := =D5*(1+Assumptions!E18)\n'My Sheet'!F6 := 12.5\nE7 => =E5-E6\n```"
    edits = parse_patch_text(text, default_sheet="IS")
    assert edits == [
        {"sheet": "IS", "cell": "E5", "content": "=D5*(1+Assumptions!E18)"},
        {"sheet": "My Sheet", "cell": "F6", "content": "12.5"},
        {"sheet": "IS", "cell": "E7", "content": "=E5-E6"},
    ]


def test_dcf_grid_must_match_own_model():
    """Reference-free: a grid that ignores its headers fails the relations oracle."""
    t = make_task("dcf-d4-s0")
    sub = reference_submission(t)
    lay = t.meta["layout"]
    price = lay.calcs["price"]
    for k in [k for k in t.target_keys if k[0] == "sensitivity"]:
        sub.set_rc("Sensitivity", k[1], k[2], f"=DCF!$C${price[1]}")  # every cell = base price
    res = Grader(oracles=["relations"]).grade(t, sub)
    assert res.components["relations"] < 1.0


def _free_reference(t, drow=0):
    """The reference model, optionally relocated ``drow`` rows down on the Model sheet."""
    from spreadsheet_env.engine.parser import Ref, Rng, map_refs, parse_formula, to_formula
    from spreadsheet_env.engine.refs import CellRef, RangeRef

    def s1(r):
        if r.sheet is None or r.sheet.lower() == "model":
            return CellRef(r.sheet, r.row + drow, r.col, r.row_abs, r.col_abs)
        return r

    def shift(n):
        return Ref(s1(n.ref)) if isinstance(n, Ref) else Rng(RangeRef(n.ref.sheet, s1(n.ref.start), s1(n.ref.end)))

    sub = t.initial.copy()
    for _, r, c, raw in t.reference.cells("Model"):
        if t.initial.raw(("model", r + drow, c)) is not None:
            continue  # never overwrite given (locked) cells such as the sheet's instruction label
        new = to_formula(map_refs(parse_formula(raw), shift)) if isinstance(raw, str) and raw.startswith("=") else raw
        sub.set_rc("Model", r + drow, c, new)
    for k in t.target_keys:
        sub.set_rc("Outputs", k[1], k[2], to_formula(map_refs(parse_formula(t.reference.raw(k)), shift)))
    return sub


@pytest.mark.parametrize("tid", FREE_IDS)
def test_free_layout_any_layout_is_accepted(tid):
    t = make_task(tid)
    assert G.grade(t, _free_reference(t)).solved
    assert G.grade(t, _free_reference(t, drow=11)).solved  # same model, different layout
    assert not G.grade(t, t.initial.copy()).solved


def test_train_and_test_seeds_are_disjoint():
    assert not set(TRAIN_SEEDS) & set(TEST_SEEDS)
