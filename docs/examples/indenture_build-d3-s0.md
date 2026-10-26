# indenture_build-d3-s0

**Auto ABS indenture (document spec): priority of payments with allocations of principal, reserve account and OC target.** Family `indenture_build`, level 3, training seed 0; 1827 graded cells, 11 perturbation scenarios.

## What the agent sees

````text
You are building a auto-loan ABS cash-flow model under an indenture (Elsby Auto Receivables Trust) in a spreadsheet (sheets: Assumptions, Model; amounts in $m). Column C holds the starting point, columns D:AY the projection (P1, P2, P3, P4, P5, P6, P7, P8, P9, P10, P11, P12, P13, P14, P15, P16, P17, P18, P19, P20, P21, P22, P23, P24, P25, P26, P27, P28, P29, P30, P31, P32, P33, P34, P35, P36, P37, P38, P39, P40, P41, P42, P43, P44, P45, P46, P47, P48).

TASK: the cells below are empty. Write a formula in every one so that the model implements the TERMS below exactly. Work out each row's logic from the terms and the row labels.
- Model!D5:AY5 "Collection Period number"
- Model!D6:AY6 "Defaulted Receivables"
- Model!D7:AY7 "Interest Collections"
- Model!D8:AY8 "Scheduled Principal Collections"
- Model!D9:AY9 "Prepayments"
- Model!D10:AY10 "Pool Balance"
- Model!D11:AY11 "Recoveries"
- Model!D14:AY14 "Collections"
- Model!D15:AY15 "Target Overcollateralization Amount"
- Model!D16:AY16 "Servicing Fee"
- Model!D17:AY17 "Class A Interest Distributable Amount"
- Model!D18:AY18 "First Allocation of Principal"
- Model!D19:AY19 "Class B Interest Distributable Amount"
- Model!D20:AY20 "Second Allocation of Principal"
- Model!D21:AY21 "Class C Interest Distributable Amount"
- Model!D22:AY22 "Third Allocation of Principal"
- Model!D23:AY23 "Reserve Account Draw Amount"
- Model!D24:AY24 "Available Funds"
- Model!D27:AY27 "Servicing Fee paid"
- Model!D28:AY28 "Class A interest paid"
- Model!D29:AY29 "First Allocation of Principal paid"
- Model!D30:AY30 "Class B interest paid"
- Model!D31:AY31 "Second Allocation of Principal paid"
- Model!D32:AY32 "Class C interest paid"
- Model!D33:AY33 "Third Allocation of Principal paid"
- Model!D34:AY34 "Specified Reserve Balance"
- Model!D35:AY35 "Deposit to the Reserve Account"
- Model!D36:AY36 "Regular Allocation of Principal paid"
- Model!D37:AY37 "Release from the Reserve Account"
- Model!D38:AY38 "Distributions to the Certificateholders"
- Model!D41:AY41 "Reserve Account - closing"
- Model!D44:AY44 "Total principal paid to the Notes"
- Model!D45:AY45 "Class A principal paid"
- Model!D46:AY46 "Class A Note Balance"
- Model!D47:AY47 "Class B principal paid"
- Model!D48:AY48 "Class B Note Balance"
- Model!D49:AY49 "Class C principal paid"
- Model!D50:AY50 "Class C Note Balance"
- Model!C53 "Prepayment rate (SMM)"
- Model!C54 "Default rate (MDR)"
- Model!C55 "Total distributions to the Certificateholders"

TERMS:
INDENTURE - ELSBY AUTO RECEIVABLES TRUST

INDENTURE dated as of the Closing Date between Elsby Auto Receivables Trust (the "Issuer") and the Indenture Trustee, relating to the Issuer's Class A Asset Backed Notes, Class B Asset Backed Notes, Class C Asset Backed Notes (the "Notes"). Amounts and rates referred to by a caption in quotation marks are set forth in Schedule 1 (the Assumptions sheet of the Model).

ARTICLE I
DEFINITIONS AND ACCOUNTING TERMS

