"""Generate the strict OMG UML 2.5 Behavioral State Machine Diagram (.drawio) for wechat_AI_assistant v3.0.

Architecture: v3.0 Single-Brain Flagship Agent ("Model-First" Plan A)
- 3 clean core LangGraph nodes: context_intake -> flagship_brain (bounded <=2 objective guard loop) -> action_executor -> END
- 0 fast-router LLM calls, 0 second critic LLM calls
- 4 Minimal Deterministic Safety Chassis Pillars + 3 Objective Guardrails + Calendar Anchor Table + 0-LLM Emergency Buttons
- Strictly conforms to OMG UML 2.5 Behavioral State Machine Diagram notation:
  - Initial Pseudostate: solid black circle (`shape=startState`) — no incoming edge, unguarded outgoing edge.
  - Final State: bullseye double circle (`shape=endState`) — zero outgoing edges.
  - Simple / Composite States: rounded rectangles with `entry /`, `do /`, `exit /` compartments.
  - Choice Pseudostate: small hollow diamond (`rhombus`) with mutually exclusive `[guard]` branches + explicit `[else]`.
  - Transitions: solid orthogonal arrows with open arrowheads and `trigger [guard] / effect` syntax.
  - Bounded loop proof: `[触犯客观硬底线 且 自纠次数 < 2] / 自纠次数+1` and `[else：通过 或 自纠次数 >= 2]`.
  - Orthogonal Regions: dashed dividers separating concurrent background monitors from the main turn flow.
  - Plain business Chinese throughout (no raw code identifiers or programmer jargon).

Run:  uv run python scripts/gen_workflow_drawio.py
Then: "/Applications/draw.io.app/Contents/MacOS/draw.io" -x -f png -o docs/04-AI分拣工作流全景图_A0.png docs/04-AI分拣工作流全景图_A0.drawio
"""

from __future__ import annotations

import html
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "04-AI分拣工作流全景图_A0.drawio"
PAGE_W, PAGE_H = 4480, 2240

# --- Strict OMG UML 2.5 mxGraph styles ---
S_TITLE = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=28;fontStyle=1;fontColor=#0f172a;"
S_SUBTITLE = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=15;fontColor=#475569;"

S_INITIAL = "ellipse;html=1;shape=startState;fillColor=#0f172a;strokeColor=#0f172a;"
S_FINAL = "ellipse;html=1;shape=endState;fillColor=#0f172a;strokeColor=#0f172a;"
S_CHOICE = "rhombus;whiteSpace=wrap;html=1;fillColor=#fffbeb;strokeColor=#b45309;strokeWidth=2.5;"

S_COMPOSITE_MAIN = (
    "swimlane;startSize=40;rounded=1;arcSize=3;fillColor=#ffffff;strokeColor=#334155;"
    "strokeWidth=2.5;fontSize=17;fontStyle=1;fontColor=#0f172a;align=left;spacingLeft=16;"
)
S_COMPOSITE_TURN = (
    "swimlane;startSize=38;rounded=1;arcSize=3;fillColor=#f8fafc;strokeColor=#2563eb;"
    "strokeWidth=2.2;fontSize=16;fontStyle=1;fontColor=#1e3a8a;align=left;spacingLeft=14;"
)
S_COMPOSITE_BRAIN = (
    "swimlane;startSize=34;rounded=1;arcSize=4;fillColor=#faf5ff;strokeColor=#7c3aed;"
    "strokeWidth=2.2;fontSize=15;fontStyle=1;fontColor=#5b21b6;align=left;spacingLeft=12;"
)
S_COMPOSITE_EXEC = (
    "swimlane;startSize=34;rounded=1;arcSize=4;fillColor=#fff7ed;strokeColor=#c2410c;"
    "strokeWidth=2.2;fontSize=15;fontStyle=1;fontColor=#9a3412;align=left;spacingLeft=12;"
)

S_ORTHO_H = "line;strokeWidth=2;dashed=1;dashPattern=8 6;strokeColor=#64748b;fillColor=none;html=1;"
S_ORTHO_V = "line;strokeWidth=2;dashed=1;dashPattern=8 6;strokeColor=#94a3b8;fillColor=none;html=1;direction=south;"
S_REGION_LBL = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=15;fontStyle=1;fontColor=#334155;"
S_STAGE_TAG = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=14;fontStyle=1;fontColor=#475569;"

