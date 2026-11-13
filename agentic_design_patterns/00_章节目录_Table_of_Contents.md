# Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems — 章节目录与内容索引 (Table of Contents)

- **文档书名**：*Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems*（智能体设计模式：构建智能系统的实战指南）
- **作者**：**Antonio Gulli**（Google 首席技术官办公室 Office of the CTO 工程总监）
- **总页数**：482 页（涵盖 4 大部分、21 个核心智能体设计模式章节、7 个技术附录、术语表及索引，每章均附有基于 **LangChain / LangGraph / CrewAI / Google ADK** 的可运行代码）
- **同目录文件**：
  - 原始 PDF：[Agentic_Design_Patterns.pdf](./Agentic_Design_Patterns.pdf)
  - 全书架构精要与技术摘要（模块化速读分册文件夹，含 `README.md` 与 9 篇短文）：[全书摘要分册/README.md](./全书摘要分册/README.md)
  - 全文 Markdown 转换版（约 90 万字符，按页精准标注 `## [PDF Page X]`）：[Agentic_Design_Patterns_full.md](./Agentic_Design_Patterns_full.md)
  - AI 范式演进全景图（Mermaid + 架构精解）：[01_AI范式演进全景图_LLM_Workflow_RAG_Agent_AgenticAI.md](./01_AI范式演进全景图_LLM_Workflow_RAG_Agent_AgenticAI.md)
  - AI 范式演进全景图（JSON Canvas 白板文件）：[01_AI范式演进全景图_LLM_Workflow_RAG_Agent_AgenticAI.canvas](./01_AI范式演进全景图_LLM_Workflow_RAG_Agent_AgenticAI.canvas)
  - 智能体复杂度金字塔（Level 0–Level 3 演进与架构叠加精解）：[02_智能体复杂度金字塔_Level0至Level3演进与架构叠加精解.md](./02_智能体复杂度金字塔_Level0至Level3演进与架构叠加精解.md)
  - Chapter 1 高亮解析与任务拆解机制对比（设计时预定义 vs 运行时 LLM 拆解）：[03_Chapter1_Prompt_Chaining_高亮解析与任务拆解机制对比.md](./03_Chapter1_Prompt_Chaining_高亮解析与任务拆解机制对比.md)
  - Chapter 2 高亮解析与路由机制实战指南（四种路由对比、三级漏斗与动态通道扩展）：[04_Chapter2_Routing_高亮解析_四种路由机制与动态通道扩展指南.md](./04_Chapter2_Routing_高亮解析_四种路由机制与动态通道扩展指南.md)
  - Chapter 3 高亮解析与并行化实战指南（适用与禁区场景、五大重点与 LangChain/LangGraph 三种实现）：[05_Chapter3_Parallelization_高亮解析_适用与禁区场景及LangGraph实现指南.md](./05_Chapter3_Parallelization_高亮解析_适用与禁区场景及LangGraph实现指南.md)
  - Chapter 4 高亮解析与反思模式落地方案（生成与评估模型配对博弈、谁来修改与 LangGraph 实战模板）：[06_Chapter4_Reflection_高亮解析_生成与评估模型博弈及工程落地方案.md](./06_Chapter4_Reflection_高亮解析_生成与评估模型博弈及工程落地方案.md)
  - 跨模式综合实战参考（工业 B2B 市场调研与 BD 销售拓展 Agentic Workflow，以 V&F IMR-MS 与 CCUS 为例）：[../reference_agentic_workflow/02_工业B2B市场调研与BD销售拓展_Agentic_Workflow_开源生态与架构参考_以VF_IMR_MS与CCUS为例.md](../reference_agentic_workflow/02_工业B2B市场调研与BD销售拓展_Agentic_Workflow_开源生态与架构参考_以VF_IMR_MS与CCUS为例.md)

---

## 一、 全局总览目录（21 大设计模式 + 7 大附录精确页码映射）

### 前言与导论（Front Matter & Introduction，PDF P1–P22）

| 章节编号 | 英文原版标题 | 中文译名与核心内容 | PDF 页码 |
| :--- | :--- | :--- | :---: |
| **TOC** | Table of Contents | 全书总目录 | P1–P2 |
| **Dedication** | Dedication & Acknowledgment | 献词与致谢 | P3–P6 |
| **Foreword** | Foreword & A Thought Leader's Perspective | 序言与思想领袖视角：智能体的力量与责任 | P7–P8 |
| **Intro** | Introduction & Overview of the Book | 引言：为什么在 AI 快速迭代期更需要提炼底层固化模式 | P9–P13 |
| **Primer** | **What makes an AI system an "Agent"?** | **什么让 AI 系统成为“智能体”？（五步循环与复杂度分级）** | **P14–P22** |

---

### 第一部分：Part One — 基础编排与协作模式（Foundational Orchestration Patterns，PDF P23–P131）

