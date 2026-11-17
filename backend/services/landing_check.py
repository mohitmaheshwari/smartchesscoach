"""The coach's landing-square check on the training page.

docs/training_coach_presence_scope.md. After the player drops a piece, before
the move is judged, the coach asks: can the opponent win your piece on its new
square? The player taps the piece that would take it, or taps "Safe".

Every answer here is a board fact:
- safe / not safe comes from grade_destination_safety_candidate, the same
  grader the drill's verdict uses (one source of truth);
- the pieces that can take come from review_tap_reflection._takers (legal
  captures, so a pinned piece is never offered);
- which of the three looks finds each one comes from coach_plan_service._kind;
- whether a given taker WINS the piece is the exchange on that square with that
  capture forced first (legal_exchange_verifier.independent_exchange_gain).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess

from services import coach_plan_service as cp
from services.destination_safety_detector import SEE_FLOOR_CP, grade_destination_safety_candidate
from services.legal_exchange_verifier import independent_exchange_gain
from services.review_tap_reflection import _takers

LOOK_WORDS = {"near": "from close by", "knight": "with a knight jump",
              "far_diagonal": "along a long diagonal", "far_line": "along a long straight line"}
LOOK_ORDER = ("near", "knight", "far_diagonal", "far_line")


def _looks(takers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The three looks, done from the landing square, with what each finds."""
    found = {k: [t for t in takers if t["kind"] == k] for k in LOOK_ORDER}
    lines = found["far_diagonal"] + found["far_line"]
    return [
        {"look": "close", "label": "Pieces close by", "found": found["near"]},
        {"look": "knight", "label": "Knight jumps", "found": found["knight"]},
        {"look": "lines", "label": "Long lines to the edge", "found": lines},
    ]


def check_landing(fen: str, move_uci: str, answer: Optional[str] = None,
                  hint: bool = False) -> Dict[str, Any]:
    """Grade the player's tap (a square, or "safe"), or return the three looks.

    {"eligible": False} when the move is not one the check is about (pawn or
    king moves, an illegal move, or the two exchange proofs disagree); the page
    then judges the move straight away, as before.
    """
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(str(move_uci or ""))
    except ValueError:
        return {"eligible": False}
    if move not in board.legal_moves:
        return {"eligible": False}
    grade = grade_destination_safety_candidate(board.fen(), move.uci())
    if grade.get("status") not in ("pass", "fail"):
        return {"eligible": False}

    me = board.turn
    after = board.copy(stack=False)
    after.push(move)
    dest = move.to_square
    dest_name = chess.square_name(dest)
    piece = chess.piece_name(move.promotion or board.piece_at(move.from_square).piece_type)
    takers = _takers(after, dest)
    gained_first = int(grade.get("played_material_gain_cp") or 0)
    for t in takers:
        frm = chess.parse_square(t["sq"])
        caps = [m for m in after.legal_moves if m.from_square == frm and m.to_square == dest]
        cap = next((m for m in caps if m.promotion in (None, chess.QUEEN)), caps[0])
        net = independent_exchange_gain(after, dest, forced_first=cap) - gained_first
        t["wins"] = grade["status"] == "fail" and net >= SEE_FLOOR_CP
        t["look_words"] = LOOK_WORDS.get(t["kind"], "")
    safe = grade["status"] == "pass"
    winners = [t for t in takers if t["wins"]]
    if not safe and not winners:
        # The grader says it is lost but no single capture shows it (rare
        # multi-step exchange): every legal taker counts as a right answer.
        winners = takers
        for t in takers:
            t["wins"] = True
    out: Dict[str, Any] = {
        "eligible": True, "piece": piece, "square": dest_name, "safe": safe,
        "fen_after": after.fen(),
        "takers": [{k: t[k] for k in ("sq", "piece", "kind", "look_words", "wins")} for t in takers],
        "looks": [{**look, "found": [{"sq": t["sq"], "piece": t["piece"]} for t in look["found"]]}
                  for look in _looks(takers)],
    }
    if hint:
        return out

    first = sorted(winners, key=lambda t: cp.VALUE.get(chess.PIECE_NAMES.index(t["piece"]), 0))[0] if winners else None
    tapped = next((t for t in takers if t["sq"] == answer), None)
    said_safe = str(answer or "").lower() == "safe"
    if safe:
        correct = said_safe
        if correct:
            words = f"Right. Your {piece} is safe on {dest_name}."
        elif tapped:
            words = (f"The {tapped['piece']} on {tapped['sq']} can take it, but you take back and "
                     f"lose nothing. Your {piece} is safe on {dest_name}.")
        else:
            words = f"Nothing can win your {piece} there. It is safe on {dest_name}."
    else:
        correct = bool(tapped and tapped["wins"])
        if correct:
            words = (f"Right. The {tapped['piece']} on {tapped['sq']} can win your {piece} on "
                     f"{dest_name} {tapped['look_words']}.")
        else:
            words = (f"Look again: the {first['piece']} on {first['sq']} can win your {piece} on "
                     f"{dest_name} {first['look_words']}.")
    out.update(correct=correct, words=words, answer_square=first["sq"] if first else None)
    return out


__all__ = ["check_landing", "LOOK_WORDS"]
