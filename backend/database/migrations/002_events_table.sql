-- Migration 002: store recognition events in PostgreSQL.
--
-- Before this, events lived only in the backend's memory (the last 100)
-- and were lost on restart. Now every event is also written here, and the
-- dashboard and the teacher/student timelines read their history from this
-- table with pagination. Safe to run more than once.
--
--   psql -U postgres -d smart_campus_db -f backend/database/migrations/002_events_table.sql
--
-- A person is either a student or a staff member, so there are two nullable
-- foreign keys (at most one is set) instead of a single person_id, which
-- couldn't reference both tables. Deleting a person keeps their events
-- (the label still says who it was) and clears the link.

BEGIN;

CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    event_type  TEXT NOT NULL CHECK (event_type IN ('entry', 'exit', 'alert', 'fall')),
    student_id  INTEGER REFERENCES students(id) ON DELETE SET NULL,
    staff_id    INTEGER REFERENCES staff(id) ON DELETE SET NULL,
    label       TEXT NOT NULL,
    track_id    INTEGER,
    camera      TEXT NOT NULL DEFAULT 'main',
    confidence  REAL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (student_id IS NULL OR staff_id IS NULL)
);

CREATE INDEX IF NOT EXISTS events_created_at_idx ON events (created_at);
CREATE INDEX IF NOT EXISTS events_student_created_idx ON events (student_id, created_at) WHERE student_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS events_staff_created_idx ON events (staff_id, created_at) WHERE staff_id IS NOT NULL;

COMMIT;
