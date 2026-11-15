# 电力能源与半导体芯片制造在线测试仪器仪表——智能体机会发现工作流

> 本项目严格基于 [《Agentic Design Patterns》全书架构精要](../../agentic_design_patterns/全书摘要分册/README.md) 的多智能体设计模式编织构建，融合开源 **`langchain-ai/open_deep_research`**（LangGraph 状态机骨架）、**`stanford-oval/storm`**（四角色买方委员会拷问）、**`bytedance/deer-flow`**（Python 确定性 ROI 计算沙箱）与书内 **Ch 21 AI Co-Scientist**（Elo 锦标赛排序），专注挖掘**中国优先、全球跟进**在未来 **3–5 年（2027–2031）** 与 **5–10 年（2031–2036）** 的在线测试仪器仪表技术、产品与应用新机会。

---

## 一、 目录结构总览

```text
power_semiconductor_opportunities/
├── .env                          # 非涉密运行时调度参数（已 Git 忽略）
├── .env.ai_search                # 从用户 GitHub 仓库提取的 AI 搜索密钥（已 Git 忽略）
├── .env.llm                      # 阿里云百炼 DashScope 与分级模型配置（已 Git 忽略）
├── env.ai_search.example         # AI 搜索环境变量模板（可追踪）
├── env.llm.example               # 大模型分级路由配置模板（可追踪）
├── langgraph.json                # LangGraph Studio 可视化调试图注册
├── Makefile                      # 快捷运行与测试命令
├── pyproject.toml                # Python 3.12 + uv 独立工程配置
├── config/
│   ├── research_contract.yaml    # Ch 11/19 形式化研究契约与 SMART 门禁标准
│   └── domain_taxonomy.yaml      # 电力能源(P1-P4) × 半导体制造(S1-S4) 8 赛道本体与双引擎查询
├── docs/
│   ├── 00_ARCHITECTURE_AND_PATTERN_MAPPING.md     # Mermaid 拓扑与 21 模式映射总表
│   ├── 01_AI_SEARCH_TOKENS_AND_ENV_REGISTRY.md    # 付费 AI 搜索密钥脱敏台账与避坑规范
│   ├── 02_OPENSOURCE_BASELINES_AND_ENHANCEMENTS.md# 开源基线对比与 8 项工业增强说明
│   └── 03_AGENTIC_WORKFLOW_ARCHITECTURE_A0.*      # A0 幅面完整工作流架构图 (.drawio/.svg/.pdf)
├── src/pso_workflow/
│   ├── config.py                 # 独立 .env 加载、Ch 16 模型分级与回退、成本账本
│   ├── schemas.py                # Pydantic v2 契约与 LangGraph State 定义
│   ├── graph.py                  # LangGraph Send() 并行扇出 + 反思闭环状态图
│   ├── cli.py                    # `pso-research` Rich 命令行工具
│   ├── prompts/templates.py      # Step-Back、Factored Cognition、严格闭卷与双语协议提示词
│   ├── tools/
│   │   ├── search_router.py      # Metaso(中国主力) + Serper(全球主力) + Jina Reader 兜底
│   │   ├── evidence_vault.py     # SQLite 持久化证据记忆库（URL 去重 + 权威分级 T1-T4）
│   │   └── roi_calculator.py     # Python PALMs 确定性 ROI/Payback/NPV/IRR 计算器
│   └── nodes/                    # Planner, Researcher, STORM, Ranker, Synthesizer, Critic, Judge
├── ide_workflows/
│   └── antigravity_run_workflow.py  # Antigravity IDE 原生 `run_workflow` 协同脚本
├── scripts/
│   └── generate_a0_workflow_drawio.py # A0 draw.io 工作流架构图生成与几何零重叠校验脚本
├── .agents/skills/pso-opportunity-research/SKILL.md
├── tests/                        # 契约、秘文防泄露、ROI 数学与 Mock 图轨迹测试
├── data/                         # 运行时 SQLite 证据库与断点检查点（已 Git 忽略）
└── outputs/                      # 结构化交付成果目录（旗舰默认：power_semiconductor_online_testing_2026_2036）
```

---

## 二、 快速在 Antigravity IDE 中运行

> 支持**两种运行模式**：在 IDE 内直接调用 **Antigravity 内置前沿大模型（推荐）**，或在终端脱离 IDE 时通过 **DashScope 外置模型 CLI** 无头运行；两者共用同一套付费 AI 搜索引擎（秘塔 Metaso + Serper `.env.ai_search`）、`EvidenceVault` SQLite 证据库与 Python PALMs 确定性 ROI 计算引擎。

