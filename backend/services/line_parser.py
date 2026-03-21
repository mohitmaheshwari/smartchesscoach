"""
Stockfish Line Parser & Explainer

Parses actual PV lines from Stockfish and converts them to human-readable explanations.
NO LLM - pure chess logic and rule mapping.

Flow:
1. Check theory database for known patterns (opening/endgame theory)
2. If no theory match, parse the PV line
3. Detect what's happening (captures, checks, threats, material changes)
4. Map the pattern to a golden rule
5. Generate clear, SHORT English explanation
"""

import chess
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# GOLDEN RULES - Patterns mapped to memorable rules
# =============================================================================

GOLDEN_RULES = {
    # Material loss patterns
    "loses_pawn": {
        "rule": "Don't give away pawns without compensation.",
        "short": "You lost a pawn."
    },
    "loses_piece": {
        "rule": "Never leave pieces undefended.",
        "short": "You lost a piece."
    },
    "loses_exchange": {
        "rule": "Don't trade a rook for a minor piece.",
        "short": "You lost the exchange (rook for bishop/knight)."
    },
    "loses_queen": {
        "rule": "Protect your queen at all costs.",
        "short": "You lost your queen."
    },
    
    # Tactical patterns
    "allows_fork": {
        "rule": "Watch for knight forks on your king and queen.",
        "short": "This allowed a fork."
    },
    "allows_pin": {
        "rule": "Avoid placing pieces on lines with your king.",
        "short": "This created a pin."
    },
    "allows_skewer": {
        "rule": "Keep your valuable pieces off the same line.",
        "short": "This allowed a skewer."
    },
    "allows_discovered_attack": {
        "rule": "Watch for pieces that can move to reveal attacks.",
        "short": "This allowed a discovered attack."
    },
    "misses_check": {
        "rule": "Always look for checks first - they force responses.",
        "short": "You missed a check that wins material."
    },
    "allows_back_rank": {
        "rule": "Give your king an escape square (luft).",
        "short": "This weakened your back rank."
    },
    
    # Positional patterns  
    "loses_center": {
        "rule": "Control the center - don't give it up easily.",
        "short": "You gave up central control."
    },
    "weakens_king": {
        "rule": "Don't push pawns in front of your castled king.",
        "short": "This weakened your king's safety."
    },
    "trades_when_behind": {
        "rule": "When behind in material, avoid trades.",
        "short": "Trading when behind helps your opponent."
    },
    "trades_when_ahead": {
        "rule": "When ahead in material, trade pieces to simplify.",
        "short": "You should trade pieces when ahead."
    },
    
    # Opening patterns
    "premature_pawn_push": {
        "rule": "Don't push pawns past the 4th rank before developing.",
        "short": "This pawn push was premature."
    },
    "undeveloped_pieces": {
        "rule": "Develop all pieces before attacking.",
        "short": "You attacked with pieces still undeveloped."
    },
    "moved_same_piece_twice": {
        "rule": "Don't move the same piece twice in the opening.",
        "short": "Moving the same piece twice loses time."
    },
    "delayed_castling": {
        "rule": "Castle early to protect your king.",
        "short": "Your king is still in the center."
    },
    
    # Opening theory patterns
    "italian_d5_premature": {
        "rule": "In the Italian/Two Knights, d5 is only good after Ng5. Play d6 first.",
        "short": "d5 is premature - d6 is the main line."
    },
    "sicilian_d6_first": {
        "rule": "In the Sicilian, play d6 to support your center before d5.",
        "short": "Prepare d5 with d6 first."
    },
    "french_attack_chain": {
        "rule": "In the French, attack the pawn chain base with c5.",
        "short": "Attack the pawn chain with c5."
    },
    
    # Generic fallback
    "unknown": {
        "rule": "Calculate your opponent's best response before moving.",
        "short": "This move has a tactical flaw."
    }
}


# Piece values for material calculation
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0  # King can't be captured
}


@dataclass
class MoveEvent:
    """Represents what happened in a single move."""
    move_san: str
    move_uci: str
    is_capture: bool
    captured_piece: Optional[str]  # "pawn", "knight", etc.
    captured_value: int
    is_check: bool
    is_checkmate: bool
    piece_moved: str  # "pawn", "knight", etc.
    from_square: str
    to_square: str


@dataclass 
class LineAnalysis:
    """Analysis of a full PV line."""
    events: List[MoveEvent]
    material_change: int  # Positive = good for side that played the line
    has_checkmate: bool
    key_moment: Optional[str]  # Description of the critical event
    pattern: str  # Key from GOLDEN_RULES
    

