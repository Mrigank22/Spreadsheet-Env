"""Experiment: which oracle detects which kind of spreadsheet bug?

For many generated models we inject single bugs with every mutation operator
(cell and row scope). Ground truth comes from an *independent* set of 300
random scenarios per task, not from the grader's own scenarios: a mutant
is a real bug if any target cell differs from the reference at the base case
or in any truth scenario. Otherwise it is an equivalent mutant and is dropped.

Each bugged workbook is then submitted to each oracle on its own:

* value_only  - base-case values rounded to 2 dp (SpreadsheetBench-style)
* base        - base-case values, relative tolerance 1e-6
* perturb     - golden match under the task's K selected scenarios
* identities  - reference-free accounting identities in all scenarios
* homogeneity - reference-free currency-scaling relation
* static      - hard-coded target cell or jammed literal (syntactic)
* full        - the shipped grader (all oracles)

It also measures how scenario *selection* (coverage-guided vs random) and the
number of scenarios K affect detection of latent bugs.

    python scripts/exp_kill_matrix.py --seeds 40 --out results/kill_matrix.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spreadsheet_env.grader.grader import Grader, close  # noqa: E402
from spreadsheet_env.parallel import default_workers, pmap  # noqa: E402
from spreadsheet_env.grader.scenarios import sample_candidate, select_scenarios, _valid  # noqa: E402
from spreadsheet_env.tasks.mutations import OPERATORS, propose  # noqa: E402
from spreadsheet_env.tasks.repair import repair_task  # noqa: E402

ORACLES = {
    "value_only": Grader(oracles=["base"], value_only_tolerance=True),
    "base": Grader(oracles=["base"]),
    "perturb": Grader(oracles=["perturb"]),
    "identities": Grader(oracles=["identities"]),
    "homogeneity": Grader(oracles=["homogeneity"]),
    "full": Grader(),
}


def truth_scenarios(task, n, seed):
    rng = random.Random(f"truth:{seed}")
    cw = task.reference.compile()
    out = []
    modes = ["local", "wide", "single"]
    i = 0
    while len(out) < n and i < n * 3:
        sc = sample_candidate(task.inputs, task.fixups, rng, modes[i % 3])
        i += 1
        if _valid(cw.run(sc), task.target_keys):
            out.append(sc)
    return out


def run_task(job):
    """All mutants of one (level, seed) model; runs in a worker process."""
    d, s, n_mut, n_truth = job
    rows = []
    sel_hits = defaultdict(lambda: [0, 0])  # (method, K) -> [detected latent, total latent]
    task = repair_task(10_000 + s, d, force_canary=True)  # a correct model to mutate
    spec, lay = task.meta["spec"], task.meta["layout"]
    ref = task.reference
    ref_cw = ref.compile()
    truth = truth_scenarios(task, n_truth, s)
    ref_truth = [ref_cw.run()] + [ref_cw.run(sc) for sc in truth]
    base_vals = ref_truth[0]
    # alternative scenario sets for the selection experiment
    alt = {}
    for method in ("coverage", "random"):
        for k in (1, 2, 4, 8):
            alt[(method, k)] = select_scenarios(
                ref, task.inputs, task.fixups, task.target_keys,
                random.Random(f"sel:{method}:{k}:{s}"), k=k, coverage=(method == "coverage"),
                scale_factor=None)
    rng = random.Random(f"mut:{d}:{s}")
    lines = [ln.id for ln in spec.lines if ln.fc is not None and ln.kind != "check"]
    made = 0
    tries = 0
    while made < n_mut and tries < n_mut * 6:
        tries += 1
        op = rng.choice(list(OPERATORS))
        scope = "row" if (op == "ANCHOR_DROP" or rng.random() < 0.4) else "cell"
        mut = propose(op, scope, rng.choice(lines), ref, spec, lay, base_vals, rng)
        if mut is None:
            continue
        wb = ref.copy()
        for k, v in mut.cells.items():
            wb.set_rc(wb.sheet_name(k[0]), k[1], k[2], v)
        cw = wb.compile()
        if cw.problems() or (cw.cyclic and not ref.iterative):
            continue
        runs = [cw.run()] + [cw.run(sc) for sc in truth]
        if any(not isinstance(runs[0].get(k), (float, bool, str)) for k in task.target_keys):
            continue  # error values at base: trivially visible, excluded
        visible = any(not close(runs[0].get(k), base_vals.get(k)) for k in task.target_keys)
        real = visible or any(
            not close(r.get(k), rr.get(k)) for r, rr in zip(runs[1:], ref_truth[1:]) for k in task.target_keys)
        if not real:
            continue
        made += 1
        res = {name: not g.grade(task, wb).solved for name, g in ORACLES.items()}
        hard = any(k in mut.cells and not (isinstance(mut.cells[k], str)) for k in task.target_keys)
        jam = bool(Grader().grade(task, wb).diagnostics.get("jammed_literals"))
        res["static"] = hard or jam
        res["reference_free"] = res["identities"] or res["homogeneity"]
        rows.append({"level": d, "seed": s, "operator": mut.operator, "category": mut.category,
                     "scope": mut.scope, "effect": "visible" if visible else "latent", "detected": res})
        if not visible:
            for (method, k), scs in alt.items():
                ref_runs = [ref_cw.run(sc) for sc in scs]
                hit = any(not close(cw.run(sc).get(t), rr.get(t))
                          for sc, rr in zip(scs, ref_runs) for t in task.target_keys)
                sel_hits[(method, k)][0] += hit
                sel_hits[(method, k)][1] += 1
    return rows, dict(sel_hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--levels", default="2,3,4,5")
    ap.add_argument("--mutants-per-task", type=int, default=24)
    ap.add_argument("--truth", type=int, default=300)
    ap.add_argument("--workers", type=int, default=default_workers())
    ap.add_argument("--out", default="results/kill_matrix.json")
    args = ap.parse_args()
    levels = [int(x) for x in args.levels.split(",")]

    t0 = time.time()
    jobs = []
    for d in levels:
        n_seeds = args.seeds if d < 5 else max(4, args.seeds // 4)
        n_truth = args.truth if d < 5 else args.truth // 3
        jobs += [(d, s, args.mutants_per_task, n_truth) for s in range(n_seeds)]
    jobs.sort(key=lambda j: -j[0])  # slowest (circular, level 5) first: shorter makespan
    print(f"{len(jobs)} models on {args.workers} worker processes", flush=True)
    rows = []
    sel_hits = defaultdict(lambda: [0, 0])
    for i, (r, hits) in pmap(run_task, jobs, args.workers, progress="kill-matrix"):
        rows += r
        for key, (a, b) in hits.items():
            sel_hits[key][0] += a
            sel_hits[key][1] += b
    rows.sort(key=lambda r: (r["level"], r["seed"]))

    # aggregate
    def rate(sub, oracle):
        return sum(r["detected"][oracle] for r in sub) / len(sub) if sub else None

    oracles = list(ORACLES) + ["static", "reference_free"]
    summary = {"n_mutants": len(rows), "seconds": round(time.time() - t0)}
    for eff in ("visible", "latent", "all"):
        sub = [r for r in rows if eff == "all" or r["effect"] == eff]
        summary[eff] = {"n": len(sub), **{o: rate(sub, o) for o in oracles}}
    by_op = {}
    for op in sorted({r["operator"] for r in rows}):
        sub = [r for r in rows if r["operator"] == op]
        by_op[op] = {"n": len(sub), "latent_share": sum(r["effect"] == "latent" for r in sub) / len(sub),
                     **{o: rate(sub, o) for o in oracles}}
    summary["by_operator"] = by_op
    summary["scenario_selection_latent_recall"] = {
        f"{m}_K{k}": (v[0] / v[1] if v[1] else None) for (m, k), v in sorted(sel_hits.items())}
    summary["scenario_selection_n_latent"] = next(iter(sel_hits.values()))[1] if sel_hits else 0
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({"summary": summary, "rows": rows}, f, indent=1)

    print(json.dumps({k: v for k, v in summary.items() if k != "by_operator"}, indent=1))
    print(f"{'operator':16s} {'n':>4s} {'latent':>6s} " + " ".join(f"{o[:9]:>9s}" for o in oracles))
    for op, v in by_op.items():
        print(f"{op:16s} {v['n']:4d} {v['latent_share']:6.2f} " + " ".join(f"{v[o]:9.2f}" for o in oracles))


if __name__ == "__main__":
    main()
