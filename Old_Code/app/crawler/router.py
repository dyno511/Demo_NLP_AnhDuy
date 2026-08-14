from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse


class CrawlAdapter(ABC):
    """Adapter for one public-source platform; never fabricates source data."""

    platform: str

    @abstractmethod
    def supports(self, source: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def crawl(self, source: Dict[str, Any], max_items: int) -> List[Dict[str, Any]]:
        pass


class FacebookPageAdapter(CrawlAdapter):
    platform = "facebook"

    def supports(self, source):
        return source.get("platform", "").lower() == "facebook" and source.get("source_type", "").lower() in {"page", "facebook_page"}

    def crawl(self, source, max_items):
        from app.crawler.facebook_crawler import FacebookCrawler
        path = urlparse(source.get("url", "")).path.strip("/")
        page_name = source.get("username_or_id") or path.split("/")[0]
        if not page_name:
            raise ValueError("Facebook source has no username_or_id or usable URL path")
        return FacebookCrawler().fetch_data([page_name], max_items=max_items)


class RSSFeedAdapter(CrawlAdapter):
    platform = "rss"

    def supports(self, source):
        return source.get("platform", "").lower() == "rss" or source.get("source_type", "").lower() == "rss_feed"

    def crawl(self, source, max_items):
        from app.crawler.rss_crawler import RSSCrawler
        url = source.get("url", "")
        if not url:
            raise ValueError("RSS source has no feed URL")
        return RSSCrawler().fetch_data([url], max_items=max_items)


class CrawlRouter:
    """Routes selected monitoring sources only to supported, public crawler adapters."""

    def __init__(self, adapters=None):
        self.adapters = adapters if adapters is not None else [FacebookPageAdapter(), RSSFeedAdapter()]

    def crawl_sources(self, sources: List[Dict[str, Any]], max_items: int = 15) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        items, updates = [], []
        summary = {"sources_considered": len(sources), "sources_crawled": 0, "unsupported_sources": 0,
                   "errors": 0, "items_collected": 0, "updates": updates}
        for source in sources:
            adapter = next((candidate for candidate in self.adapters if candidate.supports(source)), None)
            if adapter is None:
                summary["unsupported_sources"] += 1
                updates.append({"source_key": source["source_key"], "status": "CRAWLER_UNSUPPORTED",
                                "reason": f"No public crawler adapter for platform={source.get('platform')} type={source.get('source_type')}"})
                continue
            try:
                source_items = adapter.crawl(source, max_items)
                items.extend(source_items)
                summary["sources_crawled"] += 1
                updates.append({"source_key": source["source_key"], "status": "CRAWLABLE", "reason": None})
            except Exception as exc:
                summary["errors"] += 1
                updates.append({"source_key": source["source_key"], "status": "FAILED",
                                "reason": f"{type(exc).__name__}: {exc}"})
        summary["items_collected"] = len(items)
        return items, summary
