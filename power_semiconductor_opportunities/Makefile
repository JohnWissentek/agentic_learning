.PHONY: help sync verify test collect run-fast run-flagship eval

UV := /Users/john/.local/bin/uv

help:
	@echo "PSO Opportunity Discovery Agentic Workflow Targets:"
	@echo "  make sync         - 创建/同步 Python 3.12 独立虚拟环境"
	@echo "  make verify       - 验证 .env.ai_search (Metaso/Serper) 与 .env.llm (DashScope) 连通性"
	@echo "  make test         - 运行 pytest 契约、ROI数学与图轨迹三层自动化测试"
	@echo "  make collect      - 仅运行双引擎采集写入 data/evidence_vault.db"
	@echo "  make run-fast     - 快速全流程演练 (outputs/fast_smoke)"
	@echo "  make run-flagship - 运行旗舰全流程深度研究 (outputs/power_semiconductor_online_testing_2026_2036)"
	@echo "  make eval         - 对 outputs/power_semiconductor_online_testing_2026_2036 运行独立 Stage-Gate 门禁打分"

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
	$(UV) run pso-research run --sector all --profile flagship --output-dir outputs/power_semiconductor_online_testing_2026_2036

eval:
	$(UV) run pso-research evaluate outputs/power_semiconductor_online_testing_2026_2036
