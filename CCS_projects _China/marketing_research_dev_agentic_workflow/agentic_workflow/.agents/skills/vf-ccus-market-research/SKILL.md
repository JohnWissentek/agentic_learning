---
name: vf-ccus-market-research
description: Execute, audit, or customize the V&F IMR-MS China CCS/CCUS Market Research & Dual-Track GTM Multi-Agent Workflow (`vf-ccus-workflow`). Use when refreshing China CCUS projects/regulations, recalculating [MKT-CALC] TAM/SAM/SOM or [ROI-CALC] payback, updating competitor battlecards, or running the full Stage 0-7 pipeline.
---

# V&F IMR-MS China CCS/CCUS Market Research Skill

## Operational Steps

1. **Verify Environment & Siggi Primary Corpus**:
   - Confirm working directory is `agentic_workflow/`.
   - Run `uv run vf-ccus-research verify-env` and ensure Metaso, Serper, DashScope, and `information_from_siggi/` files all report PASS.
2. **Run Offline Safety Tests First**:
   - Run `uv run pytest -v` to verify `[MKT-CALC]`, `[ROI-CALC]`, Siggi PDF/MD ingestion, secret leak prevention, and mock trajectory execution.
3. **Execute Pipeline**:
   - **Standalone LangGraph**: `uv run vf-ccus-research run --profile flagship`
   - **Antigravity Native Hybrid**: Execute `ide_workflows/antigravity_run_workflow.py` via `run_workflow` with `profile="flagship"` and `WaitMsBeforeAsync=10000`.
4. **Regenerate Vector Topology Diagrams**:
   - Run `uv run python scripts/generate_clean_topology_drawio.py` to export `.drawio`, `.svg`, and `.pdf` into `docs/` and `../research_outputs/`.
5. **Mandatory Grounding Rules**:
   - Never fabricate `[EV-*]` IDs or competitor models outside `EvidenceVault`.
   - Never alter deterministic `[MKT-CALC]` or `[ROI-CALC]` numbers in prose.
