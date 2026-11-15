# 07. 旗舰智能体工作流班次运行概要与底层大模型溯源审计报告

> **运行批次 ID (`run_id`)**：`native-88e91cf7`  
> **执行完成时间**：`2026-11-15 11:58:10 CST` (`2026-11-15T03:58:10.140602+00:00`，工作流子代理窗口 `11:44:56–11:58:09 CST`，耗时约 13 分 14 秒)  
> **执行模式**：Antigravity IDE 原生 `run_workflow` + 确定性 Python CLI (`prepare-context` / `finalize-native`)  
> **输出目录名称**：`outputs/power_semiconductor_online_testing_2026_2036/`（已由通用默认名 `flagship_2026` 更名为贴合「电力能源 × 半导体制造在线测试仪器 2026–2036 十年机会研究」的专属目录，同步更新全仓库 `.env`、`src/`、`ide_workflows/`、`Makefile`、`.vscode/tasks.json`、`SKILL.md` 及 `README.md`）

---

## 一、 班次运行执行总览与核心验收指标

本次 `native-88e91cf7` 旗舰全流程（`sector=all`、`profile=flagship`）完整覆盖 **电力能源（P1–P4）** 与 **半导体芯片制造（S1–S4）** 共计 **8 条产业赛道、16 项高潜力在线测试仪器仪表技术/产品/应用机会**，严格贯彻 **“中国场景优先（2027–2031）→ 全球市场跟进（2031–2036）”** 双轨结构与 **“品质良率 / 制造降本 / 绿色环保 EHS / 高 ROI 与产业升级”** 四大价值支柱。

| 验收维度 | 契约门槛（Stage-Gate） | 本次实测结果 | 判定 |
| :--- | :--- | :--- | :---: |
| **Stage-Gate 综合裁判分** | $\ge 85.0 / 100$ | **100.0 / 100**（中国优先 `20` + 双时间窗 `20` + 物理机理 `20` + ROI与升级 `20` + 引用与行文 `20`） | PASS |
| **五卷主报告完整性** | 5 卷均 $> 500$ 字符 | Vol 00 (`32 KB`)、Vol 01 (`65 KB`)、Vol 02 (`52 KB`)、Vol 03 (`31 KB`)、Vol 04 (`51 KB`)，零截断 | PASS |
| **SQLite 证据库总量 (`EvidenceVault`)** | $\ge 48$ 条 | **225 条**去重核验证据（含 `24` 篇 `r.jina.ai` 全文深抓，Vault 检索日志 `40` 次查询） | PASS |
| **中国信源占比（China-First）** | $\ge 45.0\%$ | **63.11%**（中国证据 `142` 条 + 全球证据 `83` 条，Metaso + Serper 双引擎采集） | PASS |
| **正文去重精确引用数** | 可核验 `[EV-CN/GL-XXX]` | 正文五卷合计精确去重引用 **81 个**不同 `[EV-CN-...]` / `[EV-GL-...]` 证据编号 | PASS |
| **确定性 `[ROI-CALC]` 财务锚点** | 零 LLM 心理心算，全量锚定 Python | 跨五卷共完整锚定 **80 处 `[ROI-CALC]`** 指标，经 `finalize-native` 确定性重算校验闭环 | PASS |
| **异构 Critic 首轮审查结果** | 审核通过或触发自动修订/补搜闭环 | 首轮即 `decision: pass`（`overall_confidence = 98.5`），仅提示 2 项供应链与国际专利长期风险建议，无需重写（`critique_loops_executed = 0`） | PASS |

---

## 二、 关键透明度澄清：`model="pro"` 究竟调用了什么底层大模型？

针对“**`model="pro"` 实际运行了哪个大模型（是否为 `Gemini 3.1 Pro`、`Gemini 4 Argon`、`Gemini 4 Carbon` 或 `Claude Opus 5`）？**”这一核心问题，我们直接对 Antigravity 本会话系统日志（`transcript.jsonl`）及所有受 `task-288` 调度的 **32 个子智能体独立日志** 以及 `swarm(action="models", all=True)` 模型目录进行了逐行取证审计，结论如下：

### 2.1 三层实际底层模型实证清单（100% 日志取证）

