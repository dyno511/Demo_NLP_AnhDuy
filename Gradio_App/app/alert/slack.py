import requests
from typing import Dict, Any
from app.alert.base import BaseAlertChannel
from app.utils.logger import logger
from config import Config

class SlackAlert(BaseAlertChannel):
    """
    Slack Incoming Webhook Alert Channel Implementation.
    """

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url or Config.SLACK_WEBHOOK_URL

    def send_alert(self, alert_data: Dict[str, Any]) -> bool:
        if not self.webhook_url:
            logger.warning("[SlackAlert] Missing SLACK_WEBHOOK_URL. Skipping real HTTP request.")
            return False

        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🚨 SOCIAL LISTENING ALERT", "emoji": True}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Organization:*\n{alert_data.get('target_organization')}"},
                        {"type": "mrkdwn", "text": f"*Sentiment:*\n`{alert_data.get('sentiment')}`"},
                        {"type": "mrkdwn", "text": f"*Confidence:*\n{float(alert_data.get('confidence', 0.0)) * 100:.1f}%"},
                        {"type": "mrkdwn", "text": f"*Source:*\n{alert_data.get('source')}"}
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Content:*\n>{alert_data.get('text')}"}
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"<{alert_data.get('post_url')}|View Post / Comment Link>"}
                }
            ]
        }

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("[SlackAlert] Alert sent successfully via Slack Webhook.")
                return True
            else:
                logger.error(f"[SlackAlert] Slack Webhook error ({response.status_code}): {response.text}")
                return False
        except Exception as e:
            logger.error(f"[SlackAlert] Connection failure during Slack alert dispatch: {e}")
            return False
