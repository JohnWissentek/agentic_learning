#!/usr/bin/env python3
"""Generate Clean, Uncluttered Topology Diagram for V&F China CCS/CCUS Multi-Agent Workflow.

Separates pure control-flow topology (Left execution spine + Parallel fan-out + Bounded Critic Loop)
from Context Assembly & Prompt Payload Contracts (Decoupled Right Reference Sidebar), exporting:
- `docs/02_CLEAN_WORKFLOW_TOPOLOGY.{drawio,svg,pdf}`
- `../research_outputs/07_WORKFLOW_EXECUTION_TOPOLOGY.{drawio,svg,pdf}`
"""

from __future__ import annotations

import math
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DOCS_DRAWIO = BASE_DIR / "docs/02_CLEAN_WORKFLOW_TOPOLOGY.drawio"
OUT_DRAWIO = (BASE_DIR / "../research_outputs/07_WORKFLOW_EXECUTION_TOPOLOGY.drawio").resolve()
DRAWIO_BIN = Path("/Applications/draw.io.app/Contents/MacOS/draw.io")

CANVAS_W = 2860
CANVAS_H = 2120

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
        return font_size * 1.05
    if ch in "WM@%#&":
        return font_size * 0.78
    if ch.isupper() or ch in "[]{}()/\\":
        return font_size * 0.65
    return font_size * 0.55


def estimate_wrapped_height(
    text: str, width_px: int, font_size: int, pad_lr: int = 26, pad_tb: int = 16, line_mult: float = 1.34
) -> tuple[int, int]:
    usable_w = max(80.0, float(width_px - pad_lr))
    total_lines = 0
    for para in text.split("\n"):
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
    return total_lines, math.ceil(total_lines * font_size * line_mult) + pad_tb