| 执行层级 | 接口调用参数 / 运行角色 | 实际路由的底层模型 ID (`model` 字段) | 官方显示名称 / 模型归属 | 实测步数 / Token 消耗统计 | 是否为 Argon / Carbon / Opus 5.5？ |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. 主会话规划层 (Plan Mode)** | 对话需求分析、架构设计与方案编排 | **`gemini-pro-orchestrator`** | **`Orchestrator (Carbon)`**（即 **Gemini 4 Carbon** 规划编排器） | 本会话规划轮次持续使用（审计时已记录 48 个 Planner 步） | **是（Gemini 4 Carbon 规划器）** |
| **2. 主会话执行层 (Execute Mode)** | 文件编辑、测试验证、绘图脚本与工具编排 | **`gemini-flash-worker-agy`** | Gemini Flash Worker (Antigravity 执行模型) | 本会话执行轮次使用（审计时已记录 86 个 Worker 步） | 否（轻量执行底座） |
| **3. `run_workflow` 工作流子智能体层 (`task-288`)** | [`antigravity_run_workflow.py`](../../ide_workflows/antigravity_run_workflow.py) 中 `agent(..., model="pro")` 全部 **32 个子智能体**（1 Planner + 8 Track/STORM + 16 Elo + 5 Synth + 1 Critic + 1 Judge） | **`gemini-3.8-flash-tiered`** | **Gemini 3.8 Flash Tiered**（高吞吐思考预算分级运行时） | **32 个子会话全部一致**；合计消耗 **输入 `681,829` tokens + 输出 `356,946` tokens = 总计 `1,038,775` tokens**（`cache_read = 0`） | **否**：既不是 `Gemini 3.1 Pro`，也不是 `Gemini 4 Argon / Carbon` 或 `Claude Opus 5.5` |

### 2.2 为什么会路由到 `gemini-3.8-flash-tiered`？接口机制解析

1. **`run_workflow` 仅暴露 4 个抽象档位别名**：Antigravity 的 `run_workflow` / `invoke_subagent` 接口出于大规模并行配额调度设计，`model` 参数**只接收 4 个抽象别名**——`"inherit"`、`"pro"`、`"flash"`、`"flash_lite"`，不支持在 Python 工作流脚本里直接写入 `"gemini-4-argon-high"`、`"gemini-4-carbon-high"` 或 `"claude-opus-5-5-high"` 等具体模型字符串。
2. **宿主按并发与配额将 `"pro"` 映射至 `gemini-3.8-flash-tiered`**：在本环境中，`run_workflow(..., model="pro")` 被 Antigravity 运行时统一映射到带长思考预算的高并发分层版 `gemini-3.8-flash-tiered`，使得 **32 次多智能体调用（含 8 路并行与 5 卷长文合成）在 13 分 14 秒内一次无报错跑通**，且在独立 Critic（`98.5` 置信度）与 Stage-Gate Judge（`100.0/100`）双门禁下交付了极高质量的中文旗舰报告。
3. **Standalone CLI（模式 2 终端独立运行）模型区分**：脱离 Antigravity IDE 在终端执行 `pso-research run` 时，使用 `.env.llm` 中的 DashScope 外置模型，不经过 Antigravity 模型池（配置为 `fast=qwen3.8-flash`、`producer=qwen3.8-max`、`critic=deepseek-v4-pro` 异构交叉审查）。

### 2.3 当前 Antigravity 账号实测可用底层模型池（共 22 个，已取代早期 3.1 Pro / Opus 5）

经 `swarm(action="models", all=True)` 实时查询，当前账号中的底座已演进至 **Gemini 4** 与 **Claude 5.5** 代际（不再包含旧版 `Gemini 3.1 Pro` / `Claude Opus 5` 命名），完整列表如下：

