# CLAUDE.md

## Project Overview

CLI tool (`machine`) for creating and managing VMs on DigitalOcean. Built with Python and Click, packaged as a single-file executable via shiv.

- **Org**: Stirlingbridge (`github.com/stirlingbridge/machine`)
- **License**: AGPL-3.0-only
- **Python**: >=3.8 (CI builds on 3.8)

## Tech Stack

- **CLI framework**: Click 8.1.7
- **Cloud provider**: python-digitalocean 1.17.0
- **Config**: ruamel.yaml (reads `~/.machine/config.yml`)
- **Build tooling**: uv (dependency management), hatchling (build backend), shiv (zipapp packaging)

## Project Structure

```
machine/             # Main package
  main.py            # Click group entry point
  config.py          # Config file loading
  di.py              # Dependency injection / globals
  factory.py         # VM creation factory
  cloud_config.py    # Cloud-init config generation
  subcommands/       # Click subcommands (create, destroy, list, status, etc.)
sh/                  # Shell scripts (build, lint, dev-setup)
pyproject.toml       # Project metadata and dependencies
```

## Development Commands

```bash
uv sync                    # Install dependencies (creates .venv)
uv run machine --help      # Run CLI in development
uv run flake8              # Lint
./sh/lint.sh --fix         # Auto-format with black, then lint
./sh/build-package.sh      # Build shiv executable to build/machine
make dev                   # Alias for uv sync
make build                 # Alias for build-package.sh
make lint                  # Alias for uv run flake8
```

## Code Style

- **Formatter**: black (line length 132)
- **Linter**: flake8 (max line length 132, max complexity 25, E203 ignored)
- Config in `.flake8`

## CI/CD

GitHub Actions workflow (`.github/workflows/build-release.yml`) builds a shiv package and publishes it as a GitHub release on push to `main`.
