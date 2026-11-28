"""Generate the strict OMG UML 2.5 Behavioral State Machine Diagram (.drawio)
for `wecom_report_agentic_analysis` V2.3 (Scheme B — Red-Team Loophole Critic + Alert-Driven PDF/Email):
- Standalone Weekly PDF + Cyber Griffin Email (decoupled from WeChat Dashboard)
- Stage 1: Explicit Full-Backfill vs Incremental Sync branch + 4-Tier Goals & 4-Window Hard Trend Desktop
- Stage 2: Flagship Brain Multi-Horizon Investigation (<= 18 steps, configurable) + Initial Draft Synthesis
- Stage 3 (Scheme B): Independent Red-Team Loophole & Alert Critic (100% shared evidence, zero telephone-game loss)
  + Lightweight Evidence Verification & Red/Yellow/Blue Alert Grading (<= 2 bounded retries; minor unverified items
  degraded/grayed rather than silently dropping the weekly alert email)
- Stage 4: Archive + Alert-Driven Executive PDF Rendering + Graded Alert Subject/Body via Cyber Griffin Email
- Orthogonal Regions B1 (Schedule/Studio) & B2 (Full-Chain Observability & LLM Context Monitoring Hub)

Run:
  python3 wecom_report_agentic_analysis/diagrams/gen_uml25_workflow_drawio.py
  "/Applications/draw.io.app/Contents/MacOS/draw.io" -x -f png --scale 1.5 \
      -o wecom_report_agentic_analysis/diagrams/04_WORKFLOW_AUDIT_AND_UML25_ARCHITECTURE.png \
      wecom_report_agentic_analysis/diagrams/04_WORKFLOW_AUDIT_AND_UML25_ARCHITECTURE.drawio
"""

from __future__ import annotations

import html
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parent / "04_WORKFLOW_AUDIT_AND_UML25_ARCHITECTURE.drawio"
DX1 = 460    # Extra width after Stage 1 (explicit full vs incremental branch)
DX2 = 740    # Extra width after Stage 2 (+280 for dedicated draft synthesis state)
DX3 = 1140   # Extra width after Stage 3 (+400 for independent Red-Team Critic state)
PAGE_W, PAGE_H = 3600 + DX3, 1940

# --- Strict OMG UML 2.5 mxGraph styles ---
S_TITLE = (
    "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;"
    "fontSize=26;fontStyle=1;fontColor=#0f172a;"
)
S_SUBTITLE = (
    "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;"
    "fontSize=14;fontColor=#475569;"
)
S_LEGEND_TXT = (
    "text;html=1;strokeColor=none;fillColor=none;fontSize=13;"
    "align=left;verticalAlign=middle;fontColor=#1e293b;"
)

S_INITIAL = "ellipse;html=1;shape=startState;fillColor=#0f172a;strokeColor=#0f172a;"
S_FINAL = "ellipse;html=1;shape=endState;fillColor=#0f172a;strokeColor=#0f172a;"
S_CHOICE = "rhombus;whiteSpace=wrap;html=1;fillColor=#fffbeb;strokeColor=#b45309;strokeWidth=2.5;"

S_COMPOSITE_ROOT = (
    "swimlane;startSize=40;rounded=1;arcSize=2;fillColor=#ffffff;strokeColor=#334155;"
    "strokeWidth=2.5;fontSize=17;fontStyle=1;fontColor=#0f172a;align=left;spacingLeft=16;"
)
S_STAGE_BLUE = (
    "swimlane;startSize=36;rounded=1;arcSize=3;fillColor=#f8fafc;strokeColor=#2563eb;"
    "strokeWidth=2;fontSize=15;fontStyle=1;fontColor=#1e3a8a;align=left;spacingLeft=14;"
)
S_STAGE_PURPLE = (
    "swimlane;startSize=36;rounded=1;arcSize=3;fillColor=#faf5ff;strokeColor=#7c3aed;"
    "strokeWidth=2;fontSize=15;fontStyle=1;fontColor=#5b21b6;align=left;spacingLeft=14;"
)
S_STAGE_REDTEAM = (
    "swimlane;startSize=36;rounded=1;arcSize=3;fillColor=#fffbeb;strokeColor=#d97706;"
    "strokeWidth=2;fontSize=15;fontStyle=1;fontColor=#92400e;align=left;spacingLeft=14;"
)
S_STAGE_ORANGE = (
    "swimlane;startSize=36;rounded=1;arcSize=3;fillColor=#fff7ed;strokeColor=#c2410c;"
    "strokeWidth=2;fontSize=15;fontStyle=1;fontColor=#9a3412;align=left;spacingLeft=14;"
)

