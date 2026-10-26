# charter_build-d4-s0

**Certificate of incorporation (document spec): liquidation preferences, pari passu classes, accruing dividends and weighted-average anti-dilution.** Family `charter_build`, level 4, training seed 0; 283 graded cells, 11 perturbation scenarios.

## What the agent sees

````text
You are building a liquidation waterfall under a certificate of incorporation (Vantor Technologies, Inc.) in a spreadsheet (sheets: Assumptions, Model; amounts in $m). Column C holds the starting point, columns D:O the projection (Exit 1, Exit 2, Exit 3, Exit 4, Exit 5, Exit 6, Exit 7, Exit 8, Exit 9, Exit 10, Exit 11, Exit 12).

TASK: the cells below are empty. Write a formula in every one so that the model implements the TERMS below exactly. Work out each row's logic from the terms and the row labels.
- Model!D5:O5 "Conversion test 1: price per common share if Series Seed convert"
- Model!D6:O6 "Series Seed converts (1/0)"
- Model!D7:O7 "Conversion test 2: price per common share if Series Seed, Series A convert"
- Model!D8:O8 "Series A converts (1/0)"
- Model!D9:O9 "Conversion test 3: price per common share if Series Seed, Series A, Series C convert"
- Model!D10:O10 "Series C converts (1/0)"
- Model!D11:O11 "Conversion test 4: price per common share if Series Seed, Series A, Series C, Series B convert"
- Model!D12:O12 "Series B converts (1/0)"
- Model!D15:O15 "Series C preferential amount paid"
- Model!D16:O16 "Series B preferential amount paid"
- Model!D17:O17 "Full preferential amounts of Series Seed and Series A (not converting)"
- Model!D18:O18 "Series Seed preferential amount paid"
- Model!D19:O19 "Series A preferential amount paid"
- Model!D22:O22 "Remaining assets for Common Stock (as converted)"
- Model!D23:O23 "Shares of Common Stock sharing (as converted)"
- Model!D24:O24 "Price per share of Common Stock"
- Model!D27:O27 "Holders of Common Stock"
- Model!D28:O28 "Series Seed holders"
- Model!D29:O29 "Series A holders"
- Model!D30:O30 "Series B holders"
- Model!D31:O31 "Series C holders"
- Model!D32:O32 "Total distributed (all holders)"
- Model!C35 "Series Seed Liquidation Preference per share"
- Model!C36 "Series Seed aggregate Liquidation Preference"
- Model!C37 "Series A Liquidation Preference per share"
- Model!C38 "Series A aggregate Liquidation Preference"
- Model!C39 "Series B Liquidation Preference per share"
- Model!C40 "Series B aggregate Liquidation Preference"
- Model!C41 "Series C Liquidation Preference per share"
- Model!C42 "Series C aggregate Liquidation Preference"
- Model!C43 "Anti-dilution: A (shares deemed outstanding before the Series C issuance)"
- Model!C44 "Series Seed Conversion Price"
- Model!C45 "Series Seed Conversion Rate"
- Model!C46 "Series A Conversion Price"
- Model!C47 "Series A Conversion Rate"
- Model!C48 "Series B Conversion Price"
- Model!C49 "Series B Conversion Rate"
- Model!C52 "Series Seed multiple of invested capital at the highest Liquidation Amount"
- Model!C53 "Series A multiple of invested capital at the highest Liquidation Amount"
- Model!C54 "Series B multiple of invested capital at the highest Liquidation Amount"
- Model!C55 "Series C multiple of invested capital at the highest Liquidation Amount"

TERMS:
AMENDED AND RESTATED CERTIFICATE OF INCORPORATION OF VANTOR TECHNOLOGIES, INC.

AMENDED AND RESTATED CERTIFICATE OF INCORPORATION of Vantor Technologies, Inc. (the "Corporation"). ARTICLE FOURTH sets forth the rights, powers and preferences of the Common Stock and of the Preferred Stock, consisting of the Series Seed Preferred Stock, Series A Preferred Stock, Series B Preferred Stock, Series C Preferred Stock. Share numbers, prices and rates referred to by a caption in quotation marks are set forth in Schedule 1 (the Assumptions sheet of the Model).

ARTICLE I
DEFINITIONS

