"""A card graded good never shows a mistake sentence.

2026-11-11, game 2d86e1f9 move 4...Bc5: badge Good, caption "Nf6 would bring
out your knight ... Bc5 misses that chance". The analysis worker wrote a fault
caption for every 40cp+ move; the card graded with the player's level filter
(48cp under a 50-70cp explain threshold -> good). 574 of 10,557 user cards in
300 recent reviews had that contradiction.
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import framework  # noqa: E402
from services.llm_caption import build_facts  # noqa: E402
from services.severity import (  # noqa: E402
    is_fault_grade,
    level_softened,
    min_cp_explain_for_rating,
)

BC5_FEN = "r1bqk1nr/pppp1pp1/2n4p/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQ1RK1 w kq - 2 5"


def test_fault_grades_cover_both_sides():
    for t in ("inaccuracy", "mistake", "serious", "blunder",
              "opp_inaccuracy", "opp_blunder"):
        assert is_fault_grade(t), t
    for t in ("good", "context", "best", "", None):
        assert not is_fault_grade(t), t


def test_level_filter_matches_the_card_bands():
    assert [min_cp_explain_for_rating(r) for r in (900, 1300, 1500, 1800)] == [100, 70, 50, 30]
    assert min_cp_explain_for_rating(None) == 70      # profile missing -> 1200
    # Bc5: 48cp inaccuracy for a 1300 player reads as good; a mistake never does.
    assert level_softened("inaccuracy", 48, 70) == "good"
    assert level_softened("inaccuracy", 48, 30) == "inaccuracy"
    assert level_softened("mistake", 120, 100) == "mistake"


def _decide(monkeypatch, row, grade):
    decision = SimpleNamespace(
        text=SimpleNamespace(caption="", rule_name="R_FALLBACK"),
        teaching_meta=SimpleNamespace(severity=grade),
    )
    import services.caption_pipeline as cp
    monkeypatch.setattr(cp, "build_move_teaching_decision",
                        lambda *a, **k: decision)
    key = " ".join(BC5_FEN.split()[:4])
    return framework.decide(
        SimpleNamespace(fen_before=BC5_FEN), None,
        eval_lookup={key: row}, severity_override=grade)


FAULT_ROW = {"llm_caption": "Bc5 misses that chance.", "best_move": "Nf6", "cp_loss": 48}


def test_old_fault_sentence_is_dropped_on_a_good_card(monkeypatch):
    d = _decide(monkeypatch, dict(FAULT_ROW), "good")
    assert "misses" not in d.text.caption
    assert "LLM_CAPTION" not in d.text.rule_name


def test_fault_sentence_still_shows_on_a_fault_card(monkeypatch):
    d = _decide(monkeypatch, dict(FAULT_ROW), "inaccuracy")
    assert d.text.caption == "Bc5 misses that chance."


def test_good_alt_sentence_shows_only_on_a_good_card(monkeypatch):
    row = {"llm_caption": "That is a fine move. Nf6 was a little better.",
           "llm_caption_kind": "good_alt", "best_move": "Nf6", "cp_loss": 48}
    assert _decide(monkeypatch, dict(row), "good").text.caption.startswith("That is a fine move")
    assert _decide(monkeypatch, dict(row), "mistake").text.caption == ""


def test_opponent_fault_sentence_needs_an_opponent_fault_grade(monkeypatch):
    assert _decide(monkeypatch, dict(FAULT_ROW), "context").text.caption == ""
    assert _decide(monkeypatch, dict(FAULT_ROW), "opp_inaccuracy").text.caption


def test_writer_is_told_the_move_was_good():
    facts = build_facts("Bc5", "Nf6", [], mover_is_user=True, move_was_good=True)
    assert facts["your_move_was_good"] is True
    assert "how_bad" not in facts
    # Never for an opponent's move, and not by default.
    assert "your_move_was_good" not in build_facts("Bc5", "Nf6", [], mover_is_user=False, move_was_good=True)
    assert "your_move_was_good" not in build_facts("Bc5", "Nf6", [], mover_is_user=True)
