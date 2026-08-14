import logging
import os
import sys
from pathlib import Path
from config import Config

def setup_logger(name: str = "SocialListeningAI") -> logging.Logger:
    """
    Sets up a structured logger with both console and file output.
    Supports levels: INFO, WARNING, ERROR.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Force UTF-8 encoding on sys.stdout for Windows compatibility
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    try:
        log_file_path = Path(Config.LOG_FILE)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        console_handler.write(f"Warning: Could not initialize log file: {e}\n")

    return logger

logger = setup_logger()