Section 1.01 Defined Terms. As used in this Agreement, the following terms have the meanings specified below:
"Available Funds" means, for any Payment Date, the sum of Collections for the related Collection Period and the Reserve Account Draw Amount for such Payment Date.
"Class A Interest Distributable Amount" means, for any Payment Date, interest accrued for the related Collection Period at the "Class A Interest Rate" (30/360, i.e. one-twelfth of the annual rate) on the outstanding principal amount of the Class A Notes immediately preceding such Payment Date.
"Class B Interest Distributable Amount" means, for any Payment Date, interest accrued for the related Collection Period at the "Class B Interest Rate" (30/360, i.e. one-twelfth of the annual rate) on the outstanding principal amount of the Class B Notes immediately preceding such Payment Date.
"Class C Interest Distributable Amount" means, for any Payment Date, interest accrued for the related Collection Period at the "Class C Interest Rate" (30/360, i.e. one-twelfth of the annual rate) on the outstanding principal amount of the Class C Notes immediately preceding such Payment Date.
"Clean-Up Call" has the meaning assigned to such term in Section 3.04.
"Collection Period" means each calendar month; each column of the Model after the first is one Collection Period and its related Payment Date, numbered from 1.
"Collections" means, for any Collection Period, interest collections, scheduled principal collections and prepayments on the Receivables, and Recoveries, each as determined in accordance with Annex A.
"Defaulted Receivable" means any Receivable charged off by the Servicer in accordance with Annex A; the principal balance of a Defaulted Receivable is excluded from the Pool Balance from the Collection Period in which it defaults.
"Event of Default" has the meaning assigned to such term in Section 4.01.
"First Allocation of Principal" means, for any Payment Date, an amount (not less than zero) equal to (a) the aggregate outstanding principal amount of the Class A Notes immediately preceding such Payment Date minus (b) the Pool Balance at the end of the related Collection Period.
"Initial Pool Balance" means the Pool Balance as of the Closing Date (the first column of the Model).
"Note Balance" means, as of any date, the aggregate outstanding principal amount of the Class A, Class B and Class C Notes.
"Pool Balance" means, as of the end of any Collection Period, the aggregate principal balance of the Receivables (other than Defaulted Receivables) as of such date.
"Rating Agency Condition" means, with respect to any action, that each Rating Agency shall have been given ten days' prior notice thereof and shall not have notified the Issuer that such action will result in a reduction or withdrawal of its then-current rating of any Class of Notes.
"Receivables" means the motor vehicle retail installment sale contracts transferred to the Issuer on the Closing Date.
"Recoveries" means amounts received in respect of Defaulted Receivables, determined in accordance with Annex A.
"Regular Allocation of Principal" means, for any Payment Date, an amount (not less than zero) equal to the lesser of (a) the Note Balance immediately preceding such Payment Date and (b) such Note Balance minus the excess of the Pool Balance at the end of the related Collection Period over the Target Overcollateralization Amount, minus the sum of the First Allocation of Principal, Second Allocation of Principal, Third Allocation of Principal for such Payment Date.
"Reserve Account Draw Amount" means, for any Payment Date, the lesser of (a) the amount on deposit in the Reserve Account immediately preceding such Payment Date and (b) the amount, if any, by which the sum of the amounts payable under clauses (i), (ii), (iii), (iv), (v), (vi), (vii) of Section 3.01 (the full amounts required, before any shortfall) exceeds Collections for the related Collection Period.
"Second Allocation of Principal" means, for any Payment Date, an amount (not less than zero) equal to (a) the aggregate outstanding principal amount of the Class A Notes and Class B Notes immediately preceding such Payment Date minus (b) the Pool Balance at the end of the related Collection Period minus (c) the First Allocation of Principal for such Payment Date.
"Servicer Termination Event" means the failure of the Servicer to deliver any required payment within five Business Days, or the insolvency of the Servicer.
"Servicing Fee" means, for any Collection Period, one-twelfth of the "Servicing Fee Rate" multiplied by the Pool Balance at the beginning of such Collection Period.
"Specified Reserve Balance" means, for any Payment Date, the "Specified Reserve Percentage" multiplied by the Initial Pool Balance; provided that the Specified Reserve Balance shall be zero on any Payment Date on which the Note Balance immediately preceding such Payment Date is zero.
"Target Overcollateralization Amount" means, for any Payment Date, the greater of (a) the "Target OC Percentage" multiplied by the Pool Balance at the end of the related Collection Period and (b) the "OC Floor Percentage" multiplied by the Initial Pool Balance.
"Third Allocation of Principal" means, for any Payment Date, an amount (not less than zero) equal to (a) the aggregate outstanding principal amount of the Class A Notes and Class B Notes and Class C Notes immediately preceding such Payment Date minus (b) the Pool Balance at the end of the related Collection Period minus (c) the First Allocation of Principal and the Second Allocation of Principal for such Payment Date.

