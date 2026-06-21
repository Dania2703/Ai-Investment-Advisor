"""
src/data/news_data.py
======================
Fetches recent financial news for a given ticker from Finnhub's
company news endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

import requests

from config import settings

FINNHUB_BASE = "https://finnhub.io/api/v1"


@dataclass
class Article:
    """A single news article relevant to a ticker."""

    title: str
    description: str
    source: str
    url: str
    published_at: str

    @property
    def text(self) -> str:
        """Combined title + description used for sentiment scoring."""
        return f"{self.title}. {self.description}".strip()


def get_news(ticker: str, days_back: int = 7) -> List[Article]:
    """
    Return recent news articles for *ticker* from Finnhub.

    Returns an empty list (never raises) when the API key is missing or
    the request fails.
    """
    if not settings.finnhub_enabled:
        return []

    ticker = ticker.strip().upper()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    try:
        resp = requests.get(
            f"{FINNHUB_BASE}/company-news",
            params={
                "symbol": ticker,
                "from": from_date,
                "to": today,
                "token": settings.finnhub_api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        raw_list = resp.json()
    except (requests.RequestException, ValueError):
        return []

    if not isinstance(raw_list, list):
        return []

    articles: List[Article] = []
    for raw in raw_list[: settings.news_count]:
        pub_ts = raw.get("datetime", 0)
        pub_str = datetime.utcfromtimestamp(pub_ts).strftime("%Y-%m-%d %H:%M") if pub_ts else ""
        articles.append(
            Article(
                title=raw.get("headline") or "",
                description=raw.get("summary") or "",
                source=raw.get("source") or "Unknown",
                url=raw.get("url") or "",
                published_at=pub_str,
            )
        )
    return articles
