import sys
import secrets
import hashlib

import psycopg
from config import (
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
    POSTGRES_USER, POSTGRES_PASSWORD,
)


def hash_key(raw_key: str) -> str:
    """SHA-256 hash of the key. We store this, never the raw key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_key(name: str, rate_limit: int = 60) -> str:
    # Create a random, unguessable key
    raw_key = "cf_" + secrets.token_urlsafe(32)
    key_hash = hash_key(raw_key)

    conn = psycopg.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT, dbname=POSTGRES_DB,
        user=POSTGRES_USER, password=POSTGRES_PASSWORD,
    )
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO api_keys (key_hash, name, rate_limit) VALUES (%s, %s, %s)",
                (key_hash, name, rate_limit),
            )
    conn.close()
    return raw_key


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "default"
    rate = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    key = generate_key(name, rate)
    print(f"API key created for '{name}' (rate limit: {rate}/min)")
    print(f"  {key}")
    print("Store this now — it will NOT be shown again.")