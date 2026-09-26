"""Private read models for the Siswa and Guru attendance screens (T21–T22)."""

from __future__ import annotations

from calendar import Calendar
from datetime import date, datetime, time, timedelta
import re
from typing import Any

from app.database import get_db
from app.services.schedule_service import (
    application_now,
    database_datetime_to_local_time,
    resolve_schedule,
    resolve_schedules,
)


STATUS_LABELS = {
    "present": "Hadir",
    "late": "Terlambat",
    "permit": "Izin",
    "sick": "Sakit",
    "absent": "Alpa",
}
SOURCE_LABELS = {"system": "Sistem", "teacher": "Guru", "finalization_job": "Sistem"}
STORED_STATUSES = frozenset(STATUS_LABELS)
PAGE_SIZE = 25
_MONTH_PATTERN = re.compile(r"\d{4}-(0[1-9]|1[0-2])\Z")
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


class AttendanceReadError(ValueError):
    """Invalid read parameters or an object outside the caller's data scope."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def parse_month(value: str | None) -> tuple[date, date, str]:
    if not isinstance(value, str) or not _MONTH_PATTERN.fullmatch(value):
        raise AttendanceReadError("Bulan harus memakai format YYYY-MM.")
    year, month = (int(part) for part in value.split("-"))
    try:
        start = date(year, month, 1)
        end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    except ValueError:
        raise AttendanceReadError("Bulan tidak valid.") from None
    return start, end, value


def _parse_date(value: str | None, label: str = "Tanggal") -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not _DATE_PATTERN.fullmatch(value):
        raise AttendanceReadError(f"{label} tidak valid.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise AttendanceReadError(f"{label} tidak valid.") from None


def parse_page(value: str | None) -> int:
    if value in (None, ""):
        return 1
    if (not isinstance(value, str) or len(value) > 6
            or not value.isascii() or not value.isdecimal()):
        raise AttendanceReadError("Nomor halaman tidak valid.")
    page = int(value)
    if page < 1 or page > 100_000:
        raise AttendanceReadError("Nomor halaman tidak valid.")
    return page


def _status_label(value: str | None) -> str:
    return STATUS_LABELS.get(value, "Belum Absen")


def _db_time(value: datetime | None) -> str | None:
    return database_datetime_to_local_time(value)


def _calendar_weeks(year: int, month: int) -> list[list[dict[str, Any] | None]]:
    return [
        [None if not day else {"day": day, "date": date(year, month, day).isoformat()}
         for day in week]
        for week in Calendar(firstweekday=0).monthdayscalendar(year, month)
    ]


def get_student_profile(user_id: int, at: datetime | None = None) -> dict[str, Any]:
    moment = application_now() if at is None else at
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT s.id AS student_id, s.full_name, s.nisn
               FROM students AS s JOIN users AS u ON u.id=s.user_id
               WHERE u.id=%s AND u.role='student' AND u.is_active=1 LIMIT 1""",
            (user_id,),
        )
        student = cursor.fetchone()
        if student is None:
            raise LookupError("Profil Siswa tidak ditemukan.")
        cursor.execute(
            """SELECT c.name AS class_name, ay.name AS academic_year_name
               FROM student_class_enrollments AS sce
               JOIN classes AS c ON c.id=sce.class_id
               JOIN academic_years AS ay ON ay.id=sce.academic_year_id
               WHERE sce.student_id=%s AND ay.start_date<=%s AND ay.end_date>=%s
               ORDER BY ay.is_active DESC, ay.start_date DESC, ay.id DESC LIMIT 1""",
            (student["student_id"], moment.date(), moment.date()),
        )
        placement = cursor.fetchone()
    return {
        "full_name": student["full_name"],
        "nisn": student["nisn"],
        "class_name": placement["class_name"] if placement else None,
        "academic_year_name": placement["academic_year_name"] if placement else None,
    }


