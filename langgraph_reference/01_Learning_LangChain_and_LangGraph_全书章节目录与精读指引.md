# 《Learning LangChain & LangGraph》(O'Reilly) — 全书章节目录与核心架构索引

- **英文书名**：*Learning LangChain: Building AI and LLM Applications with LangChain and LangGraph*
- **作者**：**Mayo Oshin & Nuno Campos**（Nuno Campos 为 **LangGraph 总架构师与核心作者**）
- **出版机构**：O'Reilly Media（共 297 页）
- **本地 PDF 文件**：[learning-langchain-building-ai-and-llm-applications-with-langchain-and-langgraph-1_compress.pdf](./learning-langchain-building-ai-and-llm-applications-with-langchain-and-langgraph-1_compress.pdf)
- **配套官方实战课本**：[00_LangGraph_从原理到实战完整指南与目录索引.md](./00_LangGraph_从原理到实战完整指南与目录索引.md)（含 `langchain-academy` 30 节全量 Markdown 与源码）

---

## 一、 全局总览目录（全书 11 章官方页码映射）

| 章节 | 英文原版标题 | 中文译名与核心定位 | PDF 页码 | 重点推荐度 |
| :--- | :--- | :--- | :---: | :---: |
| **Preface** | **Preface** | **前言：大模型微调分类、提示词工程与工具调用基石** | **P11–P28** | ⭐⭐⭐ |
| **Chapter 1** | **LLM Fundamentals with LangChain** | **第 1 章：LangChain 大模型基础与 Runnable 编排接口** | **P29–P50** | ⭐⭐⭐⭐ |
| **Chapter 2** | **RAG Part I: Indexing Your Data** | **第 2 章：RAG（上）：数据索引构建与高级优化（MultiVector / RAPTOR / ColBERT）** | **P51–P84** | ⭐⭐⭐⭐⭐ |
| **Chapter 3** | **RAG Part II: Chatting with Your Data** | **第 3 章：RAG（下）：查询改写（RAG-Fusion / HyDE）、查询路由与 Text-to-SQL** | **P85–P122** | ⭐⭐⭐⭐⭐ |
| **Chapter 4** | **Using LangGraph to Add Memory to Your Chatbot** | **第 4 章：初识 LangGraph：`StateGraph` 构建与消息裁剪/过滤/合并** | **P123–P142** | ⭐⭐⭐⭐⭐ |
| **Chapter 5** | **Cognitive Architectures with LangGraph** | **第 5 章：基于 LangGraph 的认知架构分级（单次调用 $\rightarrow$ 链 $\rightarrow$ 路由器）** | **P143–P162** | ⭐⭐⭐⭐⭐ |
| **Chapter 6** | **Agent Architecture** | **第 6 章：智能体架构：Plan-Do 循环、强制首步工具调用与海量工具动态过滤** | **P163–P182** | ⭐⭐⭐⭐⭐ |
| **Chapter 7** | **Agents II** | **第 7 章：高阶智能体：自我反思（Reflection）、子图嵌套（Subgraphs）与 Supervisor 多智能体** | **P183–P198** | ⭐⭐⭐⭐⭐ |
| **Chapter 8** | **Patterns to Make the Most of LLMs** | **第 8 章：生产级控制模式：结构化输出、流式传输、4 种人工介入模式与并发冲突处理** | **P199–P218** | ⭐⭐⭐⭐⭐ |
| **Chapter 9** | **Deployment: Launching Your AI Application into Production** | **第 9 章：生产部署：LangGraph Platform API、本地测试与安全防护** | **P219–P242** | ⭐⭐⭐⭐ |
| **Chapter 10** | **Testing: Evaluation, Monitoring, and Continuous Improvement** | **第 10 章：全生命周期测试与评估：Self-Corrective RAG、黄金数据集与端到端轨迹评估** | **P243–P278** | ⭐⭐⭐⭐⭐ |
| **Chapter 11** | **Building with LLMs** | **第 11 章：LLM 交互产品形态：协同编辑（Canvas）与环境计算（Ambient Agents）** | **P279–P286** | ⭐⭐⭐ |

---

## 二、 针对你的核心问题：全书最值得精读的“黄金章节”速查指南

结合你之前提出的**“RAG 内部硬编码与模型边界”**、**“智能体编排那层窗户纸”**以及**“LangGraph 如何精准控制调用步骤与上下文装配”**三大问题，本书给出了极为硬核的解答。以下是可以直接翻阅的精确页码定位：

