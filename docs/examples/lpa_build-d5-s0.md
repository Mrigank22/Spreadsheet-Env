# lpa_build-d5-s0

**Limited partnership agreement (document spec): fund waterfall with fee offsets, GP commitment, clawback and carry escrow.** Family `lpa_build`, level 5, training seed 0; 309 graded cells, 11 perturbation scenarios.

## What the agent sees

````text
You are building a fund distribution model under a limited partnership agreement (Pellham Capital Partners) in a spreadsheet (sheets: Assumptions, Model; amounts in $m). Column C holds the starting point, columns D:O the projection (FY1, FY2, FY3, FY4, FY5, FY6, FY7, FY8, FY9, FY10, FY11, FY12).

TASK: the cells below are empty. Write a formula in every one so that the model implements the TERMS below exactly. Work out each row's logic from the terms and the row labels.
- Model!D5:O5 "Fiscal Year number"
- Model!D6:O6 "Management Fee before offsets"
- Model!D7:O7 "Offset arising from Transaction Fees"
- Model!D8:O8 "Offset applied"
- Model!D9:O9 "Unapplied offset carried forward - closing"
- Model!D10:O10 "Management Fee"
- Model!D13:O13 "Limited Partners' Capital Contributions"
- Model!D14:O14 "General Partner's Capital Contributions"
- Model!D15:O15 "Distributions to the General Partner in respect of its Commitment"
- Model!D16:O16 "Distributable Proceeds apportioned to the Limited Partners"
- Model!D19:O19 "Distributions under clause (a) (return of capital)"
- Model!D20:O20 "Unreturned Capital Contributions - closing"
- Model!D21:O21 "Preferred Return accrued"
- Model!D22:O22 "Distributions under clause (b) (Preferred Return)"
- Model!D23:O23 "Unpaid Preferred Return - closing"
- Model!D24:O24 "Cumulative distributions under clause (b)"
- Model!D25:O25 "Distributions under clause (c) (catch-up), total"
- Model!D26:O26 "Cumulative distributions under clause (c)"
- Model!D27:O27 "Distributions under clause (d) (residual)"
- Model!D28:O28 "Carried Interest distributed"
- Model!D29:O29 "Distributions to the Limited Partners"
- Model!D32:O32 "Carried Interest deposited in the Escrow Account"
- Model!D33:O33 "Carried Interest paid to the General Partner"
- Model!D34:O34 "Escrow Account - closing"
- Model!D37:O37 "LP net cash flow"
- Model!C40 "Total Limited Partner Capital Contributions"
- Model!C41 "Total Distributable Proceeds apportioned to the Limited Partners"
- Model!C42 "Total Carried Interest distributed"
- Model!C43 "Net Profits of the Limited Partners"
- Model!C44 "Clawback Amount"
- Model!C45 "Clawback Amount paid from the Escrow Account"
- Model!C46 "Clawback Amount paid by the General Partner"
- Model!C47 "Escrow Account released to the General Partner"
- Model!C48 "LP net IRR"

TERMS:
AMENDED AND RESTATED AGREEMENT OF LIMITED PARTNERSHIP OF PELLHAM CAPITAL PARTNERS, L.P.

AMENDED AND RESTATED AGREEMENT OF LIMITED PARTNERSHIP of Pellham Capital Partners, L.P. (the "Partnership") among Pellham Capital Partners GP, LLC, as general partner (the "General Partner"), and the limited partners party hereto (the "Limited Partners" and, together with the General Partner, the "Partners"). Amounts, rates and periods referred to by a caption in quotation marks are set forth in Schedule 1 (the Assumptions sheet of the Model).

ARTICLE I
DEFINITIONS AND ACCOUNTING TERMS

