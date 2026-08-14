import unittest

from app.ai.sentiment_analyzer import VietnameseSentimentAnalyzer
from app.parser.txt_parser import (
    TxtParseError,
    analyze_txt,
    flatten_posts,
    parse_txt,
    EMPTY_FILE,
    INVALID_FILE,
    INVALID_FORMAT,
    PARSE_ERROR,
    SUCCESS,
)

SAMPLE = """=== BAI 1 ===
URL: https://facebook.com/dnc/posts/1
NOI DUNG:
Cơ sở vật chất ĐH DNC xuống cấp trầm trọng.
Máy chiếu phòng A302 hỏng 3 tuần không ai sửa.

--- BINH LUAN ---
1. Sinh Vien An: Phòng đào tạo làm việc quá tệ, phục vụ hách dịch!
2. Nguyễn Văn A: Cảm ơn nhà trường đã hỗ trợ tận tình.

=== BAI 2 ===
URL: https://facebook.com/dnc/posts/2
NOI DUNG:
Thông báo lịch thi học kỳ 2 từ nhà trường.
"""


class TestTxtParser(unittest.TestCase):
    def test_parse_multiple_posts_with_comments(self):
        posts = parse_txt(SAMPLE)
        self.assertEqual(len(posts), 2)

        p1 = posts[0]
        self.assertEqual(p1["post_id"], "1")
        self.assertEqual(p1["url"], "https://facebook.com/dnc/posts/1")
        self.assertIn("xuống cấp trầm trọng", p1["content"])
        self.assertIn("Máy chiếu phòng A302", p1["content"])
        self.assertEqual(len(p1["comments"]), 2)
        self.assertEqual(p1["comments"][0]["username"], "Sinh Vien An")
        self.assertIn("quá tệ", p1["comments"][0]["content"])
        self.assertEqual(p1["comments"][1]["username"], "Nguyễn Văn A")

        p2 = posts[1]
        self.assertEqual(p2["post_id"], "2")
        self.assertEqual(len(p2["comments"]), 0)
        self.assertIn("lịch thi", p2["content"])

    def test_flatten_preserves_relations(self):
        posts = parse_txt(SAMPLE)
        items = flatten_posts(posts)
        types = [i["type"] for i in items]
        self.assertEqual(types, ["POST", "COMMENT", "COMMENT", "POST"])
        self.assertEqual(items[1]["post_id"], "1")
        self.assertEqual(items[1]["username"], "Sinh Vien An")
        self.assertEqual(items[3]["type"], "POST")
        self.assertEqual(items[3]["username"], "")

    def test_post_without_comments(self):
        text = "=== BAI 1 ===\nURL: http://x.com\nNOI DUNG:\nnội dung không có bình luận\n"
        posts = parse_txt(text)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["comments"], [])
        self.assertIn("nội dung không có bình luận", posts[0]["content"])

    def test_username_with_spaces_and_colon_in_comment(self):
        text = (
            "=== BAI 1 ===\nURL: http://x.com\nNOI DUNG:\nnd\n"
            "--- BINH LUAN ---\n1. Nguyễn Văn An: Chất lượng 10/10: rất đáng tiền\n"
        )
        posts = parse_txt(text)
        comment = posts[0]["comments"][0]
        self.assertEqual(comment["username"], "Nguyễn Văn An")
        self.assertEqual(comment["content"], "Chất lượng 10/10: rất đáng tiền")

    def test_diacritic_variants(self):
        text = (
            "=== BÀI 1 ===\nURL: https://x\nNỘI DUNG:\nnội dung bài\n"
            "--- BÌNH LUẬN ---\n1. An: hay quá\n"
        )
        posts = parse_txt(text)
        self.assertEqual(len(posts), 1)
        self.assertEqual(len(posts[0]["comments"]), 1)

    def test_skip_empty_block_keeps_others(self):
        text = (
            "=== BAI 1 ===\nURL: http://x.com\nNOI DUNG:\nnội dung 1\n"
            "=== BAI 2 ===\n\n"
            "=== BAI 3 ===\nURL: http://y.com\nNOI DUNG:\nnội dung 3\n"
        )
        posts = parse_txt(text)
        self.assertEqual(len(posts), 2)
        self.assertEqual([p["post_id"] for p in posts], ["1", "3"])

    def test_empty_file(self):
        with self.assertRaises(TxtParseError) as ctx:
            parse_txt("   \n  ")
        self.assertEqual(ctx.exception.code, EMPTY_FILE)

    def test_invalid_format_no_posts(self):
        with self.assertRaises(TxtParseError) as ctx:
            parse_txt("đây không phải file hợp lệ\nURL: xyz")
        self.assertEqual(ctx.exception.code, INVALID_FORMAT)

    def test_all_blocks_empty_raises_parse_error(self):
        with self.assertRaises(TxtParseError) as ctx:
            parse_txt("=== BAI 1 ===\n=== BAI 2 ===")
        self.assertEqual(ctx.exception.code, PARSE_ERROR)


