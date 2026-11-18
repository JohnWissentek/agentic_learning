---
name: blind-audit-and-trace
description: >-
  Replaces exhausting line-by-line manual code review with Red/Yellow/Green risk
  triage, isolated adversarial spec-vs-code blind auditing, and Golden Sample
  execution trace tables. Activate this skill when taking over or auditing an
  existing AI-generated project, verifying details hidden behind flowcharts, or
  performing a pre-release production readiness gate.
---

# 免全量审码：三区分拣、独立盲审与黄金样本回放技能 (Blind Audit & Golden Trace)

当用户面对已经生成的大量代码感到审阅耗时（如“不想一行行啃代码，帮我核查细节有没有漏洞”）、准备接管存量 AI 项目，或在上线前做生产级封版体检时激活本技能。

---

## 标准三步体检工作流

### Step 1：全仓「红黄绿三区」风险分拣（压缩 90% 人类阅读面）
扫描目标项目的源码目录（如 `src/` 与 `tests/`），统计各文件行数，输出一张清晰的 **三区审阅分拣表**：

1. **🔴 红区（人类必读清单，目标合计 <= 全项目 10% 行数）**：
   - 精确列出全局数据结构契约（`schemas`）、集中式提示词（`prompts`）、权限/白名单/确认令牌/脱敏门禁（`guard` / `auth`）的文件链接与行号范围；
   - **违规告警**：若发现业务胶水大文件（如上千行的 `graph.py` 或 `app.py`）中暗藏硬编码的野生 System Prompt、白名单常量或金额规则，立即标红指出，并建议抽离回红区。
2. **🟡 黄区（机器盲审与轨迹回放区）**：列出核心状态机编排、外部网关收发、数据库存储文件。明确告知用户：**“此区无需人工逐行通读，交由 Step 2 盲审与 Step 3 轨迹表核验。”**
3. **🟢 绿区（0 源码阅读，实机效果验收区）**：列出前端单页/组件、报表排版、画图脚本。建议直接启动预览或委派 `browser` 子智能体点测截图。

---

### Step 2：委派独立挑刺审计官执行「零客套盲审对账」
调用 `invoke_subagent` 启动只读子智能体 **`adversarial-code-auditor`**（严禁主智能体自己审自己刚写的代码！），向其明确指派：
- **对账基准**：项目下的需求规格文档、架构设计文档及流程图说明；
- **被审对象**：目标项目 `src/` 全部源码与 `tests/` 既有测试套件；
- **必查五项**：① 文档写了但代码缩水/漏做的细节；② 跨路由分支遗漏（如某分支漏调前置解析或门禁）；③ 生产级脆弱点（无 `timeout`、裸 `except: pass` 静默吞错、非幂等重复执行）；④ 安全与不可信输入边界漏洞；⑤ `tests/` 中的假测试（如把数据库本身 Mock 掉、空洞断言）。

收到审计官报告后，将其整理的 `[P0 / P1 / P2]` 真实出入点原汁原味呈现给用户，附精确文件行号链接与二选一拍板建议，绝不掩饰问题。

---

### Step 3：构建并运行「黄金真实样本实弹轨迹表」（替代看静态流程图）
当用户希望直观确认“真实脏数据进来后，每一步到底调了什么、数据库改了什么”时，参考 [golden-trace-template.md](./references/golden-trace-template.md)：

1. 设计 **8～12 条高覆盖黄金真实样本**（覆盖：正常交办、快捷 0 模型口令、重复 `msg_id` 幂等、非白名单越权、带附件混合提问、无待确认卡误触确认、上游超时/空检索兜底）；
2. 编写并运行轻量本地回放探针脚本（使用真实临时数据库 + 工具调用/模型调用计数器钩子，不污染生产库）；
3. 直接向用户输出一张 **一页纸 Markdown 实弹轨迹体检表**：
   `样本编号与输入 | 实际命中路由 | 触发的工具与模型次数 | 数据库前后 Diff | 最终回复摘要 | 门禁判定`
4. 用户仅需 3 分钟扫完这张表即可锁死全部动态执行细节。若某行暴露偏差，移交 `red-green-tdd` 技能先补红灯测试再修代码。
