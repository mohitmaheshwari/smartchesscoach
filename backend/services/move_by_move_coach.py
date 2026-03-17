"""
Move-By-Move Opening Coach

Generates rich, contextual coaching commentary for every move
during the opening phase of a teaching game. Unlike the trigger-based
system (which only speaks on mistakes), this speaks on EVERY move
to guide the player through the opening like a real coach.

The coach:
- Explains the idea behind each move
- Warns about upcoming traps BEFORE they happen
- Celebrates when user plays the right move
- Gently corrects deviations from the main line
- Asks rating-appropriate questions to build thinking habits
- Teaches patterns (forks, pins, etc.) when they arise in the position
"""

import chess
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MoveCommentary:
    """Commentary object for a single move."""
    message: str                      # Main coaching text
    question: Optional[str] = None    # Optional question for the user
    trap_warning: Optional[str] = None # Upcoming trap warning
    pattern_note: Optional[str] = None # Fork/pin/pattern teaching
    move_quality: str = "neutral"      # good, great, inaccuracy, mistake, neutral
    next_hint: Optional[str] = None    # Hint about what to play next
    teaching_type: str = "opening"     # opening, tactic, pattern, encouragement


def get_rating_tone(rating: int) -> Dict:
    """Get language style based on player's rating."""
    if rating < 800:
        return {
            "level": "beginner",
            "address": "casual",
            "explain_depth": "basic",
            "use_names": False,  # Don't use move names, describe actions
            "ask_frequency": 0.3,  # Ask questions 30% of the time
        }
    elif rating < 1200:
        return {
            "level": "novice", 
            "address": "friendly",
            "explain_depth": "simple",
            "use_names": True,
            "ask_frequency": 0.4,
        }
    elif rating < 1600:
        return {
            "level": "intermediate",
            "address": "coaching",
            "explain_depth": "detailed",
            "use_names": True,
            "ask_frequency": 0.5,
        }
    else:
        return {
            "level": "advanced",
            "address": "peer",
            "explain_depth": "strategic",
            "use_names": True,
            "ask_frequency": 0.6,
        }


# ============================================================
# POSITION PATTERN DETECTION
# ============================================================

def detect_patterns(board: chess.Board, user_color: str) -> List[Dict]:
    """Detect tactical and positional patterns in the current position."""
    patterns = []
    is_white = user_color == "white"
    move_num = board.fullmove_number
    
    # Skip detailed pattern detection in the first 5 moves (opening is about principles)
    if move_num <= 5:
        return patterns
    
    # Check for pieces under attack (not pawns in the opening)
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece:
            continue
        
        # Skip pawns in early game (too noisy)
        if piece.piece_type == chess.PAWN and move_num <= 10:
            continue
        
        is_user_piece = (piece.color == chess.WHITE) == is_white
        attackers = board.attackers(not piece.color, square)
        defenders = board.attackers(piece.color, square)
        
        if attackers and not defenders and piece.piece_type not in (chess.KING, chess.PAWN):
            piece_name = chess.piece_name(piece.piece_type)
            sq_name = chess.square_name(square)
            if is_user_piece:
                patterns.append({
                    "type": "hanging_piece",
                    "side": "user",
                    "message": f"Your {piece_name} on {sq_name} is undefended!",
                    "severity": "warning"
                })
            else:
                patterns.append({
                    "type": "hanging_piece",
                    "side": "opponent",
                    "message": f"The opponent's {piece_name} on {sq_name} is undefended.",
                    "severity": "opportunity"
                })
    
    # Check for checks
    if board.is_check():
        patterns.append({
            "type": "check",
            "message": "Check! The king must respond.",
            "severity": "critical"
        })
    
    # Check for pins (simplified)
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece:
            continue
        if piece.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
            is_user_piece = (piece.color == chess.WHITE) == is_white
            # Check if this piece is pinning something
            if board.is_pinned(not piece.color, square):
                sq_name = chess.square_name(square)
                patterns.append({
                    "type": "pin",
                    "message": f"There's a pin on {sq_name}!",
                    "severity": "tactical"
                })
    
    # Check for center control
    center_squares = [chess.E4, chess.D4, chess.E5, chess.D5]
    user_center = 0
    opp_center = 0
    for sq in center_squares:
        piece = board.piece_at(sq)
        if piece:
            if (piece.color == chess.WHITE) == is_white:
                user_center += 1
            else:
                opp_center += 1
    
    if user_center >= 2 and opp_center == 0:
        patterns.append({
            "type": "center_control",
            "message": "You have strong control of the center!",
            "severity": "positive"
        })
    
    return patterns


