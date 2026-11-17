# 02｜整体架构、三层记忆 SQLite 与世纪互联 OneDrive 归档设计

| 项 | 内容 |
| :--- | :--- |
| 文档版本 | v3.2（董事长助理开工基线版） |
| 更新日期 | 2026-11-17 |
| 关联文档 | [总览 README](../README.md) · [01-需求定义与日常场景](01-需求定义与日常场景.md) · [03-智能体内核与反思闭环](03-AI分拣工作流与确认机制.md) · [04-阿里云部署与操作手册](04-阿里云部署与分阶段实施路线.md) |

---

## 一、 四项核心架构选型与减法决策

我们在外围基础设施上坚持极简原则，在内核智能体与董事长管理视角上做满配：

### 1.1 为什么彻底砍掉 Odoo 19 MCP 对接？
1. **省掉脆弱联调**：通过 MCP 驱动 Odoo 需要维护多公司 `company_id`、必填字段校验、沙箱与生产库切换；管理“四大清单”本身很轻，绑定重型 ERP 属于过度设计。
2. **CEO 私人台账与公司多人系统物理隔离**：微信碎片、邮件摘要、未成熟想法和商业底价不进公司员工共享的 ERP，从根上消除权限误配泄密风险；待想法成熟后再单独进 Odoo 立项。
3. **纯云端文件夹可读性极强（零本地占盘）**：相比 Odoo 底层把附件转成哈希黑盒，直接存入世纪互联 OneDrive 标准分类文件夹，在浏览器网页端（SharePoint / OneDrive / Office Online）与驾驶舱直链里随时清晰可读。

### 1.2 为什么直接写入 Wissentek 世纪互联版 Office 365 OneDrive（纯云端不落本地）？
1. **纯国内高速链路 + 数据不出境**：世纪互联运营版（21Vianet）的认证（`login.chinacloudapi.cn`）与 Graph API（`microsoftgraph.chinacloudapi.cn`）均部署在中国大陆境内，呼和浩特阿里云 ECS 访问它稳定高速，核心商业文档完全留在国内合规环境。
2. **纯云端集中存储（零本机硬盘占用）+ 版本兜底**：省掉自建阿里云 OSS 与 Syncthing，**也不在本地 Mac 安装或同步 OneDrive 占用有限硬盘空间**；通过网页端 `chairman-vault`、OneDrive 网页版（Office Online 直接在线看 PDF/Excel/Word/Markdown）以及驾驶舱链接随时随地多端查阅，自带文件历史版本（Version History）和 93 天双层回收站。
3. **一套应用打通“收邮件 + 写网盘”**：若主力工作邮箱同在 Wissentek 世纪互联 Office 365 下，微软 Entra 后台注册 1 个内部应用即可兼顾只读收信（`Mail.Read`）与私有文档库归档。

### 1.3 为什么不套 OpenClaw / Hermes，而用自研《Agentic Design Patterns》专用内核？
1. **我们要“严守规矩的档案秘书”，不是“拿终端钥匙的自由跑腿工”**：OpenClaw 与 Hermes 擅长给大模型开放 Bash 终端自由探索；但在处理微信静默合并、`密：` 物理拦截、数字 100% 保真、1 卡确认才落盘等确定性约束时，专用状态图更稳定可控。
2. **严防外部邮件提示词注入（Prompt Injection）**：专用内核**物理上不提供 Shell 与任意外发工具**，外部邮件即使隐藏恶意指令也无法越权外传本地文件。
3. **“内账秘书”与“外勤跑腿”物理分家**：本系统（1 号专车）专职内部机密、四大清单、工时管理与 OneDrive 归档；未来若需要联网搜公开资料写临时脚本，再另起一个完全不碰企业邮箱和核心网盘的 Hermes（2 号外勤助手）即可。

### 1.4 为什么项目管理驾驶舱采用同进程内嵌自建，而不外挂 Plane / OpenProject 等重型开源项目？
1. **保护 2 核 4G 服务器资源**：Plane、OpenProject 等面向几十人研发团队的开源项目往往需要额外跑 PostgreSQL、Redis、RabbitMQ 等多容器，空载就吃掉 `2.5～3.5 GB` 内存，会让 ECS `firematrix` 吃紧；同进程内嵌 **FastAPI + 静态 ECharts/甘特图页面** 仅额外占用约 20–40 MB 内存。
2. **零同步延迟、零接口维护**：Web 驾驶舱直接读写同一份 SQLite `app.db`，在网页上拖拽调整工时或把想法转正立项，无需通过 API 同步，当场生效并立即触发更新 OneDrive 的 Markdown 看板。
3. **视角精准贴合董事长/总经理**：市面上团队软件关注“指派审批”，缺乏**“我的个人净投入工时 vs 外部等待日历跨度”**以及**“每天 6 小时工作容量红线预警”**，自建轻量页面可 100% 按老板复盘视角定制。

