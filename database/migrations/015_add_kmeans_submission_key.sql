-- Apply after 014_create_kmeans_run_history.sql.
-- A unique per-form request key makes simultaneous/replayed submissions idempotent.

ALTER TABLE kmeans_runs
    ADD COLUMN submission_key_hash CHAR(64) NULL AFTER created_by,
    ADD UNIQUE KEY uq_kmeans_runs_submission_key (submission_key_hash);
