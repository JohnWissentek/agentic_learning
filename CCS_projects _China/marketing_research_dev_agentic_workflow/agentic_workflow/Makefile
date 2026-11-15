.PHONY: install verify-env ingest-siggi test diagrams run-fast run-flagship

install:
	uv sync --python 3.12 --extra dev

verify-env:
	uv run vf-ccus-research verify-env

ingest-siggi:
	uv run vf-ccus-research ingest-siggi --vault-db data/vf_ccus_evidence_vault.db

test:
	uv run pytest -v

diagrams:
	uv run python scripts/generate_clean_topology_drawio.py

run-fast:
	uv run vf-ccus-research run --profile fast --sector all

run-flagship:
	uv run vf-ccus-research run --profile flagship --sector all
