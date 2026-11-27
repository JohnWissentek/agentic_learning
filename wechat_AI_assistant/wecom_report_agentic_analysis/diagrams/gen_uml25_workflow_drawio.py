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
    2400,
    42,
    "维恩科仪周度经营漏洞预警与 AI 提效智能体 — OMG UML 2.5 行为状态机架构图（V2.3 方案 B · 独立红队挑刺 + 分级预警版）",
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
    "维恩科仪周度经营漏洞预警与 AI 提效智能体系统 V2.3（独立运行 · 不集成网页看板 · 含两个并发正交区域）",
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
    395,
    325,
    320,
    "核算四期趋势与装配桌面",
    [
        "entry / 读取四层战略目标配置文件（长期 / 年度 / 季度 / 月度）并生成日历锚点表",
        "do / 纯代码精确核算四层滚动趋势硬矩阵：自今日往前推【近1月 / 近1季 / 近1年 / 全量长期】提交率、负荷、出差与高成本研发占比曲线",
        "do / 只读装配公司 15 人花名册、董事长在途任务快照与历次月度/季度归档摘要",
        "exit / 为近 30 天汇报全文分配短编号（R-001起）并包裹不可信外部数据物理围栏",
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
    1890 + DX1,
    395,
    325,
    320,
    "旗舰主脑生成诊断初稿",
    [
        "entry / 撤掉工具查证权限，锁定桌面上已集齐的全部四期证据与翻查事实",
        "do / 闭卷生成诊断初稿：梳理全公司核心任务还原、四层目标向好/偏离轨迹、高成本研发精力去向、董事长盲区空转项与 AI 提效机会",
        "exit / 将结构化诊断初稿写入共享白板，移交独立红队挑刺复核",
    ],
    "llm",
)


# ==============================================================================
# STAGE 3 (Scheme B): Independent Red-Team Loophole Critic + Evidence Check & Alert Grading
# ==============================================================================
add_container(
    "stg3",
    2095 + DX2,
    205,
    1025,
    975,
    "阶段三（方案 B）：独立红队漏洞挑刺复核 + 证据真实性核验与 Alert 分级定档",
    S_STAGE_REDTEAM,
)

