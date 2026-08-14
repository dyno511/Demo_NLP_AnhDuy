from abc import ABC, abstractmethod
from typing import List, Dict, Any
from urllib.parse import urlparse


class PlatformDiscoveryStrategy(ABC):
    platform: str
    display_name: str

    @abstractmethod
    def build_queries(self, target: str, aliases: List[str]) -> List[str]:
        """Generate platform-specific queries."""
        pass

    @abstractmethod
    def is_platform_url(self, url: str) -> bool:
        """Check if URL belongs to this platform."""
        pass

    @abstractmethod
    def extract_source_type(self, url: str) -> str:
        """Extract source type (e.g., page, group, channel, profile, post)."""
        pass

    def normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        parsed = urlparse(url)
        netloc = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.rstrip("/") or "/"
        return f"https://{netloc}{path}"


class FacebookStrategy(PlatformDiscoveryStrategy):
    platform = "facebook"
    display_name = "Facebook"

    def build_queries(self, target: str, aliases: List[str]) -> List[str]:
        terms = [target] + list(aliases or [])
        clean_terms = list(dict.fromkeys([t.strip() for t in terms if t and t.strip()]))
        return [f'site:facebook.com "{term}"' for term in clean_terms]

    def is_platform_url(self, url: str) -> bool:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        return host == "facebook.com" or host.endswith(".facebook.com")

    def extract_source_type(self, url: str) -> str:
        path = urlparse(url).path.lower()
        if "/groups/" in path:
            return "group"
        return "page"


class TikTokStrategy(PlatformDiscoveryStrategy):
    platform = "tiktok"
    display_name = "TikTok"

    def build_queries(self, target: str, aliases: List[str]) -> List[str]:
        terms = [target] + list(aliases or [])
        clean_terms = list(dict.fromkeys([t.strip() for t in terms if t and t.strip()]))
        return [f'site:tiktok.com "{term}"' for term in clean_terms]

    def is_platform_url(self, url: str) -> bool:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        return host == "tiktok.com" or host.endswith(".tiktok.com")

    def extract_source_type(self, url: str) -> str:
        path = urlparse(url).path.lower()
        if path.startswith("/@"):
            return "profile"
        return "video"


class YouTubeStrategy(PlatformDiscoveryStrategy):
    platform = "youtube"
    display_name = "YouTube"

    def build_queries(self, target: str, aliases: List[str]) -> List[str]:
        terms = [target] + list(aliases or [])
        clean_terms = list(dict.fromkeys([t.strip() for t in terms if t and t.strip()]))
        return [f'site:youtube.com "{term}"' for term in clean_terms]

    def is_platform_url(self, url: str) -> bool:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        return host in {"youtube.com", "youtu.be"} or host.endswith(".youtube.com")

    def extract_source_type(self, url: str) -> str:
        path = urlparse(url).path.lower()
        if "/channel/" in path or "/c/" in path or path.startswith("/@"):
            return "channel"
        return "video"


class InstagramStrategy(PlatformDiscoveryStrategy):
    platform = "instagram"
    display_name = "Instagram"

    def build_queries(self, target: str, aliases: List[str]) -> List[str]:
        terms = [target] + list(aliases or [])
        clean_terms = list(dict.fromkeys([t.strip() for t in terms if t and t.strip()]))
        return [f'site:instagram.com "{term}"' for term in clean_terms]

    def is_platform_url(self, url: str) -> bool:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        return host == "instagram.com" or host.endswith(".instagram.com")

    def extract_source_type(self, url: str) -> str:
        path = urlparse(url).path.lower()
        if "/p/" in path or "/reel/" in path:
            return "post"
        return "profile"


class RedditStrategy(PlatformDiscoveryStrategy):
    platform = "reddit"
    display_name = "Reddit"

    def build_queries(self, target: str, aliases: List[str]) -> List[str]:
        terms = [target] + list(aliases or [])
        clean_terms = list(dict.fromkeys([t.strip() for t in terms if t and t.strip()]))
        return [f'site:reddit.com "{term}"' for term in clean_terms]

    def is_platform_url(self, url: str) -> bool:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        return host == "reddit.com" or host.endswith(".reddit.com")

    def extract_source_type(self, url: str) -> str:
        path = urlparse(url).path.lower()
        if "/r/" in path:
            return "subreddit"
        return "post"


class ForumStrategy(PlatformDiscoveryStrategy):
    platform = "forum"
    display_name = "Forum"

    def build_queries(self, target: str, aliases: List[str]) -> List[str]:
        terms = [target] + list(aliases or [])
        clean_terms = list(dict.fromkeys([t.strip() for t in terms if t and t.strip()]))
        return [f'"{term}" diễn đàn OR forum' for term in clean_terms]

    def is_platform_url(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        path = urlparse(url).path.lower()
        return "forum" in host or "diendan" in host or "thread" in path or "topic" in path

    def extract_source_type(self, url: str) -> str:
        return "forum_thread"


class NewsStrategy(PlatformDiscoveryStrategy):
    platform = "news"
    display_name = "News"

    def build_queries(self, target: str, aliases: List[str]) -> List[str]:
        terms = [target] + list(aliases or [])
        clean_terms = list(dict.fromkeys([t.strip() for t in terms if t and t.strip()]))
        return [f'"{term}" tin tức site:vnexpress.net OR site:tuoitre.vn OR site:thanhnien.vn OR site:dantri.com.vn' for term in clean_terms]

    def is_platform_url(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        news_domains = {"vnexpress.net", "tuoitre.vn", "thanhnien.vn", "dantri.com.vn", "laodong.vn", "vietnamnet.vn"}
        return any(domain in host for domain in news_domains)

    def extract_source_type(self, url: str) -> str:
        return "news_article"


class PublicWebStrategy(PlatformDiscoveryStrategy):
    platform = "public_web"
    display_name = "Public Web"

    def build_queries(self, target: str, aliases: List[str]) -> List[str]:
        terms = [target] + list(aliases or [])
        clean_terms = list(dict.fromkeys([t.strip() for t in terms if t and t.strip()]))
        return [f'"{term}"' for term in clean_terms]

    def is_platform_url(self, url: str) -> bool:
        return bool(url and url.startswith("http"))

    def extract_source_type(self, url: str) -> str:
        return "web_page"


def get_all_platform_strategies() -> List[PlatformDiscoveryStrategy]:
    return [
        FacebookStrategy(),
        TikTokStrategy(),
        YouTubeStrategy(),
        InstagramStrategy(),
        RedditStrategy(),
        ForumStrategy(),
        NewsStrategy(),
        PublicWebStrategy()
    ]
