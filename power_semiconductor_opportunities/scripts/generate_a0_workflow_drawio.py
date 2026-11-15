#!/usr/bin/env python3
"""Programmatic ISO A0 Landscape Draw.io Architecture Generator & Geometric Auditor.

Generates `docs/03_AGENTIC_WORKFLOW_ARCHITECTURE_A0.drawio` (and syncs to
`outputs/power_semiconductor_online_testing_2026_2036/08_AGENTIC_WORKFLOW_ARCHITECTURE_A0.drawio`)
depicting the complete Power & Semiconductor Online Testing Instrumentation Agentic Workflow:
- `[硬编码 · 确定性 Python]` vs `[LLM 分析 · 智能体认知]` vs `[Context 组装]`
  vs `[持久化存储]` vs `[条件路由]`
- Exact prompt/context assembly inputs & schema locks at every LLM invocation
- Dual execution modes (Mode 1: Antigravity Native `run_workflow` vs Mode 2: Standalone CLI LangGraph)
- Forensic model provenance for `native-88e91cf7`

Enforces zero-overlap layout invariants programmatically before writing XML:
1. CJK+ASCII line-wrap height check for every card header, body, and pill
2. Strict card-to-card / pill-to-card bounding-box non-overlap check (min clearance)
3. Strict orthogonal edge-segment vs non-endpoint box AND endpoint-interior non-intersection check
4. Zero floating edge text labels (`value=""` on every edge; branch labels rendered as pills)
"""

from __future__ import annotations

import math
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path("/Users/john/Desktop/agentic_learning/power_semiconductor_opportunities")
DOCS_DRAWIO = BASE_DIR / "docs/03_AGENTIC_WORKFLOW_ARCHITECTURE_A0.drawio"
OUT_DRAWIO = (
    BASE_DIR
    / "outputs/power_semiconductor_online_testing_2026_2036/08_AGENTIC_WORKFLOW_ARCHITECTURE_A0.drawio"
)

CANVAS_W = 4681  # ISO A0 Landscape at 100 dpi (1189mm)
CANVAS_H = 3311  # ISO A0 Landscape at 100 dpi (841mm)

STYLES = {
    "HARDCODED": {
        "hdr_fill": "#1E3A8A",
        "hdr_stroke": "#1E3A8A",
        "hdr_font": "#FFFFFF",
        "body_fill": "#EFF6FF",
        "body_stroke": "#2563EB",
        "body_font": "#0F172A",
    },
    "LLM_AGENT": {
        "hdr_fill": "#5B21B6",
        "hdr_stroke": "#5B21B6",
        "hdr_font": "#FFFFFF",
        "body_fill": "#F5F3FF",
        "body_stroke": "#7C3AED",
        "body_font": "#1E1B4B",
    },
    "CONTEXT_BOX": {
        "hdr_fill": "#B45309",
        "hdr_stroke": "#B45309",
        "hdr_font": "#FFFFFF",
        "body_fill": "#FFFBEB",
        "body_stroke": "#D97706",
        "body_font": "#451A03",
    },
    "STORAGE": {
        "hdr_fill": "#065F46",
        "hdr_stroke": "#065F46",
        "hdr_font": "#FFFFFF",
        "body_fill": "#ECFDF5",
        "body_stroke": "#059669",
        "body_font": "#064E3B",
    },
    "GATE": {
        "hdr_fill": "#9F1239",
        "hdr_stroke": "#9F1239",
        "hdr_font": "#FFFFFF",
        "body_fill": "#FFF1F2",
        "body_stroke": "#E11D48",
        "body_font": "#4C0519",
    },
    "BANNER": {
        "hdr_fill": "#0F172A",
        "hdr_stroke": "#0F172A",
        "hdr_font": "#FFFFFF",
        "body_fill": "#F1F5F9",
        "body_stroke": "#334155",
        "body_font": "#0F172A",
    },
}


def _char_width_px(ch: str, font_size: int) -> float:
    code = ord(ch)
    if (
        0x4E00 <= code <= 0x9FFF
        or 0x3000 <= code <= 0x303F
        or 0xFF00 <= code <= 0xFFEF
        or ch in "·—–•≥≤±×→←↔【】「」"
    ):
        return font_size * 1.04
    if ch in "WM@%#&":
        return font_size * 0.78
    if ch.isupper() or ch in "[]{}()/\\":
        return font_size * 0.65
    return font_size * 0.54


def estimate_wrapped_height(
    text: str,
    width_px: int,
    font_size: int,
    pad_lr: int = 28,
    pad_tb: int = 22,
    line_mult: float = 1.36,
) -> tuple[int, int]:
    """Estimate wrapped text line count and pixel height for CJK+ASCII."""
    usable_w = max(80.0, float(width_px - pad_lr))
    paragraphs = text.split("\n")
    total_lines = 0
    for para in paragraphs:
        if not para:
            total_lines += 1
            continue
        cur_w = 0.0
        lines_in_para = 1
        for ch in para:
            cw = _char_width_px(ch, font_size)
            if cur_w + cw > usable_w:
                lines_in_para += 1
                cur_w = cw
            else:
                cur_w += cw
        total_lines += lines_in_para
    needed = math.ceil(total_lines * font_size * line_mult) + pad_tb
    return total_lines, needed


@dataclass
class RectBox:
    box_id: str
    kind: str  # "card" | "pill"
    x: int
    y: int
    w: int
    h: int


@dataclass
class EdgeRoute:
    edge_id: str
    src_id: str
    dst_id: str
    points: list[tuple[int, int]]
    color: str
    dashed: bool = False
    stroke_w: float = 2.6
    start_arrow: bool = False


