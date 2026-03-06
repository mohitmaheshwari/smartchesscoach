"""
Cognitive Gap Analyzer - Precise Diagnosis of WHY a Move Was Wrong

This is the CRITICAL layer that determines the actual cognitive error.
Must be EXTREMELY ACCURATE - this data drives all coaching decisions.

Cognitive Gap Types:
- calculation_depth: Saw the right idea but didn't calculate far enough
- threat_blindness: Didn't see opponent's threat/response  
- tactical_oversight: Missed a concrete tactic (fork, pin, skewer, etc.)
- positional_misread: Misunderstood what the position required
- defensive_lapse: Forgot about defense while focused on own plan
- overconfidence: Assumed opponent would miss something
- time_pressure: Move was rushed due to clock
- pattern_unfamiliarity: Didn't recognize a standard pattern/motif

Accuracy is PARAMOUNT. We only tag what we can PROVE from the position.
"""

import chess
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class CognitiveGap(str, Enum):
    """Types of cognitive gaps - must be precise and actionable."""
    
    # Calculation errors
    CALCULATION_DEPTH = "calculation_depth"  # Didn't see far enough
    CALCULATION_ERROR = "calculation_error"  # Made arithmetic mistake in line
    
    # Awareness errors
    THREAT_BLINDNESS = "threat_blindness"  # Didn't see opponent's threat
    HANGING_PIECE_BLINDNESS = "hanging_piece_blindness"  # Left piece undefended
    CHECK_BLINDNESS = "check_blindness"  # Didn't see a check
    
    # Tactical errors
    TACTICAL_OVERSIGHT = "tactical_oversight"  # Missed tactic (generic)
    MISSED_FORK = "missed_fork"  # Specific: missed fork opportunity or allowed one
    MISSED_PIN = "missed_pin"  # Specific: missed pin
    MISSED_SKEWER = "missed_skewer"  # Specific: missed skewer
    MISSED_DISCOVERED_ATTACK = "missed_discovered"  # Missed discovered attack
    BACK_RANK_BLINDNESS = "back_rank_blindness"  # Missed back rank threat
    
    # Positional errors
    POSITIONAL_MISREAD = "positional_misread"  # Wrong assessment of position needs
    WRONG_PLAN = "wrong_plan"  # Correct calculation but wrong strategic idea
    PREMATURE_ACTION = "premature_action"  # Acted before completing development/prep
    
    # Defensive errors
    DEFENSIVE_LAPSE = "defensive_lapse"  # Forgot defense while attacking
    KING_SAFETY_NEGLECT = "king_safety_neglect"  # Ignored king safety
    
    # Psychological errors
    OVERCONFIDENCE = "overconfidence"  # Assumed opponent would miss
    DESPERATION = "desperation"  # Made hope chess move when losing
    
    # Time-related
    TIME_PRESSURE = "time_pressure"  # Rushed due to clock
    RUSHED_MOVE = "rushed_move"  # Moved too fast (not clock related)
    
    # Pattern recognition
    PATTERN_UNFAMILIARITY = "pattern_unfamiliarity"  # Didn't recognize standard pattern
    
    # When we can't determine precisely
    UNCLEAR = "unclear"  # Couldn't determine the specific gap


@dataclass
class GapAnalysisResult:
    """Result of cognitive gap analysis."""
    primary_gap: CognitiveGap
    confidence: float  # 0.0 to 1.0 - how sure we are
    evidence: str  # Concrete proof from the position
    explanation: str  # Human-readable explanation
    secondary_gaps: List[CognitiveGap]  # Other contributing factors
    coaching_focus: str  # What to work on
    

def get_piece_value(piece_type: int) -> int:
    """Standard piece values."""
    values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0,
    }
    return values.get(piece_type, 0)


def find_hanging_pieces(board: chess.Board, color: chess.Color) -> List[Tuple[int, int]]:
    """Find all hanging (undefended attacked) pieces for a color.
    Returns list of (square, piece_value) tuples.
    """
    hanging = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color:
            attackers = board.attackers(not color, square)
            defenders = board.attackers(color, square)
            if attackers and not defenders:
                hanging.append((square, get_piece_value(piece.piece_type)))
    return hanging


