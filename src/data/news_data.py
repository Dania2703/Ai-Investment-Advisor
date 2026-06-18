"""
src/data/news_data.py
======================
Fetches recent financial news headlines for a given company / ticker from
NewsAPI (https://newsapi.org).

If no NewsAPI key is configured the module degrades gracefully and returns
an empty list, so the application keeps working end-to-end during grading.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

import requests

from config import settings

NEWS_ENDPOINT = "https://newsapi.org/v2/everything"


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


def get_news(query: str, page_size: int | None = None, days_back: int = 7) -> List[Article]:
    """
    Return up to *page_size* recent articles matching *query*.

    Parameters
    ----------
    query : str
        Search term — usually the company name or ticker.
    page_size : int | None
        Maximum number of articles (defaults to the configured value).
    days_back : int
        How many days of history to search.

    Notes
    -----
    Returns an empty list (never raises) when the API key is missing or the
    request fails, so the UI can show a friendly "no news" message instead
    of crashing.
    """
    if not settings.news_enabled:
        return []

    page_size = page_size or settings.news_page_size
    from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    params = {
        "q": query,
        "from": from_date,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": page_size,
        "apiKey": settings.news_api_key,
    }

    try:
        response = requests.get(NEWS_ENDPOINT, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    if payload.get("status") != "ok":
        return []

    articles: List[Article] = []
    for raw in payload.get("articles", []):
        articles.append(
            Article(
                title=raw.get("title") or "",
                description=raw.get("description") or "",
                source=(raw.get("source") or {}).get("name", "Unknown"),
                url=raw.get("url") or "",
                published_at=raw.get("publishedAt") or "",
            )
        )
    return articles