### 模式 1（IDE 内首选推荐）：使用 Antigravity 内置前沿大模型（`run_workflow` + `pro`）
全部推理与长文撰写（Step-Back 规划 → 8 赛道并研 → STORM 四方拷问 → Elo 锦标赛 → 5 卷旗舰报告合成 → 异构Critic审查 → Stage-Gate 100分门禁）均直接运行于 **Antigravity 内置 `pro` 大模型**，Python CLI 仅负责确定性证据检索与财务数学计算：

1. 在 Antigravity IDE 对话中要求运行工作流（或加载局部技能 `.agents/skills/pso-opportunity-research/SKILL.md`），系统自动调用 `run_workflow`：
   - **脚本路径**：`ide_workflows/antigravity_run_workflow.py`
   - **参数**：`{"sector": "all", "output_dir": "outputs/power_semiconductor_online_testing_2026_2036", "model": "pro"}`
2. 手动单独更新双引擎证据与 ROI 上下文（可选）：
```bash
cd /Users/john/Desktop/agentic_learning/power_semiconductor_opportunities
/Users/john/.local/bin/uv run pso-research prepare-context --sector all --output data/native_context_bundle.json
```

### 模式 2（终端/CI 无头备选）：使用 DashScope 外置大模型（`.env.llm`）

#### 1. 环境与密钥连通性自检
```bash
cd /Users/john/Desktop/agentic_learning/power_semiconductor_opportunities
/Users/john/.local/bin/uv run pso-research verify-env
```

#### 2. 运行三层自动化测试（Mock 工具 + 确定性 ROI + 图轨迹 + 原生桥接 + 防泄露扫描）
```bash
/Users/john/.local/bin/uv run pytest -v
```

#### 3. 通过 Standalone CLI 运行全流程（`qwen3.8-*` + `deepseek-v4-pro`）
```bash
/Users/john/.local/bin/uv run pso-research run --sector all --profile flagship --output-dir outputs/flagship_cli
```

#### 4. 单模块/单行业快速运行与独立门禁评分
```bash
# 仅跑电力能源 (P1-P4) 或半导体 (S1-S4)
/Users/john/.local/bin/uv run pso-research run --sector semiconductor --profile fast --output-dir outputs/semi_fast
# 对任意结果目录运行独立 Ch 19 LLM-as-a-Judge 门禁审计
/Users/john/.local/bin/uv run pso-research evaluate outputs/power_semiconductor_online_testing_2026_2036
```

---

## 三、 核心交付物说明（工作流标准 7 件套 + 旗舰运行归档 `07`–`08`）

1. `00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md` — 执行摘要、电力×半导体交叉协同主线与 Top 16 机会全景榜单
2. `01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md` — 电力能源（储能/固态电池、钙钛矿/绿氢、特高压/SF6替代/海缆、灵活调峰与CCUS）深度机会
3. `02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md` — 半导体制造（Fab AMC/湿化特气、前道纳米光学/X射线量测、SiC/GaN动态KGD、2.5D/3D混合键合）深度机会
4. `03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md` — Python PALMs 制造端 ROI/Payback/NPV/IRR 模型与 AI Co-Scientist Elo 锦标赛排位
5. `04_PRODUCT_TECH_AND_UPGRADE_STRATEGY_PLAYBOOK.md` — 共性测试平台复用、产线工程化落地门槛与“先中国后出海”产业升级执行手册
6. `05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md` — 基于 `data/evidence_vault.db` 确定性导出的核验证据与溯源链接总表
7. `06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json` — Ch 19 形式化契约校验、100 分制裁判得分与全链路 Token/底层模型审计日志
8. `07_WORKFLOW_RUN_SUMMARY_AND_MODEL_PROVENANCE.md`（旗舰目录 `outputs/power_semiconductor_online_testing_2026_2036/` 附带）— 班次运行概要、`model="pro"` 底层模型溯源澄清与 16 项终审指标对照表
9. `08_AGENTIC_WORKFLOW_ARCHITECTURE_A0.{drawio,svg,pdf}`（同步存根于 `docs/03_AGENTIC_WORKFLOW_ARCHITECTURE_A0.*`）— A0 幅面全节点工作流架构图（含硬编码/LLM 标注及全部 Context 组装细节）