| 模式编号 | 英文原版章节标题 | 中文译名 | 核心解决什么问题？（附框架代码） | PDF 页码 |
| :--- | :--- | :--- | :--- | :---: |
| **Pattern 1** | **Chapter 1: Prompt Chaining** | **模式 1：提示词链（顺序流水线）** | 将复杂任务拆解为确定性的线性步骤序列，上一步的结构化输出作为下一步的输入（Divide & Conquer） | **P23–P35** |
| **Pattern 2** | **Chapter 2: Routing** | **模式 2：动态路由（条件分支）** | 基于 LLM 语义分类、Embedding 相似度或确定性规则，将输入动态分发至不同的专业处理分支 | **P36–P49** |
| **Pattern 3** | **Chapter 3: Parallelization** | **模式 3：并行化（并发扇出与汇聚）** | 同时并发执行多个互不依赖的子任务（如多数据源检索、多视角投票审查 Sectioning & Voting）以大幅降低延迟 | **P50–P64** |
| **Pattern 4** | **Chapter 4: Reflection** | **模式 4：自我反思与批判（Generator-Critiquer）** | 引入独立的“挑刺/审查者（Critiquer）”角色对生成结果进行多轮评估与打回重改，显著提升输出质量 | **P65–P78** |
| **Pattern 5** | **Chapter 5: Tool Use (Function Calling)** | **模式 5：工具调用（函数调用）** | 让 LLM 突破文本边界，安全调用外部 API、数据库、代码解释器沙盒与本地函数 | **P79–P99** |
| **Pattern 6** | **Chapter 6: Planning** | **模式 6：自主规划（Plan-and-Execute / ReWOO）** | 面对开放式复杂目标，先生成多步执行计划（DAG 或任务树），再按步骤动态执行与重规划 | **P100–P112** |
| **Pattern 7** | **Chapter 7: Multi-Agent Collaboration** | **模式 7：多智能体协作** | 构建层级式（Supervisor）、流水线式或辩论式多智能体团队，通过角色分工与任务交接解决跨域难题 | **P113–P131** |

---

### 第二部分：Part Two — 记忆、学习、协议与目标管理（Memory, Learning & Protocols，PDF P132–P195）

| 模式编号 | 英文原版章节标题 | 中文译名 | 核心解决什么问题？（附框架代码） | PDF 页码 |
| :--- | :--- | :--- | :--- | :---: |
| **Pattern 8** | **Chapter 8: Memory Management** | **模式 8：记忆管理（短期/长期/情景/语义记忆）** | 结合心理学分类与工程实现（LangGraph Checkpointer / Store / 向量库），管理会话上下文与跨会话长期记忆 | **P132–P153** |
| **Pattern 9** | **Chapter 9: Learning and Adaptation** | **模式 9：在线学习与自适应演化** | 智能体如何从历史执行反馈、人类修正（RLHF / Few-shot 动态注入 / 记忆反思）中持续自我进化 | **P154–P166** |
| **Pattern 10** | **Chapter 10: Model Context Protocol (MCP)** | **模式 10：模型上下文协议（MCP）** | 使用统一的 MCP Client/Server 标准协议解耦智能体与外部数据源/工具，实现即插即用工具生态 | **P167–P182** |
| **Pattern 11** | **Chapter 11: Goal Setting and Monitoring** | **模式 11：目标设定与进度监控** | 将宏观目标拆解为可量化的里程碑指标（KPIs / Sub-goals），在长周期运行中持续追踪偏离度并自动纠偏 | **P183–P195** |

---

### 第三部分：Part Three — 容错、人机协同与知识检索（Reliability, HITL & RAG，PDF P196–P230）

| 模式编号 | 英文原版章节标题 | 中文译名 | 核心解决什么问题？（附框架代码） | PDF 页码 |
| :--- | :--- | :--- | :--- | :---: |
| **Pattern 12** | **Chapter 12: Exception Handling and Recovery** | **模式 12：异常处理与故障自愈** | 针对 API 超时、工具报错、格式解析失败设计指数退避重试、Fallback 备用模型切换与优雅降级机制 | **P196–P203** |
| **Pattern 13** | **Chapter 13: Human-in-the-Loop (HITL)** | **模式 13：人类在环（审批门禁与协同）** | 在高风险决策、合规签批或置信度不足时自动挂起工作流（Interrupt），引入人类专家审核、修改状态或接管 | **P204–P212** |
| **Pattern 14** | **Chapter 14: Knowledge Retrieval (RAG)** | **模式 14：知识检索增强（RAG / Agentic RAG / GraphRAG）** | 深入讲解分块策略、混合检索、重排（Reranking）、Corrective RAG（CRAG）与 GraphRAG 落地 | **P213–P230** |

---

### 第四部分：Part Four — 互联通信、优化、推理、护栏与评估（Advanced Production Patterns，PDF P231–P348）

