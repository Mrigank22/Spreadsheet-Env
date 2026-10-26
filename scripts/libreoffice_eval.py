"""Recalculate .xlsx files with LibreOffice (headless, in Docker) and read values back.

Build the image once:  docker build -t sse-libreoffice docker/libreoffice
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple

IMAGE = "sse-libreoffice"


def evaluate_many(paths: List[str], batch: int = 200) -> List[Optional[Dict[Tuple[str, int, int], object]]]:
    import openpyxl

    work = tempfile.mkdtemp(prefix="sse_lo_")
    try:
        inp, out = os.path.join(work, "in"), os.path.join(work, "out")
        os.makedirs(inp)
        os.makedirs(out)
        names = []
        for i, p in enumerate(paths):
            n = f"f{i:05d}.xlsx"
            shutil.copy(p, os.path.join(inp, n))
            names.append(n)
        for s in range(0, len(names), batch):
            chunk = " ".join(f"/data/in/{n}" for n in names[s:s + batch])
            cmd = ["docker", "run", "--rm", "-v", f"{work}:/data", IMAGE, "sh", "-c",
                   "cp -r /lo_profile /tmp/lo && soffice --headless --norestore "
                   "-env:UserInstallation=file:///tmp/lo --convert-to xlsx --outdir /data/out " + chunk
                   + " >/dev/null 2>&1"]
            subprocess.run(cmd, check=False, timeout=3600)
        results = []
        for n in names:
            fp = os.path.join(out, n)
            if not os.path.exists(fp):
                results.append(None)
                continue
            wb = openpyxl.load_workbook(fp, data_only=True)
            vals = {}
            for ws in wb.worksheets:
                for row in ws.iter_rows():
                    for c in row:
                        if c.value is not None:
                            vals[(ws.title, c.row, c.column)] = c.value
            results.append(vals)
        return results
    finally:
        shutil.rmtree(work, ignore_errors=True)
