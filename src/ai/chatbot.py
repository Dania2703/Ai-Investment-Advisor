"""
src/ai/chatbot.py
=================
Conversational AI assistant for the stock-analysis dashboard.

Engine priority:
  1. Groq  (free Llama 3.3 70B)
  2. Gemini (free tier fallback)
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


def _v(value, digits: int) -> str:
    """Format an optional number, falling back to 'N/A'."""
    return f"{value:,.{digits}f}" if value is not None else "N/A"


def build_context(quote, tech, sentiment, rec, articles) -> str:
    headlines = "\n".join(
        f"  - {a.title}" for a in (articles or [])[:8]
    ) or "  (no news available)"

    sentiment_details = "  (no per-article scores available)"
    if sentiment.details:
        sentiment_details = "\n".join(
            f"  - [{d.label} {d.score:+.2f}] {d.title}"
            for d in sentiment.details[:8]
        )

    return f"""\
COMPANY
  Ticker:         {quote.ticker}
  Name:           {quote.name}
  Sector:         {quote.sector or 'N/A'}
  Current price:  {quote.price:,.2f} {quote.currency}
  Previous close: {quote.previous_close:,.2f}
  Daily change:   {quote.change:+.2f} ({quote.change_pct:+.2f}%)
  Market cap:     {f'{quote.market_cap/1e9:,.1f} B' if quote.market_cap else 'N/A'}

TECHNICAL INDICATORS (native, TradingView-aligned)
  RSI(14):        {_v(tech.rsi, 1)} -> {tech.rsi_signal}
  MACD:           {_v(tech.macd, 3)} -> {tech.macd_trend} (hist {_v(tech.macd_hist, 3)})
  StochRSI %K/%D: {_v(tech.stoch_rsi_k, 0)} / {_v(tech.stoch_rsi_d, 0)}
  SMA 50 / 200:   {_v(tech.sma_50, 2)} / {_v(tech.sma_200, 2)}  ({tech.ma_trend})
  EMA 20/50/200:  {_v(tech.ema_20, 2)} / {_v(tech.ema_50, 2)} / {_v(tech.ema_200, 2)}
  ADX(14):        {_v(tech.adx, 1)} (+DI {_v(tech.plus_di, 1)} / -DI {_v(tech.minus_di, 1)})
  Bollinger %B:   {_v(tech.bb_percent_b, 2)}  (upper {_v(tech.bb_upper, 2)} / lower {_v(tech.bb_lower, 2)})
  ATR(14):        {_v(tech.atr, 2)} ({_v(tech.atr_pct, 2)}% of price)
  OBV trend:      {'rising (accumulation)' if (tech.obv or 0) > (tech.obv_ema or 0) else 'falling (distribution)'}
  Volume vs 20d:  {_v(tech.volume_ratio, 2)}x
  Support/Resist: {_v(tech.support, 2)} / {_v(tech.resistance, 2)}

NEWS SENTIMENT (engine: {sentiment.engine})
  Average score:  {sentiment.average_score:+.3f} (-1..+1)
  Label:          {sentiment.label}
  Breakdown:      {sentiment.positive} positive / {sentiment.neutral} neutral / {sentiment.negative} negative

PER-ARTICLE SENTIMENT
{sentiment_details}

RECOMMENDATION (decided by the deterministic scoring engine)
  Rating:         {rec.rating}
  Final score:    {rec.final_score:.1f} / 100
  Confidence:     {rec.confidence}%
  Engine:         {rec.engine}
  Summary:        {rec.rationale}

RECENT HEADLINES
{headlines}
"""


def _chat_groq(system: str, user_message: str, history: List[Tuple[str, str]]) -> tuple[str, str]:
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
    return response.choices[0].message.content, engine


def _chat_gemini(system: str, user_message: str, history: List[Tuple[str, str]]) -> tuple[str, str]:
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
    return response.text, engine


def chat(
    user_message: str,
    context: str,
    history: List[Tuple[str, str]],
) -> tuple[str, str]:
    """Send a message using the best available free engine."""
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
        "No chatbot engine available. Add a GROQ_API_KEY or GEMINI_API_KEY to your .env file."
    )