| 模式编号 | 英文原版章节标题 | 中文译名 | 核心解决什么问题？（附框架代码） | PDF 页码 |
| :--- | :--- | :--- | :--- | :---: |
| **Pattern 15** | **Chapter 15: Inter-Agent Communication (A2A)** | **模式 15：跨智能体通信协议（A2A）** | 不同框架、不同组织间的异构智能体如何通过 Agent Card、任务生命周期与消息总线进行安全互操作 | **P231–P245** |
| **Pattern 16** | **Chapter 16: Resource-Aware Optimization** | **模式 16：资源感知优化（成本/延迟/Token 预算）** | 动态模型路由（小模型处理常规任务、大模型处理复杂推理）、语义缓存（Semantic Caching）与预算熔断 | **P246–P261** |
| **Pattern 17** | **Chapter 17: Reasoning Techniques** | **模式 17：高阶推理技术（CoT / ToT / GoT / ReAct）** | 思维链（CoT）、思维树（Tree of Thoughts）、思维图（Graph of Thoughts）、自洽性投票（Self-Consistency）与深度搜索推理 | **P262–P285** |
| **Pattern 18** | **Chapter 18: Guardrails / Safety Patterns** | **模式 18：安全护栏模式（输入/输出/工具级防护）** | 防范提示词注入（Prompt Injection）、PII 敏感信息脱敏、工具权限最小化与输出合规性实时拦截 | **P286–P305** |
| **Pattern 19** | **Chapter 19: Evaluation and Monitoring** | **模式 19：智能体量化评估与生产监控** | 构建 LLM-as-a-Judge 裁判评估、轨迹级（Trajectory）准确性验证、延迟/Token 遥测追踪与回归测试 | **P306–P324** |
| **Pattern 20** | **Chapter 20: Prioritization** | **模式 20：任务优先级调度模式** | 当智能体面临多并发请求或多子任务队列时，如何基于紧急度、依赖关系与资源成本进行动态优先级排序 | **P325–P334** |
| **Pattern 21** | **Chapter 21: Exploration and Discovery** | **模式 21：自主探索与科学发现模式** | 智能体如何跳出既有路径，主动生成假设、设计实验并探索未知解空间（如自动化科研与创新方案挖掘） | **P335–P348** |

---

### 附录与总结（Appendices, Glossary & Index，PDF P349–P482）

| 附录编号 | 英文原版标题 | 中文译名与核心内容 | PDF 页码 |
| :--- | :--- | :--- | :---: |
| **Appendix A** | **Advanced Prompting Techniques** | **附录 A：高级提示词工程大全**（Zero/Few-shot、CoT、Step-Back、Thread-of-Thought、自动提示词优化 APE） | **P349–P377** |
| **Appendix B** | **AI Agentic Interactions: From GUI to Real World** | **附录 B：从图形界面（Computer Use / Browser Agent）到物理世界的智能体交互** | **P378–P384** |
| **Appendix C** | **Quick Overview of Agentic Frameworks** | **附录 C：主流智能体开发框架横向速览**（LangChain、LangGraph、CrewAI、AutoGen、Google ADK 等） | **P385–P392** |
| **Appendix D** | **Building an Agent with AgentSpace** | **附录 D：使用 Google Agentspace 构建企业级智能体** | **P393–P398** |
| **Appendix E** | **AI Agents on the CLI** | **附录 E：命令行终端智能体（CLI Agents）架构与实战** | **P399–P403** |
| **Appendix F/G** | **Under the Hood: Reasoning Engines & Coding Agents** | **附录 F/G：深入智能体推理引擎内部机制与编程智能体（Coding Agents）剖析** | **P404–P415** |
| **Conclusion** | **Conclusion** | **全书结语** | **P416–P420** |
| **Glossary** | **Glossary & Index of Terms** | **核心术语词典与全书检索索引** | **P421–P482** |

---

## 二、 如何将本书与你工作区中的其他两套资料联动阅读？

现在你的工作区已经集齐了智能体工程领域最核心的**“三驾马车”**：
1. **顶层工程路线图**：[`startup_technical_guide_ai_agents/`](../startup_technical_guide_ai_agents/00_章节目录_Table_of_Contents.md)（Google 官方 64 页初创企业工程指南 + 6 篇深度拆解专题）
2. **21 种通用设计模式词典（本书）**：[`agentic_design_patterns/`](./00_章节目录_Table_of_Contents.md)（Antonio Gulli 482 页设计模式大全，每种模式都有独立章节与代码）
3. **LangGraph 底层实现与代码圣经**：[`langgraph_reference/`](../langgraph_reference/00_LangGraph_从原理到实战完整指南与目录索引.md)（O'Reilly 297 页专著 + LangChain Academy 30 节全量 Markdown 与源码）

**推荐检索与使用方式**：
- 当你在设计具体业务（如商业合同审查系统）遇到某个环节拿不准用什么模式时（比如：*“怎么设计一审和二审挑刺？”* $\rightarrow$ 查本书 **Chapter 4: Reflection [P65]**；*“怎么处理工具报错重试？”* $\rightarrow$ 查本书 **Chapter 12: Exception Handling [P196]**；*“怎么设计安全护栏？”* $\rightarrow$ 查本书 **Chapter 18: Guardrails [P286]**），可以直接在 [Agentic_Design_Patterns_full.md](./Agentic_Design_Patterns_full.md) 中搜索 `## [PDF Page 65]` 对应的页码直接阅读 Markdown 全文与代码！

