"""
src/ui/nav.py
=============
Lightweight session-state router shared by every page.

Streamlit has no built-in auth-gated router, so we keep the current view in
``st.session_state["page"]`` and switch with :func:`go_to`, which reruns the
script. Keeping this in one place stops the pages from importing each other.
"""

from __future__ import annotations

import streamlit as st

LANDING = "landing"
LOGIN = "login"
REGISTER = "register"
DASHBOARD = "dashboard"


def current_page(default: str = LANDING) -> str:
    return st.session_state.get("page", default)


def go_to(page: str) -> None:
    """Navigate to *page* on the next rerun."""
    st.session_state["page"] = page
    st.rerun()


def set_page(page: str) -> None:
    """Set the page without forcing an immediate rerun (use in on_click callbacks)."""
    st.session_state["page"] = page
