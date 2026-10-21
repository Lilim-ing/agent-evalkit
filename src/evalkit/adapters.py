"""Adapters: how evalkit talks to an agent under test.

Any callable returning a string, a dict, or an AgentResponse works. HTTP and CLI
adapters exist so that the same suite can gate a local function and a deployed
service.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import urllib.request
from typing import Any, Callable

from .schema import AgentResponse


def normalize(raw: Any) -> AgentResponse:
    if isinstance(raw, AgentResponse):
        return raw
    if isinstance(raw, str):
        return AgentResponse(output=raw)
    if isinstance(raw, dict):
        if "output" in raw:
            return AgentResponse(**raw)
        return AgentResponse(output=json.dumps(raw, ensure_ascii=False), metadata=raw)
    raise TypeError(f"unsupported adapter return type: {type(raw).__name__}")


class FunctionAdapter:
    def __init__(self, fn: Callable[[str], Any], name: str | None = None) -> None:
        self.fn = fn
        self.name = name or getattr(fn, "__name__", "function")

    def __call__(self, text: str) -> AgentResponse:
        return normalize(self.fn(text))


class HttpAdapter:
    def __init__(self, url: str, timeout_s: float = 30.0, name: str | None = None) -> None:
        self.url = url
        self.timeout_s = timeout_s
        self.name = name or f"http:{url}"

    def __call__(self, text: str) -> AgentResponse:
        body = json.dumps({"input": text, "question": text}).encode("utf-8")
        request = urllib.request.Request(
            self.url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(request, timeout=self.timeout_s) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        return normalize(payload)


class CliAdapter:
    def __init__(self, command: str, timeout_s: float = 60.0, name: str | None = None) -> None:
        self.argv = shlex.split(command)
        self.timeout_s = timeout_s
        self.name = name or f"cli:{self.argv[0]}"

    def __call__(self, text: str) -> AgentResponse:
        completed = subprocess.run(  # noqa: S603
            self.argv,
            input=text,
            capture_output=True,
            text=True,
            timeout=self.timeout_s,
        )
        output = completed.stdout.strip()
        if completed.returncode != 0 and not output:
            raise RuntimeError(f"adapter exited {completed.returncode}: {completed.stderr[:300]}")
        return AgentResponse(output=output)


def load_adapter(spec: str) -> FunctionAdapter:
    """Load `module:function` as an adapter."""
    module_name, _, func_name = spec.partition(":")
    if not func_name:
        raise ValueError("adapter spec must look like 'module:function'")
    module = __import__(module_name, fromlist=[func_name])
    fn = getattr(module, func_name)
    return FunctionAdapter(fn, name=spec)
