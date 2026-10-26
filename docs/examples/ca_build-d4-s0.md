# ca_build-d4-s0

**Credit agreement (document spec): leveraged loan with pricing grid, ECF sweep, revolver, HoldCo PIK and an equity-cure covenant.** Family `ca_build`, level 4, training seed 0; 252 graded cells, 11 perturbation scenarios.

## What the agent sees

````text
You are building a debt model for the borrower under a credit agreement (Brackley Foods) in a spreadsheet (sheets: Assumptions, Model; amounts in $m). Column C holds the starting point, columns D:J the projection (FY2027, FY2028, FY2029, FY2030, FY2031, FY2032, FY2033).

TASK: the cells below are empty. Write a formula in every one so that the model implements the TERMS below exactly. Work out each row's logic from the terms and the row labels.
- Model!D5:J5 "Revenue"
- Model!D6:J6 "EBITDA"
- Model!D7:J7 "D&A"
- Model!D8:J8 "Capital Expenditures"
- Model!D9:J9 "Consolidated Working Capital"
- Model!D10:J10 "Increase in Consolidated Working Capital"
- Model!D11:J11 "Pro Forma Cost Savings added back"
- Model!D12:J12 "Consolidated EBITDA"
- Model!D15:J15 "Adjusted Term SOFR"
- Model!D16:J16 "Applicable Rate"
- Model!D17:J17 "Applicable Commitment Fee Rate"
- Model!D20:J20 "Interest on Term Loans"
- Model!D21:J21 "Interest on Revolving Loans"
- Model!D22:J22 "Commitment Fee"
- Model!D23:J23 "Interest on Senior Notes"
- Model!D24:J24 "Consolidated Cash Interest Expense"
- Model!D25:J25 "Taxes paid in cash"
- Model!D28:J28 "Excess Cash Flow prepayment"
- Model!D29:J29 "Prepayment credit applied to the installment"
- Model!D30:J30 "Scheduled installment paid"
- Model!D31:J31 "Unapplied prepayment credit - closing"
- Model!D32:J32 "Term Loans - closing balance"
- Model!D35:J35 "Excess Cash Flow"
- Model!D36:J36 "Applicable ECF Percentage"
- Model!D39:J39 "Cash before Revolving Loans"
- Model!D40:J40 "Revolving Loans - closing balance"
- Model!D41:J41 "Revolving Loans - borrowing/(repayment)"
- Model!D42:J42 "Senior Notes - closing balance"
- Model!D45:J45 "HoldCo Notes - PIK interest"
- Model!D46:J46 "HoldCo Notes - closing balance"
- Model!D49:J49 "Unrestricted Cash deducted (after the Netting Limit)"
- Model!D50:J50 "First Lien Net Leverage Ratio"
- Model!D51:J51 "Total Net Leverage Ratio (before any Cure Amount)"
- Model!D54:J54 "Cure Amount"
- Model!D55:J55 "Unrestricted Cash - closing"
- Model!C58 "Enterprise Value at closing"
- Model!C59 "Total Uses"
- Model!C60 "Sponsor Equity"
- Model!C61 "Exit Enterprise Value"
- Model!C62 "Exit Equity Value"
- Model!C63 "Total Sponsor Equity invested"
- Model!C64 "Sponsor MOIC"

TERMS:
CREDIT AGREEMENT

CREDIT AGREEMENT dated as of the Closing Date among Brackley Foods Holdings, Inc. ("Holdings"), Brackley Foods Intermediate, LLC (the "Borrower"), the Lenders party hereto and the Administrative Agent. Capitalized amounts, rates and ratios referred to by a caption in quotation marks are set forth in Schedule 1 (the Assumptions sheet of the Model).

ARTICLE I
DEFINITIONS AND ACCOUNTING TERMS

