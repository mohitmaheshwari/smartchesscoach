"""
Meta-Pattern Composition Engine
================================

This module does NOT do chess detection. It composes existing detection
signals (from mistake_classifier, cognitive_gap_service, live_behavior_extractor,
chess_brain/detector_registry) into higher-order "meta-patterns" — the kind
of things a human coach would notice.

Key principle:
  - Chess inference is 100% deterministic (this file + the detectors it reads)
  - LLM is ONLY allowed to write commentary (the 2-sentence message + memorable rule)
  - LLM output is validated — any chess notation in it must come from verified evidence

25 composition rules, grouped:
  Time & tempo (5)
  Sacrifice & tactics (5)
  Positional / strategic (4)
  Opening knowledge (3)
  Psychology (4)
  Conversion / endgame (2)
  Ignored resources (2)

Each rule is a pure function: MetaContext → Optional[MetaPatternMatch].
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import chess

logger = logging.getLogger(__name__)


# ─── DATA TYPES ───────────────────────────────────────────────────────


@dataclass
class MetaContext:
    """
    All signals a composition rule needs. Populated ONCE per move, by
    reading existing detectors. Rules are pure functions of this context.
    """
    # Position
    fen_before: str
    fen_after: str = ""

    # Moves
    user_move: str = ""
    best_move: Optional[str] = None
    move_history: List[str] = field(default_factory=list)  # SAN list, full game
    move_number: int = 1

    # Evaluations (user's perspective, in pawns)
    eval_before: float = 0.0
    eval_after: float = 0.0

    # Time
    time_spent: float = 0.0      # seconds on this move
    time_remaining: float = 999  # seconds left on clock
    avg_time_per_move: float = 0.0

    # User
    user_color: str = "white"    # "white"/"black"
    user_rating: int = 1200

    # Phase
    game_phase: str = "middlegame"  # "opening"/"middlegame"/"endgame"

    # Signals from existing detectors
    is_impulse_move: bool = False     # time_spent < 2s
    is_time_pressure: bool = False    # time_remaining < 60s
    is_sacrifice: bool = False        # material sacrificed this move
    is_calculated_sacrifice: bool = False  # sac but not a blunder (opponent is worse)
    threat_ignored: bool = False      # opponent had a threat user didn't address
    threat_descriptions: List[str] = field(default_factory=list)

    # Classified mistake
    mistake_type: Optional[str] = None   # From mistake_classifier.MistakeType
    cognitive_gap: Optional[str] = None  # From cognitive_gap_service.CognitiveGap

    # Walked-into patterns (specific flags from mistake_classifier)
    walked_into_fork: bool = False
    walked_into_pin: bool = False
    walked_into_skewer: bool = False
    walked_into_discovered: bool = False

    # Game context (this game)
    consecutive_blunders: int = 0    # streak ending on this move
    blunders_this_game: int = 0
    user_move_evaluations: List[Dict] = field(default_factory=list)  # all user move evals so far

    # Opening context
    opening_name: Optional[str] = None
    opening_key: Optional[str] = None
    is_theory_move: bool = False     # matches known theory
    opening_accuracy: Optional[float] = None  # % accuracy in this opening historically

    # Endgame context
    endgame_type: Optional[str] = None

    # Cross-game (from coach memory)
    persistent_weaknesses: List[Dict] = field(default_factory=list)
    recent_same_mistake_count: int = 0  # same mistake_type in last 5 games

    @property
    def cp_loss(self) -> int:
        """Centipawn loss from user's perspective (positive = user worse)."""
        return int((self.eval_before - self.eval_after) * 100)

    @property
    def was_winning(self) -> bool:
        return self.eval_before > 1.5

    @property
    def was_losing(self) -> bool:
        return self.eval_before < -1.5


@dataclass
class MetaPatternMatch:
    """A matched meta-pattern with evidence for the LLM."""
    pattern_id: str
    priority: int = 5              # 1-10, higher = shown first
    evidence: Dict = field(default_factory=dict)
    fallback_rule: str = ""        # Used if LLM fails validation
    fallback_message: str = ""     # Full fallback message


# ─── COMPOSITION RULES (25 total) ─────────────────────────────────────


# ─── Group 1: Time & tempo (5) ────────────────────────────────────────


