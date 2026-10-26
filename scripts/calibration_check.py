"""Check the generator's sector driver ranges against Damodaran's industry data.

Download (public, "no strings attached"; acknowledgement: Aswath Damodaran, NYU
Stern, data updated January 2026) into data/damodaran/:
margin.xls, capex.xls, wcdata.xls from https://pages.stern.nyu.edu/~adamodar/pc/datasets/

    python -I scripts/calibration_check.py

For each sector profile, derives the industry's value of every driver and
reports whether it lies inside the profile's sampling range. Only derived
statistics are written to the repository (docs/research/04_calibration.md),
never the raw files.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from spreadsheet_env.model.calibration import PROFILES  # noqa: E402

DATA = os.path.join(ROOT, "data", "damodaran")
INDUSTRY = {
    "software": "Software (System & Application)",
    "retail": "Retail (General)",
    "manufacturing": "Machinery",
    "consumer_staples": "Food Processing",
    "healthcare_services": "Healthcare Support Services",
    "telecom": "Telecom. Services",
}


def table(name: str) -> pd.DataFrame:
    raw = pd.read_excel(os.path.join(DATA, f"{name}.xls"), sheet_name="Industry Averages", header=None,
                        engine="xlrd")
    hdr = next(i for i in range(40) if any(str(x).strip() == "Industry Name" for x in raw.iloc[i].values))
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[hdr].values]
    df["Industry Name"] = df["Industry Name"].astype(str).str.strip()
    return df.set_index("Industry Name")


def main():
    m, c, w = table("margin"), table("capex"), table("wcdata")
    rows = []
    for sector, ind in INDUSTRY.items():
        p = PROFILES[sector]
        cogs = float(m.loc[ind, "COGS/Sales"])
        sga = float(m.loc[ind, "EBITDASG&A/Sales"]) - float(m.loc[ind, "EBITDA/Sales"])
        ar, inv, ap = (float(w.loc[ind, col]) for col in ("Acc Rec/ Sales", "Inventory/Sales", "Acc Pay/ Sales"))
        # Damodaran's "Net Cap Ex" includes acquisitions and capitalised R&D, so it is not
        # comparable; use capex/depreciation x D&A/sales, with D&A/sales = EBITDA margin
        # - (pre-tax, unadjusted) operating margin
        cap_dep = float(c.loc[ind, "Cap Ex/Deprecn"])
        da_sales = float(m.loc[ind, "EBITDA/Sales"]) - float(m.loc[ind, "Pre-tax Unadjusted Operating Margin"])
        capex = cap_dep * da_sales
        derived = {
            "cogs_pct": cogs, "sga_pct": sga, "capex_pct": capex,
            "dso": ar * 365, "dio": inv * 365 / cogs if cogs else float("nan"),
            "dpo": ap * 365 / cogs if cogs else float("nan"),
        }
        if "--suggest" in sys.argv:
            print(f"    SectorProfile ranges for {sector} ({ind}), industry value +-25%: " + ", ".join(
                f"{k}=({0.75 * v:.3g}, {1.25 * v:.3g})" for k, v in derived.items()))
        for k, v in derived.items():
            lo, hi = getattr(p, k)
            rows.append((sector, ind, k, v, lo, hi, (lo <= v <= hi) if v == v else None))
    lines = ["| sector | Damodaran industry | driver | industry value | generator range | inside |",
             "|---|---|---|---|---|---|"]
    for sector, ind, k, v, lo, hi, ok in rows:
        fmt = (lambda x: f"{x:.0f}") if k in ("dso", "dio", "dpo") else (lambda x: f"{x:.1%}")
        lines.append(f"| {sector} | {ind} | {k} | {fmt(v) if v == v else 'n/a'} | {fmt(lo)}–{fmt(hi)} | "
                     f"{'yes' if ok else ('n/a' if ok is None else '**no**')} |")
    text = "\n".join(lines)
    print(text)
    inside = sum(1 for r in rows if r[-1])
    total = sum(1 for r in rows if r[-1] is not None)
    print(f"\n{inside}/{total} industry values inside the generator's ranges")


if __name__ == "__main__":
    main()
