"""Frontier calibration in single-turn patch mode through the Message Batches API.

Why this design: one request per task (the whole workbook is in the prompt and
the model answers with all edits at once) instead of a multi-turn tool loop
(10-30 calls per task, each resending the transcript); and the Batches API,
which takes all requests in ONE submission at 50% of the standard price.
Status checks and result downloads are free.

    python scripts/frontier_batch.py estimate --tasks build:1-5:2 repair:1-5:2 dcf:1-5:2 build_free:1-5:2
    python scripts/frontier_batch.py submit   --tasks ... --model claude-opus-5-5 --effort medium --name opus55_medium
    python scripts/frontier_batch.py collect  --name opus55_medium        # waits, downloads, grades

State (batch id, task list) is kept in results/frontier/<name>_batch.json, so
``collect`` can be re-run at any time without resubmitting anything.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from evaluate import parse_tasks, wilson  # noqa: E402

from spreadsheet_env.agents.policies import PRICES, api_key_source  # noqa: E402
from spreadsheet_env.agents.runner import patch_prompt  # noqa: E402
from spreadsheet_env.parallel import default_workers, pmap_list  # noqa: E402

OUT_DIR = os.path.join(ROOT, "results", "frontier")
BATCH_DISCOUNT = 0.5
SYSTEM = ("You are an expert financial modeller. Follow the task exactly and answer in the requested edit "
          "format. Write live formulas, never typed numbers.")


def _state_path(name):
    return os.path.join(OUT_DIR, f"{name}_batch.json")


def _client():
    import anthropic

    key, _ = api_key_source()
    if not key:
        sys.exit("ANTHROPIC_API_KEY not found (see scripts/check_api_key.py)")
    return anthropic.Anthropic(api_key=key)


def build_prompts(task_ids, workers):
    return pmap_list(patch_prompt, task_ids, workers, progress="prompts")


def estimate(task_ids, prompts, model, out_tokens_low=2000, out_tokens_high=12000):
    """Rough cost range before submitting (input from text length; output is unknown)."""
    p_in, p_out = PRICES[model][0], PRICES[model][1]
    in_tok = sum(len(p) + len(SYSTEM) for p in prompts) / 3.2  # ~3.2 chars/token on this text
    lo = BATCH_DISCOUNT * (in_tok * p_in + len(prompts) * out_tokens_low * p_out) / 1e6
    hi = BATCH_DISCOUNT * (in_tok * p_in + len(prompts) * out_tokens_high * p_out) / 1e6
    return in_tok, lo, hi


def cmd_estimate(args):
    ids = parse_tasks(args.tasks, args.split)
    prompts = build_prompts(ids, args.workers)
    in_tok, lo, hi = estimate(ids, prompts, args.model)
    print(f"{len(ids)} requests, ~{in_tok / 1000:.0f}k input tokens; estimated cost with batch discount: "
          f"${lo:.2f} - ${hi:.2f} (output 2k-12k tokens per answer incl. thinking)")


def cmd_submit(args):
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    os.makedirs(OUT_DIR, exist_ok=True)
    if os.path.exists(_state_path(args.name)):
        sys.exit(f"{_state_path(args.name)} exists: this batch was already submitted (use collect)")
    ids = parse_tasks(args.tasks, args.split)
    prompts = build_prompts(ids, args.workers)
    in_tok, lo, hi = estimate(ids, prompts, args.model)
    print(f"submitting {len(ids)} requests (~{in_tok / 1000:.0f}k input tokens), estimated ${lo:.2f}-${hi:.2f}")
    reqs = [Request(custom_id=f"r{i:04d}", params=MessageCreateParamsNonStreaming(
        model=args.model, max_tokens=args.max_tokens, system=SYSTEM,
        output_config={"effort": args.effort},
        messages=[{"role": "user", "content": p}])) for i, p in enumerate(prompts)]
    batch = _client().messages.batches.create(requests=reqs)
    state = {"batch_id": batch.id, "model": args.model, "effort": args.effort, "split": args.split,
             "tasks": {f"r{i:04d}": tid for i, tid in enumerate(ids)}, "submitted": time.time()}
    with open(_state_path(args.name), "w") as f:
        json.dump(state, f, indent=1)
    print(f"batch {batch.id} submitted ({batch.processing_status}); state saved to {_state_path(args.name)}")


def grade_one(job):
    """Grade one answer with the full grader and the value-only grader; per-bug analysis."""
    tid, text = job
    from eval_repair_bugs import bug_fixed

    from spreadsheet_env.agents.runner import grade_patch
    from spreadsheet_env.grader.grader import Grader
    from spreadsheet_env.session import Session, parse_patch_text
    from spreadsheet_env.tasks import make_task

    res, edits, errs = grade_patch(tid, text)
    vo, _, _ = grade_patch(tid, text, Grader(oracles=["base"], value_only_tolerance=True))
    task = make_task(tid)
    bugs = []
    if task.family.endswith("repair") and task.bugs:
        s = Session(task, max_steps=10_000)
        s.apply_patch(parse_patch_text(text))
        bugs = [{"operator": b["operator"], "effect": b["effect"], "fixed": ok}
                for b, ok in zip(task.bugs, bug_fixed(task, s.wb))]
    return {"solved": res.solved, "reward": res.reward, "components": res.components,
            "value_only_solved": vo.solved, "n_edits": len(edits), "n_edit_errors": len(errs),
            "violations": res.violations[:3], "failing": res.failing[:8],
            "hardcoded_targets": res.diagnostics.get("n_hardcoded_targets", 0),
            "structure_problems": res.diagnostics.get("structure_problems", [])[:3], "bugs": bugs,
            "expect_no_change": task.expect_no_change}


def cmd_collect(args):
    import anthropic

    state = json.load(open(_state_path(args.name)))
    raw_path = os.path.join(OUT_DIR, f"{args.name}_raw.jsonl")
    if args.from_raw:
        rows = [json.loads(line) for line in open(raw_path, encoding="utf-8")]
        return grade_rows(args, state, rows)
    client = _client()
    while True:
        try:
            b = client.messages.batches.retrieve(state["batch_id"])
        except (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.InternalServerError) as e:
            # a network blip must not kill a long wait; status checks are free, just retry
            print(f"[{time.strftime('%H:%M:%S')}] status check failed ({type(e).__name__}); retrying", flush=True)
            time.sleep(30)
            continue
        c = b.request_counts
        print(f"[{time.strftime('%H:%M:%S')}] {b.processing_status}: processing {c.processing}, "
              f"succeeded {c.succeeded}, errored {c.errored}", flush=True)
        if b.processing_status == "ended" or not args.wait:
            break
        time.sleep(args.poll)
    if b.processing_status != "ended":
        return
    rows = []
    with open(raw_path, "w", encoding="utf-8") as raw:
        for r in client.messages.batches.results(state["batch_id"]):
            tid = state["tasks"][r.custom_id]
            row = {"task_id": tid, "custom_id": r.custom_id, "result_type": r.result.type}
            if r.result.type == "succeeded":
                m = r.result.message
                row["text"] = "".join(x.text for x in m.content if x.type == "text")
                row["stop_reason"] = m.stop_reason
                u = m.usage
                row["usage"] = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                                "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
                                "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0}
            raw.write(json.dumps(row) + "\n")
            rows.append(row)
    grade_rows(args, state, rows)


def grade_rows(args, state, rows):
    ok = [r for r in rows if r["result_type"] == "succeeded"]
    graded = pmap_list(grade_one, [(r["task_id"], r["text"]) for r in ok], args.workers, progress="grading")
    p = PRICES[state["model"]]
    out_path = os.path.join(OUT_DIR, f"{args.name}.jsonl")
    total_cost = 0.0
    with open(out_path, "w", encoding="utf-8") as f:
        for r, g in zip(ok, graded):
            u = r["usage"]
            cost = BATCH_DISCOUNT * (u["input_tokens"] * p[0] + u["output_tokens"] * p[1]
                                     + u["cache_read_input_tokens"] * p[2]
                                     + u["cache_creation_input_tokens"] * p[3]) / 1e6
            total_cost += cost
            fam, lvl = r["task_id"].split("-")[0], int(r["task_id"].split("-")[1][1:])
            f.write(json.dumps({"task_id": r["task_id"], "family": fam, "difficulty": lvl, **g,
                                "stop_reason": r["stop_reason"], "usage": u, "cost_usd": cost,
                                "text": r["text"]}) + "\n")
    summarise(out_path, state, total_cost, len(rows) - len(ok))


def summarise(path, state, total_cost, n_failed):
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    by = {}
    for r in rows:
        by.setdefault((r["family"], r["difficulty"]), []).append(r)
        by.setdefault((r["family"], "all"), []).append(r)
        by.setdefault(("ALL", "all"), []).append(r)
    print(f"\n{state['model']} effort={state['effort']} ({state['split']} split), {len(rows)} graded, "
          f"{n_failed} failed requests, total cost ${total_cost:.2f}")
    print(f"{'cell':18s} {'solved':>8s} {'95% CI':>12s} {'value-only':>10s} {'out tok':>8s}")
    summary = {}
    for (fam, lvl), rs in sorted(by.items(), key=lambda x: (x[0][0], str(x[0][1]))):
        k, n = sum(r["solved"] for r in rs), len(rs)
        lo, hi = wilson(k, n)
        vo = sum(r["value_only_solved"] for r in rs)
        ot = sum(r["usage"]["output_tokens"] for r in rs) / n
        summary[f"{fam}/d{lvl}"] = {"solved": k, "n": n, "ci95": [lo, hi], "value_only_solved": vo,
                                   "mean_output_tokens": ot}
        print(f"{fam + '/d' + str(lvl):18s} {k:3d}/{n:<3d}  [{lo:4.0%},{hi:4.0%}] {vo:6d}/{n:<3d} {ot:8.0f}")
    bugs = [b for r in rows for b in r["bugs"]]
    for eff in ("visible", "latent"):
        bb = [b for b in bugs if b["effect"] == eff]
        if bb:
            print(f"repair bugs fixed ({eff}): {sum(b['fixed'] for b in bb)}/{len(bb)}")
    summary["_meta"] = {"model": state["model"], "effort": state["effort"], "total_cost_usd": total_cost,
                        "failed_requests": n_failed,
                        "bugs_fixed": {e: [sum(b["fixed"] for b in bugs if b["effect"] == e),
                                           sum(1 for b in bugs if b["effect"] == e)] for e in ("visible", "latent")}}
    with open(path.replace(".jsonl", "_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("estimate", "submit"):
        p = sub.add_parser(name)
        p.add_argument("--tasks", nargs="+", required=True)
        p.add_argument("--split", default="test")
        p.add_argument("--model", default="claude-opus-5-5")
        p.add_argument("--effort", default="medium")
        p.add_argument("--max-tokens", type=int, default=32000)
        p.add_argument("--name", default="opus55_medium")
        p.add_argument("--workers", type=int, default=default_workers())
    p = sub.add_parser("collect")
    p.add_argument("--name", default="opus55_medium")
    p.add_argument("--wait", action="store_true", help="poll until the batch ends")
    p.add_argument("--poll", type=int, default=180, help="seconds between (free) status checks")
    p.add_argument("--workers", type=int, default=default_workers())
    p.add_argument("--from-raw", action="store_true",
                   help="grade the already-downloaded <name>_raw.jsonl (offline; e.g. after a crash)")
    args = ap.parse_args()
    {"estimate": cmd_estimate, "submit": cmd_submit, "collect": cmd_collect}[args.cmd](args)


if __name__ == "__main__":
    main()