ARTICLE II
THE NOTES

Section 2.01 Issuance of the Notes. On the Closing Date the Issuer issued the Class A Notes in an initial principal amount equal to the amount set forth opposite "Class A Initial Note Balance" in Schedule 1, Class B Notes in an initial principal amount equal to the amount set forth opposite "Class B Initial Note Balance" in Schedule 1, Class C Notes in an initial principal amount equal to the amount set forth opposite "Class C Initial Note Balance" in Schedule 1. Interest on each Class accrues at the rate set forth opposite its "Interest Rate" caption in Schedule 1.

ARTICLE III
PAYMENTS

Section 3.01 Priority of Payments. On each Payment Date the Indenture Trustee shall apply Available Funds in the following order of priority, in each case to the extent of Available Funds remaining after all prior clauses: (i) to the Servicer, the Servicing Fee; (ii) to the Class A Noteholders, the Class A Interest Distributable Amount; (iii) to the Principal Distribution Account, the First Allocation of Principal; (iv) to the Class B Noteholders, the Class B Interest Distributable Amount; (v) to the Principal Distribution Account, the Second Allocation of Principal; (vi) to the Class C Noteholders, the Class C Interest Distributable Amount; (vii) to the Principal Distribution Account, the Third Allocation of Principal; (viii) to the Reserve Account, the amount, if any, necessary to cause the amount on deposit in the Reserve Account (after any Reserve Account Draw Amount) to equal the Specified Reserve Balance; (ix) to the Principal Distribution Account, the Regular Allocation of Principal; (x) to the Certificateholders, all remaining Available Funds.

Section 3.02 Principal Distribution Account. On each Payment Date all amounts deposited in the Principal Distribution Account shall be paid sequentially: first to the Class A Noteholders until the Class A Notes are paid in full, then to the Class B Noteholders until the Class B Notes are paid in full, then to the Class C Noteholders until the Class C Notes are paid in full.

Section 3.03 Reserve Account. On the Closing Date the Issuer deposited into the Reserve Account an amount equal to the Specified Reserve Balance. On each Payment Date (a) the Reserve Account Draw Amount shall be withdrawn and included in Available Funds, and (b) after the application of Available Funds under Section 3.01, any amount on deposit in the Reserve Account (after the withdrawal under clause (a)) in excess of the Specified Reserve Balance shall be released to the Certificateholders. The Reserve Account earns no interest.

Section 3.04 Optional Redemption. The Servicer may purchase all Receivables on any Payment Date on which the Pool Balance is 10% or less of the Initial Pool Balance (the "Clean-Up Call"), in which case the Notes shall be redeemed in full at par plus accrued interest.

ARTICLE IV
DEFAULTS AND REMEDIES

Section 4.01 Events of Default. Each of the following is an Event of Default: (a) a default in the payment of interest on the Controlling Class for five days; (b) a default in the payment of principal of any Note at its final scheduled payment date; (c) insolvency of the Issuer. Upon an Event of Default the Notes may be accelerated and principal shall be paid in accordance with the post-acceleration priority of payments.

Section 4.02 Servicer Termination. Upon a Servicer Termination Event, Noteholders holding a majority of the Controlling Class may terminate the Servicer and appoint a successor, whose servicing fee may not exceed 1.50% per annum.

