"""What the LLM is costing, by day, by surface, and by user.

Mohit asked for the money side. The honest starting point is that nothing
was recorded before `services/llm_usage.py` shipped: both provider calls
received a `usage` object and dropped it. So this page can only report from
the day the recorder went live, and it says so rather than showing an
empty chart that reads like a zero bill.

Cost is recomputed here from `data/llm_prices.json` rather than summed from
the value stored on each row. Correcting a price then fixes the whole
history at once, and nobody has to trust a multiplication done months ago
at a rate that has since changed.

A model with no price shows its tokens and `price_set: false`. It is never
counted as zero dollars -- an unpriced model that reads as free is how a
page looks healthy while understating the invoice.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from routes.admin import require_admin
from routes.auth import User
from services import llm_usage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin"])

_db = None


def set_db(db) -> None:
    global _db
    _db = db
    llm_usage.set_db(db)


def _priced(model: str, inp: int, out: int, cached: int) -> Dict[str, Any]:
    cost = llm_usage.cost_usd(model, inp, out, cached)
    return {
        "input_tokens": int(inp),
        "output_tokens": int(out),
        "cached_input_tokens": int(cached),
        "cost_usd": cost,
        "price_set": cost is not None,
    }


async def _group(field: str, since: datetime,
                 limit: int = 0) -> List[Dict[str, Any]]:
    """Totals per value of `field`, priced per MODEL then folded up.

    Grouping by the field alone and pricing afterwards would need one rate
    for a mixed bag of models, so the model stays in the group key and the
    rows are combined here.
    """
    pipeline = [
        {"$match": {"ts": {"$gte": since}}},
        {"$group": {
            "_id": {"k": f"${field}", "model": "$model"},
            "input_tokens": {"$sum": "$input_tokens"},
            "output_tokens": {"$sum": "$output_tokens"},
            "cached_input_tokens": {"$sum": "$cached_input_tokens"},
            "calls": {"$sum": 1},
        }},
    ]
    rows: Dict[Any, Dict[str, Any]] = {}
    async for r in _db[llm_usage.COLLECTION].aggregate(pipeline):
        key = r["_id"].get("k")
        model = r["_id"].get("model") or "unknown"
        p = _priced(model, r["input_tokens"], r["output_tokens"],
                    r["cached_input_tokens"])
        slot = rows.setdefault(key, {
            "key": key, "calls": 0, "input_tokens": 0, "output_tokens": 0,
            "cached_input_tokens": 0, "cost_usd": 0.0,
            "models": [], "unpriced_models": [],
        })
        slot["calls"] += r["calls"]
        slot["input_tokens"] += p["input_tokens"]
        slot["output_tokens"] += p["output_tokens"]
        slot["cached_input_tokens"] += p["cached_input_tokens"]
        if model not in slot["models"]:
            slot["models"].append(model)
        if p["price_set"]:
            slot["cost_usd"] += float(p["cost_usd"] or 0.0)
        elif model not in slot["unpriced_models"]:
            slot["unpriced_models"].append(model)
    out = sorted(rows.values(),
                 key=lambda r: (r["cost_usd"], r["input_tokens"]),
                 reverse=True)
    return out[:limit] if limit else out


@router.get("/admin/llm-cost/summary")
async def llm_cost_summary(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Spend over the window, by day, by model, by surface, and top users."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    coll = _db[llm_usage.COLLECTION]

    total_calls = await coll.count_documents({"ts": {"$gte": since}})
    first = await coll.find_one({}, {"ts": 1, "_id": 0}, sort=[("ts", 1)])

    by_day_raw = [
        {"_id": {"k": {"$dateToString": {"format": "%Y-%m-%d",
                                         "date": "$ts"}},
                 "model": "$model"}}
    ]
    # by_day needs the formatted date as the group key, so it cannot reuse
    # _group's single-field path; the aggregation is written out once here.
    pipeline = [
        {"$match": {"ts": {"$gte": since}}},
        {"$group": {
            "_id": {"k": {"$dateToString": {"format": "%Y-%m-%d",
                                            "date": "$ts"}},
                    "model": "$model"},
            "input_tokens": {"$sum": "$input_tokens"},
            "output_tokens": {"$sum": "$output_tokens"},
            "cached_input_tokens": {"$sum": "$cached_input_tokens"},
            "calls": {"$sum": 1},
        }},
    ]
    days_map: Dict[str, Dict[str, Any]] = {}
    async for r in coll.aggregate(pipeline):
        key = r["_id"].get("k")
        model = r["_id"].get("model") or "unknown"
        p = _priced(model, r["input_tokens"], r["output_tokens"],
                    r["cached_input_tokens"])
        slot = days_map.setdefault(key, {
            "key": key, "calls": 0, "input_tokens": 0, "output_tokens": 0,
            "cached_input_tokens": 0, "cost_usd": 0.0,
            "unpriced_models": [],
        })
        slot["calls"] += r["calls"]
        slot["input_tokens"] += p["input_tokens"]
        slot["output_tokens"] += p["output_tokens"]
        slot["cached_input_tokens"] += p["cached_input_tokens"]
        if p["price_set"]:
            slot["cost_usd"] += float(p["cost_usd"] or 0.0)
        elif model not in slot["unpriced_models"]:
            slot["unpriced_models"].append(model)

    by_model = await _group("model", since)
    by_surface = await _group("surface", since)
    top_users = await _group("user_id", since, limit=25)

    priced_total = sum(r["cost_usd"] for r in by_model)
    unpriced = sorted({m for r in by_model for m in r["unpriced_models"]})

    return {
        "window_days": days,
        "recording_since": first.get("ts").isoformat() if first else None,
        # The one number that must not be mistaken for the whole bill.
        "covers_history": bool(first),
        "total_calls": total_calls,
        "total_cost_usd": round(priced_total, 4),
        "models_without_a_price": unpriced,
        "cost_excludes_unpriced_models": bool(unpriced),
        "by_day": sorted(days_map.values(), key=lambda r: r["key"]),
        "by_model": by_model,
        "by_surface": by_surface,
        "top_users": top_users,
        "price_table": (llm_usage.load_prices(refresh=True)
                        .get("models") or {}),
    }


@router.get("/admin/llm-cost/user/{user_id}")
async def llm_cost_for_user(
    user_id: str,
    days: int = Query(90, ge=1, le=365),
    user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """One user's spend, split by surface, with their recent calls."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    coll = _db[llm_usage.COLLECTION]
    pipeline = [
        {"$match": {"ts": {"$gte": since}, "user_id": user_id}},
        {"$group": {
            "_id": {"k": "$surface", "model": "$model"},
            "input_tokens": {"$sum": "$input_tokens"},
            "output_tokens": {"$sum": "$output_tokens"},
            "cached_input_tokens": {"$sum": "$cached_input_tokens"},
            "calls": {"$sum": 1},
        }},
    ]
    rows: Dict[Any, Dict[str, Any]] = {}
    async for r in coll.aggregate(pipeline):
        key = r["_id"].get("k")
        model = r["_id"].get("model") or "unknown"
        p = _priced(model, r["input_tokens"], r["output_tokens"],
                    r["cached_input_tokens"])
        slot = rows.setdefault(key, {"key": key, "calls": 0,
                                     "input_tokens": 0, "output_tokens": 0,
                                     "cached_input_tokens": 0,
                                     "cost_usd": 0.0,
                                     "unpriced_models": []})
        slot["calls"] += r["calls"]
        slot["input_tokens"] += p["input_tokens"]
        slot["output_tokens"] += p["output_tokens"]
        slot["cached_input_tokens"] += p["cached_input_tokens"]
        if p["price_set"]:
            slot["cost_usd"] += float(p["cost_usd"] or 0.0)
        elif model not in slot["unpriced_models"]:
            slot["unpriced_models"].append(model)

    recent: List[Dict[str, Any]] = []
    async for r in coll.find(
            {"ts": {"$gte": since}, "user_id": user_id},
            {"_id": 0}).sort("ts", -1).limit(50):
        r["ts"] = r["ts"].isoformat() if hasattr(r.get("ts"), "isoformat") \
            else r.get("ts")
        recent.append(r)

    by_surface = sorted(rows.values(), key=lambda r: r["cost_usd"],
                        reverse=True)
    return {
        "user_id": user_id,
        "window_days": days,
        "total_cost_usd": round(sum(r["cost_usd"] for r in by_surface), 4),
        "total_calls": sum(r["calls"] for r in by_surface),
        "by_surface": by_surface,
        "recent_calls": recent,
    }
