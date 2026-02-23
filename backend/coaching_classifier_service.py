"""
Coaching Classifier Service

Core Principle: Lab surfaces HUMAN-IMPROVABLE ERRORS, not engine disagreements.

Human-improvable errors are:
1. Missed forcing tactic
2. Allowed forcing tactic  
3. Violated simple decision rule (threat-check, loose piece, king safety)
4. Repeated known personal pattern
5. No coherent plan when position demanded one

Everything else = noise.

This service classifies moves into actionable coaching categories.
"""

import chess
from typing import Dict, Optional, List, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MoveCategory(str, Enum):
    """User-facing move categories"""
    BLUNDER = "blunder"                    # Big swing / tactic missed
    TACTICAL_MISTAKE = "tactical_mistake"  # Missed/allowed forcing line
    STRATEGIC_SLIP = "strategic_slip"      # Plan/structure mistake, explainable
    ENGINE_PREFERENCE = "engine_preference"  # Don't drill, just info
    GOOD_MOVE = "good_move"                # No issue
    

class ProphlaxisType(str, Enum):
    """Classification for prophylactic moves"""
    GOOD = "good"           # Real threat, addressed, no major concession
    PHANTOM = "phantom"     # Threat wasn't real/forcing - thinking error
    WRONG = "wrong"         # Creates tactical concession


class CoachingPriority(int, Enum):
    """Priority order for Lab display"""
    FORCING_TACTIC = 1      # Missed/allowed checks, captures, threats
    REPEATED_PATTERN = 2    # User's personal "leak"
    THREAT_CHECK_FAILURE = 3  # Played without seeing opponent reply
    NO_PLAN_CRITICAL = 4    # No plan when position demanded one
    ENDGAME_TECHNIQUE = 5   # Endgame errors
    LOW_PRIORITY = 99       # Engine preference, noise


# Common prophylactic pawn moves
PROPHYLACTIC_PAWN_MOVES = {
    'h6', 'h3', 'a6', 'a3', 'g6', 'g3',  # Stopping piece jumps
    'h4', 'h5', 'a4', 'a5',  # Space grabbing / preventing
}

# Squares that prophylactic moves typically defend against
PROPHYLACTIC_TARGETS = {
    'h6': ['g5', 'f7'],  # Stops Ng5/Bg5 attacking f7
    'h3': ['g4', 'f3'],  # Stops Ng4/Bg4 
    'a6': ['b5'],        # Stops Bb5 pin or Nb5 jump
    'a3': ['b4'],        # Stops Bb4 pin or Nb4
    'g6': ['f7', 'h7'],  # Fianchetto prep or stops Qh7 ideas
    'g3': ['f4', 'h4'],  # Fianchetto prep
}


def is_prophylactic_move(move_san: str, board: chess.Board) -> bool:
    """Check if a move is likely prophylactic (defensive/preventive)."""
    # Pawn moves to typical prophylactic squares
    if move_san.lower() in PROPHYLACTIC_PAWN_MOVES:
        return True
    
    # Check if move is a pawn move that doesn't capture or advance far
    if move_san[0].islower() and 'x' not in move_san:
        # Single-square pawn moves to edge files are often prophylactic
        if move_san[0] in ['a', 'h', 'g']:
            return True
    
    return False


def detect_forcing_threats(board: chess.Board, for_color: chess.Color) -> List[Dict]:
    """
    Detect forcing threats (checks, captures, attacks on valuable pieces).
    These are what the opponent might play next.
    """
    threats = []
    
    for move in board.legal_moves:
        if board.turn != for_color:
            continue
            
        board_after = board.copy()
        board_after.push(move)
        
        move_san = board.san(move)
        threat_info = {
            'move': move_san,
            'is_check': board_after.is_check(),
            'is_capture': board.is_capture(move),
            'is_mate_threat': False,
            'attacks_queen': False,
            'attacks_rook': False,
            'forcing_level': 0
        }
        
        # Check if this threatens mate
        if board_after.is_check():
            threat_info['forcing_level'] += 3
            # Check for mate threat
            for response in board_after.legal_moves:
                test = board_after.copy()
                test.push(response)
                # After their response, can we mate?
                for followup in test.legal_moves:
                    test2 = test.copy()
                    test2.push(followup)
                    if test2.is_checkmate():
                        threat_info['is_mate_threat'] = True
                        threat_info['forcing_level'] += 5
                        break
                if threat_info['is_mate_threat']:
                    break
        
        # Check if captures valuable piece
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            if captured:
                if captured.piece_type == chess.QUEEN:
                    threat_info['forcing_level'] += 4
                elif captured.piece_type == chess.ROOK:
                    threat_info['forcing_level'] += 3
                elif captured.piece_type in [chess.BISHOP, chess.KNIGHT]:
                    threat_info['forcing_level'] += 2
        
        # Check if attacks queen/rook
        to_sq = move.to_square
        board_test = board.copy()
        board_test.push(move)
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color != for_color:
                if board_test.is_attacked_by(for_color, sq):
                    if piece.piece_type == chess.QUEEN:
                        threat_info['attacks_queen'] = True
                        threat_info['forcing_level'] += 2
                    elif piece.piece_type == chess.ROOK:
                        threat_info['attacks_rook'] = True
                        threat_info['forcing_level'] += 1
        
        if threat_info['forcing_level'] > 0:
            threats.append(threat_info)
    
    # Sort by forcing level
    threats.sort(key=lambda x: x['forcing_level'], reverse=True)
    return threats[:5]  # Top 5 threats


