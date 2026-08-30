import os
import bcrypt
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

username = input("Username: ")
password = input("Password: ")
role = input("Role (admin/teacher/student): ") or "admin"
full_name = input("Full name: ")

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
