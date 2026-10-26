"""Private-equity distribution waterfalls, tier by tier, year by year.

Two real-world structures:

European (whole-fund) waterfall, levels 1, 2, 3, 5
    1. return of contributed capital
    2. preferred return (simple at level 1, compounding from level 2) on
       unreturned capital (and unpaid pref when compounding)
    3. GP catch-up (none at level 1, 100% at level 2, partial from level 3)
    4. carried-interest split of the residual
    level 3 adds a GP commitment (the GP is also an investor pro rata);
    level 5 adds management fees (funded by contributions), the LP net IRR and
    an end-of-fund clawback test.

JV "accrual account" promote, level 4
    three IRR hurdles, each tracked by a hurdle account that compounds at its
    rate, grows with contributions and is reduced by every LP distribution;
    tier k distributes until the LP's account k is cleared; the residual is
    split at the final ratio.

Convention: contributions are made at the start of each year and accrue for the
year; distributions are made at year end.
"""

from __future__ import annotations

import random
from typing import List

from ..model.spec import Calc, Line, ModelSpec, Scalar
from .framework import Bundle, IdSpec, MonoSpec

DOMAIN = "waterfall"

LEVELS = {
    1: dict(kind="european", compound=False, catchup=None, gp_commit=False, fees=False, n=8),
    2: dict(kind="european", compound=True, catchup="full", gp_commit=False, fees=False, n=8),
    3: dict(kind="european", compound=True, catchup="partial", gp_commit=True, fees=False, n=10),
    4: dict(kind="jv", tiers=3, n=10),
    5: dict(kind="european", compound=True, catchup="partial", gp_commit=True, fees=True, n=12),
}


def _flows(rng: random.Random, n: int, commitment: float, call_years: int):
    u = rng.uniform
    w = [u(0.6, 1.4) for _ in range(call_years)]
    called = u(0.80, 0.95) * commitment
    calls = [round(called * x / sum(w), 1) for x in w] + [0.0] * (n - call_years)
    moic = u(1.3, 2.6)
    start = rng.randint(2, 4)
    shape = [0.0] * n
    for t in range(start, n):
        shape[t] = (t - start + 1) ** u(1.0, 1.8) * u(0.5, 1.5)
    total = called * moic
    s = sum(shape)
    proceeds = [round(total * x / s, 1) for x in shape]
    return calls, proceeds


def generate(rng: random.Random, level: int) -> Bundle:
    cfg = LEVELS[level]
    return _jv(rng, cfg, level) if cfg["kind"] == "jv" else _european(rng, cfg, level)


