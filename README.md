# CodeForge

[![CI](https://github.com/josaiahsyiem/CodeForge/actions/workflows/ci.yml/badge.svg)](https://github.com/josaiahsyiem/CodeForge/actions)

**A secure, containerized code execution engine.** CodeForge runs untrusted code — from humans, AI agents, or CI systems — inside hardened, throwaway Docker containers with strict resource limits, then returns the results asynchronously. It supports multiple languages, judges code against test cases, and exposes production-grade auth, rate limiting, and observability.

Built as the secure execution layer for **NLGeo**, an autonomous GeoAI pipeline whose LLM-generated code previously ran in an unisolated subprocess.

---

## Why CodeForge exists

NLGeo is an AI system that writes and executes geospatial analysis code. Its original "sandbox" was a bare `subprocess.run()` — the generated code ran with full filesystem access, full network access, and the same privileges as the API server. If the LLM ever produced hostile or buggy code, nothing contained it.

CodeForge is the fix: a real execution engine that isolates untrusted code at the operating-system level. It was built in deliberate phases, hardening against a fixed suite of attacks at each step.

## Security model

Validated against an automated attack suite (`attacks.py`) run against the live API.

| # | Attack | Phase 1 (subprocess) | Phase 4 (hardened) | How it's blocked |
|---|--------|:---:|:---:|---|
| 1 | Read host system files | 🔴 | ✅ | host filesystem not mounted |
| 2 | Write to filesystem | 🔴 | ✅ | read-only root filesystem |
| 3 | Dump host env / secrets | 🔴 | ✅ | container-only environment |
| 4 | Outbound network calls | 🔴 | ✅ | `network_mode=none` |
| 5 | Read server's own files | 🔴 | ✅ | inline execution, no host mounts |
| 6 | Fork bomb | 🔴 | ✅ | `pids_limit=64` |
| 7 | Memory bomb | 🔴 | ✅ | `mem_limit`, OOM-killed |
| 8 | Infinite loop | 🔴 | ✅ | CPU cap + wall-clock timeout |

🔴 = attack succeeds &nbsp;&nbsp; ✅ = blocked

**Phase 1: 5/5 attacks succeed. Phase 4: 0/5 succeed.** See [`SECURITY.md`](SECURITY.md).

## Architecture

The API never executes code — it queues jobs and returns immediately. Separate worker processes pull jobs, run them in hardened containers, and persist results.

```
POST /jobs  ->  API  ->  Redis queue  ->  Worker  ->  Docker container (hardened)
                                             |
                                             v
                                        PostgreSQL  <-  GET /jobs/{id}

Metrics:  Worker  ->  Prometheus  ->  Grafana
```

## Features

- **Isolated execution** — fresh, hardened, throwaway Docker container per job
- **Async job queue** — Redis-backed queue with a worker pool and graceful shutdown
- **Persistent storage** — PostgreSQL tracks each job through its lifecycle
- **Multi-language** — Python and JavaScript, extensible via a language registry
- **Judge mode** — submit code + test cases, get per-case verdicts with diffs
- **API-key auth** — SHA-256 hashed keys, never stored in plaintext
- **Rate limiting** — per-key token-bucket limiter (lazy refill, thread-safe)
- **Observability** — Prometheus metrics visualized in Grafana
- **Trust-tiered sandboxing** — untrusted code fully locked down; geo workloads get network access but stay isolated

## Tech stack

Python · FastAPI · Docker SDK · Redis · PostgreSQL · Prometheus · Grafana · GitHub Actions

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/jobs` | Submit a job → returns `job_id` |
| `GET` | `/jobs/{job_id}` | Fetch a job's status and result |
| `POST` | `/judge` | Run code against test cases |

All endpoints except `/health` require an `X-API-Key` header.

### Example: submit a job

```bash
curl -X POST http://localhost:8080/jobs \
  -H "X-API-Key: cf_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{"language": "python", "code": "print(2 + 2)", "timeout_seconds": 10}'
# -> {"job_id": "...", "status": "queued"}

curl http://localhost:8080/jobs/{job_id} -H "X-API-Key: cf_your_key_here"
# -> {"status": "completed", "stdout": "4\n", "exit_code": 0, ...}
```

### Example: judge mode

```bash
curl -X POST http://localhost:8080/judge \
  -H "X-API-Key: cf_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "code": "n = int(input())\nprint(n * 2)",
    "test_cases": [
      {"stdin": "5",   "expected_stdout": "10"},
      {"stdin": "100", "expected_stdout": "200"}
    ]
  }'
# -> {"total": 2, "passed": 2, "failed": 0, "results": [...]}
```

## NLGeo integration

CodeForge replaces NLGeo's unsafe subprocess with a call to its hardened sandbox. A live query — *"pharmacies per ward in Mumbai"* — runs its LLM-generated geospatial code through CodeForge and returns a correct, mapped result with a ground-truth spatial correlation of 1.00. See [`INTEGRATION.md`](INTEGRATION.md).

## Running locally

Requires Docker Desktop and Python 3.12+. See [`CodeForge_Complete_Pipeline.md`](CodeForge_Complete_Pipeline.md) for the full phase-by-phase build.

```bash
# 1. Infrastructure (non-default ports to avoid collisions)
docker run -d --name codeforge-redis    -p 6381:6379 redis:7
docker run -d --name codeforge-postgres -e POSTGRES_PASSWORD=codeforge -e POSTGRES_DB=codeforge -p 5434:5432 postgres:17

# 2. Dependencies
pip install fastapi uvicorn docker redis "psycopg[binary]" requests prometheus-client

# 3. Execution images
docker pull python:3.12-slim
docker pull node:22-slim

# 4. Database + API key
python init_db.py
python init_keys.py
python keygen.py "my-key" 60

# 5. Run API and worker (separate terminals)
uvicorn main:app --reload --port 8080
python worker.py
```

Then open the interactive API docs at `http://localhost:8080/docs`.

## Running the attack suite

```bash
python attacks.py
```

Runs the full suite against the live API and prints a pass/block verdict per attack.

## Configuration

Connection settings default to local dev values but can be overridden via environment variables (`REDIS_HOST`, `REDIS_PORT`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`) — used by the CI pipeline.

## Roadmap

- [ ] Compiled-language support (Go, C++, Java)
- [ ] gVisor (`runsc`) runtime benchmark vs. `runc`
- [ ] Azure deployment with HTTPS
- [x] NLGeo integration — secure execution layer for LLM-generated code
- [x] CI pipeline (GitHub Actions)

## Project status

Built in deliberate, documented phases — from a naive unsafe baseline to a hardened, asynchronous, multi-language, observable execution engine, integrated as the secure execution layer for an AI geospatial pipeline. Each phase was tested before advancing, with security regressions caught by the automated attack suite.
