"""The Task container shared by every task family (no imports from families)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .engine.workbook import Key, Workbook


@dataclass
class InputInfo:
    """A perturbable constant input cell."""

    key: Key
    kind: str  # rate | growth | days | money | payout | tax
    base: float
    scale: float = 1.0  # typical money magnitude (for additive moves away from 0)
    lo: Optional[float] = None  # hard bounds for the perturbed value
    hi: Optional[float] = None
    # inputs sharing a group form a grid given in ascending order (e.g. exit values);
    # perturbed scenarios keep it ascending
    group: Optional[str] = None


@dataclass
class Fixup:
    """After perturbing inputs, set ``target = sum(sign * value)`` over ``terms``.

    Used to keep historical balance sheets balanced (retained earnings is the
    residual), so that a correct model still satisfies every identity.
    """

    target: Key
    terms: List[Tuple[float, Key]]


@dataclass
class IdentityCheck:
    """A reference-free identity instantiated on concrete cells.

    For each forecast period, ``sum(sign * value) == 0``.
    """

    name: str
    desc: str
    per_period: List[List[Tuple[int, Key]]]


@dataclass
class Task:
    task_id: str
    family: str
    difficulty: int
    seed: int
    instructions: str
    initial: Workbook
    reference: Workbook
    inputs: List[InputInfo]
    target_keys: List[Key]
    # cells the agent must not change (inputs, labels, headers, given formulas)
    locked: Dict[Key, object]
    scenarios: List[Dict[Key, float]] = field(default_factory=list)
    identities: List[IdentityCheck] = field(default_factory=list)
    money_inputs: List[Key] = field(default_factory=list)
    money_targets: List[Key] = field(default_factory=list)
    fixups: List[Fixup] = field(default_factory=list)
    # structural rules: (cells, cells they must not depend on, description)
    forbidden_deps: List[Tuple[List[Key], List[Key], str]] = field(default_factory=list)
    # reference-free metamorphic relations evaluated on the agent's own model:
    #   {"type": "grid", "cells": [[Key]], "row_headers": [Key], "col_headers": [Key],
    #    "row_input": Key, "col_input": Key, "output": Key, "runs": [run indices]}
    #   {"type": "monotone", "name": str, "output": Key, "input": Key, "delta": float,
    #    "sign": +1/-1, "runs": [run indices]}   (run 0 = base, i = scenario i)
    relations: List[dict] = field(default_factory=list)
    # labels for reports: key -> "IS!E5 Revenue FY2025E"
    labels: Dict[Key, str] = field(default_factory=dict)
    # repair tasks: the injected bugs (hidden); [] on a no-bug canary
    bugs: List[dict] = field(default_factory=list)
    # canary: the correct behaviour is to leave the model's semantics unchanged
    expect_no_change: bool = False
    max_steps: int = 60
    meta: Dict[str, object] = field(default_factory=dict)

    @property
    def input_keys(self) -> List[Key]:
        return [i.key for i in self.inputs]

    def is_editable(self, key: Key) -> bool:
        return key not in self.locked