add_state(
    "s_redteam",
    2120 + DX2,
    395,
    340,
    320,
    "独立红队漏洞挑刺复核",
    [
        "entry / 100% 共享完整四层目标、四期硬统计、围栏内近30天汇报、翻查事实、阶段二初稿及（若有）证据纠偏清单（零传话断层）",
        "do / 唤醒独立红队复核大模型（严禁和稀泥）：专揪阶段二漏掉的管理漏洞、报喜不报忧、高成本研发稀释、零汇报黑箱、停滞任务与国产化/渠道化缺位",
        "do / 为每条漏洞输出明确的 Alert 预警级别（高危红警 / 偏离黄警 / 提效蓝提示）与董事长可直接拍板的硬建议",
        "exit / 输出漏洞预警增强版最终报告，并将全量挑刺思考链推送监控大盘",
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

# --- Sub-Region B1: Periodic Schedule & Studio Manual Trigger ---
add_text(
    "reg_b1_lbl",
    64,
    1235,
    1600,
    30,
    "正交区域 B1｜定期调度与图形界面触发（每周自动运行 + 图形界面随点随跑）",
    S_REGION_LBL,
)

add_initial("b1_init", 72, 1418, 28)

add_state(
    "s_sched_wait",
    145,
    1300,
    580,
    270,
    "定时与图形界面待命中",
    [
        "do / 常驻等待每周五 18:00 定时时钟信号（以当日为锚点滚算月/季/年/长期四维对比）",
        "do / 同时支持在图形工作台（LangGraph Studio）指定任意分析基准日手动点击启动",
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
        "do / 锁定本次分析基准日与独立线程存盘编号，拉起正交区域 A 主状态机",
        "exit / 若在图形界面运行，则支持中途单步查看状态白板与检查点重放",
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
    "每周五 18:00 或 人工点击启动\n[无同周期在途批次]",
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
    "架构边界声明（对照 07 / 08 / 09 / ADP 规范，经董事长拍板启用方案 B 红队挑刺）",
    [
        "1. 彻底独立交付：不集成至微信助理网页看板、不向董事长发微信确认卡、严禁改写董事长个人任务主表（仅严格只读比对）。",
        "2. 合规升级 Ch.4 独立红队反思：本项目属低频高价值周度经营审计（每周仅 1 次），经董事长确认引入独立红队漏洞复核官，100% 共享原始桌面与翻查证据（零传话断层），专揪隐性漏洞发 Alert。",
        "3. 双重有界与降级送达：翻查上限死锁 [翻查次数 < 18]（可配置，超限转初稿）；证据纠偏死锁 [纠偏次数 < 2]，次要存疑仅标灰剔除绝不误拦整份预警邮件。",
        "4. 采集严格二分 + 配置外置：首次全量历史拉取与后续增量拉取显式分流；长期/年度/季度/月度四层战略目标统一收口至独立 JSON 配置文件，随时增补细节。",
    ],
)

# --- Sub-Region B2: Full-Chain Observability & LLM Context Monitoring Hub ---
add_text(
    "reg_b2_lbl",
    1760,
    1235,
    2850,
    30,
    "正交区域 B2｜全链路可观测性与 LLM 上下文监控大盘（复用现有双栈观测中心 · 完整透视主脑翻查与红队挑刺全量上下文）",
    S_REGION_LBL,
)

add_initial("b2_init", 1768, 1418, 28)

add_state(
    "s_obs_cap",
    1845,
    1295,
    1200,
    285,
    "全链路遥测采集与密钥脱敏",
    [
        "entry / 启动敏感凭据脱敏护栏，自动将全部大模型密钥、企微密钥与邮箱授权码掩码替换，确保大盘零泄密",
        "do / 无侵入监听主状态机全过程：捕获主脑每轮研判上下文与翻查工具问答、初稿生成、独立红队挑刺官的完整提示词与犀利思考链、证据核验报错与 Token 消耗",
        "exit / 绑定单次运行唯一追踪编号，单次采集同时双路扇出推送至三大可视化大盘",
    ],
    "tool",
)

add_state(
    "s_obs_ui",
    3310,
    1295,
    1350,
    285,
    "多屏联动实时监控大盘呈现",
    [
        "do / 屏幕 1 · 实时拓扑与上下文显微镜（本地 :8765）：左侧实时高亮主脑翻查与红队挑刺节点流转，右侧逐字对比主脑初稿 vs 红队挑刺新增了哪些 Alert 漏洞与思考过程",
        "do / 屏幕 2 · 企业级轨迹分析平台（Langfuse :3000）：完整调用火焰树、十万字上下文检索、历次周报提示词版本对比与 Token 成本趋势",
        "do / 屏幕 3 · 轻量轨迹对照（Phoenix :6006）+ 图形执行工作台（LangGraph Studio）：支持图形化点击执行、逐节点白板快照审阅与历史运行回放",
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
    "e_b2_push",
    "s_obs_cap",
    "s_obs_ui",
    "每产生节点或对话事件\n/ 脱敏后实时双路推送",
    C_TOOL,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-24,
)
add_transition(
    "e_b2_back",
    "s_obs_ui",
    "s_obs_cap",
    "本轮运行轨迹归档落盘 / 持续监听下一批次运行",
    C_ERR,
    exit_xy=(0.5, 1.0),
    entry_xy=(0.5, 1.0),
    points=[(3985, 1622), (2445, 1622)],
    label_offset_y=16,
)

add_note(
    "note_b2",
    1845,
    1668,
    2815,
    198,
    "为什么这套「主脑翻查 + 独立红队挑刺 + 三屏大盘」组合能把公司隐藏漏洞挖得最透？",
    [
        "• 主脑负责“全面盘点” + 红队负责“专挑毛病发预警”：主脑通读全量四期数据还原全貌；独立红队复核官带着四层目标与 100% 原始证据专门挑主脑的刺，挖出报喜不报忧、高成本研发稀释、渠道/国产化缺位等隐性漏洞并强制分级出 Alert。",
        "• 全量上下文显微镜（复用现有 agentic_observability_hub）：在本地实时画布（:8765）和 Langfuse（:3000）中，董事长可随时点开看到主脑与红队两轮完整对话上下文，一眼看清红队是怎么把藏在员工日常汇报里的漏洞抓出来的。",
        "• 确定性底盘防误报不误拦：轻量证据核验确保每条 Alert 都有真实员工汇报编号撑腰（绝不冤枉人），遇到次要存疑项自动标灰剔除而不拒发整份预警 PDF，确保每周五关键预警必达董事长邮箱。",
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
