# 设计规格：attendance_audit_integration 原地对齐 v2 脚手架并全链重构

| 项 | 内容 |
|---|---|
| 日期 | 2026-07-13 |
| 变更级别 | L1（文档骨架重建 + 需求/合规并入）+ L2（架构图补齐）+ L3（伪代码与代码一并重构） |
| 状态 | 已确认并实施中（P0–P2 完成，P3 进行中） |
| 范围目录 | `attendance_audit_integration/` |
| 脚手架源 | `code_dev_audit_framework_v2/`（`scaffold.py` / `project_template` / `docs/*_TEMPLATE`） |

---

## 0. 已确认决策

| 决策点 | 选择 |
|---|---|
| 落位 | **A** 原地升级 `attendance_audit_integration/` |
| 历史文档 | **B** 迁入 `docs/archive/`；**archive 只归档、永不删除** |
| 正式 PRD/ARCH | **B** 以 v2 模板重建，旧内容逐段迁入 |
| 落地方式 | **方案 1** 一次到位叠骨架 |
| 伪代码 | **全部按 v2 规范重写** |
| WiFi / 法务等专题 | **并入正式 PRD**（原稿仍留 archive 对照） |
| 业务代码 | **与伪代码一并重构**（早晚要改就本轮一起做） |

---

## 1. 目标与成功标准

### 1.1 目标

把现有考勤审计项目原地对齐 `code_dev_audit_framework_v2` 的工业级 MVP 骨架，并完成：

1. 正式文档链（PRD → ARCHITECTURE → 伪代码 → 代码 → 测试 → STATUS）按 v2 可对账；
2. 历史与专题内容不丢失（archive 保留 + 正式 PRD 吸收）；
3. 业务模块按新伪代码重构，测试与对账闸门转绿（或 STATUS 明确剩余红项与下一动作）。

### 1.2 成功标准

1. `docs/archive/` 含全部历史稿 + 旧正式 PRD/ARCH/CHECKLIST/SRS 快照；**不删除**。
2. 正式链路仅认：`PRD.md`、`ARCHITECTURE.md`、`CHECKLIST.md`、`STATUS.md`、`COMPLIANCE.md`、`pseudocode/`、`canvas/`。
3. `tools/`、git-hooks、`diagnostics`、对账测试、AI 协议文件就位。
4. 每个 `src/attendance_audit_integration/*.py`（及新增标准件）均有对应伪代码，含「异常与边界」。
5. 业务代码按新伪代码重构；`pytest -m unit` 与 `tools/check_traceability.py` 以 STATUS 登记的目标为准转绿。
6. WiFi/蓝牙打卡专题、法务意见等要点已写入正式 PRD 对应章节（范围/合规/阶段边界），并在变更记录注明来源 archive 路径。

---

## 2. 目录与文件映射

### 2.1 归档（→ `docs/archive/`，只增不删）

| 现有 | 迁入 |
|---|---|
| `docs/PRD.md`、`ARCHITECTURE.md`、`CHECKLIST.md`、`SRS.md` | `docs/archive/`（迁入前快照） |
| `docs/stage_one_*`、`docs/stage_two_*` | `docs/archive/` |
| `docs/feature_enhancements/`、`law_regulation_consulting/`、`wifi_bluetooth_office_clockin_system/` | 整目录移入 `docs/archive/` |

建议结构示例：

```
docs/archive/
  PRD.md
  ARCHITECTURE.md
  CHECKLIST.md
  SRS.md
  stage_one_*.md / stage_two_*.md
  feature_enhancements/
  law_regulation_consulting/
  wifi_bluetooth_office_clockin_system/
  README.md          # 说明：只读对照，正式链路以 docs/ 根下文件为准
```

### 2.2 正式链路（v2）

| 文件 | 做法 |
|---|---|
| `PRD.md` / `ARCHITECTURE.md` / `CHECKLIST.md` / `STATUS.md` / `COMPLIANCE.md` | 从框架模板重建并迁入 |
| `docs/pseudocode/*` | **全部重写**（含业务模块 + `diagnostics` + `tools__*`） |
| `docs/canvas/`、`docs/ui/` | 新建；架构图导出 Canvas 供人审 |

### 2.3 从模板补齐

`tools/`（含 hooks）、`diagnostics.py`、`tests/unit/test_traceability.py`、`test_diagnostics.py`、`AGENTS.md`、`CLAUDE.md`、`.cursor/rules/mvp-framework.mdc`、`.claude/`、`.agent/`、`.codex/`。

### 2.4 保留资产

`preview/`、`scripts/`、`Dockerfile`、`docker-compose.yml`、现有 `.env.example`（与模板合并补缺）。业务能力不丢，实现按新伪代码重构。

---

## 3. 文档迁入规则

### 3.1 `docs/PRD.md`

