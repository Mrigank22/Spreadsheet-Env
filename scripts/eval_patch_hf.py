"""Single-turn (patch mode) evaluation of a local Hugging Face model: pass@k.

The prompt holds the instructions and every non-empty cell of the workbook;
the model answers with one fenced block of ``Sheet!Cell := content`` edits.
Run it with a Python that has torch + transformers (e.g. a training venv):

    python scripts/eval_patch_hf.py --model Qwen/Qwen2.5-Coder-1.5B-Instruct \
        --tasks build:1-2:10 repair:1:10 dcf:1:10 --k 4 --out results/patch_qwen15.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluate import parse_tasks, wilson  # noqa: E402
from spreadsheet_env.agents.runner import grade_patch, patch_prompt  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--adapter", default=None, help="optional PEFT/LoRA adapter directory")
    ap.add_argument("--tasks", nargs="+", default=["build:1:5"])
    ap.add_argument("--split", default="test")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--max-new-tokens", type=int, default=1536)
    ap.add_argument("--batch", type=int, default=2, help="samples generated per forward pass")
    ap.add_argument("--thinking", action="store_true", help="Qwen3: enable thinking mode")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.model)
    tok.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16, device_map="cuda")
    if args.adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()

    ids = parse_tasks(args.tasks, args.split)
    rows = []
    t0 = time.time()
    for tid in ids:
        extra = {"enable_thinking": args.thinking} if "enable_thinking" in (tok.chat_template or "") else {}
        prompt = tok.apply_chat_template([{"role": "user", "content": patch_prompt(tid)}], tokenize=False,
                                         add_generation_prompt=True, **extra)
        enc = tok(prompt, return_tensors="pt").to("cuda")
        samples = []
        for start in range(0, args.k, args.batch):
            n = min(args.batch, args.k - start)
            with torch.no_grad():
                out = model.generate(**enc, max_new_tokens=args.max_new_tokens, do_sample=True,
                                     temperature=args.temperature, top_p=0.95, num_return_sequences=n,
                                     pad_token_id=tok.eos_token_id)
            for seq in out:
                samples.append(tok.decode(seq[enc["input_ids"].shape[1]:], skip_special_tokens=True))
        results = []
        for s in samples:
            res, edits, errs = grade_patch(tid, s)
            results.append({"solved": res.solved, "reward": res.reward, "components": res.components,
                            "n_edits": len(edits), "n_edit_errors": len(errs)})
        row = {"task_id": tid, "family": tid.split("-")[0], "difficulty": int(tid.split("-")[1][1:]),
               "prompt_tokens": int(enc["input_ids"].shape[1]), "samples": results,
               "pass_at_1": sum(r["solved"] for r in results) / len(results),
               "pass_at_k": any(r["solved"] for r in results), "example_completion": samples[0][:3000]}
        rows.append(row)
        with open(args.out, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        print(f"{tid:22s} prompt {row['prompt_tokens']:5d} tok  pass@1 {row['pass_at_1']:.2f}  "
              f"pass@{args.k} {row['pass_at_k']!s:5s}  mean perturb {sum(r['components'].get('perturb', 0) for r in results)/len(results):.2f}"
              f"  ({time.time() - t0:.0f}s)", flush=True)
    by = {}
    for r in rows:
        by.setdefault((r["family"], r["difficulty"]), []).append(r)
    for (fam, d), rs in sorted(by.items()):
        p1 = sum(r["pass_at_1"] for r in rs) / len(rs)
        pk = sum(r["pass_at_k"] for r in rs)
        lo, hi = wilson(pk, len(rs))
        print(f"{fam}/d{d}: pass@1 {p1:.1%}  pass@{args.k} {pk}/{len(rs)} [{lo:.0%},{hi:.0%}]")


if __name__ == "__main__":
    main()
