import chess

from scripts.adjudicate_whole_game_teaching_development import (
    _fork_targets,
    _safe_missed_capture,
    adjudicate_evidence,
)


def _evidence(fen, played, best, *, played_line=(), best_line=()):
    board = chess.Board(fen)
    played_move = board.parse_san(played)
    best_move = board.parse_san(best)
    return {
        "fen_before": fen,
        "played_san": played,
        "played_uci": played_move.uci(),
        "best_move_san": best,
        "best_move_uci": best_move.uci(),
        "pv_after_played": list(played_line),
        "pv_after_best": list(best_line),
    }


def test_proves_an_immediate_loose_piece_without_calling_equal_trade_a_loss():
    loose = _evidence(
        "4k3/8/8/8/8/8/3r4/3QK3 w - - 0 1",
        "Kf1",
        "Qxd2",
        played_line=("Rxd1+",),
    )
    equal_trade = _evidence(
        "8/8/8/8/8/2k5/3r4/3R3K w - - 0 1",
        "Rxd2",
        "Rxd2",
        played_line=("Kxd2",),
    )

    assert adjudicate_evidence(loose)["cause_family"] == "immediate_material_loss"
    assert adjudicate_evidence(equal_trade)["evidence_verdict"] == "unsupported"


def test_safe_missed_capture_rejects_an_immediate_recapture():
    safe = "4k3/8/8/8/8/8/3r4/3QK3 w - - 0 1"
    traded = "4k3/8/8/8/8/2k5/3r4/3QK3 w - - 0 1"

    assert _safe_missed_capture(safe, "d1d2")["piece"] == "rook"
    assert _safe_missed_capture(traded, "d1d2") is None


def test_detects_only_a_forking_move_that_cannot_be_taken_immediately():
    safe = "8/8/8/1q6/4k3/8/8/3NK2R w K - 0 1"
    unsafe = "8/8/8/1q6/1p2k3/8/8/3NK2R w K - 0 1"

    targets = _fork_targets(safe, "d1c3")
    assert {item["piece"] for item in targets} == {"queen", "king"}
    assert _fork_targets(unsafe, "d1c3") == []


def test_forced_mate_is_proved_from_legal_stored_line():
    evidence = _evidence(
        "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1",
        "Qe7",
        "Qg7#",
    )
    verdict = adjudicate_evidence(evidence)
    assert verdict["cause_family"] == "missed_forced_mate"
    assert verdict["critical_false_claim"] is False
