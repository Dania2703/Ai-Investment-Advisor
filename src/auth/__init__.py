"""
src.auth
========
Authentication layer: SQLAlchemy-backed user accounts, password hashing,
session tokens, and saved analysis history.

Public surface (import from here):

    from src.auth import (
        AuthError, User,
        register_user, authenticate_user, get_user_by_id,
        issue_session_token, verify_session_token,
        save_analysis, list_saved_analyses, delete_saved_analysis,
    )
"""

from __future__ import annotations

from src.auth.models import SavedAnalysis, User  # noqa: F401
from src.auth.service import (  # noqa: F401
    AuthError,
    authenticate_user,
    delete_saved_analysis,
    get_user_by_id,
    issue_session_token,
    list_saved_analyses,
    register_user,
    save_analysis,
    verify_session_token,
)

__all__ = [
    "AuthError",
    "User",
    "SavedAnalysis",
    "register_user",
    "authenticate_user",
    "get_user_by_id",
    "issue_session_token",
    "verify_session_token",
    "save_analysis",
    "list_saved_analyses",
    "delete_saved_analysis",
]
