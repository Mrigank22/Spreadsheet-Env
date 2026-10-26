"""End-to-end check of a running server through OpenEnv's MCP client (WebSocket).

    python -m spreadsheet_env.server.app --port 8765 &
    python scripts/remote_smoke.py --url http://localhost:8765

Plays one episode with the reference solution (must earn reward 1.0) and one
do-nothing episode (must earn 0.0), entirely over the network protocol.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openenv.core.env_server.mcp_types import CallToolAction  # noqa: E402
from openenv.core.mcp_client import MCPToolClient  # noqa: E402

from spreadsheet_env.engine.refs import addr  # noqa: E402
from spreadsheet_env.tasks import make_task  # noqa: E402


async def episode(url: str, task_id: str, honest: bool):
    async with MCPToolClient(base_url=url) as env:
        r = await env.reset(task_id=task_id)
        tools = [t.name for t in await env.list_tools()]
        if honest:
            t = make_task(task_id)
            edits = [{"cell": f"{t.reference.sheet_name(k[0])}!{addr(k[1], k[2])}", "content": t.reference.raw(k)}
                     for k in t.target_keys]
            await env.call_tool("write_cells", edits=edits)
        res = await env.step(CallToolAction(tool_name="submit", arguments={}))
        return tools, res.reward, res.done, (res.observation.metadata or {}).get("components")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8765")
    ap.add_argument("--task", default="build-d2-s5")
    args = ap.parse_args()
    tools, rew, done, comps = asyncio.run(episode(args.url, args.task, True))
    print("tools:", tools)
    print(f"honest episode: reward={rew} done={done} components={comps}")
    _, rew0, done0, comps0 = asyncio.run(episode(args.url, args.task, False))
    print(f"do-nothing episode: reward={rew0} done={done0} components={comps0}")
    assert rew == 1.0 and done and rew0 == 0.0 and done0, "remote smoke test failed"
    print("remote smoke test passed")


if __name__ == "__main__":
    main()
