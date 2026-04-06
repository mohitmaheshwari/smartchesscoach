"""
Position Intelligence Service — "How a coach sees a board"
==========================================================

Takes the raw observations from position_reader.py and CONNECTS them
into a single story: what's happening, what matters, and what to do.

A 1200 player can spot a hanging piece.
A coach sees: hanging piece + open file + weak king = attack now.

This service turns scattered features into ONE coherent plan.

Usage:
    from services.position_intelligence import read_board_like_a_coach

    result = read_board_like_a_coach(fen, user_color="white", user_rating=1200)
    # {
    #   "summary": "You're up a pawn and their king is stuck in the center. Attack now before they castle.",
    #   "phase": "middlegame",
    #   "material": "You're up a pawn. Small edge.",
    #   "plan": "Open the center and aim your pieces at their king.",
    #   "observations": [...],
    #   "focus": "Their king on e8 — it hasn't castled and has only 1 escape square.",
    #   "priority": "attack",
    # }
"""

import chess
import logging
from typing import Dict, List, Optional
from services.position_reader import read_position, PositionFeature

logger = logging.getLogger(__name__)


# ─── PLAN TEMPLATES ──────────────────────────────────────────────────
# Each plan combines multiple signals into one instruction.
# Priority order: whoever matches first wins.

