import unittest
from app.ai.entity_detector import OrganizationDetector
from app.ai.sentiment_analyzer import VietnameseSentimentAnalyzer

class TestAIEngine(unittest.TestCase):
    def setUp(self):
        self.detector = OrganizationDetector(
            target_org="Đại học DNC",
            aliases=["ĐH DNC", "DNC", "Trường DNC"]
        )
        self.sentiment_analyzer = VietnameseSentimentAnalyzer(force_heuristic=True)

    def test_organization_detection(self):
        """Test entity matching for official names and aliases."""
        test_cases = [
            ("Sinh viên Đại học DNC tham gia hội thao.", True, "Đại học DNC"),
            ("Chất lượng đào tạo ĐH DNC rất tốt.", True, "ĐH DNC"),
            ("Căn tếng DNC phục vụ kém quá.", True, "DNC"),
            ("Học phí Trường DNC tăng cao.", True, "Trường DNC"),
            ("Hôm nay thời tiết đẹp quá.", False, None),
        ]

        for text, expected_detected, expected_org in test_cases:
            res = self.detector.detect(text)
            self.assertEqual(res["org_detected"], expected_detected, f"Failed on text: {text}")
            if expected_detected:
                self.assertIsNotNone(res["matched_org"])

    def test_sentiment_analysis(self):
        """Test Vietnamese sentiment classification."""
        cases = [
            ("Dịch vụ của trường rất tốt.", "POSITIVE"),
            ("Cơ sở vật chất quá tệ, nhân viên hách dịch.", "NEGATIVE"),
            ("Trường tổ chức sự kiện hôm nay.", "NEUTRAL"),
        ]

        for text, expected_label in cases:
            res = self.sentiment_analyzer.analyze(text)
            self.assertIsNotNone(res)
            if expected_label != "NEUTRAL":
                self.assertEqual(res["label"], expected_label, f"Sentiment mismatch for text: {text}")
            self.assertGreaterEqual(res["confidence"], 0.0)

    def test_sentiment_analysis_transformer_mode(self):
        """Verify VietnameseSentimentAnalyzer auto-fallback/loading without crash."""
        analyzer = VietnameseSentimentAnalyzer(force_heuristic=False)
        res = analyzer.analyze("Trường học cơ sở vật chất rất tốt, đáng tiền.")
        self.assertIsNotNone(res)
        self.assertIn(res["label"], ["POSITIVE", "NEGATIVE", "NEUTRAL"])

if __name__ == "__main__":
    unittest.main()

