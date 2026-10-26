"""Per-bug evaluation of repair tasks: which bugs (visible vs latent) get fixed?

For held-out repair tasks, sample k answers (patch mode) from a local model and
score each injected bug separately: a bug is *fixed* if every cell it touched
matches the reference in the base case and every grading scenario. This is the
measurement for the reward ablation: a policy trained on a value-only reward
gets no signal for latent bugs, so it should fix visible bugs but not latent
ones.

    python scripts/eval_repair_bugs.py --model runs/grpo_full/merged --levels 1-3 --n 20 --k 4 \
        --out results/bugs_grpo_full.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spreadsheet_env.agents.runner import grade_patch  # noqa: E402
from spreadsheet_env.grader.grader import close  # noqa: E402
from spreadsheet_env.session import Session, parse_patch_text  # noqa: E402
from spreadsheet_env.tasks import TEST_SEEDS, make_task  # noqa: E402


def bug_fixed(task, wb) -> list:
    """For each injected bug: is every cell it touched correct in all runs?"""
    cw, rcw = wb.compile(), task.reference.compile()
    runs = [(cw.run(), rcw.run())] + [(cw.run(sc), rcw.run(sc)) for sc in task.scenarios]
    bug_cells = task.meta.get("bug_cells", [])
    out = []
    for b in task.bugs:
        cells = [k for k in bug_cells if task.labels.get(k) in b["cells"]]
        out.append(all(close(a.get(k), r.get(k)) for a, r in runs for k in cells))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--levels", default="1-3")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--max-new-tokens", type=int, default=640)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from train_sft_patch import render_prompt

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16, device_map="cuda").eval()
    lo, hi = (int(x) for x in args.levels.split("-"))
    stats = defaultdict(lambda: [0, 0])
    per_task = []
    for d in range(lo, hi + 1):
        for i in range(args.n):
            tid = f"repair-d{d}-s{TEST_SEEDS[i]}"
            task = make_task(tid)
            enc = tok(render_prompt(tok, args.model, tid), return_tensors="pt").to("cuda")
            with torch.no_grad():
                out = model.generate(**enc, max_new_tokens=args.max_new_tokens, do_sample=True, temperature=0.8,
                                     top_p=0.95, num_return_sequences=args.k, pad_token_id=tok.eos_token_id)
            solved = 0
            for seq in out:
                text = tok.decode(seq[enc["input_ids"].shape[1]:], skip_special_tokens=True)
                res, edits, _ = grade_patch(tid, text)
                solved += res.solved
                s = Session(task, max_steps=10_000)
                s.apply_patch(parse_patch_text(text))
                for b, ok in zip(task.bugs, bug_fixed(task, s.wb)):
                    stats[(d, b["effect"])][0] += ok
                    stats[(d, b["effect"])][1] += 1
                    stats[("all", b["effect"])][0] += ok
                    stats[("all", b["effect"])][1] += 1
                stats[(d, "solved")][0] += res.solved
                stats[(d, "solved")][1] += 1
                stats[("all", "solved")][0] += res.solved
                stats[("all", "solved")][1] += 1
            per_task.append({"task_id": tid, "solved": solved, "k": args.k,
                             "bugs": [(b["operator"], b["effect"]) for b in task.bugs]})
            print(f"{tid}: solved {solved}/{args.k}  bugs {[b['effect'] for b in task.bugs]}", flush=True)
    summary = {f"{k[0]}/{k[1]}": {"hit": v[0], "n": v[1], "rate": v[0] / v[1] if v[1] else None}
               for k, v in sorted(stats.items(), key=lambda x: str(x[0]))}
    with open(args.out, "w") as f:
        json.dump({"model": args.model, "summary": summary, "tasks": per_task}, f, indent=1)
    for k, v in summary.items():
        print(f"{k:16s} {v['hit']:4d}/{v['n']:4d} = {v['rate']:.1%}" if v["rate"] is not None else k)


if __name__ == "__main__":
    main()
