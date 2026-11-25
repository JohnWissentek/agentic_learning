#!/usr/bin/env python3
"""Generate OMG UML 2.5 Behavioral State Machine Diagram (.drawio) for PSO V4.0.

Strictly conforms to OMG UML 2.5 State Machine standards:
- Solid black Initial Pseudostate (`startState`, 30x30) with clean guard-free outgoing transition
- Bullseye Final State (`endState`, 34x34) with zero outgoing transitions
- Rounded two-compartment Simple/Composite States (`swimlane`, `entry /`, `do /`, `exit /`)
- Hollow Choice Pseudostates (`rhombus`, 36x36) with mutually exclusive `[guard]` & `[else]` edges
- Explicit bounded-loop guards (`[反证轮次 < 1] / 反证轮次 + 1`, `[核修轮次 < 1] / 核修轮次 + 1`)
- Zero flowchart shapes (no cylinders, parallelograms, or sharp rectangles) and zero code jargon.
"""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_DIR = Path("/Users/john/Desktop/agentic_learning/power_semiconductor_opportunities")
DOCS_OUT = BASE_DIR / "docs/08_V4_MODEL_FIRST_UML25_STATE_MACHINE.drawio"

STYLE_INITIAL = "ellipse;html=1;shape=startState;fillColor=#0f172a;strokeColor=#0f172a;"
STYLE_FINAL = "ellipse;html=1;shape=endState;fillColor=#0f172a;strokeColor=#0f172a;"
STYLE_CHOICE = "rhombus;whiteSpace=wrap;html=1;fillColor=#fffbeb;strokeColor=#b45309;strokeWidth=2;"
STYLE_COMPOSITE = (
    "swimlane;startSize=36;rounded=1;arcSize=5;fillColor=#f8fafc;strokeColor=#475569;"
    "strokeWidth=2;fontSize=15;fontStyle=1;fontColor=#0f172a;collapsible=0;"
)
STYLE_SIMPLE = (
    "swimlane;fontStyle=1;align=center;verticalAlign=top;childLayout=stackLayout;"
    "horizontal=1;startSize=32;horizontalStack=0;resizeParent=1;resizeLast=1;"
    "collapsible=0;marginBottom=0;rounded=1;arcSize=12;fillColor=#ffffff;"
    "strokeColor=#1e40af;strokeWidth=2;fontSize=14;fontColor=#1e3a8a;"
)
STYLE_SIMPLE_BRAIN = (
    "swimlane;fontStyle=1;align=center;verticalAlign=top;childLayout=stackLayout;"
    "horizontal=1;startSize=32;horizontalStack=0;resizeParent=1;resizeLast=1;"
    "collapsible=0;marginBottom=0;rounded=1;arcSize=12;fillColor=#fffbeb;"
    "strokeColor=#d97706;strokeWidth=2;fontSize=14;fontColor=#92400e;"
)
STYLE_SIMPLE_GUARD = (
    "swimlane;fontStyle=1;align=center;verticalAlign=top;childLayout=stackLayout;"
    "horizontal=1;startSize=32;horizontalStack=0;resizeParent=1;resizeLast=1;"
    "collapsible=0;marginBottom=0;rounded=1;arcSize=12;fillColor=#fff1f2;"
    "strokeColor=#be123c;strokeWidth=2;fontSize=14;fontColor=#881337;"
)
STYLE_ACTIVITY = (
    "text;strokeColor=none;fillColor=none;align=left;verticalAlign=top;"
    "spacingLeft=10;spacingRight=10;spacingTop=6;overflow=hidden;rotatable=0;"
    "points=[[0,0.5],[1,0.5]];portConstraint=eastwest;whiteSpace=wrap;html=1;"
    "fontSize=12;fontColor=#1e293b;"
)
STYLE_EDGE = (
    "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;"
    "html=1;endArrow=open;endFill=0;endSize=10;strokeWidth=2;strokeColor=#334155;"
    "fontSize=12;fontColor=#0f172a;labelBackgroundColor=#ffffff;"
)
STYLE_EDGE_LOOP = (
    "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;"
    "html=1;endArrow=open;endFill=0;endSize=10;strokeWidth=2;strokeColor=#b45309;"
    "fontSize=12;fontColor=#92400e;labelBackgroundColor=#ffffff;"
)
STYLE_NOTE = (
    "shape=note;whiteSpace=wrap;html=1;backgroundOutline=1;size=14;"
    "fillColor=#f1f5f9;strokeColor=#64748b;fontSize=12;align=left;verticalAlign=top;"
    "spacingLeft=10;spacingRight=10;spacingTop=8;fontColor=#334155;"
)


