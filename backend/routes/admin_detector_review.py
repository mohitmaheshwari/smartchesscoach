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

from services.caption_facts import PIECE_VALUE_CP
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


def _allowed_mate_caption(move, evidence, colour):
    """Say what the threat WAS and what would have met it, not just the finish.

    "dxc5 allows mate in one. The finish is Qxh2#." is a true sentence that
    teaches nothing -- Mohit, 2026-09-19: "how you should have saved it, or
    something better, coachable."

    The teachable fact is in the data already: on 3 of 4 sampled cards the
    mating piece was ALREADY aiming at the mating square before the move was
    played. That is not "you allowed mate", it is "the threat was standing
    there and you looked somewhere else" -- which is a habit a player can fix.

    Every clause below is checked on the board: which piece mates, from where,
    whether it was aiming there beforehand, whether the best move defends that
    square, moves the king, or blocks the line.
    """
    line = list(evidence.get("mating_line") or [])
    fen_after, fen_before = evidence.get("fen_after"), evidence.get("fen_before")
    played, best = evidence.get("played_san"), move.get("best_move")
    if not line or not fen_after or not fen_before or not played:
        return None
    # The MATING move is the last one in the line, not the first. A line like
    # "Bb7 Nxd4 Qh1#" is a mate in three, and describing Bb7 as the mate
    # reported the wrong piece on the wrong square -- caught by reading the
    # rendered cards rather than the code.
    try:
        after = chess.Board(str(fen_after))
        before = chess.Board(str(fen_before))
        board = after.copy(stack=False)
        mating = None
        for index, san in enumerate(line):
            mv = board.parse_san(str(san))
            if index == len(line) - 1 or board.gives_check(mv):
                probe = board.copy(stack=False)
                probe.push(mv)
                if probe.is_checkmate():
                    mating = mv
                    mating_board = board.copy(stack=False)
                    break
            board.push(mv)
        if mating is None:
            return None
    except Exception:  # noqa: BLE001
        return None
    piece = mating_board.piece_at(mating.from_square)
    if piece is None:
        return None
    plies = len(line)
    mate_sq = chess.square_name(mating.to_square)
    from_sq = chess.square_name(mating.from_square)
    # A pawn that mates by promoting is not a pawn on that square -- "f1=Q#
    # finishing with their pawn on f1" describes a piece that no longer exists
    # by the time it gives mate.
    piece_word = chess.piece_name(mating.promotion if mating.promotion
                                  else piece.piece_type)

    # Was the threat already standing before the move? Only meaningful for a
    # mate in one -- in a longer line the mating piece may not even be there
    # yet when the move is played.
    standing = (plies == 1
                and before.piece_at(mating.from_square) is not None
                and mating.to_square in before.attacks(mating.from_square))

    # A mate is rarely one piece. Mohit, 2026-09-19, on dxc5 / Qxh2#: "Queen
    # and knight are attacking and your king gets checkmated" -- the caption
    # named only the queen, and the knight on g4 is why Kxh2 is illegal. Name
    # everything of theirs that bears on the mating square, because the PAIR
    # is the pattern a player can learn to spot; the queen alone is not.
    mated = mating_board.copy(stack=False)
    mated.push(mating)
    supporters = []
    for sq in mated.attackers(piece.color, mating.to_square):
        if sq == mating.to_square:
            continue
        sup = mated.piece_at(sq)
        if sup is None or sup.piece_type == chess.KING:
            continue
        supporters.append((chess.piece_name(sup.piece_type), chess.square_name(sq)))
    supporters.sort()

    mate_word = "mate in one" if plies <= 1 else f"mate in {(plies + 1) // 2}"

    # "beside your king" has to be TRUE, not decorative. A back-rank mate --
    # Qc8# with the king on e8 -- is two files away, and the caption claimed
    # it was adjacent. Found by reading rendered cards, not the code.
    mated_king = mated.king(not piece.color)
    adjacent = (mated_king is not None
                and chess.square_distance(mated_king, mating.to_square) <= 1)
    beside = ", next to your king" if adjacent else ""
    named_pair = False

    # Mohit, 2026-09-19: "don't tell something the board is already showing,
    # that's the purpose of captions." The pieces, their squares and the lines
    # they point down are DRAWN (extra_arrows in _produce_allowed_mate).
    # Naming them again in words spends the reader's attention on the one
    # thing they can already see. What the board cannot show is that it is
    # mate, why the save works, and the habit -- so that is what is left.
    ring = _escape_ring(evidence)
    try:
        played_mv_obj = before.parse_san(str(played))
    except Exception:  # noqa: BLE001
        played_mv_obj = None

    # "Give your king air" is only advice for a king that has ALREADY castled.
    # On a card where the king is still on e8 with the queen and bishop hitting
    # f7, the lesson is CASTLE, and telling the player to make luft is teaching
    # them the wrong habit. Caught by reading the rendered corpus.
    home_rank = 0 if mated_king is not None and not piece.color else 7
    on_home_rank = (mated_king is not None
                    and chess.square_rank(mated_king) == home_rank)
    king_file = chess.square_file(mated_king) if mated_king is not None else 4
    castled = on_home_rank and king_file in (1, 2, 6, 7)
    uncastled_centre = on_home_rank and king_file in (3, 4)

    boxed_in = bool(ring and len(ring["own"]) >= 2 and castled)
    centre_king = bool(uncastled_centre and supporters)

    if centre_king:
        named_pair = True
        threat = (f"Your king was still in the middle when you played "
                  f"{played}, with two of their pieces already aimed at "
                  f"{mate_sq} -- {mate_word}.")
    elif boxed_in:
        # The real lesson. Two attackers converging is only mate because the
        # king had nowhere to run -- and here his OWN pieces took the exits.
        # The circles say which squares; the words say whose fault they were.
        named_pair = True
        threat = (f"Your king had nowhere to go -- your own pieces were "
                  f"sitting on {len(ring['own'])} of the squares it needed. "
                  f"That is why {played} was {mate_word}.")
    elif standing and supporters:
        named_pair = True
        threat = (f"Two of their pieces were already aimed at {mate_sq} when "
                  f"you played {played} -- {mate_word}.")
    elif standing:
        threat = (f"Their {piece_word} was already aiming at {mate_sq} when "
                  f"you played {played} -- {mate_word}.")
    elif plies == 1:
        threat = (f"{played} lets their {piece_word} reach {mate_sq}{beside} "
                  f"-- {mate_word}.")
    else:
        threat = f"{played} runs into {mate_word}, ending on {mate_sq}."

    # What the save DOES, established rather than asserted. The old version
    # said "h3 covers h2 instead" because attackers(h2) was non-empty -- but
    # that was the KING, which already covered it. h3 works by blocking the
    # file. Each branch below is a distinct, checkable mechanism, tried in the
    # order a player would think of them.
    save = ""
    if best:
        try:
            probe = before.copy(stack=False)
            best_mv = probe.parse_san(str(best))
            moved = probe.piece_at(best_mv.from_square)
            defenders_before = len(before.attackers(before.turn, mating.to_square))
            # is_castling() must be asked of the board BEFORE the push, or it
            # is always False and every castle reads as an ordinary king step.
            best_is_castle = probe.is_castling(best_mv)
            probe.push(best_mv)

            ray = set()
            if plies == 1:
                try:
                    ray = set(chess.SquareSet.between(mating.from_square,
                                                      mating.to_square))
                except Exception:  # noqa: BLE001
                    ray = set()

            if moved is not None and moved.piece_type == chess.KING:
                # NOT "off that square" -- the king is never standing on the
                # square it gets mated on. It is mated NEXT to it.
                save = (f"{best} tucks your king away from it."
                        if best_is_castle
                        else f"{best} steps your king out of it.")
            elif best_mv.to_square == mating.from_square:
                save = f"{best} takes the {piece_word} before it gets there."
            elif best_mv.to_square in ray:
                line_word = "file"
                if chess.square_file(mating.from_square) != chess.square_file(mating.to_square):
                    line_word = ("rank" if chess.square_rank(mating.from_square)
                                 == chess.square_rank(mating.to_square) else "diagonal")
                save = (f"{best} blocks the {line_word}, so the {piece_word} "
                        f"can never reach {mate_sq}.")
            elif any(best_mv.to_square == sq for _, sq in
                     [(w, chess.parse_square(q)) for w, q in supporters]):
                save = f"{best} takes the piece that was guarding {mate_sq}."
            elif len(probe.attackers(before.turn, mating.to_square)) > defenders_before:
                save = f"{best} puts another defender on {mate_sq}."
            else:
                save = f"{best} was the move."
        except Exception:  # noqa: BLE001
            save = f"{best} was the move."

    # Mohit, 2026-09-19: "caption should only and only provide teaching ...
    # principles that you don't forget." Everything positional is drawn -- the
    # attackers in yellow, the squares the king cannot use as red circles, the
    # save in green. What is left for words is the rule, plus the shortest
    # possible link saying which habit it is about.
    rule = _mate_rule(before, played_mv_obj, ring, castled, uncastled_centre,
                      standing, bool(supporters))
    # The only fact worth a word: that it is mate, and in how many. Which
    # pieces, which squares, which exits were shut -- all drawn.
    caption = f"{played} was {mate_word}. {rule}"
    if len(caption.split()) > 60:
        caption = rule
    return caption