S_UML_NOTE = (
    "shape=note;whiteSpace=wrap;html=1;backgroundOutline=1;size=16;"
    "fillColor=#fefce8;strokeColor=#ca8a04;strokeWidth=1.5;"
    "fontSize=13;align=left;verticalAlign=top;spacingTop=8;spacingLeft=12;spacingRight=14;fontColor=#422006;"
)

PALETTES = {
    "idle": ("#f1f5f9", "#475569", "#0f172a"),
    "code": ("#eff6ff", "#1d4ed8", "#1e3a8a"),
    "llm": ("#f5f3ff", "#6d28d9", "#4c1d95"),
    "commit": ("#fff7ed", "#c2410c", "#7c2d12"),
    "bg": ("#ecfdf5", "#047857", "#064e3b"),
}

C_MAIN = "#1e40af"
C_BRAIN = "#6d28d9"
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
    fill, stroke, title_color = PALETTES[kind]
    title_html = f"<b>{html.escape(name)}</b>"
    body_html = "<br/>".join(html.escape(line) for line in compartments)
    inner = (
        f'<div style="text-align:center;font-size:15px;color:{title_color};padding:6px 10px 6px 10px;'
        f'border-bottom:1.5px solid {stroke};">{title_html}</div>'
        f'<div style="text-align:left;font-size:13px;color:#1e293b;padding:8px 12px 8px 12px;line-height:1.48;">'
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
    "董事长个人 AI 项目助理 v3.0 — OMG UML 2.5 行为状态机架构图（单脑旗舰 · Model-First 方案 A）",
    S_TITLE,
)
add_text(
    "subtitle", 40, 66, 2500, 30,
    "严格遵循 OMG UML 2.5 状态机标准：实心黑圆●=入口，双圆◉=本轮终止，圆角框=状态（entry/do/exit），空心菱形◇=动态分流，实线箭头=触发事件 [监护条件] / 动作，虚线分隔=并发正交区",
    S_SUBTITLE,
)

add_initial("lg_init", 2600, 34, 24)
add_text("lg_init_t", 2632, 26, 115, 40, "初始伪状态 ●", "text;html=1;strokeColor=none;fillColor=none;fontSize=13;align=left;verticalAlign=middle;")
add_final("lg_fin", 2755, 32, 28)
add_text("lg_fin_t", 2790, 26, 115, 40, "终止状态 ◉", "text;html=1;strokeColor=none;fillColor=none;fontSize=13;align=left;verticalAlign=middle;")
add_choice("lg_ch", 2912, 30, 32)
add_text("lg_ch_t", 2952, 26, 125, 40, "选择伪状态 ◇", "text;html=1;strokeColor=none;fillColor=none;fontSize=13;align=left;verticalAlign=middle;")
add_state("lg_code", 3085, 14, 185, 74, "确定性底盘状态", ["do / 0模型事实与安全"], "code")
add_state("lg_llm", 3285, 14, 195, 74, "唯一旗舰大脑", ["do / qwen3.8-max 推理"], "llm")
add_state("lg_commit", 3495, 14, 185, 74, "受控执行与落盘", ["entry / 校验人类令牌"], "commit")
add_note("lg_note", 3695, 14, 745, 74, "v3.0 方案 A 核心原则：大脑全给旗舰模型，底盘只留 4 块硬铁板", [
    "0 次小模型路由、0 次二审打架大模型；常规 5~8 秒直出；唯一有界回环受 [自纠次数 < 2] 严格封顶。"
])

# ==============================================================================
# 1. TOP-LEVEL COMPOSITE STATE CONTAINER (7x24 Online System with 2 Orthogonal Regions)
# ==============================================================================
add_container(
    "sys_root", 40, 112, 4400, 2090,
    "董事长个人 AI 项目助理系统 v3.0（7×24 在线 · 含两个并发正交区域）",
    S_COMPOSITE_MAIN,
)

add_text(
    "reg_a_lbl", 64, 160, 1800, 30,
    "正交区域 A｜单次消息处理主状态机（极简 3 节点核心：上下文与事实供给 → 旗舰单脑综合决策 → 确定性执行与精简回复）",
    S_REGION_LBL,
)

