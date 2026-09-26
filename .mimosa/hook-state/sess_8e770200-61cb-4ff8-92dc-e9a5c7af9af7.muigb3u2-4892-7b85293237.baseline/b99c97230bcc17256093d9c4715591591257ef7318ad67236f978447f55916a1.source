"""Reconstruct missing frozen school-day snapshots for completed years (T27)."""

from __future__ import annotations

import argparse

from app import create_app
from app.services.kmeans_aggregation_service import (
    KMeansAggregationError,
    reconstruct_missing_snapshots,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rekonstruksi snapshot hari kelas yang belum tersedia pada tahun ajaran lampau."
    )
    parser.add_argument("--year-id", type=int, help="Batasi ke satu ID tahun ajaran yang telah berakhir.")
    args = parser.parse_args()
    app = create_app()
    if app.config["APP_ENV"] == "production":
        parser.error("Jalankan rekonstruksi dari environment development/test yang dituju.")
    try:
        with app.app_context():
            summary = reconstruct_missing_snapshots(year_id=args.year_id)
    except KMeansAggregationError as error:
        parser.error(str(error))
    print(
        "Rekonstruksi snapshot selesai: "
        f"tahun={summary['years']}, kelas={summary['classes']}, "
        f"dibuat={summary['inserted']}, dipertahankan={summary['preserved']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