def _capture_net_cp(board_before, played_mv):
    """What the capture actually NETS, not merely that it was a capture.

    Mohit, 2026-09-19: "are you sure that position was this, never write
    something bad or wrong." He was right. The rule fired on is_capture(),
    which says a piece was taken and nothing about whether anything was won.
    Measured over every allowed_mate capture in 300 analyses: 5 of 13 win a
    piece, 6 win only a pawn, and 2 LOSE material -- including Rxb7 at -400,
    which had been captioned "when you are about to win a piece" while the
    player was hanging a rook.
    """
    if played_mv is None or not board_before.is_capture(played_mv):
        return None
    victim = board_before.piece_at(played_mv.to_square)
    took = PIECE_VALUE_CP.get(victim.piece_type, 100) if victim else 100
    after = board_before.copy(stack=False)
    after.push(played_mv)
    try:
        from services.legal_exchange_verifier import independent_exchange_gain
        return took - independent_exchange_gain(after, played_mv.to_square)
    except Exception:  # noqa: BLE001
        return None


def _mate_rule(board_before, played_mv, ring, castled, centre, standing, pair):
    """The one sentence the player should still have next month.

    The board already shows what happened. The caption's whole job is the
    portable rule -- but a rule is only teaching if THIS position earned it.
    A bank of generic principles ("develop your pieces") reads like coaching
    and is filler, which is why each rule below is selected by a board fact
    and never appended to everything.

    Most-specific first: the most useful rule is the one about the mistake
    they actually made.
    """
    net = _capture_net_cp(board_before, played_mv)
    # Only say "winning a piece" when a piece is actually being won. A capture
    # that nets a pawn gets the pawn sentence; one that loses material is not
    # about greed at all, so it falls through to the king rules below.
    if net is not None and net >= 200:
        return "When you are about to win a piece, check your own king first."
    if net is not None and 0 < net < 200:
        return "A free pawn is never worth a turn spent away from your king."
    if centre and pair:
        return "Castle before they get two pieces pointing at your king."
    if castled and ring and len(ring.get("own") or []) >= 2:
        return "Give your king a square to run to before it needs one."
    if standing:
        return "Look at what is already aimed at your king before you move."
    return "Look for attacks on your king before anything else."


