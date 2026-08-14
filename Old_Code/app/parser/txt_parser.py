"""
TXT Upload Parser & Analysis Orchestrator.

Parses uploaded .txt files following the format:

    === BAI 1 ===
    URL: https://...
    NOI DUNG:
    ...content...
    --- BINH LUAN ---
    1. Username: comment
    2. Username: comment

Then flattens each post/comment into typed items (POST / COMMENT) and
reuses the EXISTING sentiment analyzer (app.ai.sentiment_analyzer) —
no duplicate AI logic is created here.

Error codes:
    FILE_NOT_SELECTED - no file was provided by the user
    INVALID_FILE      - wrong extension or undecodable content
    EMPTY_FILE        - file exists but contains no text
    INVALID_FORMAT    - no `=== BAI n ===` blocks found
    PARSE_ERROR       - file parsed partially/failed at block level
    ANALYSIS_ERROR    - sentiment inference failed for an item
    SUCCESS           - pipeline completed (possibly with per-item errors)
"""

import codecs
import re
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------
FILE_NOT_SELECTED = "FILE_NOT_SELECTED"
INVALID_FILE = "INVALID_FILE"
EMPTY_FILE = "EMPTY_FILE"
INVALID_FORMAT = "INVALID_FORMAT"
PARSE_ERROR = "PARSE_ERROR"
ANALYSIS_ERROR = "ANALYSIS_ERROR"
SUCCESS = "SUCCESS"


class TxtParseError(Exception):
    """Raised when a TXT file cannot be parsed. Carries an error code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Regex patterns (case-insensitive, supports both plain and diacritic forms)
# ---------------------------------------------------------------------------
_POST_HEADER_RE = re.compile(
    r"^\s*===\s*(?:BAI|BÀI)\s*([^=\n]*?)\s*===\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_URL_LINE_RE = re.compile(r"^\s*URL\s*[:：]\s*(.+)$", re.IGNORECASE)
_CONTENT_HEADER_RE = re.compile(
    r"^\s*(?:NOI|NỘI)\s*(?:DUNG|DỤNG)\s*[:：]\s*(.*)$"
    r"|^\s*(?:NOI|NỘI)\s*(?:DUNG|DỤNG)\s*$",
    re.IGNORECASE,
)
_COMMENTS_HEADER_RE = re.compile(
    r"^\s*-{2,}\s*(?:BINH|BÌNH)\s*(?:LUAN|LUẬN)\s*-{2,}\s*$"
    r"|^\s*(?:BINH|BÌNH)\s*(?:LUAN|LUẬN)\s*[:：]\s*$",
    re.IGNORECASE,
)
_COMMENT_LINE_RE = re.compile(r"^\s*(\d+)\s*(?:[.):])\s+(.+)$")


# ---------------------------------------------------------------------------
# Decoding & validation
# ---------------------------------------------------------------------------
def decode_bytes(raw: bytes) -> str:
    """Best-effort decode of uploaded file bytes with encoding detection."""
    if not raw or not raw.strip():
        raise TxtParseError(EMPTY_FILE, "File rỗng hoặc không có nội dung.")

    if raw.startswith(codecs.BOM_UTF8):
        return raw.decode("utf-8-sig")
    if raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE):
        return raw.decode("utf-16")

    for enc in ("utf-8", "utf-16-le", "utf-16-be", "cp1252", "latin-1"):
        try:
            decoded = raw.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
        # utf-16 without BOM on a utf-8/ASCII file yields embedded nulls -> skip
        if "\x00" in decoded:
            continue
        return decoded

    raise TxtParseError(INVALID_FILE, "Không thể xác định encoding của file.")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def _split_comment(rest: str) -> tuple:
    """Split 'Username: content' on the FIRST colon (content may contain colons)."""
    if ":" in rest:
        username, content = rest.split(":", 1)
        return username.strip(), content.strip()
    return "", rest.strip()


def _parse_post_block(post_id: str, block_text: str) -> Dict[str, Any]:
    """Parse a single '=== BAI n ===' block into a structured post."""
    url = ""
    content_buffer: List[str] = []
    comments: List[Dict[str, str]] = []
    in_comments = False
    last_comment: Optional[Dict[str, str]] = None

    for raw_line in block_text.splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if not stripped:
            if in_comments:
                continue
            content_buffer.append("")
            continue

        if not in_comments:
            url_match = _URL_LINE_RE.match(stripped)
            if url_match and not url:
                url = url_match.group(1).strip()
                continue

            if _COMMENTS_HEADER_RE.match(stripped):
                in_comments = True
                continue

            content_match = _CONTENT_HEADER_RE.match(stripped)
            if content_match:
                trailing = content_match.group(1).strip()
                if trailing:
                    content_buffer.append(trailing)
                continue

            content_buffer.append(line)
        else:
            comment_match = _COMMENT_LINE_RE.match(stripped)
            if comment_match:
                username, content = _split_comment(comment_match.group(2))
                last_comment = {"username": username, "content": content}
                comments.append(last_comment)
            else:
                # Continuation line of the previous comment (keep content intact)
                if last_comment is not None:
                    last_comment["content"] = (last_comment["content"] + "\n" + line).strip()

    content = "\n".join(content_buffer).strip()
    return {
        "post_id": post_id,
        "url": url,
        "content": content,
        "comments": comments,
    }


def parse_txt(text: str) -> List[Dict[str, Any]]:
    """
    Parse full TXT content into structured posts.

    Returns:
        [{"post_id": "...", "url": "...", "content": "...",
          "comments": [{"username": "...", "content": "..."}, ...]}, ...]

    Raises:
        TxtParseError (EMPTY_FILE / INVALID_FORMAT / PARSE_ERROR)
    """
    if not text or not text.strip():
        raise TxtParseError(EMPTY_FILE, "File rỗng, không có dữ liệu để phân tích.")

    headers = list(_POST_HEADER_RE.finditer(text))
    if not headers:
        raise TxtParseError(
            INVALID_FORMAT,
            "Không tìm thấy block bài viết hợp lệ (cần dòng '=== BAI n ===').",
        )

    posts: List[Dict[str, Any]] = []
    for idx, match in enumerate(headers):
        start = match.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        block_text = text[start:end]

        post_id = (match.group(1) or "").strip() or str(idx + 1)
        post = _parse_post_block(post_id, block_text)

        if not post["url"] and not post["content"] and not post["comments"]:
            # Completely empty block: skip it instead of failing the whole file.
            continue
        posts.append(post)

    if not posts:
        raise TxtParseError(
            PARSE_ERROR,
            "Không parse được bài viết nào từ file đã tải lên.",
        )

    return posts


def flatten_posts(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Flatten structured posts into typed analysis items.

    POST keeps its url; COMMENT keeps its username. The post_id relation
    is preserved on every item.
    """
    items: List[Dict[str, Any]] = []
    for post in posts:
        items.append({
            "type": "POST",
            "post_id": post["post_id"],
            "url": post["url"],
            "username": "",
            "content": post["content"],
        })
        for comment in post["comments"]:
            items.append({
                "type": "COMMENT",
                "post_id": post["post_id"],
                "url": post["url"],
                "username": comment["username"],
                "content": comment["content"],
            })
    return items