Section 1.01 Defined Terms. As used in this Agreement, the following terms have the meanings specified below:
"Adjusted Term SOFR" means, for any Fiscal Year, the greater of (a) Term SOFR for such Fiscal Year and (b) the Floor.
"Applicable Commitment Fee Rate" means, for any Fiscal Year, "Commitment Fee Rate - Higher" if the First Lien Net Leverage Ratio as of the last day of the most recently ended Fiscal Year for which financial statements have been delivered pursuant to Section 3.01(a) is greater than the "Commitment Fee Step-Down Ratio", and "Commitment Fee Rate - Lower" otherwise; provided that, until the date of delivery of financial statements for the first full Fiscal Year ending after the Closing Date, the Applicable Commitment Fee Rate shall be "Commitment Fee Rate - Higher".
"Applicable ECF Percentage" means, for any Excess Cash Flow Period, (a) "ECF Percentage - Level 1" if the First Lien Net Leverage Ratio as of the last day of such Excess Cash Flow Period is greater than the "ECF Level 1 Ratio", (b) "ECF Percentage - Level 2" if such ratio is greater than the "ECF Level 2 Ratio" but not greater than the "ECF Level 1 Ratio", and (c) 0% otherwise.
"Applicable Rate" means, for any Fiscal Year, the percentage per annum set forth below for the Pricing Level determined by the First Lien Net Leverage Ratio as of the last day of the most recently ended Fiscal Year for which financial statements have been delivered pursuant to Section 3.01(a):
  Pricing Level I: First Lien Net Leverage Ratio greater than the "Pricing Level I Threshold": "Applicable Margin - Pricing Level I";
  Pricing Level II: greater than the "Pricing Level II Threshold" but not greater than the "Pricing Level I Threshold": "Applicable Margin - Pricing Level II";
  Pricing Level III: not greater than the "Pricing Level II Threshold": "Applicable Margin - Pricing Level III";
