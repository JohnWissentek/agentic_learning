# 电力能源与半导体芯片制造在线测试仪器仪表——智能体机会发现工作流 (V3.0 海内外在售空白图谱 + AI软硬件协同)

> 本项目严格基于 [《Agentic Design Patterns》全书架构精要](../../agentic_design_patterns/全书摘要分册/README.md) 的多智能体设计模式编织构建，融合开源 **`langchain-ai/open_deep_research`**（LangGraph 有界循环状态机骨架）、**`stanford-oval/storm`**（四角色买方委员会拷问）、**`bytedance/deer-flow`**（Python 三情景确定性 ROI 计算沙箱）与书内 **Ch 21 AI Co-Scientist**（Elo 锦标赛排序）。**V3.0** 在 V2.0“从零动态发现赛道 (`RECON -> 32 -> 16`)”的基础上，进一步聚焦**现实产业可落地性**两大核心增强：
> 1. **海内外商业在售产品实证图谱**：每个赛道同步运行痛点检索与**海内外商业厂商/中标型号检索 (`cn_vendor_queries` / `global_vendor_queries`)**，零编造区分`海内外均已在售(红海/升级)`、`海外在售·国产空白` 与 `海内外均属产品空白`，并在 Stage 2 打分与 Elo 裁决中对真实空白施加结构性加权。
> 2. **AI 时代软硬件协同研发与 GTM 新范式**：全面评估 **PINN 计算传感以算代硬降 BOM**、**合成缺陷样本零样本冷启动**、**AI 辅助 FPGA/EDA/上位机将 30-48 月传统研发压缩至 10-18 月**、以及**产线物理断网 NPU+FPGA 部署与国产 BOM 替代方案**，聚焦**中国优先、全球跟进**在未来 **3–5 年（2027–2031）** 与 **5–10 年（2031–2036）** 的可执行产品与技术机会。

---

## 一、 目录结构总览

