"""Procedural generator for linked three-statement models.

``generate_model(rng, cfg)`` returns a ``ModelSpec`` (with realistic,
internally consistent actuals) plus the accounting identities that any
correct model must satisfy. Every feature is a switch in ``ModelConfig`` so
difficulty can be raised gradually:

* ``interest_income``  interest earned on opening cash
* ``tax_floor``        no tax credit on losses (``MAX(0, EBT)``)
* ``revolver``         a revolving credit facility drawn to keep minimum cash
* ``dividends``        payout of positive net income
* ``average_balances`` interest on *average* balances, which makes the model
                       circular (needs iterative calculation)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .calibration import PROFILES, SectorProfile
from .spec import Line, ModelSpec, Scalar


@dataclass
class ModelConfig:
    n_hist: int = 2
    n_forecast: int = 5
    interest_income: bool = False
    tax_floor: bool = True
    revolver: bool = False
    dividends: bool = True
    inventory: bool = True
    average_balances: bool = False
    single_sheet: bool = False  # put IS/BS/CFS on one "Model" sheet
    sector: str = ""  # empty: random


@dataclass
class Identity:
    """A reference-free accounting identity: ``lhs - rhs == 0`` every forecast period.

    Terms are (sign, line id, period offset).
    """

    name: str
    desc: str
    terms: List[Tuple[int, str, int]]


@dataclass
class GeneratedModel:
    spec: ModelSpec
    identities: List[Identity]
    sector: SectorProfile
    cfg: ModelConfig
    money_scalars: List[str] = field(default_factory=list)
    # (lines, lines they must never depend on, why) - balancing plugs etc.
    forbidden: List[Tuple[List[str], List[str], str]] = field(default_factory=list)


LABELS = {"cash": "cash", "ar": "accounts receivable", "inv": "inventory", "ap": "accounts payable",
          "debt": "term debt", "revolver": "revolver"}


def _r(x: float, nd: int = 1) -> float:
    return round(x, nd)


def generate_model(rng: random.Random, cfg: ModelConfig) -> GeneratedModel:
    prof = PROFILES[cfg.sector] if cfg.sector else rng.choice(list(PROFILES.values()))
    u = rng.uniform
    use_inv = cfg.inventory and prof.dio[1] > 0

    # ---------------- drivers -------------------------------------------
    cogs_pct = round(u(*prof.cogs_pct), 3)
    sga_pct = round(u(*prof.sga_pct), 3)
    capex_pct = round(u(*prof.capex_pct), 3)
    da_pct = round(u(*prof.da_pct), 3)
    tax_rate = round(u(0.19, 0.30), 3)
    dso = float(round(u(*prof.dso)))
    dio = float(round(u(*prof.dio))) if use_inv else 0.0
    dpo = float(round(u(*prof.dpo)))
    int_rate = round(u(0.04, 0.09), 4)
    cash_rate = round(u(0.01, 0.04), 4)
    payout = round(u(0.0, 0.5), 2)
    rev_rate = round(int_rate + u(0.005, 0.02), 4)

    # ---------------- actuals --------------------------------------------
    n_hist, n_fc = cfg.n_hist, cfg.n_forecast
    first_year = rng.randint(2019, 2024)
    periods = [f"FY{first_year + i}A" for i in range(n_hist)] + [
        f"FY{first_year + n_hist + i}E" for i in range(n_fc)
    ]
    rev0 = 10 ** u(1.5, 4.0)  # $20m .. $10bn
    g_hist = [u(*prof.growth) for _ in range(n_hist)]
    revs = []
    r = rev0
    for i in range(n_hist):
        r = r * (1 + g_hist[i]) if i else r
        revs.append(_r(r))
    noise = lambda x, s=0.05: x * (1 + rng.gauss(0, s))  # noqa: E731
    cogs = [_r(noise(v * cogs_pct)) for v in revs]
    sga = [_r(noise(v * sga_pct)) for v in revs]
    ppe = [_r(v * u(*prof.ppe_to_rev)) for v in revs[:1]]
    for i in range(1, n_hist):
        ppe.append(_r(ppe[-1] * u(0.97, 1.12)))
    da = [_r(noise(ppe[max(i - 1, 0)] * da_pct)) for i in range(n_hist)]
    ar = [_r(noise(v * dso / 365)) for v in revs]
    inv = [_r(noise(c * dio / 365)) for c in cogs] if use_inv else None
    ap = [_r(noise(c * dpo / 365)) for c in cogs]
    debt0 = revs[-1] * u(0.1, 0.8)
    debt = [_r(debt0 * (1 + 0.05 * (n_hist - 1 - i))) for i in range(n_hist)]
    cash = [_r(v * u(0.04, 0.18)) for v in revs]
    revolver_bal = [0.0] * n_hist
    int_exp = [_r(noise(d * int_rate)) for d in debt]
    ebit_h = [revs[i] - cogs[i] - sga[i] - da[i] for i in range(n_hist)]
    tax_h = [_r(max(0.0, (ebit_h[i] - int_exp[i]) * tax_rate)) for i in range(n_hist)]
    cs = _r(revs[-1] * u(0.05, 0.4))
    common = [cs] * n_hist
    # retained earnings is the residual that makes each historical BS balance
    re_hist = []
    for i in range(n_hist):
        ta = cash[i] + ar[i] + (inv[i] if inv else 0.0) + ppe[i]
        tl = ap[i] + debt[i] + revolver_bal[i]
        re_hist.append(_r(ta - tl - common[i], 1))
        # rounding: make the identity exact by adjusting cash's last digit
        diff = ta - tl - common[i] - re_hist[-1]
        cash[i] = _r(cash[i] - diff, 6)

    repay = _r(debt[-1] * u(0.05, 0.25))
    min_cash = _r(revs[-1] * u(0.03, 0.08))

    # forecast growth: fade from a near-term rate toward a long-term rate
    g_near = u(*prof.growth)
    g_long = u(0.015, 0.035)
    g_fc = [round(g_near + (g_long - g_near) * i / max(1, n_fc - 1) + rng.gauss(0, 0.005), 3)
            for i in range(n_fc)]

    # ---------------- sheets ------------------------------------------------
    if cfg.single_sheet:
        IS = BS = CF = "Model"
        sheets = ["Assumptions", "Model"]
    else:
        IS, BS, CF = "IS", "BS", "CFS"
        sheets = ["Assumptions", IS, BS, CF]

    scalars = [
        Scalar("cogs_pct", "COGS (% of revenue)", cogs_pct, "%", "rate",
               "cost of goods sold as a share of same-year revenue"),
        Scalar("sga_pct", "SG&A (% of revenue)", sga_pct, "%", "rate",
               "SG&A expense as a share of same-year revenue"),
        Scalar("da_pct", "D&A (% of opening PP&E)", da_pct, "%", "rate",
               "depreciation & amortisation as a share of the prior year's closing net PP&E"),
        Scalar("capex_pct", "Capex (% of revenue)", capex_pct, "%", "rate",
               "capital expenditure as a share of same-year revenue"),
        Scalar("tax_rate", "Tax rate", tax_rate, "%", "rate", "income tax rate"),
        Scalar("dso", "Receivable days (DSO)", dso, "days", "days",
               "accounts receivable = revenue x DSO / 365"),
    ]
    if use_inv:
        scalars.append(Scalar("dio", "Inventory days (DIO)", dio, "days", "days",
                              "inventory = COGS x DIO / 365"))
    scalars += [
        Scalar("dpo", "Payable days (DPO)", dpo, "days", "days",
               "accounts payable = COGS x DPO / 365"),
        Scalar("int_rate", "Interest rate on term debt", int_rate, "%", "rate",
               "interest on the term loan"),
        Scalar("repay", "Scheduled term-debt repayment", repay, "$m", "money",
               "repaid each year, but never more than the outstanding opening balance"),
    ]
    if cfg.interest_income:
        scalars.append(Scalar("cash_rate", "Interest rate earned on cash", cash_rate, "%", "rate",
                              "interest income on cash"))
    if cfg.dividends:
        scalars.append(Scalar("payout", "Dividend payout ratio", payout, "%", "rate",
                              "share of positive net income paid as dividends"))
    if cfg.revolver:
        scalars += [
            Scalar("min_cash", "Minimum cash balance", min_cash, "$m", "money",
                   "the revolver is drawn to keep closing cash at least at this level"),
            Scalar("rev_rate", "Interest rate on revolver", rev_rate, "%", "rate",
                   "interest on the revolver"),
        ]

    avg = cfg.average_balances

    def bal(item: str) -> str:
        """Opening balance, or average of opening and closing (circular)."""
        return f"AVERAGE({{{item}[-1]}},{{{item}}})" if avg else f"{{{item}[-1]}}"

    bal_word = "the average of opening and closing" if avg else "the opening (prior-year closing)"

    lines: List[Line] = [
        Line("g_rev", "Revenue growth", "Assumptions", "%", fc=None, hist="blank",
             forecast=g_fc, kind="rate", desc="year-on-year revenue growth for each forecast year"),
        # ---------------- income statement ---------------------------------
        Line("rev", "Revenue", IS, fc="{rev[-1]}*(1+{g_rev})", history=revs,
             desc="prior-year revenue x (1 + revenue growth for the year)", section="Income statement"),
        Line("cogs", "Cost of goods sold", IS, fc="{rev}*{$cogs_pct}", history=cogs,
             desc="revenue x COGS %"),
        Line("gp", "Gross profit", IS, fc="{rev}-{cogs}", hist="formula", desc="revenue - COGS",
             total=True),
        Line("sga", "SG&A", IS, fc="{rev}*{$sga_pct}", history=sga, desc="revenue x SG&A %"),
        Line("ebitda", "EBITDA", IS, fc="{gp}-{sga}", hist="formula", desc="gross profit - SG&A",
             total=True),
        Line("da", "Depreciation & amortisation", IS, fc="{ppe[-1]}*{$da_pct}", history=da,
             desc="prior-year closing net PP&E x D&A %"),
        Line("ebit", "EBIT", IS, fc="{ebitda}-{da}", hist="formula", desc="EBITDA - D&A", total=True),
    ]
    int_tpl = f"{bal('debt')}*{{$int_rate}}"
    int_desc = f"{bal_word} term debt balance x term-debt interest rate"
    if cfg.revolver:
        int_tpl += f"+{bal('revolver')}*{{$rev_rate}}"
        int_desc += f", plus {bal_word} revolver balance x revolver rate"
    lines.append(Line("int_exp", "Interest expense", IS, fc=int_tpl, history=int_exp, desc=int_desc))
    ebt_tpl = "{ebit}-{int_exp}"
    if cfg.interest_income:
        lines.append(Line("int_inc", "Interest income", IS, fc=f"{bal('cash')}*{{$cash_rate}}",
                          history=[0.0] * n_hist,
                          desc=f"{bal_word} cash balance x interest rate earned on cash"))
        ebt_tpl += "+{int_inc}"
    lines += [
        Line("ebt", "Pre-tax income", IS, fc=ebt_tpl, hist="formula",
             desc="EBIT - interest expense" + (" + interest income" if cfg.interest_income else ""),
             total=True),
        Line("tax", "Income tax", IS,
             fc="MAX(0,{ebt})*{$tax_rate}" if cfg.tax_floor else "{ebt}*{$tax_rate}",
             history=tax_h,
             desc=("pre-tax income x tax rate, but zero when pre-tax income is negative "
                   "(no tax credit for losses)") if cfg.tax_floor else "pre-tax income x tax rate"),
        Line("ni", "Net income", IS, fc="{ebt}-{tax}", hist="formula", desc="pre-tax income - tax",
             total=True),
    ]

    # ---------------- balance sheet -------------------------------------------
    lines += [
        Line("cash", "Cash", BS, fc="{cf_end}", history=cash,
             desc="closing cash from the cash flow statement", section="Balance sheet"),
        Line("ar", "Accounts receivable", BS, fc="{rev}*{$dso}/365", history=ar,
             desc="revenue x DSO / 365"),
    ]
    ca_items = ["cash", "ar"]
    if use_inv:
        lines.append(Line("inv", "Inventory", BS, fc="{cogs}*{$dio}/365", history=inv,
                          desc="COGS x DIO / 365"))
        ca_items.append("inv")
    lines += [
        Line("tca", "Total current assets", BS, fc=f"SUM({{cash:{ca_items[-1]}}})", hist="formula",
             desc="sum of " + ", ".join(LABELS[i] for i in ca_items), total=True),
        Line("ppe", "Net PP&E", BS, fc="{ppe[-1]}-{cf_capex}-{da}", history=ppe,
             desc="prior-year net PP&E + capex - D&A (capex is shown as a negative cash flow, "
                  "so it is subtracted)"),
        Line("ta", "Total assets", BS, fc="{tca}+{ppe}", hist="formula", desc="current assets + PP&E",
             total=True),
        Line("ap", "Accounts payable", BS, fc="{cogs}*{$dpo}/365", history=ap,
             desc="COGS x DPO / 365"),
        Line("debt", "Term debt", BS, fc="{debt[-1]}+{cf_debt}", history=debt,
             desc="prior-year term debt + term-debt cash flow (repayments are negative)"),
    ]
    liab = ["ap", "debt"]
    if cfg.revolver:
        lines.append(Line("revolver", "Revolver", BS, fc="{revolver[-1]}+{cf_rev}",
                          history=revolver_bal, desc="prior-year revolver + revolver draw/(repayment)"))
        liab.append("revolver")
    lines += [
        Line("tl", "Total liabilities", BS, fc=f"SUM({{ap:{liab[-1]}}})", hist="formula",
             desc="sum of " + ", ".join(LABELS[i] for i in liab), total=True),
        Line("cs", "Common stock", BS, fc="{cs[-1]}", history=common,
             desc="unchanged from the prior year (no issuance)"),
        Line("re", "Retained earnings", BS, fc="{re[-1]}+{ni}+{cf_div}" if cfg.dividends else "{re[-1]}+{ni}",
             history=re_hist,
             desc="prior-year retained earnings + net income" + (
                 " + dividend cash flow (dividends are negative)" if cfg.dividends else "")),
        Line("te", "Total equity", BS, fc="{cs}+{re}", hist="formula", desc="common stock + retained earnings",
             total=True),
        Line("tle", "Total liabilities & equity", BS, fc="{tl}+{te}", hist="formula",
             desc="total liabilities + total equity", total=True),
        Line("check", "Balance check (assets - L&E)", BS, fc="ROUND({ta}-{tle},6)", hist="formula",
             kind="check", desc="total assets - total liabilities & equity, rounded to 6 dp; must be 0"),
    ]

    # ---------------- cash flow statement --------------------------------------
    cfo_items = ["cf_ni", "cf_da", "cf_ar"] + (["cf_inv"] if use_inv else []) + ["cf_ap"]
    lines += [
        Line("cf_ni", "Net income", CF, fc="{ni}", hist="blank", desc="net income from the income statement",
             section="Cash flow statement"),
        Line("cf_da", "Add back: D&A", CF, fc="{da}", hist="blank", desc="D&A from the income statement"),
        Line("cf_ar", "(Increase)/decrease in receivables", CF, fc="{ar[-1]}-{ar}", hist="blank",
             desc="prior-year receivables - current receivables"),
    ]
    if use_inv:
        lines.append(Line("cf_inv", "(Increase)/decrease in inventory", CF, fc="{inv[-1]}-{inv}",
                          hist="blank", desc="prior-year inventory - current inventory"))
    lines += [
        Line("cf_ap", "Increase/(decrease) in payables", CF, fc="{ap}-{ap[-1]}", hist="blank",
             desc="current payables - prior-year payables"),
        Line("cfo", "Cash flow from operations", CF, fc=f"SUM({{cf_ni:{cfo_items[-1]}}})", hist="blank",
             desc="sum of the operating lines above", total=True),
        Line("cf_capex", "Capital expenditure", CF, fc="-{rev}*{$capex_pct}", hist="blank",
             desc="minus revenue x capex % (a cash outflow, so negative)"),
        Line("cfi", "Cash flow from investing", CF, fc="{cf_capex}", hist="blank",
             desc="capital expenditure", total=True),
        Line("cf_debt", "Term-debt repayment", CF, fc="-MIN({$repay},{debt[-1]})", hist="blank",
             desc="minus the smaller of the scheduled repayment and the opening term-debt balance"),
    ]
    cff_items = ["cf_debt"]
    if cfg.dividends:
        lines.append(Line("cf_div", "Dividends paid", CF, fc="-MAX(0,{ni})*{$payout}", hist="blank",
                          desc="minus payout ratio x net income, and zero when net income is negative"))
        cff_items.append("cf_div")
    if cfg.revolver:
        pre_terms = "+".join(["{cf_beg}", "{cfo}", "{cfi}"] + ["{%s}" % c for c in cff_items])
        lines += [
            Line("cf_rev", "Revolver draw/(repayment)", CF,
                 fc="MAX(0,{revolver[-1]}+{$min_cash}-{cash_pre})-{revolver[-1]}", hist="blank",
                 desc="closing revolver = MAX(0, opening revolver + minimum cash - cash before revolver); "
                      "this line is closing minus opening revolver"),
        ]
        cff_items.append("cf_rev")
    lines += [
        Line("cff", "Cash flow from financing", CF, fc=f"SUM({{cf_debt:{cff_items[-1]}}})", hist="blank",
             desc="sum of the financing lines above", total=True),
        Line("cf_net", "Net change in cash", CF, fc="{cfo}+{cfi}+{cff}", hist="blank",
             desc="operating + investing + financing", total=True),
        Line("cf_beg", "Beginning cash", CF, fc="{cash[-1]}", hist="blank",
             desc="prior-year closing cash from the balance sheet"),
        Line("cf_end", "Ending cash", CF, fc="{cf_beg}+{cf_net}", hist="blank",
             desc="beginning cash + net change in cash", total=True),
    ]
    if cfg.revolver:
        lines.append(Line("cash_pre", "Memo: cash before revolver", CF, fc=pre_terms, hist="blank",
                          desc="beginning cash + operating + investing + financing excluding the revolver"))

    title = f"{prof.company_noun} three-statement model"
    spec = ModelSpec(title=title, periods=periods, n_hist=n_hist, sheets=sheets, scalars=scalars,
                     lines=lines, iterative=avg)

    identities = [
        Identity("balance_sheet_balances", "total assets = total liabilities & equity",
                 [(1, "ta", 0), (-1, "tle", 0)]),
        Identity("cash_ties_to_cfs", "balance-sheet cash = cash-flow-statement ending cash",
                 [(1, "cash", 0), (-1, "cf_end", 0)]),
        Identity("cfs_beginning_cash", "beginning cash = prior-year balance-sheet cash",
                 [(1, "cf_beg", 0), (-1, "cash", -1)]),
        Identity("ppe_rollforward", "PP&E = prior PP&E - capex cash flow - D&A",
                 [(1, "ppe", 0), (-1, "ppe", -1), (1, "cf_capex", 0), (1, "da", 0)]),
        Identity("debt_rollforward", "term debt = prior term debt + debt cash flow",
                 [(1, "debt", 0), (-1, "debt", -1), (-1, "cf_debt", 0)]),
        Identity("re_rollforward", "retained earnings = prior RE + net income + dividend cash flow",
                 [(1, "re", 0), (-1, "re", -1), (-1, "ni", 0)] + ([(-1, "cf_div", 0)] if cfg.dividends else [])),
        Identity("net_income_flows_to_cfs", "CFS net income = IS net income",
                 [(1, "cf_ni", 0), (-1, "ni", 0)]),
    ]
    if cfg.revolver:
        identities.append(Identity("revolver_rollforward", "revolver = prior revolver + draw/(repayment)",
                                   [(1, "revolver", 0), (-1, "revolver", -1), (-1, "cf_rev", 0)]))
    money_scalars = [s.id for s in scalars if s.kind == "money"]
    ids = {ln.id for ln in lines}
    asset_lines = [i for i in ("cash", "ar", "inv", "ppe") if i in ids]
    claim_lines = [i for i in ("ap", "debt", "revolver", "cs", "re") if i in ids]
    all_lines = [ln.id for ln in lines if ln.id != "check"]
    forbidden = [
        (asset_lines, ["tl", "te", "tle"], "asset line computed from liabilities/equity totals (balancing plug)"),
        (claim_lines, ["tca", "ta"], "liability/equity line computed from asset totals (balancing plug)"),
        (all_lines, ["check"], "model line depends on the balance check"),
    ]
    return GeneratedModel(spec, identities, prof, cfg, money_scalars, forbidden)
