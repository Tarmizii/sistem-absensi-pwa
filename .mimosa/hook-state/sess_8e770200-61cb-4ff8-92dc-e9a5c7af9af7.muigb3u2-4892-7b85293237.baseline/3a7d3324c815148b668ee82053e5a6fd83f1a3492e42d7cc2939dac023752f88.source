"""Verify filtered XLSX export and privacy-limited audit reads on dev MySQL."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from io import BytesIO
import json
import secrets

from openpyxl import load_workbook
from werkzeug.security import generate_password_hash

from app import create_app
from app.database import transaction
from app.services.auth_service import credential_stamp
from app.services.admin_audit_service import get_admin_audit_logs
from app.services.schedule_service import application_now


def main() -> None:
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke T26 hanya boleh memakai database development/test.")
    suffix = secrets.token_hex(4)
    password_hash = generate_password_hash(f"Synthetic-T26-{suffix}-password")
    user_ids: list[int] = []
    student_ids: list[int] = []
    record_ids: list[int] = []
    audit_ids: list[int] = []
    class_id: int | None = None
    year_id: int | None = None
    context = app.app_context()
    context.push()
    try:
        today = application_now().date()
        with transaction() as (_, cursor):
            cursor.execute(
                """INSERT INTO users (username,password_hash,role,is_active,must_change_password)
                   VALUES (%s,%s,'admin',1,0)""",
                (f"smoke-t26-admin-{suffix}", password_hash),
            )
            admin_user_id = int(cursor.lastrowid)
            user_ids.append(admin_user_id)
            cursor.execute(
                """INSERT INTO academic_years (name,start_date,end_date,is_active)
                   VALUES (%s,%s,%s,1)""",
                (f"T26-{suffix}", date(today.year, 1, 1), date(today.year, 12, 31)),
            )
            year_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO classes (academic_year_id,name,is_active) VALUES (%s,%s,1)",
                (year_id, f"=2+2 T26 {suffix}"),
            )
            class_id = int(cursor.lastrowid)

            for index in range(27):
                username = f"smoke-t26-student-{index:02d}-{suffix}"
                cursor.execute(
                    """INSERT INTO users (username,password_hash,role,is_active,must_change_password)
                       VALUES (%s,%s,'student',1,0)""",
                    (username, password_hash),
                )
                user_id = int(cursor.lastrowid)
                user_ids.append(user_id)
                nisn = f"91{int(suffix, 16):010d}{index:02d}"
                if index == 0:
                    name = f"=1+1 T26 synthetic {suffix}"
                    notes = f"=HYPERLINK(\"https://synthetic.invalid/{suffix}\")"
                elif index == 1:
                    name = f"\t=HYPERLINK(\"https://synthetic.invalid/{suffix}\")"
                    notes = f"@SUM(A1:A2) {suffix}"
                else:
                    name = f"T26 Siswa {index:02d} {suffix}"
                    notes = None
                cursor.execute(
                    "INSERT INTO students (user_id,nisn,full_name,face_registered) VALUES (%s,%s,%s,1)",
                    (user_id, nisn, name),
                )
                student_id = int(cursor.lastrowid)
                student_ids.append(student_id)
                cursor.execute(
                    """INSERT INTO student_class_enrollments
                       (student_id,academic_year_id,class_id) VALUES (%s,%s,%s)""",
                    (student_id, year_id, class_id),
                )
                cursor.execute(
                    """INSERT INTO attendance_records
                       (student_id,class_id,attendance_date,status,status_source,notes,
                        checkin_at,checkout_at,checkin_photo,checkin_latitude,
                        checkin_longitude,checkin_accuracy,checkin_face_score,
                        checkin_liveness_verified)
                       VALUES (%s,%s,%s,'present','system',%s,%s,%s,'private/t26.webp',
                               -5.12,97.15,8,12.3,1)""",
                    (student_id, class_id, today, notes,
                     datetime.combine(today, time(1, 0)), datetime.combine(today, time(7, 0))),
                )
                record_ids.append(int(cursor.lastrowid))

            sensitive_metadata = json.dumps({
                "password": f"synthetic-secret-{suffix}",
                "storage_key": "faces/synthetic.webp",
                "checkin_latitude": -5.12,
            })
            for index in range(27):
                cursor.execute(
                    """INSERT INTO audit_logs
                       (actor_user_id,action,target_type,target_id,metadata,created_at)
                       VALUES (%s,'student_updated','student',%s,%s,%s)""",
                    (admin_user_id, student_ids[index], sensitive_metadata,
                     datetime.combine(today, time(2, 0)) + timedelta(seconds=index)),
                )
                audit_ids.append(int(cursor.lastrowid))
            cursor.execute(
                """INSERT INTO audit_logs
                   (actor_user_id,action,target_type,target_id,metadata,created_at)
                   VALUES (%s,'teacher_created','teacher',%s,'{}',%s)""",
                (admin_user_id, 812, datetime.combine(today, time(1, 30))),
            )
            audit_ids.append(int(cursor.lastrowid))

        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = admin_user_id
            session["credential_stamp"] = credential_stamp(password_hash)
            session["_csrf_token"] = secrets.token_urlsafe(24)

        export = client.get(
            f"/admin/attendance/export.xlsx?date={today.isoformat()}&class_id={class_id}"
            f"&status=present&q={suffix}"
        )
        assert export.status_code == 200, export.get_data(as_text=True)
        assert export.headers.get("Cache-Control") == "no-store"
        workbook = load_workbook(BytesIO(export.data), data_only=False)
        sheet = workbook["Presensi"]
        assert sheet.max_row == 28, sheet.max_row
        assert sheet.freeze_panes == "A2"
        assert sheet.auto_filter.ref == sheet.dimensions
        headers = [cell.value for cell in sheet[1]]
        assert headers == [
            "Tanggal", "Kelas", "NISN", "Nama Siswa", "Status", "Sumber",
            "Masuk WIB", "Pulang WIB", "Keterangan",
        ]
        assert not any(word in " ".join(headers).lower()
                       for word in ("photo", "latitude", "longitude", "face_score", "liveness", "storage"))
        assert any(str(sheet.cell(row, 4).value).startswith("'=1+1") for row in range(2, 29))
        assert any(str(sheet.cell(row, 9).value).startswith("'=HYPERLINK") for row in range(2, 29))
        for row in sheet.iter_rows():
            for cell in row:
                assert cell.data_type != "f", (cell.coordinate, cell.value)
        assert "private/t26.webp" not in str(list(sheet.values))

        audit_url = (
            f"/admin/audit-logs?actor=smoke-t26-admin-{suffix}"
            f"&from={today.isoformat()}&to={today.isoformat()}&action=student_updated"
        )
        audit = client.get(audit_url)
        assert audit.status_code == 200, audit.get_data(as_text=True)
        audit_body = audit.get_data(as_text=True)
        assert "27 hasil" in audit_body and "Halaman 1 dari 2" in audit_body
        assert f"synthetic-secret-{suffix}" not in audit_body
        assert "faces/synthetic.webp" not in audit_body
        assert "-5.12" not in audit_body
        page_two = client.get(audit_url + "&page=2")
        assert page_two.status_code == 200 and "Halaman 2 dari 2" in page_two.get_data(as_text=True)
        wild_actor = get_admin_audit_logs(
            "%", today.isoformat(), today.isoformat(), "", "1")
        assert wild_actor["total"] == 0, wild_actor["total"]
        wild_underscore = get_admin_audit_logs(
            "_", today.isoformat(), today.isoformat(), "", "1")
        assert wild_underscore["total"] == 0, wild_underscore["total"]
        print("t26_wildcard_actor_literal=ok")
        assert client.get(f"/admin/audit-logs?from={today.isoformat()}&to=2020-01-01").status_code == 400
        assert client.get("/admin/audit-logs?action=unknown").status_code == 400
        print("T26 MySQL smoke PASS: all-filtered XLSX rows=27, formula strings stored as text, sensitive columns omitted, audit actor/date/action filters, pagination=25, metadata omitted.")
    finally:
        try:
            with transaction() as (_, cursor):
                if audit_ids:
                    marks = ",".join(["%s"] * len(audit_ids))
                    cursor.execute(f"DELETE FROM audit_logs WHERE id IN ({marks})", tuple(audit_ids))
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
                if class_id:
                    cursor.execute("DELETE FROM classes WHERE id=%s", (class_id,))
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
