import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-in-production")

    # PostgreSQL — swap in your Render/cPanel DATABASE_URL
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://mzizibet:password@localhost:5432/mzizibet"
    )
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        # Render gives postgres:// but SQLAlchemy 1.4+ wants postgresql://
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Session / auth
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"

    # M-Pesa Daraja — deposits/withdrawals
    MPESA_CONSUMER_KEY = os.environ.get("MPESA_CONSUMER_KEY", "")
    MPESA_CONSUMER_SECRET = os.environ.get("MPESA_CONSUMER_SECRET", "")
    MPESA_SHORTCODE = os.environ.get("MPESA_SHORTCODE", "")
    MPESA_PASSKEY = os.environ.get("MPESA_PASSKEY", "")
    MPESA_CALLBACK_URL = os.environ.get("MPESA_CALLBACK_URL", "")
    MPESA_ENV = os.environ.get("MPESA_ENV", "sandbox")  # sandbox | production

    # Licensed game/odds providers — DO NOT implement in-house RNG for
    # real-money casino games or in-house odds compilation for sports.
    # Plug a certified aggregator's API keys in here once your BCLB
    # licensing process confirms an approved provider.
    GAME_PROVIDER_API_KEY = os.environ.get("GAME_PROVIDER_API_KEY", "")
    GAME_PROVIDER_BASE_URL = os.environ.get("GAME_PROVIDER_BASE_URL", "")
    ODDS_PROVIDER_API_KEY = os.environ.get("ODDS_PROVIDER_API_KEY", "")
    ODDS_PROVIDER_BASE_URL = os.environ.get("ODDS_PROVIDER_BASE_URL", "")

    # Responsible gambling defaults (BCLB compliance expects these to exist)
    DEFAULT_DAILY_DEPOSIT_LIMIT = 50000  # KES
    MIN_AGE = 18


class DevelopmentConfig(Config):
    DEBUG = True
    # Local dev: use a SQLite file so no Postgres server is required.
    # Set DATABASE_URL in your environment/.env if you want to test
    # against real Postgres locally instead.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'dev.db')}"
    )


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
