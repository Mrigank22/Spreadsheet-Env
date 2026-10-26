"""Evaluate a policy on a fixed task set and report pass rates by family/level.

Examples::

    python scripts/evaluate.py --policy reference --tasks build:1-5:4 repair:1-5:4 dcf:1-5:4
    python scripts/evaluate.py --policy anthropic --model claude-opus-5-5 --effort high \
        --tasks build:1-5:6 repair:1-5:6 dcf:1-5:6 --split test --budget-usd 15 --workers 4
    python scripts/evaluate.py --policy hf --model Qwen/Qwen3-1.7B --tasks build:1-2:5

Results are appended to a JSONL file (one line per episode, with transcript)
and summarised with Wilson 95% intervals. Episodes already present in the
output file are skipped, so an interrupted run can be resumed. ``--budget-usd``
is a hard stop: no new episode starts once the spend reaches it.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spreadsheet_env.agents.runner import run_tool_episode  # noqa: E402
from spreadsheet_env.tasks import TEST_SEEDS, TRAIN_SEEDS  # noqa: E402


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def parse_tasks(specs, split):
    seeds = TEST_SEEDS if split == "test" else TRAIN_SEEDS
    ids = []
    for spec in specs:
        fam, levels, n = spec.split(":")
        lo, hi = (int(x) for x in levels.split("-")) if "-" in levels else (int(levels), int(levels))
        for d in range(lo, hi + 1):
            for i in range(int(n)):
                ids.append(f"{fam}-d{d}-s{seeds[i]}")
    return ids


def scripted_episode(job):
    """One scripted-policy episode (CPU-bound); runs in a worker process."""
    from spreadsheet_env.agents.policies import ScriptedPolicy

    policy, task_id = job
    return run_tool_episode(ScriptedPolicy(policy, task_id), task_id).to_json()


def summarise(rows):
    by = defaultdict(list)
    for r in rows:
        by[(r["family"], str(r["difficulty"]))].append(r)
        by[(r["family"], "all")].append(r)
        by[("ALL", "all")].append(r)
    out = {}
    for (fam, d), rs in sorted(by.items()):
        k = sum(r["solved"] for r in rs)
        lo, hi = wilson(k, len(rs))
        out[f"{fam}/d{d}"] = {"n": len(rs), "solved": k, "pass_rate": k / len(rs), "ci95": [lo, hi],
                              "mean_reward": sum(r["reward"] for r in rs) / len(rs),
                              "mean_steps": sum(r["steps"] for r in rs) / len(rs),
                              "cost_usd": sum(r.get("cost_usd", 0) or 0 for r in rs)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True, choices=["anthropic", "hf", "reference", "noop"])
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--fallback", action="store_true",
                    help="enable server-side refusal fallbacks (mixes models; off for calibration)")
    ap.add_argument("--tasks", nargs="+", default=["build:1-5:2", "repair:1-5:2", "dcf:1-5:2"])
    ap.add_argument("--split", default="test", choices=["train", "test"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=None,
                    help="parallel episodes: processes for scripted policies (default: all cores - 2), "
                         "threads for API policies (default 4; API rate limits, not CPU, are the limit)")
    ap.add_argument("--budget-usd", type=float, default=5.0)
    args = ap.parse_args()

    if args.policy == "anthropic":
        tag = f"{args.model}_{args.effort}"
    elif args.policy == "hf":
        tag = args.model.split("/")[-1]
    else:
        tag = args.policy
    out = args.out or f"results/eval_{tag}.jsonl"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    done = set()
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            done = {json.loads(line)["task_id"] for line in f if line.strip()}
    ids = [t for t in parse_tasks(args.tasks, args.split) if t not in done]
    print(f"{len(ids)} episodes to run ({len(done)} already in {out})", flush=True)

    cost = [0.0]
    lock = threading.Lock()
    hf_policy = None
    if args.policy == "hf":
        from spreadsheet_env.agents.policies import HFChatPolicy

        hf_policy = HFChatPolicy(args.model)

    def make_policy(task_id):
        from spreadsheet_env.agents.policies import AnthropicPolicy, ScriptedPolicy

        if args.policy == "anthropic":
            return AnthropicPolicy(args.model, effort=args.effort, fallback=args.fallback)
        if args.policy == "hf":
            return hf_policy
        return ScriptedPolicy(args.policy, task_id)

    def one(task_id):
        with lock:
            if cost[0] >= args.budget_usd:
                return None
        res = run_tool_episode(make_policy(task_id), task_id)
        row = res.to_json()
        if args.policy == "anthropic":
            from spreadsheet_env.agents.policies import usage_cost

            row["cost_usd"] = usage_cost(args.model, res.usage)
            row["model"], row["effort"] = args.model, args.effort
        with lock:
            cost[0] += row.get("cost_usd", 0.0) or 0.0
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, default=str) + "\n")
        return row

    t0 = time.time()
    if args.policy in ("reference", "noop"):
        from spreadsheet_env.parallel import default_workers, pmap

        for _, row in pmap(scripted_episode, [(args.policy, t) for t in ids], args.workers or default_workers()):
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, default=str) + "\n")
            print(f"{row['task_id']:24s} solved={row['solved']!s:5s} reward={row['reward']:.2f}", flush=True)
        ids = []
    workers = (args.workers or 4) if args.policy == "anthropic" else 1
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, t) for t in ids]
        for fut in as_completed(futs):
            row = fut.result()
            if row:
                print(f"{row['task_id']:24s} solved={row['solved']!s:5s} reward={row['reward']:.2f} "
                      f"steps={row['steps']:3d} cost=${row.get('cost_usd', 0) or 0:.3f} total=${cost[0]:.2f} "
                      f"{row['error'][:80]}", flush=True)
    with open(out, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    summary = summarise(rows)
    summary["_meta"] = {"episodes": len(rows), "spent_this_run_usd": round(cost[0], 3),
                        "minutes_this_run": round((time.time() - t0) / 60, 1)}
    with open(out.replace(".jsonl", "_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    for k, v in summary.items():
        if k != "_meta":
            print(f"{k:16s} {v['solved']:3d}/{v['n']:3d} = {v['pass_rate']:4.0%}  "
                  f"[{v['ci95'][0]:.0%}, {v['ci95'][1]:.0%}]  steps {v['mean_steps']:.1f}  ${v['cost_usd']:.2f}")
    print(summary["_meta"])


if __name__ == "__main__":
    main()
