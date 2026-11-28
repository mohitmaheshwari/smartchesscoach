"""Was the chance there at all? An opportunity denominator from the board.

Mohit, 2026-11-27: "first I need all the detectors to evaluate and fire."
The thing standing in the way is not detectors -- it is denominators. Before
this module the system had four:

    kept a piece safe        115,295 chances    destination_safety_exact
    answered their threat     82,092 chances    paired booleans
    punished their mistake    26,109 chances    paired booleans
    found best when critical  144,116 chances   paired booleans

Everything else was a numerator: 79,277 `missed_pattern` rows recorded only
when something went wrong, with no record of how often the same chance came
and went fine. "He missed 1,073 forks" cannot be turned into a rate, so it
cannot be compared between players, tracked over time, or used to decide
whether he still needs a drill.

WHY THIS NEEDS NO ENGINE TIME
-----------------------------
`tactic_tags` already carries Lichess-validated board provers (forced mate
100%, free piece 99.6%, discovered attack 98.3%, pin 98.3%, skewer 97.8%,
fork 96.4%). Each answers one question: "is THIS move the tactic?" The
cp_loss gate that made `found`/`missed` useless as a ratio belongs to the
CALLER, not the prover -- and `ASSUMED_CP_LOSS = 300` is the convention the
Lichess validation itself used.

So the chance can be read straight off the board:

    eligible = some legal move is proved to be the tactic
    fires    = the move he played was not one of them

Measured 2026-11-27 on 600 real positions: **3.1 ms a position**, which is
about 0.7 hours single-threaded over all 766,419 stored moves. No Stockfish,
no PV, no new analysis pass.

WHAT IS IN HERE, AND WHAT IS NOT
--------------------------------
Every motif whose proof needs nothing but the position:

  mate_in_one     exact. `board.is_checkmate()` after the move -- there is
                  nothing to approximate and no prover to trust.
  free_material   the free-piece prover, measured 99.6% on Lichess, and the
                  one that takes no line (`_no_line` in tactic_tags).

  fork            geometry from `shape_detectors`, payoff proved off the
                  board by `tactic_payoff`. Added 2026-11-28 (v3).
  skewer          creation proved by `verify_created_alignment`, payoff by
                  the same `tactic_payoff`. Added 2026-11-28 (v4).

PIN AND DISCOVERED ATTACK ARE STILL NOT HERE, AND THAT IS MEASURED
------------------------------------------------------------------
The original reason all four line motifs were absent was the payoff: their
provers walk material along the engine's stored line, present on 30.9% of
moves, and `build_fork_proof` refused all 120 already-tagged positions when
handed an empty line. `tactic_payoff` removed that blocker for fork and
skewer. It did not remove it for pin, and the numbers say why.

Measured 2026-11-28 on 1,200 Lichess puzzles per theme
(`teaching_out/pinskewer_creating_side_validate.py`):

                      creation recall    payoff proved at 200cp
    skewer                 64.9%          54.8%  (84.3% of created)
    pin                    28.5%          50.9%  (50.9% of created)

A pin's value is deferred by construction -- the pinned piece is punished
later, by a second attacker, not inside a three-ply material floor -- so half
of the pins we DO find prove nothing. And the positive set is not clean: of
1,200 puzzles Lichess labels `pin`, 55.8% are won by a move that neither
creates a pin nor piles onto one. The theme covers positions where a pin is
part of the furniture, not the idea. Scoring creation recall against it reads
low for a reason that is not the prover's fault, which is precisely why pin
may not enter on this evidence. Discovered attack is untouched:
`detect_hidden_attack` is a different shape and has not been measured here.

A NOTE ON THE KING, WHICH COST THE FIRST ATTEMPT
------------------------------------------------
The first version of the fork pre-filter scored the king at 0, on the
obvious reading that a king is never captured. A check must be ANSWERED,
which is the whole mechanism of a fork, so that made every check-fork
invisible: the fork path returned zero on 600 real positions and zero on 120
positions the validated prover had already tagged. The king is the most
forkable man on the board. `_VALUE` says so.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

import chess

from services.aligned_tactic_puzzle_proof import verify_created_alignment
from services.free_piece_puzzle_proof import build_free_piece_proof
from services.shape_detectors import (
    detect_bishop_fork,
    detect_knight_fork,
    detect_pawn_fork,
    detect_queen_fork,
    detect_rook_fork,
)
from services.caption_facts import PIECE_VALUE_CP
from services.tactic_payoff import proved_payoff_moves

TACTIC_OPPORTUNITY_VERSION = "tactic_opportunity.v5"

# THE CALLER'S GATE, measured 2026-11-28 and locked here instead of left to
# whoever calls this module -- which is how v1 shipped, and it was wrong.
#
# v1 had `fires` alone and `fires` is a pure board fact: "a proved winner was
# available and he did not play it". Measured on 600 real games / 1,895
# chances, 39.9% of its 671 fires were on THE ENGINE'S OWN BEST MOVE. There is
# no reading of chess in which playing the best move is a miss. The board fact
# was true every time; the coaching claim built on it was false 2 times in 5.
#
# The fix is not to gate the board fact -- that would corrupt the denominator,
# which is the whole point of this module. `fires` stays exactly as it was and
# the rate stays computable with no engine at all. What is added is a SECOND,
# narrower verdict for the claim a player is actually shown.
#
# Gate, from the distribution:
#   played != the engine's best move     removes all 268 false fires
#   engine's own label is an error        excludes 'good'/'best'/'brilliant'
#   cp_loss >= 100                        the floor every prover in this
#                                         codebase already refuses below
#
# Survivors on the measured sample: free_material 167 fires labelled only
# blunder/mistake/inaccuracy; mate_in_one 15, all blunders.
MIN_COACHABLE_CP_LOSS = 100
ERROR_LABELS = frozenset({"inaccuracy", "mistake", "blunder"})

# The same constant tactic_tags uses when it asks a prover about a move it
# already believes in: a proved tactic is winning by construction, and the
# provers refuse a cp_loss under 100 outright.
ASSUMED_CP_LOSS = 300

# See the module docstring: the king is 100, not 0.
_VALUE: Mapping[int, int] = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100,
}

QUALITY_IDS = {
    "mate_in_one": "gap:missed_tactic:mate_in_one",
    "free_material": "gap:missed_tactic:free_material",
    # NOT the same thing as gap:missed_tactic:missed_fork, which is Plan grade
    # and LABELS a fork that was missed. This one COUNTS the chances, including
    # the ones he took, which is the only way the label becomes a rate.
    "fork": "gap:missed_tactic:fork_opportunity",
    # Likewise distinct from gap:missed_tactic:missed_skewer, which labels a
    # skewer that was missed. This counts the chances either way.
    "skewer": "gap:missed_tactic:skewer_opportunity",
}

# How much material a fork must force before it is a chance worth counting.
# Swept, not picked: against Lichess-labelled forks the proved recall runs
# 62.7% at 100cp, 61.3% at 200, 57.3% at 300 and 32.7% at 500, so 500 throws
# away a third of the family and 100 buys 1.4 points over 200 by admitting
# forks that win only a pawn. 200 keeps the recall above the Plan floor of 60%
# and still means "won material", not "won a tempo".
MIN_FORK_GAIN_CP = 200

# Same question for the skewer, swept the same way on 1,200 Lichess puzzles
# labelled `skewer`: proved recall runs 58.3% at 100cp, 54.8% at 200, 53.0%
# at 300 and 39.8% at 500. 100cp buys 3.5 points by admitting skewers that
# win a pawn, which is not a skewer worth a lesson; 500 throws away a quarter
# of the family. 200 is held to match the fork, so one number means "won at
# least a minor piece" across the whole denominator rather than two.
MIN_SKEWER_GAIN_CP = 200

# The only pieces that can be the ATTACKER of a ray alignment. See
# aligned_tactic_puzzle_proof._ray_alignments, which iterates exactly these.
_SLIDERS = frozenset({chess.BISHOP, chess.ROOK, chess.QUEEN})

# THE SHAPE MUST BE SUBSTANTIVE BEFORE THE PAYOFF IS ASKED ABOUT
# ---------------------------------------------------------------
# v4 proved two things and never linked them: `*_candidates` proved the shape
# and `proved_payoff_moves` proved >= 200cp, with nothing asking whether the
# 200cp was the SHAPE'S doing. Measured on 8,000 ordinary played positions:
# 58.0% of proved skewers had a PAWN as the rear man -- the man a skewer is
# supposed to win -- and 32.7% of proved forks attacked only one material man.
# Those are attacks and captures that happen to be good moves, not forks and
# skewers, and "a skewer was there to play" is false about them.
#
# The rule below is a pure board property, decided BEFORE the three-ply search
# (so it is also cheaper, not just safer):
#
#   fork    two attacked material men, or one plus check -- a check has to be
#           answered, so that man cannot also be saved
#   skewer  the rear man is a real piece, not a pawn
#
# Its price, measured on Lichess-verified positives, is almost nothing:
# fork 65.3% -> 65.3% recall (784 of 784 solutions kept) and skewer
# 54.8% -> 54.2% (651 of 657; only 6 real skewer solutions have a pawn
# behind). That asymmetry is the point -- a puzzle is SELECTED to contain a
# tactic so its shapes are substantive by construction, while an ordinary
# position's are not. The rule is therefore nearly free on recall and does all
# of its work on precision.
#
# What it is NOT: a claim that the payoff is attributable to the shape. A
# strict "the capture must land on the target square" test was tried and
# REJECTED as a measure -- it scores Rg3+ in
# 8/2r5/6q1/8/8/2PR1R2/1PK3k1/8 w - - 8 53 as false, when Kxg3 is illegal
# (Rd3 covers g3), black's only capture Qxg3 loses the queen to the recapture,
# and the forked queen is exactly the mechanism, just collected on g3 instead
# of g6. A target won anywhere but its own square is invisible to that test,
# so its 59.6%/39.0% are upper bounds on the false-claim rate and were never
# the rate.
_REAL_PIECE_CP = PIECE_VALUE_CP[chess.KNIGHT]
_MATERIAL_MEN = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK,
                 chess.QUEEN)


def _attacked_material_men(board: chess.Board, move: chess.Move) -> int:
    """How many enemy men worth capturing the piece hits once it lands.

    The king is excluded on purpose, and separately: a check is ANSWERED,
    never captured, so it can never be where a material payoff comes from --
    but it does stop the other man running away, which is why one man plus
    check counts below.
    """
    after = board.copy(stack=False)
    after.push(move)
    them = not board.turn
    count = 0
    for square in after.attacks(move.to_square):
        piece = after.piece_at(square)
        if (piece is not None and piece.color == them
                and piece.piece_type in _MATERIAL_MEN):
            count += 1
    return count


def fork_is_substantive(board: chess.Board, move: chess.Move) -> bool:
    """Does this move really hit two things at once?"""
    men = _attacked_material_men(board, move)
    if men >= 2:
        return True
    if men != 1:
        return False
    after = board.copy(stack=False)
    after.push(move)
    return after.is_check()


def skewer_rear_is_a_real_piece(board: chess.Board, move: chess.Move) -> bool:
    """Is the man behind the front one worth winning?"""
    try:
        created = verify_created_alignment(board, move, "skewer")
    except Exception:                                          # noqa: BLE001
        return False
    rear = (created or {}).get("rear_square")
    if not rear:
        return False
    after = board.copy(stack=False)
    after.push(move)
    try:
        piece = after.piece_at(chess.parse_square(str(rear)))
    except (ValueError, TypeError):
        return False
    if piece is None:
        return False
    return PIECE_VALUE_CP.get(piece.piece_type, 0) >= _REAL_PIECE_CP


_FORK_SHAPES = (
    detect_knight_fork,
    detect_bishop_fork,
    detect_rook_fork,
    detect_queen_fork,
    detect_pawn_fork,
)


def _stand_in(board: chess.Board, move: chess.Move) -> Optional[str]:
    """Any other legal move, which is what the provers compare against.

    The provers answer "is `best` the tactic where `played` was not", so
    asking about a move requires something to contrast it with. The same
    convention as tactic_tags._stand_in.
    """
    for other in board.legal_moves:
        if other != move:
            return other.uci()
    return None


def mate_in_one_moves(board: chess.Board) -> List[chess.Move]:
    """Every legal move that is checkmate. Exact, and no prover involved."""
    out: List[chess.Move] = []
    for mv in board.legal_moves:
        board.push(mv)
        try:
            if board.is_checkmate():
                out.append(mv)
        finally:
            board.pop()
    return out


def free_material_candidates(board: chess.Board) -> List[chess.Move]:
    """Captures worth asking about: of an undefended man, or of a bigger one.

    A cheap geometric sieve so the prover is asked about a handful of moves
    rather than all thirty-odd. It may over-offer -- the prover is what
    decides -- but it must never miss a real one, so the test for "free"
    stays deliberately loose.
    """
    out: List[chess.Move] = []
    for mv in board.legal_moves:
        if not board.is_capture(mv):
            continue
        victim = board.piece_at(mv.to_square)
        taker = board.piece_at(mv.from_square)
        if victim is None or taker is None:
            # en passant: the captured pawn is not on the target square
            continue
        defended = bool(board.attackers(victim.color, mv.to_square))
        if not defended or _VALUE[victim.piece_type] > _VALUE[taker.piece_type]:
            out.append(mv)
    return out


def _proved_free(board: chess.Board, candidate: chess.Move) -> bool:
    other = _stand_in(board, candidate)
    if other is None:
        return False
    try:
        bundle = build_free_piece_proof(
            board, other, candidate.uci(), ASSUMED_CP_LOSS)
    except Exception:                                          # noqa: BLE001
        # A prover must never take the analysis pipeline down over one move.
        return False
    return bool(bundle and getattr(bundle.verifier, "verified", False))


def free_material_moves(board: chess.Board) -> List[chess.Move]:
    """Captures the validated free-piece prover confirms win material."""
    return [mv for mv in free_material_candidates(board)
            if _proved_free(board, mv)]


def fork_candidates(board: chess.Board) -> List[chess.Move]:
    """Moves the geometry detectors say would create a fork.

    The sieve only. `shape_detectors` answers "what shape would this move
    make"; whether the shape is worth anything is the payoff prover's
    question, kept separate on purpose.

    Events describing a fork that ALREADY stands on the board carry no
    executing_move and are skipped: this is a move-level denominator, and
    "the fork was already there" is not a chance he either took or missed on
    this move.
    """
    out: List[chess.Move] = []
    seen = set()
    for detect in _FORK_SHAPES:
        try:
            events = detect(board)
        except Exception:                                      # noqa: BLE001
            # One shape detector may never take the pipeline down.
            continue
        for event in events or ():
            move = event.get("executing_move")
            if move is None:
                continue
            if not isinstance(move, chess.Move):
                try:
                    move = chess.Move.from_uci(str(move))
                except (ValueError, TypeError):
                    continue
            if move in board.legal_moves and move.uci() not in seen:
                # The shape has to be a fork before its payoff is worth
                # asking about: on ordinary positions 32.7% of what got this
                # far hit only one material man. See _REAL_PIECE_CP above.
                if not fork_is_substantive(board, move):
                    continue
                seen.add(move.uci())
                out.append(move)
    return out


def fork_moves(board: chess.Board) -> List[chess.Move]:
    """Forks whose material payoff is proved against EVERY opponent reply.

    This is the half that did not exist before. Every other fork payoff prover
    in this codebase walks the material along the engine's stored line, which
    is present on 30.9% of moves; handed an empty line, `build_fork_proof`
    refused all 120 positions `tactic_tags` had already tagged as missed forks.
    `tactic_payoff` replaces the line with an exhaustive two-ply search, so the
    proof needs no engine at all.
    """
    return sorted(
        proved_payoff_moves(board, fork_candidates(board),
                            min_gain=MIN_FORK_GAIN_CP),
        key=lambda mv: mv.uci(),
    )


def skewer_candidates(board: chess.Board) -> List[chess.Move]:
    """Moves that CREATE a skewer, which is a different question from
    "is there a skewer on the board".

    `detect_skewer` answers the second one: it reports existing alignments and
    carries `executing_move=None` on every event, so it offers nothing a
    payoff prover can score. Measured on 1,200 Lichess skewer puzzles it fires
    on 72 and offers a move on 0.

    The creating-side test already existed -- `verify_created_alignment` in
    `aligned_tactic_puzzle_proof`, built for puzzle admission. It diffs ray
    alignments before and after the move, keeps only those whose attacker IS
    the piece that just moved, and throws out any line the front piece can
    break by simply capturing the attacker -- the check that 388 of 1,457
    stored missed_pin labels failed. What was missing was never the test: it
    verifies ONE move, and a denominator needs every move. That loop is this
    function, and it is the whole of what this adds.

    Only slider moves are asked about, and that is LOSSLESS rather than a
    speed/recall trade. `_ray_alignments` walks rays from bishops, rooks and
    queens only -- no other piece can be the attacker of a ray alignment --
    and `verify_created_alignment` keeps an alignment only when its attacker
    square IS the square the move landed on. So a move whose piece does not
    end up a slider on its destination can never pass, and asking is pure
    cost. Promotion to a slider counts; castling does not, because the move's
    destination is the king's square and the function would reject it anyway.
    Verified equivalent on 600 real positions and on 1,200 Lichess puzzles.

    Costs about 2 ms a position this way against 6.5 ms over every legal move.
    """
    out: List[chess.Move] = []
    for move in board.legal_moves:
        if move.promotion:
            lands_as = move.promotion
        else:
            mover = board.piece_at(move.from_square)
            if mover is None:
                continue
            lands_as = mover.piece_type
        if lands_as not in _SLIDERS:
            continue
        try:
            created = verify_created_alignment(board, move, "skewer")
        except Exception:                                      # noqa: BLE001
            # One position may never take the pipeline down.
            continue
        if created and skewer_rear_is_a_real_piece(board, move):
            # A pawn behind the front man is a skewer by geometry and not a
            # lesson: 58.0% of v4's proved skewers were exactly that.
            out.append(move)
    return out


def skewer_moves(board: chess.Board) -> List[chess.Move]:
    """Skewers whose material payoff is proved against EVERY opponent reply.

    A skewer is the line motif this works for: the front man is the valuable
    one, so he moves and the man behind him falls, and that happens inside the
    three plies `tactic_payoff` searches. On 1,200 Lichess skewer puzzles
    84.3% of created skewers prove at 200cp and only 3.3% come back with a
    negative floor. The same composition on pins proves 50.9%, which is why
    pin is not here.
    """
    return sorted(
        proved_payoff_moves(board, skewer_candidates(board),
                            min_gain=MIN_SKEWER_GAIN_CP),
        key=lambda mv: mv.uci(),
    )


def _coachable(fires: bool, played_uci: Optional[str],
               engine: Optional[Mapping[str, Any]]) -> Optional[bool]:
    """May a player be TOLD he missed this? A stricter question than `fires`.

    None means "not measured" -- no engine witness was supplied -- which is a
    different fact from False and must not collapse into it.

    The board proves the chance existed. It does not prove that skipping it was
    an error, and in 39.9% of v1 fires it was not: he had something better, and
    the engine said so. Three independent conditions, all from stored fields:
    he did not play the engine's choice, the engine calls his move an error,
    and the error is at least MIN_COACHABLE_CP_LOSS.
    """
    if not fires or engine is None:
        return None if engine is None else False
    best = engine.get("best_move_uci")
    if best and played_uci and str(best) == str(played_uci):
        return False
    if str(engine.get("evaluation") or "").lower() not in ERROR_LABELS:
        return False
    try:
        cp = float(engine.get("cp_loss") or 0)
    except (TypeError, ValueError):
        return False
    return cp >= MIN_COACHABLE_CP_LOSS


def _verdict(motif: str, takers: Sequence[chess.Move],
             played: Optional[chess.Move],
             played_uci: Optional[str] = None,
             engine: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    eligible = bool(takers)
    _fires = eligible and (played is None or played not in takers)
    return {
        "coachable": _coachable(_fires, played_uci, engine),
        "quality_id": QUALITY_IDS[motif],
        "version": TACTIC_OPPORTUNITY_VERSION,
        "eligible": eligible,
        # Not eligible means no chance arose, which is NOT a failure. Keeping
        # `fires` False here is what makes the pair a rate: the denominator
        # counts chances, never positions.
        "fires": eligible and (played is None or played not in takers),
        "chances": [mv.uci() for mv in takers],
    }


def opportunities(fen: str, played_uci: Optional[str],
                  engine: Optional[Mapping[str, Any]] = None
                  ) -> Optional[Dict[str, Dict[str, Any]]]:
    """Per motif: did the chance exist, and did he take it?

    Returns None only when the position itself cannot be read. A missing or
    illegal played move still yields the denominator -- the chance existed
    whatever he did with it -- and counts as not taken, because the move we
    cannot read is not one of the proved winners.
    """
    try:
        board = chess.Board(fen)
    except (ValueError, TypeError):
        return None
    if not board.is_valid():
        return None

    played: Optional[chess.Move] = None
    if played_uci:
        try:
            candidate = chess.Move.from_uci(str(played_uci))
        except (ValueError, TypeError):
            candidate = None
        if candidate is not None and candidate in board.legal_moves:
            played = candidate

    return {
        "mate_in_one": _verdict("mate_in_one", mate_in_one_moves(board), played,
                                played_uci, engine),
        "free_material": _verdict("free_material", free_material_moves(board),
                                  played, played_uci, engine),
        "fork": _verdict("fork", fork_moves(board), played,
                         played_uci, engine),
        "skewer": _verdict("skewer", skewer_moves(board), played,
                           played_uci, engine),
    }