provided that, until the date of delivery of financial statements for the first full Fiscal Year ending after the Closing Date, the Applicable Rate shall be the rate set forth for Pricing Level I.
"Asset Sale" means any disposition of property of the Borrower or any Subsidiary, other than dispositions of inventory in the ordinary course of business.
"Business Day" means any day other than a Saturday, Sunday or day on which banks in New York City are authorized or required by law to close.
"Capital Expenditures" means, for any period, the capital expenditures of the Borrower and its Subsidiaries for such period determined in accordance with Annex B.
"Change of Control" means the Permitted Holders ceasing to own, directly or indirectly, more than 50% of the voting equity interests of Holdings.
"Closing Date" means the date on which the Term Loans are made, being the last day of the Fiscal Year shown in the first column of the Model.
"Consolidated Cash Interest Expense" means, for any period, the sum of (a) interest on the Term Loans and Revolving Loans, (b) interest on the Senior Notes and (c) Commitment Fees, in each case paid in cash during such period; for the avoidance of doubt, interest on the HoldCo Notes is not Consolidated Cash Interest Expense.
"Consolidated EBITDA" means, for any period, EBITDA for such period plus, without duplication, Pro Forma Cost Savings for such period; provided that the aggregate amount added pursuant to this definition for any period shall not exceed the "Cost Savings Cap" multiplied by EBITDA for such period (that is, Consolidated EBITDA calculated before giving effect to such addition).
"Consolidated First Lien Net Debt" means, as of any date, (a) the aggregate principal amount of Term Loans and Revolving Loans outstanding on such date minus (b) Unrestricted Cash on such date in an amount not exceeding the Netting Limit.
"Consolidated Total Net Debt" means, as of any date, (a) the aggregate principal amount of Term Loans, Revolving Loans and Senior Notes outstanding on such date minus (b) Unrestricted Cash on such date in an amount not exceeding the Netting Limit. The HoldCo Notes are Indebtedness of Holdings, which is not a Subsidiary of the Borrower, and are not included in Consolidated Total Net Debt or Consolidated First Lien Net Debt.
"Cure Amount" has the meaning assigned to such term in Section 5.02(a).
"Declined Proceeds" has the meaning assigned to such term in Section 2.04(e).
"EBITDA" means, for any period, the earnings before interest, taxes, depreciation and amortization of the Borrower and its Subsidiaries for such period determined in accordance with Annex B, without any pro forma adjustment.
"Excess Cash Flow" means, for any Excess Cash Flow Period, an amount (which may be negative) equal to (a) EBITDA for such period minus (b) the sum, without duplication, of (i) Consolidated Cash Interest Expense for such period, (ii) taxes paid in cash during such period, (iii) Capital Expenditures for such period, (iv) the increase in Consolidated Working Capital from the first day to the last day of such period (or minus the amount of any decrease) and (v) the aggregate principal amount of installments of Term Loans paid pursuant to Section 2.03(a) during such period. Prepayments pursuant to Section 2.04 are not deducted.
"Excess Cash Flow Period" means each full Fiscal Year ending after the Closing Date.
"First Lien Net Leverage Ratio" means, as of any date, the ratio of Consolidated First Lien Net Debt as of such date to Consolidated EBITDA for the Test Period ending on such date.
"Fiscal Year" means the fiscal year of the Borrower; each column of the Model after the first is one Fiscal Year.
"Floor" means the "Term SOFR Floor".
"HoldCo Notes" means the senior PIK notes issued by Holdings on the Closing Date in the principal amount equal to the amount set forth opposite "HoldCo Notes" in Schedule 1. Interest accrues at the "HoldCo PIK Rate" on the principal amount outstanding on the first day of each Fiscal Year and is paid in kind by being added to principal on the last day of such Fiscal Year. No payment on the HoldCo Notes is made by the Borrower.
"Incremental Cap" means the sum of (a) the greater of $150,000,000 and 100% of Consolidated EBITDA for the most recently ended Test Period, plus (b) the amount of all voluntary prepayments of Term Loans, plus (c) an unlimited amount so long as the First Lien Net Leverage Ratio does not exceed 0.25x less than the ratio on the Closing Date.
"Material Adverse Effect" means a material adverse effect on the business, assets or financial condition of the Borrower and its Subsidiaries, taken as a whole.
"Minimum Liquidity Amount" means the amount set forth opposite "Minimum Liquidity Amount" in Schedule 1.
"Net Proceeds" means the cash proceeds of any Asset Sale or incurrence of Indebtedness, net of fees, taxes and repayments of Indebtedness secured by the relevant assets.
"Netting Limit" means, as of any date, the greater of (a) the "Netting Limit - Fixed Amount" and (b) the "Netting Limit - Percentage" multiplied by Consolidated EBITDA for the Test Period ending on such date.
"Permitted Holders" means the Sponsor and its Affiliates (other than portfolio companies).
"Pro Forma Cost Savings" means, for any Fiscal Year, the amount set forth for such Fiscal Year opposite "Pro Forma Cost Savings" in Schedule 1.
"Restricted Payment" means any dividend or other distribution on, or any purchase or redemption of, any equity interest of Holdings or the Borrower.
"Revolving Commitments" means the amount set forth opposite "Revolving Commitments" in Schedule 1.
"Senior Notes" means the senior unsecured notes of the Borrower in a principal amount equal to the amount set forth opposite "Senior Notes" in Schedule 1, bearing cash interest at the "Senior Notes Coupon" on the principal amount outstanding on the first day of each Fiscal Year and maturing after the last Fiscal Year shown in the Model. The Senior Notes are unsecured and are not included in Consolidated First Lien Net Debt.
"Term SOFR" means, for any Fiscal Year, the rate set forth for such Fiscal Year opposite "Term SOFR" in Schedule 1.
"Test Period" means, as of any date, the Fiscal Year ending on such date.
"Total Net Leverage Ratio" means, as of any date, the ratio of Consolidated Total Net Debt as of such date to Consolidated EBITDA for the Test Period ending on such date.
"Unrestricted Cash" means, as of any date, the cash of the Borrower and its Subsidiaries on such date, subject to Section 5.02(d).

Section 1.02 Terms Generally. The words "include", "includes" and "including" shall be deemed to be followed by "without limitation". References to Sections, Annexes and Schedules are to those of this Agreement. Any financial ratio is calculated without rounding.

