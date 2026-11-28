"""Phase 4 补充测试：PRD 异常场景与框架合规检查。

test markers (in pyproject.toml):
  unit    — 纯逻辑，无外部依赖
"""
from __future__ import annotations

from datetime import date

import pytest


# ── geo.py 测试 ──────────────────────────────────────────────────

class TestGeoModule:
    """geo.py — Haversine 距离计算的边界场景。"""

    def test_haversine_same_point_returns_zero(self):
        """同一坐标距离 = 0。"""
        from attendance_audit_integration.geo import calculate_haversine_distance

        assert calculate_haversine_distance(39.9042, 116.4074, 39.9042, 116.4074) == 0.0

    def test_haversine_known_distance_beijing_shanghai(self):
        """北京-上海直线 ~1068 km。"""
        from attendance_audit_integration.geo import calculate_haversine_distance

        dist = calculate_haversine_distance(39.9042, 116.4074, 31.2304, 121.4737)
        assert 1050 < dist < 1090

    def test_haversine_anti_meridian(self):
        """跨国际日期变更线仍正确（东京 → 洛杉矶）。"""
        from attendance_audit_integration.geo import calculate_haversine_distance

        dist = calculate_haversine_distance(35.6762, 139.6503, 34.0522, -118.2437)
        assert 8700 < dist < 9000

    def test_haversine_symmetry(self):
        """distance(A, B) == distance(B, A)。"""
        from attendance_audit_integration.geo import calculate_haversine_distance

        d1 = calculate_haversine_distance(39.9, 116.4, 31.2, 121.5)
        d2 = calculate_haversine_distance(31.2, 121.5, 39.9, 116.4)
        assert abs(d1 - d2) < 0.001


# ── compensatory.py 测试 ─────────────────────────────────────────

class TestCompensatoryDecisions:
    """compensatory.py — 调休入账决策（纯函数）。"""

    def test_e5_statutory_holiday_blocks(self):
        """E5: 法定节假日加班禁止转调休。"""
        from attendance_audit_integration.compensatory import decide_compensatory_accrual

        status, code = decide_compensatory_accrual(
            is_statutory=True, has_signed_service_report=True
        )
        assert status == "invalid"
        assert code == "statutory_holiday_no_comp"

    def test_e6_missing_report_blocks(self):
        """E6: 非法定假加班但缺签字报告 → 拒绝。"""
        from attendance_audit_integration.compensatory import decide_compensatory_accrual

        status, code = decide_compensatory_accrual(
            is_statutory=False, has_signed_service_report=False
        )
        assert status == "invalid"
        assert code == "missing_signed_service_report"

    def test_happy_path_releases(self):
        """非法定假 + 有签字报告 → released。"""
        from attendance_audit_integration.compensatory import decide_compensatory_accrual

        status, code = decide_compensatory_accrual(
            is_statutory=False, has_signed_service_report=True
        )
        assert status == "released"
        assert code == "ok"

    def test_e5_overrides_e6(self):
        """法定假禁止转调休优先于签字报告状态（is_statutory=True, report=False）。"""
        from attendance_audit_integration.compensatory import decide_compensatory_accrual

        status, code = decide_compensatory_accrual(
            is_statutory=True, has_signed_service_report=False
        )
        assert status == "invalid"
        assert code == "statutory_holiday_no_comp"  # E5 优先于 E6


# ── payroll_cycle.py 测试 ────────────────────────────────────────

