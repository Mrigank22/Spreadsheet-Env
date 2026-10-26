"""SaaS subscription model: annual contracts, ARR, ratable revenue, deferred revenue.

Twelve months of actuals (bookings, billings, ARR, deferred revenue) are given;
the agent projects the following months. Annual contracts are billed upfront at
signature and at every anniversary; revenue is recognised ratably, 1/12 per
month starting in the billing month (ASC 606 for a ratable service).

1. renewals = billings 12 months earlier x net retention; ARR = billings of the
   last 12 months (rolling); revenue = ARR / 12.
2. + renewals split into churn (gross retention) and expansion; the ARR bridge;
   deferred revenue roll-forward (opening + billings - revenue).
3. + a price uplift on renewals from a given month, and trailing-12-month net
   revenue retention.
4. + a monthly-billed SMB segment (MRR with monthly logo churn), recognised
   as billed; blended revenue and ARR.
5. + collections on payment terms (annual invoices paid after a lag): accounts
   receivable roll-forward, cash collected, and CAC payback.
"""

from __future__ import annotations

import random
from typing import List

from ..model.spec import Calc, Line, ModelSpec, Scalar
from .framework import Bundle, IdSpec, MonoSpec

DOMAIN = "saas"

LEVELS = {
    1: dict(n=24, split=False, uplift=False, smb=False, collect=False),
    2: dict(n=24, split=True, uplift=False, smb=False, collect=False),
    3: dict(n=36, split=True, uplift=True, smb=False, collect=False),
    4: dict(n=36, split=True, uplift=True, smb=True, collect=False),
    5: dict(n=36, split=True, uplift=True, smb=True, collect=True),
}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def generate(rng: random.Random, level: int) -> Bundle:
    cfg = LEVELS[level]
    u = rng.uniform
    n = cfg["n"]
    H = 12
    grr = round(u(0.80, 0.95), 3)
    exp = round(u(0.03, 0.20), 3)
    nrr = round(grr * (1 + exp), 4)
    # simulate 36 months of history so the last 12 are internally consistent
    base_new = 10 ** u(-0.5, 1.0)  # $m new ARR per month
    g_m = u(0.005, 0.03)
    new_hist = [round(base_new * (1 + g_m) ** t * u(0.8, 1.2), 3) for t in range(36)]
    billed_hist = []
    for t in range(36):
        renew = billed_hist[t - 12] * nrr if t >= 12 else base_new * 6 * u(0.8, 1.2) * (1 + g_m) ** t
        billed_hist.append(round(new_hist[t] + renew, 3))
    arr_hist = [round(sum(billed_hist[t - 11:t + 1]), 3) for t in range(11, 36)]
    dr_hist = [round(sum(billed_hist[t - k] * (11 - k) / 12 for k in range(12)), 4) for t in range(11, 36)]
    new_h, billed_h = new_hist[-H:], billed_hist[-H:]
    arr_h, dr_h = arr_hist[-H:], dr_hist[-H:]
    new_fc = [round(new_h[-1] * (1 + g_m) ** (t + 1) * u(0.85, 1.15), 3) for t in range(n)]
    y0 = rng.randint(2024, 2026)
    m0 = rng.randint(0, 11)
    labels = [f"{MONTHS[(m0 + i) % 12]}-{str(y0 + (m0 + i) // 12)[2:]}" for i in range(H + n)]
    periods = [f"{x}A" for x in labels[:H]] + [f"{x}E" for x in labels[H:]]
    A, M = "Assumptions", "Model"
    scalars = []
    if cfg["split"]:
        scalars += [Scalar("grr", "Gross dollar retention at renewal", grr, "%", "rate"),
                    Scalar("exp", "Expansion at renewal (% of retained ARR)", exp, "%", "rate")]
    else:
        scalars.append(Scalar("nrr", "Net dollar retention at renewal", nrr, "x", "ratio"))
    if cfg["uplift"]:
        scalars += [Scalar("uplift", "Price uplift on renewals", round(rng.choice([0.03, 0.05, 0.07]), 3), "%", "rate"),
                    Scalar("uplift_month", "Uplift applies to renewals from projection month", float(rng.randint(4, 12)),
                           "#", "fixed")]
    if cfg["smb"]:
        smb_mrr0 = round(arr_h[-1] / 12 * u(0.15, 0.35), 3)
        scalars += [Scalar("smb_churn", "SMB monthly logo churn", round(u(0.015, 0.04), 4), "%", "rate")]
    if cfg["collect"]:
        lag = rng.choice([1, 2, 3])
        scalars += [Scalar("lag", "Annual invoices are collected after (months)", float(lag), "m", "fixed"),
                    Scalar("gm", "Gross margin", round(u(0.70, 0.85), 3), "%", "rate")]
    lines: List[Line] = [
        Line("new_arr", "New ARR booked (annual contracts)", A, fc=None, history=new_h, forecast=new_fc,
             kind="money", hist="input"),
    ]
    if cfg["smb"]:
        smb_new = [round(smb_mrr0 * u(0.03, 0.06), 4) for _ in range(n)]
        lines.append(Line("smb_new", "SMB new MRR (monthly-billed)", A, fc=None, hist="blank", forecast=smb_new,
                          kind="money"))
    if cfg["collect"]:
        sm = [round(new_fc[t] * u(0.8, 1.6), 3) for t in range(n)]
        lines.append(Line("sm", "Sales & marketing spend", A, fc=None, hist="blank", forecast=sm, kind="money"))
    lines += [
        Line("month", "Projection month number", M, unit="#", fc="{month[-1]}+1",
             history=[float(t - H + 1) for t in range(H)], kind="ratio", desc="prior month + 1 (actual months <= 0)",
             section="Annual contracts"),
    ]
    if cfg["split"]:
        uplift = "*IF({month}>={$uplift_month},1+{$uplift},1)" if cfg["uplift"] else ""
        lines += [
            Line("churn", "Churned ARR", M, fc="{billed[-12]}*(1-{$grr})", hist="blank",
                 desc="ARR billed 12 months earlier x (1 - gross retention)"),
            Line("expansion", "Expansion ARR", M,
                 fc="{billed[-12]}*{$grr}*{$exp}" if not cfg["uplift"] else
                 "{billed[-12]}*{$grr}*((1+{$exp})" + uplift + "-1)", hist="blank",
                 desc="retained ARR x expansion" + (" (including the price uplift on renewals from the uplift "
                                                    "month: retained ARR x ((1 + expansion) x (1 + uplift) - 1))"
                                                    if cfg["uplift"] else "")),
            Line("renew", "Renewal billings", M, fc="{billed[-12]}-{churn}+{expansion}", hist="blank",
                 desc="ARR billed 12 months earlier - churn + expansion"),
        ]
    else:
        lines.append(Line("renew", "Renewal billings", M, fc="{billed[-12]}*{$nrr}", hist="blank",
                          desc="ARR billed 12 months earlier x net retention"))
    lines += [
        Line("billed", "Annual contracts billed (ARR invoiced)", M, fc="{new_arr}+{renew}", history=billed_h,
             desc="new ARR + renewal billings"),
        Line("arr", "Contract ARR", M, fc="SUM({billed[-11..0]})", history=arr_h,
             desc="sum of annual contracts billed in the last 12 months (including this month)"),
        Line("revenue", "Contract revenue (ratable)", M, fc="{arr}/12", hist="blank", desc="contract ARR / 12"),
    ]
    if cfg["split"]:
        lines.append(Line("dr", "Deferred revenue - closing", M, fc="{dr[-1]}+{billed}-{revenue}", history=dr_h,
                          desc="opening + billings - revenue recognised"))
    if cfg["uplift"]:
        lines.append(Line("nrr_ttm", "Net revenue retention (trailing 12 months)", M, unit="x", kind="ratio",
                          fc="({arr}-SUM({new_arr[-11..0]}))/{arr[-12]}", hist="blank",
                          desc="(contract ARR - new ARR booked in the last 12 months) / contract ARR 12 months ago"))
    rev_total = "{revenue}"
    arr_total = "{arr}"
    if cfg["smb"]:
        lines += [
            Line("smb_mrr", "SMB MRR - closing", M, fc="{smb_mrr[-1]}*(1-{$smb_churn})+{smb_new}",
                 history=[0.0] * (H - 1) + [smb_mrr0], desc="opening MRR x (1 - monthly churn) + new MRR",
                 section="SMB (monthly billing)"),
            Line("smb_rev", "SMB revenue", M, fc="{smb_mrr}", hist="blank", desc="SMB MRR (billed and recognised "
                                                                                 "monthly)"),
        ]
        rev_total += "+{smb_rev}"
        arr_total += "+12*{smb_mrr}"
    lines += [
        Line("rev_total", "Total revenue", M, fc=rev_total, hist="blank",
             desc="contract revenue" + (" + SMB revenue" if cfg["smb"] else ""), section="Totals"),
        Line("arr_total", "Total ARR", M, fc=arr_total, hist="blank",
             desc="contract ARR" + (" + 12 x SMB MRR" if cfg["smb"] else "")),
    ]
    if cfg["collect"]:
        lag = int(scalars[-2].value)
        ar_h = [round(sum(billed_h[H - 1 - k] for k in range(lag)), 3)] * H
        lines += [
            Line("collect", "Cash collected", M, fc=f"{{billed[-{lag}]}}" + ("+{smb_rev}" if cfg["smb"] else ""),
                 hist="blank", desc=f"annual invoices billed {lag} month(s) earlier"
                                    + (" + SMB revenue (collected as billed)" if cfg["smb"] else ""),
                 section="Cash"),
            Line("ar", "Accounts receivable - closing", M, fc="{ar[-1]}+{billed}-" + f"{{billed[-{lag}]}}",
                 history=ar_h, desc="opening + annual invoices - annual invoices collected"),
            Line("cac_payback", "CAC payback (months)", M, unit="m", kind="ratio",
                 fc="{sm}/({new_arr}*{$gm})*12", hist="blank",
                 desc="S&M spend / (new ARR x gross margin) x 12"),
        ]
    calcs = [Calc("rev_sum", "Total revenue over the projection", M, "SUM({rev_total@fc})", section="Results",
                  desc="sum of total revenue"),
             Calc("arr_end", "Total ARR at the end of the projection", M, "{arr_total@last}", desc="final total ARR")]
    spec = ModelSpec(title="SaaS subscription model", periods=periods, n_hist=H, sheets=[A, M], scalars=scalars,
                     lines=lines, calcs=calcs)
    ts = [
        "CONTRACTS. Enterprise customers sign 12-month contracts billed annually upfront: at signature (new ARR "
        "booked) and at every anniversary (renewal). Billing a contract invoices its full ARR.",
        ("RENEWALS. A cohort renews 12 months after its previous billing: renewal billings = the ARR billed 12 "
         "months earlier x net retention." if not cfg["split"] else
         "RENEWALS. A cohort renews 12 months after its previous billing. Of the ARR billed 12 months earlier, "
         "(1 - gross retention) churns; the retained part expands by the expansion %" + (
             ", and renewals billed in projection months at or after the uplift month also carry the price uplift "
             "(retained ARR x (1 + expansion) x (1 + uplift))" if cfg["uplift"] else "") + ". Renewal billings = "
         "ARR billed 12 months earlier - churn + expansion (expansion includes any uplift)."),
        "ARR. Contract ARR = the annual contracts billed in the last 12 months, including this one (each live "
        "contract was billed exactly once in that window).",
        "REVENUE is recognised ratably: 1/12 of each contract in the billing month and each of the next 11, so "
        "contract revenue = contract ARR / 12.",
    ]
    if cfg["split"]:
        ts.append("DEFERRED REVENUE = opening deferred revenue + billings - revenue recognised.")
    if cfg["uplift"]:
        ts.append("NET REVENUE RETENTION (trailing 12 months) = (contract ARR now - new ARR booked in the last 12 "
                  "months) / contract ARR 12 months ago.")
    if cfg["smb"]:
        ts.append("SMB SEGMENT: monthly plans billed and recognised monthly. SMB MRR = opening MRR x (1 - monthly "
                  "logo churn) + new MRR; SMB revenue = SMB MRR. Total revenue adds SMB revenue; total ARR adds "
                  "12 x SMB MRR.")
    if cfg["collect"]:
        ts.append("COLLECTIONS: annual invoices are paid after the collection lag (an invoice billed in month m is "
                  "collected in month m + lag); SMB revenue is collected as billed. Accounts receivable = opening + "
                  "annual invoices billed - annual invoices collected. CAC payback (months) = S&M spend / (new ARR "
                  "x gross margin) x 12.")
    conventions = ["Monthly periods; the first 12 columns are actuals, the rest the projection.",
                   "ARR, billings and revenue are in $m; retention and expansion rates apply per renewal.",
                   "Projection month number is 1 in the first projection month (actual months are <= 0)."]
    ids = [IdSpec("arr_rolling", "ARR roll-forward: + billings now - billings 12 months ago",
                  [(1, "arr", 0), (-1, "arr", -1), (-1, "billed", 0), (1, "billed", -12)])]
    if cfg["split"]:
        ids += [IdSpec("arr_bridge", "ARR bridge: opening + new + expansion - churn = closing",
                       [(1, "arr", 0), (-1, "arr", -1), (-1, "new_arr", 0), (-1, "expansion", 0), (1, "churn", 0)]),
                IdSpec("deferred_revenue_rollforward", "deferred revenue roll-forward",
                       [(1, "dr", 0), (-1, "dr", -1), (-1, "billed", 0), (1, "revenue", 0)])]
    if cfg["collect"]:
        lag = int(next(s for s in scalars if s.id == "lag").value)
        ids.append(IdSpec("receivables_rollforward", "AR roll-forward",
                          [(1, "ar", 0), (-1, "ar", -1), (-1, "billed", 0), (1, "billed", -lag)]))
    mono = [MonoSpec("revenue_rises_with_retention", "rev_sum", "grr" if cfg["split"] else "nrr", 0.02, 1)]
    if cfg["split"]:
        mono.append(MonoSpec("arr_rises_with_expansion", "arr_end", "exp", 0.02, 1))
    outputs = [("billed", "Annual contracts billed"), ("arr", "Contract ARR"), ("revenue", "Contract revenue")]
    if cfg["split"]:
        outputs += [("churn", "Churned ARR"), ("dr", "Deferred revenue")]
    if cfg["uplift"]:
        outputs.append(("nrr_ttm", "Net revenue retention (TTM)"))
    if cfg["smb"]:
        outputs.append(("smb_mrr", "SMB MRR"))
    if cfg["collect"]:
        outputs += [("ar", "Accounts receivable"), ("cac_payback", "CAC payback (months)")]
    outputs += [("rev_total", "Total revenue"), ("rev_sum", "Total revenue over the projection"),
                ("arr_end", "Ending total ARR")]
    kinds = {"month": ("fixed", None, None), "grr": ("rate", 0.4, 1.0), "exp": ("rate", 0.0, 0.6),
             "nrr": ("ratio", 0.4, 1.6), "uplift": ("rate", 0.0, 0.3), "smb_churn": ("rate", 0.0, 0.2),
             "gm": ("rate", 0.2, 0.95), "new_arr": ("money", 0.0, None), "smb_new": ("money", 0.0, None),
             "sm": ("money", 0.0, None)}
    def fixups(lay):
        # actual ARR at the last actual month = the 12 actual billing months (keeps the
        # rolling-ARR identity valid when actual billings are perturbed)
        from ..task import Fixup

        return [Fixup(lay.key("arr", H - 1), [(1.0, lay.key("billed", p)) for p in range(H)])]

    return Bundle(domain="saas", noun="SaaS subscription revenue model (ARR, billings, deferred revenue)", spec=spec,
                  term_sheet="\n".join(ts), conventions=conventions, identities=ids, monotone=mono, kinds=kinds,
                  outputs=outputs, scale=max(arr_h[-1] / 50, 0.1), level=level, meta={"months": n},
                  fixups=fixups)
