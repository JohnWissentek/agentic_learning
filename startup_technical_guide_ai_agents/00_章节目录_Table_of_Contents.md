# Startup Technical Guide: AI Agents — 章节目录与内容索引 (Table of Contents)

- **文档标题**：Startup Technical Guide: AI Agents（初创企业 AI 智能体技术指南）
- **发布机构**：Google Cloud / Google for Startups（2025 年 11 月版）
- **总页数**：64 页（含封面、目录、正文第 1–61 页、封底）
- **核心定位**：面向初创企业创始人与工程团队的 AI Agent 全生命周期工程指南，涵盖核心概念、基于 **Agent Development Kit (ADK)** 的代码优先开发、**Google Agentspace** 平台化治理、**MCP / A2A** 开放互操作协议以及基于 **AgentOps / Agent Starter Pack** 的生产级可靠性与安全工程。
- **同目录文件**：
  - 原始 PDF：[startup_technical_guide_ai_agents_final.pdf](./startup_technical_guide_ai_agents_final.pdf)
  - 全文 Markdown 转换版：[startup_technical_guide_ai_agents_full.md](./startup_technical_guide_ai_agents_full.md)
  - 核心概念专题问答与工程深潜：[01_核心概念专题问答_工具调用_编排决策_Runtime与开源RAG.md](./01_核心概念专题问答_工具调用_编排决策_Runtime与开源RAG.md)

---

## 一、全局总览目录（官方目录映射）

| 章节编号 | 英文原版章节标题 | 中文译名 | 文档页码 | PDF 页码 |
| :--- | :--- | :--- | :---: | :---: |
| **Cover** | Startup technical guide: AI agents | 封面 | — | P1 |
| **TOC** | Table of contents | 目录 | — | P2 |
| **Intro** | **Introduction** | **引言：从原型到生产级智能体的工程路线图** | **01** | **P3** |
| **Section 1** | **Core concepts of AI agents** | **第一部分：AI 智能体的核心概念** | **02–24** | **P4–P26** |
| 1.1 | An overview of Google Cloud’s agent ecosystem | Google Cloud 智能体生态系统概览 | 04–08 | P6–P10 |
| 1.2 | Key components of every agent | 每个智能体的核心组件（模型、工具、数据/记忆、编排、运行时） | 09–16 | P11–P18 |
| 1.3 | The role of grounding in agentic systems | 事实锚定（Grounding）在智能体系统中的作用 | 17–22 | P19–P24 |
| — | Key takeaways: Choosing your AI agent’s components | 第一部分核心要点总结：如何选择智能体组件 | 23 | P25 |
| **Section 2** | **How to build AI agents** | **第二部分：如何构建 AI 智能体** | **25–47** | **P27–P49** |
| 2.1 | A complete toolkit for building AI agents | 构建 AI 智能体的完整工具链（ADK、MCP、Agent Engine、A2A） | 27–39 | P29–P41 |
| 2.2 | A step-by-step guide: Defining an LLM agent | 分步实战指南：定义一个 LLM 智能体（Software Bug Assistant） | 40–42 | P42–P44 |
| 2.3 | Govern and scale your agent workforce with Google Agentspace | 使用 Google Agentspace 治理与扩展智能体团队 | 43–44 | P45–P46 |
| 2.4 | Other options for building agents | 构建智能体的其他工具（Gemini CLI 与 Firebase Studio） | 45 | P47 |
| — | Key takeaways: From build to scale | 第二部分核心要点总结：从构建到规模化扩展 | 46 | P48 |
| **Section 3** | **Ensuring AI agents are reliable and responsible** | **第三部分：确保 AI 智能体的可靠性与负责任运行** | **48–57** | **P50–P59** |
| 3.1 | AgentOps: A framework for production-ready agents | AgentOps：面向生产级智能体的工程与评估框架 | 50–53 | P52–P55 |
| 3.2 | Build responsible and secure AI agents with AgentOps | 使用 AgentOps 构建负责任且安全的 AI 智能体 | 54–55 | P56–P57 |
| — | Key takeaways: Building reliable agents | 第三部分核心要点总结：构建高可靠智能体 | 56 | P58 |
| **Outro** | **More from Google’s full AI stack** | **拓展：Google 全栈 AI 生态精选（Nano Banana Pro / Veo / Imagen）** | **58** | **P60** |
| **Conclusion** | **Conclusion** | **结语：以严谨工程纪律构建下一代智能系统** | **59** | **P61** |
| **Resources** | **Resources** | **附录：工具、服务与开发资源词典（A–Z）** | **60–61** | **P62–P63** |

