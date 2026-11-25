"""Generate the strict OMG UML 2.5 Behavioral State Machine Diagram (.drawio) for wechat_AI_assistant.

Conforms strictly to OMG UML 2.5 State Machine Diagram notation:
- Initial Pseudostate: solid black circle (`shape=startState`) — no incoming edge, unguarded outgoing edge.
- Final State: bullseye double circle (`shape=endState`) — zero outgoing edges.
- Simple / Composite States: rounded rectangles with standard `entry /`, `do /`, `exit /` compartments.
  NO flowchart cylinders, NO I/O parallelograms, NO sharp-corner process boxes.
- Choice Pseudostate: small hollow diamond (`rhombus`) with mutually exclusive `[guard]` branches + explicit `[else]`.
- Transitions: solid orthogonal arrows with open arrowheads and `trigger [guard] / effect` syntax.
- Bounded loop proof: explicit `[未通过 且 重写次数 < 2] / 重写次数+1` and `[else：通过 或 重写次数 >= 2]`.
- Orthogonal Regions: dashed dividers separating concurrent background monitors (Stage 6) from the main turn flow.
- Plain business Chinese throughout (no raw code identifiers or programmer jargon).

Run:  uv run python scripts/gen_workflow_drawio.py
Then: "/Applications/draw.io.app/Contents/MacOS/draw.io" -x -f png -o docs/04-AI分拣工作流全景图_A0.png docs/04-AI分拣工作流全景图_A0.drawio
"""

from __future__ import annotations

import html
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "04-AI分拣工作流全景图_A0.drawio"
PAGE_W, PAGE_H = 4960, 2720

# --- Strict OMG UML 2.5 mxGraph styles ---
S_TITLE = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=28;fontStyle=1;fontColor=#0f172a;"
S_SUBTITLE = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=15;fontColor=#475569;"

S_INITIAL = "ellipse;html=1;shape=startState;fillColor=#0f172a;strokeColor=#0f172a;"
S_FINAL = "ellipse;html=1;shape=endState;fillColor=#0f172a;strokeColor=#0f172a;"
S_CHOICE = "rhombus;whiteSpace=wrap;html=1;fillColor=#fffbeb;strokeColor=#b45309;strokeWidth=2.5;"

# Composite state container (rounded outer rectangle with top header bar)
S_COMPOSITE_MAIN = (
    "swimlane;startSize=40;rounded=1;arcSize=3;fillColor=#ffffff;strokeColor=#334155;"
    "strokeWidth=2.5;fontSize=17;fontStyle=1;fontColor=#0f172a;align=left;spacingLeft=16;"
)
S_COMPOSITE_TURN = (
    "swimlane;startSize=38;rounded=1;arcSize=3;fillColor=#f8fafc;strokeColor=#2563eb;"
    "strokeWidth=2.2;fontSize=16;fontStyle=1;fontColor=#1e3a8a;align=left;spacingLeft=14;"
)
S_COMPOSITE_SUB = (
    "swimlane;startSize=34;rounded=1;arcSize=4;fillColor=#faf5ff;strokeColor=#7c3aed;"
    "strokeWidth=2;fontSize=15;fontStyle=1;fontColor=#5b21b6;align=left;spacingLeft=12;"
)
S_COMPOSITE_STAGE3 = (
    "swimlane;startSize=34;rounded=1;arcSize=5;fillColor=#fffbeb;strokeColor=#b45309;"
    "strokeWidth=2;fontSize=15;fontStyle=1;fontColor=#92400e;align=left;spacingLeft=12;"
)

# Orthogonal region dashed divider lines
S_ORTHO_H = "line;strokeWidth=2;dashed=1;dashPattern=8 6;strokeColor=#64748b;fillColor=none;html=1;"
S_ORTHO_V = "line;strokeWidth=2;dashed=1;dashPattern=8 6;strokeColor=#94a3b8;fillColor=none;html=1;direction=south;"
S_REGION_LBL = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=15;fontStyle=1;fontColor=#334155;"
S_STAGE_TAG = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=14;fontStyle=1;fontColor=#475569;"

# UML 2.5 Note (dog-eared corner note box — valid UML 2.5 Comment element)
S_UML_NOTE = (
    "shape=note;whiteSpace=wrap;html=1;backgroundOutline=1;size=16;"
    "fillColor=#fefce8;strokeColor=#ca8a04;strokeWidth=1.5;"
    "fontSize=13;align=left;verticalAlign=top;spacingTop=8;spacingLeft=12;spacingRight=14;fontColor=#422006;"
)

# Color palette for UML 2.5 simple state compartments (code vs AI vs commit vs idle)
PALETTES = {
    "idle": ("#f1f5f9", "#475569", "#0f172a"),       # Wait / Idle state
    "code": ("#eff6ff", "#1d4ed8", "#1e3a8a"),       # Deterministic code state
    "llm": ("#f5f3ff", "#6d28d9", "#4c1d95"),        # AI model reasoning state
    "commit": ("#fff7ed", "#c2410c", "#7c2d12"),     # Stage 5 controlled write state
    "bg": ("#ecfdf5", "#047857", "#064e3b"),         # Orthogonal background monitor state
}

