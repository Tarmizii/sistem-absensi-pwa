-- Short-lived, single-use server-side state for student blink challenges.
-- This table contains no image or eye/face payload.
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
