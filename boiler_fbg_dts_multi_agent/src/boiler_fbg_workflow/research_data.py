"""Real Research Data Integration - v0.2

This module contains REAL research data from the engineering research package v0.2.
All data is derived from actual research, with proper evidence IDs and limitations.

v0.2 CRITICAL CHANGES from v0.1:
1. REVOKED: Technica T885/T890 main/backup selection - params UNVERIFIED, HTML challenge failed
2. Lab RFQ priority: FiSens 1550 STD narrow + AC complete factory assembly
3. CALSENS as second RFQ source; OSENSA as non-FBG independent contrast
4. Field array sensor: NOT_SELECTED
5. Uncertainty: uc=2.864°C, U(k=2)=5.728°C; guardband |e|+U≤MPE cannot accept
6. Wavelength start: 1485nm (from 1470)
7. Link margin: UNKNOWN (35dB dynamic range cannot subtract 20.27dB)
8. CEZB260106803: Header FBG NOT water-wall, cannot transplant credentials
"""

from __future__ import annotations
from typing import Any

# Version tracking
RESEARCH_VERSION = "v0.2"
RESEARCH_VERSION_SUPERSEDES = "v0.1"
RESEARCH_ZIP_SHA256 = "d011d7ce1a6c92de9346c345c9223e3cfaaa8a4ea20227730956234acb044a6d"

# Book reference - unchanged
BOOK_REFERENCE = {
    "title": "Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems",
    "author": "Antonio Gullí",
    "publisher": "Springer",
    "year": 2025,
    "edition": "First Edition",
    "doi": "https://doi.org/10.1007/978-3-032-01402-3",
    "author_affiliation": "Google CTO Office Engineering Director",
    "is_google_official": False,
    "note": "Author works at Google but this is NOT a Google official publication",
    "evidence_id": "[EV-BOOK-001]",
}

# Engineering calculations - UPDATED for v0.2
ENGINEERING_CALCULATIONS: dict[str, Any] = {
    "version": "v0.2",
    "classification": "DETERMINISTIC_ENGINEERING_CALCULATION_NOT_AGENT_OR_HARDWARE_RESULT",
    
    "wavelength_budget": {
        "Tmin_C": 25,
        "Tmax_C": 700,  # 700°C is OPTIONAL_STRESS_SCENARIO
        "normal_Tmax_C": 600,  # Normal lab design
        "max_ST_nm_per_C": 0.018,
        "lambda_tolerance_nm_each_side": 1,
        "residual_strain_microstrain_each_side": 100,
        "strain_coefficient_nm_per_microstrain": 0.0012,
        "aging_nm_each_side": 0.15,
        "FWHM_nm": 0.8,
        "slot_nm": 16.5,
        "guard_nm": 1,
        "band_edge_nm_each_side": 4,
        # v0.2: Start from 1485nm not 1470
        "lambda_start_nm": 1485,
        "centers_nm": [1485.0, 1501.5, 1518.0, 1534.5, 1551.0, 1567.5, 1584.0, 1600.5],
        "first_peak_worst_low_nm": 1483.33,
        "last_peak_worst_high_nm": 1614.32,
        "normal600_thermal_shift_nm": 10.35,
        "normal600_envelope_nm": 13.69,
        # CALSENS 2nm FWHM does NOT fit 16.5nm slot
        "CALSENS_2nm_stress700_envelope_nm": 16.69,
        "CALSENS_2nm_fits_16_5_slot": False,
        "scope": "700°C is OPTIONAL_STRESS_SCENARIO_NOT_APPROVED_PROBE_RATING; normal lab design 25-600°C",
        "evidence_ids": ["[EV-CALC-ENG-001]", "[E11]"],
    },
    
    "uncertainty_budget": {
        # v0.2: Correct definitions - uc is standard, U is expanded (k=2)
        "lab_uc_standard_k1_C": 1.397,  # Standard uncertainty
        "lab_U_k2_C": 2.795,  # Expanded uncertainty U(k=2) = 2*uc
        "field_uc_standard_k1_C": 2.864,  # Standard uncertainty
        "field_U_k2_C": 5.728,  # Expanded uncertainty U(k=2) = 2*uc
        "target_MPE_C": 5,  # Maximum Permissible Error
        "conformity_decision_rule": "|e| + U ≤ MPE (guardband rule)",
        "guardband_acceptance": False,  # U=5.728 cannot guardband-accept MPE=5 even if e=0
        "conclusion": (
            "现场扩展不确定度U(k=2)=5.728°C；按|e|+U≤5°C保护带判据，"
            "即使测量偏差e=0也无法接受。这不代表实测偏差已超过±5°C，"
            "而是不确定度预算不支持保护带验收。"
        ),
        "required_action": (
            "需要：1)降低不确定度分量(热接触/位置/参考等)；"
            "2)或与用户协商放宽现场MPE；"
            "3)或通过实验获取更优的实际性能数据"
        ),
        "v0_1_error_retracted": (
            "v0.1错误表述'5.73>5即实测超差'已撤销。"
            "U是不确定度预算不是实测偏差。"
        ),
        "evidence_ids": ["[EV-CALC-ENG-001]", "[E12]"],
    },
    
    "optical_power_budget": {
        "one_way_loss_dB": 6.64,
        "return_loss_at20percent_dB": 20.27,
        # v0.2: Link margin is UNKNOWN
        "link_margin_dB": None,  # UNKNOWN
        "link_margin_status": "UNKNOWN",
        "margin_note": (
            "35dB动态范围不能直接减去20.27dB假设回波损耗得出余量。"
            "Ptx保证最小值/Pdetect门限/Psat饱和/谱形SNR条件均未知，"
            "真实链路余量UNKNOWN。"
        ),
        "evidence_ids": ["[EV-CALC-ENG-001]", "[E22]"],
    },
    
    "power_storage": {
        "power_load_W": 160,
        "ups_usable_Wh_30min_at80pct": 100.0,
    },
}

