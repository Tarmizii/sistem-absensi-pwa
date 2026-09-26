"""Finalization contract for T20: pure decisions, real-MySQL job, idempotency.

Pure tests pin boundary rules (AC-10 holiday, cutoff inclusivity, record
exemptions) with a controlled clock. Integration tests run finalize_alpa
against the configured dev MySQL with synthetic fixtures and clean them up.
"""

from __future__ import annotations

from datetime import date, datetime
import secrets
import unittest
from unittest.mock import patch

from app import create_app
from app.database import get_db, transaction
from app.services.finalization_service import decide_finalization, finalize_alpa


FOR_DATE = date(2026, 9, 24)
AT_NOON = datetime(2026, 9, 24, 12, 0)


def _schedule(**overrides):
    schedule = {
        "for_date": FOR_DATE,
        "checkin_start": "06:30", "late_after": "07:15",
        "checkin_cutoff": "08:00", "checkout_start": "15:00",
        "is_holiday": False, "source": "regular",
        "academic_year_id": 1, "class_id": 1,
        "exception_id": None, "exception_type": None,
    }
    schedule.update(overrides)
    return schedule


def _record(**overrides):
    record = {"status": None, "status_source": None,
              "checkin_at": None, "class_id": 1}
    record.update(overrides)
    return record


class DecideFinalizationTests(unittest.TestCase):
    """Pure decision tests with a controlled clock (no database)."""

    def test_missing_schedule_skips(self):
        self.assertEqual(
            decide_finalization(schedule=None, record=None, at=AT_NOON,
                                for_date=FOR_DATE),
            ("skip", "no_schedule"))

    def test_holiday_never_finalizes(self):
        """AC-10: the job must not create Alpa on a school holiday."""
        self.assertEqual(
            decide_finalization(schedule=_schedule(is_holiday=True), record=None,
                                at=AT_NOON, for_date=FOR_DATE),
            ("skip", "holiday"))

    def test_same_day_before_cutoff_skips(self):
        self.assertEqual(
            decide_finalization(schedule=_schedule(), record=None,
                                at=datetime(2026, 9, 24, 7, 0), for_date=FOR_DATE),
            ("skip", "before_cutoff"))

    def test_same_day_exactly_at_cutoff_still_skips(self):
        """Check-in is inclusive at cutoff, so finalization must wait."""
        self.assertEqual(
            decide_finalization(schedule=_schedule(), record=None,
                                at=datetime(2026, 9, 24, 8, 0), for_date=FOR_DATE),
            ("skip", "before_cutoff"))

    def test_same_day_strictly_after_cutoff_finalizes(self):
        self.assertEqual(
            decide_finalization(schedule=_schedule(), record=None,
                                at=datetime(2026, 9, 24, 8, 0, 0, 1),
                                for_date=FOR_DATE),
            ("finalize", ""))

    def test_backfill_of_earlier_date_not_blocked_by_todays_clock(self):
        """A missed yesterday run still finalizes when invoked this morning."""
        self.assertEqual(
            decide_finalization(schedule=_schedule(), record=None,
                                at=datetime(2026, 9, 25, 6, 0),
                                for_date=FOR_DATE),
            ("finalize", ""))

    def test_future_date_skips(self):
        self.assertEqual(
            decide_finalization(schedule=_schedule(), record=None,
                                at=AT_NOON, for_date=date(2026, 9, 25)),
            ("skip", "before_cutoff"))

    def test_auto_presence_exempt(self):
        self.assertEqual(
            decide_finalization(
                schedule=_schedule(),
                record=_record(checkin_at=datetime(2026, 9, 24, 7, 0)),
                at=AT_NOON, for_date=FOR_DATE),
            ("skip", "has_presence"))

    def test_manual_status_exempt_including_teacher_alpa(self):
        for status in ("permit", "sick", "absent"):
            with self.subTest(status=status):
                self.assertEqual(
                    decide_finalization(
                        schedule=_schedule(),
                        record=_record(status=status, status_source="teacher"),
                        at=AT_NOON, for_date=FOR_DATE),
                    ("skip", "has_manual_status"))

    def test_empty_record_finalizes(self):
        self.assertEqual(
            decide_finalization(schedule=_schedule(), record=_record(),
                                at=AT_NOON, for_date=FOR_DATE),
            ("finalize", ""))


