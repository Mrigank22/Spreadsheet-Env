# Evidence base for the bug-injection (mutation) operators

Researched 2026-10-25. The repair tasks inject bugs into correct, generated models. These
notes record why each operator exists and how often its real-world counterpart occurs, so
the sampling weights are evidence-based, not invented.

## Key numbers

- **Powell, Baker & Lawson (2009)**, an audit of 50 operational workbooks with 270,722
  formulas and 483 error instances [4]. It is the only large field audit that counts errors
  by type.
  - All instances: hard-coding 37.7%, reference 32.9%, logic 21.9%, copy/paste 3.4%,
    omission 2.7%, data input 1.2%.
  - **Instances that change results (n=281): reference 48.8%, logic 31.7%, hard-coding
    11.0%**, copy/paste 5.0%, omission 2.5%, data input 1.1%.
  - Cell error rate 1.79% overall (0.87% counting only wrong results); 94% of workbooks had
    errors and 86% had wrong results.
- **Hard-coding is the most common error but is usually latent.** The value looks right
  today and goes stale once an input changes. A grader that compares values at the base
  inputs cannot see it. This is the main empirical motivation for metamorphic,
  input-perturbation grading.
- **Lab studies** (Panko) [1][3]:
  - mean cell error rate 3.9% across 14 studies;
  - error mix: logic 45%, mechanical 23%, omission 31%;
  - a pro-forma income statement task produced pointing errors, sign errors, magnitude
    errors and a "Year 2 value used in Year 1" error.
- **Enron corpus** [6][7]:
  - 24% of workbooks containing formulas show an Excel error value, and `#REF!` is the most
    widespread;
  - real fixes recovered from emails include mechanical (14), logic (9) and omission (5)
    errors.
- **Incidents** (secondary sources):
  - Reinhart–Rogoff: a truncated AVERAGE range [8][9];
  - the London Whale: divided by a sum instead of an average [10];
  - Fidelity Magellan: a missing minus sign caused a $2.6B swing [11];
  - TransAlta: a cut-and-paste misalignment cost $24M [12].

## Taxonomies used to label operators

- Panko & Halverson: quantitative errors (mechanical, logic, omission) vs qualitative
  errors (e.g. "jamming" a constant into a formula).
- Rajalingham et al. (2000).
- Panko & Aurigemma (2010): mistakes, slips and lapses, plus violations.
- Powell (2009): Logic, Reference, Hard-coding, Copy/Paste, Data input, Omission.

## Detection tools and the error classes they target

| Tool | Error classes |
|---|---|
| ExceLint [9] | Reference-pattern breaks, off-by-one ranges |
| AmCheck/CACheck [13] | Missing or inconsistent formulas |
| CUSTODES [14] | Outlier cells in clusters of similar cells |
| Melford [15] | Numbers typed where a formula belongs |
| UCheck [16] | Unit and dimension errors |

## Practitioner standards

**FAST Standard 02c** [21]:
- consistent formulas along a row (3.02-01);
- no partial ranges (3.02-03);
- no embedded constants (3.04-01);
- don't over-anchor (3.04-07);
- corkscrews for balances (2.02-05);
- no purposeful circularity (1.01-11).

**ICAEW Financial Modelling Code** [22]: consistent formulas, a clear sign convention, a
master check, no hard-coding, no circular references.

**Forvis Mazars** [23] and **Breaking Into Wall Street** [24], common model errors:
- sign errors on cash, assets and debt;
- timing and period errors;
- working-capital double counting, and "old − new" sign errors;
- statements not linked;
- equity plugs used as a hack.

## Operators and evidence

