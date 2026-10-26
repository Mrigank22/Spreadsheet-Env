"""Structured finance: a monthly ABS collateral pool and its note waterfall.

Collateral (SIFMA standard formulas): monthly default rate MDR = 1-(1-CDR)^(1/12)
on the opening performing balance; scheduled amortisation as a level payment
(PMT) on the remaining term; prepayments SMM = 1-(1-CPR)^(1/12) on the balance
after defaults and scheduled principal; recoveries and losses realised after a
recovery lag (INDEX into the defaults row).

Notes: interest paid by class from interest collections (after the servicing
fee); principal collections (+ excess spread used to cover realised losses)
paid to the notes. Mechanics by level:

1. 24 months, class A + B, no defaults, sequential principal.
2. 36 months, + defaults, severity, recovery lag.
3. 48 months, + servicing fee, excess spread covers losses, pro-rata principal
   while the overcollateralisation (OC) test passes, sequential when it fails.
4. 60 months, + class C, and unpaid class B interest carried forward.
5. + PSA-style prepayment ramp (CPR rises linearly to its full rate by month 30)
   and the weighted average life (WAL) of class A; a non-curable cumulative
   net loss (CNL) trigger (once breached, principal is sequential for good);
   a reserve account (target = MAX(% of the current pool, floor % of the
   original pool) while notes are outstanding) that covers Class A interest
   shortfalls and is replenished from cash that would go to the residual.
"""

from __future__ import annotations

import random
from typing import List

from ..model.spec import Calc, Line, ModelSpec, Scalar
from .framework import Bundle, IdSpec, MonoSpec

DOMAIN = "abs"

LEVELS = {
    1: dict(n=24, classes=["a", "b"], defaults=False, fee=False, prorata=False, carry=False, ramp=False),
    2: dict(n=36, classes=["a", "b"], defaults=True, fee=False, prorata=False, carry=False, ramp=False),
    3: dict(n=48, classes=["a", "b"], defaults=True, fee=True, prorata=True, carry=False, ramp=False),
    4: dict(n=60, classes=["a", "b", "c"], defaults=True, fee=True, prorata=True, carry=True, ramp=False),
    5: dict(n=60, classes=["a", "b", "c"], defaults=True, fee=True, prorata=True, carry=True, ramp=True,
            cnl=True, reserve=True),
}
NAME = {"a": "Class A", "b": "Class B", "c": "Class C"}


