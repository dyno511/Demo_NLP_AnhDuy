from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAlertChannel(ABC):
    """
    Abstract Interface for Alert Channel Implementations.
    """

    @abstractmethod
    def send_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Sends formatted alert notification.
        
        Expected payload format in alert_data:
        {
            "target_organization": "Đại học Nam Cần Thơ",
            "sentiment": "NEGATIVE",
            "confidence": 0.91,
            "text": "Vietnamese content...",
            "source": "Facebook",
            "post_url": "https://...",
            "author": "SinhVienAnDanh",
            "detected_at": "ISO-8601 Timestamp"
        }
        """
        pass
