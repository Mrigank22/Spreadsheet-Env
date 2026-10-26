"""Foreign-currency translation and consolidation (current-rate method, IAS 21 / ASC 830).

A foreign subsidiary reports in local currency (LC); the group reports in USD.
Rates are USD per 1 LC. Mechanics by level:

1. translate the subsidiary: income statement at the average rate, assets and
   liabilities at the closing rate, share capital at the historical rate,
   retained earnings rolled forward in USD; the cumulative translation
   adjustment (CTA) is the equity balancing item.
2. + dividends to the parent, translated at the spot rate on the payment date,
   and the CTA analysis (translation differences on opening net assets, on the
   year's income and on dividends) that must explain the CTA movement: a
   reference-free identity.
3. + consolidation with the parent (parent standalone USD figures; the parent's
   investment at cost is eliminated against the subsidiary's share capital).
4. + a USD-denominated intercompany loan from the parent: the subsidiary
   remeasures it at the closing rate every year end, booking an FX loss/(gain)
   in its LC income statement; both sides are eliminated on consolidation.
5. + the parent owns only part of the subsidiary: non-controlling interest
   (NCI) in net assets and in income.
"""

from __future__ import annotations

import random
from typing import List

from ..model.spec import Calc, Line, ModelSpec, Scalar
from .framework import Bundle, IdSpec, MonoSpec

DOMAIN = "fx"

LEVELS = {
    1: dict(n=4, div=False, consol=False, loan=False, nci=False),
    2: dict(n=5, div=True, consol=False, loan=False, nci=False),
    3: dict(n=5, div=True, consol=True, loan=False, nci=False),
    4: dict(n=5, div=True, consol=True, loan=True, nci=False),
    5: dict(n=6, div=True, consol=True, loan=True, nci=True),
}

# rough USD per LC, so that LC amounts have realistic magnitudes
BASE_RATE = {"EUR": 1.10, "GBP": 1.27, "INR": 0.012, "BRL": 0.19, "JPY": 0.0068, "MXN": 0.055}


