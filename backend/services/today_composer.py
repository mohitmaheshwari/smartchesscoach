"""
/today composer — one coach voice, rating-band aware.

Reuses existing content from the codebase (no new dicts):
  - COACHING_DIAGNOSIS / COACHING_INSIGHTS / COACHING_RULES  (routes/training_advanced.py)
  - get_rating_band                                          (deterministic_coach_service.py)
  - focus_resolver.get_active_focus                          (services/focus_resolver.py)
  - engine2_skill_builder.pick_next_skill                    (services/engine2_skill_builder.py)

Voice changes by rating band:

  beginner_low    (0-999)   — warmest, no notation, no counts, 3 sentences max.
                              "We" language. Rule + action. Board shown without text ref.
  beginner_high   (1000-1399) — rule-focused, soft counts ("a few times lately"),
                              no move notation, no specific opponent references.
  intermediate    (1400-1799) — specific counts, references to recent games allowed,
                              limited notation in context.
  advanced        (1800+)   — full technical: counts, notation, move numbers, cp deltas.

No LLM — deterministic voice so the coach sounds consistent every time.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── ENGINE 2 SKILL → COGNITIVE-GAP KEY ───────────────────────────────
# When Engine 2 is the focus source, we still need to pull a matching
# COACHING_RULES entry for the one-line rule. This maps Engine 2 skill_ids
# (now knowledge-based — openings/traps/endgames/concepts/mate_patterns)
# to the closest cognitive-gap key used by the rules dict.
#
# Knowledge nodes don't map 1:1 onto tactical gaps, so many map to
# cognitive_gap None — in which case today_composer picks a generic
# encouragement line instead of a rule.

SKILL_TO_GAP = {
    # Tier 0 — foundations
    "coached_development":    None,                # no rule — play-with-coach handles it
    "mate_kq_vs_k":           "endgame_technique",
    "mate_kr_vs_k":           "endgame_technique",
    "defend_scholars_mate":   "ignore_threat",

    # Tier 1 — first real repertoire + basic endgames
    "opening_london_white":      None,
    "opening_caro_kann_black":   None,
    "opening_scandinavian_black": None,
    "endgame_opposition":        "endgame_technique",
    "endgame_rule_of_square":    "endgame_technique",
    "defend_fried_liver":        "ignore_threat",

    # Tier 2 — deeper repertoire + traps + real endgames + IQP
    "opening_italian_white":     None,
    "opening_italian_black":     None,
    "opening_queens_gambit":     None,
    "opening_french_black":      None,
    "trap_set_italian":          "ignore_threat",
    "trap_set_caro_kann":        "ignore_threat",
    "trap_set_london":           "ignore_threat",
    "endgame_lucena":            "endgame_technique",
    "endgame_philidor":          "endgame_technique",
    "concept_iqp":               None,

    # Tier 3 — advanced
    "opening_ruy_lopez":         None,
    "opening_sicilian_black":    None,
    "concept_prophylaxis":       "calculation_depth",
    "concept_minority_attack":   None,
}


# ── ACTION ROUTING BY KIND ───────────────────────────────────────────
# Engine 2 nodes now have a `kind` that decides the destination. This is
# a simple kind→route map, much cleaner than a per-skill dict.
#
# Each kind has band-aware CTA copy. Default verb matches the medium:
#   opening     → study the lesson then play it with coach
#   trap_set    → study the traps then play with coach who tests them
#   endgame     → do the lesson
#   mate_pattern → do the lesson
#   concept     → play with coach who reinforces the concept
#   coached_play → play with coach, focus enforced

KIND_ACTIONS = {
    "opening": {
        "beginner_low": "Let's learn this opening together",
        "beginner_high": "Study this opening",
        "intermediate": "Study this opening",
        "advanced": "Study this opening",
        "href": "/openings/{content_ref}",
        "medium": "lesson",
    },
    "trap_set": {
        "beginner_low": "Let's learn these traps together",
        "beginner_high": "Study these traps",
        "intermediate": "Study these traps",
        "advanced": "Study these traps",
        "href": "/openings/{content_ref}#traps",
        "medium": "lesson",
    },
    "endgame": {
        "beginner_low": "Let's work through this endgame",
        "beginner_high": "Do the endgame lesson",
        "intermediate": "Do the endgame lesson",
        "advanced": "Do the endgame lesson",
        "href": "/endgames/{content_ref}",
        "medium": "lesson",
    },
    "mate_pattern": {
        "beginner_low": "Let's practice the mate together",
        "beginner_high": "Practice this mate",
        "intermediate": "Practice this mate",
        "advanced": "Practice this mate",
        "href": "/endgames/{content_ref}",
        "medium": "lesson",
    },
    "concept": {
        "beginner_low": "Let's play a game together — I'll explain",
        "beginner_high": "Play a game — I'll teach",
        "intermediate": "Play a game — I'll teach",
        "advanced": "Play a game — I'll teach",
        "href": "/play-with-coach?focus={skill_id}",
        "medium": "live_game",
    },
    "coached_play": {
        "beginner_low": "Let's play a game together",
        "beginner_high": "Play a focused game",
        "intermediate": "Play a focused game with me",
        "advanced": "Play a focused game",
        "href": "/play-with-coach?focus={skill_id}",
        "medium": "live_game",
    },
}


# ── BEGINNER VOICE OVERRIDES ─────────────────────────────────────────
# For band 'beginner_low' the existing COACHING_DIAGNOSIS['short'] lines
# are correct but too clinical. These soften them to "we"-language +
# reassurance. Only used for band=beginner_low.

BEGINNER_LOW_HEADLINES = {
    "piece_safety":      "Let's work on keeping your pieces safe.",
    "ignore_threat":     "Let's work on spotting what your opponent is planning.",
    "calculation_depth": "Let's learn to think one more move ahead.",
    "missed_tactic":     "Let's practice finding simple tactics together.",
    "tactical_oversight": "Let's learn to check your opponent's reply.",
    "king_safety":       "Let's work on keeping your king safe.",
    "conversion":        "Let's practice finishing winning games.",
    "endgame_technique": "Let's work on endgames together.",
    "time_pressure":     "Let's practice keeping calm on the clock.",
}


# ── COMPOSER ─────────────────────────────────────────────────────────


async def compose_today(db, user_id: str) -> Dict[str, Any]:
    """Build the single-screen prescription for /today, voiced by rating band."""

    out: Dict[str, Any] = {
        "greeting": None,
        "headline": None,
        "evidence": [],
        "rule": None,
        "board": None,
        "action": None,
        "streak": None,
        "alternates": [],
        "source": "none",
        "band": None,
    }

    # ── Greeting ──
    user = await db.users.find_one({"user_id": user_id}, {"email": 1, "display_name": 1, "name": 1, "_id": 0})
    name = _extract_first_name(user)

    # ── Rating band (the canonical one) ──
    band_name = await _detect_band(db, user_id)
    out["band"] = band_name

    # Warm greetings for beginner_low, neutral for everyone else
    if band_name == "beginner_low":
        out["greeting"] = f"Hey {name}." if name else "Hey there."
    else:
        out["greeting"] = f"Hey {name}." if name else "Welcome back."

    # ── Pick focus (Engine 1 → Engine 2 → nothing) ──
    focus_source, focus = await _pick_todays_focus(db, user_id)
    out["source"] = focus_source

    if not focus:
        out["headline"] = _empty_state_headline(band_name, name)
        out["action"] = {"cta": "Play with me", "href": "/play-with-coach", "medium": "live_game"}
        return out

    gap = focus.get("gap") or SKILL_TO_GAP.get(focus.get("skill_id")) or focus.get("category")

    # ── Headline (band-specific) ──
    out["headline"] = _headline_for_band(band_name, gap, focus)

    # ── Evidence (band gates what's shown) ──
    out["evidence"] = await _evidence_for_band(db, user_id, band_name, gap, focus)

    # ── Rule (all bands use COACHING_RULES, shortened for beginner_low) ──
    out["rule"] = _rule_for_band(band_name, gap)

    # ── Action ──
    out["action"] = _action_for_band(band_name, focus)

    # ── Streak (hidden for beginner_low — don't show failure dots to a fragile learner) ──
    if band_name != "beginner_low":
        out["streak"] = await _gather_streak(db, user_id)

    # ── Board (all bands get it — visual, not verbal) ──
    out["board"] = await _find_critical_position(db, user_id, focus)

    # ── Alternates (same conversational dialogue for all bands) ──
    out["alternates"] = _compose_alternates(focus)

    return out


# ── HELPERS ──────────────────────────────────────────────────────────


def _extract_first_name(user: Optional[Dict]) -> Optional[str]:
    if not user:
        return None
    for key in ("display_name", "name"):
        val = user.get(key)
        if val and isinstance(val, str):
            first = val.split()[0].strip()
            if first:
                return first[0].upper() + first[1:].lower()
    email = user.get("email") or ""
    if "@" in email:
        handle = email.split("@")[0]
        parts = [p for p in handle.split(".") if p]
        if parts:
            first = parts[0]
            if 2 <= len(first) <= 12:
                return first[0].upper() + first[1:].lower()
    return None


async def _detect_band(db, user_id: str) -> str:
    """Resolve to one of: beginner_low, beginner_high, intermediate, advanced.
    Uses the canonical get_rating_band from deterministic_coach_service."""
    from deterministic_coach_service import get_rating_band

    # Prefer PGN-inferred rating (what ChessGuru actually sees); fall back
    # to coach_memory performance rating.
    rating = 1000
    try:
        from services.coach_memory import get_user_rating_from_games
        r = await get_user_rating_from_games(db, user_id)
        if r and r.get("rating"):
            rating = r["rating"]
    except Exception:
        pass

    if rating <= 0 or rating == 1200:  # 1200 is the default fallback — try memory
        try:
            mem = await db.coach_memory.find_one({"user_id": user_id}, {"performance": 1})
            if mem:
                perf_rating = (mem.get("performance") or {}).get("best_performance_rating") or 0
                if perf_rating > 0:
                    rating = perf_rating
        except Exception:
            pass

    band = get_rating_band(rating)
    return band.get("name", "beginner_low")


async def _pick_todays_focus(db, user_id: str):
    # Engine 1 first
    try:
        from services.focus_resolver import get_active_focus
        active = await get_active_focus(db, user_id, top_problems=None)
        if active and active.get("focus"):
            return "engine1", {
                "kind": "engine1",
                "focus": active.get("focus"),
                "category": active.get("category"),
                "gap": active.get("gap"),
                "label": active.get("label"),
                "reason": active.get("reason"),
                "skill_id": active.get("focus"),
            }
    except Exception as e:
        logger.debug(f"Engine 1 focus failed: {e}")

    # Engine 2 fallback
    try:
        from services.engine2_skill_builder import pick_next_skill
        from services.coach_memory import get_or_create_memory
        mem = await get_or_create_memory(db, user_id)
        rating = mem.performance.best_performance_rating or 1000
        nxt = pick_next_skill(mem, rating)
        if nxt:
            return "engine2", {
                "kind": "engine2",
                "skill_id": nxt["skill_id"],
                "label": nxt["label"],
                "reason": nxt["reason"],
                "stats": nxt.get("stats", {}),
                "tier": nxt.get("tier"),
                "gap": SKILL_TO_GAP.get(nxt["skill_id"]),
            }
    except Exception as e:
        logger.debug(f"Engine 2 pick failed: {e}")

    return "none", None


def _empty_state_headline(band_name: str, name: Optional[str]) -> str:
    """First-run / no-data headlines — welcoming, not empty."""
    if band_name == "beginner_low":
        return "Let's play a game so I can learn how you play."
    return "Let's play a game so I can start tracking your patterns."


def _headline_for_band(band_name: str, gap: Optional[str], focus: Dict) -> str:
    """One sentence in the coach's voice. Reuses existing COACHING_DIAGNOSIS
    and COACHING_INSIGHTS — with a warmer override for beginner_low."""
    # beginner_low → "we" language, reassuring
    if band_name == "beginner_low" and gap in BEGINNER_LOW_HEADLINES:
        return BEGINNER_LOW_HEADLINES[gap]

    # beginner_high → the short diagnosis line (plain, direct, not clinical)
    # intermediate → the detail line (clearer, still non-technical)
    # advanced → insight line (deeper, earns specificity)
    try:
        from routes.training_advanced import COACHING_DIAGNOSIS, COACHING_INSIGHTS
    except Exception:
        COACHING_DIAGNOSIS = {}
        COACHING_INSIGHTS = {}

    if not gap:
        return focus.get("label") or focus.get("reason") or "Let's work on your play today."

    diag = COACHING_DIAGNOSIS.get(gap, {})
    insight = COACHING_INSIGHTS.get(gap)

    if band_name == "beginner_high":
        return diag.get("short") or insight or focus.get("label") or "Let's work on this today."
    if band_name == "intermediate":
        return diag.get("detail") or diag.get("short") or insight or "Let's work on your play today."
    if band_name == "advanced":
        return insight or diag.get("detail") or "Let's work on your play today."

    # Fallback (shouldn't hit)
    return diag.get("short") or "Let's work on your play today."


async def _evidence_for_band(db, user_id: str, band_name: str, gap: Optional[str], focus: Dict) -> List[str]:
    """Band gates how evidence is shown. Beginner_low sees nothing — no
    failure counts, no move numbers, no opponent names. That level of
    specificity demoralises, not motivates."""
    if band_name == "beginner_low":
        # Don't rub failure in their face. The board + headline do the work.
        return []

    stats = focus.get("stats") or {}
    seen = stats.get("seen", 0)
    wrong = stats.get("failed", stats.get("wrong", 0))

    if band_name == "beginner_high":
        # Soft counts only — no move notation, no opponent names
        if wrong >= 3 and seen:
            return [f"This has come up a few times in your recent games."]
        # Engine 1 fallback — count prescriptions softly
        fkey = focus.get("focus") or focus.get("skill_id")
        if fkey:
            n = await db.postgame_analyses.count_documents(
                {"user_id": user_id, "coach_prescription": fkey}
            )
            if n >= 2:
                return [f"This has shown up in a few of your recent games."]
        return []

    if band_name == "intermediate":
        lines = []
        if seen and wrong >= 3:
            lines.append(f"You've missed this in {wrong} of your last {seen} games.")
        else:
            fkey = focus.get("focus") or focus.get("skill_id")
            if fkey:
                n = await db.postgame_analyses.count_documents(
                    {"user_id": user_id, "coach_prescription": fkey}
                )
                if n:
                    lines.append(f"This has come up in {n} of your recent games.")
        critical = await _find_critical_position(db, user_id, focus)
        if critical and critical.get("move_number"):
            opp = critical.get("opponent", "your opponent")
            lines.append(f"Most recent — move {critical['move_number']} vs {opp}.")
        return lines[:2]

    # advanced
    lines = []
    if seen and wrong:
        lines.append(f"Failed in {wrong} of your last {seen} games.")
    critical = await _find_critical_position(db, user_id, focus)
    if critical and critical.get("move_number"):
        opp = critical.get("opponent", "your opponent")
        lines.append(f"Last example — move {critical['move_number']} vs {opp}.")
    return lines[:2]


def _rule_for_band(band_name: str, gap: Optional[str]) -> Optional[str]:
    """Pull the actionable rule from the existing COACHING_RULES dict.
    For beginner_low we prepend 'Together:' to reinforce 'we' framing."""
    if not gap:
        return None
    try:
        from routes.training_advanced import COACHING_RULES
    except Exception:
        return None
    entry = COACHING_RULES.get(gap)
    if not entry:
        return None
    rule = entry.get("rule")
    if not rule:
        return None

    if band_name == "beginner_low":
        # Soften phrasing: "Before every move, ask:" → "Each move, we ask:"
        rule = rule.replace("Before every move, ask:", "Each move, we ask:")
        rule = rule.replace("Before every move,", "Each move,")
    return rule


def _action_for_band(band_name: str, focus: Dict) -> Dict[str, str]:
    """CTA text + destination. New flow: kind-based routing (not per-skill)."""
    # Engine 2 focus has `kind` and `content_ref` from pick_next_skill
    kind = focus.get("kind")
    content_ref = focus.get("content_ref") or ""
    skill_id = focus.get("skill_id") or focus.get("focus") or ""

    if kind and kind in KIND_ACTIONS:
        cfg = KIND_ACTIONS[kind]
        cta = cfg.get(band_name) or cfg.get("intermediate") or "Start"
        href = (cfg.get("href") or "/play-with-coach").format(
            content_ref=content_ref, skill_id=skill_id
        )
        return {"cta": cta, "href": href, "medium": cfg.get("medium", "lesson")}

    # Engine 1 focus → route to /training/prescribed by gap
    gap = focus.get("gap") or focus.get("category")
    if gap:
        cta = {
            "beginner_low":  "Let's practice this together",
            "beginner_high": "Practice this weakness",
            "intermediate":  "Practice this weakness",
            "advanced":      "Practice this weakness",
        }.get(band_name, "Practice this weakness")
        return {
            "cta": cta,
            "href": f"/training/prescribed?weakness={gap}",
            "medium": "puzzles",
        }

    # Final fallback — play a game
    return {
        "cta": "Let's play a game" if band_name == "beginner_low" else "Play with me",
        "href": "/play-with-coach",
        "medium": "live_game",
    }


def _compose_alternates(focus: Dict) -> List[Dict[str, str]]:
    """Conversational interrupts for 'not feeling this today' — never a library."""
    alternates = []
    kind = focus.get("kind")
    current_medium = (KIND_ACTIONS.get(kind) or {}).get("medium") if kind else None

    if current_medium != "live_game":
        alternates.append({"label": "I'd rather just play a game", "href": "/play-with-coach"})
    if current_medium != "puzzles":
        alternates.append({"label": "let me work on tactics instead", "href": "/training/prescribed?weakness=current"})
    alternates.append({"label": "take today off", "action": "dismiss"})
    return alternates


async def _gather_streak(db, user_id: str) -> Optional[Dict]:
    try:
        from services.focus_engine import get_user_focus
        focus = await get_user_focus(db, user_id)
        if focus and focus.get("games_played", 0) > 0:
            game_results = focus.get("game_results", []) or []
            clean = sum(1 for r in game_results if r.get("clean"))
            return {
                "clean": clean,
                "target": focus.get("clean_threshold", 3),
                "total": focus.get("games_target", 5),
                "results": [bool(r.get("clean")) for r in game_results][:5],
            }
    except Exception:
        pass
    return None


async def _find_critical_position(db, user_id: str, focus: Dict) -> Optional[Dict]:
    """Most recent game where this problem fired. Returns FEN + move number +
    opponent so the coach can display a concrete board."""
    try:
        fkey = focus.get("focus") or focus.get("skill_id")
        query = {"user_id": user_id}
        if fkey:
            query["coach_prescription"] = fkey
        doc = await db.postgame_analyses.find_one(
            query, sort=[("created_at", -1)],
            projection={"session_id": 1, "_id": 0}
        )
        if not doc:
            return None
        session_id = doc.get("session_id")
        if not session_id:
            return None
        session = await db.coach_sessions.find_one(
            {"session_id": session_id},
            {"move_history": 1, "opponent": 1, "_id": 0}
        )
        if not session:
            return None
        moves = session.get("move_history") or []
        worst = None
        worst_cp = 0
        for mv in moves:
            cp = abs(mv.get("cp_loss", 0) or 0)
            if cp > worst_cp and (mv.get("by") == "player" or not mv.get("by")):
                worst_cp = cp
                worst = mv
        if not worst:
            return None
        return {
            "fen": worst.get("fen_before") or worst.get("fen"),
            "move_number": worst.get("move_number"),
            "opponent": session.get("opponent") or "Coach",
            "game_id": session_id,
        }
    except Exception as e:
        logger.debug(f"Critical position lookup failed: {e}")
        return None
