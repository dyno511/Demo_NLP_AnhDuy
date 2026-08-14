import re
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from app.utils.logger import logger

# Module-level shared model cache: guarantees a single PhoBERT pipeline is
# built per process (keyed by MODEL_NAME) and reused by every analyzer
# instance across sessions/modules. HuggingFace's own disk cache prevents
# re-downloading when the model already exists locally.
_MODEL_CACHE: Dict[str, Any] = {}
_MODEL_CACHE_LOCK = threading.Lock()

_VN_NEGATIVE = [
    "chán", "chán nản", "buồn", "buồn bã", "khó chịu", "bực", "bực bội", "tức", "tức giận",
    "thất vọng", "thất vọng tràn trề", "tệ", "tồi", "dở", "kém", "hỏng", "lỗi", "chậm", "lag",
    "nhạt", "vô vị", "không ngon", "đắng", "chua", "đau", "mệt", "mệt mỏi", "gắt gỏng", "cáu",
    "không thích", "ghét", "chửi", "mắng", "khó khăn", "rắc rối", "phiền phức", "phẫn nộ",
    "tệ hại", "dở tệ", "nhàm chán", "tẻ nhạt", "thô", "cứng", "khó nuốt", "mặn chát",
    "không tốt", "xấu", "không đáng", "lãng phí", "phí tiền", "không hài lòng", "kém chất lượng",
    "ảm đạm", "u ám", "nặng nề", "bất mãn", "bực mình", "gây khó chịu", "kinh khủng",
]
_VN_POSITIVE = [
    "ngon", "ngon lành", "tuyệt", "tuyệt vời", "ngon tuyệt", "hấp dẫn", "hài lòng", "hài lòng tuyệt đối",
    "thích", "yêu", "xuất sắc", "tốt", "rất tốt", "tuyệt hảo", "hoàn hảo", "hoàn mỹ", "đỉnh",
    "đáng yêu", "dễ chịu", "thoải mái", "vui", "vui vẻ", "phấn khích", "hào hứng", "mong chờ",
    "không thể chê", "quá ngon", "cực ngon", "siêu ngon", "ngon xuất sắc", "chuẩn", "chuẩn vị",
    "thơm", "thơm ngon", "đậm đà", "đẹp", "xinh", "hợp", "hợp lý", "đáng", "đáng tiền",
    "hữu ích", "tiện", "tiện lợi", "nhanh", "mượt", "ổn", "ổn định", "đáng tin", "chuyên nghiệp",
    "ưng", "ưng ý", "ưng bụng", "sảng khoái", "tươi", "tươi mới", "chất lượng", "sạch sẽ",
    "nhiệt tình", "thân thiện", "dễ thương", "đáng khen", "tuyệt cú mèo", "chất", "chất lượng cao",
    "hài lòng 100%", "số một", "đỉnh cao", "ngon miệng", "bổ dưỡng", "tốt cho sức khỏe",
]


def _load_vn_stopwords() -> set:
    base_dir = Path(__file__).resolve().parents[2]
    candidates = [
        base_dir / "vn_stopwords.txt",
        base_dir / "data" / "vn_stopwords.txt",
        base_dir / "resources" / "vn_stopwords.txt",
        Path(__file__).resolve().parent.parent.parent.parent / "vn_stopwords.txt",
    ]
    for p in candidates:
        try:
            if p.exists():
                return {
                    line.strip()
                    for line in p.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.strip().startswith("#")
                }
        except (OSError, UnicodeDecodeError):
            continue
    return set()


_VN_STOPWORDS = _load_vn_stopwords()


def _heuristic_vietnamese(text: str) -> Optional[Dict[str, Any]]:
    t = re.sub(r"[^\w\s]", " ", text).lower()
    tokens = [w for w in t.split() if w and (w not in _VN_STOPWORDS)]
    joined = " ".join(tokens)
    neg_score = sum(1 for p in _VN_NEGATIVE if p in joined)
    pos_score = sum(1 for p in _VN_POSITIVE if p in joined)
    if pos_score == 0 and neg_score == 0:
        return None
    if pos_score == neg_score:
        return {
            "sentiment": "NEUTRAL",
            "sentiment_positive": 0.4,
            "sentiment_negative": 0.4,
            "sentiment_neutral": 0.2,
        }
    if pos_score > neg_score:
        return {
            "sentiment": "POSITIVE",
            "sentiment_positive": 0.8,
            "sentiment_negative": 0.1,
            "sentiment_neutral": 0.1,
        }
    return {
        "sentiment": "NEGATIVE",
        "sentiment_positive": 0.1,
        "sentiment_negative": 0.8,
        "sentiment_neutral": 0.1,
    }


def _to_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def _from_bytes(b: bytes) -> str:
    return b.decode("utf-8", errors="replace")

