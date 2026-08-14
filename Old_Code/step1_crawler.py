"""
MODULE 1: THU THẬP DỮ LIỆU TỪ FACEBOOK (CRAWLER)
Theo hướng dẫn của Thầy Huy.

Sử dụng thư viện facebook-scraper nhẹ nhàng, nghỉ 5s giữa các bài để né cấm IP.
"""

from app.crawler.facebook_crawler import scrape_facebook_page

if __name__ == "__main__":
    # Ví dụ: Quét trang fanpage của một tờ báo hoặc trang công khai, tìm kiếm các bài có nhắc đến "Đại học DNC"
    target_org = "Đại học DNC"
    page_to_scrape = "baotuoitre"
    
    print(f"[*] Bắt đầu thực thi Module 1 Crawler cho tổ chức: '{target_org}'...")
    data = scrape_facebook_page(page_name=page_to_scrape, target_keyword=target_org, max_pages=1)
    print(f"[*] Tổng số bài viết/bình luận thu thập được có nhắc đến '{target_org}': {len(data)}")
