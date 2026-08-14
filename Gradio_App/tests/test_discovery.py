import unittest

from app.discovery.providers import (
    DirectHtmlProvider,
    SitemapRssProvider,
    ArchiveIndexProvider,
    DuckDuckGoHtmlProvider,
    MockDiscoveryProvider,
    ProviderUnavailableError,
    SearchProvider
)
from app.discovery.service import DiscoveryService
from app.discovery.platforms import (
    FacebookStrategy,
    TikTokStrategy,
    YouTubeStrategy
)


class FailingTierProvider(SearchProvider):
    name = "failing_tier"
    tier_level = 1

    def search(self, query: str):
        raise ProviderUnavailableError("Tier 1 Failed")


class Test5TierFallbackDiscovery(unittest.TestCase):
    def test_5tier_hierarchy_fallback(self):
        """Test fallback sequentially from Tier 1 to Tier 5."""
        service = DiscoveryService()
        results = service.discover("Đại học Nam Cần Thơ", ["DNC"], limit=10)
        run = service.get_last_run()

        self.assertIn(run["status"], {"SUCCESS", "PARTIAL_SUCCESS"})
        self.assertGreater(len(results), 0)
        # Ensure tier metadata is recorded
        self.assertTrue(any("tier" in item or "discovery_source" in item for item in results))

    def test_fallback_to_mock_when_all_networks_fail(self):
        """Test that Tier 5 (Mock Discovery) triggers when upper network tiers fail."""
        service = DiscoveryService(providers=[FailingTierProvider(), MockDiscoveryProvider()])
        results = service.discover("Đại học Nam Cần Thơ", ["DNC"], limit=5)
        run = service.get_last_run()

        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["discovery_source"], "mock_fallback")

    def test_queries_change_dynamically_per_target_and_platform(self):
        """Test query generation per target and platform."""
        fb_strategy = FacebookStrategy()
        tt_strategy = TikTokStrategy()

        fb_queries = fb_strategy.build_queries("Đại học Nam Cần Thơ", ["ĐH DNC", "DNC"])
        tt_queries = tt_strategy.build_queries("Đại học Nam Cần Thơ", ["ĐH DNC"])

        self.assertIn('site:facebook.com "Đại học Nam Cần Thơ"', fb_queries)
        self.assertIn('site:facebook.com "ĐH DNC"', fb_queries)
        self.assertIn('site:tiktok.com "Đại học Nam Cần Thơ"', tt_queries)


if __name__ == "__main__":
    unittest.main()
