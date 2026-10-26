"""GRPO (TRL) in single-turn patch mode, with a configurable reward grader.

The reward ablation trains the same starting model twice, changing only the
grader that produces the reward:

    # full grader (perturbation + identities + structure + ...)
    python scripts/train_grpo_patch.py --model <sft-or-base> --reward full --out runs/grpo_full
    # value-only grader (base-case values, 2 dp; what value-matching benchmarks use)
    python scripts/train_grpo_patch.py --model <sft-or-base> --reward value_only --out runs/grpo_value

Whatever the training reward, the *full* grader's verdict is logged as a
zero-weight monitoring signal (``full_solved``), and so are the value-only
verdict and the number of edits, so reward hacking (training reward up, true
correctness flat) is visible in the logs as it happens.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from spreadsheet_env.agents.runner import grade_patch, patch_prompt  # noqa: E402
from spreadsheet_env.grader.grader import ALL_ORACLES, Grader  # noqa: E402
from spreadsheet_env.parallel import default_workers, pmap_list  # noqa: E402
from spreadsheet_env.session import parse_patch_text  # noqa: E402
from spreadsheet_env.tasks import TRAIN_SEEDS  # noqa: E402
from spreadsheet_env import trl_env  # noqa: E402

FULL = Grader()
VALUE_ONLY = Grader(oracles=["base"], value_only_tolerance=True)


def _text(c):
    return c if isinstance(c, str) else c[-1]["content"]


def full_solved(prompts=None, completions=None, task_id=None, **kw):
    return [float(grade_patch(t, _text(c), FULL)[0].solved) for c, t in zip(completions, task_id)]


def value_only_solved(prompts=None, completions=None, task_id=None, **kw):
    return [float(grade_patch(t, _text(c), VALUE_ONLY)[0].solved) for c, t in zip(completions, task_id)]


def n_edits(prompts=None, completions=None, task_id=None, **kw):
    return [float(len(parse_patch_text(_text(c)))) for c in completions]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--reward", choices=["full", "value_only"], default="full")
    ap.add_argument("--tasks", nargs="+", default=["repair:1-3"], help="family:levels")
    ap.add_argument("--n-train", type=int, default=400)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-steps", type=int, default=200)
    ap.add_argument("--num-generations", type=int, default=6)
    ap.add_argument("--grad-accum", type=int, default=6)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--max-completion", type=int, default=640)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--beta", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--workers", type=int, default=default_workers(), help="processes for dataset building")
    args = ap.parse_args()

    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer

    if args.reward == "full":
        trl_env.set_reward_oracles(ALL_ORACLES)
    else:
        trl_env.set_reward_oracles(["base"], value_only_tolerance=True)

    from train_sft_patch import render_prompt

    tok = AutoTokenizer.from_pretrained(args.model, padding_side="left")
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    rng = random.Random(args.seed)
    tids = []
    for spec in args.tasks:
        fam, levels = spec.split(":")
        lo, hi = (int(x) for x in levels.split("-")) if "-" in levels else (int(levels), int(levels))
        for _ in range(args.n_train):
            tids.append(f"{fam}-d{rng.randint(lo, hi)}-s{rng.choice(TRAIN_SEEDS[:50_000])}")  # SFT uses 50k+
    # build prompts on every core (task generation is CPU-bound), template in the parent
    texts = pmap_list(patch_prompt, tids, args.workers, progress="grpo-data")
    rows = [{"prompt": render_prompt(tok, args.model, tid, text), "task_id": tid} for tid, text in zip(tids, texts)]
    rng.shuffle(rows)
    ds = Dataset.from_list(rows)

    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16)
    peft_config = LoraConfig(r=args.lora_r, lora_alpha=2 * args.lora_r, lora_dropout=0.0, task_type="CAUSAL_LM",
                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj",
                                             "down_proj"])
    cfg = GRPOConfig(
        output_dir=args.out, max_steps=args.max_steps, learning_rate=args.lr, warmup_steps=5,
        per_device_train_batch_size=1, gradient_accumulation_steps=args.grad_accum,
        num_generations=args.num_generations, max_completion_length=args.max_completion,
        temperature=1.0, beta=args.beta, loss_type="dapo", scale_rewards="group",
        gradient_checkpointing=True, bf16=True, logging_steps=1, save_steps=25, save_total_limit=4,
        report_to="none", seed=args.seed, log_completions=False, mask_truncated_completions=True,
        reward_weights=[1.0, 0.0, 0.0, 0.0],
    )
    trainer = GRPOTrainer(
        model=model, processing_class=tok, args=cfg, train_dataset=ds, peft_config=peft_config,
        reward_funcs=[trl_env.patch_reward, full_solved, value_only_solved, n_edits],
    )
    trainer.train(resume_from_checkpoint=True if args.resume else None)
    trainer.save_model(args.out)
    with open(os.path.join(args.out, "log_history.json"), "w") as f:
        json.dump(trainer.state.log_history, f, indent=1)
    with open(os.path.join(args.out, "run_args.json"), "w") as f:
        json.dump(vars(args), f, indent=1)


if __name__ == "__main__":
    main()
