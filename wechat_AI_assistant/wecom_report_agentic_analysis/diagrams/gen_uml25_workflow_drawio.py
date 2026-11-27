"""Generate the strict OMG UML 2.5 Behavioral State Machine Diagram (.drawio)
for `wecom_report_agentic_analysis` V2.1 (Standalone Weekly PDF + Cyber Griffin Email
+ 4-Tier Rolling Horizon Goals + Explicit Full-Backfill vs Incremental Sync Branch).

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
DX = 460
PAGE_W, PAGE_H = 3600 + DX, 1940

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
S_STAGE_AMBER = (
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
    2100,
    42,
    "维恩科仪周度经营对齐与 AI 提效智能体 — OMG UML 2.5 行为状态机架构图（V2.1 四层目标 · 首次全量+后续增量版）",
    S_TITLE,
)
add_text(
    "subtitle",
    40,
    64,
    2200,
    30,
    "严格遵循 OMG UML 2.5 状态机标准与大模型优先架构（07/08/09/ADP）：● 初始伪状态  ◉ 终止状态  圆角框=状态（entry/do/exit）  ◇ 动态分流  实线=事件[监护条件]/动作  虚线=正交并发区",
    S_SUBTITLE,
)

add_initial("lg_init", 1960 + DX, 36, 22)
add_text("lg_init_t", 1988 + DX, 28, 92, 38, "初始伪状态", S_LEGEND_TXT)
add_final("lg_fin", 2092 + DX, 34, 26)
add_text("lg_fin_t", 2124 + DX, 28, 82, 38, "终止状态", S_LEGEND_TXT)
add_choice("lg_ch", 2218 + DX, 32, 30)
add_text("lg_ch_t", 2254 + DX, 28, 92, 38, "选择伪状态", S_LEGEND_TXT)

add_state("lg_code", 2380 + DX, 18, 165, 74, "确定性底盘状态", ["do / 0模型事实与安全"], "code")
add_state("lg_llm", 2560 + DX, 18, 165, 74, "唯一旗舰大脑", ["do / 深度推理与收敛"], "llm")
add_state("lg_tool", 2740 + DX, 18, 165, 74, "只读查证车间", ["do / 4项只读查证工具"], "tool")
add_state("lg_ver", 2920 + DX, 18, 165, 74, "客观验钞门禁", ["do / 100%硬账核验"], "verify")
add_state("lg_com", 3100 + DX, 18, 175, 74, "归档与邮件投递", ["do / PDF排版与发信"], "commit")
add_note(
    "lg_note",
    3290 + DX,
    18,
    270,
    74,
    "去看板集成 · 独立闭环",
    ["每周定期或图形界面触发，直出 PDF 附件经赛博狮鹫邮箱投递。"],
)


# ==============================================================================
# 1. TOP-LEVEL COMPOSITE STATE CONTAINER (2 Orthogonal Regions)
# ==============================================================================
add_container(
    "sys_root",
    40,
    112,
    3520 + DX,
    1790,
    "维恩科仪周度经营战略对齐与 AI 提效智能体系统 V2.1（独立运行 · 不集成网页看板 · 含两个并发正交区域）",
    S_COMPOSITE_ROOT,
)

add_text(
    "reg_a_lbl",
    64,
    160,
    3400,
    30,
    "正交区域 A｜周度经营分析与 PDF 邮件投递主状态机（首次全量 / 后续增量显式分流 + 单脑旗舰四周期推理 + 有界查证 ≤6 步 + 客观验钞 ≤2 轮）",
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
    920 + DX,
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
# STAGE 2: Flagship Brain Reasoning & Bounded Read-Only ReAct Loop
# ==============================================================================
add_container(
    "stg2",
    1140 + DX,
    205,
    820,
    975,
    "阶段二：旗舰大脑深度推理与有界查证乒乓球环（Model-First + ReAct）",
    S_STAGE_PURPLE,
)

add_state(
    "s_brain",
    1170 + DX,
    395,
    360,
    320,
    "旗舰大脑多周期深度推理",
    [
        "entry / 读取共享白板：四层目标、四期滚动趋势矩阵、围栏内近30天汇报、工具查证事实及验钞报错",
        "do / 唤醒唯一旗舰推理大模型（开启深度思考）：分别对照【月/季/年/长期】四层目标评估是否持续向好，还原核心任务、穿透审计高成本研发并识别 AI 提效替代靶点",
        "do / 遇跨季/跨年异常拐点时开具只读查证点菜单；证据齐备则直接输出强类型结构化诊断契约",
        "exit / 查证步数 +1，全量思考链与输入输出推送至监控大盘",
    ],
    "llm",
)

add_choice("c_react", 1790 + DX, 533, 44)  # center (1812 + DX, 555)

add_state(
    "s_tools",
    1170 + DX,
    835,
    450,
    315,
    "只读查证工具车间（仅 4 项只读工具）",
    [
        "entry / 校验工具白名单与严格只读权限（严禁写库或外发消息）",
        "do / 工具 1 · 查历次审计摘要：对比近月/近季/近年的整改落实与对齐分演进轨迹",
        "do / 工具 2 · 回溯全量历史汇报原文：按员工、产品线或客户精准下钻任意历史窗口原件",
        "do / 工具 3 · 查关键员工与董事长任务详情：拉取重点人员或董事长在途任务完整进展流水",
        "do / 工具 4 · 精确日期与占比计算器：确定性计算跨度天数与环比变化，杜绝心算误差",
        "exit / 将真实查证结果（含外部围栏）贴回共享白板，出错时保留原文不崩溃",
    ],
    "tool",
)


# ==============================================================================
# STAGE 3: Deterministic Verification Harness & Bounded Correction Loop
# ==============================================================================
add_container(
    "stg3",
    2095 + DX,
    205,
    625,
    975,
    "阶段三：确定性客观验钞门禁（Verification Loop）",
    S_STAGE_AMBER,
)

add_state(
    "s_verify",
    2125 + DX,
    395,
    360,
    320,
    "确定性客观验钞与编号回填",
    [
        "entry / 强类型结构契约校验：检查必填字段、枚举范围与四期演进判定灯号",
        "do / 硬账 1 · 零幻觉溯源：校验全部汇报短编号（R-xxx）与董事长任务号 100% 真实存在",
        "do / 硬账 2 · 数学与覆盖度：校验日期跨度成立、月/季/年/长期四层目标全覆盖、高成本研发精力占比和为 100%",
        "do / 硬账 3 · 展示净化：检查董事长执行摘要零内部代码术语、零重复一级标题",
        "exit / 全部通过则自动把短编号回填为真实汇报唯一编号；否则生成逐条精确报错清单",
    ],
    "verify",
)

add_choice("c_verify", 2610 + DX, 533, 44)  # center (2632 + DX, 555)

add_final("f_verify_fail", 2615 + DX, 1020, 34)


# ==============================================================================
# STAGE 4: Archive, Executive PDF Rendering & Cyber Griffin Email Delivery
# ==============================================================================
add_container(
    "stg4",
    2870 + DX,
    205,
    665,
    975,
    "阶段四：归档、PDF 排版与赛博狮鹫邮件投递（0% 大模型）",
    S_STAGE_ORANGE,
)

add_state(
    "s_deliver",
    2900 + DX,
    395,
    365,
    320,
    "归档、PDF 渲染与邮件投递",
    [
        "entry / 单事务原子写入周度审计档案库（绝不修改董事长任务主表），检查本周期防重发幂等锁",
        "do / 确定性排版生成高管级 PDF 经营诊断周报（含四层目标健康灯、跨周期趋势图与一页纸决策摘要），校验页数非空与中文字体正常",
        "do / 经由赛博狮鹫专属发件邮箱发送邮件给董事长，正文附精炼核心结论，完整 PDF 报告作为附件投递（带超时与有界重试）",
        "exit / 留存本地 PDF 归档副本、写入邮件投递回执并闭合本轮监控轨迹",
    ],
    "commit",
)

add_choice("c_deliver", 3365 + DX, 533, 44)  # center (3387 + DX, 555)

add_final("f_done", 3020 + DX, 1020, 34)
add_final("f_deliver_err", 3368 + DX, 1020, 34)


# ==============================================================================
# TRANSITIONS IN REGION A (Strict UML 2.5: trigger [guard] / effect)
# ==============================================================================

# 0. Initial -> Stage 1 Check Watermark (clean, unguarded per UML 2.5!)
add_transition(
    "e_init",
    "top_init",
    "s_check_wm",
    "/ 初始化白板\n(步数=0, 纠偏=0)",
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

# 5. Desktop Context -> Flagship Brain
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

# 6. Flagship Brain -> ReAct Gatekeeper Choice
add_transition(
    "e_brain_c",
    "s_brain",
    "c_react",
    "完成本轮大脑输出",
    C_BRAIN,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-18,
)

# 7. ReAct Choice -> Read-Only ToolNode (Bounded Loop <= 6 steps)
add_transition(
    "e_react_tool",
    "c_react",
    "s_tools",
    "[含查证点菜单 且 查证步数 < 6]\n/ 放行执行只读查证工具",
    C_TOOL,
    exit_xy=(0.5, 1.0),
    entry_xy=(1.0, 0.5),
    points=[(1812 + DX, 992)],
    label_pos=-0.25,
    label_offset_x=-10,
    label_offset_y=-24,
)

# 8. ToolNode -> Flagship Brain (Ping-Pong Return Edge)
add_transition(
    "e_tool_brain",
    "s_tools",
    "s_brain",
    "只读查证完毕 / 贴回围栏事实再次唤醒大脑",
    C_TOOL,
    exit_xy=(0.45, 0.0),
    entry_xy=(0.56, 1.0),
    label_pos=0.0,
    label_offset_x=140,
    label_offset_y=0,
)

# 9. ReAct Choice -> Verification (Normal Completion)
add_transition(
    "e_react_done",
    "c_react",
    "s_verify",
    "[不含点菜单（信息齐备已交卷）]\n/ 提交结构化诊断报告",
    C_VERIFY,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-32,
)

# 10. ReAct Choice -> Verification (Step-Cap Escape, sky-lane y=342)
add_transition(
    "e_react_cap",
    "c_react",
    "s_verify",
    "[else：查证步数 >= 6 触发上限熔断] / 停止查证并按现有证据强制收敛",
    C_LOOP,
    exit_xy=(0.5, 0.0),
    entry_xy=(0.35, 0.0),
    points=[(1812 + DX, 342), (2251 + DX, 342)],
    label_pos=-0.05,
    label_offset_y=-16,
)

# 11. Verification -> Verify Choice
add_transition(
    "e_ver_c",
    "s_verify",
    "c_verify",
    "客观验钞\n完成",
    C_VERIFY,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-28,
)

# 12. Verify Choice -> Flagship Brain (Bounded Correction Loop <= 2 retries, sky-lane y=284)
add_transition(
    "e_ver_retry",
    "c_verify",
    "s_brain",
    "[验钞未通过 且 纠偏次数 < 2] / 纠偏次数 +1 并携带逐条客观报错退回大脑定向修正",
    C_LOOP,
    exit_xy=(0.5, 0.0),
    entry_xy=(0.5, 0.0),
    points=[(2632 + DX, 284), (1350 + DX, 284)],
    label_pos=0.0,
    label_offset_y=-16,
    width=2.5,
)

# 13. Verify Choice -> Deliver (Pass)
add_transition(
    "e_ver_ok",
    "c_verify",
    "s_deliver",
    "[全部客观硬校验通过]\n/ 准予归档与投递",
    C_COMMIT,
    exit_xy=(1.0, 0.5),
    entry_xy=(0.0, 0.5),
    label_offset_y=-32,
)

# 14. Verify Choice -> Verify Fail Final (Circuit Breaker >= 2)
add_transition(
    "e_ver_fail",
    "c_verify",
    "f_verify_fail",
    "[else：纠偏次数 >= 2 触发质量熔断]\n/ 拒发 PDF 邮件，保留硬统计草稿并告警人工",
    C_LOOP,
    exit_xy=(0.5, 1.0),
    entry_xy=(0.5, 0.0),
    label_pos=0.0,
    label_offset_x=-145,
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
    "[PDF 渲染与赛博狮鹫发信成功 或 已幂等去重]\n/ 完成本周期分析与报告投递",
    C_TOOL,
    exit_xy=(0.5, 1.0),
    entry_xy=(0.5, 0.0),
    points=[(3387 + DX, 825), (3037 + DX, 825)],
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
add_line("ortho_h", 56, 1212, 3488 + DX, 4, S_ORTHO_H)
add_line("ortho_v", 1560, 1232, 4, 650, S_ORTHO_V)

# --- Sub-Region B1: Periodic Schedule & Studio Manual Trigger ---
add_text(
    "reg_b1_lbl",
    64,
    1235,
    1440,
    30,
    "正交区域 B1｜定期调度与图形界面触发（每周自动运行 + 图形界面随点随跑）",
    S_REGION_LBL,
)

add_initial("b1_init", 72, 1418, 28)

add_state(
    "s_sched_wait",
    145,
    1300,
    520,
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
    955,
    1300,
    545,
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
    points=[(1227, 1618), (405, 1618)],
    label_offset_y=16,
)

add_note(
    "note_b1",
    145,
    1668,
    1355,
    198,
    "架构边界声明（对照 07 / 08 / 09 与生产级交付宪章）",
    [
        "1. 彻底独立交付：不集成至微信助理网页看板、不向董事长发微信确认卡、严禁改写董事长个人任务主表（仅严格只读比对）。",
        "2. 单脑克制（够用即止）：0 次小模型路由器、0 次二审打架大模型、0 条解析中文口语的脆弱正则；仅配备 4 项只读查证工具（远低于 12 工具上限）。",
        "3. 双重有界熔断证明：ReAct 查证环死锁 [查证步数 < 6]，客观验钞纠偏环死锁 [纠偏次数 < 2]，每条环路均有明确逃生出口，绝无死循环与费用失控。",
        "4. 采集严格二分 + 配置外置：首次全量历史拉取与后续增量拉取显式分流互不混杂；四层战略目标统一收口至独立 JSON 配置文件，随时可增补细节。",
    ],
)

# --- Sub-Region B2: Full-Chain Observability & LLM Context Monitoring Hub ---
add_text(
    "reg_b2_lbl",
    1600,
    1235,
    2350,
    30,
    "正交区域 B2｜全链路可观测性与 LLM 上下文监控大盘（复用现有双栈观测中心 · 完整透视每轮提示词、上下文与思考链）",
    S_REGION_LBL,
)

add_initial("b2_init", 1608, 1418, 28)

add_state(
    "s_obs_cap",
    1685,
    1295,
    940,
    285,
    "全链路遥测采集与密钥脱敏",
    [
        "entry / 启动敏感凭据脱敏护栏，自动将全部大模型密钥、企微密钥与邮箱授权码掩码替换，确保大盘零泄密",
        "do / 无侵入监听主状态机全过程：捕获每次节点进入/退出、发给大模型的完整系统提示词与四期桌面上下文、大模型深度思考链、每次只读查证工具的入参与返回原文、客观验钞报错明细与 Token 消耗",
        "exit / 绑定单次运行唯一追踪编号，单次采集同时双路扇出推送至三大可视化大盘",
    ],
    "tool",
)

add_state(
    "s_obs_ui",
    2890,
    1295,
    1100,
    285,
    "多屏联动实时监控大盘呈现",
    [
        "do / 屏幕 1 · 实时拓扑与上下文显微镜（本地 :8765）：左侧实时高亮当前执行节点与循环路径，右侧逐字审阅完整未截断的输入上下文、思考链与回复",
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
    points=[(3440, 1622), (2155, 1622)],
    label_offset_y=16,
)

add_note(
    "note_b2",
    1685,
    1668,
    2305,
    198,
    "为什么这套方案同时满足「图形界面执行」与「完整 LLM 上下文监控」？",
    [
        "• 图形界面执行与调试（LangGraph Studio）：主状态机基于标准 LangGraph 状态图编译并暴露配置文件，启动后直接在浏览器图形界面看到完整节点拓扑，点击按钮即可触发分析，并可查看任意节点的实时共享白板状态。",
        "• 全量上下文显微镜（复用现有 agentic_observability_hub）：运行期间每次与大模型的完整对话（系统指令 + 四层目标 + 四期硬趋势 + 围栏内汇报 + 查证工具问答 + 深度思考链 + 验钞退回重修前后对比）100% 无截断送入本地实时画布（:8765）与 Langfuse（:3000），支持事后随时复盘与零成本回放。",
        "• 生产级确定性护栏：首次全量与后续增量显式分流、短编号防幻觉回填、日期跨度与研发占比数学对账、展示层去技术黑话检查、PDF 完整性核验、同周期防重发幂等锁，全部由确定性底盘刚性兜底。",
    ],
)


# ==============================================================================
# ASSEMBLE & WRITE .drawio XML
# ==============================================================================
xml_doc = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<mxfile host="app.diagrams.net" modified="2026-11-27T23:05:00.000Z" '
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
