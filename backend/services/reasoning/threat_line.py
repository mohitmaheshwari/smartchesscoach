"""The threat behind the reply, read from a Stockfish line.

Scope: docs/why_threat_line_scope.md (Mohit, 2026-11-16: "go", after "engine
should use lines, because those give you what stockfish tells").

The punished family says the opponent's reply carries the mistake. When the
reply is quiet, its point is the move after it, and the engine's line after
the played move shows the mover's best DEFENCE against that move, not the move
itself. The ledger then names whatever the defence pays ("Qd7 starts a line
that ends with Qxf6+ taking your bishop", dev_qf8), which is the price of the
threat, not the reason.

A threat is what the opponent does if the mover does nothing. So: after the
played move and the reply, let the mover pass and ask Stockfish for its best
move T and line. T is the reason when
  - passing costs the mover clearly more than its best defence (Stockfish), and
    the line wins material (exchange ledger) or mates;
  - after the better move and the same reply, the same T does not win (a
    search restricted to T), or is not legal.
The words say what the line shows and nothing more. Where the board shows why
T fails after the better move -- the better move guards T's square, or the
played move took a guard off it -- one more sentence says so.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess

from services.stored_line_verifier import parse_legal_move

PIECE_NAME = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
              chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}

# How much more than the best defence a pass must cost before the reply is
# said to threaten something. Provisional until the sample distribution
# (scope section 6); the measurement is kept on every run.
THREAT_MIN_CP = 200
# A mate further away than this is not a threat a reader can see.
MATE_MAX_MOVES = 3
# The threat's own capture must come early in its line: the threat is a move,
# not the engine's whole plan.
THREAT_CAPTURE_MAX_PLY = 4
# The threat is T and the exchange it starts, not the engine's whole plan: the
# ledger reads this many plies of the threat line. At 12 (the played-line
# horizon) codex_bxd5 read "taking your knight and bishop on g5", the bishop
# being a sacrifice on the same square seven plies later.
THREAT_LEDGER_PLIES = 6


def _passed(board: chess.Board) -> Optional[chess.Board]:
    """The same position with the other side to move; None if a pass is illegal."""
    if board.is_check() or board.is_game_over():
        return None
    b = board.copy(stack=False)
    b.push(chess.Move.null())
    fresh = chess.Board(b.fen())
    return fresh if fresh.is_valid() else None


def _best(session, board: chess.Board, purpose: str, *, depth: int, roots=()) -> Optional[Dict[str, Any]]:
    record = session.query(board, purpose, roots=list(roots), width=1, depth=depth)
    if record.status != "complete_iteration" or not record.lines:
        return None
    return record.lines[0]


def _takes_on(board: chess.Board, san: Optional[str], square: int) -> bool:
    """True when `san`, played on `board`, captures on `square`."""
    if not san:
        return False
    move = parse_legal_move(board, san)
    return move is not None and move.to_square == square and board.is_capture(move)


def _material(board: chess.Board, line_san: List[str], mover: chess.Color) -> Optional[Dict[str, Any]]:
    """The first square in the threat line where the mover loses at least a
    pawn's worth, when the rest of the line does not give it back."""
    from .differential import EXCHANGE_MIN_CP, closed_groups, exchange_ledger
    plies = min(len(line_san), THREAT_LEDGER_PLIES)
    ledger = exchange_ledger(board, line_san, mover, max_plies=THREAT_LEDGER_PLIES)
    closed = closed_groups(ledger, plies)
    if len(closed) != len(ledger):
        return None                     # a capture at the horizon leaves the count in doubt
    total = sum(g["net_cp"] for g in closed)
    for g in closed:
        if g["net_cp"] > -EXCHANGE_MIN_CP:
            continue
        hit = next(p for p in g["plies"] if not p["by_mover"])
        if hit["ply"] > THREAT_CAPTURE_MAX_PLY:
            return None
        if total > g["net_cp"] + EXCHANGE_MIN_CP:
            return None                 # given back later in the line
        return {"group": g, "hit": hit, "total_cp": total}
    return None