```text
power_semiconductor_opportunities/
├── .env                          # 非涉密运行时调度参数（默认 V3.0 库与输出目录，已 Git 忽略）
├── .env.ai_search                # 从用户 GitHub 仓库提取的 AI 搜索密钥（已 Git 忽略）
├── .env.llm                      # 阿里云百炼 DashScope 与分级模型配置（已 Git 忽略）
├── env.ai_search.example         # AI 搜索环境变量模板（可追踪）
├── env.llm.example               # 大模型分级路由配置模板（可追踪）
├── langgraph.json                # LangGraph Studio 可视化调试图注册
├── Makefile                      # 快捷运行与测试命令（默认指向 V3.0 旗舰目录，保留 eval-v2 / eval-v1）
├── pyproject.toml                # Python 3.12 + uv 独立工程配置
├── config/
│   ├── research_contract.yaml    # PSO-CONTRACT-2026-V3 契约、漏斗配额与 42 月保守回收期红线
│   ├── discovery_scope.yaml      # V3.0 行业边界、商用空白分类树、AI协同范式与物性规模护栏
│   └── v1_legacy_seed_catalog.yaml # V1.0 静态预设目录历史归档
├── docs/
│   ├── 00_ARCHITECTURE_AND_PATTERN_MAPPING.md        # Mermaid 拓扑与 21 模式映射总表
│   ├── 01_AI_SEARCH_TOKENS_AND_ENV_REGISTRY.md       # 付费 AI 搜索密钥脱敏台账与避坑规范
│   ├── 02_OPENSOURCE_BASELINES_AND_ENHANCEMENTS.md   # 开源基线对比与工业增强说明
│   ├── 03_AGENTIC_WORKFLOW_ARCHITECTURE_A0.*         # V1.0 A0 幅面完整载荷版架构图 (.drawio/.svg/.pdf)
│   ├── 04_V1_CLEAN_TOPOLOGY_DAG.*                    # V1.0 清爽版主干+循环拓扑图 (.drawio/.svg/.pdf)
│   ├── 05_V1_RETROSPECTIVE_AND_V2_UPGRADE_ANALYSIS.md# V1.0 架构复盘（为何非严格DAG）与局限性分析报告
│   ├── 06_V2_DYNAMIC_DISCOVERY_TOPOLOGY.*            # V2.0 从零动态发现与漏斗拓扑图 (.drawio/.svg/.pdf)
│   └── 07_V3_COMMERCIAL_AI_DISCOVERY_TOPOLOGY.*      # V3.0 商业空白与 AI 软硬件协同编排拓扑图 (.drawio/.svg/.pdf)
├── src/pso_workflow/
│   ├── config.py                 # 独立 .env 加载、Ch 16 模型分级与回退、成本账本
│   ├── schemas.py                # Pydantic v2 契约（含 `commercial_status`、8 项商业/AI协同字段）
│   ├── graph.py                  # LangGraph Send() 并行扇出 + 有界 Cyclic 反思状态图
│   ├── cli.py                    # `pso-research` CLI（含 V3 recon-search/track-search/screen-candidates/gap-search/finalize-v3）
│   ├── prompts/templates.py      # RECON_DISCOVERY、V3 零编造商用+AI提示词、双语与严格闭卷协议
│   ├── tools/
│   │   ├── search_router.py      # Metaso(中国主力) + Serper(全球主力) + Jina Reader 兜底
│   │   ├── evidence_vault.py     # SQLite 持久化证据记忆库（V3: evidence_vault_v3.db 统一去重）
│   │   └── roi_calculator.py     # Python PALMs 三情景钳位 + 商业空白度奖惩校准 + 漏斗淘汰引擎
│   └── nodes/                    # Planner(Stage 0), Researcher+Screener(Stage 1-2), STORM/Elo, Synthesizer, Critic, Judge
├── ide_workflows/
│   └── antigravity_run_workflow.py  # Antigravity IDE 原生 V3.0 `run_workflow` 7 阶段漏斗脚本
├── scripts/
│   ├── generate_a0_workflow_drawio.py         # V1.0 A0 全量架构图生成脚本
│   ├── generate_v1_clean_topology_drawio.py   # V1.0 清爽版拓扑图生成脚本
│   ├── generate_v2_clean_topology_drawio.py   # V2.0 动态发现拓扑图生成脚本
│   └── generate_v3_clean_topology_drawio.py   # V3.0 商业空白与 AI 协同拓扑图生成脚本
├── .agents/skills/pso-opportunity-research/SKILL.md
├── tests/                        # 契约、防泄露、商业空白奖惩与区间ROI、V3全图轨迹与CLI往返测试
├── data/                         # 运行时 SQLite 证据库（V3: evidence_vault_v3.db）与中间 JSON（已 Git 忽略）
└── outputs/
    ├── v3_commercial_ai_grounded_2026_2036/            # V3.0 旗舰默认输出目录
    ├── v2_dynamic_discovery_2026_2036/                 # V2.0 从零动态发现历史归档
    └── power_semiconductor_online_testing_2026_2036/   # V1.0 静态基线历史归档
```

---

## 二、 快速在 Antigravity IDE 中运行

> 支持**两种运行模式**：在 IDE 内直接调用 **Antigravity 内置前沿大模型（推荐）**，或在终端脱离 IDE 时通过 **DashScope 外置模型 CLI** 无头运行；两者共用同一套付费 AI 搜索引擎（秘塔 Metaso + Serper `.env.ai_search`）、`EvidenceVault` SQLite 证据库与 Python 确定性 ROI/空白度校准引擎。

### 模式 1（IDE 内首选推荐）：使用 Antigravity 内置前沿大模型（`run_workflow` + `pro`）
全部推理与长文撰写（Stage 0 动态赛道与商用查询规划 → 8 路痛点/竞品双检索与 AI 协同挖掘 → STORM 四方拷问 → Elo 锦标赛 → 5 卷旗舰报告合成 → 异构 Critic 审查 → Stage-Gate 100 分门禁）均直接运行于 **Antigravity 内置 `pro` 大模型**，Python CLI（`recon-search`、`track-search`、`screen-candidates`、`gap-search`、`finalize-v3`）仅负责确定性证据检索与财务/空白校准：

1. 在 Antigravity IDE 对话中要求运行工作流（或加载局部技能 `.agents/skills/pso-opportunity-research/SKILL.md`），系统自动调用 `run_workflow`：
   - **脚本路径**：`ide_workflows/antigravity_run_workflow.py`
   - **参数**：`{"sector": "all", "profile": "flagship", "output_dir": "outputs/v3_commercial_ai_grounded_2026_2036", "vault_db": "data/evidence_vault_v3.db", "model": "pro", "hitl": false}`
