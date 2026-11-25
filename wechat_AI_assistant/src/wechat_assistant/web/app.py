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
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from wechat_assistant.config import DashScopeLLMGateway, Settings, now_local
from wechat_assistant.graph import ChiefOfStaffEngine
from wechat_assistant.intake.mail_poller import mail_hourly_scheduler_loop
from wechat_assistant.intake.wecom_gateway import WeComGateway
from wechat_assistant.schemas import ActionMutation, ListType, PriorityLevel, WorkDomain
from wechat_assistant.storage.db import Database
from wechat_assistant.tools.onedrive_tools import OneDrive21VianetClient
from wechat_assistant.tools.schedule_tools import calc_business_date

COOKIE_NAME = "chairman_cockpit_session"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def _validate_optional_iso_date(v: str | None) -> str | None:
    if v is None:
        return None
    cleaned = v.strip()
    if not cleaned:
        return ""
    if len(cleaned) < 10:
        raise ValueError("Date must be YYYY-MM-DD")
    date.fromisoformat(cleaned[:10])
    return cleaned[:10]


class ItemUpdateBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    list_type: ListType | None = None
    work_domain: WorkDomain | None = None
    project_name: str | None = Field(default=None, min_length=1, max_length=80)
    deliverable: str | None = Field(default=None, max_length=300)
    acceptance_criteria: str | None = Field(default=None, max_length=300)
    milestone_stage: str | None = Field(default=None, max_length=80)
    owner: str | None = Field(default=None, min_length=1, max_length=80)
    assignee: str | None = Field(default=None, max_length=80)
    external_partner: str | None = Field(default=None, max_length=120)
    blocker_note: str | None = Field(default=None, max_length=300)
    source_channel: Literal["wechat", "outlook", "web"] | None = None
    planned_start_at: str | None = None
    planned_end_at: str | None = None
    estimated_hours: float | None = Field(default=None, ge=0.0, le=200.0)
    actual_hours: float | None = Field(default=None, ge=0.0, le=200.0)
    priority: PriorityLevel | None = None
    status: Literal["todo", "in_progress", "done"] | None = None
    stage: str | None = None

    @field_validator("planned_start_at", "planned_end_at")
    @classmethod
    def _check_dates(cls, v: str | None) -> str | None:
        return _validate_optional_iso_date(v)

    @model_validator(mode="after")
    def _check_date_order(self) -> "ItemUpdateBody":
        if self.planned_start_at and self.planned_end_at and self.planned_end_at < self.planned_start_at:
            raise ValueError("planned_end_at cannot be earlier than planned_start_at")
        return self


class ItemCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    list_type: ListType = ListType.NEXT_ACTION
    work_domain: WorkDomain = WorkDomain.RD
    project_name: str = Field(default="通用待办", min_length=1, max_length=80)
    deliverable: str = Field(default="", max_length=300)
    acceptance_criteria: str = Field(default="", max_length=300)
    milestone_stage: str = Field(default="已启动", max_length=80)
    owner: str = "本人"
    assignee: str = ""
    external_partner: str = "无"
    blocker_note: str = Field(default="", max_length=300)
    source_channel: Literal["wechat", "outlook", "web"] = "web"
    planned_start_at: str | None = None
    planned_end_at: str | None = None
    estimated_hours: float = Field(default=0.0, ge=0.0, le=200.0)
    priority: PriorityLevel = PriorityLevel.P1

    @field_validator("planned_start_at", "planned_end_at")
    @classmethod
    def _check_dates(cls, v: str | None) -> str | None:
        return _validate_optional_iso_date(v)

    @model_validator(mode="after")
    def _check_date_order(self) -> "ItemCreateBody":
        if self.planned_start_at and self.planned_end_at and self.planned_end_at < self.planned_start_at:
            raise ValueError("planned_end_at cannot be earlier than planned_start_at")
        return self


class NoteCreateBody(BaseModel):
    kind: Literal["ceo_evaluation", "comment", "progress"]
    content: str = Field(min_length=1, max_length=500)
    from_party: str = "徐宏玮"


