"""Migrations 001 -> 002 -> 003 turn a copy of the production database's
structure (tests/fixtures/pre_migration_schema.sql) into exactly what
schema.sql creates, and each migration is safe to run twice."""
import os
import uuid

import psycopg2
import pytest

from tests.conftest import ROOT

MIGRATIONS = ROOT / "backend" / "database" / "migrations"
PRE_MIGRATION = ROOT / "tests" / "fixtures" / "pre_migration_schema.sql"
SCHEMA = ROOT / "backend" / "database" / "schema.sql"


def run(conn, path):
    conn.cursor().execute(path.read_text(encoding="utf-8"))


@pytest.fixture
def fresh_db(database):
    """A new empty database in the test cluster (dropped afterwards)."""
    created = []

    def make():
        name = "mig_" + uuid.uuid4().hex[:8]
        admin = psycopg2.connect(host=os.environ["DB_HOST"], port=os.environ["DB_PORT"], dbname="postgres",
                                 user=os.environ["DB_USER"], password=os.environ.get("DB_PASSWORD") or None)
        admin.autocommit = True
        try:
            admin.cursor().execute(f"CREATE DATABASE {name};")
        except psycopg2.Error as e:
            pytest.skip(f"can't create test databases here: {e}")
        finally:
            admin.close()
        conn = psycopg2.connect(host=os.environ["DB_HOST"], port=os.environ["DB_PORT"], dbname=name,
                                user=os.environ["DB_USER"], password=os.environ.get("DB_PASSWORD") or None)
        conn.autocommit = True
        created.append((name, conn))
        return conn

    yield make
    for name, conn in created:
        conn.close()
        admin = psycopg2.connect(host=os.environ["DB_HOST"], port=os.environ["DB_PORT"], dbname="postgres",
                                 user=os.environ["DB_USER"], password=os.environ.get("DB_PASSWORD") or None)
        admin.autocommit = True
        admin.cursor().execute(f"DROP DATABASE IF EXISTS {name};")
        admin.close()


def structure(conn):
    """Columns, constraints and indexes, in a comparable form."""
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name, column_name, data_type, character_maximum_length, is_nullable, column_default
        FROM information_schema.columns WHERE table_schema = 'public' ORDER BY 1, 2;""")
    columns = cur.fetchall()
    cur.execute("""
        SELECT conrelid::regclass::text, conname, contype, pg_get_constraintdef(oid)
        FROM pg_constraint WHERE connamespace = 'public'::regnamespace ORDER BY 1, 2;""")
    constraints = cur.fetchall()
    cur.execute("SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1, 2;")
    indexes = cur.fetchall()
    return {"columns": columns, "constraints": constraints, "indexes": indexes}


def migrate(conn):
    for name in ("001_link_users_to_people.sql", "002_events_table.sql", "003_tighten_constraints.sql"):
        run(conn, MIGRATIONS / name)


def test_migrated_production_structure_equals_schema_sql(fresh_db):
    production = fresh_db()
    run(production, PRE_MIGRATION)
    migrate(production)

    fresh = fresh_db()
    run(fresh, SCHEMA)

    got, want = structure(production), structure(fresh)
    for part in ("columns", "constraints", "indexes"):
        assert got[part] == want[part], part


def test_migrations_are_safe_to_run_twice(fresh_db):
    conn = fresh_db()
    run(conn, PRE_MIGRATION)
    migrate(conn)
    once = structure(conn)
    migrate(conn)
    assert structure(conn) == once


def test_migrations_are_no_ops_on_a_fresh_schema(fresh_db):
    conn = fresh_db()
    run(conn, SCHEMA)
    before = structure(conn)
    migrate(conn)
    assert structure(conn) == before


def test_003_changes_nothing_when_a_row_breaks_a_rule(fresh_db):
    conn = fresh_db()
    run(conn, PRE_MIGRATION)
    run(conn, MIGRATIONS / "001_link_users_to_people.sql")
    run(conn, MIGRATIONS / "002_events_table.sql")
    conn.cursor().execute("INSERT INTO visitors (name, allowed_minutes) VALUES ('Legacy visitor', NULL);")
    before = structure(conn)
    with pytest.raises(psycopg2.errors.NotNullViolation):
        run(conn, MIGRATIONS / "003_tighten_constraints.sql")
    conn.cursor().execute("ROLLBACK;")                   # what psql does at the end of a failed BEGIN block
    assert structure(conn) == before                     # the whole migration rolled back


def test_003_pre_check_query_finds_the_bad_rows(fresh_db):
    conn = fresh_db()
    run(conn, PRE_MIGRATION)
    cur = conn.cursor()
    cur.execute("INSERT INTO users (username, password_hash, role) VALUES ('odd', 'x', 'superuser');")
    cur.execute("INSERT INTO staff (name) VALUES ('No role');")
    sql = (MIGRATIONS / "003_tighten_constraints.sql").read_text(encoding="utf-8")
    pre_check = "\n".join(line[3:] for line in sql.split("-- Pre-check")[1].splitlines()[2:] if line.startswith("-- "))
    cur.execute(pre_check)
    counts = dict(zip([d.name for d in cur.description], cur.fetchone()))
    assert counts == {"staff_missing": 1, "students_missing": 0, "bad_roles": 1, "visitors_bad": 0,
                      "credentials_missing": 0, "duplicate_credentials": 0}
