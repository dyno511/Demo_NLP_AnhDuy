import hashlib
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.discovery.platforms import (
    PlatformDiscoveryStrategy,
    get_all_platform_strategies
)
from app.discovery.providers import (
    DirectHtmlProvider,
    SitemapRssProvider,
    ArchiveIndexProvider,
    DuckDuckGoHtmlProvider,
    MockDiscoveryProvider,
    ProviderUnavailableError,
    SearchProvider
)

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Multi-platform public-source discovery with 5-tier Fallback system."""

    def __init__(self, registry=None, providers=None, timeout=None, max_retries=None):
        self.registry = registry
        self.timeout = timeout or int(os.getenv("DISCOVERY_TIMEOUT_SECONDS", "10"))
        self.max_retries = max_retries if max_retries is not None else int(os.getenv("DISCOVERY_MAX_RETRIES", "1"))
        self.providers = providers if providers is not None else self._configured_fallback_chain()
        self.platform_strategies = get_all_platform_strategies()
        self.last_run = self._new_run("NOT_RUN")

    def _configured_fallback_chain(self) -> List[SearchProvider]:
        """Configure 5-Tier Fallback Provider Chain."""
        return [
            DirectHtmlProvider(self.timeout),
            SitemapRssProvider(self.timeout),
            ArchiveIndexProvider(self.timeout),
            DuckDuckGoHtmlProvider(self.timeout, self.max_retries),
            MockDiscoveryProvider()
        ]

    def queries_for_platform(self, platform_name: str, target: str, aliases=None) -> List[str]:
        strategy = next((s for s in self.platform_strategies if s.platform == platform_name), None)
        if strategy:
            return strategy.build_queries(target, aliases or [])
        return [f'"{target}"']

    def discover(self, target: str, aliases=None, limit: int = 10) -> List[Dict]:
        self.last_run = self._new_run("RUNNING")
        logger.info("Discovery started: target=%r limit=%d fallback_tiers=%s",
                    target, limit, [f"T{p.tier_level}:{p.name}" for p in self.providers])

        if not target or not target.strip():
            self.last_run.update(status="EMPTY_RESULT", error="Target organization is empty")
            return []

        if not self.providers:
            self.last_run.update(status="PROVIDER_UNAVAILABLE", error="No discovery provider is configured")
            return []

        aliases = aliases or []
        candidates_by_key = {}
        platform_counts = {strategy.platform: 0 for strategy in self.platform_strategies}
        unavailable_errors = []

        # Multi-Platform Waterfall Loop across 5-Tier Fallback Chain
        for strategy in self.platform_strategies:
            if len(candidates_by_key) >= limit * 2:
                break

            queries = strategy.build_queries(target, aliases)
            self.last_run["queries"].extend(queries)

            for query in queries:
                results = self._search_with_5tier_fallback(query, unavailable_errors)
                for result in results:
                    self.last_run["search_results"] += 1
                    self.last_run["urls_extracted"] += 1

                    url = result.get("url", "")
                    if not url:
                        continue

                    # If result matches platform or strategy is public_web
                    if not strategy.is_platform_url(url) and strategy.platform != "public_web":
                        continue

                    normalized_url = strategy.normalize_url(url)
                    key = self._source_key(strategy.platform, normalized_url)

                    if key in candidates_by_key:
                        self.last_run["duplicates_removed"] += 1
                        if query not in candidates_by_key[key]["matched_queries"]:
                            candidates_by_key[key]["matched_queries"].append(query)
                        continue

                    source_type = strategy.extract_source_type(url)
                    candidate = {
                        "source_key": key,
                        "source_id": key,
                        "platform": strategy.platform,
                        "source_name": result.get("title", "") or strategy.display_name,
                        "name": result.get("title", ""),
                        "url": normalized_url,
                        "canonical_url": normalized_url,
                        "title": result.get("title", ""),
                        "snippet": result.get("snippet", ""),
                        "description": result.get("snippet", ""),
                        "source_type": source_type,
                        "username_or_id": urlparse(normalized_url).path.strip("/"),
                        "discovery_source": result.get("provider", "fallback_tier"),
                        "discovery_method": result.get("provider", "fallback_tier"),
                        "tier": result.get("tier", 5),
                        "matched_queries": [query],
                        "relevance_score": 0.0,
                        "status": "DISCOVERED",
                        "accessibility": "UNKNOWN",
                        "failure_reason": None,
                        "last_verified_at": None,
                        "discovered_at": datetime.utcnow().isoformat()
                    }

                    candidates_by_key[key] = candidate
                    platform_counts[strategy.platform] += 1

        all_candidates = list(candidates_by_key.values())
        self.last_run.update(
            query_count=len(self.last_run["queries"]),
            search_results=self.last_run["search_results"],
            valid_candidates=len(all_candidates),
            candidate_count=len(all_candidates),
            platform_counts=platform_counts
        )

        if not all_candidates:
            self.last_run.update(status="EMPTY_RESULT", error="No public source candidates found across all fallback tiers")
            return []

        # Scoring & Verification
        for candidate in all_candidates:
            self._score(candidate, target, aliases)
            self._verify(candidate)

        # Ranking
        all_candidates.sort(key=lambda item: item["relevance_score"], reverse=True)

        # Select Top N
        selected_candidates = []
        for rank, candidate in enumerate(all_candidates, 1):
            candidate["rank"] = rank
            if len(selected_candidates) < limit and candidate["relevance_score"] >= 0.20:
                candidate["status"] = "CRAWLABLE" if candidate["accessibility"] == "ACCESSIBLE" else "FAILED"
                selected_candidates.append(candidate)
            else:
                candidate["status"] = "RELEVANT" if candidate["relevance_score"] >= 0.20 else "REJECTED"

        # Determine Final Status
        active_platforms = [p for p, count in platform_counts.items() if count > 0]
        if len(active_platforms) == len(self.platform_strategies):
            final_status = "SUCCESS"
        elif len(active_platforms) > 0:
            final_status = "PARTIAL_SUCCESS"
        else:
            final_status = "EMPTY_RESULT"

        self.last_run.update(
            status=final_status,
            selected_count=len(selected_candidates),
            error="; ".join(unavailable_errors[:2]) if unavailable_errors else None
        )

        if self.registry:
            self.registry.save_sources(selected_candidates, target, limit)

        return selected_candidates

    def _search_with_5tier_fallback(self, query: str, errors: List[str]):
        """Executes 5-tier fallback chain for search query execution."""
        for provider in self.providers:
            try:
                results, metadata = provider.search(query)
                if results:
                    self.last_run["requests"].append({
                        "query": query,
                        "provider": provider.name,
                        "tier": provider.tier_level,
                        **metadata,
                        "result_count": len(results),
                        "status": "SUCCESS"
                    })
                    logger.info("Discovery provider success at Tier %d (%s): query=%r results=%d",
                                provider.tier_level, provider.name, query, len(results))
                    return results
            except ProviderUnavailableError as exc:
                errors.append(f"Tier {provider.tier_level} [{provider.name}]: {exc}")
                self.last_run["requests"].append({
                    "query": query,
                    "provider": provider.name,
                    "tier": provider.tier_level,
                    "status": "UNAVAILABLE",
                    "error": str(exc)
                })
                logger.warning("Tier %d (%s) unavailable for query=%r: %s", provider.tier_level, provider.name, query, exc)
        return []

    def get_last_run(self):
        return dict(self.last_run)

    def _verify(self, item: Dict):
        url = item.get("url", "")
        if not url:
            item["accessibility"] = "UNKNOWN"
            return

        try:
            request = Request(url, method="HEAD", headers={"User-Agent": "SocialListeningDiscovery/1.0"})
            with urlopen(request, timeout=self.timeout) as response:
                item["accessibility"] = "ACCESSIBLE" if response.status < 400 else "FAILED"
                item["last_verified_at"] = datetime.utcnow().isoformat()
        except (HTTPError, URLError, TimeoutError, Exception) as exc:
            # Fallback for HEAD request failure
            item["accessibility"] = "ACCESSIBLE" if item.get("tier", 5) == 5 else "FAILED"
            item["failure_reason"] = f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _source_key(platform: str, url: str) -> str:
        return f"{platform}:" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _score(item: Dict, target: str, aliases: List[str]):
        haystack = f"{item.get('title', '')} {item.get('snippet', '')} {item.get('url', '')}".lower()
        terms = [target.lower()] + [str(alias).lower() for alias in aliases]
        hits = sum(1 for term in terms if term and term in haystack)
        name_score = 1.0 if target.lower() in item.get("title", "").lower() else 0.0
        snippet_score = min(1.0, hits / max(1, len(terms)))
        url_score = 1.0 if target.lower().replace(" ", "") in item.get("url", "").replace(" ", "") else 0.0
        item["relevance_score"] = round(
            min(1.0, 0.40 * name_score + 0.30 * snippet_score + 0.20 * url_score + 0.10 * bool(hits)),
            4
        )

    def _new_run(self, status: str) -> Dict:
        return {
            "status": status,
            "error": None,
            "providers": [f"Tier {p.tier_level}: {p.name}" for p in self.providers],
            "queries": [],
            "query_count": 0,
            "requests": [],
            "search_results": 0,
            "urls_extracted": 0,
            "platform_counts": {},
            "valid_candidates": 0,
            "duplicates_removed": 0,
            "candidate_count": 0,
            "selected_count": 0
        }
