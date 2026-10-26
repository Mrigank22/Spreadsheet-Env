# repair-d5-s0

**Core repair task: latent bugs in a circular three-statement model.** Family `repair`, level 5, training seed 0; 280 graded cells, 11 perturbation scenarios.

## What the agent sees

````text
You are reviewing a packaged food company three-statement model (sheets: Assumptions, IS, BS, CFS; amounts in $m). Historical columns are actuals; forecast columns are formulas.

TASK: The model may contain errors in its forecast formulas, or it may be correct. Fix every formula that deviates from the methodology; if the model is correct, do not change it.

RULES:
- The methodology below is authoritative. A formula is an error if it deviates from it.
- Do not change inputs, actuals or labels. Fix formulas only; keep them live (no typed numbers): the model will be re-calculated with different input values.
- Sign convention: income-statement costs are positive numbers that are subtracted; cash outflows on the cash flow statement are negative.
- Allowed functions: SUM, AVERAGE, MIN, MAX, COUNT, IF, IFERROR, AND, OR, NOT, ABS, ROUND, ROUNDUP, ROUNDDOWN, INT, MOD, POWER, SQRT, LN, EXP, SIGN, SUMPRODUCT, NPV, PMT, IRR, INDEX, MATCH, CHOOSE.
- Iterative calculation is enabled (circular references through average balances are intended).

METHODOLOGY (forecast formulas):
- IS row 5 "Revenue": prior-year revenue x (1 + revenue growth for the year)
- IS row 6 "Cost of goods sold": revenue x COGS %
- IS row 7 "Gross profit": revenue - COGS
- IS row 8 "SG&A": revenue x SG&A %
- IS row 9 "EBITDA": gross profit - SG&A
- IS row 10 "Depreciation & amortisation": prior-year closing net PP&E x D&A %
- IS row 11 "EBIT": EBITDA - D&A
- IS row 12 "Interest expense": the average of opening and closing term debt balance x term-debt interest rate, plus the average of opening and closing revolver balance x revolver rate
- IS row 13 "Interest income": the average of opening and closing cash balance x interest rate earned on cash
- IS row 14 "Pre-tax income": EBIT - interest expense + interest income
- IS row 15 "Income tax": pre-tax income x tax rate, but zero when pre-tax income is negative (no tax credit for losses)
- IS row 16 "Net income": pre-tax income - tax
- BS row 5 "Cash": closing cash from the cash flow statement
- BS row 6 "Accounts receivable": revenue x DSO / 365
- BS row 7 "Inventory": COGS x DIO / 365
- BS row 8 "Total current assets": sum of cash, accounts receivable, inventory
- BS row 9 "Net PP&E": prior-year net PP&E + capex - D&A (capex is shown as a negative cash flow, so it is subtracted)
- BS row 10 "Total assets": current assets + PP&E
- BS row 11 "Accounts payable": COGS x DPO / 365
- BS row 12 "Term debt": prior-year term debt + term-debt cash flow (repayments are negative)
- BS row 13 "Revolver": prior-year revolver + revolver draw/(repayment)
- BS row 14 "Total liabilities": sum of accounts payable, term debt, revolver
- BS row 15 "Common stock": unchanged from the prior year (no issuance)
- BS row 16 "Retained earnings": prior-year retained earnings + net income + dividend cash flow (dividends are negative)
- BS row 17 "Total equity": common stock + retained earnings
- BS row 18 "Total liabilities & equity": total liabilities + total equity
- BS row 19 "Balance check (assets - L&E)": total assets - total liabilities & equity, rounded to 6 dp; must be 0
- CFS row 5 "Net income": net income from the income statement
- CFS row 6 "Add back: D&A": D&A from the income statement
- CFS row 7 "(Increase)/decrease in receivables": prior-year receivables - current receivables
- CFS row 8 "(Increase)/decrease in inventory": prior-year inventory - current inventory
- CFS row 9 "Increase/(decrease) in payables": current payables - prior-year payables
- CFS row 10 "Cash flow from operations": sum of the operating lines above
- CFS row 11 "Capital expenditure": minus revenue x capex % (a cash outflow, so negative)
- CFS row 12 "Cash flow from investing": capital expenditure
- CFS row 13 "Term-debt repayment": minus the smaller of the scheduled repayment and the opening term-debt balance
- CFS row 14 "Dividends paid": minus payout ratio x net income, and zero when net income is negative
- CFS row 15 "Revolver draw/(repayment)": closing revolver = MAX(0, opening revolver + minimum cash - cash before revolver); this line is closing minus opening revolver
- CFS row 16 "Cash flow from financing": sum of the financing lines above
- CFS row 17 "Net change in cash": operating + investing + financing
- CFS row 18 "Beginning cash": prior-year closing cash from the balance sheet
- CFS row 19 "Ending cash": beginning cash + net change in cash
- CFS row 20 "Memo: cash before revolver": beginning cash + operating + investing + financing excluding the revolver

