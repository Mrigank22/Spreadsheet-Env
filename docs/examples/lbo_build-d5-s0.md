# lbo_build-d5-s0

**LBO term sheet: circular average-balance interest, sweep grid, covenant with equity cure.** Family `lbo_build`, level 5, training seed 0; 277 graded cells, 11 perturbation scenarios.

## What the agent sees

````text
You are building a leveraged buyout (LBO) model with a debt schedule in a spreadsheet (sheets: Assumptions, Model; amounts in $m). Column C holds the starting point, columns D:J the projection (FY2027E, FY2028E, FY2029E, FY2030E, FY2031E, FY2032E, FY2033E).

TASK: the cells below are empty. Write a formula in every one so that the model implements the TERMS below exactly. Work out each row's logic from the terms and the row labels.
- Model!D5:J5 "Revenue"
- Model!D6:J6 "EBITDA"
- Model!D7:J7 "D&A"
- Model!D8:J8 "Capital expenditure"
- Model!D9:J9 "Net working capital"
- Model!D10:J10 "Increase in net working capital"
- Model!D13:J13 "Term Loan A - mandatory amortisation"
- Model!D14:J14 "Term Loan B - mandatory amortisation"
- Model!D15:J15 "Revolver - closing balance"
- Model!D16:J16 "Revolver - net draw/(repayment)"
- Model!D17:J17 "Revolver - cash interest"
- Model!D18:J18 "Revolver - commitment fee"
- Model!D19:J19 "Excess cash after revolver"
- Model!D20:J20 "Opening leverage (x EBITDA)"
- Model!D21:J21 "Sweep % for the year"
- Model!D22:J22 "Cash available for sweep"
- Model!D23:J23 "Term Loan A - cash sweep repayment"
- Model!D24:J24 "Term Loan A - closing balance"
- Model!D25:J25 "Term Loan A - cash interest"
- Model!D26:J26 "Term Loan B - cash sweep repayment"
- Model!D27:J27 "Term Loan B - closing balance"
- Model!D28:J28 "Term Loan B - cash interest"
- Model!D29:J29 "Senior notes - closing balance"
- Model!D30:J30 "Senior notes - cash interest"
- Model!D31:J31 "PIK notes - closing balance"
- Model!D32:J32 "PIK notes - accrued (non-cash) interest"
- Model!D35:J35 "Total cash interest and fees"
- Model!D36:J36 "Pre-tax income"
- Model!D37:J37 "Cash taxes"
- Model!D38:J38 "Free cash flow before debt repayment"
- Model!D39:J39 "Total mandatory amortisation"
- Model!D40:J40 "Cash available after mandatory amortisation"
- Model!D43:J43 "Cash before equity cure"
- Model!D44:J44 "Total debt - closing"
- Model!D45:J45 "Equity cure"
- Model!D46:J46 "Closing cash"
- Model!D47:J47 "Net leverage (x EBITDA)"
- Model!D50:J50 "Sponsor cash flows"
- Model!C53 "Entry enterprise value"
- Model!C54 "Transaction fees"
- Model!C55 "Total uses"
- Model!C56 "Total debt raised"
- Model!C57 "Sponsor equity"
- Model!C58 "Exit enterprise value"
- Model!C59 "Net debt at exit"
- Model!C60 "Exit equity value"
- Model!C61 "Total sponsor equity invested"
- Model!C62 "Sponsor MOIC"
- Model!C63 "Sponsor IRR"

