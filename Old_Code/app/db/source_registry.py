import json
from datetime import datetime


class SourceRegistry:
    def __init__(self, repository):
        self.repository = repository

    def _conn(self):
        return self.repository._get_connection()

    def init(self):
        with self._conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS discovered_sources (
                source_key TEXT PRIMARY KEY,
                target_organization TEXT,
                platform TEXT,
                source_type TEXT,
                name TEXT,
                url TEXT,
                username_or_id TEXT,
                description TEXT,
                discovery_source TEXT,
                matched_queries TEXT,
                relevance_score REAL,
                status TEXT,
                accessibility TEXT,
                failure_reason TEXT,
                last_verified_at TEXT,
                last_discovered_at TEXT
            )""")
            conn.commit()

    def save_sources(self, sources, target, limit):
        self.init()
        with self._conn() as conn:
            for item in sources:
                conn.execute("""INSERT OR REPLACE INTO discovered_sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    item.get("source_key") or item.get("source_id"),
                    target,
                    item.get("platform", "public_web"),
                    item.get("source_type", "page"),
                    item.get("source_name") or item.get("name"),
                    item.get("url"),
                    item.get("username_or_id"),
                    item.get("snippet") or item.get("description"),
                    item.get("discovery_method") or item.get("discovery_source"),
                    json.dumps(item.get("matched_queries", [])),
                    item.get("relevance_score", 0.0),
                    item.get("status", "DISCOVERED"),
                    item.get("accessibility", "UNKNOWN"),
                    item.get("failure_reason"),
                    item.get("last_verified_at"),
                    item.get("discovered_at") or datetime.utcnow().isoformat()
                ))
            conn.commit()

    def list_sources(self, target=None):
        self.init()
        with self._conn() as conn:
            query, args = "SELECT * FROM discovered_sources", []
            if target:
                query += " WHERE target_organization = ?"
                args.append(target)
            query += " ORDER BY relevance_score DESC"
            return [dict(row) for row in conn.execute(query, args)]

    def crawlable_urls(self, target=None):
        return [x["url"] for x in self.list_sources(target) if x["status"] == "CRAWLABLE"]

    def crawlable_sources(self, target=None):
        return [source for source in self.list_sources(target) if source["status"] == "CRAWLABLE"]

    def update_status(self, source_key, status, failure_reason=None):
        self.init()
        with self._conn() as conn:
            conn.execute(
                "UPDATE discovered_sources SET status = ?, failure_reason = ?, last_verified_at = ? WHERE source_key = ?",
                (status, failure_reason, datetime.utcnow().isoformat(), source_key)
            )
            conn.commit()
