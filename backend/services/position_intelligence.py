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
from services.position_reader import read_position

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
        # Their piece is pinned — opportunity to pile up.
        # Title in position_reader is "Opponent's {piece} is pinned".
        "id": "exploit_pin",
        "conditions": lambda f, m, p: _has_feature_with_title_prefix(f, "tactics", "Opponent"),
        "priority": "tactics",
        "plan": lambda f, m, p: f"Their piece is pinned. {_get_feature_text_with_title_prefix(f, 'tactics', 'Opponent')}",
        "summary": lambda f, m, p: _build_summary([
            _get_feature_text_with_title_prefix(f, "tactics", "Opponent"),
            "Add more pressure to the pinned piece.",
        ]),
    },
    {
        # Our piece is pinned — defensive concern, not an opportunity.
        # Title in position_reader is "Your {piece} is pinned".
        "id": "defend_pinned_piece",
        "conditions": lambda f, m, p: _has_feature_with_title_prefix(f, "tactics", "Your") and "pinned" in (_get_feature_title_with_title_prefix(f, "tactics", "Your") or "").lower(),
        "priority": "defense",
        "plan": lambda f, m, p: f"Your piece is pinned. {_get_feature_text_with_title_prefix(f, 'tactics', 'Your')}",
        "summary": lambda f, m, p: _build_summary([
            _get_feature_text_with_title_prefix(f, "tactics", "Your"),
            "Be careful — moving the pinned piece can lose material.",
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

    # ── PIECE ACTIVITY ──
    {
        "id": "improve_passive_piece",
        "conditions": lambda f, m, p: _has_feature(f, "piece_activity", "stuck") or _has_feature(f, "piece_activity", "passive"),
        "priority": "positional",
        "plan": lambda f, m, p: f"You have a passive piece. {_get_feature_text(f, 'piece_activity', 'stuck') or _get_feature_text(f, 'piece_activity', 'passive')} Find it a better square.",
        "summary": lambda f, m, p: _build_summary([
            _get_feature_text(f, "piece_activity", "stuck") or _get_feature_text(f, "piece_activity", "passive"),
            "Every piece should have a job. Reposition the one that's doing the least.",
        ]),
    },

    # ── BISHOP BLOCKS PAWN ──
    {
        "id": "bishop_blocks_pawn",
        "conditions": lambda f, m, p: _has_feature(f, "development", "blocks"),
        "priority": "development",
        "plan": lambda f, m, p: f"{_get_feature_text(f, 'development', 'blocks')} Move the bishop to a diagonal where it doesn't block your own pawns.",
        "summary": lambda f, m, p: _build_summary([
            _get_feature_text(f, "development", "blocks"),
            "Bishops work best on open diagonals.",
        ]),
    },

    # ── SLIGHT ADVANTAGE: IMPROVE ──
    {
        "id": "slight_advantage",
        "conditions": lambda f, m, p: 0.5 <= m.get("advantage", 0) < 3 and p == "middlegame",
        "priority": "positional",
        "plan": lambda f, m, p: "You have a small advantage. Don't rush — improve your worst piece and look for a favorable trade.",
        "summary": lambda f, m, p: _build_summary([
            m.get("eval_text", "Slight edge."),
            "Find your least active piece and give it a better square.",
        ]),
    },

    # ── EQUAL MIDDLEGAME: CREATE IMBALANCE ──
    {
        "id": "equal_middlegame",
        "conditions": lambda f, m, p: abs(m.get("advantage", 0)) < 0.5 and p == "middlegame",
        "priority": "positional",
        "plan": lambda f, m, p: _equal_middlegame_plan(f, m),
        "summary": lambda f, m, p: _equal_middlegame_summary(f, m),
    },

    # ── EQUAL OPENING: DEVELOP AND CASTLE ──
    {
        "id": "equal_opening",
        "conditions": lambda f, m, p: abs(m.get("advantage", 0)) < 1 and p == "opening",
        "priority": "development",
        "plan": lambda f, m, p: "Develop your remaining pieces and castle. Don't start attacking until your pieces are out.",
        "summary": lambda f, m, p: _build_summary([
            m.get("eval_text", "Position is balanced."),
            "Focus on development and king safety before looking for tactics.",
        ]),
    },
]


def _equal_middlegame_plan(features, meta):
    """Generate a specific plan for equal middlegame positions."""
    # Try to find something concrete to suggest
    if _has_feature(features, "pawn_structure", "weak"):
        return f"The position is equal. {_get_feature_text(features, 'pawn_structure', 'weak')} Target their pawn weaknesses."
    if _has_feature(features, "piece_activity", "open"):
        return f"The position is equal. {_get_feature_text(features, 'piece_activity', 'open')} Control the open file with your rook."
    if _has_feature(features, "center", ""):
        return "The position is equal. Fight for the center — whoever controls it will get the initiative."
    return "Equal position. Look for your opponent's weakest point and build pressure there."


def _equal_middlegame_summary(features, meta):
    """Generate a specific summary for equal middlegame positions."""
    parts = [meta.get("eval_text", "Position is balanced.")]
    if _has_feature(features, "piece_activity", "stuck"):
        parts.append(_get_feature_text(features, "piece_activity", "stuck"))
    elif _has_feature(features, "pawn_structure", ""):
        parts.append(_get_feature_text(features, "pawn_structure", ""))
    else:
        parts.append("Look for the weakest point in your opponent's position and build pressure.")
    return _build_summary(parts)


# ─── LLM-POWERED BOARD READING ────────────────────────────────────────

async def read_board_deep(
    fen: str,
    user_color: str = "white",
    user_rating: int = 1200,
) -> Dict:
    """
    Deep board reading using LLM synthesis on top of concrete board data.

    Flow:
    1. Extract concrete facts from the board (pieces, attacks, structure)
    2. Send to LLM with a tight prompt
    3. Return natural, specific, board-aware coaching text

    Falls back to deterministic read_board_like_a_coach if LLM fails.
    """
    # Validate FEN early — if it's malformed, we can't do anything.
    try:
        chess.Board(fen)
    except Exception:
        return read_board_like_a_coach(fen, user_color, user_rating)

    # Step 1: Compute the DETERMINISTIC coach plan. This is our ground truth —
    # the actual plan we're willing to recommend, derived from verifiable
    # board facts (hanging pieces, threats, king safety, etc.). The LLM's
    # role is voice rewriting only; it does not propose moves.
    deterministic = read_board_like_a_coach(fen, user_color, user_rating)
    grounded_plan = (deterministic.get("plan") or "").strip()

    # If the deterministic layer has nothing to say, we have nothing to say.
    # Better to return the stock plan than to ask an LLM to invent one.
    if not grounded_plan:
        return deterministic

    # Step 2: Rewrite-only LLM call. The prompt is constrained — the LLM may
    # NOT introduce new moves, piece names, or tactics. It may only rephrase
    # the grounded plan in a more natural coach voice.
    try:
        from llm_service import call_llm

        system = (
            f"You are a chess coach talking to a player rated around {user_rating}. "
            "You have been given a short coaching plan for the current position. "
            "Your ONLY job is to rewrite that plan in warm, natural coach voice.\n\n"
            "Hard rules:\n"
            "- ONE or TWO short sentences. No paragraphs, no multi-step plans.\n"
            "- DO NOT introduce any move, piece, square, tactic, or idea that is NOT in the input plan. "
            "If the input doesn't name Bxb5, you MUST NOT name Bxb5. Invent nothing.\n"
            "- Keep the same moves and ideas the input already names. Only change the WORDS.\n"
            "- Never use engine language (eval, centipawns, accuracy).\n"
            "- No filler ('potentially', 'consider moves like', 'take advantage of'). Say the thing directly.\n"
            "- If the input plan is already good, output it with minimal changes."
        )

        user_msg = (
            f"Input plan to rewrite:\n{grounded_plan}\n\n"
            "Rewrite this in coach voice, following the rules above. "
            "Output only the rewritten sentence(s), nothing else."
        )

        llm_response = await call_llm(system, user_msg)

        if llm_response and llm_response.strip():
            rewritten = llm_response.strip().strip('"').strip("'")
            # Sanity cap: if the LLM ignored us and produced a paragraph, fall
            # back. The constraint is "one or two short sentences" — anything
            # much longer is a sign of drift.
            if len(rewritten) <= 280:
                return {
                    **deterministic,
                    "plan": rewritten,
                    "focus": rewritten.split(".")[0] + ".",
                    "source": "llm-rewrite",
                }

    except Exception as e:
        logger.debug(f"LLM rewrite failed, using deterministic plan: {e}")

    # Fallback: the deterministic plan, untouched.
    return deterministic


def _extract_board_facts(board: chess.Board, user_color: chess.Color, opp_color: chess.Color) -> str:
    """
    Extract concrete, verifiable facts from the board.
    No opinions, no templates — just what's on the board.
    This gives the LLM real data to work with.
    """
    NAMES = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
             chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}
    facts = []

    # Material count
    user_pieces = {}
    opp_pieces = {}
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p:
            continue
        name = NAMES.get(p.piece_type, "?")
        sq_name = chess.square_name(sq)
        if p.color == user_color:
            user_pieces[sq_name] = name
        else:
            opp_pieces[sq_name] = name

    facts.append(f"Your pieces: {', '.join(f'{v} on {k}' for k, v in sorted(user_pieces.items()))}")
    facts.append(f"Opponent pieces: {', '.join(f'{v} on {k}' for k, v in sorted(opp_pieces.items()))}")

    # Material balance
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    user_mat = sum(values.get(board.piece_at(sq).piece_type, 0) for sq in chess.SQUARES
                   if board.piece_at(sq) and board.piece_at(sq).color == user_color)
    opp_mat = sum(values.get(board.piece_at(sq).piece_type, 0) for sq in chess.SQUARES
                  if board.piece_at(sq) and board.piece_at(sq).color == opp_color)
    diff = user_mat - opp_mat
    if diff > 0:
        facts.append(f"You are ahead by {diff} points of material.")
    elif diff < 0:
        facts.append(f"You are behind by {abs(diff)} points of material.")
    else:
        facts.append("Material is equal.")

    # King positions and safety
    user_king = board.king(user_color)
    opp_king = board.king(opp_color)
    if user_king:
        facts.append(f"Your king is on {chess.square_name(user_king)}.")
    if opp_king:
        opp_king_sq = chess.square_name(opp_king)
        # Pawn shield check
        king_file = chess.square_file(opp_king)
        king_rank = chess.square_rank(opp_king)
        shield_rank = king_rank + (-1 if opp_color == chess.WHITE else 1)
        missing_shield = []
        if 0 <= shield_rank <= 7:
            for f in [max(0, king_file - 1), king_file, min(7, king_file + 1)]:
                sq = chess.square(f, shield_rank)
                p = board.piece_at(sq)
                if not (p and p.piece_type == chess.PAWN and p.color == opp_color):
                    missing_shield.append(chess.square_name(sq))
        if missing_shield:
            facts.append(f"Opponent king on {opp_king_sq}. Pawn shield missing on: {', '.join(missing_shield)}.")
        else:
            facts.append(f"Opponent king on {opp_king_sq} with intact pawn shield.")

    # Hanging pieces (undefended and attacked)
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.piece_type == chess.KING:
            continue
        sq_name = chess.square_name(sq)
        attacked = board.is_attacked_by(not p.color, sq)
        defended = board.is_attacked_by(p.color, sq)
        if attacked and not defended and p.piece_type != chess.PAWN:
            owner = "Your" if p.color == user_color else "Opponent's"
            facts.append(f"{owner} {NAMES[p.piece_type]} on {sq_name} is undefended and under attack!")

    # Pinned pieces
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.piece_type == chess.KING:
            continue
        if board.is_pinned(p.color, sq):
            owner = "Your" if p.color == user_color else "Opponent's"
            facts.append(f"{owner} {NAMES[p.piece_type]} on {chess.square_name(sq)} is pinned.")

    # Open files with rooks
    for file_idx in range(8):
        has_pawn = False
        for rank in range(8):
            p = board.piece_at(chess.square(file_idx, rank))
            if p and p.piece_type == chess.PAWN:
                has_pawn = True
                break
        if not has_pawn:
            file_letter = chr(97 + file_idx)
            rooks_on_file = []
            for rank in range(8):
                p = board.piece_at(chess.square(file_idx, rank))
                if p and p.piece_type == chess.ROOK:
                    owner = "Your" if p.color == user_color else "Opponent's"
                    rooks_on_file.append(f"{owner} rook")
            if rooks_on_file:
                facts.append(f"Open {file_letter}-file with {', '.join(rooks_on_file)} on it.")
            else:
                facts.append(f"Open {file_letter}-file — no rooks on it.")

    # Passed pawns
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.piece_type != chess.PAWN:
            continue
        file_idx = chess.square_file(sq)
        rank_idx = chess.square_rank(sq)
        direction = 1 if p.color == chess.WHITE else -1
        is_passed = True
        for check_rank in range(rank_idx + direction, 8 if direction == 1 else -1, direction):
            for check_file in [file_idx - 1, file_idx, file_idx + 1]:
                if 0 <= check_file <= 7:
                    check_sq = chess.square(check_file, check_rank)
                    cp = board.piece_at(check_sq)
                    if cp and cp.piece_type == chess.PAWN and cp.color != p.color:
                        is_passed = False
                        break
            if not is_passed:
                break
        if is_passed:
            owner = "Your" if p.color == user_color else "Opponent's"
            promo_dist = (7 - rank_idx) if p.color == chess.WHITE else rank_idx
            if promo_dist <= 4:
                facts.append(f"{owner} passed pawn on {chess.square_name(sq)} ({promo_dist} squares from promotion).")

    # Available checks
    if board.turn == user_color:
        checks = []
        for move in board.legal_moves:
            board.push(move)
            if board.is_check():
                checks.append(board.peek().uci())
            board.pop()
        if checks:
            check_sans = []
            for m in board.legal_moves:
                board.push(m)
                if board.is_check():
                    board.pop()
                    check_sans.append(board.san(m))
                else:
                    board.pop()
            if check_sans:
                facts.append(f"Available checks: {', '.join(check_sans[:4])}.")

    # Phase
    piece_count = len(board.piece_map())
    if piece_count >= 28:
        facts.append("Phase: opening.")
    elif piece_count >= 14:
        facts.append("Phase: middlegame.")
    else:
        facts.append("Phase: endgame.")

    return "\n".join(facts)


# ─── DETERMINISTIC BOARD READING (fast, no LLM) ──���───────────────────

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

    # Step 4: Fallback if no plan matched — build from what we DO have
    if not matched_plan:
        if features:
            top = features[0]
            second = features[1] if len(features) > 1 else None
            summary_parts = [top.get("description", "")]
            if second:
                summary_parts.append(second.get("description", ""))
            matched_plan = {
                "id": "general",
                "priority": "general",
                "plan": top.get("actionable", "Scan the board for the most important feature and act on it."),
                "summary": _build_summary(summary_parts),
            }
        else:
            # Truly quiet position — give phase-appropriate advice
            if phase == "opening":
                matched_plan = {
                    "id": "quiet_opening",
                    "priority": "development",
                    "plan": "Develop your pieces toward the center and castle. Every move should improve a piece.",
                    "summary": "Quiet position. Focus on getting all your pieces into the game before looking for tactics.",
                }
            elif phase == "endgame":
                matched_plan = {
                    "id": "quiet_endgame",
                    "priority": "endgame",
                    "plan": "Activate your king. In the endgame, the king is a fighting piece — walk it toward the center.",
                    "summary": "Endgame position. Your king should be active. Push passed pawns if you have them.",
                }
            else:
                matched_plan = {
                    "id": "quiet_middlegame",
                    "priority": "positional",
                    "plan": "No immediate threats. Find your least active piece and improve it. Whoever improves their pieces faster gets the advantage.",
                    "summary": "Quiet position. Look at each of your pieces — which one is doing the least? That's the one to move.",
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
            for f in features[:5]
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


def _has_feature_with_title_prefix(features: List[Dict], category: str, title_prefix: str) -> bool:
    """Match features whose title STARTS with a prefix (case-insensitive).
    Stricter than _has_feature — needed when the title's leading word
    determines whose piece the feature is about (e.g., "Your knight is
    pinned" vs "Opponent's knight is pinned" both contain "pinned" but
    mean opposite things)."""
    pref = title_prefix.lower()
    for f in features:
        if f.get("category", "") == category and f.get("title", "").lower().startswith(pref):
            return True
    return False


def _get_feature_text_with_title_prefix(features: List[Dict], category: str, title_prefix: str) -> str:
    pref = title_prefix.lower()
    for f in features:
        if f.get("category", "") == category and f.get("title", "").lower().startswith(pref):
            return f.get("description", "")
    return ""


def _get_feature_title_with_title_prefix(features: List[Dict], category: str, title_prefix: str) -> str:
    pref = title_prefix.lower()
    for f in features:
        if f.get("category", "") == category and f.get("title", "").lower().startswith(pref):
            return f.get("title", "")
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
