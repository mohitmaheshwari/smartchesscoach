from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.narrator_claim_verifier import verify_caption as _verify_caption
from services.caption_templates import dispatch_promotion, reload_promotion_ladder


ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = (
    ROOT
    / "data"
    / "detector_gold"
    / "personalized_review_ten_game_gold_v1.json"
)


def verify_caption(caption: str, facts: dict):
    """All checks in this file exercise the explicit Quality V2 verifier."""
    return _verify_caption(caption, facts, strict_v2=True)


def _gold() -> dict:
    return json.loads(GOLD_PATH.read_text(encoding="utf-8"))


def _facts(case: dict) -> dict:
    return {
        "fen_before": case["fen_before"],
        "move_san": case["move_san"],
        "best_move_san": case["best_move_san"],
        "pv_after_played": case["pv_after_played"],
        "pv_after_best": case["pv_after_best"],
        "cp_loss": case["cp_loss"],
        "is_user_move": True,
    }


def test_gold_has_ten_unique_game_labels_and_no_runtime_override_permission():
    gold = _gold()
    labels = gold["main_moment_labels"]
    assert len(labels) == 10
    assert len({item["game_id"] for item in labels}) == 10
    assert gold["runtime_game_id_overrides_forbidden"] is True


@pytest.mark.parametrize(
    "case",
    _gold()["false_claim_cases"],
    ids=lambda case: case["case_id"],
)
def test_every_documented_false_claim_is_rejected_by_shared_verifier(case):
    violations = verify_caption(case["caption"], _facts(case))
    checks = {item.get("check") for item in violations}
    assert case["expected_violation"] in checks, violations


def test_narrow_truthful_caption_remains_accepted():
    case = _gold()["false_claim_cases"][0]
    caption = (
        "Bh6 left your rook on a1 available to the knight on c2. "
        "Rd1 moves the rook away before Nxa1."
    )
    assert verify_caption(caption, _facts(case)) == []


def test_real_sacrifice_remains_accepted():
    facts = {
        "fen_before": "6k1/7p/8/8/8/8/2B5/6K1 w - - 0 1",
        "move_san": "Bxh7+",
        "best_move_san": "Bxh7+",
        "pv_after_played": ["Kxh7"],
        "pv_after_best": ["Kxh7"],
        "cp_loss": 0,
        "is_user_move": True,
    }
    assert verify_caption(
        "Bxh7+ sacrifices your bishop to pull the king onto h7.", facts
    ) == []


def test_real_material_loss_remains_accepted():
    facts = {
        "fen_before": "k3r3/8/8/8/8/8/8/3Q2K1 w - - 0 1",
        "move_san": "Qe2",
        "best_move_san": "Qd2",
        "pv_after_played": ["Rxe2"],
        "pv_after_best": [],
        "cp_loss": 900,
        "is_user_move": True,
    }
    assert verify_caption("Qe2 hands material away to Rxe2.", facts) == []


def test_real_forcing_move_remains_accepted():
    facts = {
        "fen_before": "6k1/8/8/8/8/8/8/3Q2K1 w - - 0 1",
        "move_san": "Qd4",
        "best_move_san": "Qg4+",
        "pv_after_played": [],
        "pv_after_best": [],
        "cp_loss": 100,
        "is_user_move": True,
    }
    assert verify_caption("Qg4+ is a forcing move.", facts) == []


@pytest.mark.parametrize(
    ("caption", "facts"),
    (
        (
            (
                "Rg4 missed the finish because the line Nf4+, Kh6, "
                "Nf5# ends in checkmate."
            ),
            {
                "fen_before": "r5nr/pp4pp/n2N4/3N3k/7b/4BP2/PPP5/6RK w - - 2 26",
                "move_san": "Rg4",
                "best_move_san": "Nf4+",
                "pv_after_played": ["Rf8", "Rxg7", "Rxf3", "Kg2"],
                "pv_after_best": ["Kh6", "Nf5#"],
                "cp_loss": 10173,
                "is_user_move": True,
            },
        ),
        (
            (
                "Rd2 fails because it allows Qg4#, which is checkmate. "
                "Qf3 stopped that immediate finish."
            ),
            {
                "fen_before": "8/p1p2p1p/6p1/6Pk/2Q5/P6P/KPP2q2/3r4 b - - 4 30",
                "move_san": "Rd2",
                "best_move_san": "Qf3",
                "pv_after_played": ["Qg4#"],
                "pv_after_best": ["Qxc7", "Rf1", "Qc4", "Rf2"],
                "cp_loss": 10608,
                "is_user_move": True,
            },
        ),
    ),
)
def test_complete_stored_mating_line_remains_accepted(caption, facts):
    assert verify_caption(caption, facts) == []


