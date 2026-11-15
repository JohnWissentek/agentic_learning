#!/usr/bin/env python3
"""Generate Clean, Uncluttered V3.0 Orchestration Topology Diagram.

Highlights V3.0 upgrades on top of V2 dynamic zero-preset discovery:
1. Pillar A: Dual pain-point + commercial-vendor search (`cn/global_vendor_queries`) and
   3-tier white-space classification (`global_and_cn_commercialized`,
   `overseas_only_cn_blank`, `global_and_cn_true_blank`).
2. Pillar B: AI-Era HW/SW Co-Design (PINN computational sensing, synthetic defect
   cold-start, AI-assisted FPGA/EDA/host-SW compressing ~30-48m -> ~10-18m,
   air-gapped Edge-AI + Golden-Tool calibration, BOM localization & GTM form).
3. Strict separation of left control-flow spine from right Context Assembly sidebar,
   plus a clean bottom V1 -> V2 -> V3 evolution strip.

Writes:
- `docs/07_V3_COMMERCIAL_AI_DISCOVERY_TOPOLOGY.drawio`
"""

from __future__ import annotations

import shutil
from pathlib import Path

from generate_a0_workflow_drawio import _mid_bot, _mid_left, _mid_right, _mid_top
from generate_v1_clean_topology_drawio import CleanDiagramBuilder

BASE_DIR = Path("/Users/john/Desktop/agentic_learning/power_semiconductor_opportunities")
DOCS_OUT = BASE_DIR / "docs/07_V3_COMMERCIAL_AI_DISCOVERY_TOPOLOGY.drawio"

CANVAS_W = 2860
CANVAS_H = 2640


