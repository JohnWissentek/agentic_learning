# db.py 伪代码

## 本文件职责（一句话）
提供 PostgreSQL 连接，并用 `CREATE TABLE IF NOT EXISTS` 初始化全部业务表 Schema。

## 对应PRD功能
F1、F2、F4–F9、F14 的持久化底座；异常场景 E18（封账相关表/审计痕迹）、E21（employees）、E23（唯一约束幂等）

## 依赖
- 调用：config.settings、logger、psycopg2
- 被调用：audit_engine、main、cli（init_db）、mock_data_populator

## 伪代码

函数 get_db_connection():
    用 settings.DATABASE_URL 建立 psycopg2 连接并返回
    # 连接失败直接抛给调用方（快速失败）

函数 init_db():
    连接 = get_db_connection()
    游标 = 连接.游标()
    依次 CREATE TABLE IF NOT EXISTS:
        employees                 # 花名册映射（F8）
        attendance_logs           # 打卡流水（F1/F2）
        approvals                 # 请假/出差/加班/补卡（F1/F5/F6）
        field_work_reports        # 出差日报+水印（F4）
        service_reports           # 客户签字服务报告（F5）
        daily_attendance          # 日合成结果，UNIQUE(userid, date)（F1/F7）
        compensatory_leave_details # 调休流水（F6）
        vacation_balances         # 余额汇总，remaining 为 GENERATED（F6）
        national_holidays         # 法定假/调班（F9）
        audit_logs                # 人工/系统审计痕迹（F14）
        payroll_period_locks      # 薪资周期封账（F14/E18），UNIQUE(period_start, period_end)
        test_data_provenance      # 测试造数溯源，UNIQUE(table_name, record_pk)——仅 mock_data_populator 写
    ALTER TABLE field_work_reports ADD COLUMN IF NOT EXISTS raw_payload（幂等，兼容已建表环境）
    提交事务
    关闭游标与连接
    记 INFO「表初始化成功」

## 异常与边界（必填）
- 本文件处理：init_db 内未单独 try；连接/DDL 失败向上抛
- 故意往上抛：连接失败、权限不足、磁盘满 → 由 main.startup 记 CRITICAL 或 CLI 退出非 0
- 边界：IF NOT EXISTS 幂等；不自动迁移改列（Schema 变更需人工/迁移脚本）；外键 ON DELETE CASCADE 删员工会带走其流水

## 注意事项 / 坑
- attendance_logs 新建库含 UNIQUE(wecom_userid, clock_time, clock_type) 支持幂等（E23）；已有库需手工补约束
- vacation_balances.remaining 是 GENERATED ALWAYS，禁止手工 UPDATE remaining
- national_holidays 运行时只查库，不调外部节假日 API（PRD Out of Scope）
- 已部署环境执行一次 `cli init-db` 以创建 `payroll_period_locks` 与 `test_data_provenance`
- test_data_provenance 只在跑 `mock_data_populator.populate_test_data` 时被写入/清理；生产 daily/weekly/monthly 审计流程完全不碰这张表，不影响真实数据路径
