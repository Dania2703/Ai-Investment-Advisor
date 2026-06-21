"""
src/ui/pages/auth_view.py
=========================
Login and registration views. On success they establish the session via the
``on_login`` callback (which the app router wires to set the signed token and
switch to the dashboard).
"""

from __future__ import annotations

from typing import Callable

import streamlit as st

from src.auth import AuthError, authenticate_user, register_user
from src.ui import nav
from src.ui.theme import PALETTE


def _shell_open(title: str, subtitle: str) -> None:
    p = PALETTE
    st.markdown(
        f"""
        <div style="text-align:center;margin:18px 0 6px;">
          <div style="font-size:22px;font-weight:800;">📈
            <span style="color:{p['accent']}">AI</span> Investment Advisor</div>
          <div style="font-size:26px;font-weight:800;margin-top:18px;">{title}</div>
          <div class="ai-muted">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_login(on_login: Callable[[int], None]) -> None:
    """Render the login page. *on_login* receives the authenticated user id."""
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        _shell_open("Welcome back", "Log in to continue your analysis.")
        with st.form("login_form", clear_on_submit=False):
            identifier = st.text_input("Username or email", placeholder="you@example.com")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)

        if submitted:
            try:
                user = authenticate_user(identifier, password)
            except AuthError as exc:
                st.error(str(exc))
            except Exception as exc:  # noqa: BLE001 - DB/connection issues
                st.error(f"Could not reach the account database: {exc}")
            else:
                on_login(user.id)  # sets token + navigates; ends the run

        st.write("")
        c1, c2 = st.columns(2)
        if c1.button("← Back to home", use_container_width=True, key="login_home"):
            nav.go_to(nav.LANDING)
        if c2.button("Create an account", use_container_width=True, key="login_to_register"):
            nav.go_to(nav.REGISTER)


def render_register(on_login: Callable[[int], None]) -> None:
    """Render the registration page. Auto-logs in on success via *on_login*."""
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        _shell_open("Create your account", "Save your analysis history and chat with the advisor.")
        with st.form("register_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="3–32 letters, numbers or _")
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password",
                                     placeholder="At least 8 characters")
            confirm = st.text_input("Confirm password", type="password",
                                    placeholder="Re-enter your password")
            agree = st.checkbox(
                "I understand this is an educational tool and not financial advice.")
            submitted = st.form_submit_button("Create account", type="primary",
                                              use_container_width=True)

        if submitted:
            if password != confirm:
                st.error("Passwords do not match.")
            elif not agree:
                st.error("Please acknowledge the educational-use notice to continue.")
            else:
                try:
                    user = register_user(username, email, password)
                except AuthError as exc:
                    st.error(str(exc))
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not reach the account database: {exc}")
                else:
                    st.success("Account created! Signing you in…")
                    on_login(user.id)

        st.write("")
        c1, c2 = st.columns(2)
        if c1.button("← Back to home", use_container_width=True, key="reg_home"):
            nav.go_to(nav.LANDING)
        if c2.button("I already have an account", use_container_width=True, key="reg_to_login"):
            nav.go_to(nav.LOGIN)
