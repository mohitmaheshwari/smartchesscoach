"""Same reply, different answer: when both moves allow the same reply, the
difference is what the mover can do about it.

Scope: docs/why_shared_answer_scope.md (Mohit, 2026-11-27: "do it", on the
plan to teach the engine this case after a review card read out a raw line).

The case that found it: 18.Qd2 (2r1r1k1/pp2bpp1/1q3n1p/n2P4/7B/2N2B2/PPQ2PPP/
1K1R3R w). Stockfish wants d6 (+0.8 against -3.2). Black answers Nc4 after
either move, so the engine called the knight jump "shared" and stopped with no
sentence. But after d6 Nc4 the mover answers Qb3 and trades queens; after
Qd2 Nc4 the queen is no longer on c2 and Qb3 does not exist. The reply is
shared. The answer to it is not.

So: when the reply locator finds the same reply on both branches, take the
mover's answer X from the better branch's line and ask whether X still exists
after the played move and the same reply.
  - X is illegal there, and the board says why: the piece that plays X is the
    piece the played move moved, or the played move's piece now stands in X's
    path or on X's square;
  - or X is legal there but Stockfish, restricted to X, says it fails, and the
    line after X wins the mover's material (exchange ledger).
Either way the two branches must really differ: after the better move and the
reply the mover stands clearly better than after the played move and the
reply (SHARED_ANSWER_MIN_CP, and at least half the gap).

Nothing here guesses why X matters beyond what the board and the engine show:
the sentence says the answer exists on one branch and not on the other.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import chess

from .threat_line import PIECE_NAME, THREAT_MIN_CP, _best, _material

# The two branches must differ by at least this much after the shared reply,
# mover's side, and by at least SHARED_ANSWER_GAP_SHARE of the gap. Same floor
# as the threat and opportunity lines.
SHARED_ANSWER_MIN_CP = THREAT_MIN_CP
SHARED_ANSWER_GAP_SHARE = 0.5


def _between(a: int, b: int) -> set:
    """Squares strictly between a and b on a rank, file or diagonal."""
    return set(chess.SquareSet(chess.between(a, b)))


def _trade(board: chess.Board, answer: chess.Move, next_two) -> Optional[str]:
    """The piece name when the answer is taken on its square by the same kind
    of piece and taken back at once (Qb3 Qxb3 axb3: "queen"), else None."""
    mover_piece = board.piece_at(answer.from_square)
    if mover_piece is None or len(next_two) < 2:
        return None
    walker = board.copy(stack=False)
    walker.push(answer)
    try:
        take = walker.parse_san(next_two[0])
    except ValueError:
        return None
    taker = walker.piece_at(take.from_square)
    if take.to_square != answer.to_square or taker is None or taker.piece_type != mover_piece.piece_type:
        return None
    walker.push(take)
    try:
        back = walker.parse_san(next_two[1])
    except ValueError:
        return None
    if back.to_square != answer.to_square:
        return None
    return PIECE_NAME[mover_piece.piece_type]


def _why_gone(after_pr: chess.Board, played: chess.Move, answer: chess.Move,
              answer_board: chess.Board) -> Optional[Dict[str, Any]]:
    """Why `answer` (legal in `answer_board`) is not legal in `after_pr`, when
    the played move is the reason. None when the board gives another reason
    (a pin, a check), which V1 does not put into words."""
    piece = answer_board.piece_at(answer.from_square)
    if piece is None:
        return None
    name = PIECE_NAME[piece.piece_type]
    if played.from_square == answer.from_square:
        return {"kind": "moved_away", "piece": name, "from": chess.square_name(answer.from_square)}
    if played.to_square == answer.to_square:
        return {"kind": "occupied", "piece": name, "square": chess.square_name(answer.to_square)}
    if piece.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN) and played.to_square in _between(
            answer.from_square, answer.to_square):
        blocker = after_pr.piece_at(played.to_square)
        return {"kind": "blocked", "piece": name,
                "blocker": PIECE_NAME[blocker.piece_type] if blocker else None,
                "square": chess.square_name(played.to_square)}
    return None


def shared_answer(session, root: chess.Board, played: chess.Move, alternative: chess.Move, *,
                  played_branch: Optional[Dict[str, Any]], alt_branch: Optional[Dict[str, Any]],
                  depth: int, mover_is_user: bool, gap_cp: Optional[int]) -> Dict[str, Any]:
    """{"fires": bool, "why_not": str|None, "answer": dict|None, measurements...}.

    Branch scores are the reply locator's baselines: the position after the
    move with the opponent's best reply in front, from the mover's side once
    passed through score_cp."""
    from .differential import score_cp
    out: Dict[str, Any] = {"fires": False, "why_not": None, "answer": None}
    if not played_branch or not alt_branch:
        out["why_not"] = "branch_unavailable"
        return out
    reply_uci = played_branch.get("reply_uci")
    if not reply_uci or reply_uci != alt_branch.get("reply_uci"):
        out["why_not"] = "different_replies"
        return out
    p_line, a_line = list(played_branch.get("line_san") or []), list(alt_branch.get("line_san") or [])
    if len(a_line) < 2 or not p_line:
        out["why_not"] = "line_too_short"
        return out
    p_cp, a_cp = score_cp(played_branch.get("score")), score_cp(alt_branch.get("score"))
    if p_cp is None or a_cp is None:
        out["why_not"] = "search_unavailable"
        return out
    swing = a_cp - p_cp
    out.update(reply_uci=reply_uci, after_better_cp=a_cp, after_played_cp=p_cp, swing_cp=swing)
    if swing < SHARED_ANSWER_MIN_CP or (gap_cp and swing < SHARED_ANSWER_GAP_SHARE * gap_cp):
        out["why_not"] = "branches_close"
        return out

    after_ar, after_pr = root.copy(stack=False), root.copy(stack=False)
    after_ar.push(alternative)
    after_pr.push(played)
    reply = chess.Move.from_uci(reply_uci)
    if reply not in after_ar.legal_moves or reply not in after_pr.legal_moves:
        out["why_not"] = "reply_illegal"
        return out
    reply_san = after_pr.san(reply)
    after_ar.push(reply)
    after_pr.push(reply)
    try:
        answer = after_ar.parse_san(a_line[1])
    except ValueError:
        out["why_not"] = "answer_unparseable"
        return out
    answer_san = after_ar.san(answer)
    out.update(reply_san=reply_san, answer_san=answer_san, answer_line_san=a_line[1:7])
    if len(p_line) >= 2 and p_line[1] == answer_san:
        out["why_not"] = "same_answer_both"
        return out
    alt_san, played_san = root.san(alternative), root.san(played)
    your = "your" if mover_is_user else "their"
    you = "you" if mover_is_user else "they"
    trade = _trade(after_ar, answer, a_line[2:4])
    out["answer_trades"] = trade
    how = f"{answer_san} and trade {trade}s" if trade else answer_san
    lead = f"{alt_san} was the move. Both moves allow {reply_san}, but after {alt_san} {you} answer it with {how}."

    if answer not in after_pr.legal_moves:
        why = _why_gone(after_pr, played, answer, after_ar)
        out["answer_legal_after_played"] = False
        if why is None:
            out["why_not"] = "answer_gone_other_reason"
            return out
        out["gone"] = why
        if why["kind"] == "moved_away":
            tail = f"After {played_san}, {your} {why['piece']} is no longer on {why['from']}, so {answer_san} is not possible."
        elif why["kind"] == "occupied":
            tail = f"After {played_san}, {answer_san} is not possible: {your} own piece now stands on {why['square']}."
        else:
            blocker = f"{your} {why['blocker']}" if why.get("blocker") else "a piece"
            tail = f"After {played_san}, {blocker} on {why['square']} is in the way, so {answer_san} is not possible."
        text = f"{lead} {tail}"
        facts = {"the_shared_reply": reply_san, "the_answer_after_the_better_move": answer_san,
                 "the_answer_trades": f"{trade}s" if trade else None,
                 "the_answer_exists_after_the_move_played": False,
                 "why_the_answer_is_gone": tail}
        consequence = {"mechanism": "SHARED_REPLY", "direction": "missed", "agent_move": alt_san,
                       "reply": reply_san, "answer": answer_san, "gone": why, "text": None}
    else:
        out["answer_legal_after_played"] = True
        same = _best(session, after_pr, "shared_answer_played_x", depth=depth, roots=[answer])
        if same is None:
            out["why_not"] = "search_unavailable"
            return out
        x_cp = score_cp(same["score"])
        out.update(answer_after_played_cp=x_cp, answer_line_played_san=list(same["moves_san"][:8]))
        if x_cp is None or a_cp - x_cp < SHARED_ANSWER_MIN_CP:
            out["why_not"] = "answer_still_works"
            return out
        material = _material(after_pr, list(same["moves_san"]), after_pr.turn)
        if material is None:
            out["why_not"] = "answer_fails_without_material"
            return out
        from .differential import _pieces_phrase
        g, hit = material["group"], material["hit"]
        lost = _pieces_phrase(g["mover_lost"], article=False)
        tail = f"After {played_san}, {answer_san} fails: {hit['san']} wins {your} {lost} on {g['square']}."
        text = f"{lead} {tail}"
        facts = {"the_shared_reply": reply_san, "the_answer_after_the_better_move": answer_san,
                 "the_answer_trades": f"{trade}s" if trade else None,
                 "the_answer_exists_after_the_move_played": True,
                 "what_goes_wrong_with_it_after_the_move_played": tail}
        consequence = {"mechanism": "SHARED_REPLY", "direction": "missed", "agent_move": alt_san,
                       "reply": reply_san, "answer": answer_san, "square": g["square"],
                       "captures": [p["san"] for p in g["plies"]], "text": None}

    facts = {k: v for k, v in facts.items() if v is not None}
    out.update(fires=True, why_not=None,
               answer={"text": text, "facts": facts, "consequence": consequence,
                       "line_san": [alt_san, reply_san, answer_san]})
    return out