# ============================================================
# TRAP KNOWLEDGE
# ============================================================

OPENING_TRAPS = {
    "queens_gambit": [
        {
            "after_moves": ["d4", "d5", "c4", "dxc4"],
            "name": "Queen's Gambit Accepted",
            "warning": "They took the pawn! Don't worry — you'll get it back. Play e3 or e4 to open the center and the c4 pawn falls naturally.",
            "question": "Can you see how to get the pawn back?",
            "key_move": "e3",
        },
        {
            "after_moves": ["d4", "d5", "c4", "e5"],
            "name": "Albin Counter-Gambit",
            "warning": "This is the Albin Counter-Gambit. Black sacrifices a pawn for active piece play. Be careful — there's a sneaky trap if you take on e5!",
            "question": "Should you take on e5? Think about what Black might do next.",
            "key_move": "dxe5",
        },
        {
            "after_moves": ["d4", "d5", "c4", "c6"],
            "name": "Slav Defense",
            "warning": "This is the Slav Defense — very solid. Black defends d5 with a pawn instead of a piece. A smart choice!",
            "question": None,
            "key_move": None,
        },
    ],
    "italian_game": [
        {
            "after_moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"],
            "name": "Two Knights Defense",
            "warning": "They're inviting the Fried Liver Attack! If you play Ng5, you're attacking f7. But careful — they can play d5 and fight back.",
            "question": "What square is the weakest in Black's position?",
            "key_move": "Ng5",
        },
    ],
    "london_system": [
        {
            "after_moves": ["d4", "d5", "Bf4", "c5"],
            "name": "c5 challenge",
            "warning": "They're challenging your center! If you play e3, your bishop on f4 gets locked in. Consider c3 to support d4 first.",
            "question": "How can you keep your dark-squared bishop active?",
            "key_move": "e3",
        },
    ],
}


# ============================================================
# MAIN COMMENTARY GENERATOR
# ============================================================

def generate_move_commentary(
    fen_before: str,
    fen_after: str,
    move_san: str,
    move_by: str,  # "user" or "coach"
    all_moves: List[str],
    user_color: str,
    user_rating: int,
    opening_plan: Optional[Dict] = None,
    eval_before: float = 0,
    eval_after: float = 0,
    is_best_move: bool = True,
    best_move_san: str = "",
) -> MoveCommentary:
    """
    Generate rich coaching commentary for a move during the opening phase.
    
    This is called for EVERY move — both user's and coach's.
    """
    tone = get_rating_tone(user_rating)
    board_after = chess.Board(fen_after)
    move_number = (len(all_moves) + 1) // 2  # Full move number
    
    # Detect patterns in the position after the move
    patterns = detect_patterns(board_after, user_color)
    
    # Check for known traps (both static and variation-based)
    trap_warning = check_for_traps(all_moves, opening_plan, board_after)
    
    # Check if we're in a deep variation
    variation_teaching = get_variation_teaching(all_moves, opening_plan)
    
    # Get pattern note if any
    pattern_note = None
    for p in patterns:
        if p["severity"] in ("warning", "opportunity", "tactical"):
            pattern_note = p["message"]
            break
    
    if move_by == "coach":
        return _generate_coach_move_commentary(
            move_san, all_moves, opening_plan, tone, 
            board_after, user_color, move_number, 
            trap_warning, pattern_note, patterns, variation_teaching
        )
    else:
        return _generate_user_move_commentary(
            move_san, all_moves, opening_plan, tone,
            board_after, user_color, move_number,
            trap_warning, pattern_note, patterns,
            eval_before, eval_after, is_best_move, best_move_san,
            variation_teaching
        )


