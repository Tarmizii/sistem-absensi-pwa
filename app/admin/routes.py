"""Admin-only Teacher management routes for T08."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for
from pymysql import MySQLError

from app.services.auth_service import roles_required
from app.services.teacher_service import (
    TeacherValidationError,
    create_teacher,
    deactivate_teacher,
    get_teacher,
    list_teachers,
    reset_teacher_password,
    update_teacher,
)
from app.services.student_service import (
    StudentValidationError,
    create_student,
    deactivate_student,
    get_student,
    list_students,
    reset_student_password,
    update_student,
)
from app.services.class_service import (
    MasterDataValidationError,
    assign_student,
    create_academic_year,
    create_class,
    deactivate_class,
    get_academic_year,
    get_class,
    list_academic_years,
    list_class_students,
    list_classes,
    list_student_options,
    list_teacher_options,
    set_academic_year_active,
    update_class,
)
from app.services.schedule_service import (
    ScheduleValidationError,
    create_schedule,
    get_schedule,
    list_schedules,
    set_schedule_active,
    update_schedule,
)
from app.services.schedule_exception_service import (
    ScheduleExceptionError,
    ScheduleExceptionNotFoundError,
    create_schedule_exception,
    get_schedule_exception,
    list_schedule_exceptions,
    resolve_effective_schedule,
    set_schedule_exception_active,
    update_schedule_exception,
)
from app.services.geofence_service import (
    GeofenceValidationError,
    evaluate_location,
    get_geofence_config,
    save_geofence_config,
)


admin_bp = Blueprint("admin", __name__)


def _teacher_form_values() -> dict[str, str]:
    return {
        "username": request.form.get("username", ""),
        "full_name": request.form.get("full_name", ""),
        "employee_number": request.form.get("employee_number", ""),
    }


def _student_form_values() -> dict[str, str]:
    return {
        "nisn": request.form.get("nisn", ""),
        "full_name": request.form.get("full_name", ""),
    }


@admin_bp.get("/admin/teachers")
@roles_required("admin")
def teacher_list():
    search = request.args.get("q", "")
    try:
        teachers = list_teachers(search)
    except MySQLError:
        flash("Data Guru belum dapat dimuat. Coba lagi.", "error")
        teachers = []
    return render_template("admin/teacher_list.html", teachers=teachers, search=search)


@admin_bp.route("/admin/teachers/new", methods=["GET", "POST"])
@roles_required("admin")
def teacher_create():
    values = _teacher_form_values() if request.method == "POST" else {
        "username": "", "full_name": "", "employee_number": ""
    }
    if request.method == "POST":
        try:
            result = create_teacher(actor_user_id=g.current_user["id"], **values)
        except TeacherValidationError as error:
            flash(str(error), "error")
        except MySQLError:
            flash("Guru belum dapat ditambahkan. Coba lagi.", "error")
        else:
            return render_template("admin/teacher_secret.html", operation="Akun Guru dibuat", **result)
    return render_template("admin/teacher_form.html", mode="create", values=values)


@admin_bp.get("/admin/teachers/<int:teacher_id>")
@roles_required("admin")
def teacher_detail(teacher_id: int):
    teacher = get_teacher(teacher_id)
    if teacher is None:
        abort(404)
    return render_template("admin/teacher_detail.html", teacher=teacher)


@admin_bp.route("/admin/teachers/<int:teacher_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def teacher_edit(teacher_id: int):
    teacher = get_teacher(teacher_id)
    if teacher is None:
        abort(404)
    values = _teacher_form_values() if request.method == "POST" else {
        "username": teacher["username"], "full_name": teacher["full_name"],
        "employee_number": teacher["employee_number"] or "",
    }
    if request.method == "POST":
        try:
            update_teacher(actor_user_id=g.current_user["id"], teacher_id=teacher_id,
                           full_name=values["full_name"], employee_number=values["employee_number"])
        except TeacherValidationError as error:
            flash(str(error), "error")
        except MySQLError:
            flash("Profil Guru belum dapat diperbarui. Coba lagi.", "error")
        else:
            flash("Profil Guru berhasil diperbarui.", "success")
            return redirect(url_for("admin.teacher_detail", teacher_id=teacher_id))
    return render_template("admin/teacher_form.html", mode="edit", values=values, teacher=teacher)


@admin_bp.post("/admin/teachers/<int:teacher_id>/deactivate")
@roles_required("admin")
def teacher_deactivate(teacher_id: int):
    try:
        deactivate_teacher(actor_user_id=g.current_user["id"], teacher_id=teacher_id)
    except TeacherValidationError as error:
        flash(str(error), "error")
    except MySQLError:
        flash("Akun Guru belum dapat dinonaktifkan. Coba lagi.", "error")
    else:
        flash("Akun Guru dinonaktifkan. Histori tetap dipertahankan.", "success")
    return redirect(url_for("admin.teacher_detail", teacher_id=teacher_id))


@admin_bp.post("/admin/teachers/<int:teacher_id>/reset-password")
@roles_required("admin")
def teacher_reset_password(teacher_id: int):
    try:
        result = reset_teacher_password(actor_user_id=g.current_user["id"], teacher_id=teacher_id)
    except TeacherValidationError as error:
        flash(str(error), "error")
        return redirect(url_for("admin.teacher_detail", teacher_id=teacher_id))
    except MySQLError:
        flash("Password Guru belum dapat direset. Coba lagi.", "error")
        return redirect(url_for("admin.teacher_detail", teacher_id=teacher_id))
    return render_template("admin/teacher_secret.html", operation="Password sementara dibuat", **result)


@admin_bp.get("/admin/students")
@roles_required("admin")
def student_list():
    search = request.args.get("q", "")
    try:
        students = list_students(search)
    except MySQLError:
        flash("Data Siswa belum dapat dimuat. Coba lagi.", "error")
        students = []
    return render_template("admin/student_list.html", students=students, search=search)


@admin_bp.route("/admin/students/new", methods=["GET", "POST"])
@roles_required("admin")
def student_create():
    values = _student_form_values() if request.method == "POST" else {"nisn": "", "full_name": ""}
    if request.method == "POST":
        try:
            result = create_student(actor_user_id=g.current_user["id"], **values)
        except StudentValidationError as error:
            flash(str(error), "error")
        except MySQLError:
            flash("Siswa belum dapat ditambahkan. Coba lagi.", "error")
        else:
            return render_template("admin/student_secret.html", operation="Akun Siswa dibuat", **result)
    return render_template("admin/student_form.html", mode="create", values=values)


@admin_bp.get("/admin/students/<int:student_id>")
@roles_required("admin")
def student_detail(student_id: int):
    student = get_student(student_id)
    if student is None:
        abort(404)
    return render_template("admin/student_detail.html", student=student)


@admin_bp.route("/admin/students/<int:student_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def student_edit(student_id: int):
    student = get_student(student_id)
    if student is None:
        abort(404)
    values = _student_form_values() if request.method == "POST" else {
        "nisn": student["nisn"], "full_name": student["full_name"],
    }
    if request.method == "POST":
        try:
            update_student(actor_user_id=g.current_user["id"], student_id=student_id, **values)
        except StudentValidationError as error:
            flash(str(error), "error")
        except MySQLError:
            flash("Profil Siswa belum dapat diperbarui. Coba lagi.", "error")
        else:
            flash("Profil Siswa berhasil diperbarui.", "success")
            return redirect(url_for("admin.student_detail", student_id=student_id))
    return render_template("admin/student_form.html", mode="edit", values=values, student=student)


@admin_bp.post("/admin/students/<int:student_id>/deactivate")
@roles_required("admin")
def student_deactivate(student_id: int):
    try:
        deactivate_student(actor_user_id=g.current_user["id"], student_id=student_id)
    except StudentValidationError as error:
        flash(str(error), "error")
    except MySQLError:
        flash("Akun Siswa belum dapat dinonaktifkan. Coba lagi.", "error")
    else:
        flash("Akun Siswa dinonaktifkan. Histori tetap dipertahankan.", "success")
    return redirect(url_for("admin.student_detail", student_id=student_id))


@admin_bp.post("/admin/students/<int:student_id>/reset-password")
@roles_required("admin")
def student_reset_password(student_id: int):
    try:
        result = reset_student_password(actor_user_id=g.current_user["id"], student_id=student_id)
    except StudentValidationError as error:
        flash(str(error), "error")
        return redirect(url_for("admin.student_detail", student_id=student_id))
    except MySQLError:
        flash("Password Siswa belum dapat direset. Coba lagi.", "error")
        return redirect(url_for("admin.student_detail", student_id=student_id))
    return render_template("admin/student_secret.html", operation="Password sementara dibuat", **result)


def _academic_year_form_values() -> dict[str, str]:
    return {"name": request.form.get("name", ""),
            "start_date": request.form.get("start_date", ""),
            "end_date": request.form.get("end_date", ""),
            "is_active": request.form.get("is_active", "")}


def _class_form_values() -> dict[str, str]:
    return {"name": request.form.get("name", ""),
            "academic_year_id": request.form.get("academic_year_id", ""),
            "teacher_id": request.form.get("teacher_id", "")}


@admin_bp.route("/admin/academic-years", methods=["GET", "POST"])
@roles_required("admin")
def academic_year_list():
    values = _academic_year_form_values() if request.method == "POST" else {
        "name": "", "start_date": "", "end_date": "", "is_active": "",
    }
    if request.method == "POST":
        try:
            create_academic_year(actor_user_id=g.current_user["id"], **{
                "name": values["name"], "start_date": values["start_date"],
                "end_date": values["end_date"], "is_active": values["is_active"] == "on",
            })
        except MasterDataValidationError as error:
            flash(str(error), "error")
        except MySQLError:
            flash("Tahun ajaran belum dapat disimpan. Coba lagi.", "error")
        else:
            flash("Tahun ajaran berhasil ditambahkan.", "success")
            return redirect(url_for("admin.academic_year_list"))
    try:
        years = list_academic_years()
    except MySQLError:
        flash("Data tahun ajaran belum dapat dimuat. Coba lagi.", "error")
        years = []
    return render_template("admin/academic_year_list.html", years=years, values=values)


@admin_bp.post("/admin/academic-years/<int:academic_year_id>/toggle")
@roles_required("admin")
def academic_year_toggle(academic_year_id: int):
    year = get_academic_year(academic_year_id)
    if year is None:
        abort(404)
    try:
        set_academic_year_active(actor_user_id=g.current_user["id"], academic_year_id=academic_year_id,
                                 is_active=not bool(year["is_active"]))
    except MasterDataValidationError as error:
        flash(str(error), "error")
    except MySQLError:
        flash("Status tahun ajaran belum dapat diperbarui. Coba lagi.", "error")
    else:
        flash("Status tahun ajaran diperbarui.", "success")
    return redirect(url_for("admin.academic_year_list"))


@admin_bp.route("/admin/classes", methods=["GET", "POST"])
@roles_required("admin")
def class_list():
    values = _class_form_values() if request.method == "POST" else {
        "name": "", "academic_year_id": "", "teacher_id": "",
    }
    if request.method == "POST":
        try:
            create_class(actor_user_id=g.current_user["id"], name=values["name"],
                         academic_year_id=int(values["academic_year_id"]),
                         teacher_id=int(values["teacher_id"]) if values["teacher_id"] else None)
        except MasterDataValidationError as error:
            flash(str(error), "error")
        except (ValueError, TypeError):
            flash("Tahun ajaran atau Guru belum dipilih dengan benar.", "error")
        except MySQLError:
            flash("Kelas belum dapat disimpan. Coba lagi.", "error")
        else:
            flash("Kelas berhasil ditambahkan.", "success")
            return redirect(url_for("admin.class_list"))
    try:
        years = list_academic_years()
        teachers = list_teacher_options()
        classes = list_classes()
    except MySQLError:
        flash("Data kelas belum dapat dimuat. Coba lagi.", "error")
        years, teachers, classes = [], [], []
    return render_template("admin/class_list.html", years=years, teachers=teachers,
                           classes=classes, values=values)


@admin_bp.route("/admin/classes/<int:class_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def class_edit(class_id: int):
    current_class = get_class(class_id)
    if current_class is None:
        abort(404)
    values = _class_form_values() if request.method == "POST" else {
        "name": current_class["name"], "academic_year_id": str(current_class["academic_year_id"]),
        "teacher_id": str(current_class["teacher_id"] or ""),
    }
    if request.method == "POST":
        try:
            update_class(actor_user_id=g.current_user["id"], class_id=class_id,
                         name=values["name"], teacher_id=int(values["teacher_id"]) if values["teacher_id"] else None)
        except MasterDataValidationError as error:
            flash(str(error), "error")
        except (ValueError, TypeError):
            flash("Guru belum dipilih dengan benar.", "error")
        except MySQLError:
            flash("Kelas belum dapat diperbarui. Coba lagi.", "error")
        else:
            flash("Kelas berhasil diperbarui.", "success")
            return redirect(url_for("admin.class_detail", class_id=class_id))
    return render_template("admin/class_form.html", current_class=current_class,
                           teachers=list_teacher_options(), values=values)


@admin_bp.post("/admin/classes/<int:class_id>/deactivate")
@roles_required("admin")
def class_deactivate(class_id: int):
    try:
        deactivate_class(actor_user_id=g.current_user["id"], class_id=class_id)
    except MasterDataValidationError as error:
        flash(str(error), "error")
    except MySQLError:
        flash("Kelas belum dapat dinonaktifkan. Coba lagi.", "error")
    else:
        flash("Kelas dinonaktifkan; data penempatan tetap dipertahankan.", "success")
    return redirect(url_for("admin.class_list"))


@admin_bp.get("/admin/classes/<int:class_id>")
@roles_required("admin")
def class_detail(class_id: int):
    current_class = get_class(class_id)
    if current_class is None:
        abort(404)
    try:
        students = list_class_students(class_id)
        options = list_student_options(current_class["academic_year_id"])
    except MySQLError:
        flash("Daftar penempatan belum dapat dimuat. Coba lagi.", "error")
        students, options = [], []
    return render_template("admin/class_detail.html", current_class=current_class,
                           students=students, student_options=options)


@admin_bp.post("/admin/classes/<int:class_id>/students/add")
@roles_required("admin")
def class_student_add(class_id: int):
    try:
        student_id = int(request.form.get("student_id", ""))
        assign_student(actor_user_id=g.current_user["id"], class_id=class_id, student_id=student_id)
    except MasterDataValidationError as error:
        flash(str(error), "error")
    except (ValueError, TypeError):
        flash("Siswa belum dipilih dengan benar.", "error")
    except MySQLError:
        flash("Penempatan Siswa belum dapat disimpan. Coba lagi.", "error")
    else:
        flash("Siswa berhasil ditempatkan ke kelas.", "success")
    return redirect(url_for("admin.class_detail", class_id=class_id))


def _schedule_form_values() -> dict[str, str]:
    return {
        "academic_year_id": request.form.get("academic_year_id", ""),
        "day_of_week": request.form.get("day_of_week", ""),
        "checkin_start": request.form.get("checkin_start", ""),
        "late_after": request.form.get("late_after", ""),
        "checkin_cutoff": request.form.get("checkin_cutoff", ""),
        "checkout_start": request.form.get("checkout_start", ""),
        "is_active": request.form.get("is_active", "on"),
    }


@admin_bp.route("/admin/schedules", methods=["GET", "POST"])
@roles_required("admin")
def schedule_list():
    values = _schedule_form_values() if request.method == "POST" else {
        "academic_year_id": "", "day_of_week": "", "checkin_start": "07:00",
        "late_after": "07:15", "checkin_cutoff": "08:00", "checkout_start": "15:00",
        "is_active": "on",
    }
    if request.method == "POST":
        try:
            create_schedule(actor_user_id=g.current_user["id"],
                            academic_year_id=int(values["academic_year_id"]),
                            day_of_week=int(values["day_of_week"]),
                            checkin_start=values["checkin_start"], late_after=values["late_after"],
                            checkin_cutoff=values["checkin_cutoff"], checkout_start=values["checkout_start"],
                            is_active=values["is_active"] == "on")
        except ScheduleValidationError as error:
            flash(str(error), "error")
        except (ValueError, TypeError):
            flash("Tahun ajaran dan hari belum dipilih dengan benar.", "error")
        except MySQLError:
            flash("Jadwal belum dapat disimpan. Coba lagi.", "error")
        else:
            flash("Jadwal berhasil ditambahkan.", "success")
            return redirect(url_for("admin.schedule_list"))
    try:
        from app.services.class_service import list_academic_years
        years = list_academic_years()
        schedules = list_schedules()
    except MySQLError:
        flash("Data jadwal belum dapat dimuat. Coba lagi.", "error")
        years, schedules = [], []
    return render_template("admin/schedule_list.html", years=years, schedules=schedules,
                           values=values, day_names={1: "Senin", 2: "Selasa", 3: "Rabu", 4: "Kamis",
                                                     5: "Jumat", 6: "Sabtu", 7: "Minggu"})


@admin_bp.route("/admin/schedules/<int:schedule_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def schedule_edit(schedule_id: int):
    schedule = get_schedule(schedule_id)
    if schedule is None:
        abort(404)
    values = _schedule_form_values() if request.method == "POST" else {
        "academic_year_id": str(schedule["academic_year_id"]),
        "day_of_week": str(schedule["day_of_week"]),
        "checkin_start": str(schedule["checkin_start"]), "late_after": str(schedule["late_after"]),
        "checkin_cutoff": str(schedule["checkin_cutoff"]), "checkout_start": str(schedule["checkout_start"]),
        "is_active": "on" if schedule["is_active"] else "",
    }
    if request.method == "POST":
        try:
            update_schedule(actor_user_id=g.current_user["id"], schedule_id=schedule_id,
                            day_of_week=int(values["day_of_week"]), checkin_start=values["checkin_start"],
                            late_after=values["late_after"], checkin_cutoff=values["checkin_cutoff"],
                            checkout_start=values["checkout_start"])
        except ScheduleValidationError as error:
            flash(str(error), "error")
        except (ValueError, TypeError):
            flash("Hari belum dipilih dengan benar.", "error")
        except MySQLError:
            flash("Jadwal belum dapat diperbarui. Coba lagi.", "error")
        else:
            flash("Jadwal berhasil diperbarui.", "success")
            return redirect(url_for("admin.schedule_list"))
    return render_template("admin/schedule_form.html", schedule=schedule, values=values,
                           day_names={1: "Senin", 2: "Selasa", 3: "Rabu", 4: "Kamis",
                                      5: "Jumat", 6: "Sabtu", 7: "Minggu"})


@admin_bp.post("/admin/schedules/<int:schedule_id>/toggle")
@roles_required("admin")
def schedule_toggle(schedule_id: int):
    schedule = get_schedule(schedule_id)
    if schedule is None:
        abort(404)
    try:
        set_schedule_active(actor_user_id=g.current_user["id"], schedule_id=schedule_id,
                            is_active=not bool(schedule["is_active"]))
    except ScheduleValidationError as error:
        flash(str(error), "error")
    except MySQLError:
        flash("Status jadwal belum dapat diperbarui. Coba lagi.", "error")
    else:
        flash("Status jadwal diperbarui.", "success")
    return redirect(url_for("admin.schedule_list"))


def _exception_form_values(source=None) -> dict[str, str]:
    source = source or request.form
    return {key: str(source.get(key, "")) for key in (
        "academic_year_id", "exception_date", "scope", "class_id", "exception_type",
        "checkin_start", "late_after", "checkin_cutoff", "checkout_start")}


def _exception_template_context(values, *, exception=None, preview_values=None,
                                preview=None, preview_error=None):
    years = list_academic_years()
    preview_values = preview_values or {}
    default_year = next((year for year in years if year["is_active"]), years[0] if years else None)
    year_id = (values.get("academic_year_id") or preview_values.get("academic_year_id")
               or (str(default_year["id"]) if default_year else ""))
    classes = list_classes(int(year_id)) if year_id.isdigit() else []
    return {
        "years": years, "classes": classes, "exceptions": list_schedule_exceptions(),
        "values": values, "exception": exception, "preview_values": preview_values,
        "preview": preview, "preview_error": preview_error,
        "exception_types": [("holiday", "Libur"), ("exam", "Ujian"),
                             ("school_activity", "Kegiatan sekolah"),
                             ("early_dismissal", "Pulang awal"), ("custom", "Lainnya")],
    }


@admin_bp.route("/admin/schedule-exceptions", methods=["GET", "POST"])
@roles_required("admin")
def schedule_exception_list():
    values = _exception_form_values() if request.method == "POST" else {
        "academic_year_id": "", "exception_date": "", "scope": "school", "class_id": "",
        "exception_type": "holiday", "checkin_start": "", "late_after": "",
        "checkin_cutoff": "", "checkout_start": "",
    }
    if request.method == "POST":
        try:
            create_schedule_exception(
                actor_user_id=g.current_user["id"], academic_year_id=int(values["academic_year_id"]),
                exception_date=values["exception_date"], scope=values["scope"],
                class_id=int(values["class_id"]) if values["class_id"] else None,
                exception_type=values["exception_type"], checkin_start=values["checkin_start"],
                late_after=values["late_after"], checkin_cutoff=values["checkin_cutoff"],
                checkout_start=values["checkout_start"],
            )
        except ScheduleExceptionError as error:
            flash(str(error), "error")
        except (ValueError, TypeError):
            flash("Tahun ajaran atau kelas belum dipilih dengan benar.", "error")
        except MySQLError:
            flash("Exception belum dapat disimpan. Coba lagi.", "error")
        else:
            flash("Exception jadwal berhasil ditambahkan.", "success")
            return redirect(url_for("admin.schedule_exception_list"))
    try:
        context = _exception_template_context(values)
    except MySQLError:
        flash("Data exception belum dapat dimuat. Coba lagi.", "error")
        context = {"years": [], "classes": [], "exceptions": [], "values": values,
                   "exception": None, "preview_values": {}, "preview": None,
                   "preview_error": None, "exception_types": []}
    return render_template("admin/schedule_exception_list.html", **context)


@admin_bp.route("/admin/schedule-exceptions/<int:exception_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def schedule_exception_edit(exception_id: int):
    exception = get_schedule_exception(exception_id)
    if exception is None:
        abort(404)
    defaults = {key: str(exception[key] or "") for key in (
        "academic_year_id", "exception_date", "scope", "class_id", "exception_type",
        "checkin_start", "late_after", "checkin_cutoff", "checkout_start")}
    values = _exception_form_values() if request.method == "POST" else defaults
    if request.method == "POST":
        try:
            update_schedule_exception(
                actor_user_id=g.current_user["id"], exception_id=exception_id,
                academic_year_id=int(values["academic_year_id"]), exception_date=values["exception_date"],
                scope=values["scope"], class_id=int(values["class_id"]) if values["class_id"] else None,
                exception_type=values["exception_type"], checkin_start=values["checkin_start"],
                late_after=values["late_after"], checkin_cutoff=values["checkin_cutoff"],
                checkout_start=values["checkout_start"],
            )
        except ScheduleExceptionError as error:
            flash(str(error), "error")
        except (ValueError, TypeError):
            flash("Tahun ajaran atau kelas belum dipilih dengan benar.", "error")
        except MySQLError:
            flash("Exception belum dapat diperbarui. Coba lagi.", "error")
        else:
            flash("Exception jadwal berhasil diperbarui.", "success")
            return redirect(url_for("admin.schedule_exception_list"))
    try:
        context = _exception_template_context(values, exception=exception)
    except MySQLError:
        flash("Data exception belum dapat dimuat. Coba lagi.", "error")
        context = {"years": [], "classes": [], "exceptions": [], "values": values,
                   "exception": exception, "preview_values": {}, "preview": None,
                   "preview_error": None, "exception_types": []}
    return render_template("admin/schedule_exception_list.html", **context)


@admin_bp.post("/admin/schedule-exceptions/<int:exception_id>/toggle")
@roles_required("admin")
def schedule_exception_toggle(exception_id: int):
    exception = get_schedule_exception(exception_id)
    if exception is None:
        abort(404)
    try:
        set_schedule_exception_active(actor_user_id=g.current_user["id"],
                                      exception_id=exception_id,
                                      is_active=not bool(exception["is_active"]))
    except ScheduleExceptionError as error:
        flash(str(error), "error")
    except MySQLError:
        flash("Status exception belum dapat diperbarui. Coba lagi.", "error")
    else:
        flash("Status exception diperbarui.", "success")
    return redirect(url_for("admin.schedule_exception_list"))


@admin_bp.get("/admin/schedule-exceptions/preview")
@roles_required("admin")
def schedule_exception_preview():
    preview_values = {key: request.args.get(key, "") for key in
                      ("academic_year_id", "exception_date", "class_id")}
    values = {"academic_year_id": "", "exception_date": "", "scope": "school", "class_id": "",
              "exception_type": "holiday", "checkin_start": "", "late_after": "",
              "checkin_cutoff": "", "checkout_start": ""}
    try:
        preview = None
        if preview_values["exception_date"]:
            day = date.fromisoformat(preview_values["exception_date"])
            year_id = int(preview_values["academic_year_id"]) if preview_values["academic_year_id"] else None
            class_id = int(preview_values["class_id"]) if preview_values["class_id"] else None
            preview = resolve_effective_schedule(day, year_id, class_id)
        context = _exception_template_context(values, preview_values=preview_values, preview=preview)
    except (ScheduleExceptionError, ValueError, TypeError) as error:
        context = _exception_template_context(values, preview_values=preview_values,
                                              preview_error=str(error))
    except MySQLError:
        context = _exception_template_context(values, preview_values=preview_values,
                                              preview_error="Preview jadwal belum dapat dimuat. Coba lagi.")
    return render_template("admin/schedule_exception_list.html", **context)


@admin_bp.route("/admin/geofence", methods=["GET", "POST"])
@roles_required("admin")
def geofence_settings():
    values = {
        "name": request.form.get("name", "Sekolah"),
        "latitude": request.form.get("latitude", ""),
        "longitude": request.form.get("longitude", ""),
        "radius_meters": request.form.get("radius_meters", "75"),
        "max_accuracy_meters": request.form.get("max_accuracy_meters", ""),
        "is_active": request.form.get("is_active", ""),
    }
    if request.method == "POST":
        try:
            save_geofence_config(
                actor_user_id=g.current_user["id"], name=values["name"],
                latitude=values["latitude"], longitude=values["longitude"],
                radius_meters=values["radius_meters"],
                max_accuracy_meters=values["max_accuracy_meters"],
                is_active=values["is_active"] == "on",
            )
        except GeofenceValidationError as error:
            flash(str(error), "error")
        except MySQLError:
            flash("Pengaturan geofence belum dapat disimpan. Coba lagi.", "error")
        else:
            flash("Pengaturan geofence berhasil disimpan.", "success")
            return redirect(url_for("admin.geofence_settings"))
    try:
        config = get_geofence_config()
    except MySQLError:
        flash("Pengaturan geofence belum dapat dimuat. Terapkan migration 008.", "error")
        config = {"name": "Sekolah", "latitude": None, "longitude": None,
                  "radius_meters": 75, "max_accuracy_meters": None,
                  "is_active": False, "updated_at": None}
    if request.method == "GET":
        values = {key: str(config.get(key) if config.get(key) is not None else "")
                  for key in ("name", "latitude", "longitude", "radius_meters", "max_accuracy_meters")}
        values["is_active"] = "on" if config["is_active"] else ""
    return render_template("admin/geofence_settings.html", values=values, config=config)


@admin_bp.post("/admin/geofence/check")
@roles_required("admin")
def geofence_check_location():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(allowed=False, reason="invalid_request"), 400
    try:
        result = evaluate_location(
            latitude=payload.get("latitude"), longitude=payload.get("longitude"),
            accuracy_meters=payload.get("accuracy"),
        )
    except MySQLError:
        return jsonify(allowed=False, reason="unavailable"), 503
    return jsonify(result)