class TestAnalyzeTxt(unittest.TestCase):
    def setUp(self):
        self.analyzer = VietnameseSentimentAnalyzer(force_heuristic=True)

    def test_full_pipeline_success(self):
        result = analyze_txt(SAMPLE.encode("utf-8"), "data.txt", self.analyzer)
        self.assertEqual(result["status"], SUCCESS)
        self.assertIsNone(result["error_code"])
        self.assertEqual(result["summary"]["total_posts"], 2)
        self.assertEqual(result["summary"]["total_comments"], 2)
        self.assertEqual(result["summary"]["total_samples"], 4)
        self.assertEqual(result["summary"]["positive"] + result["summary"]["negative"]
                         + result["summary"]["neutral"], 4)
        self.assertIsInstance(result["summary"]["mean_confidence"], float)
        for item in result["items"]:
            self.assertIn(item["sentiment"], ["POSITIVE", "NEGATIVE", "NEUTRAL"])
            self.assertIn(item["type"], ["POST", "COMMENT"])

    def test_invalid_extension(self):
        result = analyze_txt(b"x", "data.csv", self.analyzer)
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["error_code"], INVALID_FILE)

    def test_empty_bytes(self):
        result = analyze_txt(b"", "data.txt", self.analyzer)
        self.assertEqual(result["error_code"], EMPTY_FILE)

    def test_item_error_isolation(self):
        class BadAnalyzer:
            def analyze(self, text):
                if "tệ" in text:
                    raise RuntimeError("boom")
                return {"label": "POSITIVE", "confidence": 0.9}

        result = analyze_txt(SAMPLE.encode("utf-8"), "data.txt", BadAnalyzer())
        self.assertEqual(result["status"], SUCCESS)
        self.assertGreater(result["summary"]["item_errors"], 0)
        self.assertEqual(len(result["items"]), 4)
        errors = [i for i in result["items"] if i["error"]]
        self.assertEqual(len(errors), result["summary"]["item_errors"])

    def test_duplicate_content_analyzed_once(self):
        calls = {"count": 0}

        class CountingAnalyzer:
            def analyze(self, text):
                calls["count"] += 1
                return {"label": "NEUTRAL", "confidence": 0.75}

        text = (
            "=== BAI 1 ===\nURL: http://a\nNOI DUNG:\nnội dung giống nhau\n"
            "--- BINH LUAN ---\n1. A: nội dung giống nhau\n"
            "=== BAI 2 ===\nURL: http://b\nNOI DUNG:\nnội dung giống nhau\n"
        )
        result = analyze_txt(text.encode("utf-8"), "data.txt", CountingAnalyzer())
        self.assertEqual(result["status"], SUCCESS)
        self.assertEqual(result["summary"]["total_samples"], 3)
        self.assertEqual(calls["count"], 1)


if __name__ == "__main__":
    unittest.main()