def verify_prophylactic_threat(
    board_before: chess.Board,
    prophylactic_move: str,
    user_color: chess.Color
) -> Dict:
    """
    Verify if a prophylactic move addresses a REAL threat.
    
    Returns:
        {
            'threat_was_real': bool,
            'threat_description': str,
            'threat_forcing_level': int (0-10, higher = more forcing),
            'prophylaxis_effective': bool
        }
    """
    opponent_color = not user_color
    
    # Get opponent's threats BEFORE the prophylactic move
    threats_before = detect_forcing_threats(board_before, opponent_color)
    
    # What squares does the prophylactic move control?
    try:
        move_obj = board_before.parse_san(prophylactic_move)
        prophylactic_square = chess.square_name(move_obj.to_square)
    except:
        return {
            'threat_was_real': False,
            'threat_description': 'Could not parse move',
            'threat_forcing_level': 0,
            'prophylaxis_effective': False
        }
    
    # Check if any threat uses the square we're defending
    blocked_threats = []
    for threat in threats_before:
        threat_move = threat['move']
        # Check if our prophylactic move blocks this threat
        # (either by controlling the square or by defending a target)
        
        # Simple check: does opponent's threat land on or pass through our defended square?
        try:
            threat_obj = board_before.parse_san(threat_move)
            threat_to = chess.square_name(threat_obj.to_square)
            
            # Check squares typically defended by this prophylactic move
            defended_squares = PROPHYLACTIC_TARGETS.get(prophylactic_move.lower(), [])
            
            if threat_to in defended_squares or threat_to == prophylactic_square:
                blocked_threats.append(threat)
        except:
            continue
    
    # Play the prophylactic move and check threats after
    board_after = board_before.copy()
    try:
        board_after.push_san(prophylactic_move)
    except:
        return {
            'threat_was_real': False,
            'threat_description': 'Invalid move',
            'threat_forcing_level': 0,
            'prophylaxis_effective': False
        }
    
    threats_after = detect_forcing_threats(board_after, opponent_color)
    
    # Did the prophylactic move reduce forcing threats?
    max_forcing_before = max([t['forcing_level'] for t in threats_before], default=0)
    max_forcing_after = max([t['forcing_level'] for t in threats_after], default=0)
    
    threat_reduced = max_forcing_after < max_forcing_before
    
    if blocked_threats:
        return {
            'threat_was_real': True,
            'threat_description': f"Blocks {blocked_threats[0]['move']}",
            'threat_forcing_level': blocked_threats[0]['forcing_level'],
            'prophylaxis_effective': True,
            'blocked_threats': [t['move'] for t in blocked_threats]
        }
    elif threat_reduced:
        return {
            'threat_was_real': True,
            'threat_description': 'Reduces opponent forcing options',
            'threat_forcing_level': max_forcing_before,
            'prophylaxis_effective': True
        }
    else:
        return {
            'threat_was_real': False,
            'threat_description': 'No immediate forcing threat detected',
            'threat_forcing_level': 0,
            'prophylaxis_effective': False
        }


