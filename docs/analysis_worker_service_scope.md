# Dedicated Analysis Worker Service — Scope Document

**Status:** SIGNED OFF 2026-06-06 (Mohit: "go for option 2")
**Skill applied:** `/scope-driven-development` (Section 0 done during investigation)
**Trigger:** 886-job re-analysis backlog → ~17h drain on the single in-app fallback worker.

---

## 0. Existing surfaces audit (done during investigation)

| What exists | Detail |
|---|---|
| Analysis execution | Runs as an **in-app fallback loop** inside the FastAPI backend (`server.py:analysis_queue_fallback_loop`). **Throttled to 1 concurrent** via `if processing_count > 0: return`. |
| Job claim | `analysis_worker.claim_next_job` — **atomic** `find_one_and_update` (status pending→processing). Race-safe across processes. ✓ |
| Job processing | `analysis_worker.process_job(db, job)` — sync, self-contained: Stockfish + traps + V5 gen + training extraction. One `StockfishEngine` per job (no shared engine state). |
| Compose services | `mongodb`, `backend`, `frontend-builder`. **No worker service** — the codebase comments reference a "dedicated worker" but the file (`run_queue_worker.py`) was deleted; the in-app fallback replaced it. |
| Host | 12 cores. Stockfish configured `Threads=1`, `Hash=128MB` per engine. Backend container mem limit 2G. |
| Priority | `claim_next_job` sorts `(priority DESC, queued_at ASC)` as of e6d2ce3c — live games (priority=10) jump ahead of bulk (priority=0/missing). |

**Decision: PARALLEL (add a dedicated worker service).** Not EXTEND-the-fallback (option 1) — that couples analysis CPU to API latency and shares the 2G API budget. A separate service isolates Stockfish load and scales independently.

---

## 1. What it is

A dedicated, horizontally-scalable analysis worker service. Each replica runs a claim→process loop against the shared `analysis_queue`, relying on the existing atomic claim for safety. Scale with `docker compose up -d --scale analysis-worker=N`. The in-app fallback stays as a safety net (it self-throttles to 1 and yields whenever any job is processing, so it never fights the dedicated workers).

No UI change. User-facing effect: the analysis backlog drains ~N× faster, and freshly-played games (priority=10) still jump the queue.

---

## 2. What the user sees

No UI. The effect: a game finished now is analyzed in ~1-2 min (priority jump) even with a backlog; the bulk backlog clears in `~17h / N` instead of ~17h.

---

## 3. In scope (V1)

- New `backend/run_worker.py` — standalone worker loop: claim_next_job (race-safe) → process_job → repeat, POLL_INTERVAL between empty claims. **No `processing_count` throttle** (that's a fallback-only safety; the dedicated worker processes as fast as it can claim). Calls `cleanup_stuck_jobs` on startup. Logs with a per-pid worker id.
- New `analysis-worker` service in `docker-compose.yml`:
  - Reuses `Dockerfile.backend` image (Stockfish baked in)
  - `command: python run_worker.py`
  - **No `container_name`** (required so `--scale` can run N replicas)
  - Same env as backend (MONGO_URL, DB_NAME, OPENAI_API_KEY, …)
  - `depends_on: mongodb`
  - Own memory limit (NOT the API's 2G) — sized for the replica count
  - `restart: unless-stopped`
- In-app fallback loop UNCHANGED (stays as safety net; its `processing_count > 0` self-throttle means it yields to the dedicated workers).

---

## 4. Explicitly out of scope (V1)

- **Autoscaling** — fixed replica count set at deploy via `--scale`. No dynamic scaling on queue depth.
- **Per-worker Stockfish thread tuning** — stays `Threads=1` (1 thread/engine × N workers ≤ 12 cores).
- **Removing the in-app fallback** — kept as safety net. Retiring it is a later cleanup once the dedicated service is proven.
- **The LLM-401 issue** — confirmed LOCAL-only (my Windows IP not allowlisted); prod host IP is allowlisted, so workers on srv1050112 don't hit it. Ripping out the dead V4 LLM path is a separate cleanup (it shouldn't be calling OpenAI at all per "no LLM in coaching").
- **The metadata-extraction bug** (opponent/date None) — separate bug, filed separately.
- **Multi-host workers** — V1 is same-host replicas (shares the allowlisted prod IP). Multi-host would reopen the LLM-IP question.

---

## 5. Success criteria

**Primary:** with N=4 workers, the 886-job backlog drains in roughly `17h / 4 ≈ 4-5h` (measured via queue `pending` count dropping ~4× faster than single-worker), AND no double-processed games (atomic claim holds), AND API latency unaffected (analysis off the API container).

**Secondary tracked:**
- Worker memory stays under the service limit (no OOM-kill restarts)
- `failed` job count doesn't spike vs the single-worker baseline (concurrency shouldn't introduce new failures)
- Live games (priority=10) still analyze within ~2 min during a backlog

---

## 6. Open questions — resolved

### Q1. Replica count? → **N=4 default** (configurable via `--scale`)
12 cores, 1 thread/engine → cores aren't the bind. Memory is: ~300MB/concurrent analysis. N=4 ≈ 1.2G + overhead, comfortably under a 2G worker-service limit, leaves 8 cores for API+mongo+OS headroom. Mohit can scale to 6 if memory allows. Locked default: 4.

### Q2. Worker-service memory limit? → **2G** (same as backend, sized for ~4-6 concurrent)

### Q3. Keep in-app fallback? → **Yes**, as safety net. Its self-throttle means zero conflict with dedicated workers.

### Q4. LLM-401? → **Non-issue on prod** (host IP allowlisted). Local-only artifact. V4 LLM removal filed separately.

---

## 7. Pre-code requirements

- [x] Atomic claim verified race-safe (priority sentinel test, e6d2ce3c)
- [x] Stockfish thread config known (1 thread/engine, 12 cores)
- [x] Image reuse confirmed (Dockerfile.backend has Stockfish + WORKDIR /app/backend)
- [x] LLM-401 confirmed local-only
- [x] Mohit signoff ("go for option 2")

After build: deploy on prod, `--scale analysis-worker=4`, watch the `pending` count drop ~4×.

---

## Appendix A — what gets built

- `backend/run_worker.py` — the loop (~40 lines)
- `docker-compose.yml` — `analysis-worker` service (scalable, own mem limit)
- No changes to `server.py` (fallback stays), `analysis_worker.py` (process_job/claim reused as-is), or any caption code.

**Rollback:** `docker compose stop analysis-worker` (or `--scale analysis-worker=0`). The in-app fallback resumes single-threaded processing. No data migration.