# Idle Wait State
add_initial("top_init", 68, 525, 30)
add_state(
    "s_idle", 124, 415, 250, 250,
    "待机等待中",
    [
        "do / 监听个人微信回调与整点邮件汇总触发",
        "说明 / 上轮对话、待确认卡、在途任务与来源标签均安全保存在本地数据库",
        "注 / 本轮抵达◉即回到此处，绝不后台空转",
    ],
    "idle",
)
add_transition("t_top_init", "top_init", "s_idle", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))

# ==============================================================================
# 2. COMPOSITE STATE: SINGLE TURN LIFECYCLE (v3.0 3-Node Architecture)
# ==============================================================================
add_container(
    "s_turn", 520, 200, 3880, 1450,
    "复合状态：单次处理周期（3 节点核心流水线 · 兼顾 5~8 秒极速响应与 4 块硬安全底盘）",
    S_COMPOSITE_TURN,
)

add_transition(
    "t_idle_to_turn", "s_idle", "s_turn",
    "收到微信消息\n或 邮件整点汇总",
    C_MAIN,
    exit_xy=(1, 0.45), entry_xy=(0, 0.22),
    points=[(445, 528), (445, 519)],
    label_pos=0.0, label_offset_y=-24,
)
add_transition(
    "t_turn_to_idle", "s_turn", "s_idle",
    "本轮抵达◉ / 回到待机，等待董事长下一条指令（或继续自然语言追问、一步改卡落盘）",
    C_RET,
    exit_xy=(0.15, 1), entry_xy=(0.5, 1),
    points=[(1102, 1682), (249, 1682)],
    label_pos=-0.42, label_offset_y=-16,
)

# --- NODE 1: Context Intake & Deterministic Fact Supply ---
add_text("lbl_n1", 555, 252, 560, 26, "【节点 1｜接入安全、事实供给与上下文装配（纯确定性底盘）】", S_STAGE_TAG)
add_initial("turn_init", 560, 508, 28)
add_state(
    "n1_intake", 620, 295, 540, 470,
    "上下文装配与事实供给中",
    [
        "entry / 微信通道：AES验签·单人白名单·0.5秒到达回执·2秒逐条合批·语音转文字",
        "entry / 邮件通道：域名名单过滤·抽取完整正文与发收抄送角色·可信与不可信内容物理分框",
        "do / 随附文件（PDF/Word/Excel/ZIP等）前置按页入库并备份云端收件箱（坏文件优雅占位）",
        "do / 生成显式上海时区《本周/下周日历锚点表》（昨天/今天周几/明天/本周一~日/下周一~日）",
        "do / 从本地真值库装配：跨天滚动摘要·近30轮真实对话（绝不混入原始邮件正文）·完整待确认卡·在途任务快照（1~7栏与来源标签）",
        "exit / 核查是否命中极简 0 模型单字应急按钮（仅限 1/2/0/撤销/看板/负荷，绝无自然语言正则）",
    ],
    "code",
)
add_transition("t_turn_init", "turn_init", "n1_intake", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.48))

# Choice ◇ after Intake: 0-LLM Emergency Button vs Flagship Brain
add_choice("ch_intake", 1240, 508, 48)
add_transition("t_n1_ch", "n1_intake", "ch_intake", "事实齐备", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5), label_offset_y=-14)

# --- NODE 2: Flagship Single-Brain Reasoning + 3 Objective Guardrails (Bounded <=2 Loop) ---
add_text("lbl_n2", 1450, 252, 1180, 26, "【节点 2｜旗舰单脑综合决策与 3 条客观底盘护栏（唯一大模型 · 0 次小模型路由 · 0 次二审大模型）】", S_STAGE_TAG)
add_container(
    "n2_brain_box", 1450, 295, 1340, 910,
    "复合状态：旗舰单脑推理与客观护栏（全图唯一有界回环 · 上限 2 轮）",
    S_COMPOSITE_BRAIN,
)

add_transition(
    "t_ch_brain", "ch_intake", "n2_brain_box",
    "[else：所有自然语言、\n改卡落盘、查档与邮件]",
    C_BRAIN,
    exit_xy=(1, 0.5), entry_xy=(0, 0.26),
    width=2.8, label_pos=0.0, label_offset_y=-24,
)

