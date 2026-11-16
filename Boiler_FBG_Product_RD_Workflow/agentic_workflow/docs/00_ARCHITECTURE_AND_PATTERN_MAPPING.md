# 《Agentic Design Patterns》全书模式映射与 IPD 多智能体架构说明

本工作流严格遵循 [`agentic_design_patterns`](../../../agentic_design_patterns/全书摘要分册/README.md) 的 Pattern Composition（模式编织）工程准则，将燃煤电站锅炉水冷壁 FBG 测温产品的**IPD 集成产品研发与量产导入 (NPI)** 拆解为 8 个受契约约束的执行阶段。

## 《Agentic Design Patterns》核心模式落地矩阵

| 章节与设计模式 | 本工作流工程化实现 | 对应代码位置 |
| :--- | :--- | :--- |
| **Ch 1: Prompt Chaining** | Stage 0→1→2→3/4→5→6→7 严密结构化管道，Stage 5 按 7 个专业分卷输出独立工程文档，避免单次超长截断。 | `graph.py`, `nodes/synthesizer.py` |
| **Ch 2: Routing** | 三重路由：① 中国市场/竞品路由至秘塔 `Metaso`，国际硬件/原厂 `filetype:pdf` 路由至 `Serper`；② Critic 状态路由器决定 `rewrite` 或 `judge`；③ `fast / producer / critic` 模型路由。 | `tools/search_router.py`, `nodes/critic_and_judge.py` |
| **Ch 3: Parallelization** | Stage 1 并发扇出 6 路专业研究员 + 原厂 PDF 下载验真器；Stage 3-4 并发召开 IPD 评审与电厂 STORM；Stage 5 并发撰写 `00_`–`06_`。 | `nodes/researcher.py`, `ide_workflows/antigravity_run_workflow.py` |
| **Ch 4: Reflection** | 程序化扫描 `[EV-*]` 真伪与 `./datasheets_pdf/*.pdf` 物理文件存在性 + 异构 Critic 审查，有界闭环（`Max Loops = 2`）触发定向重写。 | `nodes/critic_and_judge.py` |
| **Ch 5 & Ch 10: Tool Use / Protocol** | 封装 `MetasoSearchClient`、`SerperSearchClient`、`JinaReaderClient`、`datasheet_fetcher`（%PDF- 魔数与 `pypdf` 验真）及确定性计算引擎。 | `tools/` |
| **Ch 6: Planning** | Stage 0b 首席产品经理应用 Step-Back Prompting 分解双档产品定位与 6 条正交研发赛道查询矩阵。 | `nodes/planner.py` |
| **Ch 7: Multi-Agent Collaboration** | 组建首席 PM、市场总监、光电总师、光纤焊接专家、软件 AI 架构师、NPI 质量与 CFO 共 7 大专业角色，以及 6 角色 IPD 评审会 + 4 角色电厂买方 STORM 委员会。 | `nodes/ipd_and_storm.py`, `prompts/templates.py` |
| **Ch 8: Memory Management** | ① SQLite WAL `EvidenceVault` 实现跨阶段 URL/哈希去重与 `[EV-BASE/CN/GL/PDF]` 溯源；② LangGraph Checkpointer 持久化图状态。 | `tools/evidence_vault.py`, `graph.py` |
| **Ch 11: Goal Setting & Monitoring** | `config/product_rd_contract.yaml` 固化最少证据条数、最低验真 PDF 数量、双档双轨覆盖及 Stage-Gate ≥85 分硬红线。 | `config/product_rd_contract.yaml` |
| **Ch 12: Exception Handling & Recovery** | 秘塔 `size/page` 互斥控制、HTTP 200 下 `errCode` 拦截与 Serper 互备降级、Jina Reader 全文兜底、JSON 控字符强修复与 PDF 非法响应自动跳过。 | `config.py`, `tools/search_router.py`, `tools/datasheet_fetcher.py` |
| **Ch 14: Knowledge Retrieval (CRAG)** | 本地只读导入 `Boiler_FBG_Thermometry_Research` 为 `[EV-BASE-*]`，联合在线检索与原厂 PDF 文本摘要入库；Critic 识别缺口后触发 `gap-search` CRAG 补检。 | `tools/prior_corpus_loader.py`, `tools/datasheet_fetcher.py` |
| **Ch 16: Resource-Aware Optimization** | 轨道高并发抽取分配 `fast` 轻量级模型，规划/IPD/STORM/合成与评审分配 `pro`/`producer` 旗舰模型，实时记录成本遥测。 | `config.py`, `ide_workflows/antigravity_run_workflow.py` |
| **Ch 17: Reasoning Techniques (PALMs)** | 所有物理光学链路预算（`[PHY-CALC]`）、双轨阶梯 BOM（`[BOM-CALC]`）、5 年 NPV/IRR（`[FIN-CALC]`）与电厂回收期（`[PLANT-ROI]`）100% 由 Python 确定性代码计算。 | `tools/engineering_and_finance_calc.py` |
| **Ch 18: Guardrails & Safety** | Pydantic v2 强边界校验、单 PDF ≤ 9.5 MB 防大文件超限、绝不绕过反爬/验证码、`assert_no_secrets_leaked` 零密钥明文守卫。 | `schemas.py`, `config.py`, `tests/` |
| **Ch 19–21: Evaluation, Prioritization & Elo** | 5 维 × 20 分 = 100 分 Stage-Gate 门禁 + 3 层自动化 `pytest` + 5 套候选技术路线瑞士轮 Elo 锦标赛。 | `nodes/ipd_and_storm.py`, `tests/` |
