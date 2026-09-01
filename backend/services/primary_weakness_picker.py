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
from bson import ObjectId

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
    # time_management subtypes (v9)
    "impulsive_critical":     "critical moments played in under 3 seconds that turned into mistakes",
    "time_pressure_blunder":  "blunders you made under 30 seconds on the clock",
    "slow_paralysis":         "routine moves you spent more than 90 seconds on and then blundered later",
    "chronic_timeout":        "games you lost on the clock instead of on the board",
    # piece_safety subtypes (from move_observation_deriver piece_safety classifier)
    "simple_hang":       "board-verified piece drops (attackers > defenders on the destination)",
    "destination_safety_exact": "moves where the opponent could immediately take the exact piece you just moved",
    "threat_ignored":    "missed opponent threats you had time to see",
    "tactical_seq_loss": "miscalculations inside your own forcing sequences",
    "quiet_blunder":     "non-forcing high-cost mistakes that weren't literal hangs",
    "small_slip":        "small slips (<200cp — background noise)",
    # king_safety subtypes
    "king_walked_into_attack": "king moves onto squares your opponent attacks more than you defend",
    "ignored_king_attack":     "moves where your opponent had pieces near your king and you didn't defend",
    "king_in_center":          "positions where your king sat on its starting square past move 12 in an open game",
    "weakened_shelter":        "pawn pushes near your king that opened lines for opposing attackers",
    # missed_tactic subtypes
    "missed_fork":             "positions where the best move forked two of your opponent's pieces",
    "missed_pin":              "positions where the best move pinned an opponent piece",
    "missed_skewer":           "positions where the best move skewered opponent pieces",
    "missed_discovered_attack":"positions where the best move uncovered a discovered attack",
    "missed_generic_tactic":   "positions with a strong tactical shot you didn't play",
    # tactical_oversight subtypes
    "ignored_forcing_threat":  "moments the opponent had just made a forcing move you didn't address",
    "overlooked_immediate_reply":"moves where your opponent's next reply was obviously strong and you missed it",
    "generic_oversight":       "tactical oversights (a good move exists but you didn't see it)",
    # calculation_depth subtypes
    "shallow_horizon_2ply":    "positions where your opponent had a forcing 2-move win you didn't foresee",
    "broken_forcing_sequence": "your own forcing sequences that fell apart before completion",
    "generic_calc_gap":        "positions where deeper calculation would have found a better move",
    # piece_activity subtypes
    "queen_out_early":         "early queen moves before your minor pieces were developed",
    "piece_parked_on_start":   "pieces that stayed on their starting square well past the opening",
    # opening_knowledge subtypes
    "tempo_wasted_by_repeat":  "opening tempi lost by moving the same piece twice",
    "early_flank_pawn_move":   "flank pawn pushes in the first eight moves",
    # endgame_technique subtypes
    "passive_king_in_endgame": "endgames where your king stayed passive while your opponent's king centralized",
    "passed_pawn_ignored":     "positions where your opponent had a passed pawn advancing and you didn't stop it",
    "generic_endgame_slip":    "endgame moments where precision was needed and missed",
    # pawn_structure subtypes
    "isolated_pawn_created":   "pawn moves that created isolated pawns in your structure",
    "doubled_pawn_created":    "moves that gave you doubled pawns",
    "backward_pawn_created":   "moves that left a pawn backward — unsupported and blocked by an opposing pawn",
    "generic_structure_slip":  "pawn moves that weakened your structure",
    # soft fallback
    "unverified_hint":         "moves flagged as this pattern but not board-provable to a specific subtype",
}

