"""Project finance: construction, operations, sculpted debt, reserve accounts.

Annual model from financial close. Mechanics by level:

1. 1-year construction funded by debt (gearing) and equity; operations revenue
   = capacity x generation hours x tariff; tariff escalates yearly. Debt
   service is *sculpted*: each repayment year's debt service is proportional to
   CFADS, scaled so the loan repays exactly at the end of the tenor (constant
   DSCR = PV(CFADS over the tenor) / debt at COD).
2. + 2-year construction, interest during construction (IDC) capitalised into
   the loan, opex with its own escalation, cash taxes with straight-line tax
   depreciation (tax computed unlevered so CFADS does not depend on debt).
3. + debt service reserve account (DSRA): target = a share of next year's
   debt service, funded from cash after debt service, released when the target
   falls; equity distributions = cash after debt service - DSRA movement.
4. + longer operations (15 years) and a lifecycle (major maintenance) cost
   every few years.
5. + tax losses carried forward (NOLs), used against future taxable income;
   banking case vs operating case: debt is sculpted at financial close on the
   banking-case (P50, pre-tax) CFADS while actual generation follows an
   availability path, so the actual DSCR moves; a distribution lock-up traps
   cash in years whose actual DSCR is below the lock-up ratio and releases the
   trapped cash only after two consecutive passing years.

Flags are derived from the commercial-operation year and the tenor (both fixed
structural inputs, never perturbed).
"""

from __future__ import annotations

import random
from typing import List

from ..model.spec import Calc, Line, ModelSpec, Scalar
from .framework import Bundle, IdSpec, MonoSpec

DOMAIN = "pf"

LEVELS = {
    1: dict(constr=1, ops=15, tax=False, idc=False, opex_esc=False, dsra=False, lifecycle=False, nol=False),
    2: dict(constr=2, ops=18, tax=True, idc=True, opex_esc=True, dsra=False, lifecycle=False, nol=False),
    3: dict(constr=2, ops=18, tax=True, idc=True, opex_esc=True, dsra=True, lifecycle=False, nol=False),
    4: dict(constr=2, ops=20, tax=True, idc=True, opex_esc=True, dsra=True, lifecycle=True, nol=False),
    5: dict(constr=2, ops=20, tax=True, idc=True, opex_esc=True, dsra=True, lifecycle=True, nol=True,
            lockup=True),
}


