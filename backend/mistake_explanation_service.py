"""
Mistake Explanation Service - Educational Commentary for Chess Mistakes

Architecture:
- Our Chess Logic (Tags/Rules) → determines WHY the move is bad
- GPT → only writes the human-readable commentary based on those tags

This is a HYBRID approach:
1. Deterministic Analysis: We use mistake_classifier.py to identify WHAT happened
2. LLM Commentary: GPT takes these facts and writes an educational explanation

GPT DOES NOT:
- Decide if a move is a blunder/mistake/inaccuracy (Stockfish does)
- Identify tactical patterns (mistake_classifier does)
- Invent chess variations (we provide the engine lines)

GPT ONLY:
- Transforms structured tags into readable English
- Provides educational context ("in positions like this...")
- Suggests thinking habits to avoid the mistake
"""

import logging
from typing import Dict, Optional
import chess

from mistake_classifier import (
    MistakeType, GamePhase,
    find_hanging_pieces, find_forks, find_pins, find_skewers,
    find_discovered_attacks, find_overloaded_defenders,
    detect_walked_into_fork, detect_walked_into_pin,
    detect_missed_fork, detect_missed_pin,
    determine_phase, get_material_count
)

logger = logging.getLogger(__name__)


# ============================================
# EXPLANATION TEMPLATES - What each mistake type means
# ============================================

