-- Migration 001: link sign-in accounts to student/staff records by ID.
--
-- Before this, a student's or teacher's views were found by matching their
-- account's full name inside event labels, so "Ali" also matched "Ali Khan".
-- Now each account points at exactly one student or staff row, and events
-- carry person_type/person_id.
--
-- Run once on an existing database (new databases get these columns from
-- schema.sql already):
--   psql -U postgres -d smart_campus_db -f backend/database/migrations/001_link_users_to_people.sql
--
-- Recognition events are held in the backend's memory, not in the database,
-- so there are no stored event rows to migrate; events recorded after the
-- upgrade carry IDs.

BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS student_id INTEGER REFERENCES students(id) ON DELETE SET NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS staff_id   INTEGER REFERENCES staff(id)    ON DELETE SET NULL;

-- Backfill: link an account only when its full name matches exactly one
-- record. Ambiguous or missing matches stay NULL (listed below).
UPDATE users u
SET student_id = s.id
FROM students s
WHERE u.role = 'student' AND u.student_id IS NULL AND s.name = u.full_name
  AND (SELECT COUNT(*) FROM students s2 WHERE s2.name = u.full_name) = 1;

UPDATE users u
SET staff_id = st.id
FROM staff st
WHERE u.role = 'teacher' AND u.staff_id IS NULL AND st.name = u.full_name
  AND (SELECT COUNT(*) FROM staff st2 WHERE st2.name = u.full_name) = 1;

COMMIT;

-- Accounts that still need linking by hand (e.g.
--   UPDATE users SET student_id = 3 WHERE username = 'someone';):
SELECT id, username, role, full_name
FROM users
WHERE (role = 'student' AND student_id IS NULL) OR (role = 'teacher' AND staff_id IS NULL);