PLAN_RULES = [
    # ── IMMEDIATE TACTICS ──
    {
        "id": "win_material",
        "conditions": lambda f, m, p: _has_feature(f, "tactics", "undefended"),
        "priority": "tactics",
        "plan": lambda f, m, p: f"You can win material. {_get_feature_text(f, 'tactics', 'undefended')}",
        "summary": lambda f, m, p: _build_summary([
            _get_feature_text(f, "tactics", "undefended"),
            "Take it if it's safe.",
        ]),
    },
    {
        "id": "save_piece",
        "conditions": lambda f, m, p: _has_feature(f, "tactics", "hanging"),
        "priority": "defense",
        "plan": lambda f, m, p: f"Your piece is in danger. {_get_feature_text(f, 'tactics', 'hanging')}",
        "summary": lambda f, m, p: _build_summary([
            _get_feature_text(f, "tactics", "hanging"),
            "Deal with this before anything else.",
        ]),
    },
    {
        "id": "exploit_pin",
        "conditions": lambda f, m, p: _has_feature(f, "tactics", "pinned"),
        "priority": "tactics",
        "plan": lambda f, m, p: f"Their piece is pinned. {_get_feature_text(f, 'tactics', 'pinned')}",
        "summary": lambda f, m, p: _build_summary([
            _get_feature_text(f, "tactics", "pinned"),
            "Add more pressure to the pinned piece.",
        ]),
    },

    # ── ATTACK THE KING ──
    {
        "id": "attack_exposed_king_winning",
        "conditions": lambda f, m, p: (
            _has_feature(f, "king_safety", "hasn't castled") and
            m.get("advantage", 0) >= 1 and
            p != "endgame"
        ),
        "priority": "attack",
        "plan": lambda f, m, p: "Open the center and attack their king. You're ahead in material and their king is exposed — don't trade pieces, attack.",
        "summary": lambda f, m, p: _build_summary([
            f"You're ahead in material.",
            _get_feature_text(f, "king_safety", "hasn't castled"),
            "This is the time to attack, not simplify.",
        ]),
    },
    {
        "id": "attack_exposed_king",
        "conditions": lambda f, m, p: _has_feature(f, "king_safety", "hasn't castled") and p != "endgame",
        "priority": "attack",
        "plan": lambda f, m, p: "Their king is stuck in the center. Open the position and use your developed pieces to create threats.",
        "summary": lambda f, m, p: _build_summary([
            _get_feature_text(f, "king_safety", "hasn't castled"),
            "Look for pawn pushes or piece moves that open lines toward their king.",
        ]),
    },
    {
        "id": "attack_weak_king",
        "conditions": lambda f, m, p: _has_feature(f, "king_safety", "pawn shield"),
        "priority": "attack",
        "plan": lambda f, m, p: "Their king's pawn shield is damaged. Aim your pieces at the weak squares around their king.",
        "summary": lambda f, m, p: _build_summary([
            _get_feature_text(f, "king_safety", "pawn shield"),
            "Point your bishops, rooks, and queen toward their king.",
        ]),
    },

    # ── DEVELOPMENT ──
    {
        "id": "develop_pieces",
        "conditions": lambda f, m, p: _has_feature(f, "development", "back rank") and p == "opening",
        "priority": "development",
        "plan": lambda f, m, p: "You have pieces sitting on the back rank. Develop them before starting any attack.",
        "summary": lambda f, m, p: _build_summary([
            _get_feature_text(f, "development", "back rank"),
            "Get your knights and bishops out. Don't move the same piece twice.",
        ]),
    },

    # ── CASTLE ──
    {
        "id": "castle_now",
        "conditions": lambda f, m, p: _has_feature(f, "king_safety", "still castle") and p in ("opening", "middlegame"),
        "priority": "safety",
        "plan": lambda f, m, p: "Castle as soon as you can. Your king is not safe in the center.",
        "summary": lambda f, m, p: _build_summary([
            "Your king is still in the center.",
            "Castle to get it safe and connect your rooks.",
        ]),
    },

    # ── WINNING: SIMPLIFY ──
    {
        "id": "simplify_winning",
        "conditions": lambda f, m, p: m.get("advantage", 0) >= 3,
        "priority": "convert",
        "plan": lambda f, m, p: "You're up significant material. Trade pieces, not pawns. Simplify into a winning endgame.",
        "summary": lambda f, m, p: _build_summary([
            m.get("eval_text", "You're ahead."),
            "Trade pieces to make the game simpler. The fewer pieces, the harder it is for them to come back.",
        ]),
    },

    # ── LOSING: COMPLICATE ──
    {
        "id": "complicate_losing",
        "conditions": lambda f, m, p: m.get("advantage", 0) <= -3,
        "priority": "survive",
        "plan": lambda f, m, p: "You're down material. Don't trade pieces — keep the position complicated. Look for tactical tricks.",
        "summary": lambda f, m, p: _build_summary([
            m.get("eval_text", "You're behind."),
            "Avoid trades. Keep the board complex. Your best chance is a tactical shot.",
        ]),
    },

    # ── ENDGAME: ACTIVATE KING ──
    {
        "id": "endgame_activate",
        "conditions": lambda f, m, p: p == "endgame",
        "priority": "endgame",
        "plan": lambda f, m, p: "This is an endgame. Activate your king — walk it toward the center. Push passed pawns.",
        "summary": lambda f, m, p: _build_endgame_summary(f, m),
    },

    # ── OPEN FILES ──
    {
        "id": "use_open_file",
        "conditions": lambda f, m, p: _has_feature(f, "piece_activity", "open") and p in ("middlegame", "endgame"),
        "priority": "piece_activity",
        "plan": lambda f, m, p: f"{_get_feature_text(f, 'piece_activity', 'open')} Rooks on open files control the game.",
        "summary": lambda f, m, p: _build_summary([
            _get_feature_text(f, "piece_activity", "open"),
        ]),
    },

    # ── CENTER CONTROL ──
    {
        "id": "fight_for_center",
        "conditions": lambda f, m, p: _has_feature(f, "center", "Opponent controls"),
        "priority": "positional",
        "plan": lambda f, m, p: "Your opponent controls the center. Challenge it with a pawn push or piece placement.",
        "summary": lambda f, m, p: _build_summary([
            _get_feature_text(f, "center", "Opponent controls"),
            "Push a pawn toward the center (d5, e5, c5, or f5) to fight back.",
        ]),
    },

    # ── PASSED PAWN ──
    {
        "id": "push_passed_pawn",
        "conditions": lambda f, m, p: _has_feature(f, "pawn_structure", "Passed pawn"),
        "priority": "convert",
        "plan": lambda f, m, p: f"{_get_feature_text(f, 'pawn_structure', 'Passed pawn')} Push it and support it with your pieces.",
        "summary": lambda f, m, p: _build_summary([
            _get_feature_text(f, "pawn_structure", "Passed pawn"),
            "A passed pawn is a future queen. Push it forward and protect it.",
        ]),
    },
]


# ─── MAIN ENTRY POINT ────────────────────────────────────────────────