| 模型家族 | 可精准点名 ID (`model` 传参) | 官方显示名称 | 适用的调用方式与建议场景 |
| :--- | :--- | :--- | :--- |
| **Google Gemini 4 Carbon** | `gemini-pro-orchestrator`<br>`gemini-4-carbon-high` / `medium` / `low` | `Orchestrator (Carbon)`<br>`Gemini 4 Carbon (High/Med/Low)` | **主规划器 & 旗舰深度综合引擎**；可通过 `swarm(action="add", model=...)` 或 UI 选定后用 `run_workflow(model="inherit")` 锁定 |
| **Google Gemini 4 Argon** | `gemini-pro-orchestrator-argon`<br>`gemini-4-argon-high` / `medium` / `low` | `Orchestrator (Argon)`<br>`Gemini 4 Argon (High/Med/Low)` | **物理机理攻坚与复杂工程推理旗舰**；同上可精准指定 |
| **Google Gemini 4 Hydrogen** | `gemini-4-hydrogen-xhigh` / `high` / `medium` / `low` | `Gemini 4 Hydrogen (XHigh/High/Med/Low)` | **超高推理预算前沿底座**（支持 `xhigh` 档），适合超长多约束深度综合 |
| **Anthropic Claude 5.5** | `claude-opus-5-5-high` / `medium` / `low`<br>`claude-sonnet-5-5-high` / `medium` / `low` | `Claude Opus 5.5 (High/Med/Low)`<br>`Claude Sonnet 5.5 (High/Med/Low)` | **跨模型家族异构 Critic / 深度报告撰写旗舰**（用 `Claude Opus 5.5` 审 `Gemini 4` 草稿可实现真正的异构对抗反思） |
| **Gemini 3.8 Flash & 开源** | `gemini-3.8-flash-high` / `medium` / `low`<br>`gpt-oss-120b-medium` | `Gemini 3.8 Flash (...)`<br>`GPT-OSS 120B (Medium)` | 高并发信息抽取、轻量结构化对齐 |

### 2.4 如果后续希望“真正在顶级旗舰模型（如 `Claude Opus 5.5` / `Gemini 4 Argon / Carbon`）”重跑，如何精确锁定？

1. **方法 A（零改代码，UI 选择 + `inherit`）**：直接在 Antigravity 对话界面左上角模型选择器选中 `Claude Opus 5.5 (High)` 或 `Gemini 4 Argon (High)` / `Gemini 4 Carbon (High)`，并令工作流调用时传入 `Args={"model": "inherit"}`（将 `target_model` 设为继承当前所选旗舰模型）。
2. **方法 B（真正异构多模型混合编队，`swarm` 工具）**：利用支持**精准模型 ID 锁定**的 `swarm(action="add", name=..., model="claude-opus-5-5-high" | "gemini-4-argon-high" | "gemini-4-carbon-high")`：例如用 `Gemini 4 Argon (High)` 负责 **Phase 3 物理机理与 8 赛道研判**、用 `Gemini 4 Carbon (High)` 负责 **Phase 5 五卷合成**、再用完全不同家族的 **`Claude Opus 5.5 (High)`** 担任 **Phase 6 异构 Critic 与 Stage-Gate 独立裁判**，形成真正的跨家族大模型对抗体系。

---

## 三、 7 阶段执行轨迹、硬编码 vs LLM 职责边界及调用统计