class TestPayrollCycle:
    """payroll_cycle.py — 薪资周期日期计算。"""

    def test_cycle_start_day_26_or_later(self):
        """当日 ≥ 26 → 周期起始 = 本月 26 日。"""
        from attendance_audit_integration.payroll_cycle import get_payroll_cycle_start

        assert get_payroll_cycle_start(date(2026, 7, 26)) == date(2026, 7, 26)
        assert get_payroll_cycle_start(date(2026, 7, 31)) == date(2026, 7, 26)

    def test_cycle_start_day_before_26(self):
        """当日 < 26 → 周期起始 = 上月 26 日。"""
        from attendance_audit_integration.payroll_cycle import get_payroll_cycle_start

        assert get_payroll_cycle_start(date(2026, 7, 1)) == date(2026, 6, 26)
        assert get_payroll_cycle_start(date(2026, 7, 25)) == date(2026, 6, 26)

    def test_monthly_cycle_range_on_25th(self):
        """25 日 → end=本月25, start=上月26。"""
        from attendance_audit_integration.payroll_cycle import get_monthly_cycle_range

        start, end, label = get_monthly_cycle_range(date(2026, 7, 25))
        assert start == date(2026, 6, 26)
        assert end == date(2026, 7, 25)
        assert "07" in label

    def test_monthly_cycle_range_before_25th(self):
        """25 日之前 → end=上月25, start=上上月26。"""
        from attendance_audit_integration.payroll_cycle import get_monthly_cycle_range

        start, end, label = get_monthly_cycle_range(date(2026, 7, 10))
        assert end == date(2026, 6, 25)
        assert start == date(2026, 5, 26)

    def test_cycle_start_january(self):
        """跨年场景: 2026-01-10 → 上月=2025-12, 周期起始=2025-12-26。"""
        from attendance_audit_integration.payroll_cycle import get_payroll_cycle_start

        assert get_payroll_cycle_start(date(2026, 1, 10)) == date(2025, 12, 26)


# ── wecom_api.py 重试逻辑测试 ────────────────────────────────────

class TestRetryLogic:
    """wecom_api._retry_request — 指数退避重试。"""

    def test_retry_request_import(self):
        """_retry_request 函数可导入。"""
        from attendance_audit_integration.wecom_api import _retry_request

        assert callable(_retry_request)


# ── config.py 排除名单配置 ───────────────────────────────────────

class TestExclusionConfig:
    """config.py — 硬编码值已移入配置。"""

    def test_excluded_names_exist(self):
        """EXCLUDED_NAMES 列表已定义。"""
        from attendance_audit_integration.config import settings

        assert hasattr(settings, "EXCLUDED_NAMES")
        assert isinstance(settings.EXCLUDED_NAMES, list)
        assert len(settings.EXCLUDED_NAMES) > 0

    def test_excluded_userids_exist(self):
        """EXCLUDED_USERIDS 列表已定义。"""
        from attendance_audit_integration.config import settings

        assert hasattr(settings, "EXCLUDED_USERIDS")
        assert isinstance(settings.EXCLUDED_USERIDS, list)

    def test_company_names_exist(self):
        """DEFAULT_COMPANY_A/B 配置项已定义。"""
        from attendance_audit_integration.config import settings

        assert settings.DEFAULT_COMPANY_A
        assert settings.DEFAULT_COMPANY_B


# ── audit_engine.py 门面兼容性测试 ───────────────────────────────

class TestAuditEngineFacade:
    """audit_engine.py — 门面类向后兼容性。"""

    def test_facade_class_exists(self):
        """AuditEngine 类仍可从 audit_engine 导入。"""
        from attendance_audit_integration.audit_engine import AuditEngine

        assert AuditEngine is not None

    def test_facade_instance_exists(self):
        """audit_engine 单例仍可从 audit_engine 导入。"""
        from attendance_audit_integration.audit_engine import audit_engine

        assert audit_engine is not None

    def test_facade_re_exports_geo(self):
        """Haversine 函数可从旧路径导入。"""
        from attendance_audit_integration.audit_engine import calculate_haversine_distance

        assert callable(calculate_haversine_distance)

    def test_facade_re_exports_holiday(self):
        """Holiday 函数可从旧路径导入。"""
        from attendance_audit_integration.audit_engine import is_workday_db, seed_national_holidays

        assert callable(is_workday_db)
        assert callable(seed_national_holidays)

    def test_facade_re_exports_payroll_cycle(self):
        """Payroll cycle 函数可从旧路径导入。"""
        from attendance_audit_integration.audit_engine import (
            get_monthly_cycle_range,
            get_payroll_cycle_start,
        )

        assert callable(get_monthly_cycle_range)
        assert callable(get_payroll_cycle_start)

    def test_facade_re_exports_compensatory(self):
        """Compensatory 函数可从旧路径导入。"""
        from attendance_audit_integration.audit_engine import decide_compensatory_accrual

        assert callable(decide_compensatory_accrual)