| v2 章节 | 迁入来源 |
|---|---|
| 0 文档信息 + 变更记录 | 新建；首条记本轮脚手架对齐与全链重构 |
| 1 背景与目标 +「明确不做什么」 | 旧 PRD §1；阶段边界；WiFi/门禁等未上线能力写入「不做什么」或「后续阶段」 |
| 2 功能需求 F1… | 旧 PRD §3 + `stage_one_functions` 六大能力等，统一编号 |
| 3 用户故事 | 旧 PRD §2 四角色 |
| 4 关键业务规则 | 旧 PRD §3.2–3.7 |
| 5 外部依赖 | WeCom、SMTP、PostgreSQL、花名册、节假日等 |
| 6 边界与异常 / 6.6 场景表 | 旧 PRD §5 → 可测场景 |
| 7 非功能 | Docker、Cron、日志、诊断包等 |
| 8 验收 Checklist | 模板结构；【人】项不代勾 |
| 合规 / 监测相关 | **`archive/law_regulation_consulting/`** 要点并入（专节或 §7.3/合规附录），原文留 archive |
| 蓝牙/WiFi 打卡专题 | **`archive/wifi_bluetooth_.../`** 要点并入（阶段规划 / 不做什么 / 后续 F 编号），原文留 archive |

### 3.2 `docs/ARCHITECTURE.md`

保留并迁入旧 §1–3、§4 数据模型、§5 流程；**新建**函数调用图、参数路径图（对账必备）；补 §8 术语表、§9 失败策略、§10 无人值守、§12 决策记录（含「模块边界是否拆 services 层」——见 §4）。

### 3.3 CHECKLIST / STATUS

- CHECKLIST：v2 六阶段模板。
- STATUS：功能矩阵按 F 编号维护；待办队列反映「脚手架 → 文档 → 伪代码 → 代码重构 → 测试对账」顺序。

### 3.4 迁入原则

- 不丢失旧稿已有业务/合规/专题要点；冲突时以「正式 PRD 新表述 + 变更记录说明」为准，archive 可对照。
- 正式链路只认 docs 根下标准文件。

---

## 4. 伪代码与代码重构

### 4.1 伪代码（先于代码）

对下列模块**全部重写**伪代码（路径规则：`src/.../foo.py` → `docs/pseudocode/foo.md`；tools 用 `tools__*.md`）：

- 现有：`__init__`、`config`、`logger`、`main`、`cli`、`db`、`wecom_api`、`wxbiz_msg_crypt`、`mail_sender`、`audit_engine`、`mock_data_populator`
- 新增：`diagnostics`、`tools__check_stage`、`tools__check_process`、`tools__check_traceability`

每份必须含：职责、输入输出、主流程、**异常与边界**、与 PRD F 编号/架构节点的追溯。

### 4.2 代码重构范围

按新伪代码重构业务实现，重点包括但不限于：

- `audit_engine.py`（勾稽与周期逻辑）
- `wecom_api.py` / `wxbiz_msg_crypt.py`（外部调用与安全）
- `mail_sender.py`、`db.py`、`cli.py`、`main.py`
- `config.py` / `logger.py`：对齐 v2 约定，保留项目所需配置项
- 新增 `diagnostics.py`

**架构边界（v2 4.9）**：若现有「入口直接堆业务」违反「业务逻辑在 services 层」，重构时应拆出清晰模块/文件（例如 `services/` 或按职责拆文件），并在 ARCHITECTURE 决策表记录；以「1 逻辑模块 = 1 物理文件、依赖单向无环」为验收条件之一。

### 4.3 依赖与工程

- `pyproject.toml`：合并现有业务依赖 + v2 的 ruff/pytest；`requires-python >=3.10`。
- 双源 `requirements.txt`：以 `pyproject` 为准，旧文件移入 archive 或改为指向说明。
- Hooks：在 STATUS/README 写明子项目启用 `core.hooksPath` 的步骤；若在 monorepo 根，避免误伤其他目录。

### 4.4 测试

- 保留并改写 `tests/unit/test_audit.py`、`test_config.py` 以匹配重构后 API。
- 接入 `test_traceability`、`test_diagnostics`。
- PRD 6.6 每条异常场景补测试（可分期，但须在 STATUS 矩阵追踪）。

### 4.5 本轮不做

- **删除** `docs/archive/` 下任何文件。
- 实现尚未纳入 MVP 的硬件能力（如 BLT1/门禁）——仅在 PRD 中定义边界/后续阶段，不写生产代码。

---

## 5. 实施分期（同一目标，可多会话）

| 期 | 内容 | 出口 |
|---|---|---|
| P0 | 叠骨架 + archive 归档 + 模板文件就位 | 目录与工具链齐全 |
| P1 | 重建 PRD/ARCH/CHECKLIST/STATUS/COMPLIANCE；专题并入 PRD | 人可审正式文档 |
| P2 | 重写全部伪代码 | 伪代码与 F/图节点可追溯 |
| P3 | 按伪代码重构代码 + 单测 | unit 绿 |
| P4 | 对账图补全 + traceability 绿；STATUS 更新 | 对账门禁绿或剩余项入队 |

P0–P4 同属本设计范围；实施时按 STATUS 待办队列推进，允许跨会话，但不得跳过「先伪代码后代码」。

---

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 重构面大、易中断 | STATUS 待办队列 + 分期出口；每期可独立验证 |
| 图码对账暂时红 | P4 专治；P0–P3 在 STATUS 标明「对账未绿」 |
| 专题并入 PRD 导致范围膨胀 | 硬件/未立项能力进「不做什么/后续阶段」，不进入本轮代码 |
| monorepo hooks | 文档化启用方式，默认不强制改根仓库 hooks |

---

## 7. 人审检查点

请确认：

1. 目录/归档策略（§2）  
2. PRD/架构迁入与专题并入（§3）  
3. 伪代码全量重写 + 业务代码一并重构（§4）  
4. 分期 P0–P4（§5）  

审阅通过后，再编写实施计划（`docs/plans/`）并开工。