# ---------------------------------------------------------------------------
# Analysis orchestration (reuses the existing sentiment engine)
# ---------------------------------------------------------------------------
def _build_summary(posts: List[Dict[str, Any]], items: List[Dict[str, Any]], item_errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    sentiments = [i["sentiment"] for i in items if i.get("sentiment")]
    confidences = [i["confidence"] for i in items if i.get("confidence") is not None]

    return {
        "total_posts": len(posts),
        "total_comments": sum(len(p["comments"]) for p in posts),
        "total_samples": len(items),
        "positive": sentiments.count("POSITIVE"),
        "negative": sentiments.count("NEGATIVE"),
        "neutral": sentiments.count("NEUTRAL"),
        "unclassified": len(items) - len(sentiments),
        "item_errors": len(item_errors),
        "mean_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
    }


def _error_result(code: str, message: str) -> Dict[str, Any]:
    return {
        "status": "ERROR",
        "error_code": code,
        "error_message": message,
        "posts": [],
        "items": [],
        "summary": {},
        "item_errors": [],
    }


def analyze_txt(
    raw: bytes,
    filename: str,
    analyzer: Any,
    org_detector: Any = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    """
    End-to-end TXT analysis: validate -> decode -> parse -> flatten -> sentiment.

    Reuses the project's existing sentiment analyzer (PhoBERT + heuristic
    fallback) passed in as `analyzer` (e.g. pipeline.sentiment_analyzer).

    When `org_detector` is provided, entity detection (target organization) is
    also run per item and its result is stored on the item as `org_detected`,
    `matched_org` and `org_confidence`. This mirrors the pipeline's
    `combined_ai_res` and gives the alert decision the data it needs to
    evaluate the project's alert policy (NEGATIVE + confidence >= threshold +
    target org detected). If `org_detector` is None the item's `org_detected`
    stays None and the alert decision falls back to running detection itself.

    Duplicate contents are analyzed ONCE per run (cached) to avoid
    unnecessary model inference.

    A failure in one item is isolated (recorded in item_errors) and does
    NOT abort the rest of the file.

    Returns a result dict with status/error_code/error_message/posts/items/
    summary/item_errors.
    """
    name = filename or ""
    if not name.lower().endswith(".txt"):
        return _error_result(INVALID_FILE, "File phải có định dạng .txt.")

    try:
        text = decode_bytes(raw)
    except TxtParseError as exc:
        return _error_result(exc.code, exc.message)

    try:
        posts = parse_txt(text)
    except TxtParseError as exc:
        return _error_result(exc.code, exc.message)
    except Exception as exc:
        return _error_result(PARSE_ERROR, f"Lỗi parse không mong đợi: {type(exc).__name__}: {exc}")

    items = flatten_posts(posts)
    analyzed_items: List[Dict[str, Any]] = []
    item_errors: List[Dict[str, Any]] = []
    sentiment_cache: Dict[str, Dict[str, Any]] = {}

    total = len(items)
    for idx, item in enumerate(items):
        if progress_cb is not None:
            progress_cb(idx + 1, total)

        entry = {
            "type": item["type"],
            "post_id": item["post_id"],
            "url": item["url"],
            "username": item["username"],
            "content": item["content"],
            "sentiment": None,
            "confidence": None,
            "analyzer_type": None,
            "sentiment_positive": None,
            "sentiment_negative": None,
            "sentiment_neutral": None,
            "org_detected": None,
            "matched_org": None,
            "org_confidence": None,
            "error": None,
        }

        content = (item["content"] or "").strip()
        if not content:
            entry["error"] = "Nội dung rỗng - bỏ qua phân tích."
            item_errors.append({"index": idx, "code": PARSE_ERROR, "message": entry["error"]})
            analyzed_items.append(entry)
            continue

        # Entity detection (target org) is part of the analysis so the alert
        # decision can reuse the SAME detection result. It is deterministic on
        # the content, so it runs for both fresh and cached sentiment items.
        if org_detector is not None:
            det = org_detector.detect(content)
            entry["org_detected"] = bool(det.get("org_detected", False))
            entry["matched_org"] = det.get("matched_org")
            entry["org_confidence"] = float(det.get("confidence", 0.0) or 0.0)

        cached = sentiment_cache.get(content)
        if cached is not None:
            entry.update(cached)
            analyzed_items.append(entry)
            continue

        try:
            res = analyzer.analyze(content)
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            item_errors.append({"index": idx, "code": ANALYSIS_ERROR, "message": entry["error"]})
            analyzed_items.append(entry)
            continue

        if res is None:
            entry["error"] = "Không phân tích được nội dung."
            item_errors.append({"index": idx, "code": ANALYSIS_ERROR, "message": entry["error"]})
            analyzed_items.append(entry)
            continue

        entry["sentiment"] = res.get("label", "NEUTRAL")
        entry["confidence"] = float(res.get("confidence", 0.0) or 0.0)
        entry["analyzer_type"] = res.get("analyzer_type")
        entry["sentiment_positive"] = res.get("sentiment_positive")
        entry["sentiment_negative"] = res.get("sentiment_negative")
        entry["sentiment_neutral"] = res.get("sentiment_neutral")
        analyzed_items.append(entry)

        sentiment_cache[content] = {
            "sentiment": entry["sentiment"],
            "confidence": entry["confidence"],
            "analyzer_type": entry["analyzer_type"],
            "sentiment_positive": entry["sentiment_positive"],
            "sentiment_negative": entry["sentiment_negative"],
            "sentiment_neutral": entry["sentiment_neutral"],
        }

    return {
        "status": SUCCESS,
        "error_code": None,
        "error_message": None,
        "posts": posts,
        "items": analyzed_items,
        "summary": _build_summary(posts, analyzed_items, item_errors),
        "item_errors": item_errors,
    }