def find_threats(board: chess.Board, color: chess.Color) -> List[Dict]:
    """Find concrete threats that color has.
    Returns list of threat dictionaries.
    """
    threats = []
    
    # Check for checks
    if board.is_check():
        threats.append({
            "type": "check",
            "severity": "high",
            "description": "King is in check"
        })
    
    # Check for attacks on undefended pieces
    opponent = not color
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == opponent:
            attackers = list(board.attackers(color, square))
            defenders = list(board.attackers(opponent, square))
            
            if attackers:
                attacker_values = [get_piece_value(board.piece_at(a).piece_type) for a in attackers if board.piece_at(a)]
                defender_values = [get_piece_value(board.piece_at(d).piece_type) for d in defenders if board.piece_at(d)]
                target_value = get_piece_value(piece.piece_type)
                
                # Undefended piece under attack
                if not defenders:
                    threats.append({
                        "type": "hanging_attack",
                        "square": chess.square_name(square),
                        "piece": piece.symbol(),
                        "value": target_value,
                        "severity": "high" if target_value >= 3 else "medium",
                        "description": f"Attacks undefended {chess.piece_name(piece.piece_type)} on {chess.square_name(square)}"
                    })
                # Piece attacked by lower value piece
                elif attacker_values and min(attacker_values) < target_value:
                    threats.append({
                        "type": "favorable_exchange",
                        "square": chess.square_name(square),
                        "piece": piece.symbol(),
                        "severity": "medium",
                        "description": f"Can win material on {chess.square_name(square)}"
                    })
    
    return threats


def detect_tactical_motifs(board: chess.Board, move: chess.Move) -> List[Dict]:
    """Detect tactical motifs in a position after a move.
    Returns list of detected motifs.
    """
    motifs = []
    board_after = board.copy()
    board_after.push(move)
    
    moving_piece = board.piece_at(move.from_square)
    if not moving_piece:
        return motifs
    
    moving_color = moving_piece.color
    to_square = move.to_square
    
    # Check for forks
    attacks_after = list(board_after.attacks(to_square))
    attacked_pieces = []
    for sq in attacks_after:
        piece = board_after.piece_at(sq)
        if piece and piece.color != moving_color:
            attacked_pieces.append((sq, piece, get_piece_value(piece.piece_type)))
    
    # Fork: attacking 2+ pieces with combined value > attacker value
    if len(attacked_pieces) >= 2:
        attacker_value = get_piece_value(moving_piece.piece_type)
        high_value_targets = [p for p in attacked_pieces if p[2] >= attacker_value or p[1].piece_type == chess.KING]
        if len(high_value_targets) >= 2:
            motifs.append({
                "type": "fork",
                "attacker": chess.piece_name(moving_piece.piece_type),
                "targets": [chess.square_name(p[0]) for p in high_value_targets[:2]],
                "description": f"{chess.piece_name(moving_piece.piece_type).title()} fork on {chess.square_name(to_square)}"
            })
    
    # Check for discovered attacks
    # (piece moves, revealing attack from behind)
    file_from = chess.square_file(move.from_square)
    rank_from = chess.square_rank(move.from_square)
    
    # Check pieces that were behind the moving piece
    for direction in [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]:
        sq = move.from_square
        # Go backwards from where piece was
        df, dr = -direction[0], -direction[1]
        while True:
            f = chess.square_file(sq) + df
            r = chess.square_rank(sq) + dr
            if not (0 <= f <= 7 and 0 <= r <= 7):
                break
            sq = chess.square(f, r)
            piece = board.piece_at(sq)
            if piece:
                if piece.color == moving_color:
                    # Check if this piece now has new attacks through the vacated square
                    # This is a simplified check
                    if piece.piece_type in [chess.ROOK, chess.QUEEN, chess.BISHOP]:
                        attacks_before = set(board.attacks(sq))
                        attacks_now = set(board_after.attacks(sq))
                        new_attacks = attacks_now - attacks_before
                        for atk_sq in new_attacks:
                            target = board_after.piece_at(atk_sq)
                            if target and target.color != moving_color:
                                motifs.append({
                                    "type": "discovered_attack",
                                    "attacker": chess.piece_name(piece.piece_type),
                                    "target": chess.square_name(atk_sq),
                                    "description": f"Discovered attack by {chess.piece_name(piece.piece_type)} on {chess.square_name(atk_sq)}"
                                })
                break
    
    # Check for pins (piece cannot move because it exposes king)
    # This is complex to detect fully, simplified version:
    opponent_king_sq = board_after.king(not moving_color)
    if opponent_king_sq:
        # Check if moving piece is pinning something to the king
        for sq in attacks_after:
            piece = board_after.piece_at(sq)
            if piece and piece.color != moving_color and piece.piece_type != chess.KING:
                # Check if piece is between our piece and their king
                # Simplified: check if on same line
                if (chess.square_file(to_square) == chess.square_file(sq) == chess.square_file(opponent_king_sq) or
                    chess.square_rank(to_square) == chess.square_rank(sq) == chess.square_rank(opponent_king_sq)):
                    # Could be a pin on file/rank
                    if moving_piece.piece_type in [chess.ROOK, chess.QUEEN]:
                        motifs.append({
                            "type": "pin",
                            "pinned_piece": chess.piece_name(piece.piece_type),
                            "square": chess.square_name(sq),
                            "description": f"Pins {chess.piece_name(piece.piece_type)} to king"
                        })
    
    return motifs


