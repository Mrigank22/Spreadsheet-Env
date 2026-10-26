"""Venture exit waterfall: liquidation preferences, conversion decisions, options.

Columns are exit scenarios (exit equity values), not years. A cap table of
common stock and preferred series; each preferred series has a liquidation
preference (shares x original issue price x multiple) paid by seniority.

Non-participating preferred chooses between its preference and converting to
common (1:1). Decisions interact, so the terms fix the standard construction:
series are evaluated in ascending order of preference per share; series j
converts if (and only if) the earlier series in that order convert and the
common price per share computed assuming series 1..j convert (later ones take
their preference) is at least j's preference per share.

1. one non-participating series and common.
2. two series, stacked seniority.
3. three series.
4. + a senior participating series (preference plus pro-rata residual; never
   converts).
5. + an option pool exercised only if in the money (exercise cash adds to the
   proceeds; tested after the conversion decisions).
"""

from __future__ import annotations

import random
from typing import List

from ..model.spec import Calc, Line, ModelSpec, Scalar
from .framework import Bundle, IdSpec, MonoSpec

DOMAIN = "vc"

LEVELS = {
    1: dict(series=1, participating=False, options=False, k=8),
    2: dict(series=2, participating=False, options=False, k=10),
    3: dict(series=3, participating=False, options=False, k=12),
    4: dict(series=3, participating=True, options=False, k=12),
    5: dict(series=3, participating=True, options=True, k=12),
}
NAMES = ["Seed", "Series A", "Series B", "Series C"]


