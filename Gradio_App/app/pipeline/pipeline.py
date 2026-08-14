import time
from datetime import datetime
from typing import Dict, Any, List
from config import Config
from app.crawler.router import CrawlRouter
from app.ai.entity_detector import OrganizationDetector
from app.ai.sentiment_analyzer import VietnameseSentimentAnalyzer
from app.alert.service import AlertService
from app.db.repository import Repository
from app.utils.logger import logger
from app.db.source_registry import SourceRegistry

class SocialListeningPipeline:
    """
    Core End-to-End Social Listening AI Pipeline.
    Initializes AI models ONCE upon instantiation to prevent redundant model reloads.
    """

    def __init__(self, force_heuristic_ai: bool = False):
        logger.info("==================================================")
        logger.info("Initializing Social Listening AI Pipeline Components...")
        logger.info("==================================================")

        # 1. Initialize DB Repository
        self.repo = Repository()
        self.source_registry = SourceRegistry(self.repo)
        self.crawl_router = CrawlRouter()

        # 2. Initialize AI Engine ONCE at startup
        self.org_detector = OrganizationDetector()
        self.sentiment_analyzer = VietnameseSentimentAnalyzer(force_heuristic=force_heuristic_ai)

        # 3. Initialize Alert Service
        self.alert_service = AlertService()

        logger.info("[SocialListeningPipeline] All modules successfully initialized!")

    def run_cycle(self) -> Dict[str, Any]:
        """
        Executes a single processing cycle of the Social Listening pipeline.
        
        Flow:
        Collect Data -> Deduplicate -> Detect Org -> Sentiment -> Decide Alert -> Send Alert -> Log DB
        """
        start_time = time.time()
        now_str = datetime.now().isoformat()
        logger.info(f"\n==================================================")
        logger.info(f"[*] STARTING SOCIAL LISTENING SCAN CYCLE AT {now_str}")
        logger.info(f"Target Org : {Config.TARGET_ORGANIZATION}")
        logger.info(f"Platform   : {Config.SOCIAL_PLATFORM}")
        logger.info(f"Threshold  : {Config.SENTIMENT_THRESHOLD * 100:.1f}%")
        logger.info(f"==================================================")

        # Step 1: Collect Data using configured crawler
        crawl_sources = self.source_registry.crawlable_sources(Config.TARGET_ORGANIZATION)
        if crawl_sources:
            logger.info(f"[Pipeline] Crawling {len(crawl_sources)} registry sources in CRAWLABLE state.")
        else:
            logger.warning("[Pipeline] No CRAWLABLE discovered sources; skipping crawl for this cycle.")
        raw_items, crawl_summary = self.crawl_router.crawl_sources(crawl_sources, max_items=15)
        for update in crawl_summary["updates"]:
            self.source_registry.update_status(update["source_key"], update["status"], update["reason"])

        total_scanned = len(raw_items)
        org_mentions_count = 0
        negative_count = 0
        alerts_triggered_count = 0

        for item in raw_items:
            # Step 2: Deduplication Check using Item Hash Key
            item_id = self.repo.generate_item_id(
                item.get("post_id", ""),
                item.get("comment_id"),
                item.get("text", "")
            )
            item["item_id"] = item_id

            if self.repo.is_item_processed(item_id):
                logger.debug(f"[Pipeline] Item ID {item_id[:10]}... already processed. Skipping duplicate.")
                continue

            text_content = item.get("text", "")

            # Step 3: Organization Detection
            org_res = self.org_detector.detect(text_content)
            is_org_detected = org_res["org_detected"]
            matched_org = org_res["matched_org"]

            # Step 4: Sentiment Analysis
            sentiment_res = self.sentiment_analyzer.analyze(text_content)
            if not sentiment_res:
                continue

            sentiment_label = sentiment_res.get("label", "NEUTRAL")
            confidence = float(sentiment_res.get("confidence", 0.0))
            is_negative = sentiment_res.get("is_negative", False)

            if is_org_detected:
                org_mentions_count += 1
            if is_negative:
                negative_count += 1

            # Combined AI Result
            combined_ai_res = {
                "org_detected": is_org_detected,
                "matched_org": matched_org,
                "label": sentiment_label,
                "confidence": confidence,
                "is_negative": is_negative
            }

            # Step 5: Alert Decision Logic
            # Rule: Org Mentioned AND Negative Sentiment AND Confidence >= Threshold
            should_alert = (
                is_org_detected
                and is_negative
                and (confidence >= Config.SENTIMENT_THRESHOLD)
            )

            alert_sent = False
            if should_alert:
                logger.info(f"🚨 [ALERT DECISION TRIGGERED] Negative mention detected regarding '{matched_org}' (Conf: {confidence*100:.1f}%)")
                alert_payload = {
                    "target_organization": matched_org or Config.TARGET_ORGANIZATION,
                    "sentiment": sentiment_label,
                    "confidence": confidence,
                    "text": text_content,
                    "source": item.get("source", Config.SOCIAL_PLATFORM),
                    "post_url": item.get("post_url", ""),
                    "author": item.get("author", "Anonymous"),
                    "detected_at": now_str
                }

                # Step 6: Dispatch Alert
                alert_sent = self.alert_service.dispatch_alert(alert_payload)
                if alert_sent:
                    alerts_triggered_count += 1
                    self.repo.log_alert(
                        item_id=item_id,
                        channel=Config.ALERT_CHANNEL,
                        target_org=matched_org or Config.TARGET_ORGANIZATION,
                        sentiment=sentiment_label,
                        confidence=confidence,
                        message_text=text_content,
                        status="SUCCESS"
                    )
            else:
                if is_org_detected and is_negative:
                    logger.info(f"[Pipeline] Negative mention detected but confidence ({confidence*100:.1f}%) below threshold ({Config.SENTIMENT_THRESHOLD*100:.1f}%). Alert suppressed.")

            # Step 7: Record Item in Database Repository
            self.repo.save_processed_item(item, combined_ai_res, alert_sent)

        duration = round(time.time() - start_time, 2)
        self.repo.record_scan_cycle(
            total=total_scanned,
            mentions=org_mentions_count,
            negative=negative_count,
            alerts=alerts_triggered_count,
            duration=duration
        )

        cycle_summary = {
            "cycle_time": now_str,
            "total_scanned": total_scanned,
            "org_mentions": org_mentions_count,
            "negative_items": negative_count,
            "alerts_sent": alerts_triggered_count,
            "crawler": {key: value for key, value in crawl_summary.items() if key != "updates"},
            "duration_seconds": duration
        }

        logger.info(f"[*] SCAN CYCLE COMPLETED in {duration}s | Scanned: {total_scanned} | Mentions: {org_mentions_count} | Negative: {negative_count} | Alerts: {alerts_triggered_count}\n")
        return cycle_summary
