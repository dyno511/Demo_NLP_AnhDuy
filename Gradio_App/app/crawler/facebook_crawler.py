import time
import logging
from datetime import datetime
from typing import List, Dict, Any
from app.crawler.base import BaseCrawler
from app.utils.logger import logger


def scrape_facebook_page(page_name: str, target_keyword: str = "", max_pages: int = 1) -> List[Dict[str, Any]]:
    """
    Quét các bài đăng và bình luận gần đây từ một trang Facebook công khai.
    Thực hiện theo đúng gợi ý chiến thuật của Thầy Huy:
    - Sử dụng thư viện facebook-scraper nhẹ nhàng, không dùng trình duyệt giả lập.
    - Nghỉ 5 giây (time.sleep(5)) giữa các bài đăng để tránh bị Facebook cấm IP / Checkpoint.
    - Chỉ quét các Page hoặc Nhóm công khai.
    """
    logger.info(f"[*] Bắt đầu quét trang công khai Facebook: {page_name}")
    scraped_data = []

    try:
        try:
            from facebook_scraper import get_posts
            has_fb_scraper = True
        except ImportError:
            has_fb_scraper = False

        if not has_fb_scraper:
            logger.warning("[!] Thư viện 'facebook-scraper' chưa được cài đặt. Vui lòng chạy: pip install facebook-scraper")
            return []

        for post in get_posts(page_name, pages=max_pages, options={"comments": True}):
            text_content = str(post.get("text") or post.get("post_text") or "")
            post_id = str(post.get("post_id", ""))
            post_url = post.get("post_url") or f"https://facebook.com/{page_name}/posts/{post_id}"
            created_at = str(post.get("time") or datetime.now().isoformat())

            # Lọc bài đăng theo từ khóa nếu từ khóa được chỉ định
            if not target_keyword or target_keyword.lower() in text_content.lower():
                scraped_data.append({
                    "source": "facebook",
                    "post_id": post_id,
                    "comment_id": None,
                    "post_url": post_url,
                    "text": text_content,
                    "author": page_name,
                    "created_at": created_at,
                    "content_type": "post"
                })
                logger.info(f"    - Đã thu thập bài viết: {post_id}")

            # Thu thập bình luận chi tiết
            for comment in post.get("comments_full", []):
                cmt_id = str(comment.get("comment_id", ""))
                cmt_text = str(comment.get("comment_text", ""))
                if cmt_text:
                    if not target_keyword or target_keyword.lower() in cmt_text.lower():
                        scraped_data.append({
                            "source": "facebook",
                            "post_id": post_id,
                            "comment_id": cmt_id,
                            "post_url": f"{post_url}?comment_id={cmt_id}",
                            "text": cmt_text,
                            "author": str(comment.get("commenter_name", "Anonymous")),
                            "created_at": created_at,
                            "content_type": "comment"
                        })

            # Nghỉ 5 giây giữa các bài để tránh bị Facebook chặn (theo lưu ý của Thầy Huy)
            time.sleep(5)

    except Exception as e:
        logger.error(f"[!] Lỗi khi cào dữ liệu Facebook: {e}")

    logger.info(f"[*] Tổng số bài viết/bình luận thu thập được từ '{page_name}': {len(scraped_data)}")
    return scraped_data


class FacebookCrawler(BaseCrawler):
    """
    Public Facebook Page & Group Crawler Class wrapping the instructor's module guidelines.
    """

    def fetch_data(self, target_pages: List[str], max_items: int = 10) -> List[Dict[str, Any]]:
        all_items = []
        for page in target_pages:
            items = scrape_facebook_page(page_name=page, target_keyword="", max_pages=1)
            all_items.extend(items)
            if len(all_items) >= max_items:
                break
        return all_items[:max_items]
