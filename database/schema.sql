-- Bootstrap schema for SMA Negeri 4 Lhokseumawe.
-- Import through Laragon/HeidiSQL. It intentionally creates no account;
-- use scripts/create_admin.py so no password is stored in SQL or Git.

CREATE DATABASE IF NOT EXISTS sistem_absensi
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE sistem_absensi;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    username VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'teacher', 'student') NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_username (username),
    KEY idx_users_role_active (role, is_active)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    actor_user_id BIGINT UNSIGNED NULL,
    action VARCHAR(64) NOT NULL,
    target_type VARCHAR(32) NOT NULL,
    target_id BIGINT UNSIGNED NOT NULL,
    metadata JSON NOT NULL,
    created_at DATETIME(6) NOT NULL COMMENT 'UTC; supplied by application',
    PRIMARY KEY (id),
    KEY idx_audit_created (created_at, id),
    KEY idx_audit_target (target_type, target_id),
    CONSTRAINT fk_audit_actor FOREIGN KEY (actor_user_id)
        REFERENCES users (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS teachers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    employee_number VARCHAR(50) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_teachers_user (user_id),
    UNIQUE KEY uq_teachers_employee_number (employee_number),
    KEY idx_teachers_full_name (full_name),
    CONSTRAINT fk_teachers_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS students (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    nisn VARCHAR(20) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    face_registered BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_students_user (user_id),
    UNIQUE KEY uq_students_nisn (nisn),
    KEY idx_students_full_name (full_name),
    CONSTRAINT fk_students_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS student_faces (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    student_id BIGINT UNSIGNED NOT NULL,
    pose ENUM('front', 'left', 'right') NOT NULL,
    storage_key VARCHAR(255) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_student_faces_pose (student_id, pose),
    UNIQUE KEY uq_student_faces_storage_key (storage_key),
    CONSTRAINT fk_student_faces_student FOREIGN KEY (student_id)
        REFERENCES students (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS academic_years (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(30) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_academic_years_name (name),
    KEY idx_academic_years_active (is_active, start_date),
    CONSTRAINT chk_academic_year_dates CHECK (end_date >= start_date)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS classes (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    academic_year_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(80) NOT NULL,
    teacher_id BIGINT UNSIGNED NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_classes_year_name (academic_year_id, name),
    KEY idx_classes_teacher_active (teacher_id, is_active),
    CONSTRAINT fk_classes_year FOREIGN KEY (academic_year_id)
        REFERENCES academic_years (id) ON DELETE RESTRICT,
    CONSTRAINT fk_classes_teacher FOREIGN KEY (teacher_id)
        REFERENCES teachers (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS student_class_enrollments (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    student_id BIGINT UNSIGNED NOT NULL,
    academic_year_id BIGINT UNSIGNED NOT NULL,
    class_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_enrollments_student_year (student_id, academic_year_id),
    KEY idx_enrollments_class (class_id, student_id),
    CONSTRAINT fk_enrollments_student FOREIGN KEY (student_id)
        REFERENCES students (id) ON DELETE RESTRICT,
    CONSTRAINT fk_enrollments_year FOREIGN KEY (academic_year_id)
        REFERENCES academic_years (id) ON DELETE RESTRICT,
    CONSTRAINT fk_enrollments_class FOREIGN KEY (class_id)
        REFERENCES classes (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS attendance_schedules (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    academic_year_id BIGINT UNSIGNED NOT NULL,
    day_of_week TINYINT UNSIGNED NOT NULL,
    checkin_start TIME NOT NULL,
    late_after TIME NOT NULL,
    checkin_cutoff TIME NOT NULL,
    checkout_start TIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_schedules_year_day (academic_year_id, day_of_week),
    KEY idx_schedules_lookup (academic_year_id, day_of_week, is_active),
    CONSTRAINT fk_schedules_year FOREIGN KEY (academic_year_id)
        REFERENCES academic_years (id) ON DELETE RESTRICT,
    CONSTRAINT chk_schedules_day CHECK (day_of_week BETWEEN 1 AND 7),
    CONSTRAINT chk_schedules_order CHECK (
        checkin_start <= late_after AND late_after <= checkin_cutoff
        AND checkin_cutoff <= checkout_start
    )
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS schedule_exceptions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    academic_year_id BIGINT UNSIGNED NOT NULL,
    exception_date DATE NOT NULL,
    scope ENUM('school', 'class') NOT NULL,
    class_id BIGINT UNSIGNED NULL,
    class_scope_key BIGINT UNSIGNED AS (IFNULL(class_id, 0)) STORED,
    exception_type ENUM('holiday', 'exam', 'school_activity', 'early_dismissal', 'custom') NOT NULL,
    checkin_start TIME NULL,
    late_after TIME NULL,
    checkin_cutoff TIME NULL,
    checkout_start TIME NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_schedule_exceptions_scope (academic_year_id, exception_date, scope, class_scope_key),
    KEY idx_schedule_exceptions_lookup (academic_year_id, exception_date, is_active),
    CONSTRAINT fk_schedule_exceptions_year FOREIGN KEY (academic_year_id)
        REFERENCES academic_years (id) ON DELETE RESTRICT,
    CONSTRAINT fk_schedule_exceptions_class FOREIGN KEY (class_id)
        REFERENCES classes (id) ON DELETE RESTRICT,
    CONSTRAINT chk_schedule_exceptions_scope CHECK (
        (scope = 'school' AND class_id IS NULL) OR (scope = 'class' AND class_id IS NOT NULL)
    ),
    CONSTRAINT chk_schedule_exceptions_override CHECK (
        exception_type = 'holiday' OR checkin_start IS NOT NULL OR late_after IS NOT NULL
        OR checkin_cutoff IS NOT NULL OR checkout_start IS NOT NULL
    ),
    CONSTRAINT chk_schedule_exceptions_time_order CHECK (
        (checkin_start IS NULL OR late_after IS NULL OR checkin_start <= late_after)
        AND (late_after IS NULL OR checkin_cutoff IS NULL OR late_after <= checkin_cutoff)
        AND (checkin_cutoff IS NULL OR checkout_start IS NULL OR checkin_cutoff <= checkout_start)
    )
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS school_geofences (
    id TINYINT UNSIGNED NOT NULL DEFAULT 1,
    name VARCHAR(100) NOT NULL DEFAULT 'Sekolah',
    latitude DECIMAL(10,7) NULL,
    longitude DECIMAL(10,7) NULL,
    radius_meters INT UNSIGNED NOT NULL DEFAULT 75,
    max_accuracy_meters DECIMAL(8,2) NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    updated_by_user_id BIGINT UNSIGNED NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT fk_school_geofences_updated_by FOREIGN KEY (updated_by_user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT chk_school_geofences_singleton CHECK (id = 1),
    CONSTRAINT chk_school_geofences_coordinates CHECK (
        (latitude IS NULL AND longitude IS NULL)
        OR (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)
    ),
    CONSTRAINT chk_school_geofences_radius CHECK (radius_meters > 0),
    CONSTRAINT chk_school_geofences_accuracy CHECK (
        max_accuracy_meters IS NULL OR max_accuracy_meters > 0
    ),
    CONSTRAINT chk_school_geofences_active_config CHECK (
        is_active = FALSE OR
        (latitude IS NOT NULL AND longitude IS NOT NULL AND max_accuracy_meters IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