# ── 外勤 GPS 围栏 (E14) ─────────────────────────────────────────

class TestGPSFence:
    """PRD F13 / E14 — GPS 围栏半径 ≤200m 有效。"""

    def test_200m_exactly_valid(self):
        """恰好 200m 应判定有效。"""
        from attendance_audit_integration.roster import evaluate_outdoor_gps_distance

        result = evaluate_outdoor_gps_distance(200.0)
        assert result == "valid"

    def test_201m_invalid(self):
        """201m 应判定无效。"""
        from attendance_audit_integration.roster import evaluate_outdoor_gps_distance

        result = evaluate_outdoor_gps_distance(201.0)
        assert result == "invalid"

    def test_0m_valid(self):
        """0m 应判定有效。"""
        from attendance_audit_integration.roster import evaluate_outdoor_gps_distance

        result = evaluate_outdoor_gps_distance(0.0)
        assert result == "valid"


# ── 瞬移检测 (E12) ──────────────────────────────────────────────

class TestTeleportDetection:
    """PRD F2 / E12 — 相邻打卡时速 > 350 km/h = 虚拟定位。"""

    def test_speed_within_limit(self):
        """100 km in 1h = 100 km/h → 正常。"""
        from attendance_audit_integration.geo import calculate_haversine_distance

        # 北京市内两个约 10km 的点
        d = calculate_haversine_distance(39.9042, 116.4074, 39.99, 116.45)
        # 假设 1 小时, speed < 350
        assert d / 1.0 < 350

    def test_teleportation_detected(self):
        """北京→上海 ~1068 km in 0.5h = ~2136 km/h → 瞬移。"""
        from attendance_audit_integration.geo import calculate_haversine_distance

        d = calculate_haversine_distance(39.9042, 116.4074, 31.2304, 121.4737)
        speed = d / 0.5
        assert speed > 350


# ── F11 催用收件人验证（PRD v0.4）────────────────────────────────

class TestF11RecipientPolicy:
    """PRD v0.4 §4.2：调休催用 TO=PM（孔紫初、王楠），CC=徐宏玮+薛蕾，禁止发被催员工。"""

    def test_pm_emails_has_kong_and_wang(self):
        """PM_EMAILS 必须包含孔紫初和王楠的邮箱。"""
        from attendance_audit_integration.config import settings

        pm = settings.PM_EMAILS
        assert len(pm) >= 2
        pm_lower = [e.lower() for e in pm]
        assert any("kong" in e for e in pm_lower), "PM_EMAILS 缺少孔紫初"
        assert any("wangnan" in e for e in pm_lower), "PM_EMAILS 缺少王楠"

    def test_f11_cc_emails_has_xu_and_xue(self):
        """F11_CC_EMAILS 必须包含徐宏玮和薛蕾的邮箱。"""
        from attendance_audit_integration.config import settings

        cc = settings.F11_CC_EMAILS
        assert len(cc) >= 2
        cc_lower = [e.lower() for e in cc]
        assert any("john.xu" in e or "xuhongwei" in e for e in cc_lower), "F11_CC_EMAILS 缺少徐宏玮"
        assert any("xuelei" in e for e in cc_lower), "F11_CC_EMAILS 缺少薛蕾"

    def test_expiry_checker_does_not_email_employee(self):
        """expiry_checker 催用代码中不应出现 to_email=email 模式。"""
        import ast
        from pathlib import Path

        src = Path(__file__).resolve().parents[2] / "src" / "attendance_audit_integration" / "services" / "expiry_checker.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "to_email":
                if isinstance(node.value, ast.Name) and node.value.id == "email":
                    pytest.fail(
                        "expiry_checker.py 中 to_email=email 违反 PRD v0.4："
                        "催用禁止发给被催员工！"
                    )

    def test_expiry_checker_uses_pm_and_f11_cc(self):
        """expiry_checker 催用应使用 PM_EMAILS + F11_CC_EMAILS。"""
        from pathlib import Path

        src = Path(__file__).resolve().parents[2] / "src" / "attendance_audit_integration" / "services" / "expiry_checker.py"
        code = src.read_text(encoding="utf-8")
        assert "PM_EMAILS" in code, "expiry_checker.py 应引用 PM_EMAILS"
        assert "F11_CC_EMAILS" in code, "expiry_checker.py 应引用 F11_CC_EMAILS"


