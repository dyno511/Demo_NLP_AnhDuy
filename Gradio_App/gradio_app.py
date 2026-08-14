"""
AI Social Listening System - Gradio Web Dashboard.

Replaces the Streamlit UI (web_app.py) with an equivalent Gradio Blocks UI.
All business logic stays in app/ and is reused as-is (pipeline, AI engine,
alerting, discovery, TXT parser, SQLite repository).
"""

import json
import os
import re
import argparse
import time
import threading
from datetime import datetime

import gradio as gr
import pandas as pd
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from fastapi.concurrency import run_in_threadpool

from config import Config
from app.db.repository import Repository
from app.pipeline.pipeline import SocialListeningPipeline
from app.pipeline.scheduler import PipelineScheduler
from app.ai.entity_detector import OrganizationDetector
from app.discovery.service import DiscoveryService
from app.db.source_registry import SourceRegistry
from app.alert.service import AlertService, evaluate_alert_eligibility, build_alert_payload
from app.parser.txt_parser import analyze_txt
from app.utils.logger import logger


class AppState:
    """Application-wide state holder (equivalent of Streamlit session state)."""

    def __init__(self):
        self.pipeline = None
        self.scheduler = None
        self.repo = None
        self.source_registry = None
        self.discovery_status = {
            "status": "NOT_RUN",
            "error": None,
            "query_count": 0,
            "candidate_count": 0,
            "platform_counts": {},
        }
        self.discovered_sources = []
        self.txt_analysis = None
        self.txt_analysis_file = None
        self.source_limit = 10
        self.config_message = ""
        self.extension_last_ingest = None
        self.extension_received_preview = []


def build_state() -> AppState:
    state = AppState()
    logger.info("Khởi tạo Pipeline AI (PhoBERT) & Hệ thống Social Listening...")
    state.pipeline = SocialListeningPipeline()
    state.scheduler = PipelineScheduler(pipeline=state.pipeline)
    state.repo = Repository()
    state.source_registry = SourceRegistry(state.repo)
    return state


APP = build_state()


# ---------------------------------------------------------------------------
# Helper HTML builders
# ---------------------------------------------------------------------------

def metric_card(label: str, value, color: str = "#0F172A") -> str:
    return f"""
    <div style="background-color:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;
                padding:1rem;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
        <div style="font-size:0.8rem;color:#64748B;text-transform:uppercase;letter-spacing:0.5px;">{label}</div>
        <div style="font-size:1.7rem;font-weight:700;color:{color};">{value}</div>
    </div>"""


def overview_cards(stats: dict) -> str:
    return (
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.8rem;">'
        + metric_card("Tổng Số Mẫu Quét", stats["total_items"])
        + metric_card("Số Đề Cập Tổ Chức", stats["org_mentions"])
        + metric_card("Phát Hiện Tiêu Cực", stats["negative_items"], "#EF4444")
        + metric_card("Cảnh Báo Đã Gửi", stats["alerts_sent"], "#F59E0B")
        + "</div>"
    )


def txt_summary_cards(summary: dict) -> str:
    cards = [
        ("Tổng Số Bài Viết", summary.get("total_posts", 0)),
        ("Tổng Số Bình Luận", summary.get("total_comments", 0)),
        ("Tổng Số Mẫu Phân Tích", summary.get("total_samples", 0)),
        ("Confidence Trung Bình", f"{summary.get('mean_confidence', 0.0) * 100:.1f}%"),
    ]
    cards += [
        ("Positive", summary.get("positive", 0), "#16A34A"),
        ("Negative", summary.get("negative", 0), "#EF4444"),
        ("Neutral", summary.get("neutral", 0), "#64748B"),
        ("Mẫu Lỗi", summary.get("item_errors", 0), "#F59E0B"),
    ]
    html = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.8rem;">'
    for card in cards:
        if len(card) == 3:
            label, value, color = card
        else:
            label, value = card
            color = "#0F172A"
        html += metric_card(label, value, color)
    return html + "</div>"


def platform_counts_html(counts: dict) -> str:
    labels = [
        ("📘 Facebook", "facebook"),
        ("🎵 TikTok", "tiktok"),
        ("▶️ YouTube", "youtube"),
        ("📸 Instagram", "instagram"),
        ("🤖 Reddit", "reddit"),
        ("💬 Forum", "forum"),
        ("📰 News", "news"),
        ("🌐 Public Web", "public_web"),
    ]
    return " | ".join(f"**{label}:** {counts.get(key, 0)}" for label, key in labels)


# ---------------------------------------------------------------------------
# Tab 1: Overview
# ---------------------------------------------------------------------------

def load_overview() -> tuple:
    stats = APP.repo.get_system_stats()
    return (
        overview_cards(stats),
        f"**Lần quét cuối:** `{stats['last_scan']}`",
        f"**Kênh cảnh báo hoạt động:** `{Config.ALERT_CHANNEL.upper()}`",
    )


def load_overview_info() -> tuple:
    return (
        f"**Tổ chức đang theo dõi:** `{Config.TARGET_ORGANIZATION}`",
        f"**Danh sách Aliases:** `{', '.join(Config.TARGET_ALIASES)}`",
    )


# ---------------------------------------------------------------------------
# Tab 2: Configuration
# ---------------------------------------------------------------------------

def save_config(
    target_org: str,
    aliases_str: str,
    platform: str,
    threshold: float,
    interval: int,
    alert_channel: str,
    telegram_token: str,
    telegram_chat_id: str,
    source_limit: int,
) -> tuple:
    Config.TARGET_ORGANIZATION = (target_org or "").strip()
    Config.TARGET_ALIASES = [a.strip() for a in (aliases_str or "").split(",") if a.strip()]
    Config.SOCIAL_PLATFORM = platform
    Config.SENTIMENT_THRESHOLD = threshold
    Config.SCHEDULE_INTERVAL_MINUTES = interval
    Config.ALERT_CHANNEL = alert_channel
    Config.TELEGRAM_BOT_TOKEN = telegram_token
    Config.TELEGRAM_CHAT_ID = telegram_chat_id
    APP.source_limit = source_limit

    APP.pipeline.org_detector = OrganizationDetector(
        target_org=Config.TARGET_ORGANIZATION,
        aliases=Config.TARGET_ALIASES,
    )
    APP.pipeline.alert_service = AlertService(alert_channel)

    message = (
        "✅ Đã lưu cấu hình hệ thống. "
        "Để khám phá nguồn công khai, hãy vào tab '🚀 Kích Hoạt Quét Dữ Liệu' và bấm '🔎 Chạy Discovery'."
    )
    APP.config_message = message
    return message


