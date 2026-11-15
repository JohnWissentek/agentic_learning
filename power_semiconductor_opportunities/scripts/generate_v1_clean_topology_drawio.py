#!/usr/bin/env python3
"""Generate Clean, Uncluttered V1.0 Orchestration Topology Diagram (Bounded Cyclic StateGraph).

Separates pure control-flow topology (Left spine + parallel fan-out + bounded Critic loops)
from Context Assembly payload details (Decoupled Right Reference Sidebar), writing:
- `docs/04_V1_CLEAN_TOPOLOGY_DAG.drawio`
- `outputs/power_semiconductor_online_testing_2026_2036/09_V1_CLEAN_TOPOLOGY_DAG.drawio`
"""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from generate_a0_workflow_drawio import (
    STYLES,
    EdgeRoute,
    RectBox,
    _mid_bot,
    _mid_left,
    _mid_right,
    _mid_top,
    estimate_wrapped_height,
)

BASE_DIR = Path("/Users/john/Desktop/agentic_learning/power_semiconductor_opportunities")
DOCS_OUT = BASE_DIR / "docs/04_V1_CLEAN_TOPOLOGY_DAG.drawio"
RUN_OUT = (
    BASE_DIR
    / "outputs/power_semiconductor_online_testing_2026_2036/09_V1_CLEAN_TOPOLOGY_DAG.drawio"
)

CANVAS_W = 2800
CANVAS_H = 2040


