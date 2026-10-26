"""Frontier task tier: hard, real-world financial-modelling mechanics.

Each domain module exposes ``LEVELS`` and ``generate(rng, level) -> Bundle``.
``register_all`` turns every domain into three task families:

    <domain>_build   fixed layout; levels 1-2 per-row formula memo, 3-5 term sheet only
    <domain>_repair  injected bugs, term sheet only, undisclosed count, canaries
    <domain>_free    empty Model sheet, any layout, Outputs contract

Document-grade domains (``documents/``: credit agreement, LPA, indenture,
charter) use the generated legal document as the spec at every level.
The same seed gives the same company in every variant.
"""

from __future__ import annotations

import random
from typing import Callable, Dict


REPAIR = {1: ((1, 2), 0, 0.0), 2: ((1, 2), 1, 0.0), 3: ((2, 3), 1, 0.1), 4: ((2, 4), 2, 0.15),
          5: ((3, 4), 2, 0.15)}


def _bundle(gen: Callable, domain: str, seed: int, level: int):
    return gen(random.Random(f"{domain}:{level}:{seed}"), level)


def make_families(domain: str, gen: Callable, levels: Dict[int, dict], document: bool = False):
    """``document=True``: the spec is a legal document at every level (no per-row memo)."""
    from . import framework  # lazy: framework imports tasks, which registers these families

    def build(seed: int, difficulty: int = 3):
        b = _bundle(gen, domain, seed, difficulty)
        style = "brief" if (document or difficulty > 2) else "memo"
        return framework.build_task(b, f"{domain}_build", seed, difficulty, style, max_steps=40 + 20 * difficulty)

    def repair(seed: int, difficulty: int = 3):
        b = _bundle(gen, domain, seed, difficulty)
        n_bugs, latent, canary = REPAIR[difficulty]
        return framework.repair_task(b, f"{domain}_repair", seed, difficulty, n_bugs, latent, canary,
                                     max_steps=40 + 20 * difficulty,
                                     rng=random.Random(f"{domain}:repair:{difficulty}:{seed}"))

    def free(seed: int, difficulty: int = 3):
        b = _bundle(gen, domain, seed, difficulty)
        return framework.free_task(b, f"{domain}_free", seed, difficulty, max_steps=60 + 30 * difficulty)

    lv = {k: {} for k in levels}
    return {f"{domain}_build": (build, lv), f"{domain}_repair": (repair, lv), f"{domain}_free": (free, lv)}


def all_families():
    from . import abs as abs_, credit, fx_consolidation, lbo, project_finance, saas, tax_provision, vc_waterfall, waterfall

    fams = {}
    for mod in (lbo, waterfall, project_finance, abs_, saas, vc_waterfall, fx_consolidation, tax_provision,
                credit):
        fams.update(make_families(mod.DOMAIN, mod.generate, mod.LEVELS))
    fams.update(document_families())
    return fams


def document_families():
    """The document-grade tier (``frontier/documents``)."""
    import importlib

    from .documents import DOC_DOMAINS

    fams = {}
    for name in DOC_DOMAINS:
        mod = importlib.import_module(f".documents.{name}", __package__)
        fams.update(make_families(mod.DOMAIN, mod.generate, mod.LEVELS, document=True))
    return fams