def classify_prophylactic_move(
    board_before: chess.Board,
    move_san: str,
    best_move: str,
    cp_loss: int,
    user_color: chess.Color
) -> Dict:
    """
    Classify a prophylactic move into GOOD / PHANTOM / WRONG.
    
    Returns full classification with explanation.
    """
    threat_verification = verify_prophylactic_threat(board_before, move_san, user_color)
    
    # Play the move and check for immediate tactical issues
    board_after = board_before.copy()
    try:
        board_after.push_san(move_san)
    except:
        return {
            'type': ProphlaxisType.WRONG,
            'reason': 'Invalid move',
            'is_puzzle_eligible': False,
            'coaching_message': None
        }
    
    # Check if move creates tactical weakness
    creates_tactic = False
    tactical_issue = None
    
    # Check if opponent now has a strong forcing move
    opponent_threats = detect_forcing_threats(board_after, not user_color)
    if opponent_threats and opponent_threats[0]['forcing_level'] >= 4:
        creates_tactic = True
        tactical_issue = opponent_threats[0]
    
    # Classify based on threat reality and consequences
    if creates_tactic and cp_loss >= 150:
        # WRONG: Created a tactical problem
        return {
            'type': ProphlaxisType.WRONG,
            'reason': f"Creates tactical weakness: {tactical_issue['move']}",
            'is_puzzle_eligible': True,
            'coaching_message': f"This prophylactic move backfires - it allows {tactical_issue['move']}",
            'category': MoveCategory.TACTICAL_MISTAKE,
            'priority': CoachingPriority.FORCING_TACTIC
        }
    elif not threat_verification['threat_was_real']:
        # PHANTOM: Defending against nothing
        return {
            'type': ProphlaxisType.PHANTOM,
            'reason': 'Phantom threat - no immediate forcing threat existed',
            'is_puzzle_eligible': False,
            'coaching_message': "This was a phantom threat. Before defending, verify: is the threat actually forcing? What happens if I ignore it?",
            'category': MoveCategory.STRATEGIC_SLIP if cp_loss >= 50 else MoveCategory.GOOD_MOVE,
            'priority': CoachingPriority.THREAT_CHECK_FAILURE,
            'coach_rule': "Only defend forcing threats. If opponent's 'threat' can be ignored, develop instead."
        }
    elif threat_verification['threat_was_real'] and threat_verification['prophylaxis_effective']:
        if cp_loss < 100:
            # GOOD: Real threat, addressed it, small cost
            return {
                'type': ProphlaxisType.GOOD,
                'reason': f"Good practical defense against {threat_verification.get('threat_description', 'threat')}",
                'is_puzzle_eligible': False,
                'coaching_message': None,  # No coaching needed for good moves
                'category': MoveCategory.GOOD_MOVE,
                'priority': CoachingPriority.LOW_PRIORITY
            }
        else:
            # Addressed real threat but there was a better way
            return {
                'type': ProphlaxisType.GOOD,
                'reason': f"Reasonable defense, but {best_move} was more efficient",
                'is_puzzle_eligible': False,
                'coaching_message': f"Your defense was reasonable, but {best_move} handles the threat while also improving your position.",
                'category': MoveCategory.ENGINE_PREFERENCE,
                'priority': CoachingPriority.LOW_PRIORITY
            }
    else:
        # Default: engine preference
        return {
            'type': ProphlaxisType.GOOD,
            'reason': 'Reasonable prophylactic move',
            'is_puzzle_eligible': False,
            'coaching_message': None,
            'category': MoveCategory.ENGINE_PREFERENCE,
            'priority': CoachingPriority.LOW_PRIORITY
        }