# v0.2: Updated vendor specs - Technica REVOKED from primary selection
VENDOR_SPECS: dict[str, Any] = {
    # Luna si255 - PDF verified, still HOLD
    "luna_si255": {
        "vendor": "Luna Innovations",
        "model": "si255-EV-08-1460-1620-0010-DP",
        "source_status": "PDF_VERIFIED",
        "evidence_id": "[E05]",
        "specs": {
            "wavelength_range_nm": "1460-1620",
            "channels": 8,
            "scan_rate_hz": 10,
            "connector": "LC/APC",
            "interface": "Ethernet API",
        },
        "hold_items": [
            "SDK协议端口和时戳格式",
            "Linux/ARM支持",
            "商业分发许可",
            "宽峰精度验证",
            "当前供货状态或EOL",
            "Ptx最小/Pdetect/Psat门限",
        ],
        "release_status": "HOLD",
    },
    
    # HBK FS22SI - PDF verified, still HOLD
    "hbk_fs22si": {
        "vendor": "HBK",
        "model": "FS22SI",
        "source_status": "PDF_VERIFIED",
        "evidence_id": "[E06]",
        "specs": {
            "wavelength_range_nm": "1500-1600",
            "channels": 4,
            "scan_rate_hz": 1,
            "connector": "FC/APC",
            "interface": "SCPI TCP ports 3500/3365",
        },
        "hold_items": [
            "SDK实际获取和版本",
            "操作系统支持",
            "真实固件帧/终止符",
            "Ptx最小/Pdetect/Psat门限",
        ],
        "release_status": "HOLD",
    },
    
    # v0.2: Technica REVOKED - moved to revoked section
    "technica_t890": {
        "vendor": "Technica",
        "model": "T890",
        "source_status": "REVOKED_UNVERIFIED_SEARCH_ONLY",
        "v0_2_status": "REVOKED_FROM_MAIN_SELECTION",
        "revocation_reason": (
            "v0.2撤销T890主选：本地HTML挑战不是全文、PDF未取得；"
            "精确采购参数UNVERIFIED；只作RFI线索不作选型依据"
        ),
        "evidence_id": "[E08]",
        "hold_items": ["全部参数待原厂PDF确认"],
        "release_status": "NOT_SELECTED",
    },
    "technica_t885": {
        "vendor": "Technica",
        "model": "T885",
        "source_status": "REVOKED_UNVERIFIED_SEARCH_ONLY",
        "v0_2_status": "REVOKED_FROM_MAIN_SELECTION",
        "revocation_reason": (
            "v0.2撤销T885备选：精确谱/响应/接头规格UNVERIFIED_SEARCH_ONLY；"
            "下载HTML挑战失败不计原厂资料"
        ),
        "evidence_id": "[E08]",
        "hold_items": ["全部参数待原厂PDF确认"],
        "release_status": "NOT_SELECTED",
    },
    
    # v0.2: NEW - FiSens as lab RFQ priority
    "fisens_1550": {
        "vendor": "FiSens",
        "model": "1550 STD narrow + AC complete factory assembly",
        "source_status": "PDF_VERIFIED",
        "v0_2_status": "LAB_RFQ_PRIORITY",
        "evidence_id": "[E17]",
        "specs_from_pdf": {
            "FWHM_nm": "0.25-0.35 (STD narrow)",
            "wavelength_lower_limit_nm": 1480,
            "AC_max_length_m": 0.6,
            "complete_assembly": True,
        },
        "hold_items": [
            "600°C完整成品的全部订货配置",
            "引纤/过渡/应变自由度/热限",
            "漂移/寿命数据",
            "温区材料处理",
        ],
        "release_status": "RFQ_PRIORITY_NOT_PROCUREMENT_READY",
        "rfq_id": "R2-01",
    },
    
    # v0.2: NEW - CALSENS as second RFQ source
    "calsens_ht": {
        "vendor": "CALSENS",
        "model": "High Temperature FBG Sensor",
        "source_status": "PDF_VERIFIED",
        "v0_2_status": "SECOND_RFQ_SOURCE",
        "evidence_id": "[E18]",
        "specs_from_pdf": {
            "FWHM_nm": "0.1-2",
            "max_temp_partial_protection_C": 1200,
            "note": "2nm FWHM does NOT fit 16.5nm slot budget",
        },
        "hold_items": [
            "完整保护图",
            "1200°C可用保护类型",
            "尺寸和封装解耦",
            "漂移/校准",
        ],
        "release_status": "RFQ_CANDIDATE_NOT_PROCUREMENT_READY",
        "rfq_id": "R2-04",
    },
    
    # v0.2: NEW - OSENSA as non-FBG independent contrast
    "osensa_prb1000ht": {
        "vendor": "OSENSA",
        "model": "PRB1000HT",
        "source_status": "PDF_VERIFIED",
        "v0_2_status": "INDEPENDENT_NON_FBG_CONTRAST",
        "evidence_id": "[E19]",
        "specs_from_pdf": {
            "measurement_range_C": "0-750",
            "accuracy_350_750_C": "±0.5",
            "survival_temp_C": 850,
            "time_constant_s": 30,
            "max_extension_m": 5,
        },
        "hold_items": [
            "四点配套码",
            "4根≤5m专线",
            "低温精度",
            "当前供货/校准/接口/报价",
        ],
        "note": "非FBG、不接HBK/Luna；作为独立对照系统而非直接替代",
        "release_status": "CONTRAST_SYSTEM_NOT_PROCUREMENT_READY",
        "rfq_id": "R2-07",
    },
}

