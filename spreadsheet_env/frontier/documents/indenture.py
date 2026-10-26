"""Auto-loan ABS specified by an INDENTURE (document-grade spec).

The agent receives a generated indenture with the priority of payments drafted
the way public auto-ABS indentures draft it ("First Allocation of Principal",
"Regular Allocation of Principal", "Target Overcollateralization Amount",
"Specified Reserve Balance", alphabetical definitions, cross-references,
distractor clauses) and builds the monthly cash-flow model.

One waterfall from Available Funds (collections + reserve draw):
(i) servicing fee, (ii) Class A interest, (iii) First Allocation of Principal,
(iv) Class B interest, (v) Second Allocation, [(vi) Class C interest,
(vii) Third Allocation,] reserve deposit, Regular Allocation of Principal,
the rest to the Certificateholders. All principal allocations are paid to the
Notes sequentially (A, then B, then C).

Levels:
1. 24 months, Classes A and B, no defaults; Target OC = % of the initial pool.
2. 36 months, + defaults with lagged recoveries; Reserve Account (drawn for
   shortfalls of the senior items, replenished, released when not required).
3. 48 months, + Class C; Target OC = greater of % of the current pool and a
   floor % of the initial pool.
4. 60 months, + interest carryover shortfalls bearing interest; cumulative net
   loss ratio.
5. 60 months, + cumulative net loss trigger by month bucket that, once breached,
   steps the Target OC percentage up for good; CPR ramp; Class A WAL.
"""

from __future__ import annotations

import random
from typing import List

from ...model.spec import Calc, Line, ModelSpec, Scalar
from ..framework import Bundle, IdSpec, MonoSpec
from .legal import LegalDoc, company_name

DOMAIN = "indenture"

LEVELS = {
    1: dict(n=24, classes=["a", "b"], defaults=False, reserve=False, floor=False, carry=False, cnl=False),
    2: dict(n=36, classes=["a", "b"], defaults=True, reserve=True, floor=False, carry=False, cnl=False),
    3: dict(n=48, classes=["a", "b", "c"], defaults=True, reserve=True, floor=True, carry=False, cnl=False),
    4: dict(n=60, classes=["a", "b", "c"], defaults=True, reserve=True, floor=True, carry=True, cnl=False),
    5: dict(n=60, classes=["a", "b", "c"], defaults=True, reserve=True, floor=True, carry=True, cnl=True),
}
NAME = {"a": "Class A", "b": "Class B", "c": "Class C"}
ORD = {"a": "First", "b": "Second", "c": "Third"}

CAP = {
    "wac": "Weighted Average Coupon",
    "wam": "Remaining Term at Closing (months)",
    "cpr": "Prepayment Speed (CPR)",
    "cdr": "Default Rate (CDR)",
    "sev": "Loss Severity",
    "lag": "Recovery Lag (months)",
    "serv": "Servicing Fee Rate",
    "oc_pct": "Target OC Percentage",
    "oc_step": "Stepped-Up Target OC Percentage",
    "oc_floor": "OC Floor Percentage",
    "res_pct": "Specified Reserve Percentage",
    "t1": "CNL Trigger - Months 1 to 12",
    "t2": "CNL Trigger - Months 13 to 24",
    "t3": "CNL Trigger - Month 25 onwards",
}


def q(key: str) -> str:
    return f"\"{CAP[key]}\""


