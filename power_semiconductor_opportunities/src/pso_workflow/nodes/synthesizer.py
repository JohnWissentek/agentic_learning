"""Stage 5: Grounded Multi-Volume Report Synthesizer (V2.0 Dynamic Tracks & 3-Scenario Funnel)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from pso_workflow.nodes.deps import RuntimeDeps
from pso_workflow.prompts import SYNTHESIZER_SYSTEM
from pso_workflow.schemas import EvidenceRecord, WorkflowState


COMMERCIAL_STATUS_LABELS: dict[str, str] = {
    "global_and_cn_commercialized": "海内外均已商业在售（AI升维/降本替代）",
    "overseas_only_cn_blank": "海外成熟在售 / 国内整机空白（卡脖子首发替代）",
    "global_and_cn_true_blank": "海内外均无成熟在线整机（全球首发新物种空白）",
}


def format_commercial_whitespace_and_ai_table(
    evaluated_opps: list[dict[str, Any]], sector: str | None = None
) -> str:
    """Format V3 commercial vendor supply, product white-space tiers, and AI HW/SW co-design specs."""
    header = (
        "| 排名 | ID | 机会名称 | 商业空白分级 | 海外在售厂商与代表型号 | 国内厂商与交付状态 | 空白切入楔子 | AI 计算传感与软硬协同架构 | AI 研发周期对比 | 证据溯源 |\n"
        "| :---: | :---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    )
    rows: list[str] = []
    for item in evaluated_opps:
        seed = item["seed"]
        if sector and seed.get("sector") != sector:
            continue
        status_key = str(seed.get("commercial_status", "overseas_only_cn_blank"))
        status_label = COMMERCIAL_STATUS_LABELS.get(status_key, status_key)
        gl_v = str(seed.get("global_vendors_and_products", "-") or "-").replace("|", "\\|").replace("\n", " ")
        cn_v = str(seed.get("china_vendors_and_products", "-") or "-").replace("|", "\\|").replace("\n", " ")
        wedge = str(seed.get("white_space_and_entry_wedge", "-") or "-").replace("|", "\\|").replace("\n", " ")
        ai_cs = str(seed.get("ai_computational_sensing_and_co_design", "-") or "-").replace("|", "\\|").replace("\n", " ")
        rd_cmp = str(seed.get("estimated_rd_months_ai_vs_legacy", "-") or "-").replace("|", "\\|").replace("\n", " ")
        evs = ", ".join(f"[{e}]" for e in seed.get("evidence_ids", [])[:4])
        rows.append(
            f"| #{item.get('composite_rank', 0)} | `{seed['opp_id']}` | {seed['title']} | {status_label} | "
            f"{gl_v} | {cn_v} | {wedge} | {ai_cs} | {rd_cmp} | {evs} |"
        )
    return header + "\n" + "\n".join(rows)


def format_roi_table(evaluated_opps: list[dict[str, Any]], sector: str | None = None) -> str:
    """Format ranked opportunities into a deterministic `[ROI-CALC]` 3-scenario Markdown table."""
    rows = []
    for item in evaluated_opps:
        seed = item["seed"]
        if sector and seed["sector"] != sector:
            continue
        roi = item["roi"]
        rr = item.get("roi_range") or {}
        opt_pb = rr.get("optimistic", {}).get("payback_months", roi["payback_months"])
        cons_pb = rr.get("conservative", {}).get("payback_months", roi["payback_months"])
        status_key = str(seed.get("commercial_status", "overseas_only_cn_blank"))
        status_short = (
            "全球双空白" if status_key == "global_and_cn_true_blank"
            else ("国内空白替代" if status_key == "overseas_only_cn_blank" else "海内外均在售")
        )
        rows.append(
            f"| #{item['composite_rank']} | `{seed['opp_id']}` | {seed['track_id']} | {seed['horizon']} | {status_short} | "
            f"{seed['title']} | ¥{roi['capex_cny']/10000:.1f}万 | ¥{roi['net_annual_cashflow_cny']/10000:.1f}万/年 | "
            f"**{opt_pb} / {roi['payback_months']} / {cons_pb}月** | {roi['irr_5yr_pct']}% | ¥{roi['npv_5yr_cny']/10000:.1f}万 | "
            f"{roi['payback_tier']} | {item['weighted_pillar_score']} / Elo {item['elo_rating']} | "
            f"{', '.join(f'[{e}]' for e in seed.get('evidence_ids', [])[:4])} |"
        )
    header = (
        "| 综合排名 | ID | 赛道 | 周期 | 商业空白级 | 机会名称 | 基准CAPEX | 基准年净现金流 | "
        "乐观/基准/保守回收期[ROI-CALC] | 基准5年IRR[ROI-CALC] | 基准5年NPV[ROI-CALC] | ROI分级 | 综合分/Elo | 证据溯源 |\n"
        "| :---: | :---: | :---: | :---: | :---: | :--- | ---: | ---: | ---: | ---: | ---: | :--- | :---: | :--- |"
    )
    return header + "\n" + "\n".join(rows)


def format_dossiers(dossiers: list[dict[str, Any]], sector: str | None = None) -> str:
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
            f"  - `{o['opp_id']}` ({o['horizon']}, status={o.get('commercial_status', 'overseas_only_cn_blank')}): "
            f"{o['title']} | 机理: {o['physics_principle']} | "
            f"海外在售: {o.get('global_vendors_and_products', '-')} | 国内现状: {o.get('china_vendors_and_products', '-')} | "
            f"空白切入: {o.get('white_space_and_entry_wedge', '-')} | "
            f"AI计算传感: {o.get('ai_computational_sensing_and_co_design', '-')} | "
            f"AI研发与边缘: {o.get('ai_rd_acceleration_and_edge_deployment', '-')} ({o.get('estimated_rd_months_ai_vs_legacy', '')}) | "
            f"BOM与GTM形态: {o.get('hardware_bom_localization_and_gtm_form', '-')} | "
            f"四大支柱: 良率[{o['quality_yield_mechanism']}], 降本[{o['cost_tco_mechanism']}], "
            f"环保[{o['green_ehs_mechanism']}], 升级[{o['industrial_upgrade_mechanism']}] | "
            f"参数依据: {(o.get('roi_range_inputs') or {}).get('parameter_basis', 'n/a')} | 证据: {o.get('evidence_ids', [])}"
            for o in d.get("opportunities", [])
        )
        blocks.append(
            f"### 赛道 {d['track_id']}: {d['track_name']}\n"
            f"- 商业供给与空白全景: {d.get('commercial_landscape_summary', '')}\n"
            f"- 中国市场动态: {d['china_market_dynamics']}\n"
            f"- 全球市场动态: {d['global_market_dynamics']}\n"
            f"- 3-5年展望: {d['horizon_3_5y_outlook']}\n"
            f"- 5-10年展望: {d['horizon_5_10y_outlook']}\n"
            f"- 产线痛点:\n{pps}\n"
            f"- 候选技术/产品/应用机会:\n{opps}"
        )
    return "\n\n".join(blocks)


def format_storm_digest(evaluated_opps: list[dict[str, Any]], sector: str | None = None) -> str:
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


def format_vault_snippets(
    records: list[EvidenceRecord], tracks: set[str] | None = None, limit: int = 36
) -> str:
    filtered = [r for r in records if tracks is None or r.track_id in tracks]
    cn = [r for r in filtered if r.geo_scope == "CN"][: limit // 2 + 4]
    gl = [r for r in filtered if r.geo_scope == "GLOBAL"][: limit // 2 + 4]
    out = []
    for r in cn + gl:
        txt = (r.full_markdown[:550] if r.full_markdown else r.snippet[:320]).replace("\n", " ")
        out.append(f"- [{r.ev_id}] ({r.track_id}/{r.geo_scope}/{r.authority_tier}) {r.title} -> {txt}")
    return "\n".join(out)


def format_discovery_and_funnel_summary(
    *,
    plan: dict[str, Any],
    raw_count: int,
    shortlist_count: int,
    eliminated: list[dict[str, Any]],
) -> str:
    """Format Stage 0 dynamically emerged tracks and Stage 2 PALMs funnel elimination log."""
    tracks = plan.get("track_plans", [])
    track_lines = []
    for tp in tracks:
        tag = "新兴/跨界涌现" if tp.get("is_emerging_or_cross_cutting") else "主流演化"
        evs = ", ".join(f"[{e}]" for e in tp.get("recon_evidence_ids", [])[:4])
        track_lines.append(
            f"- `{tp.get('track_id')}` ({tp.get('sector')} | {tag}): **{tp.get('name')}** — "
            f"{tp.get('emergence_rationale', '')} 侦察证据: {evs}"
        )

    elim_header = (
        "| 淘汰候选 ID | 赛道 | 机会名称 | 周期 | 商业空白级 | 基准回收期 | 保守回收期 | 综合评分 | 淘汰/落选原因 |\n"
        "| :---: | :---: | :--- | :---: | :---: | ---: | ---: | ---: | :--- |"
    )
    elim_rows = [
        f"| `{e.get('opp_id')}` | {e.get('track_id')} | {e.get('title')} | {e.get('horizon')} | "
        f"{e.get('commercial_status', 'overseas_only_cn_blank')} | "
        f"{e.get('baseline_payback_months')}月 | {e.get('conservative_payback_months')}月 | "
        f"{e.get('weighted_pillar_score')} | {e.get('elimination_reason')} |"
        for e in eliminated
    ]
    elim_table = (
        elim_header + "\n" + "\n".join(elim_rows)
        if elim_rows
        else "(本次初筛候选池规模未超出决选上限，且全部通过保守回收期硬门禁，无被淘汰项。)"
    )

    return (
        f"### Stage 0 广谱侦察动态涌现赛道清单（共 {len(tracks)} 条）\n"
        f"侦察结论摘要: {plan.get('macro_recon_summary', '')}\n"
        + "\n".join(track_lines)
        + f"\n\n### Stage 2 确定性漏斗初筛审计（原始挖掘 {raw_count} 项 -> 入围决选 {shortlist_count} 项，淘汰 {len(eliminated)} 项）\n"
        + elim_table
    )


def render_evidence_index(
    records: list[EvidenceRecord],
    db_label: str = "data/evidence_vault_v2.db",
) -> str:
    """Deterministically compile Volume 05 from SQLite EvidenceVault (zero hallucination)."""
    cn_recs = [r for r in records if r.geo_scope == "CN"]
    gl_recs = [r for r in records if r.geo_scope == "GLOBAL"]
    lines = [
        "# 05. 核验证据库与权威引用总索引 (Verified EvidenceVault Citations Index)",
        "",
        f"> 本索引由 SQLite 持久化证据记忆库 (`{db_label}`) 自动确定性导出，共收录 **{len(records)}** 条去重溯源证据（含 Stage 0 `RECON` 侦察与各动态赛道深挖证据）："
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


def build_volume_specs(
    *,
    plan: dict[str, Any],
    dossiers: list[dict[str, Any]],
    evaluated: list[dict[str, Any]],
    elo_matches: list[dict[str, Any]],
    all_records: list[EvidenceRecord],
    raw_candidates_count: int,
    eliminated_candidates: list[dict[str, Any]],
    critique_note: str = "",
) -> list[tuple[str, str, str]]:
    """Build exact grounded V3 prompts for Volumes 00-04 cleanly shared by LangGraph & CLI."""
    roi_all_table = format_roi_table(evaluated)
    roi_power_table = format_roi_table(evaluated, sector="power_energy")
    roi_semi_table = format_roi_table(evaluated, sector="semiconductor")

    comm_all_table = format_commercial_whitespace_and_ai_table(evaluated)
    comm_power_table = format_commercial_whitespace_and_ai_table(evaluated, sector="power_energy")
    comm_semi_table = format_commercial_whitespace_and_ai_table(evaluated, sector="semiconductor")

    power_dossiers = format_dossiers(dossiers, sector="power_energy")
    semi_dossiers = format_dossiers(dossiers, sector="semiconductor")

    storm_all = format_storm_digest(evaluated)
    storm_power = format_storm_digest(evaluated, sector="power_energy")
    storm_semi = format_storm_digest(evaluated, sector="semiconductor")

    power_tids = {d["track_id"] for d in dossiers if d.get("sector") == "power_energy"} | {"RECON"}
    semi_tids = {d["track_id"] for d in dossiers if d.get("sector") == "semiconductor"} | {"RECON"}

    vault_power = format_vault_snippets(all_records, tracks=power_tids, limit=34)
    vault_semi = format_vault_snippets(all_records, tracks=semi_tids, limit=34)
    vault_all = format_vault_snippets(all_records, tracks=None, limit=42)

    power_track_labels = ", ".join(
        f"{d['track_id']}({d['track_name']})" for d in dossiers if d.get("sector") == "power_energy"
    ) or "电力能源动态赛道"
    semi_track_labels = ", ".join(
        f"{d['track_id']}({d['track_name']})" for d in dossiers if d.get("sector") == "semiconductor"
    ) or "半导体制造动态赛道"

    discovery_funnel_md = format_discovery_and_funnel_summary(
        plan=plan,
        raw_count=raw_candidates_count or len(evaluated) + len(eliminated_candidates),
        shortlist_count=len(evaluated),
        eliminated=eliminated_candidates,
    )

    elo_summary = "\n".join(
        f"- Round {m['round_idx']}: `{m['opp_a_id']}` vs `{m['opp_b_id']}` -> Winner `{m['winner_id']}` | {m['rationale']}"
        for m in elo_matches[:24]
    )

    return [
        (
            "00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md",
            "Volume 00: V3 总览、海内外在售厂商与产品空白全景、AI软硬协同范式与 Top 16 榜单",
            f"""Write **Volume 00: 电力能源与半导体芯片制造在线测试仪器仪表 3-5年及5-10年商业空白与AI原生开发战略总报告 (V3.0)**.
