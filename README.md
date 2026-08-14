---
title: AI Investment Advisor
emoji: 📈
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# 📈 AI Investment Advisor

AI-powered stock analysis tool that combines technical indicators, news sentiment, and LLM reasoning to produce educational Buy / Hold / Sell recommendations.

> Final project · *AI & Innovation in Capital Markets* · Track 3

## 🔗 Live Demo: https://drive.google.com/file/d/16c3wb9lCzy5vPxlKgBZIckp6_XxQsRZK/view?usp=drive_link

**[ai-investment-advisor-0.streamlit.app](https://ai-investment-advisor-0.streamlit.app/)**

Deployed on Streamlit Community Cloud, built directly from this repository's `main` branch (`app.py`, `requirements.txt`).

---

## Tech Stack

| Component | Technology |
|---|---|
| **Frontend** | Streamlit — multi-page (landing · login · register · dashboard) with a custom dark fintech theme |
| **Auth** | SQLAlchemy users + PBKDF2 password hashing + signed session tokens |
| **User DB** | Postgres in production (via `DATABASE_URL`), SQLite fallback for local dev |
| **Market Data** | Finnhub (quote) · yfinance (clean OHLCV history) |
| **News** | Finnhub News API |
| **Indicators** | Native NumPy/pandas, TradingView-aligned (RSI, MACD, SMA50/200, EMA20/50/200, Bollinger, Stochastic RSI, ADX, ATR, OBV, Volume SMA, Support/Resistance) |
| **Decision** | Deterministic weighted scoring engine (0–100) |
| **AI Model** | OpenAI GPT-4.1 — *explains* the score, does not decide it |
| **Sentiment** | FinBERT (fallback: VADER) |
| **Charts** | TradingView Lightweight Charts (dark theme) |
| **Chatbot** | Floating RAG assistant — Groq (Llama 3.3) / Gemini |
| **Deployment** | Streamlit Community Cloud ([live demo](https://ai-investment-advisor-0.streamlit.app/)) — a `Dockerfile` is also included for Docker-based hosts |

### Folder structure

```
app.py                       # thin entry point: theme + session restore + router
config.py                    # env-driven settings (API keys, DATABASE_URL, SECRET_KEY)
src/
  auth/                      # authentication layer
    models.py                #   SQLAlchemy User + SavedAnalysis, engine/session
    service.py               #   register/login, PBKDF2 hashing, signed tokens, history
  data/                      # service layer (market_data, news_data, database)
  analysis/                  # analysis layer (indicators, technical, sentiment, scoring)
  ai/                        # AI layer (advisor narration, RAG chatbot)
  ui/                        # presentation layer
    theme.py                 #   design system + global dark CSS
    nav.py                   #   session-state router
    components.py            #   TradingView chart
    chatbot_widget.py        #   floating bottom-right assistant
    pages/                   #   landing.py · auth_view.py · dashboard.py
```

The dashboard renders in a fixed order: **AI Executive Summary → Market Snapshot
→ Technical Indicators → Interactive Chart → News Analysis → Detailed AI Analysis
→ Saved History**, with clickable source links (Yahoo, Finnhub, SEC EDGAR,
Investor Relations, news) so every figure is verifiable. When data can't be
retrieved the UI shows **"Data unavailable"** — never a fabricated value.

---

## Architecture

The key design principle: **the scoring engine decides, the LLM explains.**
The rating is produced by a transparent, deterministic, weighted score — so the
same inputs always yield the same recommendation. GPT-4.1 only narrates it.

```
User ──> Streamlit UI (app.py)
                │
                ▼
        ┌───────────────────────────────────────────┐
        │              Pipeline / Orchestrator        │
        └───────────────────────────────────────────┘
          │            │              │            │
          ▼            ▼              ▼            ▼
   Market Data    News Data     Sentiment     Technical
   (Finnhub +    (Finnhub)     (FinBERT/     (indicators.py:
    yfinance)                   VADER)        RSI, MACD, SMA,
                                              EMA, Bollinger,
                                              StochRSI, ADX,
                                              ATR, OBV, S/R)
          │            │              │            │
          └────────────┴──────┬───────┴────────────┘
                              ▼
              ┌───────────────────────────────────┐
              │   Scoring Engine (scoring.py)      │
              │   Trend 40% · Momentum 25% ·       │
              │   Volume 15% · Volatility 10% ·    │
              │   Sentiment 10%  ──>  0–100 score  │
              │   0-30 Strong Sell ... 71+ Strong Buy │
              └───────────────────────────────────┘
                              ▼
                   AI Advisor (advisor.py)
            GPT-4.1 EXPLAINS the score (never overrides it)
            → technical summary, sentiment, risks, rationale
                              ▼
        TradingView Charts + transparency panels (UI)
                              ▼
                        SQLite (save)
```

### Scoring methodology

| Category | Weight | Drivers |
|---|---|---|
| **Trend** | 40% | Price vs SMA200/SMA50 · SMA50 vs SMA200 · EMA20/50/200 stack · ADX trend confirmation |
| **Momentum** | 25% | RSI · MACD · Stochastic RSI |
| **Volume** | 15% | OBV trend (accumulation/distribution) · volume-spike confirmation |
| **Volatility** | 10% | ATR % of price · Bollinger %B position |
| **Sentiment** | 10% | FinBERT / VADER news sentiment |

Each category scores 0–100 from graded sub-signals; the final score is the
weighted blend, with weights **renormalised** over categories that have enough
data. Rating bands: `0–30` Strong Sell · `31–45` Sell · `46–55` Hold ·
`56–70` Buy · `71–100` Strong Buy.

### Why results used to disagree with TradingView

The previous engine used `pandas-ta` defaults, which mix smoothing conventions.
TradingView uses **Wilder's RMA** for RSI/ATR/ADX, **EMA** for MACD, and
**population standard deviation** for Bollinger Bands. The indicators are now
implemented natively with exactly those conventions, with no look-ahead bias
(the still-forming daily bar is dropped) and timezone-normalised data — which
removes the spurious disagreements while keeping a richer, explainable
methodology (we improve on TradingView rather than copy it).

---

## Setup

```bash
# 1. Clone
git clone https://github.com/Dania2703/Ai-Investment-Advisor.git
cd Ai-Investment-Advisor

# 2. Install
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env and add your API keys

# 4. Run
streamlit run app.py
```

# 1. Activate the venv
.\.venv\Scripts\Activate.ps1

# 2. Launch the app
.venv/Scripts/python.exe -m pip install -r requirements.txt
source .venv/Scripts/activate


## API Keys

| Key | Source | Cost |
|---|---|---|
| `FINNHUB_API_KEY` | [finnhub.io](https://finnhub.io) | Free (60 calls/min) |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) | Paid (fallback: deterministic rule-based narrator) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Free (chatbot) |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | Free (chatbot fallback) |

> The rating never depends on an API key — the scoring engine is fully local.
> API keys only affect the *narration* (OpenAI) and the chatbot (Groq/Gemini).

---

## Testing

```bash
# Offline unit tests (indicator maths, no-look-ahead, scoring engine)
pytest

# Live validation against AAPL / MSFT / NVDA / AMZN / TSLA (needs network);
# prints each indicator + rating for eyeballing against TradingView
pytest -s -m network
```

`tests/test_indicators.py` verifies each indicator against closed-form values,
checks bounds/NaN warm-up/alignment, and proves there is **no look-ahead bias**
(truncating future bars never changes past values). `tests/test_scoring.py`
verifies rating thresholds, directionality, weight renormalisation and
determinism. `tests/test_validation.py` runs sanity checks on real tickers.

---

## Deployment

**Live app:** [ai-investment-advisor-0.streamlit.app](https://ai-investment-advisor-0.streamlit.app/)

---

## Disclaimer

This is an educational tool, not financial advice. Always do your own research and consult a licensed professional before investing.

---

Built as a final project for *AI & Innovation in Capital Markets* course — Track 3.
