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

# Maps a skill_tree content_ref (used in skill_tree.json) to the two-segment
# route the EndgameLesson page actually needs: /endgames/<category>/<lesson>.
# Keys here are what skill_tree.json holds; values are the actual lesson
# keys from data/coaching/endgame_theory_tree.json.
ENDGAME_ROUTES = {
    # content_ref           →  "<category>/<lesson>"
    "opposition":        "king_and_pawn/opposition",
    "rule_of_square":    "king_and_pawn/square_rule",
    "lucena_position":   "rook_endgames/lucena",
    "philidor_position": "rook_endgames/philidor",
    # Mate patterns (queen_checkmate / rook_checkmate) aren't in the theory
    # tree — absent here means fall back to Play with Coach teaching flow.
}


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
        # href resolved via ENDGAME_ROUTES below, falls through to OpeningsOverview
        "href": "/openings-overview#endgames",
        "medium": "lesson",
    },
    "mate_pattern": {
        "beginner_low": "Let's practice the mate together",
        "beginner_high": "Practice this mate",
        "intermediate": "Practice this mate",
        "advanced": "Practice this mate",
        # mate patterns aren't in endgame_theory_tree — route to OpeningsOverview
        "href": "/openings-overview#endgames",
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
    """
    Build the home-screen prescription. Returns BOTH engines when both
    have picks — Engine 1 as the primary hero (fix your recent mistake),
    Engine 2 as a smaller secondary card (what to learn next).

    Shape:
      {
        greeting, band, alternates,
        primary:   { source, headline, evidence, board, rule, action, streak, ... },
        secondary: { source, label, reason, tier, kind, fixes, action } | None,
      }

    Rules:
      - Both engines pick → primary = Engine 1, secondary = Engine 2
      - Only Engine 1 picks → primary = Engine 1, secondary = None
      - Only Engine 2 picks → primary = Engine 2 (promoted), secondary = None
      - Neither picks → primary = empty-state welcome, secondary = None
    """
    out: Dict[str, Any] = {
        "greeting": None,
        "band": None,
        "alternates": [],
        "primary": None,
        "secondary": None,
    }

    # ── Greeting + band ──
    user = await db.users.find_one({"user_id": user_id}, {"email": 1, "display_name": 1, "name": 1, "_id": 0})
    name = _extract_first_name(user)
    band_name = await _detect_band(db, user_id)
    out["band"] = band_name
    out["greeting"] = (f"Hey {name}." if name else
                       ("Hey there." if band_name == "beginner_low" else "Welcome back."))

    # ── Pick both engines independently ──
    engine1 = await _pick_engine1_focus(db, user_id)
    engine2 = await _pick_engine2_focus(db, user_id)

    # ── Assign primary / secondary ──
    if engine1:
        out["primary"] = await _build_primary(db, user_id, band_name, engine1)
        if engine2:
            out["secondary"] = _build_secondary(band_name, engine2)
        out["alternates"] = _compose_alternates(engine1)
    elif engine2:
        # Engine 1 silent — promote Engine 2 to hero
        out["primary"] = await _build_primary(db, user_id, band_name, engine2)
        out["alternates"] = _compose_alternates(engine2)
    else:
        # No data yet — welcoming empty state
        out["primary"] = {
            "source": "new_user",
            "headline": _empty_state_headline(band_name, name),
            "evidence": [],
            "rule": None,
            "board": None,
            "action": {"cta": "Play with me", "href": "/play-with-coach", "medium": "live_game"},
            "streak": None,
        }

    return out


async def _build_primary(db, user_id: str, band_name: str, focus: Dict) -> Dict[str, Any]:
    """Build the full primary-hero block — all vision elements populated."""
    gap = focus.get("gap") or SKILL_TO_GAP.get(focus.get("skill_id")) or focus.get("category")
    streak = await _gather_streak(db, user_id) if band_name != "beginner_low" else None
    return {
        "source": focus.get("kind") if focus.get("kind") in ("engine1", "engine2") else focus.get("_src", "engine1"),
        "headline": _headline_for_band(band_name, gap, focus),
        "evidence": await _evidence_for_band(db, user_id, band_name, gap, focus),
        "rule": _rule_for_band(band_name, gap, focus),
        "board": await _find_critical_position(db, user_id, focus),
        "action": _action_for_band(band_name, focus),
        "streak": streak,
    }


def _build_secondary(band_name: str, engine2: Dict) -> Dict[str, Any]:
    """Build the smaller 'Learn next' card that complements the primary fix.
    Intentionally simpler — no evidence / no board / no rule. Just label +
    reason + action."""
    return {
        "source": "engine2",
        "label": engine2.get("label"),
        "reason": engine2.get("reason"),
        "tier": engine2.get("tier"),
        "kind": engine2.get("e2_kind"),
        "fixes": engine2.get("fixes"),
        "action": _action_for_band(band_name, engine2),
    }


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


async def _pick_engine1_focus(db, user_id: str) -> Optional[Dict]:
    """Engine 1 (fix-your-mess) pick, or None if no focus."""
    try:
        from services.focus_resolver import get_active_focus
        active = await get_active_focus(db, user_id, top_problems=None)
        if active and active.get("focus"):
            return {
                "_src": "engine1",
                "focus": active.get("focus"),
                "category": active.get("category"),
                "gap": active.get("gap"),
                "label": active.get("label"),
                "reason": active.get("reason"),
                "skill_id": active.get("focus"),
            }
    except Exception as e:
        logger.debug(f"Engine 1 focus failed: {e}")
    return None


async def _pick_engine2_focus(db, user_id: str) -> Optional[Dict]:
    """Engine 2 (build-new-skill) pick, or None if nothing ready.
    Note: Engine 2's 'kind' (opening/trap_set/...) is kept on the focus
    dict under 'e2_kind' to avoid colliding with legacy 'kind' usage."""
    try:
        from services.engine2_skill_builder import pick_next_skill
        from services.coach_memory import get_or_create_memory
        mem = await get_or_create_memory(db, user_id)
        rating = mem.performance.best_performance_rating or 1000
        nxt = pick_next_skill(mem, rating)
        if nxt:
            return {
                "_src": "engine2",
                "skill_id": nxt["skill_id"],
                "label": nxt["label"],
                "reason": nxt["reason"],
                "fixes": nxt.get("fixes"),
                "stats": nxt.get("stats", {}),
                "tier": nxt.get("tier"),
                "e2_kind": nxt.get("kind"),    # opening / trap_set / endgame / ...
                "kind": nxt.get("kind"),       # for _action_for_band routing
                "content_ref": nxt.get("content_ref"),
                "gap": SKILL_TO_GAP.get(nxt["skill_id"]),
            }
    except Exception as e:
        logger.debug(f"Engine 2 pick failed: {e}")
    return None


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
    """Band gates how evidence is shown. Beginner_low gets soft grounded
    phrasing (no counts, no notation, no shame) but never empty — a bare
    screen feels like a fortune cookie. Every band must have *something*
    anchoring the claim."""
    if band_name == "beginner_low":
        # Soft grounded phrases — no numbers, no move notation, no opponent
        # names — but still anchored in the user's games.
        fkey = focus.get("focus") or focus.get("skill_id")
        if fkey:
            n = await db.postgame_analyses.count_documents(
                {"user_id": user_id, "coach_prescription": fkey}
            )
            if n >= 3:
                return ["This has been a pattern in your recent games.",
                        "Don't worry — we'll work on it together."]
            if n >= 1:
                return ["It came up again in your last game.",
                        "Let's fix it together."]
        # Engine 2 fallback (no prescription yet) — still ground it
        critical = await _find_critical_position(db, user_id, focus)
        if critical:
            return ["Here's a moment from your last game where it happened.",
                    "We'll practice so you start spotting it."]
        # No games / no data — still not empty
        return ["Let's play a game together so I can watch how you play."]

    stats = focus.get("stats") or {}
    seen = stats.get("seen", 0)
    wrong = stats.get("failed", stats.get("wrong", 0))

    if band_name == "beginner_high":
        # Soft counts only — no move notation, no opponent names.
        # Never empty — always anchor to something.
        if wrong >= 3 and seen:
            return ["This has come up a few times in your recent games."]
        fkey = focus.get("focus") or focus.get("skill_id")
        if fkey:
            n = await db.postgame_analyses.count_documents(
                {"user_id": user_id, "coach_prescription": fkey}
            )
            if n >= 2:
                return ["This has shown up in a few of your recent games."]
            if n >= 1:
                return ["Came up in your last game too."]
        critical = await _find_critical_position(db, user_id, focus)
        if critical:
            return ["Here's the moment from your last game."]
        return ["Let's play a game so I can show you the patterns."]

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


def _rule_for_band(band_name: str, gap: Optional[str], focus: Optional[Dict] = None) -> Optional[str]:
    """Actionable rule for this focus. Primary source: COACHING_RULES keyed
    on gap. Secondary: kind-specific fallbacks for coached_play / opening /
    trap_set / endgame where no tactical gap exists.

    Never returns None for a user with a focus — the rule anchors the
    screen and should always be present.
    """
    # Primary — gap-matched rule from the existing dictionary
    if gap:
        try:
            from routes.training_advanced import COACHING_RULES
            entry = COACHING_RULES.get(gap)
            if entry and entry.get("rule"):
                rule = entry["rule"]
                if band_name == "beginner_low":
                    rule = rule.replace("Before every move, ask:", "Each move, we ask:")
                    rule = rule.replace("Before every move,", "Each move,")
                return rule
        except Exception:
            pass

    # Secondary — kind-based fallback for knowledge skills without a gap
    kind = (focus or {}).get("kind")
    KIND_RULES = {
        "coached_play": {
            "beginner_low":  "We'll pause before each move and look together.",
            "beginner_high": "Before every move, pause and look around.",
            "intermediate":  "Before every move: captures, checks, threats.",
            "advanced":      "Before every move: captures, checks, threats.",
        },
        "opening": {
            "beginner_low":  "We'll learn the setup order, move by move.",
            "beginner_high": "Learn the setup — piece order matters.",
            "intermediate":  "Every opening move has a purpose. Know why.",
            "advanced":      "Every opening move has a purpose. Know why.",
        },
        "trap_set": {
            "beginner_low":  "We'll learn to spot these traps — and defend.",
            "beginner_high": "Learn to spot these traps — and defend.",
            "intermediate":  "Learn to spot these traps — and defend.",
            "advanced":      "Learn to spot these traps — and defend.",
        },
        "endgame": {
            "beginner_low":  "Endgames are technique. We'll practice together.",
            "beginner_high": "Endgames reward precise technique. Learn the pattern.",
            "intermediate":  "Endgames reward precise technique. Learn the pattern.",
            "advanced":      "Endgames reward precise technique. Learn the pattern.",
        },
        "mate_pattern": {
            "beginner_low":  "We'll practice the mate together, step by step.",
            "beginner_high": "The mate follows a pattern. Learn the rhythm.",
            "intermediate":  "The mate follows a pattern. Learn the rhythm.",
            "advanced":      "The mate follows a pattern. Learn the rhythm.",
        },
        "concept": {
            "beginner_low":  "We'll play a game and I'll point it out.",
            "beginner_high": "Recognize this pattern, then apply it.",
            "intermediate":  "Recognize this pattern, then apply it.",
            "advanced":      "Recognize this pattern, then apply it.",
        },
    }
    if kind and kind in KIND_RULES:
        return KIND_RULES[kind].get(band_name) or KIND_RULES[kind].get("intermediate")

    # Final — generic encouragement
    return {
        "beginner_low":  "Let's work on this together.",
        "beginner_high": "Let's work on this.",
        "intermediate":  "Let's work on this.",
        "advanced":      "Focus on this pattern.",
    }.get(band_name, "Let's work on this.")


def _gap_cta(band_name: str, gap: str) -> str:
    """Gap-specific CTA copy. Coaching language, not labels — 'Let's
    practice spotting threats' beats 'Practice this weakness'."""
    # beginner_low → 'we/us' collaborative framing
    # beginner_high → direct but kind
    # intermediate+ → puzzle framing with count
    GAP_COPY = {
        "tactical_oversight": {
            "beginner_low":  "Let's practice spotting their threats",
            "beginner_high": "Practice spotting threats",
            "intermediate":  "Solve 5 threat-detection puzzles",
            "advanced":      "Solve 5 threat-detection puzzles",
        },
        "ignore_threat": {
            "beginner_low":  "Let's practice spotting their threats",
            "beginner_high": "Practice spotting threats",
            "intermediate":  "Solve 5 threat-detection puzzles",
            "advanced":      "Solve 5 threat-detection puzzles",
        },
        "piece_safety": {
            "beginner_low":  "Let's practice keeping pieces safe",
            "beginner_high": "Practice piece safety",
            "intermediate":  "Solve 5 piece-safety puzzles",
            "advanced":      "Solve 5 piece-safety puzzles",
        },
        "calculation_depth": {
            "beginner_low":  "Let's play a slow game together",
            "beginner_high": "Play a slow game",
            "intermediate":  "Play a slow game with me",
            "advanced":      "Play a slow game with me",
        },
        "missed_tactic": {
            "beginner_low":  "Let's practice finding tactics",
            "beginner_high": "Practice finding tactics",
            "intermediate":  "Solve 5 tactics puzzles",
            "advanced":      "Solve 5 tactics puzzles",
        },
        "king_safety": {
            "beginner_low":  "Let's practice keeping your king safe",
            "beginner_high": "Practice king safety",
            "intermediate":  "Solve 5 king-safety puzzles",
            "advanced":      "Solve 5 king-safety puzzles",
        },
        "endgame_technique": {
            "beginner_low":  "Let's work through an endgame",
            "beginner_high": "Practice endgames",
            "intermediate":  "Do an endgame lesson",
            "advanced":      "Do an endgame lesson",
        },
        "conversion": {
            "beginner_low":  "Let's practice finishing a winning game",
            "beginner_high": "Practice converting wins",
            "intermediate":  "Play a game — convert the advantage",
            "advanced":      "Play a game — convert the advantage",
        },
    }
    mapping = GAP_COPY.get(gap, {})
    if mapping:
        return mapping.get(band_name) or mapping.get("intermediate") or "Practice this"
    # Unknown gap — warm-but-honest fallback
    return {
        "beginner_low":  "Let's practice this together",
        "beginner_high": "Let's work on this",
        "intermediate":  "Practice this weakness",
        "advanced":      "Practice this weakness",
    }.get(band_name, "Practice this")


def _action_for_band(band_name: str, focus: Dict) -> Dict[str, str]:
    """CTA text + destination. New flow: kind-based routing (not per-skill)."""
    # Engine 2 focus has `kind` and `content_ref` from pick_next_skill
    kind = focus.get("kind")
    content_ref = focus.get("content_ref") or ""
    skill_id = focus.get("skill_id") or focus.get("focus") or ""

    if kind and kind in KIND_ACTIONS:
        cfg = KIND_ACTIONS[kind]
        cta = cfg.get(band_name) or cfg.get("intermediate") or "Start"

        # Endgame needs a two-segment URL (/endgames/<category>/<lesson>).
        # Mate patterns aren't in endgame_theory_tree → route to coach.
        if kind == "endgame" and content_ref in ENDGAME_ROUTES:
            href = f"/endgames/{ENDGAME_ROUTES[content_ref]}"
        elif kind in ("endgame", "mate_pattern") and content_ref not in ENDGAME_ROUTES:
            # No theory-tree entry — teach via coached play with the skill
            href = f"/play-with-coach?focus={skill_id}"
        elif kind == "trap_set":
            # opening_curriculum.json uses underscores; TRAP_LIBRARY uses hyphens.
            # Normalize so /openings/:openingKey resolves.
            href = f"/openings/{content_ref.replace('-', '_')}"
        elif kind == "opening":
            # opening content_ref already uses underscores (italian_game, etc.)
            href = f"/openings/{content_ref}"
        else:
            href = (cfg.get("href") or "/play-with-coach").format(
                content_ref=content_ref, skill_id=skill_id
            )
        return {"cta": cta, "href": href, "medium": cfg.get("medium", "lesson")}

    # Engine 1 focus → route to /training/prescribed by gap with band+gap
    # aware CTA copy. No generic "Practice this weakness."
    gap = focus.get("gap") or focus.get("category")
    if gap:
        cta = _gap_cta(band_name, gap)
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
    """
    Return the most memorable 'this is the moment' position for the coach
    to display. Cascade fallbacks — we always want a board if any game has
    been analysed:

      1. Focus-specific:     postgame_analyses matching current coach_prescription
      2. Any recent loss:    postgame_analyses from last loss/draw
      3. Any recent postgame: most recent postgame_analyses doc
      4. Raw game analysis:  biggest cp_loss user move across last analysed game

    Returns {fen, move_number, opponent, game_id} or None (only when user
    has zero analysed games).
    """
    # ── 1. Focus-specific session ──
    fkey = focus.get("focus") or focus.get("skill_id")
    if fkey:
        pos = await _position_from_postgame(db, user_id, {"coach_prescription": fkey})
        if pos:
            return pos

    # ── 2. Any recent loss/draw session ──
    pos = await _position_from_postgame(
        db, user_id, {"game_result": {"$in": ["loss", "draw"]}}
    )
    if pos:
        return pos

    # ── 3. Any recent postgame at all ──
    pos = await _position_from_postgame(db, user_id, {})
    if pos:
        return pos

    # ── 4. Imported-game fallback — pull from game_analyses directly ──
    try:
        game = await db.games.find_one(
            {"user_id": user_id, "is_analyzed": True},
            sort=[("imported_at", -1)],
            projection={"game_id": 1, "user_color": 1, "result": 1, "_id": 0},
        )
        if not game:
            return None
        analysis = await db.game_analyses.find_one(
            {"game_id": game.get("game_id")},
            {"stockfish_analysis": 1, "_id": 0},
        )
        if not analysis:
            return None
        sf = analysis.get("stockfish_analysis") or {}
        moves = sf.get("move_evaluations") or []
        # Pick the user's worst move (biggest cp_loss, user-side parity)
        user_color = (game.get("user_color") or "white").lower()
        worst = None
        worst_cp = 0
        for mv in moves:
            mvn = mv.get("move_number", 0)
            is_user = (mvn % 2 == 1) if user_color == "white" else (mvn % 2 == 0)
            if not is_user:
                continue
            cp = abs(mv.get("cp_loss", 0) or 0)
            if cp > worst_cp:
                worst_cp = cp
                worst = mv
        if not worst:
            return None
        return {
            "fen": worst.get("fen_before") or worst.get("fen"),
            "move_number": worst.get("move_number"),
            "opponent": "your opponent",
            "game_id": game.get("game_id"),
        }
    except Exception as e:
        logger.debug(f"Imported-game critical-position fallback failed: {e}")
        return None


async def _position_from_postgame(db, user_id: str, extra_query: Dict) -> Optional[Dict]:
    """Helper: extract the worst user move from a postgame_analyses doc matching
    the given query. Returns None if no match or no move_history."""
    try:
        query = {"user_id": user_id, **extra_query}
        doc = await db.postgame_analyses.find_one(
            query, sort=[("created_at", -1)],
            projection={"session_id": 1, "_id": 0}
        )
        if not doc or not doc.get("session_id"):
            return None
        session = await db.coach_sessions.find_one(
            {"session_id": doc["session_id"]},
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
            "game_id": doc["session_id"],
        }
    except Exception as e:
        logger.debug(f"Postgame position lookup failed: {e}")
        return None
