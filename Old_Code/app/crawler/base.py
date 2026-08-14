from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseCrawler(ABC):
    """
    Abstract Base Class for Social Media Data Collectors.
    Ensures normalized output data schema across all platform crawlers.
    """

    @abstractmethod
    def fetch_data(self, target_pages: List[str], max_items: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch social media posts and comments from specified targets.
        
        Returns a list of standardized dictionaries:
        [
            {
                "source": "facebook|tiktok|rss|mock",
                "post_id": "123456",
                "comment_id": "789012" or None,
                "post_url": "https://...",
                "text": "Vietnamese content...",
                "author": "User Name",
                "created_at": "ISO-8601 Timestamp",
                "content_type": "post" or "comment"
            }
        ]
        """
        pass