_PS_SUBTYPE_PLURAL = {
    "impulsive_critical":     "impulsive critical-moment moves",
    "time_pressure_blunder":  "time-pressure blunders",
    "slow_paralysis":         "slow-paralysis blunders",
    "chronic_timeout":        "games lost on time",
    "simple_hang":            "simple hangs",
    "destination_safety_exact":"pieces left for an immediate capture",
    "threat_ignored":         "ignored threats",
    "tactical_seq_loss":      "tactical-sequence losses",
    "quiet_blunder":          "quiet-position blunders",
    "small_slip":             "small slips",
    "king_walked_into_attack":"king walks into attack",
    "ignored_king_attack":    "ignored king attacks",
    "king_in_center":         "king-in-center moments",
    "weakened_shelter":       "shelter weakenings",
    "missed_fork":            "missed forks",
    "missed_pin":             "missed pins",
    "missed_skewer":          "missed skewers",
    "missed_discovered_attack":"missed discovered attacks",
    "missed_generic_tactic":  "missed tactics",
    "ignored_forcing_threat": "ignored forcing threats",
    "overlooked_immediate_reply":"overlooked immediate replies",
    "generic_oversight":      "tactical oversights",
    "shallow_horizon_2ply":   "shallow horizon (2-ply) losses",
    "broken_forcing_sequence":"broken forcing sequences",
    "generic_calc_gap":       "calculation gaps",
    "queen_out_early":        "early queen moves",
    "piece_parked_on_start":  "parked pieces",
    "tempo_wasted_by_repeat": "wasted opening tempi",
    "early_flank_pawn_move":  "early flank-pawn moves",
    "passive_king_in_endgame":"passive-king endgames",
    "passed_pawn_ignored":    "ignored passed pawns",
    "generic_endgame_slip":   "endgame slips",
    "isolated_pawn_created":  "isolated-pawn creations",
    "doubled_pawn_created":   "doubled-pawn creations",
    "backward_pawn_created":  "backward-pawn creations",
    "generic_structure_slip": "structural slips",
    "unverified_hint":        "unverified hints",
}


# Sprint 2 (docs/one_surviving_instruction_scope.md): bump this whenever
# _CLOSING_BY_SUBTYPE's TEXT is edited, so an already-assigned focus's
# instruction_version stays a true record of which wording it was given,
# even after the template changes. Editing text without bumping this is
# the one way this contract can silently break -- new assignments keep
# citing the old version number for wording they never actually showed.
INSTRUCTION_TEMPLATE_VERSION = 2

_CLOSING_BY_SUBTYPE = {
    # time_management
    "impulsive_critical":     "On any critical moment, force yourself to spend at least 10 seconds before you move. The best move is worth the clock.",
    "time_pressure_blunder":  "When your clock drops under a minute, simplify — trade pieces, play safe, don't hunt for the perfect move.",
    "slow_paralysis":         "If you've spent 90+ seconds on a move that isn't critical, pick a reasonable one and move — the analysis paralysis is costing you later.",
    "chronic_timeout":        "You're losing more games on the clock than to your opponent's moves. That's a habit fix — play faster on quiet moves, save clock for real decisions.",
    # piece_safety
    "simple_hang":            "Before every move, ask: can this piece be taken?",
    "destination_safety_exact":"After choosing your move, ask: can they take the piece I just moved?",
    "tactical_seq_loss":      "You start a forcing sequence without seeing the last move. Walk every capture to the end.",
    "threat_ignored":         "When the opponent moves, first ask: what does this threaten?",
    "quiet_blunder":          "Not all mistakes are hanging pieces — sometimes it's a strategic misjudgment. Notice when the position looks 'quiet' and slow down.",
    # king_safety
    "king_walked_into_attack":"Before you move the king, count attackers and defenders on the destination.",
    "ignored_king_attack":    "When there are opponent pieces near your king, defense comes before attack.",
    "king_in_center":         "Get the king to safety early — castle by move 12 unless the position screams otherwise.",
    "weakened_shelter":       "Pushing pawns near your castled king opens lines for their pieces. Ask what attackers get a new file or diagonal.",
    # missed_tactic
    "missed_fork":            "On every move, scan for pieces that can attack two of theirs at once. Knights + queens especially.",
    "missed_pin":             "Look for pinnable geometry: opponent's king / queen behind another piece on a straight line.",
    "missed_skewer":          "Look for a high-value opponent piece with a lower-value piece behind it on a line.",
    "missed_discovered_attack":"When one of your pieces stands between your slider and an opponent piece, ask what happens if that blocker moves.",
    "missed_generic_tactic":  "The engine saw a strong move you didn't. Sharpen tactical vision with daily short puzzles.",
    # tactical_oversight
    "ignored_forcing_threat": "When the opponent makes a capture or check, address it FIRST before continuing your plan.",
    "overlooked_immediate_reply":"After you pick a move, always take 5 seconds to see the opponent's most forcing reply.",
    "generic_oversight":      "Slow down on critical moments — most of these are visible with 10 extra seconds of thought.",
    # calculation_depth
    "shallow_horizon_2ply":   "Push your calculation two moves further on any forcing line. Look for opponent's forced tactics after your move.",
    "broken_forcing_sequence":"Once you start a forcing line, walk it to the end move BEFORE you start it — including all captures and recaptures.",
    "generic_calc_gap":       "Slow down and calculate one more move deep than feels natural. That's where the plateau lives.",
    # piece_activity
    "queen_out_early":        "Develop knights and bishops before the queen. Early queen moves get chased and lose tempo.",
    "piece_parked_on_start":  "Every piece needs a job. If a piece hasn't moved by move 10, that's your next priority.",
    # opening_knowledge
    "tempo_wasted_by_repeat": "In the opening, don't move the same piece twice unless it captures. Every tempo counts.",
    "early_flank_pawn_move":  "Pushing flank pawns in the opening weakens your king. Only do it when there's a concrete tactical reason.",
    # endgame_technique
    "passive_king_in_endgame":"In endgames without queens, the king is a fighting piece. Bring it toward the center.",
    "passed_pawn_ignored":    "A passed pawn is worth material — stop the advance BEFORE it queens.",
    "generic_endgame_slip":   "Endgame technique is precision. Study one endgame idea a week (king activity, opposition, rook endings).",
    # pawn_structure
    "isolated_pawn_created":  "Before every pawn move, ask whether it isolates one of your pawns.",
    "doubled_pawn_created":   "Doubled pawns are usually a structural cost — take them only if you get real activity in return.",
    "backward_pawn_created":  "Backward pawns become long-term weaknesses. Look for pawn structures that leave your pawns supporting each other.",
    "generic_structure_slip": "Small structural moves compound over long games. Before every pawn move, ask: what does this cost my structure?",
    # soft fallback
    "unverified_hint":        "This pattern shows up in your data but the exact type isn't board-provable yet. The coaching cards will drill in on the specifics.",
}


