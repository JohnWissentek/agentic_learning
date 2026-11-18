"""Generate an oversized landscape Draw.io diagram (5600x3600) with zero box/line collisions."""
import html
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "04-AI分拣工作流全景图_A0.drawio"

STYLE_HARDCODE = "rounded=0;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#2b6cb0;strokeWidth=2;fontSize=13;align=left;verticalAlign=top;spacing=10;spacingTop=14;spacingLeft=16;spacingRight=14;"
STYLE_LLM = "rounded=0;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#6b46c1;strokeWidth=2.5;fontSize=13;align=left;verticalAlign=top;spacing=10;spacingTop=14;spacingLeft=16;spacingRight=14;"
STYLE_CONTEXT = "rounded=0;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#2f855a;strokeWidth=2;fontSize=13;align=left;verticalAlign=top;spacing=10;spacingTop=14;spacingLeft=16;spacingRight=14;"
STYLE_GUARD = "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#dd6b20;strokeWidth=2.5;fontSize=13;align=left;verticalAlign=top;spacing=10;spacingTop=14;spacingLeft=16;spacingRight=14;"
STYLE_CRITIC = "rounded=0;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#c53030;strokeWidth=2.5;fontSize=13;align=left;verticalAlign=top;spacing=10;spacingTop=14;spacingLeft=16;spacingRight=14;"
STYLE_ZONE = "rounded=0;whiteSpace=wrap;html=1;fillColor=#f8f9fa;strokeColor=#adb5bd;strokeWidth=2;dashed=1;fontSize=16;fontStyle=1;align=left;verticalAlign=top;spacing=12;spacingTop=14;spacingLeft=18;"
STYLE_TITLE = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=24;fontStyle=1;"

nodes: list[str] = []
edges: list[str] = []


