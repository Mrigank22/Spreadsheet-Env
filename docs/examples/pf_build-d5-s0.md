# pf_build-d5-s0

**Project finance term sheet: sculpted debt, DSRA, banking vs actual case, lock-up.** Family `pf_build`, level 5, training seed 0; 885 graded cells, 11 perturbation scenarios.

## What the agent sees

````text
You are building a project finance model (construction, operations and sculpted debt) in a spreadsheet (sheets: Assumptions, Model; amounts in $m). Column C holds the starting point, columns D:Y the projection (FY2027, FY2028, FY2029, FY2030, FY2031, FY2032, FY2033, FY2034, FY2035, FY2036, FY2037, FY2038, FY2039, FY2040, FY2041, FY2042, FY2043, FY2044, FY2045, FY2046, FY2047, FY2048).

TASK: the cells below are empty. Write a formula in every one so that the model implements the TERMS below exactly. Work out each row's logic from the terms and the row labels.
- Model!D5:Y5 "Year number"
- Model!D6:Y6 "Operations flag"
- Model!D7:Y7 "Operating year number"
- Model!D8:Y8 "Repayment flag"
- Model!D11:Y11 "Tariff"
- Model!D12:Y12 "Revenue (banking case, P50)"
- Model!D13:Y13 "Revenue (actual)"
- Model!D14:Y14 "Operating costs"
- Model!D15:Y15 "Major maintenance"
- Model!D16:Y16 "EBITDA"
- Model!D19:Y19 "Tax depreciation"
- Model!D20:Y20 "Tax book value - closing"
- Model!D21:Y21 "Taxable income (unlevered)"
- Model!D22:Y22 "Tax losses used"
- Model!D23:Y23 "Tax losses carried forward - closing"
- Model!D24:Y24 "Cash tax"
- Model!D27:Y27 "Cash flow available for debt service (CFADS)"
- Model!D28:Y28 "Banking-case CFADS (pre-tax)"
- Model!D29:Y29 "Banking-case CFADS in repayment years"
- Model!D30:Y30 "Debt drawdown"
- Model!D31:Y31 "Interest during construction (capitalised)"
- Model!D32:Y32 "Construction loan - closing"
- Model!D33:Y33 "Cash interest"
- Model!D34:Y34 "Debt service (sculpted)"
- Model!D35:Y35 "Principal repayment"
- Model!D36:Y36 "Debt balance - closing"
- Model!D39:Y39 "Equity contribution"
- Model!D40:Y40 "Cash flow after debt service"
- Model!D41:Y41 "DSRA target balance"
- Model!D42:Y42 "DSRA funding/(release)"
- Model!D43:Y43 "DSRA balance - closing"
- Model!D46:Y46 "Cash available for distribution"
- Model!D47:Y47 "Actual DSCR"
- Model!D48:Y48 "Lock-up test passed"
- Model!D49:Y49 "Consecutive passing years"
- Model!D50:Y50 "Cash trapped"
- Model!D51:Y51 "Trapped cash released"
- Model!D52:Y52 "Lock-up account - closing"
- Model!D53:Y53 "Distributions to equity"
- Model!D54:Y54 "Equity cash flow"
- Model!C57 "Total construction capex"
- Model!C58 "Debt at COD"
- Model!C59 "PV of repayment-year CFADS at COD"
- Model!C60 "Sculpted DSCR"
- Model!C61 "Equity IRR"

