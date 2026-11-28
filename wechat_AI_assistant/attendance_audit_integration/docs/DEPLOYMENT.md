# 部署与运维指南（DEPLOYMENT.md）

> **系统名称**：`attendance_audit_integration`（企业微信考勤审计集成系统）  
> **最后校准**：2026-11-29（与真实代码 `db.py` / `cli.py` / `main.py` / `config.py` / `docker-compose.yml` 逐项对齐）  
> **安全红线**：本文档禁止包含真实密钥、数据库密码或业务 Token；所有生产凭证一律保存在服务器本地 `.env`（已被 `.gitignore` 忽略）。

---

## 1. 运行环境与架构

- **部署方式**：Docker Compose（单容器 `wecom-attendance-app`，端口 `8000`）+ 宿主机 Cron 调用 CLI
- **依赖服务**：
  - 共享 PostgreSQL 容器（外部 Docker 网络 `docker_wissentek`）
  - 企业微信 OpenAPI（公网出口 IP 需加入企微「企业可信 IP」白名单）
  - 企业邮箱 SMTP（告警与报表邮件发送）
  - 金蝶云星空 Web API（二阶段可选，阶段一留空自动降级跳过）

---

## 2. 环境变量配置（`.env`）

以项目根目录 [`.env.example`](../.env.example) 为准复制生成 `.env`：

```ini
# --- 企业微信 API（必填）---
WECOM_CORPID=<your_corpid>
WECOM_SECRET=<your_app_secret>
WECOM_AGENT_ID=<your_agent_id>

# --- 企微审批事件回调加解密（可选；缺失时回调接口降级返回 503，不影响日/周/月审）---
WECOM_TOKEN=<your_callback_token>
WECOM_ENCODING_AES_KEY=<your_43_char_aes_key>

# --- 企微汇报/日报模板 ID（可选；用于 F4 出差日报拉取）---
WECOM_DAILY_REPORT_TEMPLATE_ID=<your_journal_template_id>

# --- PostgreSQL 数据库连接（必填）---
DATABASE_URL=postgresql://<db_user>:<db_password>@<db_host>:5432/wecom_attendance

# --- SMTP 邮件配置（变量名以 config.py 为准）---
SMTP_SERVER=smtp.exmail.qq.com
SMTP_PORT=465
SMTP_USERNAME=<your_smtp_user>
SMTP_PASSWORD=<your_smtp_password>
SMTP_SENDER=<your_sender_email>
SMTP_SENDER_NAME=考勤审计助手
SMTP_USE_TLS=false
SMTP_USE_SSL=true

# --- 测试模式拦截（生产上线务必设为 false）---
TEST_MODE=true
TEST_RECIPIENT_EMAIL=<test_receiver_email>

# --- 本地花名册 JSON（默认 data/employee_roster.json）---
# EMPLOYEE_ROSTER_PATH=

# --- 金蝶云星空只读接入（二阶段 F15，一阶段留空）---
KINGDEE_BASE_URL=
KINGDEE_ACCT_ID=
KINGDEE_USERNAME=
KINGDEE_APP_ID=
KINGDEE_APP_SECRET=
# KINGDEE_EXPENSE_FORM_ID=ER_ExpenseRequest

LOG_LEVEL=INFO
```

> 抄送白名单（`ADMIN_EMAILS`、`PM_EMAILS`、`F11_CC_EMAILS`）与考核排除名单（`EXCLUDED_NAMES`）当前定义在 `src/attendance_audit_integration/config.py`，修改人员时需同步更新 `docs/PRD.md`。

---

## 3. 真实数据库表结构（`src/attendance_audit_integration/db.py`）

执行 `init-db`（或容器启动 `lifespan`）会自动幂等创建以下 **12 张表**：

| 表名 | 用途 | 关键幂等/唯一键 |
|---|---|---|
| `employees` | 员工花名册映射（企微通讯录 + 本地 JSON 邮箱） | `wecom_userid` UNIQUE |
| `attendance_logs` | 原始打卡流水（上下班/外勤、经纬度、`exception_type`、`raw_payload`） | `(wecom_userid, clock_time, clock_type)` |
| `approvals` | 审批单据（请假/出差/加班/补卡，状态与时长） | `approval_no` UNIQUE |
| `field_work_reports` | 出差/现场工作日报（含 `raw_payload`） | `report_no` UNIQUE |
| `service_reports` | 客户手写签字技术服务报告 | `report_no` UNIQUE |
| `daily_attendance` | 每日审计结果表（首末打卡、状态、异常标记与原因） | `(wecom_userid, attendance_date)` |
| `compensatory_leave_details` | 调休工时入账/消耗/有效期流水明细 | `id` |
| `vacation_balances` | 员工年假/调休余额汇总（`remaining` 自动计算列） | `(wecom_userid, leave_type)` |
| `national_holidays` | 法定节假日与调班工作日日历（人工维护） | `holiday_date` UNIQUE |
| `audit_logs` | 人工调账与审计操作不可篡改日志 | `id` |
| `test_data_provenance` | 测试造数溯源登记表（仅登记 mock 行，防止污染真实数据） | `(table_name, record_pk)` |
| `payroll_period_locks` | 薪资周期（上月26日–本月25日）月审终审封账锁 | `(period_start, period_end)` |