def get_student_month_history(user_id: int, month_value: str | None,
                              selected_value: str | None = None,
                              at: datetime | None = None) -> dict[str, Any]:
    start, end_exclusive, month = parse_month(month_value)
    moment = application_now() if at is None else at
    current_month = moment.strftime("%Y-%m")
    if month != current_month:
        raise AttendanceReadError("Siswa hanya dapat membuka kalender bulan berjalan.", 403)
    selected_date = _parse_date(selected_value)
    last_day = end_exclusive - timedelta(days=1)
    if selected_date and (selected_date < start or selected_date > last_day):
        raise AttendanceReadError("Tanggal harus berada pada bulan kalender yang dibuka.")

    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT s.id AS student_id, s.full_name
               FROM students AS s JOIN users AS u ON u.id=s.user_id
               WHERE u.id=%s AND u.role='student' AND u.is_active=1 LIMIT 1""",
            (user_id,),
        )
        student = cursor.fetchone()
        if student is None:
            raise LookupError("Profil Siswa tidak ditemukan.")
        cursor.execute(
            """SELECT sce.class_id, sce.academic_year_id, c.name AS class_name,
                      ay.name AS academic_year_name, ay.start_date, ay.end_date, ay.is_active
               FROM student_class_enrollments AS sce
               JOIN classes AS c ON c.id=sce.class_id
               JOIN academic_years AS ay ON ay.id=sce.academic_year_id
               WHERE sce.student_id=%s AND ay.start_date<=%s AND ay.end_date>=%s
               ORDER BY ay.is_active DESC, ay.start_date DESC, ay.id DESC""",
            (student["student_id"], last_day, start),
        )
        placements = list(cursor.fetchall())
        cursor.execute(
            """SELECT attendance_date, status, status_source, notes, checkin_at, checkout_at
               FROM attendance_records
               WHERE student_id=%s AND attendance_date>=%s AND attendance_date<%s
               ORDER BY attendance_date""",
            (student["student_id"], start, end_exclusive),
        )
        records = {row["attendance_date"]: row for row in cursor.fetchall()}

    def placement_on(day: date) -> dict[str, Any] | None:
        return next((item for item in placements
                     if item["start_date"] <= day <= item["end_date"]), None)

    days = [date(start.year, start.month, day)
            for day in range(1, last_day.day + 1)]
    missing_past = [day for day in days if day <= moment.date() and day not in records]
    schedules: dict[date, dict[str, Any] | None] = {}
    groups: dict[tuple[int, int], list[date]] = {}
    no_placement: set[date] = set()
    for day in missing_past:
        placement = placement_on(day)
        if placement is None:
            no_placement.add(day)
        else:
            groups.setdefault((int(placement["academic_year_id"]), int(placement["class_id"])), []).append(day)
    for (year_id, class_id), group_dates in groups.items():
        schedules.update(resolve_schedules(group_dates, year_id, class_id))

    items: dict[date, dict[str, Any]] = {}
    for day in days:
        record = records.get(day)
        placement = placement_on(day)
        if record is not None:
            status = _status_label(record["status"])
            item = {
                "date": day.isoformat(), "day": day.day, "status": status,
                "status_key": record["status"] or "pending",
                "source": SOURCE_LABELS.get(record["status_source"]),
                "checkin_time": _db_time(record["checkin_at"]),
                "checkout_time": _db_time(record["checkout_at"]),
                "notes": record["notes"], "is_future": False,
                "class_name": placement["class_name"] if placement else None,
                "academic_year_name": placement["academic_year_name"] if placement else None,
            }
        elif day > moment.date():
            item = {"date": day.isoformat(), "day": day.day,
                    "status": "Belum berlangsung", "status_key": "upcoming",
                    "is_future": True, "class_name": None}
        elif day in no_placement:
            item = {"date": day.isoformat(), "day": day.day,
                    "status": "Tidak ada kelas", "status_key": "no_class",
                    "is_future": False, "class_name": None}
        else:
            schedule = schedules.get(day)
            if schedule is None:
                status, key = "Tidak ada jadwal", "no_schedule"
            elif schedule["is_holiday"]:
                status, key = "Libur", "holiday"
            else:
                status, key = "Belum Absen", "pending"
            item = {"date": day.isoformat(), "day": day.day,
                    "status": status, "status_key": key, "is_future": False,
                    "class_name": placement["class_name"] if placement else None}
        items[day] = item

    weeks = [
        [None if not cell else items[date.fromisoformat(cell["date"])] for cell in week]
        for week in _calendar_weeks(start.year, start.month)
    ]

    if selected_date is None:
        selected_date = moment.date()
    detail = items[selected_date]
    month_names = ("Januari", "Februari", "Maret", "April", "Mei", "Juni",
                   "Juli", "Agustus", "September", "Oktober", "November", "Desember")
    return {
        "full_name": student["full_name"], "month": month,
        "month_label": f"{month_names[start.month - 1]} {start.year}",
        "weeks": weeks,
        "days": [items[day] for day in days],
        "detail": detail,
        "selected_date": selected_date.isoformat(),
        "today": moment.date().isoformat(),
    }


def list_teacher_classes(teacher_user_id: int) -> list[dict[str, Any]]:
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT c.id AS class_id, c.name AS class_name, c.is_active AS class_active,
                      c.academic_year_id, ay.name AS academic_year_name,
                      ay.start_date AS academic_year_start, ay.end_date AS academic_year_end,
                      ay.is_active AS academic_year_active,
                      SUM(CASE WHEN u.is_active=1 THEN 1 ELSE 0 END) AS active_student_count
               FROM classes AS c
               JOIN teachers AS t ON t.id=c.teacher_id
               JOIN users AS tu ON tu.id=t.user_id
               JOIN academic_years AS ay ON ay.id=c.academic_year_id
               LEFT JOIN student_class_enrollments AS sce ON sce.class_id=c.id
               LEFT JOIN students AS s ON s.id=sce.student_id
               LEFT JOIN users AS u ON u.id=s.user_id AND u.role='student'
               WHERE t.user_id=%s AND tu.role='teacher' AND tu.is_active=1
               GROUP BY c.id, c.name, c.is_active, c.academic_year_id, ay.name,
                        ay.start_date, ay.end_date, ay.is_active
               ORDER BY ay.start_date DESC, c.name, c.id""",
            (teacher_user_id,),
        )
        return list(cursor.fetchall())


