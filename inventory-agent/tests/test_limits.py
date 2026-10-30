"""Run limits against a scripted model, so they run without Ollama or MaintainOps.

The fake model replays a fixed list of turns: each turn is either a tool call
or a final text answer, in the same stream format Strands models produce."""

import json

import pytest
from strands.models.model import Model

from inventory_agent import tools
from inventory_agent.agent import build_agent
from inventory_agent.limits import RunLimits

PARTS = [{"name": "Oil Filters", "sku": "OIL-170", "quantity_on_hand": 2, "reorder_threshold": 4}]


@pytest.fixture(autouse=True)
def fake_api(monkeypatch):
    calls = []

    def get(path):
        calls.append(path)
        return {"/parts": PARTS, "/alerts/low-stock": [], "/alerts/overdue-maintenance": []}[path]

    monkeypatch.setattr(tools, "_get", get)
    return calls


class ScriptedModel(Model):
    def __init__(self, turns):
        self.turns = list(turns)
        self.calls = 0

    def update_config(self, **kwargs):
        pass

    def get_config(self):
        return {}

    async def structured_output(self, *args, **kwargs):
        raise NotImplementedError
        yield

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        turn = self.turns[min(self.calls, len(self.turns) - 1)]
        self.calls += 1
        yield {"messageStart": {"role": "assistant"}}
        if "tool" in turn:
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": f"t{self.calls}", "name": turn["tool"]}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(turn.get("input", {}))}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockDelta": {"delta": {"text": turn["text"]}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}


def ask(turns, **limit_kwargs):
    model = ScriptedModel(turns)
    agent = build_agent(model=model, limits=RunLimits(**limit_kwargs))
    answer = str(agent("How many oil filters do we have?")).strip()
    return answer, agent.limits.report, model


def test_normal_run_completes_and_is_counted(fake_api):
    answer, report, _ = ask([{"tool": "find_part", "input": {"query": "oil"}}, {"text": "We have 2 Oil Filters."}])
    assert answer == "We have 2 Oil Filters."
    assert report.stop_reason == "completed" and report.tool_calls == 1 and report.model_calls == 2
    assert report.tools_used == ["find_part"] and fake_api == ["/parts"]


def test_tool_budget_stops_the_run(fake_api):
    turns = [{"tool": "find_part", "input": {"query": q}} for q in ("a", "b", "c", "d")] + [{"text": "done"}]
    answer, report, _ = ask(turns, max_tool_calls=2)
    assert report.stop_reason == "tool_budget" and report.tool_calls == 2
    assert "limit of 2 tool calls" in answer
    assert len(fake_api) == 2  # the third call never reached the API


def test_repeated_call_is_refused_then_loop_stops(fake_api):
    same = {"tool": "find_part", "input": {"query": "oil"}}
    answer, report, _ = ask([same, same, same, {"text": "never reached"}])
    assert report.stop_reason == "loop" and report.repeats_refused == 2
    assert fake_api == ["/parts"]  # only the first identical call ran
    assert "repeating the same tool call" in answer


def test_one_repeat_gets_a_nudge_and_the_run_can_still_finish(fake_api):
    same = {"tool": "find_part", "input": {"query": "oil"}}
    answer, report, _ = ask([same, same, {"text": "We have 2 Oil Filters."}])
    assert answer == "We have 2 Oil Filters."
    assert report.stop_reason == "completed" and report.repeats_refused == 1 and report.tool_calls == 1


def test_model_budget_stops_the_run(fake_api):
    turns = [{"tool": "find_part", "input": {"query": q}} for q in "abcdef"]
    answer, report, model = ask(turns, max_model_calls=3, max_tool_calls=10)
    assert report.stop_reason == "model_budget" and report.model_calls == 3 and model.calls == 3
    assert "limit of 3 model calls" in answer


def test_time_limit_stops_before_the_next_call(fake_api):
    now = [0.0]

    def clock():
        now[0] += 40.0  # each check is 40 "seconds" later
        return now[0]

    turns = [{"tool": "find_part", "input": {"query": "oil"}}, {"text": "late answer"}]
    answer, report, _ = ask(turns, max_seconds=60, clock=clock)
    assert report.stop_reason == "time_limit"
    assert "time limit" in answer


def test_limits_reset_between_questions(fake_api):
    model = ScriptedModel([{"tool": "find_part", "input": {"query": "oil"}}, {"text": "2 left."}])
    agent = build_agent(model=model, limits=RunLimits())
    agent("first question")
    model.calls = 0
    agent("second question")
    assert agent.limits.report.tool_calls == 1 and agent.limits.report.stop_reason == "completed"
