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
    model_path VARCHAR(255) NULL DEFAULT NULL,
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

CREATE TABLE IF NOT EXISTS face_enrollment_challenges (
    challenge_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    session_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    pose ENUM('front', 'left', 'right') NOT NULL,
    stage ENUM('await_open', 'await_closed', 'await_reopen') NOT NULL DEFAULT 'await_open',
    expires_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (challenge_hash),
    KEY idx_face_challenge_user_expiry (user_id, expires_at),
    CONSTRAINT fk_face_challenge_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE
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

CREATE TABLE IF NOT EXISTS attendance_records (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    student_id BIGINT UNSIGNED NOT NULL,
    class_id BIGINT UNSIGNED NULL COMMENT 'Historical snapshot; unchanged when the student moves class.',
    attendance_date DATE NOT NULL,
    status ENUM('present', 'late', 'permit', 'sick', 'absent') NULL
        COMMENT 'NULL until check-in or a manual status is recorded.',
    status_source ENUM('system', 'teacher', 'finalization_job') NULL,
    notes VARCHAR(500) NULL,

    checkin_at DATETIME(6) NULL,
    checkin_latitude DECIMAL(10,7) NULL,
    checkin_longitude DECIMAL(10,7) NULL,
    checkin_accuracy DECIMAL(8,2) NULL,
    checkin_photo VARCHAR(255) NULL,
    checkin_face_score DECIMAL(10,4) NULL,
    checkin_liveness_verified BOOLEAN NOT NULL DEFAULT FALSE,

    checkout_at DATETIME(6) NULL,
    checkout_latitude DECIMAL(10,7) NULL,
    checkout_longitude DECIMAL(10,7) NULL,
    checkout_accuracy DECIMAL(8,2) NULL,
    checkout_photo VARCHAR(255) NULL,
    checkout_face_score DECIMAL(10,4) NULL,
    checkout_liveness_verified BOOLEAN NOT NULL DEFAULT FALSE,

    created_by BIGINT UNSIGNED NULL,
    updated_by BIGINT UNSIGNED NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (id),
    UNIQUE KEY uq_attendance_student_date (student_id, attendance_date),
    KEY idx_attendance_date_status (attendance_date, status),
    KEY idx_attendance_date_class (attendance_date, class_id),

    CONSTRAINT fk_attendance_student FOREIGN KEY (student_id)
        REFERENCES students (id) ON DELETE RESTRICT,
    CONSTRAINT fk_attendance_class FOREIGN KEY (class_id)
        REFERENCES classes (id) ON DELETE RESTRICT,
    CONSTRAINT fk_attendance_created_by FOREIGN KEY (created_by)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_attendance_updated_by FOREIGN KEY (updated_by)
        REFERENCES users (id) ON DELETE RESTRICT,

    CONSTRAINT chk_attendance_checkin_coords CHECK (
        (checkin_latitude IS NULL AND checkin_longitude IS NULL)
        OR (checkin_latitude BETWEEN -90 AND 90 AND checkin_longitude BETWEEN -180 AND 180)
    ),
    CONSTRAINT chk_attendance_checkout_coords CHECK (
        (checkout_latitude IS NULL AND checkout_longitude IS NULL)
        OR (checkout_latitude BETWEEN -90 AND 90 AND checkout_longitude BETWEEN -180 AND 180)
    ),
    CONSTRAINT chk_attendance_checkin_accuracy CHECK (
        checkin_accuracy IS NULL OR checkin_accuracy >= 0
    ),
    CONSTRAINT chk_attendance_checkout_accuracy CHECK (
        checkout_accuracy IS NULL OR checkout_accuracy >= 0
    ),
    CONSTRAINT chk_attendance_source_checkin CHECK (
        checkin_at IS NULL OR status_source IS NULL OR status_source <> 'finalization_job'
    ),
    CONSTRAINT chk_attendance_checkout_requires_checkin CHECK (
        checkout_at IS NULL OR checkin_at IS NOT NULL
    )
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS attendance_day_snapshots (
    academic_year_id BIGINT UNSIGNED NOT NULL,
    class_id BIGINT UNSIGNED NOT NULL,
    attendance_date DATE NOT NULL,
    requires_attendance BOOLEAN NOT NULL,
    source ENUM(
        'attendance_transaction', 'manual_status', 'finalization_job', 'reconstructed'
    ) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (class_id, attendance_date),
    KEY idx_attendance_day_snapshots_year_date (academic_year_id, attendance_date, class_id),
    CONSTRAINT fk_attendance_day_snapshots_year FOREIGN KEY (academic_year_id)
        REFERENCES academic_years (id) ON DELETE RESTRICT,
    CONSTRAINT fk_attendance_day_snapshots_class FOREIGN KEY (class_id)
        REFERENCES classes (id) ON DELETE RESTRICT,
    CONSTRAINT chk_attendance_day_snapshot_requires_attendance CHECK (
        requires_attendance IN (0, 1)
    )
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS kmeans_runs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    academic_year_id BIGINT UNSIGNED NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    created_by BIGINT UNSIGNED NOT NULL,
    submission_key_hash CHAR(64) NULL,
    formula_version VARCHAR(40) NOT NULL,
    label_rule_version VARCHAR(180) NOT NULL,
    random_state INT UNSIGNED NOT NULL,
    n_init SMALLINT UNSIGNED NOT NULL,
    cluster_count TINYINT UNSIGNED NOT NULL DEFAULT 3,
    eligible_students INT UNSIGNED NOT NULL,
    ineligible_students INT UNSIGNED NOT NULL,
    reconstructed_snapshot_dates INT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY idx_kmeans_runs_year_period (academic_year_id, period_start, period_end, id),
    KEY idx_kmeans_runs_created (created_at, id),
    UNIQUE KEY uq_kmeans_runs_submission_key (submission_key_hash),
    CONSTRAINT fk_kmeans_runs_year FOREIGN KEY (academic_year_id)
        REFERENCES academic_years (id) ON DELETE RESTRICT,
    CONSTRAINT fk_kmeans_runs_creator FOREIGN KEY (created_by)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT chk_kmeans_runs_period CHECK (period_end >= period_start),
    CONSTRAINT chk_kmeans_runs_three_clusters CHECK (cluster_count = 3)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS kmeans_results (
    run_id BIGINT UNSIGNED NOT NULL,
    student_id BIGINT UNSIGNED NOT NULL,
    class_id BIGINT UNSIGNED NOT NULL,
    attendance_percentage DECIMAL(7,4) NULL,
    late_count INT UNSIGNED NOT NULL,
    alpha_count INT UNSIGNED NOT NULL,
    scheduled_school_days INT UNSIGNED NOT NULL,
    effective_days INT NOT NULL,
    is_eligible BOOLEAN NOT NULL,
    ineligible_reason VARCHAR(64) NULL,
    reconstructed_days INT UNSIGNED NOT NULL DEFAULT 0,
    cluster_no TINYINT UNSIGNED NULL,
    cluster_label ENUM('tinggi','sedang','rendah') NULL,
    PRIMARY KEY (run_id, student_id),
    KEY idx_kmeans_results_cluster (run_id, cluster_no, class_id, student_id),
    CONSTRAINT fk_kmeans_results_run FOREIGN KEY (run_id)
        REFERENCES kmeans_runs (id) ON DELETE RESTRICT,
    CONSTRAINT fk_kmeans_results_student FOREIGN KEY (student_id)
        REFERENCES students (id) ON DELETE RESTRICT,
    CONSTRAINT fk_kmeans_results_class FOREIGN KEY (class_id)
        REFERENCES classes (id) ON DELETE RESTRICT,
    CONSTRAINT chk_kmeans_result_assignment CHECK (
        (is_eligible = 1 AND attendance_percentage IS NOT NULL
            AND cluster_no BETWEEN 1 AND 3 AND cluster_label IS NOT NULL
            AND ineligible_reason IS NULL)
        OR (is_eligible = 0 AND attendance_percentage IS NULL
            AND cluster_no IS NULL AND cluster_label IS NULL
            AND ineligible_reason IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS kmeans_centroids (
    run_id BIGINT UNSIGNED NOT NULL,
    cluster_no TINYINT UNSIGNED NOT NULL,
    cluster_label ENUM('tinggi','sedang','rendah') NOT NULL,
    attendance_percentage DECIMAL(7,4) NOT NULL,
    late_count DECIMAL(9,4) NOT NULL,
    alpha_count DECIMAL(9,4) NOT NULL,
    student_count INT UNSIGNED NOT NULL,
    PRIMARY KEY (run_id, cluster_no),
    UNIQUE KEY uq_kmeans_centroid_label (run_id, cluster_label),
    CONSTRAINT fk_kmeans_centroids_run FOREIGN KEY (run_id)
        REFERENCES kmeans_runs (id) ON DELETE RESTRICT,
    CONSTRAINT chk_kmeans_centroid_rank CHECK (
        (cluster_no = 1 AND cluster_label = 'tinggi')
        OR (cluster_no = 2 AND cluster_label = 'sedang')
        OR (cluster_no = 3 AND cluster_label = 'rendah')
    )
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