TERMS:
TIMELINE. Year numbers count from financial close (close = 0). Construction runs in years 1..COD year; operations start the year after. Operating year number = 1 in the first operating year, then +1 each year. Repayment years are operating years up to and including the debt tenor.
CONSTRUCTION FUNDING. Each construction year's capex is funded by debt (gearing x capex) and equity (the rest). Interest during construction on the opening debt balance is capitalised (added to the loan); no cash interest is paid before operations. The construction loan line is a memo corkscrew of the debt raised (opening + drawdown + capitalised interest): it stays flat once operations start (it is not zeroed or repaid; repayments run through the debt balance line), and debt at COD = its balance at the end of the COD year.
OPERATIONS. Revenue ($m) = capacity (MW) x net generation hours x tariff ($/MWh) / 1,000,000, in operating years only. The tariff is indexed every year from close. Operating costs are the first-year opex escalated each operating year after the first (first-year opex x (1 + escalation)^(operating year - 1)). A major maintenance cost is incurred in every operating year that is a multiple of the maintenance interval.
TAX (computed unlevered, i.e. without the interest deduction, so CFADS does not depend on the debt). Tax depreciation is straight line: total capex / tax life per operating year, never more than the remaining tax book value. Taxable income = EBITDA - tax depreciation. Tax losses are carried forward without limit and used against positive taxable income in later years before any tax is paid. Cash tax = tax rate x positive taxable income after losses used.
BANKING CASE vs ACTUAL. Revenue (banking case) uses the P50 generation hours; actual revenue = banking-case revenue x that year's availability. Everything else uses actual revenue, except the debt sculpting: it was fixed at financial close on the BANKING-CASE CFADS = banking-case revenue - operating costs - major maintenance (pre-tax). Below, in the sculpting formulas, read 'CFADS' as banking-case CFADS.
CFADS = EBITDA - cash tax. DEBT SCULPTING: debt service in each repayment year is proportional to that year's CFADS and scaled so that the loan is exactly repaid at the end of the tenor: debt service = CFADS x debt at COD / PV(repayment-year CFADS), where the PV uses the debt rate and is measured at COD. Cash interest in operations is the rate times the opening balance; principal = debt service - interest. The resulting constant DSCR = PV(repayment-year CFADS) / debt at COD.
DSRA. In operating years the reserve target is the DSRA % of NEXT year's debt service (zero in the final model year). If the target is at or above the opening balance, the account is topped up from cash after debt service (never more than the positive cash available); otherwise the excess is released. If cash after debt service is negative, the DSRA is instead drawn to cover the shortfall (never more than its opening balance) and is not topped up that year. Cash available for distribution = cash after debt service - DSRA funding (+ releases).
LOCK-UP. Actual DSCR = actual CFADS / debt service (0 when there is no debt service). The lock-up test passes in a repayment year when actual DSCR >= the lock-up ratio, and always passes in years that are not repayment years. In a failing year the positive cash available for distribution is trapped in the lock-up account instead of being distributed. Count consecutive passing years (reset to 0 by a failure; the count runs from close); in a year that makes the count at least 2, the whole opening lock-up balance is released to equity. Distributions = cash available for distribution - cash trapped + cash released.
EQUITY IRR = IRR of yearly equity cash flows (distributions - equity contributions).

CONVENTIONS:
- Annual periods; flows at year end; the close column holds opening balances.
- All balances and costs are positive numbers.
- Flags are 1 or 0 and should be used to switch formulas on and off.

RULES:
- Every formula must be live and linked to the inputs: the model will be re-calculated with different input values, so typed numbers will be wrong.
- Do not change inputs (the Assumptions sheet and any given values), labels or headers.
- Allowed functions: SUM, AVERAGE, MIN, MAX, COUNT, IF, IFERROR, AND, OR, NOT, ABS, ROUND, ROUNDUP, ROUNDDOWN, INT, MOD, POWER, SQRT, LN, EXP, SIGN, SUMPRODUCT, NPV, PMT, IRR, INDEX, MATCH, CHOOSE.
- You may use empty cells for helper calculations.

