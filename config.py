# Connection settings for CodeForge's Redis and Postgres

REDIS_HOST = "localhost"
REDIS_PORT = 6381          # codeforge-redis

POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5434        # codeforge-postgres
POSTGRES_DB = "codeforge"
POSTGRES_USER = "postgres"
POSTGRES_PASSWORD = "codeforge"

# The Redis list we use as the job queue
JOB_QUEUE_KEY = "codeforge:jobs"