import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
from app.crawler.base import BaseCrawler
from app.utils.logger import logger

class MockCrawler(BaseCrawler):
    """
    Mock Data Crawler providing realistic Vietnamese social media data.
    Designed for local execution, demonstration, offline testing, and web deployment.
    """

    SAMPLE_POSTS = [
        # Negative mentions of DNC
        {
            "target": "dnc_confessions",
            "author": "SinhVienAnDanh_01",
            "text": "Bức xúc quá mọi người ơi! Phòng đào tạo Đại học DNC làm việc chậm trễ, xin cấp bảng điểm 2 tuần chưa xong làm lỡ học bổng của mình. Thái độ nhân viên còn hách dịch nữa!",
            "is_negative": True,
            "org": "Đại học DNC"
        },
        {
            "target": "forum_sinhvien",
            "author": "MinhTran_DNC",
            "text": "Cơ sở vật chất ĐH DNC dạo này xuống cấp trầm trọng. Máy chiếu phòng A302 hỏng 3 tuần không ai sửa, máy lạnh thì kêu ro ro nóng phát điên.",
            "is_negative": True,
            "org": "ĐH DNC"
        },
        {
            "target": "fanpage_dnc",
            "author": "GiaDinhHocSinh",
            "text": "Trường DNC tăng học phí đột ngột mà chất lượng giảng dạy không tăng! Giảng viên hay nghỉ đột xuất không báo trước. Quá thất vọng!",
            "is_negative": True,
            "org": "Trường DNC"
        },
        {
            "target": "dnc_confessions",
            "author": "ThanhNien_99",
            "text": "Căng thẳng ghê, căn tếng DNC bán thức ăn ôi thiu làm mấy bạn sinh viên bị ngộ độc thực phẩm hôm qua. Cần nhà trường làm rõ việc này!",
            "is_negative": True,
            "org": "DNC"
        },

        # Positive mentions of DNC
        {
            "target": "fanpage_dnc",
            "author": "HoangLan_K18",
            "text": "Hôm nay Đại học DNC tổ chức hội thảo hướng nghiệp rất hoành tráng! Cảm ơn nhà trường và các thầy cô đã hỗ trợ tụi em rất nhiệt tình.",
            "is_negative": False,
            "org": "Đại học DNC"
        },
        {
            "target": "dnc_confessions",
            "author": "BanCanSuLop",
            "text": "Thầy cô khoa CNTT ĐH DNC cực kỳ tâm huyết. Nhờ thầy hướng dẫn mà nhóm mình vừa đoạt giải cuộc thi sáng tạo khoa học kỹ thuật!",
            "is_negative": False,
            "org": "ĐH DNC"
        },

        # Neutral mentions of DNC
        {
            "target": "forum_sinhvien",
            "author": "TuyenSinh2026",
            "text": "Cho mình hỏi điểm chuẩn ngành Khoa học dữ liệu của Trường DNC năm nay là bao nhiêu vậy ạ? Mọi người tư vấn giúp mình với.",
            "is_negative": False,
            "org": "Trường DNC"
        },
        {
            "target": "fanpage_dnc",
            "author": "PhongDaoTao",
            "text": "Thông báo từ Đại học DNC: Lịch thi kết thúc học kỳ 2 sẽ bắt đầu từ thứ 2 tuần sau. Sinh viên chú ý xem lịch trên portal.",
            "is_negative": False,
            "org": "Đại học DNC"
        },

        # Unrelated organization / noise data
        {
            "target": "tin_tuc_hang_ngay",
            "author": "KenhTinTuc",
            "text": "Thời tiết hôm nay tại TP. Cần Thơ trời nắng đẹp, nhiệt độ dao động từ 28-34 độ C. Thích hợp cho các hoạt động ngoài trời.",
            "is_negative": False,
            "org": None
        },
        {
            "target": "review_quan_an",
            "author": "Foodie_CanTho",
            "text": "Quán bún riêu gần cầu Hưng Lợi phục vụ quá tệ, nước dùng nhạt nhẽo mà giá lại đắt. Không bao giờ quay lại!",
            "is_negative": True,
            "org": None
        }
    ]

    def fetch_data(self, target_pages: List[str], max_items: int = 10) -> List[Dict[str, Any]]:
        """Generates realistic structured social media items."""
        logger.info(f"[MockCrawler] Simulating data collection from targets: {target_pages}")
        
        items = []
        now = datetime.now()

        # Select sample items based on target pages
        selected = random.sample(self.SAMPLE_POSTS, min(max_items, len(self.SAMPLE_POSTS)))

        for idx, sample in enumerate(selected):
            post_id = f"mock_post_{random.randint(10000, 99999)}"
            created_at = (now - timedelta(minutes=random.randint(5, 120))).isoformat()
            
            # Post item
            post_url = f"https://facebook.com/{sample['target']}/posts/{post_id}"
            items.append({
                "source": "facebook_mock",
                "post_id": post_id,
                "comment_id": None,
                "post_url": post_url,
                "text": sample["text"],
                "author": sample["author"],
                "created_at": created_at,
                "content_type": "post"
            })

            # Randomly attach a comment to 30% of posts
            if random.random() < 0.3:
                comment_id = f"mock_cmt_{random.randint(100000, 999999)}"
                comment_text = f"Đúng rồi đó bạn, mình cũng thấy {sample['org'] or 'trường'} làm ăn như vậy là không ổn!" if sample["is_negative"] else f"Cảm ơn thông tin từ bạn nhé!"
                items.append({
                    "source": "facebook_mock",
                    "post_id": post_id,
                    "comment_id": comment_id,
                    "post_url": f"{post_url}?comment_id={comment_id}",
                    "text": comment_text,
                    "author": f"User_Cmt_{idx}",
                    "created_at": created_at,
                    "content_type": "comment"
                })

        logger.info(f"[MockCrawler] Successfully generated {len(items)} normalized data items.")
        return items
