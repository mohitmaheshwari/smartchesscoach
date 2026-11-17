"""The opportunity behind the better move, read from a Stockfish line.

Scope: docs/why_opportunity_line_scope.md (Mohit, 2026-11-17: "okay, go",
after "sometimes a mistake is because there was a better opportunity").

The mirror of threat_line.py. In the missed family no single reply of the
opponent carries the gap: the better move's line holds it. When the better
move is quiet, its point is the move after it, and the engine's line shows the
opponent's best defence against that move, not the move itself. The button
then had nothing to say from this side and fell back to the punish side (11 of
32 missed-family mistakes in the 2026-11-16 sample).

So: after the better move, let the opponent pass and ask Stockfish for the
mover's best move T and line. T is the opportunity when
  - after the pass, T scores clearly better for the mover than the better move
    itself, and its line wins material (exchange ledger) or mates;
  - after the played move and a pass, the same T does not win material or
    mate (a search restricted to T), or is not legal.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import chess

from .threat_line import (MATE_MAX_MOVES, THREAT_MIN_CP, _best, _material, _passed)

OPPORTUNITY_MIN_CP = THREAT_MIN_CP
# The material the threat wins must be at least the gap: a threat worth less
# than what the move cost cannot be the whole reason. At 0.5, ho02 read "Nc6
# threatens Nxa5, taking their pawn" on a 143 cp gap (416 at the judge's
# depth) whose cause is the queen trapped on a7; the hand-graded line after
# Nc6 is axb6, a defence, not a threat. All five other fires measured
# 2026-11-17 win at least the gap (200/148, 800/291, mate, 200/114).
OPPORTUNITY_GAP_SHARE = 1.0


def opportunity_line(session, root: chess.Board, played: chess.Move, alternative: chess.Move, *,
                     depth: int, mover_is_user: bool, alt_cp: Optional[int],
                     played_cp: Optional[int]) -> Dict[str, Any]:
    """{"fires": bool, "why_not": str|None, "answer": dict|None, measurements...}.

    `alt_cp` / `played_cp` are the root search's scores of the two moves, i.e.
    after the opponent's best defence. Every score is the session's, from the
    mover's side."""
    from .differential import score_cp
    out: Dict[str, Any] = {"fires": False, "why_not": None, "answer": None}
    if alt_cp is None or played_cp is None:
        out["why_not"] = "search_unavailable"
        return out
    gap_cp = alt_cp - played_cp
    mover, them = root.turn, not root.turn
    if root.gives_check(alternative):
        out["why_not"] = "better_move_is_check"
        return out
    if root.gives_check(played):
        out["why_not"] = "played_move_is_check"
        return out
    after_a, after_p = root.copy(stack=False), root.copy(stack=False)
    after_a.push(alternative)
    after_p.push(played)
    pass_a, pass_p = _passed(after_a), _passed(after_p)
    if pass_a is None or pass_p is None:
        out["why_not"] = "cannot_pass"
        return out

    threat = _best(session, pass_a, "opportunity_after_pass_better", depth=depth)
    if threat is None:
        out["why_not"] = "search_unavailable"
        return out
    t_a = score_cp(threat["score"])
    t_move = chess.Move.from_uci(threat["root_uci"])
    t_san = threat["moves_san"][0]
    out.update(threat_san=t_san, threat_line_san=list(threat["moves_san"][:8]),
               base_better_cp=alt_cp, pass_better_cp=t_a, threat_cp=t_a - alt_cp)

    mate_n = None
    if threat["score"]["kind"] == "mate" and int(threat["score"]["value"]) > 0:
        mate_n = int(threat["score"]["value"])
    if mate_n is not None and mate_n > MATE_MAX_MOVES:
        out["why_not"] = "mate_too_far"
        return out
    material = None if mate_n else _material(pass_a, list(threat["moves_san"]), them)
    if mate_n is None and t_a - alt_cp < OPPORTUNITY_MIN_CP:
        out["why_not"] = "pass_gains_little"
        return out
    if mate_n is None and material is None:
        out["why_not"] = "threat_not_material_or_mate"
        return out
    # The threat must be big enough to be the reason (OPPORTUNITY_GAP_SHARE).
    if material is not None:
        won = -material["group"]["net_cp"]
        out["threat_wins_cp"] = won
        if gap_cp and won < OPPORTUNITY_GAP_SHARE * gap_cp:
            out["why_not"] = "threat_smaller_than_gap"
            return out

    # After the played move, the opponent passing there too: does the mover
    # have the same thing? Two questions. Any move that wins on the same
    # square (or mates) means the threat was there anyway (mohit_qc2: Bd3
    # threatens Bxe4, and Qc2 threatens Qxe4 -- the same knight). And the same
    # move T, restricted, when it is legal there.
    free = _best(session, pass_p, "opportunity_after_pass_played", depth=depth)
    if free is None:
        out["why_not"] = "search_unavailable"
        return out
    out.update(base_played_cp=played_cp, free_played_san=list(free["moves_san"][:8]),
               free_played_cp=score_cp(free["score"]))
    if mate_n is not None:
        free_mates = free["score"]["kind"] == "mate" and 0 < int(free["score"]["value"]) <= MATE_MAX_MOVES
        if free_mates:
            out["why_not"] = "mate_there_after_played_move"
            return out
    else:
        free_material = _material(pass_p, list(free["moves_san"]), them)
        if free_material is not None and free_material["group"]["square"] == material["group"]["square"]:
            out["why_not"] = "same_square_won_after_played_move"
            return out

    if t_move in pass_p.legal_moves:
        same = free if free["root_uci"] == t_move.uci() else _best(
            session, pass_p, "opportunity_after_pass_played_t", depth=depth, roots=[t_move])
        if same is None:
            out["why_not"] = "search_unavailable"
            return out
        t_p = score_cp(same["score"])
        out.update(pass_played_cp=t_p, threat_played_cp=t_p - played_cp,
                   threat_line_played_san=list(same["moves_san"][:8]))
        mates_p = same["score"]["kind"] == "mate" and int(same["score"]["value"]) > 0
        # A pass hands the mover a free move on this branch too, so the eval
        # rises on both; what the sentence claims is that T wins material (or
        # mates), so that is what must be absent after the played move.
        if mate_n is not None:
            same_threat = mates_p or t_p - played_cp >= OPPORTUNITY_MIN_CP
        else:
            same_threat = mates_p or (t_p - played_cp >= OPPORTUNITY_MIN_CP
                                      and _material(pass_p, list(same["moves_san"]), them) is not None)
        if same_threat:
            out["why_not"] = "same_threat_after_played_move"
            return out
    else:
        out["threat_played_cp"] = None
        out["threat_illegal_after_played_move"] = True

    alt_san = root.san(alternative)
    their = "their" if mover_is_user else "your"
    if mate_n is not None:
        text = (f"{alt_san} was the move: it threatens {t_san}, which is mate." if mate_n == 1 else
                f"{alt_san} was the move: it threatens {t_san}, and mate follows.")
        victim_piece, victim_square, mechanism, captures = "king", None, "MATE", []
    else:
        from .differential import _dearest, _pieces_phrase
        g, hit = material["group"], material["hit"]
        lost = _pieces_phrase(g["mover_lost"], article=False)
        if g["mover_won"]:
            text = (f"{alt_san} was the move: it threatens {t_san}, which wins {their} {lost} on {g['square']} "
                    f"for {_pieces_phrase(g['mover_won'])}.")
        elif hit["ply"] == 0:
            text = f"{alt_san} was the move: it threatens {t_san}, taking {their} {lost} on {g['square']}."
        else:
            text = f"{alt_san} was the move: it threatens {t_san}, which wins {their} {lost} on {g['square']}."
        victim_piece, victim_square, mechanism = _dearest(g["mover_lost"]), g["square"], "WINS_MATERIAL"
        captures = [p["san"] for p in g["plies"]]

    consequence = {"mechanism": mechanism, "direction": "missed", "agent_move": alt_san, "threat_move": t_san,
                   "victim_piece": victim_piece, "victim_square": victim_square, "square": victim_square,
                   "captures": captures, "payoff_cp": t_a - alt_cp, "series": False, "text": None}
    out.update(fires=True, why_not=None, mate_in=mate_n,
               answer={"variant": "opportunity", "threat_san": t_san, "text": text, "consequence": consequence})
    return out