Section 1.01 Defined Terms. As used in this Agreement, the following terms have the meanings specified below:
"Accruing Dividends" means, for each share of a series of Preferred Stock, dividends accruing from its Original Issue Date at the rate per annum set forth opposite "<series> Dividend Rate" in Schedule 1 on its Original Issue Price, simple (not compounding), for the number of years set forth opposite "<series> years from Original Issue Date to the Liquidation Event" in Schedule 1.
"Common Stock" means the common stock of the Corporation; the number of shares outstanding is set forth opposite "Common Stock outstanding (m shares)" in Schedule 1.
"Conversion Price" means, for any series of Preferred Stock, its Original Issue Price, subject to adjustment pursuant to Section 4.02.
"Conversion Rate" means, for any series of Preferred Stock, its Original Issue Price divided by its Conversion Price, as adjusted pursuant to Section 4.02.
"Deemed Liquidation Event" means (a) a merger or consolidation in which the stockholders of the Corporation do not hold a majority of the voting power of the surviving entity, or (b) a sale of all or substantially all of the assets of the Corporation.
"Exempted Securities" means (a) Options granted under the Equity Incentive Plan, (b) shares issued upon conversion of Preferred Stock, and (c) shares issued in connection with a bona fide acquisition approved by the Board.
"Liquidation Amount" means the amount available for distribution to the stockholders of the Corporation upon a Liquidation Event, as set forth for each column of the Model opposite "Liquidation Amount" in Schedule 1.
"Liquidation Event" means any liquidation, dissolution or winding up of the Corporation or any Deemed Liquidation Event.
"Liquidation Preference" means, for each share of a series of Preferred Stock, its Original Issue Price multiplied by its Liquidation Multiple (as set forth opposite the caption "<series> Liquidation Multiple" in Schedule 1), plus all Accruing Dividends on such share.
"Options" means rights to acquire Common Stock granted under the Equity Incentive Plan; the number outstanding is set forth opposite "Options outstanding (m)" in Schedule 1.
"Original Issue Price" means, for each series of Preferred Stock, the price per share set forth opposite the caption "<series> Original Issue Price ($)" in Schedule 1.
"Preferred Stock" means the Series Seed Preferred Stock, Series A Preferred Stock, Series B Preferred Stock, Series C Preferred Stock, and "series" refers to each of them; the number of shares of each series outstanding is set forth opposite "<series> shares outstanding (m)" in Schedule 1.
"Qualified IPO" means a firm-commitment underwritten public offering at a price per share of at least three times the Original Issue Price of the most senior series, with gross proceeds of at least $75,000,000.
"Requisite Holders" means the holders of a majority of the outstanding Preferred Stock, voting together on an as-converted basis.

ARTICLE II
DIVIDENDS

Section 2.01 Accruing Dividends. Accruing Dividends accrue on each share of Preferred Stock as set forth in the definition thereof, whether or not declared. They are payable only (a) when, as and if declared by the Board, which has not occurred, or (b) as part of the Liquidation Preference. A share that is converted into Common Stock ceases to be entitled to any Accruing Dividends.

ARTICLE III
LIQUIDATION

Section 3.01 Liquidation Preference. (a) Upon a Liquidation Event, the holders of each series of Preferred Stock shall be entitled to receive, out of the Liquidation Amount, for each share, the greater of (i) its Liquidation Preference and (ii) the amount per share that would have been payable had all shares of such series been converted into Common Stock at the Conversion Rate immediately prior to the Liquidation Event (a series receiving the amount in clause (ii) being treated as converted and receiving no amount under clause (i)). (b) Payments under clause (a)(i) shall be made in the following order of priority: first to the Series C Preferred Stock; then to the Series B Preferred Stock; then to the Series Seed Preferred Stock and the Series A Preferred Stock (pari passu with each other). If the amount available is insufficient to pay in full the Liquidation Preferences of a class ranking pari passu, it shall be distributed among the holders of that class ratably in proportion to the full preferential amounts to which they would otherwise be entitled. (c) After payment of the Liquidation Preferences, the remaining Liquidation Amount shall be distributed ratably among the holders of Common Stock and the holders of Preferred Stock treated as converted (on an as-converted basis, each converted share counting as its Conversion Rate shares of Common Stock).

Section 3.02 Deemed Liquidation Events. Each Deemed Liquidation Event shall be treated as a Liquidation Event unless the Requisite Holders elect otherwise by written notice given at least ten days before its effective date.

ARTICLE IV
CONVERSION

Section 4.01 Optional Conversion. Each share of Preferred Stock is convertible at any time, at the option of the holder, into a number of shares of Common Stock equal to its Conversion Rate.

