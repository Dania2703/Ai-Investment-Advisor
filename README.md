# 📈 AI Investment Advisor — יועץ השקעות מבוסס בינה מלאכותית

> פרויקט גמר · קורס *"בינה מלאכותית וחדשנות בשוק ההון"* · מסלול 3 — אפליקציית AI למשקיעים

אפליקציית ווב שמקבלת **סימול מניה (Ticker)**, מושכת נתוני שוק וחדשות בזמן אמת,
מנתחת סנטימנט באמצעות מודל AI, מחשבת אינדיקטורים טכניים, ולבסוף מפעילה מודל
שפה גדול (LLM) שמפיק **המלצת השקעה מנומקת: Buy / Hold / Sell**.

---

## ✨ תכונות עיקריות (Features)

| # | יכולת | מקור / טכנולוגיה |
|---|-------|------------------|
| 1 | מחיר ונתוני שוק בזמן אמת | Yahoo Finance (`yfinance`) |
| 2 | גרף נרות + ממוצעים נעים + MACD + RSI | Plotly |
| 3 | חדשות פיננסיות אחרונות | NewsAPI |
| 4 | ניתוח סנטימנט בעזרת AI | FinBERT (Transformers) + נפילה רכה ל-VADER |
| 5 | אינדיקטורים טכניים | RSI · MACD · SMA 50 · SMA 200 |
| 6 | המלצת השקעה מנומקת | OpenAI LLM + מנוע גיבוי מבוסס-חוקים |
| 7 | ממשק משתמש אינטראקטיבי | Streamlit |

> **חשוב:** הכלי חינוכי בלבד ואינו מהווה ייעוץ השקעות.

---

## 🏗️ ארכיטקטורה (Architecture)

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
   (Yahoo Fin.)   (NewsAPI)     (FinBERT/      (RSI, MACD,
                                 VADER)         SMA50/200)
          │            │              │            │
          └────────────┴──────┬───────┴────────────┘
                              ▼
                     AI Advisor (LLM)
                  Buy / Hold / Sell + נימוק
                              ▼
                    Streamlit UI Output
```

תרשים מפורט יותר נמצא ב-[`docs/architecture.md`](docs/architecture.md).

---

## 📁 מבנה תיקיות (Project Structure)

```
ai-investment-advisor/
├── app.py                     # אפליקציית Streamlit + תזמור הצינור (pipeline)
├── config.py                  # הגדרות וקריאת מפתחות מהסביבה
├── requirements.txt           # תלויות
├── .env.example               # תבנית משתני סביבה
├── .gitignore
├── README.md
├── src/
│   ├── data/
│   │   ├── market_data.py      # Yahoo Finance — מחיר + היסטוריה
│   │   └── news_data.py        # NewsAPI — חדשות אחרונות
│   ├── analysis/
│   │   ├── technical.py        # RSI, MACD, SMA50, SMA200 + ציון משוקלל
│   │   └── sentiment.py        # ניתוח סנטימנט (FinBERT / VADER)
│   ├── ai/
│   │   └── advisor.py          # LLM — המלצה מנומקת + מנוע גיבוי
│   └── ui/
│       └── components.py       # בניית הגרף ורכיבי תצוגה
└── docs/
    ├── architecture.md         # תיעוד ארכיטקטורה
    ├── presentation_script.md  # תסריט מצגת 5 דקות
    └── project_summary.pdf     # מסמך מסכם (עד 5 עמודים)
```

---

## 🚀 התקנה והרצה מקומית (Local Setup)

דרישה מוקדמת: **Python 3.10+**

```bash
# 1. שכפול / כניסה לתיקיית הפרויקט
cd ai-investment-advisor

# 2. יצירת סביבה וירטואלית
python -m venv .venv
source .venv/bin/activate        # ב-Windows: .venv\Scripts\activate

# 3. התקנת תלויות
pip install -r requirements.txt

# 4. הגדרת מפתחות
cp .env.example .env
#    ערכו את .env והכניסו את OPENAI_API_KEY ו-NEWS_API_KEY שלכם

# 5. הרצה
streamlit run app.py
```

האפליקציה תיפתח בדפדפן בכתובת `http://localhost:8501`.

### 🔑 מפתחות API

| משתנה | היכן משיגים | חובה? |
|-------|-------------|-------|
| `OPENAI_API_KEY` | https://platform.openai.com | אופציונלי — ללא מפתח, פועל מנוע גיבוי מבוסס-חוקים |
| `NEWS_API_KEY` | https://newsapi.org (חינמי) | אופציונלי — ללא מפתח, פאנל החדשות פשוט מדלג |

