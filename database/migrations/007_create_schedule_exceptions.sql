-- Apply after 006_create_attendance_schedules.sql.
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