Section 1.01 Defined Terms. As used in this Agreement, the following terms have the meanings specified below:
"Affiliate" means, with respect to any Person, any other Person controlling, controlled by or under common control with such Person.
"Assumed Tax Rate" means the rate set forth opposite "Assumed Tax Rate" in Schedule 1.
"Capital Contributions" means the amounts contributed to the Partnership by a Partner pursuant to Section 2.01, including amounts contributed to fund Management Fees.
"Carried Interest" means all amounts distributed to the General Partner pursuant to clauses (c) and (d) of Section 4.02, other than amounts distributed to the Limited Partners under those clauses.
"Carried Interest Percentage" means the percentage set forth opposite "Carried Interest Percentage" in Schedule 1.
"Catch-Up Percentage" means the percentage set forth opposite "Catch-Up Percentage" in Schedule 1.
"Clawback Amount" has the meaning assigned to such term in Section 4.05.
"Commitment" means, for all Partners together, the amount set forth opposite "Commitments" in Schedule 1, of which the General Partner's Commitment is the "GP Commitment Percentage" and the remainder is the Commitment of the Limited Partners.
"Commitment Period" means the period from the initial closing through the end of the Fiscal Year whose number equals the "Commitment Period (Fiscal Years)" (the first Fiscal Year being number 1), subject to Section 5.01.
"Defaulting Partner" has the meaning assigned to such term in Section 2.02.
"Distributable Proceeds" means, for any Fiscal Year, the amount set forth for such Fiscal Year opposite "Distributable Proceeds" in Schedule 1, being the net cash proceeds of Portfolio Investments available for distribution on the last day of such Fiscal Year.
"Escrow Account" has the meaning assigned to such term in Section 4.06.
"Fiscal Year" means each calendar year of the Partnership; each column of the Model after the first is one Fiscal Year, numbered from 1.
"GP Commitment Percentage" means the percentage set forth opposite "GP Commitment Percentage" in Schedule 1.
"Invested Capital" means, for any Fiscal Year, the amount set forth for such Fiscal Year opposite "Invested Capital" in Schedule 1 (the cost of Portfolio Investments held by the Partnership on the first day of such Fiscal Year, for all Partners together).
"Key Person Event" means that both of the Key Persons cease to devote substantially all of their business time to the Partnership.
"Management Fee" has the meaning assigned to such term in Section 3.01.
"Net Profits" means, upon the dissolution of the Partnership, the aggregate Distributable Proceeds apportioned to the Limited Partners over the life of the Partnership minus the aggregate Capital Contributions of the Limited Partners, if positive (and zero otherwise).
"Offset Percentage" means the percentage set forth opposite "Offset Percentage" in Schedule 1.
"Organizational Expenses" means the legal, accounting and filing expenses incurred in connection with the organization of the Partnership, not to exceed $2,500,000 in the aggregate.
"Portfolio Investment" means any investment made by the Partnership in a portfolio company.
"Preferred Return" means, as of any date, an amount equal to a return at the "Preferred Return Rate" per annum, compounded annually, on the Capital Contributions of the Limited Partners from the date contributed until the date returned pursuant to clause (a) of Section 4.02, in each case computed on the sum of (i) such Capital Contributions not yet so returned and (ii) Preferred Return accrued in prior Fiscal Years and not yet distributed pursuant to clause (b) of Section 4.02.
"Successor Fund" means any pooled investment vehicle with substantially the same investment objective as the Partnership, sponsored by the General Partner or its Affiliates.
"Transaction Fees" means, for any Fiscal Year, the amount set forth for such Fiscal Year opposite "Transaction Fees" in Schedule 1, being transaction, monitoring and directors' fees received by the Manager or its Affiliates from portfolio companies during such Fiscal Year.

ARTICLE II
CAPITAL CONTRIBUTIONS

Section 2.01 Capital Contributions. Each Partner shall contribute capital on the first day of each Fiscal Year in which capital is called. Capital called for Portfolio Investments (the amount set forth opposite "Capital called for Portfolio Investments" in Schedule 1, for all Partners together) is contributed by the Partners pro rata to their Commitments. In addition, the Management Fee for each Fiscal Year is funded by Capital Contributions made on the first day of such Fiscal Year by the Limited Partners only.

Section 2.02 Defaulting Partners. If any Limited Partner fails to make a Capital Contribution when due and does not cure such failure within ten Business Days (a "Defaulting Partner"), the General Partner may cause such Defaulting Partner to forfeit 50% of its capital account and to lose its right to make further contributions.