ANNEX A - MODEL CONVENTIONS
ANNEX A is the Model convention (the Servicer's collateral model). (1) The first column shows balances at the Closing Date; each later column is a Collection Period numbered from 1, with its Payment Date. (2) Defaulted Receivables in a Collection Period = the Pool Balance at its beginning multiplied by the monthly default rate 1 - (1 - "Default Rate (CDR)")^(1/12). (3) Interest collections = (the Pool Balance at the beginning of the Collection Period minus Defaulted Receivables) multiplied by the "Weighted Average Coupon" / 12. (4) Scheduled principal collections = the level monthly payment that amortizes (the Pool Balance at the beginning of the Collection Period minus Defaulted Receivables) over the remaining term (the "Remaining Term at Closing (months)" minus the Collection Period number plus 1) at the "Weighted Average Coupon" / 12, minus interest collections. (5) Prepayments = ((the Pool Balance at the beginning of the Collection Period minus Defaulted Receivables) minus scheduled principal collections) multiplied by the monthly rate 1 - (1 - CPR)^(1/12), where CPR is the "Prepayment Speed (CPR)". (6) Pool Balance at the end = at the beginning minus Defaulted Receivables minus scheduled principal collections minus prepayments. (7) Recoveries in the Collection Period numbered m = the Defaulted Receivables of the Collection Period numbered (m minus the "Recovery Lag (months)") multiplied by (1 minus the "Loss Severity"); Recoveries are zero while m does not exceed the "Recovery Lag (months)". (8) No Clean-Up Call, Event of Default, acceleration, Servicer Termination Event or Rating Agency action occurs in the Model; provisions concerning them have no effect on the Model. (9) Notes are paid on every Payment Date shown; amounts are not rounded. (10) Distributions to the Certificateholders on a Payment Date comprise the amount paid under the last clause of Section 3.01 plus any amount released from the Reserve Account under Section 3.03.

SCHEDULE 1 - ASSUMPTIONS
Schedule 1 is the Assumptions sheet of the Model. Each caption in quotation marks refers to the value set forth opposite that caption.


CONVENTIONS:
- The Indenture above governs. Implement every provision that affects the rows of the Model exactly as drafted; provisions about events that do not occur in the Model (see Annex A) have no effect.
- Amounts in $ millions; rates as decimals; one column per monthly Collection Period and its Payment Date.

RULES:
- Every formula must be live and linked to the inputs: the model will be re-calculated with different input values, so typed numbers will be wrong.
- Do not change inputs (the Assumptions sheet and any given values), labels or headers.
- Allowed functions: SUM, AVERAGE, MIN, MAX, COUNT, IF, IFERROR, AND, OR, NOT, ABS, ROUND, ROUNDUP, ROUNDDOWN, INT, MOD, POWER, SQRT, LN, EXP, SIGN, SUMPRODUCT, NPV, PMT, IRR, INDEX, MATCH, CHOOSE.
- You may use empty cells for helper calculations.

Assumptions sheet: C4 Weighted Average Coupon; C5 Remaining Term at Closing (months); C6 Prepayment Speed (CPR); C7 Default Rate (CDR); C8 Loss Severity; C9 Recovery Lag (months); C10 Servicing Fee Rate; C11 Class A Initial Note Balance; C12 Class A Interest Rate; C13 Class B Initial Note Balance; C14 Class B Interest Rate; C15 Class C Initial Note Balance; C16 Class C Interest Rate; C17 Target OC Percentage; C18 OC Floor Percentage; C19 Specified Reserve Percentage

Use the tools to inspect and edit the workbook. Call submit when you are done.
````

## Reference formulas (first projection column and single-cell results)

| Cell | Label | Formula |
|---|---|---|
| Model!D5 | Model!D5 (Collection Period number P1) | `=C5+1` |
| Model!D6 | Model!D6 (Defaulted Receivables P1) | `=C10*$C$54` |
| Model!D7 | Model!D7 (Interest Collections P1) | `=(C10-D6)*Assumptions!$C$4/12` |
| Model!D8 | Model!D8 (Scheduled Principal Collections P1) | `=PMT(Assumptions!$C$4/12,Assumptions!$C$5-D5+1,-(C10-D6))-D7` |
| Model!D9 | Model!D9 (Prepayments P1) | `=((C10-D6)-D8)*$C$53` |
| Model!D10 | Model!D10 (Pool Balance P1) | `=C10-D6-D8-D9` |
| Model!D11 | Model!D11 (Recoveries P1) | `=IF(D5>Assumptions!$C$9,INDEX($D$6:$AY$6,D5-Assumptions!$C$9)*(1-Assumptions!$C$8),0)` |
| Model!D14 | Model!D14 (Collections P1) | `=D7+D8+D9+D11` |
| Model!D15 | Model!D15 (Target Overcollateralization Amount P1) | `=MAX(Assumptions!$C$17*D10,Assumptions!$C$18*$C$10)` |
| Model!D16 | Model!D16 (Servicing Fee P1) | `=C10*Assumptions!$C$10/12` |
| Model!D17 | Model!D17 (Class A Interest Distributable Amount P1) | `=C46*Assumptions!$C$12/12` |
| Model!D18 | Model!D18 (First Allocation of Principal P1) | `=MAX(0,C46-D10)` |
| Model!D19 | Model!D19 (Class B Interest Distributable Amount P1) | `=C48*Assumptions!$C$14/12` |
| Model!D20 | Model!D20 (Second Allocation of Principal P1) | `=MAX(0,C46+C48-D10)-D18` |
| Model!D21 | Model!D21 (Class C Interest Distributable Amount P1) | `=C50*Assumptions!$C$16/12` |
| Model!D22 | Model!D22 (Third Allocation of Principal P1) | `=MAX(0,C46+C48+C50-D10)-D18-D20` |
| Model!D23 | Model!D23 (Reserve Account Draw Amount P1) | `=MIN(C41,MAX(0,D16+D17+D18+D19+D20+D21+D22-D14))` |
| Model!D24 | Model!D24 (Available Funds P1) | `=D14+D23` |
| Model!D27 | Model!D27 (Servicing Fee paid P1) | `=MIN(D24,D16)` |
| Model!D28 | Model!D28 (Class A interest paid P1) | `=MIN(D24-D27,D17)` |
| Model!D29 | Model!D29 (First Allocation of Principal paid P1) | `=MIN(D24-D27-D28,D18)` |
| Model!D30 | Model!D30 (Class B interest paid P1) | `=MIN(D24-D27-D28-D29,D19)` |
| Model!D31 | Model!D31 (Second Allocation of Principal paid P1) | `=MIN(D24-D27-D28-D29-D30,D20)` |
| Model!D32 | Model!D32 (Class C interest paid P1) | `=MIN(D24-D27-D28-D29-D30-D31,D21)` |
| Model!D33 | Model!D33 (Third Allocation of Principal paid P1) | `=MIN(D24-D27-D28-D29-D30-D31-D32,D22)` |
| Model!D34 | Model!D34 (Specified Reserve Balance P1) | `=IF(C46+C48+C50>0,Assumptions!$C$19*$C$10,0)` |
| Model!D35 | Model!D35 (Deposit to the Reserve Account P1) | `=MIN(D24-D27-D28-D29-D30-D31-D32-D33,MAX(0,D34-(C41-D23)))` |
| Model!D36 | Model!D36 (Regular Allocation of Principal paid P1) | `=MIN(D24-D27-D28-D29-D30-D31-D32-D33-D35,MAX(0,MIN(C46+C48+C50,C46+C48+C50-D10+D15)-D18-D20-D22))` |
| Model!D37 | Model!D37 (Release from the Reserve Account P1) | `=MAX(0,C41-D23-D34)` |
| Model!D38 | Model!D38 (Distributions to the Certificateholders P1) | `=D24-D27-D28-D29-D30-D31-D32-D33-D35-D36+D37` |
| Model!D41 | Model!D41 (Reserve Account - closing P1) | `=C41-D23+D35-D37` |
| Model!D44 | Model!D44 (Total principal paid to the Notes P1) | `=D29+D31+D33+D36` |
| Model!D45 | Model!D45 (Class A principal paid P1) | `=MIN(C46,D44)` |
| Model!D46 | Model!D46 (Class A Note Balance P1) | `=C46-D45` |
| Model!D47 | Model!D47 (Class B principal paid P1) | `=MIN(C48,D44-D45)` |
| Model!D48 | Model!D48 (Class B Note Balance P1) | `=C48-D47` |
| Model!D49 | Model!D49 (Class C principal paid P1) | `=MIN(C50,D44-D45-D47)` |
| Model!D50 | Model!D50 (Class C Note Balance P1) | `=C50-D49` |
| Model!C53 | Model!C53 (Prepayment rate (SMM)) | `=1-(1-Assumptions!$C$6)^(1/12)` |
| Model!C54 | Model!C54 (Default rate (MDR)) | `=1-(1-Assumptions!$C$7)^(1/12)` |
| Model!C55 | Model!C55 (Total distributions to the Certificateholders) | `=SUM($D$38:$AY$38)` |
