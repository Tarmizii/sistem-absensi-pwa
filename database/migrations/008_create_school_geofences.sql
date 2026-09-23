-- Apply after 007_create_schedule_exceptions.sql.
-- A missing/unverified point and accuracy policy leave the fence inactive.
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
