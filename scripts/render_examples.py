"""Render example tasks to docs/examples/ (what an agent sees, and a correct answer).

One task per frontier domain (training seed 0, so no test answer is published):
the full instruction text, followed by the reference formulas of the first
projection column. Re-run after changing a generator:

    python scripts/render_examples.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spreadsheet_env.engine.refs import addr  # noqa: E402
from spreadsheet_env.parallel import pmap_list  # noqa: E402
from spreadsheet_env.tasks import make_task  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "examples")
EXAMPLES = [
    ("ca_build-d4-s0", "Credit agreement (document spec): leveraged loan with pricing grid, ECF sweep, revolver, "
                       "HoldCo PIK and an equity-cure covenant"),
    ("lpa_build-d5-s0", "Limited partnership agreement (document spec): fund waterfall with fee offsets, GP "
                        "commitment, clawback and carry escrow"),
    ("indenture_build-d3-s0", "Auto ABS indenture (document spec): priority of payments with allocations of "
                              "principal, reserve account and OC target"),
    ("charter_build-d4-s0", "Certificate of incorporation (document spec): liquidation preferences, pari passu "
                            "classes, accruing dividends and weighted-average anti-dilution"),
    ("lbo_build-d5-s0", "LBO term sheet: circular average-balance interest, sweep grid, covenant with equity cure"),
    ("pf_build-d5-s0", "Project finance term sheet: sculpted debt, DSRA, banking vs actual case, lock-up"),
    ("tax_free-d4-s0", "Tax provision, free layout: allowances with phase-out, interest limitation, expiring "
                       "losses"),
    ("repair-d5-s0", "Core repair task: latent bugs in a circular three-statement model"),
]


def render(job):
    tid, title = job
    t = make_task(tid)
    lines = [f"# {tid}", "", f"**{title}.** Family `{t.family}`, level {t.difficulty}, training seed {t.seed}; "
             f"{len(t.target_keys)} graded cells, {len(t.scenarios)} perturbation scenarios.", "",
             "## What the agent sees", "", "````text", t.instructions.rstrip(), "````", ""]
    if t.bugs:
        lines += ["## Injected bugs (hidden from the agent)", "",
                  "| Operator | Effect | Cells | Bug | Correct |", "|---|---|---|---|---|"]
        for b in t.bugs:
            cells = list(b.get("cells", {}).items())
            cell, v = cells[0]
            more = f" (+{len(cells) - 1} more)" if len(cells) > 1 else ""
            lines.append(f"| {b['operator']} | {b['effect']} | {cell}{more} | `{v['bug']}` | `{v['correct']}` |")
        lines.append("")
    lay = t.meta.get("layout")
    if lay is not None:
        col = lay.col(lay.n_hist)
        if t.family.endswith("_free"):  # targets are Outputs links; show the reference model instead
            cells = [(sh.casefold(), r, c) for sh, r, c, raw in t.reference.cells("Model")
                     if isinstance(raw, str) and raw.startswith("=")]
        else:
            cells = list(t.target_keys)
        first = sorted({k for k in cells if k[2] == col}, key=lambda k: (k[0], k[1]))
        calc_cells = sorted(k for k in cells if k[2] < col)
        lines += ["## Reference formulas (first projection column and single-cell results)", "",
                  "| Cell | Label | Formula |", "|---|---|---|"]
        for k in first + calc_cells:
            raw = t.reference.raw(k)
            label = (t.labels.get(k) or t.reference.get(t.reference.sheet_name(k[0]), f"A{k[1]}") or "")
            label = str(label).replace("|", "/")
            lines.append(f"| {t.reference.sheet_name(k[0])}!{addr(k[1], k[2])} | {label} | `{raw}` |")
        lines.append("")
    path = os.path.join(OUT, f"{tid}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return tid, len(t.instructions.split())


def main():
    os.makedirs(OUT, exist_ok=True)
    done = pmap_list(render, EXAMPLES, progress="examples")
    index = ["# Example tasks", "", "Rendered by `scripts/render_examples.py` (training seed 0). Each file shows the "
             "full prompt and the reference formulas.", "", "| Task | Words in prompt | What it is |", "|---|---|---|"]
    for (tid, title), (_, words) in zip(EXAMPLES, done):
        index.append(f"| [{tid}]({tid}.md) | {words:,} | {title} |")
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")
    print(f"wrote {len(done)} examples to {OUT}")


if __name__ == "__main__":
    main()
