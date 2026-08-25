"""
Rep Generator — deterministic coaching reps for piece safety
=============================================================

A "rep" is one live decision on a board, answered in seconds and corrected
immediately. It is the unit of the coached experience: eight reps is a session.
See docs/coaching_components_architecture.md.

WHY THIS CAN EXIST AT ALL
-------------------------
The Learning Experience System stalled on content: it needed human-reviewed Gold
positions and had zero, because "what is the best move here?" requires human
judgement.

"Is this square safe, and who takes it?" does not. Static exchange evaluation
answers it deterministically, so reps are GENERATED from data we already hold —
149,886 v16 `move_observations` and 37,266 `community_training_positions` — and
verified at generation time. There is no authoring queue.

ONE PREDICATE, TWO USES
-----------------------
Reps are generated with the same `piece_safety.d_live.v1` predicate that measures
real games (eligible piece >= knight, legal capture on the destination,
destination SEE >= 150, corroborating cp_loss >= 150). What we drill and what we
measure are therefore the same thing, so drill improvement is observable in games
by construction rather than by hoping the two correlate.

SEE comes from `coach_play.coach_blunder_guard` — the single source of truth for
one-move material safety. This module never implements its own.
"""

import logging
import random
from typing import Any, Dict, List, Optional, Tuple

import chess

logger = logging.getLogger(__name__)

# ── The locked d_live.v1 gates ────────────────────────────────────────────────
# Identical to the values the corpus audit locked; see
# docs/simple_hang_corpus_evidence.md §9. Do not tune these independently of the
# measurement — they are the same predicate.
SEE_FLOOR_CP = 150
CORROBORATING_CP_LOSS = 150

# Reps whose SEE lands just BELOW the floor are arguable — a coach cannot defend
# "this is safe" when the exchange costs a pawn and a half — so they are never
# served. Anything at or above SEE_FLOOR_CP is a miss by the locked predicate;
# only the [100, 150) band is discarded.
AMBIGUOUS_SEE_LOW = 100

# Only these pieces create a "live safety decision". A pawn stepping onto an
# attacked square is usually a normal exchange, not a piece-safety error.
ELIGIBLE_PIECE_TYPES = (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)

PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

REP_TYPES = ("is_safe", "who_takes", "pick_safe", "find_loose", "make_it_safe")


def _see_fns():
    """Canonical SEE, imported lazily so this module stays importable in tests
    that do not need a board engine."""
    from coach_play.coach_blunder_guard import material_hung_after, see_gain

    return material_hung_after, see_gain


# ── Difficulty (computed, never authored) ─────────────────────────────────────

def _difficulty(board: chess.Board, move: chess.Move, mover: bool) -> str:
    """Derived from the position, not from a stored tag.

    Easy   — one attacker, no defender at all. Nothing to count: the piece is
             simply taken. This is the whole first rung of the ladder, so it must
             not be gated on piece value — an undefended knight is just as
             obvious as an undefended rook.
    Hard    — the square is contested by several pieces, so the exchange has to
             be counted rather than seen.
    """
    after = board.copy()
    after.push(move)
    attackers = after.attackers(not mover, move.to_square)
    defenders = after.attackers(mover, move.to_square)

    if len(defenders) == 0 and len(attackers) == 1:
        return "easy"
    if len(attackers) >= 2 or len(defenders) >= 2:
        return "hard"
    return "medium"


def _square_name(sq: int) -> str:
    return chess.square_name(sq)


# ── Generation-time verification ──────────────────────────────────────────────