Assumptions sheet: C4 Commercial operation starts after construction year; C5 Debt tenor (operating years); C6 Capacity; C7 Net generation hours per year; C8 Tariff indexation (per year); C9 Opex in the first operating year; C10 Gearing (debt share of construction capex); C11 Debt interest rate; C12 Opex escalation (per year); C13 Tax rate; C14 Tax depreciation life (years, straight line); C15 DSRA target (share of next year's debt service); C16 Major maintenance cost per event; C17 Major maintenance every (operating years); C18 Distribution lock-up DSCR; row 20 Construction capex (D:Y); row 21 Availability (actual generation / P50) (D:Y)

Use the tools to inspect and edit the workbook. Call submit when you are done.
````

## Reference formulas (first projection column and single-cell results)

| Cell | Label | Formula |
|---|---|---|
| Model!D5 | Model!D5 (Year number FY2027) | `=C5+1` |
| Model!D6 | Model!D6 (Operations flag FY2027) | `=IF(D5>Assumptions!$C$4,1,0)` |
| Model!D7 | Model!D7 (Operating year number FY2027) | `=C7+D6` |
| Model!D8 | Model!D8 (Repayment flag FY2027) | `=IF(AND(D6=1,D7<=Assumptions!$C$5),1,0)` |
| Model!D11 | Model!D11 (Tariff FY2027) | `=C11*(1+Assumptions!$C$8)` |
| Model!D12 | Model!D12 (Revenue (banking case, P50) FY2027) | `=D6*Assumptions!$C$6*Assumptions!$C$7*D11/1000000` |
| Model!D13 | Model!D13 (Revenue (actual) FY2027) | `=D12*Assumptions!D21` |
| Model!D14 | Model!D14 (Operating costs FY2027) | `=D6*Assumptions!$C$9*(1+Assumptions!$C$12)^(D7-1)` |
| Model!D15 | Model!D15 (Major maintenance FY2027) | `=IF(AND(D6=1,MOD(D7,Assumptions!$C$17)=0),Assumptions!$C$16,0)` |
| Model!D16 | Model!D16 (EBITDA FY2027) | `=D13-D14-D15` |
| Model!D19 | Model!D19 (Tax depreciation FY2027) | `=D6*MIN(C20,$C$57/Assumptions!$C$14)` |
| Model!D20 | Model!D20 (Tax book value - closing FY2027) | `=C20+Assumptions!D20-D19` |
| Model!D21 | Model!D21 (Taxable income (unlevered) FY2027) | `=D16-D19` |
| Model!D22 | Model!D22 (Tax losses used FY2027) | `=MIN(C23,MAX(0,D21))` |
| Model!D23 | Model!D23 (Tax losses carried forward - closing FY2027) | `=C23-D22+MAX(0,-D21)` |
| Model!D24 | Model!D24 (Cash tax FY2027) | `=(MAX(0,D21)-D22)*Assumptions!$C$13` |
| Model!D27 | Model!D27 (Cash flow available for debt service (CFADS) FY2027) | `=D16-D24` |
| Model!D28 | Model!D28 (Banking-case CFADS (pre-tax) FY2027) | `=D12-D14-D15` |
| Model!D29 | Model!D29 (Banking-case CFADS in repayment years FY2027) | `=D8*D28` |
| Model!D30 | Model!D30 (Debt drawdown FY2027) | `=Assumptions!D20*Assumptions!$C$10` |
| Model!D31 | Model!D31 (Interest during construction (capitalised) FY2027) | `=(1-D6)*C32*Assumptions!$C$11` |
| Model!D32 | Model!D32 (Construction loan - closing FY2027) | `=C32+D30+D31` |
| Model!D33 | Model!D33 (Cash interest FY2027) | `=D6*C36*Assumptions!$C$11` |
| Model!D34 | Model!D34 (Debt service (sculpted) FY2027) | `=D29*$C$58/$C$59` |
| Model!D35 | Model!D35 (Principal repayment FY2027) | `=D8*(D34-D33)` |
| Model!D36 | Model!D36 (Debt balance - closing FY2027) | `=C36+D30+D31-D35` |
| Model!D39 | Model!D39 (Equity contribution FY2027) | `=Assumptions!D20*(1-Assumptions!$C$10)` |
| Model!D40 | Model!D40 (Cash flow after debt service FY2027) | `=D27-D34` |
| Model!D41 | Model!D41 (DSRA target balance FY2027) | `=D6*Assumptions!$C$15*E34` |
| Model!D42 | Model!D42 (DSRA funding/(release) FY2027) | `=IF(D40<0,-MIN(C43,-D40),IF(D41>=C43,MIN(MAX(0,D40),D41-C43),D41-C43))` |
| Model!D43 | Model!D43 (DSRA balance - closing FY2027) | `=C43+D42` |
| Model!D46 | Model!D46 (Cash available for distribution FY2027) | `=D6*(D40-D42)` |
| Model!D47 | Model!D47 (Actual DSCR FY2027) | `=IF(D34>0,D27/D34,0)` |
| Model!D48 | Model!D48 (Lock-up test passed FY2027) | `=IF(D8=1,IF(D47>=Assumptions!$C$18,1,0),1)` |
| Model!D49 | Model!D49 (Consecutive passing years FY2027) | `=IF(D48=1,C49+1,0)` |
| Model!D50 | Model!D50 (Cash trapped FY2027) | `=IF(D48=0,MAX(0,D46),0)` |
| Model!D51 | Model!D51 (Trapped cash released FY2027) | `=IF(D49>=2,C52,0)` |
| Model!D52 | Model!D52 (Lock-up account - closing FY2027) | `=C52+D50-D51` |
| Model!D53 | Model!D53 (Distributions to equity FY2027) | `=D46-D50+D51` |
| Model!D54 | Model!D54 (Equity cash flow FY2027) | `=D53-D39` |
| Model!C57 | Model!C57 (Total construction capex) | `=SUM(Assumptions!$D$20:$Y$20)` |
| Model!C58 | Model!C58 (Debt at COD) | `=$E$32` |
| Model!C59 | Model!C59 (PV of repayment-year CFADS at COD) | `=NPV(Assumptions!$C$11,$D$29:$Y$29)*(1+Assumptions!$C$11)^2` |
| Model!C60 | Model!C60 (Sculpted DSCR) | `=$C$59/$C$58` |
| Model!C61 | Model!C61 (Equity IRR) | `=IRR($D$54:$Y$54)` |
