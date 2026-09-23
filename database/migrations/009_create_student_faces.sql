-- Apply after 008_create_school_geofences.sql.
-- Rows are inserted only after a pose passes the capture checks in T15.
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
