"""Antigravity IDE Native Hybrid Workflow (`run_workflow`) for BoilerSense-AI™ IPD & NPI.

Orchestrates an 8-Stage Multi-Agent Product R&D Team strictly adhering to Google's
`Agentic Design Patterns` (Ch 1-21 & Appendices A-G):
- Native Antigravity frontier reasoning (`pro` / `flash` subagents via `agent()`, `parallel()`, `phase()`)
- Deterministic Python CLI spine (`bfbg-workflow`) for SQLite EvidenceVault, Metaso+Serper search,
  OEM PDF datasheet downloading/SHA256 verification, PALMs engineering/BOM/financial calculations,
  Zero-LLM Vol 07 index, Draw.io vector rendering, and Vol 08 scorecard telemetry.
"""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path

BASE_DIR = Path("/Users/john/Desktop/agentic_learning/Boiler_FBG_Product_RD_Workflow/agentic_workflow")
VENV_CLI = BASE_DIR / ".venv/bin/bfbg-workflow"

_user_args = args if "args" in globals() and isinstance(args, dict) else {}
profile = str(_user_args.get("profile", "flagship"))
output_dir = str(_user_args.get("output_dir", "../output"))
vault_db = str(_user_args.get("vault_db", "data/bfbg_evidence_vault.db"))
target_model = str(_user_args.get("model", "pro"))
fast_model = str(_user_args.get("fast_model", "flash"))
run_id = f"bfbg-native-{uuid.uuid4().hex[:8]}"
max_loops = 2 if profile == "flagship" else 1

NO_TOOL_DIRECTIVE = (
    "\n\nCRITICAL DIRECTIVE: All verified EvidenceVault excerpts ([EV-BASE-*], [EV-CN-*], [EV-GL-*], [EV-PDF-*]), "
    "verified OEM PDF filenames in `./datasheets_pdf/`, and deterministic Python calculations "
    "([PHY-CALC], [BOM-CALC], [FIN-CALC], [PLANT-ROI]) are ALREADY injected into this prompt. "
    "Do NOT call any filesystem, shell, search, or browser tools. Complete your work in one single turn "
    "and return ONLY valid JSON via `finish` matching the schema."
)


def _run_cli(cli_args: list[str]) -> str:
    proc = subprocess.run(
        [str(VENV_CLI), *cli_args],
        cwd=str(BASE_DIR),
        check=True,
        capture_output=True,
        text=True,
    )
    out = proc.stdout.strip()
    if out:
        log(out)
    return out


# ---------------------------------------------------------------------------
# Strict Flat JSON Schemas (ZERO $ref / ZERO $defs for run_workflow `agent()`)
# ---------------------------------------------------------------------------

TRACK_ENUM = [
    "T1_MARKET_POLICY",
    "T2_COMPETITIVE_INTEL",
    "T3_OPTICS_HARDWARE",
    "T4_FIBER_BOILER_PACKAGING",
    "T5_SOFTWARE_BOILER_AI",
    "T6_NPI_QAQC_FINANCE",
]

DISCOVERY_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "contract_id": {"type": "string"},
        "profile": {"type": "string"},
        "step_back_thesis": {"type": "string"},
        "china_market_positioning": {"type": "string"},
        "track_plans": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "track_id": {"type": "string", "enum": TRACK_ENUM},
                    "role_title": {"type": "string"},
                    "focus_mandate": {"type": "string"},
                    "cn_queries": {"type": "array", "items": {"type": "string"}},
                    "global_queries": {"type": "array", "items": {"type": "string"}},
                    "pdf_queries": {"type": "array", "items": {"type": "string"}},
                    "priority": {"type": "integer"},
                },
                "required": [
                    "track_id",
                    "role_title",
                    "focus_mandate",
                    "cn_queries",
                    "global_queries",
                    "pdf_queries",
                    "priority",
                ],
            },
        },
    },
    "required": [
        "contract_id",
        "profile",
        "step_back_thesis",
        "china_market_positioning",
        "track_plans",
    ],
}

SPECIALIST_DOSSIER_SCHEMA = {
    "type": "object",
    "properties": {
        "track_id": {"type": "string", "enum": TRACK_ENUM},
        "role_title": {"type": "string"},
        "executive_findings": {"type": "string"},
        "key_technical_decisions": {"type": "array", "items": {"type": "string"}},
        "competitors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "vendor_name": {"type": "string"},
                    "segment": {"type": "string"},
                    "representative_product": {"type": "string"},
                    "optical_route": {"type": "string"},
                    "claimed_capability_and_price_band": {"type": "string"},
                    "key_weaknesses_or_gaps": {"type": "string"},
                    "our_win_wedge": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "vendor_name",
                    "segment",
                    "representative_product",
                    "optical_route",
                    "claimed_capability_and_price_band",
                    "key_weaknesses_or_gaps",
                    "our_win_wedge",
                    "evidence_ids",
                ],
            },
        },
        "selected_components": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subsystem": {"type": "string"},
                    "product_tier": {"type": "string"},
                    "primary_vendor": {"type": "string"},
                    "part_number": {"type": "string"},
                    "backup_vendor_and_model": {"type": "string"},
                    "electrical_optical_interface": {"type": "string"},
                    "mechanical_env_rating": {"type": "string"},
                    "datasheet_filename": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "subsystem",
                    "product_tier",
                    "primary_vendor",
                    "part_number",
                    "backup_vendor_and_model",
                    "electrical_optical_interface",
                    "mechanical_env_rating",
                    "datasheet_filename",
                    "evidence_ids",
                ],
            },
        },
        "qa_or_field_risks": {"type": "array", "items": {"type": "string"}},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "track_id",
        "role_title",
        "executive_findings",
        "key_technical_decisions",
        "competitors",
        "selected_components",
        "qa_or_field_risks",
        "evidence_ids",
    ],
}

