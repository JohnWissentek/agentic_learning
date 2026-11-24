"""WeCom Scheme B unified HTTPS callback, KF merged_msg sync, 8s quiet aggregator, and App push."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import secrets
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from wechat_assistant.config import Settings, redact_secrets


logger = logging.getLogger("uvicorn.error")


def compute_signature(token: str, timestamp: str, nonce: str, msg_encrypt: str) -> str:
    return hashlib.sha1("".join(sorted([token, timestamp, nonce, msg_encrypt])).encode("utf-8")).hexdigest()


def decrypt_wecom_payload(aes_key_43: str, cipher_b64: str, expected_receive_id: str = "") -> tuple[str, str]:
    key = base64.b64decode(aes_key_43 + "=")
    if len(key) != 32:
        raise ValueError("Invalid EncodingAESKey length")
    cipher = Cipher(algorithms.AES(key), modes.CBC(key[:16]))
    dec = cipher.decryptor()
    raw = dec.update(base64.b64decode(cipher_b64)) + dec.finalize()
    pad = raw[-1]
    if pad < 1 or pad > 32:
        raise ValueError(f"Invalid PKCS7 pad: {pad}")
    unpadded = raw[:-pad]
    msg_len = int.from_bytes(unpadded[16:20], "big")
    content = unpadded[20 : 20 + msg_len].decode("utf-8")
    receive_id = unpadded[20 + msg_len :].decode("utf-8")
    if expected_receive_id and receive_id and receive_id != expected_receive_id:
        raise ValueError("CorpID mismatch")
    return content, receive_id


@dataclass
class _BufferedBatch:
    texts: list[str] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    msg_ids: list[str] = field(default_factory=list)
    timer_task: asyncio.Task[Any] | None = None


class QuietAggregator:
    """Async buffer grouping rapid single-item forwards within `quiet_seconds`."""

    def __init__(
        self,
        *,
        quiet_seconds: float,
        on_flush: Callable[[str, str, list[dict[str, Any]], str], Awaitable[None]],
    ) -> None:
        self.quiet_seconds = max(0.0, quiet_seconds)
        self.on_flush = on_flush
        self._batches: dict[str, _BufferedBatch] = {}
        self._lock = asyncio.Lock()

    async def push(
        self,
        sender_key: str,
        *,
        text: str = "",
        attachments: list[dict[str, Any]] | None = None,
        msg_id: str = "",
    ) -> None:
        atts = attachments or []
        t = (text or "").strip()

        if t == "好了":
            await self.flush_now(sender_key)
            return

        async with self._lock:
            batch = self._batches.setdefault(sender_key, _BufferedBatch())
            if batch.timer_task and not batch.timer_task.done():
                batch.timer_task.cancel()
            if t:
                batch.texts.append(t)
            batch.attachments.extend(atts)
            if msg_id:
                batch.msg_ids.append(msg_id)
            batch.timer_task = asyncio.create_task(self._delayed_flush(sender_key))

    async def _delayed_flush(self, sender_key: str) -> None:
        try:
            await asyncio.sleep(self.quiet_seconds)
            await self.flush_now(sender_key)
        except asyncio.CancelledError:
            return

    def has_pending_batch(self, sender_key: str) -> bool:
        batch = self._batches.get(sender_key)
        return bool(batch and batch.timer_task and not batch.timer_task.done())

    async def flush_now(self, sender_key: str) -> None:
        async with self._lock:
            batch = self._batches.pop(sender_key, None)
        if not batch:
            return
        current = asyncio.current_task()
        if batch.timer_task and batch.timer_task is not current and not batch.timer_task.done():
            batch.timer_task.cancel()
        combined_text = "\n".join(batch.texts).strip()
        primary_msg_id = batch.msg_ids[0] if batch.msg_ids else f"batch_{int(time.time() * 1000)}"
        await self.on_flush(sender_key, combined_text, batch.attachments, primary_msg_id)


class WeComGateway:
    """Unified WeCom Customer Service + Self-built App gateway for personal WeChat interaction."""

    def __init__(
        self,
        settings: Settings,
        *,
        turn_processor: Callable[[str, str, list[dict[str, Any]], str], Awaitable[str]],
    ) -> None:
        self.settings = settings
        self.turn_processor = turn_processor
        self.data_dir = Path(settings.data_dir)
        self.tmp_dir = Path(os.environ.get("TMP_CACHE_DIR", str(self.data_dir.parent / "tmp_cache")))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

        self._token_value = ""
        self._token_exp = 0.0
        self._token_lock = asyncio.Lock()
        self._seen_msg_ids: set[str] = set()
        self._seen_order: list[str] = []
        self._blocked_attempts = 0
        self.aggregator = QuietAggregator(
            quiet_seconds=float(os.environ.get("SEGMENT_QUIET_SECONDS", "2")),
            on_flush=self._handle_flushed_kf_batch,
        )

    @property
    def owner_whitelist_path(self) -> Path:
        return self.data_dir / "owner_whitelist.txt"

    def get_owner_external_userid(self) -> str:
        if self.settings.owner_external_userid:
            return self.settings.owner_external_userid
        if self.owner_whitelist_path.exists():
            return self.owner_whitelist_path.read_text(encoding="utf-8").strip()
        return ""

    def set_owner_external_userid(self, external_userid: str) -> None:
        self.owner_whitelist_path.parent.mkdir(parents=True, exist_ok=True)
        self.owner_whitelist_path.write_text(external_userid.strip(), encoding="utf-8")
        os.chmod(self.owner_whitelist_path, 0o600)

    def verify_url(self, *, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        """Verify WeCom callback URL GET challenge using App token & AES key."""
        clean_echo = echostr.replace(" ", "+")
        token = self.settings.wecom_app_token
        aes_key = self.settings.wecom_app_aes_key
        expected = compute_signature(token, timestamp, nonce, clean_echo)
        if msg_signature != expected:
            raise PermissionError("Invalid WeCom signature")
        plain, _ = decrypt_wecom_payload(aes_key, clean_echo, self.settings.wecom_corp_id)
        return plain

    def decrypt_callback_xml(self, *, msg_signature: str, timestamp: str, nonce: str, body: bytes) -> dict[str, str]:
        root = ET.fromstring(body.decode("utf-8"))
        enc = root.findtext("Encrypt") or ""
        token = self.settings.wecom_app_token
        aes_key = self.settings.wecom_app_aes_key
        if not (token and aes_key and enc and msg_signature == compute_signature(token, timestamp, nonce, enc)):
            raise PermissionError("Invalid callback POST signature")
        plain_xml, _ = decrypt_wecom_payload(aes_key, enc, self.settings.wecom_corp_id)
        ev = ET.fromstring(plain_xml)
        return {child.tag: (child.text or "") for child in ev}

    async def get_access_token(self) -> str:
        async with self._token_lock:
            now = time.time()
            if self._token_value and now < self._token_exp - 60:
                return self._token_value
            secret = self.settings.wecom_app_secret or self.settings.wecom_kf_secret
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
                    params={"corpid": self.settings.wecom_corp_id, "corpsecret": secret},
                )
                data = r.json()
            if data.get("errcode", 0) != 0:
                raise RuntimeError(f"WeCom gettoken failed: errcode={data.get('errcode')}")
            self._token_value = data["access_token"]
            self._token_exp = now + int(data.get("expires_in", 7200))
            return self._token_value

    async def send_app_push(self, content: str) -> dict[str, Any]:
        """Push proactive text notification via self-built App (`工作助理`) -> WeChat Plugin."""
        if not (self.settings.wecom_corp_id and self.settings.wecom_app_agent_id and self.settings.wecom_app_secret):
            return {"skipped": True, "reason": "missing_wecom_app_config"}
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=15.0) as client:
            for part in self._split_chunks(content, limit=1800):
                resp = await client.post(
                    "https://qyapi.weixin.qq.com/cgi-bin/message/send",
                    params={"access_token": token},
                    json={
                        "touser": "@all",
                        "msgtype": "text",
                        "agentid": int(self.settings.wecom_app_agent_id),
                        "text": {"content": part},
                    },
                )
                data = resp.json()
        return data

    async def send_kf_text(self, *, touser: str, open_kfid: str, content: str) -> None:
        token = await self.get_access_token()
        kfid = open_kfid or self.settings.wecom_kf_open_kfid
        async with httpx.AsyncClient(timeout=15.0) as client:
            for part in self._split_chunks(content, limit=1800):
                resp = await client.post(
                    "https://qyapi.weixin.qq.com/cgi-bin/kf/send_msg",
                    params={"access_token": token},
                    json={
                        "touser": touser,
                        "open_kfid": kfid,
                        "msgtype": "text",
                        "text": {"content": part},
                    },
                )
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                if data.get("errcode", 0) != 0:
                    logger.warning("kf/send_msg errcode=%s, falling back to app push", data.get("errcode"))
                    await self.send_app_push(part)

    @staticmethod
    def _split_chunks(text: str, limit: int = 1800) -> list[str]:
        """Split text into chunks strictly <= `limit` UTF-8 bytes (WeCom limit is 2048 bytes)."""
        if len(text.encode("utf-8")) <= limit:
            return [text]

        chunks: list[str] = []
        cur = ""
        cur_bytes = 0
        for line in text.splitlines(keepends=True):
            line_bytes = len(line.encode("utf-8"))
            if line_bytes > limit:
                if cur:
                    chunks.append(cur.rstrip())
                    cur, cur_bytes = "", 0
                piece = ""
                piece_bytes = 0
                for ch in line:
                    cb = len(ch.encode("utf-8"))
                    if piece_bytes + cb > limit and piece:
                        chunks.append(piece.rstrip())
                        piece, piece_bytes = "", 0
                    piece += ch
                    piece_bytes += cb
                if piece:
                    chunks.append(piece.rstrip())
                continue

            if cur_bytes + line_bytes > limit and cur:
                chunks.append(cur.rstrip())
                cur, cur_bytes = "", 0
            cur += line
            cur_bytes += line_bytes
        if cur:
            chunks.append(cur.rstrip())
        return chunks or [text[: limit // 3]]

    async def _transcribe_audio_dashscope(self, local_path: str | Path) -> str:
        """Transcribe downloaded WeCom/KF voice bytes directly via DashScope `qwen3-asr-flash`."""
        key = self.settings.dashscope_api_key
        if not key or key.startswith(("sk-fake", "sk-test")):
            return ""
        p = Path(local_path)
        if not p.exists():
            return ""
        ext = p.suffix.lower().lstrip(".")
        mime_map = {
            "amr": "audio/amr",
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "m4a": "audio/mp4",
        }
        mime = mime_map.get(ext, "audio/amr")
        try:
            b64_uri = f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode('ascii')}"
            async with httpx.AsyncClient(timeout=25.0) as client:
                r = await client.post(
                    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={
                        "model": "qwen3-asr-flash",
                        "input": {"messages": [{"role": "user", "content": [{"audio": b64_uri}]}]},
                    },
                )
            if r.status_code != 200:
                logger.warning("DashScope ASR status=%s", r.status_code)
                return ""
            items = r.json().get("output", {}).get("choices", [{}])[0].get("message", {}).get("content", [])
            parts = [it.get("text", "") for it in items if isinstance(it, dict)]
            return "".join(parts).strip()
        except Exception as exc:
            logger.warning("DashScope ASR error=%s", type(exc).__name__)
            return ""

    async def _append_voice_text(
        self,
        texts: list[str],
        atts: list[dict[str, Any]],
        recognition: str,
        media_id: str,
        fmt: str = "amr",
    ) -> None:
        rec = (recognition or "").strip()
        if rec:
            texts.append(f"[语音转写] {rec}")
            return
        if not media_id:
            return
        clean_fmt = (fmt or "amr").lower().lstrip(".")
        dl = await self._download_media(media_id, f".{clean_fmt}")
        if dl:
            atts.append(dl)
            asr_text = await self._transcribe_audio_dashscope(dl["path"])
            if asr_text:
                texts.append(f"[语音转写] {asr_text}")
                return
        texts.append("[收到语音消息，暂未能识别清晰文字，请补充文字说明]")

    def _mark_seen(self, msgid: str) -> bool:
        if not msgid:
            return True
        if msgid in self._seen_msg_ids:
            return False
        self._seen_msg_ids.add(msgid)
        self._seen_order.append(msgid)
        if len(self._seen_order) > 1000:
            oldest = self._seen_order.pop(0)
            self._seen_msg_ids.discard(oldest)
        return True

    async def _download_media(
        self,
        media_id: str,
        fallback_ext: str = ".bin",
        explicit_filename: str = "",
    ) -> dict[str, Any] | None:
        if not media_id:
            return None
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.get(
                "https://qyapi.weixin.qq.com/cgi-bin/media/get",
                params={"access_token": token, "media_id": media_id},
            )
            if r.headers.get("content-type", "").startswith("application/json"):
                return None
            disp = r.headers.get("content-disposition", "")
            m = re.search(r'filename="?([^";]+)"?', disp)
            clean_explicit = Path(explicit_filename).name if explicit_filename else ""
            fname = clean_explicit or (
                urllib.parse.unquote(m.group(1)) if m else f"{secrets.token_hex(4)}{fallback_ext}"
            )
            local_path = self.tmp_dir / f"{int(time.time())}_{fname}"
            local_path.write_bytes(r.content)
            return {"filename": fname, "path": str(local_path), "size": len(r.content)}

    async def _parse_app_xml_message(self, ev: dict[str, str]) -> tuple[str, list[dict[str, Any]]]:
        """Normalize XML callback messages from the self-built App (`AI工作助理`) inside WeChat Plugin."""
        mtype = (ev.get("MsgType") or "").lower()
        texts: list[str] = []
        atts: list[dict[str, Any]] = []

        if mtype == "text":
            content = (ev.get("Content") or "").strip()
            if content:
                texts.append(content)
        elif mtype == "voice":
            await self._append_voice_text(
                texts,
                atts,
                ev.get("Recognition", ""),
                ev.get("MediaId", ""),
                ev.get("Format", "amr"),
            )
        elif mtype in {"file", "image", "video", "shortvideo"}:
            ext = (ev.get("FileExt") or "").lower().lstrip(".")
            fallback_map = {
                "file": f".{ext}" if ext else ".bin",
                "image": ".jpg",
                "video": ".mp4",
                "shortvideo": ".mp4",
            }
            dl = await self._download_media(
                ev.get("MediaId", ""),
                fallback_map[mtype],
                explicit_filename=ev.get("FileName", ""),
            )
            if dl:
                atts.append(dl)
                texts.append(f"[收到附件] {dl['filename']}")
        elif mtype == "link":
            summary = " ".join(
                part for part in (ev.get("Title", ""), ev.get("Description", ""), ev.get("Url", "")) if part
            ).strip()
            if summary:
                texts.append(f"[链接] {summary}")
        elif mtype == "location":
            label = ev.get("Label", "").strip()
            coords = f"({ev.get('Location_X', '')},{ev.get('Location_Y', '')})"
            texts.append(f"[位置] {label} {coords}".strip())

        return "\n".join(t for t in texts if t).strip(), atts

    def _build_arrival_ack(self, msg_type: str, text_content: str = "") -> str | None:
        mtype = (msg_type or "").lower()
        t = (text_content or "").strip()
        if mtype == "text":
            if not t or t == "好了":
                return None
            return "⚡ 已收到，正在为您分析处理（约 5~8 秒）…"
        if mtype == "voice":
            return "🎙️ 已收到语音，正在转写并分析（约 6~10 秒）…"
        if mtype in {"file", "image", "video", "shortvideo"}:
            return "📎 已收到附件，正在解析并分析（约 6~10 秒）…"
        if mtype in {"merged_msg", "link", "location"}:
            return "⚡ 已收到，正在为您分析处理（约 5~8 秒）…"
        return None

    async def handle_callback_event(self, ev: dict[str, str]) -> None:
        """Process decrypted WeCom XML callback asynchronously."""
        event_name = ev.get("Event", "")
        msg_type = ev.get("MsgType", "")

        if event_name == "kf_msg_or_event":
            await self.sync_and_dispatch_kf(ev.get("Token", ""), ev.get("OpenKfId", ""))
            return

        if msg_type.lower() == "event":
            return

        msgid = ev.get("MsgId", "")
        if not self._mark_seen(msgid):
            return

        from_user = ev.get("FromUserName", "owner") or "owner"
        sender_key = f"app|{from_user}"
        if not self.aggregator.has_pending_batch(sender_key):
            ack = self._build_arrival_ack(msg_type.lower(), (ev.get("Content") or "").strip())
            if ack:
                await self.send_app_push(ack)

        text, atts = await self._parse_app_xml_message(ev)
        if not (text or atts):
            return
        await self.aggregator.push(sender_key, text=text, attachments=atts, msg_id=msgid)

    async def _parse_kf_message(self, msg: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        """Extract normalized text and downloaded attachments from text/merged_msg/voice/file/image."""
        mtype = msg.get("msgtype", "")
        texts: list[str] = []
        atts: list[dict[str, Any]] = []

        if mtype == "text":
            texts.append(msg.get("text", {}).get("content", ""))
        elif mtype == "voice":
            v = msg.get("voice", {})
            await self._append_voice_text(
                texts,
                atts,
                v.get("recognition", ""),
                v.get("media_id", ""),
                "amr",
            )
        elif mtype in {"file", "image", "video"}:
            ext_map = {"file": ".bin", "image": ".jpg", "video": ".mp4"}
            media_id = msg.get(mtype, {}).get("media_id", "")
            dl = await self._download_media(media_id, ext_map[mtype])
            if dl:
                atts.append(dl)
                texts.append(f"[收到附件] {dl['filename']}")
        elif mtype == "merged_msg":
            mm = msg.get("merged_msg", {})
            texts.append(f"【合并转发聊天记录：{mm.get('title', '对话')}】")
            for idx, sub in enumerate(mm.get("item", []), 1):
                sender = sub.get("sender_name", "未知")
                ts = sub.get("send_time")
                t_label = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M") if ts else ""
                smtype = sub.get("msgtype", "")
                mc_raw = sub.get("msg_content", "")
                try:
                    mc = json.loads(mc_raw) if isinstance(mc_raw, str) and mc_raw.startswith("{") else mc_raw
                except json.JSONDecodeError:
                    mc = mc_raw

                if smtype == "text" and isinstance(mc, dict):
                    content_str = mc.get("text", {}).get("content", "")
                    texts.append(f"{idx}. [{t_label} {sender}] {content_str}")
                elif smtype in {"file", "image", "voice"} and isinstance(mc, dict):
                    media_id = mc.get(smtype, {}).get("media_id", "")
                    dl = await self._download_media(media_id, f".{smtype}")
                    if dl:
                        atts.append(dl)
                        texts.append(f"{idx}. [{t_label} {sender}] <附件: {dl['filename']}>")
                else:
                    texts.append(f"{idx}. [{t_label} {sender}] ({smtype}) {mc}")

        return "\n".join(t for t in texts if t).strip(), atts

    async def sync_and_dispatch_kf(self, event_token: str, open_kfid: str) -> None:
        token = await self.get_access_token()
        kfid = open_kfid or self.settings.wecom_kf_open_kfid
        cursor_file = self.data_dir / "kf_cursor.txt"
        cursor = cursor_file.read_text(encoding="utf-8").strip() if cursor_file.exists() else ""

        req_body: dict[str, Any] = {"token": event_token, "open_kfid": kfid, "limit": 100}
        if cursor:
            req_body["cursor"] = cursor

        async with httpx.AsyncClient(timeout=20.0) as client:
            res = (
                await client.post(
                    "https://qyapi.weixin.qq.com/cgi-bin/kf/sync_msg",
                    params={"access_token": token},
                    json=req_body,
                )
            ).json()

        if res.get("errcode", 0) != 0:
            return
        if res.get("next_cursor"):
            cursor_file.write_text(res["next_cursor"], encoding="utf-8")

        owner_ext = self.get_owner_external_userid()
        for msg in res.get("msg_list", []):
            if msg.get("origin") != 3:
                continue  # Ignore non-WeChat-user system/self messages
            msgid = msg.get("msgid", "")
            ext_id = msg.get("external_userid", "")
            if not self._mark_seen(msgid) or not ext_id or msg.get("msgtype") == "event":
                continue

            if not owner_ext:
                self.set_owner_external_userid(ext_id)
                owner_ext = ext_id
            elif ext_id != owner_ext:
                self._blocked_attempts += 1
                continue  # Silent whitelist enforcement

            sender_key = f"{ext_id}|{kfid}"
            if not self.aggregator.has_pending_batch(sender_key):
                mtype = (msg.get("msgtype") or "").lower()
                raw_txt = (msg.get("text", {}).get("content") or "").strip() if mtype == "text" else ""
                ack = self._build_arrival_ack(mtype, raw_txt)
                if ack:
                    await self.send_kf_text(touser=ext_id, open_kfid=kfid, content=ack)

            text, atts = await self._parse_kf_message(msg)
            if not (text or atts):
                continue
            await self.aggregator.push(sender_key, text=text, attachments=atts, msg_id=msgid)

    async def _handle_flushed_kf_batch(
        self,
        sender_key: str,
        combined_text: str,
        attachments: list[dict[str, Any]],
        msg_id: str,
    ) -> None:
        is_app = sender_key.startswith("app|")
        ext_id, _, kfid = sender_key.partition("|")
        from_user = kfid or "owner"
        try:
            sender_tag = f"wecom:{from_user}" if is_app else f"wechat:{ext_id[-6:]}"
            reply = await self.turn_processor(combined_text, sender_tag, attachments, msg_id)
            safe_reply = redact_secrets(reply, self.settings)
            voice_matches = re.findall(r"\[语音转写\]\s*([^\n]+)", combined_text)
            if voice_matches:
                joined = "；".join(m.strip() for m in voice_matches if m.strip())[:120]
                if joined:
                    safe_reply = f"🗣️ **语音识别**：「{joined}」\n\n{safe_reply}"
            if is_app:
                await self.send_app_push(safe_reply)
            else:
                await self.send_kf_text(touser=ext_id, open_kfid=kfid, content=safe_reply)
        except Exception as exc:
            logger.error(
                "WeCom turn failed: %s",
                redact_secrets(f"{type(exc).__name__}: {exc}", self.settings),
            )
            await self.send_app_push("⚠️ 刚才处理消息时遇到瞬时异常，请稍后重试或换文字发送。")
