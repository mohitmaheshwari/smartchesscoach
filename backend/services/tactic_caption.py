"""A card's lead sentence and arrows, built from one proved tactic tag.

Scopes: docs/observation_detectors_scope.md and
docs/caption_from_board_meaning_scope.md (both signed). The tag comes from
services/tactic_tags.py, where a board prover with an independent verifier
confirmed it; this module only puts the tag's own pieces and squares into
words and arrows, so the sentence and the picture cannot disagree with the
proof or with each other.

Only tags whose tactic happens on the move itself (`at_ply == 0`) are used:
the 2026-11-13 hand check found half the forks and discovered attacks land
later in the line, and "b4 was a fork" for a fork five plies on is false.

Words follow the caption rules: very easy English, no numbers, and no move in
notation except the played move, the better move and the reader's own answer.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import chess

_NAME = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
         chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}

# One plain lesson per tactic, used when the card has no lesson of its own.
LESSON = {
    "fork": "Before you move, look for a move that attacks two things at once.",
    "free_piece": "Before you move, check which pieces have nothing guarding them.",
    "forced_mate": "Look at every check first: one of them can end the game.",
    "back_rank_mate": "A king shut in behind its own pawns can be mated on the back rank.",
    "discovered_attack": "When a piece moves, check what the piece behind it now attacks.",
    "pin": "A piece in front of a bigger one cannot move away safely.",
    "skewer": "When a big piece is attacked, look at what stands behind it.",
}

# Which tag the card leads with, by the card's story (punishment = what the
# move allowed; opportunity = what it missed).
_KIND_ORDER = {
    "punishment": ("allowed", "missed"),
    "opportunity": ("missed", "allowed"),
}


def _piece_name(board: chess.Board, square: Optional[str]) -> Optional[str]:
    if not square:
        return None
    try:
        p = board.piece_at(chess.parse_square(square))
    except ValueError:
        return None
    return _NAME.get(p.piece_type) if p else None


def _arrow(a: str, b: str, colour: str) -> Dict[str, Any]:
    return {"from": a, "to": b, "color": colour, "teach": True}


def pick_tag(tags: List[Dict[str, Any]], story: Optional[str]) -> Optional[Dict[str, Any]]:
    """The tag a fault card leads with: immediate tactics only, the story's kind
    first, and within a kind the order tactic_tags stores (mate first)."""
    usable = [t for t in tags or [] if t.get("at_ply") == 0
              and t.get("kind") in ("missed", "allowed") and t.get("motif") in LESSON]
    for kind in _KIND_ORDER.get(story or "", ("missed", "allowed")):
        for t in usable:
            if t["kind"] == kind:
                return t
    return None


def describe(tag: Dict[str, Any], *, fen_before: str, played_san: str,
             mover_is_user: bool) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """(sentence, arrows) for one tag, or (None, []) when the facts do not
    carry what the sentence needs. Arrows are drawn on the board the card
    shows (after the played move) and only for ALLOWED tags, whose tactic is
    on that board; a MISSED tactic belongs to the board before the move."""
    motif, kind = tag.get("motif"), tag.get("kind")
    facts = tag.get("facts") or {}
    move = tag.get("move") or ""
    try:
        before = chess.Board(fen_before)
        played = before.parse_san(played_san)
    except (ValueError, AssertionError):
        return None, []
    after = before.copy(stack=False)
    after.push(played)
    # The board the tactic is played on, and the board after it.
    tboard = before if kind == "missed" else after
    try:
        tmove = tboard.parse_san(move)
    except (ValueError, AssertionError):
        return None, []
    tafter = tboard.copy(stack=False)
    tafter.push(tmove)

    # Whose tactic, in the reader's words.
    reader_plays_it = (mover_is_user and kind == "missed") or (
        not mover_is_user and kind == "allowed")
    own, other = ("your", "their") if reader_plays_it else ("their", "your")
    mover_piece = _NAME.get(tafter.piece_at(tmove.to_square).piece_type) if tafter.piece_at(tmove.to_square) else "piece"
    arrows: List[Dict[str, Any]] = []
    frm, to = chess.square_name(tmove.from_square), chess.square_name(tmove.to_square)

    if motif == "fork":
        targets = [s for s in (facts.get("targets") or []) if isinstance(s, str)][:2]
        names = [(_piece_name(tafter, s), s) for s in targets]
        if len(names) < 2 or not all(n for n, _ in names):
            return None, []
        what = f"{other} {names[0][0]} on {names[0][1]} and {other} {names[1][0]} on {names[1][1]}"
        body = f"{own} {mover_piece} on {to} attacks {what} at once"
        arrows = [_arrow(frm, to, "blue")] + [_arrow(to, s, "green" if reader_plays_it else "red") for _, s in names]
    elif motif == "free_piece":
        sq = facts.get("captured_square")
        name = facts.get("captured_piece") or _piece_name(tboard, sq)
        if not sq or not name:
            return None, []
        body = f"{other} {name} on {sq} has nothing guarding it, and {own} {mover_piece} takes it"
        arrows = [_arrow(frm, sq, "blue" if reader_plays_it else "red")]
    elif motif in ("forced_mate", "back_rank_mate"):
        how = " on the back rank" if motif == "back_rank_mate" else ""
        body = f"{own} side can force mate{how}, starting with {own} {mover_piece} to {to}"
        arrows = [_arrow(frm, to, "blue" if reader_plays_it else "red")]
    elif motif == "discovered_attack":
        slider_sq = facts.get("slider_square")
        target_sq = facts.get("target_square") or facts.get("checked_square")
        slider = _piece_name(tafter, slider_sq)
        target = _piece_name(tafter, target_sq)
        if not (slider and target):
            return None, []
        body = (f"moving {own} {mover_piece} from {frm} opens {own} {slider} on {slider_sq} "
                f"onto {other} {target} on {target_sq}")
        arrows = [_arrow(frm, to, "blue"), _arrow(slider_sq, target_sq, "green" if reader_plays_it else "red")]
    elif motif in ("pin", "skewer"):
        fs, rs = facts.get("front_square"), facts.get("rear_square")
        front, rear = _piece_name(tafter, fs), _piece_name(tafter, rs)
        if not (front and rear):
            return None, []
        if motif == "pin":
            body = f"{own} {mover_piece} pins {other} {front} on {fs} to {other} {rear} on {rs}"
        else:
            body = (f"{own} {mover_piece} attacks {other} {front} on {fs}, and when it moves, "
                    f"{other} {rear} on {rs} falls")
        arrows = [_arrow(frm, to, "blue"), _arrow(to, fs, "red"), _arrow(fs, rs, "red")]
    else:
        return None, []

    label = {"fork": "a fork", "free_piece": "a free piece", "forced_mate": "a forced mate",
             "back_rank_mate": "a back-rank mate", "discovered_attack": "a discovered attack",
             "pin": "a pin", "skewer": "a skewer"}[motif]
    if mover_is_user and kind == "missed":
        sentence = f"You missed {label}: {move} was better, because {body}."
    elif mover_is_user and kind == "allowed":
        sentence = f"{played_san} allows {label}: {body}."
    elif kind == "missed":
        sentence = f"Your opponent missed {label}: {move} was better for them, because {body}."
    else:
        sentence = f"Their {played_san} allows {label}: play {move}, because {body}."
    sentence = sentence[0].upper() + sentence[1:]
    if kind == "allowed":
        return sentence, arrows
    # A MISSED tactic lives on the board before the move. Draw it on the board
    # the card shows only when it is still exactly there: the same move is
    # legal with the turn handed back, and the played move touched none of
    # the squares in the picture (the same test _missed_move_arrow uses).
    touched = {chess.square_name(played.from_square), chess.square_name(played.to_square)}
    squares = {a["from"] for a in arrows} | {a["to"] for a in arrows}
    probe = after.copy(stack=False)
    still_there = False
    if not probe.is_check():
        probe.push(chess.Move.null())
        still_there = tmove in probe.legal_moves and not (squares & touched)
    return sentence, (arrows if still_there else [])
