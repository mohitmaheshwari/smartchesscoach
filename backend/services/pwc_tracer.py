"""
Play with Coach session tracer.

Captures every request + response from the load-bearing PWC endpoints
into a single collection keyed by session_id. Lets us answer the
question "what exactly did the backend send to the UI, in order?"
without having to reconstruct from coach_sessions state.

Built 2026-05-19 after Mohit reported the UI showing different /
fewer coaching surfaces than what got persisted to coach_sessions.
The state doc tells you the FINAL state; this tells you every
PAYLOAD along the way.

Storage: `pwc_session_traces` collection. One row per API call.
Schema:
    {
        session_id, user_id, ts, endpoint, request, response,
        duration_ms, status
    }

Inspect with:
    docker exec chess-coach-backend python scripts/dump_pwc_session.py <session_id>
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def trace_pwc(
    db,
    session_id: Optional[str],
    user_id: Optional[str],
    endpoint: str,
    request_body: Any = None,
    response_body: Any = None,
    duration_ms: Optional[float] = None,
    status: str = "ok",
) -> None:
    """Write a single trace row. Non-fatal on failure — never let
    tracing break a real request."""
    if not session_id:
        return
    try:
        doc = {
            "session_id": session_id,
            "user_id": user_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "request": _scrub(request_body),
            "response": _scrub(response_body),
            "duration_ms": round(duration_ms or 0, 1),
            "status": status,
        }
        await db.pwc_session_traces.insert_one(doc)
    except Exception as e:
        # Tracing must not break the user-facing endpoint.
        logger.warning(f"pwc_tracer write failed: {e}")


@asynccontextmanager
async def traced_call(db, session_id: Optional[str], user_id: Optional[str],
                       endpoint: str, request_body: Any = None):
    """Async context manager. Pass response back via setter.

    Usage:
        async with traced_call(db, sid, uid, "POST /move", req) as t:
            response = await do_work()
            t.response = response
            return response
    """
    started = time.time()
    holder = _TraceHolder()
    try:
        yield holder
    except Exception:
        holder.status = "error"
        raise
    finally:
        duration_ms = (time.time() - started) * 1000.0
        await trace_pwc(
            db, session_id, user_id, endpoint,
            request_body=request_body,
            response_body=holder.response,
            duration_ms=duration_ms,
            status=holder.status,
        )


class _TraceHolder:
    def __init__(self):
        self.response: Any = None
        self.status: str = "ok"


def trace_pwc_endpoint(endpoint_name: str, get_db):
    """Decorator for PWC endpoints. Captures request body + response
    body + duration into pwc_session_traces, keyed by session_id.

    Args:
        endpoint_name: human label like "POST /coach/play/move".
        get_db:        zero-arg callable returning the live db handle
                       (route modules use a module-level `db = None`
                       that's set at startup; we pass a getter so the
                       decorator picks up the current value).

    Extracts session_id from either kwargs["request"]["session_id"]
    or kwargs["session_id"] (path param). user_id from kwargs["user"].
    Errors during tracing never propagate.
    """
    import functools
    from fastapi import HTTPException

    def decorator(handler):
        @functools.wraps(handler)
        async def wrapper(*args, **kwargs):
            started = time.time()
            request_body = kwargs.get("request")
            session_id: Optional[str] = kwargs.get("session_id")
            if session_id is None and isinstance(request_body, dict):
                session_id = request_body.get("session_id")
            user = kwargs.get("user")
            user_id = getattr(user, "user_id", None)

            response: Any = None
            status_label = "ok"
            try:
                response = await handler(*args, **kwargs)
                return response
            except HTTPException as he:
                status_label = f"http_{he.status_code}"
                raise
            except Exception:
                status_label = "error"
                raise
            finally:
                try:
                    db = get_db()
                    if db is not None:
                        duration_ms = (time.time() - started) * 1000.0
                        await trace_pwc(
                            db, session_id, user_id, endpoint_name,
                            request_body=request_body,
                            response_body=response,
                            duration_ms=duration_ms,
                            status=status_label,
                        )
                except Exception as e:
                    logger.warning(f"pwc_tracer decorator finalize failed: {e}")

        return wrapper

    return decorator


def _scrub(payload: Any, depth: int = 0) -> Any:
    """Trim values that would blow up trace rows. Drops big PGN strings,
    truncates long arrays. Recursion depth-capped so deep dict trees
    don't explode."""
    if depth > 6:
        return "<truncated:depth>"
    if payload is None:
        return None
    if isinstance(payload, (str, int, float, bool)):
        if isinstance(payload, str) and len(payload) > 4000:
            return payload[:4000] + f"...<truncated {len(payload) - 4000} chars>"
        return payload
    if isinstance(payload, dict):
        return {k: _scrub(v, depth + 1) for k, v in payload.items()}
    if isinstance(payload, list):
        if len(payload) > 200:
            return [_scrub(v, depth + 1) for v in payload[:200]] + [f"<truncated {len(payload) - 200} more>"]
        return [_scrub(v, depth + 1) for v in payload]
    # Anything else (Pydantic, datetime, etc.): str-cast
    try:
        return str(payload)[:2000]
    except Exception:
        return "<unserializable>"
