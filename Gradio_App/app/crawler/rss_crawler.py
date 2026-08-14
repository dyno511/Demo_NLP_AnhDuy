from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from typing import Any, Dict, List
from urllib.parse import urlparse

from app.crawler.base import BaseCrawler
from app.utils.logger import logger


class RSSCrawler(BaseCrawler):
    """Collect public RSS/Atom entries; never fabricates comments or fallback data."""

    def fetch_data(self, target_pages: List[str], max_items: int = 10) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for feed_url in target_pages:
            try:
                request = Request(feed_url, headers={"User-Agent": "SocialListeningRSS/1.0"})
                with urlopen(request, timeout=20) as response:
                    root = ElementTree.fromstring(response.read())
                entries = root.findall(".//item") or root.findall(".//{*}entry")
                for node in entries[:max_items]:
                    values = {child.tag.rsplit("}", 1)[-1]: (child.text or "").strip()
                              for child in node}
                    links = [child.attrib.get("href", "") for child in node
                             if child.tag.rsplit("}", 1)[-1] == "link"]
                    url = values.get("link") or next((x for x in links if x), "")
                    entry_id = values.get("guid") or values.get("id") or url
                    if not entry_id or not url:
                        logger.warning(f"[RSSCrawler] Skipping entry without stable ID/URL: {feed_url}")
                        continue
                    text = values.get("description") or values.get("summary") or values.get("title") or ""
                    items.append({
                        "source": "rss",
                        "post_id": entry_id,
                        "comment_id": None,
                        "post_url": url,
                        "text": text,
                        "author": values.get("author") or values.get("creator") or urlparse(feed_url).netloc,
                        "created_at": self._created_at(values),
                        "content_type": "post",
                    })
            except Exception as exc:
                logger.error(f"[RSSCrawler] Failed to read {feed_url}: {exc}")
        logger.info(f"[RSSCrawler] Collected {len(items)} public feed entries from {len(target_pages)} feed(s).")
        return items

    @staticmethod
    def _created_at(entry: Any) -> str:
        raw = entry.get("pubDate") or entry.get("published") or entry.get("updated")
        if raw:
            try:
                return parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError, OverflowError):
                pass
        return ""