def _evaluate_candidate(
    fen: str, move_uci: str, cp_loss: Optional[float]
) -> Optional[Dict[str, Any]]:
    """Compute the board facts for one candidate rep, or None if the position
    cannot carry a rep at all.

    Rejects, in order: unusable FEN/move, illegal move, an ineligible piece, and
    an ambiguous SEE band. Does NOT decide safe-vs-unsafe — the caller does, so
    that both safe and unsafe reps come from one code path.
    """
    if not fen or not move_uci or len(move_uci) < 4:
        return None
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(move_uci)
    except Exception:
        return None
    if move not in board.legal_moves:
        return None

    moved = board.piece_at(move.from_square)
    if moved is None or moved.piece_type not in ELIGIBLE_PIECE_TYPES:
        return None

    mover = board.turn
    material_hung_after, _see_gain = _see_fns()
    worst_cp, worst_capture = material_hung_after(board, move)

    # An arguable exchange is not teachable. Better to serve nothing.
    if AMBIGUOUS_SEE_LOW <= worst_cp < SEE_FLOOR_CP:
        return None

    after = board.copy()
    after.push(move)
    destination_attacked = after.is_attacked_by(not mover, move.to_square)

    return {
        "fen": fen,
        "move_uci": move_uci,
        "move_san": board.san(move),
        "mover": mover,
        "moved_piece": moved.piece_type,
        "moved_piece_name": PIECE_NAMES[moved.piece_type],
        "to_square": move.to_square,
        "to_square_name": _square_name(move.to_square),
        "see_cp": worst_cp,
        "winning_capture": worst_capture.uci() if worst_capture else None,
        "attacker_square": (
            _square_name(worst_capture.from_square) if worst_capture else None
        ),
        "attacker_piece_name": (
            PIECE_NAMES[after.piece_at(worst_capture.from_square).piece_type]
            if worst_capture and after.piece_at(worst_capture.from_square)
            else None
        ),
        "destination_attacked": destination_attacked,
        "cp_loss": cp_loss,
        "difficulty": _difficulty(board, move, mover),
    }


def _is_miss(facts: Dict[str, Any]) -> bool:
    """The locked d_live.v1 outcome: BOTH gates, never one alone.

    SEE alone over-fires on compensated sacrifices (48% of raw SEE hangs in the
    corpus carried cp_loss < 50). cp_loss alone catches positional errors that
    are not piece-safety errors. The conjunction is the measured predicate.
    """
    cp_loss = facts.get("cp_loss")
    if cp_loss is None:
        return False
    return facts["see_cp"] >= SEE_FLOOR_CP and cp_loss >= CORROBORATING_CP_LOSS


def _is_clean(facts: Dict[str, Any]) -> bool:
    """A genuinely safe decision: the piece moved somewhere contested and
    survived. Required so a drill of only-unsafe reps cannot teach the player to
    answer "unsafe" every time."""
    cp_loss = facts.get("cp_loss")
    return (
        facts["destination_attacked"]
        and facts["see_cp"] < AMBIGUOUS_SEE_LOW
        and (cp_loss is None or cp_loss < CORROBORATING_CP_LOSS)
    )


# ── Rep construction ──────────────────────────────────────────────────────────

def build_rep(
    facts: Dict[str, Any], rep_type: str, source: str
) -> Optional[Dict[str, Any]]:
    """Turn verified board facts into one servable rep.

    The prompt names the move and asks about the square. It never restates what
    SAN already says, and it never names the answer.
    """
    if rep_type not in REP_TYPES:
        return None

    miss = _is_miss(facts)
    clean = _is_clean(facts)
    if not (miss or clean):
        return None

    base = {
        "rep_type": rep_type,
        "fen": facts["fen"],
        "move_uci": facts["move_uci"],
        "move_san": facts["move_san"],
        "difficulty": facts["difficulty"],
        "source": source,
        "see_cp": facts["see_cp"],
        "cp_loss": facts["cp_loss"],
        "fact_version": "piece_safety.d_live.v1",
    }

    if rep_type == "is_safe":
        base.update(
            {
                "prompt": f"You want to play {facts['move_san']}.",
                "options": ["safe", "not_safe"],
                "answer": "not_safe" if miss else "safe",
                "demonstration": (
                    {
                        "capture_uci": facts["winning_capture"],
                        "highlight": [facts["attacker_square"], facts["to_square_name"]],
                        "caption": (
                            f"The {facts['attacker_piece_name']} takes it."
                            if facts["attacker_piece_name"]
                            else "It gets taken."
                        ),
                    }
                    if miss
                    else {
                        "highlight": [facts["to_square_name"]],
                        "caption": "Attacked, but defended enough. It holds.",
                    }
                ),
            }
        )
        return base

    # The remaining types only make sense when something is actually hanging.
    if not miss:
        return None

    if rep_type == "who_takes":
        base.update(
            {
                "prompt": f"After {facts['move_san']}, who takes it?",
                "answer": facts["attacker_square"],
                "answer_kind": "square",
                "demonstration": {
                    "capture_uci": facts["winning_capture"],
                    "highlight": [facts["attacker_square"], facts["to_square_name"]],
                    "caption": f"The {facts['attacker_piece_name']} on "
                    f"{facts['attacker_square']}.",
                },
            }
        )
        return base

    if rep_type == "find_loose":
        base.update(
            {
                "prompt": f"After {facts['move_san']}, one piece can be taken. Which?",
                "answer": facts["to_square_name"],
                "answer_kind": "square",
                "demonstration": {
                    "capture_uci": facts["winning_capture"],
                    "highlight": [facts["to_square_name"]],
                    "caption": f"The {facts['moved_piece_name']} on "
                    f"{facts['to_square_name']}.",
                },
            }
        )
        return base

    # pick_safe and make_it_safe need alternative moves computed from the
    # position; they are built by the pool builder, not from a single candidate.
    return None