2. 独立分段调试 V3 确定性 CLI 子命令（可选）：
```bash
cd /Users/john/Desktop/agentic_learning/power_semiconductor_opportunities
/Users/john/.local/bin/uv run pso-research recon-search --sector all --profile flagship --vault-db data/evidence_vault_v3.db
```

### 模式 2（终端/CI 无头备选）：使用 DashScope 外置大模型（`.env.llm`）

#### 1. 环境与密钥连通性自检
```bash
cd /Users/john/Desktop/agentic_learning/power_semiconductor_opportunities
/Users/john/.local/bin/uv run pso-research verify-env
```

#### 2. 运行三层自动化测试（Mock 工具 + 商业空白奖惩/区间 ROI + V3 图轨迹与 CLI 往返 + 防泄露扫描）
```bash
/Users/john/.local/bin/uv run pytest -v
```

#### 3. 通过 Standalone CLI 运行 V3.0 全流程（`qwen3.8-*` + `deepseek-v4-pro`）
```bash
/Users/john/.local/bin/uv run pso-research run --sector all --profile flagship --output-dir outputs/v3_commercial_ai_grounded_2026_2036
```

#### 4. 单行业快速运行与独立门禁评分
```bash
# 仅对电力能源 (DP*) 或半导体 (DS*) 运行快速发现
/Users/john/.local/bin/uv run pso-research run --sector semiconductor --profile fast --output-dir outputs/semi_fast
# 对 V3 结果目录运行独立 Ch 19 LLM-as-a-Judge 门禁审计
/Users/john/.local/bin/uv run pso-research evaluate outputs/v3_commercial_ai_grounded_2026_2036
```

---

## 三、 核心交付物说明（V3.0 旗舰 9 件套 + V2.0/V1.0 历史归档）

### V3.0 旗舰目录 `outputs/v3_commercial_ai_grounded_2026_2036/`
1. `00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md` — 执行摘要、V3.0 商业在售与空白全景统计、AI 软硬件协同总论与 Top 16 决选总表
2. `01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md` — 电力能源动态赛道商业化在售盘点、空白定级与 AI 协同深度研报
3. `02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md` — 半导体制造海内外设备竞品对比与 AI 原位量检测深度研报
4. `03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md` — 区间 PALMs 三情景 ROI、商业空白度加权校准、Stage 2 漏斗淘汰审计与 Elo 排位
5. `04_PRODUCT_TECH_AND_UPGRADE_STRATEGY_PLAYBOOK.md` — 传统 (30-48月) vs AI 协同 (10-18月) 研发范式 Playbook、BOM 国产化与三类战场 GTM 打法
6. `05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md` — 基于 `data/evidence_vault_v3.db` 确定性导出的 421 条核验证据溯源总表
7. `06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json` — 商业空白分布、淘汰审计、100 分制门禁评分（98.0/100）与遥测审计
8. `07_V3_COMMERCIAL_WHITESPACE_AND_AI_PARADIGM_SUMMARY.md` — **V3.0 实战运行摘要（含 V1->V2->V3 演进对比、Top 16 商业空白对照总表与 AI 软硬件协同矩阵）**
9. `08_V3_COMMERCIAL_AI_DISCOVERY_TOPOLOGY.{drawio,svg,pdf}`（同步存根于 `docs/07_V3_COMMERCIAL_AI_DISCOVERY_TOPOLOGY.*`）— V3.0 清爽版编排拓扑图

### V2.0 与 V1.0 历史归档（完整保留）
- **V2.0** (`outputs/v2_dynamic_discovery_2026_2036/`): 保留 V2 从零动态发现全 9 件套及 `data/evidence_vault_v2.db`。
- **V1.0** (`outputs/power_semiconductor_online_testing_2026_2036/`): 保留 V1 `00_`–`08_` 原版报告与 A0 图、`09_V1_CLEAN_TOPOLOGY_DAG.*` 及 `10_V1_WORKFLOW_RETROSPECTIVE_ANALYSIS.md`。