def parse_move(board: chess.Board, move: chess.Move) -> MoveEvent:
    """Parse a single move and extract what happened."""
    # Get piece being moved
    piece = board.piece_at(move.from_square)
    piece_name = chess.piece_name(piece.piece_type) if piece else "piece"
    
    # Check if capture
    is_capture = board.is_capture(move)
    captured_piece = None
    captured_value = 0
    
    if is_capture:
        # Check for en passant
        if board.is_en_passant(move):
            captured_piece = "pawn"
            captured_value = 1
        else:
            captured = board.piece_at(move.to_square)
            if captured:
                captured_piece = chess.piece_name(captured.piece_type)
                captured_value = PIECE_VALUES.get(captured.piece_type, 0)
    
    # Make move to check for check/checkmate
    board_copy = board.copy()
    board_copy.push(move)
    is_check = board_copy.is_check()
    is_checkmate = board_copy.is_checkmate()
    
    return MoveEvent(
        move_san=board.san(move),
        move_uci=move.uci(),
        is_capture=is_capture,
        captured_piece=captured_piece,
        captured_value=captured_value,
        is_check=is_check,
        is_checkmate=is_checkmate,
        piece_moved=piece_name,
        from_square=chess.square_name(move.from_square),
        to_square=chess.square_name(move.to_square)
    )


def parse_pv_line(fen: str, moves: List[str]) -> LineAnalysis:
    """
    Parse a PV line and analyze what happens.
    
    Args:
        fen: Starting position
        moves: List of moves in SAN or UCI notation
    
    Returns:
        LineAnalysis with events and detected pattern
    """
    board = chess.Board(fen)
    events = []
    material_balance = 0  # Track from perspective of side to move at start
    starting_color = board.turn
    
    for move_str in moves:
        try:
            # Try to parse as SAN first, then UCI
            try:
                move = board.parse_san(move_str)
            except ValueError:
                move = chess.Move.from_uci(move_str)
            
            if move not in board.legal_moves:
                break
                
            event = parse_move(board, move)
            events.append(event)
            
            # Track material from starting side's perspective
            if event.is_capture:
                if board.turn == starting_color:
                    material_balance += event.captured_value
                else:
                    material_balance -= event.captured_value
            
            board.push(move)
            
            if event.is_checkmate:
                break
                
        except (ValueError, chess.InvalidMoveError) as e:
            logger.warning(f"Could not parse move {move_str}: {e}")
            break
    
    # Detect the pattern
    pattern = detect_pattern(events, material_balance)
    key_moment = find_key_moment(events)
    
    return LineAnalysis(
        events=events,
        material_change=material_balance,
        has_checkmate=any(e.is_checkmate for e in events),
        key_moment=key_moment,
        pattern=pattern
    )


def detect_pattern(events: List[MoveEvent], material_change: int) -> str:
    """Detect the main pattern from the line analysis."""
    if not events:
        return "unknown"
    
    # Check for checkmate
    if any(e.is_checkmate for e in events):
        return "allows_checkmate"
    
    # Check what the FIRST move does (opponent's response)
    first_event = events[0]
    
    # If opponent captures immediately, that's the key issue
    if first_event.is_capture:
        if first_event.captured_piece == "pawn":
            return "loses_pawn"
        elif first_event.captured_piece in ["knight", "bishop"]:
            return "loses_piece"
        elif first_event.captured_piece == "rook":
            return "loses_piece"  # Rook loss is significant
        elif first_event.captured_piece == "queen":
            return "loses_queen"
    
    # Check total material loss from the line
    total_lost = sum(e.captured_value for i, e in enumerate(events) if i % 2 == 0 and e.is_capture)
    total_gained = sum(e.captured_value for i, e in enumerate(events) if i % 2 == 1 and e.is_capture)
    net_loss = total_lost - total_gained
    
    if net_loss >= 9:
        return "loses_queen"
    elif net_loss >= 3:
        return "loses_piece"
    elif net_loss >= 1:
        return "loses_pawn"
    
    # Check if first move is check (often leads to trouble)
    if first_event.is_check:
        return "misses_check"
    
    # Default - there's some tactical issue we couldn't categorize
    return "unknown"


def find_key_moment(events: List[MoveEvent]) -> Optional[str]:
    """Find the key moment that caused the problem."""
    if not events:
        return None
    
    # First opponent response (index 0 is opponent's reply)
    if events:
        first = events[0]
        if first.is_capture:
            return f"{first.move_san} captures your {first.captured_piece}"
        elif first.is_check:
            return f"{first.move_san} gives check"
    
    # Look for the first significant capture
    for i, event in enumerate(events):
        if event.is_capture and event.captured_value >= 3:
            whose = "Opponent" if i % 2 == 0 else "You"
            return f"{whose} plays {event.move_san}, winning the {event.captured_piece}"
    
    return None