Section 1.03 Accounting Terms; Timing of Calculations. (a) All amounts are determined for the Borrower and its Subsidiaries on a consolidated basis in accordance with Annex B. (b) Balances, ratios and the Netting Limit are determined as of the last day of a Fiscal Year after giving effect to all payments, borrowings and repayments made on such day (subject to Section 5.02(d)). (c) A payment required to be made within a period after the end of a Fiscal Year or after the delivery of financial statements for a Fiscal Year is made in the immediately following Fiscal Year, before the installment due on the last Business Day of that Fiscal Year. (d) Financial statements for each Fiscal Year are delivered during the immediately following Fiscal Year; a rate determined by reference to the most recently ended Fiscal Year for which financial statements have been delivered applies for the whole of the Fiscal Year in which they are delivered.

ARTICLE II
THE CREDITS

Section 2.01 The Loans. (a) On the Closing Date each Term Lender made its share of Term Loans in an aggregate principal amount equal to the "Closing Date Term Loans". (b) Each Revolving Lender agrees to make Revolving Loans to the Borrower from time to time in an aggregate principal amount not exceeding the Revolving Commitments. No Revolving Loans are outstanding on the Closing Date, on which the Borrower holds Unrestricted Cash equal to the Minimum Liquidity Amount.

Section 2.02 Revolving Borrowings and Repayments. On the last day of each Fiscal Year, after all other payments to be made on such day (other than the receipt of any Cure Amount) (a) if Unrestricted Cash would otherwise be less than the Minimum Liquidity Amount, the Borrower shall borrow Revolving Loans in the amount of the shortfall, but not in excess of the unused Revolving Commitments, and (b) if Unrestricted Cash exceeds the Minimum Liquidity Amount, the Borrower shall apply the excess to repay outstanding Revolving Loans until repaid in full.

Section 2.03 Repayment of Loans. (a) The Borrower shall repay Term Loans on the last Business Day of each Fiscal Year ending after the Closing Date in an aggregate principal amount equal to the "Installment Percentage" multiplied by the aggregate principal amount of Term Loans made on the Closing Date (as such installments may be reduced as a result of the application of prepayments in accordance with Section 2.05); provided that no installment shall exceed the principal amount of Term Loans then outstanding. (b) All Loans shall be repaid on the Maturity Date, which falls after the last Fiscal Year shown in the Model.

Section 2.04 Prepayments. (a) Optional. The Borrower may prepay Loans at any time without premium, except that any prepayment of Term Loans in connection with a Repricing Transaction within six months after the Closing Date is subject to a 1% premium. (b) Asset Sales. Within ten Business Days after receipt of Net Proceeds of any Asset Sale in excess of $10,000,000 in any Fiscal Year, the Borrower shall prepay Term Loans in an amount equal to 100% of such Net Proceeds (reduced to 50% if the First Lien Net Leverage Ratio is not greater than 0.50x below the ratio on the Closing Date), subject to reinvestment rights for 365 days. (c) Debt Incurrence. Within one Business Day after the incurrence of any Indebtedness not permitted by Section 4.01, the Borrower shall prepay Term Loans in an amount equal to 100% of the Net Proceeds. (d) Excess Cash Flow. Within five Business Days after financial statements are delivered pursuant to Section 3.01(a) for any Excess Cash Flow Period, the Borrower shall prepay Term Loans in an aggregate principal amount equal to the Applicable ECF Percentage for such Excess Cash Flow Period multiplied by Excess Cash Flow for such Excess Cash Flow Period, if positive; provided that no such prepayment shall exceed the principal amount of Term Loans then outstanding. (e) Declined Proceeds. Any Term Lender may elect to decline its share of any mandatory prepayment (such declined amounts, "Declined Proceeds"), which may be retained by the Borrower.

Section 2.05 Application of Prepayments. Each prepayment pursuant to Section 2.04(d) shall be applied to reduce the subsequent installments of Term Loans under Section 2.03(a) in direct order of maturity (the installment next due first), until the full amount of such prepayment has been applied; any portion not yet applied is carried forward and applied to each following installment in turn. A prepayment made in a Fiscal Year is applied first to the installment due on the last Business Day of that Fiscal Year.

