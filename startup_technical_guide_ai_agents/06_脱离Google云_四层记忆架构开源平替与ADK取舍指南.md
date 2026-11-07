# 脱离 Google Cloud：ADK / A2A 的取舍之道与“四层记忆架构”100% 开源平替落地方案

- **关联文档**：[Startup Technical Guide: AI Agents（初创企业 AI 智能体技术指南）](./startup_technical_guide_ai_agents_full.md)
- **章节索引**：[00_章节目录_Table_of_Contents.md](./00_章节目录_Table_of_Contents.md)（对应 **Section 1.2：Data architecture，P12–P13** 及 **Section 2.1：Manage your data & Distilled memory，P35**）
- **关联参考库**：[LangGraph 从原理到实战完整指南（含 Module 5 长期记忆源码）](../langgraph_reference/00_LangGraph_从原理到实战完整指南与目录索引.md)
- **核心问题**：
  > *“如果我不用 Google 云的 AI 功能，我还需要了解 Google 的 ADK 和 A2A 吗？但是这个 PDF 提到的四层记忆非常好，如何在非 Google 云环境下落地？”*

---

## 一、 核心结论：如何剥离“云厂商绑定”，吸取“黄金架构思想”？

阅读 Google、微软、AWS 等大厂的技术白皮书时，最重要的工程能力是**把“普适的黄金架构思想”与“推销自家云产品的专用 SDK”剥离开来**：

1. **Google ADK（Agent Development Kit）$\longrightarrow$ 不需要学具体语法，直接用 `LangGraph` 替代**
   - 虽然 ADK 本身开源，但它的核心定位是为 Google Cloud 的托管运行时（Vertex AI Agent Engine）引流。
   - ADK 中的 `SequentialAgent`、`ParallelAgent`、`LoopAgent` 和工具契约思想，在 **LangGraph** 中都有更底层、控制力更强且社区规模大十倍以上的原生实现。**工程上精通一套 LangGraph 即可，无需在两套同质化编排框架上分散精力。**
2. **A2A 协议（Agent2Agent Protocol）$\longrightarrow$ 无需写代码，但花 10 分钟掌握其设计概念**
   - **MCP vs. A2A 的精准定位区别**：
     - **MCP（Anthropic 发起）**：解决 **“Agent 如何调用工具/数据源（Tool）”**（主从关系：Agent 是大脑，MCP Server 是手脚）；
     - **A2A（Google 联合 50+ 企业捐献给 Linux 基金会）**：解决 **“不同公司、不同框架编写的两个独立 Agent 如何跨网络对话协作”**（平级外交关系）。
   - **唯一需要记住的核心概念 —— `Agent Card`（`/.well-known/agent.json`）**：每个对外提供服务的 Agent 通过一个标准 JSON 文件声明自己的能力、输入输出模态、认证方式与异步任务（Task）接口。只要你不做跨企业异构 Agent 联邦，在自己系统内部直接用 **LangGraph Subgraphs（子图嵌套）** 即可。
3. **PDF 中的“四层记忆架构”与“四层评估体系” $\longrightarrow$ 100% 跨平台通用，可直接用开源组件 1:1 完美复刻！**

---

## 二、 四层记忆架构：Google Cloud 原版 vs. 100% 免费开源平替对照表

在《Startup Technical Guide: AI Agents》第 12–13 页与第 35 页中，Google 提出了极具工程价值的**智能体四层记忆架构**。剥离 Google Cloud 商业服务后，每一层在 **LangGraph + 开源数据库** 体系中都有完全对标甚至更灵活的免费平替方案：