def _generate_coach_move_commentary(
    move_san, all_moves, opening_plan, tone,
    board, user_color, move_number,
    trap_warning, pattern_note, patterns, variation_teaching=None
) -> MoveCommentary:
    """Generate commentary after the coach (opponent) makes a move."""
    
    opening_name = opening_plan.get("name", "this opening") if opening_plan else "the opening"
    teaching_moments = opening_plan.get("teaching_moments", {}) if opening_plan else {}
    
    # Check if there's variation-specific teaching for this move
    specific_teaching = teaching_moments.get(move_san)
    
    # PRIORITY: Use variation teaching if available (deep line)
    if variation_teaching and variation_teaching.get("teaching"):
        vt = variation_teaching
        var_name = vt.get("variation_name", "")
        parts = [vt["teaching"]]
        question = None
        
        if vt.get("trap"):
            parts.append(f"Watch out: {vt['trap']}")
        
        if vt.get("idea"):
            question = f"Can you see the idea? Think about: {vt['idea']}"
        
        # Show progress in the variation
        mi = vt.get("move_index", 0)
        total = vt.get("total_moves", 0)
        if total > 0 and mi < total:
            progress = f"({var_name} — move {mi + len(variation_teaching.get('full_line', [])[:4])} of the main line)"
            parts.append(progress)
        
        return MoveCommentary(
            message=" ".join(parts),
            question=question,
            trap_warning=vt.get("trap"),
            move_quality="neutral",
            teaching_type="opening_variation"
        )
    
    # Build the message
    parts = []
    question = None
    
    if specific_teaching:
        parts.append(specific_teaching)
    else:
        # Generate contextual commentary based on what the opponent did
        if board.is_check():
            parts.append(f"I played {move_san} — check! You need to deal with this first.")
            question = "How will you get out of check?"
        elif _is_capture(move_san):
            parts.append(f"I played {move_san}, taking a piece.")
            question = "What's the best way to respond to this capture?"
        elif _is_development_move(move_san, board):
            parts.append(f"I played {move_san}, developing a piece.")
            if tone["level"] == "beginner":
                question = "Now it's your turn to develop. Which piece would you bring out?"
            else:
                question = "What's your plan here?"
        elif _is_pawn_push(move_san):
            parts.append(f"I played {move_san}, fighting for space in the center.")
            if move_number <= 5:
                question = "How do you want to respond in the center?"
        else:
            parts.append(f"I played {move_san}.")
            question = "What do you think this move is trying to do?"
    
    # Add trap warning if this move enters a trap sequence
    if trap_warning:
        parts.append(trap_warning["warning"])
        if trap_warning.get("question"):
            question = trap_warning["question"]
    
    # Add pattern note
    if pattern_note:
        parts.append(pattern_note)
    
    # For beginners, give a hint about what to do next
    next_hint = None
    if tone["level"] in ("beginner", "novice") and opening_plan:
        # Find the next expected move in the opening line
        identifying_moves = opening_plan.get("identifying_moves", [])
        current_move_count = len(all_moves)
        if current_move_count < len(identifying_moves):
            next_expected = identifying_moves[current_move_count]
            if tone["level"] == "beginner":
                next_hint = f"The next idea in {opening_name} is {next_expected}."
            else:
                next_hint = "Think about what the main line suggests here."
    
    message = " ".join(parts)
    
    return MoveCommentary(
        message=message,
        question=question,
        trap_warning=trap_warning["warning"] if trap_warning else None,
        pattern_note=pattern_note,
        move_quality="neutral",
        next_hint=next_hint,
        teaching_type="opening"
    )


