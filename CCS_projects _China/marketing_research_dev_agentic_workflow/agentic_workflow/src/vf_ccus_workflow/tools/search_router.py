"""Dual-Engine Resilient Search Router: Metaso AI (CN Primary) + Serper (Global Primary)."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Literal

import httpx

from vf_ccus_workflow.config import CostLedger, WorkflowSettings
from vf_ccus_workflow.schemas import EvidenceSearchHit, GeoScope


class MetasoAPIError(RuntimeError):
    """Raised when Metaso returns a non-zero errCode or HTTP error."""

    def __init__(self, err_code: int | str, message: str) -> None:
        super().__init__(f"Metaso errCode={err_code}: {message}")
        self.err_code = err_code


class MetasoSearchClient:
    """Async wrapper for Metaso `/search` & `/reader` adhering to API mutual-exclusion rules."""

    def __init__(self, api_key: str, base_url: str = "https://metaso.cn/api/v1") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def search(
        self,
        *,
        query: str,
        scope: Literal["webpage", "document", "scholar", "video", "image"] = "webpage",
        size: int = 8,
        page: int | None = None,
        geo_scope: GeoScope = "CN",
    ) -> tuple[list[EvidenceSearchHit], int]:
        if not self.api_key:
            return [], 0
        payload: dict[str, Any] = {
            "q": query,
            "scope": scope,
            "includeSummary": False,
            "includeRawContent": False,
            "conciseSnippet": False,
        }
        # CRITICAL API RULE: `size` and `page` MUST NOT be sent together
        if page is not None:
            payload["page"] = max(1, page)
        else:
            payload["size"] = max(1, min(size, 20))

        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(f"{self.base_url}/search", headers=self._headers(), json=payload)
            if resp.status_code != 200:
                raise MetasoAPIError(resp.status_code, resp.text[:300])
            body = resp.json()

        err_code = body.get("errCode")
        if err_code not in (None, 0):
            raise MetasoAPIError(err_code, str(body.get("errMsg", "unknown")))

        scope_key_map = {
            "webpage": "webpages",
            "document": "documents",
            "scholar": "scholars",
            "video": "videos",
            "image": "images",
        }
        items = body.get(scope_key_map.get(scope, "webpages"), []) or []
        credits = int(body.get("credits", 1) or 1)
        hits: list[EvidenceSearchHit] = []
        for item in items:
            url = item.get("link") or item.get("url") or ""
            snippet = item.get("snippet") or item.get("abstract") or item.get("summary") or ""
            title = item.get("title") or "Untitled"
            if url and snippet:
                hits.append(
                    EvidenceSearchHit(
                        title=title,
                        url=url,
                        snippet=snippet,
                        content=item.get("rawContent") or "",
                        source_engine="metaso",
                        geo_scope=geo_scope,
                        published_at=str(item.get("date") or item.get("publishTime") or ""),
                        score=float(item.get("score") or 0.0),
                    )
                )
        return hits, credits

    async def reader(self, url: str) -> tuple[str, int]:
        if not self.api_key:
            return "", 0
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(
                f"{self.base_url}/reader",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "text/markdown, application/json",
                    "Content-Type": "application/json",
                },
                json={"url": url},
            )
            if resp.status_code != 200:
                raise MetasoAPIError(resp.status_code, resp.text[:250])
            ctype = resp.headers.get("content-type", "")
            if "application/json" in ctype:
                body = resp.json()
                err_code = body.get("errCode")
                if err_code not in (None, 0):
                    raise MetasoAPIError(err_code, str(body.get("errMsg", "reader error")))
                md = body.get("markdown") or body.get("content") or ""
                return md[:8000], int(body.get("credits", 1) or 1)
            return resp.text[:8000], 1


class SerperSearchClient:
    """Async wrapper for Serper Google Search (`search` & `scholar`)."""

    def __init__(self, api_key: str, default_tbs: str = "qdr:y") -> None:
        self.api_key = api_key
        self.default_tbs = default_tbs
        self.base_url = "https://google.serper.dev"

    async def search(
        self,
        *,
        query: str,
        endpoint: Literal["search", "scholar", "news"] = "search",
        num: int = 8,
        geo_scope: GeoScope = "GLOBAL",
        gl: str = "us",
        hl: str = "en",
        tbs: str | None = None,
    ) -> list[EvidenceSearchHit]:
        if not self.api_key:
            return []
        payload: dict[str, Any] = {
            "q": query,
            "num": max(1, min(num, 20)),
            "gl": gl,
            "hl": hl,
        }
        effective_tbs = self.default_tbs if tbs is None else tbs
        if effective_tbs and endpoint != "scholar":
            payload["tbs"] = effective_tbs

        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(
                f"{self.base_url}/{endpoint}",
                headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
                json=payload,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Serper HTTP {resp.status_code}: {resp.text[:300]}")
            body = resp.json()

        raw_list = body.get("organic") or body.get("news") or body.get("results") or []
        hits: list[EvidenceSearchHit] = []
        for idx, item in enumerate(raw_list):
            url = item.get("link") or item.get("pdfUrl") or ""
            snippet = item.get("snippet") or ""
            title = item.get("title") or "Untitled"
            if url and snippet:
                hits.append(
                    EvidenceSearchHit(
                        title=title,
                        url=url,
                        snippet=snippet,
                        content="",
                        source_engine="serper",
                        geo_scope=geo_scope,
                        published_at=str(item.get("date") or item.get("year") or ""),
                        score=round(1.0 - idx * 0.05, 3),
                    )
                )
        return hits


class DualEngineSearchRouter:
    """Ch 12/16 Fault-Tolerant Search Router: CN->Metaso(Serper fb), GLOBAL->Serper(Metaso fb)."""

    def __init__(self, settings: WorkflowSettings, ledger: CostLedger) -> None:
        self.settings = settings
        self.ledger = ledger
        self.metaso = MetasoSearchClient(settings.metaso_api_key, settings.metaso_api_base)
        self.serper = SerperSearchClient(settings.serper_api_key, settings.serper_time_range)

    async def search_track(
        self,
        *,
        track_id: str,
        geo_scope: GeoScope,
        query: str,
        mode: Literal["webpage", "document", "scholar", "search", "news"] = "webpage",
        num_results: int = 8,
    ) -> list[EvidenceSearchHit]:
        if geo_scope == "CN":
            engines: list[tuple[str, str]] = [
                ("metaso", mode if mode in ("webpage", "document", "scholar") else "webpage"),
                ("serper", "scholar" if mode == "scholar" else "search"),
            ]
        else:
            engines = [
                ("serper", "scholar" if mode == "scholar" else "search"),
                ("metaso", mode if mode in ("webpage", "document", "scholar") else "webpage"),
            ]

        for engine, eng_mode in engines:
            if engine == "metaso" and not self.metaso.api_key:
                continue
            if engine == "serper" and not self.serper.api_key:
                continue

            for attempt in range(2):
                t0 = time.perf_counter()
                try:
                    if engine == "metaso":
                        hits, credits = await self.metaso.search(
                            query=query,
                            scope=eng_mode,  # type: ignore[arg-type]
                            size=num_results,
                            geo_scope=geo_scope,
                        )
                        self.ledger.record_search(
                            kind="metaso_search",
                            track_id=track_id,
                            query=query,
                            hits=len(hits),
                            credits=credits,
                            latency_ms=int((time.perf_counter() - t0) * 1000),
                            ok=True,
                        )
                        if hits:
                            return hits
                    else:
                        hits = await self.serper.search(
                            query=query,
                            endpoint=eng_mode,  # type: ignore[arg-type]
                            num=num_results,
                            geo_scope=geo_scope,
                            gl="cn" if geo_scope == "CN" else "us",
                            hl="zh-cn" if geo_scope == "CN" else "en",
                        )
                        self.ledger.record_search(
                            kind="serper_search",
                            track_id=track_id,
                            query=query,
                            hits=len(hits),
                            credits=1,
                            latency_ms=int((time.perf_counter() - t0) * 1000),
                            ok=True,
                        )
                        if hits:
                            return hits
                except MetasoAPIError as exc:
                    self.ledger.record_search(
                        kind="metaso_search",
                        track_id=track_id,
                        query=query,
                        hits=0,
                        latency_ms=int((time.perf_counter() - t0) * 1000),
                        ok=False,
                    )
                    if exc.err_code == 2005:
                        break
                except Exception:
                    self.ledger.record_search(
                        kind=f"{engine}_search",
                        track_id=track_id,
                        query=query,
                        hits=0,
                        latency_ms=int((time.perf_counter() - t0) * 1000),
                        ok=False,
                    )
                await asyncio.sleep(1.0 * (attempt + 1))
        return []

    async def read_fulltext(self, *, url: str, track_id: str) -> str:
        """Extract clean Markdown via Metaso Reader with Jina Reader fallback."""
        if self.metaso.api_key and not url.startswith("siggi-corpus://"):
            t0 = time.perf_counter()
            try:
                md, credits = await self.metaso.reader(url)
                self.ledger.record_search(
                    kind="metaso_reader",
                    track_id=track_id,
                    query=url,
                    hits=1 if md else 0,
                    credits=credits,
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                    ok=bool(md),
                )
                if len(md) >= 180:
                    return md
            except Exception:
                self.ledger.record_search(
                    kind="metaso_reader",
                    track_id=track_id,
                    query=url,
                    hits=0,
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                    ok=False,
                )

        if url.startswith("siggi-corpus://"):
            return ""

        t1 = time.perf_counter()
        headers = {}
        if self.settings.jina_api_key:
            headers["Authorization"] = f"Bearer {self.settings.jina_api_key}"
        try:
            async with httpx.AsyncClient(timeout=18.0, follow_redirects=True) as client:
                resp = await client.get(f"https://r.jina.ai/{url}", headers=headers)
                if resp.status_code == 200:
                    text = resp.text.strip()
                    self.ledger.record_search(
                        kind="jina_reader",
                        track_id=track_id,
                        query=url,
                        hits=1 if text else 0,
                        latency_ms=int((time.perf_counter() - t1) * 1000),
                        ok=bool(text),
                    )
                    return text[:8000]
        except Exception:
            pass
        return ""