# ---------------------------------------------------------------------------
# Tab 3: Scan / Discovery
# ---------------------------------------------------------------------------

def run_discovery() -> tuple:
    if not Config.TARGET_ORGANIZATION.strip():
        APP.discovery_status = {
            "status": "FAILED",
            "error": "Chưa có Target Org. Vui lòng nhập Tổ chức mục tiêu trong tab '⚙️ Cấu Hình' và bấm '💾 Lưu Cấu Hình' trước khi chạy Discovery. (MISSING_TARGET_ORG)",
            "query_count": 0,
            "candidate_count": 0,
            "platform_counts": {},
        }
        return _discovery_outputs()
    try:
        discovery_service = DiscoveryService(APP.source_registry)
        APP.discovered_sources = discovery_service.discover(
            Config.TARGET_ORGANIZATION,
            Config.TARGET_ALIASES,
            APP.source_limit,
        )
        APP.discovery_status = discovery_service.get_last_run()
    except Exception as exc:
        APP.discovery_status = {
            "status": "FAILED",
            "error": f"{type(exc).__name__}: {exc}",
            "query_count": 0,
            "candidate_count": 0,
            "platform_counts": {},
        }
        APP.discovered_sources = []
    return _discovery_outputs()


def _discovery_outputs() -> tuple:
    run = APP.discovery_status
    discovered = APP.discovered_sources

    status_color = "green" if run["status"] in {"SUCCESS", "PARTIAL_SUCCESS"} else (
        "red" if run["status"] in {"FAILED", "EMPTY_RESULT"} else "orange"
    )
    parts = [f"**Discovery Status:** :{status_color}[{run['status']}]"]
    if run.get("error"):
        parts.append(f"Thông báo Discovery: {run['error']}")
    if not Config.TARGET_ORGANIZATION.strip():
        parts.append("⚠️ Chưa có Target Org — cần lưu cấu hình trước.")
    status_html = "<br>".join(parts) if parts else ""

    counts = platform_counts_html(run.get("platform_counts", {}))
    metrics = (
        f"**Total Extracted Results:** {run.get('search_results', 0)}  |  "
        f"**Unique Candidate Sources:** {run.get('candidate_count', 0)}  |  "
        f"**Selected Monitoring Sources (Top-N):** {len(discovered)}"
    )

    if discovered:
        rows = [{
            "Rank": x.get("rank", idx + 1),
            "Platform": x.get("platform", "public_web").upper(),
            "Source Name": x.get("source_name") or x.get("name", ""),
            "Source Type": x.get("source_type", ""),
            "URL": x.get("url", ""),
            "Relevance": x.get("relevance_score", 0.0),
            "Status": x.get("status", ""),
        } for idx, x in enumerate(discovered)]
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame(columns=["Rank", "Platform", "Source Name", "Source Type", "URL", "Relevance", "Status"])
    return status_html, metrics, counts, df


def run_scan() -> str:
    logger.info("Kích hoạt chu kỳ quét thủ công từ Gradio UI...")
    summary = APP.pipeline.run_cycle()
    return (
        f"✅ Đã hoàn thành chu kỳ quét trong {summary['duration_seconds']}s!\n\n"
        f"```json\n{json.dumps(summary, ensure_ascii=False, indent=2)}\n```"
    )


# ---------------------------------------------------------------------------
# Tab 4: AI Test Bench
# ---------------------------------------------------------------------------

def analyze_testbench(text: str) -> tuple:
    if not text or not text.strip():
        return (
            "⚠️ Vui lòng nhập văn bản để phân tích.",
            "",
            "",
        )

    det = APP.pipeline.org_detector.detect(text)
    sent = APP.pipeline.sentiment_analyzer.analyze(text)

    if det["org_detected"]:
        entity_html = (
            f"### 🏢 Nhận Diện Tổ Chức\n\n"
            f"**Phát hiện tổ chức:** `{det['matched_org']}` "
            f"(Độ tự tin: {det['confidence'] * 100:.0f}%)"
        )
    else:
        entity_html = "### 🏢 Nhận Diện Tổ Chức\n\n⚠️ Không tìm thấy đề cập đến tổ chức mục tiêu."

    if sent:
        label = sent["label"]
        score = sent["confidence"]
        emoji = "❌" if label == "NEGATIVE" else ("✅" if label == "POSITIVE" else "ℹ️")
        sentiment_html = (
            f"### 🎭 Phân Tích Cảm Xúc\n\n"
            f"{emoji} **Nhãn Cảm Xúc:** `{label}` (Độ tự tin: {score * 100:.1f}%)"
        )
    else:
        sentiment_html = "### 🎭 Phân Tích Cảm Xúc\n\n⚠️ Không phân tích được văn bản."

    decision_html = ""
    if det["org_detected"] and sent:
        should_alert = sent.get("is_negative") and (sent["confidence"] >= Config.SENTIMENT_THRESHOLD)
        if should_alert:
            decision_html = (
                f"🚨 **HỆ THỐNG RA QUYẾT ĐỊNH: ĐỦ ĐIỀU KIỆN KÍCH HOẠT CẢNH BÁO!** "
                f"(Ngưỡng tin cậy {Config.SENTIMENT_THRESHOLD * 100:.0f}%)"
            )
            alert_payload = {
                "target_organization": det.get("matched_org") or Config.TARGET_ORGANIZATION,
                "sentiment": sent.get("label", "NEGATIVE"),
                "confidence": sent.get("confidence", 0.0),
                "text": text,
                "source": "AI Test Bench Playground",
                "post_url": "https://facebook.com/test_bench_playground",
                "author": "Tester",
                "detected_at": datetime.now().isoformat(),
            }
            is_telegram_chosen = Config.ALERT_CHANNEL.lower().strip() == "telegram"
            if is_telegram_chosen and (not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID):
                decision_html += (
                    "\n\n⚠️ Cảnh báo Telegram chưa được gửi: Bot Token hoặc Chat ID chưa cấu hình. "
                    "(TELEGRAM_NOT_CONFIGURED)"
                )
            else:
                try:
                    success = APP.pipeline.alert_service.dispatch_alert(alert_payload)
                    if success:
                        decision_html += "\n\n✅ Gửi cảnh báo thành công! (TELEGRAM_SEND_SUCCESS / SEND_SUCCESS)"
                    else:
                        decision_html += (
                            "\n\n❌ Gửi cảnh báo thất bại. Vui lòng kiểm tra lại cấu hình API / kết nối mạng. "
                            "(TELEGRAM_SEND_FAILED)"
                        )
                except Exception as exc:
                    decision_html += f"\n\n❌ Gửi cảnh báo gặp sự cố: {exc} (TELEGRAM_SEND_FAILED)"
        else:
            decision_html = (
                "ℹ️ **HỆ THỐNG RA QUYẾT ĐỊNH: KHÔNG GỬI CẢNH BÁO.** "
                "(Không thỏa mãn đủ điều kiện: ALERT_NOT_TRIGGERED)"
            )

    return entity_html, sentiment_html, decision_html


