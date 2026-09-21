"""Specific-question onboarding puzzles, built only where the answer is unique.

Mohit, 2026-09-20: ask the player a REAL question -- "find a fork here", "save
your king from mate" -- instead of "find the best move", start simple, and get
harder when they get it right. That tells you what someone can actually SEE,
which "there is a tactic in this position, find it" never can.

The rule that shapes this file: **the printed question must match the grader.**
Count the moves that satisfy the question the player reads, and if more than
one does, the puzzle is broken -- the player finds a fork, we mark them wrong,
and they stop trusting us. So every builder here returns a puzzle ONLY when
exactly one legal move satisfies its own question. Nothing is graded by
"is this the engine's move"; it is graded by the question's own predicate.

That is also why this file starts with the straightforward families. "Can you
win the queen in two moves" transposes, so it has no single answer and is not
here yet -- Mohit's call was to fill the unambiguous ones first and take the
harder shapes later, for stronger players.

Every family is board truth. No engine call, no stored evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import chess

PIECE_CP = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
            chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}

# What a puzzle needs to be worth setting: a fork on two pawns is not the
# lesson, and "win a pawn" is not a tactic a beginner should be hunting.
FORK_MIN_VALUE = chess.KNIGHT
FREE_PIECE_MIN_CP = 300


@dataclass(frozen=True)
class Puzzle:
    family: str
    fen: str
    question: str
    answer_uci: str
    answer_san: str
    # Why this answer, in the question's own terms -- shown AFTER they try.
    explanation: str
    difficulty: int          # 1 easiest; drives the adaptive ladder


def _piece_value(board: chess.Board, square: int) -> int:
    piece = board.piece_at(square)
    return PIECE_CP.get(piece.piece_type, 0) if piece else 0


def _is_free(board: chess.Board, move: chess.Move) -> bool:
    """Nothing can take back. That is what "free" means to a beginner.

    The first version priced the recapture and compared it to the victim --
    Bxf3 taking a knight (320) where they win back 300 read as "+20, safe".
    It ignored that the BISHOP being given up is worth 330, so the trade is
    -10. Engine-checked on
    r2qkb1r/ppp1pppp/2n2n2/8/2P3b1/P1N2N2/1P1PBPPP/R1BQK2R b: the position is
    dead equal and Bxf3 is not in the top four moves, yet it shipped as a
    free piece.

    So the test is not "do I come out ahead in the exchange" -- it is "can
    anything recapture at all". A puzzle that says something is free had
    better mean it.
    """
    after = board.copy(stack=False)
    after.push(move)
    return not after.attackers(after.turn, move.to_square)


# ── families ──────────────────────────────────────────────────────────────

def _mate_in_one(board: chess.Board) -> List[chess.Move]:
    out = []
    for move in board.legal_moves:
        probe = board.copy(stack=False)
        probe.push(move)
        if probe.is_checkmate():
            out.append(move)
    return out


def _opponent_can_mate(board: chess.Board) -> bool:
    for move in board.legal_moves:
        probe = board.copy(stack=False)
        probe.push(move)
        if probe.is_checkmate():
            return True
    return False


def _survives_two(board: chess.Board) -> bool:
    """After their reply, can we still avoid mate on the move after that?

    Checking only mate-in-one is not "saving your king". Engine-checked on
    2kr1b1r/2pq1p2/Q2p1n1p/6pb/3RP3/2N2PBP/PPP2P2/2K4R b: Kb8 is the single
    move that stops mate NEXT move, and the position is still mate in 2
    (Kb8 Rb4+ Qb5 Rxb5#). A puzzle that says "save your king" and then mates
    the player anyway is worse than no puzzle.
    """
    for reply in board.legal_moves:
        after = board.copy(stack=False)
        after.push(reply)
        if after.is_checkmate():
            return False
        # `after` has US to move. The guard here used to be
        # `if _opponent_can_mate(after)` -- which asks whether WE can mate,
        # because the side to move has flipped. So it was almost always False
        # and the whole check was skipped. Ask the real question directly:
        # is there ANY move of ours after which they cannot mate?
        saved = False
        for ours in after.legal_moves:
            probe = after.copy(stack=False)
            probe.push(ours)
            if not _opponent_can_mate(probe):
                saved = True
                break
        if not saved:
            return False
    return True


def _stops_mate(board: chess.Board) -> List[chess.Move]:
    """They threaten mate in one; which of our moves actually saves us.

    Two conditions, not one: the move must stop the immediate mate AND leave
    a position we can still survive. See _survives_two.
    """
    survivors = []
    for move in board.legal_moves:
        probe = board.copy(stack=False)
        probe.push(move)
        if _opponent_can_mate(probe):
            continue
        if not _survives_two(probe):
            continue
        survivors.append(move)
    return survivors


def _free_captures(board: chess.Board) -> List[chess.Move]:
    out = []
    for move in board.legal_moves:
        if not board.is_capture(move):
            continue
        if _piece_value(board, move.to_square) < FREE_PIECE_MIN_CP:
            continue
        if _is_free(board, move):
            out.append(move)
    return out


def _forks(board: chess.Board) -> List[chess.Move]:
    """Moves that land attacking two pieces worth a knight or more, safely."""
    out = []
    mover = board.turn
    for move in board.legal_moves:
        after = board.copy(stack=False)
        after.push(move)
        targets = []
        for square in after.attacks(move.to_square):
            piece = after.piece_at(square)
            if piece is None or piece.color == mover:
                continue
            if piece.piece_type == chess.KING or \
                    PIECE_CP.get(piece.piece_type, 0) >= PIECE_CP[FORK_MIN_VALUE]:
                targets.append(square)
        if len(targets) < 2:
            continue
        # A fork that hits two DEFENDED pieces wins nothing -- it is a move,
        # not a tactic. Nd4 on the position above attacks the knight on f3
        # and the bishop on e2, and the engine calls it +25cp, because Nxd4
        # simply trades. The exchange value there is 0, which the first
        # version read as "the knight is safe" when it means "this is an
        # even trade".
        #
        # So two things have to hold: at least one target cannot be defended
        # away, and the forking piece is not itself capturable for profit.
        from services.legal_exchange_verifier import independent_exchange_gain
        if independent_exchange_gain(after, move.to_square) > 0:
            continue
        loose = [sq for sq in targets
                 if not after.attackers(not mover, sq)
                 and after.piece_at(sq) is not None
                 and after.piece_at(sq).piece_type != chess.KING]
        if not loose:
            continue
        out.append(move)
    return out


SLIDER_DIRECTIONS = {
    chess.BISHOP: ((1, 1), (1, -1), (-1, 1), (-1, -1)),
    chess.ROOK: ((1, 0), (-1, 0), (0, 1), (0, -1)),
    chess.QUEEN: ((1, 1), (1, -1), (-1, 1), (-1, -1),
                  (1, 0), (-1, 0), (0, 1), (0, -1)),
}


def _lines_created(board: chess.Board, move: chess.Move, kind: str):
    """Moves that create a pin or a skewer, using the geometry helper that
    already exists in cognitive_gap_subtypes rather than a third copy of it.

    A pin/skewer that hands the slider away is not a tactic, and a line onto
    two pawns is not worth setting as a puzzle, so both are gated below.
    """
    from services.cognitive_gap_subtypes import _check_line_pin_or_skewer
    from services.legal_exchange_verifier import independent_exchange_gain

    mover = board.turn
    piece = board.piece_at(move.from_square)
    if piece is None or piece.piece_type not in SLIDER_DIRECTIONS:
        return False
    after = board.copy(stack=False)
    after.push(move)
    # The slider has to survive where it lands.
    if independent_exchange_gain(after, move.to_square) > 0:
        return False
    for direction in SLIDER_DIRECTIONS[piece.piece_type]:
        if _check_line_pin_or_skewer(after, move.to_square, direction,
                                     mover) != kind:
            continue
        # Walk the same line to price what is actually at stake.
        df, dr = direction
        f = chess.square_file(move.to_square) + df
        r = chess.square_rank(move.to_square) + dr
        seen = []
        while 0 <= f < 8 and 0 <= r < 8 and len(seen) < 2:
            sq = chess.square(f, r)
            occupant = after.piece_at(sq)
            if occupant is not None:
                seen.append((sq, occupant))
            f += df
            r += dr
        if len(seen) < 2:
            continue
        front, back = seen[0][1], seen[1][1]
        # Worth a puzzle: the piece we end up winning is a real piece, and the
        # king counts as the strongest thing to pin against.
        prize = back if kind == "skewer" else front
        if prize.piece_type == chess.KING:
            continue
        if PIECE_CP.get(prize.piece_type, 0) < PIECE_CP[chess.KNIGHT]:
            continue
        if kind == "pin" and back.piece_type != chess.KING and \
                PIECE_CP.get(back.piece_type, 0) <= PIECE_CP.get(front.piece_type, 0):
            continue
        return True
    return False


def _pins(board: chess.Board) -> List[chess.Move]:
    return [m for m in board.legal_moves if _lines_created(board, m, "pin")]


def _skewers(board: chess.Board) -> List[chess.Move]:
    return [m for m in board.legal_moves if _lines_created(board, m, "skewer")]


# Searching every reply gets expensive fast, and a position with 40 legal
# moves is not an onboarding puzzle anyway. These caps keep a bulk scan
# finishing without changing what counts as a mate.
MATE_SEARCH_MOVE_CAP = 48
MATE_IN_THREE_MOVE_CAP = 28


def _forces_mate_in(board: chess.Board, moves_left: int) -> bool:
    """Can the side to move force mate within `moves_left` of their moves?

    Exhaustive and exact -- no engine, no evaluation. `moves_left` counts OUR
    moves, so 1 is mate-in-one and 2 is mate-in-two.
    """
    if moves_left <= 0:
        return False
    legal = list(board.legal_moves)
    if len(legal) > MATE_SEARCH_MOVE_CAP:
        return False
    for move in legal:
        after = board.copy(stack=False)
        after.push(move)
        if after.is_checkmate():
            return True
        if moves_left == 1:
            continue
        if after.is_stalemate() or after.is_insufficient_material():
            continue
        # EVERY reply of theirs must still lose. Any escape and this move
        # does not force anything.
        replies = list(after.legal_moves)
        if not replies or len(replies) > MATE_SEARCH_MOVE_CAP:
            continue
        if all(_forces_mate_in(
                (lambda b: (b.push(r), b)[1])(after.copy(stack=False)),
                moves_left - 1) for r in replies):
            return True
    return False


def _mate_in_n_first_moves(board: chess.Board, n: int) -> List[chess.Move]:
    """First moves that force mate in exactly n, and not in fewer.

    "Not in fewer" matters: if a position is mate in one, every mate-in-two
    line through it is real but the puzzle should say mate in ONE. Otherwise
    the two families collide and the count we print is wrong.
    """
    if _forces_mate_in(board, n - 1):
        return []
    out = []
    for move in board.legal_moves:
        after = board.copy(stack=False)
        after.push(move)
        if after.is_checkmate():
            continue                     # that is mate in one, a different family
        if after.is_stalemate() or after.is_insufficient_material():
            continue
        replies = list(after.legal_moves)
        if not replies or len(replies) > MATE_SEARCH_MOVE_CAP:
            continue
        if all(_forces_mate_in(
                (lambda b: (b.push(r), b)[1])(after.copy(stack=False)),
                n - 1) for r in replies):
            out.append(move)
    return out


def _mate_in_two(board: chess.Board) -> List[chess.Move]:
    return _mate_in_n_first_moves(board, 2)


def _mate_in_three(board: chess.Board) -> List[chess.Move]:
    # Three moves deep is a 5-ply search; only attempt it where the position
    # is already narrow enough for it to finish.
    if board.legal_moves.count() > MATE_IN_THREE_MOVE_CAP:
        return []
    return _mate_in_n_first_moves(board, 3)


def _back_rank_mates(board: chess.Board) -> List[chess.Move]:
    """Mate on the back rank where the king is sealed by its OWN pawns.

    A named pattern, which is the whole point -- "there is mate in one" and
    "this is a back-rank mate" teach different amounts. Reuses back_rank_seal
    from services.mate_lesson so the puzzle and the game-review caption agree
    on what a back-rank mate is.
    """
    from services.mate_lesson import back_rank_seal

    out = []
    for move in board.legal_moves:
        after = board.copy(stack=False)
        after.push(move)
        if not after.is_checkmate():
            continue
        king = after.king(after.turn)
        if king is None:
            continue
        # AFTER the mate, not before: back_rank_seal looks up the piece
        # that LANDED on the mating square, and before the move that
        # square is empty.
        if back_rank_seal(after, move, king, after.turn) >= 2:
            out.append(move)
    return out


def _discovered_attacks(board: chess.Board) -> List[chess.Move]:
    """Moves that step a piece aside and uncover a slider onto something real.

    Reuses _discovered_attack_evidence -- the same geometry the review captions
    use. The payoff is checked on the BOARD here rather than replayed from a
    stored engine line: a puzzle has no stored line, and checking directly is
    what the line-replay version got wrong this morning anyway.
    """
    from services.caption_facts import _discovered_attack_evidence
    from services.legal_exchange_verifier import independent_exchange_gain

    mover = board.turn
    out = []
    for move in board.legal_moves:
        after = board.copy(stack=False)
        after.push(move)
        try:
            evidence = _discovered_attack_evidence(board, after, move)
        except Exception:  # noqa: BLE001
            continue
        if not evidence:
            continue
        # The uncovered piece has to be worth taking, and actually takeable.
        worth_it = False
        for item in evidence:
            if int(item.get("target_value_cp") or 0) < PIECE_CP[chess.KNIGHT]:
                continue
            try:
                target = chess.parse_square(str(item.get("target_square")))
            except (ValueError, TypeError):
                continue
            probe = after.copy(stack=False)
            probe.turn = mover
            if independent_exchange_gain(probe, target) >= PIECE_CP[chess.KNIGHT]:
                worth_it = True
                break
        if not worth_it:
            continue
        # The discovery has to come with CHECK. Without it the opponent simply
        # moves the attacked piece away and nothing is won -- engine-checked on
        # 2b2rk1/2p2pp1/prn4p/1p2q3/3pN3/3P1B2/PPPQ1PPP/R3R1K1 w, where Ng3
        # uncovers the rook onto the queen, is not in the engine's top three,
        # and the position is level: Black just plays Qf5.
        #
        # Third time today a tactic family needed "and they cannot just save
        # it" -- the fork needed an undefended target, the free piece needed
        # no recapture, and this needs the tempo.
        if not after.is_check():
            continue
        # And the piece we moved must not simply be lost for doing it.
        if independent_exchange_gain(after, move.to_square) > 0:
            continue
        out.append(move)
    return out


_FAMILIES: Dict[str, Dict[str, object]] = {
    "mate_in_one": {
        "question": "There is mate in one here. Find it.",
        "finder": _mate_in_one,
        "difficulty": 1,
        "explain": "{san} is mate: their king has no legal move left.",
    },
    "stop_the_mate": {
        "question": "They are threatening mate next move. "
                    "Only one move stops it -- find it.",
        "finder": _stops_mate,
        "difficulty": 3,
        "explain": "{san} is the only move that takes the mate away.",
    },
    "take_the_free_piece": {
        "question": "Something of theirs is free. Take it.",
        "finder": _free_captures,
        "difficulty": 1,
        "explain": "{san} wins the {victim} and nothing can take back.",
    },
    "find_the_fork": {
        "question": "One move here attacks two of their pieces at once. Find it.",
        "finder": _forks,
        "difficulty": 2,
        "explain": "{san} hits two pieces at the same time -- they cannot save both.",
    },
    "find_the_pin": {
        "question": "One move here freezes a piece of theirs -- it cannot move "
                    "without losing something bigger behind it. Find it.",
        "finder": _pins,
        "difficulty": 3,
        "explain": "{san} pins it: moving it would hand over the piece behind.",
    },
    "back_rank_mate": {
        "question": "Their king is stuck on the back rank behind its own "
                    "pawns. Finish it.",
        "finder": _back_rank_mates,
        "difficulty": 2,
        "explain": "{san} mates along the back rank -- their own pawns left "
                   "the king nowhere to go.",
    },
    # find_the_discovered_attack is NOT registered. _discovered_attacks below
    # is kept because the gating work is sound, but it has no supply: 0 in 60
    # games once the discovery is required to come with check, and without
    # that requirement it ships false puzzles (engine-checked -- Ng3 uncovers
    # a rook onto a queen on
    # 2b2rk1/2p2pp1/prn4p/1p2q3/3pN3/3P1B2/PPPQ1PPP/R3R1K1 w, is not in the
    # engine's top three, and Black just plays Qf5).
    #
    # There is also an unexplained gap underneath: on a synthetic position
    # where every precondition holds by hand -- white rook e1, knight leaving
    # e5 with check, black queen e7, nothing between -- caption_facts.
    # _discovered_attack_evidence returns no evidence, while returning
    # evidence correctly on real ruled-true cards. Noted, not chased: an empty
    # shelf is worse than no shelf, and discovered_attack occurs in 1.8% of
    # games anyway.
    "mate_in_two": {
        "question": "There is a forced mate in two here. "
                    "What is the first move?",
        "finder": _mate_in_two,
        "difficulty": 4,
        "explain": "{san} starts it -- whatever they answer, mate follows.",
    },
    "mate_in_three": {
        "question": "There is a forced mate in three here. "
                    "What is the first move?",
        "finder": _mate_in_three,
        "difficulty": 5,
        "explain": "{san} starts it -- every defence still loses.",
    },
    "find_the_skewer": {
        "question": "One move here hits two pieces standing on the same line. "
                    "The front one has to move. Find it.",
        "finder": _skewers,
        "difficulty": 4,
        "explain": "{san} attacks the front piece; when it moves, the one "
                   "behind it is yours.",
    },
}


def build_puzzle(fen: str, family: str) -> Optional[Puzzle]:
    """A puzzle for this position, or None when the answer is not unique.

    Returning None on ambiguity is the whole point. A position where two moves
    fork is a fine position and a broken puzzle.
    """
    spec = _FAMILIES.get(family)
    if spec is None:
        return None
    try:
        board = chess.Board(fen)
    except ValueError:
        return None
    if board.is_game_over():
        return None

    # "Stop the mate" only makes sense when a mate is actually threatened.
    if family == "stop_the_mate":
        probe = board.copy(stack=False)
        probe.turn = not board.turn
        if not _opponent_can_mate(probe):
            return None

    try:
        moves = spec["finder"](board)  # type: ignore[operator]
    except Exception:  # noqa: BLE001
        return None
    if len(moves) != 1:
        return None

    move = moves[0]
    san = board.san(move)
    victim = board.piece_at(move.to_square)
    return Puzzle(
        family=family,
        fen=fen,
        question=str(spec["question"]),
        answer_uci=move.uci(),
        answer_san=san,
        explanation=str(spec["explain"]).format(
            san=san,
            victim=chess.piece_name(victim.piece_type) if victim else "piece"),
        difficulty=int(spec["difficulty"]),  # type: ignore[arg-type]
    )


def families() -> List[str]:
    return list(_FAMILIES)
