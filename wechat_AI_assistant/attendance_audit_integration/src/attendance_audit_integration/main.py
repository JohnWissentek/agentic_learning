from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import Response, PlainTextResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import date, timedelta
import xmltodict
from psycopg2.extras import RealDictCursor

from attendance_audit_integration import config
from attendance_audit_integration.db import init_db, get_db_connection
from attendance_audit_integration.audit_engine import audit_engine, seed_national_holidays, send_annual_holiday_reminder
from attendance_audit_integration.mail_sender import send_html_email
from attendance_audit_integration.logger import get_logger
from attendance_audit_integration.wxbiz_msg_crypt import WXBizMsgCrypt

logger = get_logger(__name__)
settings = config.settings


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Run database initialization on startup."""
    try:
        config.validate()
        init_db()
    except Exception as e:
        logger.critical("Database initialization failed: %s", e)
    yield


app = FastAPI(
    title="WeCom Attendance Audit Integration Core",
    description="Backend API engine to sync and reconcile WeCom punches, approvals and generate HTML reports.",
    version="1.1.0",
    lifespan=lifespan,
)

# Instantiate the cryptor. WECOM_TOKEN/WECOM_ENCODING_AES_KEY are optional (only
# needed for the approval callback webhooks below); a missing/invalid key must
# not take down the whole service (daily/weekly/monthly audit endpoints do not
# depend on it) — degrade to a disabled webhook instead of crashing on startup.
try:
    wxcrypt = WXBizMsgCrypt(settings.WECOM_TOKEN, settings.WECOM_ENCODING_AES_KEY, settings.WECOM_CORPID)
except ValueError as e:
    logger.warning(
        "WXBizMsgCrypt disabled: %s (WECOM_TOKEN/WECOM_ENCODING_AES_KEY not configured; "
        "approval callback webhooks will return 503 until fixed, other endpoints are unaffected)",
        e,
    )
    wxcrypt = None


@app.get("/webhooks/approval", summary="Verify WeCom callback webhook URL.")
def verify_wecom_webhook(msg_signature: str, timestamp: str, nonce: str, echostr: str):
    """Handle WeCom URL verification (GET challenge)."""
    if wxcrypt is None:
        raise HTTPException(status_code=503, detail="WeCom callback webhook not configured")
    try:
        decrypted_echostr = wxcrypt.verify_url(
            msg_signature=msg_signature,
            timestamp=timestamp,
            nonce=nonce,
            echostr=echostr
        )
        return PlainTextResponse(decrypted_echostr)
    except Exception as e:
        logger.error("WeCom URL verification failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/webhooks/approval", summary="Receive approval status changes from WeCom.")
async def receive_wecom_approval_webhook(request: Request, msg_signature: str, timestamp: str, nonce: str):
    """Handle decrypted WeCom approval event push XML (POST notification)."""
    if wxcrypt is None:
        logger.error("Approval webhook received but WXBizMsgCrypt is disabled (missing config)")
        return PlainTextResponse("success")
    try:
        body = await request.body()
        xml_body = body.decode("utf-8")
        
        # Decrypt message
        decrypted_xml = wxcrypt.decrypt_xml_msg(
            msg_signature=msg_signature,
            timestamp=timestamp,
            nonce=nonce,
            post_data=xml_body
        )
        
        # Parse XML to dictionary
        doc = xmltodict.parse(decrypted_xml)
        event_data = doc.get("xml", {})
        
        event_type = event_data.get("Event")
        if event_type == "sys_approval_change":
            info = event_data.get("ApprovalInfo", {})
            sp_no = info.get("SpNo")
            sp_status = int(info.get("SpStatus", "1")) # 1-审批中, 2-已通过, 3-已驳回, 4-已撤销, 10-处于会签状态
            
            logger.info("Received WeCom Approval Event sp_no: %s | status: %s", sp_no, sp_status)
            
            # 收到审批状态变更时，优先回查企微详情补全起止时间/时长/假别；失败则降级保底写状态
            if sp_no:
                conn = get_db_connection()
                try:
                    cursor = conn.cursor()
                    enriched = audit_engine.sync_single_approval(cursor, sp_no)
                    if not enriched and sp_status == 2:
                        cursor.execute(
                            """
                            INSERT INTO approvals (approval_no, wecom_userid, approval_type, status)
                            VALUES (%s, %s, %s, 'approved')
                            ON CONFLICT (approval_no) DO UPDATE SET status = 'approved';
                            """,
                            (
                                sp_no,
                                info.get("Applyer", {}).get("UserId"),
                                info.get("SpName", "unknown"),
                            ),
                        )
                    conn.commit()
                    cursor.close()
                    logger.info(
                        "Processed approval webhook %s (status=%s, enriched=%s).",
                        sp_no,
                        sp_status,
                        enriched,
                    )
                finally:
                    conn.close()

        return PlainTextResponse("success")
    except Exception as e:
        logger.error("WeCom webhook callback failed: %s", e)
        # Always return success to WeCom to prevent repeated retries, but log the error
        return PlainTextResponse("success")

class AuditRequest(BaseModel):
    audit_date: Optional[str] = None  # Format: "YYYY-MM-DD", defaults to yesterday
    is_final: bool = False

class MonthlyAuditRequest(BaseModel):
    audit_date: Optional[str] = None  # Format: "YYYY-MM-DD" (Defaults to today)
    is_final: bool = False

@app.post("/audit/run", summary="Manually trigger daily or monthly audit.")
def run_audit(req: AuditRequest, background_tasks: BackgroundTasks):
    """Trigger daily audit or monthly audit."""
    try:
        if req.audit_date:
            target_date = date.fromisoformat(req.audit_date)
        else:
            target_date = date.today() - timedelta(days=1)  # Default to yesterday (T-1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    if req.is_final:
        background_tasks.add_task(audit_engine.run_monthly_audit, target_date, is_final=True)
        return {"status": "success", "message": f"Monthly final audit queued for month of {target_date.strftime('%Y-%m')}."}
    else:
        background_tasks.add_task(audit_engine.run_daily_audit, target_date)
        return {"status": "success", "message": f"Daily audit queued for date {target_date.strftime('%Y-%m-%d')}."}

@app.post("/audit/monthly", summary="Trigger monthly draft or final audit.")
def run_monthly_audit_endpoint(req: MonthlyAuditRequest, background_tasks: BackgroundTasks):
    """Trigger monthly audit (draft or final)."""
    try:
        target_date = date.fromisoformat(req.audit_date) if req.audit_date else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    background_tasks.add_task(audit_engine.run_monthly_audit, target_date, is_final=req.is_final)
    version = "final" if req.is_final else "draft"
    return {"status": "success", "message": f"Monthly {version} audit queued for date {target_date.strftime('%Y-%m-%d')}."}

@app.post("/audit/weekly", summary="Trigger weekly audit.")
def run_weekly_audit(background_tasks: BackgroundTasks):
    """Trigger weekly audit report."""
    background_tasks.add_task(audit_engine.run_weekly_audit)
    return {"status": "success", "message": "Weekly audit report queued."}

@app.post("/audit/check_expiry", summary="Scan and trigger overdue compensatory leave alerts.")
def run_expiry_check(background_tasks: BackgroundTasks):
    """Trigger checking of 7-day overdue compensatory leaves."""
    background_tasks.add_task(audit_engine.check_compensatory_leave_expiry)
    return {"status": "success", "message": "Compensatory leave overdue checking task queued."}


@app.post("/audit/vacation", summary="Sync WeCom vacation balances and run backlog/expiry audit.")
def run_vacation_audit_endpoint(background_tasks: BackgroundTasks):
    """Trigger read-only WeCom vacation balance sync and anomaly alert report."""
    background_tasks.add_task(audit_engine.run_vacation_balance_audit)
    return {"status": "success", "message": "WeCom vacation balance audit queued."}

# ＝＝＝＝＝ 国家法定节假日管理 API (PRD §3.7 / SRS §3.6) ＝＝＝＝＝

class HolidayEntry(BaseModel):
    holiday_date: str  # Format: "YYYY-MM-DD"
    day_type: str  # 'holiday' or 'workday'
    description: Optional[str] = None

@app.get("/holidays", summary="List all national holidays for a given year.")
def list_holidays(year: int = 2026):
    """List all entries in the national_holidays table for the specified year."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
        SELECT id, holiday_date, day_type, description 
        FROM national_holidays 
        WHERE EXTRACT(YEAR FROM holiday_date) = %s
        ORDER BY holiday_date;
        """, (year,))
        holidays = cursor.fetchall()
        cursor.close()
        # Convert date objects to strings for JSON serialization
        result = []
        for h in holidays:
            result.append({
                "id": h["id"],
                "holiday_date": h["holiday_date"].isoformat(),
                "day_type": h["day_type"],
                "description": h["description"]
            })
        return {"year": year, "count": len(result), "holidays": result}
    finally:
        conn.close()

@app.post("/holidays", summary="Add a national holiday or makeup workday entry.")
def add_holiday(entry: HolidayEntry):
    """Add a single entry to the national_holidays table."""
    try:
        holiday_date = date.fromisoformat(entry.holiday_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    
    if entry.day_type not in ("holiday", "workday"):
        raise HTTPException(status_code=400, detail="day_type must be 'holiday' or 'workday'.")
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO national_holidays (holiday_date, day_type, description)
        VALUES (%s, %s, %s)
        ON CONFLICT (holiday_date) DO UPDATE 
        SET day_type = EXCLUDED.day_type, description = EXCLUDED.description;
        """, (holiday_date, entry.day_type, entry.description))
        conn.commit()
        cursor.close()
        return {"status": "success", "message": f"Holiday entry for {entry.holiday_date} saved ({entry.day_type})."}
    finally:
        conn.close()

