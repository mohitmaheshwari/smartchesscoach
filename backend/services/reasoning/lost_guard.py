"""Lost guard, two steps deep: the played move stops a piece guarding a square,
and after the opponent's reply the trade on that square is won only because
that guard is gone, leaving the piece it supported with no guard.

Scope: docs/why_lost_guard_threat_scope.md (Mohit, 2026-11-16: "go ahead").

The one-step lost guard in differential_causes fires only when the reply hits a
piece left with no defender at all. It is silent when a defender is left that a
trade removes: chesstribe64's 26.Qc2 (game 4ec5dfca) took the queen off e5.
After 26...f6 the f4 pawn still guards e5, so nothing is undefended on the
board, yet the trade fxe5 fxe5 Bxe5+ is won (the bishop on g7 sees e5 once the
f6 pawn has captured) and the knight on d6, held only from e5, has no guard.
After the better 26.Rbc1 the same trade ends Qxe5, so Black does not start it.
White's best defence gives up material elsewhere (27.b5 axb5), which is why
the engine's line after the played move never shows the trade, and the button
said "f6 starts a line that ends with axb5 taking your pawn on b5".

Board only, like the one-step rule: the trade is played out capture by
capture with legal moves (so x-rays appear as pieces leave the line), each
side capturing with its cheapest piece and stopping when going on would lose
material. A threat is the opponent's next move, so the trade is judged as if
the mover passes after the reply; the sentence says "threatens".
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess

PIECE_NAME = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
              chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}
VALUE = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300, chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20_000}
MIN_TARGET_VALUE = 300     # the piece left unguarded is a knight or more


def _pass(board: chess.Board) -> Optional[chess.Board]:
    if board.is_check() or board.is_game_over():
        return None
    b = board.copy(stack=False)
    b.push(chess.Move.null())
    fresh = chess.Board(b.fen())
    return fresh if fresh.is_valid() else None


def trade(board: chess.Board, square: int) -> Dict[str, Any]:
    """The capture sequence on `square`, side to move first, cheapest legal
    capturer each time; then where a sensible side stops. Returns the moves
    actually played, the board after them and the first side's net gain."""
    walker = board.copy(stack=False)
    steps: List[Dict[str, Any]] = []
    while True:
        victim = walker.piece_at(square)
        if victim is None or victim.color == walker.turn:
            break
        captures = [m for m in walker.legal_moves if m.to_square == square]
        if not captures:
            break
        move = min(captures, key=lambda m: (VALUE[walker.piece_at(m.from_square).piece_type], m.uci()))
        steps.append({"san": walker.san(move), "uci": move.uci(), "gain": VALUE[victim.piece_type],
                      "by": walker.turn})
        walker.push(move)
    # best[i]: what the side making capture i nets from it, if both go on only
    # while it pays. A capture is made only when it nets more than nothing.
    best = [0] * len(steps)
    for i in range(len(steps) - 1, -1, -1):
        nxt = best[i + 1] if i + 1 < len(steps) else 0
        best[i] = steps[i]["gain"] - max(0, nxt)
    # The side that starts needs a real gain; a side taking back does so unless
    # it loses by it (an even recapture is the natural move: fxe5 fxe5).
    played = 0
    while played < len(steps) and (best[played] > 0 or (best[played] == 0 and steps[played]["by"] != board.turn)):
        played += 1
    end = board.copy(stack=False)
    for s in steps[:played]:
        end.push(chess.Move.from_uci(s["uci"]))
    net = sum(s["gain"] if s["by"] == board.turn else -s["gain"] for s in steps[:played])
    return {"steps": steps[:played], "board": end, "net": net, "best": best}


def _falls(end: chess.Board, target: int, piece: chess.Piece, mover: chess.Color) -> bool:
    """The target is still there, the opponent attacks it, nothing of the mover
    guards it, and the mover cannot use its move to save it (the opponent is to
    move, or every legal answer to check leaves it hanging the same way)."""
    if end.piece_at(target) != piece or end.attackers(mover, target) or not end.attackers(not mover, target):
        return False
    if end.turn != mover:
        return True
    if not end.is_check():
        return False
    for move in end.legal_moves:
        b = end.copy(stack=False)
        b.push(move)
        if b.piece_at(target) == piece and not b.attackers(mover, target) and b.attackers(not mover, target):
            continue
        return False
    return True


