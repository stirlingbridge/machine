# Setup dev environment
dev:
	@echo Please run this command: source sh/dev-setup.sh

build:
	./sh/build-package.sh

lint:
	flake8
