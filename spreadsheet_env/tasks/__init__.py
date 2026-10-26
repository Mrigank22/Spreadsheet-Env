"""Task families and a deterministic registry.

A task id is ``<family>-d<difficulty>-s<seed>`` and fully determines the task,
so tasks never need to be stored: ``make_task("repair-d3-s17")`` rebuilds it.
"""

from __future__ import annotations

import random
import re
from functools import lru_cache
from typing import Callable, Dict, Optional, Sequence

from .base import Task
from .build import BUILD_LEVELS, build_task
from .build_free import FREE_LEVELS, build_free_task
from .dcf import DCF_LEVELS, dcf_task
from .repair import REPAIR_LEVELS, repair_task

FAMILIES: Dict[str, Callable[[int, int], Task]] = {
    "build": build_task,
    "repair": repair_task,
    "dcf": dcf_task,
    "build_free": build_free_task,
}
LEVELS = {"build": BUILD_LEVELS, "repair": REPAIR_LEVELS, "dcf": DCF_LEVELS, "build_free": FREE_LEVELS}

_ID = re.compile(r"^(?P<family>[a-z_]+)-d(?P<d>\d+)-s(?P<s>\d+)$")

# Seed ranges: training and test tasks never share seeds.
TRAIN_SEEDS = range(0, 100_000)
TEST_SEEDS = range(1_000_000, 1_001_000)


def register(name: str, fn: Callable[[int, int], Task], levels: dict) -> None:
    FAMILIES[name] = fn
    LEVELS[name] = levels


_FRONTIER_DONE = False


def ensure_frontier() -> None:
    """Register the frontier families on first use (lazily, to avoid an import
    cycle: frontier modules import the task helpers defined in this package)."""
    global _FRONTIER_DONE
    if _FRONTIER_DONE:
        return
    _FRONTIER_DONE = True
    from ..frontier import all_families

    for name, (fn, levels) in all_families().items():
        register(name, fn, levels)


@lru_cache(maxsize=512)
def make_task(task_id: str) -> Task:
    m = _ID.match(task_id)
    if not m:
        raise ValueError(f"bad task id {task_id!r} (expected family-dN-sN)")
    fam = m.group("family")
    ensure_frontier()
    if fam not in FAMILIES:
        raise ValueError(f"unknown family {fam!r}; known: {sorted(FAMILIES)}")
    return FAMILIES[fam](int(m.group("s")), int(m.group("d")))


def sample_task_id(rng: random.Random, families: Optional[Sequence[str]] = None,
                   difficulties: Optional[Sequence[int]] = None, split: str = "train") -> str:
    ensure_frontier()
    fam = rng.choice(list(families or FAMILIES))
    d = rng.choice(list(difficulties or LEVELS[fam]))
    seeds = TRAIN_SEEDS if split == "train" else TEST_SEEDS
    return f"{fam}-d{d}-s{rng.choice(seeds)}"


__all__ = ["ensure_frontier", "FAMILIES", "LEVELS", "Task", "make_task", "register", "sample_task_id",
           "TRAIN_SEEDS", "TEST_SEEDS"]