def build_diagram() -> CleanDiagramBuilder:
    g = CleanDiagramBuilder(CANVAS_W, CANVAS_H)

    # ------------------------------------------------------------------
    # Top Banner
    # ------------------------------------------------------------------
    g.add_card(
        "banner",
        "BANNER",
        24,
        18,
        2812,
        88,
        hdr_h=40,
        hdr_font=18,
        body_font=13,
        title="PSO V3.0 智能体编排拓扑图：海内外商业在售空白定位 + AI 时代软硬件协同研发新范式 (2026-2036)",
        body=(
            "运行引擎：Antigravity Native (`pro`) + 付费联网检索 (Metaso + Serper -> evidence_vault_v3.db)  |  "
            "左侧为主干控制流与有界反思闭环（浅蓝实线=代码硬编码，琥珀虚线=LLM语义推理，蓝灰=持久化产物，玫红=漏斗门禁），"
            "右侧为 7 类 LLM 角色上下文装配契约与 V1->V2->V3 演进对照。"
        ),
    )

    # Color Legend Strip (x=24..1856, y=118..164)
    g.add_pill("leg_code", 24, 118, 340, 40, "[代码硬编码] Python 确定性搜索/PALMs/校对", fill="#EFF6FF", stroke="#1D4ED8", font_color="#1E3A8A", font_size=12)
    g.add_pill("leg_llm", 384, 118, 360, 40, "[LLM 推理] Antigravity Pro 结构化/并发分析", fill="#FFFBEB", stroke="#D97706", font_color="#92400E", font_size=12)
    g.add_pill("leg_store", 764, 118, 340, 40, "[存储状态] EvidenceVault v3 & JSON 中间件", fill="#F1F5F9", stroke="#475569", font_color="#0F172A", font_size=12)
    g.add_pill("leg_gate", 1124, 118, 340, 40, "[门禁漏斗] 商业空白奖惩 + ROI 红线淘汰", fill="#FFF1F2", stroke="#E11D48", font_color="#9F1239", font_size=12)
    g.add_pill("leg_v3", 1484, 118, 372, 40, "V3 核心约束: 零编造厂商型号 + AI研发周期压缩", fill="#ECFDF5", stroke="#059669", font_color="#065F46", font_size=12)

    # ==================================================================
    # LEFT CONTROL-FLOW SPINE (x=24..1856)
    # ==================================================================

    # ------------------------------------------------------------------
    # Band 0: Stage 0 Macro Recon & Dual Query Planning (y=176, h=290)
    # ------------------------------------------------------------------
    g.add_band(24, 176, 1832, 290, "Stage 0  从零动态宏观侦察：痛点信号 + 商用设备在售态势双路发现 (无预设赛道种子)", accent="#1E3A8A")

    s0_recon = g.add_card(
        "s0_recon",
        "HARDCODED",
        48,
        228,
        540,
        214,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        title="[硬编码] CLI recon-search: 宏观痛点 + 商用侦察",
        body=(
            "1. 读取 `discovery_scope.yaml` (V3 含海内外在售厂商/招投标及 AI 计算传感探测词)\n"
            "2. 并发调用 Metaso (中文) + Serper (英文) 搜索\n"
            "3. 写入 `evidence_vault_v3.db` 分配 [EV-CN/GL-xxx]\n"
            "4. 生成 `data/v3_recon_context.json`"
        ),
    )

    s0_arch = g.add_card(
        "s0_arch",
        "LLM_AGENT",
        652,
        228,
        610,
        214,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        dashed_body=True,
        title="[LLM] Stage 0 Dynamic Track Architect (Pro)",
        body=(
            "1. 从零归纳 8 条正交赛道 (`DP1-DP4` 电力, `DS1-DS4` 半导体)\n"
            "2. 识别交叉新物种 (`is_emerging_or_cross_cutting`)\n"
            "3. 为每条赛道同时生成四组检索词:\n"
            "   痛点词 (`cn_queries`/`global_queries`) +\n"
            "   商用竞争词 (`cn_vendor_queries`/`global_vendor_queries`)"
        ),
    )

    s0_store = g.add_card(
        "s0_store",
        "STORAGE",
        1326,
        228,
        506,
        214,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        title="[存储] data/v3_discovery_plan.json",
        body=(
            "- `contract_id`: PSO-CONTRACT-2026-V3\n"
            "- `track_plans[]`: 赛道定义、物理第一性原理、`cn/global_queries` + `cn/global_vendor_queries`\n"
            "- 注: 若开启 HITL，可在 Stage 0 后审阅赛道规划"
        ),
    )

    # ------------------------------------------------------------------
    # Band 1: Stage 1 Dual Search & Commercial+AI Mining (y=484, h=360)
    # ------------------------------------------------------------------
    g.add_band(24, 484, 1832, 360, "Stage 1  双路深搜（产线痛点 + 海内外在售设备）与 8 赛道并发零种子/AI 协同挖掘", accent="#92400E")

    s1_search = g.add_card(
        "s1_search",
        "HARDCODED",
        48,
        536,
        540,
        282,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        title="[硬编码] CLI track-search: 四通道联网实证入库",
        body=(
            "对每个动态赛道并发执行 4 组检索并去重入库:\n"
            "- CN 痛点/标准/政策 (`cn_queries`)\n"
            "- GL 国际前沿/法规 (`global_queries`)\n"
            "- CN 国产厂商/中标/整机型号 (`cn_vendor_queries`)\n"
            "- GL 海外商业化头部厂商/型号 (`global_vendor_queries`)\n"
            "输出 `data/v3_tracks_evidence.json` (`valid_ev_ids`)"
        ),
    )

    s1_miner = g.add_card(
        "s1_miner",
        "LLM_AGENT",
        652,
        536,
        610,
        282,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        dashed_body=True,
        title="[LLM x8 并发] V3 Commercial + AI Co-Design Miner",
        body=(
            "每个赛道隔离挖掘 3-4 候选 (24-32 原始机会)，强制抽取:\n"
            "1. `commercial_status`: 海内外在售红海 / 海外在售国产空白 / 海内外空白\n"
            "2. 仅引用 `[EV-...]` 列明海外/国内在售型号，无则诚实标疑似空白\n"
            "3. `ai_computational_sensing_and_co_design`: 以算代硬/PINN降BOM\n"
            "4. `ai_rd_acceleration_and_edge_deployment`: 合成缺陷+AI辅助FPGA\n"
            "5. `estimated_rd_months_ai_vs_legacy` + `hardware_bom_...` + 3情景ROI区间"
        ),
    )

    s1_store = g.add_card(
        "s1_store",
        "STORAGE",
        1326,
        536,
        506,
        282,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        title="[存储] data/v3_raw_dossiers.json",
        body=(
            "- `commercial_landscape_summary`: 分赛道在售与空白总结\n"
            "- 每个候选包含 8 项 V3 商业空白与 AI 软硬件协同字段\n"
            "- 附带 `roi_range_inputs` (低/基/高CAPEX与良率提升) 及 `parameter_basis`\n"
            "- 全量 `[EV-CN/GL-...]` ID 绑定用于 Python 确定性核验"
        ),
    )

    # ------------------------------------------------------------------
    # Band 2: Stage 2 Deterministic PALMs, White-Space Scoring & Funnel (y=862, h=300)
    # ------------------------------------------------------------------
    g.add_band(24, 862, 1832, 300, "Stage 2  确定性 Python 财务钳位、商业空白度奖惩校准与多赛道均衡漏斗", accent="#9F1239")

    s2_palms = g.add_card(
        "s2_palms",
        "HARDCODED",
        48,
        914,
        540,
        222,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        title="[硬编码] CLI screen-candidates: 物理边界与三情景ROI",
        body=(
            "1. Pydantic `_val_commercial_status` 与 `_clamp` 参数越界钳位\n"
            "2. `roi_calculator.py` 计算乐观/基准/保守三情景 `[ROI-CALC]`\n"
            "   (CAPEX 1.25x / 收益 0.72x 保守压力, 10% WACC)\n"
            "3. 自动校准加权分:\n"
            "   海外在售·国产空白(+2.0) | 海内外空白(+1.6~2.4) | 红海在售(-1.2)"
        ),
    )

    s2_funnel = g.add_card(
        "s2_funnel",
        "GATE",
        652,
        914,
        610,
        222,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        title="[门禁漏斗] 保守回收期红线 (<=42月) & 赛道配额优选",
        body=(
            "- 过滤保守回收期 >42月、无痛点/缺证据或红海低分化候选\n"
            "- 电力能源 8 席 + 半导体 8 席 = Top 16 决选短名单\n"
            "- 被淘汰候选完整保留至 `eliminated_candidates` (附商业空白级与淘汰原因)\n"
            "- 防止同一成熟红海方向扎堆占坑"
        ),
    )

    s2_store = g.add_card(
        "s2_store",
        "STORAGE",
        1326,
        914,
        506,
        222,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        title="[存储] data/v3_screened_shortlist.json",
        body=(
            "- `shortlist[]`: Top 16 + 三档 `[ROI-CALC]` + 校准分\n"
            "- `commercial_tables`: 商业化在售对照与 AI 协同矩阵\n"
            "- `eliminated_candidates[]`: Stage 2 漏斗淘汰审计清单\n"
            "- `vault_snippets`: 分板块去重证据片段摘要"
        ),
    )

    # ------------------------------------------------------------------
    # Band 3: Stage 3 & Stage 4 STORM + Swiss Elo + Post-Elo Tables (y=1180, h=300)
    # ------------------------------------------------------------------
    g.add_band(24, 1180, 1832, 300, "Stage 3 & 4  四角色工业买方委员会拷问 (STORM) + AI Co-Scientist Elo 双轮锦标赛", accent="#047857")

    s3_storm = g.add_card(
        "s3_storm",
        "LLM_AGENT",
        48,
        1232,
        540,
        222,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        dashed_body=True,
        title="[LLM x16 并发] V3 STORM 产线四方买方委员会",
        body=(
            "围绕 Fab良率VP / 工艺测量总工 / EHS总监 / CFO采购 逐项拷问:\n"
            "- 红海竞品切换成本 vs 首台套空白 Golden-Tool 验证周期\n"
            "- 半导体/电力厂区物理断网部署 FPGA+NPU 边缘 AI 可靠性与可解释性\n"
            "- 核心光学/射频/探测器 BOM 断供风险与保守下限 ROI 承压能力"
        ),
    )

    s4_elo = g.add_card(
        "s4_elo",
        "LLM_AGENT",
        652,
        1232,
        610,
        222,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        dashed_body=True,
        title="[LLM x2轮] Swiss-System Elo 成对锦标赛 + Python终排",
        body=(
            "每轮成对盲评对比维度权重:\n"
            "- 制造业三情景 ROI 与保守韧性 (30%) | 良率质量收益 (25%)\n"
            "- 商业空白稀缺度: 国产空白/全球空白 vs 红海 (25%)\n"
            "- AI 软硬件协同可行性、研发压缩与绿色环保 (20%)\n"
            "Python 确定性终排 = 0.55 * WeightedPillar + 0.45 * NormElo"
        ),
    )

    s4_post = g.add_card(
        "s4_post",
        "HARDCODED",
        1326,
        1232,
        506,
        222,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        title="[硬编码] Post-Elo 双基准真值表装配",
        body=(
            "1. `_format_post_elo_roi_table()`: 含【商业空白级】与三档 `[ROI-CALC]` 主表\n"
            "2. `_format_post_elo_commercial_table()`: 海内外在售厂商/型号对照、\n"
            "   AI 计算传感降本方案、AI 研发周期 vs 传统、BOM 国产化与 GTM 切入形态\n"
            "3. 注入 Stage 5 作为不可篡改的唯一数值与竞品底座"
        ),
    )

    # ------------------------------------------------------------------
    # Band 4: Stage 5 Parallel 5-Volume Grounded Report Synthesis (y=1498, h=280)
    # ------------------------------------------------------------------
    g.add_band(24, 1498, 1832, 280, "Stage 5  五卷并行产业级研报撰写 (强制商业竞品零编造 + AI 软硬件协同范式全覆盖)", accent="#6D28D9")

    s5_v012 = g.add_card(
        "s5_v012",
        "LLM_AGENT",
        48,
        1550,
        580,
        202,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        dashed_body=True,
        title="[LLM 并行] 00 战略总报告 / 01 电力能源 / 02 半导体分卷",
        body=(
            "- `00`: 全景在售vs空白图谱统计 + AI研发新范式总论 + Top 16总表\n"
            "- `01`: 新型电力系统/AIDC供配电商业在售盘点 + AI边缘声学/光谱\n"
            "- `02`: 晶圆制造/先进封装/宽禁带海内外设备对比 + AI反演/超分辨突破\n"
            "- 严格约束: 中国优先->全球跟进；严禁编造未经 `[EV]` 实证的仪器型号"
        ),
    )

    s5_v34 = g.add_card(
        "s5_v34",
        "LLM_AGENT",
        672,
        1550,
        610,
        202,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        dashed_body=True,
        title="[LLM 并行] 03 财务空白校准卷 / 04 AI软硬件协同 Playbook",
        body=(
            "- `03`: 三情景 PALMs + 商业空白加权灵敏度 + Stage 2 淘汰审计 + CFO算账模板\n"
            "- `04`: 传统 30-48月 vs AI协同 10-18月全流程对照（PINN -> 合成缺陷冷启动\n"
            "  -> AI辅助FPGA/EDA/上位机 -> 断网边缘NPU+Golden-Tool自校准）+\n"
            "  三类商业战场 GTM 打法（红海AI降本 / 国产空白平替 / 全球空白首台套）"
        ),
    )

    s5_mem = g.add_card(
        "s5_mem",
        "STORAGE",
        1326,
        1550,
        506,
        202,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        title="[存储] 内存五卷草稿 & 确定性基线遥测",
        body=(
            "- `volumes[00..04]` 五卷完整 Markdown 文本\n"
            "- `_previews_and_checks()` 自动核查:\n"
            "  `distinct_ev_ids_cited`, `[ROI-CALC]` 计数, `commercial_whitespace_breakdown`,\n"
            "  商业空白关键词覆盖 & AI软硬件协同技术词覆盖"
        ),
    )

    # ------------------------------------------------------------------
    # Band 5: Stage 6 Bounded Critic + Corrective RAG & Stage 7 Judge (y=1796, h=420)
    # ------------------------------------------------------------------
    g.add_band(24, 1796, 1832, 420, "Stage 6 & 7  有界异构 Critic 反思 + 补搜纠正 RAG + 独立门禁裁判 + finalize-v3 落盘", accent="#B45309")

    s6_critic = g.add_card(
        "s6_critic",
        "LLM_AGENT",
        48,
        1852,
        540,
        166,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        dashed_body=True,
        title="[LLM] Stage 6 Heterogeneous Critic (<= 2 Loops)",
        body=(
            "严苛审计商业化与工程接地气程度:\n"
            "1. 是否具体点明海内外在售厂商/空白定级且零型号编造?\n"
            "2. 是否讲透 AI 计算传感降 BOM、合成缺陷、FPGA压缩与断网部署?\n"
            "输出: `pass` | `needs_more_evidence` | `needs_rewrite`"
        ),
    )

    s6_gap = g.add_card(
        "s6_gap",
        "HARDCODED",
        48,
        2038,
        540,
        158,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        title="[硬编码 + LLM] 纠偏 RAG 补搜 (gap-search) + Reviser",
        body=(
            "1. 若 `needs_more_evidence`: CLI `gap-search` 针对 `gap_queries` 补搜厂商或BOM实证\n"
            "2. 并行唤醒 `Reviser` 仅定向修订 `issues` 命中的分卷\n"
            "3. 回流 Critic 二次复审；达上限 `max_loops=2` 后强制跳出防死循环"
        ),
    )

    s7_judge = g.add_card(
        "s7_judge",
        "LLM_AGENT",
        652,
        1852,
        610,
        344,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        dashed_body=True,
        title="[LLM + 确定性校验] Stage 7 独立门禁裁判 (Gate >= 85/100)",
        body=(
            "1. Python `deterministic_contract_checks()` 十项硬指标校验:\n"
            "   - `no_secret_leaked`, `distinct_ev_ids >= 15`, `roi_calc_tag_count >= 16`\n"
            "   - `commercial_whitespace_grounded=True` (在售/空白实证对照完整)\n"
            "   - `ai_native_paradigm_present=True` (计算传感/FPGA/软硬件协同到位)\n"
            "2. Stage-Gate Judge 5 维度 (每项 0-20，总分 100):\n"
            "   - 中国优先与商业空白研判 | 双时间窗分化 | 物理与AI软硬件协同 |\n"
            "   - 确定性ROI与研发压缩价值 | 全文 `[EV-CN/GL]` 零编造实证\n"
            "3. 输出 `judge_rubric` 与 `executive_verdict`"
        ),
    )

    s7_final = g.add_card(
        "s7_final",
        "HARDCODED",
        1326,
        1852,
        506,
        344,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        title="[硬编码] CLI finalize-v3: 确定性归档交付",
        body=(
            "将 `data/v3_native_outputs_bundle.json` 与 Vault 合并落盘至:\n"
            "`outputs/v3_commercial_ai_grounded_2026_2036/`\n"
            "- `00`..`04` 五卷战略/行业/财务/AI Playbook 研报\n"
            "- `05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md`\n"
            "- `06_EVALUATION_SCORECARD_AND_COST_TELEMETRY.json` (含商业空白分布)\n"
            "- `07_V3_COMMERCIAL_WHITESPACE_AND_AI_PARADIGM_SUMMARY.md`\n"
            "- `08_V3_COMMERCIAL_AI_DISCOVERY_TOPOLOGY.{drawio,pdf,svg}`\n"
            "注: V1 与 V2 历史产出目录保持 100% 完整不被覆盖。"
        ),
    )

    # ------------------------------------------------------------------
    # Bottom Strip: V1.0 -> V2.0 -> V3.0 Architecture Evolution (y=2234, h=380)
    # ------------------------------------------------------------------
    g.add_band(24, 2234, 1832, 380, "核心范式跃迁对比：V1.0 (静态预设)  ->  V2.0 (从零动态发现)  ->  V3.0 (海内外商业空白 + AI软硬件协同落脚点)", accent="#0F172A")

    ev_v1 = g.add_card(
        "ev_v1",
        "STORAGE",
        48,
        2286,
        560,
        304,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        title="V1.0  静态预设本体驱动 (理论基线归档)",
        body=(
            "- 赛道发现: YAML 硬编码 P1-P4 / S1-S4 静态 8 赛道，易遗漏跨界新物种\n"
            "- 竞品与空白: 未系统检索海内外已上市整机，易将成熟红海误判为新机会\n"
            "- 研发范式: 默认按传统 36-48 个月纯物理样机与常规上位机模式评估\n"
            "- ROI 建模: 早期单点估值 + 基础 PALMs\n"
            "- 归档目录: `outputs/power_semiconductor_online_testing_2026_2036/`"
        ),
    )

    ev_v2 = g.add_card(
        "ev_v2",
        "HARDCODED",
        640,
        2286,
        580,
        304,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        title="V2.0  从零动态发现 + 三情景漏斗 (结构升级归档)",
        body=(
            "- 赛道发现: Stage 0 联网侦察后零预设归纳 DP1-4 / DS1-4 与新物种\n"
            "- 竞品与空白: 仍偏向技术与产业痛点推演，缺少国内外已售商业产品对标\n"
            "- 研发范式: 关注工程化五道坎，但未系统建模 AI 以算代硬与研发周期重构\n"
            "- ROI 建模: 三情景参数区间 (乐观/基准/保守) + 淘汰审计\n"
            "- 归档目录: `outputs/v2_dynamic_discovery_2026_2036/`"
        ),
    )

    ev_v3 = g.add_card(
        "ev_v3",
        "LLM_AGENT",
        1252,
        2286,
        580,
        304,
        hdr_h=38,
        hdr_font=14,
        body_font=13,
        title="V3.0  商业在售空白图谱 + AI软硬件协同 (本次实战交付)",
        body=(
            "- 商业竞品深搜: 四通道搜索 (`vendor_queries`) 实证区分红海/国产空白/全球空白\n"
            "- 评分奖惩校准: 国产空白 (+2.0) / 全球空白 (+2.4) 加分，红海拥挤 (-1.2) 扣分\n"
            "- AI 研发新范式: 计算传感 PINN 降 BOM、合成缺陷冷启动、AI辅助FPGA提速至 10-18月\n"
            "- 落地 GTM 颗粒度: 产线断网 NPU+FPGA、BOM 国产化件与 OEM/整机切入形态\n"
            "- 归档目录: `outputs/v3_commercial_ai_grounded_2026_2036/`"
        ),
    )

    # ==================================================================
    # RIGHT REFERENCE SIDEBAR: Context Assembly Contracts (x=1892..2836)
    # ==================================================================
    g.add_band(1892, 118, 944, 2496, "7 大 LLM 角色上下文装配契约 (Context Engineering & Grounding Contracts)", accent="#065F46")

    g.add_card(
        "ctx_s0",
        "CONTEXT_BOX",
        1916,
        172,
        896,
        270,
        hdr_h=36,
        hdr_font=14,
        body_font=13,
        title="Context 1: Stage 0 Track Architect (Zero-Preset + Vendor Queries)",
        body=(
            "- 输入 Context: `sector_mandates` 行业边界 + `recon_context_text` ([EV-CN/GL] 宏观痛点+商用/中标信号)\n"
            "- Schema 输出 (`DISCOVERY_PLAN_SCHEMA`):\n"
            "  `track_plans[]` 除 `cn_queries` / `global_queries` 外，强制输出:\n"
            "  `cn_vendor_queries` (国产在售/招投标/设备型号) + `global_vendor_queries` (海外商业龙头与型号)"
        ),
    )

    g.add_card(
        "ctx_s1",
        "CONTEXT_BOX",
        1916,
        462,
        896,
        382,
        hdr_h=36,
        hdr_font=14,
        body_font=13,
        title="Context 2: Stage 1 Commercial+AI Miner (Per-Track Isolated Context)",
        body=(
            "- 隔离 Context: 仅注入单条赛道 `tp` + 赛道 ROI 守门提示 (`guardrail_hint`) +\n"
            "  Python 去重后的 `evidence_context` (融合痛点检索 + 海内外在售厂商检索) + `valid_ev_ids`\n"
            "- 零幻觉防线: 明确禁止编造任何未出现在 `[EV-...]` 中的海外/国产商业型号；无则输出\n"
            "  `尚未检索到量产在售整机（疑似空白）`\n"
            "- V3 结构化契约 (`TRACK_MINER_SCHEMA`): `commercial_status`, `global_vendors_and_products`,\n"
            "  `china_vendors_and_products`, `white_space_and_entry_wedge`, `ai_computational_sensing_and_co_design`,\n"
            "  `ai_rd_acceleration_and_edge_deployment`, `estimated_rd_months_ai_vs_legacy`, `hardware_bom_localization_and_gtm_form`"
        ),
    )

    g.add_card(
        "ctx_s3",
        "CONTEXT_BOX",
        1916,
        864,
        896,
        304,
        hdr_h=36,
        hdr_font=14,
        body_font=13,
        title="Context 3: Stage 3 V3 STORM Buyer Panel (16x Shortlisted)",
        body=(
            "- 输入 Context: Python 算好的 Optimistic/Baseline/Conservative `[ROI-CALC]` 财务指标 +\n"
            "  `commercial_status` 与海内外竞品对照 + `ai_computational_sensing` + `bom_localization` + 研发周期\n"
            "- 4 买方拷问焦点: 1) 在售红海切单阻力 vs 空白首台套 Golden-Tool 标定成本；\n"
            "  2) 晶圆厂/变电站物理断网条件下 Edge-AI NPU+FPGA 可解释性与稳定性；\n"
            "  3) 保守情景 CAPEX 1.25x 下是否仍满足 <= 42 个月现金流回本红线"
        ),
    )

    g.add_card(
        "ctx_s4",
        "CONTEXT_BOX",
        1916,
        1188,
        896,
        290,
        hdr_h=36,
        hdr_font=14,
        body_font=13,
        title="Context 4: Stage 4 AI Co-Scientist Elo Judge (Pairwise)",
        body=(
            "- 输入 Context (`_pair_summary`): 成对展示两个候选的 `[ROI-CALC]` 指标 + `商业状态` 标签 +\n"
            "  CN/GL 在售竞品快照 + AI 以算代硬/研发周期摘要 + 良率与产业升级机理\n"
            "- V3 裁决权重: 制造 ROI 与保守韧性 (30%) + 良率质量 (25%) +\n"
            "  商业空白稀缺性 (`overseas_only_cn_blank` / `global_blank` 优先于拥挤红海, 25%) +\n"
            "  AI 软硬件协同与环保 (20%)"
        ),
    )

    g.add_card(
        "ctx_s5",
        "CONTEXT_BOX",
        1916,
        1498,
        896,
        356,
        hdr_h=36,
        hdr_font=14,
        body_font=13,
        title="Context 5: Stage 5 5-Volume Synthesizers (Dual Grounded Truth)",
        body=(
            "- 不可篡改双真值底座:\n"
            "  1) `roi_*_tbl`: 含【商业空白级】的确定性 3 情景 `[ROI-CALC]` Post-Elo 排位表\n"
            "  2) `comm_*_tbl`: 海内外在售厂商/型号对照 + AI 算力换硬件 + 研发周期压缩 + BOM/GTM 总表\n"
            "- 叠加输入: `discovery_funnel_md` + `dossiers_*_md` + `storm_*_txt` + `vault_snippets`\n"
            "- Volume 04 专属 Context 引导拆解传统(30-48m) vs AI(10-18m) 四步研发流水线及三类 GTM 打法"
        ),
    )

    g.add_card(
        "ctx_s6",
        "CONTEXT_BOX",
        1916,
        1874,
        896,
        350,
        hdr_h=36,
        hdr_font=14,
        body_font=13,
        title="Context 6: Stage 6 Critic Reviewer & Targeted Reviser Loop",
        body=(
            "- Critic 输入 Context: `det_summary` 确定性统计 (`vault`, `commercial_whitespace_breakdown`,\n"
            "  `distinct_ev_ids_cited`, `roi_calc_tags`, `has_commercial_whitespace_terms`, `has_ai_codesign_terms`)\n"
            "  + 五卷首尾摘要 `previews`\n"
            "- Reviser Context: 仅接收 `critic.issues` 中与本卷匹配的整改意见 + `gap-search` 新增补搜片段 +\n"
            "  本卷当前全文，严格锁定不得修改任何 `[ROI-CALC]` 或编造厂商型号"
        ),
    )

    g.add_card(
        "ctx_s7",
        "CONTEXT_BOX",
        1916,
        2244,
        896,
        346,
        hdr_h=36,
        hdr_font=14,
        body_font=13,
        title="Context 7: Stage 7 Independent V3 Stage-Gate Judge",
        body=(
            "- 输入 Context: 最终 `det_summary` + Stage 6 Critic 终审结论 + 五卷完整首尾预览\n"
            "- 五维 0-20 评分 (Gate >= 85/100 放行):\n"
            "  1) 中国优先及海内外在售/空白盘点精度  2) 3-5年放量 vs 5-10年空白前瞻性\n"
            "  3) 物理机理与 AI 软硬件协同实操深度    4) 确定性 PALMs ROI 与研发压缩商业价值\n"
            "  5) `[EV-CN/GL]` 全程溯源合规与零编造\n"
            "- 联合 Python `deterministic_contract_checks()` 共同签发终版计分卡 JSON"
        ),
    )

    # ==================================================================
    # ORTHOGONAL CLEAN EDGES (Strictly routed inside lanes, zero box crossings)
    # ==================================================================

    # Stage 0 horizontal
    g.add_edge("s0_1", s0_recon, s0_arch, [_mid_right(g.boxes[s0_recon]), _mid_left(g.boxes[s0_arch])], color="#1E3A8A")
    g.add_edge("s0_2", s0_arch, s0_store, [_mid_right(g.boxes[s0_arch]), _mid_left(g.boxes[s0_store])], color="#D97706", dashed=True)

    # Stage 0 store down to Stage 1 search (via top corridor y=474)
    p_s0_out = _mid_bot(g.boxes[s0_store])
    p_s1_in = _mid_top(g.boxes[s1_search])
    g.add_edge(
        "s0_to_s1",
        s0_store,
        s1_search,
        [p_s0_out, (p_s0_out[0], 474), (p_s1_in[0], 474), p_s1_in],
        color="#475569",
    )

    # Stage 1 horizontal
    g.add_edge("s1_1", s1_search, s1_miner, [_mid_right(g.boxes[s1_search]), _mid_left(g.boxes[s1_miner])], color="#1E3A8A")
    g.add_edge("s1_2", s1_miner, s1_store, [_mid_right(g.boxes[s1_miner]), _mid_left(g.boxes[s1_store])], color="#D97706", dashed=True)

    # Stage 1 store down to Stage 2 PALMs (via corridor y=852)
    p_s1_out = _mid_bot(g.boxes[s1_store])
    p_s2_in = _mid_top(g.boxes[s2_palms])
    g.add_edge(
        "s1_to_s2",
        s1_store,
        s2_palms,
        [p_s1_out, (p_s1_out[0], 852), (p_s2_in[0], 852), p_s2_in],
        color="#475569",
    )

    # Stage 2 horizontal
    g.add_edge("s2_1", s2_palms, s2_funnel, [_mid_right(g.boxes[s2_palms]), _mid_left(g.boxes[s2_funnel])], color="#1E3A8A")
    g.add_edge("s2_2", s2_funnel, s2_store, [_mid_right(g.boxes[s2_funnel]), _mid_left(g.boxes[s2_store])], color="#E11D48")

    # Stage 2 store down to Stage 3 STORM (via corridor y=1170)
    p_s2_out = _mid_bot(g.boxes[s2_store])
    p_s3_in = _mid_top(g.boxes[s3_storm])
    g.add_edge(
        "s2_to_s3",
        s2_store,
        s3_storm,
        [p_s2_out, (p_s2_out[0], 1170), (p_s3_in[0], 1170), p_s3_in],
        color="#475569",
    )

    # Stage 3 & 4 horizontal
    g.add_edge("s3_1", s3_storm, s4_elo, [_mid_right(g.boxes[s3_storm]), _mid_left(g.boxes[s4_elo])], color="#D97706", dashed=True)
    g.add_edge("s4_1", s4_elo, s4_post, [_mid_right(g.boxes[s4_elo]), _mid_left(g.boxes[s4_post])], color="#047857", dashed=True)

    # Stage 4 post down to Stage 5 v012 (via corridor y=1488)
    p_s4_out = _mid_bot(g.boxes[s4_post])
    p_s5_in = _mid_top(g.boxes[s5_v012])
    g.add_edge(
        "s4_to_s5",
        s4_post,
        s5_v012,
        [p_s4_out, (p_s4_out[0], 1488), (p_s5_in[0], 1488), p_s5_in],
        color="#1E3A8A",
    )

    # Stage 5 horizontal (s5_v012 -> s5_mem and s5_v34 -> s5_mem, both fed by Stage 4 post)
    g.add_edge(
        "s4_to_s5b",
        s4_post,
        s5_v34,
        [p_s4_out, (p_s4_out[0], 1488), (_mid_top(g.boxes[s5_v34])[0], 1488), _mid_top(g.boxes[s5_v34])],
        color="#1E3A8A",
    )
    g.add_edge("s5_1", s5_v34, s5_mem, [_mid_right(g.boxes[s5_v34]), _mid_left(g.boxes[s5_mem])], color="#6D28D9", dashed=True)

    # Stage 5 mem down to Stage 6 critic (via corridor y=1786)
    p_s5_out = _mid_bot(g.boxes[s5_mem])
    p_s6_in = _mid_top(g.boxes[s6_critic])
    g.add_edge(
        "s5_to_s6",
        s5_mem,
        s6_critic,
        [p_s5_out, (p_s5_out[0], 1786), (p_s6_in[0], 1786), p_s6_in],
        color="#475569",
    )

    # Stage 6 Critic <-> Gap Reviser loop (short clean vertical down + left outer feedback)
    g.add_edge("s6_fail", s6_critic, s6_gap, [_mid_bot(g.boxes[s6_critic]), _mid_top(g.boxes[s6_gap])], color="#D97706", dashed=True)
    p_gap_l = _mid_left(g.boxes[s6_gap])
    p_crit_l = _mid_left(g.boxes[s6_critic])
    g.add_edge(
        "s6_retry",
        s6_gap,
        s6_critic,
        [p_gap_l, (34, p_gap_l[1]), (34, p_crit_l[1]), p_crit_l],
        color="#B45309",
        dashed=True,
    )

    # Stage 6 Critic pass -> Stage 7 Judge -> finalize-v3
    p_crit_r = _mid_right(g.boxes[s6_critic])
    p_judge_l = _mid_left(g.boxes[s7_judge])
    g.add_edge(
        "s6_pass",
        s6_critic,
        s7_judge,
        [p_crit_r, (620, p_crit_r[1]), (620, p_judge_l[1]), p_judge_l],
        color="#059669",
    )
    g.add_edge("s7_1", s7_judge, s7_final, [_mid_right(g.boxes[s7_judge]), _mid_left(g.boxes[s7_final])], color="#1E3A8A")

    # Right context reference connectors (subtle dashed gray into context rail x=1874)
    for idx, (src_box, ctx_id) in enumerate(
        [
            (s0_store, "node_ctx_s0"),
            (s1_store, "node_ctx_s1"),
            (s2_store, "node_ctx_s3"),
            (s4_post, "node_ctx_s4"),
            (s5_mem, "node_ctx_s5"),
            (s7_final, "node_ctx_s6"),
        ]
    ):
        p_src = _mid_right(g.boxes[src_box])
        p_dst = _mid_left(g.boxes[ctx_id])
        g.add_edge(
            f"ctx_ref_{idx}",
            src_box,
            ctx_id,
            [p_src, (1874, p_src[1]), (1874, p_dst[1]), p_dst],
            color="#94A3B8",
            dashed=True,
            stroke_w=1.8,
        )

    return g


def main() -> None:
    builder = build_diagram()
    xml_str = builder.build_xml("PSO_V3_Commercial_AI_Discovery_Topology")
    DOCS_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOCS_OUT.write_text(xml_str, encoding="utf-8")
    print(f"Wrote {DOCS_OUT} ({len(xml_str)} bytes); geometry_audit=PASS")


if __name__ == "__main__":
    main()
