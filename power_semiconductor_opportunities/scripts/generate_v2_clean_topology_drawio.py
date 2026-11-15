#!/usr/bin/env python3
"""Generate Clean, Uncluttered V2.0 Dynamic Discovery Orchestration Topology Diagram.

Highlights the Zero-Preset Bottom-Up Discovery Funnel architecture:
  Stage 0 Macro Recon -> Dynamic Track Clustering -> Optional HITL ->
  Stage 1 8x Zero-Seed Candidate Mining -> Stage 2 Deterministic Range PALMs Funnel & Eliminations ->
  Stage 3 STORM -> Stage 4 Elo -> Stage 5 Strictly Sliced 5-Vol + EvIndex Synthesis ->
  Stage 6 Bounded Cyclic Critic Loops (Targeted Rewrite + Corrective RAG) -> Stage 7 Judge & V2 Outputs.

Reuses CleanDiagramBuilder & geometry helpers cleanly without duplicating XML logic.
"""

from __future__ import annotations

from pathlib import Path

from generate_a0_workflow_drawio import (
    _mid_left,
    _mid_right,
)
from generate_v1_clean_topology_drawio import CleanDiagramBuilder

BASE_DIR = Path("/Users/john/Desktop/agentic_learning/power_semiconductor_opportunities")
DOCS_OUT = BASE_DIR / "docs/06_V2_DYNAMIC_DISCOVERY_TOPOLOGY.drawio"

CANVAS_W = 2800
CANVAS_H = 2490