C_MAIN = "#1e40af"
C_ROUTE = "#6d28d9"
C_COMMIT = "#c2410c"
C_LOOP = "#b91c1c"
C_RET = "#475569"
C_BG = "#047857"

cells: list[str] = []


def _esc(val: str) -> str:
    return html.escape(val, quote=True)


def add_raw(xml_snippet: str) -> None:
    cells.append(xml_snippet)


def add_text(cid: str, x: int, y: int, w: int, h: int, value: str, style: str) -> None:
    lines = "<br/>".join(html.escape(line) for line in value.splitlines())
    add_raw(
        f'<mxCell id="{cid}" value="{_esc(lines)}" style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def add_container(cid: str, x: int, y: int, w: int, h: int, title: str, style: str) -> None:
    add_raw(
        f'<mxCell id="{cid}" value="{_esc(title)}" style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def add_state(
    cid: str,
    x: int,
    y: int,
    w: int,
    h: int,
    name: str,
    compartments: list[str],
    kind: str = "code",
) -> None:
    """Render an OMG UML 2.5 rounded-rectangle state with header divider and entry/do/exit body."""
    fill, stroke, title_color = PALETTES[kind]
    title_html = f"<b>{html.escape(name)}</b>"
    body_html = "<br/>".join(html.escape(line) for line in compartments)
    # Standard UML 2.5 two-compartment state rendered cleanly via HTML divider inside rounded box
    inner = (
        f'<div style="text-align:center;font-size:15px;color:{title_color};padding:6px 10px 6px 10px;'
        f'border-bottom:1.5px solid {stroke};">{title_html}</div>'
        f'<div style="text-align:left;font-size:13px;color:#1e293b;padding:8px 12px 8px 12px;line-height:1.45;">'
        f'{body_html}</div>'
    )
    style = (
        f"rounded=1;arcSize=10;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
        "strokeWidth=2;verticalAlign=top;spacing=0;"
    )
    add_raw(
        f'<mxCell id="{cid}" value="{_esc(inner)}" style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def add_initial(cid: str, x: int, y: int, size: int = 30) -> None:
    add_raw(
        f'<mxCell id="{cid}" value="" style="{S_INITIAL}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{size}" height="{size}" as="geometry"/></mxCell>'
    )


def add_final(cid: str, x: int, y: int, size: int = 34) -> None:
    add_raw(
        f'<mxCell id="{cid}" value="" style="{S_FINAL}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{size}" height="{size}" as="geometry"/></mxCell>'
    )


def add_choice(cid: str, x: int, y: int, size: int = 44) -> None:
    add_raw(
        f'<mxCell id="{cid}" value="" style="{S_CHOICE}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{size}" height="{size}" as="geometry"/></mxCell>'
    )


def add_note(cid: str, x: int, y: int, w: int, h: int, title: str, lines: list[str]) -> None:
    body = f"<b>{html.escape(title)}</b><br/>" + "<br/>".join(html.escape(l) for l in lines)
    add_raw(
        f'<mxCell id="{cid}" value="{_esc(body)}" style="{S_UML_NOTE}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def add_line(cid: str, x: int, y: int, w: int, h: int, style: str) -> None:
    add_raw(
        f'<mxCell id="{cid}" value="" style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def add_transition(
    eid: str,
    src: str,
    dst: str,
    label: str,
    color: str,
    *,
    exit_xy: tuple[float, float],
    entry_xy: tuple[float, float],
    points: list[tuple[int, int]] | None = None,
    width: float = 2.2,
    label_pos: float = 0.0,
    label_offset_y: int = -14,
) -> None:
    style = (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;"
        "endArrow=open;endFill=0;endSize=10;"
        f"exitX={exit_xy[0]};exitY={exit_xy[1]};exitDx=0;exitDy=0;"
        f"entryX={entry_xy[0]};entryY={entry_xy[1]};entryDx=0;entryDy=0;"
        f"strokeColor={color};strokeWidth={width};"
        f"fontSize=13;fontStyle=1;fontColor={color};labelBackgroundColor=#ffffff;"
    )
    pts = ""
    if points:
        pts = '<Array as="points">' + "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in points) + "</Array>"
    geo_attr = 'relative="1" as="geometry"'
    offset_xml = ""
    if label:
        geo_attr = f'x="{label_pos}" y="{label_offset_y}" relative="1" as="geometry"'
        offset_xml = '<mxPoint as="offset"/>'
    add_raw(
        f'<mxCell id="{eid}" value="{_esc(label)}" style="{style}" edge="1" parent="1" source="{src}" target="{dst}">'
        f"<mxGeometry {geo_attr}>{pts}{offset_xml}</mxGeometry></mxCell>"
    )


# ==============================================================================
# 0. TITLE & STRICT UML 2.5 LEGEND BAR
# ==============================================================================
add_text(
    "title", 40, 20, 2200, 44,
    "董事长个人 AI 项目助理 — UML 2.5 行为状态机架构图（纯 PMO 纳管版）",
    S_TITLE,
)
add_text(
    "subtitle", 40, 66, 2600, 30,
    "严格遵循 OMG UML 2.5 状态机图标准：实心黑圆●=入口，双圆◉=本轮终止，圆角框=状态（entry/do/exit），空心菱形◇=动态分流，实线箭头=触发事件 [监护条件] / 动作，虚线分隔=并发正交区域",
    S_SUBTITLE,
)

# Compact UML 2.5 visual legend (top right)
add_initial("lg_init", 2920, 34, 24)
add_text("lg_init_t", 2952, 26, 120, 40, "初始伪状态 ●", "text;html=1;strokeColor=none;fillColor=none;fontSize=13;align=left;verticalAlign=middle;")
add_final("lg_fin", 3080, 32, 28)
add_text("lg_fin_t", 3116, 26, 130, 40, "终止状态 ◉", "text;html=1;strokeColor=none;fillColor=none;fontSize=13;align=left;verticalAlign=middle;")
add_choice("lg_ch", 3254, 30, 32)
add_text("lg_ch_t", 3294, 26, 140, 40, "选择伪状态 ◇", "text;html=1;strokeColor=none;fillColor=none;fontSize=13;align=left;verticalAlign=middle;")
add_state("lg_code", 3440, 14, 190, 74, "确定性代码状态", ["do / 0模型确定性执行"], "code")
add_state("lg_llm", 3648, 14, 190, 74, "大模型推理状态", ["do / 调用指定档位模型"], "llm")
add_state("lg_commit", 3856, 14, 190, 74, "受控写库状态", ["entry / 校验人类确认令牌"], "commit")
add_note("lg_note", 4064, 14, 856, 74, "迁移标签语法：触发事件 [监护条件] / 执行动作", [
    "全图唯一回环位于路径④审核处，由 [未通过 且 重写次数 < 2] 严格封顶；本系统为纯项目管理（PMO），绝不代干具体业务活。"
])

# ==============================================================================
# 1. TOP-LEVEL COMPOSITE STATE CONTAINER (7x24 Online System with 2 Orthogonal Regions)
# ==============================================================================
add_container(
    "sys_root", 40, 112, 4880, 2568,
    "董事长个人 AI 项目助理系统（7×24 在线 · 含两个并发正交区域）",
    S_COMPOSITE_MAIN,
)

# Region A label (Main message processing state machine)
add_text(
    "reg_a_lbl", 64, 160, 1400, 30,
    "正交区域 A｜单次消息处理主状态机（事件驱动：来一条消息走完一遍，随即回到「待机等待中」，不在后台空转）",
    S_REGION_LBL,
)

# Top-level Initial -> Waiting Idle State
add_initial("top_init", 68, 435, 30)
add_state(
    "s_idle", 124, 340, 256, 220,
    "待机等待中",
    [
        "do / 持续监听微信消息回调与定时汇总唤醒",
        "说明 / 上一轮的对话历史、待确认卡片与在途待办均已安全保存在本地数据库",
    ],
    "idle",
)
add_transition("t_top_init", "top_init", "s_idle", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))

# ==============================================================================
# 2. COMPOSITE STATE: SINGLE TURN LIFECYCLE (Stages 1 -> 5)
# ==============================================================================
add_container(
    "s_turn", 540, 200, 4340, 1940,
    "复合状态：单次处理周期（阶段一 接收预处理 → 阶段二 装配背景 → 阶段三 分诊把关 → 阶段四 五条处理路径 → 阶段五 确认落盘）",
    S_COMPOSITE_TURN,
)

# Trigger from Idle -> Single Turn, and Completion Transition from Single Turn -> Idle
add_transition(
    "t_idle_to_turn", "s_idle", "s_turn",
    "收到微信消息\n或 邮件汇总触发",
    C_MAIN,
    exit_xy=(1, 0.42), entry_xy=(0, 0.12),
    points=[(460, 432), (460, 432)],
    label_pos=0.0, label_offset_y=-24,
)
add_transition(
    "t_turn_to_idle", "s_turn", "s_idle",
    "本轮抵达◉ / 回到待机，等待你的下一条回复（如回 1 确认、0 作废或改：…）",
    C_RET,
    exit_xy=(0.14, 1), entry_xy=(0.5, 1),
    points=[(1148, 2178), (252, 2178)],
    label_pos=-0.45, label_offset_y=-16,
)

# --- Stage 1: Receive & Pre-process ---
add_text("lbl_s1", 570, 250, 440, 26, "【阶段一｜接收与预处理】", S_STAGE_TAG)
add_initial("turn_init", 575, 425, 28)
add_state(
    "s1_intake", 635, 290, 430, 355,
    "接收与预处理中",
    [
        "entry / 微信通道：验签、解密、单人白名单过滤；首条消息0.5秒内回「已收到」（发回执超时不丢消息）",
        "entry / 邮件通道：不回「已收到」，按名单过滤并加不可信隔离边界；解析/处理成功后再标已读防丢信",
        "do / 连续逐条转发停手 2 秒自动合并（发「好了」立即结束等待）",
        "do / 语音消息调用 qwen3-asr-flash 转文字（失败降级占位提示，不中断）",
        "do / 随附文件（PDF/Word/Excel/ZIP 等）前置按页提取入库并备份 OneDrive 收件箱（损坏或加密文件优雅占位）",
        "exit / 汇总为统一文本与已入库附件清单",
    ],
    "code",
)
add_transition("t_turn_init", "turn_init", "s1_intake", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.42))

# --- Stage 2: Assemble Context ---
add_text("lbl_s2", 1135, 250, 400, 26, "【阶段二｜装配上下文】", S_STAGE_TAG)
add_state(
    "s2_ctx", 1135, 290, 410, 355,
    "装配上下文中",
    [
        "do / 纯代码读取本地 SQLite 真值（0 次大模型调用，脏 JSON 自动容错）：",
        "  ① 跨天滚动摘要（只读历史）+ 近 30 轮对话（间隔超 30 分钟插入分割线防串话题）",
        "  ② 桌上的待确认卡片（标注距今分钟数与 60 分钟新鲜度窗口）",
        "  ③ 在途项目与未完待办快照（提到项目名时自动挂载项目卡）",
        "  ④ 历史档案与旧对话全文索引（仅路径③查档与路径④立卡时检索）",
        "exit / 拼出完整上下文背景（严格条数与字数截断，防撑爆模型窗口）",
    ],
    "code",
)
add_transition(
    "t_s1_s2", "s1_intake", "s2_ctx",
    "批次就绪", C_MAIN,
    exit_xy=(1, 0.5), entry_xy=(0, 0.5),
    label_offset_y=-14,
)

# --- Stage 3: Composite State (AI Secretary + Gatekeeper Safety Lock & Secret Commands) ---
add_text("lbl_s3", 1615, 250, 560, 26, "【阶段三｜意图分诊与老管家两道把关】", S_STAGE_TAG)
add_container(
    "s3_router_box", 1615, 290, 625, 760,
    "复合状态：意图分诊（AI 小秘书先理解 + 老管家两道死规矩把关）",
    S_COMPOSITE_STAGE3,
)

add_initial("s3_init", 1645, 352, 24)
add_choice("s3_pre_ch", 1715, 344, 40)
add_transition("t_s3_init", "s3_init", "s3_pre_ch", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))

