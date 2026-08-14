import os
import unittest
from app.pipeline.pipeline import SocialListeningPipeline
from config import Config

class TestPipeline(unittest.TestCase):
    def setUp(self):
        # Override config for testing
        Config.SOCIAL_PLATFORM = "mock"
        Config.ALERT_CHANNEL = "mock"
        Config.SENTIMENT_THRESHOLD = 0.70
        self.pipeline = SocialListeningPipeline(force_heuristic_ai=True)

    def test_end_to_end_cycle(self):
        """Verify full pipeline run cycle executes without exceptions."""
        summary = self.pipeline.run_cycle()
        
        self.assertIn("total_scanned", summary)
        self.assertIn("org_mentions", summary)
        self.assertIn("negative_items", summary)
        self.assertIn("alerts_sent", summary)

        self.assertGreaterEqual(summary["total_scanned"], 0)
        self.assertGreaterEqual(summary["org_mentions"], 0)
        self.assertGreaterEqual(summary["negative_items"], 0)

if __name__ == "__main__":
    unittest.main()