def build_v2_diagram() -> tuple[str, int, int]:
    g = CleanDiagramBuilder(CANVAS_W, CANVAS_H)

    # Top Title Banner
    g.add_card(
        "banner",
        "BANNER",
        x=32,
        y=20,
        w=2736,
        h=96,
        hdr_h=38,
        hdr_font=16,
        body_font=14,
        title="V2.0 零预设动态发现智能体编排拓扑图：先广谱侦察聚类赛道 → 零种子发散涌现 → 三情景 PALMs 确定性漏斗 → 受控审校闭环",
        body=(
            "说明：彻底解除 V1.0 对 8 赛道与 16 种子的静态预设锁定；严格贯彻“发散探矿（Stage 0–1）→ 确定性收敛淘汰（Stage 2）→ 深度精算排序与合成（Stage 3–5）→ "
            "<= 2 轮有界审校闭环（Stage 6–7）”漏斗哲学。左侧为主干控制流与旁路淘汰/环路，右侧为 V1→V2 机制对比与 Context 速查。"
        ),
    )

    # Backdrop Zones
    g.add_band(
        x=32,
        y=126,
        w=1850,
        h=2336,
        title="V2.0 主干动态发现漏斗控制流 (Left Funnel Spine: 发散探矿 · 物理钳位淘汰 · Critic <= 2 轮有界闭环)",
        accent="#0F172A",
    )
    g.add_band(
        x=1902,
        y=126,
        w=866,
        h=2336,
        title="解耦附表区 (Decoupled Sidebar: 图例规范 · V1 vs V2 逐层对比 · V2 七处 LLM Context 组装速查)",
        accent="#0F766E",
    )

    cx = 920

    # Stage 0
    s0_scope = g.add_card(
        "s0_scope",
        "STORAGE",
        x=470,
        y=172,
        w=900,
        h=118,
        title="[Stage 0-A · 零预设输入] 宏观边界、广谱查询与物理防失真护栏 (YAML 契约)",
        body=(
            "• config/discovery_scope.yaml：仅定义电力能源/半导体宏观使命、16 条广谱侦察查询、分行业物理边界护栏 (无预设赛道/无预设种子价)。\n"
            "• config/research_contract.yaml (V2)：中国 >=45%、保守回收期 <=42月、目标决选 Top 16、Stage-Gate >=85 分。"
        ),
    )

    s0_recon = g.add_card(
        "s0_recon",
        "HARDCODED",
        x=470,
        y=320,
        w=900,
        h=124,
        title="[Stage 0-B · 硬编码] 广谱双引擎侦察扫描 (run_macro_recon / recon-search)",
        body=(
            "• 并发调用 Metaso (CN ×8) + Serper (GLOBAL ×8) 扫描招标、政策与前沿综述；去重写入 SQLite (evidence_vault_v2.db · track_id='RECON')。\n"
            "• 确定性输出 v2_recon_context.json（含 [EV-CN/GL-...] 侦察摘要切片与行业物理护栏表），零写死具体仪器参数。"
        ),
    )

    s0_emerge = g.add_card(
        "s0_emerge",
        "LLM_AGENT",
        x=470,
        y=474,
        w=900,
        h=126,
        title="[Stage 0-C · LLM 动态发现] Step-Back 聚类涌现动态赛道 (DiscoveryPlan)",
        body=(
            "• [Antigravity Pro · Context #1] 基于实时 RECON 证据自下而上聚类形成 8 条正交高景气赛道 (如 DP1–DP4 / DS1–DS4)。\n"
            "• 显式标记新兴/跨界拐点赛道 (is_emerging_or_cross_cutting=true + 依据)，并由 LLM 为每条新赛道现写中英文深搜查询词。"
        ),
    )

    s0_hitl = g.add_card(
        "s0_hitl",
        "GATE",
        x=560,
        y=628,
        w=720,
        h=74,
        hdr_h=30,
        hdr_font=13,
        body_font=11,
        title="[可选人工门禁 · HITL] 审阅 Stage 0 动态涌现赛道清单",
        body="默认自动放行进入 Stage 1 并行深挖；传入 --hitl 时在此中断，由用户确认或增删动态赛道与检索词。",
    )

    # Stage 1 Fan-Out
    s1_power = g.add_card(
        "s1_power",
        "LLM_AGENT",
        x=340,
        y=746,
        w=540,
        h=138,
        hdr_font=13,
        title="[Stage 1-A · 并行搜 + Zero-Seed 矿工 ×4] 电力动态赛道 DP*",
        body=(
            "• 硬编码并发 search_router + 抓取 T1–T3 全文 (<6 命中自动扩搜)。\n"
            "• Zero-Seed Miner LLM 从实证中零种子提取 CN/GLOBAL 痛点，\n"
            "  各条赛道涌现 3–4 个原生仪器机会 + 三档区间参数 (ROIRangeInputs)。"
        ),
    )

    s1_semi = g.add_card(
        "s1_semi",
        "LLM_AGENT",
        x=960,
        y=746,
        w=540,
        h=138,
        hdr_font=13,
        title="[Stage 1-B · 并行搜 + Zero-Seed 矿工 ×4] 半导体动态赛道 DS*",
        body=(
            "• 硬编码并发 search_router + 抓取 T1–T3 全文 (<6 命中自动扩搜)。\n"
            "• 汇总产生 24–32 个原始候选机会（绑定 [EV-...] 引用白名单与\n"
            "  parameter_basis 估算依据，不采用写死参考价格）。"
        ),
    )

    # Stage 2 Funnel + Elimination Audit Side Card
    s2_funnel = g.add_card(
        "s2_funnel",
        "HARDCODED",
        x=470,
        y=922,
        w=900,
        h=144,
        title="[Stage 2 · 确定性 Python 漏斗] 三情景区间 PALMs 钳位、测算与竞争淘汰 (screen_candidate_pool)",
        body=(
            "• 护栏钳位：clamp_roi_range_inputs() 按行业物理合理区间兜底，严防 LLM 脱离量级的报废/良率幻觉。\n"
            "• 三档算账：Python Bisection 计算 乐观 / 基准 / 保守 (CAPEX高/良率低/成本+10%) 回收期、5Y NPV 与 IRR。\n"
            "• 硬门禁+择优：淘汰 无[EV-...] 或 净现金流<=0 或 保守回收期>42月 候选 -> 行业均衡保留 Top 16 决选池。"
        ),
    )

    s2_elim = g.add_card(
        "s2_elim",
        "GATE",
        x=1412,
        y=934,
        w=440,
        h=120,
        dashed_body=True,
        title="[Stage 2 副产品] 淘汰候选显式审计池",
        body=(
            "• EliminatedCandidate[] (典型 8–16 项)\n"
            "• 保留基准/保守回收期、得分与具体淘汰原因\n"
            "• 写入 Vol 00 / Vol 03 审计表与 telemetry JSON"
        ),
    )

    # Stage 3 & Stage 4
    s3_storm = g.add_card(
        "s3_storm",
        "LLM_AGENT",
        x=470,
        y=1102,
        w=900,
        h=122,
        title="[Stage 3 · 并发 LLM (×16)] 四角色产线买方委员会 STORM 压力拷问",
        body=(
            "• [Antigravity Pro · Context #3] 仅对入围 Top 16 机会执行（淘汰项零冗余调用）；同时传入基准与保守情景回本周期。\n"
            "• 围绕 良率VP / 工艺总工 / EHS环保 / CFO四维视角输出停线风险阻力、Spec-in 触发条件与工程化改进。"
        ),
    )

    s4_elo = g.add_card(
        "s4_elo",
        "LLM_AGENT",
        x=470,
        y=1260,
        w=900,
        h=122,
        title="[Stage 4 · 2 轮并行 LLM + Python] 瑞士制 Elo 对抗锦标赛 & 55/45 终极排位",
        body=(
            "• [Antigravity Pro · Context #4] 相邻 Elo 选手盲测对比“三档ROI韧性 × 良率 × 国产升级 × 环保TCO”四支柱。\n"
            "• Python _update_elo(K=32) + 55% 支柱分 / 45% 归一化 Elo 重排锁定 Top 16 终榜与不可篡改的三档 [ROI-CALC] 表。"
        ),
    )

    # Stage 5 Fan-Out + Join
    s5_vol05 = g.add_card(
        "s5_vol05",
        "HARDCODED",
        x=340,
        y=1428,
        w=540,
        h=126,
        title="[Stage 5-A · 硬编码] Vol 05 核验证据总索引导出",
        body=(
            "• render_evidence_index() 从 data/evidence_vault_v2.db 确定性渲染。\n"
            "• 完整收录 Stage 0 RECON 与动态赛道 CN / GLOBAL URL（零幻觉）。"
        ),
    )

    s5_vols = g.add_card(
        "s5_vols",
        "LLM_AGENT",
        x=960,
        y=1428,
        w=540,
        h=126,
        title="[Stage 5-B · 并发 5× LLM] Vol 00–04 严格分片合成",
        body=(
            "• 注入动态涌现总结、淘汰审计表与 Post-Elo 三档 [ROI-CALC] 表。\n"
            "• 强分片隔离：Vol 01/02 仅注各自行业实证与案卷；Vol 03 专攻 ROI/淘汰。"
        ),
    )

    s5_join = g.add_card(
        "s5_join",
        "HARDCODED",
        x=500,
        y=1590,
        w=840,
        h=96,
        hdr_h=30,
        hdr_font=13,
        title="[Stage 5 Join · 合并] 汇总 00–05 书稿并核验正则硬门禁 (det_checks)",
        body="校验 5 卷非空、动态发现赛道覆盖数、已引用独立 [EV-...] 证据数、三档 [ROI-CALC] 标签密度及中英文证据比 (>=45%)。",
    )

    # Stage 6 Critic & Bounded Loops
    s6_critic = g.add_card(
        "s6_critic",
        "GATE",
        x=470,
        y=1722,
        w=900,
        h=128,
        title="[Stage 6 · 异构 Critic 环路入口] 全契约审计与条件路由 (loop_count <= 2)",
        body=(
            "• [Context #6] 审查各动态赛道落地深度、中国优先/双时间窗清晰度、物理准确性及三档 [ROI-CALC] 与淘汰表一致性。\n"
            "• 输出结构化 CritiqueVerdict：pass（通过） / needs_rewrite（定向重写） / needs_more_evidence（触发补搜）。"
        ),
    )

    p_rew = g.add_pill(
        "p_rew",
        x=320,
        y=1760,
        w=122,
        h=52,
        text="needs_rewrite\n(且 loop <= 2)",
        fill="#F5F3FF",
        stroke="#7C3AED",
        font_color="#5B21B6",
        font_size=11,
    )

    s6_left = g.add_card(
        "s6_left",
        "LLM_AGENT",
        x=50,
        y=1572,
        w=252,
        h=132,
        hdr_h=30,
        hdr_font=12,
        body_font=11,
        dashed_body=True,
        title="[分支 6-A] 定向重写受损卷",
        body="• 仅将 Critique Issues 注入受损卷\n• 保留完好分卷，避免全文重跑浪费\n• 重合成后回流 Join 重检",
    )

    p_crag = g.add_pill(
        "p_crag",
        x=1398,
        y=1760,
        w=138,
        h=52,
        text="needs_more_evidence\n(且 loop <= 2)",
        fill="#FFF1F2",
        stroke="#E11D48",
        font_color="#9F1239",
        font_size=11,
    )

    s6_right = g.add_card(
        "s6_right",
        "GATE",
        x=1554,
        y=1562,
        w=304,
        h=156,
        hdr_h=30,
        hdr_font=12,
        body_font=11,
        dashed_body=True,
        title="[分支 6-B] Corrective RAG 补搜",
        body="• 调用 CLI gap-search（动态读取\n  gap_queries，去重查重入库）\n• 携带新增 [EV-...] 证据定向修订\n  受影响分卷，回流合成节点",
    )

    p_pass = g.add_pill(
        "p_pass",
        x=740,
        y=1872,
        w=360,
        h=36,
        text="pass 或达到最大循环上限 (loop > 2) -> 放行终审",
        fill="#ECFDF5",
        stroke="#059669",
        font_color="#065F46",
        font_size=12,
    )

    # Stage 7 Judge, Compiler, Outputs
    s7_judge = g.add_card(
        "s7_judge",
        "LLM_AGENT",
        x=470,
        y=1932,
        w=900,
        h=118,
        title="[Stage 7-A · LLM Judge] Ch 19 五维独立质量终审打分 (0–100 · 及格 >= 85)",
        body=(
            "• [Context #7] 围绕“中国优先与全球深度 / 3-5y vs 5-10y 严谨性 / 物理痛点清晰度 / 三档 ROI 与升级 / 溯源文风”\n"
            "  独立打出 5×20 分单项得分，输出 executive_verdict、strengths 与 residual_risks。"
        ),
    )

    s7_compile = g.add_card(
        "s7_compile",
        "HARDCODED",
        x=470,
        y=2082,
        w=900,
        h=118,
        title="[Stage 7-B · 硬编码] finalize-v2 -> 确定性校验、重算总分与全量落盘",
        body=(
            "• Python 重新校验 Judge 总分与 Elo 55/45 终榜（杜绝算术漂移），输出 stage_gate_passed 判定。\n"
            "• 编译 00–05 Markdown 书稿与 06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json。"
        ),
    )

    s7_outputs = g.add_card(
        "s7_outputs",
        "STORAGE",
        x=470,
        y=2232,
        w=900,
        h=204,
        title="[Stage 7-C · V2 交付物] outputs/v2_dynamic_discovery_2026_2036/ + evidence_vault_v2.db",
        body=(
            "• 00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md（含 Stage 0 动态涌现剖析与 Top 16 总榜）\n"
            "• 01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md · 02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md\n"
            "• 03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md（三档回收期敏感性 + Stage 2 淘汰候选完整审计表）\n"
            "• 04_PRODUCT_TECH_AND_UPGRADE_STRATEGY_PLAYBOOK.md · 05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md\n"
            "• 06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json（完整记录 discovered_tracks · funnel · top16 三档指标）"
        ),
    )

    # -----------------------------------------------------------------------
    # Right Sidebar Reference Cards (Zero Crossing Edges!)
    # -----------------------------------------------------------------------

    g.add_card(
        "side_legend",
        "BANNER",
        x=1922,
        y=172,
        w=826,
        h=460,
        title="[附表 A] 图元色系规范与核心设计哲学",
        body=(
            "■ [深蓝框 · HARDCODED] 硬编码 / Python 工具：搜索网关、SQLite 去重库、三档 PALMs 钳位与漏斗筛选、Elo 算式与终盘导出。\n"
            "■ [紫色框 · LLM_AGENT] LLM 认知节点：Stage 0 赛道聚类、Stage 1 Zero-Seed 矿工、Stage 3 STORM、Stage 4 Elo、Stage 5 合成与 Stage 7 终审。\n"
            "■ [绿色框 · STORAGE] 持久化输入/产物：discovery_scope / contract YAML、SQLite 证据库、最终 00–06 交付目录。\n"
            "■ [玫红框 · GATE/AUDITOR] 门禁、淘汰审计与有界 Critic 审校路由（最多 <= 2 轮闭环）。\n"
            "■ [琥珀框 · CONTEXT_BOX] Context 组装速查；[虚线回边] 表示 <= 2 轮受控反馈。\n\n"
            "核心差异：V1.0 像“带着标准答案找论据”的验证流水线；V2.0 是“先看实时信号→聚类长出赛道→海选发散→Python 漏斗淘汰→精算决策”的真探索漏斗。"
        ),
    )

    g.add_card(
        "side_diff",
        "HARDCODED",
        x=1922,
        y=656,
        w=826,
        h=690,
        title="[附表 B] V1.0 vs V2.0 工程机理逐层进化对照表",
        body=(
            "1. 领域输入层：\n"
            "   • V1.0：写死 domain_taxonomy.yaml (P1–P4 / S1–S4 + 固定中英文搜索词 + 16 项 roi_baseline 种子)。\n"
            "   • V2.0：仅保留 discovery_scope.yaml（宏观行业边界 + Stage 0 广谱扫描词 + 物理量级防错护栏）。\n\n"
            "2. 赛道形成机制：\n"
            "   • V1.0：Planner 只能被动润色物理原理，不能改写赛道结构。\n"
            "   • V2.0：Stage 0 先跑 RECON 实时搜索，再由 LLM 聚类涌现动态赛道（含新兴跨界赛道标记与现写深搜词）。\n\n"
            "3. 候选机会发现：\n"
            "   • V1.0：沿用 16 项预设种子，无真正海选淘汰过程。\n"
            "   • V2.0：8 路矿工零种子各挖掘 3–4 个原生候选（共 24–32 项），附证据引用及低/中/高三档参数区间。\n\n"
            "4. 财务防幻觉与漏斗：\n"
            "   • V1.0：单点基准算账 + 16 进 16 全盘入围，缺乏压力情景测试。\n"
            "   • V2.0：护栏钳位 + 乐观/基准/保守三档算账 -> 保守回收期 >42月 或 无实证直接淘汰，审计入表。\n\n"
            "5. 双模式对齐与证据隔离：\n"
            "   • LangGraph 与 antigravity_run_workflow.py 共同使用同一套 CLI 子命令、同一 Vault 库与同一合成规范。"
        ),
    )

    g.add_card(
        "side_ctx",
        "CONTEXT_BOX",
        x=1922,
        y=1370,
        w=826,
        h=1066,
        dashed_body=True,
        title="[附表 C] V2.0 七处 LLM 调用点 Context 上下文精确组装速查",
        body=(
            "• Context #1 → [Stage 0-C] 动态赛道发现架构师 (1× LLM)\n"
            "  注入：行业使命边界 + Target 赛道数 + 最多 32 条 Stage 0 实时 RECON 摘要 [EV-...] + DISCOVERY_PLAN_SCHEMA。\n\n"
            "• Context #2 → [Stage 1] 8 路并发 Zero-Seed 赛道矿工 (8× 并行 LLM · 严格赛道隔离)\n"
            "  注入：本动态赛道物理原则 + 分行业物理防失真护栏提示 + 本赛道真实 CN/GLOBAL 全文与摘要 [EV-...] +\n"
            "  TRACK_MINER_SCHEMA（强制要求输出 ROIRangeInputs 三档区间与 parameter_basis）。\n\n"
            "• Context #3 → [Stage 3] 四角色买方委员会 STORM 压力测试 (仅对入围 Top 16 · 16× 并行 LLM)\n"
            "  注入：技术形态 + 中国/出海定位 + 乐观/基准/保守 三档 [ROI-CALC] 回本周期与 IRR + 四买方角色要求。\n\n"
            "• Context #4 → [Stage 4] 瑞士制 Elo 对抗裁判 (2 轮 × 8 场 = 16× LLM · 单场盲测隔离)\n"
            "  注入：Option A vs B 基准与保守回收期对照、四大支柱机理与 35/25/20/20 权重规则 + ELO_SCHEMA。\n\n"
            "• Context #5 → [Stage 5-B] 五卷分片报告合成 (5× 并行 LLM · Context Slicing 防失焦)\n"
            "  - Vol 00 总览：Stage 0 动态涌现摘要 + Stage 2 淘汰统计 + Post-Elo 三档总表 + STORM 摘要 + 全域证据。\n"
            "  - Vol 01 电力 / Vol 02 半导体：严格按动态 track_id 自动筛选各自行业 ROI 表、案卷、STORM 与证据。\n"
            "  - Vol 03 财务与淘汰 / Vol 04 平台 Playbook：全量三档表 + 淘汰审计明细 + Elo 战报 / 双领域汇总 [:4500]。\n\n"
            "• Context #6 → [Stage 6] 异构 Critic 审稿与定向修订 (1–2× 循环)\n"
            "  注入：det_checks（含发现赛道、漏斗 raw/keep/elim、独立引用数）+ 五卷 头2200+尾800 预览 + 按需补搜增量证据。\n\n"
            "• Context #7 → [Stage 7-A] Stage-Gate 独立终审裁判 (1× LLM)\n"
            "  注入：终版统计摘要 + Critic 终审结论 + 五卷预览 + 5×20 分严格标尺。"
        ),
    )

    # -----------------------------------------------------------------------
    # Orthogonal Control-Flow Edges (clean vertical spine + planar side loops)
    # -----------------------------------------------------------------------
    g.add_edge("e_scope_recon", s0_scope, s0_recon, [(cx, 290), (cx, 320)], color="#065F46")
    g.add_edge("e_recon_emerge", s0_recon, s0_emerge, [(cx, 444), (cx, 474)], color="#1E3A8A")
    g.add_edge("e_emerge_hitl", s0_emerge, s0_hitl, [(cx, 600), (cx, 628)], color="#1D4ED8")

    # HITL -> Stage 1 Fan-Out (split at y=724)
    g.add_edge("e_hitl_s1p", s0_hitl, s1_power, [(cx, 702), (cx, 724), (610, 724), (610, 746)], color="#5B21B6")
    g.add_edge("e_hitl_s1s", s0_hitl, s1_semi, [(cx, 702), (cx, 724), (1230, 724), (1230, 746)], color="#5B21B6")

    # Stage 1 Join -> Stage 2 Funnel (join bar y=904)
    g.add_edge("e_s1p_s2", s1_power, s2_funnel, [(610, 884), (610, 904), (cx, 904), (cx, 922)], color="#065F46")
    g.add_edge("e_s1s_s2", s1_semi, s2_funnel, [(1230, 884), (1230, 904), (cx, 904), (cx, 922)], color="#065F46")

    # Stage 2 Funnel -> Elimination Audit Card (side branch)
    g.add_edge(
        "e_s2_elim",
        s2_funnel,
        s2_elim,
        [_mid_right(g.boxes[s2_funnel]), _mid_left(g.boxes[s2_elim])],
        color="#BE123C",
        dashed=True,
        stroke_w=2.4,
    )

    # Stage 2 -> Stage 3 -> Stage 4
    g.add_edge("e_s2_s3", s2_funnel, s3_storm, [(cx, 1066), (cx, 1102)], color="#1E3A8A")
    g.add_edge("e_s3_s4", s3_storm, s4_elo, [(cx, 1224), (cx, 1260)], color="#1E3A8A")

    # Stage 4 -> Stage 5 Fan-Out (split bar y=1404)
    g.add_edge("e_s4_v05", s4_elo, s5_vol05, [(cx, 1382), (cx, 1404), (610, 1404), (610, 1428)], color="#065F46")
    g.add_edge("e_s4_vols", s4_elo, s5_vols, [(cx, 1382), (cx, 1404), (1230, 1404), (1230, 1428)], color="#1E3A8A")

    # Stage 5 -> Join (bar y=1572)
    g.add_edge("e_v05_join", s5_vol05, s5_join, [(610, 1554), (610, 1572), (cx, 1572), (cx, 1590)], color="#065F46")
    g.add_edge("e_vols_join", s5_vols, s5_join, [(1230, 1554), (1230, 1572), (cx, 1572), (cx, 1590)], color="#1E3A8A")

    # Stage 5 Join -> Stage 6 Critic
    g.add_edge("e_join_critic", s5_join, s6_critic, [(cx, 1686), (cx, 1722)], color="#BE123C")

    # Left bounded loop: Critic -> p_rew -> s6_left -> s5_join
    g.add_edge("e_c_prew", s6_critic, p_rew, [(470, 1786), (442, 1786)], color="#7C3AED", dashed=True, stroke_w=2.4)
    g.add_edge("e_prew_l", p_rew, s6_left, [(320, 1786), (177, 1786), (177, 1704)], color="#7C3AED", dashed=True, stroke_w=2.4)
    g.add_edge("e_l_join", s6_left, s5_join, [_mid_right(g.boxes[s6_left]), _mid_left(g.boxes[s5_join])], color="#7C3AED", dashed=True, stroke_w=2.4)

    # Right bounded loop: Critic -> p_crag -> s6_right -> s5_vols
    g.add_edge("e_c_pcrag", s6_critic, p_crag, [(1370, 1786), (1398, 1786)], color="#BE123C", dashed=True, stroke_w=2.4)
    g.add_edge("e_pcrag_r", p_crag, s6_right, [(1536, 1786), (1706, 1786), (1706, 1718)], color="#BE123C", dashed=True, stroke_w=2.4)
    g.add_edge(
        "e_r_vols",
        s6_right,
        s5_vols,
        [(1706, 1562), (1706, 1491), (1500, 1491)],
        color="#BE123C",
        dashed=True,
        stroke_w=2.4,
    )

    # Pass line: Critic -> p_pass -> s7_judge -> s7_compile -> s7_outputs
    g.add_edge("e_c_ppass", s6_critic, p_pass, [(cx, 1850), (cx, 1872)], color="#059669", stroke_w=3.2)
    g.add_edge("e_ppass_j", p_pass, s7_judge, [(cx, 1908), (cx, 1932)], color="#059669", stroke_w=3.2)
    g.add_edge("e_j_comp", s7_judge, s7_compile, [(cx, 2050), (cx, 2082)], color="#065F46", stroke_w=3.0)
    g.add_edge("e_comp_out", s7_compile, s7_outputs, [(cx, 2200), (cx, 2232)], color="#065F46", stroke_w=3.0)

    xml_str = g.build_xml("V2_Dynamic_Discovery_Topology")
    return xml_str, len(g.boxes), len(g.edges)


def main() -> None:
    xml_str, n_boxes, n_edges = build_v2_diagram()
    DOCS_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOCS_OUT.write_text(xml_str, encoding="utf-8")
    print(f"Generated Clean V2 Topology OK | boxes={n_boxes}, edges={n_edges}, geometry_audit=PASS")
    print(f"  - {DOCS_OUT}")


if __name__ == "__main__":
    main()