---

## 二、分章节详细目录与核心内容提要

### 引言：Introduction（文档第 01 页 / PDF P3）

- **The focus of this guide（指南核心聚焦）**：聚焦于 Google 开源代码优先框架 **Agent Development Kit (ADK)**、运维自动化脚手架 **Agent Starter Pack** 以及无代码企业级智能体平台 **Google Agentspace**，同时兼容 Genkit、LangChain、CrewAI 等生态。
- **How to use this guide（阅读路径指引）**：
  - 初识智能体 → 阅读 **Section 1** 掌握核心架构概念；
  - 准备动手开发 → 跳转 **Section 2** 使用 ADK 构建首个智能体；
  - 已完成原型 → 深入 **Section 3** 实现安全、稳定与规模化生产部署；
  - 快速原型与扶持支持 → 使用 Gemini Kit 并申请 Google for Startups Cloud Program。

---

### 第一部分：Section 1 — Core concepts of AI agents（文档第 02–24 页 / PDF P4–P26）

- **导读与播客提示词（文档第 03 页 / PDF P5）**
  - 提供基于 NotebookLM 生成本章节技术播客的完整 Prompt 模板。

#### 1.1 An overview of Google Cloud’s agent ecosystem（Google Cloud 智能体生态系统概览，文档第 04–08 页 / PDF P6–P10）
- **三大路径与开放互操作底座（MCP & A2A 协议）**（文档第 04 页 / PDF P6）
- **路径一：Build your own agents（自主构建定制智能体）**（文档第 05–06 页 / PDF P7–P8）
  - **Agent Development Kit (ADK)**：面向开发者的代码优先（Code-first）自定义开发框架（多步编排、自定义工具、记忆集成、内置评估与可观测性、容器化可移植部署、多智能体协作）。
  - **Google Agentspace**：面向应用优先（Application-first）与非技术人员的无代码设计与企业智能体编排平台（多模态企业搜索、预置 Deep Research / Idea Generation 智能体、无代码 Agent Designer）。
- **路径二：Use Google Cloud agents（使用 Google Cloud 预置托管智能体）**（文档第 06–08 页 / PDF P8–P10）
  - **Gemini Code Assist**：贯穿软件研发全生命周期的编码智能体（IDE 插件、Gemini CLI 终端、GitHub PR 自动审查、带 HITL 人工确认的多文件重构、跨 Firebase / Colab / BigQuery 集成）。
  - **Gemini Cloud Assist**：面向云架构设计、故障排查（Cloud Observability 日志/指标根因分析）、FinOps 成本优化与安全合规策略生成的云专家智能体。
  - **Gemini in Colab Enterprise**：面向数据科学与机器学习团队的交互式 Python 代码生成、解释与调试工作区。
- **路径三：Bring in partner agents（引入合作伙伴与开源智能体）**（文档第 08 页 / PDF P10）
  - 基于 **Agent Garden**、Google Cloud Marketplace 与 **A2A 协议**集成第三方专业智能体。

#### 1.2 Key components of every agent（每个智能体的五大核心组件，文档第 09–16 页 / PDF P11–P18）
1. **Models: Selection and tuning（模型：选型与微调，文档第 09–11 页 / PDF P11–P13）**
   - **能力-速度-成本三角权衡（Capability, Speed, and Cost）**与多智能体动态模型路由策略：
     - **Gemini 2.5 Flash-Lite**：极致低延迟与低成本，适合早期原型与高吞吐实时任务（翻译、分类）。
     - **Gemini 2.5 Flash**：性价比均衡主力，适合高并发、高质量生产环境。
     - **Gemini 3 Pro**：旗舰级多步复杂推理、智能体编排与前沿代码生成模型。
   - **推理 Token 预算控制（Configurable Reasoning Tokens）**与 **Vertex AI Model Garden**（超 200 款模型统一发现与部署）。
   - **Model tuning（模型微调）**：基于自有高质量数据集定制领域知识与回复风格（区分微调 Fine-tuning 与事实锚定 Grounding 的边界）。
