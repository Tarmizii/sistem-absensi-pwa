-- Apply after 011_add_model_path_to_students.sql; the target database must already be selected.
-- One row per student per date (PRD 14.3, 14.4). Check-in and check-out mutate the same row.
-- 'Belum Absen' and 'Libur' are derived/schedule states and are never stored here.

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
    -- Source must match the side of the transaction it describes.
    CONSTRAINT chk_attendance_source_checkin CHECK (
        checkin_at IS NULL OR status_source IS NULL OR status_source <> 'finalization_job'
    ),
    CONSTRAINT chk_attendance_checkout_requires_checkin CHECK (
        checkout_at IS NULL OR checkin_at IS NOT NULL
    )
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
