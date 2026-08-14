import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import Config
from app.utils.logger import logger

class Repository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or Config.DB_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database schema tables if not existing."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Table for Crawled & Processed Items (Deduplication store)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_items (
                    item_id TEXT PRIMARY KEY,
                    source TEXT,
                    post_id TEXT,
                    comment_id TEXT,
                    post_url TEXT,
                    author TEXT,
                    text TEXT,
                    content_type TEXT,
                    created_at TEXT,
                    org_detected INTEGER,
                    detected_org_name TEXT,
                    sentiment_label TEXT,
                    confidence REAL,
                    alert_sent INTEGER,
                    processed_at TEXT
                )
            """)

            # Table for Alert Dispatch Logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alert_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT,
                    channel TEXT,
                    target_org TEXT,
                    sentiment_label TEXT,
                    confidence REAL,
                    message_text TEXT,
                    status TEXT,
                    sent_at TEXT,
                    FOREIGN KEY (item_id) REFERENCES processed_items (item_id)
                )
            """)

            # Table for Scan Cycle Summaries
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scan_cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_time TEXT,
                    total_scanned INTEGER,
                    org_mentions INTEGER,
                    negative_count INTEGER,
                    alerts_triggered INTEGER,
                    duration_seconds REAL
                )
            """)
            cursor.execute("""CREATE TABLE IF NOT EXISTS discovered_sources (
                source_key TEXT PRIMARY KEY, target_organization TEXT, platform TEXT,
                source_type TEXT, name TEXT, url TEXT, username_or_id TEXT, description TEXT,
                discovery_source TEXT, matched_queries TEXT, relevance_score REAL,
                status TEXT, accessibility TEXT, failure_reason TEXT,
                last_verified_at TEXT, last_discovered_at TEXT)""")
            conn.commit()

    @staticmethod
    def generate_item_id(post_id: str, comment_id: Optional[str] = None, text: str = "") -> str:
        """Generate unique hash identifier for deduplication."""
        raw_key = f"{post_id}::{comment_id or 'POST'}::{text[:50]}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def is_item_processed(self, item_id: str) -> bool:
        """Check if item has already been crawled and processed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM processed_items WHERE item_id = ?", (item_id,))
            return cursor.fetchone() is not None

    def save_processed_item(self, item_data: Dict[str, Any], ai_result: Dict[str, Any], alert_sent: bool) -> str:
        """Store processed item record in SQLite repository."""
        item_id = item_data.get("item_id") or self.generate_item_id(
            item_data.get("post_id", ""),
            item_data.get("comment_id"),
            item_data.get("text", "")
        )
        
        processed_at = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO processed_items (
                    item_id, source, post_id, comment_id, post_url, author, text,
                    content_type, created_at, org_detected, detected_org_name,
                    sentiment_label, confidence, alert_sent, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_id,
                item_data.get("source", "unknown"),
                item_data.get("post_id", ""),
                item_data.get("comment_id", ""),
                item_data.get("post_url", ""),
                item_data.get("author", "Anonymous"),
                item_data.get("text", ""),
                item_data.get("content_type", "post"),
                item_data.get("created_at", datetime.now().isoformat()),
                1 if ai_result.get("org_detected") else 0,
                ai_result.get("matched_org", ""),
                ai_result.get("label", "NEUTRAL"),
                float(ai_result.get("confidence", 0.0)),
                1 if alert_sent else 0,
                processed_at
            ))
            conn.commit()
        return item_id

    def log_alert(self, item_id: str, channel: str, target_org: str, sentiment: str, confidence: float, message_text: str, status: str):
        """Log an alert dispatch attempt."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO alert_logs (
                    item_id, channel, target_org, sentiment_label, confidence, message_text, status, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_id, channel, target_org, sentiment, confidence, message_text, status, datetime.now().isoformat()
            ))
            conn.commit()

    def record_scan_cycle(self, total: int, mentions: int, negative: int, alerts: int, duration: float):
        """Record scan cycle analytics summary."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scan_cycles (cycle_time, total_scanned, org_mentions, negative_count, alerts_triggered, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (datetime.now().isoformat(), total, mentions, negative, alerts, duration))
            conn.commit()

    def get_system_stats(self) -> Dict[str, Any]:
        """Fetch summary metrics for dashboard visualization."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM processed_items")
            total_items = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM processed_items WHERE org_detected = 1")
            total_org_mentions = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM processed_items WHERE sentiment_label = 'NEGATIVE'")
            total_negative = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM processed_items WHERE alert_sent = 1")
            total_alerts = cursor.fetchone()[0]

            cursor.execute("SELECT cycle_time FROM scan_cycles ORDER BY id DESC LIMIT 1")
            last_scan_row = cursor.fetchone()
            last_scan = last_scan_row[0] if last_scan_row else "Chưa quét"

            return {
                "total_items": total_items,
                "org_mentions": total_org_mentions,
                "negative_items": total_negative,
                "alerts_sent": total_alerts,
                "last_scan": last_scan
            }

    def get_recent_items(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent processed items for UI viewing."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM processed_items ORDER BY processed_at DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent alerts sent."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.*, p.post_url, p.author, p.text FROM alert_logs a
                LEFT JOIN processed_items p ON a.item_id = p.item_id
                ORDER BY a.id DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
