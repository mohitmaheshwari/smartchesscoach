"""Board checks on a stored model-written caption before it replaces a card's own text.

Read 2026-11-12 on 56 mistake and blunder cards (six reviews), all from the
stored LLM caption (rule chain ends LLM_CAPTION):

  - "Kf2 lets their rook hit your pawn on d4"         d4 is the OPPONENT's pawn
  - "Your opponent played Rc8, leaving your a2 pawn with nothing guarding it"
                                                       nothing guarded it before Rc8 either
  - "Kh7 is fine, but ..."                             on a blunder card

`llm_caption.validate` only refuses chess tokens that are not in the facts, so
all three passed. These checks read the board the card shows: before the move
and after it. A failed check returns the reason; the caller keeps the card's
deterministic caption (a refusal is never silence).
"""
from __future__ import annotations

import re
from typing import Optional

import chess

_PIECE = {"pawn": chess.PAWN, "knight": chess.KNIGHT, "bishop": chess.BISHOP,
          "rook": chess.ROOK, "queen": chess.QUEEN, "king": chess.KING}
_P = r"(pawn|knight|bishop|rook|queen|king)"
_SQ = r"([a-h][1-8])"
# "your pawn on d4" / "their knight on e5"
_OWNED_ON = re.compile(rf"\b(your|their)\s+{_P}\s+on\s+{_SQ}\b", re.I)
# "your a2 pawn" / "their e5 knight"
_OWNED_SQ_FIRST = re.compile(rf"\b(your|their)\s+{_SQ}\s+{_P}\b", re.I)
# "leaves/leaving/left your a2 pawn ... nothing guarding it"
_LEAVES_UNGUARDED = re.compile(
    rf"\b(?:leaves|leaving|left)\s+(your|their)\s+(?:{_P}\s+on\s+{_SQ}|{_SQ}\s+{_P})"
    r"[^.]*?\b(?:nothing guarding|with no guard|unguarded|undefended|unprotected|loose|hanging)", re.I)
_APOS = "['’]"
# The same wording game_summary_service refuses under a fault badge.
_DENIES_FAULT = re.compile(
    rf"\b(isn{_APOS}t a (?:blunder|mistake)|is not a (?:blunder|mistake)|"
    rf"is playable|is fine|is okay|doesn{_APOS}t change much)\b", re.I)


def _boards(fen_before: str, played_san: str):
    before = chess.Board(fen_before)
    after = before.copy()
    try:
        after.push_san(played_san)
    except Exception:                                   # noqa: BLE001
        after = None
    return before, after


def stored_caption_problem(text: str, *, fen_before: str, played_san: str,
                           mover_is_user: bool, fault_card: bool) -> Optional[str]:
    """Why this stored caption may not replace the card's text, or None."""
    text = (text or "").strip()
    if not text or not fen_before or not played_san:
        return None
    if fault_card and _DENIES_FAULT.search(text):
        return "denies the fault the card shows"
    try:
        before, after = _boards(fen_before, played_san)
    except Exception:                                   # noqa: BLE001
        return None
    mover = before.turn
    reader = mover if mover_is_user else (not mover)
    boards = [b for b in (before, after) if b is not None]

    def owner_of(word: str) -> chess.Color:
        return reader if word.lower() == "your" else (not reader)

    for m in list(_OWNED_ON.finditer(text)) + list(_OWNED_SQ_FIRST.finditer(text)):
        if m.re is _OWNED_ON:
            whose, piece, sq = m.group(1), m.group(2), m.group(3)
        else:
            whose, sq, piece = m.group(1), m.group(2), m.group(3)
        square = chess.parse_square(sq.lower())
        want = chess.Piece(_PIECE[piece.lower()], owner_of(whose))
        found = [b.piece_at(square) for b in boards]
        same_type = [p for p in found if p and p.piece_type == want.piece_type]
        # Only a square that holds that kind of piece is judged; a square from
        # later in a line is left alone.
        if same_type and all(p.color != want.color for p in same_type):
            return f"calls the {piece} on {sq} {whose.lower()}, but it belongs to the other side"

    for m in _LEAVES_UNGUARDED.finditer(text):
        whose = m.group(1)
        piece = m.group(2) or m.group(5)
        sq = m.group(3) or m.group(4)
        square = chess.parse_square(sq.lower())
        owner = owner_of(whose)
        p_before = before.piece_at(square)
        if not p_before or p_before.color != owner or p_before.piece_type != _PIECE[piece.lower()]:
            continue
        guarded_before = before.is_attacked_by(owner, square)
        guarded_after = after is not None and after.piece_at(square) == p_before and after.is_attacked_by(owner, square)
        if not guarded_before or guarded_after:
            return (f"says the move leaves the {piece} on {sq} unguarded, but "
                    + ("nothing guarded it before the move either" if not guarded_before
                       else "it is still guarded after the move"))
    return None
