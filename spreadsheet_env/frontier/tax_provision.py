"""Corporate income-tax provision: current and deferred tax with carryforwards.

The mechanics are stated as term-sheet rules, not as any one country's law,
but each has a real counterpart: capital-allowance pools written down on a
reducing balance (UK main pool), a capped first-year allowance with a
dollar-for-dollar phase-out (US s.179 / UK AIA), an interest limitation at a
share of adjusted taxable income with indefinite carryforward (US s.163(j),
EU ATAD art. 4), loss carryforwards usable against a share of income (US
post-2017 NOLs, 80%), older losses with no limit but an expiry date, and a
valuation allowance driven by the cumulative-loss test (ASC 740).

1. tax pool and writing-down allowance, book NBV, current tax, deferred tax
   liability on fixed assets, total tax expense, statutory rate reconciliation.
2. + loss carryforwards: new losses add to the pool, usage limited to a share
   of taxable income; deferred tax asset on the losses.
3. + interest limitation: deductible interest = MIN(interest + carryforward,
   cap % x adjusted taxable income (ATI)); disallowed interest carries forward.
4. + first-year allowance with an annual cap that phases out dollar-for-dollar
   above an additions threshold; legacy losses (no % limit, used first) that
   expire at the end of a given year (the expiry is a permanent tax cost).
5. + ATI adds back tax depreciation only in flagged years; valuation allowance
   against the net deferred tax asset when the three-year cumulative book
   pre-tax result is a loss.

The statutory-rate reconciliation is a reference-free identity: with only
temporary differences, tax expense = rate x book pre-tax income + rate x
expired legacy losses + change in valuation allowance, whatever the
carryforward state.
"""

from __future__ import annotations

import random
from typing import List

from ..model.spec import Calc, Line, ModelSpec, Scalar
from .framework import Bundle, IdSpec, MonoSpec

DOMAIN = "tax"

LEVELS = {
    1: dict(n=6, nol=False, intlim=False, fya=False, legacy=False, va=False),
    2: dict(n=6, nol=True, intlim=False, fya=False, legacy=False, va=False),
    3: dict(n=7, nol=True, intlim=True, fya=False, legacy=False, va=False),
    4: dict(n=7, nol=True, intlim=True, fya=True, legacy=True, va=False),
    5: dict(n=8, nol=True, intlim=True, fya=True, legacy=True, va=True),
}