def analyze_cognitive_gap(
    fen_before: str,
    user_move_san: str,
    best_move_san: str,
    eval_before: float,
    eval_after: float,
    threat_description: Optional[str] = None,
    user_stated_plan: Optional[str] = None,
    user_hypothesis_category: Optional[str] = None,
    time_spent_seconds: Optional[float] = None,
    clock_remaining_seconds: Optional[float] = None,
    user_confidence: Optional[str] = None,
) -> Dict:
    """
    Analyze the cognitive gap between user's move and the best move.
    
    This is the CORE function - must be EXTREMELY ACCURATE.
    
    Args:
        fen_before: Position before the move
        user_move_san: What user played
        best_move_san: What Stockfish recommends
        eval_before: Centipawn evaluation before move
        eval_after: Centipawn evaluation after user's move
        threat_description: Description of threat user missed (from Stockfish)
        user_stated_plan: What user said they were trying to do
        user_hypothesis_category: Category of user's selected hypothesis
        time_spent_seconds: How long user thought
        clock_remaining_seconds: Clock time remaining
        user_confidence: User's stated confidence level
        
    Returns:
        Dictionary with gap analysis results
    """
    try:
        board = chess.Board(fen_before)
        user_move = board.parse_san(user_move_san)
        best_move = board.parse_san(best_move_san)
    except (ValueError, chess.InvalidMoveError, chess.AmbiguousMoveError) as e:
        return {
            "primary_gap": CognitiveGap.UNCLEAR.value,
            "confidence": 0.0,
            "evidence": f"Could not parse moves: {e}",
            "explanation": "Unable to analyze this position",
            "secondary_gaps": [],
            "coaching_focus": None,
        }
    
    user_color = board.turn
    cp_loss = abs(eval_before - eval_after)
    
    # ========================================
    # STEP 0: Check LEARNED PATTERN RULES first
    # These are rules extracted from user feedback
    # Uses SYNCHRONOUS check via position features (no DB call needed!)
    # ========================================
    try:
        from services.pattern_learning.pattern_rule_extractor import PatternRuleExtractor, PositionAnalyzer
        
        # Use the position analyzer to extract features
        analyzer = PositionAnalyzer()
        position_features = analyzer.extract_features(fen_before, best_move_san, user_move_san)
        
        # Check for common patterns based on position features
        matched_rule = None
        rule_confidence = 0.0
        
        # Pattern: KING_SAFETY_LUFT - King on back rank with no escape squares
        if position_features.king_on_back_rank and position_features.king_escape_squares == 0:
            if position_features.back_rank_vulnerable:
                matched_rule = {
                    "pattern_name": "BACK_RANK_MATE_THREAT",
                    "explanation_template": "You missed a back rank mate threat. Your king is stuck on the back rank with no escape, and the enemy rook/queen can deliver checkmate. {best_move} prevents this.",
                    "rule_id": "builtin_back_rank"
                }
                rule_confidence = 0.9
            else:
                matched_rule = {
                    "pattern_name": "KING_SAFETY_LUFT",
                    "explanation_template": "The move {best_move} was better because it gives your king breathing room (luft), preventing back rank threats. Your king was trapped with no escape squares.",
                    "rule_id": "builtin_luft"
                }
                rule_confidence = 0.85
        
        # Pattern: HANGING_PIECE
        elif position_features.hanging_pieces and len(position_features.hanging_pieces) > 0:
            matched_rule = {
                "pattern_name": "HANGING_PIECE",
                "explanation_template": "You left a piece undefended. {best_move} would have protected it or removed it from danger.",
                "rule_id": "builtin_hanging"
            }
            rule_confidence = 0.85
        
        if matched_rule and rule_confidence >= 0.7:
            # Use the matched pattern!
            explanation = matched_rule["explanation_template"].format(
                best_move=best_move_san,
                played_move=user_move_san
            )
            
            # Map pattern name to CognitiveGap
            gap_mapping = {
                "KING_SAFETY_LUFT": CognitiveGap.KING_SAFETY_NEGLECT.value,
                "KING_SAFETY": CognitiveGap.KING_SAFETY_NEGLECT.value,
                "BACK_RANK_MATE_THREAT": CognitiveGap.BACK_RANK_BLINDNESS.value,
                "HANGING_PIECE": CognitiveGap.HANGING_PIECE_BLINDNESS.value,
                "PIECE_FORK": CognitiveGap.MISSED_FORK.value,
                "PIN": CognitiveGap.MISSED_PIN.value,
            }
            
            primary_gap = gap_mapping.get(
                matched_rule["pattern_name"], 
                CognitiveGap.POSITIONAL_MISREAD.value
            )
            
            return {
                "primary_gap": primary_gap,
                "confidence": rule_confidence,
                "evidence": f"Matched pattern: {matched_rule['pattern_name']}",
                "explanation": explanation,
                "secondary_gaps": [],
                "coaching_focus": f"Focus on {matched_rule['pattern_name'].lower().replace('_', ' ')} patterns",
                "learned_from_feedback": True,
                "rule_id": matched_rule["rule_id"],
            }
    except Exception as e:
        # If pattern matching fails, continue with normal analysis
        pass
    
    # ========================================
    # STEP 1: Check for TIME PRESSURE (easiest to identify)
    # ========================================
    if clock_remaining_seconds is not None and clock_remaining_seconds < 30:
        # Under 30 seconds - time pressure is a factor
        time_pressure_factor = True
        if clock_remaining_seconds < 10:
            # Critical time pressure
            return {
                "primary_gap": CognitiveGap.TIME_PRESSURE.value,
                "confidence": 0.95,
                "evidence": f"Only {clock_remaining_seconds:.0f} seconds on clock",
                "explanation": "You were in severe time pressure. This move was likely rushed out of necessity.",
                "secondary_gaps": [],
                "coaching_focus": "Work on time management - avoid getting into time trouble",
            }
    else:
        time_pressure_factor = False
    
    # Check for rushed move (fast move, not clock related)
    if time_spent_seconds is not None and time_spent_seconds < 5 and cp_loss > 100:
        rushed_factor = True
    else:
        rushed_factor = False
    
    # ========================================
    # STEP 2: Analyze what BEST MOVE accomplishes
    # ========================================
    board_after_best = board.copy()
    board_after_best.push(best_move)
    
    best_move_effects = {
        "is_check": board_after_best.is_check(),
        "is_capture": board.is_capture(best_move),
        "captured_piece": None,
        "tactical_motifs": detect_tactical_motifs(board, best_move),
        "threats_created": find_threats(board_after_best, user_color),
    }
    
    if board.is_capture(best_move):
        captured = board.piece_at(best_move.to_square)
        if captured:
            best_move_effects["captured_piece"] = chess.piece_name(captured.piece_type)
            best_move_effects["captured_value"] = get_piece_value(captured.piece_type)
    
    # ========================================
    # STEP 3: Analyze what USER MOVE does
    # ========================================
    board_after_user = board.copy()
    board_after_user.push(user_move)
    
    user_move_effects = {
        "is_check": board_after_user.is_check(),
        "is_capture": board.is_capture(user_move),
        "captured_piece": None,
        "tactical_motifs": detect_tactical_motifs(board, user_move),
        "threats_created": find_threats(board_after_user, user_color),
        "hanging_pieces_after": find_hanging_pieces(board_after_user, user_color),
    }
    
    if board.is_capture(user_move):
        captured = board.piece_at(user_move.to_square)
        if captured:
            user_move_effects["captured_piece"] = chess.piece_name(captured.piece_type)
            user_move_effects["captured_value"] = get_piece_value(captured.piece_type)
    
    # ========================================
    # STEP 4: Check what threats OPPONENT has after user's move
    # ========================================
    opponent_threats_after = find_threats(board_after_user, not user_color)
    
    # ========================================
    # STEP 5: DETERMINE THE GAP
    # ========================================
    
    # Case 1: User left a piece hanging
    if user_move_effects["hanging_pieces_after"]:
        worst_hanging = max(user_move_effects["hanging_pieces_after"], key=lambda x: x[1])
        hanging_square, hanging_value = worst_hanging
        piece_at_hanging = board_after_user.piece_at(hanging_square)
        
        if hanging_value >= 3:  # Knight/Bishop or higher
            return {
                "primary_gap": CognitiveGap.HANGING_PIECE_BLINDNESS.value,
                "confidence": 0.95,
                "evidence": f"Left {chess.piece_name(piece_at_hanging.piece_type)} on {chess.square_name(hanging_square)} undefended and under attack",
                "explanation": f"Your {chess.piece_name(piece_at_hanging.piece_type)} on {chess.square_name(hanging_square)} is now hanging. Before moving, you need to check: 'Is anything undefended after this move?'",
                "secondary_gaps": [CognitiveGap.DEFENSIVE_LAPSE.value] if user_stated_plan and "attack" in user_stated_plan.lower() else [],
                "coaching_focus": "Before EVERY move, ask: 'What am I leaving undefended?'",
                "time_factor": "rushed" if rushed_factor else None,
            }
    
    # Case 2: User missed a check (best move was check)
    if best_move_effects["is_check"] and not user_move_effects["is_check"]:
        if cp_loss > 150:
            return {
                "primary_gap": CognitiveGap.CHECK_BLINDNESS.value,
                "confidence": 0.90,
                "evidence": f"Best move {best_move_san} gives check, which you missed",
                "explanation": f"The move {best_move_san} gives check, creating a forcing move that you missed. Always look for checks first.",
                "secondary_gaps": [CognitiveGap.CALCULATION_DEPTH.value],
                "coaching_focus": "Start your candidate move search with: 'Are there any checks?'",
            }
    
    # Case 3: User missed a winning capture
    if best_move_effects["is_capture"] and best_move_effects.get("captured_value", 0) >= 3:
        if not user_move_effects["is_capture"] or user_move_effects.get("captured_value", 0) < best_move_effects["captured_value"]:
            return {
                "primary_gap": CognitiveGap.TACTICAL_OVERSIGHT.value,
                "confidence": 0.85,
                "evidence": f"Could capture {best_move_effects['captured_piece']} with {best_move_san}",
                "explanation": f"You could have captured the {best_move_effects['captured_piece']} with {best_move_san}. This was a free piece or a favorable exchange.",
                "secondary_gaps": [],
                "coaching_focus": "Before each move, scan: 'Can I capture anything valuable?'",
            }
    
    # Case 4: User missed a fork (best move creates fork)
    best_forks = [m for m in best_move_effects["tactical_motifs"] if m["type"] == "fork"]
    if best_forks:
        fork = best_forks[0]
        return {
            "primary_gap": CognitiveGap.MISSED_FORK.value,
            "confidence": 0.90,
            "evidence": f"{best_move_san} creates a {fork['attacker']} fork on {', '.join(fork['targets'])}",
            "explanation": f"The move {best_move_san} creates a fork, attacking multiple pieces at once. {fork['description']}.",
            "secondary_gaps": [CognitiveGap.PATTERN_UNFAMILIARITY.value],
            "coaching_focus": "Practice recognizing fork patterns. Ask: 'Can any piece attack two things at once?'",
        }
    
    # Case 5: User missed a pin
    best_pins = [m for m in best_move_effects["tactical_motifs"] if m["type"] == "pin"]
    if best_pins:
        pin = best_pins[0]
        return {
            "primary_gap": CognitiveGap.MISSED_PIN.value,
            "confidence": 0.85,
            "evidence": f"{best_move_san} pins the {pin['pinned_piece']} on {pin['square']}",
            "explanation": f"The move {best_move_san} pins a piece to the king. {pin['description']}.",
            "secondary_gaps": [CognitiveGap.PATTERN_UNFAMILIARITY.value],
            "coaching_focus": "Look for pieces on the same line as the opponent's king",
        }
    
    # Case 6: User missed a discovered attack
    best_discovered = [m for m in best_move_effects["tactical_motifs"] if m["type"] == "discovered_attack"]
    if best_discovered:
        disc = best_discovered[0]
        return {
            "primary_gap": CognitiveGap.MISSED_DISCOVERED_ATTACK.value,
            "confidence": 0.85,
            "evidence": f"{best_move_san} creates {disc['description']}",
            "explanation": "Moving allows a discovered attack. Your piece clears the way for another piece to attack.",
            "secondary_gaps": [CognitiveGap.PATTERN_UNFAMILIARITY.value],
            "coaching_focus": "When moving a piece, check: 'What does this uncover behind it?'",
        }
    
    # Case 7: Analyze the threat that user missed (from Stockfish analysis)
    if threat_description:
        threat_lower = threat_description.lower()
        
        # Check for mate-level cp_loss (9000+ = checkmate) even if threat doesn't say "mate"
        is_checkmate_level = cp_loss >= 9000
        
        if "mate" in threat_lower or "checkmate" in threat_lower or is_checkmate_level:
            # Build specific explanation
            if is_checkmate_level:
                explanation = f"You missed checkmate! After your move, opponent had {threat_description} leading to checkmate."
            else:
                explanation = f"You missed a checkmate threat. {threat_description}"
            
            return {
                "primary_gap": CognitiveGap.THREAT_BLINDNESS.value,
                "confidence": 0.95,
                "evidence": f"Missed threat: {threat_description}" + (" (leads to checkmate)" if is_checkmate_level else ""),
                "explanation": explanation,
                "secondary_gaps": [CognitiveGap.KING_SAFETY_NEGLECT.value],
                "coaching_focus": "Before EVERY move, ask: 'What can opponent do to me RIGHT NOW? Any checks?'",
            }
        
        if "fork" in threat_lower:
            return {
                "primary_gap": CognitiveGap.THREAT_BLINDNESS.value,
                "confidence": 0.90,
                "evidence": f"Missed threat: {threat_description}",
                "explanation": f"You allowed a fork. {threat_description}",
                "secondary_gaps": [CognitiveGap.MISSED_FORK.value],
                "coaching_focus": "Before moving, ask: 'Can opponent fork me after this?'",
            }
        
        if "pin" in threat_lower:
            return {
                "primary_gap": CognitiveGap.THREAT_BLINDNESS.value,
                "confidence": 0.85,
                "evidence": f"Missed threat: {threat_description}",
                "explanation": f"You allowed a pin. {threat_description}",
                "secondary_gaps": [CognitiveGap.MISSED_PIN.value],
                "coaching_focus": "Check if any pieces are on the same line as your king/queen",
            }
        
        if "hanging" in threat_lower or "undefended" in threat_lower or "wins" in threat_lower:
            return {
                "primary_gap": CognitiveGap.THREAT_BLINDNESS.value,
                "confidence": 0.90,
                "evidence": f"Missed threat: {threat_description}",
                "explanation": f"You didn't see opponent's threat. {threat_description}",
                "secondary_gaps": [CognitiveGap.DEFENSIVE_LAPSE.value],
                "coaching_focus": "Before moving, ask: 'What can opponent do to me after this?'",
            }
        
        if "back rank" in threat_lower:
            return {
                "primary_gap": CognitiveGap.BACK_RANK_BLINDNESS.value,
                "confidence": 0.90,
                "evidence": f"Missed threat: {threat_description}",
                "explanation": "You missed a back rank threat. Your king needs an escape square.",
                "secondary_gaps": [CognitiveGap.KING_SAFETY_NEGLECT.value],
                "coaching_focus": "Check if your king has luft (escape square) on the back rank",
            }
    
    # Case 8: Check if user's plan was reasonable but execution was wrong
    if user_stated_plan:
        plan_lower = user_stated_plan.lower()
        
        # User wanted to attack but forgot defense
        if "attack" in plan_lower or "threat" in plan_lower:
            if opponent_threats_after:
                high_threats = [t for t in opponent_threats_after if t.get("severity") == "high"]
                if high_threats:
                    return {
                        "primary_gap": CognitiveGap.DEFENSIVE_LAPSE.value,
                        "confidence": 0.85,
                        "evidence": f"Focused on attacking but missed opponent's threat: {high_threats[0].get('description', '')}",
                        "explanation": f"Your attacking idea was understandable, but you forgot to check opponent's threats first. {high_threats[0].get('description', '')}",
                        "secondary_gaps": [CognitiveGap.THREAT_BLINDNESS.value],
                        "coaching_focus": "Before attacking, ALWAYS check: 'What can opponent do to me?'",
                    }
        
        # User wanted to defend but calculation was short
        if "defend" in plan_lower or "protect" in plan_lower:
            if cp_loss > 200:
                return {
                    "primary_gap": CognitiveGap.CALCULATION_DEPTH.value,
                    "confidence": 0.75,
                    "evidence": "Defensive intent was correct, but the specific move didn't work",
                    "explanation": "You correctly identified the need to defend, but the move you chose doesn't actually solve the problem. Calculate one move deeper.",
                    "secondary_gaps": [],
                    "coaching_focus": "When defending, calculate: 'After I defend, what does opponent do next?'",
                }
    
    # Case 9: Large eval swing without clear tactical reason = positional misread
    if cp_loss > 150 and not best_move_effects["is_capture"] and not best_move_effects["is_check"]:
        # Best move was positional, user missed it
        return {
            "primary_gap": CognitiveGap.POSITIONAL_MISREAD.value,
            "confidence": 0.70,
            "evidence": f"Evaluation dropped by {cp_loss/100:.1f} pawns without obvious tactical reason",
            "explanation": "The best move was positional rather than tactical. You may have misunderstood what the position required.",
            "secondary_gaps": [],
            "coaching_focus": "In quiet positions, ask: 'What is the most important feature of this position?'",
        }
    
    # Case 10: Rushed move with significant error
    if rushed_factor and cp_loss > 100:
        return {
            "primary_gap": CognitiveGap.RUSHED_MOVE.value,
            "confidence": 0.80,
            "evidence": f"Spent only {time_spent_seconds:.1f} seconds on a move that lost {cp_loss/100:.1f} pawns",
            "explanation": "You moved too quickly. This wasn't a simple position - it deserved more thought.",
            "secondary_gaps": [],
            "coaching_focus": "On non-obvious moves, force yourself to spend at least 20 seconds",
        }
    
    # Case 11: Overconfidence (user was very sure but wrong)
    if user_confidence and user_confidence in ["very_sure", "confident"] and cp_loss > 100:
        return {
            "primary_gap": CognitiveGap.OVERCONFIDENCE.value,
            "confidence": 0.70,
            "evidence": f"Stated confidence was high but move lost {cp_loss/100:.1f} pawns",
            "explanation": "You felt confident but missed something. When you feel very sure, that's exactly when to double-check.",
            "secondary_gaps": [],
            "coaching_focus": "When confident, ask: 'What am I possibly missing here?'",
        }
    
    # Fallback: We can't determine precisely
    return {
        "primary_gap": CognitiveGap.CALCULATION_DEPTH.value,
        "confidence": 0.50,
        "evidence": f"Move lost approximately {cp_loss/100:.1f} pawns of value",
        "explanation": "The best move was better for reasons that require deeper calculation to understand.",
        "secondary_gaps": [],
        "coaching_focus": "Practice calculating 2-3 moves ahead before deciding",
    }


