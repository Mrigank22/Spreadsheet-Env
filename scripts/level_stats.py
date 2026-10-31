"""Measure how much work each difficulty level demands, per family (no grading, no API).

    python scripts/level_stats.py [results/level_stats.jsonl]     # SEEDS=2 SSE_WORKERS=N
    SUMMARY_ONLY=1 python scripts/level_stats.py                  # re-print the table

written  = cells whose reference content differs from the starting workbook (what the agent must change)
rules    = distinct (row, R1C1 signature) among those cells (distinct formulas to derive)
branch   = IF/MIN/MAX/AND/OR/IRR/INDEX/MATCH calls summed over the distinct rules (conditional logic)
depth    = longest same-period chain of written rows (A feeds B feeds C ... within one column)
tokens   = prompt length in characters / 4
"""
import json
import os
import re
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BRANCH = re.compile(r"\b(IF|MIN|MAX|AND|OR|IRR|INDEX|MATCH)\(")


def measure(tid):
    from spreadsheet_env.tasks import ensure_frontier, make_task
    from spreadsheet_env.session import r1c1_signature
    ensure_frontier()
    t = make_task(tid)
    ref, ini = t.reference, t.initial
    written = []
    for sheet, r, c, raw in ref.cells():
        key = (sheet.casefold(), r, c)
        if isinstance(raw, str) and raw.startswith("=") and ini.raw(key) != raw:
            written.append(key)
    sigs = {}
    for (s, r, c) in written:
        sigs.setdefault((s, r, r1c1_signature(ref.raw((s, r, c)), r, c)), ref.raw((s, r, c)))
    branch = sum(len(BRANCH.findall(f.upper())) for f in sigs.values())
    comp = ref.compile()
    wset = set(written)
    rows = {(s, r) for (s, r, _) in written}
    edges = defaultdict(set)
    for (s, r, c) in written:
        for p in comp.precedents((s, r, c)):
            if p in wset and p[2] == c and (p[0], p[1]) != (s, r):
                edges[(s, r)].add((p[0], p[1]))
    memo, onstack = {}, set()

    def longest(n):
        if n in memo:
            return memo[n]
        onstack.add(n)
        best = 0
        for m in edges[n]:
            if m not in onstack:
                best = max(best, longest(m))
        onstack.discard(n)
        memo[n] = best + 1
        return memo[n]

    sys.setrecursionlimit(10000)
    depth = max((longest(n) for n in rows), default=0)
    return dict(tid=tid, fam=t.family, d=t.difficulty, written=len(written), rows=len(rows), rules=len(sigs),
                branch=branch, depth=depth, tokens=len(t.instructions) // 4, inputs=len(t.inputs),
                circular=bool(ref.iterative), bugs=t.meta.get("n_bugs", len(t.bugs)),
                latent=t.meta.get("n_latent"), canary=t.expect_no_change, steps=t.max_steps)


def summarise(path):
    """Median per (tier, variant, level), as in the README table."""
    from statistics import median

    docs = {"ca", "lpa", "indenture", "charter"}
    groups = defaultdict(list)
    for line in open(path):
        r = json.loads(line)
        fam = r["fam"]
        if fam in ("build", "repair", "dcf", "build_free"):
            tier, var = "core", {"build_free": "free"}.get(fam, fam)
        else:
            dom, var = fam.rsplit("_", 1)
            tier = "document" if dom in docs else "frontier"
        groups[(tier, var, r["d"])].append(r)
    cols = ["written", "rules", "branch", "depth", "tokens", "inputs", "bugs"]
    print(f"{'tier':9}{'variant':8}{'level':>5} " + " ".join(f"{c:>7}" for c in cols))
    for key in sorted(groups, key=lambda k: (["core", "frontier", "document"].index(k[0]), k[1], k[2])):
        g = groups[key]
        print(f"{key[0]:9}{key[1]:8}{key[2]:>5} " + " ".join(f"{median(x[c] for x in g):>7.1f}" for c in cols))


if __name__ == "__main__":
    from spreadsheet_env.tasks import FAMILIES, ensure_frontier
    out = sys.argv[1] if len(sys.argv) > 1 else "results/level_stats.jsonl"
    if os.environ.get("SUMMARY_ONLY"):
        summarise(out)
        sys.exit()
    ensure_frontier()
    seeds = range(int(os.environ.get("SEEDS", "2")))
    tids = [f"{f}-d{d}-s{s}" for f in sorted(FAMILIES) for d in range(1, 6) for s in seeds]
    with ProcessPoolExecutor(int(os.environ.get("SSE_WORKERS", str(max(1, (os.cpu_count() or 2) - 2))))) as ex, \
            open(out, "w") as fh:
        for i, row in enumerate(ex.map(measure, tids, chunksize=2), 1):
            fh.write(json.dumps(row) + "\n")
            if i % 50 == 0:
                print(i, "/", len(tids), flush=True)
    summarise(out)