def generate(rng: random.Random, level: int) -> Bundle:
    cfg = LEVELS[level]
    u = rng.uniform
    nc, no = cfg["constr"], cfg["ops"]
    n = nc + no
    tenor = no - rng.randint(2, 4)  # repayment ends before the end of operations (a tail remains)
    y0 = rng.randint(2025, 2027)
    periods = [f"FY{y0} (close)"] + [f"FY{y0 + i + 1}" for i in range(n)]
    capacity = round(u(50, 400), 0)  # MW
    # utility-scale renewables: ~1.0-1.6 $m/MW capex, 1,800-3,400 net hours, $40-80/MWh
    hours = round(u(1800, 3400), 0)  # net generation hours / year
    tariff0 = round(u(40, 80), 2)  # $/MWh at close
    capex_total = capacity * u(0.85, 1.35) * (hours * tariff0 / (2600 * 60))  # $m, scaled with revenue potential
    capex = [round(capex_total * w, 1) for w in ([1.0] if nc == 1 else [0.55, 0.45])] + [0.0] * no
    revenue1 = capacity * hours * tariff0 / 1e6
    A, M = "Assumptions", "Model"
    scalars = [
        Scalar("cod_year", "Commercial operation starts after construction year", float(nc), "yr", "fixed"),
        Scalar("tenor", "Debt tenor (operating years)", float(tenor), "yrs", "fixed"),
        Scalar("capacity", "Capacity", capacity, "MW", "ratio"),
        Scalar("hours", "Net generation hours per year", hours, "h", "ratio"),
        Scalar("tariff_esc", "Tariff indexation (per year)", round(u(0.015, 0.03), 4), "%", "rate"),
        Scalar("opex1", "Opex in the first operating year", round(revenue1 * u(0.18, 0.30), 2), "$m", "money"),
        Scalar("gearing", "Gearing (debt share of construction capex)", round(u(0.65, 0.80), 3), "%", "rate"),
        Scalar("rate", "Debt interest rate", round(u(0.05, 0.075), 4), "%", "interest"),
    ]
    if cfg["opex_esc"]:
        scalars.append(Scalar("opex_esc", "Opex escalation (per year)", round(u(0.02, 0.035), 4), "%", "rate"))
    if cfg["tax"]:
        scalars += [Scalar("tax_rate", "Tax rate", round(u(0.2, 0.3), 3), "%", "tax"),
                    Scalar("dep_years", "Tax depreciation life (years, straight line)", float(rng.choice([10, 12, 15])),
                           "yrs", "fixed")]
    if cfg["dsra"]:
        scalars.append(Scalar("dsra_pct", "DSRA target (share of next year's debt service)",
                              rng.choice([0.5, 0.5, 1.0]), "%", "rate"))
    if cfg["lifecycle"]:
        scalars += [Scalar("lc_cost", "Major maintenance cost per event", round(capex_total * u(0.03, 0.06), 2), "$m",
                           "money"),
                    Scalar("lc_every", "Major maintenance every (operating years)", float(rng.choice([4, 5])), "yrs",
                           "fixed")]
    lock = cfg.get("lockup", False)
    if lock:
        scalars.append(Scalar("lock_ratio", "Distribution lock-up DSCR", rng.choice([1.05, 1.1, 1.15]), "x",
                              "ratio"))
    lines: List[Line] = [
        Line("capex", "Construction capex", A, fc=None, hist="blank", forecast=capex, kind="money"),
        Line("year", "Year number", M, unit="#", fc="{year[-1]}+1", history=[0.0], kind="ratio",
             desc="prior year + 1", section="Timeline"),
        Line("ops", "Operations flag", M, unit="1/0", fc="IF({year}>{$cod_year},1,0)", hist="blank", kind="ratio",
             desc="1 if year number > COD year, else 0"),
        Line("op_year", "Operating year number", M, unit="#", fc="{op_year[-1]}+{ops}", history=[0.0], kind="ratio",
             desc="prior operating year number + operations flag"),
        Line("rep", "Repayment flag", M, unit="1/0", fc="IF(AND({ops}=1,{op_year}<={$tenor}),1,0)", hist="blank",
             kind="ratio", desc="1 in operating years up to the tenor, else 0"),
        Line("tariff", "Tariff", M, unit="$/MWh", fc="{tariff[-1]}*(1+{$tariff_esc})", history=[tariff0],
             kind="money", desc="prior-year tariff x (1 + indexation)", section="Operations"),
    ]
    if lock:
        # P50 is the median: actual availability scatters around 1.0, with two bad years
        avail = [1.0] * nc + [round(u(0.97, 1.05), 3) for _ in range(no)]
        for k in rng.sample(range(nc, nc + tenor), 2):  # two bad operating years inside the tenor
            avail[k] = round(u(0.72, 0.86), 3)
        lines.insert(1, Line("avail", "Availability (actual generation / P50)", A, unit="%", fc=None, hist="blank",
                             forecast=avail, kind="ratio"))
        lines += [
            Line("rev_bank", "Revenue (banking case, P50)", M, fc="{ops}*{$capacity}*{$hours}*{tariff}/1000000",
                 hist="blank", desc="operations flag x capacity x hours x tariff / 1,000,000 ($m)"),
            Line("revenue", "Revenue (actual)", M, fc="{rev_bank}*{avail}", hist="blank",
                 desc="banking-case revenue x availability"),
        ]
    else:
        lines.append(Line("revenue", "Revenue", M, fc="{ops}*{$capacity}*{$hours}*{tariff}/1000000", hist="blank",
                          desc="operations flag x capacity x hours x tariff / 1,000,000 ($m)"))
    if cfg["opex_esc"]:
        lines.append(Line("opex", "Operating costs", M,
                          fc="{ops}*{$opex1}*(1+{$opex_esc})^({op_year}-1)", hist="blank",
                          desc="operations flag x first-year opex x (1 + escalation)^(operating year - 1)"))
    else:
        lines.append(Line("opex", "Operating costs", M, fc="{ops}*{$opex1}", hist="blank",
                          desc="operations flag x first-year opex"))
    ebitda_fc = "{revenue}-{opex}"
    if cfg["lifecycle"]:
        lines.append(Line("lifecycle", "Major maintenance", M,
                          fc="IF(AND({ops}=1,MOD({op_year},{$lc_every})=0),{$lc_cost},0)", hist="blank",
                          desc="major maintenance cost in operating years that are multiples of the interval"))
        ebitda_fc += "-{lifecycle}"
    lines.append(Line("ebitda", "EBITDA", M, fc=ebitda_fc, hist="blank",
                      desc="revenue - operating costs" + (" - major maintenance" if cfg["lifecycle"] else "")))
    if cfg["tax"]:
        lines += [
            Line("tax_dep", "Tax depreciation", M, fc="{ops}*MIN({tax_nbv[-1]},{capex_total}/{$dep_years})",
                 hist="blank", section="Tax",
                 desc="operations flag x the smaller of opening tax book value and total capex / tax life"),
            Line("tax_nbv", "Tax book value - closing", M, fc="{tax_nbv[-1]}+{capex}-{tax_dep}", history=[0.0],
                 desc="opening + construction capex - tax depreciation"),
            Line("taxable", "Taxable income (unlevered)", M, fc="{ebitda}-{tax_dep}", hist="blank",
                 desc="EBITDA - tax depreciation"),
        ]
        if cfg["nol"]:
            lines += [
                Line("nol_used", "Tax losses used", M, fc="MIN({nol[-1]},MAX(0,{taxable}))", hist="blank",
                     desc="the smaller of opening tax losses and positive taxable income"),
                Line("nol", "Tax losses carried forward - closing", M,
                     fc="{nol[-1]}-{nol_used}+MAX(0,-{taxable})", history=[0.0],
                     desc="opening - losses used + this year's loss"),
                Line("tax", "Cash tax", M, fc="(MAX(0,{taxable})-{nol_used})*{$tax_rate}", hist="blank",
                     desc="(positive taxable income - losses used) x tax rate"),
            ]
        else:
            lines.append(Line("tax", "Cash tax", M, fc="MAX(0,{taxable})*{$tax_rate}", hist="blank",
                              desc="positive taxable income x tax rate"))
        cfads_fc = "{ebitda}-{tax}"
    else:
        cfads_fc = "{ebitda}"
    lines.append(Line("cfads", "Cash flow available for debt service (CFADS)", M, fc=cfads_fc, hist="blank",
                      desc="EBITDA" + (" - cash tax" if cfg["tax"] else ""), section="Debt"))
    if lock:
        lines += [
            Line("cfads_bank", "Banking-case CFADS (pre-tax)", M,
                 fc="{rev_bank}-{opex}" + ("-{lifecycle}" if cfg["lifecycle"] else ""), hist="blank",
                 desc="banking-case revenue - operating costs" + (" - major maintenance" if cfg["lifecycle"] else "")),
            Line("cfads_rep", "Banking-case CFADS in repayment years", M, fc="{rep}*{cfads_bank}", hist="blank",
                 desc="repayment flag x banking-case CFADS"),
        ]
    else:
        lines.append(Line("cfads_rep", "CFADS in repayment years", M, fc="{rep}*{cfads}", hist="blank",
                          desc="repayment flag x CFADS"))
    lines += [
        Line("draw", "Debt drawdown", M, fc="{capex}*{$gearing}", hist="blank", desc="construction capex x gearing"),
    ]
    # The construction loan is tracked in its own corkscrew so that debt at COD (which
    # sizes the sculpted repayments) does not depend on those repayments - otherwise the
    # model is circular, in Excel as in this engine (dependencies are syntactic).
    if cfg["idc"]:
        lines.append(Line("idc", "Interest during construction (capitalised)", M,
                          fc="(1-{ops})*{debt_c[-1]}*{$rate}", hist="blank",
                          desc="(1 - operations flag) x opening construction loan x interest rate"))
        lines.append(Line("debt_c", "Construction loan - closing", M, fc="{debt_c[-1]}+{draw}+{idc}", history=[0.0],
                          desc="opening + drawdown + IDC (flat once operations start)"))
        debt_fc = "{debt[-1]}+{draw}+{idc}-{principal}"
    else:
        lines.append(Line("debt_c", "Construction loan - closing", M, fc="{debt_c[-1]}+{draw}", history=[0.0],
                          desc="opening + drawdown (flat once operations start)"))
        debt_fc = "{debt[-1]}+{draw}-{principal}"
    lines += [
        Line("interest", "Cash interest", M, fc="{ops}*{debt[-1]}*{$rate}", hist="blank",
             desc="operations flag x opening debt x interest rate"),
        Line("ds", "Debt service (sculpted)", M, fc="{cfads_rep}*{debt_cod}/{pv_cfads}", hist="blank",
             desc="CFADS in repayment years x debt at COD / PV of repayment-year CFADS"),
        Line("principal", "Principal repayment", M, fc="{rep}*({ds}-{interest})", hist="blank",
             desc="repayment flag x (debt service - interest)"),
        Line("debt", "Debt balance - closing", M, fc=debt_fc, hist="formula", hist_fc="{debt_c}",
             desc="opening + drawdown" + (" + IDC" if cfg["idc"] else "") + " - principal"),
    ]
    equity_in = "{capex}*(1-{$gearing})"
    lines.append(Line("equity_in", "Equity contribution", M, fc=equity_in, hist="blank", section="Equity",
                      desc="construction capex x (1 - gearing)"))
    lines.append(Line("cf_after_ds", "Cash flow after debt service", M, fc="{cfads}-{ds}", hist="blank",
                      desc="CFADS - debt service"))
    if cfg["dsra"]:
        lines += [
            Line("dsra_target", "DSRA target balance", M, fc="{ops}*{$dsra_pct}*{ds[1]}", fc_last="0", hist="blank",
                 desc="operations flag x DSRA % x NEXT year's debt service (zero in the final year)"),
            Line("dsra_move", "DSRA funding/(release)", M,
                 fc=("IF({cf_after_ds}<0,-MIN({dsra[-1]},-{cf_after_ds})," if cfg.get("lockup") else "")
                    + "IF({dsra_target}>={dsra[-1]},MIN(MAX(0,{cf_after_ds}),{dsra_target}-{dsra[-1]}),"
                    "{dsra_target}-{dsra[-1]})" + (")" if cfg.get("lockup") else ""), hist="blank",
                 desc=("if cash after debt service is negative: draw the smaller of the opening balance and the "
                       "shortfall (negative); otherwise " if cfg.get("lockup") else "")
                      + "if the target is at or above the opening balance: fund the smaller of positive cash after "
                        "debt service and the shortfall; otherwise release down to the target (negative)"),
            Line("dsra", "DSRA balance - closing", M, fc="{dsra[-1]}+{dsra_move}", history=[0.0],
                 desc="opening + funding/(release)"),
        ]
        if lock:
            lines += [
                Line("pre_dist", "Cash available for distribution", M, fc="{ops}*({cf_after_ds}-{dsra_move})",
                     hist="blank", desc="operations flag x (cash after debt service - DSRA funding/(release))",
                     section="Distribution lock-up"),
                Line("dscr_act", "Actual DSCR", M, unit="x", kind="ratio", fc="IF({ds}>0,{cfads}/{ds},0)",
                     hist="blank", desc="CFADS / debt service (0 when there is no debt service)"),
                Line("lk_pass", "Lock-up test passed", M, unit="1/0", kind="ratio",
                     fc="IF({rep}=1,IF({dscr_act}>={$lock_ratio},1,0),1)", hist="blank",
                     desc="in repayment years 1 if actual DSCR >= lock-up ratio; 1 in all other years"),
                Line("lk_streak", "Consecutive passing years", M, unit="#", kind="ratio",
                     fc="IF({lk_pass}=1,{lk_streak[-1]}+1,0)", history=[0.0],
                     desc="prior count + 1 if the test passed this year, else 0"),
                Line("trapped", "Cash trapped", M, fc="IF({lk_pass}=0,MAX(0,{pre_dist}),0)", hist="blank",
                     desc="positive cash available for distribution in a failing year"),
                Line("released", "Trapped cash released", M, fc="IF({lk_streak}>=2,{lock[-1]},0)", hist="blank",
                     desc="the whole opening lock-up balance once two consecutive years have passed"),
                Line("lock", "Lock-up account - closing", M, fc="{lock[-1]}+{trapped}-{released}", history=[0.0],
                     desc="opening + trapped - released"),
                Line("dist", "Distributions to equity", M, fc="{pre_dist}-{trapped}+{released}", hist="blank",
                     desc="cash available for distribution - trapped + released"),
            ]
        else:
            lines.append(Line("dist", "Distributions to equity", M, fc="{ops}*({cf_after_ds}-{dsra_move})",
                              hist="blank",
                              desc="operations flag x (cash after debt service - DSRA funding/(release))"))
    else:
        lines.append(Line("dist", "Distributions to equity", M, fc="{ops}*{cf_after_ds}", hist="blank",
                          desc="operations flag x cash after debt service"))
    lines.append(Line("equity_cf", "Equity cash flow", M, fc="{dist}-{equity_in}", hist="blank",
                      desc="distributions - equity contributions"))
    cod_col = nc  # period index of the last construction year (= COD)
    calcs = [
        Calc("capex_total", "Total construction capex", M, "SUM({capex@fc})", section="Results",
             desc="sum of construction capex"),
        Calc("debt_cod", "Debt at COD", M, f"{{debt_c@{cod_col}}}",
             desc="construction loan balance at the end of the last construction year"),
        Calc("pv_cfads", "PV of repayment-year CFADS at COD", M,
             f"NPV({{$rate}},{{cfads_rep@fc}})*(1+{{$rate}})^{nc}",
             desc=f"NPV at the debt rate of repayment-year CFADS (from the first projection year), carried "
                  f"forward to COD: x (1 + rate)^{nc}"),
        Calc("dscr", "Sculpted DSCR", M, "{pv_cfads}/{debt_cod}", unit="x", kind="ratio",
             desc="PV of repayment-year CFADS / debt at COD"),
        Calc("equity_irr", "Equity IRR", M, "IRR({equity_cf@fc})", unit="%", kind="ratio",
             desc="IRR of yearly equity cash flows"),
    ]
    spec = ModelSpec(title="Project finance model", periods=periods, n_hist=1, sheets=[A, M], scalars=scalars,
                     lines=lines, calcs=calcs)
    ts = [
        "TIMELINE. Year numbers count from financial close (close = 0). Construction runs in years 1.."
        "COD year; operations start the year after. Operating year number = 1 in the first operating year, then "
        "+1 each year. Repayment years are operating years up to and including the debt tenor.",
        "CONSTRUCTION FUNDING. Each construction year's capex is funded by debt (gearing x capex) and equity (the "
        "rest). " + ("Interest during construction on the opening debt balance is capitalised (added to the loan); "
                     "no cash interest is paid before operations." if cfg["idc"] else
                     "No interest accrues before operations.")
        + " The construction loan line is a memo corkscrew of the debt raised (opening + drawdown"
        + (" + capitalised interest" if cfg["idc"] else "") + "): it stays flat once operations start (it is not "
        "zeroed or repaid; repayments run through the debt balance line), and debt at COD = its balance at the end "
        "of the COD year.",
        "OPERATIONS. Revenue ($m) = capacity (MW) x net generation hours x tariff ($/MWh) / 1,000,000, in operating "
        "years only. The tariff is indexed every year from close. Operating costs are the first-year opex" + (
            " escalated each operating year after the first (first-year opex x (1 + escalation)^(operating year - "
            "1))" if cfg["opex_esc"] else " in every operating year") + "." + (
            " A major maintenance cost is incurred in every operating year that is a multiple of the maintenance "
            "interval." if cfg["lifecycle"] else ""),
    ]
    if cfg["tax"]:
        ts.append("TAX (computed unlevered, i.e. without the interest deduction, so CFADS does not depend on the "
                  "debt). Tax depreciation is straight line: total capex / tax life per operating year, never more "
                  "than the remaining tax book value. Taxable income = EBITDA - tax depreciation." + (
                      " Tax losses are carried forward without limit and used against positive taxable income in "
                      "later years before any tax is paid." if cfg["nol"] else "")
                  + " Cash tax = tax rate x positive taxable income" + (" after losses used." if cfg["nol"] else "."))
    if lock:
        ts.append("BANKING CASE vs ACTUAL. Revenue (banking case) uses the P50 generation hours; actual revenue = "
                  "banking-case revenue x that year's availability. Everything else uses actual revenue, except the "
                  "debt sculpting: it was fixed at financial close on the BANKING-CASE CFADS = banking-case revenue - "
                  "operating costs" + (" - major maintenance" if cfg["lifecycle"] else "") + " (pre-tax). Below, in "
                  "the sculpting formulas, read 'CFADS' as banking-case CFADS.")
    ts.append("CFADS = EBITDA" + (" - cash tax" if cfg["tax"] else "") + ". DEBT SCULPTING: debt service in each "
              "repayment year is proportional to that year's CFADS and scaled so that the loan is exactly repaid at "
              "the end of the tenor: debt service = CFADS x debt at COD / PV(repayment-year CFADS), where the PV "
              "uses the debt rate and is measured at COD. Cash interest in operations is the rate times the opening "
              "balance; principal = debt service - interest. The resulting constant DSCR = PV(repayment-year "
              "CFADS) / debt at COD.")
    if cfg["dsra"]:
        ts.append("DSRA. In operating years the reserve target is the DSRA % of NEXT year's debt service (zero in "
                  "the final model year). If the target is at or above the opening balance, the account is topped "
                  "up from cash after debt service (never more than the positive cash available); otherwise the "
                  "excess is released. " + ("If cash after debt service is negative, the DSRA is instead drawn to "
                                            "cover the shortfall (never more than its opening balance) and is not "
                                            "topped up that year. " if lock else "") + ("Cash available for distribution" if lock else "Distributions to equity")
                  + " = cash after debt service - DSRA funding (+ releases).")
    if lock:
        ts.append("LOCK-UP. Actual DSCR = actual CFADS / debt service (0 when there is no debt service). The lock-up "
                  "test passes in a repayment year when actual DSCR >= the lock-up ratio, and always passes in years "
                  "that are not repayment years. In a failing year the positive cash available for distribution is "
                  "trapped in the lock-up account instead of being distributed. Count consecutive passing years "
                  "(reset to 0 by a failure; the count runs from close); in a year that makes the count at least 2, "
                  "the whole opening lock-up balance is released to equity. Distributions = cash available for "
                  "distribution - cash trapped + cash released.")
    else:
        ts.append("Distributions to equity = cash after debt service in operating years.")
    ts.append("EQUITY IRR = IRR of yearly equity cash flows (distributions - equity contributions).")
    conventions = ["Annual periods; flows at year end; the close column holds opening balances.",
                   "All balances and costs are positive numbers.",
                   "Flags are 1 or 0 and should be used to switch formulas on and off."]
    ids = [IdSpec("debt_rollforward", "debt roll-forward",
                  [(1, "debt", 0), (-1, "debt", -1), (-1, "draw", 0), (1, "principal", 0)]
                  + ([(-1, "idc", 0)] if cfg["idc"] else [])),
           IdSpec("loan_repaid_at_tenor", "debt balance is zero at the end of the tenor",
                  [(1, "debt", cod_col + tenor)], when="once"),
           IdSpec("ds_equals_interest_plus_principal_in_repayment",
                  "debt service = interest + principal in repayment years (rep x ...)",
                  [(1, "principal", 0), (-1, "ds", 0), (1, "interest", 0)] if False else
                  [(1, "cfads_rep", 0), (-1, "cfads_rep", 0)])]
    ids = ids[:2]
    if cfg["dsra"]:
        ids.append(IdSpec("dsra_rollforward", "DSRA roll-forward",
                          [(1, "dsra", 0), (-1, "dsra", -1), (-1, "dsra_move", 0)]))
    if cfg["tax"]:
        ids.append(IdSpec("tax_book_rollforward", "tax book value roll-forward",
                          [(1, "tax_nbv", 0), (-1, "tax_nbv", -1), (-1, "capex", 0), (1, "tax_dep", 0)]))
    mono = [MonoSpec("equity_irr_rises_with_hours", "equity_irr", "hours", 100.0, 1),
            MonoSpec("dscr_rises_with_hours", "dscr", "hours", 100.0, 1)]
    outputs = [("revenue", "Revenue"), ("cfads", "CFADS"), ("ds", "Debt service"), ("debt", "Debt balance"),
               ("dist", "Distributions to equity"), ("equity_cf", "Equity cash flow"),
               ("debt_cod", "Debt at COD"), ("dscr", "Sculpted DSCR"), ("equity_irr", "Equity IRR")]
    if cfg["dsra"]:
        outputs.insert(4, ("dsra", "DSRA balance"))
    if lock:
        outputs += [("dscr_act", "Actual DSCR"), ("lock", "Lock-up account balance")]
        ids.append(IdSpec("lockup_rollforward", "lock-up account roll-forward",
                          [(1, "lock", 0), (-1, "lock", -1), (-1, "trapped", 0), (1, "released", 0)]))
    kinds = {"capacity": ("ratio", 1.0, None), "hours": ("ratio", 500.0, 8760.0), "tariff": ("money", 1.0, None),
             "year": ("fixed", None, None), "op_year": ("fixed", None, None),
             "gearing": ("rate", 0.3, 0.9), "rate": ("interest", 0.005, 0.15), "dsra_pct": ("rate", 0.0, 1.0),
             "tariff_esc": ("rate", 0.0, 0.08), "opex_esc": ("rate", 0.0, 0.08), "tax_rate": ("tax", 0.0, 0.45),
             "capex": ("money", 0.0, None), "lc_cost": ("money", 0.0, None), "opex1": ("money", 0.0, None),
             "avail": ("rate", 0.3, 1.1), "lock_ratio": ("multiple", 0.8, 2.0)}
    return Bundle(domain="pf", noun="project finance model (construction, operations and sculpted debt)",
                  spec=spec, term_sheet="\n".join(ts), conventions=conventions, identities=ids, monotone=mono,
                  kinds=kinds, outputs=outputs, scale=capex_total / 10, level=level, fixed_when_zero=("capex",),
                  meta={"construction_years": nc, "operating_years": no, "tenor": tenor})
