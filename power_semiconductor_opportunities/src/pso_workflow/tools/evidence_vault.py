"""Persistent SQLite Evidence Vault (Ch 8 Memory + Ch 14 Agentic RAG).

Handles URL canonicalization, SHA-1 deduplication across parallel track runs,
source authority tiering (T1..T4), full-text Markdown caching, and citation IDs.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pso_workflow.schemas import EvidenceRecord, SearchHit

_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "spm",
    "from",
    "source",
    "ref",
}

_T1_DOMAINS = (
    ".gov.cn",
    ".gov",
    "semi.org",
    "ieee.org",
    "iec.ch",
    "iso.org",
    "nist.gov",
    "energy.gov",
    "iea.org",
    "ndrc.gov.cn",
    "miit.gov.cn",
    "mee.gov.cn",
    "nea.gov.cn",
    "sgcc.com.cn",
    "csg.cn",
    "sciencedirect.com",
    "springer.com",
    "nature.com",
    "acs.org",
    "aip.org",
    "optics.org",
    "iopscience.iop.org",
    "arxiv.org",
    "cnki.net",
    "patents.google.com",
)

_T2_DOMAINS = (
    "kla.com",
    "appliedmaterials.com",
    "asml.com",
    "bruker.com",
    "thermofisher.com",
    "zeiss.com",
    "horiba.com",
    "inficon.com",
    "siemens-energy.com",
    "abb.com",
    "hitachienergy.com",
    "schneider-electric.com",
    "catl.com",
    "byd.com",
    "naura.com",
    "amec-inc.com",
    "skyverse.cn",
    "djtech.cn",
    "semiinsights.com",
    "trendforce.com",
    "yolegroup.com",
    "techinsights.com",
    "semiconductor-digest.com",
    "semiconductor-today.com",
    "pv-magazine.com",
    "hydrogeninsight.com",
    "energystorage.news",
)


def normalize_url(url: str) -> str:
    """Canonicalize URL by stripping tracking query parameters and trailing slashes."""
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    clean_q = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in _TRACKING_PARAMS
    ]
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(
        (
            parsed.scheme.lower() or "https",
            parsed.netloc.lower(),
            path,
            "",
            urlencode(sorted(clean_q)),
            "",
        )
    )


def url_sha1(url: str) -> str:
    """Return stable SHA-1 hex digest of canonicalized URL."""
    return hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()


def score_source_authority(url: str, title: str = "") -> Literal["T1", "T2", "T3", "T4"]:
    """Classify source credibility into T1 (standards/gov/peer-reviewed) .. T4 (social)."""
    host = urlparse(url or "").netloc.lower()
    low_title = (title or "").lower()
    if any(dom in host for dom in _T1_DOMAINS) or any(
        kw in low_title for kw in ("standard", "iso ", "iec ", "ieee", "gb/t", "十五五", "白皮书", "期刊")
    ):
        return "T1"
    if any(dom in host for dom in _T2_DOMAINS) or any(
        kw in low_title for kw in ("patent", "专利", "财报", "招股书", "年报", "semi")
    ):
        return "T2"
    if any(dom in host for dom in ("zhihu.com", "csdn.net", "sohu.com", "baijiahao", "163.com", "toutiao.com")):
        return "T4"
    return "T3"


class EvidenceVault:
    """Thread-safe SQLite store backing cross-track evidence memory & citation stability."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidences (
                    ev_id TEXT PRIMARY KEY,
                    url_hash TEXT UNIQUE NOT NULL,
                    track_id TEXT NOT NULL,
                    geo_scope TEXT NOT NULL,
                    engine TEXT NOT NULL,
                    authority_tier TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    published_date TEXT DEFAULT '',
                    snippet TEXT DEFAULT '',
                    full_markdown TEXT DEFAULT '',
                    query TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id TEXT NOT NULL,
                    engine TEXT NOT NULL,
                    geo_scope TEXT NOT NULL,
                    query TEXT NOT NULL,
                    hits_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _next_ev_id(self, geo_scope: str) -> str:
        prefix = "EV-CN-" if geo_scope == "CN" else "EV-GL-"
        cur = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM evidences WHERE geo_scope = ?", (geo_scope,)
        )
        n = int(cur.fetchone()["cnt"]) + 1
        candidate = f"{prefix}{n:03d}"
        while (
            self._conn.execute(
                "SELECT 1 FROM evidences WHERE ev_id = ?", (candidate,)
            ).fetchone()
            is not None
        ):
            n += 1
            candidate = f"{prefix}{n:03d}"
        return candidate

    def log_query(
        self, *, track_id: str, engine: str, geo_scope: str, query: str, hits_count: int
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO query_log (track_id, engine, geo_scope, query, hits_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (track_id, engine, geo_scope, query, hits_count, now),
            )

    def upsert_hit(
        self,
        *,
        track_id: str,
        hit: SearchHit,
        full_markdown: str = "",
    ) -> EvidenceRecord | None:
        """Insert or enrich a search hit; deduplicate on normalized URL hash."""
        norm = normalize_url(hit.url)
        if not norm:
            return None
        uhash = url_sha1(norm)
        tier = score_source_authority(norm, hit.title)
        now = datetime.now(timezone.utc).isoformat()
        snippet_text = (hit.summary or hit.snippet or "").strip()[:1500]
        md_text = (full_markdown or "").strip()[:8000]

        with self._lock, self._conn:
            existing = self._conn.execute(
                "SELECT * FROM evidences WHERE url_hash = ?", (uhash,)
            ).fetchone()
            if existing is not None:
                # Enrich full_markdown if newly extracted
                if md_text and len(md_text) > len(existing["full_markdown"] or ""):
                    self._conn.execute(
                        "UPDATE evidences SET full_markdown = ? WHERE url_hash = ?",
                        (md_text, uhash),
                    )
                return EvidenceRecord(
                    ev_id=existing["ev_id"],
                    track_id=existing["track_id"],
                    geo_scope=existing["geo_scope"],
                    engine=existing["engine"],
                    authority_tier=existing["authority_tier"],
                    title=existing["title"],
                    url=existing["url"],
                    published_date=existing["published_date"] or "",
                    snippet=existing["snippet"] or "",
                    full_markdown=md_text or existing["full_markdown"] or "",
                    query=existing["query"] or "",
                )

            ev_id = self._next_ev_id(hit.geo_scope)
            self._conn.execute(
                """
                INSERT INTO evidences (
                    ev_id, url_hash, track_id, geo_scope, engine, authority_tier,
                    title, url, published_date, snippet, full_markdown, query, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ev_id,
                    uhash,
                    track_id,
                    hit.geo_scope,
                    hit.engine,
                    tier,
                    hit.title.strip()[:400],
                    norm,
                    hit.published_date or "",
                    snippet_text,
                    md_text,
                    hit.query,
                    now,
                ),
            )
            return EvidenceRecord(
                ev_id=ev_id,
                track_id=track_id,
                geo_scope=hit.geo_scope,
                engine=hit.engine,
                authority_tier=tier,
                title=hit.title.strip()[:400],
                url=norm,
                published_date=hit.published_date or "",
                snippet=snippet_text,
                full_markdown=md_text,
                query=hit.query,
            )

    def list_by_track(self, track_id: str) -> list[EvidenceRecord]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM evidences
                WHERE track_id = ?
                ORDER BY CASE authority_tier WHEN 'T1' THEN 1 WHEN 'T2' THEN 2 WHEN 'T3' THEN 3 ELSE 4 END,
                         ev_id ASC
                """,
                (track_id,),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def list_all(self) -> list[EvidenceRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM evidences ORDER BY geo_scope ASC, ev_id ASC"
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = int(self._conn.execute("SELECT COUNT(*) FROM evidences").fetchone()[0])
            cn = int(
                self._conn.execute("SELECT COUNT(*) FROM evidences WHERE geo_scope='CN'").fetchone()[0]
            )
            gl = int(
                self._conn.execute("SELECT COUNT(*) FROM evidences WHERE geo_scope='GLOBAL'").fetchone()[0]
            )
            with_md = int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM evidences WHERE length(full_markdown) > 200"
                ).fetchone()[0]
            )
            by_track_rows = self._conn.execute(
                "SELECT track_id, geo_scope, COUNT(*) AS cnt FROM evidences GROUP BY track_id, geo_scope"
            ).fetchall()
        by_track: dict[str, dict[str, int]] = {}
        for r in by_track_rows:
            t = by_track.setdefault(r["track_id"], {"CN": 0, "GLOBAL": 0})
            t[r["geo_scope"]] = int(r["cnt"])
        return {
            "total": total,
            "cn_count": cn,
            "global_count": gl,
            "cn_ratio": round(cn / total, 4) if total else 0.0,
            "with_fulltext_count": with_md,
            "by_track": by_track,
        }

    @staticmethod
    def _row_to_record(r: sqlite3.Row) -> EvidenceRecord:
        return EvidenceRecord(
            ev_id=r["ev_id"],
            track_id=r["track_id"],
            geo_scope=r["geo_scope"],
            engine=r["engine"],
            authority_tier=r["authority_tier"],
            title=r["title"],
            url=r["url"],
            published_date=r["published_date"] or "",
            snippet=r["snippet"] or "",
            full_markdown=r["full_markdown"] or "",
            query=r["query"] or "",
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