def _tier_closing(band: str, dominant_subtype: str, rating: Optional[int]) -> str:
    """The one-line closing coaching instruction, band-aware but data-driven.

    For beginners/intermediates, we hand-tune closings per subtype. For
    advanced/expert players (>=1600), we prefix with a rating annotation
    on the subtypes where framing matters (piece_safety-family)."""
    r_str = f"At {rating}, " if rating else ""

    # Advanced/expert reframing on piece_safety subtypes
    if band in ("advanced", "expert") and dominant_subtype == "simple_hang":
        return (f"{r_str}dropping pieces in quiet positions is a scanning gap, "
                "not a calculation gap. Slow down on quiet moves.")

    return _CLOSING_BY_SUBTYPE.get(
        dominant_subtype,
        "Focus on the pattern above; the coaching cards will drill in on specifics.",
    )


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
    # v9: time_management has a synthetic histogram stored on signals
    if topic == "time_management" and signals.get("_time_synth_hist"):
        subtypes = signals["_time_synth_hist"]
    else:
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
            # No subtype evidence yet -- no instruction to give until there is.
            "instruction_text": None,
            "dominant_subtype": None,
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
        # Sprint 2 (2026-08-08, docs/one_surviving_instruction_scope.md):
        # the closing line IS the actionable instruction, already computed
        # above (_tier_closing) but previously only baked into `narrative`
        # as prose. Exposed as its own field so assign_focus() can store
        # it as a standalone, addressable instruction_text.
        "instruction_text": _tier_closing(band, dominant_subtype, rating),
        "dominant_subtype": dominant_subtype,
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


async def _pic_enabled_for_user(db, user_id: str) -> bool:
    from services.focus_bridge import _pic_fields_eligible
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "role": 1})
    return _pic_fields_eligible((user_doc or {}).get("role"))


async def _get_cohort_signals(
    db, user_id: str, see_backed_only: bool = False
) -> Dict[str, Any]:
    """Compute the aggregate signals from this user's move_observations.

    Cap at 25000 obs (~1000 games) — enough to cover our largest users
    (Mohit has 15k, Parth 6k). Any user hitting the cap should switch to
    server-side aggregation, but at current scale in-memory is fine."""
    from services.move_observation_deriver import aggregate_user_signals
    query: Dict[str, Any] = {"user_id": user_id}
    if see_backed_only:
        query["schema_version"] = {"$gte": 16}
    obs = await db.move_observations.find(query).to_list(length=25000)
    from services.detector_quality import sanitize_plan_observation
    obs = [sanitize_plan_observation(item) for item in obs]
    return aggregate_user_signals(obs), len(obs)


