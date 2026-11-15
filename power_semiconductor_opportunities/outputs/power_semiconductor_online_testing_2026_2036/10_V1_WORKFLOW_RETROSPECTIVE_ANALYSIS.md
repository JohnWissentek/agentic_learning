# V1.0 智能体工作流架构复盘、方法论批判与 V2.0“从零动态发现”升级蓝图

> **关联拓扑图**：[09_V1_CLEAN_TOPOLOGY_DAG.pdf](../outputs/power_semiconductor_online_testing_2026_2036/09_V1_CLEAN_TOPOLOGY_DAG.pdf) / [.drawio](../outputs/power_semiconductor_online_testing_2026_2036/09_V1_CLEAN_TOPOLOGY_DAG.drawio) ｜ [08_AGENTIC_WORKFLOW_ARCHITECTURE_A0.pdf](../outputs/power_semiconductor_online_testing_2026_2036/08_AGENTIC_WORKFLOW_ARCHITECTURE_A0.pdf)  
> **基准运行批次**：`native-88e91cf7`（Stage-Gate `100.0 / 100`、`225` 条 SQLite 核验证据、`63.11%` 中国信源、`1,038,775` 子智能体 tokens）  
> **文档性质**：面向工作流所有者与架构师的 V1.0 深度复盘报告，直接回答“这是否是 DAG？”“为什么先画靶子写死 8 赛道与 16 种子不合理？”以及“V2.0 如何演进为真正自下而上的新机会发现系统”。

---

## 一、 编排图的图论本质与原 A0 详图可读性复盘

