"""
Smart Coaching — LLM-powered, position-aware coaching text.

Uses the LLM with full context to generate genuinely insightful coaching,
not templates. Every coaching message is specific to THIS position, THIS
player, THIS moment.

Context fed to LLM:
- FEN + what the move does (capture, check, develop, etc.)
- V2 teaching intent (what the coach is trying to teach)
- Position reader features (pins, forks, hanging pieces, development)
- Stockfish best moves and evaluation
- Player profile (rating, weaknesses, patterns)
- Game phase (opening/middlegame/endgame)
- Opening theory (if in a known opening)
"""

import chess
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


async def generate_smart_coach_explanation(
    board_before: chess.Board,
    move: chess.Move,
    user_color: str,
    v2_context: Optional[Dict] = None,
    position_features: Optional[List] = None,
    player_weaknesses: Optional[List[str]] = None,
    user_rating: int = 1200,
    opening_name: Optional[str] = None,
) -> Dict:
    """
    Generate position-specific coaching using LLM.

    Returns dict with: explanation, plan, hint_for_user, teaching_point, opponent_opportunity
    """
    from llm_service import call_llm
    from services.position_reader import read_position

    move_san = board_before.san(move)
    piece = board_before.piece_at(move.from_square)
    captured = board_before.piece_at(move.to_square)
    coach_color = piece.color if piece else chess.WHITE
    user_chess_color = chess.WHITE if user_color == "white" else chess.BLACK

    board_after = board_before.copy()
    board_after.push(move)

    # Gather position context
    fen_after = board_after.fen()
    phase = _get_phase(board_after)

    # Get position features from the reader
    if not position_features:
        try:
            pos_data = read_position(fen_after, user_color, user_rating)
            position_features = pos_data.get("features", [])
        except Exception:
            position_features = []

    # Scan for opponent opportunities (what can the student exploit?)
    opportunities = _scan_opportunities(board_after, user_chess_color)

    # Build the move description
    move_desc = _describe_move(board_before, move, piece, captured)

    # V2 intent info
    intent = ""
    intent_reason = ""
    if v2_context and v2_context.get("v2"):
        intent = v2_context.get("teaching_goal", "")
        intent_reason = v2_context.get("why_instructive", "")

    # Position features as text
    feature_text = ""
    if position_features:
        feature_lines = [f"- {f.title}: {f.description}" for f in position_features[:4]]
        feature_text = "\n".join(feature_lines)

    # Build prompt
    system_prompt = f"""You are a chess coach sitting next to a {user_rating}-rated player during a game.
You just played a move as their opponent. Explain YOUR move to teach them.

Rules:
- Talk directly to the student ("I played...", "Notice how...", "Can you see...")
- Be specific to THIS position — no generic principles
- Ask ONE question that makes them look at the board
- If you see something they can exploit, hint at it without giving the answer
- Keep it under 3 sentences for explanation, 1 sentence for the question
- Never say the best move — make them find it
- Phase: {phase}
{f'- Opening: {opening_name}' if opening_name else ''}
{f'- Student weaknesses: {", ".join(player_weaknesses)}' if player_weaknesses else ''}
{f'- Teaching intent: {intent} ({intent_reason})' if intent else ''}"""

    user_prompt = f"""Position after my move: {fen_after}
I played: {move_san} ({move_desc})
{f'Position features the student should notice:' + chr(10) + feature_text if feature_text else ''}
{f'Opportunities for the student: {opportunities}' if opportunities else ''}

Respond in this exact JSON format (no markdown, just raw JSON):
{{"explanation": "what my move does and why", "question": "one question to make them think", "hint": "subtle hint about what they should look for"}}"""

    try:
        response = await call_llm(system_prompt, user_prompt)

        # Parse JSON response
        import json
        # Clean up response — sometimes LLM wraps in markdown
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()

        data = json.loads(clean)

        return {
            "move_san": move_san,
            "explanation": data.get("explanation", f"I played {move_san}."),
            "plan": "",  # LLM doesn't need a separate plan — it's in the explanation
            "threats": [],
            "teaching_point": "",
            "hint_for_user": data.get("question", ""),
            "opponent_opportunity": {
                "type": "llm",
                "message": data.get("hint", ""),
            } if data.get("hint") else None,
        }

    except Exception as e:
        logger.warning(f"[SMART-COACHING] LLM call failed, falling back to template: {e}")
        # Fallback to template-based explanation
        return None