ARTICLE III
MANAGEMENT FEE

Section 3.01 Management Fee. (a) The Partnership shall pay to the Manager for each Fiscal Year a management fee (the "Management Fee") equal to (i) during the Commitment Period, the "Management Fee Rate - Commitment Period" multiplied by the Commitment of the Limited Partners, and (ii) thereafter, the "Management Fee Rate - Post-Commitment Period" multiplied by the Limited Partners' share (in proportion to their Commitments) of Invested Capital for such Fiscal Year. (b) The General Partner's Commitment does not bear any Management Fee.

Section 3.02 Management Fee Offset. The Management Fee for any Fiscal Year shall be reduced (but not below zero) by the Offset Percentage multiplied by the Transaction Fees received during such Fiscal Year. Any portion of such reduction that cannot be applied because the Management Fee would be reduced below zero shall be carried forward and applied to reduce the Management Fee for each following Fiscal Year in turn until fully applied. For purposes of this Agreement the Management Fee means the Management Fee after such reductions.

Section 3.03 Organizational Expenses. The Partnership shall bear Organizational Expenses up to the limit set forth in the definition thereof; any excess shall be borne by the Manager.

ARTICLE IV
DISTRIBUTIONS

Section 4.01 Apportionment. Distributable Proceeds for each Fiscal Year shall first be apportioned among the Partners in proportion to their Capital Contributions for Portfolio Investments, that is, the GP Commitment Percentage to the General Partner and the remainder to the Limited Partners. Amounts apportioned to the General Partner are distributed to it as a Partner in respect of its Commitment and are not Carried Interest. Amounts apportioned to the Limited Partners are distributed in accordance with Section 4.02.

Section 4.02 Distribution Waterfall. Distributable Proceeds apportioned to the Limited Partners for each Fiscal Year shall be distributed on the last day of such Fiscal Year in the following order of priority: (a) Return of Capital: 100% to the Limited Partners until they have received cumulative distributions under this clause (a) equal to their aggregate Capital Contributions made on or before such date; (b) Preferred Return: 100% to the Limited Partners until they have received cumulative distributions under this clause (b) equal to the Preferred Return; (c) Catch-Up: the Catch-Up Percentage to the General Partner and the remainder to the Limited Partners, until the General Partner has received pursuant to this clause (c) an amount equal to the Carried Interest Percentage of the sum of all amounts distributed pursuant to clause (b) and this clause (c) (to all recipients) since the initial closing; and (d) thereafter, the Carried Interest Percentage to the General Partner and the remainder to the Limited Partners.

Section 4.03 Tax Distributions. The General Partner may cause the Partnership to make distributions to the General Partner to enable it to pay taxes on allocations of Partnership income, which distributions shall be treated as advances against subsequent distributions of Carried Interest.

Section 4.04 Distributions in Kind. Distributions prior to the dissolution of the Partnership shall be made only in cash or marketable securities, valued at the average closing price over the five trading days preceding distribution.

Section 4.05 General Partner Clawback. Upon the dissolution of the Partnership (the end of the last Fiscal Year shown in the Model), if the aggregate Carried Interest distributed (including amounts deposited in the Escrow Account) exceeds the Carried Interest Percentage multiplied by Net Profits, the General Partner shall restore the excess to the Limited Partners (the "Clawback Amount"); provided that the Clawback Amount shall not exceed the aggregate Carried Interest distributed reduced by the Assumed Tax Rate (that is, multiplied by one minus the Assumed Tax Rate). The Clawback Amount shall be satisfied first from the Escrow Account in accordance with Section 4.06.

Section 4.06 Carry Escrow. (a) The Escrow Percentage (as set forth opposite "Escrow Percentage" in Schedule 1) of each distribution of Carried Interest shall be deposited into a segregated account (the "Escrow Account") instead of being paid to the General Partner; the remainder is paid to the General Partner. The Escrow Account bears no interest and makes no payment before dissolution. (b) Upon dissolution, the Escrow Account shall be applied first to pay the Clawback Amount (up to its balance); the General Partner shall pay any remaining Clawback Amount; and any balance remaining in the Escrow Account shall be released to the General Partner.

