import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    print("Connected to PostgreSQL successfully!")

    cur = conn.cursor()
    cur.execute("SELECT * FROM students;")
    rows = cur.fetchall()

    print("Students in database:")
    for row in rows:
        print(row)

    cur.close()
    conn.close()

except Exception as e:
    print("Connection failed:", e)
