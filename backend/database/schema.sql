-- Smart Campus AI database schema (PostgreSQL 13+).
-- Creates every table the backend uses. Safe to re-run: existing tables
-- are left as they are.
--
--   psql -U postgres -d smart_campus_db -f backend/database/schema.sql
--
-- Matches the production database after migrations 001-003: same column
-- types and lengths, plus the stricter rules added by migration 003
-- (NOT NULLs, the user-role CHECK, unique credential IDs).
--
-- Foreign keys have no ON DELETE action, so the database REFUSES to delete a
-- class that still has students or a teacher, a student/staff member with a
-- login account, or a user with a registered fingerprint. The API turns those
-- refusals into 409 responses that say what to fix first. (Events are the
-- exception: deleting a person keeps their events and clears the link.)

CREATE TABLE IF NOT EXISTS classes (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50) NOT NULL,
    grade_level VARCHAR(20),
    section     VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS students (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    roll_number  VARCHAR(50) NOT NULL UNIQUE,     -- duplicate roll numbers are rejected (400)
    photo_folder VARCHAR(100) NOT NULL,           -- folder under data/known_faces/
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    class_id     INTEGER REFERENCES classes(id),
    person_type  VARCHAR(20) DEFAULT 'student'
);

CREATE TABLE IF NOT EXISTS staff (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    role         VARCHAR(50) NOT NULL,            -- Teacher | Security | Worker | Admin Staff | Other
    department   VARCHAR(100),
    photo_folder VARCHAR(100) NOT NULL,
    person_type  VARCHAR(20) DEFAULT 'staff',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    class_id     INTEGER REFERENCES classes(id)   -- the class a teacher teaches
);

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,          -- bcrypt
    role          VARCHAR(20) NOT NULL DEFAULT 'admin'
                  CONSTRAINT users_role_check CHECK (role IN ('admin', 'teacher', 'student')),
    full_name     VARCHAR(100),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Which person this account belongs to (see migrations/001).
    staff_id      INTEGER REFERENCES staff(id),     -- teacher accounts
    student_id    INTEGER REFERENCES students(id)   -- student accounts
);

CREATE TABLE IF NOT EXISTS visitors (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    cnic_or_id      VARCHAR(50),
    reason          VARCHAR(255),
    host_name       VARCHAR(100),
    check_in_time   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    allowed_minutes INTEGER NOT NULL DEFAULT 60
                    CONSTRAINT visitors_allowed_minutes_check CHECK (allowed_minutes > 0),
    check_out_time  TIMESTAMP,
    status          VARCHAR(20) NOT NULL DEFAULT 'checked_in'   -- set to 'checked_out' on check-out
);

CREATE TABLE IF NOT EXISTS webauthn_credentials (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    credential_id BYTEA NOT NULL CONSTRAINT webauthn_credentials_credential_id_key UNIQUE,
    public_key    BYTEA NOT NULL,
    sign_count    INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recognition events (entries, exits, alerts, falls). Written in the
-- background by the tracking engine; see migrations/002_events_table.sql.
CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    event_type  TEXT NOT NULL CHECK (event_type IN ('entry', 'exit', 'alert', 'fall')),
    -- Who it was: a student OR a staff member, or neither (unknown person, crowd alert).
    -- One foreign key can't point at two tables, hence two nullable columns.
    student_id  INTEGER REFERENCES students(id) ON DELETE SET NULL,
    staff_id    INTEGER REFERENCES staff(id) ON DELETE SET NULL,
    label       TEXT NOT NULL,                   -- what was shown at the time, e.g. "Jane Doe (R-1)"
    track_id    INTEGER,                         -- ByteTrack ID within the camera session
    camera      TEXT NOT NULL DEFAULT 'main',
    confidence  REAL,                            -- recognition similarity for entries, else NULL
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (student_id IS NULL OR staff_id IS NULL)
);
CREATE INDEX IF NOT EXISTS events_created_at_idx ON events (created_at);
CREATE INDEX IF NOT EXISTS events_student_created_idx ON events (student_id, created_at) WHERE student_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS events_staff_created_idx ON events (staff_id, created_at) WHERE staff_id IS NOT NULL;