def classify_move_for_coaching(
    fen_before: str,
    move_played: str,
    best_move: str,
    cp_loss: int,
    user_color: str,
    has_user_reflection: bool = False,
    user_reflection_text: str = None,
    user_pattern_history: List[str] = None
) -> Dict:
    """
    Main classification function for the coaching system.
    
    Determines:
    1. What category this move falls into
    2. Whether it should be a puzzle
    3. What coaching message to show
    4. What priority in Lab
    
    Returns comprehensive classification for UI consumption.
    """
    try:
        board = chess.Board(fen_before)
    except:
        return {
            'category': MoveCategory.ENGINE_PREFERENCE,
            'is_puzzle_eligible': False,
            'priority': CoachingPriority.LOW_PRIORITY,
            'error': 'Invalid FEN'
        }
    
    color = chess.WHITE if user_color == "white" else chess.BLACK
    
    # Step 1: Check for forced tactics (highest priority)
    tactical_classification = classify_tactical_content(board, move_played, best_move, cp_loss, color)
    
    if tactical_classification['has_forcing_tactic']:
        return {
            'category': tactical_classification['category'],
            'is_puzzle_eligible': True,
            'priority': CoachingPriority.FORCING_TACTIC,
            'coaching_message': tactical_classification['message'],
            'tactical_type': tactical_classification['tactical_type'],
            'show_in_lab': True
        }
    
    # Step 2: Check if this is a prophylactic move
    if is_prophylactic_move(move_played, board):
        prophylaxis_result = classify_prophylactic_move(board, move_played, best_move, cp_loss, color)
        
        # If user has a reflection, factor it in
        if has_user_reflection and user_reflection_text:
            prophylaxis_result = enhance_with_reflection(
                prophylaxis_result, 
                user_reflection_text,
                board,
                move_played
            )
        
        return {
            'category': prophylaxis_result['category'],
            'is_puzzle_eligible': prophylaxis_result['is_puzzle_eligible'],
            'priority': prophylaxis_result['priority'],
            'coaching_message': prophylaxis_result.get('coaching_message'),
            'prophylaxis_type': prophylaxis_result['type'],
            'coach_rule': prophylaxis_result.get('coach_rule'),
            'show_in_lab': prophylaxis_result['type'] != ProphlaxisType.GOOD,
            'reason': prophylaxis_result['reason']
        }
    
    # Step 3: Check for repeated patterns (if history available)
    if user_pattern_history:
        pattern_match = check_repeated_pattern(move_played, board, user_pattern_history)
        if pattern_match:
            return {
                'category': MoveCategory.STRATEGIC_SLIP,
                'is_puzzle_eligible': False,
                'priority': CoachingPriority.REPEATED_PATTERN,
                'coaching_message': f"You've made this type of move before: {pattern_match['pattern_name']}",
                'pattern_info': pattern_match,
                'show_in_lab': True
            }
    
    # Step 4: Apply threshold-based classification
    if cp_loss >= 150:
        # Significant loss - either tactical or strategic
        return {
            'category': MoveCategory.STRATEGIC_SLIP,
            'is_puzzle_eligible': True,
            'priority': CoachingPriority.NO_PLAN_CRITICAL,
            'coaching_message': f"This move gives up significant ground. {best_move} was stronger.",
            'show_in_lab': True
        }
    elif cp_loss >= 50:
        # Check if there's a coaching angle
        coaching_angle = find_coaching_angle(board, move_played, best_move, color)
        
        if coaching_angle:
            return {
                'category': MoveCategory.STRATEGIC_SLIP,
                'is_puzzle_eligible': False,
                'priority': coaching_angle['priority'],
                'coaching_message': coaching_angle['message'],
                'show_in_lab': True,
                'coach_rule': coaching_angle.get('rule')
            }
        else:
            # Just an engine preference
            return {
                'category': MoveCategory.ENGINE_PREFERENCE,
                'is_puzzle_eligible': False,
                'priority': CoachingPriority.LOW_PRIORITY,
                'coaching_message': None,
                'show_in_lab': False  # Hidden by default in Coach Mode
            }
    else:
        # Small loss - good move
        return {
            'category': MoveCategory.GOOD_MOVE,
            'is_puzzle_eligible': False,
            'priority': CoachingPriority.LOW_PRIORITY,
            'coaching_message': None,
            'show_in_lab': False
        }