---

## 二、 四积木与同进程驾驶舱全景图

```mermaid
flowchart TB
    subgraph L1["1. 接入与输入护栏层（阿里云 ECS 常驻进程）"]
        WX["企业微信双口 HTTPS 回调（FastAPI 同进程）<br/>（微信客服 API 接合并转发 + 自建应用推简报）"]
        MAIL["企业邮件只读增量器<br/>（世纪互联 Graph Mail.Read / 只读 IMAP）"]
        BUF["去重 · 60s 静默合并 · Ch.18 护栏<br/>（识别『密：』前缀物理拦截零出网）"]
        WX & MAIL --> BUF
    end

    subgraph L2["2. 《Agentic Design Patterns》智能体内核（LangGraph Bounded Cyclic StateGraph）"]
        CACHE["ECS 临时缓存 & 按页文本提取"]
        ROUTE["Ch.2 & Ch.16 分诊路由<br/>（qwen3.8-flash）"]
        REACT["Ch.6 规划 & Ch.17 ReAct + 排期工时评估<br/>（qwen3.8-max + 四大受控工具箱）"]
        CE["Level 2 上下文工程压缩<br/>（清洗提炼为 EvidenceCard）"]
        CRITIC["Ch.4 异构模型反思博弈<br/>（deepseek-v4-pro + 规则硬核验）"]
        CARD["Ch.13 HITL 决策卡中断点<br/>（interrupt() 挂起等待回 1）"]
        BUF --> CACHE --> ROUTE --> REACT --> CE --> CRITIC
        CRITIC -->|"未通过（≤2轮）"| REACT
        CRITIC -->|"PASS"| CARD
    end

    subgraph L3["3. Ch.8 三层记忆 SQLite · 同进程驾驶舱 · 世纪互联 OneDrive"]
        SQL["checkpoints.db（短期断点）<br/>+ app.db（三层记忆 + 排期工时字段 + 混合检索）"]
        WEB["📊 同进程董事长项目管理驾驶舱 Web App<br/>（127.0.0.1:8090 ← Nginx 已备案 HTTPS 反代，自适应微信 WebView 与电脑大屏）"]
        OD["☁️ Wissentek 世纪互联版 OneDrive<br/>microsoftgraph.chinacloudapi.cn + Sites.Selected 私有库<br/>（00_我的四大清单/*.md + PARA 分类文档，分片上传后清缓存）"]
        CARD -->|"回 1 令牌放行"| SQL
        SQL <--> WEB
        SQL --> OD
    end

    subgraph L4["4. 纯云端与多端消费（零 Mac 本地磁盘占用）"]
        MAC["🌐 浏览器 / 手机 OneDrive（SharePoint 网页在线预览）& 电脑大屏驾驶舱"]
        WX_R["📱 绿色个人微信（微信插件每日简报 · 打卡 · 魔法链接直开 · Agentic RAG）"]
    end

    OD <-->|"纯云端 Office Online 在线预览"| MAC
    WEB <-->|"https://assistant.fire-matrix.com + 验证码"| MAC
    WEB <-->|"微信内直开（单次魔法链接）"| WX_R
    SQL --> WX_R
```

---

## 三、 极简 SQLite 单文件承载 Ch.8 三层记忆、排期工时与混合检索

整个系统在本地只维护两个轻量化 SQLite 文件（开启 WAL 模式），拒绝重造 20 张表迷你 ERP：

### 3.1 短期会话与断点记忆 (`data/checkpoints.db`)
- 由 **LangGraph `AsyncSqliteSaver`** 管理。挂起发出决策卡后，无论隔几小时回复或中途重启 ECS，均从断点原位恢复，已执行的模型调用和工具结果零重跑。

### 3.2 长期三类记忆、排期工时与混合检索 (`data/app.db` — 仅 3+1 张核心表)

