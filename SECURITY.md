# CodeForge — Security Model & Attack Suite

CodeForge executes untrusted code. This document tracks how each phase
of hardening defends against a fixed suite of attacks. Every attack is
run automatically by `attacks.py` against the live API.

🔴 = attack succeeds (VULNERABLE — the sandbox did NOT stop it)
✅ = BLOCKED (the sandbox prevented the attack)
⚠️ = partially contained (runs, but exposes nothing sensitive)

## Attack Results by Phase

| # | Attack | What it proves | Phase 1 (subprocess) | Phase 2 (Docker) | Phase 3 (limits) | Phase 4 (hardened) |
|---|--------|----------------|:---:|:---:|:---:|:---:|
| 1 | file_read | Reads host system files | 🔴 | ✅ | ✅ | ✅ |
| 2 | file_write | Writes to filesystem | 🔴 | 🔴 | 🔴 | ✅ Read-only FS |
| 3 | env_leak | Dumps host env vars / secrets | 🔴 | ⚠️ | ⚠️ | ✅ Container-only |
| 4 | network_exfil | Makes outbound network calls | 🔴 | 🔴 | 🔴 | ✅ network=none |
| 5 | cwd_snoop | Reads server's own files | 🔴 | ✅ | ✅ | ✅ |
| 6 | fork_bomb | Spawns unlimited processes | 🔴* | 🔴* | ✅ PID limit 64 | ✅ |
| 7 | memory_bomb | Exhausts host memory | 🔴* | 🔴* | ✅ OOM (exit 137) | ✅ |
| 8 | infinite_loop | Hogs CPU forever | 🔴* | 🔴* | ✅ CPU cap + timeout | ✅ |

\* Attacks 6–8 are destructive. They are documented in Phase 1 but only run
at full strength from Phase 3 onward, where resource limits catch them safely
without risking the host machine.

**Phase 1 result: 5/5 runnable attacks succeeded — no isolation whatsoever.**
**Phase 4 result: 0/5 attacks succeed — every vector blocked or neutralized.**

## Evidence (Phase 4)

Each block is backed by observed output from the live API:

- **file_read** → `FileNotFoundError` — host filesystem is not mounted inside the container
- **file_write** → `OSError: [Errno 30] Read-only file system` — root filesystem is read-only
- **network_exfil** → `urllib` connection failure — container has no network interface (`network_mode=none`)
- **cwd_snoop** → empty listing `[]` — nothing of the host is visible
- **env_leak** → only container defaults (`PATH`, `HOSTNAME`); no host secrets or Windows paths present
- **fork_bomb** → `BlockingIOError: [Errno 11] Resource temporarily unavailable` at the 64-process PID limit
- **memory_bomb** → container killed by the kernel OOM killer, exit code 137
- **infinite_loop** → capped to 1 CPU core and force-killed at the wall-clock timeout

## Why Phase 1 is dangerous

The naive executor runs submitted code via `subprocess.run(["python", file])`.
This code executes:
- as the same OS user as the API server (full user privileges)
- with full read/write access to the host filesystem
- with unrestricted network access
- with no limit on CPU, memory, processes, or disk

This is the exact risk that NLGeo currently carries by running
LLM-generated code through a bare subprocess. CodeForge exists to close it.

## The hardening layers (Phase 2–4)

Applied per execution, every container is created with:

| Layer | Setting | Defends against |
|-------|---------|-----------------|
| Isolation | fresh Docker container per job, destroyed after | host filesystem/process access |
| Memory | `mem_limit=256m`, swap disabled | memory bombs |
| CPU | `nano_cpus=1e9` (1 core) | CPU-hogging loops |
| Processes | `pids_limit=64` | fork bombs |
| Network | `network_mode=none` | data exfiltration |
| Filesystem | `read_only=True` + tmpfs `/tmp` | tampering, persistence |
| Privileges | `cap_drop=ALL`, `no-new-privileges` | privilege escalation |
| Time | wall-clock timeout, force-kill | infinite loops |