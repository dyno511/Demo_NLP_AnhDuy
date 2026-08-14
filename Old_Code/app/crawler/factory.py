from app.crawler.base import BaseCrawler
from app.crawler.mock_crawler import MockCrawler
from app.crawler.facebook_crawler import FacebookCrawler
from app.crawler.rss_crawler import RSSCrawler
from app.utils.logger import logger

class CrawlerFactory:
    """
    Factory class to instantiate the appropriate crawler implementation
    based on configuration.
    """

    @staticmethod
    def get_crawler(platform_type: str = "mock") -> BaseCrawler:
        platform = platform_type.lower().strip()
        if platform == "facebook":
            logger.info("[CrawlerFactory] Using Facebook Crawler Implementation.")
            return FacebookCrawler()
        elif platform == "rss":
            logger.info("[CrawlerFactory] Using public RSS/Atom Crawler.")
            return RSSCrawler()
        else:
            logger.info(f"[CrawlerFactory] Using Mock Crawler Implementation for platform '{platform}'.")
            return MockCrawler()
