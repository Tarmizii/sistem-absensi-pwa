-- Apply after 013_create_attendance_day_snapshots.sql; select the target database first.
-- Runs are inserted only after aggregation and clustering both complete successfully.

CREATE TABLE IF NOT EXISTS kmeans_runs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    academic_year_id BIGINT UNSIGNED NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    created_by BIGINT UNSIGNED NOT NULL,
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