Section 4.02 Adjustment for Dilutive Issuances. If the Corporation issues Additional Shares of Common Stock (other than Exempted Securities) at a price per share less than the Conversion Price of a series in effect immediately before such issuance, the Conversion Price of that series shall be reduced to CP2 = CP1 x (A + B) / (A + C), where CP1 is that Conversion Price immediately before the issuance; A is the number of shares of Common Stock outstanding immediately before the issuance, treating all outstanding Options and all outstanding Preferred Stock (other than the shares then issued) as exercised or converted into one share of Common Stock each; B is the number of shares of Common Stock that the aggregate consideration received for the issuance would purchase at CP1; and C is the number of shares issued. The issuance of the Series C Preferred Stock, at its Original Issue Price, was an issuance of Additional Shares of Common Stock for this purpose (and was the only one); the Series C Preferred Stock is not itself adjusted.

Section 4.03 Mandatory Conversion. Upon the closing of a Qualified IPO, or upon the written election of the Requisite Holders, all outstanding shares of Preferred Stock shall automatically convert into Common Stock at the then effective Conversion Rate.

ARTICLE V
OTHER RIGHTS

Section 5.01 Voting. Each holder of Preferred Stock votes together with the Common Stock on an as-converted basis; the holders of the most senior series, voting as a separate class, may elect one director.

Section 5.02 Redemption. The Preferred Stock is not redeemable at the option of the holder or of the Corporation.

ANNEX A - MODEL CONVENTIONS
ANNEX A is the Model convention. (1) Each column of the Model is a separate Liquidation Event with the Liquidation Amount given for that column (amounts in $ millions; shares in millions). (2) For the purposes of Section 3.01(a), the series are tested one at a time in the following order: Series Seed, Series A, Series C, Series B. A series is treated as converted if and only if every series earlier in that order is treated as converted and, assuming that series and every earlier series in the order convert and every later series does not, the amount per share of Common Stock under Section 3.01(c) multiplied by the series' Conversion Rate is at least its Liquidation Preference per share; for this test the amount per share of Common Stock is the greater of zero and (the Liquidation Amount minus the Liquidation Preferences of the series assumed not to convert), divided by the shares of Common Stock plus the as-converted shares of the series assumed to convert. (3) Options are not exercised in the Model and receive nothing. (4) The multiple of invested capital of a series = the total amount received by its holders at the highest Liquidation Amount (the last column) divided by (its shares outstanding multiplied by its Original Issue Price). (5) No Qualified IPO, mandatory conversion, optional conversion other than as determined under (2), redemption or dividend declaration occurs in the Model; provisions concerning them have no effect on the Model.

SCHEDULE 1 - ASSUMPTIONS
Schedule 1 is the Assumptions sheet of the Model; "<series>" in a caption stands for the name of the relevant series (for example "Series A shares outstanding (m)").


CONVENTIONS:
- The Certificate above governs. Implement every provision that affects the rows of the Model exactly as drafted; provisions about events that do not occur in the Model (see Annex A) have no effect.
- Amounts in $ millions, shares in millions, prices in $ per share; flags are 1 or 0.
- Each column is computed independently from its Liquidation Amount; Liquidation Amounts are always given in ascending order.

RULES:
- Every formula must be live and linked to the inputs: the model will be re-calculated with different input values, so typed numbers will be wrong.
- Do not change inputs (the Assumptions sheet and any given values), labels or headers.
- Allowed functions: SUM, AVERAGE, MIN, MAX, COUNT, IF, IFERROR, AND, OR, NOT, ABS, ROUND, ROUNDUP, ROUNDDOWN, INT, MOD, POWER, SQRT, LN, EXP, SIGN, SUMPRODUCT, NPV, PMT, IRR, INDEX, MATCH, CHOOSE.
- You may use empty cells for helper calculations.

Assumptions sheet: C4 Common Stock outstanding (m shares); C5 Options outstanding (m); C6 Series Seed shares outstanding (m); C7 Series Seed Original Issue Price ($); C8 Series Seed Liquidation Multiple; C9 Series Seed Dividend Rate; C10 Series Seed years from Original Issue Date to the Liquidation Event; C11 Series A shares outstanding (m); C12 Series A Original Issue Price ($); C13 Series A Liquidation Multiple; C14 Series A Dividend Rate; C15 Series A years from Original Issue Date to the Liquidation Event; C16 Series B shares outstanding (m); C17 Series B Original Issue Price ($); C18 Series B Liquidation Multiple; C19 Series B Dividend Rate; C20 Series B years from Original Issue Date to the Liquidation Event; C21 Series C shares outstanding (m); C22 Series C Original Issue Price ($); C23 Series C Liquidation Multiple; C24 Series C Dividend Rate; C25 Series C years from Original Issue Date to the Liquidation Event; row 27 Liquidation Amount (D:O)