@dataclass
class RectBox:
    box_id: str
    kind: str
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
                "style": "rounded=1;arcSize=2;whiteSpace=wrap;html=0;fillColor=#FFFFFF;strokeColor=#CBD5E1;strokeWidth=2;",
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(frame, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
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
        ET.SubElement(ribbon, "mxGeometry", {"x": str(x + 12), "y": str(y + 8), "width": str(w - 24), "height": "32", "as": "geometry"})
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
        hdr_font: int = 14,
        body_font: int = 13,
    ) -> str:
        st = STYLES[kind]
        _, t_need = estimate_wrapped_height(title, w, hdr_font, pad_lr=22, pad_tb=8, line_mult=1.22)
        if t_need > hdr_h:
            raise AssertionError(f"Header overflow `{key}`: need {t_need} > {hdr_h}")
        _, b_need = estimate_wrapped_height(body, w, body_font, pad_lr=26, pad_tb=16, line_mult=1.34)
        if b_need > (h - hdr_h):
            raise AssertionError(f"Body overflow `{key}`: need {b_need} > {h - hdr_h}")

        oid = f"node_{key}"
        outline = ET.Element(
            "mxCell",
            {
                "id": oid,
                "value": "",
                "style": f"rounded=1;arcSize=4;whiteSpace=wrap;html=0;fillColor={st['body_fill']};strokeColor={st['body_stroke']};strokeWidth=2;",
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(outline, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        self.fg_cells.append(outline)

        hdr = ET.Element(
            "mxCell",
            {
                "id": f"{oid}_hdr",
                "value": title,
                "style": (
                    f"rounded=0;whiteSpace=wrap;html=0;fillColor={st['hdr_fill']};strokeColor={st['hdr_stroke']};"
                    f"fontColor={st['hdr_font']};fontStyle=1;fontSize={hdr_font};align=left;verticalAlign=middle;"
                    "spacingLeft=12;spacingRight=10;overflow=hidden;"
                ),
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(hdr, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(hdr_h), "as": "geometry"})
        self.fg_cells.append(hdr)

        bcell = ET.Element(
            "mxCell",
            {
                "id": f"{oid}_body",
                "value": body,
                "style": (
                    f"rounded=0;whiteSpace=wrap;html=0;fillColor=none;strokeColor=none;"
                    f"fontColor={st['body_font']};fontSize={body_font};align=left;verticalAlign=top;"
                    "spacingLeft=12;spacingRight=12;spacingTop=8;spacingBottom=8;overflow=hidden;"
                ),
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(bcell, "mxGeometry", {"x": str(x), "y": str(y + hdr_h), "width": str(w), "height": str(h - hdr_h), "as": "geometry"})
        self.fg_cells.append(bcell)
        self.boxes[key] = RectBox(key, "card", x, y, w, h)
        return key

    def add_pill(self, key: str, text: str, x: int, y: int, w: int, h: int, fill: str, stroke: str, font_color: str) -> str:
        pid = f"pill_{key}"
        p = ET.Element(
            "mxCell",
            {
                "id": pid,
                "value": text,
                "style": (
                    f"rounded=1;arcSize=50;whiteSpace=wrap;html=0;fillColor={fill};"
                    f"strokeColor={stroke};strokeWidth=1.5;fontColor={font_color};"
                    "fontStyle=1;fontSize=12;align=center;verticalAlign=middle;overflow=hidden;"
                ),
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(p, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        self.fg_cells.append(p)
        self.boxes[key] = RectBox(key, "pill", x, y, w, h)
        return key

    def add_edge(self, src: str, dst: str, pts: list[tuple[int, int]], color: str = "#334155", dashed: bool = False, stroke_w: float = 2.6) -> None:
        eid = self.next_id("edge")
        dash_css = "dashed=1;dashPattern=8 5;" if dashed else ""
        cell = ET.Element(
            "mxCell",
            {
                "id": eid,
                "value": "",
                "style": (
                    f"edgeStyle=none;rounded=0;orthogonalLoop=1;jettySize=auto;html=0;"
                    f"strokeColor={color};strokeWidth={stroke_w};{dash_css}"
                    "endArrow=block;endFill=1;endSize=8;"
                ),
                "edge": "1",
                "parent": "1",
            },
        )
        geo = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        ET.SubElement(geo, "mxPoint", {"x": str(pts[0][0]), "y": str(pts[0][1]), "as": "sourcePoint"})
        ET.SubElement(geo, "mxPoint", {"x": str(pts[-1][0]), "y": str(pts[-1][1]), "as": "targetPoint"})
        if len(pts) > 2:
            arr = ET.SubElement(geo, "Array", {"as": "points"})
            for px, py in pts[1:-1]:
                ET.SubElement(arr, "mxPoint", {"x": str(px), "y": str(py)})
        self.edge_cells.append(cell)
        self.edges.append(EdgeRoute(eid, src, dst, pts, color, dashed, stroke_w))

    def validate_no_overlaps(self) -> None:
        boxes = list(self.boxes.values())
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if not (a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y):
                    raise AssertionError(f"Box overlap: {a.box_id} vs {b.box_id}")

    def build_xml(self) -> ET.ElementTree:
        self.validate_no_overlaps()
        mxfile = ET.Element("mxfile", {"host": "app.diagrams.net", "version": "24.7.17"})
        diag = ET.SubElement(mxfile, "diagram", {"id": "vf-ccus-clean", "name": "VF-CCUS-Workflow-Topology"})
        model = ET.SubElement(
            diag,
            "mxGraphModel",
            {"dx": "1400", "dy": "900", "grid": "1", "gridSize": "10", "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1", "page": "1", "pageScale": "1", "pageWidth": str(self.width), "pageHeight": str(self.height), "background": "#F8FAFC"},
        )
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", {"id": "0"})
        ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
        for c in self.bg_cells + self.fg_cells + self.edge_cells:
            root.append(c)
        return ET.ElementTree(mxfile)


def mid_top(b: RectBox) -> tuple[int, int]:
    return (b.x + b.w // 2, b.y)


def mid_bot(b: RectBox) -> tuple[int, int]:
    return (b.x + b.w // 2, b.y + b.h)


def mid_right(b: RectBox) -> tuple[int, int]:
    return (b.x + b.w, b.y + b.h // 2)


def mid_left(b: RectBox) -> tuple[int, int]:
    return (b.x, b.y + b.h // 2)


def generate_all() -> None:
    d = CleanDiagramBuilder()

    # Header Banner
    d.add_card(
        "hdr_banner",
        "BANNER",
        40,
        30,
        2780,
        125,
        "奥地利 V&F IMR-MS 中国 CCS/CCUS 市场调研与双轨 GTM 多智能体协同拓扑图 (VF-CCUS-CHINA-2026-V1)",
        "遵循《Agentic Design Patterns》全书范式（Ch 1-21）| 左区：Stage 0a → Stage 7 清晰控制流主干与 Critic 有界闭环；右区：Context Assembly & 防幻觉审计契约边栏。\n"
        "图例：[深蓝]=确定性Python工具与计算 | [紫色]=多智能体认知节点 | [绿色]=Siggi语料与SQLite证据库 | [琥珀]=Context组装 | [玫红]=门禁/有界循环",
        hdr_h=40,
        hdr_font=16,
        body_font=14,
    )

    # Left Control Spine Band
    d.add_band(40, 180, 1780, 1900, "控制流主干区：Stage 0a → Stage 7 因果协同工作流与有界反思闭环", "#1E293B")

    # Stage 0a & Vault
    d.add_card(
        "s0a_siggi",
        "STORAGE",
        80,
        235,
        520,
        165,
        "Stage 0a-1：Siggi 一手资料 MCP 解析器 [确定性]",
        "• 全量解析 information_from_siggi/ 下 MD 与 PDF\n"
        "• 生成 [EV-SIGGI-001..048]：CO2Sense / QAS 架构、Thermo MAX-iR/MAX-Bev、Shell/IFE 2024 点蚀机理\n"
        "• 存入 data/vf_ccus_evidence_vault.db (WAL去重)",
        hdr_h=38,
    )
    d.add_card(
        "s0a_recon",
        "HARDCODED",
        650,
        235,
        520,
        165,
        "Stage 0a-2：中国 & 全球宏观侦察 [确定性检索]",
        "• 双引擎路由：Metaso CN 优先 / Serper GLOBAL 优先\n"
        "• 实时检索十五五 CCUS 枢纽、绿色甲醇、LCO2 船运及国标动态\n"
        "• 铸造初始 [EV-CN-*] 与 [EV-GL-*] 并记入 query_log",
        hdr_h=38,
    )
    d.add_card(
        "s0b_plan",
        "LLM_AGENT",
        1220,
        235,
        560,
        165,
        "Stage 0b：Step-Back 发现规划官 [智能体]",
        "• 零预设静态赛道，综合 EV-SIGGI + 宏观扫描结果\n"
        "• 动态聚类 5–6 条新兴赛道（S1 EOR/管道/船运、S2 绿醇、S3 捕集中试、S4 食品负向对照、竞品与PAC）\n"
        "• 锁定 DiscoveryPlan 检索词契约",
        hdr_h=38,
    )

    # Stage 1 Parallel Track Researchers
    d.add_band(75, 455, 1710, 260, "Stage 1：Parallelization 多赛道并发深挖与防幻觉入库（Ch 3 Parallel Fan-Out）", "#4338CA")
    tracks_meta = [
        ("t1", "T1 EOR/管道", "长输管道腐蚀\n& 三桶油示范"),
        ("t2", "T2 LCO2船运", "中国船厂LCO2\n& 沿海接收枢纽"),
        ("t3", "T3 绿醇/e-SAF", "Cu基催化剂防毒\n& 合成气监测"),
        ("t4", "T4 胺法/中试", "设计院中试/水泥\nTrack A 科研切入"),
        ("t5", "T5 竞品/PAC", "FTIR/GC/国产MS\n& GB/T3836小屋"),
        ("t6", "T6 食品对照", "饮料级低支付意愿\n伪需求对照检验"),
    ]
    tx = 95
    for idx, (tk, t_title, t_body) in enumerate(tracks_meta):
        d.add_card(
            tk,
            "LLM_AGENT",
            tx + idx * 280,
            508,
            262,
            182,
            t_title,
            f"• CN/GLOBAL 并发\n• 全文抓取与抽取\n• {t_body}\n• Clean IDs入库",
            hdr_h=36,
            hdr_font=13,
            body_font=12,
        )

    # Stage 2 Deterministic Sizing & Screening
    d.add_card(
        "s2_calc",
        "HARDCODED",
        80,
        775,
        1120,
        195,
        "Stage 2：Python 确定性双核引擎 [MKT-CALC] TAM/SAM/SOM + [ROI-CALC] 漏斗筛查（严禁 LLM 心算）",
        "1. [MKT-CALC] 自底向上汇总 2026–2030（十五五）与 2031–2036（十六五）低/中/高三情景台套数与万元规模；按 Track A(¥180万)/B(¥420万)/C(¥720万) 单价精准锚定。\n"
        "2. [ROI-CALC] 三情景计算客户 CAPEX、防酸蚀/防催化剂中毒/省人耗净现金流、回收期(月)、3Y ROI%、5Y IRR% 与 NPV。\n"
        "3. 反幸存者偏差门禁：显式淘汰保守回收期 > 42 个月或低支付意愿伪需求（如常规饮料级CO2抽检）进入 EliminatedWedge 保留清单。",
        hdr_h=38,
    )
    d.add_card(
        "s3_storm",
        "LLM_AGENT",
        1240,
        775,
        540,
        195,
        "Stage 3：中国买方 4 角色 STORM 压力测试 [智能体]",
        "• 三桶油/央企压缩防腐总工（H2SO4/HNO3 点蚀门禁）\n"
        "• 设计院(SEI/HQC/CPECC/天辰)分析室与EPC采购经理\n"
        "• 煤化工/水泥/绿醇项目业主 EHS 与财务 ROI 决策人\n"
        "• 大型分析小屋集成商（VF-QAS-CN 毛利与SLA）",
        hdr_h=38,
    )

    # Stage 4 Swiss Elo & Stage 5 Parallel 5-Volume Synthesis
    d.add_card(
        "s4_elo",
        "LLM_AGENT",
        80,
        1030,
        540,
        175,
        "Stage 4：瑞士轮配对 Elo 锦标赛 [Ch 20/21]",
        "• 依据 IMR-MS 物理不可替代性、[ROI-CALC] 保守韧性、近中期签约确定性进行 2 轮配对裁决\n"
        "• 55% 加权得分 + 45% 归一化 Elo 输出商业切入总榜",
        hdr_h=38,
    )
    d.add_card(
        "s5_synth",
        "LLM_AGENT",
        660,
        1030,
        1120,
        175,
        "Stage 5：5 卷旗舰交付报告并发撰写 [Ch 3 Parallel Fan-Out]",
        "• Vol 00：决策备忘录（直接回答机会/规模/竞品/GTM四大问题）  • Vol 01：市场规模测算、重点项目清单与化学腐败痛点\n"
        "• Vol 02：国内外竞品与一线 Battlecards（不含编造型号）        • Vol 03：Track A/B/C 双轨定价、PAC合作与设计院 Spec-in\n"
        "• Vol 04：30-60-90 天与 12-24 个月可审计商业落地路线图（严格原样锁定 [MKT-CALC] 与 [ROI-CALC] 数字）",
        hdr_h=38,
    )

    # Stage 6 Bounded Critic + CRAG Loop
    d.add_band(75, 1265, 1710, 320, "Stage 6：异构 Critic 有界反思闭环 + Corrective RAG 缺口补检（Ch 4 + Ch 14，Max Loops = 2）", "#9F1239")
    d.add_card(
        "s6_critic",
        "GATE",
        100,
        1320,
        740,
        220,
        "Stage 6a：程序化引用核验 + 异构 Critic 深度审计 [门禁]",
        "• Python 确定性正则核查所有 [EV-SIGGI/CN/GL-*] 是否全部真实存在于 SQLite 证据库\n"
        "• 异构推理模型核查跨卷宗数字一致性、竞品无编造、Track A/B/C 财务与BOM闭环\n"
        "• 产出 CritiqueAuditOutput（Passed 放行 OR 指定待重写卷宗 + CRAG 补检词）",
        hdr_h=38,
    )
    d.add_card(
        "s6_crag",
        "HARDCODED",
        960,
        1320,
        800,
        220,
        "Stage 6b：CRAG 缺口再检索 + 定向单卷重写 [有界 <= 2轮]",
        "• 若 Critic 标记证据缺失，自动调用 Metaso/Serper 执行最多 4 条精准补检并写入 Vault\n"
        "• 仅重生成被 Critic 点名的瑕疵卷宗（节省 >60% Token，不重新扰动已过关章节）\n"
        "• 重生成后强制回流 Stage 6a 复检，达到 max_loops=2 强制退出至 Stage 7",
        hdr_h=38,
    )

    # Stage 7 Zero-LLM Index + Judge + Final Outputs
    d.add_card(
        "s7_vol5",
        "HARDCODED",
        80,
        1645,
        540,
        185,
        "Stage 7a：Zero-LLM 全量证据索引 [确定性]",
        "• 直接读取 SQLite Vault 全量表，零 LLM 改写\n"
        "• 生成 Vol 05 可审计引用溯源索引表\n"
        "• 运行 SecretLeakGuard 扫描确保无密钥泄露",
        hdr_h=38,
    )
    d.add_card(
        "s7_judge",
        "GATE",
        660,
        1645,
        540,
        185,
        "Stage 7b：100 分制 Stage-Gate 终审门禁",
        "• 5 维度 × 20 分（中国项目落地/规模机理 rigour/竞品战卡/双轨GTM/引用完备性）\n"
        "• ≥ 85.0 分方可通过门禁并签发终稿",
        hdr_h=38,
    )
    d.add_card(
        "s7_out",
        "STORAGE",
        1240,
        1645,
        540,
        185,
        "最终交付产物集合 (research_outputs/)",
        "• 00–04 战略报告主卷 + 05 证据索引表\n"
        "• 06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json\n"
        "• 07_WORKFLOW_EXECUTION_TOPOLOGY.{drawio,svg,pdf}",
        hdr_h=38,
    )

    # Bottom governance footer inside left zone
    d.add_card(
        "footer_mode",
        "BANNER",
        80,
        1885,
        1700,
        160,
        "双运行模式完全等价性保障（Standalone LangGraph CLI 与 Antigravity Native Hybrid 共用同一 Python 脊柱）",
        "• Standalone 模式：`uv run vf-ccus-research run --profile flagship` 由 LangGraph StateGraph 调度 DashScope (qwen3.8-flash / qwen3.8-max / deepseek-v4-pro)。\n"
        "• Native Hybrid 模式：`run_workflow` 执行 `ide_workflows/antigravity_run_workflow.py`，原生 Pro/Critics 智能体经由 `vf-ccus-research` CLI 共享同一 SQLite Vault 与 [MKT-CALC]/[ROI-CALC] 计算引擎。",
        hdr_h=38,
    )

    # Right Reference Sidebar Band (Decoupled Context Assembly & Contracts)
    d.add_band(1855, 180, 965, 1900, "右区解耦边栏：上下文组装契约 (Context Assembly) 与核心工程不变式", "#B45309")

    d.add_card(
        "ctx_dual",
        "CONTEXT_BOX",
        1885,
        235,
        905,
        295,
        "契约 1：双轨混合交付与定价护栏 (discovery_scope.yaml)",
        "• Track A (奥地利原装核心主机 CO2Sense/AirSense)：¥140万–220万（基准 ¥180万），主攻科研院所/高校/催化剂与膜中试平台。\n"
        "• Track B (VF-QAS-CN 双轨本土化防爆小屋)：¥320万–550万（基准 ¥420万），进口 CO2Sense + 中国 PAC 集成商（GB/T 3836 防爆、电伴热采样、恒流切换阀、辅助 GC/NDIR/FID/P2O5/AFS汞），主攻三桶油管道/EOR、绿醇催化、国内新建装置。\n"
        "• Track C (奥地利原装 PremierGuard CCUS QAS)：¥580万–950万（基准 ¥720万），主攻外资合资沿海枢纽与国际 LCO2 船舶出口。",
        hdr_h=38,
    )
    d.add_card(
        "ctx_physics",
        "CONTEXT_BOX",
        1885,
        565,
        905,
        345,
        "契约 2：V&F IMR-MS 物理不可替代性与一手基线 ([EV-SIGGI-*])",
        "• 核心对比：29 种 CCS 关键杂质表中 IMR-MS 软电离 (~1s 响应) 直测 21/29 种；Thermo MAX-iR/MAX-Bev FTIR 无法直测 H2/N2/Ar，且综合排硫/纯度周期 ~10分钟（[EV-SIGGI-*]）。\n"
        "• Shell/IFE 2024 机理：高压 CO2 管道内 NOx (2.5ppm) + H2S (5ppm) + SOx (10ppm) + O2 (10ppm) + H2O (50ppm) 诱发自由基链式反应生成硫酸/硝酸，致碳钢点蚀 >25–1000 mm/yr（5Mtpa管道 1ppm 析出即 5,000 kg/年强酸）。\n"
        "• 欧洲已验证灯塔：Northern Lights Ph2 (>5Mtpa)、Brevik 水泥 (400ktpa, ~30s周期)、Stockholm Exergi (900ktpa, 3套QAS)、丹麦 ASV/AVV、中国厦门造 LCO2 船。",
        hdr_h=38,
    )
    d.add_card(
        "ctx_math",
        "CONTEXT_BOX",
        1885,
        945,
        905,
        335,
        "契约 3：[MKT-CALC] 与 [ROI-CALC] 确定性数学审计锁",
        "• 所有 TAM/SAM/SOM 台套数与营收规模均由 `compute_china_tam_sam_som` 按低/中/高三情景在 Python 内算出，跨越 `2026-2030` 与 `2031-2036` 双周期。\n"
        "• 所有客户回报由 `compute_roi_metrics` 按 8% 折现率计算 5 年 NPV/IRR、3 年 ROI 与回收期月数。\n"
        "• 任何大模型节点禁止篡改数字；Critic 阶段自动比对第 00/01/03 卷与 JSON 基准数值，不一致即退回重写。",
        hdr_h=38,
    )
    d.add_card(
        "ctx_guard",
        "CONTEXT_BOX",
        1885,
        1315,
        905,
        340,
        "契约 4：反伪需求与合规安全三重防线",
        "• 反幸存者偏差：保留第 2 阶段被淘汰的常规食品饮料级 CO2 离线抽检场景（S4 负向对照），向管理层诚实披露“有技术优势但客户无支付意愿”的陷阱。\n"
        "• 反型号编造：`clean_track_dossier` 在入库后立即校验证据 ID，凡证据库未出现的国产或进口设备型号一律剔除。\n"
        "• 防密钥泄露：`assert_no_secrets_leaked` 在 Stage 7 写盘前及 `pytest` 全程扫描所有文本与 JSON。",
        hdr_h=38,
    )
    d.add_card(
        "ctx_kpi",
        "STORAGE",
        1885,
        1690,
        905,
        355,
        "契约 5：Stage-Gate 量化准出基准 (100 分制 >= 85 通过)",
        "1. 中国项目与政策颗粒度 (20分)：是否具名落地三大油、煤化工、绿醇与国内船厂项目。\n"
        "2. 规模测算与化学机理深度 (20分)：[MKT-CALC] 逻辑透明性 + 腐蚀/防毒定量论证。\n"
        "3. 竞品战卡精准度 (20分)：过程质谱 vs FTIR vs 光学/GC vs 国产质谱真实优劣拆解。\n"
        "4. 双轨 GTM 与设计院可执行性 (20分)：Track A/B/C 售价/毛利/PAC伙伴/Spec-in路径。\n"
        "5. 全量证据追溯与正反客观性 (20分)：Zero-LLM 第05卷索引、无编造ID、明确标注已淘汰伪需求。",
        hdr_h=38,
    )

    # Wire clean orthogonal arrows on Left Spine
    b = d.boxes
    d.add_edge("s0a_siggi", "s0a_recon", [mid_right(b["s0a_siggi"]), mid_left(b["s0a_recon"])], "#059669")
    d.add_edge("s0a_recon", "s0b_plan", [mid_right(b["s0a_recon"]), mid_left(b["s0b_plan"])], "#2563EB")

    # Fan-out from s0b_plan bottom -> horizontal bus y=430 -> all 6 track cards
    sx, sy = mid_bot(b["s0b_plan"])
    for tk in ("t1", "t2", "t3", "t4", "t5", "t6"):
        tx, ty = mid_top(b[tk])
        d.add_edge("s0b_plan", tk, [(sx, sy), (sx, 428), (tx, 428), (tx, ty)], "#5B21B6")

    # Fan-in from track cards -> bus y=735 -> s2_calc top
    cx, cy = mid_top(b["s2_calc"])
    for tk in ("t1", "t2", "t3", "t4", "t5", "t6"):
        bx, by = mid_bot(b[tk])
        d.add_edge(tk, "s2_calc", [(bx, by), (bx, 738), (cx, 738), (cx, cy)], "#1E3A8A")

    # Stage 2 -> Stage 3 -> Stage 4 -> Stage 5 -> Stage 6a
    d.add_edge("s2_calc", "s3_storm", [mid_right(b["s2_calc"]), mid_left(b["s3_storm"])], "#1E3A8A")
    s3x, s3y = mid_bot(b["s3_storm"])
    s4x, s4y = mid_top(b["s4_elo"])
    d.add_edge("s3_storm", "s4_elo", [(s3x, s3y), (s3x, 998), (s4x, 998), (s4x, s4y)], "#5B21B6")
    d.add_edge("s4_elo", "s5_synth", [mid_right(b["s4_elo"]), mid_left(b["s5_synth"])], "#5B21B6")

    s5x, s5y = mid_bot(b["s5_synth"])
    s6ax, s6ay = mid_top(b["s6_critic"])
    d.add_edge("s5_synth", "s6_critic", [(s5x, s5y), (s5x, 1235), (s6ax, 1235), (s6ax, s6ay)], "#5B21B6")

    # Bounded Critic Loop: s6_critic <-> s6_crag
    d.add_edge("s6_critic", "s6_crag", [mid_right(b["s6_critic"]), mid_left(b["s6_crag"])], "#E11D48", dashed=True)
    c_bot_x, c_bot_y = mid_bot(b["s6_crag"])
    a_bot_x, a_bot_y = mid_bot(b["s6_critic"])
    d.add_edge("s6_crag", "s6_critic", [(c_bot_x, c_bot_y), (c_bot_x, 1565), (a_bot_x, 1565), (a_bot_x, a_bot_y)], "#E11D48", dashed=True)

    # Pills on Critic branch
    d.add_pill("p_reject", "不通过 / 补检 (≤2轮)", 845, 1392, 112, 34, "#FFE4E6", "#E11D48", "#881337")
    d.add_pill("p_pass", "Critic PASS / 达上限", 215, 1598, 170, 32, "#DCFCE7", "#16A34A", "#14532D")

    # s6_critic -> s7_vol5 -> s7_judge -> s7_out
    v5x, v5y = mid_top(b["s7_vol5"])
    d.add_edge("s6_critic", "s7_vol5", [(v5x, a_bot_y), (v5x, v5y)], "#16A34A")
    d.add_edge("s7_vol5", "s7_judge", [mid_right(b["s7_vol5"]), mid_left(b["s7_judge"])], "#1E3A8A")
    d.add_edge("s7_judge", "s7_out", [mid_right(b["s7_judge"]), mid_left(b["s7_out"])], "#059669")

    tree = d.build_xml()
    DOCS_DRAWIO.parent.mkdir(parents=True, exist_ok=True)
    OUT_DRAWIO.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(DOCS_DRAWIO), encoding="utf-8", xml_declaration=True)
    shutil.copy2(DOCS_DRAWIO, OUT_DRAWIO)

    if DRAWIO_BIN.exists():
        for target_drawio in (DOCS_DRAWIO, OUT_DRAWIO):
            for fmt in ("svg", "pdf"):
                out_file = target_drawio.with_suffix(f".{fmt}")
                subprocess.run(
                    [str(DRAWIO_BIN), "-x", "-f", fmt, "-o", str(out_file), str(target_drawio)],
                    check=True,
                    capture_output=True,
                )
    print(f"Clean topology generated & exported: {DOCS_DRAWIO} and {OUT_DRAWIO}")


if __name__ == "__main__":
    generate_all()
