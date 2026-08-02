import uuid
from fastapi import FastAPI, HTTPException, Header, Depends

from models import ExecuteRequest, JobSubmitResponse, JobStatusResponse, JudgeRequest, JudgeResponse
from judge import run_judge
from ratelimit import registry
import store

app = FastAPI(title="CodeForge", version="0.6.0")


def require_api_key(x_api_key: str = Header(None)):
    """Auth + rate-limit dependency. Runs before protected endpoints."""
    # 1. Must provide a key
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key (X-API-Key header)")

    # 2. Key must be valid and active
    key_info = store.lookup_api_key(x_api_key)
    if key_info is None:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    # 3. Rate limit check (token bucket per key)
    bucket = registry.get_bucket(key_info["key_hash"], key_info["rate_limit"])
    if not bucket.allow():
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({key_info['rate_limit']}/min). Try again shortly.",
        )

    return key_info


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/jobs", response_model=JobSubmitResponse)
def submit_job(req: ExecuteRequest, key_info: dict = Depends(require_api_key)) -> JobSubmitResponse:
    job_id = str(uuid.uuid4())
    store.create_job(job_id, req.language, req.code)
    store.enqueue_job(job_id)
    return JobSubmitResponse(job_id=job_id, status="queued")


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, key_info: dict = Depends(require_api_key)) -> JobStatusResponse:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job)


@app.post("/judge", response_model=JudgeResponse)
def judge(req: JudgeRequest, key_info: dict = Depends(require_api_key)) -> JudgeResponse:
    return run_judge(req)