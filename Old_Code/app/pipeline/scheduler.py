import time
import threading
import schedule
from typing import Optional
from config import Config
from app.pipeline.pipeline import SocialListeningPipeline
from app.utils.logger import logger

class PipelineScheduler:
    """
    Automated Background Scheduler for the Social Listening Pipeline.
    Runs non-blocking in background threads or standalone CLI mode.
    """

    def __init__(self, pipeline: Optional[SocialListeningPipeline] = None):
        self.pipeline = pipeline or SocialListeningPipeline()
        self.is_running = False
        self._thread: Optional[threading.Thread] = None

    def _scheduled_job(self):
        try:
            self.pipeline.run_cycle()
        except Exception as e:
            logger.error(f"[PipelineScheduler] Exception during scheduled job execution: {e}")

    def start_background(self, interval_minutes: Optional[int] = None):
        """Starts background scheduler thread."""
        if self.is_running:
            logger.warning("[PipelineScheduler] Scheduler is already running.")
            return

        minutes = interval_minutes or Config.SCHEDULE_INTERVAL_MINUTES
        logger.info(f"[PipelineScheduler] Scheduling background pipeline scan every {minutes} minute(s).")
        
        schedule.clear()
        schedule.every(minutes).minutes.do(self._scheduled_job)

        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("[PipelineScheduler] Background scheduler thread started successfully.")

    def _run_loop(self):
        # Run initial cycle immediately upon starting
        self._scheduled_job()
        while self.is_running:
            schedule.run_pending()
            time.sleep(1)

    def stop(self):
        """Stops background scheduler."""
        self.is_running = False
        schedule.clear()
        logger.info("[PipelineScheduler] Scheduler stopped.")

    def run_blocking(self, interval_minutes: Optional[int] = None):
        """Runs scheduler in foreground blocking mode for CLI usage."""
        minutes = interval_minutes or Config.SCHEDULE_INTERVAL_MINUTES
        logger.info(f"[PipelineScheduler] Starting FOREGROUND blocking loop (Interval: {minutes} minutes)...")

        # Initial run
        self._scheduled_job()

        schedule.clear()
        schedule.every(minutes).minutes.do(self._scheduled_job)

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("[PipelineScheduler] Foreground loop interrupted by user. Exiting cleanly.")
