"""Policies for ``run_tool_episode``.

* ``AnthropicPolicy``  Claude through the Messages API (manual tool loop).
* ``HFChatPolicy``     a local Hugging Face chat model with a tool-calling chat
                        template (Qwen-style ``<tool_call>{json}</tool_call>``).
* ``ScriptedPolicy``   deterministic baselines (reference oracle, do-nothing),
                        used to test the harness itself.

Every policy implements ``act``, ``assistant_message``, ``tool_result_messages``
and ``user_nudge`` so the runner stays provider-agnostic.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .runner import AgentTurn, ToolCall

# $ per million tokens: (input, output, cache read, cache write 5-min)
PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    "claude-fable-5-1": (10.00, 50.00, 0.25, 12.50),
}


def usage_cost(model: str, usage: Dict[str, int]) -> float:
    p = PRICES.get(model)
    if not p:
        return float("nan")
    return (usage.get("input_tokens", 0) * p[0] + usage.get("output_tokens", 0) * p[1]
            + usage.get("cache_read_input_tokens", 0) * p[2]
            + usage.get("cache_creation_input_tokens", 0) * p[3]) / 1e6


def api_key_source() -> Tuple[Optional[str], str]:
    """(key, where it came from). Order: this process's environment, then the Windows
    *user* environment (HKCU), then the *machine* environment (HKLM). The registry is
    read directly so a variable set after this shell started is still found."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key, "process environment"
    try:
        import winreg

        for hive, path, label in (
            (winreg.HKEY_CURRENT_USER, r"Environment", "Windows user environment"),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
             "Windows machine environment"),
        ):
            try:
                with winreg.OpenKey(hive, path) as k:
                    val = winreg.QueryValueEx(k, "ANTHROPIC_API_KEY")[0]
                    if val:
                        return val, label
            except OSError:
                continue
    except ImportError:
        pass
    return None, "not found"


def _api_key() -> Optional[str]:
    return api_key_source()[0]


class AnthropicPolicy:
    def __init__(self, model: str = "claude-opus-5-5", effort: str = "high", max_tokens: int = 16000,
                 fallback: bool = False):
        import anthropic

        self.client = anthropic.Anthropic(api_key=_api_key())
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.fallback = fallback

    def act(self, system: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> AgentTurn:
        from ..tools import anthropic_tools

        kwargs = dict(model=self.model, max_tokens=self.max_tokens, system=system, tools=anthropic_tools(),
                      messages=messages, cache_control={"type": "ephemeral"},
                      output_config={"effort": self.effort})
        if self.fallback:
            resp = self.client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                                    fallbacks="default", **kwargs)
        else:
            resp = self.client.messages.create(**kwargs)
        u = resp.usage
        usage = {
            "input_tokens": u.input_tokens or 0,
            "output_tokens": u.output_tokens or 0,
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
            "requests": 1,
        }
        if any(getattr(e, "type", "") == "fallback_message" for e in (getattr(u, "iterations", None) or [])):
            usage["fallback_turns"] = 1
        if resp.stop_reason == "refusal":
            usage["refusals"] = 1
        if resp.stop_reason == "max_tokens":
            usage["max_tokens_stops"] = 1
        text = "".join(b.text for b in resp.content if b.type == "text")
        calls = [ToolCall(b.id, b.name, dict(b.input)) for b in resp.content if b.type == "tool_use"]
        return AgentTurn(text=text, tool_calls=calls, raw=resp.content, usage=usage)

    def assistant_message(self, turn: AgentTurn) -> Dict[str, Any]:
        return {"role": "assistant", "content": turn.raw}  # verbatim, thinking blocks included

    def tool_result_messages(self, results) -> List[Dict[str, Any]]:
        return [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": c.id, "content": out,
             **({"is_error": True} if out.startswith("error") else {})}
            for c, out in results]}]

    def user_nudge(self) -> Dict[str, Any]:
        return {"role": "user", "content": "Continue with the tools. When the workbook is finished, call submit."}


_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


