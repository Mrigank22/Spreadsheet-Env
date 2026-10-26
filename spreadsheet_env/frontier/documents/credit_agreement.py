"""Leveraged-loan model specified by a CREDIT AGREEMENT (document-grade spec).

The agent receives a generated credit agreement (defined terms in alphabetical
order, cross-referenced sections, provisos, distractor clauses) instead of a
formula-level term sheet, and must build the borrower's annual debt model from it.
Every operative clause is generated next to the formula it encodes.

Levels (each adds to the previous one):

1. Term Loans: interest at Adjusted Term SOFR (SOFR floored) + a fixed margin;
   1% installments of the Closing Date amount; an Excess Cash Flow sweep paid in
   the FOLLOWING Fiscal Year (commencing with the first full Fiscal Year) and
   applied to the maturity balloon (installments unchanged).
2. + pricing grid on the First Lien Net Leverage Ratio of the most recent year
   for which financial statements were delivered (Level I until the first full
   year's statements); Applicable ECF Percentage stepping down with year-end
   leverage; ECF prepayments applied to later installments in direct order of
   maturity (a carried-forward prepayment credit).
3. + Revolving Loans (minimum-liquidity draw/repay rule, commitment fee grid),
   Senior Notes (in total but not first-lien leverage), Consolidated EBITDA
   with a capped cost-savings add-back (ratios only; ECF uses unadjusted
   EBITDA), and a greater-of limit on the cash netted against debt.
4. + HoldCo PIK notes (outside the credit group: not debt of the Borrower, not
   in interest or taxes, but in the sponsor's exit equity), a maintenance
   Total Net Leverage covenant with an EBITDA equity cure whose cash is
   disregarded for every ratio of that year, sponsor returns.
5. + springing test (only when the revolver is drawn above a threshold), cure
   limits (two in total, none in consecutive years), a covenant-default flag,
   and IRR of the sponsor's cash flows.
"""

from __future__ import annotations

import random
from typing import List

from ...model.spec import Calc, Line, ModelSpec, Scalar
from ..framework import Bundle, IdSpec, MonoSpec
from .legal import LegalDoc, company_name

DOMAIN = "ca"

LEVELS = {
    1: dict(grid=False, credit=False, revolver=False, n=6),
    2: dict(grid=True, credit=True, revolver=False, n=6),
    3: dict(grid=True, credit=True, revolver=True, n=7),
    4: dict(grid=True, credit=True, revolver=True, holdco=True, cov=True, n=7),
    5: dict(grid=True, credit=True, revolver=True, holdco=True, cov=True, spring=True, n=7),
}

# Schedule 1 captions (= Assumptions sheet labels); the agreement refers to inputs by caption
CAP = {
    "tl_amt": "Closing Date Term Loans",
    "floor": "Term SOFR Floor",
    "margin": "Applicable Margin",
    "margin3": "Applicable Margin - Pricing Level III",
    "margin2": "Applicable Margin - Pricing Level II",
    "margin1": "Applicable Margin - Pricing Level I",
    "pg_t2": "Pricing Level II Threshold",
    "pg_t1": "Pricing Level I Threshold",
    "amort_pct": "Installment Percentage",
    "ecf_pct": "ECF Percentage",
    "ecf_mid": "ECF Percentage - Level 2",
    "ecf_hi": "ECF Percentage - Level 1",
    "ecf_t2": "ECF Level 2 Ratio",
    "ecf_t1": "ECF Level 1 Ratio",
    "tax_rate": "Tax Rate",
    "da_pct": "D&A (% of revenue)",
    "capex_pct": "Capital Expenditures (% of revenue)",
    "nwc_pct": "Consolidated Working Capital (% of revenue)",
    "open_cash": "Closing Date Cash",
    "min_cash": "Minimum Liquidity Amount",
    "rev_commit": "Revolving Commitments",
    "fee_lo": "Commitment Fee Rate - Lower",
    "fee_hi": "Commitment Fee Rate - Higher",
    "fee_t": "Commitment Fee Step-Down Ratio",
    "notes_amt": "Senior Notes",
    "notes_cpn": "Senior Notes Coupon",
    "cs_cap": "Cost Savings Cap",
    "net_fixed": "Netting Limit - Fixed Amount",
    "net_pct": "Netting Limit - Percentage",
    "hold_amt": "HoldCo Notes",
    "hold_rate": "HoldCo PIK Rate",
    "spring_pct": "Springing Threshold",
    "entry_mult": "Entry Multiple",
    "fee_pct": "Transaction Costs (% of Enterprise Value)",
    "exit_mult": "Exit Multiple",
    # per-year series
    "sofr": "Term SOFR",
    "g_rev": "Revenue growth",
    "margin_e": "EBITDA margin",
    "savings": "Pro Forma Cost Savings",
    "cov_max": "Maximum Total Net Leverage Ratio",
}


def q(key: str) -> str:
    """Quote a Schedule 1 caption."""
    return f"\"{CAP[key]}\""


def amt(key: str) -> str:
    """An amount defined by reference to its Schedule 1 caption."""
    return f"the amount set forth opposite {q(key)} in Schedule 1"


def _r(x: float, step: float) -> float:
    return round(round(x / step) * step, 6)


