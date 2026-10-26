"""Rendering of generated legal documents (credit agreements, LPAs, indentures, charters).

A document is assembled clause by clause by a domain generator, right next to the
model formula each operative clause encodes. This module only does the drafting
mechanics real documents have and models must cope with:

* defined terms collected in Section 1.01 in **alphabetical** order (so the
  logic is scattered, as in a real agreement, not presented in model order);
* numbered articles and sections, with cross-references written as
  ``[[key]]`` or ``[[key|(d)]]`` and resolved to "Section 2.08(d)" at render time;
* schedules and annexes after the articles.

Distractor clauses (provisions about events the model does not contain) are
added by the generators; the model conventions annex states which events do not
occur, so a distractor never makes the answer ambiguous.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_XREF = re.compile(r"\[\[([a-z0-9_]+)(\|[^\]]*)?\]\]")


@dataclass
class _Section:
    key: str
    heading: str
    text: str


@dataclass
class _Article:
    heading: str
    sections: List[_Section] = field(default_factory=list)


class LegalDoc:
    def __init__(self, title: str, preamble: str, defs_heading: str = "DEFINITIONS AND ACCOUNTING TERMS",
                 section_word: str = "Section"):
        self.title = title
        self.preamble = preamble
        self.section_word = section_word
        self.defs: Dict[str, str] = {}
        self.articles: List[_Article] = [_Article(defs_heading)]
        self._art_index: Dict[str, int] = {defs_heading: 0}
        self.annexes: List[Tuple[str, str]] = []

    # ------------------------------------------------------------------ building
    def define(self, term: str, text: str) -> None:
        """``text`` continues the sentence '"Term" ...' (usually starting with 'means')."""
        if term in self.defs:
            raise ValueError(f"term defined twice: {term}")
        self.defs[term] = text

    def section(self, article: str, key: str, heading: str, text: str) -> None:
        if article not in self._art_index:
            self._art_index[article] = len(self.articles)
            self.articles.append(_Article(article))
        art = self.articles[self._art_index[article]]
        if any(s.key == key for a in self.articles for s in a.sections):
            raise ValueError(f"section key used twice: {key}")
        art.sections.append(_Section(key, heading, text))

    def annex(self, heading: str, text: str) -> None:
        self.annexes.append((heading, text))

    # ------------------------------------------------------------------ rendering
    def render(self) -> str:
        numbers: Dict[str, str] = {}
        for ai, art in enumerate(self.articles, 1):
            offset = 2 if ai == 1 else 1  # Section 1.01 is reserved for the defined terms
            for si, s in enumerate(art.sections, offset):
                numbers[s.key] = f"{ai}.{si:02d}"

        def resolve(text: str) -> str:
            def sub(m):
                key, suffix = m.group(1), (m.group(2) or "|")[1:]
                if key not in numbers:
                    raise KeyError(f"unresolved cross-reference [[{key}]]")
                return f"{self.section_word} {numbers[key]}{suffix}"
            return _XREF.sub(sub, text)

        out = [self.title.upper(), "", resolve(self.preamble), ""]
        for ai, art in enumerate(self.articles, 1):
            out += [f"ARTICLE {_roman(ai)}", art.heading.upper(), ""]
            if ai == 1:
                out.append(f"{self.section_word} 1.01 Defined Terms. As used in this Agreement, the following terms "
                           "have the meanings specified below:")
                for term in sorted(self.defs, key=lambda t: t.casefold().strip('"')):
                    out.append(f"\"{term}\" {resolve(self.defs[term])}")
                out.append("")
            for s in art.sections:
                out.append(f"{self.section_word} {numbers[s.key]} {s.heading}. {resolve(s.text)}")
                out.append("")
        for heading, text in self.annexes:
            out += [heading.upper(), resolve(text), ""]
        return "\n".join(out).rstrip() + "\n"


def _roman(n: int) -> str:
    vals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


_FIRST = ["Alder", "Brackley", "Corvel", "Dunmore", "Elsby", "Fenwick", "Galloway", "Harrowgate", "Inverly",
          "Juniper", "Kestrel", "Larchmont", "Merrow", "Norland", "Ospreay", "Pellham", "Quarrington", "Rowanby",
          "Sableton", "Tamsworth", "Umber", "Vantor", "Wexley", "Yarrowdale"]
_SECOND = ["Industrial", "Health", "Software", "Brands", "Logistics", "Materials", "Foods", "Services", "Systems"]


def company_name(rng: random.Random) -> str:
    """A fictional company stem (no real issuer, lender or fund names)."""
    return f"{rng.choice(_FIRST)} {rng.choice(_SECOND)}"


def pct_words(label: str) -> str:
    """Refer to a Schedule 1 input by its caption (the value lives on the Assumptions sheet)."""
    return f"the percentage set forth opposite the caption \"{label}\" in Schedule 1"


def choose(rng: random.Random, items: List[str], k: int) -> List[str]:
    k = max(0, min(k, len(items)))
    return rng.sample(items, k)


def opt(cond: bool, text: str, alt: str = "") -> str:
    return text if cond else alt


def join_nonempty(*parts: Optional[str], sep: str = " ") -> str:
    return sep.join(p for p in parts if p)
