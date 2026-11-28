import psycopg2
from psycopg2.extras import RealDictCursor
from attendance_audit_integration.config import settings
from attendance_audit_integration.logger import get_logger

logger = get_logger(__name__)

def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    conn = psycopg2.connect(settings.DATABASE_URL)
    return conn

def init_db():
    """Initialize the database tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create tables sequentially
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id SERIAL PRIMARY KEY,
        wecom_userid VARCHAR(100) UNIQUE NOT NULL,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(255),
        company VARCHAR(200),
        role VARCHAR(100),
        hire_date DATE,
        status VARCHAR(20) DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance_logs (
        id SERIAL PRIMARY KEY,
        wecom_userid VARCHAR(100) NOT NULL,
        clock_time TIMESTAMP NOT NULL,
        clock_type VARCHAR(20) NOT NULL, -- 'start_shift', 'end_shift', 'outdoor'
        location_name TEXT,
        latitude NUMERIC(9, 6),
        longitude NUMERIC(9, 6),
        ip_address VARCHAR(45),
        exception_type VARCHAR(50),
        raw_payload JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid) ON DELETE CASCADE,
        UNIQUE (wecom_userid, clock_time, clock_type)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS approvals (
        id SERIAL PRIMARY KEY,
        approval_no VARCHAR(100) UNIQUE NOT NULL,
        wecom_userid VARCHAR(100) NOT NULL,
        approval_type VARCHAR(50) NOT NULL, -- 'leave', 'business_trip', 'overtime', 'punch_correction'
        sub_type VARCHAR(50), -- 'sick_leave', 'annual_leave', 'compensatory_leave'
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        duration_hours NUMERIC(5, 2),
        status VARCHAR(20) NOT NULL, -- 'approved', 'rejected'
        reason TEXT,
        raw_payload JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS field_work_reports (
        id SERIAL PRIMARY KEY,
        report_no VARCHAR(100) UNIQUE NOT NULL,
        wecom_userid VARCHAR(100) NOT NULL,
        report_date DATE NOT NULL,
        work_summary TEXT,
        watermark_image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid) ON DELETE CASCADE
    );
    """)
    # 企微日报原始表单结构随模板自定义，字段抽取为最佳努力解析；留原始 JSON 兜底排查
    cursor.execute(
        "ALTER TABLE field_work_reports ADD COLUMN IF NOT EXISTS raw_payload JSONB;"
    )

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS service_reports (
        id SERIAL PRIMARY KEY,
        report_no VARCHAR(100) UNIQUE NOT NULL,
        wecom_userid VARCHAR(100) NOT NULL,
        report_date DATE NOT NULL,
        is_customer_signed BOOLEAN DEFAULT FALSE,
        signature_image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_attendance (
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
        FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS compensatory_leave_details (
        id SERIAL PRIMARY KEY,
        wecom_userid VARCHAR(100) NOT NULL,
        accrual_date DATE NOT NULL,
        total_hours NUMERIC(5, 2) NOT NULL,
        used_hours NUMERIC(5, 2) DEFAULT 0.0,
        is_fully_used BOOLEAN DEFAULT FALSE,
        status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'released', 'invalid'
        expire_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vacation_balances (
        id SERIAL PRIMARY KEY,
        wecom_userid VARCHAR(100) NOT NULL,
        leave_type VARCHAR(50) NOT NULL, -- 'annual', 'compensatory'
        total_granted NUMERIC(5, 2) NOT NULL,
        total_used NUMERIC(5, 2) DEFAULT 0.0,
        remaining NUMERIC(5, 2) GENERATED ALWAYS AS (total_granted - total_used) STORED,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (wecom_userid, leave_type),
        FOREIGN KEY (wecom_userid) REFERENCES employees(wecom_userid) ON DELETE CASCADE
    );
    """)

    # 国家法定节假日日历表 (SRS §3.6)
    # 由总经理徐宏玮手动录入维护，不使用外部 API
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS national_holidays (
        id SERIAL PRIMARY KEY,
        holiday_date DATE UNIQUE NOT NULL,
        day_type VARCHAR(20) NOT NULL, -- 'holiday' (法定节假日-需支付法定加班费), 'workday' (调班工作日-按常规工作日审计)
        description VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        wecom_userid VARCHAR(100),
        action_type VARCHAR(50) NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 测试造数溯源表：仅 mock_data_populator.py 写入，记录"哪些行是人工补造的"；
    # 未在此表登记的行默认视为真实数据（PRD 测试数据策略：真实优先，缺口才造假）
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS test_data_provenance (
        id SERIAL PRIMARY KEY,
        table_name VARCHAR(50) NOT NULL,
        record_pk VARCHAR(100) NOT NULL,
        scenario_id VARCHAR(20) NOT NULL,
        reason TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (table_name, record_pk)
    );
    """)

    # F14 / E18：薪资周期终审封账表（禁止同周期重复终审静默重算）
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payroll_period_locks (
        id SERIAL PRIMARY KEY,
        period_start DATE NOT NULL,
        period_end DATE NOT NULL,
        audit_month_label VARCHAR(32) NOT NULL,
        locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        locked_by VARCHAR(100) DEFAULT 'system',
        UNIQUE (period_start, period_end)
    );
    """)

    conn.commit()
    cursor.close()
    conn.close()
    logger.info("Database tables initialized successfully.")

