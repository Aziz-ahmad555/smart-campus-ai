"""Turn database foreign-key refusals into clear 409 Conflict messages.

The database refuses to delete a row that others still point at (a class
with students or a teacher, a person with a login account, a user with a
registered fingerprint) and to save a row that points at something missing
(a student in a class that doesn't exist). Each refusal is identified by
its constraint name, and the message says exactly what to fix first.
"""
from fastapi import HTTPException
from fastapi.responses import JSONResponse


def _plural(n, word, plural=None):
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def _count(cur, sql, args):
    cur.execute(sql, args)
    return cur.fetchone()[0]


def _usernames(cur, column, row_id):
    cur.execute(f"SELECT username FROM users WHERE {column} = %s ORDER BY username;", (row_id,))
    return [r[0] for r in cur.fetchall()]


def class_still_used(cur, class_id):
    students = _count(cur, "SELECT count(*) FROM students WHERE class_id = %s;", (class_id,))
    teachers = _count(cur, "SELECT count(*) FROM staff WHERE class_id = %s;", (class_id,))
    parts = []
    if students:
        parts.append(_plural(students, "student"))
    if teachers:
        parts.append(_plural(teachers, "teacher"))
    what = " and ".join(parts) or "records"
    return f"This class still has {what} assigned. Reassign them first."


def person_has_account(cur, table, row_id):
    column = "student_id" if table == "students" else "staff_id"
    names = _usernames(cur, column, row_id)
    who = "student" if table == "students" else "staff member"
    listed = ", ".join(f"'{n}'" for n in names)
    if len(names) > 1:
        return (f"This {who} has login accounts ({listed}). "
                "Remove the accounts or unlink them from this person before deleting them.")
    has = f"a login account ({listed})" if names else "a login account"
    return f"This {who} has {has}. Remove the account or unlink it from this person before deleting them."


def user_has_fingerprints(cur, user_id):
    n = _count(cur, "SELECT count(*) FROM webauthn_credentials WHERE user_id = %s;", (user_id,))
    return (f"This user has {_plural(n, 'registered fingerprint')} for sign-in. "
            "Remove their fingerprints first, then delete the account.")


# Deleting a row that others still point at (no counts: used when the
# refusal wasn't expected by the endpoint).
DELETE_BLOCKED = {
    "students_class_id_fkey": "This class still has students assigned. Reassign them first.",
    "staff_class_id_fkey": "This class still has a teacher assigned. Reassign them first.",
    "users_student_id_fkey": "This student has a login account. Remove or unlink it first.",
    "users_staff_id_fkey": "This staff member has a login account. Remove or unlink it first.",
    "webauthn_credentials_user_id_fkey": "This user has registered fingerprints for sign-in. Remove them before deleting the account.",
}

# Saving a row that points at something that doesn't exist.
MISSING_TARGET = {
    "students_class_id_fkey": "That class doesn't exist (it may have just been deleted). Pick another class.",
    "staff_class_id_fkey": "That class doesn't exist (it may have just been deleted). Pick another class.",
    "users_student_id_fkey": "That student record doesn't exist.",
    "users_staff_id_fkey": "That staff record doesn't exist.",
    "webauthn_credentials_user_id_fkey": "That user account no longer exists.",
}


GENERIC = "This change conflicts with related records, so the database refused it."


def _constraint(error):
    return getattr(getattr(error, "diag", None), "constraint_name", None) or ""


def _is_delete_refusal(error):
    # PostgreSQL: 'update or delete on table "x" violates foreign key constraint ...'
    return str(error).lstrip().startswith("update or delete on table")


def static_message(error):
    table = DELETE_BLOCKED if _is_delete_refusal(error) else MISSING_TARGET
    return table.get(_constraint(error), GENERIC)


def explain(error, cur, deleting=None):
    """Message for a psycopg2 ForeignKeyViolation. `deleting` is
    (table, id) when the refused statement was a DELETE of that row."""
    if deleting and _is_delete_refusal(error):
        table, row_id = deleting
        if table == "classes":
            return class_still_used(cur, row_id)
        if table in ("students", "staff"):
            return person_has_account(cur, table, row_id)
        if table == "users":
            return user_has_fingerprints(cur, row_id)
    return static_message(error)


def conflict(error, conn, deleting=None):
    """Roll back the failed statement and raise a 409 that explains it."""
    conn.rollback()
    with conn.cursor() as cur:
        message = explain(error, cur, deleting)
    return HTTPException(status_code=409, detail=message)


async def unhandled_fk_violation(request, error):
    """Last line of defence: any foreign-key refusal not handled by an
    endpoint becomes a 409 instead of a 500."""
    return JSONResponse(status_code=409, content={"detail": static_message(error)})