ARTICLE V
GOVERNANCE

Section 5.01 Key Person Event. Upon the occurrence of a Key Person Event, the Commitment Period shall be suspended automatically unless Limited Partners holding a majority of Commitments elect to continue it.

Section 5.02 Successor Funds. The General Partner shall not close a Successor Fund until the earlier of the end of the Commitment Period and the date on which 75% of Commitments have been invested or reserved.

ARTICLE VI
DISSOLUTION

Section 6.01 Term. The Partnership shall dissolve at the end of the last Fiscal Year shown in the Model, subject to two one-year extensions at the discretion of the General Partner.

ANNEX A - MODEL CONVENTIONS
ANNEX A is the Model convention. (1) The first column of the Model is the initial closing (no balances); each later column is a Fiscal Year. (2) Capital Contributions are made on the first day of a Fiscal Year and distributions on its last day, so Capital Contributions made in a Fiscal Year are taken into account in that Fiscal Year's distributions and earn the Preferred Return for that whole Fiscal Year. (3) Amounts are for all Limited Partners together (and the General Partner where stated). (4) LP net cash flow for a Fiscal Year = distributions to the Limited Partners minus Capital Contributions of the Limited Partners plus, in the last Fiscal Year, the Clawback Amount; the LP net IRR is the internal rate of return of the annual LP net cash flows (one per Fiscal Year, the initial closing column excluded). (5) No Key Person Event, default by any Partner, tax distribution, distribution in kind, Organizational Expense in excess of the limit, extension of the term or Successor Fund occurs in the Model; provisions concerning them have no effect on the Model.

SCHEDULE 1 - ASSUMPTIONS
Schedule 1 is the Assumptions sheet of the Model. Each caption in quotation marks refers to the value set forth opposite that caption (per-year values: in the column of the relevant Fiscal Year).


CONVENTIONS:
- The Agreement above governs. Implement every provision that affects the rows of the Model exactly as drafted; provisions about events that do not occur in the Model (see Annex A) have no effect.
- Amounts in $ millions; percentages as decimals (8% = 0.08).

RULES:
- Every formula must be live and linked to the inputs: the model will be re-calculated with different input values, so typed numbers will be wrong.
- Do not change inputs (the Assumptions sheet and any given values), labels or headers.
- Allowed functions: SUM, AVERAGE, MIN, MAX, COUNT, IF, IFERROR, AND, OR, NOT, ABS, ROUND, ROUNDUP, ROUNDDOWN, INT, MOD, POWER, SQRT, LN, EXP, SIGN, SUMPRODUCT, NPV, PMT, IRR, INDEX, MATCH, CHOOSE.
- You may use empty cells for helper calculations.

Assumptions sheet: C4 Preferred Return Rate; C5 Carried Interest Percentage; C6 Catch-Up Percentage; C7 Commitments; C8 Commitment Period (Fiscal Years); C9 Management Fee Rate - Post-Commitment Period; C10 Management Fee Rate - Commitment Period; C11 GP Commitment Percentage; C12 Offset Percentage; C13 Assumed Tax Rate; C14 Escrow Percentage; row 16 Capital called for Portfolio Investments (D:O); row 17 Distributable Proceeds (D:O); row 18 Invested Capital (D:O); row 19 Transaction Fees (D:O)

Use the tools to inspect and edit the workbook. Call submit when you are done.
````

## Reference formulas (first projection column and single-cell results)

