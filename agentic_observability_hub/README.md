# 企业级智能体双栈可观测性与实时拓扑中心 (`agentic_observability_hub`)

本中心严格基于开源软件构建，为你的多智能体研发工作流（如 [`Boiler_FBG_Product_RD_Workflow`](../Boiler_FBG_Product_RD_Workflow/README.md)）同时提供**“方案 B（企业级自托管 Langfuse v3）”**与**“方案 A（Arize Phoenix + 全景实时节点/线路画布）”**双栈并行运行与同屏对比能力：工作流只需执行一次（或零成本回放已有运行轨迹），即可在浏览器三个页面同时看到完整的**全局节点流转图**与**每次 LLM 交互的完整 Prompt、注入 Context、思维链和回复内容**。

---

## 一、 浏览器三屏访问入口（OrbStack 实盘运行）

| 浏览器标签页 | 对应方案 | 开源底座 | 核心作用 | 访问地址与预置登录信息 |
| :--- | :--- | :--- | :--- | :--- |
| **大屏 1：全景实时工作流拓扑与显微镜** | 方案 A+B 联动入口 | FastAPI + SSE + SQLite + SVG交互画布 | 左屏实时显示 8 阶段全部节点与动态流光线路（含 Critic 反思回边与 10x 实盘动态重放）；右屏直接查看完整未截断 Prompt / Context / Thinking / 回复，并带一键跳转 Langfuse 与 Phoenix 按钮 | **http://localhost:8765**<br/>*(免密直开)* |
| **大屏 2：企业级 AI 工程可观测平台** | **方案 B（企业主力）** | **Langfuse v3**（Postgres + ClickHouse + Redis + MinIO + Web/Worker） | 查看 Agent Graph、企业级 Trace 火焰树、ClickHouse 秒级检索十万字上下文、Prompt 版本库与在线 Playground 改词重跑 | **http://localhost:3000**<br/>邮箱：`admin@wissentek.local`<br/>密码：`Admin123456!`<br/>组织 / 项目：`Wissentek` / `BoilerSense-AI-IPD` |
| **大屏 3：OpenInference 轨迹显微镜** | **方案 A（敏捷对照）** | **Arize Phoenix**（单容器 OpenInference / OTel） | 轻量级 Span 时间轴与每轮 Chat Messages 输入输出拆解、Token 成本与检索评估对比 | **http://localhost:6006**<br/>*(免密直开)* |

---

## 二、 日常一键启停命令（基于 OrbStack）

```bash
cd /Users/john/Desktop/agentic_learning/agentic_observability_hub

# 1. 同时拉起【方案 B (Langfuse v3 六容器) + 方案 A (Arize Phoenix)】
make up-all

# 2. 启动全局实时拓扑与 Prompt/Context 双栏监控台 (:8765)
make serve-canvas

# 3. 零成本将 BoilerSense-AI™ 实盘运行 (23 智能体 + 5 确定性步骤) 灌入三端体验对比
make replay

# 其他常用操作：
make status    # 查看所有 OrbStack 容器运行与健康状态
make up-b      # 仅启动企业级方案 B (Langfuse v3)
make up-a      # 仅启动轻量级方案 A (Arize Phoenix)
make down      # 停止并清理运行容器（保留持久化卷数据）
```

---

## 三、 架构与运维手册导航

1. [`01_DUAL_STACK_OTEL_FANOUT_ARCHITECTURE.md`](./docs/01_DUAL_STACK_OTEL_FANOUT_ARCHITECTURE.md) — 双栈同跑技术架构：OpenTelemetry 单次埋点扇出、共享 Trace ID 与密钥脱敏护栏
2. [`02_SCHEME_B_LANGFUSE_V3_ENTERPRISE_GUIDE.md`](./docs/02_SCHEME_B_LANGFUSE_V3_ENTERPRISE_GUIDE.md) — 方案 B（Langfuse v3）六容器原理、Headless 初始化与浏览器操作指南
3. [`03_SCHEME_A_PHOENIX_AND_LIVE_TOPOLOGY_STUDIO.md`](./docs/03_SCHEME_A_PHOENIX_AND_LIVE_TOPOLOGY_STUDIO.md) — 方案 A（Arize Phoenix + 实时拓扑控制台 `:8765`）联动与静态/动态双视野设计
4. [`04_SIDE_BY_SIDE_EVALUATION_AND_SWITCHING_PLAYBOOK.md`](./docs/04_SIDE_BY_SIDE_EVALUATION_AND_SWITCHING_PLAYBOOK.md) — A vs B 同屏对比体验评分卡、历史轨迹零成本回放与未来单栈切换手册