Step-Back Thesis: {plan.get('step_back_thesis', '')}
{discovery_funnel_md}

Commercial Vendor Supply, Product White-Space & AI Co-Design Master Matrix:
{comm_all_table}

Deterministic [ROI-CALC] Master Ranking Table (Top Shortlist):
{roi_all_table}

STORM Buying-Committee Highlights:
{storm_all}

Selected Grounded Evidence:
{vault_all}
{critique_note}

Mandatory Structure:
1. 执行摘要与核心判断（先中国后全球的结构性拐点；用商业供给与AI工程实证破除纸面空谈）
2. **海内外现有在售设备摸底 vs. 三级产品空白全景矩阵**（完整展示 16 项机会中哪些属“海内外均有在售”、哪些属“海外成熟/中国商业空白”、哪些属“全球真正空白”）
3. **AI 时代软硬件协同开发范式重构对在线检测仪器的实质改变**（计算传感“AI算力换硬件极限”降BOM、合成缺陷破解少样本冷启动、AI辅助多物理场/FPGA/上位机开发将研发周期从30月压至14月、断网边缘推理与模型订阅模式）
4. Stage 0 从零动态发现赛道与电力×半导体跨界能力复用（含跨界新兴赛道与共性平台复用）
5. Top 16 综合排位总表与 3-5年 vs 5-10年双时间窗对比（完整复现上面 Python 计算的三档回收期与 `[ROI-CALC]` 数据）暨淘汰候选审计
6. 仪器企业与投资方落地切入优先级决策建议（先选哪类空白、用何种 MVP 形态切入、如何防范红海降价战）。""",
        ),
        (
            "01_POWER_ENERGY_ONLINE_TESTING_OPPORTUNITIES.md",
            "Volume 01: 电力能源行业动态赛道商业格局、产品空白与AI软硬方案深度研报",
            f"""Write **Volume 01: 电力能源行业动态发现赛道（{power_track_labels}）3-5年及5-10年在线测试仪器商业落地与技术研报 (V3.0)**.
