import subprocess
import time
import tempfile
import os

from models import ExecuteRequest, ExecuteResponse


def execute_code(req: ExecuteRequest) -> ExecuteResponse:
    # Write the submitted code to a temporary file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write(req.code)
        code_path = f.name

    start = time.perf_counter()

    try:
        result = subprocess.run(
            ["python", code_path],
            capture_output=True,
            text=True,
            timeout=req.timeout_seconds,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)

        status = "completed" if result.returncode == 0 else "error"

        return ExecuteResponse(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            duration_ms=duration_ms,
            status=status,
        )

    except subprocess.TimeoutExpired:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return ExecuteResponse(
            stdout="",
            stderr=f"Execution timed out after {req.timeout_seconds}s",
            exit_code=-1,
            duration_ms=duration_ms,
            status="timeout",
        )

    finally:
        # Always clean up the temp file, even if execution failed
        if os.path.exists(code_path):
            os.remove(code_path)