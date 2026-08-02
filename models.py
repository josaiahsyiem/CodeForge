from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    language: str = Field(..., description="Programming language, e.g. 'python'")
    code: str = Field(..., description="Source code to execute")
    timeout_seconds: int = Field(default=10, ge=1, le=600, description="Max wall-clock seconds")


class ExecuteResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    status: str  # completed | error | timeout

class JobSubmitResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    language: str | None = None
    status: str
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None

from typing import List, Optional


class TestCase(BaseModel):
    stdin: str = ""
    expected_stdout: str


class JudgeRequest(BaseModel):
    language: str
    code: str
    test_cases: List[TestCase]
    timeout_seconds: int = Field(default=10, ge=1, le=60)


class TestCaseResult(BaseModel):
    case: int
    status: str  # passed | wrong_answer | runtime_error | timeout
    expected: Optional[str] = None
    actual: Optional[str] = None
    duration_ms: int


class JudgeResponse(BaseModel):
    language: str
    total: int
    passed: int
    failed: int
    results: List[TestCaseResult]