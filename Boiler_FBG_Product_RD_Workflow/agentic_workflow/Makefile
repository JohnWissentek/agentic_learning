UV := /Users/john/.local/bin/uv

.PHONY: sync verify-env test run run-fast diagrams lint

sync:
	$(UV) sync --python 3.12 --extra dev

verify-env:
	$(UV) run bfbg-workflow verify-env

test:
	$(UV) run pytest -v

lint:
	$(UV) run ruff check src tests

run:
	$(UV) run bfbg-workflow run --profile flagship --output-dir ../output

run-fast:
	$(UV) run bfbg-workflow run --profile fast --output-dir ../output

diagrams:
	$(UV) run python scripts/generate_ipd_workflow_drawio.py
	$(UV) run python scripts/generate_system_interface_drawio.py
