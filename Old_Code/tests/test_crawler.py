import unittest
from app.crawler.mock_crawler import MockCrawler
from app.crawler.factory import CrawlerFactory

class TestCrawler(unittest.TestCase):
    def setUp(self):
        self.crawler = MockCrawler()

    def test_fetch_data_schema(self):
        """Verify data schema of returned items."""
        data = self.crawler.fetch_data(target_pages=["dnc_confessions"], max_items=5)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

        required_keys = ["source", "post_id", "comment_id", "post_url", "text", "author", "created_at", "content_type"]
        for item in data:
            for key in required_keys:
                self.assertIn(key, item, f"Key '{key}' missing from crawler output item.")
            self.assertTrue(item["post_url"].startswith("http"), "Invalid URL format.")

    def test_factory(self):
        """Verify crawler factory instantiation."""
        crawler_mock = CrawlerFactory.get_crawler("mock")
        self.assertIsInstance(crawler_mock, MockCrawler)

    def test_repository_deduplication(self):
        """Verify SQLite repository initialization and deduplication hash logic."""
        from app.db.repository import Repository
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_db_path = tmp.name

        try:
            repo = Repository(db_path=tmp_db_path)
            item_id = repo.generate_item_id("post_101", "cmt_202", "Nội dung bài viết mẫu")
            self.assertTrue(isinstance(item_id, str) and len(item_id) == 64)

            # Test check processed before saving
            self.assertFalse(repo.is_item_processed(item_id))

            # Test save item
            dummy_item = {
                "item_id": item_id,
                "source": "facebook_mock",
                "post_id": "post_101",
                "comment_id": "cmt_202",
                "post_url": "https://facebook.com/post/101",
                "author": "Tester",
                "text": "Nội dung bài viết mẫu",
                "content_type": "comment",
                "created_at": "2026-08-09T05:00:00"
            }
            dummy_ai = {"org_detected": True, "matched_org": "Đại học DNC", "label": "NEGATIVE", "confidence": 0.95}
            saved_id = repo.save_processed_item(dummy_item, dummy_ai, alert_sent=True)

            self.assertEqual(saved_id, item_id)
            self.assertTrue(repo.is_item_processed(item_id))

            # Test stats
            stats = repo.get_system_stats()
            self.assertEqual(stats["total_items"], 1)
            self.assertEqual(stats["negative_items"], 1)
        finally:
            if os.path.exists(tmp_db_path):
                os.remove(tmp_db_path)

if __name__ == "__main__":
    unittest.main()