| # | Operator | Category | Evidence |
|---|---|---|---|
| 1 | REF_SHIFT: a reference points to the adjacent row or column | Reference / pointing slip | 48.8% of wrong-result errors [4]; Enron D4→D10 [7] |
| 2 | ROW_INCONSISTENCY: one period uses a different driver | Copy-paste / FAST 3.02-01 | Most of ExceLint's 397 errors [9]; Mazars #1 [23] |
| 3 | RANGE_TRUNCATE: SUM drops the first or last row | Omission / reference | Reinhart–Rogoff [8]; ExceLint [9] |
| 4 | DOUBLE_COUNT: a total includes a subtotal or an extra line | Logic | ExceLint "extra reference" [9]; BIWS [24] |
| 5 | HARDCODE_PASTE: formula replaced by its current value | Hard-coding (latent) | 37.7% of all errors [4]; Melford [15] |
| 6 | JAMMED_CONSTANT: a literal inside a formula disagrees with the input cell | Hard-coding (wrong result) | Powell's 3.5% vs 4% inflation case [4] |
| 7 | ANCHOR_ERROR: missing or extra `$`, so fill-right drifts | Reference | ExceLint [9]; FAST 3.04-07 |
| 8 | SIGN_FLIP_CF: sign of the working-capital change, capex or repayment inverted | Slip / domain logic | Fidelity [11]; Mazars [23]; BIWS [24] |
| 9 | PERIOD_OFFSET: t vs t−1 confusion in a corkscrew or driver | Lapse / reference | Panko's "Year 2 in Year 1" [1]; Mazars [23] |
| 10 | OPERATOR_SWAP: + vs −, SUM vs AVERAGE, ÷sum vs ÷mean | Logic | London Whale [10]; logic is 31.7% of wrong results [4] |
| 11 | LINK_OMISSION: drop the D&A add-back, the NI→RE link or dividends | Omission | 31% of lab errors [3]; BIWS's top imbalance cause [24] |
| 12 | PLUG_FUDGE: a hard-coded balancing item, or an IFERROR mask | Violation | ExceLint "+1000 fudge" [9]; BIWS [24] |
| 13 | CIRCULARITY: interest on the closing balance | Domain logic | FAST, ICAEW, Mazars (no frequency counts) |
| 14 | UNIT_PERIODICITY: % entered as a whole number; annual vs quarterly | Dimension | UCheck [16]; Mazars [23] |
| 15 | INPUT_SLIP: transposed digits or a magnitude error | Data input | Panko [1] |

**Sampling weights, from Powell's mix of wrong-result errors:**
- reference-type operators (1, 2, 3, 7, 9): about 50%
- logic operators (4, 10, 13, 14): about 30%
- hard-coding operators (5, 6, 12): about 10–15%
- the rest: about 5–10%

**Caveats:**
- Powell's audit covered general business spreadsheets, not three-statement models
  specifically.
- Operators 8, 9, 11, 13 and 14 rest on incidents and practitioner guidance, not on counts.
- Pearson et al. (2017), as cited in ExceLint, found that fault-finding methods tested on
  random faults do not carry over to real faults. So every operator mimics one plausible
  slip, applied in a way consistent with how real copied regions look.

**No public corpus of three-statement models with labelled errors was found.** This is a
gap that this environment's generator and mutation pipeline fill by construction.

## References

1. https://arxiv.org/abs/0809.3613
2. https://arxiv.org/abs/0805.4224
3. https://arxiv.org/abs/1602.02601
4. https://mba.tuck.dartmouth.edu/spreadsheet/product_pubs_files/Errors.pdf
5. https://arxiv.org/abs/1808.10231
6. https://figshare.com/articles/Enron_s_Spreadsheets_and_Related_Emails_A_Dataset_and_Analysis/1222882
7. https://web-ainf.aau.at/pub/jannach/files/Conference_VL_HCC_2016.pdf
8. https://www.newstatesman.com/business/economics/2013/04/statistic-cited-defend-austerity-partially-based-excel-error
9. https://arxiv.org/abs/1901.11100
10. https://www.bloomberg.com/news/articles/2013-01-16/jpmorgan-halves-dimon-pay-says-ceo-responsible-for-lapses-1-
11. https://blog.trginternational.com/7-worst-financial-fiascos-caused-by-excel-errors
12. https://www.theregister.com/2003/06/19/excel_snafu_costs_firm_24m/
13. https://arxiv.org/abs/1810.04542
14. https://cse.hkust.edu.hk/pg/defenses/Summer15/wchenah-23-07-2015.html
15. https://www.microsoft.com/en-us/research/publication/melford-using-neural-networks-find-spreadsheet-errors/
16. https://web.engr.oregonstate.edu/~erwig/UCheck/
17. https://figshare.com/articles/dataset/VEnron2/4798042 (CC0)
18. https://spreadsheets.sai.tugraz.at/?p=343
19. https://zenodo.org/record/581678
20. https://spreadsheets.sai.tugraz.at/?p=322
21. https://fast-standard.org/wp-content/uploads/2019/10/FAST-Standard-02c-July-2019.pdf
22. https://www.icaew.com/-/media/corporate/files/technical/technology/excel-community/financial-modelling-code.ashx
23. https://www.forvismazars.us/getattachment/17e4d933-cdf4-4b42-83b3-f1a8e824a242/Model-Review-Webinar-Presentation-Final.pdf
24. https://breakingintowallstreet.com/kb/3-statement-models/balance-sheet-not-balancing/
25. https://arxiv.org/abs/1001.4107