---

## 4. 构建、启动与初始化

```bash
# 1. 构建并后台启动容器（容器名：wecom-attendance-app）
docker-compose down
docker-compose up --build -d

# 2. 检查容器状态与日志
docker-compose ps
docker logs -f --tail=100 wecom-attendance-app

# 3. 首次建表（或升级表结构）
docker exec wecom-attendance-app python -m attendance_audit_integration.cli init-db

# 4. 首次同步企微花名册
docker exec wecom-attendance-app python -m attendance_audit_integration.cli sync-roster
```

---

## 5. CLI 命令与 Crontab 生产调度

真实 CLI 入口为 `python -m attendance_audit_integration.cli`（定义在 `src/attendance_audit_integration/cli.py`）：

| 子命令 | 说明 | 示例 |
|---|---|---|
| `init-db` | 初始化 PostgreSQL 表结构 | `... cli init-db` |
| `sync-roster` | 同步企微通讯录与本地 JSON 花名册 | `... cli sync-roster` |
| `daily [--date YYYY-MM-DD]` | 执行日审（默认昨日 T-1）并发送异常/汇总邮件 | `... cli daily --date 2026-08-26` |
| `weekly` | 执行周审汇总邮件 | `... cli weekly` |
| `check-expiry` | 扫描调休入账后 7/15/30 天未用完提醒（F11，仅发 PM） | `... cli check-expiry` |
| `vacation-audit [--no-email]` | 只读拉取企微假期配置与全员余额，检出调休堆积/年假偏高/离职残留/病假 0 限额风险 | `... cli vacation-audit` |
| `monthly [--date YYYY-MM-DD] [--sync] [--final]` | 执行月审（加 `--sync` 先同步周期审批/汇报/余额；加 `--final` 执行终审封账） | `... cli monthly --sync --final` |
| `expense-cross [--date YYYY-MM-DD]` | 金蝶差旅补助交叉审计（二阶段 F15，只读） | `... cli expense-cross` |

推荐宿主机 Crontab（与 `PRD.md` §4.1 对齐）：

```cron
# 每日 09:00：执行昨日（T-1）日审并发送告警与公司日报
0 9 * * * docker exec wecom-attendance-app python -m attendance_audit_integration.cli daily

# 每周一 09:30：检查调休逾期催用 + 同步企微真实假期余额堆积审计（仅发 PM/HR）
30 9 * * 1 docker exec wecom-attendance-app python -m attendance_audit_integration.cli check-expiry
35 9 * * 1 docker exec wecom-attendance-app python -m attendance_audit_integration.cli vacation-audit

# 每周一 10:00：执行上周考勤汇总周报
0 10 * * 1 docker exec wecom-attendance-app python -m attendance_audit_integration.cli weekly

# 每月 25 日 18:00：前置同步并生成本薪资周期（上月26日–本月25日）月审草稿
0 18 25 * * docker exec wecom-attendance-app python -m attendance_audit_integration.cli monthly --sync

# 每月 26 日 18:00：执行月审终审并锁定周期（须 HR 确认异常已核销后启用，或改为人工触发）
# 0 18 26 * * docker exec wecom-attendance-app python -m attendance_audit_integration.cli monthly --final
```

---

## 6. HTTP 服务接口（`src/attendance_audit_integration/main.py`）

容器暴露 `8000` 端口，提供以下主要端点：

- `GET /`：健康检查
- `GET /webhooks/approval` & `POST /webhooks/approval`：企业微信审批状态变更回调（`sys_approval_change`）
- `POST /audit/run`：手动触发日审或月审终审
- `POST /audit/weekly`、`POST /audit/monthly`、`POST /audit/check_expiry`、`POST /audit/vacation`：手动触发周审/月审/调休催用/企微假期余额与堆积审计
- `GET/POST/DELETE /holidays`、`POST /holidays/seed/{year}`、`POST /holidays/annual_reminder`：法定节假日日历维护
- `POST /test/send_email`：测试 SMTP 连通性

---

## 7. 诊断与本地测试

```bash
# 导出脱敏自检诊断包
docker exec wecom-attendance-app python -m attendance_audit_integration.diagnostics

# 本地运行单元测试（含架构图↔代码溯源对账门禁）
PYTHONPATH=src pytest -m unit
```