TERMS:
TRANSACTION. A sponsor acquires the company at the entry multiple times LTM EBITDA (the enterprise value). Transaction fees are a percentage of enterprise value. The company must hold the minimum cash balance at close. Total uses = enterprise value + fees + minimum cash. Sponsor equity funds the part of total uses not funded by debt.
FINANCING (sizes are multiples of LTM EBITDA, drawn in full at close):
- Term Loan A: cash interest at its fixed rate on the average of opening and closing balance; mandatory amortisation each year of the amortisation % times the ORIGINAL principal, never more than the balance outstanding.
- Term Loan B: cash interest at its fixed rate on the average of opening and closing balance; mandatory amortisation each year of the amortisation % times the ORIGINAL principal, never more than the balance outstanding.
- Senior notes: cash coupon at the fixed rate on the average of opening and closing balance; repaid in full at maturity, which is after the projection (no repayment in the model).
- PIK notes: no cash interest; interest at the PIK rate on the opening balance accrues to principal every year. Accrued PIK interest is tax-deductible.
- Revolver: undrawn at close; cash interest at its rate on the average of opening and closing drawn balance. At each year end, cash available = opening cash + free cash flow - mandatory amortisation - minimum cash. If this is negative, the revolver is drawn to cover the shortfall (up to the commitment); if positive, it first repays any revolver balance. A commitment fee is paid in cash on the undrawn commitment (commitment - the average of opening and closing drawn balance); it is part of total cash interest and fees, and tax-deductible.
SWEEP GRID. Opening leverage = all debt at the start of the year (every tranche incl. PIK notes, plus the revolver) / prior-year EBITDA. Sweep % = the top-tier % if opening leverage is above the top threshold; else the middle-tier % if above the middle threshold; else the bottom-tier % if above the bottom threshold; else 0%.
CASH SWEEP. Excess cash = cash available plus the revolver net draw (net repayment counts as negative), floored at zero. The sweep % of excess cash prepays term loans at year end: first Term Loan A, then Term Loan B with whatever is left, each capped at its balance remaining after mandatory amortisation. Cash not swept stays on balance sheet.
OPERATIONS. Revenue grows at the yearly growth rate; EBITDA = revenue x EBITDA margin for the year. D&A, capex and net working capital are percentages of revenue; an increase in NWC uses cash. Taxes = tax rate x (EBITDA - D&A - cash interest - PIK interest), zero if that amount is negative. Free cash flow before debt repayment = EBITDA - cash interest - taxes - capex - increase in NWC.
COVENANT. At each year end, net leverage = (total debt incl. PIK notes and revolver - closing cash) / EBITDA must not exceed that year's maximum. If it would (using cash before any cure), the sponsor injects just enough equity as cash to bring it to the maximum: equity cure = MAX(0, total debt - cash before cure - maximum x EBITDA). The cure is added to closing cash after the sweep (it is not swept that year).
EXIT at the end of FY2033E: exit EV = exit multiple x final-year EBITDA; exit equity = exit EV - (all debt outstanding incl. PIK notes and revolver - closing cash). MOIC = exit equity / (sponsor equity + all equity cures). Sponsor cash flows: - sponsor equity at close, - the equity cure each year, + exit equity in the final year; IRR = IRR of those flows (one value per column, close included).

CONVENTIONS:
- All flows occur at year end. The first column is the closing date of the transaction (balances at close).
- Debt balances, repayments and interest are positive numbers; repayments reduce balances.
- Interest is charged on the average of opening and closing balance of each tranche.
- Sizes, rates and percentages are on the Assumptions sheet; growth and margins are given per year.
- Revolver net draw/(repayment) is positive when the revolver is drawn.

RULES:
- Every formula must be live and linked to the inputs: the model will be re-calculated with different input values, so typed numbers will be wrong.
- Do not change inputs (the Assumptions sheet and any given values), labels or headers.
- Allowed functions: SUM, AVERAGE, MIN, MAX, COUNT, IF, IFERROR, AND, OR, NOT, ABS, ROUND, ROUNDUP, ROUNDDOWN, INT, MOD, POWER, SQRT, LN, EXP, SIGN, SUMPRODUCT, NPV, PMT, IRR, INDEX, MATCH, CHOOSE.
- Iterative calculation is enabled in this workbook (the circularity described in the terms is intended).
- You may use empty cells for helper calculations.

