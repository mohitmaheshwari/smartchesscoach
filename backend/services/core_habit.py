"""core_habit.py — targeted-mistake DETECTION for the Universal Habit Coach.

LOGICALLY SEPARATE system (design constraint, Mohit 2026-06-09): this module answers ONLY
"did this move commit the habit's targeted mistake?" It knows nothing about focus, game_results,
graduation, or root-problem detection. Pure functions on a game analysis's move_evaluations.

The MEASUREMENT layer (services/focus_measurement.py) consumes this; it does not live here.
The ROOT-PROBLEM re-detection layer (services/root_behavior_engine.py) is unrelated to this.

Habit framing: Threat Scan is a CANDIDATE habit (best current hypothesis for the highest-leverage
universal habit at 600-1500), NOT proven truth. V1 proves the LOOP MECHANISM, not that this is THE habit.
"""
import chess

_VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
MIN_CP = 150        # only count significant mistakes (matches the L4 metric's cp_loss>=150 gate)
MIN_GAME_MOVES = 10  # a "real game" floor: abandoned coach stubs (2-3 moves) are NOT measured
                     # (they'd count clean trivially and inflate games_with_focus / clean_games)

# Targeted cognitive_gap families per habit.
# V1 = piece_safety ONLY, and that scope is deliberate + corpus-justified:
#   - `ignored_threat` (the "what is the opponent threatening?" half) is defined in the
#     classifier but effectively UNPOPULATED in the data — not measurable in V1.
#   - `king_safety` was audited (2026-06-09, n=1176): only 20% are concrete king threats
#     (threat-scan failures); 80% are AMBIENT positional king weakness ("king/pawn-shield",
#     "king under pressure pre-move") — a DIFFERENT coaching habit. Including it would silently
#     expand "did you hang something?" into "+ long-term king safety". EXCLUDED.
# So V1 measures the "anything hanging?" half only; we do NOT pretend to measure the threat half.
HABITS = {
    "threat_scan": {
        "label": "Threat Scan",
        "rule": "Before you move: is anything hanging?",  # V1 measures the hanging half only
        "gaps": {"piece_safety"},
        "candidate": True,  # not proven highest-leverage; see module docstring
    },
}


def _piece_safety_counts(move_eval) -> bool:
    """Audit pawn-fix: a piece_safety flag counts only if a real PIECE (>= minor) is left
    hanging — not an incidental pawn. Avoids the ~68% pawn over-fire the audit found.
    Falls back to trusting the label if the board can't be read."""
    fa = move_eval.get("fen_after")
    if not fa:
        return True
    try:
        b = chess.Board(fa)
    except Exception:
        return True
    user = not b.turn  # the side that just moved
    worst = 0
    for sq, p in b.piece_map().items():
        if (p.color == user and p.piece_type != chess.KING
                and b.attackers(b.turn, sq) and not b.attackers(user, sq)):
            worst = max(worst, _VAL[p.piece_type])
    return worst >= 3  # a minor piece or better hanging; bare pawn (worst==1) does not count


def is_targeted_mistake(move_eval, habit: str = "threat_scan") -> bool:
    """True iff this single user move committed the habit's targeted mistake."""
    if not isinstance(move_eval, dict) or move_eval.get("is_opponent_move"):
        return False
    if (move_eval.get("cp_loss", 0) or 0) < MIN_CP:
        return False
    cg = move_eval.get("cognitive_gap")
    if cg not in HABITS[habit]["gaps"]:
        return False
    if cg == "piece_safety":
        return _piece_safety_counts(move_eval)
    return True


def targeted_mistakes(move_evals, habit: str = "threat_scan") -> int:
    """Count the user's moves in one game that committed the habit's targeted mistake."""
    return sum(1 for m in (move_evals or []) if is_targeted_mistake(m, habit))


def user_moves(move_evals) -> int:
    """Denominator for the L4 rate: the user's own moves in the game."""
    return sum(1 for m in (move_evals or [])
               if isinstance(m, dict) and not m.get("is_opponent_move"))


def is_real_game(move_evals) -> bool:
    """Exclude abandoned coach stubs: a game must have >= MIN_GAME_MOVES user moves to be
    measured. Without this, 2-3 move sessions count as 'clean' and inflate the metrics."""
    return user_moves(move_evals) >= MIN_GAME_MOVES