add_state(
    "s3_ai", 1650, 445, 555, 165,
    "1. AI 小秘书初步判断意图",
    [
        "do / 调用 qwen3.8-flash（主备自动切换，最多重试 4 次）阅读上下文背景",
        "do / 听懂日常口语（「好的按这个办」「刚才那个审完了」）、补全「这个/刚才那事」指代并提炼查档关键词",
        "注 / 万一大模型断网故障，直接跳往下方「老板专属死暗号」保底通道",
    ],
    "llm",
)
add_transition(
    "t_s3_pre_ai", "s3_pre_ch", "s3_ai",
    "[else：需理解上下文]", C_MAIN,
    exit_xy=(0.5, 1), entry_xy=(0.15, 0),
    label_pos=-0.1, label_offset_y=0,
)
add_transition(
    "t_s3_pre_hi", "s3_pre_ch", "s4_record",
    "[纯问候(你好/在吗) 且 无历史无待确认卡] / 直接回复问候",
    C_RET,
    exit_xy=(1, 0.5), entry_xy=(0.75, 0),
    points=[(2265, 364), (2265, 278), (3875, 278)],
    label_pos=0.42, label_offset_y=-14,
)

add_state(
    "s3_guard", 1650, 660, 555, 360,
    "2. 铁面老管家两道把关（纯代码，0 次模型）",
    [
        "do / 【第一道·防闯祸安全锁（专拦小秘书瞎办事）】",
        "  • 桌上根本没有待确认卡，却判成要签字/存想法/作废 → 拦住改成「参谋聊天」，绝不碰库",
        "  • 小秘书自己把握不到五成半（没听清没听懂）→ 拦住不准瞎立项，改去「先问清楚」",
        "  • 纯 PMO 边界：系统已物理移除联网公网搜索与代算业务报价工具",
        "do / 【第二道·老板专属死暗号（含义唯一，一锤定音，最高优先级）】",
        "  • 整句只发「看板 / 负荷」→ 只看网页或日程，绝不改待办",
        "  • 整句只发「撤销 / 开始 3 / 完成 3」→ 必定改对应状态",
        "  • 桌上有卡时整句发「1 / 2 / 0 / 取消 / 改：…」→ 必定签字、存想法、作废或重排",
        "  （日常口语「好的」「做完了」含义随语境变化，不放死暗号表，仍交由小秘书结合上下文判断）",
    ],
    "code",
)
add_transition(
    "t_s3_ai_guard", "s3_ai", "s3_guard",
    "给出初步判断 或 网关故障", C_MAIN,
    exit_xy=(0.5, 1), entry_xy=(0.5, 0),
    label_offset_y=0,
)

