.PHONY: help sync verify test collect run-fast run-flagship eval eval-v2 eval-v1

UV := /Users/john/.local/bin/uv

help:
	@echo "PSO Opportunity Discovery Agentic Workflow Targets (V4.0 Model-First + Deterministic Chassis):"
	@echo "  make sync         - 创建/同步 Python 3.12 独立虚拟环境"
	@echo "  make verify       - 验证 .env.ai_search (Metaso/Serper) 与 .env.llm (DashScope) 连通性"
	@echo "  make test         - 运行 pytest 全量红区契约、反证/组合评审、主表注入与轨迹自动化测试"
	@echo "  make collect      - [V1 Archive] 仅运行预设词表双引擎采集"
	@echo "  make run-fast     - V4.0 快速动态发现全流程演练 (outputs/fast_smoke)"
	@echo "  make run-flagship - 运行 V4.0 旗舰全流程 (outputs/v4_model_first_grounded_2026_2036)"
	@echo "  make eval         - 对 V4.0 outputs/v4_model_first_grounded_2026_2036 运行门禁审计"
	@echo "  make eval-v3      - 对 V3.0 历史归档 outputs/v3_commercial_ai_grounded_2026_2036 运行门禁打分"
	@echo "  make eval-v2      - 对 V2.0 历史归档 outputs/v2_dynamic_discovery_2026_2036 运行门禁打分"
	@echo "  make eval-v1      - 对 V1.0 历史归档 outputs/power_semiconductor_online_testing_2026_2036 运行门禁打分"

sync:
	$(UV) sync --python 3.12 --extra dev

verify:
	$(UV) run pso-research verify-env

test:
	$(UV) run pytest -v

collect:
	$(UV) run pso-research collect --sector all --num-results 6

run-fast:
	$(UV) run pso-research run --sector all --profile fast --output-dir outputs/fast_smoke

run-flagship:
	$(UV) run pso-research run --sector all --profile flagship --output-dir outputs/v4_model_first_grounded_2026_2036

eval:
	$(UV) run pso-research evaluate outputs/v4_model_first_grounded_2026_2036

eval-v3:
	$(UV) run pso-research evaluate outputs/v3_commercial_ai_grounded_2026_2036

eval-v2:
	$(UV) run pso-research evaluate outputs/v2_dynamic_discovery_2026_2036

eval-v1:
	$(UV) run pso-research evaluate outputs/power_semiconductor_online_testing_2026_2036
