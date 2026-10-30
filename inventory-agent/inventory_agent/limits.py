"""Run limits for the agent loop, as a Strands hook.

A read-only agent can still go wrong in expensive ways: call the same tool
over and over, keep asking the model for "one more look", or hang on a slow
model. These limits stop each of those and say why, so a run always ends
with an answer or a clear reason instead of burning time and tokens.

- Tool budget: at most `max_tool_calls` tool calls per question.
- Loop guard: an identical tool call (same tool, same arguments) is refused
  with a note to reuse the earlier result; a second refusal ends the run.
- Model budget: at most `max_model_calls` model calls per question.
- Time limit: no new model or tool call starts after `max_seconds`.

`report` holds what happened on the last question, for logs and the eval.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from strands.hooks import (
    BeforeInvocationEvent,
    BeforeModelCallEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)


@dataclass
class RunReport:
    tool_calls: int = 0
    model_calls: int = 0
    repeats_refused: int = 0
    stop_reason: str = "completed"
    tools_used: list[str] = field(default_factory=list)


class RunLimits(HookProvider):
    def __init__(self, max_tool_calls: int = 6, max_model_calls: int = 8, max_seconds: float = 60.0,
                 clock=time.monotonic):
        self.max_tool_calls = max_tool_calls
        self.max_model_calls = max_model_calls
        self.max_seconds = max_seconds
        self._clock = clock
        self._start = clock()
        self._seen: set[str] = set()
        self.report = RunReport()

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeInvocationEvent, self._on_start)
        registry.add_callback(BeforeModelCallEvent, self._on_model_call)
        registry.add_callback(BeforeToolCallEvent, self._on_tool_call)

    def _on_start(self, event: BeforeInvocationEvent) -> None:
        self._start = self._clock()
        self._seen.clear()
        self.report = RunReport()

    def _out_of_time(self) -> bool:
        return self._clock() - self._start > self.max_seconds

    def _stop(self, reason: str) -> str:
        self.report.stop_reason = reason
        return {
            "time_limit": f"Stopped: the {self.max_seconds:g}-second time limit was reached before an answer.",
            "model_budget": f"Stopped: the limit of {self.max_model_calls} model calls was reached before an answer.",
            "tool_budget": f"Stopped: the limit of {self.max_tool_calls} tool calls was reached before an answer.",
            "loop": "Stopped: the agent kept repeating the same tool call.",
        }[reason]

    def _on_model_call(self, event: BeforeModelCallEvent) -> None:
        if self.report.stop_reason != "completed":
            event.cancel = self._stop(self.report.stop_reason)
        elif self._out_of_time():
            event.cancel = self._stop("time_limit")
        elif self.report.model_calls >= self.max_model_calls:
            event.cancel = self._stop("model_budget")
        else:
            self.report.model_calls += 1

    def _on_tool_call(self, event: BeforeToolCallEvent) -> None:
        name = event.tool_use["name"]
        key = name + json.dumps(event.tool_use.get("input", {}), sort_keys=True)
        if self._out_of_time():
            event.cancel_tool = self._stop("time_limit")
            event.agent.cancel(message=event.cancel_tool, after_current_tools=True)
        elif self.report.tool_calls >= self.max_tool_calls:
            event.cancel_tool = self._stop("tool_budget")
            event.agent.cancel(message=event.cancel_tool, after_current_tools=True)
        elif key in self._seen:
            self.report.repeats_refused += 1
            if self.report.repeats_refused >= 2:
                event.cancel_tool = self._stop("loop")
                event.agent.cancel(message=event.cancel_tool, after_current_tools=True)
            else:
                event.cancel_tool = (f"You already called {name} with these arguments. "
                                     "Use that earlier result instead of calling it again.")
        else:
            self._seen.add(key)
            self.report.tool_calls += 1
            self.report.tools_used.append(name)