# v0.2: Updated recommended scenario
RECOMMENDED_SCENARIO: dict[str, Any] = {
    "target_boiler": "300-660MW调峰煤粉直流炉背火侧可达水冷壁管屏",
    "points": "32-64点(4-8串×8点/串)",
    "temp_range_normal_C": "25-600",
    "temp_range_stress_C": "700 (OPTIONAL_STRESS_SCENARIO)",
    "tech_route": "飞秒Type II/PbP高温FBG",
    "demodulator_primary": "Luna si255-EV-08 (HOLD)",
    "demodulator_lab": "HBK FS22SI 4CH (HOLD)",
    # v0.2: Sensor selection updated
    "sensor_lab_rfq_priority": "FiSens 1550 STD narrow + AC (RFQ_PRIORITY)",
    "sensor_second_rfq": "CALSENS High Temp FBG (RFQ_CANDIDATE)",
    "sensor_field_array": "NOT_SELECTED",  # v0.2 change
    "independent_contrast": "OSENSA PRB1000HT (non-FBG)",
    "technica_status": "REVOKED_FROM_SELECTION_v0.2",
    "evidence_ids": ["[EV-DESIGN-SCEN-001]"],
}

# v0.2: Updated budget summary
BUDGET_SUMMARY: dict[str, Any] = {
    "lab_tier": {
        "subtotal_low_cny": 75000,
        "subtotal_high_cny": 218000,
        "contingency_pct": 25,
        "total_low_wan": 9.375,
        "total_high_wan": 27.25,
    },
    "pilot_tier": {
        "subtotal_low_cny": 553400,
        "subtotal_high_cny": 1590000,
        "contingency_pct": 30,
        "total_low_wan": 71.942,
        "total_high_wan": 206.70,
    },
    "disclaimer": (
        "⚠️ 全部价格为ENGINEERING_SCENARIO_NO_QUOTE - 预算情景占位，"
        "没有核实原厂售价或正式报价。禁止据此采购或宣称成本竞争力已证实。"
        "不含完整长时DVT等范围，不承诺足够覆盖。"
    ),
    "evidence_ids": ["[EV-BUDGET-001]", "[E13]"],
}

