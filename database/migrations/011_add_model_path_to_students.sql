-- Apply after 010_create_face_enrollment_challenges.sql; the target database must already be selected.
-- Adds model_path to students for T16 face model storage.

ALTER TABLE students
    ADD COLUMN model_path VARCHAR(255) NULL DEFAULT NULL AFTER face_registered;