# ── PRD v0.5 工时硬参数常量（制度 2026-08-21 民主确认版）─────────

class TestWorkHourConstants:
    """config.py 须包含 PRD v0.5 §4.1 的全部硬参数；旧固定窗常量必须已删除。"""

    def test_work_day_window(self):
        from attendance_audit_integration.config import settings

        assert settings.WORK_DAY_WINDOW_START == "08:30"
        assert settings.WORK_DAY_WINDOW_END == "18:30"
        assert settings.WORK_DAY_WINDOW_END_EXTENDED == "19:00"

    def test_required_presence_hours(self):
        from attendance_audit_integration.config import settings

        assert settings.REQUIRED_PRESENCE_HOURS == 8.5
        assert settings.REQUIRED_PRESENCE_HOURS_EXTENDED == 9.0

    def test_lunch_flex_window(self):
        from attendance_audit_integration.config import settings

        assert settings.LUNCH_FLEX_START == "11:00"
        assert settings.LUNCH_FLEX_END == "14:00"
        assert settings.LUNCH_DEFAULT_HOURS == 0.5
        assert settings.LUNCH_EXTENDED_HOURS == 1.0

    def test_full_day_hours(self):
        from attendance_audit_integration.config import settings

        assert settings.FULL_DAY_HOURS == 8.0

    def test_passive_offset_cap(self):
        from attendance_audit_integration.config import settings

        assert settings.PASSIVE_OFFSET_MONTHLY_CAP_HOURS == 4.0
        assert settings.PASSIVE_OFFSET_TALK_THRESHOLD_COUNT == 2

    def test_absent_and_deduction_rules(self):
        from attendance_audit_integration.config import settings

        assert settings.ABSENT_DAY_THRESHOLD_HOURS == 4.0
        assert settings.MONTHLY_SALARY_DAY_DIVISOR == 21.75

    def test_retro_and_transit_rules(self):
        from attendance_audit_integration.config import settings

        assert settings.EMERGENCY_RETRO_MAX_PER_MONTH == 2
        assert settings.TRANSIT_LEAVE_SHORT_HOURS == 2.0
        assert settings.TRANSIT_LEAVE_HALF_DAY_HOURS == 4.0
        assert settings.TRIP_ONSITE_HALF_SUBSIDY_HOURS == 4.0

    def test_legacy_constants_removed(self):
        """旧制度常量（固定工时/打卡窗/补卡3次/加班16h）必须已删除，禁止复活。"""
        from attendance_audit_integration.config import settings

        for legacy_name in (
            "WORK_START", "WORK_END", "LUNCH_START", "LUNCH_END",
            "CLOCK_IN_WINDOW_START", "CLOCK_IN_WINDOW_END",
            "CLOCK_OUT_WINDOW_START", "CLOCK_OUT_WINDOW_END",
            "PUNCH_CORRECTION_MAX_PER_MONTH", "OVERTIME_MONTHLY_CAP_HOURS",
        ):
            assert not hasattr(settings, legacy_name), (
                "旧口径常量 %s 应已随 PRD v0.5 删除" % legacy_name
            )
