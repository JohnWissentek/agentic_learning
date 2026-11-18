"""Embedded FastAPI Chief-of-Staff Cockpit Web App & WeCom HTTPS Callback Server."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field

from wechat_assistant.config import DashScopeLLMGateway, Settings
from wechat_assistant.graph import ChiefOfStaffEngine
from wechat_assistant.intake.mail_poller import mail_poller_loop
from wechat_assistant.intake.wecom_gateway import WeComGateway
from wechat_assistant.schemas import ActionMutation, ListType, PriorityLevel, WorkDomain
from wechat_assistant.storage.db import Database
from wechat_assistant.tools.onedrive_tools import OneDrive21VianetClient

COOKIE_NAME = "chairman_cockpit_session"
STATIC_DIR = Path(__file__).resolve().parent / "static"


class ItemUpdateBody(BaseModel):
    title: str | None = None
    list_type: str | None = None
    work_domain: str | None = None
    project_name: str | None = None
    owner: str | None = None
    planned_start_at: str | None = None
    planned_end_at: str | None = None
    estimated_hours: float | None = Field(default=None, ge=0.0, le=200.0)
    actual_hours: float | None = Field(default=None, ge=0.0, le=200.0)
    priority: str | None = None
    status: str | None = None
    stage: str | None = None


class ItemCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    list_type: ListType = ListType.NEXT_ACTION
    work_domain: WorkDomain = WorkDomain.RD
    project_name: str = Field(default="General Ops", min_length=1, max_length=80)
    owner: str = "Chairman"
    planned_start_at: str | None = None
    planned_end_at: str | None = None
    estimated_hours: float = Field(default=0.0, ge=0.0, le=200.0)
    priority: PriorityLevel = PriorityLevel.P1


class PromoteIdeaBody(BaseModel):
    project_name: str = Field(min_length=1, max_length=80)
    planned_start_at: str
    planned_end_at: str
    estimated_hours: float = Field(default=1.0, ge=0.1, le=200.0)


class CompleteItemBody(BaseModel):
    actual_hours: float | None = Field(default=None, ge=0.0, le=200.0)


class VerifyCodeBody(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class AuthManager:
    """Rate-limited 6-digit WeChat login code + signed 180d Cookie + optional magic link."""

    def __init__(self, secret: str, session_days: int = 180) -> None:
        self.secret = secret or secrets.token_hex(32)
        self.session_days = session_days
        self._magic_tokens: dict[str, float] = {}
        self._login_codes: dict[str, float] = {}
        self._rate_hits: dict[str, list[float]] = {}

    def mint_magic_token(self, ttl_seconds: int = 300) -> str:
        tok = secrets.token_urlsafe(24)
        self._magic_tokens[tok] = time.time() + ttl_seconds
        return tok

    def consume_magic_token(self, token: str) -> bool:
        exp = self._magic_tokens.pop(token, None)
        if exp is None or time.time() > exp:
            return False
        return True

    def can_request_code(self, client_ip: str) -> bool:
        now = time.time()
        hits = [t for t in self._rate_hits.get(client_ip, []) if now - t < 600]
        if len(hits) >= 5:
            self._rate_hits[client_ip] = hits
            return False
        hits.append(now)
        self._rate_hits[client_ip] = hits
        return True

    def mint_login_code(self, ttl_seconds: int = 300) -> str:
        code = f"{secrets.randbelow(1000000):06d}"
        self._login_codes[code] = time.time() + ttl_seconds
        return code

    def verify_login_code(self, code: str) -> bool:
        now = time.time()
        self._login_codes = {k: v for k, v in self._login_codes.items() if v > now}
        for valid_code in list(self._login_codes):
            if hmac.compare_digest(valid_code, code.strip()):
                del self._login_codes[valid_code]
                return True
        return False

    def sign_session_cookie(self) -> str:
        exp = int(time.time() + self.session_days * 86400)
        payload = base64.urlsafe_b64encode(json.dumps({"role": "chairman", "exp": exp}).encode("utf-8")).decode("ascii")
        sig = hmac.new(self.secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{payload}.{sig}"

    def verify_session_cookie(self, cookie_val: str | None) -> bool:
        if not cookie_val or "." not in cookie_val:
            return False
        payload, _, sig = cookie_val.partition(".")
        expected = hmac.new(self.secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return False
        try:
            padded = payload + "=" * ((4 - len(payload) % 4) % 4)
            data = json.loads(base64.urlsafe_b64decode(padded))
            return int(data.get("exp", 0)) > time.time()
        except Exception:
            return False


def build_daily_digest_message(ov: dict[str, Any], kind: str, magic_url: str) -> str:
    """Build morning or evening WeChat digest; evening digest prompts active progress check-in."""
    today = ov["today"]
    today_info = ov["workload"]["days"].get(today, {})
    open_items = [i for i in ov["items"] if i["status"] != "done"]
    top_todos = open_items[:5]
    todo_text = "\n".join(
        f"- `#{i['id']}` `[{i['priority']}]` {i['title']}（{i['planned_start_at'] or '-'}~{i['planned_end_at'] or '-'}）"
        for i in top_todos
    ) or "- 暂无未完成待办"
    waits = ov["waiting_items"][:3]
    wait_text = "\n".join(f"- 等{w['owner']}：{w['title']}（已等 {w['waiting_days']} 天）" for w in waits)

    checkin_block = ""
    if "晚间" in kind:
        due_or_active = [
            i for i in open_items
            if i["status"] == "in_progress" or (i.get("planned_end_at") and i["planned_end_at"][:10] <= today)
        ][:6]
        if due_or_active:
            lines: list[str] = []
            for it in due_or_active:
                pe = (it.get("planned_end_at") or "")[:10]
                if pe and pe < today:
                    tag = "已超期"
                elif pe == today:
                    tag = "今日到期"
                else:
                    tag = "进行中"
                lines.append(f"- `#{it['id']}` [{tag}] {it['title']}")
            checkin_block = (
                "\n📝 **今日进度盘点（请一句话确认，方便自动闭合周期）**：\n"
                + "\n".join(lines)
                + "\n👉 可直接回复：`#3 做完了，#5 开始了`（未完事项也可说明新截止日）\n"
            )

    return (
        f"{kind}（{today}）\n"
        f"📅 今日在途事项：{len(today_info.get('items', []))} 项 ｜ 平均完成跨度：{ov.get('avg_completion_span_days', 0)} 天\n\n"
        f"📌 **今日优先事项**：\n{todo_text}\n"
        + (f"\n⏳ **外部卡点**：\n{wait_text}\n" if wait_text else "")
        + checkin_block
        + f"\n📊 点击打开驾驶舱：{magic_url}"
    )


async def _daily_digest_scheduler(engine: ChiefOfStaffEngine, gateway: WeComGateway) -> None:
    sent_marks: set[str] = set()
    morning = os.environ.get("DAILY_MORNING_DIGEST", "08:30").strip()
    evening = os.environ.get("DAILY_EVENING_DIGEST", "18:00").strip()
    while True:
        try:
            now = datetime.now()
            hm = now.strftime("%H:%M")
            day_key = f"{now.strftime('%Y-%m-%d')}:{hm}"
            if now.weekday() < 5 and hm in {morning, evening} and day_key not in sent_marks:
                sent_marks.add(day_key)
                kind = "🌅 早间工作简报" if hm == morning else "🌆 晚间复盘简报"
                ov = engine.db.dashboard_overview(engine.settings.daily_capacity_hours)
                magic_url = engine.magic_link_factory()
                msg = build_daily_digest_message(ov, kind, magic_url)
                await gateway.send_app_push(msg)
                # Persist digest into dialogue history so follow-up replies ("#3做完了") resolve cleanly
                engine.db.append_conversation_turn(
                    thread_id="owner",
                    role="assistant",
                    content=msg,
                    intent="digest:evening_checkin",
                )
        except Exception:
            pass
        await asyncio.sleep(30)


async def run_turn_with_heartbeat(
    engine: ChiefOfStaffEngine,
    gateway: WeComGateway,
    *,
    text: str,
    sender: str,
    msg_id: str,
    attachments: list[dict[str, Any]],
    first_delay_seconds: float = 12.0,
    interval_seconds: float = 25.0,
) -> str:
    """Execute one turn in a worker thread while pushing periodic WeChat heartbeats if slow."""
    stage = {"label": "正在启动分析", "t0": time.monotonic()}
    done_evt = asyncio.Event()

    async def _watcher() -> None:
        wait_s = first_delay_seconds
        while not done_evt.is_set():
            try:
                await asyncio.wait_for(done_evt.wait(), timeout=wait_s)
                return
            except asyncio.TimeoutError:
                elapsed = max(1, int(time.monotonic() - stage["t0"]))
                try:
                    await gateway.send_app_push(
                        f"⏳ 仍在处理中（已用时 {elapsed}s）：当前正在【{stage['label']}】"
                    )
                except Exception:
                    pass
                wait_s = interval_seconds

    watcher = asyncio.create_task(_watcher())
    try:
        res = await asyncio.to_thread(
            engine.handle_incoming_turn,
            text,
            sender=sender,
            external_msg_id=msg_id,
            attachments=attachments,
            thread_id="owner",
            progress_callback=lambda lbl: stage.update(label=lbl),
        )
        return res["reply_text"]
    finally:
        done_evt.set()
        try:
            await watcher
        except Exception:
            pass


def create_app(
    *,
    settings: Settings | None = None,
    db: Database | None = None,
    engine: ChiefOfStaffEngine | None = None,
    gateway: WeComGateway | None = None,
    onedrive: OneDrive21VianetClient | None = None,
    start_background_tasks: bool = True,
) -> FastAPI:
    """FastAPI factory supporting production ECS deployment and fast offline test injection."""
    cfg = settings or Settings.load(require_bailian=True)
    data_dir = Path(cfg.data_dir)
    store = db or Database(data_dir / "app.db")
    od_client = onedrive or (OneDrive21VianetClient(cfg) if cfg.ms_client_id and cfg.ms_site_id else None)
    auth = AuthManager(cfg.web_access_secret or cfg.dashscope_api_key)

    def make_magic_link() -> str:
        return f"{cfg.web_public_base_url.rstrip('/')}/"

    llm_gw = DashScopeLLMGateway(cfg)
    eng = engine or ChiefOfStaffEngine(
        settings=cfg,
        db=store,
        gateway=llm_gw,
        onedrive=od_client,
        checkpoints_path=data_dir / "checkpoints.db",
        magic_link_factory=make_magic_link,
    )

    wc_gw: WeComGateway | None = None

    async def process_turn(text: str, sender: str, attachments: list[dict[str, Any]], msg_id: str) -> str:
        assert wc_gw is not None
        return await run_turn_with_heartbeat(
            eng,
            wc_gw,
            text=text,
            sender=sender,
            msg_id=msg_id,
            attachments=attachments,
        )

    wc_gw = gateway or WeComGateway(cfg, turn_processor=process_turn)
    bg_tasks: list[asyncio.Task[Any]] = []

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if start_background_tasks:
            if od_client is not None:
                try:
                    await asyncio.to_thread(od_client.sync_all_lists, store)
                except Exception:
                    pass
            bg_tasks.append(asyncio.create_task(_daily_digest_scheduler(eng, wc_gw)))
            if cfg.mail_enabled and od_client is not None:
                async def on_email(body: str, sender: str, ext_id: str) -> None:
                    reply = await asyncio.to_thread(
                        eng.handle_incoming_turn,
                        body,
                        sender=f"mail:{sender}",
                        external_msg_id=ext_id,
                        thread_id="owner",
                    )
                    if reply.get("proposal_id"):
                        await wc_gw.send_app_push(f"📧 新邮件幕僚分析：\n{reply['reply_text']}")
                bg_tasks.append(
                    asyncio.create_task(mail_poller_loop(cfg, od_client, on_email, mark_seen=store.mark_external_seen))
                )
        try:
            yield
        finally:
            for t in bg_tasks:
                t.cancel()
            eng.close()

    app = FastAPI(title="董事长个人 AI 助理与项目管理驾驶舱", lifespan=lifespan)
    app.state.engine = eng
    app.state.auth = auth
    app.state.gateway = wc_gw
    app.state.db = store
    app.state.onedrive = od_client
    app.state.settings = cfg

    def require_session(request: Request) -> None:
        if not auth.verify_session_cookie(request.cookies.get(COOKIE_NAME)):
            raise HTTPException(status_code=401, detail="Please sign in with a WeChat 6-digit code or Magic Link.")

    def _set_session_cookie(request: Request, response: Response) -> None:
        is_https = request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https"
        response.set_cookie(
            key=COOKIE_NAME,
            value=auth.sign_session_cookie(),
            max_age=auth.session_days * 86400,
            httponly=True,
            secure=is_https,
            samesite="lax",
            path="/",
        )

    async def _sync_onedrive_async() -> None:
        if od_client is not None:
            try:
                await asyncio.to_thread(od_client.sync_all_lists, store)
            except Exception:
                pass

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "service": "wechat-ai-assistant", "version": "0.1.0"}

    # --- WeCom callback routes ---

    @app.get("/api/wecom/app/callback", response_class=PlainTextResponse)
    @app.get("/api/wecom/kf/callback", response_class=PlainTextResponse)
    async def wecom_verify_url(msg_signature: str = "", timestamp: str = "", nonce: str = "", echostr: str = ""):
        try:
            plain = wc_gw.verify_url(msg_signature=msg_signature, timestamp=timestamp, nonce=nonce, echostr=echostr)
            return PlainTextResponse(content=plain, status_code=200)
        except PermissionError:
            raise HTTPException(status_code=403, detail="invalid signature")
        except Exception:
            raise HTTPException(status_code=400, detail="verify failed")

    @app.post("/api/wecom/app/callback", response_class=PlainTextResponse)
    @app.post("/api/wecom/kf/callback", response_class=PlainTextResponse)
    async def wecom_callback_post(request: Request, msg_signature: str = "", timestamp: str = "", nonce: str = ""):
        body = await request.body()
        try:
            ev = wc_gw.decrypt_callback_xml(
                msg_signature=msg_signature,
                timestamp=timestamp,
                nonce=nonce,
                body=body,
            )

            async def _safe_dispatch() -> None:
                try:
                    await wc_gw.handle_callback_event(ev)
                except Exception as exc:
                    logging.getLogger("uvicorn.error").error("WeCom dispatch error: %s", type(exc).__name__)

            asyncio.create_task(_safe_dispatch())
            return PlainTextResponse(content="success", status_code=200)
        except PermissionError:
            raise HTTPException(status_code=403, detail="invalid signature")
        except Exception:
            return PlainTextResponse(content="success", status_code=200)

    # --- Web UI & Auth routes ---

    @app.get("/", response_class=HTMLResponse)
    async def index_page():
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(content=html)

    @app.get("/auth/magic")
    async def magic_login(request: Request, token: str = ""):
        if not auth.consume_magic_token(token):
            return HTMLResponse(
                content=(
                    "<!doctype html><html><meta charset='utf-8'><body style='font-family:\"Figtree\",-apple-system,sans-serif;background:#f6f7fb;color:#323338;padding:48px;text-align:center;'>"
                    "<div style='max-width:460px;margin:0 auto;background:#fff;border:1px solid #e6e9ef;border-radius:12px;padding:32px;box-shadow:0 8px 24px rgba(0,0,0,0.06);'>"
                    "<h2 style='margin-bottom:12px;'>Magic Link Expired or Already Used</h2>"
                    "<p style='color:#676879;font-size:14px;line-height:1.6;'>Send <b>看板</b> to your WeChat assistant for a fresh 5-minute single-use link, or return to the workspace and sign in with a 6-digit WeChat code.</p>"
                    "<a href='/' style='display:inline-block;margin-top:18px;background:#0073ea;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;'>Back to Executive Work OS</a>"
                    "</div></body></html>"
                ),
                status_code=403,
            )
        resp = RedirectResponse(url="/", status_code=302)
        _set_session_cookie(request, resp)
        return resp

    @app.get("/api/auth/me")
    async def auth_status(request: Request):
        return {
            "authenticated": auth.verify_session_cookie(request.cookies.get(COOKIE_NAME)),
            "public_base_url": cfg.web_public_base_url,
        }

    @app.post("/api/auth/request-code")
    async def request_login_code(request: Request):
        ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
        if not auth.can_request_code(ip):
            raise HTTPException(status_code=429, detail="Too many code requests. Please try again in 10 minutes.")
        code = auth.mint_login_code(300)
        res = await wc_gw.send_app_push(f"🔐 Executive Work OS Sign-In Code: `{code}`\n(Valid for 5 minutes — do not share)")
        if res.get("skipped"):
            return {"sent": False, "message": "Local dev mode: use a Magic Link to sign in."}
        return {"sent": True, "message": "6-digit code sent to your WeChat (AI工作助理)."}

    @app.post("/api/auth/verify-code")
    async def verify_login_code(request: Request, body: VerifyCodeBody, response: Response):
        if not auth.verify_login_code(body.code):
            raise HTTPException(status_code=401, detail="Invalid or expired verification code")
        _set_session_cookie(request, response)
        return {"authenticated": True}

    @app.post("/api/auth/logout")
    async def logout(response: Response):
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"authenticated": False}

    # --- Protected Dashboard APIs ---

    @app.get("/api/dashboard/overview", dependencies=[Depends(require_session)])
    async def get_overview():
        ov = store.dashboard_overview(daily_capacity=cfg.daily_capacity_hours)
        ov["onedrive_vault_url"] = "https://wissentek.sharepoint.cn/sites/chairman-vault/Shared%20Documents/Forms/AllItems.aspx"
        ov["onedrive_lists_url"] = "https://wissentek-my.sharepoint.cn/my"
        return ov

    @app.post("/api/items", dependencies=[Depends(require_session)])
    async def create_item_api(body: ItemCreateBody):
        today_str = datetime.now().strftime("%Y-%m-%d")
        start_d = body.planned_start_at or today_str
        end_d = body.planned_end_at or start_d
        act = ActionMutation(
            list_type=body.list_type,
            work_domain=body.work_domain,
            project_name=body.project_name.strip() or "General Ops",
            title=body.title.strip(),
            owner=body.owner.strip() or "Chairman",
            planned_start_at=start_d,
            planned_end_at=end_d,
            estimated_hours=body.estimated_hours,
            priority=body.priority,
        )
        res = store.apply_proposal_atomic(
            proposal_id=None,
            actions=[act],
            source_ids=[],
            doc_paths=[],
            brief_summary=f"Created in Work OS: {body.title}",
        )
        asyncio.create_task(_sync_onedrive_async())
        return {"created_ids": res["inserted_item_ids"]}

    @app.patch("/api/items/{item_id}", dependencies=[Depends(require_session)])
    async def patch_item(item_id: int, body: ItemUpdateBody):
        updated = store.update_item_fields(item_id, body.model_dump(exclude_none=True))
        if not updated:
            raise HTTPException(status_code=404, detail="Item not found or no fields changed")
        asyncio.create_task(_sync_onedrive_async())
        return {"item": updated}

    @app.delete("/api/items/{item_id}", dependencies=[Depends(require_session)])
    async def delete_item_api(item_id: int):
        if not store.delete_item(item_id):
            raise HTTPException(status_code=404, detail="Item not found")
        asyncio.create_task(_sync_onedrive_async())
        return {"deleted": True}

    @app.post("/api/items/{item_id}/promote", dependencies=[Depends(require_session)])
    async def promote_item(item_id: int, body: PromoteIdeaBody):
        updated = store.promote_idea_to_project(
            item_id,
            project_name=body.project_name,
            planned_start_at=body.planned_start_at,
            planned_end_at=body.planned_end_at,
            estimated_hours=body.estimated_hours,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Idea item not found")
        asyncio.create_task(_sync_onedrive_async())
        return {"item": updated}

    @app.post("/api/items/{item_id}/start", dependencies=[Depends(require_session)])
    async def start_item_api(item_id: int):
        updated = store.start_item(item_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Item not found")
        asyncio.create_task(_sync_onedrive_async())
        return {"item": updated}

    @app.post("/api/items/{item_id}/complete", dependencies=[Depends(require_session)])
    async def complete_item_api(item_id: int, body: CompleteItemBody):
        updated = store.complete_item(item_id, actual_hours=body.actual_hours)
        if not updated:
            raise HTTPException(status_code=404, detail="Item not found")
        asyncio.create_task(_sync_onedrive_async())
        return {"item": updated}

    @app.post("/api/sync/onedrive", dependencies=[Depends(require_session)])
    async def force_sync_onedrive():
        if od_client is None:
            return {"synced": False, "urls": {}}
        urls = await asyncio.to_thread(od_client.sync_all_lists, store)
        return {"synced": True, "urls": urls}

    return app
