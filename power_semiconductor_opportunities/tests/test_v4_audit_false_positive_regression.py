"""Regression guards from real V4.0 flagship live-run debugging (anti-false-positive rules)."""

from __future__ import annotations

from pso_workflow.tools.audit_guard import audit_roi_consistency


def test_roi_audit_never_misparses_company_3m_or_rd_months_in_commercial_tables() -> None:
    """Real-world regression: '3M 垄断' and '10个月 vs 24个月' R&D cycle MUST NOT trigger ROI drift."""
    evaluated_opps = [
        {
            "seed": {"opp_id": "DP1-O2"},
            "roi": {"payback_months": 10.9},
            "roi_range": {
                "optimistic": {"payback_months": 5.5},
                "baseline": {"payback_months": 10.9},
                "conservative": {"payback_months": 25.5},
            },
        },
        {
            "seed": {"opp_id": "DP4-O3"},
            "roi": {"payback_months": 14.9},
            "roi_range": {
                "optimistic": {"payback_months": 7.6},
                "baseline": {"payback_months": 14.9},
                "conservative": {"payback_months": 34.4},
            },
        },
    ]
    drafts = {
        "00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md": (
            "| #1 | `DP1-O2` | 硫化物传感器 | 全球空白 | 10个月 (AI协同) vs 24个月 (传统串行) |\n"
            "| #1 | `DP1-O2` | **5.5 / 10.9 / 25.5月** | [ROI-CALC] |\n"
        ),
        "03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md": (
            "| **`DP4-O3`** | `DP4` | 打破 3M 垄断 [EV-CN-131]，无商用在线一体机 |\n"
            "| #3 | `DP4-O3` | **7.6 / 14.9 / 34.4月** | [ROI-CALC] |\n"
        ),
    }
    res = audit_roi_consistency(drafts=drafts, evaluated_opps=evaluated_opps)
    assert res["roi_consistency_pass"] is True
    assert res["mismatches"] == []


def test_roi_audit_scopes_multi_opp_prose_and_skips_commercial_target_clauses() -> None:
    """Real-world regression: multi-opp prose lines & Spec-in target ceilings must not false-positive,
    while actual tampered numbers in the same multi-opp prose line MUST still be caught."""
    evaluated_opps = [
        {
            "seed": {"opp_id": "DP1-O2"},
            "roi": {"payback_months": 10.9},
            "roi_range": {
                "optimistic": {"payback_months": 3.3},
                "baseline": {"payback_months": 10.9},
                "conservative": {"payback_months": 25.5},
            },
        },
        {
            "seed": {"opp_id": "DP2-O3"},
            "roi": {"payback_months": 25.3},
            "roi_range": {
                "optimistic": {"payback_months": 12.4},
                "baseline": {"payback_months": 25.3},
                "conservative": {"payback_months": 58.4},
            },
        },
        {
            "seed": {"opp_id": "DS1-O3"},
            "roi": {"payback_months": 20.3},
            "roi_range": {
                "optimistic": {"payback_months": 8.2},
                "baseline": {"payback_months": 20.3},
                "conservative": {"payback_months": 61.4},
            },
        },
    ]
    clean_drafts = {
        "00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md": (
            "- 回报分布：`#1 DP1-O2`（乐观/基准/保守回收期分别为 **3.3 / 10.9 / 25.5月**）；"
            "仅 1 项落入 Tier-C：`#14 DP2-O3`（Base **25.3月**，IRR 42.4%）。\n"
            "| 高ROI | 重点 `DP1-O2` / `DP2-O3` | `DP1-O2` 基准回收 **10.9 个月**（`DP1-O2` CAPEX ¥110万），共 14 项达成 ≤24 个月基准回收期。 |\n"
        ),
        "03_ROI_FINANCIAL_MODEL_AND_ELO_RANKING.md": (
            "| #7 `DS1-O3` | 先于 300+ 层 3D NAND 跑通 6 个月再开 APC | 把保守回本压回 48 月内。 |\n"
            "| 研发周期 | 远期平台需 **22 个月**（`DP2-O3`）。现金流回本跨度大（Base 10.9–25.3 月）。 | 旁路舱 **11 个月**（`DS1-O3`）。 |\n"
        ),
    }
    res_ok = audit_roi_consistency(drafts=clean_drafts, evaluated_opps=evaluated_opps)
    assert res_ok["roi_consistency_pass"] is True
    assert res_ok["mismatches"] == []

    # Verify tampering with DP2-O3 on the same multi-opp line is STILL caught!
    tampered_drafts = {
        "00_EXECUTIVE_SUMMARY_AND_TOP_OPPORTUNITIES.md": (
            "- 回报分布：`#1 DP1-O2`（乐观/基准/保守回收期分别为 **3.3 / 10.9 / 25.5月**）；"
            "仅 1 项落入 Tier-C：`#14 DP2-O3`（Base **4.2月**，IRR 42.4%）。\n"
        ),
    }
    res_bad = audit_roi_consistency(drafts=tampered_drafts, evaluated_opps=evaluated_opps)
    assert res_bad["roi_consistency_pass"] is False
    assert any(m["opp_id"] == "DP2-O3" for m in res_bad["mismatches"])
