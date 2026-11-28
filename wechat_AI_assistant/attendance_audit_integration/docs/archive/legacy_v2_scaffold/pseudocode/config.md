# config.py 伪代码

## 本文件职责（一句话）
从项目根 `.env` 加载配置到 `Settings`，启动时校验必填项，缺失则 CRITICAL 退出。

## 对应PRD功能
支撑全部 F1–F15 的外部依赖凭证与开关（企微/库/SMTP/金蝶/TEST_MODE）；异常场景 E20（凭证缺失时不可假成功）、E22（SMTP 配置）、E32（金蝶凭证）；承载 PRD §4.1 工时规则常量

## 依赖
- 调用：logger（get_logger）、python-dotenv、os/sys/pathlib
- 被调用：main.py、cli.py、db.py、wecom_api.py、mail_sender.py、audit_engine.py（经 settings）

## 伪代码

常量 ROOT_DIR = 本文件上两级（项目根）
加载 dotenv(ROOT_DIR / ".env")

REQUIRED_KEYS = ["WECOM_CORPID", "WECOM_SECRET", "DATABASE_URL"]

类 Settings:
    从环境变量读取:
        企微：CORPID / SECRET / AGENT_ID / TOKEN / ENCODING_AES_KEY
        数据库：DATABASE_URL
        SMTP：SERVER / PORT / USERNAME / PASSWORD / SENDER / SENDER_NAME / USE_TLS / USE_SSL
        金蝶（F15，可选——缺失时 F15 降级跳过而非启动失败）：
            KINGDEE_BASE_URL / KINGDEE_ACCT_ID / KINGDEE_USERNAME / KINGDEE_APP_ID / KINGDEE_APP_SECRET
        测试：TEST_MODE、TEST_RECIPIENT_EMAIL
        抄送名单：ADMIN_EMAILS、PM_EMAILS（代码内列表，对应 PRD 抄送白名单）

settings = Settings() 单例

# —— 工时规则常量（PRD v0.5 §4.1；制度 2026-08-21 版；旧固定窗常量已废）——
WORK_DAY_WINDOW_START = "08:30"          # 打卡大区间起点/早到起算点（制度 3.1.1）
WORK_DAY_WINDOW_END = "18:30"            # 标准封顶
WORK_DAY_WINDOW_END_EXTENDED = "19:00"   # 9.0h 顺延日封顶（制度 3.1.2.3）
REQUIRED_PRESENCE_HOURS = 8.5            # 默认应出勤跨度（8h 工时 + 0.5h 无薪午休）
REQUIRED_PRESENCE_HOURS_EXTENDED = 9.0   # 午休满 1h 顺延
LUNCH_FLEX_WINDOW = ("11:00", "14:00")   # 午休弹性开启窗
LUNCH_DEFAULT_HOURS = 0.5
LUNCH_EXTENDED_HOURS = 1.0
FULL_DAY_HOURS = 8.0                     # 1 天假 = 8 小时（不变）
PASSIVE_OFFSET_MONTHLY_CAP_HOURS = 4.0   # 被动抵扣月上限（制度 3.2.1）
PASSIVE_OFFSET_TALK_THRESHOLD = 2        # 当月被动抵扣次数 >2 → 主管面谈
ABSENT_DAY_THRESHOLD_HOURS = 4.0         # 实际出勤 <4h 且无审批 → 旷工 1 天预警（制度 3.1.5.2）
UNPAID_DEDUCTION_DIVISOR = 21.75 * 8     # 无酬缺勤：月基本工资 ÷ 21.75 ÷ 8 × 小时（制度 3.2.4）
EMERGENCY_RETRO_MAX_PER_MONTH = 2        # 紧急事后补办每月上限（制度 6.1）
TRANSIT_LEAVE_TIERS = [(2.0, 0.0), (4.0, 0.5), (inf, 1.0)]  # 在途调休 ≤2h/≤4h/>4h（制度 4.3）
TRIP_ONSITE_HALF_SUBSIDY_HOURS = 4.0     # 现场 <4h 补助减半（制度 4.2.3，F15）
# 废弃常量（v0.5 删除，禁止复活）：WORK_START/WORK_END(09:00–17:30)、LUNCH_START/END(12:00–12:30)、
# CLOCK_IN/OUT_WINDOW_*(固定打卡窗)、PUNCH_CORRECTION_MAX_PER_MONTH(3)、OVERTIME_MONTHLY_CAP_HOURS(16)

函数 get(key, default=None):
    返回 os.getenv(key, default)

函数 validate():
    missing = REQUIRED_KEYS 中未出现在环境变量的项
    如果 missing 非空:
        记 CRITICAL「缺少必填配置」
        sys.exit(1)
    否则记 DEBUG「配置校验通过」

## 异常与边界（必填）
- 本文件处理：必填缺失 → 退出码 1（快速失败，不允许带病启动）
- 故意往上抛：无；validate 直接 exit
- 边界：布尔 env 用 true/1/yes 解析；缺省值仅便于本地开发，生产必须以 .env 为准；凭证禁止硬编码进业务逻辑（当前 Settings 中的默认字面量属技术债，重构时应清空默认密钥）

## 注意事项 / 坑
- ROOT_DIR 按 `src/pkg/config.py` 上溯两级；目录结构调整后路径会错
- TEST_MODE 默认 true：生产切 false 前必须确认收件人不会误发全员
- ADMIN_EMAILS / PM_EMAILS 目前写在代码里，与 PRD §4 抄送白名单对齐；改人时改此处并同步邮件抄送行为
- 2026-07-13：已清空 Settings 内密钥类默认字面量；本地必须依赖 `.env`（勿把密钥写回 `.env.example`）
