# Connection settings for CodeForge's Redis and Postgres
# Ports can be overridden via environment variables (used in CI).

import os

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6381"))       # codeforge-redis (local)

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5434"))  # codeforge-postgres (local)
POSTGRES_DB = os.environ.get("POSTGRES_DB", "codeforge")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "codeforge")

# The Redis list we use as the job queue
JOB_QUEUE_KEY = "codeforge:jobs"