def _european(rng: random.Random, cfg: dict, level: int) -> Bundle:
    u = rng.uniform
    n = cfg["n"]
    commitment = round(10 ** u(2.2, 3.2), 0)
    inv_period = rng.randint(3, 5)
    calls, proceeds = _flows(rng, n, commitment, inv_period)
    periods = ["Inception"] + [f"Year {i + 1}" for i in range(n)]
    A, M = "Assumptions", "Model"
    pref = rng.choice([0.07, 0.08, 0.08, 0.09])
    carry = rng.choice([0.15, 0.20, 0.20, 0.25])
    catchup = {"full": 1.0, "partial": rng.choice([0.5, 0.6, 0.8])}.get(cfg["catchup"])
    g = round(u(0.01, 0.03), 3) if cfg["gp_commit"] else 0.0
    scalars = [Scalar("pref", "Preferred return (annual)", pref, "%", "rate"),
               Scalar("carry", "Carried interest", carry, "%", "rate")]
    if catchup is not None:
        scalars.append(Scalar("catchup", "GP share of distributions during catch-up", catchup, "%", "rate"))
    if g:
        scalars.append(Scalar("gp_commit", "GP commitment (share of all contributions)", g, "%", "rate"))
    if cfg["fees"]:
        scalars += [Scalar("commitment", "Total commitments", commitment, "$m", "money"),
                    Scalar("inv_period", "Investment period (years)", float(inv_period), "yrs", "count"),
                    Scalar("fee1", "Management fee during investment period (% of commitments)",
                           round(u(0.015, 0.02), 4), "%", "rate"),
                    Scalar("fee2", "Management fee after investment period (% of unreturned capital)",
                           round(u(0.01, 0.015), 4), "%", "rate")]
    lines: List[Line] = [
        Line("calls", "Capital calls for investments", A, fc=None, hist="blank", forecast=calls, kind="money"),
        Line("proceeds", "Gross proceeds available for distribution", A, fc=None, hist="blank",
             forecast=proceeds, kind="money"),
    ]
    if cfg["fees"]:
        lines += [
            Line("year", "Fund year", M, unit="#", fc="{year[-1]}+1", history=[0.0], kind="ratio",
                 desc="prior year + 1", section="Contributions"),
            Line("fee", "Management fee", M,
                 fc="IF({year}<={$inv_period},{$commitment}*{$fee1},{roc_close[-1]}*{$fee2})", hist="blank",
                 desc="during the investment period: commitments x fee 1; afterwards: opening unreturned capital "
                      "x fee 2"),
            Line("contrib", "Total contributions", M, fc="{calls}+{fee}", hist="blank",
                 desc="capital calls + management fee"),
        ]
        contrib = "{contrib}"
    else:
        lines.append(Line("contrib", "Total contributions", M, fc="{calls}", hist="blank",
                          desc="capital calls", section="Contributions"))
        contrib = "{contrib}"
    pref_base = f"{{roc_close[-1]}}+{contrib}" + ("+{pref_close[-1]}" if cfg["compound"] else "")
    lines += [
        Line("roc_paid", "Tier 1 - return of capital", M, fc=f"MIN({{proceeds}},{{roc_close[-1]}}+{contrib})",
             hist="blank", section="Waterfall",
             desc="the smaller of proceeds and (opening unreturned capital + contributions)"),
        Line("roc_close", "Unreturned capital - closing", M, fc=f"{{roc_close[-1]}}+{contrib}-{{roc_paid}}",
             history=[0.0], desc="opening + contributions - return of capital"),
        Line("pref_accr", "Preferred return accrued", M, fc=f"{{$pref}}*({pref_base})", hist="blank",
             desc="pref rate x (opening unreturned capital + contributions"
                  + (" + opening unpaid pref)" if cfg["compound"] else ")")),
        Line("pref_paid", "Tier 2 - preferred return paid", M,
             fc="MIN({proceeds}-{roc_paid},{pref_close[-1]}+{pref_accr})", hist="blank",
             desc="the smaller of proceeds left after tier 1 and (opening unpaid pref + accrual)"),
        Line("pref_close", "Unpaid preferred return - closing", M,
             fc="{pref_close[-1]}+{pref_accr}-{pref_paid}", history=[0.0],
             desc="opening + accrual - paid"),
        Line("cum_pref", "Cumulative preferred return paid", M, fc="{cum_pref[-1]}+{pref_paid}", history=[0.0],
             desc="prior cumulative + pref paid this year"),
    ]
    resid_terms = "{proceeds}-{roc_paid}-{pref_paid}"
    if catchup is not None:
        lines += [
            Line("cu_paid", "Tier 3 - catch-up distributions (total)", M,
                 fc="MIN({proceeds}-{roc_paid}-{pref_paid},MAX(0,{$carry}*{cum_pref}/({$catchup}-{$carry})"
                    "-{cum_cu[-1]}))", hist="blank",
                 desc="the smaller of cash left after tier 2 and MAX(0, carry x cumulative pref paid / "
                      "(catch-up share - carry) - cumulative catch-up paid before this year)"),
            Line("cum_cu", "Cumulative catch-up distributions", M, fc="{cum_cu[-1]}+{cu_paid}", history=[0.0],
                 desc="prior cumulative + catch-up this year"),
        ]
        resid_terms += "-{cu_paid}"
    lines.append(Line("residual", "Tier 4 - residual split", M, fc=resid_terms, hist="blank",
                      desc="proceeds - all earlier tiers"))
    carry_fc = ("{cu_paid}*{$catchup}+" if catchup is not None else "") + "{residual}*{$carry}"
    lines.append(Line("gp_carry", "GP carried interest", M, fc=carry_fc, hist="blank",
                      desc=("catch-up x GP catch-up share + " if catchup is not None else "")
                           + "residual x carry %"))
    if g:
        lines += [
            Line("lp_dist", "Distributions to LPs", M, fc="(1-{$gp_commit})*({proceeds}-{gp_carry})",
                 hist="blank", desc="(1 - GP commitment share) x (proceeds - GP carry)"),
            Line("gp_total", "Total distributions to GP (carry + GP investor share)", M,
                 fc="{gp_carry}+{$gp_commit}*({proceeds}-{gp_carry})", hist="blank",
                 desc="GP carry + GP commitment share x (proceeds - GP carry)"),
            Line("lp_cf", "LP net cash flow", M, fc="{lp_dist}-(1-{$gp_commit})*{contrib}", hist="blank",
                 desc="LP distributions - LP share of contributions"),
        ]
    else:
        lines += [
            Line("lp_dist", "Distributions to LPs", M, fc="{proceeds}-{gp_carry}", hist="blank",
                 desc="proceeds - GP carry"),
            Line("gp_total", "Total distributions to GP", M, fc="{gp_carry}", hist="blank", desc="GP carry"),
            Line("lp_cf", "LP net cash flow", M, fc="{lp_dist}-{contrib}", hist="blank",
                 desc="LP distributions - contributions"),
        ]
    calcs = [
        Calc("tot_contrib", "Total contributions", M, "SUM({contrib@fc})", section="Fund totals",
             desc="sum of contributions"),
        Calc("tot_dist", "Total proceeds distributed", M, "SUM({proceeds@fc})", desc="sum of proceeds"),
        Calc("tot_carry", "Total GP carried interest", M, "SUM({gp_carry@fc})", desc="sum of GP carry"),
        Calc("tot_lp", "Total LP distributions", M, "SUM({lp_dist@fc})", desc="sum of LP distributions"),
        Calc("lp_irr", "LP net IRR", M, "IRR({lp_cf@fc})", unit="%", kind="ratio", desc="IRR of LP net cash flows"),
    ]
    if cfg["fees"]:
        calcs += [
            Calc("carry_cap", "Maximum carry (carry % of total fund profit)", M,
                 "{$carry}*MAX(0,{tot_dist}-{tot_contrib})", desc="carry % x MAX(0, total proceeds - total "
                                                                   "contributions)"),
            Calc("clawback", "GP clawback due at fund end", M, "MAX(0,{tot_carry}-{carry_cap})",
                 desc="MAX(0, total GP carry - maximum carry)"),
        ]
    spec = ModelSpec(title="Fund distribution waterfall", periods=periods, n_hist=1, sheets=[A, M],
                     scalars=scalars, lines=lines, calcs=calcs)

    cu_text = {
        None: "",
        "full": "TIER 3 - GP CATCH-UP: 100% of the remaining cash goes to the GP until the GP has received, "
                "cumulatively, the carry % of all preferred return plus catch-up distributed (i.e. cumulative "
                "catch-up = carry x cumulative pref paid / (1 - carry)). ",
        "partial": "TIER 3 - GP CATCH-UP: the remaining cash is split, the GP receiving the catch-up share and the "
                   "investors the rest, until the GP's catch-up receipts equal the carry % of all preferred return "
                   "plus catch-up distributed. Equivalently, cumulative catch-up distributions (total, both "
                   "sides) may reach carry x cumulative pref paid / (catch-up share - carry); each year's catch-up "
                   "is the smaller of cash remaining and that target less catch-up already paid (never negative). ",
    }[cfg["catchup"]]
    ts = [
        "CONTRIBUTIONS are made at the start of each year" + (
            " and comprise capital calls for investments plus the management fee: during the investment period "
            "(fund years up to and including the investment period) the fee is fee 1 x total commitments; "
            "afterwards it is fee 2 x unreturned capital at the start of the year. Fees count as contributed "
            "capital." if cfg["fees"] else " (capital calls)."),
        "Each year's gross proceeds are distributed at year end through the tiers below, in order.",
        "TIER 1 - RETURN OF CAPITAL: 100% to investors until all capital contributed to date (including this "
        "year's contributions) has been returned. Track unreturned capital.",
        "TIER 2 - PREFERRED RETURN: 100% to investors until they have received the preferred return. The pref "
        "accrues each year at the pref rate on unreturned capital at the start of the year plus that year's "
        "contributions" + (" plus pref accrued in earlier years and not yet paid (compounding)." if cfg["compound"]
                           else " (simple, not compounding)."),
        cu_text + ("TIER 4 - CARRY: the rest is split, the GP receiving the carried-interest % and the investors the "
                   "remainder." if catchup is not None else "TIER 3 - CARRY: the rest is split, the GP receiving "
                   "the carried-interest % and the investors the remainder."),
    ]
    if g:
        ts.append("GP COMMITMENT: the GP is also an investor for its commitment share. It pays that share of all "
                  "contributions and receives that share of everything distributed to investors (all tiers except "
                  "its carry). LP figures exclude the GP's investor share.")
    ts.append("FUND TOTALS: totals are sums over all years; LP net IRR is the IRR of yearly LP net cash flows "
              "(LP distributions minus LP contributions).")
    if cfg["fees"]:
        ts.append("CLAWBACK TEST at fund end: maximum carry = carry % x the greater of zero and (total proceeds - "
                  "total contributions); clawback = the excess of total GP carry over that maximum, never negative.")
    conventions = ["Contributions at the start of the year, distributions at year end; the Inception column "
                   "holds opening balances (zero for a new fund).",
                   "All amounts are positive; LP net cash flow is negative when the LP pays in more than it "
                   "receives."]
    ids = [IdSpec("tiers_distribute_all_proceeds", "sum of tiers = proceeds",
                  [(1, "roc_paid", 0), (1, "pref_paid", 0), (1, "residual", 0), (-1, "proceeds", 0)]
                  + ([(1, "cu_paid", 0)] if catchup is not None else [])),
           IdSpec("lp_plus_gp_equals_proceeds", "LP + GP distributions = proceeds",
                  [(1, "lp_dist", 0), (1, "gp_total", 0), (-1, "proceeds", 0)]),
           IdSpec("unreturned_capital_rollforward", "unreturned capital roll-forward",
                  [(1, "roc_close", 0), (-1, "roc_close", -1), (-1, "contrib", 0), (1, "roc_paid", 0)]),
           IdSpec("unpaid_pref_rollforward", "unpaid pref roll-forward",
                  [(1, "pref_close", 0), (-1, "pref_close", -1), (-1, "pref_accr", 0), (1, "pref_paid", 0)]),
           IdSpec("total_carry_is_sum", "total carry = sum of yearly carry", [(1, "tot_carry", 0)]
                  + [], when="once")]
    ids = [i for i in ids if i.name != "total_carry_is_sum"]
    mono = [MonoSpec("carry_total_rises_with_carry_pct", "tot_carry", "carry", 0.02, 1),
            MonoSpec("lp_total_falls_with_carry_pct", "tot_lp", "carry", 0.02, -1)]
    outputs = [("roc_paid", "Return of capital"), ("pref_paid", "Preferred return paid")]
    if catchup is not None:
        outputs.append(("cu_paid", "Catch-up distributions"))
    outputs += [("lp_dist", "Distributions to LPs"), ("gp_total", "Distributions to GP"),
                ("tot_carry", "Total GP carried interest"), ("lp_irr", "LP net IRR")]
    if cfg["fees"]:
        outputs.append(("clawback", "GP clawback due"))
    kinds = {"pref": ("rate", 0.0, 0.2), "carry": ("rate", 0.05, 0.4), "catchup": ("rate", 0.45, 1.0),
             "gp_commit": ("rate", 0.0, 0.1), "fee1": ("rate", 0.0, 0.04), "fee2": ("rate", 0.0, 0.04),
             "inv_period": ("count", 1.0, 8.0), "calls": ("money", 0.0, None), "proceeds": ("money", 0.0, None)}
    return Bundle(domain="waterfall", noun="private-equity fund distribution waterfall", spec=spec,
                  term_sheet="\n".join(ts), conventions=conventions, identities=ids, monotone=mono, kinds=kinds,
                  outputs=outputs, scale=commitment / 10, level=level, meta={"structure": "european"})


