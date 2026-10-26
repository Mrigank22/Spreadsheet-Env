"""Fund distribution model specified by a LIMITED PARTNERSHIP AGREEMENT (document-grade spec).

The agent receives a generated LPA (alphabetical definitions, cross-referenced
articles, provisos, distractor clauses) and builds the fund's annual cash-flow
and distribution model from it.

Levels (each adds to the previous one):

1. European (whole-fund) waterfall: return of Capital Contributions, a Preferred
   Return compounded annually, a 100% GP catch-up, then the carried-interest split.
2. + Management Fee: a % of Commitments during the Commitment Period, then a % of
   Invested Capital; fees are funded by Capital Contributions (so they are returned
   and earn the Preferred Return).
3. + GP Commitment that bears no Management Fee, with Distributable Proceeds
   apportioned between the GP (as investor) and the Limited Partners before the
   waterfall; Management Fee Offset of Transaction Fees with a carried-forward
   excess; partial (80%) catch-up.
4. + end-of-fund clawback limited to after-tax carry; LP net IRR including the
   clawback receipt.
5. + Carry escrow: a share of every carry distribution is held back and applied
   first to the clawback at dissolution, the balance released to the GP.
"""

from __future__ import annotations

import random
from typing import List

from ...model.spec import Calc, Line, ModelSpec, Scalar
from ..framework import Bundle, IdSpec, MonoSpec
from .legal import LegalDoc, company_name

DOMAIN = "lpa"

LEVELS = {
    1: dict(fees=False, gp=False, offset=False, partial=False, clawback=False, escrow=False, n=10),
    2: dict(fees=True, gp=False, offset=False, partial=False, clawback=False, escrow=False, n=10),
    3: dict(fees=True, gp=True, offset=True, partial=True, clawback=False, escrow=False, n=10),
    4: dict(fees=True, gp=True, offset=True, partial=True, clawback=True, escrow=False, n=12),
    5: dict(fees=True, gp=True, offset=True, partial=True, clawback=True, escrow=True, n=12),
}

CAP = {
    "commit": "Commitments",
    "gp_pct": "GP Commitment Percentage",
    "pref": "Preferred Return Rate",
    "carry": "Carried Interest Percentage",
    "cu": "Catch-Up Percentage",
    "cp_years": "Commitment Period (Fiscal Years)",
    "fee1": "Management Fee Rate - Commitment Period",
    "fee2": "Management Fee Rate - Post-Commitment Period",
    "offset_pct": "Offset Percentage",
    "tax": "Assumed Tax Rate",
    "escrow_pct": "Escrow Percentage",
    "calls": "Capital called for Portfolio Investments",
    "proceeds": "Distributable Proceeds",
    "inv_cap": "Invested Capital",
    "tx_fees": "Transaction Fees",
}


def q(key: str) -> str:
    return f"\"{CAP[key]}\""


