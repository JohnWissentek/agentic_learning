"""Live Agent Implementations using Real LLM Inference.

Each agent uses actual LLM calls with v0.2 research data as context.
Outputs are marked as "研发工作流演示，小模型产物未经工程验证".

Reference: Chapter 7 (P113-131) - Multi-Agent Collaboration
- Chapter 4 (P67-82): Reflection Pattern - QA findings drive PM task revision
- Chapter 13 (P201-218): Human-in-the-Loop - guardrails on QA gate decisions
"""

from __future__ import annotations

import json
from typing import Any

from boiler_fbg_workflow.llm_provider import (
    LLMProvider,
    LLMCallTrace,
    LLMCallRegistry,
)
from boiler_fbg_workflow.research_data import (
    RESEARCH_VERSION,
    BOOK_REFERENCE,
    ENGINEERING_CALCULATIONS,
    VENDOR_SPECS,
    RECOMMENDED_SCENARIO,
    BUDGET_SUMMARY,
    RISK_REGISTER,
    EVIDENCE_LEDGER,
    get_qa_gate_decision,
)
from boiler_fbg_workflow.qa_findings import (
    QA_REVIEW_METADATA,
    QA_FINDINGS_HIGH,
    QA_FINDINGS_MEDIUM,
    QA_FINDINGS_ALL,
    get_findings_summary,
    get_findings_for_reflection_prompt,
    get_pm_task_revision_input,
)

# Disclaimer for all live outputs
LIVE_OUTPUT_DISCLAIMER = (
    "⚠️ 研发工作流演示：本输出由Qwen2.5-0.5B-Instruct小模型生成，"
    "未经工程验证，不代表已审查研究基线的专业质量。"
    "所有HOLD项继续保留，不可被模型建议覆盖。"
)


def _build_system_prompt(role: str, role_description: str) -> str:
    """Build system prompt with research context."""
    return f"""你是燃煤锅炉水冷壁光纤测温产品研发团队的{role}。

角色职责：{role_description}

研究数据版本：{RESEARCH_VERSION}
书籍参考：《{BOOK_REFERENCE['title']}》({BOOK_REFERENCE['author']}, {BOOK_REFERENCE['publisher']} {BOOK_REFERENCE['year']})

关键约束：
1. 所有分析必须基于已提供的v0.2研究数据
2. 不可编造事实或数据
3. HOLD状态项不可被改为PASS或已验证
4. 采购状态为NOT_PROCUREMENT_READY
5. 现场传感器为NOT_SELECTED
6. Technica T885/T890已撤销(REVOKED)
7. 不确定度U(k=2)=5.728°C，保护带判据|e|+U≤5°C无法接受
8. 链路余量UNKNOWN

请用简洁专业的中文回答，控制在200字以内。"""


def _extract_json_from_response(response: str) -> dict[str, Any] | None:
    """Try to extract JSON from response."""
    try:
        # Try direct parse
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON block
    import re
    json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    return None


