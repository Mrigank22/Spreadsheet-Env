"""Experiment: does the grader accept correct-but-differently-written models?

For each task, the reference formulas of every target cell are rewritten with
random semantics-preserving transformations (commutation, a-b -> a+(-b),
SUM -> explicit addition, MAX(0,x) -> IF(x>0,x,0), MIN -> IF, AVERAGE ->
(a+b)/2, extra $ anchors, and moving logic into helper cells). Every rewrite is
correct, so every one must be solved. The false-positive rate is the share
that is not, broken down by oracle.

    python scripts/exp_false_positives.py --seeds 25
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spreadsheet_env.grader.equivalence import equivalent_rewrite  # noqa: E402
from spreadsheet_env.grader.grader import Grader  # noqa: E402
from spreadsheet_env.parallel import default_workers, pmap  # noqa: E402
from spreadsheet_env.tasks import make_task  # noqa: E402


def run_task(job):
    """Grade every equivalent rewrite of one task; runs in a worker process."""
    task_id, variants = job
    g = Grader()
    t = make_task(task_id)
    n = 0
    fails = Counter()
    examples = []
    for v in range(variants):
        rng = random.Random(f"eq:{t.task_id}:{v}")
        # every cell the agent has to write: the targets, plus reference cells that
        # are empty in the task (the whole model in free-layout builds)
        to_write = set(t.target_keys) | {k for k in t.reference.snapshot() if t.initial.raw(k) is None}
        full = equivalent_rewrite(t.reference, sorted(to_write), rng)
        # keep locked cells exactly as given; only written cells and helpers change
        sub = t.initial.copy()
        for k in to_write:
            sub.set_rc(sub.sheet_name(k[0]), k[1], k[2], full.raw(k))
        for sheet, r, c, raw in full.cells():
            key = (sheet.casefold(), r, c)
            if t.initial.raw(key) is None and t.reference.raw(key) is None:
                sub.set_rc(sheet, r, c, raw)  # helper cells
        res = g.grade(t, sub)
        n += 1
        if not res.solved:
            for comp, val in res.components.items():
                if val < 1:
                    fails[comp] += 1
            examples.append({"task": t.task_id, "variant": v, "summary": res.summary(),
                             "diag": {k: res.diagnostics.get(k) for k in ("structure_problems", "identities_broken")}})
    return n, fails, examples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--variants", type=int, default=3)
    ap.add_argument("--workers", type=int, default=default_workers())
    ap.add_argument("--out", default="results/false_positives.json")
    ap.add_argument("--families", default="core",
                    help="'core' (the original families), 'frontier' (every frontier family) or a comma list")
    ap.add_argument("--levels", default="1,2,3,4,5")
    args = ap.parse_args()
    if args.families == "core":
        fams = ("build", "repair", "dcf", "build_free")
    elif args.families == "frontier":
        from spreadsheet_env.frontier import all_families
        fams = tuple(all_families())
    else:
        fams = tuple(args.families.split(","))
    jobs = [(f"{fam}-d{d}-s{s}", args.variants)
            for fam in fams for d in (int(x) for x in args.levels.split(","))
            for s in range(args.seeds if d < 5 else max(3, args.seeds // 4))]
    jobs.sort(key=lambda j: -int(j[0].split("-d")[1][0]))  # level 5 (circular, slowest) first
    n = 0
    fails = Counter()
    examples = []
    for _, (k, f, ex) in pmap(run_task, jobs, args.workers, progress="false-positives"):
        n += k
        fails.update(f)
        examples += ex
    out = {"variants_graded": n, "failed_by_oracle": dict(fails), "examples": examples[:20]}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"graded {n} equivalent rewrites; failures by oracle: {dict(fails) or 'none'}")
    for e in examples[:5]:
        print(e["task"], e["summary"], e["diag"])


if __name__ == "__main__":
    main()
