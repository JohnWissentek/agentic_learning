# 03 · 方案 A（敏捷对照 + 全景实时拓扑监控台）：Arize Phoenix 与 Live Canvas (`:8765`)

## 1. 为什么在方案 B 之外，建议同时拉起方案 A 作为参照与前置控制台？

- **Arize Phoenix (`:6006`)**：纯 OpenInference/OpenTelemetry 原生显微镜，单容器启动极快、无登录墙、消息列表（System / User / Assistant 气泡化）与检索/评估曲线非常直观。
- **Live Topology Studio (`:8765`)**：专门补齐 Langfuse 与 Phoenix 都存在的“**全局全图预置拓扑 + 实盘动态流光 + 双平台一键跳转**”盲区！

---

## 2. 全景实时拓扑工作台 (`http://localhost:8765`) 的核心能力

1. **左屏：全流程节点与线路实时监控（仪表盘 1）**
   - 无论工作流正在跑第几步，左屏永远清晰显示**完整 8 阶段 28 个核心节点**及所有正交分支/并发扇出/Stage 6 Critic 反思回退虚线：
     - `⚪ 待命（灰）`：尚未轮到的下游阶段；
     - `🔵 运行中（亮蓝呼吸脉冲 + 线路流动动画）`：正在并发或串行推理的节点与连线；
     - `🟢 完成（翠绿）`：已验证通过并产出结果；
     - `🔴 打回重写 / 异常（告警红）`：Critic 审查触发 CRAG 补搜重写的循环分支。
   - 顶部提供 **`[▶ 10x 动态重放工作流流转]`** 按钮：即使在回顾历史运行（如 `bfbg-native-5b28e04a`），点击即可按时间轴逐阶段点亮节点和连线动画，重现并发扇出与收敛全过程！
2. **右屏：节点级 LLM Prompt & Context 显微镜（仪表盘 2）**
   - 点击左屏任意节点（或子智能体卡片），右屏立刻展示该节点的：
     - **完整输入（`System Prompt` + `User Prompt` + 注入的 `[EV-*]` / `[BOM-CALC]` 上下文原文）**——**100% 零截断完整保存**（哪怕是上万字的合成提示词也能全文搜索与复制）；
     - **模型内部思考链 (`Thinking / Reasoning`)** 与 **完整输出 (`Output / JSON / Markdown`)**；
     - **Token 统计、模型型号、耗时**；
     - 顶部提供两个直达按钮：**`在 Langfuse v3 (:3000) 打开此 Trace`** 与 **`在 Arize Phoenix (:6006) 查看`**，真正实现“一图统览全局，一键钻进两套企业平台细节对比”。

---

## 3. Arize Phoenix (`http://localhost:6006`) 浏览器看图与看上下文步骤

1. 浏览器打开 **[http://localhost:6006](http://localhost:6006)**（无需密码）。
2. 在 Projects 列表中点击 **`default`**（或筛选 `BoilerSense-AI-IPD`）。
3. 点开任意一条 Trace：
   - 左侧 Span Tree 清晰区分 **`CHAIN`（工作流阶段）**、**`AGENT`（专业角色智能体）**、**`LLM`（大模型调用）** 与 **`TOOL`（确定性 CLI/检索工具）**；
   - 点击右侧 **`Attributes`** / **`Input` / `Output`** 选项卡，即可像微信/Chat 对话框一样逐条检查发给模型的 `input_messages` 和返回结果。