MISTAKE_TEMPLATES = {
    # ==================== CRITICAL: CHECKMATE THREATS ====================
    # These take HIGHEST priority - nothing else matters if you get mated
    "allowed_mate_in_1": {
        "short": "Allowed mate in 1!",
        "pattern": "This move allowed checkmate on the very next move. The most critical mistake.",
        "thinking_habit": "ALWAYS check: Does my move allow any checks? Can those checks lead to mate?",
        "severity": "decisive"
    },
    "allowed_mate_in_2": {
        "short": "Allowed forced mate",
        "pattern": "This move allowed a forced checkmate sequence. A decisive oversight.",
        "thinking_habit": "Before your move, look at ALL their checks. Follow each one to the end.",
        "severity": "decisive"
    },
    "missed_mate_in_1": {
        "short": "Missed checkmate!",
        "pattern": "You had checkmate in one move! These are the most important to spot.",
        "thinking_habit": "Every move, quickly scan: Do I have any checks? Can any check be mate?",
        "severity": "decisive"
    },
    "missed_mate_in_2": {
        "short": "Missed forced mate",
        "pattern": "A forced checkmate was available. Worth training your eye for these.",
        "thinking_habit": "When you have active pieces near their king, ALWAYS check for mate patterns.",
        "severity": "decisive"
    },
    
    # Tactical pattern mistakes - Coach-style feedback
    "hanging_piece": {
        "short": "Piece left unprotected",
        "pattern": "That piece was left without backup. It happens to everyone!",
        "thinking_habit": "Quick tip: Before each move, do a 'safety scan' - which of your pieces are unguarded?",
        "severity": "material_loss"
    },
    "material_blunder": {
        "short": "Material slipped away",
        "pattern": "This one gave away some material. It's a great learning moment.",
        "thinking_habit": "Try this: After deciding your move, pause and ask 'What can they take next?'",
        "severity": "material_loss"
    },
    "walked_into_fork": {
        "short": "Double attack incoming",
        "pattern": "Two of your pieces ended up vulnerable to the same attack. Classic trap!",
        "thinking_habit": "Knight squares are sneaky - always check if they can hit two targets at once.",
        "severity": "tactical"
    },
    "walked_into_pin": {
        "short": "Created a pin situation",
        "pattern": "Your pieces lined up in a way that created a pin. Happens to the best of us!",
        "thinking_habit": "Watch out for pieces lining up on same files, ranks, or diagonals.",
        "severity": "tactical"
    },
    "walked_into_skewer": {
        "short": "Skewer opportunity given",
        "pattern": "A valuable piece ended up in front of another on the same line.",
        "thinking_habit": "Keep your heavy pieces (Queen, Rooks) spread out to avoid skewers.",
        "severity": "tactical"
    },
    "walked_into_discovered_attack": {
        "short": "Discovered attack set up",
        "pattern": "The opponent got to 'unmask' a hidden attacker. Tricky pattern!",
        "thinking_habit": "Look for enemy pieces that could reveal another attacker when they move.",
        "severity": "tactical"
    },
    "missed_fork": {
        "short": "Fork opportunity spotted!",
        "pattern": "There was a chance to attack two pieces at once. Good ones to look for!",
        "thinking_habit": "Quick check: Can any of my knights or pawns hit two targets?",
        "severity": "missed_tactic"
    },
    "missed_pin": {
        "short": "Pin was available",
        "pattern": "You could have frozen an opponent's piece by pinning it. Next time!",
        "thinking_habit": "Scan for pieces that are lined up with their King or Queen behind them.",
        "severity": "missed_tactic"
    },
    "missed_skewer": {
        "short": "Skewer opportunity",
        "pattern": "A skewer was on the board - these are satisfying to find!",
        "thinking_habit": "When heavy pieces line up, check if you can attack through them.",
        "severity": "missed_tactic"
    },
    "missed_discovered_attack": {
        "short": "Hidden attack available",
        "pattern": "One of your pieces could have 'revealed' another attacker. Sneaky tactic!",
        "thinking_habit": "Check if moving a piece can unmask an attack from behind.",
        "severity": "missed_tactic"
    },
    "missed_piece_trap": {
        "short": "Trapping opportunity missed!",
        "pattern": "You could have trapped an enemy piece - limiting where it can go safely.",
        "thinking_habit": "Look for enemy pieces with limited escape squares. Can you cut off more exits?",
        "severity": "missed_tactic"
    },
    "missed_mobility_restriction": {
        "short": "Could have restricted enemy piece",
        "pattern": "There was a way to significantly limit an opponent's piece activity.",
        "thinking_habit": "Ask: How many squares can their active pieces reach? Can I reduce that?",
        "severity": "missed_tactic"
    },
    "missed_multi_threat": {
        "short": "Multiple threats were possible!",
        "pattern": "A move creating several threats at once was available - very powerful!",
        "thinking_habit": "Best moves often do TWO things at once. Look for double-duty moves.",
        "severity": "missed_tactic"
    },
    "missed_attack_valuable": {
        "short": "Attack on high-value piece missed",
        "pattern": "You could have directly threatened a valuable enemy piece.",
        "thinking_habit": "Where are their queen and rooks? Can I attack them with a lesser piece?",
        "severity": "missed_tactic"
    },
    "missed_winning_tactic": {
        "short": "Winning shot was there!",
        "pattern": "A decisive tactical blow was available. These are what we practice for!",
        "thinking_habit": "Remember the order: Checks, Captures, Threats. Scan each move.",
        "severity": "missed_tactic"
    },
    "ignored_threat": {
        "short": "Opponent's plan overlooked",
        "pattern": "The opponent had something brewing that needed attention.",
        "thinking_habit": "Golden question: What's their best move? Always ask it.",
        "severity": "threat_blindness"
    },
    
    # Positional/conversion mistakes
    "blunder_when_ahead": {
        "short": "Victory slipped away",
        "pattern": "You were in control but relaxed a bit too much. Happens to grandmasters too!",
        "thinking_habit": "When winning, pretend it's still equal. Stay sharp until the end.",
        "severity": "conversion"
    },
    "failed_conversion": {
        "short": "Advantage needed one more push",
        "pattern": "You had them on the ropes but the finish was tricky.",
        "thinking_habit": "In winning positions, simplify! Trade pieces and keep it clean.",
        "severity": "conversion"
    },
    
    # Phase-specific mistakes
    "opening_inaccuracy": {
        "short": "Opening wobble",
        "pattern": "This strayed a bit from solid opening ideas. Easy to fix!",
        "thinking_habit": "Opening checklist: Develop, control center, castle, connect rooks.",
        "severity": "positional"
    },
    "positional_drift": {
        "short": "Position slowly slipped",
        "pattern": "Small choices added up and the position got trickier. Subtle but important!",
        "thinking_habit": "Every 3-4 moves, pause and ask: What's my plan from here?",
        "severity": "positional"
    },
    "king_safety_error": {
        "short": "King needed more protection",
        "pattern": "The king got a bit exposed. Safety first!",
        "thinking_habit": "Castle early, keep pawns in front of your king, watch for back-rank issues.",
        "severity": "positional"
    },
    
    # Time-related
    "time_pressure_blunder": {
        "short": "Time pressure blunder",
        "pattern": "Under time pressure, you made a mistake.",
        "thinking_habit": "Budget time better in complex positions.",
        "severity": "time_management"
    },
    
    # Default/generic
    "inaccuracy": {
        "short": "Inaccuracy",
        "pattern": "A slightly imprecise move.",
        "thinking_habit": "Look for the most purposeful move each turn.",
        "severity": "minor"
    },
    "good_move": {
        "short": "Good move",
        "pattern": "Solid choice.",
        "thinking_habit": None,
        "severity": "none"
    },
}


