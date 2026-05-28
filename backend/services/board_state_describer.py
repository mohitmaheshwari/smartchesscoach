"""Board-state describer — pure FEN geometry that paints a coach-voice
picture of the position after the played move.

Mohit 2026-05-21 architectural unlock: when we can't explain the best
move (engine depth), we don't fall back to engine-speak. We describe
*board state from both sides* in human terms. Every move in good chess
has a reason — if a 1200's move lacks one, the board shows it:
scattered pieces, undeveloped, weak king zone, no central control.

All metrics:
  - Read FROM the user's perspective (user_color), so captions say
    "your pieces" / "opponent's pieces" consistently regardless of
    which side just blundered.
  - Compute only from board state (python-chess Board). No engine,
    no LLM, no prose. Strictly geometry → structured facts.
  - Return None placeholders when the metric doesn't fire — selector
    drops those before ranking.

Output shape: list[Fact], severity-ranked, ready for a top-N picker
(see select_top_facts). Each fact carries a fact_id matching a
template key in R12_blunder.json's `variants` map, plus the
placeholder values the template needs.

Architecture LAW: no user-facing strings here. Templates live in JSON.
This module produces only facts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import chess


# ────────────────────────────────────────────────────────────────────
# Public dataclass
# ────────────────────────────────────────────────────────────────────


@dataclass
class BoardStateFact:
    """One ranked, structured board-state observation.

    fact_id    — matches a variant key in R12_blunder.json (e.g.
                 "bs_isolated_attacker", "bs_development_gap").
    category   — used by the selector's diversity rule (max 2 per cat).
    severity   — higher = more teachable; selector ranks by this.
    placeholders — values that the JSON template substitutes.
    """

    fact_id: str
    category: str
    severity: int
    placeholders: Dict[str, Any] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────
# Constants — piece values, names, board geometry helpers
# ────────────────────────────────────────────────────────────────────


_PIECE_NAME = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

_CENTRAL_SQUARES = [chess.E4, chess.D4, chess.E5, chess.D5]

# Starting squares for minor + major pieces — "still home" check.
_HOME_SQUARES_WHITE = {
    chess.KNIGHT: {chess.B1, chess.G1},
    chess.BISHOP: {chess.C1, chess.F1},
    chess.ROOK: {chess.A1, chess.H1},
    chess.QUEEN: {chess.D1},
}
_HOME_SQUARES_BLACK = {
    chess.KNIGHT: {chess.B8, chess.G8},
    chess.BISHOP: {chess.C8, chess.F8},
    chess.ROOK: {chess.A8, chess.H8},
    chess.QUEEN: {chess.D8},
}


def _home_squares(color: chess.Color) -> Dict[int, set]:
    return _HOME_SQUARES_WHITE if color == chess.WHITE else _HOME_SQUARES_BLACK


def _own_side_ranks(color: chess.Color) -> range:
    """Ranks (0-indexed) considered 'own side' for activity metrics.
    White's own side = ranks 0-3 (1-4 in chess notation).
    Black's own side = ranks 4-7 (5-8 in chess notation)."""
    return range(0, 4) if color == chess.WHITE else range(4, 8)


def _opp_side_ranks(color: chess.Color) -> range:
    return range(4, 8) if color == chess.WHITE else range(0, 4)


def _king_zone(king_square: int) -> List[int]:
    """King square + 8 neighbors (clipped to board)."""
    kf = chess.square_file(king_square)
    kr = chess.square_rank(king_square)
    zone = []
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            f = kf + df
            r = kr + dr
            if 0 <= f < 8 and 0 <= r < 8:
                zone.append(chess.square(f, r))
    return zone


def _is_developed(board: chess.Board, color: chess.Color) -> int:
    """Count minor pieces (knight/bishop) that are NOT on their starting
    square. A simple proxy for development that doesn't require move
    history. Returns count in [0..4]."""
    home = _home_squares(color)
    developed = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP):
        for sq in board.pieces(piece_type, color):
            if sq not in home[piece_type]:
                developed += 1
    return developed