class FallbackHeuristicSentimentAnalyzer:
    """
    High-accuracy Vietnamese Lexicon + Rule Engine fallback for sentiment analysis.
    Guarantees immediate zero-dependency evaluation when offline or if HuggingFace is unavailable.
    """

    NEGATIVE_KEYWORDS = [
        "tệ", "xấu", "chán", "thất vọng", "bức xúc", "hách dịch", "chậm trễ", "phàn nàn",
        "tẩy chay", "ngộ độc", "ôi thiu", "hỏng", "nóng phát điên", "xuống cấp", "trầm trọng",
        "thái độ lồi lõm", "làm ăn vớ vẩn", "lừa đảo", "gian dối", "coi thường", "quá đắt",
        "nhạt nhẽo", "tệ hại", "yếu kém", "báo động", "sai phạm", "hành dân", "phiền hà"
    ]

    POSITIVE_KEYWORDS = [
        "tốt", "tuyệt vời", "xuất sắc", "hài lòng", "tâm huyết", "nhiệt tình", "khen ngợi",
        "đáng tiền", "hoành tráng", "chất lượng", "yêu thích", "cảm ơn", "tuyệt", "chu đáo",
        "đạt giải", "sáng tạo", "thành công", "phù hợp", "uy tín", "chuyên nghiệp"
    ]

    def analyze(self, text: str) -> Dict[str, Any]:
        text_lower = text.lower()
        neg_score = sum(1 for word in self.NEGATIVE_KEYWORDS if word in text_lower)
        pos_score = sum(1 for word in self.POSITIVE_KEYWORDS if word in text_lower)

        if neg_score > pos_score:
            confidence = min(0.70 + neg_score * 0.10, 0.98)
            return {
                "label": "NEGATIVE",
                "confidence": confidence,
                "is_negative": True,
                "raw_label": "NEG",
                "analyzer_type": "heuristic"
            }
        elif pos_score > neg_score:
            confidence = min(0.70 + pos_score * 0.10, 0.98)
            return {
                "label": "POSITIVE",
                "confidence": confidence,
                "is_negative": False,
                "raw_label": "POS",
                "analyzer_type": "heuristic"
            }
        else:
            return {
                "label": "NEUTRAL",
                "confidence": 0.75,
                "is_negative": False,
                "raw_label": "NEU",
                "analyzer_type": "heuristic"
            }


