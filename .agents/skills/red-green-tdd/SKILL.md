---
name: red-green-tdd
description: >-
  Executes anti-collusion, zero-handwritten-test TDD (Isolated RED -> Locked GREEN
  -> Safe Refactor -> Fresh Proof) for feature slices and bug fixes. Activate this
  skill whenever implementing business logic, adding a thin slice, or fixing a bug
  so that behavior is proven by black-box tests without forcing the human to write test code.
---

# 免手写读写隔离 TDD 执行技能 (Anti-Collusion Red-Green-Refactor)

当需要对某个垂直薄切片编写生产代码、新增核心业务逻辑或修复 Bug 时激活本技能。本技能融合了 `obra/superpowers`（*Iron Law of TDD* & *Verification Before Completion*）与 `addyosmani/agent-skills` 规范，通过**子智能体读写隔离**彻底阻断 AI「自己写错代码再写假测试放水」的同源串谋问题。

---

## 核心铁律（违反任意一条即视为流程失效）

1. **没有亲眼见证失败的红灯测试，绝不写生产业务代码**（纯静态配置、纯视觉样式微调、经人类明确豁免的一次性探索脚本除外）。
2. **编写测试与编写实现必须物理隔离**：优先调用 `invoke_subagent` 启动 `blind-test-author` 子智能体编写红灯测试；主智能体在实现阶段将 `tests/` 视为只读法律。
3. **重生成红线**：同一薄片在 Green 阶段若连续修补 2 轮仍引发旧测试回归失败，停止盲目打补丁，核对契约后干净重写该切片。

阅读防偷懒自查表：[anti-rationalization-checklist.md](./references/anti-rationalization-checklist.md)。

---

## 标准五步执行闭环

### Phase 1：对齐中文验收场景矩阵（Contract Lock）
检查当前任务是否已有明确的「正常 + 边界 + 禁令」验收条件：
- 若用户已给出：直接整理为清晰的 4～6 条中文验证点；
- 若用户只给了一句模糊需求（如“把邮件拉取加上”）：主智能体先用大白话拟定 **4～6 条中文验收点**（含幂等去重、附件边界、非白名单禁令），若无重大歧义可直接进入 Phase 2 并在汇报中展示。

---

### Phase 2：调度独立盲测官生成「有效红灯」（Isolated RED）
1. 若公开入口函数/类尚不存在，主智能体仅可在 `src/` 中创建**空签名桩（Stub）**（函数体仅写 `raise NotImplementedError("Pending Green phase")`），**严禁在此步偷写任何业务实现逻辑**。
2. 调用 `invoke_subagent` 启动 **`blind-test-author`**，向其传入：
   - 🔴 红区契约文件路径（`schemas.py`、公开入口签名路径）；
   - Phase 1 的中文验收场景矩阵；
   - 明确指令：*“仅编写黑盒契约测试（使用真实临时数据库，仅 Stub 最外层外部网络/付费模型网关），运行测试运行器确认因业务未实现或未达标而明确 FAILED（红灯），返回 60 秒核心断言速审表。”*
3. 收到盲测官返回后，核验红灯是否真实有效（非测试语法错误）。若用户要求先确认测试，展示 60 秒断言速审表；否则进入 Phase 3。

---

### Phase 3：锁死 `tests/`，编写最小生产代码变绿（Locked GREEN）
主智能体开始在 `src/` 中实现业务逻辑，严格遵守：
1. **`tests/` 只读锁死**：**严禁修改、删除、注释或 `skip` 刚刚生成的任何测试断言**。若发现测试本身确实存在契约字段拼写错误，必须停下向用户说明并获准后再改。
2. **遵循生产级安全基线**：外部调用必带 `timeout`、入口必做幂等防重、禁止裸 `except: pass` 静默吞错、严禁在业务文件里硬编码野生 System Prompt（提示词一律放入集中式 `prompts/`）。
3. 运行当前切片测试与全仓历史回归测试，直到 **100% 全部变绿（Exit Code 0）**。

---

### Phase 4：安全网内整理重构（Safe Refactor）
在测试全绿保护下，快速扫描刚编写的 `src/` 代码：
- 消除重复代码块、拆分过长函数、确认 🔴 红区与 🟡 黄区边界干净；
- 重构后**再次重跑全量测试套件**，确认依然 100% 全绿。

---

### Phase 5：新鲜实证交付（Fresh Verification Gate）
向用户汇报完工时，必须同时呈现以下三项实证（缺一不可，严禁口头说“应该好了”）：
1. **60 秒断言覆盖摘要**：列出本切片锁死的几条中文业务场景与测试名；
2. **改动范围统计**：新增/修改的 `src/` 文件链接与行数（验证符合薄切片体量）；
3. **当轮终端实测输出**：贴出最新一次全量测试与静态检查命令、真实退出码（`0`）及通过用例总数。
