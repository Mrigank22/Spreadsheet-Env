# Spreadsheet Financial-Model Env

![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-Apache--2.0-green)
![tests](https://img.shields.io/badge/tests-345%20passing-brightgreen)
![openenv](https://img.shields.io/badge/OpenEnv-0.9-purple)

An **OpenEnv** reinforcement-learning environment in which an LLM agent **builds, repairs and
values spreadsheet financial models**. The models range from three-statement models and DCFs to
LBO debt schedules, project finance, ABS waterfalls, fund distribution waterfalls, tax provisions,
credit-loss models and FX consolidation. The specification can be a methodology memo, a term
sheet, or a **generated legal document**: a credit agreement, LPA, indenture or certificate of
incorporation.

The reward comes from a **deterministic grader with seven independent oracles**:

- recalculation under coverage-selected input perturbations;
- reference-free accounting identities and metamorphic relations;
- dependency-graph checks that catch hard-codes and balancing plugs.

There is no LLM judge and no Excel. Every claim below has a script that reproduces it, and
every grader defect we found is logged with before/after evidence in
[`docs/HACK_LOG.md`](docs/HACK_LOG.md).

| | |
|---|---|
| Task families | **43** (4 core, 27 frontier term-sheet, 12 legal-document) × 5 levels; unlimited deterministic seeds |
| Grader robustness | 0 of 1,686 correct-but-rewritten models rejected (all tiers); **2,328 / 2,328** injected bugs caught, including all 697 latent ones; every cheating strategy in three hack audits scores **0** |
| Formula engine | 100% agreement with formualizer and ironcalc on 351,714 formula cells, including circular models |
| Frontier calibration | Claude Opus 5.5 (medium effort), 130 tasks, $4.25: every failure was audited at cell level ([results](#calibration-against-a-frontier-model)) |
| Examples | [`docs/examples/`](docs/examples/): full prompts and reference formulas for 8 tasks |

---

## Contents

- [Why this environment](#why-this-environment)
- [Quickstart](#quickstart)
- [Task families](#task-families)
- [The grader](#the-grader) and its [evidence](#evidence)
- [Calibration against a frontier model](#calibration-against-a-frontier-model)
- [Interfaces](#interfaces) · [Repository layout](#repository-layout) · [Reproduce](#reproduce) ·
  [Performance](#performance) · [Known limitations](#known-limitations) · [Roadmap](#roadmap)

## Why this environment

Spreadsheet work is a major professional deliverable (GDPval, Halluminate, Vals AI EMB). Most open
spreadsheet benchmarks grade by **comparing cell values at the given inputs**. That check is
gameable:

| Cheat | Value-only grader | This grader |
|---|---|---|
| Type the right numbers instead of formulas | **accepted (100%)** | rejected |
| Do nothing on a repair task whose bugs are *latent* (right today, wrong when an input changes) | **accepted on 18–30% of repair tasks** | rejected |
| Force the balance sheet with a plug (`cash = L&E − other assets`) | accepted | rejected (`structure`) |
| Overwrite the balance-check row with `0` | accepted | rejected (`structure`) |

Input perturbation of a golden workbook **already exists**: fin-model-edits, ledgerlab,
FormulaGym, SpreadsheetBench 2's debugging set. This project does not claim it (prior work:
[`docs/research/02_prior_work.md`](docs/research/02_prior_work.md)). What it adds:

1. **Reference-free oracles.** Accounting identities hold in every perturbed scenario; a
   currency-homogeneity relation holds; a DCF sensitivity grid is checked against the agent's
   *own* model (data-table semantics); monotonicity relations hold.
2. **A dependency-graph oracle.** It catches what no value check can see: balancing plugs, a
   hard-coded check row whose correct value is always 0, disconnected logic.
3. **Free-layout builds graded deterministically** through an output contract.
4. **Circular models** (interest on average balances), solved by a deterministic fixed-point
   solver.
5. **Latent-bug repair tasks**, with bugs drawn from an evidence-weighted taxonomy of real
   spreadsheet errors ([`docs/research/01_error_taxonomy.md`](docs/research/01_error_taxonomy.md)).
6. **Coverage-guided scenario selection.** Every IF/MAX/MIN branch arm of the reference is
   exercised by some scenario.
7. **Real-world finance mechanics in 13 domains**, including **specs written as legal documents**
   (alphabetical defined terms, cross-references, provisos, distractor clauses). No other
   deterministic environment we found covers waterfalls, project finance, ABS, tax provisions,
   credit-loss models or document-specified models.
8. **Generated data with a clean license.** No forum or IP-encumbered content; each task id
   determines its task.

## Quickstart

```bash
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"     # Linux/macOS: .venv/bin/pip
pytest                                                             # 345 tests, ~1 min on 8 cores
```

```python
from spreadsheet_env.tasks import make_task
from spreadsheet_env.agents.runner import grade_patch, patch_prompt

tid = "ca_build-d3-s0"                 # credit agreement, level 3, training seed 0
task = make_task(tid)
print(task.instructions[:1500])        # the agreement and the cells to fill
prompt = patch_prompt(tid)             # single-turn prompt, including the workbook

answer = "Model!D5:J5 := 100"          # a model's edits: "Sheet!Range := formula or value"
result, edits, errors = grade_patch(tid, answer)
print(result.solved, result.reward)   # False 0.0
print(result.summary())               # per-oracle components and the failing cells
```

Multi-turn agents use the OpenEnv server (`python -m spreadsheet_env.server.app`) or the TRL
wrapper; see [Interfaces](#interfaces).

## Task families

Every task id `<family>-d<level>-s<seed>` is deterministic. Training seeds are `0–99,999`, test
seeds `1,000,000–1,000,999`.

### Core: three-statement models and DCF

| Family | What the agent does | Levels 1 → 5 |
|---|---|---|
| `build` | Writes the formulas of empty forecast rows in a three-statement model, from its methodology memo | a few income-statement rows → whole model with revolver, interest income, tax floor → **circular** average-balance interest |
| `repair` | Finds and fixes bugs injected by 13 evidence-weighted operators | 1 visible bug, row named → 3–4 bugs incl. latent ones, count **not disclosed**, 15% **no-bug canaries**, circular model |
| `dcf` | Builds an unlevered-FCF DCF, the valuation bridge and a 5×5 WACC × g grid | valuation block → … → mid-year convention + tax floor |
| `build_free` | Builds a full model **in any layout** and links an `Outputs` contract | income statement only → … → circular |

Sector profiles (software, retail, machinery, packaged food, healthcare services, telecom) are
calibrated to Damodaran's industry averages: 36/36 industry values fall inside the ranges
([`docs/research/04_calibration.md`](docs/research/04_calibration.md)).

### Frontier tier: 9 domains specified by term sheets

`spreadsheet_env/frontier/`. Each domain has three variants: `<domain>_build` (fixed layout),
`<domain>_repair` (injected bugs) and `<domain>_free` (any layout, Outputs contract), each over 5
levels.

| Domain | Models | Level 5 adds |
|---|---|---|
| `lbo` | Multi-tranche LBO debt schedule (TLA, TLB, notes, PIK, revolver), sources & uses, returns | Average-balance interest (circular), a sweep grid on leverage, a commitment fee, a stepping-down covenant with equity cures, IRR of actual sponsor flows |
| `waterfall` | PE distribution waterfalls: European (return of capital, compounding pref, catch-up, carry) and a JV promote with IRR hurdle accounts | Management fees, LP net IRR, GP clawback |
| `pf` | Project finance: construction, IDC, tax losses, CFADS-sculpted debt, DSRA | Banking vs actual case, actual DSCR, a lock-up released after two passes, equity IRR |
| `abs` | 60-month ABS: CPR/CDR/severity, recovery lag, servicing fee, 3 classes, OC trigger | Sticky cumulative-net-loss trigger, reserve account |
| `saas` | Annual contracts, rolling ARR, ratable revenue, deferred revenue | Price uplift, TTM NRR, SMB segment, collections lag, CAC payback |
| `vc` | Exit waterfall over an exit grid: seniority, conversion decisions, participation | In-the-money options, MOIC by series |
| `fx` | IAS 21 translation, CTA as a plug and CTA analysis | Consolidation, a USD intercompany loan, NCI |
| `tax` | Tax provision: allowance pool, DTL, rate reconciliation | 80% loss limitation, 30%-of-ATI interest cap, phased-out allowance, expiring losses, valuation allowance |
| `credit` | Monthly roll-rate credit model with cures | CECL R&S period with reversion, IFRS 9 staging, probability-weighted scenarios |

### Document tier: 4 domains specified by generated legal documents

`spreadsheet_env/frontier/documents/`. The spec is a generated legal document whose clauses are
written next to the formulas they encode:

- defined terms in **alphabetical** order, so the logic is scattered as in a real agreement;
- numbered, cross-referenced sections;
- provisos placed away from the rules they modify;
- distractor clauses about events the model does not contain (asset sales, IPOs, defaults);
- a model-conventions annex, with Schedule 1 being the Assumptions sheet.

Every quoted caption is checked to exist on the Assumptions sheet (`tests/test_frontier.py`).

| Domain | Document | Level 5 contains |
|---|---|---|
| `ca` | Credit agreement | Adjusted Term SOFR floor; pricing grid with "Level I until the first financial statements"; ECF sweep paid the *following* year and credited to installments in direct order of maturity; revolver with a minimum-liquidity rule and a fee grid; capped cost-savings add-backs; greater-of netting limit; HoldCo PIK outside the credit group; springing covenant with an EBITDA equity cure (cure cash disregarded for ratios), cure limits and a default flag; sponsor IRR |
| `lpa` | Limited partnership agreement | European waterfall; fee on commitments then on invested capital; transaction-fee offsets carried forward; a GP commitment that bears no fee, with proceeds apportioned first; after-tax clawback; carry escrow applied to the clawback |
| `indenture` | Auto-ABS indenture | Priority of payments with First/Second/Third and Regular Allocations of Principal; reserve account; OC target with a floor; interest carryover shortfalls bearing interest; sticky CNL trigger stepping up the OC target; WAL |
| `charter` | Certificate of incorporation | Seniority with pari passu classes (ratable shortfall); accruing dividends forfeited on conversion; broad-based weighted-average anti-dilution after a down round; management carve-out; options |

**Validation of every frontier and document task type** (13 domains × 3 variants × 5 levels × 2
seeds = 390 tasks):

- the reference solves;
- no-op and pasted values fail;
- the scripted expert patch solves;
- equivalent rewrites are accepted.

Base cases were tuned to look like real deals, for example:

- PF equity IRR has a median of 9.9%;
- the ABS loss trigger fires in 1 of 20 base cases, while the scenarios still exercise it;
- the credit agreement steps through all three ECF tiers, with a sponsor IRR median of 14%;
- the indenture's OC builds from 6.5% to 22%, with a Class A WAL of 2.2 years;
- the anti-dilution adjustments are 3–9%.

## The grader

| Oracle | Checks | Reference needed? |
|---|---|---|
| `integrity` | Inputs, labels and given formulas unchanged; no parse errors, forbidden functions (`INDIRECT`, `OFFSET`, volatile), unexpected cycles or runaway size | no |
| `base` | Every target cell matches the reference at the base inputs (what value-matching benchmarks check) | yes |
| `perturb` | Every target cell matches the reference under 10 coverage-selected scenarios plus a currency-scaling scenario | yes |
| `identities` | Balance sheet balances, cash and roll-forward ties, waterfall and reserve identities, tax-rate reconciliation | **no** |
| `homogeneity` | All money inputs ×3.7 ⇒ all money outputs ×3.7 (catches embedded constants) | **no** |
| `structure` | Each target depends on every input its logic actually responds to (check rows: every input of their formula); no forbidden dependencies (plugs) | partly |
| `relations` | DCF grid = the agent's own model at the grid's inputs; monotone responses (price falls as WACC rises, MOIC falls with the entry multiple) | **no** |

The reward is binary by default (`solved` = all oracles pass); `shaped` partial credit is
available, and each component is reported separately.

### Evidence

| Claim | Result | Reproduce |
|---|---|---|
| The formula engine computes what spreadsheet apps compute | **100%** agreement with formualizer on 351,714 formula cells (incl. 79,618 in circular models) and with ironcalc on 271,823; 100% with LibreOffice on 138,011 acyclic cells (LibreOffice does not converge on circular models, see the hack log) | `scripts/crosscheck_engines.py` |
| The grader does not reject correct work | **0 / 612** equivalent rewrites rejected (core), **0 / 810** (frontier + credit agreement), **0 / 264** (document tier) | `scripts/exp_false_positives.py` |
| The grader catches real bugs | **2,328 / 2,328** injected bugs detected (all 697 latent ones), ground truth from 300 independent scenarios per model | `scripts/exp_kill_matrix.py --seeds 30` |
| Cheats are blocked | 14 strategies on 80 core tasks, 13 on 162 frontier tasks, 13 on 72 document tasks: **mean reward 0.000** for every cheat (honest model 1.000). A value-only grader accepts most of them | `scripts/hack_audit.py` |
| Every task is solvable | reference 80/80 through the multi-turn tool loop; expert patches solve every frontier and document task type | `scripts/evaluate.py`, `tests/` |
| Doing nothing scores ~0 | 4/100 core; 2/162 frontier; 3/72 document: all of them genuine no-bug repair canaries | `scripts/evaluate.py --policy noop`, hack audit |
| No input crashes the grader | 12,000 fuzzed formulas per test run | `tests/test_engine.py` |

`=IFERROR(<correct formula>, …)` scores 0.67–0.75 in the hack audits: in those tasks it wraps the
*correct* formula, so it is semantically correct and accepted by design.

### Kill matrix (bugs × oracles)

2,328 real bugs (13 operators, cell and row scope) injected into correct models at levels 2–5.
Ground truth comes from 300 independent random scenarios per model; a mutant no scenario
distinguishes is dropped as equivalent. *Latent* bugs (697) give correct values at the base inputs.

| Oracle alone | Visible bugs (1,631) | Latent bugs (697) | All (2,328) |
|---|---|---|---|
| value-only (2 dp, base case) | 100% | **0.1%** | 70.1% |
| base (exact, base case) | 100% | 0.0% | 70.1% |
| perturb (golden, 11 scenarios) | 100% | 99.7% | 99.9% |
| identities (reference-free) | 40.5% | 45.2% | 41.9% |
| homogeneity (reference-free) | 1.4% | 65.4% | 20.5% |
| identities ∪ homogeneity (reference-free) | 41.9% | 77.5% | 52.5% |
| **full grader** | **100%** | **100%** | **100%** |

Latent-bug recall by number of scenarios K: coverage-guided selection reaches 94.8 / 97.8 / 99.3 /
**99.9%** at K = 1 / 2 / 4 / 8, against 90.7 / 93.5 / 96.8 / 97.7% for random scenarios. Per-operator
detection is in `results/kill_matrix.json`.

## Calibration against a frontier model

Claude Opus 5.5 at medium effort, single-turn patch mode, test seeds, Batches API.

**Every failure was audited at cell level before being counted.** An answer given under a spec
later found ambiguous is reported as *void*, not as a model failure. Stored answers are re-graded
offline with `scripts/regrade_batch.py`.

| Batch | Tasks | Raw verdict | After audit | Cost |
|---|---|---|---|---|
| core | 4 families × 5 levels × 2 seeds (40) | 40/40 | 40 solved | $0.92 |
| frontier v1 | lbo, waterfall, pf, abs, saas × 3 variants × levels 3, 5 (30) | 21/30 | 24 solved, 6 void, **0 genuine failures** | $0.93 |
| frontier v2 | fx, tax, credit, vc × 3 variants × levels 3, 5; hardened lbo, pf, abs (36) | 23/36 | 34 solved, 2 void, **0 genuine failures** | $1.18 |
| documents v3 | ca, lpa, indenture, charter × 3 variants × levels 3, 5 (24) | 20/24 | 22 solved, 1 void, **1 genuine failure** (renamed a locked label, against the stated rules) | $1.22 |

What the audits found:

- **Most raw failures were environment defects, not model errors.** Examples (HACK_LOG #15–25):
  - perturbed structural zeros;
  - a structure rule that demanded inputs which cancel exactly;
  - an exit grid shuffled by scenarios;
  - shortened Outputs labels;
  - a stale 3,000-cell patch cap;
  - spec gaps the reference resolved silently.

  The tier-level checks (reference, no-op, paste, expert, rewrites) had passed on every task and
  found none of these; real model answers did.
- **Opus's routes were often better than the reference's.** It used the CTA analysis identity
  instead of a plug, `MAX`/`MATCH` for "the highest exit", and a construction loan refinanced to
  zero at COD.
- **Repairs:** every repair bug was fixed, 48/48 in batches v2 and v3, 29 of them
  latent.

**Verdict, stated plainly.** With a complete, unambiguous spec, a frontier model at medium
effort solves essentially every task:

- long and stateful logic (sticky triggers, two-pass lock-ups, circular covenants with cures,
  CECL reversion, valuation allowances, anti-dilution);
- formula-level term sheets;
- generated legal documents.

Every divergence in 130 answers came from *interpretation*: a silent spec, a literal label, a
realistic convention. None came from executing a stated rule.

So this environment is not a frontier-difficulty benchmark. Its value lies elsewhere:

- a grader that holds up under attack, with the evidence to show it;
- breadth and realism across 13 finance domains;
- an unlimited, deterministic supply of well-posed tasks for RL training below the frontier, and
  for reliability testing at the frontier.

Small open models (Qwen 1.5–1.7B) score 0 out of the box.

Results: `results/frontier/*.jsonl` and `*_summary.json`. `scripts/frontier_batch.py` estimates
the cost, submits one batch, polls for free, and grades the answers.

## Interfaces

- **OpenEnv MCP environment** (`spreadsheet_env.environment.SpreadsheetEnvironment`), served by
  `python -m spreadsheet_env.server.app`, with concurrent sessions.
  - Tools: `list_sheets`, `read_range` (full / values / formulas / compact view), `write_cell`,
    `write_cells`, `copy_cell` (Excel fill semantics), `trace` (precedents/dependents), `find`,
    `submit`.
  - `openenv validate` passes at both static and runtime level; `scripts/remote_smoke.py` plays
    full episodes over WebSocket.
- **Single-turn patch mode**: the workbook goes in the prompt; the answer is a block of
  `Sheet!E5:J5 := =formula` edits (a range edit fills right).
- **TRL**: `spreadsheet_env.trl_env.SpreadsheetToolEnv` for `GRPOTrainer(environment_factory=...)`,
  or `patch_reward` for single-turn GRPO. `set_reward_oracles([...])` swaps the reward grader,
  which is how a reward ablation is run.
- **Agent harness** (`scripts/evaluate.py`): Claude (manual tool loop with prompt caching and
  cost accounting), local Hugging Face models, scripted oracles.

## Repository layout

```
spreadsheet_env/
  engine/               formula parser and evaluator, fixed-point solver for circular models
  model/                declarative ModelSpec DSL -> workbook + layout
  tasks/                core families (build, repair, dcf, build_free) and the 13 bug operators
  frontier/             9 term-sheet domains and the shared task framework
  frontier/documents/   credit agreement, LPA, indenture, charter (legal-document specs)
  grader/               the 7 oracles, scenario selection, equivalence rewrites
  agents/               prompts, policies (Claude, Hugging Face, scripted), expert demonstrations
  server/               OpenEnv server (FastAPI + MCP)
scripts/                experiments: kill matrix, hack audit, false positives, engine cross-check,
                        calibration batches, example rendering, SFT/GRPO training
tests/                  345 tests (engine fuzzing, every family, frontier and document tiers)
docs/                   PLAN (design record), HACK_LOG, research notes, examples/
results/                the evidence behind every number in this README (JSON / JSONL)
```

## Reproduce

```bash
pip install -e ".[dev,crosscheck,agents]"
pytest                                                             # 345 tests
python scripts/hack_audit.py --seeds 4                             # core red-team table
python scripts/hack_audit.py --families frontier --levels 5,3,1 --seeds 2
python scripts/exp_false_positives.py --seeds 12                   # equivalence suite (core)
python scripts/exp_false_positives.py --families frontier --levels 1,3,5 --seeds 3
python scripts/exp_kill_matrix.py --seeds 30                       # oracle x bug matrix
python scripts/crosscheck_engines.py --seeds 20                    # + --libreoffice (docker/libreoffice)
python scripts/render_examples.py                                  # docs/examples/
python scripts/frontier_batch.py estimate --tasks ca_build:3:1 lpa_build:5:1   # cost before any API call
python -m spreadsheet_env.server.app --port 8000                   # OpenEnv server; or docker/server/Dockerfile
```

The API key for calibration batches is read from the environment (`ANTHROPIC_API_KEY`, or the
Windows user environment); it is never stored in the repository.

## Performance

Grading is pure Python, so every experiment spreads independent units over a process pool
(`spreadsheet_env/parallel.py`; default: all logical cores − 2, override with `--workers` or
`SSE_WORKERS`). Measured on a Ryzen 7 7745HX laptop (8 cores / 16 threads):

| Job | Time |
|---|---|
| Kill matrix (97 models, 2,328 mutants, 300 truth scenarios each) | 6.9 min (14 workers) |
| Engine cross-check (1,691 workbooks) | 59 s (14 workers) |
| Test suite (345 tests) | 41–50 s (6–8 workers) |
| Core hack audit (80 tasks × 16 attacks) / core false-positive suite (612 rewrites) | ~2 min / 17 s |

Grading a submission takes 10–60 ms (about 150 ms for circular models; up to ~1 s for 60-month
monthly models). Task generation is deterministic and cached.

## Known limitations

- **Frontier difficulty.** See the calibration verdict: with complete specs, frontier models
  solve these tasks. The audits' main yield was grader and spec quality.
- **Free-layout plugs.** In free-layout tasks, a plug numerically identical to the correct logic
  cannot be detected (the agent's internal line items are unknown). Plugs that hide errors are
  caught.
- **Constant targets.** A cell whose correct value never changes may be typed as a constant (a
  structural zero), except for check rows, which must stay computed. A flag that no scenario and
  no single-input move can trigger could therefore be typed. Coverage-guided scenarios make this
  rare.
- **Portable formula subset.** OFFSET/INDIRECT, volatile functions, implicit intersection and
  spilled arrays are rejected by design; data tables are written as formulas.
- **Circular models** are solved to a 1e-14 relative tolerance; scenarios are restricted to those
  where the reference converges quickly.
- **Synthetic companies and documents.** Ranges are calibrated, but no task uses real issuer
  data, and documents are generated (fictional names).

## Roadmap

1. **Agentic mode with hidden context**: workbooks and documents too large for one prompt, which
   forces multi-turn tool use. This is the remaining untested difficulty lever.
2. **RL training demo and reward ablation**: an SFT warm-start (~1k expert demonstrations from
   `agents/demos.py`), then GRPO on repair tasks, with a value-only reward vs the full grader.
   Prediction: the value-only arm learns to leave latent bugs in place.
3. **More families**: a roll-forward (new actuals arrive) and real-company historicals from SEC
   data.

## License

Apache-2.0 (see [LICENSE](LICENSE)). All task data is generated by this code; the Damodaran
datasets used for calibration are not redistributed ([`data/README.md`](data/README.md)).
