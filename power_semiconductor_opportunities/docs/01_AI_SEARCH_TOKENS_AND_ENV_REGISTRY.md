# AI 搜索引擎与大模型凭据盘点及独立 `.env` 注册说明

> **安全边界**：本工作区已配置 `.gitignore` 严格忽略 `.env`、`.env.*`、`data/*.db`。文档中仅保留脱敏指纹，严禁写入明文密钥。所有真实密钥已写入独立环境文件：
> - AI 搜索引擎独立配置：[`.env.ai_search`](../.env.ai_search)（模板：[env.ai_search.example](../env.ai_search.example)）
> - 大模型网关独立配置：[`.env.llm`](../.env.llm)（模板：[env.llm.example](../env.llm.example)）
> - 运行时调度配置：[`.env`](../.env)

---

## 1. 从用户 GitHub 仓库盘点出的付费 AI 搜索与大模型 Token

经过对 `JohnWissentek` 与 `Wissentek` 命名空间下全部 91 个仓库的深度检索（通过工作区 `.env.tokens` 授权的 GitHub API），确认已付费在用及预留的 AI 搜索/推理通道如下：

| 类别 | 服务名称 | 环境变量名 | 脱敏指纹 | 原始来源仓库与文件路径 | 状态 | 核心用途与路由策略 |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| **AI 搜索（中文主力）** | **秘塔 AI 搜索 (Metaso)** | `METASO_API_KEY`<br>`METASO_API_BASE` | `mk-43...E8C9` | `JohnWissentek/CCS_projects_China` (`.env_AI_search_engine`)<br>`JohnWissentek/competitor_analysis_agent` (`agam_marketing_agent/methods/metaso_search_api.md`) | **已付费激活** | 中国境内电力能源、半导体晶圆厂扩产、国产替代政策（十五五/双碳/大基金三期）、招标与中文学术文献（`webpage` / `scholar` / `document`）检索与 `/reader` Markdown 全文抽取 |
| **AI 搜索（全球主力）** | **Serper.dev (Google API)** | `SERPER_API_KEY`<br>`SERPER_TIME_RANGE` | `fc19e...a7af` | `JohnWissentek/CCS_projects_China` (`.env_AI_search_engine`)<br>`JohnWissentek/global_intelligence_analyst` (`agentic_workflow/.env`, `serper_search.py`) | **已付费激活** | 全球（欧美日韩台/东南亚/中东）Google 搜索、Google Scholar 论文与 Patents 检索；并作为中文域的交叉验证补充源（`gl=cn`） |
| **大语言模型网关（主力）** | **阿里云百炼 (DashScope)** | `DASHSCOPE_API_KEY`<br>`DASHSCOPE_BASE_URL` | `sk-ee...bb40` | `JohnWissentek/CCS_projects_China` (`.env.aliyun_bailian`)<br>`JohnWissentek/wechat_AI_agent_automation` (`.env.bailian`) | **已付费激活** | 驱动三级模型池（Ch 16）：`qwen3.8-flash`（高速并发压缩）、`qwen3.8-max`（深度规划/报告主笔）、`deepseek-v4-pro`（异构 RLVR 批评审查与裁判） |
| **扩展搜索预留** | Tavily / Exa / Perplexity / Firecrawl / Jina | `TAVILY_API_KEY` 等 | *未在历史仓库发现有效付费密钥（已预留槽位）* | `JohnWissentek/global_intelligence_analyst` (`.env.example`)<br>`JohnWissentek/bidding-information-collection` (`中国招投标平台与搜索引擎API参考手册.md`) | **预留扩展** | 在 `.env.ai_search` 填入任意一个 Key 后，搜索路由层自动解锁对应补充通道；网页全文抽取已免费内置 `https://r.jina.ai/` 作为 `/reader` 的零密钥兜底回退 |

---

## 2. 搜索引擎接口契约与工程避坑规范

依据 `JohnWissentek/competitor_analysis_agent` 与 `JohnWissentek/global_intelligence_analyst` 的实测经验，工作流内的 `src/pso_workflow/tools/search_router.py` 强制执行以下工程护栏：

1. **秘塔 Metaso 接口（`https://metaso.cn/api/v1`）**
   - **搜索端点**：`POST /search`，支持 `scope` 为 `webpage` / `scholar` / `document`。
   - **全文抽取端点**：`POST /reader`，传入 `{"url": "..."}` 返回高质量 `markdown`，仅对高权威（`T1`/`T2`）和相关性过滤后的 Top URL 调用以控制 Credits 消耗。
   - **避坑铁律 1（HTTP 200 业务错误码）**：密钥失效或参数异常时 Metaso 仍可能返回 `HTTP 200`，必须在解析层检查 JSON 体内的 `errCode`（`2005` 为密钥无效，`1000` 为参数错误）。
   - **避坑铁律 2（`size` 与 `page` 互斥）**：第 1 页仅传 `size`（如 `size=10`），第 2 页起仅传 `page`（不传 `size`），否则触发 `errCode=1000`。
   - **避坑铁律 3（结果数组字段动态映射）**：不同 `scope` 对应的返回数组键名不同：`webpages`、`scholars`、`documents`。

2. **Serper.dev 接口（`https://google.serper.dev`）**
   - **鉴权头**：`X-API-KEY: $SERPER_API_KEY`。
   - **多模态科研检索**：支持 `/search`（全网实时情报）、`/scholar`（IEEE/SEMI/Elsevier 论文与量测原理）、`/patents`（专利技术壁垒与设备厂布局），支持通过 `tbs=qdr:y` 控制时间窗以防旧报告干扰。

3. **中国优先、全球跟进的双擎路由规则（Ch 2 Routing）**
   - **`CN` 任务域**：优先调用 `Metaso(webpage + scholar)`，同时以 `Serper(gl="cn", hl="zh-cn")` 补充外企官网中文新闻与专利。
   - **`GLOBAL` 任务域**：优先调用 `Serper(search + scholar + patents)`，同时以 `Metaso(scholar)` 补充中文研究机构对海外产线（TSMC/Intel/Samsung/欧洲电网）的中文深度拆解。
   - **异常降级（Ch 12 Fallback）**：任一主引擎出现超时或限流，自动指数退避重试并无缝切换至另一引擎或 `r.jina.ai` 全文兜底。

---

## 3. 成本估算参考（对齐 Ch 16 资源感知与 Ch 19 审计）

- **Metaso Search**：约 `3 credits / 次`（合人民币约 `¥0.05/次`）；`Metaso Reader`：约 `3 credits / URL`。
- **Serper Search**：按千次计费（约 `$0.001 / 次`，合人民币约 `¥0.007/次`）。
- **DashScope LLM**：单次 Flagship 全流程运行（8 路并发 + STORM + PALMs + Elo + 5 卷深度报告 + Critic 循环 + Judge）预估总消耗约 **¥3–¥12 人民币**，全部计入 `outputs/.../06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json` 进行逐节点审计。
