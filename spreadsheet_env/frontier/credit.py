"""Consumer-loan portfolio: delinquency roll rates and the credit-loss allowance.

A monthly Markov roll-rate model of a consumer instalment portfolio (the
workhorse of retail-bank and card credit forecasting) with an allowance
built by the roll-rate (flow-to-loss) method. That method measures the losses
already in the delinquency pipeline (the classic incurred-loss technique);
the CECL (ASC 326) and IFRS 9 mechanics added at higher levels -- a
reasonable-and-supportable forecast with straight-line reversion, staging and
probability-weighted scenarios -- are applied to its roll rates, but the
coverage it produces is not a full lifetime estimate.

Buckets: current, 30-59, 60-89 and 90+ days past due. Each month current
loans pay down, a share of what is left rolls to 30 days; in each delinquent
bucket a share rolls on (90+: is charged off) and the rest cures to current.

1. balance roll-forward, charge-offs, recoveries, net credit losses.
2. + allowance by the flow-to-loss method (loss given default x balance x
   product of the roll rates to charge-off) and the provision that makes the
   allowance roll forward (opening + provision - net charge-offs = closing).
3. + interest income with non-accrual on 90+ and a macro multiplier on the
   roll rates, capped so a rate never exceeds 100%.
4. + CECL reversion: the macro multiplier is used for a reasonable-and-
   supportable period, then reverts straight-line to 1.0; IFRS 9 staging
   (stage 1 = current, stage 2 = 30-89, stage 3 = 90+) and coverage.
5. + the allowance is probability-weighted over base, upside and downside
   macro paths (IFRS 9 5.5.17); recoveries arrive one month after charge-off.
"""

from __future__ import annotations

import random
from typing import List

from ..model.spec import Calc, Line, ModelSpec, Scalar
from .framework import Bundle, IdSpec, MonoSpec

DOMAIN = "credit"

LEVELS = {
    1: dict(n=12, allow=False, macro=False, revert=False, scen=False),
    2: dict(n=12, allow=True, macro=False, revert=False, scen=False),
    3: dict(n=18, allow=True, macro=True, revert=False, scen=False),
    4: dict(n=24, allow=True, macro=True, revert=True, scen=False),
    5: dict(n=24, allow=True, macro=True, revert=True, scen=True),
}
BUCKETS = ("cur", "d30", "d60", "d90")
ROLL = {"cur": "rc", "d30": "r30", "d60": "r60", "d90": "r90"}
NAME = {"cur": "Current", "d30": "30-59 dpd", "d60": "60-89 dpd", "d90": "90+ dpd"}


