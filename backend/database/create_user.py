"""Create a sign-in account.

    python backend/database/create_user.py

Asks for a username, password (not echoed), role and full name. Student
accounts are linked to a student record by roll number, teacher accounts to
a staff record by ID, so their own views show the right person.
"""
import getpass
import sys

import bcrypt
from dotenv import load_dotenv

sys.path.insert(0, ".")
from backend.api.db import get_db_connection  # noqa: E402

load_dotenv()
ROLES = ("admin", "teacher", "student")

username = input("Username: ").strip()
password = getpass.getpass("Password: ")
if not username or len(username) > 50 or len(password) < 8:
    sys.exit("A username (up to 50 characters) and a password of at least 8 characters are required.")
role = (input("Role (admin/teacher/student) [admin]: ").strip() or "admin").lower()
if role not in ROLES:
    sys.exit(f"Role must be one of: {', '.join(ROLES)}")
full_name = input("Full name: ").strip()
if len(full_name) > 100:
    sys.exit("The full name can be at most 100 characters.")

conn = get_db_connection()
cur = conn.cursor()
student_id = staff_id = None
if role == "student":
    roll = input("Roll number of this student's record: ").strip()
    cur.execute("SELECT id, name FROM students WHERE roll_number = %s;", (roll,))
    row = cur.fetchone()
    if not row:
        sys.exit(f"No student with roll number '{roll}'. Add the student first.")
    student_id = row[0]
    print(f"Linked to student #{row[0]} {row[1]}.")
elif role == "teacher":
    cur.execute("SELECT id, name, role FROM staff ORDER BY id;")
    for sid, name, staff_role in cur.fetchall():
        print(f"  {sid}: {name} ({staff_role})")
    answer = input("ID of this teacher's staff record: ").strip()
    cur.execute("SELECT id FROM staff WHERE id = %s;", (int(answer) if answer.isdigit() else -1,))
    if not cur.fetchone():
        sys.exit(f"There is no staff record with ID '{answer}'.")
    staff_id = int(answer)

cur.execute("SELECT 1 FROM users WHERE username = %s;", (username,))
if cur.fetchone():
    sys.exit(f"The username '{username}' is already taken.")

hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
cur.execute(
    "INSERT INTO users (username, password_hash, role, full_name, student_id, staff_id) VALUES (%s, %s, %s, %s, %s, %s);",
    (username, hashed, role, full_name, student_id, staff_id)
)
conn.commit()
cur.close()
conn.close()
print(f"User '{username}' created with role '{role}'.")
