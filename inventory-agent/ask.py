"""Ask the inventory agent one question from the command line.

    python ask.py "What are we running low on?"
"""

import sys

from inventory_agent.agent import build_agent

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "What are we running low on?"
    result = build_agent()(question)
    print(str(result).strip())
