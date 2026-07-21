"""
Generate the Hebrew (RTL) project-summary PDF (up to 5 pages) using ReportLab.
Hebrew text is reshaped for right-to-left display with python-bidi.
"""

from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable,
)

# ---- Register Hebrew-capable fonts ----------------------------------------
pdfmetrics.registerFont(TTFont("Rubik", "assets/fonts/Rubik-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Rubik-Bold", "assets/fonts/Rubik-Bold.ttf"))

# ---- Palette (navy / teal / gold) -----------------------------------------
NAVY = colors.HexColor("#1A2A4F")
TEAL = colors.HexColor("#0694A2")
GOLD = colors.HexColor("#C99700")
LIGHT = colors.HexColor("#F2F5FA")
GREY = colors.HexColor("#555555")


def rtl(text: str) -> str:
    """Reorder a Hebrew string for correct RTL visual display."""
    return get_display(text)


# ---- Paragraph styles ------------------------------------------------------
styles = getSampleStyleSheet()

H1 = ParagraphStyle("H1", parent=styles["Title"], fontName="Rubik-Bold",
                    fontSize=22, textColor=NAVY, alignment=TA_RIGHT, leading=28,
                    spaceAfter=2)
SUB = ParagraphStyle("SUB", fontName="Rubik", fontSize=11, textColor=TEAL,
                     alignment=TA_RIGHT, leading=16, spaceAfter=10)
H2 = ParagraphStyle("H2", fontName="Rubik-Bold", fontSize=14, textColor=NAVY,
                    alignment=TA_RIGHT, leading=20, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("BODY", fontName="Rubik", fontSize=10.2, textColor=colors.black,
                      alignment=TA_RIGHT, leading=16, spaceAfter=4)
BULLET = ParagraphStyle("BULLET", parent=BODY, rightIndent=14, spaceAfter=2)
SMALL = ParagraphStyle("SMALL", fontName="Rubik", fontSize=8.5, textColor=GREY,
                       alignment=TA_CENTER, leading=12)
CELL = ParagraphStyle("CELL", fontName="Rubik", fontSize=9.5, textColor=colors.black,
                      alignment=TA_RIGHT, leading=13)
CELLB = ParagraphStyle("CELLB", fontName="Rubik-Bold", fontSize=9.5, textColor=colors.white,
                       alignment=TA_RIGHT, leading=13)


def p(text, style=BODY):
    return Paragraph(rtl(text), style)


def bullet(text):
    return Paragraph("• " + rtl(text), BULLET)


def section_rule():
    return HRFlowable(width="100%", thickness=1, color=GOLD, spaceBefore=4, spaceAfter=6)


# ---- Build story -----------------------------------------------------------
story = []

# Title block
story.append(p("יועץ השקעות מבוסס בינה מלאכותית", H1))
story.append(p("AI Investment Advisor · פרויקט גמר — מסלול 3", SUB))
story.append(section_rule())

# 1. Overview
story.append(p("1. תקציר הפרויקט", H2))
story.append(p(
    "אפליקציית Streamlit מלאה עם הרשמה והתחברות (SQLAlchemy + PBKDF2). לאחר "
    "כניסה, המשתמש מזין סימול מניה (Ticker) ומפעיל בלחיצת כפתור צינור ניתוח "
    "שלם: משיכת נתוני שוק וחדשות בזמן אמת, חישוב אינדיקטורים טכניים native "
    "(תואמי-TradingView), הפעלת מנוע ניקוד דטרמיניסטי (0–100), ונרטיב הסבר "
    "מ-GPT-4.1 שמנסח את הציון ואינו קובע אותו. כל ניתוח נשמר להיסטוריית "
    "המשתמש. הכלי חינוכי בלבד ואינו מהווה ייעוץ פיננסי."))

# 2. Goals
story.append(p("2. מטרות ודרישות", H2))
story.append(bullet("Frontend ב-Streamlit (רב-עמודי: נחיתה/הרשמה/דשבורד) ו-Backend ב-Python."))
story.append(bullet("שכבת אימות משתמשים (SQLAlchemy) עם היסטוריית ניתוחים שמורה."))
story.append(bullet("חיבור ל-Finnhub למחיר חי וחדשות, ול-yfinance להיסטוריית OHLCV."))
story.append(bullet("מנוע ניקוד דטרמיניסטי ושקוף המשלב אינדיקטורים טכניים וסנטימנט AI (FinBERT)."))
story.append(bullet("GPT-4.1 מנסח נרטיב הסבר על בסיס הציון; צ'אטבוט צף מקורקע בנתונים חיים."))

# 3. Architecture
story.append(p("3. ארכיטקטורה", H2))
story.append(p(
    "המערכת בנויה בתבנית שכבות: אימות (Auth) → נתונים (Data) → ניתוח "
    "(Analysis) → מנוע ניקוד (Scoring) → AI (נרטיב + צ'אטבוט) → תצוגה "
    "(Streamlit). העיקרון המנחה: מנוע הניקוד הדטרמיניסטי מחליט, וה-LLM "
    "רק מסביר — כך שאותם נתונים תמיד מניבים אותה המלצה, וה-AI לא יכול "
    "להטות את הדירוג עצמו."))

# Architecture flow table (visual, RTL order)
flow = [
    [p("פלט: דשבורד + נרטיב GPT + צ'אטבוט מקורקע + שמירה להיסטוריה", CELLB)],
    [p("שכבת AI — GPT-4.1 מנסח את הציון (אינו קובע אותו)", CELL)],
    [p("מנוע ניקוד — Trend 35% · Momentum 25% · Volume 15% · Volatility 10% · Sentiment 10% · Risk 5%", CELL)],
    [p("שכבת ניתוח — אינדיקטורים native (RSI/MACD/EMA/Bollinger/ADX/ATR/OBV) + סנטימנט (FinBERT)", CELL)],
    [p("שכבת נתונים — Finnhub (מחיר/חדשות) + yfinance (היסטוריה)", CELL)],
    [p("שכבת אימות — הרשמה/התחברות (SQLAlchemy) · טוקן session חתום", CELL)],
]
flow_tbl = Table(flow, colWidths=[16 * cm])
flow_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (0, 0), NAVY),
    ("BACKGROUND", (0, 1), (0, 1), LIGHT),
    ("BACKGROUND", (0, 2), (0, 2), colors.white),
    ("BACKGROUND", (0, 3), (0, 3), LIGHT),
    ("BACKGROUND", (0, 4), (0, 4), colors.white),
    ("BOX", (0, 0), (-1, -1), 0.5, NAVY),
    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
]))
story.append(Spacer(1, 4))
story.append(flow_tbl)

# 4. Tech stack table
story.append(p("4. מחסנית טכנולוגית", H2))
stack_rows = [
    [p("טכנולוגיה", CELLB), p("רכיב", CELLB)],
    [p("Streamlit (רב-עמודי)", CELL), p("ממשק משתמש (Frontend)", CELL)],
    [p("Python · pandas · numpy", CELL), p("Backend וחישובים", CELL)],
    [p("SQLAlchemy · PBKDF2", CELL), p("אימות משתמשים והיסטוריה", CELL)],
    [p("SQLite / Postgres", CELL), p("בסיס נתונים (DATABASE_URL)", CELL)],
    [p("Finnhub", CELL), p("מחיר חי וחדשות פיננסיות", CELL)],
    [p("yfinance", CELL), p("היסטוריית OHLCV (שנתיים)", CELL)],
    [p("FinBERT / VADER", CELL), p("ניתוח סנטימנט (AI)", CELL)],
    [p("OpenAI GPT-4.1", CELL), p("נרטיב הסבר להמלצה", CELL)],
    [p("Groq (Llama 3.3) / Gemini", CELL), p("צ'אטבוט צף מקורקע", CELL)],
    [p("TradingView Lightweight Charts", CELL), p("גרפים אינטראקטיביים", CELL)],
    [p("Docker · Hugging Face Spaces", CELL), p("פריסה", CELL)],
]
stack_tbl = Table(stack_rows, colWidths=[9 * cm, 7 * cm])
stack_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), TEAL),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
    ("BOX", (0, 0), (-1, -1), 0.5, TEAL),
    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDDDDD")),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
]))
story.append(stack_tbl)

# 5. Pipeline / how it works
story.append(p("5. אופן הפעולה — צינור הנתונים", H2))
story.append(bullet("המשתמש מתחבר/נרשם, מזין סימול מניה ולוחץ Analyze."))
story.append(bullet("מחיר חי מ-Finnhub + היסטוריית OHLCV לשנתיים מ-yfinance; עד 10 כותרות חדשות מ-Finnhub."))
story.append(bullet("מודול האינדיקטורים מחשב RSI/MACD/EMA/Bollinger/StochRSI/ADX/ATR/OBV; הסנטימנט מדורג ב-FinBERT."))
story.append(bullet("מודול correlation.py נועד לנטרל כפילויות בין אינדיקטורי מגמה מתואמים — טרם מחובר בפועל, ראו סעיף 6.1."))
story.append(bullet("scoring.py מפיק ציון 0–100 ורמת ביטחון (מרחק מ-50 + הסכמה בין קטגוריות)."))
story.append(bullet("GPT-4.1 מנסח רציונל בשפה טבעית על בסיס הציון; התוצאה נשמרת להיסטוריית המשתמש."))

# 6. Technical indicators & the scoring engine
story.append(p("6. האינדיקטורים ומנוע הניקוד", H2))
story.append(p(
    "כל אינדיקטור ממומש native ב-NumPy/pandas (לא ספריית pandas-ta), בקונבנציות "
    "התואמות ל-TradingView: Wilder's RMA ל-RSI/ATR/ADX, EMA למקד'ד (MACD), "
    "וסטיית תקן אוכלוסייה לרצועות בולינגר. הציון הסופי הוא שקלול של שש קטגוריות: "
    "Trend 35% · Momentum 25% · Volume 15% · Volatility 10% · Sentiment 10% "
    "(כמוגדר ב-config.py), כאשר כל אינדיקטור חושף ערך, אות ומידת תרומה לממוצע "
    "הקטגוריה — ללא קופסה שחורה. הערה: קיים גם משקל Risk Adjustment (5%) "
    "ב-config.py, אך אין כרגע קטגוריית סיכון פעילה ב-scoring.py — משקל מוגדר "
    "שטרם מומש."))

# 6b. The bug-fix story (audit) — reported honestly, including what's NOT wired yet
story.append(p("6.1 אבחון הטיה שיטתית — docs/AUDIT.md", H2))
story.append(p(
    "בבדיקה מול TradingView נמצא שהמנוע המקורי נטה בעקביות ל-'Strong Buy' גם "
    "כשאתרים אחרים סימנו Sell/Neutral. הסיבה שאובחנה: שישה-שבעה אינדיקטורי "
    "מגמה מתואמים (מחיר מול SMA50/200, חציות ממוצעים וכו') נספרים כקולות "
    "בלתי-תלויים, כך שתופעה אחת — מגמת עלייה — נספרת כמעט פי שש. הפתרון "
    "שנבנה ונבדק: מודול correlation.py, שמזהה אוטומטית אינדיקטורים מתואמים "
    "(מעל סף 0.85) ומאחד אותם למשקל cluster משותף. בכנות: המודול קיים "
    "ועובר בדיקות עצמאיות, אך נכון להגשה זו הוא עדיין לא מיובא או נקרא "
    "מ-scoring.py — קטגוריית Trend שם עדיין ממצעת את תת-האינדיקטורים "
    "באופן שווה. מה שכן יושם בפועל: הגבלת משקל המגמה ל-35% (בהשוואה ל-40% "
    "המקורי), ורכיב הסכמה-בין-קטגוריות שנוסף לחישוב רמת הביטחון. חיבור "
    "correlation.py לצינור הניקוד הוא פריט הפיתוח הבא בעדיפות הגבוהה ביותר. "
    "התהליך המלא מתועד ב-docs/AUDIT.md."))

# 7. Robustness / testing
story.append(p("7. עמידות ובדיקות", H2))
story.append(p(
    "מנוע הניקוד אינו תלוי במפתחות API — הוא רץ במלואו גם ללא OpenAI (רק הנרטיב "
    "מושבת); סנטימנט נופל מ-FinBERT ל-VADER בזיכרון מוגבל; והנר האחרון מסולק "
    "אוטומטית אם עדיין נסחר, למניעת look-ahead bias. נתון חסר מוצג כ-'Data "
    "unavailable' ולעולם לא מפוברק. סוויטת pytest (tests/) מוודאת ערכים סגורים "
    "לכל אינדיקטור, היעדר look-ahead bias, דטרמיניזם של הניקוד, ותקינות מול "
    "טיקרים אמיתיים."))

# 8. Limitations & future work
story.append(p("8. מגבלות ופיתוח עתידי", H2))
story.append(bullet("correlation.py קיים ובדוק אך לא מחובר בפועל ל-scoring.py — ראו סעיף 6.1."))
story.append(bullet("קטגוריית Risk Adjustment (5%) מוגדרת ב-config.py אך אינה ממומשת ב-scoring.py."))
story.append(bullet("רמת הביטחון עדיין תלויה במידה ניכרת במרחק הציון מ-50, לא רק בהסכמה בין קטגוריות."))
story.append(bullet("כלי חינוכי בלבד; אינדיקטורים מסתכלים אחורה; ציון גבוה אינו מבטיח תשואה."))
story.append(bullet("כיסוי חדשות באנגלית בעיקר; SQLite כברירת מחדל אינו מתאים לעומס מקבילי גבוה."))
story.append(bullet("עתיד: חיבור correlation.py לצינור (עדיפות ראשונה), מימוש קטגוריית הסיכון, Backtesting מלא."))
story.append(bullet("עתיד: תיק מרובה-מניות, התראות אוטומטיות, מקורות נוספים (דוחות SEC, מאקרו-כלכלה)."))

# 9. Deployment
story.append(p("9. פריסה", H2))
story.append(p(
    "האפליקציה ארוזה ב-Docker (Dockerfile בשורש הפרויקט) ומיועדת לפריסה כ-Space "
    "מסוג Docker ב-Hugging Face Spaces — קובץ ה-README כולל את ה-frontmatter "
    "הנדרש (sdk: docker, app_port: 7860). יש להגדיר את מפתחות ה-API ו-DATABASE_URL "
    "כ-Secrets בהגדרות ה-Space. פירוט מלא מופיע ב-README."))

# Footer disclaimer
story.append(Spacer(1, 8))
story.append(section_rule())
story.append(p("מסמך זה הוא תקציר פרויקט אקדמי. הכלי נועד להדגמה ולמידה בלבד "
               "ואינו מהווה ייעוץ השקעות.", SMALL))


# ---- Page template with footer --------------------------------------------
def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Rubik", 8)
    canvas.setFillColor(GREY)
    canvas.drawCentredString(A4[0] / 2, 1.0 * cm, rtl(f"AI Investment Advisor — עמוד {doc.page}"))
    canvas.restoreState()


doc = BaseDocTemplate(
    "docs/project_summary.pdf",
    pagesize=A4,
    rightMargin=2 * cm, leftMargin=2 * cm,
    topMargin=1.6 * cm, bottomMargin=1.6 * cm,
    title="AI Investment Advisor - Project Summary",
    author="Track 3 Capstone",
)
frame = Frame(doc.leftMargin, doc.bottomMargin,
              doc.width, doc.height, id="main")
doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=footer)])
doc.build(story)
print("PDF generated: docs/project_summary.pdf")