Section 2.06 Fees. (a) The Borrower shall pay to the Administrative Agent for the account of each Revolving Lender a commitment fee for each Fiscal Year (the "Commitment Fee") at the Applicable Commitment Fee Rate on the amount by which the Revolving Commitments exceed the Revolving Loans outstanding on the first day of such Fiscal Year. (b) The Borrower shall pay the agency fees separately agreed in the Fee Letter.

Section 2.07 Interest. (a) The Term Loans and Revolving Loans bear interest for each Fiscal Year at a rate per annum equal to Adjusted Term SOFR for such Fiscal Year plus the Applicable Rate, on the principal amount outstanding on the first day of such Fiscal Year, payable in cash on the last day of such Fiscal Year. (b) Upon the occurrence and during the continuance of an Event of Default, at the election of the Required Lenders, overdue amounts bear interest at 2% per annum above the otherwise applicable rate.

Section 2.08 Taxes. All payments by the Borrower shall be made free and clear of withholding taxes, subject to customary gross-up and exclusions for Excluded Taxes.

ARTICLE III
AFFIRMATIVE COVENANTS

Section 3.01 Financial Statements. The Borrower shall deliver to the Administrative Agent: (a) within 120 days after the end of each Fiscal Year, audited consolidated financial statements for such Fiscal Year; (b) within 45 days after the end of each of the first three fiscal quarters, unaudited quarterly financial statements; and (c) with each delivery under clause (a), a compliance certificate setting forth the calculation of the First Lien Net Leverage Ratio and the Total Net Leverage Ratio.

ARTICLE IV
NEGATIVE COVENANTS

Section 4.01 Indebtedness. The Borrower shall not incur Indebtedness other than (a) the Loans, (b) the Senior Notes, (c) Incremental Facilities in an aggregate amount not exceeding the Incremental Cap and (d) other Indebtedness in an aggregate amount not exceeding the greater of $50,000,000 and 50% of Consolidated EBITDA for the most recently ended Test Period.

Section 4.02 Restricted Payments. The Borrower shall not make any Restricted Payment, except (a) Restricted Payments in an aggregate amount not exceeding the sum of 50% of cumulative Excess Cash Flow not required to be applied under Section 2.04(d) (the "Available Amount"), so long as the Total Net Leverage Ratio would not exceed 4.00x on a pro forma basis, and (b) payments to Holdings to pay its franchise taxes and overhead not exceeding $5,000,000 in any Fiscal Year.

Section 4.03 Financial Covenant. Commencing with the first full Fiscal Year ending after the Closing Date, the Borrower shall not permit the Total Net Leverage Ratio as of the last day of any Fiscal Year to exceed the ratio set forth for such Fiscal Year opposite "Maximum Total Net Leverage Ratio" in Schedule 1.

ARTICLE V
EVENTS OF DEFAULT

Section 5.01 Events of Default. Each of the following is an Event of Default: (a) failure to pay principal when due, or interest within five Business Days after it is due; (b) any representation proving materially incorrect when made; (c) failure to observe any covenant (including Section 4.03, subject to Section 5.02); (d) cross-default to Indebtedness in excess of $40,000,000; (e) insolvency events; (f) judgments in excess of $40,000,000 unsatisfied for 60 days; and (g) a Change of Control.

Section 5.02 Right to Cure. (a) If the Borrower fails to comply with Section 4.03 as of the last day of any Fiscal Year, the Sponsor may make a cash equity contribution to the Borrower (the amount so contributed, a "Cure Amount"), which shall be added to Consolidated EBITDA for such Fiscal Year solely for the purpose of determining compliance with Section 4.03 as of the last day of such Fiscal Year. (b) The Cure Amount shall be equal to the minimum amount that, if so added, would cause the Total Net Leverage Ratio to equal the maximum ratio permitted for such Fiscal Year; the Sponsor contributes exactly that amount whenever a Cure Amount is permitted. (c) There is no limit on the number of Cure Amounts. (d) No Cure Amount shall reduce Indebtedness (by netting or otherwise) or be included in Unrestricted Cash for the purpose of determining any financial ratio, the Netting Limit, the Applicable Rate, the Applicable Commitment Fee Rate, the Applicable ECF Percentage or the Springing Test Condition as of the last day of the Fiscal Year in respect of which it is made, and no Cure Amount increases Consolidated EBITDA for any purpose other than Section 4.03. The Cure Amount is received in cash on the last day of such Fiscal Year after all other payments, borrowings and repayments on such day, is not applied to repay any Loan, and forms part of Unrestricted Cash thereafter.