def select_teacher_class(teacher_user_id: int, class_value: str | None,
                         at: datetime | None = None) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    class_id = None
    if class_value not in (None, ""):
        if (not isinstance(class_value, str) or len(class_value) > 20
                or not class_value.isascii() or not class_value.isdecimal()):
            raise AttendanceReadError("Kelas tidak valid.")
        class_id = int(class_value)
        if class_id < 1:
            raise AttendanceReadError("Kelas tidak valid.")
    classes = list_teacher_classes(teacher_user_id)
    if not classes:
        if class_id is not None:
            raise AttendanceReadError("Kelas tidak ditemukan.", 404)
        return classes, None
    if class_id is None:
        moment = application_now() if at is None else at
        selected = next((item for item in classes
                         if bool(item["class_active"]) and bool(item["academic_year_active"])
                         and item["academic_year_start"] <= moment.date() <= item["academic_year_end"]),
                        classes[0])
        return classes, selected
    selected = next((item for item in classes if int(item["class_id"]) == class_id), None)
    if selected is None:
        raise AttendanceReadError("Kelas tidak ditemukan.", 404)
    return classes, selected


def get_teacher_dashboard(teacher_user_id: int, class_value: str | None,
                          at: datetime | None = None) -> dict[str, Any]:
    moment = application_now() if at is None else at
    classes, selected = select_teacher_class(teacher_user_id, class_value, moment)
    result: dict[str, Any] = {
        "classes": classes, "selected_class": selected, "today": moment.date().isoformat(),
        "server_time": moment.strftime("%H:%M"), "summary": {"total": 0, "present": 0,
        "late": 0, "permit": 0, "sick": 0, "absent": 0, "pending": 0},
        "review_students": [], "review_count": 0,
    }
    if selected is None:
        return result

    active_today = (bool(selected["class_active"]) and bool(selected["academic_year_active"])
                    and selected["academic_year_start"] <= moment.date() <= selected["academic_year_end"])
    result["class_is_current"] = active_today
    if not active_today:
        return result

    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT s.id AS student_id, s.full_name, s.nisn, u.is_active
               FROM student_class_enrollments AS sce
               JOIN students AS s ON s.id=sce.student_id
               JOIN users AS u ON u.id=s.user_id
               WHERE sce.class_id=%s AND u.role='student' AND u.is_active=1
               ORDER BY s.full_name, s.id""",
            (selected["class_id"],),
        )
        roster = list(cursor.fetchall())
        cursor.execute(
            """SELECT student_id, status, checkin_at, checkout_at
               FROM attendance_records
               WHERE class_id=%s AND attendance_date=%s""",
            (selected["class_id"], moment.date()),
        )
        records = {int(row["student_id"]): row for row in cursor.fetchall()}

    summary = result["summary"]
    summary["total"] = len(roster)
    reviews: list[dict[str, Any]] = []
    schedule = resolve_schedule(moment.date(), int(selected["academic_year_id"]), int(selected["class_id"]))
    if not schedule or schedule.get("is_holiday"):
        cutoff = None
        checkout_start = None
    else:
        cutoff = _clock(schedule.get("checkin_cutoff"))
        checkout_start = _clock(schedule.get("checkout_start"))
    now_time = moment.timetz().replace(tzinfo=None)
    for student in roster:
        record = records.get(int(student["student_id"]))
        status = record["status"] if record else None
        if status in summary:
            summary[status] += 1
        else:
            summary["pending"] += 1
        reason = None
        if status == "absent":
            reason = "Alpa tercatat"
        elif status is None and cutoff is not None and now_time > cutoff:
            reason = "Belum masuk setelah batas check-in"
        elif (record and record["checkin_at"] is not None and record["checkout_at"] is None
              and checkout_start is not None and now_time >= checkout_start):
            reason = "Belum melakukan presensi pulang"
        if reason:
            reviews.append({"student_id": int(student["student_id"]),
                            "full_name": student["full_name"], "nisn": student["nisn"],
                            "reason": reason})
    result["review_count"] = len(reviews)
    result["review_students"] = reviews
    return result


def _clock(value: str | time | None) -> time | None:
    if value is None:
        return None
    return value if isinstance(value, time) else time.fromisoformat(str(value))


def get_teacher_attendance(teacher_user_id: int, class_value: str | None,
                           month_value: str | None, status_value: str | None,
                           query: str | None, page_value: str | None) -> dict[str, Any]:
    start, end, month = parse_month(month_value)
    status = status_value or ""
    if status and status not in STORED_STATUSES:
        raise AttendanceReadError("Filter status tidak valid.")
    q = _validate_search(query)
    page = parse_page(page_value)
    classes, selected = select_teacher_class(teacher_user_id, class_value)
    if selected is None:
        return {"classes": classes, "selected_class": None, "rows": [],
                "page": 1, "pages": 0, "total": 0, "month": month,
                "status": status, "q": q}
    where = ["ar.class_id=%s", "ar.attendance_date>=%s", "ar.attendance_date<%s"]
    params: list[Any] = [selected["class_id"], start, end]
    if status:
        where.append("ar.status=%s")
        params.append(status)
    if q:
        where.append("(s.full_name LIKE %s ESCAPE '\\\\' OR s.nisn LIKE %s ESCAPE '\\\\')")
        like = f"%{escape_like_pattern(q)}%"
        params.extend((like, like))
    where_sql = " AND ".join(where)
    with get_db().cursor() as cursor:
        cursor.execute(
            f"""SELECT COUNT(*) AS total
                FROM attendance_records AS ar
                JOIN students AS s ON s.id=ar.student_id
                WHERE {where_sql}""",
            tuple(params),
        )
        total = int(cursor.fetchone()["total"])
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        page = min(page, max(pages, 1))
        cursor.execute(
            f"""SELECT ar.attendance_date, ar.status, ar.status_source, ar.notes,
                       ar.checkin_at, ar.checkout_at, s.id AS student_id,
                       s.full_name, s.nisn
                FROM attendance_records AS ar
                JOIN students AS s ON s.id=ar.student_id
                WHERE {where_sql}
                ORDER BY ar.attendance_date DESC, s.full_name, s.id
                LIMIT %s OFFSET %s""",
            (*params, PAGE_SIZE, (page - 1) * PAGE_SIZE),
        )
        rows = list(cursor.fetchall())
    for row in rows:
        row["date"] = row.pop("attendance_date").isoformat()
        row["status_label"] = _status_label(row["status"])
        row["source_label"] = SOURCE_LABELS.get(row["status_source"])
        row["checkin_time"] = _db_time(row.pop("checkin_at"))
        row["checkout_time"] = _db_time(row.pop("checkout_at"))
    return {"classes": classes, "selected_class": selected, "rows": rows,
            "page": page, "pages": pages, "total": total, "month": month,
            "status": status, "q": q}


def _validate_search(query: str | None) -> str:
    value = query or ""
    if (not isinstance(value, str) or len(value) > 100
            or any(ord(char) < 32 for char in value)):
        raise AttendanceReadError("Pencarian tidak valid.")
    return value.strip()


def escape_like_pattern(value: str) -> str:
    """Escape LIKE wildcards so a search term only matches itself literally.

    Every LIKE site must pair the escaped term with ESCAPE '\\' so a typed
    "%" or "_" never turns into "match everything".
    """

    return (value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_"))


def get_teacher_students(teacher_user_id: int, class_value: str | None,
                        query: str | None, page_value: str | None) -> dict[str, Any]:
    classes, selected = select_teacher_class(teacher_user_id, class_value)
    q = _validate_search(query)
    page = parse_page(page_value)
    if selected is None:
        return {"classes": classes, "selected_class": None, "rows": [],
                "page": 1, "pages": 0, "total": 0, "q": q}
    where = ["sce.class_id=%s", "u.role='student'"]
    params: list[Any] = [selected["class_id"]]
    if q:
        where.append("(s.full_name LIKE %s ESCAPE '\\\\' OR s.nisn LIKE %s ESCAPE '\\\\')")
        like = f"%{escape_like_pattern(q)}%"
        params.extend((like, like))
    where_sql = " AND ".join(where)
    with get_db().cursor() as cursor:
        cursor.execute(
            f"""SELECT COUNT(*) AS total FROM student_class_enrollments AS sce
                JOIN students AS s ON s.id=sce.student_id
                JOIN users AS u ON u.id=s.user_id WHERE {where_sql}""",
            tuple(params),
        )
        total = int(cursor.fetchone()["total"])
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        page = min(page, max(pages, 1))
        cursor.execute(
            f"""SELECT s.id AS student_id, s.full_name, s.nisn, u.is_active
                FROM student_class_enrollments AS sce
                JOIN students AS s ON s.id=sce.student_id
                JOIN users AS u ON u.id=s.user_id
                WHERE {where_sql}
                ORDER BY s.full_name, s.id LIMIT %s OFFSET %s""",
            (*params, PAGE_SIZE, (page - 1) * PAGE_SIZE),
        )
        rows = list(cursor.fetchall())
    return {"classes": classes, "selected_class": selected, "rows": rows,
            "page": page, "pages": pages, "total": total, "q": q}


def get_teacher_student_detail(teacher_user_id: int, class_value: str | None,
                               student_id: int, month_value: str | None,
                               selected_value: str | None = None) -> dict[str, Any]:
    start, end, month = parse_month(month_value or application_now().strftime("%Y-%m"))
    moment = application_now()
    selected_date = _parse_date(selected_value)
    if selected_date and (selected_date < start or selected_date >= end):
        raise AttendanceReadError("Tanggal harus berada pada bulan yang dibuka.")
    classes, selected = select_teacher_class(teacher_user_id, class_value)
    if selected is None:
        raise AttendanceReadError("Siswa tidak ditemukan.", 404)
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT s.id AS student_id, s.full_name, s.nisn, u.is_active,
                      EXISTS(SELECT 1 FROM student_class_enrollments AS sce
                             WHERE sce.student_id=s.id AND sce.class_id=%s) AS enrolled_here,
                      EXISTS(SELECT 1 FROM attendance_records AS ar
                             WHERE ar.student_id=s.id AND ar.class_id=%s) AS has_history_here
               FROM students AS s JOIN users AS u ON u.id=s.user_id
               WHERE s.id=%s AND u.role='student' LIMIT 1""",
            (selected["class_id"], selected["class_id"], student_id),
        )
        student = cursor.fetchone()
        if (student is None or not (student["enrolled_here"] or student["has_history_here"])):
            raise AttendanceReadError("Siswa tidak ditemukan.", 404)
        cursor.execute(
            """SELECT id AS record_id, attendance_date, status, status_source, notes,
                      checkin_at, checkout_at
               FROM attendance_records
               WHERE student_id=%s AND class_id=%s AND attendance_date>=%s AND attendance_date<%s
               ORDER BY attendance_date""",
            (student_id, selected["class_id"], start, end),
        )
        records = list(cursor.fetchall())
    record_by_date: dict[date, dict[str, Any]] = {}
    for row in records:
        row["date"] = row.pop("attendance_date").isoformat()
        row["status_label"] = _status_label(row["status"])
        row["source_label"] = SOURCE_LABELS.get(row["status_source"])
        checkin_at = row.pop("checkin_at")
        checkout_at = row.pop("checkout_at")
        row["has_checkin"] = checkin_at is not None
        row["has_checkout"] = checkout_at is not None
        row["checkin_time"] = _db_time(checkin_at)
        row["checkout_time"] = _db_time(checkout_at)
        record_by_date[date.fromisoformat(row["date"])] = row
    month_names = ("Januari", "Februari", "Maret", "April", "Mei", "Juni",
                   "Juli", "Agustus", "September", "Oktober", "November", "Desember")
    if selected_date is None:
        if moment.year == start.year and moment.month == start.month:
            selected_date = moment.date()
    weeks = []
    for week in _calendar_weeks(start.year, start.month):
        enriched_week = []
        for cell in week:
            if cell is None:
                enriched_week.append(None)
                continue
            day = date.fromisoformat(cell["date"])
            record = record_by_date.get(day)
            enriched_week.append({
                **cell,
                "status": record["status_label"] if record else "Tidak ada record",
                "status_key": (record["status"] or "pending") if record else "no_record",
                "is_selected": selected_date == day,
            })
        weeks.append(enriched_week)
    detail = record_by_date.get(selected_date) if selected_date else None
    if selected_date and detail is None:
        detail = {"date": selected_date.isoformat(), "status_label": "Tidak ada record",
                  "status": None, "source_label": None, "checkin_time": None,
                  "checkout_time": None, "notes": None, "has_checkin": False,
                  "has_checkout": False}
    manual_status = {"available": False, "can_set": False, "can_clear": False,
                     "can_mark_absent": False, "reason": "Status manual hanya dapat diatur untuk hari ini."}
    if selected_date == moment.date():
        class_is_current = (
            bool(selected["class_active"]) and bool(selected["academic_year_active"])
            and selected["academic_year_start"] <= moment.date() <= selected["academic_year_end"]
        )
        if not class_is_current:
            manual_status["reason"] = "Status manual hanya tersedia pada kelas aktif tahun ajaran berjalan."
        elif not bool(student["is_active"]) or not bool(student["enrolled_here"]):
            manual_status["reason"] = "Siswa harus aktif dan terdaftar pada kelas ini."
        else:
            schedule = resolve_schedule(moment.date(), int(selected["academic_year_id"]),
                                        int(selected["class_id"]))
            if schedule is None:
                manual_status["reason"] = "Tidak ada jadwal presensi untuk hari ini."
            elif schedule.get("is_holiday"):
                manual_status["reason"] = "Status manual tidak tersedia pada hari libur."
            else:
                now_time = moment.timetz().replace(tzinfo=None)
                cutoff = _clock(schedule.get("checkin_cutoff"))
                current_status = detail.get("status") if detail else None
                current_source = detail.get("status_source") if detail else None
                has_checkin = bool(detail and detail.get("has_checkin"))
                mutable_status = current_status in {None, "permit", "sick", "absent"}
                allowed_source = (current_status is None or current_source in
                                  {"teacher", "finalization_job"})
                manual_status.update({
                    "available": not has_checkin and mutable_status and allowed_source,
                    "can_set": not has_checkin and mutable_status and allowed_source,
                    "can_clear": (not has_checkin and current_status in {"permit", "sick", "absent"}
                                  and current_source == "teacher" and cutoff is not None
                                  and now_time <= cutoff),
                    "can_mark_absent": cutoff is not None and now_time > cutoff,
                    "current_status": current_status,
                    "reason": ("Presensi otomatis Hadir/Terlambat tidak dapat diubah."
                               if has_checkin or current_status in {"present", "late"} else None),
                })
    return {"classes": classes, "selected_class": selected, "student": student,
            "month": month, "month_label": f"{month_names[start.month - 1]} {start.year}",
            "weeks": weeks, "detail": detail,
            "selected_date": selected_date.isoformat() if selected_date else None,
            "today": moment.date().isoformat(),
            "manual_status": manual_status}