class UML25Builder:
    def __init__(self, width: int = 1920, height: int = 2360) -> None:
        self._id = 2
        self.mxfile = ET.Element("mxfile", host="app.diagrams.net", type="device")
        diagram = ET.SubElement(
            self.mxfile,
            "diagram",
            id="pso-v4-uml25",
            name="PSO V4.0 UML 2.5 状态机图",
        )
        model = ET.SubElement(
            diagram,
            "mxGraphModel",
            dx="1422",
            dy="762",
            grid="1",
            gridSize="10",
            guides="1",
            tooltips="1",
            connect="1",
            arrows="1",
            fold="1",
            page="1",
            pageScale="1",
            pageWidth=str(width),
            pageHeight=str(height),
            background="#ffffff",
        )
        self.root = ET.SubElement(model, "root")
        ET.SubElement(self.root, "mxCell", id="0")
        ET.SubElement(self.root, "mxCell", id="1", parent="0")

    def _next_id(self) -> str:
        val = str(self._id)
        self._id += 1
        return val

    def add_initial(self, x: int, y: int, parent: str = "1") -> str:
        cid = self._next_id()
        cell = ET.SubElement(self.root, "mxCell", id=cid, value="", style=STYLE_INITIAL, vertex="1", parent=parent)
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width="30", height="30", **{"as": "geometry"})
        return cid

    def add_final(self, x: int, y: int, parent: str = "1") -> str:
        cid = self._next_id()
        cell = ET.SubElement(self.root, "mxCell", id=cid, value="", style=STYLE_FINAL, vertex="1", parent=parent)
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width="34", height="34", **{"as": "geometry"})
        return cid

    def add_choice(self, x: int, y: int, parent: str = "1") -> str:
        cid = self._next_id()
        cell = ET.SubElement(self.root, "mxCell", id=cid, value="", style=STYLE_CHOICE, vertex="1", parent=parent)
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width="36", height="36", **{"as": "geometry"})
        return cid

    def add_composite(self, title: str, x: int, y: int, w: int, h: int, parent: str = "1") -> str:
        cid = self._next_id()
        cell = ET.SubElement(self.root, "mxCell", id=cid, value=title, style=STYLE_COMPOSITE, vertex="1", parent=parent)
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), **{"as": "geometry"})
        return cid

    def add_state(
        self,
        title: str,
        activities: list[str],
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        kind: str = "chassis",
        parent: str = "1",
    ) -> str:
        style = (
            STYLE_SIMPLE_BRAIN
            if kind == "brain"
            else (STYLE_SIMPLE_GUARD if kind == "guard" else STYLE_SIMPLE)
        )
        cid = self._next_id()
        cell = ET.SubElement(self.root, "mxCell", id=cid, value=title, style=style, vertex="1", parent=parent)
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), **{"as": "geometry"})

        act_id = self._next_id()
        body_html = "<br/>".join(activities)
        act = ET.SubElement(self.root, "mxCell", id=act_id, value=body_html, style=STYLE_ACTIVITY, vertex="1", parent=cid)
        ET.SubElement(act, "mxGeometry", y="32", width=str(w), height=str(h - 32), **{"as": "geometry"})
        return cid

    def add_note(self, text_lines: list[str], x: int, y: int, w: int, h: int, parent: str = "1") -> str:
        cid = self._next_id()
        cell = ET.SubElement(
            self.root, "mxCell", id=cid, value="<br/>".join(text_lines), style=STYLE_NOTE, vertex="1", parent=parent
        )
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), **{"as": "geometry"})
        return cid

    def add_transition(
        self,
        src: str,
        dst: str,
        label: str = "",
        *,
        loop: bool = False,
        waypoints: list[tuple[int, int]] | None = None,
        parent: str = "1",
    ) -> str:
        cid = self._next_id()
        style = STYLE_EDGE_LOOP if loop else STYLE_EDGE
        cell = ET.SubElement(
            self.root, "mxCell", id=cid, value=label, style=style, edge="1", parent=parent, source=src, target=dst
        )
        geom = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        if waypoints:
            arr = ET.SubElement(geom, "Array", **{"as": "points"})
            for wx, wy in waypoints:
                ET.SubElement(arr, "mxPoint", x=str(wx), y=str(wy))
        return cid

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        ET.indent(self.mxfile, space="  ")
        path.write_text(ET.tostring(self.mxfile, encoding="unicode"), encoding="utf-8")


