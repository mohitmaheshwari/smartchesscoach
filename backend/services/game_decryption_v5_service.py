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
import chess.engine
import json
import os
import io
import re
import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# V5 coaching version — increment when coaching logic changes to trigger re-generation
V5_COACHING_VERSION = 22  # v22 (2026-05-18): Phase 6 — 3 cross-opening theme detectors. v20 OP_BISHOP_TRADE_DOUBLES_PAWN (Bxc3-bxc3 structural concession across English / Nimzo / Vienna). v21 OP_F2_F7_STRIKE (weak-king-square capture, only king defends). v22 OP_TRAPPED_KNIGHT (every legal destination SEE-unsafe, distinct from OP_KNIGHT_ON_RIM). All three use state-keyed suppression (Phase 0.5) and per-principle audit scripts in backend/scripts.

# Stockfish path
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")

# ── V5 caption pipeline feature flag ────────────────────────────────────
# When True, every move record also carries new fields produced by the
# extractor→rules→renderer pipeline (caption, rule_name, caption_arrows,
# caption_highlight_squares, caption_facts_primary_reason). Legacy fields
# (narrative, plan, future_moves, highlight_squares) remain in place so
# reviewers can compare side-by-side. Disable by setting env to "0".
# Per docs/caption_pipeline_design.md.
CAPTION_V5_PIPELINE_ENABLED = os.environ.get("CAPTION_V5_PIPELINE_ENABLED", "1") not in ("0", "false", "False", "")

try:
    from services.caption_facts import extract_facts as _extract_caption_facts
    from services.caption_renderer import render_caption_dict as _render_caption_dict
    from services.caption_principles import PRINCIPLES_BY_ID as _CAPTION_PRINCIPLES_BY_ID
except Exception as _caption_import_exc:  # pragma: no cover — defensive
    _extract_caption_facts = None
    _render_caption_dict = None
    logger.warning(f"[caption_v5] import failed; pipeline disabled: {_caption_import_exc}")
    CAPTION_V5_PIPELINE_ENABLED = False

# TIER 3 shape-pattern selector. Pure-function detector + engine verifier
# wrapper. Lives behind a try/except so a detector import failure can't
# wedge the V5 pipeline.
try:
    from services.shape_layer import select_shape_for_position as _select_shape_for_position
    from services.shape_detectors import detect_all_shapes as _detect_all_shapes
    from services.shape_detectors import verify_with_engine_data as _verify_shapes_with_engine
    from services.shape_patterns import PATTERNS_BY_ID as _SHAPE_PATTERNS_BY_ID
except Exception as _shape_import_exc:  # pragma: no cover — defensive
    _select_shape_for_position = None
    _detect_all_shapes = None
    _verify_shapes_with_engine = None
    _SHAPE_PATTERNS_BY_ID = {}
    logger.warning(f"[shape_v3] import failed; shape layer disabled: {_shape_import_exc}")

# Trap recognition (named opening traps from data/traps.json). Stateful:
# fires on setup-completing move and again on each move that follows the
# authored trap_line. Pure Python, no engine call.
try:
    from services.trap_recognition import detect_trap_setup, match_trap_line_step
except Exception as _trap_import_exc:  # pragma: no cover — defensive
    detect_trap_setup = None
    match_trap_line_step = None
    logger.warning(f"[trap] import failed; trap layer disabled: {_trap_import_exc}")

# Opening curriculum lookup (data/opening_curriculum.json). Matches the
# moving side's played-move prefix against setup_order. Returns name +
# summary + golden_rules when on-book ≥ 3 setup moves.
try:
    from services.opening_lookup import match_opening_for_mover
except Exception as _opening_import_exc:  # pragma: no cover — defensive
    match_opening_for_mover = None
    logger.warning(f"[opening] import failed; opening layer disabled: {_opening_import_exc}")

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
class CandidateMove:
    """A candidate move with its strategic idea."""
    move_san: str                # The move in SAN notation
    idea: str                    # The strategic idea/plan behind this move
    move_type: str               # "counter_attack" | "prophylactic" | "development" | "central" | "tactical"


@dataclass
class ChessPlan:
    """A transferable chess plan (not just moves)."""
    goal: str                    # What we're trying to achieve
    current_problem: str         # Why current move doesn't achieve it
    consequence: str             # What happens after (the future)
    better_approach: str         # What to do instead (summary)
    transferable_learning: str   # The concept that applies to many games
    concept_id: str              # Unique ID for tracking acknowledgment
    concept_type: str            # "opening" | "endgame" | "tactical" | "positional"
    candidate_moves: List[Dict] = field(default_factory=list)  # Multiple alternatives with ideas


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


def get_opening_introduction(
    eco_code: Optional[str],
    opening_name: Optional[str],
    move_san: str,
    user_color: str,
    move_index: Optional[int] = None,
) -> Optional[Dict]:
    """
    Get opening introduction for the first few moves.
    Returns context about what opening this is and what the plans are.

    move_index (ply index, 0-based) is used to gate the "first-move
    opening" labels: e4/d4/c4/Nf3 only refer to a named opening when
    they are white's literal first move (idx 0); e5/c5/c6/Nf6 etc only
    when they are black's literal first response (idx 1). Without this
    gate, Nf3 played as move 3 (e.g., after 1.e4 e5 2.f4) gets labelled
    "Réti Opening" — wrong, because Réti specifically means 1.Nf3 with
    no prior pawn play. Source bug: fb_d0454a4088f3.
    """
    # Common opening patterns by first moves
    opening_intros = {
        # White first moves
        "e4": {
            "name": "King's Pawn Opening",
            "idea": "White stakes a claim in the center. Most popular opening - leads to open games.",
            "black_response_hint": "You can match with e5 (Open Game) or fight back with c5 (Sicilian), e6 (French), c6 (Caro-Kann), or d5 (Scandinavian)."
        },
        "d4": {
            "name": "Queen's Pawn Opening", 
            "idea": "White controls the center from the side. Games tend to be more closed and strategic.",
            "black_response_hint": "d5 is solid (closed games), Nf6 is flexible (Indian systems), f5 is aggressive (Dutch)."
        },
        "c4": {
            "name": "English Opening",
            "idea": "White controls d5 without committing the d-pawn. Flexible and positional.",
            "black_response_hint": "c5 for symmetry, e5 to grab space, Nf6 for flexibility."
        },
        "Nf3": {
            "name": "Réti Opening",
            "idea": "White develops without committing pawns. Can transpose to many openings.",
            "black_response_hint": "d5 is the most principled. Nf6 mirrors White's approach."
        },
        
        # Common Black responses to e4
        "e5": {"name": "Open Game", "idea": "Symmetric center control. Leads to tactical play."},
        "c5": {"name": "Sicilian Defense", "idea": "Asymmetric counter-attack. Black fights for d4 control."},
        "e6": {"name": "French Defense", "idea": "Solid but cramped. Black will undermine with c5 and sometimes f6."},
        "c6": {"name": "Caro-Kann Defense", "idea": "Very solid. Black develops the bishop to f5 or g4 before e6."},
        
        # Common Black responses to d4
        "d5": {"name": "Closed Game", "idea": "Solid central control. Strategic middlegames."},
        "Nf6": {"name": "Indian Defense", "idea": "Flexible - can become King's Indian, Nimzo-Indian, or Queen's Indian."},
        
        # Common follow-ups
        "Nc3": {"idea": "Develops naturally, prepares e4 or supports d5."},
        "Bf4": {"name": "London System", "idea": "White develops bishop before e3. Solid and easy to play."},
        "Bg5": {"idea": "Pins the knight. White may double Black's pawns or force concessions."},
        "Bc4": {"name": "Italian Game direction", "idea": "Aims at f7 weakness. Classic development."},
        "Bb5": {"name": "Spanish Game direction", "idea": "Pressures e5 indirectly through the knight on c6."},
    }
    
    # Gate first-move labels on move_index — see docstring. The set
    # of move_sans below is "openings named purely from the move name,
    # ASSUMING it's the first or second ply." Without the gate they
    # mis-fire on transpositions.
    _WHITE_FIRST_MOVE_OPENINGS = {"e4", "d4", "c4", "Nf3"}
    _BLACK_FIRST_RESPONSES = {"e5", "c5", "e6", "c6", "d5", "Nf6"}

    if move_san in opening_intros:
        if move_index is not None:
            if move_san in _WHITE_FIRST_MOVE_OPENINGS and move_index != 0:
                # Not white's first move — can't be the named first-move
                # opening (likely a transposition). Skip the label.
                return None
            if move_san in _BLACK_FIRST_RESPONSES and move_index != 1:
                # Not black's first response — same reasoning.
                return None
        intro = opening_intros[move_san]
        return {
            "name": intro.get("name"),
            "idea": intro.get("idea"),
            "hint": intro.get("black_response_hint") if user_color == "black" else None
        }
    
    # Use ECO-based name if available
    if opening_name:
        return {
            "name": opening_name,
            "idea": None,
            "hint": None
        }
    
    return None


# ─── OPENING BOOK MOVE DETECTION ─────────────────────────────────────

# Known opening responses that Stockfish may score poorly but are completely valid theory.
# Maps FEN position prefix -> set of valid SAN moves in that position.
# We only need to track positions where Stockfish might disagree with theory.
KNOWN_OPENING_RESPONSES = None  # Will be built dynamically using python-chess

def is_book_opening_move(board: chess.Board, move_san: str, move_index: int,
                         opening_name: Optional[str] = None, cp_loss: int = 0,
                         move_history: Optional[List[str]] = None) -> bool:
    """
    Check if a user's move is a known opening book move that shouldn't be
    flagged as an inaccuracy, even if Stockfish slightly prefers another line.

    Returns True if the move is a recognized opening response.

    move_history: optional list of SAN moves played up to (not including)
        the candidate move. When provided, the opening-detection check uses
        it directly. When None, falls back to board.move_stack (which is
        empty if board was built from a raw FEN). Audit scripts that
        reconstruct from FEN should pass move_history explicitly.
    """
    # Only applies to early game (first 12 half-moves)
    if move_index > 12:
        return False
    
    # If cp_loss is very high (>120), it's genuinely bad even for an opening
    if cp_loss > 120:
        return False
    
    # --- Check 1: Use the opening-detection service for moves >= 2 ---
    # Reconstruct the played sequence + the candidate move, ask
    # services.opening_mastery whether the sequence matches a known
    # opening line. Handles 23+ openings via the existing detector —
    # no hardcoded per-opening response sets here. Detector requires
    # at least 2 moves to classify, so move 1 (idx 0/1) falls through
    # to Check 2 below.
    try:
        from services.opening_mastery import detect_opening_from_moves
        # Prefer explicit move_history when caller provides it (audit
        # scripts reconstructing from FEN). Fall back to board.move_stack
        # (production path where board was built incrementally).
        if move_history is not None:
            prior_sans = list(move_history)
        else:
            replay_board = chess.Board()
            prior_sans = []
            for past_mv in board.move_stack:
                prior_sans.append(replay_board.san(past_mv))
                replay_board.push(past_mv)
        full_sequence = prior_sans + [move_san]
        opening_info = detect_opening_from_moves(full_sequence)
        if opening_info and opening_info.get("opening_key"):
            return True
    except Exception:
        pass

    # --- Check 2: Move-1 sanity (detector needs >=2 moves to classify) ---
    # Any standard first move by white is book. Any standard first
    # response by black to a recognised first move is book.
    _STANDARD_FIRST_WHITE_MOVES = {
        "e4", "d4", "c4", "Nf3", "g3", "b3", "f4", "e3", "d3", "b4", "Nc3",
    }
    _STANDARD_FIRST_BLACK_RESPONSES = {
        "e5", "c5", "e6", "c6", "d5", "d6", "Nf6", "Nc6", "g6", "b6", "a6", "f5",
    }
    if move_index == 0 and move_san in _STANDARD_FIRST_WHITE_MOVES:
        return True
    if move_index == 1 and move_san in _STANDARD_FIRST_BLACK_RESPONSES:
        return True
    
    # --- Check 2: If opening was detected, trust early moves ---
    # If the game eventually reaches a recognized opening (e.g., Scandinavian),
    # the moves that got us there were book moves
    if opening_name and move_index < 8:
        return True
    
    # --- Check 3: Common early-game developing moves with small cp_loss ---
    # In the first few moves, natural developing moves shouldn't be flagged
    if move_index <= 6 and cp_loss < 60:
        # Check if it's a natural developing move
        try:
            move = board.parse_san(move_san)
            piece = board.piece_at(move.from_square)
            if piece:
                # Knight/Bishop development, castling, central pawn pushes
                if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                    return True
                if piece.piece_type == chess.KING and board.is_castling(move):
                    return True
                if piece.piece_type == chess.PAWN:
                    # Central or semi-central pawn moves
                    to_file = chess.square_file(move.to_square)
                    if to_file in (2, 3, 4, 5):  # c, d, e, f files
                        return True
        except Exception:
            pass
    
    return False


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
    eco_code: Optional[str] = None,
    stockfish_candidates: Optional[List[Dict]] = None
) -> Optional[ChessPlan]:
    """
    Extract a PLAN from the Stockfish PV (not just moves).
    
    This is the core innovation of V5 - turning engine analysis into
    transferable chess understanding.
    """
    if cp_loss < 30:
        return None  # Good moves don't need a plan explanation
    
    played_san = board.san(played_move)
    
    # ─── MATE BLUNDER CHECK ──────────────────────────────
    # If this move allows checkmate, everything else is irrelevant.
    #
    # The trigger condition (cp_loss >= 5000 OR PV-has-"#") is too
    # eager — fb_ca616e985bf8 fired "Bb6 allows checkmate" on a 50-pawn
    # eval swing where no forced mate actually existed (white's
    # position was already losing; Bb6 made it more losing without a
    # real mate threat). Verify the mate claim with a deeper engine
    # search before emitting "allows checkmate."
    mate_trigger = (
        cp_loss >= 5000
        or (pv_after_played and any("#" in m for m in pv_after_played[:4]))
    )
    if mate_trigger:
        board_after = board.copy()
        board_after.push(played_move)

        # Verify the mate claim against the engine. losing_side is the
        # player whose move is accused (the side whose turn it WAS in
        # `board`, before played_move).
        mate_confirmed = True
        try:
            from services.threat_verifier import (
                _get_singleton_engine,
                position_allows_forced_mate,
            )
            engine = _get_singleton_engine()
            if engine is not None:
                mate_confirmed = position_allows_forced_mate(
                    fen_after_played_move=board_after.fen(),
                    losing_side=board.turn,
                    engine=engine,
                )
        except Exception as exc:
            logger.debug(f"[V5] mate verifier skipped: {exc}")

        if mate_confirmed:
            consequence = _describe_consequence(pv_after_played, board_after) if pv_after_played else "This allows a forced checkmate."
            return ChessPlan(
                goal="Avoid checkmate",
                current_problem=f"{played_san} allows checkmate.",
                consequence=consequence,
                better_approach=f"{best_move} stops the checkmate and keeps the game going." if best_move else "You needed to block the checkmate threat first.",
                transferable_learning="Before every move, check: can my opponent give checkmate? If yes, stop that before doing anything else.",
                concept_id="king_safety_mate_threat",
                concept_type="tactical"
            )
        # Mate not confirmed — fall through to the regular plan-
        # extraction path so the caption describes the actual eval
        # swing (material loss, positional collapse) instead of
        # claiming a checkmate that doesn't exist.
    
    # Create a board with the user's move played (for consequence analysis)
    board_after_move = board.copy()
    board_after_move.push(played_move)
    
    # Try opening theory tree first (more comprehensive)
    try:
        from services.opening_theory_tree_service import get_mistake_from_theory
        
        theory_mistake = get_mistake_from_theory(eco_code, played_san, board.fen())
        if theory_mistake:
            return ChessPlan(
                goal="Follow opening principles",
                current_problem=theory_mistake.get("why_bad", f"{played_san} is a theoretical mistake"),
                consequence=theory_mistake.get("consequence", _describe_consequence(pv_after_played, board_after_move)),
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
                        consequence=_describe_consequence(pv_after_played, board_after_move),
                        better_approach=f"{pattern.get('good_move', best_move)} — {pattern.get('why_good', 'keeps the position solid')}",
                        transferable_learning=pattern.get("rule", ""),
                        concept_id=pattern_id,
                        concept_type="opening"
                    )
        except Exception:
            continue
    
    # Try endgame principles
    if phase == "endgame":
        endgame_plan = _match_endgame_principle(board_after_move, played_move, best_move, pv_after_played)
        if endgame_plan:
            return endgame_plan
    
    # Try tactical patterns
    tactical_plan = _detect_tactical_issue(board_after_move, played_move, pv_after_played, cp_loss, played_san)
    if tactical_plan:
        return tactical_plan
    
    # Get the piece type for generic plan
    piece_type = board.piece_at(played_move.from_square).piece_type if board.piece_at(played_move.from_square) else None
    
    # Generic positional plan - now with Stockfish candidate moves!
    return _generate_generic_plan(
        board_after_move, played_san, piece_type, played_move.to_square,
        best_move, pv_after_played, cp_loss,
        board_before=board, played_move=played_move,
        stockfish_candidates=stockfish_candidates
    )


