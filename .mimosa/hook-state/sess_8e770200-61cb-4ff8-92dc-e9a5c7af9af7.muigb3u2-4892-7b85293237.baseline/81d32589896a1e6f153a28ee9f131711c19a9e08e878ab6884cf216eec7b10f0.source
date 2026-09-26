"""Account setup operations used before the authentication module exists."""

from __future__ import annotations

import re

from werkzeug.security import generate_password_hash


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,100}$")
MIN_ADMIN_PASSWORD_LENGTH = 12


def create_admin_user(cursor, username: str, password: str) -> int:
    """Insert one initial Admin into an existing transaction.

    The caller owns commit/rollback through ``database.transaction``. The
    password is hashed before it reaches SQL and is never returned or logged.
    """

    normalized_username = username.strip()
    if not USERNAME_PATTERN.fullmatch(normalized_username):
        raise ValueError(
            "Username hanya boleh berisi huruf, angka, titik, garis bawah, "
            "atau tanda hubung (3–100 karakter)."
        )
    if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password Admin minimal {MIN_ADMIN_PASSWORD_LENGTH} karakter."
        )

    cursor.execute(
        "SELECT id FROM users WHERE username = %s LIMIT 1",
        (normalized_username,),
    )
    if cursor.fetchone() is not None:
        raise ValueError("Username Admin sudah digunakan.")

    cursor.execute(
        """
        INSERT INTO users
            (username, password_hash, role, is_active, must_change_password)
        VALUES (%s, %s, 'admin', 1, 0)
        """,
        (normalized_username, generate_password_hash(password)),
    )
    return int(cursor.lastrowid)
