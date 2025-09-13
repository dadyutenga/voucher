from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database Configuration
    DATABASE_URL: str = "postgresql://user:pass@localhost/dbname"
    
    # Email/SMTP Configuration
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

    # Application Configuration
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Meraki Configuration
    MERAKI_API_KEY: Optional[str] = None
    MERAKI_BASE_GRANT_URL: str = "https://your-meraki-controller.com/guest/s/default/"
    MERAKI_NETWORK_ID: Optional[str] = None

    # Redis Configuration
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"

    # Security and CORS
    CORS_ORIGINS: str = "http://localhost:3000,https://yourdomain.com"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Rate Limiting
    DEMO_VOUCHER_RATE_LIMIT: int = 3
    DEMO_VOUCHER_RATE_WINDOW: int = 3600

    class Config:
        env_file = ".env"
        # Allow extra fields to prevent validation errors
        extra = "ignore"

settings = Settings()
