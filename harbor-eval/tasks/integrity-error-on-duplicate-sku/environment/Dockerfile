FROM python:3.11-slim

WORKDIR /app

COPY app_src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app_src/app ./app

ENV PYTHONPATH=/app
