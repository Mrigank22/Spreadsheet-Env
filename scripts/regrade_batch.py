"""Re-grade stored frontier answers offline (no API calls) after a grader/spec fix.

    python scripts/regrade_batch.py results/frontier/frontier_tier_v1.jsonl
writes <name>_regraded.jsonl and prints old vs new verdicts per task.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frontier_batch import grade_one  # noqa: E402

from spreadsheet_env.parallel import pmap_list  # noqa: E402


def main():
    path = sys.argv[1]
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    new = pmap_list(grade_one, [(r["task_id"], r["text"]) for r in rows])
    out = path.replace(".jsonl", "_regraded.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r, g in zip(rows, new):
            f.write(json.dumps({**r, **g, "old_solved": r["solved"]}) + "\n")
    changed = 0
    for r, g in sorted(zip(rows, new), key=lambda x: x[0]["task_id"]):
        mark = "" if r["solved"] == g["solved"] else "   <-- changed"
        changed += bool(mark)
        print(f"{r['task_id']:28s} old={r['solved']!s:5s} new={g['solved']!s:5s}{mark}"
              + ("" if g["solved"] else f"  failing: {g['failing'][:2]}"))
    print(f"solved: old {sum(r['solved'] for r in rows)}/{len(rows)}  new {sum(g['solved'] for g in new)}/{len(rows)}"
          f"  ({changed} verdicts changed) -> {out}")


if __name__ == "__main__":
    main()
