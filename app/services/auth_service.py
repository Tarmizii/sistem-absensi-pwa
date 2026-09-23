"""Session authentication and role-scope helpers."""

from __future__ import annotations

from collections import OrderedDict, deque
from functools import wraps
import hashlib
import hmac
from time import monotonic
from threading import RLock
from typing import Any, Callable

from flask import current_app, g, redirect, request, session, url_for
from pymysql import MySQLError
from werkzeug.security import check_password_hash, generate_password_hash

from app.database import get_db, transaction
from app.services.account_service import MIN_ADMIN_PASSWORD_LENGTH
from app.services.audit_service import record_audit


LOGIN_FAILURE_WINDOW_SECONDS = 60.0
LOGIN_FAILURE_LIMIT = 5
MAX_LOGIN_FAILURE_KEYS = 4096
_login_failures: OrderedDict[str, deque[float]] = OrderedDict()
_failure_lock = RLock()


def fetch_user_by_username(username: str) -> dict[str, Any] | None:
    """Fetch one account by username using a parameterized query."""

    with get_db().cursor() as cursor:
        cursor.execute(
            """
            SELECT u.id, u.username, u.password_hash, u.role, u.is_active,
                   u.must_change_password, COALESCE(s.face_registered, 0) AS face_registered
            FROM users AS u
            LEFT JOIN students AS s ON s.user_id = u.id
            WHERE u.username = %s
            LIMIT 1
            """,
            (username,),
        )
        return cursor.fetchone()


def fetch_active_user(user_id: int) -> dict[str, Any] | None:
    """Fetch an active account for the current request."""

    with get_db().cursor() as cursor:
        cursor.execute(
            """
            SELECT u.id, u.username, u.password_hash, u.role, u.is_active,
                   u.must_change_password, COALESCE(s.face_registered, 0) AS face_registered
            FROM users AS u
            LEFT JOIN students AS s ON s.user_id = u.id
            WHERE u.id = %s AND u.is_active = 1
            LIMIT 1
            """,
            (user_id,),
        )
        return cursor.fetchone()


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    """Return the account only when username, active state, and hash match."""

    normalized_username = username.strip()
    if not normalized_username or not password:
        return None
    user = fetch_user_by_username(normalized_username)
    if user is None or not user["is_active"]:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user


def login_attempt_key(username: str, remote_addr: str | None) -> str:
    """Build a non-secret key for the small local login throttle."""

    identity = f"{remote_addr or 'unknown'}:{username.strip().lower()}"
    return hashlib.sha256(identity.encode()).hexdigest()


def is_login_rate_limited(key: str, now: float | None = None) -> bool:
    """Apply a per-process five-failures-per-minute throttle.

    This deliberately stays small for the initial app. A multi-worker
    deployment should replace it with a shared limiter before production.
    """

    current = monotonic() if now is None else now
    with _failure_lock:
        failures = _login_failures.get(key)
        if not failures:
            return False
        while failures and current - failures[0] >= LOGIN_FAILURE_WINDOW_SECONDS:
            failures.popleft()
        if not failures:
            _login_failures.pop(key, None)
            return False
        return len(failures) >= LOGIN_FAILURE_LIMIT


def record_login_failure(key: str, now: float | None = None) -> None:
    current = monotonic() if now is None else now
    with _failure_lock:
        is_login_rate_limited(key, current)
        if key not in _login_failures:
            if len(_login_failures) >= MAX_LOGIN_FAILURE_KEYS:
                _login_failures.popitem(last=False)
            _login_failures[key] = deque(maxlen=LOGIN_FAILURE_LIMIT)
        _login_failures[key].append(current)
        _login_failures.move_to_end(key)


def clear_login_failures(key: str) -> None:
    with _failure_lock:
        _login_failures.pop(key, None)


def credential_stamp(password_hash: str) -> str:
    """Opaque session binding; never expose the password hash in the cookie."""
    return hmac.new(current_app.secret_key.encode(), password_hash.encode(), hashlib.sha256).hexdigest()


def update_password(user_id: int, password: str, expected_hash: str | None = None) -> str:
    """Replace a password hash and clear its forced-change flag atomically."""

    if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
        raise ValueError("Password baru tidak valid atau sama dengan password lama.")
    if expected_hash is not None and check_password_hash(expected_hash, password):
        raise ValueError("Password baru tidak valid atau sama dengan password lama.")
    new_hash = generate_password_hash(password)
    with transaction() as (_, cursor):
        if expected_hash is None:
            cursor.execute(
                """UPDATE users SET password_hash = %s, must_change_password = 0
                   WHERE id = %s AND is_active = 1""",
                (new_hash, user_id),
            )
        else:
            cursor.execute(
                """UPDATE users SET password_hash = %s, must_change_password = 0
                   WHERE id = %s AND is_active = 1 AND password_hash = %s""",
                (new_hash, user_id, expected_hash),
            )
        if cursor.rowcount != 1:
            raise ValueError("Akun tidak ditemukan atau sudah dinonaktifkan.")
        record_audit(cursor, actor_user_id=user_id, action="password_changed",
                     target_type="user", target_id=user_id,
                     metadata={"must_change_password": False})
    return credential_stamp(new_hash)


def load_current_user() -> None:
    """Refresh the active account from the database for each request."""

    user_id = session.get("user_id")
    g.current_user = None
    if user_id is None:
        return
    try:
        user = fetch_active_user(int(user_id))
    except (MySQLError, TypeError, ValueError):
        # Do not keep an unverifiable session when the database is unavailable.
        session.clear()
        return
    if user is None:
        session.clear()
        return
    stamp = session.get("credential_stamp")
    if (not isinstance(stamp, str) or not stamp.isascii()
            or not hmac.compare_digest(stamp, credential_stamp(user["password_hash"]))):
        session.clear()
        return
    g.current_user = user


def enforce_password_change_gate():
    """Keep temporary-password accounts on the password-change route."""

    user = g.get("current_user")
    if user is None or not user["must_change_password"]:
        return None
    allowed_endpoints = {"auth.change_password", "auth.logout", "static", "main.healthz"}
    if request.endpoint in allowed_endpoints:
        return None
    return redirect(url_for("auth.change_password"))


def enforce_student_enrollment_gate():
    """Keep un-enrolled students on their own face-enrollment page."""

    user = g.get("current_user")
    if user is None or user["role"] != "student" or bool(user.get("face_registered")):
        return None
    endpoint = request.endpoint or ""
    if endpoint == "student.enrollment":
        return None
    protected = (
        endpoint in {"role.student_dashboard", "role.student_profile"}
        or endpoint.startswith(("student.", "attendance.", "face."))
    )
    if protected:
        return redirect(url_for("student.enrollment"))
    return None


def login_required(view: Callable) -> Callable:
    """Redirect anonymous users to login while preserving the target path."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("current_user") is None:
            return redirect(url_for("auth.login", next=request_path()))
        return view(*args, **kwargs)

    return wrapped


def roles_required(*roles: str) -> Callable:
    """Allow only authenticated users whose role is in ``roles``."""

    allowed_roles = set(roles)

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = g.get("current_user")
            if user is None:
                return redirect(url_for("auth.login", next=request_path()))
            if user["role"] not in allowed_roles:
                return current_app.response_class(
                    "Akses ditolak.", status=403, mimetype="text/plain"
                )
            return view(*args, **kwargs)

        return wrapped

    return decorator


def request_path() -> str:
    """Return a safe local path for the login redirect parameter."""

    from flask import request

    return request.full_path.rstrip("?")
