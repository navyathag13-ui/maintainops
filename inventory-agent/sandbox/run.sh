#!/usr/bin/env bash
# Run the inventory agent in a locked-down container.
#
#   sandbox/run.sh ask.py "What are we running low on?"
#   sandbox/run.sh eval/run_eval.py --model qwen2.5:3b --prompt v2
#
# The container gets an --internal Docker network (no route to the internet)
# shared only with the MaintainOps backend and the Ollama container, a
# read-only filesystem, no Linux capabilities, a non-root user and caps on
# memory, CPU and process count. Only eval/results is writable.
set -euo pipefail

cd "$(dirname "$0")/.."
NET=${SANDBOX_NETWORK:-agent-sandbox}
BACKEND=${BACKEND_CONTAINER:-maintainops-backend-1}
OLLAMA=${OLLAMA_CONTAINER:-inventory-ollama}
IMAGE=inventory-agent-sandbox

docker build -q -t "$IMAGE" -f sandbox/Dockerfile . >/dev/null
docker network inspect "$NET" >/dev/null 2>&1 || docker network create --internal "$NET" >/dev/null
for c in "$BACKEND" "$OLLAMA"; do
  docker network connect "$NET" "$c" 2>/dev/null || true   # already connected is fine
done
mkdir -p eval/results

docker run --rm \
  --network "$NET" \
  --read-only --tmpfs /tmp:size=16m \
  --cap-drop ALL --security-opt no-new-privileges \
  --user 10001 \
  --memory 512m --cpus 1 --pids-limit 64 \
  -v "$PWD/eval/results:/app/eval/results" \
  -e MAINTAINOPS_API="http://$BACKEND:8000" \
  -e OLLAMA_HOST="http://$OLLAMA:11434" \
  -e OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:3b}" \
  -e AGENT_MAX_TOOL_CALLS="${AGENT_MAX_TOOL_CALLS:-6}" \
  -e AGENT_MAX_MODEL_CALLS="${AGENT_MAX_MODEL_CALLS:-8}" \
  -e AGENT_MAX_SECONDS="${AGENT_MAX_SECONDS:-60}" \
  "$IMAGE" "$@"
