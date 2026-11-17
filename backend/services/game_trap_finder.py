"""Traps found in a player's own games, Stage A: the natural move takes the offer.

Scope: docs/trap_lesson_from_games_scope.md (signed 2026-11-17, Mohit: "go
ahead please"). Example 856f6111: 4.Ng5 h6 5.Nxf7 Kxf7 6.Bc4+ Ke8?? and mate.

A trap, Stage A, is three things on the board, each read from stored engine
data and one Maia number:

  the offer      one of the opponent's last two moves cost them at least
                 OFFER_MIN_CP by the engine's own evaluation (they risked it);
  the natural    the player's move is one Maia gives at least NATURAL_MIN at
  move           the player's rating, and it loses at least LOSS_MIN_CP;
                 it TAKES what the offer put there or left unguarded, or it
                 ANSWERS the check that follows the opponent's sacrifice;
  the punishment the engine line after it takes back more than it won
                 (exchange ledger, PUNISH_NET_CP) or mates.

Measured on Mohit's newest 300 games (2026-11-17): the crude "natural blunder
after a costly opponent move" rule found 77 moments, 8 of 30 graded were
traps and 15 were slips; this rule keeps 5 of the 8 and none of the 15.

Nothing here calls an engine. Maia is passed in (`share_of`), so the analysis
worker, a backfill and the tests use the same rule.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

import chess

OFFER_MIN_CP = 100
NATURAL_MIN = 0.30
LOSS_MIN_CP = 200
# At 100 the first dry run (63 finds, 30 graded) let in trades where a better
# in-between move existed and the natural recapture cost one pawn (18, 27 in
# the graded set). Every clear trap in both graded sets costs at least 200
# or mates.
PUNISH_NET_CP = 200
# Already this far behind before the move: not a lesson (graded set 2).
LOST_BEFORE_CP = 300
# An evaluation this big is a mate score; a swing measured against one is not
# a price anybody paid (the unclear rows in the graded sample).
MATE_EVAL = 5000

_VALUE = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300, chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}

ShareFn = Callable[[str, str], Optional[float]]   # (fen, uci) -> Maia share at the player's rating


def share_words(share: float) -> str:
    """How common, said as words (published text carries no numbers)."""
    if share >= 0.6:
        return "most players at your level"
    if share >= 0.45:
        return "about half of players at your level"
    return "many players at your level"


def _move_between(fen_from: Optional[str], fen_to: Optional[str]) -> Optional[chess.Move]:
    """The one legal move that turns `fen_from` into `fen_to` (board, side, castling, ep)."""
    if not fen_from or not fen_to:
        return None
    board = chess.Board(fen_from)
    target = fen_to.split(" ")[:4]
    for mv in board.legal_moves:
        board.push(mv)
        hit = board.fen().split(" ")[:4] == target
        board.pop()
        if hit:
            return mv
    return None


def _material(board: chess.Board, color: chess.Color) -> int:
    return sum(_VALUE[p.piece_type] for p in board.piece_map().values() if p.color == color)


def _offer_cost(prev: Dict[str, Any], cur: Dict[str, Any], user: chess.Color) -> Optional[int]:
    """What the opponent's move between two of the player's moves cost the
    opponent, from the stored White-relative evaluations; None near a mate."""
    a, b = prev.get("eval_after"), cur.get("eval_before")
    if a is None or b is None or abs(a) >= MATE_EVAL or abs(b) >= MATE_EVAL:
        return None
    sign = 1 if user == chess.WHITE else -1
    return sign * (int(b) - int(a))


def _mated(m: Dict[str, Any], user: chess.Color) -> bool:
    """The played move's own evaluation is mate against the player."""
    ev = m.get("eval_after")
    if ev is None:
        return False
    return (ev <= -9000) if user == chess.WHITE else (ev >= 9000)