def _escape_ring(evidence):
    """Which squares the mated king could not use, and why.

    Mohit, 2026-09-19: "mate is when the king has no escape square, right?"
    The card was drawing the two attackers converging and never the thing that
    actually makes it mate -- that the king has nowhere to go. On his dxc5 /
    Qxh2# card THREE of the five squares are blocked by White's own rook and
    pawns; the queen only had to touch h2.

    Uses services.escape_squares_service, which already owns this calculation
    for the escape-squares quiz. Not reimplemented here.
    """
    try:
        from services.escape_squares_service import count_king_escape_squares
        board = chess.Board(str(evidence.get("fen_after") or ""))
        for san in list(evidence.get("mating_line") or []):
            mv = board.parse_san(str(san))
            probe = board.copy(stack=False)
            probe.push(mv)
            if probe.is_checkmate():
                loser = "white" if probe.turn == chess.WHITE else "black"
                info = count_king_escape_squares(probe.fen(), loser)
                blocked = list(info.get("blocked_squares") or [])
                return {
                    "squares": [b["square"] for b in blocked],
                    "own": [b["square"] for b in blocked
                            if b.get("reason") == "own_piece"],
                    "covered": [b["square"] for b in blocked
                                if b.get("reason") != "own_piece"],
                }
            board.push(mv)
    except Exception:  # noqa: BLE001
        return None
    return None


