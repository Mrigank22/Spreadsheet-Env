# Hack and fix log

Every entry below was found while building this environment. Each lists:

- the exploit or defect;
- how it was found;
- the fix;
- before/after evidence.

A grader that is meant to hold up under attack should come with this log. Reproduce the
numbers with the commands given.

| # | Exploit / defect | Found by | Fix | Before → after |
|---|---|---|---|---|
| 1 | **Pasted values**: type the right numbers instead of formulas | design / `scripts/hack_audit.py` | `perturb` oracle (golden match under 11 coverage-selected scenarios) + `homogeneity` + `structure` | value-only grader accepts 100% → full grader 0% |
| 2 | **Do nothing on latent-bug repairs**: bugs that leave base-case values correct (stale paste, jammed constant, removed `MAX(0,…)` guard, coincident reference) | `scripts/evaluate.py --policy noop` + value-only grader | `perturb` oracle | value-only grader rewards the no-op on 18–30% of repair tasks (per level, 40 seeds) → only true no-bug canaries pass |
| 3 | **Balancing plug**: honest model, but `cash = total L&E − other assets` | `hack_audit.py` (reward 0.61) | `structure` oracle, forbidden dependency: asset lines must not depend on L&E totals (and vice versa) | mean reward 0.611 → 0.000 |
| 4 | **Overwrite the balance check with `0`** (the "delete the failing test" move) | `hack_audit.py` (reward 0.78) | `structure` oracle, required dependencies: every target must depend on every input its reference logic depends on | mean reward 0.778 → 0.000 |
| 5 | **Grader crash via overflow**: `SUM(1E308,1E308)` made `math.fsum` raise | crash during `exp_kill_matrix.py` | overflow → `#NUM!` in every aggregate; the grader catches all exceptions and fails the submission instead of crashing | crash → `#NUM!`, reward 0 |
| 6 | **Grader crash via `ROUND(x, 1E17)`** (`decimal.InvalidOperation`) | random-formula fuzzer (`tests/test_engine.py`) | clamp digits; catch `ArithmeticError` in all function wrappers | crash → handled; 12,000 fuzzed formulas per test run |
| 7 | **Recursion bombs**: 100 nested parentheses or a 400-term `1*1*…` chain overflowed Python's stack | fuzzer / code review | parser limits: 64 nesting levels, 300 operators, 2,000 characters | crash → `FormulaSyntaxError` |
| 8 | **Forbidden functions** (`INDIRECT`, `OFFSET`, `RAND`, `NOW`, …) defeat dependency analysis and perturbation | design | rejected by the write tool; evaluate to `#NAME?`; flagged by `integrity` | blocked |
| 9 | **Editing an input** to make outputs match | `hack_audit.py` | `integrity` oracle: inputs, labels and given formulas are locked | reward 0 |
| 10 | **Writing thousands of cells** (resource abuse) | `hack_audit.py` | `integrity`: at most 3,000 new cells; 400 per batch write; 600 per read | reward 0 (a value-only grader accepted it) |
| 11 | **False negatives on correct circular models**: equivalent rewrites of iterative (average-balance) models were rejected (18/210) | `scripts/exp_false_positives.py` | (a) under-relaxed retries in the Gauss–Seidel solver; (b) interest-rate perturbations capped at 25%; (c) a scenario is kept only if the reference converges in ≤ 200 iterations | false positives 18/210 → 0/210 |
| 12 | **`ROUND` boundary flip in circular models**: the solver stopped at a 1e-11 relative step, leaving ~1e-6 absolute error that `ROUND(TA−TLE,6)` exposed | `scripts/crosscheck_engines.py` (5 disagreements vs formualizer) | stop at a 1e-14 relative step | 99.9973% → 100% agreement (186,246 cells) |
| 13 | **Weaker scenario sets for circular models** (an attempted speed-up) | coverage measurement before merging | kept 80 candidates: 40 lost branch arms on 5/8 models | change rejected |
| 14 | **Latent bug the scenarios never exposed**: `-MIN(repay, debt[t-2])` instead of `debt[t-1]` matters only in the year debt is nearly repaid (3–4% of random scenarios) | kill matrix v1 (2/2,328 missed) | (a) a MIN/MAX arm that wins only at value 0 no longer counts as covered; (b) an "extreme" sampling mode (money log-uniform over 3 orders of magnitude); (c) up to 2 coverage-directed extra rounds while new arms appear | misses 2/2,328 → 0/2,328; equivalence suite still 0/612 false positives |
| 15 | **False positives on frontier tasks: structural zeros perturbed.** Scenarios moved opening balances that the term sheet fixes at zero ("revolver undrawn at close", empty DSRA, no carried-forward shortfall). E.g. an opening revolver of 851.8 against a 76.3 commitment. Correct models that relied on the stated zero were failed. | Auditing every failure of the first Opus 5.5 frontier batch at cell level (`scripts/regrade_batch.py`) | A zero opening balance of a model corkscrew is a structural input (`fixed`), never perturbed (`frontier/framework.py: inputs_for`) | 4 of Opus's 9 failures were grader errors: 21/30 → 24/30 on the same stored answers (no new API calls) |
| 16 | **Ambiguous spec: ABS edge cases.** (a) The OC ratio once all notes are repaid (division by zero; the reference used `MAX(1E-9, …)`, a defensible answer used 0). (b) Negative excess spread when the servicing fee exceeds collections ("unused excess spread" could be read as floored at 0). | Same audit | Term sheet now states both: OC ratio is 0 once the notes are repaid; the residual formula is given and excess spread may be negative. The OC reference changed to `IF(notes>0, pool/notes, 0)`. | ABS answers re-run under the clarified spec in batch v2 |
| 17 | **Cell budget too small for large free-layout builds**: the 60-month ABS waterfall needs more than 3,000 new cells, so the *reference* failed integrity | Frontier domain validation (`abs_free-d5`) | budget = max(3,000, 2 × the reference's own writes); still blocks the junk-writing attack | reference 0 → 1; `write_thousands_of_cells` still 0 |
| 18 | **Equivalence test placed helper cells inside wide models**: a fixed +30-column offset overwrote cells of 60-month models (spurious circularity) | `tests/test_frontier.py` | helper offset clears the widest used column | 2 failing tests → 0 |
| 19 | **False positive: `structure` required inputs that cancel exactly.** The reference computes the CTA movement as a plug of translated net assets. Because LC cash is a balancing line, PP&E and liabilities drop out of it algebraically. Opus wrote the equivalent CTA analysis identity (`td_open + td_inc − td_div`), was right in every scenario, and was failed for "missing 6 inputs". | Cell-level audit of batch v2: all 6 FX tasks failed on `structure` alone, with `base` = `perturb` = 1 | For a target whose reference value *varies*, an input is required only if moving it alone (up and down, in the base case and every scenario) moves the reference value. A *constant* target (a balance check) keeps the syntactic rule, which is what blocks #4. Runs only when every other oracle passed. | FX 0/6 → 6/6 on the same answers. `test_typed_zero_check_row_still_fails_structure` keeps #4 closed. |
| 20 | **False positive: scenarios broke an ordered grid.** VC exit values form an ascending grid, so "MOIC at the highest exit" is the last column. Independent perturbations shuffled the grid; a model using `MAX`/`MATCH` (the literal reading) was failed against the reference's last column. | Same audit (4 VC build/free failures, scenario 1 only) | Inputs can belong to an ascending group (`InputInfo.group`); scenarios re-sort it. The term sheet says that the exits ascend. | VC build/free 0/4 → 4/4 |
| 21 | **Ambiguous Outputs labels.** The Outputs contract used shortened labels: "Reserve funding" for the signed "Reserve funding/(release)". Opus kept funding and release as separate lines (correct) and linked only funding. Relinking that one row makes the 60-month model fully correct. | Same audit (`abs_free-d5`) | Outputs rows carry the model line's full label unless the contract label contains it and adds a sign convention (`framework._output_label`) | Answer void (old label ambiguous); every free task relabelled |
| 22 | **Patch writer capped at 3,000 cells.** #17 raised the integrity budget, but the patch-mode writer still stopped at a hard-coded 3,000 cells and reported "range too large". Six of Opus's output rows were silently dropped. | Same audit (6 edit errors on `abs_free-d5`) | One `cell_budget(task)` shared by the integrity oracle and the patch writer; separate messages for "range too large" and "cell budget exhausted" | `test_patch_budget_matches_the_grader_budget` |
| 23 | **Spec gaps the reference resolved silently.** (a) ABS: the reserve draw is sized against *positive* interest, but the classes were paid from interest *including* a negative servicing shortfall. (b) PF: the construction loan stays flat after COD, but level-5 prompts show labels only, and the term sheet never said so. Opus took the realistic reading of both (shortfall met from principal; loan refinanced to zero). | Same audit | (a) The reference adopts the reading that matches the rest of the term sheet, which now states it: classes are paid from `MAX(0, interest) + draw`. (b) The term sheet states the memo-corkscrew rule. | ABS build 0/1 → 1/1; PF answer void |

| 24 | **False positive: a structural zero typed as 0.** The credit agreement pays the ECF sweep from the first full Fiscal Year, in the following year, so the first-year prepayment is zero in every scenario. The `structure` oracle kept the strict syntactic rule for *every* always-constant target (written for balance checks), so a correct `=0` was failed for "missing" the Term Loan input. | Cell-level audit of document batch v3 (3 of the 4 credit-agreement failures) | The strict rule now applies only to check rows (`kind == "check"`); every other target is held to the inputs it actually responds to | 2 credit-agreement builds solved on the same answers; `overwrite_check_row` still 0 (core hack audit re-run) |
| 25 | **Spec gap: negative cash in the netting.** Annex B allows negative cash (overdraft), but "Unrestricted Cash … not exceeding the Netting Limit" did not say whether a negative balance adds to net debt. Opus read it both ways in different answers (floored at 0 in the builds, not floored in the free-layout builds), which shows the wording was genuinely ambiguous. | Same audit | The agreement now states that the amount deducted is never below zero (an overdraft is neither deducted nor added); exit equity uses the signed balance | Free-layout answer void |

## Lesson from frontier calibration

The tier-level checks:

- the reference solves;
- no-op and pasted values fail;
- the scripted expert solves;
- random equivalent rewrites are accepted.

All of them passed on all 270 frontier tasks. Yet **every one of the 13 failures in the second Opus 5.5 batch was an environment defect (#19–23), not a model error**. Real model answers take routes the reference and the rewriter never take: analysis identities instead of plugs, literal readings of labels, realistic conventions where the spec is silent.

So every failure of a strong model is audited cell by cell before a pass rate is reported (`scripts/regrade_batch.py` re-grades stored answers offline, at no API cost). Answers given under a spec later found ambiguous are reported as void, not as failures.

## Accepted, not exploits

- `=IFERROR(1/0, <correct formula>)` is semantically the correct formula in every scenario,
  so it is accepted. IFERROR used to *hide* a wrong formula changes values and fails.
- A **numerically harmless plug in free-layout tasks** cannot be detected, because the grader
  does not know the agent's internal line items. A plug that hides an error still fails the
  golden and identity checks. This is a documented limitation.

## External finding: LibreOffice and circular models

LibreOffice 25.2 headless was run with iterative calculation enabled, both through the file's
`calcPr` and through the profile key
`/org.openoffice.Office.Calc/Calculate/IterativeReference`. On our circular models it returned
values with fixed-point residual 0.75, and its balance sheet was out by up to 11.3.

- Our engine and formualizer agree to 1e-6 relative on all 48,235 circular cells.
- On acyclic models, LibreOffice agrees with our engine on 100% of 138,011 cells.

The root cause inside LibreOffice was not investigated. Environments that grade circular
(LBO-style) models by LibreOffice recalculation should check convergence before trusting
references.
