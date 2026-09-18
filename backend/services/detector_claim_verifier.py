"""Refute detector claims that are provably false, before a human reads them.

Mohit, 2026-09-18: "to make the process faster, can we use codex higher models
to approve some of these?"

No — and the threshold lock says why in its own words. Under **Rejected
shortcuts** it lists "implementation-to-implementation agreement: duplicated
logic can agree and still be wrong", and it names who may adjudicate:
"human/tablebase/board-verifier adjudication is required before promotion."

The fork detector is the proof. It agreed with human-curated Lichess puzzle
themes on 99.6% and 99.7% of two 1,000-puzzle samples — better evidence than a
model would produce — and stayed in Shadow, because a 1,000-puzzle negative
control still produced 304 fires (30.4%) on checks that happened to hit a
second piece. Whether that is a fork worth teaching or an incidental
check-plus-target is a causal question. A model answers it confidently and we
have no way to tell a right confident answer from a wrong one.

So this module does the half that IS mechanical, and refuses the half that is
not. Two rules it never breaks:

1. **It can refute. It can never approve.** `REFUTED` removes a claim from the
   queue; everything else leaves it for a person. There is no verdict here
   that counts toward the 50 reviewed fires.
2. **It never reorders.** The lock requires corpus order so easy cases cannot
   float to the top. This filters; it does not rank.

Model chess strength is irrelevant to every check below — they are python-chess
and the stored engine line doing the work. That is the point: a better-reasoning
model would not compute a static exchange more accurately, and the one place
better chess reasoning WOULD help is the causal question the lock forbids it
from settling.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

import chess

# What a check concluded.
REFUTED = "refuted"          # provably false — drop it, and it is a bug report
STANDS = "stands"            # the mechanical part holds; a human still decides
UNDECIDABLE = "undecidable"  # we cannot settle it here; a human still decides


@dataclass(frozen=True)
class Verdict:
    status: str
    reason: str

    @property
    def is_refuted(self) -> bool:
        return self.status == REFUTED


def _board(fen: object) -> Optional[chess.Board]:
    try:
        return chess.Board(str(fen or ""))
    except (ValueError, AssertionError):
        return None


def _parse(board: chess.Board, san_or_uci: object) -> Optional[chess.Move]:
    text = str(san_or_uci or "").strip()
    if not text:
        return None
    try:
        move = chess.Move.from_uci(text.lower())
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    try:
        return board.parse_san(text)
    except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError,
            chess.AmbiguousMoveError):
        return None


# ─── simple_hang ────────────────────────────────────────────────────────
# Claim: "after X, your <piece> on <square> is hanging."
# Mechanical: is that piece actually losing material on that square?

def _verify_simple_hang(e: Mapping[str, Any]) -> Verdict:
    from services.legal_exchange_verifier import independent_exchange_gain

    board = _board(e.get("fen_after") or e.get("review_fen"))
    square_name = str(e.get("hung_square") or "")
    if board is None or not square_name:
        return Verdict(UNDECIDABLE, "no position or no named square")
    try:
        square = chess.parse_square(square_name)
    except ValueError:
        return Verdict(REFUTED, f"{square_name} is not a square")

    piece = board.piece_at(square)
    if piece is None:
        return Verdict(REFUTED, f"nothing stands on {square_name}")
    # The claim is about the PLAYER's piece, so the opponent must be to move
    # and the piece must belong to the other side.
    if piece.color == board.turn:
        return Verdict(REFUTED,
                       f"the piece on {square_name} belongs to the side to move")
    named = str(e.get("hung_piece") or "").lower()
    actual = chess.piece_name(piece.piece_type)
    if named and named != actual:
        return Verdict(REFUTED, f"claimed a {named} on {square_name}, found a {actual}")

    # Does taking it actually win material for the opponent?
    gain = independent_exchange_gain(board, square)
    if gain <= 0:
        return Verdict(REFUTED,
                       f"the exchange on {square_name} nets {gain}cp for the "
                       "opponent, so it is not hanging")
    return Verdict(STANDS, f"taking on {square_name} wins {gain}cp")


# ─── allowed_mate ───────────────────────────────────────────────────────
# Claim: "X allows mate in N. The finish is <line>."
# Mechanical: replay the line and assert the board is actually checkmated.

def _verify_allowed_mate(e: Mapping[str, Any]) -> Verdict:
    from services.allowed_mate_detector import _plies_to_mate

    fen_after = e.get("fen_after")
    line: Sequence[str] = e.get("mating_line") or []
    if not fen_after or not line:
        return Verdict(UNDECIDABLE, "no stored continuation to replay")
    plies = _plies_to_mate(str(fen_after), list(line))
    if plies is None:
        # A truncated or unplayable line is not evidence of safety, so this is
        # explicitly NOT a refutation.
        return Verdict(UNDECIDABLE, "the stored line does not reach mate on the board")
    claimed = e.get("plies_to_mate")
    if isinstance(claimed, int) and claimed != plies:
        return Verdict(REFUTED,
                       f"claimed mate in {claimed} plies, the line mates in {plies}")
    return Verdict(STANDS, f"replayed to checkmate in {plies} plies")


# ─── left_book ──────────────────────────────────────────────────────────
# Claim: "you left the book; <book_move> is the move and also the engine's."
# Mechanical: is the named book move legal here, and is it the stored best?

def _verify_left_book(e: Mapping[str, Any]) -> Verdict:
    board = _board(e.get("review_fen") or e.get("fen_before"))
    if board is None:
        return Verdict(UNDECIDABLE, "no position")
    book = str(e.get("book_move") or "")
    if not book:
        return Verdict(REFUTED, "the claim names no book move")
    if _parse(board, book) is None:
        return Verdict(REFUTED, f"{book} is not legal in this position")

    played = str(e.get("played_san") or "")
    if played and _bare(played) == _bare(book):
        return Verdict(REFUTED, "they played the book move, so they did not leave it")

    best = str(e.get("best_move") or "")
    if best and _bare(best) != _bare(book):
        return Verdict(REFUTED,
                       f"the claim says the book move is also the engine's, but "
                       f"the engine plays {best} and the book plays {book}")
    return Verdict(STANDS, f"{book} is legal, is the engine's move, and was not played")


def _bare(san: object) -> str:
    return str(san or "").replace("+", "").replace("#", "").strip()


# ─── fork / discovered attack ───────────────────────────────────────────
# Claim: "<best> was there instead, and it wins material with a <motif>."
#
# The geometry is mechanical. The CAUSAL question -- is this a fork worth
# teaching, or a check that happens to hit a second piece -- is the one the
# lock reserves for a human, and the negative control puts it at 30.4% of
# fires. So these can only ever be refuted on geometry, never upheld.

def _verify_missed_motif(e: Mapping[str, Any], motif: str) -> Verdict:
    board = _board(e.get("review_fen") or e.get("fen_before"))
    if board is None:
        return Verdict(UNDECIDABLE, "no position")
    best = _parse(board, e.get("best_move"))
    if best is None:
        return Verdict(REFUTED, f"{e.get('best_move')} is not legal in this position")
    played = _parse(board, e.get("played_san"))
    if played is not None and played == best:
        return Verdict(REFUTED, "they played the move the claim says they missed")

    mover = board.turn
    after = board.copy(stack=False)
    after.push(best)

    if motif == "fork":
        targets = [
            sq for sq in after.attacks(best.to_square)
            if (p := after.piece_at(sq)) and p.color != mover
        ]
        if len(targets) < 2 and not after.is_check():
            return Verdict(REFUTED,
                           f"the move attacks {len(targets)} piece(s) and gives no "
                           "check, so there is no fork")
        return Verdict(UNDECIDABLE,
                       f"attacks {len(targets)} piece(s); whether that is a fork "
                       "worth teaching or an incidental check is the human call")

    # discovered attack: some OTHER friendly piece must now attack something
    # it was not attacking before.
    def seen(b: chess.Board, exclude: int) -> set:
        out = set()
        for sq in chess.SQUARES:
            p = b.piece_at(sq)
            if not p or p.color != mover or sq == exclude:
                continue
            for target in b.attacks(sq):
                tp = b.piece_at(target)
                if tp and tp.color != mover:
                    out.add((sq, target))
        return out

    revealed = seen(after, best.to_square) - seen(board, best.from_square)
    if not revealed and not after.is_check():
        return Verdict(REFUTED,
                       "no piece behind the mover gains a new attack, so nothing "
                       "was discovered")
    return Verdict(UNDECIDABLE,
                   f"{len(revealed)} new attack(s) revealed; whether that is the "
                   "lesson is the human call")


_VERIFIERS = {
    "simple_hang": _verify_simple_hang,
    "allowed_mate": _verify_allowed_mate,
    "left_book": _verify_left_book,
    "fork": lambda e: _verify_missed_motif(e, "fork"),
    "discovered_attack": lambda e: _verify_missed_motif(e, "discovered_attack"),
}


def verify(detector: str, evidence: Mapping[str, Any]) -> Verdict:
    """Refute a claim if it is provably false. Never approve one.

    An unknown detector, a missing field or a thrown exception all leave the
    claim standing. Failing open is correct here: the cost of keeping a false
    claim is one reviewer saying "wrong", and the cost of dropping a true one
    is evidence we never collect and never know we lost.
    """
    checker = _VERIFIERS.get(detector)
    if checker is None:
        return Verdict(UNDECIDABLE, f"no mechanical check for {detector}")
    try:
        return checker(evidence)
    except Exception as exc:  # noqa: BLE001
        return Verdict(UNDECIDABLE, f"{type(exc).__name__}: {exc}")
