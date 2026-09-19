"""Read what a detector would actually say, and rule on it.

Every detector here lands in shadow by default — `_UNKNOWN` grades an
unregistered id SHADOW with "No reviewed promotion packet; unknown IDs fail
closed". That default is right for a live product and wrong for this one.
ChessGuru is not launched. A wrong claim costs one review cycle; silence costs
the review cycle itself, and 47 of 48 registered detectors have been mute
long enough that nobody remembers what they would say.

So this serves the claims. One at a time, rendered exactly as a player would
read them, with the position and the detector's own evidence beside them. A
verdict is true / false / unsure, and it is Mohit's, not a model's.

Two things it deliberately is NOT:

- not a promotion. Verdicts accumulate into the precision figure a promotion
  packet needs, but `detector_quality` remains the only authority on what may
  reach a player, and nothing here writes to it.
- not a sample of the detector's own choosing. Fires are drawn in corpus
  order and skipped once ruled, so the easy ones cannot float to the top.

Follows the geometry-gaps queue (`/admin/geometry-gaps/next` + POST +
`/results`) rather than inventing a fourth review shape.
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import chess
from fastapi import APIRouter, Body, Depends, HTTPException, Query

from routes.admin import require_admin
from routes.auth import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin"])
db = None

VERDICTS = {"true", "false", "unsure"}
COLLECTION = "detector_claim_rulings"

# How many analyses to walk before giving up on finding an unjudged fire.
#
# This was 900 while the loop did a database round trip per analysis. With the
# game context preloaded the walk is CPU-bound, so it can cover the whole
# corpus (15,807 analyses today). 900 was why the page told Mohit "done" on
# allowed_mate and fork at 36 and 32 rulings: it had run out of the window,
# not out of claims, and the empty state could not tell him which.
SCAN_LIMIT = 20000

# A motif claim says "it wins material". That has to mean piece-scale, not a
# pawn left over after trading a bishop for a knight. Measured across the live
# claim set before choosing it -- see the note at the gate.
WINNABLE_CP = 200


def set_db(database):
    global db
    db = database


# ─── The claim producers ────────────────────────────────────────────────
#
# One per detector. Each takes a single stored move (plus the game's colour
# and the analysis, for the two detectors that need wider context) and returns
# either None or (claim_sentence, evidence_dict).
#
# They are deliberately thin adapters over the real detectors rather than
# reimplementations. A review that judged a copy of a detector would certify
# the copy, and the grade would be attached to code no player ever runs.


def _orientation_and_arrow(fen, san):
    """What the reviewer needs to SEE, worked out once, on the server.

    The card was unreadable without these: no indication of whose move it is,
    and no indication of where the move being claimed actually goes. Mohit,
    looking at the first build: "this is not very clear to understand the
    purpose of this page."

    Returns (side_to_move, [from_sq, to_sq]) with the move in UCI squares, or
    (side, None) when the move cannot be parsed in this position.
    """
    import chess

    try:
        board = chess.Board(str(fen or ""))
    except (ValueError, AssertionError):
        return ("white", None)
    side = "white" if board.turn == chess.WHITE else "black"
    if not san:
        return (side, None)
    try:
        move = board.parse_san(str(san))
    except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError,
            chess.AmbiguousMoveError):
        return (side, None)
    return (side, [chess.square_name(move.from_square),
                   chess.square_name(move.to_square)])


# ─── How sure is the BOARD, on its own? ─────────────────────────────────
#
# Mohit, after ruling 91 cards: "please only show me positions which you're
# not sure about, there is no point showing me what you already know are true,
# that's not my job."
#
# He is right, and the queue was built backwards. The gates above can settle a
# claim mechanically -- is the target winnable, does the line reach mate, can
# the piece legally be taken -- and then the page spent his afternoon on the
# ones the gates were MOST certain of.
#
# So each claim carries a confidence, and the queue serves the least certain
# first. What this is NOT: auto-approval. A low-confidence claim is where his
# judgement adds something the board cannot supply; a high-confidence one is
# still only board-verified, and the threshold lock is explicit that board
# verification alone does not promote a detector. It reorders. It never rules.
#
# The lock's own sampling rule is about stopping a detector flattering itself
# by floating EASY cases to the top. This does the opposite, which can only
# lower a measured precision, never raise it.

CONFIDENCE_CERTAIN = "certain"      # the board settles it; low review value
CONFIDENCE_LIKELY = "likely"        # settled, but near a boundary
CONFIDENCE_UNCERTAIN = "uncertain"  # the board cannot answer the real question

_CONFIDENCE_RANK = {
    CONFIDENCE_UNCERTAIN: 0,
    CONFIDENCE_LIKELY: 1,
    CONFIDENCE_CERTAIN: 2,
}


def _motif_confidence(names, probe, after, mover, best_gain):
    """Certain when the win is unambiguous; uncertain when it is a judgement.

    A target nobody defends, taken for 400cp or more, is not a question worth
    a person's time. A defended target won by 200 after a trade is exactly the
    shape Mohit kept marking unsure, and it is where the real question lives:
    is this the lesson, or just a true sentence?
    """
    import chess as _chess

    undefended = 0
    for name in names:
        try:
            sq = _chess.parse_square(str(name))
        except (ValueError, TypeError):
            continue
        if not after.attackers(not mover, sq):
            undefended += 1
    if best_gain is None:
        return CONFIDENCE_UNCERTAIN
    if undefended and best_gain >= 400:
        return CONFIDENCE_CERTAIN
    if best_gain >= 300:
        return CONFIDENCE_LIKELY
    return CONFIDENCE_UNCERTAIN


def _produce_allowed_mate(move, colour, analysis):
    from services.allowed_mate_detector import detect_allowed_mate, render_claim

    evidence = detect_allowed_mate(move, colour)
    if not evidence:
        return None
    fen = evidence.get("fen_before")
    side, arrow = _orientation_and_arrow(fen, evidence.get("played_san"))
    evidence = dict(evidence)
    from services.allowed_mate_detector import _plies_to_mate

    # Certain when the stored line actually reaches checkmate on the board.
    # A truncated line is not evidence of safety -- it is a question.
    _proved = _plies_to_mate(str(evidence.get("fen_after") or ""),
                             list(evidence.get("mating_line") or []))
    evidence.update({
        "confidence": CONFIDENCE_CERTAIN if _proved else CONFIDENCE_UNCERTAIN,
        "review_fen": fen, "side_to_move": side, "arrow": arrow,
        "arrow_is": "the move played",
        "line_fen": fen,
        # The mate IS the punishment line, so it steps like any other.
        "pv_after_played": list(evidence.get("mating_line") or [])[:8],
        "best_move": move.get("best_move"),
        "pv_after_best": list(move.get("pv_after_best") or [])[:8],
    })
    return (render_claim(evidence), evidence)


def _produce_simple_hang(move, colour, analysis):
    """`played_hangs_detector` -- 96.9% documented on 260 reviewed fires.

    The closest thing we have to a promotable detector, and the one whose
    review is most worth Mohit's time.
    """
    import chess

    from services.played_hangs_detector import clause_for, detect_played_hangs

    fen = move.get("fen_before")
    uci = move.get("move_uci")
    if not fen or not uci:
        return None
    try:
        board = chess.Board(fen)
        played = chess.Move.from_uci(uci)
        if played not in board.legal_moves:
            return None
    except (ValueError, AssertionError):
        return None
    hang = detect_played_hangs(
        board, played, move.get("cp_loss"),
        mate_in_play=bool(move.get("mate_info")))
    if not hang:
        return None
    # Position says hanging; what actually happened next is the other half.
    # They disagree on a quarter of cases, and that disagreement is the only
    # interesting question here -- everything else the board already settled.
    confidence = CONFIDENCE_CERTAIN
    try:
        from services.legal_exchange_verifier import independent_exchange_gain

        sq = chess.parse_square(str(hang.get("square")))
        after_board = chess.Board(str(move.get("fen_after") or ""))
        gain = independent_exchange_gain(after_board, sq)
        lost_next = 0
        replay = chess.Board(str(move.get("fen_after") or ""))
        for san in list(move.get("pv_after_played") or [])[:4]:
            nxt = replay.parse_san(str(san))
            cap = replay.piece_at(nxt.to_square)
            if cap is not None and cap.color == board.turn:
                lost_next += 1
            replay.push(nxt)
        if gain >= 300 and lost_next:
            confidence = CONFIDENCE_CERTAIN
        elif not lost_next:
            confidence = CONFIDENCE_UNCERTAIN   # says hanging, nothing was lost
        else:
            confidence = CONFIDENCE_LIKELY
    except Exception:  # noqa: BLE001
        confidence = CONFIDENCE_UNCERTAIN

    return (
        f"After {move.get('move')}, {clause_for(hang)}.",
        {"fen_before": fen, "fen_after": move.get("fen_after"),
         # The claim is "after X your piece hangs", so show the position it
         # hangs in.
         "review_fen": move.get("fen_after") or fen,
         # Both lines, so the reviewer can step the mistake forward AND see
         # what the engine wanted -- the /admin/geometry-gaps shape.
         "line_fen": fen,
         "played_san": move.get("move"),
         "best_move": move.get("best_move"),
         "pv_after_played": list(move.get("pv_after_played") or [])[:8],
         "pv_after_best": list(move.get("pv_after_best") or [])[:8],
         "move_number": move.get("move_number"),
         "cp_loss": move.get("cp_loss"), "hung_piece": hang.get("piece"),
         "hung_square": hang.get("square"),
         "confidence": confidence,
         "side_to_move": "white" if board.turn == chess.WHITE else "black",
         "highlight": [hang.get("square")],
         "highlight_is": "the piece said to be hanging",
         "defender_moved_away": not hang.get("moved_piece")},
    )


def _missed_motif(builder, label):
    """Shared shape for the two motif proofs.

    Both answer the same question -- did the move the player MISSED create
    this motif -- so the claim is about the best move, not the played one.

    A note on the wording, because the caption guard is right to flag it:
    `fork_puzzle_proof` and `discovered_attack_puzzle_proof` have no claim
    renderer at all. They have never spoken, so there is no player-facing
    sentence to review against, and the threshold lock's "evidence must match
    the player-facing claim" cannot be satisfied yet by anyone.

    So a ruling here certifies the DETECTION, not the prose -- is it true that
    the best move forks? The wording review happens when these are wired into
    `build_move_teaching_decision`, which is where every player-facing caption
    belongs and where the guard will enforce it. The UI says this in as many
    words so the reviewer knows which question they are answering.
    """

    def produce(move, colour, analysis):
        import chess

        fen = move.get("fen_before")
        played, best = move.get("move"), move.get("best_move")
        if not fen or not played or not best:
            return None
        try:
            board = chess.Board(fen)
        except (ValueError, AssertionError):
            return None
        from services.legal_exchange_verifier import independent_exchange_gain

        after = board.copy(stack=False)
        after.push(board.parse_san(best))
        bundle = builder(board, played, best, move.get("pv_after_best") or [],
                         move.get("cp_loss"))
        if not bundle:
            return None
        # A bundle is returned even when the independent verifier REJECTED the
        # payoff -- `verified=False` with empty acceptable_moves. Those are
        # candidates the detector does not stand behind, and showing them as
        # claims put 83% of discovered_attack and 65% of fork rubbish into the
        # queue. Mohit caught two of them by hand before this was found.
        #
        # The canonical miss: Bf1 "discovers" the queen onto a knight on d7 --
        # true geometry, and the knight is defended by the queen on e6 so it
        # wins nothing. The stored line has the knight simply walking away.
        # The detector saw all of that and said unverified. The queue did not
        # ask.
        if not getattr(getattr(bundle, "verifier", None), "verified", False):
            return None

        # Second gate, board-only: the target has to be WINNABLE, not merely
        # attacked. The verifier above proves the ray opens and the stored line
        # pays off; it does not price the target square itself, and a defended
        # target survives that. Mohit's first two rejected cards were both this
        # shape -- a knight on d7 defended by a queen on e6, a knight on d2
        # defended by a knight on f3 -- where the "discovery" wins nothing.
        #
        # Board-verifier adjudication is what the threshold lock permits, so
        # this is allowed to filter. It only removes; it never promotes.
        facts = list(getattr(getattr(bundle, "detector", None), "facts", ()) or ())
        head = (facts[0] or {}) if facts else {}
        # Two shapes: discovered_attack names one `target_square`, fork carries
        # a list under `targets`. Reading only the first meant fork skipped
        # this gate entirely.
        names = []
        if head.get("target_square"):
            names.append(head["target_square"])
        for t in head.get("targets") or []:
            names.append(t.get("square") if isinstance(t, dict) else t)

        if names:
            probe = after.copy(stack=False)
            probe.turn = board.turn          # the side that played the motif
            best_gain = None
            for name in names:
                try:
                    sq = chess.parse_square(str(name))
                except (ValueError, TypeError):
                    continue
                gain = independent_exchange_gain(probe, sq)
                best_gain = gain if best_gain is None else max(best_gain, gain)
            # WINNABLE_CP, not "> 0". Mohit's Nxh7: the discovery hits a knight
            # on h6 defended by the g7 pawn, so Bxh6 gxh6 Qxh6 nets +100 -- a
            # bishop traded for a knight plus a pawn. True, and not what "it
            # wins material with a discovered attack" tells a player.
            #
            # Threshold from the distribution, not from taste: of 11 claims, 8
            # win the target outright, 2 win 200-299, and exactly 1 sits at
            # 100. The cut removes that one and keeps all ten.
            if best_gain is not None and best_gain < WINNABLE_CP:
                return None

            # A FORK has to be able to win either of two things. Mohit ruled
            # "unsure" on five fork cards and four were the same shape: two
            # pieces attacked, one of them defended so it was never loseable.
            # Nxe5 hitting an undefended rook on f7 and a knight on d7 guarded
            # three times over is a rook win, not a fork -- and a player told
            # "you missed a fork", shown a position where the second piece was
            # never in danger, trusts the next card less.
            #
            # The detection is NOT deleted: those moves still win material and
            # deserve a caption. It is the word "fork" that is unearned, so
            # they need a plain material-win caption instead. Until that
            # exists they stay out of a queue that is measuring the fork claim.
            #
            # Cost measured before choosing it: 51 claims -> 42 (82% kept).
            if label == "fork":
                winnable = 0
                for name in names:
                    try:
                        sq = chess.parse_square(str(name))
                    except (ValueError, TypeError):
                        continue
                    piece = after.piece_at(sq)
                    if piece is not None and piece.piece_type == chess.KING:
                        winnable += 1          # a king always has to move
                    elif independent_exchange_gain(probe, sq) > 0:
                        winnable += 1
                if winnable < 2:
                    return None
        side, arrow = _orientation_and_arrow(fen, best)
        confidence = _motif_confidence(names, probe, after, board.turn, best_gain)
        return (
            # Provisional review wording only, never served to a player --
            # see the docstring above.
            f"You played {played}. {best} was there instead, and it wins "  # allow-noncentral-caption
            f"material with a {label}.",
            {"fen_before": fen, "fen_after": move.get("fen_after"),
             # The claim is about the move that was AVAILABLE, so the reviewer
             # needs the position it was available in. Showing fen_after would
             # ask them to judge a fork on a board where it no longer exists.
             "review_fen": fen,
             "line_fen": fen,
             "played_san": played, "best_move": best,
             "move_number": move.get("move_number"),
             "cp_loss": move.get("cp_loss"),
             "pv_after_played": list(move.get("pv_after_played") or [])[:8],
             "pv_after_best": list(move.get("pv_after_best") or [])[:8],
             "side_to_move": side,
             "arrow": arrow,
             "arrow_is": f"the {label} that was available",
             "confidence": confidence,
             "quality_id": getattr(bundle, "quality_id", None),
             "detector_facts": [
                 dict(f) for f in getattr(
                     getattr(bundle, "detector", None), "facts", ()) or ()][:4]},
        )

    return produce


def _produce_left_book(move, colour, analysis):
    """Needs the analysis-level opening deviation, not just the move."""
    from services.cognitive_gap_subtypes import _classify_left_book

    context = {"opening_deviation": analysis.get("opening_deviation") or {}}
    subtype, severity = _classify_left_book(move, context)
    if not subtype:
        return None
    detail = (context["opening_deviation"] or {}).get("deviation") or {}
    side, arrow = _orientation_and_arrow(
        move.get("fen_before"), detail.get("expected_san"))
    # Never "the engine". Mohit, on this exact card: "we should never talk
    # about engine, this makes coach less trustable." A coach who cites a
    # computer is quoting an authority instead of teaching, and a 900-rated
    # player cannot argue with it or learn from it. The detector's own third
    # condition IS that the book move and the best move agree -- so the claim
    # can simply be made, without naming who agrees.
    #
    # "Book" also goes: it is club jargon for a 600-1500 audience.
    return (
        # Provisional review wording only, never served to a player -- see
        # _missed_motif's docstring.
        f"{move.get('move')} steps outside what is normally played here. "  # allow-noncentral-caption
        f"{detail.get('expected_san')} is the established move in this position.",
        {"fen_before": move.get("fen_before"), "fen_after": move.get("fen_after"),
         "review_fen": move.get("fen_before"),
         "line_fen": move.get("fen_before"),
         # No board fact decides whether "you left the book" is the right
         # thing to say -- two of the first three sampled were hung knights
         # dressed as theory. This one is always a human question.
         "confidence": CONFIDENCE_UNCERTAIN,
         "played_san": move.get("move"), "book_move": detail.get("expected_san"),
         "best_move": move.get("best_move"),
         "pv_after_played": list(move.get("pv_after_played") or [])[:8],
         "pv_after_best": list(move.get("pv_after_best") or [])[:8],
         "move_number": move.get("move_number"),
         "cp_loss": move.get("cp_loss"), "severity": severity,
         "side_to_move": side, "arrow": arrow,
         "arrow_is": "the book move",
         "opening": detail.get("opening_name")},
    )


# The quality id each producer's detector is graded under. Without this the
# page cannot tell an already-promoted detector from a muted one -- and the
# first version of this queue put `simple_hang` (promoted to CAPTION on
# 2026-08-31 at 96.9% over 260 fires) and `fork` (also CAPTION) at the TOP of
# the list, which would have spent most of a review session re-proving work
# that was already done.
DETECTOR_QUALITY_IDS = {
    "simple_hang": "gap:piece_safety:simple_hang",
    "fork": "tactic:fork_with_stored_payoff",
    "discovered_attack": "tactic:discovered_attack_with_stored_payoff",
    "left_book": "gap:opening_knowledge:left_book_for_a_worse_move",
    "allowed_mate": "gap:king_safety:allowed_mate_exact",
    # Candidate only -- unregistered, so _grade_for reports shadow.
    "tempo_loss": None,
}


# A grade whose evidence we no longer trust. These stay in the queue even at
# caption grade, because the grade rests on something the lock rejects.
#
# simple_hang: its 96.9% comes from 260 events re-checked with a second SEE
# implementation. Both compute the exchange ON THE SQUARE and neither subtracts
# what the move captured, so on a recapture they agree and are both wrong --
# 21.7% of 890 production fires were trades reported as hangs. The defect is
# fixed; the EVIDENCE still measures geometry rather than the player-facing
# claim, which is the distinction the threshold lock draws.
EVIDENCE_UNDER_REVIEW = {
    "simple_hang": (
        "Graded on 260 automated SEE re-checks, which missed that a piece "
        "which just captured is trading, not hanging. Fixed 2026-09-18; "
        "needs 50 human rulings to replace that evidence."
    ),
}


def _grade_for(detector: str) -> str:
    """The grade detector_quality holds today, read live rather than copied."""
    from services.detector_quality import _AUTHORIZATIONS

    quality_id = DETECTOR_QUALITY_IDS.get(detector)
    auth = _AUTHORIZATIONS.get(quality_id) if quality_id else None
    if auth is None:
        return "shadow"   # _UNKNOWN fails closed, and so do we
    return str(getattr(auth.grade, "value", auth.grade))


# ─── tempo loss in the opening (CANDIDATE, docs/tempo_loss_scope.md) ────
#
# Not a registered detector. It exists in this queue only, so Mohit can rule
# on real cards before anything is built -- he asked to see the 290 rather
# than sign off on a number.
#
# The five gates are the scope's, in order. Gate 5 is the one that matters:
# tempo may only speak when nothing simpler does. Measured across 383
# engine-gated candidates: 290 residue, 85 hung pieces, 4 mates, 4 motifs.

HOME_SQUARES = {
    chess.WHITE: (chess.B1, chess.G1, chess.C1, chess.F1, chess.D1),
    chess.BLACK: (chess.B8, chess.G8, chess.C8, chess.F8, chess.D8),
}


def _piece_history(analysis, upto_uci, upto_number):
    """Squares each piece has occupied, replayed from the stored moves.

    Returns (history_by_square, opponent_developments_after) or None.
    """
    moves = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
    history: Dict[int, List[int]] = {}
    for m in moves:
        fen, uci = m.get("fen_before"), m.get("move_uci")
        if not fen or not uci:
            continue
        try:
            board = chess.Board(fen)
            mv = chess.Move.from_uci(uci)
            if mv not in board.legal_moves:
                continue
        except (ValueError, AssertionError):
            continue
        if uci == upto_uci and m.get("move_number") == upto_number:
            return history
        # POP the origin and ASSIGN the destination. The first version used
        # get + setdefault().extend(), which left the history behind on the
        # square a piece had left and then appended it to whatever moved
        # through next -- so a queen that went d1->f3->e4->d3 was reported as
        # "e2 -> g1 -> d1 -> f3 -> e4 -> d3", the first two hops belonging to
        # other pieces entirely. Verified against the real game before fixing.
        #
        # Assigning also discards the captured piece's history on a capture,
        # which is what should happen.
        past = history.pop(mv.from_square, [])
        history[mv.to_square] = past + [mv.from_square]
    return None


def _produce_tempo_loss(move, colour, analysis):
    if move.get("is_opponent_move"):
        return None
    number = move.get("move_number") or 0
    cp_loss = move.get("cp_loss")
    fen, uci = move.get("fen_before"), move.get("move_uci")
    # 1 + 4: opening, and the engine says it actually lost ground.
    if number > 12 or not fen or not uci:
        return None
    if not isinstance(cp_loss, (int, float)) or cp_loss < 100:
        return None
    try:
        board = chess.Board(fen)
        played = chess.Move.from_uci(uci)
        if played not in board.legal_moves:
            return None
    except (ValueError, AssertionError):
        return None
    piece = board.piece_at(played.from_square)
    # 2: a piece that has already moved this game.
    if piece is None or piece.piece_type not in (
            chess.KNIGHT, chess.BISHOP, chess.QUEEN):
        return None
    history = _piece_history(analysis, uci, number)
    if history is None:
        return None
    past = history.get(played.from_square) or []
    if not past:
        return None
    # 3: pieces still sitting at home.
    at_home = [chess.square_name(sq) for sq in HOME_SQUARES[piece.color]
               if board.piece_at(sq) and board.piece_at(sq).color == piece.color]
    if len(at_home) < 2:
        return None

    # 5: nothing simpler explains it.
    from analysis_interpreter import mate_gate_label
    from services.played_hangs_detector import detect_played_hangs

    if mate_gate_label(move.get("mate_info"), colour):
        return None
    if detect_played_hangs(board.copy(), played, cp_loss,
                           mate_in_play=bool(move.get("mate_info"))):
        return None
    best = move.get("best_move")
    if best:
        from services.discovered_attack_puzzle_proof import (
            build_discovered_attack_proof,
        )
        from services.fork_puzzle_proof import build_fork_proof

        for builder in (build_fork_proof, build_discovered_attack_proof):
            try:
                bundle = builder(board.copy(), move.get("move"), best,
                                 move.get("pv_after_best") or [], cp_loss)
            except Exception:  # noqa: BLE001
                bundle = None
            if bundle and getattr(bundle.verifier, "verified", False):
                return None

    # 6: the engine's answer has to be DEVELOPMENT. Added after looking at
    # the first eight cards, because five of them were not tempo lessons at
    # all: the engine wanted the same piece on a better square (Qf5+ -> Qh5+),
    # or the other knight (Ndxf2 -> Ngxf2), or a rook (Bf5 -> Nxh1).
    #
    # Measured over 200 candidates: 51% the engine moves a different
    # already-developed piece, 26% the SAME piece, and only 23% develops or
    # castles. Without this gate three quarters of the queue would be a
    # tempo caption on a move whose lesson is something else entirely.
    if best:
        try:
            best_mv = board.parse_san(str(best))
        except Exception:  # noqa: BLE001
            return None
        if best_mv.from_square == played.from_square:
            return None          # same piece: the lesson is the square
        develops = (best_mv.from_square in HOME_SQUARES[piece.color]
                    or board.is_castling(best_mv))
        if not develops:
            return None
    else:
        return None

    origin = chess.square_name(played.from_square)
    came_from = chess.square_name(past[-1])
    returns = played.to_square in past
    side, arrow = _orientation_and_arrow(fen, move.get("move"))
    piece_word = chess.piece_name(piece.piece_type)

    claim = (
        f"Your {piece_word} was already on {origin} (it came from {came_from}). "  # allow-noncentral-caption
        f"{move.get('move')} moves it again while {len(at_home)} of your pieces "
        f"are still on their starting squares"
        + (f", and it lands back on a square it has already left." if returns
           else ".")
        + f" {best} gets another piece into the game instead."
    )
    return (claim, {
        "review_fen": fen,
        "line_fen": fen,
        "fen_before": fen,
        "fen_after": move.get("fen_after"),
        "played_san": move.get("move"),
        "best_move": best,
        "move_number": number,
        "cp_loss": cp_loss,
        "side_to_move": side,
        "arrow": arrow,
        "arrow_is": "the move played",
        "piece_path": " -> ".join(
            chess.square_name(sq) for sq in past + [played.from_square,
                                                    played.to_square]),
        "still_at_home": ", ".join(at_home),
        "returns_to_a_left_square": returns,
        "pv_after_played": list(move.get("pv_after_played") or [])[:8],
        "pv_after_best": list(move.get("pv_after_best") or [])[:8],
        # Every one of these is a judgement call -- that is the whole point.
        "confidence": CONFIDENCE_UNCERTAIN,
    })


def _producers():
    from services.discovered_attack_puzzle_proof import (
        build_discovered_attack_proof,
    )
    from services.fork_puzzle_proof import build_fork_proof

    return {
        "allowed_mate": _produce_allowed_mate,
        "tempo_loss": _produce_tempo_loss,
        "simple_hang": _produce_simple_hang,
        "left_book": _produce_left_book,
        "fork": _missed_motif(build_fork_proof, "fork"),
        "discovered_attack": _missed_motif(
            build_discovered_attack_proof, "discovered attack"),
    }


async def _fires_for(detector: str, skip_fens: set, limit: int) -> List[Dict[str, Any]]:
    """Walk real games and render what this detector would say."""
    producers = _producers()
    produce = producers.get(detector)
    if produce is None:
        raise HTTPException(
            status_code=400,
            detail=f"unknown detector: {detector}. "
                   f"known: {sorted(producers)}")

    found: List[Dict[str, Any]] = []
    producer_errors: Counter = Counter()
    scanned = 0

    # One query for every game's context instead of one per analysis. The old
    # loop did a find_one per analysis, which is what forced SCAN_LIMIT down to
    # 900 -- and 900 of 15,807 analyses is why the queue told Mohit "done" at
    # 36 of 50 rulings. ~16k small docs is a couple of MB and one round trip.
    games_by_id: Dict[str, Dict[str, Any]] = {}
    async for g in db.games.find(
        {}, {"_id": 0, "game_id": 1, "user_color": 1, "white": 1, "black": 1,
             "platform": 1, "result": 1, "played_at": 1, "date": 1},
    ):
        games_by_id[g.get("game_id")] = g

    cursor = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations.0": {"$exists": True}},
        {"_id": 0, "game_id": 1, "user_id": 1, "opening_deviation": 1,
         "stockfish_analysis.move_evaluations": 1},
    )
    async for analysis in cursor:
        scanned += 1
        if scanned > SCAN_LIMIT or len(found) >= limit:
            break
        game = games_by_id.get(analysis.get("game_id"))
        colour = (game or {}).get("user_color") or "white"
        # Mohit chose full game context for the reviewing coach (2026-09-18):
        # usernames, platform and result travel with every claim. No email --
        # the coach judges the claim, and the account holder is never the
        # question being asked.
        context = {
            "white": (game or {}).get("white"),
            "black": (game or {}).get("black"),
            "platform": (game or {}).get("platform"),
            "result": (game or {}).get("result"),
            "played_at": str((game or {}).get("played_at")
                             or (game or {}).get("date") or "") or None,
            "user_color": colour,
        }
        for move in (analysis.get("stockfish_analysis") or {}).get(
                "move_evaluations") or []:
            if move.get("is_opponent_move"):
                continue
            try:
                produced = produce(move, colour, analysis)
            except Exception as exc:  # noqa: BLE001
                # One malformed stored move must not empty the whole queue --
                # but a bug in a producer must not hide behind that. A stray
                # NameError here silently returned ZERO claims for a detector
                # and read exactly like "the gate filtered everything".
                producer_errors[type(exc).__name__] += 1
                if producer_errors[type(exc).__name__] == 1:
                    logger.warning(
                        "[detector-review] %s producer raised %s: %s",
                        detector, type(exc).__name__, exc, exc_info=True)
                continue
            if not produced:
                continue
            claim, evidence = produced
            key = f"{detector}:{analysis.get('game_id')}:{evidence.get('move_number')}"
            if key in skip_fens:
                continue
            found.append({
                "claim_key": key,
                "detector": detector,
                "game_id": analysis.get("game_id"),
                "claim": claim,
                "evidence": evidence,
                "game": context,
            })
            if len(found) >= limit:
                break
    if producer_errors:
        logger.warning("[detector-review] %s producer errors: %s",
                       detector, dict(producer_errors))

    # Least certain first. The board already settled the confident ones, and
    # spending a reviewer on those is spending them on the answer we have.
    # This is a REORDER, not a filter: every claim still reaches the queue,
    # and a "certain" claim is still only board-verified, which the threshold
    # lock says does not promote anything by itself.
    found.sort(key=lambda c: _CONFIDENCE_RANK.get(
        (c.get("evidence") or {}).get("confidence"), 0))
    return found


@router.get("/admin/detector-review/next")
async def next_claim(
    detector: str = Query(default="allowed_mate"),
    user: User = Depends(require_admin),
):
    """One unjudged claim, or 404 when the queue is clear."""
    ruled = set(await db[COLLECTION].distinct(
        "claim_key", {"detector": detector}))
    found = await _fires_for(detector, ruled, limit=1)
    if not found:
        raise HTTPException(
            status_code=404,
            detail="No unjudged claims found in the scan window")
    return found[0]


@router.get("/admin/detector-review/batch")
async def batch_claims(
    detector: str = Query(default="allowed_mate"),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(require_admin),
):
    """Several at once — reading fifty claims in ten minutes is the point."""
    ruled = set(await db[COLLECTION].distinct(
        "claim_key", {"detector": detector}))
    claims = await _fires_for(detector, ruled, limit)
    buckets = Counter(
        (c.get("evidence") or {}).get("confidence") or "uncertain"
        for c in claims)
    return {
        "detector": detector,
        "claims": claims,
        # So the page can say what it is asking for: the ones the board could
        # not settle, not everything it found.
        "confidence_split": dict(buckets),
        # So the page can say "searched N games" rather than implying the work
        # is over when the scan window simply ended.
        "scanned_analyses": min(SCAN_LIMIT, await db.game_analyses.count_documents(
            {"stockfish_analysis.move_evaluations.0": {"$exists": True}})),
        "already_ruled": len(ruled),
    }


@router.post("/admin/detector-review")
async def rule_claim(
    payload: Dict = Body(...),
    user: User = Depends(require_admin),
):
    """Record a verdict. It does not promote anything; see the module docstring."""
    claim_key = str(payload.get("claim_key") or "").strip()
    detector = str(payload.get("detector") or "").strip()
    verdict = str(payload.get("verdict") or "").strip().lower()
    if not claim_key or not detector:
        raise HTTPException(status_code=400, detail="claim_key and detector required")
    if verdict not in VERDICTS:
        raise HTTPException(
            status_code=400, detail=f"verdict must be one of {sorted(VERDICTS)}")

    await db[COLLECTION].update_one(
        {"claim_key": claim_key, "detector": detector},
        {"$set": {
            "verdict": verdict,
            "note": str(payload.get("note") or "")[:500],
            "claim": str(payload.get("claim") or "")[:500],
            "ruled_by": user.email,
            # The login is shared with a reviewing coach by Mohit's choice, so
            # `ruled_by` alone cannot tell two reviewers apart. This is not
            # access control -- it is so the promotion packet can say who
            # judged what, and so one reviewer's calls can be re-examined
            # without discarding the other's.
            "reviewer_name": str(payload.get("reviewer_name") or "").strip()[:80]
                             or None,
            "ruled_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return {"recorded": True, "claim_key": claim_key, "verdict": verdict}


@router.get("/admin/detector-review/results")
async def review_results(user: User = Depends(require_admin)):
    """Tallies, plus every claim ruled false — those are the bug reports."""
    rows = await db[COLLECTION].find({}, {"_id": 0}).to_list(length=None)
    by_detector: Dict[str, Counter] = {}
    for row in rows:
        by_detector.setdefault(row.get("detector"), Counter())[
            row.get("verdict")] += 1

    by_reviewer: Counter = Counter()
    for row in rows:
        by_reviewer[row.get("reviewer_name") or row.get("ruled_by") or "?"] += 1

    # Every known detector gets a row, including the ones with no rulings yet.
    # Without this the page cannot show "0 of 50" for the untouched ones, and a
    # reviewer has no way to see what is left to do -- which is what made the
    # first version of this page unreadable.
    for known in _producers():
        by_detector.setdefault(known, Counter())

    summary = {}
    for detector, counts in by_detector.items():
        judged = counts["true"] + counts["false"]
        summary[detector] = {
            "true": counts["true"],
            "false": counts["false"],
            "unsure": counts["unsure"],
            # The number a promotion packet needs. Unsure is excluded from the
            # denominator on purpose: it is a reviewer abstention, not evidence
            # either way.
            "precision": round(100 * counts["true"] / judged, 1) if judged else None,
            "judged": judged,
            # docs/detector_quality_threshold_lock_2026_08_27.md
            "caption_bar": {"fires": 50, "precision": 95},
            "plan_bar": {"fires": 200, "precision": 95, "recall": 60},
            # Said plainly, so the page never has to work it out itself.
            "remaining": max(0, 50 - judged),
            "grade": _grade_for(detector),
            # Caption and plan grades already clear the bar this queue builds
            # toward, so more caption-grade rulings on them buy nothing --
            # UNLESS the evidence behind the grade is known to be unsound.
            "already_promoted": (
                _grade_for(detector) in ("caption", "plan")
                and detector not in EVIDENCE_UNDER_REVIEW
            ),
            "evidence_note": EVIDENCE_UNDER_REVIEW.get(detector),
            "on_track": (
                None if judged < 5
                else (100 * counts["true"] / judged) >= 95
            ),
        }
    return {
        "summary": summary,
        "by_reviewer": dict(by_reviewer),
        "wrong_claims": [
            {k: r.get(k) for k in ("detector", "claim", "note", "claim_key")}
            for r in rows if r.get("verdict") == "false"
        ],
        "total_ruled": len(rows),
    }