def generate(rng: random.Random, level: int) -> Bundle:
    cfg = LEVELS[level]
    u = rng.uniform
    n = cfg["n"]
    cls = cfg["classes"]
    dflt, res, floor, carry, cnl = cfg["defaults"], cfg["reserve"], cfg["floor"], cfg["carry"], cfg["cnl"]
    pool0 = round(10 ** u(2.6, 3.3), 1)
    wam = n + rng.randint(12, 36)
    oc0 = u(0.04, 0.10)
    split = {"a": 0.84, "b": 0.16} if len(cls) == 2 else {"a": 0.78, "b": 0.13, "c": 0.09}
    notes0 = {c: round(pool0 * (1 - oc0) * split[c], 1) for c in cls}
    coupon = {"a": round(u(0.040, 0.055), 4), "b": round(u(0.055, 0.075), 4), "c": round(u(0.075, 0.100), 4)}
    trust = company_name(rng).split()[0] + " Auto Receivables Trust"

    A, M = "Assumptions", "Model"
    S = Scalar
    scalars: List[Scalar] = [
        S("wac", CAP["wac"], round(u(0.08, 0.15), 4), "%", "interest"),
        S("wam", CAP["wam"], float(wam), "m", "fixed"),
        S("cpr", CAP["cpr"], round(u(0.08, 0.22), 4), "%", "rate"),
    ]
    if dflt:
        scalars += [S("cdr", CAP["cdr"], round(u(0.01, 0.05), 4), "%", "rate"),
                    S("sev", CAP["sev"], round(u(0.35, 0.6), 3), "%", "rate"),
                    S("lag", CAP["lag"], float(rng.choice([3, 4, 6])), "m", "fixed")]
    scalars.append(S("serv", CAP["serv"], 0.01, "%", "rate"))
    for c in cls:
        scalars += [S(f"{c}_bal0", f"{NAME[c]} Initial Note Balance", notes0[c], "$m", "money"),
                    S(f"{c}_cpn", f"{NAME[c]} Interest Rate", coupon[c], "%", "interest")]
    oc_pct = round(oc0 * u(1.15, 1.6), 4)
    asc = []
    if cnl:
        scalars += [S("oc_pct", CAP["oc_pct"], oc_pct, "%", "rate"),
                    S("oc_step", CAP["oc_step"], round(oc_pct + u(0.03, 0.06), 4), "%", "rate")]
        asc.append(("oc_pct", "oc_step"))
    else:
        scalars.append(S("oc_pct", CAP["oc_pct"], oc_pct, "%", "rate"))
    if floor:
        scalars.append(S("oc_floor", CAP["oc_floor"], round(oc_pct * u(0.3, 0.6), 4), "%", "rate"))
    if res:
        scalars.append(S("res_pct", CAP["res_pct"], round(u(0.005, 0.015), 4), "%", "rate"))
    if cnl:
        cdr_v = next(s.value for s in scalars if s.id == "cdr")
        sev_v = next(s.value for s in scalars if s.id == "sev")
        yearly = cdr_v * sev_v  # rough annual net loss as a share of the initial pool
        t1 = round(yearly * u(1.1, 1.8), 4)
        t2 = round(t1 + yearly * u(0.7, 1.2), 4)
        t3 = round(t2 + yearly * u(0.7, 1.2), 4)
        scalars += [S("t1", CAP["t1"], t1, "%", "rate"), S("t2", CAP["t2"], t2, "%", "rate"),
                    S("t3", CAP["t3"], t3, "%", "rate")]
        asc.append(("t1", "t2", "t3"))

    lines: List[Line] = [
        Line("month", "Collection Period number", M, unit="#", kind="ratio", fc="{month[-1]}+1", history=[0.0],
             section="Receivables"),
    ]
    if cnl:
        lines.append(Line("smm", "Prepayment rate (SMM)", M, unit="%", kind="ratio", hist="blank",
                          fc="1-(1-{$cpr}*MIN(1,{month}/30))^(1/12)"))
        smm = "{smm}"
    else:
        smm = "{smm_c}"
    if dflt:
        lines.append(Line("defaults", "Defaulted Receivables", M, fc="{perf[-1]}*{mdr}", hist="blank"))
        net_open = "({perf[-1]}-{defaults})"
    else:
        net_open = "{perf[-1]}"
    lines += [
        Line("int_coll", "Interest Collections", M, fc=f"{net_open}*{{$wac}}/12", hist="blank"),
        Line("sched_prin", "Scheduled Principal Collections", M, hist="blank",
             fc=f"PMT({{$wac}}/12,{{$wam}}-{{month}}+1,-{net_open})-{{int_coll}}"),
        Line("prepay", "Prepayments", M, fc=f"({net_open}-{{sched_prin}})*{smm}", hist="blank"),
        Line("perf", "Pool Balance", M, fc="{perf[-1]}" + ("-{defaults}" if dflt else "") + "-{sched_prin}-{prepay}",
             history=[pool0]),
    ]
    coll = "{int_coll}+{sched_prin}+{prepay}"
    if dflt:
        lines.append(Line("recov", "Recoveries", M, hist="blank",
                          fc="IF({month}>{$lag},INDEX({defaults@fc},{month}-{$lag})*(1-{$sev}),0)"))
        coll += "+{recov}"
    if carry:
        lines += [
            Line("cum_nl", "Cumulative Net Losses", M, fc="{cum_nl[-1]}+{defaults}-{recov}", history=[0.0]),
            Line("cnl_ratio", "Cumulative Net Loss Ratio", M, unit="%", kind="ratio", hist="blank",
                 fc="{cum_nl}/{perf@0}"),
        ]
    if cnl:
        lines += [
            Line("trig", "Applicable CNL Trigger", M, unit="%", kind="ratio", hist="blank",
                 fc="IF({month}<=12,{$t1},IF({month}<=24,{$t2},{$t3}))"),
            Line("breach", "CNL Trigger Event (1/0)", M, unit="flag", kind="ratio", history=[0.0],
                 fc="IF(OR({breach[-1]}=1,{cnl_ratio}>{trig}),1,0)"),
        ]
    lines.append(Line("coll", "Collections", M, fc=coll, hist="blank", section="Available Funds"))
    notes_open = "+".join(f"{{{c}[-1]}}" for c in cls)
    if floor:
        pct = "IF({breach}=1,{$oc_step},{$oc_pct})" if cnl else "{$oc_pct}"
        toc = f"MAX({pct}*{{perf}},{{$oc_floor}}*{{perf@0}})"
    else:
        toc = "{$oc_pct}*{perf@0}"
    lines.append(Line("toc", "Target Overcollateralization Amount", M, fc=toc, hist="blank"))
    lines.append(Line("fee", "Servicing Fee", M, fc="{perf[-1]}*{$serv}/12", hist="blank"))
    senior = ["{fee}"]
    prior_alloc = []
    for c in cls:
        due = f"{{{c}[-1]}}*{{${c}_cpn}}/12"
        if carry:
            due += f"+{{{c}_short[-1]}}*(1+{{${c}_cpn}}/12)"
        lines.append(Line(f"{c}_due", f"{NAME[c]} Interest Distributable Amount", M, fc=due, hist="blank"))
        bal = "+".join(f"{{{x}[-1]}}" for x in cls[: cls.index(c) + 1])
        alloc = f"MAX(0,{bal}-{{perf}})" + "".join(f"-{{{p}}}" for p in prior_alloc)
        lines.append(Line(f"alloc_{c}", f"{ORD[c]} Allocation of Principal", M, fc=alloc, hist="blank"))
        prior_alloc.append(f"alloc_{c}")
        senior += [f"{{{c}_due}}", f"{{alloc_{c}}}"]
    if res:
        lines.append(Line("draw", "Reserve Account Draw Amount", M, hist="blank",
                          fc=f"MIN({{res[-1]}},MAX(0,{'+'.join(senior)}-{{coll}}))"))
        lines.append(Line("avail", "Available Funds", M, fc="{coll}+{draw}", hist="blank"))
    else:
        lines.append(Line("avail", "Available Funds", M, fc="{coll}", hist="blank"))
    # sequential payments
    paid: List[str] = []

    def pay(ident: str, label: str, due: str, section: str = "") -> None:
        rem = "{avail}" + "".join(f"-{{{p}}}" for p in paid)
        lines.append(Line(ident, label, M, fc=f"MIN({rem},{due})", hist="blank", section=section))
        paid.append(ident)

    pay("fee_paid", "Servicing Fee paid", "{fee}", section="Priority of Payments")
    for c in cls:
        pay(f"{c}_ipaid", f"{NAME[c]} interest paid", f"{{{c}_due}}")
        pay(f"p_{c}", f"{ORD[c]} Allocation of Principal paid", f"{{alloc_{c}}}")
        if carry:
            lines.append(Line(f"{c}_short", f"{NAME[c]} Interest Carryover Shortfall", M,
                              fc=f"{{{c}_due}}-{{{c}_ipaid}}", history=[0.0]))
    if res:
        lines.append(Line("spec_res", "Specified Reserve Balance", M, hist="blank",
                          fc=f"IF({notes_open}>0,{{$res_pct}}*{{perf@0}},0)"))
        pay("res_fund", "Deposit to the Reserve Account", "MAX(0,{spec_res}-({res[-1]}-{draw}))")
    allocs = "".join(f"-{{alloc_{c}}}" for c in cls)
    pay("reg", "Regular Allocation of Principal paid",
        f"MAX(0,MIN({notes_open},{notes_open}-{{perf}}+{{toc}}){allocs})")
    rem = "{avail}" + "".join(f"-{{{p}}}" for p in paid)
    if res:
        lines += [
            Line("release", "Release from the Reserve Account", M, hist="blank",
                 fc="MAX(0,{res[-1]}-{draw}-{spec_res})"),
            Line("resid", "Distributions to the Certificateholders", M, fc=f"{rem}+{{release}}", hist="blank"),
            Line("res", "Reserve Account - closing", M, fc="{res[-1]}-{draw}+{res_fund}-{release}",
                 hist="formula", hist_fc="{$res_pct}*{perf@0}", section="Reserve Account"),
        ]
    else:
        lines.append(Line("resid", "Distributions to the Certificateholders", M, fc=rem, hist="blank"))
    prin = "+".join(f"{{p_{c}}}" for c in cls) + "+{reg}"
    lines.append(Line("prin", "Total principal paid to the Notes", M, fc=prin, hist="blank", section="Notes"))
    done: List[str] = []
    for c in cls:
        lines.append(Line(f"{c}_ppaid", f"{NAME[c]} principal paid", M, hist="blank",
                          fc=f"MIN({{{c}[-1]}},{{prin}}" + "".join(f"-{{{d}}}" for d in done) + ")"))
        done.append(f"{c}_ppaid")
        lines.append(Line(c, f"{NAME[c]} Note Balance", M, fc=f"{{{c}[-1]}}-{{{c}_ppaid}}", hist="formula",
                          hist_fc=f"{{${c}_bal0}}"))
    calcs: List[Calc] = [Calc("smm_c", "Prepayment rate (SMM)", M, "1-(1-{$cpr})^(1/12)", unit="%", kind="ratio",
                              section="Rates and results")] if not cnl else []
    if dflt:
        calcs.append(Calc("mdr", "Default rate (MDR)", M, "1-(1-{$cdr})^(1/12)", unit="%", kind="ratio",
                          section="" if calcs else "Rates and results"))
    calcs.append(Calc("resid_total", "Total distributions to the Certificateholders", M, "SUM({resid@fc})"))
    if cnl:
        calcs.append(Calc("wal_a", "Class A weighted average life (years)", M,
                          "SUMPRODUCT({month@fc},{a_ppaid@fc})/SUM({a_ppaid@fc})/12", unit="yrs", kind="ratio"))
    spec = ModelSpec(title="Auto ABS model", periods=["Closing"] + [f"P{i + 1}" for i in range(n)], n_hist=1,
                     sheets=[A, M], scalars=scalars, lines=lines, calcs=calcs)

    doc = _indenture(cfg, trust)
    conventions = ["The Indenture above governs. Implement every provision that affects the rows of the Model exactly "
                   "as drafted; provisions about events that do not occur in the Model (see Annex A) have no effect.",
                   "Amounts in $ millions; rates as decimals; one column per monthly Collection Period and its "
                   "Payment Date."]
    ids = [IdSpec("pool_rollforward", "Pool Balance roll-forward",
                  [(1, "perf", 0), (-1, "perf", -1), (1, "sched_prin", 0), (1, "prepay", 0)]
                  + ([(1, "defaults", 0)] if dflt else [])),
           IdSpec("principal_to_classes", "principal paid by class = principal allocations paid",
                  [(1, f"{c}_ppaid", 0) for c in cls] + [(-1, "prin", 0)])]
    wf = [(1, "fee_paid", 0)] + [(1, f"{c}_ipaid", 0) for c in cls] + [(1, f"p_{c}", 0) for c in cls] + \
         [(1, "reg", 0), (1, "resid", 0), (-1, "avail", 0)]
    if res:
        wf += [(1, "res_fund", 0), (-1, "release", 0)]
        ids.append(IdSpec("reserve_rollforward", "Reserve Account roll-forward",
                          [(1, "res", 0), (-1, "res", -1), (1, "draw", 0), (-1, "res_fund", 0), (1, "release", 0)]))
    ids.append(IdSpec("priority_of_payments_exhausts_funds", "Available Funds are fully applied", wf))
    for c in cls:
        ids.append(IdSpec(f"{c}_rollforward", f"{NAME[c]} roll-forward",
                          [(1, c, 0), (-1, c, -1), (1, f"{c}_ppaid", 0)]))
    mono = [MonoSpec("residual_rises_with_wac", "resid_total", "wac", 0.01, 1)]
    outputs = [("coll", "Collections"), ("perf", "Pool Balance"), ("toc", "Target Overcollateralization Amount"),
               ("avail", "Available Funds"), ("reg", "Regular Allocation of Principal paid"),
               ("resid", "Distributions to the Certificateholders")]
    outputs += [(c, f"{NAME[c]} Note Balance") for c in cls]
    if res:
        outputs += [("draw", "Reserve Account Draw Amount"), ("res", "Reserve Account - closing")]
    if carry:
        outputs.append(("cnl_ratio", "Cumulative Net Loss Ratio"))
    if cnl:
        outputs += [("breach", "CNL Trigger Event (1/0)"), ("wal_a", "Class A weighted average life (years)")]
    kinds = {"wac": ("interest", 0.01, 0.3), "cpr": ("rate", 0.0, 0.6), "cdr": ("rate", 0.0, 0.25),
             "sev": ("rate", 0.05, 0.95), "serv": ("rate", 0.0, 0.03), "oc_pct": ("rate", 0.0, 0.4),
             "oc_step": ("rate", 0.0, 0.5), "oc_floor": ("rate", 0.0, 0.2), "res_pct": ("rate", 0.0, 0.05),
             "t1": ("rate", 0.0, 0.3), "t2": ("rate", 0.0, 0.3), "t3": ("rate", 0.0, 0.3)}
    for c in cls:
        kinds[f"{c}_cpn"] = ("interest", 0.0, 0.25)
    return Bundle(domain=DOMAIN, noun=f"auto-loan ABS cash-flow model under an indenture ({trust})", spec=spec,
                  term_sheet=doc, conventions=conventions, identities=ids, monotone=mono, kinds=kinds,
                  outputs=outputs, scale=pool0 / 20, level=level, ascending_scalars=asc,
                  meta={"months": n, "classes": cls, "document": "indenture"})