Assumptions sheet: C4 Entry multiple (EV / LTM EBITDA); C5 Transaction fees (% of EV); C6 Minimum cash balance; C7 Tax rate; C8 D&A (% of revenue); C9 Capex (% of revenue); C10 Net working capital (% of revenue); C11 Exit multiple (EV / final-year EBITDA); C12 Term Loan A size (x LTM EBITDA); C13 Term Loan A interest rate; C14 Term Loan A amortisation (% of original principal / yr); C15 Term Loan B size (x LTM EBITDA); C16 Term Loan B interest rate; C17 Term Loan B amortisation (% of original principal / yr); C18 Senior notes size (x LTM EBITDA); C19 Senior notes interest rate; C20 PIK notes size (x LTM EBITDA); C21 PIK notes interest rate; C22 Revolver commitment; C23 Revolver interest rate; C24 Revolver commitment fee (on the undrawn amount); C25 Sweep grid: top leverage threshold (x); C26 Sweep grid: middle leverage threshold (x); C27 Sweep grid: bottom leverage threshold (x); C28 Sweep % above the top threshold; C29 Sweep % above the middle threshold; C30 Sweep % above the bottom threshold; row 32 Revenue growth (D:J); row 33 EBITDA margin (D:J); row 34 Maximum net leverage covenant (x EBITDA) (D:J)

Use the tools to inspect and edit the workbook. Call submit when you are done.
````

## Reference formulas (first projection column and single-cell results)

