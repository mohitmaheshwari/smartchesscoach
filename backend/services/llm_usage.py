"""What each LLM call cost, recorded at the moment it happens.

Nothing was recorded before this. `_call_openai` and `_call_claude` both
receive a `usage` object from the provider and both returned
`response.choices[0].message.content`, throwing it away -- so the honest
answer to "what are we spending" was that the data did not exist. There is
no collection, no counter, and no way to recover a single past call.

Two rules this module exists to keep.

**Tokens are facts, cost is derived.** Only the token counts the provider
reported are stored. Prices live in `backend/data/llm_prices.json` and are
applied at read time, so correcting a price fixes every past row at once
and nobody has to trust a number that was multiplied months ago by a rate
that has since changed.

**An unset price is visible, never zero.** A model with no entry reports
its tokens and `price_set: False`. Treating it as free would understate
the bill and look like a working page, which is the failure this repo has
already had with empty authored content shipping silently.

Recording must never break a call. Every write is wrapped: the caption
path falls back to a deterministic caption when the LLM fails, and a
bookkeeping error is not a reason to trigger that.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

COLLECTION = "llm_usage"
_PRICES_PATH = Path(__file__).resolve().parents[1] / "data" / "llm_prices.json"
_prices_cache: Optional[Dict[str, Any]] = None

# Set by server.py / the worker, the same way the admin routes take a db.
_db = None


_is_async_db = False


def set_db(db) -> None:
    """Take whichever Mongo handle the caller has.

    The API process holds a motor handle and the analysis worker a pymongo
    one, and the two are not interchangeable: calling motor's `insert_one`
    from synchronous code returns a coroutine nobody awaits, so the write
    silently never happens and the page shows a smaller bill than the
    invoice. So the flavour is detected once, here, rather than assumed.
    """
    global _db, _is_async_db
    _db = db
    _is_async_db = type(db).__module__.startswith("motor")


def load_prices(refresh: bool = False) -> Dict[str, Any]:
    """The price table, or an empty one. Never raises."""
    global _prices_cache
    if _prices_cache is not None and not refresh:
        return _prices_cache
    try:
        with open(_PRICES_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        _prices_cache = data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("[llm_usage] no price table (%r); costs will read "
                       "as unset rather than zero", exc)
        _prices_cache = {}
    return _prices_cache


def price_for(model: str) -> Optional[Dict[str, float]]:
    """Per-million-token prices for a model, or None when unset.

    Matched exactly first, then by the longest configured prefix, so
    `gpt-6-luna-2026-01` picks up a `gpt-6-luna` entry without needing a
    row per dated snapshot.
    """
    table = (load_prices() or {}).get("models") or {}
    if model in table:
        return table[model]
    best = None
    for key, val in table.items():
        if model.startswith(key) and (best is None or len(key) > len(best[0])):
            best = (key, val)
    return best[1] if best else None


def cost_usd(model: str, input_tokens: int, output_tokens: int,
             cached_input_tokens: int = 0) -> Optional[float]:
    """Dollars for one call, or None when the model has no price set.

    None is deliberate and must reach the page as "not set". Returning 0.0
    would make an unpriced model look free.
    """
    p = price_for(model)
    if not p:
        return None
    try:
        inp = float(p.get("input_per_mtok") or 0.0)
        out = float(p.get("output_per_mtok") or 0.0)
        cached = p.get("cached_input_per_mtok")
        cached = float(cached) if cached is not None else inp
        billed_fresh = max(0, int(input_tokens) - int(cached_input_tokens))
        return (billed_fresh * inp
                + int(cached_input_tokens) * cached
                + int(output_tokens) * out) / 1_000_000.0
    except Exception:
        return None


def _extract(usage: Any) -> Dict[str, int]:
    """Token counts from either provider's usage object.

    OpenAI says prompt_tokens/completion_tokens; Anthropic says
    input_tokens/output_tokens plus cache_read_input_tokens. Both are read
    defensively because a provider adding or renaming a field must not take
    the caption path down with it.
    """
    def g(*names) -> int:
        for n in names:
            v = getattr(usage, n, None)
            if v is None and isinstance(usage, dict):
                v = usage.get(n)
            if isinstance(v, (int, float)):
                return int(v)
        return 0

    cached = g("cache_read_input_tokens", "cached_tokens")
    if not cached:
        details = getattr(usage, "prompt_tokens_details", None)
        if details is not None:
            cached = int(getattr(details, "cached_tokens", 0) or 0)
    return {
        "input_tokens": g("prompt_tokens", "input_tokens"),
        "output_tokens": g("completion_tokens", "output_tokens"),
        "cached_input_tokens": cached,
        "reasoning_tokens": g("reasoning_tokens"),
    }


def record(model: str, usage: Any, *, surface: str = "unattributed",
           user_id: Optional[str] = None,
           game_id: Optional[str] = None) -> None:
    """Write one usage row. Swallows everything.

    `surface` defaults to "unattributed" rather than being dropped: a call
    nobody has wired yet must still appear in the total, or the page shows
    a number smaller than the invoice and reads as if it were complete.
    """
    if _db is None or usage is None:
        return
    try:
        tok = _extract(usage)
        if not any(tok.values()):
            return
        doc = {
            "ts": datetime.now(timezone.utc),
            "model": str(model or "unknown"),
            "surface": str(surface or "unattributed"),
            "user_id": user_id,
            "game_id": game_id,
            **tok,
        }
        est = cost_usd(doc["model"], tok["input_tokens"],
                       tok["output_tokens"], tok["cached_input_tokens"])
        # Stored for convenience only. The admin page recomputes from the
        # live table so a price correction applies to history too; this
        # field is what the row cost under the rate of the day.
        doc["cost_usd_at_write"] = est
        if _is_async_db:
            # Both provider calls are async, so there is a running loop.
            # Fire and forget: the answer must not wait on bookkeeping.
            import asyncio
            task = asyncio.get_running_loop().create_task(
                _db[COLLECTION].insert_one(doc))
            # Without a done-callback an exception here surfaces as
            # "Task exception was never retrieved" in the logs.
            task.add_done_callback(
                lambda t: t.exception() and logger.debug(
                    "[llm_usage] async insert failed: %r", t.exception()))
        else:
            _db[COLLECTION].insert_one(doc)
    except Exception as exc:
        logger.debug("[llm_usage] not recorded: %r", exc)


async def record_async(model: str, usage: Any, **kw) -> None:
    """Motor variant, for the async paths that hold an async db handle."""
    if _db is None or usage is None:
        return
    try:
        tok = _extract(usage)
        if not any(tok.values()):
            return
        doc = {
            "ts": datetime.now(timezone.utc),
            "model": str(model or "unknown"),
            "surface": str(kw.get("surface") or "unattributed"),
            "user_id": kw.get("user_id"),
            "game_id": kw.get("game_id"),
            **tok,
        }
        doc["cost_usd_at_write"] = cost_usd(
            doc["model"], tok["input_tokens"], tok["output_tokens"],
            tok["cached_input_tokens"])
        await _db[COLLECTION].insert_one(doc)
    except Exception as exc:
        logger.debug("[llm_usage] not recorded: %r", exc)


def env_default_surface() -> str:
    """A process-wide label for calls nobody passed a surface for, so the
    worker's calls do not land in the same bucket as a request's."""
    return os.environ.get("LLM_USAGE_SURFACE") or "unattributed"
