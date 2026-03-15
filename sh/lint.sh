#!/bin/bash

if [[ "$1" == "--fix" ]]; then
  uv run ruff format machine/
  uv run ruff check --fix machine/
else
  uv run ruff format --check machine/
  uv run ruff check machine/
fi