# ---------------------------------------------------------------------------
# Tab 5: History
# ---------------------------------------------------------------------------

def load_history() -> tuple:
    items = APP.repo.get_recent_items(limit=100)
    alerts = APP.repo.get_recent_alerts(limit=50)
    if items:
        df_items = pd.DataFrame(items)[
            ["item_id", "source", "author", "text", "org_detected", "detected_org_name",
             "sentiment_label", "confidence", "alert_sent", "processed_at"]
        ]
    else:
        df_items = pd.DataFrame(columns=["item_id", "source", "author", "text", "org_detected",
                                         "detected_org_name", "sentiment_label", "confidence",
                                         "alert_sent", "processed_at"])
    if alerts:
        df_alerts = pd.DataFrame(alerts)[
            ["id", "channel", "target_org", "sentiment_label", "confidence", "text", "post_url", "sent_at"]
        ]
    else:
        df_alerts = pd.DataFrame(columns=["id", "channel", "target_org", "sentiment_label",
                                          "confidence", "text", "post_url", "sent_at"])
    return df_items, df_alerts


# ---------------------------------------------------------------------------
# Tab 6: TXT Analysis
# ---------------------------------------------------------------------------

TXT_COLUMNS = ["Type", "Bài", "Username", "Nội dung", "Sentiment", "Confidence",
               "Pos", "Neg", "Neu", "Engine", "URL"]


def _txt_rows(items) -> list:
    rows = []
    for item in items:
        rows.append({
            "Type": item["type"],
            "Bài": item["post_id"],
            "Username": item["username"] if item["username"] else "—",
            "Nội dung": item["content"],
            "Sentiment": item["sentiment"] if item["sentiment"] else "LỖI",
            "Confidence": item["confidence"] if item["confidence"] is not None else 0.0,
            "Pos": item.get("sentiment_positive"),
            "Neg": item.get("sentiment_negative"),
            "Neu": item.get("sentiment_neutral"),
            "Engine": "AI" if item.get("analyzer_type") == "phobert" else (
                "Heuristic" if item.get("analyzer_type") else "—"),
            "URL": item["url"] if item["url"] else "—",
        })
    return rows


def _empty_txt_df() -> pd.DataFrame:
    return pd.DataFrame(columns=TXT_COLUMNS)


def analyze_txt_file(file, progress=gr.Progress()) -> tuple:
    if file is None:
        return "⚠️ Vui lòng chọn file `.txt` trước khi phân tích. (FILE_NOT_SELECTED)", "", "", _empty_txt_df()

    # Gradio versions differ: type="filepath" -> str path, type="binary" ->
    # bytes (v6+) or (bytes, filename) tuple (v4/v5). Handle them all.
    if isinstance(file, bytes):
        binary, filename = file, "upload.txt"
    elif isinstance(file, str):
        binary = open(file, "rb").read()
        filename = os.path.basename(file)
    elif isinstance(file, tuple):
        binary, filename = file
    else:
        binary, filename = None, None

    if not binary:
        return "⚠️ Vui lòng chọn file `.txt` trước khi phân tích. (FILE_NOT_SELECTED)", "", "", _empty_txt_df()

    APP.txt_analysis = None
    APP.txt_analysis_file = None

    def _update_progress(done, total):
        progress(done / total if total else 1.0, desc=f"Đang phân tích cảm xúc {done}/{total} mẫu...")

    try:
        result = analyze_txt(
            binary,
            filename,
            APP.pipeline.sentiment_analyzer,
            org_detector=APP.pipeline.org_detector,
            progress_cb=_update_progress,
        )
    except Exception as exc:
        result = {
            "status": "ERROR",
            "error_code": "ANALYSIS_ERROR",
            "error_message": f"{type(exc).__name__}: {exc}",
            "posts": [], "items": [], "summary": {}, "item_errors": [],
        }

    APP.txt_analysis = result
    APP.txt_analysis_file = filename
    return _txt_outputs()


