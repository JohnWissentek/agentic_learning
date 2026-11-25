# 00 系统架构规范 v2.0 (`00_ARCHITECTURAL_SPECIFICATION`)

## 1. 工程结构与主次双入口

本系统采用 **「全旗舰大脑 + 强确定性 Python 底盘」** 职责二分架构：

- **主用入口 — Antigravity Native Hybrid 模式**（`ide_workflows/antigravity_run_workflow.py`）：
  - 在 IDE 原生旗舰模型上执行认知推理，通过 `vf-ccus-research` CLI 复用 100% 同一套确定性 Python 底盘（单源 Schema 导出、一手资料解析、Metaso/Serper SQLite 证据库、细分 `[MKT-CALC]` & 保比例 `[ROI-CALC]`、卷宗精准证据路由、Zero-LLM 第 05 卷索引与 100% 双版本确定性门禁）。
- **兼容入口 — Standalone LangGraph 模式**（`src/vf_ccus_workflow/graph.py`）：
  - 基于 4 阶段 `StateGraph` + `MemorySaver`，适合无人值守批处理与离线轨迹测试。

## 2. v2.0 核心工程不变式（Engineering Invariants）

1. **Single-Source Flat Schema**：`schemas.py` 是唯一红区契约源；`export_flat_json_schema` 自动展开 `$ref`/`$defs` 并保留全部上下界与枚举，彻底杜绝双写漂移与 0–10 vs 0–100 标尺分裂。
2. **Zero LLM Arithmetic & Domain Fidelity**：
   - `[MKT-CALC]` 按 `(sector, sub_segment, primary_delivery_track, horizon)` 累加测算，陆上管网（Track B）与出口 LCO2 船运/离岸枢纽（Track C）并存不覆盖；情景乘数全部从 `config/discovery_scope.yaml` 单源读取。
   - `[ROI-CALC]` 在护栏钳制时按原始 4 项收益占比等比缩放，严禁硬编码覆写收益结构。
3. **Zero Silent Evidence Backfill**：凡模型产出无法匹配真实 SQLite 证据 ID 的项目、竞品、PAC 集成商或切入点，一律严格剔除并记入 `dropped_unverified_records` 审计台账，严禁回填无关 `fallback_ids`。
4. **Zero-Truncation Context & Full-Text Audit**：
   - 按卷主题与关联引用 ID 精准路由证据包；
   - 分卷 Critic 与定向 Rewrite 均传入 **100% 完整卷宗正文**（严禁截断）；
   - 确定性审计门禁使用全量正则提取所有单条与多 ID 组合引用（如 `[EV-SIGGI-001, EV-CN-003]`），并跨双版本核验十年 SOM 与回收期数值一致性。
5. **Dual-Edition Synchronized Deliverables**：每次完整运行同步交付 **5 卷原始详版**（`00_`–`04_`）与 **5 卷高密度高管版**（`executive_edition/00_`–`04_`），外加 Zero-LLM `05_` 证据索引与客观确定性 `06_` 遥测报告（取消 100 分制花瓶 LLM Judge）。
6. **Secret Leak Prevention**：`assert_no_secrets_leaked` 在所有 12 份落盘文件写入前全量扫描拦截密钥泄露。