| Cell | Label | Formula |
|---|---|---|
| Model!D5 | Model!D5 (Revenue FY2027E) | `=C5*(1+Assumptions!D32)` |
| Model!D6 | Model!D6 (EBITDA FY2027E) | `=D5*Assumptions!D33` |
| Model!D7 | Model!D7 (D&A FY2027E) | `=D5*Assumptions!$C$8` |
| Model!D8 | Model!D8 (Capital expenditure FY2027E) | `=D5*Assumptions!$C$9` |
| Model!D9 | Model!D9 (Net working capital FY2027E) | `=D5*Assumptions!$C$10` |
| Model!D10 | Model!D10 (Increase in net working capital FY2027E) | `=D9-C9` |
| Model!D13 | Model!D13 (Term Loan A - mandatory amortisation FY2027E) | `=MIN(C24,$C$24*Assumptions!$C$14)` |
| Model!D14 | Model!D14 (Term Loan B - mandatory amortisation FY2027E) | `=MIN(C27,$C$27*Assumptions!$C$17)` |
| Model!D15 | Model!D15 (Revolver - closing balance FY2027E) | `=MIN(Assumptions!$C$22,MAX(0,C15-D40))` |
| Model!D16 | Model!D16 (Revolver - net draw/(repayment) FY2027E) | `=D15-C15` |
| Model!D17 | Model!D17 (Revolver - cash interest FY2027E) | `=AVERAGE(C15,D15)*Assumptions!$C$23` |
| Model!D18 | Model!D18 (Revolver - commitment fee FY2027E) | `=Assumptions!$C$24*(Assumptions!$C$22-AVERAGE(C15,D15))` |
| Model!D19 | Model!D19 (Excess cash after revolver FY2027E) | `=MAX(0,D40+D16)` |
| Model!D20 | Model!D20 (Opening leverage (x EBITDA) FY2027E) | `=(C24+C27+C29+C31+C15)/C6` |
| Model!D21 | Model!D21 (Sweep % for the year FY2027E) | `=IF(D20>Assumptions!$C$25,Assumptions!$C$28,IF(D20>Assumptions!$C$26,Assumptions!$C$29,IF(D20>Assumptions!$C$27,Assumptions!$C$30,0)))` |
| Model!D22 | Model!D22 (Cash available for sweep FY2027E) | `=D19*D21` |
| Model!D23 | Model!D23 (Term Loan A - cash sweep repayment FY2027E) | `=MIN(D22,C24-D13)` |
| Model!D24 | Model!D24 (Term Loan A - closing balance FY2027E) | `=C24-D13-D23` |
| Model!D25 | Model!D25 (Term Loan A - cash interest FY2027E) | `=AVERAGE(C24,D24)*Assumptions!$C$13` |
| Model!D26 | Model!D26 (Term Loan B - cash sweep repayment FY2027E) | `=MIN(D22-D23,C27-D14)` |
| Model!D27 | Model!D27 (Term Loan B - closing balance FY2027E) | `=C27-D14-D26` |
| Model!D28 | Model!D28 (Term Loan B - cash interest FY2027E) | `=AVERAGE(C27,D27)*Assumptions!$C$16` |
| Model!D29 | Model!D29 (Senior notes - closing balance FY2027E) | `=C29` |
| Model!D30 | Model!D30 (Senior notes - cash interest FY2027E) | `=AVERAGE(C29,D29)*Assumptions!$C$19` |
| Model!D31 | Model!D31 (PIK notes - closing balance FY2027E) | `=C31*(1+Assumptions!$C$21)` |
| Model!D32 | Model!D32 (PIK notes - accrued (non-cash) interest FY2027E) | `=C31*Assumptions!$C$21` |
| Model!D35 | Model!D35 (Total cash interest and fees FY2027E) | `=D17+D18+D25+D28+D30` |
| Model!D36 | Model!D36 (Pre-tax income FY2027E) | `=D6-D7-D35-D32` |
| Model!D37 | Model!D37 (Cash taxes FY2027E) | `=MAX(0,D36)*Assumptions!$C$7` |
| Model!D38 | Model!D38 (Free cash flow before debt repayment FY2027E) | `=D6-D35-D37-D8-D10` |
| Model!D39 | Model!D39 (Total mandatory amortisation FY2027E) | `=D13+D14` |
| Model!D40 | Model!D40 (Cash available after mandatory amortisation FY2027E) | `=C46+D38-D39-Assumptions!$C$6` |
| Model!D43 | Model!D43 (Cash before equity cure FY2027E) | `=C46+D38-D39+D16-D23-D26` |
| Model!D44 | Model!D44 (Total debt - closing FY2027E) | `=D24+D27+D29+D31+D15` |
| Model!D45 | Model!D45 (Equity cure FY2027E) | `=MAX(0,D44-D43-Assumptions!D34*D6)` |
| Model!D46 | Model!D46 (Closing cash FY2027E) | `=D43+D45` |
| Model!D47 | Model!D47 (Net leverage (x EBITDA) FY2027E) | `=(D44-D46)/D6` |
| Model!D50 | Model!D50 (Sponsor cash flows FY2027E) | `=-D45` |
| Model!C53 | Model!C53 (Entry enterprise value) | `=$C$6*Assumptions!$C$4` |
| Model!C54 | Model!C54 (Transaction fees) | `=$C$53*Assumptions!$C$5` |
| Model!C55 | Model!C55 (Total uses) | `=$C$53+$C$54+Assumptions!$C$6` |
| Model!C56 | Model!C56 (Total debt raised) | `=$C$24+$C$27+$C$29+$C$31` |
| Model!C57 | Model!C57 (Sponsor equity) | `=$C$55-$C$56` |
| Model!C58 | Model!C58 (Exit enterprise value) | `=$J$6*Assumptions!$C$11` |
| Model!C59 | Model!C59 (Net debt at exit) | `=$J$24+$J$27+$J$29+$J$31+$J$15-$J$46` |
| Model!C60 | Model!C60 (Exit equity value) | `=$C$58-$C$59` |
| Model!C61 | Model!C61 (Total sponsor equity invested) | `=$C$57+SUM($D$45:$J$45)` |
| Model!C62 | Model!C62 (Sponsor MOIC) | `=$C$60/$C$61` |
| Model!C63 | Model!C63 (Sponsor IRR) | `=IRR($C$50:$J$50)` |
