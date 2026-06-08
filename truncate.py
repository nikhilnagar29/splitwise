import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgres://user:password@localhost:5432/splitwise"
)

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE messages, payments, splits, expenses, group_members, groups, users CASCADE;")
    conn.commit()
    print("Tables truncated successfully.")
except Exception as e:
    print("ERROR:", e)
