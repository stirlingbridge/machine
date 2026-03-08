# Setup dev environment
dev:
	uv sync

build:
	./sh/build-package.sh

test:
	uv run pytest tests/ -v

lint:
	uv run flake8