S_ORTHO_H = "line;strokeWidth=2;dashed=1;dashPattern=8 6;strokeColor=#64748b;fillColor=none;html=1;"
S_ORTHO_V = (
    "line;strokeWidth=2;dashed=1;dashPattern=8 6;strokeColor=#94a3b8;"
    "fillColor=none;html=1;direction=south;"
)
S_REGION_LBL = (
    "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;"
    "fontSize=15;fontStyle=1;fontColor=#1e293b;"
)
S_UML_NOTE = (
    "shape=note;whiteSpace=wrap;html=1;backgroundOutline=1;size=16;"
    "fillColor=#fefce8;strokeColor=#ca8a04;strokeWidth=1.5;"
    "fontSize=13;align=left;verticalAlign=top;spacingTop=8;spacingLeft=12;spacingRight=14;fontColor=#422006;"
)

PALETTES = {
    "idle": ("#f1f5f9", "#475569", "#0f172a"),
    "code": ("#eff6ff", "#1d4ed8", "#1e3a8a"),
    "llm": ("#f5f3ff", "#6d28d9", "#4c1d95"),
    "redteam": ("#fef2f2", "#dc2626", "#991b1b"),
    "tool": ("#ecfdf5", "#047857", "#064e3b"),
    "verify": ("#fefce8", "#b45309", "#78350f"),
    "commit": ("#fff7ed", "#c2410c", "#7c2d12"),
}

C_MAIN = "#1e40af"
C_BRAIN = "#6d28d9"
C_TOOL = "#047857"
C_VERIFY = "#b45309"
C_LOOP = "#b91c1c"
C_COMMIT = "#c2410c"
C_ERR = "#64748b"

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
        f'<div style="text-align:center;font-size:15px;color:{title_color};padding:7px 10px 6px 10px;'
        f'border-bottom:1.5px solid {stroke};">{title_html}</div>'
        f'<div style="text-align:left;font-size:12.5px;color:#1e293b;padding:8px 11px 8px 11px;line-height:1.48;">'
        f"{body_html}</div>"
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
    label_offset_x: int = 0,
    label_offset_y: int = -14,
) -> None:
    style = (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;"
        "endArrow=open;endFill=0;endSize=10;"
        f"exitX={exit_xy[0]};exitY={exit_xy[1]};exitDx=0;exitDy=0;"
        f"entryX={entry_xy[0]};entryY={entry_xy[1]};entryDx=0;entryDy=0;"
        f"strokeColor={color};strokeWidth={width};"
        f"fontSize=12.5;fontStyle=1;fontColor={color};labelBackgroundColor=#ffffff;"
    )
    pts = ""
    if points:
        pts = (
            '<Array as="points">'
            + "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in points)
            + "</Array>"
        )
    geo_attr = 'relative="1" as="geometry"'
    offset_xml = ""
    if label:
        geo_attr = f'x="{label_pos}" y="{label_offset_y}" relative="1" as="geometry"'
        offset_xml = f'<mxPoint x="{label_offset_x}" as="offset"/>' if label_offset_x else '<mxPoint as="offset"/>'
    val_html = "<br/>".join(html.escape(line) for line in label.splitlines()) if label else ""
    add_raw(
        f'<mxCell id="{eid}" value="{_esc(val_html)}" style="{style}" edge="1" parent="1" source="{src}" target="{dst}">'
        f"<mxGeometry {geo_attr}>{pts}{offset_xml}</mxGeometry></mxCell>"
    )


# ==============================================================================
# 0. TITLE & STRICT UML 2.5 LEGEND BAR
# ==============================================================================
add_text(
    "title",
    40,
    18,
    2700,
    42,
    "维恩科仪「双轨制」周度经营诊断与预警智能体 — OMG UML 2.5 行为状态机架构图（V3.0 质量轨×战略轨 · 生产无头版）",
    S_TITLE,
)
add_text(
    "subtitle",
    40,
    64,
    2480,
    30,
    "严格遵循 OMG UML 2.5 状态机标准与 07/08/09/ADP（经董事长拍板按需启用 Ch.4 独立红队反思）：● 初始伪状态  ◉ 终止状态  圆角框=状态  ◇ 动态分流  实线=事件[条件]/动作  虚线=并发正交区",
    S_SUBTITLE,
)

add_initial("lg_init", 2680, 36, 22)
add_text("lg_init_t", 2708, 28, 86, 38, "初始伪状态", S_LEGEND_TXT)
add_final("lg_fin", 2802, 34, 26)
add_text("lg_fin_t", 2834, 28, 76, 38, "终止状态", S_LEGEND_TXT)
add_choice("lg_ch", 2918, 32, 30)
add_text("lg_ch_t", 2954, 28, 86, 38, "选择伪状态", S_LEGEND_TXT)

