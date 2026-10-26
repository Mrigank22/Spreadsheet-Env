# Research plan and design record

Started 2026-10-25. Every design decision below names the evidence it rests on. Some
decisions were reversed when the evidence contradicted them; those are listed too.

## 1. Goal

A sellable, research-grade RL environment for **spreadsheet financial modelling**: build,
repair and value models. The defining property is **a grader that holds up under attack,
with documented evidence**, because buyers and the research literature (Epoch, Snorkel,
ImpossibleBench) report that broken graders are the main failure of purchased environments.

## 2. What exists (survey: `docs/research/02_prior_work.md`)

- **Value-match spreadsheet benchmarks**: SpreadsheetBench v1/Verified/v2, Spreadsheet-RL,
  SheetCopilot, OSWorld-Calc. Pasted values pass all of them.
- **Finance-model benchmarks graded by LLM judges or expert rubrics**: BlueFin, Vals EMB
  (scratch mode), MBABench, FrontierFinance, Halluminate. They are stochastic, costly, and
  some are non-commercial or private.
- **Deterministic perturbation graders against a golden workbook**: fin-model-edits,
  ledgerlab, FormulaGym, filing-update-evals. These already exist, so we do not claim them.
  The community versions are saturated by frontier models.

## 3. Resources used

| Resource | Use | License / terms |
|---|---|---|
| Powell, Baker & Lawson (2009) audit; Panko; EuSpRIG; ExceLint; Enron corpus studies | Error taxonomy and sampling weights for the 13 bug operators | Papers (cited) |
| FAST Standard, ICAEW Financial Modelling Code, practitioner guides | Model conventions (consistent rows, corkscrews, no plugs, no embedded constants) | Public |
| formualizer 0.12, ironcalc 0.9, LibreOffice 25.2 | Independent engines to validate our formula engine | MIT/Apache, MPL |
| OpenEnv 0.9 (MCPEnvironment), TRL 1.16 (`environment_factory`, GRPO) | Environment server and training | BSD / Apache |
| Damodaran industry datasets, SEC financial-statement data sets | Planned: calibrate sector driver ranges; real-company historicals | No-strings-attached / public information |

No forum or proprietary spreadsheet data is used. Every task is generated.

## 4. Design and the evidence behind each decision