class PromoteIdeaBody(BaseModel):
    project_name: str = Field(min_length=1, max_length=80)
    planned_start_at: str
    planned_end_at: str
    estimated_hours: float = Field(default=0.0, ge=0.0, le=200.0)

    @field_validator("planned_start_at", "planned_end_at")
    @classmethod
    def _check_dates(cls, v: str) -> str:
        res = _validate_optional_iso_date(v)
        if not res:
            raise ValueError("Date must be YYYY-MM-DD")
        return res

    @model_validator(mode="after")
    def _check_date_order(self) -> "PromoteIdeaBody":
        if self.planned_end_at < self.planned_start_at:
            raise ValueError("planned_end_at cannot be earlier than planned_start_at")
        return self


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
        self._verify_failures: list[float] = []
        self._verify_locked_until: float = 0.0

    def is_verify_locked(self) -> bool:
        return time.time() < self._verify_locked_until

    def mint_magic_token(self, ttl_seconds: int = 300) -> str:
        now = time.time()
        self._magic_tokens = {k: v for k, v in self._magic_tokens.items() if v > now}
        tok = secrets.token_urlsafe(24)
        self._magic_tokens[tok] = now + ttl_seconds
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
        if now < self._verify_locked_until:
            return False
        self._login_codes = {k: v for k, v in self._login_codes.items() if v > now}
        self._verify_failures = [t for t in self._verify_failures if now - t < 600]
        for valid_code in list(self._login_codes):
            if hmac.compare_digest(valid_code, code.strip()):
                del self._login_codes[valid_code]
                self._verify_failures.clear()
                return True
        self._verify_failures.append(now)
        if len(self._verify_failures) >= 5:
            self._login_codes.clear()
            self._verify_locked_until = now + 600
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
    """Build v2.0 flat independent task-card Morning/Evening WeChat digest (zero repetition)."""
    today = ov["today"]
    today_dt = date.fromisoformat(today[:10])
    open_items = [i for i in ov["items"] if i["status"] != "done" and i.get("list_type") != ListType.IDEA.value]
    waits = ov.get("waiting_items") or []
    urgent_cnt = 0
    for i in open_items:
        pe_raw = (i.get("planned_end_at") or "").strip()
        if pe_raw:
            try:
                if (date.fromisoformat(pe_raw[:10]) - today_dt).days <= 2:
                    urgent_cnt += 1
            except ValueError:
                pass

    ch_map = {"wechat": "微信", "mail_in": "邮件", "mail_out": "发件", "web": "驾驶舱"}
    src_map = {"wechat": "微信", "outlook": "Outlook", "web": "驾驶舱"}
    status_map = {"todo": "待办", "in_progress": "进行中", "done": "已完成"}

    card_blocks: list[str] = []
    for it in open_items[:8]:
        st_lbl = "等待外部" if it.get("list_type") == ListType.WAITING_FOR.value else status_map.get(it.get("status", "todo"), "待办")
        src_lbl = src_map.get(str(it.get("source_channel") or "wechat").lower(), "微信")
        deliverable = (it.get("deliverable") or "").strip() or it["title"]
        stage_lbl = (it.get("milestone_stage") or "已启动").strip()
        owner = (it.get("owner") or "本人").strip()
        assignee = (it.get("assignee") or "").strip() or owner
        ext = (it.get("external_partner") or "").strip() or "无"

        ps_str = (it.get("planned_start_at") or "").strip()
        pe_str = (it.get("planned_end_at") or "").strip()
        elapsed_note = ""
        if ps_str:
            try:
                ps_dt = date.fromisoformat(ps_str[:10])
                if ps_dt > today_dt:
                    elapsed_note = f"距开始还有 {(ps_dt - today_dt).days} 天"
                else:
                    elapsed_days = (today_dt - ps_dt).days + 1
                    elapsed_note = f"已进行 {elapsed_days} 天"
            except ValueError:
                pass
        due_note = ""
        if pe_str:
            try:
                left = (date.fromisoformat(pe_str[:10]) - today_dt).days
                due_note = f"距截止剩 {left} 天" if left >= 0 else f"已超期 {abs(left)} 天"
            except ValueError:
                pass
        span_notes = "｜".join(x for x in (elapsed_note, due_note) if x)
        sched_line = f"{ps_str or '-'} → {pe_str or '【待补齐】'}" + (f"（{span_notes}）" if span_notes else "")

        block_lines = [
            f"【任务 #{it['id']}】{it['title']}（归属：{it.get('project_name', '日常事务')} / {it.get('work_domain', '')}｜{it.get('priority', 'P1')}｜{st_lbl}｜来源：{src_lbl}）",
            f"1）目标与交付成果：{deliverable}",
        ]
        timeline = list(it.get("timeline") or [])
        if timeline:
            block_lines.append(f"2）当前进度与往来沟通：{stage_lbl}")
            for entry in timeline[-2:]:
                ch_lbl = ch_map.get(entry.get("channel", "wechat"), entry.get("channel", ""))
                who = (
                    f"{entry.get('from_party', '')}→{entry.get('to_party', '')}"
                    if entry.get("to_party")
                    else (entry.get("from_party") or "")
                )
                who_part = f"｜{who}" if who else ""
                raw_ts = str(entry.get("timestamp") or "").strip()
                short_ts = raw_ts[5:16] if (len(raw_ts) >= 16 and raw_ts[4:5] == "-" and raw_ts[7:8] == "-") else raw_ts
                block_lines.append(f"   - [{short_ts}｜{ch_lbl}{who_part}] {entry.get('summary', '')}")
        else:
            block_lines.append(f"2）当前进度与往来沟通：{stage_lbl}")

        block_lines.append(f"3）责任分工：负责人：{owner} ｜ 实施人：{assignee} ｜ 外部协作：{ext}")
        block_lines.append(f"4）时间排期：{sched_line}")

        blocker = (it.get("blocker_note") or "").strip() or "无"
        docs = list(it.get("onedrive_doc_paths") or [])
        doc_part = f" ｜ 档案：{', '.join(str(d).rsplit('/', 1)[-1] for d in docs[:2])}" if docs else ""
        block_lines.append(f"5）卡点与关联档案：{blocker}{doc_part}")

        comments = list(it.get("comments") or [])
        if comments:
            latest_cmts = "；".join(
                f"[{c.get('date', '')}] {c.get('content', '')}" if isinstance(c, dict) else str(c)
                for c in comments[-2:]
            )
            block_lines.append(f"6）补充备注（Comments）：{latest_cmts}")

        ceo_evals = list(it.get("ceo_evaluation") or [])
        if ceo_evals:
            last_ev = ceo_evals[-1]
            ev_txt = f"[{last_ev.get('date', '')}] {last_ev.get('content', '')}" if isinstance(last_ev, dict) else str(last_ev)
            block_lines.append(f"7）CEO 评价：{ev_txt}")

        card_blocks.append("\n".join(block_lines))

    body_text = "\n\n━━━━━━━━━━━━━━━━━━━━\n".join(card_blocks) if card_blocks else "- 暂无未完成在途任务"
    if len(open_items) > 8:
        body_text += f"\n\n…另有 {len(open_items) - 8} 项在途任务，请打开驾驶舱查看全量"

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
                "\n\n📝 **今日进度盘点（请一句话确认，方便自动闭合周期）**：\n"
                + "\n".join(lines)
                + "\n👉 可直接回复：`#3 做完了，#5 开始了`（未完事项也可说明新截止日）"
            )

    return (
        f"{kind}（{today}）\n"
        f"📊 在途任务：{len(open_items)} 项 ｜ 外部等待：{len(waits)} 项 ｜ 临期/超期预警：{urgent_cnt} 项\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n{body_text}"
        + checkin_block
        + "\n\n━━━━━━━━━━━━━━━━━━━━\n"
        + "👉 微信直接回复：`完成 #1` 闭环 ｜ `评价 #2：...` 加 CEO 评价 ｜ `备注 #2：...` 加补充说明\n"
        + f"📊 点击打开驾驶舱：{magic_url}"
    )