Power Commercial White-Space & AI Co-Design Matrix:
{comm_power_table}

Power Deterministic [ROI-CALC] Table:
{roi_power_table}

Power Track Dossiers:
{power_dossiers}

STORM Buyer Interrogation:
{storm_power}

Power Evidence Snippets:
{vault_power}
{critique_note}

Mandatory Structure (cover EVERY dynamically discovered Power track above in full practical depth):
- 第一节：中国市场产业痛点、在售设备招标格局与国产替代缺口（引用 `[EV-CN-...]`）
- 第二节：全球市场（欧美日中等地区标杆厂商如 Omicron/ABB/Keysight/Hioki 等在售型号及空白界定）（引用 `[EV-GL-...]`）
- 第三节：3-5年高ROI机会 vs 5-10年全球空白新物种（针对每项机会写清：商业空白级别 + 竞品切入楔子 + AI 计算传感/FPGA边缘协同硬件形态 + 良率/降本/环保/三档ROI `[ROI-CALC]` 量化支撑）
- 第四节：电厂/电池厂/智算中心买方四角色阻力、零样本冷启动破局与 Spec-in 方案。""",
        ),
        (
            "02_SEMICONDUCTOR_ONLINE_TESTING_OPPORTUNITIES.md",
            "Volume 02: 半导体芯片制造动态赛道商业格局、产品空白与AI软硬方案深度研报",
            f"""Write **Volume 02: 半导体芯片制造行业动态发现赛道（{semi_track_labels}）3-5年及5-10年在线量检测设备商业落地与技术研报 (V3.0)**.
