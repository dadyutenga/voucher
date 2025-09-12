from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:pass@localhost/dbname"
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SENDER_EMAIL: str = ""

    # M-Pesa Configuration
    MPESA_CONSUMER_KEY: Optional[str] = None
    MPESA_CONSUMER_SECRET: Optional[str] = None
    MPESA_SHORTCODE: Optional[str] = None
    MPESA_PASSKEY: Optional[str] = None
    MPESA_CALLBACK_URL: Optional[str] = None

    # General Payment Configuration
    DEFAULT_CURRENCY: str = "KES"

    # Security
    SECRET_KEY: Optional[str] = "your-secret-key-change-in-production"

    # Meraki Configuration
    MERAKI_API_KEY: Optional[str] = None
    MERAKI_BASE_GRANT_URL: Optional[str] = "https://your-meraki-controller.com/guest/s/default/"
    MERAKI_NETWORK_ID: Optional[str] = None

    class Config:
        env_file = ".env"

settings = Settings()
