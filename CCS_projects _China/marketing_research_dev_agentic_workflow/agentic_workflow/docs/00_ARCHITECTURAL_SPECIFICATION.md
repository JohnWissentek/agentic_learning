# 00 系统架构规范 (`00_ARCHITECTURAL_SPECIFICATION`)

## 1. 工程结构与双运行模式

本系统采用 **“确定性 Python 工具脊柱 + 多智能体认知层”** 分离设计：

- **认知与调度双模式**：
  - **Standalone 模式** (`src/vf_ccus_workflow/graph.py`)：基于 `langgraph.graph.StateGraph` + `MemorySaver`，将 DashScope (`qwen3.8-flash` / `qwen3.8-max` / `deepseek-v4-pro`) 绑定至结构化节点，适合全自动 CI/无人值守批处理。
  - **Antigravity Native Hybrid 模式** (`ide_workflows/antigravity_run_workflow.py`)：通过 `run_workflow` 在 IDE 原生高配模型上调度子智能体，同时通过 `vf-ccus-research` CLI 强制由 Python 负责联网搜索、SQLite 入库、确定性计算与 Stage-Gate 审计。

## 2. 核心设计不变式 (Engineering Invariants)

1. **Zero LLM Arithmetic**：所有中国市场规模 (`TAM/SAM/SOM`, `[MKT-CALC]`) 与客户财务回报 (`Payback/IRR/NPV`, `[ROI-CALC]`) 由 `tools/market_and_roi_calculator.py` 纯 Python 计算。
2. **EvidenceVault Single Source of Truth**：所有论断均需挂载经 `EvidenceVault` 赋予的序列 ID：
   - `[EV-SIGGI-XXX]`：Siggi 会议纪要、V&F 幻灯片、Thermo 对比与 Shell/IFE 腐蚀论文一手资料；
   - `[EV-CN-XXX]`：Metaso 中文实时检索（国家政策、央企/煤化工/绿醇/LCO2船厂项目、国内竞品与分析小屋集成商）；
   - `[EV-GL-XXX]`：Serper 国际标准与海外项目核验（Northern Lights、Brevik、ISO 标准等）。
3. **Anti-Survivorship Bias Funnel**：保留食品级 CO2 常规抽检等“伪需求/低支付意愿淘汰项”（`EliminatedWedge`），禁止将一切市场一律粉饰为可投机会。
4. **Dual-Track Hybrid Localization**：产品交付模型按 **Track A (进口核心主机)** / **Track B (`VF-QAS-CN` 双轨本土化防爆分析小屋)** / **Track C (奥地利原装 `PremierGuard QAS`)** 严格区分定价、BOM、渠道与适用客群。
5. **Secret Leak Prevention**：`assert_no_secrets_leaked` 在 Stage 7 写盘前及 `pytest` 全程扫描并拦截任何 API Token 泄露。
