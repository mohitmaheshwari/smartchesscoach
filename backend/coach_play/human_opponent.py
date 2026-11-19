"""A human-move opponent for Play with Coach (docs/coaching_intelligence_scope.md, 1c).

The opponent players actually meet in coach mode ranks full-strength depth-10
lines; players under 1000 scored 0 of 45 real games against it (2026-11-18).
This opponent plays the way a person at the player's own rating plays: each
move is sampled from Maia-2's distribution of what such a player plays in
this position, so its mistakes are human-shaped (a natural but loose move, a
missed defence), not engine noise.

No engine veto and no "punish" rule: a person at that rating does not always
take a free piece, and an opponent that always does is not that person. The
only cut is Maia's extreme tail (TAIL_CUTOFF), set from how much of real play
sits there in our players' games (calibration of 2026-11-19, below).

Behind PWC_HUMAN_OPPONENT_USERS (comma list of user ids, or "*"). Off for
everyone else. If Maia is unavailable the caller falls back to the existing
opponent, so a game can never stall on this.
"""
from __future__ import annotations

import logging
import os
import random
from typing import Any, Dict, Optional

import chess

logger = logging.getLogger(__name__)

FLAG_ENV = "PWC_HUMAN_OPPONENT_USERS"
VERSION = "human_opponent.v1"
# Moves Maia gives less than this are never sampled. Calibration on 1,200 real
# moves from our players (2026-11-19): Maia is well calibrated (moves it gives
# 1-10% were played 3.6% of the time against 3.5% predicted). Real players make
# moves under 1% 0.7-5% of the time by band, so a 1% veto would delete real
# play; under 0.2% holds 0-1.3% of real moves. Hence 0.2%.
TAIL_CUTOFF = 0.002
MAIA_TOP_K = 200
_MAIA: Any = None


def enabled_for(user_id: Optional[str]) -> bool:
    if not user_id:
        return False
    ids = {x.strip() for x in os.environ.get(FLAG_ENV, "").split(",") if x.strip()}
    return "*" in ids or user_id in ids


def _maia():
    global _MAIA
    if _MAIA is None:
        from services.human_behavior_engine import Maia2Provider

        path = os.environ.get("MAIA2_MODEL_PATH")
        _MAIA = Maia2Provider(model_path=path) if path else False
        if _MAIA:
            # The backend container has no CPU quota, so the provider's
            # quota-based cap does not apply and torch spreads one tiny
            # inference over every core of a shared box: measured on prod
            # 2026-11-19, median 5.2 s and up to 25 s per move. One thread is
            # the measured fast case (0.11 s per position, human_behavior_engine).
            try:
                import torch

                torch.set_num_threads(1)
            except Exception:
                logger.warning("human opponent: could not pin torch to one thread")
    return _MAIA or None


def sample(distribution: Dict[str, float], rng: random.Random, cutoff: float = TAIL_CUTOFF) -> Optional[str]:
    """One move from a {uci: probability} distribution, its tail below
    `cutoff` removed and the rest renormalised. Pure, for tests."""
    kept = {m: p for m, p in distribution.items() if p >= cutoff}
    if not kept:
        kept = {max(distribution, key=distribution.get): 1.0} if distribution else {}
    if not kept:
        return None
    moves, weights = zip(*kept.items())
    return rng.choices(moves, weights=weights, k=1)[0]


def choose_move(fen: str, target_rating: int, player_rating: int,
                rng: Optional[random.Random] = None) -> Optional[Dict[str, Any]]:
    """The opponent's move, or None (caller falls back). Blocking: run it in
    an executor. `target_rating` is the strength played at; in v1 it is the
    player's own rating (no floor), adapted later from results."""
    maia = _maia()
    if maia is None:
        return None
    from services.human_behavior_engine import MoveContext

    try:
        board = chess.Board(fen)
        dist = maia.predict(MoveContext(fen=fen, player_elo=int(target_rating), opponent_elo=int(player_rating)),
                            top_k=MAIA_TOP_K)
    except Exception:
        logger.exception("human opponent: Maia failed")
        return None
    if not dist:
        return None
    legal = {m.uci(): (dist.probability_of(m.uci()) or 0.0) for m in board.legal_moves}
    total = sum(legal.values())
    if total <= 0:
        return None
    legal = {m: p / total for m, p in legal.items()}
    uci = sample(legal, rng or random.Random())
    if not uci:
        return None
    ranked = sorted(legal, key=legal.get, reverse=True)
    return {
        "san": board.san(chess.Move.from_uci(uci)),
        "uci": uci,
        "probability": round(legal[uci], 4),
        "rank": ranked.index(uci) + 1,
        "legal_moves": len(legal),
        "target_rating": int(target_rating),
        "version": VERSION,
    }


def teaching_context(choice: Dict[str, Any]) -> Dict[str, Any]:
    """What the coach-play routes read after a move. Natural play: no
    teaching intent, no claim that the move is best."""
    return {
        "teaching_goal": "natural_play",
        "move_type": "human_policy",
        "is_best_move": None,
        "v2": False,
        "why_instructive": "",
        "human_policy": {"used": True, "reason": VERSION, "chess_authority": False,
                         "probability": choice.get("probability"), "rank": choice.get("rank"),
                         "target_rating": choice.get("target_rating")},
    }