Use the tools to inspect and edit the workbook. Call submit when you are done.
````

## Reference formulas (first projection column and single-cell results)

| Cell | Label | Formula |
|---|---|---|
| Model!D5 | Model!D5 (Conversion test 1: price per common share if Series Seed convert Exit 1) | `=MAX(0,Assumptions!D27-$C$38-$C$40-$C$42)/(Assumptions!$C$4+Assumptions!$C$6*$C$45)` |
| Model!D6 | Model!D6 (Series Seed converts (1/0) Exit 1) | `=IF(AND(D5*$C$45>=$C$35),1,0)` |
| Model!D7 | Model!D7 (Conversion test 2: price per common share if Series Seed, Series A convert Exit 1) | `=MAX(0,Assumptions!D27-$C$40-$C$42)/(Assumptions!$C$4+Assumptions!$C$6*$C$45+Assumptions!$C$11*$C$47)` |
| Model!D8 | Model!D8 (Series A converts (1/0) Exit 1) | `=IF(AND(D6=1,D7*$C$47>=$C$37),1,0)` |
| Model!D9 | Model!D9 (Conversion test 3: price per common share if Series Seed, Series A, Series C convert Exit 1) | `=MAX(0,Assumptions!D27-$C$40)/(Assumptions!$C$4+Assumptions!$C$6*$C$45+Assumptions!$C$11*$C$47+Assumptions!$C$21*1)` |
| Model!D10 | Model!D10 (Series C converts (1/0) Exit 1) | `=IF(AND(D8=1,D9*1>=$C$41),1,0)` |
| Model!D11 | Model!D11 (Conversion test 4: price per common share if Series Seed, Series A, Series C, Series B convert Exit 1) | `=MAX(0,Assumptions!D27)/(Assumptions!$C$4+Assumptions!$C$6*$C$45+Assumptions!$C$11*$C$47+Assumptions!$C$21*1+Assumptions!$C$16*$C$49)` |
| Model!D12 | Model!D12 (Series B converts (1/0) Exit 1) | `=IF(AND(D10=1,D11*$C$49>=$C$39),1,0)` |
| Model!D15 | Model!D15 (Series C preferential amount paid Exit 1) | `=(1-D10)*MIN($C$42,MAX(0,Assumptions!D27))` |
| Model!D16 | Model!D16 (Series B preferential amount paid Exit 1) | `=(1-D12)*MIN($C$40,MAX(0,Assumptions!D27-D15))` |
| Model!D17 | Model!D17 (Full preferential amounts of Series Seed and Series A (not converting) Exit 1) | `=(1-D6)*$C$36+(1-D8)*$C$38` |
| Model!D18 | Model!D18 (Series Seed preferential amount paid Exit 1) | `=IF(D17=0,0,(1-D6)*$C$36*MIN(1,MAX(0,Assumptions!D27-D15-D16)/D17))` |
| Model!D19 | Model!D19 (Series A preferential amount paid Exit 1) | `=IF(D17=0,0,(1-D8)*$C$38*MIN(1,MAX(0,Assumptions!D27-D15-D16)/D17))` |
| Model!D22 | Model!D22 (Remaining assets for Common Stock (as converted) Exit 1) | `=Assumptions!D27-D15-D16-D18-D19` |
| Model!D23 | Model!D23 (Shares of Common Stock sharing (as converted) Exit 1) | `=Assumptions!$C$4+D6*Assumptions!$C$6*$C$45+D8*Assumptions!$C$11*$C$47+D12*Assumptions!$C$16*$C$49+D10*Assumptions!$C$21*1` |
| Model!D24 | Model!D24 (Price per share of Common Stock Exit 1) | `=D22/D23` |
| Model!D27 | Model!D27 (Holders of Common Stock Exit 1) | `=Assumptions!$C$4*D24` |
| Model!D28 | Model!D28 (Series Seed holders Exit 1) | `=D18+D6*Assumptions!$C$6*$C$45*D24` |
| Model!D29 | Model!D29 (Series A holders Exit 1) | `=D19+D8*Assumptions!$C$11*$C$47*D24` |
| Model!D30 | Model!D30 (Series B holders Exit 1) | `=D16+D12*Assumptions!$C$16*$C$49*D24` |
| Model!D31 | Model!D31 (Series C holders Exit 1) | `=D15+D10*Assumptions!$C$21*1*D24` |
| Model!D32 | Model!D32 (Total distributed (all holders) Exit 1) | `=D27+D28+D29+D30+D31` |
| Model!C35 | Model!C35 (Series Seed Liquidation Preference per share) | `=Assumptions!$C$7*Assumptions!$C$8+Assumptions!$C$7*Assumptions!$C$9*Assumptions!$C$10` |
| Model!C36 | Model!C36 (Series Seed aggregate Liquidation Preference) | `=Assumptions!$C$6*$C$35` |
| Model!C37 | Model!C37 (Series A Liquidation Preference per share) | `=Assumptions!$C$12*Assumptions!$C$13+Assumptions!$C$12*Assumptions!$C$14*Assumptions!$C$15` |
| Model!C38 | Model!C38 (Series A aggregate Liquidation Preference) | `=Assumptions!$C$11*$C$37` |
| Model!C39 | Model!C39 (Series B Liquidation Preference per share) | `=Assumptions!$C$17*Assumptions!$C$18+Assumptions!$C$17*Assumptions!$C$19*Assumptions!$C$20` |
| Model!C40 | Model!C40 (Series B aggregate Liquidation Preference) | `=Assumptions!$C$16*$C$39` |
| Model!C41 | Model!C41 (Series C Liquidation Preference per share) | `=Assumptions!$C$22*Assumptions!$C$23+Assumptions!$C$22*Assumptions!$C$24*Assumptions!$C$25` |
| Model!C42 | Model!C42 (Series C aggregate Liquidation Preference) | `=Assumptions!$C$21*$C$41` |
| Model!C43 | Model!C43 (Anti-dilution: A (shares deemed outstanding before the Series C issuance)) | `=Assumptions!$C$4+Assumptions!$C$5+Assumptions!$C$6+Assumptions!$C$11+Assumptions!$C$16` |
| Model!C44 | Model!C44 (Series Seed Conversion Price) | `=IF(Assumptions!$C$22<Assumptions!$C$7,Assumptions!$C$7*($C$43+Assumptions!$C$21*Assumptions!$C$22/Assumptions!$C$7)/($C$43+Assumptions!$C$21),Assumptions!$C$7)` |
| Model!C45 | Model!C45 (Series Seed Conversion Rate) | `=Assumptions!$C$7/$C$44` |
| Model!C46 | Model!C46 (Series A Conversion Price) | `=IF(Assumptions!$C$22<Assumptions!$C$12,Assumptions!$C$12*($C$43+Assumptions!$C$21*Assumptions!$C$22/Assumptions!$C$12)/($C$43+Assumptions!$C$21),Assumptions!$C$12)` |
| Model!C47 | Model!C47 (Series A Conversion Rate) | `=Assumptions!$C$12/$C$46` |
| Model!C48 | Model!C48 (Series B Conversion Price) | `=IF(Assumptions!$C$22<Assumptions!$C$17,Assumptions!$C$17*($C$43+Assumptions!$C$21*Assumptions!$C$22/Assumptions!$C$17)/($C$43+Assumptions!$C$21),Assumptions!$C$17)` |
| Model!C49 | Model!C49 (Series B Conversion Rate) | `=Assumptions!$C$17/$C$48` |
| Model!C52 | Model!C52 (Series Seed multiple of invested capital at the highest Liquidation Amount) | `=$O$28/(Assumptions!$C$6*Assumptions!$C$7)` |
| Model!C53 | Model!C53 (Series A multiple of invested capital at the highest Liquidation Amount) | `=$O$29/(Assumptions!$C$11*Assumptions!$C$12)` |
| Model!C54 | Model!C54 (Series B multiple of invested capital at the highest Liquidation Amount) | `=$O$30/(Assumptions!$C$16*Assumptions!$C$17)` |
| Model!C55 | Model!C55 (Series C multiple of invested capital at the highest Liquidation Amount) | `=$O$31/(Assumptions!$C$21*Assumptions!$C$22)` |