@app.delete("/holidays/{holiday_id}", summary="Delete a national holiday entry by ID.")
def delete_holiday(holiday_id: int):
    """Delete a single entry from the national_holidays table."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM national_holidays WHERE id = %s RETURNING id;", (holiday_id,))
        deleted = cursor.fetchone()
        conn.commit()
        cursor.close()
        if deleted:
            return {"status": "success", "message": f"Holiday entry #{holiday_id} deleted."}
        else:
            raise HTTPException(status_code=404, detail=f"Holiday entry #{holiday_id} not found.")
    finally:
        conn.close()

@app.post("/holidays/seed/{year}", summary="Auto-seed holidays from chinesecalendar library.")
def seed_holidays(year: int):
    """One-time bootstrap: populate national_holidays table using the chinesecalendar library.
    After seeding, data should be manually maintained by the General Manager."""
    result = seed_national_holidays(year)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return {"status": "success", **result}

@app.post("/holidays/annual_reminder", summary="Trigger annual holiday input reminder email.")
def trigger_annual_reminder(background_tasks: BackgroundTasks):
    """Manually trigger the Dec 31 annual reminder email to the General Manager."""
    background_tasks.add_task(send_annual_holiday_reminder)
    return {"status": "success", "message": "Annual holiday reminder email queued."}

# ＝＝＝＝＝ 测试与运维工具 ＝＝＝＝＝

class TestEmailRequest(BaseModel):
    to_email: str
    subject: str = "Test SMTP connection"
    message: str = "Hello! This is a test email sent from the WeCom Attendance Audit System."

@app.post("/test/send_email", summary="Send a test SMTP email.")
def send_test_email(req: TestEmailRequest):
    """Trigger sending a simple HTML test email."""
    html_content = f"""
    <html>
    <body>
        <h2>WeCom Attendance Audit Integration Test</h2>
        <p>{req.message}</p>
    </body>
    </html>
    """
    success = send_html_email(
        subject=req.subject,
        html_content=html_content,
        to_email=req.to_email
    )
    if success:
        return {"status": "success", "message": f"Test email sent to {req.to_email} successfully."}
    else:
        raise HTTPException(status_code=500, detail="Failed to send test email. Check SMTP server configs in .env.")

@app.get("/", summary="App status check endpoint.")
def read_root():
    return {"status": "running", "stage": "Production Scaffolded Package"}