async def _resolve_user_rating(db, user_id: str) -> Optional[int]:
    """Get the user's current rating for band classification.
    Prefers rating_resolver if available, falls back to user_doc + profile."""
    try:
        from services.rating_resolver import get_coaching_rating
        user_doc = await db.users.find_one({"user_id": user_id}) or {}
        profile_doc = await db.player_profiles.find_one({"user_id": user_id}) or {}
        return await get_coaching_rating(
            db, user_id, user=user_doc, profile=profile_doc
        )
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


async def _compute_baseline_metric(
    db, user_id: str, topic: str, see_backed_only: bool = False
) -> Dict[str, Any]:
    """Baseline per-game rate — total occurrences divided by total analyzed
    games. Simple + correct. Previous version divided by a capped n which
    made rates 30x too high."""
    games_analyzed = await db.games.count_documents(
        {"user_id": user_id, "is_analyzed": True}
    )
    observation_query: Dict[str, Any] = {
        "user_id": user_id,
        "missed_pattern": topic,
    }
    from services.detector_quality import (
        authorized_gap_subtypes,
        enforcement_enabled,
    )
    if enforcement_enabled():
        authorized_subtypes = authorized_gap_subtypes(topic)
        if not authorized_subtypes:
            return {
                "name": f"{topic}_per_game",
                "value": 0.0,
                "occurrence_count": 0,
                "n_games_at_baseline": games_analyzed,
            }
        observation_query["subtype"] = {"$in": list(authorized_subtypes)}
    if see_backed_only:
        observation_query["schema_version"] = {"$gte": 16}
    total = await db.move_observations.count_documents(observation_query)
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

    # Signals from move_observations. PIC hard-excludes pre-SEE schemas;
    # flag-off users retain the legacy query until controlled migration.
    pic_enabled = await _pic_enabled_for_user(db, user_id)
    signals, n_obs = await _get_cohort_signals(
        db, user_id, see_backed_only=pic_enabled
    )
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

    # Build candidate list. When subtype data is available, use the
    # subtype-classified count as the truth (not the raw missed_pattern_counts
    # from the analyzer). This excludes events that failed the coaching-
    # relevance gates (e.g., king_safety events in already-lost positions
    # or endgame king walks that got rerouted).
    pattern_subtypes = signals.get("pattern_subtype_severity") or {}
    candidates: List[Dict[str, Any]] = []
    for pattern, raw_count in (signals.get("missed_pattern_counts") or {}).items():
        if pattern in pattern_subtypes:
            # Subtype-classified count is the coaching-relevant count
            subtype_bucket = pattern_subtypes[pattern]
            classified_count = sum(sum(sev_counts.values()) for sev_counts in subtype_bucket.values())
            count = classified_count
            weighted = _severity_weighted_count(subtype_bucket)
        else:
            count = raw_count
            weighted = raw_count * 1.0

        if count < MIN_EVIDENCE:
            continue
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

    # v9: time_management as a synthetic topic — scored from time_flag counts
    # + game-level timeout_loss_rate. Not a missed_pattern the analyzer tags,
    # but a first-class coaching dimension the picker considers.
    time_flag_counts = signals.get("time_flag_counts") or {}
    time_flag_sev = signals.get("time_flag_severity") or {}
    n_time_flags = sum(time_flag_counts.values())

    # Compute timeout_loss_rate at pick time (game-level signal)
    n_analyzed = await db.games.count_documents({"user_id": user_id, "is_analyzed": True})
    n_time_loss = 0
    async for gg in db.games.find(
        {"user_id": user_id, "termination": "timeout"},
        {"result": 1, "user_color": 1},
    ):
        col = gg.get("user_color")
        res = gg.get("result")
        if (res == "1-0" and col == "black") or (res == "0-1" and col == "white"):
            n_time_loss += 1
    timeout_loss_rate = n_time_loss / max(n_analyzed, 1)

    # Mohit 2026-07-21: DISABLED pending fix. _compute_baseline_metric() and
    # check_focus_outcome() both measure progress via
    # move_observations.missed_pattern == topic — but time_management is
    # scored here from time_flag_counts/timeout_loss_rate (see comment
    # below), a field this topic's evidence was NEVER tagged under. Every
    # user locked onto this topic gets baseline_rate=0 and current_rate=0
    # forever (delta=0.0 exactly → "stuck"), so close_focus() can never
    # promote them past status="active" — confirmed in production: 18 of 38
    # active weakness-locks were permanently wedged on time_management,
    # extending 7 more days on every 6-hourly outcome check with no way out.
    # Re-enable once check_focus_outcome has a matching time_flag-based
    # branch for this topic.
    _TIME_MANAGEMENT_OUTCOME_CHECK_FIXED = False
    # Score: severity-weighted flags PLUS a chronic-timeout bonus
    if _TIME_MANAGEMENT_OUTCOME_CHECK_FIXED and (n_time_flags >= MIN_EVIDENCE or timeout_loss_rate >= 0.10):
        # Build a synthetic subtype_severity dict for the narrative
        synth_hist: Dict[str, Dict[str, int]] = {}
        for flag, count in time_flag_counts.items():
            synth_hist[flag] = dict(time_flag_sev.get(flag, {})) or {"moderate": count}
        # Also add a game-level "chronic_timeout" subtype if applicable
        if timeout_loss_rate >= 0.10:
            n_timeout_loss = int(timeout_loss_rate * n_analyzed)
            synth_hist["chronic_timeout"] = {"critical": n_timeout_loss}

        weighted = _severity_weighted_count(synth_hist)
        # Rate lookups for later narrative building — stash on signals
        signals["_time_synth_hist"] = synth_hist
        signals["_timeout_loss_rate"] = timeout_loss_rate
        signals["_n_time_loss_games"] = n_time_loss
        signals["_n_analyzed_games_time"] = n_analyzed
        prior = 1.0  # time_management always gets neutral prior (no band table yet)
        candidates.append({
            "topic": "time_management",
            "score": round(weighted * prior, 3),
            "evidence_count": n_time_flags + (int(timeout_loss_rate * n_analyzed) if timeout_loss_rate >= 0.10 else 0),
            "severity_weighted_count": round(weighted, 2),
            "per_100_moves": None,
            "impact_weight": 1.0,
            "rating_prior": prior,
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
    # Sprint 2: the standalone actionable instruction, distinct from the
    # full diagnosis+instruction coaching_narrative paragraph above.
    winner["instruction_text"] = narrative_pack["instruction_text"]
    winner["dominant_subtype_at_assignment"] = narrative_pack["dominant_subtype"]
    winner["pic_enabled"] = pic_enabled

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


async def _instruction_fields_eligible_for_write(db, user_id: str) -> bool:
    """Same eligibility rule as focus_bridge's read-time gate (flag +
    role), evaluated here at write time instead. Reuses focus_bridge's
    own check rather than duplicating the flag/role logic -- one source
    of truth for what "eligible" means, just called from two places
    (write-time here, read-time in focus_bridge for docs written before
    this fix)."""
    from services.focus_bridge import _instruction_fields_eligible
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "role": 1})
    return _instruction_fields_eligible((user_doc or {}).get("role"))


