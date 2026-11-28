# 设计模式映射文档

本文档建立《Agentic Design Patterns》原书章节/页码到本项目实现的精确映射。

## 书籍信息

- **书名**: Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems
- **作者**: Antonio Gulli (Google CTO Office Engineering Director)
- **总页数**: 482页
- **说明**: 本书为作者个人专著，非Google官方出版物

---

## 核心模式映射

### Pattern 1: Prompt Chaining (Chapter 1, P23-35)

**书中定义**: 将复杂任务拆解为确定性的线性步骤序列，上一步的结构化输出作为下一步的输入。

**本项目实现**:
- 位置: `graph.py` 阶段间边定义
- 实现方式: Stage 0 → Stage 1 → Stage 2 → ... → Stage 5 的严格因果流水线
- 代码示例:
```python
builder.add_edge("stage_0_hitl", "stage_1_concept")
builder.add_edge("stage_1_hitl", "stage_2_detailed")
```

### Pattern 3: Parallelization (Chapter 3, P50-64)

**书中定义**: 同时并发执行多个互不依赖的子任务以降低延迟。

**本项目实现**:
- 位置: `graph.py` 各阶段节点内部
- 实现方式: Stage内多角色并行执行（如 MKT+OPT 并行、OPT+HW+SW 并行）
- 代码示例:
```python
# Stage 0: MKT and OPT run in parallel
mkt_result = execute_market_research(deps)
opt_result = execute_tech_feasibility(deps)
```

### Pattern 4: Reflection (Chapter 4, P65-78)

**书中定义**: 引入独立的"挑刺/审查者"角色对生成结果进行多轮评估与打回重改。

**本项目实现**:
- 位置: `nodes/quality_reviewer.py`
- 实现方式: QA角色独立审查所有阶段产物，识别问题，决定PASS/HOLD/BLOCKED
- 代码示例:
```python
builder.add_conditional_edges(
    "stage_0_qa_review",
    partial(route_after_qa, ...),
    {"next": "stage_0_hitl", "hitl": "stage_0_hitl", "rewrite": "stage_0_market_research"},
)
```

### Pattern 5: Tool Use (Chapter 5, P79-99)

**书中定义**: 让LLM突破文本边界，安全调用外部API、数据库、代码解释器。

**本项目实现**:
- 位置: `tools/` 目录
- 实现方式:
  - `evidence_vault.py`: SQLite证据存储
  - 确定性计算工具: [MKT-CALC], [COST-CALC] 标签
- 关键约束: 所有数值计算由Python确定性完成，非LLM心算

### Pattern 6: Planning (Chapter 6, P100-112)

**书中定义**: 面对开放式目标，先生成多步执行计划再按步骤动态执行与重规划。

**本项目实现**:
- 位置: `nodes/planner.py`
- 实现方式: PM角色负责研发阶段规划，支持基于QA反馈的重规划
- 阶段定义: `config.py` 中的 STAGE_CONFIG

### Pattern 7: Multi-Agent Collaboration (Chapter 7, P113-131)

**书中定义**: 构建由多个具备独立角色的智能体组成的协作集群。

**本项目实现**:
- 位置: 整体架构
- 拓扑选择: 层级主管(PM) + 流水线交接 + 批评者-审查员(QA) 混合
- 角色定义: 12个专业角色 (PM, MKT, OPT, HW, SW, SCM, QA, MFG, TRN, FIN, SLS, STR)

书中六大协作模式对应:
1. **顺序交接**: Stage间串行流转
2. **并行处理**: Stage内多角色并行
3. **批评者-审查员**: QA独立审查所有产物

### Pattern 11: Goal Setting and Monitoring (Chapter 11, P183-195)

**书中定义**: 将宏观目标拆解为可量化的里程碑指标，持续追踪偏离度并自动纠偏。

**本项目实现**:
- 位置: `schemas.py` Milestone模型
- 实现方式: 研发阶段里程碑追踪，deliverables和dependencies定义

### Pattern 12: Exception Handling (Chapter 12, P196-203)

**书中定义**: 通过前瞻性的错误防御与反应式的恢复协议确保系统韧性。

**本项目实现**:
- 位置: `config.py` 重试配置
- 实现方式:
  - 最大重试次数: max_retries
  - 指数退避: retry_backoff_base
  - 优雅降级: 模拟模式作为回退

### Pattern 13: Human-in-the-Loop (Chapter 13, P204-212)

**书中定义**: 在高风险决策点自动挂起工作流，引入人类专家审核。

**本项目实现**:
- 位置: `nodes/hitl_gate.py`
- 实现方式:
  - 5个HITL门禁: requirement_approval, design_approval, procurement_approval, test_approval, launch_approval
  - 模拟模式自动批准并标记 [SIMULATION]
  - 实际运行时挂起等待人工输入

---

## 未实现/简化的模式

以下模式在当前版本中未完全实现或做了简化处理:

| 模式 | 页码 | 状态 | 说明 |
|------|------|------|------|
| Pattern 8: Memory | P132-153 | 简化 | 使用LangGraph MemorySaver，未实现长期记忆 |
| Pattern 9: Learning | P154-166 | 未实现 | 需要实际运行数据积累 |
| Pattern 10: MCP | P167-182 | 未实现 | 可扩展添加MCP工具 |
| Pattern 14: RAG | P213-230 | 部分 | 证据库可扩展为向量检索 |
| Pattern 15: A2A | P231-245 | 未实现 | 单系统内无需跨框架通信 |
| Pattern 16: Resource Opt | P246-261 | 部分 | 成本追踪已实现，模型路由未实现 |
| Pattern 17: Reasoning | P262-285 | 未实现 | 可在live模式添加CoT |
| Pattern 18: Guardrails | P286-305 | 部分 | 安全约束在提示词中定义 |
| Pattern 19: Evaluation | P306-324 | 部分 | QA审查实现，LLM-as-Judge未实现 |
| Pattern 20: Prioritization | P325-334 | 未实现 | 当前为固定阶段顺序 |
| Pattern 21: Exploration | P335-348 | 未实现 | 研发场景已预定义 |

---

## 证据要求

所有实现声明需满足:
1. 指明书中具体章节和页码
2. 提供代码位置和关键代码片段
3. 说明实现程度（完全/部分/简化）
4. 记录与原书方法的差异