def build_v4_uml25_diagram() -> UML25Builder:
    g = UML25Builder(width=1920, height=2320)

    # Header Note (UML 2.5 Diagram Title & Legend)
    g.add_note(
        [
            "<b>电力能源与半导体在线测试仪器机会发现工作流 V4.0 — OMG UML 2.5 行为状态机图</b>",
            "架构原则：大模型优先（琥珀框＝旗舰大脑推理）+ 确定性底盘（蓝框＝检索/算账/主表注入，红框＝全量硬审计）",
            "图元规范：● 初始伪状态 ｜ ◉ 终止状态 ｜ ◇ 互斥完备选择伪状态（含 [else]）｜ 所有回环均显式证明有界次数上限",
        ],
        x=40,
        y=24,
        w=1840,
        h=84,
    )

    # Top-level Initial Pseudostate
    start_top = g.add_initial(x=665, y=140)

    # Stage 0 Composite State
    s0 = g.add_composite("阶段一：宏观广谱侦察与动态赛道立题", x=80, y=220, w=1200, h=220)
    s0_init = g.add_initial(x=30, y=108, parent=s0)
    s0_recon = g.add_state(
        "执行宏观双语侦察",
        [
            "entry / 装载研究契约与行业经济边界护栏",
            "do / 并发检索中国与全球最新产线痛点及厂商动态并去重入库",
            "exit / 以不可信外部数据边界框物理封装侦察证据",
        ],
        x=110,
        y=60,
        w=430,
        h=128,
        kind="chassis",
        parent=s0,
    )
    s0_cluster = g.add_state(
        "动态聚类生成候选赛道",
        [
            "do / 旗舰大脑基于实时证据从零归纳正交与交叉赛道",
            "exit / 输出各赛道产线痛点与商用厂商双路检索词",
        ],
        x=630,
        y=60,
        w=430,
        h=128,
        kind="brain",
        parent=s0,
    )
    s0_end = g.add_final(x=1120, y=106, parent=s0)
    g.add_transition(s0_init, s0_recon, parent=s0)
    g.add_transition(s0_recon, s0_cluster, "侦察完成", parent=s0)
    g.add_transition(s0_cluster, s0_end, parent=s0)
    g.add_transition(start_top, s0, "/ 初始化独立证据库与费用台账")

    # HITL Choice Pseudostate & Wait State
    hitl_choice = g.add_choice(x=662, y=490)
    g.add_transition(s0, hitl_choice, "赛道清单就绪")

    wait_hitl = g.add_state(
        "等待人工审定赛道",
        [
            "entry / 落盘待审赛道清单并展示侦察证据依据",
            "do / 挂起等待业务决策者批准或微调赛道方向",
        ],
        x=1360,
        y=446,
        w=480,
        h=124,
        kind="guard",
    )
    hitl_abort_end = g.add_final(x=1583, y=640)
    g.add_transition(hitl_choice, wait_hitl, "[已开启人工审定门禁]")
    g.add_transition(wait_hitl, hitl_abort_end, "收到中止指令 [未批准] / 保留快照退出")

    # Stage 1 Composite State (with Bounded Falsification Loop)
    s1 = g.add_composite("阶段二：多赛道并发取证与有界反证核查（消除伪空白）", x=80, y=620, w=1200, h=360)
    s1_init = g.add_initial(x=30, y=118, parent=s1)
    s1_search = g.add_state(
        "并发双路检索与高权威深抓",
        [
            "do / 8条赛道并行执行痛点+商用厂商检索与网页全文深抓",
            "exit / 统一编号入库并以不可信外部数据框隔离封装",
        ],
        x=100,
        y=72,
        w=340,
        h=124,
        kind="chassis",
        parent=s1,
    )
    s1_mine = g.add_state(
        "旗舰大脑提炼候选与空白初判",
        [
            "do / 零种子涌现候选机会、初判商用空白级别与工业ROI区间",
            "exit / 为每个疑似空白生成定向厂商反证检索词",
        ],
        x=500,
        y=72,
        w=360,
        h=124,
        kind="brain",
        parent=s1,
    )
    s1_choice = g.add_choice(x=930, y=116, parent=s1)
    s1_falsify = g.add_state(
        "执行定向反证核查",
        [
            "do / 追搜龙头厂商业型号与中标记录，由旗舰大脑复核降级或确认真空白",
            "exit / 写入反证审计说明与真实入库编号",
        ],
        x=500,
        y=232,
        w=460,
        h=102,
        kind="brain",
        parent=s1,
    )
    s1_seal = g.add_state(
        "赛道档案零造假封盘",
        [
            "do / 严禁伪造回填证据编号，无真实证据的候选留空待淘汰",
        ],
        x=1010,
        y=232,
        w=168,
        h=102,
        kind="guard",
        parent=s1,
    )
    s1_end = g.add_final(x=1130, y=116, parent=s1)

    g.add_transition(s1_init, s1_search, parent=s1)
    g.add_transition(s1_search, s1_mine, "证据装配就绪", parent=s1)
    g.add_transition(s1_mine, s1_choice, "初判完成", parent=s1)
    g.add_transition(
        s1_choice,
        s1_falsify,
        "[存在疑似空白 且 反证轮次 < 1] / 反证轮次 + 1",
        loop=True,
        parent=s1,
    )
    g.add_transition(s1_falsify, s1_mine, "反证证据入库", loop=True, parent=s1)
    g.add_transition(s1_choice, s1_seal, "[无待反证项 或 反证轮次 >= 1 / else]", parent=s1)
    g.add_transition(s1_seal, s1_end, parent=s1)

    g.add_transition(hitl_choice, s1, "[未开启人工审定门禁 或 else]")
    g.add_transition(wait_hitl, s1, "收到批准指令 [已批准] / 锁定赛道", waypoints=[(1400, 600), (1050, 600)])

    # Stage 2-3 Composite State
    s2 = g.add_composite("阶段三：工业校准财务漏斗与行业级买方组合评审（2-3次统筹替代32次碎片调用）", x=80, y=1040, w=1200, h=220)
    s2_init = g.add_initial(x=30, y=112, parent=s2)
    s2_funnel = g.add_state(
        "校准财务建模与硬门禁筛除",
        [
            "do / 引入行业毛利归因、单机归因与首年爬坡计算三情景回收期",
            "exit / 硬淘汰无实证、负现金流及保守回收期超42月候选",
        ],
        x=110,
        y=62,
        w=440,
        h=126,
        kind="chassis",
        parent=s2,
    )
    s2_portfolio = g.add_state(
        "行业级买方委员会拷问与组合排位",
        [
            "do / 电力与半导体分组统筹审视全量候选、真实证据与三情景财务",
            "exit / 输出四角色压力测试备忘录与零丢弃全局组合排位",
        ],
        x=630,
        y=62,
        w=440,
        h=126,
        kind="brain",
        parent=s2,
    )
    s2_end = g.add_final(x=1130, y=110, parent=s2)
    g.add_transition(s2_init, s2_funnel, parent=s2)
    g.add_transition(s2_funnel, s2_portfolio, "短名单与淘汰审计就绪", parent=s2)
    g.add_transition(s2_portfolio, s2_end, parent=s2)
    g.add_transition(s1, s2, "全部赛道档案汇合")

    # Stage 4 Composite State
    s3 = g.add_composite("阶段四：确定性主表注入与五卷投决级精炼研报并行合成", x=80, y=1320, w=1200, h=220)
    s3_init = g.add_initial(x=30, y=112, parent=s3)
    s3_tables = g.add_state(
        "确定性渲染只读数据主表",
        [
            "do / 程序直出零误差财务总表、商用空白总表、淘汰表与证据总索引",
            "exit / 锁定只读表格模块，禁止大模型手抄数字表",
        ],
        x=110,
        y=62,
        w=440,
        h=126,
        kind="chassis",
        parent=s3,
    )
    s3_synth = g.add_state(
        "并发撰写五卷投决精炼正文",
        [
            "do / 旗舰大脑聚焦物理机理、反证结论与落地路线，按6-9万字控篇成稿",
            "exit / 程序按占位符确定性注入全部只读数据主表",
        ],
        x=630,
        y=62,
        w=440,
        h=126,
        kind="brain",
        parent=s3,
    )
    s3_end = g.add_final(x=1130, y=110, parent=s3)
    g.add_transition(s3_init, s3_tables, parent=s3)
    g.add_transition(s3_tables, s3_synth, "只读主表已锁定", parent=s3)
    g.add_transition(s3_synth, s3_end, parent=s3)
    g.add_transition(s2, s3, "组合排位就绪")

    # Stage 5 Composite State (Full-Corpus Hard Audit + Bounded Repair)
    s4 = g.add_composite("阶段五：全量零截断客观硬审计与有界按需核修", x=80, y=1600, w=1200, h=350)
    s4_init = g.add_initial(x=30, y=112, parent=s4)
    s4_audit = g.add_state(
        "全量确定性客观硬审计",
        [
            "do / 零截断扫描全量正文：核验每条引用入库存在、财务数字零漂移、",
            "     赛道真覆盖（不含侦察桶）与全仓零密钥泄露",
        ],
        x=100,
        y=68,
        w=430,
        h=120,
        kind="guard",
        parent=s4,
    )
    s4_choice = g.add_choice(x=610, y=110, parent=s4)
    s4_repair = g.add_state(
        "定向局部核修",
        [
            "do / 仅对检出引用断链或数字漂移的分卷执行增量修补",
            "exit / 重新注入确定性主表并交回硬审计复验",
        ],
        x=180,
        y=228,
        w=460,
        h=96,
        kind="brain",
        parent=s4,
    )
    s4_compile = g.add_state(
        "编译交付包与真实费用台账",
        [
            "do / 写入五卷研报、全量证据总索引、客观审计计分卡与真实检索费用明细",
        ],
        x=760,
        y=68,
        w=340,
        h=120,
        kind="chassis",
        parent=s4,
    )
    s4_end = g.add_final(x=1140, y=111, parent=s4)

    g.add_transition(s4_init, s4_audit, parent=s4)
    g.add_transition(s4_audit, s4_choice, "审计结论产出", parent=s4)
    g.add_transition(
        s4_choice,
        s4_repair,
        "[存在硬缺陷 且 核修轮次 < 1] / 核修轮次 + 1",
        loop=True,
        parent=s4,
    )
    g.add_transition(s4_repair, s4_audit, "修补完成", loop=True, parent=s4)
    g.add_transition(s4_choice, s4_compile, "[硬审计全通过 或 核修轮次 >= 1 / else]", parent=s4)
    g.add_transition(s4_compile, s4_end, parent=s4)
    g.add_transition(s3, s4, "五卷主表注入完成")

    # Top-level Final State
    end_top = g.add_final(x=663, y=2020)
    g.add_transition(s4, end_top, "全套交付物落盘完成")

    # Right Sidebar Governance Note (Detached — Zero Crossing Lines)
    g.add_note(
        [
            "<b>V3.0 → V4.0 核心工程演进对照</b>",
            "1. <b>大脑升格与精简</b>：取消弱小模型挖掘；32次碎片买方/对战调用收敛为 2-3 次行业组合统筹评审（总调用降幅 ~55%）",
            "2. <b>反证式空白核查</b>：疑似空白必须触发有界厂商反证追搜，从「没搜到」升级为「反证确认」",
            "3. <b>工业财务校准</b>：引入毛利归因、单机归因与首年爬坡，根治 12 天回本与 500% IRR 顶格失真",
            "4. <b>零截断硬审计</b>：统一 EV-CN/EV-GL 编号并 100% 校验入库存在性、ROI 零漂移与非恒真赛道覆盖",
            "5. <b>单内核薄双壳</b>：IDE 脚本由 1,184 行瘦身至 306 行，与终端无头工作流 100% 同源无漂移",
        ],
        x=1360,
        y=780,
        w=480,
        h=340,
    )

    return g


def main() -> None:
    builder = build_v4_uml25_diagram()
    builder.write(DOCS_OUT)
    print(f"Wrote UML 2.5 Draw.io diagram -> {DOCS_OUT}")

    drawio_bin = shutil.which("drawio") or "/Applications/draw.io.app/Contents/MacOS/draw.io"
    if Path(drawio_bin).exists():
        for fmt in ("svg", "pdf"):
            target = DOCS_OUT.with_suffix(f".{fmt}")
            subprocess.run([drawio_bin, "-x", "-f", fmt, "-o", str(target), str(DOCS_OUT)], check=True)
            print(f"Exported {target}")


if __name__ == "__main__":
    main()
