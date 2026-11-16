#!/usr/bin/env python3
"""Generate Clean Topology Diagram for BoilerSense-AI™ Multi-Agent IPD Product R&D Workflow.

Exports:
- `docs/01_MULTI_AGENT_IPD_WORKFLOW_TOPOLOGY.{drawio,svg,pdf}`
- `<output_dir>/09_MULTI_AGENT_IPD_WORKFLOW_TOPOLOGY.{drawio,svg,pdf}`
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DOCS_DRAWIO = BASE_DIR / "docs/01_MULTI_AGENT_IPD_WORKFLOW_TOPOLOGY.drawio"
DRAWIO_BIN = Path("/Applications/draw.io.app/Contents/MacOS/draw.io")

CANVAS_W = 2860
CANVAS_H = 2160

STYLES = {
    "HARDCODED": {"hdr_fill": "#1E3A8A", "hdr_stroke": "#1E3A8A", "hdr_font": "#FFFFFF", "body_fill": "#EFF6FF", "body_stroke": "#2563EB", "body_font": "#0F172A"},
    "LLM_AGENT": {"hdr_fill": "#5B21B6", "hdr_stroke": "#5B21B6", "hdr_font": "#FFFFFF", "body_fill": "#F5F3FF", "body_stroke": "#7C3AED", "body_font": "#1E1B4B"},
    "CONTEXT_BOX": {"hdr_fill": "#B45309", "hdr_stroke": "#B45309", "hdr_font": "#FFFFFF", "body_fill": "#FFFBEB", "body_stroke": "#D97706", "body_font": "#451A03"},
    "STORAGE": {"hdr_fill": "#065F46", "hdr_stroke": "#065F46", "hdr_font": "#FFFFFF", "body_fill": "#ECFDF5", "body_stroke": "#059669", "body_font": "#064E3B"},
    "GATE": {"hdr_fill": "#9F1239", "hdr_stroke": "#9F1239", "hdr_font": "#FFFFFF", "body_fill": "#FFF1F2", "body_stroke": "#E11D48", "body_font": "#4C0519"},
    "BANNER": {"hdr_fill": "#0F172A", "hdr_stroke": "#0F172A", "hdr_font": "#FFFFFF", "body_fill": "#F1F5F9", "body_stroke": "#334155", "body_font": "#0F172A"},
}


def _char_width_px(ch: str, font_size: int) -> float:
    code = ord(ch)
    if 0x4E00 <= code <= 0x9FFF or 0x3000 <= code <= 0x303F or 0xFF00 <= code <= 0xFFEF or ch in "·—–•≥≤±×→←↔【】「」":
        return font_size * 1.05
    if ch in "WM@%#&":
        return font_size * 0.78
    if ch.isupper() or ch in "[]{}()/\\":
        return font_size * 0.65
    return font_size * 0.55


def estimate_wrapped_height(text: str, width_px: int, font_size: int, pad_lr: int = 26, pad_tb: int = 16, line_mult: float = 1.34) -> tuple[int, int]:
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

    def next_id(self, prefix: str = "c") -> str:
        self._id_counter += 1
        return f"{prefix}_{self._id_counter}"

    def add_band(self, x: int, y: int, w: int, h: int, title: str, accent: str = "#334155") -> None:
        bid = self.next_id("band")
        frame = ET.Element("mxCell", {"id": bid, "value": "", "style": "rounded=1;arcSize=2;whiteSpace=wrap;html=0;fillColor=#FFFFFF;strokeColor=#CBD5E1;strokeWidth=2;", "vertex": "1", "parent": "1"})
        ET.SubElement(frame, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        self.bg_cells.append(frame)

        hdr = ET.Element("mxCell", {"id": self.next_id("bh"), "value": title, "style": f"rounded=0;whiteSpace=wrap;html=0;fillColor={accent};strokeColor=none;fontColor=#FFFFFF;fontSize=15;fontStyle=1;align=left;spacingLeft=16;", "vertex": "1", "parent": "1"})
        ET.SubElement(hdr, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": "36", "as": "geometry"})
        self.bg_cells.append(hdr)

    def add_box(self, key: str, kind: str, x: int, y: int, w: int, title: str, body: str, *, hdr_h: int = 38, body_font_size: int = 12, min_h: int = 80) -> RectBox:
        st = STYLES[kind]
        _, needed_h = estimate_wrapped_height(body, w, body_font_size, pad_lr=24, pad_tb=16)
        h = max(min_h, hdr_h + needed_h)
        gid = self.next_id("grp")
        body_cell = ET.Element("mxCell", {"id": gid, "value": body, "style": f"rounded=1;arcSize=6;whiteSpace=wrap;html=0;fillColor={st['body_fill']};strokeColor={st['body_stroke']};strokeWidth=2;fontColor={st['body_font']};fontSize={body_font_size};align=left;verticalAlign=top;spacingTop={hdr_h + 6};spacingLeft=12;spacingRight=12;spacingBottom=8;", "vertex": "1", "parent": "1"})
        ET.SubElement(body_cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        self.fg_cells.append(body_cell)

        hdr_cell = ET.Element("mxCell", {"id": self.next_id("hdr"), "value": title, "style": f"rounded=0;whiteSpace=wrap;html=0;fillColor={st['hdr_fill']};strokeColor={st['hdr_stroke']};fontColor={st['hdr_font']};fontSize=13;fontStyle=1;align=center;verticalAlign=middle;", "vertex": "1", "parent": "1"})
        ET.SubElement(hdr_cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(hdr_h), "as": "geometry"})
        self.fg_cells.append(hdr_cell)

        box = RectBox(box_id=gid, kind=kind, x=x, y=y, w=w, h=h)
        self.boxes[key] = box
        return box

    def add_pill(self, key: str, label: str, x: int, y: int, w: int, h: int, fill: str, stroke: str, font: str) -> None:
        pid = self.next_id("pill")
        cell = ET.Element("mxCell", {"id": pid, "value": label, "style": f"rounded=1;arcSize=50;whiteSpace=wrap;html=0;fillColor={fill};strokeColor={stroke};strokeWidth=1.5;fontColor={font};fontSize=11;fontStyle=1;align=center;verticalAlign=middle;", "vertex": "1", "parent": "1"})
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        self.fg_cells.append(cell)

    def add_edge(self, src_key: str, dst_key: str, points: list[tuple[int, int]], color: str, dashed: bool = False, stroke_w: float = 2.6) -> None:
        eid = self.next_id("edge")
        dash = "dashed=1;dashPattern=6 4;" if dashed else ""
        cell = ET.Element("mxCell", {"id": eid, "value": "", "style": f"edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=0;strokeColor={color};strokeWidth={stroke_w};{dash}endArrow=block;endFill=1;", "edge": "1", "parent": "1", "source": self.boxes[src_key].box_id, "target": self.boxes[dst_key].box_id})
        geom = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        if len(points) >= 2:
            ET.SubElement(geom, "mxPoint", {"x": str(points[0][0]), "y": str(points[0][1]), "as": "sourcePoint"})
            ET.SubElement(geom, "mxPoint", {"x": str(points[-1][0]), "y": str(points[-1][1]), "as": "targetPoint"})
            if len(points) > 2:
                arr = ET.SubElement(geom, "Array", {"as": "points"})
                for px, py in points[1:-1]:
                    ET.SubElement(arr, "mxPoint", {"x": str(px), "y": str(py)})
        self.edge_cells.append(cell)

    def build_xml(self) -> ET.ElementTree:
        mxfile = ET.Element("mxfile", {"host": "app.diagrams.net", "modified": "2026-11-16", "version": "24.7.17"})
        diag = ET.SubElement(mxfile, "diagram", {"id": "bfbg_ipd_topology", "name": "BoilerSense-AI Multi-Agent IPD Topology"})
        model = ET.SubElement(diag, "mxGraphModel", {"dx": "1420", "dy": "880", "grid": "1", "gridSize": "10", "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1", "page": "1", "pageScale": "1", "pageWidth": str(self.width), "pageHeight": str(self.height), "math": "0", "shadow": "0"})
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", {"id": "0"})
        ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
        bg = ET.SubElement(root, "mxCell", {"id": "bg_canvas", "value": "", "style": "rounded=0;fillColor=#F8FAFC;strokeColor=none;", "vertex": "1", "parent": "1"})
        ET.SubElement(bg, "mxGeometry", {"x": "0", "y": "0", "width": str(self.width), "height": str(self.height), "as": "geometry"})
        for el in self.bg_cells + self.edge_cells + self.fg_cells:
            root.append(el)
        return ET.ElementTree(mxfile)


def mid_right(b: RectBox) -> tuple[int, int]:
    return (b.x + b.w, b.y + b.h // 2)


def mid_left(b: RectBox) -> tuple[int, int]:
    return (b.x, b.y + b.h // 2)


def mid_top(b: RectBox) -> tuple[int, int]:
    return (b.x + b.w // 2, b.y)


def mid_bot(b: RectBox) -> tuple[int, int]:
    return (b.x + b.w // 2, b.y + b.h)


def generate_all(output_dir: Path) -> None:
    d = CleanDiagramBuilder(CANVAS_W, CANVAS_H)

    d.add_box(
        "banner",
        "BANNER",
        40,
        30,
        2780,
        "BoilerSense-AI™ 燃煤电站锅炉水冷壁 FBG 测温产品研发与量产导入多智能体拓扑图 (对齐《Agentic Design Patterns》21模式)",
        "工程分离原则: agentic_workflow/ (LangGraph + Antigravity run_workflow 编排) ↔ output/ (7卷交付 + Zero-LLM 证据索引 + 原厂PDF规格书库 + 评分遥测)\n"
        "颜色图例: 深蓝=确定性代码/计算/验真 | 紫色=多角色智能体推理/撰写 | 绿=SQLite EvidenceVault/物理PDF库 | 暗红=异构Critic/100分Stage-Gate门禁 | 琥珀=右侧独立契约栏",
        hdr_h=40,
        body_font_size=13,
    )

    # Left Execution Spine Bands
    d.add_band(40, 150, 1790, 230, "Stage 0 · 历史语料只读入库 + 宏观侦察 + 首席产品经理 Step-Back 规划 (Ch 6 / Ch 8 / App A)", "#1E3A8A")
    d.add_band(40, 405, 1790, 320, "Stage 1 · 6 角色 IPD 专家并行扇出检索 + 国际原厂 PDF 规格书联网下载 & SHA256 验真 (Ch 2 / Ch 3 / Ch 5 / Ch 14)", "#5B21B6")
    d.add_band(40, 750, 1790, 260, "Stage 2–4 · PALMs 确定性工程算账 + 内部 IPD 评审 + 电厂买方 STORM + 架构瑞士轮 Elo 锦标赛 (Ch 7 / Ch 17 / Ch 21)", "#065F46")
    d.add_band(40, 1035, 1790, 220, "Stage 5 · 7 位领域主笔并发合成交付卷宗 00_–06_ (Ch 1 Prompt Chaining + Ch 3 Parallelization)", "#5B21B6")
    d.add_band(40, 1280, 1790, 340, "Stage 6 · 程序化引用/PDF 校验 + 异构 Critic 反思 + CRAG 定向补搜重写闭环 (Ch 4 / Ch 12 / Max Loops=2)", "#9F1239")
    d.add_band(40, 1645, 1790, 260, "Stage 7 · 100分制 Stage-Gate 门禁评估 + Zero-LLM 证据索引 + Draw.io 矢量导出 (Ch 18 / Ch 19 / Ch 20)", "#0F172A")

    # Right Context & Governance Sidebar
    d.add_band(1860, 150, 960, 1755, "工程治理契约、工具协议与质量红线参考栏 (Context & Governance Sidebar)", "#B45309")

    # Stage 0 boxes
    d.add_box("s0_prior", "STORAGE", 70, 205, 490, "Stage 0a-1: 历史语料只读入库", "• 只读扫描 Boiler_FBG_Thermometry_Research/*.md\n• 写入 [EV-BASE-*] (保持原文件夹 0 修改)\n• 解除早期单一路线假定约束", min_h=145)
    d.add_box("s0_recon", "HARDCODED", 630, 205, 510, "Stage 0a-2: 宏观市场 & 器件侦察", "• Metaso (CN): 煤电三改联动/爆管痛点/竞品\n• Serper (GL): Ibsen/Santec/FBGS/Lumentum\n• 写入 SQLite EvidenceVault", min_h=145)
    d.add_box("s0_pm", "LLM_AGENT", 1210, 205, 590, "Stage 0b: 首席产品经理 (Chief PM)", "• 应用 Step-Back Prompting 分解 6 研发赛道\n• 锁定 BS-STD-600 + BS-PRO-2000 双档路线\n• 输出 ProductDiscoveryPlan JSON", min_h=145)

    # Stage 1 6 parallel track boxes + PDF fetcher
    tracks = [
        ("t1", "T1 市场政策研究员", "煤电深调峰政策\n结焦爆管需求规模\n电力招标定价带"),
        ("t2", "T2 竞品拆解专家", "理工光科/太辰光\nLuna/Omnisens\n热电偶/声学对比"),
        ("t3", "T3 光电硬件架构师", "Ibsen/Amonics/Sercalo\nSantec/FEMTO/Spectrum\nMoxa/MeanWell接口"),
        ("t4", "T4 光纤与焊接专家", "FBGS/OFS/Fibercore\n长飞碳PI与弱光栅\n15CrMoG导热块工艺"),
        ("t5", "T5 软件与锅炉AI架构师", "亚像素寻峰/样条标定\n克里金3D壁温云图\n一期旁路只读→二期闭环"),
        ("t6", "T6 NPI质量与财务专家", "650°C自动标定/老化\nIQC/IPQC/FAT/SAT SOP\n精益创业GTM与培训"),
    ]
    tx = 65
    for k, title, body in tracks:
        d.add_box(k, "LLM_AGENT", tx, 460, 240, title, body, hdr_h=34, body_font_size=11, min_h=120)
        tx += 252
    d.add_box("pdf_fetch", "HARDCODED", 1585, 460, 220, "OEM PDF 验真下载器", "• 复制11份基线PDF\n• Serper补齐工控/网关/标定炉\n• %PDF-/pypdf/SHA256校验", hdr_h=34, body_font_size=11, min_h=120)
    d.add_box("vault_sync", "STORAGE", 65, 625, 1740, "SQLite WAL EvidenceVault (bfbg_evidence_vault.db)", "统一去重并分配不可伪造溯源编码：[EV-BASE-0001..] + [EV-CN-0001..] + [EV-GL-0001..] + [EV-PDF-0001..]，并将 ≥15 份验真原厂 PDF 落盘至 output/datasheets_pdf/", hdr_h=32, body_font_size=12, min_h=75)

    # Stage 2-4 boxes
    d.add_box("s2_calc", "HARDCODED", 70, 805, 520, "Stage 2: PALMs 确定性工程与财务引擎", "• [PHY-CALC] 20-600°C漂移/链路损耗/SNR裕度\n• [BOM-CALC] Track A/B 样机-10套-50套成本与毛利\n• [FIN-CALC] & [PLANT-ROI] 5年NPV/IRR与回收期", min_h=175)
    d.add_box("s3_ipd_storm", "LLM_AGENT", 660, 805, 560, "Stage 3: 内部 IPD 评审 + 外部买方 STORM", "• 6角色IPD会: PM/硬件/AI/焊接/QA/CFO\n• 4角色电厂会: 总工/防磨点检长/网安/集团采购\n• 暴露接口盲区与招标硬门槛", min_h=175)
    d.add_box("s4_elo", "LLM_AGENT", 1290, 805, 510, "Stage 4: 5大技术路线瑞士轮 Elo 锦标赛", "• 模块化双档集成 vs 纯瑞利OFDR vs 紫外FBG\n• vs 从零画PCB vs 传统K型热电偶矩阵\n• 定量裁决胜出架构与研发周期优势", min_h=175)

    # Stage 5 boxes
    d.add_box("s5_synth", "LLM_AGENT", 70, 1090, 1730, "Stage 5: 7 角色专业主笔并行撰写交付文档 (00_ 至 06_)", "首席PM (00_立项路线图)  |  市场总监 (01_市场与竞品)  |  光电总师 (02_架构选型与双轨BOM)  |  接口主任师 (03_光电/电气/协议集成详设)\n软件AI总师 (04_寻峰算法与两阶段锅炉AI)  |  NPI质量总监 (05_装调/焊接安装/QA-QC SOP)  |  CFO与培训总监 (06_财务/GTM/工程师与销售培训)", hdr_h=36, body_font_size=12, min_h=130)

    # Stage 6 boxes
    d.add_box("s6_prog", "HARDCODED", 70, 1340, 440, "Stage 6a-1: 程序化契约审计", "• 扫描全量 [EV-*] ID 真伪\n• 检查 datasheets_pdf/*.pdf 物理存在\n• 拦截密钥泄露与空卷宗", min_h=160)
    d.add_box("s6_critic", "GATE", 575, 1340, 560, "Stage 6a-2: 异构 Critic 严苛审查", "• 核查链路预算与BOM数值一致性\n• 检查电气/光学/寄存器接口完整度\n• 缺失则判定 passed=false 触发定向修复", min_h=160)
    d.add_box("s6_crag", "LLM_AGENT", 1210, 1340, 590, "Stage 6b: CRAG 定向补搜与并行重写", "• 仅对 defect 赛道调用 gap-search 补证\n• 并行重修问题卷宗并回流复审\n• 硬上限 Max Loops = 2 防止死循环", min_h=160)

    # Stage 7 boxes
    d.add_box("s7_judge", "GATE", 70, 1705, 520, "Stage 7a: 100分制 Stage-Gate 门禁", "• 5大维度 × 20分 = 100分评审\n• 门禁及格红线 ≥ 85 分\n• 输出 08_EVALUATION_SCORECARD.json", min_h=165)
    d.add_box("s7_vol7", "HARDCODED", 660, 1705, 530, "Stage 7b: Zero-LLM 证据索引 & 矢量图导出", "• 确定性生成 07_ 全量证据与PDF SHA256台账\n• 自动调用 Draw.io CLI 渲染 09_ 与 10_ 矢量图\n• 执行 assert_no_secrets_leaked 最终守护", min_h=165)
    d.add_box("s7_out", "STORAGE", 1260, 1705, 540, "Stage 7c: 产品级交付物目录 (output/)", "• 00_~07_ 全套工程/财务/SOP/培训 Markdown\n• datasheets_pdf/ (≥15份验真原厂PDF)\n• 08_评分遥测JSON + 09_/10_架构图(.drawio/.svg/.pdf)", min_h=165)

    # Right Sidebar cards
    d.add_box("sb_patterns", "CONTEXT_BOX", 1890, 210, 900, "1. 《Agentic Design Patterns》全书核心模式落地清单", "• Ch 1-3 控制流: 8阶段管道 + Intent/Geo 路由 + 6轨道/7卷宗异步并行\n• Ch 4 反思闭环: 异构 Critic + 程序化引用/PDF存在校验 + 有界2轮重写\n• Ch 5/10/14 工具与RAG: Metaso+Serper+PDF解析器 + CRAG 缺口定向补搜\n• Ch 6/7/21 协作探索: Step-Back PM规划 + IPD内审 + 电厂STORM + Elo锦标赛\n• Ch 12/16/18/19: 三级搜索回退、高低配模型路由、密钥零泄露与100分Stage-Gate", min_h=240)
    d.add_box("sb_product", "CONTEXT_BOX", 1890, 480, 900, "2. 双档产品定位与核心选型边界 (已澄清确认)", "• 标准版 BS-STD-600 (300-600点): 丹麦 Ibsen I-MON 512 + Amonics ASE + Sercalo MEMS\n• 旗舰版 BS-PRO-2000 (1000-2000+点): Santec/Lumentum扫频 + NIST HCN气室 + FEMTO + Spectrum\n• 传感双轨: Track A (德国FBGS+OFS全进口) vs Track B (严选飞秒/DTG+本土CNC导热块)\n• 锅炉AI分步: 一期旁路只读 (DCS隔离网闸→云图/吹灰/爆管预警) → 二期闭环寻优", min_h=230)
    d.add_box("sb_calcs", "CONTEXT_BOX", 1890, 740, 900, "3. PALMs 确定性计算铁律 (严禁大模型心算)", "• [PHY-CALC] 20~600°C非线性漂移、25点间距防串扰余量、SNR Margin (dB) 与刷新周期\n• [BOM-CALC] 样机/10套/50套主机+传感BOM、单点COGS、售价与毛利率矩阵\n• [FIN-CALC] 80万精益启动CAPEX、Bear/Base/Bull 5年营收/EBITDA/保本点/NPV/IRR\n• [PLANT-ROI] 600MW & 1000MW 机组避爆管/节汽/降煤耗收益与保守-乐观回收期", min_h=215)
    d.add_box("sb_pdf", "CONTEXT_BOX", 1890, 985, 900, "4. 原厂 PDF 规格书验真与防篡改硬门禁", "• 第一批: 11 份国际光学/采集/光纤基线 PDF 从历史研究目录只读拷贝并校验\n• 第二批: Serper `filetype:pdf` 补齐工控机、Moxa网关、MeanWell电源、AMETEK标定炉等\n• 物理验真: 魔数 `%PDF-` + 单文件 <9.5MB + `pypdf` 可读页数>=1 + SHA256 入库 [EV-PDF-*]", min_h=210)
    d.add_box("sb_guard", "CONTEXT_BOX", 1890, 1225, 900, "5. Ch 18 工程安全护栏与自动化测试基线", "• 禁止在 Prompt/日志/输出文件中出现任何 API Key 子串 (`assert_no_secrets_leaked`)\n• 严禁修改原目录 `Boiler_FBG_Thermometry_Research/` 内任何文件\n• 3 层离线 `pytest` 测试: 物理财务数学测试 + Vault/PDF魔数测试 + Mock LLM 全图轨迹", min_h=205)
    d.add_box("sb_score", "CONTEXT_BOX", 1890, 1460, 900, "6. Stage-Gate 100 分制交付红线 (≥ 85 分通过)", "• 1) 市场与竞品深度 (20分)   • 2) 硬件选型与接口详尽度 (20分)\n• 3) 解调算法与两阶段锅炉AI (20分)   • 4) NPI装调、焊接与QA/QC SOP (20分)\n• 5) 双轨BOM成本、5年财务、GTM营销与培训 + 零幻觉溯源 (20分)", min_h=205)

    # Wiring
    b = d.boxes
    d.add_edge("s0_prior", "s0_recon", [mid_right(b["s0_prior"]), mid_left(b["s0_recon"])], "#1E3A8A")
    d.add_edge("s0_recon", "s0_pm", [mid_right(b["s0_recon"]), mid_left(b["s0_pm"])], "#2563EB")

    px, py = mid_bot(b["s0_pm"])
    for k in ("t1", "t2", "t3", "t4", "t5", "t6", "pdf_fetch"):
        tx_p, ty_p = mid_top(b[k])
        d.add_edge("s0_pm", k, [(px, py), (px, 432), (tx_p, 432), (tx_p, ty_p)], "#5B21B6")
        bx, by = mid_bot(b[k])
        d.add_edge(k, "vault_sync", [(bx, by), (bx, 608), (mid_top(b["vault_sync"])[0], 608), mid_top(b["vault_sync"])], "#059669")

    vx, vy = mid_bot(b["vault_sync"])
    cx, cy = mid_top(b["s2_calc"])
    d.add_edge("vault_sync", "s2_calc", [(vx, vy), (vx, 775), (cx, 775), (cx, cy)], "#1E3A8A")
    d.add_edge("s2_calc", "s3_ipd_storm", [mid_right(b["s2_calc"]), mid_left(b["s3_ipd_storm"])], "#1E3A8A")
    d.add_edge("s3_ipd_storm", "s4_elo", [mid_right(b["s3_ipd_storm"]), mid_left(b["s4_elo"])], "#5B21B6")

    ex, ey = mid_bot(b["s4_elo"])
    sx, sy = mid_top(b["s5_synth"])
    d.add_edge("s4_elo", "s5_synth", [(ex, ey), (ex, 1060), (sx, 1060), (sx, sy)], "#5B21B6")

    s5x, s5y = mid_bot(b["s5_synth"])
    p6x, p6y = mid_top(b["s6_prog"])
    d.add_edge("s5_synth", "s6_prog", [(s5x, s5y), (s5x, 1308), (p6x, 1308), (p6x, p6y)], "#9F1239")
    d.add_edge("s6_prog", "s6_critic", [mid_right(b["s6_prog"]), mid_left(b["s6_critic"])], "#9F1239")
    d.add_edge("s6_critic", "s6_crag", [mid_right(b["s6_critic"]), mid_left(b["s6_crag"])], "#E11D48", dashed=True)
    d.add_edge("s6_crag", "s6_critic", [mid_bot(b["s6_crag"]), (mid_bot(b["s6_crag"])[0], 1575), (mid_bot(b["s6_critic"])[0], 1575), mid_bot(b["s6_critic"])], "#E11D48", dashed=True)

    d.add_pill("p_reject", "不通过 / CRAG补检 (≤2轮)", 1142, 1398, 128, 34, "#FFE4E6", "#E11D48", "#881337")
    d.add_pill("p_pass", "PASS / 达到上限", 770, 1598, 155, 32, "#DCFCE7", "#16A34A", "#14532D")

    d.add_edge("s6_critic", "s7_judge", [(mid_bot(b["s6_critic"])[0], mid_bot(b["s6_critic"])[1]), (mid_bot(b["s6_critic"])[0], 1672), (mid_top(b["s7_judge"])[0], 1672), mid_top(b["s7_judge"])], "#16A34A")
    d.add_edge("s7_judge", "s7_vol7", [mid_right(b["s7_judge"]), mid_left(b["s7_vol7"])], "#1E3A8A")
    d.add_edge("s7_vol7", "s7_out", [mid_right(b["s7_vol7"]), mid_left(b["s7_out"])], "#059669")

    tree = d.build_xml()
    DOCS_DRAWIO.parent.mkdir(parents=True, exist_ok=True)
    out_drawio = output_dir / "09_MULTI_AGENT_IPD_WORKFLOW_TOPOLOGY.drawio"
    out_drawio.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(DOCS_DRAWIO), encoding="utf-8", xml_declaration=True)
    shutil.copy2(DOCS_DRAWIO, out_drawio)

    if DRAWIO_BIN.exists():
        for target in (DOCS_DRAWIO, out_drawio):
            for fmt in ("svg", "pdf"):
                out_f = target.with_suffix(f".{fmt}")
                subprocess.run([str(DRAWIO_BIN), "-x", "-f", fmt, "-o", str(out_f), str(target)], check=True, capture_output=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str((BASE_DIR / "../output").resolve()))
    args = parser.parse_args()
    generate_all(Path(args.output_dir).resolve())


if __name__ == "__main__":
    main()
