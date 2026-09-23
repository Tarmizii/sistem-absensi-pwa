-- Apply after 005_create_academic_years_classes_enrollments.sql.
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
