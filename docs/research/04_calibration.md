# Calibration of the generator's sector profiles

**Data**: Aswath Damodaran, NYU Stern. US industry averages, January 2026 update:

- `margin.xls`
- `capex.xls`
- `wcdata.xls`

Terms: "no strings attached", with acknowledgement. Only derived statistics are kept in this
repository; the raw files are downloaded locally into `data/damodaran/`.

**Reproduce**: `python -I scripts/calibration_check.py`

## Mapping to the model's drivers

| Model driver | Derived from |
|---|---|
| COGS % of revenue | `COGS/Sales` |
| SG&A % of revenue | `EBITDASG&A/Sales − EBITDA/Sales` |
| Capex % of revenue | `Cap Ex/Deprecn × (EBITDA/Sales − Pre-tax Unadjusted Operating Margin)` |
| DSO | `Acc Rec/Sales × 365` |
| DIO | `Inventory/Sales × 365 / (COGS/Sales)` |
| DPO | `Acc Pay/Sales × 365 / (COGS/Sales)` |

Notes on the mapping:

- **Capex.** The first version used Damodaran's `Net Cap Ex/Sales`, which includes
  acquisitions and capitalised R&D. That gave software a capex of 30% of sales and was wrong.
  The capex row uses capex/depreciation × D&A/sales instead.
- **DIO and DPO** are expressed against COGS because the model computes inventory and payables
  from COGS. For asset-light sectors (software, telecom), payables also cover operating
  expenses, so the equivalent DPO is high (108 and 185 days).

## Result

| Version | Industry values inside the generator's ranges |
|---|---|
| Hand-set ranges, first (wrong) capex derivation | 19 / 33 |
| Hand-set ranges, corrected derivation | 20 / 36 |
| **Calibrated ranges** (industry value ±20% for COGS, ±25% otherwise; COGS capped so COGS% + min SG&A% ≤ 97%) | **36 / 36** |

The biggest corrections from the hand-set ranges:

- **Consumer staples** (Food Processing): COGS 45–65% → 61–88%; SG&A 18–30% → 9–15%.
- **Healthcare services** (Healthcare Support Services): COGS 65–80% → 70–91%;
  DSO 35–60 → 19–32 days; capex 2–5% → 0.5–0.9%.
- **Software**: SG&A 30–50% → 18–31%; now carries a small inventory (4–7 days).
- **Telecom, software, retail**: DPO widened upward (see the note above).

Not calibrated, because there is no comparable field in these datasets:

- revenue growth;
- D&A as a percentage of opening PP&E;
- PP&E / revenue.

These remain broad hand-set ranges.

## Scope of the claim

Generated companies have **driver values within ±20–25% of their industry's average**. They
are not samples of real companies' joint distributions: correlations between drivers are not
modelled. The task is model construction and repair, not forecasting accuracy, so this level
of realism is what matters: plausible magnitudes and signs.