### 1.1 它不是纯无环图（DAG），而是“主干 DAG + 尾部受控有界环路”
严格按图论语义分类，本系统在 [`src/pso_workflow/graph.py`](../src/pso_workflow/graph.py#L85-L115) 与 [`ide_workflows/antigravity_run_workflow.py`](../ide_workflows/antigravity_run_workflow.py) 中编排的拓扑结构属于 **Bounded Cyclic StateGraph（有界可循环有向状态图）**：
- **前段主干严格无环（V0 → V5）**：配置/契约装载 → 检索与算账 → Step-Back 总规划 → 8 赛道并行扇出与汇合（Fan-Out / Join）→ 瑞士制两轮 Elo 成对排位 → 五卷合成与零 LLM 索引直出，数据单向流动、绝不回头。
- **尾部质量反思环路（V6 Critic ↔ V5/CRAG）**：`node_heterogeneous_critic` 审查草稿后，确定性条件路由器 `route_after_critic` 允许依据质检结果触发两类受控回环：
  1. `needs_more_evidence` → 触发 `Corrective RAG` 按 `gap_queries` 定向补搜入库，回流重触发五卷报告合成；
  2. `needs_rewrite` → 唤醒定向修订智能体只修补受损分卷，重跑正则审计再复检。
  3. **硬熔断守卫（防死循环）**：当 `loop_count > max_loops`（默认上限 `2` 轮）时，路由器强制放行至终审，从而把图控制在“有界可收敛状态机”。

### 1.2 为什么原 A0 全详图（`08_...A0.pdf`）令人难看懂？三大设计失焦根因
对比重绘前后的两张图，旧图难读并非节点算力复杂，而是可视化与流程耦合方式产生了三重视觉噪音：
1. **将“Prompt 上下文装配说明书”串进了主干控制流**：原本控制流核心节点只有不到 10 个，旧图却在每次 LLM 调用框正前方硬塞一个与算子同等体积的巨型琥珀色 `[Context 组装]` 框，使 36 个大卡片按“Z 字形”在 7 个横条泳道中反复左右折返、上下穿行，读者被迫追踪 37 条连线才能拼接出主逻辑。
2. **双运行模式的物理因果顺序在图面上拧巴**：
   - 在 [`graph.py`](../src/pso_workflow/graph.py#L96-L101) 的理想逻辑链中，顺理成章的顺序是：**先规划（Planner）→ 人类确认（HITL）→ 再分头搜索（Track Researcher）→ 算账排位**；
   - 然而在 IDE 原生工具 [`antigravity_run_workflow.py`](../ide_workflows/antigravity_run_workflow.py#L242-L265) 运行时，由于 `run_workflow` 子智能体在沙箱内被禁止直接运行终端或擅自联网搜库，工程实现上把全部检索和 `roi_calculator.py` 财务计算提前打包进了 `Phase 1 (prepare-context)`。表现在流程图上，就成了极其反直觉的**“Phase 1 还没规划就已经搜完且算好 16 个产品的账，Phase 2 才开始总规划”**。
3. **画幅过度摊大**：A0（4.68 米宽）被迫将关联信息拉开过远，缺乏“一屏看清主干闭环、旁侧集中查细节”的信息分层。

为此，我们在保留原 A0 详情底稿的基础上，新增了**主辅彻底解耦的 [09_V1_CLEAN_TOPOLOGY_DAG.pdf](../outputs/power_semiconductor_online_testing_2026_2036/09_V1_CLEAN_TOPOLOGY_DAG.pdf)**：左侧主图只画垂直主干与左右两条闭环通道，将全部 7 处 `Context #1–#7` 拼装规则、图论说明与底层模型实证移至右侧独立附表区（零连线跨区交叉），做到 5 秒看懂完整执行脉络。

---

## 二、 Phase 1 上来定死“8 赛道 + 16 种子”合理吗？三层架构批判

> **结论先行**：你指出的“难道不应该是调研后才出的结果吗”**切中了 V1.0 最本质的方法论缺陷**。对于**探索 3–5 年 / 5–10 年未知技术、产品与应用机会**的命题而言，Phase 1 就预先定死赛道与产品种子是**不合理的**。

拆开 [`config/domain_taxonomy.yaml`](../config/domain_taxonomy.yaml)、[`config/research_contract.yaml`](../config/research_contract.yaml) 和 [`src/pso_workflow/nodes/researcher.py`](../src/pso_workflow/nodes/researcher.py#L122-L176) 的真实源码可以看到，V1.0 在开机之前其实预埋了**三层预设**，其合理性截然不同：

| 预设层次 | V1.0 代码中的具体内容 | 合理性判定 | 深度剖析：为什么合理 / 为什么不合理 |
| :--- | :--- | :---: | :--- |
| **L1：研究契约边界与评价权重** | 行业域（电力能源 × 半导体制造）、中国优先→全球跟进、双时间窗（3–5年/5–10年）、四大支柱权重（ROI 35% / 良率 25% / 降本环保 20% / 产业升级 20%）、门禁门槛 | **合理（应当保留）** | 这不是预先下结论，而是明确本次商业调研的“问题定义”和“选品标尺”。没有标尺，智能体就会泛泛写科普。 |
| **L2：写死 8 个二级赛道 (`P1–P4`, `S1–S4`) 与固定检索式** | `domain_taxonomy.yaml` 写死电池、光伏/氢能、特高压/海缆、火电/CCUS、Fab AMC、前道量测、SiC/GaN、先进封装；[`planner.py`](../src/pso_workflow/nodes/planner.py#L60-L85) 还会强制忽略 LLM 产出的检索词，用 YAML 死查询强行覆盖 | **半合理但封闭僵化（重大弊端）** | **唯一好处**是类似咨询框架的 MECE 防漏底线；**致命缺陷**在于彻底锁死了行业版图：凡是不落入这 8 个固定格子里的**新兴赛道或跨界增量**——例如 **AI 智算中心 800V 高压直流供电/浸没液冷在线监测**、**硅光 CPO（Co-Packaged Optics）晶圆级光耦合在线量测**、**高温超导/可控核聚变超导带材临界电流在线无损检测**、**构网型储能与钠/液流长时储能在线电化学阻抗诊断**——从第 0 分钟起就永远无法出现在搜索结果与报告里。 |
| **L3：预埋 16 个 `seed_opportunities` 具象产品及 `roi_baseline` 参数** | 直接把 `OPP-P1-3Y-01`（无氦检漏质谱）等 16 个产品标题、物理原理及 CAPEX/良率提升数字写死在 YAML 中；[`prepare-context`](../src/pso_workflow/cli.py#L305-L330) 在 Phase 1 就算出全部 16 个 `[ROI-CALC]`；[`researcher.py`](../src/pso_workflow/nodes/researcher.py#L149) 还强制覆盖回填 | **不合理（本末倒置）** | 当初这样设计是为了遵循《Agentic Design Patterns》Ch 17（PALMs 确定性算账），物理杜绝大模型胡编财务回报率，保证报告零数值幻觉。<br>**但代价过高**：它把一个**“自下而上发现未知机会（Bottom-Up Discovery）”**的工作流，实质矮化成了**“先画 16 个靶子、再去抓 225 条真实文献做论据填充、由 4 个买家角色挑刺并用 Elo 排位的验证型工作流（Top-Down Validation & Scoring）”**。尽管源码第 178 行留了一句允许额外多留 1 个新发现机会的口子，但受限于 Phase 1 固定搜索词且模式 1 仅打包预设 16 个基准，新机会极难脱颖而出。 |

---

## 三、 V1.0 可复用工程资产 vs V2.0“从零动态发现”升级蓝图

尽管 V1.0 存在“先射箭后画靶”的选题封闭性问题，但我们在 V1.0 中投入构建的**6 项防幻觉与确定性工程底座**依然极其宝贵，应当 **100% 继承到 V2.0**：
1. **Metaso（中国主力）+ Serper（全球主力）+ `r.jina.ai` 全文深抓的双引擎路由器**（含互斥分页、`errCode` 拦截、指数退避）；
2. **SQLite `EvidenceVault` 去重记忆库与 `T1–T4` 权威分级体系**；
3. **封闭引用白名单拦截机制（物理抛弃任何未出现在当轮 Vault 内的 `[EV-...]` 幻觉编号）**；
4. **Python PALMs 财务算账引擎与阶段分域 Strict Context Slicing 隔离机制**；
5. **Stanford STORM 四角色买方拷问与 Ch 21 AI Co-Scientist 瑞士制成对 Elo 排位**；
6. **Ch 4 异构 Critic 反思闭环 + Ch 19 确定性正则核验与防算术漂移重算**。

### V1.0 → V2.0 四项本质级架构重构

为了既**彻底摆脱静态预设赛道与种子限制**，又**绝不放任大模型幻觉胡编投资回报率**，V2.0 将工作流重塑为**四阶段漏斗式动态发现架构（Funnel-Based Bottom-Up Discovery）**：

| 演进维度 | V1.0 预设验证流（旧版） | V2.0 从零动态发现漏斗流（新版） |
| :--- | :--- | :--- |
| **赛道来源** | `domain_taxonomy.yaml` 静态写死 8 条赛道 + 固定查询词 | **Stage 0 广谱侦察（Broad Horizon Recon）**：仅给“电力能源 × 半导体 + 在线测试”宽泛范围，先调用双擎搜索最新 1–2 年行业规划/SEMI 路线图/招标与大厂扩张痛点，再由 LLM 基于真实 `RECON` 证据**自下而上聚类生成 8 条动态赛道**（含明确标识的跨界新兴赛道 `is_emerging_or_cross_cutting`）及专属 CN/GLOBAL 检索式；支持可选 `--hitl` 人工确认。 |
| **机会来源** | 预先写死 16 项 `seed_opportunities` 直接灌入各赛道 | **Stage 1 无种子候选池涌现**：完全移除种子，各赛道智能体依据动态搜索+全文深抓结果，从真实良率损失、工段瓶颈与环保法规中**每赛道自主涌现 3–4 项原始候选机会（总计 ~24–32 个原始候选）**，无实证 `[EV-...]` 支撑的构想不准入池。 |
| **财务防幻觉机制** | 写死单点 `roi_baseline`，Phase 1 预计算导致无法发现新产品 | **Stage 2 证据锚定区间抽取 + 物理边界钳位 + 三档漏斗初筛**：LLM 严禁写单点回报率，只从真实文献/招标区间提取 `capex_cny (low/base/high)` 与 `yield_gain_pct (low/base/high)` 并附带 `parameter_basis` 引用依据；Python 在 `sector_roi_guardrails` 物理上限内强行钳位，确定性算出**乐观 / 基准 / 保守 三档 ROI/Payback/IRR/NPV**，把 ~24–32 个原始候选通过硬核淘汰漏斗（记录明确淘汰理由 `EliminatedCandidate`）筛选收敛为 **Top 16 决选名单**。 |
| **双模式执行序** | 模式 1 先搜完算完再规划，因果顺序别扭 | **Stage 0–7 因果彻底统一**：无论是 IDE 原生 `run_workflow` 还是终端 LangGraph CLI，均严格遵从 **Stage 0 广谱侦察长赛道 → Stage 1 按需动态搜证据涌现候选 → Stage 2 Python 三档区间算账漏斗初筛 → Stage 3 STORM 拷问 → Stage 4 Elo PK → Stage 5 五卷含淘汰解析报告 → Stage 6 Critic 闭环 → Stage 7 Stage-Gate 终审**。 |