def get_coaching_message(gap_result: Dict) -> str:
    """Generate a coaching message based on the gap analysis."""
    gap = gap_result.get("primary_gap", "unclear")
    explanation = gap_result.get("explanation", "")
    coaching_focus = gap_result.get("coaching_focus", "")
    
    # Create concise coaching message
    messages = {
        CognitiveGap.HANGING_PIECE_BLINDNESS.value: "Piece safety check needed.",
        CognitiveGap.CHECK_BLINDNESS.value: "Always look for checks first.",
        CognitiveGap.THREAT_BLINDNESS.value: "Check opponent's threats before moving.",
        CognitiveGap.TACTICAL_OVERSIGHT.value: "Scan for captures and tactics.",
        CognitiveGap.MISSED_FORK.value: "Look for fork opportunities.",
        CognitiveGap.MISSED_PIN.value: "Check for pin possibilities.",
        CognitiveGap.DEFENSIVE_LAPSE.value: "Defense before attack.",
        CognitiveGap.CALCULATION_DEPTH.value: "Calculate one move deeper.",
        CognitiveGap.POSITIONAL_MISREAD.value: "Re-evaluate position requirements.",
        CognitiveGap.TIME_PRESSURE.value: "Time management needed.",
        CognitiveGap.RUSHED_MOVE.value: "Take more time on critical moves.",
        CognitiveGap.OVERCONFIDENCE.value: "Double-check when confident.",
    }
    
    return messages.get(gap, coaching_focus or "Review this position carefully.")