def _describe_consequence(pv: List[str], board: chess.Board) -> str:
    """
    Describe what SPECIFICALLY happens in the PV.
    
    Priority:
    1. Checkmate in PV → "Checkmate"
    2. Material loss in PV (walk the moves, find captures) → "Your knight gets taken"
    3. Static analysis (undefended pieces) → fallback
    """
    if not pv:
        return "Something's not right here!"
    
    sim = board.copy()
    user_color = not board.turn  # User just moved, so opponent is to move
    first_move_san = pv[0]
    
    # ─── 1. CHECKMATE CHECK ──────────────────────────────
    if "#" in first_move_san:
        return f"After {first_move_san}, it's checkmate. Game over."
    
    try:
        first_move = sim.parse_san(first_move_san)
        sim.push(first_move)
        if sim.is_checkmate():
            return f"After {first_move_san}, it's checkmate. Game over."
        
        # Check mate in PV (2-3 moves)
        sim2 = sim.copy()
        for pv_san in pv[1:4]:
            try:
                if "#" in pv_san:
                    return f"After {first_move_san}, forced checkmate follows within a few moves."
                pm = sim2.parse_san(pv_san)
                sim2.push(pm)
                if sim2.is_checkmate():
                    return f"After {first_move_san}, forced checkmate follows within a few moves."
            except Exception:
                break
    except Exception:
        pass
    
    # ─── 2. WALK THE PV — find material loss (most accurate) ───
    sim = board.copy()
    for i, san in enumerate(pv[:5]):
        try:
            move = sim.parse_san(san)
            
            if sim.is_capture(move):
                captured = sim.piece_at(move.to_square)
                if captured:
                    captured_name = _get_fun_piece_name(captured)
                    sq_name = chess.square_name(move.to_square)
                    
                    if captured.color == user_color and captured.piece_type != chess.PAWN:
                        # User loses a piece — this is the key consequence
                        # Explain the forcing sequence
                        if i == 0:
                            return f"After {san}, your {captured_name} on {sq_name} gets captured!"
                        elif i >= 2:
                            # There's a forcing sequence leading to this
                            sequence = " ".join(pv[:i+1])
                            # Check if there was a check forcing the defense
                            check_move = None
                            for j in range(i):
                                if "+" in pv[j]:
                                    check_move = pv[j]
                                    break
                            if check_move:
                                return f"After {check_move}, you're forced to deal with the check, and then {san} wins your {captured_name}!"
                            else:
                                return f"After {sequence}, your {captured_name} on {sq_name} gets taken!"
                        else:
                            return f"After {pv[0]}, your {captured_name} on {sq_name} gets captured!"
                    
                    elif captured.color == user_color and captured.piece_type == chess.PAWN:
                        # Pawn loss — note but keep looking for bigger losses
                        pass
            
            sim.push(move)
        except Exception:
            break
    
    # ─── 3. STATIC ANALYSIS — undefended pieces (fallback) ───
    sim = board.copy()
    problems = []
    
    try:
        first_move = sim.parse_san(first_move_san)
        sim.push(first_move)
        
        # Check for checks first
        if sim.is_check():
            problems.append("your King gets checked! Gotta deal with that first!")
        
        # Check user pieces for new attacks
        for sq in chess.SQUARES:
            piece = sim.piece_at(sq)
            if piece and piece.color == user_color and piece.piece_type != chess.PAWN:
                attackers = list(sim.attackers(not user_color, sq))
                defenders = list(sim.attackers(user_color, sq))
                
                if attackers and not defenders:
                    piece_name = _get_fun_piece_name(piece)
                    sq_name = chess.square_name(sq)
                    problems.append(f"your {piece_name} on {sq_name} is hanging with no defenders!")
                    break
                elif attackers and len(attackers) > len(defenders):
                    piece_name = _get_fun_piece_name(piece)
                    sq_name = chess.square_name(sq)
                    problems.append(f"your {piece_name} on {sq_name} is outnumbered - {len(attackers)} vs {len(defenders)}!")
                    break
        
        # If no piece issues, check pawns
        if not problems:
            for sq in chess.SQUARES:
                piece = sim.piece_at(sq)
                if piece and piece.color == user_color and piece.piece_type == chess.PAWN:
                    attackers = list(sim.attackers(not user_color, sq))
                    defenders = list(sim.attackers(user_color, sq))
                    if attackers and not defenders:
                        sq_name = chess.square_name(sq)
                        problems.append(f"your pawn on {sq_name} is undefended!")
                        break
    except Exception:
        pass
    
    if not problems:
        problems = _analyze_positional_weakness(board, user_color)
    
    if problems:
        return f"After {first_move_san}, {problems[0]}"
    
    return f"After {first_move_san}, your opponent gains space and activity. You'll need to defend!"


def _analyze_positional_weakness(board: chess.Board, user_color: bool) -> List[str]:
    """
    Find positional weaknesses when no tactical issues are found.
    Returns a list of specific problems.
    """
    problems = []
    
    # Check for center control issues
    center_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
    user_center_control = 0
    opp_center_control = 0
    
    for sq in center_squares:
        user_attackers = len(list(board.attackers(user_color, sq)))
        opp_attackers = len(list(board.attackers(not user_color, sq)))
        user_center_control += user_attackers
        opp_center_control += opp_attackers
    
    if opp_center_control > user_center_control + 3:
        problems.append("your opponent has more pieces aimed at the center (d4, d5, e4, e5). This gives their pieces better squares to go to.")
    
    # Check for development issues (pieces still on back rank)
    undeveloped = 0
    back_rank_squares = [chess.B1, chess.C1, chess.F1, chess.G1] if user_color == chess.WHITE else [chess.B8, chess.C8, chess.F8, chess.G8]
    for sq in back_rank_squares:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
            undeveloped += 1
    
    if undeveloped >= 2:
        problems.append(f"you still have {undeveloped} pieces on the back rank that haven't moved. Get your knights and bishops out before attacking.")
    
    # Check for king safety (castling rights)
    if user_color == chess.WHITE:
        if not board.has_kingside_castling_rights(chess.WHITE) and not board.has_queenside_castling_rights(chess.WHITE):
            king_sq = board.king(chess.WHITE)
            if king_sq and chess.square_file(king_sq) in [3, 4]:  # King still in center
                problems.append("your king is stuck in the center and can't castle anymore. It's exposed to attacks.")
    else:
        if not board.has_kingside_castling_rights(chess.BLACK) and not board.has_queenside_castling_rights(chess.BLACK):
            king_sq = board.king(chess.BLACK)
            if king_sq and chess.square_file(king_sq) in [3, 4]:
                problems.append("your king is stuck in the center and can't castle anymore. It's exposed to attacks.")
    
    # Check for weak pawns
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type == chess.PAWN:
            # Check if pawn is isolated
            file = chess.square_file(sq)
            has_neighbor = False
            for neighbor_file in [file - 1, file + 1]:
                if 0 <= neighbor_file <= 7:
                    for rank in range(8):
                        neighbor_sq = chess.square(neighbor_file, rank)
                        neighbor_piece = board.piece_at(neighbor_sq)
                        if neighbor_piece and neighbor_piece.color == user_color and neighbor_piece.piece_type == chess.PAWN:
                            has_neighbor = True
                            break
            
            if not has_neighbor:
                sq_name = chess.square_name(sq)
                attackers = list(board.attackers(not user_color, sq))
                if attackers:
                    problems.append(f"your isolated pawn on {sq_name} is a target!")
                    break
    
    return problems


def _is_move_safe(board: chess.Board, move_san: str, user_color: bool) -> bool:
    """
    Check if a move is SAFE - doesn't hang the moving piece.
    
    A move is unsafe if:
    1. The piece lands on a square attacked by a lower-value piece
    2. The piece is a Queen/Rook and lands where it can be taken
    3. The piece becomes hanging (attacked with insufficient defense)
    """
    try:
        move = board.parse_san(move_san)
    except Exception:
        return False
    
    piece = board.piece_at(move.from_square)
    if not piece:
        return False
    
    # Simulate the move
    sim = board.copy()
    sim.push(move)
    
    to_square = move.to_square
    piece_value = _piece_value(piece)
    
    # Check if the piece is now attacked
    attackers = list(sim.attackers(not user_color, to_square))
    
    if not attackers:
        return True  # Not attacked = safe
    
    # Get defenders (excluding the piece itself)
    defenders = list(sim.attackers(user_color, to_square))
    
    # For each attacker, check if it's a bad trade
    min_attacker_value = float('inf')
    for attacker_sq in attackers:
        attacker = sim.piece_at(attacker_sq)
        if attacker:
            attacker_value = _piece_value(attacker)
            min_attacker_value = min(min_attacker_value, attacker_value)
    
    # If the cheapest attacker is worth less than our piece, it's a bad trade
    # Unless we have enough defenders to make it safe
    if min_attacker_value < piece_value:
        # Simple heuristic: if attacker is worth less AND we don't have more defenders than attackers
        if len(defenders) <= len(attackers):
            return False  # Losing material!
    
    # For Queen: be VERY careful - any attack is dangerous
    if piece.piece_type == chess.QUEEN:
        # Queen is attacked - check if we can recapture profitably
        if len(attackers) > 0 and len(defenders) < len(attackers):
            return False
        # If attacked by something worth less than queen (anything except another queen)
        if min_attacker_value < piece_value:
            return False
    
    # For Rook: careful about minor pieces
    if piece.piece_type == chess.ROOK:
        if min_attacker_value <= 3:  # Bishop or knight value
            if len(defenders) < len(attackers):
                return False
    
    return True


async def _get_stockfish_candidates(board: chess.Board, num_moves: int = 3, depth: int = 12) -> List[Dict]:
    """
    Use Stockfish multi-PV to get the TOP candidate moves.
    
    This ensures we only suggest moves that are actually GOOD according to the engine.
    Returns moves sorted by evaluation (best first).
    """
    candidates = []
    
    try:
        transport, engine = await chess.engine.popen_uci(STOCKFISH_PATH)
        
        try:
            # Multi-PV analysis to get top N moves
            result = await engine.analyse(
                board,
                chess.engine.Limit(depth=depth),
                multipv=num_moves
            )
            
            for info in result:
                if "pv" not in info or not info["pv"]:
                    continue
                
                move = info["pv"][0]
                san = board.san(move)
                
                # Get evaluation
                score = info.get("score")
                if score:
                    if score.is_mate():
                        cp = 10000 if score.relative.mate() > 0 else -10000
                    else:
                        cp = score.relative.score(mate_score=10000)
                else:
                    cp = 0
                
                # Get PV continuation
                pv_san = []
                temp_board = board.copy()
                for pv_move in info["pv"][:4]:
                    try:
                        pv_san.append(temp_board.san(pv_move))
                        temp_board.push(pv_move)
                    except Exception:
                        break
                
                candidates.append({
                    "move": san,
                    "eval_cp": cp,
                    "pv": pv_san,
                    "is_best": len(candidates) == 0  # First one is best
                })
        finally:
            await engine.quit()
            
    except Exception as e:
        logger.error(f"Stockfish multi-PV analysis failed: {e}")
    
    return candidates


def _analyze_candidate_moves(
    board_before: chess.Board,
    played_move: chess.Move,
    best_move_san: Optional[str],
    user_color: bool,
    stockfish_candidates: Optional[List[Dict]] = None
) -> List[Dict]:
    """
    Analyze candidate moves from Stockfish and explain the IDEA behind each.
    
    Uses STOCKFISH multi-PV data if available, otherwise falls back to best_move only.
    This ensures we only suggest moves that are actually GOOD.
    
    Each move gets categorized and explained:
    - counter_attack: Creates threats, gains initiative  
    - prophylactic: Prevents opponent's plan
    - development: Gets pieces into the game
    - central: Controls key squares
    - tactical: Wins material or creates threats
    """
    candidates = []
    played_san = board_before.san(played_move)
    
    # Use Stockfish candidates if available
    if stockfish_candidates:
        for sf_candidate in stockfish_candidates:
            move_san = sf_candidate.get("move")
            if move_san == played_san:
                continue  # Skip the move that was actually played
            
            # Get the idea behind this Stockfish-approved move
            idea = _explain_move_idea(board_before, move_san, user_color)
            
            if idea:
                candidates.append({
                    "move": move_san,
                    "idea": idea["explanation"],
                    "type": idea["type"],
                    "is_best": sf_candidate.get("is_best", False),
                    "eval_cp": sf_candidate.get("eval_cp")
                })
            else:
                # Fallback explanation if our heuristics don't match
                candidates.append({
                    "move": move_san,
                    "idea": f"{move_san} is a strong move here according to the engine",
                    "type": "engine_choice",
                    "is_best": sf_candidate.get("is_best", False),
                    "eval_cp": sf_candidate.get("eval_cp")
                })
    
    # If no Stockfish candidates, use just the best move
    elif best_move_san:
        idea = _explain_move_idea(board_before, best_move_san, user_color)
        if idea:
            candidates.append({
                "move": best_move_san,
                "idea": idea["explanation"],
                "type": idea["type"],
                "is_best": True
            })
        else:
            candidates.append({
                "move": best_move_san,
                "idea": f"{best_move_san} was the best move here",
                "type": "engine_choice",
                "is_best": True
            })
    
    return candidates[:3]


