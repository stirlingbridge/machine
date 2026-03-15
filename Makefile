# Setup dev environment
dev:
	uv sync

build:
	./sh/build-package.sh

test:
	uv run pytest tests/ -v

test-e2e:
	uv run pytest tests/test_e2e.py -v -m e2e

lint:
	uv run ruff check machine/
	uv run ruff format --check machine/