ARTICLE VI
THE ADMINISTRATIVE AGENT

Section 6.01 Appointment and Authority. Each Lender irrevocably appoints the Administrative Agent to act on its behalf under this Agreement and authorizes it to take such actions and exercise such powers as are delegated to it hereunder.

ARTICLE VII
MISCELLANEOUS

Section 7.01 Governing Law. This Agreement shall be governed by, and construed in accordance with, the law of the State of New York.

ANNEX A - SPONSOR RETURNS METHODOLOGY
ANNEX A is the Sponsor's returns methodology (it is not an obligation of the Borrower). (1) Enterprise Value at closing = the "Entry Multiple" multiplied by EBITDA for the Fiscal Year ended on the Closing Date. (2) Total Uses = Enterprise Value at closing plus Transaction Costs (the "Transaction Costs (% of Enterprise Value)" multiplied by Enterprise Value at closing) plus the Minimum Liquidity Amount funded to the balance sheet. (3) Sponsor Equity = Total Uses minus the Term Loans, the Senior Notes and the HoldCo Notes, each as of the Closing Date. (4) Exit Enterprise Value = the "Exit Multiple" multiplied by EBITDA (not Consolidated EBITDA) for the last Fiscal Year shown in the Model. (5) Exit Equity Value = Exit Enterprise Value minus the Term Loans, Revolving Loans, Senior Notes and HoldCo Notes outstanding at the end of that Fiscal Year plus all Unrestricted Cash at that date (without regard to the Netting Limit). (6) Sponsor MOIC = Exit Equity Value divided by the sum of Sponsor Equity and all Cure Amounts.

ANNEX B - MODEL CONVENTIONS
ANNEX B is the Model convention. (1) Each column of the Model after the first is a Fiscal Year; the first column shows balances as of the Closing Date. (2) Revenue for a Fiscal Year = revenue for the prior Fiscal Year multiplied by (1 + "Revenue growth" for the year); EBITDA = revenue multiplied by "EBITDA margin" for the year. D&A, Capital Expenditures and Consolidated Working Capital are revenue multiplied by "D&A (% of revenue)", "Capital Expenditures (% of revenue)" and "Consolidated Working Capital (% of revenue)" respectively; the increase in Consolidated Working Capital for a Fiscal Year is the amount at its end minus the amount at the end of the prior Fiscal Year. (3) Taxes paid in cash for a Fiscal Year = the "Tax Rate" multiplied by (EBITDA - D&A - Consolidated Cash Interest Expense), or zero if that amount is negative; interest on the HoldCo Notes is not deductible by the Borrower. (4) Unrestricted Cash at the end of a Fiscal Year = Unrestricted Cash at the end of the prior Fiscal Year + EBITDA - Consolidated Cash Interest Expense - taxes paid in cash - Capital Expenditures - the increase in Consolidated Working Capital - prepayments and installments of Term Loans paid in the year + net Revolving Loans borrowed (minus net repayments) under Section 2.02 + any Cure Amount; it may be negative. (5) The Model reflects no Asset Sales, incurrence of Indebtedness (other than Revolving Loans), Incremental Facilities, optional prepayments, Repricing Transactions, Declined Proceeds, Restricted Payments, payments under the Fee Letter, default interest or other Event of Default consequences, and provisions concerning them have no effect on the Model.

SCHEDULE 1 - ASSUMPTIONS
Schedule 1 is the Assumptions sheet of the Model. Each caption in quotation marks in this Agreement refers to the value set forth opposite that caption (per-year values: in the column of the relevant Fiscal Year).