def _generate_user_move_commentary(
    move_san, all_moves, opening_plan, tone,
    board, user_color, move_number,
    trap_warning, pattern_note, patterns,
    eval_before, eval_after, is_best_move, best_move_san,
    variation_teaching=None
) -> MoveCommentary:
    """Generate commentary after the user makes a move."""
    
    teaching_moments = opening_plan.get("teaching_moments", {}) if opening_plan else {}
    identifying_moves = opening_plan.get("identifying_moves", []) if opening_plan else []
    main_ideas = opening_plan.get("main_ideas", []) if opening_plan else []
    typical_mistakes = opening_plan.get("typical_mistakes", []) if opening_plan else []
    
    # Check if this is the expected opening move
    is_main_line = _is_on_main_line(move_san, all_moves, identifying_moves, user_color)
    
    # PRIORITY: Use variation teaching if available (deep line)
    if variation_teaching and variation_teaching.get("teaching"):
        vt = variation_teaching
        expected = vt.get("expected_move", "")
        played_expected = move_san.replace("+", "").replace("#", "").lower() == expected.replace("+", "").replace("#", "").lower() if expected else False
        
        parts = []
        question = None
        quality = "great" if played_expected else "good"
        
        if played_expected:
            parts.append(f"Excellent! {move_san}!")
            parts.append(vt["teaching"])
        else:
            # They played something else — still teach the expected move
            parts.append(f"You played {move_san}.")
            if expected:
                parts.append(f"The main line here is {expected}.")
            parts.append(vt["teaching"])
            quality = "inaccuracy"
        
        if vt.get("idea"):
            if played_expected:
                parts.append(f"Key concept: {vt['idea']}")
            else:
                question = f"The key idea here is: {vt['idea']}. Can you see why?"
        
        if vt.get("trap"):
            parts.append(f"Trap alert: {vt['trap']}")
        
        # Share variation plans at key moments
        plans = vt.get("key_plans", [])
        if plans and vt.get("move_index", 0) in (4, 8, 12):
            parts.append(f"Your plan from here: {plans[0]}")
        
        return MoveCommentary(
            message=" ".join(parts),
            question=question,
            trap_warning=vt.get("trap"),
            move_quality=quality,
            teaching_type="opening_variation"
        )
    
    # Evaluate move quality
    cp_loss = 0
    if user_color == "white":
        cp_loss = (eval_before - eval_after) * 100
    else:
        cp_loss = (eval_after - eval_before) * 100
    
    if is_best_move or cp_loss < 10:
        quality = "great"
    elif cp_loss < 50:
        quality = "good"
    elif cp_loss < 100:
        quality = "inaccuracy"
    elif cp_loss < 200:
        quality = "mistake"
    else:
        quality = "blunder"
    
    parts = []
    question = None
    
    # Check for specific teaching moment
    specific_teaching = teaching_moments.get(move_san)
    
    if quality in ("great", "good"):
        # Celebrate and teach
        if specific_teaching:
            if quality == "great":
                parts.append(f"Excellent! {move_san}!")
            else:
                parts.append(f"Good move — {move_san}.")
            parts.append(specific_teaching)
        elif is_main_line:
            if quality == "great":
                parts.append(f"Perfect! {move_san} is exactly right.")
            else:
                parts.append(f"Nice — {move_san}.")
            
            # Teach the idea behind the move
            idea = _explain_move_idea(move_san, board, user_color, tone)
            if idea:
                parts.append(idea)
            
            # Share a main idea if early in the opening
            if move_number <= 4 and main_ideas:
                idea_idx = min(move_number - 1, len(main_ideas) - 1)
                parts.append(f"Key idea: {main_ideas[idea_idx]}")
        else:
            parts.append(f"Okay, {move_san}.")
            idea = _explain_move_idea(move_san, board, user_color, tone)
            if idea:
                parts.append(idea)
        
        # Ask a question sometimes to reinforce learning
        if tone["ask_frequency"] > 0.3 and move_number <= 8:
            question = _generate_learning_question(move_san, board, user_color, tone, opening_plan)
    
    elif quality == "inaccuracy":
        # Gentle correction
        parts.append(f"Okay, {move_san} is playable.")
        if best_move_san:
            if tone["level"] in ("beginner", "novice"):
                parts.append(f"But {best_move_san} would have been a bit stronger here.")
            else:
                parts.append(f"Consider {best_move_san} next time — it's more precise.")
            
            idea = _explain_move_idea(best_move_san, board, user_color, tone)
            if idea:
                parts.append(f"The idea is: {idea}")
        
        question = "Can you see why that move would be better?"
    
    elif quality in ("mistake", "blunder"):
        # Teaching moment — don't make them feel bad
        if quality == "blunder":
            parts.append(f"Hmm, {move_san} gives away some advantage.")
        else:
            parts.append(f"{move_san} isn't the best here.")
        
        if best_move_san:
            parts.append(f"Try to think about {best_move_san} in this type of position.")
            idea = _explain_move_idea(best_move_san, board, user_color, tone)
            if idea:
                parts.append(idea)
        
        # Check if this matches a typical mistake
        for mistake in typical_mistakes:
            if move_san.lower() in mistake.lower():
                parts.append(f"Common pitfall: {mistake}")
                break
        
        question = "What do you think went wrong with that move?"
    
    # Add trap warning
    if trap_warning:
        parts.append(trap_warning["warning"])
        if trap_warning.get("question"):
            question = trap_warning["question"]
    
    # Add pattern note for opportunities
    for p in patterns:
        if p["severity"] == "opportunity" and p["side"] == "opponent":
            parts.append(f"By the way — {p['message']} Can you take advantage?")
            break
    
    message = " ".join(parts)
    
    return MoveCommentary(
        message=message,
        question=question,
        trap_warning=trap_warning["warning"] if trap_warning else None,
        pattern_note=pattern_note,
        move_quality=quality,
        next_hint=None,
        teaching_type="opening"
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def check_for_traps(
    all_moves: List[str],
    opening_plan: Optional[Dict],
    board_after: Optional[chess.Board] = None,
) -> Optional[Dict]:
    """Check if the current move sequence enters a known trap."""
    if not opening_plan:
        return None

    clean_moves = [_normalize_move_san(move) for move in all_moves if move]
    trap_lookup_keys = []
    for key in (opening_plan.get("key"), opening_plan.get("family_key")):
        if key and key not in trap_lookup_keys:
            trap_lookup_keys.append(key)

    for opening_key in trap_lookup_keys:
        traps = OPENING_TRAPS.get(opening_key, [])
        for trap in traps:
            trap_moves = [_normalize_move_san(move) for move in trap.get("after_moves", [])]
            if trap_moves and clean_moves == trap_moves:
                return trap

    best_match, trigger_len = _find_best_variation_match(clean_moves, opening_plan.get("variations", {}))
    if best_match:
        move_idx = len(clean_moves) - trigger_len
        for trap in best_match.get("traps", []):
            if trap.get("after_move") is not None and move_idx >= trap.get("after_move"):
                return {
                    "warning": trap["warning"],
                    "name": trap.get("name", best_match.get("name", "")),
                    "question": trap.get("question"),
                }
            trap_move = trap.get("move")
            if trap_move and board_after is not None:
                try:
                    board_after.parse_san(trap_move)
                except ValueError:
                    continue
                return {
                    "warning": trap["warning"],
                    "name": trap.get("name", best_match.get("name", "")),
                    "question": trap.get("question"),
                }

    return None


def get_variation_teaching(all_moves: List[str], opening_plan: Optional[Dict]) -> Optional[Dict]:
    """
    Find the active variation and return teaching for the current move.
    
    Looks up teaching by MOVE NAME (not position index) so it works
    even when the opponent deviates from the main line.
    """
    if not opening_plan:
        return None
    
    variations = opening_plan.get("variations", {})
    if not variations:
        return None
    
    clean_moves = [_normalize_move_san(move) for move in all_moves if move]
    if not clean_moves:
        return None

    current_move = clean_moves[-1]
    best_match, trigger_len = _find_best_variation_match(clean_moves, variations)
    if not best_match:
        return None

    move_teaching = best_match.get("move_teaching", {})
    full_line_raw = best_match.get("full_line", [])
    full_line = [_normalize_move_san(move) for move in full_line_raw]
    moves_into_variation = len(clean_moves) - trigger_len
    current_ply_index = len(clean_moves) - 1

    expected_move = None
    expected_move_normalized = None
    if current_ply_index < len(full_line):
        expected_move = full_line_raw[current_ply_index]
        expected_move_normalized = full_line[current_ply_index]

    teaching = _get_teaching_for_move(move_teaching, current_move)
    if not teaching and expected_move:
        teaching = _get_teaching_for_move(move_teaching, expected_move)

    next_expected_move = None
    if len(clean_moves) < len(full_line_raw):
        next_expected_move = full_line_raw[len(clean_moves)]

    if teaching:
        return {
            "variation_name": best_match.get("name", ""),
            "teaching": teaching.get("teach", ""),
            "expected_move": expected_move or current_move,
            "played_move": all_moves[-1],
            "matched_expected": current_move == (expected_move_normalized or current_move),
            "idea": teaching.get("idea", ""),
            "trap": teaching.get("trap"),
            "key_plans": best_match.get("key_plans", []),
            "full_line": best_match.get("full_line", []),
            "move_index": moves_into_variation,
            "total_moves": len(best_match.get("full_line", [])),
            "next_expected_move": next_expected_move,
        }

    # Even if no specific teaching for this move, return variation context
    # so the coach knows we're in a variation and can teach contextually
    return {
        "variation_name": best_match.get("name", ""),
        "teaching": None,
        "key_plans": best_match.get("key_plans", []),
        "full_line": best_match.get("full_line", []),
        "move_index": moves_into_variation,
        "total_moves": len(best_match.get("full_line", [])),
        "expected_move": expected_move,
        "played_move": all_moves[-1],
        "matched_expected": current_move == expected_move_normalized if expected_move_normalized else True,
        "next_expected_move": next_expected_move,
    }


def _normalize_move_san(move: str) -> str:
    return (
        (move or "")
        .replace("+", "")
        .replace("#", "")
        .replace("!", "")
        .replace("?", "")
        .strip()
        .lower()
    )


def _get_teaching_for_move(move_teaching: Dict[str, Dict], move: Optional[str]) -> Optional[Dict]:
    if not move:
        return None

    normalized_move = _normalize_move_san(move)
    for key, value in move_teaching.items():
        if _normalize_move_san(key) == normalized_move:
            return value
    return None


def _find_best_variation_match(clean_moves: List[str], variations: Dict[str, Dict]) -> Tuple[Optional[Dict], int]:
    best_match = None
    best_depth = 0

    for var_data in variations.values():
        trigger = [_normalize_move_san(move) for move in var_data.get("trigger_moves", [])]
        if len(clean_moves) < len(trigger):
            continue

        if clean_moves[: len(trigger)] == trigger and len(trigger) > best_depth:
            best_match = var_data
            best_depth = len(trigger)

    return best_match, best_depth


def _is_on_main_line(move_san: str, all_moves: List[str], identifying_moves: List[str], user_color: str) -> bool:
    """Check if the user's move follows the expected opening line."""
    if not identifying_moves:
        return False
    
    move_idx = len(all_moves) - 1  # Index of this move in the sequence
    if move_idx < len(identifying_moves):
        expected = identifying_moves[move_idx]
        return move_san.replace("+", "").replace("#", "").lower() == expected.replace("+", "").replace("#", "").lower()
    return False


def _is_capture(move_san: str) -> bool:
    return "x" in move_san


def _is_pawn_push(move_san: str) -> bool:
    return len(move_san) >= 2 and move_san[0].islower() and "x" not in move_san


def _is_development_move(move_san: str, board: chess.Board) -> bool:
    """Check if this is a piece development move (not pawn, not king)."""
    if not move_san:
        return False
    first = move_san[0]
    return first in "NBRQ"


def _explain_move_idea(move_san: str, board: chess.Board, user_color: str, tone: Dict) -> Optional[str]:
    """Generate a plain-English explanation of why a move is good."""
    if not move_san:
        return None
    
    # Simple heuristic explanations
    first = move_san[0] if move_san else ""
    
    if move_san in ("O-O", "O-O-O"):
        if tone["level"] == "beginner":
            return "Castling keeps your king safe and activates the rook."
        return "Good — the king is safer now."
    
    if first == "N":
        target = move_san[-2:].replace("+", "").replace("#", "")
        if target in ("f3", "c3", "f6", "c6"):
            return "Knights love central squares — they control more from here."
        if target in ("e5", "d5", "e4", "d4"):
            return "A strong outpost in the center!"
    
    if first == "B":
        return "Active development — the bishop is now in the game."
    
    if _is_pawn_push(move_san):
        target = move_san[:2]
        if target in ("e4", "d4", "e5", "d5"):
            if tone["level"] == "beginner":
                return "Fighting for the center! Pawns in the middle control key squares."
            return "Contesting the center."
        if target in ("c4", "c5"):
            return "This puts pressure on the center."
    
    if "x" in move_san:
        return "Capturing — make sure this trade is in your favor."
    
    return None


def _generate_learning_question(
    move_san: str, board: chess.Board, user_color: str, 
    tone: Dict, opening_plan: Optional[Dict]
) -> Optional[str]:
    """Generate a rating-appropriate question to build thinking habits."""
    
    move_count = board.fullmove_number
    
    if tone["level"] == "beginner":
        questions = [
            "How many pieces have you developed so far?",
            "Is your king safe? Have you thought about castling?",
            "Which of your pieces is still on its starting square?",
            "Can you see any undefended pieces on the board?",
        ]
    elif tone["level"] == "novice":
        questions = [
            "What's your plan for the next 2-3 moves?",
            "Which piece is your least active right now?",
            "Are there any tactical ideas you can spot?",
            "What do you think your opponent will play?",
        ]
    elif tone["level"] == "intermediate":
        questions = [
            "What's the strategic idea in this position?",
            "Can you see any weaknesses in your opponent's setup?",
            "What pawn breaks are available?",
            "Where should your pieces be aiming?",
        ]
    else:
        questions = [
            "What's the critical difference between the two sides?",
            "Where should the play be focused?",
            "Can you evaluate this position?",
        ]
    
    # Pick based on move number to avoid repeats
    idx = (move_count - 1) % len(questions)
    return questions[idx]
