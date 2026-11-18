"""LangGraph StateGraph Assembly for Multi-Agent R&D Workflow.

Design Pattern References:
- Chapter 1 (P23-35): Prompt Chaining - Stage sequence
- Chapter 3 (P50-64): Parallelization - Parallel role execution
- Chapter 7 (P113-131): Multi-Agent Collaboration - Topology
- Chapter 4 (P65-78): Reflection - QA review loops
- Chapter 13 (P204-212): HITL - Gate interrupts
"""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from boiler_fbg_workflow.config import (
    CostLedger,
    RuntimeDeps,
    STAGE_CONFIG,
    WorkflowSettings,
)
from boiler_fbg_workflow.schemas import GateStatus, WorkflowState


def node_stage_0_market_research(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 0: Market research and requirements analysis.
    
    Parallel execution: MKT (market research) + OPT (technical feasibility)
    Reference: Chapter 3 (P50-64) Parallelization
    """
    from boiler_fbg_workflow.nodes.market_researcher import execute_market_research
    from boiler_fbg_workflow.nodes.optical_engineer import execute_tech_feasibility
    
    run_id = state.get("run_id", "unknown")
    mode = state.get("mode", "simulation")
    
    # In simulation mode, use pre-defined outputs
    if deps.is_simulation:
        return _simulation_stage_0_output(run_id)
    
    # Live mode: parallel execution
    mkt_result = execute_market_research(deps)
    opt_result = execute_tech_feasibility(deps)
    
    return {
        "current_stage": "stage_0_requirements",
        "market_segments": mkt_result.get("segments", []),
        "market_sizing": mkt_result.get("sizing", []),
        "competitors": mkt_result.get("competitors", []),
        "requirements": opt_result.get("requirements", []),
        "recommended_scenario": mkt_result.get("recommended_scenario", {}),
        "telemetry_events": [{
            "event": "stage_0_completed",
            "run_id": run_id,
            "mode": mode,
        }],
    }


def node_stage_0_qa_review(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 0 QA Review - Independent quality gate.
    
    Reference: Chapter 4 (P65-78) Reflection pattern
    """
    from boiler_fbg_workflow.nodes.quality_reviewer import execute_qa_review
    
    if deps.is_simulation:
        return _simulation_qa_review("stage_0_requirements", state.get("run_id", ""))
    
    return execute_qa_review(
        state,
        stage="stage_0_requirements",
        deps=deps,
    )


def node_stage_1_concept_design(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 1: Concept design.
    
    Parallel execution: OPT + HW + SW
    """
    from boiler_fbg_workflow.nodes.optical_engineer import execute_optical_design
    from boiler_fbg_workflow.nodes.hardware_integrator import execute_hw_architecture
    from boiler_fbg_workflow.nodes.software_developer import execute_sw_architecture
    
    run_id = state.get("run_id", "unknown")
    
    if deps.is_simulation:
        return _simulation_stage_1_output(run_id)
    
    opt_result = execute_optical_design(state, deps)
    hw_result = execute_hw_architecture(state, deps)
    sw_result = execute_sw_architecture(state, deps)
    
    return {
        "current_stage": "stage_1_concept",
        "tech_route_analysis": opt_result.get("tech_route", {}),
        "sensor_specs": opt_result.get("sensor_specs", []),
        "system_architecture": hw_result.get("architecture", {}),
        "software_architecture": sw_result.get("architecture", {}),
        "telemetry_events": [{
            "event": "stage_1_completed",
            "run_id": run_id,
        }],
    }


def node_stage_1_qa_review(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 1 QA Review."""
    from boiler_fbg_workflow.nodes.quality_reviewer import execute_qa_review
    
    if deps.is_simulation:
        return _simulation_qa_review("stage_1_concept", state.get("run_id", ""))
    
    return execute_qa_review(state, stage="stage_1_concept", deps=deps)


def node_stage_2_detailed_design(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 2: Detailed design and procurement review.
    
    Parallel execution: OPT + HW + SCM + FIN
    """
    run_id = state.get("run_id", "unknown")
    
    if deps.is_simulation:
        return _simulation_stage_2_output(run_id)
    
    from boiler_fbg_workflow.nodes.optical_engineer import execute_detailed_optical
    from boiler_fbg_workflow.nodes.hardware_integrator import execute_detailed_hw
    from boiler_fbg_workflow.nodes.supply_chain import execute_supplier_analysis
    from boiler_fbg_workflow.nodes.finance import execute_cost_analysis
    
    opt_result = execute_detailed_optical(state, deps)
    hw_result = execute_detailed_hw(state, deps)
    scm_result = execute_supplier_analysis(state, deps)
    fin_result = execute_cost_analysis(state, deps)
    
    return {
        "current_stage": "stage_2_detailed_design",
        "detailed_optical_design": opt_result,
        "detailed_hw_design": hw_result.get("design", {}),
        "bom_items": hw_result.get("bom", []),
        "supplier_analysis": scm_result.get("suppliers", []),
        "cost_breakdown": fin_result.get("breakdown", {}),
        "telemetry_events": [{
            "event": "stage_2_completed",
            "run_id": run_id,
        }],
    }


def node_stage_2_qa_review(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 2 QA Review with BOM compliance check."""
    from boiler_fbg_workflow.nodes.quality_reviewer import execute_qa_review
    
    if deps.is_simulation:
        return _simulation_qa_review("stage_2_detailed_design", state.get("run_id", ""))
    
    return execute_qa_review(state, stage="stage_2_detailed_design", deps=deps)


def node_hitl_gate(state: WorkflowState, *, deps: RuntimeDeps, gate_type: str) -> dict[str, Any]:
    """Human-in-the-Loop gate node.
    
    Reference: Chapter 13 (P204-212) HITL pattern
    """
    from boiler_fbg_workflow.nodes.hitl_gate import execute_hitl_gate
    
    if deps.is_simulation:
        return _simulation_hitl_decision(gate_type, state.get("run_id", ""))
    
    return execute_hitl_gate(state, gate_type=gate_type, deps=deps)


def route_after_qa(state: WorkflowState, *, deps: RuntimeDeps, stage: str) -> Literal["hitl", "next", "rewrite"]:
    """Route based on QA review result.
    
    Reference: Chapter 4 (P65-78) - Conditional routing after reflection
    Reference: Chapter 13 (P204-212) - HITL for unresolvable issues
    
    After MAX_REWRITE_ATTEMPTS blocked reviews, escalate to HITL
    rather than infinite loop.
    """
    MAX_REWRITE_ATTEMPTS = 2
    
    qa_reviews = state.get("qa_reviews", [])
    
    # Count reviews for this stage
    stage_reviews = [r for r in qa_reviews if r.get("stage") == stage]
    blocked_count = sum(1 for r in stage_reviews if r.get("gate_status") == GateStatus.BLOCKED.value)
    
    # Find the latest review for this stage
    latest_review = None
    for review in reversed(qa_reviews):
        if review.get("stage") == stage:
            latest_review = review
            break
    
    if not latest_review:
        return "next"
    
    gate_status = latest_review.get("gate_status", "PASS")
    
    if gate_status == GateStatus.BLOCKED.value:
        # After max attempts, escalate to HITL instead of infinite rewrite loop
        if blocked_count >= MAX_REWRITE_ATTEMPTS:
            return "hitl"  # Escalate to human decision
        return "rewrite"
    elif gate_status == GateStatus.HOLD.value:
        return "hitl"
    elif gate_status == GateStatus.PENDING_HITL.value:
        return "hitl"
    else:
        return "next"


def node_stage_3_development(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 3: Development implementation."""
    run_id = state.get("run_id", "unknown")
    
    if deps.is_simulation:
        return _simulation_stage_3_output(run_id)
    
    from boiler_fbg_workflow.nodes.hardware_integrator import execute_hw_integration
    from boiler_fbg_workflow.nodes.software_developer import execute_sw_development
    
    hw_result = execute_hw_integration(state, deps)
    sw_result = execute_sw_development(state, deps)
    
    return {
        "current_stage": "stage_3_development",
        "development_status": {
            "hardware": hw_result,
            "software": sw_result,
        },
        "telemetry_events": [{"event": "stage_3_completed", "run_id": run_id}],
    }


def node_stage_4_testing(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 4: System testing and verification."""
    run_id = state.get("run_id", "unknown")
    
    if deps.is_simulation:
        return _simulation_stage_4_output(run_id)
    
    from boiler_fbg_workflow.nodes.quality_reviewer import execute_system_testing
    
    test_result = execute_system_testing(state, deps)
    
    return {
        "current_stage": "stage_4_testing",
        "test_results": test_result.get("results", []),
        "telemetry_events": [{"event": "stage_4_completed", "run_id": run_id}],
    }


def node_stage_5_production(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Stage 5: Production introduction and training."""
    run_id = state.get("run_id", "unknown")
    
    if deps.is_simulation:
        return _simulation_stage_5_output(run_id)
    
    from boiler_fbg_workflow.nodes.manufacturing import execute_production_readiness
    from boiler_fbg_workflow.nodes.training import execute_training_development
    from boiler_fbg_workflow.nodes.marketing import execute_marketing_strategy
    
    mfg_result = execute_production_readiness(state, deps)
    trn_result = execute_training_development(state, deps)
    mkt_result = execute_marketing_strategy(state, deps)
    
    return {
        "current_stage": "stage_5_production",
        "production_readiness": mfg_result,
        "training_materials": trn_result.get("materials", {}),
        "sales_toolkit": trn_result.get("sales_toolkit", {}),
        "marketing_strategy": mkt_result,
        "telemetry_events": [{"event": "stage_5_completed", "run_id": run_id}],
    }


def node_final_report(state: WorkflowState, *, deps: RuntimeDeps) -> dict[str, Any]:
    """Generate final workflow report."""
    from boiler_fbg_workflow.nodes.planner import generate_final_report
    
    return generate_final_report(state, deps)


# Simulation output generators - NOW USING REAL RESEARCH DATA
def _simulation_stage_0_output(run_id: str) -> dict[str, Any]:
    """Generate Stage 0 output using REAL RESEARCH DATA.
    
    Data sourced from engineering research package with proper evidence IDs.
    """
    from boiler_fbg_workflow.research_data import (
        RECOMMENDED_SCENARIO,
        BUDGET_SUMMARY,
        VENDOR_SPECS,
        RISK_REGISTER,
    )
    
    return {
        "current_stage": "stage_0_requirements",
        "market_segments": [
            {
                "segment_id": "SEG-PILOT-001",
                "name": "300-660MW调峰煤粉直流炉",
                "description": "参与深度调峰的现役超/超超临界煤粉直流炉，背火侧可达水冷壁管屏",
                "estimated_boiler_count": "[市场数据待注入-不编造]",
                "notes": "目标画像非已找到客户；调峰负荷/给水变动对应温差可解释",
                "evidence_ids": ["[EV-DESIGN-SCEN-001]"],
            },
        ],
        "market_sizing": [
            {
                "calc_tag": "[MKT-CALC]",
                "segment_id": "SEG-PILOT-001",
                "horizon": "2026-2028",
                "tam_units": "[市场数据待注入]",
                "tam_cny_wan": "[市场数据待注入]",
                "sam_units": "[市场数据待注入]",
                "sam_cny_wan": "[市场数据待注入]",
                "som_units": "[市场数据待注入]",
                "som_cny_wan": "[市场数据待注入]",
                "assumptions": "火电≠煤电、机组数≠锅炉数，不能据装机容量编算TAM金额",
                "evidence_ids": ["[EV-LIT-NEA-001]"],
                "data_injection_required": True,
            },
        ],
        "competitors": [
            {
                "vendor_name": "南京大得",
                "origin": "domestic",
                "tech_route": "FBG/DTS(混杂表述)",
                "key_products": ["锅炉壁温光纤监测系统"],
                "strengths": "已有锅炉壁温光纤方案对外提供",
                "weaknesses": "原理表述混杂(拉曼/OTDR与FBG/WDM同页)",
                "china_presence": "已有",
                "evidence_ids": ["[EV-COMP-DADE-001]"],
                "confidence": "B",
                "limitation": "仅能证实其对外提供该类方案，不能借其混杂说明判断技术细节或价格",
            },
            {
                "vendor_name": "国家能源集团电科院锅检公司",
                "origin": "domestic",
                "tech_route": "飞秒/双栅FBG",
                "key_products": ["自研系统-非商品化"],
                "strengths": "报道称投运两年多、±1°C、700°C、双光栅",
                "weaknesses": "研发/使用方自述，未附原始校准、样本量、失效率",
                "evidence_ids": ["[EV-COMP-CEIC-001]"],
                "confidence": "B",
                "limitation": "不把宣传精度、寿命和适用对象作为本产品保证",
            },
        ],
        "requirements": [
            {
                "req_id": "R01",
                "category": "measurement",
                "description": "32-64个局部水冷壁接触测点",
                "target_value": "64点(8串×8点)",
                "priority": "must",
                "verification_method": "λ预算与原厂定制能力确认",
                "status": "draft",
                "evidence_ids": ["[EV-REQ-R01]"],
            },
            {
                "req_id": "R02",
                "category": "temperature",
                "description": "拟验证连续测量温度范围",
                "target_value": "25-600",
                "unit": "°C",
                "priority": "must",
                "notes": "700°C短时能力仅候选，须规定时间/循环/漂移；不是锅炉运行许可温度",
                "verification_method": "高温炉标定+现场比对",
                "status": "draft",
                "evidence_ids": ["[EV-REQ-R02]"],
            },
            {
                "req_id": "R04",
                "category": "accuracy",
                "description": "现场试点匹配参考工况差值目标",
                "target_value": "±5",
                "unit": "°C",
                "priority": "must",
                "current_status": "NOT_MET",
                "current_value": "5.73°C (k=2)",
                "notes": "⚠️ 当前工程计算不确定度5.73°C超过目标±5°C - 需改进或重定目标",
                "verification_method": "现场参考比对(参考/位置/不确定度足够时)",
                "status": "BLOCKED",
                "evidence_ids": ["[EV-CALC-ENG-001]"],
            },
            {
                "req_id": "R05",
                "category": "power",
                "description": "场侧无供电光纤传感，冷端电气系统独立供电、UPS",
                "target_value": "≥150Wh UPS可用量",
                "priority": "must",
                "verification_method": "电源配置验证",
                "status": "draft",
                "evidence_ids": ["[EV-REQ-R05]"],
            },
            {
                "req_id": "R10",
                "category": "safety",
                "description": "AI仅解释趋势、给建议与证据，不替代运行规程与保护",
                "target_value": "人工决策确认/无DCS写权限",
                "priority": "must",
                "verification_method": "架构审查 + 功能测试 + 代码审计",
                "status": "draft",
                "evidence_ids": ["[EV-REQ-R10]"],
            },
        ],
        "recommended_scenario": RECOMMENDED_SCENARIO,
        "budget_summary": BUDGET_SUMMARY,
        "risk_register": RISK_REGISTER[:5],
        "telemetry_events": [{
            "event": "stage_0_completed",
            "run_id": run_id,
            "mode": "simulation_with_real_research_data",
            "data_source": "engineering_research_package_v0.1",
            "tag": "[RESEARCH_DATA]",
        }],
    }


def _simulation_qa_review(stage: str, run_id: str) -> dict[str, Any]:
    """Generate QA review based on REAL RESEARCH DATA.
    
    CRITICAL: QA MUST REJECT Stage 2 because:
    1. Field uncertainty 5.73°C > ±5°C target
    2. All BOM prices are ENGINEERING_SCENARIO_NO_QUOTE
    3. Technica specs are WEB_INDEX_ONLY
    """
    from boiler_fbg_workflow.research_data import get_qa_gate_decision, ENGINEERING_CALCULATIONS
    
    # For Stage 2 (detailed design), QA MUST reject due to uncertainty not meeting target
    if stage == "stage_2_detailed_design":
        qa_decision = get_qa_gate_decision()
        return {
            "qa_reviews": [{
                "review_id": f"QA-{stage}-{run_id[:8]}",
                "stage": stage,
                "reviewer_role": "qa",
                "overall_assessment": (
                    "❌ QA审查未通过 - 存在阻塞性问题。"
                    f"现场不确定度{ENGINEERING_CALCULATIONS['uncertainty_budget']['field_U_k2_C']}°C "
                    f"超过目标±{ENGINEERING_CALCULATIONS['uncertainty_budget']['target_MPE_C']}°C。"
                    "全部BOM价格为预算情景无实际报价。Technica规格仅为网页索引待原厂确认。"
                ),
                "issues": qa_decision["critical_issues"],
                "gate_status": "BLOCKED",
                "requires_hitl": True,
                "hitl_reason": "存在阻塞性技术问题，需人工决策是否调整目标或进行实验验证",
                "artifacts_reviewed": [
                    "detailed_optical_design",
                    "detailed_hw_design", 
                    "bom_items",
                    "cost_breakdown",
                    "supplier_analysis",
                ],
                "evidence_ids": ["[EV-REVIEW-QA-001]"],
                "hold_count": qa_decision["hold_count"],
            }],
        }
    
    # For other stages, conditional pass with noted issues
    return {
        "qa_reviews": [{
            "review_id": f"QA-{stage}-{run_id[:8]}",
            "stage": stage,
            "reviewer_role": "qa",
            "overall_assessment": (
                "条件通过 - 基于真实研究数据审查。"
                "已识别待验证项和HOLD项，需跟踪解决。"
            ),
            "issues": [
                {
                    "issue_id": f"ISS-{stage}-001",
                    "stage": stage,
                    "role_source": "qa",
                    "severity": "major",
                    "title": "市场数据待外部注入",
                    "description": "火电≠煤电、机组数≠锅炉数，不能据装机容量编算TAM",
                    "required_action": "从父级任务获取具体市场调研数据",
                    "assigned_to": "mkt",
                    "status": "open",
                    "evidence_ids": ["[EV-LIT-NEA-001]"],
                },
                {
                    "issue_id": f"ISS-{stage}-002",
                    "stage": stage,
                    "role_source": "qa",
                    "severity": "major",
                    "title": "供应商规格待原厂确认",
                    "description": "Technica T885/T890 PDF下载失败，仅网页索引",
                    "required_action": "获取原厂正式数据表和报价",
                    "assigned_to": "scm",
                    "status": "open",
                    "evidence_ids": ["[EV-SPEC-T890-001]"],
                },
            ],
            "gate_status": "CONDITIONAL_PASS",
            "requires_hitl": False,
            "artifacts_reviewed": [f"{stage}_outputs"],
            "evidence_ids": ["[EV-REVIEW-QA-002]"],
        }],
    }


def _simulation_hitl_decision(gate_type: str, run_id: str) -> dict[str, Any]:
    """Generate simulation HITL decision."""
    return {
        "hitl_decisions": [{
            "decision_id": f"HITL-{gate_type}-{run_id[:8]}",
            "stage": gate_type.replace("_approval", ""),
            "gate_type": gate_type,
            "request_summary": f"[SIMULATION] {gate_type} 需人工审批",
            "options_presented": ["approve", "reject", "defer"],
            "decision": "approve",
            "decision_rationale": "[SIMULATION] 模拟自动批准，实际需人工决策",
            "decided_by": "[SIMULATION_AUTO]",
            "conditions": ["实际运行时需人工确认"],
            "evidence_ids": ["[EV-SYNTH-HITL-001]"],
        }],
    }


def _simulation_stage_1_output(run_id: str) -> dict[str, Any]:
    """Generate Stage 1 output using REAL RESEARCH DATA."""
    from boiler_fbg_workflow.research_data import VENDOR_SPECS, ENGINEERING_CALCULATIONS
    
    return {
        "current_stage": "stage_1_concept",
        "tech_route_analysis": {
            "recommended_route": "飞秒Type II/PbP高温FBG",
            "alternatives_considered": [
                {
                    "route": "再生FBG (RFBG)",
                    "status": "可行备选",
                    "condition": "必须比较同温同寿命同封装数据",
                },
                {
                    "route": "Raman DTS",
                    "status": "备选(米级热点)",
                    "condition": "当重点为长距离覆盖可接受米级热点定位时",
                    "ref_vendor": "Sensornet Sentinel系列",
                },
            ],
            "selection_rationale": (
                "主路线：采购完整封装/校准探头，避免自研裸纤封装拖延。"
                "多点WDM、窄光栅区域；engionic原厂标到1000°C但'存活'不等'准确多年'。"
            ),
            "pending_verification": [
                "高温漂移（参考MDPI论文Grobnic等900-1000°C试验）",
                "峰形/双折射",
                "封装摩擦应变",
                "反射率/带宽取决订货规格",
            ],
            "evidence_ids": ["[EV-LIT-MDPI-001]", "[EV-SPEC-ENGIONIC-001]"],
            "drift_reference": {
                "source": "Sensors 2021,21,1454 (Grobnic et al.)",
                "finding": "初期红移、后期蓝移，预退火不能保证消除长期漂移",
                "limitation": "不能用900°C漂移数值线性外推600°C寿命",
            },
        },
        "sensor_specs": [
            {
                "spec_id": "DEMOD-LUNA-001",
                "vendor": "Luna Innovations",
                "model": "si255-EV-08-1460-1620-0010-DP",
                "source_status": "PDF_VERIFIED",
                "specs": VENDOR_SPECS["luna_si255"]["specs"],
                "hold_items": VENDOR_SPECS["luna_si255"]["hold_items"],
                "evidence_ids": ["[E05]"],
            },
            {
                "spec_id": "DEMOD-HBK-001",
                "vendor": "HBK",
                "model": "FS22SI",
                "source_status": "PDF_VERIFIED",
                "specs": VENDOR_SPECS["hbk_fs22si"]["specs"],
                "hold_items": VENDOR_SPECS["hbk_fs22si"]["hold_items"],
                "evidence_ids": ["[E06]"],
            },
            # v0.2: FiSens as LAB RFQ PRIORITY (Technica REVOKED)
            {
                "spec_id": "PROBE-FISENS-001",
                "vendor": "FiSens",
                "model": "1550 STD narrow + AC",
                "source_status": "PDF_VERIFIED",
                "v0_2_status": "LAB_RFQ_PRIORITY",
                "specs": VENDOR_SPECS["fisens_1550"]["specs_from_pdf"],
                "hold_items": VENDOR_SPECS["fisens_1550"]["hold_items"],
                "evidence_ids": ["[E17]"],
            },
            # v0.2: CALSENS as second RFQ source
            {
                "spec_id": "PROBE-CALSENS-001",
                "vendor": "CALSENS",
                "model": "High Temperature FBG Sensor",
                "source_status": "PDF_VERIFIED",
                "v0_2_status": "SECOND_RFQ_SOURCE",
                "specs": VENDOR_SPECS["calsens_ht"]["specs_from_pdf"],
                "hold_items": VENDOR_SPECS["calsens_ht"]["hold_items"],
                "evidence_ids": ["[E18]"],
            },
            # v0.2: Technica REVOKED - for reference only
            {
                "spec_id": "PROBE-T890-REVOKED",
                "vendor": "Technica",
                "model": "T890",
                "source_status": "REVOKED_UNVERIFIED_SEARCH_ONLY",
                "v0_2_status": "REVOKED_FROM_MAIN_SELECTION",
                "revocation_reason": "v0.2撤销：PDF未取得，HTML挑战失败，参数UNVERIFIED",
                "evidence_ids": ["[E08]"],
                "limitation": "⚠️ 仅作RFI线索，不作选型依据",
            },
        ],
        "wavelength_budget": ENGINEERING_CALCULATIONS["wavelength_budget"],
        "system_architecture": {
            "topology": "8独立串×8点/串，星型光纤网络 + 集中解调",
            "data_chain": (
                "管壁→可拆金属热接触夹具→松套高温FBG封装→陶瓷/金属高温转接段→"
                "冷端装甲单模传输纤→接线盒/熔接盘→APC跳线→解调仪→隔离采集LAN→"
                "工业PC→HMI→单向/隔离接口至获准目的系统"
            ),
            "components": [
                "Luna si255-EV 8CH解调仪 (商用HOLD) / HBK FS22SI (实验HOLD)",
                "FiSens 1550 STD+AC 高温FBG探头 (LAB_RFQ_PRIORITY)",
                "CALSENS高温FBG (SECOND_RFQ)",
                "OSENSA PRB1000HT 非FBG对照 (CONTRAST_SYSTEM)",
                "⚠️ Technica T890/T885 v0.2撤销 (REVOKED)",
                "现场高温阵列 NOT_SELECTED",
                "Advantech UNO-2484G V2 工业计算机",
                "隔离网络/UPS/机柜",
            ],
            "interfaces": {
                "to_dcs": "OPC-UA/Modbus TCP（只读获取标签，不写）",
                "network_isolation": "依27号令由电厂网安确定分区和单向隔离",
            },
            "safety_isolation": "无DCS写权限；TCP只读不等于物理单向隔离",
            "evidence_ids": ["[EV-ARCH-001]", "[EV-LIT-ORDER27-001]"],
        },
        "software_architecture": {
            "modules": [
                "驱动采集→规范化→质量检验（ICD-05）",
                "规则与时序报警（硬规则+统计模型）",
                "HMI可视化",
                "AI解释建议（非关键路径）",
                "审计日志",
            ],
            "deployment": "Advantech UNO-2484G V2 / 等效工业平台",
            "ai_constraints": (
                "LLM不在采集/报警关键路径；原始波长/报警不可由LLM改写；"
                "AI建议另表保存引用标签、时间窗、模型版本与不确定度；"
                "发现输入缺失、工况越界或参考不一致则拒绝给操作指令"
            ),
            "fallback": "无论模型离线/失效，采集与确定性报警继续",
            "evidence_ids": ["[EV-ARCH-SW-001]"],
        },
        "telemetry_events": [{
            "event": "stage_1_completed",
            "run_id": run_id,
            "mode": "simulation_with_real_research_data",
            "data_source": "engineering_research_package_v0.2",
            "v0_2_changes": ["Technica_REVOKED", "FiSens_LAB_RFQ_PRIORITY", "CALSENS_SECOND_RFQ"],
        }],
    }


def _simulation_stage_2_output(run_id: str) -> dict[str, Any]:
    """Generate Stage 2 output using REAL RESEARCH DATA.
    
    IMPORTANT: All prices are ENGINEERING_SCENARIO_NO_QUOTE - not actual quotes.
    All BOM items are HOLD status.
    """
    from boiler_fbg_workflow.research_data import (
        BOM_LAB_TIER,
        BOM_PILOT_TIER,
        BUDGET_SUMMARY,
        ENGINEERING_CALCULATIONS,
    )
    
    return {
        "current_stage": "stage_2_detailed_design",
        "detailed_optical_design": {
            "sensor_layout": "8独立串×8点/串=64点，纵向间隔0.5-1m覆盖3.5-7m",
            "channel_count": 64,
            "fiber_routing": "背火侧可达管屏，8条串不在同一支承/单一路径集中",
            "point_selection": (
                "横向选哪8根管必须由历史偏差、燃烧器/吹灰/边墙效应、"
                "可达性与热工分析决定，不默认连续8根即可代表全炉"
            ),
            "wavelength_budget": ENGINEERING_CALCULATIONS["wavelength_budget"],
            "optical_power_budget": ENGINEERING_CALCULATIONS["optical_power_budget"],
            "evidence_ids": ["[EV-DESIGN-OPT-001]"],
            "notes": "此间隔是勘查起始假设，不是对0.5m以下热点不会漏检的保证",
        },
        "detailed_hw_design": {
            "primary_demodulator": {
                "tier": "商用试点",
                "model": "Luna si255-EV-08-1460-1620-0010-DP",
                "channels": 8,
                "wavelength_nm": "1460-1620",
                "speed_hz": 10,
                "source_status": "PDF_VERIFIED",
                "release_status": "HOLD",
                "hold_reason": "SDK/供货/许可与校准待确认",
            },
            "lab_demodulator": {
                "tier": "实验室",
                "model": "HBK FS22SI 4CH",
                "channels": 4,
                "wavelength_nm": "1500-1600",
                "speed_hz": 1,
                "source_status": "PDF_VERIFIED",
                "release_status": "HOLD",
                "hold_reason": "租借可用性未确认",
            },
            "sensors": {
                # v0.2: Technica REVOKED, FiSens as RFQ priority
                "lab_rfq_priority": "FiSens 1550 STD narrow + AC (PDF_VERIFIED, RFQ_PRIORITY)",
                "lab_rfq_second": "CALSENS High Temp FBG (PDF_VERIFIED, RFQ_CANDIDATE)",
                "field_array": "NOT_SELECTED",
                "independent_contrast": "OSENSA PRB1000HT (非FBG, CONTRAST_SYSTEM)",
                "v0_2_revoked": "⚠️ Technica T890/T885 已撤销 (REVOKED_UNVERIFIED)",
                "release_status": "NOT_PROCUREMENT_READY",
                "hold_reason": "待FiSens/CALSENS询价完成和原厂确认",
            },
            "ipc": "Advantech UNO-2484G V2 (PDF_VERIFIED)",
            "power_budget_w": ENGINEERING_CALCULATIONS["power_storage"]["power_load_W"],
            "ups_requirement_wh": ENGINEERING_CALCULATIONS["power_storage"]["ups_usable_Wh_30min_at80pct"],
            "evidence_ids": ["[EV-DESIGN-HW-001]"],
        },
        "bom_items": BOM_LAB_TIER + BOM_PILOT_TIER,
        "bom_disclaimer": (
            "⚠️ 全部价格为ENGINEERING_SCENARIO_NO_QUOTE - 预算情景占位，"
            "没有核实原厂售价或正式报价。禁止据此采购或宣称成本竞争力已证实。"
        ),
        "supplier_analysis": [
            {
                "supplier_id": "SUP-LUNA-001",
                "name": "Luna Innovations",
                "country": "USA",
                "products": ["si255解调仪系列"],
                "spec_status": "PDF_VERIFIED",
                "clarifications_needed": [
                    "SDK协议端口和时戳格式",
                    "Linux/ARM支持",
                    "商业分发许可",
                    "宽峰精度验证",
                ],
                "release_status": "HOLD",
                "evidence_ids": ["[EV-SUP-LUNA-001]"],
            },
            # v0.2: FiSens as LAB RFQ PRIORITY
            {
                "supplier_id": "SUP-FISENS-001",
                "name": "FiSens GmbH",
                "country": "Germany",
                "products": ["1550 STD narrow + AC complete factory assembly"],
                "spec_status": "PDF_VERIFIED",
                "v0_2_status": "LAB_RFQ_PRIORITY",
                "clarifications_needed": [
                    "600°C完整成品订货配置",
                    "引纤/过渡/应变自由度",
                    "漂移/寿命数据",
                ],
                "release_status": "RFQ_PRIORITY_NOT_PROCUREMENT_READY",
                "evidence_ids": ["[E17]"],
            },
            # v0.2: CALSENS as second RFQ source
            {
                "supplier_id": "SUP-CALSENS-001",
                "name": "CALSENS",
                "country": "China",
                "products": ["High Temperature FBG Sensor"],
                "spec_status": "PDF_VERIFIED",
                "v0_2_status": "SECOND_RFQ_SOURCE",
                "clarifications_needed": [
                    "完整保护图",
                    "1200°C可用保护类型",
                    "尺寸和封装解耦",
                ],
                "release_status": "RFQ_CANDIDATE_NOT_PROCUREMENT_READY",
                "evidence_ids": ["[E18]"],
                "note": "2nm FWHM不满足16.5nm槽预算",
            },
            # v0.2: Technica REVOKED
            {
                "supplier_id": "SUP-TECHNICA-001-REVOKED",
                "name": "Technica Optical Components",
                "country": "USA(总部)/China(制造)/Singapore(技术)",
                "products": ["T885单点探头", "T890多点阵列"],
                "spec_status": "REVOKED_UNVERIFIED_SEARCH_ONLY",
                "v0_2_status": "REVOKED_FROM_SELECTION",
                "revocation_reason": "PDF未取得，HTML挑战失败，参数UNVERIFIED",
                "release_status": "NOT_SELECTED",
                "evidence_ids": ["[E08]"],
                "limitation": "⚠️ v0.2撤销，仅作RFI线索",
            },
            {
                "supplier_id": "SUP-HBK-001",
                "name": "HBK (Hottinger Brüel & Kjær)",
                "country": "Germany",
                "products": ["FS22SI解调仪"],
                "spec_status": "PDF_VERIFIED",
                "release_status": "HOLD",
                "evidence_ids": ["[EV-SUP-HBK-001]"],
            },
        ],
        "cost_breakdown": {
            "lab_tier": BUDGET_SUMMARY["lab_tier"],
            "pilot_tier": BUDGET_SUMMARY["pilot_tier"],
            "disclaimer": BUDGET_SUMMARY["disclaimer"],
            "evidence_ids": ["[EV-BUDGET-001]"],
        },
        "uncertainty_analysis": {
            "lab_U_k2_C": ENGINEERING_CALCULATIONS["uncertainty_budget"]["lab_U_k2_C"],
            "field_U_k2_C": ENGINEERING_CALCULATIONS["uncertainty_budget"]["field_U_k2_C"],
            "target_C": ENGINEERING_CALCULATIONS["uncertainty_budget"]["target_MPE_C"],
            "status": "NOT_MET",
            "conclusion": ENGINEERING_CALCULATIONS["uncertainty_budget"]["conclusion"],
            "required_action": ENGINEERING_CALCULATIONS["uncertainty_budget"]["required_action"],
            "evidence_ids": ["[EV-CALC-ENG-001]"],
        },
        "telemetry_events": [{
            "event": "stage_2_completed",
            "run_id": run_id,
            "mode": "simulation_with_real_research_data",
            "data_source": "engineering_research_package_v0.1",
            "critical_note": "Field uncertainty 5.73°C > ±5°C target - QA MUST REJECT",
        }],
    }


def _simulation_stage_3_output(run_id: str) -> dict[str, Any]:
    """Generate simulation output for Stage 3."""
    return {
        "current_stage": "stage_3_development",
        "development_status": {
            "hardware": {
                "status": "[SIMULATION] 硬件集成待采购完成",
                "blockers": ["BOM待确认", "供应商待选定"],
            },
            "software": {
                "status": "[SIMULATION] 软件框架已搭建",
                "modules_completed": ["数据采集适配器接口", "合成数据生成器"],
                "modules_pending": ["实际硬件联调", "算法调优"],
            },
        },
        "telemetry_events": [{
            "event": "stage_3_completed",
            "run_id": run_id,
            "mode": "simulation",
        }],
    }


def _simulation_stage_4_output(run_id: str) -> dict[str, Any]:
    """Generate simulation output for Stage 4."""
    return {
        "current_stage": "stage_4_testing",
        "test_results": [
            {
                "test_id": "TEST-UNIT-001",
                "type": "unit_test",
                "name": "数据模型单元测试",
                "status": "passed",
                "evidence_ids": ["[EV-TEST-001]"],
            },
            {
                "test_id": "TEST-SYNTH-001",
                "type": "synthetic_data_test",
                "name": "合成数据风险检测测试",
                "status": "passed",
                "data_source": "synthetic",
                "evidence_ids": ["[EV-SYNTH-TEST-001]"],
            },
            {
                "test_id": "TEST-HW-001",
                "type": "hardware_integration",
                "name": "实际硬件联调测试",
                "status": "pending",
                "reason": "待硬件采购完成",
                "evidence_ids": [],
            },
        ],
        "telemetry_events": [{
            "event": "stage_4_completed",
            "run_id": run_id,
            "mode": "simulation",
        }],
    }


def _simulation_stage_5_output(run_id: str) -> dict[str, Any]:
    """Generate simulation output for Stage 5."""
    return {
        "current_stage": "stage_5_production",
        "production_readiness": {
            "status": "[SIMULATION] 生产准备待硬件验证完成",
            "dfm_review": "pending",
            "pilot_plan": "待定义",
        },
        "training_materials": {
            "installation_guide": "[SIMULATION] 安装指南模板已创建",
            "operator_manual": "[SIMULATION] 操作手册模板已创建",
            "maintenance_guide": "[SIMULATION] 维护指南模板已创建",
        },
        "sales_toolkit": {
            "product_brochure": "[SIMULATION] 产品手册模板",
            "demo_script": "[SIMULATION] 演示脚本模板",
            "battlecard": "[SIMULATION] 竞品对比卡模板",
        },
        "marketing_strategy": {
            "positioning": "[SIMULATION] 定位策略待市场调研完善",
            "channels": ["直销", "系统集成商"],
            "launch_plan": "[SIMULATION] 上市计划待确定",
        },
        "telemetry_events": [{
            "event": "stage_5_completed",
            "run_id": run_id,
            "mode": "simulation",
        }],
    }


def build_boiler_fbg_graph(deps: RuntimeDeps, *, checkpointer: Any | None = None):
    """Build the multi-agent R&D workflow graph.
    
    Architecture: Pipeline + Parallel Hybrid (Chapter 1 + Chapter 3)
    with Reflection (Chapter 4) and HITL gates (Chapter 13)
    """
    builder = StateGraph(WorkflowState)
    
    # Stage 0: Requirements & Market Research
    builder.add_node("stage_0_market_research", partial(node_stage_0_market_research, deps=deps))
    builder.add_node("stage_0_qa_review", partial(node_stage_0_qa_review, deps=deps))
    builder.add_node("stage_0_hitl", partial(node_hitl_gate, deps=deps, gate_type="requirement_approval"))
    
    # Stage 1: Concept Design
    builder.add_node("stage_1_concept", partial(node_stage_1_concept_design, deps=deps))
    builder.add_node("stage_1_qa_review", partial(node_stage_1_qa_review, deps=deps))
    builder.add_node("stage_1_hitl", partial(node_hitl_gate, deps=deps, gate_type="design_approval"))
    
    # Stage 2: Detailed Design
    builder.add_node("stage_2_detailed", partial(node_stage_2_detailed_design, deps=deps))
    builder.add_node("stage_2_qa_review", partial(node_stage_2_qa_review, deps=deps))
    builder.add_node("stage_2_hitl", partial(node_hitl_gate, deps=deps, gate_type="procurement_approval"))
    
    # Stage 3: Development
    builder.add_node("stage_3_development", partial(node_stage_3_development, deps=deps))
    
    # Stage 4: Testing
    builder.add_node("stage_4_testing", partial(node_stage_4_testing, deps=deps))
    builder.add_node("stage_4_hitl", partial(node_hitl_gate, deps=deps, gate_type="test_approval"))
    
    # Stage 5: Production
    builder.add_node("stage_5_production", partial(node_stage_5_production, deps=deps))
    
    # Final Report
    builder.add_node("final_report", partial(node_final_report, deps=deps))
    
    # Define edges (Chapter 1: Sequential Handoffs)
    builder.add_edge(START, "stage_0_market_research")
    builder.add_edge("stage_0_market_research", "stage_0_qa_review")
    
    # Conditional routing after QA (Chapter 4: Reflection)
    builder.add_conditional_edges(
        "stage_0_qa_review",
        partial(route_after_qa, deps=deps, stage="stage_0_requirements"),
        {
            "next": "stage_0_hitl",
            "hitl": "stage_0_hitl",
            "rewrite": "stage_0_market_research",
        },
    )
    builder.add_edge("stage_0_hitl", "stage_1_concept")
    
    builder.add_edge("stage_1_concept", "stage_1_qa_review")
    builder.add_conditional_edges(
        "stage_1_qa_review",
        partial(route_after_qa, deps=deps, stage="stage_1_concept"),
        {
            "next": "stage_1_hitl",
            "hitl": "stage_1_hitl",
            "rewrite": "stage_1_concept",
        },
    )
    builder.add_edge("stage_1_hitl", "stage_2_detailed")
    
    builder.add_edge("stage_2_detailed", "stage_2_qa_review")
    builder.add_conditional_edges(
        "stage_2_qa_review",
        partial(route_after_qa, deps=deps, stage="stage_2_detailed_design"),
        {
            "next": "stage_2_hitl",
            "hitl": "stage_2_hitl",
            "rewrite": "stage_2_detailed",
        },
    )
    builder.add_edge("stage_2_hitl", "stage_3_development")
    
    builder.add_edge("stage_3_development", "stage_4_testing")
    builder.add_edge("stage_4_testing", "stage_4_hitl")
    builder.add_edge("stage_4_hitl", "stage_5_production")
    
    builder.add_edge("stage_5_production", "final_report")
    builder.add_edge("final_report", END)
    
    return builder.compile(checkpointer=checkpointer or MemorySaver())


def build_langgraph_app():
    """Factory entrypoint for LangGraph."""
    settings = WorkflowSettings.load()
    ledger = CostLedger()
    deps = RuntimeDeps(
        settings=settings,
        ledger=ledger,
    )
    return build_boiler_fbg_graph(deps)
