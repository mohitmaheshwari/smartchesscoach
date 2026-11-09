"""Import fills time_control_category and opponent_rating, never replacing a value.

Only a backfill script ever called derive_context_fields, so on 2026-11-09
13,311 games had no opponent_rating and 13,339 no time_control_category, and
the academy backfill's bullet skip never fired on a fresh import.
"""
from pathlib import Path

from services.game_context_enricher import fill_missing_context

PGN = ('[Event "Live Chess"]\n[WhiteElo "1150"]\n[BlackElo "1210"]\n'
       '[TimeControl "60"]\n\n1. e4 e5 *')
BACKEND = Path(__file__).resolve().parent.parent


def test_a_bare_import_gets_category_and_opponent_rating():
    doc = {"pgn": PGN, "user_color": "white"}
    added = fill_missing_context(doc)
    assert doc["time_control_category"] == "bullet"
    assert doc["opponent_rating"] == 1210
    assert doc["rating_gap"] == -60
    assert set(added) >= {"time_control_category", "opponent_rating"}


def test_a_stored_value_is_never_replaced():
    doc = {"pgn": PGN, "user_color": "black", "time_control": "rapid",
           "time_control_category": "rapid", "white_rating": 1149}
    fill_missing_context(doc)
    assert doc["time_control_category"] == "rapid"
    assert doc["white_rating"] == 1149
    assert doc["opponent_rating"] == 1150  # from the PGN, since none was stored


def test_user_rating_is_left_to_the_resolver():
    doc = {"pgn": PGN, "user_color": "white"}
    fill_missing_context(doc)
    assert "user_rating" not in doc


def test_both_import_paths_call_it():
    for rel in ("journey_service.py", "routes/analysis.py"):
        src = (BACKEND / rel).read_text(encoding="utf-8")
        assert "fill_missing_context(" in src, f"{rel} imports games without the context fields"