# v0.2: Updated BOM - Technica revoked
BOM_LAB_TIER: list[dict[str, Any]] = [
    {
        "item_id": "A01",
        "tier": "LAB",
        "category": "demodulator",
        "description": "解调仪(实验4CH)",
        "vendor": "HBK",
        "part_number": "FS22SI-系列",
        "quantity": 1,
        "unit_price_low_cny": 40000,
        "unit_price_high_cny": 80000,
        "price_evidence": "ENGINEERING_SCENARIO_NO_QUOTE",
        "status": "HOLD",
        "evidence_ids": ["[E06]"],
    },
    {
        "item_id": "A02",
        "tier": "LAB",
        "category": "sensor",
        "description": "高温FBG探头4点实验样件",
        "vendor": "FiSens (RFQ优先) / CALSENS (备选)",
        "part_number": "TBD-RFQ_REQUIRED",
        "quantity": 4,
        "unit_price_low_cny": 3000,
        "unit_price_high_cny": 18000,
        "price_evidence": "ENGINEERING_SCENARIO_NO_QUOTE",
        "status": "RFQ_PRIORITY_NOT_PROCUREMENT_READY",
        "v0_2_note": "Technica已撤销，改为FiSens/CALSENS询价",
        "evidence_ids": ["[E17]", "[E18]"],
    },
    {
        "item_id": "A03",
        "tier": "LAB",
        "category": "contrast_system",
        "description": "独立非FBG对照探头系统",
        "vendor": "OSENSA",
        "part_number": "PRB1000HT + FTX300-LUX-HT",
        "quantity": 1,
        "unit_price_low_cny": 15000,
        "unit_price_high_cny": 50000,
        "price_evidence": "ENGINEERING_SCENARIO_NO_QUOTE",
        "status": "RFQ_CANDIDATE",
        "v0_2_note": "新增独立非FBG对照系统",
        "evidence_ids": ["[E19]"],
    },
]

BOM_PILOT_TIER: list[dict[str, Any]] = [
    {
        "item_id": "B01",
        "tier": "PILOT",
        "category": "demodulator",
        "description": "解调仪(商用8CH)",
        "vendor": "Luna",
        "part_number": "si255-EV-08-1460-1620-0010-DP",
        "quantity": 1,
        "unit_price_low_cny": 200000,
        "unit_price_high_cny": 500000,
        "price_evidence": "ENGINEERING_SCENARIO_NO_QUOTE",
        "status": "HOLD",
        "evidence_ids": ["[E05]"],
    },
    {
        "item_id": "B02",
        "tier": "PILOT",
        "category": "sensor",
        "description": "现场高温FBG阵列探头",
        "vendor": "TBD",
        "part_number": "NOT_SELECTED",
        "quantity": 8,
        "unit_price_low_cny": 20000,
        "unit_price_high_cny": 80000,
        "price_evidence": "ENGINEERING_SCENARIO_NO_QUOTE",
        "status": "NOT_SELECTED",
        "v0_2_note": "现场阵列传感器NOT_SELECTED，待实验室验证后决策",
        "evidence_ids": [],
    },
]

