# The agent runs here, not on the host: no shell tools, no host files, no internet.
# run.sh starts it read-only, as a non-root user, with no Linux capabilities,
# on a network that reaches only the MaintainOps API and the model server.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt && useradd --uid 10001 --no-create-home agent
COPY inventory_agent ./inventory_agent
COPY ask.py ./
COPY eval/run_eval.py ./eval/

USER agent
ENTRYPOINT ["python"]
CMD ["ask.py", "What are we running low on?"]
