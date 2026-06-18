# ארכיטקטורת המערכת — AI Investment Advisor

מסמך זה מתאר את הארכיטקטורה המלאה של האפליקציה: השכבות, רכיביהן, זרימת
הנתונים והחלטות התכן המרכזיות.

---

## 1. סקירה כללית

המערכת בנויה בתבנית **שכבות (Layered Architecture)** עם הפרדת אחריות ברורה:
שכבת תצוגה (UI), שכבת תזמור (Orchestration), שכבת ניתוח (Analysis), ושכבת
נתונים (Data Access). כל מודול הוא יחידה עצמאית וניתנת לבדיקה.

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                            │
│   app.py  (Streamlit)        +     src/ui/components.py           │
│   • קלט Ticker               •     בניית גרף Plotly                │
│   • תצוגת מחיר/חדשות/המלצה    •     רכיבי תצוגה                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │  קורא ל-pipeline
┌───────────────────────────────▼─────────────────────────────────┐
│                    ORCHESTRATION LAYER                            │
│   main() ב-app.py — מתזמר את כל השלבים ברצף, עם caching וטיפול     │
│   בשגיאות (try/except) ומשוב התקדמות (spinners).                  │
└───────┬───────────────┬─────────────────┬───────────────┬───────┘
        │               │                 │               │
┌───────▼──────┐ ┌──────▼──────┐ ┌────────▼───────┐ ┌─────▼────────┐
│  DATA LAYER  │ │  DATA LAYER │ │ ANALYSIS LAYER │ │ ANALYSIS     │
│ market_data  │ │  news_data  │ │   sentiment    │ │ technical    │
│ (Yahoo Fin.) │ │  (NewsAPI)  │ │ (FinBERT/VADER)│ │ (RSI/MACD/MA)│
└───────┬──────┘ └──────┬──────┘ └────────┬───────┘ └─────┬────────┘
        │               │                 │               │
        │  Quote +      │  Article[]      │ SentimentRes. │ TechSummary
        │  History      │                 │               │
        └───────────────┴────────┬────────┴───────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │       AI LAYER          │
                    │     src/ai/advisor.py   │
                    │  LLM (OpenAI) או מנוע    │
                    │  גיבוי מבוסס-חוקים        │
                    │  → Recommendation        │
                    └────────────┬────────────┘
                                 │
                                 ▼
                        חוזר ל-UI לתצוגה
```

---

## 2. תיאור רכיבים

### 2.1 שכבת הנתונים (Data Layer)

**`src/data/market_data.py`**
- אחראי על משיכת נתוני מחיר מ-Yahoo Finance דרך `yfinance` (ללא צורך במפתח).
- `get_quote(ticker)` → אובייקט `Quote` (מחיר, שינוי יומי, שווי שוק, סקטור).
- `get_history(ticker, period, interval)` → `DataFrame` של OHLCV.
- זורק `MarketDataError` בסימול שגוי, כדי שה-UI יציג הודעה ידידותית.

**`src/data/news_data.py`**
- מושך כותרות מ-NewsAPI דרך `requests`.
- `get_news(query)` → רשימת `Article`.
- *Graceful degradation:* ללא מפתח או בכשל רשת — מחזיר רשימה ריקה במקום לקרוס.

### 2.2 שכבת הניתוח (Analysis Layer)

**`src/analysis/technical.py`**
- מימוש מפורש ב-pandas של כל האינדיקטורים (שקיפות לבודק):
  - **RSI(14)** — החלקת Wilder.
  - **MACD(12,26,9)** — הפרש EMA + קו אות + היסטוגרמה.
  - **SMA 50 / SMA 200** — ממוצעים נעים פשוטים.
- `analyze(history)` → `TechnicalSummary` הכולל **ציון משוקלל** ב-[-1, +1]
  שמשמש עוגן כמותי להמלצה.

**`src/analysis/sentiment.py`**
- מנוע ראשי: **FinBERT** (`ProsusAI/finbert`) דרך Transformers.
- מנוע גיבוי: **VADER** (NLTK) — קל משקל, ללא הורדת מודל כבד.
- `score_articles(articles)` → `SentimentResult` (ציון מצרפי + פירוט לכל כותרת).

### 2.3 שכבת ה-AI (AI Layer)

**`src/ai/advisor.py`**
- מקבל `Quote` + `TechnicalSummary` + `SentimentResult`.
- בונה prompt מובנה ושולח ל-OpenAI עם `response_format=json_object`.
- ממיר את התשובה ל-`Recommendation` (action, confidence, rationale, key_points).
- **מנוע גיבוי שקוף**: כשאין מפתח OpenAI, משקלל טכני (70%) + סנטימנט (30%)
  לכלל החלטה דטרמיניסטית — כך הפרויקט רץ מקצה-לקצה גם ללא עלות.

### 2.4 שכבת התצוגה (Presentation Layer)

**`app.py`** — תזמור + פריסת Streamlit, caching (`st.cache_data`), טיפול בשגיאות.
**`src/ui/components.py`** — בניית גרף Plotly תלת-שורתי (מחיר+ממוצעים / MACD / RSI).

### 2.5 הגדרות (Configuration)

**`config.py`** — מחלקת `Settings` קפואה (frozen dataclass) שקוראת מפתחות
ופרמטרים ממשתני סביבה, עם תכונות `openai_enabled` / `news_enabled`.

---

## 3. זרימת נתונים מקצה-לקצה

1. **קלט:** המשתמש מזין Ticker ולוחץ *Analyze*.
2. **שוק:** `load_quote` + `load_history` (caching ל-5 דקות).
3. **חדשות:** `load_news(company_name)`.
4. **סנטימנט:** `score_articles` → ציון [-1, +1].
5. **טכני:** `analyze(history)` → אינדיקטורים + ציון משוקלל.
6. **AI:** `get_recommendation` → Buy / Hold / Sell + נימוק.
7. **פלט:** רינדור מחיר, גרף, חדשות, סנטימנט, אינדיקטורים והמלצה.

---

## 4. החלטות תכן מרכזיות

| החלטה | נימוק |
|-------|-------|
| Streamlit ולא React | קוד Python אחיד, פריסה מהירה, מתאים לאפליקציית דאטה. |
| `yfinance` ולא Yahoo רשמי בתשלום | חינמי, יציב, ללא מפתח. |
| FinBERT + נפילה ל-VADER | דיוק פיננסי גבוה כשאפשר, עמידות בסביבות מוגבלות. |
| מנוע גיבוי מבוסס-חוקים ל-LLM | המערכת רצה ונבדקת גם ללא מפתח/קרדיט. |
| ציון משוקלל [-1,+1] | עוגן כמותי אחיד ל-LLM ולמנוע הגיבוי כאחד. |
| `st.cache_data` | מצמצם קריאות API חוזרות ומשפר חוויית משתמש. |

---

## 5. טיפול בשגיאות ועמידות

- כל קריאת רשת עטופה ב-`try/except` עם נפילה רכה.
- סימול שגוי → הודעת שגיאה ידידותית ב-UI (לא קריסה).
- ללא מפתחות → מנועי גיבוי שומרים על תפקוד מלא של הצינור.
