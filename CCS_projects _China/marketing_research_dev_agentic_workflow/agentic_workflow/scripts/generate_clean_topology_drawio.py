#!/usr/bin/env python3
"""Generate OMG UML 2.5 Behavioral State Machine Diagram for V&F China CCS/CCUS Workflow v2.0.

Strictly adheres to OMG UML 2.5 State Machine Diagram standards:
- Initial Pseudostate ● (startState, clean outgoing transition with / effect only)
- Final State ◉ (endState, zero outgoing transitions)
- Composite States (rounded containers) & Simple States (two-compartment rounded swimlanes with entry/do/exit)
- Choice Pseudostate ◇ (hollow diamond with mutually exclusive [guard] branches + explicit [else])
- Bounded loop proof: [存在硬核错误或关键缺口 且 修订次数 < 2] / 修订次数+1
- Plain Chinese business language (zero code/database/flowchart symbol mix-ins)

Exports:
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

CANVAS_W = 2400
CANVAS_H = 1660


def _char_width_px(ch: str, font_size: int) -> float:
    code = ord(ch)
    if (
        0x4E00 <= code <= 0x9FFF
        or 0x3000 <= code <= 0x303F
        or 0xFF00 <= code <= 0xFFEF
        or ch in "·—–•≥≤±×→←↔【】「」：；，。（）"
    ):
        return font_size * 1.05
    if ch in "WM@%#&":
        return font_size * 0.78
    if ch.isupper() or ch in "[]{}()/\\":
        return font_size * 0.65
    return font_size * 0.55


def estimate_wrapped_height(
    text: str, width_px: int, font_size: int, pad_lr: int = 24, pad_tb: int = 16, line_mult: float = 1.38
) -> int:
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
    return math.ceil(total_lines * font_size * line_mult) + pad_tb


@dataclass
class RectBox:
    box_id: str
    kind: str
    x: int
    y: int
    w: int
    h: int


class UML25StateMachineBuilder:
    """Deterministic Draw.io mxGraph builder for strict OMG UML 2.5 State Machine Diagrams."""

    def __init__(self, width: int = CANVAS_W, height: int = CANVAS_H) -> None:
        self.width = width
        self.height = height
        self._id_counter = 10
        self.bg_cells: list[ET.Element] = []
        self.fg_cells: list[ET.Element] = []
        self.edge_cells: list[ET.Element] = []
        self.boxes: dict[str, RectBox] = {}
        self.check_boxes: dict[str, RectBox] = {}

    def next_id(self, prefix: str = "uml") -> str:
        self._id_counter += 1
        return f"{prefix}_{self._id_counter}"

    def add_title_header(self, x: int, y: int, w: int, h: int, title: str, subtitle: str) -> None:
        tid = self.next_id("title")
        cell = ET.Element(
            "mxCell",
            {
                "id": tid,
                "value": f"{title}\n{subtitle}",
                "style": (
                    "rounded=1;arcSize=4;whiteSpace=wrap;html=0;fillColor=#0F172A;strokeColor=#0F172A;"
                    "fontColor=#FFFFFF;fontStyle=1;fontSize=16;align=left;verticalAlign=middle;"
                    "spacingLeft=18;spacingRight=18;spacingTop=8;spacingBottom=8;"
                ),
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        self.bg_cells.append(cell)

    def add_composite_state(
        self,
        key: str,
        x: int,
        y: int,
        w: int,
        h: int,
        title: str,
        *,
        stroke: str = "#475569",
        fill: str = "#F8FAFC",
    ) -> str:
        cid = f"comp_{key}"
        cell = ET.Element(
            "mxCell",
            {
                "id": cid,
                "value": title,
                "style": (
                    f"swimlane;startSize=36;rounded=1;arcSize=4;fillColor={fill};"
                    f"strokeColor={stroke};strokeWidth=2;fontColor=#0F172A;fontSize=15;fontStyle=1;"
                    "align=left;spacingLeft=14;collapsible=0;html=0;"
                ),
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        self.bg_cells.append(cell)
        self.boxes[key] = RectBox(key, "composite", x, y, w, h)
        return key

    def add_simple_state(
        self,
        key: str,
        x: int,
        y: int,
        w: int,
        h: int,
        name: str,
        activities: str,
        *,
        stroke: str = "#1E40AF",
        fill: str = "#FFFFFF",
        hdr_h: int = 34,
        font_size: int = 13,
    ) -> str:
        need_h = estimate_wrapped_height(activities, w, font_size, pad_lr=24, pad_tb=18)
        if need_h > (h - hdr_h):
            raise AssertionError(f"State `{key}` text overflow: need {need_h} > available {h - hdr_h}")

        sid = f"state_{key}"
        container = ET.Element(
            "mxCell",
            {
                "id": sid,
                "value": name,
                "style": (
                    f"swimlane;fontStyle=1;align=center;verticalAlign=top;startSize={hdr_h};"
                    f"collapsible=0;rounded=1;arcSize=10;fillColor={fill};strokeColor={stroke};"
                    f"strokeWidth=2;fontColor=#0F172A;fontSize=14;html=0;"
                ),
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(container, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        self.fg_cells.append(container)

        body = ET.Element(
            "mxCell",
            {
                "id": f"{sid}_body",
                "value": activities,
                "style": (
                    f"text;strokeColor=none;fillColor=none;align=left;verticalAlign=top;"
                    f"spacingLeft=12;spacingRight=12;spacingTop=8;spacingBottom=8;"
                    f"overflow=hidden;whiteSpace=wrap;html=0;fontColor=#1E293B;fontSize={font_size};"
                ),
                "vertex": "1",
                "parent": sid,
            },
        )
        ET.SubElement(body, "mxGeometry", {"x": "0", "y": str(hdr_h), "width": str(w), "height": str(h - hdr_h), "as": "geometry"})
        self.fg_cells.append(body)

        box = RectBox(key, "state", x, y, w, h)
        self.boxes[key] = box
        self.check_boxes[key] = box
        return key

    def add_initial(self, key: str, x: int, y: int, size: int = 32) -> str:
        nid = f"init_{key}"
        cell = ET.Element(
            "mxCell",
            {
                "id": nid,
                "value": "",
                "style": "ellipse;html=1;shape=startState;fillColor=#000000;strokeColor=#000000;",
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(size), "height": str(size), "as": "geometry"})
        self.fg_cells.append(cell)
        box = RectBox(key, "initial", x, y, size, size)
        self.boxes[key] = box
        self.check_boxes[key] = box
        return key

    def add_final(self, key: str, x: int, y: int, size: int = 36) -> str:
        nid = f"final_{key}"
        cell = ET.Element(
            "mxCell",
            {
                "id": nid,
                "value": "",
                "style": "ellipse;html=1;shape=endState;fillColor=#000000;strokeColor=#000000;",
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(size), "height": str(size), "as": "geometry"})
        self.fg_cells.append(cell)
        box = RectBox(key, "final", x, y, size, size)
        self.boxes[key] = box
        self.check_boxes[key] = box
        return key

    def add_choice(self, key: str, x: int, y: int, size: int = 44) -> str:
        nid = f"choice_{key}"
        cell = ET.Element(
            "mxCell",
            {
                "id": nid,
                "value": "",
                "style": "rhombus;whiteSpace=wrap;html=1;fillColor=#FFFBEB;strokeColor=#B45309;strokeWidth=2.4;",
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(size), "height": str(size), "as": "geometry"})
        self.fg_cells.append(cell)
        box = RectBox(key, "choice", x, y, size, size)
        self.boxes[key] = box
        self.check_boxes[key] = box
        return key

    def add_note(self, key: str, x: int, y: int, w: int, h: int, text: str) -> str:
        nid = f"note_{key}"
        cell = ET.Element(
            "mxCell",
            {
                "id": nid,
                "value": text,
                "style": (
                    "shape=note;whiteSpace=wrap;html=0;size=16;fillColor=#FFFBEB;strokeColor=#D97706;"
                    "strokeWidth=1.6;fontColor=#451A03;fontSize=12;align=left;verticalAlign=top;"
                    "spacingLeft=12;spacingRight=12;spacingTop=10;spacingBottom=8;"
                ),
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        self.fg_cells.append(cell)
        box = RectBox(key, "note", x, y, w, h)
        self.boxes[key] = box
        self.check_boxes[key] = box
        return key

    def add_transition(
        self,
        pts: list[tuple[int, int]],
        label: str = "",
        *,
        color: str = "#1E293B",
        label_pos: tuple[int, int] | None = None,
        label_w: int = 260,
        label_h: int = 34,
    ) -> None:
        eid = self.next_id("trans")
        cell = ET.Element(
            "mxCell",
            {
                "id": eid,
                "value": "",
                "style": (
                    f"edgeStyle=none;rounded=0;html=0;strokeColor={color};strokeWidth=2.2;"
                    "endArrow=open;endFill=0;endSize=10;"
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

        if label and label_pos is not None:
            lid = self.next_id("lbl")
            lcell = ET.Element(
                "mxCell",
                {
                    "id": lid,
                    "value": label,
                    "style": (
                        f"rounded=1;arcSize=16;whiteSpace=wrap;html=0;fillColor=#FFFFFF;"
                        f"strokeColor={color};strokeWidth=1;fontColor={color};fontStyle=1;"
                        "fontSize=12;align=center;verticalAlign=middle;spacingLeft=6;spacingRight=6;"
                    ),
                    "vertex": "1",
                    "parent": "1",
                },
            )
            ET.SubElement(
                lcell,
                "mxGeometry",
                {
                    "x": str(label_pos[0]),
                    "y": str(label_pos[1]),
                    "width": str(label_w),
                    "height": str(label_h),
                    "as": "geometry",
                },
            )
            self.edge_cells.append(lcell)

    def validate_no_overlaps(self) -> None:
        items = list(self.check_boxes.values())
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                if not (a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y):
                    raise AssertionError(f"UML node overlap detected: {a.box_id} vs {b.box_id}")

    def build_xml(self) -> ET.ElementTree:
        self.validate_no_overlaps()
        mxfile = ET.Element("mxfile", {"host": "app.diagrams.net", "version": "24.7.17"})
        diag = ET.SubElement(mxfile, "diagram", {"id": "vf-ccus-uml25-v2", "name": "VF-CCUS-UML25-StateMachine-v2"})
        model = ET.SubElement(
            diag,
            "mxGraphModel",
            {
                "dx": "1400",
                "dy": "900",
                "grid": "1",
                "gridSize": "10",
                "guides": "1",
                "tooltips": "1",
                "connect": "1",
                "arrows": "1",
                "page": "1",
                "pageScale": "1",
                "pageWidth": str(self.width),
                "pageHeight": str(self.height),
                "background": "#FFFFFF",
            },
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
    d = UML25StateMachineBuilder()

    # Header Banner
    d.add_title_header(
        40,
        24,
        2320,
        74,
        "V&F IMR-MS 中国 CCS/CCUS 市场调研与双轨 GTM 工作流 v2.0 — OMG UML 2.5 行为状态机图",
        "架构宪章：全旗舰大脑 + 确定性底盘（4 阶段主干 / 原生混合编排优先 / 双版本同步交付：5 卷原始详版 + 5 卷高密度高管版 / 全文零截断真审计）",
    )

    # Initial Pseudostate ● (aligned dead-horizontal with s0_plan mid_y=278)
    d.add_initial("start", 72, 262, size=32)

    # -----------------------------------------------------------------------
    # 阶段一：确定性底座与全局规划 (Composite State)
    # -----------------------------------------------------------------------
    d.add_composite_state("stage0", 220, 128, 620, 270, "阶段一：确定性底座与全局规划", stroke="#1E3A8A", fill="#EFF6FF")
    d.add_simple_state(
        "s0_plan",
        246,
        180,
        568,
        196,
        "事实装载与正交规划中",
        "entry / 解析奥地利原厂一手技术资料并分配唯一证据编号\n"
        "entry / 执行中英文宏观联网侦察并去重归档至本地证据库\n"
        "do / 调用旗舰大脑纵览一手资料，划分 5 条正交业务赛道与 1 条独立竞品及防爆小屋生态任务\n"
        "exit / 导出单源结构化契约并固化调研计划",
        stroke="#1E40AF",
    )

    # -----------------------------------------------------------------------
    # 阶段二：分赛道并发深挖与证据核验 (Composite State)
    # -----------------------------------------------------------------------
    d.add_composite_state("stage1", 920, 128, 700, 270, "阶段二：分赛道并发深挖与证据核验", stroke="#5B21B6", fill="#F5F3FF")
    d.add_simple_state(
        "s1_mine",
        946,
        180,
        648,
        196,
        "并发检索与全旗舰提纯中",
        "entry / 并发执行中英文双引擎检索及核心网页全文抓取入库\n"
        "do / 全旗舰大脑按业务赛道提纯项目、细分规模参数与原始四项收益结构（严守 0–100 标尺）\n"
        "do / 独立竞品生态任务专门提纯竞品战卡、本土防爆小屋集成商与设计院准入壁垒\n"
        "exit / 确定性核验全部引用编号，剔除无依据条目并记录剔除台账（禁止静默假挂靠）",
        stroke="#6D28D9",
    )

    # -----------------------------------------------------------------------
    # 阶段三：确定性测算与全局商业裁决 (Composite State)
    # -----------------------------------------------------------------------
    d.add_composite_state("stage2", 1700, 128, 660, 270, "阶段三：确定性测算与全局商业裁决", stroke="#065F46", fill="#ECFDF5")
    d.add_simple_state(
        "s2_arbitrate",
        1726,
        180,
        608,
        196,
        "双核测算与全局裁决中",
        "entry / 确定性引擎按细分赛道与三轨交付分别累加测算 2026–2036 市场规模（读取配置乘数）\n"
        "entry / 确定性引擎保留原始收益比例测算三情景回收期并淘汰伪需求（防幸存者偏差）\n"
        "do / 单次旗舰大脑纵览全池：合并同义重复场景、统一标尺全局排序并产出四类买方阻力矩阵\n"
        "exit / 锁定全卷唯一只读事实锚点总表，并按五卷主题精准路由证据包",
        stroke="#059669",
    )

    # -----------------------------------------------------------------------
    # 阶段四：双版本撰写与全量真审计门禁 (Composite State)
    # -----------------------------------------------------------------------
    d.add_composite_state(
        "stage3",
        220,
        468,
        2140,
        890,
        "阶段四：双版本撰写与全量真审计门禁（有界闭环 ≤ 2 轮）",
        stroke="#9F1239",
        fill="#FFF1F2",
    )

    # 3a: 原始详版并发撰写
    d.add_simple_state(
        "s3_full_synth",
        260,
        536,
        640,
        204,
        "原始详版五卷并发撰写中",
        "entry / 向每卷精准注入专属主题证据包（高序号引用优先召回，零按序盲截）与只读事实锚点总表\n"
        "do / 旗舰大脑并发撰写第 00–04 卷原始详版报告（严格锁定市场规模与回收期数值，保留伪需求淘汰表）\n"
        "exit / 暂存五卷原始详版初稿",
        stroke="#6D28D9",
    )

    # 3b-1: 全量硬审计与分卷全文复核
    d.add_simple_state(
        "s3_critic",
        1040,
        536,
        640,
        204,
        "全量硬审计与分卷全文复核中",
        "entry / 确定性程序全量扫描五卷正文：提取全部单条与组合引用编号并核对入库真值\n"
        "do / 独立复核大脑分卷并发审阅（每卷传入 100% 完整正文，严禁截断），核对跨卷数字与竞品真实性\n"
        "exit / 汇总硬核错误清单、待修订卷宗及外部缺口补检词",
        stroke="#BE123C",
    )

    # Choice Pseudostate ◇ (Audit Verdict)
    d.add_choice("audit_choice", 1337, 822, size=46)

    # 3b-2: 定向补检与完整修订
    d.add_simple_state(
        "s3_rewrite",
        1760,
        742,
        560,
        206,
        "定向补检与完整修订中",
        "entry / 若复核标记外部证据缺口，执行最多 4 条精准联网补检并追加归档至证据库\n"
        "do / 仅针对被点名卷宗传入 100% 完整原稿、具体错误清单与新证据执行定向修订（严禁腰斩原稿）\n"
        "exit / 回填修订后完整卷宗并准备复检",
        stroke="#B45309",
    )

    # 3c: 高密度高管版提纯
    d.add_simple_state(
        "s3_exec_distill",
        260,
        1060,
        780,
        220,
        "高密度高管版五卷提纯中",
        "entry / 锁定经审定通过的五卷原始详版全文与全局只读事实锚点总表\n"
        "do / 旗舰大脑并发提纯第 00–04 卷高密度高管版（每卷 2,500–5,500 字，结论先行、表格驱动、零注水）\n"
        "do / 100% 保持市场规模、回收期、三轨架构、淘汰伪需求结论及合法证据编号与详版完全一致\n"
        "exit / 形成与原始详版 1:1 对应的五卷高密度高管版",
        stroke="#0369A1",
    )

    # 3d: 终局确定性双版本门禁与落盘
    d.add_simple_state(
        "s3_finalize",
        1180,
        1060,
        820,
        220,
        "确定性双版本审计门禁与落盘中",
        "entry / 确定性程序全量审计十卷成品（5 卷原始详版 + 5 卷高管版）：核验引用 100% 合法、十年市场规模与回收期数值一致、伪需求已披露\n"
        "entry / 确定性程序零改写渲染第 05 卷全量证据溯源索引表，并对全套产物执行密钥防泄露扫描\n"
        "do / 落盘原始详版五卷、高管版五卷（独立子目录）、证据索引表及客观核验遥测报告\n"
        "exit / 签发确定性门禁结果与交付文件清单",
        stroke="#059669",
    )

    # Final State ◉
    d.add_final("end", 2160, 1152, size=36)

    # UML 2.5 Legend & Engineering Guardrails Note (non-state annotation, no transitions)
    d.add_note(
        "legend_note",
        220,
        1400,
        2140,
        220,
        "【OMG UML 2.5 图元图例与 v2.0 架构治理要点说明（纯注释区，不参与状态迁移）】\n"
        "1. 符号规范：● 初始伪状态（唯一无条件入口） ｜ ◉ 终止状态（零出边） ｜ ◇ 选择伪状态（出边全部具备互斥 [监护条件] 及显式 [else] 保底出口） ｜ 圆角两栏框 = 状态节点（内部标注 entry/do/exit，不混用数据库圆柱体或流程图菱形）。\n"
        "2. 关键瘦身与止血：取消 v1.0 中 10 次小模型买方质询 + 10 场小模型两两锦标赛 + 盲打 100 分的终审裁判，合并为 1 次全旗舰全局裁决；总大模型调用量从 34 次压减至 ~11–13 次（另加 5 次高管版提纯），全链路直上旗舰大脑。\n"
        "3. 确定性底盘升级：修复陆上管网与出口船运规模覆盖漏洞（细分累加保留三轨）、保留原始四项收益比例（取消固定比例覆写）、全量提取多编号组合引用、剔除无据条目零假挂靠、分卷复核与修订均 100% 全文输入零截断。\n"
        "4. 双套报告交付：原始详版 5 卷落盘于输出根目录，高密度高管版 5 卷落盘于 executive_edition/ 子目录，两套报告共用同一证据索引表并同步通过 100% 确定性审计门禁。",
    )

    # -----------------------------------------------------------------------
    # Transitions (strictly orthogonal, non-overlapping, UML 2.5 syntax)
    # -----------------------------------------------------------------------
    b = d.boxes

    # ● -> Stage 0 (/ 初始化，无事件无 guard，正水平直连)
    d.add_transition(
        [mid_right(b["start"]), mid_left(b["s0_plan"])],
        "/ 初始化运行任务",
        color="#0F172A",
        label_pos=(104, 232),
        label_w=130,
        label_h=28,
    )

    # Stage 0 -> Stage 1
    d.add_transition(
        [mid_right(b["s0_plan"]), mid_left(b["s1_mine"])],
        "调研计划已固化",
        color="#1E40AF",
        label_pos=(828, 240),
        label_w=108,
        label_h=28,
    )

    # Stage 1 -> Stage 2
    d.add_transition(
        [mid_right(b["s1_mine"]), mid_left(b["s2_arbitrate"])],
        "各赛道核验完成",
        color="#6D28D9",
        label_pos=(1604, 240),
        label_w=116,
        label_h=28,
    )

    # Stage 2 -> Stage 3a (drop at x=780 cleanly to the right of Stage 4 title text)
    s2b = mid_bot(b["s2_arbitrate"])
    s3_entry = (780, b["s3_full_synth"].y)
    d.add_transition(
        [s2b, (s2b[0], 432), (s3_entry[0], 432), s3_entry],
        "事实锚点总表已锁定",
        color="#059669",
        label_pos=(1260, 416),
        label_w=156,
        label_h=28,
    )

    # Stage 3a -> Stage 3b-1
    d.add_transition(
        [mid_right(b["s3_full_synth"]), mid_left(b["s3_critic"])],
        "五卷初稿已生成",
        color="#6D28D9",
        label_pos=(912, 600),
        label_w=116,
        label_h=28,
    )

    # Stage 3b-1 -> Choice ◇
    d.add_transition(
        [mid_bot(b["s3_critic"]), mid_top(b["audit_choice"])],
        "审计结论已产出",
        color="#BE123C",
        label_pos=(1374, 764),
        label_w=120,
        label_h=28,
    )

    # Choice ◇ -> Rewrite (Guarded bounded loop!)
    ch_r = mid_right(b["audit_choice"])
    rw_l = mid_left(b["s3_rewrite"])
    d.add_transition(
        [ch_r, rw_l],
        "[存在错误或缺口 且 修订次数 < 2]\n/ 修订次数 + 1",
        color="#B45309",
        label_pos=(1430, 796),
        label_w=276,
        label_h=44,
    )

    # Rewrite -> Stage 3b-1 (loop back cleanly above Rewrite box into right side of Critic)
    rw_t = mid_top(b["s3_rewrite"])
    cr_r = mid_right(b["s3_critic"])
    d.add_transition(
        [rw_t, (rw_t[0], cr_r[1]), cr_r],
        "修订稿已回填",
        color="#B45309",
        label_pos=(1820, 598),
        label_w=118,
        label_h=28,
    )

    # Choice ◇ -> Executive Distill (Pass branch)
    ch_l = mid_left(b["audit_choice"])
    ed_t_pass = (b["s3_exec_distill"].x + 260, b["s3_exec_distill"].y)
    d.add_transition(
        [ch_l, (ed_t_pass[0], ch_l[1]), ed_t_pass],
        "[全量硬审计与分卷复核全部通过]",
        color="#059669",
        label_pos=(660, 826),
        label_w=260,
        label_h=30,
    )

    # Choice ◇ -> Executive Distill ([else] cap-reached escape branch)
    ch_b = mid_bot(b["audit_choice"])
    ed_t_else = (b["s3_exec_distill"].x + 620, b["s3_exec_distill"].y)
    d.add_transition(
        [ch_b, (ch_b[0], 986), (ed_t_else[0], 986), ed_t_else],
        "[else：达到修订上限(2次)] / 标记未闭环风险清单",
        color="#9F1239",
        label_pos=(910, 968),
        label_w=360,
        label_h=30,
    )

    # Executive Distill -> Finalize
    d.add_transition(
        [mid_right(b["s3_exec_distill"]), mid_left(b["s3_finalize"])],
        "高管版五卷已提纯",
        color="#0369A1",
        label_pos=(1046, 1134),
        label_w=128,
        label_h=34,
    )

    # Finalize -> Final State ◉
    d.add_transition(
        [mid_right(b["s3_finalize"]), mid_left(b["end"])],
        "/ 输出双版本十卷与遥测",
        color="#059669",
        label_pos=(2008, 1134),
        label_w=148,
        label_h=34,
    )

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
    print(f"OMG UML 2.5 state machine diagram generated & exported: {DOCS_DRAWIO} and {OUT_DRAWIO}")


if __name__ == "__main__":
    generate_all()