def _mate_arrows(evidence):
    """Draw every piece of theirs that bears on the mating square.

    This is the geometry the caption used to spend thirty words listing. The
    card drew only the move played, so the mate itself -- the thing the card
    is about -- was invisible, and the words had to carry it. Drawn, they do
    not.
    """
    arrows = []
    try:
        board = chess.Board(str(evidence.get("fen_after") or ""))
        for san in list(evidence.get("mating_line") or []):
            mv = board.parse_san(str(san))
            probe = board.copy(stack=False)
            probe.push(mv)
            if probe.is_checkmate():
                mover = board.turn
                sq = mv.to_square
                arrows.append([chess.square_name(mv.from_square),
                               chess.square_name(sq), "yellow"])
                for att in probe.attackers(mover, sq):
                    if att == sq:
                        continue
                    pc = probe.piece_at(att)
                    if pc is None or pc.piece_type == chess.KING:
                        continue
                    arrows.append([chess.square_name(att),
                                   chess.square_name(sq), "yellow"])
                break
            board.push(mv)
    except Exception:  # noqa: BLE001
        return []
    return arrows


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
        "extra_arrows": _mate_arrows(evidence)[:4],
        "extra_arrows_is": "what is aiming at the mating square",
        "highlight": ((_escape_ring(evidence) or {}).get("squares") or [])[:8],
        "highlight_is": "every square the king cannot use",
        "line_fen": fen,
        # The mate IS the punishment line, so it steps like any other.
        "pv_after_played": list(evidence.get("mating_line") or [])[:8],
        "best_move": move.get("best_move"),
        "pv_after_best": list(move.get("pv_after_best") or [])[:8],
    })
    coachable = _allowed_mate_caption(move, evidence, colour)
    return (coachable or render_claim(evidence), evidence)


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
        # Does the opponent's OWN continuation actually take the piece?
        #
        # Mohit's d6 card: SEE on the square says +300, and the engine's
        # fourth-choice Qxd6 scores +14 against Rb1 at +112, because Qxd6 is
        # answered by Qxa1 on the far side of the board. A piece you can take
        # but should not is not hanging, and no square-level test can see the
        # refutation.
        #
        # Measured on 506 fires: the opponent takes it immediately in 74.7%,
        # never in 19.8%, later in 5.5%. "Never" is NOT proof the claim is
        # false -- they may simply have something better -- so this does not
        # suppress. It routes the claim to a person, which is what confidence
        # is for.
        takes_it = None
        try:
            probe = chess.Board(str(move.get("fen_after") or ""))
            for index, san in enumerate(list(move.get("pv_after_played") or [])[:4]):
                nxt = probe.parse_san(str(san))
                if nxt.to_square == sq and probe.is_capture(nxt):
                    takes_it = index + 1
                    break
                probe.push(nxt)
        except Exception:  # noqa: BLE001
            takes_it = None

        if takes_it == 1 and gain >= 300:
            confidence = CONFIDENCE_CERTAIN
        elif takes_it is None and move.get("pv_after_played"):
            # They had the chance and passed. Worth a human look.
            confidence = CONFIDENCE_UNCERTAIN
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


def _discovered_attack_caption(board, best_move, facts):
    """A caption a 1200 can act on, built only from board facts.

    The old one -- "Nxf3+ was there instead, and it wins material with a
    discovered attack" -- named the motif and explained nothing. A player who
    did not already know what a discovered attack is learns nothing, and one
    who does still cannot see WHICH piece was blocking WHAT.

    So: name the geometry (your own piece stands in front of your queen), name
    what it uncovers, say whether the target is defended, and end on the scan
    that transfers. The motif's name goes last, as a label for a thing they
    have just been shown -- not as an explanation in itself.
    """
    try:
        mv = board.parse_san(str(best_move))
    except Exception:  # noqa: BLE001
        return None
    attacker_sq = str(facts.get("discovered_attacker_square") or "")
    target_sq = str(facts.get("target_square") or "")
    if not attacker_sq or not target_sq:
        return None
    blocker = board.piece_at(mv.from_square)
    attacker = facts.get("discovered_attacker_piece_type")
    target = facts.get("target_piece_type")
    if blocker is None or not attacker or not target:
        return None

    after = board.copy(stack=False)
    after.push(mv)
    undefended = not after.attackers(not board.turn, chess.parse_square(target_sq))
    gives_check = after.is_check()

    # Under the 60-word cap in caption_config.json. The first draft ran 70-76
    # and would have been cut at a sentence boundary with no ellipsis -- which
    # eats the LAST sentence, and the last sentence is the principle. The
    # thing worth keeping would have disappeared silently.
    blocker_word = chess.piece_name(blocker.piece_type)
    lead = (f"Your own {blocker_word} on {chess.square_name(mv.from_square)} "
            f"stands in front of your {attacker} on {attacker_sq}.")
    middle = (f"{best_move} moves it away"
              + (" with check" if gives_check else "")
              + f", and the {attacker} then looks straight at the "
                f"{target} on {target_sq}"
              + (" — which nothing defends." if undefended else "."))
    principle = ("When your own piece blocks your queen, rook or bishop, "
                 "look at what sits at the far end of that line. "
                 "That is a discovered attack.")
    caption = f"{lead} {middle} {principle}"
    if len(caption.split()) > 60:      # never ship one the renderer would cut
        caption = f"{lead} {middle}"
    return caption


