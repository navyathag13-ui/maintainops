#!/bin/bash
set -u

mkdir -p /logs/verifier

cd /app
python -m pytest /tests/test_outputs.py -rA --tb=short

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
