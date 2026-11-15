"""Dual-engine AI Search Router (Metaso for China + Serper for Global + Jina Fallback).

Implements:
- Ch 2 Routing: China-first Metaso webpage/scholar/document + Global Serper search/scholar/patents
- Ch 5 Tool Use: Clean typed clients enforcing API contracts
- Ch 12 Exception Handling: HTTP 200 `errCode` detection, `size`/`page` mutual exclusion,
  exponential backoff, cross-engine failover, and `r.jina.ai` Markdown extraction fallback.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Literal, Protocol

import httpx

from pso_workflow.config import CostLedger, WorkflowSettings
from pso_workflow.schemas import SearchHit
from pso_workflow.tools.evidence_vault import score_source_authority

METASO_SCOPE_KEYS: dict[str, str] = {
    "webpage": "webpages",
    "document": "documents",
    "scholar": "scholars",
    "video": "videos",
    "image": "images",
}


class MetasoAPIError(RuntimeError):
    """Raised when Metaso returns a business errCode or transport failure."""

    def __init__(self, err_code: int, message: str) -> None:
        self.err_code = err_code
        super().__init__(f"Metaso error (errCode={err_code}): {message}")


class SerperAPIError(RuntimeError):
    """Raised when Serper returns an HTTP error."""


class SearchRouterProtocol(Protocol):
    """Protocol enabling offline trajectory testing with mocked search results."""

    async def search_track(
        self,
        *,
        track_id: str,
        geo_scope: Literal["CN", "GLOBAL"],
        query: str,
        mode: str = "webpage",
        num_results: int = 8,
    ) -> list[SearchHit]: ...

    async def read_fulltext(self, *, url: str, track_id: str) -> str: ...


class MetasoClient:
    """Metaso AI Search & Markdown Reader async client."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://metaso.cn/api/v1",
        timeout: float = 20.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def build_search_payload(
        self,
        *,
        query: str,
        scope: str = "webpage",
        size: int | None = 8,
        page: int | None = None,
        include_summary: bool = True,
    ) -> dict[str, Any]:
        """Construct payload strictly enforcing `size` vs `page` mutual exclusion."""
        if size is not None and page is not None:
            raise ValueError("Metaso API forbids passing `size` and `page` simultaneously (errCode=1000)")
        payload: dict[str, Any] = {
            "q": query,
            "scope": scope,
            "includeSummary": include_summary,
            "includeRawContent": False,
        }
        if page is not None:
            payload["page"] = int(page)
        else:
            payload["size"] = int(size or 8)
        return payload

    @staticmethod
    def parse_search_response(
        body: dict[str, Any], *, scope: str, query: str, geo_scope: Literal["CN", "GLOBAL"] = "CN"
    ) -> tuple[list[SearchHit], int]:
        """Inspect errCode even under HTTP 200 and map scope-specific result lists."""
        err_code = body.get("errCode")
        if err_code not in (None, 0):
            raise MetasoAPIError(int(err_code), str(body.get("errMsg") or body))

        array_key = METASO_SCOPE_KEYS.get(scope, "webpages")
        raw_items = body.get(array_key) or body.get("data") or []
        credits = int(body.get("credits") or 0)
        hits: list[SearchHit] = []
        for idx, it in enumerate(raw_items):
            url = (it.get("link") or it.get("url") or "").strip()
            title = (it.get("title") or "").strip()
            if not url or not title:
                continue
            tier = score_source_authority(url, title)
            hits.append(
                SearchHit(
                    engine="metaso",
                    geo_scope=geo_scope,
                    query=query,
                    title=title,
                    url=url,
                    snippet=str(it.get("snippet") or ""),
                    summary=str(it.get("summary") or it.get("snippet") or ""),
                    published_date=str(it.get("date") or ""),
                    authority_tier=tier,
                    score=max(0.1, 1.0 - idx * 0.05),
                )
            )
        return hits, credits

    async def search(
        self,
        *,
        query: str,
        scope: str = "webpage",
        size: int | None = 8,
        page: int | None = None,
        geo_scope: Literal["CN", "GLOBAL"] = "CN",
    ) -> tuple[list[SearchHit], int]:
        if not self.api_key:
            raise MetasoAPIError(2005, "METASO_API_KEY is empty")
        payload = self.build_search_payload(query=query, scope=scope, size=size, page=page)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/search", headers=self._headers(), json=payload
            )
            resp.raise_for_status()
            body = resp.json()
        return self.parse_search_response(body, scope=scope, query=query, geo_scope=geo_scope)

    async def reader(self, url: str) -> tuple[str, int]:
        if not self.api_key:
            raise MetasoAPIError(2005, "METASO_API_KEY is empty")
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(
                f"{self.base_url}/reader",
                headers=self._headers(),
                json={"url": url},
            )
            resp.raise_for_status()
            body = resp.json()
        err_code = body.get("errCode")
        if err_code not in (None, 0):
            raise MetasoAPIError(int(err_code), str(body.get("errMsg") or body))
        md = str(body.get("markdown") or body.get("content") or "").strip()
        credits = int(body.get("credits") or 3)
        return md, credits