def _txt_outputs() -> tuple:
    analysis = APP.txt_analysis
    if analysis is None or analysis.get("status") == "ERROR":
        if analysis is None:
            return "Chưa có kết quả phân tích.", "", "", _empty_txt_df()
        message = analysis.get("error_message", "Không phân tích được file.")
        return f"❌ Không thể phân tích file: {message} ({analysis.get('error_code', 'ANALYSIS_ERROR')})", "", "", _empty_txt_df()

    summary = analysis["summary"]
    warnings = []
    if summary.get("item_errors", 0) > 0:
        warnings.append(
            f"⚠️ Có {summary['item_errors']} mẫu bị lỗi phân tích (đã ghi nhận lỗi riêng). "
            f"Các mẫu còn lại vẫn được xử lý bình thường."
        )
    heuristic_count = sum(1 for it in analysis["items"] if it.get("analyzer_type") == "heuristic")
    if heuristic_count:
        warnings.append(
            f"⚠️ PhoBERT không khả dụng (không tải được model), "
            f"{heuristic_count}/{summary['total_samples']} mẫu được phân tích bằng bộ từ điển heuristic — "
            f"độ chính xác thấp hơn model AI."
        )
    message = "✅ Đã phân tích xong file!" + ("\n\n" + "\n\n".join(warnings) if warnings else "")
    summary_html = f"### 📊 Tổng Quan Kết Quả\n\n{txt_summary_cards(summary)}"
    count_label = f"**Chi tiết kết quả ({len(analysis['items'])}/{summary['total_samples']} mẫu):**"
    return message, summary_html, count_label, _filter_txt("Tất cả", True)


def _filter_txt(filter_option: str, sort_negative: bool) -> pd.DataFrame:
    analysis = APP.txt_analysis
    if analysis is None or analysis.get("status") != "SUCCESS" or not analysis.get("items"):
        return _empty_txt_df()

    df = pd.DataFrame(_txt_rows(analysis["items"]))
    if filter_option == "Negative":
        df = df[df["Sentiment"] == "NEGATIVE"]
    elif filter_option == "Positive":
        df = df[df["Sentiment"] == "POSITIVE"]
    elif filter_option == "Neutral":
        df = df[df["Sentiment"] == "NEUTRAL"]
    elif filter_option == "Chỉ bài viết (POST)":
        df = df[df["Type"] == "POST"]
    elif filter_option == "Chỉ bình luận (COMMENT)":
        df = df[df["Type"] == "COMMENT"]

    if sort_negative:
        sentiment_rank = {"NEGATIVE": 0, "POSITIVE": 1, "NEUTRAL": 2, "LỖI": 3}
        df = df.copy()
        df["__rank"] = df["Sentiment"].map(lambda s: sentiment_rank.get(s, 4))
        df = df.sort_values("__rank", kind="stable").drop(columns="__rank")

    return df.reset_index(drop=True)


def txt_count_label() -> str:
    analysis = APP.txt_analysis
    if analysis is None or analysis.get("status") != "SUCCESS":
        return ""
    return f"**Chi tiết kết quả ({len(analysis['items'])} mẫu):**"


def send_txt_alerts() -> str:
    analysis = APP.txt_analysis
    if analysis is None or analysis.get("status") != "SUCCESS" or not analysis.get("items"):
        return "⚠️ Vui lòng upload và phân tích file trước khi gửi cảnh báo. (NOT_ANALYZED)"

    candidates, diagnostics = evaluate_alert_eligibility(
        analysis["items"],
        APP.pipeline.org_detector,
        Config.SENTIMENT_THRESHOLD,
    )

    negative_total = analysis.get("summary", {}).get("negative", 0)
    if not candidates:
        reason_counts = {}
        for diag in diagnostics:
            if diag.get("sentiment") != "NEGATIVE":
                continue
            reason = diag.get("reason")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        reason_labels = {
            "ORG_NOT_DETECTED": "không phát hiện tổ chức mục tiêu",
            "CONFIDENCE_BELOW_THRESHOLD": "confidence dưới ngưỡng",
            "DUPLICATE": "trùng lặp",
            "SENTIMENT_NOT_NEGATIVE": "không phải NEGATIVE",
        }
        breakdown = ", ".join(
            f"{reason_labels[r]} ({reason_counts[r]})"
            for r in ("ORG_NOT_DETECTED", "CONFIDENCE_BELOW_THRESHOLD", "DUPLICATE", "SENTIMENT_NOT_NEGATIVE")
            if reason_counts.get(r)
        )
        msg = (f"ℹ️ Không có nội dung đủ điều kiện cảnh báo "
               f"(NEGATIVE: {negative_total}, đủ điều kiện: 0). (ALERT_NOT_TRIGGERED)")
        if breakdown:
            msg += f" Lý do: {breakdown}."
        return msg

    msg = (f"🚨 Alert đã được kích hoạt: "
           f"NEGATIVE: {negative_total}, đủ điều kiện cảnh báo: {len(candidates)}. (ALERT_TRIGGERED)")

    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        return (msg + f"\n\n⚠️ Có {len(candidates)} cảnh báo đủ điều kiện nhưng Telegram chưa được cấu hình. "
                      f"Vui lòng nhập Bot Token và Chat ID trong tab '⚙️ Cấu Hình'. (TELEGRAM_NOT_CONFIGURED)")

    telegram_service = AlertService("telegram")
    success_count = 0
    failure_count = 0
    for candidate in candidates:
        payload = build_alert_payload(candidate["item"], candidate["detection"], source="File TXT")
        try:
            ok = telegram_service.dispatch_alert(payload)
        except Exception:
            ok = False
        if ok:
            success_count += 1
        else:
            failure_count += 1

    if success_count > 0 and failure_count == 0:
        return msg + f"\n\n✅ Đã gửi {success_count}/{len(candidates)} cảnh báo về Telegram. (TELEGRAM_SEND_SUCCESS)"
    if failure_count > 0 and success_count == 0:
        return (msg + f"\n\n❌ Có {len(candidates)} cảnh báo đủ điều kiện nhưng không gửi được cảnh báo nào. "
                      f"Vui lòng kiểm tra lại cấu hình API / kết nối mạng. (TELEGRAM_SEND_FAILED)")
    return (msg + f"\n\n⚠️ Đã gửi {success_count}/{len(candidates)} cảnh báo, "
                  f"thất bại {failure_count}. (PARTIAL_SEND)")


# ---------------------------------------------------------------------------
# Tab 7: AI Model Manager (auto-load when no model is available)
# ---------------------------------------------------------------------------

