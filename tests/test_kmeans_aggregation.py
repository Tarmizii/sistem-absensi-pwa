"""Tests for the T27 period and feature rules before database/UI work."""

from datetime import date
import unittest
from unittest.mock import MagicMock, patch

from app.services.kmeans_aggregation_service import (
    KMeansAggregationError,
    calculate_student_features,
    validate_period,
    aggregate_period,
)
from app.services.attendance_day_snapshot_service import (
    ensure_day_snapshot,
    snapshot_requires_closure,
)


class KMeansPeriodValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.year_start = date(2025, 7, 1)
        self.year_end = date(2026, 6, 30)
        self.today = date(2026, 9, 24)

    def test_accepts_range_within_completed_year(self) -> None:
        self.assertEqual(
            validate_period(date(2025, 8, 1), date(2025, 8, 31),
                            self.year_start, self.year_end, self.today),
            (date(2025, 8, 1), date(2025, 8, 31)),
        )

    def test_record_class_snapshot_must_match_the_day_used_for_analysis(self):
        for record_class_id in (22, None):
            with self.subTest(record_class_id=record_class_id):
                cursor = MagicMock()
                cursor.fetchone.return_value = {
                    "id": 1, "name": "2025/2026", "start_date": self.year_start,
                    "end_date": self.year_end,
                }
                cursor.fetchall.side_effect = [
                    [{"class_id": 12}], [{"class_id": 12, "snapshot_days": 1}],
                    [{"student_id": 7, "full_name": "Siswa", "nisn": "007",
                      "class_id": 12, "class_name": "X-1", "attendance_date": date(2025, 8, 1),
                      "requires_attendance": 1, "snapshot_source": "reconstructed",
                      "record_id": 99, "record_class_id": record_class_id, "status": "present"}],
                ]
                db = MagicMock()
                db.cursor.return_value.__enter__.return_value = cursor
                with patch("app.services.kmeans_aggregation_service.get_db", return_value=db), \
                        self.assertRaisesRegex(KMeansAggregationError, "kelas"):
                    aggregate_period(year_id=1, start_value="2025-08-01", end_value="2025-08-01",
                                     today=self.today)

    def test_rejects_open_year_reversed_range_and_out_of_year_dates(self) -> None:
        with self.assertRaises(KMeansAggregationError):
            validate_period(date(2025, 8, 1), date(2025, 8, 31),
                            self.year_start, date(2026, 12, 31), self.today)
        with self.assertRaises(KMeansAggregationError):
            validate_period(date(2025, 9, 1), date(2025, 8, 31),
                            self.year_start, self.year_end, self.today)
        with self.assertRaises(KMeansAggregationError):
            validate_period(date(2025, 6, 30), date(2025, 7, 2),
                            self.year_start, self.year_end, self.today)
        with self.assertRaises(KMeansAggregationError):
            validate_period(date(2026, 6, 1), date(2026, 7, 1),
                            self.year_start, self.year_end, self.today)