| Decision | Evidence |
|---|---|
| Own formula engine, validated against three others (not used as the grader) | Needed for branch instrumentation and a strict portable subset. Measured 100% agreement with formualizer (186k cells), ironcalc (138k) and LibreOffice (138k acyclic) |
| Generated models are the source of truth (reasoning-gym pattern) | Reference answers are exact by construction. Identities hold in 600/600 generated models and in every scenario of every task (test) |
| Perturbation grading **plus** reference-free oracles | Kill matrix: value-only grading detects 0.3% of latent bugs; reference-free oracles alone detect 77% of latent bugs without any golden workbook |
| `structure` oracle (dependency graph) | Hack audit found a balancing plug (reward 0.61) and a hard-coded check row (0.78) that no value check can see → both 0.00 |
| Coverage-guided scenario selection | Kill matrix (final, calibrated generator): latent-bug recall at K=1/2/4/8 is 94.8/97.8/99.3/99.9% (coverage) vs 90.7/93.5/96.8/97.7% (random); earlier runs showed the same ordering |
| Parallel execution everywhere (process pools, all cores − 2) | Kill matrix 43 min → 6.9 min; engine cross-check 4.7× more workbooks per second; tests 31 s → 13 s |
| Non-degenerate arms + coverage-directed extra rounds | 2 residual misses (both `MIN(repay, debt)` with debt nearly repaid) traced to an arm that the sampler never reached; fixed (both caught) |
| Damped solver + scenario convergence gate for circular models | 18/210 correct rewrites were rejected → 0/210 |
| 80 candidates even for slow circular models | Measured: 40 candidates lost branch arms on 5/8 models (**speed-up rejected**) |
| Compact (R1C1-style) workbook view | Patch prompts fell from 2–10.6k to 2–5k tokens |
| SFT warm-start before GRPO for small models | Qwen2.5-Coder-1.5B 0/44 and Qwen3-1.7B 0/4 at level 1: no RL signal without it. A 100-demo pilot was not enough (0/12) |
| Sector driver ranges calibrated to Damodaran industry data | Hand-set ranges matched only 20/36 industry values; the calibrated ranges match 36/36 (`docs/research/04_calibration.md`) |
| Zero openings of corkscrews are structural (never perturbed) | 4 of 9 Opus failures in frontier batch v1 came from scenarios that moved openings the term sheet fixes at zero (HACK_LOG #15) |
| `structure` requires only inputs a varying target actually responds to; constant targets keep the syntactic rule | 6 FX answers were correct in every scenario but used the CTA analysis identity, in which assets cancel (#19). Hack #4 (typed-zero check row) stays blocked: regression test, plus the re-run hack audit |
| Ordered input grids stay ordered under perturbation | 4 VC answers read "highest exit" literally (`MAX`) and were failed only because scenarios shuffled the exit grid (#20) |
| Outputs labels = full model-line labels; one cell budget for grader and patch writer | A shortened label hid a sign convention, and a stale 3,000-cell cap dropped six output rows of a correct 60-month model (#21, #22) |
| Every failure of a strong model is audited cell by cell before a pass rate is reported | v2: all 13 raw failures were environment defects. Reference, no-op, paste, expert and rewrite checks had all passed on all 270 tasks, and they do not find these |
| **Document-grade specs** (credit agreement, LPA, indenture, charter) as the next difficulty lever | Across 66 frontier answers every divergence came from interpretation, never from executing a stated rule. So the spec itself is made the hard part. Each document is generated clause by clause from the same parameters as the reference model, which keeps the answer unique |
| Grid thresholds and grid rates stay ordered under perturbation (`Bundle.ascending_scalars`) | A pricing grid whose Level I threshold falls below Level II makes the drafted level definitions contradict each other: an ambiguity created by the grader, not the task |
| Grid thresholds anchored to the closing *net* ratio | Anchoring them to gross leverage left the 50% ECF tier unreached in all 20 base cases; anchoring to the closing First Lien Net Leverage Ratio puts the base case through all three tiers |
| Every quoted caption in a document must exist on the Assumptions sheet (test) | Caption drift between document and workbook would silently create unanswerable tasks; `test_document_captions_exist` checks all 20 document task types |

## 5. Task families (implemented)

- `build` (5 levels)
- `repair` (5 levels; latent bugs, no-bug canaries)
- `dcf` (5 levels; sensitivity grid)
- `build_free` (5 levels; any layout, output contract)

Frontier tier (`spreadsheet_env/frontier/`): 9 domains × build / repair / free × 5 levels = 27 families.

- The domains: LBO, PE waterfall, project finance, ABS, SaaS, VC exit waterfall, FX translation and consolidation, tax provision, consumer-credit roll rates.
- One shared framework turns each domain's line DSL into a task: identities, monotone relations, structural zeros, ordered grids and the Outputs contract (README table).

Document tier (`spreadsheet_env/frontier/documents/`): 4 domains × build / repair / free × 5 levels = 12 families.

- The spec is a generated legal document: alphabetical defined terms, numbered and cross-referenced sections, provisos, distractor clauses, a model-conventions annex, and Schedule 1 = the Assumptions sheet.
- `ca`: credit agreement. Adjusted Term SOFR with a floor; a pricing grid with "Level I until the first financial statements"; an ECF sweep paid the following year and credited to installments in direct order of maturity; a revolver with a minimum-liquidity rule and a fee grid; a cost-savings cap; a greater-of netting limit; HoldCo PIK outside the credit group; a springing covenant with an EBITDA cure, cure limits and a default flag.
- `lpa`: LPA. European waterfall; fees on commitments and then on invested capital; fee offsets carried forward; a GP commitment without fees and with proceeds apportioned first; an after-tax clawback; a carry escrow.
- `indenture`: auto-ABS indenture. Allocations of principal; a reserve account; an OC target with a floor; interest carryover with interest; a sticky CNL trigger stepping up the OC target.
- `charter`: VC charter. Seniority with pari passu classes; accruing dividends forfeited on conversion; broad-based weighted-average anti-dilution; a management carve-out; options.

Planned (roadmap):
- `rollforward`: new actuals arrive, roll the model forward a year;
- real-company historicals from SEC data.

## 6. Evaluation plan

1. Sanity: the reference solves 100%; do-nothing scores ~0; the same seed gives the same
   reward. Done.
2. Grader adequacy: kill matrix, false-positive suite, hack audit, engine cross-check, fuzzing.
   Done.
3. Difficulty calibration: pass@k by family and level for a small open model, a mid model and
   a frontier model.
   - Small models: 0%.
   - **Claude Opus 5.5, medium effort: 40/40 (100%)**, $0.92 via one Batches API submission.
     Levels 1–5 are saturated for frontier models.
   - Frontier tier, Opus 5.5 medium, 2 batches (66 tasks, $2.11). After the cell-level audit: **58 solved, 8 void** (answered under a spec later found ambiguous), **0 genuine failures**. Raw grader verdicts were 21/30 and 23/36; every raw failure was an environment defect (HACK_LOG #15, #16, #19–23).
   - Conclusion: stated rules are executed reliably, however complex. Divergence only ever came from interpretation.
   - Document tier (credit agreement, LPA, indenture, charter), batch v3: 24 tasks, $1.22. Raw verdict 20/24; after the audit **22 solved, 1 void, 1 genuine failure** (the model renamed a locked label, against the stated rules).
     - The other failures were a grader false positive (#24: a structural zero typed as 0) and a spec gap (#25: negative cash in the netting). Opus read #25 both ways in different answers.
   - Conclusion: legal-document specs are interpreted reliably too. Across 130 calibrated answers, the only genuine failure was an instruction-following lapse.
   - The environment's value is the grader, the breadth and the unlimited supply of well-posed tasks, not frontier difficulty. The remaining untested lever is agentic mode with hidden context. A mid-size-model gradient was not measured (the user declined the spend).
4. Training demo, the **reward ablation**: from the same SFT warm-start, GRPO with
   (A) a value-only reward vs (B) the full grader, on repair tasks with latent bugs. Evaluate
   held-out with the full grader, split by visible and latent bugs.
   - Hypothesis: (A) learns visible fixes but not latent ones.
   - Status: an SFT pilot (Qwen3-1.7B, LoRA, 100 demos, 13 optimizer steps, 1 hour on the
     RTX 4060) did not move the model: 0/12 samples on held-out build level 1, still copying
     the format placeholder.
   - Next: ~1k demos with prompts capped at 4.5k tokens. VRAM spilled to shared memory at
     ~6k tokens, so steps slowed from 120 s to 350 s. Or use a rented GPU.

## 7. Reversed or rejected ideas

- **"40 scenario candidates suffice for circular models"**: false (coverage loss); rejected.
- **LibreOffice as a reference engine for circular models**: it does not converge (residual
  0.75); kept only as an acyclic cross-check.
- **Telling the agent nothing about perturbation**: rejected. The rules say "the model will be
  re-calculated with different inputs", because the goal is to train good practice, not to
  trap.
- **A generic format placeholder (`Sheet!Cell`) in the patch prompt**: small models copied it
  literally; replaced with a task-specific example.
- **"Legal-document specs make frontier models fail"**: false.
  - Credit agreements with alphabetical definitions, provisos placed away from their rules, timing rules and distractors: 22/23 non-void answers were solved.
- **"More complex logic makes tasks hard for frontier models"**: false.
  - Sticky triggers, two-pass lock-up releases, circular covenants with equity cures, CECL reversion and valuation-allowance tests, all stated in the term sheet, were solved by Opus 5.5 at medium effort on every unambiguous task.
- **"Reference, no-op, paste, expert and equivalent-rewrite checks certify a task"**: insufficient.
  - All 270 frontier tasks passed them, yet real model answers exposed 7 kinds of environment defect in two batches (HACK_LOG #15, #16, #19–23).
  - Real answers take routes the rewriter never generates: identities instead of plugs, literal readings, realistic conventions.