def detect_walked_into_skewer(board_before: chess.Board, board_after: chess.Board, user_color: bool) -> Optional[Dict]:
    """
    Detect if the user's move created a skewer opportunity for opponent.
    A skewer is when a high-value piece is attacked and must move, exposing a lower-value piece behind it.
    Classic example: Queen moves in front of King/Rook on same file/diagonal.
    """
    opponent = not user_color
    
    # Check for skewers that exist AFTER the move that didn't exist BEFORE
    skewers_after = find_skewers(board_after, opponent)
    skewers_before = find_skewers(board_before, opponent)
    
    # Get squares that were skewered before
    skewered_before = set()
    for s in skewers_before:
        skewered_before.add(s.get("front_square"))
    
    # Find NEW skewers created by the user's move
    for skewer in skewers_after:
        front_sq = skewer.get("front_square")
        if front_sq not in skewered_before:
            # This is a NEW skewer the user walked into
            return {
                "front_piece": skewer.get("front_piece"),
                "front_square": front_sq,
                "back_piece": skewer.get("back_piece"),
                "back_square": skewer.get("back_square"),
                "attacker": skewer.get("attacker_piece"),
                "attacker_square": skewer.get("attacker_square")
            }
    
    return None


def analyze_mistake_position(fen_before: str, move_played: str, best_move: str, 
                              cp_loss: int, user_color: str) -> Dict:
    """
    Analyze a mistake position to determine what went wrong.
    
    IMPORTANT: This function should ONLY be called when Stockfish has determined
    the move is a mistake (cp_loss >= 50). Stockfish is the source of truth for
    whether a move is good or bad. This function only explains WHY it's bad.
    
    Example: Queen moves in front of rook
    - If cp_loss is LOW → Stockfish says it's GOOD (maybe a brilliant sacrifice) → DON'T call this
    - If cp_loss is HIGH → Stockfish says it's BAD (blunder) → Call this to explain why
    
    Returns structured tags that can be turned into an explanation.
    This is 100% DETERMINISTIC - no LLM involved.
    
    Args:
        fen_before: FEN position before the mistake
        move_played: The move the user played (SAN notation)
        best_move: The engine's best move (SAN notation)
        cp_loss: Centipawn loss (always positive, should be >= 50)
        user_color: "white" or "black"
    
    Returns:
        Dict with tags describing the mistake
    """
    # Early return if this isn't actually a mistake according to Stockfish
    if cp_loss < 50:
        return {
            "mistake_type": "good_move",
            "details": {},
            "phase": "unknown",
            "severity": "none",
            "note": "Not a mistake - cp_loss too low"
        }
    
    try:
        board = chess.Board(fen_before)
    except (ValueError, chess.InvalidFenError):
        return {
            "mistake_type": "inaccuracy",
            "details": {},
            "phase": "unknown",
            "error": "Invalid FEN"
        }
    
    color = chess.WHITE if user_color == "white" else chess.BLACK
    opponent = not color
    
    # Determine game phase
    phase = determine_phase(board)
    
    # Get position context
    was_in_check = board.is_check()
    
    # Eval context
    # Positive cp_loss means user lost centipawns
    severity = "minor"
    if cp_loss >= 300:
        severity = "blunder"
    elif cp_loss >= 100:
        severity = "mistake"
    elif cp_loss >= 50:
        severity = "inaccuracy"
    
    # Play the user's move to see the resulting position
    board_after = board.copy()
    try:
        board_after.push_san(move_played)
    except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError):
        return {
            "mistake_type": "inaccuracy",
            "details": {},
            "phase": phase.value if hasattr(phase, 'value') else str(phase),
            "severity": severity,
            "error": "Could not parse move"
        }
    
    # Check for tactical patterns
    mistake_type = "inaccuracy"  # Default
    details = {}
    
    # ==================== PRIORITY 0: CHECKMATE DETECTION ====================
    # This MUST come first - nothing else matters if there's checkmate involved
    
    # 0a. Did this move allow mate in 1?
    # After user's move, opponent can mate immediately
    if board_after.is_checkmate():
        # User got mated by their own move? That shouldn't happen...
        pass
    else:
        # Check if opponent has mate in 1 after our move
        for opp_move in board_after.legal_moves:
            test_board = board_after.copy()
            test_board.push(opp_move)
            if test_board.is_checkmate():
                mating_move = board_after.san(opp_move)
                mistake_type = "allowed_mate_in_1"
                details["mating_move"] = mating_move
                details["mating_square"] = chess.square_name(opp_move.to_square)
                details["critical"] = True
                severity = "decisive"
                # If we found mate in 1, return immediately - this is the explanation
                return {
                    "mistake_type": mistake_type,
                    "details": details,
                    "phase": phase.value if hasattr(phase, 'value') else str(phase),
                    "severity": severity,
                    "short_label": "Allowed Mate in 1",
                    "note": f"This move allowed {mating_move} which is checkmate"
                }
    
    # 0b. Did user miss a mate in 1? (best_move would have been checkmate)
    if best_move:
        try:
            board_test = board.copy()
            board_test.push_san(best_move)
            if board_test.is_checkmate():
                mistake_type = "missed_mate_in_1"
                details["mating_move"] = best_move
                details["critical"] = True
                severity = "decisive"
                return {
                    "mistake_type": mistake_type,
                    "details": details,
                    "phase": phase.value if hasattr(phase, 'value') else str(phase),
                    "severity": severity,
                    "short_label": "Missed Checkmate!",
                    "note": f"You missed {best_move} which is checkmate"
                }
        except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError):
            pass
    
    # 0c. Check for mate in 2 (allowed)
    # This is expensive so only do it for high cp_loss moves
    if cp_loss >= 500:  # Only check for big blunders
        mate_in_2_found = False
        for opp_move1 in board_after.legal_moves:
            if mate_in_2_found:
                break
            test1 = board_after.copy()
            test1.push(opp_move1)
            if test1.is_checkmate():
                # This is mate in 1, already handled above
                continue
            # Check if all our responses lead to mate
            all_responses_lead_to_mate = True
            num_responses = 0
            for our_response in test1.legal_moves:
                num_responses += 1
                if num_responses > 5:  # Limit for performance
                    all_responses_lead_to_mate = False
                    break
                test2 = test1.copy()
                test2.push(our_response)
                # Now check if opponent has mate
                has_mate = False
                for opp_move2 in test2.legal_moves:
                    test3 = test2.copy()
                    test3.push(opp_move2)
                    if test3.is_checkmate():
                        has_mate = True
                        break
                if not has_mate:
                    all_responses_lead_to_mate = False
                    break
            if num_responses > 0 and all_responses_lead_to_mate:
                mistake_type = "allowed_mate_in_2"
                details["mating_sequence_starts"] = board_after.san(opp_move1)
                details["critical"] = True
                severity = "decisive"
                mate_in_2_found = True
                return {
                    "mistake_type": mistake_type,
                    "details": details,
                    "phase": phase.value if hasattr(phase, 'value') else str(phase),
                    "severity": severity,
                    "short_label": "Allowed Forced Mate",
                    "note": f"This allowed a forced checkmate starting with {board_after.san(opp_move1)}"
                }
    
    # ==================== END CHECKMATE DETECTION ====================
    
    # 1. FIRST check if the moved piece is now hanging (directly capturable)
    # This takes priority over "fork" because moving to an attacked square = blunder
    hanging = find_hanging_pieces(board_after, color)
    moved_piece_hanging = False
    if hanging:
        # Get the destination square of the move we played
        try:
            move_obj = board.parse_san(move_played)
            to_square = chess.square_name(move_obj.to_square)
            # Check if the piece we just moved is now hanging
            for h in hanging:
                if h.get("square") == to_square:
                    moved_piece_hanging = True
                    mistake_type = "material_blunder" if h["value"] >= 5 else "hanging_piece"
                    details["hanging"] = h
                    break
        except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError):
            pass
    
    # 2. Check if walked into a fork (only if we didn't just hang the moved piece)
    if mistake_type == "inaccuracy":
        walked_into_fork = detect_walked_into_fork(board, board_after, color)
        if walked_into_fork:
            # Any piece can fork - the key is whether targets are valuable (not just pawns)
            # The fork is only relevant if total target value is significant
            total_value = walked_into_fork.get("total_value", 0)
            if total_value >= 6:  # At least a minor piece + something else
                mistake_type = "walked_into_fork"
                details["fork"] = walked_into_fork
    
    # 3. Check if walked into a pin
    if mistake_type == "inaccuracy":
        walked_into_pin = detect_walked_into_pin(board, board_after, color)
        if walked_into_pin:
            mistake_type = "walked_into_pin"
            details["pin"] = walked_into_pin
    
    # 4. Check for other hanging pieces after the move (not the moved piece)
    if mistake_type == "inaccuracy" and not moved_piece_hanging:
        if hanging:
            highest_value = max(h["value"] for h in hanging)
            if highest_value >= 3:  # At least a minor piece
                mistake_type = "hanging_piece"
                details["hanging"] = hanging[0]
    
    # 5. DEEP TACTICAL ANALYSIS - Run BEFORE simpler pattern checks
    # This catches things like piece trapping, mobility restriction that are more accurate
    # than simple "fork" detection which doesn't account for protected pieces
    if mistake_type == "inaccuracy" and best_move:
        try:
            from position_analyzer import analyze_deep_tactics
            deep_analysis = analyze_deep_tactics(fen_before, move_played, best_move, user_color)
            
            if deep_analysis.get("pattern") and deep_analysis["pattern"] not in ["positional", None]:
                # Found a meaningful tactical pattern!
                mistake_type = f"missed_{deep_analysis['pattern']}"
                details["deep_tactics"] = {
                    "pattern": deep_analysis["pattern"],
                    "pattern_name": deep_analysis["pattern_name"],
                    "explanation": deep_analysis["explanation"],
                    "key_insight": deep_analysis["key_insight"]
                }
        except Exception as e:
            logger.warning(f"Deep tactical analysis failed: {e}")
    
    # 6. Check if missed a fork with the best move (only if deep analysis didn't find anything)
    if mistake_type == "inaccuracy" and best_move:
        missed_fork = detect_missed_fork(board, best_move, color)
        if missed_fork:
            # Additional validation: check if targets are actually capturable (not well-protected)
            # A "fork" where one target is protected isn't as strong
            board_after_best = board.copy()
            try:
                board_after_best.push_san(best_move)
                actually_winning = False
                for target in missed_fork.get("targets", []):
                    target_sq = chess.parse_square(target["square"])
                    # Count attackers vs defenders
                    attackers = len(board_after_best.attackers(color, target_sq))
                    defenders = len(board_after_best.attackers(opponent, target_sq))
                    if attackers > defenders:
                        actually_winning = True
                        break
                
                if actually_winning:
                    mistake_type = "missed_fork"
                    details["missed_fork"] = missed_fork
            except Exception:
                # If we can't verify, still report the fork
                mistake_type = "missed_fork"
                details["missed_fork"] = missed_fork
    
    # 7. Check if missed a pin with the best move
    if mistake_type == "inaccuracy" and best_move:
        missed_pin = detect_missed_pin(board, best_move, color)
        if missed_pin:
            mistake_type = "missed_pin"
            details["missed_pin"] = missed_pin
    
    # 6. Check if walked into a skewer (e.g., queen moved in front of king/rook)
    if mistake_type == "inaccuracy":
        walked_into_skewer = detect_walked_into_skewer(board, board_after, color)
        if walked_into_skewer:
            mistake_type = "walked_into_skewer"
            details["skewer"] = walked_into_skewer
    
    # 7. Check for opponent threats that were ignored
    if mistake_type == "inaccuracy":
        # Get opponent's threatening moves BEFORE user's move
        board_opponent_turn = board.copy()
        board_opponent_turn.turn = opponent
        
        # Check if opponent can now execute a threat
        opponent_forks = find_forks(board_after, opponent)
        if opponent_forks and opponent_forks[0].get("includes_king") or (opponent_forks and opponent_forks[0].get("total_value", 0) >= 8):
            mistake_type = "ignored_threat"
            details["threat"] = f"Opponent has {opponent_forks[0]['attacker_piece']} fork"
        
        # Check for opponent skewers after our move
        if mistake_type == "inaccuracy":
            opponent_skewers = find_skewers(board_after, opponent)
            if opponent_skewers:
                # The user walked into a position where they can be skewered
                mistake_type = "walked_into_skewer"
                details["skewer"] = opponent_skewers[0]
    
    # 8. Determine if it's a conversion failure (was ahead, now not)
    # This would need eval_before which we don't have in this function
    # So we'll mark it based on phase and severity
    if severity == "blunder" and phase == GamePhase.ENDGAME:
        if mistake_type == "inaccuracy":
            mistake_type = "failed_conversion"
    
    # 9. Phase-specific defaults
    if mistake_type == "inaccuracy":
        if phase == GamePhase.OPENING and cp_loss >= 50:
            mistake_type = "opening_inaccuracy"
        elif cp_loss >= 50:
            mistake_type = "positional_drift"
    
    return {
        "mistake_type": mistake_type,
        "details": details,
        "phase": phase.value if hasattr(phase, 'value') else str(phase),
        "severity": severity,
        "was_in_check": was_in_check
    }