def generate(rng: random.Random, level: int) -> Bundle:
    cfg = LEVELS[level]
    u = rng.uniform
    n = cfg["n"]
    grid, credit, revolver = cfg["grid"], cfg["credit"], cfg["revolver"]
    holdco, cov, spring = cfg.get("holdco", False), cfg.get("cov", False), cfg.get("spring", False)
    y0 = rng.randint(2024, 2026)
    periods = [f"FY{y0} (Closing)"] + [f"FY{y0 + i + 1}" for i in range(n)]
    ebitda0 = round(10 ** u(1.6, 2.6), 1)
    margin0 = u(0.14, 0.30)
    rev0 = round(ebitda0 / margin0, 1)
    g_near = u(0.03, 0.09)
    growth = [round(g_near + (0.025 - g_near) * i / max(1, n - 1) + rng.gauss(0, 0.006), 4) for i in range(n)]
    margins = [round(min(0.42, max(0.08, margin0 + u(-0.004, 0.010) * (i + 1))), 4) for i in range(n)]
    tl_amt = round(ebitda0 * u(3.6, 4.6), 1)
    notes_amt = round(ebitda0 * u(1.0, 1.5), 1) if revolver else 0.0
    hold_amt = round(ebitda0 * u(0.6, 1.0), 1) if holdco else 0.0
    s0 = u(0.030, 0.045)
    sofr = [round(max(0.004, s0 + i * u(-0.005, 0.002) + rng.gauss(0, 0.002)), 4) for i in range(n)]
    floor = rng.choice([0.005, 0.0075, 0.01])
    min_cash = round(rev0 * u(0.02, 0.04), 1)
    company = company_name(rng)
    cs_cap = rng.choice([0.15, 0.2, 0.25]) if revolver else 0.0
    sv0 = u(0.10, 0.30) if revolver else 0.0
    # grid thresholds are anchored to the closing First Lien Net Leverage Ratio (net of cash, over
    # Consolidated EBITDA), so the base case starts in the top tiers and steps down as it delevers
    fl_net0 = (tl_amt - min_cash) / (ebitda0 * (1 + min(sv0, cs_cap)))

    A, M = "Assumptions", "Model"
    S = Scalar
    scalars: List[Scalar] = [S("tl_amt", CAP["tl_amt"], tl_amt, "$m", "money"),
                             S("floor", CAP["floor"], floor, "%", "rate")]
    asc: List[tuple] = []
    if grid:
        m1 = _r(u(0.0350, 0.0425), 0.0025)
        scalars += [S("margin3", CAP["margin3"], round(m1 - 0.005, 4), "%", "rate"),
                    S("margin2", CAP["margin2"], round(m1 - 0.0025, 4), "%", "rate"),
                    S("margin1", CAP["margin1"], m1, "%", "rate")]
        t1 = _r(fl_net0 - u(0.0, 0.4), 0.25)
        t2 = round(t1 - rng.choice([0.5, 0.75]), 2)
        scalars += [S("pg_t2", CAP["pg_t2"], t2, "x", "multiple"), S("pg_t1", CAP["pg_t1"], t1, "x", "multiple")]
        asc += [("margin3", "margin2", "margin1"), ("pg_t2", "pg_t1")]
    else:
        scalars.append(S("margin", CAP["margin"], _r(u(0.0300, 0.0425), 0.0025), "%", "rate"))
    scalars.append(S("amort_pct", CAP["amort_pct"], rng.choice([0.01, 0.01, 0.0125]), "%", "rate"))
    if grid:
        e1 = _r(fl_net0 - u(0.25, 0.6), 0.25)
        e2 = round(e1 - rng.choice([0.5, 0.75, 1.0]), 2)
        scalars += [S("ecf_mid", CAP["ecf_mid"], 0.25, "%", "rate"), S("ecf_hi", CAP["ecf_hi"], 0.5, "%", "rate"),
                    S("ecf_t2", CAP["ecf_t2"], e2, "x", "multiple"), S("ecf_t1", CAP["ecf_t1"], e1, "x", "multiple")]
        asc += [("ecf_mid", "ecf_hi"), ("ecf_t2", "ecf_t1")]
    else:
        scalars.append(S("ecf_pct", CAP["ecf_pct"], rng.choice([0.5, 0.75]), "%", "rate"))
    scalars += [S("tax_rate", CAP["tax_rate"], round(u(0.21, 0.27), 3), "%", "tax"),
                S("da_pct", CAP["da_pct"], round(u(0.02, 0.045), 4), "%", "rate"),
                S("capex_pct", CAP["capex_pct"], round(u(0.02, 0.05), 4), "%", "rate"),
                S("nwc_pct", CAP["nwc_pct"], round(u(0.06, 0.14), 4), "%", "rate")]
    if revolver:
        scalars += [S("min_cash", CAP["min_cash"], min_cash, "$m", "money"),
                    S("rev_commit", CAP["rev_commit"], round(ebitda0 * u(0.6, 1.0), 1), "$m", "money"),
                    S("fee_lo", CAP["fee_lo"], 0.00375, "%", "rate"), S("fee_hi", CAP["fee_hi"], 0.005, "%", "rate"),
                    S("fee_t", CAP["fee_t"], round(t2 + rng.choice([0.25, 0.5]), 2), "x", "multiple"),
                    S("notes_amt", CAP["notes_amt"], notes_amt, "$m", "money"),
                    S("notes_cpn", CAP["notes_cpn"], round(u(0.075, 0.095), 4), "%", "interest"),
                    S("cs_cap", CAP["cs_cap"], cs_cap, "%", "rate"),
                    S("net_fixed", CAP["net_fixed"], round(ebitda0 * u(0.15, 0.35), 1), "$m", "money"),
                    S("net_pct", CAP["net_pct"], rng.choice([0.25, 0.5]), "%", "rate")]
        asc.append(("fee_lo", "fee_hi"))
    else:
        scalars.append(S("open_cash", CAP["open_cash"], min_cash, "$m", "money"))
    if holdco:
        scalars += [S("hold_amt", CAP["hold_amt"], hold_amt, "$m", "money"),
                    S("hold_rate", CAP["hold_rate"], round(u(0.11, 0.14), 4), "%", "interest")]
    if spring:
        scalars.append(S("spring_pct", CAP["spring_pct"], rng.choice([0.35, 0.4]), "%", "rate"))
    if holdco:
        debt0 = tl_amt + notes_amt + hold_amt
        scalars += [S("entry_mult", CAP["entry_mult"], round(debt0 / ebitda0 + u(3.0, 5.0), 2), "x", "multiple"),
                    S("fee_pct", CAP["fee_pct"], round(u(0.015, 0.03), 4), "%", "rate")]
        scalars.append(S("exit_mult", CAP["exit_mult"], round(scalars[-2].value + u(-1.5, 1.0), 2), "x", "multiple"))

    # ------------------------------------------------------------------ model lines
    lines: List[Line] = [
        Line("sofr", CAP["sofr"], A, "%", fc=None, hist="blank", forecast=sofr, kind="rate"),
        Line("g_rev", CAP["g_rev"], A, "%", fc=None, hist="blank", forecast=growth, kind="rate"),
        Line("margin_e", CAP["margin_e"], A, "%", fc=None, hist="blank", forecast=margins, kind="rate"),
    ]
    if revolver:
        savings = [round(ebitda0 * sv0 * max(0.0, 1 - i / 3), 1) for i in range(n)]
        lines.append(Line("savings", CAP["savings"], A, fc=None, hist="blank", forecast=savings, kind="money"))
    if cov:
        tot0 = (tl_amt + notes_amt - min_cash) / ebitda0
        start = tot0 + u(1.1, 1.6)
        covs = [round(max(start - 0.4 * i, tot0 - 0.6), 2) for i in range(n)]
        lines.append(Line("cov_max", CAP["cov_max"], A, "x", fc=None, hist="blank", forecast=covs, kind="ratio"))

    E = "{cons_ebitda}" if revolver else "{ebitda}"  # the ratio denominator (Consolidated EBITDA)
    lines += [
        Line("rev", "Revenue", M, fc="{rev[-1]}*(1+{g_rev})", history=[rev0], section="Operations"),
        Line("ebitda", "EBITDA", M, fc="{rev}*{margin_e}", history=[ebitda0]),
        Line("da", "D&A", M, fc="{rev}*{$da_pct}", hist="blank"),
        Line("capex", "Capital Expenditures", M, fc="{rev}*{$capex_pct}", hist="blank"),
        Line("nwc", "Consolidated Working Capital", M, fc="{rev}*{$nwc_pct}",
             history=[round(rev0 * u(0.06, 0.14), 1)]),
        Line("d_nwc", "Increase in Consolidated Working Capital", M, fc="{nwc}-{nwc[-1]}", hist="blank"),
    ]
    if revolver:
        lines += [
            Line("cs_add", "Pro Forma Cost Savings added back", M, fc="MIN({savings},{$cs_cap}*{ebitda})",
                 hist="blank"),
            Line("cons_ebitda", "Consolidated EBITDA", M, fc="{ebitda}+{cs_add}", hist="blank"),
        ]
    lines.append(Line("adj_sofr", "Adjusted Term SOFR", M, "%", kind="ratio", fc="MAX({sofr},{$floor})",
                      hist="blank", section="Pricing"))
    if grid:
        lines.append(Line("app_rate", "Applicable Rate", M, "%", kind="ratio", hist="blank",
                          fc="IF({fl_lev[-1]}>{$pg_t1},{$margin1},IF({fl_lev[-1]}>{$pg_t2},{$margin2},{$margin3}))",
                          fc_first="{$margin1}"))
        rate = "({adj_sofr}+{app_rate})"
    else:
        rate = "({adj_sofr}+{$margin})"
    if revolver:
        lines.append(Line("fee_rate", "Applicable Commitment Fee Rate", M, "%", kind="ratio", hist="blank",
                          fc="IF({fl_lev[-1]}>{$fee_t},{$fee_hi},{$fee_lo})", fc_first="{$fee_hi}"))
    lines.append(Line("tl_int", "Interest on Term Loans", M, fc=f"{{tl_close[-1]}}*{rate}", hist="blank",
                      section="Interest and taxes"))
    int_terms = ["{tl_int}"]
    if revolver:
        lines += [
            Line("rev_int", "Interest on Revolving Loans", M, fc=f"{{rev_close[-1]}}*{rate}", hist="blank"),
            Line("cfee", "Commitment Fee", M, fc="({$rev_commit}-{rev_close[-1]})*{fee_rate}", hist="blank"),
            Line("notes_int", "Interest on Senior Notes", M, fc="{notes_close[-1]}*{$notes_cpn}", hist="blank"),
        ]
        int_terms += ["{rev_int}", "{cfee}", "{notes_int}"]
    lines += [
        Line("cash_int", "Consolidated Cash Interest Expense", M, fc="+".join(int_terms), hist="blank"),
        Line("tax", "Taxes paid in cash", M, fc="MAX(0,{ebitda}-{da}-{cash_int})*{$tax_rate}", hist="blank"),
    ]
    ecf_rate_prev = "{ecf_rate[-1]}" if grid else "{$ecf_pct}"
    lines.append(Line("ecf_pay", "Excess Cash Flow prepayment", M,
                      fc=f"MIN({{tl_close[-1]}},MAX(0,{{ecf[-1]}})*{ecf_rate_prev})", hist="blank",
                      section="Term Loans"))
    inst = "{$amort_pct}*{tl_close@0}"
    if credit:
        lines.append(Line("credit_used", "Prepayment credit applied to the installment", M,
                          fc=f"MIN({{credit[-1]}}+{{ecf_pay}},{inst})", hist="blank"))
        lines.append(Line("sched", "Scheduled installment paid", M,
                          fc=f"MIN({{tl_close[-1]}}-{{ecf_pay}},{inst}-{{credit_used}})", hist="blank"))
        lines.append(Line("credit", "Unapplied prepayment credit - closing", M,
                          fc="{credit[-1]}+{ecf_pay}-{credit_used}", history=[0.0]))
    else:
        lines.append(Line("sched", "Scheduled installment paid", M, fc=f"MIN({{tl_close[-1]}}-{{ecf_pay}},{inst})",
                          hist="blank"))
    lines.append(Line("tl_close", "Term Loans - closing balance", M, fc="{tl_close[-1]}-{ecf_pay}-{sched}",
                      hist="formula", hist_fc="{$tl_amt}"))
    lines.append(Line("ecf", "Excess Cash Flow", M, fc="{ebitda}-{cash_int}-{tax}-{capex}-{d_nwc}-{sched}",
                      hist="blank", section="Excess Cash Flow"))
    if grid:
        lines.append(Line("ecf_rate", "Applicable ECF Percentage", M, "%", kind="ratio", hist="blank",
                          fc="IF({fl_lev}>{$ecf_t1},{$ecf_hi},IF({fl_lev}>{$ecf_t2},{$ecf_mid},0))"))
    flow = "{cash[-1]}+{ebitda}-{cash_int}-{tax}-{capex}-{d_nwc}-{ecf_pay}-{sched}"
    if revolver:
        lines += [
            Line("cash_pre", "Cash before Revolving Loans", M, fc=flow, hist="blank", section="Revolver and cash"),
            Line("rev_close", "Revolving Loans - closing balance", M,
                 fc="MIN({$rev_commit},MAX(0,{rev_close[-1]}-({cash_pre}-{$min_cash})))", history=[0.0]),
            Line("rev_net", "Revolving Loans - borrowing/(repayment)", M, fc="{rev_close}-{rev_close[-1]}",
                 hist="blank"),
            Line("notes_close", "Senior Notes - closing balance", M, fc="{notes_close[-1]}", hist="formula",
                 hist_fc="{$notes_amt}"),
        ]
    if holdco:
        lines += [
            Line("hold_int", "HoldCo Notes - PIK interest", M, fc="{hold_close[-1]}*{$hold_rate}", hist="blank",
                 section="Holdings"),
            Line("hold_close", "HoldCo Notes - closing balance", M, fc="{hold_close[-1]}+{hold_int}",
                 hist="formula", hist_fc="{$hold_amt}"),
        ]
    # ratios and covenant
    if revolver:
        cash_ratio = "({cash_pre}+{rev_net})" if cov else "{cash}"
        lines.append(Line("net_cash", "Unrestricted Cash deducted (after the Netting Limit)", M, hist="blank",
                          fc=f"MAX(0,MIN({cash_ratio},MAX({{$net_fixed}},{{$net_pct}}*{{cons_ebitda}})))",
                          section="Financial ratios"))
        lines.append(Line("fl_lev", "First Lien Net Leverage Ratio", M, "x", kind="ratio", hist="blank",
                          fc=f"({{tl_close}}+{{rev_close}}-{{net_cash}})/{E}"))
        lines.append(Line("tot_lev", "Total Net Leverage Ratio (before any Cure Amount)", M, "x", kind="ratio",
                          hist="blank", fc=f"({{tl_close}}+{{rev_close}}+{{notes_close}}-{{net_cash}})/{E}"))
    elif grid:
        lines.append(Line("fl_lev", "First Lien Net Leverage Ratio", M, "x", kind="ratio", hist="blank",
                          fc=f"({{tl_close}}-MAX(0,{{cash}}))/{E}", section="Financial ratios"))
    cure_terms = ""
    if cov:
        need = f"MAX(0,({{tl_close}}+{{rev_close}}+{{notes_close}}-{{net_cash}})/{{cov_max}}-{E})"
        if spring:
            lines += [
                Line("cure_req", "Cure Amount required", M, hist="blank", section="Financial covenant",
                     fc=f"IF({{rev_close}}>{{$spring_pct}}*{{$rev_commit}},{need},0)"),
                Line("cure", "Cure Amount", M, hist="blank",
                     fc="IF(AND({cure_n[-1]}<2,{cure[-1]}=0),{cure_req},0)"),
                Line("cure_n", "Cure Amounts made to date (number)", M, unit="#", kind="ratio",
                     fc="{cure_n[-1]}+IF({cure}>0,1,0)", history=[0.0]),
                Line("cov_default", "Financial Covenant Default (1/0)", M, unit="flag", kind="ratio", hist="blank",
                     fc="IF(AND({cure_req}>0,{cure}=0),1,0)"),
            ]
        else:
            lines.append(Line("cure", "Cure Amount", M, fc=need, hist="blank", section="Financial covenant"))
        cure_terms = "+{cure}"
    if revolver:
        lines.append(Line("cash", "Unrestricted Cash - closing", M, fc="{cash_pre}+{rev_net}" + cure_terms,
                          hist="formula", hist_fc="{$min_cash}"))
    else:
        lines.append(Line("cash", "Unrestricted Cash - closing", M, fc=flow, hist="formula", hist_fc="{$open_cash}",
                          section="Cash"))
    calcs: List[Calc] = []
    if holdco:
        calcs += [
            Calc("entry_ev", "Enterprise Value at closing", M, "{ebitda@0}*{$entry_mult}", section="Sponsor returns"),
            Calc("uses", "Total Uses", M, "{entry_ev}*(1+{$fee_pct})+{$min_cash}"),
            Calc("sponsor_eq", "Sponsor Equity", M, "{uses}-{tl_close@0}-{notes_close@0}-{hold_close@0}"),
            Calc("exit_ev", "Exit Enterprise Value", M, "{ebitda@last}*{$exit_mult}"),
            Calc("exit_eq", "Exit Equity Value", M,
                 "{exit_ev}-{tl_close@last}-{rev_close@last}-{notes_close@last}-{hold_close@last}+{cash@last}"),
            Calc("eq_total", "Total Sponsor Equity invested", M, "{sponsor_eq}+SUM({cure@fc})"),
            Calc("moic", "Sponsor MOIC", M, "{exit_eq}/{eq_total}", unit="x", kind="ratio"),
        ]
        if spring:
            lines.append(Line("eq_flow", "Sponsor cash flows", M, fc="-{cure}", fc_last="-{cure}+{exit_eq}",
                              hist="formula", hist_fc="-{sponsor_eq}", section="Sponsor cash flows"))
            calcs.append(Calc("irr", "Sponsor IRR", M, "IRR({eq_flow@all})", unit="%", kind="ratio"))
    spec = ModelSpec(title="Credit agreement model", periods=periods, n_hist=1, sheets=[A, M], scalars=scalars,
                     lines=lines, calcs=calcs)

    doc = _agreement(rng, cfg, level, company, n)
    conventions = [
        "The Agreement above governs. Implement every provision that affects the rows of the Model exactly as "
        "drafted; provisions about events that do not occur in the Model (see Annex B) have no effect.",
        "Amounts in $ millions; percentages and ratios as decimals (5% = 0.05, 4.25x = 4.25).",
    ]

    ids = [IdSpec("term_loan_rollforward", "Term Loans roll forward",
                  [(1, "tl_close", 0), (-1, "tl_close", -1), (1, "ecf_pay", 0), (1, "sched", 0)]),
           IdSpec("ecf_definition", "Excess Cash Flow = EBITDA - cash interest - taxes - capex - increase in WC - "
                  "installments", [(1, "ecf", 0), (-1, "ebitda", 0), (1, "cash_int", 0), (1, "tax", 0),
                                   (1, "capex", 0), (1, "d_nwc", 0), (1, "sched", 0)])]
    if credit:
        ids.append(IdSpec("prepayment_credit_rollforward", "credit = opening + ECF prepayment - credit applied",
                          [(1, "credit", 0), (-1, "credit", -1), (-1, "ecf_pay", 0), (1, "credit_used", 0)]))
    cash_terms = [(1, "cash", 0), (-1, "cash", -1), (-1, "ebitda", 0), (1, "cash_int", 0), (1, "tax", 0),
                  (1, "capex", 0), (1, "d_nwc", 0), (1, "ecf_pay", 0), (1, "sched", 0)]
    if revolver:
        cash_terms.append((-1, "rev_net", 0))
        ids.append(IdSpec("revolver_rollforward", "Revolving Loans roll forward",
                          [(1, "rev_close", 0), (-1, "rev_close", -1), (-1, "rev_net", 0)]))
        ids.append(IdSpec("notes_bullet", "Senior Notes unchanged", [(1, "notes_close", 0), (-1, "notes_close", -1)]))
    if cov:
        cash_terms.append((-1, "cure", 0))
    ids.append(IdSpec("cash_rollforward", "cash roll-forward", cash_terms))
    if holdco:
        ids += [IdSpec("holdco_rollforward", "HoldCo Notes accrete by PIK interest",
                       [(1, "hold_close", 0), (-1, "hold_close", -1), (-1, "hold_int", 0)]),
                IdSpec("sources_equal_uses", "sponsor equity + debt at closing = total uses",
                       [(1, "sponsor_eq", 0), (1, "tl_close", 0), (1, "notes_close", 0), (1, "hold_close", 0),
                        (-1, "uses", 0)], when="once")]
    mono = [MonoSpec("moic_falls_with_entry_multiple", "moic", "entry_mult", 0.5, -1)] if holdco else \
        [MonoSpec("term_loans_fall_with_installments", "tl_close@last", "amort_pct", 0.005, -1)]

    outputs = [("adj_sofr", "Adjusted Term SOFR"), ("cash_int", "Consolidated Cash Interest Expense"),
               ("tax", "Taxes paid in cash"), ("ecf", "Excess Cash Flow"), ("ecf_pay", "Excess Cash Flow prepayment"),
               ("sched", "Scheduled installment paid"), ("tl_close", "Term Loans - closing balance"),
               ("cash", "Unrestricted Cash - closing")]
    if grid:
        outputs += [("app_rate", "Applicable Rate"), ("fl_lev", "First Lien Net Leverage Ratio")]
    if revolver:
        outputs += [("cons_ebitda", "Consolidated EBITDA"), ("rev_close", "Revolving Loans - closing balance"),
                    ("tot_lev", "Total Net Leverage Ratio (before any Cure Amount)")]
    if cov:
        outputs.append(("cure", "Cure Amount"))
    if spring:
        outputs.append(("cov_default", "Financial Covenant Default (1/0)"))
    if holdco:
        outputs += [("hold_close", "HoldCo Notes - closing balance"), ("sponsor_eq", "Sponsor Equity"),
                    ("exit_eq", "Exit Equity Value"), ("moic", "Sponsor MOIC")]
    if spring:
        outputs.append(("irr", "Sponsor IRR"))

    kinds = {
        "floor": ("rate", 0.0, 0.03), "sofr": ("interest", 0.0, 0.12), "amort_pct": ("rate", 0.0, 0.05),
        "margin": ("rate", 0.005, 0.08), "margin1": ("rate", 0.005, 0.08), "margin2": ("rate", 0.005, 0.08),
        "margin3": ("rate", 0.005, 0.08), "pg_t1": ("multiple", 0.5, 9.0), "pg_t2": ("multiple", 0.5, 9.0),
        "ecf_t1": ("multiple", 0.5, 9.0), "ecf_t2": ("multiple", 0.5, 9.0), "fee_t": ("multiple", 0.5, 9.0),
        "ecf_pct": ("rate", 0.0, 1.0), "ecf_hi": ("rate", 0.0, 1.0), "ecf_mid": ("rate", 0.0, 1.0),
        "fee_lo": ("rate", 0.0, 0.02), "fee_hi": ("rate", 0.0, 0.02), "cs_cap": ("rate", 0.0, 0.5),
        "net_pct": ("rate", 0.0, 1.0), "spring_pct": ("rate", 0.05, 0.95), "tax_rate": ("tax", 0.0, 0.45),
        "entry_mult": ("multiple", 4.0, 18.0), "exit_mult": ("multiple", 3.0, 18.0), "fee_pct": ("rate", 0.0, 0.06),
        "cov_max": ("multiple", 1.0, 12.0), "g_rev": ("growth", None, None), "margin_e": ("rate", 0.03, 0.6),
        "notes_cpn": ("interest", 0.0, 0.2), "hold_rate": ("interest", 0.0, 0.25), "savings": ("money", 0.0, None),
    }
    return Bundle(domain=DOMAIN, noun=f"debt model for the borrower under a credit agreement ({company})", spec=spec,
                  term_sheet=doc, conventions=conventions, identities=ids, monotone=mono, kinds=kinds,
                  outputs=outputs, scale=rev0, level=level, fixed_when_zero=("savings",), ascending_scalars=asc,
                  meta={"years": n, "document": "credit agreement"})