# v0.2: Updated risk register
RISK_REGISTER: list[dict[str, Any]] = [
    {
        "risk_id": "RISK-001",
        "title": "现场不确定度预算不支持保护带验收",
        "category": "technical",
        "probability": "high",
        "impact": "high",
        "description": (
            "U(k=2)=5.728°C，按|e|+U≤5°C保护带判据无法接受。"
            "这不代表实测偏差已超过±5°C。"
        ),
        "v0_2_clarification": "v0.1'5.73>5即超差'表述已撤销",
        "mitigation": "降低不确定度分量或与用户协商MPE",
        "evidence_ids": ["[E12]"],
    },
    {
        "risk_id": "RISK-002",
        "title": "高温FBG探头选型阻塞",
        "category": "technical",
        "probability": "high",
        "impact": "high",
        "description": (
            "v0.2撤销Technica T885/T890主备选型。"
            "FiSens/CALSENS为RFQ优先但均需原厂确认。"
            "现场阵列传感器NOT_SELECTED。"
        ),
        "mitigation": "完成FiSens/CALSENS询价，获取原厂规格和报价",
        "evidence_ids": ["[E08]", "[E17]", "[E18]"],
    },
    {
        "risk_id": "RISK-003",
        "title": "链路余量未知",
        "category": "technical",
        "probability": "medium",
        "impact": "high",
        "description": (
            "35dB动态范围不能直接减去20.27dB假设损耗。"
            "Ptx/Pdetect/Psat未知，真实链路余量UNKNOWN。"
        ),
        "mitigation": "向Luna/HBK确认链路计算参数",
        "evidence_ids": ["[E22]"],
    },
    {
        "risk_id": "RISK-004",
        "title": "国内竞品业绩不可直接移植",
        "category": "market",
        "probability": "medium",
        "impact": "medium",
        "description": (
            "国能CEZB260106803是联箱FBG招标非水冷壁，"
            "300MW业绩门槛不能移植为本产品资质。"
        ),
        "mitigation": "先合作验证/合法取得业绩，非直接宣称可独立投标",
        "evidence_ids": ["[E20]"],
    },
]

# v0.2: Evidence ledger (full list)
EVIDENCE_LEDGER: list[dict[str, Any]] = [
    {"evidence_id": "E01", "claim": "书籍第一版由Springer出版", "confidence": "A"},
    {"evidence_id": "E02", "claim": "Ch7明确多智能体结构", "confidence": "A"},
    {"evidence_id": "E03", "claim": "2025-2027煤电升级政策", "confidence": "A"},
    {"evidence_id": "E04", "claim": "国能2026自述飞秒监测示范", "confidence": "B"},
    {"evidence_id": "E05", "claim": "Luna si255规格", "confidence": "A"},
    {"evidence_id": "E06", "claim": "HBK FS22SI规格", "confidence": "A"},
    {"evidence_id": "E07", "claim": "HBK SCPI端口", "confidence": "A"},
    {"evidence_id": "E08", "claim": "T890网页描述(v0.2撤销主选)", "confidence": "W1_LIMITED"},
    {"evidence_id": "E09", "claim": "engionic TypeII规格", "confidence": "B"},
    {"evidence_id": "E10", "claim": "高温FBG漂移文献", "confidence": "A"},
    {"evidence_id": "E11", "claim": "波长预算计算", "confidence": "C"},
    {"evidence_id": "E12", "claim": "不确定度预算(v0.2修正)", "confidence": "C"},
    {"evidence_id": "E13", "claim": "BOM预算占位", "confidence": "D"},
    {"evidence_id": "E14", "claim": "第一版无自动闭环", "confidence": "REQUIREMENT"},
    {"evidence_id": "E15", "claim": "试点对象设计画像", "confidence": "DESIGN_CHOICE"},
    {"evidence_id": "E16", "claim": "27号令网安要求", "confidence": "A"},
    {"evidence_id": "E17", "claim": "FiSens1550 Rev7规格", "confidence": "A_PRIMARY_PDF"},
    {"evidence_id": "E18", "claim": "CALSENS高温FBG规格", "confidence": "A_PRIMARY_PDF"},
    {"evidence_id": "E19", "claim": "OSENSA PRB1000HT规格", "confidence": "A_PRIMARY_PDF"},
    {"evidence_id": "E20", "claim": "国能CEZB260106803联箱招标", "confidence": "A_PRIMARY_NOTICE"},
    {"evidence_id": "E21", "claim": "准智水冷壁FBG营销", "confidence": "B_PRIMARY_MARKETING"},
    {"evidence_id": "E22", "claim": "链路余量UNKNOWN", "confidence": "ENGINEERING_REVIEW"},
]