def test_explicit_mate_must_be_the_terminal_move_of_a_complete_stored_branch():
    facts = {
        "fen_before": "r5nr/pp4pp/n2N4/3N3k/7b/4BP2/PPP5/6RK w - - 2 26",
        "move_san": "Rg4",
        "best_move_san": "Nf4+",
        "pv_after_played": ["Rf8", "Rxg7", "Rxf3", "Kg2"],
        "pv_after_best": ["Kh6", "Nf5#"],
        "cp_loss": 10173,
        "is_user_move": True,
    }
    violations = verify_caption("Nf4# is checkmate.", facts)
    assert {item["check"] for item in violations} == {"mate"}


@pytest.mark.parametrize(
    ("caption", "facts"),
    [
        (
            "Rc8 missed material because the line Ne5, e4, fxe4 takes the pawn on e4.",
            {
                "fen_before": "4r1k1/7p/R1p3p1/1p1q1p2/1PnP4/2BQP1P1/5P1P/6K1 b - - 7 33",
                "move_san": "Rc8",
                "best_move_san": "Ne5",
                "pv_after_played": ["Qe2", "Re8", "Qa2", "h5"],
                "pv_after_best": ["e4", "fxe4", "Qe2", "Nf3+"],
                "is_user_move": True,
            },
        ),
        (
            "Qh6+ missed material because the line Qd8+, Kc6, Rf1, a1=Q, Rxa1 takes the queen on a1.",
            {
                "fen_before": "7Q/3n4/1k6/1p3R2/8/2P5/p5P1/6K1 w - - 0 43",
                "move_san": "Qh6+",
                "best_move_san": "Qd8+",
                "pv_after_played": ["Kc7", "Rf1", "Kb8", "Ra1"],
                "pv_after_best": ["Kc6", "Rf1", "a1=Q", "Rxa1"],
                "is_user_move": True,
            },
        ),
    ],
)
def test_capture_piece_square_is_verified_at_its_stored_line_ply(caption, facts):
    assert verify_caption(caption, facts) == []


def test_capture_phrase_does_not_excuse_wrong_piece_on_stored_capture_square():
    facts = {
        "fen_before": "4r1k1/7p/R1p3p1/1p1q1p2/1PnP4/2BQP1P1/5P1P/6K1 b - - 7 33",
        "move_san": "Rc8",
        "best_move_san": "Ne5",
        "pv_after_played": ["Qe2", "Re8", "Qa2", "h5"],
        "pv_after_best": ["e4", "fxe4", "Qe2", "Nf3+"],
        "is_user_move": True,
    }
    violations = verify_caption(
        "Ne5, e4, fxe4 takes the knight on e4.",
        facts,
    )
    assert any(item["check"] == "piece_on_square" for item in violations)


def test_past_tense_capture_piece_is_verified_on_the_played_move():
    facts = {
        "fen_before": "1r4nr/ppk3p1/2p2pQ1/7p/1B1p2bP/3P4/PP4P1/R2QR1K1 w - - 1 23",
        "move_san": "Qdxg4",
        "best_move_san": "Qxg7+",
        "pv_after_played": ["hxg4", "Qxg7+", "Kb6", "Qxh8"],
        "pv_after_best": ["Ne7", "Ba5+", "b6", "Rxe7+"],
        "is_user_move": True,
    }
    assert verify_caption(
        "Qdxg4 won the bishop on g4, but hxg4 then won your queen on g4.",
        facts,
    ) == []


def test_unreconstructable_board_is_not_treated_as_verified():
    violations = verify_caption(
        "This is a forcing move.",
        {
            "fen_before": "not-a-fen",
            "move_san": "Qh5+",
            "best_move_san": "Qh5+",
            "pv_after_played": [],
            "pv_after_best": [],
            "is_user_move": True,
        },
    )
    assert {item["check"] for item in violations} == {"unverified_board"}


def test_opening_knowledge_cannot_overwrite_a_concrete_move_explanation():
    reload_promotion_ladder()
    facts = {
        "caption_empty": False,
        "move_san": "Bc4",
        "opening_intro_name": "Italian Game direction",
        "opening_intro_idea": "Aims at f7. Classic development.",
        "opening_theory_name": "Italian Game",
        "opening_theory_match_quality": "best",
        "opening_theory_played_why_good": "Classic development.",
        "opening_record": {"name": "Italian Game", "summary": "Develop quickly."},
    }
    assert dispatch_promotion(facts) == (None, None)


def test_opening_knowledge_still_fills_an_empty_caption():
    reload_promotion_ladder()
    facts = {
        "caption_empty": True,
        "move_san": "Nf3",
        "opening_intro_name": "Italian Game direction",
        "opening_intro_idea": "Develops a piece and prepares to castle.",
        "opening_record": {},
    }
    text, source = dispatch_promotion(facts)
    assert "Italian Game direction" in text
    assert source == "R_PROMOTED_opening_intro"


def test_gold_game_ids_are_not_embedded_in_runtime_services():
    service_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (ROOT / "services").rglob("*.py")
    )
    for label in _gold()["main_moment_labels"]:
        assert label["game_id"] not in service_text