# ── Pool building ─────────────────────────────────────────────────────────────

def build_safe_alternatives(
    fen: str, move_uci: str, limit: int = 3
) -> List[Dict[str, str]]:
    """Legal moves of the same piece that do NOT hang material.

    Used by `pick_safe` and to grade `make_it_safe`. Returned in a stable order
    so the same position always offers the same choices.
    """
    try:
        board = chess.Board(fen)
        played = chess.Move.from_uci(move_uci)
    except Exception:
        return []
    material_hung_after, _ = _see_fns()

    out: List[Dict[str, str]] = []
    for mv in sorted(board.legal_moves, key=lambda m: m.uci()):
        if mv.from_square != played.from_square or mv == played:
            continue
        worst, _cap = material_hung_after(board, mv)
        if worst < AMBIGUOUS_SEE_LOW:
            out.append({"uci": mv.uci(), "san": board.san(mv)})
        if len(out) >= limit:
            break
    return out


def generate_reps_from_candidates(
    candidates: List[Dict[str, Any]],
    rep_types: Tuple[str, ...] = ("is_safe", "who_takes"),
    count: int = 8,
    balance_is_safe: bool = True,
    seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Build a verified, balanced set of reps.

    `candidates` are dicts with `fen`, `move_uci` and `cp_loss` — the shape both
    `move_observations` (fen_before/move_uci/cp_loss) and
    `community_training_positions` (fen/user_move_uci/cp_loss) reduce to.

    Balancing matters: a session of only-unsafe `is_safe` reps trains the player
    to answer "not safe" without looking.
    """
    rng = random.Random(seed)
    safe_bucket: List[Dict[str, Any]] = []
    unsafe_bucket: List[Dict[str, Any]] = []
    other: List[Dict[str, Any]] = []

    for cand in candidates:
        facts = _evaluate_candidate(
            cand.get("fen") or cand.get("fen_before"),
            cand.get("move_uci") or cand.get("user_move_uci"),
            cand.get("cp_loss"),
        )
        if facts is None:
            continue
        source = cand.get("source", "corpus")
        for rep_type in rep_types:
            rep = build_rep(facts, rep_type, source)
            if rep is None:
                continue
            if rep_type == "is_safe":
                (unsafe_bucket if rep["answer"] == "not_safe" else safe_bucket).append(rep)
            else:
                other.append(rep)

    rng.shuffle(safe_bucket)
    rng.shuffle(unsafe_bucket)
    rng.shuffle(other)

    # Allocate the session across the requested rep types first, THEN balance
    # inside `is_safe`. Balancing before allocating lets is_safe swallow the
    # whole session and starve every other type.
    out: List[Dict[str, Any]] = []
    share = max(1, count // max(1, len(rep_types)))

    if "is_safe" in rep_types:
        want = share if len(rep_types) > 1 else count
        half = want // 2
        picked = unsafe_bucket[:half] + safe_bucket[: want - half]
        # If one side is short, top up from the other rather than under-filling.
        if len(picked) < want:
            spare = unsafe_bucket[half:] + safe_bucket[want - half:]
            picked.extend(spare[: want - len(picked)])
        out.extend(picked)

    out.extend(other[: max(0, count - len(out))])

    if len(out) < count:
        used = {id(r) for r in out}
        pool = [r for r in (unsafe_bucket + safe_bucket + other) if id(r) not in used]
        out.extend(pool[: count - len(out)])

    rng.shuffle(out)
    return out[:count]