class CleanDiagramBuilder:
    def __init__(self, width: int = CANVAS_W, height: int = CANVAS_H) -> None:
        self.width = width
        self.height = height
        self._id_counter = 10
        self.bg_cells: list[ET.Element] = []
        self.fg_cells: list[ET.Element] = []
        self.edge_cells: list[ET.Element] = []
        self.boxes: dict[str, RectBox] = {}
        self.edges: list[EdgeRoute] = []

    def next_id(self, prefix: str = "c") -> str:
        self._id_counter += 1
        return f"{prefix}_{self._id_counter}"

    def add_band(self, x: int, y: int, w: int, h: int, title: str, accent: str = "#334155") -> None:
        bid = self.next_id("band")
        frame = ET.Element(
            "mxCell",
            {
                "id": bid,
                "value": "",
                "style": (
                    "rounded=1;arcSize=2;whiteSpace=wrap;html=0;fillColor=#FFFFFF;"
                    "strokeColor=#CBD5E1;strokeWidth=2;shadow=0;"
                ),
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(
            frame,
            "mxGeometry",
            {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"},
        )
        self.bg_cells.append(frame)

        rid = self.next_id("ribbon")
        ribbon = ET.Element(
            "mxCell",
            {
                "id": rid,
                "value": title,
                "style": (
                    f"rounded=1;arcSize=4;whiteSpace=wrap;html=0;fillColor={accent};"
                    f"strokeColor={accent};fontColor=#FFFFFF;fontStyle=1;fontSize=15;"
                    "align=left;verticalAlign=middle;spacingLeft=14;spacingRight=12;overflow=hidden;"
                ),
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(
            ribbon,
            "mxGeometry",
            {"x": str(x + 12), "y": str(y + 8), "width": str(w - 24), "height": "32", "as": "geometry"},
        )
        self.bg_cells.append(ribbon)

    def add_card(
        self,
        key: str,
        kind: str,
        x: int,
        y: int,
        w: int,
        h: int,
        title: str,
        body: str,
        *,
        hdr_h: int = 38,
        hdr_font: int = 15,
        body_font: int = 14,
        dashed_body: bool = False,
    ) -> str:
        st = STYLES[kind]
        t_lines, t_need = estimate_wrapped_height(title, w, hdr_font, pad_lr=24, pad_tb=8, line_mult=1.22)
        if t_need > hdr_h:
            raise AssertionError(
                f"Header overflow `{key}`: need {t_need}px ({t_lines}L) > hdr_h={hdr_h} | {title!r}"
            )
        body_h = h - hdr_h
        b_lines, b_need = estimate_wrapped_height(body, w, body_font, pad_lr=28, pad_tb=16, line_mult=1.34)
        if b_need > body_h:
            raise AssertionError(
                f"Body overflow `{key}`: need {b_need}px ({b_lines}L) > body_h={body_h} | {key}"
            )

        outline_id = f"node_{key}"
        dash_css = "dashed=1;dashPattern=6 4;" if dashed_body else ""
        outline = ET.Element(
            "mxCell",
            {
                "id": outline_id,
                "value": "",
                "style": (
                    f"rounded=1;arcSize=4;whiteSpace=wrap;html=0;fillColor={st['body_fill']};"
                    f"strokeColor={st['body_stroke']};strokeWidth=2;{dash_css}"
                ),
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(
            outline,
            "mxGeometry",
            {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"},
        )
        self.fg_cells.append(outline)

        hdr = ET.Element(
            "mxCell",
            {
                "id": f"{outline_id}_hdr",
                "value": title,
                "style": (
                    f"rounded=0;whiteSpace=wrap;html=0;fillColor={st['hdr_fill']};"
                    f"strokeColor={st['hdr_stroke']};strokeWidth=1;fontColor={st['hdr_font']};"
                    f"fontStyle=1;fontSize={hdr_font};align=left;verticalAlign=middle;"
                    "spacingLeft=12;spacingRight=10;overflow=hidden;"
                ),
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(
            hdr,
            "mxGeometry",
            {"x": str(x), "y": str(y), "width": str(w), "height": str(hdr_h), "as": "geometry"},
        )
        self.fg_cells.append(hdr)

        bcell = ET.Element(
            "mxCell",
            {
                "id": f"{outline_id}_body",
                "value": body,
                "style": (
                    f"rounded=0;whiteSpace=wrap;html=0;fillColor=none;strokeColor=none;"
                    f"fontColor={st['body_font']};fontSize={body_font};align=left;verticalAlign=top;"
                    "spacingLeft=13;spacingRight=12;spacingTop=8;spacingBottom=8;overflow=hidden;"
                ),
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(
            bcell,
            "mxGeometry",
            {"x": str(x), "y": str(y + hdr_h), "width": str(w), "height": str(body_h), "as": "geometry"},
        )
        self.fg_cells.append(bcell)
        self.boxes[outline_id] = RectBox(outline_id, "card", x, y, w, h)
        return outline_id

    def add_pill(
        self,
        key: str,
        x: int,
        y: int,
        w: int,
        h: int,
        text: str,
        *,
        fill: str = "#FFFFFF",
        stroke: str = "#9F1239",
        font_color: str = "#881337",
        font_size: int = 13,
    ) -> str:
        lines, need = estimate_wrapped_height(text, w, font_size, pad_lr=14, pad_tb=6, line_mult=1.24)
        if need > h:
            raise AssertionError(f"Pill overflow `{key}`: need {need}px ({lines}L) > {h}px | {text!r}")
        pid = f"pill_{key}"
        el = ET.Element(
            "mxCell",
            {
                "id": pid,
                "value": text,
                "style": (
                    f"rounded=1;arcSize=50;whiteSpace=wrap;html=0;fillColor={fill};"
                    f"strokeColor={stroke};strokeWidth=2;fontColor={font_color};"
                    f"fontStyle=1;fontSize={font_size};align=center;verticalAlign=middle;"
                    "spacingLeft=6;spacingRight=6;overflow=hidden;"
                ),
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(
            el,
            "mxGeometry",
            {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"},
        )
        self.fg_cells.append(el)
        self.boxes[pid] = RectBox(pid, "pill", x, y, w, h)
        return pid

    def add_edge(
        self,
        key: str,
        src_id: str,
        dst_id: str,
        points: list[tuple[int, int]],
        *,
        color: str = "#1E3A8A",
        dashed: bool = False,
        stroke_w: float = 2.8,
        end_arrow: str = "classic",
    ) -> None:
        if len(points) < 2:
            raise ValueError(f"Edge `{key}` needs >= 2 points")
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            if x1 != x2 and y1 != y2:
                raise AssertionError(f"Diagonal segment on `{key}`: ({x1},{y1})->({x2},{y2})")
        eid = f"edge_{key}"
        dash_css = "dashed=1;dashPattern=8 5;" if dashed else ""
        end_css = f"endArrow={end_arrow};endFill=1;" if end_arrow != "none" else "endArrow=none;"
        cell = ET.Element(
            "mxCell",
            {
                "id": eid,
                "value": "",
                "style": (
                    f"edgeStyle=none;orthogonalLoop=1;jettySize=auto;html=0;rounded=1;arcSize=8;"
                    f"strokeColor={color};strokeWidth={stroke_w};{dash_css}startArrow=none;{end_css}"
                ),
                "edge": "1",
                "parent": "1",
            },
        )
        geom = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        ET.SubElement(geom, "mxPoint", {"x": str(points[0][0]), "y": str(points[0][1]), "as": "sourcePoint"})
        ET.SubElement(geom, "mxPoint", {"x": str(points[-1][0]), "y": str(points[-1][1]), "as": "targetPoint"})
        if len(points) > 2:
            arr = ET.SubElement(geom, "Array", {"as": "points"})
            for px, py in points[1:-1]:
                ET.SubElement(arr, "mxPoint", {"x": str(px), "y": str(py)})
        self.edge_cells.append(cell)
        self.edges.append(EdgeRoute(eid, src_id, dst_id, points, color, dashed, stroke_w, False))

    def audit_geometry(self) -> None:
        box_list = list(self.boxes.values())
        for b in box_list:
            if b.x < 10 or b.y < 10 or b.x + b.w > self.width - 10 or b.y + b.h > self.height - 10:
                raise AssertionError(f"Box `{b.box_id}` out of bounds ({self.width}x{self.height}): {b}")
        margin = 8
        for i, a in enumerate(box_list):
            for b in box_list[i + 1 :]:
                x_ov = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
                y_ov = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
                if x_ov > -margin and y_ov > -margin:
                    raise AssertionError(f"Box overlap ({x_ov}x{y_ov}): `{a.box_id}` vs `{b.box_id}`")

        pad = 3
        for e in self.edges:
            for seg_idx, ((x1, y1), (x2, y2)) in enumerate(zip(e.points, e.points[1:])):
                sx_lo, sx_hi = min(x1, x2), max(x1, x2)
                sy_lo, sy_hi = min(y1, y2), max(y1, y2)
                mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                for b in box_list:
                    if b.box_id in (e.src_id, e.dst_id):
                        if (b.x + 2 < mx < b.x + b.w - 2) and (b.y + 2 < my < b.y + b.h - 2):
                            raise AssertionError(
                                f"Edge `{e.edge_id}` seg {seg_idx} passes inside own endpoint `{b.box_id}`!"
                            )
                        continue
                    bx_lo, bx_hi = b.x - pad, b.x + b.w + pad
                    by_lo, by_hi = b.y - pad, b.y + b.h + pad
                    if sx_lo == sx_hi:
                        if bx_lo <= sx_lo <= bx_hi and sy_hi > by_lo and sy_lo < by_hi:
                            raise AssertionError(
                                f"Edge `{e.edge_id}` seg {seg_idx} ({x1},{y1})->({x2},{y2}) crosses `{b.box_id}`"
                            )
                    else:
                        if by_lo <= sy_lo <= by_hi and sx_hi > bx_lo and sx_lo < bx_hi:
                            raise AssertionError(
                                f"Edge `{e.edge_id}` seg {seg_idx} ({x1},{y1})->({x2},{y2}) crosses `{b.box_id}`"
                            )

    def build_xml(self, diag_name: str) -> str:
        self.audit_geometry()
        mxfile = ET.Element(
            "mxfile",
            {
                "host": "Antigravity-Agent",
                "modified": "2026-11-15T06:20:00.000Z",
                "agent": "PSO-Workflow-Clean-Topology-Generator",
                "version": "32.6.1",
                "type": "device",
            },
        )
        diagram = ET.SubElement(mxfile, "diagram", {"id": "pso_v1_clean_topology", "name": diag_name})
        model = ET.SubElement(
            diagram,
            "mxGraphModel",
            {
                "dx": "1600",
                "dy": "1100",
                "grid": "1",
                "gridSize": "10",
                "guides": "1",
                "tooltips": "1",
                "connect": "1",
                "arrows": "1",
                "fold": "1",
                "page": "1",
                "pageScale": "1",
                "pageWidth": str(self.width),
                "pageHeight": str(self.height),
                "math": "0",
                "shadow": "0",
                "background": "#F8FAFC",
            },
        )
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", {"id": "0"})
        ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
        for cell in self.bg_cells + self.fg_cells + self.edge_cells:
            root.append(cell)
        ET.indent(mxfile, space="  ")
        return ET.tostring(mxfile, encoding="unicode", xml_declaration=True) + "\n"


def build_diagram() -> tuple[str, int, int]:
    g = CleanDiagramBuilder(CANVAS_W, CANVAS_H)

    # Top Title Banner
    g.add_card(
        "banner",
        "BANNER",
        x=32,
        y=24,
        w=2736,
        h=96,
        hdr_h=38,
        hdr_font=16,
        body_font=14,
        title="V1.0 清爽版智能体编排拓扑图：主干有向推进 + 尾部受控有界环路 (Bounded Cyclic StateGraph)",
        body=(
            "说明：本图剥离冗长上下文载荷卡片，左侧主图严格呈现控制流骨架、Fan-Out/Join 并发与 Critic 受控闭环 (<= 2 轮)；"
            "右侧独立附表集中展示图例约定、模型实证及 7 处 LLM Context 组装速查，与 A0 详图完全一致。"
        ),
    )

    # Left Main Flow Backdrop Frame + Right Reference Backdrop Frame
    g.add_band(
        x=32,
        y=134,
        w=1850,
        h=1882,
        title="主干控制流拓扑 (Left Spine: Fan-Out / Join 与 Critic <= 2 轮受控闭环)",
        accent="#0F172A",
    )
    g.add_band(
        x=1902,
        y=134,
        w=866,
        h=1882,
        title="解耦附表区 (Decoupled Sidebar: 图论图例 · 模型底座 · Context #1–#7 速查)",
        accent="#B45309",
    )

    # Main vertical spine centered around cx=950
    v0 = g.add_card(
        "v0",
        "STORAGE",
        x=460,
        y=184,
        w=920,
        h=112,
        title="[V0 · 预设静态输入] 研究契约 + 写死 8 赛道与 16 种子",
        body=(
            "• config/research_contract.yaml (中国信源>=45%, >=85分, 四大支柱权重 35/25/20/20)。\n"
            "• config/domain_taxonomy.yaml (写死 P1–P4 / S1–S4 赛道名、固定检索词及 16 项 roi_baseline 种子)。"
        ),
    )
    p_v1_limit = g.add_pill(
        "v1_limit",
        x=1408,
        y=205,
        w=450,
        h=70,
        text="V1.0 核心方法论局限：\n上来预设 8 赛道与 16 种子，偏“验证找证据”，难自下而上发现未知增量",
        fill="#FFF1F2",
        stroke="#E11D48",
        font_color="#9F1239",
        font_size=13,
    )

    v1 = g.add_card(
        "v1",
        "HARDCODED",
        x=430,
        y=336,
        w=980,
        h=126,
        title="[V1 · 硬编码 Python] 双引擎 AI 检索入库 + PALMs 16 项财务预计算",
        body=(
            "• Metaso(CN) + Serper(GL) + r.jina.ai → SQLite EvidenceVault (225 条去重证据, 63.11% CN)。\n"
            "• tools/roi_calculator.py：确定性算出 16 项 CAPEX/Payback/IRR/NPV/TAM（严禁 LLM 心算）。\n"
            "• 执行序差异：模式1 (run_workflow) 因沙箱限网将本步前置到 Phase 1；模式2 (graph.py) 置于 V2 之后。"
        ),
    )

    v2 = g.add_card(
        "v2",
        "LLM_AGENT",
        x=430,
        y=502,
        w=980,
        h=112,
        title="[V2 · LLM #1] Step-Back 物理第一性原理总规划 (+ 可选 HITL 检查点)",
        body=(
            "• 1× LLM 调用 (Context #1)：推演跨行业核心传感物理不变量与 8 赛道失效机理（不注网页噪音）。\n"
            "• 模式2 启用 --hitl 时在此调用 interrupt() 人工审阅后，再按 8 赛道并发扇出。"
        ),
    )

    # Row 3: Fan-out (Power || Semi) -> Join
    v3a = g.add_card(
        "v3a_power",
        "LLM_AGENT",
        x=320,
        y=666,
        w=560,
        h=122,
        title="[V3a · 4× 并行 LLM] 电力能源 P1–P4 + STORM",
        body=(
            "4 路隔离并发 (Context #2)：P1储能固态电池、P2钙钛矿绿氢、\n"
            "P3特高压/SF6替代/海缆、P4调峰CCUS + 4角色买方拷问。"
        ),
    )
    v3b = g.add_card(
        "v3b_semi",
        "LLM_AGENT",
        x=960,
        y=666,
        w=560,
        h=122,
        title="[V3b · 4× 并行 LLM] 半导体 S1–S4 + STORM",
        body=(
            "4 路隔离并发 (Context #2)：S1 Fab AMC湿化、S2 前道OCD/SAXS、\n"
            "S3 碳化硅/氮化镓KGD、S4 混合键合HBM + 4角色买方拷问。"
        ),
    )

    v3j = g.add_card(
        "v3_join",
        "HARDCODED",
        x=430,
        y=822,
        w=980,
        h=106,
        title="[V3 Join · 硬编码 Python] 白名单引用清洗 · 财务重锚定 · 初始 Elo",
        body=(
            "• 丢弃一切不在赛道 valid_ev_ids 内的虚构编号；强制用 Python PALMs 数据覆盖 LLM 输出防篡改。\n"
            "• 计算四支柱加权分，按 1500 + (score - 75)*4 生成 16 项机会初始天梯分。"
        ),
    )

    # Row 4: Elo Tournament
    v4 = g.add_card(
        "v4",
        "LLM_AGENT",
        x=430,
        y=966,
        w=980,
        h=112,
        title="[V4 · 16× 并行 LLM + 硬编码 K=32] 瑞士制两轮 Elo 锦标赛排位 (#1..#16)",
        body=(
            "• Round 1+2 共 16 场两两对抗裁判 (Context #3，每场仅见双方数据，消除位置偏置)。\n"
            "• Python 确定性执行 K=32 Elo 更新，按 0.55×支柱分 + 0.45×Elo 冻结终审排位并预渲染分域表。"
        ),
    )

    # Row 5: Parallel Synth Fan-out (Left: Vol 05 Hardcoded, Right: Vol 00-04 LLM) -> Regex Join
    v5a = g.add_card(
        "v5a_idx",
        "HARDCODED",
        x=320,
        y=1132,
        w=560,
        h=122,
        title="[V5a · 硬编码 零LLM] SQLite 直出总索引 (Vol 05)",
        body=(
            "render_evidence_index() 直接遍历 SQLite 渲染\n"
            "225 条去重证据与核验链接 (113 KB)，物理杜绝 URL 幻觉。"
        ),
    )
    v5b = g.add_card(
        "v5b_llm",
        "LLM_AGENT",
        x=960,
        y=1132,
        w=560,
        h=122,
        title="[V5b · 5× 并行 LLM] 五卷长文撰写 (Vol 00–04)",
        body=(
            "5 路严格分域隔离合成 (Context #4)，共写 231 KB 正文；\n"
            "去重精确引用 81 个 [EV-...] 与 80 处 [ROI-CALC]。"
        ),
    )

    v5j = g.add_card(
        "v5_check",
        "HARDCODED",
        x=430,
        y=1288,
        w=980,
        h=106,
        title="[V5 Join · 硬编码 Python] 正则契约审计 & 五卷头尾摘要截取",
        body=(
            "• 正则统计 EV-(CN|GL)-XXX 引用数、[ROI-CALC] 数、CN信源占比 (63.11%) 与五卷字数。\n"
            "• 截取各卷 头2200字 + 尾800字 预览包（防止 231 KB 全文送审导致审稿大模型注意力退化）。"
        ),
    )

    # Row 6: Critic & Bounded Side Loops
    v6 = g.add_card(
        "v6_critic",
        "GATE",
        x=430,
        y=1432,
        w=980,
        h=126,
        title="[V6 · LLM #5 + 条件路由] 异构 Critic 审稿 & route_after_critic",
        body=(
            "• 审查 Context #5 (实测首轮 pass, 置信度 98.5)；防死循环硬熔断：loop_count <= max_loops (默认 2 轮)。\n"
            "• 三路条件分流：1) pass 向下直通终审 ｜ 2) needs_more_evidence 向右补搜重合成 ｜ 3) needs_rewrite 向左重写。"
        ),
    )

    # Side loop boxes flanking V5 / V6 cleanly
    v6_left = g.add_card(
        "v6_rewrite",
        "LLM_AGENT",
        x=48,
        y=1262,
        w=246,
        h=152,
        hdr_h=36,
        hdr_font=14,
        body_font=13,
        title="[闭环2 · LLM #6] 定向重写",
        body="按问题分卷定向注入整改清单 (Context #6) 并重算正则摘要回 V6 (本次跳过)。",
    )
    p_left = g.add_pill(
        "needs_rewrite",
        x=306,
        y=1476,
        w=112,
        h=38,
        text="needs_rewrite\n(<=2轮)",
        fill="#FFF1F2",
        stroke="#7C3AED",
        font_color="#5B21B6",
        font_size=11,
    )

    v6_right = g.add_card(
        "v6_refill",
        "HARDCODED",
        x=1596,
        y=1258,
        w=266,
        h=158,
        hdr_h=36,
        hdr_font=14,
        body_font=13,
        title="[闭环1 · 硬编码] 补搜 CRAG",
        body="模式2 Corrective RAG：提取 gap_queries[:4] 补搜入 SQLite，回流 V5b 重触发合成。",
    )
    p_right = g.add_pill(
        "needs_more_evidence",
        x=1426,
        y=1474,
        w=156,
        h=42,
        text="needs_more_evidence\n(缺证据 · 模式2)",
        fill="#FFF1F2",
        stroke="#BE123C",
        font_color="#9F1239",
        font_size=11,
    )

    # Pass Gate Pill + Row 7 Judge & Finalize & Archive
    p_pass = g.add_pill(
        "pass",
        x=785,
        y=1578,
        w=270,
        h=36,
        text="pass (首轮置信度 98.5 · 直通终审)",
        fill="#ECFDF5",
        stroke="#059669",
        font_color="#065F46",
        font_size=13,
    )

    v7 = g.add_card(
        "v7_judge",
        "LLM_AGENT",
        x=430,
        y=1634,
        w=980,
        h=106,
        title="[V7 · LLM #7] Stage-Gate 100 分制独立裁判",
        body=(
            "Context #7 (量化指标 + 五卷摘要)：逐维打分 0–20 × 5 维；本次实测 20×5 = 100.0 / 100 (门槛 >= 85 通过)。"
        ),
    )

    v8 = g.add_card(
        "v8_finalize",
        "HARDCODED",
        x=430,
        y=1770,
        w=980,
        h=106,
        title="[V8 · 硬编码 Python] finalize-native 终审校核与防漂移归档",
        body=(
            "按实际通过白名单的证据数重算支柱分/Elo 排位，Python 强制重算五项分数和，消除 LLM 算术漂移。"
        ),
    )

    v9 = g.add_card(
        "v9_archive",
        "STORAGE",
        x=320,
        y=1904,
        w=1200,
        h=96,
        hdr_h=34,
        hdr_font=14,
        body_font=13,
        title="[V9 · 持久化交付物] outputs/power_semiconductor_online_testing_2026_2036/",
        body=(
            "00–04 五卷研报 (231 KB) ｜ 05 零幻觉索引 (113 KB, 225条) ｜ 06 遥测审计 JSON ｜ 07 模型溯源报告 ｜ 08 A0详图 ｜ 09 本清爽拓扑图 ｜ 10 复盘报告"
        ),
    )

    # Decoupled Right Sidebar (Zero cross-panel edges)
    g.add_card(
        "side_legend",
        "BANNER",
        x=1922,
        y=184,
        w=826,
        h=480,
        title="[附表 A] 图论性质 · 颜色编码 · 本次实测模型路由摘要",
        body=(
            "1. 这究竟是不是 DAG？\n"
            "   • 不是纯粹无环图，而是“主干单向 DAG (V0→V5) + 尾部受控有界闭环 (Bounded Cyclic StateGraph)”。\n"
            "   • 尾部 V6 Critic 允许两条有限回环（<= 2 轮熔断防死循环），V7 之后严格单向收敛到 V9。\n\n"
            "2. 五色图例约定：\n"
            "   • 深蓝 [硬编码 Python]：确定性搜库、PALMs 算账、白名单清洗、K=32 Elo 更新、正则检查、Vol 05 直出。\n"
            "   • 深紫 [LLM 分析]：认知规划、赛道深研+STORM、成对胜负裁决、长文撰写、Critic 审稿、Judge 打分。\n"
            "   • 翠绿 [持久化存储]：YAML 契约与 SQLite EvidenceVault / 终稿归档。\n"
            "   • 玫红 [条件路由]：route_after_critic 三路分流与 loop_count <= 2 硬上限。\n"
            "   • 琥珀 [Context 组装]：独立成表展示下方，不打断主流程视觉读取。\n\n"
            "3. native-88e91cf7 真实底座：\n"
            "   • Plan Mode: gemini-pro-orchestrator [Orchestrator (Carbon)] | Execute: gemini-flash-worker-agy\n"
            "   • run_workflow(model=\"pro\") 全部 32 个子智能体实测路由至 gemini-3.8-flash-tiered（共 1,038,775 tokens）。"
        ),
    )

    g.add_card(
        "side_ctx",
        "CONTEXT_BOX",
        x=1922,
        y=684,
        w=826,
        h=866,
        dashed_body=True,
        title="[附表 B] 7 处 LLM 调用点 Context 上下文精确组装速查手册",
        body=(
            "• Context #1 → [V2] Step-Back 总规划 (1× LLM)\n"
            "  注入：中国优先+双时间窗 Mandate + 8 赛道工段清单 + NO_TOOL_DIRECTIVE + PLAN_SCHEMA（不注网页噪音）。\n\n"
            "• Context #2 → [V3a/b] 8 赛道并行深研 + STORM (8× 并行 LLM)\n"
            "  注入（严格赛道隔离）：本赛道物理原则 + 2 种子与 Python [ROI-CALC] + Top 22 条 SQLite 摘要\n"
            "  (12 CN + 10 GLOBAL [EV-...]) + 4 角色买方定义 + TRACK_SCHEMA（强制封闭白名单引用）。\n\n"
            "• Context #3 → [V4] 瑞士制 Elo 成对裁判 (2 轮 × 8 场 = 16× LLM)\n"
            "  注入（单场盲区隔离）：仅注 Option A vs B 的标题、周期、逐字 [ROI-CALC]、良率/升级机理与 35/25/20/20 权重。\n\n"
            "• Context #4 → [V5b] 五卷并行报告合成 (5× 并行 LLM · Strict Context Slicing 按卷防失焦)\n"
            "  - Vol 00 总览：step_back + roi_all + storm_all + elo_digest + ev_all\n"
            "  - Vol 01 电力 / Vol 02 半导体：严格仅注各自行业 ROI / 案卷 / STORM / ev_*（零跨行业噪音）\n"
            "  - Vol 03 财务Elo / Vol 04 平台出海：roi_all + elo_digest / 分域 [:3800] + storm_all + ev_all + SYNTH_RULES\n\n"
            "• Context #5 → [V6] 异构 Critic 审稿 (1× LLM)\n"
            "  注入：det_summary 正则硬统计 (81 引用 / 80 ROI / 63.11% CN) + 五卷 头2200字+尾800字 预览 + CRITIC_SCHEMA。\n\n"
            "• Context #6 / #7 → [V6-Loop2] 定向重写 & [V7] Stage-Gate 终审\n"
            "  按需仅注受损分卷+整改清单；终审注 det_summary + Critic 结论 + 五卷摘要 + 5×20 维标尺。"
        ),
    )

    g.add_card(
        "side_v2_bridge",
        "GATE",
        x=1922,
        y=1572,
        w=826,
        h=428,
        title="[附表 C] V1.0 诊断结论 → V2.0“从零动态发现”四大重构要点",
        body=(
            "1. 解绑 V0 静态赛道：废除 domain_taxonomy.yaml 对 8 赛道与固定搜索词的写死预设；改由 Stage 0 广谱侦察\n"
            "   (SEMI / IEA / 十五五规划 / 大厂招标扩产) 实证结果自下而上聚类长出 6–10 条高景气赛道（含跨界增量）。\n\n"
            "2. 解绑 16 项种子机会：取消预设 seed_opportunities 与固定 roi_baseline，改由 Stage 1 各赛道智能体根据真实产线\n"
            "   报错、废品损失与 EHS 法规自主涌现 24–32 个原始候选仪器机会（无 [EV-...] 实证支撑不准入池）。\n\n"
            "3. 三档区间 PALMs 漏斗防幻觉：LLM 仅从招投标/论文区间提取 CAPEX、良率提升与产值上下限 (low/base/high)，\n"
            "   由 Python 在行业物理边界内强行钳位并计算 保守/基准/乐观 三档回收期，通过 Stage 2 漏斗淘汰低弹性伪需求。\n\n"
            "4. 统一双模式因果序：Mode 1 (run_workflow) 与 Mode 2 (LangGraph) 全面对齐“先广谱侦察长赛道 → 再定标深挖\n"
            "   长候选 → Python 算账漏斗初筛 → STORM / Elo 复审排序 → 合成与 Critic 闭环”的真探索流。"
        ),
    )

    # Control-flow orthogonal edges (spine centered at cx=920)
    cx = 920
    # V0 -> V1
    g.add_edge("v0_v1", v0, v1, [(cx, 296), (cx, 336)], color="#065F46")
    # V0 dashed annotation link to V1 limitation pill
    g.add_edge("v0_limit", v0, p_v1_limit, [_mid_right(g.boxes[v0]), _mid_left(g.boxes[p_v1_limit])], color="#E11D48", dashed=True, stroke_w=2.2)
    # V1 -> V2
    g.add_edge("v1_v2", v1, v2, [(cx, 462), (cx, 502)], color="#1E3A8A")
    # V2 -> Fan-out V3a & V3b (split at y=638)
    g.add_edge("v2_split", v2, v3a, [(cx, 614), (cx, 638), (600, 638), (600, 666)], color="#5B21B6")
    g.add_edge("v2_split_r", v2, v3b, [(cx, 614), (cx, 638), (1240, 638), (1240, 666)], color="#5B21B6")
    # V3a & V3b -> Join V3j (join bar at y=804)
    g.add_edge("v3a_join", v3a, v3j, [(600, 788), (600, 804), (cx, 804), (cx, 822)], color="#5B21B6")
    g.add_edge("v3b_join", v3b, v3j, [(1240, 788), (1240, 804), (cx, 804), (cx, 822)], color="#5B21B6")
    # V3j -> V4
    g.add_edge("v3j_v4", v3j, v4, [(cx, 928), (cx, 966)], color="#1E3A8A")
    # V4 -> Fan-out V5a (Vol 05 hardcoded) & V5b (Vol 00-04 LLM) at y=1104
    g.add_edge("v4_split_l", v4, v5a, [(cx, 1078), (cx, 1104), (600, 1104), (600, 1132)], color="#1E3A8A")
    g.add_edge("v4_split_r", v4, v5b, [(cx, 1078), (cx, 1104), (1240, 1104), (1240, 1132)], color="#5B21B6")
    # V5a & V5b -> Join V5j (bar y=1270)
    g.add_edge("v5a_join", v5a, v5j, [(600, 1254), (600, 1270), (cx, 1270), (cx, 1288)], color="#1E3A8A")
    g.add_edge("v5b_join", v5b, v5j, [(1240, 1254), (1240, 1270), (cx, 1270), (cx, 1288)], color="#5B21B6")
    # V5j -> V6
    g.add_edge("v5j_v6", v5j, v6, [(cx, 1394), (cx, 1432)], color="#1E3A8A")

    # Left bounded loop: V6 -> p_left -> V6_rewrite -> V5j (clean planar loop!)
    g.add_edge("v6_p_left", v6, p_left, [(430, 1495), (418, 1495)], color="#7C3AED", dashed=True, stroke_w=2.4)
    g.add_edge("p_left_box", p_left, v6_left, [(306, 1495), (171, 1495), (171, 1414)], color="#7C3AED", dashed=True, stroke_w=2.4)
    g.add_edge("rew_back", v6_left, v5j, [(294, 1341), (430, 1341)], color="#7C3AED", dashed=True, stroke_w=2.4)

    # Right bounded loop: V6 -> p_right -> V6_refill -> V5b (clean planar loop!)
    g.add_edge("v6_p_right", v6, p_right, [(1410, 1495), (1426, 1495)], color="#BE123C", dashed=True, stroke_w=2.4)
    g.add_edge("p_right_box", p_right, v6_right, [(1582, 1495), (1729, 1495), (1729, 1416)], color="#BE123C", dashed=True, stroke_w=2.4)
    g.add_edge("crag_back", v6_right, v5b, [(1729, 1258), (1729, 1193), (1520, 1193)], color="#BE123C", dashed=True, stroke_w=2.4)

    # Pass mainline: V6 -> p_pass -> V7 -> V8 -> V9
    g.add_edge("v6_pass", v6, p_pass, [(cx, 1558), (cx, 1578)], color="#059669", stroke_w=3.2)
    g.add_edge("pass_v7", p_pass, v7, [(cx, 1614), (cx, 1634)], color="#059669", stroke_w=3.2)
    g.add_edge("v7_v8", v7, v8, [(cx, 1740), (cx, 1770)], color="#5B21B6", stroke_w=3.0)
    g.add_edge("v8_v9", v8, v9, [(cx, 1876), (cx, 1904)], color="#065F46", stroke_w=3.0)

    xml_str = g.build_xml("V1_Clean_Orchestration_Topology")
    return xml_str, len(g.boxes), len(g.edges)


def main() -> None:
    xml_str, n_boxes, n_edges = build_diagram()
    for target in (DOCS_OUT, RUN_OUT):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(xml_str, encoding="utf-8")
    shutil.copy2(DOCS_OUT, RUN_OUT)
    print(f"Generated Clean V1 Topology OK | boxes={n_boxes}, edges={n_edges}, geometry_audit=PASS")
    print(f"  - {DOCS_OUT}")
    print(f"  - {RUN_OUT}")


if __name__ == "__main__":
    main()