def generate(rng: random.Random, level: int) -> Bundle:
    cfg = LEVELS[level]
    u = rng.uniform
    n = cfg["n"]
    y0 = rng.randint(2022, 2025)
    periods = [f"FY{y0} (opening)"] + [f"FY{y0 + i + 1}" for i in range(n)]
    lc = rng.choice(sorted(BASE_RATE))
    base = BASE_RATE[lc]
    k_lc = 1 / base  # LC amounts are larger for weak currencies
    close = [base * u(0.9, 1.1)]
    for _ in range(n):
        close.append(close[-1] * u(0.88, 1.12))
    avg = [round((close[i] + close[i + 1]) / 2 * u(0.98, 1.02), 7) for i in range(n)]
    divr = [round(close[i] + (close[i + 1] - close[i]) * u(0.3, 0.9), 7) for i in range(n)]
    close = [round(c, 7) for c in close]
    hist_rate = round(base * u(0.7, 1.3), 7)
    own = rng.choice([0.6, 0.7, 0.75, 0.8]) if cfg["nci"] else 1.0

    rev = [round(u(80, 160) * k_lc * 1.05 ** i, 1) for i in range(n)]
    exp = [round(r * u(0.78, 0.92), 1) for r in rev]
    ppe = [round(u(50, 90) * k_lc, 1)]
    liab = [round(u(20, 40) * k_lc, 1)]
    for _ in range(n):
        ppe.append(round(ppe[-1] * u(0.97, 1.08), 1))
        liab.append(round(liab[-1] * u(0.95, 1.08), 1))
    div = [round((rev[i] - exp[i]) * u(0.2, 0.5), 1) for i in range(n)]
    cap_lc = round(u(30, 60) * k_lc, 1)
    re0_lc = round(u(10, 40) * k_lc, 1)
    # USD retained earnings were built up at past average rates: near, not equal to, LC x a rate
    re0_usd = round(re0_lc * base * u(0.9, 1.1), 2)

    A, M = "Assumptions", "Model"
    scalars = [Scalar("cap_lc", f"Subsidiary share capital ({lc})", cap_lc, lc, "money"),
               Scalar("hist_rate", f"Historical rate when the share capital was issued (USD per {lc})", hist_rate,
                      "x", "count")]
    if cfg["loan"]:
        scalars.append(Scalar("loan_usd", "Intercompany loan from the parent (USD principal, no repayments)",
                              round(u(0.15, 0.35) * cap_lc * base, 1), "$m", "money"))
    if cfg["nci"]:
        scalars.append(Scalar("own", "Parent ownership of the subsidiary", own, "%", "rate"))

    lines: List[Line] = [
        Line("close", f"Closing rate (USD per {lc})", A, unit="x", kind="ratio", history=[close[0]],
             forecast=close[1:]),
        Line("avg", f"Average rate for the year (USD per {lc})", A, unit="x", kind="ratio", hist="blank",
             forecast=avg),
    ]
    if cfg["div"]:
        lines.append(Line("divr", f"Spot rate on the dividend payment date (USD per {lc})", A, unit="x",
                          kind="ratio", hist="blank", forecast=divr))
    lines += [
        Line("rev_lc", f"Subsidiary revenue ({lc})", A, unit=lc, hist="blank", forecast=rev),
        Line("exp_lc", f"Subsidiary operating expenses ({lc})", A, unit=lc, hist="blank", forecast=exp),
        Line("ppe_lc", f"Subsidiary PP&E ({lc})", A, unit=lc, history=[ppe[0]], forecast=ppe[1:]),
        Line("liab_lc", f"Subsidiary third-party liabilities ({lc})", A, unit=lc, history=[liab[0]],
             forecast=liab[1:]),
    ]
    if cfg["div"]:
        lines.append(Line("div_lc", f"Dividends paid by the subsidiary ({lc})", A, unit=lc, hist="blank",
                          forecast=div))
    if cfg["consol"]:
        pc = [round(u(40, 90), 1) for _ in range(n + 1)]
        po = [round(u(150, 300), 1) for _ in range(n + 1)]
        pl = [round(u(80, 160), 1) for _ in range(n + 1)]
        lines += [
            Line("p_cash", "Parent cash (USD)", A, history=pc[:1], forecast=pc[1:]),
            Line("p_oth", "Parent other assets (USD; excl. the investment and the loan receivable)", A,
                 history=po[:1], forecast=po[1:]),
            Line("p_liab", "Parent liabilities (USD)", A, history=pl[:1], forecast=pl[1:]),
        ]

    # ---------------- subsidiary in LC -----------------------------------------
    sub = []
    if cfg["loan"]:
        sub += [
            Line("loan_lc", f"Intercompany loan payable ({lc})", M, unit=lc, fc="{$loan_usd}/{close}",
                 hist="formula", desc="USD principal / closing rate", section=f"Subsidiary ({lc})"),
            Line("fx_loss", f"FX loss/(gain) on the intercompany loan ({lc})", M, unit=lc,
                 fc="{loan_lc}-{loan_lc[-1]}", hist="blank", desc="closing - opening LC carrying amount"),
        ]
    sub += [
        Line("ni_lc", f"Net income ({lc})", M, unit=lc, fc="{rev_lc}-{exp_lc}" + ("-{fx_loss}" if cfg["loan"] else ""),
             hist="blank", desc="revenue - expenses" + (" - FX loss on the loan" if cfg["loan"] else ""),
             section="" if cfg["loan"] else f"Subsidiary ({lc})"),
        Line("re_lc", f"Retained earnings ({lc})", M, unit=lc, history=[re0_lc],
             fc="{re_lc[-1]}+{ni_lc}" + ("-{div_lc}" if cfg["div"] else ""),
             desc="opening + net income" + (" - dividends" if cfg["div"] else "")),
        Line("na_lc", f"Net assets ({lc})", M, unit=lc, fc="{$cap_lc}+{re_lc}", hist="formula",
             desc="share capital + retained earnings"),
        Line("cash_lc", f"Cash and other net current assets ({lc})", M, unit=lc,
             fc="{na_lc}+{liab_lc}" + ("+{loan_lc}" if cfg["loan"] else "") + "-{ppe_lc}", hist="formula",
             desc="balancing item: net assets + liabilities - PP&E"),
    ]
    lines += sub
    # ---------------- translation into USD -------------------------------------
    lines += [
        Line("ni_usd", "Net income (USD)", M, fc="{ni_lc}*{avg}", hist="blank", desc="LC net income x average rate",
             section="Translation (USD)"),
    ]
    if cfg["div"]:
        lines.append(Line("div_usd", "Dividends (USD)", M, fc="{div_lc}*{divr}", hist="blank",
                          desc="LC dividends x spot rate on the payment date"))
    lines += [
        Line("cash_usd", "Cash and other net current assets (USD)", M, fc="{cash_lc}*{close}", hist="formula",
             desc="LC x closing rate"),
        Line("ppe_usd", "PP&E (USD)", M, fc="{ppe_lc}*{close}", hist="formula", desc="LC x closing rate"),
        Line("liab_usd", "Third-party liabilities (USD)", M, fc="{liab_lc}*{close}", hist="formula",
             desc="LC x closing rate"),
    ]
    na = "{cash_usd}+{ppe_usd}-{liab_usd}"
    if cfg["loan"]:
        lines.append(Line("loan_sub_usd", "Intercompany loan payable (USD)", M, fc="{loan_lc}*{close}",
                          hist="formula", desc="LC carrying amount x closing rate"))
        na += "-{loan_sub_usd}"
    lines += [
        Line("na_usd", "Net assets (USD)", M, fc=na, hist="formula", desc="translated assets - liabilities"),
        Line("cap_usd", "Share capital (USD)", M, fc="{$cap_lc}*{$hist_rate}", hist="formula",
             desc="LC share capital x historical rate"),
        Line("re_usd", "Retained earnings (USD)", M, history=[re0_usd],
             fc="{re_usd[-1]}+{ni_usd}" + ("-{div_usd}" if cfg["div"] else ""),
             desc="opening + translated net income" + (" - translated dividends" if cfg["div"] else "")),
        Line("cta", "Cumulative translation adjustment (CTA)", M, fc="{na_usd}-{cap_usd}-{re_usd}", hist="formula",
             desc="net assets - share capital - retained earnings (USD)"),
    ]
    if cfg["div"]:
        lines += [
            Line("cta_move", "CTA movement", M, fc="{cta}-{cta[-1]}", hist="blank", desc="closing - opening CTA",
                 section="CTA analysis"),
            Line("td_open", "Translation difference on opening net assets", M, fc="{na_lc[-1]}*({close}-{close[-1]})",
                 hist="blank", desc="opening LC net assets x (closing rate - prior closing rate)"),
            Line("td_inc", "Translation difference on net income", M, fc="{ni_lc}*({close}-{avg})", hist="blank",
                 desc="LC net income x (closing rate - average rate)"),
            Line("td_div", "Translation difference on dividends", M, fc="{div_lc}*({close}-{divr})", hist="blank",
                 desc="LC dividends x (closing rate - payment-date rate)"),
        ]
    if cfg["consol"]:
        inv = ("{$own}*" if cfg["nci"] else "") + "{$cap_lc}*{$hist_rate}"
        lines += [
            Line("p_inv", "Parent investment in the subsidiary (at cost)", M, fc=inv, hist="formula",
                 desc=("ownership x " if cfg["nci"] else "") + "LC share capital x historical rate",
                 section="Parent and consolidation (USD)"),
            Line("p_eq", "Parent standalone equity", M,
                 fc="{p_cash}+{p_oth}+{p_inv}" + ("+{$loan_usd}" if cfg["loan"] else "") + "-{p_liab}",
                 hist="formula", desc="parent cash + other assets + investment" + (
                     " + loan receivable" if cfg["loan"] else "") + " - liabilities"),
            Line("c_assets", "Consolidated total assets", M, fc="{p_cash}+{p_oth}+{cash_usd}+{ppe_usd}",
                 hist="formula", desc="parent cash and other assets + subsidiary cash and PP&E (USD)"),
            Line("c_liab", "Consolidated liabilities", M, fc="{p_liab}+{liab_usd}", hist="formula",
                 desc="parent + subsidiary third-party liabilities"),
        ]
        if cfg["nci"]:
            lines += [
                Line("nci", "Non-controlling interest", M, fc="(1-{$own})*{na_usd}", hist="formula",
                     desc="(1 - ownership) x subsidiary net assets (USD)"),
                Line("nci_ni", "NCI share of net income", M, fc="(1-{$own})*{ni_usd}", hist="blank",
                     desc="(1 - ownership) x subsidiary net income (USD)"),
            ]
        lines.append(Line("c_eq", "Equity attributable to the parent", M,
                          fc="{p_eq}+" + ("{$own}*" if cfg["nci"] else "") + "({re_usd}+{cta})", hist="formula",
                          desc="parent standalone equity + " + ("ownership x " if cfg["nci"] else "")
                               + "(subsidiary USD retained earnings + CTA)"))
    calcs = [Calc("cta_end", "CTA at the end of the projection", M, "{cta@last}", section="Results",
                  desc="final-year CTA"),
             Calc("ni_total", "Cumulative net income (USD)", M, "SUM({ni_usd@fc})", desc="sum of translated net income")]
    if cfg["consol"]:
        calcs.append(Calc("c_eq_end", "Equity attributable to the parent at the end", M, "{c_eq@last}",
                          desc="final-year equity attributable to the parent"))
    spec = ModelSpec(title="FX translation and consolidation", periods=periods, n_hist=1, sheets=[A, M],
                     scalars=scalars, lines=lines, calcs=calcs)

    # ---------------- term sheet -------------------------------------------------
    ts = [f"The subsidiary reports in {lc}; the group reports in USD. All rates are USD per 1 {lc}. The first column "
          "is the opening balance sheet date.",
          "SUBSIDIARY (" + lc + "): net income = revenue - operating expenses" + (
              " - FX loss on the intercompany loan" if cfg["loan"] else "") + "; retained earnings = opening + net "
          "income" + (" - dividends" if cfg["div"] else "") + "; net assets = share capital + retained earnings; cash "
          "and other net current assets is the balancing item (net assets + third-party liabilities" + (
              " + intercompany loan" if cfg["loan"] else "") + " - PP&E).",
          "TRANSLATION (current-rate method): income and expenses at the year's AVERAGE rate; assets and liabilities "
          "at the CLOSING rate; share capital at the HISTORICAL rate; retained earnings (USD) = opening USD retained "
          "earnings + translated net income" + (" - dividends translated at the spot rate on the payment date"
                                                if cfg["div"] else "") + ". CTA = translated net assets - share "
          "capital (USD) - retained earnings (USD), in every column including the opening one."]
    if cfg["div"]:
        ts.append("CTA ANALYSIS (each projection year): translation difference on opening net assets = opening LC "
                  "net assets x (closing rate - prior closing rate); on net income = LC net income x (closing rate - "
                  "average rate); on dividends = LC dividends x (closing rate - payment-date rate). CTA movement = "
                  "the first two minus the third.")
    if cfg["loan"]:
        ts.append(f"INTERCOMPANY LOAN: the parent lent a fixed USD principal (no repayments) to the subsidiary. The "
                  f"subsidiary carries it in {lc} at USD principal / closing rate, remeasured every year end; the "
                  f"change in that carrying amount (closing - opening) is an FX loss (a gain when negative) in its "
                  f"{lc} income statement. Translated, the loan payable is the LC carrying amount x closing rate.")
    if cfg["consol"]:
        ts.append("CONSOLIDATION. The parent formed the subsidiary" + (" together with a minority investor" if
                  cfg["nci"] else "") + "; all subsidiary retained earnings arose after formation. Parent investment "
                  "at cost = " + ("ownership x " if cfg["nci"] else "") + "subsidiary share capital (USD). Parent "
                  "standalone equity = parent cash + other assets + investment" + (
                      " + loan receivable (the USD principal)" if cfg["loan"] else "") + " - parent liabilities. "
                  "Consolidated total assets = parent cash and other assets + subsidiary cash and other net current "
                  "assets + subsidiary PP&E (all USD): the investment" + (
                      " and the intercompany loan are" if cfg["loan"] else " is") + " eliminated. Consolidated "
                  "liabilities = parent liabilities + subsidiary third-party liabilities. Equity attributable to the "
                  "parent = parent standalone equity + " + ("ownership x " if cfg["nci"] else "")
                  + "(subsidiary USD retained earnings + CTA).")
    if cfg["nci"]:
        ts.append("NON-CONTROLLING INTEREST = (1 - ownership) x subsidiary net assets (USD); NCI share of net income "
                  "= (1 - ownership) x subsidiary net income (USD).")
    conventions = [f"Amounts in {lc} millions on the subsidiary lines, USD millions elsewhere.",
                   "The opening column holds balances only (no flows)."]

    ids = [IdSpec("re_usd_rollforward", "USD retained earnings roll-forward",
                  [(1, "re_usd", 0), (-1, "re_usd", -1), (-1, "ni_usd", 0)]
                  + ([(1, "div_usd", 0)] if cfg["div"] else []))]
    if cfg["div"]:
        ids.append(IdSpec("cta_movement_explained", "CTA movement = translation differences",
                          [(1, "cta_move", 0), (-1, "td_open", 0), (-1, "td_inc", 0), (1, "td_div", 0)]))
    if cfg["consol"]:
        ids.append(IdSpec("consolidated_bs_balances", "consolidated assets = liabilities + parent equity"
                          + (" + NCI" if cfg["nci"] else ""),
                          [(1, "c_assets", 0), (-1, "c_liab", 0), (-1, "c_eq", 0)]
                          + ([(-1, "nci", 0)] if cfg["nci"] else [])))
    mono = [MonoSpec("cta_falls_with_historical_rate", "cta_end", "hist_rate", round(hist_rate * 0.05, 9), -1)]
    outputs = [("ni_usd", "Net income (USD)"), ("na_usd", "Net assets (USD)"), ("re_usd", "Retained earnings (USD)"),
               ("cta", "CTA")]
    if cfg["div"]:
        outputs += [("div_usd", "Dividends (USD)"), ("cta_move", "CTA movement"),
                    ("td_open", "Translation difference on opening net assets"),
                    ("td_inc", "Translation difference on net income"),
                    ("td_div", "Translation difference on dividends")]
    if cfg["loan"]:
        outputs.append(("fx_loss", f"FX loss/(gain) on the intercompany loan ({lc})"))
    if cfg["consol"]:
        outputs += [("c_assets", "Consolidated total assets"), ("c_liab", "Consolidated liabilities"),
                    ("c_eq", "Equity attributable to the parent")]
    if cfg["nci"]:
        outputs.append(("nci", "Non-controlling interest"))
    outputs.append(("cta_end", "CTA at the end of the projection"))
    rate = ("count", 1e-9, None)
    kinds = {"close": rate, "avg": rate, "divr": rate, "hist_rate": rate, "own": ("rate", 0.3, 1.0)}
    return Bundle(domain=DOMAIN, noun="foreign-currency translation and consolidation model", spec=spec,
                  term_sheet="\n".join(ts), conventions=conventions, identities=ids, monotone=mono, kinds=kinds,
                  outputs=outputs, scale=40.0 * k_lc, level=level, meta={"currency": lc})
