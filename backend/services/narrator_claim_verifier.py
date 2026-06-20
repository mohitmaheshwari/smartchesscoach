"""narrator_claim_verifier.py — verify a NARRATOR (LLM) caption's chess claims
against the board + stored engine line before it ships (2026-06-11).

Counterpart to caption_claim_verifier.py: that one checks the DETECTOR's
*structured* primary-reason claim; this one checks the narrator's free *text*
(the LLM can name a piece on the wrong square, say "no recapture" when there is
one, call a defended pawn "free", or claim a mate that isn't). Claude hallucinates
~10-15% even when fed engine truth — proven on this game (m14 "queen on b6 / no
recapture"; m9 v1 "knight on e6"). A narrator caption ships ONLY if it passes;
otherwise it is sent back for self-correction, and on a second failure it is HELD.

API:
    verify_caption(caption, facts) -> list[dict]   # [] == clean
      facts needs: fen_before, played_san (=move_san), is_user_move,
                   best_move_san, pv_after_played
    Each violation: {"check": str, "detail": str}   # detail IS the board truth,
      suitable to feed straight back to the LLM as the correction.

V1 covers the deterministic, high-frequency classes we actually saw. Tactic-NAME
mislabels (e.g. "discovered attack" for a plain check) need per-tactic geometry
and are deferred (logged by the caller as residual). Adding a check = adding one
function — same growth model as caption_claim_verifier.
"""
import re
from typing import Any, Dict, List

import chess

_PIECE = {"knight": chess.KNIGHT, "bishop": chess.BISHOP, "rook": chess.ROOK,
          "queen": chess.QUEEN, "king": chess.KING, "pawn": chess.PAWN}
_PNAME = {v: k for k, v in _PIECE.items()}

_FREE_RX = re.compile(r"\b(free pawn|hanging|undefended|for free|wins? the pawn|"
                      r"win a free|free piece|grab the free)\b", re.I)
_NORECAP_RX = re.compile(r"\b(no recapture|can'?t (?:take|recapture)|"
                         r"loses? (?:the|that) pawn cleanly|without (?:a )?recapture|"
                         r"no way to recapture)\b", re.I)
_MATE_RX = re.compile(r"\b(checkmate|is mate|delivers mate)\b|#", re.I)


def _board_post(facts: Dict[str, Any]) -> chess.Board:
    """Board the user is looking at: after the move that was played."""
    b = chess.Board(facts["fen_before"])
    b.push_san(facts["move_san"])
    return b


def _check_piece_on_square(caption: str, post: chess.Board) -> List[Dict[str, str]]:
    """'<piece> on <sq>' must match the board the user sees. Current-location
    claims only — skip 'to/jumps to/plays' (those are future moves)."""
    out = []
    for m in re.finditer(r"\b(knight|bishop|rook|queen|king|pawn)\s+on\s+([a-h][1-8])\b",
                         caption, re.I):
        pc, sq = m.group(1).lower(), m.group(2).lower()
        pa = post.piece_at(chess.parse_square(sq))
        if pa is None or pa.piece_type != _PIECE[pc]:
            actual = _PNAME.get(pa.piece_type, "nothing") if pa else "nothing"
            out.append({"check": "piece_on_square",
                        "detail": f"says '{pc} on {sq}' but {sq} holds {actual}"})
    return out


def _recommended_capture(facts: Dict[str, Any]):
    """The capture the caption is justifying: best move (user) or the student's
    punishing reply (opponent move). Returns (base_board, move) or (None, None)."""
    b = chess.Board(facts["fen_before"])
    try:
        if facts.get("is_user_move"):
            san = facts.get("best_move_san")
            base = b
        else:
            b.push_san(facts["move_san"])
            pv = facts.get("pv_after_played") or []
            san = pv[0] if pv else None
            base = b
        if not san:
            return (None, None)
        mv = base.parse_san(san)
        return (base, mv) if base.is_capture(mv) else (None, None)
    except Exception:
        return (None, None)


def _check_free(caption: str, facts: Dict[str, Any]) -> List[Dict[str, str]]:
    if not _FREE_RX.search(caption):
        return []
    base, mv = _recommended_capture(facts)
    if mv is None:
        return []
    defs = base.attackers(not base.turn, mv.to_square)
    if defs:
        sq = chess.square_name(mv.to_square)
        return [{"check": "free_when_defended",
                 "detail": f"calls it free/won but {sq} is defended by "
                           f"{[chess.square_name(s) for s in defs]} — the win is a tactic, not a free grab"}]
    return []