### 1. 想彻底搞懂“编排的四个确定性等级” $\longrightarrow$ 直奔 **Chapter 5（P143–P162）**
作者 Nuno Campos 在第 144 页提出了一个极其精辟的概念——**“自主性与确定性的权衡光谱（Autonomy vs. Determinism Spectrum）”**，将所有 LLM 应用拆解为 4 种递进的认知架构：
- **Architecture #1: LLM Call（单次调用，P146）**：固定代码准备好上下文，只调一次 LLM；
- **Architecture #2: Chain（确定性链，P149）**：固定顺序调多次 LLM（例如先调 LLM 把自然语言转 SQL，再用硬编码执行 SQL，再调 LLM 解释结果），**步骤顺序 100% 由硬编码决定**；
- **Architecture #3: Router（语义路由器，P153）**：由 LLM 决定**下一步走哪条分支**（比如判断问题属于财务库、法务库还是技术库），但分支集合是硬编码锁死的；
- **Architecture #4: State Machine / Agent（状态机与智能体，Chapter 6 P163）**：把“决定走哪条分支”加上了**循环（Cycle）**，允许大模型根据工具返回结果决定是否再来一轮。

### 2. 想精准控制“工具调用顺序”与“工具过多选不准” $\longrightarrow$ 直奔 **Chapter 6（P171–P180）**
这两节直接回答了你问的*“怎么让 LangGraph 比手写循环更受控、更准确”*：
- **Always Calling a Tool First（强制第一步必须调指定工具，P171–P175）**：
  - 在很多严肃场景（如你的合同审查或故障诊断），我们**绝不允许**大模型一上来就自由发挥，而是要求第 1 步必须先调用特定检索工具。
  - 书中第 172 页展示了如何用**硬编码节点 `first_model`** 直接构造或强制生成工具调用，跳过大模型的盲猜阶段，确保起手动作 100% 确定。
- **Dealing with Many Tools（当工具超过 10~20 个时怎么防选错？P176–P180）**：
  - 当挂载的工具过多时，大模型极易选错函数或填错参数。
  - 书中第 177 页给出了工业级解法：**在进入 LLM 节点前，先加一个 `select_tools` 节点（用 Embedding 向量检索或轻量级分类）**，每次只把与当前任务最相关的 3~5 个工具动态绑定（`model.bind_tools(selected_tools)`）给大模型！

### 3. 想精准控制“上下文装配（裁剪、过滤、合并）” $\longrightarrow$ 直奔 **Chapter 4（P135–P141）**
专门讲解在调用大模型前如何对 `messages` 做外科手术：
- **`trim_messages`（按 Token 预算精确裁剪，P135）**：设置 `strategy="last"`、`include_system=True`、`start_on="human"`，确保上下文永不超窗，且绝不截断半截工具调用；
- **`filter_messages`（按类型/ID/名称精准过滤，P138）**：比如在某个节点故意隐藏掉前序其他子 Agent 产生的 `ToolMessage`，只给当前模型看 `HumanMessage` 和 `AIMessage`；
- **`merge_message_runs`（合并连续同角色消息，P140）**：防止连续两条 `HumanMessage` 或 `SystemMessage` 违反部分大模型 API 的交替格式校验。

### 4. 想掌握“多智能体嵌套”与“人工介入 4 大模式” $\longrightarrow$ 直奔 **Chapter 7 & 8（P183–P214）**
- **Reflection（自我反思与二审挑刺循环，P183–P188）**：用 `generate` 节点 + `reflect`（挑刺）节点构成的固定循环，完全对应合同审查里的“一审生成意见 $\rightarrow$ 二审合伙人挑刺打回修改”；
- **Subgraphs（子图状态隔离与转换，P189–P193）**：详解当父图与子图拥有完全不同的 `State Schema` 时，如何用包装函数做上下文出入参转换；
- **Human-in-the-Loop 四大模式（P207–P214）**：
  1. **Approve or Reject（批准或拒绝，P209）**：在危险工具前暂停，拒绝则直接路由到结束或重规划；
  2. **Edit Graph State（人工直接修改状态快照，P210）**：人类直接改写 `state` 里的消息或参数后继续；
  3. **Review Tool Calls（审查并修改待执行的工具参数，P211）**：在工具执行前人工修正参数；
  4. **Validating Human Input（校验人类输入，P212）**。

---

## 三、 分章节详细三级目录（含精确 PDF 页码）

### Preface（前言，P11–P28）
- Brief Primer on LLMs（大模型简明导论，P13）
  - Instruction-Tuned LLMs（指令微调模型，P16）
  - Dialogue-Tuned LLMs（对话微调模型，P16）
  - Fine-Tuned LLMs（领域微调模型，P17）
- Brief Primer on Prompting（提示词工程简明导论，P17）
  - Zero-Shot Prompting（零样本提示，P18）
  - Chain-of-Thought（思维链 CoT，P19）
  - Retrieval-Augmented Generation（检索增强生成 RAG，P20）
  - Tool Calling（工具调用，P20）
  - Few-Shot Prompting（少样本提示，P22）
