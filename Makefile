# Setup dev environment
dev:
	uv sync

build:
	./sh/build-package.sh

lint:
	uv run flake8