# =============================================================================
# OPENING DETECTION - Known opening patterns for better rules
# =============================================================================

OPENING_PATTERNS = {
    # Italian Game / Two Knights - d5 vs d6
    "italian_d5": {
        "fen_pattern": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R",  # After 1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6
        "bad_move": "d5",
        "good_move": "d6",
        "pattern": "italian_d5_premature",
        "explanation_prefix": "In the Two Knights Defense, d5 is premature when White hasn't played Ng5. "
    },
}


def detect_opening_pattern(fen: str, played_move: str, best_move: str) -> Optional[Dict]:
    """
    Check if this position matches a known opening pattern.
    Returns the pattern info if found, None otherwise.
    """
    # Extract board position (ignore move counters)
    board_fen = fen.split()[0] if " " in fen else fen
    
    for name, pattern in OPENING_PATTERNS.items():
        pattern_board = pattern["fen_pattern"].split()[0]
        
        # Check if position matches and moves match
        if (board_fen == pattern_board and 
            played_move.lower().replace("+", "").replace("#", "") == pattern["bad_move"].lower() and
            best_move.lower().replace("+", "").replace("#", "") == pattern["good_move"].lower()):
            return pattern
    
    return None


def explain_line(
    fen_before: str,
    played_move: str,
    played_move_uci: str,
    best_move: str,
    best_move_uci: str,
    pv_after_played: List[str],
    pv_after_best: List[str],
    eval_loss: int  # centipawns
) -> Dict[str, Any]:
    """
    Generate explanation by parsing the actual Stockfish lines.
    
    Priority:
    1. Check theory database for known opening/endgame patterns
    2. Fall back to hardcoded opening patterns
    3. Parse PV lines and generate explanation
    
    Returns:
        {
            "headline": "Short title",
            "explanation": "What happens in the line",
            "rule": "Golden rule to remember",
            "arrows": [[from, to, color], ...],
            "category": "tactical" | "positional" | "opening",
            "theory_match": bool  # Whether this matched a theory pattern
        }
    """
    # 1. Check theory database first (admin-editable JSON)
    try:
        from services.chess_theory_service import get_theory_service
        theory_service = get_theory_service()
        
        # Try to match opening theory
        theory_match = theory_service.match_opening_theory(
            fen_before, 
            played_move or played_move_uci, 
            best_move or best_move_uci
        )
        
        if theory_match:
            # Build arrows
            arrows = []
            if best_move_uci and len(best_move_uci) >= 4:
                arrows.append([best_move_uci[:2], best_move_uci[2:4], "green"])
            
            return {
                "headline": theory_match.get("name", "Opening Theory"),
                "explanation": theory_match.get("explanation", ""),
                "rule": theory_match.get("rule", ""),
                "arrows": arrows,
                "category": theory_match.get("category", "opening"),
                "theory_match": True,
                "why_bad": theory_match.get("why_bad"),
                "why_good": theory_match.get("why_good")
            }
        
        # Try to match endgame theory
        endgame_match = theory_service.match_endgame_theory(fen_before)
        if endgame_match:
            arrows = []
            if best_move_uci and len(best_move_uci) >= 4:
                arrows.append([best_move_uci[:2], best_move_uci[2:4], "green"])
            
            return {
                "headline": endgame_match.get("name", "Endgame Theory"),
                "explanation": endgame_match.get("explanation", ""),
                "rule": endgame_match.get("rule", "") or endgame_match.get("key_rule", ""),
                "arrows": arrows,
                "category": "endgame",
                "theory_match": True,
                "common_mistake": endgame_match.get("common_mistake"),
                "correct_technique": endgame_match.get("correct_technique")
            }
    except Exception as e:
        logger.warning(f"Theory service error: {e}")
    
    # 2. Check hardcoded opening patterns (legacy fallback)
    opening_pattern = detect_opening_pattern(fen_before, played_move or played_move_uci, best_move or best_move_uci)
    
    # 3. Parse the PV lines
    board = chess.Board(fen_before)
    
    # First, make the played move to get the position after
    try:
        played = board.parse_san(played_move) if played_move else chess.Move.from_uci(played_move_uci)
    except (ValueError, chess.InvalidMoveError):
        try:
            played = chess.Move.from_uci(played_move_uci)
        except (ValueError, chess.InvalidMoveError):
            return _fallback(played_move or played_move_uci, best_move or best_move_uci, eval_loss)
    
    # Get FEN after played move
    board_after_played = board.copy()
    board_after_played.push(played)
    fen_after_played = board_after_played.fen()
    
    # Parse the continuation after played move
    played_analysis = parse_pv_line(fen_after_played, pv_after_played)
    
    # Parse the continuation after best move
    try:
        best = board.parse_san(best_move) if best_move else chess.Move.from_uci(best_move_uci)
        board_after_best = board.copy()
        board_after_best.push(best)
        fen_after_best = board_after_best.fen()
        best_analysis = parse_pv_line(fen_after_best, pv_after_best)
    except (ValueError, chess.InvalidMoveError):
        best_analysis = None
    
    # Generate explanation from parsed data
    return generate_explanation(
        played_move=played_move or played_move_uci,
        best_move=best_move or best_move_uci,
        best_move_uci=best_move_uci,
        played_analysis=played_analysis,
        best_analysis=best_analysis,
        eval_loss=eval_loss,
        opening_pattern=opening_pattern
    )