MODEL MAP:
Period columns (same on every sheet): actuals C:D (FY2020A, FY2021A); forecast E:J (FY2022E, FY2023E, FY2024E, FY2025E, FY2026E, FY2027E). Column A = labels, B = units.
Assumptions: C4 COGS (% of revenue) = 0.752; C5 SG&A (% of revenue) = 0.102; C6 D&A (% of opening PP&E) = 0.097; C7 Capex (% of revenue) = 0.064; C8 Tax rate = 0.231; C9 Receivable days (DSO) = 33; C10 Inventory days (DIO) = 67; C11 Payable days (DPO) = 45; C12 Interest rate on term debt = 0.0787; C13 Scheduled term-debt repayment = 499.6; C14 Interest rate earned on cash = 0.0192; C15 Dividend payout ratio = 0.2; C16 Minimum cash balance = 267.7; C17 Interest rate on revolver = 0.0945; row 19 Revenue growth
IS: row 5 Revenue; row 6 Cost of goods sold; row 7 Gross profit; row 8 SG&A; row 9 EBITDA; row 10 Depreciation & amortisation; row 11 EBIT; row 12 Interest expense; row 13 Interest income; row 14 Pre-tax income; row 15 Income tax; row 16 Net income
BS: row 5 Cash; row 6 Accounts receivable; row 7 Inventory; row 8 Total current assets; row 9 Net PP&E; row 10 Total assets; row 11 Accounts payable; row 12 Term debt; row 13 Revolver; row 14 Total liabilities; row 15 Common stock; row 16 Retained earnings; row 17 Total equity; row 18 Total liabilities & equity; row 19 Balance check (assets - L&E)
CFS: row 5 Net income; row 6 Add back: D&A; row 7 (Increase)/decrease in receivables; row 8 (Increase)/decrease in inventory; row 9 Increase/(decrease) in payables; row 10 Cash flow from operations; row 11 Capital expenditure; row 12 Cash flow from investing; row 13 Term-debt repayment; row 14 Dividends paid; row 15 Revolver draw/(repayment); row 16 Cash flow from financing; row 17 Net change in cash; row 18 Beginning cash; row 19 Ending cash; row 20 Memo: cash before revolver

Use the tools to inspect and edit the workbook. Call submit when you are done (you may list the cells you fixed in the notes).
````

## Injected bugs (hidden from the agent)

| Operator | Effect | Cells | Bug | Correct |
|---|---|---|---|---|
| HARDCODE_PASTE | latent | IS!F10 (Depreciation & amortisation FY2023E) | `232.00409544480002` | `=BS!E9*Assumptions!$C$6` |
| OPERATOR_SWAP | visible | IS!J6 (Cost of goods sold FY2027E) | `=J5/Assumptions!$C$4` | `=J5*Assumptions!$C$4` |
| COINCIDENT_REF | latent | CFS!F20 (Memo: cash before revolver FY2023E) | `=F18+F10+F12+E13+F14` | `=F18+F10+F12+F13+F14` |

## Reference formulas (first projection column and single-cell results)

