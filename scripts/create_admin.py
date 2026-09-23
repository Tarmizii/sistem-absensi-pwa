"""Create the first Admin without placing a password in shell history."""

from __future__ import annotations

import argparse
import getpass

from app import create_app
from app.database import transaction
from app.services.account_service import create_admin_user


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Buat akun Admin pertama.")
    parser.add_argument(
        "--username",
        help="Username Admin; password tetap diminta secara interaktif.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    username = (args.username or input("Username Admin: ")).strip()
    password = getpass.getpass("Password Admin: ")
    confirmation = getpass.getpass("Ulangi Password Admin: ")
    if password != confirmation:
        raise SystemExit("Password dan konfirmasi tidak sama.")

    app = create_app()
    with app.app_context():
        with transaction() as (_, cursor):
            user_id = create_admin_user(cursor, username, password)
    print(f"Admin berhasil dibuat dengan id={user_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