def build_explanation_prompt(analysis: Dict, move_data: Dict) -> str:
    """
    Build a prompt for GPT to generate the educational explanation.
    
    GPT's job is ONLY to write readable commentary - NOT to analyze chess.
    We provide all the facts, GPT makes them readable.
    """
    mistake_type = analysis.get("mistake_type", "inaccuracy")
    template = MISTAKE_TEMPLATES.get(mistake_type, MISTAKE_TEMPLATES["inaccuracy"])
    details = analysis.get("details", {})
    phase = analysis.get("phase", "middlegame")
    
    # Build the context for GPT
    context_parts = []
    
    # Move info
    context_parts.append(f"Move played: {move_data.get('move', '?')}")
    context_parts.append(f"Better move: {move_data.get('best_move', '?')}")
    context_parts.append(f"Centipawn loss: {move_data.get('cp_loss', 0)}")
    context_parts.append(f"Game phase: {phase}")
    
    # =============== CHECKMATE PATTERNS (HIGHEST PRIORITY) ===============
    if mistake_type == "allowed_mate_in_1":
        mating_move = details.get("mating_move", "?")
        context_parts.append("CRITICAL ERROR: This move allowed CHECKMATE in 1 move!")
        context_parts.append(f"Opponent's mating move: {mating_move}")
        context_parts.append("SEVERITY: This is the most decisive mistake - the game is immediately lost")
    
    elif mistake_type == "allowed_mate_in_2":
        mating_start = details.get("mating_sequence_starts", "?")
        context_parts.append("CRITICAL ERROR: This move allowed FORCED CHECKMATE")
        context_parts.append(f"Mating sequence starts with: {mating_start}")
        context_parts.append("SEVERITY: The game is lost - opponent has a forced mate")
    
    elif mistake_type == "missed_mate_in_1":
        mating_move = details.get("mating_move", "?")
        context_parts.append(f"MISSED WINNING MOVE: {mating_move} was CHECKMATE!")
        context_parts.append("You had mate in one but missed it")
    
    elif mistake_type == "missed_mate_in_2":
        context_parts.append("MISSED WINNING SEQUENCE: You had forced checkmate available")
    
    # Pattern-specific details
    elif mistake_type == "walked_into_fork" and details.get("fork"):
        fork = details["fork"]
        targets = fork.get("targets", [])
        target_desc = " and ".join([f"{t['piece']} on {t['square']}" for t in targets[:2]])
        context_parts.append(f"TACTICAL PATTERN: User walked into a {fork.get('attacker_piece', 'knight')} fork attacking {target_desc}")
    
    elif mistake_type == "walked_into_pin" and details.get("pin"):
        pin = details["pin"]
        context_parts.append(f"TACTICAL PATTERN: User created a pin - {pin.get('pinned_piece', 'piece')} is now pinned to the {pin.get('pinned_to', 'king')}")
    
    elif mistake_type == "hanging_piece" and details.get("hanging"):
        hanging = details["hanging"]
        context_parts.append(f"TACTICAL PATTERN: Left {hanging.get('piece', 'piece')} on {hanging.get('square', '?')} undefended")
    
    elif mistake_type == "missed_fork" and details.get("missed_fork"):
        fork = details["missed_fork"]
        targets = fork.get("targets", [])
        target_desc = " and ".join([f"{t['piece']}" for t in targets[:2]])
        context_parts.append(f"MISSED TACTIC: Could have forked {target_desc} with {fork.get('attacker_piece', 'knight')}")
    
    elif mistake_type == "missed_pin" and details.get("missed_pin"):
        pin = details["missed_pin"]
        context_parts.append(f"MISSED TACTIC: Could have pinned {pin.get('pinned_piece', 'piece')} to the {pin.get('pinned_to', 'king')}")
    
    elif mistake_type == "ignored_threat" and details.get("threat"):
        context_parts.append(f"IGNORED THREAT: {details['threat']}")
    
    elif mistake_type == "walked_into_skewer" and details.get("skewer"):
        skewer = details["skewer"]
        context_parts.append(f"TACTICAL PATTERN: User walked into a skewer - {skewer.get('front_piece', 'piece')} on {skewer.get('front_square', '?')} is attacked by {skewer.get('attacker', 'opponent piece')}, exposing {skewer.get('back_piece', 'piece')} behind it")
    
    # Handle deep tactical analysis patterns
    elif details.get("deep_tactics"):
        deep = details["deep_tactics"]
        pattern_name = deep.get("pattern_name", "tactical opportunity")
        explanation = deep.get("explanation", "")
        key_insight = deep.get("key_insight", "")
        
        context_parts.append(f"TACTICAL PATTERN: {pattern_name}")
        if explanation:
            context_parts.append(f"WHAT HAPPENED: {explanation}")
        if key_insight:
            context_parts.append(f"KEY INSIGHT: {key_insight}")
    
    # Template info
    context_parts.append(f"MISTAKE CATEGORY: {template['short']}")
    context_parts.append(f"PATTERN: {template['pattern']}")
    if template.get("thinking_habit"):
        context_parts.append(f"THINKING HABIT TO BUILD: {template['thinking_habit']}")
    
    context_str = "\n".join(context_parts)
    
    prompt = f"""You are a chess coach writing an educational explanation for a student's mistake.

FACTS ABOUT THIS MISTAKE (these are VERIFIED by chess engine - NEVER contradict or change them):
{context_str}

YOUR TASK:
Write 2-3 sentences explaining WHY this move was a mistake and what the student should learn.

CRITICAL RULES:
1. ONLY mention tactical patterns (fork, pin, skewer, etc.) if explicitly stated in FACTS above
2. If no TACTICAL PATTERN is listed above, DO NOT invent one - just explain the general issue
3. NEVER say "fork" "pin" "skewer" "discovered attack" unless the FACTS section explicitly mentions it
4. Use simple, clear English (8th grade reading level)
5. Focus on the THINKING ERROR, not just the move
6. Be supportive, not harsh ("it happens!" "next time try...")
7. End with a concrete tip from the THINKING HABIT above
8. Do NOT mention centipawns, engine scores, or technical jargon
9. Keep it under 50 words

Write the explanation now (no preamble, just the explanation):"""
    
    return prompt


