import time
import signal
import sys
import metrics

from models import ExecuteRequest
from docker_executor import execute_code_docker
import store

# Flag for graceful shutdown
_shutdown = False


def _handle_shutdown(signum, frame):
    global _shutdown
    print("\n[worker] Shutdown signal received, finishing current job...")
    _shutdown = True


def process_one_job(job_id: str):
    """Run a single job through the Docker executor and save the result."""
    print(f"[worker] Picked up job {job_id}")

    # Fetch the job's code from Postgres
    job = store.get_job(job_id)
    if job is None:
        print(f"[worker] Job {job_id} not found in DB, skipping")
        return

    # Mark it running
    store.update_job_running(job_id)

    # We need the actual code — get_job doesn't return it, so fetch separately
    with store._connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT language, code FROM jobs WHERE id = %s", (job_id,))
            row = cur.fetchone()
    language, code = row[0], row[1]

    # Geo-analysis jobs legitimately run for minutes; give them headroom.
    # Untrusted quick snippets stay on a short leash.
    job_timeout = 600 if language == "python-geo" else 30

    # Build the request and run it through the hardened Docker executor
    req = ExecuteRequest(language=language, code=code, timeout_seconds=job_timeout)

    metrics.active_jobs.inc()          # one more job running
    try:
        result = execute_code_docker(req)
    finally:
        metrics.active_jobs.dec()      # done running (even if it errored)

    # Record metrics about this job
    metrics.jobs_total.labels(language=language, status=result.status).inc()
    metrics.job_duration.labels(language=language).observe(result.duration_ms / 1000.0)

    # Save the result back to Postgres
    store.update_job_result(
        job_id=job_id,
        status=result.status,
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
    )
    print(f"[worker] Finished job {job_id} -> {result.status}")


def main():
    # Register graceful shutdown handlers
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    # Start a Prometheus metrics endpoint on port 9100
    from prometheus_client import start_http_server
    start_http_server(9100)
    print("[worker] Metrics available at http://localhost:9100/metrics")

    print("[worker] Started. Waiting for jobs... (Ctrl+C to stop)")

    while not _shutdown:
        try:
            job_id = store.dequeue_job(timeout=5)
        except Exception as e:
            print(f"[worker] Redis error, retrying: {e}")
            time.sleep(1)
            continue
        if job_id is None:
            continue
        try:
            process_one_job(job_id)
        except Exception as e:
            print(f"[worker] Error processing {job_id}: {e}")

    print("[worker] Stopped cleanly.")


if __name__ == "__main__":
    main()