def _macro_path(rng: random.Random, n: int, shock: float) -> List[float]:
    """A recession-shaped multiplier path: rises to a peak, then eases."""
    peak = rng.randint(3, max(4, n // 3))
    out = []
    for t in range(1, n + 1):
        m = 1 + shock * (t / peak if t <= peak else max(0.0, 1 - (t - peak) / (1.5 * peak)))
        out.append(round(m * rng.uniform(0.98, 1.02), 4))
    return out


def generate(rng: random.Random, level: int) -> Bundle:
    cfg = LEVELS[level]
    u = rng.uniform
    n = cfg["n"]
    periods = ["M0 (opening)"] + [f"M{i}" for i in range(1, n + 1)]
    size = u(400, 1500)
    rates = {"rc": round(u(0.015, 0.035), 4), "r30": round(u(0.25, 0.45), 4), "r60": round(u(0.45, 0.65), 4),
             "r90": round(u(0.65, 0.85), 4)}
    # opening buckets near the chain's steady state
    cur0 = round(size, 1)
    d30 = round(cur0 * rates["rc"] * u(0.8, 1.2), 1)
    d60 = round(d30 * rates["r30"] * u(0.8, 1.2), 1)
    d90 = round(d60 * rates["r60"] * u(0.8, 1.2), 1)
    pay = round(u(0.025, 0.045), 4)
    new = [round(size * pay * u(0.9, 1.25), 1) for _ in range(n)]

    A, M = "Assumptions", "Model"
    scalars = [Scalar("pay", "Monthly principal payment rate (current loans)", pay, "%", "rate")]
    scalars += [Scalar(k, f"Roll rate: {lab}", v, "%", "rate") for k, lab, v in [
        ("rc", "current to 30-59 dpd", rates["rc"]), ("r30", "30-59 to 60-89 dpd", rates["r30"]),
        ("r60", "60-89 to 90+ dpd", rates["r60"]), ("r90", "90+ dpd to charge-off", rates["r90"])]]
    scalars.append(Scalar("rec", "Recovery rate on charge-offs", round(u(0.08, 0.25), 3), "%", "rate"))
    if cfg["macro"]:
        scalars.append(Scalar("yld", "Portfolio yield (annual)", round(u(0.09, 0.2), 4), "%", "rate"))
    if cfg["revert"]:
        rs = rng.randint(6, 10)
        scalars += [Scalar("rs", "Reasonable and supportable period (months)", float(rs), "months", "fixed"),
                    Scalar("rev", "Straight-line reversion period (months)", float(rng.choice([6, 9, 12])), "months",
                           "fixed")]
    if cfg["scen"]:
        w_up, w_dn = rng.choice([(0.2, 0.3), (0.25, 0.25), (0.15, 0.35), (0.2, 0.2)])
        scalars += [Scalar("w_up", "Scenario weight: upside", w_up, "%", "rate"),
                    Scalar("w_dn", "Scenario weight: downside", w_dn, "%", "rate")]

    lines: List[Line] = [Line("new", "New originations", A, hist="blank", forecast=new)]
    scen_ids = [""]
    if cfg["macro"]:
        lines.append(Line("macro", "Macro multiplier on roll rates (base)", A, unit="x", kind="ratio", hist="blank",
                          forecast=_macro_path(rng, n, u(0.15, 0.5))))
    if cfg["scen"]:
        lines += [Line("macro_up", "Macro multiplier on roll rates (upside)", A, unit="x", kind="ratio", hist="blank",
                       forecast=_macro_path(rng, n, u(-0.15, 0.05))),
                  Line("macro_dn", "Macro multiplier on roll rates (downside)", A, unit="x", kind="ratio",
                       hist="blank", forecast=_macro_path(rng, n, u(0.6, 1.2)))]
        scen_ids = ["", "_up", "_dn"]

    # ---------------- model ---------------------------------------------------------
    if cfg["revert"]:
        lines.append(Line("month", "Month number", M, unit="#", kind="ratio", history=[0.0], fc="{month[-1]}+1",
                          section="Timeline"))
    sfx_name = {"": "base", "_up": "upside", "_dn": "downside"}
    if cfg["macro"]:
        for sx in scen_ids:
            if cfg["revert"]:
                fc = (f"IF({{month}}<={{$rs}},{{macro{sx}}},IF({{month}}<{{$rs}}+{{$rev}},INDEX({{macro{sx}@fc}},{{$rs}})"
                      f"+(1-INDEX({{macro{sx}@fc}},{{$rs}}))*({{month}}-{{$rs}})/{{$rev}},1))")
                desc = ("the macro multiplier up to the end of the reasonable-and-supportable period; then straight-"
                        "line from its value in that last month to 1.0 over the reversion period; 1.0 afterwards")
            else:
                fc, desc = f"{{macro{sx}}}", "the macro multiplier"
            lines.append(Line(f"fac{sx}", f"Roll-rate multiplier ({sfx_name[sx]})" if cfg["scen"] else
                              "Roll-rate multiplier", M, unit="x", kind="ratio", fc=fc, hist="blank", desc=desc,
                              section="Roll rates" if sx == "" else ""))
        for sx in scen_ids:
            for b in BUCKETS:
                r = ROLL[b]
                lines.append(Line(f"{r}_t{sx}", f"Roll rate {NAME[b]}" + (f" ({sfx_name[sx]})" if cfg["scen"] else ""),
                                  M, unit="%", kind="ratio", fc=f"MIN(1,{{${r}}}*{{fac{sx}}})", hist="blank",
                                  desc="MIN(100%, base roll rate x multiplier)"))
        rate = {b: f"{{{ROLL[b]}_t}}" for b in BUCKETS}
    else:
        rate = {b: f"{{${ROLL[b]}}}" for b in BUCKETS}

    lines += [
        Line("c_pay", "Principal payments (current loans)", M, fc="{cur[-1]}*{$pay}", hist="blank",
             desc="opening current x payment rate", section="Flows"),
        Line("c_roll", "Current rolling to 30-59 dpd", M, fc="({cur[-1]}-{c_pay})*" + rate["cur"], hist="blank",
             desc="(opening current - payments) x roll rate"),
        Line("d30_roll", "30-59 rolling to 60-89 dpd", M, fc="{d30[-1]}*" + rate["d30"], hist="blank",
             desc="opening 30-59 x roll rate"),
        Line("d60_roll", "60-89 rolling to 90+ dpd", M, fc="{d60[-1]}*" + rate["d60"], hist="blank",
             desc="opening 60-89 x roll rate"),
        Line("co", "Charge-offs (90+ rolling out)", M, fc="{d90[-1]}*" + rate["d90"], hist="blank" if not cfg["scen"]
             else "input", history=[round(d90 * rates["r90"] * u(0.85, 1.15), 1)] if cfg["scen"] else None,
             desc="opening 90+ x roll rate"),
        Line("cures", "Cures back to current", M,
             fc="{d30[-1]}-{d30_roll}+{d60[-1]}-{d60_roll}+{d90[-1]}-{co}", hist="blank",
             desc="delinquent balances that did not roll on"),
        Line("cur", "Current - closing", M, history=[cur0], fc="{cur[-1]}-{c_pay}-{c_roll}+{cures}+{new}",
             desc="opening - payments - roll to 30 + cures + new originations", section="Balances"),
        Line("d30", "30-59 dpd - closing", M, history=[d30], fc="{c_roll}", desc="current rolling to 30-59"),
        Line("d60", "60-89 dpd - closing", M, history=[d60], fc="{d30_roll}", desc="30-59 rolling to 60-89"),
        Line("d90", "90+ dpd - closing", M, history=[d90], fc="{d60_roll}", desc="60-89 rolling to 90+"),
        Line("tot", "Total loans - closing", M, fc="{cur}+{d30}+{d60}+{d90}", hist="formula",
             desc="sum of the buckets"),
        Line("recov", "Recoveries", M, fc="{$rec}*{co" + ("[-1]" if cfg["scen"] else "") + "}", hist="blank",
             desc="recovery rate x " + ("last month's" if cfg["scen"] else "this month's") + " charge-offs",
             section="Credit losses"),
        Line("nco", "Net charge-offs", M, fc="{co}-{recov}", hist="blank", desc="charge-offs - recoveries"),
    ]
    if cfg["allow"]:
        for sx in scen_ids:
            def rr(b, sx=sx):
                return f"{{{ROLL[b]}_t{sx}}}" if cfg["macro"] else f"{{${ROLL[b]}}}"
            flow = (f"{{cur}}*{rr('cur')}*{rr('d30')}*{rr('d60')}*{rr('d90')}+{{d30}}*{rr('d30')}*{rr('d60')}*{rr('d90')}"
                    f"+{{d60}}*{rr('d60')}*{rr('d90')}+{{d90}}*{rr('d90')}")
            lines.append(Line(f"allow{sx}", "Allowance" + (f" ({sfx_name[sx]})" if cfg["scen"] else ""), M,
                              fc=f"(1-{{$rec}})*({flow})", hist="blank" if (cfg["macro"] or cfg["scen"]) else "formula",
                              desc="(1 - recovery rate) x sum over buckets of balance x product of this month's roll "
                                   "rates from that bucket to charge-off",
                              section="Allowance" if sx == "" else ""))
        main = "allow"
        if cfg["scen"]:
            lines.append(Line("allow_w", "Allowance (probability-weighted)", M,
                              fc="(1-{$w_up}-{$w_dn})*{allow}+{$w_up}*{allow_up}+{$w_dn}*{allow_dn}",
                              hist="blank", desc="base weight = 1 - upside - downside"))
            main = "allow_w"
        # allowance balance: opening column given (an input) when the multiplier path makes it period-specific
        hist_bal = cfg["macro"] or cfg["scen"]
        lines += [
            Line("allow_bal", "Allowance for credit losses - closing", M, fc=f"{{{main}}}",
                 hist="input" if hist_bal else "formula",
                 history=[round((d90 * rates["r90"] + d60 * rates["r60"] * rates["r90"] + d30 * rates["r30"]
                                 * rates["r60"] * rates["r90"]) * 0.85, 1)] if hist_bal else None,
                 hist_fc=None if hist_bal else f"{{{main}}}", desc="the " + ("probability-weighted " if cfg["scen"]
                                                                          else "") + "allowance"),
            Line("prov", "Provision expense", M, fc="{allow_bal}-{allow_bal[-1]}+{nco}", hist="blank",
                 desc="closing - opening allowance + net charge-offs"),
        ]
    if cfg["macro"]:
        lines += [
            Line("int_inc", "Interest income", M, fc="{$yld}/12*({cur[-1]}+{d30[-1]}+{d60[-1]})", hist="blank",
                 desc="yield / 12 x opening accruing balances (90+ is non-accrual)", section="Earnings"),
            Line("margin", "Risk-adjusted margin", M, fc="{int_inc}-{prov}", hist="blank",
                 desc="interest income - provision"),
        ]
    if cfg["revert"]:
        lines += [
            Line("s1", "Stage 1 (current)", M, fc="{cur}", hist="formula", desc="current", section="IFRS 9 staging"),
            Line("s2", "Stage 2 (30-89 dpd)", M, fc="{d30}+{d60}", hist="formula", desc="30-59 + 60-89"),
            Line("s3", "Stage 3 (90+ dpd)", M, fc="{d90}", hist="formula", desc="90+"),
            Line("cov", "Coverage ratio", M, unit="%", kind="ratio", fc="{allow_bal}/{tot}", hist="blank",
                 desc="allowance / total loans"),
        ]
    calcs = [Calc("nco_total", "Total net charge-offs", M, "SUM({nco@fc})", section="Results",
                  desc="sum of net charge-offs"),
             Calc("loss_rate", "Cumulative net loss rate", M, "{nco_total}/{tot@0}", unit="%", kind="ratio",
                  desc="total net charge-offs / opening total loans")]
    if cfg["allow"]:
        calcs.append(Calc("prov_total", "Total provision expense", M, "SUM({prov@fc})", desc="sum of provisions"))
    spec = ModelSpec(title="Consumer-loan roll-rate and allowance model", periods=periods, n_hist=1, sheets=[A, M],
                     scalars=scalars, lines=lines, calcs=calcs)

    # ---------------- term sheet ----------------------------------------------------------
    rr_txt = "the roll rates" if not cfg["macro"] else "this month's roll rates"
    ts = ["PORTFOLIO. Four buckets: current, 30-59, 60-89 and 90+ days past due; the opening column holds the "
          "opening balances. Each month, using the OPENING balances:",
          "- Principal payments = opening current x payment rate. Current rolling to 30-59 = (opening current - "
          "payments) x " + ("current roll rate" if not cfg["macro"] else "this month's current roll rate") + ".",
          "- Each delinquent bucket: opening balance x its roll rate moves on (to the next bucket; from 90+ it is "
          "charged off); the rest cures back to current.",
          "- Closing current = opening - payments - roll to 30-59 + all cures + new originations; each delinquent "
          "bucket closes at what rolled into it this month.",
          "- Recoveries = recovery rate x " + ("LAST month's charge-offs (the opening column holds last month's)"
                                              if cfg["scen"] else "this month's charge-offs") + "; net charge-offs = "
          "charge-offs - recoveries."]
    if cfg["macro"]:
        ts.append("ROLL RATES. Each month's roll rate = MIN(100%, base roll rate x roll-rate multiplier)" + (
            " for each macro scenario" if cfg["scen"] else "") + "." + (
            " The multiplier equals the macro multiplier for months up to and including the reasonable-and-"
            "supportable period; after it, it moves in a straight line from the macro multiplier of the last "
            "supportable month back to 1.0, reaching 1.0 at the end of the reversion period (month = period + "
            "reversion) and staying there. With R = the supportable period, V = the reversion period and m = the "
            "month number: multiplier = m(R) + (1 - m(R)) x (month - R) / V for R < month < R + V."
            if cfg["revert"] else " The multiplier is the macro multiplier."))
    if cfg["allow"]:
        ts.append("ALLOWANCE (flow-to-loss method): (1 - recovery rate) x [current x rc x r30 x r60 x r90 + 30-59 x "
                  "r30 x r60 x r90 + 60-89 x r60 x r90 + 90+ x r90], using closing balances and " + rr_txt + "."
                  + (" Compute it for the base, upside and downside multiplier paths; the allowance held is their "
                     "probability-weighted average (base weight = 1 - upside - downside); the loan balances follow "
                     "the base path." if cfg["scen"] else "")
                  + (" The opening allowance is given." if cfg["macro"] else " Include the opening column.")
                  + " Provision expense = closing allowance - opening allowance + net charge-offs.")
    if cfg["macro"]:
        ts.append("EARNINGS. Interest income = yield / 12 x opening (current + 30-59 + 60-89); 90+ loans are on "
                  "non-accrual. Risk-adjusted margin = interest income - provision expense.")
    if cfg["revert"]:
        ts.append("STAGING: stage 1 = current, stage 2 = 30-89 days past due, stage 3 = 90+. Coverage = allowance / "
                  "total loans.")
    ts.append("RESULTS: cumulative net loss rate = total net charge-offs / opening total loans.")
    conventions = ["Monthly periods; all amounts in $m.", "Rates on Assumptions are monthly unless marked annual."]

    ids = [IdSpec("balance_conservation", "closing loans = opening - payments - charge-offs + new",
                  [(1, "tot", 0), (-1, "tot", -1), (1, "c_pay", 0), (1, "co", 0), (-1, "new", 0)])]
    if cfg["allow"]:
        ids.append(IdSpec("allowance_rollforward", "closing allowance = opening + provision - net charge-offs",
                          [(1, "allow_bal", 0), (-1, "allow_bal", -1), (-1, "prov", 0), (1, "nco", 0)]))
    if cfg["revert"]:
        ids.append(IdSpec("stages_sum", "stages add up to total loans",
                          [(1, "s1", 0), (1, "s2", 0), (1, "s3", 0), (-1, "tot", 0)]))
    mono = [MonoSpec("losses_rise_with_chargeoff_roll", "nco_total", "r90", 0.02, 1),
            MonoSpec("losses_fall_with_recovery_rate", "nco_total", "rec", 0.02, -1)]
    if cfg["allow"]:
        mono.append(MonoSpec("provisions_rise_with_current_roll", "prov_total", "rc", 0.005, 1))
    outputs = [("c_pay", "Principal payments"), ("co", "Charge-offs"), ("new", "New originations"),
               ("tot", "Total loans - closing"), ("d90", "90+ dpd - closing"), ("nco", "Net charge-offs")]
    if cfg["allow"]:
        outputs += [("allow_bal", "Allowance for credit losses - closing"), ("prov", "Provision expense")]
    if cfg["macro"]:
        outputs.append(("int_inc", "Interest income"))
    if cfg["revert"]:
        outputs += [("s1", "Stage 1"), ("s2", "Stage 2"), ("s3", "Stage 3"), ("cov", "Coverage ratio")]
    if cfg["scen"]:
        outputs += [("allow", "Allowance (base)"), ("allow_dn", "Allowance (downside)")]
    outputs.append(("loss_rate", "Cumulative net loss rate"))
    mult = ("count", 0.0, None)
    kinds = {"rc": ("rate", 0.0, 0.3), "r30": ("rate", 0.0, 1.0), "r60": ("rate", 0.0, 1.0), "r90": ("rate", 0.0, 1.0),
             "pay": ("rate", 0.0, 0.2), "rec": ("rate", 0.0, 0.9), "yld": ("interest", 0.0, None),
             "macro": mult, "macro_up": mult, "macro_dn": mult, "w_up": ("rate", 0.0, 0.45),
             "w_dn": ("rate", 0.0, 0.45)}
    return Bundle(domain=DOMAIN, noun="consumer-loan roll-rate and allowance model", spec=spec,
                  term_sheet="\n".join(ts), conventions=conventions, identities=ids, monotone=mono, kinds=kinds,
                  outputs=outputs, scale=size, level=level)
