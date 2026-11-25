---
name: uml25-state-machine-diagram
description: >-
  Draws, refactors, and audits LangGraph and agentic workflow architecture diagrams
  strictly conforming to OMG UML 2.5 Behavioral State Machine Diagram standards
  (Mermaid stateDiagram-v2 and Draw.io mxGraph). Activate this skill whenever creating
  or updating any LangGraph, StateGraph, or state machine diagram.
---

# UML 2.5 状态机图制图技能（LangGraph / 智能体架构专用）

当用户要求绘制、重绘或审查 LangGraph 架构图、状态流转图或智能体工作流图时激活本技能，确保输出的每一张图 **100% 符合 OMG UML 2.5 状态机图（State Machine Diagram）规范**，同时让非编程背景的业务负责人也能一眼看懂状态迁移与安全边界。

详细语法对照、Draw.io XML 样式与反模式自查表见：[uml25-langgraph-mapping.md](./references/uml25-langgraph-mapping.md)。

---

## 标准制图五步流程

### Step 1：盘点状态机要素（禁止拿流程图思维凑节点）
动笔前先将代码或设计拆解为以下 5 类纯净的 UML 2.5 要素：
1. **状态集（States）**：系统在某一时刻所处的稳定阶段或正在执行的受控活动（圆角矩形，内部用 `entry /`、`do /`、`exit /` 描述读写数据库、调用哪个大模型或工具——**绝不把 SQLite 数据库圆柱体或微信输入框画成状态节点！**）；
2. **伪状态集（Pseudostates）**：起点 `●`（Initial）、终点 `◉`（Final）、运行时动态条件分流点 `◇`（Choice）；
3. **复合状态与正交区（Composite States & Orthogonal Regions）**：若存在宏观阶段（如接入期、分诊期、审签期）或后台并发伴随机制（如超时进度心跳、每日定时唤醒），划入复合状态与虚线分隔的正交并发区；
4. **迁移与监护条件（Transitions & `[Guards]`）**：梳理每一条有向边上的 `事件 [条件] / 动作`，核查每个 `◇` 选择点是否都有互斥条件与 `[else]` 保底出口；
5. **有界回环核验（Loop Bound Check）**：检查图中所有回退箭头是否均标明了计数上限 `[次数 < N]` 与超限跳出分支。

---

### Step 2：选择载体并套用标准 UML 2.5 样式
- **文档内嵌轻量图**：一律使用 Mermaid `stateDiagram-v2`（严禁使用 `flowchart TD/LR` 画状态机！）；
- **大幅工程图纸（`.drawio` + 导出 `.png` / `.pdf`）**：使用 Python 脚本确定性生成标准 `mxGraph` UML 2.5 图元（实心圆 `startState`、牛眼 `endState`、带标题分割线的两栏圆角状态框、正交不穿卡走线），若有本机 Draw.io CLI 则同步导出高清无裁切 `.png` / `.pdf`。

---

### Step 3：业务可读性润色（零黑话审查）
逐个检查状态框标题与迁移线文字：
- ❌ 禁止裸写代码标识：`guardrail_router`、`confidence < 0.55`、`apply_proposal_atomic()`；
- ✅ 改写为直白中文业务状态与条件：`意图分诊中`、`[把握不足五成半]`、`/ 原子写入正式待办并刷新云端看板`。

---

### Step 4：UML 2.5 合规性 6 项自检（出图前必过门禁）
1. 图中是否混入了圆柱体、平行四边形、文档波浪框等非状态机符号？（若有，立即移入状态内部 `do /` 或迁移 `/ effect`）
2. 是否存在没有入边的孤岛状态，或没有路径能到达 `◉` 终点的死胡同状态（常驻正交守护区除外）？
3. 每个 `◇` 选择菱形的出边是否全部带有 `[...]` 方括号监护条件，且包含 `[else]` 兜底？
4. 初始黑圆 `●` 的出边是否干净（无触发事件、无 `[guard]`）？终止牛眼 `◉` 是否零出边？
5. 所有循环回边是否在 `[guard]` 中写明了最大次数上限？
6. 连线是否全部正交避让节点，无文字压线、无穿框交叉？