# ────────────────────────────────────────────────────────────────────
# Individual metric functions — each returns a BoardStateFact or None.
# ────────────────────────────────────────────────────────────────────


def _metric_isolated_attacker(
    board: chess.Board, user_color: chess.Color, move_number: int
) -> Optional[BoardStateFact]:
    """A user minor/major piece sits in opp territory, undefended,
    and attacked. The classic 'lone invader' shape — coach voice:
    'your knight is alone behind enemy lines.'"""
    opp_color = not user_color
    opp_ranks = _opp_side_ranks(user_color)
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        for sq in board.pieces(piece_type, user_color):
            if chess.square_rank(sq) not in opp_ranks:
                continue
            if board.attackers(opp_color, sq) and not board.attackers(user_color, sq):
                return BoardStateFact(
                    fact_id="bs_isolated_attacker",
                    category="coordination",
                    severity=22,
                    placeholders={
                        "bs_piece": _PIECE_NAME[piece_type],
                        "bs_square": chess.square_name(sq),
                    },
                )
    return None


def _metric_worst_placed_piece(
    board: chess.Board, user_color: chess.Color, move_number: int
) -> Optional[BoardStateFact]:
    """User's minor/major piece with ≤2 legal moves (cramped). Only
    counts pieces that have been DEVELOPED — a rook stuck on a1
    behind its a-pawn is normal opening play, not a teaching moment.
    Also skipped before move 8 to avoid early-opening noise."""
    if move_number < 8:
        return None
    home = _home_squares(user_color)
    saved_turn = board.turn
    board.turn = user_color
    worst_sq = None
    worst_count = None
    worst_piece = None
    try:
        for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            for sq in board.pieces(piece_type, user_color):
                # Skip pieces still on their starting square — they
                # haven't been moved, so being cramped is structural,
                # not a coaching insight.
                if sq in home.get(piece_type, set()):
                    continue
                count = sum(1 for _ in board.legal_moves if _.from_square == sq)
                if worst_count is None or count < worst_count:
                    worst_count = count
                    worst_sq = sq
                    worst_piece = piece_type
    finally:
        board.turn = saved_turn
    if worst_sq is None or worst_count is None or worst_count > 2:
        return None
    return BoardStateFact(
        fact_id="bs_worst_placed_piece",
        category="coordination",
        severity=15,
        placeholders={
            "bs_piece": _PIECE_NAME[worst_piece],
            "bs_square": chess.square_name(worst_sq),
            "bs_legal_count": worst_count,
            "bs_legal_word": "move" if worst_count == 1 else "moves",
        },
    )


def _metric_development_gap(
    board: chess.Board, user_color: chess.Color, move_number: int
) -> Optional[BoardStateFact]:
    """User vs opp minor-piece development count. Opening-phase only.

    Parth Class B (fb_7bba7f53f347 / fb_2be92824826e): require gap >= 3
    (was >= 2). A 2-piece development gap is borderline and produces a
    stat-dump caption ("Opp developed 5; you developed 3") without
    teaching anything actionable. At gap >= 3 the deficit is large
    enough that the user is meaningfully behind.
    """
    if move_number > 20:
        return None
    user_dev = _is_developed(board, user_color)
    opp_dev = _is_developed(board, not user_color)
    gap = opp_dev - user_dev
    if gap < 3:
        return None
    severity = 20 if gap >= 4 else 15
    return BoardStateFact(
        fact_id="bs_development_gap",
        category="development",
        severity=severity,
        placeholders={
            "bs_user_developed": user_dev,
            "bs_opp_developed": opp_dev,
            "bs_user_developed_word": "piece" if user_dev == 1 else "pieces",
        },
    )


