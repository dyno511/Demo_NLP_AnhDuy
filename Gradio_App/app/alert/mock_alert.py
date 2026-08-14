from typing import Dict, Any, List
from app.alert.base import BaseAlertChannel
from app.utils.logger import logger

class MockAlert(BaseAlertChannel):
    """
    Mock Alert Channel for local testing and demonstration.
    Stores alerts in memory and logs formatted alert payloads.
    """

    def __init__(self):
        self.sent_alerts: List[Dict[str, Any]] = []

    def send_alert(self, alert_data: Dict[str, Any]) -> bool:
        self.sent_alerts.append(alert_data)
        logger.info(
            f"\n[MockAlert] 🚨 SIMULATED ALERT SENT:\n"
            f"  - Target Org : {alert_data.get('target_organization')}\n"
            f"  - Sentiment  : {alert_data.get('sentiment')}\n"
            f"  - Confidence : {float(alert_data.get('confidence', 0.0))*100:.1f}%\n"
            f"  - Content    : {alert_data.get('text')}\n"
            f"  - Link       : {alert_data.get('post_url')}\n"
        )
        return True
