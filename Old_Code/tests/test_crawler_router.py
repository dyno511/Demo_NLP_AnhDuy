import unittest

from app.crawler.router import CrawlAdapter, CrawlRouter


class FixtureAdapter(CrawlAdapter):
    platform = "fixture"

    def supports(self, source):
        return source.get("platform") == self.platform

    def crawl(self, source, max_items):
        return [{"source": "fixture", "post_id": source["source_key"], "comment_id": None,
                 "post_url": source["url"], "text": "real adapter test fixture", "author": "fixture",
                 "created_at": "", "content_type": "post"}]


class TestCrawlRouter(unittest.TestCase):
    def test_routes_only_supported_sources(self):
        sources = [
            {"source_key": "fixture:1", "platform": "fixture", "source_type": "page", "url": "https://example.test/a"},
            {"source_key": "tiktok:1", "platform": "tiktok", "source_type": "tiktok", "url": "https://tiktok.com/@x"},
        ]
        items, summary = CrawlRouter(adapters=[FixtureAdapter()]).crawl_sources(sources, max_items=5)
        self.assertEqual(len(items), 1)
        self.assertEqual(summary["sources_crawled"], 1)
        self.assertEqual(summary["unsupported_sources"], 1)
        self.assertEqual(summary["updates"][1]["status"], "CRAWLER_UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
