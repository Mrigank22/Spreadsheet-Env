"""Leveraged buyout with a multi-tranche debt waterfall, cash sweep and returns.

Mechanics by level (each level adds to the previous one):

1. Term Loan B (1% amortisation) + senior notes (bullet); interest on opening balances.
2. + Term Loan A with amortisation as a % of original principal.
3. + revolver (drawn to protect minimum cash, repaid first) and an excess-cash
   sweep applied sequentially to TLA then TLB, capped by remaining balances.
4. + PIK notes (interest accrues to principal; tax-deductible, non-cash), a
   commitment fee on the undrawn revolver, and an excess-cash-flow sweep % that
   steps down with opening leverage (the grid in most term-loan agreements).
5. + interest on *average* balances (circular; iterative calculation) and a
   maintenance net-leverage covenant that steps down each year: a breach is
   cured by a sponsor equity injection, and returns use the actual sponsor
   cash flows (IRR of equity at close, cures, exit equity).

Returns: entry EV at an EBITDA multiple, fees, sources & uses (sponsor equity
funds the gap), exit at a multiple of final-year EBITDA, MOIC and IRR.
"""

from __future__ import annotations

import random
from typing import List

from ..model.spec import Calc, Line, ModelSpec, Scalar
from .framework import Bundle, IdSpec, MonoSpec

DOMAIN = "lbo"

LEVELS = {
    1: dict(tranches=["tlb", "notes"], revolver=False, sweep=False, pik=False, avg=False, n=5),
    2: dict(tranches=["tla", "tlb", "notes"], revolver=False, sweep=False, pik=False, avg=False, n=5),
    3: dict(tranches=["tla", "tlb", "notes"], revolver=True, sweep=True, pik=False, avg=False, n=6),
    4: dict(tranches=["tla", "tlb", "notes", "pik"], revolver=True, sweep=True, pik=True, avg=False, n=7,
            fee=True, grid=True),
    5: dict(tranches=["tla", "tlb", "notes", "pik"], revolver=True, sweep=True, pik=True, avg=True, n=7,
            fee=True, grid=True, cov=True),
}
NAMES = {"tla": "Term Loan A", "tlb": "Term Loan B", "notes": "Senior notes", "pik": "PIK notes",
         "rev": "Revolver"}


def _pct(x: float) -> str:
    return f"{100 * x:.2f}".rstrip("0").rstrip(".") + "%"


