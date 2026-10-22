"""The USD/INR rate for the day a cost was incurred.

Mohit: "you have to get the latest usd to INR rate for me for that day, you
know, to get me the money spent". Right, and the reason matters: converting
a whole window at today's rate is the same error as pricing yesterday's
tokens at today's token rate. Over the three weeks to 2026-10-22 the rate
moved from 96.78 to 94.47 -- about 2.4% -- so a month's spend converted at
one rate is wrong by more than the rounding anyone would accept in an
account.

So each day's dollars are converted at that day's rate and the rupee total
is the sum of those, never the dollar total times one number.

Source is Frankfurter (ECB reference rates): free, no key, and it returns a
whole date range in ONE request, so a 90-day page costs one call rather
than ninety. Rates are cached per date in Mongo, so the second page load
costs none.

ECB publishes on business days only. A Saturday has no rate, and the
accounting convention -- the one every ledger uses -- is the most recent
published rate before it. The resolved date travels with the answer so the
page can show which day's rate it actually used, rather than implying a
rate existed on a Sunday.

If the rate cannot be fetched, the answer is None and the page shows
dollars and says the conversion is unavailable. It never invents a rate,
for the same reason an unpriced model is never shown as free.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

COLLECTION = "fx_rates"
SOURCE_URL = "https://api.frankfurter.dev/v1"
BASE, QUOTE = "USD", "INR"

# How far back to look for a published rate when the asked-for day has none
# (a weekend plus a long holiday weekend is the worst realistic case).
MAX_LOOKBACK_DAYS = 7

_db = None


def set_db(db) -> None:
    global _db
    _db = db


def _iso(d) -> str:
    if isinstance(d, (datetime,)):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return str(d)[:10]


async def _cached(start: str, end: str) -> Dict[str, float]:
    if _db is None:
        return {}
    out: Dict[str, float] = {}
    try:
        cur = _db[COLLECTION].find(
            {"pair": f"{BASE}{QUOTE}", "date": {"$gte": start, "$lte": end}},
            {"_id": 0, "date": 1, "rate": 1})
        async for r in cur:
            if isinstance(r.get("rate"), (int, float)):
                out[str(r["date"])] = float(r["rate"])
    except Exception as exc:
        logger.debug("[fx] cache read failed: %r", exc)
    return out


async def _store(rates: Dict[str, float]) -> None:
    if _db is None or not rates:
        return
    try:
        from pymongo import UpdateOne
        ops = [
            UpdateOne(
                {"pair": f"{BASE}{QUOTE}", "date": d},
                {"$set": {"pair": f"{BASE}{QUOTE}", "date": d,
                          "rate": float(v), "source": "frankfurter-ecb",
                          "fetched_at": datetime.now(timezone.utc)}},
                upsert=True)
            for d, v in rates.items()
        ]
        if ops:
            await _db[COLLECTION].bulk_write(ops, ordered=False)
    except Exception as exc:
        logger.debug("[fx] cache write failed: %r", exc)


async def _fetch(start: str, end: str) -> Dict[str, float]:
    """One request for the whole range. Never raises."""
    try:
        import httpx
        url = f"{SOURCE_URL}/{start}..{end}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, params={"base": BASE,
                                              "symbols": QUOTE})
            r.raise_for_status()
            body = r.json()
        out: Dict[str, float] = {}
        for d, v in (body.get("rates") or {}).items():
            val = (v or {}).get(QUOTE)
            if isinstance(val, (int, float)):
                out[str(d)] = float(val)
        return out
    except Exception as exc:
        logger.warning("[fx] could not fetch %s..%s: %r", start, end, exc)
        return {}


async def rates_for_range(start, end) -> Dict[str, float]:
    """Published rates by date for [start, end]. Cache first, then one call.

    Only the gap is fetched, and only when the cache is missing a business
    day inside the range -- which is why the range is re-requested whole
    rather than day by day: the provider charges nothing but the latency is
    per request.
    """
    s, e = _iso(start), _iso(end)
    have = await _cached(s, e)
    # Business days in the window that the cache has no answer for. A
    # weekend gap is expected and must not trigger a fetch every page load.
    d0 = date.fromisoformat(s)
    d1 = date.fromisoformat(e)
    missing_business_day = False
    cur = d0
    while cur <= d1:
        if cur.weekday() < 5 and cur.isoformat() not in have:
            missing_business_day = True
            break
        cur += timedelta(days=1)
    if missing_business_day:
        fetched = await _fetch(s, e)
        if fetched:
            await _store(fetched)
            have.update(fetched)
    return have


def resolve(rates: Dict[str, float], day: str,
            max_lookback: int = MAX_LOOKBACK_DAYS) -> Optional[Dict]:
    """The rate in force on `day`: that day's, or the most recent before it.

    Returns {"rate", "rate_date"} so the page can say which day's rate it
    used. None when nothing is within `max_lookback` -- better no number
    than a stale one presented as the day's.
    """
    try:
        d = date.fromisoformat(str(day)[:10])
    except Exception:
        return None
    for back in range(0, max_lookback + 1):
        k = (d - timedelta(days=back)).isoformat()
        if k in rates:
            return {"rate": rates[k], "rate_date": k}
    return None
