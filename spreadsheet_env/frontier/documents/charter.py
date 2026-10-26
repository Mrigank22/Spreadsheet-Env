"""Venture exit model specified by a CERTIFICATE OF INCORPORATION (document-grade spec).

Columns are Liquidation Amounts (an ascending grid of exit values). The agent
receives a generated charter (Article Fourth: dividends, liquidation preference,
conversion, anti-dilution, plus distractor clauses on voting, redemption and
mandatory conversion) and builds the distribution of each Liquidation Amount.

Levels (each adds to the previous one):
1. Seed and Series A, non-participating, Series A senior; each series receives
   the greater of its preference and its as-converted amount.
2. + Series B (senior); Seed and Series A rank pari passu and share a shortfall
   ratably in proportion to their full preferential amounts.
3. + cumulative Accruing Dividends (simple, from each Original Issue Date) added
   to the Liquidation Preference and forfeited on conversion; Series B at 1.5x.
4. + Series C down round (senior) with broad-based weighted-average anti-dilution:
   earlier series priced above the new price get a lower Conversion Price, so
   they convert into more than one common share each.
5. + Management Carve-Out paid first when the Liquidation Amount does not exceed
   the aggregate Liquidation Preference; options exercised only if in the money.
"""

from __future__ import annotations

import random
from typing import Dict, List

from ...model.spec import Calc, Line, ModelSpec, Scalar
from ..framework import Bundle, IdSpec, MonoSpec
from .legal import LegalDoc, company_name

DOMAIN = "charter"

LEVELS = {
    1: dict(series=["seed", "a"], groups=[["a"], ["seed"]], div=False, down=False, carve=False, k=8),
    2: dict(series=["seed", "a", "b"], groups=[["b"], ["seed", "a"]], div=False, down=False, carve=False, k=10),
    3: dict(series=["seed", "a", "b"], groups=[["b"], ["seed", "a"]], div=True, down=False, carve=False, k=10),
    4: dict(series=["seed", "a", "b", "c"], groups=[["c"], ["b"], ["seed", "a"]], div=True, down=True, carve=False,
            k=12),
    5: dict(series=["seed", "a", "b", "c"], groups=[["c"], ["b"], ["seed", "a"]], div=True, down=True, carve=True,
            k=12),
}
NAME = {"seed": "Series Seed", "a": "Series A", "b": "Series B", "c": "Series C"}


