import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

class Config:
    # Target Organization Configuration
    TARGET_ORGANIZATION: str = os.getenv("TARGET_ORGANIZATION", "Đại học Nam Cần Thơ")
    TARGET_ALIASES: list = [
        alias.strip() for alias in os.getenv("TARGET_ALIASES", "ĐH DNC, DNC, Trường DNC, Nam Cần Thơ").split(",") if alias.strip()
    ]

    # Social Media Platform Configuration
    SOCIAL_PLATFORM: str = os.getenv("SOCIAL_PLATFORM", "mock")  # Options: mock, facebook, rss
    TARGET_PAGES: list = [
        page.strip() for page in os.getenv("TARGET_PAGES", "dnc_confessions, fanpage_dnc, forum_sinhvien").split(",") if page.strip()
    ]

    # Public source discovery timeouts
    DISCOVERY_TIMEOUT_SECONDS: int = int(os.getenv("DISCOVERY_TIMEOUT_SECONDS", "10"))
    DISCOVERY_MAX_RETRIES: int = int(os.getenv("DISCOVERY_MAX_RETRIES", "1"))

    # Scheduler Configuration
    SCHEDULE_INTERVAL_MINUTES: int = int(os.getenv("SCHEDULE_INTERVAL_MINUTES", "60"))

    # AI Decision Threshold
    SENTIMENT_THRESHOLD: float = float(os.getenv("SENTIMENT_THRESHOLD", "0.80"))

    # Alerting Channel Configuration
    ALERT_CHANNEL: str = os.getenv("ALERT_CHANNEL", "telegram")  # Options: telegram, slack, email, mock, all

    # Telegram Credentials
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "8812720117:AAHOk0_96tuNjw3-eizzdWxtn-NsLefumqo")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "-5469376065")

    # Slack Credentials
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")

    # Email Credentials
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")
    ALERT_RECEIVER_EMAIL: str = os.getenv("ALERT_RECEIVER_EMAIL", "")

    # Database Path
    DB_PATH: str = os.getenv("DB_PATH", str(Path(__file__).parent / "data" / "social_listening.db"))

    # Logging Path
    LOG_FILE: str = os.getenv("LOG_FILE", str(Path(__file__).parent / "logs" / "system.log"))

    @classmethod
    def get_all_org_names(cls) -> list:
        """Returns target organization name along with all configured aliases."""
        names = [cls.TARGET_ORGANIZATION]
        for alias in cls.TARGET_ALIASES:
            if alias.lower() not in [n.lower() for n in names]:
                names.append(alias)
        return names