# Link Stage 2 -> Stage 3 composite state
add_transition(
    "t_s2_s3", "s2_ctx", "s3_router_box",
    "背景就绪", C_MAIN,
    exit_xy=(1, 0.5), entry_xy=(0, 0.23),
    label_offset_y=-14,
)

# --- Stage 3 Exit Choice Pseudostate ◇ (Routing to Stage 4's 5 Paths + Read-only Direct Reply) ---
add_choice("ch_route", 2310, 818, 48)
add_transition(
    "t_s3_choice", "s3_router_box", "ch_route",
    "最终裁决", C_ROUTE,
    exit_xy=(1, 0.72), entry_xy=(0, 0.5),
    label_offset_y=-14,
)

# ==============================================================================
# 3. STAGE 4: FIVE PROCESSING PATHS + STAGE 5 CONTROLLED COMMIT
# ==============================================================================
add_text("lbl_s4", 2560, 252, 760, 26, "【阶段四｜五条受控处理路径（仅路径①通往阶段五改库）】", S_STAGE_TAG)

# Path ①: Action Shortcut -> Stage 5 Commit
add_state(
    "s4_p1", 2580, 295, 520, 155,
    "路径①：执行确认、打卡与撤销指令",
    [
        "do / 解析确认卡编号、作废指令、单条或一句话批量开始/完成打卡、或 24 小时撤销指令",
        "注 / 凡是「看板 / 负荷」只读查询，直接输出网页链接或近 3 日日程，不改待办",
    ],
    "code",
)
# Path ②: Conversational Advisor
add_state(
    "s4_p2", 2580, 500, 520, 150,
    "路径②：参谋单轮对谈",
    [
        "do / 调用 qwen3.8-max 结合上下文提供参谋意见（每条消息只回一次，绝不后台自聊死循环）",
        "注 / 绝不新建或修改任何正式待办；聊几轮完全由你决定",
    ],
    "llm",
)
# Path ③: Grounded QA
add_state(
    "s4_p3", 2580, 700, 520, 165,
    "路径③：闭卷查档与进度问答",
    [
        "do / 检索本地历史文档（含本轮刚发并前置入库的新附件）、旧对话与在途项目待办",
        "do / 查无依据直接回复「未查到」（0 次模型）；有依据则调 qwen3.8-max 严格带页码出处作答",
    ],
    "llm",
)
# Path ⑤: Clarify / Unsupported
add_state(
    "s4_p5", 2580, 915, 520, 145,
    "路径⑤：追问澄清与能力边界说明",
    [
        "do / 说明本助理只做项目管理（不支持代发外部微信/邮件或订票），或礼貌追问项目名/具体事项",
        "注 / 0 次数据库写入，绝不强行乱建待办",
    ],
    "code",
)