async def _daily_digest_scheduler(engine: ChiefOfStaffEngine, gateway: WeComGateway) -> None:
    morning = os.environ.get("DAILY_MORNING_DIGEST", "08:30").strip()
    evening = os.environ.get("DAILY_EVENING_DIGEST", "18:00").strip()
    while True:
        try:
            now = now_local()
            hm = now.strftime("%H:%M")
            day_key = f"digest:{now.strftime('%Y-%m-%d')}:{hm}"
            if now.weekday() < 5 and hm in {morning, evening} and not engine.db.is_external_seen(day_key):
                kind = "🌅 早间工作报告" if hm == morning else "🌆 晚间复盘简报"
                ov = engine.db.dashboard_overview(engine.settings.daily_capacity_hours)
                magic_url = engine.magic_link_factory()
                msg = build_daily_digest_message(ov, kind, magic_url)
                await gateway.send_app_push(msg)
                engine.db.mark_external_seen(day_key, source="daily_digest")
                # Persist digest into dialogue history so follow-up replies ("#3做完了") resolve cleanly
                engine.db.append_conversation_turn(
                    thread_id="owner",
                    role="assistant",
                    content=msg,
                    intent="digest:morning" if hm == morning else "digest:evening_checkin",
                )
        except Exception as exc:
            logging.getLogger("uvicorn.error").warning("Daily digest scheduler error: %s", type(exc).__name__)
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
                except Exception as exc:
                    logging.getLogger("uvicorn.error").warning("Heartbeat push failed: %s", type(exc).__name__)
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
        except Exception as exc:
            logging.getLogger("uvicorn.error").warning("Heartbeat watcher cleanup error: %s", type(exc).__name__)


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
                except Exception as exc:
                    logging.getLogger("uvicorn.error").warning("Initial OneDrive sync failed: %s", type(exc).__name__)
            bg_tasks.append(asyncio.create_task(_daily_digest_scheduler(eng, wc_gw)))
            has_mail_creds = bool(
                (cfg.mail_tenant_id and cfg.mail_client_id and cfg.mail_client_secret)
                or od_client is not None
            )
            if cfg.mail_enabled and has_mail_creds:
                bg_tasks.append(
                    asyncio.create_task(
                        mail_hourly_scheduler_loop(
                            settings=cfg,
                            db=store,
                            od_client=od_client,
                            engine=eng,
                            send_push=wc_gw.send_app_push,
                        )
                    )
                )
        try:
            yield
        finally:
            for t in bg_tasks:
                t.cancel()
            if bg_tasks:
                await asyncio.gather(*bg_tasks, return_exceptions=True)
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
            except Exception as exc:
                logging.getLogger("uvicorn.error").warning("Async OneDrive sync failed: %s", type(exc).__name__)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "service": "wechat-ai-assistant", "version": "3.0.0"}

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
        except Exception as exc:
            logging.getLogger("uvicorn.error").warning("WeCom callback POST parse error: %s", type(exc).__name__)
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
        if auth.is_verify_locked():
            raise HTTPException(status_code=429, detail="Too many failed verification attempts. Please request a new code later.")
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
        today_str = now_local().strftime("%Y-%m-%d")
        start_d = body.planned_start_at if body.planned_start_at else today_str
        raw_end = (body.planned_end_at or "").strip() if body.planned_end_at is not None else ""
        if raw_end:
            end_d = raw_end
        else:
            base_d = start_d if start_d > today_str else today_str
            end_d = calc_business_date(base_d, 3)
        act = ActionMutation(
            list_type=body.list_type,
            work_domain=body.work_domain,
            project_name=body.project_name.strip() or "通用待办",
            title=body.title.strip(),
            deliverable=body.deliverable.strip(),
            acceptance_criteria=body.acceptance_criteria.strip(),
            milestone_stage=body.milestone_stage.strip() or "已启动",
            owner=body.owner.strip() or "本人",
            assignee=body.assignee.strip(),
            external_partner=body.external_partner.strip() or "无",
            blocker_note=body.blocker_note.strip(),
            source_channel=body.source_channel,
            planned_start_at=start_d,
            planned_end_at=end_d,
            estimated_hours=body.estimated_hours,
            priority=body.priority,
            missing_required_fields=[],
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

    @app.post("/api/items/{item_id}/note", dependencies=[Depends(require_session)])
    async def append_item_note_api(item_id: int, body: NoteCreateBody):
        if body.kind == "ceo_evaluation":
            updated = store.append_task_ceo_evaluation(item_id, body.content)
            if not updated:
                raise HTTPException(status_code=404, detail="Item not found")
            asyncio.create_task(_sync_onedrive_async())
            return {"item": updated}
        if body.kind == "comment":
            updated = store.append_task_comment(item_id, body.content)
            if not updated:
                raise HTTPException(status_code=404, detail="Item not found")
            asyncio.create_task(_sync_onedrive_async())
            return {"item": updated}
        entry = store.append_task_timeline(
            item_id,
            summary=body.content,
            channel="web",
            from_party=body.from_party.strip() or "徐宏玮",
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Item not found")
        asyncio.create_task(_sync_onedrive_async())
        return {"timeline_entry": entry}

    @app.get("/api/items/{item_id}/timeline", dependencies=[Depends(require_session)])
    async def get_item_timeline_api(item_id: int):
        item = store.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"item_id": item_id, "timeline": item.get("timeline") or []}

    @app.patch("/api/items/{item_id}", dependencies=[Depends(require_session)])
    async def patch_item(item_id: int, body: ItemUpdateBody):
        updated = store.update_item_fields(item_id, body.model_dump(mode="json", exclude_none=True))
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
        try:
            updated = store.promote_idea_to_project(
                item_id,
                project_name=body.project_name,
                planned_start_at=body.planned_start_at,
                planned_end_at=body.planned_end_at,
                estimated_hours=body.estimated_hours,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
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