def add_box(cid: str, x: int, y: int, w: int, h: int, title: str, body: str, style: str) -> None:
    inner = f"<b>{html.escape(title)}</b><br/>" + "<br/>".join(html.escape(line) for line in body.splitlines())
    label = html.escape(inner, quote=True)
    nodes.append(
        f'<mxCell id="{cid}" value="{label}" style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def add_zone(cid: str, x: int, y: int, w: int, h: int, title: str) -> None:
    nodes.append(
        f'<mxCell id="{cid}" value="{html.escape(title, quote=True)}" style="{STYLE_ZONE}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def add_edge(
    eid: str,
    src: str,
    dst: str,
    label: str = "",
    color: str = "#2b6cb0",
    dashed: bool = False,
    width: int = 2.5,
    exit_xy: tuple[float, float] | None = None,
    entry_xy: tuple[float, float] | None = None,
    points: list[tuple[int, int]] | None = None,
) -> None:
    dash = "dashed=1;" if dashed else ""
    anchors = ""
    if exit_xy:
        anchors += f"exitX={exit_xy[0]};exitY={exit_xy[1]};exitDx=0;exitDy=0;"
    if entry_xy:
        anchors += f"entryX={entry_xy[0]};entryY={entry_xy[1]};entryDx=0;entryDy=0;"
    style = (
        f"edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;"
        f"{anchors}strokeColor={color};strokeWidth={width};{dash}fontSize=12;fontStyle=1;labelBackgroundColor=#ffffff;"
    )
    pts_xml = ""
    if points:
        pts_xml = '<Array as="points">' + "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in points) + "</Array>"
    edges.append(
        f'<mxCell id="{eid}" value="{html.escape(label, quote=True)}" style="{style}" edge="1" parent="1" source="{src}" target="{dst}">'
        f'<mxGeometry relative="1" as="geometry">{pts_xml}</mxGeometry></mxCell>'
    )


# Title & Legends (5600 wide canvas)
nodes.append(
    f'<mxCell id="title" value="董事长 AI 私人幕僚 — 智能体五阶段全链路工作流、硬编码 vs 大模型边界与上下文装配（超宽无遮挡全景图）" style="{STYLE_TITLE}" vertex="1" parent="1">'
    f'<mxGeometry x="80" y="24" width="2400" height="44" as="geometry"/></mxCell>'
)
add_box("leg1", 2540, 16, 360, 78, "节点色：硬编码确定性机制", "纯 Python/正则/SQL/API，0 次大模型", STYLE_HARDCODE)
add_box("leg2", 2930, 16, 360, 78, "节点色：大语言模型（LLM）", "标明模型档位、Prompt 与 Pydantic 契约", STYLE_LLM)
add_box("leg3", 3320, 16, 360, 78, "节点色：上下文 & 存储底座", "SQLite 记忆 / FTS5 / 21Vianet", STYLE_CONTEXT)
add_box("leg4", 3710, 16, 360, 78, "节点色：护栏 / 确认 / 审计", "白名单 / 令牌门禁 / HITL / Critic", STYLE_GUARD)
add_box(
    "leg_edges",
    4100,
    16,
    1400,
    78,
    "连线颜色图例（所有连线走专用空白走廊，绝不穿过卡片）",
    "蓝实线=主业务与数据流 ｜ 绿虚线=上下文装配/真值读取流 ｜ 紫实线=LLM路由与草案流 ｜ 红虚线=Critic驳回反思 ｜ 橙实线/虚线=确认放行 & 18:00盘点回流",
    "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#6c757d;strokeWidth=1.5;fontSize=12;align=left;verticalAlign=top;spacing=8;spacingTop=12;spacingLeft=14;",
)

# ==================== 阶段一：zone x=80..960, cards x=180..840 (left/right internal gutters 100px each) ====================
add_zone("z1", 80, 140, 880, 2940, "阶段一｜多入口接入、附件解析与快捷指令前哨（硬编码通道）")
add_box(
    "n_wx_app", 180, 220, 660, 240,
    "1A. 个人微信主力入口（个人幕僚室 → AI工作助理）",
    "• 接口：FastAPI POST /api/wecom/app/callback（wecom_gateway.py）\n"
    "• 硬编码机制：AES-256-CBC 验签解密 → XML 解析 → <0.5s 异步到达回执\n"
    "• 自动合并多条转发：停手等 2 秒即自动打包为同一件事处理（不必输「好了」，想跳过等待时可选发「好了」）\n"
    "• 语音处理：拉取 AMR/SILK 临时媒体 → 调用 qwen3-asr-flash 转写原文",
    STYLE_HARDCODE,
)
add_box(
    "n_wx_kf", 180, 520, 660, 200,
    "1B. 备用客服通道（接收微信原生「合并转发」卡片）",
    "• 接口：POST /api/wecom/kf/callback → sync_msg() 增量拉取\n"
    "• 硬编码门禁：owner_external_userid 单人白名单校验（非本人直接丢弃）\n"
    "• 硬编码解析：递归展开 merged_msg 聊天记录合并为结构化文本",
    STYLE_HARDCODE,
)
add_box(
    "n_mail", 180, 780, 660, 250,
    "1C. 香港/国际版 Office 365 Outlook 只读增量器（mail_poller.py）",
    "• 端点：login.microsoftonline.com + graph.microsoft.com/v1.0（Mail.Read 只读）\n"
    "• 硬编码白名单：matches_mail_allowlist() 仅放行 V&F / Tera / B&D 往来邮件\n"
    "• 硬编码防注入：跳过退订/验证码噪音，正文包裹 [UNTRUSTED_EXTERNAL_DATA]\n"
    "• 去重：按 internetMessageId 写入 seen_external_ids 表，同一封邮件只分析一次（MSAL 令牌缓存，不阻塞事件循环）",
    STYLE_HARDCODE,
)
add_box(
    "n_att", 180, 1110, 660, 270,
    "1D. 多格式附件提取、兜底机制与原件备份（ingest_inputs）",
    "• 已支持硬编码解析：PDF（pypdf 按页）、Word（.docx）、Excel（.xlsx/.xlsm）、CSV/TSV/纯文本、以及 .zip 安全递归解压（防路径穿越/限30文件/50MB）\n"
    "• 硬编码处理不了的格式（.dwg CAD/加密PDF或加密包/扫描件/未知二进制）：\n"
    "  1) 拦截二进制乱码入库，仅存 [未解析附件+文件名+大小] 元信息占位；\n"
    "  2) 100% 保留原件传至 21Vianet OneDrive 00_原件收件箱/（永不丢原件）；\n"
    "  3) 靠你的附言/语音说明关联项目与待办，并在确认卡诚实提示未解析",
    STYLE_HARDCODE,
)
add_box(
    "n_fast_guard", 180, 1460, 660, 340,
    "1E. 零大模型快捷指令前哨（handle_incoming_turn）",
    "• 亚毫秒快捷指令（全部 0 次 LLM 调用，直连数据库或返回链接）：\n"
    "  - 看板 / 驾驶舱 → 返回固定驾驶舱链接（长期有效，首次微信 6 位码验证后本机 180 天免密直开）\n"
    "  - 负荷 / 待办 → 查询近 3 日日程排期分布与 Top 待办\n"
    "  - 撤销 → 24h 内 undo_last_commit() 原子回滚并重绘 OneDrive\n"
    "  - 开始 #N / 完成 #N [耗时] → 更新状态与 actual_span_days 并重绘\n"
    "• 整轮持有可重入锁（同一时刻只处理一条，心跳标签不串扰）；工作流异常时先写入原话再如实告知「未生成待办」",
    STYLE_GUARD,
)

# ==================== 阶段二：zone x=1100..2080, cards x=1200..1980 ====================
add_zone("z2", 1100, 140, 980, 2940, "阶段二｜4 层多时段上下文装配引擎 ContextAssembler（硬编码确定性组装）")
add_box(
    "ctx_l1", 1200, 220, 780, 330,
    "Layer 1：跨天滚动摘要 + 近期对话流（episode_summaries + conversation_turns）",
    "• 滚动会话摘要（episode_summaries）：每 8 轮先写抽取式摘要（不阻塞回复），再由 qwen3.8-flash 后台合并为语义摘要（失败保留抽取式），\n"
    "  即使隔了多天或超出 30 轮原文窗口，依然自动置顶注入上下文\n"
    "• 近期对话流：按 thread_id='owner' 取最近 30 轮（<=600字/轮）\n"
    "• 硬编码时间边界：间隔 > 30 分钟插跨时段分割线与谨慎区分警告；\n"
    "  从 <=60 分钟连续窗口提取最多 6 个 anchor_entities",
    STYLE_CONTEXT,
)
add_box(
    "ctx_l2", 1200, 600, 780, 310,
    "Layer 2：待确认提案暂存卡（pending_proposals，防盲目入库）",
    "• 含义：AI 生成方案发到微信后，在你回复「1 确认」或「0 取消」前暂存的草案卡\n"
    "• 作用：让你在微信里不用死记编号，直接回「按这个办」「改成下周五」「为什么排明天」\n"
    "  时，AI 能看懂你针对的是哪张尚未落盘的卡片\n"
    "• 新鲜度判定：<=60 分钟视为当前连续讨论，>60 分钟防止误改昨天的旧卡片",
    STYLE_CONTEXT,
)
add_box(
    "ctx_l3", 1200, 960, 780, 320,
    "Layer 3：工作区快照 + 跨项目自动挂载卡（projects + list_items + memory_rules）",
    "• 跨项目自动挂载（借鉴 IDE 工作区感知）：当输入或近期锚点提及项目名/别名时，\n"
    "  自动挂载最多 3 张【相关项目上下文卡】（板块、周期、最新进展与关联待办）\n"
    "• 高容量真值快照：projects(30) + 未完成 list_items(60) + memory_rules(20)\n"
    "• 原则：直接从数据库实时读取真值，严禁大模型凭记忆猜测项目编号与状态",
    STYLE_CONTEXT,
)
add_box(
    "ctx_l4", 1200, 1340, 780, 320,
    "Layer 4：FTS5 全文检索文档与历史对话（retrieve_long_horizon_evidence）",
    "• 触发对象：quick_qa_responder 与 react_investigator 节点\n"
    "• 检索词拼装（硬编码去重）：search_queries + anchor_entities + 中文3-4字滑窗词\n"
    "• 双路 FTS5 trigram 召回：\n"
    "  1) raw_sources / sources_fts 文档按页切片；\n"
    "  2) conversation_turns_fts 全文索引历史对话（自动回填存量 + LIKE 短词兜底）",
    STYLE_CONTEXT,
)
add_box(
    "ctx_render", 1200, 1740, 780, 440,
    "上下文拼装渲染与防幻觉原则（render_for_router & 节点拼装模板）",
    "• 路由器输入拼装顺序：[当前时间戳] → [跨天滚动会话摘要] → [相关项目上下文卡] → [近期对话流与时间间隔] → [待确认卡片] → [在途快照] → [用户输入]\n"
    "• 提案起草输入拼装：今天日期 → 跨天滚动摘要 → 相关项目卡 → 近期对话 → 在途快照 → 补全意图 → EvidenceCard[] → 工具事实 → 纠偏/整改要求\n"
    "• 四大核心原则：\n"
    "  1) 上下文预算隔离（适配 128K 大模型）：文档 <=1000字/条(top10)、历史对话 <=600字/条(top8)、附件 <=6000字，兼顾信息完整与防注意力稀释\n"
    "  2) 闭卷真值约束：所有数字、日期、页码与 #ID 只能引用拼装上下文或确定性工具返回，未查到必须坦诚拒绝\n"
    "  3) 跨天跨项目连续性：滚动摘要 + 30/60分钟窗口 + 项目上下文自动挂载 + FTS5 历史对话召回，确保隔天切换项目依然连贯\n"
    "  4) 安全隔离：外部邮件正文始终带 [UNTRUSTED_EXTERNAL_DATA] 标签包裹，不与系统规则混淆",
    STYLE_CONTEXT,
)

# ==================== 阶段三：zone x=2220..3360, cards x=2360..3220 (140px left/right internal gutters) ====================
add_zone("z3", 2220, 140, 1140, 2940, "阶段三｜智能意图路由与三条轻交互分支（checkpoints.db 断点持久化）")
add_box(
    "n_router", 2360, 220, 860, 350,
    "2. guardrail_router（上下文感知路由：LLM #1 + 硬编码后置护栏）",
    "• 【调用 LLM（qwen3.8-flash，Prompt: FAST_ROUTER_PROMPT）干什么】：\n"
    "  结合 4 层装配上下文，识别用户意图分类、把「他/这个/刚才那事」补全为完整表述、提炼检索关键词、识别目标待办 #ID\n"
    "• 【输出什么（IntentRoute）】：intent（11选1，含第11类兜底 clarify_or_unsupported）+ resolved_intent_text + search_queries[] + target_item_id + needs_deep_research\n"
    "• 【硬编码处理什么 → 输出什么】：\n"
    "  1) 若无待确认卡片却判 confirm/discard，降级为 conversational_chat 防误操作；\n"
    "  2) 仅「工作交办」类且置信度 < 0.55 时转 clarify_or_unsupported 礼貌澄清（查询/打卡不受影响）；chitchat 交给 3B 回复；\n"
    "  3) 除非原文显式含「查一下/上网查/联网搜」，否则强置 needs_deep_research=False（禁止代做外部调研）",
    STYLE_LLM,
)
add_box(
    "n_shortcut", 2360, 640, 860, 370,
    "3A. action_shortcut（纯硬编码执行，0 次 LLM 调用）",
    "• 【硬编码处理什么】：\n"
    "  1) confirm_pending / ideas_only_pending：调用 commit_pending_proposal() 签发令牌、写 SQLite 并上传 OneDrive；\n"
    "  2) discard_pending：作废 pending_proposals 最新草稿卡；undo：24h 内 undo_last_commit() 事务回滚；\n"
    "  3) mutate_existing_item：正则解析单个或多个 #ID（如「#1 做完了，#2 开始了」），分别调用 complete_item()（算跨度天数）或 start_item() 并重绘 5 份 .md 看板\n"
    "• 【输出什么】：直接返回微信结构化执行回执文本（如「✅ #1 已完成（跨度 3 天）」）+ 刷新后的云端看板",
    STYLE_HARDCODE,
)
add_box(
    "n_chat", 2360, 1080, 860, 340,
    "3B. conversational_responder（跨轮参谋对话：每条消息单次 LLM 回复，LLM #2）",
    "• 【调用 LLM（qwen3.8-flash，Prompt: CONVERSATIONAL_ADVISOR_PROMPT）干什么】：\n"
    "  每收到一条消息只调用 1 次模型，不自主循环；带上跨天摘要、项目卡、最近 30 轮对话、待确认卡与在途快照，接着前文做参谋分析或澄清\n"
    "• 【输出什么（ConversationalReply）】：1 条中文参谋回复 reply（不建待办）；若有待确认卡片，结尾提醒确认\n"
    "• 【轮数与终止】：轮数由董事长决定（发一条回一条，无上限）；下一条被路由器判为交办/查询/确认/打卡等意图即切换分支，不再发消息即结束",
    STYLE_LLM,
)
add_box(
    "n_qa", 2360, 1460, 860, 370,
    "3C. quick_qa_responder（Ch.14 闭卷档案问答：硬编码检索 + LLM #3）",
    "• 【硬编码处理什么】：调用 retrieve_long_horizon_evidence() + 扫描 30 轮近期对话，捞出匹配的 FTS5 文档页、历史对话、待办与待确认卡拼成证据块（ev_blocks）；若无任何证据直接拦截返回“未查到”\n"
    "• 【调用 LLM（qwen3.8-flash，Prompt: QA_GROUNDED_PROMPT）干什么】：严格闭卷阅读上述证据块作答，禁止凭记忆编造数字或人名\n"
    "• 【输出什么（GroundedAnswer）】：带准确来源与页码的回答（如《Spec.pdf》第 4 页）+ citations[] + found_in_sources 布尔标记",
    STYLE_LLM,
)

# ==================== 阶段四：zone x=3500..4520, cards x=3590..4410 ====================
add_zone("z4", 3500, 140, 1020, 2940, "阶段四｜work_triage 主干分拣、精算查证与异构反思闭环（核心大脑）")
add_box(
    "n_inv", 3590, 220, 820, 340,
    "4. react_investigator（确定性工具前置查证，纯硬编码执行）",
    "• 调用 1：ingest_inputs() 落盘附件原文并按页提取文本\n"
    "• 调用 2：retrieve_long_horizon_evidence() 跨时段召回历史文件与旧对话（hybrid_search）\n"
    "• 调用 3：check_workload_and_schedule() 统计未来 14 天每日已排期事项数、P0 数与是否拥挤（>=5 项为拥挤），给出推荐起始日（不估工时）\n"
    "• 调用 4：若存在 >=2 张 Excel 报价表，自动执行 analyze_excel_quote()（openpyxl 逐行 Diff 与含税精算）\n"
    "• 调用 5（默认关闭）：仅当 needs_deep_research=True（用户显式要求上网查）时，执行脱敏 search_public_tech_intel()",
    STYLE_HARDCODE,
)
add_box(
    "n_comp", 3590, 620, 820, 220,
    "5. context_compactor（Level 2 上下文工程压缩，纯硬编码）",
    "• 将原始文档命中列表、历史对话命中与本次附件浓缩为结构化 EvidenceCard[]（文档 <=1000字/条，对话 <=600字/条，附件 <=6000字，最多 12 张）\n"
    "• 将日程负载、Excel Diff、外部检索简报拼装为紧凑的 tool_outputs_text\n"
    "• 目的：避免超长原始 JSON 塞满主推理模型上下文导致指令遗忘或数字幻觉",
    STYLE_HARDCODE,
)
add_box(
    "n_prod", 3590, 900, 820, 390,
    "6. producer_drafter（董秘提案起草，LLM #4 + ReAct 工具调用）",
    "• LLM 调用：producer 档旗舰模型 qwen3.8-max（fallback: qwen-max），Prompt: PRODUCER_TRIAGE_PROMPT\n"
    "• 绑定沙箱工具（模型可自主调用）：check_workload_and_schedule、calc_business_date\n"
    "• 接收输入：当前日期 + 跨天摘要 + 相关项目卡 + 3层工作区上下文 + EvidenceCard[] + tool_outputs_text + 纠偏/整改要求\n"
    "• 输出 Pydantic 契约：TriageProposal(headline, executive_summary, actions[], overload_warning, citations[], referenced_numbers[])\n"
    "• 业务铁律：不代做外部市场调研，只拆解行动/会议/干系人/待查资料；estimated_hours 默认 0.0，专注规划日历起止周期",
    STYLE_LLM,
)
add_box(
    "n_crit", 3590, 1360, 820, 420,
    "7. heterogeneous_critic（双重审计门禁：硬编码规则核验 + 异构 LLM #5）",
    "• 第一重（硬编码确定性检查 deterministic_critic_check）：\n"
    "  - 数字保真检查：核验 proposal.referenced_numbers 是否真实存在于原文/证据/工具输出中\n"
    "  - 逻辑红线：若填了非零工时须有原话依据且不能把多天等待换算成几十小时；拦截把纯脑暴放进 P0 今日待办\n"
    "• 第二重（异构模型审计）：critic 档模型 deepseek-v4-pro（fallback: qwen3.8-max），Prompt: CRITIC_AUDIT_PROMPT\n"
    "• 输出契约：CriticVerdict(passed, numeric_fidelity_ok, schedule_reasonable, issues, fix_instructions)\n"
    "• 有界反思循环（Ch.4）：若 passed=False 且 loop_count < 2，回退 producer_drafter 带整改指示重做；达上限则带标注放行",
    STYLE_CRITIC,
)
add_box(
    "n_gate", 3590, 1850, 820, 330,
    "8. hitl_preview_gate（Ch.13 人在回路人工确认挂起点，硬编码）",
    "• 生成待确认卡片：save_pending_proposal() 写入 SQLite pending_proposals 表（状态 pending）\n"
    "• 渲染高密度微信决策卡：format_decision_card() 展示 #卡片号、动作列表、P0/P1/P2、日历周期与跨度天数、证据出处\n"
    "• 附带固定驾驶舱链接并挂起等待董事长回复：\n"
    "  - 回复「1 / 好的 / 确认」→ 放行落盘 ｜ 回复「2」→ 仅存想法 ｜ 回复「改：...」→ 携带纠偏重走工作流",
    STYLE_GUARD,
)

# ==================== 阶段五：zone x=4660..5520, cards x=4710..5470 ====================
add_zone("z5", 4660, 140, 860, 2940, "阶段五｜原子落盘、双云同步、Web 驾驶舱与每日主动闭环")
add_box(
    "n_exec", 4710, 220, 760, 470,
    "9. atomic_executor（Ch.18 令牌门禁 + 原子持久化，纯硬编码）",
    "• 门禁校验：mint_approval_token() + before_tool_callback() HMAC 校验，无确认令牌物理拒绝任何写入\n"
    "• SQLite 事务：apply_proposal_atomic() 原子写入 list_items、projects、记录 24h undo_snapshot_json，并将卡片标为 confirmed\n"
    "• 21Vianet OneDrive 同步（microsoftgraph.chinacloudapi.cn）：\n"
    "  - 按 YYYYMMDD_<项目>_<文件名> 上传分类目录（>=4MB 分片断点续传）并清理 ECS 本地临时文件\n"
    "  - 追加 00_项目沟通与纪要.md\n"
    "  - 调用 render_lists_markdown() 自动重绘 5 份 .md 看板\n"
    "    (00_个人规则库 / 01_今日待办 / 02_项目总览 / 03_想法池 / 04_等待他人)",
    STYLE_HARDCODE,
)
add_box(
    "n_db", 4710, 760, 760, 470,
    "10. 本地持久化与 21Vianet 私有云存储底座",
    "• data/checkpoints.db：LangGraph SqliteSaver 状态断点库（重启不丢上下文）\n"
    "• data/app.db（SQLite WAL + FTS5）：\n"
    "  - raw_sources + sources_fts（按页文本索引）\n"
    "  - conversation_turns + conversation_turns_fts + episode_summaries（全量对话与跨天滚动摘要）\n"
    "  - projects + list_items（planned_span_days / actual_span_days）\n"
    "  - memory_rules（episodic_case / procedural_rule / span_baseline）\n"
    "  - pending_proposals + model_calls + auth_tokens\n"
    "• Wissentek 世纪互联 OneDrive（Sites.Selected 锁定 chairman-vault 私有库）",
    STYLE_CONTEXT,
)
add_box(
    "n_web", 4710, 1300, 760, 420,
    "11. 同进程内嵌 Web 驾驶舱（Executive Work OS）",
    "• 挂载：FastAPI 127.0.0.1:8090 ← Nginx 443 HTTPS (assistant.fire-matrix.com)\n"
    "• 鉴权：固定访问链接 + 微信 6 位 OTP 验证后 180 天 HttpOnly Secure Cookie 长效免密\n"
    "• 实时进度心跳（run_turn_with_heartbeat）：处理超过 12 秒首次推送当前节点进度，此后每 25 秒汇报一次，防长任务静默假死\n"
    "• 四大视图（直连同一 app.db）：\n"
    "  1) Main Table（状态/优先级/起止日期/Span 跨度/一键转立项）\n"
    "  2) Gantt & Timeline（21 天滚动拖拽改期）\n"
    "  3) Schedule Load（7 天每日排期密度）\n"
    "  4) Analytics（平均完成跨度 Avg Span + 业务板块事项占比/完成进度）\n"
    "• 网页端任意修改实时写库并同步重绘 OneDrive 看板",
    STYLE_HARDCODE,
)
add_box(
    "n_digest", 4710, 1800, 760, 520,
    "12. 早晚简报与 18:00 主动进度盘点闭环（硬编码定时调度）",
    "• 早 08:30 简报（build_daily_digest_message）：推送今日在途事项、平均完成跨度、P0/P1/P2 优先待办、外部卡点与固定驾驶舱链接\n"
    "• 晚 18:00 主动盘点追问（解决“忘记打卡导致跨度失真”）：\n"
    "  - 自动筛出「进行中 / 今日到期 / 已超期」未完成事项生成【📝 今日进度盘点】清单\n"
    "  - 主动发微信请董事长一句话确认进度（如「#3 做完了，#5 开始了」）\n"
    "  - 自动写入 conversation_turns，确保后续自然语言回复无缝衔接\n"
    "• 闭环结果：complete_item() 自动计算 actual_span_days 并沉淀 span_baseline 至 memory_rules",
    STYLE_HARDCODE,
)

# ==================== 100% 零遮挡正交走线（严格走空白走廊） ====================
# 阶段一：1A/1B/1C 走阶段一右侧内部空白道 (x=880, 910) -> 1D，绝不穿过 1B/1C！
add_edge("e1", "n_wx_app", "n_att", "语音转写/附件", "#2b6cb0", exit_xy=(1.0, 0.5), entry_xy=(1.0, 0.2), points=[(910, 340), (910, 1164)])
add_edge("e2", "n_wx_kf", "n_att", "合并转发文本", "#2b6cb0", exit_xy=(1.0, 0.5), entry_xy=(1.0, 0.5), points=[(880, 620), (880, 1245)])
add_edge("e3", "n_mail", "n_att", "白名单命中邮件", "#2b6cb0", exit_xy=(0.5, 1.0), entry_xy=(0.5, 0.0))
add_edge("e4", "n_att", "n_fast_guard", "预处理完成", "#2b6cb0", exit_xy=(0.5, 1.0), entry_xy=(0.5, 0.0))

# 阶段一 -> 阶段二 & 阶段三（走阶段一/二之间走廊 x=1020 与顶部空白走廊 y=115）
add_edge("e5", "n_fast_guard", "ctx_render", "触发上下文装配", "#2b6cb0", exit_xy=(1.0, 0.65), entry_xy=(0.0, 0.3), points=[(1020, 1681), (1020, 1872)])
add_edge("e5_top", "n_fast_guard", "n_router", "进入路由主流程", "#2b6cb0", exit_xy=(1.0, 0.25), entry_xy=(0.0, 0.3), points=[(1020, 1545), (1020, 115), (2150, 115), (2150, 319)])

# 阶段二内部：Layer 1/2/3/4 走阶段二左右内部空白道 (x=1140, 1165, 2030) -> ctx_render
add_edge("e_ctx1", "ctx_l1", "ctx_render", "滚动摘要+30轮对话", "#2f855a", dashed=True, exit_xy=(0.0, 0.5), entry_xy=(0.0, 0.15), points=[(1135, 385), (1135, 1806)])
add_edge("e_ctx2", "ctx_l2", "ctx_render", "待确认卡片", "#2f855a", dashed=True, exit_xy=(1.0, 0.5), entry_xy=(1.0, 0.15), points=[(2035, 755), (2035, 1806)])
add_edge("e_ctx3", "ctx_l3", "ctx_render", "快照+项目卡", "#2f855a", dashed=True, exit_xy=(0.0, 0.5), entry_xy=(0.0, 0.45), points=[(1165, 1120), (1165, 1938)])
add_edge("e_ctx4", "ctx_l4", "ctx_render", "FTS5 检索证据", "#2f855a", dashed=True, exit_xy=(0.5, 1.0), entry_xy=(0.5, 0.0))

# 阶段二 -> 阶段三 & 阶段四（走阶段二/三之间走廊 x=2130..2190，以及底部专属走廊 y=3180）
add_edge("e_ctx_r", "ctx_render", "n_router", "喂给路由器", "#2f855a", dashed=True, exit_xy=(1.0, 0.2), entry_xy=(0.0, 0.65), points=[(2130, 1828), (2130, 434)])
add_edge("e_ctx_c", "ctx_render", "n_chat", "喂给参谋对话", "#2f855a", dashed=True, exit_xy=(1.0, 0.5), entry_xy=(0.0, 0.5), points=[(2160, 1960), (2160, 1230)])
add_edge("e_ctx_p", "ctx_render", "n_prod", "喂给提案起草（底部安全走廊）", "#2f855a", dashed=True, exit_xy=(0.5, 1.0), entry_xy=(0.0, 0.6), points=[(1590, 3180), (3445, 3180), (3445, 1134)])

# 阶段三内部：n_router -> 3A / 3B / 3C（分别走中线、右侧内部走廊 x=3300、左侧内部走廊 x=2280，绝不互相穿过！）
add_edge("e_r1", "n_router", "n_shortcut", "confirm / discard / undo / mutate", "#6b46c1", exit_xy=(0.5, 1.0), entry_xy=(0.5, 0.0))
add_edge("e_r2", "n_router", "n_chat", "conversational_chat", "#6b46c1", exit_xy=(1.0, 0.75), entry_xy=(1.0, 0.4), points=[(3300, 467), (3300, 1200)])
add_edge("e_r3", "n_router", "n_qa", "quick_query", "#6b46c1", exit_xy=(0.0, 0.8), entry_xy=(0.0, 0.35), points=[(2280, 484), (2280, 1586)])

# 阶段三 -> 阶段四（走阶段三/四之间走廊 x=3415，紫实线）
add_edge("e_r4", "n_router", "n_inv", "work_triage / revise_pending", "#6b46c1", width=3, exit_xy=(1.0, 0.35), entry_xy=(0.0, 0.35))

# 阶段四内部：查证 -> 压缩 -> 起草 -> 审计 <-> 反思 -> 确认门禁
add_edge("e_p1", "n_inv", "n_comp", "原始检索与工具输出", "#2b6cb0", exit_xy=(0.5, 1.0), entry_xy=(0.5, 0.0))
add_edge("e_p2", "n_comp", "n_prod", "EvidenceCard[] + 工具事实", "#2b6cb0", exit_xy=(0.5, 1.0), entry_xy=(0.5, 0.0))
add_edge("e_p3", "n_prod", "n_crit", "TriageProposal 草案", "#6b46c1", exit_xy=(0.5, 1.0), entry_xy=(0.5, 0.0))
add_edge("e_p4", "n_crit", "n_prod", "FAIL 且 loops < 2（带批注整改）", "#c53030", dashed=True, width=2.5, exit_xy=(1.0, 0.35), entry_xy=(1.0, 0.65), points=[(4470, 1507), (4470, 1153)])
add_edge("e_p5", "n_crit", "n_gate", "PASS（或达上限带标注放行）", "#2f855a", width=3, exit_xy=(0.5, 1.0), entry_xy=(0.5, 0.0))

# 阶段四 & 阶段三 -> 阶段五（橙实线：走阶段四/五走廊 x=4590 及顶部走廊 y=115）
add_edge("e_g1", "n_gate", "n_exec", "回复 1 / 2 确认放行", "#dd6b20", width=3, exit_xy=(1.0, 0.5), entry_xy=(0.0, 0.55), points=[(4590, 2015), (4590, 478)])
add_edge("e_sc_exec", "n_shortcut", "n_exec", "快捷确认 / 批量打卡落盘", "#dd6b20", width=2.5, exit_xy=(1.0, 0.35), entry_xy=(0.0, 0.2), points=[(3340, 766), (3340, 115), (4590, 115), (4590, 314)])

# 阶段五内部 & 最底部专属回流走廊 y=3360 -> 最左侧 x=35 -> 1A
add_edge("e_g2", "n_exec", "n_db", "原子写库 + 同步 21Vianet", "#2b6cb0", exit_xy=(0.5, 1.0), entry_xy=(0.5, 0.0))
add_edge("e_db_web", "n_db", "n_web", "SQLite 零延迟直连", "#2f855a", exit_xy=(0.5, 1.0), entry_xy=(0.5, 0.0))
add_edge("e_web_dig", "n_web", "n_digest", "读取待盘点事项", "#2f855a", exit_xy=(0.5, 1.0), entry_xy=(0.5, 0.0))
add_edge("e_dig_wx", "n_digest", "n_wx_app", "18:00 主动盘点推微信 → 触发下一轮闭环（底部回流走廊）", "#dd6b20", dashed=True, width=3, exit_xy=(0.5, 1.0), entry_xy=(0.0, 0.5), points=[(5090, 3360), (35, 3360), (35, 340)])

xml = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<mxfile host="app.diagrams.net" modified="2026-11-18T17:05:00.000Z" agent="Antigravity" version="24.7.17">\n'
    '  <diagram id="agent-workflow-a0" name="AI工作助理完整工作流全景图_超宽无遮挡版">\n'
    '    <mxGraphModel dx="2800" dy="1800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
    'fold="1" page="1" pageScale="1" pageWidth="5600" pageHeight="3600" math="0" shadow="0">\n'
    '      <root>\n'
    '        <mxCell id="0"/>\n'
    '        <mxCell id="1" parent="0"/>\n'
    '        ' + "\n        ".join(nodes + edges) + '\n'
    '      </root>\n'
    '    </mxGraphModel>\n'
    '  </diagram>\n'
    '</mxfile>\n'
)

OUT_PATH.write_text(xml, encoding="utf-8")
print("Wrote", OUT_PATH, "bytes=", len(xml.encode("utf-8")))