| Cell | Label | Formula |
|---|---|---|
| Model!D5 | Model!D5 (Fiscal Year number FY1) | `=C5+1` |
| Model!D6 | Model!D6 (Management Fee before offsets FY1) | `=IF(D5<=Assumptions!$C$8,Assumptions!$C$10*Assumptions!$C$7*(1-Assumptions!$C$11),Assumptions!$C$9*Assumptions!D18*(1-Assumptions!$C$11))` |
| Model!D7 | Model!D7 (Offset arising from Transaction Fees FY1) | `=Assumptions!$C$12*Assumptions!D19` |
| Model!D8 | Model!D8 (Offset applied FY1) | `=MIN(D6,C9+D7)` |
| Model!D9 | Model!D9 (Unapplied offset carried forward - closing FY1) | `=C9+D7-D8` |
| Model!D10 | Model!D10 (Management Fee FY1) | `=D6-D8` |
| Model!D13 | Model!D13 (Limited Partners' Capital Contributions FY1) | `=Assumptions!D16*(1-Assumptions!$C$11)+D10` |
| Model!D14 | Model!D14 (General Partner's Capital Contributions FY1) | `=Assumptions!D16*Assumptions!$C$11` |
| Model!D15 | Model!D15 (Distributions to the General Partner in respect of its Commitment FY1) | `=Assumptions!D17*Assumptions!$C$11` |
| Model!D16 | Model!D16 (Distributable Proceeds apportioned to the Limited Partners FY1) | `=Assumptions!D17-D15` |
| Model!D19 | Model!D19 (Distributions under clause (a) (return of capital) FY1) | `=MIN(D16,C20+D13)` |
| Model!D20 | Model!D20 (Unreturned Capital Contributions - closing FY1) | `=C20+D13-D19` |
| Model!D21 | Model!D21 (Preferred Return accrued FY1) | `=Assumptions!$C$4*(C20+D13+C23)` |
| Model!D22 | Model!D22 (Distributions under clause (b) (Preferred Return) FY1) | `=MIN(D16-D19,C23+D21)` |
| Model!D23 | Model!D23 (Unpaid Preferred Return - closing FY1) | `=C23+D21-D22` |
| Model!D24 | Model!D24 (Cumulative distributions under clause (b) FY1) | `=C24+D22` |
| Model!D25 | Model!D25 (Distributions under clause (c) (catch-up), total FY1) | `=MIN(D16-D19-D22,MAX(0,Assumptions!$C$5*D24/(Assumptions!$C$6-Assumptions!$C$5)-C26))` |
| Model!D26 | Model!D26 (Cumulative distributions under clause (c) FY1) | `=C26+D25` |
| Model!D27 | Model!D27 (Distributions under clause (d) (residual) FY1) | `=D16-D19-D22-D25` |
| Model!D28 | Model!D28 (Carried Interest distributed FY1) | `=D25*Assumptions!$C$6+D27*Assumptions!$C$5` |
| Model!D29 | Model!D29 (Distributions to the Limited Partners FY1) | `=D16-D28` |
| Model!D32 | Model!D32 (Carried Interest deposited in the Escrow Account FY1) | `=D28*Assumptions!$C$14` |
| Model!D33 | Model!D33 (Carried Interest paid to the General Partner FY1) | `=D28-D32` |
| Model!D34 | Model!D34 (Escrow Account - closing FY1) | `=C34+D32` |
| Model!D37 | Model!D37 (LP net cash flow FY1) | `=D29-D13` |
| Model!C40 | Model!C40 (Total Limited Partner Capital Contributions) | `=SUM($D$13:$O$13)` |
| Model!C41 | Model!C41 (Total Distributable Proceeds apportioned to the Limited Partners) | `=SUM($D$16:$O$16)` |
| Model!C42 | Model!C42 (Total Carried Interest distributed) | `=SUM($D$28:$O$28)` |
| Model!C43 | Model!C43 (Net Profits of the Limited Partners) | `=MAX(0,$C$41-$C$40)` |
| Model!C44 | Model!C44 (Clawback Amount) | `=MIN(MAX(0,$C$42-Assumptions!$C$5*$C$43),$C$42*(1-Assumptions!$C$13))` |
| Model!C45 | Model!C45 (Clawback Amount paid from the Escrow Account) | `=MIN($C$44,$O$34)` |
| Model!C46 | Model!C46 (Clawback Amount paid by the General Partner) | `=$C$44-$C$45` |
| Model!C47 | Model!C47 (Escrow Account released to the General Partner) | `=$O$34-$C$45` |
| Model!C48 | Model!C48 (LP net IRR) | `=IRR($D$37:$O$37)` |
