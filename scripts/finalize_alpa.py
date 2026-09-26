"""Run the Alpa finalization job for one date (T20); safe to run repeatedly.

Intended for manual runs and server schedulers (cron). Unlike the smoke
scripts this command has no environment guard because it is a production job.
Output contains only counts — never student names, NISN, or other personal data.
"""

from __future__ import annotations

import argparse
from datetime import date

from app import create_app
from app.services.finalization_service import FinalizationError, finalize_alpa
from app.services.schedule_service import application_now


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalisasi Alpa siswa wajib hadir setelah cutoff efektif.")
    parser.add_argument(
        "--date",
        help="Tanggal finalisasi YYYY-MM-DD; default hari ini menurut APP_TIMEZONE.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Hitung kandidat dan hasil tanpa menulis apa pun.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = create_app()
    with app.app_context():
        target: date | None = None
        if args.date:
            try:
                target = date.fromisoformat(args.date.strip())
            except ValueError:
                raise SystemExit("--date harus memakai format YYYY-MM-DD.") from None
            if target > application_now().date():
                raise SystemExit("Tanggal finalisasi tidak boleh di masa depan.")
        try:
            summary = finalize_alpa(for_date=target, dry_run=args.dry_run)
        except FinalizationError as error:
            raise SystemExit(str(error)) from None

    reasons = " ".join(
        f"{key}={value}" for key, value in summary["skip_reasons"].items() if value)
    parts = [
        f"finalisasi_alpa date={summary['date']}",
        f"dry_run={int(summary['dry_run'])}",
        f"candidates={summary['candidates']}",
        f"processed={summary['processed']}",
        f"skipped={summary['skipped']}",
        f"failed={summary['failed']}",
    ]
    if reasons:
        parts.append(f"skip=({reasons})")
    print(" ".join(parts))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
