import json
import redis
import psycopg

from config import (
    REDIS_HOST, REDIS_PORT, JOB_QUEUE_KEY,
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
    POSTGRES_USER, POSTGRES_PASSWORD,
)

# --- Redis (the queue) ---
_redis = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    socket_timeout=None,          # no socket-level read timeout
    socket_keepalive=True,
)


def enqueue_job(job_id: str):
    """Push a job ID onto the Redis queue for a worker to pick up."""
    _redis.lpush(JOB_QUEUE_KEY, job_id)


def dequeue_job(timeout: int = 5):
    """Block until a job ID is available, or return None after `timeout` seconds."""
    result = _redis.brpop(JOB_QUEUE_KEY, timeout=timeout)
    if result is None:
        return None
    # brpop returns (queue_name, value)
    return result[1]


# --- Postgres (permanent job storage) ---
def _connect():
    return psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )


def create_job(job_id: str, language: str, code: str):
    """Insert a new job with status 'queued'."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO jobs (id, language, code, status) VALUES (%s, %s, %s, 'queued')",
                (job_id, language, code),
            )


def update_job_running(job_id: str):
    """Mark a job as running."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET status = 'running' WHERE id = %s",
                (job_id,),
            )


def update_job_result(job_id: str, status: str, stdout: str, stderr: str,
                      exit_code: int, duration_ms: int):
    """Save the final result of a job."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE jobs
                   SET status = %s, stdout = %s, stderr = %s,
                       exit_code = %s, duration_ms = %s, completed_at = NOW()
                   WHERE id = %s""",
                (status, stdout, stderr, exit_code, duration_ms, job_id),
            )


def get_job(job_id: str):
    """Fetch a job's current state as a dict, or None if not found."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, language, status, stdout, stderr,
                          exit_code, duration_ms
                   FROM jobs WHERE id = %s""",
                (job_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "job_id": row[0],
                "language": row[1],
                "status": row[2],
                "stdout": row[3],
                "stderr": row[4],
                "exit_code": row[5],
                "duration_ms": row[6],
            }
import hashlib


def lookup_api_key(raw_key: str):
    """Return {'key_hash', 'rate_limit'} if the key is valid and active, else None."""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT key_hash, rate_limit FROM api_keys WHERE key_hash = %s AND is_active = TRUE",
                (key_hash,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {"key_hash": row[0], "rate_limit": row[1]}