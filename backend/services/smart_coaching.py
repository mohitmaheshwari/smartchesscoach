"""
Smart Coaching — LLM converts structured chess data into natural coaching language.

IMPORTANT: The LLM does NOT analyze chess positions. All chess analysis comes
from Stockfish and our detector classes. The LLM's only job is to take those
FACTS and write them as a human coach would say them.

Data flow:
  Stockfish → evals, best moves, cp_loss
  V2 selector → teaching intent, why this move was chosen
  Pattern detectors → hanging pieces, forks, threats
  Position reader → pins, development, center control
  Player profile → weaknesses, rating
  ──────────────────────────────────────────────────
  ALL OF THE ABOVE → LLM → natural coaching sentence
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
    Generate coaching text using LLM as a language layer only.
    All chess facts are computed by our systems and passed to the LLM.
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
    phase = _get_phase(board_after)

    # ─── GATHER ALL FACTS (from our systems, NOT the LLM) ───

    # Fact 1: What the move does mechanically
    move_facts = []
    if board_before.is_castling(move):
        side = "kingside" if chess.square_file(move.to_square) > 4 else "queenside"
        move_facts.append(f"Castled {side}")
    elif captured:
        move_facts.append(f"Captured {chess.piece_name(captured.piece_type)} on {chess.square_name(move.to_square)}")
    if board_after.is_check():
        move_facts.append("Gives check")
    if piece:
        piece_name = chess.piece_name(piece.piece_type)
        from_sq = chess.square_name(move.from_square)
        to_sq = chess.square_name(move.to_square)
        move_facts.append(f"{piece_name} moved from {from_sq} to {to_sq}")

    # Fact 2: V2 teaching intent
    intent_fact = ""
    if v2_context and v2_context.get("v2"):
        intent = v2_context.get("teaching_goal", "")
        why = v2_context.get("why_instructive", "")
        breakdown = v2_context.get("v2_breakdown", {})
        sub = breakdown.get("sub_scores", {})

        if intent == "hanging_piece_punishment":
            if sub.get("capture_punishment", 0) > 0:
                intent_fact = f"Coach captured an undefended piece (punishing a hanging piece)"
            elif sub.get("undefended", 0) > 0:
                intent_fact = f"Coach's move leaves one of the student's pieces undefended"
            elif sub.get("underdefended", 0) > 0:
                intent_fact = f"Coach's move puts pressure on an underdefended student piece"
        elif intent == "fork_opportunity":
            intent_fact = f"Coach's piece now attacks two student pieces at once ({why})"
        elif intent == "threat_awareness":
            if sub.get("attacks_undefended", 0) > 0:
                intent_fact = "Coach now threatens an undefended student piece"
            elif sub.get("checks", 0) > 0:
                intent_fact = "Coach has a check available next move"
            elif sub.get("safe_captures", 0) > 0:
                intent_fact = "Coach has a safe capture available"
            else:
                intent_fact = "Coach created a threat the student must notice"

    # Fact 3: What the student can exploit (from our detectors)
    opportunities = _scan_opportunities(board_after, user_chess_color)

    # Fact 4: Position features from our reader
    feature_facts = []
    if not position_features:
        try:
            pos_data = read_position(board_after.fen(), user_color, user_rating)
            position_features = pos_data.get("features", [])
        except Exception:
            position_features = []
    for f in (position_features or [])[:3]:
        feature_facts.append(f"{f.title}: {f.description}")

    # Fact 5: New threats created by this move
    threat_facts = []
    for sq in chess.SQUARES:
        target = board_after.piece_at(sq)
        if target and target.color == user_chess_color and target.piece_type != chess.KING:
            now_attacked = board_after.is_attacked_by(coach_color, sq)
            was_attacked = board_before.is_attacked_by(coach_color, sq)
            if now_attacked and not was_attacked:
                t_name = chess.piece_name(target.piece_type)
                t_sq = chess.square_name(sq)
                defenders = len(list(board_after.attackers(user_chess_color, sq)))
                threat_facts.append(f"Student's {t_name} on {t_sq} is now attacked (defenders: {defenders})")

    # ─── BUILD PROMPT WITH ONLY VERIFIED FACTS ───

    facts_block = f"""VERIFIED FACTS (from Stockfish and our analysis — these are true):
- Move played: {move_san}
- {'; '.join(move_facts)}
{f'- Teaching intent: {intent_fact}' if intent_fact else ''}
{f'- New threats: {"; ".join(threat_facts)}' if threat_facts else '- No new threats created'}
{f'- Student opportunities: {opportunities}' if opportunities else '- No obvious student opportunities'}
{f'- Position features: {"; ".join(feature_facts)}' if feature_facts else ''}
- Game phase: {phase}
{f'- Opening: {opening_name}' if opening_name else ''}
- Student rating: {user_rating}
{f'- Student weaknesses: {", ".join(player_weaknesses)}' if player_weaknesses else ''}"""

    system_prompt = """You are a chess coach converting analysis data into coaching language.

