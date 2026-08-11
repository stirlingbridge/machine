#!/bin/bash

# A bash script exits with the status of its last command, so without this the
# format check's result was discarded and only `ruff check` decided the outcome.
# Both checks still run to completion on failure, so one invocation reports all
# the work that needs doing rather than stopping at the first problem.
set -uo pipefail

status=0

if [[ "${1:-}" == "--fix" ]]; then
  uv run ruff format machine/ || status=1
  uv run ruff check --fix machine/ || status=1
else
  uv run ruff format --check machine/ || status=1
  uv run ruff check machine/ || status=1
fi

exit "${status}"