def read_board_like_a_coach(
    fen: str,
    user_color: str = "white",
    user_rating: int = 1200
) -> Dict:
    """
    Read the board the way a coach would — connect the dots between
    individual observations into one coherent message.
    """
    # Step 1: Get raw observations from position_reader
    raw = read_position(fen, user_color, user_rating)
    features = raw.get("features", [])
    eval_text = raw.get("eval_text", "")
    phase = raw.get("phase", "middlegame")

    # Step 2: Compute material advantage
    try:
        board = chess.Board(fen)
        advantage = _compute_material_advantage(board, user_color)
    except Exception:
        board = None
        advantage = 0

    meta = {
        "eval_text": eval_text,
        "advantage": advantage,
    }

    # Step 3: Match the FIRST plan rule that fits
    matched_plan = None
    for rule in PLAN_RULES:
        try:
            if rule["conditions"](features, meta, phase):
                matched_plan = {
                    "id": rule["id"],
                    "priority": rule["priority"],
                    "plan": rule["plan"](features, meta, phase),
                    "summary": rule["summary"](features, meta, phase),
                }
                break
        except Exception as e:
            logger.debug(f"Plan rule {rule['id']} failed: {e}")
            continue

    # Step 4: Fallback if no plan matched
    if not matched_plan:
        if features:
            top = features[0]
            matched_plan = {
                "id": "general",
                "priority": "general",
                "plan": top.get("actionable", "Look at the whole board. What stands out?"),
                "summary": top.get("description", "Take a moment to scan the board."),
            }
        else:
            matched_plan = {
                "id": "neutral",
                "priority": "general",
                "plan": "The position is roughly equal. Improve your worst-placed piece.",
                "summary": "No immediate tactics. Look for the piece that's doing the least and find it a better square.",
            }

    # Step 5: Pick the single most important thing to focus on
    focus = ""
    if features:
        top_feature = features[0]
        focus = top_feature.get("description", "")

    return {
        "summary": matched_plan["summary"],
        "phase": phase,
        "material": eval_text,
        "plan": matched_plan["plan"],
        "plan_id": matched_plan["id"],
        "priority": matched_plan["priority"],
        "focus": focus,
        "observations": [
            {
                "title": f.get("title", ""),
                "description": f.get("description", ""),
                "actionable": f.get("actionable", ""),
                "category": f.get("category", ""),
            }
            for f in features[:3]
        ],
    }


# ─── HELPER FUNCTIONS ─────────────────────────────────────────────────

def _has_feature(features: List[Dict], category: str, title_contains: str) -> bool:
    """Check if any feature matches category and title substring."""
    for f in features:
        if f.get("category", "") == category and title_contains.lower() in f.get("title", "").lower():
            return True
    return False


def _get_feature_text(features: List[Dict], category: str, title_contains: str) -> str:
    """Get the description of a matching feature."""
    for f in features:
        if f.get("category", "") == category and title_contains.lower() in f.get("title", "").lower():
            return f.get("description", "")
    return ""


def _build_summary(parts: List[str]) -> str:
    """Join non-empty parts into a clean summary."""
    clean = [p.rstrip(".") + "." for p in parts if p]
    return " ".join(clean)


def _build_endgame_summary(features: List[Dict], meta: Dict) -> str:
    """Endgame-specific summary."""
    parts = ["This is an endgame."]

    if meta.get("advantage", 0) >= 1:
        parts.append("You're ahead — activate your king and push your pawns.")
    elif meta.get("advantage", 0) <= -1:
        parts.append("You're behind — try to create a passed pawn or find a fortress.")
    else:
        parts.append("Material is equal. The king becomes a strong piece — walk it to the center.")

    # Check for passed pawn
    passed = _get_feature_text(features, "pawn_structure", "Passed pawn")
    if passed:
        parts.append(passed)

    return _build_summary(parts)


def _compute_material_advantage(board: chess.Board, user_color: str) -> int:
    """Returns material advantage in pawns (positive = user ahead)."""
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    user_is_white = user_color == "white"

    white_total = sum(values.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == chess.WHITE)
    black_total = sum(values.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == chess.BLACK)

    if user_is_white:
        return white_total - black_total
    return black_total - white_total
