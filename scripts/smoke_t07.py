"""Exercise password/audit transactions against local MySQL with cleanup.

Run after migration 002. Uses configured DB_* and a uniquely named synthetic
account; never edits an existing account. No passwords/hashes are printed.
"""

import re
import secrets
from unittest.mock import patch

from pymysql import MySQLError
from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, transaction


def token(client, path):
    response = client.get(path)
    assert response.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True)).group(1)


def main():
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke test hanya untuk database development/test.")
    name = "__t07_" + secrets.token_hex(8)
    old, new = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    user_id = None
    try:
        with app.app_context(), transaction() as (_, cursor):
            cursor.execute("INSERT INTO users (username,password_hash,role,must_change_password) VALUES (%s,%s,'admin',1)",
                           (name, generate_password_hash(old)))
            user_id = cursor.lastrowid
        client, other = app.test_client(), app.test_client()
        for browser in (client, other):
            response = browser.post("/login", data={"csrf_token": token(browser, "/login"),
                                                   "username": name, "password": old})
            assert response.location == "/change-password"
        assert client.get("/admin/dashboard").location == "/change-password"
        fields = {"csrf_token": token(client, "/change-password"), "current_password": old,
                  "new_password": new, "confirmation": new}
        with patch("app.services.auth_service.record_audit", side_effect=MySQLError("synthetic failure")):
            assert client.post("/change-password", data=fields).status_code == 200
        with app.app_context(), get_db().cursor() as cursor:
            cursor.execute("SELECT must_change_password FROM users WHERE id=%s", (user_id,))
            assert cursor.fetchone()["must_change_password"] == 1
            cursor.execute("SELECT COUNT(*) AS n FROM audit_logs WHERE actor_user_id=%s", (user_id,))
            assert cursor.fetchone()["n"] == 0
        # Success using the old password proves the failed mutation rolled back.
        response = client.post("/change-password", data=fields)
        assert response.location == "/admin/dashboard"
        assert client.get("/admin/profile").status_code == 200
        assert "/login" in other.get("/admin/profile").location
        with app.app_context(), get_db().cursor() as cursor:
            cursor.execute("SELECT action, metadata FROM audit_logs WHERE actor_user_id=%s", (user_id,))
            rows = cursor.fetchall()
            assert len(rows) == 1 and rows[0]["action"] == "password_changed"
            assert old not in rows[0]["metadata"] and new not in rows[0]["metadata"]
        assert client.post("/logout", data={"csrf_token": token(client, "/admin/profile")}).status_code == 302
        for password, status in ((old, 401), (new, 302)):
            response = client.post("/login", data={"csrf_token": token(client, "/login"),
                                                  "username": name, "password": password})
            assert response.status_code == status
    finally:
        if user_id is not None:
            with app.app_context(), transaction() as (_, cursor):
                cursor.execute("DELETE FROM audit_logs WHERE actor_user_id=%s", (user_id,))
                cursor.execute("DELETE FROM users WHERE id=%s AND username=%s", (user_id, name))
    print("t07_mysql_smoke=ok; rollback=ok; session_revocation=ok; cleanup=ok")


if __name__ == "__main__":
    main()