def model_status() -> str:
    sa = APP.pipeline.sentiment_analyzer
    engine = "PhoBERT (Transformer)" if sa.is_transformer_loaded else "Heuristic (từ điển)"
    status = "ĐÃ TẢI" if sa.is_transformer_loaded else "CHƯA TẢI → DÙNG HEURISTIC"
    lines = [
        "### 🤖 Trạng Thái Mô Hình AI",
        f"- **Model đang cấu hình:** `{sa.model_name}`",
        f"- **Trạng thái:** `{status}`",
        f"- **Engine đang dùng:** `{engine}`",
    ]
    if sa.load_error:
        lines.append(f"- **Lỗi tải mô hình (nếu có):**\n```text\n{sa.load_error[:500]}\n```")
    return "\n".join(lines)


def load_model_ui(model_name: str) -> tuple:
    if not model_name or not model_name.strip():
        return ("⚠️ Vui lòng nhập Model ID (HuggingFace). Ví dụ: `wonrax/phobert-base-vietnamese-sentiment`",
                model_status())
    model_id = model_name.strip()
    logger.info(f"Đang tải mô hình AI từ HuggingFace: {model_id} (lần đầu có thể mất vài phút)...")
    result = APP.pipeline.sentiment_analyzer.load_model(model_id)
    if result["status"] == "OK":
        message = f"✅ {result['message']} Hệ thống đã chuyển sang engine Transformer."
    else:
        message = (f"❌ Tải mô hình thất bại, hệ thống dùng heuristic thay thế:\n"
                   f"```text\n{result['message'][:500]}\n```")
    return message, model_status()


# ---------------------------------------------------------------------------
# Ingest API: Chrome Extension đẩy nội dung đã quét lên server
# ---------------------------------------------------------------------------

EXTENSION_SOURCE = "extension"
_extension_ingest_lock = threading.Lock()


def _extract_facebook_post_id(url: str) -> str:
    """Lấy post_id từ URL bài viết Facebook (dạng /groups/<id>/posts/<pid>)."""
    if not url:
        return ""
    m = re.search(r"/groups/\d+/(?:posts|permalink)/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"story_fbid=(\d+)", url)
    return m.group(1) if m else ""


def ingest_extension_items(payload: dict) -> dict:
    """
    Nhận JSON từ extension: chuyển thành item (POST + từng COMMENT), chạy
    cùng quy trình như pipeline (dedup → detect org → sentiment → alert → DB),
    ghi vào repository để hiển thị ở tab Lịch sử / Extension.

    Payload: {"source": str, "group_id": str, "items": [{url, postText, comments, commentCount}]}
    """
    raw: list = (payload or {}).get("items") or []
    stats = {
        "status": "OK",
        "received_posts": 0,
        "received_comments": 0,
        "stored_new": 0,
        "duplicates_skipped": 0,
        "alerts_triggered": 0,
        "errors": [],
    }
    now_str = datetime.now().isoformat()
    source_label = (payload or {}).get("source") or "Extension"

    # Bước 1: chuẩn hóa dữ liệu đầu vào -> raw items (POST + COMMENT)
    raw_items = []
    seen_posts = set()
    preview = []
    for post in raw:
        if not isinstance(post, dict):
            continue
        url = (post.get("url") or "").strip()
        if not url:
            continue
        post_id = _extract_facebook_post_id(url) or url
        if post_id in seen_posts:
            continue
        seen_posts.add(post_id)
        post_text = (post.get("postText") or post.get("content") or "").strip()
        comments = post.get("comments")
        if not isinstance(comments, list):
            comments = []
        if post_text or comments:
            stats["received_posts"] += 1
            preview.append({"url": url, "postText": post_text[:300], "comments": comments[:10]})
        if post_text:
            raw_items.append({
                "source": EXTENSION_SOURCE, "post_id": post_id, "post_url": url,
                "author": "POST", "text": post_text, "content_type": "post",
                "created_at": now_str,
            })
        for idx, comment in enumerate(comments):
            text = str(comment or "").strip()
            if not text:
                continue
            author = "Bình luận"
            if ":" in text:
                maybe_author, _, rest = text.partition(":")
                if rest.strip():
                    author = maybe_author.strip()
                    text = rest.strip()
            raw_items.append({
                "source": EXTENSION_SOURCE, "post_id": post_id,
                "comment_id": f"{post_id}_c{idx}", "post_url": url,
                "author": author, "text": text, "content_type": "comment",
                "created_at": now_str,
            })
            stats["received_comments"] += 1

    # Bước 2: xử lý từng item theo đúng quy trình pipeline
    for item in raw_items:
        item_id = APP.repo.generate_item_id(
            item.get("post_id", ""), item.get("comment_id"), item.get("text", "")
        )
        if APP.repo.is_item_processed(item_id):
            stats["duplicates_skipped"] += 1
            continue

        text = item.get("text", "")
        try:
            det = APP.pipeline.org_detector.detect(text)
            sent = APP.pipeline.sentiment_analyzer.analyze(text) or {}
        except Exception as exc:
            stats["errors"].append(f"Phân tích lỗi: {type(exc).__name__}: {exc}")
            continue

        combined = {
            "org_detected": det.get("org_detected", False),
            "matched_org": det.get("matched_org", ""),
            "label": sent.get("label", "NEUTRAL"),
            "confidence": float(sent.get("confidence", 0.0)),
            "is_negative": sent.get("is_negative", False),
        }

        should_alert = (
            combined["org_detected"]
            and combined["is_negative"]
            and combined["confidence"] >= Config.SENTIMENT_THRESHOLD
        )
        alert_sent = False
        if should_alert:
            alert_payload = {
                "target_organization": combined["matched_org"] or Config.TARGET_ORGANIZATION,
                "sentiment": combined["label"],
                "confidence": combined["confidence"],
                "text": text,
                "source": source_label,
                "post_url": item.get("post_url", ""),
                "author": item.get("author", "Anonymous"),
                "detected_at": now_str,
            }
            try:
                alert_sent = APP.pipeline.alert_service.dispatch_alert(alert_payload)
            except Exception as exc:
                alert_sent = False
                stats["errors"].append(f"Dispatch lỗi: {type(exc).__name__}: {exc}")
            if alert_sent:
                stats["alerts_triggered"] += 1
                try:
                    APP.repo.log_alert(
                        item_id=item_id,
                        channel=Config.ALERT_CHANNEL,
                        target_org=combined["matched_org"] or Config.TARGET_ORGANIZATION,
                        sentiment=combined["label"],
                        confidence=combined["confidence"],
                        message_text=text,
                        status="SUCCESS",
                    )
                except Exception:
                    pass

        APP.repo.save_processed_item(item, combined, alert_sent)
        stats["stored_new"] += 1

    APP.extension_last_ingest = {**stats, "time": now_str, "source": source_label}
    APP.extension_received_preview = preview
    return stats


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Max-Age": "3600",
    }


