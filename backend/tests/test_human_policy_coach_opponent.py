from __future__ import annotations

import chess
import chess.engine

from coach_play.coach_blunder_guard import (
    move_is_free_hang,
    select_sound_coach_move,
)
from coach_play.coach_opponent import session_history_to_uci


class FakeEvidence:
    def __init__(self, order):
        self.order = tuple(order)

    def rank_verified_candidates(self, candidates):
        allowed = set(candidates)
        return tuple(move for move in self.order if move in allowed)


class FakeEngine:
    def __init__(self, infos=None, *, fail=False):
        self.infos = infos or []
        self.fail = fail

    def analyse(self, board, limit, multipv=None):
        if self.fail:
            raise RuntimeError("engine unavailable")
        return self.infos


def info(board, uci, cp):
    return {
        "pv": [chess.Move.from_uci(uci)],
        "score": chess.engine.PovScore(chess.engine.Cp(cp), board.turn),
    }


def test_human_policy_ranks_only_full_strength_safe_candidates():
    board = chess.Board("4r1k1/8/8/8/8/8/P2Q4/6K1 w - - 0 1")
    unsafe = chess.Move.from_uci("d2e2")
    safe = chess.Move.from_uci("d2c3")
    best = chess.Move.from_uci("d2a5")
    assert move_is_free_hang(board, unsafe)
    assert not move_is_free_hang(board, safe)
    engine = FakeEngine([
        info(board, best.uci(), 80),
        info(board, safe.uci(), 20),
        info(board, unsafe.uci(), -50),
    ])
    selected, changed = select_sound_coach_move(
        engine,
        board,
        best,
        human_policy_evidence=FakeEvidence((unsafe.uci(), safe.uci(), best.uci())),
    )
    assert selected == safe
    assert changed is True


def test_no_engine_truth_means_no_human_policy_override_and_static_hang_floor_survives():
    board = chess.Board("4r1k1/8/8/8/8/8/P2Q4/6K1 w - - 0 1")
    unsafe = chess.Move.from_uci("d2e2")
    selected, changed = select_sound_coach_move(
        FakeEngine(fail=True),
        board,
        unsafe,
        human_policy_evidence=FakeEvidence((unsafe.uci(),)),
    )
    assert selected != unsafe
    assert changed is True
    assert not move_is_free_hang(board, selected)


def test_session_history_is_used_only_when_it_reaches_the_exact_fen():
    board = chess.Board()
    board.push_san("e4")
    board.push_san("e5")
    entries = [
        {"move": "e4", "by": "user"},
        {"uci": "e7e5", "by": "coach"},
    ]
    assert session_history_to_uci(entries, board.fen()) == ("e2e4", "e7e5")
    assert session_history_to_uci(entries[:1], board.fen()) == ()
    assert session_history_to_uci([{"move": "not-a-move"}], board.fen()) == ()
