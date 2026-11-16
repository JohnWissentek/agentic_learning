# 02 · 方案 B（企业级主力）：自托管 Langfuse v3 全栈操作手册

## 1. 为什么企业级生产选择 Langfuse v3？

相比单机工具，Langfuse v3（完全开源 MIT 核心）是当前工业界标准的 LLM Engineering 企业级平台，其核心底座由 **6 个协同容器**构成：

| 容器服务 | 角色与架构价值 | 工程避坑配置（已在 `docker-compose.dual-stack.yml` 固化） |
| :--- | :--- | :--- |
| **`langfuse-web`** | Next.js Web 控制台 + Public API + 原生 OTLP 接收网关 (`:3000`) | 配置 `ENCRYPTION_KEY` 为严格 64 位十六进制字符（32 字节 AES-256），开启 Headless 免注册初始化 |
| **`langfuse-worker`** | 异步后台工作节点：消费 Redis 队列并将大体积 Trace/Generation 落库 | 等待 `postgres`、`clickhouse`、`redis`、`minio` 全部 `healthy` 后启动 |
| **`postgres:16`** | 存储组织、项目、API Key、Prompt 模板版本、评分规则与权限元数据 | 独立持久化卷 `postgres_data` |
| **`clickhouse:24.8`** | 列式分析型存储引擎：毫秒级过滤、聚合与全文搜索百万级 Prompt/Context | 配置 `CLICKHOUSE_CLUSTER_ENABLED=false` 适配单机高效运行 |
| **`redis:7`** | 高吞吐消息队列与异步缓冲，保障高并发多智能体不丢 Span | 开启密码认证与 `AOF/RDB` 持久卷 `redis_data` |
| **`minio`** | 本地 S3 兼容对象存储，安全承载几万字级的 Context 证据原文与多模态附件 | 通过入口命令启动前自动创建 `/data/langfuse` 存储桶并开启 `FORCE_PATH_STYLE=true` |

---

## 2. OrbStack 运行调优建议

1. **内存分配**：OrbStack 在 Apple Silicon 上按需动态分配内存，6 容器空闲时通常占用约 `1.8~2.8 GB`，高并发检索大型 Context 时峰值约 `3.5~4.5 GB`。建议在 OrbStack 设置中保持默认动态内存或设置上限 ≥ `8 GB`。
2. **数据持久化**：所有卷（`postgres_data`、`clickhouse_data`、`redis_data`、`minio_data`）均由 OrbStack 托管，执行 `make down` 不会丢失你的 Trace 历史；仅在需要彻底清空重建时才运行 `docker compose down -v`。

---

## 3. 浏览器操作指南（如何在 `:3000` 看流程与 Prompt/Context）

1. 打开浏览器访问 **[http://localhost:3000](http://localhost:3000)**。
2. 使用预置账号登录：
   - **Email**：`admin@wissentek.local`
   - **Password**：`Admin123456!`
3. 登录后直接进入预建项目 **`BoilerSense-AI-IPD`**，点击左侧菜单 **Tracing -> Traces**。
4. 点开任意一条工作流 Trace（如回放的 `BoilerSense-AI-IPD-Run (bfbg-native-5b28e04a)`）：
   - **看工作流结构与节点关系**：在左侧面板切换 **`Tree`（树形调用层级）**、**`Timeline`（并发瀑布流，直观看到 Stage 1 六专家与 Stage 5 七主笔的并行耗时条）** 与 **`Graph`（智能体节点有向图）**。
   - **看每次交互的完整 Prompt 和 Context**：点击树中任意紫色 **`GENERATION`** 节点（如 `Chief Product Manager`、`Specialist T3_OPTICS_HARDWARE`、`Writer 03`、`Adversarial Critic L1`）：
     - 右侧 **`Input` 卡片**：点击 `Pretty` / `Markdown` 切换，完整阅读当时注入的 `System Prompt`、`User Prompt`、`[EV-*]` 证据原文及 `[PHY-CALC]`/`[BOM-CALC]` 数据；
     - 右侧 **`Output` 卡片**：直接看到模型的推理思路与最终返回的 JSON/Markdown；
     - **`Metadata` 标签**：查看 `langgraph_node`、`model`、`input_tokens`、`output_tokens` 及精确起止时间戳。
5. **企业级进阶功能**：在右侧任意 Generation 卡片右上角点击 **`Open in Playground`**，可以直接把某次表现不满意的提示词和上下文拉入沙盒，微调一句话后用真实大模型重新生成对比！
