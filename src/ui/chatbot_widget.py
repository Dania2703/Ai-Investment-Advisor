"""
src/ui/chatbot_widget.py
========================
A floating, expandable chat assistant pinned to the bottom-right corner.

Implementation notes
--------------------
Streamlit can't host a truly free-floating native widget, so we use
``st.popover`` (a real expandable panel triggered by a button) and pin that
button to the bottom-right with scoped CSS. ``st.chat_input`` may only live at
the page root, so inside the popover we use a small form (text input + send).

RAG discipline: the assistant is handed ONLY the live ``context`` string built
from retrieved data (quote, indicators, news, recommendation). It is instructed
to answer from that context alone — see :mod:`src.ai.chatbot`.
"""

from __future__ import annotations

import streamlit as st

from config import settings
from src.ai.chatbot import chat as chatbot_chat
from src.ui.theme import PALETTE

_SUGGESTIONS = [
    "Why is this rating given?",
    "Explain the MACD signal.",
    "What are the main risks?",
    "How strong is the trend?",
]


def _inject_css() -> None:
    p = PALETTE
    st.markdown(
        f"""
        <style>
        /* Pin the (single) popover trigger to the bottom-right as a FAB */
        div[data-testid="stPopover"] {{
            position: fixed;
            bottom: 26px;
            right: 26px;
            z-index: 100000;
        }}
        div[data-testid="stPopover"] > div > button {{
            border-radius: 999px !important;
            padding: 12px 20px !important;
            font-weight: 700 !important;
            color: #04222A !important;
            background: {p['brand']} !important;
            border: none !important;
            box-shadow: 0 10px 26px rgba(34,211,238,0.28) !important;
        }}
        div[data-testid="stPopover"] > div > button:hover {{ filter: brightness(1.08); }}

        /* The expanded chat panel */
        div[data-testid="stPopoverBody"] {{
            width: 420px !important;
            max-width: 92vw !important;
            background: {p['surface']} !important;
            border: 1px solid {p['border_strong']} !important;
        }}
        .ai-chat-msg {{ border-radius: 12px; padding: 9px 12px; margin: 6px 0; font-size: 14px; }}
        .ai-chat-user {{ background: {p['surface_2']}; border: 1px solid {p['border']}; }}
        .ai-chat-bot  {{ background: rgba(34,211,238,0.08); border: 1px solid rgba(34,211,238,0.28); }}
        @media (max-width: 640px) {{
            div[data-testid="stPopoverBody"] {{ width: 92vw !important; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _history_key(ticker: str) -> str:
    return f"chat_history::{ticker}"


def render_floating_chatbot(ticker: str, context: str) -> None:
    """
    Render the floating assistant for *ticker*, grounded in *context*.

    Safe to call once near the end of the dashboard render.
    """
    _inject_css()

    key = _history_key(ticker)
    history = st.session_state.setdefault(key, [])

    with st.popover("💬  Ask the Advisor", use_container_width=False):
        p = PALETTE
        st.markdown(
            f"<div style='font-weight:700;font-size:15px;'>AI Advisor "
            f"<span class='ai-muted' style='font-weight:400;'>· {ticker}</span></div>"
            f"<div class='ai-muted' style='font-size:12px;margin-bottom:6px;'>"
            f"Answers only from this stock's live data, indicators &amp; news.</div>",
            unsafe_allow_html=True,
        )

        if not settings.chatbot_enabled:
            st.info(
                "Add a free **GROQ_API_KEY** (console.groq.com) or **GEMINI_API_KEY** "
                "(aistudio.google.com) to your `.env` to enable the chatbot."
            )
            return

        # ---- Transcript -------------------------------------------------
        transcript = st.container(height=280)
        with transcript:
            if not history:
                st.markdown(
                    "<div class='ai-muted' style='font-size:13px;'>👋 Ask me anything about "
                    f"{ticker} — the indicators, the news, or why it's rated the way it is.</div>",
                    unsafe_allow_html=True,
                )
            for role, text in history:
                css = "ai-chat-user" if role == "user" else "ai-chat-bot"
                who = "You" if role == "user" else "Advisor"
                st.markdown(
                    f"<div class='ai-chat-msg {css}'><b style='color:{p['accent']}'>{who}</b><br>{text}</div>",
                    unsafe_allow_html=True,
                )

        # ---- Quick suggestions -----------------------------------------
        pending = st.session_state.pop("_chat_pending", None)
        scols = st.columns(2)
        for i, s in enumerate(_SUGGESTIONS):
            if scols[i % 2].button(s, key=f"sugg_{ticker}_{i}", use_container_width=True):
                pending = s

        # ---- Composer ---------------------------------------------------
        with st.form(f"chat_form_{ticker}", clear_on_submit=True):
            cols = st.columns([5, 1])
            user_text = cols[0].text_input(
                "msg", label_visibility="collapsed",
                placeholder=f"Ask about {ticker}…",
            )
            send = cols[1].form_submit_button("Send", use_container_width=True)
        if send and user_text.strip():
            pending = user_text.strip()

        if pending:
            history.append(("user", pending))
            try:
                reply, engine = chatbot_chat(
                    user_message=pending,
                    context=context,
                    history=history[:-1],
                )
            except Exception as exc:  # noqa: BLE001
                reply = f"Sorry, I couldn't process that. ({exc})"
            history.append(("assistant", reply))
            st.session_state[key] = history
            st.rerun()
