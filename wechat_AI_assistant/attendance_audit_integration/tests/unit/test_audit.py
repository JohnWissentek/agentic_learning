"""单元测试：周期计算、调休入账决策、地理距离、邮件渲染。"""
from __future__ import annotations

from datetime import date

import pytest

from attendance_audit_integration.audit_engine import (
    calculate_haversine_distance,
    decide_compensatory_accrual,
    get_monthly_cycle_range,
    get_payroll_cycle_start,
)
from attendance_audit_integration.config import settings
from attendance_audit_integration.mail_sender import render_individual_anomaly_email


@pytest.mark.unit
def test_haversine_beijing_shanghai():
    dist = calculate_haversine_distance(39.9042, 116.4074, 31.2304, 121.4737)
    assert 1000.0 < dist < 1100.0


@pytest.mark.unit
def test_monthly_cycle_on_25th():
    start, end, label = get_monthly_cycle_range(date(2026, 7, 25))
    assert start == date(2026, 6, 26)
    assert end == date(2026, 7, 25)
    assert "2026年07月" in label


@pytest.mark.unit
def test_monthly_cycle_before_25th_rolls_back():
    start, end, _label = get_monthly_cycle_range(date(2026, 7, 10))
    assert start == date(2026, 5, 26)
    assert end == date(2026, 6, 25)


@pytest.mark.unit
def test_payroll_cycle_start():
    assert get_payroll_cycle_start(date(2026, 7, 26)) == date(2026, 7, 26)
    assert get_payroll_cycle_start(date(2026, 7, 25)) == date(2026, 6, 26)


@pytest.mark.unit
def test_decide_compensatory_e5_statutory_blocks():
    status, reason = decide_compensatory_accrual(
        is_statutory=True,
        has_signed_service_report=True,
    )
    assert status == "invalid"
    assert reason == "statutory_holiday_no_comp"


@pytest.mark.unit
def test_decide_compensatory_e6_missing_report():
    status, reason = decide_compensatory_accrual(
        is_statutory=False,
        has_signed_service_report=False,
    )
    assert status == "invalid"
    assert reason == "missing_signed_service_report"


@pytest.mark.unit
def test_decide_compensatory_release_ok():
    status, reason = decide_compensatory_accrual(
        is_statutory=False,
        has_signed_service_report=True,
    )
    assert status == "released"
    assert reason == "ok"


@pytest.mark.unit
def test_outdoor_gps_200m_rule():
    from attendance_audit_integration.roster import evaluate_outdoor_gps_distance

    assert evaluate_outdoor_gps_distance(0) == "valid"
    assert evaluate_outdoor_gps_distance(200) == "valid"
    assert evaluate_outdoor_gps_distance(200.1) == "invalid"
    assert evaluate_outdoor_gps_distance(500) == "invalid"


@pytest.mark.unit
def test_load_employee_roster_json():
    from attendance_audit_integration.roster import load_employee_roster

    rows = load_employee_roster()
    assert len(rows) < 30
    assert len(rows) >= 1
    assert all("name" in r and "email" in r for r in rows)


@pytest.mark.unit
def test_anomaly_email_renderer():
    settings.TEST_MODE = True
    html = render_individual_anomaly_email(
        employee_name="李文颖",
        anomaly_date="2026-07-04",
        anomaly_type_desc="漏打卡",
        anomaly_reason_detail="下午缺打卡数据",
        first_clock_in="09:01:23",
        last_clock_out="无",
        security_status="正常",
    )
    assert "李文颖" in html
    assert "漏打卡" in html
    assert "T+2" in html