async def assign_focus(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Pick + persist. Returns the created focus doc or None."""
    picked = await pick_next_focus(db, user_id)
    if not picked:
        return None
    now = datetime.now(timezone.utc)
    pic_enabled = bool(picked.get("pic_enabled"))
    baseline = await _compute_baseline_metric(
        db,
        user_id,
        picked["topic"],
        see_backed_only=pic_enabled,
    )
    # Sprint 2 (docs/one_surviving_instruction_scope.md): pre-generate the
    # _id so instruction_id can be set in the SAME document, atomically --
    # no follow-up write needed. instruction_id is a plain string field
    # (not literally _id) so callers never have to know/care it originated
    # from an ObjectId.
    new_id = ObjectId()

    # Correction (2026-08-08, external review of b0105f21): the scope's
    # own contract is "a non-eligible user's session should not COMPUTE
    # instruction_id/instruction_text, not merely hide them" -- v1 of this
    # function wrote the 3 fields unconditionally for every user and
    # topic, gating only at focus_bridge read time. That's real Sprint 2
    # logic executing for every eligible user regardless of role, which
    # is not what was locked. Gated HERE, at the only write site, so an
    # ineligible user's user_active_focus document never contains these
    # fields at all -- identical in shape to a pre-Sprint-2 legacy doc.
    include_instruction_fields = (
        picked["topic"] == "piece_safety"
        and await _instruction_fields_eligible_for_write(db, user_id)
    )

    focus = {
        "_id": new_id,
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

    from services.detector_quality import gap_quality_id, grade_for
    dominant_subtype = picked.get("dominant_subtype_at_assignment")
    detector_quality_id = gap_quality_id(picked["topic"], dominant_subtype)
    focus["detector_quality_id"] = detector_quality_id
    focus["detector_quality_grade"] = grade_for(
        detector_quality_id
    ).value

    destination_safety_count = int(
        ((picked.get("subtype_histogram") or {}).get("destination_safety_exact") or {}).get(
            "count", 0
        )
    )
    if pic_enabled and picked["topic"] == "piece_safety" and destination_safety_count > 0:
        from services.focus_bridge import get_destination_safety_evidence_summary
        focus.update({
            "cycle_version": 1,
            "focus_kind": "piece_safety/destination_safety_exact",
            "proof_eligibility": "verified",
            "diagnosis_detector_id": "piece_safety.destination_safety_exact.v1",
            "proof_detector_id": "piece_safety.destination_safety_exact.v1",
            "evidence_summary": {
                "baseline": await get_destination_safety_evidence_summary(db, user_id),
                "recent": {"decisions": 0, "misses": 0, "handled": 0},
                "last_verdict": "measurement_pending",
                "measured_at": now,
            },
            # New PIC timestamps are BSON datetimes. Readers remain tolerant of
            # legacy ISO strings while comparisons stop mixing types.
            "started_at": now,
            "locked_until": now + timedelta(days=LOCK_DURATION_DAYS),
            "created_at": now,
            "updated_at": now,
        })

    # Sprint 2 canonical instruction fields -- the ONE source of truth for
    # "what is the player being asked to do," captured once here and never
    # regenerated for the life of this focus. Only present on the document
    # AT ALL when eligible (piece_safety + admin/super_admin + flag on) --
    # an ineligible user's doc is identical in shape to a pre-Sprint-2
    # legacy doc, not just a doc with these fields hidden downstream.
    if include_instruction_fields:
        focus["instruction_id"] = str(new_id)
        focus["instruction_text"] = picked.get("instruction_text")
        focus["instruction_version"] = INSTRUCTION_TEMPLATE_VERSION
        focus["instruction_subtype"] = picked.get("dominant_subtype_at_assignment")

    await db[COLLECTION].insert_one(focus)
    return focus


async def check_focus_outcome(db, focus: Dict[str, Any]) -> Dict[str, Any]:
    """Called at locked_until. Returns {resolution, action, delta_pct}."""
    if focus.get("cycle_version") == 1:
        return {
            "resolution": "measurement_pending",
            "action": "hold",
            "delta_pct": None,
            "current_metric": None,
        }
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
    now_dt = datetime.now(timezone.utc)
    use_bson_time = isinstance(focus.get("locked_until"), datetime) or bool(
        focus.get("cycle_version")
    )
    now = now_dt if use_bson_time else now_dt.isoformat()
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
        # PIC's locked calendar backstop is a check-in, never an evidence
        # verdict. Preserve BSON timestamps and its configured backstop.
        extension_days = int(
            focus.get("calendar_backstop_days") or (21 if use_bson_time else 7)
        )
        new_until_dt = now_dt + timedelta(days=extension_days)
        new_until = new_until_dt if use_bson_time else new_until_dt.isoformat()
        update["$set"]["locked_until"] = new_until
    await db[COLLECTION].update_one({"_id": focus["_id"]}, update)


async def unstick_time_management_lock(db, user_id: str, dry_run: bool = True) -> Dict[str, Any]:
    """
    One-time fix for the time_management outcome-check gap (see the
    disabled-candidate comment in pick_next_focus). Closes an active
    weakness-lock stuck on topic_key='time_management' with an honest
    status — NOT "completed" or "escalated" (that would fabricate an
    outcome the metric gap made impossible to actually observe) — then
    assigns a fresh, real focus from the user's current evidence via the
    normal assign_focus() path.

    Only acts on a user whose active lock is specifically time_management;
    no-ops (written=False) for everyone else, including users correctly
    locked on a real topic.
    """
    active = await _get_active_focus(db, user_id)
    if not active or active.get("topic_key") != "time_management":
        return {"user_id": user_id, "written": False, "reason": "not stuck on time_management"}

    if dry_run:
        return {"user_id": user_id, "written": False, "old_topic": "time_management", "dry_run": True}

    now = datetime.now(timezone.utc).isoformat()
    await db[COLLECTION].update_one(
        {"_id": active["_id"]},
        {"$set": {
            "status": "closed_unresolvable_metric",
            "resolution": "metric_gap",
            "next_action": "reassigned",
            "closed_at": now,
            "updated_at": now,
        }},
    )
    new_focus = await assign_focus(db, user_id)
    return {
        "user_id": user_id,
        "written": True,
        "old_topic": "time_management",
        "new_topic": (new_focus or {}).get("topic_key"),
    }
