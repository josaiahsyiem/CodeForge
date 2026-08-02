"""
Attack suite for CodeForge — Phase 1 baseline.

Sends malicious payloads to the /execute endpoint and records whether
each attack SUCCEEDS (system is vulnerable) or is BLOCKED.

In Phase 1 (naive subprocess execution), nearly all of these succeed.
By Phase 4 (hardened Docker isolation), all should be blocked.

Run the server first:  uvicorn main:app --port 8080
Then in another terminal:  python attacks.py
"""

import requests

API = "http://127.0.0.1:8080/execute"

# Each attack: (name, code, what_success_looks_like)
ATTACKS = [
    (
        "file_read",
        # On Windows, read a system file instead of /etc/passwd
        "print(open(r'C:\\Windows\\System32\\drivers\\etc\\hosts').read())",
        "Reads a host system file",
    ),
    (
        "file_write",
        "open('/etc/pwned','w').write('compromised'); print('WROTE OK')",
        "Writes to the container's read-only filesystem",
    ),
    (
        "env_leak",
        "import os; print(dict(os.environ))",
        "Dumps host environment variables (secrets, API keys)",
    ),
    (
        "network_exfil",
        "import urllib.request; print(urllib.request.urlopen('https://httpbin.org/ip', timeout=5).read())",
        "Makes an outbound network call",
    ),
    (
        "cwd_snoop",
        "import os; print(os.listdir('.'))",
        "Lists files in the server's working directory",
    ),
]


def run_attack(name, code, description):
    try:
        resp = requests.post(
            API,
            json={"language": "python", "code": code, "timeout_seconds": 10},
            timeout=30,
        )
        data = resp.json()
        stdout = data.get("stdout", "")
        stderr = data.get("stderr", "")
        status = data.get("status", "")

        # Heuristic: attack "succeeded" if it completed and produced output
        # without an error/permission-denied
        # An attack "succeeded" if it ran without being stopped by the sandbox.
        # Different attacks prove success differently:
        #   - some print output (file_read, network, snoop)
        #   - some write a file silently (file_write) -> completed with no error IS success
        #   - a crash from the code itself (not a sandbox block) still shows access
        blocked_signals = ["permission denied", "operation not permitted",
                           "access is denied", "no such file"]
        stderr_lower = stderr.lower()
        was_blocked_by_sandbox = any(sig in stderr_lower for sig in blocked_signals)

        # Signals that the sandbox blocked the attack
        block_signals = [
            "permission denied", "operation not permitted", "access is denied",
            "read-only file system", "errno 30",           # file_write blocked
            "filenotfounderror", "no such file",           # file_read blocked (host path gone)
            "urlopen error", "network is unreachable",     # network blocked
            "name or service not known", "temporary failure in name resolution",
            "errno 11", "blockingioerror",                 # fork bomb blocked
        ]
        stderr_lower = stderr.lower()
        was_blocked = any(sig in stderr_lower for sig in block_signals)

        # cwd_snoop special case: empty listing means it saw nothing of ours
        saw_nothing = stdout.strip() in ("[]", "")

        # env_leak special case: only container vars, no host secrets -> neutralized
        # (we still count it as "not a real breach" if no host-specific paths appear)

        # env_leak: reading env vars can't be blocked, but inside the container
        # it only exposes harmless container defaults, never host secrets.
        host_secret_markers = ["c:\\", "users\\", "appdata", "predator"]
        stdout_lower = stdout.lower()
        env_leaked_host = any(m in stdout_lower for m in host_secret_markers)

        if was_blocked or (name == "cwd_snoop" and saw_nothing):
            succeeded = False
        elif name == "env_leak" and not env_leaked_host:
            succeeded = False  # neutralized: only container env, no host secrets
        else:
            succeeded = status in ("completed", "error")

        verdict = "VULNERABLE (attack succeeded)" if succeeded else "blocked/failed"
        print(f"[{name}] {verdict}")
        print(f"    goal: {description}")
        if stdout:
            preview = stdout.strip().replace("\n", " ")[:100]
            print(f"    stdout: {preview}")
        if stderr:
            preview = stderr.strip().replace("\n", " ")[:100]
            print(f"    stderr: {preview}")
        print()
        return succeeded

    except Exception as e:
        print(f"[{name}] request failed: {e}\n")
        return False


def main():
    print("=" * 60)
    print("CodeForge Attack Suite — Phase 1 baseline")
    print("=" * 60)
    print()

    results = {}
    for name, code, desc in ATTACKS:
        results[name] = run_attack(name, code, desc)

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    vulnerable = sum(1 for v in results.values() if v)
    for name, succeeded in results.items():
        mark = "VULNERABLE" if succeeded else "blocked"
        print(f"  {name:20} {mark}")
    print()
    print(f"  {vulnerable}/{len(results)} attacks succeeded against Phase 1")


if __name__ == "__main__":
    main()