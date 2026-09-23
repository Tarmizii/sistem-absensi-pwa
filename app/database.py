"""Small PyMySQL connection and transaction helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pymysql
from flask import Flask, current_app, g
from pymysql.connections import Connection
from pymysql.cursors import Cursor, DictCursor


def _connection_options(config: Any) -> dict[str, Any]:
    """Build PyMySQL options from Flask config without logging credentials."""

    if config["APP_ENV"] == "production" and not config["DB_PASSWORD"]:
        raise RuntimeError(
            "DB_PASSWORD wajib diisi melalui environment saat APP_ENV=production."
        )

    return {
        "host": config["DB_HOST"],
        "port": config["DB_PORT"],
        "user": config["DB_USER"],
        "password": config["DB_PASSWORD"],
        "database": config["DB_NAME"],
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": False,
        "connect_timeout": config["DB_CONNECT_TIMEOUT"],
    }


def get_db() -> Connection:
    """Return one request-scoped connection, opening it only when needed."""

    if "db" not in g:
        g.db = pymysql.connect(**_connection_options(current_app.config))
    return g.db


@contextmanager
def transaction() -> Iterator[tuple[Connection, Cursor]]:
    """Commit on success and roll back every failed transaction."""

    connection = get_db()
    try:
        with connection.cursor() as cursor:
            yield connection, cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def close_db(error: BaseException | None = None) -> None:
    """Close the request-scoped connection, if one was opened."""

    del error
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_app(app: Flask) -> None:
    """Register teardown handling on the Flask application."""

    app.teardown_appcontext(close_db)
