"""
Game Decryption V5 Service - "Thinking Simulator"
==================================================

Vision: Teach HOW to think, not just WHAT to play.

Key Principles:
1. EVERY move gets coaching (user + opponent)
2. Plans > Moves (transferable knowledge)
3. LLM = Language translator ONLY (all logic from existing layers)
4. Smart theory (track what user has understood)
5. Simple language (1200-friendly)

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│  1. STOCKFISH LAYER - Get eval, best move, PV (the future)     │
├─────────────────────────────────────────────────────────────────┤
│  2. LOGIC LAYER - Existing services                            │
│     - chess_theory_service → opening/endgame/tactical match    │
│     - line_parser → PV analysis, pattern detection             │
│     - thinking_coach → principle-based feedback                │
│     - coaching_answer → thinking pattern detection             │
├─────────────────────────────────────────────────────────────────┤
│  3. PLAN EXTRACTION - Turn PV into a PLAN (not just moves)     │
├─────────────────────────────────────────────────────────────────┤
│  4. MEMORY CHECK - Has user seen this concept? Acknowledged?   │
├─────────────────────────────────────────────────────────────────┤
│  5. LANGUAGE LAYER - LLM for key moments, templates for rest   │
└─────────────────────────────────────────────────────────────────┘
"""

import chess
import chess.pgn
import json
import os
import io
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Load theory data
THEORY_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "theory")
COACHING_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "coaching")


def _load_json_safe(filepath: str) -> dict:
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
            data.pop("_meta", None)
            return data
    except Exception as e:
        logger.warning(f"Could not load {filepath}: {e}")
        return {}


# Cache for theory data
_THEORY_CACHE = {}

def get_theory_data(key: str) -> dict:
    global _THEORY_CACHE
    if key not in _THEORY_CACHE:
        if key == "endgame_principles":
            _THEORY_CACHE[key] = _load_json_safe(os.path.join(THEORY_DIR, "endgame_principles.json"))
        elif key == "opening_mistakes":
            _THEORY_CACHE[key] = _load_json_safe(os.path.join(THEORY_DIR, "opening_mistakes.json"))
        elif key == "tactical_patterns":
            _THEORY_CACHE[key] = _load_json_safe(os.path.join(THEORY_DIR, "tactical_patterns.json"))
        elif key == "positional_rules":
            _THEORY_CACHE[key] = _load_json_safe(os.path.join(THEORY_DIR, "positional_rules.json"))
        elif key == "opening_plans":
            _THEORY_CACHE[key] = _load_json_safe(os.path.join(COACHING_DIR, "opening_plans.json"))
    return _THEORY_CACHE.get(key, {})


# ─── DATA CLASSES ───────────────────────────────────────────────────

@dataclass
class ChessPlan:
    """A transferable chess plan (not just moves)."""
    goal: str                    # What we're trying to achieve
    current_problem: str         # Why current move doesn't achieve it
    consequence: str             # What happens after (the future)
    better_approach: str         # What to do instead
    transferable_learning: str   # The concept that applies to many games
    concept_id: str              # Unique ID for tracking acknowledgment
    concept_type: str            # "opening" | "endgame" | "tactical" | "positional"


@dataclass
class MoveCoaching:
    """Complete coaching for a single move."""
    # Identification
    move_number: int
    move_san: str
    is_user_move: bool
    is_white: bool
    fen_before: str
    fen_after: str
    phase: str  # opening/middlegame/endgame
    
    # Evaluation
    cp_loss: int
    eval_before: Optional[int]
    eval_after: Optional[int]
    best_move_san: Optional[str]
    severity: str  # good/inaccuracy/mistake/blunder/context
    
    # The Coaching (V5)
    narrative: str              # Simple, 1200-friendly explanation
    plan: Optional[ChessPlan]   # The transferable plan
    
    # For clickable UI
    future_moves: List[str]     # PV moves to show on board
    highlight_squares: List[str]  # Key squares to highlight
    
    # Theory connection
    theory_match: Optional[Dict]  # Matched theory pattern
    needs_acknowledgment: bool    # Show "I understand" button
    already_acknowledged: bool    # User already knows this
    acknowledgment_prompt: Optional[str]  # Message about understanding
    
    # For opponent moves
    your_plan_now: Optional[str]  # What user should do after this
    
    # Tracking
    is_best_move: bool           # Did user play the best move?
    concept_applied: Optional[str]  # What concept user demonstrated


# ─── PHASE DETECTION ─────────────────────────────────────────────────

def detect_phase(board: chess.Board, move_number: int) -> str:
    """Detect game phase based on material and move number."""
    piece_count = len(board.piece_map())
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    
    if move_number <= 10 and piece_count >= 28:
        return "opening"
    if move_number <= 15 and piece_count >= 24:
        return "opening"
    if queens == 0 or piece_count <= 12:
        return "endgame"
    if piece_count <= 18:
        return "endgame"
    return "middlegame"


def get_piece_name(piece: chess.Piece) -> str:
    names = {
        chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
        chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"
    }
    return names.get(piece.piece_type, "piece")


# ─── OPENING DETECTION ───────────────────────────────────────────────

def detect_opening_from_pgn(pgn: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract opening name and ECO code from PGN headers."""
    opening_name = None
    eco_code = None
    
    eco_match = re.search(r'\[ECO\s+"([^"]+)"\]', pgn)
    if eco_match:
        eco_code = eco_match.group(1)
    
    opening_match = re.search(r'\[Opening\s+"([^"]+)"\]', pgn)
    if opening_match:
        opening_name = opening_match.group(1)
    
    if not opening_name:
        eco_url_match = re.search(r'\[ECOUrl\s+"[^"]*openings/([^"]+)"\]', pgn)
        if eco_url_match:
            opening_name = eco_url_match.group(1).replace("-", " ").title()
    
    return opening_name, eco_code


def get_opening_data(eco_code: Optional[str], opening_name: Optional[str]) -> dict:
    """Get opening-specific plans and ideas."""
    opening_plans = get_theory_data("opening_plans")
    if not opening_plans:
        return opening_plans.get("default", {})
    
    # Match by ECO code
    if eco_code:
        eco_prefix = eco_code[:2] if len(eco_code) >= 2 else eco_code
        for key, data in opening_plans.items():
            if key.startswith("_"):
                continue
            prefixes = data.get("eco_prefix", [])
            if eco_code in prefixes or eco_prefix in [p[:2] for p in prefixes]:
                return data
    
    # Match by name
    if opening_name:
        name_lower = opening_name.lower()
        for key, data in opening_plans.items():
            if key.startswith("_"):
                continue
            if key.replace("_", " ") in name_lower or data.get("name", "").lower() in name_lower:
                return data
    
    return opening_plans.get("default", {})


# ─── PLAN EXTRACTION ─────────────────────────────────────────────────

def extract_plan_from_pv(
    board: chess.Board,
    played_move: chess.Move,
    best_move: Optional[str],
    pv_after_played: List[str],
    pv_after_best: List[str],
    phase: str,
    opening_data: dict,
    cp_loss: int,
    eco_code: Optional[str] = None
) -> Optional[ChessPlan]:
    """
    Extract a PLAN from the Stockfish PV (not just moves).
    
    This is the core innovation of V5 - turning engine analysis into
    transferable chess understanding.
    """
    if cp_loss < 30:
        return None  # Good moves don't need a plan explanation
    
    played_san = board.san(played_move)
    
    # Try opening theory tree first (more comprehensive)
    try:
        from services.opening_theory_tree_service import get_mistake_from_theory
        
        theory_mistake = get_mistake_from_theory(eco_code, played_san, board.fen())
        if theory_mistake:
            return ChessPlan(
                goal="Follow opening principles",
                current_problem=theory_mistake.get("why_bad", f"{played_san} is a theoretical mistake"),
                consequence=theory_mistake.get("consequence", _describe_consequence(pv_after_played, board)),
                better_approach=f"{theory_mistake.get('better_move', best_move)} is better" if theory_mistake.get('better_move') else (f"{best_move} was better" if best_move else ""),
                transferable_learning=theory_mistake.get("learning", ""),
                concept_id=f"theory_{theory_mistake.get('position_name', 'unknown').lower().replace(' ', '_').replace(':', '_')}",
                concept_type="opening"
            )
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Theory tree lookup failed: {e}")
    
    # Try to match opening theory from legacy data
    opening_mistakes = get_theory_data("opening_mistakes")
    for pattern_id, pattern in opening_mistakes.items():
        if not isinstance(pattern, dict) or not pattern.get("fen_pattern"):
            continue
        
        try:
            pattern_board = chess.Board(pattern["fen_pattern"])
            if board.board_fen() == pattern_board.board_fen():
                bad_move = pattern.get("bad_move", "").lower().replace("+", "").replace("#", "")
                if played_san.lower().replace("+", "").replace("#", "") == bad_move:
                    return ChessPlan(
                        goal="Control the center and develop safely",
                        current_problem=pattern.get("why_bad", f"{played_san} is premature here"),
                        consequence=_describe_consequence(pv_after_played, board),
                        better_approach=f"{pattern.get('good_move', best_move)} — {pattern.get('why_good', 'keeps the position solid')}",
                        transferable_learning=pattern.get("rule", ""),
                        concept_id=pattern_id,
                        concept_type="opening"
                    )
        except Exception:
            continue
    
    # Try endgame principles
    if phase == "endgame":
        endgame_plan = _match_endgame_principle(board, played_move, best_move, pv_after_played)
        if endgame_plan:
            return endgame_plan
    
    # Try tactical patterns
    tactical_plan = _detect_tactical_issue(board, played_move, pv_after_played, cp_loss)
    if tactical_plan:
        return tactical_plan
    
    # Generic positional plan
    return _generate_generic_plan(board, played_move, best_move, pv_after_played, pv_after_best, cp_loss)


def _describe_consequence(pv: List[str], board: chess.Board) -> str:
    """Describe what happens in the PV in simple terms."""
    if not pv:
        return "The position becomes worse"
    
    # Play through the line and describe key events
    sim = board.copy()
    events = []
    
    for i, san in enumerate(pv[:4]):
        try:
            move = sim.parse_san(san)
            if sim.is_capture(move):
                captured = sim.piece_at(move.to_square)
                if captured:
                    events.append(f"loses the {get_piece_name(captured)}")
            if sim.gives_check(move):
                events.append("check")
            sim.push(move)
        except Exception:
            break
    
    if events:
        return f"After {' '.join(pv[:3])}, you {events[0]}"
    return f"After {' '.join(pv[:2])}, your position weakens"


def _match_endgame_principle(
    board: chess.Board,
    played_move: chess.Move,
    best_move: Optional[str],
    pv: List[str]
) -> Optional[ChessPlan]:
    """Match position to endgame principles."""
    endgame_principles = get_theory_data("endgame_principles")
    
    # Count material to classify endgame type
    pieces = {}
    for color_name, color in [("white", chess.WHITE), ("black", chess.BLACK)]:
        for piece_name, piece_type in [("Q", chess.QUEEN), ("R", chess.ROOK), ("B", chess.BISHOP), ("N", chess.KNIGHT), ("P", chess.PAWN)]:
            pieces[f"{color_name}_{piece_name}"] = len(board.pieces(piece_type, color))
    
    total = sum(v for k, v in pieces.items())
    has_rook = (pieces["white_R"] + pieces["black_R"]) > 0
    has_pawn = (pieces["white_P"] + pieces["black_P"]) > 0
    
    # Rook endgame
    if has_rook and total <= 6:
        for key, principle in endgame_principles.items():
            if principle.get("pattern_type") == "rook_endgame":
                return ChessPlan(
                    goal=principle.get("key_rule", "Activate your rook"),
                    current_problem=principle.get("common_mistake", "Passive play"),
                    consequence=_describe_consequence(pv, board),
                    better_approach=principle.get("correct_technique", ""),
                    transferable_learning=principle.get("rule", ""),
                    concept_id=key,
                    concept_type="endgame"
                )
    
    # King and pawn
    if has_pawn and total <= 3:
        for key, principle in endgame_principles.items():
            if principle.get("pattern_type") == "KP_vs_K":
                return ChessPlan(
                    goal=principle.get("key_rule", "Get your king in front of the pawn"),
                    current_problem=principle.get("common_mistake", "Pushing the pawn too early"),
                    consequence=_describe_consequence(pv, board),
                    better_approach=principle.get("correct_technique", ""),
                    transferable_learning=principle.get("rule", ""),
                    concept_id=key,
                    concept_type="endgame"
                )
    
    return None


def _detect_tactical_issue(
    board: chess.Board,
    played_move: chess.Move,
    pv: List[str],
    cp_loss: int
) -> Optional[ChessPlan]:
    """Detect if the move allows a tactical pattern."""
    if cp_loss < 100:
        return None
    
    tactical_patterns = get_theory_data("tactical_patterns")
    
    # Play the move and check opponent's response
    sim = board.copy()
    sim.push(played_move)
    
    if pv:
        try:
            opp_response = sim.parse_san(pv[0])
            
            # Check for fork
            if sim.piece_at(opp_response.from_square):
                if sim.piece_at(opp_response.from_square).piece_type == chess.KNIGHT:
                    # Check if knight attacks multiple pieces after moving
                    sim2 = sim.copy()
                    sim2.push(opp_response)
                    attacked = []
                    for sq in chess.SQUARES:
                        if sim2.is_attacked_by(not board.turn, sq):
                            piece = sim2.piece_at(sq)
                            if piece and piece.color == board.turn:
                                attacked.append(get_piece_name(piece))
                    if len(attacked) >= 2 and "king" in attacked:
                        pattern = tactical_patterns.get("knight_fork", {})
                        return ChessPlan(
                            goal="Avoid tactical vulnerabilities",
                            current_problem=f"This allows a knight fork on your king and {attacked[1] if attacked[1] != 'king' else attacked[0]}",
                            consequence=f"After {pv[0]}, your opponent forks and wins material",
                            better_approach="Keep your king and queen on different color squares",
                            transferable_learning=pattern.get("rule", "Watch for knight fork squares"),
                            concept_id="knight_fork",
                            concept_type="tactical"
                        )
            
            # Check for back rank issues
            if sim.is_check():
                king_sq = sim.king(board.turn)
                if king_sq and chess.square_rank(king_sq) in [0, 7]:
                    pattern = tactical_patterns.get("back_rank_weakness", {})
                    return ChessPlan(
                        goal="Keep your king safe",
                        current_problem="This weakens your back rank",
                        consequence=f"After {pv[0]}, you face back rank threats",
                        better_approach="Give your king an escape square (h3 or g3)",
                        transferable_learning=pattern.get("rule", "Give your king luft before it's too late"),
                        concept_id="back_rank_weakness",
                        concept_type="tactical"
                    )
        except Exception:
            pass
    
    return None


def _generate_generic_plan(
    board: chess.Board,
    played_move: chess.Move,
    best_move: Optional[str],
    pv_after_played: List[str],
    pv_after_best: List[str],
    cp_loss: int
) -> ChessPlan:
    """Generate a generic plan when no specific pattern matches."""
    played_san = board.san(played_move)
    piece = board.piece_at(played_move.from_square)
    piece_name = get_piece_name(piece) if piece else "piece"
    
    # Determine the type of issue
    if board.is_capture(played_move):
        concept_type = "tactical"
        goal = "Calculate captures carefully"
        problem = f"This {piece_name} capture has a flaw"
    else:
        concept_type = "positional"
        goal = "Improve your pieces"
        problem = f"Moving the {piece_name} here doesn't help your position"
    
    consequence = _describe_consequence(pv_after_played, board)
    
    better = ""
    if best_move:
        better = f"{best_move} was better"
        if pv_after_best:
            better += f" — the idea is {' '.join(pv_after_best[:2])}"
    
    severity = "inaccuracy" if cp_loss < 100 else ("mistake" if cp_loss < 250 else "blunder")
    
    return ChessPlan(
        goal=goal,
        current_problem=problem,
        consequence=consequence,
        better_approach=better,
        transferable_learning="Before moving, ask: what does my opponent do next?",
        concept_id=f"generic_{severity}",
        concept_type=concept_type
    )


# ─── OPPONENT MOVE ANALYSIS ──────────────────────────────────────────

def analyze_opponent_move(
    board: chess.Board,
    move: chess.Move,
    eval_before: Optional[int],
    eval_after: Optional[int],
    pv_after: List[str],
    user_color: str
) -> Tuple[str, Optional[str], List[str]]:
    """
    Analyze opponent's move from USER's perspective.
    Returns: (narrative, your_plan_now, highlight_squares)
    """
    move_san = board.san(move)
    
    # Calculate eval swing from user's perspective
    eval_swing = 0
    if eval_before is not None and eval_after is not None:
        # Positive means good for user
        if user_color == "white":
            eval_swing = eval_after - eval_before
        else:
            eval_swing = eval_before - eval_after
    
    highlight_squares = []
    your_plan_now = None
    
    # Opponent blundered
    if eval_swing > 150:
        # Find what they weakened
        sim = board.copy()
        sim.push(move)
        
        weak_squares = []
        # Check for weakened king
        opp_king = sim.king(not (user_color == "white"))
        if opp_king:
            king_attackers = sim.attackers(user_color == "white", opp_king)
            if king_attackers:
                weak_squares.append(chess.square_name(opp_king))
        
        # Check for hanging pieces
        for sq, p in sim.piece_map().items():
            if p.color != (user_color == "white"):
                attackers = sim.attackers(user_color == "white", sq)
                defenders = sim.attackers(not (user_color == "white"), sq)
                if len(attackers) > len(defenders):
                    weak_squares.append(chess.square_name(sq))
        
        highlight_squares = weak_squares[:3]
        
        if weak_squares:
            your_plan_now = f"Target the weak squares: {', '.join(weak_squares[:2])}"
            narrative = f"Your opponent's {move_san} creates a weakness. Look for ways to exploit it."
        else:
            your_plan_now = "Your opponent made an error. Look for forcing moves."
            narrative = f"This {move_san} is a mistake. Find the best response."
    
    # Opponent played a normal move
    elif abs(eval_swing) < 50:
        # Describe what the move does
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            narrative = f"Opponent took the {get_piece_name(captured) if captured else 'piece'} with {move_san}."
        elif board.is_castling(move):
            narrative = "Opponent castled — their king is safer now."
        else:
            narrative = f"Opponent played {move_san}."
        
        # What should user think about?
        your_plan_now = "Check: what did this move threaten? What did it weaken?"
    
    # Opponent made a small inaccuracy
    else:
        narrative = f"Opponent's {move_san} is slightly inaccurate."
        your_plan_now = "Look for ways to take advantage."
    
    return narrative, your_plan_now, highlight_squares


# ─── GOOD MOVE RECOGNITION ───────────────────────────────────────────

def recognize_good_move(
    board: chess.Board,
    move: chess.Move,
    best_move: Optional[str],
    cp_loss: int,
    phase: str,
    opening_data: dict
) -> Tuple[str, Optional[str], bool]:
    """
    Recognize when user plays a good move.
    Returns: (narrative, concept_applied, is_best_move)
    """
    move_san = board.san(move)
    is_best = best_move and move_san.lower().replace("+", "").replace("#", "") == best_move.lower().replace("+", "").replace("#", "")
    
    piece = board.piece_at(move.from_square)
    piece_name = get_piece_name(piece) if piece else "piece"
    
    concept_applied = None
    
    # Check if this matches opening theory
    typical_ideas = opening_data.get("typical_ideas", {})
    if move_san in typical_ideas:
        concept_applied = f"opening_{move_san.lower()}"
        if is_best:
            return f"Perfect! {move_san} — {typical_ideas[move_san]}", concept_applied, True
        return f"Good — {move_san}. {typical_ideas[move_san]}", concept_applied, False
    
    # Castling
    if board.is_castling(move):
        concept_applied = "king_safety_castling"
        if is_best:
            return "Excellent — castling at the right moment keeps your king safe.", concept_applied, True
        return "Good — king safety first.", concept_applied, False
    
    # Development
    back_rank = 0 if piece.color == chess.WHITE else 7
    if piece and chess.square_rank(move.from_square) == back_rank and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
        concept_applied = "development"
        if is_best:
            return f"Great development! The {piece_name} is now active.", concept_applied, True
        return f"Solid — developing the {piece_name}.", concept_applied, False
    
    # Generic good move
    if is_best:
        return f"You found the best move! {move_san} is exactly right here.", "found_best_move", True
    
    if cp_loss < 10:
        return f"Very good — {move_san}.", None, False
    
    return f"{move_san}.", None, False


# ─── NARRATIVE GENERATION ────────────────────────────────────────────

def generate_simple_narrative(
    plan: ChessPlan,
    move_san: str,
    best_move: Optional[str],
    cp_loss: int,
    already_acknowledged: bool
) -> str:
    """
    Generate a simple, 1200-friendly narrative.
    
    If user already acknowledged this concept, keep it brief.
    If not, include the learning.
    """
    if already_acknowledged:
        # Brief reminder
        if plan.concept_type == "opening":
            return f"{move_san} — you know this position. {best_move} was better."
        return f"{move_san} loses something. You've seen this pattern before."
    
    # Full explanation for new concepts
    parts = []
    
    # Start with what they tried to do (acknowledge intent)
    parts.append(f"You played {move_san}.")
    
    # The problem (simple)
    if plan.current_problem:
        parts.append(plan.current_problem)
    
    # The consequence (show the future)
    if plan.consequence:
        parts.append(plan.consequence)
    
    # The better approach
    if plan.better_approach:
        parts.append(plan.better_approach)
    
    return " ".join(parts)


# ─── MAIN ORCHESTRATOR ───────────────────────────────────────────────

async def generate_game_decryption_v5(
    pgn: str,
    user_color: str,
    move_evaluations: List[Dict],
    user_id: str,
    db  # MongoDB database reference
) -> List[Dict]:
    """
    Generate V5 "Thinking Simulator" coaching for a game.
    
    Key differences from V4:
    1. Coaches EVERY move (not just mistakes)
    2. Extracts PLANS (not just moves)
    3. Tracks concept acknowledgment
    4. Simple, 1200-friendly language
    """
    try:
        # Parse game
        game = chess.pgn.read_game(io.StringIO(pgn))
        if not game:
            logger.error("Could not parse PGN")
            return []
        
        moves = list(game.mainline_moves())
        
        # Detect opening
        opening_name, eco_code = detect_opening_from_pgn(pgn)
        opening_data = get_opening_data(eco_code, opening_name)
        logger.info(f"[DECRYPTION V5] Opening: {opening_name or 'Unknown'} ({eco_code or 'N/A'})")
        
        # Build eval lookup by FEN
        eval_lookup = {}
        for eval_data in move_evaluations:
            fen = eval_data.get("fen_before", "")
            if fen:
                fen_key = " ".join(fen.split()[:4])
                eval_lookup[fen_key] = eval_data
        
        # Get user's acknowledged concepts
        acknowledged_concepts = set()
        if db is not None:
            try:
                cursor = db.user_concept_understanding.find(
                    {"user_id": user_id, "acknowledged": True},
                    {"concept_id": 1}
                )
                async for doc in cursor:
                    acknowledged_concepts.add(doc.get("concept_id"))
            except Exception as e:
                logger.warning(f"Could not fetch acknowledged concepts: {e}")
        
        # Process each move
        decryption_data = []
        board = chess.Board()
        prev_move = None
        
        for idx, move in enumerate(moves):
            move_san = board.san(move)
            full_move_number = (idx // 2) + 1
            is_white = (idx % 2 == 0)
            is_user = (user_color == "white" and is_white) or (user_color == "black" and not is_white)
            
            # Get eval data
            fen_key = " ".join(board.fen().split()[:4])
            eval_data = eval_lookup.get(fen_key, {})
            cp_loss = abs(eval_data.get("cp_loss", 0)) if is_user else 0
            
            phase = detect_phase(board, full_move_number)
            
            # Determine severity
            if not is_user:
                severity = "context"
            elif cp_loss < 30:
                severity = "good"
            elif cp_loss < 100:
                severity = "inaccuracy"
            elif cp_loss < 250:
                severity = "mistake"
            else:
                severity = "blunder"
            
            # Check for forced recapture
            is_forced_recapture = False
            if is_user and board.is_capture(move) and prev_move:
                if move.to_square == prev_move.to_square:
                    captures_on_sq = [m for m in board.legal_moves if m.to_square == move.to_square and board.is_capture(m)]
                    if len(captures_on_sq) <= 1:
                        is_forced_recapture = True
                        severity = "good"
            
            fen_before = board.fen()
            
            # Get PV data
            pv_after_played = eval_data.get("pv_after_played", [])
            pv_after_best = eval_data.get("pv_after_best", [])
            best_move = eval_data.get("best_move")
            
            # Build coaching based on move type
            narrative = ""
            plan = None
            future_moves = []
            highlight_squares = []
            your_plan_now = None
            needs_acknowledgment = False
            already_acknowledged = False
            acknowledgment_prompt = None
            is_best_move = False
            concept_applied = None
            
            if not is_user:
                # OPPONENT MOVE - Analyze from user's POV
                narrative, your_plan_now, highlight_squares = analyze_opponent_move(
                    board, move,
                    eval_data.get("eval_before"),
                    eval_data.get("eval_after"),
                    pv_after_played,
                    user_color
                )
                future_moves = pv_after_played[:3] if pv_after_played else []
                
            elif severity == "good":
                # GOOD USER MOVE - Recognize and track
                narrative, concept_applied, is_best_move = recognize_good_move(
                    board, move, best_move, cp_loss, phase, opening_data
                )
                
            elif is_forced_recapture:
                # FORCED RECAPTURE - Natural move
                captured = board.piece_at(move.to_square)
                narrative = f"Forced recapture — {move_san} takes back the {get_piece_name(captured) if captured else 'piece'}."
                
            else:
                # MISTAKE/INACCURACY - Extract plan
                plan = extract_plan_from_pv(
                    board, move, best_move,
                    pv_after_played, pv_after_best,
                    phase, opening_data, cp_loss,
                    eco_code=eco_code
                )
                
                if plan:
                    already_acknowledged = plan.concept_id in acknowledged_concepts
                    
                    # Check how many times we've shown this concept
                    shown_count = 0
                    if db is not None:
                        try:
                            concept_doc = await db.user_concept_understanding.find_one({
                                "user_id": user_id,
                                "concept_id": plan.concept_id
                            })
                            if concept_doc:
                                shown_count = concept_doc.get("shown_count", 0)
                        except Exception:
                            pass
                    
                    if not already_acknowledged:
                        needs_acknowledgment = True
                        if shown_count >= 3:
                            acknowledgment_prompt = "Let's revisit this concept — it keeps coming up."
                        else:
                            acknowledgment_prompt = "Click 'I understand' when this is clear to you."
                    
                    narrative = generate_simple_narrative(
                        plan, move_san, best_move, cp_loss, already_acknowledged
                    )
                    future_moves = pv_after_played[:4] if pv_after_played else []
                else:
                    # Fallback narrative
                    narrative = f"{move_san} loses about {cp_loss // 100} pawns. {best_move} was better."
                    future_moves = pv_after_played[:3] if pv_after_played else []
            
            # Build move output
            prev_move = move
            board.push(move)
            
            move_output = {
                "move_number": full_move_number,
                "move_san": move_san,
                "is_user_move": is_user,
                "is_white": is_white,
                "fen_before": fen_before,
                "fen_after": board.fen(),
                "phase": phase,
                "opening_name": opening_name,
                
                # Evaluation
                "cp_loss": cp_loss,
                "eval_before": eval_data.get("eval_before"),
                "eval_after": eval_data.get("eval_after"),
                "best_move_san": best_move,
                "severity": severity,
                "is_mistake": severity in ("mistake", "blunder"),
                
                # V5 Coaching
                "narrative": narrative,
                "plan": asdict(plan) if plan else None,
                "future_moves": future_moves,
                "highlight_squares": highlight_squares,
                
                # Theory/Learning
                "needs_acknowledgment": needs_acknowledgment,
                "already_acknowledged": already_acknowledged,
                "acknowledgment_prompt": acknowledgment_prompt,
                "concept_id": plan.concept_id if plan else None,
                "concept_type": plan.concept_type if plan else None,
                
                # Opponent analysis
                "your_plan_now": your_plan_now,
                
                # Good move tracking
                "is_best_move": is_best_move,
                "concept_applied": concept_applied,
            }
            
            decryption_data.append(move_output)
            
            # Update concept shown count
            if plan and needs_acknowledgment and db is not None:
                try:
                    await db.user_concept_understanding.update_one(
                        {"user_id": user_id, "concept_id": plan.concept_id},
                        {
                            "$inc": {"shown_count": 1},
                            "$set": {
                                "concept_type": plan.concept_type,
                                "concept_text": plan.transferable_learning,
                                "updated_at": datetime.now(timezone.utc).isoformat()
                            },
                            "$setOnInsert": {
                                "user_id": user_id,
                                "concept_id": plan.concept_id,
                                "acknowledged": False,
                                "source_position": fen_before,
                                "created_at": datetime.now(timezone.utc).isoformat()
                            }
                        },
                        upsert=True
                    )
                except Exception as e:
                    logger.warning(f"Could not update concept tracking: {e}")
        
        logger.info(f"[DECRYPTION V5] Generated coaching for {len(decryption_data)} moves")
        
        # ─── LLM ENHANCEMENT PASS ────────────────────────────────────
        # Enhance mistakes/inaccuracies with LLM for more natural language
        try:
            from services.v5_llm_narrator import generate_concise_narrative, generate_opponent_narrative, generate_good_move_praise
            
            mistakes_to_enhance = [
                (i, m) for i, m in enumerate(decryption_data)
                if m.get("severity") in ("mistake", "blunder", "inaccuracy") and m.get("plan")
            ]
            
            if mistakes_to_enhance:
                logger.info(f"[DECRYPTION V5] Enhancing {len(mistakes_to_enhance)} mistakes with LLM...")
                
                for idx, move_data in mistakes_to_enhance:
                    try:
                        llm_narrative = await generate_concise_narrative(
                            move_san=move_data.get("move_san", ""),
                            plan_data=move_data.get("plan", {}),
                            phase=move_data.get("phase", "middlegame"),
                            severity=move_data.get("severity", "mistake"),
                            is_user_move=True
                        )
                        if llm_narrative:
                            decryption_data[idx]["narrative"] = llm_narrative
                            decryption_data[idx]["llm_enhanced"] = True
                    except Exception as e:
                        logger.warning(f"LLM enhancement failed for move {idx}: {e}")
                        
                logger.info("[DECRYPTION V5] LLM enhancement complete")
        except ImportError:
            logger.warning("[DECRYPTION V5] LLM narrator not available, using rule-based narratives")
        except Exception as e:
            logger.warning(f"[DECRYPTION V5] LLM enhancement skipped: {e}")
        
        return decryption_data
        
    except Exception as e:
        logger.error(f"Error in game decryption V5: {e}")
        import traceback
        traceback.print_exc()
        return []


# ─── SYNC WRAPPER ────────────────────────────────────────────────────

def generate_game_decryption_v5_sync(
    pgn: str,
    user_color: str,
    move_evaluations: List[Dict],
    user_id: str,
    db
) -> List[Dict]:
    """Synchronous wrapper for V5 decryption."""
    import asyncio
    
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            generate_game_decryption_v5(pgn, user_color, move_evaluations, user_id, db)
        )
        loop.close()
        return result
    except RuntimeError:
        # Already in event loop
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(
                asyncio.run,
                generate_game_decryption_v5(pgn, user_color, move_evaluations, user_id, db)
            )
            return future.result(timeout=180)


# ─── ACKNOWLEDGMENT API ──────────────────────────────────────────────

async def acknowledge_concept(db, user_id: str, concept_id: str) -> bool:
    """
    Mark a concept as acknowledged by the user.
    Called when user clicks "I understand" button.
    """
    try:
        result = await db.user_concept_understanding.update_one(
            {"user_id": user_id, "concept_id": concept_id},
            {
                "$set": {
                    "acknowledged": True,
                    "acknowledged_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Also add to coach_memory.learning.concepts_mastered
        await db.coach_memory.update_one(
            {"user_id": user_id},
            {
                "$addToSet": {"learning.concepts_mastered": concept_id},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
        
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error acknowledging concept: {e}")
        return False


async def track_concept_application(
    db,
    user_id: str,
    concept_id: str,
    applied_correctly: bool
) -> None:
    """
    Track when user applies (or fails to apply) a concept.
    Called after analyzing a game where the concept was relevant.
    """
    try:
        update_field = "applied_correctly_count" if applied_correctly else "failed_to_apply_count"
        await db.user_concept_understanding.update_one(
            {"user_id": user_id, "concept_id": concept_id},
            {
                "$inc": {update_field: 1},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
    except Exception as e:
        logger.warning(f"Could not track concept application: {e}")