| 阶段 | 核心模块 / 脚本位置 | 节点执行性质 | 调用次数与并发方式 | 输入 Context 组装来源 | 产出成果与确定性保障 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1: 证据采集与财务预计算** | `cli.py::_cmd_prepare_context` + `search_router.py` + `evidence_vault.py` + `roi_calculator.py` | **100% 硬编码 Python** | `40` 次 Vault 检索日志；`225` 条证据 + `24` 篇全文 | `research_contract.yaml`、`domain_taxonomy.yaml`、`.env.ai_search`（Metaso+Serper） | 生成 `data/evidence_vault.db` 与 `data/native_context_bundle.json`（含全 16 项 PALMs `[ROI-CALC]`） |
| **Phase 2: 范围门禁与 Step-Back 规划** | `antigravity_run_workflow.py` (Phase 2) / `nodes/planner.py` | **硬编码前置裁剪 + LLM 分析** | **1 次 LLM 调用** (`Chief Metrology Architect`) | `track_briefs`（8 赛道名+工艺工段）、China-First/Dual-Horizon 指令、`NO_TOOL_DIRECTIVE`、`PLAN_SCHEMA` | 输出全篇 `step_back_thesis` 及 `phys_by_track[P1..S4]` 物理第一性原理映射 |
| **Phase 3: 8 赛道并研 + 四角色 STORM** | `antigravity_run_workflow.py` (Phase 3) + `_build_track_prompt` | **硬编码扇出隔离 + 8 路并行 LLM + 硬编码对齐归并** | **8 路全并发 LLM** (`Track P1..S4 Research + STORM`) | 赛道隔离切片：每赛道仅见本赛道 `12 CN + 10 GLOBAL` `[EV-...]` 摘要、2 个种子+`[ROI-CALC]`、4 个买方角色定义、`TRACK_SCHEMA` | 经白名单过滤剔除任何幻觉 ID，重新锚定 Python 财务基线并计算初始 Elo (`1500 + (pillar - 75)*4`) |
| **Phase 4: AI Co-Scientist Elo 锦标赛** | `antigravity_run_workflow.py` (Phase 4) + `_update_elo_local` | **硬编码瑞士制配对 + 16 场并行 LLM 裁判 + 硬编码评分冻结** | **2 轮 × 8 场并行 = 16 次 LLM 调用** (`K=32`) | 两两 `Option A` vs `Option B`（行业/周期/标题/逐字 `[ROI-CALC]` 财务/良率与升级机制）+ 35/25/20/20 裁判权重 + `ELO_SCHEMA` | 计算综合分排序 `#1..#16` (`0.55*Pillar + 0.45*NormElo`) 并确定性渲染分赛道 Markdown 表与卡片 |
| **Phase 5: 五卷并行深度撰写 + 索引编译** | `antigravity_run_workflow.py` (Phase 5) + `render_evidence_index` | **5 路并行 LLM 撰写 (Vol 00–04) + 100% 硬编码导出 (Vol 05)** | **5 路并发 LLM** (`Synthesizer 00..04`) | 按卷精细裁剪：如 `Vol 01` 仅注入电力表格/案卷/STORM/`ev_power`；`Vol 02` 仅注入半导体切片 + `SYNTH_RULES` + 禁用工具指令 | 生成 `00_`–`04_` 五卷长篇（共 `231 KB`）；Vol 05 (`113 KB`) 不经 LLM，100% 从 SQLite 直出防幻觉 |
| **Phase 6: 异构 Critic 与 Stage-Gate 门禁** | `antigravity_run_workflow.py` (Phase 6) + `_previews_and_checks` | **硬编码正则统计 + 2 次顺序 LLM 审查（含条件重修路由）** | **1 次 Critic + 0 次重修 + 1 次 Stage-Gate Judge** | `det_summary`（去重 ID 数 `81`、`[ROI-CALC]` 数 `80`、卷长）+ 5 卷 `头2200字 + 尾800字` 预览 + 契约/评分 Schema | Critic 给出 `pass (98.5)`，Judge 给出 5×20 维逐项评分（`finalized = 100.0/100`） |
| **Phase 7: 确定性终稿编译与遥测归档** | `cli.py::_cmd_finalize_native` | **100% 硬编码 Python** | 确定性终端落盘 | `data/native_outputs_bundle.json` + SQLite `EvidenceVault` + `domain_taxonomy.yaml` | 重算证据加权分与 5 项得分和防 LLM 加法漂移；写出 `00_`–`06_` 全部旗舰成果 |

---

## 四、 Top 16 在线测试仪器机会完整排位与 `[ROI-CALC]` 财务指标总表

> **说明**：下表依据最终落盘函数 `cli.py::_cmd_finalize_native` 的终审口径汇总（`evidence_count = 实际通过白名单校验的证据数`、`Stage-Gate = 100.0/100`、`06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json` 与此表 **Top 10 完全一致**）。（注：Phase 4 中间态生成的 `00_`/`03_` 正文内表格采用 `prepare-context` 阶段 `min(4, len)` 预评分，故 Pillar 分与终态略有 `~3` 分系统级差异；全系 16 项机会的 **CAPEX、年净现金流、回收期、5年IRR、5年NPV、ROI 分级** 等底层财务数值完全一致、一字不差。）