- LangChain and Why It’s Important（为什么需要 LangChain 与 LangGraph，P22）
- What to Expect from This Book（本书内容导览，P24）

---

### Chapter 1. LLM Fundamentals with LangChain（LangChain 大模型基础，P29–P50）
- Getting Set Up with LangChain（环境搭建，P31）
- Using LLMs in LangChain（ChatModel 标准接口调用，P32）
- Making LLM Prompts Reusable（提示词模板化 `ChatPromptTemplate`，P35）
- Getting Specific Formats out of LLMs（强制输出特定结构化格式，P41）
  - JSON Output（`with_structured_output` 与 Pydantic 强类型约束，P42）
  - Other Machine-Readable Formats with Output Parsers（解析器，P43）
- Assembling the Many Pieces of an LLM Application（组装大模型应用组件，P44）
  - Using the Runnable Interface（统一接口：`invoke` / `batch` / `stream`，P44）
  - Imperative Composition（命令式组合：`@chain` 装饰器，P46）
  - Declarative Composition（声明式组合：LCEL 管道语法 `|`，P48）

---

### Chapter 2. RAG Part I: Indexing Your Data（RAG 上篇：数据索引与高级建库优化，P51–P84）
- The Goal: Picking Relevant Context for LLMs（核心目标：为 LLM 挑选最相关的上下文，P52）
- Embeddings: Converting Text to Numbers（向量嵌入：将文本转化为数字，P53）
  - Embeddings Before LLMs（前大模型时代的词向量，P53）
  - LLM-Based Embeddings（基于大模型的稠密向量，P55）
  - Semantic Embeddings Explained（高维语义空间解析，P55）
- Converting Your Documents into Text（文档加载与文本解析，P58）
- Splitting Your Text into Chunks（文本分块 `RecursiveCharacterTextSplitter`，P60）
- Generating Text Embeddings（批量生成文本向量，P64）
- Storing Embeddings in a Vector Store（存入向量数据库，P67）
  - Getting Set Up with PGVector（配置 PostgreSQL `pgvector`，P68）
  - Working with Vector Stores（增删查操作，P69）
- Tracking Changes to Your Documents（文档增量同步：`RecordManager` 去重与变更追踪，P72）
- **Indexing Optimization（工业级索引优化三大杀器，P76）**
  - **MultiVectorRetriever（多向量检索器：用摘要块/假设问题建向量索引，命中后返回完整原始父文档/表格，P77）**
  - **RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval（树状递归聚类摘要索引：兼顾底层细节与顶层跨文档问题，P81）**
  - **ColBERT: Optimizing Embeddings（迟交互多向量模型：解决传统稠密向量对专有名词不敏感痛点，P82）**

---

### Chapter 3. RAG Part II: Chatting with Your Data（RAG 下篇：高级检索策略与查询路由，P85–P122）
- Introducing Retrieval-Augmented Generation（基础检索与生成串联，P85）
  - Retrieving Relevant Documents（检索相关文档，P87）
  - Generating LLM Predictions Using Relevant Documents（基于检索结果生成回答，P91）
- **Query Transformation（四大查询转换与改写技术，P96）**
  - **Rewrite-Retrieve-Read（先改写口语问题 $\rightarrow$ 再检索 $\rightarrow$ 再阅读，P96）**
  - **Multi-Query Retrieval（单问题裂变为多个不同角度的子查询并发检索，P99）**
  - **RAG-Fusion（多查询检索 + 倒数秩融合 RRF 重排算法，P102）**
  - **Hypothetical Document Embeddings / HyDE（先让 LLM 生成一段假设答案，用假设答案的向量去搜真实文档，P106）**
- **Query Routing（查询路由分发，P109）**
  - **Logical Routing（逻辑路由：利用 Function Calling / Structured Output 将问题路由至不同数据源，P109）**
  - **Semantic Routing（语义路由：直接计算问题向量与预设 Prompt 模板的余弦相似度做极速路由，P112）**
- **Query Construction（结构化查询构建，P115）**
  - **Text-to-Metadata Filter（自然语言自动转向量库 Metadata 过滤条件 `SelfQueryRetriever`，P115）**
  - **Text-to-SQL（自然语言转数据库 SQL 查询与安全执行，P118）**

---

### Chapter 4. Using LangGraph to Add Memory to Your Chatbot（LangGraph 入门与上下文记忆手术，P123–P142）
- Building a Chatbot Memory System（构建对话记忆系统，P124）
- Introducing LangGraph（为什么需要 LangGraph 状态图，P126）
- Creating a `StateGraph`（从零创建 `StateGraph`、定义 `State`、添加节点与边，P129）
- Adding Memory to `StateGraph`（挂载 Checkpointer 实现持久化与多会话隔离，P133）
- **Modifying Chat History（精准装配与修改上下文历史的三大工具，P135）**
  - **Trimming Messages（`trim_messages` 按 Token 窗口裁剪，P135）**
  - **Filtering Messages（`filter_messages` 按角色/ID/名称精准过滤，P138）**
  - **Merging Consecutive Messages（`merge_message_runs` 合并连续同角色消息，P140）**

