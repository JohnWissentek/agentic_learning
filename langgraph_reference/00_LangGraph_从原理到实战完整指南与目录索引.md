# LangGraph 从原理到实战完整指南与官方参考手册索引

- **目录位置**：`/Users/john/Desktop/agentic_learning/langgraph_reference/`
- **内容构成**：
  1. **官方原版教程与源码库**：[`./langchain-academy/`](./langchain-academy/)（完整拉取自 `github.com/langchain-ai/langchain-academy`，含 Module 0–6 全部 Jupyter Notebooks 与 `studio/` 生产级 `.py` 源码）；
  2. **全量 Markdown 免启动阅读版**：[`./academy_markdown/`](./academy_markdown/)（已将全部 30 节 `.ipynb` 课程无损转换为可直接阅读的 `.md` 文档）；
  3. **五大工业级工作流设计模式（Workflows & Agents）与核心参数速查**（见下文第三、四节）。

---

## 一、 全局阅读导航：Module 0 – Module 6 完整目录映射

你可以直接点击下表中的 **Markdown 阅读版** 链接在编辑器中流畅阅读，或打开对应的 **源码/Notebook** 运行调试：

| 模块 | 章节主题 | Markdown 直接阅读版 | 配套 Studio 生产级 `.py` 源码 / 原版 Notebook | 核心解决什么工程问题？ |
| :--- | :--- | :--- | :--- | :--- |
| **Module 0** | 环境与基础配置 | [basics.md](./academy_markdown/module-0/basics.md) | [basics.ipynb](./langchain-academy/module-0/basics.ipynb) | API 配置、ChatModel 统一接口与搜索工具初始化 |
| **Module 1**<br>*(图编排基石)* | **1.1 最简状态图** | [simple-graph.md](./academy_markdown/module-1/simple-graph.md) | [simple.py](./langchain-academy/module-1/studio/simple.py) | `StateGraph`、`TypedDict`、节点（Node）、普通边与条件边（`add_conditional_edges`） |
| | **1.2 消息链与工具绑定** | [chain.md](./academy_markdown/module-1/chain.md) | [chain.ipynb](./langchain-academy/module-1/chain.ipynb) | 四种消息类型（`Human`/`AI`/`System`/`ToolMessage`）、`bind_tools` 与 `add_messages` 归约器 |
| | **1.3 条件路由（Router）** | [router.md](./academy_markdown/module-1/router.md) | [router.py](./langchain-academy/module-1/studio/router.py) | 使用内置 `ToolNode` 与 `tools_condition` 实现“调工具 or 直接回答”二元路由 |
| | **1.4 ReAct 循环智能体** | [agent.md](./academy_markdown/module-1/agent.md) | [agent.py](./langchain-academy/module-1/studio/agent.py) | 将 `ToolNode` 的输出边连回 `assistant` 节点，形成完整的 `Act -> Observe -> Reason` 闭环 |
| | **1.5 带持久记忆的智能体** | [agent-memory.md](./academy_markdown/module-1/agent-memory.md) | [agent-memory.ipynb](./langchain-academy/module-1/agent-memory.ipynb) | 挂载 `MemorySaver` Checkpointer 与 `thread_id`，实现多轮对话状态自动持久化 |
| | **1.6 本地 Studio 部署预览** | [deployment.md](./academy_markdown/module-1/deployment.md) | [langgraph.json](./langchain-academy/module-1/studio/langgraph.json) | 理解 `langgraph.json` 配置文件结构与图服务化封装 |
| **Module 2**<br>*(状态与上下文精控)* | **2.1 状态 Schema 选型** | [state-schema.md](./academy_markdown/module-2/state-schema.md) | [state-schema.ipynb](./langchain-academy/module-2/state-schema.ipynb) | 对比 `TypedDict`、`dataclass` 与 **`Pydantic BaseModel`（运行时强类型校验）** |
| | **2.2 状态归约器（Reducers）** | [state-reducers.md](./academy_markdown/module-2/state-reducers.md) | [state-reducers.ipynb](./langchain-academy/module-2/state-reducers.ipynb) | 解决并行节点同时修改同一字段的冲突；自定义 Reducer 函数与 `RemoveMessage` 删除指定历史消息 |
| | **2.3 多 Schema 状态隔离** | [multiple-schemas.md](./academy_markdown/module-2/multiple-schemas.md) | [multiple-schemas.ipynb](./langchain-academy/module-2/multiple-schemas.ipynb) | **`PrivateState`（节点间内部传递临时数据）** + **`InputState` / `OutputState`（过滤接口输入输出）** |
| | **2.4 消息裁剪与过滤** | [trim-filter-messages.md](./academy_markdown/module-2/trim-filter-messages.md) | [trim-filter-messages.ipynb](./langchain-academy/module-2/trim-filter-messages.ipynb) | **精准控制上下文长度**：使用 `RemoveMessage`、列表切片或 `trim_messages(max_tokens=...)` |
| | **2.5 自动摘要压缩上下文** | [chatbot-summarization.md](./academy_markdown/module-2/chatbot-summarization.md) | [chatbot.py](./langchain-academy/module-2/studio/chatbot.py) | 当对话超过 N 轮时，条件边自动跳转到 `summarize_conversation` 节点生成摘要并清空旧消息 |
| | **2.6 外部 SQLite 持久化** | [chatbot-external-memory.md](./academy_markdown/module-2/chatbot-external-memory.md) | [chatbot-external-memory.ipynb](./langchain-academy/module-2/chatbot-external-memory.ipynb) | 使用 `SqliteSaver`（生产环境对应 `PostgresSaver`）将 Checkpointer 状态落盘到数据库文件 |
| **Module 3**<br>*(人工门禁与时间旅行)* | **3.1 流式输出与中断** | [streaming-interruption.md](./academy_markdown/module-3/streaming-interruption.md) | [streaming-interruption.ipynb](./langchain-academy/module-3/streaming-interruption.ipynb) | `stream_mode="values"` vs `"updates"`，以及逐 Token 流式输出 `astream_events` |
| | **3.2 静态断点（Breakpoints）** | [breakpoints.md](./academy_markdown/module-3/breakpoints.md) | [agent.py](./langchain-academy/module-3/studio/agent.py) | `interrupt_before=["tools"]`：在执行高危工具前强制暂停，人工确认后传 `None` 继续执行 |
| | **3.3 人工直接修改状态** | [edit-state-human-feedback.md](./academy_markdown/module-3/edit-state-human-feedback.md) | [edit-state-human-feedback.ipynb](./langchain-academy/module-3/edit-state-human-feedback.ipynb) | **`graph.update_state()`**：暂停期间由人类（或外部校验代码）直接修改大模型的参数或插入反馈 |
| | **3.4 节点内部动态断点** | [dynamic-breakpoints.md](./academy_markdown/module-3/dynamic-breakpoints.md) | [dynamic_breakpoints.py](./langchain-academy/module-3/studio/dynamic_breakpoints.py) | `NodeInterrupt` / `interrupt()`：当满足特定代码条件（如金额超限、参数过长）时在函数内部主动挂起 |
| | **3.5 时间旅行（Time Travel）** | [time-travel.md](./academy_markdown/module-3/time-travel.md) | [time-travel.ipynb](./langchain-academy/module-3/time-travel.ipynb) | `get_state_history()` 查看历史每一步快照，指定過去の `checkpoint_id` 分叉（Fork）重跑 |
| **Module 4**<br>*(高级复杂工作流)* | **4.1 节点并行执行（Fan-out/Fan-in）** | [parallelization.md](./academy_markdown/module-4/parallelization.md) | [parallelization.py](./langchain-academy/module-4/studio/parallelization.py) | 一个节点同时连向多个下游节点并发检索（如同时搜维基百科和网页），再用自定义 Reducer 合并排序 |
| | **4.2 子图嵌套（Sub-graphs）** | [sub-graph.md](./academy_markdown/module-4/sub-graph.md) | [sub_graphs.py](./langchain-academy/module-4/studio/sub_graphs.py) | 构建多智能体系统：每个子 Agent 拥有自己独立的 `State` 空间，跑完后只把干净结论汇总回父图 |
| | **4.3 Map-Reduce 动态分发** | [map-reduce.md](./academy_markdown/module-4/map-reduce.md) | [map_reduce.py](./langchain-academy/module-4/studio/map_reduce.py) | **`Send()` API**：当子任务数量在运行前未知时（如一份合同拆出 N 个条款），动态并发启动 N 个节点审查 |
| | **4.4 综合实战：深度研究助手** | [research-assistant.md](./academy_markdown/module-4/research-assistant.md) | [research_assistant.py](./langchain-academy/module-4/studio/research_assistant.py) | 串联“规划师 + 人工批准大纲 + `Send()` 多智能体并行访谈检索 + 报告主编汇总”的旗舰级完整工程 |
| **Module 5**<br>*(跨会话长期记忆)* | **5.1 LangGraph Store 键值/向量库** | [memory_store.md](./academy_markdown/module-5/memory_store.md) | [memory_store.py](./langchain-academy/module-5/studio/memory_store.py) | 区分单会话 `Checkpointer`（短期记忆）与跨会话 `InMemoryStore` / 数据库 `Store`（长期记忆） |
| | **5.2 结构化用户画像记忆** | [memoryschema_profile.md](./academy_markdown/module-5/memoryschema_profile.md) | [memoryschema_profile.py](./langchain-academy/module-5/studio/memoryschema_profile.py) | 用 Pydantic 定义用户 Profile，结合 **[Trustcall](https://github.com/hinthornw/trustcall)** 做增量 JSON Patch 更新而不丢失旧字段 |
| | **5.3 集合式经验记忆库** | [memoryschema_collection.md](./academy_markdown/module-5/memoryschema_collection.md) | [memoryschema_collection.py](./langchain-academy/module-5/studio/memoryschema_collection.py) | 将多条离散事实存入 Collection，支持持续新增与按语义检索 |
| | **5.4 多记忆路由智能体实战** | [memory_agent.md](./academy_markdown/module-5/memory_agent.md) | [memory_agent.py](./langchain-academy/module-5/studio/memory_agent.py) | 完整的 `Task mAIstro` 智能体：在对话中自主决定更新用户画像、待办清单还是操作偏好 |
| **Module 6**<br>*(生产环境部署)* | **6.1–6.4 容器化与高并发处理** | • [creating.md](./academy_markdown/module-6/creating.md)<br>• [connecting.md](./academy_markdown/module-6/connecting.md)<br>• [double-texting.md](./academy_markdown/module-6/double-texting.md)<br>• [assistant.md](./academy_markdown/module-6/assistant.md) | [deployment/](./langchain-academy/module-6/deployment/) | Docker Compose 生产部署、SDK 远程调用、Assistants 多版本配置管理、以及 **Double-Texting 并发冲突策略（`reject` / `enqueue` / `interrupt` / `rollback`）** |

---

## 二、 核心精华提炼：LangGraph 最重要的 5 个高级工程模式（含代码模板）

结合你在阅读 Google PDF 时重点关注的“编排（Orchestration）”与“上下文控制”，以下直接从 `langchain-academy` Module 2–4 中提取出 **5 个最核心的生产级代码范式**：

---

### 范式 1：多 Schema 状态隔离（`OverallState` vs `PrivateState` vs `Input/Output`）
**出处**：[module-2/multiple-schemas.md](./academy_markdown/module-2/multiple-schemas.md)
**解决什么痛点？**
在多步编排中，节点 A 查出了 20 段粗糙的中间参考资料传给节点 B 做筛选，但我们**既不想把这 20 段废话暴露给最终 API 输出，也不想让它污染全局的 `messages`**。

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

# 1. 定义对外输入与输出 Schema（保持接口极其干净）
class InputState(TypedDict):
    contract_clause: str

class OutputState(TypedDict):
    final_legal_opinion: str

# 2. 定义全局内部状态
class OverallState(TypedDict):
    contract_clause: str
    raw_retrieved_chunks: list[str]
    final_legal_opinion: str

# 3. 定义仅在某两个节点之间私密传递的临时状态 (PrivateState)
class PrivateAuditState(TypedDict):
    internal_draft_score: int

def node_1_retrieve(state: InputState) -> OverallState:
    # 只接收干净的 InputState，写出内部状态
    return {"raw_retrieved_chunks": ["法条1...", "法条2..."]}

def node_2_draft(state: OverallState) -> PrivateAuditState:
    # 写入私有状态 internal_draft_score，外部不可见
    return {"internal_draft_score": 85}

def node_3_finalize(state: PrivateAuditState) -> OutputState:
    # 读取私有状态，最终只返回 OutputState 定义的字段！
    return {"final_legal_opinion": f"经内部评分({state['internal_draft_score']})，建议修改如下..."}

# 编译时显式指定 input 和 output Schema，框架会自动过滤掉所有中间字段！
builder = StateGraph(OverallState, input=InputState, output=OutputState)
```

---

### 范式 2：上下文自动摘要压缩（滚动窗口 + `RemoveMessage`）
**出处**：[module-2/chatbot-summarization.md](./academy_markdown/module-2/chatbot-summarization.md) & [module-2/studio/chatbot.py](./langchain-academy/module-2/studio/chatbot.py)
**解决什么痛点？**
当 Agent 跑长周期任务或多轮对话（超过 6 轮）时，如何既记住前面发生的事，又把旧消息从列表里删掉以节省 Token？

```python
from langchain_core.messages import SystemMessage, HumanMessage, RemoveMessage
from langgraph.graph import MessagesState

# 扩展默认 MessagesState，增加一个独立字段存放滚动摘要
class State(MessagesState):
    summary: str

def call_model(state: State):
    # 🟦 硬编码拼装上下文：如果已有历史摘要，把它作为 SystemMessage 放在最前面！
    summary = state.get("summary", "")
    if summary:
        system_msg = f"以下是此前对话与操作的核心摘要：{summary}"
        messages = [SystemMessage(content=system_msg)] + state["messages"]
    else:
        messages = state["messages"]
    
    response = model.invoke(messages)
    return {"messages": [response]}

def summarize_conversation(state: State):
    # 🟥 调用 LLM 将旧消息浓缩进 summary 字段
    summary = state.get("summary", "")
    prompt = f"已有摘要：{summary}\n请结合上面的最新对话更新摘要：" if summary else "请总结上面的对话："
    response = model.invoke(state["messages"] + [HumanMessage(content=prompt)])
    
    # 🟦 关键硬编码操作：生成 RemoveMessage 指令，把除了最后 2 条之外的所有旧消息从状态里彻底删掉！
    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
    return {"summary": response.content, "messages": delete_messages}

# 🟦 硬编码条件边：消息超过 6 条就自动去压缩，否则直接结束
def should_continue(state: State):
    if len(state["messages"]) > 6:
        return "summarize_conversation"
    return "__end__"
```

---

### 范式 3：人工介入直接篡改大模型状态（`update_state`）与时间旅行（Time-Travel）
**出处**：[module-3/edit-state-human-feedback.md](./academy_markdown/module-3/edit-state-human-feedback.md) & [module-3/time-travel.md](./academy_markdown/module-3/time-travel.md)
**解决什么痛点？**
当 Agent 决定调用 `dispatch_control_setpoint(target_temp=500)` 或拟定了一版合同修改词，我们在 `interrupt_before=["tools"]` 处拦住了它。人类工程师发现 `500` 度太高了，应该改成 `450` 度再让它执行，怎么改？

```python
# 1. 启动运行，图在进入 tools 节点前自动暂停挂起
thread = {"configurable": {"thread_id": "1"}}
graph.invoke({"messages": ["把炉温调高"]}, thread)

# 2. 查看当前暂停处的状态快照
current_state = graph.get_state(thread)
last_ai_msg = current_state.values["messages"][-1]

# 3. 🟦 人类工程师/外部校验代码直接修改大模型刚刚生成的 tool_calls 参数！
last_ai_msg.tool_calls[0]["args"]["target_temp"] = 450

# 4. 使用 update_state（因为 ID 相同，add_messages 会原地覆盖那条 AIMessage！）
graph.update_state(thread, {"messages": [last_ai_msg]})

# 5. 传入 None 恢复运行，此时 tools 节点就会按人类改好的 450 度去执行！
graph.invoke(None, thread)
```

---

### 范式 4：Map-Reduce 动态并发拆解（`Send` API）
**出处**：[module-4/map-reduce.md](./academy_markdown/module-4/map-reduce.md) & [module-4/studio/map_reduce.py](./langchain-academy/module-4/studio/map_reduce.py)
**解决什么痛点？**
比如审一份商业合同，事先不知道里面有 15 条还是 40 条。第 1 步解析出 `clauses` 列表后，如何动态启动 N 个并行的 `audit_single_clause` 节点同时审查，最后再汇总到 `generate_report` 节点？

```python
import operator
from typing import Annotated, TypedDict
from langgraph.types import Send
from langgraph.graph import StateGraph, START, END

# 全局状态：注意 audit_results 使用 operator.add 把所有并行节点的返回列表自动合并！
class OverallState(TypedDict):
    contract_text: str
    clauses: list[str]
    audit_results: Annotated[list[dict], operator.add]
    final_report: str

# 单个并行 Worker 节点的输入状态
class ClauseWorkerState(TypedDict):
    clause: str

def split_contract_node(state: OverallState):
    # 拆出 N 个条款
    return {"clauses": ["第一条：...", "第二条：...", "第三条：..."]}

# 🟦 核心动态分发路由函数：返回一组 Send(目标节点名, 给该节点的独立参数)
def continue_to_clause_auditors(state: OverallState):
    return [Send("audit_single_clause_node", {"clause": c}) for c in state["clauses"]]

def audit_single_clause_node(state: ClauseWorkerState):
    # 这个函数会被 LangGraph 在后台并发调用 N 次！
    finding = llm_audit(state["clause"])
    # 返回列表，会被 OverallState 的 operator.add 自动归约拼接到一起
    return {"audit_results": [finding]}

def reduce_report_node(state: OverallState):
    # 等上面 N 个并行节点全部跑完后，自动进入本节点汇总报告
    return {"final_report": summarize_all(state["audit_results"])}

builder = StateGraph(OverallState)
builder.add_node("split_contract", split_contract_node)
builder.add_node("audit_single_clause_node", audit_single_clause_node)
builder.add_node("reduce_report", reduce_report_node)

builder.add_edge(START, "split_contract")
# 使用 add_conditional_edges 配合 Send() 实现动态 Map 分发
builder.add_conditional_edges("split_contract", continue_to_clause_auditors, ["audit_single_clause_node"])
builder.add_edge("audit_single_clause_node", "reduce_report")
builder.add_edge("reduce_report", END)
```

---

### 范式 5：子图嵌套与多智能体架构（Sub-graphs）
**出处**：[module-4/sub-graph.md](./academy_markdown/module-4/sub-graph.md) & [module-4/studio/sub_graphs.py](./langchain-academy/module-4/studio/sub_graphs.py)
**解决什么痛点？**
当系统里有多个专业子 Agent（如“法规检索子图”、“财务核算子图”），如果所有子 Agent 都往主图的同一个 `messages` 里塞中间步骤，主图状态会彻底乱套。
**LangGraph 子图机制**：每个子图（Sub-graph）拥有自己完全隔离的 `SubState`，编译成一个独立图后，直接作为父图的一个普通节点 `parent_builder.add_node("sub_agent", sub_graph_ builder.compile())` 挂进去。双方只通过同名的重叠字段（Overlapping Keys，如输入 `clause`、输出 `clean_summary`）交换最终结果。

---

## 三、 生产级并发防冲突策略（Double-Texting，Module 6 精华）

**出处**：[module-6/double-texting.md](./academy_markdown/module-6/double-texting.md)
在真实生产环境中，当 Agent 正在后台跑一个耗时 15 秒的多步任务时，用户突然又发来一条新消息（补充条件或改主意），传统手写循环会直接导致状态覆盖错乱。LangGraph Runtime 原生提供 4 种硬核处理参数（`multitask_strategy`）：

1. **`reject`（拒绝）**：直接拒绝第二次请求，返回 409 状态码提示“当前任务正在执行中”；
2. **`enqueue`（排队）**：把新请求放入队列，等当前图跑完最后一个节点后，自动接着跑新请求；
3. **`interrupt`（中断保存并切换）**：立即暂停当前正在跑的图（保留已跑完节点的 Checkpointer 状态），立刻开始处理新请求；
4. **`rollback`（回滚重来）**：直接丢弃并删除当前未跑完的这次运行产生的所有中间分支状态，用最新请求从上一个完整存档点重新开始。

