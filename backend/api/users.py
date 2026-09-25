"""Admin management of sign-in accounts: list, link/unlink to a student or
staff record, remove fingerprints, delete. Replaces create_user.py/SQL for
linking. Every route is admin-only."""
from typing import Optional

import psycopg2
import psycopg2.errors
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api import auth, conflicts
from backend.api.auth import admin_only
from backend.api.db import get_db_connection

router = APIRouter(prefix="/users", tags=["users"])

USER_QUERY = """
    SELECT u.id, u.username, u.role, u.full_name, u.created_at, u.student_id, u.staff_id,
           COALESCE(s.name, st.name) AS linked_name,
           s.roll_number AS linked_roll_number,
           (SELECT count(*) FROM webauthn_credentials c WHERE c.user_id = u.id) AS fingerprints
    FROM users u
    LEFT JOIN students s ON s.id = u.student_id
    LEFT JOIN staff st ON st.id = u.staff_id
"""


def _fetch_user(cur, user_id):
    cur.execute(USER_QUERY + " WHERE u.id = %s;", (user_id,))
    user = cur.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")
    return user


@router.get("")
def list_users(session=Depends(admin_only)):
    """Accounts with who they're linked to. Password hashes are never returned."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(USER_QUERY + " ORDER BY u.role, u.username;")
            return {"users": cur.fetchall()}
    finally:
        conn.close()


class LinkRequest(BaseModel):
    person_id: Optional[int] = None     # a student id (student accounts) or staff id (teacher accounts); null unlinks


@router.put("/{user_id}/link")
def link_user(user_id: int, body: LinkRequest, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        user = _fetch_user(cur, user_id)
        if user["role"] == "admin":
            raise HTTPException(status_code=400, detail="Admin accounts aren't linked to a student or staff record.")
        student_id = body.person_id if user["role"] == "student" else None
        staff_id = body.person_id if user["role"] == "teacher" else None
        try:
            cur.execute("UPDATE users SET student_id = %s, staff_id = %s WHERE id = %s;", (student_id, staff_id, user_id))
            conn.commit()
        except psycopg2.errors.ForeignKeyViolation as e:     # that student/staff record doesn't exist
            raise conflicts.conflict(e, conn)
        auth.update_user_link(user_id, student_id, staff_id)  # takes effect for open sessions now
        return {"user": _fetch_user(cur, user_id)}
    finally:
        cur.close()
        conn.close()


@router.delete("/{user_id}/fingerprints")
def remove_fingerprints(user_id: int, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        _fetch_user(cur, user_id)
        cur.execute("DELETE FROM webauthn_credentials WHERE user_id = %s;", (user_id,))
        removed = cur.rowcount
        conn.commit()
        return {"removed": removed}
    finally:
        cur.close()
        conn.close()


@router.delete("/{user_id}")
def delete_user(user_id: int, session=Depends(admin_only)):
    if user_id == session["user_id"]:
        raise HTTPException(status_code=400, detail="You can't delete your own account.")
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        user = _fetch_user(cur, user_id)
        if user["role"] == "admin":
            cur.execute("SELECT count(*) AS n FROM users WHERE role = 'admin';")
            if cur.fetchone()["n"] <= 1:
                raise HTTPException(status_code=400, detail="This is the last admin account, so it can't be deleted.")
        try:
            cur.execute("DELETE FROM users WHERE id = %s;", (user_id,))
            conn.commit()
        except psycopg2.errors.ForeignKeyViolation as e:     # registered fingerprints
            raise conflicts.conflict(e, conn, deleting=("users", user_id))
    finally:
        cur.close()
        conn.close()
    auth.end_user_sessions(user_id)                          # signed out everywhere
    return {"deleted": True}
