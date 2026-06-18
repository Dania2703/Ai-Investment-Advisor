"""
src/analysis/sentiment.py
=========================
Scores the sentiment of financial news headlines with an AI model.

Primary engine
--------------
A Hugging Face transformers pipeline running **FinBERT**
(`ProsusAI/finbert`) — a BERT model fine-tuned on financial text, which
classifies each headline as positive / negative / neutral.

Fallback engine
----------------
If `transformers` / `torch` are unavailable (or the model can't download),
we fall back to **VADER** from NLTK, a lightweight rule-based sentiment
analyzer. This guarantees the feature works in constrained environments
such as the free Hugging Face Spaces / Render tiers.

The public API is a single `score_articles()` function returning an
aggregate score in [-1, +1] plus per-article detail.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from src.data.news_data import Article

# --------------------------------------------------------------------------- #
# Lazy, cached model loaders
# --------------------------------------------------------------------------- #
_finbert = None
_vader = None


def _load_finbert():
    """Lazily build the FinBERT pipeline; return None on any failure."""
    global _finbert
    if _finbert is not None:
        return _finbert
    try:
        from transformers import pipeline

        _finbert = pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            truncation=True,
        )
    except Exception:  # noqa: BLE001 - missing deps / no network / etc.
        _finbert = None
    return _finbert


def _load_vader():
    """Lazily build the VADER analyzer; downloads its tiny lexicon if needed."""
    global _vader
    if _vader is not None:
        return _vader
    try:
        import nltk
        from nltk.sentiment import SentimentIntensityAnalyzer

        try:
            _vader = SentimentIntensityAnalyzer()
        except LookupError:
            nltk.download("vader_lexicon", quiet=True)
            _vader = SentimentIntensityAnalyzer()
    except Exception:  # noqa: BLE001
        _vader = None
    return _vader


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #
@dataclass
class ArticleSentiment:
    """Sentiment result for a single article."""

    title: str
    label: str        # "positive" / "negative" / "neutral"
    score: float      # signed score in [-1, +1]


@dataclass
class SentimentResult:
    """Aggregate sentiment across all analysed articles."""

    engine: str                       # "FinBERT" or "VADER" or "None"
    average_score: float              # [-1, +1]
    label: str                        # "Positive" / "Negative" / "Neutral"
    positive: int
    negative: int
    neutral: int
    details: List[ArticleSentiment]

    @property
    def percent(self) -> int:
        """Map the [-1, +1] score onto a friendly 0-100 scale for the UI."""
        return int(round((self.average_score + 1) / 2 * 100))


# --------------------------------------------------------------------------- #
# Scoring helpers
# --------------------------------------------------------------------------- #
def _score_with_finbert(texts: List[str], pipe) -> List[ArticleSentiment]:
    results = []
    raw = pipe(texts)
    for text, r in zip(texts, raw):
        label = r["label"].lower()
        prob = float(r["score"])
        signed = prob if label == "positive" else -prob if label == "negative" else 0.0
        results.append(ArticleSentiment(title=text[:120], label=label, score=signed))
    return results


def _score_with_vader(texts: List[str], analyzer) -> List[ArticleSentiment]:
    results = []
    for text in texts:
        compound = analyzer.polarity_scores(text)["compound"]
        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"
        results.append(ArticleSentiment(title=text[:120], label=label, score=compound))
    return results


def score_articles(articles: List[Article]) -> SentimentResult:
    """
    Analyse a list of articles and return an aggregate SentimentResult.

    Empty input yields a neutral result so callers never need to special-case
    "no news".
    """
    texts = [a.text for a in articles if a.text.strip()]
    if not texts:
        return SentimentResult("None", 0.0, "Neutral", 0, 0, 0, [])

    pipe = _load_finbert()
    if pipe is not None:
        engine = "FinBERT"
        print(f"[AI AUDIT] FinBERT scoring {len(texts)} headlines")
        details = _score_with_finbert(texts, pipe)
    else:
        analyzer = _load_vader()
        if analyzer is None:
            return SentimentResult("None", 0.0, "Neutral", 0, 0, 0, [])
        engine = "VADER"
        details = _score_with_vader(texts, analyzer)

    avg = sum(d.score for d in details) / len(details)
    positive = sum(1 for d in details if d.label == "positive")
    negative = sum(1 for d in details if d.label == "negative")
    neutral = len(details) - positive - negative

    if avg >= 0.15:
        label = "Positive"
    elif avg <= -0.15:
        label = "Negative"
    else:
        label = "Neutral"

    return SentimentResult(
        engine=engine,
        average_score=round(avg, 3),
        label=label,
        positive=positive,
        negative=negative,
        neutral=neutral,
        details=details,
    )