# Shared Turn-End State for Paths ②/③/⑤ & Read-only Replies
add_state(
    "s4_record", 3560, 580, 420, 270,
    "回复微信并记录本次对话",
    [
        "entry / 扫描输出文本，严防任何密钥或令牌泄漏",
        "do / 分片推送回复到你的个人微信（语音消息附带转写原文回显）",
        "do / 将你的原话与助理回复成对写入本地对话记录（供下次阶段二衔接上下文）",
        "exit / 若累计满 8 轮新对话，同步写入保底摘要并唤醒正交区 B 升级语义摘要",
    ],
    "code",
)
add_final("turn_fin_main", 4080, 698, 34)
add_transition("t_rec_fin", "s4_record", "turn_fin_main", "本轮结束", C_RET, exit_xy=(1, 0.5), entry_xy=(0, 0.5), label_offset_y=-14)

# --- Stage 5: Controlled Formal Data Commit ---
add_text("lbl_s5", 4220, 250, 620, 26, "【阶段五｜唯一能修改正式待办与看板的受控门禁】", S_STAGE_TAG)
add_state(
    "s5_commit", 4220, 295, 610, 340,
    "修改正式待办、项目与云端看板",
    [
        "entry / 对 AI 提案卡：现场签发并校验一次性 HMAC 人类确认令牌（无有效令牌物理拒写）",
        "do / 本地 SQLite 单事务原子落盘：写入项目与待办，同时留存 24 小时完整撤销快照",
        "do / 将临时附件正式归档至世纪互联 OneDrive 对应项目目录，并重绘 5 份 .md 清单看板",
        "do / 云端容错：若 OneDrive 瞬时网络波动，绝不回滚本地已落盘待办，如实告知稍后补刷",
        "exit / 脱敏推送执行结果到微信，并写入对话记录（Web 驾驶舱实时共享同一数据库）",
    ],
    "commit",
)
add_final("turn_fin_s5", 4508, 700, 34)
add_transition("t_s5_fin", "s5_commit", "turn_fin_s5", "落盘并回复完毕", C_COMMIT, exit_xy=(0.5, 1), entry_xy=(0.5, 0), label_offset_y=0)

# Routing transitions from ◇ ch_route to Paths ① / ② / ③ / ⑤ / ④
add_transition(
    "t_r_p1", "ch_route", "s4_p1",
    "[确认/作废/打卡/撤销/看板/负荷]", C_ROUTE,
    exit_xy=(0.5, 0), entry_xy=(0, 0.5),
    points=[(2334, 372)],
    label_pos=0.18, label_offset_y=-14,
)
add_transition(
    "t_r_p2", "ch_route", "s4_p2",
    "[探讨思路 或 无卡误触确认]", C_ROUTE,
    exit_xy=(0.75, 0.25), entry_xy=(0, 0.5),
    points=[(2410, 830), (2410, 575)],
    label_pos=0.32, label_offset_y=-14,
)
add_transition(
    "t_r_p3", "ch_route", "s4_p3",
    "[查文档 或 查进度]", C_ROUTE,
    exit_xy=(1, 0.5), entry_xy=(0, 0.5),
    points=[(2470, 842), (2470, 782)],
    label_pos=0.25, label_offset_y=-14,
)
add_transition(
    "t_r_p5", "ch_route", "s4_p5",
    "[把握不足五成半\n或 超出职责]", C_ROUTE,
    exit_xy=(0.75, 0.75), entry_xy=(0, 0.5),
    points=[(2430, 854), (2430, 987)],
    label_pos=0.55, label_offset_y=-24,
)

