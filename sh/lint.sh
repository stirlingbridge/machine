#!/bin/bash

if [[ "$1" == "--fix" ]]; then
  LINE_LENGTH=$(grep 'max-line-length' .flake8 | cut -d'=' -f2 | awk '{ print $1 }')
  uv run black -l ${LINE_LENGTH:-132} machine/
fi

uv run flake8