CRITICAL RULES:
- ONLY use the VERIFIED FACTS provided. Do NOT infer, calculate, or analyze the position yourself.
- You do NOT know chess well enough to analyze positions. The facts are already computed for you.
- Write as if speaking to the student sitting next to you during the game.
- 2-3 sentences max for explanation.
- End with ONE question that makes them look at the board.
- Do NOT reveal the best move or tell them what to play.
- If there's a student opportunity, hint at it without naming the move.

Respond in JSON only (no markdown):
{"explanation": "...", "question": "...", "hint": "..."}"""

    try:
        response = await call_llm(system_prompt, facts_block)

        import json
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()

        data = json.loads(clean)

        result = {
            "move_san": move_san,
            "explanation": data.get("explanation", f"I played {move_san}."),
            "plan": "",
            "threats": [],
            "teaching_point": "",
            "hint_for_user": data.get("question", ""),
        }
        if data.get("hint"):
            result["opponent_opportunity"] = {
                "type": "smart",
                "message": data["hint"],
            }
        return result

    except Exception as e:
        logger.warning(f"[SMART-COACHING] LLM failed, falling back: {e}")
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
    Generate Socratic question for mistakes using LLM as language layer.
    All chess facts come from Stockfish and fundamentals checker.
    """
    if severity in ("good", "brilliant"):
        return None

    from llm_service import call_llm

    move_san = board_before.san(user_move)
    piece = board_before.piece_at(user_move.from_square)
    captured = board_before.piece_at(user_move.to_square)
    board_after = board_before.copy()
    board_after.push(user_move)

    # ─── GATHER FACTS ───

    # What the move did
    move_desc = _describe_move(board_before, user_move, piece, captured)

    # What went wrong (from our fundamentals checker)
    problem_facts = []
    if fundamental_violated == "check_opponents_move":
        problem_facts.append("Student did not respond to the opponent's threat from the previous move")
    elif fundamental_violated == "hanging_pieces":
        # Find which piece is now hanging
        user_color_bool = chess.WHITE if board_before.turn == chess.WHITE else chess.BLACK
        for sq in chess.SQUARES:
            p = board_after.piece_at(sq)
            if p and p.color == user_color_bool and p.piece_type != chess.KING and p.piece_type != chess.PAWN:
                attackers = list(board_after.attackers(not user_color_bool, sq))
                defenders = list(board_after.attackers(user_color_bool, sq))
                if attackers and not defenders:
                    problem_facts.append(f"Student's {chess.piece_name(p.piece_type)} on {chess.square_name(sq)} is now undefended and attacked")
                    break
        if not problem_facts:
            problem_facts.append("Student left a piece undefended")
    elif fundamental_violated == "calculate":
        problem_facts.append(f"Student didn't calculate the response — lost {cp_loss} centipawns")
    elif fundamental_violated == "king_safety":
        problem_facts.append("Student's king is in danger")
    elif fundamental_violated == "development":
        problem_facts.append("Student moved an already-developed piece instead of developing a new one")
    elif fundamental_violated == "center_control":
        problem_facts.append("Student lost control of the center")
    elif fundamental_violated == "have_a_plan":
        problem_facts.append("Student's move doesn't serve a clear purpose")

    if coach_intent:
        intent_map = {
            "hanging_piece_punishment": "The coach deliberately created a position to test piece safety awareness",
            "fork_opportunity": "The coach set up a double attack that the student needed to handle",
            "threat_awareness": "The coach created a threat the student needed to notice",
        }
        if coach_intent in intent_map:
            problem_facts.append(intent_map[coach_intent])

    facts_block = f"""VERIFIED FACTS:
- Student played: {move_san} ({move_desc})
- This was a {severity} (lost {cp_loss} centipawns)
- Best move was: {best_move_san or 'unknown'}
- What went wrong: {'; '.join(problem_facts) if problem_facts else 'unclear'}
- Game phase: {phase}
- Student rating: {user_rating}"""

    system_prompt = """You convert chess analysis into ONE Socratic question for a student.

RULES:
- ONLY use the VERIFIED FACTS. Do NOT analyze the position yourself.
- Ask about what they MISSED — do NOT tell them the answer.
- Reference specific pieces and squares from the facts.
- ONE question, under 20 words.
- ONE hint sentence if they can't answer.

Respond in JSON only: {"question": "...", "hint": "..."}"""

    try:
        response = await call_llm(system_prompt, facts_block)
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
