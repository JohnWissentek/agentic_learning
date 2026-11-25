# 电力能源与半导体芯片制造在线测试仪器仪表——智能体机会发现工作流 (V4.0 大模型优先 + 确定性底盘)

> 本项目遵循 **「大模型优先（Model-First）+ 确定性底盘（Deterministic Chassis）」** 智能体工程方法论与 **OMG UML 2.5 行为状态机图标准**，在 V3.0“海内外商业空白图谱 + AI 软硬件协同”的基础上完成 **V4.0 结构性升级**：
> 1. **大脑做深推理（少而精）**：彻底合并 V3 的 16 次孤立 STORM + 16 次高噪声 2 轮 Elo（共 32 次碎片调用），重构为 **2 次行业买方委员会组合终审 + 1 次跨行业全局排位（≤3 次旗舰调用）**；并在 Stage 1 深度挖掘后新增 **Stage 1b 有界靶向空白证伪环（`max_rounds=1`）**，由旗舰模型交叉检索具体厂商型号，去伪存真区分全球双空白、海外在售/国内空白与海内外已在售升维机会。
> 2. **确定性底盘管牢数字、边界与安全**：
>    - **工业级校准 PALMs CFO 引擎**：引入单位边际毛利/废品归因系数（`0.30`）、单一仪器可归因份额（`0.35`）与首年爬坡折扣（`0.50`），彻底修复 V3 100% 毛利导致的回本过短与 IRR 触顶失真；
>    - **Python 确定性注表 + 全语料零截断硬审计**：由 Python 通过 `<!-- TABLE:... -->` 占位符直接注入商业空白表、三情景 `[ROI-CALC]` 财务表与淘汰表；全量扫描 5 卷正文校验 `100%` Vault 引用零伪造与 `[ROI-CALC]` 零漂移，彻底删除 `fallback_ids` 凑引用与截断软审计；
>    - **单核双壳（Single-Core + Thin Dual Shells）**：所有契约、提示词、ROI 财务引擎、注表与审计逻辑收口于 `src/pso_workflow/`，`ide_workflows/antigravity_run_workflow.py` 瘦身为 **287 行纯标准库薄壳**；外部搜索上下文统一施加 `[UNTRUSTED_EXTERNAL_DATA_START/END]` 物理隔离围栏，并支持真实可挂起的 `--hitl` 赛道审批断点。

---

## 一、 目录结构总览

```text
power_semiconductor_opportunities/
├── .env                          # 非涉密运行时调度参数（默认 V4.0 库与输出目录，已 Git 忽略）
├── .env.ai_search                # 付费 AI 搜索密钥（Metaso + Serper，已 Git 忽略）
├── .env.llm                      # 阿里云百炼 DashScope 与分级模型配置（已 Git 忽略）
├── env.ai_search.example         # AI 搜索环境变量模板（可追踪）
├── env.llm.example               # 大模型分级路由配置模板（可追踪）
├── langgraph.json                # LangGraph Studio 可视化调试图注册
├── Makefile                      # 快捷运行与测试命令（默认指向 V4.0 旗舰目录）
├── pyproject.toml                # Python 3.12 + uv 独立工程配置
├── config/
│   ├── research_contract.yaml    # PSO-CONTRACT-2026-V4 契约、66月五因子压测红线与客观硬门禁
│   ├── discovery_scope.yaml      # V4.0 行业边界、商用空白分类树、工业毛利/归因/爬坡护栏
│   └── v1_legacy_seed_catalog.yaml # V1.0 静态预设目录历史归档
├── docs/
│   ├── 00_ARCHITECTURE_AND_PATTERN_MAPPING.md        # V4.0 OMG UML 2.5 stateDiagram-v2 与大脑/底盘边界表
│   ├── 01_AI_SEARCH_TOKENS_AND_ENV_REGISTRY.md       # 付费 AI 搜索密钥脱敏台账与避坑规范
│   ├── 02_OPENSOURCE_BASELINES_AND_ENHANCEMENTS.md   # 开源基线对比与工业增强说明
│   ├── 08_V4_MODEL_FIRST_UML25_STATE_MACHINE.*       # V4.0 OMG UML 2.5 行为状态机架构图 (.drawio/.svg/.pdf)
│   └── 03_–07_*                                      # V1/V2/V3 历史架构图与复盘文档
├── src/pso_workflow/
│   ├── config.py                 # 独立 .env 加载、模型分级与真实检索计账
│   ├── schemas.py                # 红区 Pydantic v2 严格契约（拒收未知枚举，含 V4 证伪与组合评审模型）
│   ├── graph.py                  # LangGraph Send() 并行扇出 + 有界证伪与硬审计修复状态机
│   ├── cli.py                    # `pso-research` 单核 CLI（含 export-v4-schemas/falsify-search/prepare-portfolio/prepare-synthesis/finalize-v4）
│   ├── prompts/templates.py      # 红区集中提示词（含反证审计、买方组合终审、全局排位与注表占位指令）
│   ├── tools/
│   │   ├── audit_guard.py        # 红区客观硬审计与不可信外部数据物理隔离围栏
│   │   ├── search_router.py      # Metaso(中国主力) + Serper(全球主力) + 失败显式日志记录
│   │   ├── evidence_vault.py     # SQLite 持久化证据记忆库（V4 统一 mint EV-CN-xxx / EV-GL-xxx）
│   │   └── roi_calculator.py     # Python 工业校准 PALMs 三情景引擎 + 漏斗淘汰
│   └── nodes/                    # Planner(Stage 0), Researcher+Falsifier(Stage 1/1b), PortfolioReviewer(Stage 3), Synthesizer(Stage 4), Auditor/Judge(Stage 5)
├── ide_workflows/
│   └── antigravity_run_workflow.py  # 287 行纯标准库薄壳（支持 hitl 挂起与 resume_from_stage2）
├── scripts/
│   └── generate_v4_uml25_state_machine_drawio.py  # V4.0 OMG UML 2.5 状态机图自动生成脚本（及 V1-V3 脚本）
├── .agents/skills/pso-opportunity-research/SKILL.md
├── tests/                        # 48 项自动化测试（含 Slice 0/1/2 独立盲写黑盒契约测试与反误报回归测试）
├── data/                         # 运行时 SQLite 证据库（V4: evidence_vault_v4.db）与中间 JSON（已 Git 忽略）
└── outputs/
    ├── v4_model_first_grounded_2026_2036/              # V4.0 旗舰默认输出目录（9 件套）
    ├── v3_commercial_ai_grounded_2026_2036/            # V3.0 历史归档
    ├── v2_dynamic_discovery_2026_2036/                 # V2.0 历史归档
    └── power_semiconductor_online_testing_2026_2036/   # V1.0 历史归档
```