def _fork_caption(board, best_move, facts):
    """Same shape as the discovered-attack caption: geometry, then the scan.

    The old one -- "it wins material with a fork" -- named the motif and left
    the player to find it. Which two pieces? Why can they not both escape?
    Those are the lesson and they are both board facts.
    """
    try:
        mv = board.parse_san(str(best_move))
    except Exception:  # noqa: BLE001
        return None
    squares = [str(t) for t in (facts.get("targets") or [])]
    if len(squares) < 2:
        return None
    after = board.copy(stack=False)
    after.push(mv)

    hits = []
    for name in squares:
        try:
            sq = chess.parse_square(name)
        except (ValueError, TypeError):
            continue
        piece = after.piece_at(sq)
        if piece is None:
            continue
        hits.append((chess.piece_name(piece.piece_type), name,
                     piece.piece_type == chess.KING))
    if len(hits) < 2:
        return None

    forker = board.piece_at(mv.from_square)
    forker_word = chess.piece_name(forker.piece_type) if forker else "piece"
    king = next((h for h in hits if h[2]), None)
    other = next((h for h in hits if not h[2]), None)

    if king and other:
        # The forcing case: the king has to move, so the other one falls.
        lead = (f"{best_move} hits their king on {king[1]} and the "
                f"{other[0]} on {other[1]} at the same time.")
        middle = f"The king has to move, and then the {other[0]} drops."
        principle = (f"When a {forker_word} lands near their king, check what "
                     f"else it reaches from that square.")
    else:
        a, b_ = hits[0], hits[1]
        lead = (f"{best_move} attacks the {a[0]} on {a[1]} and the "
                f"{b_[0]} on {b_[1]} at once.")
        middle = "Only one of them can get out of the way."
        principle = ("Before you move, look for a square that touches two of "
                     "their pieces at the same time.")
    caption = f"{lead} {middle} {principle}"
    if len(caption.split()) > 60:
        caption = f"{lead} {middle}"
    return caption


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
        coachable = None
        if label == "discovered attack":
            coachable = _discovered_attack_caption(board.copy(), best, head)
        elif label == "fork":
            coachable = _fork_caption(board.copy(), best, head)
        if coachable:
            # The caption says "the queen then looks straight at the rook on
            # a1". Until now the board drew the two MOVES and never that line,
            # so the one thing the lesson is about was invisible. Yellow is
            # the coach's-point brush per docs/coach_geometry_arrows_scope.md.
            discovered_line = None
            extra = []
            try:
                a_sq = str(head.get("discovered_attacker_square") or "")
                t_sq = str(head.get("target_square") or "")
                if a_sq and t_sq:
                    discovered_line = [a_sq, t_sq, "yellow"]
                    extra = [discovered_line]
                elif head.get("targets"):
                    # A fork: draw the landing square onto BOTH targets, which
                    # is the whole point and was previously invisible.
                    landing = chess.square_name(
                        board.parse_san(str(best)).to_square)
                    extra = [[landing, str(t), "yellow"]
                             for t in head["targets"]][:3]
            except Exception:  # noqa: BLE001
                discovered_line = None
                extra = []
            return (coachable, {
                "review_fen": fen, "line_fen": fen,
                "fen_before": fen, "fen_after": move.get("fen_after"),
                "played_san": played, "best_move": best,
                "move_number": move.get("move_number"),
                "cp_loss": move.get("cp_loss"),
                "pv_after_played": list(move.get("pv_after_played") or [])[:8],
                "pv_after_best": list(move.get("pv_after_best") or [])[:8],
                "side_to_move": side, "arrow": arrow,
                "arrow_is": f"the {label} that was available",
                "extra_arrows": extra,
                "extra_arrows_is": (
                    (f"the line it opens: your "
                     f"{head.get('discovered_attacker_piece_type')} onto the "
                     f"{head.get('target_piece_type')}")
                    if discovered_line
                    else ("what the move hits — both at once" if extra else None)
                ),
                "confidence": confidence,
                "quality_id": getattr(bundle, "quality_id", None),
                "detector_facts": [dict(f) for f in facts][:4],
            })
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