def _metric_pieces_on_back_rank(
    board: chess.Board, user_color: chess.Color, move_number: int
) -> Optional[BoardStateFact]:
    """Count of user minor pieces still on starting back rank. Only
    meaningful in the opening (move ≤ 15) AND when opp has at least
    one more developed piece — otherwise symmetric and not teachable."""
    if move_number > 15:
        return None
    home_user = _home_squares(user_color)
    home_opp = _home_squares(not user_color)
    user_home = 0
    opp_home = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP):
        for sq in board.pieces(piece_type, user_color):
            if sq in home_user[piece_type]:
                user_home += 1
        for sq in board.pieces(piece_type, not user_color):
            if sq in home_opp[piece_type]:
                opp_home += 1
    if user_home < 2 or user_home <= opp_home:
        return None
    return BoardStateFact(
        fact_id="bs_pieces_on_back_rank",
        category="development",
        severity=10,
        placeholders={"bs_back_rank_count": user_home},
    )


def _metric_king_shield_broken(
    board: chess.Board, user_color: chess.Color, move_number: int
) -> Optional[BoardStateFact]:
    """User's king has lost shelter pawns from the original castled
    formation. We check the 3 squares directly in front of the king
    on the rank it occupies — if pawns are missing from there (and
    king has castled, i.e. not on e1/e8), call it shield-broken.

    Parth fb_a81663d410b6: gate on king being on its STARTING BACK
    RANK. The "front rank pawns are the shelter" geometry assumes the
    king is castled on rank 1 (white) / rank 8 (black). If the king
    has walked further (e.g. Kc7 from Kc8, or Kg2 from Kg1), the
    shelter calculation looks at the wrong squares — and saying "lost
    N of its pawn shelter" misrepresents a position where the king is
    actively out of shelter altogether.
    """
    if move_number < 10:
        return None
    king_sq = board.king(user_color)
    if king_sq is None:
        return None
    starting_king_sq = chess.E1 if user_color == chess.WHITE else chess.E8
    if king_sq == starting_king_sq:
        return None  # uncastled — the shield idea doesn't apply yet
    # King must still be on its back rank for the shelter geometry to
    # make sense. Walked-off kings have left the shelter — don't claim
    # "lost N pawn shelter" when the structure no longer applies.
    back_rank = 0 if user_color == chess.WHITE else 7
    if chess.square_rank(king_sq) != back_rank:
        return None
    kf = chess.square_file(king_sq)
    # Front rank from king's POV
    front_rank = chess.square_rank(king_sq) + (1 if user_color == chess.WHITE else -1)
    if front_rank < 0 or front_rank > 7:
        return None
    files_to_check = [f for f in (kf - 1, kf, kf + 1) if 0 <= f < 8]
    missing = 0
    for f in files_to_check:
        sq = chess.square(f, front_rank)
        p = board.piece_at(sq)
        if p is None or p.piece_type != chess.PAWN or p.color != user_color:
            missing += 1
    if missing < 2:
        return None
    return BoardStateFact(
        fact_id="bs_king_shield_broken",
        category="king_safety",
        severity=20,
        placeholders={
            "bs_king_square": chess.square_name(king_sq),
            "bs_missing_shield": missing,
        },
    )


def _metric_king_attackers(
    board: chess.Board, user_color: chess.Color, move_number: int
) -> Optional[BoardStateFact]:
    """Count of opp pieces attacking squares in user's king zone.
    3+ attackers = "opp has pieces aimed at your king."""
    if move_number < 10:
        return None
    king_sq = board.king(user_color)
    if king_sq is None:
        return None
    opp_color = not user_color
    attacker_set = set()
    for sq in _king_zone(king_sq):
        for attacker_sq in board.attackers(opp_color, sq):
            attacker_set.add(attacker_sq)
    if len(attacker_set) < 3:
        return None
    return BoardStateFact(
        fact_id="bs_king_attackers",
        category="king_safety",
        severity=18,
        placeholders={
            "bs_king_square": chess.square_name(king_sq),
            "bs_attacker_count": len(attacker_set),
        },
    )


