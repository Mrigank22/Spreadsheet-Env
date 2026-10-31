"""How big is the "typed constant" hole left by HACK_LOG #24?

Since #24, a target that is not a check row may be typed as a constant when its reference value
never moves: at the base inputs, in every graded scenario, and when any single input is moved
up or down on its own (the structure oracle's sensitivity test). That is right for structural
zeros (the first-year ECF prepayment is zero by contract). It is a hole if the cell *does* move
for other plausible inputs that the grader never tries, e.g. a default flag that no graded
scenario trips. A policy could then learn to type it.

For every task this script lists the targets the grader would accept as typed constants, then
recomputes the reference under fresh random scenarios (same sampler, fresh seeds, local / wide
/ extreme modes). A typable target that moves in any fresh scenario is a genuine hole.

    python scripts/constant_target_audit.py --seeds 2 --workers 4
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spreadsheet_env.grader.grader import Grader, close  # noqa: E402
from spreadsheet_env.grader.scenarios import sample_candidate  # noqa: E402
from spreadsheet_env.parallel import default_workers, pmap  # noqa: E402
from spreadsheet_env.tasks import FAMILIES, ensure_frontier, make_task  # noqa: E402

N_FRESH = 60


def audit(tid):
    task = make_task(tid)
    g = Grader()
    runs = g._reference_runs(task)
    checks = g._check_keys(task)
    inputs = set(task.input_keys) | {fx.target for fx in task.fixups}
    clo = g._reference_closures(task)
    typable = []
    for k in task.target_keys:
        need = clo.get(k, frozenset()) & inputs
        if not need or k in checks:
            continue  # a target with no inputs is a given constant; check rows stay strict
        v0 = runs[0].get(k)
        if not all(close(r.get(k), v0, 1e-9) for r in runs):
            continue
        if any(g._sensitive(task, k, i) for i in need):
            continue
        typable.append(k)
    holes = set()
    if typable:
        cw = task.reference.compile()
        rng = random.Random(f"fresh:{tid}")
        for j in range(N_FRESH):
            sc = sample_candidate(task.inputs, task.fixups, rng, ("local", "wide", "extreme")[j % 3])
            vals = cw.run(sc)
            for k in typable:
                v = vals.get(k)
                if isinstance(v, (int, float)) and not close(v, runs[0].get(k), 1e-6):
                    holes.add(k)
    lab = task.labels
    return {"task_id": tid, "targets": len(task.target_keys), "typable": len(typable), "holes": len(holes),
            "hole_labels": sorted({lab.get(k, str(k)) for k in holes})[:6]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--workers", type=int, default=default_workers())
    ap.add_argument("--out", default="results/constant_target_audit.json")
    args = ap.parse_args()
    ensure_frontier()
    tids = [f"{f}-d{d}-s{s}" for f in sorted(FAMILIES) for d in (5, 4, 3, 2, 1) for s in range(args.seeds)]
    rows = [r for _, r in pmap(audit, tids, args.workers, progress="constant-targets")]
    rows.sort(key=lambda r: r["task_id"])
    tot = {k: sum(r[k] for r in rows) for k in ("targets", "typable", "holes")}
    summary = {"tasks": len(rows), **tot, "tasks_with_holes": sum(r["holes"] > 0 for r in rows),
               "fresh_scenarios_per_task": N_FRESH}
    with open(args.out, "w") as f:
        json.dump({"summary": summary, "tasks": rows}, f, indent=1)
    print(json.dumps(summary))
    for r in rows:
        if r["holes"]:
            print(r["task_id"], r["holes"], r["hole_labels"])


if __name__ == "__main__":
    main()