def generate(rng: random.Random, level: int) -> Bundle:
    cfg = LEVELS[level]
    u = rng.uniform
    n = cfg["n"]
    fees, gp, offset, partial = cfg["fees"], cfg["gp"], cfg["offset"], cfg["partial"]
    clawback, escrow = cfg["clawback"], cfg["escrow"]
    commit = float(round(10 ** u(2.4, 3.3), 0))
    cp_years = rng.randint(4, 6)
    # capital calls during the Commitment Period, proceeds rising after year 3
    w = [u(0.6, 1.4) for _ in range(cp_years)]
    called = u(0.75, 0.90) * commit
    calls = [round(called * x / sum(w), 1) for x in w] + [0.0] * (n - cp_years)
    gross_moic = u(1.4, 2.4)
    start = rng.randint(2, 4)
    shape = [0.0] * n
    for t in range(start, n):
        shape[t] = (t - start + 1) ** u(0.6, 1.4) * u(0.6, 1.4)
    total = called * gross_moic
    proceeds = [round(total * x / sum(shape), 1) for x in shape]
    # Invested Capital (cost of Portfolio Investments held) at the start of each year: cumulative
    # calls less the cost realised so far (cost realised in proportion to proceeds)
    inv_cap, held, realised = [], 0.0, 0.0
    for t in range(n):
        held += calls[t]
        inv_cap.append(round(max(0.0, held - realised), 1))
        realised += called * proceeds[t] / total
    tx = [round(calls[t] * u(0.005, 0.02), 1) for t in range(n)]
    fund = company_name(rng).split()[0] + " Capital Partners"
    pref = rng.choice([0.07, 0.08, 0.08, 0.09])
    carry = rng.choice([0.15, 0.2, 0.2, 0.25])
    cu = rng.choice([0.8, 0.8, 0.6]) if partial else 1.0

    A, M = "Assumptions", "Model"
    S = Scalar
    scalars: List[Scalar] = [S("pref", CAP["pref"], pref, "%", "rate"), S("carry", CAP["carry"], carry, "%", "rate")]
    if partial:
        scalars.append(S("cu", CAP["cu"], cu, "%", "rate"))
    if fees:
        scalars += [S("commit", CAP["commit"], commit, "$m", "money"),
                    S("cp_years", CAP["cp_years"], float(cp_years), "yrs", "count"),
                    S("fee2", CAP["fee2"], round(u(0.0100, 0.0150), 4), "%", "rate"),
                    S("fee1", CAP["fee1"], round(u(0.0175, 0.0200), 4), "%", "rate")]
    if gp:
        scalars.append(S("gp_pct", CAP["gp_pct"], round(u(0.01, 0.03), 3), "%", "rate"))
    if offset:
        scalars.append(S("offset_pct", CAP["offset_pct"], rng.choice([0.5, 0.8, 1.0]), "%", "rate"))
    if clawback:
        scalars.append(S("tax", CAP["tax"], round(u(0.35, 0.45), 3), "%", "tax"))
    if escrow:
        scalars.append(S("escrow_pct", CAP["escrow_pct"], rng.choice([0.2, 0.25, 0.3]), "%", "rate"))

    lines: List[Line] = [
        Line("calls", CAP["calls"], A, fc=None, hist="blank", forecast=calls, kind="money"),
        Line("proceeds", CAP["proceeds"], A, fc=None, hist="blank", forecast=proceeds, kind="money"),
    ]
    if fees:
        lines.append(Line("inv_cap", CAP["inv_cap"], A, fc=None, hist="blank", forecast=inv_cap, kind="money"))
    if offset:
        lines.append(Line("tx_fees", CAP["tx_fees"], A, fc=None, hist="blank", forecast=tx, kind="money"))
    lp_share = "(1-{$gp_pct})" if gp else "1"
    if fees:
        commit_lp = f"{{$commit}}*{lp_share}" if gp else "{$commit}"
        inv_lp = f"{{inv_cap}}*{lp_share}" if gp else "{inv_cap}"
        lines += [
            Line("year", "Fiscal Year number", M, unit="#", kind="ratio", fc="{year[-1]}+1", history=[0.0],
                 section="Management Fee"),
            Line("base_fee", "Management Fee before offsets", M, hist="blank",
                 fc=f"IF({{year}}<={{$cp_years}},{{$fee1}}*{commit_lp},{{$fee2}}*{inv_lp})"),
        ]
        if offset:
            lines += [
                Line("offset_new", "Offset arising from Transaction Fees", M, fc="{$offset_pct}*{tx_fees}",
                     hist="blank"),
                Line("offset_used", "Offset applied", M, fc="MIN({base_fee},{offset_cf[-1]}+{offset_new})",
                     hist="blank"),
                Line("offset_cf", "Unapplied offset carried forward - closing", M,
                     fc="{offset_cf[-1]}+{offset_new}-{offset_used}", history=[0.0]),
                Line("fee", "Management Fee", M, fc="{base_fee}-{offset_used}", hist="blank"),
            ]
        else:
            lines.append(Line("fee", "Management Fee", M, fc="{base_fee}", hist="blank"))
    contrib = f"{{calls}}*{lp_share}" if gp else "{calls}"
    contrib += "+{fee}" if fees else ""
    lines.append(Line("lp_contrib", "Limited Partners' Capital Contributions", M, fc=contrib, hist="blank",
                      section="Contributions and apportionment"))
    if gp:
        lines += [
            Line("gp_contrib", "General Partner's Capital Contributions", M, fc="{calls}*{$gp_pct}", hist="blank"),
            Line("gp_inv_dist", "Distributions to the General Partner in respect of its Commitment", M,
                 fc="{proceeds}*{$gp_pct}", hist="blank"),
            Line("lp_proc", "Distributable Proceeds apportioned to the Limited Partners", M,
                 fc="{proceeds}-{gp_inv_dist}", hist="blank"),
        ]
        lp_proc = "{lp_proc}"
    else:
        lp_proc = "{proceeds}"
    target = f"{{$carry}}*{{cum_pref}}/({{$cu}}-{{$carry}})" if partial else "{$carry}*{cum_pref}/(1-{$carry})"
    cu_share = "{$cu}" if partial else "1"
    lines += [
        Line("roc_paid", "Distributions under clause (a) (return of capital)", M, hist="blank",
             fc=f"MIN({lp_proc},{{roc_close[-1]}}+{{lp_contrib}})", section="Distribution waterfall"),
        Line("roc_close", "Unreturned Capital Contributions - closing", M,
             fc="{roc_close[-1]}+{lp_contrib}-{roc_paid}", history=[0.0]),
        Line("pref_accr", "Preferred Return accrued", M, hist="blank",
             fc="{$pref}*({roc_close[-1]}+{lp_contrib}+{pref_close[-1]})"),
        Line("pref_paid", "Distributions under clause (b) (Preferred Return)", M, hist="blank",
             fc=f"MIN({lp_proc}-{{roc_paid}},{{pref_close[-1]}}+{{pref_accr}})"),
        Line("pref_close", "Unpaid Preferred Return - closing", M, fc="{pref_close[-1]}+{pref_accr}-{pref_paid}",
             history=[0.0]),
        Line("cum_pref", "Cumulative distributions under clause (b)", M, fc="{cum_pref[-1]}+{pref_paid}",
             history=[0.0]),
        Line("cu_paid", "Distributions under clause (c) (catch-up), total", M, hist="blank",
             fc=f"MIN({lp_proc}-{{roc_paid}}-{{pref_paid}},MAX(0,{target}-{{cum_cu[-1]}}))"),
        Line("cum_cu", "Cumulative distributions under clause (c)", M, fc="{cum_cu[-1]}+{cu_paid}", history=[0.0]),
        Line("residual", "Distributions under clause (d) (residual)", M, hist="blank",
             fc=f"{lp_proc}-{{roc_paid}}-{{pref_paid}}-{{cu_paid}}"),
        Line("carry_t", "Carried Interest distributed", M, fc=f"{{cu_paid}}*{cu_share}+{{residual}}*{{$carry}}",
             hist="blank"),
        Line("lp_dist", "Distributions to the Limited Partners", M, fc=f"{lp_proc}-{{carry_t}}", hist="blank"),
    ]
    if escrow:
        lines += [
            Line("escrow_in", "Carried Interest deposited in the Escrow Account", M, fc="{carry_t}*{$escrow_pct}",
                 hist="blank", section="Escrow"),
            Line("carry_cash", "Carried Interest paid to the General Partner", M, fc="{carry_t}-{escrow_in}",
                 hist="blank"),
            Line("escrow", "Escrow Account - closing", M, fc="{escrow[-1]}+{escrow_in}", history=[0.0]),
        ]
    calcs: List[Calc] = [
        Calc("tot_lp_contrib", "Total Limited Partner Capital Contributions", M, "SUM({lp_contrib@fc})",
             section="Fund totals"),
        Calc("tot_lp_proc", "Total Distributable Proceeds apportioned to the Limited Partners", M,
             f"SUM({{{'lp_proc' if gp else 'proceeds'}@fc}})"),
        Calc("tot_carry", "Total Carried Interest distributed", M, "SUM({carry_t@fc})"),
    ]
    if clawback:
        calcs += [
            Calc("net_profit", "Net Profits of the Limited Partners", M, "MAX(0,{tot_lp_proc}-{tot_lp_contrib})"),
            Calc("clawback", "Clawback Amount", M,
                 "MIN(MAX(0,{tot_carry}-{$carry}*{net_profit}),{tot_carry}*(1-{$tax}))"),
        ]
        if escrow:
            calcs += [
                Calc("claw_escrow", "Clawback Amount paid from the Escrow Account", M,
                     "MIN({clawback},{escrow@last})"),
                Calc("claw_gp", "Clawback Amount paid by the General Partner", M, "{clawback}-{claw_escrow}"),
                Calc("escrow_rel", "Escrow Account released to the General Partner", M,
                     "{escrow@last}-{claw_escrow}"),
            ]
        lines.append(Line("lp_cf", "LP net cash flow", M, fc="{lp_dist}-{lp_contrib}",
                          fc_last="{lp_dist}-{lp_contrib}+{clawback}", hist="blank", section="LP returns"))
    else:
        lines.append(Line("lp_cf", "LP net cash flow", M, fc="{lp_dist}-{lp_contrib}", hist="blank",
                          section="LP returns"))
    calcs.append(Calc("lp_irr", "LP net IRR", M, "IRR({lp_cf@fc})", unit="%", kind="ratio"))
    spec = ModelSpec(title="Fund model", periods=["Inception"] + [f"FY{i + 1}" for i in range(n)], n_hist=1,
                     sheets=[A, M], scalars=scalars, lines=lines, calcs=calcs)

    doc = _lpa(cfg, fund, rng)
    conventions = [
        "The Agreement above governs. Implement every provision that affects the rows of the Model exactly as "
        "drafted; provisions about events that do not occur in the Model (see Annex A) have no effect.",
        "Amounts in $ millions; percentages as decimals (8% = 0.08).",
    ]
    ids = [IdSpec("waterfall_distributes_lp_proceeds", "clauses (a)-(d) distribute the LP proceeds",
                  [(1, "roc_paid", 0), (1, "pref_paid", 0), (1, "cu_paid", 0), (1, "residual", 0)]
                  + ([(-1, "lp_proc", 0)] if gp else [(-1, "proceeds", 0)])),
           IdSpec("lp_plus_carry", "LP distributions + carry = LP proceeds",
                  [(1, "lp_dist", 0), (1, "carry_t", 0)] + ([(-1, "lp_proc", 0)] if gp else [(-1, "proceeds", 0)])),
           IdSpec("unreturned_rollforward", "unreturned capital roll-forward",
                  [(1, "roc_close", 0), (-1, "roc_close", -1), (-1, "lp_contrib", 0), (1, "roc_paid", 0)]),
           IdSpec("pref_rollforward", "unpaid pref roll-forward",
                  [(1, "pref_close", 0), (-1, "pref_close", -1), (-1, "pref_accr", 0), (1, "pref_paid", 0)])]
    if gp:
        ids.append(IdSpec("apportionment", "GP + LP apportionment = proceeds",
                          [(1, "gp_inv_dist", 0), (1, "lp_proc", 0), (-1, "proceeds", 0)]))
    if offset:
        ids += [IdSpec("offset_rollforward", "offset carried forward roll-forward",
                       [(1, "offset_cf", 0), (-1, "offset_cf", -1), (-1, "offset_new", 0), (1, "offset_used", 0)]),
                IdSpec("fee_after_offset", "fee = base fee - offset applied",
                       [(1, "fee", 0), (1, "offset_used", 0), (-1, "base_fee", 0)])]
    if escrow:
        ids.append(IdSpec("escrow_rollforward", "escrow roll-forward",
                          [(1, "escrow", 0), (-1, "escrow", -1), (-1, "escrow_in", 0)]))
    mono = [MonoSpec("carry_rises_with_carry_pct", "tot_carry", "carry", 0.02, 1)]
    outputs = [("lp_contrib", "Limited Partners' Capital Contributions"),
               ("roc_paid", "Distributions under clause (a) (return of capital)"),
               ("pref_paid", "Distributions under clause (b) (Preferred Return)"),
               ("cu_paid", "Distributions under clause (c) (catch-up), total"),
               ("carry_t", "Carried Interest distributed"), ("lp_dist", "Distributions to the Limited Partners"),
               ("tot_carry", "Total Carried Interest distributed"), ("lp_irr", "LP net IRR")]
    if fees:
        outputs.insert(0, ("fee", "Management Fee"))
    if clawback:
        outputs.append(("clawback", "Clawback Amount"))
    if escrow:
        outputs += [("escrow", "Escrow Account - closing"), ("claw_gp", "Clawback Amount paid by the General Partner")]
    kinds = {"pref": ("rate", 0.0, 0.2), "carry": ("rate", 0.05, 0.4), "cu": ("rate", 0.5, 1.0),
             "gp_pct": ("rate", 0.0, 0.1), "fee1": ("rate", 0.0, 0.04), "fee2": ("rate", 0.0, 0.04),
             "cp_years": ("count", 1.0, 8.0), "offset_pct": ("rate", 0.0, 1.0), "tax": ("tax", 0.0, 0.6),
             "escrow_pct": ("rate", 0.0, 0.6), "calls": ("money", 0.0, None), "proceeds": ("money", 0.0, None),
             "inv_cap": ("money", 0.0, None), "tx_fees": ("money", 0.0, None)}
    asc = [("fee2", "fee1")] if fees else []
    return Bundle(domain=DOMAIN, noun=f"fund distribution model under a limited partnership agreement ({fund})",
                  spec=spec, term_sheet=doc, conventions=conventions, identities=ids, monotone=mono, kinds=kinds,
                  outputs=outputs, scale=commit / 10, level=level, fixed_when_zero=("calls", "tx_fees"),
                  ascending_scalars=asc, meta={"years": n, "document": "limited partnership agreement"})


