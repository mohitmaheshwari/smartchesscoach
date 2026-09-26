"""The "Why" button: pick the good move that explains itself.

The problem this exists to solve
--------------------------------
Every other caption path computes the why under a page-render deadline.
When it cannot derive a reason it still has to emit a sentence, so it
emits one it does not know. Measured 2026-09-25 on 441 fresh mistake
captions: 25.6% named the punishment, 51.5% described only the
alternative move, 22.9% did neither. Rewording variant files cannot fix
that, because the shortage is of *derivable reasons*, not of prose.

Behind a button the deadline goes away. So instead of taking the
engine's single best move and struggling to explain it, we ask for
several good moves and keep the first one we can explain from the
board. Settings and their measurements are in
docs/why_button_scope.md; the short version, on 40 positions, server,
Threads=1: depth 18 / 8 candidates costs 5.5s median and leaves ~10%
with nothing explainable.

That remainder is the point of the design, not a defect. explain()
returns None there and the caller must say so. Manufacturing a sentence
for those positions is the bug we are removing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

import chess

from services.punishment_resolver import (
    Punishment,
    _line_material_gain,
    resolve_missed,
    resolve_received,
)

logger = logging.getLogger(__name__)

# How many engine candidates to consider. 8, not 4: top-4 halves the wait
# but doubles the share of positions with nothing explainable (18% vs 10%),
# and that share is exactly the bucket that produces invented captions.
CANDIDATE_COUNT = 8

# Matches the depth the stored analysis already uses, so a candidate's
# evaluation here is comparable with the cp_loss on the card.
CANDIDATE_DEPTH = 18

# We will not recommend a move that is materially worse than the engine's
# best just because it made a tidier story. Measured: the best move is
# itself explainable 25/36 times, and 31/36 land inside this bound.
CLOSENESS_CP = 50


def _phrase(p: Punishment, played_san: str) -> Optional[str]:
    """One plain sentence. Short words, one idea, no numbers.

    Returns None for a mechanism we have no honest sentence for, which
    the caller treats exactly like no punishment at all.
    """
    # No silent fallback to the word "piece". If the resolver could not
    # name what was lost, we say "material" -- vaguer, but not a word
    # pretending to carry information it does not have.
    named = (p.victim_piece or "").strip().lower()
    piece = named or "piece"
    agent = p.agent_move

    if p.direction == "received":
        if p.mechanism == "MATE":
            return f"After {played_san}, {agent} leads to mate."
        if p.mechanism == "WINS_MATERIAL":
            if named:
                return f"After {played_san}, {agent} wins your {named}."
            return f"After {played_san}, {agent} wins material."
        if p.mechanism == "FORK":
            return (f"After {played_san}, {agent} attacks two things at once. "
                    f"You cannot save both.")
        if p.mechanism == "TRAPPED":
            where = f" on {p.victim_square}" if p.victim_square else ""
            return (f"After {played_san}, your {piece}{where} has no safe "
                    f"square left.")
        if p.mechanism == "PROMOTES":
            return (f"After {played_san}, their pawn runs through and "
                    f"becomes a queen.")
        if p.mechanism == "FORCES_RETREAT":
            back = (" straight back to where it came from"
                    if p.returns_home else "")
            return f"After {played_san}, {agent} chases your {piece}{back}."
        return None

    # direction == "missed": what the better move would have collected.
    if p.mechanism == "MATE":
        return f"{agent} leads to mate."
    if p.mechanism == "WINS_MATERIAL":
        if named:
            return f"{agent} wins their {named}."
        return f"{agent} wins material."
    if p.mechanism == "FORK":
        return f"{agent} attacks two things at once. They cannot save both."
    if p.mechanism == "TRAPPED":
        where = f" on {p.victim_square}" if p.victim_square else ""
        return f"{agent} leaves their {piece}{where} with no safe square."
    if p.mechanism == "PROMOTES":
        return f"{agent} lets your pawn run through and become a queen."
    if p.mechanism == "FORCES_RETREAT":
        return f"{agent} drives their {piece} back."
    return None


def _arrows(fen_before: str, line_san: Sequence[str],
            limit: int = 3) -> List[Dict[str, str]]:
    """One arrow per move of the line we are showing, in board order.

    Built by pushing the moves, never by parsing the sentence -- the
    prose is downstream of the proof and must never be its source.
    """
    out: List[Dict[str, str]] = []
    try:
        board = chess.Board(fen_before)
    except ValueError:
        return out
    for san in list(line_san)[:limit]:
        try:
            mv = board.parse_san(str(san or "").strip())
        except (ValueError, AssertionError, KeyError):
            break
        out.append({
            "from": chess.square_name(mv.from_square),
            "to": chess.square_name(mv.to_square),
            "san": san,
        })
        board.push(mv)
    return out


def explain(
    fen_before: str,
    played_san: str,
    pv_after_played: Sequence[str],
    candidates: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Why the played move was bad, or None if we cannot honestly say.

    `candidates` is stockfish_service.get_candidate_lines() output for the
    position BEFORE the played move -- best first, each with line_san.

    Order of attack:
      1. What their reply actually collects. This is the most direct
         answer to "why was my move bad" and needs no alternative.
      2. Failing that, the best move we can explain, provided it is not
         materially worse than the engine's best.
      3. Failing that, None.
    """
    if not fen_before or not played_san:
        return None

    # 1. The punishment we took.
    got = resolve_received(fen_before, played_san, list(pv_after_played or []))
    if got is not None:
        text = _phrase(got, played_san)
        if text:
            return {
                "found": True,
                "direction": "received",
                "mechanism": got.mechanism,
                "text": text,
                "move_san": got.agent_move,
                # Punishment.line starts AFTER the agent move, and for this
                # direction the agent move is their reply -- which itself
                # comes after ours. From fen_before the board therefore
                # needs the played move and the reply prepended, or the
                # first SAN is illegal and no arrow is drawn at all. That
                # is exactly what shipped: a correct sentence with an
                # empty arrow list.
                "line_san": [played_san, got.agent_move] + list(got.line),
                "arrows": _arrows(
                    fen_before, [played_san, got.agent_move] + list(got.line)),
                "candidate_rank": None,
                "eval_gap_cp": 0,
                "payoff_cp": got.payoff_cp,
            }

    # 2. The opportunity we missed -- but only credit the better move with
    #    material the played move did not already win. Without this guard
    #    we tell the player a move "wins a knight" when theirs did too.
    baseline = max(0, _line_material_gain(
        fen_before, played_san, list(pv_after_played or [])))

    best_cp = None
    for cand in candidates or []:
        if cand.get("eval_cp") is not None:
            best_cp = cand["eval_cp"]
            break

    for rank, cand in enumerate(candidates or [], 1):
        line = [str(x).strip() for x in (cand.get("line_san") or [])
                if str(x or "").strip()]
        san = cand.get("move_san")
        if not line or not san or san == played_san:
            continue
        cp = cand.get("eval_cp")
        gap = (best_cp - cp) if (best_cp is not None and cp is not None) else 0
        if gap > CLOSENESS_CP:
            # candidates are sorted, so everything after this is worse too
            break
        missed = resolve_missed(fen_before, san, line,
                                material_baseline_cp=baseline)
        if missed is None:
            continue
        text = _phrase(missed, played_san)
        if not text:
            continue
        return {
            "found": True,
            "direction": "missed",
            "mechanism": missed.mechanism,
            "text": text,
            "move_san": missed.agent_move,
            # Same frame problem, one move shallower: the better move was
            # never played, so the line runs straight from fen_before.
            "line_san": [missed.agent_move] + list(missed.line),
            "arrows": _arrows(
                fen_before, [missed.agent_move] + list(missed.line)),
            "candidate_rank": rank,
            "eval_gap_cp": gap,
            "payoff_cp": missed.payoff_cp,
        }

    # 3. Nothing we can stand behind.
    return None
