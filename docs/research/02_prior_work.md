# Prior work and gap analysis

Surveyed 2026-10-25. The purpose is honesty about novelty: what already exists, and what
this environment adds. Sources are linked. Items from 2023–2025 are partly from abstracts.

## What already exists (do not claim these as new)

| Work | Tasks | Grading | Notes |
|---|---|---|---|
| Spreadsheet-RL (arXiv 2605.22642) | 5.9k ExcelForum tasks + 1.7k domain tasks; multi-turn tools | Binary value match after real-Excel (COM) recalc, values compared at 2 decimals | Pasted values pass; no perturbation; Qwen3-4B 12.0→23.4 on SpreadsheetBench |
| SpreadsheetBench v1 / Verified-400 | 912 forum questions; OJ-style test-case sheets | Value match | Input variation applies to the solution *code*, not workbook formulas; Verified is saturated (86–95%) |
| SpreadsheetBench 2 (arXiv 2606.29955) | 321 tasks: 100 financial modeling, 100 debugging (10 injected error types incl. embedded hardcodes) | LibreOffice recalc + golden value match | No formula-vs-value check, no perturbation; Opus 4.6 34.9%, debugging 12.0% |
| BlueFin (arXiv 2605.30907) | 131 finance tasks (DCF, LBO circularity, debt, waterfalls) | An **LLM judge** perturbs an input, recalcs and inspects | Stochastic; non-commercial license; perturbation checks 15–37% pass |
| Vals AI EMB | 103 expert modeling tasks | Exact cells (template) or LLM-judge rubric (scratch); some base/bull/bear toggles | Private; Opus 5.5 75.9% |
| MBABench (arXiv 2605.22664) | 101 ModelOff/FMWC/WSP tasks | LLM judge over a 129-check rubric (~20 deterministic) | Source IP risk |
| FrontierFinance, Halluminate Diligence Bench | Long-horizon finance tasks | Expert / agentic rubric | Mostly non-deterministic, private |
| FormulaGym (OpenEnv community) | Enron workbooks; rebuild / repair a single formula | LibreOffice recalc on real and perturbed inputs | Single-formula granularity; Qwen3.5-2B 2→34% |
| fin-model-edits (GitHub, 2026-10-11) | 540 generated three-statement + DCF edit/repair tasks | LibreOffice recalc, reference match under perturbation, inputs_unchanged, 50 red-team cheats, one cash-plug check | Opus/Sonnet 5.5 score 100% (saturated) |
| ledgerlab (GitHub, 2026-10-22) | Operating model + DCF repair | Custom formula engine, K=3 perturbations, collateral-damage penalty | Saturated (1.00); three-statement, balance checks and debt listed as future work |
| filing-update-evals | 39 10-Q update tasks | LibreOffice perturbation grading | Opus 5.5 97% |
| Poon et al. 2014/2017 | End-user spreadsheets | Metamorphic testing (pre-LLM) | Shows metamorphic relations work for spreadsheets |

Taken together, prior work already includes:
- recalculation as a reward;
- input perturbation against a golden reference;
- a custom Excel-free engine;
- an OpenEnv spreadsheet environment;
- RL on spreadsheets;
- grader red-teaming.

## Gaps this environment targets

1. **Reference-free oracles.** Accounting identities hold in *every* perturbed scenario:
   - the balance sheet balances;
   - ending cash on the cash-flow statement equals balance-sheet cash;
   - corkscrew roll-forwards close;
   - retained earnings stay continuous.

   Directional and metamorphic relations are checked too (WACC↑ ⇒ EV↓, a sensitivity grid
   that is monotone and self-consistent, scaling relations). No prior work uses these as a
   systematic grading term. They also catch bugs in the generator's own references (the
   MedCalc-Bench lesson).
2. **Deterministic grading of free-layout builds.** The agent may lay out the model as it
   likes and declares an *output contract*. The grader perturbs locked inputs and reads the
   declared outputs. Today, scratch builds are graded by LLM judges or by fixed-template
   cell match.
3. **Circular debt schedules (iterative calculation) and sensitivity grids, graded
   deterministically.**
   - Circular schedules are compared by the fixed point they converge to.
   - Each grid cell is checked by recomputing the agent's *own* model at that grid point.
4. **Latent-bug repair.** These bugs leave base-case values correct (stale hardcodes,
   anchoring errors, IF branches that don't fire at base). A value-only grader rewards the
   do-nothing agent on them. We quantify this directly.
5. **A published RL ablation.** A value-only reward vs the full grader, measuring hacking
   (do-nothing, hardcoding, plugging) on held-out tasks.
6. **Unsaturated difficulty with deterministic grading.** Community environments saturate
   for frontier models. We report pass@k by difficulty for a small, a mid-sized and a
   frontier model.
7. **A clean license.** All tasks are generated, so no forum or IP-encumbered data is used.

### Status of each gap (2026-10-31)

| # | Gap | Status |
|---|---|---|
| 1 | Reference-free oracles | **Done.** Identities and homogeneity alone detect 77.5% of latent bugs (kill matrix) |
| 2 | Deterministic grading of free-layout builds | **Done.** Outputs contract, 0 false positives on equivalent rewrites |
| 3 | Circular schedules and sensitivity grids | **Done.** Convergence-gated scenarios; grid checked against the agent's own model |
| 4 | Latent-bug repair | **Done.** A value-only grader detects 0.1% of the 697 latent bugs; the full grader 100% |
| 5 | Published RL ablation | **Not done.** A 100-demo SFT pilot did not move a 1.7B model; the run needs ~1k demos or a larger GPU |
| 6 | Unsaturated difficulty for frontier models | **Not achieved.** Claude Opus 5.5 (medium effort) solved every unambiguous task across 130 calibrated tasks, document tier included. Small models score 0%; no mid-size model was measured |
| 7 | Clean license | **Done.** Every task is generated; Apache-2.0 |

Added beyond the original list: legal-document specs (credit agreement, LPA, indenture, charter)
generated clause by clause from the reference's parameters, nine structured-finance domains, and
an adaptive red-team in which a frontier model that knows the grader tries to earn reward
without doing the task (`scripts/red_team.py`, README).

## Sources

- https://arxiv.org/abs/2605.22642
- https://github.com/RUCKBReasoning/SpreadsheetBench
- https://shortcut.ai/blog/posts/spreadsheetbench-verified
- https://arxiv.org/abs/2606.29955
- https://arxiv.org/abs/2605.30907
- https://www.vals.ai/benchmarks/emb
- https://github.com/namkoong-lab/MBABench
- https://arxiv.org/abs/2604.05912
- https://www.halluminate.ai/blog/due-diligence-bench
- https://huggingface.co/datasets/piyushgupta53/formulagym-arena
- https://github.com/TanishGudise/fin-model-edits
- https://github.com/cero753/ledgerlab
- https://github.com/TanishGudise/filing-update-evals
- https://vuir.vu.edu.au/33045/
- https://arxiv.org/abs/2512.13168
- https://huggingface.co/docs/openenv/environments/finqa
