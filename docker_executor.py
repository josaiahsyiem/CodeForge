import docker
import time
import tempfile
import os
import tarfile
import io

from models import ExecuteRequest, ExecuteResponse
import languages

# One shared Docker client for the whole app
_client = docker.from_env()


def _make_code_tar(code: str, filename: str = "code.py") -> io.BytesIO:
    """Package the code string into an in-memory tar archive that we can
    stream into the container. Docker's put_archive expects a tar."""
    data = code.encode("utf-8")
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        info = tarfile.TarInfo(name=filename)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    tar_stream.seek(0)
    return tar_stream


def execute_code_docker(req: ExecuteRequest) -> ExecuteResponse:
    start = time.perf_counter()
    container = None

    # Reject unsupported languages cleanly
    if not languages.is_supported(req.language):
        return ExecuteResponse(
            stdout="",
            stderr=f"Unsupported language: {req.language}. Supported: {languages.supported_languages()}",
            exit_code=-1,
            duration_ms=0,
            status="error",
        )

    try:
        # 1. Create the container (but don't start it yet)
        lang_config = languages.get_config(req.language)

        # Geo workloads need network (data fetching) and more memory/disk.
        # Everything else stays fully locked down (no network).
        if req.language == "python-geo":
            net_mode = "bridge"       # allow network for data fetching
            mem = "1g"                # geo libs are memory-hungry
            tmp_size = "256m"         # room for downloaded/written files
            # Shared data volume so multi-stage pipelines can pass files
            volumes = {r"E:\GOAI\PHASE2\data": {"bind": "/data", "mode": "rw"}}
            read_only_root = False    # geo code writes to /data
        else:
            net_mode = "none"         # full lockdown for untrusted code
            mem = "256m"
            tmp_size = "32m"
            volumes = None
            read_only_root = True     # untrusted code: read-only everything

        container = _client.containers.create(
            image=lang_config["image"],
            command=lang_config["cmd"](req.code),
            working_dir="/tmp",
            stdin_open=True,
            tty=False,
            # --- Phase 3: resource limits ---
            mem_limit=mem,
            memswap_limit=mem,
            nano_cpus=1_000_000_000,
            pids_limit=64,
            # --- Phase 4: security hardening (profile depends on language) ---
            network_mode=net_mode,
            dns=["8.8.8.8", "1.1.1.1"] if req.language == "python-geo" else None,
            read_only=read_only_root,
            volumes=volumes,
            tmpfs={"/tmp": f"size={tmp_size}"},
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
        )

        # 2. Make the /sandbox dir and copy the code file into it


        # 3. Start the container
        container.start()

        # 4. Wait for it to finish, with a timeout
        try:
            result = container.wait(timeout=req.timeout_seconds)
            exit_code = result.get("StatusCode", -1)
            status = "completed" if exit_code == 0 else "error"
        except Exception:
            # Timeout: kill the container
            container.kill()
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ExecuteResponse(
                stdout="",
                stderr=f"Execution timed out after {req.timeout_seconds}s",
                exit_code=-1,
                duration_ms=duration_ms,
                status="timeout",
            )

        # 5. Read the logs (stdout + stderr)
        stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

        duration_ms = int((time.perf_counter() - start) * 1000)

        return ExecuteResponse(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=duration_ms,
            status=status,
        )

    finally:
        # 6. ALWAYS remove the container, no matter what happened
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass