"""
Primary Weakness Picker — the "pick ONE thing, lock it, measure it" service.

Consumes move_observations (Theme 1 layer) to pick a single focus per user,
locks it for 14 days, and provides a day-14 outcome check.

See docs/primary_weakness_picker_scope.md for the full design.

Defaults chosen (per Mohit's implicit signoff via "go get it, finish things"):
  - Lock duration: 14 days
  - Improvement threshold: -20% rate change → "improved"
  - Regression threshold: +10% rate change → "regressed"
  - Escalation action: email suggesting Play-with-Coach (no auto-schedule)
  - New user path: minimum 10 analyzed games before assignment
  - Cooldown: 30 days on the same topic after completion

Collection: user_active_focus
Indexes:
  - (user_id, status) — 1 active per user, fast lookup
  - (locked_until) — cron finds focuses ready for outcome check
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

COLLECTION = "user_active_focus"

# ─── Rating-tier-aware impact weights ────────────────────────────────────
# The SAME cognitive_gap tag means different things at different ratings.
# At 1200, "piece_safety" catches literal hanging pieces — highest impact.
# At 1900+, "piece_safety" catches calculation errors in tactical sequences
# — real diagnosis is calculation/tactics/endgame, not "learn to defend."
#
# So the picker weights topics DIFFERENTLY per rating band. A 1900 with
# 127 piece_safety events shouldn't be told "the piece-safety scan" — that
# would insult him AND miss the real diagnosis.
#
# Evidence: Mohit (1270) piece_safety events are 42% opening / 10% captures /
# median 242cp. Parth (1950) events are 24% opening / 8% captures /
# 28% endgame / median 185cp. Same tag, different phenomenon.

RATING_BANDS = {
    "beginner":     {"min": 0,    "max": 1199},
    "intermediate": {"min": 1200, "max": 1599},
    "advanced":     {"min": 1600, "max": 1899},
    "expert":       {"min": 1900, "max": 3000},
}

# Per-band impact weights, keyed by the ACTUAL cognitive_gap tags that
# live in move_observations.missed_pattern. Higher = coach picks it first.
#
# Actual tags in prod:
#   piece_safety, king_safety, piece_activity, missed_tactic,
#   opening_knowledge, tactical_oversight, pawn_structure,
#   calculation_depth, endgame_technique
# Plus synthetic signals:  threat_awareness, punish_blunders
IMPACT_TABLE_BY_BAND: Dict[str, Dict[str, float]] = {
    "beginner": {
        # At sub-1200, piece_safety = literal hangings — the #1 fix
        "piece_safety":                    1.00,
        "king_safety":                     0.85,
        "opening_knowledge":               0.75,   # beginners play random openings
        "missed_tactic":                   0.55,
        "piece_activity":                  0.50,
        "tactical_oversight":              0.45,
        "calculation_depth":               0.40,
        "pawn_structure":                  0.30,
        "endgame_technique":               0.25,   # rarely reach endgames
        "threat_awareness":                0.70,
        "punish_blunders":                 0.55,
    },
    "intermediate": {
        # 1200-1599: piece_safety still primary, but tactics start mattering
        "piece_safety":                    1.00,
        "king_safety":                     0.90,
        "missed_tactic":                   0.75,
        "tactical_oversight":              0.70,
        "calculation_depth":               0.60,
        "piece_activity":                  0.55,
        "opening_knowledge":               0.55,
        "endgame_technique":               0.45,
        "pawn_structure":                  0.40,
        "threat_awareness":                0.80,
        "punish_blunders":                 0.60,
    },
    "advanced": {
        # 1600-1899: piece_safety catches tactical calculation, not literal
        # hangs. King safety + tactics dominate. Endgame technique rises.
        "piece_safety":                    0.55,
        "king_safety":                     0.95,
        "missed_tactic":                   0.90,
        "tactical_oversight":              0.90,
        "calculation_depth":               0.95,
        "piece_activity":                  0.75,
        "endgame_technique":               0.85,
        "pawn_structure":                  0.65,
        "opening_knowledge":               0.30,
        "threat_awareness":                0.90,
        "punish_blunders":                 0.75,
    },
    "expert": {
        # 1900+: piece_safety tag means calculation/tactical errors,
        # NOT dropped pieces. Endgame conversion + calculation depth
        # are the plateau-breakers.
        "piece_safety":                    0.30,   # de-emphasized; almost never literal
        "king_safety":                     1.00,
        "missed_tactic":                   0.95,
        "tactical_oversight":              1.00,
        "calculation_depth":               1.00,
        "piece_activity":                  0.85,
        "endgame_technique":               1.00,   # THE plateau-breaker at 1900+
        "pawn_structure":                  0.75,
        "opening_knowledge":               0.15,   # experts know their openings
        "threat_awareness":                0.90,
        "punish_blunders":                 0.70,
    },
}


def _classify_band(rating: Optional[int]) -> str:
    """Classify a rating into a band. None or missing → intermediate (safe default)."""
    if rating is None:
        return "intermediate"
    for band, r in RATING_BANDS.items():
        if r["min"] <= rating <= r["max"]:
            return band
    return "intermediate"


# ─── Rating confidence ────────────────────────────────────────────────
# Rating is a signal but not a hard input. A "900" account with 5 games
# might be an IM ladder-climbing; a 1900 with 200 games is who they say.
# Confidence = how much we trust the rating as a picker prior.
#
# Thresholds per Mohit's spec (2026-07-02):
#   <10 games   → unreliable  (ignore rating; evidence-only)
#   10-25 games → low         (rating prior dampened to 0.5×)
#   >25 games   → high        (full 1.0× rating prior)

def _classify_rating_confidence(game_count: int) -> str:
    if game_count < 10:
        return "unreliable"
    if game_count <= 25:
        return "low"
    return "high"


_CONFIDENCE_MULTIPLIER = {
    "unreliable": 0.0,
    "low":        0.5,
    "high":       1.0,
}

# ─── Severity weights for scoring ─────────────────────────────────────
# Applied to each observation's severity when computing the picker score.
# 40 critical simple_hangs (× 3.0) = 120  beats
# 100 minor small_slips  (× 0.5) = 50
_SEVERITY_WEIGHT = {
    "critical": 3.0,
    "moderate": 1.5,
    "minor":    0.5,
    None:       1.0,   # topic without subtype/severity yet (e.g., king_safety pre-v5)
}


# ─── Evidence-driven narrative generator ──────────────────────────────
# Replaces the deleted DIAGNOSTIC_NARRATIVES template dict.
# Reads the user's actual subtype histogram + rating band, and speaks
# to what THAT PERSON'S DATA shows — not a hardcoded per-tier script.

_PS_SUBTYPE_PHRASING = {
    "simple_hang":       "board-verified piece drops (attackers > defenders on the destination)",
    "threat_ignored":    "missed opponent threats you had time to see",
    "tactical_seq_loss": "miscalculations inside your own forcing sequences",
    "quiet_blunder":     "non-forcing high-cost mistakes that weren't literal hangs",
    "small_slip":        "small slips (<200cp — background noise)",
}

# Human-readable plural noun for each subtype (avoids "losss" from naive +s)
_PS_SUBTYPE_PLURAL = {
    "simple_hang":       "simple hangs",
    "threat_ignored":    "ignored threats",
    "tactical_seq_loss": "tactical-sequence losses",
    "quiet_blunder":     "quiet-position blunders",
    "small_slip":        "small slips",
}


def _tier_closing(band: str, dominant_subtype: str, rating: Optional[int]) -> str:
    """The one-line closing coaching instruction, band-aware but data-driven."""
    r_str = f"At {rating}, " if rating else ""
    if dominant_subtype == "simple_hang":
        if band in ("beginner", "intermediate"):
            return "Before every move, ask: can this piece be taken?"
        # advanced / expert
        return (f"{r_str}dropping pieces in quiet positions is a scanning gap, "
                "not a calculation gap. Slow down on quiet moves.")
    if dominant_subtype == "tactical_seq_loss":
        return "You start a forcing sequence without seeing the last move. Walk every capture to the end."
    if dominant_subtype == "threat_ignored":
        return "When the opponent moves, first ask: what does this threaten?"
    return "Focus on the pattern above; coaching cards will drill in."


def build_narrative_from_evidence(
    topic: str,
    signals: Dict[str, Any],
    band: str,
    rating: Optional[int],
    n_games: int,
) -> Dict[str, Any]:
    """Generate {label, narrative, subtype_histogram} for a topic using
    ONLY the user's own histogram.

    Rules:
      - Lead with topic + event count + games
      - Feature the dominant MEANINGFUL subtype (not small_slip if there's
        another with ≥15% share)
      - Mention secondary meaningful subtypes only if ≥10%
      - Suppress small_slip from the story unless it's the ONLY thing
      - Closing = tier-aware line targeting the dominant meaningful subtype
      - Label = "{topic} ({X}% critical)" for the focus card badge
    """
    subtypes = (signals.get("pattern_subtype_severity") or {}).get(topic) or {}
    flat: Dict[str, Dict[str, Any]] = {}
    total = 0
    for st, sev_counts in subtypes.items():
        n = sum(sev_counts.values())
        total += n
        dom_sev = max(sev_counts.items(), key=lambda x: x[1])[0] if sev_counts else None
        flat[st] = {"count": n, "dominant_severity": dom_sev, "severity_breakdown": sev_counts}

    if total == 0:
        label = topic.replace("_", " ").title()
        return {
            "label": label,
            "narrative": (f"{label} is your top pattern based on evidence. "
                          f"Detailed subtype breakdown will populate as more games get analyzed."),
            "subtype_histogram": {},
            "total_events": 0,
        }

    ordered = sorted(flat.items(), key=lambda kv: -kv[1]["count"])
    # Meaningful = anything except small_slip
    meaningful = [(st, d) for st, d in ordered if st != "small_slip"]
    dominant_meaningful = meaningful[0] if meaningful else ordered[0]
    dominant_subtype = dominant_meaningful[0]
    dominant_data = dominant_meaningful[1]

    topic_h = topic.replace("_", " ")
    parts: List[str] = [
        f"{topic_h.capitalize()} is your top pattern — {total} events across {n_games} games."
    ]

    def _subtype_label(st: str) -> str:
        return _PS_SUBTYPE_PLURAL.get(st, st.replace("_", " ") + "s")

    # Feature the dominant meaningful subtype
    dm_pct = round(100 * dominant_data["count"] / total)
    dm_n = dominant_data["count"]
    dm_phrase = _PS_SUBTYPE_PHRASING.get(dominant_subtype, dominant_subtype.replace("_", " "))
    dm_sev = dominant_data.get("dominant_severity")
    sev_tag = f" ({dm_sev})" if dm_sev and dm_sev != "minor" else ""
    parts.append(f"{dm_pct}% of them ({dm_n} events) are {_subtype_label(dominant_subtype)} — {dm_phrase}{sev_tag}.")

    # Mention secondary meaningful subtypes ≥10%
    for st, data in meaningful[1:3]:
        pct = round(100 * data["count"] / total)
        if pct < 10:
            continue
        phrase = _PS_SUBTYPE_PHRASING.get(st, st.replace("_", " "))
        sev = data.get("dominant_severity")
        s_tag = f" ({sev})" if sev and sev != "minor" else ""
        parts.append(f"Another {pct}% are {_subtype_label(st)} — {phrase}{s_tag}.")

    parts.append(_tier_closing(band, dominant_subtype, rating))

    # Label = "{topic} ({X}% critical)" — but only if there IS critical share
    critical_n = sum(d["count"] for _, d in flat.items() if d["dominant_severity"] == "critical")
    critical_pct = round(100 * critical_n / total)
    if critical_pct > 0:
        label = f"{topic_h.capitalize()} ({critical_pct}% critical)"
    else:
        label = topic_h.capitalize()

    return {
        "label": label,
        "narrative": " ".join(parts),
        "subtype_histogram": flat,
        "total_events": total,
    }


# Legacy IMPACT_TABLE kept for backward compat (defaults to intermediate)
IMPACT_TABLE: Dict[str, float] = IMPACT_TABLE_BY_BAND["intermediate"]

# Topic → moments_topic_registry key (some subcategories map to same page)
TOPIC_TO_MOMENTS_KEY: Dict[str, str] = {
    "piece_safety":                    "piece_safety",
    "ignoring_king_safety_threats":    "piece_safety",  # same page for now
    "fork_misses":                     "piece_safety",
    "discovered_attack_misses":        "piece_safety",
    "removal_of_defender_misses":      "piece_safety",
    "neglecting_development":          "piece_safety",  # placeholder until per-topic pages
    "poor_piece_activity":             "piece_safety",
    "pawn_structure_damage":           "piece_safety",
    "king_activity_neglect":           "long_game_conversion",
    "threat_awareness":                "piece_safety",
    "punish_blunders":                 "piece_safety",
}

MIN_EVIDENCE = 3           # a pattern needs ≥3 occurrences to be pickable
MIN_ANALYZED_GAMES = 10    # user must have ≥10 analyzed games
LOCK_DURATION_DAYS = 14
COOLDOWN_DAYS = 30
IMPROVEMENT_THRESHOLD = -0.20
REGRESSION_THRESHOLD = +0.10
BASELINE_WINDOW_GAMES = 30


async def ensure_indexes(db) -> None:
    coll = db[COLLECTION]
    await coll.create_index([("user_id", 1), ("status", 1)])
    await coll.create_index([("locked_until", 1)])
    await coll.create_index([("user_id", 1), ("topic_key", 1)])


async def _get_active_focus(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Return the active WEAKNESS focus. The collection also stores
    strength focuses (type='strength') — those must not block weakness
    assignment, so we filter to type='weakness' (or no type field, which
    is the legacy shape from before the strength picker landed)."""
    return await db[COLLECTION].find_one({
        "user_id": user_id, "status": "active",
        "$or": [{"type": {"$exists": False}}, {"type": "weakness"}],
    })