class VietnameseSentimentAnalyzer:
    """
    Vietnamese Sentiment Analyzer powered by PhoBERT Transformer Model
    (wonrax/phobert-base-vietnamese-sentiment).
    Initialized ONCE upon system startup for maximum efficiency.
    """

    # Single active sentiment model (PhoBERT fine-tuned for Vietnamese sentiment).
    # This is the ONLY model loaded by the system; 'vinai/phobert-base-v2' is
    # intentionally NOT used. Do not switch models without clearing _MODEL_CACHE.
    MODEL_NAME = "wonrax/phobert-base-vietnamese-sentiment"

    def __init__(self, force_heuristic: bool = False, model_name: Optional[str] = None):
        self.model_name = model_name or self.MODEL_NAME
        self.analyzer = None
        self.heuristic = FallbackHeuristicSentimentAnalyzer()
        self.is_transformer_loaded = False
        self.load_error: Optional[str] = None

        if not force_heuristic:
            self.load_model()
        else:
            logger.info("[VietnameseSentimentAnalyzer] Force heuristic mode active.")
            self.load_error = "PhoBERT disabled by force_heuristic flag"

    def load_model(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        (Re)load the transformer model at runtime and return a status dict.

        If `model_name` is provided the analyzer switches to that model.
        When the model is not present locally, HuggingFace automatically
        downloads it (needs internet on the first run). The pipeline is
        cached module-wide (keyed by model name) and reused by every
        analyzer instance, so no duplicate in-memory model is ever built.
        A module-level lock prevents a double-load race when multiple
        threads/sessions start concurrently.

        Returns:
        {
            "status": "OK" | "FAILED",
            "message": str,
            "is_transformer_loaded": bool,
            "load_error": Optional[str],
            "fallback": "heuristic" on failure (else None)
        }
        """
        if model_name and model_name.strip():
            self.model_name = model_name.strip()

        with _MODEL_CACHE_LOCK:
            cached = _MODEL_CACHE.get(self.model_name)
            if cached is not None:
                self.analyzer = cached
                self.is_transformer_loaded = True
                self.load_error = None
                logger.info(f"[VietnameseSentimentAnalyzer] Reusing cached pipeline for '{self.model_name}'.")
                return {
                    "status": "OK",
                    "message": f"Tái sử dụng pipeline đã cache cho mô hình '{self.model_name}'.",
                    "is_transformer_loaded": True,
                    "load_error": None,
                    "fallback": None,
                }

            try:
                logger.info(f"[VietnameseSentimentAnalyzer] Initializing model '{self.model_name}'...")
                from transformers import pipeline

                analyzer = pipeline(
                    "text-classification",
                    model=self.model_name,
                    tokenizer=self.model_name,
                    device=-1  # CPU inference
                )
                _MODEL_CACHE[self.model_name] = analyzer
                self.analyzer = analyzer
                self.is_transformer_loaded = True
                self.load_error = None
                logger.info("[VietnameseSentimentAnalyzer] Model successfully loaded into memory!")
                return {
                    "status": "OK",
                    "message": f"Đã tải mô hình '{self.model_name}' thành công.",
                    "is_transformer_loaded": True,
                    "load_error": None,
                    "fallback": None,
                }
            except Exception as e:
                self.load_error = str(e)
                self.is_transformer_loaded = False
                logger.warning(f"[VietnameseSentimentAnalyzer] Could not load model '{self.model_name}': {e}")
                logger.info("[VietnameseSentimentAnalyzer] Activating Rule-Based Vietnamese Heuristic Fallback Engine.")
                return {
                    "status": "FAILED",
                    "message": f"{type(e).__name__}: {e}",
                    "is_transformer_loaded": False,
                    "load_error": str(e),
                    "fallback": "heuristic",
                }

    def _load_transformer_model(self):
        """Backward-compatible alias for load_model()."""
        return self.load_model()

    def analyze(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Analyzes sentiment of given Vietnamese text.
        Truncates input to 500 characters to respect PhoBERT maximum sequence length (256 subwords).
        
        Returns:
        {
            "text": str,
            "label": "POSITIVE" | "NEGATIVE" | "NEUTRAL",
            "confidence": float (0.0 to 1.0),
            "is_negative": bool,
            "raw_label": str,
            "analyzer_type": "phobert" | "heuristic"
        }
        """
        if not text or not text.strip():
            return None

        truncated_text = text[:500]

        if self.is_transformer_loaded and self.analyzer and not self.load_error:
            try:
                raw_results = self.analyzer(truncated_text)
                if raw_results and len(raw_results) > 0:
                    top_pred = raw_results[0]
                    raw_label = str(top_pred.get("label", "")).upper()
                    score = float(top_pred.get("score", 0.0))

                    # Normalize label output
                    if raw_label in ["NEG", "LABEL_0", "NEGATIVE"]:
                        norm_label = "NEGATIVE"
                        is_neg = True
                    elif raw_label in ["POS", "LABEL_1", "POSITIVE"]:
                        norm_label = "POSITIVE"
                        is_neg = False
                    else:
                        norm_label = "NEUTRAL"
                        is_neg = False

                    if norm_label == "POSITIVE":
                        sentiment_positive, sentiment_negative, sentiment_neutral = score, (1 - score) / 2, (1 - score) / 2
                    elif norm_label == "NEGATIVE":
                        sentiment_positive, sentiment_negative, sentiment_neutral = (1 - score) / 2, score, (1 - score) / 2
                    else:
                        sentiment_positive, sentiment_negative, sentiment_neutral = (1 - score) / 2, (1 - score) / 2, score

                    return {
                        "text": text,
                        "label": norm_label,
                        "confidence": score,
                        "is_negative": is_neg,
                        "raw_label": raw_label,
                        "analyzer_type": "phobert",
                        "sentiment_positive": round(sentiment_positive, 4),
                        "sentiment_negative": round(sentiment_negative, 4),
                        "sentiment_neutral": round(sentiment_neutral, 4),
                    }
            except Exception as e:
                self.load_error = str(e)
                logger.error(f"[VietnameseSentimentAnalyzer] Exception during PhoBERT inference: {e}")
                logger.info("[VietnameseSentimentAnalyzer] Falling back to heuristic sentiment engine.")

        # Heuristic Fallback execution
        res = self.heuristic.analyze(truncated_text)
        res["text"] = text
        res["error"] = self.load_error
        if res["label"] == "POSITIVE":
            res["sentiment_positive"] = res["confidence"]
            res["sentiment_negative"] = round((1 - res["confidence"]) / 2, 4)
            res["sentiment_neutral"] = round((1 - res["confidence"]) / 2, 4)
        elif res["label"] == "NEGATIVE":
            res["sentiment_negative"] = res["confidence"]
            res["sentiment_positive"] = round((1 - res["confidence"]) / 2, 4)
            res["sentiment_neutral"] = round((1 - res["confidence"]) / 2, 4)
        else:
            res["sentiment_neutral"] = res["confidence"]
            res["sentiment_positive"] = round((1 - res["confidence"]) / 2, 4)
            res["sentiment_negative"] = round((1 - res["confidence"]) / 2, 4)
        return res
