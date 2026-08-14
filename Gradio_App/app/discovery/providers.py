import json
import logging
from abc import ABC, abstractmethod
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, urlopen
from typing import List, Dict, Tuple, Any

logger = logging.getLogger(__name__)


class ProviderUnavailableError(RuntimeError):
    """Raised when a provider cannot supply usable search results."""


class SearchProvider(ABC):
    name: str
    tier_level: int  # 1 to 5

    @abstractmethod
    def search(self, query: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Return normalized results: title, url, snippet, provider, rank, tier."""


# ---------------------------------------------------------
# TẦNG 1: Direct HTML Web Provider
# ---------------------------------------------------------
class DirectHtmlProvider(SearchProvider):
    """Tier 1: Direct HTML meta tag & OpenGraph metadata scraping."""
    name = "direct_html"
    tier_level = 1

    def __init__(self, timeout: int = 5):
        self.timeout = timeout

    def search(self, query: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        # Converts queries into target site URLs if query resembles a domain/site
        terms = [t.strip('"') for t in query.split() if not t.startswith("site:")]
        clean_target = " ".join(terms).strip()
        if not clean_target:
            raise ProviderUnavailableError("DirectHtmlProvider requires valid search term")

        results = []
        target_urls = [
            f"https://www.{clean_target.lower().replace(' ', '')}.edu.vn",
            f"https://{clean_target.lower().replace(' ', '')}.com",
            f"https://facebook.com/{clean_target.lower().replace(' ', '')}"
        ]

        for url in target_urls:
            try:
                request = Request(url, headers={"User-Agent": "SocialListeningBot/1.0"})
                with urlopen(request, timeout=self.timeout) as response:
                    if response.status == 200:
                        html = response.read().decode("utf-8", errors="replace")
                        title = self._extract_title(html) or clean_target
                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": f"Trang chính thức / trực tiếp thu thập từ {url}",
                            "provider": self.name,
                            "tier": self.tier_level,
                            "rank": len(results) + 1
                        })
            except Exception:
                continue

        if not results:
            raise ProviderUnavailableError("Direct HTML fetching failed for query target")
        return results, {"http_status": 200, "tier": 1}

    @staticmethod
    def _extract_title(html: str) -> str:
        start = html.find("<title>")
        end = html.find("</title>")
        if start != -1 and end != -1:
            return html[start + 7:end].strip()
        return ""


# ---------------------------------------------------------
# TẦNG 2: Public Sitemap / RSS / Atom Discovery Provider
# ---------------------------------------------------------
class SitemapRssProvider(SearchProvider):
    """Tier 2: Discovery via public RSS feeds, Atom, and sitemaps."""
    name = "sitemap_rss"
    tier_level = 2

    def __init__(self, timeout: int = 5):
        self.timeout = timeout

    def search(self, query: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        terms = [t.strip('"') for t in query.split() if not t.startswith("site:")]
        clean_target = " ".join(terms).strip()
        if not clean_target:
            raise ProviderUnavailableError("SitemapRssProvider requires valid search term")

        results = []
        feed_urls = [
            f"https://{clean_target.lower().replace(' ', '')}.edu.vn/feed",
            f"https://{clean_target.lower().replace(' ', '')}.vn/rss",
            f"https://news.google.com/rss/search?q={urlencode({'q': clean_target})}&hl=vi&gl=VN&ceid=VN:vi"
        ]

        for url in feed_urls:
            try:
                request = Request(url, headers={"User-Agent": "SocialListeningBot/1.0"})
                with urlopen(request, timeout=self.timeout) as response:
                    if response.status == 200:
                        results.append({
                            "title": f"Nguồn RSS/Feed tin tức - {clean_target}",
                            "url": url,
                            "snippet": f"Kênh tin tức & RSS tự động cho {clean_target}",
                            "provider": self.name,
                            "tier": self.tier_level,
                            "rank": len(results) + 1
                        })
            except Exception:
                continue

        if not results:
            raise ProviderUnavailableError("Sitemap/RSS discovery returned no feeds")
        return results, {"http_status": 200, "tier": 2}


# ---------------------------------------------------------
# TẦNG 3: Common Crawl / Internet Archive Provider
# ---------------------------------------------------------
class ArchiveIndexProvider(SearchProvider):
    """Tier 3: Discovery via Internet Archive / Wayback CDX API."""
    name = "archive_index"
    tier_level = 3

    def __init__(self, timeout: int = 5):
        self.timeout = timeout

    def search(self, query: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        terms = [t.strip('"') for t in query.split() if not t.startswith("site:")]
        domain_term = "".join(terms).lower().replace(" ", "")
        if not domain_term:
            raise ProviderUnavailableError("ArchiveIndexProvider requires domain keyword")

        archive_url = f"http://web.archive.org/cdx/search/cdx?url=*{domain_term}*&output=json&limit=5"
        try:
            request = Request(archive_url, headers={"User-Agent": "SocialListeningBot/1.0"})
            with urlopen(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise ProviderUnavailableError(f"Archive CDX returned HTTP {response.status}")
                data = json.loads(response.read().decode("utf-8"))
                results = []
                if len(data) > 1:  # First item is header
                    for rank, row in enumerate(data[1:], 1):
                        original_url = row[2]
                        results.append({
                            "title": f"Chỉ mục lưu trữ Internet Archive - {original_url}",
                            "url": original_url,
                            "snippet": f"Bản lưu công khai từ Internet Archive Wayback Machine",
                            "provider": self.name,
                            "tier": self.tier_level,
                            "rank": rank
                        })
                if results:
                    return results, {"http_status": 200, "tier": 3}
        except Exception as exc:
            raise ProviderUnavailableError(f"Archive index search failed: {exc}")

        raise ProviderUnavailableError("Internet Archive CDX returned no records")


# ---------------------------------------------------------
# TẦNG 4: Search-Engine Indexed Content Provider
# ---------------------------------------------------------
class _DuckDuckGoResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._current = None
        self._capture = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        classes = values.get("class", "")
        if tag == "a" and "result__a" in classes and values.get("href"):
            self._current = {"href": values["href"], "title": "", "snippet": ""}
            self._capture = "title"
        elif self._current and "result__snippet" in classes:
            self._capture = "snippet"

    def handle_data(self, data):
        if self._current and self._capture:
            self._current[self._capture] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._current and self._capture == "title":
            self.results.append({key: value.strip() for key, value in self._current.items()})
            self._current = None
            self._capture = None
        elif tag in {"a", "div", "span"} and self._capture == "snippet":
            self._capture = None


class DuckDuckGoHtmlProvider(SearchProvider):
    """Tier 4: Public Search Engine Index provider."""
    name = "search_engine_index"
    tier_level = 4
    endpoint = "https://html.duckduckgo.com/html/"

    def __init__(self, timeout: int = 10, max_retries: int = 1):
        self.timeout = timeout
        self.max_retries = max_retries

    def search(self, query: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                data = urlencode({'q': query}).encode('utf-8')
                request = Request(
                    self.endpoint,
                    data=data,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                        "Content-Type": "application/x-www-form-urlencoded"
                    }
                )
                with urlopen(request, timeout=self.timeout) as response:
                    body = response.read().decode("utf-8", errors="replace")
                    if response.status != 200 or "anomaly-modal" in body or "challenge-submit" in body:
                        raise ProviderUnavailableError(f"Search Engine index returned unusable HTTP {response.status}")
                    parser = _DuckDuckGoResultParser()
                    parser.feed(body)
                    return self._normalize(parser.results), {"http_status": response.status, "retry": attempt, "tier": 4}
            except Exception as exc:
                last_error = exc
        raise ProviderUnavailableError(f"Search Engine Index provider unavailable: {last_error}")

    def _normalize(self, raw_results):
        normalized = []
        for rank, item in enumerate(raw_results, 1):
            href = unquote(item["href"])
            destination = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
            normalized.append({
                "title": item["title"],
                "url": destination,
                "snippet": item["snippet"],
                "provider": self.name,
                "tier": self.tier_level,
                "rank": rank
            })
        return normalized


# ---------------------------------------------------------
# TẦNG 5: Simulated Mock Data Fallback Provider
# ---------------------------------------------------------
class MockDiscoveryProvider(SearchProvider):
    """Tier 5: Fallback Mock Data Provider for offline/unreachable environments."""
    name = "mock_fallback"
    tier_level = 5

    def search(self, query: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        terms = [t.strip('"') for t in query.split() if not t.startswith("site:")]
        target = " ".join(terms).strip() or "Đại học Nam Cần Thơ"
        clean_id = target.lower().replace(" ", "_")

        mock_results = [
            {
                "title": f"Fanpage Công Khai {target}",
                "url": f"https://www.facebook.com/{clean_id}_official",
                "snippet": f"Trang thông tin chính thức công khai của {target}.",
                "provider": self.name,
                "tier": 5,
                "rank": 1
            },
            {
                "title": f"Diễn Đàn Sinh Viên {target}",
                "url": f"https://www.facebook.com/groups/{clean_id}_forum",
                "snippet": f"Cộng đồng thảo luận và chia sẻ thông tin sinh viên {target}.",
                "provider": self.name,
                "tier": 5,
                "rank": 2
            },
            {
                "title": f"Kênh TikTok {target}",
                "url": f"https://www.tiktok.com/@{clean_id}_news",
                "snippet": f"Kênh tin tức video ngắn của {target}.",
                "provider": self.name,
                "tier": 5,
                "rank": 3
            },
            {
                "title": f"Kênh YouTube {target}",
                "url": f"https://www.youtube.com/@{clean_id}_channel",
                "snippet": f"Kênh truyền thông video chính thức của {target}.",
                "provider": self.name,
                "tier": 5,
                "rank": 4
            }
        ]

        return mock_results, {"http_status": 200, "tier": 5}
