"""
/today composer — turns the backend's intelligence into ONE coach voice.

The rest of the app has cards, screens, systems. /today has sentences.
This module reads focus_resolver (Engine 1), engine2_skill_builder (Engine 2),
game history, and coach_memory and returns a single shape the UI renders
as one screen with one action.

No menus. No cards. A sentence, an evidence line, a board, a button.

Voice rules:
  - Use the player's name when we have it
  - Lead with what's broken, not a label
  - Always show evidence (count, recent example)
  - One action verb ("Play", "Solve", "Watch")
  - Never a list of options as primary UI

LLM is NOT used here — voice is deterministic composed sentences so the
coach sounds consistent every time. LLM can be added later for polish.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── SKILL → ACTION mapping ───────────────────────────────────────────
# Each skill the coach might prescribe → a concrete action verb + destination.
# Pattern-drill (tactical) skills → puzzles. Meta-habits + conversion → live game.

SKILL_ACTIONS = {
    # Meta-habit — only built through live play with guardian
    "pre_move_check": {
        "verb": "Play",
        "cta": "Play a slow game with me",
        "href_template": "/play-with-coach?focus=pre_move_check&slow=true",
        "medium": "live_game",
    },
    # Tactical pattern — puzzles are the right medium
    "hanging_piece": {
        "verb": "Solve",
        "cta": "Solve 5 piece-safety puzzles",
        "href_template": "/training/prescribed?weakness=piece_safety",
        "medium": "puzzles",
    },
    "opponent_threat": {
        "verb": "Solve",
        "cta": "Solve 5 threat-detection puzzles",
        "href_template": "/training/prescribed?weakness=tactical_oversight",
        "medium": "puzzles",
    },
    "king_safety": {
        "verb": "Solve",
        "cta": "Solve 5 king-safety puzzles",
        "href_template": "/training/prescribed?weakness=king_safety",
        "medium": "puzzles",
    },
    "fork": {
        "verb": "Solve",
        "cta": "Solve 5 fork puzzles",
        "href_template": "/training/prescribed?weakness=missed_tactic",
        "medium": "puzzles",
    },
    "pin": {
        "verb": "Solve",
        "cta": "Solve 5 pin puzzles",
        "href_template": "/training/prescribed?weakness=missed_tactic",
        "medium": "puzzles",
    },
    "free_piece_capture": {
        "verb": "Solve",
        "cta": "Solve 5 winning-capture puzzles",
        "href_template": "/training/prescribed?weakness=missed_tactic",
        "medium": "puzzles",
    },
    "simple_mates": {
        "verb": "Practice",
        "cta": "Practice basic mates",
        "href_template": "/training/prescribed?weakness=endgame_technique",
        "medium": "puzzles",
    },
    "king_pawn_endgame": {
        "verb": "Practice",
        "cta": "Work through 5 endgame positions",
        "href_template": "/training/prescribed?weakness=endgame_technique",
        "medium": "puzzles",
    },
    "conversion": {
        "verb": "Play",
        "cta": "Play a game — convert the advantage",
        "href_template": "/play-with-coach?focus=conversion",
        "medium": "live_game",
    },
    "basic_trade": {
        "verb": "Play",
        "cta": "Play a game — practice trades",
        "href_template": "/play-with-coach?focus=basic_trade",
        "medium": "live_game",
    },
    "opening_principles": {
        "verb": "Study",
        "cta": "Study opening fundamentals",
        "href_template": "/openings",
        "medium": "lesson",
    },
}


# ── VOICE TEMPLATES ──────────────────────────────────────────────────
# Conversational headlines keyed on the focus. The coach speaks, doesn't label.

FOCUS_HEADLINES = {
    "hanging_piece":    "You keep hanging pieces. Let's fix that today.",
    "piece_safety":     "You keep hanging pieces. Let's fix that today.",
    "one_move_blunder": "You keep hanging pieces. Let's fix that today.",
    "missed_fork":      "You're missing forks that are right there.",
    "missed_pin":       "You're not seeing pins on the board.",
    "missed_skewer":    "You're not seeing skewers on the board.",
    "missed_discovery": "You're not seeing discovered attacks.",
    "missed_overload":  "You keep missing overloaded defenders.",
    "tactical_miss":    "You're missing tactics that are right there.",
    "missed_tactic":    "You're missing tactics that are right there.",
    "tactical_oversight": "You're missing your opponent's replies.",
    "king_safety":      "Your king is getting caught. Let's work on it.",
    "ignore_threat":    "You're not seeing what your opponent is doing.",
    "calculation_error": "You stop calculating one move too early.",
    "calculation_depth": "You stop calculating one move too early.",
    "threw_winning":    "You keep throwing winning positions.",
    "conversion":       "You keep throwing winning positions.",
    "opening_disaster": "Your games go wrong in the first 10 moves.",
    "endgame_collapse": "You're reaching endgames you should win — and not winning them.",
    "time_collapse":    "You're losing on the clock. Let's slow down.",
    "pre_move_check":   "You move too fast. Let's learn to pause.",
}


# ── COMPOSER ─────────────────────────────────────────────────────────


async def compose_today(db, user_id: str) -> Dict[str, Any]:
    """
    Build the single-screen prescription for /today.

    Shape:
        {
          "greeting": "Hey Mohit.",
          "headline": "You're missing tactics that are right there.",
          "evidence": ["Missed one in 7 of your last 10 games", "Most recent: move 16 vs MuchoGusto"],
          "rule": "Before every move — check captures, checks, and threats.",
          "board": { "fen": "...", "game_id": "...", "move_number": 16 } | None,
          "action": { "verb": "Solve", "cta": "Solve 5 piece-safety puzzles", "href": "/training/prescribed?weakness=piece_safety" },
          "streak": { "clean": 1, "target": 3 } | None,
          "alternates": [
            { "label": "I want to play freely", "href": "/play-with-coach" },
            { "label": "let me work on openings", "href": "/play-with-coach?focus=opening_principles" },
            { "label": "take today off", "action": "dismiss" }
          ]
        }
    """
    out: Dict[str, Any] = {
        "greeting": None,
        "headline": None,
        "evidence": [],
        "rule": None,
        "board": None,
        "action": None,
        "streak": None,
        "alternates": [],
        "source": "none",  # "engine1" | "engine2" | "none"
    }

    # 1. Greeting with name
    user = await db.users.find_one({"user_id": user_id}, {"email": 1, "display_name": 1, "name": 1, "_id": 0})
    name = _extract_first_name(user)
    out["greeting"] = f"Hey {name}." if name else "Welcome back."

    # 2. Pick today's focus: Engine 1 first, Engine 2 as fallback
    focus_source, focus = await _pick_todays_focus(db, user_id)
    out["source"] = focus_source

    if not focus:
        # Nothing known yet — new user or no data
        out["headline"] = "Let's play a game so I can learn how you think."
        out["evidence"] = []
        out["action"] = {
            "verb": "Play",
            "cta": "Play with me",
            "href": "/play-with-coach",
        }
        return out

    # 3. Headline in the coach's voice
    out["headline"] = _compose_headline(focus)

    # 4. Evidence (concrete counts + recent example)
    out["evidence"] = await _gather_evidence(db, user_id, focus)

    # 5. Action verb + destination
    out["action"] = _compose_action(focus)

    # 6. Streak (if applicable — from focus_engine cluster tracker)
    out["streak"] = await _gather_streak(db, user_id)

    # 7. Rule line (short, memorable)
    out["rule"] = _rule_for_focus(focus)

    # 8. Recent critical position (board to show)
    out["board"] = await _find_critical_position(db, user_id, focus)

    # 9. Alternates — NOT a menu. Conversational options for "not feeling this."
    out["alternates"] = _compose_alternates(focus)

    return out


# ── INTERNAL ─────────────────────────────────────────────────────────


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


async def _pick_todays_focus(db, user_id: str):
    """Pick Engine 1's active focus first; fall back to Engine 2's next skill."""
    # Engine 1 — via focus_resolver
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
                "skill_id": active.get("focus"),  # pattern-drill focus keys match skill_ids
            }
    except Exception as e:
        logger.debug(f"Engine 1 focus failed: {e}")

    # Engine 2 — via pick_next_skill
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
            }
    except Exception as e:
        logger.debug(f"Engine 2 pick failed: {e}")

    return "none", None


def _compose_headline(focus: Dict) -> str:
    """Pick a conversational sentence for the focus. Never a label or slug."""
    key = focus.get("focus") or focus.get("skill_id") or ""
    # Try multiple lookups — focus key, skill_id, category
    for candidate in (key, focus.get("skill_id"), focus.get("category")):
        if candidate and candidate in FOCUS_HEADLINES:
            return FOCUS_HEADLINES[candidate]
    # Fall back to the reason from the engine, else generic
    reason = focus.get("reason")
    if reason:
        return reason
    label = focus.get("label") or "Let's work on your play today."
    return label


async def _gather_evidence(db, user_id: str, focus: Dict) -> List[str]:
    """Return 1-2 evidence lines. Counts + most recent specific example."""
    evidence: List[str] = []

    # If Engine 2 skill, show seen/correct
    stats = focus.get("stats") or {}
    if stats and stats.get("seen"):
        seen = stats.get("seen", 0)
        wrong = stats.get("failed", stats.get("wrong", 0))
        if wrong >= 3:
            evidence.append(f"You missed it in {wrong} of your last {seen} games.")
        elif seen >= 5 and (stats.get("correct", 0) == 0):
            evidence.append(f"{seen} games in a row without hitting this cleanly.")

    # Engine 1 focus — pull from postgame_analyses
    if not evidence:
        fkey = focus.get("focus") or focus.get("skill_id")
        if fkey:
            recent = await db.postgame_analyses.find(
                {"user_id": user_id, "coach_prescription": fkey},
                {"_id": 0, "created_at": 1}
            ).sort("created_at", -1).limit(10).to_list(10)
            if recent:
                evidence.append(f"This has come up in {len(recent)} of your recent games.")

    # Most recent concrete example: find a game where this mistake fired
    critical = await _find_critical_position(db, user_id, focus)
    if critical and critical.get("move_number"):
        opponent = critical.get("opponent", "your opponent")
        evidence.append(f"Most recent — move {critical['move_number']} vs {opponent}.")

    return evidence[:2]  # keep it tight


def _compose_action(focus: Dict) -> Dict[str, str]:
    """Pick the concrete action verb + destination for this focus."""
    skill_id = focus.get("skill_id") or focus.get("focus")
    # Try direct skill match first
    if skill_id in SKILL_ACTIONS:
        cfg = SKILL_ACTIONS[skill_id]
        return {"verb": cfg["verb"], "cta": cfg["cta"], "href": cfg["href_template"], "medium": cfg["medium"]}

    # Category-based fallback
    CATEGORY_ACTIONS = {
        "tactical_miss":     SKILL_ACTIONS["fork"],
        "missed_tactic":     SKILL_ACTIONS["fork"],
        "one_move_blunder":  SKILL_ACTIONS["hanging_piece"],
        "piece_safety":      SKILL_ACTIONS["hanging_piece"],
        "calculation_error": SKILL_ACTIONS["pre_move_check"],
        "calculation_depth": SKILL_ACTIONS["pre_move_check"],
        "king_safety":       SKILL_ACTIONS["king_safety"],
        "endgame_collapse":  SKILL_ACTIONS["king_pawn_endgame"],
        "opening_disaster":  SKILL_ACTIONS["opening_principles"],
        "threw_winning":     SKILL_ACTIONS["conversion"],
        "conversion":        SKILL_ACTIONS["conversion"],
        "time_collapse":     SKILL_ACTIONS["pre_move_check"],
    }
    cat = focus.get("category") or focus.get("focus")
    cfg = CATEGORY_ACTIONS.get(cat)
    if cfg:
        return {"verb": cfg["verb"], "cta": cfg["cta"], "href": cfg["href_template"], "medium": cfg["medium"]}

    # Final fallback — play freely
    return {
        "verb": "Play",
        "cta": "Play with me",
        "href": "/play-with-coach",
        "medium": "live_game",
    }


def _compose_alternates(focus: Dict) -> List[Dict[str, str]]:
    """Conversational interrupts when the user says 'not feeling this today.'
    Never a full library menu — 3 curated paths."""
    alternates = []
    # Offer the other engine's path if we haven't picked it
    current_medium = None
    skill_id = focus.get("skill_id") or focus.get("focus")
    if skill_id in SKILL_ACTIONS:
        current_medium = SKILL_ACTIONS[skill_id]["medium"]

    if current_medium != "live_game":
        alternates.append({
            "label": "I'd rather just play a game",
            "href": "/play-with-coach",
        })

    if current_medium != "puzzles":
        alternates.append({
            "label": "let me work on tactics instead",
            "href": "/training/prescribed?weakness=current",
        })

    alternates.append({"label": "take today off", "action": "dismiss"})
    return alternates


def _rule_for_focus(focus: Dict) -> Optional[str]:
    """A short, memorable rule the user can repeat before every move."""
    RULES = {
        "pre_move_check":   "Before every move: what is my opponent threatening?",
        "hanging_piece":    "Before every move: is anything I own under attack?",
        "one_move_blunder": "Before every move: is anything I own under attack?",
        "opponent_threat":  "Before every move: what is my opponent threatening?",
        "tactical_miss":    "Every move: captures, checks, and threats.",
        "missed_tactic":    "Every move: captures, checks, and threats.",
        "fork":             "Look for your knight's forks first.",
        "pin":              "Pieces in front of higher-value pieces — that's a pin.",
        "king_safety":      "Before you attack, ask: is my king safe?",
        "calculation_error": "Before committing — what will they do next?",
        "calculation_depth": "Before committing — what will they do next?",
        "conversion":       "When ahead — trade pieces, not pawns.",
        "threw_winning":    "When ahead — simplify. Don't get creative.",
        "opening_disaster": "First 10 moves — develop, control center, castle.",
    }
    for k in (focus.get("focus"), focus.get("skill_id"), focus.get("category")):
        if k and k in RULES:
            return RULES[k]
    return None


async def _gather_streak(db, user_id: str) -> Optional[Dict]:
    """Pull clean-streak from focus_engine if it's tracking the current cluster."""
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
    """Most recent game where the focus problem showed up. Return the critical
    FEN + move number + opponent for the coach to display a real position."""
    try:
        # Find the most recent postgame analysis with a critical_moment matching this focus
        fkey = focus.get("focus") or focus.get("skill_id")
        query = {"user_id": user_id}
        if fkey:
            query["coach_prescription"] = fkey
        doc = await db.postgame_analyses.find_one(
            query, sort=[("created_at", -1)],
            projection={"session_id": 1, "game_result": 1, "created_at": 1, "_id": 0}
        )
        if not doc:
            return None
        session_id = doc.get("session_id")
        if not session_id:
            return None
        # Pull the session to get critical move
        session = await db.coach_sessions.find_one(
            {"session_id": session_id},
            {"move_history": 1, "opponent": 1, "_id": 0}
        )
        if not session:
            return None
        # Best heuristic: find move with biggest cp_loss
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