async def generate_mistake_explanation(move_data: Dict, llm_call_func) -> Dict:
    """
    Generate an educational explanation for a mistake.
    
    This is the main entry point for the service.
    
    Args:
        move_data: Dict containing:
            - fen_before: FEN position before move
            - move: The move played (SAN)
            - best_move: The better move (SAN)
            - cp_loss: Centipawn loss
            - user_color: "white" or "black"
        llm_call_func: Async function to call LLM (from llm_service)
    
    Returns:
        Dict with:
            - explanation: Human-readable explanation
            - mistake_type: Category of mistake
            - thinking_habit: Suggestion for improvement
            - details: Tactical details if applicable
    """
    # Step 1: Deterministic analysis
    analysis = analyze_mistake_position(
        fen_before=move_data.get("fen_before", ""),
        move_played=move_data.get("move", ""),
        best_move=move_data.get("best_move", ""),
        cp_loss=move_data.get("cp_loss", 0),
        user_color=move_data.get("user_color", "white")
    )
    
    mistake_type = analysis.get("mistake_type", "inaccuracy")
    template = MISTAKE_TEMPLATES.get(mistake_type, MISTAKE_TEMPLATES["inaccuracy"])
    
    # Step 2: Generate explanation with LLM
    prompt = build_explanation_prompt(analysis, move_data)
    
    try:
        explanation = await llm_call_func(
            system_message="You are a friendly chess coach. Write short, educational explanations.",
            user_message=prompt,
            model="gpt-4o-mini"
        )
        explanation = explanation.strip()
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        # Fallback to template-based explanation
        explanation = f"{template['pattern']} {template.get('thinking_habit', '')}"
    
    return {
        "explanation": explanation,
        "mistake_type": mistake_type,
        "short_label": template.get("short", "Mistake"),
        "thinking_habit": template.get("thinking_habit"),
        "severity": analysis.get("severity", "minor"),
        "phase": analysis.get("phase", "middlegame"),
        "details": analysis.get("details", {})
    }


