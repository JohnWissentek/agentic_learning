# V&F IMR-MS 中国 CCS/CCUS 市场调研与 GTM 智能体工作流 v2.0 (`vf-ccus-workflow`)

本工作流严格遵循工作区最新方法论 **[07_智能体工作流开发方法论_大模型优先与确定性底盘边界](../../../agentic_design_patterns/07_智能体工作流开发方法论_大模型优先与确定性底盘边界.md)**（第 2 档合理并发 + 强确定性底盘），以 **Antigravity Native Hybrid (`ide_workflows/antigravity_run_workflow.py` + `vf-ccus-research` Python CLI)** 为主用入口，同时保持 Standalone LangGraph 状态图同步可用。

## v2.0 核心架构升级（对比 v1.0）

| 维度 | v1.0 旧版 | v2.0 修订版（Model-First + 确定性底盘） |
| :--- | :--- | :--- |
| **主干拓扑** | 8 阶段 / 34 次调用（含 10 次 `flash` STORM + 10 场 `flash` Elo + 花瓶 Judge） | **4 阶段 / ~11–13 次全旗舰调用**（+ 5 次高管版提纯），零弱模型降智 |
| **契约单源化** | `src/` 与 `ide_workflows/` 手抄两套 Schema（导致 0–10 vs 0–100 标尺分裂） | `schemas.py` 单源导出扁平 JSON Schema（`vf-ccus-research export-schemas`），内置高优场景 `<=10` 分制拦截与正交 `SectorDossier` / `CompetitiveEcosystemDossier` 分离 |
| **确定性计算修复** | S1 覆盖丢失 Track C 船运规模；ROI 4 项收益被硬洗成 45/30/15/10 | 按 `(sector, sub_segment, track, horizon)` 累加保留三轨；按原始收益比例等比缩放；直接读取 YAML 情景乘数 |
| **上下文与真审计** | 截断 70% 证据、84% STORM、94% 报告正文；组合引用正则漏检 86.8% | 按卷精准路由证据包；**100% 全文分卷 Critic/Rewrite 零截断**；全量提取单/组合 `[EV-*]` 编号；剔除无据条目零静默假挂靠 |
| **双版本报告交付** | 仅 1 套 18.4 万字详版报告 | **原始详版 5 卷** + **`executive_edition/` 高密度高管版 5 卷** 同步审计落盘 |
| **架构可视化** | 普通卡片流程图 | 严格遵循 **OMG UML 2.5 行为状态机图标准**（[02_CLEAN_WORKFLOW_TOPOLOGY.svg](./docs/02_CLEAN_WORKFLOW_TOPOLOGY.svg)） |

## 快速启动

```bash
# 1. 安装依赖（Python 3.12）
uv sync --python 3.12 --extra dev

# 2. 运行全部离线黑盒契约与回归测试（零成本，无网络依赖）
uv run pytest -v

# 3. 重绘并导出 OMG UML 2.5 状态机矢量图
uv run python scripts/generate_clean_topology_drawio.py

# 4. 校验一手资料、Metaso/Serper 与大模型连通性
uv run vf-ccus-research verify-env
```

**主用执行入口（Antigravity Native Hybrid）**：通过 Antigravity `run_workflow` 运行 [`ide_workflows/antigravity_run_workflow.py`](./ide_workflows/antigravity_run_workflow.py)。
**备用独立执行入口（Standalone LangGraph）**：`uv run vf-ccus-research run --profile flagship`。
