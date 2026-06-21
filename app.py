"""
app.py
======
AI Investment Advisor — application shell & router.

This is the entry point. It is intentionally thin: it wires together the
self-contained layers and decides *which page* to show based on the session.

Architecture
------------
    config.py                  global settings (env-driven)
    src/auth/                  authentication layer (SQLAlchemy users + sessions)
    src/data/                  service layer (market data, news, DB)
    src/analysis/              analysis layer (indicators, sentiment, scoring)
    src/ai/                    AI layer (advisor narration, RAG chatbot)
    src/ui/                    presentation layer
        theme.py               design system / CSS
        nav.py                 session-state router
        components.py          charts
        chatbot_widget.py      floating assistant
        pages/                 landing · auth · dashboard

Session flow
------------
* A signed token (``src.auth.issue_session_token``) is stored in the URL query
  params so a login survives a browser refresh.
* On each run we restore the user from that token, then route:
  unauthenticated → landing/login/register; authenticated → dashboard.
"""

from __future__ import annotations

import streamlit as st

from src.auth import (
    get_user_by_id,
    issue_session_token,
    verify_session_token,
)
from src.ui import nav
from src.ui.pages import auth_view, dashboard, landing
from src.ui.theme import inject_global_css

st.set_page_config(
    page_title="AI Investment Advisor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# --------------------------------------------------------------------------- #
# Session helpers
# --------------------------------------------------------------------------- #
def _restore_session() -> None:
    """Populate st.session_state['user'] from the signed query-param token."""
    if "user" in st.session_state:
        return
    token = st.query_params.get("s")
    if not token:
        return
    user_id = verify_session_token(token)
    if not user_id:
        # Stale/forged token — clear it.
        if "s" in st.query_params:
            del st.query_params["s"]
        return
    user = get_user_by_id(user_id)
    if user is not None:
        st.session_state["user"] = {"id": user.id, "username": user.username,
                                    "email": user.email}


def _login(user_id: int) -> None:
    """Establish the session for *user_id*: store token + user, go to dashboard."""
    user = get_user_by_id(user_id)
    if user is None:
        st.error("Could not load your account after login.")
        return
    st.session_state["user"] = {"id": user.id, "username": user.username, "email": user.email}
    st.query_params["s"] = issue_session_token(user)
    nav.go_to(nav.DASHBOARD)


def _logout() -> None:
    """Tear down the session and return to the landing page."""
    st.session_state.pop("user", None)
    st.session_state.pop("run", None)
    if "s" in st.query_params:
        del st.query_params["s"]
    nav.go_to(nav.LANDING)


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #
def main() -> None:
    inject_global_css()
    _restore_session()

    user = st.session_state.get("user")
    page = nav.current_page(default=nav.LANDING)

    # Authenticated users always land on the dashboard.
    if user:
        if page not in (nav.DASHBOARD,):
            st.session_state["page"] = nav.DASHBOARD
        dashboard.render(user, on_logout=_logout)
        return

    # Unauthenticated routing.
    if page == nav.LOGIN:
        auth_view.render_login(on_login=_login)
    elif page == nav.REGISTER:
        auth_view.render_register(on_login=_login)
    else:
        landing.render()


if __name__ == "__main__":
    main()