2. **Tools: Enabling agentic action（工具：赋予智能体行动能力，文档第 11 页 / PDF P13）**
   - 涵盖函数（Functions）、内部/第三方 API、数据源查询（Data sources）以及将其他智能体作为工具（Agent-as-a-Tool）。
3. **Data architecture for agentic systems（智能体数据与记忆三层架构，文档第 12–13 页 / PDF P14–P15）**
   - **第 1 层：Long-term knowledge base（长期知识库：锚定与检索）**
     - `Vertex AI Search`（托管向量检索与语义搜索）
     - `Firestore`（Serverless NoSQL 文档库，维护多步长任务实时状态）
     - `Vertex AI Memory Bank (Preview)`（自动从对话历史异步提取并持久化用户长期偏好记忆 `GenerateMemories`）
     - `Cloud Storage`（非结构化原始文档/音视频对象存储）
     - `BigQuery`（Serverless 数据仓库，支撑智能体大规模数据分析查询）
   - **第 2 层：Working memory（工作记忆：会话上下文与短期状态）**
     - `Memorystore`（托管亚毫秒级内存数据库 Redis/Valkey，用于高频/高成本工具调用结果缓存）
   - **第 3 层：Transactional memory（事务记忆：状态管理与行动审计）**
     - `Cloud SQL`（单区域强一致关系型数据库，记录支付、开通服务等关键操作的 ACID 审计日志）
     - `Cloud Spanner`（全球分布式强一致关系型数据库，支撑跨洲多区域零冲突并发事务）
4. **Agent orchestration: The executive function（智能体编排：执行中枢，文档第 14–15 页 / PDF P16–P17）**
   - **ReAct（Reason + Action）循环机制**：`Reason`（评估目标与当前状态）→ `Act`（调用工具执行动作）→ `Observe`（整合工具返回结果进入下一轮推理）。
   - **实战示例**：使用 ReAct 编排处理客户退款流程（查询退款政策 → 核查订单日期 → 调用退款接口）及运维自愈、销售线索清洗等场景。
5. **Runtime: Deploying agents at scale（运行时：规模化部署智能体，文档第 16 页 / PDF P18）**
   - 生产级运行时三大核心要素：弹性伸缩（Scalability）、安全隔离（Security）、可靠性与监控（Reliability & Monitoring）。
   - 三大部署目标对比：**Vertex AI Agent Engine**（全托管智能体专用运行时）、**Cloud Run**（Serverless 容器平台，按实际请求计费）、**Google Kubernetes Engine (GKE)**（深度架构控制与现有微服务体系融合）。

#### 1.3 The role of grounding in agentic systems（事实锚定在智能体系统中的演进路线，文档第 17–22 页 / PDF P19–P24）
- **演进阶段一：RAG — A foundational first step（基础检索增强生成，文档第 17–18 页 / PDF P19–P20）**
  - `Vertex AI Search` 与 `Vertex AI RAG Engine` 工作流（Ingest → Parse → Chunk → Embed → Store → Retrieve）。
  - **Vector databases: Search by meaning（向量数据库与语义搜索原理）**及鞋企客服语义匹配案例。
- **演进阶段二：GraphRAG — Smarter grounding（基于知识图谱的增强锚定，文档第 19 页 / PDF P21）**
  - 利用知识图谱显式建模实体关联（如医疗助手理解“症状 → 病因 → 治疗方案”层级关系），附 GCP GraphRAG 完整架构图（Cloud Storage + Pub/Sub + Cloud Run + Vertex AI Embedding/Gemini + Cloud Spanner 知识图谱）。
- **演进阶段三：Agentic RAG — Dynamic reasoning and retrieval（智能体动态推理检索，文档第 20–22 页 / PDF P22–P24）**
  - 将智能体从被动接收检索结果转变为主动规划多步检索与工具调用的推理主体。
  - **实战示例 1：实时库存与保修查询**（结合向量库 `product_lookup` 语义识别商品 + 函数调用 `check_inventory` 查实时库存）。
  - **Google Cloud Agentic RAG 工作流与“检索 + 重排（Retrieve and Re-rank）”两步法最佳实践**（`Gemini Embedding` + `Vertex AI Vector Search`）。
  - **实战示例 2：Grounding with Google Search**（5 步闭环：用户提问 → 意图判断是否搜索 → 自动生成搜索词检索网页 → 综合多源结果 → 返回带引用元数据的可验证回答）。
  - **其他锚定方式**：Google Maps 地理空间锚定、企业自有网站/文档数据集锚定。
