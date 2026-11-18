---
name: spec-thin-slice
description: >-
  Guides spec-driven requirement clarification, Red-Zone contract-first scaffolding,
  and vertical thin-slice breakdown for solo developers. Activate this skill when
  starting a new project, designing a major feature, or planning architecture so
  that the agent never dumps thousands of lines of code at once.
---

# 规格先行与垂直薄切片拆解技能 (Spec-First & Thin Slicing)

当用户准备启动新项目、新增复杂业务模块，或要求“先做需求分析/架构规划/拆解开发计划”时激活本技能。本技能吸收了 GitHub `spec-kit` 与 Thoughtworks SDD（规格驱动开发）核心方法，专为**不希望事后硬啃几千行陌生源码的个人独立开发者**裁剪。

---

## 执行四步曲（严禁跳步直接倾倒业务代码）

### Step 1：高危歧义前置追问（Ambiguity Grill · 最多 3～5 问）
在写任何设计文档或代码前，先扫描用户的目标描述，找出**如果靠 AI 自己瞎猜一定会出细节事故**的边界问题（一次最多集中问 3～5 个问题，给出推荐默认选项，不问琐碎废话）：
1. **外部输入与信任边界**：谁能触发系统？非白名单/异常格式/重复推送时静默丢弃还是报错回复？
2. **状态与写操作底线**：哪些数据 AI 可以直接改，哪些必须先出草稿卡等人类确认（HITL）或支持撤销？
3. **成本与性能红线**：哪些高频动作必须 `0 次大模型调用`（纯代码确定性处理）？长耗时任务怎么反馈进度？
4. **明确不做什么（Out of Scope）**：本期砍掉哪些容易引发过度设计的附加功能？

> 用户回答确认前，**停留在规划阶段，不创建业务源码文件**。

---

### Step 2：生成「垂直薄切片路线图」与验收矩阵
参考模板 [slice-spec-template.md](./references/slice-spec-template.md)，将整个项目或大特性拆解为 **Slice 0 + 3～6 个端到端垂直薄切片**：

- **Slice 0（🔴 红区契约底座，必做第一片）**：
  - 只包含项目的目录骨架、全局强类型数据结构（如 `schemas.py` / `types.ts`）、集中式系统提示词（`prompts/`）、安全与确认门禁纯函数签名（`guard.py`）以及环境配置校验（`config.py`）。
  - **严格控制 Slice 0 代码总量 <= 300 行**，供人类架构师花 10 分钟 100% 逐行精读拍板。
- **Slice 1 ～ Slice N（端到端垂直薄片）**：
  - 每一片必须是一根**从输入到落库/输出可独立跑通验证的细管道**（严禁按“第一片写全部 15 张表 SQL、第二片写全部 20 个工具、第三片写全部路由”横向分层堆砌！）；
  - 每一片预估新增生产代码 **150～300 行**；
  - 为每一片附上 **「5 行中文验收场景矩阵」（正常 1 条 + 刁钻边界 2 条 + 绝对禁令 1～2 条）**。

---

### Step 3：先交付并锁定 Slice 0（🔴 红区契约签字门禁）
路线图获用户点头后，**只生成 Slice 0（红区契约文件与空入口签名）**，运行类型检查/语法检查确认无误后停下汇报：
1. 列出刚刚创建的 🔴 红区文件精确链接与行数；
2. 明确提示用户花 5～10 分钟审阅字段默认值、枚举定义与提示词底线；
3. 等待用户确认“契约没问题，开始 Slice 1”。

---

### Step 4：移交 `red-green-tdd` 逐片闭环交付
从 Slice 1 开始，每一片严格移交 `red-green-tdd` 技能执行（独立盲测官先出红灯黑盒测试 → 锁死测试写实现变绿 → 验证实证 → Git 提交），**绝不在未经确认的情况下连续跨多个切片狂奔写码**。
