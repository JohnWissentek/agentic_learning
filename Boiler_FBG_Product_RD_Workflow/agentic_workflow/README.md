# BoilerSense-AI™ 多智能体产品研发与量产导入工作流 (`bfbg-workflow`)

本工作流严格依据 Google [`agentic_design_patterns`](../../../agentic_design_patterns/全书摘要分册/README.md) 全书 21 个设计模式与工程附录，结合 `CCS_projects _China` 与 `power_semiconductor_opportunities` 的双引擎取证、PALMs 确定性算账、异构 Critic 闭环及 Draw.io 架构可视化经验打造，围绕**燃煤电站锅炉水冷壁 FBG 智能测温与 AI 优化系统**完成从市场调研、双档产品定义、国际供应链选型与原厂 PDF 验真、硬件接口集成详设、解调算法与锅炉 AI 架构、量产 NPI QA/QC 与现场焊接 SOP 到财务、营销与培训体系的全生命周期研发输出。

## 快速启动

```bash
cd /Users/john/Desktop/agentic_learning/Boiler_FBG_Product_RD_Workflow/agentic_workflow

# 1. 创建 Python 3.12 虚拟环境并安装依赖
/Users/john/.local/bin/uv sync --python 3.12 --extra dev

# 2. 检查搜索、原厂语料、PDF及 Draw.io 工具连通性（不泄露密钥明文）
/Users/john/.local/bin/uv run bfbg-workflow verify-env

# 3. 运行离线单元测试、PDF魔数校验与 LangGraph 全图轨迹测试
/Users/john/.local/bin/uv run pytest -v

# 4. 独立运行完整多智能体工作流（DashScope 外置大模型无头模式）
/Users/john/.local/bin/uv run bfbg-workflow run --profile flagship --output-dir ../output
```

也可在 Antigravity IDE 中调用 `run_workflow` 运行 [`ide_workflows/antigravity_run_workflow.py`](./ide_workflows/antigravity_run_workflow.py)，由内置前沿大模型充当产品研发 IPD 多角色团队，配合 `bfbg-workflow` 确定性 CLI 执行取证、PDF 验真下载、工程/财务计算与交付物编译。

## 架构文档与拓扑图

- [00_ARCHITECTURE_AND_PATTERN_MAPPING.md](./docs/00_ARCHITECTURE_AND_PATTERN_MAPPING.md)：《Agentic Design Patterns》全模式落地映射总表与 8 阶段 IPD 团队协作机制。
- [01_MULTI_AGENT_IPD_WORKFLOW_TOPOLOGY.svg](./docs/01_MULTI_AGENT_IPD_WORKFLOW_TOPOLOGY.svg)：多智能体研发与 NPI 工作流拓扑矢量图。
- [02_BOILER_FBG_SYSTEM_INTERFACE_ARCH.svg](./docs/02_BOILER_FBG_SYSTEM_INTERFACE_ARCH.svg)：双档系统硬件集成与光电/电气/DCS/AI接口矢量框图。
