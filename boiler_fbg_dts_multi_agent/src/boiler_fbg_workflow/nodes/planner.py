"""Project Manager (PM) node - Planning and coordination.

Design Pattern References:
- Chapter 6 (P100-112): Planning pattern
- Chapter 11 (P183-195): Goal Setting and Monitoring
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from boiler_fbg_workflow.config import RuntimeDeps
from boiler_fbg_workflow.schemas import WorkflowState


def generate_final_report(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Generate final workflow report.
    
    Consolidates all stage outputs into a comprehensive report.
    """
    run_id = state.get("run_id", "unknown")
    mode = state.get("mode", "simulation")
    output_dir = Path(state.get("output_dir", "./outputs"))
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Collect all evidence IDs
    all_evidence_ids = set()
    for key, value in state.items():
        if isinstance(value, dict) and "evidence_ids" in value:
            all_evidence_ids.update(value["evidence_ids"])
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and "evidence_ids" in item:
                    all_evidence_ids.update(item["evidence_ids"])
    
    # Categorize evidence
    verified_evidence = [e for e in all_evidence_ids if not e.startswith("[EV-UNKNOWN") and not e.startswith("[EV-SYNTH")]
    pending_evidence = [e for e in all_evidence_ids if e.startswith("[EV-UNKNOWN")]
    synthetic_evidence = [e for e in all_evidence_ids if e.startswith("[EV-SYNTH")]
    
    # Build report
    report = {
        "report_id": f"REPORT-{run_id}",
        "generated_at": datetime.now().isoformat(),
        "mode": mode,
        "mode_disclaimer": _get_mode_disclaimer(mode),
        
        "executive_summary": {
            "project": "燃煤锅炉水冷壁光纤测温产品研发",
            "tech_route": state.get("tech_route_analysis", {}).get("recommended_route", "[待确定]"),
            "stages_completed": _count_completed_stages(state),
            "qa_reviews_count": len(state.get("qa_reviews", [])),
            "hitl_decisions_count": len(state.get("hitl_decisions", [])),
            "overall_status": _determine_overall_status(state),
        },
        
        "stage_outputs": {
            "stage_0_requirements": {
                "market_segments": state.get("market_segments", []),
                "market_sizing": state.get("market_sizing", []),
                "competitors": state.get("competitors", []),
                "requirements": state.get("requirements", []),
                "recommended_scenario": state.get("recommended_scenario", {}),
            },
            "stage_1_concept": {
                "tech_route_analysis": state.get("tech_route_analysis", {}),
                "sensor_specs": state.get("sensor_specs", []),
                "system_architecture": state.get("system_architecture", {}),
                "software_architecture": state.get("software_architecture", {}),
            },
            "stage_2_detailed_design": {
                "detailed_optical_design": state.get("detailed_optical_design", {}),
                "detailed_hw_design": state.get("detailed_hw_design", {}),
                "bom_items": state.get("bom_items", []),
                "cost_breakdown": state.get("cost_breakdown", {}),
            },
            "stage_3_development": state.get("development_status", {}),
            "stage_4_testing": {
                "test_results": state.get("test_results", []),
            },
            "stage_5_production": {
                "production_readiness": state.get("production_readiness", {}),
                "training_materials": state.get("training_materials", {}),
                "sales_toolkit": state.get("sales_toolkit", {}),
                "marketing_strategy": state.get("marketing_strategy", {}),
            },
        },
        
        "quality_assurance": {
            "qa_reviews": state.get("qa_reviews", []),
            "hitl_decisions": state.get("hitl_decisions", []),
            "stage_gate_results": state.get("stage_gate_results", {}),
        },
        
        "evidence_summary": {
            "total_evidence_count": len(all_evidence_ids),
            "verified_count": len(verified_evidence),
            "pending_verification_count": len(pending_evidence),
            "synthetic_count": len(synthetic_evidence),
            "verified_evidence_ids": sorted(verified_evidence),
            "pending_evidence_ids": sorted(pending_evidence),
            "synthetic_evidence_ids": sorted(synthetic_evidence),
        },
        
        "risks_and_limitations": {
            "risks": state.get("risks", []),
            "known_limitations": [
                "硬件适配器为契约定义，需实际硬件联调",
                "合成数据带SYNTHETIC标记，不声称电厂实测",
                "高温FBG规格需原厂确认",
                "市场数据待外部注入",
            ],
            "pending_items": [
                item for item in state.get("bom_items", [])
                if item.get("status") == "pending_quote"
            ],
        },
        
        "cost_summary": state.get("cost_ledger", deps.ledger.get_summary()),
        
        "telemetry": {
            "events": state.get("telemetry_events", []),
            "written_files": state.get("written_files", []),
        },
    }
    
    # Write report to file
    report_path = output_dir / f"final_report_{run_id}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # Write human-readable summary
    summary_path = output_dir / f"final_summary_{run_id}.md"
    _write_markdown_summary(report, summary_path)
    
    written_files = state.get("written_files", [])
    written_files.extend([str(report_path), str(summary_path)])
    
    return {
        "stage_gate_results": {
            "final_report_generated": True,
            "report_path": str(report_path),
            "summary_path": str(summary_path),
        },
        "written_files": written_files,
        "telemetry_events": [{
            "event": "final_report_generated",
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
        }],
    }