def generate(rng: random.Random, level: int) -> Bundle:
    cfg = LEVELS[level]
    u = rng.uniform
    sers: List[str] = cfg["series"]
    div, down, carve = cfg["div"], cfg["down"], cfg["carve"]
    common = round(u(6, 12), 2)
    opts = round(common * u(0.10, 0.20), 2) if (down or carve) else 0.0
    price = u(0.4, 1.0)
    oip: Dict[str, float] = {}
    shares: Dict[str, float] = {}
    for s in ["seed", "a", "b"]:
        if s in sers:
            price *= u(1.8, 3.2)
            oip[s] = round(price, 3)
            shares[s] = round(u(1.5, 4.5), 2)
    if "c" in sers:  # down round below Series B
        oip["c"] = round(oip["b"] * u(0.6, 0.85), 3)
        shares["c"] = round(u(3.0, 6.0), 2)
    mult = {s: 1.0 for s in sers}
    if div and "b" in sers:
        mult["b"] = 1.5
    rate = {s: rng.choice([0.06, 0.08]) for s in sers}
    years = {"seed": round(u(5, 7), 1), "a": round(u(3, 5), 1), "b": round(u(1.5, 3), 1), "c": round(u(0.5, 1.2), 1)}
    company = company_name(rng).split()[0] + " Technologies, Inc."

    # base-case preference per as-converted share fixes the conversion order (stated in the charter)
    lp_ps = {s: oip[s] * mult[s] + (oip[s] * rate[s] * years[s] if div else 0.0) for s in sers}
    ratio = {s: 1.0 for s in sers}
    if down:
        a_sh = common + opts + sum(shares[s] for s in sers if s != "c")
        for s in sers:
            if s != "c" and oip["c"] < oip[s]:
                cp = oip[s] * (a_sh + shares["c"] * oip["c"] / oip[s]) / (a_sh + shares["c"])
                ratio[s] = oip[s] / cp
    order = sorted(sers, key=lambda s: lp_ps[s] / ratio[s])
    total_lp = sum(shares[s] * lp_ps[s] for s in sers)
    k = cfg["k"]
    lo, hi = total_lp * u(0.35, 0.6), total_lp * u(3.0, 6.0)
    exits = [round(lo * (hi / lo) ** (j / (k - 1)), 1) for j in range(k)]

    A, M = "Assumptions", "Model"
    S = Scalar
    scalars: List[Scalar] = [S("common", "Common Stock outstanding (m shares)", common, "m", "count")]
    if opts:
        scalars.append(S("opts", "Options outstanding (m)", opts, "m", "count"))
    if carve:
        scalars += [S("strike", "Option exercise price ($)", round(oip["seed"] * u(1.0, 2.0), 3), "$", "money_fixed"),
                    S("carve", "Carve-Out Percentage", rng.choice([0.05, 0.075, 0.1]), "%", "rate")]
    for s in sers:
        scalars += [S(f"{s}_sh", f"{NAME[s]} shares outstanding (m)", shares[s], "m", "count"),
                    S(f"{s}_oip", f"{NAME[s]} Original Issue Price ($)", oip[s], "$", "money_fixed"),
                    S(f"{s}_mult", f"{NAME[s]} Liquidation Multiple", mult[s], "x", "fixed")]
        if div:
            scalars += [S(f"{s}_div", f"{NAME[s]} Dividend Rate", rate[s], "%", "fixed"),
                        S(f"{s}_yrs", f"{NAME[s]} years from Original Issue Date to the Liquidation Event",
                          years[s], "yrs", "fixed")]

    lines: List[Line] = [Line("exit", "Liquidation Amount", A, fc=None, hist="blank", forecast=exits, kind="money")]
    calcs: List[Calc] = []
    for i, s in enumerate(sers):
        lpps = f"{{${s}_oip}}*{{${s}_mult}}" + (f"+{{${s}_oip}}*{{${s}_div}}*{{${s}_yrs}}" if div else "")
        calcs += [
            Calc(f"{s}_lpps", f"{NAME[s]} Liquidation Preference per share", M, lpps, unit="$", kind="ratio",
                 section="Preferences and conversion" if i == 0 else ""),
            Calc(f"{s}_lp", f"{NAME[s]} aggregate Liquidation Preference", M, f"{{${s}_sh}}*{{{s}_lpps}}"),
        ]
    if down:
        a_terms = "{$common}+{$opts}+" + "+".join(f"{{${s}_sh}}" for s in sers if s != "c")
        calcs.append(Calc("ad_a", "Anti-dilution: A (shares deemed outstanding before the Series C issuance)", M,
                          a_terms, unit="m", kind="ratio"))
        for s in sers:
            if s == "c":
                continue
            cp = (f"IF({{$c_oip}}<{{${s}_oip}},{{${s}_oip}}*({{ad_a}}+{{$c_sh}}*{{$c_oip}}/{{${s}_oip}})"
                  f"/({{ad_a}}+{{$c_sh}}),{{${s}_oip}})")
            calcs += [Calc(f"{s}_cp", f"{NAME[s]} Conversion Price", M, cp, unit="$", kind="ratio"),
                      Calc(f"{s}_cr", f"{NAME[s]} Conversion Rate", M, f"{{${s}_oip}}/{{{s}_cp}}", unit="x",
                           kind="ratio")]
    cr = (lambda s: f"{{{s}_cr}}" if s != "c" else "1") if down else (lambda s: "1")
    if carve:
        calcs.append(Calc("tot_lp", "Aggregate Liquidation Preference of all Preferred Stock", M,
                          "+".join(f"{{{s}_lp}}" for s in sers)))
        lines += [
            Line("carve_amt", "Management Carve-Out", M, fc="IF({exit}<={tot_lp},{$carve}*{exit},0)", hist="blank",
                 section="Carve-out"),
            Line("net", "Liquidation Amount after the Carve-Out", M, fc="{exit}-{carve_amt}", hist="blank"),
        ]
        net = "{net}"
    else:
        net = "{exit}"
    # conversion decisions in the stated order
    for m, s in enumerate(order):
        conv = order[: m + 1]
        others = [x for x in sers if x not in conv]
        prefs = "".join(f"-{{{x}_lp}}" for x in others)
        denom = "{$common}" + "".join(f"+{{${x}_sh}}*{cr(x)}" if down else f"+{{${x}_sh}}" for x in conv)
        lines.append(Line(f"t{m}", f"Conversion test {m + 1}: price per common share if "
                          + ", ".join(NAME[x] for x in conv) + " convert", M, unit="$", kind="ratio", hist="blank",
                          fc=f"MAX(0,{net}{prefs})/({denom})", section="Conversion" if m == 0 else ""))
        prev = f"{{c_{order[m - 1]}}}=1," if m else ""
        test = f"{{t{m}}}*{cr(s)}" if down else f"{{t{m}}}"
        lines.append(Line(f"c_{s}", f"{NAME[s]} converts (1/0)", M, unit="1/0", kind="ratio", hist="blank",
                          fc=f"IF(AND({prev}{test}>={{{s}_lpps}}),1,0)"))
    # preferences by seniority group, ratable within a group
    paid: List[str] = []
    for gi, grp in enumerate(cfg["groups"]):
        avail = net + "".join(f"-{p}" for p in paid)
        if len(grp) == 1:
            s = grp[0]
            lines.append(Line(f"pp_{s}", f"{NAME[s]} preferential amount paid", M, hist="blank",
                              fc=f"(1-{{c_{s}}})*MIN({{{s}_lp}},MAX(0,{avail}))",
                              section="Liquidation preferences" if gi == 0 else ""))
            paid.append(f"{{pp_{s}}}")
        else:
            gid = "g" + "".join(grp)
            lines.append(Line(gid, "Full preferential amounts of " + " and ".join(NAME[x] for x in grp)
                              + " (not converting)", M, hist="blank",
                              fc="+".join(f"(1-{{c_{x}}})*{{{x}_lp}}" for x in grp),
                              section="Liquidation preferences" if gi == 0 else ""))
            for s in grp:
                lines.append(Line(f"pp_{s}", f"{NAME[s]} preferential amount paid", M, hist="blank",
                                  fc=f"IF({{{gid}}}=0,0,(1-{{c_{s}}})*{{{s}_lp}}*MIN(1,MAX(0,{avail})/{{{gid}}}))"))
            paid += [f"{{pp_{s}}}" for s in grp]
    lines.append(Line("resid", "Remaining assets for Common Stock (as converted)", M, hist="blank",
                      fc=net + "".join(f"-{p}" for p in paid), section="Remaining assets"))
    denom = "{$common}" + "".join(f"+{{c_{s}}}*{{${s}_sh}}*{cr(s)}" if down else f"+{{c_{s}}}*{{${s}_sh}}"
                                  for s in sers)
    lines.append(Line("denom", "Shares of Common Stock sharing (as converted)", M, unit="m", kind="ratio",
                      fc=denom, hist="blank"))
    if carve:
        lines += [
            Line("px_ex", "Price per share if Options are exercised", M, unit="$", kind="ratio", hist="blank",
                 fc="({resid}+{$opts}*{$strike})/({denom}+{$opts})"),
            Line("ex", "Options exercised (1/0)", M, unit="1/0", kind="ratio", hist="blank",
                 fc="IF({px_ex}>{$strike},1,0)"),
            Line("px", "Price per share of Common Stock", M, unit="$", kind="ratio", hist="blank",
                 fc="IF({ex}=1,{px_ex},{resid}/{denom})"),
            Line("opt_net", "Option holders (net of exercise price)", M, fc="{ex}*{$opts}*({px}-{$strike})",
                 hist="blank"),
        ]
    else:
        lines.append(Line("px", "Price per share of Common Stock", M, unit="$", kind="ratio", fc="{resid}/{denom}",
                          hist="blank"))
    lines.append(Line("to_common", "Holders of Common Stock", M, fc="{$common}*{px}", hist="blank",
                      section="Proceeds by holder"))
    for s in sers:
        conv_sh = f"{{${s}_sh}}*{cr(s)}" if down else f"{{${s}_sh}}"
        lines.append(Line(f"to_{s}", f"{NAME[s]} holders", M, fc=f"{{pp_{s}}}+{{c_{s}}}*{conv_sh}*{{px}}",
                          hist="blank"))
    total = ["{to_common}"] + [f"{{to_{s}}}" for s in sers] + (["{opt_net}", "{carve_amt}"] if carve else [])
    lines.append(Line("total_out", "Total distributed (all holders" + (", option holders net and the Carve-Out Plan"
                                                                     if carve else "") + ")", M,
                      fc="+".join(total), hist="blank"))
    for s in sers:
        calcs.append(Calc(f"moic_{s}", f"{NAME[s]} multiple of invested capital at the highest Liquidation Amount", M,
                          f"{{to_{s}@last}}/({{${s}_sh}}*{{${s}_oip}})", unit="x", kind="ratio",
                          section="Returns" if s == sers[0] else ""))
    spec = ModelSpec(title="Liquidation waterfall", periods=["Inputs"] + [f"Exit {j + 1}" for j in range(k)],
                     n_hist=1, sheets=[A, M], scalars=scalars, lines=lines, calcs=calcs)

    doc = _charter(cfg, company, order)
    conventions = ["The Certificate above governs. Implement every provision that affects the rows of the Model "
                   "exactly as drafted; provisions about events that do not occur in the Model (see Annex A) have no "
                   "effect.",
                   "Amounts in $ millions, shares in millions, prices in $ per share; flags are 1 or 0.",
                   "Each column is computed independently from its Liquidation Amount; Liquidation Amounts are always "
                   "given in ascending order."]
    # option exercise cash is netted out, so holders always receive exactly the Liquidation Amount
    ids = [IdSpec("everything_distributed", "holders receive the Liquidation Amount",
                  [(1, "total_out", 0), (-1, "exit", 0)])]
    mono = [MonoSpec("common_rises_with_exit", "to_common@last", "common", 0.5, 1)]
    outputs = [("to_common", "Holders of Common Stock")] + [(f"to_{s}", f"{NAME[s]} holders") for s in sers] + \
              [(f"c_{s}", f"{NAME[s]} converts (1/0)") for s in sers] + \
              [("px", "Price per share of Common Stock")] + \
              [(f"moic_{s}", f"{NAME[s]} multiple of invested capital at the highest Liquidation Amount") for s in sers]
    if carve:
        outputs.append(("carve_amt", "Management Carve-Out"))
    kinds = {"common": ("count", 1.0, None), "exit": ("money", 0.0, None), "opts": ("count", 0.0, None),
             "carve": ("rate", 0.0, 0.3)}
    for s in sers:
        kinds[f"{s}_sh"] = ("count", 0.1, None)
    return Bundle(domain=DOMAIN, noun=f"liquidation waterfall under a certificate of incorporation ({company})",
                  spec=spec, term_sheet=doc, conventions=conventions, identities=ids, monotone=mono, kinds=kinds,
                  outputs=outputs, scale=total_lp / 10, level=level, ascending=("exit",),
                  meta={"order": order, "document": "certificate of incorporation"})


