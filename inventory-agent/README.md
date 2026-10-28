# Inventory Agent (Strands Agents)

A tool-calling agent built with [Strands Agents](https://strandsagents.com)
that answers a shift supervisor's questions ("what are we running low on?",
"how many drill bits do we have?") from live MaintainOps data.

- **3 read-only tools** over the MaintainOps REST API: low-stock parts,
  overdue equipment and part lookup. The agent cannot change stock; writes
  stay in the app and the voice agent, where a person confirms them.
- **Swappable model provider**: `AGENT_PROVIDER=ollama` (default, runs a local
  model for free) or `AGENT_PROVIDER=bedrock` (Amazon Bedrock through the same
  Strands agent; needs AWS credentials). The results below were measured on
  Ollama only.
- **Tool descriptions written for the model**: each says what it returns and
  when to use it, since that text is what the model reads when it picks a tool.

## What the evaluation showed

`eval/run_eval.py` asks 7 questions and computes the expected answers from the
live API at run time, so it stays correct if the data changes. A case passes
only if the agent called the right tool *and* the answer contains the facts the
tool returned, or, for the two trick questions (a part that doesn't exist and a
request to change stock), declines instead of inventing.

Measured on `qwen2.5:3b` (local CPU, Docker), one fresh agent per question:

| Prompt | Passed | Right tool | Median latency | Avg tokens / question |
|---|---|---|---|---|
| v1: one generic sentence | 6 / 7 | 7 / 7 | 9.6 s | 879 |
| **v2: explicit rules (chosen)** | **7 / 7** | 7 / 7 | 10.6 s | 977 |

v1 picked the right tool every time but, asked to "set the Drill Bits quantity
to 100", it did not clearly decline. v2 adds four rules (always call a tool,
say so when nothing is found, quote the tool's numbers, and state that the
agent can only read) and passes all 7 for about 11% more tokens. That trade is
worth it: a supervisor should never think a stock change went through when it
didn't.

The first question of each run includes loading the model (the v1 run took
208 s on that question); latencies above are medians so that warm-up does not
skew them. An earlier manual check on `qwen2.5:7b` with the v2 prompt missed
some low-stock parts, which is why the eval checks every part name rather than
just "mentions some parts".

## Running it

```bash
# MaintainOps API (from the repo root) and a local model
docker compose up -d db backend
docker run -d -p 11434:11434 -v ~/.ollama:/root/.ollama ollama/ollama
docker exec <container> ollama pull qwen2.5:3b

uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt

OLLAMA_MODEL=qwen2.5:3b .venv/bin/python ask.py "What are we running low on?"
.venv/bin/python eval/run_eval.py --model qwen2.5:3b --prompt v1 v2
.venv/bin/python -m pytest -q   # tool tests, no API or model needed
```

## Layout

- `inventory_agent/tools.py`: the 3 `@tool` functions and their descriptions
- `inventory_agent/agent.py`: model provider, system prompts v1 and v2, agent factory
- `eval/run_eval.py`: live-data evaluation; results in `eval/results/`
- `tests/test_tools.py`: 7 tests with the API mocked
