"""FastAPI app exposing ``SpreadsheetEnvironment`` over HTTP/WebSocket (OpenEnv).

Run locally::

    python -m spreadsheet_env.server.app --port 8000

Configuration via environment variables (all optional):

    SSE_FAMILIES      comma-separated families (default: all) e.g. "build,repair"
    SSE_DIFFICULTIES  comma-separated levels (default: all)
    SSE_SPLIT         "train" | "test" seed range (default: train)
    SSE_REWARD_MODE   "binary" | "shaped" (default: binary)
    SSE_MAX_SESSIONS  concurrent sessions (default: 16)
"""

from __future__ import annotations

import os

from openenv.core.env_server.http_server import create_app
from openenv.core.env_server.mcp_types import CallToolAction

from spreadsheet_env.environment import SpreadsheetEnvironment
from spreadsheet_env.models import SpreadsheetObservation


def _cfg_list(name):
    raw = os.environ.get(name, "").strip()
    return [x.strip() for x in raw.split(",") if x.strip()] or None


def make_env() -> SpreadsheetEnvironment:
    diffs = _cfg_list("SSE_DIFFICULTIES")
    return SpreadsheetEnvironment(
        families=_cfg_list("SSE_FAMILIES"),
        difficulties=[int(d) for d in diffs] if diffs else None,
        split=os.environ.get("SSE_SPLIT", "train"),
        reward_mode=os.environ.get("SSE_REWARD_MODE", "binary"),
    )


app = create_app(
    make_env,
    CallToolAction,
    SpreadsheetObservation,
    env_name="spreadsheet-financial-model",
    max_concurrent_envs=int(os.environ.get("SSE_MAX_SESSIONS", "16")),
)


def main() -> None:
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Spreadsheet financial-model environment server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--workers", type=int, default=1,
                        help="uvicorn worker processes; grading is CPU-bound Python, so use several for "
                             "many concurrent RL sessions (each WebSocket session stays in one process)")
    args = parser.parse_args()
    if args.workers > 1:
        uvicorn.run("spreadsheet_env.server.app:app", host=args.host, port=args.port, workers=args.workers)
    else:
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
