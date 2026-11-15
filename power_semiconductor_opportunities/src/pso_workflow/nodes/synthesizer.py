"""Node 5: Grounded Multi-Volume Report Synthesizer (Ch 1, Ch 3 Strict Merger, Ch 14)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from pso_workflow.nodes.deps import RuntimeDeps
from pso_workflow.prompts import SYNTHESIZER_SYSTEM
from pso_workflow.schemas import EvidenceRecord, WorkflowState


def _format_roi_table(evaluated_opps: list[dict[str, Any]], sector: str | None = None) -> str:
    rows = []
    for item in evaluated_opps:
        seed = item["seed"]
        if sector and seed["sector"] != sector:
            continue
        roi = item["roi"]
        rows.append(
            f"| #{item['composite_rank']} | `{seed['opp_id']}` | {seed['track_id']} | {seed['horizon']} | "
            f"{seed['title']} | ¥{roi['capex_cny']/10000:.1f}万 | ¥{roi['net_annual_cashflow_cny']/10000:.1f}万/年 | "
            f"**{roi['payback_months']}月** | {roi['irr_5yr_pct']}% | ¥{roi['npv_5yr_cny']/10000:.1f}万 | "
            f"{roi['payback_tier']} | {item['weighted_pillar_score']} / Elo {item['elo_rating']} | "
            f"{', '.join(f'[{e}]' for e in seed.get('evidence_ids', [])[:4])} |"
        )
    header = (
        "| 综合排名 | ID | 赛道 | 周期 | 机会名称 | 单套CAPEX | 年净现金流 | "
        "回收期[ROI-CALC] | 5年IRR[ROI-CALC] | 5年NPV[ROI-CALC] | ROI分级 | 综合分/Elo | 证据溯源 |\n"
        "| :---: | :---: | :---: | :---: | :--- | ---: | ---: | ---: | ---: | ---: | :--- | :---: | :--- |"
    )
    return header + "\n" + "\n".join(rows)


def _format_dossiers(dossiers: list[dict[str, Any]], sector: str | None = None) -> str:
    blocks: list[str] = []
    for d in dossiers:
        if sector and d.get("sector") != sector:
            continue
        pps = "\n".join(
            f"  - [{p['geo_scope']}] {p['process_stage']}: {p['pain_description']} "
            f"(现有局限: {p['current_limitation']}) 证据: {p.get('evidence_ids', [])}"
            for p in d.get("pain_points", [])
        )
        opps = "\n".join(
            f"  - `{o['opp_id']}` ({o['horizon']}): {o['title']} | 机理: {o['physics_principle']} | "
            f"中国切入: {o['china_positioning']} | 全球拓展: {o['global_expansion_path']} | "
            f"四大支柱: 良率[{o['quality_yield_mechanism']}], 降本[{o['cost_tco_mechanism']}], "
            f"环保[{o['green_ehs_mechanism']}], 升级[{o['industrial_upgrade_mechanism']}] | 证据: {o.get('evidence_ids', [])}"
            for o in d.get("opportunities", [])
        )
        blocks.append(
            f"### 赛道 {d['track_id']}: {d['track_name']}\n"
            f"- 中国市场动态: {d['china_market_dynamics']}\n"
            f"- 全球市场动态: {d['global_market_dynamics']}\n"
            f"- 3-5年展望: {d['horizon_3_5y_outlook']}\n"
            f"- 5-10年展望: {d['horizon_5_10y_outlook']}\n"
            f"- 产线痛点:\n{pps}\n"
            f"- 候选技术/产品/应用机会:\n{opps}"
        )
    return "\n\n".join(blocks)


def _format_storm_digest(evaluated_opps: list[dict[str, Any]], sector: str | None = None) -> str:
    lines: list[str] = []
    for item in evaluated_opps:
        seed = item["seed"]
        if sector and seed["sector"] != sector:
            continue
        memo = item.get("storm_memo") or {}
        assessments = memo.get("buyer_assessments", [])
        persona_str = " ; ".join(
            f"{a['persona_role']}->{a['adoption_barrier']} (Spec-in触发: {a['spec_in_trigger']})"
            for a in assessments
        )
        lines.append(
            f"- `{seed['opp_id']}` 最尖锐痛点: {memo.get('sharpest_pain_point_summary', '')} | "
            f"本土/出海护城河: {memo.get('key_localization_or_export_moat', '')} | "
            f"四方拷问摘要: {persona_str}"
        )
    return "\n".join(lines)


def _format_vault_snippets(records: list[EvidenceRecord], tracks: set[str] | None = None, limit: int = 36) -> str:
    filtered = [r for r in records if tracks is None or r.track_id in tracks]
    cn = [r for r in filtered if r.geo_scope == "CN"][: limit // 2 + 4]
    gl = [r for r in filtered if r.geo_scope == "GLOBAL"][: limit // 2 + 4]
    out = []
    for r in cn + gl:
        txt = (r.full_markdown[:550] if r.full_markdown else r.snippet[:320]).replace("\n", " ")
        out.append(f"- [{r.ev_id}] ({r.track_id}/{r.geo_scope}/{r.authority_tier}) {r.title} -> {txt}")
    return "\n".join(out)


def render_evidence_index(records: list[EvidenceRecord]) -> str:
    """Deterministically compile Volume 05 from SQLite EvidenceVault (zero hallucination)."""
    cn_recs = [r for r in records if r.geo_scope == "CN"]
    gl_recs = [r for r in records if r.geo_scope == "GLOBAL"]
    lines = [
        "# 05. 核验证据库与权威引用总索引 (Verified EvidenceVault Citations Index)",
        "",
        f"> 本索引由 SQLite 持久化证据记忆库 (`data/evidence_vault.db`) 自动确定性导出，共收录 **{len(records)}** 条去重溯源证据："
        f"中国市场证据 **{len(cn_recs)}** 条（优先通过秘塔 Metaso / 中文权威渠道检索），全球市场证据 **{len(gl_recs)}** 条（通过 Serper Google / Scholar / Patents 检索）。",
        "",
        "## 一、 中国市场证据清单（CN — 秘塔 Metaso / 国内权威信源）",
        "",
        "| 证据编号 | 赛道 | 权威分级 | 引擎 | 日期 | 标题与核验链接 | 核心摘要 |",
        "| :---: | :---: | :---: | :---: | :---: | :--- | :--- |",
    ]
    for r in cn_recs:
        safe_title = r.title.replace("|", "\\|")
        safe_snip = (r.snippet or r.full_markdown[:180]).replace("\n", " ").replace("|", "\\|")[:180]
        lines.append(
            f"| `{r.ev_id}` | {r.track_id} | {r.authority_tier} | {r.engine} | {r.published_date or '-'} | "
            f"[{safe_title}]({r.url}) | {safe_snip} |"
        )
    lines.extend(
        [
            "",
            "## 二、 全球市场证据清单（GLOBAL — Serper Google / Scholar / Patents）",
            "",
            "| 证据编号 | 赛道 | 权威分级 | 引擎 | 日期 | 标题与核验链接 | 核心摘要 |",
            "| :---: | :---: | :---: | :---: | :---: | :--- | :--- |",
        ]
    )
    for r in gl_recs:
        safe_title = r.title.replace("|", "\\|")
        safe_snip = (r.snippet or r.full_markdown[:180]).replace("\n", " ").replace("|", "\\|")[:180]
        lines.append(
            f"| `{r.ev_id}` | {r.track_id} | {r.authority_tier} | {r.engine} | {r.published_date or '-'} | "
            f"[{safe_title}]({r.url}) | {safe_snip} |"
        )
    return "\n".join(lines) + "\n"


async def node_grounded_report_synthesizer(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Synthesize Volumes 00-04 cleanly in dedicated grounded calls + compile Volume 05."""
    profile = state.get("profile", "flagship")
    dossiers = state.get("track_dossiers", [])
    evaluated = state.get("evaluated_opportunities", [])
    elo_matches = state.get("elo_matches", [])
    plan = state.get("research_plan", {})
    critique = state.get("latest_critique") or {}
    loop_count = int(state.get("loop_count", 0))

    all_records = deps.vault.list_all()
    max_tok = 7500 if profile == "flagship" else 4200
    tier = "producer" if profile == "flagship" else "fast"

    critique_note = ""
    if loop_count > 0 and critique:
        issues_txt = "\n".join(
            f"- [{i.get('severity')}] ({i.get('section')}): {i.get('description')}"
            for i in critique.get("issues", [])
        )
        critique_note = (
            f"\n\n=== CRITIC FEEDBACK TO FIX IN THIS REVISION (Loop {loop_count}) ===\n"
            f"Summary: {critique.get('summary', '')}\n{issues_txt}\n"
        )

    roi_all_table = _format_roi_table(evaluated)
    roi_power_table = _format_roi_table(evaluated, sector="power_energy")
    roi_semi_table = _format_roi_table(evaluated, sector="semiconductor")

    power_dossiers = _format_dossiers(dossiers, sector="power_energy")
    semi_dossiers = _format_dossiers(dossiers, sector="semiconductor")

    storm_all = _format_storm_digest(evaluated)
    storm_power = _format_storm_digest(evaluated, sector="power_energy")
    storm_semi = _format_storm_digest(evaluated, sector="semiconductor")

    vault_power = _format_vault_snippets(all_records, tracks={"P1", "P2", "P3", "P4"}, limit=32)
    vault_semi = _format_vault_snippets(all_records, tracks={"S1", "S2", "S3", "S4"}, limit=32)
    vault_all = _format_vault_snippets(all_records, tracks=None, limit=40)

    elo_summary = "\n".join(
        f"- Round {m['round_idx']}: `{m['opp_a_id']}` vs `{m['opp_b_id']}` -> Winner `{m['winner_id']}` | {m['rationale']}"
        for m in elo_matches[:20]
    )

    volumes_spec = [
        (
            "00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md",
            "Volume 00: 总览、顶层战略判断与 Top 16 机会全景榜单",
            f"""Write **Volume 00: 电力能源与半导体芯片制造在线测试仪器仪表 3-5年及5-10年战略机会总报告**.
Step-Back Thesis: {plan.get('step_back_thesis', '')}
Deterministic [ROI-CALC] Master Ranking Table:
{roi_all_table}
STORM Buying-Committee Highlights:
{storm_all}
Selected Grounded Evidence:
{vault_all}
{critique_note}

Mandatory Structure:
1. 执行摘要与核心判断（中国优先→全球跟进的双轨结构性拐点）
2. 电力能源 × 半导体交叉协同主线（重点剖析 SiC/GaN 宽禁带器件、电网高频高压装备、新能源与算力芯片的共性在线测试底层能力复用）
3. 3-5年（2027-2031 产线痛点高ROI放量） vs 5-10年（2031-2036 代际工艺跃迁新物种）双时间窗全景对比表
4. Top 机会综合排位总表（完整复现上面 Python 计算的 `[ROI-CALC]` 数据，禁止篡改任何数字）
5. 对工业仪器研发企业与系统集成商的三大决策建议（先切哪个产线、如何用 ROI 算账打动 CFO/总工、如何借国产替代出海）。""",
        ),
        (
            "01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md",
            "Volume 01: 电力能源行业（P1-P4）在线测试仪器深度机会分析",
            f"""Write **Volume 01: 电力能源行业（储能/固态电池、新型光伏/绿氢、特高压/环保气体/海缆、灵活调峰与CCUS）3-5年及5-10年在线测试仪器仪表深度研报**.
Power Deterministic [ROI-CALC] Table:
{roi_power_table}
Power Track Dossiers:
{power_dossiers}
STORM Buyer Interrogation:
{storm_power}
Power Evidence Snippets:
{vault_power}
{critique_note}

Mandatory Structure (for EACH of P1, P2, P3, P4):
- 第一节：中国市场产业痛点、十五五/双碳/国网南网驱动与本土在线检测刚需（引用 `[EV-CN-...]`）
- 第二节：全球市场（欧美F-gas法规、绿氢补贴、海外储能与CCUS）对标与出海窗口（引用 `[EV-GL-...]`）
- 第三节：3-5年高ROI机会 vs 5-10年下一代技术新机会（含测量物理机理、产品形态、安装取样/光学接口、产线良率/降本/环保/ROI[ROI-CALC]量化支撑）
- 第四节：产线买方四角色阻力与 Spec-in 破局点。""",
        ),
        (
            "02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md",
            "Volume 02: 半导体芯片制造行业（S1-S4）在线测试仪器深度机会分析",
            f"""Write **Volume 02: 半导体芯片制造行业（Fab AMC与湿化/特气、前道纳米光学/X射线量测、SiC/GaN宽禁带功率半导体、2.5D/3D Chiplet/HBM混合键合）3-5年及5-10年在线量检测与测试深度研报**.
Semiconductor Deterministic [ROI-CALC] Table:
{roi_semi_table}
Semiconductor Track Dossiers:
{semi_dossiers}
STORM Buyer Interrogation:
{storm_semi}
Semiconductor Evidence Snippets:
{vault_semi}
{critique_note}

Mandatory Structure (for EACH of S1, S2, S3, S4):
- 第一节：中国晶圆厂/功率产线/封测厂痛点、良率爬坡瓶颈与国产化率缺口（引用 `[EV-CN-...]`）
- 第二节：全球先进节点（GAA/CFET、HBM4、Cu-Cu混合键合、8英寸SiC）技术代际演进与国际标杆（引用 `[EV-GL-...]`）
- 第三节：3-5年确定性国产替代与良率放量机会 vs 5-10年原子级/非接触无损原位新物种（含物理测量限界突破、EFEM/原位腔体集成、良率/成本/EHS/ROI[ROI-CALC]定量指标）
- 第四节：晶圆厂工艺与CFO门禁壁垒破解方案。""",
        ),
        (
            "03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md",
            "Volume 03: PALMs 制造端 ROI 财务建模、TCO 算账与 Elo 锦标赛排位",
            f"""Write **Volume 03: 制造环节投资回报率 (ROI) 量化模型、TCO 算账与 AI Co-Scientist Elo 锦标赛排位报告**.
Master Deterministic [ROI-CALC] Table:
{roi_all_table}
Pairwise Elo Tournament Match Log:
{elo_summary}
STORM CFO & Procurement Gatekeeper Findings:
{storm_all}
{critique_note}

Mandatory Structure:
1. 生产制造端 ROI 建模方法论（为什么产线买单靠的是 `良率增益 + 避免整批报废/非计划停线 + 耗材/环保减负 - OPEX`，附计算公式与 10% WACC 基准）
2. 完整 16+ 项机会的 `[ROI-CALC]` 财务指标汇总与敏感性分析（区分 Tier-A <=12个月、Tier-B 12-24个月、Tier-C 24-42个月）
3. AI Co-Scientist 两两对抗 Elo 锦标赛排序解析（为什么某些高价值“产业升级项”在 Elo 评分中排位靠前或靠后）
4. 给客户 CFO 与总工的“一页纸算账模板”（分别以动力电池/火电厂、晶圆厂/SiC封测线为例）。""",
        ),
        (
            "04_PRODUCT_TECH_AND_UPGRADE_STRATEGY_PLAYBOOK.md",
            "Volume 04: 仪器技术路线图、产品工程化与产业升级 BD 路线图",
            f"""Write **Volume 04: 在线测试仪器技术研发、产品形态演进与助力产业升级执行手册 (Playbook)**.
Master Ranking & Physics Context:
{roi_all_table}
Dossiers Summary:
{power_dossiers[:3500]}
{semi_dossiers[:3500]}
STORM Engineering Tweaks:
{storm_all}
{critique_note}

Mandatory Structure:
1. 共性核心技术平台复用矩阵（如何用同一套“软电离质谱(IMR-MS)/激光光谱(TDLAS/CRDS)/太赫兹与超声无损成像/高压动态电学测试”底层平台横跨电力能源与半导体双赛道，降本增效）
2. 从“离线实验室仪器”升级为“产线在线/机台原位仪器”的五大工程化坎（采样预处理防堵塞/防腐蚀、SECS/GEM 与 PLC 工业总线闭环、防爆/洁净室兼容、自动标定免漂移、AI实时缺陷重构）
3. 分阶段市场进入策略（先中国本土标杆示范线 Spec-in -> 再随大客户与认证标准出海欧美/东南亚/中东）
4. 未来 3-5 年与 5-10 年研发立项与并购/生态合作里程碑清单。""",
        ),
    ]

    async def _gen_volume(filename: str, role_label: str, prompt: str) -> tuple[str, str]:
        async with deps.semaphore:
            md = await deps.llm.complete_text(
                tier=tier,
                node=f"synth_{filename[:2]}",
                system_prompt=SYNTHESIZER_SYSTEM,
                user_prompt=prompt,
                temperature=0.25,
                max_tokens=max_tok,
            )
        return filename, md.strip() + "\n"

    # Skip re-synthesizing unaffected volumes if critic specified narrow sections on rewrite
    existing = dict(state.get("draft_reports") or {})
    target_specs = volumes_spec
    if loop_count > 0 and critique.get("decision") == "needs_rewrite" and existing:
        flagged = {i.get("section", "") for i in critique.get("issues", [])}
        narrowed = [
            spec
            for spec in volumes_spec
            if any(spec[0][:2] in sec or spec[0] in sec or "all" in sec.lower() for sec in flagged)
        ]
        if narrowed:
            target_specs = narrowed

    generated_pairs = await asyncio.gather(
        *[_gen_volume(fn, lbl, pr) for fn, lbl, pr in target_specs]
    )
    updated_drafts = dict(generated_pairs)
    updated_drafts["05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md"] = render_evidence_index(all_records)

    return {
        "draft_reports": updated_drafts,
        "evidence_stats": deps.vault.stats(),
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "grounded_report_synthesizer",
                "volumes_generated": [fn for fn, _ in generated_pairs],
                "total_evidences": len(all_records),
            }
        ],
    }
