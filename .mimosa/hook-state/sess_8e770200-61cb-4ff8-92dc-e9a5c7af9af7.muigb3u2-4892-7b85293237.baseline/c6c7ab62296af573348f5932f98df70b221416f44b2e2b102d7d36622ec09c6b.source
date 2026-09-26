"""Exercise assignment-scoped Guru monitoring against development MySQL."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import secrets

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, transaction
from app.services.auth_service import credential_stamp
from app.services.schedule_service import application_now


def main() -> None:
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke T22 hanya boleh memakai database development/test.")
    suffix = secrets.token_hex(4)
    password_hash = generate_password_hash(f"SyntheticT22-{suffix}-password")
    user_ids: list[int] = []
    student_ids: list[int] = []
    teacher_user_ids: list[int] = []
    teacher_ids: list[int] = []
    class_ids: list[int] = []
    year_ids: list[int] = []
    seeded_students: dict[str, int] = {}
    context = app.app_context()
    context.push()
    try:
        moment = application_now()
        today = moment.date()
        old_day = today - timedelta(days=370)
        month = today.strftime("%Y-%m")
        old_month = old_day.strftime("%Y-%m")

        with transaction() as (_, cursor):
            for role_name in ("satu", "dua"):
                cursor.execute(
                    "INSERT INTO users (username,password_hash,role,is_active,must_change_password) VALUES (%s,%s,'teacher',1,0)",
                    (f"smoke-t22-guru-{role_name}-{suffix}", password_hash),
                )
                teacher_user_id = int(cursor.lastrowid)
                user_ids.append(teacher_user_id)
                teacher_user_ids.append(teacher_user_id)
                cursor.execute(
                    "INSERT INTO teachers (user_id,full_name,employee_number) VALUES (%s,%s,%s)",
                    (teacher_user_id, f"Guru Smoke T22 {role_name} {suffix}", f"T22{suffix}{role_name}"),
                )
                teacher_ids.append(int(cursor.lastrowid))

            for year_name, start, end, active in (
                (f"2026/T22{suffix}", date(today.year, 1, 1), date(today.year, 12, 31), 1),
                (f"{old_day.year}/T22{suffix}", date(old_day.year, 1, 1), date(old_day.year, 12, 31), 0),
            ):
                cursor.execute(
                    "INSERT INTO academic_years (name,start_date,end_date,is_active) VALUES (%s,%s,%s,%s)",
                    (year_name, start, end, active),
                )
                year_ids.append(int(cursor.lastrowid))
            current_year, old_year = year_ids

            for year_id, teacher_id, name, active in (
                (current_year, teacher_ids[0], f"X-T22-{suffix}", 1),
                (current_year, teacher_ids[1], f"Y-T22-{suffix}", 1),
                (old_year, teacher_ids[0], f"Z-T22-{suffix}", 0),
            ):
                cursor.execute(
                    "INSERT INTO classes (academic_year_id,name,teacher_id,is_active) VALUES (%s,%s,%s,%s)",
                    (year_id, name, teacher_id, active),
                )
                class_ids.append(int(cursor.lastrowid))
            class_one, class_two, old_class = class_ids

            for year_id, day in ((current_year, today), (old_year, old_day)):
                cursor.execute(
                    """INSERT INTO attendance_schedules
                       (academic_year_id,day_of_week,checkin_start,late_after,checkin_cutoff,checkout_start,is_active)
                       VALUES (%s,%s,'00:00','00:01','00:02','00:03',1)""",
                    (year_id, day.isoweekday()),
                )

            def add_student(label: str, class_id: int, year_id: int, *, active: bool = True) -> int:
                cursor.execute(
                    "INSERT INTO users (username,password_hash,role,is_active,must_change_password) VALUES (%s,%s,'student',%s,0)",
                    (f"smoke-t22-{label}-{suffix}", password_hash, active),
                )
                user_id = int(cursor.lastrowid)
                user_ids.append(user_id)
                cursor.execute(
                    "INSERT INTO students (user_id,nisn,full_name,face_registered) VALUES (%s,%s,%s,1)",
                    (user_id, f"{suffix}{len(student_ids):04d}", f"Siswa T22 {label} {suffix}"),
                )
                student_id = int(cursor.lastrowid)
                student_ids.append(student_id)
                cursor.execute(
                    "INSERT INTO student_class_enrollments (student_id,academic_year_id,class_id) VALUES (%s,%s,%s)",
                    (student_id, year_id, class_id),
                )
                seeded_students[label] = student_id
                return student_id

            labels = ("hadir", "terlambat", "izin", "sakit", "alpa", "kosong", "belum-pulang", "tanpa-snapshot")
            for label in labels:
                add_student(label, class_one, current_year)
            foreign_student_id = add_student("kelas-guru-dua", class_two, current_year)
            old_student_id = add_student("historis-nonaktif", old_class, old_year, active=False)
            for index in range(25):
                add_student(f"arsip-{index:02d}", class_one, current_year, active=False)

            # Normal present/late records have a completed checkout. Only selected
            # display columns are expected in Guru HTML; all evidence remains private.
            cursor.execute(
                """INSERT INTO attendance_records
                   (student_id,class_id,attendance_date,status,status_source,notes,checkin_at,checkout_at,
                    checkin_photo,checkin_latitude,checkin_longitude,checkin_accuracy,checkin_face_score,checkin_liveness_verified)
                   VALUES (%s,%s,%s,'present','system','catatan sintetis',%s,%s,'private/t22.webp',5.1,97.1,8,12.3,1)""",
                (seeded_students["hadir"], class_one, today,
                 datetime.combine(today, time(1, 35)), datetime.combine(today, time(7, 20))),
            )
            cursor.execute(
                """INSERT INTO attendance_records
                   (student_id,class_id,attendance_date,status,status_source,checkin_at,checkout_at)
                   VALUES (%s,%s,%s,'late','system',%s,%s)""",
                (seeded_students["terlambat"], class_one, today,
                 datetime.combine(today, time(1, 40)), datetime.combine(today, time(7, 20))),
            )
            for label, status in (("izin", "permit"), ("sakit", "sick"), ("alpa", "absent")):
                cursor.execute(
                    """INSERT INTO attendance_records
                       (student_id,class_id,attendance_date,status,status_source,notes)
                       VALUES (%s,%s,%s,%s,'teacher','catatan uji')""",
                    (seeded_students[label], class_one, today, status),
                )
            cursor.execute(
                """INSERT INTO attendance_records
                   (student_id,class_id,attendance_date,status,status_source,checkin_at)
                   VALUES (%s,%s,%s,'present','system',%s)""",
                (seeded_students["belum-pulang"], class_one, today,
                 datetime.combine(today, time(1, 30))),
            )
            # A roster student with a NULL snapshot is deliberately invisible in
            # class-scoped journal/detail queries and counts as no class record.
            cursor.execute(
                """INSERT INTO attendance_records
                   (student_id,class_id,attendance_date,status,status_source,checkin_at,
                    checkin_photo,checkin_latitude,checkin_accuracy)
                   VALUES (%s,NULL,%s,'present','system',%s,'private/no-snapshot.webp',5.2,7)""",
                (seeded_students["tanpa-snapshot"], today, datetime.combine(today, time(1, 32))),
            )
            cursor.execute(
                """INSERT INTO attendance_records
                   (student_id,class_id,attendance_date,status,status_source,notes)
                   VALUES (%s,%s,%s,'absent','finalization_job','histori lama')""",
                (old_student_id, old_class, old_day),
            )

            for index in range(25):
                student_id = seeded_students[f"arsip-{index:02d}"]
                cursor.execute(
                    """INSERT INTO attendance_records
                       (student_id,class_id,attendance_date,status,status_source,notes)
                       VALUES (%s,%s,%s,'present','system','record arsip sintetis')""",
                    (student_id, class_one, today),
                )
            cursor.execute(
                """INSERT INTO attendance_records
                   (student_id,class_id,attendance_date,status,status_source)
                   VALUES (%s,%s,%s,'present','system')""",
                (foreign_student_id, class_two, today),
            )

        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = teacher_user_ids[0]
            session["credential_stamp"] = credential_stamp(password_hash)
            session["_csrf_token"] = secrets.token_urlsafe(24)

        dashboard = client.get("/teacher/dashboard")
        assert dashboard.status_code == 200, dashboard.get_data(as_text=True)
        body = dashboard.get_data(as_text=True)
        for label, count in (("Siswa aktif", "8"), ("Hadir", "2"), ("Terlambat", "1"),
                             ("Izin", "1"), ("Sakit", "1"), ("Alpa", "1"), ("Belum Absen", "2")):
            assert label in body and count in body, (label, count)
        assert "Belum masuk setelah batas check-in" in body
        assert "Belum melakukan presensi pulang" in body
        assert "Alpa tercatat" in body
        assert "private/t22.webp" not in body and "97.1" not in body and "12.3" not in body

        with transaction() as (_, cursor):
            cursor.execute(
                """INSERT INTO schedule_exceptions
                   (academic_year_id,exception_date,scope,class_id,exception_type,is_active)
                   VALUES (%s,%s,'school',NULL,'holiday',1)""",
                (current_year, today),
            )
        holiday_dashboard = client.get(f"/teacher/dashboard?class_id={class_one}")
        holiday_body = holiday_dashboard.get_data(as_text=True)
        review_section = holiday_body.split("Daftar tindak lanjut", 1)[-1]
        assert "Alpa tercatat" in review_section
        assert "Belum masuk setelah batas check-in" not in review_section
        assert "Belum melakukan presensi pulang" not in review_section

        journal = client.get(f"/teacher/attendance?class_id={class_one}&month={month}")
        assert journal.status_code == 200, journal.get_data(as_text=True)
        with get_db().cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS total FROM attendance_records WHERE class_id=%s AND attendance_date>=%s AND attendance_date<%s",
                (class_one, date(today.year, today.month, 1),
                 date(today.year + (today.month == 12), 1 if today.month == 12 else today.month + 1, 1)),
            )
            journal_total = int(cursor.fetchone()["total"])
        assert journal_total == 31, journal_total
        assert "Halaman 1 dari 2" in journal.get_data(as_text=True)
        page_two = client.get(f"/teacher/attendance?class_id={class_one}&month={month}&page=2")
        assert page_two.status_code == 200 and "Halaman 2 dari 2" in page_two.get_data(as_text=True)
        filtered = client.get(f"/teacher/attendance?class_id={class_one}&month={month}&status=permit&q=izin")
        assert filtered.status_code == 200 and "Siswa T22 izin" in filtered.get_data(as_text=True)
        assert "private/t22.webp" not in journal.get_data(as_text=True)
        assert client.get(f"/teacher/attendance?class_id={class_one}&month={month}&status=not-a-status").status_code == 400
        assert client.get(f"/teacher/attendance?class_id={class_one}&month={month}&page=abc").status_code == 400

        roster = client.get(f"/teacher/students?class_id={class_one}")
        assert roster.status_code == 200 and "Halaman 1 dari 2" in roster.get_data(as_text=True)
        roster_page_two = client.get(f"/teacher/students?class_id={class_one}&page=2")
        assert roster_page_two.status_code == 200 and "Halaman 2 dari 2" in roster_page_two.get_data(as_text=True)
        assert "Nonaktif" in roster.get_data(as_text=True)
        searched = client.get(f"/teacher/students?class_id={class_one}&q={suffix}0007")
        assert searched.status_code == 200 and "Siswa T22 tanpa-snapshot" in searched.get_data(as_text=True)
        for wild in ("%25", "_"):
            wild_journal = client.get(
                f"/teacher/attendance?class_id={class_one}&month={month}&q={wild}"
            )
            assert wild_journal.status_code == 200, wild_journal.get_data(as_text=True)
            assert "Tidak ada record yang cocok" in wild_journal.get_data(as_text=True), wild
            wild_roster = client.get(f"/teacher/students?class_id={class_one}&q={wild}")
            assert wild_roster.status_code == 200, wild_roster.get_data(as_text=True)
            assert "Tidak ada siswa yang cocok" in wild_roster.get_data(as_text=True), wild
        print("t22_wildcard_search_literal=ok")

        foreign = client.get(f"/teacher/students?class_id={class_two}")
        assert foreign.status_code == 404
        foreign_detail = client.get(f"/teacher/students/{foreign_student_id}?class_id={class_one}&month={month}")
        assert foreign_detail.status_code == 404
        saved_detail = client.get(
            f"/teacher/students/{seeded_students['hadir']}?class_id={class_one}&month={month}&date={today.isoformat()}&source=attendance&status=present&q={suffix}&page=2"
        )
        assert saved_detail.status_code == 200, saved_detail.get_data(as_text=True)
        detail_body = saved_detail.get_data(as_text=True)
        assert "08:35" in detail_body and "14:20" in detail_body
        assert "private/t22.webp" not in detail_body and "97.1" not in detail_body
        assert "q=" in detail_body and "Kembali ke jurnal presensi" in detail_body

        old_detail = client.get(
            f"/teacher/students/{old_student_id}?class_id={old_class}&month={old_month}&date={old_day.isoformat()}"
        )
        assert old_detail.status_code == 200 and "Alpa" in old_detail.get_data(as_text=True)
        no_snapshot_detail = client.get(
            f"/teacher/students/{seeded_students['tanpa-snapshot']}?class_id={class_one}&month={month}&date={today.isoformat()}"
        )
        assert no_snapshot_detail.status_code == 200
        assert "Tidak ada record" in no_snapshot_detail.get_data(as_text=True)

        with transaction() as (_, cursor):
            cursor.execute("UPDATE classes SET teacher_id=%s WHERE id=%s", (teacher_ids[1], class_one))
        assert client.get(f"/teacher/students?class_id={class_one}").status_code == 404
        with client.session_transaction() as session:
            session["user_id"] = teacher_user_ids[1]
            session["credential_stamp"] = credential_stamp(password_hash)
        newly_assigned = client.get(f"/teacher/students?class_id={class_one}")
        assert newly_assigned.status_code == 200, newly_assigned.get_data(as_text=True)
        print("t22_mysql_smoke=ok; summary=ok; review_reasons=ok; pagination=25; filters=ok; assigned_scope=ok; reassignment=immediate; inactive_history=ok; null_snapshot=omitted; private_fields=omitted")
    finally:
        try:
            with transaction() as (_, cursor):
                if student_ids:
                    placeholders = ",".join(["%s"] * len(student_ids))
                    cursor.execute(f"DELETE FROM attendance_records WHERE student_id IN ({placeholders})", tuple(student_ids))
                    cursor.execute(f"DELETE FROM student_class_enrollments WHERE student_id IN ({placeholders})", tuple(student_ids))
                    cursor.execute(f"DELETE FROM students WHERE id IN ({placeholders})", tuple(student_ids))
                if class_ids:
                    placeholders = ",".join(["%s"] * len(class_ids))
                    year_placeholders = ",".join(["%s"] * len(year_ids))
                    cursor.execute(f"DELETE FROM schedule_exceptions WHERE academic_year_id IN ({year_placeholders})", tuple(year_ids))
                    cursor.execute(f"DELETE FROM attendance_schedules WHERE academic_year_id IN ({year_placeholders})", tuple(year_ids))
                    cursor.execute(f"DELETE FROM classes WHERE id IN ({placeholders})", tuple(class_ids))
                if teacher_ids:
                    placeholders = ",".join(["%s"] * len(teacher_ids))
                    cursor.execute(f"DELETE FROM teachers WHERE id IN ({placeholders})", tuple(teacher_ids))
                if user_ids:
                    placeholders = ",".join(["%s"] * len(user_ids))
                    cursor.execute(f"DELETE FROM users WHERE id IN ({placeholders})", tuple(user_ids))
                if year_ids:
                    placeholders = ",".join(["%s"] * len(year_ids))
                    cursor.execute(f"DELETE FROM academic_years WHERE id IN ({placeholders})", tuple(year_ids))
            print("cleanup=ok")
        finally:
            context.pop()


if __name__ == "__main__":
    main()