def _check_no_recapture(caption: str, facts: Dict[str, Any]) -> List[Dict[str, str]]:
    if not _NORECAP_RX.search(caption):
        return []
    if facts.get("is_user_move"):
        return []  # 'no recapture' framing applies to an opponent capture
    try:
        b = chess.Board(facts["fen_before"])
        mv = b.parse_san(facts["move_san"])
        if not b.is_capture(mv):
            return []
        tgt = mv.to_square
        b.push(mv)
        recaps = [m for m in b.legal_moves if m.to_square == tgt and b.is_capture(m)]
        if recaps:
            return [{"check": "no_recapture",
                     "detail": f"says 'no recapture' but you can recapture on "
                               f"{chess.square_name(tgt)} ({[b.san(m) for m in recaps]})"}]
    except Exception:
        pass
    return []


def _check_mate(caption: str, facts: Dict[str, Any]) -> List[Dict[str, str]]:
    if not _MATE_RX.search(caption):
        return []
    try:
        b = chess.Board(facts["fen_before"])
        if facts.get("is_user_move"):
            rec = facts.get("best_move_san") or facts.get("move_san")
        else:
            pv = facts.get("pv_after_played") or []
            rec = pv[0] if pv else None
        if not rec:
            return []
        b.push_san(rec)
        if not b.is_checkmate():
            return [{"check": "mate",
                     "detail": f"claims checkmate but {rec} is not mate"}]
    except Exception:
        pass
    return []


_OUTPOST_RX = re.compile(r"\boutpost\b|no pawn can chase", re.I)


def _move_is_outpost(board: "chess.Board", mv: "chess.Move") -> bool:
    """Independent re-derivation of the outpost claim (do NOT import the detector —
    defense in depth): a knight on an advanced square no enemy pawn can advance to hit."""
    pc = board.piece_at(mv.from_square)
    if pc is None or pc.piece_type != chess.KNIGHT:
        return False
    to = mv.to_square
    f, r = chess.square_file(to), chess.square_rank(to)
    color = pc.color
    if color == chess.WHITE and not (3 <= r <= 5):
        return False
    if color == chess.BLACK and not (2 <= r <= 4):
        return False
    enemy = not color
    for df in (-1, 1):
        af = f + df
        if 0 <= af <= 7:
            for rr in range(8):
                p = board.piece_at(chess.square(af, rr))
                if p and p.piece_type == chess.PAWN and p.color == enemy:
                    if color == chess.WHITE and rr > r:
                        return False
                    if color == chess.BLACK and rr < r:
                        return False
    return True


def _check_outpost(caption: str, facts: Dict[str, Any]) -> List[Dict[str, str]]:
    if not _OUTPOST_RX.search(caption):
        return []
    cands = []
    try:
        b = chess.Board(facts["fen_before"])
        for san in (facts.get("move_san"), facts.get("best_move_san")):
            if san:
                try:
                    cands.append((b, b.parse_san(san)))
                except Exception:
                    pass
    except Exception:
        pass
    fa = facts.get("fen_after")
    if fa and facts.get("user_best_reply_san"):
        try:
            ba = chess.Board(fa)
            cands.append((ba, ba.parse_san(facts["user_best_reply_san"])))
        except Exception:
            pass
    if cands and not any(_move_is_outpost(bd, mv) for bd, mv in cands):
        return [{"check": "outpost",
                 "detail": "claims an outpost but no candidate move posts a knight no pawn can chase"}]
    return []


def verify_caption(caption: str, facts: Dict[str, Any]) -> List[Dict[str, str]]:
    """Return a list of board-verified violations ([] == clean)."""
    if not caption or not (caption or "").strip():
        return []
    try:
        post = _board_post(facts)
    except Exception:
        return []  # can't build the board → can't check; let caller decide
    return (_check_piece_on_square(caption, post)
            + _check_free(caption, facts)
            + _check_no_recapture(caption, facts)
            + _check_mate(caption, facts)
            + _check_outpost(caption, facts))
