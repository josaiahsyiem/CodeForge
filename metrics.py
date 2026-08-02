from prometheus_client import Counter, Histogram, Gauge

# Total jobs processed, split by language and final status
jobs_total = Counter(
    "codeforge_jobs_total",
    "Total jobs processed",
    ["language", "status"],
)

# How long jobs take to execute (seconds), split by language
job_duration = Histogram(
    "codeforge_job_duration_seconds",
    "Job execution duration in seconds",
    ["language"],
    buckets=[0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60],
)

# How many jobs are currently waiting in the queue
queue_depth = Gauge(
    "codeforge_queue_depth",
    "Number of jobs currently in the Redis queue",
)

# How many jobs a worker is actively running right now
active_jobs = Gauge(
    "codeforge_active_jobs",
    "Number of jobs currently being executed",
)