def _get_mode_disclaimer(mode: str) -> str:
    """Get disclaimer based on run mode."""
    disclaimers = {
        "simulation": (
            "本报告由模拟模式生成，所有角色输出为预定义模板数据，"
            "标记为[SIMULATION]。不代表真实LLM调用或实际产品开发结果。"
        ),
        "offline-replay": (
            "本报告由离线重放模式生成，基于历史trace数据，"
            "用于验证工作流逻辑，标记为[OFFLINE-REPLAY]。"
        ),
        "live": (
            "本报告由实时模式生成，包含真实LLM调用，"
            "标记为[LIVE-LLM]。实际硬件验证仍需线下完成。"
        ),
    }
    return disclaimers.get(mode, "未知运行模式")


def _count_completed_stages(state: WorkflowState) -> int:
    """Count completed stages."""
    completed = 0
    stage_keys = [
        "market_segments",  # Stage 0
        "tech_route_analysis",  # Stage 1
        "detailed_hw_design",  # Stage 2
        "development_status",  # Stage 3
        "test_results",  # Stage 4
        "production_readiness",  # Stage 5
    ]
    for key in stage_keys:
        if state.get(key):
            completed += 1
    return completed


def _determine_overall_status(state: WorkflowState) -> str:
    """Determine overall project status."""
    qa_reviews = state.get("qa_reviews", [])
    
    # Check for any BLOCKED reviews
    for review in qa_reviews:
        if review.get("gate_status") == "BLOCKED":
            return "BLOCKED - 存在阻塞性问题"
    
    # Check for HOLD reviews
    for review in qa_reviews:
        if review.get("gate_status") == "HOLD":
            return "HOLD - 等待人工决策"
    
    # Check completion
    if state.get("production_readiness"):
        return "COMPLETED - 所有阶段完成（需实际验证）"
    
    return "IN_PROGRESS - 工作流进行中"


def _write_markdown_summary(report: dict, path: Path) -> None:
    """Write human-readable markdown summary."""
    summary = f"""# 燃煤锅炉水冷壁光纤测温产品研发报告

**报告ID**: {report['report_id']}
**生成时间**: {report['generated_at']}
**运行模式**: {report['mode']}

> ⚠️ {report['mode_disclaimer']}

---

## 一、执行摘要

| 项目 | 状态 |
|------|------|
| 技术路线 | {report['executive_summary']['tech_route']} |
| 完成阶段数 | {report['executive_summary']['stages_completed']} / 6 |
| QA审查次数 | {report['executive_summary']['qa_reviews_count']} |
| HITL决策次数 | {report['executive_summary']['hitl_decisions_count']} |
| 总体状态 | {report['executive_summary']['overall_status']} |

---

## 二、证据追溯

| 类别 | 数量 |
|------|------|
| 总证据数 | {report['evidence_summary']['total_evidence_count']} |
| 已验证 | {report['evidence_summary']['verified_count']} |
| 待验证 | {report['evidence_summary']['pending_verification_count']} |
| 合成数据 | {report['evidence_summary']['synthetic_count']} |

**待验证证据ID**:
{chr(10).join('- ' + e for e in report['evidence_summary']['pending_evidence_ids'][:10])}
{('... 及其他 ' + str(len(report['evidence_summary']['pending_evidence_ids']) - 10) + ' 项') if len(report['evidence_summary']['pending_evidence_ids']) > 10 else ''}

---

## 三、已知限制

{chr(10).join('- ' + lim for lim in report['risks_and_limitations']['known_limitations'])}

---

## 四、待处理采购项

| 项目ID | 描述 | 状态 |
|--------|------|------|
"""
    for item in report['risks_and_limitations'].get('pending_items', [])[:5]:
        summary += f"| {item.get('item_id', 'N/A')} | {item.get('description', 'N/A')} | {item.get('status', 'N/A')} |\n"
    
    summary += """
---

*本报告基于《Agentic Design Patterns》(Antonio Gulli) 设计模式构建*
"""
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(summary)
