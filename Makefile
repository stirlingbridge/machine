# Setup dev environment
dev:
	@echo Please run this command: source scripts/dev-setup.sh

build:
	./scripts/build-package.sh

lint:
	flake8

