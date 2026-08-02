# CodeForge — Secure Code Execution Engine

## Complete Production Pipeline: Phase 0 to Phase 15

**Language:** Go (primary) · Python, C, JavaScript, Java (executed languages)
**Why Go:** Industry standard for infrastructure tooling (Docker, Kubernetes, Prometheus, Terraform — all Go). Complements NLGeo's Python stack. Goroutines give you real concurrency without threads. Static binary — single file deployment. If you write this in Python, interviewers see "the same language twice." Go says "I pick the right tool for the job."

**Final Stack:** Go · Docker SDK · Redis · PostgreSQL · Prometheus · Grafana · GitHub Actions · Caddy (HTTPS) · Microsoft Azure

**What you're building:** A production-grade service where clients (humans, AI agents, CI pipelines) submit untrusted code over a REST API. The code executes inside locked-down, throwaway Docker containers with strict resource limits. Results return asynchronously via job polling or webhooks. Every execution is logged, metered, and monitored.

**The interview story:** "My first project, NLGeo, is an AI agent that writes and executes geospatial code. I realized it runs LLM-generated code via subprocess with zero isolation — full filesystem and network access. So I built CodeForge: the secure execution layer that agent frameworks need. Then I plugged NLGeo into it."

---

## Phase 0 — Go Foundations

**Goal:** Enough Go fluency to write production services. Don't rush this — every later phase depends on it.

**Duration:** 10–14 days

### What to learn (in this order)

**Week 1: Language basics**
- Go tour (tour.golang.org) — complete all exercises
- Types, structs, interfaces, methods, pointers
- Error handling (Go has no exceptions — errors are values)
- Slices, maps, range loops
- Packages, imports, module system (`go mod init`)
- Write a CLI todo app storing tasks in a JSON file

**Week 2: Concurrency + networking**
- Goroutines and channels — this is Go's superpower
- `sync.WaitGroup`, `sync.Mutex`, `sync.RWMutex`
- `context.Context` — used everywhere for timeouts and cancellation
- `net/http` — build a tiny HTTP server from scratch (no framework)
- JSON marshalling/unmarshalling with struct tags
- Write a concurrent URL health-checker: takes 20 URLs, checks all in parallel, reports status

### Key exercises before moving on

1. Write a program that spawns 10 goroutines, each computing something, and collects results via a channel
2. Write an HTTP server with 3 endpoints that reads/writes JSON
3. Use `context.WithTimeout` to cancel a long-running operation
4. Write a program that uses `os/exec` to run a shell command and capture its output