| 记忆层级 | 核心职责（为什么缺一不可？） | Google Cloud 方案（PDF 原文） | **100% 免费开源平替方案（本地 / 私有云）** | 代码中由谁负责读写？（硬编码 vs. 模型） |
| :--- | :--- | :--- | :--- | :--- |
| **第 1 层：短期工作记忆**<br>*(Working Memory)* | 保存当前正在执行的单次会话/任务的上下文 `messages`、节点间中间变量、断点续传状态，以及高频工具调用缓存。 | `Firestore` + `Memorystore (Redis)` | **LangGraph `PostgresSaver` (`SqliteSaver`) + 本地 `Redis`** | **🟦 100% 硬编码自动读写**<br>LangGraph 每跑完一个节点自动按 `thread_id` 将 `State` 序列化落盘；高频工具加 `@redis_cache` 装饰器。 |
| **第 2 层：长期领域知识库**<br>*(Long-term Knowledge Base)* | 存储企业静态/半静态的客观专业知识（如法律法规、合同范本、设备技术手册），用于事实锚定（Grounding）。 | `Vertex AI Search` / `RAG Engine` + `Cloud Storage` | **`Qdrant` / `Milvus` / `pgvector` + `LightRAG`**<br>*(配 `Qwen3-Embedding` + `Qwen3-Reranker`)* | **🟥 LLM 发起 Tool 调用 $\rightarrow$ 🟦 硬编码混合检索 + 🟨 小模型精排** |
| **第 3 层：蒸馏式跨会话记忆**<br>*(Distilled Conversational Memory)* | **最前沿的一层**：自动从用户过去的冗长聊天记录中，提炼出结构化的“用户偏好、背景事实、历史教训”，跨会话永久记住。 | `Vertex AI Memory Bank` (`GenerateMemories`) | **LangGraph `BaseStore` (`PostgresStore`) + 开源 [`Trustcall`](https://github.com/hinthornw/trustcall) 或 [`Mem0`](https://github.com/mem0ai/mem0)** | **🟦 会话开始时硬编码注入 System Prompt**；<br>**🟥 会话结束/后台异步调轻量 LLM 提炼 JSON 事实并更新入库**。 |
| **第 4 层：强一致事务审计记忆**<br>*(Transactional Memory)* | 记录 Agent 执行过的所有不可逆真实动作（如发起退款、修改合同条款、下发 PLC 控制指令），要求 ACID 强一致与防篡改审计。 | `Cloud SQL` / `Cloud Spanner` | **开源 `PostgreSQL`**<br>*(标准关系型 ACID 事务表)* | **🟦 100% 硬编码在写操作 Tool 函数内部**<br>使用标准 SQL `BEGIN ... COMMIT` 事务写入审计流水表，绝不让大模型直接管账。 |

---

## 三、 极简主义架构：仅用 **1 个开源 PostgreSQL** 统一承载全部四层记忆

许多工程团队担心：“为了实现这四层记忆，难道要在服务器上同时部署维护 Redis、Milvus、Neo4j、MongoDB、MySQL 五六个数据库吗？”

**完全不需要！** 在现代 AI 工程栈中，**仅仅依靠一个安装了扩展插件的开源 `PostgreSQL` 实例**，就能以极低的运维成本把这四层记忆全部装进去（All-in-Postgres 架构）：

```mermaid
flowchart TB
    subgraph App["LangGraph 智能体应用 (Python Runtime)"]
        direction LR
        Node["节点执行与上下文拼装<br/>(Node Functions)"]
        Tool["写操作业务工具<br/>(Write Action Tools)"]
        BgWorker["后台记忆蒸馏节点<br/>(Memory Extraction Node)"]
    end

    subgraph PG["单实例开源 PostgreSQL (All-in-One 四层记忆底座)"]
        direction TB
        L1[("【第 1 层：短期工作记忆】<br/>langgraph-checkpoint-postgres<br/>checkpoints 表：按 thread_id 存储每一步 State 快照<br/>支撑断点续传、人工审批挂起与时间旅行")]
        
        L2[("【第 2 层：长期领域知识库】<br/>pgvector + pg_search (BM25)<br/>knowledge_chunks 表：存储文档向量与全文索引<br/>支撑毫秒级 Hybrid RAG 检索")]
        
        L3[("【第 3 层：蒸馏式跨会话记忆】<br/>LangGraph PostgresStore (JSONB + 向量)<br/>store 表：按 namespace=('memories', user_id)<br/>存储提炼后的用户画像 Profile 与经验事实条目")]
        
        L4[("【第 4 层：强一致事务审计记忆】<br/>标准 ACID 关系表 (action_audit_ledger)<br/>记录 tool_name、入参、修改前后值、批准人、trace_id")]
    end

    Node <-->|"1. 🟦 每步自动读写 Checkpoint"| L1
    Node <-->|"2. 🟦+🟨 RAG 工具混合召回"| L2
    Node <-- "3a. 🟦 会话初读取用户长期偏好" --- L3
    BgWorker -- "3b. 🟥 轻量 LLM 蒸馏聊天记录写入 JSON" --> L3
    Tool -- "4. 🟦 ACID 事务强制记录不可篡改流水" --> L4
```

---

## 四、 重点拆解第 3 层：如何用开源方案复刻 `Vertex AI Memory Bank`（蒸馏式对话记忆）？

在这四层记忆中，第 1、2、4 层大家都比较熟悉，而第 3 层 **“Distilled Conversational Memory（蒸馏式对话记忆，原书 P12 & P35）”** 是让 Agent 具备“越用越懂你”的核心关键。

### 1. 什么是“蒸馏式对话记忆”？
- 如果用户上周跟合同审查 Agent 聊了 50 句，其中提到过一句：*“顺便说一下，我们法务部规定所有采购合同的违约金上限绝对不能超过合同总额的 20%，而且管辖法院必须在上海。”*
- **错误的做法**：下周用户开启新对话（新的 `thread_id`）时，把上周那 50 句冗长的聊天记录全塞进新对话里（Token 爆炸且充满噪音）。
- **蒸馏式记忆（Memory Bank / LangGraph Store）的做法**：
  1. 在上周对话过程中或结束时，通过一个**记忆提取器（Memory Extractor）**，调用轻量级 LLM 把那 50 句废话“蒸馏”成两条高度结构化的 JSON 事实：
     - `{"rule_type": "liability_cap", "preference": "违约金上限不得超过合同总额 20%"}`
     - `{"rule_type": "jurisdiction", "preference": "争议管辖法院必须为买方所在地（上海）"}`
  2. 把这两条干净的 JSON 存入跨会话的 **`PostgresStore`**（绑定在该 `user_id` 命名空间下）。
  3. 下周该用户开启任何新会话时，节点代码自动从 `Store` 中取出这两条规则，拼接到 System Prompt 里！

---

### 2. 代码实战：用 LangGraph `Store` + `PostgresSaver` 完整串联四层记忆

以下代码直接对应我们在 [langgraph_reference/academy_markdown/module-5/](../langgraph_reference/academy_markdown/module-5/memory_agent.md) 中拉取的官方长期记忆模式，展示了如何在同一个 LangGraph 节点中协同使用这四层记忆：

```python
from typing import Annotated, TypedDict
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.store.base import BaseStore
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore

# ================= 1. 初始化基于同一个 PostgreSQL 的多层记忆底座 =================
DB_URI = "postgresql://user:password@localhost:5432/agent_memory_db"

# 【第 1 层：短期工作记忆】按 thread_id 存当前会话每一步的状态快照
checkpointer = PostgresSaver.from_conn_string(DB_URI)

# 【第 3 层：跨会话蒸馏记忆库】按 user_id 存提炼后的长期偏好与事实 (支持语义检索)
long_term_store = PostgresStore.from_conn_string(DB_URI)


# ================= 2. 节点 A：读取长期记忆与知识库，执行推理 =================
def contract_audit_agent_node(
    state: MessagesState, 
    config: RunnableConfig, 
    *, 
    store: BaseStore  # LangGraph 自动注入第 3 层跨会话 Store
):
    # 获取当前用户 ID
    user_id = config["configurable"]["user_id"]
    
    # -----------------------------------------------------------------
    # 🟦 【读取第 3 层：蒸馏式长期记忆】
    # 从 Store 的 ("audit_preferences", user_id) 命名空间下检索该用户的历史审查偏好
    # -----------------------------------------------------------------
    namespace = ("audit_preferences", user_id)
    user_memories = store.search(namespace, query=state["messages"][-1].content, limit=5)
    distilled_rules = "\n".join([f"- {m.value['fact']}" for m in user_memories])

    # -----------------------------------------------------------------
    # 🟦 + 🟨 【读取第 2 层：长期领域知识库 (RAG)】
    # 用 Qwen3-Embedding + pgvector/Qdrant 检索相关法律法规
    # -----------------------------------------------------------------
    statutes = retrieve_from_knowledge_base(state["messages"][-1].content, top_k=3)

    # 🟦 硬编码精准组装当前步骤的上下文
    system_prompt = (
        f"你是资深合同审查专家。\n\n"
        f"【该用户的长期审查偏好（来自第 3 层蒸馏记忆）】\n{distilled_rules or '暂无特殊偏好'}\n\n"
        f"【相关法律法规（来自第 2 层知识库）】\n{statutes}"
    )
    
    response = llm_with_tools.invoke([SystemMessage(content=system_prompt)] + state["messages"])
    return {"messages": [response]}


# ================= 3. 节点 B：异步/后置蒸馏新记忆写入第 3 层 Store =================
def distill_and_save_memory_node(
    state: MessagesState, 
    config: RunnableConfig, 
    *, 
    store: BaseStore
):
    """🟥 调用轻量模型，判断用户刚才的话里有没有需要永久记住的新规则/偏好"""
    user_id = config["configurable"]["user_id"]
    namespace = ("audit_preferences", user_id)
    
    # 让轻量级 LLM (如 Qwen3-8B / Gemini Flash) 从最新对话中提取长期事实
    extracted = lightweight_llm.with_structured_output(MemoryFactSchema).invoke(
        f"请从以下对话中提取用户声明的长期合同审查规则（若无则返回空）：\n{state['messages'][-2:]}"
    )
    
    if extracted.has_new_rule:
        # 🟦 将提炼出的干净事实写入第 3 层跨会话 Store
        store.put(namespace, key=extracted.rule_id, value={"fact": extracted.rule_text})
        
    return {}


# ================= 4. 写操作工具：在工具内部硬编码落实【第 4 层：ACID 事务记忆】 =================
def apply_contract_redline_tool(contract_id: str, clause_no: str, old_text: str, new_text: str) -> str:
    """当需要正式修改合同条款并记录合规审计流水时调用此工具。"""
    # 🟦 【第 4 层：Transactional Memory】100% 硬编码数据库 ACID 事务！
    with pg_connection.cursor() as cur:
        # 1. 更新业务合同表
        cur.execute(
            "UPDATE contracts SET clause_text = %s WHERE id = %s AND clause_no = %s",
            (new_text, contract_id, clause_no)
        )
        # 2. 在同一个 ACID 事务中写入不可篡改的行动审计账本 (System of Record)
        cur.execute(
            """
            INSERT INTO action_audit_ledger (contract_id, clause_no, before_val, after_val, executed_at)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (contract_id, clause_no, old_text, new_text)
        )
        pg_connection.commit()
    return "条款修改已提交，ACID 审计流水已记录。"


# ================= 5. 编译同时挂载【第 1 层 Checkpointer】与【第 3 层 Store】的图 =================
builder = StateGraph(MessagesState)
builder.add_node("audit_agent", contract_audit_agent_node)
builder.add_node("distill_memory", distill_and_save_memory_node)
builder.add_edge(START, "audit_agent")
builder.add_edge("audit_agent", "distill_memory")
builder.add_edge("distill_memory", END)

# 编译时同时传入 checkpointer (第1层短期记忆) 和 store (第3层跨会话长期记忆)！
graph = builder.compile(checkpointer=checkpointer, store=long_term_store)
```

---

## 五、 总结：你的非 Google 云开源智能体黄金技术栈

脱离 Google Cloud 后，你可以直接采用下面这套 **100% 免费开源、可私有化部署在本地 Mac mini 或任意 Linux 服务器** 的顶配架构，完整落地 Google PDF 中的所有高阶设计：

1. **编排与运行时（替代 ADK + Agent Engine）**：**`LangGraph`**
2. **四合一记忆底座（替代 Firestore + Vertex Search + Memory Bank + Cloud SQL）**：
   - 单实例 **`PostgreSQL`**（开启 `pgvector` 扩展）
   - 第 1 层工作记忆：`langgraph-checkpoint-postgres`
   - 第 2 层领域知识 RAG：`Docling`（解析 PDF） + `Qdrant` / `pgvector` + `LightRAG`（知识图谱） + `Qwen3-Embedding` + `Qwen3-Reranker`
   - 第 3 层蒸馏式对话记忆：`LangGraph PostgresStore` + `Trustcall`（或开源 `Mem0`）
   - 第 4 层事务审计记忆：`PostgreSQL` 标准 ACID 事务表
3. **工具标准化协议**：**`MCP (Model Context Protocol)`**
4. **可观测性与评估（替代 Cloud Trace + Vertex Evaluation）**：开源 **`Arize Phoenix`** 或 **`Langfuse`**（原生支持 OpenTelemetry，可在本地 Docker 一键启动，可视化查看每一步 ReAct 轨迹与 Token 消耗）。

