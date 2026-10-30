"""Builds the Strands agent. The model provider is a setting, so the same
agent and tools run on a local Ollama model or on Amazon Bedrock."""

import os

from strands import Agent

from .limits import RunLimits
from .tools import ALL_TOOLS

# v2 is the prompt the evaluation picked; v1 is kept so the comparison in
# eval/run_eval.py can be rerun. See README "What the evaluation showed".
SYSTEM_PROMPTS = {
    "v1": "You are a helpful maintenance assistant. Answer questions about inventory and equipment.",
    "v2": (
        "You answer a maintenance supervisor's questions about parts and equipment.\n"
        "- Always call a tool to get current numbers; never guess a quantity or a name.\n"
        "- If a tool returns nothing, say so plainly (for example, that no such part exists).\n"
        "- Answer in one or two short sentences and include the exact numbers the tool returned.\n"
        "- You can only read data. If asked to change stock or log work, say that has to be done in MaintainOps."
    ),
}


def build_model(provider: str | None = None, model_id: str | None = None):
    provider = (provider or os.getenv("AGENT_PROVIDER", "ollama")).lower()
    if provider == "bedrock":
        from strands.models.bedrock import BedrockModel

        return BedrockModel(
            model_id=model_id or os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0"),
            temperature=0,
        )
    from strands.models.ollama import OllamaModel

    return OllamaModel(
        os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        model_id=model_id or os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        temperature=0,
    )


def build_agent(prompt_version: str = "v2", provider: str | None = None, model_id: str | None = None,
                limits: RunLimits | None = None, model=None) -> Agent:
    # Every agent gets run limits (tool budget, loop guard, model budget, time limit);
    # read them back from agent.limits.report after a question.
    limits = limits or RunLimits(
        max_tool_calls=int(os.getenv("AGENT_MAX_TOOL_CALLS", "6")),
        max_model_calls=int(os.getenv("AGENT_MAX_MODEL_CALLS", "8")),
        max_seconds=float(os.getenv("AGENT_MAX_SECONDS", "60")),
    )
    agent = Agent(
        model=model or build_model(provider, model_id),
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPTS[prompt_version],
        hooks=[limits],
        callback_handler=None,  # quiet: the CLI and eval print what they need
    )
    agent.limits = limits
    return agent