class HFChatPolicy:
    """Local chat model with a tool-calling chat template (tested with Qwen2.5/Qwen3)."""

    def __init__(self, model_name: str, max_new_tokens: int = 1024, temperature: float = 0.0,
                 device: str = "cuda", dtype: str = "bfloat16", model=None, tokenizer=None,
                 enable_thinking: bool = False):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tok = tokenizer or AutoTokenizer.from_pretrained(model_name)
        self.model = model or AutoModelForCausalLM.from_pretrained(
            model_name, dtype=getattr(torch, dtype), device_map=device)
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.enable_thinking = enable_thinking
        self.model_name = model_name

    def _render(self, system, messages, tools):
        from ..tools import openai_tools

        msgs = [{"role": "system", "content": system}] + messages
        kw = {"enable_thinking": self.enable_thinking} if "qwen3" in self.model_name.lower() else {}
        return self.tok.apply_chat_template(msgs, tools=openai_tools(), add_generation_prompt=True,
                                            tokenize=False, **kw)

    def act(self, system, messages, tools) -> AgentTurn:
        import torch

        prompt = self._render(system, messages, tools)
        ids = self.tok(prompt, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            out = self.model.generate(
                **ids, max_new_tokens=self.max_new_tokens, do_sample=self.temperature > 0,
                temperature=self.temperature if self.temperature > 0 else None, top_p=None, top_k=None,
                pad_token_id=self.tok.eos_token_id)
        gen = self.tok.decode(out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True)
        calls = []
        for m in _TOOL_CALL_RE.finditer(gen):
            try:
                obj = json.loads(m.group(1))
                calls.append(ToolCall(str(uuid.uuid4())[:8], obj.get("name", ""), obj.get("arguments", {}) or {}))
            except json.JSONDecodeError:
                calls.append(ToolCall(str(uuid.uuid4())[:8], "_invalid", {}))
        usage = {"input_tokens": int(ids["input_ids"].shape[1]),
                 "output_tokens": int(out.shape[1] - ids["input_ids"].shape[1]), "requests": 1}
        return AgentTurn(text=gen, tool_calls=calls, raw=gen, usage=usage)

    def assistant_message(self, turn: AgentTurn):
        calls = [{"type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                 for c in turn.tool_calls]
        text = _TOOL_CALL_RE.sub("", turn.text).strip()
        msg = {"role": "assistant", "content": text}
        if calls:
            msg["tool_calls"] = calls
        return msg

    def tool_result_messages(self, results):
        return [{"role": "tool", "name": c.name, "content": out} for c, out in results]

    def user_nudge(self):
        return {"role": "user", "content": "Continue with the tools. When the workbook is finished, call submit."}


class ScriptedPolicy:
    """Deterministic baselines that exercise the harness end to end.

    ``mode="reference"`` writes the hidden reference formulas (an oracle upper
    bound: it must score 1.0); ``mode="noop"`` submits immediately.
    """

    def __init__(self, mode: str = "reference", task_id: str = ""):
        self.mode = mode
        self.task_id = task_id
        self._chunks = None

    def act(self, system, messages, tools) -> AgentTurn:
        if self.mode == "noop":
            return AgentTurn(tool_calls=[ToolCall("s", "submit", {})])
        if self._chunks is None:
            from ..engine.refs import addr
            from ..tasks import make_task

            t = make_task(self.task_id)
            # the targets plus every reference cell that is empty in the task (for
            # free-layout builds that is the whole model the Outputs link to)
            keys = sorted(set(t.target_keys) | {k for k in t.reference.snapshot() if t.initial.raw(k) is None})
            edits = [{"cell": f"{t.reference.sheet_name(k[0])}!{addr(k[1], k[2])}", "content": t.reference.raw(k)}
                     for k in keys]
            self._chunks = [edits[i:i + 300] for i in range(0, len(edits), 300)]  # tool limit is 400
        if self._chunks:
            return AgentTurn(tool_calls=[ToolCall("w", "write_cells", {"edits": self._chunks.pop(0)})])
        return AgentTurn(tool_calls=[ToolCall("s", "submit", {})])

    def assistant_message(self, turn):
        return {"role": "assistant", "content": ""}

    def tool_result_messages(self, results):
        return [{"role": "user", "content": out} for _, out in results]

    def user_nudge(self):
        return {"role": "user", "content": "continue"}
