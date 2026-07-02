"""
Session Goal Service — Coaching Presence v1 (spine arc, step 1).

Derives ONE forward-framed session goal for a Play-with-Coach game, in simple
English, from the EXISTING player identity engine (player_identity_engine.py) —
the brain is already built; this connects it to the in-the-moment coaching.

Source of truth (per docs/coaching_presence_scope.md "Reality check"):
  - `compute_player_identity` (primary leak + weak phase) = WHO the player is.
  - If the identity is confident enough -> a PERSONAL goal from the leak/phase.
  - Otherwise (thin data, <8 analyzed games) -> a rating-BAND default.

Truth constraint: we never assert a personal focus the data can't support — the
identity engine already gates on >=8 games and carries a confidence label; below
that we fall back to the band default ("still getting to know you" honesty).

Voice: simple English, no jargon (routes through the same discipline as captions —
/check-voice, /rewrite-for-1200). No "fianchetto/zwischenzug"; name the action.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Primary-leak -> forward-framed goal (simple English, one thing to work on today).
# Keys match player_identity_engine.LEAK_INTERPRETATIONS.
_LEAK_GOALS = {
    "hanging_piece_blindness": "Today's one rule: before every move, a quick check — is anything of mine left undefended?",
    "threat_blindness":        "Today we're working on reading your opponent's threats — what they're trying to do — before you move.",
    "calculation_depth":       "Today, let's slow down and look one move further before you commit.",
    "tactical_oversight":      "Today, look for forcing moves first — checks, captures, and threats — before quiet moves.",
    "time_pressure":           "Today, let's keep a steady pace, so you're not rushing the important moves at the end.",
    "advantage_collapse":      "Today, when you're winning, slow down and close it out — the win isn't done until it's done.",
    "overconfidence":          "Today, when you're ahead, stay careful — keep playing solid moves instead of rushing.",
    "positional_misread":      "Today, pick one clear plan each move and stick with it.",
    "defensive_lapse":         "Today, when you're under pressure, slow down and find the solid, safe move.",
}

# Weak-phase -> goal (used when the leak has no clean mapping).
_PHASE_GOALS = {
    "opening":    "Today, let's get a clean start — develop your pieces and get your king safe early.",
    "middlegame": "Today, when the position gets busy, slow down and check before you commit.",
    "endgame":    "Today, let's focus on the endgame — patient, precise, convert the advantage.",
}

# Appended to the leak goal to anchor WHERE it shows up. Gives leak x phase
# differentiation so two users with the same leak but different weak phases get
# different goals (avoids the 83%-identical "advantage_collapse" goal problem).
_PHASE_TAIL = {
    "opening":    "Watch the opening especially — early slips set the tone.",
    "middlegame": "It bites most when the position gets complex.",
    "endgame":    "Watch the endgame especially — that's where it tends to slip.",
}

# Rating-band default (no confident identity yet). Mirrors the per-band "thinking we
# install" table in the scope doc. Band keys match deterministic_coach_service.RATING_BANDS.
_BAND_GOALS = {
    "beginner_low":  "Today's one rule: before every move, check — can my opponent take any of my pieces?",
    "beginner_high": "Today we're working on spotting your opponent's threats before you move.",
    "intermediate":  "Today, let's look one move deeper — what's my opponent's best reply — before you commit.",
    "advanced":      "Today, let's focus on converting your advantages cleanly, without letting the win slip.",
}
_BAND_GOAL_FALLBACK = "Today, let's keep your pieces safe — a quick check before each move."


def _band_default_goal(user_rating: Optional[int]) -> Dict:
    # Compute the band KEY directly from the documented RATING_BANDS thresholds
    # (<1000 / 1000-1399 / 1400-1799 / 1800+). We don't call get_rating_band here
    # because it returns the band *dict*, not the key — using that as a lookup key
    # raises "unhashable type: dict".
    r = user_rating or 800
    band = ("beginner_low" if r < 1000 else "beginner_high" if r < 1400
            else "intermediate" if r < 1800 else "advanced")
    return {
        "text": _BAND_GOALS.get(band, _BAND_GOAL_FALLBACK),
        "focus_area": None,
        "source": "band_default",
        "band": band,
        "confidence": "getting_to_know_you",
    }


async def derive_session_goal(db, user_id: str, user_rating: Optional[int] = None) -> Dict:
    """
    Return one session goal:
      {text, focus_area, source: "active_focus"|"identity"|"band_default", ...}

    Priority order (2026-07-03 — spine wiring):
      1. active_focus  — user has a locked weakness focus from
                          primary_weakness_picker via focus_bridge. Authoritative.
      2. identity      — player_identity_engine leak+phase mapping.
      3. band_default  — rating-band fallback.
    """
    # ── (1) active_focus is the authoritative source ─────────────────
    try:
        from services.focus_bridge import get_active_focus_bundle
        from services.primary_weakness_picker import _CLOSING_BY_SUBTYPE
        focus = await get_active_focus_bundle(db, user_id)
        if focus and focus.get("topic_key"):
            topic = focus["topic_key"]
            dom = focus.get("dominant_subtype")
            days_in = focus.get("days_into_focus") or 0
            days_left = focus.get("days_remaining") or 14
            # Closing line for the dominant subtype (if we have one)
            closing = _CLOSING_BY_SUBTYPE.get(dom) if dom else None
            topic_label = focus.get("topic_label") or topic.replace("_", " ").title()
            if closing:
                text = f"Today: {topic_label}. {closing}"
            else:
                text = f"Today: {topic_label} — day {days_in + 1} of 14."
            return {
                "text": text,
                "focus_area": topic,
                "dominant_subtype": dom,
                "days_into_focus": days_in,
                "days_remaining": days_left,
                "coaching_narrative": focus.get("coaching_narrative"),
                "source": "active_focus",
                "confidence": "locked",
                "focus_topic_key": topic,
            }
    except Exception as e:
        logger.warning("derive_session_goal: focus_bridge failed (%s) — fallback", str(e)[:80])

    # ── (2) identity — legacy path retained ──────────────────────────
    try:
        from player_identity_engine import compute_player_identity
        identity = await compute_player_identity(db, user_id)
    except Exception as e:
        logger.warning("derive_session_goal: identity failed (%s) — band default", str(e)[:80])
        return _band_default_goal(user_rating)

    if not identity or not identity.get("has_identity"):
        return _band_default_goal(user_rating)

    raw = identity.get("raw", {}) or {}
    # Coerce to str-or-None: the engine normally returns string keys, but guard
    # against an unexpected dict shape so a .get() never raises "unhashable type".
    leak = raw.get("leak") if isinstance(raw.get("leak"), str) else None
    phase = raw.get("phase") if isinstance(raw.get("phase"), str) else None
    conf = (identity.get("confidence") or {}).get("label", "")

    core = _LEAK_GOALS.get(leak)
    if core:
        tail = _PHASE_TAIL.get(phase)
        text = f"{core} {tail}" if tail else core
        focus = f"{leak}+{phase}" if phase else leak
    else:
        # no leak mapping — fall back to a phase-only goal
        text = _PHASE_GOALS.get(phase)
        focus = phase

    if not text:
        # identity exists but neither leak nor phase maps — stay honest, band default
        return _band_default_goal(user_rating)

    return {
        "text": text,
        "focus_area": focus,
        "source": "identity",
        "confidence": conf or "forming",
    }