class KMeansFeatureCalculationTests(unittest.TestCase):
    @staticmethod
    def day(status: str | None, *, required: bool = True,
            reconstructed: bool = False) -> dict[str, object]:
        return {"requires_attendance": required, "status": status,
                "source": "reconstructed" if reconstructed else "attendance_transaction"}

    def test_formula_excludes_holiday_and_permit_sick_but_counts_late_and_alpa(self) -> None:
        days = [
            self.day("present"), self.day("late"), self.day("permit"),
            self.day("sick"), self.day("absent"), self.day("present"),
            self.day(None, required=False),  # Libur, tidak masuk denominator.
        ]

        result = calculate_student_features(days)

        self.assertEqual(result["scheduled_school_days"], 6)
        self.assertEqual(result["effective_days"], 4)
        self.assertEqual(result["attendance_percentage"], 75.0)
        self.assertEqual(result["late_count"], 1)
        self.assertEqual(result["alpha_count"], 1)
        self.assertTrue(result["eligible"])

    def test_reconstructed_snapshot_is_reported_and_inactive_student_can_be_counted(self) -> None:
        # Student account activity is deliberately not an input: historical
        # placement, not current account state, defines this population.
        result = calculate_student_features([
            self.day("present", reconstructed=True),
            self.day("absent", reconstructed=True),
        ])
        self.assertEqual(result["reconstructed_days"], 2)
        self.assertEqual(result["attendance_percentage"], 50.0)

    def test_missing_status_on_required_day_rejects_incomplete_period(self) -> None:
        with self.assertRaisesRegex(KMeansAggregationError, "belum lengkap"):
            calculate_student_features([self.day("present"), self.day(None)])

    def test_stored_status_on_frozen_non_school_day_is_not_silently_discarded(self) -> None:
        for status in ("present", "late", "permit", "sick", "absent"):
            with self.subTest(status=status), self.assertRaisesRegex(
                    KMeansAggregationError, "bertentangan"):
                calculate_student_features([self.day(status, required=False)])

    def test_zero_effective_days_is_returned_as_ineligible_not_division_by_zero(self) -> None:
        result = calculate_student_features([self.day("permit"), self.day("sick")])
        self.assertEqual(result["effective_days"], 0)
        self.assertIsNone(result["attendance_percentage"])
        self.assertFalse(result["eligible"])
        self.assertEqual(result["ineligible_reason"], "zero_effective_days")

    def test_invalid_status_or_missing_snapshot_is_rejected(self) -> None:
        with self.assertRaises(KMeansAggregationError):
            calculate_student_features([self.day("unknown")])
        with self.assertRaisesRegex(KMeansAggregationError, "Snapshot hari"):
            calculate_student_features([{"requires_attendance": True, "status": "present"}])


class AttendanceDaySnapshotTests(unittest.TestCase):
    def test_first_snapshot_is_insert_only_and_later_schedule_does_not_replace_it(self) -> None:
        class Cursor:
            def __init__(self) -> None:
                self.rowcount = 1
                self.calls = []

            def execute(self, query, params) -> None:
                self.calls.append((query, params))

        cursor = Cursor()
        school_day = {"is_holiday": False}
        holiday = {"is_holiday": True}
        self.assertTrue(ensure_day_snapshot(
            cursor, academic_year_id=1, class_id=2,
            for_date=date(2025, 8, 1), schedule=school_day,
            source="attendance_transaction",
        ))
        cursor.rowcount = 0  # INSERT IGNORE found the already-frozen class/date.
        self.assertFalse(ensure_day_snapshot(
            cursor, academic_year_id=1, class_id=2,
            for_date=date(2025, 8, 1), schedule=holiday,
            source="finalization_job",
        ))
        self.assertEqual(len(cursor.calls), 2)
        self.assertTrue(all("INSERT IGNORE" in call[0] for call in cursor.calls))
        self.assertTrue(all("UPDATE" not in call[0] for call in cursor.calls))
        self.assertEqual(cursor.calls[0][1][-2:], (1, "attendance_transaction"))
        self.assertEqual(cursor.calls[1][1][-2:], (0, "finalization_job"))

    def test_finalizer_closes_only_after_inclusive_cutoff(self) -> None:
        from datetime import datetime, time
        from zoneinfo import ZoneInfo

        day = date(2025, 8, 1)
        tz = ZoneInfo("Asia/Jakarta")
        schedule = {"checkin_cutoff": time(8, 0), "is_holiday": False}
        self.assertFalse(snapshot_requires_closure(
            schedule=schedule, for_date=day,
            at=datetime(2025, 8, 1, 8, 0, tzinfo=tz),
        ))
        self.assertTrue(snapshot_requires_closure(
            schedule=schedule, for_date=day,
            at=datetime(2025, 8, 1, 8, 0, 1, tzinfo=tz),
        ))
        self.assertTrue(snapshot_requires_closure(
            schedule={"is_holiday": True}, for_date=day,
            at=datetime(2025, 8, 1, 6, 0, tzinfo=tz),
        ))


if __name__ == "__main__":
    unittest.main()
