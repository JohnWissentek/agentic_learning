# db.py 伪代码

## 本文件职责（一句话）
提供 PostgreSQL 数据库连接，并定义了系统所需的所有核心数据库表的 Schema 及初始化建立逻辑。

## 对应PRD功能
考勤、请假审批、加班勾稽、日报、服务单、节假日及系统审计日志的底层数据存储。

## 依赖
- 调用：psycopg2, config.settings, logger
- 被调用：main.py, audit_engine.py, mock_data_populator.py 等需要连接数据库的模块。

## 伪代码
```python
函数 get_db_connection():
    返回 psycopg2.connect(连接地址 = settings.DATABASE_URL)

函数 init_db():
    连接 = get_db_connection()
    游标 = 连接.游标()
    
    尝试:
        # 1. 创建员工信息表 (employees)
        游标.执行建表 """
        IF NOT EXISTS employees (
            wecom_userid VARCHAR UNIQUE (主键ID),
            name VARCHAR (姓名),
            email VARCHAR (邮箱),
            company VARCHAR (所属公司),
            role VARCHAR (岗位),
            hire_date DATE (入职时间),
            status VARCHAR (状态: active 等)
        )"""

        # 2. 创建原始打卡日志表 (attendance_logs)
        游标.执行建表 """
        IF NOT EXISTS attendance_logs (
            wecom_userid VARCHAR (关联 employees),
            clock_time TIMESTAMP (打卡时间),
            clock_type VARCHAR (上班/下班/外勤打卡),
            location_name TEXT (打卡地点名称),
            latitude/longitude NUMERIC (经纬度),
            ip_address VARCHAR (打卡IP),
            exception_type VARCHAR (异常类型: 设备异常/定位异常等),
            raw_payload JSONB (企业微信接口原始JSON)
        )"""

        # 3. 创建审批单表 (approvals)
        游标.执行建表 """
        IF NOT EXISTS approvals (
            approval_no VARCHAR UNIQUE (审批单号),
            wecom_userid VARCHAR (关联 employees),
            approval_type VARCHAR (请假/出差/加班/补卡),
            sub_type VARCHAR (假勤子类: 病假/年假/调休等),
            start_time/end_time TIMESTAMP (审批生效区间),
            duration_hours NUMERIC (时长小时数),
            status VARCHAR (approved/rejected 状态),
            reason TEXT (原因说明),
            raw_payload JSONB
        )"""

        # 4. 创建出差现场工作日报表 (field_work_reports)
        游标.执行建表 """
        IF NOT EXISTS field_work_reports (
            report_no VARCHAR UNIQUE (日报单号),
            wecom_userid VARCHAR (关联 employees),
            report_date DATE (汇报日期),
            work_summary TEXT (工作内容总结),
            watermark_image_url TEXT (现场环境水印图片链接)
        )"""

        # 5. 创建周末客户签字现场服务单表 (service_reports)
        游标.执行建表 """
        IF NOT EXISTS service_reports (
            report_no VARCHAR UNIQUE (服务单号),
            wecom_userid VARCHAR (关联 employees),
            report_date DATE (服务日期),
            is_customer_signed BOOLEAN (客户是否手写签字),
            signature_image_url TEXT (手写签名照片链接)
        )"""

        # 6. 创建每日考稽决算明细表 (daily_attendance)
        游标.执行建表 """
        IF NOT EXISTS daily_attendance (
            wecom_userid VARCHAR (关联 employees),
            attendance_date DATE (考勤业务日期),
            first_clock_in TIMESTAMP (首次上班打卡时间),
            last_clock_out TIMESTAMP (末次下班打卡时间),
            status VARCHAR (考勤核定状态: normal/absent/late/leave等),
            is_anomaly BOOLEAN (是否异常),
            anomaly_reason TEXT (异常原因描述),
            联合唯一约束 (wecom_userid, attendance_date)
        )"""

        # 7. 创建调休假期明细表 (compensatory_leave_details)
        游标.执行建表 """
        IF NOT EXISTS compensatory_leave_details (
            wecom_userid VARCHAR (关联 employees),
            accrual_date DATE (加班产生调休的日期),
            total_hours NUMERIC (总可调休小时数),
            used_hours NUMERIC (已消耗小时数),
            is_fully_used BOOLEAN (是否消耗完毕),
            status VARCHAR (状态: pending/released/invalid),
            expire_date DATE (调休截止有效期)
        )"""

        # 8. 创建假期余额汇总表 (vacation_balances)
        游标.执行建表 """
        IF NOT EXISTS vacation_balances (
            wecom_userid VARCHAR (关联 employees),
            leave_type VARCHAR (假种: annual/compensatory),
            total_granted NUMERIC (已发放总天/数),
            total_used NUMERIC (已使用总天/数),
            remaining NUMERIC (剩余余额 = total_granted - total_used 自动生成列),
            联合唯一约束 (wecom_userid, leave_type)
        )"""

        # 9. 创建国家法定节假日日历表 (national_holidays)
        游标.执行建表 """
        IF NOT EXISTS national_holidays (
            holiday_date DATE UNIQUE (日期),
            day_type VARCHAR (holiday表示假节日，workday表示调班工作日),
            description VARCHAR (备注描述)
        )"""

        # 10. 创建系统操作审计日志表 (audit_logs)
        游标.执行建表 """
        IF NOT EXISTS audit_logs (
            wecom_userid VARCHAR,
            action_type VARCHAR,
            description TEXT
        )"""

        提交事务
        记日志 INFO "数据库表结构初始化成功。"
    捕获 异常 并 异常回滚:
        游标.关闭()
        连接.关闭()
        抛出 异常
    最后:
        游标.关闭()
        连接.关闭()
```

## 注意事项 / 坑
- 所有的表在创建时都附加了外键关联约束 `FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid) ON DELETE CASCADE`。这意味着一旦删除了某员工记录，该员工的所有打卡、审批、决算和日报数据将被物理级级联删除。
- 节假日表 `national_holidays` 专用于考勤工作日校验。此表在应用初始化时通过 `chinesecalendar` 库进行一次性批量生成（Seed），但后续由总经理徐宏玮进行手动个性化维护。
- `vacation_balances` 里的 `remaining` 是一个 PostgreSQL `GENERATED ALWAYS AS (total_granted - total_used) STORED` 的物理自动计算列，不允许显式向其插入或更新值，修改时只需操作 `total_granted` 或 `total_used` 即可。