add_initial("b_init", 1485, 535, 26)
add_state(
    "n2_llm", 1545, 355, 560, 400,
    "1. 旗舰大脑思考与原生工具调用",
    [
        "do / 调用唯一旗舰主脑 qwen3.8-max（备选自动切换）一次性通读全部上下文与日历锚点表",
        "do / 按需自主调用 4 个确定性只读工具（上限 ≤4 轮）：",
        "  • 查历史文档与跨天旧对话  • 精确读原件页码",
        "  • 查未来 14 天排期密度    • 精确推算工作日日期",
        "do / 直接产出统一决策：新建/修改待确认卡、1 步改卡并确认落盘、一句复合改多条任务、闭卷带页码问答、或参谋回复",
        "do / 纯项目管理（PMO）定位：不编造数字、不泄露内部技术黑话、不代发外部消息",
    ],
    "llm",
)
add_state(
    "n2_guard", 2180, 385, 450, 330,
    "2. 客观底盘三线安检（纯代码，0 模型，仅提案模式）",
    [
        "do / ① 日期合法性：确认全部日期为真实公历且截止不早于开始（绝不误杀昨天/本周五推算）",
        "do / ② 显式邮件抄送通道锁：仅针对外部邮件抄送项，严禁把董事长填为负责人或实施人（绝不误伤微信交办）",
        "do / ③ 客观工时上限：防外部等待跨度误填为个人工时（彻底取消字面子串数字误杀）",
        "exit / 汇总客观报错清单（日常合法决策 0 报错直接一次通过）",
    ],
    "code",
)
add_choice("ch_guard", 2690, 526, 48)
add_final("b_fin", 2697, 815, 34)

add_transition("t_b_init", "b_init", "n2_llm", "", C_BRAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.48))
add_transition("t_llm_guard", "n2_llm", "n2_guard", "产出统一决策 [仅提案模式]", C_BRAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5), label_offset_y=-14)
add_transition("t_guard_ch", "n2_guard", "ch_guard", "", C_BRAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))

# Bounded loop proof inside Node 2 (routes cleanly around right side of b_fin)
add_transition(
    "t_guard_retry", "ch_guard", "n2_llm",
    "[触犯客观硬底线 且 自纠次数 < 2] / 携客观报错反馈自纠，自纠次数+1（全图唯一有界回环）",
    C_LOOP,
    exit_xy=(1, 0.5), entry_xy=(0.5, 1),
    points=[(2766, 550), (2766, 1085), (1825, 1085)],
    width=2.6, label_pos=0.15, label_offset_y=-16,
)
add_transition(
    "t_guard_pass", "ch_guard", "b_fin",
    "[else：通过 或 自纠次数 >= 2]",
    C_BRAIN,
    exit_xy=(0.5, 1), entry_xy=(0.5, 0),
    label_pos=-0.1, label_offset_y=-14,
)

add_note(
    "n2_note", 1545, 815, 980, 175,
    "为什么彻底删除旧版小模型路由与二审大模型？（方案 A 实证收益）",
    [
        "• 彻底消灭多节点传话失真：不再出现“您明明补充了本周五，却被二审当成造假抹回待补齐”的内耗事故。",
        "• 支持任意自然中文与复合指令：例如「目标截止暂定本周五，之后确认落盘了」一步完成改卡与落盘；一句话同时改多条任务截止日、加 CEO 评价与打卡。",
        "• 耗时由 25~40 秒压降至 5~8 秒，同时单任务卡片自动隐藏重复长摘要与系统噪点，零英文代码黑话。",
    ],
)

# --- NODE 3: Deterministic Action Executor & Concise Renderer ---
add_text("lbl_n3", 2955, 252, 1180, 26, "【节点 3｜受控执行、原子落盘与精简回复（唯一可改正式数据库与云端看板的受控出口）】", S_STAGE_TAG)
add_container(
    "n3_exec_box", 2955, 295, 1410, 1295,
    "复合状态：确定性执行与精简输出（4 块底盘收口：审批验签 · 原子落盘 · 来源打标 · 极简渲染）",
    S_COMPOSITE_EXEC,
)