> **תכנון עמיד:** המערכת רצה מקצה-לקצה גם ללא אף מפתח, כך שניתן להריץ ולבדוק
> את הפרויקט מיד. עם מפתחות — מתקבלות המלצות LLM אמיתיות וחדשות חיות.

---

## ☁️ פריסה (Deployment)

הסבר מלא נמצא בהמשך הקובץ — ראו סעיף [פריסה ל-Hugging Face / Render](#-פריסה-לhugging-face-spaces-או-render).

---

## 🧠 איך זה עובד — צינור הנתונים (Pipeline)

1. המשתמש מזין **Ticker** (לדוגמה `AAPL`).
2. `market_data` מושך מחיר נוכחי + היסטוריה של שנה מ-Yahoo Finance.
3. `news_data` מושך עד 10 כותרות אחרונות מ-NewsAPI.
4. `sentiment` מדרג כל כותרת (חיובי/שלילי/נייטרלי) ומחשב ציון מצרפי ב-[-1, +1].
5. `technical` מחשב RSI(14), MACD(12,26,9), SMA50, SMA200 ו**ציון משוקלל**.
6. `advisor` (LLM) משקלל את הכל ומפיק **Buy / Hold / Sell** + רמת ביטחון + נימוק.
7. ה-UI מציג מחיר, גרף, חדשות, סנטימנט, אינדיקטורים, המלצה והסבר מפורט.

---

## ☁️ פריסה ל-Hugging Face Spaces או Render

### אפשרות א׳ — Hugging Face Spaces (מומלץ, חינמי)

1. צרו חשבון ב-https://huggingface.co וצרו **Space** חדש מסוג **Streamlit**.
2. העלו את כל קבצי הפרויקט (או חברו את ה-Space ל-Git repo).
3. ודאו ש-`requirements.txt` נמצא בשורש — HF יתקין אוטומטית.
4. ב-**Settings → Variables and secrets** הוסיפו:
   - `OPENAI_API_KEY`
   - `NEWS_API_KEY`
5. ה-Space יבנה ויריץ את `app.py` אוטומטית. זהו.

> טיפ: בטיר החינמי, FinBERT עלול לחרוג מהזיכרון. המערכת תיפול אוטומטית ל-VADER —
> ניתוח הסנטימנט ימשיך לעבוד ללא תקלה.

### אפשרות ב׳ — Render

1. דחפו את הקוד ל-GitHub.
2. ב-https://render.com צרו **New → Web Service** וחברו את ה-repo.
3. הגדרות:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:**
     `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
4. תחת **Environment** הוסיפו את `OPENAI_API_KEY` ו-`NEWS_API_KEY`.
5. **Create Web Service** — Render יבנה ויפרוס.

---

## 🔭 פיתוח עתידי ומגבלות

### רעיונות לפיתוח עתידי
- תיק השקעות מרובה-מניות עם מתאם וסיכון (Sharpe, beta).
- התראות אוטומטיות (מייל / Telegram) על שינוי המלצה.
- Backtesting — בדיקת ביצועי האסטרטגיה היסטורית.
- מקורות נוספים: דוחות כספיים, נתוני מאקרו, סנטימנט מ-Reddit/X.
- שמירת היסטוריית ניתוחים במסד נתונים (SQLite / Postgres).
- תמיכה בעברית מלאה ב-UI ובנימוקי ה-LLM.

### מגבלות המערכת
- **לא ייעוץ פיננסי** — כלי חינוכי בלבד.
- נתוני Yahoo Finance עלולים להתעכב ואינם מובטחים בדיוק "live" מלא.
- האיכות תלויה בכיסוי החדשות של NewsAPI (אנגלית בעיקר).
- FinBERT דורש זיכרון; בסביבות מוגבלות עוברים ל-VADER (פחות מדויק).
- ה-LLM עלול לשגות; ההמלצה אינדיקטיבית ולא דטרמיניסטית.
- האינדיקטורים מסתכלים אחורה (lagging) ולא חוזים שינויי מגמה חדים.

---

## 📜 רישיון ואחריות

פרויקט אקדמי לצורכי לימוד. אין להסתמך על הפלט לקבלת החלטות השקעה אמיתיות.

---

## 👤 קרדיט

נבנה כפרויקט גמר לקורס *בינה מלאכותית וחדשנות בשוק ההון* — מסלול 3.
