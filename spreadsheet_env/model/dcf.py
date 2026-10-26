"""Procedural generator for DCF valuations with a share-price sensitivity grid.

Layout: ``Assumptions`` (drivers, WACC, terminal growth, net debt, shares),
``DCF`` (unlevered free cash flow build, discounting, valuation block) and
``Sensitivity`` (implied share price for a grid of WACC x terminal growth).

The grid is the interesting part. In Excel it is usually a What-If data table;
here each grid cell must be a formula. It is graded two ways:

* golden: each cell matches the reference under perturbed inputs;
* reference-free (``relations``): each cell equals the agent's *own* share
  price recomputed with WACC and terminal growth set to that cell's headers -
  exactly what a data table means - and the price must fall as WACC rises and
  rise with terminal growth (when the final-year cash flow is positive).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from ..engine.refs import index_to_col
from ..engine.workbook import Key, Workbook
from .calibration import PROFILES, SectorProfile
from .spec import Calc, Layout, Line, ModelSpec, Scalar, render

WACC_OFFSETS = (-0.01, -0.005, 0.0, 0.005, 0.01)
TG_OFFSETS = (-0.005, -0.0025, 0.0, 0.0025, 0.005)
GRID_SHEET = "Sensitivity"
GRID_TOP = 6  # first grid row (row 5 holds the growth headers)
GRID_LEFT = 3  # column C (column B holds the WACC headers)


@dataclass
class DCFConfig:
    n_forecast: int = 5
    mid_year: bool = False
    tax_floor: bool = False
    sector: str = ""


@dataclass
class GeneratedDCF:
    spec: ModelSpec
    sector: SectorProfile
    cfg: DCFConfig
    grid_keys: List[List[Key]] = field(default_factory=list)
    row_header_keys: List[Key] = field(default_factory=list)
    col_header_keys: List[Key] = field(default_factory=list)
    identities: list = field(default_factory=list)


def generate_dcf(rng: random.Random, cfg: DCFConfig) -> GeneratedDCF:
    prof = PROFILES[cfg.sector] if cfg.sector else rng.choice(list(PROFILES.values()))
    u = rng.uniform
    n_fc = cfg.n_forecast
    year0 = rng.randint(2020, 2025)
    periods = [f"FY{year0}A"] + [f"FY{year0 + i + 1}E" for i in range(n_fc)]
    rev0 = round(10 ** u(1.7, 4.0), 1)
    ebitda_margin = round(u(0.08, 0.35), 3)
    da_pct = round(u(0.02, 0.06), 3)
    capex_pct = round(max(da_pct + u(-0.01, 0.03), 0.01), 3)
    nwc_pct = round(u(0.03, 0.18), 3)
    tax_rate = round(u(0.19, 0.30), 3)
    wacc = round(u(0.08, 0.13), 4)
    tg = round(u(0.01, 0.03), 4)
    g_near = u(*prof.growth)
    g_fc = [round(g_near + (tg - g_near) * i / max(1, n_fc - 1) + rng.gauss(0, 0.004), 3) for i in range(n_fc)]
    nwc0 = round(rev0 * nwc_pct * u(0.9, 1.1), 1)
    ebitda_mult = u(6, 14)
    ev_guess = rev0 * ebitda_margin * ebitda_mult
    net_debt = round(ev_guess * u(-0.1, 0.5), 1)
    # share count implied by a plausible share price ($15-120) on the rough equity value
    shares = round(max(ev_guess - net_debt, ev_guess * 0.3) / u(15, 120), 2)

    A, D = "Assumptions", "DCF"
    scalars = [
        Scalar("ebitda_margin", "EBITDA margin", ebitda_margin, "%", "rate", "EBITDA as a share of revenue"),
        Scalar("da_pct", "D&A (% of revenue)", da_pct, "%", "rate", "D&A as a share of revenue"),
        Scalar("capex_pct", "Capex (% of revenue)", capex_pct, "%", "rate", "capex as a share of revenue"),
        Scalar("nwc_pct", "Net working capital (% of revenue)", nwc_pct, "%", "rate",
               "closing net working capital as a share of revenue"),
        Scalar("tax_rate", "Tax rate", tax_rate, "%", "tax", "cash tax rate on EBIT"),
        Scalar("wacc", "WACC", wacc, "%", "wacc", "discount rate"),
        Scalar("tg", "Terminal growth rate", tg, "%", "tg", "perpetual growth after the forecast"),
        Scalar("net_debt", "Net debt", net_debt, "$m", "money", "debt minus cash at valuation date"),
        Scalar("shares", "Diluted shares outstanding", shares, "m", "count", "share count"),
    ]
    lines: List[Line] = [
        Line("g_rev", "Revenue growth", A, "%", fc=None, hist="blank", forecast=g_fc, kind="rate",
             desc="year-on-year revenue growth"),
        Line("rev", "Revenue", D, fc="{rev[-1]}*(1+{g_rev})", history=[rev0],
             desc="prior-year revenue x (1 + revenue growth)", section="Free cash flow"),
        Line("ebitda", "EBITDA", D, fc="{rev}*{$ebitda_margin}", hist="blank", desc="revenue x EBITDA margin"),
        Line("da", "D&A", D, fc="{rev}*{$da_pct}", hist="blank", desc="revenue x D&A %"),
        Line("ebit", "EBIT", D, fc="{ebitda}-{da}", hist="blank", desc="EBITDA - D&A"),
        Line("tax", "Taxes on EBIT", D,
             fc="MAX(0,{ebit})*{$tax_rate}" if cfg.tax_floor else "{ebit}*{$tax_rate}", hist="blank",
             desc="EBIT x tax rate" + (", but zero when EBIT is negative" if cfg.tax_floor else "")),
        Line("nopat", "NOPAT", D, fc="{ebit}-{tax}", hist="blank", desc="EBIT - taxes on EBIT"),
        Line("capex", "Capital expenditure", D, fc="{rev}*{$capex_pct}", hist="blank",
             desc="revenue x capex % (a positive number, subtracted in free cash flow)"),
        Line("nwc", "Net working capital", D, fc="{rev}*{$nwc_pct}", history=[nwc0],
             desc="revenue x NWC %"),
        Line("d_nwc", "Increase in net working capital", D, fc="{nwc}-{nwc[-1]}", hist="blank",
             desc="current NWC - prior-year NWC"),
        Line("ufcf", "Unlevered free cash flow", D, fc="{nopat}+{da}-{capex}-{d_nwc}", hist="blank",
             desc="NOPAT + D&A - capex - increase in NWC"),
        Line("period", "Year number", D, unit="yrs", fc="{period[-1]}+1", history=[0.0], kind="ratio",
             desc="1 for the first forecast year, 2 for the second, ... (prior year + 1)",
             section="Discounting"),
    ]
    if cfg.mid_year:
        lines.append(Line("disc_t", "Discount period (mid-year)", D, unit="yrs", fc="{period}-0.5",
                          hist="blank", kind="ratio", desc="year number - 0.5 (mid-year convention)"))
        t_ref = "disc_t"
    else:
        t_ref = "period"
    lines += [
        Line("df", "Discount factor", D, unit="x", fc=f"1/(1+{{$wacc}})^{{{t_ref}}}", hist="blank", kind="ratio",
             desc=f"1 / (1 + WACC) ^ {'discount period' if cfg.mid_year else 'year number'}"),
        Line("pv", "PV of free cash flow", D, fc="{ufcf}*{df}", hist="blank",
             desc="unlevered free cash flow x discount factor"),
    ]
    calcs = [
        Calc("sum_pv", "Sum of PV of free cash flows", D, "SUM({pv@fc})",
             desc="sum of the PV of free cash flow over the forecast years", section="Valuation"),
        Calc("tv", "Terminal value (at final year)", D, "{ufcf@last}*(1+{$tg})/({$wacc}-{$tg})",
             desc="final-year free cash flow x (1 + terminal growth) / (WACC - terminal growth)"),
        Calc("pv_tv", "PV of terminal value", D, "{tv}*{df@last}",
             desc="terminal value x the final year's discount factor"),
        Calc("ev", "Enterprise value", D, "{sum_pv}+{pv_tv}", desc="sum of PV of free cash flows + PV of terminal value"),
        Calc("equity", "Equity value", D, "{ev}-{$net_debt}", desc="enterprise value - net debt"),
        Calc("price", "Implied share price", D, "{equity}/{$shares}", unit="$", kind="money",
             desc="equity value / diluted shares"),
    ]
    spec = ModelSpec(title=f"{prof.company_noun} DCF valuation", periods=periods, n_hist=1,
                     sheets=[A, D, GRID_SHEET], scalars=scalars, lines=lines, calcs=calcs)
    gen = GeneratedDCF(spec, prof, cfg)
    return gen


def render_dcf(gen: GeneratedDCF) -> Tuple[Workbook, Layout]:
    """Render the model plus the sensitivity grid (headers + closed-form cells)."""
    spec = gen.spec
    wb, lay = render(spec)
    S = GRID_SHEET
    n = gen.cfg.n_forecast
    wacc = lay.scalar_a1("wacc")
    tg = lay.scalar_a1("tg")
    nd = lay.scalar_a1("net_debt")
    sh = lay.scalar_a1("shares")
    _, ufcf_row = lay.rows["ufcf"]
    c0 = index_to_col(lay.col(spec.n_hist))
    c1 = index_to_col(lay.col(lay.n_periods - 1))
    ufcf_rng = f"DCF!${c0}${ufcf_row}:${c1}${ufcf_row}"
    ufcf_last = f"DCF!${c1}${ufcf_row}"
    wb.set_rc(S, 4, 1, "Implied share price ($): rows = WACC, columns = terminal growth")
    wb.set_rc(S, GRID_TOP - 1, 2, "WACC \\ g")
    row_keys, col_keys, grid = [], [], []
    for j, off in enumerate(TG_OFFSETS):
        c = GRID_LEFT + j
        wb.set_rc(S, GRID_TOP - 1, c, f"={tg}+{off}" if off else f"={tg}")
        col_keys.append((S.casefold(), GRID_TOP - 1, c))
    for i, off in enumerate(WACC_OFFSETS):
        r = GRID_TOP + i
        wb.set_rc(S, r, 2, f"={wacc}+{off}" if off else f"={wacc}")
        row_keys.append((S.casefold(), r, 2))
        row = []
        for j in range(len(TG_OFFSETS)):
            c = GRID_LEFT + j
            w = f"$B{r}"
            g = f"{index_to_col(c)}${GRID_TOP - 1}"
            if gen.cfg.mid_year:
                f = (f"=(NPV({w},{ufcf_rng})*(1+{w})^0.5+{ufcf_last}*(1+{g})/({w}-{g})/(1+{w})^{n - 0.5}"
                     f"-{nd})/{sh}")
            else:
                f = f"=(NPV({w},{ufcf_rng})+{ufcf_last}*(1+{g})/({w}-{g})/(1+{w})^{n}-{nd})/{sh}"
            wb.set_rc(S, r, c, f)
            row.append((S.casefold(), r, c))
        grid.append(row)
    gen.grid_keys, gen.row_header_keys, gen.col_header_keys = grid, row_keys, col_keys
    return wb, lay