CONVENTIONS:
- The Agreement above governs. Implement every provision that affects the rows of the Model exactly as drafted; provisions about events that do not occur in the Model (see Annex B) have no effect.
- Amounts in $ millions; percentages and ratios as decimals (5% = 0.05, 4.25x = 4.25).

RULES:
- Every formula must be live and linked to the inputs: the model will be re-calculated with different input values, so typed numbers will be wrong.
- Do not change inputs (the Assumptions sheet and any given values), labels or headers.
- Allowed functions: SUM, AVERAGE, MIN, MAX, COUNT, IF, IFERROR, AND, OR, NOT, ABS, ROUND, ROUNDUP, ROUNDDOWN, INT, MOD, POWER, SQRT, LN, EXP, SIGN, SUMPRODUCT, NPV, PMT, IRR, INDEX, MATCH, CHOOSE.
- You may use empty cells for helper calculations.

Assumptions sheet: C4 Closing Date Term Loans; C5 Term SOFR Floor; C6 Applicable Margin - Pricing Level III; C7 Applicable Margin - Pricing Level II; C8 Applicable Margin - Pricing Level I; C9 Pricing Level II Threshold; C10 Pricing Level I Threshold; C11 Installment Percentage; C12 ECF Percentage - Level 2; C13 ECF Percentage - Level 1; C14 ECF Level 2 Ratio; C15 ECF Level 1 Ratio; C16 Tax Rate; C17 D&A (% of revenue); C18 Capital Expenditures (% of revenue); C19 Consolidated Working Capital (% of revenue); C20 Minimum Liquidity Amount; C21 Revolving Commitments; C22 Commitment Fee Rate - Lower; C23 Commitment Fee Rate - Higher; C24 Commitment Fee Step-Down Ratio; C25 Senior Notes; C26 Senior Notes Coupon; C27 Cost Savings Cap; C28 Netting Limit - Fixed Amount; C29 Netting Limit - Percentage; C30 HoldCo Notes; C31 HoldCo PIK Rate; C32 Entry Multiple; C33 Transaction Costs (% of Enterprise Value); C34 Exit Multiple; row 36 Term SOFR (D:J); row 37 Revenue growth (D:J); row 38 EBITDA margin (D:J); row 39 Pro Forma Cost Savings (D:J); row 40 Maximum Total Net Leverage Ratio (D:J)

Use the tools to inspect and edit the workbook. Call submit when you are done.
````

## Reference formulas (first projection column and single-cell results)

