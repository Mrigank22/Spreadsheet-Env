"""SFT warm-start on expert patch demonstrations (generated from the references).

Small models (1.5-2B) score 0% on even the easiest tasks out of the box
(``results/patch_*_smoke.jsonl``): they compute numbers by hand or copy the
format placeholder. GRPO needs a non-zero pass rate to get any learning signal,
so we first teach format + basic formula writing with SFT on *build* and
*dcf* tasks (training seeds only), then run RL on a different skill (repair).

    python scripts/train_sft_patch.py --model Qwen/Qwen3-1.7B --out runs/sft_qwen3 \
        --tasks build:1-3 dcf:1-2 --n 300

The LoRA adapter is merged into the base weights and saved under ``<out>/merged``
so GRPO can start from it.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from spreadsheet_env.agents.demos import expert_patch  # noqa: E402
from spreadsheet_env.agents.runner import patch_prompt  # noqa: E402
from spreadsheet_env.parallel import default_workers, pmap_list  # noqa: E402
from spreadsheet_env.tasks import TRAIN_SEEDS, make_task  # noqa: E402


def render_prompt(tok, model_name: str, task_id: str, text: str | None = None) -> str:
    """Chat-templated patch prompt (templates with a thinking switch, e.g. Qwen3:
    non-thinking mode). Detected from the template itself, so merged/fine-tuned
    checkpoints in arbitrary directories get the same format as their base model.
    ``text``: the already-built patch prompt (built in parallel workers)."""
    extra = {"enable_thinking": False} if "enable_thinking" in (tok.chat_template or "") else {}
    content = text if text is not None else patch_prompt(task_id)
    return tok.apply_chat_template([{"role": "user", "content": content}], tokenize=False,
                                   add_generation_prompt=True, **extra)


def prompt_and_demo(task_id: str):
    """(patch prompt, expert answer) for one task; CPU-bound, runs in a worker process."""
    return patch_prompt(task_id), expert_patch(make_task(task_id))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", nargs="+", default=["build:1-3", "dcf:1-2"])
    ap.add_argument("--n", type=int, default=300, help="examples per family spec")
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--max-length", type=int, default=7000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=default_workers(), help="processes for dataset building")
    args = ap.parse_args()

    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    rng = random.Random(args.seed)
    tids = []
    for spec in args.tasks:
        fam, levels = spec.split(":")
        lo, hi = (int(x) for x in levels.split("-")) if "-" in levels else (int(levels), int(levels))
        for _ in range(args.n):
            # seeds 50_000+ are reserved for SFT so they never overlap GRPO training prompts
            tids.append(f"{fam}-d{rng.randint(lo, hi)}-s{rng.choice(TRAIN_SEEDS[50_000:])}")
    # task generation is CPU-bound: build prompts and expert answers on every core
    built = pmap_list(prompt_and_demo, tids, args.workers, progress="sft-data")
    # prompts are templated here (same function as GRPO uses) so both stages see
    # byte-identical prompt formats
    rows = [{"prompt": render_prompt(tok, args.model, tid, text), "completion": demo + tok.eos_token,
             "task_id": tid} for tid, (text, demo) in zip(tids, built)]
    rng.shuffle(rows)
    ds = Dataset.from_list(rows)

    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16)
    peft_config = LoraConfig(r=args.lora_r, lora_alpha=2 * args.lora_r, lora_dropout=0.0, task_type="CAUSAL_LM",
                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj",
                                             "down_proj"])
    cfg = SFTConfig(
        output_dir=args.out, num_train_epochs=args.epochs, learning_rate=args.lr, lr_scheduler_type="cosine",
        warmup_steps=10, per_device_train_batch_size=1, gradient_accumulation_steps=8,
        gradient_checkpointing=True, bf16=True, logging_steps=5, save_steps=100, save_total_limit=2,
        max_length=args.max_length, report_to="none", seed=args.seed, completion_only_loss=True,
    )
    trainer = SFTTrainer(model=model, args=cfg, train_dataset=ds, processing_class=tok, peft_config=peft_config)
    trainer.train()
    trainer.save_model(args.out)
    with open(os.path.join(args.out, "log_history.json"), "w") as f:
        json.dump(trainer.state.log_history, f, indent=1)
    merged = trainer.model.merge_and_unload()
    merged.save_pretrained(os.path.join(args.out, "merged"))
    tok.save_pretrained(os.path.join(args.out, "merged"))
    print("saved", os.path.join(args.out, "merged"))


if __name__ == "__main__":
    main()