Semiconductor Commercial White-Space & AI Co-Design Matrix:
{comm_semi_table}

Semiconductor Deterministic [ROI-CALC] Table:
{roi_semi_table}

Semiconductor Track Dossiers:
{semi_dossiers}

STORM Buyer Interrogation:
{storm_semi}

Semiconductor Evidence Snippets:
{vault_semi}
{critique_note}

Mandatory Structure (cover EVERY dynamically discovered Semiconductor track above in full practical depth):
- 第一节：中国晶圆厂/功率产线/封测厂良率痛点、海外龙头垄断型号与国产商业化缺口（引用 `[EV-CN-...]`）
- 第二节：全球 KLA/Onto/Camtek/Lasertec/Bruker/Horiba/Inficon 等在售产品矩阵 vs 真正的全球在线量测空白（引用 `[EV-GL-...]`）
- 第三节：3-5年国产首发替代 vs 5-10年全球空白新物种（针对每项机会写清：物理限界 + AI 逆散射/超分辨补偿国产中端器件 + 断网 FPGA+NPU EFEM 集成 + 四大支柱与三档 `[ROI-CALC]`）
- 第四节：晶圆厂工艺总工、Golden-Tool 对齐与 CFO 门禁壁垒破解方案。""",
        ),
        (
            "03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md",
            "Volume 03: 三情景产线ROI、仪器商业经济性与Elo排位报告",
            f"""Write **Volume 03: 制造端三情景 `[ROI-CALC]` 量化模型、不同商业空白毛利与AI研发经济性暨 Elo 排位报告 (V3.0)**.
{discovery_funnel_md}