| Cell | Label | Formula |
|---|---|---|
| Model!D5 | Model!D5 (Revenue FY2027) | `=C5*(1+Assumptions!D37)` |
| Model!D6 | Model!D6 (EBITDA FY2027) | `=D5*Assumptions!D38` |
| Model!D7 | Model!D7 (D&A FY2027) | `=D5*Assumptions!$C$17` |
| Model!D8 | Model!D8 (Capital Expenditures FY2027) | `=D5*Assumptions!$C$18` |
| Model!D9 | Model!D9 (Consolidated Working Capital FY2027) | `=D5*Assumptions!$C$19` |
| Model!D10 | Model!D10 (Increase in Consolidated Working Capital FY2027) | `=D9-C9` |
| Model!D11 | Model!D11 (Pro Forma Cost Savings added back FY2027) | `=MIN(Assumptions!D39,Assumptions!$C$27*D6)` |
| Model!D12 | Model!D12 (Consolidated EBITDA FY2027) | `=D6+D11` |
| Model!D15 | Model!D15 (Adjusted Term SOFR FY2027) | `=MAX(Assumptions!D36,Assumptions!$C$5)` |
| Model!D16 | Model!D16 (Applicable Rate FY2027) | `=Assumptions!$C$8` |
| Model!D17 | Model!D17 (Applicable Commitment Fee Rate FY2027) | `=Assumptions!$C$23` |
| Model!D20 | Model!D20 (Interest on Term Loans FY2027) | `=C32*(D15+D16)` |
| Model!D21 | Model!D21 (Interest on Revolving Loans FY2027) | `=C40*(D15+D16)` |
| Model!D22 | Model!D22 (Commitment Fee FY2027) | `=(Assumptions!$C$21-C40)*D17` |
| Model!D23 | Model!D23 (Interest on Senior Notes FY2027) | `=C42*Assumptions!$C$26` |
| Model!D24 | Model!D24 (Consolidated Cash Interest Expense FY2027) | `=D20+D21+D22+D23` |
| Model!D25 | Model!D25 (Taxes paid in cash FY2027) | `=MAX(0,D6-D7-D24)*Assumptions!$C$16` |
| Model!D28 | Model!D28 (Excess Cash Flow prepayment FY2027) | `=MIN(C32,MAX(0,C35)*C36)` |
| Model!D29 | Model!D29 (Prepayment credit applied to the installment FY2027) | `=MIN(C31+D28,Assumptions!$C$11*$C$32)` |
| Model!D30 | Model!D30 (Scheduled installment paid FY2027) | `=MIN(C32-D28,Assumptions!$C$11*$C$32-D29)` |
| Model!D31 | Model!D31 (Unapplied prepayment credit - closing FY2027) | `=C31+D28-D29` |
| Model!D32 | Model!D32 (Term Loans - closing balance FY2027) | `=C32-D28-D30` |
| Model!D35 | Model!D35 (Excess Cash Flow FY2027) | `=D6-D24-D25-D8-D10-D30` |
| Model!D36 | Model!D36 (Applicable ECF Percentage FY2027) | `=IF(D50>Assumptions!$C$15,Assumptions!$C$13,IF(D50>Assumptions!$C$14,Assumptions!$C$12,0))` |
| Model!D39 | Model!D39 (Cash before Revolving Loans FY2027) | `=C55+D6-D24-D25-D8-D10-D28-D30` |
| Model!D40 | Model!D40 (Revolving Loans - closing balance FY2027) | `=MIN(Assumptions!$C$21,MAX(0,C40-(D39-Assumptions!$C$20)))` |
| Model!D41 | Model!D41 (Revolving Loans - borrowing/(repayment) FY2027) | `=D40-C40` |
| Model!D42 | Model!D42 (Senior Notes - closing balance FY2027) | `=C42` |
| Model!D45 | Model!D45 (HoldCo Notes - PIK interest FY2027) | `=C46*Assumptions!$C$31` |
| Model!D46 | Model!D46 (HoldCo Notes - closing balance FY2027) | `=C46+D45` |
| Model!D49 | Model!D49 (Unrestricted Cash deducted (after the Netting Limit) FY2027) | `=MIN((D39+D41),MAX(Assumptions!$C$28,Assumptions!$C$29*D12))` |
| Model!D50 | Model!D50 (First Lien Net Leverage Ratio FY2027) | `=(D32+D40-D49)/D12` |
| Model!D51 | Model!D51 (Total Net Leverage Ratio (before any Cure Amount) FY2027) | `=(D32+D40+D42-D49)/D12` |
| Model!D54 | Model!D54 (Cure Amount FY2027) | `=MAX(0,(D32+D40+D42-D49)/Assumptions!D40-D12)` |
| Model!D55 | Model!D55 (Unrestricted Cash - closing FY2027) | `=D39+D41+D54` |
| Model!C58 | Model!C58 (Enterprise Value at closing) | `=$C$6*Assumptions!$C$32` |
| Model!C59 | Model!C59 (Total Uses) | `=$C$58*(1+Assumptions!$C$33)+Assumptions!$C$20` |
| Model!C60 | Model!C60 (Sponsor Equity) | `=$C$59-$C$32-$C$42-$C$46` |
| Model!C61 | Model!C61 (Exit Enterprise Value) | `=$J$6*Assumptions!$C$34` |
| Model!C62 | Model!C62 (Exit Equity Value) | `=$C$61-$J$32-$J$40-$J$42-$J$46+$J$55` |
| Model!C63 | Model!C63 (Total Sponsor Equity invested) | `=$C$60+SUM($D$54:$J$54)` |
| Model!C64 | Model!C64 (Sponsor MOIC) | `=$C$62/$C$63` |