# Emergency 0-LLM Bypass Transition from ch_intake -> n3_exec_box (routes cleanly along bottom corridor)
add_transition(
    "t_ch_emergency", "ch_intake", "n3_exec_box",
    "[命中 0 模型单字应急按钮：1 / 2 / 0 / 撤销 / 看板 / 负荷（大模型 503 断网照常秒回）]",
    C_COMMIT,
    exit_xy=(0.5, 1), entry_xy=(0, 0.85),
    points=[(1264, 1396)],
    width=2.6, label_pos=-0.12, label_offset_y=-16,
)
# Normal completion transition from Node 2 -> Node 3
add_transition(
    "t_brain_exec", "n2_brain_box", "n3_exec_box",
    "决策就绪",
    C_COMMIT,
    exit_xy=(1, 0.42), entry_xy=(0, 0.30),
    width=2.8, label_offset_y=-14,
)

add_initial("e_init", 2988, 672, 26)
add_choice("ch_exec", 3060, 661, 48)
add_transition("t_e_init", "e_init", "ch_exec", "", C_COMMIT, exit_xy=(1, 0.5), entry_xy=(0, 0.5))

add_state(
    "e_commit", 3360, 355, 650, 255,
    "A. 审批落盘正式任务库与云端看板",
    [
        "entry / 现场签发并校验一次性 HMAC 人类确认令牌（硬错未消解或无令牌物理拒写）",
        "do / 本地 SQLite 单事务原子写入任务/更新与 24 小时撤销快照",
        "do / 自动强打标来源（微信/邮件/驾驶舱）并自动回填 120 位邮件会话编号",
        "do / 同步归档附件并重绘世纪互联 OneDrive 5 份看板（云端波动绝不回滚本地）",
    ],
    "commit",
)
add_state(
    "e_direct", 3360, 650, 650, 225,
    "B. 复合直接更新已有任务或 24h 撤销",
    [
        "do / 单轮一次性执行任意组合：改截止日/实施人/负责人/阶段/卡点、追加 CEO 评价/备注/进展、批量开始/完成打卡、查沟通时间轴、或 24 小时一键撤销",
        "do / 实时同步刷新云端 OneDrive 看板与 Web 驾驶舱（共享同一数据库）",
    ],
    "commit",
)
add_state(
    "e_preview", 3360, 915, 650, 255,
    "C. 暂存草稿并推送极简确认卡",
    [
        "entry / 仅存入「待确认暂存表」（绝不改动正式待办与看板）",
        "do / 极简模板排版：单任务卡自动隐藏冗余长摘要、过滤无意义系统出处、零技术黑话",
        "do / 若满 2 轮仍有客观硬错未消解，显式印出「⚠️ 审计待人工复核点」交由董事长裁决",
        "注 / 董事长下一句说「1」或「截止改周五直接落盘」即可进入分支 A",
    ],
    "code",
)
add_state(
    "e_reply", 3360, 1210, 650, 180,
    "D. 纯知会、闭卷问答或只读查询回复",
    [
        "do / 纯知会邮件免建阻塞卡片；查档带页码出处；看板/负荷只读不改库",
        "do / 若 1 步落盘触发客观硬错，物理拦截落盘并明确提示修正点",
    ],
    "code",
)

# Shared Turn-End Output & Turn Recording State inside Node 3
add_state(
    "e_out", 4085, 695, 250, 320,
    "脱敏推送并记入对话",
    [
        "entry / 扫描防密钥泄漏",
        "do / 分片推送个人微信",
        "do / 记录本轮真实对话（外部原始邮件正文绝不污染对话流）",
        "exit / 满 8 轮触发正交区 B 滚动摘要",
    ],
    "code",
)
add_final("turn_fin", 4193, 1085, 34)

add_transition(
    "t_ex_a", "ch_exec", "e_commit",
    "[确认待确认卡 或\n1步改卡并落盘(0硬错)]", C_COMMIT,
    exit_xy=(0.5, 0), entry_xy=(0, 0.5),
    points=[(3084, 482)],
    label_pos=0.22, label_offset_y=-24,
)
add_transition(
    "t_ex_b", "ch_exec", "e_direct",
    "[复合改已有任务/\n追评/打卡/撤销]", C_COMMIT,
    exit_xy=(1, 0.5), entry_xy=(0, 0.45),
    points=[(3215, 685), (3215, 751)],
    label_pos=0.25, label_offset_y=-24,
)
add_transition(
    "t_ex_c", "ch_exec", "e_preview",
    "[需确认的新建/改卡\n待确认提案]", C_MAIN,
    exit_xy=(0.75, 0.75), entry_xy=(0, 0.5),
    points=[(3155, 697), (3155, 1042)],
    label_pos=0.45, label_offset_y=-24,
)
add_transition(
    "t_ex_d", "ch_exec", "e_reply",
    "[else：纯知会/问答/\n看板负荷/硬错拦截]", C_RET,
    exit_xy=(0.5, 1), entry_xy=(0, 0.5),
    points=[(3084, 1300)],
    label_pos=0.42, label_offset_y=-24,
)

