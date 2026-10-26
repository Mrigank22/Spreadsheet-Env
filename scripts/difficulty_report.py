"""Aggregate evaluation files into one difficulty table (family x level x policy).

Reads every ``results/eval_*.jsonl`` (multi-turn tool episodes; one row per
episode) and ``results/patch_*.jsonl`` (single-turn; one row per task with k
samples) and prints/saves pass rates with Wilson 95% intervals.

    python scripts/difficulty_report.py --out results/difficulty_report.md
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evaluate import wilson  # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", default="results/difficulty_report.md")
    args = ap.parse_args()
    table = defaultdict(dict)  # (family, level) -> policy -> cell text
    policies = []
    for path in sorted(glob.glob(os.path.join(args.results, "eval_*.jsonl"))):
        pol = os.path.basename(path)[5:-6]
        policies.append(pol)
        by = defaultdict(list)
        for r in load(path):
            by[(r["family"], r["difficulty"])].append(r["solved"])
        for key, xs in by.items():
            k, n = sum(xs), len(xs)
            lo, hi = wilson(k, n)
            table[key][pol] = f"{k}/{n} ({k / n:.0%}; {lo:.0%}-{hi:.0%})"
    for path in sorted(glob.glob(os.path.join(args.results, "patch_*.jsonl"))):
        pol = "patch:" + os.path.basename(path)[6:-6]
        policies.append(pol)
        by = defaultdict(list)
        for r in load(path):
            by[(r["family"], r["difficulty"])].append(r)
        for key, rs in by.items():
            p1 = sum(r["pass_at_1"] for r in rs) / len(rs)
            pk = sum(r["pass_at_k"] for r in rs)
            k = len(rs[0]["samples"])
            table[key][pol] = f"pass@1 {p1:.0%}, pass@{k} {pk}/{len(rs)}"
    lines = ["| family | level | " + " | ".join(policies) + " |",
             "|---|---|" + "---|" * len(policies)]
    for (fam, lvl) in sorted(table):
        lines.append(f"| {fam} | {lvl} | " + " | ".join(table[(fam, lvl)].get(p, "-") for p in policies) + " |")
    text = "\n".join(lines)
    print(text)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