def get_qa_gate_decision() -> dict[str, Any]:
    """Get QA gate decision based on v0.2 research data.
    
    QA MUST REJECT Stage 2 because:
    1. Field uncertainty U(k=2)=5.728°C, guardband |e|+U≤5°C cannot accept
    2. All BOM prices are ENGINEERING_SCENARIO_NO_QUOTE
    3. Technica specs REVOKED - lab sensor NOT_SELECTED for field arrays
    4. Link margin UNKNOWN
    
    NOTE: U=5.728 > 5 does NOT mean measured bias > 5°C.
    It means the uncertainty budget cannot support guardband acceptance.
    """
    return {
        "gate_status": "BLOCKED",
        "decision_rationale": (
            "v0.2审查未通过 - 存在阻塞性问题。"
            "1) 扩展不确定度U(k=2)=5.728°C，保护带判据|e|+U≤5°C无法接受；"
            "2) Technica T885/T890已撤销主选，现场阵列传感器NOT_SELECTED；"
            "3) 链路余量UNKNOWN；"
            "4) 全部BOM价格为预算情景无实际报价。"
        ),
        "v0_2_clarification": (
            "澄清：U=5.728°C是不确定度预算，不是实测偏差。"
            "'不能验收'指保护带判据不满足，不代表实测已超差。"
            "v0.1的'5.73>5即超差'表述已撤销。"
        ),
        "critical_issues": [
            {
                "issue_id": "ISS-002-001",
                "severity": "critical",
                "title": "不确定度预算不支持保护带验收",
                "description": (
                    "U(k=2)=5.728°C，按|e|+U≤5°C判据，"
                    "即使e=0也无法接受。需降低U分量或协商MPE。"
                ),
                "evidence_ids": ["[E12]"],
            },
            {
                "issue_id": "ISS-002-002",
                "severity": "critical",
                "title": "Technica选型已撤销",
                "description": (
                    "T885/T890参数UNVERIFIED，PDF未取得，"
                    "v0.2撤销主备选型。现场阵列传感器NOT_SELECTED。"
                ),
                "evidence_ids": ["[E08]"],
            },
            {
                "issue_id": "ISS-002-003",
                "severity": "major",
                "title": "链路余量未知",
                "description": (
                    "35dB动态范围不能直接减去20.27dB假设损耗。"
                    "Ptx/Pdetect/Psat未知，真实余量UNKNOWN。"
                ),
                "evidence_ids": ["[E22]"],
            },
            {
                "issue_id": "ISS-002-004",
                "severity": "major",
                "title": "全部价格为预算占位",
                "description": "ENGINEERING_SCENARIO_NO_QUOTE，禁止据此采购",
                "evidence_ids": ["[E13]"],
            },
        ],
        "hold_count": len(VENDOR_SPECS),
        "evidence_ids": ["[EV-REVIEW-QA-V02]"],
    }


def get_revoked_conclusions() -> list[dict[str, Any]]:
    """List of v0.1 conclusions that are REVOKED in v0.2.
    
    For regression testing - these conclusions must NOT appear in output.
    """
    return [
        {
            "revoked_id": "REV-001",
            "v0_1_conclusion": "Technica T890 as primary field array sensor",
            "v0_2_status": "REVOKED",
            "reason": "PDF未取得，HTML挑战失败，参数UNVERIFIED",
        },
        {
            "revoked_id": "REV-002",
            "v0_1_conclusion": "Technica T885 as backup sensor",
            "v0_2_status": "REVOKED",
            "reason": "精确谱/响应/接头规格UNVERIFIED_SEARCH_ONLY",
        },
        {
            "revoked_id": "REV-003",
            "v0_1_conclusion": "5.73°C > 5°C means measured bias exceeds target",
            "v0_2_status": "REVOKED",
            "reason": "U是不确定度预算不是实测偏差。正确表述：保护带判据|e|+U≤MPE无法接受",
        },
        {
            "revoked_id": "REV-004",
            "v0_1_conclusion": "35dB - 20.27dB = 14.7dB margin",
            "v0_2_status": "REVOKED",
            "reason": "Ptx/Pdetect/Psat未知，链路余量UNKNOWN",
        },
        {
            "revoked_id": "REV-005",
            "v0_1_conclusion": "Wavelength start at 1470nm",
            "v0_2_status": "REVISED",
            "reason": "改为1485nm以兼顾FiSens 1480下限",
        },
        {
            "revoked_id": "REV-006",
            "v0_1_conclusion": "CEZB260106803 as water-wall FBG precedent",
            "v0_2_status": "REVOKED",
            "reason": "该招标是联箱FBG非水冷壁，不能移植业绩",
        },
    ]
