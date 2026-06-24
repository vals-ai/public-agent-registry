#!/bin/bash
# $1 = problem_statement_path (unused - fabv2 uses its bundled dataset)
# $2 = task_id
# $3 = model

TASK_ID="$2"
MODEL="$3"

fabv2 run \
  --model "$MODEL" \
  --run-id valkyrie \
  --skip-eval \
  --dataset-file /app/data/dataset.json \
  --results-dir /app/results \
  "$TASK_ID"