IPD_MEMO_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_readiness_verdict": {"type": "string"},
        "critical_interface_risks": {"type": "array", "items": {"type": "string"}},
        "design_for_manufacturing_actions": {"type": "array", "items": {"type": "string"}},
        "qa_calibration_mandates": {"type": "array", "items": {"type": "string"}},
        "cost_down_levers": {"type": "array", "items": {"type": "string"}},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "overall_readiness_verdict",
        "critical_interface_risks",
        "design_for_manufacturing_actions",
        "qa_calibration_mandates",
        "cost_down_levers",
        "evidence_ids",
    ],
}

STORM_PANEL_SCHEMA = {
    "type": "object",
    "properties": {
        "chief_engineer_concerns": {"type": "array", "items": {"type": "string"}},
        "boiler_inspection_head_demands": {"type": "array", "items": {"type": "string"}},
        "ic_cybersecurity_hard_gates": {"type": "array", "items": {"type": "string"}},
        "cfo_procurement_thresholds": {"type": "array", "items": {"type": "string"}},
        "winning_value_propositions": {"type": "array", "items": {"type": "string"}},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "chief_engineer_concerns",
        "boiler_inspection_head_demands",
        "ic_cybersecurity_hard_gates",
        "cfo_procurement_thresholds",
        "winning_value_propositions",
        "evidence_ids",
    ],
}

ELO_MATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "round_num": {"type": "integer"},
        "arch_a": {"type": "string"},
        "arch_b": {"type": "string"},
        "winner": {"type": "string"},
        "margin": {"type": "string", "enum": ["decisive", "narrow"]},
        "rationale": {"type": "string"},
    },
    "required": ["round_num", "arch_a", "arch_b", "winner", "margin", "rationale"],
}

VOLUME_REPORT_SCHEMA = {
    "type": "object",
    "properties": {"markdown": {"type": "string"}},
    "required": ["markdown"],
}

CRITIC_AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "passed": {"type": "boolean"},
        "overall_assessment": {"type": "string"},
        "volumes_to_rewrite": {"type": "array", "items": {"type": "string"}},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "volume": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                    "finding": {"type": "string"},
                    "fix_instruction": {"type": "string"},
                    "needs_crag_gap_search": {"type": "boolean"},
                    "suggested_geo_scope": {"type": "string", "enum": ["CN", "GLOBAL", "PDF"]},
                    "suggested_query": {"type": "string"},
                },
                "required": [
                    "volume",
                    "severity",
                    "finding",
                    "fix_instruction",
                    "needs_crag_gap_search",
                    "suggested_geo_scope",
                    "suggested_query",
                ],
            },
        },
    },
    "required": ["passed", "overall_assessment", "volumes_to_rewrite", "issues"],
}

JUDGE_RUBRIC_SCHEMA = {
    "type": "object",
    "properties": {
        "market_and_competitive_rigor": {"type": "number"},
        "hardware_selection_and_interface_completeness": {"type": "number"},
        "software_demod_and_boiler_ai_actionability": {"type": "number"},
        "npi_qaqc_bringup_and_field_sop": {"type": "number"},
        "financial_gtm_training_and_traceability": {"type": "number"},
        "total_score": {"type": "number"},
        "pass_status": {"type": "string", "enum": ["PASS", "NEEDS_HUMAN_REVIEW"]},
        "executive_verdict": {"type": "string"},
        "key_strengths": {"type": "array", "items": {"type": "string"}},
        "remaining_gaps": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "market_and_competitive_rigor",
        "hardware_selection_and_interface_completeness",
        "software_demod_and_boiler_ai_actionability",
        "npi_qaqc_bringup_and_field_sop",
        "financial_gtm_training_and_traceability",
        "total_score",
        "pass_status",
        "executive_verdict",
        "key_strengths",
        "remaining_gaps",
    ],
}


# ---------------------------------------------------------------------------
# Stage 0: Prior Read-Only Ingestion, Macro Recon & Chief PM Step-Back Planner
# ---------------------------------------------------------------------------
phase("Stage 0: Baseline Ingestion, Live Recon & Chief PM Step-Back Planning")
_run_cli(
    [
        "prepare-evidence",
        "--profile",
        profile,
        "--vault-db",
        vault_db,
        "--output-file",
        "data/stage0_recon_context.json",
    ]
)
recon_ctx = json.loads((BASE_DIR / "data/stage0_recon_context.json").read_text(encoding="utf-8"))

