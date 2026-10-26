"""Differential test: does our engine compute what independent engines compute?

Corpus: for each family x difficulty x seed, the reference workbook, the
reference under a few perturbation scenarios (inputs overwritten), and (for
repair tasks) the bugged workbook. Each is written to .xlsx and evaluated by

* this package's engine,
* formualizer (Rust, Excel-compatible; supports iterative calculation),
* ironcalc (Rust; no iterative calculation, so circular models are skipped),
* LibreOffice headless (optional, ``--libreoffice``; run via Docker).

Every formula cell is compared (relative tolerance 1e-9, 1e-6 on circular
cells). Output: agreement rates and the first disagreements, saved to
``results/engine_crosscheck.json``.

    python scripts/crosscheck_engines.py --seeds 20
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import tempfile
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spreadsheet_env.engine.refs import ExcelError, addr  # noqa: E402
from spreadsheet_env.engine.xlsx import save_xlsx  # noqa: E402
from spreadsheet_env.parallel import default_workers, pmap  # noqa: E402
from spreadsheet_env.tasks import make_task  # noqa: E402


def norm(v):
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, ExcelError):
        return v.code
    s = str(v)
    if s.startswith("#"):
        return s.upper()
    try:
        return float(s)
    except ValueError:
        return s


def agree(a, b, rtol):
    a, b = norm(a), norm(b)
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) or math.isnan(b):
            return False
        return abs(a - b) <= rtol * max(1.0, abs(a), abs(b))
    return a == b


FAMILIES = ("build", "repair", "dcf", "build_free")


def task_corpus(task_id, n_scen=3):
    """The workbooks derived from one task: reference, perturbed references, bugged copy."""
    t = make_task(task_id)
    yield f"{t.task_id}/reference", t.reference.copy()
    for i, sc in enumerate(t.scenarios[:n_scen]):
        wb = t.reference.copy()
        for k, v in sc.items():
            wb.set_rc(wb.sheet_name(k[0]), k[1], k[2], v)
        yield f"{t.task_id}/scenario{i}", wb
    if t.family == "repair" and t.bugs:
        yield f"{t.task_id}/bugged", t.initial.copy()


def eval_formualizer(path, keys, sheet_names):
    import formualizer as fz

    wb = fz.load_workbook(path)
    wb.evaluate_all()
    return {k: wb.get_value(sheet_names[k[0]], k[1], k[2]) for k in keys}


def eval_ironcalc(path, keys, sheet_index):
    import ironcalc as ic

    m = ic.load_from_xlsx(path, "en", "UTC")
    m.evaluate()
    return {k: m.get_cell_value(sheet_index[k[0]], k[1], k[2]) for k in keys}


def _record(stats, by_fn, examples, eng, name, wb, cw, ours, vals_of):
    for k in sorted(cw.cells):
        v = vals_of(k)
        rtol = 1e-6 if k in cw.cyclic else 1e-9
        ok = agree(ours[k], v, rtol)
        stats[eng]["cells"] += 1
        stats[eng]["agree" if ok else "disagree"] += 1
        kind = "circular_wb" if cw.cyclic else "acyclic_wb"
        stats[eng][f"{kind}_cells"] += 1
        stats[eng][f"{kind}_{'agree' if ok else 'disagree'}"] += 1
        for f in cw.functions_used(k) or {"(arith)"}:
            by_fn[eng][f]["agree" if ok else "disagree"] += 1
        if not ok and len(examples[eng]) < 25:
            examples[eng].append(f"{name} {wb.sheet_name(k[0])}!{addr(k[1], k[2])} {wb.raw(k)}: "
                                 f"ours={norm(ours[k])!r} {eng}={norm(v)!r}")


def check_task(job):
    """Evaluate one task's workbooks in every in-process engine; runs in a worker."""
    task_id, tmp, keep_files = job
    stats = defaultdict(Counter)
    by_fn = defaultdict(lambda: defaultdict(Counter))
    examples = defaultdict(list)
    kept = []
    n_wb = 0
    for j, (name, wb) in enumerate(task_corpus(task_id)):
        n_wb += 1
        cw = wb.compile()
        ours = cw.run()
        keys = sorted(cw.cells)
        path = os.path.join(tmp, f"{task_id}_{j}.xlsx")
        save_xlsx(wb, path)
        sheet_names = {n.casefold(): n for n in wb.sheet_names}
        sheet_index = {n.casefold(): i for i, n in enumerate(wb.sheet_names)}
        try:
            vals = eval_formualizer(path, keys, sheet_names)
            _record(stats, by_fn, examples, "formualizer", name, wb, cw, ours, vals.get)
        except Exception as e:  # noqa: BLE001 - reported, not fatal
            stats["formualizer"]["load_error"] += 1
            examples["formualizer"].append(f"{name}: load error {e!r}"[:300])
        if not wb.iterative:
            try:
                vals = eval_ironcalc(path, keys, sheet_index)
                _record(stats, by_fn, examples, "ironcalc", name, wb, cw, ours, vals.get)
            except Exception as e:  # noqa: BLE001
                stats["ironcalc"]["load_error"] += 1
                examples["ironcalc"].append(f"{name}: load error {e!r}"[:300])
        else:
            stats["ironcalc"]["skipped_circular_workbooks"] += 1
        if keep_files:
            kept.append((name, path))
        else:
            os.remove(path)
    return n_wb, {e: dict(c) for e, c in stats.items()},         {e: {f: dict(c) for f, c in d.items()} for e, d in by_fn.items()}, dict(examples), kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--workers", type=int, default=default_workers())
    ap.add_argument("--out", default="results/engine_crosscheck.json")
    ap.add_argument("--libreoffice", action="store_true", help="also compare with LibreOffice (Docker)")
    args = ap.parse_args()

    engines = ["formualizer", "ironcalc"] + (["libreoffice"] if args.libreoffice else [])
    stats = {e: Counter() for e in engines}
    by_fn = {e: defaultdict(Counter) for e in engines}
    examples = {e: [] for e in engines}
    tmp = tempfile.mkdtemp(prefix="sse_xcheck_")
    t0 = time.time()
    jobs = [(f"{fam}-d{d}-s{s}", tmp, args.libreoffice) for d in (5, 4, 3, 2, 1) for fam in FAMILIES
            for s in range(args.seeds)]
    n_wb = 0
    lo_files = []
    for _, (n, st, bf, ex, kept) in pmap(check_task, jobs, args.workers, progress="crosscheck"):
        n_wb += n
        for e, c in st.items():
            stats[e].update(c)
        for e, d in bf.items():
            for f, c in d.items():
                by_fn[e][f].update(c)
        for e, lst in ex.items():
            examples[e] += lst[: max(0, 25 - len(examples[e]))]
        lo_files += kept
    if args.libreoffice:
        from libreoffice_eval import evaluate_many  # scripts/libreoffice_eval.py

        from spreadsheet_env.engine.xlsx import load_xlsx

        lo_vals = evaluate_many([p for _, p in lo_files])
        for (name, path), vals in zip(lo_files, lo_vals):
            if vals is None:
                stats["libreoffice"]["load_error"] += 1
                continue
            wb = load_xlsx(path)
            cw = wb.compile()
            ours = cw.run()
            names = {n.casefold(): n for n in wb.sheet_names}
            _record(stats, by_fn, examples, "libreoffice", name, wb, cw, ours,
                    lambda k, vals=vals, names=names: vals.get((names[k[0]], k[1], k[2])))

    shutil.rmtree(tmp, ignore_errors=True)
    report = {
        "workbooks": n_wb,
        "seconds": round(time.time() - t0, 1),
        "engines": {
            e: {
                **dict(stats[e]),
                "agreement": (stats[e]["agree"] / stats[e]["cells"]) if stats[e]["cells"] else None,
                "by_function": {f: dict(c) for f, c in sorted(by_fn[e].items())},
                "examples": examples[e],
            }
            for e in engines
        },
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(report, f, indent=1)
    for e in engines:
        r = report["engines"][e]
        print(f"{e}: {r.get('agree', 0)}/{r.get('cells', 0)} cells agree "
              f"({(r['agreement'] or 0) * 100:.4f}%), load errors {r.get('load_error', 0)}, "
              f"skipped circular {r.get('skipped_circular_workbooks', 0)}")
        print("    ", {k: v for k, v in r.items() if k.startswith(("circular", "acyclic"))})
        for ex in r["examples"][:4]:
            print("   ", ex)
    print(f"{n_wb} workbooks in {report['seconds']}s -> {args.out}")


if __name__ == "__main__":
    main()
