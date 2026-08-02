from models import ExecuteRequest, JudgeRequest, JudgeResponse, TestCaseResult
from docker_executor import execute_code_docker


def _normalize(text: str) -> str:
    """Trim trailing whitespace/newlines so '10\n' matches '10'."""
    if text is None:
        return ""
    return text.strip()


def run_judge(req: JudgeRequest) -> JudgeResponse:
    results = []
    passed = 0

    for i, tc in enumerate(req.test_cases, start=1):
        # Build a single-run request for this test case's code
        exec_req = ExecuteRequest(
            language=req.language,
            code=req.code,
            timeout_seconds=req.timeout_seconds,
        )

        # Feed stdin by wrapping the code to read from a preset string.
        # This avoids fragile stdin-socket handling on Windows/Docker.
        if req.language == "python":
            wrapped = (
                "import sys, io\n"
                f"sys.stdin = io.StringIO({tc.stdin!r})\n"
                + req.code
            )
        elif req.language == "javascript":
            # Node: preload stdin string as the data for readline/process.stdin
            wrapped = (
                f"const __stdin = {tc.stdin!r};\n"
                "let __lines = __stdin.split('\\n'); let __i = 0;\n"
                "global.prompt = () => __lines[__i++];\n"
                + req.code
            )
        else:
            wrapped = req.code

        exec_req_wrapped = ExecuteRequest(
            language=req.language,
            code=wrapped,
            timeout_seconds=req.timeout_seconds,
        )
        result = execute_code_docker(exec_req_wrapped)

        actual = _normalize(result.stdout)
        expected = _normalize(tc.expected_stdout)

        # Decide the verdict for this case
        if result.status == "timeout":
            status = "timeout"
        elif result.status == "error":
            status = "runtime_error"
        elif actual == expected:
            status = "passed"
            passed += 1
        else:
            status = "wrong_answer"

        results.append(TestCaseResult(
            case=i,
            status=status,
            expected=expected if status == "wrong_answer" else None,
            actual=actual if status == "wrong_answer" else None,
            duration_ms=result.duration_ms,
        ))

    return JudgeResponse(
        language=req.language,
        total=len(req.test_cases),
        passed=passed,
        failed=len(req.test_cases) - passed,
        results=results,
    )