def generate(rng: random.Random, level: int) -> Bundle:
    cfg = LEVELS[level]
    u = rng.uniform
    ns = cfg["series"]
    names = NAMES[:ns] if not cfg["participating"] else NAMES[:ns] + ["Series C"]
    ids = [f"p{i}" for i in range(len(names))]
    part_id = ids[-1] if cfg["participating"] else None
    common = round(u(5, 12), 2)  # m shares
    shares = {}
    oip = {}
    mult = {}
    price = u(0.3, 1.0)
    for i, sid in enumerate(ids):
        price *= u(1.8, 3.5)  # each round prices higher
        oip[sid] = round(price, 3)
        shares[sid] = round(u(1.5, 5.0), 2)
        mult[sid] = rng.choice([1.0, 1.0, 1.0, 1.5, 2.0]) if i >= 1 else 1.0
    post_money = sum(shares.values()) * price + common * price
    k = cfg["k"]
    lo, hi = post_money * u(0.05, 0.15), post_money * u(1.5, 3.0)
    exits = [round(lo * (hi / lo) ** (j / (k - 1)), 1) for j in range(k)]
    A, M = "Assumptions", "Model"
    scalars = [Scalar("common", "Common shares (m)", common, "m", "count")]
    for sid, nm in zip(ids, names):
        scalars += [Scalar(f"{sid}_sh", f"{nm} shares (m)", shares[sid], "m", "count"),
                    Scalar(f"{sid}_oip", f"{nm} original issue price ($)", oip[sid], "$", "money_fixed"),
                    Scalar(f"{sid}_mult", f"{nm} liquidation preference multiple", mult[sid], "x", "fixed")]
    if cfg["options"]:
        scalars += [Scalar("opts", "Options outstanding (m)", round(common * u(0.1, 0.25), 2), "m", "count"),
                    Scalar("strike", "Option strike price ($)", round(oip[ids[0]] * u(0.5, 1.5), 3), "$", "money_fixed")]
    nonpart = [s for s in ids if s != part_id]
    order = sorted(nonpart, key=lambda s: oip[s] * mult[s])  # ascending preference per share
    senior = list(reversed(ids))  # later rounds are senior; the participating series is the most senior
    nm = dict(zip(ids, names))
    lines: List[Line] = [Line("exit", "Exit equity value", A, fc=None, hist="blank", forecast=exits, kind="money")]
    calcs: List[Calc] = []
    for sid in ids:
        calcs.append(Calc(f"{sid}_lp", f"{nm[sid]} liquidation preference", M,
                          f"{{${sid}_sh}}*{{${sid}_oip}}*{{${sid}_mult}}", section="Preferences" if sid == ids[0] else "",
                          desc="shares x original issue price x multiple"))
        calcs.append(Calc(f"{sid}_lpps", f"{nm[sid]} preference per share", M, f"{{${sid}_oip}}*{{${sid}_mult}}",
                          unit="$", kind="ratio", desc="original issue price x multiple"))
    # conversion tests in the fixed order
    part_sh = f"+{{${part_id}_sh}}" if part_id else ""
    for m, sid in enumerate(order):
        converted = order[: m + 1]
        others = [s for s in ids if s not in converted]
        prefs = "".join(f"-{{{s}_lp}}" for s in others)
        denom = "{$common}" + "".join(f"+{{${s}_sh}}" for s in converted) + part_sh
        lines.append(Line(f"t{m}", f"Test {m + 1}: common price if {', '.join(nm[s] for s in converted)} convert", M,
                          unit="$", kind="ratio", fc=f"MAX(0,{{exit}}{prefs})/({denom})", hist="blank",
                          section="Conversion decisions" if m == 0 else "",
                          desc="MAX(0, exit value - preferences of the series that do not convert) / (common shares "
                               "+ shares of the converting series" + (" + participating shares)" if part_id else ")")))
        prev = f"{{c_{order[m - 1]}}}=1," if m else ""
        lines.append(Line(f"c_{sid}", f"{nm[sid]} converts (1/0)", M, unit="1/0", kind="ratio",
                          fc=f"IF(AND({prev}{{t{m}}}>={{{sid}_lpps}}),1,0)", hist="blank",
                          desc=("1 if the previous series in the order converts and " if m else "1 if ")
                               + f"test {m + 1} price >= {nm[sid]} preference per share, else 0"))
    # preferences paid by seniority (converting series take nothing here)
    paid = []
    for sid in senior:
        flag = f"(1-{{c_{sid}}})*" if sid != part_id else ""
        avail = "{exit}" + "".join(f"-{x}" for x in paid)
        lines.append(Line(f"pp_{sid}", f"{nm[sid]} preference paid", M,
                          fc=f"{flag}MIN({{{sid}_lp}},MAX(0,{avail}))", hist="blank",
                          section="Distribution" if sid == senior[0] else "",
                          desc=("zero if converting, else " if sid != part_id else "")
                               + "the smaller of its preference and proceeds left after more senior preferences"))
        paid.append(f"{{pp_{sid}}}")
    resid = "{exit}" + "".join(f"-{x}" for x in paid)
    denom_final = "{$common}" + "".join(f"+{{c_{s}}}*{{${s}_sh}}" for s in nonpart) + part_sh
    lines.append(Line("resid", "Residual for common (as converted)", M, fc=resid, hist="blank",
                      desc="exit value - all preferences paid"))
    lines.append(Line("denom", "Shares sharing the residual", M, unit="m", kind="ratio", fc=denom_final, hist="blank",
                      desc="common + converting preferred" + (" + participating preferred" if part_id else "")))
    if cfg["options"]:
        lines += [
            Line("px_ex", "Price per share if options are exercised", M, unit="$", kind="ratio",
                 fc="({resid}+{$opts}*{$strike})/({denom}+{$opts})", hist="blank",
                 desc="(residual + options x strike) / (sharing shares + options)"),
            Line("ex", "Options exercised (1/0)", M, unit="1/0", kind="ratio", fc="IF({px_ex}>{$strike},1,0)",
                 hist="blank", desc="1 if that price exceeds the strike"),
            Line("px", "Price per share", M, unit="$", kind="ratio",
                 fc="IF({ex}=1,{px_ex},{resid}/{denom})", hist="blank",
                 desc="price with exercise if exercised, else residual / sharing shares"),
            Line("opt_net", "Option holders (net of strike)", M, fc="{ex}*{$opts}*({px}-{$strike})", hist="blank",
                 desc="exercise flag x options x (price - strike)"),
        ]
    else:
        lines.append(Line("px", "Price per share", M, unit="$", kind="ratio", fc="{resid}/{denom}", hist="blank",
                          desc="residual / sharing shares"))
    lines.append(Line("to_common", "Common stockholders", M, fc="{$common}*{px}", hist="blank",
                      desc="common shares x price", section="Proceeds by holder"))
    total_terms = ["{to_common}"] + (["{opt_net}"] if cfg["options"] else [])
    for sid in ids:
        if sid == part_id:
            fc = f"{{pp_{sid}}}+{{${sid}_sh}}*{{px}}"
            d = "preference paid + shares x price (participating)"
        else:
            fc = f"{{pp_{sid}}}+{{c_{sid}}}*{{${sid}_sh}}*{{px}}"
            d = "preference paid + (if converting) shares x price"
        lines.append(Line(f"to_{sid}", f"{nm[sid]} holders", M, fc=fc, hist="blank", desc=d))
        total_terms.append(f"{{to_{sid}}}")
    lines.append(Line("total_out", "Total distributed", M, fc="+".join(total_terms), hist="blank",
                      desc="sum of all holders"))
    for sid in ids:
        calcs.append(Calc(f"moic_{sid}_top", f"{nm[sid]} MOIC at the highest exit", M,
                          f"{{to_{sid}@last}}/({{${sid}_sh}}*{{${sid}_oip}})", unit="x", kind="ratio",
                          desc="proceeds at the last exit value / (shares x original issue price)"))
    spec = ModelSpec(title="Venture exit waterfall", periods=["Inputs"] + [f"Exit {j + 1}" for j in range(k)],
                     n_hist=1, sheets=[A, M], scalars=scalars, lines=lines, calcs=calcs)
    ts = [
        "Each column is an exit scenario with the given exit equity value. Holders: common stock"
        + "".join(f", {nm[s]}" for s in ids) + ".",
        "PREFERENCE of a preferred series = shares x original issue price x preference multiple; preference per "
        "share = original issue price x multiple.",
        "SENIORITY: preferences are paid in the order " + " > ".join(nm[s] for s in senior)
        + " (most senior first); each receives the smaller of its preference and the proceeds left after more "
        "senior preferences. A series that converts receives no preference.",
        "CONVERSION (non-participating series: " + ", ".join(nm[s] for s in nonpart) + "): each takes its "
        "preference or converts 1:1 into common. Evaluate them in this order: " + ", ".join(nm[s] for s in order)
        + " (ascending preference per share). Test j computes the common price per share assuming series 1..j of "
        "that order convert and the rest take their preference: MAX(0, exit value - preferences of the "
        "non-converting series) / (common shares + shares of the converting series" + (
            " + the participating series' shares" if part_id else "") + "). Series j converts if series j-1 converts "
        "(not required for the first) and test j's price is at least its preference per share.",
    ]
    if part_id:
        ts.append(f"PARTICIPATION: {nm[part_id]} is participating and never converts: it receives its preference and "
                  "also shares in the residual pro rata with common.")
    ts.append("RESIDUAL = exit value - preferences paid, shared per share by common, converting series"
              + (" and the participating series" if part_id else "") + ".")
    if cfg["options"]:
        ts.append("OPTIONS (tested after the conversion decisions): if the price per share with exercise = "
                  "(residual + options x strike) / (sharing shares + options) exceeds the strike, all options are "
                  "exercised and that is the price; otherwise the price is residual / sharing shares and options get "
                  "nothing. Option holders receive options x (price - strike) when exercised.")
    ts.append("MOIC of a series at the highest exit (the last column: exit values are in ascending order) = its "
              "proceeds there / (shares x original issue price).")
    conventions = ["Amounts in $m, shares in millions, prices in $ per share.",
                   "Exit values are always given in ascending order.",
                   "Flags are 1 or 0. Each column is computed independently from its exit value."]
    idsp = [IdSpec("everything_distributed", "holders receive the exit value" + (" plus option exercise cash"
                                                                              if cfg["options"] else ""),
                   [(1, "total_out", 0), (-1, "exit", 0)] + ([] if not cfg["options"] else []))]
    if cfg["options"]:
        idsp = []  # option exercise cash makes the identity scenario-dependent; checked via golden values
    mono = [MonoSpec("common_rises_with_common_shares", "to_common@last", "common", 0.5, 1)]
    outputs = [("to_common", "Common stockholders")] + [(f"to_{s}", f"{nm[s]} holders") for s in ids] + \
              [(f"c_{s}", f"{nm[s]} converts (1/0)") for s in nonpart] + [("px", "Price per share")]
    outputs += [(f"moic_{s}_top", f"{nm[s]} MOIC at the highest exit") for s in ids]
    kinds = {"common": ("count", 1.0, None), "exit": ("money", 0.0, None), "opts": ("count", 0.0, None)}
    for s in ids:
        kinds[f"{s}_sh"] = ("count", 0.1, None)
    return Bundle(domain="vc", noun="venture capital exit (liquidation preference) waterfall", spec=spec,
                  term_sheet="\n".join(ts), conventions=conventions, identities=idsp, monotone=mono, kinds=kinds,
                  outputs=outputs, scale=post_money / 20, level=level, meta={"order": order, "seniority": senior},
                  ascending=("exit",))
