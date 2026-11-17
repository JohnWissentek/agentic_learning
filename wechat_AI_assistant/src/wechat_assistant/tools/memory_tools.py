"""Group 1 Memory Tools: hybrid FTS5+LIKE search, cited page reading, and project timeline."""

from __future__ import annotations

from typing import Any

from wechat_assistant.storage.db import Database


def hybrid_search(db: Database, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Retrieve matching sources with page snippets for grounded answering."""
    rows = db.search_sources(query, top_k=top_k)
    results: list[dict[str, Any]] = []
    q_terms = [t.strip() for t in query.split() if len(t.strip()) >= 2]
    for r in rows:
        best_page = 1
        best_snippet = (r.get("raw_text") or "")[:300]
        for p in r.get("pages", []):
            txt = p.get("text", "")
            if any(t in txt for t in q_terms) or (query.strip() and query.strip() in txt):
                best_page = int(p.get("page", 1))
                best_snippet = txt[:400]
                break
        results.append(
            {
                "source_id": int(r["id"]),
                "title": r.get("title", ""),
                "page": best_page,
                "snippet": best_snippet,
                "onedrive_web_url": r.get("onedrive_web_url", ""),
                "created_at": r.get("created_at", ""),
            }
        )
    return results


def read_doc_pages(db: Database, source_id: int, page_numbers: list[int] | None = None) -> list[dict[str, Any]]:
    """Read full extracted text for specified page numbers of a document."""
    return db.get_source_pages(source_id, page_numbers=page_numbers)


def trace_timeline(db: Database, project_name: str) -> dict[str, Any]:
    """Retrieve chronological project actions, status, and archival sources."""
    return db.get_timeline_for_project(project_name)
