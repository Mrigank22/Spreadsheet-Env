"""Process-pool helpers: run independent work units on every CPU core.

The formula engine and grader are pure Python, so threads cannot use more than
one core (the GIL); work is spread over *processes*. Every experiment script
splits its job into independent units (one task, seed, workbook or episode)
and maps them with ``pmap``.

Default worker count: all logical cores minus two (OS and the parent process
stay responsive), overridable with ``--workers`` or the ``SSE_WORKERS``
environment variable.
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, Callable, Iterable, Iterator, List, Optional, Tuple


def default_workers() -> int:
    env = os.environ.get("SSE_WORKERS")
    if env:
        return max(1, int(env))
    return max(1, (os.cpu_count() or 2) - 2)


def pmap(fn: Callable[[Any], Any], items: Iterable[Any], workers: Optional[int] = None,
         progress: Optional[str] = None, ordered: bool = False) -> Iterator[Tuple[int, Any]]:
    """Yield ``(index, fn(item))`` as results complete (or in input order).

    ``fn`` must be a top-level (picklable) function. With ``workers == 1`` it
    runs in-process, which keeps tracebacks readable while debugging.
    """
    items = list(items)
    workers = workers or default_workers()
    t0 = time.time()
    if workers == 1 or len(items) <= 1:
        for i, it in enumerate(items):
            yield i, fn(it)
            _progress(progress, i + 1, len(items), t0)
        return
    with ProcessPoolExecutor(max_workers=min(workers, len(items))) as ex:
        futs = {ex.submit(fn, it): i for i, it in enumerate(items)}
        if ordered:
            done: dict = {}
            nxt = 0
            for n, fut in enumerate(as_completed(futs), 1):
                done[futs[fut]] = fut.result()
                _progress(progress, n, len(items), t0)
                while nxt in done:
                    yield nxt, done.pop(nxt)
                    nxt += 1
        else:
            for n, fut in enumerate(as_completed(futs), 1):
                yield futs[fut], fut.result()
                _progress(progress, n, len(items), t0)


def pmap_list(fn: Callable[[Any], Any], items: Iterable[Any], workers: Optional[int] = None,
              progress: Optional[str] = None) -> List[Any]:
    """``[fn(x) for x in items]``, computed in parallel, in input order."""
    out = {}
    for i, r in pmap(fn, items, workers, progress):
        out[i] = r
    return [out[i] for i in range(len(out))]


def _progress(label: Optional[str], n: int, total: int, t0: float) -> None:
    if not label:
        return
    el = time.time() - t0
    eta = el / n * (total - n)
    print(f"[{label}] {n}/{total} done, {el:.0f}s elapsed, ~{eta:.0f}s left", file=sys.stderr, flush=True)