# ---------------------------------------------------------------------------
# the agreement
# ---------------------------------------------------------------------------

def _agreement(rng: random.Random, cfg: dict, level: int, company: str, n: int) -> str:
    grid, credit, revolver = cfg["grid"], cfg["credit"], cfg["revolver"]
    holdco, cov, spring = cfg.get("holdco", False), cfg.get("cov", False), cfg.get("spring", False)
    hold = f"{company} Holdings, Inc."
    borrower = f"{company} Intermediate, LLC"
    doc = LegalDoc("Credit Agreement",
                   f"CREDIT AGREEMENT dated as of the Closing Date among {hold} (\"Holdings\"), {borrower} "
                   "(the \"Borrower\"), the Lenders party hereto and the Administrative Agent. Capitalized "
                   "amounts, rates and ratios referred to by a caption in quotation marks are set forth in Schedule 1 "
                   "(the Assumptions sheet of the Model).")
    D = doc.define
    loans = "Term Loans and Revolving Loans" if revolver else "Term Loans"

    # ---- operative definitions
    D("Adjusted Term SOFR", "means, for any Fiscal Year, the greater of (a) Term SOFR for such Fiscal Year and (b) "
      "the Floor.")
    if grid:
        D("Applicable Rate", "means, for any Fiscal Year, the percentage per annum set forth below for the Pricing "
          "Level determined by the First Lien Net Leverage Ratio as of the last day of the most recently ended Fiscal "
          "Year for which financial statements have been delivered pursuant to [[fin_statements|(a)]]:\n"
          f"  Pricing Level I: First Lien Net Leverage Ratio greater than the {q('pg_t1')}: {q('margin1')};\n"
          f"  Pricing Level II: greater than the {q('pg_t2')} but not greater than the {q('pg_t1')}: {q('margin2')};\n"
          f"  Pricing Level III: not greater than the {q('pg_t2')}: {q('margin3')};\n"
          "provided that, until the date of delivery of financial statements for the first full Fiscal Year ending "
          "after the Closing Date, the Applicable Rate shall be the rate set forth for Pricing Level I.")
    else:
        D("Applicable Rate", f"means {q('margin')} per annum.")
    if revolver:
        D("Applicable Commitment Fee Rate", f"means, for any Fiscal Year, {q('fee_hi')} if the First Lien Net "
          "Leverage Ratio as of the last day of the most recently ended Fiscal Year for which financial statements "
          f"have been delivered pursuant to [[fin_statements|(a)]] is greater than the {q('fee_t')}, and "
          f"{q('fee_lo')} otherwise; provided that, until the date of delivery of financial statements for the first "
          f"full Fiscal Year ending after the Closing Date, the Applicable Commitment Fee Rate shall be {q('fee_hi')}.")
    if grid:
        D("Applicable ECF Percentage", f"means, for any Excess Cash Flow Period, (a) {q('ecf_hi')} if the First "
          f"Lien Net Leverage Ratio as of the last day of such Excess Cash Flow Period is greater than the "
          f"{q('ecf_t1')}, (b) {q('ecf_mid')} if such ratio is greater than the {q('ecf_t2')} but not greater than "
          f"the {q('ecf_t1')}, and (c) 0% otherwise.")
    else:
        D("Applicable ECF Percentage", f"means {q('ecf_pct')}.")
    D("Capital Expenditures", "means, for any period, the capital expenditures of the Borrower and its Subsidiaries "
      "for such period determined in accordance with Annex B.")
    D("Closing Date", "means the date on which the Term Loans are made, being the last day of the Fiscal Year shown "
      "in the first column of the Model.")
    D("Consolidated Cash Interest Expense", "means, for any period, the sum of (a) interest on the "
      + loans + (", (b) interest on the Senior Notes and (c) Commitment Fees" if revolver else "")
      + ", in each case paid in cash during such period" + (
          "; for the avoidance of doubt, interest on the HoldCo Notes is not Consolidated Cash Interest Expense"
          if holdco else "") + ".")
    if revolver:
        D("Consolidated EBITDA", "means, for any period, EBITDA for such period plus, without duplication, Pro Forma "
          "Cost Savings for such period; provided that the aggregate amount added pursuant to this definition for "
          f"any period shall not exceed the {q('cs_cap')} multiplied by EBITDA for such period (that is, Consolidated "
          "EBITDA calculated before giving effect to such addition).")
        D("Consolidated First Lien Net Debt", "means, as of any date, (a) the aggregate principal amount of Term "
          "Loans and Revolving Loans outstanding on such date minus (b) Unrestricted Cash on such date in an amount "
          "not exceeding the Netting Limit.")
        D("Consolidated Total Net Debt", "means, as of any date, (a) the aggregate principal amount of Term Loans, "
          "Revolving Loans and Senior Notes outstanding on such date minus (b) Unrestricted Cash on such date in an "
          "amount not exceeding the Netting Limit" + (
              ". The HoldCo Notes are Indebtedness of Holdings, which is not a Subsidiary of the Borrower, and are not "
              "included in Consolidated Total Net Debt or Consolidated First Lien Net Debt" if holdco else "") + ".")
        D("Netting Limit", f"means, as of any date, the greater of (a) the {q('net_fixed')} and (b) the "
          f"{q('net_pct')} multiplied by Consolidated EBITDA for the Test Period ending on such date.")
        D("Pro Forma Cost Savings", f"means, for any Fiscal Year, the amount set forth for such Fiscal Year "
          f"opposite {q('savings')} in Schedule 1.")
        D("Minimum Liquidity Amount", f"means {amt('min_cash')}.")
        D("Revolving Commitments", f"means {amt('rev_commit')}.")
        D("Senior Notes", f"means the senior unsecured notes of the Borrower in a principal amount equal to "
          f"{amt('notes_amt')}, bearing cash interest at the {q('notes_cpn')} on the principal amount outstanding on "
          "the first day of each Fiscal Year and maturing after the last Fiscal Year shown in the Model. The Senior "
          "Notes are unsecured and are not included in Consolidated First Lien Net Debt.")
        D("Total Net Leverage Ratio", "means, as of any date, the ratio of Consolidated Total Net Debt as of such "
          "date to Consolidated EBITDA for the Test Period ending on such date.")
    else:
        D("Consolidated EBITDA", "means, for any period, EBITDA for such period.")
        if grid:
            D("Consolidated First Lien Net Debt", "means, as of any date, the aggregate principal amount of Term "
              "Loans outstanding on such date minus Unrestricted Cash on such date.")
    D("EBITDA", "means, for any period, the earnings before interest, taxes, depreciation and amortization of the "
      "Borrower and its Subsidiaries for such period determined in accordance with Annex B, without any pro forma "
      "adjustment.")
    D("Excess Cash Flow", "means, for any Excess Cash Flow Period, an amount (which may be negative) equal to (a) "
      "EBITDA for such period minus (b) the sum, without duplication, of (i) Consolidated Cash Interest Expense for "
      "such period, (ii) taxes paid in cash during such period, (iii) Capital Expenditures for such period, (iv) the "
      "increase in Consolidated Working Capital from the first day to the last day of such period (or minus the "
      "amount of any decrease) and (v) the aggregate principal amount of installments of Term Loans paid pursuant "
      "to [[repayment|(a)]] during such period. Prepayments pursuant to [[prepayments]] are not deducted.")
    D("Excess Cash Flow Period", "means each full Fiscal Year ending after the Closing Date.")
    if grid:
        D("First Lien Net Leverage Ratio", "means, as of any date, the ratio of Consolidated First Lien Net Debt "
          "as of such date to Consolidated EBITDA for the Test Period ending on such date.")
    D("Fiscal Year", "means the fiscal year of the Borrower; each column of the Model after the first is one "
      "Fiscal Year.")
    D("Floor", f"means the {q('floor')}.")
    if holdco:
        D("HoldCo Notes", f"means the senior PIK notes issued by Holdings on the Closing Date in the principal "
          f"amount equal to {amt('hold_amt')}. Interest accrues at the {q('hold_rate')} on the principal amount "
          "outstanding on the first day of each Fiscal Year and is paid in kind by being added to principal on the "
          "last day of such Fiscal Year. No payment on the HoldCo Notes is made by the Borrower.")
    D("Term SOFR", f"means, for any Fiscal Year, the rate set forth for such Fiscal Year opposite {q('sofr')} in "
      "Schedule 1.")
    D("Test Period", "means, as of any date, the Fiscal Year ending on such date.")
    D("Unrestricted Cash", "means, as of any date, the cash balance of the Borrower and its Subsidiaries on such "
      "date (which is negative if overdrawn)" + ((
          "; provided that the amount of Unrestricted Cash deducted in calculating Consolidated First Lien Net Debt"
          + (" or Consolidated Total Net Debt" if revolver else "") + " shall never be less than zero (a negative "
          "balance is not deducted and is not added to Indebtedness)") if grid else "")
      + (", subject to [[cure|(d)]]" if cov else "") + ".")
    if cov:
        D("Cure Amount", "has the meaning assigned to such term in [[cure|(a)]].")
    if spring:
        D("Springing Test Condition", "means, as of the last day of any Fiscal Year, that the aggregate principal "
          "amount of Revolving Loans outstanding on such day (after giving effect to all borrowings and repayments "
          f"on such day) exceeds the {q('spring_pct')} multiplied by the Revolving Commitments.")

    # ---- distractor definitions
    distractor_defs = [
        ("Asset Sale", "means any disposition of property of the Borrower or any Subsidiary, other than dispositions "
         "of inventory in the ordinary course of business."),
        ("Business Day", "means any day other than a Saturday, Sunday or day on which banks in New York City are "
         "authorized or required by law to close."),
        ("Change of Control", "means the Permitted Holders ceasing to own, directly or indirectly, more than 50% of "
         "the voting equity interests of Holdings."),
        ("Declined Proceeds", "has the meaning assigned to such term in [[prepayments|(e)]]."),
        ("Incremental Cap", "means the sum of (a) the greater of $150,000,000 and 100% of Consolidated EBITDA for "
         "the most recently ended Test Period, plus (b) the amount of all voluntary prepayments of Term Loans, plus "
         "(c) an unlimited amount so long as the First Lien Net Leverage Ratio does not exceed 0.25x less than the "
         "ratio on the Closing Date."),
        ("Material Adverse Effect", "means a material adverse effect on the business, assets or financial condition "
         "of the Borrower and its Subsidiaries, taken as a whole."),
        ("Net Proceeds", "means the cash proceeds of any Asset Sale or incurrence of Indebtedness, net of fees, taxes "
         "and repayments of Indebtedness secured by the relevant assets."),
        ("Permitted Holders", "means the Sponsor and its Affiliates (other than portfolio companies)."),
        ("Restricted Payment", "means any dividend or other distribution on, or any purchase or redemption of, any "
         "equity interest of Holdings or the Borrower."),
    ]
    for term, text in distractor_defs:
        D(term, text)

    # ---- Article I: interpretation
    doc.section("DEFINITIONS AND ACCOUNTING TERMS", "interp", "Terms Generally",
                "The words \"include\", \"includes\" and \"including\" shall be deemed to be "
                "followed by \"without limitation\". References to Sections, Annexes and Schedules are to "
                "those of this Agreement. Any financial ratio is calculated without rounding.")
    doc.section("DEFINITIONS AND ACCOUNTING TERMS", "acct", "Accounting Terms; Timing of Calculations",
                "(a) All amounts are determined for the Borrower and its Subsidiaries on a consolidated basis in "
                "accordance with Annex B. (b) Balances, ratios and the Netting Limit are determined as of the last day "
                "of a Fiscal Year after giving effect to all payments, borrowings and repayments made on such day"
                + (" (subject to [[cure|(d)]])" if cov else "") + ". (c) A payment required to be made within a "
                "period after the end of a Fiscal Year or after the delivery of financial statements for a Fiscal "
                "Year is made in the immediately following Fiscal Year, before the installment due on the last "
                "Business Day of that Fiscal Year. (d) Financial statements for each Fiscal Year are delivered during "
                "the immediately following Fiscal Year; a rate determined by reference to the most recently ended "
                "Fiscal Year for which financial statements have been delivered applies for the whole of the Fiscal "
                "Year in which they are delivered.")

    # ---- Article II: the credits
    art2 = "THE CREDITS"
    doc.section(art2, "loans", "The Loans",
                f"(a) On the Closing Date each Term Lender made its share of Term Loans in an aggregate principal "
                f"amount equal to the {q('tl_amt')}." + (
                    " (b) Each Revolving Lender agrees to make Revolving Loans to the Borrower from time to time in an "
                    "aggregate principal amount not exceeding the Revolving Commitments. No Revolving Loans are "
                    "outstanding on the Closing Date, on which the Borrower holds Unrestricted Cash equal to the "
                    "Minimum Liquidity Amount." if revolver else
                    f" (b) On the Closing Date the Borrower holds Unrestricted Cash equal to the {q('open_cash')}."))
    if revolver:
        doc.section(art2, "liquidity", "Revolving Borrowings and Repayments",
                    "On the last day of each Fiscal Year, after all other payments to be made on such day "
                    + ("(other than the receipt of any Cure Amount) " if cov else "")
                    + "(a) if Unrestricted Cash would otherwise be less than the Minimum Liquidity Amount, the "
                    "Borrower shall borrow Revolving Loans in the amount of the shortfall, but not in excess of the "
                    "unused Revolving Commitments, and (b) if Unrestricted Cash exceeds the Minimum Liquidity Amount, "
                    "the Borrower shall apply the excess to repay outstanding Revolving Loans until repaid in full.")
    doc.section(art2, "repayment", "Repayment of Loans",
                "(a) The Borrower shall repay Term Loans on the last Business Day of each Fiscal Year ending after the "
                f"Closing Date in an aggregate principal amount equal to the {q('amort_pct')} multiplied by the "
                "aggregate principal amount of Term Loans made on the Closing Date (as such installments may be "
                "reduced as a result of the application of prepayments in accordance with [[application]]); "
                "provided that no installment shall exceed the principal amount of Term Loans then outstanding. "
                "(b) All Loans shall be repaid on the Maturity Date, which falls after the last Fiscal Year shown in "
                "the Model.")
    prepay = [
        "(a) Optional. The Borrower may prepay Loans at any time without premium, except that any prepayment of Term "
        "Loans in connection with a Repricing Transaction within six months after the Closing Date is subject to a 1% "
        "premium.",
        "(b) Asset Sales. Within ten Business Days after receipt of Net Proceeds of any Asset Sale in excess of "
        "$10,000,000 in any Fiscal Year, the Borrower shall prepay Term Loans in an amount equal to 100% of such Net "
        "Proceeds (reduced to 50% if the First Lien Net Leverage Ratio is not greater than 0.50x below the ratio on "
        "the Closing Date), subject to reinvestment rights for 365 days.",
        "(c) Debt Incurrence. Within one Business Day after the incurrence of any Indebtedness not permitted by "
        "[[indebtedness]], the Borrower shall prepay Term Loans in an amount equal to 100% of the Net Proceeds.",
        "(d) Excess Cash Flow. Within five Business Days after financial statements are delivered pursuant to "
        "[[fin_statements|(a)]] for any Excess Cash Flow Period, the Borrower shall prepay Term Loans in an aggregate "
        "principal amount equal to the Applicable ECF Percentage for such Excess Cash Flow Period multiplied by "
        "Excess Cash Flow for such Excess Cash Flow Period, if positive; provided that no such prepayment shall "
        "exceed the principal amount of Term Loans then outstanding.",
        "(e) Declined Proceeds. Any Term Lender may elect to decline its share of any mandatory prepayment (such "
        "declined amounts, \"Declined Proceeds\"), which may be retained by the Borrower.",
    ]
    doc.section(art2, "prepayments", "Prepayments", " ".join(prepay))
    if credit:
        app = ("Each prepayment pursuant to [[prepayments|(d)]] shall be applied to reduce the subsequent installments "
               "of Term Loans under [[repayment|(a)]] in direct order of maturity (the installment next due first), "
               "until the full amount of such prepayment has been applied; any portion not yet applied is carried "
               "forward and applied to each following installment in turn. A prepayment made in a Fiscal Year is "
               "applied first to the installment due on the last Business Day of that Fiscal Year.")
    else:
        app = ("Each prepayment pursuant to [[prepayments|(d)]] shall be applied to the principal amount of Term "
               "Loans due on the Maturity Date and shall not reduce any installment under [[repayment|(a)]].")
    doc.section(art2, "application", "Application of Prepayments", app)
    if revolver:
        doc.section(art2, "fees", "Fees",
                    "(a) The Borrower shall pay to the Administrative Agent for the account of each Revolving Lender a "
                    "commitment fee for each Fiscal Year (the \"Commitment Fee\") at the Applicable "
                    "Commitment Fee Rate on the amount by which the Revolving Commitments exceed the Revolving Loans "
                    "outstanding on the first day of such Fiscal Year. (b) The Borrower shall pay the agency fees "
                    "separately agreed in the Fee Letter.")
    doc.section(art2, "interest", "Interest",
                f"(a) The {loans} bear interest for each Fiscal Year at a rate per annum equal to Adjusted Term SOFR "
                "for such Fiscal Year plus the Applicable Rate, on the principal amount outstanding on the first day "
                "of such Fiscal Year, payable in cash on the last day of such Fiscal Year. (b) Upon the occurrence "
                "and during the continuance of an Event of Default, at the election of the Required Lenders, overdue "
                "amounts bear interest at 2% per annum above the otherwise applicable rate.")
    doc.section(art2, "taxes_gross", "Taxes",
                "All payments by the Borrower shall be made free and clear of withholding taxes, subject to customary "
                "gross-up and exclusions for Excluded Taxes.")

    # ---- Article V / VI / VII
    doc.section("AFFIRMATIVE COVENANTS", "fin_statements", "Financial Statements",
                "The Borrower shall deliver to the Administrative Agent: (a) within 120 days after the end of each "
                "Fiscal Year, audited consolidated financial statements for such Fiscal Year; (b) within 45 days after "
                "the end of each of the first three fiscal quarters, unaudited quarterly financial statements; and (c) "
                "with each delivery under clause (a), a compliance certificate setting forth the calculation of the "
                "First Lien Net Leverage Ratio" + (" and the Total Net Leverage Ratio" if revolver else "") + ".")
    neg = "NEGATIVE COVENANTS"
    doc.section(neg, "indebtedness", "Indebtedness",
                "The Borrower shall not incur Indebtedness other than (a) the Loans, " + (
                    "(b) the Senior Notes, " if revolver else "") + "(c) Incremental Facilities in an aggregate "
                "amount not exceeding the Incremental Cap and (d) other Indebtedness in an aggregate amount not "
                "exceeding the greater of $50,000,000 and 50% of Consolidated EBITDA for the most recently ended Test "
                "Period.")
    doc.section(neg, "restricted_payments", "Restricted Payments",
                "The Borrower shall not make any Restricted Payment, except (a) Restricted Payments in an aggregate "
                "amount not exceeding the sum of 50% of cumulative Excess Cash Flow not required to be applied under "
                "[[prepayments|(d)]] (the \"Available Amount\"), so long as the Total Net Leverage Ratio would "
                "not exceed 4.00x on a pro forma basis, and (b) payments to Holdings to pay its franchise taxes and "
                "overhead not exceeding $5,000,000 in any Fiscal Year.")
    if cov:
        text = ("Commencing with the first full Fiscal Year ending after the Closing Date, the Borrower shall not "
                "permit the Total Net Leverage Ratio as of the last day of any Fiscal Year to exceed the ratio set "
                f"forth for such Fiscal Year opposite {q('cov_max')} in Schedule 1")
        if spring:
            text += ("; provided that this covenant shall be tested only as of the last day of a Fiscal Year on which "
                     "the Springing Test Condition is satisfied, and shall not apply to any other Fiscal Year")
        doc.section(neg, "fin_cov", "Financial Covenant", text + ".")
    eod = "EVENTS OF DEFAULT"
    doc.section(eod, "events", "Events of Default",
                "Each of the following is an Event of Default: (a) failure to pay principal when due, or interest "
                "within five Business Days after it is due; (b) any representation proving materially incorrect when "
                "made; (c) failure to observe any covenant" + (
                    " (including [[fin_cov]], subject to [[cure]])" if cov else "") + "; (d) cross-default to "
                "Indebtedness in excess of $40,000,000; (e) insolvency events; (f) judgments in excess of "
                "$40,000,000 unsatisfied for 60 days; and (g) a Change of Control.")
    if cov:
        cure = ("(a) If the Borrower fails to comply with [[fin_cov]] as of the last day of any Fiscal Year, the "
                "Sponsor may make a cash equity contribution to the Borrower (the amount so contributed, a "
                "\"Cure Amount\"), which shall be added to Consolidated EBITDA for such Fiscal Year solely for "
                "the purpose of determining compliance with [[fin_cov]] as of the last day of such Fiscal Year. "
                "(b) The Cure Amount shall be equal to the minimum amount that, if so added, would cause the Total "
                "Net Leverage Ratio to equal the maximum ratio permitted for such Fiscal Year; the Sponsor contributes "
                "exactly that amount whenever a Cure Amount is permitted. ")
        if spring:
            cure += ("(c) No more than two Cure Amounts may be made during the term of this Agreement, and no Cure "
                     "Amount may be made in respect of a Fiscal Year immediately following a Fiscal Year in respect "
                     "of which a Cure Amount was made. If [[fin_cov]] is not complied with and no Cure Amount is "
                     "permitted, a \"Financial Covenant Default\" occurs for such Fiscal Year. ")
        else:
            cure += "(c) There is no limit on the number of Cure Amounts. "
        cure += ("(d) No Cure Amount shall reduce Indebtedness (by netting or otherwise) or be included in "
                 "Unrestricted Cash for the purpose of determining any financial ratio, the Netting Limit, the "
                 "Applicable Rate" + (", the Applicable Commitment Fee Rate" if revolver else "") + ", the "
                 "Applicable ECF Percentage or the Springing Test Condition as of the last day of the Fiscal Year in "
                 "respect of which it is made, and no Cure Amount increases Consolidated EBITDA for any purpose other "
                 "than [[fin_cov]]. The Cure Amount is received in cash on the last day of such Fiscal Year after "
                 "all other payments, borrowings and repayments on such day, is not applied to repay any Loan, and "
                 "forms part of Unrestricted Cash thereafter.")
        doc.section(eod, "cure", "Right to Cure", cure)
    doc.section("THE ADMINISTRATIVE AGENT", "agent", "Appointment and Authority",
                "Each Lender irrevocably appoints the Administrative Agent to act on its behalf under this Agreement "
                "and authorizes it to take such actions and exercise such powers as are delegated to it hereunder.")
    doc.section("MISCELLANEOUS", "law", "Governing Law",
                "This Agreement shall be governed by, and construed in accordance with, the law of the State of New "
                "York.")

    # ---- annexes
    if holdco:
        ret = ("ANNEX A is the Sponsor's returns methodology (it is not an obligation of the Borrower). (1) Enterprise "
               f"Value at closing = the {q('entry_mult')} multiplied by EBITDA for the Fiscal Year ended on the Closing "
               f"Date. (2) Total Uses = Enterprise Value at closing plus Transaction Costs (the {q('fee_pct')} "
               "multiplied by Enterprise Value at closing) plus the Minimum Liquidity Amount funded to the balance "
               "sheet. (3) Sponsor Equity = Total Uses minus the Term Loans, the Senior Notes and the HoldCo Notes, "
               f"each as of the Closing Date. (4) Exit Enterprise Value = the {q('exit_mult')} multiplied by EBITDA "
               "(not Consolidated EBITDA) for the last Fiscal Year shown in the Model. (5) Exit Equity Value = Exit "
               "Enterprise Value minus the Term Loans, Revolving Loans, Senior Notes and HoldCo Notes outstanding at "
               "the end of that Fiscal Year plus the cash balance at that date (without regard to the Netting Limit, "
               "and negative if overdrawn). (6) Sponsor MOIC = Exit Equity Value divided by the sum of Sponsor Equity and all Cure "
               "Amounts.")
        if spring:
            ret += (" (7) Sponsor cash flows: minus Sponsor Equity in the Closing Date column; minus the Cure Amount "
                    "in each Fiscal Year; plus Exit Equity Value in the last Fiscal Year. Sponsor IRR is the internal "
                    "rate of return of these annual cash flows (one value per column, Closing Date column included).")
        doc.annex("Annex A - Sponsor Returns Methodology", ret)
    ops = ("ANNEX B is the Model convention. (1) Each column of the Model after the first is a Fiscal Year; the "
           "first column shows balances as of the Closing Date. (2) Revenue for a Fiscal Year = revenue for the prior "
           f"Fiscal Year multiplied by (1 + {q('g_rev')} for the year); EBITDA = revenue multiplied by {q('margin_e')} "
           f"for the year. D&A, Capital Expenditures and Consolidated Working Capital are revenue multiplied by "
           f"{q('da_pct')}, {q('capex_pct')} and {q('nwc_pct')} respectively; the increase in Consolidated Working "
           "Capital for a Fiscal Year is the amount at its end minus the amount at the end of the prior Fiscal Year. "
           f"(3) Taxes paid in cash for a Fiscal Year = the {q('tax_rate')} multiplied by (EBITDA - D&A - Consolidated "
           "Cash Interest Expense), or zero if that amount is negative" + (
               "; interest on the HoldCo Notes is not deductible by the Borrower" if holdco else "") + ". "
           "(4) Unrestricted Cash at the end of a Fiscal Year = Unrestricted Cash at the end of the prior Fiscal Year "
           "+ EBITDA - Consolidated Cash Interest Expense - taxes paid in cash - Capital Expenditures - the increase "
           "in Consolidated Working Capital - prepayments and installments of Term Loans paid in the year"
           + (" + net Revolving Loans borrowed (minus net repayments) under [[liquidity]]" if revolver else "")
           + (" + any Cure Amount" if cov else "") + "; it may be negative. "
           "(5) The Model reflects no Asset Sales, incurrence of Indebtedness (other than Revolving Loans), "
           "Incremental Facilities, optional prepayments, Repricing Transactions, Declined Proceeds, Restricted "
           "Payments, payments under the Fee Letter, default interest or other Event of Default consequences, and "
           "provisions concerning them have no effect on the Model" + (
               " (a Financial Covenant Default is recorded as 1 for the Fiscal Year in which it occurs and 0 "
               "otherwise, without any further consequence)" if spring else "") + ".")
    doc.annex("Annex B - Model Conventions", ops)
    doc.annex("Schedule 1 - Assumptions", "Schedule 1 is the Assumptions sheet of the Model. Each caption in "
              "quotation marks in this Agreement refers to the value set forth opposite that caption (per-year "
              "values: in the column of the relevant Fiscal Year).")
    return doc.render()