add_transition("t_a_out", "e_commit", "e_out", "", C_COMMIT, exit_xy=(1, 0.5), entry_xy=(0.5, 0), points=[(4210, 482)])
add_transition("t_b_out", "e_direct", "e_out", "", C_COMMIT, exit_xy=(1, 0.5), entry_xy=(0, 0.25), points=[(4045, 762), (4045, 775)])
add_transition("t_c_out", "e_preview", "e_out", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.75), points=[(4045, 1042), (4045, 935)])
add_transition("t_d_out", "e_reply", "e_out", "", C_RET, exit_xy=(1, 0.5), entry_xy=(0.25, 1), points=[(4148, 1300)])
add_transition("t_out_fin", "e_out", "turn_fin", "本轮结束", C_RET, exit_xy=(0.5, 1), entry_xy=(0.5, 0), label_offset_y=0)

# ==============================================================================
# 3. ORTHOGONAL REGION B (Concurrent Background Monitors & Schedulers)
# ==============================================================================
add_line("ortho_div_ab", 42, 1720, 4396, 10, S_ORTHO_H)
add_text(
    "reg_b_lbl", 64, 1742, 1900, 30,
    "正交区域 B｜后台并发伴随机制（与主消息处理并行独立运行，通过虚线正交隔离，互不阻塞）",
    S_REGION_LBL,
)