### Resources
- "A Tour of Go" — official, free
- "Go by Example" (gobyexample.com) — pattern reference
- "Learning Go" by Jon Bodner (O'Reilly) — if you want a book
- Go standard library docs — read `net/http`, `os/exec`, `context`, `encoding/json`

### Exit condition
You can explain goroutines vs threads, what a channel does, and what `context.Context` is for. You can write an HTTP server that handles JSON requests concurrently. You understand Go's error handling philosophy.

---

## Phase 1 — Naive Executor (The Deliberately Unsafe Version)

**Goal:** A working HTTP API that runs code the wrong way. This is your measurable baseline — every improvement in later phases is measured against this.

**Duration:** 3–4 days

### What to build

A single Go binary that:
1. Listens on port 8080
2. Accepts `POST /execute` with JSON body:
```json
{
  "language": "python",
  "code": "print('hello world')",
  "timeout_seconds": 10
}
```
3. Runs the code using `os/exec.CommandContext`
4. Returns JSON:
```json
{
  "stdout": "hello world\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 42,
  "status": "completed"
}
```

### Implementation details

- Use Go's standard `net/http` — no framework (Gin/Echo are fine later, but learn the stdlib first)
- `exec.CommandContext(ctx, "python3", "-c", code)` with a timeout context
- Capture stdout and stderr separately using `cmd.StdoutPipe()` and `cmd.StderrPipe()` (or `bytes.Buffer`)
- Measure duration with `time.Now()` and `time.Since()`
- Handle timeout: if context deadline exceeded, return `"status": "timeout"`
- Handle crash: if exit code != 0, return `"status": "error"` with stderr

### The Attack Suite (CRITICAL — write this now)

Create a test file `attacks_test.go` or a script that sends these payloads:

| # | Attack | Code | What it does |
|---|--------|------|-------------|
| 1 | File read | `import os; print(open('/etc/passwd').read())` | Reads host system files |
| 2 | File write | `open('/tmp/pwned', 'w').write('hacked')` | Writes to host filesystem |
| 3 | Network exfiltration | `import urllib.request; print(urllib.request.urlopen('https://httpbin.org/ip').read())` | Makes outbound network calls |
| 4 | Fork bomb | `import os; [os.fork() for _ in range(100)]` | Spawns unlimited processes |
| 5 | Memory bomb | `x = 'A' * (10**10)` | Allocates 10 GB of memory |
| 6 | Infinite loop | `while True: pass` | Runs forever, hogs CPU |
| 7 | Disk bomb | `open('/tmp/fill','wb').write(b'X'*10**9)` | Fills disk with 1 GB file |
| 8 | Environment leak | `import os; print(dict(os.environ))` | Reads host environment variables (API keys, secrets) |

**Document the results in a table:**

| Attack | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|--------|---------|---------|---------|---------|
| File read | ✅ PASS (unsafe) | | | |
| Network exfil | ✅ PASS (unsafe) | | | |
| Fork bomb | ✅ PASS (unsafe) | | | |
| ... | ... | | | |

"PASS" here means the attack SUCCEEDED — the system is VULNERABLE. By Phase 4, every cell should say "❌ BLOCKED."

This table becomes the single most powerful artifact in your README. It's concrete, visual proof of security engineering.

### Project structure at this point
```
codeforge/
├── cmd/
│   └── server/
│       └── main.go          # entry point
├── internal/
│   ├── api/
│   │   ├── handler.go       # HTTP handlers
│   │   └── router.go        # route setup
│   └── executor/
│       └── naive.go          # os/exec runner
├── pkg/
│   └── models/
│       └── job.go            # request/response structs
├── tests/
│   └── attacks_test.go       # attack suite
├── go.mod
├── go.sum
└── README.md
```

### Exit condition
API runs, accepts code, returns results. All 8 attacks succeed. Attack table documented with evidence (screenshots or test output). You can articulate exactly why this is dangerous.

---

## Phase 2 — Docker Isolation

**Goal:** Every code execution happens inside a throwaway container. The code never touches the host.

**Duration:** 4–5 days

### What changes

Replace `os/exec` with the Docker Go SDK (`github.com/docker/docker/client`).

### Execution lifecycle (per job)

```
1. Create container (from pre-pulled image, e.g. python:3.12-slim)
2. Copy code into container (as a temp file via Docker cp / tar archive)
3. Start container
4. Wait for container to exit (with timeout)
5. Read logs (stdout + stderr)
6. Force-remove container (always, even on error)
```

### Implementation details

- `docker pull` the base images at server startup: `python:3.12-slim`, `node:22-slim`, `golang:1.22-alpine`
- Each execution creates a NEW container — never reuse. The container is destroyed after every run.
- No volume mounts from host — the container cannot see the host filesystem
- Use `container.Wait()` with a context timeout for wall-clock limits
- Use `container.Logs()` to read stdout/stderr after completion
- Wrap everything in a `defer` to guarantee container removal even if something panics
- Create a `DockerExecutor` struct that implements the same interface as `NaiveExecutor` — makes swapping clean

### Container config
```go
containerConfig := &container.Config{
    Image: "python:3.12-slim",
    Cmd:   []string{"python3", "/tmp/code.py"},
    // No env vars from host
    // No exposed ports
}

hostConfig := &container.HostConfig{
    // No volume binds
    // No privileged mode
    AutoRemove: false, // we remove manually after reading logs
}
```

### Code injection into container
Use the Docker SDK's `CopyToContainer` to create a tar archive containing the user's code file and stream it into the container before starting it.

### Update the attack table

| Attack | Phase 1 | Phase 2 |
|--------|---------|---------|
| File read (/etc/passwd) | ✅ PASS | ❌ BLOCKED (reads container's /etc/passwd, not host's) |
| File write | ✅ PASS | ❌ BLOCKED (writes inside container, destroyed after) |
| Environment leak | ✅ PASS | ❌ BLOCKED (container has no host env vars) |
| Network exfil | ✅ PASS | ⚠️ STILL PASSES (container has network by default) |
| Fork bomb | ✅ PASS | ⚠️ STILL PASSES (no PID limit yet) |
| Memory bomb | ✅ PASS | ⚠️ STILL PASSES (no memory limit yet) |

Some attacks are now blocked, others still pass. That's expected — Phases 3 and 4 close the remaining gaps.

### Exit condition
Code executes inside Docker containers. Host filesystem is no longer accessible. Container is created and destroyed per job. File read/write/env-leak attacks fail.

---

## Phase 3 — Resource Limits & Kill Switches

**Goal:** No submitted code can starve the host machine of CPU, memory, PIDs, disk, or time.

**Duration:** 3–4 days

### Resource controls (all via Docker HostConfig)

**CPU limit:**
```go
hostConfig := &container.HostConfig{
    Resources: container.Resources{
        NanoCPUs: 1_000_000_000, // 1 CPU core
    },
}
```

**Memory limit (with swap disabled):**
```go
Resources: container.Resources{
    Memory:     256 * 1024 * 1024, // 256 MB
    MemorySwap: 256 * 1024 * 1024, // same as Memory = swap disabled
}
```

**PID limit (kills fork bombs):**
```go
Resources: container.Resources{
    PidsLimit: int64Ptr(64), // max 64 processes
}
```

**Disk limit (tmpfs with size cap):**
```go
hostConfig := &container.HostConfig{
    Tmpfs: map[string]string{
        "/tmp": "size=50m", // 50 MB writable space, in memory
    },
}
// Also make root filesystem read-only (Phase 4)
```

**Wall-clock timeout:**
```go
ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
// If container doesn't finish in 30s, force kill it
```

**Output cap:**
When reading container logs, truncate after 64 KB. This prevents a `print('A' * 10**9)` from consuming all your server memory.

```go
limitedReader := io.LimitReader(logReader, 64*1024) // 64 KB max
```

### Status codes for resource violations

Map container exit codes and OOM events to user-friendly statuses:
- Exit code 137 (SIGKILL) + OOM flag → `"status": "memory_limit_exceeded"`
- Context deadline exceeded → `"status": "time_limit_exceeded"`
- Exit code 137 without OOM (likely PID limit) → `"status": "process_limit_exceeded"`
- Normal exit code 0 → `"status": "completed"`
- Any other non-zero exit → `"status": "runtime_error"`

### Update the attack table

| Attack | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|
| Fork bomb | ✅ PASS | ⚠️ PASS | ❌ BLOCKED (PID limit: 64) |
| Memory bomb | ✅ PASS | ⚠️ PASS | ❌ BLOCKED (256 MB limit, killed with OOM) |
| Infinite loop | ✅ PASS | ⚠️ PASS | ❌ BLOCKED (30s timeout, force killed) |
| Disk bomb | ✅ PASS | ⚠️ PASS | ❌ BLOCKED (tmpfs 50 MB cap) |
| Network exfil | ✅ PASS | ⚠️ PASS | ⚠️ STILL PASSES |

### Exit condition
Fork bomb, memory bomb, infinite loop, and disk bomb all die cleanly with descriptive error messages. Host stays healthy under attack. One attack remains: network exfiltration (fixed in Phase 4).

---

## Phase 4 — Security Hardening

**Goal:** Defense in depth. Close every remaining attack vector. This phase impresses infra interviewers the most.

**Duration:** 4–5 days

### Network isolation
```go
hostConfig := &container.HostConfig{
    NetworkMode: "none", // no network interface at all
}
```
Network exfiltration attack now fails. The container has no network stack — it can't even resolve DNS.

### Run as non-root
```go
containerConfig := &container.Config{
    User: "65534:65534", // nobody:nogroup
}
```

### Read-only root filesystem
```go
hostConfig := &container.HostConfig{
    ReadonlyRootfs: true,
    Tmpfs: map[string]string{
        "/tmp": "size=50m,noexec", // writable scratch space, but no executables
    },
}
```
Note: some languages need a writable `/tmp` for temp files. The tmpfs provides this without allowing writes to the actual filesystem.

### Drop all Linux capabilities
```go
hostConfig := &container.HostConfig{
    CapDrop: []string{"ALL"}, // drop every Linux capability
}
```
This removes the ability to: change file ownership, bind to privileged ports, load kernel modules, modify the network stack, use raw sockets, trace processes, etc.

### No new privileges
```go
hostConfig := &container.HostConfig{
    SecurityOpt: []string{"no-new-privileges"},
}
```
Prevents the code from escalating privileges via setuid binaries or other mechanisms.

### Optional: seccomp profile
Docker applies a default seccomp profile that blocks ~44 dangerous syscalls. You can make it stricter:
```go
hostConfig := &container.HostConfig{
    SecurityOpt: []string{
        "no-new-privileges",
        "seccomp=/path/to/custom-seccomp.json",
    },
}
```
The default profile is already good. A custom one that additionally blocks `ptrace`, `mount`, `reboot`, etc. is a nice extra.

### Optional stretch goal: gVisor (runsc) runtime
gVisor is Google's application kernel that intercepts all syscalls. It provides stronger isolation than default Docker (which shares the host kernel).

```go
hostConfig := &container.HostConfig{
    Runtime: "runsc", // use gVisor instead of runc
}
```

If you add this: benchmark the same workload under `runc` vs `runsc`, measure the latency overhead, and write up the tradeoff. This is extremely strong interview material — almost nobody at resume-project level touches container runtimes.

### The complete HostConfig at this point
```go
hostConfig := &container.HostConfig{
    NetworkMode:    "none",
    ReadonlyRootfs: true,
    CapDrop:        []string{"ALL"},
    SecurityOpt:    []string{"no-new-privileges"},
    Tmpfs: map[string]string{
        "/tmp": "size=50m",
    },
    Resources: container.Resources{
        NanoCPUs:  1_000_000_000,
        Memory:    256 * 1024 * 1024,
        MemorySwap: 256 * 1024 * 1024,
        PidsLimit: int64Ptr(64),
    },
}
```

### Final attack table

| Attack | Phase 1 (subprocess) | Phase 2 (Docker) | Phase 3 (limits) | Phase 4 (hardened) |
|--------|----------------------|-------------------|-------------------|---------------------|
| File read | ✅ PASS | ❌ BLOCKED | ❌ BLOCKED | ❌ BLOCKED |
| File write | ✅ PASS | ❌ BLOCKED | ❌ BLOCKED | ❌ BLOCKED (read-only FS) |
| Network exfil | ✅ PASS | ⚠️ PASS | ⚠️ PASS | ❌ BLOCKED (no network) |
| Fork bomb | ✅ PASS | ⚠️ PASS | ❌ BLOCKED | ❌ BLOCKED |
| Memory bomb | ✅ PASS | ⚠️ PASS | ❌ BLOCKED | ❌ BLOCKED |
| Infinite loop | ✅ PASS | ⚠️ PASS | ❌ BLOCKED | ❌ BLOCKED |
| Disk bomb | ✅ PASS | ⚠️ PASS | ❌ BLOCKED | ❌ BLOCKED |
| Env leak | ✅ PASS | ❌ BLOCKED | ❌ BLOCKED | ❌ BLOCKED |

**Every attack blocked. This table goes in the README.**

### Exit condition
All 8 attacks fail. Container runs as non-root with no capabilities, no network, read-only filesystem, strict resource limits. You can explain every security layer and why it exists.

---

## Phase 5 — Async Job Queue + Worker Pool

**Goal:** The API no longer blocks on execution. Jobs are queued and processed by a pool of workers — the same architectural leap NLGeo made with Celery, but here you build the worker logic yourself in Go.

**Duration:** 5–6 days

### Architecture change

Before (Phases 1–4): `POST /execute` → run code → wait → return result (synchronous)

After: `POST /jobs` → enqueue → return job ID instantly (async)
       `GET /jobs/{id}` → poll for result

### Components

**API server (cmd/server/main.go):**
- `POST /jobs` — validates input, generates UUID, pushes to Redis queue, returns `{"job_id": "uuid", "status": "queued"}`
- `GET /jobs/{id}` — looks up job in Postgres, returns current status + result if complete
- `GET /health` — liveness check
- `GET /metrics` — Prometheus metrics (Phase 10)

**Worker (cmd/worker/main.go):**
- Separate binary
- Starts N goroutines (configurable, default 4)
- Each goroutine: `BRPOP` from Redis → deserialize job → run through Phase 2–4 executor → write result to Postgres → loop
- Graceful shutdown: on SIGTERM/SIGINT, stop accepting new jobs, let current jobs finish (with a deadline), then exit

### Redis as the queue

Use `github.com/redis/go-redis/v9`.

```go
// Enqueue (API side)
jobJSON, _ := json.Marshal(job)
rdb.LPush(ctx, "codeforge:jobs", jobJSON)

// Dequeue (worker side)
result, err := rdb.BRPop(ctx, 0, "codeforge:jobs").Result()
// BRPop blocks until a job is available — no busy-waiting, no polling
```

Why Redis and not a Go channel? Because the API and workers are separate processes (separate binaries, separate containers in production). You can scale workers independently.

### PostgreSQL for job persistence

Table schema:
```sql
CREATE TABLE jobs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    language      VARCHAR(20) NOT NULL,
    code_hash     VARCHAR(64) NOT NULL,  -- SHA-256 of submitted code
    status        VARCHAR(20) NOT NULL DEFAULT 'queued',
    -- status: queued → running → completed | failed | timeout | memory_limit_exceeded | ...
    stdout        TEXT,
    stderr        TEXT,
    exit_code     INTEGER,
    duration_ms   INTEGER,
    worker_id     VARCHAR(50),           -- which worker picked it up
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    started_at    TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ
);

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created ON jobs(created_at);
```

### Worker lifecycle

```
┌──────────┐     ┌─────────┐     ┌──────────────┐     ┌──────────────┐
│ API:     │────▶│  Redis   │────▶│   Worker     │────▶│  PostgreSQL  │
│ POST /jobs│    │  Queue   │    │  goroutine   │    │  results     │
└──────────┘     └─────────┘     └──────────────┘     └──────────────┘
                                       │
                                       ▼
                                 ┌──────────────┐
                                 │   Docker      │
                                 │   container   │
                                 └──────────────┘
```

### Worker pool in Go

```go
func startWorkerPool(ctx context.Context, n int, rdb *redis.Client, db *pgxpool.Pool, docker *client.Client) {
    var wg sync.WaitGroup
    for i := 0; i < n; i++ {
        wg.Add(1)
        go func(workerID int) {
            defer wg.Done()
            workerLoop(ctx, workerID, rdb, db, docker)
        }(i)
    }
    wg.Wait()
}

func workerLoop(ctx context.Context, id int, rdb *redis.Client, db *pgxpool.Pool, docker *client.Client) {
    for {
        select {
        case <-ctx.Done():
            log.Printf("Worker %d shutting down gracefully", id)
            return
        default:
            // BRPOP with 5s timeout so we periodically check ctx.Done()
            result, err := rdb.BRPop(ctx, 5*time.Second, "codeforge:jobs").Result()
            if err != nil {
                continue // timeout or context cancelled
            }
            processJob(ctx, id, result[1], db, docker)
        }
    }
}
```

### Graceful shutdown

```go
sigChan := make(chan os.Signal, 1)
signal.Notify(sigChan, syscall.SIGTERM, syscall.SIGINT)
<-sigChan
log.Println("Shutdown signal received, finishing current jobs...")
cancel() // cancel the context — workers stop accepting new jobs
// wg.Wait() ensures current jobs finish
// Then exit cleanly
```

This is an interview goldmine: "How does your service handle shutdown?" → you explain signal handling, context cancellation, and WaitGroup draining.

### Concurrency test

Submit 100 jobs simultaneously:
```bash
for i in $(seq 1 100); do
  curl -s -X POST localhost:8080/jobs \
    -H 'Content-Type: application/json' \
    -d '{"language":"python","code":"import time; time.sleep(1); print('$i')"}' &
done
wait
```
All 100 should complete. API should remain responsive throughout. Workers should process 4 at a time (with 4 goroutines).

### Exit condition
Jobs are processed asynchronously. API returns instantly. Workers pull from Redis and write results to Postgres. 100 concurrent submissions all complete. Graceful shutdown works cleanly.

---

## Phase 6 — API Authentication & Rate Limiting

**Goal:** Production API behavior — no anonymous access, no abuse.

**Duration:** 4–5 days

### API key system

Table:
```sql
CREATE TABLE api_keys (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash   VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 of the API key
    name       VARCHAR(100) NOT NULL,        -- "NLGeo production", "test key"
    rate_limit INT NOT NULL DEFAULT 60,      -- requests per minute
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_active  BOOLEAN DEFAULT TRUE
);
```

Generate keys via a CLI command:
```bash
./codeforge keygen --name "NLGeo production" --rate-limit 120
# Output: API key: cf_live_a1b2c3d4e5f6... (store this, shown once)
```

Store only the SHA-256 hash — never store the raw key.

### Authentication middleware

```go
func authMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        key := r.Header.Get("X-API-Key")
        if key == "" {
            http.Error(w, `{"error":"missing API key"}`, 401)
            return
        }
        hash := sha256Hex(key)
        apiKey, err := db.LookupKeyHash(hash)
        if err != nil || !apiKey.IsActive {
            http.Error(w, `{"error":"invalid API key"}`, 401)
            return
        }
        ctx := context.WithValue(r.Context(), "api_key", apiKey)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```

### Token bucket rate limiter (implement yourself — classic interview topic)

Don't use a library. Implement the token bucket algorithm:

```go
type TokenBucket struct {
    mu         sync.Mutex
    tokens     float64
    maxTokens  float64
    refillRate float64   // tokens per second
    lastRefill time.Time
}

func (tb *TokenBucket) Allow() bool {
    tb.mu.Lock()
    defer tb.mu.Unlock()
    
    now := time.Now()
    elapsed := now.Sub(tb.lastRefill).Seconds()
    tb.tokens = min(tb.maxTokens, tb.tokens + elapsed*tb.refillRate)
    tb.lastRefill = now
    
    if tb.tokens >= 1 {
        tb.tokens--
        return true
    }
    return false
}
```

One bucket per API key, stored in a `sync.Map`. When `Allow()` returns false:
```json
{
    "error": "rate limit exceeded",
    "retry_after_seconds": 3
}
```
Return HTTP 429 with `Retry-After` header.

### Input validation

- `language`: must be one of `["python", "javascript", "go", "c", "cpp", "java"]`
- `code`: max 64 KB
- `timeout_seconds`: 1–60, default 10
- Request body: max 128 KB total
- Return 400 with descriptive errors for invalid input

### Consistent error format

Every error response follows the same shape:
```json
{
    "error": "human readable message",
    "code": "RATE_LIMIT_EXCEEDED",
    "details": {}
}
```

### Exit condition
Unauthenticated requests get 401. Rate-limited requests get 429 with retry-after. Invalid input gets 400 with clear messages. Rate limiter is your own implementation, not a library.

---

## Phase 7 — Multi-Language Support

**Goal:** Support Python, JavaScript, Go, C, C++, and Java. Compiled languages need a compile-then-run flow inside the container.

**Duration:** 4–5 days

### Language registry

```go
type LanguageConfig struct {
    Image      string   // Docker image
    Extension  string   // file extension
    Compile    []string // compile command (nil for interpreted)
    Run        []string // run command
    ArtifactPath string // path to compiled binary (for compiled langs)
}

var languages = map[string]LanguageConfig{
    "python": {
        Image:     "python:3.12-slim",
        Extension: ".py",
        Run:       []string{"python3", "/sandbox/code.py"},
    },
    "javascript": {
        Image:     "node:22-slim",
        Extension: ".js",
        Run:       []string{"node", "/sandbox/code.js"},
    },
    "go": {
        Image:     "golang:1.22-alpine",
        Extension: ".go",
        Compile:   []string{"go", "build", "-o", "/sandbox/code", "/sandbox/code.go"},
        Run:       []string{"/sandbox/code"},
    },
    "c": {
        Image:     "gcc:14",
        Extension: ".c",
        Compile:   []string{"gcc", "-o", "/sandbox/code", "/sandbox/code.c", "-lm"},
        Run:       []string{"/sandbox/code"},
    },
    "cpp": {
        Image:     "gcc:14",
        Extension: ".cpp",
        Compile:   []string{"g++", "-o", "/sandbox/code", "/sandbox/code.cpp", "-lm", "-std=c++20"},
        Run:       []string{"/sandbox/code"},
    },
    "java": {
        Image:     "eclipse-temurin:21-jdk",
        Extension: ".java",
        Compile:   []string{"javac", "/sandbox/Code.java"},
        Run:       []string{"java", "-cp", "/sandbox", "Code"},
    },
}
```

### Two-stage execution for compiled languages

```
1. Create container
2. Copy code file in
3. If compile step exists:
   a. Run compile command
   b. If compile fails → return "compilation_error" with compiler stderr
   c. If compile succeeds → continue
4. Run the binary/script
5. Capture output
6. Remove container
```

This means compiled languages have TWO commands executed inside the same container. Use `docker exec` for the second command after the first succeeds, or chain them: `sh -c "gcc code.c -o code && ./code"`.

### Stdin support (for judge mode later)

Add an optional `stdin` field to the request:
```json
{
    "language": "python",
    "code": "n = int(input()); print(n * 2)",
    "stdin": "21"
}
```
Pipe stdin into the container via Docker's attach/stdin stream.

### Pre-pull images at startup

```go
func prePullImages(ctx context.Context, cli *client.Client) error {
    images := []string{"python:3.12-slim", "node:22-slim", "golang:1.22-alpine", "gcc:14", "eclipse-temurin:21-jdk"}
    for _, img := range images {
        reader, err := cli.ImagePull(ctx, img, image.PullOptions{})
        if err != nil { return err }
        io.Copy(io.Discard, reader) // consume the pull output
        reader.Close()
    }
    return nil
}
```

### Exit condition
The same problem solved in all 6 languages, all returning correct output. Compilation errors return clear error messages. Stdin works for interactive programs.

---

## Phase 8 — Judge Mode (Test Runner)

**Goal:** Submit code + test cases → engine returns pass/fail per case. This is what makes it a mini-LeetCode/Judge0, not just a code runner.

**Duration:** 4–5 days

### API

```
POST /judge
{
    "language": "python",
    "code": "def solve(n): return n * 2\nprint(solve(int(input())))",
    "test_cases": [
        {"stdin": "5",  "expected_stdout": "10"},
        {"stdin": "0",  "expected_stdout": "0"},
        {"stdin": "-3", "expected_stdout": "-6"},
        {"stdin": "1000000", "expected_stdout": "2000000"}
    ],
    "timeout_per_case_seconds": 5
}
```

### Response

```json
{
    "job_id": "uuid",
    "status": "completed",
    "summary": {
        "total": 4,
        "passed": 3,
        "failed": 1,
        "duration_ms": 847
    },
    "results": [
        {"case": 1, "status": "passed", "duration_ms": 42},
        {"case": 2, "status": "passed", "duration_ms": 38},
        {"case": 3, "status": "wrong_answer",
         "expected": "-6", "actual": "6",
         "duration_ms": 41},
        {"case": 4, "status": "passed", "duration_ms": 39}
    ]
}
```

### Implementation options

**Option A (simple, slower):** Run a fresh container per test case. Clean but has container startup overhead (200–500ms) multiplied by N cases.

**Option B (optimized, recommended):** Compile once, then run multiple times in the same container using `docker exec` for each case. Same isolation (the container is still sandboxed), much faster.

**Option C (most optimized):** Build a wrapper script that reads all test cases from a JSON file, runs the solution for each, and outputs a JSON result. One container, one execution. This is how real judges work.

Go with Option B or C.

### Statuses per test case
- `passed` — stdout matches expected (after trimming whitespace)
- `wrong_answer` — stdout doesn't match
- `runtime_error` — non-zero exit code
- `time_limit_exceeded` — case exceeded timeout
- `memory_limit_exceeded` — OOM kill during this case
- `compilation_error` — compile failed (returned once, not per case)

### Exit condition
Judge mode correctly evaluates multiple test cases. Wrong answers, TLEs, and runtime errors are distinguished. Compilation happens once, not per case.

---

## Phase 9 — Observability (Prometheus + Grafana)

**Goal:** Production-grade monitoring. Mirror NLGeo's observability stack but in Go.

**Duration:** 3–4 days

### Prometheus metrics

Use `github.com/prometheus/client_golang`.

```go
var (
    jobsTotal = prometheus.NewCounterVec(
        prometheus.CounterOpts{Name: "codeforge_jobs_total", Help: "Total jobs processed"},
        []string{"language", "status"}, // labels
    )
    jobDuration = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "codeforge_job_duration_seconds",
            Help:    "Job execution duration",
            Buckets: []float64{0.1, 0.5, 1, 2, 5, 10, 30, 60},
        },
        []string{"language"},
    )
    queueDepth = prometheus.NewGauge(
        prometheus.GaugeOpts{Name: "codeforge_queue_depth", Help: "Jobs waiting in queue"},
    )
    activeWorkers = prometheus.NewGauge(
        prometheus.GaugeOpts{Name: "codeforge_active_workers", Help: "Workers currently executing a job"},
    )
    containerStartup = prometheus.NewHistogram(
        prometheus.HistogramOpts{
            Name:    "codeforge_container_startup_seconds",
            Help:    "Time to create and start a container",
            Buckets: []float64{0.05, 0.1, 0.2, 0.5, 1, 2},
        },
    )
    rateLimitHits = prometheus.NewCounterVec(
        prometheus.CounterOpts{Name: "codeforge_rate_limit_hits_total"},
        []string{"api_key_name"},
    )
)
```

Expose on `GET /metrics` — Prometheus scrapes this endpoint every 15 seconds.

### Grafana dashboard

Create a JSON dashboard with panels for:
1. Jobs/minute by language (stacked bar chart)
2. Job duration p50/p95/p99 (heatmap or line chart)
3. Queue depth over time
4. Active workers gauge
5. Error rate by type (timeout, OOM, runtime error)
6. Container startup latency
7. Rate limit hits

### Structured logging

Use `log/slog` (Go 1.21+ standard library):

```go
slog.Info("job completed",
    "job_id", job.ID,
    "language", job.Language,
    "status", result.Status,
    "duration_ms", result.DurationMs,
    "worker_id", workerID,
)
```

JSON-formatted logs with consistent fields. Every log line includes `job_id` for tracing a job through the system.

### Health endpoint

```go
GET /health
{
    "status": "healthy",
    "docker": "connected",
    "redis": "connected",
    "postgres": "connected",
    "workers_active": 3,
    "queue_depth": 12,
    "uptime_seconds": 84321
}
```

### Exit condition
`/metrics` returns valid Prometheus exposition format. Grafana dashboard shows live data during a load test. Logs are structured JSON with job IDs throughout. Health endpoint reports service status.

---

## Phase 10 — Testing & Benchmarks

**Goal:** Numbers for the README and resume. Proof that it works and how well it performs.

**Duration:** 4–5 days

### Test layers

**Unit tests (internal logic):**
- Token bucket rate limiter: test refill timing, concurrent access, burst handling
- Language config validation: all images exist, compile commands are valid
- Job status transitions: queued → running → completed, no invalid transitions
- Input validation: all rejection cases covered
- Output truncation: verify 64 KB cap works correctly

**Integration tests (with real Docker):**
- Submit job → poll → get correct output (per language)
- Submit attack suite → all blocked
- Submit compilation error → get descriptive error
- Submit with stdin → correct output
- Judge mode → correct pass/fail per case
- Rate limiting → 429 on exceeded
- Auth → 401 on invalid key

**Load testing:**

Use `vegeta` (Go load testing tool) or `k6`:

```bash
# Sustained load: 10 requests/second for 60 seconds
echo 'POST http://localhost:8080/jobs
Content-Type: application/json
X-API-Key: your-key-here
@body.json' | vegeta attack -rate=10/s -duration=60s | vegeta report
```

### Benchmark table (for README)

Run these benchmarks and record real numbers:

| Metric | Value |
|--------|-------|
| Container cold start (create + start) | ___ms |
| Python hello-world end-to-end | ___ms |
| Go compile + run end-to-end | ___ms |
| Max throughput (1 worker) | ___jobs/min |
| Max throughput (4 workers) | ___jobs/min |
| Max throughput (8 workers) | ___jobs/min |
| p50 latency at 10 req/s | ___ms |
| p95 latency at 10 req/s | ___ms |
| p99 latency at 10 req/s | ___ms |
| Memory per container | ___MB |
| Queue drain time (100 jobs, 4 workers) | ___s |

### Attack suite as automated regression

```go
func TestAttackSuite(t *testing.T) {
    attacks := []struct{
        name     string
        code     string
        expectBlocked bool
    }{
        {"file_read", "print(open('/etc/passwd').read())", true},
        {"network_exfil", "import urllib.request; ...", true},
        {"fork_bomb", "import os; [os.fork() for _ in range(100)]", true},
        // ... all 8
    }
    for _, a := range attacks {
        t.Run(a.name, func(t *testing.T) {
            result := submitAndWait(a.code)
            if a.expectBlocked {
                assert(t, result.Status != "completed", "attack should be blocked")
            }
        })
    }
}
```

Run this in CI — if any attack starts passing again (due to a config change), the build breaks.

### Exit condition
All tests pass. Load test runs without failures. Benchmark table filled with real numbers. Attack suite runs as automated regression.

---

## Phase 11 — CI/CD Pipeline

**Goal:** Professional development workflow. NLGeo doesn't have this — new signal on your resume.

**Duration:** 2–3 days

### GitHub Actions workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: '1.22'
      - name: golangci-lint
        uses: golangci/golangci-lint-action@v6

  test:
    runs-on: ubuntu-latest
    needs: lint
    services:
      redis:
        image: redis:7-alpine
        ports: ['6379:6379']
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: codeforge_test
          POSTGRES_PASSWORD: test
        ports: ['5432:5432']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: '1.22'
      - name: Run unit tests
        run: go test ./... -v -count=1
      - name: Run integration tests
        run: go test ./tests/integration/... -v -tags=integration

  build:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker images
        run: |
          docker build -t codeforge-api -f Dockerfile.api .
          docker build -t codeforge-worker -f Dockerfile.worker .
```

### Dockerfiles

```dockerfile
# Dockerfile.api
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /codeforge-api ./cmd/server

FROM alpine:3.20
RUN apk --no-cache add ca-certificates
COPY --from=builder /codeforge-api /usr/local/bin/
EXPOSE 8080
CMD ["codeforge-api"]
```

Multi-stage build: compile in a Go image, run in a tiny Alpine image. Final image is ~15 MB instead of 800+ MB.

### docker-compose.yml

```yaml
version: '3.8'
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8080:8080"
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgres://codeforge:secret@postgres:5432/codeforge
      - DOCKER_HOST=unix:///var/run/docker.sock
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock  # API needs Docker to check health
    depends_on:
      - redis
      - postgres

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgres://codeforge:secret@postgres:5432/codeforge
      - DOCKER_HOST=unix:///var/run/docker.sock
      - WORKER_POOL_SIZE=4
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock  # worker creates containers
    depends_on:
      - redis
      - postgres
    deploy:
      replicas: 1  # scale with: docker compose up --scale worker=3

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: codeforge
      POSTGRES_PASSWORD: secret
    volumes:
      - pg_data:/var/lib/postgresql/data

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=codeforge123

volumes:
  redis_data:
  pg_data:
```

### Badge on README

```markdown
[![CI](https://github.com/yourusername/codeforge/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/codeforge/actions)
```

Green badge = confidence signal for anyone visiting your repo.

### Exit condition
Every push runs lint + test + build. Broken tests block merge. Green badge on repo. Docker images build cleanly.

---

## Phase 12 — Azure Deployment

**Goal:** Live public URL. Same playbook as NLGeo, upgraded with HTTPS.

**Duration:** 3–4 days

### VM setup

- Same as NLGeo: Standard_B2s_v2 (2 vCPU / 8 GB), Central India, Debian 12
- Or reuse the same VM if credits allow — run both projects on one machine
- NSG inbound rules: 22 (SSH), 80 (HTTP→redirect), 443 (HTTPS), 3000 (Grafana)

### Deployment steps

1. SSH into VM
2. Install Docker + Docker Compose
3. Clone repo
4. `docker compose up -d`
5. Pre-pull execution images: `docker pull python:3.12-slim && docker pull node:22-slim && ...`
6. Generate an API key: `docker exec codeforge-api codeforge keygen --name "public-demo"`

### HTTPS with Caddy (upgrade over NLGeo's plain HTTP)

If you have a domain:
```
# Caddyfile
yourdomain.com {
    reverse_proxy api:8080
}
grafana.yourdomain.com {
    reverse_proxy grafana:3000
}
```
Caddy auto-provisions Let's Encrypt TLS certificates. Zero configuration HTTPS.

If no domain (like NLGeo's IP-only setup): use self-signed cert or serve on HTTP — still an improvement to document.

### Verified on Azure

Run the attack suite against the live deployment. Run the benchmark suite. Add "Azure verified" column to the tables, same as NLGeo does.

### Deallocate between sessions

Same as NLGeo — stop the VM when not in use to conserve student credits.

### Exit condition
Public URL executes code safely. Attack suite passes on Azure. Grafana dashboard accessible. Deallocate/restart procedure documented.

---

## Phase 13 — Capstone: Power NLGeo with CodeForge

**Goal:** The two projects become one connected story. Replace NLGeo's unsafe subprocess with a call to your own engine.

**Duration:** 3–4 days

### What changes in NLGeo

In NLGeo's `agents/analysis_agent.py`, the LLM-generated code currently runs via:
```python
result = subprocess.run(
    ["python3", code_path],
    capture_output=True, timeout=120, text=True
)
```

Replace with:
```python
import requests

def execute_sandboxed(code: str, timeout: int = 60) -> dict:
    response = requests.post(
        "http://localhost:8080/jobs",  # or Azure URL
        headers={"X-API-Key": os.environ["CODEFORGE_API_KEY"]},
        json={
            "language": "python",
            "code": code,
            "timeout_seconds": timeout
        }
    )
    job_id = response.json()["job_id"]
    
    # Poll for result
    while True:
        status = requests.get(f"http://localhost:8080/jobs/{job_id}",
                             headers={"X-API-Key": os.environ["CODEFORGE_API_KEY"]})
        result = status.json()
        if result["status"] not in ("queued", "running"):
            return result
        time.sleep(0.5)
```

### Custom Python image for geo workloads

NLGeo's generated code needs `geopandas`, `shapely`, `rasterio`, etc. Create a custom Docker image:

```dockerfile
# images/python-geo/Dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y libgdal-dev libgeos-dev libproj-dev && \
    pip install --no-cache-dir geopandas shapely rasterio rasterstats osmnx pandas numpy scipy && \
    apt-get clean
```

Register it in CodeForge as a new language variant:
```go
"python-geo": {
    Image:     "codeforge/python-geo:latest",
    Extension: ".py",
    Run:       []string{"python3", "/sandbox/code.py"},
},
```

### Before/after writeup

Document in the README:
- **Before:** NLGeo runs LLM-generated code via subprocess. If the LLM generates `import os; os.system('rm -rf /')`, nothing stops it. The code has full filesystem access, network access, and runs as the same user as the API server.
- **After:** LLM-generated code runs inside a CodeForge container with no network, no host filesystem access, read-only rootfs, non-root user, 256 MB memory cap, 30-second timeout.
- **Latency cost:** ___ms overhead per execution (container startup). Measure with the Mumbai flood benchmark.

### End-to-end verification

Run NLGeo's Mumbai flood benchmark through CodeForge:
- Query: "Which Mumbai wards have the highest flood-exposed population?"
- Pipeline: NLGeo decomposes → retrieves data → LLM generates analysis code → **CodeForge executes it safely** → result returns → Spearman correlation 1.0

That's the proof that the integration works. Screenshot it. Include it in both READMEs.

### Architecture diagram showing both systems

```
User query
    │
    ▼
┌─────────────────────────────────────────────┐
│  NLGeo                                       │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Decompose│─▶│ Retrieve │─▶│ Generate  │  │
│  │ (LLM)    │  │ (Overpass)│  │ Code (LLM)│  │
│  └──────────┘  └──────────┘  └─────┬─────┘  │
│                                     │        │
│                                     ▼        │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Return   │◀─│ Evaluate │◀─│ CodeForge │◀─┼─── code sent via API
│  │ Map      │  │ (LLM)    │  │ (execute) │  │
│  └──────────┘  └──────────┘  └───────────┘  │
└─────────────────────────────────────────────┘
                                     │
                                     ▼
                        ┌─────────────────────┐
                        │  CodeForge Engine     │
                        │  ┌─────┐ ┌────────┐  │
                        │  │Redis│ │Workers │  │
                        │  │Queue│─▶│(Docker)│  │
                        │  └─────┘ └────────┘  │
                        │  ┌─────┐ ┌────────┐  │
                        │  │Prom.│ │Postgres│  │
                        │  └─────┘ └────────┘  │
                        └─────────────────────┘
```

### Exit condition
Mumbai flood benchmark passes end-to-end through CodeForge. Spearman correlation still 1.0. Latency overhead measured and documented. Architecture diagram in README shows both systems.

---

## Phase 14 — Webhooks & Streaming (Production Polish)

**Goal:** Real-world integration patterns beyond simple polling.

**Duration:** 3–4 days

### Webhook callbacks

Instead of polling `GET /jobs/{id}`, clients can provide a callback URL:

```json
POST /jobs
{
    "language": "python",
    "code": "print(42)",
    "webhook_url": "https://your-app.com/callbacks/codeforge"
}
```

When the job completes, CodeForge sends a POST to the webhook URL with the result. The client doesn't need to poll.

Implementation: after the worker writes the result to Postgres, it checks if `webhook_url` is set and sends an HTTP POST. Retry 3 times with exponential backoff on failure.

### Server-Sent Events (SSE) for real-time status

```
GET /jobs/{id}/stream
```

Returns an SSE stream:
```
data: {"status": "queued", "position": 3}

data: {"status": "running", "worker_id": "worker-2"}

data: {"status": "completed", "stdout": "42\n", "duration_ms": 156}
```

This is how a frontend would show live execution status without polling.

### Job expiry and cleanup

- Jobs older than 24 hours: soft-delete from Postgres (mark as expired)
- Jobs older than 7 days: hard-delete
- Orphan containers (worker crashed mid-execution): periodic cleanup goroutine that finds and removes containers with a `codeforge-` prefix that have been running too long
- Run this cleanup every 5 minutes in a background goroutine

### Exit condition
Webhooks fire correctly on job completion. SSE stream delivers real-time updates. Old jobs are cleaned up automatically. Orphan containers are detected and removed.

---

## Phase 15 — README, Demo, and Presentation

**Goal:** Make everything you built visible and compelling.

**Duration:** 2–3 days

### README structure

```markdown
# CodeForge — Secure Code Execution Engine

One-line description + badges (CI, Go version, license)

## What is this?
2–3 sentences. Link to NLGeo. The security motivation.

## Architecture
Diagram showing API → Redis → Workers → Docker → Postgres

## Security Model
The attack before/after table (Phase 4). This is the hero section.

## Supported Languages
Table: Python, JavaScript, Go, C, C++, Java

## API Reference
POST /jobs, GET /jobs/{id}, POST /judge, GET /health, GET /metrics
With curl examples for each.

## Benchmarks
The performance table from Phase 10.

## NLGeo Integration
Before/after diagram. Mumbai benchmark proof.

## Quick Start
docker compose up -d + one curl command to run code.

## Deployment
Azure setup notes.

## Tech Stack
Go, Docker SDK, Redis, PostgreSQL, Prometheus, Grafana, Caddy, GitHub Actions, Azure
```

### Demo video (2–3 minutes)

1. Show the API accepting code (curl or Postman)
2. Show a dangerous submission being blocked (fork bomb → "process_limit_exceeded")
3. Show the Grafana dashboard during a load test
4. Show judge mode evaluating test cases
5. Show NLGeo's Mumbai query running through CodeForge

### Optional: blog post

"I Let an LLM Execute Code on My Server — Here's How I Made It Safe"

Covers: the NLGeo problem, the naive approach, each layer of defense, the before/after table, benchmarks, what you learned. Post on dev.to or your personal blog. Link from both READMEs.

### Exit condition
README is complete with diagrams, tables, and examples. Demo video recorded. Repo is clean, well-documented, and public.

---

## The Complete Resume Story

> **Project 1 — NLGeo:** Production autonomous GeoAI pipeline. 7-stage async architecture (FastAPI + Celery + Redis + PostGIS + Qdrant) processing natural language geospatial queries across 20+ cities. LLM-generated code with self-verification (Spearman 1.0 vs QGIS ground truth). Langfuse observability. Deployed on Microsoft Azure.

> **Project 2 — CodeForge:** Secure code execution engine in Go. Docker SDK-based sandboxing with 8-vector attack containment (filesystem, network, fork bomb, memory, CPU, disk, env leak, privilege escalation). Async job queue (Redis + worker pool with graceful shutdown). Token-bucket rate limiting. Judge mode with multi-language support (Python, JS, Go, C/C++, Java). Prometheus + Grafana monitoring. CI/CD via GitHub Actions. HTTPS deployment on Azure.

> **Together:** "CodeForge secures NLGeo's execution layer — LLM-generated geospatial code runs inside hardened containers instead of raw subprocesses. Mumbai flood benchmark passes end-to-end through the secured pipeline."

---

## Timeline estimate (with plenty of time)

| Phase | Duration | Cumulative |
|-------|----------|------------|
| 0. Go foundations | 10–14 days | 2 weeks |
| 1. Naive executor + attack suite | 3–4 days | ~2.5 weeks |
| 2. Docker isolation | 4–5 days | ~3.5 weeks |
| 3. Resource limits | 3–4 days | ~4 weeks |
| 4. Security hardening | 4–5 days | ~5 weeks |
| 5. Job queue + workers | 5–6 days | ~6 weeks |
| 6. Auth + rate limiting | 4–5 days | ~7 weeks |
| 7. Multi-language | 4–5 days | ~8 weeks |
| 8. Judge mode | 4–5 days | ~9 weeks |
| 9. Observability | 3–4 days | ~9.5 weeks |
| 10. Testing + benchmarks | 4–5 days | ~10.5 weeks |
| 11. CI/CD | 2–3 days | ~11 weeks |
| 12. Azure deployment | 3–4 days | ~12 weeks |
| 13. NLGeo integration | 3–4 days | ~12.5 weeks |
| 14. Webhooks + streaming | 3–4 days | ~13 weeks |
| 15. README + demo | 2–3 days | ~14 weeks |

**Total: ~14 weeks (3.5 months) at a steady pace.**

You can compress this significantly if you're working full-time on it. Phases are designed to be independently deployable — after Phase 5, you already have a working, deployed, secured execution engine. Everything after that is polish and differentiation.