def classify_tactical_content(
    board: chess.Board,
    move_played: str,
    best_move: str,
    cp_loss: int,
    user_color: chess.Color
) -> Dict:
    """Check if move involves forcing tactics (missed or allowed)."""
    
    # Check if best_move was a forcing tactic we missed
    missed_tactic = None
    allowed_tactic = None
    
    try:
        best_move_obj = board.parse_san(best_move)
        board_after_best = board.copy()
        board_after_best.push(best_move_obj)
        
        # Was best move a check?
        if board_after_best.is_check():
            missed_tactic = {'type': 'check', 'move': best_move}
        
        # Was best move a capture of valuable piece?
        if board.is_capture(best_move_obj):
            captured = board.piece_at(best_move_obj.to_square)
            if captured and captured.piece_type >= chess.KNIGHT:
                missed_tactic = {'type': 'capture', 'move': best_move, 'piece': captured.piece_type}
        
        # Was best move checkmate?
        if board_after_best.is_checkmate():
            missed_tactic = {'type': 'checkmate', 'move': best_move}
    except:
        pass
    
    # Check if move_played allows a forcing tactic
    try:
        move_obj = board.parse_san(move_played)
        board_after_move = board.copy()
        board_after_move.push(move_obj)
        
        opponent_threats = detect_forcing_threats(board_after_move, not user_color)
        if opponent_threats:
            strongest = opponent_threats[0]
            if strongest['forcing_level'] >= 4:
                allowed_tactic = {
                    'type': 'allows_tactic',
                    'threat': strongest['move'],
                    'is_check': strongest['is_check'],
                    'is_mate_threat': strongest.get('is_mate_threat', False)
                }
    except:
        pass
    
    # Determine category
    if missed_tactic and missed_tactic['type'] == 'checkmate':
        return {
            'has_forcing_tactic': True,
            'category': MoveCategory.BLUNDER,
            'tactical_type': 'missed_mate',
            'message': f"Missed checkmate with {best_move}!"
        }
    elif allowed_tactic and allowed_tactic.get('is_mate_threat'):
        return {
            'has_forcing_tactic': True,
            'category': MoveCategory.BLUNDER,
            'tactical_type': 'allowed_mate_threat',
            'message': f"This allows {allowed_tactic['threat']} with a mating attack"
        }
    elif missed_tactic and cp_loss >= 150:
        return {
            'has_forcing_tactic': True,
            'category': MoveCategory.TACTICAL_MISTAKE,
            'tactical_type': f"missed_{missed_tactic['type']}",
            'message': f"Missed the forcing move {best_move}"
        }
    elif allowed_tactic and cp_loss >= 150:
        return {
            'has_forcing_tactic': True,
            'category': MoveCategory.TACTICAL_MISTAKE,
            'tactical_type': 'allowed_tactic',
            'message': f"This allows the strong reply {allowed_tactic['threat']}"
        }
    
    return {'has_forcing_tactic': False}


def find_coaching_angle(
    board: chess.Board,
    move_played: str,
    best_move: str,
    user_color: chess.Color
) -> Optional[Dict]:
    """
    Find a teachable coaching angle for a 50-149cp loss move.
    
    Only returns a coaching angle if there's a clear thinking error pattern.
    """
    
    try:
        move_obj = board.parse_san(move_played)
        best_obj = board.parse_san(best_move)
    except:
        return None
    
    # Check for threat-check failure (moved without seeing opponent's reply)
    board_after = board.copy()
    board_after.push(move_obj)
    
    opponent_threats = detect_forcing_threats(board_after, not user_color)
    if opponent_threats and opponent_threats[0]['forcing_level'] >= 3:
        return {
            'priority': CoachingPriority.THREAT_CHECK_FAILURE,
            'message': f"Before this move, check what your opponent can do. They have {opponent_threats[0]['move']}.",
            'rule': "Always ask: what's my opponent's best reply?"
        }
    
    # Check for leaving piece en prise
    for sq in chess.SQUARES:
        piece = board_after.piece_at(sq)
        if piece and piece.color == user_color:
            attackers = len(board_after.attackers(not user_color, sq))
            defenders = len(board_after.attackers(user_color, sq))
            if attackers > defenders and piece.piece_type >= chess.KNIGHT:
                return {
                    'priority': CoachingPriority.THREAT_CHECK_FAILURE,
                    'message': f"This leaves your {chess.piece_name(piece.piece_type)} undefended.",
                    'rule': "Check: are all my pieces defended?"
                }
    
    # Check for king safety issues
    king_sq = board_after.king(user_color)
    if king_sq:
        attackers_on_king_zone = 0
        for delta in [-9, -8, -7, -1, 1, 7, 8, 9]:
            test_sq = king_sq + delta
            if 0 <= test_sq < 64:
                if board_after.is_attacked_by(not user_color, test_sq):
                    attackers_on_king_zone += 1
        
        if attackers_on_king_zone >= 3:
            return {
                'priority': CoachingPriority.THREAT_CHECK_FAILURE,
                'message': "This weakens your king's safety. Consider your king first.",
                'rule': "King safety comes before everything"
            }
    
    return None