def threat_line(session, root: chess.Board, played: chess.Move, alternative: chess.Move,
                reply_uci: Optional[str], *, depth: int, mover_is_user: bool,
                base_played: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """{"fires": bool, "why_not": str|None, "cause": dict|None, measurements...}.

    `base_played` is the played branch from the reply locator; its baseline
    line starts with the reply, so its score is the mover's best defence. Every
    score here is the session's, i.e. from the mover's side."""
    from .differential import score_cp
    out: Dict[str, Any] = {"fires": False, "why_not": None, "cause": None}
    if not reply_uci:
        out["why_not"] = "no_reply"
        return out
    mover = root.turn
    reply = chess.Move.from_uci(reply_uci)
    after_p, after_a = root.copy(stack=False), root.copy(stack=False)
    after_p.push(played)
    after_a.push(alternative)
    if reply not in after_p.legal_moves:
        out["why_not"] = "reply_illegal"
        return out
    reply_san = after_p.san(reply)
    if after_p.gives_check(reply):
        out["why_not"] = "reply_is_check"
        return out
    tp = after_p.copy(stack=False)
    tp.push(reply)
    pass_p = _passed(tp)
    if pass_p is None:
        out["why_not"] = "cannot_pass"
        return out

    # The mover's best defence after the reply.
    base_p, defence_p_san = None, None
    if base_played and base_played.get("score") and (base_played.get("line_san") or [None])[0] == reply_san:
        base_p = score_cp(base_played["score"])
        defence_p_san = (list(base_played["line_san"]) + [None])[1]
    if base_p is None:
        defence = _best(session, chess.Board(tp.fen()), "threat_defence_played", depth=depth)
        base_p = score_cp(defence["score"]) if defence else None
        defence_p_san = defence["moves_san"][0] if defence else None
    threat = _best(session, pass_p, "threat_after_pass_played", depth=depth)
    if base_p is None or threat is None:
        out["why_not"] = "search_unavailable"
        return out
    t_p = score_cp(threat["score"])
    t_move = chess.Move.from_uci(threat["root_uci"])
    t_san = threat["moves_san"][0]
    out.update(threat_san=t_san, threat_line_san=list(threat["moves_san"][:8]),
               base_played_cp=base_p, pass_played_cp=t_p, threat_cp=base_p - t_p)
    # A threat made by the reply piece is no threat when the best defence
    # simply takes that piece: 2d86e1f9 m17, after Rf8 Nxf6 the defence is
    # gxf6 and "Nxf6 threatens Nh7+" named a move the knight never lives to
    # make. A pass skips the recapture, so the pass line cannot see this.
    if t_move.from_square == reply.to_square and _takes_on(tp, defence_p_san, reply.to_square):
        out["why_not"] = "defence_takes_the_reply"
        return out

    mate_n = None
    if threat["score"]["kind"] == "mate" and int(threat["score"]["value"]) < 0:
        mate_n = abs(int(threat["score"]["value"]))
    material = None if mate_n else _material(pass_p, list(threat["moves_san"]), mover)
    if mate_n is not None and mate_n > MATE_MAX_MOVES:
        out["why_not"] = "mate_too_far"
        return out
    if mate_n is None and base_p - t_p < THREAT_MIN_CP:
        out["why_not"] = "pass_costs_little"
        return out
    if mate_n is None and material is None:
        out["why_not"] = "threat_not_material_or_mate"
        return out

    # The same threat after the better move and the same reply.
    if reply not in after_a.legal_moves:
        out["why_not"] = "reply_not_on_better_branch"
        return out
    ta = after_a.copy(stack=False)
    ta.push(reply)
    pass_a = _passed(ta)
    if pass_a is None:
        out["why_not"] = "cannot_pass_on_better_branch"
        return out
    takes_reply_a = False
    if t_move in pass_a.legal_moves:
        defence_a = _best(session, chess.Board(ta.fen()), "threat_defence_better", depth=depth)
        same = _best(session, pass_a, "threat_after_pass_better", depth=depth, roots=[t_move])
        if defence_a is None or same is None:
            out["why_not"] = "search_unavailable"
            return out
        base_a, t_a = score_cp(defence_a["score"]), score_cp(same["score"])
        out.update(base_better_cp=base_a, pass_better_cp=t_a, threat_better_cp=base_a - t_a,
                   threat_line_better_san=list(same["moves_san"][:8]))
        mated_a = same["score"]["kind"] == "mate" and int(same["score"]["value"]) < 0
        # After the better move the defence takes the reply piece: the threat
        # is met there, whatever a pass would allow (c31e86a3 m15: after Na6
        # Nc7 the defence is Nxc7; after Nc6 nothing can take on c7).
        takes_reply_a = (t_move.from_square == reply.to_square
                         and _takes_on(ta, defence_a["moves_san"][0], reply.to_square))
        out["defence_takes_reply_after_better_move"] = takes_reply_a
        # A pass hands the opponent a free move, so the eval drops on both
        # branches; what the sentence claims is that T wins material (or
        # mates), so that is what must be absent after the better move
        # (codex_bxd5: after exd5 Nxd5, Qxg5 is met by Bxd5 and nothing is won,
        # though the eval still falls by more than two pawns).
        if mate_n is not None:
            same_threat = mated_a or base_a - t_a >= THREAT_MIN_CP
        else:
            same_threat = mated_a or (base_a - t_a >= THREAT_MIN_CP
                                      and _material(pass_a, list(same["moves_san"]), mover) is not None)
        if same_threat and not takes_reply_a:
            out["why_not"] = "same_threat_after_better_move"
            return out
    else:
        out["threat_better_cp"] = None
        out["threat_illegal_after_better_move"] = True

    played_san, alt_san = root.san(played), root.san(alternative)
    own = "your" if mover_is_user else "their"
    if mate_n is not None:
        first = (f"After {played_san}, {reply_san} threatens {t_san}, which is mate." if mate_n == 1 else
                 f"After {played_san}, {reply_san} threatens {t_san}, and mate follows.")
        victim_piece, victim_square, mechanism, captures = "king", None, "MATE", []
    else:
        from .differential import _pieces_phrase
        g, hit = material["group"], material["hit"]
        lost = _pieces_phrase(g["mover_lost"], article=False)
        if g["mover_won"]:
            first = (f"After {played_san}, {reply_san} threatens {t_san}, which wins {own} {lost} on {g['square']} "
                     f"for {_pieces_phrase(g['mover_won'])}.")
        elif hit["ply"] == 0:
            first = f"After {played_san}, {reply_san} threatens {t_san}, taking {own} {lost} on {g['square']}."
        else:
            first = f"After {played_san}, {reply_san} threatens {t_san}, which wins {own} {lost} on {g['square']}."
        from .differential import _dearest
        victim_piece, victim_square, mechanism = _dearest(g["mover_lost"]), g["square"], "WINS_MATERIAL"
        captures = [p["san"] for p in g["plies"]]

    # Why it fails after the better move, when the board shows it plainly.
    reason, guard = None, None
    sq = t_move.to_square
    sname = chess.square_name(sq)
    # A guard the better move adds, not "the square had no guard": in ho05 and
    # ho08 the king guards f2 on both branches, and Rxc2's rook is the guard
    # that makes Qxf2+ fail.
    # And one more guard than after the played move: in 3823bc89 m12 Bb2 and
    # Bd2 both guard c3, and Bd2's point is the pin it blocks, which "your
    # bishop guards c3" would misstate.
    guards_a, guards_p = ta.attackers(mover, sq), tp.attackers(mover, sq)
    if len(guards_a) > len(guards_p):
        if alternative.to_square in guards_a and alternative.to_square not in guards_p:
            piece = PIECE_NAME[ta.piece_at(alternative.to_square).piece_type]
            reason = f"After {alt_san}, {own} {piece} guards {sname}."
            guard = {"by": "better_move", "piece": piece, "from": chess.square_name(alternative.to_square)}
        # Not when the played move lands ON the threatened square: then the
        # piece is the target, not a guard that left (18.Qd2, local engine:
        # "Qd2 stops your queen guarding d2" about the queen standing on d2).
        elif (played.from_square in guards_a and played.to_square not in guards_p
              and played.to_square != sq):
            piece = PIECE_NAME[root.piece_at(played.from_square).piece_type]
            reason = f"{played_san} stops {own} {piece} guarding {sname}."
            guard = {"by": "played_move_left", "piece": piece, "from": chess.square_name(played.from_square)}
    # Otherwise, when the threat is met by taking the reply piece after the
    # better move, say who guards the reply's square (c31e86a3 m15: "After
    # Na6, your knight guards c7"). Second, because a guard on the threat's
    # own square says more where both hold (ho05: Rxc2's rook guards f2 and c5).
    rsq = reply.to_square
    if reason is None and takes_reply_a and alternative.to_square in ta.attackers(mover, rsq) \
            and alternative.to_square not in tp.attackers(mover, rsq):
        piece = PIECE_NAME[ta.piece_at(alternative.to_square).piece_type]
        reason = f"After {alt_san}, {own} {piece} guards {chess.square_name(rsq)}."
        guard = {"by": "better_move", "piece": piece, "from": chess.square_name(alternative.to_square),
                 "square": chess.square_name(rsq)}

    text = first if reason is None else f"{first} {reason}"
    consequence = {"mechanism": mechanism, "direction": "received", "agent_move": t_san,
                   "victim_piece": victim_piece, "victim_square": victim_square, "square": victim_square,
                   "captures": captures, "payoff_cp": base_p - t_p, "series": False, "text": None}
    out.update(fires=True, why_not=None, mate_in=mate_n, guard=guard,
               cause={"kind": "threat", "variant": "threat", "reply": reply_san, "threat_san": t_san,
                      "threat_square": sname, "piece": victim_piece, "square": victim_square,
                      "owner": own, "guard": guard, "text": text, "consequence": consequence})
    return out