add_state("lg_code", 3060, 18, 160, 74, "确定性底盘状态", ["do / 0模型事实与安全"], "code")
add_state("lg_llm", 3235, 18, 160, 74, "旗舰主脑状态", ["do / 翻查与初稿生成"], "llm")
add_state("lg_tool", 3410, 18, 160, 74, "只读查证车间", ["do / 4项只读查证工具"], "tool")
add_state("lg_red", 3585, 18, 165, 74, "独立红队复核", ["do / 专揪漏洞发预警"], "redteam")
add_state("lg_ver", 3765, 18, 160, 74, "证据核验定档", ["do / 查真伪定红黄蓝"], "verify")
add_state("lg_com", 3940, 18, 165, 74, "预警PDF与发信", ["do / 分级预警邮件"], "commit")
add_note(
    "lg_note",
    4120,
    18,
    580,
    74,
    "方案 B 核心定位：找漏洞 + 分级预警（Alert）+ 可落地整改建议",
    ["每周低频高价值审计启用独立红队复核（100% 共享原始证据，绝不和稀泥），轻量防假证据核验保障预警稳定送达。"],
)


# ==============================================================================
# 1. TOP-LEVEL COMPOSITE STATE CONTAINER (2 Orthogonal Regions)
# ==============================================================================
add_container(
    "sys_root",
    40,
    112,
    3520 + DX3,
    1790,
    "维恩科仪「双轨制」经营质量与战略对齐智能体系统 V3.0（轨一：SOP·留痕·硬成果质量评估 × 轨二：目标投入账本与四期演进 · 对齐 06/07 文档）",
    S_COMPOSITE_ROOT,
)

add_text(
    "reg_a_lbl",
    64,
    160,
    4400,
    30,
    "正交区域 A｜周度经营漏洞挖掘、分级预警（Alert）与 PDF 邮件投递主状态机（首次全量 / 后续增量分流 → 主脑翻查 ≤18 轮出初稿 → 独立红队挑刺补漏洞 → 证据核验定档 → 预警 PDF 发信）",
    S_REGION_LBL,
)

# Entry Initial Pseudostate (Region A) — center y = 555
add_initial("top_init", 66, 540, 30)


# ==============================================================================
# STAGE 1: Deterministic Ingestion (Explicit Full vs Incremental) & Desktop Context
# ==============================================================================
add_container(
    "stg1",
    165,
    205,
    920 + DX1,
    975,
    "阶段一：确定性采集（首次全量 / 后续增量）与四期桌面装配底盘（0% 大模型）",
    S_STAGE_BLUE,
)

add_state(
    "s_check_wm",
    188,
    415,
    255,
    280,
    "校验凭据与检查水位",
    [
        "entry / 读取企业微信只读凭据与 5 类汇报模板清单",
        "do / 同步最新公司花名册",
        "do / 读取本地同步水位记录，判定是否已完成首次全量历史拉取",
    ],
    "code",
)

add_choice("c_sync_mode", 500, 533, 44)  # center (522, 555)

add_state(
    "s_full_sync",
    655,
    265,
    300,
    210,
    "首次全量历史拉取",
    [
        "do / 自历史起点按 ≤25 天切片分页回溯，一次性拉取全部 5 类历史汇报（支持断点续传）",
        "exit / 按唯一汇报编号幂等写入本地分析库（绝不改写董事长任务主表），打标「已完成首次全量」并记录同步水位",
    ],
    "code",
)

add_state(
    "s_inc_sync",
    655,
    565,
    300,
    210,
    "后续增量拉取汇报",
    [
        "do / 仅从上次同步水位起拉取新增汇报（自动兼容近期迟交补报并按唯一编号跳过已入库记录，绝不重拉全量历史）",
        "exit / 幂等写入本次新增汇报至本地分析库（绝不改写董事长任务主表），推进最新同步水位",
    ],
    "code",
)

add_choice("c_sync", 1018, 533, 44)  # center (1040, 555)

add_state(
    "s_desktop",
    1198,
    375,
    330,
    360,
    "核算双轨硬指标与装配桌面",
    [
        "entry / 读取四层目标（空层自动跳过）与新企微模板生效日（旧数据免苛责新字段）",
        "do / 精确考勤 + 质量硬数：剔除周末/法定节假日、次日 12:00 宽限、现场报告替代 10 分钟日报、注明未扣请假倒休；统计新模板「成果/存档/目标挂钩」填写率与附件率",
        "do / 核算【近1月 / 近1季 / 近1年 / 全量】四期趋势矩阵，装载 15 人花名册、董事长在途任务与历史摘要",
        "exit / 为近 30 天汇报分配短编号（R-001起）并套不可信外部数据物理围栏",
    ],
    "code",
)

add_final("f_sync_err", 785, 1020, 34)  # center (802, 1037)
add_final("f_sync_empty", 1250, 1020, 34)  # center (1267, 1037)


# ==============================================================================
# STAGE 2: Flagship Brain Investigation Loop (<=18) & Initial Draft Synthesis
# ==============================================================================
add_container(
    "stg2",
    1140 + DX1,
    205,
    1100,
    975,
    "阶段二：旗舰主脑多周期翻查（上限 18 轮，可配置）与诊断初稿生成（Model-First + ReAct）",
    S_STAGE_PURPLE,
)

