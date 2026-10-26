"""Deterministic grader for spreadsheet financial models.

The grader is a set of independent *oracles*; each can be switched off, which
is how the experiments compare them (``scripts/exp_kill_matrix.py``):

``integrity``    locked cells (inputs, labels, given formulas) unchanged; no
                 parse errors, forbidden/unsupported functions, unexpected
                 circularity, or runaway size.
``base``         golden match of every target cell at the base inputs. This is
                 the check value-matching benchmarks use.
``perturb``      golden match under every perturbation scenario (metamorphic /
                 differential testing against the hidden reference).
``identities``   reference-free accounting identities (balance sheet balances,
                 cash ties, roll-forwards) in the base case and every scenario.
``homogeneity``  reference-free scaling relation: multiplying every money input
                 by k multiplies every money target by k.
``structure``    dependency-graph rules that no value check can see:
                 (a) each target must depend on every input its reference
                 depends on and actually responds to (inputs that cancel
                 exactly may be left out; a check row keeps the full
                 syntactic rule, so a balance check that is always 0 cannot
                 be typed as 0), and (b) forbidden dependencies (an asset
                 line computed from liabilities & equity is a plug).
``relations``    reference-free metamorphic relations on the agent's own model:
                 each sensitivity-grid cell must equal the agent's output
                 recomputed at that cell's header inputs (data-table
                 semantics), and outputs must move in the economically
                 required direction (e.g. price falls as WACC rises).

``solved`` requires every enabled oracle to pass. The reward is binary by
default; ``shaped`` adds partial credit for the fraction of target cells that
are correct in every scenario (gated by integrity).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

from ..engine.parser import Call, Num, walk
from ..engine.refs import ExcelError, addr
from ..engine.workbook import CompiledWorkbook, Key, Workbook
from ..task import Task

ALL_ORACLES = ("integrity", "base", "perturb", "identities", "homogeneity", "structure", "relations")
RTOL = 1e-6
MAX_EXTRA_CELLS = 3000
# Literals a formula may legitimately contain without being a "jammed" input.
BENIGN_LITERALS = {0.0, 1.0, 2.0, 12.0, 100.0, 360.0, 365.0, 6.0, -1.0}


def close(a, r, rtol: float = RTOL) -> bool:
    if isinstance(a, bool) or isinstance(r, bool):
        return a == r
    if isinstance(a, float) and isinstance(r, float):
        return abs(a - r) <= rtol * max(1.0, abs(r))
    return a == r


def value_only_close(a, r) -> bool:
    """Spreadsheet-benchmark style comparison: values rounded to 2 decimals."""
    if isinstance(a, float) and isinstance(r, float):
        return round(a, 2) == round(r, 2)
    return a == r


@dataclass
class GradeResult:
    solved: bool
    reward: float
    components: Dict[str, float]
    violations: List[str] = field(default_factory=list)
    failing: List[str] = field(default_factory=list)
    diagnostics: Dict[str, object] = field(default_factory=dict)

    def summary(self, max_items: int = 8) -> str:
        lines = [f"solved={self.solved} reward={self.reward:.3f}"]
        lines.append("components: " + ", ".join(f"{k}={v:.3f}" for k, v in self.components.items()))
        if self.violations:
            lines.append("integrity violations: " + "; ".join(self.violations[:max_items]))
        if self.failing:
            lines.append("incorrect cells: " + "; ".join(self.failing[:max_items])
                         + (" ..." if len(self.failing) > max_items else ""))
        return "\n".join(lines)


class Grader:
    def __init__(self, oracles: Iterable[str] = ALL_ORACLES, reward_mode: str = "binary",
                 value_only_tolerance: bool = False):
        self.oracles = set(oracles)
        unknown = self.oracles - set(ALL_ORACLES)
        if unknown:
            raise ValueError(f"unknown oracles {unknown}")
        self.reward_mode = reward_mode
        self.value_only_tolerance = value_only_tolerance
        self._ref_cache: Dict[str, tuple] = {}

    # ------------------------------------------------------------------
    def _reference_runs(self, task: Task):
        cached = self._ref_cache.get(task.task_id)
        if cached is not None and cached[0] is task:
            return cached[1]
        cw = task.reference.compile()
        runs = [cw.run()] + [cw.run(sc) for sc in task.scenarios]
        self._ref_cache[task.task_id] = (task, runs)
        if len(self._ref_cache) > 256:
            self._ref_cache.pop(next(iter(self._ref_cache)))
        return runs

    def grade(self, task: Task, submission: Workbook) -> GradeResult:
        """Grade a submission. Never raises: anything the submission does that
        breaks evaluation is a failed submission, reported in ``violations``."""
        try:
            return self._grade(task, submission)
        except Exception as e:  # noqa: BLE001 - deliberate: the grader must not crash
            comps = {o: 0.0 for o in self.oracles}
            return GradeResult(False, 0.0, comps, [f"submission could not be evaluated: {type(e).__name__}: {e}"],
                               [], {"exception": repr(e)[:500]})

    def _grade(self, task: Task, submission: Workbook) -> GradeResult:
        comps: Dict[str, float] = {}
        violations: List[str] = []
        diag: Dict[str, object] = {}
        label = lambda k: task.labels.get(k) or f"{submission.sheet_name(k[0]) if submission.has_sheet(k[0]) else k[0]}!{addr(k[1], k[2])}"  # noqa: E731

        cw = submission.compile()

        # ---------------- integrity --------------------------------------
        if "integrity" in self.oracles:
            violations = self.integrity_violations(task, submission, cw)
            comps["integrity"] = 0.0 if violations else 1.0

        # ---------------- recalculation ------------------------------------
        sub_runs = [cw.run()] + [cw.run(sc) for sc in task.scenarios]
        ref_runs = self._reference_runs(task)
        cmp = value_only_close if self.value_only_tolerance else close

        targets = task.target_keys
        base_ok = {k: cmp(sub_runs[0].get(k), ref_runs[0].get(k)) for k in targets}
        robust_ok = dict(base_ok)
        first_bad_scenario: Dict[Key, int] = {}
        for i in range(1, len(sub_runs)):
            for k in targets:
                if robust_ok[k] and not cmp(sub_runs[i].get(k), ref_runs[i].get(k)):
                    robust_ok[k] = False
                    first_bad_scenario[k] = i
        n = max(1, len(targets))
        if "base" in self.oracles:
            comps["base"] = sum(base_ok.values()) / n
        if "perturb" in self.oracles:
            comps["perturb"] = sum(robust_ok.values()) / n
        diag["latent_wrong"] = [label(k) for k in targets if base_ok[k] and not robust_ok[k]][:20]

        # ---------------- identities (reference-free) ----------------------
        if "identities" in self.oracles and task.identities:
            total = passed = 0
            broken: Dict[str, int] = {}
            for idc in task.identities:
                for terms in idc.per_period:
                    for run in sub_runs:
                        total += 1
                        if _identity_holds(run, terms):
                            passed += 1
                        else:
                            broken[idc.name] = broken.get(idc.name, 0) + 1
            comps["identities"] = passed / max(1, total)
            diag["identities_broken"] = broken

        # ---------------- homogeneity (reference-free) ---------------------
        if "homogeneity" in self.oracles and task.money_targets and task.meta.get("scale_factor"):
            f = float(task.meta["scale_factor"])
            idx = len(sub_runs) - 1  # scale scenario is always last
            ok = 0
            for k in task.money_targets:
                a, b = sub_runs[0].get(k), sub_runs[idx].get(k)
                if isinstance(a, float) and isinstance(b, float) and close(b, a * f, 1e-6):
                    ok += 1
            comps["homogeneity"] = ok / len(task.money_targets)

        # ---------------- metamorphic relations (reference-free) -------------
        if "relations" in self.oracles and task.relations:
            total = passed = 0
            broken: Dict[str, int] = {}
            for rel in task.relations:
                for i in rel.get("runs", range(len(sub_runs))):
                    sc = {} if i == 0 else task.scenarios[i - 1]
                    ok = _relation_holds(cw, rel, sc, sub_runs[i])
                    total += 1
                    passed += ok
                    if not ok:
                        name = rel.get("name", rel["type"])
                        broken[name] = broken.get(name, 0) + 1
            comps["relations"] = passed / max(1, total)
            diag["relations_broken"] = broken

        # ---------------- structure (dependency graph) ----------------------
        if "structure" in self.oracles:
            # the (costlier) cancellation test can only change the verdict of a
            # submission every other oracle accepts
            sp = self.structure_problems(task, cw, label,
                                         refine=all(v >= 1.0 - 1e-12 for v in comps.values()))
            comps["structure"] = 0.0 if sp else 1.0
            diag["structure_problems"] = sp[:10]

        # ---------------- static diagnostics -------------------------------
        hard = [label(k) for k in targets
                if _is_formula_value(task.reference, k) and not _is_formula_value(submission, k)]
        diag["hardcoded_targets"] = hard[:20]
        diag["n_hardcoded_targets"] = len(hard)
        diag["jammed_literals"] = _jammed_literals(cw, targets)[:20]

        failing = []
        for k in targets:
            if not robust_ok[k]:
                i = first_bad_scenario.get(k, 0)
                where = "base case" if i == 0 else f"scenario {i}"
                failing.append(f"{label(k)} ({where})")

        # ---------------- verdict ---------------------------------------------
        solved = all(v >= 1.0 - 1e-12 for v in comps.values())
        if self.reward_mode == "binary":
            reward = 1.0 if solved else 0.0
        elif self.reward_mode == "shaped":
            gate = comps.get("integrity", 1.0)
            frac = comps.get("perturb", comps.get("base", 0.0))
            idn = comps.get("identities", 1.0)
            reward = 1.0 if solved else gate * (0.7 * frac + 0.2 * idn) * 0.9
        else:
            raise ValueError(self.reward_mode)
        return GradeResult(solved, reward, comps, violations, failing, diag)

    # ------------------------------------------------------------------
    def _reference_closures(self, task: Task):
        cached = self._ref_cache.get(("closures", task.task_id))
        if cached is not None and cached[0] is task:
            return cached[1]
        clo = task.reference.compile().closures()
        self._ref_cache[("closures", task.task_id)] = (task, clo)
        return clo

    def _check_keys(self, task: Task) -> frozenset:
        """Cells of check rows (``kind == "check"``, e.g. the balance check), all periods."""
        cached = self._ref_cache.get(("checks", task.task_id))
        if cached is not None and cached[0] is task:
            return cached[1]
        spec, lay = task.meta.get("spec"), task.meta.get("layout")
        keys = frozenset()
        if spec is not None and lay is not None:
            keys = frozenset(lay.key(ln.id, p) for ln in spec.lines if ln.kind == "check" and ln.id in lay.rows
                             for p in range(lay.n_periods))
        self._ref_cache[("checks", task.task_id)] = (task, keys)
        return keys

    def _sensitive(self, task: Task, k: Key, i: Key) -> bool:
        """Does the reference value of target ``k`` respond to input ``i``?

        Input ``i`` alone is moved up and down in the base case and in every
        scenario. An input that never moves ``k`` cancels exactly (e.g. LC cash
        is a balancing line, so assets drop out of a translation difference)
        and an equivalent formula may leave it out. Cached per task."""
        cache = self._ref_cache.setdefault(("sensitivity", task.task_id), (task, {}))
        if cache[0] is not task:
            cache = self._ref_cache[("sensitivity", task.task_id)] = (task, {})
        memo = cache[1]
        if (k, i) in memo:
            return memo[(k, i)]
        runs = self._reference_runs(task)
        cached = self._ref_cache.get(("compiled", task.task_id))
        if cached is None or cached[0] is not task:
            cached = self._ref_cache[("compiled", task.task_id)] = (task, task.reference.compile())
        cw = cached[1]
        hit = False
        for sc, rr in zip([{}] + list(task.scenarios), runs):
            v = sc.get(i, runs[0].get(i))
            v = v if isinstance(v, float) else 0.0
            for new in (v * 1.37 + 0.731, v * 0.71 - 0.219):
                if not close(cw.run({**sc, i: new}).get(k), rr.get(k), 1e-9):
                    hit = True
                    break
            if hit:
                break
        memo[(k, i)] = hit
        return hit

    def structure_problems(self, task: Task, cw: CompiledWorkbook, label, refine: bool = True) -> List[str]:
        out: List[str] = []
        inputs = set(task.input_keys) | {fx.target for fx in task.fixups}
        ref_clo = self._reference_closures(task)
        sub_clo = cw.closures()
        disconnected = []
        for k in task.target_keys:
            need = ref_clo.get(k, frozenset()) & inputs
            if not need:
                continue
            have = sub_clo.get(k, frozenset())
            missing = need - have
            # A target need only depend on the inputs it actually responds to (inputs that
            # cancel exactly may be left out, HACK_LOG #19; a structural zero such as the
            # first-year ECF prepayment may be typed as 0, #24). Check rows keep the
            # syntactic rule: that is what tells a computed balance check from a typed 0
            # (HACK_LOG #4).
            if missing and refine and k not in self._check_keys(task):
                missing = {i for i in missing if self._sensitive(task, k, i)}
            if missing:
                disconnected.append((k, len(missing)))
        if disconnected:
            k, n = disconnected[0]
            out.append(f"{len(disconnected)} target cell(s) do not depend on inputs their logic requires "
                       f"(hard-coded or disconnected), e.g. {label(k)} misses {n} input(s)")
        for srcs, bans, why in task.forbidden_deps:
            banned = set(bans)
            for k in srcs:
                if sub_clo.get(k, frozenset()) & banned:
                    out.append(f"{label(k)}: {why}")
                    break
        return out

    def integrity_violations(self, task: Task, sub: Workbook, cw: CompiledWorkbook) -> List[str]:
        out: List[str] = []
        if [s.casefold() for s in sub.sheet_names] != [s.casefold() for s in task.initial.sheet_names]:
            out.append("sheets were added, removed or renamed")
        snap = sub.snapshot()
        changed = []
        for k, raw in task.locked.items():
            v = snap.get(k)
            if not _same_raw(v, raw):
                changed.append(k)
        if changed:
            names = ", ".join(task.labels.get(k) or f"{k[0]}!{addr(k[1], k[2])}" for k in changed[:6])
            out.append(f"{len(changed)} locked cell(s) changed (inputs/labels/given formulas): {names}")
        probs = cw.problems()
        if probs:
            k, msg = next(iter(probs.items()))
            out.append(f"{len(probs)} formula problem(s), e.g. {k[0]}!{addr(k[1], k[2])}: {msg}")
        if cw.cyclic and not task.reference.iterative:
            out.append(f"circular references in {len(cw.cyclic)} cell(s)")
        if len(snap) > len(task.initial.snapshot()) + cell_budget(task):
            out.append("too many cells written")
        return out


def cell_budget(task: Task) -> int:
    """New cells a submission may write: a fixed floor, or 2x what the reference
    itself writes (large free-layout builds). Shared by the integrity oracle and
    the patch-mode writer, so neither rejects a full-size correct model."""
    n_init = len(task.initial.snapshot())
    return max(MAX_EXTRA_CELLS, 2 * (len(task.reference.snapshot()) - n_init))


def _relation_holds(cw: CompiledWorkbook, rel: dict, sc: dict, run: Dict[Key, object]) -> bool:
    if rel["type"] == "grid":
        for i, rk in enumerate(rel["row_headers"]):
            for j, ck in enumerate(rel["col_headers"]):
                w, g = run.get(rk), run.get(ck)
                cell = run.get(rel["cells"][i][j])
                if not (isinstance(w, float) and isinstance(g, float) and isinstance(cell, float)):
                    return False
                out = cw.run({**sc, rel["row_input"]: w, rel["col_input"]: g}).get(rel["output"])
                if not isinstance(out, float) or not close(cell, out, 1e-6):
                    return False
        return True
    if rel["type"] == "monotone":
        base = run.get(rel["output"])
        x = run.get(rel["input"])
        if not (isinstance(base, float) and isinstance(x, float)):
            return False
        moved = cw.run({**sc, rel["input"]: x + rel["delta"]}).get(rel["output"])
        if not isinstance(moved, float):
            return False
        return rel["sign"] * (moved - base) > 1e-9 * max(1.0, abs(base))
    raise ValueError(f"unknown relation {rel['type']}")


def _same_raw(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return a == b or (math.isnan(a) and math.isnan(b))
    if isinstance(a, str) and isinstance(b, str) and a.startswith("=") and b.startswith("="):
        return a.replace(" ", "").upper() == b.replace(" ", "").upper()
    return a == b


def _identity_holds(run: Dict[Key, object], terms) -> bool:
    s = 0.0
    mag = 1.0
    for sign, k in terms:
        v = run.get(k)
        if v is None:
            v = 0.0
        if not isinstance(v, float) or isinstance(v, bool):
            return False
        s += sign * v
        mag = max(mag, abs(v))
    return abs(s) <= 1e-6 * mag


def _is_formula_value(wb: Workbook, k: Key) -> bool:
    raw = wb.raw(k)
    return isinstance(raw, str) and raw.startswith("=")


def _jammed_literals(cw: CompiledWorkbook, targets: Sequence[Key]) -> List[str]:
    out = []
    for k in targets:
        cc = cw.cells.get(k)
        if not cc or cc.ast is None:
            continue
        lits = [n.value for n in walk(cc.ast) if isinstance(n, Num) and n.value not in BENIGN_LITERALS]
        if lits:
            out.append(f"{k[0]}!{addr(k[1], k[2])}: {lits[:3]}")
    return out
