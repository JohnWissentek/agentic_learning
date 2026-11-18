"""Audit Logger for Temperature Monitoring System.

Provides complete audit trail of all readings, alerts, and actions.
All entries are timestamped and include hash verification.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from boiler_fbg_workflow.schemas import TemperatureAlert, TemperatureReading


class AuditLogger:
    """Audit logging with full traceability.
    
    Logs:
    - All temperature readings with source tags
    - All generated alerts
    - All acknowledgments and actions
    - System events
    
    All entries include:
    - Timestamp
    - Content hash for integrity verification
    - Data source tag (synthetic vs live)
    """
    
    def __init__(self, db_path: str | Path = "./outputs/audit_log.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize audit database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    channel_id INTEGER NOT NULL,
                    position_m REAL,
                    temperature_c REAL,
                    quality_flag TEXT,
                    data_source TEXT NOT NULL,
                    content_hash TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT UNIQUE NOT NULL,
                    timestamp TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    channel_id INTEGER,
                    current_value REAL,
                    threshold_value REAL,
                    message TEXT,
                    recommended_action TEXT,
                    acknowledged INTEGER DEFAULT 0,
                    ack_by TEXT,
                    ack_timestamp TEXT,
                    content_hash TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    description TEXT,
                    details TEXT,
                    content_hash TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)
            """)
            conn.commit()
    
    def _compute_hash(self, content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    
    def log_readings(self, readings: list[TemperatureReading]) -> None:
        """Log a batch of temperature readings."""
        with sqlite3.connect(self.db_path) as conn:
            for r in readings:
                content = f"{r.channel_id}|{r.temperature_c}|{r.timestamp}|{r.data_source}"
                content_hash = self._compute_hash(content)
                
                conn.execute("""
                    INSERT INTO readings 
                    (timestamp, channel_id, position_m, temperature_c, quality_flag, data_source, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.timestamp,
                    r.channel_id,
                    r.position_m,
                    r.temperature_c,
                    r.quality_flag,
                    r.data_source,
                    content_hash,
                ))
            conn.commit()
    
    def log_alert(self, alert: TemperatureAlert) -> None:
        """Log a single alert."""
        content = f"{alert.alert_id}|{alert.alert_type}|{alert.severity}|{alert.current_value}|{alert.timestamp}"
        content_hash = self._compute_hash(content)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO alerts
                (alert_id, timestamp, alert_type, severity, channel_id, current_value, 
                 threshold_value, message, recommended_action, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id,
                alert.timestamp,
                alert.alert_type,
                alert.severity,
                alert.channel_id,
                alert.current_value,
                alert.threshold_value,
                alert.message,
                alert.recommended_action,
                content_hash,
            ))
            conn.commit()
    
    def log_alerts(self, alerts: list[TemperatureAlert]) -> None:
        """Log multiple alerts."""
        for alert in alerts:
            self.log_alert(alert)
    
    def acknowledge_alert(self, alert_id: str, ack_by: str) -> bool:
        """Acknowledge an alert.
        
        Args:
            alert_id: The alert to acknowledge
            ack_by: Who acknowledged (operator ID or name)
            
        Returns:
            True if acknowledged, False if alert not found
        """
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                "UPDATE alerts SET acknowledged = 1, ack_by = ?, ack_timestamp = ? WHERE alert_id = ?",
                (ack_by, datetime.now().isoformat(), alert_id)
            )
            conn.commit()
            return result.rowcount > 0
    
    def log_event(self, event_type: str, description: str, details: dict[str, Any] | None = None) -> None:
        """Log a system event."""
        timestamp = datetime.now().isoformat()
        details_json = json.dumps(details or {}, ensure_ascii=False)
        content = f"{event_type}|{description}|{timestamp}"
        content_hash = self._compute_hash(content)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO events (timestamp, event_type, description, details, content_hash)
                VALUES (?, ?, ?, ?, ?)
            """, (timestamp, event_type, description, details_json, content_hash))
            conn.commit()
    
    def get_recent_alerts(self, limit: int = 100, unacknowledged_only: bool = False) -> list[dict]:
        """Get recent alerts."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = "SELECT * FROM alerts"
            if unacknowledged_only:
                query += " WHERE acknowledged = 0"
            query += " ORDER BY timestamp DESC LIMIT ?"
            
            rows = conn.execute(query, (limit,)).fetchall()
            return [dict(row) for row in rows]
    
    def get_statistics(self) -> dict[str, Any]:
        """Get audit log statistics."""
        with sqlite3.connect(self.db_path) as conn:
            readings_count = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
            alerts_count = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            unacked_count = conn.execute("SELECT COUNT(*) FROM alerts WHERE acknowledged = 0").fetchone()[0]
            events_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            
            alerts_by_severity = dict(conn.execute(
                "SELECT severity, COUNT(*) FROM alerts GROUP BY severity"
            ).fetchall())
            
            return {
                "total_readings_logged": readings_count,
                "total_alerts": alerts_count,
                "unacknowledged_alerts": unacked_count,
                "total_events": events_count,
                "alerts_by_severity": alerts_by_severity,
                "database_path": str(self.db_path),
            }
    
    def export_audit_trail(self, output_path: str | Path, start_time: str | None = None) -> None:
        """Export audit trail to JSON file.
        
        Args:
            output_path: Path to output file
            start_time: Optional start time filter (ISO format)
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get readings
            query = "SELECT * FROM readings"
            if start_time:
                query += f" WHERE timestamp >= '{start_time}'"
            query += " ORDER BY timestamp"
            readings = [dict(row) for row in conn.execute(query).fetchall()]
            
            # Get alerts
            query = "SELECT * FROM alerts"
            if start_time:
                query += f" WHERE timestamp >= '{start_time}'"
            query += " ORDER BY timestamp"
            alerts = [dict(row) for row in conn.execute(query).fetchall()]
            
            # Get events
            query = "SELECT * FROM events"
            if start_time:
                query += f" WHERE timestamp >= '{start_time}'"
            query += " ORDER BY timestamp"
            events = [dict(row) for row in conn.execute(query).fetchall()]
        
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "start_time_filter": start_time,
            "statistics": self.get_statistics(),
            "readings_sample": readings[:1000],  # Limit for file size
            "readings_total": len(readings),
            "alerts": alerts,
            "events": events,
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
