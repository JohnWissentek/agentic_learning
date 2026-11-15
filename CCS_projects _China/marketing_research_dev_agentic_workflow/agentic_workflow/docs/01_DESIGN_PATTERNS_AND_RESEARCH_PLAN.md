# 01 设计模式映射与八阶段研究逻辑 (`01_DESIGN_PATTERNS_AND_RESEARCH_PLAN`)

| 阶段 | 对应模块 | 《Agentic Design Patterns》依据 | 核心机制与防幻觉策略 |
| :--- | :--- | :--- | :--- |
| **Stage 0a** | `siggi_corpus_loader` + `run_macro_recon` | Ch 14 Knowledge Retrieval / MCP Context | 解析 `information_from_siggi/` 全量 PDF/MD 赋予 `[EV-SIGGI-*]` + Metaso/Serper 实时扫描中国与国际动态 |
| **Stage 0b** | `node_siggi_ingest_and_planner` | Ch 6 Planning + Step-Back Prompting | 零预设前提，由一手证据动态聚拢 5–6 个研究赛道并构建 4 赛道全景假说（含 S4 负向对照） |
| **Stage 1** | `node_parallel_track_researcher` | Ch 3 Parallelization + Ch 12 Recovery | 并发运行 CN/GLOBAL 检索与全文提取；严格清洗并剔除一切无 Vault 来源的模型或项目 |
| **Stage 2** | `aggregate_catalogs_and_screen` | Ch 5 Tool Use + Ch 17 Guardrails | Python `[MKT-CALC]` 计算 2026–2036 TAM/SAM/SOM + `[ROI-CALC]` 筛除高回收期或伪需求切入点 |
| **Stage 3** | `node_size_screen_and_storm` | Ch 7 Multi-Agent + Stanford STORM | 三桶油总工/设计院室主任/煤化工CFO/分析小屋集成商 四重视角质询落地阻力 |
| **Stage 4** | `node_swiss_elo_ranker` | Ch 20/21 Prioritization & Tournament | 基于物理护城河与 `[ROI-CALC]` 保守韧性开展瑞士轮配对 Elo 排序 |
| **Stage 5** | `node_parallel_volume_synthesizer` | Ch 1 Prompt Chaining & Parallel Fan-Out | 5 卷旗帜级报告并发撰写（严格绑定相同计算锚点与证据库 ID） |
| **Stage 6** | `node_adversarial_critic` + CRAG | Ch 4 Reflection + Corrective RAG | 程序化检查非法引用 ID + 异构 Critic (`deepseek-v4-pro`/Native Critic) Audit；最多 2 轮定向补检重写 |
| **Stage 7** | `node_stage_gate_judge_and_finalize` | Ch 19 Evaluation + Zero-LLM Index | 确定性渲染第 05 卷全量证据索引，运行 100 分制门禁评分与防泄密检查后落盘交付 |