def _charter(cfg: dict, company: str, order: List[str]) -> str:
    sers: List[str] = cfg["series"]
    div, down, carve = cfg["div"], cfg["down"], cfg["carve"]
    groups: List[List[str]] = cfg["groups"]
    doc = LegalDoc(f"Amended and Restated Certificate of Incorporation of {company}",
                   f"AMENDED AND RESTATED CERTIFICATE OF INCORPORATION of {company} (the \"Corporation\"). ARTICLE "
                   "FOURTH sets forth the rights, powers and preferences of the Common Stock and of the Preferred "
                   "Stock, consisting of the " + ", ".join(f"{NAME[s]} Preferred Stock" for s in sers) + ". Share "
                   "numbers, prices and rates referred to by a caption in quotation marks are set forth in Schedule 1 "
                   "(the Assumptions sheet of the Model).", defs_heading="DEFINITIONS")
    D = doc.define
    D("Common Stock", "means the common stock of the Corporation; the number of shares outstanding is set forth "
      "opposite \"Common Stock outstanding (m shares)\" in Schedule 1.")
    D("Conversion Rate", "means, for any series of Preferred Stock, its Original Issue Price divided by its "
      "Conversion Price" + (", as adjusted pursuant to [[antidilution]]" if down else "") + ".")
    D("Conversion Price", "means, for any series of Preferred Stock, its Original Issue Price" + (
        ", subject to adjustment pursuant to [[antidilution]]" if down else "") + ".")
    D("Liquidation Amount", "means the amount available for distribution to the stockholders of the Corporation upon "
      "a Liquidation Event, as set forth for each column of the Model opposite \"Liquidation Amount\" in Schedule 1.")
    D("Liquidation Event", "means any liquidation, dissolution or winding up of the Corporation or any Deemed "
      "Liquidation Event.")
    D("Liquidation Preference", "means, for each share of a series of Preferred Stock, its Original Issue Price "
      "multiplied by its Liquidation Multiple (as set forth opposite the caption \"<series> Liquidation Multiple\" in "
      "Schedule 1)" + (", plus all Accruing Dividends on such share" if div else "") + ".")
    D("Original Issue Price", "means, for each series of Preferred Stock, the price per share set forth opposite "
      "the caption \"<series> Original Issue Price ($)\" in Schedule 1.")
    D("Preferred Stock", "means the " + ", ".join(f"{NAME[s]} Preferred Stock" for s in sers) + ", and \"series\" "
      "refers to each of them; the number of shares of each series outstanding is set forth opposite \"<series> shares "
      "outstanding (m)\" in Schedule 1.")
    if div:
        D("Accruing Dividends", "means, for each share of a series of Preferred Stock, dividends accruing from its "
          "Original Issue Date at the rate per annum set forth opposite \"<series> Dividend Rate\" in Schedule 1 on "
          "its Original Issue Price, simple (not compounding), for the number of years set forth opposite \"<series> "
          "years from Original Issue Date to the Liquidation Event\" in Schedule 1.")
    if down:
        D("Options", "means rights to acquire Common Stock granted under the Equity Incentive Plan; the number "
          "outstanding is set forth opposite \"Options outstanding (m)\" in Schedule 1.")
    elif carve:
        pass
    if carve:
        D("Carve-Out Plan", "has the meaning assigned to such term in [[carveout]].")
    for term, text in [
        ("Deemed Liquidation Event", "means (a) a merger or consolidation in which the stockholders of the "
         "Corporation do not hold a majority of the voting power of the surviving entity, or (b) a sale of all or "
         "substantially all of the assets of the Corporation."),
        ("Exempted Securities", "means (a) Options granted under the Equity Incentive Plan, (b) shares issued upon "
         "conversion of Preferred Stock, and (c) shares issued in connection with a bona fide acquisition approved by "
         "the Board."),
        ("Qualified IPO", "means a firm-commitment underwritten public offering at a price per share of at least "
         "three times the Original Issue Price of the most senior series, with gross proceeds of at least "
         "$75,000,000."),
        ("Requisite Holders", "means the holders of a majority of the outstanding Preferred Stock, voting together "
         "on an as-converted basis."),
    ]:
        D(term, text)

    if div:
        doc.section("DIVIDENDS", "dividends", "Accruing Dividends",
                    "Accruing Dividends accrue on each share of Preferred Stock as set forth in the definition thereof, "
                    "whether or not declared. They are payable only (a) when, as and if declared by the Board, which "
                    "has not occurred, or (b) as part of the Liquidation Preference. A share that is converted into "
                    "Common Stock ceases to be entitled to any Accruing Dividends.")
    seniority = []
    for gi, grp in enumerate(groups):
        names = " and the ".join(f"{NAME[s]} Preferred Stock" for s in grp)
        seniority.append(names + (" (pari passu with each other)" if len(grp) > 1 else ""))
    liq = ("(a) Upon a Liquidation Event, the holders of each series of Preferred Stock shall be entitled to receive, "
           "out of the Liquidation Amount" + (" remaining after the Carve-Out Plan" if carve else "") + ", for each "
           "share, the greater of (i) its Liquidation Preference and (ii) the amount per share that would have been "
           "payable had all shares of such series been converted into Common Stock at the Conversion Rate "
           "immediately prior to the Liquidation Event (a series receiving the amount in clause (ii) being treated as "
           "converted and receiving no amount under clause (i)). (b) Payments under clause (a)(i) shall be made in the "
           "following order of priority: first to the " + "; then to the ".join(seniority) + ". If the amount "
           "available is insufficient to pay in full the Liquidation Preferences of a class ranking pari passu, it "
           "shall be distributed among the holders of that class ratably in proportion to the full preferential "
           "amounts to which they would otherwise be entitled. (c) After payment of the Liquidation Preferences, the "
           "remaining Liquidation Amount shall be distributed ratably among the holders of Common Stock and the "
           "holders of Preferred Stock treated as converted (on an as-converted basis, each converted share counting "
           "as its Conversion Rate shares of Common Stock).")
    doc.section("LIQUIDATION", "liquidation", "Liquidation Preference", liq)
    if carve:
        doc.section("LIQUIDATION", "carveout", "Management Carve-Out",
                    "If the Liquidation Amount does not exceed the aggregate Liquidation Preference of all outstanding "
                    "Preferred Stock (determined as if no series converts), an amount equal to the Liquidation Amount "
                    "multiplied by the percentage set forth opposite \"Carve-Out Percentage\" in Schedule 1 shall be "
                    "paid to the participants in the management carve-out plan (the \"Carve-Out Plan\") before any "
                    "other distribution; otherwise no amount is paid under the Carve-Out Plan.")
    doc.section("LIQUIDATION", "deemed", "Deemed Liquidation Events",
                "Each Deemed Liquidation Event shall be treated as a Liquidation Event unless the Requisite Holders "
                "elect otherwise by written notice given at least ten days before its effective date.")
    doc.section("CONVERSION", "optional_conv", "Optional Conversion",
                "Each share of Preferred Stock is convertible at any time, at the option of the holder, into a number "
                "of shares of Common Stock equal to its Conversion Rate.")
    if down:
        doc.section("CONVERSION", "antidilution", "Adjustment for Dilutive Issuances",
                    "If the Corporation issues Additional Shares of Common Stock (other than Exempted Securities) at a "
                    "price per share less than the Conversion Price of a series in effect immediately before such "
                    "issuance, the Conversion Price of that series shall be reduced to CP2 = CP1 x (A + B) / (A + C), "
                    "where CP1 is that Conversion Price immediately before the issuance; A is the number of shares of "
                    "Common Stock outstanding immediately before the issuance, treating all outstanding Options and all "
                    "outstanding Preferred Stock (other than the shares then issued) as exercised or converted into "
                    "one share of Common Stock each; B is the number of shares of Common Stock that the aggregate "
                    "consideration received for the issuance would purchase at CP1; and C is the number of shares "
                    "issued. The issuance of the Series C Preferred Stock, at its Original Issue Price, was an "
                    "issuance of Additional Shares of Common Stock for this purpose (and was the only one); the "
                    "Series C Preferred Stock is not itself adjusted.")
    doc.section("CONVERSION", "mandatory", "Mandatory Conversion",
                "Upon the closing of a Qualified IPO, or upon the written election of the Requisite Holders, all "
                "outstanding shares of Preferred Stock shall automatically convert into Common Stock at the then "
                "effective Conversion Rate.")
    doc.section("OTHER RIGHTS", "voting", "Voting",
                "Each holder of Preferred Stock votes together with the Common Stock on an as-converted basis; the "
                "holders of the most senior series, voting as a separate class, may elect one director.")
    doc.section("OTHER RIGHTS", "redemption", "Redemption",
                "The Preferred Stock is not redeemable at the option of the holder or of the Corporation.")
    ann = ("ANNEX A is the Model convention. (1) Each column of the Model is a separate Liquidation Event with the "
           "Liquidation Amount given for that column (amounts in $ millions; shares in millions). (2) For the purposes "
           "of [[liquidation|(a)]], the series are tested one at a time in the following order: "
           + ", ".join(NAME[s] for s in order) + ". A series is treated as converted if and only if every series "
           "earlier in that order is treated as converted and, assuming that series and every earlier series in the "
           "order convert and every later series does not, the amount per share of Common Stock under "
           f"[[liquidation|(c)]]" + (" (computed without exercise of Options)" if carve else "") + " multiplied by "
           "the series' Conversion Rate is at least its Liquidation Preference per share; for this test the amount "
           "per share of Common Stock is the greater of zero and (the Liquidation Amount"
           + (" after the Carve-Out Plan" if carve else "") + " minus the Liquidation Preferences of the series "
           "assumed not to convert), divided by the shares of Common Stock plus the as-converted shares of the series "
           "assumed to convert. ")
    if carve:
        ann += ("(3) Options participate only if exercised: they are exercised in a column if and only if (the "
                "remaining Liquidation Amount under [[liquidation|(c)]] plus Options outstanding multiplied by the "
                "\"Option exercise price ($)\") divided by (the as-converted shares sharing under "
                "[[liquidation|(c)]] plus the Options outstanding) exceeds the exercise price; if exercised, that "
                "amount is the price per share of Common Stock and the option holders receive, net of the exercise "
                "price, the Options outstanding multiplied by (that price minus the exercise price); otherwise the "
                "price per share is the remaining Liquidation Amount divided by the sharing shares and the option "
                "holders receive nothing. ")
    elif down:
        ann += "(3) Options are not exercised in the Model and receive nothing. "
    ann += ("(4) The multiple of invested capital of a series = the total amount received by its holders at the "
            "highest Liquidation Amount (the last column) divided by (its shares outstanding multiplied by its "
            "Original Issue Price). (5) No Qualified IPO, mandatory conversion, optional conversion other than as "
            "determined under (2), redemption or dividend declaration occurs in the Model; provisions concerning them "
            "have no effect on the Model.")
    doc.annex("Annex A - Model Conventions", ann)
    doc.annex("Schedule 1 - Assumptions", "Schedule 1 is the Assumptions sheet of the Model; \"<series>\" in a "
              "caption stands for the name of the relevant series (for example \"Series A shares outstanding (m)\").")
    return doc.render()