def rule_time_pressure_blunder(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Blundered with <60s on the clock."""
    if ctx.is_time_pressure and ctx.cp_loss >= 150:
        return MetaPatternMatch(
            pattern_id="time_pressure_blunder",
            priority=9,
            evidence={
                "time_remaining": round(ctx.time_remaining, 1),
                "cp_loss": ctx.cp_loss,
                "user_move": ctx.user_move,
                "best_move": ctx.best_move,
            },
            fallback_rule="Don't trust your instincts in time trouble — trust your checks.",
            fallback_message=f"Time pressure got you. {ctx.user_move} cost you — the right move was {ctx.best_move}. When your clock gets low, do a 5-second scan: checks, captures, threats.",
        )
    return None


def rule_rushed_without_threat_check(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Moved in <2s AND missed opponent's threat."""
    if ctx.is_impulse_move and ctx.threat_ignored and ctx.cp_loss >= 100:
        return MetaPatternMatch(
            pattern_id="rushed_without_threat_check",
            priority=8,
            evidence={
                "time_spent": round(ctx.time_spent, 1),
                "cp_loss": ctx.cp_loss,
                "threats": ctx.threat_descriptions[:2],
                "user_move": ctx.user_move,
            },
            fallback_rule="Before every move, ask: what is opponent threatening?",
            fallback_message=f"You played {ctx.user_move} in {ctx.time_spent:.1f} seconds. Opponent was threatening something — and you didn't see it. Never move without checking.",
        )
    return None


def rule_rushed_streak_collapse(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Third+ fast move in a row, and blundered."""
    # Count last 3 user moves for rapid streak
    recent = ctx.user_move_evaluations[-3:]
    fast_streak = sum(1 for m in recent if (m.get("time_spent", 99) or 99) < 5)
    if fast_streak >= 3 and ctx.cp_loss >= 100:
        return MetaPatternMatch(
            pattern_id="rushed_streak_collapse",
            priority=7,
            evidence={
                "fast_moves_in_row": fast_streak,
                "cp_loss": ctx.cp_loss,
                "user_move": ctx.user_move,
            },
            fallback_rule="When you feel fast, slow down. Momentum is not a plan.",
            fallback_message=f"Three quick moves in a row, then {ctx.user_move} — a mistake. Speed became your enemy.",
        )
    return None


def rule_slow_but_wrong(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Spent >30s on this move and still got it wrong badly."""
    if ctx.time_spent > 30 and ctx.cp_loss >= 200:
        return MetaPatternMatch(
            pattern_id="slow_but_wrong",
            priority=6,
            evidence={
                "time_spent": round(ctx.time_spent, 1),
                "cp_loss": ctx.cp_loss,
                "user_move": ctx.user_move,
                "best_move": ctx.best_move,
            },
            fallback_rule="Long think, wrong idea. Next time, pick a candidate move first, then verify — don't drift.",
            fallback_message=f"You spent {ctx.time_spent:.0f} seconds and still played {ctx.user_move}. Long thinks on wrong plans burn time AND advantage.",
        )
    return None


def rule_unequal_clock_usage(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Clock dropped fast from opening overthinking — now in time trouble later."""
    # Signal: we're in time pressure, game phase is endgame/late middlegame,
    # and early moves were slow
    if not (ctx.is_time_pressure and ctx.game_phase != "opening" and len(ctx.user_move_evaluations) > 15):
        return None
    early_times = [m.get("time_spent", 0) or 0 for m in ctx.user_move_evaluations[:10]]
    late_times = [m.get("time_spent", 0) or 0 for m in ctx.user_move_evaluations[-10:]]
    avg_early = sum(early_times) / max(1, len(early_times))
    avg_late = sum(late_times) / max(1, len(late_times))
    if avg_early > avg_late * 2 and avg_early > 20:
        return MetaPatternMatch(
            pattern_id="unequal_clock_usage",
            priority=5,
            evidence={
                "avg_early_time": round(avg_early, 1),
                "avg_late_time": round(avg_late, 1),
                "time_remaining": round(ctx.time_remaining, 1),
            },
            fallback_rule="Distribute your clock. Don't spend half your time on the first 10 moves.",
            fallback_message=f"You averaged {avg_early:.0f}s early and only {avg_late:.0f}s now. Save thinking for when it matters.",
        )
    return None


# ─── Group 2: Sacrifice & tactics (5) ─────────────────────────────────


def rule_ran_from_sacrifice(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """
    Opponent sacrificed, user was in check from follow-up, user retreated king
    instead of counterattacking. Best move was a defensive counter.
    """
    # Need at least 2 moves of history to detect opp sac + follow-up
    if len(ctx.move_history) < 3 or not ctx.best_move or not ctx.user_move:
        return None

    try:
        board = chess.Board(ctx.fen_before)
        if not board.is_check():
            return None  # Must be in check when this move was made

        # Was the user's move a king move (retreat)?
        user_mv = board.parse_san(ctx.user_move)
        user_piece = board.piece_at(user_mv.from_square)
        if not user_piece or user_piece.piece_type != chess.KING:
            return None

        # Was the best move a non-king move (counter)?
        best_mv = board.parse_san(ctx.best_move)
        best_piece = board.piece_at(best_mv.from_square)
        if not best_piece or best_piece.piece_type == chess.KING:
            return None

        # Did opponent sacrifice in the recent past? Check material balance shift.
        # Look 2 plies back — if opp played a capture that "looked" like a sac
        # (captured pawn, lost a piece). This is a rough check.
        if len(ctx.move_history) < 2:
            return None
        # Simplest heuristic: user already has a material advantage
        # (means opp gave up material, user accepted)
        own_color = board.turn  # It's user's turn when in check
        user_material = _count_material(board, own_color)
        opp_material = _count_material(board, not own_color)
        if user_material - opp_material < 2:
            return None  # Not clearly up material

        # Match!
        return MetaPatternMatch(
            pattern_id="ran_from_sacrifice",
            priority=10,
            evidence={
                "user_move": ctx.user_move,
                "best_move": ctx.best_move,
                "material_advantage": user_material - opp_material,
                "was_in_check": True,
            },
            fallback_rule="When you take a sacrifice, don't run — counterattack.",
            fallback_message=f"You took the sacrifice (you're up material!), then ran with {ctx.user_move}. The right move was {ctx.best_move} — block the check AND hit back. When attacked, ask: can I defend AND attack at once?",
        )
    except Exception:
        return None


def rule_grabbed_poisoned_material(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """User captured something, eval dropped by 1+ pawn — the capture was bad."""
    if not ctx.user_move or ctx.cp_loss < 100:
        return None
    try:
        board = chess.Board(ctx.fen_before)
        mv = board.parse_san(ctx.user_move)
        if not board.is_capture(mv):
            return None
        captured = board.piece_at(mv.to_square)
        mover = board.piece_at(mv.from_square)
        if not captured or not mover:
            return None
        return MetaPatternMatch(
            pattern_id="grabbed_poisoned_material",
            priority=9,
            evidence={
                "user_move": ctx.user_move,
                "captured_piece": chess.piece_name(captured.piece_type),
                "mover_piece": chess.piece_name(mover.piece_type),
                "cp_loss": ctx.cp_loss,
                "best_move": ctx.best_move,
            },
            fallback_rule="Before taking, ask: why did my opponent leave this?",
            fallback_message=f"{ctx.user_move} looked free. It wasn't — you lost {ctx.cp_loss}cp. If a piece looks offered, it's probably poisoned.",
        )
    except Exception:
        return None


def rule_panic_sacrifice(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """User sacrificed material but it wasn't a calculated sac — just a blunder."""
    if not ctx.is_sacrifice:
        return None
    if ctx.is_calculated_sacrifice:
        return None  # It was actually sound
    if ctx.cp_loss < 200:
        return None
    return MetaPatternMatch(
        pattern_id="panic_sacrifice",
        priority=8,
        evidence={
            "user_move": ctx.user_move,
            "cp_loss": ctx.cp_loss,
            "best_move": ctx.best_move,
        },
        fallback_rule="Don't sacrifice out of fear. Sacrifices need a concrete follow-up.",
        fallback_message=f"{ctx.user_move} gave up material without a plan. Sacrifice only when you can SEE the win.",
    )


def rule_missed_counterattack(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Best move attacked something, user played defensive/quiet instead."""
    if not ctx.best_move or not ctx.user_move or ctx.cp_loss < 100:
        return None
    try:
        board = chess.Board(ctx.fen_before)
        best_mv = board.parse_san(ctx.best_move)
        user_mv = board.parse_san(ctx.user_move)

        # Did best move attack something valuable?
        best_is_aggressive = board.is_capture(best_mv) or board.gives_check(best_mv)
        if not best_is_aggressive:
            # Check if best move attacks a piece from its destination
            board.push(best_mv)
            attacks_something_valuable = False
            for sq in board.attacks(best_mv.to_square):
                p = board.piece_at(sq)
                if p and p.color == board.turn:
                    attacks_something_valuable = True
                    break
            board.pop()
            if not attacks_something_valuable:
                return None

        # Was user's move quiet (not a capture, not a check)?
        user_quiet = not board.is_capture(user_mv) and not board.gives_check(user_mv)
        if not user_quiet:
            return None

        return MetaPatternMatch(
            pattern_id="missed_counterattack",
            priority=7,
            evidence={
                "user_move": ctx.user_move,
                "best_move": ctx.best_move,
                "cp_loss": ctx.cp_loss,
            },
            fallback_rule="Attack is defense. When they threaten you, look for your own threat.",
            fallback_message=f"You played safe with {ctx.user_move}. {ctx.best_move} was the counter-punch. Best defense is offense.",
        )
    except Exception:
        return None


def rule_walked_into_known_tactic(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """User walked into a fork/pin/skewer/discovered attack."""
    tactic = None
    if ctx.walked_into_fork:
        tactic = "fork"
    elif ctx.walked_into_pin:
        tactic = "pin"
    elif ctx.walked_into_skewer:
        tactic = "skewer"
    elif ctx.walked_into_discovered:
        tactic = "discovered attack"
    if not tactic:
        return None
    return MetaPatternMatch(
        pattern_id="walked_into_known_tactic",
        priority=9,
        evidence={
            "tactic": tactic,
            "user_move": ctx.user_move,
            "cp_loss": ctx.cp_loss,
        },
        fallback_rule="Before you move, imagine your opponent's reply. Every single move.",
        fallback_message=f"{ctx.user_move} walked right into a {tactic}. Always ask: what's my opponent's best response to this?",
    )


# ─── Group 3: Positional / strategic (4) ─────────────────────────────


def rule_retreated_developed_piece(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Moved a developed knight/bishop backward without any threat to it."""
    if not ctx.user_move:
        return None
    try:
        board = chess.Board(ctx.fen_before)
        mv = board.parse_san(ctx.user_move)
        piece = board.piece_at(mv.from_square)
        if not piece or piece.piece_type not in (chess.KNIGHT, chess.BISHOP):
            return None

        # Check if the moved piece was attacked (legitimate retreat)
        if board.is_attacked_by(not piece.color, mv.from_square):
            # If attacked by lower-value piece, might be forced retreat — still a retreat
            attackers = list(board.attackers(not piece.color, mv.from_square))
            if attackers:
                # Check if any attacker is weaker than the piece
                piece_val = _piece_value(piece.piece_type)
                for a in attackers:
                    a_p = board.piece_at(a)
                    if a_p and _piece_value(a_p.piece_type) < piece_val:
                        return None  # Forced retreat by pawn etc, not meta-pattern

        # Check if move is backward (toward own back rank)
        own_back_rank = 0 if piece.color == chess.WHITE else 7
        from_rank = chess.square_rank(mv.from_square)
        to_rank = chess.square_rank(mv.to_square)
        went_backward = (
            (piece.color == chess.WHITE and to_rank < from_rank)
            or (piece.color == chess.BLACK and to_rank > from_rank)
        )
        if not went_backward:
            return None

        # Only meaningful if piece was off back rank (developed)
        if from_rank == own_back_rank:
            return None

        return MetaPatternMatch(
            pattern_id="retreated_developed_piece",
            priority=5,
            evidence={
                "user_move": ctx.user_move,
                "piece": chess.piece_name(piece.piece_type),
                "from_sq": chess.square_name(mv.from_square),
                "to_sq": chess.square_name(mv.to_square),
            },
            fallback_rule="Pieces go forward, not back.",
            fallback_message=f"{ctx.user_move} — you retreated your {chess.piece_name(piece.piece_type)} when nothing was attacking it. Developed pieces fight; they don't hide.",
        )
    except Exception:
        return None


def rule_traded_while_attacking(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Initiated a trade (capture) during own attack, losing initiative."""
    if not ctx.user_move or ctx.cp_loss < 80:
        return None
    try:
        board = chess.Board(ctx.fen_before)
        mv = board.parse_san(ctx.user_move)
        if not board.is_capture(mv):
            return None

        # User was "attacking" if they had eval advantage
        if ctx.eval_before < 0.5:
            return None

        # The capture is an equal trade (same piece type or close)
        captured = board.piece_at(mv.to_square)
        mover = board.piece_at(mv.from_square)
        if not captured or not mover:
            return None
        if _piece_value(captured.piece_type) < _piece_value(mover.piece_type):
            return None  # Lost material, not a "trade"
        if abs(_piece_value(captured.piece_type) - _piece_value(mover.piece_type)) > 1:
            return None  # Big material swing, not a "trade"

        return MetaPatternMatch(
            pattern_id="traded_while_attacking",
            priority=6,
            evidence={
                "user_move": ctx.user_move,
                "captured_piece": chess.piece_name(captured.piece_type),
                "mover_piece": chess.piece_name(mover.piece_type),
                "eval_before": round(ctx.eval_before, 1),
                "cp_loss": ctx.cp_loss,
            },
            fallback_rule="When attacking, don't trade pieces. Fewer pieces = weaker attack.",
            fallback_message=f"{ctx.user_move} traded off your attacker. You were winning — keep your pieces on the board when you have the initiative.",
        )
    except Exception:
        return None


def rule_king_stuck_in_center(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Move 10+, king still on original square or nearby, didn't castle."""
    if ctx.move_number < 10 or ctx.move_number > 25:
        return None
    try:
        board = chess.Board(ctx.fen_before)
        uc = chess.WHITE if ctx.user_color == "white" else chess.BLACK
        king_sq = board.king(uc)
        if king_sq is None:
            return None
        # Check if king still on starting square area (e1/e8 or d1/d8)
        back_rank = 0 if uc == chess.WHITE else 7
        king_rank = chess.square_rank(king_sq)
        king_file = chess.square_file(king_sq)
        if king_rank != back_rank:
            return None  # King already moved (castled or otherwise)
        if king_file in (6, 2):
            return None  # Castled already (g/c file)
        if king_file not in (3, 4):
            return None  # Not in center
        # Check: castling rights exist?
        has_castling = board.has_castling_rights(uc)
        if not has_castling:
            return None

        return MetaPatternMatch(
            pattern_id="king_stuck_in_center",
            priority=7,
            evidence={
                "move_number": ctx.move_number,
                "king_square": chess.square_name(king_sq),
                "castling_available": has_castling,
            },
            fallback_rule="Castle before attacking. A safe king lets you play freely.",
            fallback_message=f"Move {ctx.move_number}, your king is still in the center. Castle now — every move of delay is a gift to your opponent.",
        )
    except Exception:
        return None


def rule_hasty_pawn_push(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Pushed a flank pawn (a/b/g/h) in opening/early middlegame without clear purpose."""
    if ctx.move_number > 20 or ctx.move_number < 3:
        return None
    if not ctx.user_move or ctx.cp_loss < 50:
        return None
    try:
        board = chess.Board(ctx.fen_before)
        mv = board.parse_san(ctx.user_move)
        piece = board.piece_at(mv.from_square)
        if not piece or piece.piece_type != chess.PAWN:
            return None
        # Flank file = a/b/g/h (file 0, 1, 6, 7)
        file = chess.square_file(mv.from_square)
        if file not in (0, 1, 6, 7):
            return None
        # Not a capture (captures are usually purposeful)
        if board.is_capture(mv):
            return None

        return MetaPatternMatch(
            pattern_id="hasty_pawn_push",
            priority=4,
            evidence={
                "user_move": ctx.user_move,
                "move_number": ctx.move_number,
                "cp_loss": ctx.cp_loss,
            },
            fallback_rule="Don't drift. Focus on the center.",
            fallback_message=f"{ctx.user_move} pushes a flank pawn with no clear plan. Early moves should develop or fight for the center.",
        )
    except Exception:
        return None


# ─── Group 4: Opening knowledge (3) ──────────────────────────────────


def rule_opening_knowledge_gap(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Low accuracy in known opening, historically weak there."""
    if ctx.game_phase != "opening":
        return None
    if not ctx.opening_name:
        return None
    if ctx.opening_accuracy is None or ctx.opening_accuracy >= 70:
        return None
    if ctx.cp_loss < 50:
        return None
    return MetaPatternMatch(
        pattern_id="opening_knowledge_gap",
        priority=6,
        evidence={
            "opening_name": ctx.opening_name,
            "historical_accuracy": round(ctx.opening_accuracy, 1),
            "user_move": ctx.user_move,
            "best_move": ctx.best_move,
            "move_number": ctx.move_number,
        },
        fallback_rule="When you don't know the opening, control the center and develop.",
        fallback_message=f"You struggle in the {ctx.opening_name} ({ctx.opening_accuracy:.0f}% accuracy across your games). Let's study its ideas, not just the moves.",
    )


def rule_opening_deviation(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Left known theory with a cp_loss — went off-book into a worse position."""
    if ctx.move_number > 15 or ctx.game_phase != "opening":
        return None
    if ctx.is_theory_move:
        return None  # Stayed on theory, no deviation
    if ctx.cp_loss < 75:
        return None
    if not ctx.opening_name:
        return None
    return MetaPatternMatch(
        pattern_id="opening_deviation",
        priority=6,
        evidence={
            "opening_name": ctx.opening_name,
            "user_move": ctx.user_move,
            "best_move": ctx.best_move,
            "move_number": ctx.move_number,
            "cp_loss": ctx.cp_loss,
        },
        fallback_rule="If you leave the main line, leave it for a reason.",
        fallback_message=f"Move {ctx.move_number} in the {ctx.opening_name} — you deviated from theory with {ctx.user_move}. {ctx.best_move} was the main line.",
    )


def rule_moved_same_piece_twice_opening(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """In first 10 moves, moved same piece 2+ times while others sit on back rank."""
    if ctx.move_number > 12 or len(ctx.move_history) < 2:
        return None
    if not ctx.user_move:
        return None
    try:
        # Rebuild the position from move_history and check what piece moved
        board = chess.Board(ctx.fen_before)
        mv = board.parse_san(ctx.user_move)
        to_sq = mv.to_square

        # Check if this destination or origin was used by a prior user move
        own_moves = ctx.move_history[::2] if ctx.user_color == "white" else ctx.move_history[1::2]
        own_moves = own_moves[:-1]  # Exclude the current move
        if len(own_moves) < 1:
            return None

        # Simple heuristic: same square appears as destination in prior moves
        # (we'd need to replay to be exact, but matching is good enough for a hint)
        piece_str = ctx.user_move[0] if ctx.user_move[0].isupper() else "P"
        same_piece_moves = sum(
            1 for m in own_moves
            if m and (m[0] == piece_str if piece_str != "P" else (m[0].islower() and not m[0] in "abcdefgh") or m[0] in "abcdefgh")
        )
        if same_piece_moves < 1:
            return None

        # Check how many pieces are still on back rank (undeveloped minors)
        uc = chess.WHITE if ctx.user_color == "white" else chess.BLACK
        back_rank = 0 if uc == chess.WHITE else 7
        undeveloped = 0
        for sq in chess.SQUARES:
            p = board.piece_at(sq)
            if not p or p.color != uc:
                continue
            if p.piece_type in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(sq) == back_rank:
                undeveloped += 1
        if undeveloped < 2:
            return None

        return MetaPatternMatch(
            pattern_id="moved_same_piece_twice_opening",
            priority=6,
            evidence={
                "user_move": ctx.user_move,
                "move_number": ctx.move_number,
                "undeveloped_pieces": undeveloped,
            },
            fallback_rule="Each move, a new piece.",
            fallback_message=f"{ctx.user_move} — you're moving the same piece again with {undeveloped} minor pieces still at home. Bring out a fresh piece.",
        )
    except Exception:
        return None


# ─── Group 5: Psychology (4) ──────────────────────────────────────────


def rule_overconfidence_collapse(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Was winning (eval > +2), now not winning, cp_loss >= 150."""
    if ctx.eval_before < 2.0:
        return None
    if ctx.eval_after >= 1.5:
        return None  # Still winning
    if ctx.cp_loss < 150:
        return None
    return MetaPatternMatch(
        pattern_id="overconfidence_collapse",
        priority=10,
        evidence={
            "eval_before": round(ctx.eval_before, 1),
            "eval_after": round(ctx.eval_after, 1),
            "user_move": ctx.user_move,
            "best_move": ctx.best_move,
            "cp_loss": ctx.cp_loss,
        },
        fallback_rule="Winning positions demand MORE focus, not less. Finish the job.",
        fallback_message=f"You went from +{ctx.eval_before:.1f} to +{ctx.eval_after:.1f} with {ctx.user_move}. Being ahead is when the hardest moves appear — the easy ones are over.",
    )


def rule_tilt_cascade(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Multiple blunders after a first blunder — emotional spiral."""
    if ctx.consecutive_blunders < 2:
        return None
    return MetaPatternMatch(
        pattern_id="tilt_cascade",
        priority=9,
        evidence={
            "consecutive_blunders": ctx.consecutive_blunders,
            "blunders_this_game": ctx.blunders_this_game,
            "user_move": ctx.user_move,
        },
        fallback_rule="One blunder is a move. Three is emotion. Pause.",
        fallback_message=f"{ctx.consecutive_blunders} blunders in a row — you're on tilt. Close your eyes, breathe. Don't play the next move until you've calmed down.",
    )


def rule_post_blunder_spiral(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Blundered, then blundered again within 5 moves."""
    if ctx.consecutive_blunders != 0 and ctx.cp_loss < 200:
        return None
    # Look at last 10 user move evaluations for a prior blunder
    if len(ctx.user_move_evaluations) < 2:
        return None
    recent = ctx.user_move_evaluations[-6:-1]  # Last 5 moves before this one
    prior_blunder_move = None
    for m in recent:
        if (m.get("cp_loss", 0) or 0) >= 200:
            prior_blunder_move = m.get("move_number")
            break
    if not prior_blunder_move:
        return None
    if ctx.cp_loss < 200:
        return None
    return MetaPatternMatch(
        pattern_id="post_blunder_spiral",
        priority=8,
        evidence={
            "prior_blunder_move": prior_blunder_move,
            "current_move": ctx.move_number,
            "moves_between": ctx.move_number - prior_blunder_move,
            "user_move": ctx.user_move,
        },
        fallback_rule="After a blunder, the position isn't lost — your focus is. Reset before you move.",
        fallback_message=f"You blundered on move {prior_blunder_move}, and now another on move {ctx.move_number}. One mistake doesn't lose a game — the second one usually does.",
    )


def rule_confidence_illusion(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Same mistake repeating across multiple games (3+ in last 5)."""
    if ctx.recent_same_mistake_count < 3:
        return None
    if not ctx.mistake_type:
        return None
    return MetaPatternMatch(
        pattern_id="confidence_illusion",
        priority=8,
        evidence={
            "mistake_type": ctx.mistake_type,
            "occurrences_recent_games": ctx.recent_same_mistake_count,
            "user_move": ctx.user_move,
        },
        fallback_rule="Same mistake, same lesson. Until you fix it, it stays.",
        fallback_message=f"This is the {ctx.recent_same_mistake_count}rd time in your last 5 games — {ctx.mistake_type.replace('_', ' ')}. Recognition is the first step. Now, the fix.",
    )


# ─── Group 6: Conversion / endgame (2) ───────────────────────────────


def rule_failed_endgame_conversion(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """In identified endgame, was winning, lost advantage."""
    if ctx.game_phase != "endgame" or not ctx.endgame_type:
        return None
    if ctx.eval_before < 1.5 or ctx.cp_loss < 100:
        return None
    return MetaPatternMatch(
        pattern_id="failed_endgame_conversion",
        priority=9,
        evidence={
            "endgame_type": ctx.endgame_type,
            "eval_before": round(ctx.eval_before, 1),
            "eval_after": round(ctx.eval_after, 1),
            "user_move": ctx.user_move,
            "best_move": ctx.best_move,
        },
        fallback_rule="Endgames are won by technique, not by hope.",
        fallback_message=f"You had a winning {ctx.endgame_type.replace('_', ' ')} endgame and let it slip. Let's practice this technique until conversion is automatic.",
    )


def rule_stalemate_trap(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Drew when ahead by major material — likely stalemated opponent."""
    if ctx.eval_after != 0.0 or ctx.eval_before < 5.0:
        return None
    # Near-zero eval after huge advantage — stalemate
    try:
        board = chess.Board(ctx.fen_after)
        if board.is_stalemate():
            return MetaPatternMatch(
                pattern_id="stalemate_trap",
                priority=10,
                evidence={
                    "eval_before": round(ctx.eval_before, 1),
                    "user_move": ctx.user_move,
                },
                fallback_rule="In a winning endgame, always leave the enemy king ONE square.",
                fallback_message=f"Stalemate! You were winning by {ctx.eval_before:.0f} pawns and {ctx.user_move} gave the enemy king no squares. Always check: can my opponent move?",
            )
    except Exception:
        pass
    return None


# ─── Group 7: Ignored resources (2) ──────────────────────────────────


def rule_ignored_opponent_threat(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Opponent had a concrete threat, user didn't address it, cp_loss >= 100."""
    if not ctx.threat_ignored or ctx.cp_loss < 100:
        return None
    return MetaPatternMatch(
        pattern_id="ignored_opponent_threat",
        priority=8,
        evidence={
            "threats": ctx.threat_descriptions[:2],
            "user_move": ctx.user_move,
            "best_move": ctx.best_move,
            "cp_loss": ctx.cp_loss,
        },
        fallback_rule="Every move, ask: what is opponent threatening?",
        fallback_message=f"You played {ctx.user_move} while opponent was preparing a real threat. Before every move, look at THEIR pieces: what are they about to do?",
    )


def rule_missed_defensive_resource(ctx: MetaContext) -> Optional[MetaPatternMatch]:
    """Best move was a defensive move, user played something else (likely attack)."""
    if not ctx.best_move or not ctx.user_move or ctx.cp_loss < 100:
        return None
    try:
        board = chess.Board(ctx.fen_before)
        best_mv = board.parse_san(ctx.best_move)
        # Check if best move defends a threatened piece or blocks a threat
        # Heuristic: best move's destination covers a friendly piece under attack
        own_color = board.turn
        threatened_pieces = []
        for sq in chess.SQUARES:
            p = board.piece_at(sq)
            if not p or p.color != own_color:
                continue
            if p.piece_type == chess.PAWN or p.piece_type == chess.KING:
                continue
            if board.is_attacked_by(not own_color, sq):
                threatened_pieces.append(sq)
        if not threatened_pieces:
            return None
        # Does best move land on a square that defends a threatened piece?
        best_defends = False
        board.push(best_mv)
        for sq in threatened_pieces:
            if board.is_attacked_by(own_color, sq):
                # Wasn't defended before? (count attackers/defenders)
                best_defends = True
                break
        board.pop()
        if not best_defends:
            return None

        return MetaPatternMatch(
            pattern_id="missed_defensive_resource",
            priority=7,
            evidence={
                "user_move": ctx.user_move,
                "best_move": ctx.best_move,
                "threatened_count": len(threatened_pieces),
                "cp_loss": ctx.cp_loss,
            },
            fallback_rule="Defense first, attack second.",
            fallback_message=f"{ctx.best_move} would have saved your piece. You played {ctx.user_move} instead — attacking without defending first rarely works.",
        )
    except Exception:
        return None


# ─── REGISTRY ────────────────────────────────────────────────────────


META_RULES: List[Callable[[MetaContext], Optional[MetaPatternMatch]]] = [
    # Time & tempo
    rule_time_pressure_blunder,
    rule_rushed_without_threat_check,
    rule_rushed_streak_collapse,
    rule_slow_but_wrong,
    rule_unequal_clock_usage,
    # Sacrifice & tactics
    rule_ran_from_sacrifice,
    rule_grabbed_poisoned_material,
    rule_panic_sacrifice,
    rule_missed_counterattack,
    rule_walked_into_known_tactic,
    # Positional
    rule_retreated_developed_piece,
    rule_traded_while_attacking,
    rule_king_stuck_in_center,
    rule_hasty_pawn_push,
    # Opening knowledge
    rule_opening_knowledge_gap,
    rule_opening_deviation,
    rule_moved_same_piece_twice_opening,
    # Psychology
    rule_overconfidence_collapse,
    rule_tilt_cascade,
    rule_post_blunder_spiral,
    rule_confidence_illusion,
    # Conversion
    rule_failed_endgame_conversion,
    rule_stalemate_trap,
    # Ignored resources
    rule_ignored_opponent_threat,
    rule_missed_defensive_resource,
]

assert len(META_RULES) == 25, f"Expected 25 meta-rules, got {len(META_RULES)}"


def detect_meta_patterns(ctx: MetaContext) -> List[MetaPatternMatch]:
    """
    Run all 25 composition rules over the context. Return matches sorted by
    priority (descending). Caller typically takes the top 1 for coaching.
    """
    matches = []
    for rule in META_RULES:
        try:
            m = rule(ctx)
            if m is not None:
                matches.append(m)
        except Exception as e:
            logger.debug(f"[META] Rule {rule.__name__} failed: {e}")
    matches.sort(key=lambda m: m.priority, reverse=True)
    return matches


# ─── COMMENTARY (LLM wrapper with strict validation) ────────────────


_LLM_PROMPT = """You are a warm Indian chess coach who writes short, memorable feedback.

A detection system has identified this pattern in a game:

Pattern: {pattern_id}
Evidence (VERIFIED FACTS — do not invent others):
{evidence_json}
Student rating: {rating}

Write JSON with two fields:
- "message": 2 sentences max, warm coach voice. You may reference the evidence.
  If you mention any chess move (e.g. "Bxf7"), it MUST appear in the evidence.
- "rule": 6-10 word memorable principle the student can repeat during games.

Do not invent chess moves, squares, pieces, or evaluations not in the evidence.
If you're unsure, say less. Short > clever.

Return ONLY valid JSON, no prose, no markdown."""


def _extract_chess_notation(text: str) -> List[str]:
    """Extract chess move notation (simple heuristic) from text."""
    # Matches things like Nf3, Bxf7, O-O, e4, Qh5+, Ne8#
    pattern = r"\b([KQRBN][a-h]?[1-8]?x?[a-h][1-8][+#]?|O-O(?:-O)?|[a-h]x?[a-h][1-8](?:=[QRBN])?[+#]?|[a-h][1-8])\b"
    return re.findall(pattern, text)


def _validate_llm_output(text: str, evidence: Dict) -> Optional[Dict[str, str]]:
    """
    Parse + validate LLM output. Rejects:
    - Invalid JSON
    - Missing fields
    - Chess notation not present in evidence
    - Excessive length
    """
    import json
    try:
        # Strip markdown if present
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
    except Exception:
        return None

    msg = data.get("message", "").strip()
    rule = data.get("rule", "").strip()
    if not msg or not rule:
        return None
    if len(msg) > 300:
        return None
    if len(rule) > 80:
        return None

    # Verify all chess notation in output is in evidence
    evidence_str = " ".join(str(v) for v in evidence.values())
    evidence_moves = set(_extract_chess_notation(evidence_str))
    for target in (msg, rule):
        for notation in _extract_chess_notation(target):
            if notation not in evidence_moves:
                logger.warning(f"[META] LLM mentioned {notation} not in evidence — rejecting")
                return None

    return {"message": msg, "rule": rule}


async def generate_commentary(
    pattern: MetaPatternMatch,
    rating: int,
    llm_call_fn: Optional[Callable] = None,
) -> Dict[str, str]:
    """
    Generate coach-style commentary for a matched pattern.

    Uses LLM if available (passed via llm_call_fn), otherwise falls back
    to the hardcoded rule/message on the pattern.

    LLM output is strictly validated — any chess notation must appear in
    the evidence, else we reject and use fallback.

    llm_call_fn signature: async (prompt: str) -> str (the LLM text response)
    """
    # Always have a working fallback
    fallback = {
        "message": pattern.fallback_message or pattern.fallback_rule,
        "rule": pattern.fallback_rule,
    }

    if llm_call_fn is None:
        return fallback

    try:
        import json
        prompt = _LLM_PROMPT.format(
            pattern_id=pattern.pattern_id,
            evidence_json=json.dumps(pattern.evidence, indent=2),
            rating=rating,
        )
        response_text = await llm_call_fn(prompt)
        validated = _validate_llm_output(response_text, pattern.evidence)
        if validated:
            return validated
        logger.info(f"[META] LLM output invalid for {pattern.pattern_id} — using fallback")
    except Exception as e:
        logger.warning(f"[META] LLM call failed for {pattern.pattern_id}: {e}")

    return fallback


# ─── SMALL HELPERS ───────────────────────────────────────────────────


_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def _piece_value(pt: int) -> int:
    return _PIECE_VALUES.get(pt, 0)


def _count_material(board: chess.Board, color: chess.Color) -> int:
    total = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.color == color and p.piece_type != chess.KING:
            total += _PIECE_VALUES.get(p.piece_type, 0)
    return total