def enhance_with_reflection(
    base_classification: Dict,
    reflection_text: str,
    board: chess.Board,
    move_played: str
) -> Dict:
    """
    Enhance classification with user's reflection.
    
    Validates whether user's reasoning was correct and adds intent vs reality comparison.
    """
    result = base_classification.copy()
    
    # Extract intent from reflection (simple keyword matching)
    reflection_lower = reflection_text.lower()
    
    user_intent = None
    if 'stop' in reflection_lower or 'prevent' in reflection_lower:
        user_intent = 'prophylactic'
    elif 'attack' in reflection_lower:
        user_intent = 'attacking'
    elif 'develop' in reflection_lower:
        user_intent = 'development'
    elif 'trap' in reflection_lower:
        user_intent = 'trapping'
    
    # Add reflection context
    result['user_reflection'] = reflection_text
    result['user_intent'] = user_intent
    
    # Validate intent
    if user_intent == 'prophylactic':
        threat_check = verify_prophylactic_threat(
            board, 
            move_played, 
            chess.WHITE if board.turn == chess.WHITE else chess.BLACK
        )
        
        if threat_check['threat_was_real']:
            result['intent_validation'] = 'correct'
            result['validation_message'] = f"Correct threat read - {threat_check['threat_description']}"
            # If intent was correct, reduce priority
            result['priority'] = CoachingPriority.LOW_PRIORITY
            result['show_in_lab'] = False  # Move to "Reviewed" section
        else:
            result['intent_validation'] = 'misread'
            result['validation_message'] = "Threat misread - the threat wasn't actually forcing"
            result['coach_rule'] = "Before defending, verify: can I actually ignore this threat?"
    
    return result


def check_repeated_pattern(
    move_played: str,
    board: chess.Board,
    pattern_history: List[str]
) -> Optional[Dict]:
    """Check if this move matches a known repeated pattern for this user."""
    
    # Simple pattern matching (would be more sophisticated in production)
    # Patterns like: "early queen moves", "neglecting development", "weakening king"
    
    # For now, just check if similar move types appear in history
    move_type = categorize_move_type(move_played, board)
    
    pattern_counts = {}
    for hist_pattern in pattern_history:
        pattern_counts[hist_pattern] = pattern_counts.get(hist_pattern, 0) + 1
    
    if move_type in pattern_counts and pattern_counts[move_type] >= 2:
        return {
            'pattern_name': move_type,
            'occurrence_count': pattern_counts[move_type] + 1,
            'is_repeated': True
        }
    
    return None


def categorize_move_type(move_san: str, board: chess.Board) -> str:
    """Categorize a move into a pattern type."""
    
    # Queen moves in opening
    if move_san[0] == 'Q' and len(list(board.move_stack)) < 10:
        return 'early_queen_move'
    
    # King moves before castling (and not forced)
    if move_san[0] == 'K' and board.has_castling_rights(board.turn):
        return 'king_move_before_castling'
    
    # Pawn pushes that weaken king
    if move_san in ['g3', 'g4', 'g6', 'h3', 'h4', 'h6', 'f3', 'f4', 'f6']:
        return 'weakening_pawn_move'
    
    return 'general'


# ============================================================
# PUBLIC API - These functions are called from server.py
# ============================================================

async def get_move_coaching_classification(
    db,
    user_id: str,
    fen_before: str,
    move_played: str,
    best_move: str,
    cp_loss: int,
    user_color: str
) -> Dict:
    """
    Main entry point for coaching classification.
    Called when analyzing a move to determine what to show in Lab.
    """
    
    # Check for user reflection on this move
    has_reflection = False
    reflection_text = None
    
    # TODO: Query reflections collection for this move
    # reflection = await db.reflections.find_one({
    #     'user_id': user_id,
    #     'fen': fen_before,
    #     'move': move_played
    # })
    # if reflection:
    #     has_reflection = True
    #     reflection_text = reflection.get('text', '')
    
    # Get user's pattern history
    # TODO: Query user's pattern history
    pattern_history = []
    
    classification = classify_move_for_coaching(
        fen_before=fen_before,
        move_played=move_played,
        best_move=best_move,
        cp_loss=cp_loss,
        user_color=user_color,
        has_user_reflection=has_reflection,
        user_reflection_text=reflection_text,
        user_pattern_history=pattern_history
    )
    
    return classification


def should_create_puzzle(classification: Dict) -> bool:
    """Determine if this move should become a puzzle/drill."""
    return classification.get('is_puzzle_eligible', False)


def should_show_in_lab(classification: Dict, coach_mode: bool = True) -> bool:
    """Determine if this move should appear in Lab view."""
    if coach_mode:
        return classification.get('show_in_lab', False)
    else:
        # Engine mode - show everything with cp_loss >= 50
        return True
