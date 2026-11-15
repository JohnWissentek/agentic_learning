"""Real Research Data Integration Module.

This module contains ACTUAL RESEARCH DATA from the engineering research package.
All data is properly sourced with evidence IDs and limitations clearly marked.

IMPORTANT DISCLAIMERS:
1. All prices are ENGINEERING_SCENARIO_NO_QUOTE - not actual vendor quotes
2. Technica PDF download failed - specs are WEB_INDEX_ONLY, pending OEM confirmation
3. Current field uncertainty ~5.73°C does NOT meet ±5°C target - QA MUST REJECT
4. All BOM items are HOLD status until vendor clarifications complete
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Book reference - verified
BOOK_REFERENCE = {
    "title": "Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems",
    "author": "Antonio Gullí",
    "publisher": "Springer Cham",
    "edition": "1st Edition, 2025",
    "doi": "https://doi.org/10.1007/978-3-032-01402-3",
    "pages": 482,
    "repo_path": "agentic_design_patterns/Agentic_Design_Patterns_full.md",
    "author_affiliation": "Google CTO Office (employment relationship, NOT Google official publication)",
    "evidence_id": "[EV-LIT-BOOK-001]",
    "confidence": "A",
    "limitation": "Author works at Google; this is NOT a Google-certified or official publication",
}

# Recommended scenario - from research
RECOMMENDED_SCENARIO = {
    "scenario_id": "SCEN-PILOT-001",
    "name": "300-660MW调峰煤粉直流炉背火侧水冷壁局部监测",
    "description": "调峰参与机组的背火侧可达管屏区域32-64点附加监测，保留现有热电偶和保护系统",
    "rationale": "调峰负荷/给水变动对应温差和升温速率可解释，已有DCS可对照，背火侧可达性较好",
    "points_count": "32-64点(8串×4-8点)",
    "temperature_range_c": "25-600 (待验证范围，非锅炉运行许可温度)",
    "temperature_700c_note": "700°C短时能力仅为候选，原厂未给时间/寿命保证前HOLD",
    "evidence_ids": ["[EV-DESIGN-SCEN-001]"],
    "confidence": "DESIGN_CHOICE",
    "limitation": "目标画像，不是已找到的试点客户",
}

# Engineering calculations - DETERMINISTIC, verified
ENGINEERING_CALCULATIONS = {
    "classification": "DETERMINISTIC_ENGINEERING_CALCULATION_NOT_AGENT_OR_HARDWARE_RESULT",
    "wavelength_budget": {
        "Tmin_C": 25,
        "Tmax_C": 700,
        "max_ST_nm_per_C": 0.018,
        "thermal_shift_nm": 12.15,
        "full_envelope_nm": 15.49,
        "slot_nm": 16.5,
        "eight_slot_width_nm": 132.0,
        "band160_usable_nm": 152,
        "band100_usable_nm": 92,
        "conclusion": "160nm band (1460-1620nm) can fit 8 points/string; 100nm band cannot fit 8 points",
    },
    "optical_power_budget": {
        "one_way_loss_dB": 6.64,
        "return_loss_at_20pct_dB": 20.27,
        "loss_plus_6dB_margin_dB": 26.27,
        "si255_dynamic_range_dB": 35,
        "conclusion": "Paper calculation shows margin exists; actual full-string test required",
    },
    "uncertainty_budget": {
        "lab_components": {
            "reference_C": 0.5,
            "furnace_uniformity_C": 0.7,
            "repeatability_C": 0.3,
            "fitting_C": 0.5,
            "demodulation_C": 0.15,
            "residual_strain_C": 0.6,
            "short_term_drift_C": 0.7,
        },
        "field_additional": {
            "thermal_contact_C": 2.0,
            "position_difference_C": 1.5,
        },
        "lab_U_k2_C": 2.79,
        "field_U_k2_C": 5.73,
        "target_uncertainty_C": 5.0,
        "conclusion": "FIELD UNCERTAINTY 5.73°C EXCEEDS ±5°C TARGET - QA MUST REJECT",
        "required_action": "Must reduce thermal contact/position error OR relax field target",
    },
    "power_storage": {
        "power_load_W": 160,
        "ups_usable_Wh_30min_at80pct": 100.0,
        "storage_GB_per_day": 5.308416,
    },
    "evidence_id": "[EV-CALC-ENG-001]",
    "confidence": "C",
    "limitation": "All coefficients are design assumptions requiring OEM/test verification",
}

# BOM data - ALL ENGINEERING_SCENARIO_NO_QUOTE
BOM_LAB_TIER = [
    {
        "item_id": "A01",
        "description": "HBK FS22SI 4CH FC/APC租借/共享",
        "unit": "套期",
        "qty": 1,
        "unit_low_CNY": 15000,
        "unit_high_CNY": 40000,
        "price_evidence": "ENGINEERING_SCENARIO_NO_QUOTE",
        "notes": "租借可用性未确认；稳态1Hz",
        "release_status": "HOLD",
        "evidence_id": "[EV-BOM-A01]",
    },
    {
        "item_id": "A02",
        "description": "Technica T885单点完整高温探头",
        "unit": "支",
        "qty": 4,
        "unit_low_CNY": 3000,
        "unit_high_CNY": 10000,
        "price_evidence": "ENGINEERING_SCENARIO_NO_QUOTE",
        "notes": "需温区/校准/应变澄清；非现价；PDF下载失败仅网页索引",
        "release_status": "HOLD",
        "evidence_id": "[EV-BOM-A02]",
        "spec_status": "WEB_INDEX_ONLY_PENDING_OEM_CONFIRMATION",
    },
    {
        "item_id": "A03",
        "description": "可溯源参考传感器及读出借用/租赁",
        "unit": "组",
        "qty": 1,
        "unit_low_CNY": 8000,
        "unit_high_CNY": 20000,
        "price_evidence": "ENGINEERING_SCENARIO_NO_QUOTE",
        "notes": "依目标不确定度选定",
        "release_status": "HOLD",
        "evidence_id": "[EV-BOM-A03]",
    },
    {
        "item_id": "A04",
        "description": "50-600°C温源租赁或实验室服务",
        "unit": "组",
        "qty": 1,
        "unit_low_CNY": 10000,
        "unit_high_CNY": 30000,
        "price_evidence": "ENGINEERING_SCENARIO_NO_QUOTE",
        "notes": "25°C和热接触另验证；不含700°C",
        "release_status": "HOLD",
        "evidence_id": "[EV-BOM-A04]",
    },
]

BOM_PILOT_TIER = [
    {
        "item_id": "B01",
        "description": "Luna si255-EV-08-1460-1620-0010-DP",
        "unit": "套",
        "qty": 1,
        "unit_low_CNY": 180000,
        "unit_high_CNY": 450000,
        "price_evidence": "ENGINEERING_SCENARIO_NO_QUOTE",
        "notes": "SDK/供货/许可与校准待确认",
        "release_status": "HOLD",
        "evidence_id": "[EV-BOM-B01]",
        "spec_source": "Luna_si255.pdf REV4 2021",
    },
    {
        "item_id": "B02",
        "description": "Technica T890 8点高温阵列",
        "unit": "串",
        "qty": 8,
        "unit_low_CNY": 10000,
        "unit_high_CNY": 30000,
        "price_evidence": "ENGINEERING_SCENARIO_NO_QUOTE",
        "notes": "8x8=64工作点；全温谱/寿命未确认；PDF下载失败",
        "release_status": "HOLD",
        "evidence_id": "[EV-BOM-B02]",
        "spec_status": "WEB_INDEX_ONLY_PENDING_OEM_CONFIRMATION",
    },
    {
        "item_id": "B06",
        "description": "Advantech UNO2484G V2级IPC/SSD",
        "unit": "套",
        "qty": 1,
        "unit_low_CNY": 10000,
        "unit_high_CNY": 25000,
        "price_evidence": "ENGINEERING_SCENARIO_NO_QUOTE",
        "notes": "准确CPU/OS/RAM/SKU待定",
        "release_status": "HOLD",
        "evidence_id": "[EV-BOM-B06]",
        "spec_source": "Advantech_UNO2484G_V2.pdf",
    },
    {
        "item_id": "B13",
        "description": "首版软件/AI/QA研发NRE",
        "unit": "项",
        "qty": 1,
        "unit_low_CNY": 120000,
        "unit_high_CNY": 350000,
        "price_evidence": "ENGINEERING_SCENARIO_NO_QUOTE",
        "notes": "研发费用不冒充每套重复BOM",
        "release_status": "ESTIMATE_ONLY",
        "evidence_id": "[EV-BOM-B13]",
    },
]

BUDGET_SUMMARY = {
    "lab_tier": {
        "subtotal_low_CNY": 75000,
        "subtotal_high_CNY": 218000,
        "contingency_fraction": 0.25,
        "planning_total_low_CNY": 93750,
        "planning_total_high_CNY": 272500,
        "meaning": "未询价预算情景；不含税费停机重大改造",
        "evidence_id": "[EV-BUDGET-LAB]",
        "confidence": "D",
    },
    "pilot_tier": {
        "subtotal_low_CNY": 553400,
        "subtotal_high_CNY": 1590000,
        "contingency_fraction": 0.30,
        "planning_total_low_CNY": 719420,
        "planning_total_high_CNY": 2067000,
        "meaning": "未询价预算情景；不含税费停机重大改造",
        "evidence_id": "[EV-BUDGET-PILOT]",
        "confidence": "D",
    },
    "disclaimer": "全部是透明规划占位范围；禁止据此采购或宣称成本竞争力已证实",
}

# Vendor specs - with verified PDF status
VENDOR_SPECS = {
    "luna_si255": {
        "vendor": "Luna Innovations",
        "model": "si255-EV-08-1460-1620-0010-DP",
        "source": "Luna_si255.pdf REV4 2021",
        "source_status": "PDF_VERIFIED",
        "specs": {
            "channels": 8,
            "wavelength_range_nm": "1460-1620",
            "scan_rate_hz": 10,
            "accuracy_pm": 1,
            "stability_pm": 1,
            "dynamic_range_dB": "35 peak / 45 FS",
            "connector": "LC/APC",
            "power_vdc": "9-36",
            "power_typical_w": 30,
            "power_max_w": 40,
            "operating_temp_c": "-20 to 60",
            "api": "Python/Matlab/C++/C#/LabVIEW",
        },
        "hold_items": [
            "SDK协议端口和时戳格式",
            "Linux/ARM支持",
            "商业分发许可",
            "掉线缓存行为",
            "仪器生命周期/售后",
            "宽峰精度验证",
        ],
        "evidence_id": "[EV-SPEC-LUNA-001]",
        "confidence": "A",
    },
    "hbk_fs22si": {
        "vendor": "HBK (Hottinger Brüel & Kjær)",
        "model": "FS22SI",
        "source": "HBK_FS22SI_B04203.pdf 2024-09-19",
        "source_status": "PDF_VERIFIED",
        "specs": {
            "wavelength_range_nm": "1500-1600",
            "repeatability_pm": "<0.5",
            "resolution_pm": "<0.5",
            "stability_pm": 1,
            "channels": "1/4/8",
            "scan_rate_hz": 1,
            "dynamic_range_dB": ">50",
            "connector": "FC/APC or SC/APC",
            "interface": "TCP/IP ASCII SCPI",
            "time_sync": "NTP",
            "power_vdc": "11-36 (standard)",
        },
        "hold_items": [
            "分辨率/重复性不等于绝对波长准确度",
            "不可据1pm再现直接承诺±0.1°C",
            "宽温峰数限制",
        ],
        "evidence_id": "[EV-SPEC-HBK-001]",
        "confidence": "A",
    },
    "technica_t890": {
        "vendor": "Technica Optical Components",
        "model": "T890",
        "source": "https://technicasa.com/t890-high-temp-fbg-sensing-probe/",
        "source_status": "WEB_INDEX_ONLY_PDF_DOWNLOAD_FAILED",
        "specs_from_webpage": {
            "description": "低摩擦Inconel625管多点探头",
            "max_points": "up to 40",
            "max_length_m": 25,
            "coating": "可选涂覆/密封",
        },
        "hold_items": [
            "原厂PDF未取得",
            "连续600°C时长/寿命未确认",
            "应变系数未确认",
            "校准不确定度未确认",
            "全温光谱未确认",
        ],
        "evidence_id": "[EV-SPEC-T890-001]",
        "confidence": "B",
        "limitation": "仅网页索引，待原厂确认，不能认为兼容已证实",
    },
    "technica_t885": {
        "vendor": "Technica Optical Components",
        "model": "T885",
        "source": "Webpage index + failed PDF download",
        "source_status": "WEB_INDEX_ONLY_PDF_DOWNLOAD_FAILED",
        "specs_from_index": {
            "wavelength_nm": "1460-1620nm ±1nm",
            "fwhm_nm": "0.15-0.8 (>400°C)",
            "reflectivity": ">20%",
            "connector": "FC/APC",
        },
        "hold_items": [
            "本地PDF下载遇站点反自动化跳转，未取得有效PDF实体",
            "表内数值是索引证据/需正式数据表确认",
            "不作已收货规格",
            "单点探头不假装可串联",
        ],
        "evidence_id": "[EV-SPEC-T885-001]",
        "confidence": "B",
        "limitation": "仅网页索引，待原厂确认",
    },
}

# Risk register (FMEA initial)
RISK_REGISTER = [
    {
        "risk_id": "H01",
        "failure_mode": "高温光栅存活但波长漂移",
        "effect": "热预警阈值错/长期偏差",
        "severity": "HIGH",
        "owner_role": "光学/QA",
        "mitigation": "温度时间封装漂移数据+1000h计划+复校",
        "status": "OPEN",
    },
    {
        "risk_id": "H02",
        "failure_mode": "安装应变耦合/热胀受限",
        "effect": "假超温/漏报",
        "severity": "HIGH",
        "owner_role": "机械/光学",
        "mitigation": "松套封装+应变隔离试验+安装资格",
        "status": "OPEN",
    },
    {
        "risk_id": "H03",
        "failure_mode": "热接触/保温/辐射误差",
        "effect": "读的是套管非管壁",
        "severity": "HIGH",
        "owner_role": "热工",
        "mitigation": "受控管屏热流/参考/重复安装",
        "status": "OPEN",
    },
    {
        "risk_id": "H06",
        "failure_mode": "压力管损伤/夹持应力/焊接影响",
        "effect": "机械完整性风险",
        "severity": "CRITICAL",
        "owner_role": "电厂锅监/OEM",
        "mitigation": "不擅焊打磨开孔/OEM安装批准/资质",
        "status": "HOLD",
    },
    {
        "risk_id": "H08",
        "failure_mode": "网安跨区/公网外传/写DCS",
        "effect": "电厂安全风险",
        "severity": "CRITICAL",
        "owner_role": "网安",
        "mitigation": "分区批准/无写权限/隔离/不外传",
        "status": "HOLD",
    },
    {
        "risk_id": "H12",
        "failure_mode": "预算占位当报价",
        "effect": "资金决策失误",
        "severity": "HIGH",
        "owner_role": "财务/PM",
        "mitigation": "价格证据分级/不授权采购/区间敏感性",
        "status": "OPEN",
    },
]

# Evidence ledger summary
EVIDENCE_LEDGER = {
    "total_entries": 16,
    "confidence_distribution": {
        "A": 7,  # Verified primary sources
        "B": 4,  # Partially verified
        "C": 2,  # Calculations with assumptions
        "D": 1,  # Budget scenarios only
        "DESIGN_CHOICE": 1,
        "REQUIREMENT": 1,
    },
    "critical_findings": [
        {
            "id": "E12",
            "finding": "现场接触不确定度示例U≈5.73°C大于拟±5°C目标",
            "action": "QA MUST REJECT - cannot claim target met",
            "evidence_source": "engineering/02_系统设计及接口基线.md §7",
        },
        {
            "id": "E13",
            "finding": "全部BOM价格仅为预算情景，没有核实原厂售价",
            "action": "禁止据此采购或宣称成本竞争力已证实",
            "evidence_source": "tables/BOM_两档预算.csv",
        },
    ],
    "pdf_status": {
        "verified_valid": [
            "Luna_si255.pdf",
            "HBK_FS22SI_A04249.pdf",
            "HBK_FS22SI_B04203.pdf",
            "Advantech_UNO2484G_V2.pdf",
            "Sensornet_Sentinel_DTS.pdf",
            "engionic_FemtoGratings.pdf",
            "NEA_coal_upgrade_2025_2027.pdf",
            "Power_Cybersecurity_Order27.pdf",
        ],
        "download_failed": [
            "Technica_T885_download_failed.html",
            "Technica_T890 - no PDF obtained",
        ],
    },
}


def get_qa_gate_decision() -> dict[str, Any]:
    """Get QA gate decision based on research data.
    
    CRITICAL: Current field uncertainty (5.73°C) does NOT meet target (±5°C).
    QA MUST REJECT/HOLD until uncertainty is reduced or target is relaxed.
    """
    return {
        "gate_status": "BLOCKED",
        "decision_rationale": (
            "现场不确定度5.73°C超过±5°C目标，不能放行。"
            "必须：1)降低热接触/位置误差 或 2)放宽现场指标 或 3)进行实验验证证明可达性"
        ),
        "critical_issues": [
            {
                "issue_id": "QA-UNCERT-001",
                "severity": "CRITICAL",
                "title": "现场不确定度不满足目标",
                "description": "工程计算显示现场U(k=2)=5.73°C > ±5°C目标",
                "required_action": "必须实验验证或调整设计/目标",
                "evidence_id": "[EV-CALC-ENG-001]",
            },
            {
                "issue_id": "QA-BOM-001",
                "severity": "MAJOR",
                "title": "全部BOM无实际报价",
                "description": "所有价格为ENGINEERING_SCENARIO_NO_QUOTE，禁止据此采购",
                "required_action": "获取原厂正式报价后更新",
                "evidence_id": "[EV-BUDGET-LAB]",
            },
            {
                "issue_id": "QA-SPEC-001",
                "severity": "MAJOR",
                "title": "Technica规格仅为网页索引",
                "description": "T885/T890 PDF下载失败，规格未经原厂确认",
                "required_action": "获取原厂正式数据表",
                "evidence_id": "[EV-SPEC-T890-001]",
            },
        ],
        "hold_count": len([b for b in BOM_LAB_TIER + BOM_PILOT_TIER if b["release_status"] == "HOLD"]),
        "evidence_ids": ["[EV-REVIEW-QA-GATE-001]"],
    }
