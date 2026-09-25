-- Migration 003: apply the stricter rules from schema.sql to an existing
-- database. Run after 001 and 002. Safe to run more than once.
--
--   psql -U postgres -d smart_campus_db -f backend/database/migrations/003_tighten_constraints.sql
--
-- What it enforces:
--   staff.role, staff.photo_folder, students.photo_folder, students.created_at  NOT NULL
--   users.role                     only 'admin', 'teacher' or 'student'
--   visitors.allowed_minutes       NOT NULL and > 0
--   visitors.check_in_time/status  NOT NULL
--   webauthn_credentials.user_id / sign_count  NOT NULL, credential_id UNIQUE
--
-- It runs in one transaction: if any existing row breaks a rule, nothing is
-- changed and the error names the rule. Find such rows first with the
-- "pre-check" query at the bottom of this file.

BEGIN;

ALTER TABLE staff    ALTER COLUMN role         SET NOT NULL;
ALTER TABLE staff    ALTER COLUMN photo_folder SET NOT NULL;
ALTER TABLE students ALTER COLUMN photo_folder SET NOT NULL;
ALTER TABLE students ALTER COLUMN created_at   SET NOT NULL;

ALTER TABLE visitors ALTER COLUMN allowed_minutes SET NOT NULL;
ALTER TABLE visitors ALTER COLUMN check_in_time   SET NOT NULL;
ALTER TABLE visitors ALTER COLUMN status          SET NOT NULL;

ALTER TABLE webauthn_credentials ALTER COLUMN user_id    SET NOT NULL;
ALTER TABLE webauthn_credentials ALTER COLUMN sign_count SET NOT NULL;

-- Named constraints are added only if they don't exist yet.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_role_check') THEN
        ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('admin', 'teacher', 'student'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'visitors_allowed_minutes_check') THEN
        ALTER TABLE visitors ADD CONSTRAINT visitors_allowed_minutes_check CHECK (allowed_minutes > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'webauthn_credentials_credential_id_key') THEN
        ALTER TABLE webauthn_credentials ADD CONSTRAINT webauthn_credentials_credential_id_key UNIQUE (credential_id);
    END IF;
END
$$;

COMMIT;

-- Pre-check (read-only). Every count should be 0 before running this file:
--
-- SELECT
--   (SELECT count(*) FROM staff    WHERE role IS NULL OR photo_folder IS NULL)                   AS staff_missing,
--   (SELECT count(*) FROM students WHERE photo_folder IS NULL OR created_at IS NULL)             AS students_missing,
--   (SELECT count(*) FROM users    WHERE role IS NULL OR role NOT IN ('admin','teacher','student')) AS bad_roles,
--   (SELECT count(*) FROM visitors WHERE allowed_minutes IS NULL OR allowed_minutes <= 0
--                                    OR check_in_time IS NULL OR status IS NULL)                 AS visitors_bad,
--   (SELECT count(*) FROM webauthn_credentials WHERE user_id IS NULL OR sign_count IS NULL)      AS credentials_missing,
--   (SELECT count(*) - count(DISTINCT credential_id) FROM webauthn_credentials)                  AS duplicate_credentials;
