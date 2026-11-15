---
name: pso-opportunity-research
description: >-
  Run or customize the V3.0 Commercial White-Space Grounding & AI-Era HW/SW Co-Design Discovery Workflow inside power_semiconductor_opportunities/. Supports standalone LangGraph CLI (`pso-research`) and native Antigravity `run_workflow` 7-stage funnel orchestration across China-first and Global markets (3-5y and 5-10y horizons).
---

# Power & Semiconductor Online Testing Instrumentation Workflow Skill (V3.0)

## 1. Execution Options inside Antigravity IDE

### Mode 1 (Recommended inside Antigravity IDE): Antigravity Built-in Frontier LLM (`run_workflow` on `pro`)
Uses **Antigravity's built-in frontier LLMs (`model="pro"`)** across the 7-stage V3 funnel (Stage 0 Macro Recon + Dual Pain-Point & Vendor Queries, Stage 1 Parallel Dual-Channel Search & Commercial/AI Co-Design Miners, Stage 2 Deterministic Range PALMs + White-Space Calibration + Elimination Funnel, Stage 3 V3 STORM Buyer Panel, Stage 4 Elo Tournament, Stage 5 5-Volume Grounded Synthesis, Stage 6 Critic Reflection + Corrective RAG, Stage 7 Stage-Gate Judge), paired with deterministic Python CLI bridges (`recon-search`, `track-search`, `screen-candidates`, `gap-search`, `finalize-v3`) for **paid Metaso/Serper AI Search (`.env.ai_search`)** and **PALMs 3-Scenario ROI/NPV/IRR math**.

Invoke `run_workflow` with:
- `ScriptPath`: `/Users/john/Desktop/agentic_learning/power_semiconductor_opportunities/ide_workflows/antigravity_run_workflow.py`
- `Args`: `{"sector": "all", "profile": "flagship", "output_dir": "outputs/v3_commercial_ai_grounded_2026_2036", "vault_db": "data/evidence_vault_v3.db", "model": "pro", "hitl": false}`
- `Cwd`: `/Users/john/Desktop/agentic_learning/power_semiconductor_opportunities`

### Mode 2 (Standalone / Headless CLI Alternative): DashScope External LLMs (`.env.llm`)
For automated CI/terminal runs outside Antigravity IDE using DashScope (`qwen3.8-flash` / `qwen3.8-max` / `deepseek-v4-pro`):
```bash
cd /Users/john/Desktop/agentic_learning/power_semiconductor_opportunities
/Users/john/.local/bin/uv run pso-research verify-env
/Users/john/.local/bin/uv run pso-research run --sector all --profile flagship --output-dir outputs/v3_commercial_ai_grounded_2026_2036
```

## 2. Customization Hooks
- **Search Tokens**: Stored safely in `.env.ai_search` (ignored by Git). Uses `METASO_API_KEY` (China-first) and `SERPER_API_KEY` (Global), with optional slots for `TAVILY_API_KEY`, `EXA_API_KEY`, `PERPLEXITY_API_KEY`, `FIRECRAWL_API_KEY`.
- **LLM Engine**: Inside IDE, `run_workflow` natively uses Antigravity `pro` (no DashScope calls needed). Standalone CLI routes via `.env.llm` (`qwen3.8-flash` / `qwen3.8-max` / `deepseek-v4-pro`).
- **Discovery Scope, White-Space Taxonomy & AI Co-Design (V3.0)**: Edit `config/discovery_scope.yaml` (`commercial_whitespace_taxonomy`, `ai_native_engineering_paradigms`, `sector_mandates`, `macro_recon_queries`, `sector_roi_guardrails`) and `config/research_contract.yaml` (`PSO-CONTRACT-2026-V3` funnel quotas and 42-month conservative payback cutoff).
- **Historical Archives**: V1.0 preserved read-only in `outputs/power_semiconductor_online_testing_2026_2036/` (`config/v1_legacy_seed_catalog.yaml`), and V2.0 preserved read-only in `outputs/v2_dynamic_discovery_2026_2036/` (`data/evidence_vault_v2.db`).