class SerperClient:
    """Serper.dev Google Search / Scholar / Patents async client."""

    def __init__(self, api_key: str, time_range: str = "qdr:y", timeout: float = 20.0) -> None:
        self.api_key = api_key
        self.time_range = time_range
        self.timeout = timeout

    async def search(
        self,
        *,
        query: str,
        endpoint: Literal["search", "scholar", "patents"] = "search",
        num: int = 8,
        geo_scope: Literal["CN", "GLOBAL"] = "GLOBAL",
        gl: str = "us",
        hl: str = "en",
    ) -> list[SearchHit]:
        if not self.api_key:
            raise SerperAPIError("SERPER_API_KEY is empty")
        payload: dict[str, Any] = {"q": query, "num": min(num, 20)}
        if endpoint == "search":
            payload["gl"] = gl
            payload["hl"] = hl
            if self.time_range:
                payload["tbs"] = self.time_range
        url = f"https://google.serper.dev/{endpoint}"
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise SerperAPIError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            body = resp.json()

        hits: list[SearchHit] = []
        answer_box = body.get("answerBox") or {}
        if answer_box.get("snippet") and answer_box.get("link"):
            hits.append(
                SearchHit(
                    engine="serper",
                    geo_scope=geo_scope,
                    query=query,
                    title=str(answer_box.get("title") or "AnswerBox"),
                    url=str(answer_box["link"]),
                    snippet=str(answer_box["snippet"]),
                    summary=str(answer_box["snippet"]),
                    authority_tier=score_source_authority(str(answer_box["link"])),
                    score=1.0,
                )
            )

        for idx, it in enumerate(body.get("organic", [])):
            link = (it.get("link") or it.get("pdfUrl") or "").strip()
            title = (it.get("title") or "").strip()
            if not link or not title:
                continue
            tier = score_source_authority(link, title)
            hits.append(
                SearchHit(
                    engine="serper",
                    geo_scope=geo_scope,
                    query=query,
                    title=title,
                    url=link,
                    snippet=str(it.get("snippet") or ""),
                    summary=str(it.get("snippet") or ""),
                    published_date=str(it.get("date") or it.get("year") or ""),
                    authority_tier=tier,
                    score=max(0.1, 0.95 - idx * 0.05),
                )
            )
        return hits


class DualEngineSearchRouter:
    """Ch 2 geo-aware router + Ch 12 resilient retry/failover wrapper."""

    def __init__(self, settings: WorkflowSettings, ledger: CostLedger) -> None:
        self.settings = settings
        self.ledger = ledger
        self.metaso = MetasoClient(
            api_key=settings.metaso_api_key, base_url=settings.metaso_api_base
        )
        self.serper = SerperClient(
            api_key=settings.serper_api_key, time_range=settings.serper_time_range
        )

    async def search_track(
        self,
        *,
        track_id: str,
        geo_scope: Literal["CN", "GLOBAL"],
        query: str,
        mode: str = "webpage",
        num_results: int = 8,
    ) -> list[SearchHit]:
        """Execute geo-routed search with automatic cross-engine failover."""
        if geo_scope == "CN":
            primary = ("metaso", mode if mode in METASO_SCOPE_KEYS else "webpage")
            secondary = ("serper", "scholar" if mode == "scholar" else "search")
        else:
            primary = ("serper", mode if mode in ("search", "scholar", "patents") else "search")
            secondary = ("metaso", "scholar" if mode == "scholar" else "webpage")

        for engine, eng_mode in (primary, secondary):
            for attempt in range(2):
                t0 = time.perf_counter()
                try:
                    if engine == "metaso" and self.metaso.api_key:
                        hits, credits = await self.metaso.search(
                            query=query, scope=eng_mode, size=num_results, geo_scope=geo_scope
                        )
                        self.ledger.record_search(
                            kind="metaso_search",
                            track_id=track_id,
                            query=query,
                            hits=len(hits),
                            credits=credits or 3,
                            latency_ms=int((time.perf_counter() - t0) * 1000),
                            ok=True,
                        )
                        if hits:
                            return hits
                    elif engine == "serper" and self.serper.api_key:
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
                        break  # fatal auth error -> switch immediately to fallback engine
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
        if self.metaso.api_key:
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

        # Fallback: r.jina.ai
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
