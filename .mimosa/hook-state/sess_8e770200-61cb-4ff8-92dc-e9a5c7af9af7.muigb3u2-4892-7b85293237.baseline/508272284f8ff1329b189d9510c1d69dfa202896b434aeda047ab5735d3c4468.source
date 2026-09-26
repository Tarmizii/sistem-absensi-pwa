"""Small application-wide CSRF protection for form and API mutations."""

from __future__ import annotations

import hmac
import secrets

from flask import abort, request, session


CSRF_SESSION_KEY = "_csrf_token"
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def issue_csrf_token() -> str:
    """Return the current session token, creating one when needed."""

    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def is_valid_csrf_token(candidate: str | None) -> bool:
    """Compare a submitted token without leaking timing information."""

    expected = session.get(CSRF_SESSION_KEY)
    return (isinstance(expected, str) and isinstance(candidate, str)
            and bool(expected) and candidate.isascii()
            and hmac.compare_digest(expected, candidate))


def protect_mutating_request() -> None:
    """Reject state-changing requests without a valid form/header token."""

    if request.method not in MUTATING_METHODS:
        return

    candidate = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not is_valid_csrf_token(candidate):
        abort(400, description="Permintaan tidak valid.")
