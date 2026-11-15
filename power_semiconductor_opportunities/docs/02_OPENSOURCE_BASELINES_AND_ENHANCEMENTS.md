# GitHub 开源基线项目选型、对比与工程增强说明

本项目没有从零“重复造轮子”，而是严格遵循《Agentic Design Patterns》附录 C 框架选型原则，在对比 GitHub 上主流开源智能体研究框架后，**以 `langchain-ai/open_deep_research` 为核心状态机骨架，融合 `stanford-oval/storm` 的多视角拷问与 `bytedance/deer-flow` 的确定性代码算账沙箱**，并针对工业仪器仪表 B2B 调研痛点进行了 8 项重大修订增强。

---

## 1. GitHub 对标开源项目全景对比

| 开源项目 | 仓库定位与 License | 与《Agentic Design Patterns》契合点 | 原版直接用于工业在线检测调研时的核心短板 |
| :--- | :--- | :--- | :--- |
| **`langchain-ai/open_deep_research`** | LangGraph 官方旗舰深度研究框架（MIT） | 极简清晰地实现了 `Scope -> Supervisor Send() 并行子研究员 -> Strictly Grounded Merger`（Ch 3, Ch 6, Ch 14）。 | 1. 强绑定境外 Tavily/OpenAI，无中国本土深度搜索（Metaso）与中英文双擎路由；<br>2. 缺少工业制造 ROI/Payback 定量财务计算器，商业报告容易流于定性空话；<br>3. 依赖高达 30+ 冗余云 SDK；<br>4. 缺少异构 Critic 循环审校与 100 分制门禁。 |
| **`stanford-oval/storm`** | 斯坦福大学多视角专家访谈调研框架（MIT） | 通过“不同专家视角提问（Perspective-Guided Questioning）”消除单一视角的盲区（Ch 7 多智能体协作）。 | 偏向百科知识综述，缺少投资回报率计算、国产替代生态位分析及结构化契约检验。 |
| **`bytedance/deer-flow`** | LangGraph 多智能体深度探索平台（MIT） | 引入 `Coder` 沙箱执行定量计算、HITL 规划审批与分步可观测性（Ch 5, Ch 13）。 | 偏重全栈 Web 服务与重型容器部署，在 IDE 本地 Python 环境下直接二次编排与离线回放测试较重。 |
| **`google-gemini/gemini-fullstack-langgraph-quickstart`** | Google 官方 LangGraph Deep Research 模版（Apache 2.0） | 实现了搜索 -> Gap 识别 -> 循环追索闭环（Ch 4, Ch 14）。 | 止步于通用单篇报告，无法承载“中国优先→全球跟进 + 3-5y/5-10y + 电力×半导体 8 赛道交叉”的复杂矩阵。 |

---

## 2. 本工作流实施的 8 项核心修订与增强（Enhancements）

1. **轻量级双引擎中文优先路由器（替代单一 Tavily 绑定）**
   - `open_deep_research` 默认以英文网页和 Tavily 为主，导致中国政策（十五五、国网/南网规范、大基金三期、国产半导体产线招标）召回率极低。
   - **增强**：构建 `DualEngineSearchRouter`，以用户已付费的 **秘塔 Metaso (`webpage` + `scholar` + `/reader`)** 攻克中国境内产业政策、招标与中文技术论文，以 **Serper.dev (`search` + `scholar` + `patents`)** 攻克全球 SEMI/IEEE/欧美法规/专利，并内置 `r.jina.ai` 全文兜底与 `errCode` 防呆拦截。
2. **领域本体驱动的正交 8 赛道并行扇出（取代无约束自由发散搜索）**
   - 通过 `config/domain_taxonomy.yaml` 锚定电力能源（`P1-P4`）与半导体制造（`S1-S4`）八大制造环节，杜绝大模型遗漏核心工段（如 SiC 晶圆级动态 KGD 测试、环保气体 $\text{C}_4\text{F}_7\text{N}$ 分解监测、混合键合非接触激光超声检测）。
3. **融合 STORM 四角色买方委员会拷问（`storm_persona_interrogator`）**
   - 借鉴 `stanford-oval/storm` 的多视角范式，将每个机会置入真实中国工厂/晶圆厂采购决策链中，接受 **产线良率 VP、工艺量测总工、EHS 合规总监、CFO 财务守门人** 四方质疑，提炼真痛点与 Spec-in 门槛。
4. **融合 Deer-Flow / PALMs 确定性 Python 经济性引擎（`roi_calculator.py`）**
   - 大模型擅长归纳工艺痛点但极易在 NPV/IRR/Payback 上胡乱心算。所有投资回收期（月）、3 年 ROI、5 年净现值（NPV）与内部收益率（IRR）均交由确定性 Python 财务函数运算并标注 `[ROI-CALC]` 标签。
5. **引入 Book Ch 21 AI Co-Scientist Elo 锦标赛排序（`palms_roi_and_elo_ranker`）**
   - 在多维量化打分基础上进行 LLM 两两配对辩论并动态更新 Elo 积分，输出兼具技术壁垒、高 ROI 与产业升级杠杆的客观机会排行榜。
6. **异构 Producer-Critic 双模型反思闭环（`qwen3.8-max` vs `deepseek-v4-pro`）**
   - 打破同一模型自写自审的确认偏误，专门调度阿里云百炼上的原生推理模型 `deepseek-v4-pro` 担任硬核批评者，发现证据盲区时自动触发 **Corrective RAG** 补搜。
7. **分卷独立 Synthesis 防截断架构 + 100 分制 Stage-Gate 裁判**
   - 将输出拆为 5 份高密度专业卷宗（总览、电力专篇、半导体专篇、ROI与Elo排位、产品技术与产业升级路线图）加上溯源索引与遥测 JSON，每卷分配独立高输出预算，保证高质量不缩水。
8. **双运行模态（独立 LangGraph CLI + Antigravity IDE 原生 `run_workflow` 协同）**
   - 既可通过 `uv run pso-research run` 在终端/LangGraph Studio 独立运行（带 SQLite 断点续跑），也可由 IDE 内的 `ide_workflows/antigravity_run_workflow.py` 直接调用内置编排原语协同执行。