# Path ① -> Stage 5 (or Read-only -> Record)
add_choice("ch_p1_write", 3220, 350, 44)
add_transition("t_p1_ch", "s4_p1", "ch_p1_write", "", C_COMMIT, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
add_transition(
    "t_p1_s5", "ch_p1_write", "s5_commit",
    "[确认/作废/打卡/撤销（需改数据）]", C_COMMIT,
    exit_xy=(1, 0.5), entry_xy=(0, 0.23),
    label_offset_y=-14,
)
add_transition(
    "t_p1_ro", "ch_p1_write", "s4_record",
    "[else：看板 / 负荷（只读不改库）]", C_RET,
    exit_xy=(0.5, 1), entry_xy=(0.25, 0),
    points=[(3242, 480), (3665, 480)],
    label_pos=-0.05, label_offset_y=-14,
)

# Paths ② / ③ / ⑤ -> Shared Reply & Record state
add_transition("t_p2_rec", "s4_p2", "s4_record", "", C_RET, exit_xy=(1, 0.5), entry_xy=(0, 0.25), points=[(3340, 575), (3340, 648)])
add_transition("t_p3_rec", "s4_p3", "s4_record", "", C_RET, exit_xy=(1, 0.5), entry_xy=(0, 0.55), points=[(3340, 782), (3340, 728)])
add_transition("t_p5_rec", "s4_p5", "s4_record", "", C_RET, exit_xy=(1, 0.5), entry_xy=(0, 0.85), points=[(3340, 987), (3340, 810)])

# ==============================================================================
# 4. COMPOSITE STATE: PATH ④ PURE PMO CARD DRAFTING & BOUNDED CRITIC LOOP
# ==============================================================================
add_container(
    "s4_p4_box", 1615, 1170, 3215, 920,
    "路径④ 复合状态：项目管理立卡与派单排期（纯 PMO 纳管——把具体工作拆成卡片安排人做，绝不代干具体业务活）",
    S_COMPOSITE_SUB,
)
add_transition(
    "t_r_p4", "ch_route", "s4_p4_box",
    "[else：具体工作事项、派人、转发、附件或修改卡片]", C_ROUTE,
    exit_xy=(0.5, 1), entry_xy=(0.223, 0),
    points=[(2334, 1170)],
    width=3.0, label_pos=0.45, label_offset_y=-14,
)

add_initial("p4_init", 1650, 1425, 28)

add_state(
    "p4_s1", 1715, 1295, 420, 290,
    "1. 前置查证与排期密度体检",
    [
        "do / 检索历史档案库与跨时段旧对话，找齐同项目上下文",
        "do / 查询未来 14 天每日已排事项数量与拥挤日期（单日 ≥5 项标为拥挤）",
        "注 / 随附原件已在阶段一完成提取入库与原件备份，此处不再重复",
    ],
    "code",
)
add_state(
    "p4_s2", 2205, 1320, 350, 220,
    "2. 证据压缩整理",
    [
        "do / 将检索到的长文档、旧对话与新附件截断浓缩为最多 12 张精简证据卡",
        "do / 附带未来 7 天排期密度摘要，防止长文本淹没主模型注意力",
    ],
    "code",
)
add_state(
    "p4_s3", 2635, 1270, 500, 320,
    "3. PMO 立卡与排期起草",
    [
        "do / 调用 qwen3.8-max 拆解为标准项目管理动作：",
        "  • 归属项目与六大业务板块",
        "  • 区分本人亲办（责任人=本人）vs 委派同事/外部跟进（责任人=张工/王总等，入委派跟进清单）",
        "  • 调用排期密度与工作日推算工具确定起止验收日（自动避开拥挤日）",
        "do / 铁律：默认不猜个人净工时（0.0h），绝不代写调研报告或代算业务内容",
        "注 / 内部工具调用严格封顶 ≤5 轮，防工具循环",
    ],
    "llm",
)
add_state(
    "p4_s4", 3220, 1285, 470, 290,
    "4. 双重独立把关审核",
    [
        "do / 第一重（硬编码）：核对卡片里每个关键数字是否 100% 出自原文或工具事实；核对外部等待项不误填工时",
        "do / 第二重（异构模型 deepseek-v4-pro）：打破同源盲区，独立挑出漏项、想法混入紧急待办或拥挤排期未提醒等问题",
        "exit / 输出审核结论（是否通过 + 具体整改意见）",
    ],
    "llm",
)

add_choice("p4_ch_ok", 3775, 1408, 48)

add_state(
    "p4_s5", 4120, 1280, 540, 300,
    "5. 暂存草稿卡并推送微信确认",
    [
        "entry / 将提案存入「待确认暂存表」（绝不改动正式待办与看板）",
        "entry / 卡片醒目打印：项目名、事项、责任人（本人/被委派人）、起止周期",
        "entry / 若满 2 轮重写仍有未消解审核疑点，显式印出「⚠️ 审计待人工复核点」提醒董事长裁决",
        "do / 扫描防密钥泄漏 → 推送确认卡到微信 → 记录本轮对话",
    ],
    "commit",
)
add_final("p4_fin", 4735, 1413, 34)

# Path ④ internal transitions (including strict bounded loop!)
add_transition("t_p4_init", "p4_init", "p4_s1", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
add_transition("t_p4_12", "p4_s1", "p4_s2", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
add_transition("t_p4_23", "p4_s2", "p4_s3", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
add_transition("t_p4_34", "p4_s3", "p4_s4", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
add_transition("t_p4_4c", "p4_s4", "p4_ch_ok", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))

# Bounded loop: [未通过 且 重写次数 < 2] / 重写次数+1
add_transition(
    "t_p4_retry", "p4_ch_ok", "p4_s3",
    "[审核未通过 且 重写次数 < 2] / 携带整改意见，重写次数+1（全图唯一有界回环）",
    C_LOOP,
    exit_xy=(0.5, 1), entry_xy=(0.5, 1),
    points=[(3799, 1730), (2885, 1730)],
    width=2.6, label_pos=0.0, label_offset_y=-16,
)
# Escape / Pass: [else：审核通过 或 重写次数 >= 2]
add_transition(
    "t_p4_pass", "p4_ch_ok", "p4_s5",
    "[else：审核通过 或 重写次数 >= 2]",
    C_MAIN,
    exit_xy=(1, 0.5), entry_xy=(0, 0.5),
    label_pos=0.0, label_offset_y=-16,
)
add_transition("t_p4_fin", "p4_s5", "p4_fin", "", C_COMMIT, exit_xy=(1, 0.5), entry_xy=(0, 0.5))

# UML Comment note explaining cross-turn human confirmation (no illegal arrow out of Final State!)
add_note(
    "p4_hitl_note", 3990, 1810, 780, 225,
    "人机签字闭环说明（为什么这里先抵达终止状态 ◉？）",
    [
        "• 发出待确认卡后，本次处理立即结束（回到左侧「待机等待中」），AI 绝不擅自改你的正式待办。",
        "• 当你下一条微信回复「1 / 好的」→ 触发全新一次处理 → 经阶段三进入路径① → 阶段五验签落盘。",
        "• 当你回复「0 / 取消」→ 经路径①作废草稿卡；回复「改：交给李工，下周五截止」→ 携带原卡重走路径④。",
        "• 任何未预期系统异常均会被顶层捕获：先把你的原话记入对话库并主动告知，绝不静默崩溃或乱改数据。",
    ],
)

# ==============================================================================
# 5. ORTHOGONAL REGION B (Stage 6: Concurrent Background Monitors & Schedulers)
# ==============================================================================
add_line("ortho_div_ab", 42, 2215, 4876, 10, S_ORTHO_H)
add_text(
    "reg_b_lbl", 64, 2236, 1600, 30,
    "正交区域 B｜阶段六并发伴随机制（与主消息处理并行独立运行，通过虚线正交隔离，各自独立启停、互不阻塞）",
    S_REGION_LBL,
)

# Sub-region B1: Progress Heartbeat Monitor
add_text("lbl_b1", 80, 2280, 500, 24, "并发子区 B1｜长耗时进度心跳监控（防假死焦虑）", S_STAGE_TAG)
add_initial("b1_init", 84, 2425, 24)
add_state(
    "b1_watch", 140, 2345, 410, 185,
    "监控单次处理耗时",
    [
        "do / 随单次处理启动异步计时器",
        "注 / 12 秒内处理完直接安静退出，零打扰",
    ],
    "bg",
)
add_state(
    "b1_beat", 860, 2345, 470, 185,
    "定期播报当前步骤",
    [
        "do / 每次超时向微信推送「已用时 Xs：正在执行【当前步骤】」",
        "exit / 主流程结束或异常退出时，finally 强制销毁心跳协程",
    ],
    "bg",
)
add_transition("t_b1_init", "b1_init", "b1_watch", "", C_BG, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
add_transition(
    "t_b1_start", "b1_watch", "b1_beat",
    "after(12秒) [仍在处理中] / 首次播报", C_BG,
    exit_xy=(1, 0.35), entry_xy=(0, 0.35),
    label_offset_y=-14,
)
add_transition(
    "t_b1_loop", "b1_beat", "b1_beat",
    "after(25秒) [仍未结束] / 继续播报", C_BG,
    exit_xy=(0.75, 1), entry_xy=(0.25, 1),
    points=[(1212, 2595), (978, 2595)],
    label_offset_y=-14,
)
add_transition(
    "t_b1_stop", "b1_beat", "b1_watch",
    "单次处理结束 / 销毁计时器", C_RET,
    exit_xy=(0, 0.72), entry_xy=(1, 0.72),
    label_offset_y=16,
)

# Vertical dashed divider B1 | B2
add_line("ortho_div_b12", 1420, 2280, 10, 360, S_ORTHO_V)

# Sub-region B2: Daily Digest & Workday Mail Summary Scheduler
add_text("lbl_b2", 1470, 2280, 820, 24, "并发子区 B2｜工作日定时早晚简报与邮件汇总", S_STAGE_TAG)
add_initial("b2_init", 1474, 2425, 24)
add_state(
    "b2_wait", 1530, 2340, 440, 200,
    "按时钟轮询等待唤醒",
    [
        "do / 每 30 秒核对本地时钟（仅周一至周五运行）",
        "do / 推送成功后再记同日防重标，失败记日志不静默丢失",
    ],
    "bg",
)
add_state(
    "b2_digest", 2320, 2315, 580, 130,
    "推送早间简报 / 18:00 晚间盘点",
    [
        "do / 汇总今日在途、外部委派卡点与进度盘点列表，推送微信并写入对话库",
        "exit / 方便你直接回复「#3 做完了，#5 开始了」批量打卡",
    ],
    "bg",
)
add_state(
    "b2_mail", 2320, 2475, 580, 145,
    "拉取白名单邮件汇总（只读）",
    [
        "do / 08:30 补夜间与周末积压；09:00–21:00 每小时一次（夜间与周末不拉）",
        "do / 收件合成一张待确认卡触发正交区 A；发出的信同条列出；成功后再标已读",
    ],
    "bg",
)
add_transition("t_b2_init", "b2_init", "b2_wait", "", C_BG, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
add_transition(
    "t_b2_dig", "b2_wait", "b2_digest",
    "at(工作日 08:30 / 18:00)", C_BG,
    exit_xy=(1, 0.25), entry_xy=(0, 0.5),
    points=[(2120, 2390), (2120, 2380)],
    label_offset_y=-14,
)
add_transition(
    "t_b2_mail", "b2_wait", "b2_mail",
    "at(工作日 08:30 及 09:00–21:00 整点) [有新邮件]", C_BG,
    exit_xy=(1, 0.78), entry_xy=(0, 0.5),
    points=[(2120, 2496), (2120, 2547)],
    label_offset_y=-14,
)
add_transition(
    "t_b2_dig_back", "b2_digest", "b2_wait",
    "", C_RET,
    exit_xy=(0.5, 0), entry_xy=(0.5, 0),
    points=[(2610, 2292), (1750, 2292)],
)
add_transition(
    "t_b2_mail_back", "b2_mail", "b2_wait",
    "", C_RET,
    exit_xy=(0.5, 1), entry_xy=(0.5, 1),
    points=[(2610, 2642), (1750, 2642)],
)

# Vertical dashed divider B2 | B3
add_line("ortho_div_b23", 2970, 2280, 10, 360, S_ORTHO_V)

# Sub-region B3: Rolling Semantic Summary Background Upgrader
add_text("lbl_b3", 3020, 2280, 900, 24, "并发子区 B3｜跨天滚动会话摘要后台升级（不阻塞主回复）", S_STAGE_TAG)
add_initial("b3_init", 3024, 2425, 24)
add_state(
    "b3_idle", 3080, 2345, 510, 185,
    "空闲等待对话满 8 轮",
    [
        "do / 监听新对话入库计数，未满 8 轮不耗模型",
        "note / 满 8 轮瞬间由主流程先同步写关键词保底摘要并推进游标（防并发重入）",
    ],
    "bg",
)
add_state(
    "b3_run", 3980, 2335, 840, 205,
    "后台线程语义摘要升级",
    [
        "do / 调用 qwen3.8-flash 将上一版摘要与新增 8 轮对话合并为 ≤600 字中文要点",
        "do / 核对乐观锁（无更新版本抢先写入时）覆盖更新至数据库",
        "do / 若模型超时或失败：安全保留关键词保底摘要，绝不影响前台回复速度",
    ],
    "llm",
)
add_transition("t_b3_init", "b3_init", "b3_idle", "", C_BG, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
add_transition(
    "t_b3_go", "b3_idle", "b3_run",
    "新增对话满 8 轮 / 启守护线程", C_BG,
    exit_xy=(1, 0.35), entry_xy=(0, 0.35),
    label_offset_y=-14,
)
add_transition(
    "t_b3_done", "b3_run", "b3_idle",
    "升级完成 或 异常保留保底摘要", C_RET,
    exit_xy=(0, 0.72), entry_xy=(1, 0.72),
    label_offset_y=16,
)

# ==============================================================================
# 6. SERIALIZE DRAW.IO XML
# ==============================================================================
xml = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<mxfile host="app.diagrams.net" agent="Antigravity-UML25" version="24.7.17">\n'
    '  <diagram id="uml25-state-machine" name="UML 2.5 状态机架构图">\n'
    f'    <mxGraphModel dx="2400" dy="1600" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
    f'fold="1" page="1" pageScale="1" pageWidth="{PAGE_W}" pageHeight="{PAGE_H}" math="0" shadow="0">\n'
    "      <root>\n"
    '        <mxCell id="0"/>\n'
    '        <mxCell id="1" parent="0"/>\n'
    "        " + "\n        ".join(cells) + "\n"
    "      </root>\n"
    "    </mxGraphModel>\n"
    "  </diagram>\n"
    "</mxfile>\n"
)
OUT_PATH.write_text(xml, encoding="utf-8")
print("Wrote", OUT_PATH, "bytes=", len(xml.encode("utf-8")))