class DrawioCanvasBuilder:
    def __init__(self) -> None:
        self._id_counter = 10
        self.bg_cells: list[ET.Element] = []
        self.fg_cells: list[ET.Element] = []
        self.edge_cells: list[ET.Element] = []
        self.boxes: dict[str, RectBox] = {}
        self.edges: list[EdgeRoute] = []

    def next_id(self, prefix: str = "c") -> str:
        self._id_counter += 1
        return f"{prefix}_{self._id_counter}"

    def add_band(self, x: int, y: int, w: int, h: int, title: str, accent: str = "#475569") -> None:
        """Add subtle swimlane frame + top title ribbon."""
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
            {
                "x": str(x + 14),
                "y": str(y + 8),
                "width": str(w - 28),
                "height": "32",
                "as": "geometry",
            },
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
        hdr_h: int = 44,
        hdr_font: int = 15,
        body_font: int = 14,
        dashed_body: bool = False,
    ) -> str:
        """Add two-part structured node card (solid header + light body) and assert text fits."""
        st = STYLES[kind]
        t_lines, t_need = estimate_wrapped_height(title, w, hdr_font, pad_lr=24, pad_tb=10, line_mult=1.25)
        if t_need > hdr_h:
            raise AssertionError(
                f"Header overflow on `{key}`: need {t_need}px ({t_lines}L) > hdr_h={hdr_h}px | title={title!r}"
            )
        body_h = h - hdr_h
        b_lines, b_need = estimate_wrapped_height(body, w, body_font, pad_lr=28, pad_tb=18, line_mult=1.35)
        if b_need > body_h:
            raise AssertionError(
                f"Body overflow on `{key}`: need {b_need}px ({b_lines}L) > body_h={body_h}px (total h={h}, w={w})"
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
            {
                "x": str(x),
                "y": str(y + hdr_h),
                "width": str(w),
                "height": str(body_h),
                "as": "geometry",
            },
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
        font_size: int = 12,
    ) -> str:
        """Add compact badge pill (replaces fragile floating edge text)."""
        lines, need = estimate_wrapped_height(text, w, font_size, pad_lr=14, pad_tb=6, line_mult=1.25)
        if need > h:
            raise AssertionError(f"Pill overflow `{key}`: need {need}px ({lines}L) > {h}px | text={text!r}")
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
        stroke_w: float = 2.6,
        start_arrow: bool = False,
    ) -> None:
        """Add strictly orthogonal connector passing through explicit points (empty edge text)."""
        if len(points) < 2:
            raise ValueError(f"Edge `{key}` needs >= 2 points")
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            if x1 != x2 and y1 != y2:
                raise AssertionError(
                    f"Edge `{key}` segment ({x1},{y1})->({x2},{y2}) is diagonal, must be strictly orthogonal!"
                )
        eid = f"edge_{key}"
        dash_css = "dashed=1;dashPattern=8 5;" if dashed else ""
        sa_css = "startArrow=classic;startFill=1;" if start_arrow else "startArrow=none;"
        cell = ET.Element(
            "mxCell",
            {
                "id": eid,
                "value": "",
                "style": (
                    f"edgeStyle=none;orthogonalLoop=1;jettySize=auto;html=0;rounded=1;arcSize=8;"
                    f"strokeColor={color};strokeWidth={stroke_w};{dash_css}{sa_css}"
                    "endArrow=classic;endFill=1;"
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
        self.edges.append(EdgeRoute(eid, src_id, dst_id, points, color, dashed, stroke_w, start_arrow))

    def audit_geometry(self) -> None:
        """Verify zero box overlaps, zero non-endpoint crossings, and zero endpoint interior crossings."""
        box_list = list(self.boxes.values())
        for b in box_list:
            if b.x < 10 or b.y < 10 or b.x + b.w > CANVAS_W - 10 or b.y + b.h > CANVAS_H - 10:
                raise AssertionError(f"Box `{b.box_id}` out of A0 bounds: {b}")

        margin = 8
        for i, a in enumerate(box_list):
            for b in box_list[i + 1 :]:
                x_ov = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
                y_ov = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
                if x_ov > -margin and y_ov > -margin:
                    raise AssertionError(
                        f"Box overlap ({x_ov}x{y_ov}) between `{a.box_id}` ({a}) and `{b.box_id}` ({b})"
                    )

        pad = 3
        for e in self.edges:
            for seg_idx, ((x1, y1), (x2, y2)) in enumerate(zip(e.points, e.points[1:])):
                sx_lo, sx_hi = min(x1, x2), max(x1, x2)
                sy_lo, sy_hi = min(y1, y2), max(y1, y2)
                mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                for b in box_list:
                    if b.box_id in (e.src_id, e.dst_id):
                        # Even endpoint boxes must NOT have a segment passing through their interior!
                        if (b.x + 2 < mx < b.x + b.w - 2) and (b.y + 2 < my < b.y + b.h - 2):
                            raise AssertionError(
                                f"Edge `{e.edge_id}` seg {seg_idx} passes inside own endpoint `{b.box_id}` ({b})!"
                            )
                        continue
                    bx_lo, bx_hi = b.x - pad, b.x + b.w + pad
                    by_lo, by_hi = b.y - pad, b.y + b.h + pad
                    if sx_lo == sx_hi:
                        if bx_lo <= sx_lo <= bx_hi and sy_hi > by_lo and sy_lo < by_hi:
                            raise AssertionError(
                                f"Edge `{e.edge_id}` seg {seg_idx} ({x1},{y1})->({x2},{y2}) crosses `{b.box_id}` ({b})"
                            )
                    else:
                        if by_lo <= sy_lo <= by_hi and sx_hi > bx_lo and sx_lo < bx_hi:
                            raise AssertionError(
                                f"Edge `{e.edge_id}` seg {seg_idx} ({x1},{y1})->({x2},{y2}) crosses `{b.box_id}` ({b})"
                            )

    def build_xml(self) -> str:
        self.audit_geometry()
        mxfile = ET.Element(
            "mxfile",
            {
                "host": "Antigravity-Agent",
                "modified": "2026-11-15T05:40:00.000Z",
                "agent": "PSO-Workflow-Drawio-Generator",
                "version": "32.6.1",
                "type": "device",
            },
        )
        diagram = ET.SubElement(
            mxfile,
            "diagram",
            {
                "id": "pso_a0_workflow_architecture",
                "name": "A0_Workflow_Architecture_And_Context_Assembly",
            },
        )
        model = ET.SubElement(
            diagram,
            "mxGraphModel",
            {
                "dx": "1800",
                "dy": "1200",
                "grid": "1",
                "gridSize": "10",
                "guides": "1",
                "tooltips": "1",
                "connect": "1",
                "arrows": "1",
                "fold": "1",
                "page": "1",
                "pageScale": "1",
                "pageWidth": str(CANVAS_W),
                "pageHeight": str(CANVAS_H),
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


def _mid_top(b: RectBox) -> tuple[int, int]:
    return (b.x + b.w // 2, b.y)


def _mid_bot(b: RectBox) -> tuple[int, int]:
    return (b.x + b.w // 2, b.y + b.h)


def _mid_left(b: RectBox) -> tuple[int, int]:
    return (b.x, b.y + b.h // 2)


def _mid_right(b: RectBox) -> tuple[int, int]:
    return (b.x + b.w, b.y + b.h // 2)


def build_diagram() -> tuple[str, int, int]:
    g = DrawioCanvasBuilder()

    # =========================================================================
    # BAND 0 (y=36..310): Title Banner, Semantic Legend & Model Provenance
    # =========================================================================
    g.add_band(
        x=60,
        y=36,
        w=4460,
        h=274,
        title="全景架构总览 · 设计模式谱系 · 节点性质色标与双运行模式大模型底座实证 (ISO A0 Landscape: 4681 × 3311 px)",
        accent="#0F172A",
    )

    g.add_card(
        "title",
        "BANNER",
        x=88,
        y=78,
        w=1460,
        h=218,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="电力能源 × 半导体芯片制造 在线测试仪器仪表智能体发现工作流 (2026–2036)",
        body=(
            "• 战略定位：【中国市场优先 (2027–2031 国产替代与高ROI放量) → 全球市场跟进 (2031–2036 代际跃迁与标准出海)】。\n"
            "• 八大赛道：电力 P1(储能/固态电池) P2(钙钛矿/绿氢) P3(特高压/SF6替代/海缆) P4(调峰/CCUS) × 半导体 S1(AMC/湿化) S2(前道/SAXS) S3(SiC/GaN) S4(混合键合/HBM)。\n"
            "• 四大价值：品质良率提升 (25%) ｜ 制造降本与TCO/环保EHS (20%) ｜ 高制造ROI回报与产业升级 (35%+20%)。\n"
            "• 架构融合：Agentic Design Patterns (Ch 1–21) + open_deep_research + Stanford STORM + Deer-Flow PALMs + AI Co-Scientist Elo。"
        ),
    )

    g.add_card(
        "legend",
        "STORAGE",
        x=1596,
        y=78,
        w=1380,
        h=218,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[图例约定] 五类节点执行性质 · 上下文组装标示 · 箭头语义",
        body=(
            "• 深蓝 [硬编码 · 确定性 Python]：零 LLM 参与；负责搜索/去重、SQLite I/O、PALMs ROI/IRR/NPV 算账、Elo 更新与正则核验。\n"
            "• 深紫 [LLM 分析 · 智能体认知]：模式1 Antigravity run_workflow 或模式2 DashScope 网关；仅做机理推导与文本合成，禁止心算数字。\n"
            "• 琥珀 [Context 组装 · 上下文载荷]：虚线框标出每次 LLM 调用 Prompt 精准注入的切片来源、封闭引用白名单与 JSON Schema 约束。\n"
            "• 翠绿 [持久化存储 · 契约 / SQLite / 终稿]：YAML 契约本体、Git 隔离密钥 .env.ai_search、evidence_vault.db 及 00–08 交付物。\n"
            "• 玫红 [条件路由 · 质量门禁循环]：route_after_critic 分支路由、可选 HITL 检查点与循环次数熔断 (loop_count <= max_loops)。"
        ),
    )

    g.add_card(
        "provenance",
        "LLM_AGENT",
        x=3024,
        y=78,
        w=1468,
        h=218,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[底层模型实证溯源] 班次 native-88e91cf7 双运行模式真实模型路由",
        body=(
            "• 主会话规划层 (Plan Mode)：gemini-pro-orchestrator [Orchestrator (Carbon) = Gemini 4 Carbon] ｜ 执行层：gemini-flash-worker-agy。\n"
            "• 模式 1 (run_workflow 传 model=\"pro\")：接口仅接收 4 档抽象别名；经 transcript.jsonl 实证，全部 32 个子智能体均路由至\n"
            "  gemini-3.8-flash-tiered（输入 681,829 + 输出 356,946 = 1,038,775 tokens，耗时 13m14s），并非 Argon / Carbon / 3.1 Pro / Claude Opus 5.5。\n"
            "• 精准锁定顶级底座：(a) IDE 选定 Claude Opus 5.5 / Gemini 4 Argon 并传 model=\"inherit\"；(b) 用 swarm(model=...) 按具体 ID 绑定。\n"
            "• 模式 2 (Standalone CLI 终端 graph.py)：直连 .env.llm DashScope 异构梯队 (qwen3.8-flash / qwen3.8-max / critic: deepseek-v4-pro)。"
        ),
    )

    # =========================================================================
    # BAND 1 (y=368..748): Phase 1 — Paid Search, SQLite Vault & PALMs ROI
    # =========================================================================
    g.add_band(
        x=60,
        y=368,
        w=4460,
        h=380,
        title="Phase 1: 契约本体装载 · 付费双引擎 AI 检索 · SQLite 持久化证据库 · Python PALMs 财务预计算 [100% 硬编码确定性执行]",
        accent="#1E3A8A",
    )

    n1_1 = g.add_card(
        "n1_1_cfg",
        "STORAGE",
        x=88,
        y=410,
        w=970,
        h=322,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[持久化存储 · 输入基座] 契约 YAML + 8 赛道本体 + 密钥隔离",
        body=(
            "• 形式化契约 config/research_contract.yaml (PSO-CONTRACT-2026-V1)：\n"
            "  强制中国信源 >= 45%、总证据 >= 48、Stage-Gate 通过线 >= 85/100、四大价值权重 (35/25/20/20)。\n"
            "• 行业本体 config/domain_taxonomy.yaml：\n"
            "  定义 P1–P4 与 S1–S4 共 8 条赛道、核心产线工艺工段、CN/GLOBAL 检索式及 16 个校准\n"
            "  基准机会种子 (seed_opportunities + roi_baseline)。\n"
            "• 密钥物理隔离 (.gitignore)：.env.ai_search 独立存 METASO_API_KEY 与 SERPER_API_KEY；\n"
            "  .env.llm 仅用于模式2；WorkflowSettings.load() (config.py) 统一校验加载。"
        ),
    )

    n1_2 = g.add_card(
        "n1_2_search",
        "HARDCODED",
        x=1128,
        y=410,
        w=1080,
        h=322,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[硬编码 · Python] DualEngineSearchRouter 双引擎 AI 检索网关",
        body=(
            "• 中国优先引擎 MetasoClient (tools/search_router.py)：\n"
            "  调用 POST https://metaso.cn/api/v1/search (webpage/scholar)；强制 size 与 page 互斥传参，\n"
            "  并主动拦截 HTTP 200 响应体内隐藏的 errCode != 0 业务报错。\n"
            "• 全球主力引擎 SerperClient：并发查询 Google search / scholar / patents (默认 qdr:y 时效)。\n"
            "• 全文增强与容错 (Ch 12)：Top T1–T3 URL 经 r.jina.ai (备援 Metaso reader) 抓取至多\n"
            "  10,000 字符 Markdown 正文；指数退避重试 + Semaphore(6) + CostLedger (40 次查询入库)。"
        ),
    )

    n1_3 = g.add_card(
        "n1_3_vault",
        "STORAGE",
        x=2278,
        y=410,
        w=1060,
        h=322,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[持久化存储 · SQLite] EvidenceVault 去重入库与权威分级记忆库",
        body=(
            "• 介质：data/evidence_vault.db (evidences + query_log 双表，tools/evidence_vault.py)。\n"
            "• URL 归一化与 SHA-1 去重：normalize_url() 剥离 utm_*/spm/ref 参数，url_sha1() 跨赛道\n"
            "  幂等 Upsert 去重，避免重复写入并保留已抓取全文 Markdown。\n"
            "• 权威分级 (score_source_authority)：T1 (.gov, ieee, semi, iec, nature, patents.google)\n"
            "  / T2 (KLA, ASML, CATL, Yole) / T3 / T4。\n"
            "• 本次实测固化成果：分配唯一编号 EV-CN-001..142 (142 条占 63.11%) 与 EV-GL-001..083\n"
            "  (83 条)，总计 225 条去重核验证据（含 24 篇全文深抓）。"
        ),
    )

    n1_4 = g.add_card(
        "n1_4_palms",
        "HARDCODED",
        x=3408,
        y=410,
        w=1084,
        h=322,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[硬编码 · Python] PALMs 确定性财务计算 & prepare-context 打包器",
        body=(
            "• 确定性财务算账 tools/roi_calculator.py（严格禁止 LLM 心算任何投资数据）：\n"
            "  NetCF = YieldGain + ScrapAvoid + DowntimeAvoid + EHS_Save - OPEX；计算静态回收期\n"
            "  (Payback 月)、3Y ROI%、5Y NPV (WACC=10%)、5Y IRR (80 轮二分法)、Tier 分级及 SAM/SOM。\n"
            "• 四支柱加权打分 compute_weighted_pillar_score()：按 35/25/20/20 权重生成基准排序。\n"
            "• 原生桥接 cli.py::_cmd_prepare_context：\n"
            "  按赛道裁剪导出 Top 12 CN + 10 GLOBAL 证据包与 16 项 [ROI-CALC] → data/native_context_bundle.json。"
        ),
    )

    # =========================================================================
    # BAND 2 (y=818..1178): Phase 2 — Guardrail, Context #1, Planner, Map
    # =========================================================================
    g.add_band(
        x=60,
        y=818,
        w=4460,
        h=360,
        title="Phase 2: 范围护栏校验 · 可选 HITL 检查点 · 上下文组装 #1 · Step-Back 物理第一性原理总规划",
        accent="#5B21B6",
    )

    n2_1 = g.add_card(
        "n2_1_guard",
        "HARDCODED",
        x=88,
        y=860,
        w=970,
        h=302,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[硬编码 · 门禁护栏] 输入范围校验 + LangGraph 可选 HITL 审批门禁",
        body=(
            "• 行业作用域校验 (nodes/planner.py::_select_tracks & cli.py)：\n"
            "  验证 sector_filter in {all, power, semiconductor}，锁定 8 条正交赛道 (P1–P4 & S1–S4) 及核心工段。\n"
            "• 契约底线注入：强制锁定【中国优先 → 全球跟进】与【3–5年 vs 5–10年双时间窗】不可删减。\n"
            "• 可选人类审批检查点 (node_hitl_approval_gate)：\n"
            "  模式2 启用 --hitl 时，基于 SQLite Checkpointer (langgraph_checkpoints.db) 调用\n"
            "  langgraph.types.interrupt()，先呈报 8 赛道规划并暂停等待确认，再行全并发深度研究。"
        ),
    )

    n2_2 = g.add_card(
        "n2_2_ctx1",
        "CONTEXT_BOX",
        x=1128,
        y=860,
        w=1180,
        h=302,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        dashed_body=True,
        title="[Context 组装 #1] Step-Back Planner Prompt 上下文结构",
        body=(
            "• 角色设定：Chief Industrial Metrology Architect（工业计量首席架构师）。\n"
            "• 注入内容（故意轻量化隔离 — 本跳不注入任何网页碎片，防止高层物理抽象受局部噪音干扰）：\n"
            "  1. Mandate：CN-First (2027–2031 放量 / 2031–2036 跃迁) → Global Second；四大价值支柱。\n"
            "  2. track_briefs：仅拼接 8 赛道的 id、sector、name 与 manufacturing_stages 工艺工段清单。\n"
            "• 输出与工具锁定：\n"
            "  - 模式1 追加 NO_TOOL_DIRECTIVE（禁用文件/命令行/搜索工具）+ PLAN_SCHEMA (step_back_thesis 等)。\n"
            "  - 模式2 注入 PLANNER_SYSTEM + ResearchPlan Schema。"
        ),
    )

    n2_3 = g.add_card(
        "n2_3_planner",
        "LLM_AGENT",
        x=2378,
        y=860,
        w=1050,
        h=302,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[LLM 分析 #1] Chief Metrology Architect (Step-Back 规划节点)",
        body=(
            "• 调用方式与真实底座：\n"
            "  - 模式1 (antigravity_run_workflow.py Phase 2)：1 次调用 agent(model=\"pro\") -> gemini-3.8-flash-tiered。\n"
            "  - 模式2 (nodes/planner.py)：tier=\"producer\" -> qwen3.8-max (关闭思维链加速结构化生成)。\n"
            "• Step-Back 第一性原理抽象推导：\n"
            "  从“能量量子（光子/声子/X射线/THz）或分子质荷比与制造界面的微观相互作用”出发，界定离线\n"
            "  抽检为何必然被原位 R2R/APC 闭环取代，输出全局 step_back_thesis 及 8 赛道专属物理失效准则。"
        ),
    )

    n2_4 = g.add_card(
        "n2_4_pmap",
        "HARDCODED",
        x=3498,
        y=860,
        w=994,
        h=302,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[硬编码 · Python] 物理原理映射提取与权威检索式回填",
        body=(
            "• 物理引导映射构建 (phys_by_track)：\n"
            "  解析 Planner 结构化返回值，提取 track_id -> step_back_physics_principle 字典；\n"
            "  若任何赛道缺失，自动回退填充默认赛道物理不变量。\n"
            "• 防搜索漂移保护（模式2）：\n"
            "  强制覆盖清空 LLM 生成的泛化查询词，直接从 config/domain_taxonomy.yaml 确定性挂载经过\n"
            "  校准的 cn_queries (Metaso) 与 global_queries (Serper)，保证后续检索信噪比。"
        ),
    )

    # =========================================================================
    # BAND 3 (y=1248..1678): Phase 3 — Parallel 8-Track + STORM + Alignment
    # =========================================================================
    g.add_band(
        x=60,
        y=1248,
        w=4460,
        h=430,
        title="Phase 3: 8 赛道并行动态扇出 · 零串扰赛道隔离 Context 组装 #2 · 8 路并行深研与 STORM 四角色拷问 · 确定性锚定归并",
        accent="#5B21B6",
    )

    n3_1 = g.add_card(
        "n3_1_fanout",
        "HARDCODED",
        x=88,
        y=1290,
        w=970,
        h=370,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[硬编码 · 并行扇出] 动态 8 路隔离认知分发器 (Factored Cognition)",
        body=(
            "• 并发扇出：模式1 await parallel(ctx[\"tracks\"], ...) ｜ 模式2 Send(\"track_researcher\", ...)。\n"
            "• 8 条正交细分工业赛道同步启动：\n"
            "  [电力能源] P1 储能/固态电池 ｜ P2 钙钛矿/绿氢 ｜ P3 特高压/SF6替代/海缆 ｜ P4 调峰/CCUS。\n"
            "  [半导体制造] S1 Fab AMC/湿化 ｜ S2 前道膜厚/OCD/SAXS ｜ S3 SiC/GaN ｜ S4 HBM/混合键合。\n"
            "• 认知隔离准则 (Factored Cognition)：每名并发 Worker 仅获准读取自身所属赛道切片，零跨赛道\n"
            "  上下文泄漏或 Token 相互污染。"
        ),
    )

    n3_2 = g.add_card(
        "n3_2_ctx2",
        "CONTEXT_BOX",
        x=1128,
        y=1290,
        w=1220,
        h=370,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        dashed_body=True,
        title="[Context 组装 #2] Per-Track 隔离 Prompt 装配 (_build_track_prompt)",
        body=(
            "• 精准组装 5 层赛道隔离上下文：\n"
            "  1. phys_by_track[track_id]（Phase 2 输出）+ 本赛道制造工段 manufacturing_stages。\n"
            "  2. 本赛道 2 项机会种子 + Python 预计算 [ROI-CALC]（CAPEX/NetCF/Payback/IRR/NPV/CN&GL TAM）。\n"
            "  3. 本赛道 Top 22 条 SQLite 权威证据：12 条 CN + 10 条 GLOBAL [EV-CN/GL-...]\n"
            "     （full_markdown[:600] 或 snippet[:380]），同步形成严格封闭引用白名单 valid_ev_ids。\n"
            "  4. 强制四角色 STORM 买方审查定义：Fab/Plant Yield VP、Metrology Chief Engineer、\n"
            "     EHS Compliance Director、CFO / Procurement ROI Gatekeeper。\n"
            "  5. 中国优先+双时间窗要求 + NO_TOOL_DIRECTIVE + 扁平化 TRACK_SCHEMA。"
        ),
    )

    n3_3 = g.add_card(
        "n3_3_res_storm",
        "LLM_AGENT",
        x=2418,
        y=1290,
        w=1050,
        h=370,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[LLM 分析 #2] 8× 并行赛道深研 + 4 角色 STORM 买方拷问智能体",
        body=(
            "• 执行架构与底层模型：\n"
            "  - 模式1 (Phase 3)：8 路全并发 agent() (gemini-3.8-flash-tiered) 在单回合结构化输出内\n"
            "    一体完成赛道痛点研究与 4 角色 STORM 买方委员会抗拒点拷问（共 16 组完整对话画像）。\n"
            "  - 模式2：8 路 qwen3.8-flash (TrackDossier) → 16 路并发 qwen3.8-max (OpportunityStormMemo)。\n"
            "• 产出要素：先中国市场动态、后全球市场对标；区分 3–5 年 vs 5–10 年演进；>=4 项产线痛点；\n"
            "  每项机会的量子/分子传感机理、在线 Form Factor、四大价值机制与工程改型破局动作。"
        ),
    )

    n3_4 = g.add_card(
        "n3_4_align",
        "HARDCODED",
        x=3538,
        y=1290,
        w=954,
        h=370,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[硬编码 · Python] 证据白名单清洗 · 财务重锚定 · Elo 初始化",
        body=(
            "• 确定性对齐与清洗器 (aligned_opps / _merge_baseline_opportunities)：\n"
            "  1. 引用幻觉物理拦截：逐项校验 evidence_ids 是否落在本赛道 valid_ev_ids 白名单内；\n"
            "     任意虚构或跨号引用立即丢弃并回填核验 ID。\n"
            "  2. 财务数据重锚定：强行用 Phase 1 Python 计算的权威 roi_metrics / roi_baseline 覆盖，\n"
            "     确保 LLM 无法修改哪怕小数点后一位数字。\n"
            "  3. 初始 Elo 赋分：按 1500.0 + (weighted_pillar_score - 75.0) * 4.0 为全部 16 项\n"
            "     机会计算锦标赛起始天梯分。"
        ),
    )

    # =========================================================================
    # BAND 4 (y=1748..2118): Phase 4 — Elo Tournament & Master Table Builder
    # =========================================================================
    g.add_band(
        x=60,
        y=1748,
        w=4460,
        h=370,
        title="Phase 4: AI Co-Scientist 瑞士制配对器 · Context 组装 #3 · 16 场并行 Elo 锦标赛裁决 · K=32 排位冻结与分赛道切片编译",
        accent="#1E3A8A",
    )

    n4_1 = g.add_card(
        "n4_1_swiss",
        "HARDCODED",
        x=88,
        y=1790,
        w=950,
        h=312,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[硬编码 · Python] Swiss-System 瑞士制双轮成对配对器",
        body=(
            "• 双轮赛制控制（Flagship 2 轮 × 8 对 = 16 场裁决；Fast 1 轮 8 场）：\n"
            "  - Round 1：按初始 Elo 降序排序 16 项机会，相邻两两配对 (0,1), (2,3), ..., (14,15)。\n"
            "  - Round 2：第 1 轮并行裁决完并刷新 elo_rating 后重新降序排序配对，让一线头部机会\n"
            "    与同梯队强手直接正面交锋，拉开真实区分度。\n"
            "• 原理 (Ch 21 AI Co-Scientist)：通过成对相对比较消除大模型单表一次性排序的头部偏置。"
        ),
    )

    n4_2 = g.add_card(
        "n4_2_ctx3",
        "CONTEXT_BOX",
        x=1108,
        y=1790,
        w=1200,
        h=312,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        dashed_body=True,
        title="[Context 组装 #3] 两两对抗裁判 Prompt 装配 (Elo Matchup Payload)",
        body=(
            "• 单场裁判隔离上下文（仅含对阵双方，无其他 14 项干扰）：\n"
            "  1. [Option A] vs [Option B] 标牌：opp_id、sector、horizon (3-5y/5-10y)、title。\n"
            "  2. 双方逐字不变 [ROI-CALC] 数据：CAPEX、NetCF、Payback (月)、5Y IRR、China TAM。\n"
            "  3. 双方核心工程机理：quality_yield_mechanism + industrial_upgrade_mechanism。\n"
            "• 量化权重标尺：ROI & 回本速度 (35%) ｜ 良率控制 (25%) ｜ 产业升级与中国优先 (20%) ｜ TCO与环保 (20%)。\n"
            "• 约束输出：NO_TOOL_DIRECTIVE + ELO_SCHEMA (仅返回合法 winner_id 与中文裁决理据 rationale)。"
        ),
    )

    n4_3 = g.add_card(
        "n4_3_elo_llm",
        "LLM_AGENT",
        x=2378,
        y=1790,
        w=1030,
        h=312,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[LLM 分析 #3] 16× 并行 Elo 锦标赛裁判 (2 轮 × 8 路并发)",
        body=(
            "• 调度模型：模式1 Round 1(8并发) + Round 2(8并发) 共 16 次 agent() (gemini-3.8-flash-tiered)；\n"
            "  模式2 tier=\"producer\" -> qwen3.8-max (EloPairDecision)。\n"
            "• 典型高价值跨赛道裁决（本次实测）：\n"
            "  榜首 OPP-S4-5Y-02（混合键合激光超声：4.3月回本 / 281.6% IRR / 年净现 ¥1,184万）在两轮中\n"
            "  先后击败 OPP-S3-3Y-01（SiC外延）与 OPP-S2-3Y-01（内嵌椭偏），体现超高盈利体量与原子级\n"
            "  突破的双重胜出逻辑；大模型严禁自行计算 Elo 加减分。"
        ),
    )

    n4_4 = g.add_card(
        "n4_4_table",
        "HARDCODED",
        x=3478,
        y=1790,
        w=1014,
        h=312,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[硬编码 · Python] Elo K=32 更新 · 综合排名 · 分域 Markdown 预编译",
        body=(
            "• K=32 确定性积分更新 (_update_elo)：Ea = 1 / (1 + 10^((Rb - Ra)/400))。\n"
            "• 综合排位公式 (#1 .. #16)：\n"
            "  Composite = 0.55 * weighted_pillar_score + 0.45 * (60.0 + ((Elo - Elo_min) / span) * 38.0)。\n"
            "• 不可篡改分域表格渲染器 (_fmt_roi_table, _fmt_dossiers, _fmt_storm, _fmt_vault)：\n"
            "  预先生成精准切片文本块：roi_all / power / semi、power / semi_dossiers、storm_all / power / semi、\n"
            "  elo_digest 与 ev_power / semi / all，作为 Phase 5 唯一真值数据源。"
        ),
    )

    # =========================================================================
    # BAND 5 (y=2188..2618): Phase 5 — Vol 05 (Left) | Context #4 (Mid) | 5x Synth (Right)
    # =========================================================================
    g.add_band(
        x=60,
        y=2188,
        w=4460,
        h=430,
        title="Phase 5: Zero-LLM SQLite 证据索引直出 (Vol 05) · 分卷精细裁剪 Context 组装 #4 · 5 路并行旗舰长文合成 (Vol 00–04)",
        accent="#065F46",
    )

    n5_3 = g.add_card(
        "n5_3_vol05",
        "STORAGE",
        x=88,
        y=2230,
        w=1340,
        h=370,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[硬编码 + 持久化交付] Zero-LLM Vol 05 证据索引编译器 (render_evidence_index)",
        body=(
            "• 100% 零大模型直出（物理杜绝 225 条真实 URL、日期、机构标题的改写与编造风险）：\n"
            "  由 synthesizer.py::render_evidence_index(all_records) 直接遍历 SQLite EvidenceVault 生成。\n"
            "• 确定性中国优先分节排版：\n"
            "  1. 第一节完整列出全部中国市场证据 EV-CN-001..142（142 条，Metaso / 中文权威源）。\n"
            "  2. 第二节完整列出全部全球市场证据 EV-GL-001..083（83 条，Serper / Scholar / Patents）。\n"
            "  3. 自动转义 Markdown 竖线符，附摘要前 180 字与原始可点击核验链接。\n"
            "• 输出交付物：05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md（实测 113 KB，225 条零误差全量溯源表）。"
        ),
    )

    n5_1 = g.add_card(
        "n5_1_ctx4",
        "CONTEXT_BOX",
        x=1498,
        y=2230,
        w=1480,
        h=370,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        dashed_body=True,
        title="[Context 组装 #4] 5 卷分域精确切片 Prompt 装配 (volumes_spec)",
        body=(
            "• 按卷实施【严格分域切片隔离 (Strict Context Slicing)】，防止上下文过载失焦：\n"
            "  - Vol 00 总报告：step_back_thesis + roi_all + storm_all + elo_digest + ev_all (每赛道 5 条)。\n"
            "  - Vol 01 电力能源 P1–P4：仅注入 roi_power + power_dossiers + storm_power + ev_power（零半导噪声）。\n"
            "  - Vol 02 半导体 S1–S4：仅注入 roi_semi + semi_dossiers + storm_semi + ev_semi（零电力噪声）。\n"
            "  - Vol 03 ROI与Elo专题：roi_all + elo_digest + storm_all（含 WACC=10% 方法论与 CFO 算账模版）。\n"
            "  - Vol 04 技术平台与出海手册：roi_all + power/semi_dossiers[:3800] + storm_all + ev_all。\n"
            "• 共同注入：SYNTH_RULES（CN优先、双时间窗、逐字保留 [ROI-CALC] 与 [EV-...]）+ NO_TOOL_DIRECTIVE（重修时附 critique_note）。"
        ),
    )

    n5_2 = g.add_card(
        "n5_2_synth",
        "LLM_AGENT",
        x=3048,
        y=2230,
        w=1444,
        h=370,
        hdr_h=44,
        hdr_font=15,
        body_font=14,
        title="[LLM 分析 #4] 5× 并行旗舰长文合成智能体 (Synthesizer 00–04)",
        body=(
            "• 并发架构（麦肯锡 / SEMI / 中金行研旗舰标准）：\n"
            "  - 模式1 (Phase 5)：5 路全并发 agent(model=\"pro\", schema=string) -> gemini-3.8-flash-tiered。\n"
            "  - 模式2 (nodes/synthesizer.py)：5 路并发 qwen3.8-max (max_tokens=7500, timeout=300s)。\n"
            "• 本次班次实测产出（总计 231 KB，五卷正文去重精确引用 81 个 [EV-...] 编号、80 处 [ROI-CALC]）：\n"
            "  1. 00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md (32 KB · 含跨赛道平台复用 Mermaid 图)\n"
            "  2. 01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md (65 KB · P1–P4 四节闭环研报)\n"
            "  3. 02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md (52 KB · S1–S4 四节闭环研报)\n"
            "  4. 03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md (31 KB) & 04_STRATEGY_PLAYBOOK.md (51 KB)"
        ),
    )

    # =========================================================================
    # BAND 6 (y=2688..3258): Phase 6 & 7 — Critic, Corrective RAG, Judge, Final
    # =========================================================================
    g.add_band(
        x=60,
        y=2688,
        w=4460,
        h=570,
        title="Phase 6 & 7: 确定性正则审计 · 异构 Critic 反思闭环 · Corrective RAG / 定向重修路由 · Stage-Gate 100分裁判 · 终稿编译落盘",
        accent="#9F1239",
    )

    # Upper Row (y=2728, h=218)
    n6_1 = g.add_card(
        "n6_1_det",
        "HARDCODED",
        x=88,
        y=2728,
        w=820,
        h=218,
        hdr_h=42,
        hdr_font=14,
        body_font=13,
        title="[硬编码] 契约正则核验与头尾摘要截取",
        body=(
            "• _previews_and_checks / deterministic_contract_checks：\n"
            "  - 正则 EV-(CN|GL)-\\d{3} 核验去重引用数（本次 81 条）。\n"
            "  - 统计 [ROI-CALC] 锚点数（80 处）、CN 占比 (63.11%) 与 5 卷长度。\n"
            "• 上下文压缩保护：每卷仅截取 前 2,200 字 + 尾 800 字 送审，\n"
            "  防止 231 KB 全文塞爆审查上下文窗导致注意力退化。"
        ),
    )

    n6_2 = g.add_card(
        "n6_2_ctx5",
        "CONTEXT_BOX",
        x=958,
        y=2728,
        w=920,
        h=218,
        hdr_h=42,
        hdr_font=14,
        body_font=13,
        dashed_body=True,
        title="[Context 组装 #5] 异构 Critic 审稿载荷",
        body=(
            "• 组装送交 Critic 的 4 项审计材料：\n"
            "  1. det_summary JSON (Vault 统计 / 引用数 / 财务标签数 / 各卷长)。\n"
            "  2. 五卷 Head 2200 + Tail 800 拼装摘要文本 (previews)。\n"
            "  3. 五项契约刚性准则（先中国后全球、双时间窗、物理机制精确等）。\n"
            "  4. NO_TOOL_DIRECTIVE + CRITIC_SCHEMA / CritiqueVerdict。"
        ),
    )

    n6_3 = g.add_card(
        "n6_3_critic",
        "LLM_AGENT",
        x=1928,
        y=2728,
        w=960,
        h=218,
        hdr_h=42,
        hdr_font=14,
        body_font=13,
        title="[LLM 分析 #5] 异构 Chief Reviewer (Critic)",
        body=(
            "• 角色：Metrology Fellow & Industrial PE Partner 联合审稿人。\n"
            "• 底座：模式1 gemini-3.8-flash-tiered ｜ 模式2 跨家族 deepseek-v4-pro。\n"
            "• 本次实测 (native-88e91cf7)：首轮判定 decision=\"pass\"，\n"
            "  overall_confidence = 98.5，仅附 2 项供应链与国际专利长期\n"
            "  minor 观察建议，未触发重写。"
        ),
    )

    n6_4 = g.add_card(
        "n6_4_router",
        "GATE",
        x=2938,
        y=2728,
        w=610,
        h=218,
        hdr_h=42,
        hdr_font=14,
        body_font=13,
        title="[条件路由] route_after_critic",
        body=(
            "• 防死循环熔断 (loop_count <= max_loops, 默认 2 次)。\n"
            "• 3 路确定性条件分流：\n"
            "  1. needs_more_evidence (LangGraph) → 补搜。\n"
            "  2. needs_rewrite → 并行重修受损分卷。\n"
            "  3. pass → 直接进入 Stage-Gate 独立终审裁判。"
        ),
    )

    n6_5 = g.add_card(
        "n6_5_crag",
        "HARDCODED",
        x=3748,
        y=2728,
        w=744,
        h=218,
        hdr_h=42,
        hdr_font=14,
        body_font=13,
        title="[硬编码 · 条件分支] Corrective RAG 定向补搜",
        body=(
            "• node_corrective_rag_refill (模式2 LangGraph)：\n"
            "  - 提取 gap_queries[:4] 并用 SHA-1(geo:query) 核验防重复查询。\n"
            "  - 调度 DualEngineSearchRouter 定向补采并 Upsert 写入\n"
            "    EvidenceVault，经右侧闭环回流总线重触发 Phase 5 合成。"
        ),
    )

    # Lower Row (y=3020, h=222)
    n6_6 = g.add_card(
        "n6_6_reviser",
        "LLM_AGENT",
        x=88,
        y=3020,
        w=1010,
        h=222,
        hdr_h=42,
        hdr_font=14,
        body_font=13,
        title="[Context #6 + LLM #6] 定向分卷重写并行智能体 (Reviser 00–04)",
        body=(
            "• 触发门限：仅当 decision == \"needs_rewrite\" 时按需唤醒（本次 pass 跳过，执行 0 次）。\n"
            "• Context #6 精准切片：按 issues[].section 前缀只锁定问题分卷，注入整改清单\n"
            "  issues_txt + 该卷完整当前草稿 volumes[spec[0]] + [EV-...]/[ROI-CALC] 防篡改指令。\n"
            "• 重写后重新运行 _previews_and_checks() 刷新统计与摘要，送交 Stage-Gate Judge。"
        ),
    )

    n6_7 = g.add_card(
        "n6_7_ctx7",
        "CONTEXT_BOX",
        x=1158,
        y=3020,
        w=1050,
        h=222,
        hdr_h=42,
        hdr_font=14,
        body_font=13,
        dashed_body=True,
        title="[Context 组装 #7] Stage-Gate 独立裁判 Prompt 装配",
        body=(
            "• Ch 19 终审裁判载荷（量化硬指标与定性摘要合一）：\n"
            "  1. det_summary / vault_stats (225 证据 / CN 63.11% / 81 引用 / 80 [ROI-CALC])。\n"
            "  2. Critic 终审评语摘要 + 5 卷头尾拼装预览 (previews)。\n"
            "  3. 5×20 分仲裁 Rubric（中国优先、双时间窗、物理机理、ROI与升级、引用与行文）+\n"
            "     NO_TOOL_DIRECTIVE + JUDGE_SCHEMA (JudgeRubricScores)。"
        ),
    )

    n6_8 = g.add_card(
        "n6_8_judge",
        "LLM_AGENT",
        x=2268,
        y=3020,
        w=1030,
        h=222,
        hdr_h=42,
        hdr_font=14,
        body_font=13,
        title="[LLM 分析 #7] Stage-Gate Quality Judge (Ch 19 独立裁判)",
        body=(
            "• 执行底座：模式1 gemini-3.8-flash-tiered ｜ 模式2 deepseek-v4-pro。\n"
            "• 独立仲裁实测结果 (native-88e91cf7)：100.0 / 100（门禁 >= 85 通过）：\n"
            "  中国优先 20.0 + 双时间窗 20.0 + 物理精度 20.0 + ROI与升级 20.0 + 引用行文 20.0。\n"
            "• 输出行长级结论 executive_verdict、5 项核心优势与 3 项产业链残余风险。"
        ),
    )

    n6_9 = g.add_card(
        "n6_9_fin",
        "HARDCODED",
        x=3358,
        y=3020,
        w=1134,
        h=222,
        hdr_h=42,
        hdr_font=14,
        body_font=13,
        title="[硬编码 + 终稿归档] finalize-native 与全套交付物 (00–08)",
        body=(
            "• cli.py::_cmd_finalize_native 终审校验防线：\n"
            "  1. 按实际通过白名单的 len(cleaned_evs) 确定性重算终审支柱分与 Elo 排名；\n"
            "  2. 强制 Python 精确重算 5 项评分和 (exact_sum = 100.0)，消除大模型算术漂移；\n"
            "  3. 输出至 outputs/power_semiconductor_online_testing_2026_2036/ (00–08 全套交付物)。"
        ),
    )

    # =========================================================================
    # Branch Pills (perfectly aligned to ports -> ZERO backtracking!)
    # =========================================================================
    # N6.4 right x=3548, N6.5 left x=3748 -> 200px wide gutter!
    p_crag = g.add_pill(
        "branch_crag",
        x=3562,
        y=2820,
        w=172,
        h=34,
        text="needs_more_evidence",
        fill="#FFF1F2",
        stroke="#9F1239",
        font_color="#881337",
        font_size=12,
    )

    # Center p_rew on N6.6 top center (x=593) & p_pass on N6.7 top center (x=1683)
    p_rew = g.add_pill(
        "branch_rew",
        x=503,
        y=2966,
        w=180,
        h=32,
        text="needs_rewrite (0次)",
        fill="#FFF1F2",
        stroke="#9F1239",
        font_color="#881337",
        font_size=12,
    )
    p_pass = g.add_pill(
        "branch_pass",
        x=1593,
        y=2966,
        w=180,
        h=32,
        text="pass (置信度 98.5)",
        fill="#ECFDF5",
        stroke="#059669",
        font_color="#064E3B",
        font_size=12,
    )

    p_refill = g.add_pill(
        "bus_refill",
        x=4534,
        y=2560,
        w=132,
        h=42,
        text="补搜入库并\n重触发合成",
        fill="#FFF1F2",
        stroke="#E11D48",
        font_color="#881337",
        font_size=12,
    )

    p_vault_bus = g.add_pill(
        "vault_bus",
        x=120,
        y=766,
        w=290,
        h=32,
        text="SQLite EvidenceVault 直供下游通道",
        fill="#ECFDF5",
        stroke="#059669",
        font_color="#064E3B",
        font_size=12,
    )

    # =========================================================================
    # Orthogonal Connectors (ZERO edge labels, ZERO box crossings!)
    # =========================================================================
    boxes = g.boxes
    NAVY = "#1E3A8A"
    PURPLE = "#6D28D9"
    AMBER = "#D97706"
    GREEN = "#059669"
    CRIMSON = "#BE123C"

    # Band 1 internal flow
    g.add_edge("b1_12", n1_1, n1_2, [_mid_right(boxes[n1_1]), _mid_left(boxes[n1_2])], color=NAVY)
    g.add_edge("b1_23", n1_2, n1_3, [_mid_right(boxes[n1_2]), _mid_left(boxes[n1_3])], color=NAVY)
    g.add_edge("b1_34", n1_3, n1_4, [_mid_right(boxes[n1_3]), _mid_left(boxes[n1_4])], color=NAVY)

    # Band 1 -> Band 2
    n14_b = _mid_bot(boxes[n1_4])
    n21_t = _mid_top(boxes[n2_1])
    g.add_edge("b1_to_b2", n1_4, n2_1, [n14_b, (n14_b[0], 782), (n21_t[0], 782), n21_t], color=NAVY)

    # Band 2 internal flow
    g.add_edge("b2_12", n2_1, n2_2, [_mid_right(boxes[n2_1]), _mid_left(boxes[n2_2])], color=AMBER, dashed=True)
    g.add_edge("b2_23", n2_2, n2_3, [_mid_right(boxes[n2_2]), _mid_left(boxes[n2_3])], color=PURPLE)
    g.add_edge("b2_34", n2_3, n2_4, [_mid_right(boxes[n2_3]), _mid_left(boxes[n2_4])], color=NAVY)

    # Band 2 -> Band 3
    n24_b = _mid_bot(boxes[n2_4])
    n31_t = _mid_top(boxes[n3_1])
    g.add_edge("b2_to_b3", n2_4, n3_1, [n24_b, (n24_b[0], 1213), (n31_t[0], 1213), n31_t], color=NAVY)

    # Outer Left Vault Bus -> Pill -> N5.3 (Vol 05) & N3.2 (Context #2)
    n13_b = _mid_bot(boxes[n1_3])
    pb_r = _mid_right(boxes[p_vault_bus])
    pb_l = _mid_left(boxes[p_vault_bus])
    pb_b = _mid_bot(boxes[p_vault_bus])
    g.add_edge(
        "vault_to_pill",
        n1_3,
        p_vault_bus,
        [n13_b, (n13_b[0], 756), (pb_r[0] + 24, 756), (pb_r[0] + 24, pb_r[1]), pb_r],
        color=GREEN,
        dashed=True,
    )
    n53_l = _mid_left(boxes[n5_3])
    g.add_edge(
        "vault_pill_to_vol05",
        p_vault_bus,
        n5_3,
        [pb_l, (32, pb_l[1]), (32, n53_l[1]), n53_l],
        color=GREEN,
        dashed=True,
    )
    n32_t = _mid_top(boxes[n3_2])
    g.add_edge(
        "vault_pill_to_ctx2",
        p_vault_bus,
        n3_2,
        [pb_b, (pb_b[0], 804), (46, 804), (46, 1198), (n32_t[0], 1198), n32_t],
        color=AMBER,
        dashed=True,
    )

    # Band 3 internal flow
    g.add_edge("b3_12", n3_1, n3_2, [_mid_right(boxes[n3_1]), _mid_left(boxes[n3_2])], color=AMBER, dashed=True)
    g.add_edge("b3_23", n3_2, n3_3, [_mid_right(boxes[n3_2]), _mid_left(boxes[n3_3])], color=PURPLE)
    g.add_edge("b3_34", n3_3, n3_4, [_mid_right(boxes[n3_3]), _mid_left(boxes[n3_4])], color=NAVY)

    # Band 3 -> Band 4
    n34_b = _mid_bot(boxes[n3_4])
    n41_t = _mid_top(boxes[n4_1])
    g.add_edge("b3_to_b4", n3_4, n4_1, [n34_b, (n34_b[0], 1713), (n41_t[0], 1713), n41_t], color=NAVY)

    # Band 4 internal flow
    g.add_edge("b4_12", n4_1, n4_2, [_mid_right(boxes[n4_1]), _mid_left(boxes[n4_2])], color=AMBER, dashed=True)
    g.add_edge("b4_23", n4_2, n4_3, [_mid_right(boxes[n4_2]), _mid_left(boxes[n4_3])], color=PURPLE)
    g.add_edge("b4_34", n4_3, n4_4, [_mid_right(boxes[n4_3]), _mid_left(boxes[n4_4])], color=NAVY)

    # Band 4 -> Band 5
    n44_b = _mid_bot(boxes[n4_4])
    n51_t = _mid_top(boxes[n5_1])
    g.add_edge("b4_to_b5", n4_4, n5_1, [n44_b, (n44_b[0], 2153), (n51_t[0], 2153), n51_t], color=AMBER, dashed=True)

    # Band 5 internal flow
    g.add_edge("b5_12", n5_1, n5_2, [_mid_right(boxes[n5_1]), _mid_left(boxes[n5_2])], color=PURPLE)

    # Band 5 -> Band 6
    n52_b = _mid_bot(boxes[n5_2])
    n61_t = _mid_top(boxes[n6_1])
    g.add_edge("b5_to_b6_det", n5_2, n6_1, [n52_b, (n52_b[0], 2653), (n61_t[0], 2653), n61_t], color=NAVY)

    # Band 5 (Vol 05) -> Outer Left Bus -> Bottom Bus -> N6.9 finalize
    n53_b = _mid_bot(boxes[n5_3])
    n69_b = _mid_bot(boxes[n6_9])
    g.add_edge(
        "vol05_to_finalize",
        n5_3,
        n6_9,
        [n53_b, (n53_b[0], 2668), (22, 2668), (22, 3280), (n69_b[0], 3280), n69_b],
        color=GREEN,
        dashed=True,
    )

    # Band 6 Upper Row horizontal flow
    g.add_edge("b6_12", n6_1, n6_2, [_mid_right(boxes[n6_1]), _mid_left(boxes[n6_2])], color=AMBER, dashed=True)
    g.add_edge("b6_23", n6_2, n6_3, [_mid_right(boxes[n6_2]), _mid_left(boxes[n6_3])], color=PURPLE)
    g.add_edge("b6_34", n6_3, n6_4, [_mid_right(boxes[n6_3]), _mid_left(boxes[n6_4])], color=CRIMSON)

    # Router branches (zero interior crossing!)
    g.add_edge("b6_4_crag_p", n6_4, p_crag, [_mid_right(boxes[n6_4]), _mid_left(boxes[p_crag])], color=CRIMSON)
    g.add_edge("b6_crag_p_5", p_crag, n6_5, [_mid_right(boxes[p_crag]), _mid_left(boxes[n6_5])], color=CRIMSON)

    r_b_left = (boxes[n6_4].x + 180, boxes[n6_4].y + boxes[n6_4].h)
    r_b_right = (boxes[n6_4].x + 430, boxes[n6_4].y + boxes[n6_4].h)
    prew_t = _mid_top(boxes[p_rew])
    prew_b = _mid_bot(boxes[p_rew])
    ppass_r = _mid_right(boxes[p_pass])
    ppass_b = _mid_bot(boxes[p_pass])
    n66_t = _mid_top(boxes[n6_6])
    n67_t = _mid_top(boxes[n6_7])

    g.add_edge(
        "b6_4_to_rew_p",
        n6_4,
        p_rew,
        [r_b_left, (r_b_left[0], 2956), (prew_t[0], 2956), prew_t],
        color=CRIMSON,
    )
    g.add_edge("b6_rew_p_to_6", p_rew, n6_6, [prew_b, n66_t], color=CRIMSON)

    g.add_edge(
        "b6_4_to_pass_p",
        n6_4,
        p_pass,
        [r_b_right, (r_b_right[0], ppass_r[1]), ppass_r],
        color=GREEN,
    )
    # Exit p_pass cleanly from BOTTOM straight into N6.7 top (exact same X=1683, ZERO interior crossing!)
    g.add_edge("b6_pass_p_to_7", p_pass, n6_7, [ppass_b, n67_t], color=GREEN)

    # Band 6 Lower Row horizontal flow
    g.add_edge("b6_67", n6_6, n6_7, [_mid_right(boxes[n6_6]), _mid_left(boxes[n6_7])], color=AMBER, dashed=True)
    g.add_edge("b6_78", n6_7, n6_8, [_mid_right(boxes[n6_7]), _mid_left(boxes[n6_8])], color=PURPLE)
    g.add_edge("b6_89", n6_8, n6_9, [_mid_right(boxes[n6_8]), _mid_left(boxes[n6_9])], color=NAVY)

    # Outer Right Feedback Bus: N6.5 (CRAG) -> p_refill -> N5.2 & N1.3 Vault
    n65_r = _mid_right(boxes[n6_5])
    pref_b = _mid_bot(boxes[p_refill])
    pref_t = _mid_top(boxes[p_refill])
    pref_r = _mid_right(boxes[p_refill])
    n52_r = _mid_right(boxes[n5_2])
    n13_t = _mid_top(boxes[n1_3])
    g.add_edge("crag_to_pill", n6_5, p_refill, [n65_r, (pref_b[0], n65_r[1]), pref_b], color=CRIMSON, dashed=True)
    g.add_edge("crag_pill_to_synth", p_refill, n5_2, [pref_t, (pref_t[0], n52_r[1]), n52_r], color=CRIMSON, dashed=True)
    g.add_edge(
        "crag_pill_to_vault",
        p_refill,
        n1_3,
        [pref_r, (4662, pref_r[1]), (4662, 338), (n13_t[0], 338), n13_t],
        color=CRIMSON,
        dashed=True,
    )

    return g.build_xml(), len(g.boxes), len(g.edges)


def main() -> None:
    xml_text, n_boxes, n_edges = build_diagram()
    DOCS_DRAWIO.parent.mkdir(parents=True, exist_ok=True)
    DOCS_DRAWIO.write_text(xml_text, encoding="utf-8")
    OUT_DRAWIO.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DOCS_DRAWIO, OUT_DRAWIO)
    print(
        f"Generated A0 draw.io successfully: boxes={n_boxes}, edges={n_edges}, "
        f"geometry_audit=PASS -> {DOCS_DRAWIO} & {OUT_DRAWIO}"
    )


if __name__ == "__main__":
    main()
