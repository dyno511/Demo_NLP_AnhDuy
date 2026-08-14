import unittest
from app.alert.mock_alert import MockAlert
from app.alert.service import AlertService

class TestAlerting(unittest.TestCase):
    def test_mock_alert_dispatch(self):
        """Verify Mock Alert Channel stores and formats alert payload."""
        mock_channel = MockAlert()
        payload = {
            "target_organization": "Đại học DNC",
            "sentiment": "NEGATIVE",
            "confidence": 0.92,
            "text": "Bức xúc quá, phòng đào tạo DNC làm việc quá tệ!",
            "source": "Facebook",
            "post_url": "https://facebook.com/posts/123",
            "detected_at": "2026-08-08T12:00:00"
        }

        success = mock_channel.send_alert(payload)
        self.assertTrue(success)
        self.assertEqual(len(mock_channel.sent_alerts), 1)
        self.assertEqual(mock_channel.sent_alerts[0]["target_organization"], "Đại học DNC")

    def test_alert_service_resolution(self):
        """Verify AlertService resolves active channels correctly."""
        service = AlertService(channel="mock")
        self.assertGreater(len(service.channels), 0)

        # Test dispatch via service
        payload = {
            "target_organization": "Đại học DNC",
            "sentiment": "NEGATIVE",
            "confidence": 0.95,
            "text": "Nhà ăn trường DNC làm ăn quá ẩu!",
            "source": "Facebook",
            "post_url": "https://facebook.com/posts/456",
            "detected_at": "2026-08-08T12:05:00"
        }
        success = service.dispatch_alert(payload)
        self.assertTrue(success)

    def test_telegram_alert_missing_token(self):
        """Verify TelegramAlert handles missing credentials gracefully without throwing exceptions."""
        from app.alert.telegram import TelegramAlert
        tg_alert = TelegramAlert(bot_token="", chat_id="")
        payload = {
            "target_organization": "Đại học DNC",
            "sentiment": "NEGATIVE",
            "confidence": 0.90,
            "text": "Nội dung tiêu cực test Telegram",
            "source": "Facebook",
            "post_url": "https://facebook.com/posts/789",
            "detected_at": "2026-08-08T12:10:00"
        }
        success = tg_alert.send_alert(payload)
        self.assertFalse(success)  # Returns False gracefully due to missing token

if __name__ == "__main__":
    unittest.main()

