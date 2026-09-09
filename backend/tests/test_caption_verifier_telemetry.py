from __future__ import annotations

import chess

from services.caption_pipeline import _verify_and_recover_caption


BASE = {
    "fen_before": chess.STARTING_FEN,
    "played_move": chess.Move.from_uci("e2e4"),
    "user_color": "white",
    "played_san": "e4",
    "best_move_san": "e4",
    "pv_after_best": [],
    "severity_practical": "good",
    "mover_is_user": True,
}


def test_caption_verifier_records_pass_for_supported_text():
    payload = {"caption": "e4 puts your pawn on e4.", "rule_name": "TEST"}
    result = _verify_and_recover_caption(caption_payload=payload, **BASE)
    assert result["verdict"] == "pass"
    assert payload["caption"] == "e4 puts your pawn on e4."


def test_caption_verifier_records_recovery_for_false_square_claim():
    payload = {"caption": "Your queen is on a7.", "rule_name": "TEST"}
    result = _verify_and_recover_caption(caption_payload=payload, **BASE)
    assert result["verdict"] == "fail_recovered"
    assert payload["caption"] == "e4."
    assert payload["rule_name"].endswith("R_VERIFIER_RECOVERY")


def test_empty_caption_has_explicit_neutral_verdict():
    result = _verify_and_recover_caption(
        caption_payload={"caption": "", "rule_name": "TEST"},
        **BASE,
    )
    assert result == {"verdict": "not_applicable", "reason": "empty_caption"}