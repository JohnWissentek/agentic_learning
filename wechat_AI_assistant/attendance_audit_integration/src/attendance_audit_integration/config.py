"""配置加载（框架标准件）。

- 从项目根目录 .env 读取配置（python-dotenv）
- 必填项缺失时启动即报错退出（CRITICAL）
- 凭证默认值一律为空：禁止在源码中硬编码密钥
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from attendance_audit_integration.logger import get_logger

logger = get_logger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

# 必填配置项校验清单（对应 PRD §5）
REQUIRED_KEYS: list[str] = [
    "WECOM_CORPID",
    "WECOM_SECRET",
    "DATABASE_URL",
]


def _env_bool(key: str, default: str = "false") -> bool:
    return os.getenv(key, default).lower() in ("true", "1", "yes")


def _env_int(key: str, default: str) -> int:
    raw = os.getenv(key, default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.critical("配置项 %s 必须是整数，当前值=%r", key, raw)
        sys.exit(1)


class Settings:
    """运行时配置。密钥类字段无源码默认值，必须来自 .env。"""

    WECOM_CORPID: str = os.getenv("WECOM_CORPID", "")
    WECOM_SECRET: str = os.getenv("WECOM_SECRET", "")
    WECOM_AGENT_ID: int = _env_int("WECOM_AGENT_ID", "0")

    WECOM_TOKEN: str = os.getenv("WECOM_TOKEN", "")
    WECOM_ENCODING_AES_KEY: str = os.getenv("WECOM_ENCODING_AES_KEY", "")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "")
    SMTP_PORT: int = _env_int("SMTP_PORT", "587")
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_SENDER: str = os.getenv("SMTP_SENDER", "")
    SMTP_SENDER_NAME: str = os.getenv("SMTP_SENDER_NAME", "")
    SMTP_USE_TLS: bool = _env_bool("SMTP_USE_TLS", "true")
    SMTP_USE_SSL: bool = _env_bool("SMTP_USE_SSL", "false")

    TEST_MODE: bool = _env_bool("TEST_MODE", "true")
    TEST_RECIPIENT_EMAIL: str = os.getenv("TEST_RECIPIENT_EMAIL", "")

    # 企微日报模板 ID（F4，可选覆盖；留空时默认遍历 WECOM_JOURNAL_TEMPLATES 全部 6 个启用模板）
    WECOM_DAILY_REPORT_TEMPLATE_ID: str = os.getenv("WECOM_DAILY_REPORT_TEMPLATE_ID", "")

    # ── 维恩科仪企微现网真实模板 ID（2026-11-29 后台只读实盘盘点，见 wecom_live_inventory.md）──
    WECOM_APPROVAL_TEMPLATES: dict[str, str] = {
        "leave": "Bs8114rcQrU1NHmkaEctMKKRDqSCo9YEdCeLAfjmv",            # 请假
        "punch_correction": "Bs7zz7rsMzoj5roRdLbs2anYNgm3L1ifMq442xHMZ",  # 打卡补卡
        "overtime": "C4NvrtgmDKznbXFJCKEw5XGNyrw6dhLquQuNkq8Ze",          # 加班申请
        "outing": "3WK7K6pXKXzaUwzDh9KmqtjXGUvMThtDGwHAKzHo",             # 外出申请
        "business_trip": "ZvVcpYA7cWdCjM3hr8aDhde5CXcYfGw2pVhiDP",        # 出差申请
    }

    WECOM_JOURNAL_TEMPLATES: dict[str, str] = {
        "field_service_report": "C4ZW7hqyqemoDeSFqoGAyEoGMB1HdvfE78qzTv58B",  # 现场技术支持工作报告（含手写签名）
        "field_daily_report": "3WPHEvoCeoDFheRgDUVsyjpSUpfFr2WimsxeXGQ3",    # 现场每日10分钟工作报告
        "rd_maintenance_daily": "3WN63QNme5LesazCsN6TrsJsF4G5ZGW6wNt5ryB8",  # 研发性能测试/返厂维护日报
        "general_daily_report": "C4c9RoeekLMSRRcqyurjgee3x7c6MUgPqN96rLmFr",  # 每日10分钟工作日报
        "finance_daily_report": "3WPHEvnos5s9srSXWAqcs5hUgib4WwJYkb8yxAsZ",  # 财务每日10分钟工作简报
        "morning_briefing": "3WNhb5shbwE39YGY3xP8Uds7zUQCF8kNxKkYyWaP",      # 晨会简报（含请假/倒休/出差名单）
    }

    # ── 企微现网真实假期 ID（纠正旧文档误写：4 为调休假，2 为事假）──
    WECOM_VACATION_ID_ANNUAL: int = 1
    WECOM_VACATION_ID_PERSONAL: int = 2
    WECOM_VACATION_ID_SICK: int = 3
    WECOM_VACATION_ID_COMPENSATORY: int = 4
    VACATION_COMP_BACKLOG_WARN_HOURS: float = 32.0   # 调休堆积预警线（4 天）
    VACATION_ANNUAL_HIGH_WARN_HOURS: float = 40.0    # 年假偏高核查线（5 天）

    # 与 PRD §4 抄送白名单对齐（改人时同步 PRD 变更记录）
    ADMIN_EMAILS: list[str] = [
        "john.xu@palmarytech.com",  # 徐宏玮
        "xuelei@palmarytech.com",  # 薛蕾
        "wangxiao@palmarytech.com",  # 王晓
        "steffi@palmarytech.com",  # 杨丽丽
    ]

    PM_EMAILS: list[str] = [
        "winni-zichu.kong@wissentek.com",  # 孔紫初
        "wangnan@palmarytech.com",  # 王楠
    ]

    # F11 催用抄送白名单（PRD v0.4：TO=PM，CC=徐宏玮+薛蕾，禁止发/抄送被催员工）
    F11_CC_EMAILS: list[str] = [
        "john.xu@palmarytech.com",  # 徐宏玮
        "xuelei@palmarytech.com",  # 薛蕾
    ]

    # 公司名称（花名册同步默认值，PRD §4 / F8）
    DEFAULT_COMPANY_A: str = "北京帕莫瑞科技有限公司"
    DEFAULT_COMPANY_B: str = "维恩科仪（北京）机械自动化设备有限公司"

    # 考核排除名单（PRD §4.1：不参与日/月缺卡考核）
    EXCLUDED_NAMES: list[str] = ["徐宏玮", "杨丽丽"]
    EXCLUDED_USERIDS: list[str] = ["XuHongWei", "YangLiLi"]

    # ── 金蝶云星空只读接入（F15；可选——缺失时交叉审计降级跳过）──
    KINGDEE_BASE_URL: str = os.getenv("KINGDEE_BASE_URL", "")
    KINGDEE_ACCT_ID: str = os.getenv("KINGDEE_ACCT_ID", "")
    KINGDEE_USERNAME: str = os.getenv("KINGDEE_USERNAME", "")
    KINGDEE_APP_ID: str = os.getenv("KINGDEE_APP_ID", "")
    KINGDEE_APP_SECRET: str = os.getenv("KINGDEE_APP_SECRET", "")
    KINGDEE_EXPENSE_FORM_ID: str = os.getenv("KINGDEE_EXPENSE_FORM_ID", "ER_ExpenseRequest")

    # ── 一期硬参数（PRD v0.5 §4.1；制度 2026-08-21 民主确认版）──
    # 打卡大区间与封顶（制度 3.1.1）：无固定上/下班窗，入口不关停
    WORK_DAY_WINDOW_START: str = "08:30"
    WORK_DAY_WINDOW_END: str = "18:30"
    WORK_DAY_WINDOW_END_EXTENDED: str = "19:00"  # 9.0h 顺延日封顶
    # 动态工时：下班基准 = max(上班卡, 08:30) + 应出勤跨度
    REQUIRED_PRESENCE_HOURS: float = 8.5   # 8h 工时 + 0.5h 无薪午休
    REQUIRED_PRESENCE_HOURS_EXTENDED: float = 9.0  # 用餐+小憩满 1h 顺延（制度 3.1.2.3）
    LUNCH_FLEX_START: str = "11:00"
    LUNCH_FLEX_END: str = "14:00"
    LUNCH_DEFAULT_HOURS: float = 0.5
    LUNCH_EXTENDED_HOURS: float = 1.0
    FULL_DAY_HOURS: float = 8.0  # 1 天假 = 8 小时
    # 被动抵扣与缺勤（制度 3.2.1 / 3.1.5.2 / 3.2.4）
    PASSIVE_OFFSET_MONTHLY_CAP_HOURS: float = 4.0
    PASSIVE_OFFSET_TALK_THRESHOLD_COUNT: int = 2  # 当月被动抵扣 >2 次 → 主管面谈
    ABSENT_DAY_THRESHOLD_HOURS: float = 4.0  # 实际出勤 <4h 且无审批 → 旷工 1 天预警
    MONTHLY_SALARY_DAY_DIVISOR: float = 21.75  # 无酬缺勤 = 月基本工资÷21.75÷8×缺勤小时
    # 补办与在途调休（制度 6.1 / 4.3）
    EMERGENCY_RETRO_MAX_PER_MONTH: int = 2
    TRANSIT_LEAVE_SHORT_HOURS: float = 2.0    # 单程 ≤2h 不计在途调休
    TRANSIT_LEAVE_HALF_DAY_HOURS: float = 4.0  # >2h 且 ≤4h → 0.5 天；>4h → 1 天
    # 差旅补助减半（制度 4.2.3，F15）
    TRIP_ONSITE_HALF_SUBSIDY_HOURS: float = 4.0
    # 旧口径常量（09:00–17:30 固定工时/打卡窗/补卡月 3 次/加班月 16h）已随
    # PRD v0.5 作废删除，禁止复活；历史见 docs/archive 与 PRD 变更记录 v0.4


settings = Settings()


def get(key: str, default: str | None = None) -> str | None:
    return os.getenv(key, default)


def validate() -> None:
    """启动时校验必填配置，缺失则退出。"""
    missing = [k for k in REQUIRED_KEYS if not os.getenv(k)]
    if missing:
        logger.critical("缺少必填配置项: %s，请检查 .env 文件", ", ".join(missing))
        sys.exit(1)
    logger.debug("配置校验通过，共 %d 个必填项", len(REQUIRED_KEYS))