def generate_explanation(
    played_move: str,
    best_move: str,
    best_move_uci: str,
    played_analysis: LineAnalysis,
    best_analysis: Optional[LineAnalysis],
    eval_loss: int,
    opening_pattern: Optional[Dict] = None
) -> Dict[str, Any]:
    """Generate the final explanation from parsed analysis."""
    
    # If we have a known opening pattern, use its rule
    if opening_pattern:
        pattern = opening_pattern["pattern"]
        rule_data = GOLDEN_RULES.get(pattern, GOLDEN_RULES["unknown"])
        explanation_prefix = opening_pattern.get("explanation_prefix", "")
    else:
        pattern = played_analysis.pattern
        rule_data = GOLDEN_RULES.get(pattern, GOLDEN_RULES["unknown"])
        explanation_prefix = ""
    
    # Build the explanation from actual events
    explanation_parts = []
    
    # Add opening theory prefix if available
    if explanation_prefix:
        explanation_parts.append(explanation_prefix)
    
    # Describe what happens in the line - trace the key moves
    if played_analysis.events:
        # Build a narrative of what happens
        moves_narrative = []
        for i, event in enumerate(played_analysis.events[:4]):  # First 4 moves max
            if event.is_capture:
                whose = "White" if i % 2 == 0 else "Black"
                moves_narrative.append(f"{event.move_san} ({whose} takes {event.captured_piece})")
            elif event.is_check:
                moves_narrative.append(f"{event.move_san}+")
            else:
                moves_narrative.append(event.move_san)
        
        if moves_narrative:
            explanation_parts.append(f"After {played_move}, the line goes: {', '.join(moves_narrative)}.")
        
        # Summarize the result
        total_lost_by_player = sum(e.captured_value for i, e in enumerate(played_analysis.events) if i % 2 == 0 and e.is_capture)
        total_recaptured = sum(e.captured_value for i, e in enumerate(played_analysis.events) if i % 2 == 1 and e.is_capture)
        net_loss = total_lost_by_player - total_recaptured
        
        if net_loss >= 1:
            if net_loss == 1:
                explanation_parts.append("You end up down a pawn.")
            elif net_loss >= 3:
                explanation_parts.append("You end up losing a piece.")
    
    # Describe why best move is better
    if best_move:
        explanation_parts.append(f"{best_move} avoids this and keeps your position solid.")
    
    # Build headline - use opening pattern headline if available
    if opening_pattern:
        headline = rule_data["short"]
    elif played_analysis.key_moment:
        headline = played_analysis.key_moment
    else:
        headline = rule_data["short"]
    
    # Determine category
    category = "tactical"
    if opening_pattern or pattern.startswith("italian_") or pattern.startswith("sicilian_") or pattern.startswith("french_"):
        category = "opening"
    elif pattern in ["loses_center", "weakens_king", "premature_pawn_push", "undeveloped_pieces"]:
        category = "positional"
    elif pattern in ["premature_pawn_push", "undeveloped_pieces", "moved_same_piece_twice", "delayed_castling"]:
        category = "opening"
    
    # Build arrows - show best move in green
    arrows = []
    if best_move_uci and len(best_move_uci) >= 4:
        arrows.append([best_move_uci[:2], best_move_uci[2:4], "green"])
    
    return {
        "headline": headline[:50],  # Cap length
        "explanation": " ".join(explanation_parts) if explanation_parts else f"Playing {played_move} loses about {eval_loss // 100} pawns. {best_move} was better.",
        "rule": rule_data["rule"],
        "arrows": arrows,
        "category": category
    }


def _fallback(played_move: str, best_move: str, eval_loss: int) -> Dict[str, Any]:
    """Fallback when parsing fails."""
    return {
        "headline": "A better move was available",
        "explanation": f"Playing {played_move} instead of {best_move} cost about {eval_loss // 100} pawns.",
        "rule": "Calculate your opponent's best response before moving.",
        "arrows": [],
        "category": "tactical"
    }
