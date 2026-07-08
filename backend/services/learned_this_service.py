"""learned_this_service.py — the "You Learned This" composed surface.

Composes three sources of user-improvement signal that ALREADY exist
into ONE emotional-payoff surface for the home page:

  1. improvement_proof_engine — recent 10 vs previous 10 games,
     per-root-pattern reduction%. Already surfaced (subtly) on
     HomePage as a footnote line. This service promotes it.
  2. motif_recognition (player_profiles) — recognition rate deltas
     per motif, windowed by date_played.
  3. user_concept_understanding — concepts freshly mastered in the
     last N days.

Design rule: this service ADDS NO NEW DETECTION. Every signal it
surfaces is engine-verified already. Its job is composition +
prioritization + framing.

Design rule 2: silence when there's nothing to say. If the user has
no meaningful improvement window (too few games, no significant
delta, no fresh mastery), return has_data=False. Don't manufacture
wins.

See docs/motif_profile_backlog.md and the conversation on 2026-07-08
for the "Card #1: You Learned This" scope.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

# Minimum sample sizes before we'll claim improvement.
MIN_GAMES_TOTAL = 15               # need enough history for a delta at all
MIN_OPPS_PER_MOTIF_WINDOW = 5       # per-motif rate needs ≥5 opps in each window
MIN_MOTIF_DELTA_PP = 8              # +8 percentage points to call it a real jump
CONCEPT_FRESHNESS_DAYS = 30         # a concept mastered in the last 30 days = "new"


def _parse_date(v) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        s = str(v).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _split_by_game_index(by_game: Dict[str, Any], all_games: List[Dict],
                        recent_n: int = 10, older_n: int = 10):
    """Split motif_recognition.by_game into (recent, older) buckets by
    game order (most-recent first). Uses game.date_played so we compare
    real time windows, not just insertion order."""
    # Sort games newest-first
    sorted_games = sorted(
        all_games,
        key=lambda g: _parse_date(g.get("date_played")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    recent_ids = {g.get("game_id") for g in sorted_games[:recent_n]}
    older_ids = {g.get("game_id") for g in sorted_games[recent_n:recent_n + older_n]}
    recent_av, recent_fo = {}, {}
    older_av, older_fo = {}, {}
    for gid, tally in (by_game or {}).items():
        av = tally.get("av") or {}
        fo = tally.get("fo") or {}
        target_av, target_fo = None, None
        if gid in recent_ids:
            target_av, target_fo = recent_av, recent_fo
        elif gid in older_ids:
            target_av, target_fo = older_av, older_fo
        else:
            continue
        for m, v in av.items():
            target_av[m] = target_av.get(m, 0) + v
        for m, v in fo.items():
            target_fo[m] = target_fo.get(m, 0) + v
    return {
        "recent": {"av": recent_av, "fo": recent_fo, "n_games": len(recent_ids)},
        "older": {"av": older_av, "fo": older_fo, "n_games": len(older_ids)},
    }


MOTIF_LABEL = {
    "fork": "Fork spotting",
    "pin": "Pin spotting",
    "skewer": "Skewer spotting",
    "discovered": "Discovered-attack spotting",
    "loose": "Free-piece spotting",
}


def _motif_wins(splits) -> List[Dict[str, Any]]:
    """Compute per-motif recognition rate deltas (recent vs older).
    Return the wins (positive delta), meaningful sample only."""
    wins = []
    for motif, label in MOTIF_LABEL.items():
        r_av = splits["recent"]["av"].get(motif, 0)
        r_fo = splits["recent"]["fo"].get(motif, 0)
        o_av = splits["older"]["av"].get(motif, 0)
        o_fo = splits["older"]["fo"].get(motif, 0)
        if r_av < MIN_OPPS_PER_MOTIF_WINDOW or o_av < MIN_OPPS_PER_MOTIF_WINDOW:
            continue
        r_rate = r_fo / r_av
        o_rate = o_fo / o_av
        delta_pp = round((r_rate - o_rate) * 100)
        if delta_pp < MIN_MOTIF_DELTA_PP:
            continue
        wins.append({
            "type": "motif",
            "key": motif,
            "label": label,
            "from_rate_pct": round(o_rate * 100),
            "to_rate_pct": round(r_rate * 100),
            "delta_pp": delta_pp,
            "recent_opps": r_av,
            "older_opps": o_av,
        })
    wins.sort(key=lambda x: -x["delta_pp"])
    return wins


def _load_principle_names() -> Dict[str, str]:
    """Same catalog InGameMasteryPanel already reads via
    /coach/principles-catalog. Cached at module scope so the hero card
    doesn't re-import PRINCIPLES on every request. Returns concept_id ->
    human-readable name (falls back to the concept_id itself for
    catalog gaps, so the frontend never shows raw TAC_/OP_/MID_ codes).
    """
    global _PRINCIPLE_NAMES
    if _PRINCIPLE_NAMES is not None:
        return _PRINCIPLE_NAMES
    try:
        from services.caption_principles import PRINCIPLES
        _PRINCIPLE_NAMES = {p["id"]: (p.get("name") or p["id"]) for p in PRINCIPLES}
    except Exception:
        _PRINCIPLE_NAMES = {}
    return _PRINCIPLE_NAMES


_PRINCIPLE_NAMES: Optional[Dict[str, str]] = None


def _pretty_concept_name(concept_id: str) -> str:
    """Look up the human name; fall back to a titlecased version of the id."""
    name = _load_principle_names().get(concept_id)
    if name:
        return name
    # Fallback: strip category prefix + titlecase — so unknown ids read
    # as "Rook Open File" instead of "MID_ROOK_OPEN_FILE".
    parts = concept_id.split("_", 1)
    tail = parts[1] if len(parts) > 1 else concept_id
    return tail.replace("_", " ").title()


async def _fresh_mastered_concepts(db, user_id: str, days: int = CONCEPT_FRESHNESS_DAYS) -> List[Dict[str, Any]]:
    """Concepts newly-mastered in the last `days` days — the "you own
    this pattern now" signal. Reads user_concept_understanding.mastered_at.

    Rate over count:
      Mohit 2026-07-08 — "226 clean and all is not worth it, it should
      be percentage of me playing vs opportunities". The mastery gate
      uses a recent-streak criterion (see docs/pwc_mastery_gate_scope.md),
      which means a concept can be flagged 'mastered' with a low
      LIFETIME clean rate. Showing "226 clean" for TAC_HANGING_PIECE at
      25% lifetime clean rate is dishonest coaching.
      Fix (both halves):
        1. Each row carries clean_rate + opportunity_count so the card
           can render "99% clean (291 chances)" instead of raw counts.
        2. STRENGTH_FILTER excludes concepts below CLEAN_RATE_FLOOR from
           the "You Learned This" celebration — those aren't wins to
           surface here. Users can still see them on /progress.
      Sort is by clean_rate DESC — the strongest actual masteries lead.
    """
    CLEAN_RATE_FLOOR = 0.60           # ≥60% lifetime clean rate to count as a real win here
    MIN_OPPORTUNITIES = 20            # need enough sample before the rate is trustworthy

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    async for row in db.user_concept_understanding.find(
        {"user_id": user_id, "mastered_at": {"$ne": None}},
        {"_id": 0, "concept_id": 1, "mastered_at": 1,
         "clean_games_total": 1, "violations_total": 1},
    ).sort("mastered_at", -1).limit(50):
        m_at = _parse_date(row.get("mastered_at"))
        if not m_at or m_at < cutoff:
            continue
        clean = int(row.get("clean_games_total") or 0)
        viol = int(row.get("violations_total") or 0)
        opps = clean + viol
        if opps < MIN_OPPORTUNITIES:
            continue
        rate = clean / opps
        if rate < CLEAN_RATE_FLOOR:
            continue
        cid = row.get("concept_id") or ""
        out.append({
            "type": "concept",
            "concept_id": cid,
            "name": _pretty_concept_name(cid),
            "mastered_at": row.get("mastered_at"),
            "clean_rate_pct": round(rate * 100),
            "opportunity_count": opps,
            # kept for backward compat; frontend prefers clean_rate_pct
            "clean_games_total": clean,
        })
    # Sort by CLEAN RATE desc — strongest genuine masteries lead the list.
    out.sort(key=lambda c: (-c["clean_rate_pct"], -c["opportunity_count"]))
    return out


async def compute_learned_this(db, user_id: str) -> Dict[str, Any]:
    """The composed 'You Learned This' surface for one user.

    Returns:
      has_data: bool
      headline: {label, from, to, unit, kind}  — the ONE biggest win
      wins:     [ {type, ...}, ... ]           — supporting wins
      accuracy: {recent, older, delta}         — from improvement_proof
      window:   {recent_games, older_games}
    """
    # ─── 0. gate: need enough history ───
    n_analyzed = await db.games.count_documents({"user_id": user_id, "is_analyzed": True})
    if n_analyzed < MIN_GAMES_TOTAL:
        return {"has_data": False, "reason": f"need at least {MIN_GAMES_TOTAL} analyzed games (you have {n_analyzed})"}

    # ─── 1. improvement_proof (patterns) ───
    from services.improvement_proof_engine import compute_improvement_proof
    proof = await compute_improvement_proof(db, user_id)
    if not proof.get("has_data"):
        return {"has_data": False, "reason": proof.get("reason", "no improvement_proof data")}

    primary = proof.get("primary_pattern") or {}
    all_patterns = proof.get("all_patterns") or []
    pattern_wins = [
        {
            "type": "pattern",
            "key": p["pattern"],
            "label": p["label"],
            "from_per_game": p["old_per_game"],
            "to_per_game": p["new_per_game"],
            "reduction_pct": p["reduction_pct"],
        }
        for p in all_patterns
        if p.get("trend") == "improving" and p.get("reduction_pct", 0) >= 20
    ]

    # ─── 2. motif recognition deltas ───
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0, "motif_recognition": 1},
    ) or {}
    mr = profile.get("motif_recognition") or {}
    by_game = mr.get("by_game") or {}
    all_games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "date_played": 1},
    ).to_list(500)
    splits = _split_by_game_index(by_game, all_games)
    motif_wins = _motif_wins(splits)

    # ─── 3. concept freshly mastered ───
    concept_wins = await _fresh_mastered_concepts(db, user_id)

    # ─── 4. pick the HEADLINE ───
    # Priority: biggest pattern reduction > biggest motif jump > freshest concept
    headline = None
    if pattern_wins:
        p = pattern_wins[0]
        headline = {
            "kind": "pattern_reduction",
            "label": f"{p['reduction_pct']}% fewer {p['label'].lower()} mistakes",
            "detail": f"{p['from_per_game']} per game → {p['to_per_game']} per game",
            "meta": "Last 10 games vs previous 10",
        }
    elif motif_wins:
        m = motif_wins[0]
        headline = {
            "kind": "motif_gain",
            "label": f"{m['label']} up {m['delta_pp']} points",
            "detail": f"{m['from_rate_pct']}% → {m['to_rate_pct']}%",
            "meta": "Last 10 games vs previous 10",
        }
    elif concept_wins:
        c = concept_wins[0]
        headline = {
            "kind": "concept_mastered",
            "label": f"You mastered {len(concept_wins)} concept{'s' if len(concept_wins) > 1 else ''} this month",
            "detail": None,
            "meta": f"Latest: {c['concept_id']}",
        }

    if not headline:
        return {"has_data": False, "reason": "no meaningful improvement window yet"}

    # ─── 5. supporting wins (excluding whichever became the headline) ───
    supporting = []
    # Accuracy delta ≥ 3 points counts as a real win
    acc = proof.get("accuracy") or {}
    if acc.get("delta", 0) >= 3:
        supporting.append({
            "type": "accuracy",
            "label": f"Accuracy up {acc['delta']} points",
            "detail": f"{acc['older']} → {acc['recent']}",
        })
    # Include the OTHER pattern wins if the headline is a motif or concept
    if headline["kind"] != "pattern_reduction":
        for p in pattern_wins[:2]:
            supporting.append({
                "type": "pattern",
                "label": f"{p['reduction_pct']}% fewer {p['label'].lower()} mistakes",
                "detail": f"{p['from_per_game']} → {p['to_per_game']} per game",
            })
    # Include motif wins (skip the headlined one)
    for m in motif_wins:
        if headline["kind"] == "motif_gain" and m["key"] == headline.get("_key"):
            continue
        supporting.append({
            "type": "motif",
            "label": f"{m['label']} up {m['delta_pp']} pts",
            "detail": f"{m['from_rate_pct']}% → {m['to_rate_pct']}%",
        })
        if len(supporting) >= 5:
            break
    # Include concept masteries as a compact summary — the card expands
    # to show the full list on click, so ship the whole list here (not
    # just the count). Sorted newest-first by mastered_at (already the
    # order from _fresh_mastered_concepts).
    if concept_wins and headline["kind"] != "concept_mastered":
        supporting.append({
            "type": "concept_summary",
            "label": f"{len(concept_wins)} concept{'s' if len(concept_wins) > 1 else ''} mastered this month",
            "detail": None,
            "concepts": [
                {"concept_id": c["concept_id"], "name": c["name"],
                 "mastered_at": c["mastered_at"],
                 "clean_rate_pct": c["clean_rate_pct"],
                 "opportunity_count": c["opportunity_count"]}
                for c in concept_wins
            ],
        })

    return {
        "has_data": True,
        "headline": headline,
        "supporting": supporting[:5],
        "accuracy": acc,
        "window": {
            "recent_games": splits["recent"]["n_games"],
            "older_games": splits["older"]["n_games"],
        },
        "before_after": (proof.get("before_after") or [])[:1],
    }