def _metric_central_control_gap(
    board: chess.Board, user_color: chess.Color, move_number: int
) -> Optional[BoardStateFact]:
    """User vs opp attacker count on e4/d4/e5/d5. Gap ≥ 3 fires.

    Parth Class B (fb_7bba7f53f347 / fb_2be92824826e): require gap >= 3
    (was >= 2). Stat-dump captions ('Opp attacks center 6 times; you
    attack it 4 times') with a 2-gap are borderline noise — the user
    can't act on a 2-attacker difference. At gap >= 3 the deficit is
    structurally meaningful.
    """
    opp_color = not user_color
    user_attacks = sum(len(board.attackers(user_color, sq)) for sq in _CENTRAL_SQUARES)
    opp_attacks = sum(len(board.attackers(opp_color, sq)) for sq in _CENTRAL_SQUARES)
    gap = opp_attacks - user_attacks
    if gap < 3:
        return None
    severity = 12 if gap >= 4 else 8
    return BoardStateFact(
        fact_id="bs_central_control_gap",
        category="central",
        severity=severity,
        placeholders={
            "bs_user_central": user_attacks,
            "bs_opp_central": opp_attacks,
            "bs_user_central_word": "time" if user_attacks == 1 else "times",
            "bs_opp_central_word": "time" if opp_attacks == 1 else "times",
        },
    )


def _metric_open_file_owned_by_opp(
    board: chess.Board, user_color: chess.Color, move_number: int
) -> Optional[BoardStateFact]:
    """Open file with an opp rook/queen on it and no user major piece
    contesting it. Classic 'opp owns the d-file' coaching."""
    if move_number < 12:
        return None
    opp_color = not user_color
    for file_idx in range(8):
        has_pawn = False
        opp_major_on_file = None
        user_major_on_file = False
        for rank in range(8):
            sq = chess.square(file_idx, rank)
            p = board.piece_at(sq)
            if p is None:
                continue
            if p.piece_type == chess.PAWN:
                has_pawn = True
                break
            if p.piece_type in (chess.ROOK, chess.QUEEN):
                if p.color == opp_color:
                    opp_major_on_file = p.piece_type
                else:
                    user_major_on_file = True
        if has_pawn or user_major_on_file or not opp_major_on_file:
            continue
        return BoardStateFact(
            fact_id="bs_open_file_owned_by_opp",
            category="central",
            severity=17,
            placeholders={
                "bs_file_letter": chess.FILE_NAMES[file_idx],
                "bs_opp_major_piece": _PIECE_NAME[opp_major_on_file],
            },
        )
    return None


def _metric_queen_alone_active(
    board: chess.Board, user_color: chess.Color, move_number: int
) -> Optional[BoardStateFact]:
    """User's queen is past the midline (opp side ranks) while all
    other user minor/major pieces sit in own-side ranks. Classic
    'queen sortie with no support' shape."""
    if move_number < 8:
        return None
    queens = list(board.pieces(chess.QUEEN, user_color))
    if len(queens) != 1:
        return None
    queen_sq = queens[0]
    opp_ranks = _opp_side_ranks(user_color)
    if chess.square_rank(queen_sq) not in opp_ranks:
        return None
    own_ranks = _own_side_ranks(user_color)
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK):
        for sq in board.pieces(piece_type, user_color):
            if chess.square_rank(sq) not in own_ranks:
                return None  # at least one other piece is also active
    return BoardStateFact(
        fact_id="bs_queen_alone_active",
        category="activity",
        severity=25,
        placeholders={"bs_queen_square": chess.square_name(queen_sq)},
    )