---

## 二、 快速运行指南（单核双壳）

> 支持**两种运行模式**：在 IDE 内直接调用 **Antigravity 内置前沿大模型（推荐）**，或在终端脱离 IDE 时通过 **DashScope 外置模型 CLI** 无头运行；两者 100% 共享 `src/pso_workflow/` 单核契约、提示词、校准财务引擎、注表与全量客观硬审计。

### 模式 1（IDE 内首选推荐）：Antigravity 原生 `run_workflow` 薄壳（`pro`）
- **脚本路径**：`ide_workflows/antigravity_run_workflow.py`（287 行纯 stdlib，通过 `pso-research export-v4-schemas` 拉取单核契约与提示词）
- **标准全量参数**：
  `{"sector": "all", "profile": "flagship", "output_dir": "outputs/v4_model_first_grounded_2026_2036", "vault_db": "data/evidence_vault_v4.db", "model": "pro", "hitl": false}`
- **开启真实人类审批断点（可选）**：设置 `"hitl": true`，Stage 0 后自动落盘 `data/v4_hitl_pending_tracks.json` 并安全退出；审批修改后传入 `"resume_plan": "data/v4_hitl_pending_tracks.json"` 继续执行。
- **复用已核验 Stage 0–1b 数据重跑 Stage 2–5（可选）**：设置 `"resume_from_stage2": true`，避免重复消耗付费搜索额度。

### 模式 2（终端 / CI 无头运行）：Standalone CLI

```bash
cd /Users/john/Desktop/agentic_learning/power_semiconductor_opportunities

# 1. 环境与付费搜索/模型连通性自检
/Users/john/.local/bin/uv run pso-research verify-env

# 2. 运行全部 48 项黑盒契约与回归测试（含零密钥泄露扫描）
/Users/john/.local/bin/uv run pytest -v

# 3. 运行 V4.0 全流程（默认输出 outputs/v4_model_first_grounded_2026_2036）
/Users/john/.local/bin/uv run pso-research run --sector all --profile flagship

# 4. 独立复核客观硬门禁与评分
/Users/john/.local/bin/uv run pso-research evaluate outputs/v4_model_first_grounded_2026_2036
```

---

## 三、 核心交付物说明（V4.0 旗舰 9 件套 + V3/V2/V1 历史归档）

### V4.0 旗舰目录 `outputs/v4_model_first_grounded_2026_2036/`
1. `00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md` — 投决级总览、反证后商业空白全景、跨行业共性平台与 Top 16 总表（Python 确定性注表）
2. `01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md` — 电力能源动态赛道（DP1–DP4）商业格局、靶向证伪核查与 AI 软硬协同深度研报
3. `02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md` — 半导体制造动态赛道（DS1–DS4）前道/封装/CPO 量检测反证深度研报
4. `03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md` — 工业校准三情景 `[ROI-CALC]` 财务模型、Stage 2 16 项淘汰审计与买方委员会组合排位
5. `04_PRODUCT_TECH_AND_UPGRADE_STRATEGY_PLAYBOOK.md` — 全 16 项 AI 协同研发周期压缩、国产 BOM 替代与三级 GTM 商业化执行手册（零截断）
6. `05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md` — 基于 `data/evidence_vault_v4.db` 确定性导出的 582 条核验证据溯源总表（统一 `EV-CN-xxx` / `EV-GL-xxx`）
7. `06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json` — 全语料零截断硬审计报告（0 伪造引用、0 财务漂移）与真实搜索成本遥测（`¥5.19 CNY`）
8. `07_V4_MODEL_FIRST_EXECUTION_SUMMARY.md` — V4.0 实战运行摘要（含 V3 → V4 量化演进对照与 Top 16 全景总表）
9. `08_V4_MODEL_FIRST_UML25_STATE_MACHINE.{drawio,svg,pdf}`（同步存于 `docs/08_V4_MODEL_FIRST_UML25_STATE_MACHINE.*`）— OMG UML 2.5 行为状态机架构图

### 历史版本归档（完整保留未改动）
- **V3.0** (`outputs/v3_commercial_ai_grounded_2026_2036/`)：商业空白图谱 + AI 协同初版及 `data/evidence_vault_v3.db`。
- **V2.0** (`outputs/v2_dynamic_discovery_2026_2036/`)：从零动态发现全 9 件套及 `data/evidence_vault_v2.db`。
- **V1.0** (`outputs/power_semiconductor_online_testing_2026_2036/`)：静态基线版原版报告、A0 架构图与复盘文档。