class FinalizeAlpaDatabaseTests(unittest.TestCase):
    """Real-MySQL job behavior with synthetic fixtures (T20.4)."""

    def setUp(self):
        self.app = create_app({"TESTING": True})
        self.context = self.app.app_context()
        self.context.push()
        self.suffix = secrets.token_hex(4)
        self.user_ids: list[int] = []
        self.student_ids: list[int] = []
        self.seed_ids: dict[str, int] = {}
        with transaction() as (_, cursor):
            cursor.execute(
                "INSERT INTO academic_years (name, start_date, end_date, is_active) VALUES (%s, '2026-07-01', '2027-06-30', 1)",
                (f"Tahun T20 {self.suffix}",))
            self.seed_ids["year"] = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO classes (academic_year_id, name, is_active) VALUES (%s, %s, 1)",
                (self.seed_ids["year"], f"X-T20{self.suffix[:4]}"))
            self.seed_ids["class"] = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO attendance_schedules (academic_year_id, day_of_week, checkin_start, late_after, checkin_cutoff, checkout_start, is_active) VALUES (%s, %s, '06:30', '07:15', '08:00', '15:00', 1)",
                (self.seed_ids["year"], FOR_DATE.isoweekday()))
            for label in ("fresh", "present", "manual"):
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, 'student', 1)",
                    (f"t20_{label}_{self.suffix}", "x" * 20))
                user_id = int(cursor.lastrowid)
                self.user_ids.append(user_id)
                cursor.execute(
                    "INSERT INTO students (user_id, nisn, full_name, face_registered) VALUES (%s, %s, %s, 1)",
                    (user_id, f"80{self.suffix[:4]}{len(self.student_ids)}",
                     f"Siswa T20 {label}"))
                student_id = int(cursor.lastrowid)
                self.student_ids.append(student_id)
                cursor.execute(
                    "INSERT INTO student_class_enrollments (student_id, academic_year_id, class_id) VALUES (%s, %s, %s)",
                    (student_id, self.seed_ids["year"], self.seed_ids["class"]))
        self.fresh_id, self.present_id, self.manual_id = self.student_ids

    def tearDown(self):
        try:
            with transaction() as (_, cursor):
                if self.student_ids:
                    ph = ",".join(["%s"] * len(self.student_ids))
                    ids = tuple(self.student_ids)
                    cursor.execute(
                        "DELETE FROM audit_logs WHERE actor_user_id IS NULL AND action='attendance_alpa_finalized'"
                        " AND target_id IN (SELECT id FROM attendance_records WHERE student_id IN (" + ph + "))",
                        ids)
                    cursor.execute(
                        "DELETE FROM attendance_records WHERE student_id IN (" + ph + ")", ids)
                    cursor.execute("DELETE FROM student_faces WHERE student_id IN (" + ph + ")", ids)
                    cursor.execute(
                        "DELETE FROM student_class_enrollments WHERE student_id IN (" + ph + ")", ids)
                    cursor.execute("DELETE FROM students WHERE id IN (" + ph + ")", ids)
                if self.user_ids:
                    ph = ",".join(["%s"] * len(self.user_ids))
                    ids = tuple(self.user_ids)
                    cursor.execute(
                        "DELETE FROM face_enrollment_challenges WHERE user_id IN (" + ph + ")", ids)
                    cursor.execute("DELETE FROM users WHERE id IN (" + ph + ")", ids)
                if self.seed_ids:
                    if self.seed_ids.get("class"):
                        cursor.execute(
                            "DELETE FROM attendance_day_snapshots WHERE class_id=%s",
                            (self.seed_ids["class"],))
                    cursor.execute(
                        "DELETE FROM attendance_schedules WHERE academic_year_id=%s",
                        (self.seed_ids["year"],))
                    cursor.execute(
                        "DELETE FROM schedule_exceptions WHERE academic_year_id=%s",
                        (self.seed_ids["year"],))
                    cursor.execute("DELETE FROM classes WHERE academic_year_id=%s",
                                   (self.seed_ids["year"],))
                    cursor.execute("DELETE FROM academic_years WHERE id=%s",
                                   (self.seed_ids["year"],))
        finally:
            self.context.pop()

    def _row(self, student_id: int):
        with get_db().cursor() as cursor:
            cursor.execute(
                "SELECT id, status, status_source, checkin_at FROM attendance_records"
                " WHERE student_id=%s AND attendance_date=%s",
                (student_id, FOR_DATE))
            return cursor.fetchone()

    def _audit_count(self, student_id: int) -> int:
        with get_db().cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM audit_logs"
                " WHERE actor_user_id IS NULL AND action='attendance_alpa_finalized'"
                " AND target_type='attendance_record'"
                " AND target_id IN (SELECT id FROM attendance_records"
                "                   WHERE student_id=%s AND attendance_date=%s)",
                (student_id, FOR_DATE))
            return int(cursor.fetchone()["cnt"])

    def _insert_record(self, student_id: int, *, status=None, status_source=None,
                       checkin_at=None) -> None:
        with transaction() as (_, cursor):
            cursor.execute(
                """INSERT INTO attendance_records
                   (student_id, class_id, attendance_date, status, status_source, checkin_at)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (student_id, self.seed_ids["class"], FOR_DATE,
                 status, status_source, checkin_at))

    def test_job_marks_only_fresh_student_and_preserves_others(self):
        self._insert_record(self.present_id, status="present", status_source="system",
                            checkin_at=datetime(2026, 9, 24, 7, 0))
        self._insert_record(self.manual_id, status="permit", status_source="teacher")

        summary = finalize_alpa(for_date=FOR_DATE, at=AT_NOON)

        # >= 3 karena database development boleh berisi roster demo lain;
        # roster tanpa jadwal terskip tanpa tulisan (lihat skip_reasons).
        self.assertGreaterEqual(summary["candidates"], 3)
        # Lower bounds: database development boleh berisi roster demo lain
        # yang ikut terskip dengan alasannya masing-masing.
        self.assertGreaterEqual(summary["processed"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertGreaterEqual(summary["skip_reasons"]["has_presence"], 1)
        self.assertGreaterEqual(summary["skip_reasons"]["has_manual_status"], 1)

        fresh = self._row(self.fresh_id)
        self.assertIsNotNone(fresh)
        self.assertEqual(fresh["status"], "absent")
        self.assertEqual(fresh["status_source"], "finalization_job")
        self.assertIsNone(fresh["checkin_at"])
        self.assertEqual(self._audit_count(self.fresh_id), 1)

        present = self._row(self.present_id)
        self.assertEqual(present["status"], "present")
        self.assertIsNotNone(present["checkin_at"])
        manual = self._row(self.manual_id)
        self.assertEqual(manual["status"], "permit")
        self.assertEqual(manual["status_source"], "teacher")

    def test_second_run_is_idempotent(self):
        first = finalize_alpa(for_date=FOR_DATE, at=AT_NOON)
        self.assertEqual(first["processed"], 3)

        second = finalize_alpa(for_date=FOR_DATE, at=AT_NOON)
        self.assertEqual(second["processed"], 0)
        self.assertGreaterEqual(second["skip_reasons"]["has_manual_status"], 3)

        self.assertEqual(self._row(self.fresh_id)["status"], "absent")
        self.assertEqual(self._audit_count(self.fresh_id), 1)

    def test_holiday_creates_no_alpa(self):
        """AC-10 via real resolver: school holiday -> zero records written."""
        with transaction() as (_, cursor):
            cursor.execute(
                """INSERT INTO schedule_exceptions
                   (academic_year_id, exception_date, scope, class_id, exception_type, is_active)
                   VALUES (%s, %s, 'school', NULL, 'holiday', 1)""",
                (self.seed_ids["year"], FOR_DATE.isoformat()))
        summary = finalize_alpa(for_date=FOR_DATE, at=AT_NOON)
        self.assertEqual(summary["processed"], 0)
        self.assertEqual(summary["skip_reasons"]["holiday"], 3)
        for student_id in self.student_ids:
            self.assertIsNone(self._row(student_id))

    def test_before_cutoff_writes_nothing(self):
        summary = finalize_alpa(
            for_date=FOR_DATE, at=datetime(2026, 9, 24, 7, 0))
        self.assertEqual(summary["processed"], 0)
        self.assertGreaterEqual(summary["skip_reasons"]["before_cutoff"], 3)
        for student_id in self.student_ids:
            self.assertIsNone(self._row(student_id))

    def test_dry_run_counts_without_writing(self):
        summary = finalize_alpa(for_date=FOR_DATE, at=AT_NOON, dry_run=True)
        self.assertTrue(summary["dry_run"])
        # >= 3 karena database development boleh berisi roster demo lain.
        self.assertGreaterEqual(summary["candidates"], 3)
        self.assertEqual(summary["processed"], 3)
        for student_id in self.student_ids:
            self.assertIsNone(self._row(student_id))

    def test_stale_record_read_rechecks_under_lock(self):
        """Benturan dengan submit: bulk read misses records that land first."""
        stale: dict[int, dict] = {}  # pretends no records existed yet
        with patch("app.services.finalization_service._load_records",
                   return_value=stale):
            # Check-in and a teacher status arrive after the bulk read.
            self._insert_record(self.fresh_id, status="present",
                                status_source="system",
                                checkin_at=datetime(2026, 9, 24, 7, 0))
            self._insert_record(self.present_id, status="late",
                                status_source="system",
                                checkin_at=datetime(2026, 9, 24, 7, 30))
            self._insert_record(self.manual_id, status="permit",
                                status_source="teacher")
            summary = finalize_alpa(for_date=FOR_DATE, at=AT_NOON)

        self.assertEqual(summary["processed"], 0)
        self.assertGreaterEqual(summary["skip_reasons"]["has_presence"], 2)
        self.assertGreaterEqual(summary["skip_reasons"]["has_manual_status"], 1)
        self.assertEqual(self._row(self.fresh_id)["status"], "present")
        self.assertEqual(self._row(self.manual_id)["status"], "permit")
        self.assertEqual(self._audit_count(self.fresh_id), 0)


if __name__ == "__main__":
    unittest.main()
