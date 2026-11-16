"""Stage 5: Parallel Multi-Agent Authoring of Volumes 00-06."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from bfbg_workflow.nodes.deps import RuntimeDeps
from bfbg_workflow.prompts.templates import VOLUME_SPECS
from bfbg_workflow.schemas import WorkflowState
from bfbg_workflow.tools.evidence_vault import format_records_compact


async def node_parallel_volume_synthesizer(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Generate all 7 core product R&D, interface, AI, QA/QC, and GTM volumes in parallel."""
    calc = state["calc_bundle"]
    md = calc["markdown_tables"]
    ipd_json = json.dumps(state.get("ipd_memo", {}), ensure_ascii=False)[:2200]
    storm_json = json.dumps(state.get("storm_panel", {}), ensure_ascii=False)[:2200]
    elo_json = json.dumps(state.get("elo_ranking", []), ensure_ascii=False)
    dossiers_ctx = json.dumps(state.get("track_dossiers", []), ensure_ascii=False)[:7000]

    cn_ctx = format_records_compact(deps.vault.list_all(geo_scope="CN"), limit=32)
    gl_ctx = format_records_compact(deps.vault.list_all(geo_scope="GLOBAL"), limit=24)
    pdf_ctx = format_records_compact(deps.vault.list_all(geo_scope="PDF"), limit=25)
    base_ctx = format_records_compact(deps.vault.list_all(geo_scope="BASE"), limit=18)

    datasheets_md = "\n".join(
        f"- `{ds['ev_id']}` | {ds['vendor']} `{ds['part_number']}` -> `./datasheets_pdf/{ds['filename']}` ({ds['subsystem']})"
        for ds in state.get("datasheet_assets", [])
    )

    async def _author(spec: tuple[str, str, str, str]) -> tuple[str, str]:
        fname, title_cn, role_cn, mandate = spec
        sys_p = (
            f"你是 BoilerSense-AI™ 研发团队的【{role_cn}】。"
            "请以可直接在实验室搭建、按表下单采购、照图接线联调、按 SOP 进厂焊接培训交付的工业工程级水准，"
            "使用专业简体中文撰写 Markdown 交付文档。"
        )
        usr_p = (
            f"撰写文档 `{fname}` — {title_cn}\n"
            f"职责要求：{mandate}\n\n"
            "【绝对铁律】：\n"
            "1. 所有事实、供应商型号、市场数据必须严格标注真实存在的 `[EV-CN-*]` / `[EV-GL-*]` / `[EV-PDF-*]` / `[EV-BASE-*]`，严禁编造不存在的编号；\n"
            "2. 所有光学链路预算、BOM 单价/毛利率、五年 NPV/IRR、电厂回收期必须逐字沿用下方 Python 确定性计算结果；\n"
            "3. 引用原厂 PDF 时必须使用精确相对路径 `./datasheets_pdf/<filename>`；\n"
            "4. 内容详尽扎实，包含清晰表格、接线/接口字段、公差阈值与可执行检查清单。\n\n"
            f"=== [PHY-CALC] ===\n{md['physics_link_md']}\n\n"
            f"=== [ARCH & ELO] ===\n{md['arch_comparison_md']}\nElo: {elo_json}\n\n"
            f"=== [BOM-CALC] ===\n{md['bom_matrix_md']}\n\n"
            f"=== [FIN-CALC] ===\n{md['financial_scenarios_md']}\n\n"
            f"=== [PLANT-ROI] ===\n{md['plant_roi_md']}\n\n"
            f"=== VERIFIED DATASHEETS (./datasheets_pdf/) ===\n{datasheets_md}\n\n"
            f"=== IPD & BUYER STORM ===\nIPD: {ipd_json}\nSTORM: {storm_json}\n\n"
            f"=== SPECIALIST DOSSIERS ===\n{dossiers_ctx}\n\n"
            f"=== EVIDENCE CN ===\n{cn_ctx}\n\n=== EVIDENCE GLOBAL ===\n{gl_ctx}\n\n"
            f"=== EVIDENCE PDF ===\n{pdf_ctx}\n\n=== EVIDENCE BASE ===\n{base_ctx}"
        )
        content = await deps.llm.complete_text(
            tier="producer",
            node=f"stage5_author_{fname[:2]}",
            system_prompt=sys_p,
            user_prompt=usr_p,
            max_tokens=7800,
            temperature=0.2,
        )
        return fname, content + "\n"

    results = await asyncio.gather(*(_author(sp) for sp in VOLUME_SPECS))
    return {"volumes": dict(results)}