add_state(
    "s_brain",
    1165 + DX1,
    395,
    325,
    320,
    "旗舰主脑研判与翻查",
    [
        "entry / 读取共享白板：四层目标、四期滚动趋势矩阵、围栏内近30天汇报及历次翻查回来的新证据",
        "do / 唤醒旗舰推理主脑（开启深度思考）：拿【月/季/年/长期】四层目标当照妖镜，识别业务偏离、执行漏洞与跨季异常拐点",
        "do / 若需核实更早历史因果或重点任务细节，则发起只读翻查请求（单轮可并发查多项）；若证据已查齐，则宣布停止翻查",
        "exit / 翻查次数 +1，全量思考链与上下文推送至监控大盘",
    ],
    "llm",
)

add_choice("c_react", 1605 + DX1, 533, 44)  # center (1627 + DX1 = 2087, 555)

add_state(
    "s_tools",
    1165 + DX1,
    835,
    405,
    315,
    "只读查证工具车间（仅 4 项只读工具）",
    [
        "entry / 校验工具白名单与严格只读权限（严禁写库或外发消息）",
        "do / 工具 1 · 查历次审计摘要：对比近月/近季/近年的整改落实与预警收敛轨迹",
        "do / 工具 2 · 回溯全量历史汇报原文：按员工、产品线或客户精准下钻任意历史窗口原件",
        "do / 工具 3 · 查关键员工与董事长任务详情：拉取重点人员或董事长在途任务完整进展流水",
        "do / 工具 4 · 精确日期与占比计算器：确定性计算跨度天数与环比变化，杜绝心算误差",
        "exit / 将真实查证结果（含外部围栏）贴回共享白板，出错时保留原文不崩溃",
    ],
    "tool",
)

add_state(
    "s_synth",
    1885 + DX1,
    365,
    335,
    380,
    "旗舰主脑双轨算账与出稿",
    [
        "entry / 撤掉翻查工具权限，锁定双轨硬数、翻查证据与 06/07 号规格口径",
        "do / 【轨道一 · 管理与汇报质量】：按 SOP 遵循、沟通记录存档、硬成果/结论/知识沉淀、客户满意与收益四维，评全员 15 人质量红黄绿灯，抓出“空心流水账”与高成果标杆",
        "do / 【轨道二 · 战略目标投入总账】：算清各已配置目标投入人·天、精力占比 %、有效推进 vs 救火拆账、硬产出与杂务黑洞池，产出 8×7×5 任务还原、长期转型、李文颖穿透、盲区空转与 AI 提效 4 维度",
        "exit / 写入双轨量化账本与初稿至白板，移交独立红队双轨核账挑刺",
    ],
    "llm",
)


# ==============================================================================
# STAGE 3 (Scheme B): Independent Red-Team Dual-Track Critic + Evidence Check & Alert Grading
# ==============================================================================
add_container(
    "stg3",
    2095 + DX2,
    205,
    1025,
    975,
    "阶段三（方案 B）：独立红队双轨核账 + 10 大漏洞挑刺 + 证据核验与 Alert 定档",
    S_STAGE_REDTEAM,
)

add_state(
    "s_redteam",
    2120 + DX2,
    365,
    345,
    380,
    "独立红队双轨核账与挑刺",
    [
        "entry / 100% 共享已配置目标、双轨硬数、近30天围栏汇报、翻查事实、主脑双轨初稿与纠偏清单（零断层）",
        "do / 第一步 · 双轨核账：复核各目标投入人·天/产出账本（拆穿伪战略投入），并复核全员汇报硬成果与留痕质量评级",
        "do / 第二步 · 按双轨 10 大漏洞清单挑刺：战略轨 8 项（研发稀释/支柱零投入/空转/黑箱/救火/内卷/低效岗/漏查）+ 质量轨 2 项（空心流水账假忙碌 / 跳 SOP 缺沟通存档），标定红/黄/蓝 6 要素 Alert 与硬建议",
        "exit / 输出双轨预警增强版报告，调试期同步推送挑刺思考链至大盘",
    ],
    "redteam",
)

add_state(
    "s_verify",
    2575 + DX2,
    395,
    335,
    320,
    "证据真实性核验与预警定档",
    [
        "entry / 校验报告基本结构与 Alert 预警列表完整性",
        "do / 轻量防幻觉核查：校验每条 Alert 引用的汇报短编号（R-xxx）与董事长任务号 100% 真实存在、日期跨度与数字不自相矛盾（杜绝 AI 冤枉或误报）",
        "do / 自动按「🔴高危漏洞 / 🟡偏离风险 / 🔵AI与效率提示」排序归档，过滤内部代码黑话",
        "exit / 通过则自动回填真实汇报编号；发现伪造证据则列出报错明细；纠偏超限时仅标灰剔除存疑单条，不阻断已查实预警送达",
    ],
    "verify",
)

