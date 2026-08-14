from typing import Dict, Any, List
from datetime import datetime
from app.alert.base import BaseAlertChannel
from app.alert.telegram import TelegramAlert
from app.alert.slack import SlackAlert
from app.alert.email_alert import EmailAlert
from app.alert.mock_alert import MockAlert
from config import Config
from app.utils.logger import logger

class AlertService:
    """
    Alert Service Orchestrator dispatching notifications across active channels.
    """

    def __init__(self, channel: str = ""):
        self.channel_name = (channel or Config.ALERT_CHANNEL).lower().strip()
        self.channels: List[BaseAlertChannel] = self._resolve_channels(self.channel_name)

    def _resolve_channels(self, channel_name: str) -> List[BaseAlertChannel]:
        channels = []
        if channel_name == "telegram":
            channels.append(TelegramAlert())
        elif channel_name == "slack":
            channels.append(SlackAlert())
        elif channel_name == "email":
            channels.append(EmailAlert())
        elif channel_name == "all":
            channels.extend([TelegramAlert(), SlackAlert(), EmailAlert()])
        else:
            channels.append(MockAlert())
        return channels

    def dispatch_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Dispatches alert to all configured channels."""
        if not self.channels:
            logger.warning("[AlertService] No active alert channels configured.")
            return False

        overall_success = False
        for channel in self.channels:
            success = channel.send_alert(alert_data)
            if success:
                overall_success = True
        return overall_success


def evaluate_alert_eligibility(items: List[Dict[str, Any]], org_detector: Any, threshold: float):
    """
    Single source of truth for the project's alert condition:
        sentiment == NEGATIVE
        AND confidence >= threshold
        AND target organization detected

    If an item already carries entity-detection results (org_detected /
    matched_org / org_confidence stored by the analysis step, e.g. the TXT
    analyzer or the pipeline), those stored results are reused so the alert
    decision matches the analysis exactly. Otherwise (field missing, value
    None) detection is run on the item content via `org_detector`.

    Returns:
        (candidates, diagnostics)
        candidates  - deduplicated [{"item": ..., "detection": ...}, ...]
        diagnostics - per-item record with type/post_id/sentiment/confidence/
                      entity_match/target_org/eligible/reason for observability.
    """
    candidates: List[Dict[str, Any]] = []
    diagnostics: List[Dict[str, Any]] = []
    seen = set()
    for item in items:
        diag = {
            "type": item.get("type"),
            "post_id": item.get("post_id"),
            "username": item.get("username"),
            "sentiment": item.get("sentiment"),
            "confidence": item.get("confidence"),
            "entity_match": item.get("org_detected"),
            "matched_org": item.get("matched_org"),
            "target_org": Config.TARGET_ORGANIZATION,
            "eligible": False,
            "reason": None,
        }

        if item.get("sentiment") != "NEGATIVE":
            diag["reason"] = "SENTIMENT_NOT_NEGATIVE"
            diagnostics.append(diag)
            continue

        confidence = item.get("confidence")
        if confidence is None or float(confidence or 0.0) < threshold:
            diag["reason"] = "CONFIDENCE_BELOW_THRESHOLD"
            diagnostics.append(diag)
            continue

        content = (item.get("content") or "").strip()

        # Prefer the detection already produced during analysis.
        stored_org_detected = item.get("org_detected")
        if stored_org_detected is not None:
            if not stored_org_detected:
                diag["reason"] = "ORG_NOT_DETECTED"
                diagnostics.append(diag)
                continue
            detection = {
                "org_detected": True,
                "matched_org": item.get("matched_org"),
                "confidence": float(item.get("org_confidence") or 0.0),
            }
            diag["entity_match"] = True
            diag["matched_org"] = item.get("matched_org")
        else:
            detection = org_detector.detect(content)
            diag["entity_match"] = detection.get("org_detected")
            diag["matched_org"] = detection.get("matched_org")
            if not detection.get("org_detected"):
                diag["reason"] = "ORG_NOT_DETECTED"
                diagnostics.append(diag)
                continue

        key = (item.get("type"), item.get("post_id"), item.get("username"), content)
        if key in seen:
            diag["reason"] = "DUPLICATE"
            diagnostics.append(diag)
            continue
        seen.add(key)

        diag["eligible"] = True
        diag["reason"] = "ELIGIBLE"
        diagnostics.append(diag)
        candidates.append({"item": item, "detection": detection})

    return candidates, diagnostics


def select_alert_candidates(items: List[Dict[str, Any]], org_detector: Any, threshold: float) -> List[Dict[str, Any]]:
    """
    Filter analyzed items that meet the project's alert condition (see
    `evaluate_alert_eligibility`). Returns only the candidate list.
    """
    candidates, _ = evaluate_alert_eligibility(items, org_detector, threshold)
    return candidates


def build_alert_payload(item: Dict[str, Any], detection: Dict[str, Any],
                        source: str = "File TXT", detected_at: str = "") -> Dict[str, Any]:
    """
    Build the standard alert payload expected by AlertService channels.

    POST items map to "Bài viết", COMMENT items to "Bình luận".
    Username/author is only populated for comments.
    """
    now_str = detected_at or datetime.now().isoformat()
    return {
        "target_organization": detection.get("matched_org") or Config.TARGET_ORGANIZATION,
        "sentiment": item.get("sentiment") or "NEGATIVE",
        "confidence": float(item.get("confidence") or 0.0),
        "text": item.get("content") or "",
        "source": source,
        "post_url": item.get("url") or "N/A",
        "author": item.get("username") or "",
        "type": "Bài viết" if item.get("type") == "POST" else "Bình luận",
        "detected_at": now_str,
    }
