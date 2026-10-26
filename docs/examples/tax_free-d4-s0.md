# tax_free-d4-s0

**Tax provision, free layout: allowances with phase-out, interest limitation, expiring losses.** Family `tax_free`, level 4, training seed 0; 86 graded cells, 11 perturbation scenarios.

## What the agent sees

````text
Build a corporate tax provision model from scratch in a spreadsheet (amounts in $m).

TASK: build the whole model on the Model sheet in any layout you like, then link every cell of the Outputs sheet to it. Projection periods: FY2025, FY2026, FY2027, FY2028, FY2029, FY2030, FY2031 (use Outputs columns D:J for them, same order).
Outputs to fill:
- row 4: Total capital allowances (forecast years)
- row 5: Taxable income (forecast years)
- row 6: Current tax (forecast years)
- row 7: Deferred tax expense/(credit) (forecast years)
- row 8: Total tax expense (forecast years)
- row 9: Net deferred tax liability (forecast years)
- row 10: Deductible interest (forecast years)
- row 11: Disallowed interest carried forward - closing (forecast years)
- row 12: Loss carryforward - closing (forecast years)
- row 13: Legacy losses - closing (forecast years)
- row 14: Tax at the statutory rate (forecast years)
- row 15: Effect of expired legacy losses (forecast years)
- row 16: Total current tax (single value in column C)
- row 17: Effective tax rate over the projection (single value in column C)

TERMS:
CAPITAL ALLOWANCES. The tax pool is written down on a reducing balance: writing-down allowance = WDA % x (opening pool + additions not given the first-year allowance); closing pool = opening + those additions - writing-down allowance. A FIRST-YEAR ALLOWANCE deducts additions immediately up to an annual cap; the cap is reduced dollar-for-dollar by additions above the phase-out threshold (never below zero) and the allowance cannot exceed the additions. Additions not given the first-year allowance join the pool. Total capital allowances = first-year allowance + writing-down allowance. Book NBV = opening + additions - book depreciation.
INTEREST LIMITATION. ATI = EBITDA. Deductible interest = the smaller of (this year's interest + disallowed interest carried forward) and cap % x ATI (zero if ATI is negative). Disallowed interest carries forward indefinitely: closing = opening + interest - deductible interest.
TAXABLE INCOME before loss relief = EBITDA - total capital allowances - deductible interest (negative = a tax loss).
LEGACY LOSSES are used first, against all of the positive taxable income before loss relief (no % limit). Whatever is left at the end of the expiry year (projection year number on Assumptions; the opening column is year 0) expires and is lost.
LOSS CARRYFORWARD. Usage = the smaller of the opening carryforward and limit % x positive taxable income after legacy losses. A tax loss adds to the carryforward (never to the legacy pool). Closing = opening + new losses - used.
Taxable income = MAX(0, taxable income before loss relief - losses used); current tax = rate x taxable income.
DEFERRED TAX. DTL on fixed assets = rate x (book NBV - tax pool); DTA on carryforwards = rate x (loss carryforward + legacy losses + disallowed interest). Net deferred tax liability = DTL - DTA, in every column including the opening one. Deferred tax expense = change in the net deferred tax liability; total tax expense = current + deferred.
Book pre-tax income = EBITDA - book depreciation - interest. RATE RECONCILIATION: tax at the statutory rate = rate x book pre-tax income; effect of expired legacy losses = rate x losses expired.
RESULTS: effective tax rate = total tax expense / total book pre-tax income over the projection (0 if that total is not positive).

CONVENTIONS:
- The opening column holds balances only (no flows).
- All amounts in $m.

RULES:
- Every formula must be live and linked to the inputs: the model will be re-calculated with different input values, so typed numbers will be wrong.
- Do not change inputs (the Assumptions sheet and any given values), labels or headers.
- Allowed functions: SUM, AVERAGE, MIN, MAX, COUNT, IF, IFERROR, AND, OR, NOT, ABS, ROUND, ROUNDUP, ROUNDDOWN, INT, MOD, POWER, SQRT, LN, EXP, SIGN, SUMPRODUCT, NPV, PMT, IRR, INDEX, MATCH, CHOOSE.
- Use only the Model sheet (and Outputs) for your work; the starting values on Model are given.

Assumptions sheet: C4 Tax rate; C5 Writing-down allowance on the tax pool (reducing balance); C6 Loss carryforward usable against this share of taxable income; C7 Interest limitation: cap as a share of ATI; C8 First-year allowance: annual cap; C9 First-year allowance: phase-out threshold (additions); C10 Legacy losses expire at the end of projection year; row 12 EBITDA (book = tax) (D:J); row 13 Net interest expense (D:J); row 14 Capital additions (qualifying for allowances) (D:J); row 15 Book depreciation (fixed-asset register) (D:J)

Use the tools to build the model. Call submit when you are done.
````

## Reference formulas (first projection column and single-cell results)

| Cell | Label | Formula |
|---|---|---|
| Model!D5 | Model!D5 (Projection year FY2025) | `=C5+1` |
| Model!D8 | Model!D8 (First-year allowance FY2025) | `=MIN(Assumptions!D14,MAX(0,Assumptions!$C$8-MAX(0,Assumptions!D14-Assumptions!$C$9)))` |
| Model!D9 | Model!D9 (Writing-down allowance FY2025) | `=Assumptions!$C$5*(C10+Assumptions!D14-D8)` |
| Model!D10 | Model!D10 (Tax pool (written-down value) - closing FY2025) | `=C10+Assumptions!D14-D8-D9` |
| Model!D11 | Model!D11 (Total capital allowances FY2025) | `=D8+D9` |
| Model!D12 | Model!D12 (Book net book value - closing FY2025) | `=C12+Assumptions!D14-Assumptions!D15` |
| Model!D15 | Model!D15 (Adjusted taxable income (ATI) FY2025) | `=Assumptions!D12` |
| Model!D16 | Model!D16 (Deductible interest FY2025) | `=MIN(Assumptions!D13+C17,Assumptions!$C$7*MAX(0,D15))` |
| Model!D17 | Model!D17 (Disallowed interest carried forward - closing FY2025) | `=C17+Assumptions!D13-D16` |
| Model!D20 | Model!D20 (Taxable income before loss relief FY2025) | `=Assumptions!D12-D11-D16` |
| Model!D21 | Model!D21 (Legacy losses used FY2025) | `=MIN(C23,MAX(0,D20))` |
| Model!D22 | Model!D22 (Legacy losses expired FY2025) | `=IF(D5=Assumptions!$C$10,C23-D21,0)` |
| Model!D23 | Model!D23 (Legacy losses - closing FY2025) | `=C23-D21-D22` |
| Model!D24 | Model!D24 (Loss carryforward used FY2025) | `=MIN(C26,Assumptions!$C$6*MAX(0,D20-D21))` |
| Model!D25 | Model!D25 (New tax losses FY2025) | `=MAX(0,-D20)` |
| Model!D26 | Model!D26 (Loss carryforward - closing FY2025) | `=C26+D25-D24` |
| Model!D27 | Model!D27 (Taxable income FY2025) | `=MAX(0,D20-D21-D24)` |
| Model!D28 | Model!D28 (Current tax FY2025) | `=Assumptions!$C$4*D27` |
| Model!D31 | Model!D31 (Deferred tax liability on fixed assets FY2025) | `=Assumptions!$C$4*(D12-D10)` |
| Model!D32 | Model!D32 (Deferred tax asset on carryforwards FY2025) | `=Assumptions!$C$4*(D26+D23+D17)` |
| Model!D33 | Model!D33 (Book pre-tax income FY2025) | `=Assumptions!D12-Assumptions!D15-Assumptions!D13` |
| Model!D34 | Model!D34 (Net deferred tax liability FY2025) | `=D31-D32` |
| Model!D35 | Model!D35 (Deferred tax expense/(credit) FY2025) | `=D34-C34` |
| Model!D36 | Model!D36 (Total tax expense FY2025) | `=D28+D35` |
| Model!D39 | Model!D39 (Tax at the statutory rate FY2025) | `=Assumptions!$C$4*D33` |
| Model!D40 | Model!D40 (Effect of expired legacy losses FY2025) | `=Assumptions!$C$4*D22` |
| Model!C31 | Model!C31 (Deferred tax liability on fixed assets FY2024 (opening)) | `=Assumptions!$C$4*(C12-C10)` |
| Model!C32 | Model!C32 (Deferred tax asset on carryforwards FY2024 (opening)) | `=Assumptions!$C$4*(C26+C23+C17)` |
| Model!C34 | Model!C34 (Net deferred tax liability FY2024 (opening)) | `=C31-C32` |
| Model!C43 | Model!C43 (Total current tax) | `=SUM($D$28:$J$28)` |
| Model!C44 | Model!C44 (Total tax expense) | `=SUM($D$36:$J$36)` |
| Model!C45 | Model!C45 (Total book pre-tax income) | `=SUM($D$33:$J$33)` |
| Model!C46 | Model!C46 (Effective tax rate over the projection) | `=IF($C$45>0,$C$44/$C$45,0)` |