| 终审排名 | 机会编号 | 赛道 | 时间窗 | 机会名称 | 单套 CAPEX | 年净现金流 | 回收期 `[ROI-CALC]` | 5年 IRR `[ROI-CALC]` | 5年 NPV `[ROI-CALC]` | 终审支柱分 / Elo | ROI 分级 |
| :---: | :--- | :---: | :---: | :--- | ---: | ---: | ---: | ---: | ---: | :---: | :--- |
| **#1** | `OPP-S4-5Y-02` | S4 | 5-10y | 免耦合水非接触激光超声+红外光热混合键合(Hybrid Bonding)纳米空洞及玻璃TGV在线检测仪 | ¥420.0万 | ¥1184.0万/年 | **4.3月** | **281.6%** | ¥4068.3万 | 96.21 / 1616.4 | Tier-A (<=12m Ultra-High ROI) |
| **#2** | `OPP-S2-5Y-02` | S2 | 5-10y | 面向3D NAND超深孔与GAA/CFET的紧凑型高亮度液态金属靶X射线CD-SAXS/XRF在线量测系统 | ¥550.0万 | ¥979.0万/年 | **6.7月** | **176.9%** | ¥3161.2万 | 92.9 / 1603.22 | Tier-A (<=12m Ultra-High ROI) |
| **#3** | `OPP-S2-3Y-01` | S2 | 3-5y | 机台内嵌式(Integrated)宽光谱穆勒矩阵椭偏+皮秒超声膜厚/OCD在线闭环量测模块 | ¥310.0万 | ¥724.0万/年 | **5.1月** | **233.0%** | ¥2434.5万 | 95.1 / 1580.38 | Tier-A (<=12m Ultra-High ROI) |
| **#4** | `OPP-S3-3Y-01` | S3 | 3-5y | 8英寸SiC外延片UV-PL缺陷映射+非接触FTIR/电晕电荷掺杂厚度一体化在线量测仪 | ¥280.0万 | ¥739.5万/年 | **4.5月** | **263.7%** | ¥2523.3万 | 94.92 / 1579.73 | Tier-A (<=12m Ultra-High ROI) |
| **#5** | `OPP-P4-3Y-01` | P4 | 3-5y | 煤电/垃圾焚烧灵活调峰锅炉声波二维测温+原位TDLAS多组分燃烧闭环优化系统 | ¥98.0万 | ¥204.5万/年 | **5.8月** | **207.9%** | ¥677.2万 | 89.6 / 1590.07 | Tier-A (<=12m Ultra-High ROI) |
| **#6** | `OPP-S4-3Y-01` | S4 | 3-5y | 亚10微米TSV/微凸点高速在线3D X射线层析成像(AXI/CT)与AI缺陷判别站 | ¥360.0万 | ¥840.0万/年 | **5.1月** | **232.8%** | ¥2824.3万 | 92.7 / 1570.78 | Tier-A (<=12m Ultra-High ROI) |
| **#7** | `OPP-S1-3Y-01` | S1 | 3-5y | 12英寸晶圆厂多流路切换ppt级AMC分子污染在线软电离质谱/CRDS监控系统 | ¥220.0万 | ¥489.0万/年 | **5.4月** | **221.6%** | ¥1633.7万 | 92.46 / 1569.61 | Tier-A (<=12m Ultra-High ROI) |
| **#8** | `OPP-P1-3Y-01` | P1 | 3-5y | 无氦化高频在线质谱/VOC微漏检测系统（替代传统真空氦检与产线电解液泄漏筛查） | ¥115.0万 | ¥250.5万/年 | **5.5月** | **217.1%** | ¥834.6万 | 86.76 / 1580.01 | Tier-A (<=12m Ultra-High ROI) |
| **#9** | `OPP-P2-5Y-02` | P2 | 5-10y | GW级钙钛矿/晶硅叠层产线纳秒激光PL+高光谱薄膜结晶态在线闭环检测系统 | ¥160.0万 | ¥246.0万/年 | **7.8月** | **152.2%** | ¥772.5万 | 89.79 / 1558.66 | Tier-A (<=12m Ultra-High ROI) |
| **#10** | `OPP-S3-3Y-02` | S3 | 3-5y | 高压碳化硅功率芯片晶圆级动态开关/栅氧早期失效(KGD)高通量在线测试分选平台 | ¥340.0万 | ¥769.0万/年 | **5.3月** | **225.6%** | ¥2575.1万 | 93.88 / 1543.93 | Tier-A (<=12m Ultra-High ROI) |
| **#11** | `OPP-P3-3Y-01` | P3 | 3-5y | SF6环保替代气体(C4F7N/混合气)产线纯度及痕量分解物在线红外-质谱分析仪 | ¥88.0万 | ¥152.5万/年 | **6.9月** | **172.1%** | ¥490.1万 | 89.46 / 1557.05 | Tier-A (<=12m Ultra-High ROI) |
| **#12** | `OPP-P2-3Y-01` | P2 | 3-5y | 绿氢电解槽膜电极(CCM)贵金属载量高速在线微区XRF+微针孔缺陷协同检测仪 | ¥135.0万 | ¥245.0万/年 | **6.6月** | **180.4%** | ¥793.7万 | 89.09 / 1556.12 | Tier-A (<=12m Ultra-High ROI) |
| **#13** | `OPP-P3-5Y-02` | P3 | 5-10y | 特高压海缆XLPE交联挤出全周向太赫兹+多角度X射线微杂质/偏心在线检测站 | ¥240.0万 | ¥343.0万/年 | **8.4月** | **141.2%** | ¥1060.2万 | 88.09 / 1552.08 | Tier-A (<=12m Ultra-High ROI) |
| **#14** | `OPP-S1-5Y-02` | S1 | 5-10y | 先进制程循环湿法清洗(SC1/HF/SPM)单机台原位金属杂质与药液组分在线光学-质谱联用仪 | ¥260.0万 | ¥483.0万/年 | **6.5月** | **184.8%** | ¥1571.0万 | 90.94 / 1532.39 | Tier-A (<=12m Ultra-High ROI) |
| **#15** | `OPP-P1-5Y-02` | P1 | 5-10y | 太赫兹时域光谱与空气耦合超声融合的干法电极/全固态电解质界面在线无损成像仪 | ¥185.0万 | ¥236.0万/年 | **9.4月** | **125.4%** | ¥709.6万 | 90.0 / 1527.77 | Tier-A (<=12m Ultra-High ROI) |
| **#16** | `OPP-P4-5Y-02` | P4 | 5-10y | 电力CCUS与掺氢燃机多流路软电离质谱(IMR-MS)痕量杂质及腐蚀预警分析站 | ¥195.0万 | ¥184.0万/年 | **12.7月** | **90.6%** | ¥502.5万 | 84.92 / 1509.08 | Tier-B (12-24m Strong ROI) |

