import requests
from typing import Dict, Any
from app.alert.base import BaseAlertChannel
from app.utils.logger import logger
from config import Config

class TelegramAlert(BaseAlertChannel):
    """
    Telegram Bot API Alert Channel Implementation.
    """

    def __init__(self, bot_token: str = "8812720117:AAHOk0_96tuNjw3-eizzdWxtn-NsLefumqo", chat_id: str = "-5469376065"):
        self.bot_token = bot_token or Config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or Config.TELEGRAM_CHAT_ID

    def send_alert(self, alert_data: Dict[str, Any]) -> bool:
        # Validate configuration and log clean diagnostic details without leaking credentials
        token_present = "present" if self.bot_token else "missing"
        chat_id_present = "present" if self.chat_id else "missing"

        if not self.bot_token or not self.chat_id:
            logger.error(
                f"[TelegramAlert] Telegram configuration missing:\n"
                f"- Bot Token: {token_present}\n"
                f"- Chat ID: {chat_id_present}"
            )
            return False

        # Backward-compatible message builder: 'type' and 'author' are optional.
        # Existing callers (pipeline / AI Test Bench) keep their current output.
        message = "🚨 *CẢNH BÁO NỘI DUNG TIÊU CỰC*\n\n"
        if alert_data.get("type"):
            message += f"*Loại:*\n{alert_data['type']}\n\n"
        message += (
            f"*Tổ chức:*\n{alert_data.get('target_organization', 'Không xác định')}\n\n"
            f"*Nội dung:*\n_{alert_data.get('text', '')}_\n\n"
            f"*Sentiment:*\n{alert_data.get('sentiment', 'NEGATIVE')}\n\n"
            f"*Độ tin cậy:*\n{float(alert_data.get('confidence', 0.0)) * 100:.1f}%\n\n"
            f"*Nguồn:*\n{alert_data.get('source', 'Mạng xã hội')}\n\n"
            f"*Link:*\n{alert_data.get('post_url', 'N/A')}\n\n"
        )
        if alert_data.get("author"):
            message += f"*Username:*\n{alert_data['author']}\n\n"
        message += f"*Thời gian:*\n{alert_data.get('detected_at', '')}"

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("[TelegramAlert] Alert sent successfully via Telegram Bot API.")
                return True
            else:
                logger.error(f"[TelegramAlert] Telegram API error ({response.status_code}): {response.text}")
                return False
        except Exception as e:
            logger.error(f"[TelegramAlert] Connection failure during Telegram alert dispatch: {e}")
            return False
