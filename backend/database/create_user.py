"""Create a sign-in account.

    python backend/database/create_user.py

Asks for a username, password (not echoed), role and full name. For a
teacher or student, the full name must match their name in the staff or
students table so their class/profile views find them.
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
if not username or len(password) < 8:
    sys.exit("A username and a password of at least 8 characters are required.")
role = (input("Role (admin/teacher/student) [admin]: ").strip() or "admin").lower()
if role not in ROLES:
    sys.exit(f"Role must be one of: {', '.join(ROLES)}")
full_name = input("Full name: ").strip()

hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

conn = get_db_connection()
cur = conn.cursor()
cur.execute(
    "INSERT INTO users (username, password_hash, role, full_name) VALUES (%s, %s, %s, %s);",
    (username, hashed, role, full_name)
)
conn.commit()
cur.close()
conn.close()
print(f"User '{username}' created with role '{role}'.")
