-- Apply after 012_create_attendance_records.sql; select the target database first.
-- A class/date is frozen once: attendance transactions, manual status, or day finalization.
-- Historical rows created by the T27 backfill are marked 'reconstructed'.

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
