# 燃煤电站锅炉水冷壁 FBG 智能测温系统——产品研发与量产导入多智能体工作流 (`Boiler_FBG_Product_RD_Workflow`)

本目录严格遵循**智能体研发编排工程与交付成果完全分离**原则，对标 Google《Agentic Design Patterns》（Antonio Gulli 著，482 页全书 21 模式与工程附录）及 `CCS_projects _China` / `power_semiconductor_opportunities` 工业级工程范式构建，覆盖**市场调研 → 架构设计 → 国际选型与 PDF 规格书验真 → 硬件接口与集成详设 → 软件/锅炉 AI 架构 → 调试/安装/全流程 QA-QC 与 SOP → 财务/GTM/培训体系**全链路端到端执行。

## 目录结构

1. [`agentic_workflow/`](./agentic_workflow/README.md)：基于 LangGraph `StateGraph` 与 Antigravity Native `run_workflow` 的多智能体 IPD 产品研发与量产导入（NPI）工作流引擎、确定性工程与财务计算沙箱（`[PHY-CALC]` / `[BOM-CALC]` / `[FIN-CALC]` / `[PLANT-ROI]`）、双引擎搜索与原厂 PDF 验真下载器、自动化测试及矢量架构图生成脚本。
2. [`output/`](./output/00_EXECUTIVE_PRODUCT_CHARTER_AND_ROADMAP.md)：工作流实盘运行输出的全套产品级研发与商业交付物（`00_`–`08_` 文档与遥测 JSON、[`datasheets_pdf/`](./output/datasheets_pdf/) 原厂 PDF 规格书合集、`09_` 与 `10_` Draw.io/SVG/PDF 架构图）。

## 历史参考边界

- [`../Boiler_FBG_Thermometry_Research/`](../Boiler_FBG_Thermometry_Research/00_Overview_and_Index/README.md) 保持**纯净只读**，仅作为 Stage 0a 本地基线语料与初始 11 份原厂 PDF 输入源；本工程独立构建双档模块化产品矩阵（`BS-STD-600` 标准版 300–600 点 + `BS-PRO-2000` 旗舰版 1000–2000+ 点）、双轨分级传感 BOM 与旁路只读起步的锅炉 AI 平台。