def lost_guard_threat(root: chess.Board, played: chess.Move, alternative: chess.Move, reply_uci: Optional[str], *,
                      mover_is_user: bool) -> Dict[str, Any]:
    """{"fires": bool, "why_not": str|None, "cause": dict|None, ...}; the
    measurement is kept whether or not it fires."""
    out: Dict[str, Any] = {"fires": False, "why_not": None, "cause": None}
    if not reply_uci:
        out["why_not"] = "no_reply"
        return out
    mover = root.turn
    after_p, after_a = root.copy(stack=False), root.copy(stack=False)
    after_p.push(played)
    after_a.push(alternative)
    reply = chess.Move.from_uci(reply_uci)
    if reply not in after_p.legal_moves or reply not in after_a.legal_moves:
        out["why_not"] = "reply_not_on_both_branches"
        return out
    if after_p.is_capture(reply) or after_p.gives_check(reply):
        out["why_not"] = "reply_not_quiet"          # captures and checks belong to the one-step families
        return out
    guard_from = played.from_square
    guard = root.piece_at(guard_from)
    tp, ta = after_p.copy(stack=False), after_a.copy(stack=False)
    tp.push(reply)
    ta.push(reply)
    pass_p, pass_a = _pass(tp), _pass(ta)
    if pass_p is None or pass_a is None:
        out["why_not"] = "cannot_pass"
        return out
    tried = []
    for s in chess.SquareSet(root.attacks(guard_from)):
        sp = root.piece_at(s)
        # The moved piece guarded s before, still would after the better move,
        # and does not after the played move; the reply now attacks s.
        if sp is None or sp.color != mover or sp.piece_type == chess.KING:
            continue
        if tp.piece_at(s) != sp or ta.piece_at(s) != sp:
            continue
        if not (guard_from in ta.attackers(mover, s) and played.to_square not in tp.attackers(mover, s)
                and guard_from not in tp.attackers(mover, s)):
            continue
        if reply.to_square != s and s not in tp.attacks(reply.to_square):
            continue
        targets = [k for k in chess.SquareSet(tp.attacks(s)) if (p := tp.piece_at(k)) is not None
                   and p.color == mover and p.piece_type != chess.KING and VALUE[p.piece_type] >= MIN_TARGET_VALUE
                   and set(tp.attackers(mover, k)) == {s}]
        if not targets:
            continue
        tried.append(chess.square_name(s))
        tr_p, tr_a = trade(pass_p, s), trade(pass_a, s)
        if tr_p["net"] <= 0 or tr_a["net"] > 0:
            continue                                  # not won after the played move, or won after both
        for k in targets:
            piece = tp.piece_at(k)
            if not _falls(tr_p["board"], k, piece, mover):
                continue
            if tr_a["steps"] and _falls(tr_a["board"], k, piece, mover):
                continue
            played_san, reply_san, alt_san = root.san(played), after_p.san(reply), root.san(alternative)
            own, other = ("your", "their") if mover_is_user else ("their", "your")
            they = "they" if mover_is_user else "you"
            last = tr_p["steps"][-1]
            taker = PIECE_NAME[tr_p["board"].piece_at(s).piece_type]
            check = " with check" if tr_p["board"].is_check() else ""
            moves = " ".join(st["san"] for st in tr_p["steps"])
            sname, kname = chess.square_name(s), chess.square_name(k)
            guard_name = PIECE_NAME[guard.piece_type]
            middle = (f"After {reply_san}, {they} win the trade on {sname}: {other} {taker} takes last{check}."
                      if len(tr_p["steps"]) > 1 else
                      f"After {reply_san}, {they} can take on {sname} with {other} {taker}{check}.")
            text = (f"{played_san} stops {own} {guard_name} guarding {sname}. {middle} "
                    f"Then nothing guards {own} {PIECE_NAME[piece.piece_type]} on {kname}. "
                    f"{alt_san} keeps {own} {guard_name} guarding {sname}.")
            consequence = {"mechanism": "WINS_MATERIAL", "direction": "received", "agent_move": reply_san,
                           "victim_piece": PIECE_NAME[piece.piece_type], "victim_square": kname, "square": kname,
                           "captures": [st["san"] for st in tr_p["steps"]], "payoff_cp": tr_p["net"],
                           "series": False, "text": None}
            out.update(fires=True, why_not=None, supports=tried, trade_played=moves,
                       trade_alternative=" ".join(st["san"] for st in tr_a["steps"]),
                       cause={"kind": "lost_guard", "variant": "threat", "reply": reply_san,
                              "piece": PIECE_NAME[sp.piece_type], "square": sname,
                              "guard_square": chess.square_name(guard_from), "guard_piece": PIECE_NAME[guard.piece_type],
                              "guard_was_the_moved_piece": True, "target_piece": PIECE_NAME[piece.piece_type],
                              "target_square": kname, "trade_san": [st["san"] for st in tr_p["steps"]],
                              "last_capture": last["san"], "owner": own, "text": text, "consequence": consequence})
            return out
    out["supports"] = tried
    out["why_not"] = "no_guard_loss_decides_a_trade" if tried else "no_guarded_support_lost"
    return out
