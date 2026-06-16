import os
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
HUGGINGFACE_MODEL = os.getenv("HUGGINGFACE_MODEL", "HuggingFaceH4/zephyr-7b-beta")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
USE_TWIKIT = os.getenv("USE_TWIKIT", "false").lower() == "true"
APIFY_API_KEY = os.getenv("APIFY_API_KEY")
TWITTER_SCRAPER_ACTOR_ID = os.getenv("TWITTER_SCRAPER_ACTOR_ID", "apify/twitter-scraper")
APP_ENV = os.getenv("APP_ENV", "development")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://lumen8health.com")


class Settings:
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "noreply@lmn8.com"))


COHERENCE_THRESHOLD_LOW = float(os.getenv("COHERENCE_THRESHOLD_LOW", "0.3"))
COHERENCE_THRESHOLD_MEDIUM = float(os.getenv("COHERENCE_THRESHOLD_MEDIUM", "0.6"))
QUARANTINE_TTL_DAYS = int(os.getenv("QUARANTINE_TTL_DAYS", "14"))
DRIFT_ALERT_THRESHOLD = float(os.getenv("DRIFT_ALERT_THRESHOLD", "0.3"))
DRIFT_LOOKBACK_COUNT = int(os.getenv("DRIFT_LOOKBACK_COUNT", "10"))



settings = Settings()
