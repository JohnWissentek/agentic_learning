---
name: pso-opportunity-research
description: >-
  Run or customize the Power & Semiconductor Online Testing Instrumentation Opportunity Discovery Agentic Workflow inside power_semiconductor_opportunities/. Supports standalone LangGraph CLI (`pso-research`) and native Antigravity `run_workflow` orchestration across China-first and Global markets (3-5y and 5-10y horizons).
---

# Power & Semiconductor Online Testing Instrumentation Workflow Skill

## 1. Execution Options inside Antigravity IDE

### Mode 1 (Recommended inside Antigravity IDE): Antigravity Built-in Frontier LLM (`run_workflow` on `pro`)
Uses **Antigravity's built-in frontier LLMs (`model="pro"`)** for all cognitive stages (Step-Back Planning, 8-Track Research, 4-Persona STORM Interrogation, Elo Tournament, 5-Volume Grounded Synthesis, Critic Audit, Stage-Gate Judge), paired with deterministic Python CLI bridges (`prepare-context` & `finalize-native`) for **paid Metaso/Serper AI Search (`.env.ai_search`)** and **PALMs ROI/NPV/IRR math**.

Invoke `run_workflow` with:
- `ScriptPath`: `/Users/john/Desktop/agentic_learning/power_semiconductor_opportunities/ide_workflows/antigravity_run_workflow.py`
- `Args`: `{"sector": "all", "output_dir": "outputs/power_semiconductor_online_testing_2026_2036", "model": "pro"}`
- `Cwd`: `/Users/john/Desktop/agentic_learning/power_semiconductor_opportunities`

### Mode 2 (Standalone / Headless CLI Alternative): DashScope External LLMs (`.env.llm`)
For automated CI/terminal runs outside Antigravity IDE using DashScope (`qwen3.8-flash` / `qwen3.8-max` / `deepseek-v4-pro`):
```bash
cd /Users/john/Desktop/agentic_learning/power_semiconductor_opportunities
/Users/john/.local/bin/uv run pso-research verify-env
/Users/john/.local/bin/uv run pso-research run --sector all --profile flagship --output-dir outputs/power_semiconductor_online_testing_2026_2036
```

## 2. Customization Hooks
- **Search Tokens**: Stored safely in `.env.ai_search` (ignored by Git). Uses `METASO_API_KEY` (China-first) and `SERPER_API_KEY` (Global), with optional slots for `TAVILY_API_KEY`, `EXA_API_KEY`, `PERPLEXITY_API_KEY`, `FIRECRAWL_API_KEY`.
- **LLM Engine**: Inside IDE, `run_workflow` natively uses Antigravity `pro` (no DashScope calls needed). Standalone CLI routes via `.env.llm` (`qwen3.8-flash` / `qwen3.8-max` / `deepseek-v4-pro`).
- **Domain Taxonomy**: Edit `config/domain_taxonomy.yaml` to adjust tracks `P1-P4` / `S1-S4`, search queries, or baseline manufacturing ROI assumptions.
