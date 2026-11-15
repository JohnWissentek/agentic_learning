# V&F IMR-MS 中国 CCS/CCUS 市场调研与 GTM 智能体工作流 (`vf-ccus-workflow`)

本工作流严格依据 [`agentic_design_patterns`](../../../agentic_design_patterns/全书摘要分册/README.md) 的核心设计模式构建，并吸收 `power_semiconductor_opportunities` V1–V3 工程经验，用于对奥地利 **V&F Analyse- und Messtechnik GmbH (`CO2Sense` / `PremierGuard CCUS QAS`)** 在中国 CCS/CCUS 市场开展可审计的市场规模测算、竞争情报分析、双轨本土化 GTM 规划与 30-60-90 天落地路线图编排。

## 核心架构亮点（对齐《Agentic Design Patterns》全书规范）

| 设计模式章节 | 本工作流工程实现 | 代码位置 |
| :--- | :--- | :--- |
| **Ch 1–3 Prompt Chaining & Parallelization** | 阶段0–7严密因果管道 + Stage 1 多赛道并发检索与 Stage 5 五卷宗并发撰写 | `nodes/researcher.py`, `nodes/synthesizer.py`, `ide_workflows/antigravity_run_workflow.py` |
| **Ch 4 Reflection (Adversarial Critic Loop)** | 异构模型批评官 (`deepseek-v4-pro` / Native Critic) + 程序化引用核验，最多 `2` 轮闭环定向重写 | `nodes/critic_and_judge.py` |
| **Ch 5/14 Knowledge Retrieval & CRAG** | 本地 Siggi 一手资料解析器 (`[EV-SIGGI-*]`) + Metaso/Serper SQLite `EvidenceVault` + Critic 缺口触发 CRAG 补检 | `tools/siggi_corpus_loader.py`, `tools/evidence_vault.py`, `tools/search_router.py` |
| **Ch 7/17 Multi-Agent STORM & PALMs Calculation** | 4 类中国 CCS 买方角色深度质询 + Python 确定性 `[MKT-CALC]` 市场规模 & `[ROI-CALC]` 客户回收期漏斗（**严禁 LLM 心算**） | `tools/market_and_roi_calculator.py`, `nodes/storm_and_rank.py` |
| **Ch 12/16 Resilience & Model Routing** | Metaso ↔ Serper ↔ Jina 全文三级容错、DashScope 阶梯模型故障切换、JSON 强修复与 API Key 防泄露守卫 | `config.py`, `tools/search_router.py` |
| **Ch 19/20/21 Evaluation, Swiss Elo & Prioritization** | 瑞士轮配对 Elo 排序 + Zero-LLM 第05卷全量证据索引 + 100分制 Stage-Gate 门禁（≥85分） | `nodes/critic_and_judge.py`, `cli.py` |

## 快速启动

```bash
# 1. 安装依赖（Python 3.12）
uv sync --python 3.12 --extra dev

# 2. 校验 Siggi 一手资料、Metaso/Serper 与 DashScope 模型连通性
uv run vf-ccus-research verify-env

# 3. 单独测试离线单元测试与端到端图轨迹（零成本，无网络依赖）
uv run pytest -v

# 4. 入库 Siggi 一手技术与会议资料 ([EV-SIGGI-*])
uv run vf-ccus-research ingest-siggi

# 5. 运行独立版完整 LangGraph 工作流 (产出自动落盘至 ../research_outputs/)
uv run vf-ccus-research run --profile flagship
```

也可通过 Antigravity Native `run_workflow` 执行 [`ide_workflows/antigravity_run_workflow.py`](./ide_workflows/antigravity_run_workflow.py) 进行混合原生编排。
