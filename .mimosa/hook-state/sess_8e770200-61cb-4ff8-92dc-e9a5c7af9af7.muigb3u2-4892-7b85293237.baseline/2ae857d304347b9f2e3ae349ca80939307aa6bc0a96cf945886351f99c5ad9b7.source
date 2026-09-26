"""Verify Admin monitoring counts, filters, pagination, and history on dev MySQL."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import secrets

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import transaction
from app.services.auth_service import credential_stamp
from app.services.admin_attendance_service import get_admin_attendance
from app.services.schedule_service import application_now


def main() -> None:
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke T25 hanya boleh memakai database development/test.")
    suffix = secrets.token_hex(4)
    password_hash = generate_password_hash(f"Synthetic-T25-{suffix}-password")
    user_ids: list[int] = []
    student_ids: list[int] = []
    class_ids: list[int] = []
    record_ids: list[int] = []
    year_id: int | None = None
    context = app.app_context()
    context.push()
    try:
        moment = application_now()
        today = moment.date()
        past = today - timedelta(days=1)
        month = today.strftime("%Y-%m")
        old_month = past.strftime("%Y-%m")
        baseline = get_admin_attendance(today.isoformat(), None, None, None, None, at=moment)
        with transaction() as (_, cursor):
            cursor.execute(
                """INSERT INTO users (username,password_hash,role,is_active,must_change_password)
                   VALUES (%s,%s,'admin',1,0)""",
                (f"smoke-t25-admin-{suffix}", password_hash),
            )
            admin_user_id = int(cursor.lastrowid)
            user_ids.append(admin_user_id)
            cursor.execute(
                """INSERT INTO academic_years (name,start_date,end_date,is_active)
                   VALUES (%s,%s,%s,1)""",
                (f"T25-{suffix}", date(today.year, 1, 1), date(today.year, 12, 31)),
            )
            year_id = int(cursor.lastrowid)
            for name in (f"X-T25-{suffix}", f"Y-T25-{suffix}"):
                cursor.execute(
                    "INSERT INTO classes (academic_year_id,name,is_active) VALUES (%s,%s,1)",
                    (year_id, name),
                )
                class_ids.append(int(cursor.lastrowid))
            class_one, holiday_class = class_ids
            cursor.execute(
                """INSERT INTO attendance_schedules
                   (academic_year_id,day_of_week,checkin_start,late_after,checkin_cutoff,
                    checkout_start,is_active)
                   VALUES (%s,%s,'06:30','07:15','08:00','15:00',1)""",
                (year_id, today.isoweekday()),
            )
            cursor.execute(
                """INSERT INTO schedule_exceptions
                   (academic_year_id,exception_date,scope,class_id,exception_type,is_active)
                   VALUES (%s,%s,'class',%s,'holiday',1)""",
                (year_id, today, holiday_class),
            )

            def add_student(label: str, class_id: int, *, active: bool = True) -> int:
                cursor.execute(
                    """INSERT INTO users
                       (username,password_hash,role,is_active,must_change_password)
                       VALUES (%s,%s,'student',%s,0)""",
                    (f"smoke-t25-{label}-{suffix}", password_hash, active),
                )
                user_id = int(cursor.lastrowid)
                user_ids.append(user_id)
                nisn = f"90{int(suffix, 16):010d}{len(student_ids):02d}"
                cursor.execute(
                    """INSERT INTO students (user_id,nisn,full_name,face_registered)
                       VALUES (%s,%s,%s,1)""",
                    (user_id, nisn, f"T25 {label} {suffix}"),
                )
                student_id = int(cursor.lastrowid)
                student_ids.append(student_id)
                cursor.execute(
                    """INSERT INTO student_class_enrollments
                       (student_id,academic_year_id,class_id) VALUES (%s,%s,%s)""",
                    (student_id, year_id, class_id),
                )
                return student_id

            def add_record(student_id: int, class_id: int, for_date: date,
                           status: str | None, *, notes: str | None = None) -> int:
                cursor.execute(
                    """INSERT INTO attendance_records
                       (student_id,class_id,attendance_date,status,status_source,notes,
                        checkin_at,checkout_at,checkin_photo,checkin_latitude,
                        checkin_longitude,checkin_accuracy,checkin_face_score)
                       VALUES (%s,%s,%s,%s,'system',%s,%s,%s,'private/t25.webp',-5.12,97.15,8,12.3)""",
                    (student_id, class_id, for_date, status, notes,
                     datetime.combine(for_date, time(1, 0)) if status in {"present", "late"} else None,
                     datetime.combine(for_date, time(7, 0)) if status in {"present", "late"} else None),
                )
                record_id = int(cursor.lastrowid)
                record_ids.append(record_id)
                return record_id

            present = add_student("Rani", class_one)
            late = add_student("terlambat", class_one)
            absent = add_student("alpa", class_one)
            add_student("belum", class_one)
            inactive = add_student("nonaktif", class_one, active=False)
            permit = add_student("izin", holiday_class)
            add_student("libur-tanpa-record", holiday_class)

            rani_record_id = add_record(present, class_one, today, "present", notes="catatan uji")
            add_record(late, class_one, today, "late")
            add_record(absent, class_one, today, "absent")
            add_record(inactive, class_one, today, "absent")
            add_record(permit, holiday_class, today, "permit")

            for index in range(25):
                extra = add_student(f"arsip-{index:02d}", class_one)
                add_record(extra, class_one, today, "present")

            old_record_id = add_record(absent, class_one, past, "sick")
            add_record(add_student("status-kosong-historis", class_one), class_one, past, None)

        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = admin_user_id
            session["credential_stamp"] = credential_stamp(password_hash)
            session["_csrf_token"] = secrets.token_urlsafe(24)

        response = client.get(f"/admin/attendance?date={today.isoformat()}")
        assert response.status_code == 200, response.get_data(as_text=True)
        body = response.get_data(as_text=True)
        global_summary = get_admin_attendance(today.isoformat(), None, None, None, None, at=moment)["summary"]
        for key, delta in (("present", 26), ("late", 1), ("permit", 1),
                           ("sick", 0), ("absent", 1), ("pending", 3), ("total", 32)):
            assert global_summary[key] == baseline["summary"][key] + delta, (
                key, baseline["summary"], global_summary
            )
        assert "Hadir" in body and "Terlambat" in body and "Belum Absen" in body
        assert "private/t25.webp" not in body
        assert "-5.12" not in body and "97.15" not in body and "12.3" not in body

        with_class = client.get(
            f"/admin/attendance?date={today.isoformat()}&class_id={class_ids[0]}"
        )
        assert with_class.status_code == 200
        class_body = with_class.get_data(as_text=True)
        assert "26" in class_body and "Halaman 1 dari 2" in class_body
        assert "T25 izin" not in class_body
        class_model = get_admin_attendance(
            today.isoformat(), str(class_ids[0]), None, None, None, at=moment
        )
        assert class_model["summary"] == {
            "total": 30, "present": 26, "late": 1, "permit": 0,
            "sick": 0, "absent": 1, "pending": 2,
        }
        second_page = client.get(
            f"/admin/attendance?date={today.isoformat()}&class_id={class_ids[0]}&page=2"
        )
        assert second_page.status_code == 200
        assert "Halaman 2 dari 2" in second_page.get_data(as_text=True)

        filtered = client.get(
            f"/admin/attendance?date={today.isoformat()}&class_id={class_ids[0]}"
            f"&status=present&q=Rani"
        )
        assert filtered.status_code == 200
        filtered_body = filtered.get_data(as_text=True)
        assert "T25 Rani" in filtered_body and "1 record cocok" in filtered_body
        assert "T25 terlambat" not in filtered_body
        assert f"/attendance/{rani_record_id}/evidence" in filtered_body
        for wild in ("%25", "_"):
            wild_response = client.get(
                f"/admin/attendance?date={today.isoformat()}&class_id={class_ids[0]}&q={wild}"
            )
            assert wild_response.status_code == 200, wild_response.get_data(as_text=True)
            assert "Tidak ada record yang cocok" in wild_response.get_data(as_text=True), wild
        print("t25_wildcard_search_literal=ok")
        assert client.get(f"/admin/attendance?date={today.isoformat()}&class_id=999999").status_code == 400
        assert client.get(f"/admin/attendance?date={today.isoformat()}&status=unknown").status_code == 400
        assert client.get(f"/admin/attendance?date={today.isoformat()}&page=abc").status_code == 400

        holiday_summary = client.get(
            f"/admin/attendance?date={today.isoformat()}&class_id={holiday_class}"
        )
        holiday_body = holiday_summary.get_data(as_text=True)
        holiday_model = get_admin_attendance(
            today.isoformat(), str(holiday_class), None, None, None, at=moment
        )
        assert holiday_summary.status_code == 200
        assert holiday_model["summary"] == {
            "total": 2, "present": 0, "late": 0, "permit": 1,
            "sick": 0, "absent": 0, "pending": 1,
        }
        assert "Belum Absen" in holiday_body

        historical = client.get(
            f"/admin/attendance?date={past.isoformat()}&class_id={class_ids[0]}"
        )
        historical_body = historical.get_data(as_text=True)
        assert historical.status_code == 200
        historical_model = get_admin_attendance(
            past.isoformat(), str(class_ids[0]), None, None, None, at=moment
        )
        assert historical_model["summary"]["sick"] == 1
        assert historical_model["summary"]["pending"] == 0
        assert historical_model["summary"]["total"] == 1
        assert "Status tersimpan" in historical_body and "2 record cocok" in historical_body
        assert "Status belum tercatat" in historical_body
        assert f"/attendance/{old_record_id}/evidence" in historical_body

        student_history = client.get(f"/admin/students/{absent}?month={old_month}")
        assert student_history.status_code == 200, student_history.get_data(as_text=True)
        assert past.isoformat() in student_history.get_data(as_text=True)

        empty = client.get(
            f"/admin/attendance?date={(past - timedelta(days=90)).isoformat()}"
            f"&class_id={class_ids[0]}"
        )
        assert empty.status_code == 200 and "Tidak ada record yang cocok" in empty.get_data(as_text=True)
        assert "Tidak ada record yang cocok" in client.get(
            f"/admin/attendance?date={today.isoformat()}&q=tidak-ada"
        ).get_data(as_text=True)
        print("T25 MySQL smoke PASS: all-class counts, active roster pending, class holiday, filters, pagination=25, stored-only history, Admin student month, empty state, privacy.")
    finally:
        try:
            with transaction() as (_, cursor):
                if record_ids:
                    marks = ",".join(["%s"] * len(record_ids))
                    cursor.execute(f"DELETE FROM attendance_records WHERE id IN ({marks})", tuple(record_ids))
                if student_ids:
                    marks = ",".join(["%s"] * len(student_ids))
                    cursor.execute(
                        f"DELETE FROM student_class_enrollments WHERE student_id IN ({marks})",
                        tuple(student_ids),
                    )
                    cursor.execute(f"DELETE FROM students WHERE id IN ({marks})", tuple(student_ids))
                if class_ids:
                    marks = ",".join(["%s"] * len(class_ids))
                    cursor.execute(f"DELETE FROM schedule_exceptions WHERE class_id IN ({marks})", tuple(class_ids))
                    cursor.execute("DELETE FROM attendance_schedules WHERE academic_year_id=%s", (year_id,))
                    cursor.execute(f"DELETE FROM classes WHERE id IN ({marks})", tuple(class_ids))
                if user_ids:
                    marks = ",".join(["%s"] * len(user_ids))
                    cursor.execute(f"DELETE FROM users WHERE id IN ({marks})", tuple(user_ids))
                if year_id:
                    cursor.execute("DELETE FROM academic_years WHERE id=%s", (year_id,))
            print("cleanup=ok")
        finally:
            context.pop()


if __name__ == "__main__":
    main()
