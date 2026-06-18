"""
src/ai/chatbot.py
=================
Conversational AI assistant for the stock-analysis dashboard.

Engine priority:
  1. Groq  (free Llama 3.3 70B — 30 RPM / 14,400 RPD)
  2. Gemini (free tier — if key is configured and quota available)

The chatbot receives the full analysis context (quote, technicals,
sentiment, recommendation) so every answer is grounded in the live
data the user is looking at — not generic finance knowledge.
"""

from __future__ import annotations

from typing import List, Tuple

from config import settings

SYSTEM_INSTRUCTION = """\
You are the AI Investment Advisor chatbot — a helpful, educational assistant \
embedded in a stock-analysis dashboard. You answer questions about the stock \
the user is currently viewing, using ONLY the live analysis context provided \
below. When the user asks about indicators, sentiment, or the recommendation, \
refer to the actual numbers. Keep answers concise (3-6 sentences) unless the \
user asks for a detailed explanation. Always remind users that this is \
educational and not financial advice when giving any investment-related answer.

CURRENT ANALYSIS CONTEXT
========================
{context}
"""


def build_context(quote, tech, sentiment, rec, articles) -> str:
    """Build a compact text block from the current analysis results."""
    headlines = "\n".join(
        f"  - {a.title}" for a in (articles or [])[:8]
    ) or "  (no news available)"

    if sentiment.details:
        sentiment_details = "\n".join(
            f"  - [{d.label} {d.score:+.2f}] {d.title}"
            for d in sentiment.details[:8]
        )
    else:
        sentiment_details = "  (no per-article scores available)"

    return f"""\
COMPANY
  Ticker:         {quote.ticker}
  Name:           {quote.name}
  Sector:         {quote.sector or 'N/A'}
  Current price:  {quote.price:,.2f} {quote.currency}
  Previous close: {quote.previous_close:,.2f}
  Daily change:   {quote.change:+.2f} ({quote.change_pct:+.2f}%)
  Market cap:     {f'{quote.market_cap/1e9:,.1f} B' if quote.market_cap else 'N/A'}

TECHNICAL INDICATORS
  RSI(14):        {f'{tech.rsi:.1f}' if tech.rsi is not None else 'N/A'} -> {tech.rsi_signal}
  MACD:           {f'{tech.macd:.3f}' if tech.macd is not None else 'N/A'} -> {tech.macd_trend}
  MACD histogram: {f'{tech.macd_hist:.3f}' if tech.macd_hist is not None else 'N/A'}
  SMA 50:         {f'{tech.sma_50:,.2f}' if tech.sma_50 is not None else 'N/A'}
  SMA 200:        {f'{tech.sma_200:,.2f}' if tech.sma_200 is not None else 'N/A'}
  MA trend:       {tech.ma_trend}
  Composite:      {tech.composite_score:+.2f} (-1 bearish .. +1 bullish)

NEWS SENTIMENT (engine: {sentiment.engine})
  Average score:  {sentiment.average_score:+.3f} (-1..+1)
  Label:          {sentiment.label}
  Breakdown:      {sentiment.positive} positive / {sentiment.neutral} neutral / {sentiment.negative} negative

PER-ARTICLE SENTIMENT
{sentiment_details}

RECOMMENDATION
  Action:         {rec.action}
  Confidence:     {rec.confidence}%
  Engine:         {rec.engine}
  Rationale:      {rec.rationale}

RECENT HEADLINES
{headlines}
"""


# --------------------------------------------------------------------------- #
# Groq (Llama) — primary free engine
# --------------------------------------------------------------------------- #
def _chat_groq(
    system: str,
    user_message: str,
    history: List[Tuple[str, str]],
) -> str:
    from groq import Groq

    client = Groq(api_key=settings.groq_api_key)

    messages = [{"role": "system", "content": system}]
    for role, text in history:
        messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=0.4,
        max_tokens=1024,
    )
    engine = f"Groq ({settings.groq_model})"
    print(f"[AI AUDIT] Chatbot called. Engine: {engine}")
    return response.choices[0].message.content, engine


# --------------------------------------------------------------------------- #
# Gemini — fallback free engine
# --------------------------------------------------------------------------- #
def _chat_gemini(
    system: str,
    user_message: str,
    history: List[Tuple[str, str]],
) -> str:
    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)

    contents = [
        {"role": "user", "parts": [{"text": system + "\n\n(System context loaded.)"}]},
        {"role": "model", "parts": [{"text": "Understood. I have the full analysis context. How can I help?"}]},
    ]
    for role, text in history:
        gemini_role = "user" if role == "user" else "model"
        contents.append({"role": gemini_role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=contents,
    )
    engine = f"Gemini ({settings.gemini_model})"
    print(f"[AI AUDIT] Chatbot called. Engine: {engine}")
    return response.text, engine


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def chat(
    user_message: str,
    context: str,
    history: List[Tuple[str, str]],
) -> tuple[str, str]:
    """
    Send a message using the best available free engine.

    Returns
    -------
    tuple of (response_text, engine_name)
    """
    system = SYSTEM_INSTRUCTION.format(context=context)

    if settings.groq_enabled:
        try:
            return _chat_groq(system, user_message, history)
        except Exception as exc:
            print(f"[AI AUDIT] Groq failed: {exc}")

    if settings.gemini_enabled:
        try:
            return _chat_gemini(system, user_message, history)
        except Exception as exc:
            print(f"[AI AUDIT] Gemini failed: {exc}")

    raise RuntimeError(
        "No chatbot engine available. Add a GROQ_API_KEY (free at https://console.groq.com) "
        "or GEMINI_API_KEY to your .env file."
    )
