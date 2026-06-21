"""
src/ui/theme.py
===============
Design-system loader + light/dark theming.

The look is driven by the semantic CSS variables in ``src/styles.css``. A theme
is simply a different set of values for those variables, applied to ``.stApp``
(which sits above every component, so the whole tree re-themes instantly).

* :func:`inject_global_css` — injects styles.css + the active theme's variables.
* :func:`tokens` / :func:`chart_colors` — concrete colours for the few places
  that can't read CSS variables (the TradingView chart, the chatbot popover).
* :func:`theme_toggle_button` — a Streamlit button that flips the theme.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

_CSS_PATH = Path(__file__).resolve().parents[1] / "styles.css"

# --------------------------------------------------------------------------- #
# Theme token sets (mirror the variable names in styles.css)
# --------------------------------------------------------------------------- #
_DARK = {
    "bg": "#0A0E1A", "bg-2": "#0C111F",
    "surface": "#111726", "surface-2": "#161D2F", "surface-3": "#1B2336",
    "border": "rgba(255,255,255,0.06)", "border-strong": "rgba(255,255,255,0.12)",
    "text": "#E6EAF2", "text-2": "#B3BCD0", "text-muted": "#7B879E",
    "brand": "#22D3EE", "brand-dim": "rgba(34,211,238,0.14)",
    "bull": "#10B981", "bear": "#F43F5E", "neutral": "#F59E0B",
    "app-bg": ("radial-gradient(900px 480px at 50% -160px,"
               " rgba(34,211,238,0.10), transparent 70%), #0A0E1A"),
    "topbar-bg": "rgba(10,14,26,0.82)",
    "grid": "rgba(255,255,255,0.05)",
}

_LIGHT = {
    "bg": "#F5F7FB", "bg-2": "#FFFFFF",
    "surface": "#FFFFFF", "surface-2": "#F1F4F9", "surface-3": "#E7ECF3",
    "border": "rgba(15,23,42,0.10)", "border-strong": "rgba(15,23,42,0.18)",
    "text": "#0F1B2D", "text-2": "#38465C", "text-muted": "#5C6B82",
    "brand": "#0891B2", "brand-dim": "rgba(8,145,178,0.12)",
    "bull": "#059669", "bear": "#E11D48", "neutral": "#B45309",
    "app-bg": ("radial-gradient(900px 480px at 50% -160px,"
               " rgba(8,145,178,0.08), transparent 70%), #F5F7FB"),
    "topbar-bg": "rgba(245,247,251,0.86)",
    "grid": "rgba(15,23,42,0.07)",
}

_THEMES = {"dark": _DARK, "light": _LIGHT}

# Vivid signal colours stay constant (they read well on both themes).
RATING_COLORS = {
    "Strong Buy": "#10B981", "Buy": "#10B981", "Hold": "#F59E0B",
    "Sell": "#F43F5E", "Strong Sell": "#F43F5E",
}
SENTIMENT_COLORS = {
    "positive": "#10B981", "Positive": "#10B981",
    "negative": "#F43F5E", "Negative": "#F43F5E",
    "neutral": "#7B879E", "Neutral": "#7B879E",
}

DEFAULT_THEME = "dark"


# --------------------------------------------------------------------------- #
# Active-theme accessors
# --------------------------------------------------------------------------- #
def active_theme() -> str:
    t = st.session_state.get("theme", DEFAULT_THEME)
    return t if t in _THEMES else DEFAULT_THEME


def tokens() -> dict:
    """Concrete colour values for the active theme (underscore keys)."""
    raw = _THEMES[active_theme()]
    return {k.replace("-", "_"): v for k, v in raw.items()}


# Back-compat: a few modules import PALETTE. Resolve it dynamically per call via
# a dict-like proxy so it always reflects the active theme.
class _PaletteProxy(dict):
    def __getitem__(self, key):  # noqa: D401
        t = tokens()
        if key in t:
            return t[key]
        # legacy aliases
        alias = {"accent": "brand", "accent_2": "brand",
                 "positive": "bull", "negative": "bear", "warning": "neutral"}
        return t[alias.get(key, "brand")]

    def get(self, key, default=None):
        try:
            return self[key]
        except Exception:  # noqa: BLE001
            return default


PALETTE = _PaletteProxy()


def chart_colors() -> dict:
    """Colours for the TradingView chart (which can't read CSS variables)."""
    t = tokens()
    return {
        "bg": t["surface"], "text": t["text_muted"], "grid": t["grid"],
        "border": t["border_strong"], "watermark": "rgba(123,135,158,0.07)",
        "up": t["bull"], "down": t["bear"],
        "sma50": t["brand"], "sma200": t["neutral"], "ema20": t["text_muted"],
    }


# --------------------------------------------------------------------------- #
# CSS injection
# --------------------------------------------------------------------------- #
def inject_global_css() -> None:
    """Inject styles.css, then override the variables for the active theme."""
    try:
        css = _CSS_PATH.read_text(encoding="utf-8")
    except OSError:
        css = ""
    raw = _THEMES[active_theme()]
    overrides = ";".join(f"--{k}:{v}" for k, v in raw.items())
    st.markdown(
        f"<style>{css}\n.stApp{{{overrides};background:var(--app-bg);}}</style>",
        unsafe_allow_html=True,
    )


def theme_toggle_button(key: str = "theme_toggle", use_container_width: bool = True) -> None:
    """A button that flips between light and dark."""
    cur = active_theme()
    label = "☀ Light" if cur == "dark" else "🌙 Dark"
    if st.button(label, key=key, use_container_width=use_container_width,
                 help="Toggle light / dark mode"):
        st.session_state["theme"] = "light" if cur == "dark" else "dark"
        st.rerun()


# --------------------------------------------------------------------------- #
# Lightweight HTML helpers (kept for back-compat with existing pages)
# --------------------------------------------------------------------------- #
def section_header(eyebrow: str, title: str, subtitle: str = "") -> str:
    sub = f'<div class="muted" style="margin-top:2px;">{subtitle}</div>' if subtitle else ""
    return (f'<div class="eyebrow">{eyebrow}</div>'
            f'<div class="section-title">{title}</div>{sub}')


def render_section_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    st.markdown(section_header(eyebrow, title, subtitle), unsafe_allow_html=True)


def pill(text: str, color: str) -> str:
    return (f'<span style="display:inline-block;padding:3px 10px;border-radius:999px;'
            f'font-size:12px;font-weight:700;color:{color};background:{color}1A;'
            f'border:1px solid {color}55;">{text}</span>')


def rating_pill(rating: str) -> str:
    return pill(rating.upper(), RATING_COLORS.get(rating, "#22D3EE"))
