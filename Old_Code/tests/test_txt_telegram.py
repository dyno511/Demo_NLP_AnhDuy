import unittest

import requests

from config import Config
from app.alert.service import select_alert_candidates, build_alert_payload
from app.alert.telegram import TelegramAlert


class FakeOrgDetector:
    def detect(self, text):
        detected = "DNC" in (text or "")
        return {
            "org_detected": detected,
            "matched_org": "Đại học DNC" if detected else None,
        }


def _items():
    return [
        {"type": "COMMENT", "post_id": "1", "username": "A", "url": "https://x/1",
         "content": "Đại học DNC phục vụ tệ hại", "sentiment": "NEGATIVE", "confidence": 0.95},
        # exact duplicate -> must be dropped
        {"type": "COMMENT", "post_id": "1", "username": "A", "url": "https://x/1",
         "content": "Đại học DNC phục vụ tệ hại", "sentiment": "NEGATIVE", "confidence": 0.95},
        # below threshold -> excluded
        {"type": "POST", "post_id": "2", "username": "", "url": "https://x/2",
         "content": "Đại học DNC quá chậm trễ", "sentiment": "NEGATIVE", "confidence": 0.60},
        # positive -> excluded
        {"type": "COMMENT", "post_id": "3", "username": "B", "url": "https://x/3",
         "content": "thời tiết đẹp quá", "sentiment": "POSITIVE", "confidence": 0.95},
        # negative + high conf but no org mention -> excluded
        {"type": "COMMENT", "post_id": "4", "username": "C", "url": "https://x/4",
         "content": "quán ăn phục vụ quá tệ", "sentiment": "NEGATIVE", "confidence": 0.95},
        # qualifying POST -> included
        {"type": "POST", "post_id": "5", "username": "", "url": "https://x/5",
         "content": "Cơ sở vật chất ĐH DNC xuống cấp trầm trọng", "sentiment": "NEGATIVE", "confidence": 0.98},
    ]


class TestAlertCandidates(unittest.TestCase):
    def test_filters_and_dedups(self):
        candidates = select_alert_candidates(_items(), FakeOrgDetector(), threshold=0.80)
        self.assertEqual(len(candidates), 2)
        kinds = sorted(c["item"]["post_id"] for c in candidates)
        self.assertEqual(kinds, ["1", "5"])

    def test_threshold_respected(self):
        items = [
            {"type": "POST", "post_id": "1", "username": "", "url": "u",
             "content": "Đại học DNC tệ", "sentiment": "NEGATIVE", "confidence": 0.70},
            {"type": "POST", "post_id": "2", "username": "", "url": "u",
             "content": "Đại học DNC tệ", "sentiment": "NEGATIVE", "confidence": 0.81},
        ]
        candidates = select_alert_candidates(items, FakeOrgDetector(), threshold=0.80)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["item"]["post_id"], "2")

    def test_build_payload_comment(self):
        item = _items()[0]
        detection = FakeOrgDetector().detect(item["content"])
        payload = build_alert_payload(item, detection, detected_at="2026-01-01T00:00:00")
        self.assertEqual(payload["type"], "Bình luận")
        self.assertEqual(payload["author"], "A")
        self.assertEqual(payload["post_url"], "https://x/1")
        self.assertEqual(payload["sentiment"], "NEGATIVE")
        self.assertEqual(payload["confidence"], 0.95)
        self.assertEqual(payload["target_organization"], "Đại học DNC")
        self.assertEqual(payload["source"], "File TXT")

    def test_build_payload_post_no_username(self):
        item = _items()[5]
        detection = FakeOrgDetector().detect(item["content"])
        payload = build_alert_payload(item, detection)
        self.assertEqual(payload["type"], "Bài viết")
        self.assertEqual(payload["author"], "")
        self.assertEqual(payload["post_url"], "https://x/5")


class FakeResponse:
    status_code = 200
    text = "ok"


class TestTelegramMessage(unittest.TestCase):
    def setUp(self):
        self._orig_post = requests.post
        self.captured = {}

        def fake_post(url, json=None, timeout=None):
            self.captured["url"] = url
            self.captured["json"] = json
            return FakeResponse()

        requests.post = fake_post

    def tearDown(self):
        requests.post = self._orig_post

    def test_message_contains_required_fields(self):
        alert = TelegramAlert(bot_token="token", chat_id="chat")
        payload = {
            "target_organization": "Đại học DNC",
            "sentiment": "NEGATIVE",
            "confidence": 0.92,
            "text": "Cơ sở vật chất xuống cấp trầm trọng",
            "source": "File TXT",
            "post_url": "https://facebook.com/posts/1",
            "author": "Sinh Vien An",
            "type": "Bình luận",
            "detected_at": "2026-08-09T10:00:00",
        }
        ok = alert.send_alert(payload)
        self.assertTrue(ok)
        self.assertIn("bottoken/sendMessage", self.captured["url"])
        self.assertEqual(self.captured["json"]["chat_id"], "chat")
        sent_text = self.captured["json"]["text"]
        for token in [
            "Loại", "Bình luận", "Username", "Sinh Vien An",
            "Cơ sở vật chất xuống cấp trầm trọng", "NEGATIVE", "92.0%",
            "https://facebook.com/posts/1", "Đại học DNC",
        ]:
            self.assertIn(token, sent_text)

    def test_message_backward_compatible(self):
        # Payload without type/author (as sent by pipeline / AI Test Bench) keeps old output.
        alert = TelegramAlert(bot_token="token", chat_id="chat")
        payload = {
            "target_organization": "X",
            "sentiment": "NEGATIVE",
            "confidence": 0.9,
            "text": "t",
            "source": "fb",
            "post_url": "u",
            "detected_at": "d",
        }
        ok = alert.send_alert(payload)
        self.assertTrue(ok)
        sent_text = self.captured["json"]["text"]
        self.assertNotIn("Loại", sent_text)
        self.assertNotIn("Username", sent_text)
        self.assertIn("X", sent_text)

    def test_missing_config_returns_false(self):
        old_token, old_chat = Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHAT_ID
        Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHAT_ID = "", ""
        try:
            alert = TelegramAlert(bot_token="", chat_id="")
            self.assertFalse(alert.send_alert({}))
        finally:
            Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHAT_ID = old_token, old_chat


if __name__ == "__main__":
    unittest.main()