---

### Chapter 5. Cognitive Architectures with LangGraph（基于 LangGraph 的认知架构设计，P143–P162）
- 自主性与确定性权衡矩阵（Autonomy vs. Determinism，P144）
- Architecture #1: LLM Call（架构 1：单步大模型调用，P146）
- Architecture #2: Chain（架构 2：固定顺序多步调用链，P149）
- Architecture #3: Router（架构 3：带条件边 `add_conditional_edges` 的动态分支路由，P153）

---

### Chapter 6. Agent Architecture（智能体核心架构与工具控制，P163–P182）
- The Plan-Do Loop（规划-执行循环的本质，P164）
- Building a LangGraph Agent（用 `StateGraph` + `ToolNode` + 条件边手搭 ReAct 智能体，P167）
- **Always Calling a Tool First（工程硬控：强制第一步必须调用指定工具，P171）**
- **Dealing with Many Tools（工程硬控：当工具数量庞大时，通过前置语义检索节点动态过滤挂载工具集，P176）**

---

### Chapter 7. Agents II（高阶多智能体与反思架构，P183–P198）
- **Reflection（自我反思与批判改进闭环：Generator $\leftrightarrow$ Critiquer 循环，P183）**
- **Subgraphs in LangGraph（子图嵌套与独立状态空间隔离，P189）**
  - Calling a Subgraph Directly（共享状态键时直接将子图作为节点挂载，P190）
  - Calling a Subgraph with a Function（状态键不同时通过包装函数转换出入参并调用子图，P192）
- **Multi-Agent Architectures（多智能体协同架构，P193）**
  - **Supervisor Architecture（主管-专家分发架构完整代码实现，P195）**

---

### Chapter 8. Patterns to Make the Most of LLMs（生产级控制与人机协同模式，P199–P218）
- Structured Output（结构化输出进阶模式，P201）
- Intermediate Output & Streaming（流式输出中间节点状态与逐 Token 流，P204–P206）
- **Human-in-the-Loop Modalities（人工介入的五大核心控制模式，P207）**
  - Resume（断点恢复，P208）
  - Restart（修改输入重跑，P209）
  - Edit Graph State（直接编辑修改图状态快照，P210）
  - Review Tool Calls（拦截并审核/修改工具调用参数，P211）
  - Time Travel / Fork（回溯历史快照并分叉执行，P212）
- **Multitasking LLMs（并发请求冲突处理策略：Reject / Enqueue / Interrupt / Rollback，P214）**

---

### Chapter 9. Deployment: Launching Your AI Application into Production（生产环境部署，P219–P242）
- Prerequisites（模型、向量库、后端 API 与 LangSmith 配置，P219）
- Understanding the LangGraph Platform API（理解 `Assistants`、`Threads`、`Runs`、`Cron Jobs` 数据模型，P228）
- Deploying Your AI Application（编写 `langgraph.json`、本地 CLI 测试与 LangGraph Studio 可视化调试，P232）
- Security（身份认证与访问控制，P241）

---

### Chapter 10. Testing: Evaluation, Monitoring, and Continuous Improvement（测试、评估与持续改进，P243–P278）
- Testing Techniques Across the LLM App Development Cycle（研发全周期测试方法论，P244）
- **The Design Stage: Self-Corrective RAG（设计阶段实战：构建带自我纠错闭环的 Corrective RAG 图，自动评估检索文档相关性并打回重写查询，P245–P251）**
- **The Preproduction Stage（上线前量化评估体系，P252）**
  - Creating Datasets（构建黄金测试集，P252）
  - Defining Evaluation Criteria（定义评估器：精准匹配、非结构化语义评估、LLM-as-a-Judge，P256）
  - Evaluating an Agent’s End-to-End Performance（智能体端到端评估：**最终结果评估 vs. 单步工具选择评估 vs. 完整执行轨迹 Trajectory 评估**，P263–P274）
- Production（生产环境 Tracing 追踪、用户反馈收集与异常监控，P275）

---

### Chapter 11. Building with LLMs（构建下一代 LLM 应用产品形态，P279–P286）
- Interactive Chatbots（交互式对话机器人，P280）
- Collaborative Editing with LLMs（人与 AI 协同编辑工作台架构，P282）
- Ambient Computing（后台事件触发的静默运行智能体 Ambient Agents，P283）

