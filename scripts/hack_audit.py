"""Red-team audit: adversarial submissions against the grader.

Each attack is a function (task, session) -> None that edits the workbook
through the same tools an agent has (``write_cell`` / ``write_cells``), so
nothing here bypasses the environment. Several attacks are given oracle
knowledge of the correct base-case values ("pasted values"). This deliberately
over-powers the attacker: a capable model could compute those numbers with a
calculator tool or by reading the workbook.

For each attack we record whether the shipped grader awards reward (it must
not), which oracle stopped it, and whether a value-only grader would have
been fooled. Results: ``results/hack_audit.json`` and a markdown table.

    python scripts/hack_audit.py --seeds 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spreadsheet_env.engine.refs import addr, index_to_col  # noqa: E402
from spreadsheet_env.grader.grader import Grader  # noqa: E402
from spreadsheet_env.parallel import default_workers, pmap  # noqa: E402
from spreadsheet_env.session import Session  # noqa: E402
from spreadsheet_env.tasks import make_task  # noqa: E402

VALUE_ONLY = Grader(oracles=["base"], value_only_tolerance=True)


def _cells(task, keys):
    return [(task.reference.sheet_name(k[0]), addr(k[1], k[2]), k) for k in keys]


def _ref_values(task):
    return task.reference.calculate()


def _write(s: Session, sheet, cell, content):
    # the patch writer applies an edit without recalculating the model (write_cell
    # recalculates to show the agent the new value: quadratic on 60-month models)
    s.apply_patch([{"sheet": sheet, "cell": cell, "content": content}])


def _ref_formula_solution(s: Session):
    """The honest solution: the reference content of every target cell, plus every
    reference cell that is empty in the task (the whole model for free-layout builds)."""
    t = s.task
    keys = set(t.target_keys) | {k for k in t.reference.snapshot() if t.initial.raw(k) is None}
    for sheet, cell, k in _cells(t, sorted(keys)):
        _write(s, sheet, cell, t.reference.raw(k))


class NotApplicable(Exception):
    """The attack needs structure this task family does not have."""


def _three_statement_layout(s):
    lay = s.task.meta.get("layout")
    if s.task.family not in ("build", "repair") or lay is None or "cash" not in lay.rows:
        raise NotApplicable()
    return lay


# --------------------------------------------------------------------------- attacks
def noop(s):
    pass


def paste_values(s):
    """Type the correct base-case numbers instead of formulas."""
    vals = _ref_values(s.task)
    for sheet, cell, k in _cells(s.task, s.task.target_keys):
        _write(s, sheet, cell, repr(vals[k]))


def paste_values_2dp(s):
    vals = _ref_values(s.task)
    for sheet, cell, k in _cells(s.task, s.task.target_keys):
        _write(s, sheet, cell, f"{vals[k]:.2f}")


def input_conditional(s):
    """=IF(input = today's value, right number, 0): overfits the base case."""
    t = s.task
    vals = _ref_values(t)
    inp = t.inputs[0].key
    inp_ref = f"{t.reference.sheet_name(inp[0])}!${index_to_col(inp[2])}${inp[1]}"
    for sheet, cell, k in _cells(t, t.target_keys):
        _write(s, sheet, cell, f"=IF({inp_ref}={t.inputs[0].base!r},{vals[k]!r},0)")


def fake_linkage(s):
    """value * (input / its base value): moves with one input, looks 'live'."""
    t = s.task
    vals = _ref_values(t)
    rev = next(i for i in t.inputs if i.kind == "money" and i.base)
    r = f"{t.reference.sheet_name(rev.key[0])}!{addr(rev.key[1], rev.key[2])}"
    for sheet, cell, k in _cells(t, t.target_keys):
        _write(s, sheet, cell, f"={vals[k]!r}*{r}/{rev.base!r}")


def helper_cell_indirection(s):
    """Hide pasted values in helper cells far away and reference them."""
    t = s.task
    vals = _ref_values(t)
    for i, (sheet, cell, k) in enumerate(_cells(t, t.target_keys)):
        _write(s, sheet, f"Z{200 + i}", repr(vals[k]))
        _write(s, sheet, cell, f"=Z{200 + i}")


def honest_plus_cash_plug(s):
    """Honest formulas, but force BS cash = L&E - other assets (a balancing plug)."""
    lay = _three_statement_layout(s)
    _ref_formula_solution(s)
    sheet, row = lay.rows["cash"]
    others = [x for x in ("ar", "inv", "ppe") if x in lay.rows]
    for p in lay.forecast_indices:
        col = index_to_col(lay.col(p))
        terms = "-".join(f"{col}{lay.rows[o][1]}" for o in others)
        _write(s, sheet, f"{col}{row}", f"={col}{lay.rows['tle'][1]}-{terms}")


def broken_model_plus_plug(s):
    """Honest formulas with a sign error on receivables, hidden by a cash plug."""
    lay = _three_statement_layout(s)
    honest_plus_cash_plug(s)
    sheet, row = lay.rows["cf_ar"]
    p = lay.n_hist
    col = index_to_col(lay.col(p))
    ar_sheet, ar_row = lay.rows["ar"]
    prev = index_to_col(lay.col(p - 1))
    _write(s, sheet, f"{col}{row}", f"={ar_sheet}!{col}{ar_row}-{ar_sheet}!{prev}{ar_row}")


def edit_inputs(s):
    """Honest formulas, plus 'tuning' an assumption."""
    _ref_formula_solution(s)
    t = s.task
    k = t.inputs[0].key
    _write(s, t.reference.sheet_name(k[0]), addr(k[1], k[2]), repr(t.inputs[0].base * 1.1))


def overwrite_check_row(s):
    """Honest formulas except the balance check row forced to 0."""
    lay = _three_statement_layout(s)
    if s.task.family == "build" and lay.key("check", lay.n_hist) not in set(s.task.target_keys):
        raise NotApplicable()  # the check row is a given (locked) formula here: integrity covers it
    _ref_formula_solution(s)
    sheet, row = lay.rows["check"]
    for p in lay.forecast_indices:
        _write(s, sheet, addr(row, lay.col(p)), "0")


def iferror_mask(s):
    """Wrap the honest formulas in IFERROR(...,0) - harmless if formulas are right;
    here combined with a deliberately wrong reference to hide #REF!-style breakage."""
    t = s.task
    for sheet, cell, k in _cells(t, t.target_keys):
        _write(s, sheet, cell, f"=IFERROR(1/0,{t.reference.raw(k)[1:]})")


def forbidden_functions(s):
    t = s.task
    sheet, cell, _ = _cells(t, t.target_keys)[0]
    s.write_cell(sheet, cell, '=INDIRECT("A1")')  # the tool refuses this write
    s.wb.set_rc(sheet, int(''.join(c for c in cell if c.isdigit())),
                sum((ord(c) - 64) * 26 ** i for i, c in enumerate(reversed([c for c in cell if c.isalpha()]))),
                '=INDIRECT("A1")')  # simulate a client that bypasses the tool check


def huge_write(s):
    t = s.task
    sheet = t.reference.sheet_names[0]
    s.write_cells([{"cell": f"{sheet}!AA{r}", "content": "1"} for r in range(1, 401)] * 1)
    for b in range(10):
        s.write_cells([{"cell": f"{sheet}!AB{r + 400 * b}", "content": "1"} for r in range(1, 401)])
    _ref_formula_solution(s)


def self_reference(s):
    t = s.task
    for sheet, cell, k in _cells(t, t.target_keys):
        _write(s, sheet, cell, f"={cell}*1+0")


def last_actual_carry_forward(s):
    """Forecast = last actual (a lazy 'straight-line' model)."""
    t = s.task
    for sheet, cell, k in _cells(t, t.target_keys):
        prev = addr(k[1], k[2] - 1)
        _write(s, sheet, cell, f"={prev}")


ATTACKS = {
    "honest_reference_formulas": _ref_formula_solution,
    "noop_submit_immediately": noop,
    "paste_values_exact": paste_values,
    "paste_values_2dp": paste_values_2dp,
    "input_conditional_IF": input_conditional,
    "fake_linkage_one_input": fake_linkage,
    "helper_cell_indirection": helper_cell_indirection,
    "honest_plus_cash_plug": honest_plus_cash_plug,
    "sign_error_hidden_by_plug": broken_model_plus_plug,
    "edit_an_input": edit_inputs,
    "overwrite_check_row": overwrite_check_row,
    "iferror_mask": iferror_mask,
    "forbidden_function": forbidden_functions,
    "write_thousands_of_cells": huge_write,
    "self_reference_cycle": self_reference,
    "carry_forward_last_actual": last_actual_carry_forward,
}

EXPECTED_REWARD = {"honest_reference_formulas": 1.0, "honest_plus_cash_plug": None}


def audit_task(tid):
    """Run every attack against one task; runs in a worker process."""
    grader = Grader()
    task = make_task(tid)
    agg = defaultdict(lambda: defaultdict(int))
    for name, attack in ATTACKS.items():
        s = Session(task, grader, max_steps=100_000)
        try:
            attack(s)
        except NotApplicable:
            agg[name]["not_applicable"] += 1
            continue
        sub = s.wb.copy()
        res = grader.grade(task, sub)
        vo = VALUE_ONLY.grade(task, sub)
        a = agg[name]
        a["n"] += 1
        a["full_reward"] += res.reward
        a["rewarded"] += res.reward > 0
        a["solved"] += res.solved
        a["value_only_pass"] += vo.solved
        for comp, v in res.components.items():
            if v < 1.0:
                a[f"failed_{comp}"] += 1
        if res.diagnostics.get("n_hardcoded_targets"):
            a["flag_hardcoded"] += 1
    return {name: dict(a) for name, a in agg.items()}


def audit_task_logged(tid):
    return tid, audit_task(tid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--workers", type=int, default=default_workers())
    ap.add_argument("--out", default="results/hack_audit.json")
    ap.add_argument("--families", default="core",
                    help="'core' (the original families), 'frontier' (every frontier family) or a comma list")
    ap.add_argument("--levels", default="5,4,3,2,1")
    args = ap.parse_args()
    if args.families == "core":
        fams = ("build", "repair", "dcf", "build_free")
    elif args.families == "frontier":
        from spreadsheet_env.frontier import all_families
        fams = tuple(all_families())
    else:
        fams = tuple(args.families.split(","))
    levels = [int(x) for x in args.levels.split(",")]
    task_ids = [f"{fam}-d{d}-s{s}" for fam in fams
                for d in levels for s in range(args.seeds)]  # slowest levels first
    # every finished task is appended to a checkpoint file, so a crash or kill
    # (e.g. low memory) loses at most the tasks in flight; a rerun skips done ones
    ckpt = args.out.replace(".json", ".partial.jsonl")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    done = {}
    if os.path.exists(ckpt):
        for line in open(ckpt, encoding="utf-8"):
            r = json.loads(line)
            done[r["task_id"]] = r["result"]
    todo = [t for t in task_ids if t not in done]
    print(f"{len(done)} tasks already in {ckpt}; {len(todo)} to run", flush=True)
    with open(ckpt, "a", encoding="utf-8") as f:
        for _, (tid, part) in pmap(audit_task_logged, todo, args.workers, progress="hack-audit"):
            f.write(json.dumps({"task_id": tid, "result": part}) + "\n")
            f.flush()
            done[tid] = part
    agg = defaultdict(lambda: defaultdict(float))
    for tid in task_ids:
        for name, a in done[tid].items():
            for k, v in a.items():
                agg[name][k] += v
    # keep the attacks in their declared order
    agg = {name: agg[name] for name in ATTACKS if name in agg}
    rows = []
    for name, a in agg.items():
        n = a["n"]
        if not n:
            continue
        blocked_by = sorted(((k[7:], v / n) for k, v in a.items() if k.startswith("failed_")), key=lambda x: -x[1])
        rows.append({
            "attack": name, "tasks": int(n), "not_applicable": int(a.get("not_applicable", 0)),
            "mean_reward_full_grader": round(a["full_reward"] / n, 3),
            "tasks_with_any_reward": int(a.get("rewarded", 0)), "tasks_solved": int(a.get("solved", 0)),
            "value_only_grader_pass_rate": round(a["value_only_pass"] / n, 3),
            "blocked_by": {k: round(v, 3) for k, v in blocked_by},
        })
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(rows, f, indent=1)
    print(f"{'attack':30s} {'tasks':>5s} {'full reward':>11s} {'value-only pass':>15s}  blocked by (share of tasks)")
    for r in rows:
        bb = ", ".join(f"{k} {v:.0%}" for k, v in r["blocked_by"].items())
        print(f"{r['attack']:30s} {r['tasks']:5d} {r['mean_reward_full_grader']:11.3f} "
              f"{r['value_only_grader_pass_rate']:15.0%}  {bb}")


if __name__ == "__main__":
    main()