def _authorized_evidence_row(cursor, *, user_id: int, role: str,
                             record_id: int) -> dict[str, Any] | None:
    """Fetch one record only if this request's role still has access to it."""
    if role == "admin":
        cursor.execute(
            """SELECT ar.id AS record_id, ar.student_id, ar.class_id, ar.attendance_date,
                      ar.status, ar.status_source,
                      ar.notes, ar.checkin_at, ar.checkout_at,
                      ar.checkin_latitude, ar.checkin_longitude, ar.checkin_accuracy,
                      ar.checkin_photo, ar.checkout_latitude, ar.checkout_longitude,
                      ar.checkout_accuracy, ar.checkout_photo, s.full_name AS student_name,
                      c.name AS class_name
               FROM attendance_records AS ar
               JOIN students AS s ON s.id=ar.student_id
               LEFT JOIN classes AS c ON c.id=ar.class_id
               WHERE ar.id=%s LIMIT 1""", (record_id,)
        )
    elif role == "teacher":
        cursor.execute(
            """SELECT ar.id AS record_id, ar.student_id, ar.class_id, ar.attendance_date,
                      ar.status, ar.status_source,
                      ar.notes, ar.checkin_at, ar.checkout_at,
                      ar.checkin_latitude, ar.checkin_longitude, ar.checkin_accuracy,
                      ar.checkin_photo, ar.checkout_latitude, ar.checkout_longitude,
                      ar.checkout_accuracy, ar.checkout_photo, s.full_name AS student_name,
                      c.name AS class_name
               FROM attendance_records AS ar
               JOIN students AS s ON s.id=ar.student_id
               JOIN classes AS c ON c.id=ar.class_id
               JOIN teachers AS t ON t.id=c.teacher_id
               JOIN users AS tu ON tu.id=t.user_id
               WHERE ar.id=%s AND ar.class_id IS NOT NULL
                 AND t.user_id=%s AND tu.is_active=1
                 AND tu.role='teacher' LIMIT 1""", (record_id, user_id)
        )
    else:
        return None
    return cursor.fetchone()