def _jv(rng: random.Random, cfg: dict, level: int) -> Bundle:
    u = rng.uniform
    n = cfg["n"]
    equity = round(10 ** u(1.8, 2.8), 0)
    call_years = rng.randint(2, 3)
    calls, proceeds = _flows(rng, n, equity, call_years)
    periods = ["Inception"] + [f"Year {i + 1}" for i in range(n)]
    A, M = "Assumptions", "Model"
    h = sorted(rng.sample([0.08, 0.10, 0.12, 0.15, 0.18, 0.20], 3))
    s = [1.0, rng.choice([0.85, 0.8]), rng.choice([0.75, 0.7]), rng.choice([0.6, 0.5])]
    scalars = []
    for k in range(3):
        scalars.append(Scalar(f"h{k + 1}", f"Hurdle {k + 1} (IRR)", h[k], "%", "rate"))
    for k in range(4):
        scalars.append(Scalar(f"s{k + 1}", f"LP share of tier {k + 1}", s[k], "%", "rate"))
    lines: List[Line] = [
        Line("calls", "Equity contributions (LP)", A, fc=None, hist="blank", forecast=calls, kind="money"),
        Line("proceeds", "Cash available for distribution", A, fc=None, hist="blank", forecast=proceeds,
             kind="money"),
    ]
    lp_prior = []
    cash_prior = []
    for k in (1, 2, 3):
        lines.append(Line(f"acc{k}_pre", f"Hurdle {k} account before distributions", M,
                          fc=f"({{acc{k}[-1]}}+{{calls}})*(1+{{$h{k}}})", hist="blank",
                          section="Waterfall" if k == 1 else "",
                          desc=f"(opening account {k} + contributions) x (1 + hurdle {k})"))
        need = f"{{acc{k}_pre}}" + "".join(f"-{x}" for x in lp_prior)
        avail = "{proceeds}" + "".join(f"-{x}" for x in cash_prior)
        lines.append(Line(f"t{k}_cash", f"Tier {k} cash distributed", M,
                          fc=f"MIN({avail},MAX(0,{need})/{{$s{k}}})", hist="blank",
                          desc=f"the smaller of cash left and MAX(0, account {k} before distributions - LP cash "
                               f"from earlier tiers) / LP share of tier {k}"))
        lines.append(Line(f"t{k}_lp", f"Tier {k} - to LP", M, fc=f"{{t{k}_cash}}*{{$s{k}}}", hist="blank",
                          desc=f"tier {k} cash x LP share"))
        lp_prior.append(f"{{t{k}_lp}}")
        cash_prior.append(f"{{t{k}_cash}}")
    lines.append(Line("t4_cash", "Tier 4 cash distributed (residual)", M,
                      fc="{proceeds}-{t1_cash}-{t2_cash}-{t3_cash}", hist="blank", desc="cash left after tier 3"))
    lines.append(Line("t4_lp", "Tier 4 - to LP", M, fc="{t4_cash}*{$s4}", hist="blank", desc="tier 4 x LP share"))
    lines.append(Line("lp_dist", "Total distributions to LP", M, fc="{t1_lp}+{t2_lp}+{t3_lp}+{t4_lp}",
                      hist="blank", desc="sum of LP tier distributions"))
    lines.append(Line("promote", "Sponsor promote", M, fc="{proceeds}-{lp_dist}", hist="blank",
                      desc="cash distributed - LP distributions"))
    for k in (1, 2, 3):
        lines.append(Line(f"acc{k}", f"Hurdle {k} account - closing", M, fc=f"MAX(0,{{acc{k}_pre}}-{{lp_dist}})",
                          history=[0.0], desc=f"MAX(0, account {k} before distributions - total LP distributions)"))
    lines.append(Line("lp_cf", "LP net cash flow", M, fc="{lp_dist}-{calls}", hist="blank",
                      desc="LP distributions - contributions"))
    calcs = [Calc("tot_promote", "Total sponsor promote", M, "SUM({promote@fc})", section="Totals",
                  desc="sum of promote"),
             Calc("tot_lp", "Total LP distributions", M, "SUM({lp_dist@fc})", desc="sum of LP distributions"),
             Calc("lp_irr", "LP IRR", M, "IRR({lp_cf@fc})", unit="%", kind="ratio", desc="IRR of LP net cash flows")]
    spec = ModelSpec(title="JV promote waterfall", periods=periods, n_hist=1, sheets=[A, M], scalars=scalars,
                     lines=lines, calcs=calcs)
    ts = [
        "The LP contributes all equity at the start of each year; cash available is distributed at year end "
        "through four tiers in order.",
        "HURDLE ACCOUNTS: for each hurdle k = 1..3 keep an account: (opening balance + this year's contributions) "
        "grows by hurdle k for the year; every dollar distributed to the LP (from any tier) then reduces it; the "
        "closing balance is never below zero (a hurdle that has been exceeded does not go negative).",
        "TIER k (k = 1, 2, 3): cash is split between the LP (LP share of tier k) and the sponsor (the rest) until "
        "the LP's distributions this year, including those from earlier tiers, have reduced hurdle account k to "
        "zero. So tier k distributes the smaller of the cash still available and (account k before distributions "
        "minus LP cash already received this year, floored at zero) divided by the LP share of tier k.",
        "TIER 4: all remaining cash, split at the LP share of tier 4; the sponsor's share is its promote.",
        "TOTALS: sums over all years; LP IRR = IRR of yearly LP net cash flows (distributions minus "
        "contributions).",
    ]
    conventions = ["Contributions at the start of the year, distributions at year end; the Inception column holds "
                   "opening hurdle balances (zero for a new venture).",
                   "Hurdle accounts and distributions are positive amounts."]
    ids = [IdSpec("tiers_distribute_all_cash", "sum of tier cash = cash available",
                  [(1, "t1_cash", 0), (1, "t2_cash", 0), (1, "t3_cash", 0), (1, "t4_cash", 0), (-1, "proceeds", 0)]),
           IdSpec("lp_plus_promote", "LP + promote = cash available",
                  [(1, "lp_dist", 0), (1, "promote", 0), (-1, "proceeds", 0)])]
    mono = [MonoSpec("promote_falls_as_lp_share_rises", "tot_promote", "s4", 0.05, -1),
            MonoSpec("lp_total_rises_with_hurdle1", "tot_lp", "h1", 0.01, 1)]
    outputs = [("t1_cash", "Tier 1 cash"), ("t2_cash", "Tier 2 cash"), ("t3_cash", "Tier 3 cash"),
               ("lp_dist", "Distributions to LP"), ("promote", "Sponsor promote"),
               ("tot_promote", "Total sponsor promote"), ("lp_irr", "LP IRR")]
    kinds = {f"h{k}": ("rate", 0.0, 0.35) for k in (1, 2, 3)}
    kinds.update({f"s{k}": ("rate", 0.3, 1.0) for k in (1, 2, 3, 4)})
    kinds.update({"calls": ("money", 0.0, None), "proceeds": ("money", 0.0, None)})
    return Bundle(domain="waterfall", noun="joint-venture promote (distribution waterfall) model", spec=spec,
                  term_sheet="\n".join(ts), conventions=conventions, identities=ids, monotone=mono, kinds=kinds,
                  outputs=outputs, scale=equity / 10, level=level, meta={"structure": "jv"})
