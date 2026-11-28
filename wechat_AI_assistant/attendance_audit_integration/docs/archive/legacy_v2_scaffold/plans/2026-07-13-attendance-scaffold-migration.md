# attendance_audit_integration v2 脚手架对齐 + 全链重构 Implementation Plan

> **For agentic workers:** 按任务顺序执行；优先 inline。步骤用 checkbox 跟踪。  
> **Spec:** `docs/specs/2026-07-13-attendance-scaffold-migration-design.md`

**Goal:** 原地将 `attendance_audit_integration` 对齐 `code_dev_audit_framework_v2`，归档旧文档、重建正式文档链、重写伪代码并重构业务代码，使 unit/对账闸门可追踪转绿。

**Architecture:** 在现有包上叠 v2 骨架（tools/diagnostics/hooks/AI 协议）；正式文档仅认 docs 根下标准文件；业务按「先伪代码后代码」重构，必要时拆 services 层以满足单向依赖。

**Tech Stack:** Python ≥3.10、FastAPI、PostgreSQL/psycopg2、httpx、Jinja2、pytest、ruff、框架 tools 对账脚本

---

## 文件职责总览

| 路径 | 职责 |
|---|---|
| `docs/archive/**` | 只读历史；永不删除 |
| `docs/PRD.md` 等 | v2 正式文档 |
| `docs/pseudocode/**` | 全量重写后的实现说明书 |
| `tools/**` | 阶段/对账/过程闸门 |
| `src/attendance_audit_integration/**` | 业务 + diagnostics；按伪代码重构 |
| `tests/unit/**` | 单测 + traceability/diagnostics |

---

### Task 1 (P0): 归档历史文档

**Files:**
- Create: `attendance_audit_integration/docs/archive/README.md`
- Move: 旧 PRD/ARCH/CHECKLIST/SRS、stage_*、专题目录 → `docs/archive/`
- Copy: `docs/pseudocode` → `docs/archive/pseudocode_pre_v2/`（重写前快照）

- [ ] 将正式旧稿与专题目录移入 archive（不删）
- [ ] 写 `docs/archive/README.md` 说明只读对照规则
- [ ] 确认 `docs/` 根下已无 stage_* / 专题目录

### Task 2 (P0): 叠入 v2 骨架文件

**Files:**
- Copy from `code_dev_audit_framework_v2/project_template/`: `tools/`、AI 协议、`docs/canvas`、`docs/ui`
- Copy templates from framework docs → 临时占位后由 P1 填内容
- Create: `src/.../diagnostics.py`（可先模板）
- Merge: `pyproject.toml`、`.gitignore`、`.env.example`

- [ ] 复制 `tools/`（含 git-hooks）并替换 `{{package}}` → `attendance_audit_integration`
- [ ] 复制 AGENTS.md / CLAUDE.md / `.cursor/rules/mvp-framework.mdc` / `.claude` / `.agent` / `.codex`
- [ ] 合并 pyproject（保留业务依赖 + ruff）
- [ ] 加入 test_traceability / test_diagnostics；合并 conftest 如需
- [ ] 新建空 `STATUS.md`/`COMPLIANCE.md`/`CHECKLIST.md` 骨架（内容 P1 填）

### Task 3 (P1): 重建 PRD（含专题并入）

**Files:**
- Create: `docs/PRD.md`
- Read: `docs/archive/PRD.md`、`stage_one_functions.md`、法务与 WiFi 目录

- [ ] 按 v2 模板写满 §0–§8
- [ ] F 编号覆盖旧规则 + stage_one 六大能力
- [ ] 法务/WiFi 要点并入合规与阶段边界；变更记录注明 archive 路径
- [ ] 「明确不做什么」含未上线硬件

### Task 4 (P1): 重建 ARCHITECTURE / CHECKLIST / STATUS / COMPLIANCE

- [ ] ARCHITECTURE：迁入旧图 + 新建函数调用图/参数路径图初稿
- [ ] CHECKLIST：v2 六阶段
- [ ] STATUS：阶段门 + 功能矩阵 + 待办队列 + 开发日志
- [ ] COMPLIANCE：从模板填写项目名与适用说明

### Task 5 (P2): 全量重写伪代码

- [ ] 按 `03_PSEUDOCODE_GUIDE` 重写每个模块 md（含异常与边界、F 追溯）
- [ ] 含 diagnostics 与 tools__*

### Task 6 (P3): 按伪代码重构代码 + 单测

- [ ] 必要时拆 services；更新 ARCHITECTURE 决策表
- [ ] 重构 audit_engine / wecom_api / mail_sender / db / cli / main / config / logger
- [ ] 新增 diagnostics
- [ ] 改写 unit 测试至绿

### Task 7 (P4): 对账转绿 + 收工 STATUS

- [ ] 补全 Mermaid 与代码一致
- [ ] `python tools/check_traceability.py` 与 pytest 对账门禁
- [ ] 更新 STATUS 第 0 节与开发日志

---

## 执行说明

用户已要求「开始实施」：本会话 **inline 执行**，从 Task 1–2（P0）起连续推进；P1+ 按 STATUS 队列继续。不自动 git commit，除非用户明确要求。
