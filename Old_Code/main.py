import sys
import argparse
from config import Config
from app.pipeline.pipeline import SocialListeningPipeline
from app.pipeline.scheduler import PipelineScheduler
from app.utils.logger import logger

def main():
    parser = argparse.ArgumentParser(description="AI Social Listening System - Organization Negative Content Detector")
    parser.add_argument("--mode", choices=["once", "daemon", "test"], default="once",
                        help="Execution mode: 'once' (single scan), 'daemon' (scheduled loop), 'test' (run test suite)")
    parser.add_argument("--interval", type=int, default=Config.SCHEDULE_INTERVAL_MINUTES,
                        help="Scan interval in minutes for daemon mode")
    parser.add_argument("--heuristic", action="store_true", help="Force lightweight rule-based sentiment model")

    args = parser.parse_args()

    logger.info("==========================================================")
    logger.info("  AI SOCIAL LISTENING EXPERIMENTAL SYSTEM - STARTUP")
    logger.info("==========================================================")

    if args.mode == "once":
        logger.info("[Main] Mode: SINGLE SCAN CYCLE")
        pipeline = SocialListeningPipeline(force_heuristic_ai=args.heuristic)
        summary = pipeline.run_cycle()
        logger.info(f"[Main] Cycle Summary: {summary}")

    elif args.mode == "daemon":
        logger.info(f"[Main] Mode: CONTINUOUS DAEMON (Every {args.interval} minutes)")
        pipeline = SocialListeningPipeline(force_heuristic_ai=args.heuristic)
        scheduler = PipelineScheduler(pipeline=pipeline)
        scheduler.run_blocking(interval_minutes=args.interval)

    elif args.mode == "test":
        logger.info("[Main] Mode: RUNNING TEST SUITE")
        import unittest
        loader = unittest.TestLoader()
        suite = loader.discover("tests", pattern="test_*.py")
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        sys.exit(not result.wasSuccessful())

if __name__ == "__main__":
    main()