Commercial White-Space & R&D Cycle Comparison:
{comm_all_table}

Master Deterministic [ROI-CALC] Table (Optimistic / Baseline / Conservative):
{roi_all_table}

Pairwise Elo Tournament Match Log:
{elo_summary}

STORM CFO & Procurement Gatekeeper Findings:
{storm_all}
{critique_note}

Mandatory Structure:
1. 生产制造端三情景区间 ROI 建模方法论（参数区间提取 + 保守压力情景 + 10% WACC 公式）
2. 完整入围机会的 `[ROI-CALC]` 乐观/基准/保守三档财务指标汇总与敏感性分析（明确 Tier-A/B/C）
3. **仪器研制商视角商业经济性对照（海内外均在售红海 vs 国内空白国产首发 vs 全球空白新物种的毛利、BOM 国产化降幅与 AI 把 30 个月研发压至 14 个月的回本优势）**
4. Stage 2 漏斗淘汰审计（含商业空白级别对比）与 AI Co-Scientist Elo 锦标赛排位暨一页纸算账模板。""",
        ),
        (
            "04_PRODUCT_TECH_AND_UPGRADE_STRATEGY_PLAYBOOK.md",
            "Volume 04: AI 时代在线测试仪器软硬件协同研发与商业化落地执行手册 (Playbook)",
            f"""Write **Volume 04: AI 时代在线测试仪器软硬件协同研发、工程落脚点与三级 GTM 商业化执行手册 (V3.0 Playbook)**.
