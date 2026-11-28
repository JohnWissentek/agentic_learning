# 软件需求规格说明书 (SRS) - 阶段一（过渡期方案）
## 目录: `attendance_audit_integration/stage_one/docs/SRS.md`

---

## 1. 阶段一：系统数据库 Schema 设计

在第一阶段（过渡期），系统数据库保留核心人员与打卡结构，并支持日报、服务报告及调休流水的存储：

### 1.1 `employees` (员工表)
```sql
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    wecom_userid VARCHAR(100) UNIQUE NOT NULL,  -- 企业微信 UserID
    name VARCHAR(100) NOT NULL, -- 员工中文姓名
    email VARCHAR(255), -- 电子邮件地址
    company VARCHAR(200), -- 签约公司名称
    role VARCHAR(100), -- 岗位岗位
    hire_date DATE, -- 入职时间
    status VARCHAR(20) DEFAULT 'active', -- active, resigned
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 1.2 `attendance_logs` (打卡日志表)
```sql
CREATE TABLE attendance_logs (
    id SERIAL PRIMARY KEY,
    wecom_userid VARCHAR(100) NOT NULL,
    clock_time TIMESTAMP NOT NULL,
    clock_type VARCHAR(20) NOT NULL, -- 'start_shift', 'end_shift', 'outdoor'
    location_name TEXT,
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    ip_address VARCHAR(45), -- 记录打卡时的出口 IP（IPv4/IPv6）
    exception_type VARCHAR(50), -- 记录企微判定的异常类型：'location_anomaly'等
    raw_payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid)
);
```

### 1.3 `approvals` (审批单据表)
```sql
CREATE TABLE approvals (
    id SERIAL PRIMARY KEY,
    approval_no VARCHAR(100) UNIQUE NOT NULL, -- 企业微信审批单号
    wecom_userid VARCHAR(100) NOT NULL,
    approval_type VARCHAR(50) NOT NULL, -- 'leave', 'business_trip', 'overtime', 'punch_correction'
    sub_type VARCHAR(50), -- 'sick_leave', 'annual_leave', 'compensatory_leave'
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    duration_hours NUMERIC(5, 2) NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'approved', 'rejected'
    reason TEXT,
    raw_payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid)
);
```

### 1.4 `field_work_reports` (现场工作日报表)
```sql
CREATE TABLE field_work_reports (
    id SERIAL PRIMARY KEY,
    report_no VARCHAR(100) UNIQUE NOT NULL, -- 企微日志单号
    wecom_userid VARCHAR(100) NOT NULL,
    report_date DATE NOT NULL,
    work_summary TEXT,
    watermark_image_url TEXT, -- 现场环境水印照片链接（若有）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid)
);
```

### 1.5 `service_reports` (服务报告表)
```sql
CREATE TABLE service_reports (
    id SERIAL PRIMARY KEY,
    report_no VARCHAR(100) UNIQUE NOT NULL,
    wecom_userid VARCHAR(100) NOT NULL,
    report_date DATE NOT NULL,
    is_customer_signed BOOLEAN DEFAULT FALSE,
    signature_image_url TEXT, -- 客户签字扫描件链接
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid)
);
```

### 1.6 `daily_attendance` (日考勤明细结果表)
```sql
CREATE TABLE daily_attendance (
    id SERIAL PRIMARY KEY,
    wecom_userid VARCHAR(100) NOT NULL,
    attendance_date DATE NOT NULL,
    first_clock_in TIMESTAMP,
    last_clock_out TIMESTAMP,
    status VARCHAR(50) NOT NULL,
    is_anomaly BOOLEAN DEFAULT FALSE,
    anomaly_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (wecom_userid, attendance_date),
    FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid)
);
```

### 1.7 `compensatory_leave_details` (调休流水明细表)
```sql
CREATE TABLE compensatory_leave_details (
    id SERIAL PRIMARY KEY,
    wecom_userid VARCHAR(100) NOT NULL,
    accrual_date DATE NOT NULL,
    total_hours NUMERIC(5, 2) NOT NULL,
    used_hours NUMERIC(5, 2) DEFAULT 0.0,
    is_fully_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid)
);
```

### 1.8 `vacation_balances` (假期余额表)
```sql
CREATE TABLE vacation_balances (
    id SERIAL PRIMARY KEY,
    wecom_userid VARCHAR(100) NOT NULL,
    leave_type VARCHAR(50) NOT NULL, -- 'annual', 'compensatory'
    total_granted NUMERIC(5, 2) NOT NULL,
    total_used NUMERIC(5, 2) DEFAULT 0.0,
    remaining NUMERIC(5, 2) GENERATED ALWAYS AS (total_granted - total_used) STORED,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid)
);
```

---

## 2. 定时任务与审计逻辑（阶段一）

### 2.1 日基础考勤与防作弊对账 (T-1日，每日上午 09:00)
1. **防作弊过滤**：
   - 检查 `attendance_logs.exception_type` 是否为异常。如果是，直接判定为考勤异常。
   - **速度可行性校验**：比对相邻打卡记录的距离（使用 GPS 坐标）与时间差，计算移动时速。若移动时速 `V > 350 km/h`（如跨省瞬移），直接判定为“虚拟定位空间矛盾作弊”。
2. **缺卡校验**：若无审批且缺打卡，判定为“漏打卡考勤异常”，写入 `daily_attendance.is_anomaly = TRUE`。
3. **报警邮件发送**：向缺卡员工发信，**抄送：徐宏玮、薛蕾、王晓**。

### 2.2 月度终审与后置交叉审计 (每月 5 日凌晨 01:00)
1. **差旅日报核对**：检查处于“出差”状态日期是否有对应的 `field_work_reports`，缺失则判定异常。
2. **加班服务报告核对**：检查所有普通周末加班是否关联 `service_reports` 且 `is_customer_signed = TRUE`。若缺失或未签字，扣减或阻断该日加班进入 `compensatory_leave_details`（不产生调休）。
3. **高管考勤日报/周报/月报推送**：
   - 自动生成对应周期的考勤统计表。
   - 直接发送到高管邮箱：**徐宏玮、薛蕾、王晓**。