def generate(rng: random.Random, level: int) -> Bundle:
    cfg = LEVELS[level]
    u = rng.uniform
    n = cfg["n"]
    cls = cfg["classes"]
    pool0 = round(10 ** u(2.3, 3.2), 1)  # $200m - $1.6bn
    wam = n + rng.randint(12, 48)
    oc0 = u(0.04, 0.12)  # initial overcollateralisation
    split = {"a": [0.82], "b": [0.18]} if len(cls) == 2 else {"a": [0.75], "b": [0.15], "c": [0.10]}
    notes0 = {c: round(pool0 * (1 - oc0) * split[c][0], 1) for c in cls}
    coupon = {"a": round(u(0.040, 0.060), 4), "b": round(u(0.060, 0.085), 4), "c": round(u(0.085, 0.120), 4)}
    A, M = "Assumptions", "Model"
    periods = ["Closing"] + [f"M{i + 1}" for i in range(n)]
    scalars = [
        Scalar("wac", "Collateral coupon (WAC, annual)", round(u(0.07, 0.14), 4), "%", "interest"),
        Scalar("wam", "Remaining term at closing (months)", float(wam), "m", "fixed"),
        Scalar("cpr", "Prepayment speed (CPR, annual)", round(u(0.06, 0.25), 4), "%", "rate"),
    ]
    if cfg["defaults"]:
        scalars += [Scalar("cdr", "Default rate (CDR, annual)", round(u(0.01, 0.06), 4), "%", "rate"),
                    Scalar("sev", "Loss severity", round(u(0.3, 0.6), 3), "%", "rate"),
                    Scalar("lag", "Recovery lag (months)", float(rng.choice([3, 6, 9, 12])), "m", "fixed")]
    if cfg["fee"]:
        scalars.append(Scalar("serv", "Servicing fee (annual % of pool)", round(u(0.005, 0.015), 4), "%", "rate"))
    if cfg["prorata"]:
        scalars.append(Scalar("oc_trig", "OC trigger (pool / notes, minimum)", round(1 + oc0 * u(0.6, 0.95), 4),
                              "x", "ratio"))
    for c in cls:
        scalars.append(Scalar(f"{c}_cpn", f"{NAME[c]} coupon (annual)", coupon[c], "%", "interest"))
    cnl, res = cfg.get("cnl", False), cfg.get("reserve", False)
    if cnl:
        # set above the expected loss (~ CDR x severity x ~2 years of pool life), as in real deals; the
        # multiple's spread means some base cases still breach late in the deal
        cdr_v, sev_v = (next(x.value for x in scalars if x.id == k) for k in ("cdr", "sev"))
        scalars.append(Scalar("cnl_trig", "Cumulative net loss trigger (% of original pool)",
                              round(cdr_v * sev_v * 2.0 * u(1.4, 2.4), 4), "%", "rate"))
    if res:
        res_pct = round(u(0.01, 0.025), 4)
        scalars += [Scalar("res_pct", "Reserve target (% of current pool)", res_pct, "%", "rate"),
                    Scalar("res_floor", "Reserve floor (% of original pool)", round(res_pct * u(0.3, 0.6), 4), "%",
                           "rate")]
    lines: List[Line] = [
        Line("month", "Month", M, unit="#", fc="{month[-1]}+1", history=[0.0], kind="ratio", desc="prior month + 1",
             section="Collateral"),
    ]
    if cfg["ramp"]:
        lines.append(Line("smm", "Prepayment rate (SMM)", M, unit="%", kind="ratio",
                          fc="1-(1-{$cpr}*MIN(1,{month}/30))^(1/12)", hist="blank",
                          desc="1 - (1 - CPR x MIN(1, month / 30))^(1/12)"))
        smm = "{smm}"
    else:
        smm = "{smm_c}"
    if cfg["defaults"]:
        lines.append(Line("defaults", "Defaults", M, fc="{perf[-1]}*{mdr}", hist="blank",
                          desc="opening performing balance x monthly default rate"))
        net_open = "({perf[-1]}-{defaults})"
    else:
        net_open = "{perf[-1]}"
    lines += [
        Line("int_coll", "Interest collections", M, fc=f"{net_open}*{{$wac}}/12", hist="blank",
             desc="(opening performing balance" + (" - defaults" if cfg["defaults"] else "") + ") x WAC / 12"),
        Line("sched_prin", "Scheduled principal", M,
             fc=f"PMT({{$wac}}/12,{{$wam}}-{{month}}+1,-{net_open})-{{int_coll}}", hist="blank",
             desc="level monthly payment on the non-defaulted balance over the remaining term (PMT) - interest"),
        Line("prepay", "Prepayments", M, fc=f"({net_open}-{{sched_prin}})*{smm}", hist="blank",
             desc="(balance after defaults and scheduled principal) x SMM"),
        Line("perf", "Performing balance - closing", M,
             fc="{perf[-1]}" + ("-{defaults}" if cfg["defaults"] else "") + "-{sched_prin}-{prepay}", history=[pool0],
             desc="opening - defaults - scheduled principal - prepayments"),
    ]
    if cfg["defaults"]:
        lines += [
            Line("recov", "Recoveries", M, fc="IF({month}>{$lag},INDEX({defaults@fc},{month}-{$lag})*(1-{$sev}),0)",
                 hist="blank", desc="defaults from 'lag' months earlier x (1 - severity), zero before then"),
            Line("loss", "Realised losses", M, fc="IF({month}>{$lag},INDEX({defaults@fc},{month}-{$lag})*{$sev},0)",
                 hist="blank", desc="defaults from 'lag' months earlier x severity, zero before then"),
        ]
    if cfg["fee"]:
        lines.append(Line("fee", "Servicing fee", M, fc="{perf[-1]}*{$serv}/12", hist="blank",
                          desc="opening performing balance x fee / 12", section="Available funds"))
        int_avail = "{int_coll}-{fee}"
    else:
        int_avail = "{int_coll}"
    lines.append(Line("int_avail", "Interest available for notes", M, fc=int_avail, hist="blank",
                      desc="interest collections" + (" - servicing fee" if cfg["fee"] else ""),
                      section="" if cfg["fee"] else "Available funds"))
    paid_so_far = []
    if res:
        lines.append(Line("res_draw", "Reserve draw for Class A interest", M,
                          fc="MIN({res[-1]},MAX(0,{a_due}-MAX(0,{int_avail})))", hist="blank",
                          desc="the smaller of the opening reserve and Class A's shortfall (interest due - positive "
                               "interest available)"))
        paid_so_far.append("(-{res_draw})")
    for c in cls:
        due = f"{{{c}[-1]}}*{{${c}_cpn}}/12"
        if cfg["carry"] and c != "a":
            due = f"{due}+{{{c}_short[-1]}}"
            desc = f"{NAME[c]} opening balance x coupon / 12 + unpaid interest carried forward"
        else:
            desc = f"{NAME[c]} opening balance x coupon / 12"
        lines.append(Line(f"{c}_due", f"{NAME[c]} interest due", M, fc=due, hist="blank", desc=desc))
        avail = "{int_avail}" + "".join(f"-{x}" for x in paid_so_far)
        # with a reserve, the classes are paid from positive interest + the draw; a servicing
        # shortfall (negative interest available) stays in excess spread, met from principal
        avail = avail.replace("{int_avail}-(-{res_draw})", "MAX(0,{int_avail})+{res_draw}")
        lines.append(Line(f"{c}_ipaid", f"{NAME[c]} interest paid", M, fc=f"MIN(MAX(0,{avail}),{{{c}_due}})",
                          hist="blank", desc="the smaller of interest still available and interest due"))
        if cfg["carry"] and c != "a":
            lines.append(Line(f"{c}_short", f"{NAME[c]} unpaid interest carried forward", M,
                              fc=f"{{{c}_due}}-{{{c}_ipaid}}", history=[0.0], desc="interest due - interest paid"))
        paid_so_far.append(f"{{{c}_ipaid}}")
    lines.append(Line("excess", "Excess spread", M,
                      fc=("{int_avail}" + "".join(f"-{x}" for x in paid_so_far)).replace("-(-{res_draw})", "+{res_draw}"),
                      hist="blank", desc="interest available" + (" + reserve draw" if res else "")
                                         + " - interest paid to all classes"))
    prin_avail = "{sched_prin}+{prepay}" + ("+{recov}" if cfg["defaults"] else "")
    if cfg["fee"] and cfg["defaults"]:
        lines.append(Line("loss_cover", "Excess spread used to cover losses", M, fc="MIN(MAX(0,{excess}),{loss})",
                          hist="blank", desc="the smaller of positive excess spread and realised losses"))
        prin_avail += "+{loss_cover}"
    lines.append(Line("pdist", "Principal available for notes", M, fc=prin_avail, hist="blank",
                      desc="scheduled principal + prepayments" + (" + recoveries" if cfg["defaults"] else "")
                           + (" + excess spread covering losses" if cfg["fee"] and cfg["defaults"] else "")))
    notes_open = "+".join(f"{{{c}[-1]}}" for c in cls)
    if cfg["prorata"]:
        lines.append(Line("oc", "OC ratio (opening)", M, unit="x", kind="ratio",
                          fc=f"IF({notes_open}>0,{{perf[-1]}}/({notes_open}),0)", hist="blank",
                          desc="opening performing balance / opening total notes (0 once the notes are repaid)"))
        if cnl:
            lines += [
                Line("cum_l", "Cumulative realised losses", M, fc="{cum_l[-1]}+{loss}", history=[0.0],
                     desc="prior + this month's realised losses"),
                Line("cnl_hit", "CNL trigger breached", M, unit="1/0", kind="ratio",
                     fc="IF(OR({cnl_hit[-1]}=1,{cum_l}/{perf@0}>{$cnl_trig}),1,0)", history=[0.0],
                     desc="1 once cumulative losses / original pool have exceeded the trigger (stays 1)"),
                Line("oc_pass", "Pro rata allowed", M, unit="1/0", kind="ratio",
                     fc="IF(AND({oc}>={$oc_trig},{cnl_hit}=0),1,0)", hist="blank",
                     desc="1 if OC ratio >= trigger and the CNL trigger has never been breached, else 0"),
            ]
        else:
            lines.append(Line("oc_pass", "OC test passed", M, unit="1/0", kind="ratio",
                              fc="IF({oc}>={$oc_trig},1,0)", hist="blank", desc="1 if OC ratio >= trigger, else 0"))
    prior = []
    for c in cls:
        remaining = "{pdist}" + "".join(f"-{x}" for x in prior)
        if cfg["prorata"]:
            share = f"{{{c}[-1]}}/MAX(1E-9,{notes_open})"
            fc = (f"MIN({{{c}[-1]}},MAX(0,IF({{oc_pass}}=1,{{pdist}}*{share},{remaining})))" if c == cls[0] else
                  f"MIN({{{c}[-1]}},MAX(0,IF({{oc_pass}}=1,{{pdist}}*{share},{remaining})))")
            desc = ("if the OC test passes: principal available x this class's share of opening notes; otherwise "
                    "sequential (principal left after more senior classes); capped at the class balance")
        else:
            fc = f"MIN({{{c}[-1]}},MAX(0,{remaining}))"
            desc = "sequential: principal left after more senior classes, capped at the class balance"
        lines.append(Line(f"{c}_ppaid", f"{NAME[c]} principal paid", M, fc=fc, hist="blank", desc=desc,
                          section="Notes" if c == cls[0] else ""))
        lines.append(Line(c, f"{NAME[c]} balance - closing", M, fc=f"{{{c}[-1]}}-{{{c}_ppaid}}",
                          history=[notes0[c]], desc="opening - principal paid"))
        prior.append(f"{{{c}_ppaid}}")
    resid = "{excess}" + ("-{loss_cover}" if cfg["fee"] and cfg["defaults"] else "") + "+{pdist}" + "".join(
        f"-{x}" for x in prior)
    if res:
        notes_close = "+".join(f"{{{c}}}" for c in cls)
        net_open = "({res[-1]}-{res_draw})"
        lines += [
            Line("resid_pre", "Cash after the notes", M, fc=resid, hist="blank",
                 desc="excess spread not used for losses + principal not paid to notes", section="Reserve account"),
            Line("res_target", "Reserve target", M,
                 fc=f"IF({notes_close}>0,MAX({{$res_pct}}*{{perf}},{{$res_floor}}*{{perf@0}}),0)", hist="blank",
                 desc="while notes are outstanding: MAX(target % x closing pool, floor % x original pool); else 0"),
            Line("res_fund", "Reserve funding/(release)", M,
                 fc=f"IF({{res_target}}>={net_open},MIN(MAX(0,{{resid_pre}}),{{res_target}}-{net_open}),"
                    f"{{res_target}}-{net_open})", hist="blank",
                 desc="if the target is at or above the reserve after the draw: top up from positive cash after the "
                      "notes; otherwise release the excess (negative)"),
            Line("res", "Reserve account - closing", M, fc="{res[-1]}-{res_draw}+{res_fund}",
                 history=[round(pool0 * res_pct, 2)], desc="opening - draw + funding/(release)"),
            Line("residual", "Cash released to residual holder", M, fc="{resid_pre}-{res_fund}", hist="blank",
                 desc="cash after the notes - reserve funding (+ release)"),
        ]
    else:
        lines.append(Line("residual", "Cash released to residual holder", M, fc=resid, hist="blank",
                          desc="excess spread" + (" not used for losses" if cfg["fee"] and cfg["defaults"] else "")
                               + " + principal not paid to notes"))
    calcs = [Calc("smm_c", "Prepayment rate (SMM, monthly)", M, "1-(1-{$cpr})^(1/12)", unit="%", kind="ratio",
                  section="Rates and results", desc="1 - (1 - CPR)^(1/12)")]
    if cfg["defaults"]:
        calcs.append(Calc("mdr", "Default rate (MDR, monthly)", M, "1-(1-{$cdr})^(1/12)", unit="%", kind="ratio",
                          desc="1 - (1 - CDR)^(1/12)"))
        calcs.append(Calc("cum_loss", "Cumulative realised losses (% of original pool)", M,
                          "SUM({loss@fc})/{perf@0}", unit="%", kind="ratio", desc="sum of losses / closing pool"))
    calcs.append(Calc("resid_total", "Total cash to residual holder", M, "SUM({residual@fc})",
                      desc="sum of residual cash"))
    if cfg["ramp"]:
        calcs.append(Calc("wal_a", "Class A weighted average life (years)", M,
                          "SUMPRODUCT({month@fc},{a_ppaid@fc})/SUM({a_ppaid@fc})/12", unit="yrs", kind="ratio",
                          desc="SUMPRODUCT(month, class A principal) / total class A principal / 12"))
    spec = ModelSpec(title="ABS cash flow model", periods=periods, n_hist=1, sheets=[A, M], scalars=scalars,
                     lines=lines, calcs=calcs)
    ts = [
        "COLLATERAL (monthly; closing column = balances at closing):",
        "- Defaults at the monthly default rate MDR = 1 - (1 - CDR)^(1/12) on the opening performing balance."
        if cfg["defaults"] else "- No defaults.",
        "- Interest collections = (opening performing balance" + (" - defaults" if cfg["defaults"] else "")
        + ") x WAC / 12.",
        "- Scheduled principal: each month the non-defaulted balance pays a level monthly payment over its remaining "
        "term (remaining term = remaining term at closing - month + 1); scheduled principal = that payment - "
        "interest collections.",
        "- Prepayments = (non-defaulted balance - scheduled principal) x SMM, SMM = 1 - (1 - CPR)^(1/12)"
        + (" where the CPR ramps up linearly: CPR in month m = CPR x MIN(1, m / 30)." if cfg["ramp"] else "."),
        "- Closing performing balance = opening - defaults - scheduled principal - prepayments."
        if cfg["defaults"] else "- Closing performing balance = opening - scheduled principal - prepayments.",
    ]
    if cfg["defaults"]:
        ts.append("- Defaulted loans are worked out after the recovery lag: in month m the defaults of month m - lag "
                  "produce recoveries of (1 - severity) and realised losses of severity; nothing before month lag + "
                  "1.")
    ts.append("WATERFALL each month:")
    if cfg["fee"]:
        ts.append("- Interest available for the notes = interest collections - servicing fee (annual fee x opening "
                  "performing balance / 12).")
    if res:
        ts.append("- RESERVE DRAW: before interest is paid, the reserve account covers Class A's interest shortfall: "
                  "draw = the smaller of the opening reserve balance and (Class A interest due - positive interest "
                  "available for the notes). Interest available to the classes = MAX(0, interest available for the "
                  "notes) + draw: a negative interest available (servicing fee above interest collections) is not "
                  "taken from the classes; it stays in excess spread.")
    ts.append("- Interest is paid in order of seniority (" + ", ".join(NAME[c] for c in cls) + "): each class "
              "receives the smaller of interest still available and its interest due (opening class balance x "
              "coupon / 12" + (", plus for subordinate classes any interest unpaid in earlier months, which is "
                              "carried forward)" if cfg["carry"] else ")") + ". What remains is excess spread.")
    ts.append("- Principal available for the notes = scheduled principal + prepayments" + (
        " + recoveries" if cfg["defaults"] else "") + (
        " + the part of excess spread used to cover this month's realised losses (the smaller of positive excess "
        "spread and losses)" if cfg["fee"] and cfg["defaults"] else "") + ".")
    if cnl:
        ts.append("- CNL TRIGGER: cumulative realised losses (including this month's) / original pool balance; once "
                  "it has exceeded the CNL trigger in any month, the trigger is breached for the rest of the deal "
                  "(non-curable) and principal is paid sequentially from that month on, whatever the OC test says.")
    if cfg["prorata"]:
        ts.append("- OC test: OC ratio = opening performing balance / opening total notes (0 once the notes are fully "
                  "repaid). If it is at or above the "
                  "OC trigger, principal is paid pro rata (each class gets principal available x its share of opening "
                  "total notes); otherwise sequentially (most senior first). Each class is capped at its balance.")
    else:
        ts.append("- Principal is paid sequentially: most senior class first, each capped at its balance.")
    ts.append("- Everything not paid to the notes (" + ("unused excess spread and " if True else "")
              + "principal beyond the note balances) is released to the residual holder: cash released = excess "
              "spread" + (" - excess spread used to cover losses" if cfg["fee"] and cfg["defaults"] else "")
              + " + principal available - principal paid to the notes." + (
                  " Excess spread is negative when the servicing fee exceeds interest collections; that shortfall "
                  "is met from principal collections, so it reduces the cash released (which can then be "
                  "negative)." if cfg["fee"] else ""))
    if res:
        ts.append("- RESERVE ACCOUNT (after the residual cash is determined, before it is released): target = MAX("
                  "reserve % x closing performing balance, floor % x original pool) while any note is outstanding "
                  "after this month's payments, otherwise 0. If the target is at or above the balance after this "
                  "month's draw, top it up from the positive cash after the notes (never more than that cash); "
                  "otherwise release the excess. Cash released to the residual holder = cash after the notes - "
                  "reserve funding (+ release). The reserve's closing balance = opening - draw + funding/(release).")
    if cfg["ramp"]:
        ts.append("RESULTS: Class A WAL (years) = SUMPRODUCT(month number, class A principal) / total class A "
                  "principal / 12.")
    conventions = ["Monthly periods M1..; the Closing column holds balances at closing.",
                   "Rates on the Assumptions sheet are annual; convert as stated in the terms.",
                   "All cash amounts are positive."]
    ids = [IdSpec("pool_rollforward", "performing balance roll-forward",
                  [(1, "perf", 0), (-1, "perf", -1), (1, "sched_prin", 0), (1, "prepay", 0)]
                  + ([(1, "defaults", 0)] if cfg["defaults"] else [])),
           IdSpec("cash_fully_allocated", "interest + principal sources = note payments + residual",
                  [(1, "int_avail", 0), (1, "sched_prin", 0), (1, "prepay", 0)]
                  + ([(1, "recov", 0)] if cfg["defaults"] else [])
                  + [(-1, f"{c}_ipaid", 0) for c in cls] + [(-1, f"{c}_ppaid", 0) for c in cls]
                  + [(-1, "residual", 0)] + ([(1, "res_draw", 0), (-1, "res_fund", 0)] if res else []))]
    if res:
        ids.append(IdSpec("reserve_rollforward", "reserve roll-forward",
                          [(1, "res", 0), (-1, "res", -1), (1, "res_draw", 0), (-1, "res_fund", 0)]))
    for c in cls:
        ids.append(IdSpec(f"{c}_rollforward", f"{NAME[c]} roll-forward",
                          [(1, c, 0), (-1, c, -1), (1, f"{c}_ppaid", 0)]))
    mono = [MonoSpec("residual_rises_with_wac", "resid_total", "wac", 0.005, 1)]
    if cfg["defaults"]:
        mono.append(MonoSpec("residual_falls_with_severity", "resid_total", "sev", 0.05, -1))
    if cfg["ramp"]:
        mono.append(MonoSpec("wal_falls_with_cpr", "wal_a", "cpr", 0.02, -1))
    outputs = [("perf", "Performing balance"), ("int_avail", "Interest available for notes"),
               ("pdist", "Principal available for notes")]
    outputs += [(c, f"{NAME[c]} balance") for c in cls] + [("residual", "Cash to residual holder"),
                                                            ("resid_total", "Total cash to residual holder")]
    if cfg["ramp"]:
        outputs.append(("wal_a", "Class A WAL (years)"))
    if cnl:
        outputs.append(("cnl_hit", "CNL trigger breached"))
    if res:
        outputs += [("res", "Reserve account balance"), ("res_draw", "Reserve draw"), ("res_fund", "Reserve funding/(release) (a release is negative)")]
    kinds = {"month": ("fixed", None, None), "cpr": ("rate", 0.0, 0.6), "cdr": ("rate", 0.0, 0.25),
             "sev": ("rate", 0.0, 1.0), "serv": ("rate", 0.0, 0.03), "oc_trig": ("ratio", 1.0, 1.3),
             "cnl_trig": ("rate", 0.0, 0.2), "res_pct": ("rate", 0.0, 0.1), "res_floor": ("rate", 0.0, 0.05)}
    return Bundle(domain="abs", noun="asset-backed securities (ABS) cash flow model with a note waterfall",
                  spec=spec, term_sheet="\n".join(ts), conventions=conventions, identities=ids, monotone=mono,
                  kinds=kinds, outputs=outputs, scale=pool0 / 10, level=level, meta={"months": n, "classes": cls})