add_choice("c_verify", 3015 + DX2, 533, 44)  # center (3037 + DX2 = 3777, 555)

add_final("f_verify_fail", 3020 + DX2, 1020, 34)


# ==============================================================================
# STAGE 4: Archive, Alert-Driven Executive PDF Rendering & Cyber Griffin Email Delivery
# ==============================================================================
add_container(
    "stg4",
    2870 + DX3,
    205,
    665,
    975,
    "阶段四：归档、预警驱动 PDF 排版与赛博狮鹫分级预警投递（0% 大模型）",
    S_STAGE_ORANGE,
)

add_state(
    "s_deliver",
    2900 + DX3,
    395,
    365,
    320,
    "归档、预警 PDF 渲染与邮件投递",
    [
        "entry / 单事务原子写入周度审计与漏洞预警库（绝不修改董事长任务主表），检查本周期防重发幂等锁",
        "do / 确定性排版高管级 PDF：首页置顶《本周经营漏洞 Alert 告警台与董事长决断清单》（按红/黄/蓝排序附实证与建议），后附四层目标演进图、15人硬统计、高成本研发穿透与 AI 替代清单",
        "do / 经由赛博狮鹫专属发件邮箱发信：主题自动标注最高告警等级与条数，正文直出 Top 预警与建议动作，完整 PDF 作为附件投递",
        "exit / 留存本地 PDF 归档副本、写入发信回执并闭合本轮监控轨迹",
    ],
    "commit",
)

add_choice("c_deliver", 3365 + DX3, 533, 44)  # center (3387 + DX3, 555)

add_final("f_done", 3020 + DX3, 1020, 34)
add_final("f_deliver_err", 3368 + DX3, 1020, 34)


# ==============================================================================
# TRANSITIONS IN REGION A (Strict UML 2.5: trigger [guard] / effect)
# ==============================================================================

# 0. Initial -> Stage 1 Check Watermark (clean, unguarded per UML 2.5!)
add_transition(
    "e_init",
    "top_init",
    "s_check_wm",
    "/ 初始化白板\n(翻查=0, 纠偏=0)",
    C_MAIN,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_pos=-0.1,
    label_offset_y=-34,
)

# 1a. Check Watermark -> Sync Mode Choice
add_transition(
    "e_wm_mode",
    "s_check_wm",
    "c_sync_mode",
    "水位\n核查完",
    C_MAIN,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-26,
)

# 1b. Sync Mode Choice -> Full Backfill (First Run Only)
add_transition(
    "e_mode_full",
    "c_sync_mode",
    "s_full_sync",
    "[尚未完成首次全量拉取]\n/ 启动首次全量回溯",
    C_MAIN,
    exit_xy=(0.5, 0.0),
    entry_xy=(0.0, 0.5),
    points=[(522, 370)],
    label_pos=0.1,
    label_offset_x=-10,
    label_offset_y=-28,
)

# 1c. Sync Mode Choice -> Incremental Sync ([else]: All Subsequent Runs)
add_transition(
    "e_mode_inc",
    "c_sync_mode",
    "s_inc_sync",
    "[else：已完成首次全量]\n/ 仅执行增量拉取",
    C_TOOL,
    exit_xy=(0.5, 1.0),
    entry_xy=(0.0, 0.5),
    points=[(522, 670)],
    label_pos=0.1,
    label_offset_x=-10,
    label_offset_y=28,
)

# 1d. Full Backfill -> Result Choice
add_transition(
    "e_full_res",
    "s_full_sync",
    "c_sync",
    "全量结束",
    C_MAIN,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.5, 0.0),
    points=[(1040, 370)],
    label_pos=-0.2,
    label_offset_y=-16,
)

# 1e. Incremental Sync -> Result Choice
add_transition(
    "e_inc_res",
    "s_inc_sync",
    "c_sync",
    "增量\n结束",
    C_TOOL,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    points=[(988, 670), (988, 555)],
    label_pos=-0.25,
    label_offset_x=0,
    label_offset_y=26,
)

# 2. Result Choice -> Desktop Context ([else])
add_transition(
    "e_sync_ok",
    "c_sync",
    "s_desktop",
    "[else：存在有效\n汇报] / 指标核算",
    C_MAIN,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-32,
)

# 3. Result Choice -> Sync Error Final
add_transition(
    "e_sync_err",
    "c_sync",
    "f_sync_err",
    "[企微接口异常 且 重试耗尽]\n/ 记错误日志并邮件告警管理员",
    C_ERR,
    exit_xy=(0.5, 1.0),
    entry_xy=(0.5, 0.0),
    points=[(1040, 875), (802, 875)],
    label_pos=0.25,
    label_offset_y=-28,
)