def find_offer_traps(window_moves: Sequence[Dict[str, Any]], user_color: str, share_of: ShareFn) -> List[Dict[str, Any]]:
    """Stage A traps among the player's moves.

    `window_moves` are the player's own move_evaluations in game order (any
    contiguous run; each needs fen_before, fen_after, move, cp_loss,
    eval_before, eval_after, best_move, pv_after_played). Returns one finding
    per losing move that meets the rule, with the measurements kept."""
    from services.reasoning.differential import closed_groups, exchange_ledger
    user = chess.WHITE if str(user_color).lower() == "white" else chess.BLACK
    them = not user
    out: List[Dict[str, Any]] = []
    moves = list(window_moves)
    for i, m in enumerate(moves):
        if i < 1 or (m.get("cp_loss") or 0) < LOSS_MIN_CP or not m.get("fen_before") or not m.get("move"):
            continue
        if m.get("best_move") and m["best_move"] == m["move"]:
            continue
        root = chess.Board(m["fen_before"])
        try:
            played = root.parse_san(m["move"])
        except ValueError:
            continue
        # Already lost before the move: no lesson in the trap (graded set 2,
        # cases 4, 12, 27, 29 at -4 to -9 for the player).
        if m.get("eval_before") is not None and abs(m["eval_before"]) < MATE_EVAL:
            mine = m["eval_before"] if user == chess.WHITE else -m["eval_before"]
            if mine <= -LOST_BEFORE_CP:
                continue
        # Another piece taking back on the same square was fine: a wrong
        # recapture, not a trap (graded set 2, cases 3, 5, 10: Qxe1, Qxf3, Nxf7).
        best = None
        try:
            best = root.parse_san(m["best_move"]) if m.get("best_move") else None
        except ValueError:
            best = None
        if best is not None and root.is_capture(best) and best.to_square == played.to_square:
            continue

        # The opponent's last two moves, read back off the stored positions.
        offers = []
        for back, j in ((1, i), (2, i - 1)):
            if j < 1:
                continue
            mv = _move_between(moves[j - 1].get("fen_after"), moves[j].get("fen_before"))
            cost = _offer_cost(moves[j - 1], moves[j], user)
            if mv is None or cost is None:
                continue
            # A king move is not an offer: a king that steps off a pawn's
            # guard has blundered, not baited (dry run 1: 4f24e726 m25 and
            # f8b1fe02 m11, both "Kg8", were missed wins, not traps).
            if moves[j - 1].get("fen_after") and chess.Board(moves[j - 1]["fen_after"]).piece_type_at(mv.from_square) == chess.KING:
                continue
            offers.append({"back": back, "move": mv, "cost": cost,
                           "before": chess.Board(moves[j - 1]["fen_after"]), "after": chess.Board(moves[j]["fen_before"])})
        offers = [o for o in offers if o["cost"] >= OFFER_MIN_CP]
        if not offers:
            continue

        # The shape: the move takes the offer, or answers the check after a sacrifice.
        shape, offer = None, None
        sq = played.to_square
        if root.is_capture(played):
            for o in offers:
                pre, post, mv = o["before"], o["after"], o["move"]
                put_there = mv.to_square == sq
                lost_guard = (pre.piece_at(sq) is not None and post.piece_at(sq) is not None
                              and mv.from_square in pre.attackers(them, sq)
                              and mv.to_square not in post.attackers(them, sq))
                if put_there and pre.is_capture(mv):
                    # A capture answered by a recapture is a trade unless they
                    # gave more than they took (graded set 2, case 11: Bxd7
                    # Nxd7 was a plain trade).
                    took_v = _VALUE[pre.piece_at(mv.to_square).piece_type] if pre.piece_at(mv.to_square) else 100
                    gave_v = _VALUE[root.piece_at(sq).piece_type] if root.piece_at(sq) else 0
                    if gave_v < took_v + 200:
                        continue
                if put_there or lost_guard:
                    shape, offer = "offer_taken", o
                    offer["lost_guard"] = lost_guard and not put_there
                    break
        if shape is None and root.is_check() and i >= 1:
            for o in offers:
                given = ((_material(o["before"], them) - _material(o["before"], user))
                         - (_material(root, them) - _material(root, user)))
                if given < 200:
                    continue
                # The player must have TAKEN the sacrifice: 856f6111 Kxf7 took
                # the knight Nxf7 gave. A queen hung with check and not taken
                # is the opponent's slip (graded set 2, case 0).
                prev = moves[i - 1]
                try:
                    pb = chess.Board(prev["fen_before"])
                    pm = pb.parse_san(prev["move"])
                except (ValueError, KeyError, TypeError):
                    continue
                if pb.is_capture(pm) and pm.to_square == o["move"].to_square:
                    shape, offer = "check_after_sacrifice", o
                    break
        if shape is None:
            continue

        # The punishment, on the engine's own line after the move.
        line = [m["move"]] + [str(x) for x in (m.get("pv_after_played") or [])]
        ledger = exchange_ledger(root, line, user)
        closed = closed_groups(ledger, len(line))
        net = sum(g["net_cp"] for g in closed)
        mate = _mated(m, user)
        if not mate and net > -PUNISH_NET_CP:
            continue
        # When the offer only took a guard away, the piece that made it must
        # take part in the punishment, or the loss is unrelated to it
        # (c209379f: Rc1 leaves a2, and the same rook comes back, Ra1).
        if offer.get("lost_guard"):
            walk, involved = root.copy(stack=False), False
            walk.push(played)
            for k, san in enumerate(line[1:7]):
                try:
                    mv = walk.parse_san(san)
                except ValueError:
                    break
                if k % 2 == 0 and mv.from_square == offer["move"].to_square:
                    involved = True
                    break
                walk.push(mv)
            if not involved:
                continue

        # Natural: Maia at the player's rating. Asked last, it is the cost.
        share = share_of(m["fen_before"], played.uci())
        if share is None or share < NATURAL_MIN:
            continue

        pre = offer["before"]
        out.append({
            "source": "game", "stage": "A", "kind": shape, "role": "victim",
            "move_number": m.get("move_number"), "natural_san": m["move"],
            "natural_share": round(float(share), 3), "share_words": share_words(float(share)),
            "offer_san": pre.san(offer["move"]), "offer_moves_back": offer["back"],
            "offer_square": chess.square_name(offer["move"].to_square), "offer_cost_cp": offer["cost"],
            "holding_move": m.get("best_move"), "punishment_san": line[1:11],
            "mate": mate, "net_cp": net, "cp_loss": m.get("cp_loss"),
            "took": root.piece_at(sq).symbol().lower() if root.piece_at(sq) and shape == "offer_taken" else None,
        })
    return out