async def check_learned_pattern_rules_async(fen: str, best_move: str, played_move: str) -> Optional[Dict]:
    """
    Async function to check if any learned pattern rules match this position.
    
    This is called from async endpoints to leverage database-stored rules.
    
    Args:
        fen: Position FEN before the move
        best_move: What Stockfish recommends
        played_move: What the user played
        
    Returns:
        Dict with pattern match info, or None if no match
    """
    try:
        from services.pattern_learning.pattern_rule_extractor import PatternRuleStore
        from motor.motor_asyncio import AsyncIOMotorClient
        import os
        
        client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
        db = client[os.environ.get("DB_NAME", "test_database")]
        store = PatternRuleStore(db)
        
        matching_rules = await store.find_matching_rules(fen)
        
        if matching_rules:
            best_rule, confidence = matching_rules[0]
            
            if confidence >= 0.7:
                explanation = best_rule.explanation_template.format(
                    best_move=best_move,
                    played_move=played_move
                )
                
                gap_mapping = {
                    "KING_SAFETY_LUFT": CognitiveGap.KING_SAFETY_NEGLECT.value,
                    "KING_SAFETY": CognitiveGap.KING_SAFETY_NEGLECT.value,
                    "BACK_RANK_MATE_THREAT": CognitiveGap.BACK_RANK_BLINDNESS.value,
                    "HANGING_PIECE": CognitiveGap.HANGING_PIECE_BLINDNESS.value,
                    "PIECE_FORK": CognitiveGap.MISSED_FORK.value,
                    "PIN": CognitiveGap.MISSED_PIN.value,
                }
                
                return {
                    "primary_gap": gap_mapping.get(best_rule.pattern_name, CognitiveGap.POSITIONAL_MISREAD.value),
                    "confidence": confidence,
                    "evidence": f"Matched learned pattern: {best_rule.pattern_name}",
                    "explanation": explanation,
                    "secondary_gaps": [],
                    "coaching_focus": f"Focus on {best_rule.pattern_name.lower().replace('_', ' ')} patterns",
                    "learned_from_feedback": True,
                    "rule_id": best_rule.rule_id,
                }
        
        return None
        
    except Exception as e:
        return None