async def _get_cohort_signals(db, user_id: str) -> Dict[str, Any]:
    """Compute the aggregate signals from this user's move_observations.

    Cap at 25000 obs (~1000 games) — enough to cover our largest users
    (Mohit has 15k, Parth 6k). Any user hitting the cap should switch to
    server-side aggregation, but at current scale in-memory is fine."""
    from services.move_observation_deriver import aggregate_user_signals
    obs = await db.move_observations.find({"user_id": user_id}).to_list(length=25000)
    return aggregate_user_signals(obs), len(obs)


async def _resolve_user_rating(db, user_id: str) -> Optional[int]:
    """Get the user's current rating for band classification.
    Prefers rating_resolver if available, falls back to user_doc + profile."""
    try:
        from services.rating_resolver import get_current_rating
        user_doc = await db.users.find_one({"user_id": user_id}) or {}
        profile_doc = await db.player_profiles.find_one({"user_id": user_id}) or {}
        return get_current_rating(user_doc, profile_doc)
    except Exception:
        # Fallback: median of recent user_rating on games
        ratings = []
        async for g in db.games.find(
            {"user_id": user_id, "user_rating": {"$ne": None}},
            {"user_rating": 1},
        ).sort("date_played", -1).limit(20):
            r = g.get("user_rating")
            if isinstance(r, (int, float)) and r > 0:
                ratings.append(int(r))
        if not ratings:
            return None
        return sorted(ratings)[len(ratings) // 2]


async def _in_cooldown(db, user_id: str, topic: str) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=COOLDOWN_DAYS)).isoformat()
    prev = await db[COLLECTION].find_one({
        "user_id": user_id,
        "topic_key": topic,
        "status": {"$in": ["completed", "escalated"]},
        "closed_at": {"$gte": cutoff},
    })
    return prev is not None


async def _compute_baseline_metric(db, user_id: str, topic: str) -> Dict[str, Any]:
    """Baseline per-game rate — total occurrences divided by total analyzed
    games. Simple + correct. Previous version divided by a capped n which
    made rates 30x too high."""
    games_analyzed = await db.games.count_documents(
        {"user_id": user_id, "is_analyzed": True}
    )
    total = await db.move_observations.count_documents({
        "user_id": user_id,
        "missed_pattern": topic,
    })
    rate = round(total / max(games_analyzed, 1), 3)
    return {
        "name": f"{topic}_per_game",
        "value": rate,
        "occurrence_count": total,
        "n_games_at_baseline": games_analyzed,
    }


def _severity_weighted_count(subtypes_dict: Dict[str, Dict[str, int]]) -> float:
    """Sum count × severity_weight across all subtypes of a pattern.
    subtypes_dict shape: {subtype: {severity: count}}"""
    total = 0.0
    for _, sev_counts in subtypes_dict.items():
        for sev, n in sev_counts.items():
            total += n * _SEVERITY_WEIGHT.get(sev, 1.0)
    return total


async def pick_next_focus(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Returns the topic dict to lock, or None if we shouldn't assign yet.

    Scoring per docs/piece_safety_subtype_scope.md:
        score = severity_weighted_count(pattern)
              × rating_prior(band, pattern)
              × confidence_multiplier(game_count)

    Rating is a signal, not a hard input. Evidence dominates.
    """
    # Gate 1: don't pick if user already has an active focus
    if await _get_active_focus(db, user_id):
        return None

    # Gate 2: enough analyzed games
    n_games = await db.games.count_documents({"user_id": user_id, "is_analyzed": True})
    if n_games < MIN_ANALYZED_GAMES:
        return None

    # Signals from move_observations
    signals, n_obs = await _get_cohort_signals(db, user_id)
    if n_obs == 0:
        return None

    total_user_moves = max(signals.get("total_user_moves", 1), 1)

    # Resolve rating + confidence. If confidence is unreliable, the rating
    # prior gets muted and evidence carries the ranking alone.
    rating = await _resolve_user_rating(db, user_id)
    band = _classify_band(rating)
    confidence = _classify_rating_confidence(n_games)
    conf_mult = _CONFIDENCE_MULTIPLIER[confidence]
    impact_table = IMPACT_TABLE_BY_BAND[band]

    def rating_prior(topic: str) -> float:
        """Soft rating prior in [0.5, 1.5] — a nudge, not a crush.

        Evidence has to be able to win over a low band weight. If Parth
        has 51 critical simple_hangs, we WANT the coach to see them even
        though the expert band deprioritizes piece_safety as a class.
        """
        band_weight = impact_table.get(topic, 0.3)
        # Half-strength influence of band_weight, dampened by confidence
        delta = conf_mult * (band_weight - 1.0) * 0.5
        return max(0.5, min(1.5, 1.0 + delta))

    # Build candidate list
    pattern_subtypes = signals.get("pattern_subtype_severity") or {}
    candidates: List[Dict[str, Any]] = []
    for pattern, count in (signals.get("missed_pattern_counts") or {}).items():
        if count < MIN_EVIDENCE:
            continue
        # Severity-weighted count if we have subtype data; else fall back to raw count
        if pattern in pattern_subtypes:
            weighted = _severity_weighted_count(pattern_subtypes[pattern])
        else:
            weighted = count * 1.0
        prior = rating_prior(pattern)
        score = weighted * prior
        candidates.append({
            "topic": pattern,
            "score": round(score, 3),
            "evidence_count": count,
            "severity_weighted_count": round(weighted, 2),
            "per_100_moves": round(count / total_user_moves * 100, 2),
            "impact_weight": impact_table.get(pattern, 0.3),
            "rating_prior": round(prior, 3),
        })

    # Positive-signal gaps (things user DOESN'T do enough of).
    # No subtype data on these — score them by miss rate × rating_prior.
    threat_rate = signals.get("threat_response_rate")
    if threat_rate is not None and threat_rate < 0.7:
        n_ignored = signals.get("ignored_opponent_threat", 0)
        prior = rating_prior("threat_awareness")
        candidates.append({
            "topic": "threat_awareness",
            "score": round((1 - threat_rate) * 100 * prior, 3),
            "evidence_count": n_ignored,
            "severity_weighted_count": None,
            "per_100_moves": None,
            "impact_weight": impact_table["threat_awareness"],
            "rating_prior": round(prior, 3),
        })
    punish_rate = signals.get("blunder_punish_rate")
    if punish_rate is not None and punish_rate < 0.5:
        n_missed = signals.get("missed_opponent_blunder", 0)
        prior = rating_prior("punish_blunders")
        candidates.append({
            "topic": "punish_blunders",
            "score": round((1 - punish_rate) * 100 * prior, 3),
            "evidence_count": n_missed,
            "severity_weighted_count": None,
            "per_100_moves": None,
            "impact_weight": impact_table["punish_blunders"],
            "rating_prior": round(prior, 3),
        })

    # Cooldown filter
    fresh = []
    for c in candidates:
        if not await _in_cooldown(db, user_id, c["topic"]):
            fresh.append(c)
    if not fresh:
        return None

    # Sort desc by score.
    fresh.sort(key=lambda c: -c["score"])
    winner = fresh[0]

    # Evidence-driven narrative from THIS user's own subtype histogram
    narrative_pack = build_narrative_from_evidence(
        winner["topic"], signals, band, rating, n_games,
    )

    winner["rating_band"] = band
    winner["rating_used"] = rating
    winner["rating_confidence"] = confidence
    winner["coaching_label"] = narrative_pack["label"]
    winner["coaching_narrative"] = narrative_pack["narrative"]
    winner["subtype_histogram"] = narrative_pack["subtype_histogram"]

    winner["runners_up"] = [
        {
            "topic": c["topic"],
            "score": c["score"],
            "evidence_count": c["evidence_count"],
            "coaching_label": build_narrative_from_evidence(
                c["topic"], signals, band, rating, n_games
            )["label"],
        }
        for c in fresh[1:4]
    ]
    return winner


async def assign_focus(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Pick + persist. Returns the created focus doc or None."""
    picked = await pick_next_focus(db, user_id)
    if not picked:
        return None
    now = datetime.now(timezone.utc)
    baseline = await _compute_baseline_metric(db, user_id, picked["topic"])
    focus = {
        "user_id": user_id,
        "type": "weakness",
        "status": "active",
        "topic_key": picked["topic"],
        "moments_page_topic": TOPIC_TO_MOMENTS_KEY.get(picked["topic"], "piece_safety"),
        "picker_score": picked["score"],
        "picker_evidence_count": picked["evidence_count"],
        "picker_per_100_moves": picked.get("per_100_moves"),
        "picker_impact_weight": picked.get("impact_weight"),
        # Rating-tier-aware coaching (same tag ≠ same coaching)
        "rating_band": picked.get("rating_band"),
        "rating_used": picked.get("rating_used"),
        "rating_confidence": picked.get("rating_confidence"),
        "coaching_label": picked.get("coaching_label"),
        "coaching_narrative": picked.get("coaching_narrative"),
        "subtype_histogram": picked.get("subtype_histogram"),
        "severity_weighted_count": picked.get("severity_weighted_count"),
        "runners_up": picked.get("runners_up", []),
        "started_at": now.isoformat(),
        "locked_until": (now + timedelta(days=LOCK_DURATION_DAYS)).isoformat(),
        "baseline_metric": baseline,
        "current_metric": None,
        "resolution": None,
        "next_action": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    await db[COLLECTION].insert_one(focus)
    return focus


async def check_focus_outcome(db, focus: Dict[str, Any]) -> Dict[str, Any]:
    """Called at locked_until. Returns {resolution, action, delta_pct}."""
    topic = focus["topic_key"]
    user_id = focus["user_id"]
    started_at = focus["started_at"]
    baseline_rate = focus["baseline_metric"]["value"]

    # Games analyzed since lock started
    games_since = await db.games.count_documents({
        "user_id": user_id,
        "is_analyzed": True,
        "analyzed_at": {"$gte": started_at},
    })
    if games_since == 0:
        return {"resolution": "no_data", "action": "extend", "delta_pct": None}

    obs_since = await db.move_observations.find({
        "user_id": user_id,
        "missed_pattern": topic,
        "derived_at": {"$gte": started_at},
    }).to_list(length=None)
    current_rate = len(obs_since) / games_since
    delta = (current_rate - baseline_rate) / max(baseline_rate, 0.01)

    if delta <= IMPROVEMENT_THRESHOLD:
        return {"resolution": "improved", "action": "celebrate",
                "delta_pct": round(delta * 100, 1),
                "current_metric": {"value": round(current_rate, 3),
                                   "n_games_since_start": games_since}}
    if delta >= REGRESSION_THRESHOLD:
        return {"resolution": "regressed", "action": "escalate",
                "delta_pct": round(delta * 100, 1),
                "current_metric": {"value": round(current_rate, 3),
                                   "n_games_since_start": games_since}}
    return {"resolution": "stuck", "action": "extend",
            "delta_pct": round(delta * 100, 1),
            "current_metric": {"value": round(current_rate, 3),
                               "n_games_since_start": games_since}}


async def close_focus(db, focus: Dict[str, Any], outcome: Dict[str, Any]) -> None:
    """Mark a focus completed with outcome data."""
    now = datetime.now(timezone.utc).isoformat()
    status = "completed" if outcome["action"] == "celebrate" else \
             "escalated" if outcome["action"] == "escalate" else "active"
    update = {
        "$set": {
            "resolution": outcome["resolution"],
            "next_action": outcome["action"],
            "current_metric": outcome.get("current_metric"),
            "updated_at": now,
        }
    }
    if status != "active":
        update["$set"]["status"] = status
        update["$set"]["closed_at"] = now
    else:
        # Extend the lock by another 7 days
        new_until = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        update["$set"]["locked_until"] = new_until
    await db[COLLECTION].update_one({"_id": focus["_id"]}, update)
