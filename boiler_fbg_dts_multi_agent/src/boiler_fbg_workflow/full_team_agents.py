"""Full 12-Role Team Agent Implementations.

Implements all 12 team roles for multi-agent R&D workflow:
PM, MKT, OPT, HW, SW, SCM, QA, MFG, TRN, FIN, SLS, STR

Each agent uses real LLM inference with v0.3 research data.
Outputs are validated and marked appropriately for quality.

Reference: Chapter 7 (P113-131) - Multi-Agent Collaboration
"""

from __future__ import annotations
import json
import hashlib
from datetime import datetime
from typing import Any, Optional

from boiler_fbg_workflow.llm_provider import (
    LLMProvider,
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
    get_qa_gate_decision,
)
from boiler_fbg_workflow.qa_findings import (
    QA_REVIEW_METADATA,
    QA_FINDINGS_HIGH,
    QA_FINDINGS_MEDIUM,
    get_findings_summary,
    get_findings_for_reflection_prompt,
    get_pm_task_revision_input,
)
from boiler_fbg_workflow.model_manifest import (
    MODEL_MANIFEST,
    V03_BASELINE,
    get_model_manifest,
)


# Quality markers for output validation
class OutputQuality:
    VALID = "VALID"
    TRUNCATED = "TRUNCATED"
    INVALID_FORMAT = "INVALID_FORMAT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    MODEL_LIMITATION = "MODEL_LIMITATION"
    PARSE_FAILED = "PARSE_FAILED"


LIVE_OUTPUT_DISCLAIMER = (
    "⚠️ 研发工作流演示：本输出由Qwen2.5-0.5B-Instruct小模型生成，"
    "未经工程验证，不代表已审查研究基线的专业质量。"
    "模型执行成功≠专业产物合格。所有HOLD项继续保留。"
)

V031_CONTEXT = f"""
研究数据版本：v0.3.1 (SHA256: {V03_BASELINE['zip_sha256'][:16]}...)
状态：
- 10项文档纠正已实施，独立复查10/10已接受
- 接受范围：DOCUMENT_CORRECTION_ONLY
- 工程验证10项仍OPEN，全部实体试验NOT_RUN
- 采购NOT_READY，现场阵列NOT_SELECTED
- 产品交付NOT_READY，竞争力未证明
- 文档纠正不能自动关闭实体门禁
"""

V03_CONTEXT = V031_CONTEXT  # Alias


def _build_v03_system_prompt(role: str, role_description: str) -> str:
    """Build system prompt with v0.3 research context."""
    return f"""你是燃煤锅炉水冷壁光纤测温产品研发团队的{role}。

角色职责：{role_description}

{V03_CONTEXT}

书籍参考：《{BOOK_REFERENCE['title']}》({BOOK_REFERENCE['author']}, {BOOK_REFERENCE['publisher']} {BOOK_REFERENCE['year']})

关键约束：
1. 所有分析必须基于v0.3研究数据
2. 文档纠正IMPLEMENTED ≠ 工程验证PASS
3. 10项独立复查均NOT_ACCEPTED
4. 不可将HOLD改为PASS
5. 不可声称采购就绪或产品可交付

请用简洁专业的中文回答，控制在200字以内。"""


def _extract_json_from_response(response: str) -> Optional[dict[str, Any]]:
    """Try to extract JSON from response."""
    import re
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    
    json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return None


def _validate_output(response: str, parsed: Optional[dict]) -> dict[str, Any]:
    """Validate output quality and return quality markers."""
    quality = OutputQuality.VALID
    issues = []
    
    if not response or len(response.strip()) < 10:
        quality = OutputQuality.INVALID_FORMAT
        issues.append("输出为空或过短")
    
    if len(response) > 2000 and not response.rstrip().endswith(('```', '}', '。', '！', '?')):
        quality = OutputQuality.TRUNCATED
        issues.append("输出可能被截断")
    
    if parsed is None:
        if quality == OutputQuality.VALID:
            quality = OutputQuality.PARSE_FAILED
        issues.append("JSON解析失败")
    
    if any(kw in response for kw in ['...', '等等', '以此类推']):
        if quality == OutputQuality.VALID:
            quality = OutputQuality.NEEDS_REVIEW
        issues.append("输出包含省略内容")
    
    return {
        "quality": quality,
        "issues": issues,
        "is_valid": quality == OutputQuality.VALID,
        "needs_human_review": quality in [OutputQuality.NEEDS_REVIEW, OutputQuality.TRUNCATED, OutputQuality.PARSE_FAILED],
    }