def generate(rng: random.Random, level: int) -> Bundle:
    cfg = LEVELS[level]
    u = rng.uniform
    n = cfg["n"]
    y0 = rng.randint(2024, 2026)
    periods = [f"FY{y0} (close)"] + [f"FY{y0 + i + 1}E" for i in range(n)]
    ebitda0 = round(10 ** u(1.6, 2.9), 1)  # $40m - $800m LTM EBITDA
    margin0 = u(0.12, 0.32)
    rev0 = round(ebitda0 / margin0, 1)
    g_near = u(0.03, 0.10)
    growth = [round(g_near + (0.025 - g_near) * i / max(1, n - 1) + rng.gauss(0, 0.005), 4) for i in range(n)]
    margins = [round(min(0.45, max(0.06, margin0 + u(-0.005, 0.012) * (i + 1))), 4) for i in range(n)]
    tr = cfg["tranches"]
    total_lev = u(4.5, 6.2)
    weights = {"tla": u(0.15, 0.30), "tlb": u(0.40, 0.60), "notes": u(0.15, 0.30), "pik": u(0.08, 0.15)}
    wsum = sum(weights[t] for t in tr)
    mult = {t: round(total_lev * weights[t] / wsum, 2) for t in tr}
    rate = {"tla": round(u(0.060, 0.080), 4), "tlb": round(u(0.075, 0.100), 4),
            "notes": round(u(0.085, 0.110), 4), "pik": round(u(0.110, 0.140), 4), "rev": round(u(0.060, 0.080), 4)}
    amort = {"tla": round(u(0.05, 0.15), 3), "tlb": round(rng.choice([0.01, 0.01, 0.0125, 0.025]), 4)}
    entry_mult = round(sum(mult.values()) + u(3.0, 6.0), 2)
    exit_mult = round(entry_mult + u(-1.5, 1.0), 2)
    sweep_pct = rng.choice([0.5, 0.75, 1.0])
    min_cash = round(rev0 * u(0.02, 0.05), 1)
    rev_commit = round(ebitda0 * u(0.5, 1.0), 1)
    avg = cfg["avg"]
    fee, grid, cov = cfg.get("fee", False), cfg.get("grid", False), cfg.get("cov", False)

    A, M = "Assumptions", "Model"
    scalars: List[Scalar] = [
        Scalar("entry_mult", "Entry multiple (EV / LTM EBITDA)", entry_mult, "x", "multiple"),
        Scalar("fee_pct", "Transaction fees (% of EV)", round(u(0.015, 0.03), 4), "%", "rate"),
        Scalar("min_cash", "Minimum cash balance", min_cash, "$m", "money"),
        Scalar("tax_rate", "Tax rate", round(u(0.21, 0.28), 3), "%", "tax"),
        Scalar("da_pct", "D&A (% of revenue)", round(u(0.02, 0.05), 4), "%", "rate"),
        Scalar("capex_pct", "Capex (% of revenue)", round(u(0.02, 0.06), 4), "%", "rate"),
        Scalar("nwc_pct", "Net working capital (% of revenue)", round(u(0.05, 0.15), 4), "%", "rate"),
        Scalar("exit_mult", "Exit multiple (EV / final-year EBITDA)", exit_mult, "x", "multiple"),
    ]
    for t in tr:
        scalars.append(Scalar(f"{t}_mult", f"{NAMES[t]} size (x LTM EBITDA)", mult[t], "x", "multiple"))
        scalars.append(Scalar(f"{t}_rate", f"{NAMES[t]} interest rate", rate[t], "%", "interest"))
        if t in amort:
            scalars.append(Scalar(f"{t}_amort", f"{NAMES[t]} amortisation (% of original principal / yr)",
                                  amort[t], "%", "rate"))
    if cfg["revolver"]:
        scalars.append(Scalar("rev_commit", "Revolver commitment", rev_commit, "$m", "money"))
        scalars.append(Scalar("rev_rate", "Revolver interest rate", rate["rev"], "%", "interest"))
    if fee:
        scalars.append(Scalar("commit_fee", "Revolver commitment fee (on the undrawn amount)",
                              rng.choice([0.0025, 0.00375, 0.005]), "%", "rate"))
    if grid:
        lv = round(u(4.6, 5.4), 2)
        for k, lab, v in [("lv_hi", "Sweep grid: top leverage threshold", lv),
                          ("lv_mid", "Sweep grid: middle leverage threshold", round(lv - 1.0, 2)),
                          ("lv_lo", "Sweep grid: bottom leverage threshold", round(lv - 2.0, 2))]:
            scalars.append(Scalar(k, lab + " (x)", v, "x", "multiple"))
        for k, lab, v in [("sw_hi", "Sweep % above the top threshold", 0.75),
                          ("sw_mid", "Sweep % above the middle threshold", 0.5),
                          ("sw_lo", "Sweep % above the bottom threshold", 0.25)]:
            scalars.append(Scalar(k, lab, v, "%", "rate"))
    elif cfg["sweep"]:
        scalars.append(Scalar("sweep_pct", "Excess cash flow sweep (%)", sweep_pct, "%", "rate"))

    def bal(t):
        return f"AVERAGE({{{t}_close[-1]}},{{{t}_close}})" if avg else f"{{{t}_close[-1]}}"

    bal_word = "the average of opening and closing" if avg else "the opening (prior-year closing)"
    lines: List[Line] = [
        Line("g_rev", "Revenue growth", A, "%", fc=None, hist="blank", forecast=growth, kind="rate"),
        Line("margin", "EBITDA margin", A, "%", fc=None, hist="blank", forecast=margins, kind="rate"),
    ]
    if cov:
        start = total_lev + u(1.0, 1.6)
        covs = [round(max(start - 0.5 * i, 3.0), 2) for i in range(n)]
        lines.append(Line("cov_max", "Maximum net leverage covenant (x EBITDA)", A, "x", fc=None, hist="blank",
                          forecast=covs, kind="ratio"))
    lines += [
        Line("rev", "Revenue", M, fc="{rev[-1]}*(1+{g_rev})", history=[rev0], section="Operations",
             desc="prior-year revenue x (1 + revenue growth)"),
        Line("ebitda", "EBITDA", M, fc="{rev}*{margin}", history=[ebitda0], desc="revenue x EBITDA margin"),
        Line("da", "D&A", M, fc="{rev}*{$da_pct}", hist="blank", desc="revenue x D&A %"),
        Line("capex", "Capital expenditure", M, fc="{rev}*{$capex_pct}", hist="blank", desc="revenue x capex %"),
        Line("nwc", "Net working capital", M, fc="{rev}*{$nwc_pct}", history=[round(rev0 * u(0.05, 0.15), 1)],
             desc="revenue x NWC %"),
        Line("d_nwc", "Increase in net working capital", M, fc="{nwc}-{nwc[-1]}", hist="blank",
             desc="current NWC - prior-year NWC"),
    ]
    cash_int_terms = []
    mand_terms = []
    for t in [x for x in ["tla", "tlb"] if x in tr]:
        lines.append(Line(f"{t}_mand", f"{NAMES[t]} - mandatory amortisation", M,
                          fc=f"MIN({{{t}_close[-1]}},{{{t}_close@0}}*{{${t}_amort}})", hist="blank",
                          section="Debt schedule",
                          desc=f"the smaller of the opening balance and original principal x amortisation %"))
        mand_terms.append(f"{{{t}_mand}}")
    lines_after_sweep = []
    if cfg["revolver"]:
        lines.append(Line("rev_close", "Revolver - closing balance", M,
                          fc="MIN({$rev_commit},MAX(0,{rev_close[-1]}-{cash_avail}))", history=[0.0],
                          desc="MIN(commitment, MAX(0, opening revolver - cash available))"))
        lines.append(Line("rev_net", "Revolver - net draw/(repayment)", M, fc="{rev_close}-{rev_close[-1]}",
                          hist="blank", desc="closing revolver - opening revolver"))
        lines.append(Line("rev_int", "Revolver - cash interest", M, fc=f"{bal('rev')}*{{$rev_rate}}",
                          hist="blank", desc=f"{bal_word} revolver balance x revolver rate"))
        cash_int_terms.append("{rev_int}")
        if fee:
            lines.append(Line("rev_fee", "Revolver - commitment fee", M,
                              fc=f"{{$commit_fee}}*({{$rev_commit}}-{bal('rev')})", hist="blank",
                              desc=f"fee % x (commitment - {bal_word} drawn balance)"))
            cash_int_terms.append("{rev_fee}")
    if cfg["sweep"]:
        lines.append(Line("excess", "Excess cash after revolver", M, fc="MAX(0,{cash_avail}+{rev_net})",
                          hist="blank", desc="MAX(0, cash available + revolver net draw)"))
        if grid:
            opening = "+".join(f"{{{t}_close[-1]}}" for t in tr) + "+{rev_close[-1]}"
            lines.append(Line("lev_open", "Opening leverage (x EBITDA)", M, unit="x", kind="ratio",
                              fc=f"({opening})/{{ebitda[-1]}}", hist="blank",
                              desc="all debt at the start of the year / prior-year EBITDA"))
            lines.append(Line("sweep_rate", "Sweep % for the year", M, unit="%", kind="ratio",
                              fc="IF({lev_open}>{$lv_hi},{$sw_hi},IF({lev_open}>{$lv_mid},{$sw_mid},"
                                 "IF({lev_open}>{$lv_lo},{$sw_lo},0)))", hist="blank",
                              desc="step-down grid on opening leverage"))
        lines.append(Line("sweep_avail", "Cash available for sweep", M,
                          fc="{excess}*" + ("{sweep_rate}" if grid else "{$sweep_pct}"), hist="blank",
                          desc="excess cash x sweep %"))
    for t in [x for x in ["tla", "tlb"] if x in tr]:
        if cfg["sweep"]:
            prior = "-{tla_sweep}" if (t == "tlb" and "tla" in tr) else ""
            lines.append(Line(f"{t}_sweep", f"{NAMES[t]} - cash sweep repayment", M,
                              fc=f"MIN({{sweep_avail}}{prior},{{{t}_close[-1]}}-{{{t}_mand}})", hist="blank",
                              desc="the smaller of the sweep cash still available and the balance remaining after "
                                   "mandatory amortisation"))
            close = f"{{{t}_close[-1]}}-{{{t}_mand}}-{{{t}_sweep}}"
        else:
            close = f"{{{t}_close[-1]}}-{{{t}_mand}}"
        lines.append(Line(f"{t}_close", f"{NAMES[t]} - closing balance", M, fc=close, hist="formula",
                          hist_fc=f"{{${t}_mult}}*{{ebitda}}",
                          desc="opening balance - mandatory amortisation" + (" - sweep" if cfg["sweep"] else "")
                               + "; at close: size multiple x LTM EBITDA"))
        lines.append(Line(f"{t}_int", f"{NAMES[t]} - cash interest", M, fc=f"{bal(t)}*{{${t}_rate}}", hist="blank",
                          desc=f"{bal_word} balance x rate"))
        cash_int_terms.append(f"{{{t}_int}}")
    lines.append(Line("notes_close", "Senior notes - closing balance", M, fc="{notes_close[-1]}", hist="formula",
                      hist_fc="{$notes_mult}*{ebitda}", desc="unchanged (bullet); at close: multiple x LTM EBITDA"))
    lines.append(Line("notes_int", "Senior notes - cash interest", M, fc=f"{bal('notes')}*{{$notes_rate}}",
                      hist="blank", desc=f"{bal_word} balance x coupon"))
    cash_int_terms.append("{notes_int}")
    if cfg["pik"]:
        lines.append(Line("pik_close", "PIK notes - closing balance", M, fc="{pik_close[-1]}*(1+{$pik_rate})",
                          hist="formula", hist_fc="{$pik_mult}*{ebitda}",
                          desc="opening balance x (1 + PIK rate); at close: multiple x LTM EBITDA"))
        lines.append(Line("pik_int", "PIK notes - accrued (non-cash) interest", M, fc="{pik_close[-1]}*{$pik_rate}",
                          hist="blank", desc="opening balance x PIK rate"))
    lines.append(Line("cash_int", "Total cash interest and fees" if fee else "Total cash interest", M,
                      fc="+".join(cash_int_terms), hist="blank", section="Cash flow",
                      desc="sum of cash interest on all cash-pay tranches" + (" + commitment fee" if fee else "")))
    ebt = "{ebitda}-{da}-{cash_int}" + ("-{pik_int}" if cfg["pik"] else "")
    lines.append(Line("ebt", "Pre-tax income", M, fc=ebt, hist="blank",
                      desc="EBITDA - D&A - cash interest" + (" - PIK interest" if cfg["pik"] else "")))
    lines.append(Line("tax", "Cash taxes", M, fc="MAX(0,{ebt})*{$tax_rate}", hist="blank",
                      desc="pre-tax income x tax rate, zero when pre-tax income is negative"))
    lines.append(Line("fcf", "Free cash flow before debt repayment", M,
                      fc="{ebitda}-{cash_int}-{tax}-{capex}-{d_nwc}", hist="blank",
                      desc="EBITDA - cash interest - taxes - capex - increase in NWC"))
    lines.append(Line("mand_total", "Total mandatory amortisation", M, fc="+".join(mand_terms) or "0", hist="blank",
                      desc="sum of mandatory amortisation"))
    if cfg["revolver"]:
        lines.append(Line("cash_avail", "Cash available after mandatory amortisation", M,
                          fc="{cash[-1]}+{fcf}-{mand_total}-{$min_cash}", hist="blank",
                          desc="opening cash + FCF - mandatory amortisation - minimum cash"))
        cash_fc = "{cash[-1]}+{fcf}-{mand_total}+{rev_net}" + "".join(
            f"-{{{t}_sweep}}" for t in ["tla", "tlb"] if t in tr and cfg["sweep"])
    else:
        cash_fc = "{cash[-1]}+{fcf}-{mand_total}"
    cash_desc = "opening cash + FCF - mandatory amortisation" + (
        " + revolver net draw - sweep repayments" if cfg["revolver"] else "")
    if cov:
        debt_all = "+".join(f"{{{t}_close}}" for t in tr) + "+{rev_close}"
        lines += [
            Line("cash_pre", "Cash before equity cure", M, fc=cash_fc, hist="blank", desc=cash_desc,
                 section="Covenant"),
            Line("tot_debt", "Total debt - closing", M, fc=debt_all, hist="formula",
                 desc="all tranches incl. PIK notes and revolver"),
            Line("cure", "Equity cure", M, fc="MAX(0,{tot_debt}-{cash_pre}-{cov_max}*{ebitda})", hist="blank",
                 desc="MAX(0, total debt - cash before cure - covenant x EBITDA)"),
            Line("cash", "Closing cash", M, fc="{cash_pre}+{cure}", hist="formula", hist_fc="{$min_cash}",
                 desc="cash before cure + equity cure; at close: minimum cash"),
            Line("net_lev", "Net leverage (x EBITDA)", M, unit="x", kind="ratio", fc="({tot_debt}-{cash})/{ebitda}",
                 hist="blank", desc="(total debt - closing cash) / EBITDA"),
        ]
    else:
        lines.append(Line("cash", "Closing cash", M, fc=cash_fc, hist="formula", hist_fc="{$min_cash}",
                          desc=cash_desc + "; at close: minimum cash"))
    # move the revolver/sweep rows below cash_avail in the sheet for readability? order is cosmetic
    debt_terms = [f"{{{t}_close@0}}" for t in tr]
    exit_debt = [f"{{{t}_close@last}}" for t in tr] + (["{rev_close@last}"] if cfg["revolver"] else [])
    calcs = [
        Calc("entry_ev", "Entry enterprise value", M, "{ebitda@0}*{$entry_mult}", section="Returns",
             desc="LTM EBITDA x entry multiple"),
        Calc("fees", "Transaction fees", M, "{entry_ev}*{$fee_pct}", desc="entry EV x fee %"),
        Calc("uses", "Total uses", M, "{entry_ev}+{fees}+{$min_cash}", desc="entry EV + fees + minimum cash"),
        Calc("debt_raised", "Total debt raised", M, "+".join(debt_terms), desc="sum of all tranches at close"),
        Calc("sponsor_eq", "Sponsor equity", M, "{uses}-{debt_raised}", desc="total uses - total debt raised"),
        Calc("exit_ev", "Exit enterprise value", M, "{ebitda@last}*{$exit_mult}",
             desc="final-year EBITDA x exit multiple"),
        Calc("net_debt_exit", "Net debt at exit", M, "+".join(exit_debt) + "-{cash@last}",
             desc="all debt outstanding at the end of the final year (incl. PIK and revolver) - closing cash"),
        Calc("exit_eq", "Exit equity value", M, "{exit_ev}-{net_debt_exit}", desc="exit EV - net debt at exit"),
    ]
    if cov:
        lines.append(Line("eq_flow", "Sponsor cash flows", M, fc="-{cure}", fc_last="-{cure}+{exit_eq}",
                          hist="formula", hist_fc="-{sponsor_eq}", section="Sponsor returns",
                          desc="close: - sponsor equity; each year: - equity cure; final year: + exit equity"))
        calcs += [
            Calc("eq_total", "Total sponsor equity invested", M, "{sponsor_eq}+SUM({cure@fc})",
                 desc="sponsor equity + all equity cures"),
            Calc("moic", "Sponsor MOIC", M, "{exit_eq}/{eq_total}", unit="x", kind="ratio",
                 desc="exit equity value / total sponsor equity invested"),
            Calc("irr", "Sponsor IRR", M, "IRR({eq_flow@all})", unit="%", kind="ratio",
                 desc="IRR of the sponsor cash flows"),
        ]
    else:
        calcs += [
            Calc("moic", "Sponsor MOIC", M, "{exit_eq}/{sponsor_eq}", unit="x", kind="ratio",
                 desc="exit equity value / sponsor equity"),
            Calc("irr", "Sponsor IRR", M, f"{{moic}}^(1/{n})-1", unit="%", kind="ratio",
                 desc=f"MOIC ^ (1 / {n} years) - 1"),
        ]
    spec = ModelSpec(title=f"LBO model", periods=periods, n_hist=1, sheets=[A, M], scalars=scalars,
                     lines=lines, calcs=calcs, iterative=avg)

    # ---------------- term sheet (business language) ----------------------------
    ts = [
        "TRANSACTION. A sponsor acquires the company at the entry multiple times LTM EBITDA (the "
        "enterprise value). Transaction fees are a percentage of enterprise value. The company must hold the "
        "minimum cash balance at close. Total uses = enterprise value + fees + minimum cash. Sponsor equity funds "
        "the part of total uses not funded by debt.",
        "FINANCING (sizes are multiples of LTM EBITDA, drawn in full at close):",
    ]
    for t in tr:
        if t == "tla":
            ts.append(f"- Term Loan A: cash interest at its fixed rate on {bal_word} balance; mandatory "
                      "amortisation each year of the amortisation % times the ORIGINAL principal, never more than "
                      "the balance outstanding.")
        elif t == "tlb":
            ts.append(f"- Term Loan B: cash interest at its fixed rate on {bal_word} balance; mandatory "
                      "amortisation each year of the amortisation % times the ORIGINAL principal, never more than "
                      "the balance outstanding.")
        elif t == "notes":
            ts.append(f"- Senior notes: cash coupon at the fixed rate on {bal_word} balance; repaid in full at "
                      "maturity, which is after the projection (no repayment in the model).")
        elif t == "pik":
            ts.append("- PIK notes: no cash interest; interest at the PIK rate on the opening balance accrues to "
                      "principal every year. Accrued PIK interest is tax-deductible.")
    if cfg["revolver"]:
        ts.append(f"- Revolver: undrawn at close; cash interest at its rate on {bal_word} drawn balance. At each "
                  "year end, cash available = opening cash + free cash flow - mandatory amortisation - minimum "
                  "cash. If this is negative, the revolver is drawn to cover the shortfall (up to the commitment); "
                  "if positive, it first repays any revolver balance." + (
                      f" A commitment fee is paid in cash on the undrawn commitment (commitment - {bal_word} drawn "
                      "balance); it is part of total cash interest and fees, and tax-deductible." if fee else ""))
    if grid:
        ts.append("SWEEP GRID. Opening leverage = all debt at the start of the year (every tranche incl. PIK notes, "
                  "plus the revolver) / prior-year EBITDA. Sweep % = the top-tier % if opening leverage is above "
                  "the top threshold; else the middle-tier % if above the middle threshold; else the bottom-tier % "
                  "if above the bottom threshold; else 0%.")
    if cfg["sweep"]:
        ts.append("CASH SWEEP. Excess cash = cash available plus the revolver net draw (net repayment counts as "
                  "negative), floored at zero. The sweep % of excess cash prepays term loans at year end: first "
                  "Term Loan A, then Term Loan B with whatever is left, each capped at its balance remaining after "
                  "mandatory amortisation. Cash not swept stays on balance sheet.")
    ts.append("OPERATIONS. Revenue grows at the yearly growth rate; EBITDA = revenue x EBITDA margin for the year. "
              "D&A, capex and net working capital are percentages of revenue; an increase in NWC uses cash. Taxes "
              "= tax rate x (EBITDA - D&A - cash interest" + (" - PIK interest" if cfg["pik"] else "")
              + "), zero if that amount is negative. Free cash flow before debt repayment = EBITDA - cash interest "
              "- taxes - capex - increase in NWC.")
    if cov:
        ts.append("COVENANT. At each year end, net leverage = (total debt incl. PIK notes and revolver - closing "
                  "cash) / EBITDA must not exceed that year's maximum. If it would (using cash before any cure), "
                  "the sponsor injects just enough equity as cash to bring it to the maximum: equity cure = MAX(0, "
                  "total debt - cash before cure - maximum x EBITDA). The cure is added to closing cash after the "
                  "sweep (it is not swept that year).")
    ts.append(f"EXIT at the end of {periods[-1]}: exit EV = exit multiple x final-year EBITDA; exit equity = exit "
              "EV - (all debt outstanding incl. " + ("PIK notes and revolver " if cfg["pik"] else "")
              + "- closing cash). " + (
                  f"MOIC = exit equity / sponsor equity; IRR = MOIC^(1/{n}) - 1." if not cov else
                  "MOIC = exit equity / (sponsor equity + all equity cures). Sponsor cash flows: - sponsor equity at "
                  "close, - the equity cure each year, + exit equity in the final year; IRR = IRR of those flows "
                  "(one value per column, close included)."))
    term_sheet = "\n".join(ts)
    conventions = [
        "All flows occur at year end. The first column is the closing date of the transaction (balances at close).",
        "Debt balances, repayments and interest are positive numbers; repayments reduce balances.",
        f"Interest is charged on {bal_word} balance of each tranche.",
        "Sizes, rates and percentages are on the Assumptions sheet; growth and margins are given per year.",
    ]
    if cfg["revolver"]:
        conventions.append("Revolver net draw/(repayment) is positive when the revolver is drawn.")

    # ---------------- identities, relations, outputs -------------------------------
    ids = [IdSpec("sources_equal_uses", "sponsor equity + debt raised = total uses",
                  [(1, "sponsor_eq", 0), (1, "debt_raised", 0), (-1, "uses", 0)], when="once"),
           IdSpec("exit_equity_bridge", "exit equity = exit EV - net debt at exit",
                  [(1, "exit_eq", 0), (-1, "exit_ev", 0), (1, "net_debt_exit", 0)], when="once"),
           IdSpec("notes_bullet", "senior notes unchanged", [(1, "notes_close", 0), (-1, "notes_close", -1)])]
    for t in [x for x in ["tla", "tlb"] if x in tr]:
        terms = [(1, f"{t}_close", 0), (-1, f"{t}_close", -1), (1, f"{t}_mand", 0)]
        if cfg["sweep"]:
            terms.append((1, f"{t}_sweep", 0))
        ids.append(IdSpec(f"{t}_rollforward", f"{NAMES[t]} roll-forward", terms))
    if cfg["pik"]:
        ids.append(IdSpec("pik_rollforward", "PIK balance grows by accrued PIK interest",
                          [(1, "pik_close", 0), (-1, "pik_close", -1), (-1, "pik_int", 0)]))
    if cfg["revolver"]:
        ids.append(IdSpec("revolver_rollforward", "revolver roll-forward",
                          [(1, "rev_close", 0), (-1, "rev_close", -1), (-1, "rev_net", 0)]))
    cash_terms = [(1, "cash", 0), (-1, "cash", -1), (-1, "fcf", 0), (1, "mand_total", 0)]
    if cfg["revolver"]:
        cash_terms.append((-1, "rev_net", 0))
    if cfg["sweep"]:
        cash_terms += [(1, f"{t}_sweep", 0) for t in ["tla", "tlb"] if t in tr]
    if cov:
        cash_terms.append((-1, "cure", 0))
    ids.append(IdSpec("cash_rollforward", "closing cash = opening cash + FCF - repayments + revolver draw",
                      cash_terms))
    mono = [MonoSpec("moic_rises_with_exit_multiple", "moic", "exit_mult", 0.5, 1),
            MonoSpec("moic_falls_with_entry_multiple", "moic", "entry_mult", 0.5, -1)]
    outputs = [("fcf", "Free cash flow before debt repayment"), ("cash_int", "Total cash interest"),
               ("tax", "Cash taxes"), ("cash", "Closing cash")]
    outputs += [(f"{t}_close", f"{NAMES[t]} closing balance") for t in tr]
    if cfg["revolver"]:
        outputs.append(("rev_close", "Revolver closing balance"))
    if grid:
        outputs.append(("sweep_rate", "Sweep % for the year"))
    if cov:
        outputs += [("cure", "Equity cure"), ("net_lev", "Net leverage")]
    outputs += [("sponsor_eq", "Sponsor equity"), ("exit_eq", "Exit equity value"), ("moic", "Sponsor MOIC"),
                ("irr", "Sponsor IRR")]
    kinds = {
        "entry_mult": ("multiple", 4.0, 16.0), "exit_mult": ("multiple", 3.0, 16.0),
        "fee_pct": ("rate", 0.0, 0.06), "tax_rate": ("tax", 0.0, 0.45),
        "sweep_pct": ("rate", 0.0, 1.0), "pik_rate": ("interest", 0.0, 0.25),
        "commit_fee": ("rate", 0.0, 0.02), "lv_hi": ("multiple", 0.5, 10.0), "lv_mid": ("multiple", 0.5, 10.0),
        "lv_lo": ("multiple", 0.5, 10.0), "sw_hi": ("rate", 0.0, 1.0), "sw_mid": ("rate", 0.0, 1.0),
        "sw_lo": ("rate", 0.0, 1.0), "cov_max": ("multiple", 1.0, 16.0),
        "g_rev": ("growth", None, None), "margin": ("rate", 0.02, 0.6),
    }
    for t in tr:
        kinds[f"{t}_mult"] = ("multiple", 0.2, 4.0)
        if t in amort:
            kinds[f"{t}_amort"] = ("rate", 0.0, 0.3)
    return Bundle(domain="lbo", noun="leveraged buyout (LBO) model with a debt schedule", spec=spec,
                  term_sheet=term_sheet, conventions=conventions, identities=ids, monotone=mono, kinds=kinds,
                  outputs=outputs, scale=rev0, level=level, meta={"tranches": tr, "years": n})