def generate(rng: random.Random, level: int) -> Bundle:
    cfg = LEVELS[level]
    u = rng.uniform
    n = cfg["n"]
    y0 = rng.randint(2023, 2026)
    periods = [f"FY{y0} (opening)"] + [f"FY{y0 + i + 1}" for i in range(n)]
    s = u(0.6, 2.0)  # company size
    ebitda, x = [], u(90, 160) * s
    dip = rng.randrange(1, n - 1)  # one downturn year, where losses and the interest cap tend to bite
    for i in range(n):
        x *= u(0.97, 1.09)
        ebitda.append(round(x * (u(0.25, 0.55) if i == dip else 1.0), 1))
    interest = [round(u(0.16, 0.30) * ebitda[0] * u(0.9, 1.1), 1) for _ in range(n)]
    capex = [round(u(0.25, 0.5) * e if i != dip else u(0.1, 0.2) * ebitda[0], 1) for i, e in enumerate(ebitda)]
    book_dep = [round(c * u(0.7, 1.0) + u(5, 12) * s, 1) for c in capex]
    book0 = round(u(250, 400) * s, 1)
    pool0 = round(book0 * u(0.55, 0.8), 1)

    A, M = "Assumptions", "Model"
    scalars = [Scalar("rate", "Tax rate", rng.choice([0.21, 0.25, 0.27, 0.30]), "%", "rate"),
               Scalar("wda", "Writing-down allowance on the tax pool (reducing balance)", rng.choice([0.18, 0.20, 0.25]),
                      "%", "rate")]
    if cfg["nol"]:
        scalars.append(Scalar("nol_lim", "Loss carryforward usable against this share of taxable income", 0.8, "%",
                              "rate"))
    if cfg["intlim"]:
        scalars.append(Scalar("int_lim", "Interest limitation: cap as a share of ATI", 0.3, "%", "rate"))
    if cfg["fya"]:
        cap = round(u(0.25, 0.45) * capex[0], 1)
        scalars += [Scalar("fy_cap", "First-year allowance: annual cap", cap, "$m", "money"),
                    Scalar("fy_thr", "First-year allowance: phase-out threshold (additions)",
                           round(capex[0] * u(0.75, 1.05), 1), "$m", "money")]
    if cfg["legacy"]:
        scalars.append(Scalar("leg_exp", "Legacy losses expire at the end of projection year", float(rng.randint(3, n - 2)),
                              "yr", "fixed"))
    if cfg["va"]:
        scalars.append(Scalar("pbt_m2", "Book pre-tax income two years before the opening year",
                              round(u(0.2, 0.5) * ebitda[0], 1), "$m", "money"))

    lines: List[Line] = [
        Line("ebitda", "EBITDA (book = tax)", A, hist="blank", forecast=ebitda),
        Line("interest", "Net interest expense", A, hist="blank", forecast=interest),
        Line("capex", "Capital additions (qualifying for allowances)", A, hist="blank", forecast=capex),
        Line("book_dep", "Book depreciation (fixed-asset register)", A, hist="blank", forecast=book_dep),
    ]
    if cfg["va"]:
        flags = [1.0 if rng.random() < 0.6 else 0.0 for _ in range(n)]
        flags[0] = 0.0
        flags[-1] = 1.0
        lines.append(Line("ati_flag", "ATI adds back tax depreciation (1 = yes, 0 = no)", A, unit="1/0", kind="ratio",
                          hist="blank", forecast=flags))

    # ---------------- model -------------------------------------------------------
    if cfg["legacy"]:
        lines.append(Line("year", "Projection year", M, unit="#", kind="ratio", history=[0.0], fc="{year[-1]}+1",
                          section="Timeline"))
    add = "{capex}"
    if cfg["fya"]:
        lines.append(Line("fya", "First-year allowance", M,
                          fc="MIN({capex},MAX(0,{$fy_cap}-MAX(0,{capex}-{$fy_thr})))", hist="blank",
                          desc="MIN(additions, MAX(0, cap - MAX(0, additions - threshold)))",
                          section="Capital allowances"))
        add = "{capex}-{fya}"
    lines += [
        Line("wda_amt", "Writing-down allowance", M, fc="{$wda}*({pool[-1]}+" + add + ")", hist="blank",
             desc="WDA % x (opening pool + additions" + (" not given first-year allowance" if cfg["fya"] else "") + ")",
             section="" if cfg["fya"] else "Capital allowances"),
        Line("pool", "Tax pool (written-down value) - closing", M, history=[pool0],
             fc="{pool[-1]}+" + add + "-{wda_amt}", desc="opening + additions - allowances"),
        Line("tax_dep", "Total capital allowances", M, fc=("{fya}+" if cfg["fya"] else "") + "{wda_amt}",
             hist="blank", desc=("first-year allowance + " if cfg["fya"] else "") + "writing-down allowance"),
        Line("book_nbv", "Book net book value - closing", M, history=[book0], fc="{book_nbv[-1]}+{capex}-{book_dep}",
             desc="opening + additions - book depreciation"),
    ]
    if cfg["intlim"]:
        ati = "{ebitda}" if not cfg["va"] else "{ebitda}-(1-{ati_flag})*{tax_dep}"
        lines += [
            Line("ati", "Adjusted taxable income (ATI)", M, fc=ati, hist="blank",
                 desc="EBITDA" + (" - tax depreciation in years without the add-back" if cfg["va"] else ""),
                 section="Interest limitation"),
            Line("int_ded", "Deductible interest", M, fc="MIN({interest}+{int_cf[-1]},{$int_lim}*MAX(0,{ati}))",
                 hist="blank", desc="MIN(interest + carried-forward interest, cap % x MAX(0, ATI))"),
            Line("int_cf", "Disallowed interest carried forward - closing", M,
                 history=[round(u(0.0, 0.25) * interest[0], 1) if rng.random() < 0.7 else 0.0],
                 fc="{int_cf[-1]}+{interest}-{int_ded}", desc="opening + interest - deductible interest"),
        ]
    ti = "{ebitda}-{tax_dep}-" + ("{int_ded}" if cfg["intlim"] else "{interest}")
    lines.append(Line("ti_pre", "Taxable income before loss relief", M, fc=ti, hist="blank",
                      desc="EBITDA - capital allowances - " + ("deductible interest" if cfg["intlim"] else "interest"),
                      section="Taxable income"))
    used = []
    if cfg["legacy"]:
        lines += [
            Line("leg_use", "Legacy losses used", M, fc="MIN({legacy[-1]},MAX(0,{ti_pre}))", hist="blank",
                 desc="MIN(opening legacy losses, MAX(0, taxable income before loss relief))"),
            Line("leg_expd", "Legacy losses expired", M, fc="IF({year}={$leg_exp},{legacy[-1]}-{leg_use},0)",
                 hist="blank", desc="what is left at the end of the expiry year"),
            Line("legacy", "Legacy losses - closing", M, history=[round(u(0.2, 0.5) * ebitda[0], 1)],
                 fc="{legacy[-1]}-{leg_use}-{leg_expd}", desc="opening - used - expired"),
        ]
        used.append("{leg_use}")
    if cfg["nol"]:
        after_leg = "{ti_pre}" + ("-{leg_use}" if cfg["legacy"] else "")
        lines += [
            Line("nol_use", "Loss carryforward used", M, fc="MIN({nol[-1]},{$nol_lim}*MAX(0," + after_leg + "))",
                 hist="blank", desc="MIN(opening losses, limit % x MAX(0, taxable income after legacy losses))"
                 if cfg["legacy"] else "MIN(opening losses, limit % x MAX(0, taxable income before loss relief))"),
            Line("nol_add", "New tax losses", M, fc="MAX(0,-{ti_pre})", hist="blank",
                 desc="MAX(0, -taxable income before loss relief)"),
            Line("nol", "Loss carryforward - closing", M, history=[round(u(0.3, 0.9) * ebitda[0], 1)],
                 fc="{nol[-1]}+{nol_add}-{nol_use}", desc="opening + new losses - used"),
        ]
        used.append("{nol_use}")
    lines += [
        Line("taxable", "Taxable income", M, fc="MAX(0,{ti_pre}" + "".join("-" + x for x in used) + ")", hist="blank",
             desc="MAX(0, taxable income before loss relief" + (" - losses used" if used else "") + ")"),
        Line("cur_tax", "Current tax", M, fc="{$rate}*{taxable}", hist="blank", desc="rate x taxable income"),
        Line("dtl", "Deferred tax liability on fixed assets", M, fc="{$rate}*({book_nbv}-{pool})", hist="formula",
             desc="rate x (book NBV - tax pool)", section="Deferred tax"),
    ]
    dta_terms = (["{nol}"] if cfg["nol"] else []) + (["{legacy}"] if cfg["legacy"] else []) + (
        ["{int_cf}"] if cfg["intlim"] else [])
    net = "{dtl}"
    if dta_terms:
        lines.append(Line("dta", "Deferred tax asset on carryforwards", M, fc="{$rate}*(" + "+".join(dta_terms) + ")",
                          hist="formula", desc="rate x (" + " + ".join(t.strip("{}") for t in dta_terms) + ")"))
        net += "-{dta}"
    lines.append(Line("pbt", "Book pre-tax income", M, fc="{ebitda}-{book_dep}-{interest}",
                      history=[round(u(0.3, 0.6) * ebitda[0], 1)] if cfg["va"] else None,
                      hist="input" if cfg["va"] else "blank", desc="EBITDA - book depreciation - interest"))
    if cfg["va"]:
        lines += [
            Line("pbt2", "Book pre-tax income, current + prior year", M, fc="{pbt}+{pbt[-1]}", hist="formula",
                 hist_fc="{pbt}+{$pbt_m2}", desc="this year + last year"),
            Line("cum3", "Three-year cumulative book pre-tax income", M, fc="{pbt}+{pbt2[-1]}", hist="blank",
                 desc="this year + the two prior years"),
            Line("va", "Valuation allowance", M, history=[0.0], fc="IF({cum3}<0,MAX(0,{dta}-MAX(0,{dtl})),0)",
                 desc="if the three-year cumulative result is a loss: MAX(0, DTA - MAX(0, DTL)); otherwise 0"),
        ]
        net += "+{va}"
    lines += [
        Line("net_dt", "Net deferred tax liability", M, fc=net, hist="formula",
             desc="DTL" + (" - DTA" if dta_terms else "") + (" + valuation allowance" if cfg["va"] else "")),
        Line("def_tax", "Deferred tax expense/(credit)", M, fc="{net_dt}-{net_dt[-1]}", hist="blank",
             desc="change in net deferred tax liability"),
        Line("tax_exp", "Total tax expense", M, fc="{cur_tax}+{def_tax}", hist="blank", desc="current + deferred"),
        Line("stat_tax", "Tax at the statutory rate", M, fc="{$rate}*{pbt}", hist="blank", desc="rate x book pre-tax income",
             section="Rate reconciliation"),
    ]
    rec = [(1, "tax_exp", 0), (-1, "stat_tax", 0)]
    if not cfg["nol"]:
        lines += [
            Line("lost", "Tax losses not relieved", M, fc="MAX(0,-{ti_pre})", hist="blank",
                 desc="MAX(0, -taxable income before loss relief)"),
            Line("rec_lost", "Effect of unrelieved tax losses", M, fc="{$rate}*{lost}", hist="blank",
                 desc="rate x tax losses not relieved"),
        ]
        rec.append((-1, "rec_lost", 0))
    if cfg["legacy"]:
        lines.append(Line("rec_exp", "Effect of expired legacy losses", M, fc="{$rate}*{leg_expd}", hist="blank",
                          desc="rate x legacy losses expired"))
        rec.append((-1, "rec_exp", 0))
    if cfg["va"]:
        lines.append(Line("rec_va", "Change in valuation allowance", M, fc="{va}-{va[-1]}", hist="blank",
                          desc="closing - opening valuation allowance"))
        rec.append((-1, "rec_va", 0))
    calcs = [Calc("cash_tax_total", "Total current tax", M, "SUM({cur_tax@fc})", section="Results",
                  desc="sum of current tax"),
             Calc("tax_total", "Total tax expense", M, "SUM({tax_exp@fc})", desc="sum of total tax expense"),
             Calc("pbt_total", "Total book pre-tax income", M, "SUM({pbt@fc})", desc="sum of book pre-tax income"),
             Calc("etr", "Effective tax rate over the projection", M, "IF({pbt_total}>0,{tax_total}/{pbt_total},0)",
                  unit="%", kind="ratio", desc="total tax expense / total pre-tax income (0 if that is not positive)")]
    spec = ModelSpec(title="Corporate tax provision", periods=periods, n_hist=1, sheets=[A, M], scalars=scalars,
                     lines=lines, calcs=calcs)

    # ---------------- term sheet ------------------------------------------------------
    fya_txt = ""
    if cfg["fya"]:
        fya_txt = (" A FIRST-YEAR ALLOWANCE deducts additions immediately up to an annual cap; the cap is reduced "
                   "dollar-for-dollar by additions above the phase-out threshold (never below zero) and the allowance "
                   "cannot exceed the additions. Additions not given the first-year allowance join the pool.")
    ts = ["CAPITAL ALLOWANCES. The tax pool is written down on a reducing balance: writing-down allowance = WDA % x "
          "(opening pool + additions" + (" not given the first-year allowance" if cfg["fya"] else "") + "); closing "
          "pool = opening + those additions - writing-down allowance." + fya_txt + " Total capital allowances = "
          + ("first-year allowance + " if cfg["fya"] else "") + "writing-down allowance. Book NBV = opening + "
          "additions - book depreciation."]
    if cfg["intlim"]:
        ts.append("INTEREST LIMITATION. ATI = EBITDA" + (
            " in years where the add-back flag is 1; EBITDA - total capital allowances where it is 0" if cfg["va"]
            else "") + ". Deductible interest = the smaller of (this year's interest + disallowed interest carried "
            "forward) and cap % x ATI (zero if ATI is negative). Disallowed interest carries forward indefinitely: "
            "closing = opening + interest - deductible interest.")
    ts.append("TAXABLE INCOME before loss relief = EBITDA - total capital allowances - " + (
        "deductible interest" if cfg["intlim"] else "interest") + " (negative = a tax loss).")
    if cfg["legacy"]:
        ts.append("LEGACY LOSSES are used first, against all of the positive taxable income before loss relief (no % "
                  "limit). Whatever is left at the end of the expiry year (projection year number on Assumptions; "
                  "the opening column is year 0) expires and is lost.")
    if cfg["nol"]:
        ts.append("LOSS CARRYFORWARD. Usage = the smaller of the opening carryforward and limit % x positive taxable "
                  "income " + ("after legacy losses" if cfg["legacy"] else "before loss relief") + ". A tax loss "
                  "adds to the carryforward (never to the legacy pool). Closing = opening + new losses - used.")
    ts.append("Taxable income = MAX(0, taxable income before loss relief" + (" - losses used" if used else "")
              + "); current tax = rate x taxable income.")
    ts.append("DEFERRED TAX. DTL on fixed assets = rate x (book NBV - tax pool)" + (
        "; DTA on carryforwards = rate x (" + " + ".join(
            {"{nol}": "loss carryforward", "{legacy}": "legacy losses", "{int_cf}": "disallowed interest"}[t]
            for t in dta_terms) + ")" if dta_terms else "") + (
        ". VALUATION ALLOWANCE: when book pre-tax income summed over the current and two prior years is negative, "
        "a valuation allowance = MAX(0, DTA - MAX(0, DTL)) is held; otherwise none" if cfg["va"] else "")
        + ". Net deferred tax liability = DTL" + (" - DTA" if dta_terms else "") + (
        " + valuation allowance" if cfg["va"] else "") + ", in every column including the opening one. Deferred tax "
        "expense = change in the net deferred tax liability; total tax expense = current + deferred.")
    ts.append("Book pre-tax income = EBITDA - book depreciation - interest. RATE RECONCILIATION: tax at the "
              "statutory rate = rate x book pre-tax income" + (
                  "; effect of unrelieved tax losses = rate x MAX(0, -taxable income before loss relief), since "
                  "losses cannot be carried forward" if not cfg["nol"] else "") + (
                  "; effect of expired legacy losses = rate x losses expired" if cfg["legacy"] else "") + (
                  "; change in valuation allowance = closing - opening" if cfg["va"] else "") + ".")
    ts.append("RESULTS: effective tax rate = total tax expense / total book pre-tax income over the projection "
              "(0 if that total is not positive).")
    conventions = ["The opening column holds balances only (no flows).", "All amounts in $m."]
    if cfg["va"]:
        conventions.append("The opening column of book pre-tax income is last year's actual result.")

    ids = [IdSpec("rate_reconciliation", "tax expense = statutory tax + reconciling items", rec)]
    ids.append(IdSpec("pool_rollforward", "tax pool roll-forward",
                      [(1, "pool", 0), (-1, "pool", -1), (-1, "capex", 0), (1, "tax_dep", 0)]))
    if cfg["nol"]:
        ids.append(IdSpec("loss_rollforward", "loss carryforward roll-forward",
                          [(1, "nol", 0), (-1, "nol", -1), (-1, "nol_add", 0), (1, "nol_use", 0)]))
    mono = [MonoSpec("cash_tax_falls_with_wda", "cash_tax_total", "wda", 0.02, -1),
            MonoSpec("cash_tax_rises_with_rate", "cash_tax_total", "rate", 0.02, 1)]
    if cfg["nol"]:
        mono.append(MonoSpec("cash_tax_falls_with_loss_limit", "cash_tax_total", "nol_lim", 0.05, -1))
    if cfg["intlim"]:
        mono.append(MonoSpec("cash_tax_falls_with_interest_cap", "cash_tax_total", "int_lim", 0.05, -1))
    outputs = [("tax_dep", "Total capital allowances"), ("taxable", "Taxable income"), ("cur_tax", "Current tax"),
               ("def_tax", "Deferred tax expense"), ("tax_exp", "Total tax expense"),
               ("net_dt", "Net deferred tax liability")]
    if cfg["intlim"]:
        outputs += [("int_ded", "Deductible interest"), ("int_cf", "Disallowed interest carried forward")]
    if cfg["nol"]:
        outputs.append(("nol", "Loss carryforward - closing"))
    if cfg["legacy"]:
        outputs.append(("legacy", "Legacy losses - closing"))
    if cfg["va"]:
        outputs.append(("va", "Valuation allowance"))
    outputs.append(("stat_tax", "Tax at the statutory rate"))
    outputs += [(t[1], {"rec_lost": "Effect of unrelieved tax losses", "rec_exp": "Effect of expired legacy losses",
                        "rec_va": "Change in valuation allowance"}[t[1]]) for t in rec[2:]]
    outputs += [("cash_tax_total", "Total current tax"), ("etr", "Effective tax rate")]
    kinds = {"rate": ("tax", 0.05, 0.5), "wda": ("rate", 0.05, 0.5), "nol_lim": ("rate", 0.5, 1.0),
             "int_lim": ("rate", 0.1, 0.5), "ati_flag": ("fixed", None, None)}
    return Bundle(domain=DOMAIN, noun="corporate tax provision model", spec=spec, term_sheet="\n".join(ts),
                  conventions=conventions, identities=ids, monotone=mono, kinds=kinds, outputs=outputs,
                  scale=100.0 * s, level=level)