# 4. Result Choice -> Empty Window Final
add_transition(
    "e_sync_empty",
    "c_sync",
    "f_sync_empty",
    "[本地无任何有效周期汇报]\n/ 记空跑日志，0 模型调用",
    C_ERR,
    exit_xy=(0.5, 1.0),
    entry_xy=(0.5, 0.0),
    points=[(1040, 875), (1267, 875)],
    label_pos=0.25,
    label_offset_y=-28,
)

# 5. Desktop Context -> Flagship Brain Investigation
add_transition(
    "e_desk_brain",
    "s_desktop",
    "s_brain",
    "桌面装配\n完成",
    C_BRAIN,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-28,
)

# 6. Flagship Brain Investigation -> ReAct Gatekeeper Choice
add_transition(
    "e_brain_c",
    "s_brain",
    "c_react",
    "完成本轮\n研判",
    C_BRAIN,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-26,
)

# 7. ReAct Choice -> Read-Only ToolNode (Bounded Loop <= 18 steps)
add_transition(
    "e_react_tool",
    "c_react",
    "s_tools",
    "[需要继续翻查历史档案 且 翻查次数 < 18]\n/ 放行调用只读查证工具",
    C_TOOL,
    exit_xy=(0.5, 1.0),
    entry_xy=(1.0, 0.5),
    points=[(1627 + DX1, 992)],
    label_pos=-0.25,
    label_offset_x=145,
    label_offset_y=0,
)

# 8. ToolNode -> Flagship Brain Investigation (Ping-Pong Return Edge)
add_transition(
    "e_tool_brain",
    "s_tools",
    "s_brain",
    "只读查证完毕 / 贴回围栏事实再次唤醒大脑",
    C_TOOL,
    exit_xy=(0.40, 0.0),
    entry_xy=(0.50, 1.0),
    label_pos=0.0,
    label_offset_x=140,
    label_offset_y=0,
)

# 9. ReAct Choice -> Initial Draft Synthesis (Evidence Ready OR Step Cap >= 18)
add_transition(
    "e_react_synth",
    "c_react",
    "s_synth",
    "[else：证据已查齐 或 翻查次数 >= 18]\n/ 停止翻查，进入初稿收口",
    C_BRAIN,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-32,
)

# 10. Initial Draft Synthesis -> Independent Red-Team Critic
add_transition(
    "e_synth_red",
    "s_synth",
    "s_redteam",
    "提交诊断\n初稿",
    C_LOOP,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-28,
)

# 11a. Independent Red-Team Critic -> Evidence Check & Alert Grading
add_transition(
    "e_red_ver",
    "s_redteam",
    "s_verify",
    "输出预警\n增强报告",
    C_VERIFY,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-28,
)

# 11b. Evidence Check -> Verify Choice
add_transition(
    "e_ver_c",
    "s_verify",
    "c_verify",
    "核验\n完成",
    C_VERIFY,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-26,
)

# 12. Verify Choice -> Red-Team Critic (Bounded Evidence Correction Loop <= 2 retries)
add_transition(
    "e_ver_retry",
    "c_verify",
    "s_redteam",
    "[发现伪造证据或结构解析失败 且 纠偏次数 < 2] / 纠偏次数 +1 并附精确报错退回红队定向修正",
    C_LOOP,
    exit_xy=(0.5, 0.0),
    entry_xy=(0.5, 0.0),
    points=[(3037 + DX2, 296), (2290 + DX2, 296)],
    label_pos=0.0,
    label_offset_y=-16,
    width=2.5,
)

# 13. Verify Choice -> Deliver (Pass OR Degraded Pass with Unverified Minor Items Grayed)
add_transition(
    "e_ver_ok",
    "c_verify",
    "s_deliver",
    "[证据核验通过 或 次要存疑项已标灰剔除]\n/ 放行生成分级预警 PDF 并投递",
    C_COMMIT,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-32,
)

# 14. Verify Choice -> Catastrophic Fail Final (Circuit Breaker >= 2 AND Unparseable)
add_transition(
    "e_ver_fail",
    "c_verify",
    "f_verify_fail",
    "[else：纠偏 >= 2 且 报告彻底损坏无法解析]\n/ 保留客观硬统计草稿并告警维护人",
    C_LOOP,
    exit_xy=(0.5, 1.0),
    entry_xy=(0.5, 0.0),
    label_pos=0.0,
    label_offset_x=-155,
    label_offset_y=0,
)

# 15. Deliver -> Deliver Choice
add_transition(
    "e_del_c",
    "s_deliver",
    "c_deliver",
    "排版发信\n结束",
    C_COMMIT,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-28,
)

# 16. Deliver Choice -> Final Success
add_transition(
    "e_del_ok",
    "c_deliver",
    "f_done",
    "[预警 PDF 渲染与赛博狮鹫发信成功 或 已幂等去重]\n/ 完成本周期漏洞预警与报告投递",
    C_TOOL,
    exit_xy=(0.5, 1.0),
    entry_xy=(0.5, 0.0),
    points=[(3387 + DX3, 825), (3037 + DX3, 825)],
    label_pos=0.1,
    label_offset_y=-30,
)