| Cell | Label | Formula |
|---|---|---|
| BS!E5 | BS!E5 (Cash FY2022E) | `=CFS!E19` |
| BS!E6 | BS!E6 (Accounts receivable FY2022E) | `=IS!E5*Assumptions!$C$9/365` |
| BS!E7 | BS!E7 (Inventory FY2022E) | `=IS!E6*Assumptions!$C$10/365` |
| BS!E8 | BS!E8 (Total current assets FY2022E) | `=SUM(E5:E7)` |
| BS!E9 | BS!E9 (Net PP&E FY2022E) | `=D9-CFS!E11-IS!E10` |
| BS!E10 | BS!E10 (Total assets FY2022E) | `=E8+E9` |
| BS!E11 | BS!E11 (Accounts payable FY2022E) | `=IS!E6*Assumptions!$C$11/365` |
| BS!E12 | BS!E12 (Term debt FY2022E) | `=D12+CFS!E13` |
| BS!E13 | BS!E13 (Revolver FY2022E) | `=D13+CFS!E15` |
| BS!E14 | BS!E14 (Total liabilities FY2022E) | `=SUM(E11:E13)` |
| BS!E15 | BS!E15 (Common stock FY2022E) | `=D15` |
| BS!E16 | BS!E16 (Retained earnings FY2022E) | `=D16+IS!E16+CFS!E14` |
| BS!E17 | BS!E17 (Total equity FY2022E) | `=E15+E16` |
| BS!E18 | BS!E18 (Total liabilities & equity FY2022E) | `=E14+E17` |
| BS!E19 | BS!E19 (Balance check (assets - L&E) FY2022E) | `=ROUND(E10-E18,6)` |
| CFS!E5 | CFS!E5 (Net income FY2022E) | `=IS!E16` |
| CFS!E6 | CFS!E6 (Add back: D&A FY2022E) | `=IS!E10` |
| CFS!E7 | CFS!E7 ((Increase)/decrease in receivables FY2022E) | `=BS!D6-BS!E6` |
| CFS!E8 | CFS!E8 ((Increase)/decrease in inventory FY2022E) | `=BS!D7-BS!E7` |
| CFS!E9 | CFS!E9 (Increase/(decrease) in payables FY2022E) | `=BS!E11-BS!D11` |
| CFS!E10 | CFS!E10 (Cash flow from operations FY2022E) | `=SUM(E5:E9)` |
| CFS!E11 | CFS!E11 (Capital expenditure FY2022E) | `=-IS!E5*Assumptions!$C$7` |
| CFS!E12 | CFS!E12 (Cash flow from investing FY2022E) | `=E11` |
| CFS!E13 | CFS!E13 (Term-debt repayment FY2022E) | `=-MIN(Assumptions!$C$13,BS!D12)` |
| CFS!E14 | CFS!E14 (Dividends paid FY2022E) | `=-MAX(0,IS!E16)*Assumptions!$C$15` |
| CFS!E15 | CFS!E15 (Revolver draw/(repayment) FY2022E) | `=MAX(0,BS!D13+Assumptions!$C$16-E20)-BS!D13` |
| CFS!E16 | CFS!E16 (Cash flow from financing FY2022E) | `=SUM(E13:E15)` |
| CFS!E17 | CFS!E17 (Net change in cash FY2022E) | `=E10+E12+E16` |
| CFS!E18 | CFS!E18 (Beginning cash FY2022E) | `=BS!D5` |
| CFS!E19 | CFS!E19 (Ending cash FY2022E) | `=E18+E17` |
| CFS!E20 | CFS!E20 (Memo: cash before revolver FY2022E) | `=E18+E10+E12+E13+E14` |
| IS!E5 | IS!E5 (Revenue FY2022E) | `=D5*(1+Assumptions!E19)` |
| IS!E6 | IS!E6 (Cost of goods sold FY2022E) | `=E5*Assumptions!$C$4` |
| IS!E7 | IS!E7 (Gross profit FY2022E) | `=E5-E6` |
| IS!E8 | IS!E8 (SG&A FY2022E) | `=E5*Assumptions!$C$5` |
| IS!E9 | IS!E9 (EBITDA FY2022E) | `=E7-E8` |
| IS!E10 | IS!E10 (Depreciation & amortisation FY2022E) | `=BS!D9*Assumptions!$C$6` |
| IS!E11 | IS!E11 (EBIT FY2022E) | `=E9-E10` |
| IS!E12 | IS!E12 (Interest expense FY2022E) | `=AVERAGE(BS!D12,BS!E12)*Assumptions!$C$12+AVERAGE(BS!D13,BS!E13)*Assumptions!$C$17` |
| IS!E13 | IS!E13 (Interest income FY2022E) | `=AVERAGE(BS!D5,BS!E5)*Assumptions!$C$14` |
| IS!E14 | IS!E14 (Pre-tax income FY2022E) | `=E11-E12+E13` |
| IS!E15 | IS!E15 (Income tax FY2022E) | `=MAX(0,E14)*Assumptions!$C$8` |
| IS!E16 | IS!E16 (Net income FY2022E) | `=E14-E15` |
| BS!C8 | BS!C8 (Total current assets FY2020A) | `=SUM(C5:C7)` |
| BS!D8 | BS!D8 (Total current assets FY2021A) | `=SUM(D5:D7)` |
| BS!C10 | BS!C10 (Total assets FY2020A) | `=C8+C9` |
| BS!D10 | BS!D10 (Total assets FY2021A) | `=D8+D9` |
| BS!C14 | BS!C14 (Total liabilities FY2020A) | `=SUM(C11:C13)` |
| BS!D14 | BS!D14 (Total liabilities FY2021A) | `=SUM(D11:D13)` |
| BS!C17 | BS!C17 (Total equity FY2020A) | `=C15+C16` |
| BS!D17 | BS!D17 (Total equity FY2021A) | `=D15+D16` |
| BS!C18 | BS!C18 (Total liabilities & equity FY2020A) | `=C14+C17` |
| BS!D18 | BS!D18 (Total liabilities & equity FY2021A) | `=D14+D17` |
| BS!C19 | BS!C19 (Balance check (assets - L&E) FY2020A) | `=ROUND(C10-C18,6)` |
| BS!D19 | BS!D19 (Balance check (assets - L&E) FY2021A) | `=ROUND(D10-D18,6)` |
| IS!C7 | IS!C7 (Gross profit FY2020A) | `=C5-C6` |
| IS!D7 | IS!D7 (Gross profit FY2021A) | `=D5-D6` |
| IS!C9 | IS!C9 (EBITDA FY2020A) | `=C7-C8` |
| IS!D9 | IS!D9 (EBITDA FY2021A) | `=D7-D8` |
| IS!C11 | IS!C11 (EBIT FY2020A) | `=C9-C10` |
| IS!D11 | IS!D11 (EBIT FY2021A) | `=D9-D10` |
| IS!C14 | IS!C14 (Pre-tax income FY2020A) | `=C11-C12+C13` |
| IS!D14 | IS!D14 (Pre-tax income FY2021A) | `=D11-D12+D13` |
| IS!C16 | IS!C16 (Net income FY2020A) | `=C14-C15` |
| IS!D16 | IS!D16 (Net income FY2021A) | `=D14-D15` |