def register_extension_api(app) -> None:
    """
    Gắn endpoint public để extension POST dữ liệu lên.

    Phải gọi trên App thực tế đang serve (kết quả trả về từ demo.launch()).
    Gradio 6 tạo App mới khi launch nên nếu đăng ký trên demo.app trước khi
    launch, route sẽ bị rớt (health 404).
    """
    if app is None or not hasattr(app, "router"):
        logger.warning("Không gắn được Extension Ingest API (app không hợp lệ).")
        return
    prefix = "/api/extension"

    @app.options(f"{prefix}/ingest")
    async def _opts():
        return Response(status_code=204, headers=_cors_headers())

    @app.get(f"{prefix}/ingest")
    async def _get_ingest():
        # Accidental GET (proxy/tunnel có thể đổi POST -> GET): trả thông tin hữu ích
        # thay vì 405 Method Not Allowed khiến extension báo lỗi khó hiểu.
        return JSONResponse({
            "status": "OK",
            "hint": "API này chỉ nhận POST (extension dùng fetch POST). Dữ liệu phải gửi kèm body JSON.",
            "example": '{"source": "AnhDuy AUTO-BOT", "items": [{"url": "...", "postText": "...", "comments": []}]}',
        }, headers=_cors_headers())

    @app.get(f"{prefix}/health")
    async def _health():
        return JSONResponse({"status": "OK"}, headers=_cors_headers())

    @app.post(f"{prefix}/ingest")
    async def _post(request: Request):
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError("Payload phải là một JSON object.")
        except Exception as exc:
            return JSONResponse(
                {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"},
                status_code=400, headers=_cors_headers(),
            )
        with _extension_ingest_lock:
            try:
                stats = await run_in_threadpool(ingest_extension_items, payload)
            except Exception as exc:
                return JSONResponse(
                    {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"},
                    status_code=500, headers=_cors_headers(),
                )
        return JSONResponse(stats, headers=_cors_headers())


# ---------------------------------------------------------------------------
# Tab: Dữ Liệu Từ Extension (xem trước dữ liệu extension gửi lên)
# ---------------------------------------------------------------------------

EXT_CRAWL_COLUMNS = ["URL", "Nội dung bài", "Số bình luận", "Bình luận"]


def load_extension_view() -> tuple:
    """Trả về: trạng thái lần nhận gần nhất + bảng raw preview + bảng DB."""
    last = APP.extension_last_ingest
    if last:
        status_md = (
            f"### 📡 Lần Nhận Gần Nhất\n\n"
            f"- **Nguồn:** `{last.get('source', 'Extension')}` lúc `{last.get('time')}`\n"
            f"- **Bài nhận:** `{last.get('received_posts', 0)}` | "
            f"**Bình luận nhận:** `{last.get('received_comments', 0)}` | "
            f"**Lưu mới vào DB:** `{last.get('stored_new', 0)}` | "
            f"**Trùng lặp → bỏ qua:** `{last.get('duplicates_skipped', 0)}`\n"
            f"- **Cảnh báo đã gửi:** `{last.get('alerts_triggered', 0)}`"
        )
        if last.get("errors"):
            status_md += "\n- **Lỗi:**\n```text\n" + "\n".join(last["errors"][:5]) + "\n```"
    else:
        status_md = "Chưa có dữ liệu nào từ Extension. Mở extension, bấm **Quét ngay** rồi **Đồng bộ lên server**."

    preview = APP.extension_received_preview or []
    if preview:
        raw_df = pd.DataFrame([
            {
                "URL": p.get("url", ""),
                "Nội dung bài": p.get("postText", ""),
                "Số bình luận": len(p.get("comments") or []),
                "Bình luận": "\n".join(p.get("comments") or []),
            }
            for p in preview
        ])
    else:
        raw_df = pd.DataFrame(columns=EXT_CRAWL_COLUMNS)

    src_filter = {EXTENSION_SOURCE}
    if last and last.get("source"):
        src_filter.add(last["source"])
    items = [
        r for r in APP.repo.get_recent_items(limit=200)
        if r.get("source") in src_filter
    ]
    if items:
        db_df = pd.DataFrame(items)[
            ["item_id", "source", "content_type", "author", "text", "org_detected",
             "detected_org_name", "sentiment_label", "confidence", "alert_sent", "processed_at"]
        ]
    else:
        db_df = pd.DataFrame(columns=["item_id", "source", "content_type", "author", "text",
                                      "org_detected", "detected_org_name", "sentiment_label",
                                      "confidence", "alert_sent", "processed_at"])
    return status_md, raw_df, db_df


# ---------------------------------------------------------------------------
# UI Construction
# ---------------------------------------------------------------------------

GRADIO_MAJOR = int(gr.__version__.split(".")[0])
UI_THEME = gr.themes.Soft()


def build_ui() -> gr.Blocks:
    blocks_kwargs = {"title": "AI Social Listening System"}
    if GRADIO_MAJOR < 6:
        blocks_kwargs["theme"] = UI_THEME
    with gr.Blocks(**blocks_kwargs) as demo:
        gr.Markdown(
            "# 🛡️ AI Social Listening - Phát Hiện Nội Dung Tiêu Cực\n\n"
            "Hệ thống thực nghiệm tự động thu thập, phân tích cảm xúc tiếng Việt (PhoBERT) "
            "và cảnh báo khủng hoảng truyền thông."
        )

        with gr.Tabs():
            # ---------------- Tab 1: Overview ----------------
            with gr.Tab("📊 Tổng Quan Hệ Thống"):
                overview_grid = gr.HTML()
                info_row = gr.Row()
                with info_row:
                    with gr.Column():
                        target_info = gr.Markdown()
                        aliases_info = gr.Markdown()
                    with gr.Column():
                        last_scan_info = gr.Markdown()
                        channel_info = gr.Markdown()
                refresh_overview_btn = gr.Button("🔄 Làm Mới Số Liệu", variant="primary")
                refresh_overview_btn.click(
                    load_overview, outputs=[overview_grid, last_scan_info, channel_info]
                )
                demo.load(load_overview, outputs=[overview_grid, last_scan_info, channel_info])
                demo.load(load_overview_info, outputs=[target_info, aliases_info])

            # ---------------- Tab 2: Configuration ----------------
            with gr.Tab("⚙️ Cấu Hình Hệ Thống"):
                gr.Markdown("Cấu hình tổ chức mục tiêu, nguồn dữ liệu, ngưỡng cảnh báo và kênh Telegram.")
                with gr.Row():
                    with gr.Column():
                        target_org_input = gr.Textbox(
                            label="Tổ chức mục tiêu (Target Org)",
                            value=Config.TARGET_ORGANIZATION,
                        )
                        aliases_input = gr.Textbox(
                            label="Tên viết tắt / Aliases (phân cách bằng dấu phẩy)",
                            value=", ".join(Config.TARGET_ALIASES),
                        )
                        platform_input = gr.Dropdown(
                            label="Nguồn dữ liệu Quét (Social Platform)",
                            choices=["mock", "facebook", "rss"],
                            value=Config.SOCIAL_PLATFORM,
                        )
                        source_limit_input = gr.Dropdown(
                            label="Số nguồn Top-N cần khám phá",
                            choices=[10, 20, 50, 100],
                            value=APP.source_limit,
                        )
                    with gr.Column():
                        threshold_input = gr.Slider(
                            label="Ngưỡng tin cậy Cảnh báo (Sentiment Threshold)",
                            minimum=0.50, maximum=0.99, step=0.05,
                            value=Config.SENTIMENT_THRESHOLD,
                        )
                        interval_input = gr.Number(
                            label="Chu kỳ quét tự động (phút)",
                            minimum=1, maximum=1440,
                            value=Config.SCHEDULE_INTERVAL_MINUTES,
                        )
                        channel_input = gr.Dropdown(
                            label="Kênh gửi cảnh báo (Alert Channel)",
                            choices=["mock", "telegram", "slack", "email", "all"],
                            value=Config.ALERT_CHANNEL,
                        )
                gr.Markdown("### 🔑 Kênh Telegram")
                with gr.Row():
                    telegram_token_input = gr.Textbox(
                        label="Telegram Bot Token", value=Config.TELEGRAM_BOT_TOKEN, type="password",
                    )
                    telegram_chat_id_input = gr.Textbox(
                        label="Telegram Chat ID", value=Config.TELEGRAM_CHAT_ID,
                    )
                save_config_btn = gr.Button("💾 Lưu Cấu Hình", variant="primary")
                config_message = gr.Markdown()
                save_config_btn.click(
                    save_config,
                    inputs=[
                        target_org_input, aliases_input, platform_input, threshold_input,
                        interval_input, channel_input, telegram_token_input,
                        telegram_chat_id_input, source_limit_input,
                    ],
                    outputs=[config_message],
                )

            # ---------------- Tab: AI Model Manager ----------------
            with gr.Tab("🤖 Mô Hình AI"):
                model_status_md = gr.Markdown()
                gr.Markdown(
                    "Nếu hệ thống **chưa có mô hình** (hoặc muốn đổi sang mô hình khác), "
                    "nhập **Model ID trên HuggingFace** rồi bấm nút tải. "
                    "Lần đầu sẽ **tự động download** mô hình (cần internet, có thể mất vài phút); "
                    "nếu tải thất bại, hệ thống tự chuyển sang **heuristic** để hệ thống vẫn chạy."
                )
                model_name_input = gr.Textbox(
                    label="Model ID (HuggingFace)",
                    value=APP.pipeline.sentiment_analyzer.model_name,
                    placeholder="wonrax/phobert-base-vietnamese-sentiment",
                )
                model_load_btn = gr.Button("⬇️ Tải / Tải Lại Mô Hình", variant="primary")
                model_result_md = gr.Markdown()
                model_load_btn.click(
                    load_model_ui,
                    inputs=[model_name_input],
                    outputs=[model_result_md, model_status_md],
                )
                demo.load(model_status, outputs=[model_status_md])

            # ---------------- Tab 3: Scan / Discovery ----------------
            with gr.Tab("🚀 Kích Hoạt Quét Dữ Liệu"):
                gr.Markdown(
                    "Khu vực vận hành: khám phá nguồn công khai (Source Discovery) "
                    "và kích hoạt chu kỳ quét thủ công. "
                    "Discovery chỉ chạy khi bạn chủ động bấm nút bên dưới."
                )
                with gr.Row():
                    discovery_btn = gr.Button("🔎 Chạy Discovery", variant="secondary")
                    scan_btn = gr.Button("🔥 Kích Hoạt Quét Ngay", variant="primary")
                discovery_status = gr.Markdown()
                discovery_counts = gr.Markdown()
                discovery_metrics = gr.Markdown()
                discovery_table = gr.Dataframe(headers=["Rank", "Platform", "Source Name",
                                                        "Source Type", "URL", "Relevance", "Status"])
                scan_output = gr.Markdown()

                discovery_btn.click(run_discovery, outputs=[
                    discovery_status, discovery_counts, discovery_metrics, discovery_table,
                ])
                scan_btn.click(run_scan, outputs=[scan_output])

            # ---------------- Tab 4: AI Test Bench ----------------
            with gr.Tab("🧪 AI Test Bench"):
                gr.Markdown(
                    "Thử nghiệm phân tích cảm xúc & nhận diện thực thể tiếng Việt. "
                    "Nhập văn bản bất kỳ để kiểm thử PhoBERT / Heuristic AI."
                )
                test_input = gr.Textbox(
                    label="Nhập nội dung bài đăng / bình luận tiếng Việt:",
                    value="Phòng đào tạo Đại học DNC làm việc quá chậm trễ, phục vụ tệ hại lừa đảo sinh viên!",
                    lines=4,
                )
                test_analyze_btn = gr.Button("🔍 Phân Tích Văn Bản", variant="primary")
                with gr.Row():
                    entity_output = gr.Markdown()
                    sentiment_output = gr.Markdown()
                decision_output = gr.Markdown()
                test_analyze_btn.click(
                    analyze_testbench,
                    inputs=[test_input],
                    outputs=[entity_output, sentiment_output, decision_output],
                )

            # ---------------- Tab 5: History ----------------
            with gr.Tab("📜 Lịch Sử Cảnh Báo & Dữ Liệu"):
                refresh_history_btn = gr.Button("🔄 Làm Mới", variant="primary")
                gr.Markdown("### Bài Viết / Bình Luận Đã Quét")
                items_table = gr.Dataframe()
                gr.Markdown("### Lịch Sử Cảnh Báo Gửi Đi")
                alerts_table = gr.Dataframe()
                refresh_history_btn.click(load_history, outputs=[items_table, alerts_table])
                demo.load(load_history, outputs=[items_table, alerts_table])

            # ---------------- Tab 6: TXT Analysis ----------------
            with gr.Tab("📄 Phân Tích Cảm Xúc Từ File TXT"):
                gr.Markdown(
                    "Tải lên file `.txt` theo định dạng chuẩn: `=== BAI n ===` / `URL:` / `NOI DUNG:` / "
                    "`--- BINH LUAN ---` / `N. Username: bình luận`. Hệ thống sẽ parse toàn bộ bài viết "
                    "(POST) và bình luận (COMMENT), giữ nguyên URL / username / nội dung, sau đó phân tích "
                    "sentiment riêng từng mẫu bằng AI Engine PhoBERT hiện có."
                )
                txt_file = gr.File(label="Chọn file .txt để phân tích", file_count="single", type="binary")
                with gr.Row():
                    txt_analyze_btn = gr.Button("🔍 Phân Tích File", variant="primary")
                    txt_alert_btn = gr.Button("🚨 Gửi cảnh báo về Telegram")
                txt_message = gr.Markdown()
                txt_summary = gr.Markdown()
                txt_result_count = gr.Markdown()
                with gr.Row():
                    txt_filter = gr.Dropdown(
                        label="Bộ lọc nhanh:",
                        choices=["Tất cả", "Negative", "Positive", "Neutral",
                                 "Chỉ bài viết (POST)", "Chỉ bình luận (COMMENT)"],
                        value="Tất cả",
                    )
                    txt_sort_negative = gr.Checkbox(
                        label="Ưu tiên hiển thị Negative trước", value=True,
                    )
                txt_table = gr.Dataframe(headers=TXT_COLUMNS)

                txt_analyze_btn.click(
                    analyze_txt_file,
                    inputs=[txt_file],
                    outputs=[txt_message, txt_summary, txt_result_count, txt_table],
                )
                txt_filter.change(
                    _filter_txt,
                    inputs=[txt_filter, txt_sort_negative],
                    outputs=[txt_table],
                )
                txt_sort_negative.change(
                    _filter_txt,
                    inputs=[txt_filter, txt_sort_negative],
                    outputs=[txt_table],
                )
                txt_alert_btn.click(send_txt_alerts, outputs=[txt_message])

            # ---------------- Tab 8: Extension Ingest / Preview ----------------
            with gr.Tab("📡 Dữ Liệu Từ Extension"):
                gr.Markdown(
                    "Xem nội dung mà **Chrome Extension** đã quét và tự động đẩy lên "
                    "qua endpoint `POST /api/extension/ingest`. Phần mềm chạy cùng quy trình "
                    "AI (detect tổ chức + sentiment + cảnh báo) như pipeline chính, kết quả "
                    "lưu vào DB và hiển thị cả ở tab '📜 Lịch Sử'."
                )
                extension_last_md = gr.Markdown()
                refresh_extension_btn = gr.Button("🔄 Làm Mới", variant="primary")
                gr.Markdown("### Bài Vừa Nhận Từ Extension (raw)")
                extension_raw_table = gr.Dataframe(headers=EXT_CRAWL_COLUMNS)
                gr.Markdown("### Bản Ghi Đã Phân Tích Lưu Vào DB (source = extension)")
                extension_db_table = gr.Dataframe()
                refresh_extension_btn.click(
                    load_extension_view,
                    outputs=[extension_last_md, extension_raw_table, extension_db_table],
                )
                demo.load(
                    load_extension_view,
                    outputs=[extension_last_md, extension_raw_table, extension_db_table],
                )

        return demo


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Social Listening - Gradio Dashboard")
    parser.add_argument("--share", action="store_true",
                        help="Publish a public URL via the Gradio share tunnel")
    parser.add_argument("--server-name", default="127.0.0.1",
                        help="Host address to bind (default: 127.0.0.1)")
    parser.add_argument("--server-port", type=int, default=8501,
                        help="Port to bind (default: 8501)")
    args = parser.parse_args()

    demo = build_ui()
    launch_kwargs = {
        "server_name": args.server_name,
        "server_port": args.server_port,
        "share": args.share,
    }
    if GRADIO_MAJOR >= 6:
        launch_kwargs["theme"] = UI_THEME
    else:
        launch_kwargs["show_api"] = False

    # prevent_thread_lock để chúng ta có thể đăng ký Extension Ingest API lên
    # App thực tế đang serve (gradio tạo App mới khi launch, demo.app là bản cũ).
    launch_kwargs["prevent_thread_lock"] = True
    result = demo.launch(**launch_kwargs)

    serve_app = None
    if isinstance(result, tuple) and len(result) > 0 and hasattr(result[0], "router"):
        serve_app = result[0]
    elif hasattr(result, "router"):
        serve_app = result
    if serve_app is None:
        serve_app = getattr(demo, "app", None)
    register_extension_api(serve_app)

    logger.info("Extension Ingest API sẵn sàng tại POST /api/extension/ingest.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass

