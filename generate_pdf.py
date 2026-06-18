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
    "האפליקציה מקבלת סימול מניה (Ticker) ומבצעת בלחיצת כפתור צינור ניתוח שלם: "
    "משיכת נתוני שוק וחדשות בזמן אמת, ניתוח סנטימנט באמצעות מודל AI, חישוב "
    "אינדיקטורים טכניים, והפעלת מודל שפה גדול (LLM) שמפיק המלצת השקעה מנומקת — "
    "קנייה, החזקה או מכירה (Buy / Hold / Sell). המערכת מאחדת ניתוח טכני כמותי עם "
    "הקשר חדשותי איכותני תחת שכבת בינה מלאכותית אחת המסבירה את ההחלטה בשפה פשוטה. "
    "הכלי חינוכי בלבד ואינו מהווה ייעוץ פיננסי."))

# 2. Goals
story.append(p("2. מטרות ודרישות", H2))
story.append(bullet("Frontend ב-Streamlit ו-Backend ב-Python."))
story.append(bullet("חיבור ל-Yahoo Finance לנתוני מניות, ול-NewsAPI לחדשות."))
story.append(bullet("ניתוח סנטימנט של חדשות באמצעות מודל AI (FinBERT)."))
story.append(bullet("חישוב אינדיקטורים: RSI, MACD, ממוצע נע 50 וממוצע נע 200."))
story.append(bullet("מודל LLM המפיק המלצה מנומקת על בסיס כל הנתונים."))

# 3. Architecture
story.append(p("3. ארכיטקטורה", H2))
story.append(p(
    "המערכת בנויה בתבנית שכבות עם הפרדת אחריות ברורה. שכבת התצוגה (Streamlit) "
    "מקבלת את הסימול ומתזמרת ארבעה מודולים: שכבת נתונים המושכת מחיר והיסטוריה "
    "מ-Yahoo Finance וחדשות מ-NewsAPI; שכבת ניתוח המחשבת אינדיקטורים טכניים "
    "ומדרגת סנטימנט; ושכבת AI שבה ה-LLM משקלל את כל הנתונים להמלצה סופית. כל "
    "מודול עצמאי וניתן לבדיקה בנפרד."))

# Architecture flow table (visual, RTL order)
flow = [
    [p("פלט: מחיר · גרף · חדשות · סנטימנט · אינדיקטורים · המלצה + נימוק", CELLB)],
    [p("שכבת AI — LLM (OpenAI) או מנוע גיבוי מבוסס-חוקים · פלט: Buy / Hold / Sell", CELL)],
    [p("שכבת ניתוח — אינדיקטורים טכניים (RSI/MACD/SMA) + סנטימנט (FinBERT/VADER)", CELL)],
    [p("שכבת נתונים — Yahoo Finance (מחיר/היסטוריה) + NewsAPI (חדשות)", CELL)],
    [p("שכבת תצוגה — Streamlit · קלט Ticker", CELL)],
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
    [p("Streamlit", CELL), p("ממשק משתמש (Frontend)", CELL)],
    [p("Python · pandas · numpy", CELL), p("Backend וחישובים", CELL)],
    [p("yfinance (Yahoo Finance)", CELL), p("נתוני שוק בזמן אמת", CELL)],
    [p("NewsAPI", CELL), p("חדשות פיננסיות", CELL)],
    [p("FinBERT / VADER", CELL), p("ניתוח סנטימנט (AI)", CELL)],
    [p("OpenAI LLM", CELL), p("המלצת השקעה מנומקת", CELL)],
    [p("Plotly", CELL), p("גרפים אינטראקטיביים", CELL)],
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
story.append(bullet("המשתמש מזין סימול מניה ולוחץ Analyze."))
story.append(bullet("המערכת מושכת מחיר נוכחי והיסטוריה של שנה מ-Yahoo Finance."))
story.append(bullet("נמשכות עד 10 כותרות חדשות אחרונות מ-NewsAPI."))
story.append(bullet("מודול הסנטימנט מדרג כל כותרת ומחשב ציון מצרפי בטווח [1-, 1+]."))
story.append(bullet("מודול טכני מחשב RSI, MACD, SMA50, SMA200 וציון משוקלל אחיד."))
story.append(bullet("ה-LLM משקלל את כל הנתונים ומפיק Buy / Hold / Sell עם רמת ביטחון ונימוק."))

# 6. Technical indicators explanation
story.append(p("6. האינדיקטורים הטכניים", H2))
story.append(p(
    "המימוש מפורש ב-pandas (ולא ספרייה אטומה) לשם שקיפות. RSI(14) מזהה קנייתֵר/"
    "מכירת יתר; MACD מודד מומנטום לפי הפרש ממוצעים מעריכיים; חצייה של ממוצע נע 50 "
    "מעל 200 מהווה 'צלב זהב' שורי, ומתחתיו 'צלב מוות' דובי. מכל אלה מחושב ציון "
    "משוקלל אחד בטווח [1-, 1+] המשמש עוגן כמותי להחלטת ה-LLM."))

# 7. Robustness / fallback
story.append(p("7. עמידות ומנועי גיבוי", H2))
story.append(p(
    "המערכת תוכננה לרוץ מקצה-לקצה גם ללא מפתחות API: ללא מפתח OpenAI מופעל מנוע "
    "גיבוי שקוף המשקלל 70% טכני ו-30% סנטימנט; אם FinBERT אינו זמין (זיכרון מוגבל) "
    "מתבצעת נפילה רכה ל-VADER; וללא מפתח NewsAPI פאנל החדשות פשוט מדולג. כל קריאת "
    "רשת עטופה בטיפול בשגיאות, וסימול שגוי מציג הודעה ידידותית במקום קריסה."))

# 8. Limitations & future work
story.append(p("8. מגבלות ופיתוח עתידי", H2))
story.append(bullet("מגבלות: כלי חינוכי בלבד; אינדיקטורים מסתכלים אחורה; ה-LLM עלול לשגות."))
story.append(bullet("נתוני Yahoo Finance עלולים להתעכב; כיסוי NewsAPI בעיקר באנגלית."))
story.append(bullet("עתיד: תיק מרובה-מניות, התראות אוטומטיות, Backtesting היסטורי."))
story.append(bullet("עתיד: מקורות נוספים (דוחות כספיים, מאקרו, סנטימנט מרשתות חברתיות)."))

# 9. Deployment
story.append(p("9. פריסה", H2))
story.append(p(
    "ניתן לפרוס בקלות ב-Hugging Face Spaces (סוג Streamlit, העלאת הקבצים והגדרת "
    "המפתחות כ-Secrets) או ב-Render (Web Service עם פקודת הרצה "
    "streamlit run app.py והגדרת משתני סביבה). פירוט מלא מופיע ב-README."))

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
