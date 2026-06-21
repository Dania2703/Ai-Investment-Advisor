"""
config.py
=========
Central configuration for the AI Investment Advisor.

All secrets are read from environment variables (loaded from a local `.env`
file in development, or from the platform's secret manager in production —
e.g. Hugging Face Spaces "Secrets").
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable application settings, populated from the environment."""

    # ---- API credentials -------------------------------------------------
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    finnhub_api_key: str = field(default_factory=lambda: os.getenv("FINNHUB_API_KEY", ""))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    # Optional, OFF by default: only used as a resilience fallback for daily
    # candles when yfinance fails. See src/data/market_data.py.
    tiingo_api_key: str = field(default_factory=lambda: os.getenv("TIINGO_API_KEY", ""))

    # ---- LLM settings ----------------------------------------------------
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4.1"))
    llm_temperature: float = field(
        default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.2"))
    )
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))

    # ---- Data settings ---------------------------------------------------
    # 2 years of daily candles gives clean warm-up for SMA200 / ADX / Wilder
    # smoothing and enough context for swing-based support/resistance.
    default_period: str = "2y"
    default_interval: str = "1d"
    news_count: int = 10
    cache_ttl_seconds: int = 300
    # Minimum candles required before we trust the full indicator set.
    min_history_bars: int = 60
    # Drop the final candle if it belongs to an in-progress session
    # (avoids a partial/forming bar skewing the latest indicator values).
    drop_incomplete_bar: bool = True

    # ---- Data-quality / freshness guards ---------------------------------
    # Price adjustment policy. "raw" => split-adjusted, dividend-UNADJUSTED
    # close (matches TradingView / Investing / Barchart defaults). This is the
    # canonical series indicators run on. The fully-adjusted series is kept
    # alongside as "Adj Close" for reference only.
    price_adjustment: str = "raw"
    # Fail loudly if the latest bar is older than this many *business* days.
    max_stale_business_days: int = 5
    # Transient yfinance/scraper failures: retry a few times before failing.
    history_retries: int = 3
    history_retry_wait_seconds: float = 1.5

    # ---- Technical-indicator parameters ----------------------------------
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    sma_short: int = 50
    sma_long: int = 200
    ema_fast: int = 20
    ema_mid: int = 50
    ema_slow: int = 200
    bb_period: int = 20
    bb_std: float = 2.0
    stoch_rsi_period: int = 14
    stoch_rsi_k: int = 3
    stoch_rsi_d: int = 3
    adx_period: int = 14
    atr_period: int = 14
    obv_ema_period: int = 20
    volume_sma_period: int = 20
    # Lookback (in bars) for swing-based support / resistance detection.
    sr_lookback: int = 60

    # ---- Scoring-engine weights (must sum to 1.0) ------------------------
    # Trend is intentionally capped at 35% and its internally correlated
    # sub-signals are de-duplicated (see src/analysis/correlation.py) to stop
    # the over-bullish score inflation documented in docs/AUDIT.md.
    weight_trend: float = 0.35
    weight_momentum: float = 0.25
    weight_volume: float = 0.15
    weight_volatility: float = 0.10
    weight_sentiment: float = 0.10
    weight_risk: float = 0.05

    # Above this absolute correlation, two signals are treated as one concept
    # and share a single weight (automatic double-count removal).
    correlation_threshold: float = 0.85
    # ADX keeps an independent share of the trend category so trend strength is
    # never fully absorbed into the (collinear) moving-average cluster.
    trend_adx_share: float = 0.30

    # Signal classification thresholds on the 0..1 bullishness scale.
    bullish_threshold: float = 0.60
    bearish_threshold: float = 0.40

    # ---- Database --------------------------------------------------------
    # Legacy SQLite path for the anonymous analysis cache (kept for back-compat).
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "data/advisor.db"))

    # User accounts + saved history live in a SQLAlchemy-managed database.
    # Set DATABASE_URL to a Postgres connection string in production
    # (e.g. Neon / Supabase / Render). Falls back to a local SQLite file so
    # the app runs out-of-the-box in development with zero infrastructure.
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///data/users.db")
    )

    # ---- Auth / session --------------------------------------------------
    # Secret used to sign the session token stored in the URL query params so
    # a login survives a browser refresh. Override in production.
    secret_key: str = field(
        default_factory=lambda: os.getenv("SECRET_KEY", "dev-insecure-change-me")
    )
    # Session lifetime, in hours, before a stored token is considered expired.
    session_ttl_hours: int = field(
        default_factory=lambda: int(os.getenv("SESSION_TTL_HOURS", "168"))  # 7 days
    )

    @property
    def normalized_database_url(self) -> str:
        """
        Return a SQLAlchemy-compatible URL.

        Many managed providers (Heroku-style) hand out ``postgres://`` URLs,
        which SQLAlchemy 2.x no longer accepts — normalise them to
        ``postgresql://``.
        """
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return url

    @property
    def using_postgres(self) -> bool:
        return self.normalized_database_url.startswith("postgresql")

    @property
    def openai_enabled(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def finnhub_enabled(self) -> bool:
        return bool(self.finnhub_api_key)

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def groq_enabled(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def chatbot_enabled(self) -> bool:
        return self.groq_enabled or self.gemini_enabled

    @property
    def tiingo_enabled(self) -> bool:
        return bool(self.tiingo_api_key)


settings = Settings()