def _indenture(cfg: dict, trust: str) -> str:
    cls = cfg["classes"]
    dflt, res, floor, carry, cnl = cfg["defaults"], cfg["reserve"], cfg["floor"], cfg["carry"], cfg["cnl"]
    doc = LegalDoc(f"Indenture - {trust}",
                   f"INDENTURE dated as of the Closing Date between {trust} (the \"Issuer\") and the Indenture "
                   "Trustee, relating to the Issuer's " + ", ".join(f"{NAME[c]} Asset Backed Notes" for c in cls)
                   + " (the \"Notes\"). Amounts and rates referred to by a caption in quotation marks are set forth in "
                   "Schedule 1 (the Assumptions sheet of the Model).")
    D = doc.define
    note_list = " and ".join(NAME[c] for c in cls) if len(cls) == 2 else "Class A, Class B and Class C"
    D("Available Funds", "means, for any Payment Date, the sum of Collections for the related Collection Period"
      + (" and the Reserve Account Draw Amount for such Payment Date" if res else "") + ".")
    D("Collection Period", "means each calendar month; each column of the Model after the first is one Collection "
      "Period and its related Payment Date, numbered from 1.")
    D("Collections", "means, for any Collection Period, interest collections, scheduled principal collections and "
      "prepayments on the Receivables" + (", and Recoveries" if dflt else "") + ", each as determined in "
      "accordance with Annex A.")
    if carry:
        D("Cumulative Net Loss Ratio", "means, for any Collection Period, (a) the aggregate principal balance of all "
          "Receivables that became Defaulted Receivables since the Closing Date minus all Recoveries received since "
          "the Closing Date, divided by (b) the Initial Pool Balance.")
    if cnl:
        D("CNL Trigger Event", "shall occur on the first Payment Date on which the Cumulative Net Loss Ratio for the "
          f"related Collection Period exceeds the {q('t1')} (for Collection Periods 1 to 12), the {q('t2')} (for "
          f"Collection Periods 13 to 24) or the {q('t3')} (for Collection Period 25 and later), and once it has "
          "occurred shall be continuing on every later Payment Date.")
    if dflt:
        D("Defaulted Receivable", "means any Receivable charged off by the Servicer in accordance with Annex A; the "
          "principal balance of a Defaulted Receivable is excluded from the Pool Balance from the Collection Period "
          "in which it defaults.")
    for c in cls:
        idx = cls.index(c)
        prev = cls[:idx + 1]
        earlier = [ORD[x] for x in cls[:idx]]
        D(f"{ORD[c]} Allocation of Principal", "means, for any Payment Date, an amount (not less than zero) equal to "
          "(a) the aggregate outstanding principal amount of the " + " and ".join(f"{NAME[x]} Notes" for x in prev)
          + " immediately preceding such Payment Date minus (b) the Pool Balance at the end of the related Collection "
          "Period" + (" minus (c) the " + " and the ".join(f"{e} Allocation of Principal" for e in earlier)
                      + " for such Payment Date" if earlier else "") + ".")
        D(f"{NAME[c]} Interest Distributable Amount", "means, for any Payment Date, interest accrued for the related "
          f"Collection Period at the \"{NAME[c]} Interest Rate\" (30/360, i.e. one-twelfth of the annual rate) on the "
          f"outstanding principal amount of the {NAME[c]} Notes immediately preceding such Payment Date" + (
              f", plus the {NAME[c]} Interest Carryover Shortfall for the preceding Payment Date and interest on such "
              f"Interest Carryover Shortfall at the \"{NAME[c]} Interest Rate\" for the related Collection Period"
              if carry else "") + ".")
        if carry:
            D(f"{NAME[c]} Interest Carryover Shortfall", f"means, for any Payment Date, the excess of the {NAME[c]} "
              f"Interest Distributable Amount over the amount of interest paid to the {NAME[c]} Noteholders on "
              "such Payment Date.")
    D("Initial Pool Balance", "means the Pool Balance as of the Closing Date (the first column of the Model).")
    D("Note Balance", "means, as of any date, the aggregate outstanding principal amount of the " + note_list
      + " Notes.")
    D("Pool Balance", "means, as of the end of any Collection Period, the aggregate principal balance of the "
      "Receivables (other than Defaulted Receivables) as of such date.")
    if dflt:
        D("Recoveries", "means amounts received in respect of Defaulted Receivables, determined in accordance with "
          "Annex A.")
    D("Regular Allocation of Principal", "means, for any Payment Date, an amount (not less than zero) equal to the "
      "lesser of (a) the Note Balance immediately preceding such Payment Date and (b) such Note Balance minus the "
      "excess of the Pool Balance at the end of the related Collection Period over the Target Overcollateralization "
      "Amount, minus the sum of the " + ", ".join(f"{ORD[c]} Allocation of Principal" for c in cls)
      + " for such Payment Date.")
    if res:
        D("Reserve Account Draw Amount", "means, for any Payment Date, the lesser of (a) the amount on deposit in the "
          "Reserve Account immediately preceding such Payment Date and (b) the amount, if any, by which the sum of "
          "the amounts payable under clauses " + ", ".join(_roman_list(len(cls) * 2 + 1)) + " of [[priority]] "
          "(the full amounts required, before any shortfall) exceeds Collections for the related Collection Period.")
        D("Specified Reserve Balance", f"means, for any Payment Date, the {q('res_pct')} multiplied by the Initial "
          "Pool Balance; provided that the Specified Reserve Balance shall be zero on any Payment Date on which the "
          "Note Balance immediately preceding such Payment Date is zero.")
    D("Servicing Fee", f"means, for any Collection Period, one-twelfth of the {q('serv')} multiplied by the Pool "
      "Balance at the beginning of such Collection Period.")
    if floor:
        pct = (f"the {q('oc_step')} if a CNL Trigger Event has occurred and is continuing on such Payment Date, and "
               f"otherwise the {q('oc_pct')}," if cnl else f"the {q('oc_pct')}")
        D("Target Overcollateralization Amount", f"means, for any Payment Date, the greater of (a) {pct} multiplied "
          "by the Pool Balance at the end of the related Collection Period and (b) the "
          f"{q('oc_floor')} multiplied by the Initial Pool Balance.")
    else:
        D("Target Overcollateralization Amount", f"means the {q('oc_pct')} multiplied by the Initial Pool Balance.")
    for term, text in [
        ("Clean-Up Call", "has the meaning assigned to such term in [[optional]]."),
        ("Event of Default", "has the meaning assigned to such term in [[eod]]."),
        ("Rating Agency Condition", "means, with respect to any action, that each Rating Agency shall have been given "
         "ten days' prior notice thereof and shall not have notified the Issuer that such action will result in a "
         "reduction or withdrawal of its then-current rating of any Class of Notes."),
        ("Receivables", "means the motor vehicle retail installment sale contracts transferred to the Issuer on the "
         "Closing Date."),
        ("Servicer Termination Event", "means the failure of the Servicer to deliver any required payment within "
         "five Business Days, or the insolvency of the Servicer."),
    ]:
        D(term, text)

    doc.section("THE NOTES", "issuance", "Issuance of the Notes",
                "On the Closing Date the Issuer issued the " + ", ".join(
                    f"{NAME[c]} Notes in an initial principal amount equal to the amount set forth opposite "
                    f"\"{NAME[c]} Initial Note Balance\" in Schedule 1" for c in cls) + ". Interest on each Class "
                "accrues at the rate set forth opposite its \"Interest Rate\" caption in Schedule 1.")
    art = "PAYMENTS"
    items = ["(i) to the Servicer, the Servicing Fee"]
    n = 1
    for c in cls:
        items.append(f"({_roman(n + 1)}) to the {NAME[c]} Noteholders, the {NAME[c]} Interest Distributable Amount")
        items.append(f"({_roman(n + 2)}) to the Principal Distribution Account, the {ORD[c]} Allocation of "
                     "Principal")
        n += 2
    if res:
        n += 1
        items.append(f"({_roman(n)}) to the Reserve Account, the amount, if any, necessary to cause the amount on "
                     "deposit in the Reserve Account (after any Reserve Account Draw Amount) to equal the Specified "
                     "Reserve Balance")
    n += 1
    items.append(f"({_roman(n)}) to the Principal Distribution Account, the Regular Allocation of Principal")
    n += 1
    items.append(f"({_roman(n)}) to the Certificateholders, all remaining Available Funds")
    doc.section(art, "priority", "Priority of Payments",
                "On each Payment Date the Indenture Trustee shall apply Available Funds in the following order of "
                "priority, in each case to the extent of Available Funds remaining after all prior clauses: "
                + "; ".join(items) + ".")
    doc.section(art, "principal", "Principal Distribution Account",
                "On each Payment Date all amounts deposited in the Principal Distribution Account shall be paid "
                "sequentially: first to the Class A Noteholders until the Class A Notes are paid in full, then to the "
                "Class B Noteholders until the Class B Notes are paid in full" + (
                    ", then to the Class C Noteholders until the Class C Notes are paid in full" if len(cls) == 3
                    else "") + ".")
    if res:
        doc.section(art, "reserve", "Reserve Account",
                    "On the Closing Date the Issuer deposited into the Reserve Account an amount equal to the "
                    "Specified Reserve Balance. On each Payment Date (a) the Reserve Account Draw Amount shall be "
                    "withdrawn and included in Available Funds, and (b) after the application of Available Funds "
                    "under [[priority]], any amount on deposit in the Reserve Account (after the withdrawal under "
                    "clause (a)) in excess of the Specified Reserve Balance shall be released to the "
                    "Certificateholders. The Reserve Account earns no interest.")
    doc.section(art, "optional", "Optional Redemption",
                "The Servicer may purchase all Receivables on any Payment Date on which the Pool Balance is 10% or "
                "less of the Initial Pool Balance (the \"Clean-Up Call\"), in which case the Notes shall be redeemed "
                "in full at par plus accrued interest.")
    doc.section("DEFAULTS AND REMEDIES", "eod", "Events of Default",
                "Each of the following is an Event of Default: (a) a default in the payment of interest on the "
                "Controlling Class for five days; (b) a default in the payment of principal of any Note at its final "
                "scheduled payment date; (c) insolvency of the Issuer. Upon an Event of Default the Notes may be "
                "accelerated and principal shall be paid in accordance with the post-acceleration priority of "
                "payments.")
    doc.section("DEFAULTS AND REMEDIES", "servicer", "Servicer Termination",
                "Upon a Servicer Termination Event, Noteholders holding a majority of the Controlling Class may "
                "terminate the Servicer and appoint a successor, whose servicing fee may not exceed 1.50% per annum.")
    coll = ("ANNEX A is the Model convention (the Servicer's collateral model). (1) The first column shows balances "
            "at the Closing Date; each later column is a Collection Period numbered from 1, with its Payment Date. ")
    if dflt:
        coll += ("(2) Defaulted Receivables in a Collection Period = the Pool Balance at its beginning multiplied by "
                 f"the monthly default rate 1 - (1 - {q('cdr')})^(1/12). ")
    nd = "(the Pool Balance at the beginning of the Collection Period minus Defaulted Receivables)" if dflt else \
        "(the Pool Balance at the beginning of the Collection Period)"
    coll += (f"(3) Interest collections = {nd} multiplied by the {q('wac')} / 12. (4) Scheduled principal "
             f"collections = the level monthly payment that amortizes {nd} over the remaining term (the "
             f"{q('wam')} minus the Collection Period number plus 1) at the {q('wac')} / 12, minus interest "
             f"collections. (5) Prepayments = ({nd} minus scheduled principal collections) multiplied by the monthly "
             f"rate 1 - (1 - CPR)^(1/12), where CPR is the {q('cpr')}" + (
                 " multiplied by the lesser of 1 and the Collection Period number divided by 30" if cnl else "")
             + ". (6) Pool Balance at the end = at the beginning" + (" minus Defaulted Receivables" if dflt else "")
             + " minus scheduled principal collections minus prepayments. ")
    if dflt:
        coll += (f"(7) Recoveries in the Collection Period numbered m = the Defaulted Receivables of the Collection "
                 f"Period numbered (m minus the {q('lag')}) multiplied by (1 minus the {q('sev')}); Recoveries are "
                 f"zero while m does not exceed the {q('lag')}. ")
    coll += ("(8) No Clean-Up Call, Event of Default, acceleration, Servicer Termination Event or Rating Agency action "
             "occurs in the Model; provisions concerning them have no effect on the Model. (9) Notes are paid on "
             "every Payment Date shown; amounts are not rounded. (10) Distributions to the Certificateholders on a "
             "Payment Date comprise the amount paid under the last clause of [[priority]]" + (
                 " plus any amount released from the Reserve Account under [[reserve]]" if res else "") + "." + (
                 " (11) The Class A weighted average life (years) = the sum over all Payment Dates of (Collection "
                 "Period number multiplied by principal paid to the Class A Noteholders) divided by the total "
                 "principal paid to the Class A Noteholders, divided by 12." if cnl else ""))
    doc.annex("Annex A - Model Conventions", coll)
    doc.annex("Schedule 1 - Assumptions", "Schedule 1 is the Assumptions sheet of the Model. Each caption in "
              "quotation marks refers to the value set forth opposite that caption.")
    return doc.render()


def _roman(n: int) -> str:
    vals = [(10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def _roman_list(k: int) -> List[str]:
    return [f"({_roman(i)})" for i in range(1, k + 1)]