class LiveMKTAgent:
    """Market Research agent."""
    ROLE = "MKT"
    ROLE_DESC = "市场研究员，负责煤电行业趋势、竞品分析、客户需求调研"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def analyze_market(self) -> dict[str, Any]:
        """MKT market analysis based on v0.3 data."""
        messages = [
            {"role": "system", "content": _build_v03_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于v0.3研究数据分析市场状况：

目标场景：{RECOMMENDED_SCENARIO['target_boiler']}
点数：{RECOMMENDED_SCENARIO['points']}
技术路线：{RECOMMENDED_SCENARIO['tech_route']}

已知市场证据：
- 国能CEZB260106803是联箱FBG招标，非水冷壁（不可移植业绩）
- 准智水冷壁FBG营销存在但无独立验收证据
- 客户支付意愿和成本竞争力UNVERIFIED

请分析：
1. 目标市场容量评估（保守/无数据则标UNKNOWN）
2. 竞品状态（已知vs未知）
3. 客户痛点（2-3点）
4. 市场进入风险

用JSON格式回答，包含market_size, competitors, pain_points, entry_risks字段。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=350,
            temperature=0.3,
            role=self.ROLE,
            stage="market_analysis",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        quality = _validate_output(trace.response, parsed)
        
        return {
            "role": self.ROLE,
            "stage": "market_analysis",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "output_quality": quality,
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }


class LiveOPTAgent:
    """Optical/Thermal Engineer agent."""
    ROLE = "OPT"
    ROLE_DESC = "光学/热工工程师，负责FBG传感器技术评估、波长预算、不确定度分析"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def analyze_technical_feasibility(self) -> dict[str, Any]:
        """OPT technical feasibility analysis with v0.3 QA responses."""
        wavelength = ENGINEERING_CALCULATIONS.get("wavelength_budget", {})
        uncertainty = ENGINEERING_CALCULATIONS.get("uncertainty_budget", {})
        
        # Include QA-05 FWHM finding
        qa05 = next((f for f in QA_FINDINGS_HIGH if f["id"] == "QA-05"), {})
        
        messages = [
            {"role": "system", "content": _build_v03_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于v0.3数据和QA findings分析技术可行性：

波长预算：
- 起点: {wavelength.get('lambda_start_nm', 1485)}nm
- 槽宽: {wavelength.get('slot_nm', 16.5)}nm
- FWHM: {wavelength.get('FWHM_nm', 0.8)}nm

QA-05发现：FWHM不是全谱边界保证
- 问题：{qa05.get('problem', '')[:150]}...
- v0.3响应：FWHM降为近似主峰运动宽度非全谱罩

不确定度预算：
- 现场U(k=2): {uncertainty.get('field_U_k2_C', 5.728)}°C
- 目标MPE: ±{uncertainty.get('target_MPE_C', 5)}°C
- v0.3状态：accuracy NOT_PROVEN

请分析：
1. FWHM vs 全谱罩的区别
2. 波长预算是否满足8点/串
3. 不确定度是否满足保护带（注意：文档纠正≠验证通过）
4. OPT角色需完成的验证任务

用JSON格式回答。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=400,
            temperature=0.3,
            role=self.ROLE,
            stage="technical_analysis",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        quality = _validate_output(trace.response, parsed)
        
        return {
            "role": self.ROLE,
            "stage": "technical_analysis",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "output_quality": quality,
            "v03_qa05_addressed": True,
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }


class LiveHWAgent:
    """Hardware Integrator agent."""
    ROLE = "HW"
    ROLE_DESC = "硬件集成工程师，负责系统架构、接口设计、硬件选型"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def analyze_hardware_design(self) -> dict[str, Any]:
        """HW hardware design analysis with v0.3 QA responses."""
        optical_power = ENGINEERING_CALCULATIONS.get("optical_power_budget", {})
        
        # Include QA-04 mechanical finding
        qa04 = next((f for f in QA_FINDINGS_HIGH if f["id"] == "QA-04"), {})
        
        messages = [
            {"role": "system", "content": _build_v03_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于v0.3数据和QA findings分析硬件设计：

光功率预算：
- 单程损耗: {optical_power.get('one_way_loss_dB', 6.64)}dB
- 链路余量: {optical_power.get('link_margin_status', 'UNKNOWN')}

QA-04发现：夹具热胀释放无设计载荷
- 问题：{qa04.get('problem', '')[:150]}...
- v0.3响应：ΔL积分公式/自由行程/载荷窗口已补，但±100με仅假设

解调仪状态：
- Luna si255: HOLD (SDK/商业许可待确认)
- HBK FS22SI: HOLD (固件版本待确认)

请分析：
1. 机械热胀设计要点
2. 链路余量UNKNOWN的影响
3. 解调仪集成风险
4. HW角色需完成的验证任务

用JSON格式回答。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=350,
            temperature=0.3,
            role=self.ROLE,
            stage="hardware_design",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        quality = _validate_output(trace.response, parsed)
        
        return {
            "role": self.ROLE,
            "stage": "hardware_design",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "output_quality": quality,
            "v03_qa04_addressed": True,
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
        """SW software architecture analysis with v0.3 QA responses."""
        # Include QA-08 availability finding
        qa08 = next((f for f in QA_FINDINGS_MEDIUM if f["id"] == "QA-08"), {})
        
        messages = [
            {"role": "system", "content": _build_v03_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于v0.3数据和QA findings分析软件架构：

QA-08发现：百分比可用率不足
- 问题：{qa08.get('problem', '')[:150]}...
- v0.3响应：增加逐点连续盲区10s/重连30s/重启120s等proposal

v0.3可用率提案：
- FAT: 99.5%，最长盲区10s
- SAT: 99.0%，重连30s，重启120s
- 状态：PROPOSAL未批准

关键约束：
1. AI仅解释趋势/给建议，不替代运行规程
2. LLM不在采集/报警关键路径
3. 原始波长/报警不可由LLM改写

请分析：
1. 如何实现最长盲区统计（而非仅百分比）
2. 数据流设计要点
3. AI集成安全隔离
4. SW角色需实现的功能

用JSON格式回答。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=350,
            temperature=0.3,
            role=self.ROLE,
            stage="software_architecture",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        quality = _validate_output(trace.response, parsed)
        
        return {
            "role": self.ROLE,
            "stage": "software_architecture",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "output_quality": quality,
            "v03_qa08_addressed": True,
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }


class LiveSCMAgent:
    """Supply Chain Manager agent."""
    ROLE = "SCM"
    ROLE_DESC = "供应链经理，负责供应商评估、采购风险分析、BOM管理"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def analyze_supply_chain(self) -> dict[str, Any]:
        """SCM supply chain analysis with v0.3 status."""
        vendors = {k: {
            "vendor": v.get("vendor", ""),
            "v0_2_status": v.get("v0_2_status", ""),
            "release_status": v.get("release_status", ""),
        } for k, v in VENDOR_SPECS.items() if "technica" not in k.lower()}
        
        messages = [
            {"role": "system", "content": _build_v03_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于v0.3数据分析供应链状况：

供应商状态：
{json.dumps(vendors, ensure_ascii=False, indent=2)[:500]}

v0.3采购状态：
- 采购就绪：NOT_READY
- 现场阵列：NOT_SELECTED
- Technica：已撤销（v0.2）
- 所有价格：ENGINEERING_SCENARIO_NO_QUOTE

资金边界（v0.3新增）：
- A0/A1/A2/B32/B64总额：全部UNKNOWN
- 未知成本不得填0

请分析：
1. 可用供应商评估
2. 采购阻塞项（具体列出）
3. 资金不确定性风险
4. SCM角色待办任务

注意：不可声称采购已就绪。

用JSON格式回答。"""}
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
        quality = _validate_output(trace.response, parsed)
        
        return {
            "role": self.ROLE,
            "stage": "supply_chain_analysis",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "output_quality": quality,
            "procurement_status": "NOT_READY",
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }


class LiveQAAgent:
    """Quality Assurance agent with REAL findings."""
    ROLE = "QA"
    ROLE_DESC = "独立质量评审员，基于真实QA findings (5H/5M) 进行审查"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def review_with_v03_findings(self, team_outputs: dict[str, Any]) -> dict[str, Any]:
        """QA review using v0.3 findings status."""
        deterministic_decision = get_qa_gate_decision()
        findings_summary = get_findings_summary()
        
        # Format team outputs for review
        team_summary = json.dumps({
            k: v.get("output_quality", {}).get("quality", "UNKNOWN")
            for k, v in team_outputs.items()
        }, ensure_ascii=False)
        
        messages = [
            {"role": "system", "content": _build_v03_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于v0.3状态进行QA审查：

团队输出质量：
{team_summary}

v0.3 findings状态（10项）：
- 文档纠正：10项IMPLEMENTED
- 独立复查：0项ACCEPTED（全部NOT_ACCEPTED_YET）
- 工程关闭：10项OPEN
- 实体试验：10项NOT_RUN

v0.3门禁逻辑：
- document_correction_alone_can_close_physical_gate: FALSE
- all_required_evidence_present: FALSE
- authorized_human_release: FALSE

TOP 5阻塞项：{findings_summary['top5_priority']}

请进行QA审查：
1. 团队输出中需要返工的项目（具体指出哪个角色的哪个输出）
2. v0.3文档纠正 vs 工程验证的区别
3. 当前仍阻塞的关键证据缺口
4. QA门禁决策（注意：决策为确定性BLOCKED）

用JSON格式回答，包含：
- rework_required: 需返工项目列表
- doc_vs_engineering: 文档纠正vs工程验证说明
- evidence_gaps: 证据缺口
- gate_decision: BLOCKED (确定性)"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=500,
            temperature=0.3,
            role=self.ROLE,
            stage="qa_review_v03",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        quality = _validate_output(trace.response, parsed)
        
        return {
            "role": self.ROLE,
            "stage": "qa_review_v03",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "output_quality": quality,
            "v03_findings_status": V03_BASELINE["findings_status"],
            "gate_decision": deterministic_decision,
            "gate_status": "BLOCKED",
            "gate_is_deterministic": True,
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
            "qa_note": "QA门禁为确定性BLOCKED，文档纠正不能自动放行",
        }


class LiveMFGAgent:
    """Manufacturing/NPI agent."""
    ROLE = "MFG"
    ROLE_DESC = "制造/NPI工程师，负责小批导入、生产工艺、QC检验"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def analyze_npi_readiness(self) -> dict[str, Any]:
        """MFG NPI readiness analysis."""
        messages = [
            {"role": "system", "content": _build_v03_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于v0.3数据评估NPI就绪状态：

当前状态：
- 产品交付：NOT_READY
- BOM：预算占位，非定型
- DVT/PVT/FAT/SAT：全部NOT_RUN
- 受控图纸：未批准
- AVL合格证据：无

v0.3 QA-04响应（机械）：
- 热胀/载荷设计已补规范
- 但实测数据NOT_RUN
- 图纸批准前不得高温开工

请分析：
1. NPI关键阻塞项
2. 小批导入前置条件
3. 所需验证/测试清单
4. MFG角色待办任务

用JSON格式回答。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=300,
            temperature=0.3,
            role=self.ROLE,
            stage="npi_readiness",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        quality = _validate_output(trace.response, parsed)
        
        return {
            "role": self.ROLE,
            "stage": "npi_readiness",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "output_quality": quality,
            "npi_status": "NOT_READY",
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }


class LiveTRNAgent:
    """Training agent."""
    ROLE = "TRN"
    ROLE_DESC = "培训工程师，负责工程师培训、操作手册、技能认证"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def analyze_training_needs(self) -> dict[str, Any]:
        """TRN training needs analysis."""
        messages = [
            {"role": "system", "content": _build_v03_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于v0.3数据分析培训需求：

产品特性：
- 技术路线：{RECOMMENDED_SCENARIO['tech_route']}
- 温度范围：{RECOMMENDED_SCENARIO['temp_range_normal_C']}°C
- 点数：{RECOMMENDED_SCENARIO['points']}

培训对象：
1. 安装工程师
2. 调试工程师
3. 运维人员

v0.3约束：
- 首版AI仅监测/预警/建议，人工决策
- 不得闭环控制锅炉DCS
- 安装必须遵守锅监/OEM许可

请分析：
1. 培训模块建议
2. 安全操作要点
3. 所需认证/资质
4. TRN角色待办任务

用JSON格式回答。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=300,
            temperature=0.3,
            role=self.ROLE,
            stage="training_needs",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        quality = _validate_output(trace.response, parsed)
        
        return {
            "role": self.ROLE,
            "stage": "training_needs",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "output_quality": quality,
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }


class LiveFINAgent:
    """Finance agent."""
    ROLE = "FIN"
    ROLE_DESC = "财务分析师，负责预算分析、成本核算、投资回报"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def analyze_financials(self) -> dict[str, Any]:
        """FIN financial analysis with v0.3 QA-10 response."""
        # Include QA-10 funding finding
        qa10 = next((f for f in QA_FINDINGS_MEDIUM if f["id"] == "QA-10"), {})
        
        messages = [
            {"role": "system", "content": _build_v03_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于v0.3数据进行财务分析：

QA-10发现：资金情景未与阶段退出对齐
- 问题：{qa10.get('problem', '')[:150]}...
- v0.3响应：A0/A1/A2与32/64点细化，但完整总额UNKNOWN

v0.3资金边界：
- A0_complete_total: UNKNOWN
- A1_complete_total: UNKNOWN  
- A2_complete_total: UNKNOWN
- B32_complete_total: UNKNOWN
- B64_complete_total: UNKNOWN
- unknown_cost_must_not_default_to_zero: TRUE

预算范围（v0.2）：
- 实验室: {BUDGET_SUMMARY['lab_tier']['total_low_wan']}-{BUDGET_SUMMARY['lab_tier']['total_high_wan']}万元
- 试点: {BUDGET_SUMMARY['pilot_tier']['total_low_wan']}-{BUDGET_SUMMARY['pilot_tier']['total_high_wan']}万元
- 声明: {BUDGET_SUMMARY['disclaimer'][:80]}...

请分析：
1. 资金缺口评估（哪些未知不可填0）
2. 阶段转换成本风险
3. 成本竞争力状态（UNVERIFIED的原因）
4. FIN角色待办任务

用JSON格式回答。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=350,
            temperature=0.3,
            role=self.ROLE,
            stage="financial_analysis",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        quality = _validate_output(trace.response, parsed)
        
        return {
            "role": self.ROLE,
            "stage": "financial_analysis",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "output_quality": quality,
            "v03_qa10_addressed": True,
            "cost_competitiveness": "UNVERIFIED",
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }


class LiveSLSAgent:
    """Sales/Marketing agent."""
    ROLE = "SLS"
    ROLE_DESC = "销售/营销专员，负责销售策略、客户开发、营销材料"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def analyze_sales_strategy(self) -> dict[str, Any]:
        """SLS sales strategy analysis."""
        messages = [
            {"role": "system", "content": _build_v03_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于v0.3数据分析销售策略：

目标市场：{RECOMMENDED_SCENARIO['target_boiler']}
产品状态：
- 产品交付：NOT_READY
- 竞争力：UNVERIFIED
- 客户价值证据：无

v0.3限制：
- 不得宣称成本竞争优势已证明
- 不得使用未验证的营销主张
- 无真实项目业绩可引用

市场进入策略（研究）：
- 先合作验证/合法取得业绩
- 非直接宣称可独立投标

请分析：
1. 当前可用营销材料范围
2. 不可宣称的内容（列出）
3. 客户开发前置条件
4. SLS角色待办任务

用JSON格式回答。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=300,
            temperature=0.3,
            role=self.ROLE,
            stage="sales_strategy",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        quality = _validate_output(trace.response, parsed)
        
        return {
            "role": self.ROLE,
            "stage": "sales_strategy",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "output_quality": quality,
            "marketing_claims_verified": False,
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }


class LiveSTRAgent:
    """Strategy agent."""
    ROLE = "STR"
    ROLE_DESC = "战略规划师，负责产品路线图、竞争定位、长期规划"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def analyze_strategy(self, team_outputs: dict[str, Any]) -> dict[str, Any]:
        """STR strategy analysis based on team outputs."""
        # Summarize team output quality
        quality_summary = {
            k: v.get("output_quality", {}).get("quality", "UNKNOWN")
            for k, v in team_outputs.items()
        }
        
        messages = [
            {"role": "system", "content": _build_v03_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""基于v0.3数据和团队输出进行战略分析：

团队输出状态：
{json.dumps(quality_summary, ensure_ascii=False, indent=2)}

当前项目状态：
- 研究基线：v0.3
- 文档纠正：10项已实施
- 独立复查：0项接受
- 工程验证：全部OPEN
- 采购就绪：NOT_READY
- 产品交付：NOT_READY

风险概览：
{json.dumps([r['title'] for r in RISK_REGISTER[:3]], ensure_ascii=False)}

请进行战略分析：
1. 当前阶段定位（研究/开发/验证/生产）
2. 关键里程碑建议
3. Go/No-Go决策点
4. STR角色建议

用JSON格式回答。"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=350,
            temperature=0.3,
            role=self.ROLE,
            stage="strategy_analysis",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        quality = _validate_output(trace.response, parsed)
        
        return {
            "role": self.ROLE,
            "stage": "strategy_analysis",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "output_quality": quality,
            "current_phase": "RESEARCH_BASELINE_v0.3",
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }


class LivePMAgent:
    """Project Manager agent - coordinates team and synthesizes results."""
    ROLE = "PM"
    ROLE_DESC = "项目经理，协调12角色团队、综合输出、执行反思循环"
    
    def __init__(self, provider: LLMProvider, registry: LLMCallRegistry):
        self.provider = provider
        self.registry = registry
    
    def synthesize_all_outputs(self, team_outputs: dict[str, Any]) -> dict[str, Any]:
        """PM synthesizes all 12-role team outputs."""
        # Count outputs by quality
        quality_counts = {}
        for role, output in team_outputs.items():
            q = output.get("output_quality", {}).get("quality", "UNKNOWN")
            quality_counts[q] = quality_counts.get(q, 0) + 1
        
        messages = [
            {"role": "system", "content": _build_v03_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""作为PM综合12角色团队输出：

输出质量统计：
{json.dumps(quality_counts, ensure_ascii=False)}

v0.3项目状态：
- 文档纠正：10项IMPLEMENTED
- 独立复查：0项ACCEPTED
- 工程关闭：10项OPEN
- QA门禁：BLOCKED（确定性）

需要处理的返工项：
（根据QA审查识别需返工的角色输出）

请综合分析：
1. 各角色输出汇总（有效/需审查/无效）
2. 识别需返工的具体项目
3. 触发返工的原因
4. 下一步行动计划

用JSON格式回答，包含：
- output_summary: 各角色输出状态
- rework_items: 需返工项目及原因
- action_plan: 行动计划"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=500,
            temperature=0.3,
            role=self.ROLE,
            stage="synthesis_all",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        quality = _validate_output(trace.response, parsed)
        
        return {
            "role": self.ROLE,
            "stage": "synthesis_all",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "output_quality": quality,
            "team_quality_counts": quality_counts,
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }
    
    def execute_rework(self, qa_review: dict[str, Any], original_output: dict[str, Any]) -> dict[str, Any]:
        """PM executes rework based on QA feedback - REAL REFLECTION LOOP."""
        rework_items = qa_review.get("parsed", {}).get("rework_required", [])
        
        messages = [
            {"role": "system", "content": _build_v03_system_prompt(self.ROLE, self.ROLE_DESC)},
            {"role": "user", "content": f"""执行返工闭环（Reflection Pattern）：

QA审查识别的返工项：
{json.dumps(rework_items, ensure_ascii=False) if rework_items else "QA未能成功解析返工项"}

原始输出中的问题：
{json.dumps(original_output.get('team_quality_counts', {}), ensure_ascii=False)}

v0.3约束：
- 文档纠正 ≠ 工程验证
- 10项独立复查均未接受
- QA门禁BLOCKED

这是真实的返工闭环，请：
1. 明确指出哪个角色的哪个输出触发返工
2. 返工原因（具体引用QA findings）
3. 返工后的修正措施
4. 是否需要再次QA审查

用JSON格式回答，包含：
- trigger_output: 触发返工的输出
- trigger_reason: 触发原因
- correction_actions: 修正措施
- needs_reqa: 是否需再次审查"""}
        ]
        
        trace = self.provider.generate(
            messages=messages,
            max_tokens=400,
            temperature=0.3,
            role=self.ROLE,
            stage="rework_execution",
        )
        self.registry.record(trace)
        
        parsed = _extract_json_from_response(trace.response)
        quality = _validate_output(trace.response, parsed)
        
        return {
            "role": self.ROLE,
            "stage": "rework_execution",
            "trace": trace.to_dict(),
            "raw_response": trace.response,
            "parsed": parsed,
            "output_quality": quality,
            "reflection_pattern": {
                "chapter": "Chapter 4 (P67-82)",
                "pattern": "Reflection Pattern",
                "flow": "QA review → identify rework → PM correction → re-evaluation",
            },
            "rework_triggered": True,
            "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        }


def run_full_team_workflow(
    provider: LLMProvider,
    output_dir: str = "./outputs/full_team_run",
) -> dict[str, Any]:
    """Run complete 12-role team workflow with v0.3 data.
    
    Flow:
    1. Parallel Phase 1: MKT, OPT, HW, SW, SCM
    2. Parallel Phase 2: MFG, TRN, FIN, SLS
    3. QA Review (with real findings)
    4. PM Synthesis
    5. STR Strategy
    6. PM Rework (Reflection Loop)
    7. Final QA Gate
    
    Returns complete execution trace with quality markers.
    """
    import os
    from pathlib import Path
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    registry = LLMCallRegistry()
    
    # Create all 12 agents
    pm = LivePMAgent(provider, registry)
    mkt = LiveMKTAgent(provider, registry)
    opt = LiveOPTAgent(provider, registry)
    hw = LiveHWAgent(provider, registry)
    sw = LiveSWAgent(provider, registry)
    scm = LiveSCMAgent(provider, registry)
    qa = LiveQAAgent(provider, registry)
    mfg = LiveMFGAgent(provider, registry)
    trn = LiveTRNAgent(provider, registry)
    fin = LiveFINAgent(provider, registry)
    sls = LiveSLSAgent(provider, registry)
    str_agent = LiveSTRAgent(provider, registry)
    
    run_id = f"FULL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    results = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "provider": provider.provider_type.value,
        "model_manifest": get_model_manifest(),
        "v03_baseline": V03_BASELINE,
        "input_hash": V03_BASELINE["zip_sha256"],
        "workflow_patterns": {
            "reflection": "Chapter 4 (P67-82)",
            "multi_agent": "Chapter 7 (P113-131) - 12 roles",
            "hitl": "Chapter 13 (P201-218)",
        },
        "disclaimer": LIVE_OUTPUT_DISCLAIMER,
        "roles_executed": [],
        "stages": {},
        "quality_summary": {},
    }
    
    team_outputs = {}
    
    # Phase 1: Parallel analysis (5 roles)
    print("  [Phase 1] 并行分析（MKT, OPT, HW, SW, SCM）...")
    
    print("    [1/12] MKT: 市场分析...")
    team_outputs["MKT"] = mkt.analyze_market()
    results["stages"]["mkt_market"] = team_outputs["MKT"]
    results["roles_executed"].append("MKT")
    
    print("    [2/12] OPT: 光学/热工技术分析...")
    team_outputs["OPT"] = opt.analyze_technical_feasibility()
    results["stages"]["opt_technical"] = team_outputs["OPT"]
    results["roles_executed"].append("OPT")
    
    print("    [3/12] HW: 硬件设计分析...")
    team_outputs["HW"] = hw.analyze_hardware_design()
    results["stages"]["hw_hardware"] = team_outputs["HW"]
    results["roles_executed"].append("HW")
    
    print("    [4/12] SW: 软件架构分析...")
    team_outputs["SW"] = sw.analyze_software_architecture()
    results["stages"]["sw_software"] = team_outputs["SW"]
    results["roles_executed"].append("SW")
    
    print("    [5/12] SCM: 供应链分析...")
    team_outputs["SCM"] = scm.analyze_supply_chain()
    results["stages"]["scm_supply"] = team_outputs["SCM"]
    results["roles_executed"].append("SCM")
    
    # Phase 2: Support roles (4 roles)
    print("  [Phase 2] 支持角色（MFG, TRN, FIN, SLS）...")
    
    print("    [6/12] MFG: NPI就绪分析...")
    team_outputs["MFG"] = mfg.analyze_npi_readiness()
    results["stages"]["mfg_npi"] = team_outputs["MFG"]
    results["roles_executed"].append("MFG")
    
    print("    [7/12] TRN: 培训需求分析...")
    team_outputs["TRN"] = trn.analyze_training_needs()
    results["stages"]["trn_training"] = team_outputs["TRN"]
    results["roles_executed"].append("TRN")
    
    print("    [8/12] FIN: 财务分析...")
    team_outputs["FIN"] = fin.analyze_financials()
    results["stages"]["fin_financial"] = team_outputs["FIN"]
    results["roles_executed"].append("FIN")
    
    print("    [9/12] SLS: 销售策略分析...")
    team_outputs["SLS"] = sls.analyze_sales_strategy()
    results["stages"]["sls_sales"] = team_outputs["SLS"]
    results["roles_executed"].append("SLS")
    
    # Phase 3: QA Review
    print("  [Phase 3] QA独立审查（v0.3 findings）...")
    print("    [10/12] QA: 独立质量审查...")
    qa_review = qa.review_with_v03_findings(team_outputs)
    results["stages"]["qa_review"] = qa_review
    results["roles_executed"].append("QA")
    
    # Phase 4: PM Synthesis
    print("  [Phase 4] PM综合与策略...")
    print("    [11/12] PM: 综合团队输出...")
    pm_synthesis = pm.synthesize_all_outputs(team_outputs)
    results["stages"]["pm_synthesis"] = pm_synthesis
    results["roles_executed"].append("PM")
    
    # Phase 5: Strategy
    print("    [12/12] STR: 战略分析...")
    str_analysis = str_agent.analyze_strategy(team_outputs)
    results["stages"]["str_strategy"] = str_analysis
    results["roles_executed"].append("STR")
    
    # Phase 6: Reflection Loop - PM Rework
    print("  [Phase 5] 返工闭环（Reflection Pattern）...")
    rework_result = pm.execute_rework(qa_review, pm_synthesis)
    results["stages"]["pm_rework"] = rework_result
    results["reflection_loop_executed"] = True
    
    # Compile quality summary
    quality_summary = {
        "total_roles": 12,
        "roles_executed": len(results["roles_executed"]),
        "llm_calls": registry.get_summary(),
    }
    
    for role, output in team_outputs.items():
        q = output.get("output_quality", {})
        quality_summary[role] = {
            "quality": q.get("quality", "UNKNOWN"),
            "is_valid": q.get("is_valid", False),
            "needs_review": q.get("needs_human_review", True),
        }
    
    results["quality_summary"] = quality_summary
    results["final_gate_status"] = "BLOCKED"
    results["gate_is_deterministic"] = True
    
    # Save trace
    trace_path = os.path.join(output_dir, f"live_trace_{run_id}.json")
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Save JSONL format
    jsonl_path = os.path.join(output_dir, f"live_trace_{run_id}.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for stage_name, stage_data in results["stages"].items():
            entry = {
                "run_id": run_id,
                "stage": stage_name,
                "role": stage_data.get("role", "UNKNOWN"),
                "quality": stage_data.get("output_quality", {}).get("quality", "UNKNOWN"),
                "raw_response": stage_data.get("raw_response", "")[:500],
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    # Save calls
    calls_path = os.path.join(output_dir, f"llm_calls_{run_id}.json")
    registry.save(calls_path)
    
    results["trace_path"] = trace_path
    results["jsonl_path"] = jsonl_path
    results["calls_path"] = calls_path
    
    return results
