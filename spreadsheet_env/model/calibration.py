"""Sector profiles: plausible ranges for the operating drivers of generated models.

Ranges are (low, high) for uniform sampling. The COGS, SG&A, capex and working-capital
ranges are **calibrated to Damodaran's industry averages** (US, January 2026 update):
industry value +-20% for COGS % and +-25% for the others, with COGS capped so that
COGS% + minimum SG&A% <= 97% of revenue. Derivations and the before/after check are in
``docs/research/04_calibration.md`` (reproduce: ``python -I scripts/calibration_check.py``).

Not calibrated (no comparable field in those datasets; hand-set, broad): revenue growth,
D&A as % of opening PP&E, PP&E / revenue.

Payable days are expressed against COGS because the model computes payables as
COGS x DPO / 365; for asset-light sectors whose payables also cover operating
expenses (software, telecom), the equivalent DPO is therefore high.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

R = Tuple[float, float]


@dataclass(frozen=True)
class SectorProfile:
    name: str
    company_noun: str
    damodaran_industry: str
    growth: R
    cogs_pct: R
    sga_pct: R
    capex_pct: R
    da_pct: R  # D&A as % of opening net PP&E (not calibrated)
    ppe_to_rev: R  # not calibrated
    dso: R
    dio: R
    dpo: R


PROFILES: Dict[str, SectorProfile] = {
    p.name: p
    for p in [
        SectorProfile("software", "Software company", "Software (System & Application)",
                      growth=(0.06, 0.25), cogs_pct=(0.226, 0.340), sga_pct=(0.183, 0.305),
                      capex_pct=(0.054, 0.090), da_pct=(0.15, 0.30), ppe_to_rev=(0.10, 0.30),
                      dso=(46, 77), dio=(4.4, 7.3), dpo=(81, 135)),
        SectorProfile("retail", "Retailer", "Retail (General)",
                      growth=(0.01, 0.08), cogs_pct=(0.534, 0.802), sga_pct=(0.157, 0.261),
                      capex_pct=(0.047, 0.079), da_pct=(0.08, 0.15), ppe_to_rev=(0.15, 0.35),
                      dso=(9.6, 16.0), dio=(35.5, 59.2), dpo=(48.7, 81.2)),
        SectorProfile("manufacturing", "Industrial machinery manufacturer", "Machinery",
                      growth=(0.01, 0.09), cogs_pct=(0.500, 0.750), sga_pct=(0.147, 0.246),
                      capex_pct=(0.019, 0.032), da_pct=(0.07, 0.12), ppe_to_rev=(0.20, 0.50),
                      dso=(52, 87), dio=(73, 121), dpo=(43.5, 72.4)),
        SectorProfile("consumer_staples", "Packaged food company", "Food Processing",
                      growth=(0.01, 0.06), cogs_pct=(0.614, 0.879), sga_pct=(0.091, 0.152),
                      capex_pct=(0.047, 0.078), da_pct=(0.06, 0.11), ppe_to_rev=(0.25, 0.50),
                      dso=(21, 35), dio=(48, 80), dpo=(43, 72)),
        SectorProfile("healthcare_services", "Healthcare services provider", "Healthcare Support Services",
                      growth=(0.03, 0.10), cogs_pct=(0.703, 0.907), sga_pct=(0.063, 0.105),
                      capex_pct=(0.005, 0.009), da_pct=(0.08, 0.14), ppe_to_rev=(0.03, 0.10),
                      dso=(19, 32), dio=(10.7, 17.9), dpo=(44, 73)),
        SectorProfile("telecom", "Telecom operator", "Telecom. Services",
                      growth=(0.00, 0.04), cogs_pct=(0.330, 0.494), sga_pct=(0.168, 0.280),
                      capex_pct=(0.112, 0.187), da_pct=(0.07, 0.12), ppe_to_rev=(0.80, 1.50),
                      dso=(35, 59), dio=(13.6, 22.6), dpo=(139, 231)),
    ]
}
