"""Dual-Engine Resilient Search Router: Metaso AI (CN Primary) + Serper (Global & PDF Primary)."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Literal

import httpx

from bfbg_workflow.config import CostLedger, WorkflowSettings
from bfbg_workflow.schemas import EvidenceSearchHit, GeoScope


class MetasoAPIError(RuntimeError):
    """Raised when Metaso returns a non-zero errCode or HTTP error."""

    def __init__(self, err_code: int | str, message: str) -> None:
        super().__init__(f"Metaso errCode={err_code}: {message}")
        self.err_code = err_code


class MetasoSearchClient:
    """Async wrapper for Metaso `/search` & `/reader` respecting size/page mutual exclusion."""

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
        # API mutual-exclusion rule: never send size and page together
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
        use_time_filter: bool = True,
    ) -> list[EvidenceSearchHit]:
        if not self.api_key:
            return []
        payload: dict[str, Any] = {"q": query, "num": max(1, min(num, 20))}
        if geo_scope == "CN":
            payload["gl"] = "cn"
            payload["hl"] = "zh-cn"
        else:
            payload["gl"] = "us"
            payload["hl"] = "en"
        if use_time_filter and self.default_tbs and endpoint != "scholar":
            payload["tbs"] = self.default_tbs

        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(
                f"{self.base_url}/{endpoint}",
                headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
                json=payload,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Serper HTTP {resp.status_code}: {resp.text[:250]}")
            body = resp.json()

        items = body.get("news" if endpoint == "news" else "organic", []) or []
        hits: list[EvidenceSearchHit] = []
        for idx, item in enumerate(items):
            url = item.get("link") or item.get("pdfUrl") or ""
            snippet = item.get("snippet") or item.get("publicationInfo") or ""
            title = item.get("title") or "Untitled"
            if url and (snippet or title):
                hits.append(
                    EvidenceSearchHit(
                        title=title,
                        url=url,
                        snippet=snippet or title,
                        content="",
                        source_engine="serper",
                        geo_scope=geo_scope,
                        published_at=str(item.get("date") or item.get("year") or ""),
                        score=max(0.1, 1.0 - idx * 0.08),
                    )
                )
        return hits


class JinaReaderClient:
    """Zero-config markdown reader fallback (`https://r.jina.ai/<url>`)."""

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key

    async def read(self, url: str) -> str:
        headers = {"Accept": "text/plain"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            resp = await client.get(f"https://r.jina.ai/{url}", headers=headers)
            if resp.status_code != 200:
                return ""
            return resp.text[:8000]


class DualEngineSearchRouter:
    """Ch 2 & Ch 12 Search Router: Metaso primary for CN, Serper primary for GLOBAL/PDF."""

    def __init__(self, settings: WorkflowSettings, ledger: CostLedger) -> None:
        self.settings = settings
        self.ledger = ledger
        self.metaso = MetasoSearchClient(settings.metaso_api_key, settings.metaso_api_base)
        self.serper = SerperSearchClient(settings.serper_api_key, settings.serper_time_range)
        self.jina = JinaReaderClient(settings.jina_api_key)

    async def search_track(
        self,
        *,
        track_id: str,
        geo_scope: GeoScope,
        query: str,
        num_results: int = 8,
        use_time_filter: bool = True,
    ) -> list[EvidenceSearchHit]:
        t0 = time.perf_counter()
        if geo_scope == "CN":
            try:
                hits, credits = await self.metaso.search(
                    query=query, scope="webpage", size=num_results, geo_scope="CN"
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
            except Exception:
                self.ledger.record_search(
                    kind="metaso_search_err",
                    track_id=track_id,
                    query=query,
                    hits=0,
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                    ok=False,
                )

            try:
                hits = await self.serper.search(
                    query=query,
                    endpoint="search",
                    num=num_results,
                    geo_scope="CN",
                    use_time_filter=use_time_filter,
                )
                self.ledger.record_search(
                    kind="serper_cn_fallback",
                    track_id=track_id,
                    query=query,
                    hits=len(hits),
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                    ok=True,
                )
                return hits
            except Exception:
                return []

        # GLOBAL or PDF search via Serper primary
        try:
            hits = await self.serper.search(
                query=query,
                endpoint="search",
                num=num_results,
                geo_scope=geo_scope,
                use_time_filter=use_time_filter,
            )
            self.ledger.record_search(
                kind="serper_global",
                track_id=track_id,
                query=query,
                hits=len(hits),
                latency_ms=int((time.perf_counter() - t0) * 1000),
                ok=True,
            )
            if hits:
                return hits
        except Exception:
            self.ledger.record_search(
                kind="serper_global_err",
                track_id=track_id,
                query=query,
                hits=0,
                latency_ms=int((time.perf_counter() - t0) * 1000),
                ok=False,
            )

        try:
            hits, credits = await self.metaso.search(
                query=query, scope="webpage", size=num_results, geo_scope=geo_scope
            )
            self.ledger.record_search(
                kind="metaso_global_fallback",
                track_id=track_id,
                query=query,
                hits=len(hits),
                credits=credits,
                latency_ms=int((time.perf_counter() - t0) * 1000),
                ok=True,
            )
            return hits
        except Exception:
            return []

    async def enrich_top_hits(
        self,
        hits: list[EvidenceSearchHit],
        *,
        max_fetch: int = 2,
    ) -> list[EvidenceSearchHit]:
        """Selectively extract full markdown via Metaso Reader or Jina Reader fallback."""
        if not hits:
            return hits

        async def _read_one(hit: EvidenceSearchHit) -> EvidenceSearchHit:
            if hit.content and len(hit.content) > 400:
                return hit
            if hit.url.lower().endswith(".pdf"):
                return hit
            for attempt in range(2):
                try:
                    if hit.source_engine == "metaso" and self.settings.metaso_api_key:
                        txt, credits = await self.metaso.reader(hit.url)
                        self.ledger.record_search(
                            kind="metaso_reader",
                            track_id="READER",
                            query=hit.url,
                            hits=1 if txt else 0,
                            credits=credits,
                            ok=bool(txt),
                        )
                        if txt:
                            return hit.model_copy(update={"content": txt})
                    txt = await self.jina.read(hit.url)
                    if txt:
                        return hit.model_copy(update={"content": txt})
                except Exception:
                    await asyncio.sleep(0.6 * (attempt + 1))
            return hit

        head = await asyncio.gather(*(_read_one(h) for h in hits[:max_fetch]))
        return list(head) + hits[max_fetch:]