def _lpa(cfg: dict, fund: str, rng: random.Random) -> str:
    fees, gp, offset, partial = cfg["fees"], cfg["gp"], cfg["offset"], cfg["partial"]
    clawback, escrow = cfg["clawback"], cfg["escrow"]
    doc = LegalDoc(f"Amended and Restated Agreement of Limited Partnership of {fund}, L.P.",
                   f"AMENDED AND RESTATED AGREEMENT OF LIMITED PARTNERSHIP of {fund}, L.P. (the \"Partnership\") among "
                   f"{fund} GP, LLC, as general partner (the \"General Partner\"), and the limited partners party hereto "
                   "(the \"Limited Partners\" and, together with the General Partner, the \"Partners\"). Amounts, rates "
                   "and periods referred to by a caption in quotation marks are set forth in Schedule 1 (the "
                   "Assumptions sheet of the Model).", section_word="Section")
    D = doc.define
    lp_word = "the Limited Partners"
    # ---- operative definitions
    D("Capital Contributions", "means the amounts contributed to the Partnership by a Partner pursuant to "
      "[[contributions]]" + (", including amounts contributed to fund Management Fees" if fees else "") + ".")
    if partial:
        D("Catch-Up Percentage", f"means the percentage set forth opposite {q('cu')} in Schedule 1.")
    D("Carried Interest", "means all amounts distributed to the General Partner pursuant to clauses (c) and (d) of "
      "[[waterfall]], other than amounts distributed to the Limited Partners under those clauses.")
    D("Carried Interest Percentage", f"means the percentage set forth opposite {q('carry')} in Schedule 1.")
    if fees:
        D("Commitment", f"means, for all Partners together, the amount set forth opposite {q('commit')} in Schedule 1"
          + (f", of which the General Partner's Commitment is the {q('gp_pct')} and the remainder is the Commitment "
             "of the Limited Partners" if gp else "") + ".")
        D("Commitment Period", f"means the period from the initial closing through the end of the Fiscal Year whose "
          f"number equals the {q('cp_years')} (the first Fiscal Year being number 1), subject to [[key_person]].")
        D("Invested Capital", f"means, for any Fiscal Year, the amount set forth for such Fiscal Year opposite "
          f"{q('inv_cap')} in Schedule 1 (the cost of Portfolio Investments held by the Partnership on the first day "
          "of such Fiscal Year, for all Partners together).")
    elif gp:
        pass
    D("Distributable Proceeds", f"means, for any Fiscal Year, the amount set forth for such Fiscal Year opposite "
      f"{q('proceeds')} in Schedule 1, being the net cash proceeds of Portfolio Investments available for "
      "distribution on the last day of such Fiscal Year.")
    D("Fiscal Year", "means each calendar year of the Partnership; each column of the Model after the first is one "
      "Fiscal Year, numbered from 1.")
    if gp:
        D("GP Commitment Percentage", f"means the percentage set forth opposite {q('gp_pct')} in Schedule 1.")
    if fees:
        D("Management Fee", "has the meaning assigned to such term in [[fee]].")
    if offset:
        D("Offset Percentage", f"means the percentage set forth opposite {q('offset_pct')} in Schedule 1.")
        D("Transaction Fees", f"means, for any Fiscal Year, the amount set forth for such Fiscal Year opposite "
          f"{q('tx_fees')} in Schedule 1, being transaction, monitoring and directors' fees received by the Manager "
          "or its Affiliates from portfolio companies during such Fiscal Year.")
    D("Preferred Return", f"means, as of any date, an amount equal to a return at the {q('pref')} per annum, "
      f"compounded annually, on the Capital Contributions of {lp_word} from the date contributed until the date "
      "returned pursuant to clause (a) of [[waterfall]], in each case computed on the sum of (i) such Capital "
      "Contributions not yet so returned and (ii) Preferred Return accrued in prior Fiscal Years and not yet "
      "distributed pursuant to clause (b) of [[waterfall]].")
    if clawback:
        D("Assumed Tax Rate", f"means the rate set forth opposite {q('tax')} in Schedule 1.")
        D("Clawback Amount", "has the meaning assigned to such term in [[clawback]].")
        D("Net Profits", "means, upon the dissolution of the Partnership, the aggregate Distributable Proceeds "
          f"apportioned to {lp_word} over the life of the Partnership minus the aggregate Capital Contributions of "
          f"{lp_word}, if positive (and zero otherwise).")
    if escrow:
        D("Escrow Account", "has the meaning assigned to such term in [[escrow]].")
    # ---- distractor definitions
    for term, text in [
        ("Affiliate", "means, with respect to any Person, any other Person controlling, controlled by or under "
         "common control with such Person."),
        ("Defaulting Partner", "has the meaning assigned to such term in [[default]]."),
        ("Key Person Event", "means that both of the Key Persons cease to devote substantially all of their "
         "business time to the Partnership."),
        ("Organizational Expenses", "means the legal, accounting and filing expenses incurred in connection with "
         "the organization of the Partnership, not to exceed $2,500,000 in the aggregate."),
        ("Portfolio Investment", "means any investment made by the Partnership in a portfolio company."),
        ("Successor Fund", "means any pooled investment vehicle with substantially the same investment objective as "
         "the Partnership, sponsored by the General Partner or its Affiliates."),
    ]:
        D(term, text)

    art3 = "CAPITAL CONTRIBUTIONS"
    contrib = ("Each Partner shall contribute capital on the first day of each Fiscal Year in which capital is "
               f"called. Capital called for Portfolio Investments (the amount set forth opposite {q('calls')} in "
               "Schedule 1, for all Partners together) is contributed by the Partners pro rata to their "
               "Commitments" if gp else
               "Each Limited Partner shall contribute capital on the first day of each Fiscal Year in which capital "
               f"is called. Capital called for Portfolio Investments (the amount set forth opposite {q('calls')} in "
               "Schedule 1) is contributed by the Limited Partners; the General Partner has no Commitment and makes "
               "no Capital Contributions")
    if fees:
        contrib += (". In addition, the Management Fee for each Fiscal Year is funded by Capital Contributions made "
                    "on the first day of such Fiscal Year" + (" by the Limited Partners only" if gp else ""))
    doc.section(art3, "contributions", "Capital Contributions", contrib + ".")
    doc.section(art3, "default", "Defaulting Partners",
                "If any Limited Partner fails to make a Capital Contribution when due and does not cure such failure "
                "within ten Business Days (a \"Defaulting Partner\"), the General Partner may cause such Defaulting "
                "Partner to forfeit 50% of its capital account and to lose its right to make further contributions.")
    if fees:
        art4 = "MANAGEMENT FEE"
        base = (f"(a) The Partnership shall pay to the Manager for each Fiscal Year a management fee (the "
                f"\"Management Fee\") equal to (i) during the Commitment Period, the {q('fee1')} multiplied by the "
                + ("Commitment of the Limited Partners" if gp else "Commitment")
                + f", and (ii) thereafter, the {q('fee2')} multiplied by "
                + ("the Limited Partners' share (in proportion to their Commitments) of " if gp else "")
                + "Invested Capital for such Fiscal Year"
                + (". (b) The General Partner's Commitment does not bear any Management Fee" if gp else "") + ".")
        doc.section(art4, "fee", "Management Fee", base)
        if offset:
            doc.section(art4, "offset", "Management Fee Offset",
                        "The Management Fee for any Fiscal Year shall be reduced (but not below zero) by the Offset "
                        "Percentage multiplied by the Transaction Fees received during such Fiscal Year. Any portion "
                        "of such reduction that cannot be applied because the Management Fee would be reduced below "
                        "zero shall be carried forward and applied to reduce the Management Fee for each following "
                        "Fiscal Year in turn until fully applied. For purposes of this Agreement the Management Fee "
                        "means the Management Fee after such reductions.")
        doc.section(art4, "org", "Organizational Expenses",
                    "The Partnership shall bear Organizational Expenses up to the limit set forth in the definition "
                    "thereof; any excess shall be borne by the Manager.")
    art5 = "DISTRIBUTIONS"
    if gp:
        doc.section(art5, "apportion", "Apportionment",
                    "Distributable Proceeds for each Fiscal Year shall first be apportioned among the Partners in "
                    "proportion to their Capital Contributions for Portfolio Investments, that is, the GP Commitment "
                    "Percentage to the General Partner and the remainder to the Limited Partners. Amounts apportioned "
                    "to the General Partner are distributed to it as a Partner in respect of its Commitment and are "
                    "not Carried Interest. Amounts apportioned to the Limited Partners are distributed in accordance "
                    "with [[waterfall]].")
    lp = "the Limited Partners"
    src = "Distributable Proceeds apportioned to the Limited Partners" if gp else "Distributable Proceeds"
    cu_clause = ("(c) Catch-Up: the Catch-Up Percentage to the General Partner and the remainder to "
                 f"{lp}, until the General Partner has received pursuant to this clause (c) an amount equal to the "
                 "Carried Interest Percentage of the sum of all amounts distributed pursuant to clause (b) and this "
                 "clause (c) (to all recipients) since the initial closing; and" if partial else
                 "(c) Catch-Up: 100% to the General Partner until the General Partner has received pursuant to this "
                 "clause (c) an amount equal to the Carried Interest Percentage of the sum of all amounts distributed "
                 "pursuant to clause (b) and this clause (c) since the initial closing; and")
    doc.section(art5, "waterfall", "Distribution Waterfall",
                f"{src} for each Fiscal Year shall be distributed on the last day of such Fiscal Year in the "
                f"following order of priority: (a) Return of Capital: 100% to {lp} until they have received "
                "cumulative distributions under this clause (a) equal to their aggregate Capital Contributions made "
                f"on or before such date; (b) Preferred Return: 100% to {lp} until they have received cumulative "
                "distributions under this clause (b) equal to the Preferred Return; " + cu_clause + " (d) "
                "thereafter, the Carried Interest Percentage to the General Partner and the remainder to "
                f"{lp}.")
    doc.section(art5, "tax_dist", "Tax Distributions",
                "The General Partner may cause the Partnership to make distributions to the General Partner to enable "
                "it to pay taxes on allocations of Partnership income, which distributions shall be treated as "
                "advances against subsequent distributions of Carried Interest.")
    doc.section(art5, "in_kind", "Distributions in Kind",
                "Distributions prior to the dissolution of the Partnership shall be made only in cash or marketable "
                "securities, valued at the average closing price over the five trading days preceding distribution.")
    if clawback:
        claw = ("Upon the dissolution of the Partnership (the end of the last Fiscal Year shown in the Model), if the "
                "aggregate Carried Interest distributed" + (
                    " (including amounts deposited in the Escrow Account)" if escrow else "") + " exceeds the "
                "Carried Interest Percentage multiplied by Net Profits, the General Partner shall restore the excess to the Limited Partners (the \"Clawback "
                "Amount\"); provided that the Clawback Amount shall not exceed the aggregate Carried Interest "
                "distributed reduced by the Assumed Tax Rate (that is, multiplied by one minus the Assumed Tax Rate).")
        if escrow:
            claw += " The Clawback Amount shall be satisfied first from the Escrow Account in accordance with [[escrow]]."
        doc.section(art5, "clawback", "General Partner Clawback", claw)
    if escrow:
        doc.section(art5, "escrow", "Carry Escrow",
                    "(a) The Escrow Percentage (as set forth opposite " + q("escrow_pct") + " in Schedule 1) of each "
                    "distribution of Carried Interest shall be deposited into a segregated account (the \"Escrow "
                    "Account\") instead of being paid to the General Partner; the remainder is paid to the General "
                    "Partner. The Escrow Account bears no interest and makes no payment before dissolution. (b) Upon "
                    "dissolution, the Escrow Account shall be applied first to pay the Clawback Amount (up to its "
                    "balance); the General Partner shall pay any remaining Clawback Amount; and any balance remaining "
                    "in the Escrow Account shall be released to the General Partner.")
    doc.section("GOVERNANCE", "key_person", "Key Person Event",
                "Upon the occurrence of a Key Person Event, the Commitment Period shall be suspended automatically "
                "unless Limited Partners holding a majority of Commitments elect to continue it.")
    doc.section("GOVERNANCE", "successor", "Successor Funds",
                "The General Partner shall not close a Successor Fund until the earlier of the end of the Commitment "
                "Period and the date on which 75% of Commitments have been invested or reserved.")
    doc.section("DISSOLUTION", "term", "Term",
                "The Partnership shall dissolve at the end of the last Fiscal Year shown in the Model, subject to two "
                "one-year extensions at the discretion of the General Partner.")
    ann = ("ANNEX A is the Model convention. (1) The first column of the Model is the initial closing (no balances); "
           "each later column is a Fiscal Year. (2) Capital Contributions are made on the first day of a Fiscal Year "
           "and distributions on its last day, so Capital Contributions made in a Fiscal Year are taken into account "
           "in that Fiscal Year's distributions and earn the Preferred Return for that whole Fiscal Year. (3) "
           "Amounts are for all Limited Partners together (and the General Partner where stated). (4) LP net cash "
           f"flow for a Fiscal Year = distributions to {lp} minus Capital Contributions of {lp}"
           + (" plus, in the last Fiscal Year, the Clawback Amount" if clawback else "")
           + "; the LP net IRR is the internal rate of return of the annual LP net cash flows (one per Fiscal Year, "
           "the initial closing column excluded). (5) No Key Person Event, default by any Partner, tax distribution, "
           "distribution in kind, Organizational Expense in excess of the limit, extension of the term or Successor "
           "Fund occurs in the Model; provisions concerning them have no effect on the Model.")
    doc.annex("Annex A - Model Conventions", ann)
    doc.annex("Schedule 1 - Assumptions", "Schedule 1 is the Assumptions sheet of the Model. Each caption in "
              "quotation marks refers to the value set forth opposite that caption (per-year values: in the column "
              "of the relevant Fiscal Year).")
    return doc.render()
