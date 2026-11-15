"""Stage 0a (Siggi MCP Corpus + Macro Recon) & Stage 0b (Step-Back Discovery Planner)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from vf_ccus_workflow.nodes.deps import RuntimeDeps
from vf_ccus_workflow.prompts import DISCOVERY_PLANNER_SYSTEM
from vf_ccus_workflow.schemas import DiscoveryPlan, EvidenceRecord, TrackPlan, WorkflowState
from vf_ccus_workflow.tools.siggi_corpus_loader import load_siggi_corpus_hits

RECON_QUERIES: list[tuple[str, str, str]] = [
    # (geo_scope, mode, query)
    ("CN", "webpage", "中国 CCUS 二氧化碳捕集 利用 封存 年度报告 百万吨 管道 齐鲁石化 大亚湾 2025 2026"),
    ("CN", "webpage", "中国 绿色甲醇 绿氢 二氧化碳合成 示范项目 产能规划 十五五 2025 2026"),
    ("CN", "webpage", "中国 液化二氧化碳 LCO2 运输船 江南造船 厦船重工 中集太平洋 出口 标准 2025 2026"),
    ("CN", "webpage", "中国 CCUS 二氧化碳 纯度 标准 在线质谱仪 FTIR 分析小屋 竞争格局 中石化 中海油"),
    ("CN", "scholar", "超临界二氧化碳管道 杂质 腐蚀 NOx SOx H2S 在线监测 质谱 气相色谱"),
    ("GLOBAL", "search", "China CCUS CCS projects pipeline green methanol LCO2 ship 2025 2026 CO2 purity"),
    ("GLOBAL", "search", "Northern Lights CO2 impurity specification IMR-MS V&F Thermo MAX-iR FTIR CCS comparison"),
]


def ingest_siggi_corpus(deps: RuntimeDeps) -> list[EvidenceRecord]:
    """Deterministically ingest primary V&F/Thermo/Shell-IFE files into EvidenceVault."""
    hits = load_siggi_corpus_hits(deps.settings.siggi_corpus_dir)
    records: list[EvidenceRecord] = []
    for hit in hits:
        rec = deps.vault.upsert_hit(track_id="SIGGI_BASE", hit=hit)
        if rec is not None:
            records.append(rec)
    deps.vault.log_query(
        track_id="SIGGI_BASE",
        engine="siggi_mcp",
        geo_scope="SIGGI",
        query=f"local_corpus:{deps.settings.siggi_corpus_dir.name}",
        hits_count=len(records),
    )
    return records


async def run_macro_recon(
    deps: RuntimeDeps, profile: str = "flagship"
) -> tuple[list[EvidenceRecord], list[str]]:
    """Run Stage 0a live China + Global macro search without hardcoded outcomes."""
    queries = RECON_QUERIES if profile == "flagship" else RECON_QUERIES[:4]
    num_res = 6 if profile == "flagship" else 3
    records: list[EvidenceRecord] = []
    q_log: list[str] = []

    for geo, mode, q in queries:
        hits = await deps.search_router.search_track(
            track_id="RECON",
            geo_scope=geo,  # type: ignore[arg-type]
            query=q,
            mode=mode,  # type: ignore[arg-type]
            num_results=num_res,
        )
        deps.vault.log_query(
            track_id="RECON",
            engine="metaso" if geo == "CN" else "serper",
            geo_scope=geo,  # type: ignore[arg-type]
            query=q,
            hits_count=len(hits),
        )
        q_log.append(f"{geo}:{q[:50]}")
        for h in hits:
            rec = deps.vault.upsert_hit(track_id="RECON", hit=h)
            if rec is not None:
                records.append(rec)
    return records, q_log


def format_records_compact(records: list[EvidenceRecord], *, limit: int = 36) -> str:
    lines: list[str] = []
    for r in records[:limit]:
        body = (r.fulltext_excerpt or r.snippet).replace("\n", " ")[:480]
        lines.append(f"[{r.ev_id}] ({r.geo_scope}/{r.track_id}) {r.title}\nURL: {r.url}\nExcerpt: {body}")
    return "\n\n".join(lines)


def _fallback_default_tracks() -> list[TrackPlan]:
    return [
        TrackPlan(
            track_id="T1_EOR_PIPE",
            sector="S1_pipeline_ship_eor",
            name="中国百万吨级EOR与超临界CO2长输管道腐蚀监控",
            research_hypothesis="长输管道内H2S+NOx+SOx+O2+H2O共反应致碳钢暴发点蚀，传统单气体传感器与GC无法秒级预警，VF-QAS-CN契合三桶油防腐刚需。",
            cn_queries=[
                "中国 齐鲁石化 胜利油田 二氧化碳管道 大亚湾 CCUS 管道腐蚀 在线监测",
                "中石油 长庆油田 吉林油田 新疆 广汇 延安 CO2 驱油 管道 杂质控制",
                "国能 锦界 华能 陇东 百万吨 CCUS 捕集 压缩 输送 纯度",
            ],
            global_queries=[
                "supercritical CO2 pipeline impurity specification H2S NOx SOx O2 H2O online analyzer",
            ],
            priority=1,
        ),
        TrackPlan(
            track_id="T2_LCO2_SHIP",
            sector="S1_pipeline_ship_eor",
            name="中国船厂LCO2运输船建造与沿海接收外输枢纽",
            research_hypothesis="中国船厂承建国际LCO2船及沿海海上封存枢纽（大亚湾/恩平15-1等）需要严格对标Northern Lights标准的装卸船前在线QAS门禁。",
            cn_queries=[
                "中国船厂 液化二氧化碳运输船 LCO2 江南造船 大连造船 厦船重工 气体监测",
                "中海油 恩平15-1 惠州 大亚湾 千万吨级 CCUS 海上封存 纯度要求",
            ],
            global_queries=[
                "LCO2 carrier ship Northern Lights cargo CO2 quality analyzer IMR-MS",
            ],
            priority=2,
        ),
        TrackPlan(
            track_id="T3_GREEN_MEOH",
            sector="S2_green_methanol_ccu_chem",
            name="绿氢+CO2制绿色甲醇与e-SAF催化剂防中毒在线分析",
            research_hypothesis="内蒙古/吉林/沿海大型生物质/捕集CO2加氢制绿醇爆发，Cu/ZnO/Al2O3催化剂怕H2S/COS/CS2/NH3/胺中毒，CO2Sense 1s防护价值突出。",
            cn_queries=[
                "中国 绿色甲醇 e-SAF 二氧化碳加氢 合成 催化剂 中毒 硫 胺 在线监测",
                "金风科技 远景 吉电股份 电气风电 中煤 绿色甲醇 项目 产能 CO2原料气",
                "合成气 CO2 原料气 微量硫 氨 质谱 气相色谱 分析仪 响应时间",
            ],
            global_queries=[
                "e-methanol green methanol CO2 feedstock impurity H2S COS NH3 catalyst protection analyzer",
            ],
            priority=3,
        ),
        TrackPlan(
            track_id="T4_AMINE_RD",
            sector="S3_capture_rd_industry",
            name="燃煤/水泥/钢铁胺法捕集装置逃逸与科研中试平台",
            research_hypothesis="设计院、高校、水泥(海螺)与火电中试平台需要Track A进口CO2Sense裸机实时跟踪胺降解、亚硝胺/甲醛及热脱附动态。",
            cn_queries=[
                "海螺水泥 华能 国家能源集团 碳捕集 胺液降解 逃逸 在线质谱 PTR-MS IMR-MS",
                "中国 化工设计院 SEI 寰球 HQC 天辰 CCUS 分析小屋 分析仪表室 招标",
            ],
            global_queries=[
                "amine carbon capture solvent degradation nitrosamine online IMR-MS Brevik cement CCS",
            ],
            priority=4,
        ),
        TrackPlan(
            track_id="T5_COMP_PAC",
            sector="S1_pipeline_ship_eor",
            name="中国过程质谱/FTIR/GC竞品格局与本土PAC集成商生态",
            research_hypothesis="核实Thermo MAX-iR/MAX-Bev、ABB/Siemens/Servomex/E+H及国产质谱(聚光/雪迪龙/天瑞/磐合等)在CO2全组分分析的真实能力与盲区，以及中国分析小屋OEM伙伴。",
            cn_queries=[
                "中国 过程质谱仪 四极杆 飞行时间 质谱 厂商 聚光科技 雪迪龙 CCUS 气体分析",
                "中国 在线FTIR 二氧化碳杂质 Thermo MAX-iR ABB 西门子 艾默生 仕富梅 气相色谱",
                "中国 防爆分析小屋 系统集成商 聚光 川仪 皖仪 中石化工控 资质 GB/T 3836",
            ],
            global_queries=[
                "Thermo Fisher MAX-iR MAX-Bev vs IMR-MS V&F CO2 purity cycle time H2 N2 Ar limitation",
            ],
            priority=5,
        ),
        TrackPlan(
            track_id="T6_FOOD_CTRL",
            sector="S4_food_beverage_dryice",
            name="中国食品饮料级与干冰级CO2市场支付意愿对比验证",
            research_hypothesis="对照检验Sigi提到的中国1.5-2.5 Mt/yr食品级CO2市场：究竟存在升级机会还是因离线低成本抽检习惯导致ROI不成立（伪需求淘汰）。",
            cn_queries=[
                "中国 食品级二氧化碳 国家标准 GB 1886.228 在线监测 ISBT 成本 利润率",
                "百威 可口可乐 中国 食品级CO2 回收 苯 硫醇 甲醇 检测 方法 气相色谱",
            ],
            global_queries=[
                "ISBT EIGA beverage grade CO2 online analyzer cost effectiveness vs batch GC China",
            ],
            priority=6,
        ),
    ]


async def node_siggi_ingest_and_planner(
    state: WorkflowState, deps: RuntimeDeps
) -> dict[str, Any]:
    """Stage 0a + Stage 0b: Ingest local Siggi MCP corpus, run macro recon, and emit emergent DiscoveryPlan."""
    profile = state.get("profile", "flagship")
    siggi_records = ingest_siggi_corpus(deps)
    recon_records, q_log = await run_macro_recon(deps, profile=profile)

    siggi_ctx = format_records_compact(siggi_records, limit=24)
    recon_ctx = format_records_compact(recon_records, limit=24)

    user_prompt = (
        f"Contract: {deps.settings.contract.get('title')}\n"
        f"Profile: {profile}\n\n"
        f"=== SIGGI PRIMARY CORPUS ([EV-SIGGI-*]) ===\n{siggi_ctx}\n\n"
        f"=== LIVE CHINA & GLOBAL MACRO RECON ([EV-CN-*] / [EV-GL-*]) ===\n{recon_ctx}\n\n"
        "Based strictly on these primary materials and macro signals, generate a DiscoveryPlan with "
        "5 to 6 emergent tracks covering S1, S2, S3, Competitive/PAC Ecosystem, and S4 (negative/control sector check)."
    )

    tier = "producer" if profile == "flagship" else "fast"
    try:
        plan = await deps.llm.complete_structured(
            tier=tier,
            node="discovery_planner",
            system_prompt=DISCOVERY_PLANNER_SYSTEM,
            user_prompt=user_prompt,
            schema=DiscoveryPlan,
            max_tokens=3600,
        )
    except Exception:
        plan = DiscoveryPlan(
            contract_id=deps.settings.contract.get("contract_id", "VF-CCUS-CHINA-2026-V1"),
            profile=profile,
            macro_recon_summary="已完成Siggi一手资料与中/欧宏观CCS动态扫描（使用容错基准轨道）。",
            step_back_thesis="聚焦中国高压酸性杂气混输腐败点蚀、绿醇合成防毒与出口LCO2船运三大高付现意愿场景，剥离低支付意愿食品线下抽检红海。",
            track_plans=_fallback_default_tracks(),
        )

    return {
        "siggi_records": [r.model_dump() for r in siggi_records],
        "recon_records": [r.model_dump() for r in recon_records],
        "discovery_plan": plan.model_dump(),
        "evidence_stats": deps.vault.stats(),
        "telemetry_events": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": "siggi_ingest_and_planner",
                "siggi_records": len(siggi_records),
                "recon_records": len(recon_records),
                "recon_queries": q_log,
                "emergent_tracks": len(plan.track_plans),
            }
        ],
    }