- **Section 1 核心要点速查表（Key takeaways: Choosing your AI agent’s components，文档第 23 页 / PDF P25）**

---

### 第二部分：Section 2 — How to build AI agents（文档第 25–47 页 / PDF P27–P49）

- **导读与播客提示词（文档第 26 页 / PDF P28）**

#### 2.1 A complete toolkit for building AI agents（构建 AI 智能体的完整工具套件，文档第 27–39 页 / PDF P29–P41）
- **四大核心支柱概览（文档第 27 页 / PDF P29）**：`Agent Development Kit (ADK)`、`Model Context Protocol (MCP)`、`Vertex AI Agent Engine`、`Agent2Agent (A2A) protocol`。
- **Develop with ADK（使用 ADK 开发的四大核心优势，文档第 28–29 页 / PDF P30–P31）**：
  1. 构建复杂的多智能体协同系统（Multi-agent by design）；
  2. 无缝集成现有工具、数据源与第三方框架（Notion、Slack、LangChain、LlamaIndex、LangGraph、CrewAI）；
  3. 从第一天起保障质量与可靠性（内置可观测性、完整执行轨迹追踪与量化评估）；
  4. 基于 FastAPI 标准容器化封装，随处可部署。
- **ADK core: Agent architectures（ADK 三大核心智能体基类与架构模式，文档第 29–32 页 / PDF P31–P34）**：
  1. **`LlmAgent`（LLM 驱动智能体）**：非确定性、动态推理、工具调用与子智能体移交（Transfer）。
  2. **`Workflow Agents`（确定性工作流编排智能体）**：
     - `SequentialAgent`（顺序执行智能体，含网页抓取与摘要串联代码示例）；
     - `ParallelAgent`（并行执行智能体，含多源并发检索代码示例）；
     - `LoopAgent`（循环迭代智能体，含“生成包含指定数量香蕉的图片并视觉校验计数”迭代退出代码示例）。
  3. **`CustomAgent`（继承 `BaseAgent` 的自定义 Python 逻辑智能体）**：通过重写 `_run_async_impl` 实现特定硬编码规则流。
- **ADK orchestration: Implementing the ReAct loop（ADK 如何原生实现 ReAct 循环，文档第 32 页 / PDF P34）**
- **ADK tools: A framework for agentic action（ADK 工具设计契约与分类体系，文档第 32–33 页 / PDF P34–P35）**：
  - **模型 API 契约四要素**：函数签名与强制类型注解（Function signature & Python type hints）、语义化文档字符串（Docstring）、结构化字典返回值（如 `{'status': 'success', 'data': ...}`）、会话状态上下文注入（`tool_context: ToolContext`）。
  - **ADK 工具分类**：`Toolset`（工具集打包）、Custom function tools（自定义函数）、Hierarchical and remote tools（`AgentTool` 父子调用 vs 子智能体移交、`RemoteA2aAgent` 远程跨进程调用）、Pre-built and integrated tools（内置 Google Search / Code Execution 及 `LangchainTool` / `CrewaiTool` 包装器）。
- **Standardize with Model Context Protocol (MCP)（使用 MCP 协议标准化工具与数据源接入，文档第 34 页 / PDF P36）**：
  - ADK 智能体既可作为 **MCP Client** 消费外部工具，也可将自身工具封装为 **MCP Server** 暴露给生态；推荐使用开源 **MCP Toolbox for Databases** 连接 BigQuery、Cloud SQL、Spanner、AlloyDB、MySQL、PostgreSQL 等数据库。
- **Manage your data with Google Cloud services（在 ADK 中落地四层记忆架构，文档第 35 页 / PDF P37）**：
  - 长期知识库（`VertexAISearchToolset`、`Firestore`、`Cloud Storage`、`BigQueryToolset`）；
  - 工作记忆（`Memorystore` 缓存）；
  - 事务记忆（`Cloud SQL`、`Cloud Spanner`）；
  - **下一代前沿：Distilled conversational memory（蒸馏式对话记忆）**：通过 `Vertex AI Memory Bank` 自动将冗长历史对话提炼为结构化核心事实（异步提取 + Memory-as-a-Tool 主动写入）。
