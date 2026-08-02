import psycopg
from config import (
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
    POSTGRES_USER, POSTGRES_PASSWORD,
)

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    language     TEXT NOT NULL,
    code         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'queued',
    stdout       TEXT,
    stderr       TEXT,
    exit_code    INTEGER,
    duration_ms  INTEGER,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
"""

def main():
    conn = psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )
    with conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE)
    conn.close()
    print("Table 'jobs' created (or already exists).")

if __name__ == "__main__":
    main()