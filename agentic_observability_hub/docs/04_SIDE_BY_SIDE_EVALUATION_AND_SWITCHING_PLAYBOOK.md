# 04 · A vs B 同屏对比评估打分卡、实盘回放与切换手册

## 1. 零成本实盘回放：如何一秒把刚才 23 个智能体的完整对话灌入 A+B？

不需要重新消耗任何大模型费用！刚才在 [`Boiler_FBG_Product_RD_Workflow`](../Boiler_FBG_Product_RD_Workflow/README.md) 实盘生成的 23 个子智能体完整轨迹（包含数十万字符级未截断的 Prompt、注入证据 Context、内部 `thinking`、Token 统计和输出）已经保存在本地日志中。执行以下命令即可一键灌入三端：

```bash
cd /Users/john/Desktop/agentic_learning/agentic_observability_hub
make replay
```

随后请同时在浏览器打开以下 3 个标签页进行真实体验：
1. **[http://localhost:8765](http://localhost:8765)** — 点击顶部 `▶ 10x 动态重放工作流流转`，观察全局 8 阶段并行扇出与收敛动画，并点击任意节点查看完整零截断上下文。
2. **[http://localhost:3000](http://localhost:3000)** — 登录 Langfuse v3（`admin@wissentek.local` / `Admin123456!`），进入 `BoilerSense-AI-IPD -> Traces`，依次点开同一条 Trace 下的 **`Tree`**、**`Timeline`**、**`Graph`** 视图以及每个 `GENERATION` 的 `Input/Output` 和 `Playground`。
3. **[http://localhost:6006](http://localhost:6006)** — 在 Arize Phoenix 中点开同一条 Trace，对比它的气泡式 Message 视图、Span 瀑布树与搜索过滤体验。

---

## 2. 方案 B (Langfuse v3) vs 方案 A (Phoenix + Live Canvas) 同屏评估打分表

建议你在实际体验 10 分钟后，按以下 5 个维度给自己最关心的权重打分（1–5 分）：

| 评估维度 | 关注重点 | 方案 B：Langfuse v3 (`:3000`) | 方案 A1：Arize Phoenix (`:6006`) | 方案 A2：Live Canvas (`:8765`) |
| :--- | :--- | :---: | :---: | :---: |
| **1. 工作流全局拓扑与路线状态** | 未执行阶段是否可见、并发扇出/Critic循环是否直观 | ⭐⭐⭐（运行中仅展示已到达节点，有 `Graph` 标签） | ⭐⭐（偏重调用树与瀑布流） | ⭐⭐⭐⭐⭐（全图静态固定拓扑 + 动态流光） |
| **2. 超长 Prompt / Context 可读性** | 万字级 `[EV-*]` 证据与表格渲染、Markdown 高亮、全文检索 | ⭐⭐⭐⭐⭐（ClickHouse 秒搜 + Pretty/Markdown 切换） | ⭐⭐⭐⭐（Message 气泡清晰，偏重短中等长度） | ⭐⭐⭐⭐⭐（原生四标签页独立展开完整零截断全文） |
| **3. Prompt 版本迭代与工程协同** | 在线修改某一段提示词重跑对比、数据集回归评分 | ⭐⭐⭐⭐⭐（自带 Prompt Registry + Playground + Datasets） | ⭐⭐⭐（基础 Playground 与 Evals） | —（定位监控，按钮跳转到 B/A） |
| **4. 部署维护与资源开销** | OrbStack 容器数、内存占用与长期数据容量 | ⭐⭐⭐（6 容器，约 2.5~4.5 GB 内存，可扛千万级日志） | ⭐⭐⭐⭐⭐（单容器，约 500 MB 内存） | ⭐⭐⭐⭐⭐（单 Python 进程，几十 MB） |
| **5. 多团队/企业级审计能力** | 多项目隔离、用户权限、审计留痕、S3 大对象存储 | ⭐⭐⭐⭐⭐（天生企业级多租户架构） | ⭐⭐⭐（偏研究与单团队开发） | ⭐⭐（本地开发者驾驶舱） |

---

## 3. 未来按需切换或精简方案

本中心采用 Docker Compose `profiles` 与无耦合双路导出设计，未来你决定定型任一方案时**零重构成本**：

- **保留“企业主力方案 B + 全景拓扑大屏 (:8765)”**（最推荐长期企业配置）：
  ```bash
  make down && make up-b && make serve-canvas
  ```
- **仅保留“轻量方案 A (Phoenix + :8765)”**（释放约 2~3 GB 内存）：
  ```bash
  make down && make up-a && make serve-canvas
  ```
- **三端长期同开**（Mac 内存 ≥ 16 GB 时完全无压力）：
  ```bash
  make up-all && make serve-canvas
  ```