def _explain_move_idea(board: chess.Board, move_san: str, user_color: bool) -> Optional[Dict]:
    """
    Explain the strategic idea behind a specific move.
    Returns the idea type, explanation, and a quality score.
    """
    try:
        move = board.parse_san(move_san)
    except Exception:
        return None
    
    piece = board.piece_at(move.from_square)
    if not piece:
        return None
    
    sim = board.copy()
    sim.push(move)
    
    to_sq = move.to_square
    to_file = chess.square_file(to_sq)
    to_rank = chess.square_rank(to_sq)
    
    # Check different move ideas
    ideas = []
    
    # 1. COUNTER-ATTACK: Does this move create a threat?
    threats_created = []
    for sq in chess.SQUARES:
        opp_piece = sim.piece_at(sq)
        if opp_piece and opp_piece.color != user_color:
            if sim.is_attacked_by(user_color, sq):
                # Was it attacked before?
                if not board.is_attacked_by(user_color, sq):
                    threats_created.append(_get_fun_piece_name(opp_piece))
    
    if threats_created:
        target = threats_created[0]
        ideas.append({
            "type": "counter_attack",
            "explanation": f"{move_san} attacks their {target} - forces them to respond!",
            "score": 8 if "Queen" in target or "Tower" in target else 5
        })
    
    # 2. PROPHYLACTIC: Does this move prevent an opponent threat?
    # Check if move blocks or prevents an attack
    if piece.piece_type == chess.PAWN:
        # Check for moves like a6/h6 that prevent piece invasions
        # a6 prevents Bb5 or Nb5, h6 prevents Bg5 or Ng5
        prophylactic_targets = {
            # Black pawns preventing White pieces
            chess.A6: [(chess.B5, "Bb5"), (chess.B5, "Nb5")],
            chess.H6: [(chess.G5, "Bg5"), (chess.G5, "Ng5")],
            chess.A3: [(chess.B4, "Bb4"), (chess.B4, "Nb4")],
            chess.H3: [(chess.G4, "Bg4"), (chess.G4, "Ng4")],
            # White pawns preventing Black pieces
            chess.A3: [(chess.B4, "Bb4"), (chess.B4, "Nb4")],
            chess.H3: [(chess.G4, "Bg4"), (chess.G4, "Ng4")],
        }
        
        if to_sq in prophylactic_targets:
            for target_sq, piece_name in prophylactic_targets[to_sq]:
                # Check if opponent could have played this move
                opp_color = not user_color
                for opp_move in board.legal_moves:
                    if opp_move.to_square == target_sq:
                        opp_piece = board.piece_at(opp_move.from_square)
                        if opp_piece and opp_piece.color == opp_color:
                            ideas.append({
                                "type": "prophylactic",
                                "explanation": f"{move_san} stops {piece_name} - no invasion allowed!",
                                "score": 5
                            })
                            break
        
        # Generic prophylactic check for pawn moves on the wings
        if to_file in [0, 7]:  # a or h pawn
            # Check if this stops a knight/bishop invasion to b5/g5
            invasion_squares = []
            if user_color == chess.BLACK:
                invasion_squares = [chess.B5, chess.G5] if to_file == 0 else [chess.G5, chess.B5]
            else:
                invasion_squares = [chess.B4, chess.G4] if to_file == 0 else [chess.G4, chess.B4]
            
            for inv_sq in invasion_squares:
                if board.is_attacked_by(not user_color, inv_sq):
                    ideas.append({
                        "type": "prophylactic",
                        "explanation": f"{move_san} prevents their piece from invading {chess.square_name(inv_sq)}",
                        "score": 4
                    })
                    break
        
        # Check if pawn stops piece from coming to a square
        blocked_squares = [to_sq + 8, to_sq + 9, to_sq + 7] if user_color == chess.WHITE else [to_sq - 8, to_sq - 9, to_sq - 7]
        for bsq in blocked_squares:
            if 0 <= bsq < 64 and board.is_attacked_by(not user_color, bsq):
                ideas.append({
                    "type": "prophylactic",
                    "explanation": f"{move_san} blocks their piece from reaching {chess.square_name(bsq)}",
                    "score": 3
                })
                break
    
    # 3. DEVELOPMENT: Is this developing a piece?
    if piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
        back_rank = 0 if user_color == chess.WHITE else 7
        if chess.square_rank(move.from_square) == back_rank:
            # Check if it's going to a good square
            center_distance = abs(to_file - 3.5) + abs(to_rank - 3.5)
            if center_distance < 3:
                ideas.append({
                    "type": "development",
                    "explanation": f"{move_san} develops with a purpose - aims at the center",
                    "score": 6
                })
            else:
                ideas.append({
                    "type": "development",
                    "explanation": f"{move_san} develops a piece toward the center",
                    "score": 4
                })
    
    # 4. CENTRAL CONTROL: Does this move improve center control?
    center_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
    if to_sq in center_squares:
        if piece.piece_type == chess.PAWN:
            # Distinguish first central push (d2-d4) from break (d3-d4).
            # Both land on d4 but they're different ideas: the first
            # OCCUPIES the center; the second CHALLENGES the opposing
            # pawn that already contests the center. Same words for both
            # produces nonsense like "puts your pawn in the center" when
            # the pawn was already on d3.
            from_rank = chess.square_rank(move.from_square)
            is_first_push = (
                (user_color == chess.WHITE and from_rank == 1)
                or (user_color == chess.BLACK and from_rank == 6)
            )
            if is_first_push:
                ideas.append({
                    "type": "central",
                    "explanation": f"{move_san} puts your pawn in the center where it controls the most squares",
                    "score": 7,
                })
            else:
                # Identify the enemy pawn this break now attacks, if any.
                attacked_pawn_sq = None
                for atk_sq in sim.attacks(to_sq):
                    p = sim.piece_at(atk_sq)
                    if p and p.color != user_color and p.piece_type == chess.PAWN:
                        attacked_pawn_sq = atk_sq
                        break
                if attacked_pawn_sq is not None:
                    ideas.append({
                        "type": "central",
                        "explanation": f"{move_san} strikes at their pawn on {chess.square_name(attacked_pawn_sq)} and opens the center",
                        "score": 7,
                    })
                else:
                    ideas.append({
                        "type": "central",
                        "explanation": f"{move_san} pushes forward in the center and opens lines",
                        "score": 7,
                    })
        else:
            placed_name = chess.piece_name(piece.piece_type)
            ideas.append({
                "type": "central",
                "explanation": f"{move_san} puts your {placed_name} in the center where it controls the most squares",
                "score": 7,
            })
    elif piece.piece_type == chess.PAWN and to_file in [3, 4]:  # d or e file
        ideas.append({
            "type": "central",
            "explanation": f"{move_san} fights for central space",
            "score": 5
        })
    
    # 5. CASTLING: King safety
    if board.is_castling(move):
        ideas.append({
            "type": "king_safety",
            "explanation": f"{move_san} castles your king to safety and connects your rooks",
            "score": 7
        })
    
    # 6. TACTICAL: Check or capture
    if sim.is_check():
        ideas.append({
            "type": "tactical",
            "explanation": f"{move_san} gives check — your opponent must respond to this first",
            "score": 6
        })
    
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured:
            attacker_value = _piece_value(piece)
            captured_value = _piece_value(captured)
            captured_name = _get_fun_piece_name(captured)
            attacker_name = _get_fun_piece_name(piece)
            to_sq_name = chess.square_name(move.to_square)
            if captured_value > attacker_value:
                ideas.append({
                    "type": "tactical",
                    "explanation": f"{move_san} takes their {captured_name} on {to_sq_name} with your {attacker_name} — winning material",
                    "score": 9
                })
            elif captured_value == attacker_value:
                # Equal trade — explain WHY it might be good (removes a defender, etc.)
                sim_after = board.copy()
                sim_after.push(move)
                # Check if this creates new threats
                new_threats = []
                for sq in chess.SQUARES:
                    target = sim_after.piece_at(sq)
                    if target and target.color != piece.color and target.piece_type not in (chess.PAWN, chess.KING):
                        if sim_after.is_attacked_by(piece.color, sq) and not board.is_attacked_by(piece.color, sq):
                            new_threats.append(f"{_get_fun_piece_name(target)} on {chess.square_name(sq)}")
                if new_threats:
                    ideas.append({
                        "type": "tactical",
                        "explanation": f"{move_san} trades {attacker_name} for their {captured_name} and reveals an attack on their {new_threats[0]}",
                        "score": 9
                    })
                else:
                    ideas.append({
                        "type": "tactical",
                        "explanation": f"{move_san} captures their {captured_name} on {to_sq_name}",
                        "score": 7
                    })
    
    # Return the best idea for this move
    if ideas:
        ideas.sort(key=lambda x: x["score"], reverse=True)
        return ideas[0]
    
    return None




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
    board_after: chess.Board,
    played_move: chess.Move,
    pv: List[str],
    cp_loss: int,
    played_san: str
) -> Optional[ChessPlan]:
    """Detect if the move allows a tactical pattern."""
    if cp_loss < 100:
        return None
    
    tactical_patterns = get_theory_data("tactical_patterns")
    
    # Board already has the move played
    sim = board_after.copy()
    user_color = not board_after.turn  # The user just moved
    
    if pv:
        try:
            opp_response = sim.parse_san(pv[0])
            
            # Check for fork
            if sim.piece_at(opp_response.from_square):
                if sim.piece_at(opp_response.from_square).piece_type == chess.KNIGHT:
                    # Check if THIS SPECIFIC knight attacks multiple pieces after moving
                    sim2 = sim.copy()
                    sim2.push(opp_response)
                    knight_landing = opp_response.to_square
                    # Only check squares attacked by THIS knight (not all opponent pieces)
                    knight_attacks = sim2.attacks(knight_landing)
                    attacked = []
                    attacked_values = []
                    for sq in knight_attacks:
                        piece = sim2.piece_at(sq)
                        if piece and piece.color == user_color and piece.piece_type != chess.PAWN:
                            piece_name = _get_fun_piece_name(piece)
                            attacked.append(piece_name)
                            attacked_values.append(_piece_value(piece))

                    # Fork detected if attacking 2+ valuable pieces (total value >= 5)
                    if len(attacked) >= 2 and sum(attacked_values) >= 5:
                        attacked_with_values = list(zip(attacked, attacked_values))
                        attacked_with_values.sort(key=lambda x: x[1], reverse=True)
                        piece1 = attacked_with_values[0][0]
                        piece2 = attacked_with_values[1][0]

                        return ChessPlan(
                            goal="Avoid knight forks",
                            current_problem=f"{played_san} allows a knight fork — their knight can attack two of your pieces at once.",
                            consequence=f"After {pv[0]}, their knight attacks your {piece1} and {piece2}. You can only save one.",
                            better_approach=f"Before playing {played_san}, check: can a knight jump to a square that attacks two of my pieces?",
                            transferable_learning=f"A knight fork happens when one knight attacks two valuable pieces at once. You lose one of them. Always check if your {piece1} and {piece2} can both be reached by one knight jump.",
                            concept_id="knight_fork",
                            concept_type="tactical"
                        )
            
            # Check for back rank issues — ONLY if:
            # 1. It's middlegame or later (move > 20)
            # 2. King is actually on the back rank
            # 3. The check is from a rook or queen (not a minor piece)
            move_count = board_after.fullmove_number or (len(sim.move_stack) // 2)
            checking_piece = sim.piece_at(opp_response.from_square) if opp_response else None
            is_heavy_piece_check = checking_piece and checking_piece.piece_type in (chess.ROOK, chess.QUEEN)
            if sim.is_check() and move_count > 20 and is_heavy_piece_check:
                king_sq = sim.king(user_color)
                if king_sq and chess.square_rank(king_sq) in [0, 7]:
                    pattern = tactical_patterns.get("back_rank_weakness", {})
                    return ChessPlan(
                        goal="Protect your back rank",
                        current_problem=f"{played_san} leaves your back rank weak. Your king has no escape square.",
                        consequence=f"After {pv[0]}, your opponent threatens checkmate on the back rank.",
                        better_approach="Push h3 or g3 to give your king an escape square before this becomes a problem.",
                        transferable_learning=pattern.get("rule", "If your king is on the back rank with no escape square, a rook or queen can checkmate you. Push one pawn (h3 or g3) to create a way out."),
                        concept_id="back_rank_weakness",
                        concept_type="tactical"
                    )
        except Exception:
            pass
    
    return None


def _generate_generic_plan(
    board_after: chess.Board,
    played_san: str,
    piece_type: Optional[int],
    to_square: int,
    best_move: Optional[str],
    pv_after_played: List[str],
    cp_loss: int,
    board_before: Optional[chess.Board] = None,
    played_move: Optional[chess.Move] = None,
    stockfish_candidates: Optional[List[Dict]] = None
) -> ChessPlan:
    """
    Generate a plan with FUN language, SPECIFIC consequences, and STOCKFISH candidate moves.
    
    Key improvement: Uses Stockfish multi-PV for candidate moves (not pattern matching).
    """
    
    # Analyze what went wrong SPECIFICALLY
    consequence = _describe_consequence(pv_after_played, board_after)
    
    # Get candidate moves with their ideas - NOW FROM STOCKFISH!
    candidate_moves = []
    if board_before and played_move:
        user_color = board_before.turn
        candidate_moves = _analyze_candidate_moves(
            board_before, played_move, best_move, user_color,
            stockfish_candidates=stockfish_candidates
        )
    
    # Build a rich "better approach" from candidates
    better_approach = _format_better_approach(candidate_moves, best_move)
    
    # Determine transferable learning based on the candidate types
    transferable_learning = _derive_transferable_learning(candidate_moves, piece_type, to_square)
    
    # ── Build concrete, board-specific explanation ──
    sq_name = chess.square_name(to_square)

    if piece_type == chess.KNIGHT:
        if chess.square_file(to_square) in [0, 7] or chess.square_rank(to_square) in [0, 7]:
            return ChessPlan(
                goal="Keep your knight active",
                current_problem=f"{played_san} puts your knight on the edge of the board where it only controls a few squares.",
                consequence=consequence,
                better_approach=better_approach or f"{best_move} keeps the knight near the center where it controls more squares.",
                transferable_learning=transferable_learning or "A knight on the edge controls 2-4 squares. In the center it controls 8. Always prefer central squares for knights.",
                concept_id="knight_on_rim",
                concept_type="positional",
                candidate_moves=candidate_moves
            )
        else:
            return ChessPlan(
                goal="Make your knight do something",
                current_problem=f"{played_san} moves your knight but it doesn't attack anything or defend anything important.",
                consequence=consequence,
                better_approach=better_approach or f"{best_move} was better here.",
                transferable_learning=transferable_learning or "Before moving a piece, ask: what will it attack or defend from the new square?",
                concept_id="piece_without_purpose",
                concept_type="positional",
                candidate_moves=candidate_moves
            )

    elif piece_type == chess.BISHOP:
        # Before defaulting to "blocked diagonal", check what the bishop
        # ACTUALLY does on its new square. If it attacks a high-value
        # enemy piece, the move is tactical, not positional — name the
        # attack target. Source bug: fb_1dbdb06502eb (Bg4 attacks queen
        # but caption said "pawns block its diagonal" — wrong reason).
        bishop_target_phrase = None
        try:
            opp_color = not board_after.turn  # bishop just moved, so it
                                              # belongs to side that just moved
            attacked_pieces = []
            for attacked_sq in board_after.attacks(to_square):
                p = board_after.piece_at(attacked_sq)
                if (
                    p
                    and p.color != opp_color
                    and p.piece_type != chess.PAWN
                    and p.piece_type != chess.KING  # checks are not "attacks on pieces" in this template
                ):
                    attacked_pieces.append((p, attacked_sq))
            # Prefer queens, then rooks, then minor pieces.
            attacked_pieces.sort(key=lambda x: -_piece_value(x[0]))
            if attacked_pieces:
                target_piece, target_sq = attacked_pieces[0]
                target_name = get_piece_name(target_piece)
                target_sq_name = chess.square_name(target_sq)
                bishop_target_phrase = (
                    f"{played_san} attacks their {target_name} on {target_sq_name}, "
                    f"but it's still a mistake here — see what comes next."
                )
        except Exception:
            bishop_target_phrase = None

        if bishop_target_phrase:
            return ChessPlan(
                goal="Make your move count tactically",
                current_problem=bishop_target_phrase,
                consequence=consequence,
                better_approach=better_approach or (f"{best_move} was better." if best_move else ""),
                transferable_learning=transferable_learning or "Attacking a piece isn't always good — check whether your opponent has a strong reply that punishes the attacker.",
                concept_id="bishop_tactical_attack",
                concept_type="tactical",
                candidate_moves=candidate_moves
            )

        return ChessPlan(
            goal="Keep your bishop on an open diagonal",
            current_problem=f"{played_san} puts your bishop where pawns block its diagonal. It can't do much from {sq_name}.",
            consequence=consequence,
            better_approach=better_approach or f"{best_move} gives the bishop a longer diagonal with more targets.",
            transferable_learning=transferable_learning or "Bishops are strongest on long, open diagonals. If your own pawns block it, look for a better diagonal.",
            concept_id="blocked_bishop",
            concept_type="positional",
            candidate_moves=candidate_moves
        )

    elif piece_type == chess.PAWN:
        return ChessPlan(
            goal="Be careful with pawn moves",
            current_problem=f"{played_san} pushes a pawn that can't come back. This weakens the squares around it.",
            consequence=consequence,
            better_approach=better_approach or f"{best_move} was safer.",
            transferable_learning=transferable_learning or "Pawns can never move backwards. Every pawn push creates squares that can't be defended by pawns anymore.",
            concept_id="premature_pawn",
            concept_type="positional",
            candidate_moves=candidate_moves
        )

    else:
        return ChessPlan(
            goal="Check what your opponent can do",
            current_problem=f"{played_san} has a problem — look at what your opponent can do next.",
            consequence=consequence,
            better_approach=better_approach or f"{best_move} was the better move here.",
            transferable_learning=transferable_learning or "Before every move, ask yourself: what can my opponent do after this? Check for captures, checks, and threats.",
            concept_id="generic_mistake",
            concept_type="general",
            candidate_moves=candidate_moves
        )


def _format_better_approach(candidates: List[Dict], best_move: Optional[str]) -> str:
    """
    Format the candidate moves into a readable "better approach" string.
    Shows the main idea, not just the move.
    """
    if not candidates:
        return f"{best_move} was better" if best_move else ""
    
    # Get the best move's idea
    best_candidate = candidates[0] if candidates else None
    if best_candidate:
        return best_candidate.get("idea", f"{best_move} was better")
    
    return f"{best_move} was better" if best_move else ""


def _derive_transferable_learning(
    candidates: List[Dict],
    piece_type: Optional[int],
    to_square: int
) -> str:
    """
    Derive a transferable learning from the candidate moves.
    This teaches the PATTERN, not just the move.
    """
    if not candidates:
        return ""
    
    # Analyze the types of good moves available
    move_types = [c.get("type", "") for c in candidates]
    
    # If there was a counter-attack available
    if "counter_attack" in move_types:
        return "When your opponent attacks, don't just defend. Look for your own threat that's even stronger."

    if "prophylactic" in move_types:
        return "Ask: what does my opponent want to do next? If you can stop their plan first, you take control."

    if "development" in move_types:
        return "Bring your pieces out to squares where they point at the center or at your opponent's weak spots."

    if "central" in move_types:
        return "Pieces in the center control more squares. A knight on e4 is much stronger than a knight on a3."

    if len(set(move_types)) >= 2:
        return "There were several good moves here. When you have choices, pick the one that improves your worst-placed piece."
    
    return ""


# ─── OPPONENT MOVE ANALYSIS ──────────────────────────────────────────

def analyze_opponent_move(
    board: chess.Board,
    move: chess.Move,
    eval_before: Optional[int],
    eval_after: Optional[int],
    pv_after: List[str],
    user_color: str,
    move_history_san: Optional[List[str]] = None,
    full_move_number: Optional[int] = None,
) -> Tuple[str, Optional[str], List[str]]:
    """
    Analyze opponent's move from USER's perspective with EDUCATIONAL depth.
    
    When opponent makes a mistake, we explain:
    1. WHAT they weakened (specific squares, diagonals, pieces)
    2. HOW to punish it (best move and why)
    3. THE PATTERN to remember
    
    Returns: (narrative, your_plan_now, highlight_squares)
    """
    board.san(move)
    
    # Calculate eval swing from user's perspective
    eval_swing = 0
    if eval_before is not None and eval_after is not None:
        if user_color == "white":
            eval_swing = eval_after - eval_before
        else:
            eval_swing = eval_before - eval_after
    
    highlight_squares = []
    your_plan_now = None
    
    # Simulate the position after opponent's move
    sim = board.copy()
    sim.push(move)
    user_is_white = (user_color == "white")
    
    # Get the best response from PV
    best_response = pv_after[0] if pv_after else None
    
    # Opponent made a significant mistake (100+ centipawns swing)
    if eval_swing >= 100:
        narrative, your_plan_now, highlight_squares = _analyze_opponent_mistake(
            board, move, sim, eval_swing, best_response, user_is_white, pv_after
        )
    
    # Opponent played a normal move
    elif abs(eval_swing) < 50:
        narrative, your_plan_now = _explain_opponent_move_with_context(
            board, move, user_color, pv_after,
            move_history_san=move_history_san,
            full_move_number=full_move_number,
        )
    
    # Small inaccuracy (50-100 cp)
    else:
        narrative, your_plan_now, highlight_squares = _analyze_opponent_slip(
            board, move, sim, eval_swing, best_response, user_is_white
        )
    
    return narrative, your_plan_now, highlight_squares


def _analyze_opponent_mistake(
    board_before: chess.Board,
    move: chess.Move,
    board_after: chess.Board,
    eval_swing: int,
    best_response: Optional[str],
    user_is_white: bool,
    pv_after: List[str]
) -> Tuple[str, str, List[str]]:
    """
    Deeply analyze opponent's mistake to create educational content.
    
    Looks for:
    - Weakened squares (especially around their king)
    - Hanging pieces
    - Tactical vulnerabilities (pins, forks, discoveries)
    - Pawn structure damage
    """
    move_san = board_before.san(move)
    highlight_squares = []
    
    # What type of mistake was this?
    piece_moved = board_before.piece_at(move.from_square)
    is_pawn_move = piece_moved and piece_moved.piece_type == chess.PAWN
    to_sq = move.to_square
    to_file = chess.square_file(to_sq)
    to_rank = chess.square_rank(to_sq)
    
    # ─── 1. CHECK FOR HANGING PIECES ───
    hanging_pieces = _find_hanging_pieces(board_after, not user_is_white)
    if hanging_pieces:
        piece_info = hanging_pieces[0]
        highlight_squares = [piece_info["square"]]
        
        if best_response:
            narrative = f"{move_san} leaves their {piece_info['name']} on {piece_info['square']} undefended! {best_response} wins it."
            your_plan_now = f"Capture the hanging {piece_info['name']} with {best_response}!"
        else:
            narrative = f"{move_san} leaves their {piece_info['name']} on {piece_info['square']} hanging!"
            your_plan_now = f"Take the free {piece_info['name']}!"
        
        return narrative, your_plan_now, highlight_squares
    
    # ─── 2. CHECK FOR WEAKENED KING POSITION ───
    opp_king_sq = board_after.king(not user_is_white)
    if opp_king_sq and is_pawn_move:
        king_file = chess.square_file(opp_king_sq)
        king_rank = chess.square_rank(opp_king_sq)
        
        # Did they weaken squares near their king?
        if abs(to_file - king_file) <= 2 and abs(to_rank - king_rank) <= 2:
            weakened = _find_weakened_squares_near_king(board_before, board_after, opp_king_sq, user_is_white)
            if weakened:
                highlight_squares = weakened[:3]
                sq_names = ", ".join(weakened[:2])
                
                if best_response:
                    # Try to explain what best_response does
                    response_explanation = _explain_response_idea(board_after, best_response, user_is_white, weakened)
                    narrative = f"{move_san} weakens the squares {sq_names} around their king. {response_explanation}"
                    your_plan_now = f"Target {sq_names} — their king's defenses are compromised!"
                else:
                    narrative = f"{move_san} creates holes on {sq_names}. Their king is exposed!"
                    your_plan_now = f"Attack the weak squares: {sq_names}"
                
                return narrative, your_plan_now, highlight_squares
    
    # ─── 3. CHECK FOR TACTICAL VULNERABILITIES ───
    # Look for pins, forks, discoveries that are now possible
    tactics = _find_tactical_opportunities(board_after, user_is_white)
    if tactics:
        tactic = tactics[0]
        highlight_squares = tactic.get("squares", [])
        
        if best_response:
            narrative = f"{move_san} allows {tactic['type']}! {best_response} {tactic['description']}"
        else:
            narrative = f"{move_san} allows a {tactic['type']}! {tactic['description']}"
        your_plan_now = tactic.get("plan", "Look for the tactic!")
        
        return narrative, your_plan_now, highlight_squares
    
    # ─── 4. CHECK FOR PIECE ACTIVITY LOSS ───
    if piece_moved:
        activity_issue = _check_piece_activity_loss(board_before, board_after, move, not user_is_white)
        if activity_issue:
            if best_response:
                narrative = f"{move_san} {activity_issue['problem']}. {best_response} takes advantage — {activity_issue['exploitation']}."
            else:
                narrative = f"{move_san} {activity_issue['problem']}."
            your_plan_now = activity_issue.get("plan", "Exploit their passive piece!")
            return narrative, your_plan_now, highlight_squares
    
    # ─── 5. FALLBACK: Explain based on best response ───
    if best_response:
        response_idea = _explain_response_idea(board_after, best_response, user_is_white, [])
        if response_idea and "Unknown" not in response_idea:
            narrative = f"{move_san} is a mistake. {response_idea}"
            your_plan_now = f"Play {best_response}!"
            return narrative, your_plan_now, highlight_squares
    
    # Last resort - at least mention the eval swing
    pawn_swing = eval_swing / 100
    narrative = f"{move_san} loses about {pawn_swing:.1f} pawns worth of advantage."
    your_plan_now = f"Look for the best continuation — you're winning here!"
    
    return narrative, your_plan_now, highlight_squares


def _analyze_opponent_slip(
    board_before: chess.Board,
    move: chess.Move,
    board_after: chess.Board,
    eval_swing: int,
    best_response: Optional[str],
    user_is_white: bool
) -> Tuple[str, str, List[str]]:
    """Analyze a small opponent inaccuracy (50-100 cp)."""
    move_san = board_before.san(move)
    highlight_squares = []
    
    if best_response:
        response_idea = _explain_response_idea(board_after, best_response, user_is_white, [])
        if response_idea and "Unknown" not in response_idea:
            narrative = f"{move_san} is slightly passive. {response_idea}"
            your_plan_now = f"{best_response} improves your position."
            return narrative, your_plan_now, highlight_squares
    
    pawn_swing = eval_swing / 100
    narrative = f"{move_san} gives you a small edge (+{pawn_swing:.1f})."
    your_plan_now = "You're slightly better — keep up the pressure!"
    
    return narrative, your_plan_now, highlight_squares


def _find_hanging_pieces(board: chess.Board, color: bool) -> List[Dict]:
    """Find pieces that are attacked but not defended."""
    hanging = []
    
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == color and piece.piece_type != chess.KING:
            attackers = list(board.attackers(not color, sq))
            defenders = list(board.attackers(color, sq))
            
            if attackers and not defenders:
                hanging.append({
                    "square": chess.square_name(sq),
                    "name": get_piece_name(piece),
                    "value": _piece_value(piece)
                })
    
    # Sort by value (most valuable first)
    hanging.sort(key=lambda x: x["value"], reverse=True)
    return hanging


def _find_weakened_squares_near_king(
    board_before: chess.Board,
    board_after: chess.Board,
    king_sq: int,
    user_is_white: bool
) -> List[str]:
    """Find squares near the king that became weaker after the move."""
    weakened = []
    king_file = chess.square_file(king_sq)
    king_rank = chess.square_rank(king_sq)
    
    # Check squares in the king's vicinity
    for df in [-1, 0, 1]:
        for dr in [-1, 0, 1]:
            if df == 0 and dr == 0:
                continue
            
            f = king_file + df
            r = king_rank + dr
            if 0 <= f <= 7 and 0 <= r <= 7:
                sq = chess.square(f, r)
                
                # Check if this square was defended before but not after
                defenders_before = len(list(board_before.attackers(not user_is_white, sq)))
                defenders_after = len(list(board_after.attackers(not user_is_white, sq)))
                
                # Also check if we can now attack it
                our_attackers = len(list(board_after.attackers(user_is_white, sq)))
                
                if defenders_after < defenders_before or (our_attackers > 0 and defenders_after == 0):
                    weakened.append(chess.square_name(sq))
    
    return weakened


def _find_tactical_opportunities(board: chess.Board, user_is_white: bool) -> List[Dict]:
    """Find tactical opportunities (forks, pins, etc.) in the position."""
    tactics = []
    
    # Check for knight fork opportunities
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_is_white and piece.piece_type == chess.KNIGHT:
            for target_sq in board.attacks(sq):
                target = board.piece_at(target_sq)
                if target and target.color != user_is_white:
                    # Check if moving the knight here creates a fork
                    for knight_move in board.legal_moves:
                        if knight_move.from_square == sq:
                            sim = board.copy()
                            sim.push(knight_move)
                            attacked = []
                            for attacked_sq in sim.attacks(knight_move.to_square):
                                attacked_piece = sim.piece_at(attacked_sq)
                                if attacked_piece and attacked_piece.color != user_is_white:
                                    if attacked_piece.piece_type in [chess.QUEEN, chess.ROOK, chess.KING]:
                                        attacked.append(attacked_piece)
                            
                            if len(attacked) >= 2:
                                tactics.append({
                                    "type": "knight fork",
                                    "squares": [chess.square_name(knight_move.to_square)],
                                    "description": "the knight forks two pieces.",
                                    "plan": f"Look for {board.san(knight_move)}."
                                })
                                return tactics
    
    return tactics


def _check_piece_activity_loss(
    board_before: chess.Board,
    board_after: chess.Board,
    move: chess.Move,
    piece_color: bool
) -> Optional[Dict]:
    """Check if the move made a piece less active."""
    piece = board_before.piece_at(move.from_square)
    if not piece:
        return None
    
    # Count controlled squares before and after
    attacks_before = len(list(board_before.attacks(move.from_square)))
    attacks_after = len(list(board_after.attacks(move.to_square)))
    
    if attacks_after < attacks_before - 2:
        piece_name = get_piece_name(piece)
        return {
            "problem": f"puts their {piece_name} on a passive square",
            "exploitation": "your pieces have more freedom now",
            "plan": "Take the center. Their piece can't stop you from there."
        }
    
    # Check if piece is now blocked
    if piece.piece_type == chess.BISHOP:
        # Check if bishop's diagonals are blocked by own pawns
        blocked_by_pawns = 0
        for diag_sq in board_after.attacks(move.to_square):
            blocker = board_after.piece_at(diag_sq)
            if blocker and blocker.color == piece_color and blocker.piece_type == chess.PAWN:
                blocked_by_pawns += 1
        
        if blocked_by_pawns >= 2:
            return {
                "problem": "blocks their own bishop behind pawns",
                "exploitation": "their bishop is buried — does nothing",
                "plan": "Your pieces are more active. Press your advantage."
            }
    
    return None


def _explain_response_idea(
    board: chess.Board,
    response_san: str,
    user_is_white: bool,
    weak_squares: List[str]
) -> str:
    """
    Explain what the best response achieves - EDUCATIONAL version.
    
    Goes beyond just naming the move - explains the IDEA.
    """
    try:
        move = board.parse_san(response_san)
    except:
        return f"Unknown response."
    
    piece = board.piece_at(move.from_square)
    if not piece:
        return f"Unknown response."
    
    sim = board.copy()
    is_capture = board.is_capture(move)
    sim.push(move)
    
    get_piece_name(piece)
    to_sq = move.to_square
    to_file = chess.square_file(to_sq)
    to_rank = chess.square_rank(to_sq)
    
    # ─── PAWN MOVES - Often the most instructive ───
    if piece.piece_type == chess.PAWN:
        # Pawn break - check if this pawn attacks enemy pawns/pieces
        attacked_by_pawn = list(sim.attacks(to_sq))
        enemy_pieces_attacked = [sq for sq in attacked_by_pawn 
                                  if sim.piece_at(sq) and sim.piece_at(sq).color != user_is_white]
        
        # Central pawn break (d5, e5, d4, e4 type moves)
        if to_sq in [chess.D5, chess.E5, chess.D4, chess.E4, chess.E6, chess.D6]:
            chess.square_name(to_sq)
            # Check what it opens
            if sim.is_check():
                return f"{response_san} breaks through with check! The center is torn open."
            
            # Check if it attacks pieces
            for attacked_sq in attacked_by_pawn:
                attacked = sim.piece_at(attacked_sq)
                if attacked and attacked.color != user_is_white and attacked.piece_type != chess.PAWN:
                    return f"{response_san} breaks in the center, attacking their {get_piece_name(attacked)}! This blows open the position."
            
            return f"{response_san} is a powerful pawn break! It opens lines and creates threats. h6 weakened this possibility."
        
        # Attacking pawn — detect forks (2+ non-pawn pieces attacked
        # simultaneously). Source bug: fb_c45f3552e4d9 said "f6 attacks
        # their knight" when f6 actually forked bishop + knight.
        if enemy_pieces_attacked:
            non_pawn_targets = [
                sq for sq in enemy_pieces_attacked
                if sim.piece_at(sq) and sim.piece_at(sq).piece_type != chess.PAWN
            ]
            if len(non_pawn_targets) >= 2:
                names = sorted({
                    get_piece_name(sim.piece_at(sq)) for sq in non_pawn_targets
                })
                if len(names) >= 2:
                    return (
                        f"{response_san} forks the {names[0]} and {names[1]} — "
                        f"double attack, you win material."
                    )
                # Two pieces of the same type forked (e.g., two knights)
                return (
                    f"{response_san} forks two {names[0]}s — "
                    f"double attack, you win material."
                )
            attacked = sim.piece_at(enemy_pieces_attacked[0])
            if attacked:
                return f"{response_san} attacks their {get_piece_name(attacked)}."
        
        # Passed pawn creation
        # Check if there are no enemy pawns in front
        is_passed = True
        for r in range(to_rank + 1, 8) if user_is_white else range(0, to_rank):
            for f in [to_file - 1, to_file, to_file + 1]:
                if 0 <= f <= 7:
                    sq = chess.square(f, r)
                    p = sim.piece_at(sq)
                    if p and p.piece_type == chess.PAWN and p.color != user_is_white:
                        is_passed = False
                        break
        
        if is_passed:
            return f"{response_san} creates a dangerous passed pawn!"
    
    # ─── CAPTURES ───
    if is_capture:
        captured = board.piece_at(to_sq)
        if captured:
            captured_name = get_piece_name(captured)
            attacker_value = _piece_value(piece)
            captured_value = _piece_value(captured)
            
            if captured_value > attacker_value:
                return f"{response_san} wins the {captured_name}! Free material."
            elif captured_value == attacker_value:
                # Check if recapture is problematic
                defenders = list(sim.attackers(not user_is_white, to_sq))
                if not defenders:
                    return f"{response_san} takes the {captured_name} for free — no recapture!"
                return f"{response_san} trades off the {captured_name}."
            else:
                return f"{response_san} wins the {captured_name}."
    
    # ─── CHECKS ───
    if sim.is_check():
        # Analyze what kind of check
        # Is it a discovered check?
        if piece.piece_type not in [chess.QUEEN, chess.ROOK, chess.BISHOP]:
            # The checking piece might be different
            opp_king = sim.king(not user_is_white)
            checkers = list(sim.attackers(user_is_white, opp_king))
            for checker_sq in checkers:
                checker = sim.piece_at(checker_sq)
                if checker and checker_sq != to_sq:
                    return f"{response_san} unleashes a discovered check! Devastating."
        
        return f"{response_san} gives check, forcing their king to move."
    
    # ─── ATTACKS ON VALUABLE PIECES (with fork detection) ───
    # Collect every enemy non-pawn piece this move attacks. If 2+, name
    # the fork explicitly. If 1, fall back to the single-target template.
    enemy_targets = []
    for attacked_sq in sim.attacks(to_sq):
        attacked = sim.piece_at(attacked_sq)
        if attacked and attacked.color != user_is_white and attacked.piece_type != chess.PAWN:
            enemy_targets.append(attacked)
    if len(enemy_targets) >= 2:
        names = sorted({get_piece_name(p) for p in enemy_targets})
        if len(names) >= 2:
            return (
                f"{response_san} forks the {names[0]} and {names[1]} — "
                f"double attack, you win material."
            )
        return (
            f"{response_san} forks two {names[0]}s — "
            f"double attack, you win material."
        )
    if len(enemy_targets) == 1:
        attacked = enemy_targets[0]
        if attacked.piece_type == chess.QUEEN:
            return f"{response_san} attacks their Queen!"
        if attacked.piece_type == chess.ROOK:
            return f"{response_san} attacks their Rook."
    
    # ─── KNIGHT MOVES ───
    if piece.piece_type == chess.KNIGHT:
        if to_sq in [chess.D5, chess.E5, chess.D4, chess.E4]:
            return f"{response_san} plants the knight powerfully in the center — hard to kick out!"
        
        # Outpost?
        # Check if the square can be attacked by enemy pawns
        can_be_attacked = False
        for f in [to_file - 1, to_file + 1]:
            if 0 <= f <= 7:
                for r in range(8):
                    sq = chess.square(f, r)
                    p = board.piece_at(sq)
                    if p and p.piece_type == chess.PAWN and p.color != user_is_white:
                        # Could this pawn ever attack our square?
                        if (user_is_white and r < to_rank) or (not user_is_white and r > to_rank):
                            can_be_attacked = True
                            break
        
        if not can_be_attacked:
            return f"{response_san} establishes a permanent outpost — no pawns can challenge it!"
    
    # ─── BISHOP MOVES ───
    if piece.piece_type == chess.BISHOP:
        # Long diagonal?
        diag_length = len(list(sim.attacks(to_sq)))
        if diag_length >= 7:
            return f"{response_san} activates the bishop on a long diagonal."
    
    # ─── ROOK MOVES ───
    if piece.piece_type == chess.ROOK:
        # Open file?
        pawns_on_file = sum(1 for r in range(8) 
                           if board.piece_at(chess.square(to_file, r)) 
                           and board.piece_at(chess.square(to_file, r)).piece_type == chess.PAWN)
        if pawns_on_file == 0:
            return f"{response_san} seizes the open file — Rooks love open files!"
        
        # Seventh rank?
        if (user_is_white and to_rank == 6) or (not user_is_white and to_rank == 1):
            return f"{response_san} invades the seventh rank — threatens their pawns and cramps their king!"
    
    # ─── QUEEN MOVES ───
    if piece.piece_type == chess.QUEEN:
        # Check what it attacks
        attacked = list(sim.attacks(to_sq))
        valuable_targets = [sq for sq in attacked 
                           if sim.piece_at(sq) and sim.piece_at(sq).color != user_is_white 
                           and sim.piece_at(sq).piece_type in [chess.ROOK, chess.KNIGHT, chess.BISHOP]]
        if len(valuable_targets) >= 2:
            return f"{response_san} creates multiple threats — their position is crumbling!"
    
    # ─── LANDING ON WEAK SQUARES ───
    to_sq_name = chess.square_name(to_sq)
    if to_sq_name in weak_squares:
        return f"{response_san} exploits the weak {to_sq_name} square that they created."
    
    # ─── FALLBACK ───
    return f"{response_san} improves your position."


def _explain_opponent_move_with_context(
    board: chess.Board,
    move: chess.Move,
    user_color: str,
    pv_after: List[str],
    move_history_san: Optional[List[str]] = None,
    full_move_number: Optional[int] = None,
) -> Tuple[str, str]:
    """
    Explain opponent's move.

    First-pass: if the move is in known opening theory, prefer theory
    over invented "fun" copy. e5 in response to e4 should say
    "Open Game / King's Pawn Opening — symmetric center control. Leads
    to tactical play.", not "Pawn advances. They want the center! Don't
    let them have all the space. Push back!".

    Falls through to the legacy fun-text branches when theory has
    nothing to say.
    """
    move_san = board.san(move)
    piece = board.piece_at(move.from_square)

    sim = board.copy()
    sim.push(move)

    # ── Opening-theory first-pass ──
    # When move_history is available and we're in the opening phase,
    # use the opening detector to emit theory-grounded captions instead
    # of hardcoded "fun" text. Source bugs: fb_d0454a4088f3 / fb_e093213e873f
    # / fb_a12c4f9d39ed (opening moves got "Pawn advances to e5. They
    # want the center! Don't let them have all the space. Push back!"
    # instead of "King's Pawn Opening — Open game, both sides fight for
    # the center.").
    #
    # Try get_opening_theory_note first (curriculum-grade content for
    # named lines like the Queen's Gambit, Sicilian variations, etc.).
    # Fall back to detect_opening_from_moves (broader coverage including
    # bare e4/d4/c4/Nf3 + first responses) when curriculum has no entry.
    if move_history_san and full_move_number and full_move_number <= 12:
        try:
            from services.opening_theory_note import get_opening_theory_note
            note = get_opening_theory_note(
                move_history=move_history_san,
                move_number=full_move_number,
            )
            if note:
                opening_name = note.get("opening_name") or ""
                summary = (note.get("summary") or "").strip()
                key_rule = (note.get("key_rule") or "").strip()
                if opening_name and summary:
                    return (
                        f"{opening_name}: {summary}",
                        key_rule or f"Stay with the {opening_name.lower()} plan.",
                    )
        except Exception as exc:
            logger.debug(f"opening_theory_note failed (non-fatal): {exc}")

        # Detector fallback — covers the common "no curriculum entry"
        # case (e4-e5, d4-d5, e4-c5, etc.). Returns name + description
        # + introduction which are enough to teach with.
        try:
            from services.opening_mastery import detect_opening_from_moves
            info = detect_opening_from_moves(move_history_san)
            if info:
                opening_name = info.get("opening_name") or ""
                description = (info.get("description") or "").strip()
                introduction = (info.get("introduction") or "").strip()
                if opening_name and description:
                    # Description sometimes has " / " separating white
                    # vs black ideas — take the first half (more
                    # universally framed) for the narrative.
                    desc_short = description.split(" / ")[0].strip().rstrip(".")
                    return (
                        f"{opening_name} — {desc_short}.",
                        introduction.rstrip("!") + ("!" if introduction.endswith("!") else ".") if introduction else f"Stay with the {opening_name.lower()} plan.",
                    )
        except Exception as exc:
            logger.debug(f"detect_opening_from_moves failed (non-fatal): {exc}")

    # Check what this move threatens
    threats = []

    # 1. Does it create a direct threat?
    for sq, p in sim.piece_map().items():
        if p.color == (user_color == "white"):  # User's pieces
            attackers = sim.attackers(not (user_color == "white"), sq)
            defenders = sim.attackers(user_color == "white", sq)
            if len(attackers) > len(defenders):
                piece_name = _get_fun_piece_name(p)
                threats.append(f"eyeing your {piece_name} on {chess.square_name(sq)}")
    
    # 2. Is this a capture?
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured:
            captured_name = _get_fun_piece_name(captured)
            return (
                f"Chomp! They took your {captured_name}.",
                "Recapture? Check if it's worth it first!"
            )
    
    # 3. Is this castling?
    if board.is_castling(move):
        return (
            "They castled! Their King is tucked away safely now.",
            "Time to make a plan. Where's their weakness?"
        )
    
    # 4. Check for piece-specific ideas with FUN names
    if piece:
        if piece.piece_type == chess.PAWN:
            to_file = chess.square_file(move.to_square)
            if to_file in [3, 4]:  # d or e file
                return (
                    f"Pawn advances to {move_san}. They want the center!",
                    "Don't let them have all the space. Push back!"
                )
            return (
                f"Pawn to {move_san}. What's the plan behind it?",
                "Every pawn move creates a weakness. Where is it?"
            )
        
        elif piece.piece_type == chess.KNIGHT:
            to_sq = move.to_square
            if to_sq in [chess.C3, chess.F3, chess.C6, chess.F6]:
                return (
                    f"Their horsey hops to {move_san}. Classic development!",
                    "Keep developing. Don't fall behind!"
                )
            if to_sq in [chess.D5, chess.E5, chess.D4, chess.E4]:
                return (
                    f"Whoa! Their knight lands in the center with {move_san}. Strong!",
                    "Can you kick it out? Challenge that knight!"
                )
            return (
                f"Knight to {move_san}. Where's it heading?",
                "Watch where that horsey wants to jump next!"
            )
        
        elif piece.piece_type == chess.BISHOP:
            return (
                f"Bishop slides to {move_san}. Bishops love open diagonals!",
                "Make sure your pieces aren't on that diagonal!"
            )
        
        elif piece.piece_type == chess.ROOK:
            to_file = chess.square_file(move.to_square)
            file_pawns = len([sq for sq in chess.SQUARES if chess.square_file(sq) == to_file and board.piece_at(sq) and board.piece_at(sq).piece_type == chess.PAWN])
            if file_pawns == 0:
                return (
                    f"Tower Power! Their rook hits the open file with {move_san}.",
                    "Open files are dangerous. Contest it or block it!"
                )
            return (
                f"Rook moves to {move_san}.",
                "Rooks want open files. Don't give them one!"
            )
        
        elif piece.piece_type == chess.QUEEN:
            return (
                f"Her Majesty enters with {move_san}. Respect the Queen!",
                "The Queen is powerful but attackable. Can you harass her?"
            )
    
    # 5. If there's a threat, warn about it
    if threats:
        return (
            f"Watch out! {move_san} is {threats[0]}.",
            "Deal with this threat first, then continue your plan."
        )
    
    # 6. Fallback - but still useful
    return (
        f"They played {move_san}.",
        "Keep developing! Castle if you haven't."
    )


def _get_fun_piece_name(piece: chess.Piece) -> str:
    """Get clear piece names."""
    names = {
        chess.PAWN: "pawn",
        chess.KNIGHT: "knight",
        chess.BISHOP: "bishop",
        chess.ROOK: "rook",
        chess.QUEEN: "queen",
        chess.KING: "king"
    }
    return names.get(piece.piece_type, "piece")


# ─── GOOD MOVE RECOGNITION ───────────────────────────────────────────

def recognize_good_move(
    board: chess.Board,
    move: chess.Move,
    best_move: Optional[str],
    cp_loss: int,
    phase: str,
    opening_data: dict,
    pv_after_best: List[str] = None,
    eval_before: float = None,
    eval_after: float = None
) -> Tuple[str, Optional[str], bool]:
    """
    Recognize when user plays a good move - use FUN, MEMORABLE language!
    Returns: (narrative, concept_applied, is_best_move)
    
    NOW HANDLES: Critical situations like mate threats!
    """
    move_san = board.san(move)
    is_best = best_move and move_san.lower().replace("+", "").replace("#", "") == best_move.lower().replace("+", "").replace("#", "")
    
    piece = board.piece_at(move.from_square)
    
    concept_applied = None
    narrative = ""
    
    # ─── CRITICAL: Handle mate situations FIRST ───
    # Mate detected when eval_after is very high (±9000+) indicating forced mate
    # Or when there's a big eval swing indicating critical position
    
    board_after = board.copy()
    board_after.push(move)
    
    # Check if WE just gave checkmate
    if board_after.is_checkmate():
        return f"Checkmate. {move_san} ends the game.", "checkmate_delivery", True

    # ── Checks (non-mating) ──
    # Don't let development templates fire on a check. "Bc4+. Bishop on
    # an active diagonal." is wrong on so many levels — the news is the
    # check, not the bishop's diagonal. Route to a check-specific
    # template that names what the check forks/attacks if anything.
    if board_after.is_check():
        opp_color = not board_after.turn  # we just moved → opp's turn
        # What else does the moving piece attack besides the king?
        extras = []
        if move.to_square is not None:
            for sq in board_after.attacks(move.to_square):
                p = board_after.piece_at(sq)
                if (p and p.color == board_after.turn  # opp pieces (current turn = opp)
                        and p.piece_type != chess.KING
                        and p.piece_type != chess.PAWN):
                    extras.append(get_piece_name(p))
        if extras:
            # Check + extra attack = mini fork
            extra = extras[0]
            return (
                f"{move_san} — check, and attacks the {extra} too.",
                "double_attack_check",
                is_best,
            )
        return (
            f"{move_san} — check. Their king has to move or block.",
            "check_given",
            is_best,
        )

    # Check for mate threats (eval indicates forced mate - values near ±10000)
    if eval_after is not None:
        # We're getting mated (eval around -9000 to -10000 for mate scores)
        if eval_after <= -5000:  # Forced mate against us
            if is_best:
                return f"{move_san} — the only move. You're facing a forced mate; this puts up the best fight.", "defensive_critical", True
            else:
                return f"{move_san} delays it, but mate is coming. The position was already lost.", "defensive_critical", False

        # We're winning with mate (eval around +9000 to +10000)
        if eval_after >= 5000:
            if is_best:
                return f"{move_san} keeps the winning attack going. Mate is close.", "winning_attack", True
            else:
                return f"{move_san}. You're winning — keep playing accurate moves to close it out.", "winning_attack", False

        # Check if eval dropped significantly (position collapsed from okay to lost)
        if eval_before is not None:
            # Went from reasonable to getting mated
            if eval_before > -1000 and eval_after <= -5000:
                if is_best:
                    return f"{move_san} — the best option in a lost position. The damage was done earlier.", "best_in_lost", True
                else:
                    return f"{move_san} — but the position collapsed. This was the critical moment.", "desperate_defense", False

            # Went from reasonable to significantly worse (but not mate)
            if eval_before > -200 and eval_after <= -500:
                if is_best:
                    return f"{move_san} — best in a difficult position. You're under pressure.", "best_under_pressure", True
                else:
                    return f"{move_san} — things are tough here. Time to slow down.", "under_pressure", False

    # ─── Check if this matches opening theory ───
    typical_ideas = opening_data.get("typical_ideas", {})
    if move_san in typical_ideas:
        concept_applied = f"opening_{move_san.lower()}"
        narrative = f"{move_san}. {typical_ideas[move_san]}"
        return narrative, concept_applied, is_best

    # Castling
    if board.is_castling(move):
        concept_applied = "king_safety_castling"
        move_num = len(list(board.move_stack)) // 2 + 1
        if move_num <= 10:
            narrative = "Castled. King's in the corner, rook joins the game."
        else:
            narrative = "Castled. Should have come sooner — but the king is safe now."
        return narrative, concept_applied, is_best

    # Development by piece type
    if piece:
        back_rank = 0 if piece.color == chess.WHITE else 7

        if piece.piece_type == chess.KNIGHT:
            to_sq = move.to_square
            if to_sq in [chess.F3, chess.C3, chess.F6, chess.C6]:
                concept_applied = "knight_development"
                narrative = f"{move_san}. Knights are strongest on f3/c3 — they control the center from here."
                if is_best:
                    narrative = f"{move_san}. The right square for the knight here."
                return narrative, concept_applied, is_best
            elif to_sq in [chess.E5, chess.D5, chess.E4, chess.D4]:
                concept_applied = "central_knight"
                narrative = f"{move_san}. Knight in the center, hard to kick out."
                return narrative, concept_applied, is_best

        elif piece.piece_type == chess.BISHOP:
            if chess.square_rank(move.from_square) == back_rank:
                concept_applied = "bishop_development"
                to_sq = move.to_square
                to_file = chess.square_file(to_sq)
                if to_file in [1, 2, 5, 6]:  # b, c, f, g files - active squares
                    narrative = f"{move_san}. Bishop on an active diagonal."
                else:
                    narrative = f"{move_san}. Bishop out — open diagonal ahead."
                return narrative, concept_applied, is_best

        elif piece.piece_type == chess.PAWN:
            to_file = chess.square_file(move.to_square)
            if to_file in [3, 4]:  # d or e file
                to_rank = chess.square_rank(move.to_square)
                if (piece.color == chess.WHITE and to_rank == 3) or (piece.color == chess.BLACK and to_rank == 4):
                    concept_applied = "center_control"
                    narrative = f"{move_san}. Grabs space in the center."
                    return narrative, concept_applied, is_best

        elif piece.piece_type == chess.ROOK:
            to_file = chess.square_file(move.to_square)
            file_pawns = len([sq for sq in chess.SQUARES if chess.square_file(sq) == to_file and board.piece_at(sq) and board.piece_at(sq).piece_type == chess.PAWN])
            if file_pawns == 0:
                concept_applied = "rook_on_open_file"
                narrative = f"{move_san}. Rook on an open file — controls the whole column."
                return narrative, concept_applied, is_best

    # Capture that wins material
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured:
            attacker_value = _piece_value(piece)
            captured_value = _piece_value(captured)
            if captured_value > attacker_value:
                concept_applied = "winning_material"
                narrative = f"{move_san} wins material — straight gain."
                return narrative, concept_applied, is_best

    # Generic best move
    if is_best:
        sim = board.copy()
        sim.push(move)

        for sq, p in sim.piece_map().items():
            if p.color != piece.color:
                attackers = sim.attackers(piece.color, sq)
                if attackers:
                    narrative = f"{move_san}. Creates a new threat — they have to respond."
                    return narrative, "found_best_move", True

        narrative = f"{move_san}. Best move here."
        return narrative, "found_best_move", True

    if cp_loss < 10:
        return f"{move_san}. Solid.", None, False

    return f"{move_san}.", None, False


def _piece_value(piece: chess.Piece) -> int:
    """Get approximate piece value."""
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
    return values.get(piece.piece_type, 0)


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

async def _get_adaptive_config(db, user_id: str) -> Dict:
    """
    Get adaptive decryption config based on player rating + known weaknesses.
    
    Philosophy:
    - 1100 player: Only blunders/mistakes. Inaccuracies are noise.
    - 1400 player: Blunders/mistakes + inaccuracies that match known weaknesses.
    - 1700+ player: Everything.
    - If a known weakness reappears: ALWAYS explain, even at low cp_loss.
    """
    config = {
        "rating": 1200,
        "min_cp_explain": 100,   # Only explain moves with cp_loss >= this
        "min_cp_detail": 200,    # Only show detailed plans for moves >= this
        "known_weaknesses": set(),  # concept_ids / pattern types to always explain
        "weakness_patterns": {},    # pattern_type -> count (for emphasis)
    }

    if db is None:
        return config

    try:
        # Get player rating from profile
        profile = await db.player_profiles.find_one(
            {"user_id": user_id},
            {"_id": 0, "estimated_elo": 1, "current_rating": 1}
        )
        if profile:
            config["rating"] = profile.get("estimated_elo") or profile.get("current_rating") or 1200

        # Get known weaknesses from player identity
        identity = await db.player_identities.find_one(
            {"user_id": user_id},
            {"_id": 0, "blunder_taxonomy": 1, "priority_focus": 1, "learning_velocity": 1}
        )
        if identity:
            taxonomy = identity.get("blunder_taxonomy", {})
            by_type = taxonomy.get("by_type", {})
            # Top 3 most frequent weakness patterns
            sorted_types = sorted(by_type.items(), key=lambda x: x[1], reverse=True)
            for ptype, count in sorted_types[:3]:
                config["known_weaknesses"].add(ptype)
                config["weakness_patterns"][ptype] = count

            priority = identity.get("priority_focus")
            if priority:
                config["known_weaknesses"].add(priority)

            # Also add worsening areas
            velocity = identity.get("learning_velocity", {})
            for area in velocity.get("worsening_areas", []):
                config["known_weaknesses"].add(area)

        # Adaptive thresholds based on rating
        rating = config["rating"]
        if rating < 1200:
            config["min_cp_explain"] = 100   # Only mistakes & blunders
            config["min_cp_detail"] = 150
        elif rating < 1400:
            config["min_cp_explain"] = 70    # Include bigger inaccuracies
            config["min_cp_detail"] = 120
        elif rating < 1600:
            config["min_cp_explain"] = 50    # Include most inaccuracies
            config["min_cp_detail"] = 80
        else:
            config["min_cp_explain"] = 30    # Full detail (current behavior)
            config["min_cp_detail"] = 50

        logger.info(f"[ADAPTIVE] Rating={rating}, min_explain={config['min_cp_explain']}, weaknesses={config['known_weaknesses']}")

    except Exception as e:
        logger.warning(f"Could not load adaptive config: {e}")

    return config


def _get_move_priority(
    severity: str,
    cp_loss: int,
    plan: object,
    config: Dict,
    is_user: bool,
) -> str:
    """
    Determine decryption priority for a move.
    Returns: "essential" | "weakness_match" | "growth" | "silent"
    
    essential: Always show (blunders, mistakes, opponent blunders)
    weakness_match: Matches a known weakness — show with emphasis
    growth: Inaccuracy worth explaining at this level
    silent: Skip detailed explanation
    """
    if not is_user:
        # Opponent moves: show blunders/mistakes, skip the rest
        if severity in ("opp_blunder", "opp_mistake"):
            return "essential"
        return "context"

    if severity in ("blunder",):
        return "essential"
    if severity in ("mistake",):
        return "essential"

    # Check if this move matches a known weakness pattern
    if plan and hasattr(plan, 'concept_id') and plan.concept_id:
        concept = plan.concept_id.lower()
        for weakness in config.get("known_weaknesses", set()):
            if weakness.lower() in concept or concept in weakness.lower():
                return "weakness_match"

    # Inaccuracies: only explain if cp_loss meets the adaptive threshold
    if severity == "inaccuracy":
        if cp_loss >= config.get("min_cp_explain", 100):
            return "growth"
        return "silent"

    # Good moves
    return "silent"


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
        
        # Get adaptive config (rating-based filtering + known weaknesses)
        adaptive = await _get_adaptive_config(db, user_id)
        
        # Process each move
        decryption_data = []
        board = chess.Board()
        prev_move = None
        prev_user_eval_after = None  # Track eval after user's last move

        # ── Teaching-layer suppression state ──────────────────────────
        # Catalog declares per-principle suppression semantics:
        #   once_per_move        — default; no game-state filter
        #   once_per_state_entry — fire on transitions from "not firing
        #                          last move" to "firing this move"
        #   once_per_game        — fire only the FIRST time per game
        # Detectors are pure (no game-state); filtering happens here.
        # Without this, state-persistent principles like END_KING_ACTIVE
        # spammed 34k times across the audit corpus (first audit pass
        # surfaced the gap).
        principles_fired_this_game: set = set()
        principles_fired_last_move: set = set()
        # State-keyed suppression set (Phase 0.5, 2026-05-18):
        # tracks (principle_id, state_key) tuples so the same principle
        # CAN fire again when board state meaningfully changes (different
        # focal squares, different king pair, different best-move family).
        # See project_suppression_key_overhaul.md for the design.
        state_keys_fired_this_game: set = set()
        # TIER 3 shape-pattern suppression — same convention as principles:
        # each pattern fires at most once per game, so the cue stays a
        # memorable marker instead of a repeated label.
        shapes_fired_this_game: set = set()

        # Trap + opening recognition state (walked statefully across the game).
        # `played_san_so_far` accumulates SAN of every move played; trap and
        # opening lookup compare against this sequence each move.
        played_san_so_far: List[str] = []
        active_trap: Optional[Dict[str, Any]] = None
        active_trap_setup_completed_by_user: Optional[bool] = None
        active_trap_step_cursor: int = 0

        for idx, move in enumerate(moves):
            # Defensive: a small share of corpus games have PGN ↔
            # move_evaluations drift where the next mainline move
            # isn't legal in the replayed board state. Skip the
            # offending move rather than aborting the entire game.
            try:
                move_san = board.san(move)
            except (AssertionError, ValueError, chess.IllegalMoveError) as _drift_exc:
                logger.warning(
                    f"[V5] PGN-replay drift at idx={idx} ({move.uci()}): "
                    f"{_drift_exc}. Skipping this move; remainder of game "
                    f"continues."
                )
                continue
            full_move_number = (idx // 2) + 1
            is_white = (idx % 2 == 0)
            is_user = (user_color == "white" and is_white) or (user_color == "black" and not is_white)
            
            # Get eval data - for user moves, from current position; for opponent, we'll use next position
            fen_key = " ".join(board.fen().split()[:4])
            eval_data = eval_lookup.get(fen_key, {})
            cp_loss = abs(eval_data.get("cp_loss", 0)) if is_user else 0

            # Mate-sentinel cp_loss capture — when the engine returns a
            # mate-loss as eval_after, cp_loss may be absent/0 in the
            # stored eval_data even though the move walked into mate.
            # Recompute cp_loss from eval_before + eval_after when those
            # are available and the stored cp_loss looks suspicious.
            # Source bug: fb_a9ac9f02affa (Rxc3 = "Equal trade" caught by
            # Phase 2 audit at +381cp swing; underlying severity was tagged
            # "good" because the stored cp_loss didn't reflect the swing).
            if is_user:
                eval_before_v = eval_data.get("eval_before")
                eval_after_v = eval_data.get("eval_after")
                if eval_before_v is not None and eval_after_v is not None:
                    user_eval_before = eval_before_v if user_color == "white" else -eval_before_v
                    user_eval_after = eval_after_v if user_color == "white" else -eval_after_v
                    derived_loss = max(0, user_eval_before - user_eval_after)
                    cp_loss = max(cp_loss, derived_loss)
            
            # For opponent moves, calculate eval swing using:
            # - eval BEFORE opponent move = eval AFTER user's last move (prev_user_eval_after)
            # - eval AFTER opponent move = eval BEFORE user's next move (look ahead)
            opp_eval_before = None
            opp_eval_after = None
            opp_cp_loss = 0
            if not is_user:
                opp_eval_before = prev_user_eval_after
                # Look ahead to get eval after opponent's move
                if idx + 1 < len(moves):
                    # Simulate opponent's move to get the FEN that will be user's turn
                    sim_board = board.copy()
                    sim_board.push(move)
                    next_fen_key = " ".join(sim_board.fen().split()[:4])
                    next_eval_data = eval_lookup.get(next_fen_key, {})
                    opp_eval_after = next_eval_data.get("eval_before")  # This is the eval at user's next turn
                
                # Calculate opponent's cp_loss (from opponent's perspective, positive = bad for them)
                if opp_eval_before is not None and opp_eval_after is not None:
                    if user_color == "white":
                        # User is white, opponent is black
                        # If eval went from -100 to +50, opponent blundered (swing of 150 in user's favor)
                        opp_cp_loss = opp_eval_after - opp_eval_before
                    else:
                        # User is black, opponent is white
                        # If eval went from +100 to -50, opponent blundered (swing of 150 in user's favor)
                        opp_cp_loss = opp_eval_before - opp_eval_after
            
            phase = detect_phase(board, full_move_number)
            
            # Determine severity for opponent moves too
            if not is_user:
                if opp_cp_loss >= 250:
                    severity = "opp_blunder"
                elif opp_cp_loss >= 100:
                    severity = "opp_mistake"
                elif opp_cp_loss >= 50:
                    severity = "opp_inaccuracy"
                else:
                    severity = "context"
            else:
                # Forced-mate sentinel guard FIRST — if the move walks the
                # user into a losing mate (eval_after deeply negative from
                # user's perspective), severity is BLUNDER regardless of
                # the stored cp_loss. Bug fb_a9ac9f02affa class: Rxc3
                # tagged "good" while engine sees mate-in-2 against the
                # mover. Mate sentinels typically sit beyond ~3000cp.
                _MATE_SENTINEL_CP = 3000
                user_post_eval = None
                _eb = eval_data.get("eval_before")
                _ea = eval_data.get("eval_after")
                if _ea is not None:
                    user_post_eval = _ea if user_color == "white" else -_ea
                if user_post_eval is not None and user_post_eval <= -_MATE_SENTINEL_CP:
                    severity = "blunder"
                elif cp_loss < 30:
                    severity = "good"
                elif cp_loss < 100:
                    severity = "inaccuracy"
                elif cp_loss < 250:
                    severity = "mistake"
                else:
                    severity = "blunder"
            
            # Override: known opening book moves should never be flagged as inaccuracies
            if is_user and severity in ("inaccuracy", "mistake") and phase == "opening":
                if is_book_opening_move(board, move_san, idx, opening_name, cp_loss):
                    logger.info(f"[BOOK MOVE] {move_san} (cpl={cp_loss}) is a book opening move — overriding '{severity}' to 'good'")
                    severity = "good"

            # Category 6 fix — best-move agreement sanity check. When the
            # severity classifier says mistake/inaccuracy/blunder but the
            # stored best_move EQUALS the played move, the stored cp_loss
            # is internally inconsistent (you can't lose centipawns by
            # playing the engine's top choice). Downgrade severity to
            # "good" rather than mislead the user. Source bugs:
            #   fb_4102902e3639 (Qe5 marked mistake but is engine's best)
            #   fb_5dd398d092c9 (h6 marked mistake; Parth: both moves fine)
            if is_user and severity in ("inaccuracy", "mistake", "blunder"):
                _stored_best = (eval_data.get("best_move") or "").strip().rstrip("!?+#")
                _played_norm = (move_san or "").strip().rstrip("!?+#")
                if _stored_best and _stored_best == _played_norm:
                    logger.info(
                        f"[SEVERITY-SANITY] move {move_san} == stored best_move but "
                        f"severity={severity} (cpl={cp_loss}). Reclassifying as "
                        f"'forced' (best damage control in a losing position). "
                        f"Internal severity stays 'good' for downstream-consumer "
                        f"compatibility; user-facing caption surfaces via "
                        f"R14_forced_best (\"only move\")."
                    )
                    severity = "good"
            
            # Check for forced recapture
            is_forced_recapture = False
            if is_user and board.is_capture(move) and prev_move:
                if move.to_square == prev_move.to_square:
                    captures_on_sq = [m for m in board.legal_moves if m.to_square == move.to_square and board.is_capture(m)]
                    if len(captures_on_sq) <= 1:
                        is_forced_recapture = True
                        severity = "good"
            
            fen_before = board.fen()
            
            # ─── ADAPTIVE PRIORITY ────────────────────────────────
            # Determine if this move should be fully explained based on player level
            # For lower-rated players: skip inaccuracies, focus on mistakes/blunders
            move_priority = "silent"
            if is_user and severity == "inaccuracy" and cp_loss < adaptive.get("min_cp_explain", 100):
                # Below this player's threshold — treat as fine
                severity = "good"
                move_priority = "silent"
            elif is_user and severity == "inaccuracy":
                move_priority = "growth"
            elif is_user and severity in ("mistake", "blunder"):
                move_priority = "essential"
            elif not is_user and severity in ("opp_blunder", "opp_mistake"):
                move_priority = "essential"
            elif not is_user:
                move_priority = "context"
            elif severity == "good":
                move_priority = "silent"
            
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
                # OPPONENT MOVE - Analyze from user's POV with proper eval data
                # Get the user's best response from the NEXT position's eval data
                user_best_response = None
                if idx + 1 < len(moves):
                    sim_board = board.copy()
                    sim_board.push(move)
                    next_fen_key = " ".join(sim_board.fen().split()[:4])
                    next_eval_data = eval_lookup.get(next_fen_key, {})
                    user_best_response = next_eval_data.get("best_move")
                
                # Use the best response in PV if available
                pv_for_analysis = [user_best_response] if user_best_response else pv_after_played
                
                # Build move history (SAN list) including this opponent
                # move — used by analyze_opponent_move to look up opening
                # theory and emit theory-grounded captions in the
                # opening phase.
                move_history_san = []
                try:
                    replay = chess.Board()
                    for past_move in board.move_stack:
                        move_history_san.append(replay.san(past_move))
                        replay.push(past_move)
                    move_history_san.append(replay.san(move))
                except Exception:
                    move_history_san = []

                narrative, your_plan_now, highlight_squares = analyze_opponent_move(
                    board, move,
                    opp_eval_before,
                    opp_eval_after,
                    pv_for_analysis,
                    user_color,
                    move_history_san=move_history_san,
                    full_move_number=full_move_number,
                )
                future_moves = pv_after_played[:3] if pv_after_played else []
                
                # Add opening introduction for early moves (only if it's a normal move)
                if idx < 10 and phase == "opening" and severity == "context":
                    intro = get_opening_introduction(
                        eco_code, opening_name, move_san, user_color,
                        move_index=idx,
                    )
                    if intro:
                        intro_name = intro.get("name")
                        intro_idea = intro.get("idea")
                        intro_hint = intro.get("hint")
                        
                        if intro_name and intro_idea:
                            narrative = f"{intro_name}: {intro_idea}"
                            if intro_hint:
                                your_plan_now = intro_hint
                        elif intro_name:
                            narrative = f"This is the {intro_name}. {narrative}"
                
            elif severity == "good":
                # GOOD USER MOVE - Recognize and track
                narrative, concept_applied, is_best_move = recognize_good_move(
                    board, move, best_move, cp_loss, phase, opening_data,
                    eval_before=eval_data.get("eval_before"),
                    eval_after=eval_data.get("eval_after")
                )
                
            elif is_forced_recapture:
                # FORCED RECAPTURE - Natural move
                captured = board.piece_at(move.to_square)
                narrative = f"Forced recapture — {move_san} takes back the {get_piece_name(captured) if captured else 'piece'}."
                
            else:
                # MISTAKE/INACCURACY - Extract plan
                # Get Stockfish candidates for alternative moves
                stockfish_candidates = await _get_stockfish_candidates(board, num_moves=3, depth=12)
                
                plan = extract_plan_from_pv(
                    board, move, best_move,
                    pv_after_played, pv_after_best,
                    phase, opening_data, cp_loss,
                    eco_code=eco_code,
                    stockfish_candidates=stockfish_candidates
                )
                
                # ── GOLDEN RULE INJECTION ──
                # Enrich the plan's transferable_learning with phase-specific wisdom
                try:
                    from services.golden_rule_service import get_golden_rule
                    golden = get_golden_rule(
                        board=board,
                        move=move,
                        phase=phase,
                        severity=severity,
                        cp_loss=cp_loss,
                        eco_code=eco_code,
                        opening_name=opening_name,
                        best_move_san=best_move,
                        concept_type=plan.concept_type if plan else None,
                    )
                    if golden and golden.get("rule"):
                        if plan:
                            # Override generic transferable_learning with specific golden rule
                            plan.transferable_learning = golden["rule"]
                        else:
                            # No plan exists — create a minimal one with the golden rule
                            plan = ChessPlan(
                                goal="",
                                current_problem=f"{move_san} was not the best choice here.",
                                consequence="",
                                better_approach=f"{best_move} was better." if best_move else "",
                                transferable_learning=golden["rule"],
                                concept_id=f"golden_{golden.get('source', 'rule')}_{full_move_number}",
                                concept_type=golden.get("category", "general"),
                            )
                except Exception as gr_err:
                    logger.debug(f"Golden rule injection failed (non-fatal): {gr_err}")

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
            
            # Check weakness match — boost priority if move matches known pattern
            weakness_match = False
            weakness_count = 0
            if plan and is_user and severity in ("inaccuracy", "mistake", "blunder"):
                concept = (plan.concept_id or "").lower()
                concept_type = (plan.concept_type or "").lower()
                for weakness in adaptive.get("known_weaknesses", set()):
                    wk = weakness.lower()
                    if wk in concept or wk in concept_type or concept in wk:
                        weakness_match = True
                        weakness_count = adaptive.get("weakness_patterns", {}).get(weakness, 0)
                        if move_priority != "essential":
                            move_priority = "weakness_match"
                        break

            # ── V5 CAPTION PIPELINE ─────────────────────────────────────
            # Extractor → rules → renderer. Runs for EVERY move (user +
            # opponent). Pure-function: facts come from FEN + engine truth,
            # renderer never touches `chess`. New fields land on move_output
            # alongside the legacy `narrative`/`plan`/`highlight_squares`
            # so we can review side-by-side before retiring the dispatcher.
            # Per docs/caption_pipeline_design.md §3.
            caption_payload = {
                "caption": "",
                "rule_name": "R_FALLBACK_disabled",
                "highlight_squares": [],
                "arrows": [],
            }
            caption_primary_reason = None
            caption_principles_violated: List[Dict] = []
            principle_cue = ""
            principle_id_used: Optional[str] = None
            caption_captured_piece: Optional[str] = None
            if CAPTION_V5_PIPELINE_ENABLED and _extract_caption_facts and _render_caption_dict:
                try:
                    # Rebuild SAN history from board.move_stack so the
                    # extractor sees the same line we just replayed.
                    cap_history: List[str] = []
                    _replay = chess.Board()
                    for _past in board.move_stack:
                        cap_history.append(_replay.san(_past))
                        _replay.push(_past)
                    # Eval inputs are stored from white's POV regardless of
                    # who moved; extractor flips per-side internally.
                    if is_user:
                        _eb = eval_data.get("eval_before")
                        _ea = eval_data.get("eval_after")
                        _cpl = cp_loss
                    else:
                        _eb = opp_eval_before
                        _ea = opp_eval_after
                        _cpl = max(0, opp_cp_loss)
                    caption_facts = _extract_caption_facts(
                        fen_before=fen_before,
                        played_san=move_san,
                        best_move_san=best_move,
                        eval_before_cp=_eb,
                        eval_after_cp=_ea,
                        cp_loss=_cpl,
                        pv_after_played=pv_after_played,
                        pv_after_best=pv_after_best,
                        move_history_san=cap_history,
                        full_move_number=full_move_number,
                        mover_is_user=is_user,
                    )
                    caption_payload = _render_caption_dict(caption_facts)
                    caption_primary_reason = caption_facts.get("primary_reason")
                    # Surface what was captured (pawn / knight / bishop / rook /
                    # queen / None) for downstream caption generation. Parth
                    # flagged exd6 captioned "won a pawn" when actually the
                    # captured piece was a knight (won the exchange overall).
                    # caption_facts already extracts this — V5 just propagates.
                    caption_captured_piece = caption_facts.get("captured_piece_type")
                    # Teaching layer — apply per-principle suppression
                    # against the running game-state. Detectors are
                    # pure; this layer dedupes per the catalog's
                    # suppress semantics.
                    # Reset per-move principle-cue outputs before the
                    # filter loop fills them.
                    principle_cue = ""
                    principle_id_used = None
                    raw_principles = caption_facts.get("principles_violated") or []
                    caption_principles_violated = []
                    _this_move_fired = set()
                    for _ev in raw_principles:
                        _pid = _ev.get("principle_id")
                        if not _pid:
                            continue
                        _entry = _CAPTION_PRINCIPLES_BY_ID.get(_pid, {}) if _CAPTION_PRINCIPLES_BY_ID else {}
                        _suppress = _entry.get("suppress", "once_per_move")
                        # Phase 0.5 suppression overhaul (2026-05-18):
                        # three policies replace the previous two.
                        #   once_per_move        — no game-state filter (default)
                        #   once_per_state_key   — fires while detector's state_key changes
                        #                          (re-arms when focal squares / piece /
                        #                          best-move family / phase change)
                        #   once_per_game        — fires exactly once across the game
                        #   once_per_state_entry — DEPRECATED; treated as once_per_game
                        #                          for backward compat
                        if _suppress == "once_per_game" or _suppress == "once_per_state_entry":
                            if _pid in principles_fired_this_game:
                                continue
                        elif _suppress == "once_per_state_key":
                            _sk = _ev.get("state_key")
                            if _sk is None:
                                # Detector didn't emit state_key — degrade
                                # gracefully to once_per_game semantics.
                                if _pid in principles_fired_this_game:
                                    continue
                            else:
                                if _sk in state_keys_fired_this_game:
                                    continue
                                state_keys_fired_this_game.add(_sk)
                        # once_per_move (default) → no further filter
                        caption_principles_violated.append(_ev)
                        _this_move_fired.add(_pid)
                        principles_fired_this_game.add(_pid)
                    principles_fired_last_move = _this_move_fired

                    # ── Pick the cue for this move ────────────────────
                    # Highest-priority surviving principle (lowest
                    # priority number wins) contributes the cue.
                    # Endorsement tier picks the variant: best /
                    # top_n / absent → maps to cue_best / cue_top_n /
                    # cue_absent in the catalog entry. top_n is
                    # reserved for future multi-PV; v1 returns
                    # best or absent.
                    if caption_principles_violated and _CAPTION_PRINCIPLES_BY_ID:
                        sorted_pv = sorted(
                            caption_principles_violated,
                            key=lambda ev: _CAPTION_PRINCIPLES_BY_ID.get(
                                ev.get("principle_id") or "", {}
                            ).get("priority", 99),
                        )
                        _top = sorted_pv[0]
                        _top_pid = _top.get("principle_id")
                        _entry = _CAPTION_PRINCIPLES_BY_ID.get(_top_pid, {}) if _top_pid else {}
                        _endorsement = _top.get("engine_endorsement", "absent")
                        _cue_key = {
                            "best": "cue_best",
                            "top_n": "cue_top_n",
                            "absent": "cue_absent",
                        }.get(_endorsement, "cue_absent")
                        # Gate cue_absent on engine-approved moves.
                        # Parth flagged Re1+ (cp_loss=-55, BEST move) and Rxd6
                        # (cp_loss=0, best move) where principle fired with
                        # absent endorsement, producing "Engine has another
                        # plan" cues on moves the engine actually liked. The
                        # principle simply didn't apply — its cue_absent
                        # text reads as critique. Skip surfacing in that case.
                        _played_cp_loss = (cp_loss if is_user else opp_cp_loss) or 0
                        if _endorsement == "absent" and _played_cp_loss < 30:
                            pass  # principle didn't apply; engine endorsed the move
                        else:
                            principle_cue = _entry.get(_cue_key) or _entry.get("cue_absent") or ""
                            principle_id_used = _top_pid
                except Exception as _caption_exc:
                    # Downgraded warning → info after audit noise: these
                    # fire predictably on PGN ↔ eval-data drift games
                    # (small corpus subset). The wrapper returns silent
                    # caption; only debugging needs every entry logged.
                    logger.info(
                        f"[caption_v5] move {full_move_number} {move_san} "
                        f"extract/render failed: {_caption_exc}"
                    )
                    caption_payload = {
                        "caption": "",
                        "rule_name": "R_FALLBACK_extractor_crashed",
                        "highlight_squares": [],
                        "arrows": [],
                    }
                    caption_primary_reason = None
                    caption_principles_violated = []

            # Build move output
            prev_move = move
            board.push(move)

            # Track user's eval_after for opponent blunder detection
            if is_user:
                prev_user_eval_after = eval_data.get("eval_after")

            # ── TIER 3 shape-pattern detection ─────────────────────
            # Runs on the POST-move board (the player sees the result
            # of the move in review). Engine verifier matches against
            # the engine's best move FOR THE PRE-MOVE position so the
            # "executed/missed pattern" semantics line up with the
            # move that was just played.
            shape_pattern_record: Optional[Dict[str, Any]] = None
            if _select_shape_for_position is not None:
                try:
                    # Detect on the pre-move board: the side-to-move at
                    # fen_before is the side whose pattern we're naming.
                    pre_move_board = chess.Board(fen_before)
                    shape_pattern_record = _select_shape_for_position(
                        pre_move_board,
                        eval_data={
                            "best_move_uci": eval_data.get("best_move_uci", ""),
                        },
                        shapes_fired_this_game=shapes_fired_this_game,
                        prev_move=prev_move,
                    )
                except Exception as _shape_exc:
                    logger.info(f"[shape_v3] detect failed on move {full_move_number}: {_shape_exc}")
                    shape_pattern_record = None

            # ── Post-move shape detection (Mohit fb_eb1d11ba227f) ──
            # Patterns in shape_patterns.py flagged `detect_phase=post_move`
            # describe "you walked into this" geometry — the vulnerability
            # was CREATED by the just-played move, the opposing side can
            # now execute it. These must be detected on the POST-move
            # board so the pattern is attached to the move that created
            # the geometry (e.g., black's Qd6 walks into white's e5 pawn
            # fork). Engine confirmation uses pv_after_played[0] — the
            # opponent's best response IS the executing move.
            if (
                shape_pattern_record is None
                and _detect_all_shapes is not None
                and severity in ("mistake", "blunder", "opp_mistake", "opp_blunder")
                and pv_after_played
            ):
                try:
                    # `board` is the post-move state (board.push(move) at line ~3277).
                    post_move_board = board.copy()
                    opp_best_uci = ""
                    try:
                        opp_best_uci = post_move_board.parse_san(pv_after_played[0]).uci()
                    except Exception:
                        opp_best_uci = ""
                    post_phase_ids = {
                        pid for pid, p in _SHAPE_PATTERNS_BY_ID.items()
                        if p.get("detect_phase") == "post_move"
                    }
                    if post_phase_ids:
                        all_post = _detect_all_shapes(post_move_board, prev_move=move)
                        post_candidates = [c for c in all_post if c["pattern_id"] in post_phase_ids]
                        post_candidates = _verify_shapes_with_engine(
                            post_candidates, {"best_move_uci": opp_best_uci}
                        )
                        if post_candidates:
                            post_candidates.sort(
                                key=lambda c: -_SHAPE_PATTERNS_BY_ID[c["pattern_id"]].get("priority", 0)
                            )
                            ev = post_candidates[0]
                            spec = _SHAPE_PATTERNS_BY_ID[ev["pattern_id"]]
                            # Key names must match select_shape_for_position's
                            # return contract (shape_layer.py:310-318) — V5
                            # move_output reads pattern_id / pattern_name /
                            # pattern_desc / mover / targets / executing_move
                            # at lines 3547-3552.
                            shape_pattern_record = {
                                "pattern_id":     ev["pattern_id"],
                                "pattern_name":   spec.get("name", ""),
                                "pattern_desc":   spec.get("description", ""),
                                "mover":          ev.get("mover"),
                                "targets":        ev.get("targets", []),
                                "executing_move": ev.get("executing_move"),
                                "evidence":       ev.get("evidence", ""),
                            }
                            shapes_fired_this_game.add(ev["pattern_id"])
                except Exception as _post_shape_exc:
                    logger.info(
                        f"[shape_post_move] detect failed on move {full_move_number}: "
                        f"{_post_shape_exc}"
                    )

            # ── Trap + opening recognition ─────────────────────────
            # Pure-Python detectors. Append the played SAN before running
            # so the matchers see the full prefix INCLUDING this move.
            played_san_so_far.append(move_san)

            trap_record: Optional[Dict[str, Any]] = None
            if detect_trap_setup is not None and match_trap_line_step is not None:
                try:
                    if active_trap is None:
                        hit = detect_trap_setup(played_san_so_far)
                        if hit:
                            active_trap = hit
                            active_trap_setup_completed_by_user = bool(is_user)
                            active_trap_step_cursor = 0
                            trap_record = {
                                "name": hit["name"],
                                "family": hit["family"],
                                "description": hit["description"],
                                "step": 0,
                                "step_label": "setup_completed",
                                "completed_by_user": active_trap_setup_completed_by_user,
                                "this_move_by_user": bool(is_user),
                                "next_expected_move": hit["trap_line"][0] if hit["trap_line"] else None,
                            }
                    else:
                        step_index = active_trap_step_cursor
                        if match_trap_line_step(active_trap, move_san, step_index):
                            step_label = "victim_falls" if step_index % 2 == 0 else "trap_player_punishes"
                            step_expl = ""
                            steps = active_trap.get("trap_line_steps") or []
                            if step_index < len(steps):
                                step_expl = steps[step_index].get("explanation", "")
                            next_mv = None
                            if step_index + 1 < len(active_trap["trap_line"]):
                                next_mv = active_trap["trap_line"][step_index + 1]
                            trap_record = {
                                "name": active_trap["name"],
                                "family": active_trap["family"],
                                "description": active_trap["description"],
                                "step": step_index + 1,
                                "step_label": step_label,
                                "step_explanation": step_expl,
                                "completed_by_user": active_trap_setup_completed_by_user,
                                "this_move_by_user": bool(is_user),
                                "next_expected_move": next_mv,
                            }
                            active_trap_step_cursor = step_index + 1
                            if active_trap_step_cursor >= len(active_trap["trap_line"]):
                                active_trap = None
                                active_trap_step_cursor = 0
                        else:
                            # Player deviated from trap_line — drop tracking.
                            active_trap = None
                            active_trap_step_cursor = 0
                except Exception as _trap_exc:
                    logger.info(f"[trap] detect failed on move {full_move_number}: {_trap_exc}")
                    trap_record = None

            opening_record: Optional[Dict[str, Any]] = None
            if match_opening_for_mover is not None:
                try:
                    mover_color = "white" if is_white else "black"
                    opening_record = match_opening_for_mover(played_san_so_far, mover_color)
                except Exception as _open_exc:
                    logger.info(f"[opening] detect failed on move {full_move_number}: {_open_exc}")
                    opening_record = None

            move_output = {
                "move_number": full_move_number,
                "move_san": move_san,
                "is_user_move": is_user,
                "is_white": is_white,
                "fen_before": fen_before,
                "fen_after": board.fen(),
                "phase": phase,
                "opening_name": opening_name,

                # Evaluation - include opponent eval data too
                "cp_loss": cp_loss if is_user else opp_cp_loss,
                "eval_before": eval_data.get("eval_before") if is_user else opp_eval_before,
                "eval_after": eval_data.get("eval_after") if is_user else opp_eval_after,
                "best_move_san": best_move,
                # Threaded for the deterministic PV tactical analyzer so it
                # can explain why the best move works (material gained,
                # forks, defender deflection, etc.) instead of relying on
                # the LLM narrator to guess the reason.
                "best_move_uci": eval_data.get("best_move_uci", ""),
                "pv_after_best": pv_after_best,
                # The opponent's best reply to the played move — the
                # PUNISHMENT line. Stockfish computes this for bad
                # moves (mistake/blunder/inaccuracy in stockfish_service
                # lines 628-640) but until now it was dropped on the
                # floor instead of carried forward. Captions need it
                # to teach WHY a blunder is bad (the threat that
                # follows), not just WHAT the better move was. Mohit
                # feedback fb_eb1d11ba227f.
                "pv_after_played": pv_after_played,
                "severity": severity,
                "is_mistake": severity in ("mistake", "blunder", "opp_blunder", "opp_mistake"),
                
                # Adaptive priority
                "priority": move_priority,
                "weakness_match": weakness_match,
                "weakness_count": weakness_count if weakness_match else None,
                
                # ── LEGACY PROSE FIELDS RETIRED ─────────────────
                # narrative / plan.{goal,current_problem,consequence,
                # better_approach,transferable_learning,concept_id,
                # concept_type} / your_plan_now / future_moves are no
                # longer emitted. The frontend reads its move-by-move
                # text from the new V5 caption pipeline via the
                # /coach/decryption/per-move/{game_id} endpoint, which
                # sources from `caption` below. Per memory rule
                # `feedback_v5_caption_rewrite_no_patches.md`: ship the
                # new pipeline end-to-end, drop the legacy prose.
                #
                # Engine candidate moves (just the SAN list) are kept
                # on plan.candidate_moves so the click-to-see-line UI
                # still works — those aren't prose, they're an
                # interactive game-tree feature.
                "narrative": "",
                "plan": (
                    {
                        "goal": None,
                        "current_problem": None,
                        "consequence": None,
                        "better_approach": None,
                        "transferable_learning": None,
                        "concept_id": None,
                        "concept_type": None,
                        "candidate_moves": plan.candidate_moves,
                    }
                    if plan and plan.candidate_moves else None
                ),
                "future_moves": [],
                "highlight_squares": highlight_squares,

                # Concept-acknowledgment loop retired with the legacy
                # transferable_learning surface (frontend JSX deleted).
                "needs_acknowledgment": False,
                "already_acknowledged": False,
                "acknowledgment_prompt": None,
                "concept_id": None,
                "concept_type": None,

                "your_plan_now": None,

                # Good move tracking — concept_applied is the only
                # legacy "good move" string we leave in; renderer
                # doesn't surface it but other lab consumers may.
                "is_best_move": is_best_move,
                "concept_applied": concept_applied,

                # ── NEW V5 CAPTION PIPELINE (the only text source) ─
                # Per docs/caption_pipeline_design.md. Frontend reads
                # via /coach/decryption/per-move/{game_id}.
                "caption": caption_payload["caption"],
                "rule_name": caption_payload["rule_name"],
                "caption_arrows": caption_payload["arrows"],
                "caption_highlight_squares": caption_payload["highlight_squares"],
                "caption_facts_primary_reason": caption_primary_reason,
                # Teaching layer — list of evidence dicts, one per
                # firing principle. Grows as detectors are shipped
                # one-by-one per feedback_design_clean_code_leaky.md.
                # Audit script reads this; renderer integration is a
                # later commit once enough detectors are live.
                "caption_facts_principles_violated": caption_principles_violated,
                # Captured piece type (pawn/knight/bishop/rook/queen/None).
                # Surfaced from caption_facts so the LLM caption generator
                # can name what was actually taken instead of guessing
                # "won a pawn". Parth flagged exd6 captioned "won a pawn"
                # when actually a knight was captured.
                "captured_piece_type": caption_captured_piece,
                # Teaching cue — highest-priority principle's
                # endorsement-tiered cue string. Frontend renders this
                # as a separate italic line under the main caption so
                # the diagnosis + the named-principle habit stay
                # visually distinct.
                "principle_cue": principle_cue,
                "principle_id_used": principle_id_used,

                # ── TIER 3 shape pattern (visual danger language) ─
                # At most one pattern per move; once-per-game suppression.
                # Frontend renders pattern_name as a callout under the
                # caption, with pattern_desc on hover/expansion and
                # target squares for board highlighting.
                "shape_pattern_id":   shape_pattern_record["pattern_id"] if shape_pattern_record else None,
                "shape_pattern_name": shape_pattern_record["pattern_name"] if shape_pattern_record else None,
                "shape_pattern_desc": shape_pattern_record["pattern_desc"] if shape_pattern_record else None,
                "shape_pattern_mover": shape_pattern_record["mover"] if shape_pattern_record else None,
                "shape_pattern_targets": shape_pattern_record["targets"] if shape_pattern_record else [],
                "shape_pattern_executing_move": shape_pattern_record["executing_move"] if shape_pattern_record else None,

                # ── Trap recognition (data/traps.json) ─────────────
                # Set on the move that completes a known trap setup, and on
                # subsequent moves that follow the authored trap_line.
                # Fields nested under one dict to keep the move record clean.
                "trap": trap_record,

                # ── Opening curriculum match (data/opening_curriculum.json) ─
                # Set when the mover's played-move prefix matches an opening's
                # setup_order ≥ 3 steps. Carries name, summary, golden_rules.
                "opening": opening_record,
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
        
        # ─── NARRATIVE ENHANCEMENT PASS ───────────────────────────────
        # Two-stage narrative: try the deterministic PV tactical analyzer
        # first (walks Stockfish's principal variation with python-chess;
        # grounded, no fabrication). If it finds a concrete tactical reason
        # (fork, deflection, material gain), use that as the narrative. If
        # not, fall back to the LLM narrator for positional/vague mistakes
        # where the PV doesn't yield a clean tactical signal.
        try:
            from services.pv_tactical_analyzer import explain_best_move_tactically
            from services.v5_llm_narrator import generate_concise_narrative

            mistakes_to_enhance = [
                (i, m) for i, m in enumerate(decryption_data)
                if m.get("severity") in ("mistake", "blunder", "inaccuracy")
                and m.get("plan")
                and m.get("priority") != "silent"
            ]

            if mistakes_to_enhance:
                logger.info(
                    f"[DECRYPTION V5] Enhancing {len(mistakes_to_enhance)} mistakes "
                    f"(deterministic tactical first, LLM fallback)..."
                )

                det_hits = 0
                llm_hits = 0

                for idx, move_data in mistakes_to_enhance:
                    # Stage 1: deterministic PV walk.
                    det_narrative = None
                    try:
                        det_narrative = explain_best_move_tactically(
                            fen_before=move_data.get("fen_before", ""),
                            best_move_uci=move_data.get("best_move_uci", ""),
                            best_move_san=move_data.get("best_move_san", ""),
                            pv_after_best=move_data.get("pv_after_best") or [],
                        )
                    except Exception as e:
                        logger.debug(f"PV analyzer failed for move {idx}: {e}")

                    if det_narrative:
                        decryption_data[idx]["narrative"] = det_narrative
                        decryption_data[idx]["narrative_source"] = "pv_tactical"
                        det_hits += 1
                        continue

                    # Stage 2: LLM narrator fallback.
                    try:
                        llm_narrative = await generate_concise_narrative(
                            move_san=move_data.get("move_san", ""),
                            plan_data=move_data.get("plan", {}),
                            phase=move_data.get("phase", "middlegame"),
                            severity=move_data.get("severity", "mistake"),
                            is_user_move=True,
                        )
                        if llm_narrative:
                            decryption_data[idx]["narrative"] = llm_narrative
                            decryption_data[idx]["narrative_source"] = "llm"
                            llm_hits += 1
                    except Exception as e:
                        logger.warning(f"LLM enhancement failed for move {idx}: {e}")

                logger.info(
                    f"[DECRYPTION V5] Narrative pass complete: "
                    f"{det_hits} deterministic, {llm_hits} LLM fallback"
                )
        except ImportError:
            logger.warning("[DECRYPTION V5] Narrative enhancers not available, using rule-based narratives")
        except Exception as e:
            logger.warning(f"[DECRYPTION V5] Narrative enhancement skipped: {e}")

        # Hallucination guard pass — every per-move text the user will
        # see (narrative, consequence, your_plan_now, better_approach)
        # gets verified against that move's FEN. Strings with hallucinated
        # piece references are stripped (set to empty) so the frontend
        # falls back to other available context. Better silence than
        # confidently-wrong claims. Source bugs:
        #   fb_a36d3d477950 ("Your pawn on f4" with no pawn there)
        #   fb_4f5aff6798ed ("Your queen on g5" — actually a bishop)
        #   fb_93b8af5dd608 ("your knight on e5" — knight is enemy's)
        #   fb_274dfae7eb44 ("your bishop on f7" — bishop is enemy's)
        try:
            from services.coaching_text_guard import verify_coaching_text
            stripped = 0
            for item in decryption_data:
                fen = item.get("fen_before") or item.get("fen") or ""
                if not fen:
                    continue
                for field in ("narrative", "consequence", "your_plan_now", "better_approach"):
                    text = (item.get(field) or "").strip()
                    if not text:
                        continue
                    issues = verify_coaching_text(text, fen, user_color=user_color)
                    if issues:
                        logger.warning(
                            f"[DECRYPTION V5] Stripped hallucinated {field} on move "
                            f"{item.get('move_number')} {item.get('move_san')}: "
                            f"{[i.detail for i in issues]}"
                        )
                        item[field] = ""
                        stripped += 1
            if stripped:
                logger.warning(f"[DECRYPTION V5] Hallucination guard stripped {stripped} fields")
        except Exception as e:
            logger.warning(f"[DECRYPTION V5] Hallucination guard skipped: {e}")

        # Vacuous text suppressor — Category 5. After rendering, if the
        # narrative on a mistake/inaccuracy/blunder is vacuous (no
        # squares, no specific moves, no tactical pattern names —
        # filler like "Something just changed on the board"), strip it.
        # Frontend falls back to severity badge + best move, which is
        # honest silence vs. confidently-wrong fluff. Source bugs:
        #   fb_53710952f696, fb_81ea58440719, fb_2d3cd3b7bf57,
        #   fb_50304a538492, fb_2f2b3ec9dcde
        try:
            from services.vacuous_text_detector import strip_vacuous_segments
            vacuous_stripped = 0
            vacuous_partial = 0
            for item in decryption_data:
                severity = (item.get("severity") or "").strip().lower()
                phase = (item.get("phase") or "").strip().lower()
                played_san = item.get("move_san") or ""
                # Sentence-level strip: drops only the filler-bearing
                # sentences, preserving opening names / diagnoses /
                # alt-move recommendations that appear alongside filler.
                # Earlier all-or-nothing wipe nuked captions like
                # "This is the Nimzo Indian Defense… Bishop slides to
                # Bb4. Bishops love open diagonals!" — losing the
                # opening-name content with the praise tail.
                for field in ("narrative", "consequence", "your_plan_now"):
                    text = (item.get(field) or "").strip()
                    if not text:
                        continue
                    cleaned = strip_vacuous_segments(
                        text,
                        severity=severity,
                        played_move_san=played_san,
                        phase=phase,
                    )
                    if cleaned == text:
                        continue  # nothing to do
                    if not cleaned:
                        logger.warning(
                            f"[DECRYPTION V5] Stripped vacuous {field} on move "
                            f"{item.get('move_number')} {played_san}: "
                            f"\"{text[:80]}\""
                        )
                        item[field] = ""
                        vacuous_stripped += 1
                    else:
                        logger.info(
                            f"[DECRYPTION V5] Trimmed filler from {field} on move "
                            f"{item.get('move_number')} {played_san}: "
                            f"\"{text[:80]}\" -> \"{cleaned[:80]}\""
                        )
                        item[field] = cleaned
                        vacuous_partial += 1
            if vacuous_stripped or vacuous_partial:
                logger.warning(
                    f"[DECRYPTION V5] Vacuous-text suppressor: "
                    f"{vacuous_stripped} fields fully stripped, "
                    f"{vacuous_partial} partially trimmed"
                )
        except Exception as e:
            logger.warning(f"[DECRYPTION V5] Vacuous-text suppressor skipped: {e}")

        # Multi-ply chain verifier — Category 8. Coaching strings often
        # claim future move sequences ("After g4 Nxe5 Nxe5, your knight
        # on e5 gets taken"). Verify each move in the chain is legal
        # from the post-played-move position. Illegal chains (typo'd
        # moves, hallucinated sequences) get the field wiped.
        # Source bug: fb_93b8af5dd608 (chain interpretation issues).
        try:
            from services.coaching_text_guard import verify_chain_claims
            chain_stripped = 0
            for item in decryption_data:
                # Compute post-move FEN. The chain claim describes what
                # happens AFTER the played move, so we verify the chain
                # starting from that position.
                fen_pre = item.get("fen_before") or item.get("fen") or ""
                played_san = item.get("move_san") or ""
                if not fen_pre or not played_san:
                    continue
                try:
                    _b = chess.Board(fen_pre)
                    _b.push_san(played_san)
                    fen_post = _b.fen()
                except Exception:
                    continue
                for field in ("narrative", "consequence"):
                    text = (item.get(field) or "").strip()
                    if not text:
                        continue
                    chain_issues = verify_chain_claims(text, fen_post)
                    if chain_issues:
                        logger.warning(
                            f"[DECRYPTION V5] Stripped illegal-chain {field} on move "
                            f"{item.get('move_number')} {played_san}: "
                            f"{[i.detail for i in chain_issues]}"
                        )
                        item[field] = ""
                        chain_stripped += 1
            if chain_stripped:
                logger.warning(f"[DECRYPTION V5] Chain-legality verifier stripped {chain_stripped} fields")
        except Exception as e:
            logger.warning(f"[DECRYPTION V5] Chain-legality verifier skipped: {e}")

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
