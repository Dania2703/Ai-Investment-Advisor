"""
src/ui/widgets.py
=================
Reusable, token-driven HTML/SVG building blocks for the dashboard.

Everything here returns an HTML string that references the CSS variables defined
in ``src/styles.css`` — no hardcoded colours — so the whole look is retheme-able
from one place. Icons are inline lucide SVGs (MIT) since ``lucide-react`` isn't
available in a Streamlit runtime.
"""

from __future__ import annotations

import math
import urllib.parse
from typing import Optional

# --------------------------------------------------------------------------- #
# Lucide icons (inline SVG paths, MIT licensed)
# --------------------------------------------------------------------------- #
_ICONS = {
    "bar-chart-3": '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "candlestick": '<path d="M9 5v4"/><rect width="4" height="6" x="7" y="9" rx="1"/><path d="M9 15v2"/>'
                   '<path d="M17 3v2"/><rect width="4" height="8" x="15" y="5" rx="1"/><path d="M17 13v3"/>'
                   '<path d="M3 3v18h18"/>',
    "newspaper": '<path d="M15 18h-5"/><path d="M18 14h-8"/>'
                 '<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Z"/>'
                 '<rect width="8" height="4" x="10" y="6" rx="1"/>',
    "brain": '<rect width="16" height="16" x="4" y="4" rx="3"/><rect width="6" height="6" x="9" y="9" rx="1"/>'
             '<path d="M15 2v2"/><path d="M9 2v2"/><path d="M15 20v2"/><path d="M9 20v2"/>'
             '<path d="M20 9h2"/><path d="M20 14h2"/><path d="M2 9h2"/><path d="M2 14h2"/>',
    "history": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>'
               '<path d="M12 7v5l4 2"/>',
    "trending-up": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "trending-down": '<polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/>',
    "minus": '<path d="M5 12h14"/>',
    "gauge": '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
    "newspaper-mini": '<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Z"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
            '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
}


def icon(name: str, size: int = 16, color: str = "currentColor", stroke: float = 2.0) -> str:
    """Return an inline lucide SVG string."""
    paths = _ICONS.get(name, "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'style="vertical-align:middle;display:inline-block;">{paths}</svg>'
    )


# --------------------------------------------------------------------------- #
# Rating helpers
# --------------------------------------------------------------------------- #
def rating_tone(rating: str) -> str:
    """Map a rating to a token tone: 'bull' | 'bear' | 'neutral'."""
    if rating in ("Strong Buy", "Buy"):
        return "bull"
    if rating in ("Sell", "Strong Sell"):
        return "bear"
    return "neutral"


def rating_var(rating: str) -> str:
    return f"var(--{rating_tone(rating)})"


def badge(rating: str) -> str:
    tone = rating_tone(rating)
    return f'<span class="badge {tone}">{rating.upper()}</span>'


# --------------------------------------------------------------------------- #
# Circular score gauge (animated ring, pure SVG + CSS)
# --------------------------------------------------------------------------- #
def score_gauge(score: Optional[float], rating: str, size: int = 132) -> str:
    """An animated circular gauge showing *score*/100, coloured by *rating*."""
    s = max(0.0, min(100.0, float(score))) if score is not None else 0.0
    r = (size / 2) - 8
    cx = cy = size / 2
    circ = 2 * math.pi * r
    target = circ * (1 - s / 100.0)
    color = rating_var(rating)
    score_txt = f"{s:.0f}" if score is not None else "—"
    return f"""
    <div class="gauge-wrap" style="width:{size}px;height:{size}px;">
      <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
        <circle cx="{cx}" cy="{cy}" r="{r}" fill="none"
                stroke="var(--surface-3)" stroke-width="9"/>
        <circle class="gauge-ring-fg" cx="{cx}" cy="{cy}" r="{r}" fill="none"
                stroke="{color}" stroke-width="9" stroke-linecap="round"
                transform="rotate(-90 {cx} {cy})"
                stroke-dasharray="{circ:.2f}"
                style="--circ:{circ:.2f};--target:{target:.2f};
                       stroke-dashoffset:{target:.2f};
                       animation: ringIn 1.1s cubic-bezier(.22,1,.36,1) both;"/>
      </svg>
      <div class="gauge-center">
        <div class="gauge-score" style="color:{color};">{score_txt}</div>
        <div class="gauge-sub">/ 100</div>
      </div>
    </div>
    """


# --------------------------------------------------------------------------- #
# KPI / snapshot cards
# --------------------------------------------------------------------------- #
def kpi_card(label: str, value: str, *, sub: str = "", sub_tone: str = "",
             icon_name: str = "") -> str:
    """One equal-height KPI card. *sub_tone* in {'up','down','flat',''}."""
    ic = icon(icon_name, 13, "var(--text-muted)") if icon_name else ""
    sub_html = f'<div class="kpi-sub {sub_tone}">{sub}</div>' if sub else ""
    return (
        f'<div class="kpi">'
        f'<div class="kpi-label">{ic}{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{sub_html}</div>'
    )


def grid(cards: list[str], cls: str = "kpi-grid") -> str:
    return f'<div class="{cls}">{"".join(cards)}</div>'


# --------------------------------------------------------------------------- #
# Source chips with favicon, grouped by trust tier
# --------------------------------------------------------------------------- #
def _favicon(domain: str) -> str:
    return f"https://www.google.com/s2/favicons?domain={urllib.parse.quote(domain)}&sz=64"


def source_chip(label: str, url: str, domain: str) -> str:
    return (
        f'<a class="chip" href="{url}" target="_blank" rel="noopener">'
        f'<img src="{_favicon(domain)}" alt=""/>{label}</a>'
    )


def status_dot(is_open: bool, label: str) -> str:
    cls = "open" if is_open else "closed"
    return f'<span class="dot {cls}"></span><span>{label}</span>'