def get_attendance_evidence(*, user_id: int, role: str,
                            record_id: int) -> dict[str, Any]:
    """Return display-safe evidence metadata for Admin or currently assigned Teacher."""
    with get_db().cursor() as cursor:
        row = _authorized_evidence_row(cursor, user_id=user_id, role=role,
                                       record_id=record_id)
    if row is None:
        raise AttendanceReadError("Bukti presensi tidak ditemukan.", 404)
    status_label = STATUS_LABELS.get(row["status"], "Belum Absen")
    checkin_location = (row["checkin_latitude"] is not None
                        and row["checkin_longitude"] is not None)
    checkout_location = (row["checkout_latitude"] is not None
                         and row["checkout_longitude"] is not None)
    return {
        "record_id": int(row["record_id"]), "student_id": int(row["student_id"]),
        "class_id": int(row["class_id"]) if row["class_id"] is not None else None,
        "student_name": row["student_name"],
        "class_name": row["class_name"], "date": row["attendance_date"].isoformat(),
        "status_label": status_label, "source_label": SOURCE_LABELS.get(row["status_source"]),
        "notes": row["notes"], "checkin_time": _db_time(row["checkin_at"]),
        "checkout_time": _db_time(row["checkout_at"]),
        "checkin_accuracy": str(row["checkin_accuracy"]) if row["checkin_accuracy"] is not None else None,
        "checkout_accuracy": str(row["checkout_accuracy"]) if row["checkout_accuracy"] is not None else None,
        "has_checkin_photo": bool(row["checkin_photo"]),
        "has_checkout_photo": bool(row["checkout_photo"]),
        "checkin_location_available": checkin_location,
        "checkout_location_available": checkout_location,
    }


def get_attendance_evidence_file(*, user_id: int, role: str,
                                 record_id: int, phase: str):
    """Authorize again, then resolve only the selected phase key from this record."""
    if phase not in {"checkin", "checkout"}:
        raise AttendanceReadError("Bukti presensi tidak ditemukan.", 404)
    from app.services.storage_service import StorageError, resolve_private_file
    with get_db().cursor() as cursor:
        row = _authorized_evidence_row(cursor, user_id=user_id, role=role,
                                       record_id=record_id)
    if row is None:
        raise AttendanceReadError("Bukti presensi tidak ditemukan.", 404)
    key = row[f"{phase}_photo"]
    if not isinstance(key, str) or not key.startswith("attendance/"):
        raise AttendanceReadError("Foto bukti presensi tidak tersedia.", 404)
    try:
        return resolve_private_file(key)
    except (StorageError, FileNotFoundError, OSError):
        raise AttendanceReadError("Foto bukti presensi tidak tersedia.", 404) from None