planner_prompt = (
    "You are the Chief Product Manager leading BoilerSense-AI™ (Coal-Fired Power Plant Waterwall FBG Thermometry & AI Product Team).\n"
    "Apply Step-Back Prompting & Factored Cognition to plan 6 orthogonal R&D & GTM tracks:\n"
    "1. `T1_MARKET_POLICY`: China coal power retrofit/deep peak-shaving market & waterwall tube leak pain points.\n"
    "2. `T2_COMPETITIVE_INTEL`: Domestic (理工光科, 太辰光, 东方锐择, 深圳光子传感) & global (Luna, FBGS, Omnisens, Yokogawa) competitors + acoustic/IR/TC.\n"
    "3. `T3_OPTICS_HARDWARE`: Off-the-shelf international optical/DAQ/edge hardware (Ibsen I-MON 512, Amonics ASE, Sercalo MEMS, Santec/Lumentum, FEMTO, Spectrum M2p, Wavelength Ref HCN-13, Moxa, Advantech, MeanWell).\n"
    "4. `T4_FIBER_BOILER_PACKAGING`: Track A (FBGS FSG / FemtoFiberTec + OFS PyroCoat / Fibercore + Sandvik) vs Track B (YOFC 200kpsi PI/carbon + certified femto/DTG + 15CrMoG loose-tube thermal blocks & welding).\n"
    "5. `T5_SOFTWARE_BOILER_AI`: Sub-picometer peak tracking, spline HCN calibration, Kriging 3D wall map, Phase-1 read-only bypass AI (slagging/sootblowing, Larson-Miller creep, flame skew) -> Phase-2 closed-loop.\n"
    "6. `T6_NPI_QAQC_FINANCE`: Lean assembly/650°C calibration/72h burn-in/IQC-IPQC-FAT-SAT, 5-year financials, GTM, engineer & sales training.\n\n"
    f"Product Positioning: Modular dual-tier (BS-STD-600: 300-600 pts; BS-PRO-2000: 1000-2000+ pts).\n"
    f"Prior Baseline Notes [EV-BASE-*]:\n{recon_ctx['prior_context_text'][:4000]}\n\n"
    f"Live Recon:\n{recon_ctx['recon_context_text'][:4000]}\n\n"
    "Emit `ProductDiscoveryPlan` JSON with exactly the 6 `track_plans`, each having 2-3 high-precision CN queries and 2-3 GLOBAL queries."
    + NO_TOOL_DIRECTIVE
)
plan_obj = await agent(
    prompt=planner_prompt,
    schema=DISCOVERY_PLAN_SCHEMA,
    role="Chief Product Manager",
    model=target_model,
)
plan_file = BASE_DIR / "data/stage0_discovery_plan.json"
plan_file.write_text(json.dumps(plan_obj, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Stage 1: 6-Track Web Search + OEM PDF Fetcher + 6 Parallel Specialist Agents
# ---------------------------------------------------------------------------
phase("Stage 1: 6-Role Parallel Deep Research & Verified OEM PDF Acquisition")
_run_cli(
    [
        "execute-tracks-and-pdfs",
        "--plan-file",
        str(plan_file),
        "--profile",
        profile,
        "--vault-db",
        vault_db,
        "--output-dir",
        output_dir,
        "--output-file",
        "data/stage1_tracks_and_pdfs.json",
    ]
)
stage1_data = json.loads((BASE_DIR / "data/stage1_tracks_and_pdfs.json").read_text(encoding="utf-8"))
all_valid_ev_ids = set(stage1_data["all_valid_ev_ids"])
verified_pdfs = {ds["filename"] for ds in stage1_data["datasheet_assets"]}
datasheets_list_str = "\n".join(
    f"- `{ds['ev_id']}` | {ds['vendor']} `{ds['part_number']}` -> `./datasheets_pdf/{ds['filename']}` ({ds['subsystem']})"
    for ds in stage1_data["datasheet_assets"]
)


async def _mine_specialist(tp: dict) -> dict:
    tid = tp["track_id"]
    t_ctx = stage1_data["track_contexts"].get(tid, "")
    prompt = (
        f"You are the `{tp['role_title']}` specialist for `{tid}`.\n"
        f"Mandate: {tp['focus_mandate']}\n\n"
        "STRICT GROUNDING: Cite ONLY exact `[EV-*]` IDs present below, and use ONLY verified datasheet filenames.\n\n"
        f"=== TRACK WEB EVIDENCE ===\n{t_ctx}\n\n"
        f"=== VERIFIED OEM PDF DATASHEETS ===\n{datasheets_list_str}\n\n"
        f"=== PDF EXCERPTS [EV-PDF-*] ===\n{stage1_data['context_pdf'][:4000]}\n\n"
        f"=== PRIOR BASELINE [EV-BASE-*] ===\n{stage1_data['context_base'][:3200]}"
        + NO_TOOL_DIRECTIVE
    )
    return await agent(
        prompt=prompt,
        schema=SPECIALIST_DOSSIER_SCHEMA,
        role=f"Specialist ({tid[:2]} {tp['role_title'][:12]})",
        model=fast_model,
    )


track_dossiers = await parallel(plan_obj["track_plans"], _mine_specialist)


# ---------------------------------------------------------------------------
# Stage 2: Deterministic PALMs Physics, Dual-Track BOM, 5-Yr Finance & Plant ROI
# ---------------------------------------------------------------------------
phase("Stage 2: PALMs Deterministic Physics, Dual-Track BOM & 5-Year Finance Engine")
_run_cli(["run-calcs", "--output-file", "data/stage2_deterministic_calcs.json"])
calcs = json.loads((BASE_DIR / "data/stage2_deterministic_calcs.json").read_text(encoding="utf-8"))
md_tables = calcs["markdown_tables"]


# ---------------------------------------------------------------------------
# Stage 3 & 4: IPD Review Board + Buyer STORM + 5-Route Swiss Elo Tournament
# ---------------------------------------------------------------------------
phase("Stage 3-4: IPD Engineering Board, Power-Plant STORM & Architecture Elo")
dossiers_digest = "\n\n".join(
    f"### {d['track_id']} ({d['role_title']})\n{d['executive_findings']}\nKey decisions: {'; '.join(d['key_technical_decisions'][:4])}"
    for d in track_dossiers
)

ipd_prompt = (
    "Convene the 6-role IPD Engineering & Manufacturability Review Board (PM, Opto-Mechanical HW, Software/AI, Boiler Welding, QA/NPI, CFO).\n"
    "Review optical link margins, electrical/protocol interfaces, DFM assembly, 650°C calibration mandates, and dual-track cost levers.\n\n"
    f"=== [PHY-CALC] ===\n{md_tables['physics_link_md']}\n\n"
    f"=== [BOM-CALC] ===\n{md_tables['bom_matrix_md']}\n\n"
    f"=== SPECIALIST DIGEST ===\n{dossiers_digest}\n\n"
    f"=== DATASHEETS ===\n{datasheets_list_str}"
    + NO_TOOL_DIRECTIVE
)

storm_prompt = (
    "Convene the 4-persona Coal Power Plant Buyer STORM Committee:\n"
    "1) Plant Chief Engineer, 2) Boiler Tube-Inspection Head, 3) I&C/Cybersecurity Specialist, 4) Group Procurement CFO.\n"
    "Expose hardest field/cyber/budget objections and map winning responses.\n\n"
    f"=== [PLANT-ROI] ===\n{md_tables['plant_roi_md']}\n\n"
    f"=== [BOM-CALC] ===\n{md_tables['bom_matrix_md']}\n\n"
    f"=== CN MARKET EVIDENCE ===\n{stage1_data['context_cn'][:4500]}\n\n"
    f"=== SPECIALIST DIGEST ===\n{dossiers_digest[:3000]}"
    + NO_TOOL_DIRECTIVE
)

arch_ids = [a["arch_id"] for a in calcs["arch_comparisons"]]
elo_pairs = [
    (1, arch_ids[0], arch_ids[1]),
    (1, arch_ids[2], arch_ids[3]),
    (2, arch_ids[0], arch_ids[2]),
    (2, arch_ids[0], arch_ids[3]),
    (3, arch_ids[0], arch_ids[4]),
]


async def _run_elo_pair(pair: tuple) -> dict:
    r_num, a_id, b_id = pair
    p = (
        f"Swiss Round {r_num}: Compare `{a_id}` vs `{b_id}` for China coal-fired boiler FBG productization.\n"
        f"=== ARCH COMPARISON ===\n{md_tables['arch_comparison_md']}\n\n"
        f"=== [PHY-CALC] ===\n{md_tables['physics_link_md']}\n\n"
        "Set `winner` to exact `arch_a` or `arch_b` string."
        + NO_TOOL_DIRECTIVE
    )
    return await agent(
        prompt=p,
        schema=ELO_MATCH_SCHEMA,
        role=f"Elo Judge R{r_num}",
        model=fast_model,
    )


ipd_task = agent(prompt=ipd_prompt, schema=IPD_MEMO_SCHEMA, role="IPD Review Board", model=target_model)
storm_task = agent(prompt=storm_prompt, schema=STORM_PANEL_SCHEMA, role="Power-Plant STORM Panel", model=target_model)

ipd_memo, storm_panel, elo_matches = await parallel(
    [0, 1, 2],
    lambda idx: ipd_task if idx == 0 else (storm_task if idx == 1 else parallel(elo_pairs, _run_elo_pair)),
)

# Compute deterministic Elo summary string for Stage 5 writers
ratings = {aid: 1500.0 for aid in arch_ids}
for m in elo_matches:
    a, b, w = m["arch_a"], m["arch_b"], m["winner"]
    if a in ratings and b in ratings:
        k = 40.0 if m["margin"] == "decisive" else 24.0
        ea = 1.0 / (1.0 + 10.0 ** ((ratings[b] - ratings[a]) / 400.0))
        sa = 1.0 if w == a else 0.0
        ratings[a] += k * (sa - ea)
        ratings[b] += k * ((1.0 - sa) - (1.0 - ea))
elo_summary_str = ", ".join(f"{k}={round(v,1)}" for k, v in sorted(ratings.items(), key=lambda x: -x[1]))


# ---------------------------------------------------------------------------
# Stage 5: Parallel Multi-Agent Authoring of 00_ through 06_
# ---------------------------------------------------------------------------
phase("Stage 5: Parallel Multi-Agent Authoring of Volumes 00_ to 06_")

VOLUME_SPECS = [
    (
        "00_EXECUTIVE_PRODUCT_CHARTER_AND_ROADMAP.md",
        "产品立项总纲、双档产品定义与全生命周期研发量产路线图",
        "首席产品经理 (Chief PM)",
        "涵盖项目使命、BS-STD-600(300-600点)与BS-PRO-2000(1000-2000+点)双档定义、Elo技术路线裁决(Modular Dual-Tier胜出依据)、外购国际成品集成+自研软件AI战略、35-55天样机到首年1-3台挂网示范再到10-80套批量量产里程碑、风险矩阵与整套文档索引。",
    ),
    (
        "01_CHINA_COAL_BOILER_MARKET_AND_COMPETITIVE_LANDSCAPE.md",
        "中国燃煤电力锅炉水冷壁 FBG 测温市场趋势与国内外竞品拆解",
        "市场与竞品首席分析师",
        "分析中国煤电三改联动/15%-30%深度调峰水冷壁爆管痛点、全天候监测需求；横向对比热电偶/声学/红外/传统UV-FBG/飞秒及弱光栅阵列；对标国内外竞品（理工光科、太辰光、东方锐择、光子传感、Luna、FBGS、Omnisens）的路线、价格带、短板与我方破局武器；结合STORM买方4角色痛点给出招投标应对策略。",
    ),
    (
        "02_SYSTEM_ARCHITECTURE_SUPPLIER_SELECTION_AND_BOM.md",
        "双档系统总体架构、国际硬件选型与双轨分级 BOM（含原厂 PDF 映射）",
        "光电系统总师",
        "完整融入 [PHY-CALC] 链路预算与 [BOM-CALC] 双轨阶梯成本表；详细对比 BS-STD-600 与 BS-PRO-2000 硬件选型依据、原厂 Part Number、一备一防呆备选件、精准链接 `./datasheets_pdf/<filename>`、Track A（全进口德国FBGS+OFS）vs Track B（核心进口+严选本土传感降本）完整可下单 BOM 采购表（含交期、起订量、参考单价与单点均摊成本）。",
    ),
    (
        "03_COMPONENT_INTERFACES_AND_DETAILED_INTEGRATION_DESIGN.md",
        "全系统硬件接口定义、光电/电气/机械/协议集成详设与装调接口规程",
        "硬软件接口主任工程师",
        "极高工程颗粒度：① 光学拓扑与光纤连接定义（FC/APC 8°斜面、环形器Port1/2/3流向、Sercalo SW1x16/32/48 引脚、HCN-13 气室与50GHz标准具90/10分光接法）；② 电气与配电详设（MeanWell 24V隔离电源树、FEMTO HCA-S-200M-IN ±15V供电与SMA 50Ω至Spectrum M2p.5922 PCIe CH0/CH1/Trig端接、Santec/Lumentum TTL Trigger同步时序）；③ 工控机与Ibsen I-MON 512 USB帧协议、Sercalo RS-232命令帧格式、Moxa MGate/OPC UA 单向物理隔离网闸至电厂DCS点表与4-20mA硬接线干接点定义；④ 2U/4U机箱物理布局、风道散热、光纤盘纤R>=30mm规范与EMC接地。",
    ),
    (
        "04_SOFTWARE_DEMODULATION_AND_BOILER_AI_SPEC.md",
        "自研高速解调算法、数字孪生上位机与两阶段锅炉 AI 应用架构",
        "软件与锅炉 AI 首席架构师",
        "完整定义自主研发软件栈：① 硬件抽象层（Ibsen USB/SPI SDK 与 Spectrum DMA 零拷贝双缓冲采集）；② 核心信号解调管道（暗电流扣除→SG滤波→HCN/F-P三次样条波长线性化校准→重心粗寻峰+加权对数高斯/LM非线性亚像素拟合<0.5pm→三阶温度反演+15CrMoG导热块热流逆向补偿）；③ 光衰/断纤/超温分级自诊断；④ 水冷壁四面三维展开克里金温度场上位机 UI 与工业数据库设计；⑤ 两阶段锅炉AI方案（一期旁路只读：热阻洁净因子按需吹灰、Larson-Miller蠕变寿命与爆管提前预警、切圆火焰偏斜与高温腐蚀诊断；二期闭环寻优：等保三级合规与二次风门/吹灰闭环建议）。",
    ),
    (
        "05_SYSTEM_BRINGUP_FIELD_INSTALLATION_AND_QAQC_SOP.md",
        "系统上电调试、电厂水冷壁现场安装焊接指南与全流程 QA/QC 及 NPI SOP",
        "NPI 质量与现场交付总监",
        "可执行工厂与现场指导书：① 实验室/厂内系统 Bring-Up 光电逐点联调 SOP（光源功率校验→光开关切换验证→光谱基线与气室吸收峰核对→算法闭环测试）；② 量产 NPI 全流程 QA/QC（IQC 来料：光纤 200kpsi 复验、FBG 光谱 FWHM/SLSR/反射率筛选；IPQC 装配力矩与盘纤检验；650°C 三温区管式标定炉多温区自动标定曲线生成；72小时 -10~+60°C 高低温循环老化；FAT 出厂检验证书清单）；③ 电厂现场施工安装十大关键 SOP（膜式水冷壁打磨探伤→15CrMoG 导热块定位与 TIG 满焊防烧穿工艺→316L/Inconel600 毛细管松套穿纤严禁拉紧与胶粘光栅区→穿炉墙膨胀密封套管与防磨护瓦→盘纤熔接 OTDR ≤0.08dB 验收→冷态/热态升负荷标定与 DCS 点对点 SAT 验收）。",
    ),
    (
        "06_FINANCIAL_ANALYSIS_GTM_MARKETING_AND_TRAINING_PLAYBOOK.md",
        "财务投资分析、市场营销 GTM 策略、内部工程师与销售实战培训手册",
        "CFO 与商业化培训总监",
        "严格沿用 [FIN-CALC]、[BOM-CALC]、[PLANT-ROI] 确定性数据：① 80万元精益启动 CAPEX 细目与 5 年 Bear/Base/Bull 营收、毛利、EBITDA、现金流、保本套数、NPV@10% 与 IRR 完整分年表；② 600MW 与 1000MW 电厂经济性测算书与回收期话术；③ GTM 商业打法（首年 1-3 台标杆挂网示范切入→次年 12 套→5 年 80 套/年，五大六小发电集团与三大锅炉厂协同、投标控标技术壁垒参数）；④ 内部工程师 4 周模块化实战培训大纲（光学基础/系统装调/算法标定/电厂焊接防爆督导及考核标准）；⑤ 销售赋能手册（电厂 4 类决策人异议应答话术与 Battlecards）。",
    ),
]

shared_context_block = (
    f"=== [PHY-CALC] ===\n{md_tables['physics_link_md']}\n\n"
    f"=== [ARCH & ELO] ===\n{md_tables['arch_comparison_md']}\nElo Standings: {elo_summary_str}\n\n"
    f"=== [BOM-CALC] ===\n{md_tables['bom_matrix_md']}\n\n"
    f"=== [FIN-CALC] ===\n{md_tables['financial_scenarios_md']}\n\n"
    f"=== [PLANT-ROI] ===\n{md_tables['plant_roi_md']}\n\n"
    f"=== VERIFIED DATASHEETS (./datasheets_pdf/) ===\n{datasheets_list_str}\n\n"
    f"=== IPD REVIEW MEMO ===\n{json.dumps(ipd_memo, ensure_ascii=False)[:2500]}\n\n"
    f"=== POWER-PLANT BUYER STORM ===\n{json.dumps(storm_panel, ensure_ascii=False)[:2500]}\n\n"
    f"=== SPECIALIST RESEARCH DIGEST ===\n{dossiers_digest[:6500]}"
)


async def _author_volume(spec: tuple) -> dict:
    fname, title_cn, role_cn, mandate = spec
    prompt = (
        f"You are the `{role_cn}` of the BoilerSense-AI™ Product Team.\n"
        f"Write `{fname}` ({title_cn}) in deep, concrete, engineering-grade Simplified Chinese.\n"
        f"Mandate: {mandate}\n\n"
        "NON-NEGOTIABLE GROUNDING RULES:\n"
        "1. Every factual/vendor claim MUST cite ONLY valid `[EV-BASE-*]`, `[EV-CN-*]`, `[EV-GL-*]`, or `[EV-PDF-*]` IDs present in the injected evidence.\n"
        "2. Copy ALL Python `[PHY-CALC]`, `[BOM-CALC]`, `[FIN-CALC]`, and `[PLANT-ROI]` numbers EXACTLY without inventing or altering math.\n"
        "3. Every datasheet link MUST match exact filename under `./datasheets_pdf/<filename>` listed above.\n"
        "4. Include crisp Markdown tables, Mermaid diagrams where helpful, pin/port/protocol specs, and actionable checklists.\n\n"
        f"{shared_context_block}\n\n"
        f"=== CHINA EVIDENCE [EV-CN-*] ===\n{stage1_data['context_cn'][:4200]}\n\n"
        f"=== GLOBAL EVIDENCE [EV-GL-*] ===\n{stage1_data['context_global'][:3600]}\n\n"
        f"=== PDF DATASHEET EXCERPTS [EV-PDF-*] ===\n{stage1_data['context_pdf'][:3800]}\n\n"
        f"=== BASELINE CORPUS [EV-BASE-*] ===\n{stage1_data['context_base'][:2500]}"
        + NO_TOOL_DIRECTIVE
    )
    res = await agent(
        prompt=prompt,
        schema=VOLUME_REPORT_SCHEMA,
        role=f"Writer ({fname[:2]} {role_cn[:8]})",
        model=target_model,
    )
    return {"filename": fname, "markdown": res["markdown"].strip() + "\n"}


vol_list = await parallel(VOLUME_SPECS, _author_volume)
volumes_map = {item["filename"]: item["markdown"] for item in vol_list}


# ---------------------------------------------------------------------------
# Stage 6: Bounded Critic Reflection + Programmatic Audit + CRAG Refill
# ---------------------------------------------------------------------------
phase("Stage 6: Adversarial Critic Audit & CRAG Gap-Refill")
critique_history: list[dict] = []
critique_loops_executed = 0

for loop_idx in range(1, max_loops + 1):
    critique_loops_executed = loop_idx
    invalid_cites: dict[str, list[str]] = {}
    broken_pdfs: dict[str, list[str]] = {}
    for v_name, v_text in volumes_map.items():
        cited = set(re.findall(r"\[(EV-(?:BASE|CN|GL|PDF)-\d{4})\]", v_text))
        bad = sorted(c for c in cited if c not in all_valid_ev_ids)
        if bad:
            invalid_cites[v_name] = bad
        pdf_refs = set(re.findall(r"datasheets_pdf/([A-Za-z0-9._-]+\.pdf)", v_text))
        bad_p = sorted(p for p in pdf_refs if p not in verified_pdfs)
        if bad_p:
            broken_pdfs[v_name] = bad_p

    excerpts = "\n\n".join(f"=== {k} (chars={len(v)}) ===\n{v[:2200]}" for k, v in sorted(volumes_map.items()))
    critic_prompt = (
        f"Critique Loop {loop_idx}/{max_loops} for BoilerSense-AI™ Product R&D & NPI Dossier:\n"
        f"Programmatic Invalid Citation Check: {json.dumps(invalid_cites, ensure_ascii=False)}\n"
        f"Programmatic Broken PDF Check: {json.dumps(broken_pdfs, ensure_ascii=False)}\n\n"
        f"=== AUTHORITATIVE TABLES ===\n{md_tables['physics_link_md']}\n\n{md_tables['bom_matrix_md']}\n\n{md_tables['financial_scenarios_md']}\n\n"
        f"=== VERIFIED PDF FILES ===\n{sorted(verified_pdfs)}\n\n"
        f"=== VOLUME EXCERPTS ===\n{excerpts}\n\n"
        "Check cross-volume numeric consistency, interface pin/voltage/protocol precision, field welding/QA-QC tolerances, "
        "no fabricated EV IDs or broken PDF links. If clean, return passed=true and volumes_to_rewrite=[]."
        + NO_TOOL_DIRECTIVE
    )
    audit = await agent(
        prompt=critic_prompt,
        schema=CRITIC_AUDIT_SCHEMA,
        role=f"Adversarial Critic L{loop_idx}",
        model=target_model,
    )

    vols_to_fix = list(dict.fromkeys(audit.get("volumes_to_rewrite", [])))
    for bad_v in set(invalid_cites.keys()) | set(broken_pdfs.keys()):
        if bad_v not in vols_to_fix:
            vols_to_fix.append(bad_v)
    if invalid_cites or broken_pdfs:
        audit["passed"] = False

    crag_queries = [
        {"geo_scope": iss["suggested_geo_scope"], "query": iss["suggested_query"]}
        for iss in audit.get("issues", [])
        if iss.get("needs_crag_gap_search") and str(iss.get("suggested_query", "")).strip()
    ][:4]

    critique_history.append(
        {
            "loop": loop_idx,
            "passed": audit["passed"],
            "volumes_to_rewrite": vols_to_fix,
            "crag_queries": crag_queries,
            "assessment": audit["overall_assessment"],
        }
    )

    if audit["passed"] or loop_idx == max_loops or (not vols_to_fix and not crag_queries):
        break

    crag_ctx = ""
    if crag_queries:
        gap_q_file = BASE_DIR / f"data/stage6_gap_queries_l{loop_idx}.json"
        gap_out_file = BASE_DIR / f"data/stage6_gap_evidence_l{loop_idx}.json"
        gap_q_file.write_text(json.dumps(crag_queries, ensure_ascii=False, indent=2), encoding="utf-8")
        _run_cli(
            [
                "gap-search",
                "--queries-json",
                str(gap_q_file),
                "--vault-db",
                vault_db,
                "--output-file",
                str(gap_out_file),
            ]
        )
        gap_data = json.loads(gap_out_file.read_text(encoding="utf-8"))
        crag_ctx = gap_data.get("formatted_context", "")
        if gap_data.get("all_valid_ev_ids"):
            all_valid_ev_ids.update(gap_data["all_valid_ev_ids"])

    async def _rewrite_target(v_name: str) -> dict:
        r_prompt = (
            f"Rewrite `{v_name}` completely in Simplified Chinese to fix all Critic findings:\n"
            f"Assessment: {audit['overall_assessment']}\n"
            f"Invalid EV IDs to remove: {invalid_cites.get(v_name, [])}\n"
            f"Broken PDF links to fix (must be in verified list): {broken_pdfs.get(v_name, [])}\n\n"
            f"=== AUTHORITATIVE DATA ===\n{shared_context_block[:6500]}\n\n"
            f"=== CRAG NEW EVIDENCE ===\n{crag_ctx}\n\n"
            f"=== VALID EVIDENCE SAMPLES ===\n{stage1_data['context_cn'][:2400]}\n\n{stage1_data['context_pdf'][:2400]}\n\n"
            f"=== PREVIOUS DRAFT ===\n{volumes_map[v_name][:6000]}"
            + NO_TOOL_DIRECTIVE
        )
        res = await agent(
            prompt=r_prompt,
            schema=VOLUME_REPORT_SCHEMA,
            role=f"CRAG Rewriter ({v_name[:2]})",
            model=target_model,
        )
        return {"filename": v_name, "markdown": res["markdown"].strip() + "\n"}

    valid_targets = [v for v in vols_to_fix if v in volumes_map]
    if valid_targets:
        rewritten = await parallel(valid_targets, _rewrite_target)
        for item in rewritten:
            volumes_map[item["filename"]] = item["markdown"]


# ---------------------------------------------------------------------------
# Stage 7: 100-Point Stage-Gate Judge & Final Export (Vol 07, Vol 08, Diagrams)
# ---------------------------------------------------------------------------
phase("Stage 7: 100-Point Stage-Gate Judge & Deliverables Export")
judge_prompt = (
    "Score this BoilerSense-AI™ Complete Product R&D & NPI Package strictly on the 5x20=100 Stage-Gate Rubric:\n"
    "1. `market_and_competitive_rigor` (20)\n"
    "2. `hardware_selection_and_interface_completeness` (20)\n"
    "3. `software_demod_and_boiler_ai_actionability` (20)\n"
    "4. `npi_qaqc_bringup_and_field_sop` (20)\n"
    "5. `financial_gtm_training_and_traceability` (20)\n\n"
    f"Vault Stats: {json.dumps(stage1_data['vault_stats'], ensure_ascii=False)}\n"
    f"Verified OEM PDFs count: {len(verified_pdfs)}\n\n"
    f"Vol 00:\n{volumes_map['00_EXECUTIVE_PRODUCT_CHARTER_AND_ROADMAP.md'][:1800]}\n\n"
    f"Vol 02:\n{volumes_map['02_SYSTEM_ARCHITECTURE_SUPPLIER_SELECTION_AND_BOM.md'][:1800]}\n\n"
    f"Vol 03:\n{volumes_map['03_COMPONENT_INTERFACES_AND_DETAILED_INTEGRATION_DESIGN.md'][:1800]}\n\n"
    f"Vol 05:\n{volumes_map['05_SYSTEM_BRINGUP_FIELD_INSTALLATION_AND_QAQC_SOP.md'][:1800]}\n\n"
    f"Vol 06:\n{volumes_map['06_FINANCIAL_ANALYSIS_GTM_MARKETING_AND_TRAINING_PLAYBOOK.md'][:1800]}"
    + NO_TOOL_DIRECTIVE
)
rubric = await agent(
    prompt=judge_prompt,
    schema=JUDGE_RUBRIC_SCHEMA,
    role="Stage-Gate Judge",
    model=target_model,
)

bundle_file = BASE_DIR / "data/final_native_bundle.json"
final_bundle = {
    "run_id": run_id,
    "profile": profile,
    "llm_engine": f"antigravity_native:{target_model}+{fast_model}",
    "elo_matches": elo_matches,
    "volumes": volumes_map,
    "judge_rubric": rubric,
    "critique_loops_executed": critique_loops_executed,
    "critique_history": critique_history,
    "native_agent_invocations": {
        "chief_pm_planner": 1,
        "specialist_miners": len(plan_obj["track_plans"]),
        "ipd_review_board": 1,
        "power_plant_storm_panel": 1,
        "elo_judges": len(elo_matches),
        "volume_authors": len(VOLUME_SPECS),
        "critic_loops": critique_loops_executed,
        "stage_gate_judge": 1,
    },
}
bundle_file.write_text(json.dumps(final_bundle, ensure_ascii=False, indent=2), encoding="utf-8")

_run_cli(
    [
        "finalize",
        "--bundle-file",
        str(bundle_file),
        "--vault-db",
        vault_db,
        "--output-dir",
        output_dir,
    ]
)

print(
    json.dumps(
        {
            "run_id": run_id,
            "stage_gate_score": rubric.get("total_score"),
            "pass_status": rubric.get("pass_status"),
            "verified_pdfs": len(verified_pdfs),
            "output_dir": str((BASE_DIR / output_dir).resolve()),
        },
        ensure_ascii=False,
    )
)