# B1: Progress Heartbeat
add_text("lbl_b1", 80, 1785, 520, 24, "并发子区 B1｜长耗时进度心跳监控（防假死）", S_STAGE_TAG)
add_initial("b1_init", 84, 1930, 24)
add_state(
    "b1_watch", 136, 1848, 370, 185,
    "监控单次处理耗时",
    [
        "do / 随单次处理启动异步计时器",
        "注 / v3.0 常规 5~8 秒直出，12 秒内安静退出零打扰",
    ],
    "bg",
)
add_state(
    "b1_beat", 790, 1848, 460, 185,
    "定期播报当前进度",
    [
        "do / 每次超时向微信播报「已用时 Xs：正在执行【1~3 阶段】」",
        "exit / 主流程结束或异常退出时立即销毁计时器",
    ],
    "bg",
)
add_transition("t_b1_init", "b1_init", "b1_watch", "", C_BG, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
add_transition("t_b1_start", "b1_watch", "b1_beat", "after(12秒) [仍处理中]", C_BG, exit_xy=(1, 0.35), entry_xy=(0, 0.35), label_offset_y=-14)
add_transition("t_b1_loop", "b1_beat", "b1_beat", "after(25秒) [仍未结束]", C_BG, exit_xy=(0.75, 1), entry_xy=(0.25, 1), points=[(1135, 2105), (905, 2105)], label_offset_y=-14)
add_transition("t_b1_stop", "b1_beat", "b1_watch", "单次处理结束 / 销毁", C_RET, exit_xy=(0, 0.72), entry_xy=(1, 0.72), label_offset_y=16)

add_line("ortho_div_b12", 1325, 1785, 10, 380, S_ORTHO_V)

# B2: Daily Digest & Workday Hourly Mail Window
add_text("lbl_b2", 1370, 1785, 920, 24, "并发子区 B2｜工作日早晚简报与整点 Outlook 只读汇总", S_STAGE_TAG)
add_initial("b2_init", 1374, 1930, 24)
add_state(
    "b2_wait", 1425, 1845, 415, 195,
    "按时钟轮询等待唤醒",
    [
        "do / 每 30 秒核对本地时钟（仅周一至周五运行）",
        "do / 夜间与周末完全静默不打扰；推送成功后再记防重水位",
    ],
    "bg",
)
add_state(
    "b2_digest", 2180, 1820, 620, 130,
    "推送早间简报 / 18:00 晚间盘点",
    [
        "do / 汇总今日在途（附微信/邮件/驾驶舱来源标）、临期与卡点，推送微信并记对话",
        "exit / 支持直接自然语言批量打卡或修改排期",
    ],
    "bg",
)
add_state(
    "b2_mail", 2180, 1980, 620, 150,
    "拉取白名单邮件整点汇总（物理只读）",
    [
        "do / 08:30 补夜间周末积压；09:00–21:00 每小时一次；强制标来源=邮件",
        "do / 老会话自动绑定已有任务追加时间轴，新事合批触发正交区 A；上卡未回则延后不覆盖",
    ],
    "bg",
)
add_transition("t_b2_init", "b2_init", "b2_wait", "", C_BG, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
add_transition("t_b2_dig", "b2_wait", "b2_digest", "at(工作日 08:30 / 18:00)", C_BG, exit_xy=(1, 0.25), entry_xy=(0, 0.5), points=[(2005, 1893), (2005, 1885)], label_offset_y=-14)
add_transition("t_b2_mail", "b2_wait", "b2_mail", "at(工作日 08:30 及 09–21 整点) [有新信]", C_BG, exit_xy=(1, 0.78), entry_xy=(0, 0.5), points=[(2005, 1997), (2005, 2055)], label_offset_y=-14)
add_transition("t_b2_dig_back", "b2_digest", "b2_wait", "", C_RET, exit_xy=(0.5, 0), entry_xy=(0.5, 0), points=[(2490, 1812), (1632, 1812)])
add_transition("t_b2_mail_back", "b2_mail", "b2_wait", "", C_RET, exit_xy=(0.5, 1), entry_xy=(0.5, 1), points=[(2490, 2154), (1632, 2154)])

add_line("ortho_div_b23", 2870, 1785, 10, 380, S_ORTHO_V)

# B3: Rolling Semantic Summary Background Upgrader
add_text("lbl_b3", 2915, 1785, 920, 24, "并发子区 B3｜跨天滚动会话摘要后台升级（不阻塞主回复）", S_STAGE_TAG)
add_initial("b3_init", 2920, 1930, 24)
add_state(
    "b3_idle", 2972, 1848, 460, 185,
    "空闲等待对话满 8 轮",
    [
        "do / 监听真实对话入库计数，未满 8 轮不耗模型",
        "note / 满 8 轮瞬间由主流程先同步写保底摘要并推进游标",
    ],
    "bg",
)
add_state(
    "b3_run", 3740, 1838, 650, 205,
    "后台线程语义摘要升级",
    [
        "do / 调用轻量模型 qwen3.8-flash 合并为 ≤600 字中文要点（仅在后台运行，绝不参与主决策）",
        "do / 核对乐观锁覆盖更新至数据库；超时或失败安全保留关键词保底摘要",
    ],
    "llm",
)
add_transition("t_b3_init", "b3_init", "b3_idle", "", C_BG, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
add_transition("t_b3_go", "b3_idle", "b3_run", "新增对话满 8 轮 / 启守护线程", C_BG, exit_xy=(1, 0.35), entry_xy=(0, 0.35), label_offset_y=-14)
add_transition("t_b3_done", "b3_run", "b3_idle", "摘要升级完毕或降级保留", C_RET, exit_xy=(0, 0.72), entry_xy=(1, 0.72), label_offset_y=16)


def build_xml() -> str:
    body = "\n        ".join(cells)
    return f"""<mxfile host="app.diagrams.net" modified="2026-11-25T13:20:00.000Z" agent="gen_workflow_drawio.py (v3.0 UML 2.5)" version="24.0.0">
  <diagram id="wechat-ai-uml25-v3" name="AI助理v3.0状态机全景图(UML2.5)">
    <mxGraphModel dx="1422" dy="794" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{PAGE_W}" pageHeight="{PAGE_H}" math="0" shadow="0" background="#ffffff">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        {body}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""


def main() -> None:
    OUT_PATH.write_text(build_xml(), encoding="utf-8")
    print(f"Wrote strict UML 2.5 v3.0 state machine diagram to {OUT_PATH} ({len(cells)} mxCells)")


if __name__ == "__main__":
    main()