- **Deploy to the managed runtime with Vertex AI Agent Engine（部署至托管运行时，文档第 36–37 页 / PDF P38–P39）**：
  - `adk api_server` FastAPI 封装与三大目标（Cloud Run、Vertex AI Agent Engine、GKE）架构对比，详解 Gemini 驱动的 Agent Engine 系统架构图。
- **Collaborate with Agent2Agent (A2A) communication（通过 A2A 协议实现跨智能体协同，文档第 38–39 页 / PDF P40–P41）**：
  - 核心概念：**Agent Card**（通过标准 `agent.json` 暴露能力、端点与认证要求）、**Task-oriented architecture**（围绕任务状态流转的异步长时协同）、**Modality agnostic**（跨模态支持）。
  - **客户案例（Customer Story）：BioCorteX** 如何结合 ADK、GraphRAG（440 亿连接生物知识图谱）与 A2A 协议将药物研发假设验证从数年缩短至数天。

#### 2.2 A step-by-step guide: Defining an LLM agent（分步实战：定义 Software Bug Assistant 智能体，文档第 40–42 页 / PDF P42–P44）
- **步骤 1：Define the agent’s identity（定义身份：`model`、`name`、`description`）**
- **步骤 2：Guide the agent with instructions（编写精准的 `instruction` 提示词，防范 Context Poisoning，遵循“简短且边界清晰”原则）**
- **步骤 3：Equip the agent with tools（装配工具：结合 MCP Toolbox for Databases、GitHub MCP Server、LangChain StackExchange 工具、Google Search Agent-as-a-Tool）**
- **步骤 4：Complete the development lifecycle（完整架构图解析与生命周期闭环）**
- **客户案例（Customer Story）：Box** 如何使用 ADK 与 A2A 协议构建连接 Box Intelligent Content Cloud 的企业内容智能体。

#### 2.3 Govern and scale your agent workforce with Google Agentspace（使用 Google Agentspace 治理与扩展智能体团队，文档第 43–44 页 / PDF P45–P46）
- 打通企业数据孤岛（内置 Jira、SharePoint、ServiceNow 等连接器与多模态企业搜索）；
- 赋能业务专家通过无代码 **Agent Designer** 创建专属智能体；
- 通过 **Agent Gallery** 统一纳管 ADK 代码智能体、无代码智能体与第三方智能体。
- **客户案例（Customer Story）：Zoom** 如何将 Zoom AI Companion 与 Google Agentspace 及 A2A 协议集成，根据 Gmail 上下文自动协商并安排 Zoom 会议。

#### 2.4 Other options for building agents（其他智能体构建与全栈加速工具，文档第 45 页 / PDF P47）
- **Experiment with Gemini CLI**：终端开源 AI 智能体（支持 100 万 Token 上下文、免费高频额度、本地代码理解与自动化构建）。
- **Accelerate development with Firebase Studio**：AI 驱动的云端全栈开发环境（从模板/自然语言提示词生成前端 UI、后端逻辑、模拟器预览到一键部署至 Cloud Run / Firebase Hosting）。
- **Section 2 核心要点速查表（Key takeaways: From build to scale，文档第 46 页 / PDF P48）**

---

### 第三部分：Section 3 — Ensuring AI agents are reliable and responsible（文档第 48–57 页 / PDF P50–P59）

- **导读、播客提示词与 OpenTelemetry 可观测性提示（文档第 49 页 / PDF P51）**

#### 3.1 AgentOps: A framework for production-ready agents（AgentOps：生产级智能体运维与四层评估框架，文档第 50–53 页 / PDF P52–P55）
- **告别“凭感觉测试（Vibe-testing）”：四层系统化评估体系（A systematic framework for agent evaluation）**（文档第 50–51 页 / PDF P52–P53）：
  - **Layer 1: Component-level evaluation（组件级确定性单元测试）**：针对 Python/Java 自定义工具函数的 `pytest` 单元测试（`tests/unit/`）。
  - **Layer 2: Trajectory evaluation（轨迹级过程正确性评估）**：验证 ReAct 循环中的推理假设（Reason）、工具选择与参数生成（Act）、观察整合（Observe），结合 Google Cloud Trace 可视化与 `tests/integration/` 黄金轨迹集回归测试。
  - **Layer 3: Outcome evaluation（结果级语义正确性评估）**：评估最终回复的事实锚定度（Grounding verification）、相关性与安全性，集成 **Vertex AI Gen AI Evaluation Service** 与 BigQuery 人工反馈日志。
  - **Layer 4: System-level monitoring（生产环境系统级持续监控）**：基于 OpenTelemetry、Cloud Logging、BigQuery 与 Looker Studio 监控生产环境延迟、成本、错误率与 ReAct 循环步数分布。