---

## 五、 本输出目录全套交付物文件导览（`00`–`08`）与安全审计

1. `00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md` (`32 KB`) — 执行摘要、电力×半导体底层共性测量物理交叉协同图谱及 3–5 年 vs 5–10 年双时间窗矩阵
2. `01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md` (`65 KB`) — 电力能源 P1–P4（动力/固态电池、钙钛矿/绿氢、特高压/SF6替代/海缆、火电调峰/CCUS）深度研报
3. `02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md` (`52 KB`) — 半导体 S1–S4（Fab AMC/湿化特气、前道膜厚/OCD/CD-SAXS、SiC/GaN 动态 KGD、2.5D/3D 混合键合）深度研报
4. `03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md` (`31 KB`) — Python PALMs 确定性制造端 ROI/NPV/IRR 模型、三档稼动率压力测试与 Elo 锦标赛解析
5. `04_PRODUCT_TECH_AND_UPGRADE_STRATEGY_PLAYBOOK.md` (`51 KB`) — 共性测试仪器四大硬件平台复用、实验室→在线五大工程化坎及先中国后出海 BD 手册
6. `05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md` (`113 KB`) — 由 `data/evidence_vault.db` 确定性直出的 225 条（142 CN + 83 GLOBAL）去重证据总表
7. `06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json` (`31 KB`) — 契约检验、Stage-Gate `100.0/100` 裁判打分、Elo 对局轨迹与全链路底层模型/Token 遥测记录
8. `07_WORKFLOW_RUN_SUMMARY_AND_MODEL_PROVENANCE.md`（本报告） — 班次运行概要、`model="pro"` 真实底座溯源澄清与 16 项终审指标对照表
9. `08_AGENTIC_WORKFLOW_ARCHITECTURE_A0.drawio` / `.svg` / `.pdf`（同步存根于 `docs/03_AGENTIC_WORKFLOW_ARCHITECTURE_A0.*`） — **A0 幅面**全节点工作流、硬编码 vs LLM 性质标识及每一跳 Context 组装架构大图
