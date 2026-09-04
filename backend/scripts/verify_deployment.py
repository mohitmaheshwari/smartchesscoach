"""
Deployment verification for ChessGuru — "is what's running RIGHT NOW
actually the thing we think we just shipped?"

Why this exists (2026-08-07): the motif blind-spot feature shipped in
FOUR separate steps the same night — backend computed + stored the
data, then a separate deploy made the API actually return it, then a
separate deploy made the frontend render it, then a separate step
built + shipped the frontend bundle to the static site. At one point a
backend file was deployed but the container was never restarted, so
the OLD code kept serving silently — no error, just quietly wrong
behavior. No single script checked "did the thing we just changed
actually reach production." This is that script.

It checks, against a live base URL:
  1. Git commit match           (currently a REAL GAP — see printed note)
  2. Frontend bundle marker     (fetch HTML -> find bundle -> grep for a string)
  3. Backend health endpoint    (GET /api/health)
  4. Authenticated read -> DB   (GET /api/auth/me with a session token)
  5. Canonical coaching contract (GET /api/coach/decryption/v5/{game_id})
  6. Worker queue health        (analysis_queue counts, direct MONGO_URL)
  7. Failed-job spike check     (recent failed count vs a real baseline)
  8. Non-admin coaching journey (Home -> lesson -> Review -> Progress)

Every check prints PASS / FAIL / SKIPPED with a reason. SKIPPED never
counts as a pass — it means "could not verify," and is printed loudly
so a clean exit code is never mistaken for "fully verified."

Usage:
  # Against production (default), unauthenticated — checks 1-3 run,
  # 4-7 SKIP with a clear reason (no --auth-token / no DB access).
  python backend/scripts/verify_deployment.py

  # Against a local stack, fully authenticated:
  python backend/scripts/verify_deployment.py \\
      --base-url http://localhost:8002 \\
      --auth-token <session_token> \\
      --mongo-url mongodb://localhost:27017 --db-name chess_coach

  # On the server itself (MONGO_URL/DB_NAME already in env), checks
  # 6-7 run automatically without any extra flags.
  docker exec -it chess-coach-backend python3 scripts/verify_deployment.py --auth-token <token>

Exit code: 0 only if every check that actually RAN passed. Non-zero
if any check FAILED. SKIPPED checks do not affect the exit code by
default, but are always printed loudly (see the module docstring
above) so a clean exit code is never misread as "fully verified."

Strict mode (2026-08-07, added per external review): the default
behavior above is right for an exploratory/diagnostic run, but wrong
for a release gate — a deploy could return exit 0 with 3 checks passed
and 4 skipped, verifying nothing about commit identity, auth, the
canonical coaching contract, or worker health. Pass --require-checks to
turn specific SKIPs into hard failures for CI/release use:

  python backend/scripts/verify_deployment.py \\
      --auth-token <token> --mongo-url ... \\
      --require-checks commit,bundle,health,auth,contract,queue,failures

  # or require every check that ran-or-should-have-run:
  python backend/scripts/verify_deployment.py --require-all ...

Checks 1-7 are read-only. Check 8 uses a dedicated non-admin verification
fixture and may create idempotent lesson/reach evidence in that isolated
account. It must never use a real learner account.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Windows consoles default to a legacy codepage that mangles the em
# dashes / arrows used below (prints as "?" / mojibake). Force UTF-8
# stdout when possible; harmless no-op on Linux (docker) where the
# default is already UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import requests

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIPPED"

# Stable short keys for --require-checks, mapped from each check's number
# prefix in its `name` (e.g. "1. Git commit match" -> "commit"). Keeps the
# CLI flag readable without depending on RESULTS list order, which follows
# execution order (health, commit, bundle, auth, contract, queue, failures),
# not numeric order.
CHECK_KEYS = {
    "1": "commit",
    "2": "bundle",
    "3": "health",
    "4": "auth",
    "5": "contract",
    "6": "queue",
    "7": "failures",
    "8": "journey",
}


def _check_key(name: str) -> str | None:
    prefix = name.split(".", 1)[0].strip()
    return CHECK_KEYS.get(prefix)


def spike_threshold(baseline_failed_count: int, baseline_days: float, floor: int) -> int:
    """Data-derived failed-job spike threshold: 3x the trailing daily
    average, floored so a near-zero baseline doesn't make check 7
    hair-trigger. Pulled out as a pure function (2026-08-07, external
    review) so it's directly unit testable -- see
    backend/tests/test_verify_deployment.py.
    """
    baseline_per_day = baseline_failed_count / baseline_days
    return max(floor, round(baseline_per_day * 3))

DEFAULT_BASE_URL = "https://chessguru.ai"
# 2026-08-07: data-testid on the motif blind-spot card shipped tonight
# (frontend/src/components/GameDecryptionV5.jsx). Confirmed present in
# the live main.*.js bundle at time of writing — a real, checkable
# recent-deploy marker, not a made-up placeholder.
DEFAULT_FRONTEND_MARKER = "phase8-transfer-verdict"


@dataclass
class CheckResult:
    name: str
    status: str
    detail: list[str] = field(default_factory=list)


RESULTS: list[CheckResult] = []


def record(name: str, status: str, detail: list[str] | None = None) -> CheckResult:
    r = CheckResult(name=name, status=status, detail=detail or [])
    RESULTS.append(r)
    return r


def _print_result(r: CheckResult) -> None:
    marker = {"PASS": "[PASS]   ", "FAIL": "[FAIL]   ", "SKIPPED": "[SKIPPED]"}[r.status]
    print(f"{marker} {r.name}")
    for line in r.detail:
        print(f"           {line}")
    print()


def _local_git_head() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


# =====================================================================
# Check 1 — git commit match
# =====================================================================

def check_commit_match(health_json: dict | None) -> None:
    name = "1. Git commit match"

    commit_keys = [k for k in (health_json or {}) if any(
        tok in k.lower() for tok in ("commit", "sha", "git", "version", "build")
    )]

    if commit_keys:
        exposed = {k: health_json[k] for k in commit_keys}
        # "unknown" is the Dockerfile's own documented default when the
        # image was built without --build-arg GIT_COMMIT=... — a real,
        # distinct state from "wrong commit," not a FAIL. Otherwise a
        # dev container built via `docker cp` (never gets a build arg)
        # would falsely report a commit mismatch every time.
        if all(str(v).strip().lower() in ("unknown", "", "none") for v in exposed.values()):
            record(name, SKIP, [
                f"Health endpoint exposes: {exposed}",
                "The endpoint is plumbed but this build never received --build-arg GIT_COMMIT.",
                "Not a mismatch -- deploy with: "
                "GIT_COMMIT=$(git rev-parse HEAD) docker compose up -d --build",
            ])
            return
        local_head = _local_git_head()
        detail = [f"Health endpoint exposes: {exposed}"]
        if local_head:
            detail.append(f"Local HEAD (this checkout): {local_head}")
            match = local_head in str(exposed.values())
            record(name, PASS if match else FAIL, detail + [
                "commit matches local HEAD" if match else
                "does NOT match local HEAD — server may be running an older/newer commit"
            ])
        else:
            record(name, SKIP, detail + ["could not resolve local HEAD to compare against"])
        return

    # Real gap, confirmed by reading the codebase: /api/health
    # (backend/server.py) returns only {"status", "database"}. No
    # endpoint anywhere exposes a commit/build id. The Docker build
    # (Dockerfile.backend) also excludes .git via .dockerignore, so
    # `git rev-parse HEAD` isn't even available inside the running
    # container — there's nothing to read yet, not just an endpoint
    # to add.
    record(
        name,
        SKIP,
        [
            "GAP: no endpoint anywhere exposes a git commit/build id.",
            "/api/health (backend/server.py) returns only {status, database}.",
            ".dockerignore excludes .git from the build context, so the",
            "commit isn't even available inside the running container today.",
            "",
            "Minimal fix (3 small edits, not a one-liner because the value",
            "has to be PLUMBED IN at build time, not just read):",
            "  1. Dockerfile.backend: add `ARG GIT_COMMIT=unknown` and",
            "     `ENV GIT_COMMIT=$GIT_COMMIT` before the CMD line.",
            "  2. docker-compose.yml backend service: pass it through, e.g.",
            "     `build: args: {GIT_COMMIT: ${GIT_COMMIT}}`.",
            "  3. backend/server.py health() -> add",
            "     `\"git_commit\": os.environ.get(\"GIT_COMMIT\", \"unknown\")`.",
            "  4. Deploy step must then run:",
            "     `GIT_COMMIT=$(git rev-parse HEAD) docker compose up -d --build`",
            f"(local HEAD right now, for reference: {_local_git_head() or 'unknown'})",
        ],
    )


# =====================================================================
# Check 2 — frontend bundle marker
# =====================================================================

def check_frontend_marker(base_url: str, marker: str, timeout: float) -> None:
    name = "2. Frontend bundle contains expected marker"
    try:
        resp = requests.get(base_url.rstrip("/") + "/", timeout=timeout)
    except Exception as e:
        record(name, FAIL, [f"Could not fetch {base_url}/ — {e}"])
        return

    if resp.status_code != 200:
        record(name, FAIL, [f"GET {base_url}/ returned HTTP {resp.status_code}"])
        return

    html = resp.text
    m = re.search(r'<script[^>]+src="([^"]*main[^"]*\.js)"', html)
    if not m:
        # fall back to any script tag under /static/js/
        m = re.search(r'<script[^>]+src="([^"]*/static/js/[^"]+\.js)"', html)
    if not m:
        record(name, FAIL, [
            "Could not find a main JS bundle <script> tag in the served HTML.",
            f"First 300 chars of response: {html[:300]!r}",
        ])
        return

    bundle_url = urljoin(base_url, m.group(1))
    try:
        bundle_resp = requests.get(bundle_url, timeout=timeout)
    except Exception as e:
        record(name, FAIL, [f"Found bundle URL {bundle_url} but could not fetch it — {e}"])
        return

    if bundle_resp.status_code != 200:
        record(name, FAIL, [f"GET {bundle_url} returned HTTP {bundle_resp.status_code}"])
        return

    body = bundle_resp.text
    found = marker in body
    detail = [
        f"HTML page:   {base_url}/",
        f"Bundle URL:  {bundle_url}",
        f"Bundle size: {len(body):,} bytes",
        f"Marker:      {marker!r} -> {'found' if found else 'NOT FOUND'}",
    ]
    record(name, PASS if found else FAIL, detail)


# =====================================================================
# Check 3 — backend health endpoint
# =====================================================================

def check_health(base_url: str, timeout: float) -> dict | None:
    name = "3. Backend health endpoint"
    url = base_url.rstrip("/") + "/api/health"
    try:
        resp = requests.get(url, timeout=timeout)
    except Exception as e:
        record(name, FAIL, [f"GET {url} — {e}"])
        return None

    if resp.status_code != 200:
        record(name, FAIL, [f"GET {url} returned HTTP {resp.status_code}", resp.text[:300]])
        return None

    try:
        body = resp.json()
    except Exception:
        record(name, FAIL, [f"GET {url} returned non-JSON body: {resp.text[:300]!r}"])
        return None

    status_ok = str(body.get("status", "")).lower() in ("healthy", "ok", "up")
    record(
        name,
        PASS if status_ok else FAIL,
        [f"GET {url} -> HTTP 200, body={body}"],
    )
    return body


# =====================================================================
# Check 4 — authenticated read reaches MongoDB (GET /api/auth/me)
# =====================================================================

def check_authenticated_read(base_url: str, auth_token: str | None, timeout: float) -> dict | None:
    name = "4. Authenticated read reaches MongoDB (GET /api/auth/me)"
    if not auth_token:
        record(name, SKIP, [
            "No --auth-token provided.",
            "backend/routes/auth.py get_current_user() accepts either the",
            "'session_token' cookie or an 'Authorization: Bearer <token>' header.",
            "Get one via GET /api/auth/dev-login (DEV_MODE only) or a normal",
            "login, then pass it here: --auth-token <session_token>",
        ])
        return None

    url = base_url.rstrip("/") + "/api/auth/me"
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {auth_token}"}, timeout=timeout)
    except Exception as e:
        record(name, FAIL, [f"GET {url} — {e}"])
        return None

    if resp.status_code != 200:
        record(name, FAIL, [f"GET {url} returned HTTP {resp.status_code}", resp.text[:300]])
        return None

    try:
        body = resp.json()
    except Exception:
        record(name, FAIL, [f"GET {url} returned non-JSON body: {resp.text[:300]!r}"])
        return None

    user_id = body.get("user_id")
    if user_id:
        record(name, PASS, [f"GET {url} -> HTTP 200, user_id={user_id}"])
    else:
        record(name, FAIL, [f"GET {url} -> HTTP 200 but no user_id in body: {body}"])
    return body


# =====================================================================
# Check 5 — canonical coaching endpoint contract
# =====================================================================

def check_canonical_endpoint(base_url: str, auth_token: str | None, game_id: str | None, timeout: float) -> None:
    name = "5. Canonical coaching endpoint contract (GET /api/coach/decryption/v5/{game_id})"
    if not auth_token:
        record(name, SKIP, [
            "No --auth-token provided (this endpoint requires auth) — same",
            "requirement/reason as check 4.",
        ])
        return
    if not game_id:
        record(name, SKIP, [
            "No --game-id provided and none could be auto-discovered",
            "(needs direct DB access — see checks 6/7 for why that's unavailable).",
            "Pass a real game_id owned by the --auth-token user with --game-id.",
        ])
        return

    url = base_url.rstrip("/") + f"/api/coach/decryption/v5/{game_id}"
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {auth_token}"}, timeout=timeout)
    except Exception as e:
        record(name, FAIL, [f"GET {url} — {e}"])
        return

    if resp.status_code != 200:
        record(name, FAIL, [f"GET {url} returned HTTP {resp.status_code}", resp.text[:300]])
        return

    try:
        body = resp.json()
    except Exception:
        record(name, FAIL, [f"GET {url} returned non-JSON body: {resp.text[:300]!r}"])
        return

    if body.get("error"):
        record(name, FAIL, [f"GET {url} -> {body}", "(game_id likely not found / not owned by this user)"])
        return

    # Contract per routes/coach.py get_game_decryption_v5: always a
    # dict with "status" and "decryption_data" top-level keys.
    missing = [k for k in ("status", "decryption_data") if k not in body]
    if missing:
        record(name, FAIL, [f"Response missing expected key(s): {missing}", f"Got keys: {sorted(body.keys())}"])
        return

    status = body.get("status")
    detail = [f"GET {url} -> HTTP 200, status={status!r}"]
    if status == "complete":
        n = len(body.get("decryption_data") or [])
        detail.append(f"decryption_data: {n} move(s)")
        detail.append(f"motif_blindspot present: {'motif_blindspot' in body}")
    elif status == "generating":
        detail.append("Coaching still generating for this game_id — contract is valid, just not ready yet.")
    record(name, PASS, detail)


# =====================================================================
# Check 8 — non-admin complete coaching journey
# =====================================================================

def check_complete_coaching_journey(
    base_url: str,
    auth_token: str | None,
    auth_body: dict | None,
    fixture: dict | None,
    timeout: float,
) -> None:
    name = "8. Non-admin complete coaching journey"
    if not auth_token:
        record(name, SKIP, ["No --auth-token provided for the journey fixture."])
        return
    if not fixture:
        record(name, SKIP, [
            "No --journey-fixture-json or PHASE8_VERIFICATION_FIXTURE_JSON provided."
        ])
        return
    if str((auth_body or {}).get("role") or "user").lower() in {
        "admin",
        "super_admin",
    }:
        record(name, FAIL, ["Journey verification account must be non-admin."])
        return
    required = ("content_kind", "content_id", "move", "game_id")
    missing = [key for key in required if not str(fixture.get(key) or "").strip()]
    if missing:
        record(name, FAIL, [f"Journey fixture missing keys: {missing}"])
        return

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }
    detail = []
    try:
        home_url = base_url.rstrip("/") + "/api/coach/personal-curriculum?surface=home"
        home = requests.get(home_url, headers=headers, timeout=timeout)
        if home.status_code != 200:
            raise ValueError(f"Home contract returned HTTP {home.status_code}: {home.text[:200]}")
        home_body = home.json()
        primary = (home_body.get("decision") or {}).get("primary") or {}
        destination = primary.get("destination") or {}
        if (
            home_body.get("enabled") is not True
            or not (home_body.get("rollout") or {}).get("enabled")
            or destination.get("lesson_kind") != fixture["content_kind"]
            or destination.get("lesson_id") != fixture["content_id"]
            or not str(destination.get("href") or "").startswith("/training")
        ):
            raise ValueError(
                "Home did not return the enabled canonical focus/action "
                "for the exact verification lesson"
            )
        detail.append("Home returned one enabled canonical focus and training action")

        start_url = base_url.rstrip("/") + "/api/training/personalized/session/start"
        start = requests.post(
            start_url,
            headers=headers,
            json={
                "content_kind": fixture["content_kind"],
                "content_id": fixture["content_id"],
                "skill_id": fixture.get("skill_id"),
                "limit": 1,
            },
            timeout=timeout,
        )
        if start.status_code != 200:
            raise ValueError(f"Lesson start returned HTTP {start.status_code}: {start.text[:200]}")
        session = start.json()
        session_id = session.get("session_id")
        if not session_id:
            raise ValueError("Lesson start returned no session_id")
        lesson = session.get("lesson") or {}
        if (
            lesson.get("kind") != destination.get("lesson_kind")
            or lesson.get("id") != destination.get("lesson_id")
        ):
            raise ValueError("Lesson start did not preserve the Home content identity")

        if session.get("status") == "completed":
            evidence_url = (
                base_url.rstrip("/")
                + f"/api/training/personalized/session/{session_id}/evidence"
            )
            evidence_response = requests.get(
                evidence_url, headers=headers, timeout=timeout
            )
            if evidence_response.status_code != 200:
                raise ValueError("Completed fixture has no readable server evidence")
            evidence_rows = evidence_response.json().get("evidence") or []
            if not any(
                (row.get("attempt") or {}).get("correct") is True
                for row in evidence_rows
            ):
                raise ValueError("Completed fixture has no persisted correct verdict")
            detail.append("Lesson fixture already complete with persisted server verdict")
        else:
            respond_url = (
                base_url.rstrip("/")
                + "/api/training/personalized/session/respond"
            )
            interaction_id = (
                "phase8-deploy-"
                + hashlib.sha256(
                    (session_id + str(fixture["move"])).encode("utf-8")
                ).hexdigest()[:24]
            )
            response_payload = {
                "session_id": session_id,
                "move": fixture["move"],
                "interaction_id": interaction_id,
            }
            responded = requests.post(
                respond_url,
                headers=headers,
                json=response_payload,
                timeout=timeout,
            )
            if responded.status_code != 200:
                raise ValueError(
                    f"Lesson response returned HTTP {responded.status_code}: "
                    f"{responded.text[:200]}"
                )
            verdict = responded.json()
            if verdict.get("correct") is not True:
                raise ValueError(f"Fixture move did not receive a correct verdict: {verdict}")
            duplicate = requests.post(
                respond_url,
                headers=headers,
                json=response_payload,
                timeout=timeout,
            )
            if duplicate.status_code != 200 or duplicate.json() != verdict:
                raise ValueError("Duplicate lesson submission was not idempotent")
            evidence_url = (
                base_url.rstrip("/")
                + f"/api/training/personalized/session/{session_id}/evidence"
            )
            evidence_response = requests.get(
                evidence_url, headers=headers, timeout=timeout
            )
            if evidence_response.status_code != 200:
                raise ValueError("Submitted fixture has no readable server evidence")
            evidence_rows = evidence_response.json().get("evidence") or []
            stored_matches = [
                row for row in evidence_rows
                if row.get("event_id") == interaction_id
            ]
            if (
                len(stored_matches) != 1
                or (stored_matches[0].get("attempt") or {}).get("correct")
                is not True
            ):
                raise ValueError(
                    "Lesson attempt was not stored exactly once with a correct verdict"
                )
            detail.append(
                "Interactive lesson returned a verdict and stored one idempotent attempt"
            )

        review_url = (
            base_url.rstrip("/")
            + f"/api/coach/decryption/v5/{fixture['game_id']}"
        )
        review = requests.get(review_url, headers=headers, timeout=timeout)
        review_body = review.json()
        if review.status_code != 200 or review_body.get("status") != "complete":
            raise ValueError("Game Review did not return a complete routed contract")
        events = review_body.get("teachable_events") or []
        if (
            not events
            or any(
                ((event.get("display") or {}).get("authorized") is not True)
                for event in events
                if isinstance(event, dict)
            )
            or any(not isinstance(event, dict) for event in events)
        ):
            raise ValueError(
                "Game Review fixture returned no fully authorized teaching event"
            )
        detail.append("Game Review returned only authorized teaching events")

        progress_url = base_url.rstrip("/") + "/api/progress/complete-coaching"
        progress = requests.get(progress_url, headers=headers, timeout=timeout)
        if progress.status_code != 200:
            raise ValueError(f"Progress returned HTTP {progress.status_code}")
        progress_body = progress.json()
        if (
            progress_body.get("enabled") is not True
            or (progress_body.get("practice") or {}).get(
                "changes_transfer_verdict"
            ) is not False
            or (progress_body.get("transfer") or {}).get("verdict")
            not in {"improved", "still_recurring", "insufficient_evidence"}
            or (progress_body.get("steps") or {}).get("verdict_served")
            is not True
        ):
            raise ValueError("Progress did not preserve practice-versus-transfer truth")
        detail.append("Progress returned an honest practice-versus-transfer verdict")
    except (ValueError, requests.RequestException, json.JSONDecodeError) as exc:
        record(name, FAIL, [*detail, str(exc)])
        return
    record(name, PASS, detail)


# =====================================================================
# Checks 6/7 — worker queue health + failed-job spike (direct Mongo)
# =====================================================================

async def check_queue_and_failures(mongo_url: str | None, db_name: str, db_timeout_ms: int,
                                    max_recent_failures: int) -> None:
    name6 = "6. Worker queue health (analysis_queue)"
    name7 = "7. No spike in failed analysis jobs"

    if not mongo_url:
        reason = [
            "No MONGO_URL available (not passed via --mongo-url, not in env).",
            "This check needs DIRECT database access — the same way other",
            "backend/scripts/*.py scripts connect (MONGO_URL + DB_NAME env vars).",
            "Run this script on the server (or with an SSH tunnel to Mongo) to",
            "enable checks 6-7:",
            "  docker exec -it chess-coach-backend python3 scripts/verify_deployment.py",
        ]
        record(name6, SKIP, reason)
        record(name7, SKIP, reason)
        return

    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except ImportError:
        record(name6, SKIP, ["motor is not installed in this Python environment."])
        record(name7, SKIP, ["motor is not installed in this Python environment."])
        return

    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=db_timeout_ms)
    try:
        await client.admin.command("ping")
    except Exception as e:
        reason = [
            f"Could not reach MongoDB at {mongo_url!r} within {db_timeout_ms}ms — {e}",
            "SKIPPING checks 6-7 (this environment has no direct DB access, not",
            "a failure of the deployed system).",
        ]
        record(name6, SKIP, reason)
        record(name7, SKIP, reason)
        client.close()
        return

    db = client[db_name]

    # ---- Check 6: queue health snapshot ----
    try:
        pending = await db.analysis_queue.count_documents({"status": "pending"})
        processing = await db.analysis_queue.count_documents({"status": "processing"})
        completed = await db.analysis_queue.count_documents({"status": "completed"})
        failed_total = await db.analysis_queue.count_documents({"status": "failed"})

        stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=15)
        stale_processing = await db.analysis_queue.count_documents({
            "status": "processing",
            "$or": [
                {"last_heartbeat": {"$lt": stale_threshold}},
                {"last_heartbeat": {"$lt": stale_threshold.isoformat()}},
            ],
        })

        detail6 = [
            f"pending={pending} processing={processing} completed={completed} failed={failed_total}",
            f"stale processing (no heartbeat >15m): {stale_processing}",
        ]
        if stale_processing > 0:
            record(name6, FAIL, detail6 + ["worker appears stuck on at least one job"])
        else:
            record(name6, PASS, detail6)
    except Exception as e:
        record(name6, FAIL, [f"Query against analysis_queue failed: {e}"])

    # ---- Check 7: failed-job spike vs. real trailing baseline ----
    try:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=24)
        baseline_start = now - timedelta(days=8)

        recent_failed = await db.analysis_queue.count_documents({
            "status": "failed",
            "$or": [
                {"failed_at": {"$gte": window_start}},
                {"failed_at": {"$gte": window_start.isoformat()}},
            ],
        })

        baseline_failed = await db.analysis_queue.count_documents({
            "status": "failed",
            "$or": [
                {"failed_at": {"$gte": baseline_start, "$lt": window_start}},
                {"failed_at": {"$gte": baseline_start.isoformat(), "$lt": window_start.isoformat()}},
            ],
        })
        baseline_per_day = baseline_failed / 7.0
        # A real, data-derived threshold: 3x the trailing 7-day daily
        # average, floored at --max-recent-failures so a near-zero
        # baseline doesn't make the check hair-trigger.
        threshold = spike_threshold(baseline_failed, 7.0, max_recent_failures)

        detail7 = [
            f"failed in last 24h: {recent_failed}",
            f"trailing 7-day baseline: {baseline_failed} failed total "
            f"({baseline_per_day:.1f}/day average)",
            f"spike threshold used: {threshold} "
            f"(max of --max-recent-failures={max_recent_failures} and 3x baseline/day)",
        ]
        if recent_failed > threshold:
            record(name7, FAIL, detail7 + ["recent failed count exceeds the spike threshold"])
        else:
            record(name7, PASS, detail7)
    except Exception as e:
        record(name7, FAIL, [f"Query against analysis_queue for failure stats failed: {e}"])
    finally:
        client.close()


# =====================================================================
# Auto-discover a game_id for check 5 (best-effort, only if DB reachable)
# =====================================================================

async def try_autodiscover_game_id(mongo_url: str | None, db_name: str, db_timeout_ms: int,
                                    user_id: str | None) -> str | None:
    if not mongo_url or not user_id:
        return None
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except ImportError:
        return None
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=db_timeout_ms)
    try:
        await client.admin.command("ping")
        db = client[db_name]
        game = await db.games.find_one(
            {"user_id": user_id, "is_analyzed": True},
            {"_id": 0, "game_id": 1},
            sort=[("date_played", -1)],
        )
        return game.get("game_id") if game else None
    except Exception:
        return None
    finally:
        client.close()


# =====================================================================
# main
# =====================================================================

async def run(args: argparse.Namespace) -> int:
    print("=" * 72)
    print("  CHESSGURU DEPLOYMENT VERIFICATION")
    print(f"  base_url = {args.base_url}")
    print(f"  time     = {datetime.now(timezone.utc).isoformat()}")
    print("=" * 72)
    print()

    # Check 3 first — its response feeds check 1.
    health_json = check_health(args.base_url, args.timeout)
    _print_result(RESULTS[-1])

    check_commit_match(health_json)
    _print_result(RESULTS[-1])

    check_frontend_marker(args.base_url, args.frontend_marker, args.timeout)
    _print_result(RESULTS[-1])

    auth_body = check_authenticated_read(args.base_url, args.auth_token, args.timeout)
    _print_result(RESULTS[-1])

    mongo_url = args.mongo_url or os.environ.get("MONGO_URL")
    db_name = args.db_name or os.environ.get("DB_NAME", "chess_coach")

    game_id = args.game_id
    if not game_id and auth_body and auth_body.get("user_id"):
        game_id = await try_autodiscover_game_id(mongo_url, db_name, args.db_timeout_ms, auth_body.get("user_id"))

    check_canonical_endpoint(args.base_url, args.auth_token, game_id, args.timeout)
    _print_result(RESULTS[-1])

    check_complete_coaching_journey(
        args.base_url,
        args.auth_token,
        auth_body,
        args.journey_fixture,
        args.timeout,
    )
    _print_result(RESULTS[-1])

    await check_queue_and_failures(mongo_url, db_name, args.db_timeout_ms, args.max_recent_failures)
    _print_result(RESULTS[-2])
    _print_result(RESULTS[-1])

    # ---- summary ----
    n_pass = sum(1 for r in RESULTS if r.status == PASS)
    n_fail = sum(1 for r in RESULTS if r.status == FAIL)
    n_skip = sum(1 for r in RESULTS if r.status == SKIP)

    print("=" * 72)
    print(f"  SUMMARY: {n_pass} passed, {n_fail} failed, {n_skip} skipped (out of {len(RESULTS)} checks)")
    print("=" * 72)
    if n_skip:
        print(f"  {n_skip} check(s) SKIPPED — this run does NOT fully verify the deployment.")
        for r in RESULTS:
            if r.status == SKIP:
                print(f"    - {r.name}")
    print()

    required = set(args.required_checks or [])
    if required:
        unmet = [r for r in RESULTS if _check_key(r.name) in required and r.status != PASS]
        print(f"  REQUIRED CHECKS: {sorted(required)}")
        if unmet:
            print(f"  {len(unmet)} required check(s) did NOT pass (SKIPPED counts as not-passed in this mode):")
            for r in unmet:
                print(f"    - [{r.status}] {r.name}")
            print()
            return 1
        print("  All required checks passed.")
        print()
        return 1 if n_fail else 0

    return 1 if n_fail else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a ChessGuru deployment actually serves what we think it does.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                         help=f"Site to check (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--frontend-marker", default=DEFAULT_FRONTEND_MARKER,
                         help=f"String expected in the live JS bundle (default: {DEFAULT_FRONTEND_MARKER!r})")
    parser.add_argument("--auth-token", default=os.environ.get("DEPLOY_VERIFY_AUTH_TOKEN"),
                         help="Session token for authenticated checks (Authorization: Bearer <token>). "
                              "Get one via GET /api/auth/dev-login in DEV_MODE, or a normal login.")
    parser.add_argument("--game-id", default=os.environ.get("DEPLOY_VERIFY_GAME_ID"),
                         help="game_id for the canonical-endpoint check. Auto-discovered from the "
                              "--auth-token user's games if DB access is available and this is omitted.")
    parser.add_argument("--mongo-url", default=None,
                         help="Mongo connection string for checks 6-7. Defaults to $MONGO_URL.")
    parser.add_argument("--db-name", default=None,
                         help="Mongo DB name for checks 6-7. Defaults to $DB_NAME, else 'chess_coach'.")
    parser.add_argument("--db-timeout-ms", type=int, default=3000,
                         help="Mongo server-selection timeout in ms before checks 6-7 SKIP (default: 3000)")
    parser.add_argument("--max-recent-failures", type=int, default=5,
                         help="Floor for the check-7 spike threshold when the trailing baseline is near "
                              "zero (default: 5)")
    parser.add_argument("--timeout", type=float, default=15.0,
                         help="HTTP request timeout in seconds (default: 15)")
    parser.add_argument(
        "--journey-fixture-json",
        default=os.environ.get("PHASE8_VERIFICATION_FIXTURE_JSON"),
        help=(
            "JSON object for the dedicated non-admin fixture with "
            "content_kind, content_id, move and game_id. Defaults to "
            "$PHASE8_VERIFICATION_FIXTURE_JSON."
        ),
    )
    parser.add_argument("--require-checks", default=None,
                         help="Comma-separated check keys that must PASS (not just run) or the script "
                              f"exits non-zero, even with zero FAILs. Valid keys: {sorted(set(CHECK_KEYS.values()))}. "
                              "Use this for CI/release gating; omit for exploratory/diagnostic runs.")
    parser.add_argument("--require-all", action="store_true",
                         help="Shorthand for --require-checks with every valid key (commit,bundle,health,"
                              "auth,contract,queue,failures,journey).")
    args = parser.parse_args()
    if args.journey_fixture_json:
        try:
            args.journey_fixture = json.loads(args.journey_fixture_json)
        except json.JSONDecodeError as exc:
            parser.error(f"--journey-fixture-json is not valid JSON: {exc}")
        if not isinstance(args.journey_fixture, dict):
            parser.error("--journey-fixture-json must decode to an object")
    else:
        args.journey_fixture = None

    if args.require_all:
        args.required_checks = sorted(set(CHECK_KEYS.values()))
    elif args.require_checks:
        requested = [k.strip() for k in args.require_checks.split(",") if k.strip()]
        valid = set(CHECK_KEYS.values())
        bad = [k for k in requested if k not in valid]
        if bad:
            parser.error(f"--require-checks: unknown key(s) {bad}. Valid keys: {sorted(valid)}")
        args.required_checks = requested
    else:
        args.required_checks = None

    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