def get_quick_explanation(mistake_type: str, details: Dict = None) -> str:
    """
    Get a quick template-based explanation without LLM call.
    Use this for bulk operations or when LLM is unavailable.
    """
    template = MISTAKE_TEMPLATES.get(mistake_type, MISTAKE_TEMPLATES["inaccuracy"])
    
    explanation = template["pattern"]
    
    # Add specific details if available
    if details:
        # CHECKMATE PATTERNS - highest priority
        if mistake_type == "allowed_mate_in_1" and details.get("mating_move"):
            mating_move = details["mating_move"]
            explanation = f"This move allowed {mating_move} which is checkmate! Always check: does my move allow any checks that could be mate?"
        
        elif mistake_type == "allowed_mate_in_2" and details.get("mating_sequence_starts"):
            explanation = f"This move allowed a forced checkmate. The game is lost after {details['mating_sequence_starts']}."
        
        elif mistake_type == "missed_mate_in_1" and details.get("mating_move"):
            explanation = f"You missed {details['mating_move']} which was checkmate! Always scan for mate before playing."
        
        elif mistake_type == "missed_mate_in_2":
            explanation = "You had a forced checkmate available but missed it. Worth practicing mate patterns!"
        
        elif mistake_type == "walked_into_fork" and details.get("fork"):
            fork = details["fork"]
            targets = fork.get("targets", [])
            if targets:
                target_desc = " and ".join([t['piece'] for t in targets[:2]])
                explanation = f"Your move allowed opponent's {fork.get('attacker_piece', 'knight')} to fork your {target_desc}."
        
        elif mistake_type == "hanging_piece" and details.get("hanging"):
            hanging = details["hanging"]
            explanation = f"Your {hanging.get('piece', 'piece')} on {hanging.get('square', '')} was left undefended."
        
        elif mistake_type == "missed_fork" and details.get("missed_fork"):
            fork = details["missed_fork"]
            targets = fork.get("targets", [])
            if targets:
                target_desc = " and ".join([t['piece'] for t in targets[:2]])
                explanation = f"You could have forked {target_desc} with your {fork.get('attacker_piece', 'knight')}!"
    
    return explanation