| 记忆维度 | 承载表名 | 核心字段与设计 | 工程作用 |
| :--- | :--- | :--- | :--- |
| **长期语义记忆**<br>（记事实与原件） | **`raw_sources`**<br/>+ **`sources_fts`**（FTS5 `trigram`）<br/>+ 可选向量列 | `id`、`source_type`、`external_msg_id`、`sender`、`raw_text`、`content_hash`、`is_confidential`、`onedrive_raw_path`、`onedrive_archive_path`、`extracted_pages_json`（按页文本）、`embedding`（可选轻量向量） | **防丢与 Ch.14 混合检索**：同时支持字面 `FTS5 trigram` 与可选向量语义召回；大体积附件传完 OneDrive 即删 ECS 本地缓存，仅留纯文本索引。 |
| **长期项目字典**<br>+ 项目周期汇总 | **`projects`** | `id`、`name`、`aliases_json`、`category`（project/product/operation）、`work_domain`、`status`、`planned_start_date`、`target_end_date`、`total_estimated_hours`、`total_actual_hours`、`onedrive_folder`、`latest_brief`、`updated_at` | 全局项目目录地图 + 甘特图项目级起止周期与累计净投入工时统计。 |
| **四合一动态清单**<br>+ 工时排期与撤销 | **`list_items`** | `id`、`list_type`（`project_action`/`next_action`/`idea`/`waiting_for`）、`project_id`、`work_domain`、`title`、`owner`、`planned_start_at`、`planned_end_at`、`actual_start_at`、`actual_end_at`、`estimated_hours`、`actual_hours`、`priority`（`P0`/`P1`/`P2`）、`priority_score`、`status`、`stage`、`relation_note`、`source_ids_json`、`onedrive_doc_paths_json`、`undo_snapshot_json` | **一张表统一承载四大清单、甘特周期与个人净工时**：严格区分日历跨度（`planned_start_at`～`planned_end_at`）与本人净投入小时数（`estimated_hours`/`actual_hours`）；支持 Ch.20 动态优先级计算与 24h 内 `撤销` 快照回滚；同步渲染 OneDrive 4 份 `.md` 看板。 |
| **情景与程序性记忆**<br>（记纠偏、工时校准与规矩） | **`memory_rules`** | `id`、`memory_kind`（`episodic_case` 纠偏样例 / `procedural_rule` 个人铁律 / `effort_baseline` 同类工时校准基准）、`trigger_tags_json`、`rule_text`、`correction_count`、`status` | 既记你的分类与工作偏好（纠正 2 次自动提议升格为个人规则），也沉淀你做不同类型事项的真实耗时基准，让后续工时预估越来越准。 |

> 外加轻量 `model_calls` 排错与成本台账表（记录节点耗时、Token 成本及反思批注，默认 30 天滚动清理）。

---

## 四、 Wissentek 世纪互联版企业 OneDrive 直写与 `Sites.Selected` 隔离

### 4.1 关键修正：为什么必须用 `Sites.Selected` 私有文档库，而不用 `AppFolder`？
- **官方边界核实**：微软在个人消费版 OneDrive 中提供 `Files.ReadWrite.AppFolder` 沙箱权限，但**企业版 Office 365（含 Wissentek 世纪互联运营版）并不支持 `Files.ReadWrite.AppFolder`**。
- **Wissentek 世纪互联版标准最小权限方案 —— `Sites.Selected` 独立私有文档库**：
  1. 在 Wissentek 世纪互联 M365 中新建 **1 个仅你本人可见的私有 SharePoint 站点/文档库**（如 `董事长幕僚归档库`）；
  2. 在世纪互联 Entra 门户注册内部应用，赋予 Graph Application 权限 **`Sites.Selected`**（**绝不申请全租户的 `Sites.ReadWrite.All` 或 `Files.ReadWrite.All`**）；
  3. 由管理员通过 Graph API 仅把这 **1 个私有库（`MS_SITE_ID`）** 的 `write` 权限授予该应用；
  4. **效果**：程序在微软底层完全碰不到 Wissentek 组织里任何其他部门或同事的文件；服务端用 Client Credentials 7×24 自动换取令牌免人工登录；通过网页端 `Add shortcut to OneDrive -> My files` 绑定后，整个分类库与四大 `.md` 清单随时在浏览器（SharePoint / OneDrive 网页版）和驾驶舱直链里在线打开，**不在本地 Mac 占磁盘**！

### 4.2 世纪互联中国区端点与 2Mbps 带宽异步分片上传
- **世纪互联专属端点**：
  - 认证授权端点：`https://login.chinacloudapi.cn/{TENANT_ID}`
  - Microsoft Graph 端点：`https://microsoftgraph.chinacloudapi.cn/v1.0`
