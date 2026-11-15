"""Evidence Vault - Auditable evidence storage.

Design Pattern Reference:
- Chapter 14 (P213-230): Knowledge Retrieval - Traceability
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from boiler_fbg_workflow.schemas import EvidenceRecord, EvidenceType


class EvidenceVault:
    """SQLite-based evidence storage with full audit trail."""
    
    def __init__(self, db_path: str | Path = "./evidence_registry/evidence.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence (
                    ev_id TEXT PRIMARY KEY,
                    ev_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    url TEXT,
                    date TEXT,
                    content_hash TEXT,
                    status TEXT DEFAULT 'PENDING_VERIFICATION',
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence_references (
                    ev_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (ev_id, artifact_id),
                    FOREIGN KEY (ev_id) REFERENCES evidence(ev_id)
                )
            """)
            conn.commit()
    
    def register(self, record: EvidenceRecord) -> str:
        """Register a new evidence record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO evidence 
                (ev_id, ev_type, title, source, url, date, content_hash, status, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.ev_id,
                record.ev_type.value,
                record.title,
                record.source,
                record.url,
                record.date,
                record.content_hash,
                record.status,
                record.notes,
                record.created_at,
                datetime.now().isoformat(),
            ))
            conn.commit()
        return record.ev_id
    
    def get(self, ev_id: str) -> EvidenceRecord | None:
        """Retrieve an evidence record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM evidence WHERE ev_id = ?", (ev_id,)
            ).fetchone()
            
            if not row:
                return None
            
            refs = conn.execute(
                "SELECT artifact_id FROM evidence_references WHERE ev_id = ?", (ev_id,)
            ).fetchall()
            
            return EvidenceRecord(
                ev_id=row["ev_id"],
                ev_type=EvidenceType(row["ev_type"]),
                title=row["title"],
                source=row["source"],
                url=row["url"] or "",
                date=row["date"] or "",
                content_hash=row["content_hash"] or "",
                status=row["status"],
                notes=row["notes"] or "",
                created_at=row["created_at"],
                referenced_by=[r["artifact_id"] for r in refs],
            )
    
    def add_reference(self, ev_id: str, artifact_id: str) -> None:
        """Add a reference from an artifact to evidence."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO evidence_references (ev_id, artifact_id, created_at)
                VALUES (?, ?, ?)
            """, (ev_id, artifact_id, datetime.now().isoformat()))
            conn.commit()
    
    def list_all(self) -> list[EvidenceRecord]:
        """List all evidence records."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM evidence ORDER BY created_at DESC").fetchall()
            return [
                EvidenceRecord(
                    ev_id=row["ev_id"],
                    ev_type=EvidenceType(row["ev_type"]),
                    title=row["title"],
                    source=row["source"],
                    url=row["url"] or "",
                    date=row["date"] or "",
                    content_hash=row["content_hash"] or "",
                    status=row["status"],
                    notes=row["notes"] or "",
                    created_at=row["created_at"],
                )
                for row in rows
            ]
    
    def get_statistics(self) -> dict[str, Any]:
        """Get evidence statistics."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
            by_type = dict(conn.execute(
                "SELECT ev_type, COUNT(*) FROM evidence GROUP BY ev_type"
            ).fetchall())
            by_status = dict(conn.execute(
                "SELECT status, COUNT(*) FROM evidence GROUP BY status"
            ).fetchall())
            
            return {
                "total": total,
                "by_type": by_type,
                "by_status": by_status,
            }
    
    def export_index(self, output_path: str | Path) -> None:
        """Export evidence index to JSON."""
        records = self.list_all()
        output = {
            "exported_at": datetime.now().isoformat(),
            "statistics": self.get_statistics(),
            "records": [r.model_dump() for r in records],
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)


def compute_content_hash(content: str | bytes) -> str:
    """Compute SHA256 hash of content."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return f"sha256:{hashlib.sha256(content).hexdigest()}"