# 17. Deliver Choice -> Final Deliver Error
add_transition(
    "e_del_err",
    "c_deliver",
    "f_deliver_err",
    "[else：PDF 异常或发信重试耗尽]\n/ 保留已归档报告与本地 PDF 待补发",
    C_ERR,
    exit_xy=(0.5, 1.0),
    entry_xy=(0.5, 0.0),
    label_pos=0.45,
    label_offset_x=-130,
    label_offset_y=0,
)


# ==============================================================================
# 2. ORTHOGONAL REGION DIVIDER & REGION B (Concurrent Monitors & Schedulers)
# ==============================================================================
add_line("ortho_h", 56, 1212, 3488 + DX3, 4, S_ORTHO_H)
add_line("ortho_v", 1720, 1232, 4, 650, S_ORTHO_V)

# --- Sub-Region B1: Production Headless Schedule (Default) vs Debug Studio (Dev Only) ---
add_text(
    "reg_b1_lbl",
    64,
    1235,
    1620,
    30,
    "正交区域 B1｜触发调度（正式生产：轻量定时无头直跑 ｜ 仅调试期按需用 LangGraph Studio）",
    S_REGION_LBL,
)

add_initial("b1_init", 72, 1418, 28)

add_state(
    "s_sched_wait",
    145,
    1300,
    580,
    270,
    "生产定时待命中（默认无头模式）",
    [
        "do / 正式上线后：由轻量系统定时任务每周自动唤醒（无需启动任何图形界面或网页看板）",
        "do / 仅调试验收期：按需临时启动 LangGraph Studio 图形界面手动点跑与单步查白板，调完即关",
        "说明 / 与董事长个人微信助理网页看板彻底解耦，互不阻塞",
    ],
    "idle",
)

add_state(
    "s_sched_fire",
    1045,
    1300,
    605,
    270,
    "派发周期分析批次",
    [
        "entry / 检查是否已有同批次在途任务，避免并发重复执行",
        "do / 生产模式：直接无头拉起主状态机「读资料 → 算账挑刺 → 渲染 PDF 发邮件」",
        "do / 调试模式（可选）：支持开启干跑预览（只出本地 PDF 不发邮件）与单步检查点回放",
    ],
    "code",
)

add_transition(
    "e_b1_init",
    "b1_init",
    "s_sched_wait",
    "",
    C_ERR,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
)
add_transition(
    "e_b1_fire",
    "s_sched_wait",
    "s_sched_fire",
    "每周定时到达（生产）或 调试期手动点跑\n[无同周期在途批次]",
    C_MAIN,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-24,
)
add_transition(
    "e_b1_back",
    "s_sched_fire",
    "s_sched_wait",
    "批次拉起完成 / 回归待命等待下周期",
    C_ERR,
    exit_xy=(0.5, 1.0),
    entry_xy=(0.5, 1.0),
    points=[(1347, 1618), (435, 1618)],
    label_offset_y=16,
)

add_note(
    "note_b1",
    145,
    1668,
    1505,
    198,
    "架构边界声明（对照 07 / 08 / 09 / ADP 规范 · 生产轻量化运行）",
    [
        "1. 生产期零重型依赖：调试完毕上线后，不跑 LangGraph Studio、不跑三屏监控大盘、不集成微信看板；每周定时直接读资料、算账挑刺、生成预警 PDF 经赛博狮鹫发邮箱。",
        "2. 合规升级 Ch.4 独立红队反思：每周低频高价值经营审计引入独立红队核账挑刺官，100% 共享原始桌面与翻查证据（零传话断层），先核各目标投入硬账再发 6 要素 Alert。",
        "3. 双重有界与降级送达：翻查上限死锁 [翻查次数 < 18]（可配置）；证据纠偏死锁 [纠偏次数 < 2]，次要存疑仅标灰剔除绝不误拦整份预警邮件。",
        "4. 采集严格二分 + 稀疏四层配置：首次全量与后续增量显式分流；四层目标 JSON 空层自动跳过，精确考勤口径由底盘 100% 确定性核算。",
    ],
)

# --- Sub-Region B2: Debug-Only Observability & LLM Context Monitoring Hub ---
add_text(
    "reg_b2_lbl",
    1760,
    1235,
    2900,
    30,
    "正交区域 B2｜可观测性与 LLM 上下文监控（默认关闭 · 仅调试期按需开启多屏大盘，生产期只留极简本地运行日志）",
    S_REGION_LBL,
)

add_initial("b2_init", 1768, 1418, 28)