class LivePMAgent:
    """Project Manager agent - coordinates team and synthesizes results."""
    
    ROLE = "PM"
    ROLE_DESC = "项目经理，负责协调团队、把控进度、综合各方输出形成决策建议"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def analyze_stage_0(self) -> dict[str, Any]:
        """PM analysis for Stage 0 - Requirements."""
        messages = [
            {"role": "system", "content": _build_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于以下研究数据，作为PM简要总结Stage 0需求分析的关键发现：

推荐场景：
{json.dumps(RECOMMENDED_SCENARIO, ensure_ascii=False, indent=2)}

主要风险：
{json.dumps(RISK_REGISTER[:3], ensure_ascii=False, indent=2)}

请回答：
1. 目标应用场景（一句话）
2. 主要技术挑战（2-3点）
3. 当前阻塞项（列出）
4. 下一步建议（2点）

用JSON格式回答，包含target_scenario, challenges, blockers, recommendations字段。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=300,
            temperature=0.3,
            role=self.ROLE,
            stage="stage_0_requirements",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        trace.parsed_output = parsed or {}
        trace.parse_success = parsed is not None
        
        return {
            "role": self.ROLE,
            "stage": "stage_0_requirements",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }
    
    def synthesize_team_outputs(
        self,
        opt_output: dict[str, Any],
        scm_output: dict[str, Any],
    ) -> dict[str, Any]:
        """PM synthesizes parallel team outputs."""
        messages = [
            {"role": "system", "content": _build_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""作为PM，综合以下团队成员的输出：

光学/热工工程师(OPT)输出：
{json.dumps(opt_output.get('parsed') or opt_output.get('raw_response', ''), ensure_ascii=False)[:500]}

供应链(SCM)输出：
{json.dumps(scm_output.get('parsed') or scm_output.get('raw_response', ''), ensure_ascii=False)[:500]}

请综合分析并给出：
1. 技术可行性评估（一句话）
2. 供应链风险等级（高/中/低）
3. 综合建议（2点）
4. 是否可进入下一阶段（是/否，理由）

用JSON格式回答，包含tech_feasibility, supply_risk, recommendations, proceed_to_next字段。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=300,
            temperature=0.3,
            role=self.ROLE,
            stage="synthesis",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        trace.parsed_output = parsed or {}
        trace.parse_success = parsed is not None
        
        return {
            "role": self.ROLE,
            "stage": "synthesis",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "input_opt": opt_output.get("raw_response", "")[:200],
            "input_scm": scm_output.get("raw_response", "")[:200],
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }
    
    def revise_tasks_from_qa_feedback(
        self,
        qa_review_output: dict[str, Any],
    ) -> dict[str, Any]:
        """PM revises task list based on QA findings feedback.
        
        This implements the Reflection Pattern (Ch4, P67-82):
        QA findings → PM task revision → Updated action plan
        
        Reference: Chapter 4 - Reflection Pattern
        """
        # Get structured QA feedback
        pm_revision_input = get_pm_task_revision_input()
        qa_parsed = qa_review_output.get("parsed") or {}
        
        messages = [
            {"role": "system", "content": _build_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""作为PM，根据独立QA审查反馈修订任务清单。

## QA审查结果
- 门禁状态: {qa_review_output.get('gate_status', 'BLOCKED')}
- HIGH严重性发现: {qa_review_output.get('findings_count', {}).get('high', 5)}项
- MEDIUM严重性发现: {qa_review_output.get('findings_count', {}).get('medium', 5)}项
- 阻塞性发现: {qa_review_output.get('blocking_finding_ids', [])}

## QA分析内容
{json.dumps(qa_parsed, ensure_ascii=False)[:800]}

## 必须添加的任务（来自QA findings）
{json.dumps(pm_revision_input['high_priority_actions'], ensure_ascii=False, indent=2)}

## 需要实现的测试
{pm_revision_input['tests_to_implement']}

请基于QA反馈制定修订后的任务清单：

1. 针对QA-01（老化复验）: 添加什么具体任务？
2. 针对QA-03（8TC→64点）: 如何处理NOT_COVERED的56点？
3. 针对QA-05（FWHM局限）: 如何定义谱罩和固件阈值？
4. 针对QA-08（百分比可用率）: 如何定义最长连续盲区上限？
5. 优先级排序（哪些任务先做）
6. 责任人分配建议

用JSON格式回答，包含以下字段：
- revised_task_list: 修订后的任务清单（数组）
- qa01_aging_task: QA-01老化复验具体任务
- qa03_coverage_task: QA-03覆盖缺口处理任务
- qa05_spectral_task: QA-05谱罩定义任务
- qa08_availability_task: QA-08盲区上限任务
- priority_order: 优先级排序
- owner_assignments: 责任人分配"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=700,
            temperature=0.3,
            role=self.ROLE,
            stage="task_revision_from_qa",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        trace.parsed_output = parsed or {}
        trace.parse_success = parsed is not None
        
        return {
            "role": self.ROLE,
            "stage": "task_revision_from_qa",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "qa_input": {
                "gate_status": qa_review_output.get("gate_status"),
                "findings_count": qa_review_output.get("findings_count"),
                "blocking_ids": qa_review_output.get("blocking_finding_ids"),
            },
            "required_actions": pm_revision_input["high_priority_actions"],
            "required_tests": pm_revision_input["tests_to_implement"],
            "reflection_pattern": {
                "chapter": "Chapter 4 (P67-82)",
                "pattern": "Reflection Pattern",
                "flow": "QA findings → PM analysis → Task revision",
            },
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
            "pm_note": (
                "本任务修订基于真实独立QA发现的反思循环。"
                "QA门禁为BLOCKED，PM需完成所有HIGH优先级任务后才能重新提交评审。"
            ),
        }


class LiveOPTAgent:
    """Optical/Thermal Engineer agent - technical analysis."""
    
    ROLE = "OPT"
    ROLE_DESC = "光学/热工工程师，负责FBG传感器技术评估、波长预算、不确定度分析"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def analyze_technical_feasibility(self) -> dict[str, Any]:
        """OPT technical feasibility analysis."""
        wavelength = ENGINEERING_CALCULATIONS.get("wavelength_budget", {})
        uncertainty = ENGINEERING_CALCULATIONS.get("uncertainty_budget", {})
        
        messages = [
            {"role": "system", "content": _build_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于以下工程计算数据，分析技术可行性：

波长预算：
- 起点: {wavelength.get('lambda_start_nm', 1485)}nm
- 槽宽: {wavelength.get('slot_nm', 16.5)}nm
- 600°C热漂移: {wavelength.get('normal600_thermal_shift_nm', 10.35)}nm

不确定度预算：
- 实验室U(k=2): {uncertainty.get('lab_U_k2_C', 2.795)}°C
- 现场U(k=2): {uncertainty.get('field_U_k2_C', 5.728)}°C
- 目标MPE: ±{uncertainty.get('target_MPE_C', 5)}°C
- 保护带判据: {uncertainty.get('conformity_decision_rule', '|e|+U≤MPE')}

传感器选型状态：
- FiSens: LAB_RFQ_PRIORITY
- CALSENS: SECOND_RFQ_SOURCE
- Technica: REVOKED

请分析：
1. 波长预算是否满足8点/串要求
2. 不确定度是否满足保护带验收
3. 主要技术风险
4. 改进建议

用JSON格式回答。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=350,
            temperature=0.3,
            role=self.ROLE,
            stage="technical_analysis",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        trace.parsed_output = parsed or {}
        trace.parse_success = parsed is not None
        
        return {
            "role": self.ROLE,
            "stage": "technical_analysis",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }


class LiveSCMAgent:
    """Supply Chain agent - procurement and vendor analysis."""
    
    ROLE = "SCM"
    ROLE_DESC = "供应链经理，负责供应商评估、采购风险分析、BOM管理"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def analyze_supply_chain(self) -> dict[str, Any]:
        """SCM supply chain analysis."""
        vendors = {k: {
            "vendor": v.get("vendor", ""),
            "source_status": v.get("source_status", ""),
            "release_status": v.get("release_status", ""),
            "v0_2_status": v.get("v0_2_status", ""),
        } for k, v in VENDOR_SPECS.items()}
        
        messages = [
            {"role": "system", "content": _build_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于以下供应商状态，分析供应链风险：

供应商状态：
{json.dumps(vendors, ensure_ascii=False, indent=2)}

预算状态：
- 实验室: {BUDGET_SUMMARY['lab_tier']['total_low_wan']}-{BUDGET_SUMMARY['lab_tier']['total_high_wan']}万元
- 试点: {BUDGET_SUMMARY['pilot_tier']['total_low_wan']}-{BUDGET_SUMMARY['pilot_tier']['total_high_wan']}万元
- 注意: {BUDGET_SUMMARY['disclaimer'][:100]}

请分析：
1. 当前可用供应商数量
2. 主要供应风险（2-3点）
3. 采购就绪状态（是/否）
4. 建议的询价优先级

注意：不可将任何HOLD状态改为已验证，不可声称采购已就绪。

用JSON格式回答，包含available_vendors, supply_risks, procurement_ready, rfq_priority字段。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=350,
            temperature=0.3,
            role=self.ROLE,
            stage="supply_chain_analysis",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        trace.parsed_output = parsed or {}
        trace.parse_success = parsed is not None
        
        return {
            "role": self.ROLE,
            "stage": "supply_chain_analysis",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }


class LiveQAAgent:
    """Quality Assurance agent - independent review with REAL findings.
    
    CRITICAL: QA gate decisions are DETERMINISTIC and cannot be overridden by model.
    The model analyzes real QA findings (5 HIGH, 5 MEDIUM) and provides commentary.
    
    Reference: Chapter 4 (P67-82) - Reflection Pattern
    """
    
    ROLE = "QA"
    ROLE_DESC = "独立质量评审员，基于真实QA findings进行审查、分析和反馈"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def review_with_real_findings(
        self,
        stage: str,
        pm_synthesis: dict[str, Any],
    ) -> dict[str, Any]:
        """QA reviews using REAL independent QA findings.
        
        Uses actual findings from independent review (5 HIGH, 5 MEDIUM).
        Gate decision is DETERMINISTIC - model cannot override.
        """
        # Get deterministic gate decision
        deterministic_decision = get_qa_gate_decision()
        
        # Get real findings summary
        findings_summary = get_findings_summary()
        findings_prompt = get_findings_for_reflection_prompt()
        
        messages = [
            {"role": "system", "content": _build_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""作为独立QA，基于以下真实的独立评审发现进行分析：

{findings_prompt[:3000]}

PM先前综合输出：
{json.dumps(pm_synthesis.get('parsed') or pm_synthesis.get('raw_response', ''), ensure_ascii=False)[:400]}

基于真实QA发现（{findings_summary['high_severity_count']}个HIGH，{findings_summary['medium_severity_count']}个MEDIUM），请分析：

1. TOP 5最关键问题的具体影响（QA-01至QA-05）
2. 针对QA-08（百分比可用率不足）：为什么99.5%不够？最长连续盲区的风险是什么？
3. 针对QA-03（8TC推64点）：为什么8个对照点无法验证64点精度？
4. 针对QA-05（FWHM不是全谱边界）：为什么FWHM不能保证峰检测正确？
5. 针对QA-01（老化后复验）：为什么漂移通过不等于全链MPE通过？
6. 建议PM修订的任务清单

注意：QA门禁决策为{deterministic_decision['gate_status']}（确定性规则）。你的分析用于帮助PM修订任务，不能改变门禁决策。

用JSON格式回答，包含以下字段：
- top5_impact_analysis: 对TOP5问题的影响分析
- qa08_blind_window_risk: QA-08百分比不足的具体风险
- qa03_coverage_gap: QA-03的8→64覆盖缺口分析
- qa05_fwhm_limitation: QA-05 FWHM局限性分析
- qa01_aging_verification: QA-01老化复验要求
- pm_task_revisions: 建议PM添加的任务列表"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=600,
            temperature=0.3,
            role=self.ROLE,
            stage=f"qa_review_real_findings_{stage}",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        trace.parsed_output = parsed or {}
        trace.parse_success = parsed is not None
        
        return {
            "role": self.ROLE,
            "stage": f"qa_review_real_findings_{stage}",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            # Include real findings metadata
            "real_findings_source": QA_REVIEW_METADATA["review_id"],
            "findings_count": {
                "high": findings_summary["high_severity_count"],
                "medium": findings_summary["medium_severity_count"],
                "blocking": findings_summary["blocking_findings_count"],
            },
            "blocking_finding_ids": findings_summary["blocking_finding_ids"],
            # DETERMINISTIC gate decision - cannot be overridden
            "gate_decision": deterministic_decision,
            "gate_status": deterministic_decision["gate_status"],
            "gate_is_deterministic": True,
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
            "qa_note": (
                "本QA分析基于真实独立评审findings（5 HIGH, 5 MEDIUM）。"
                "门禁决策为确定性规则BLOCKED，不可被模型输出覆盖。"
            ),
        }
    
    def review_stage_output(
        self,
        stage: str,
        pm_synthesis: dict[str, Any],
    ) -> dict[str, Any]:
        """Legacy QA review - redirects to real findings review."""
        return self.review_with_real_findings(stage, pm_synthesis)


class LiveHWAgent:
    """Hardware Integrator agent."""
    
    ROLE = "HW"
    ROLE_DESC = "硬件集成工程师，负责系统架构、接口设计、硬件选型"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def analyze_hardware_design(self) -> dict[str, Any]:
        """HW hardware design analysis."""
        optical_power = ENGINEERING_CALCULATIONS.get("optical_power_budget", {})
        
        messages = [
            {"role": "system", "content": _build_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于以下硬件设计数据，分析系统架构：

光功率预算：
- 单程损耗: {optical_power.get('one_way_loss_dB', 6.64)}dB
- 回波损耗: {optical_power.get('return_loss_at20percent_dB', 20.27)}dB
- 链路余量: {optical_power.get('link_margin_status', 'UNKNOWN')}

解调仪选型：
- Luna si255: PDF_VERIFIED, HOLD
- HBK FS22SI: PDF_VERIFIED, HOLD

请分析：
1. 系统拓扑建议
2. 接口要求
3. 硬件风险（2点）
4. 集成建议

用JSON格式回答。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=300,
            temperature=0.3,
            role=self.ROLE,
            stage="hardware_design",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        trace.parsed_output = parsed or {}
        trace.parse_success = parsed is not None
        
        return {
            "role": self.ROLE,
            "stage": "hardware_design",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }


class LiveSWAgent:
    """Software Developer agent."""
    
    ROLE = "SW"
    ROLE_DESC = "软件开发工程师，负责数据采集、算法、HMI、AI集成"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def analyze_software_architecture(self) -> dict[str, Any]:
        """SW software architecture analysis."""
        messages = [
            {"role": "system", "content": _build_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": """基于锅炉水冷壁光纤测温系统需求，分析软件架构：

关键约束：
1. AI仅解释趋势、给建议与证据，不替代运行规程与保护
2. LLM不在采集/报警关键路径
3. 原始波长/报警不可由LLM改写
4. 无论模型离线/失效，采集与确定性报警继续

请分析：
1. 推荐的模块划分
2. 数据流设计
3. AI集成方式
4. 安全隔离措施

用JSON格式回答。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=300,
            temperature=0.3,
            role=self.ROLE,
            stage="software_architecture",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        trace.parsed_output = parsed or {}
        trace.parse_success = parsed is not None
        
        return {
            "role": self.ROLE,
            "stage": "software_architecture",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }


def run_live_workflow_demo(
    provider: LLMProvider,
    output_dir: str = "./outputs/live_run",
    include_reflection_loop: bool = True,
) -> dict[str, Any]:
    """Run live workflow demonstration with real LLM inference.
    
    Flow (with reflection loop):
    PM → (OPT + SCM + HW + SW parallel) → PM synthesis 
    → QA review with REAL findings (5 HIGH, 5 MEDIUM)
    → PM task revision (Reflection Pattern)
    
    Reference:
    - Chapter 4 (P67-82): Reflection Pattern
    - Chapter 7 (P113-131): Multi-Agent Collaboration
    - Chapter 13 (P201-218): Human-in-the-Loop
    
    Returns complete execution trace.
    """
    import os
    from pathlib import Path
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    registry = LLMCallRegistry()
    
    # Create agents
    pm = LivePMAgent(provider, registry)
    opt = LiveOPTAgent(provider, registry)
    scm = LiveSCMAgent(provider, registry)
    qa = LiveQAAgent(provider, registry)
    hw = LiveHWAgent(provider, registry)
    sw = LiveSWAgent(provider, registry)
    
    results = {
        "run_id": f"LIVE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "provider": provider.provider_type.value,
        "model_id": provider.model_id,
        "model_revision": provider.model_revision,
        "model_license": provider.model_license,
        "research_version": RESEARCH_VERSION,
        "qa_findings_source": QA_REVIEW_METADATA["review_id"],
        "workflow_patterns": {
            "reflection": "Chapter 4 (P67-82) - QA findings → PM task revision",
            "multi_agent": "Chapter 7 (P113-131) - 12 role collaboration",
            "hitl": "Chapter 13 (P201-218) - Deterministic QA gates",
        },
        "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        "stages": {},
    }
    
    # Stage 1: PM initial analysis
    print("  [1/9] PM: Stage 0 需求分析...")
    results["stages"]["pm_stage_0"] = pm.analyze_stage_0()
    
    # Stage 2: Parallel technical analysis (OPT + SCM)
    print("  [2/9] OPT: 技术可行性分析...")
    opt_result = opt.analyze_technical_feasibility()
    results["stages"]["opt_technical"] = opt_result
    
    print("  [3/9] SCM: 供应链分析...")
    scm_result = scm.analyze_supply_chain()
    results["stages"]["scm_supply"] = scm_result
    
    # Stage 3: Additional parallel (HW + SW)
    print("  [4/9] HW: 硬件设计分析...")
    results["stages"]["hw_design"] = hw.analyze_hardware_design()
    
    print("  [5/9] SW: 软件架构分析...")
    results["stages"]["sw_architecture"] = sw.analyze_software_architecture()
    
    # Stage 4: PM synthesizes parallel outputs
    print("  [6/9] PM: 综合团队输出...")
    pm_synthesis = pm.synthesize_team_outputs(opt_result, scm_result)
    results["stages"]["pm_synthesis"] = pm_synthesis
    
    # Stage 5: QA independent review with REAL FINDINGS
    print("  [7/9] QA: 基于真实独立评审findings进行审查 (5 HIGH, 5 MEDIUM)...")
    qa_result = qa.review_with_real_findings("stage_2", pm_synthesis)
    results["stages"]["qa_review_real_findings"] = qa_result
    
    # Stage 6: Reflection Loop - PM task revision based on QA feedback
    if include_reflection_loop:
        print("  [8/9] PM: 基于QA反馈修订任务清单 (Reflection Pattern)...")
        pm_revision = pm.revise_tasks_from_qa_feedback(qa_result)
        results["stages"]["pm_task_revision"] = pm_revision
        results["reflection_loop_completed"] = True
    else:
        results["reflection_loop_completed"] = False
    
    # Summary
    print("  [9/9] 生成执行摘要...")
    results["call_summary"] = registry.get_summary()
    results["final_gate_status"] = qa_result["gate_status"]
    results["gate_is_deterministic"] = True
    
    # Real findings summary
    findings_summary = get_findings_summary()
    results["qa_findings_summary"] = {
        "source": findings_summary["review_id"],
        "total": findings_summary["total_findings"],
        "high": findings_summary["high_severity_count"],
        "medium": findings_summary["medium_severity_count"],
        "blocking": findings_summary["blocking_findings_count"],
        "blocking_ids": findings_summary["blocking_finding_ids"],
        "top5": findings_summary["top5_priority"],
        "tests_to_add": findings_summary["tests_to_add"],
    }
    
    # Save trace
    trace_path = os.path.join(output_dir, f"live_trace_{results['run_id']}.json")
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Save raw calls
    calls_path = os.path.join(output_dir, f"llm_calls_{results['run_id']}.json")
    registry.save(calls_path)
    
    results["trace_path"] = trace_path
    results["calls_path"] = calls_path
    
    return results


# Import datetime for use
from datetime import datetime