Commercial White-Space & AI Co-Design Matrix:
{comm_all_table}

Master Ranking & Physics Context:
{roi_all_table}

Dossiers Summary:
{power_dossiers[:3600]}
{semi_dossiers[:3600]}

STORM Engineering Tweaks:
{storm_all}
{critique_note}

Mandatory Structure (FOCUS ON PRACTICAL BUILDABILITY IN THE AI ERA):
1. **计算传感核心方法论：“AI 算力换硬件物理极限”工程架构**（按光谱/质谱/光学/超声/高频电学平台拆解如何用 PINNs/逆散射/超分辨与国产成熟核心部件绕开海外禁运件并压降 BOM 30%-60%）
2. **AI 时代仪器研发生命周期新范式（30–48个月 → 10–18个月）**（AI 多物理场代理仿真 + 物理数字孪生合成缺陷工厂解决冷启动 + AI 辅助 FPGA RTL/高速采集驱动/SECS-GEM/IEC61850 上位机生成）
3. **Fab 与电网断网安全域 Edge-AI 工程落地五道坎**（FPGA+NPU 毫秒级确定性推理、Golden-Tool 自校准防漂移、原位防爆/超净旁路免停线设计、误报率 SLA 兜底与合规）
4. **可落地的产品形态与“商业化三级抓手”（Wedge Strategy）**：
   - 外挂式 AI 传感吊舱 / 旁路测试模块（Retrofit Pod，低风险快速进厂收费）
   - 独立在线国产替代整机（对准 `overseas_only_cn_blank` 抢占集采/扩产订单）
   - 全球首发 AI 原位 OEM 模组（嵌入工艺机台腔体 + 工艺模型库年度订阅与国际合规认证出海）
5. 未来 12–18 个月 MVP 研制里程碑与资源配置清单。""",
        ),
    ]


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
    raw_count = int(state.get("raw_candidates_count", 0))
    eliminated = state.get("eliminated_candidates", [])

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

    volumes_spec = build_volume_specs(
        plan=plan,
        dossiers=dossiers,
        evaluated=evaluated,
        elo_matches=elo_matches,
        all_records=all_records,
        raw_candidates_count=raw_count,
        eliminated_candidates=eliminated,
        critique_note=critique_note,
    )

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
    db_name = deps.settings.vault_db_name or "evidence_vault_v3.db"
    updated_drafts["05_VERIFIED_EVIDENCE_CITATIONS_INDEX.md"] = render_evidence_index(
        all_records, db_label=f"data/{db_name}"
    )

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
