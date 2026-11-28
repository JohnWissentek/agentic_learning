"""调休入账决策（PRD F5/F6 / E5/E6）。

判定加班是否可转入调休假余额:
- 法定节假日加班 → 禁止转调休（E5），仅记加班费工时
- 非法定假加班但缺客户手写签字服务报告 → 拒绝生成调休（E6）
- 有审批+有签字报告 → released，入 compensatory_leave_details
"""
from __future__ import annotations


def decide_compensatory_accrual(
    *,
    is_statutory: bool,
    has_signed_service_report: bool,
) -> tuple[str, str]:
    """决定加班是否可转入调休。

    Returns:
        (status, reason_code):
        - ``("released", "ok")`` — 可入调休
        - ``("invalid", "statutory_holiday_no_comp")`` — 法定假禁止转调休 (E5)
        - ``("invalid", "missing_signed_service_report")`` — 缺签字服务报告 (E6)
    """
    if is_statutory:
        return "invalid", "statutory_holiday_no_comp"
    if not has_signed_service_report:
        return "invalid", "missing_signed_service_report"
    return "released", "ok"