- **AgentOps toolkit: ADK and Agent Starter Pack（一键生成生产级智能体工程：`uvx agent-starter-pack create`，文档第 52–53 页 / PDF P54–P55）**：
  - **Agent Starter Pack 架构图与五大内置组件**：IaC 基础设施模板（Terraform）、自动化 CI/CD 流水线（Cloud Build `cloudbuild.yaml`）、全链路可观测性（Cloud Trace + Cloud Logging + BigQuery + Looker Studio）、RAG 数据管线组件、Vertex AI 自动化评估集成。
  - **Better together: ADK 与 Agent Starter Pack 五步协同工作流**：
    1. 使用 Agent Starter Pack 一键初始化工程脚手架；
    2. 使用 ADK 编写核心智能体逻辑与工具；
    3. 提交代码触发 CI/CD 自动化流水线；
    4. 流水线自动构建容器并针对黄金测试集运行量化评估；
    5. 评估达标后自动部署至生产环境。

#### 3.2 Build responsible and secure AI agents with AgentOps（构建负责任且安全的 AI 智能体，文档第 54–55 页 / PDF P56–P57）
- **生成式 AI 常见风险与技术/流程防护矩阵图**（参照 Google **Secure AI Framework (SAIF)**）：涵盖性能/安全偏离、恶意滥用、能力误导、社会偏见放大、过早不安全部署、信息危害/幻觉等六大风险维度的缓解措施。
- **ADK + Agent Starter Pack 纵深防御（Defense-in-depth）三大支柱**：
  1. **安全基础设施与最小权限访问控制（Secure infrastructure & IAM least privilege）**：Terraform 自动化配置 Cloud Run 与 IAM 角色边界；
  2. **输入输出护栏与自动化安全测试（Guardrails & CI/CD security testing）**：防范提示词注入（Prompt Injection）与有害输出过滤；
  3. **全链路审计与合规（Comprehensive auditing and compliance）**：将每一次思考（Thought）与工具调用（Tool Call）通过日志路由沉淀至 BigQuery 形成不可篡改审计轨迹。
- **Section 3 核心要点速查表（Key takeaways: Building reliable agents，文档第 56 页 / PDF P58）**

---

### 拓展、结语与附录资源（文档第 58–61 页 / PDF P60–P64）

- **More from Google’s full AI stack（Google 全栈视觉与多模态模型精选，文档第 58 页 / PDF P60）**
  - **Gemini 3 Pro Image (Nano Banana Pro)**：高价值生产级图像生成、多图融合、角色一致性保持与自然语言局部编辑模型（搭配 Nano Banana 用于快速低延迟探索）。
  - **Veo and Imagen**：前沿文本生成视频与高质量图像生成模型。
- **Conclusion（结语，文档第 59 页 / PDF P61）**
- **Resources（术语与官方资源速查词典 A–Z，文档第 60–61 页 / PDF P62–P63）**
  - 收录 34 项核心工具、协议与云服务定义：`AdkApp`、`Agent Development Kit (ADK)`、`Agent2Agent (A2A)`、`Agent Starter Pack`、`BigQuery`、`Check grounding API`、`Cloud Run`、`Cloud SQL`、`Cloud Spanner`、`Cloud Storage`、`Colab Enterprise`、`Container Registry`、`Firestore`、`Gemini 2.5 Flash Image (Nano Banana)`、`Gemini CLI`、`Gemini Code Assist`、`Gemini Cloud Assist`、`Gemini models`、`Gen AI Evaluation Service`、`Google AI Studio`、`Google Cloud Observability`、`Google Kubernetes Engine (GKE)`、`GraphRAG`、`Imagen`、`MCP Toolbox for Databases`、`Memorystore`、`Model Context Protocol (MCP)`、`Model evaluation in Vertex AI`、`Model Garden on Vertex AI`、`Model tuning`、`Multi-turn / Conversational Search`、`Safety and content filters`、`Vertex AI Agent Builder`、`Vertex AI Agent Engine`、`Vertex AI Platform`、`Vertex AI RAG Engine`、`Vertex AI Search`、`Vertex AI Studio`、`Vertex AI Vector Search`。