add_state(
    "s_obs_cap",
    1845,
    1295,
    920,
    285,
    "运行模式遥测开关与密钥脱敏",
    [
        "entry / 读取调试大盘开关，启动敏感凭据脱敏护栏（屏蔽全部模型密钥、企微密钥与邮箱授权码）",
        "do / 【正式生产模式（开关关闭 · 默认）】：不连接任何大盘容器，仅本地落盘极简运行日志（耗时、Token 成本、告警条数与发信回执），零资源开销",
        "do / 【调试验收模式（开关开启）】：全量捕获主脑翻查上下文、思考链、红队挑刺对话与核验报错，脱敏后推送至监控大盘",
    ],
    "tool",
)

add_choice("c_obs_mode", 2875, 1416, 44)  # center (2897, 1438)

add_state(
    "s_obs_ui",
    3235,
    1295,
    1425,
    285,
    "调试期多屏联动上下文监控大盘（生产期关闭不启动）",
    [
        "do / 仅在开发调优与 Prompt 验收阶段开启，复用现有 agentic_observability_hub 双栈观测中心：",
        "do / • 屏幕 1 · 实时拓扑与上下文显微镜（:8765）：高亮节点流转，逐字对比主脑初稿 vs 红队挑刺新增了哪些 Alert 与完整思考链",
        "do / • 屏幕 2 · Langfuse（:3000）+ 屏幕 3 · Phoenix（:6006）：十万字上下文检索、提示词版本对照与 Token 成本核查",
        "exit / 调试验收通过后一键关闭开关并停掉监控容器，切回生产极简无头模式",
    ],
    "llm",
)

add_transition(
    "e_b2_init",
    "b2_init",
    "s_obs_cap",
    "",
    C_TOOL,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
)
add_transition(
    "e_b2_c",
    "s_obs_cap",
    "c_obs_mode",
    "模式\n判定",
    C_TOOL,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-24,
)
add_transition(
    "e_b2_push",
    "c_obs_mode",
    "s_obs_ui",
    "[调试期大盘开关=开启]\n/ 脱敏推送完整 LLM 上下文",
    C_BRAIN,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-30,
)
add_transition(
    "e_b2_prod",
    "c_obs_mode",
    "s_obs_cap",
    "[else：正式生产模式（大盘关闭）] / 仅写极简本地日志，不启动大盘",
    C_ERR,
    exit_xy=(0.5, 1.0),
    entry_xy=(0.5, 1.0),
    points=[(2897, 1622), (2305, 1622)],
    label_offset_y=16,
)
add_transition(
    "e_b2_back",
    "s_obs_ui",
    "s_obs_cap",
    "调试批次归档 / 等待下次调试运行",
    C_ERR,
    exit_xy=(0.5, 1.0),
    entry_xy=(0.25, 1.0),
    points=[(3947, 1648), (2075, 1648)],
    label_offset_y=14,
)

add_note(
    "note_b2",
    1845,
    1678,
    2815,
    190,
    "开发调试期 vs 正式生产期清晰分离（既看得透黑匣子，又保证线上跑得轻快省心）",
    [
        "• 开发调试期（按需开启）：打开 LangGraph Studio 图形界面 + 监控大盘开关（:8765 / :3000 / :6006），把主脑 18 轮翻查、目标投入算账、红队 8 大漏洞挑刺的每一字 Prompt 与上下文看得一清二楚，调到报告质量 100% 满意。",
        "• 正式生产期（默认极简无头）：一键关闭调试大盘与 Studio，系统每周定时直接无头执行「增量同步 → 读目标与历史库 → 算账挑刺 → 渲染预警 PDF → 赛博狮鹫发邮件」，不依赖任何前端服务或 Docker 监控栈，稳定零负担。",
    ],
)


# ==============================================================================
# ASSEMBLE & WRITE .drawio XML
# ==============================================================================
xml_doc = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<mxfile host="app.diagrams.net" modified="2026-11-28T00:48:00.000Z" '
    'agent="Antigravity-UML25-Generator" version="24.7.17" type="device">\n'
    '  <diagram id="wecom-ops-uml25-v2" name="OMG-UML-2.5-状态机架构图">\n'
    f'    <mxGraphModel dx="1600" dy="960" grid="1" gridSize="10" guides="1" tooltips="1" '
    f'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{PAGE_W}" '
    f'pageHeight="{PAGE_H}" math="0" shadow="0" background="#ffffff">\n'
    "      <root>\n"
    '        <mxCell id="0"/>\n'
    '        <mxCell id="1" parent="0"/>\n'
    + "\n".join(f"        {c}" for c in cells)
    + "\n      </root>\n"
    "    </mxGraphModel>\n"
    "  </diagram>\n"
    "</mxfile>\n"
)

OUT_PATH.write_text(xml_doc, encoding="utf-8")
print(f"Wrote UML 2.5 Draw.io diagram: {OUT_PATH} ({len(cells)} cells, {len(xml_doc):,} bytes)")
