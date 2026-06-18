"""
config.py
=========
Central configuration for the AI Investment Advisor.

All secrets are read from environment variables (loaded from a local `.env`
file in development, or from the platform's secret manager in production —
e.g. Hugging Face Spaces "Secrets" or Render "Environment").

Never hard-code API keys in source files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load variables from a .env file if one exists (no-op in production).
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable application settings, populated from the environment."""

    # ---- API credentials -------------------------------------------------
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    news_api_key: str = field(default_factory=lambda: os.getenv("NEWS_API_KEY", ""))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))

    # ---- LLM settings ----------------------------------------------------
    # The advisor falls back to a deterministic rule-based engine when no
    # OpenAI key is configured, so the app still runs end-to-end for grading.
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    llm_temperature: float = field(
        default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.2"))
    )
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))

    # ---- Data settings ---------------------------------------------------
    default_period: str = "1y"        # History window pulled from Yahoo Finance.
    default_interval: str = "1d"      # Daily candles.
    news_page_size: int = 10          # Number of headlines pulled from NewsAPI.
    cache_ttl_seconds: int = 300      # Streamlit cache lifetime (5 minutes).

    # ---- Technical-indicator parameters ---------------------------------
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    sma_short: int = 50
    sma_long: int = 200

    @property
    def openai_enabled(self) -> bool:
        """True when a real OpenAI key is present."""
        return bool(self.openai_api_key)

    @property
    def news_enabled(self) -> bool:
        """True when a real NewsAPI key is present."""
        return bool(self.news_api_key)

    @property
    def gemini_enabled(self) -> bool:
        """True when a real Gemini API key is present."""
        return bool(self.gemini_api_key)

    @property
    def groq_enabled(self) -> bool:
        """True when a real Groq API key is present."""
        return bool(self.groq_api_key)

    @property
    def chatbot_enabled(self) -> bool:
        """True when at least one chatbot engine is available."""
        return self.groq_enabled or self.gemini_enabled


# A single shared settings instance imported across the codebase.
settings = Settings()