- **本地秒收 + 异步分片上传**：收到附件先落 ECS `/opt/wechat-agent/tmp_cache/` 秒级提取文本写入 SQLite FTS5，并在 2～3 秒内返回决策卡；确认写入后后台队列将 `< 4 MB` 文件直传、将 `>= 4 MB` 大文件调用 `createUploadSession` 分片断点上传至 `/sites/{MS_SITE_ID}/drive/root:/...`，核对云端 `eTag`/`size` 后立即删除 ECS 本地大文件缓存，确保 60G 系统盘永不写满。

### 4.3 私有库下的统一文件夹结构（纯云端 Markdown / Office Online 原生可读）

```text
Wissentek 私有库 (董事长幕僚归档库)/
├── 00_我的四大清单/                         ← 每次入库、打卡或驾驶舱修改后自动重绘覆盖
│   ├── 00_我的个人规则库.md                 # 已确认的程序性记忆规则（Ch.8）
│   ├── 01_今日与行动待办.md                 # 含 P0–P2、日历起止与预计净工时（Ch.20）
│   ├── 02_在途项目总览.md                   # 项目起止周期、累计工时、近况与链接
│   ├── 03_想法与孵化池.md                   # 闪念收集 / 调研评估 / 准备立项 / 留存参考
│   └── 04_等待他人清单.md                   # 外部依赖、等待天数与催办节点
├── 00_原件收件箱/                           ← 所有收到消息与附件的原始备份（按月，永不改写）
├── 01_项目归档/<项目简称>/                  ← 00_项目沟通与纪要.md + 01_报价合同与商务/ + 02_技术方案与现场/
├── 02_产品与研发/<产品简称>/                ← 00_研发动态与参数演变.md + 01_规格书与原厂资料/ + 02_设计BOM与测试/
├── 03_公司运营/                             ← 01_采购与供应商/ + 02_财务税务与法务/ + 03_人事招聘与制度/ + 04_IT与内部系统/
└── 04_想法与行业参考/                       ← 脑暴长文、脱敏调研简报、绝密直存文档
```

> 正式归档文件一律重命名为 **`YYYYMMDD_<项目或对象简称>_<原文件名>`**；重名自动加 `_v2`，不覆盖旧文件。

---

## 五、 模块化工程代码结构（含同进程 Web 驾驶舱）

对齐工作区 `Boiler_FBG_Product_RD_Workflow/agentic_workflow/src/bfbg_workflow/` 工程规范：

```text
wechat_assistant/
├── src/wechat_assistant/
│   ├── config.py             # 配置加载、CostLedger、assert_no_secrets_leaked、DashScopeLLMGateway
│   ├── schemas.py            # WorkflowState、EvidenceCard、TriageProposal（含工时与排期）、CriticVerdict
│   ├── graph.py              # LangGraph 有界闭环 StateGraph 装配与 SqliteSaver 断点恢复
│   ├── nodes/                # guardrail_router、react_investigator、context_compactor、
│   │                         # producer_drafter、heterogeneous_critic、hitl_gate、atomic_executor
│   ├── tools/                # 四大受控幕僚工具箱 + Ch.18 before_tool_callback 拦截器
│   │   ├── memory_tools.py   # hybrid_search、read_doc_pages、trace_timeline
│   │   ├── schedule_tools.py # calc_business_date、check_workload_and_schedule（负荷与工时校核）
│   │   ├── calc_tools.py     # analyze_excel_quote（报价单逐行 Diff 与含税精算）
│   │   ├── search_tools.py   # 脱敏前置拦截器 + Metaso/Serper/Jina 异步并发外搜
│   │   └── onedrive_tools.py # 世纪互联 Graph Sites.Selected 读写、分片上传与四大清单渲染
│   ├── web/                  # 同进程内嵌 FastAPI 董事长项目管理驾驶舱（响应式移动端卡片+桌面端甘特图，及微信魔法链接/6位验证码鉴权）
│   ├── intake/               # 微信客服 API（sync_msg 合并转发）与自建应用 HTTPS 回调接收器、60s 静默合并器、Graph Mail/IMAP 只读拉取器
│   ├── storage/              # SQLite 3+1 表、FTS5 索引、PDF/Office 按页提取
│   └── prompts/              # 节点提示词版本包（严禁含真实密钥、私有 URL 或商业底数）
└── tests/
    ├── unit/                 # 数字保真、工时周期分离校验、Excel Diff、脱敏护栏与路径安全单测
    ├── trajectory/           # Ch.19 Mock 工具轨迹评测（Trajectory Eval）
    └── regression/           # LLM-as-a-Judge 黄金回归测试集
```
