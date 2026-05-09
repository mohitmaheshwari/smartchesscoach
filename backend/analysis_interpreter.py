"""
Analysis Interpreter Service - Behavioral Pattern Detection Layer

This service runs AFTER Stockfish analysis to interpret WHY the player
made their decisions. It transforms raw engine data into coaching insights.

Pipeline position:
  Stockfish → [raw moves] → THIS SERVICE → [interpreted moves] → Storage

Key principle: Engine analysis (what happened) is separate from
behavioral interpretation (why it happened).
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import chess

from cognitive_gap_service import (
    CognitiveGap,
    analyze_cognitive_gap,
    find_hanging_pieces,
    find_threats
)
from services.visual_shapes import detect_shapes_for_move

logger = logging.getLogger(__name__)


# Canonical cognitive-gap taxonomy used by the Lab / Home / Training surfaces
# and keyed into COACHING_DIAGNOSIS in routes/training_advanced.py. The older
# CognitiveGap enum used different string values (e.g. "hanging_piece_blindness"
# instead of "piece_safety"), which caused downstream lookups to miss and the
# prod pool to collapse into just 2 tags. All new classifier output emits
# these canonical strings.
GAP_PIECE_SAFETY       = "piece_safety"
GAP_IGNORE_THREAT      = "ignore_threat"
GAP_CALCULATION_DEPTH  = "calculation_depth"
GAP_MISSED_TACTIC      = "missed_tactic"
GAP_TACTICAL_OVERSIGHT = "tactical_oversight"
GAP_KING_SAFETY        = "king_safety"
GAP_PAWN_STRUCTURE     = "pawn_structure"
GAP_PIECE_ACTIVITY     = "piece_activity"
GAP_OPENING_KNOWLEDGE  = "opening_knowledge"
GAP_ENDGAME_TECHNIQUE  = "endgame_technique"


def _count_non_king_pieces(fen: str) -> int:
    """Piece count on the board excluding kings — used to detect endgame phase."""
    if not fen:
        return 32
    try:
        board_part = fen.split(" ", 1)[0]
        return sum(1 for ch in board_part if ch.isalpha() and ch not in "Kk")
    except Exception:
        return 32


def _is_pawn_move(move_uci: str, fen_before: str) -> bool:
    """True if the played move was a pawn move (from the side to move's POV)."""
    if not move_uci or len(move_uci) < 4 or not fen_before:
        return False
    try:
        import chess
        board = chess.Board(fen_before)
        mv = chess.Move.from_uci(move_uci)
        piece = board.piece_at(mv.from_square)
        return piece is not None and piece.piece_type == chess.PAWN
    except Exception:
        return False


def _king_under_attack(fen_before: str, user_is_side_to_move: bool = True) -> bool:
    """Rough check: is the side-to-move's king under immediate attack or highly exposed?"""
    if not fen_before:
        return False
    try:
        import chess
        board = chess.Board(fen_before)
        if board.is_check():
            return True
        king_sq = board.king(board.turn)
        if king_sq is None:
            return False
        # Count opponent attackers on squares adjacent to the king
        opp = not board.turn
        adj = chess.SquareSet(chess.BB_KING_ATTACKS[king_sq])
        attacker_count = sum(1 for sq in adj if board.attackers(opp, sq))
        return attacker_count >= 2
    except Exception:
        return False


def _best_move_is_forcing(best_move_san: str) -> bool:
    """Captures, checks, mate — the forcing-move family that defines 'missed tactic'."""
    if not best_move_san:
        return False
    return any(ch in best_move_san for ch in ("x", "+", "#"))


_PIECE_VALUE_CP = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


def _played_drops_material(fen_before: str, move_uci: str, threshold_cp: int = 200) -> bool:
    """Did the played move drop ≥ threshold_cp of material to a forced
    opp recapture? Used as the hard signal for tactical/calculation
    failures: if the user's move loses material via simple recapture,
    the gap is tactical, not positional."""
    if not fen_before or not move_uci or len(move_uci) < 4:
        return False
    try:
        board = chess.Board(fen_before)
        mv = chess.Move.from_uci(move_uci)
        if mv not in board.legal_moves:
            return False
        moving_piece = board.piece_at(mv.from_square)
        if not moving_piece:
            return False
        attacker_value = _PIECE_VALUE_CP.get(moving_piece.piece_type, 0)
        board.push(mv)
        user_color = not board.turn
        attackers = board.attackers(not user_color, mv.to_square)
        if not attackers:
            return False
        cheapest_value = min(
            _PIECE_VALUE_CP.get(board.piece_at(a).piece_type, 9999)
            for a in attackers if board.piece_at(a)
        )
        defenders = board.attackers(user_color, mv.to_square)
        if not defenders:
            # Hanging — full attacker_value lost
            return attacker_value >= threshold_cp
        # With defenders, we lose (attacker_value - cheapest_attacker)
        cp_lost = max(0, attacker_value - cheapest_value)
        return cp_lost >= threshold_cp
    except Exception:
        return False


def _move_involves_king(fen_before: str, move_uci: str) -> bool:
    """Did the played move involve the user's king (move it OR break
    its pawn shield in front of a castled king)?"""
    if not fen_before or not move_uci or len(move_uci) < 4:
        return False
    try:
        board = chess.Board(fen_before)
        mv = chess.Move.from_uci(move_uci)
        moving = board.piece_at(mv.from_square)
        if not moving:
            return False
        if moving.piece_type == chess.KING:
            return True
        if moving.piece_type != chess.PAWN:
            return False
        user_color = moving.color
        king_sq = board.king(user_color)
        if king_sq is None:
            return False
        kf = chess.square_file(king_sq)
        kr = chess.square_rank(king_sq)
        pf = chess.square_file(mv.from_square)
        pr = chess.square_rank(mv.from_square)
        castled_rank = 0 if user_color == chess.WHITE else 7
        forward = 1 if user_color == chess.WHITE else -1
        if kr == castled_rank and abs(kf - pf) <= 2 and pr == kr + forward:
            return True
        return False
    except Exception:
        return False


def _played_move_hangs_piece(fen_before: str, move_uci: str) -> bool:
    """Did the played move leave a user piece attacked with no defender?

    Reliable inline replacement for cognitive_gap_service.find_hanging_pieces,
    which expects a chess.Board + color but was being called with a FEN string
    (silent exception, always returned falsy). With this detector piece_safety
    actually fires on the classifier's output.
    """
    if not fen_before or not move_uci or len(move_uci) < 4:
        return False
    try:
        import chess
        board = chess.Board(fen_before)
        mv = chess.Move.from_uci(move_uci)
        if mv not in board.legal_moves:
            return False
        board.push(mv)
        # After pushing, it's opponent's turn — we want to see if any piece
        # belonging to the player who just moved is attacked and undefended.
        user_color = not board.turn
        for sq, piece in board.piece_map().items():
            if piece.color != user_color or piece.piece_type == chess.KING:
                continue
            if board.attackers(not user_color, sq) and not board.attackers(user_color, sq):
                return True
        return False
    except Exception:
        return False


class CriticalReason(str, Enum):
    """Why a move is marked critical for coaching"""
    TACTICAL_ERROR = "tactical_error"       # cp_loss >= 100 or blunder
    TURNING_POINT = "turning_point"         # eval swing >= 120
    PATTERN_EVENT = "pattern_event"         # behavioral pattern detected
    MISSED_MATE = "missed_mate"             # had mate, didn't take it
    POSITIONAL_COLLAPSE = "positional_collapse"  # gradual position decay


@dataclass
class InterpretedMove:
    """Move with behavioral interpretation added"""
    move_number: int
    move_uci: str
    fen_before: str
    fen_after: str
    cp_loss: int
    eval_swing: int
    is_turning_point: bool
    evaluation: str  # good/mistake/blunder etc

    # Behavioral interpretation (NEW)
    cognitive_gap: Optional[str] = None
    is_critical: bool = False
    critical_reason: Optional[str] = None
    gap_confidence: float = 0.0
    gap_evidence: str = ""
    coaching_focus: str = ""
    # Visual-shape detections (orthogonal to cognitive_gap — both can fire
    # on the same move; shapes describe geometric danger patterns, the
    # cognitive_gap describes the move's tactical/strategic mistake type).
    shapes: List[Dict] = field(default_factory=list)


class AnalysisInterpreter:
    """
    Interprets raw Stockfish analysis to identify behavioral patterns.
    
    This is the bridge between engine truth and coaching insight.
    """
    
    def __init__(self, db=None):
        self.db = db
    
    def interpret_moves(
        self,
        move_evaluations: List[Dict],
        user_color: str = "white"
    ) -> List[InterpretedMove]:
        """
        Process raw move evaluations and add behavioral interpretation.

        Args:
            move_evaluations: Raw moves from Stockfish analysis
            user_color: Which color the user played

        Returns:
            List of InterpretedMove with cognitive gap analysis
        """
        interpreted = []

        # Visual-shape detectors need a few future plies for verifier checks
        # (e.g. queen-too-early needs to see whether the queen got chased in
        # the next 4 plies). Slice once per move and pass through.
        SHAPE_LOOKAHEAD = 6
        for idx, move in enumerate(move_evaluations):
            future = move_evaluations[idx + 1: idx + 1 + SHAPE_LOOKAHEAD]
            interpreted_move = self._interpret_single_move(move, future_moves=future)
            interpreted.append(interpreted_move)

        # Second pass: detect patterns across moves
        self._detect_cross_move_patterns(interpreted)

        return interpreted
    
    def _interpret_single_move(
        self,
        move: Dict,
        future_moves: Optional[List[Dict]] = None,
    ) -> InterpretedMove:
        """Interpret a single move for behavioral patterns.

        `future_moves` is the next handful of plies (for shape verifiers).
        """

        cp_loss = move.get("cp_loss", 0)
        eval_swing = move.get("eval_swing", 0)
        is_turning_point = move.get("is_turning_point", False)
        evaluation = move.get("evaluation", "good")
        fen_before = move.get("fen_before", "")
        fen_after = move.get("fen_after", "")
        mate_info = move.get("mate_info")
        
        # Initialize interpretation
        cognitive_gap = None
        is_critical = False
        critical_reason = None
        gap_confidence = 0.0
        gap_evidence = ""
        coaching_focus = ""
        
        # TRIGGER 1: Tactical Severity (cp_loss >= 100)
        if cp_loss >= 100 or evaluation in ["blunder", "mistake"]:
            is_critical = True
            critical_reason = CriticalReason.TACTICAL_ERROR.value
            
            # Run cognitive gap analysis
            gap_result = self._analyze_gap(move)
            if gap_result:
                cognitive_gap = gap_result.get("primary_gap")
                gap_confidence = gap_result.get("confidence", 0.0)
                gap_evidence = gap_result.get("evidence", "")
                coaching_focus = gap_result.get("coaching_focus", "")
        
        # TRIGGER 2: Missed Mate
        if mate_info and mate_info.get("before") is not None:
            # Had mate before but maybe lost it
            mate_before = mate_info.get("before")
            mate_after = mate_info.get("after")
            
            if mate_before is not None and (mate_after is None or abs(mate_after) > abs(mate_before) + 2):
                is_critical = True
                critical_reason = CriticalReason.MISSED_MATE.value
                cognitive_gap = CognitiveGap.TACTICAL_OVERSIGHT.value
        
        # TRIGGER 3: Turning Point (eval swing >= 120)
        if is_turning_point and not is_critical:
            is_critical = True
            critical_reason = CriticalReason.TURNING_POINT.value
            
            # Analyze why momentum shifted
            gap_result = self._analyze_gap(move)
            if gap_result:
                cognitive_gap = gap_result.get("primary_gap")
                gap_confidence = gap_result.get("confidence", 0.0)
        
        # TRIGGER 4: Pattern Event (from cognitive gap detection)
        if not is_critical and fen_before:
            gap_result = self._analyze_gap(move)
            if gap_result and gap_result.get("is_behavior_event"):
                is_critical = True
                critical_reason = CriticalReason.PATTERN_EVENT.value
                cognitive_gap = gap_result.get("primary_gap")
                gap_confidence = gap_result.get("confidence", 0.0)
                gap_evidence = gap_result.get("evidence", "")
                coaching_focus = gap_result.get("coaching_focus", "")
        
        # Visual-shape detection — orthogonal to cognitive_gap. Both layers
        # may fire on the same move (e.g. a queen-too-early move can also be
        # a piece_safety blunder). Verifier-gated inside detect_shapes_for_move
        # so misfires never leak to the user-facing surface.
        try:
            shapes = detect_shapes_for_move(move, future_moves or []) or []
        except Exception as exc:
            logger.warning(f"Shape detection failed at move {move.get('move_number')}: {exc}")
            shapes = []

        return InterpretedMove(
            move_number=move.get("move_number", 0),
            move_uci=move.get("move_uci", ""),
            fen_before=fen_before,
            fen_after=fen_after,
            cp_loss=cp_loss,
            eval_swing=eval_swing,
            is_turning_point=is_turning_point,
            evaluation=evaluation,
            cognitive_gap=cognitive_gap,
            is_critical=is_critical,
            critical_reason=critical_reason,
            gap_confidence=gap_confidence,
            gap_evidence=gap_evidence,
            coaching_focus=coaching_focus,
            shapes=shapes,
        )
    
    def _analyze_gap(self, move: Dict) -> Optional[Dict]:
        """
        Classify the cognitive gap behind a critical move.

        Emits one of the canonical CLAUDE.md taxonomy strings (see GAP_*
        constants above). Priority-ordered: phase-specific gaps first
        (opening / endgame), then king/piece safety, then threat / tactic
        detectors, then pawn/piece framing, then a cp-loss fallback.
        Earlier detectors are more specific — they claim the move before
        generic buckets swallow it.
        """
        try:
            fen_before = move.get("fen_before", "")
            played_uci = move.get("move_uci", "")
            best_move_san = move.get("best_move", "")
            cp_loss = move.get("cp_loss", 0)
            evaluation = move.get("evaluation", "good")
            threat = move.get("threat")
            move_number = move.get("move_number", 0) or 0

            if not fen_before:
                return None

            piece_count = _count_non_king_pieces(fen_before)
            is_opening = move_number > 0 and move_number <= 10
            is_endgame = piece_count <= 12

            primary_gap = None
            confidence = 0.0
            evidence = ""
            coaching_focus = ""
            is_behavior_event = False

            # ── Rule order rewritten 2026-05-09 to fix mis-classification.
            #
            # Old order: king_safety → piece_safety → opening → endgame →
            #   ignore_threat → missed_tactic → pawn_structure → piece_activity.
            #
            # 1000-game audit found:
            #   - king_safety fired from POSITION pressure regardless of
            #     what the move did: 33.6% misfire rate.
            #   - piece_activity was a catch-all for any non-pawn move
            #     where engine's best was non-forcing — caught calculation
            #     errors and labelled them "passive pieces".
            #
            # New order leads with MOVE-LEVEL evidence:
            #   1. Hanging piece (your move drops material) → piece_safety
            #   2. Material drop on the played move ≥200cp → tactical_oversight
            #   3. Engine's best is forcing → missed_tactic
            #   4. King-safety with MOVE evidence (move involved king
            #      OR addressed a king threat) → king_safety
            #   5. Phase + structural buckets (opening / endgame / pawn)
            #   6. piece_activity LAST and only with positive evidence
            #      (no tactic missed, played move quiet)

            # 1. Piece safety — played move left a user piece hanging.
            #    Strongest signal; fires first.
            if cp_loss >= 100 and _played_move_hangs_piece(fen_before, played_uci):
                primary_gap = GAP_PIECE_SAFETY
                confidence = 0.85
                evidence = "Move left a piece attacked with no defender"
                coaching_focus = (
                    "Before each move, scan your pieces — is anything undefended?"
                )
                is_behavior_event = True

            # 2. Tactical / calculation blunder — played move drops material
            #    to a forced recapture. Catches the failed sacrifices that
            #    were previously misclassified as piece_activity.
            if primary_gap is None and cp_loss >= 200 and _played_drops_material(fen_before, played_uci, threshold_cp=200):
                primary_gap = GAP_TACTICAL_OVERSIGHT
                confidence = 0.85
                evidence = f"Played move drops material — calculation failure"
                coaching_focus = (
                    "Before sacrificing a piece, calculate at least 3 moves of forcing reply."
                )
                is_behavior_event = True

            # 3. Best move was a forcing move (capture/check/mate). User
            #    missed a concrete tactic.
            if primary_gap is None and cp_loss >= 150 and _best_move_is_forcing(best_move_san):
                primary_gap = GAP_MISSED_TACTIC
                confidence = 0.75
                evidence = f"Missed {best_move_san}"
                coaching_focus = "Scan checks, captures, threats every move"

            # 4. King safety — TIGHTENED. Old rule fired on position
            #    pressure alone (34% misfire). New rule requires the
            #    move to actually involve the king OR (king under attack
            #    AND played move didn't address it).
            if primary_gap is None and cp_loss >= 100:
                try:
                    move_touches_king = _move_involves_king(fen_before, played_uci)
                    king_in_trouble = _king_under_attack(fen_before)
                    if move_touches_king or (king_in_trouble and not _best_move_is_forcing(best_move_san)):
                        primary_gap = GAP_KING_SAFETY
                        confidence = 0.75
                        evidence = (
                            "Played move involved king or pawn shield"
                            if move_touches_king
                            else "King under pressure pre-move and threat went unaddressed"
                        )
                        coaching_focus = "Check the king's safety before attacking"
                        is_behavior_event = True
                except Exception:
                    pass

            # 5. Opponent had a real threat that was ignored.
            if primary_gap is None:
                try:
                    threats = find_threats(fen_before)
                    if threats and (threat or evaluation in ("blunder", "mistake")):
                        primary_gap = GAP_IGNORE_THREAT
                        confidence = 0.8
                        evidence = f"Opponent threat: {threat or 'unaddressed'}"
                        coaching_focus = "Name the threat before picking your move"
                        is_behavior_event = True
                except Exception:
                    pass

            # 6. Phase context — opening/endgame — only if no specific gap fired.
            if primary_gap is None and cp_loss >= 100 and is_opening:
                primary_gap = GAP_OPENING_KNOWLEDGE
                confidence = 0.7
                evidence = f"Opening move {move_number} lost {cp_loss}cp"
                coaching_focus = "Learn the ideas behind the opening, not just the moves"

            if primary_gap is None and cp_loss >= 100 and is_endgame:
                primary_gap = GAP_ENDGAME_TECHNIQUE
                confidence = 0.75
                evidence = f"Endgame slip cost {cp_loss}cp"
                coaching_focus = "Active king, passed pawns, clean technique"

            # 7. Pawn move with lasting structural cost.
            if primary_gap is None and cp_loss >= 100 and _is_pawn_move(played_uci, fen_before):
                primary_gap = GAP_PAWN_STRUCTURE
                confidence = 0.6
                evidence = "Pawn move with lasting positional cost"
                coaching_focus = "Every pawn push is permanent — think before pushing"

            # 8. Piece activity — TIGHTENED. Old rule was a catch-all
            #    when engine's best was non-forcing (~5% confirmed misfire,
            #    ~18% suspicious). New rule additionally requires:
            #      - played move was NOT a capture/check (those aren't
            #        "passive" by definition)
            #      - played move did NOT drop material (that's tactical)
            #      - played move was NOT a king move (that's king_safety)
            played_san_str = move.get("move_san") or ""
            played_is_forcing = "x" in played_san_str or "+" in played_san_str or "#" in played_san_str
            if (
                primary_gap is None
                and cp_loss >= 100
                and best_move_san
                and not _best_move_is_forcing(best_move_san)
                and not _is_pawn_move(played_uci, fen_before)
                and not played_is_forcing
                and not _played_drops_material(fen_before, played_uci, threshold_cp=200)
                and not _move_involves_king(fen_before, played_uci)
            ):
                primary_gap = GAP_PIECE_ACTIVITY
                confidence = 0.55
                evidence = f"A quieter move ({best_move_san}) improved piece coordination"
                coaching_focus = "Look for moves that activate sleeping pieces"

            # cp-loss fallback — the generic buckets catch anything the
            # specific detectors above missed.
            if primary_gap is None:
                if evaluation == "blunder" and cp_loss >= 300:
                    primary_gap = GAP_TACTICAL_OVERSIGHT
                    confidence = 0.9
                    evidence = f"Lost {cp_loss} centipawns"
                    coaching_focus = "Pause for the opponent's best reply"
                elif evaluation == "mistake" and cp_loss >= 100:
                    primary_gap = GAP_CALCULATION_DEPTH
                    confidence = 0.7
                    evidence = "One move deeper was needed"
                    coaching_focus = "Calculate one move deeper"
                elif move.get("is_turning_point"):
                    primary_gap = GAP_CALCULATION_DEPTH
                    confidence = 0.5
                    evidence = "Position shifted here"
                    coaching_focus = "Re-evaluate after each exchange"
                    is_behavior_event = True

            if primary_gap:
                return {
                    "primary_gap": primary_gap,
                    "confidence": confidence,
                    "evidence": evidence,
                    "coaching_focus": coaching_focus,
                    "is_behavior_event": is_behavior_event
                }

            return None

        except Exception as e:
            logger.warning(f"Gap analysis failed: {e}")
            return None
    
    def _detect_cross_move_patterns(self, moves: List[InterpretedMove]):
        """
        Detect patterns that span multiple moves.
        
        Examples:
        - Repeated threat blindness
        - Gradual positional collapse
        - Time pressure pattern
        """
        # Count cognitive gaps to detect patterns
        gap_counts = {}
        
        for move in moves:
            if move.cognitive_gap:
                gap_counts[move.cognitive_gap] = gap_counts.get(move.cognitive_gap, 0) + 1
        
        # If same gap appears 3+ times, mark later occurrences as pattern events
        repeated_gaps = {gap for gap, count in gap_counts.items() if count >= 3}
        
        occurrence_count = {}
        for move in moves:
            if move.cognitive_gap in repeated_gaps:
                occurrence_count[move.cognitive_gap] = occurrence_count.get(move.cognitive_gap, 0) + 1
                
                # Mark as critical if this is 2nd+ occurrence
                if occurrence_count[move.cognitive_gap] >= 2 and not move.is_critical:
                    move.is_critical = True
                    move.critical_reason = CriticalReason.PATTERN_EVENT.value
                    move.gap_evidence = f"Repeated pattern ({occurrence_count[move.cognitive_gap]}x)"
    
    def get_critical_moves(self, interpreted_moves: List[InterpretedMove]) -> List[InterpretedMove]:
        """Extract only the critical moves for PV enrichment"""
        return [m for m in interpreted_moves if m.is_critical]
    
    def get_interpretation_summary(self, interpreted_moves: List[InterpretedMove]) -> Dict:
        """
        Generate a summary of behavioral patterns found.
        
        Returns:
            Summary dict with pattern counts and primary issues
        """
        total = len(interpreted_moves)
        critical = sum(1 for m in interpreted_moves if m.is_critical)
        
        # Count by reason
        reason_counts = {}
        for m in interpreted_moves:
            if m.critical_reason:
                reason_counts[m.critical_reason] = reason_counts.get(m.critical_reason, 0) + 1
        
        # Count by cognitive gap
        gap_counts = {}
        for m in interpreted_moves:
            if m.cognitive_gap:
                gap_counts[m.cognitive_gap] = gap_counts.get(m.cognitive_gap, 0) + 1
        
        # Find primary issue (most frequent gap)
        primary_issue = None
        max_count = 0
        for gap, count in gap_counts.items():
            if count > max_count:
                max_count = count
                primary_issue = gap
        
        return {
            "total_moves": total,
            "critical_moves": critical,
            "critical_percentage": round(critical / total * 100, 1) if total > 0 else 0,
            "reason_breakdown": reason_counts,
            "gap_breakdown": gap_counts,
            "primary_issue": primary_issue,
            "primary_issue_count": max_count
        }


def interpret_game_analysis(
    move_evaluations: List[Dict],
    user_color: str = "white",
    db=None
) -> Tuple[List[Dict], Dict]:
    """
    Convenience function to interpret a full game analysis.
    
    Args:
        move_evaluations: Raw moves from Stockfish
        user_color: Player's color
        db: Optional database connection
        
    Returns:
        (enriched_moves, summary)
    """
    from position_context_service import enrich_moves_with_context
    
    interpreter = AnalysisInterpreter(db)
    interpreted = interpreter.interpret_moves(move_evaluations, user_color)
    summary = interpreter.get_interpretation_summary(interpreted)
    
    # Convert back to dict format for storage
    enriched_moves = []
    for i, m in enumerate(interpreted):
        # Get original move data for fields we don't have in InterpretedMove
        orig = move_evaluations[i] if i < len(move_evaluations) else {}
        
        enriched = {
            "move_number": m.move_number,
            "move": orig.get("move", ""),
            "move_uci": m.move_uci,
            "fen_before": m.fen_before,
            "fen_after": m.fen_after,
            "cp_loss": m.cp_loss,
            "eval_before": orig.get("eval_before", 0),
            "eval_after": orig.get("eval_after", 0),
            "eval_swing": m.eval_swing,
            "is_turning_point": m.is_turning_point,
            "evaluation": m.evaluation,
            "cognitive_gap": m.cognitive_gap,
            "is_critical": m.is_critical,
            "critical_reason": m.critical_reason,
            "gap_confidence": m.gap_confidence,
            "gap_evidence": m.gap_evidence,
            "coaching_focus": m.coaching_focus,
            # Visual-shape detections — orthogonal to cognitive_gap.
            "shapes": m.shapes,
            # Preserve original fields
            "best_move": orig.get("best_move"),
            "best_move_uci": orig.get("best_move_uci"),
            "is_best": orig.get("is_best", False),
            "mate_info": orig.get("mate_info"),
            "pv_after_played": orig.get("pv_after_played", []),
            "pv_after_best": orig.get("pv_after_best", []),
            "threat": orig.get("threat")
        }
        enriched_moves.append(enriched)
    
    # Add position context to all moves
    enriched_moves = enrich_moves_with_context(enriched_moves, user_color)
    
    return enriched_moves, summary