async def generate_smart_user_feedback(
    board_before: chess.Board,
    user_move: chess.Move,
    best_move_san: Optional[str],
    cp_loss: int,
    severity: str,
    fundamental_violated: Optional[str],
    coach_intent: Optional[str],
    user_rating: int = 1200,
    phase: str = "middlegame",
) -> Optional[Dict]:
    """
    Generate position-specific feedback on the user's move using LLM.

    Only called for mistakes/blunders — good moves get brief praise without LLM.
    """
    if severity in ("good", "brilliant"):
        return None  # No LLM needed for good moves

    from llm_service import call_llm

    move_san = board_before.san(user_move)
    piece = board_before.piece_at(user_move.from_square)
    board_after = board_before.copy()
    board_after.push(user_move)

    move_desc = _describe_move(board_before, user_move, piece,
                               board_before.piece_at(user_move.to_square))

    # Map fundamental to what they should have checked
    fundamental_labels = {
        "check_opponents_move": "checking what the opponent's last move threatened",
        "hanging_pieces": "checking if all their pieces are defended",
        "king_safety": "their king's safety",
        "calculate": "calculating the opponent's response",
        "development": "developing new pieces instead of moving the same one",
        "center_control": "fighting for the center",
        "have_a_plan": "having a clear plan",
    }
    fundamental_text = fundamental_labels.get(fundamental_violated, "")

    system_prompt = f"""You are a chess coach. Your {user_rating}-rated student just made a {severity} (lost {cp_loss} centipawns).
Your job: ask ONE Socratic question that makes them find the problem themselves.

Rules:
- Do NOT tell them the answer or the best move
- Ask about what they MISSED, not what they should do
- Reference specific pieces and squares on the board
- One question only, under 20 words
- Phase: {phase}
{f'- They failed at: {fundamental_text}' if fundamental_text else ''}
{f'- You were trying to teach: {coach_intent}' if coach_intent else ''}"""

    user_prompt = f"""Position before their move: {board_before.fen()}
They played: {move_san} ({move_desc})
Best move was: {best_move_san or 'unknown'}
Position after: {board_after.fen()}

Respond in JSON: {{"question": "the Socratic question", "hint": "what they should look at if they can't answer"}}"""

    try:
        response = await call_llm(system_prompt, user_prompt)
        import json
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
        return json.loads(clean)
    except Exception as e:
        logger.warning(f"[SMART-COACHING] User feedback LLM failed: {e}")
        return None


def _describe_move(board, move, piece, captured):
    """Describe what a move does in plain English."""
    parts = []
    if board.is_castling(move):
        side = "kingside" if chess.square_file(move.to_square) > 4 else "queenside"
        return f"{side} castling"
    if captured:
        parts.append(f"captures {chess.piece_name(captured.piece_type)} on {chess.square_name(move.to_square)}")
    if piece:
        parts.append(f"{chess.piece_name(piece.piece_type)} from {chess.square_name(move.from_square)} to {chess.square_name(move.to_square)}")

    board_after = board.copy()
    board_after.push(move)
    if board_after.is_check():
        parts.append("gives check")

    return "; ".join(parts) if parts else "quiet move"


def _get_phase(board):
    pieces = len(board.piece_map())
    if pieces >= 28:
        return "opening"
    elif pieces >= 14:
        return "middlegame"
    else:
        return "endgame"


def _scan_opportunities(board, student_color):
    """Quick scan for what the student can exploit in this position."""
    try:
        from coach_play.teaching.pattern_detectors import find_hanging_pieces, find_fork_opportunities
        coach_color = not student_color

        hanging, underdefended = find_hanging_pieces(board, victim_color=coach_color)
        forks = find_fork_opportunities(board, forker_color=student_color)

        parts = []
        if hanging:
            names = [f"{chess.piece_name(h.piece_type)} on {chess.square_name(h.square)}" for h in hanging]
            parts.append(f"Coach has undefended: {', '.join(names)}")
        if forks:
            parts.append(f"Student can fork {len(forks)} targets")
        if underdefended:
            names = [f"{chess.piece_name(h.piece_type)} on {chess.square_name(h.square)}" for h in underdefended]
            parts.append(f"Under pressure: {', '.join(names)}")
        return "; ".join(parts) if parts else ""
    except Exception:
        return ""
