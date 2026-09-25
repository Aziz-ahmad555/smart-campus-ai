-- Smart Campus AI database schema (PostgreSQL 13+).
-- Creates every table the backend uses. Safe to re-run: existing tables
-- are left as they are.
--
--   psql -U postgres -d smart_campus_db -f backend/database/schema.sql

CREATE TABLE IF NOT EXISTS classes (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    grade_level TEXT,
    section     TEXT
);

CREATE TABLE IF NOT EXISTS students (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    roll_number  TEXT NOT NULL UNIQUE,           -- duplicate roll numbers are rejected (400)
    photo_folder TEXT NOT NULL,                  -- folder under data/known_faces/
    class_id     INTEGER REFERENCES classes(id) ON DELETE SET NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staff (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    role         TEXT NOT NULL,                  -- Teacher | Security | Worker | Admin Staff | Other
    department   TEXT,
    photo_folder TEXT NOT NULL,
    class_id     INTEGER REFERENCES classes(id) ON DELETE SET NULL   -- the class a teacher teaches
);

CREATE TABLE IF NOT EXISTS visitors (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    cnic_or_id      TEXT,
    reason          TEXT,
    host_name       TEXT,
    allowed_minutes INTEGER NOT NULL DEFAULT 60 CHECK (allowed_minutes > 0),
    check_in_time   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    check_out_time  TIMESTAMP,
    status          TEXT NOT NULL DEFAULT 'checked_in'   -- set to 'checked_out' on check-out
);

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,                 -- bcrypt
    role          TEXT NOT NULL CHECK (role IN ('admin', 'teacher', 'student')),
    full_name     TEXT,
    -- Which person this account belongs to (see migrations/001).
    student_id    INTEGER REFERENCES students(id) ON DELETE SET NULL,   -- student accounts
    staff_id      INTEGER REFERENCES staff(id) ON DELETE SET NULL       -- teacher accounts
);

CREATE TABLE IF NOT EXISTS webauthn_credentials (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    credential_id BYTEA NOT NULL UNIQUE,
    public_key    BYTEA NOT NULL,
    sign_count    INTEGER NOT NULL DEFAULT 0
);