def _metric_connected_rooks_only_opp(
    board: chess.Board, user_color: chess.Color, move_number: int
) -> Optional[BoardStateFact]:
    """Opp rooks see each other on a rank or file; user rooks don't."""
    if move_number < 12:
        return None

    def _rooks_connected(b: chess.Board, color: chess.Color) -> bool:
        rooks = list(b.pieces(chess.ROOK, color))
        if len(rooks) < 2:
            return False
        r0, r1 = rooks[0], rooks[1]
        same_rank = chess.square_rank(r0) == chess.square_rank(r1)
        same_file = chess.square_file(r0) == chess.square_file(r1)
        if not (same_rank or same_file):
            return False
        between = chess.SquareSet(chess.between(r0, r1))
        for sq in between:
            if b.piece_at(sq) is not None:
                return False
        return True

    user_connected = _rooks_connected(board, user_color)
    opp_connected = _rooks_connected(board, not user_color)
    if user_connected or not opp_connected:
        return None
    return BoardStateFact(
        fact_id="bs_connected_rooks_only_opp",
        category="activity",
        severity=12,
        placeholders={},
    )


def _metric_passive_pieces_count(
    board: chess.Board, user_color: chess.Color, move_number: int
) -> Optional[BoardStateFact]:
    """Count of user non-pawn pieces still in own-side ranks (1-4 for
    white, 5-8 for black). 4+ AND opp is more active (fewer passive
    pieces) — symmetric positions don't teach anything."""
    if move_number > 25:
        return None
    own_ranks_user = _own_side_ranks(user_color)
    own_ranks_opp = _own_side_ranks(not user_color)
    user_passive = 0
    opp_passive = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        for sq in board.pieces(piece_type, user_color):
            if chess.square_rank(sq) in own_ranks_user:
                user_passive += 1
        for sq in board.pieces(piece_type, not user_color):
            if chess.square_rank(sq) in own_ranks_opp:
                opp_passive += 1
    if user_passive < 4 or user_passive <= opp_passive:
        return None
    return BoardStateFact(
        fact_id="bs_passive_pieces_count",
        category="activity",
        severity=10,
        placeholders={"bs_passive_count": user_passive},
    )


# ────────────────────────────────────────────────────────────────────
# Top-level: compute all metrics, return ranked list, plus the
# diversity-aware top-N selector.
# ────────────────────────────────────────────────────────────────────


_ALL_METRICS = [
    _metric_isolated_attacker,
    _metric_worst_placed_piece,
    _metric_development_gap,
    _metric_pieces_on_back_rank,
    _metric_king_shield_broken,
    _metric_king_attackers,
    _metric_central_control_gap,
    _metric_open_file_owned_by_opp,
    _metric_queen_alone_active,
    _metric_connected_rooks_only_opp,
    _metric_passive_pieces_count,
]


def describe_board_state(
    fen_after: str,
    user_color: str,
    move_number: int,
) -> List[BoardStateFact]:
    """Run every metric against the post-move board, return the
    ranked list (severity descending). Caller picks top-N via
    select_top_facts (which applies diversity).

    Args:
      fen_after: position FEN AFTER the played move (what the user
        is now looking at).
      user_color: "white" or "black".
      move_number: 1-indexed full move number.
    """
    try:
        board = chess.Board(fen_after)
    except ValueError:
        return []
    color = chess.WHITE if (user_color or "").lower() == "white" else chess.BLACK
    facts: List[BoardStateFact] = []
    for metric in _ALL_METRICS:
        try:
            f = metric(board, color, move_number)
        except Exception:
            f = None
        if f is not None:
            facts.append(f)
    facts.sort(key=lambda x: x.severity, reverse=True)
    return facts


def select_top_facts(
    facts: List[BoardStateFact], n: int = 3, max_per_category: int = 2
) -> List[BoardStateFact]:
    """Pick top-N facts with a diversity rule: no more than
    `max_per_category` facts from the same category. Preserves
    severity ordering otherwise."""
    out: List[BoardStateFact] = []
    counts: Dict[str, int] = {}
    for f in facts:
        if counts.get(f.category, 0) >= max_per_category:
            continue
        out.append(f)
        counts[f.category] = counts.get(f.category, 0) + 1
        if len(out) >= n:
            break
    return out
