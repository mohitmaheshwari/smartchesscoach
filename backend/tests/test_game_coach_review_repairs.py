"""Regression tests for the six game-review repairs.

docs/game_review_repair_and_timeline_scope.md, part one. Each test names the
repair it guards and the real symptom it reproduces, so a future change that
reintroduces the defect fails here rather than in front of a player.

Run:
    python -m pytest backend/tests/test_game_coach_review_repairs.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.game_coach_review import (  # noqa: E402
    GOOD_QUALITY_VALUES,
    MATE_SENTINEL_CP,
    QUALITY_FIELD,
    _format_cp,
    _is_mate_swing,
    _title_for_caption,
    compose_story,
)
from services.game_coach_summary import (  # noqa: E402
    _blunder_cost_line,
    _cp_to_pieces,
    _describe_opponent,
    compute_game_summary,
)


# --------------------------------------------------------------------------
# A minimal game. Four user moves, one of them a 300cp blunder so the story
# clears PRINCIPLE_CP_FLOOR, all with white to move in fen_before so the
# summary's side-detection reads them as the user's.
# --------------------------------------------------------------------------
def _row(mn, san, cp, **kw):
    row = {
        "move_number": mn,
        "move": san,
        "cp_loss": cp,
        "best_move": "d4",
        "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "eval_before": 20,
        "eval_after": 20 - cp,
        QUALITY_FIELD: "best" if cp == 0 else "blunder",
        "cognitive_gap": None if cp == 0 else "piece_safety",
    }
    row.update(kw)
    return row


def _game(extra=None):
    evs = [
        _row(6, "Nf3", 0),
        _row(7, "Bc4", 0),
        _row(8, "b4", 300),
        _row(9, "O-O", 0),
    ]
    if extra:
        evs.extend(extra)
    return evs


# ── Repair 1.1 — strengths, and the contract that guards the key ───────────

def test_1_1_quality_field_name_matches_the_stored_schema():
    """The symptom: good_moves was [] on every game ever rendered, because
    the filter read `classification` and no stored row has that key."""
    assert QUALITY_FIELD == "evaluation"
    assert "best" in GOOD_QUALITY_VALUES


def test_1_1_good_moves_is_populated():
    out = compose_story(_game(), "0-1", "white", "Italian Game")
    assert out is not None
    assert out["good_moves"], "zero-loss 'best' moves must surface as strengths"
    assert {m["move_number"] for m in out["good_moves"]} <= {6, 7, 9}


def test_1_1_a_renamed_key_is_caught_here_not_in_the_output():
    """Guards the contract rather than the behaviour: if the stored field is
    renamed, this fails instead of good_moves silently emptying again."""
    rows = _game()
    assert all(QUALITY_FIELD in r for r in rows)
    broken = [{k: v for k, v in r.items() if k != QUALITY_FIELD} for r in rows]
    out = compose_story(broken, "0-1", "white", "Italian Game")
    assert out["good_moves"] == [], (
        "with the key absent the filter must yield nothing, which is exactly "
        "the production symptom this repair fixes"
    )


# ── Repair 1.2 — mate is not a centipawn quantity ─────────────────────────

@pytest.mark.parametrize("row,expected", [
    ({"cp_loss": 300}, False),
    ({"cp_loss": MATE_SENTINEL_CP}, True),
    ({"cp_loss": 9108}, True),
    ({"cp_loss": 100, "eval_before": 9970}, True),
    ({"cp_loss": 100, "eval_after": -9840}, True),
    # Production rows use {"before": n, "after": n}; this asserts that an
    # unfamiliar key shape is still recognised as mate-related.
    ({"cp_loss": 100, "mate_info": {"mate_in": 3}}, True),
    ({"cp_loss": 100, "mate_info": {"before": None, "after": None}}, False),
    ({"cp_loss": 100}, False),
])
def test_1_2_mate_swing_detection(row, expected):
    assert _is_mate_swing(row) is expected


def test_1_2_mate_is_never_labelled_in_centipawns():
    """The symptom: '-9108cp' and '-1385cp' on cards whose cost was the
    difference between two mate scores.

    The label is now the transition rather than a fixed phrase -- see
    test_mate_state_and_cost_wording.py, which covers the review finding that
    "lost a forced mate" was wrong for a player who ALLOWED one.
    """
    assert _format_cp(300) == "-300cp"
    assert "cp" not in _format_cp(9108, mate_transition="gave up a forced mate")
    assert _format_cp(9108, mate_transition="allowed a forced mate") ==         "allowed a forced mate"


def test_1_2_mate_card_label_and_flag():
    out = compose_story(_game([_row(20, "Qxh3+", 1385, eval_before=9970)]),
                        "0-1", "white", "Italian Game")
    card = next(p for p in out["principles"] if p["move_number"] == 20)
    assert card["cost_is_mate"] is True
    assert "cp" not in card["cp_loss_label"]
    assert card["mate_transition"] is not None


def test_1_2_cp_to_pieces_does_not_call_a_mate_a_queen():
    assert _cp_to_pieces(950) == "a queen"
    assert _cp_to_pieces(9108) == "a forced mate"


def test_1_2_cost_line_excludes_mate_rows():
    """The symptom: 'Total material leaked: 99.3 pawns worth'.

    The wording also stopped claiming material at all -- review finding P1,
    covered in detail in test_mate_state_and_cost_wording.py.
    """
    line = _blunder_cost_line([{"cp_loss": 300}, {"cp_loss": 9108}])
    assert "99" not in line and "91" not in line
    assert "300 centipawns" in line
    assert "pawns worth" not in line
    assert "forced mate" in line
    assert _blunder_cost_line([{"cp_loss": 9108}]).startswith("One of these")


# ── Repair 1.3 — three states for opponent evidence ───────────────────────

def _profile(opponent_moves, blunders=(), mistakes=(), offered=False):
    return {
        "opponent_moves": list(opponent_moves),
        "opponent_blunders": list(blunders),
        "opponent_mistakes": list(mistakes),
        "opponent_offered_chances": offered,
    }


def test_1_3_no_opponent_rows_says_so():
    """The symptom: 'Your opponent played clean — no mistakes to punish.' on a
    game where not one opponent move was ever evaluated."""
    msg = _describe_opponent(_profile([]))
    assert "no evaluation" in msg.lower()
    assert "played clean" not in msg


def test_1_3_opponent_rows_present_and_clean_still_says_clean():
    msg = _describe_opponent(_profile([{"cp_loss": 10}]))
    assert "played clean" in msg


def test_1_3_opponent_errors_are_counted():
    msg = _describe_opponent(
        _profile([{"cp_loss": 250}], blunders=[{"cp_loss": 250}]))
    assert "blunder" in msg


def test_1_3_user_only_array_does_not_claim_a_clean_opponent():
    """End to end: a user-only move_evaluations array is the normal shape, and
    it must not produce a claim about the opponent."""
    out = compute_game_summary(_game(), "0-1", "white", "Italian Game", "timeout")
    joined = " ".join(out.get("context") or []) + " " + str(out.get("subline") or "")
    assert "played clean" not in joined


# ── Repair 1.4 — no empty strings in user-facing output ───────────────────

def test_1_4_no_blank_user_facing_strings():
    out = compose_story(_game(), "0-1", "white", "Italian Game")
    for card in out["principles"]:
        for key, value in card.items():
            if isinstance(value, str):
                assert value.strip(), f"blank {key} on a principle card"
    for row in out["summary_table"]:
        assert row["remedy"].strip(), "a summary row shipped an empty remedy"


def test_1_4_summary_row_omitted_when_the_remedy_is_empty(monkeypatch):
    """The symptom: two of five rows in one real game shipped remedy: ''."""
    import services.game_coach_review as gcr
    monkeypatch.setattr(gcr, "_split_r12_caption", lambda cap: ("Bad move.", ""))
    rows = _game()
    rows[2] = dict(rows[2])
    out = gcr.compose_story(
        rows, "0-1", "white", "Italian Game",
        decryption_data=[{"move_number": 8, "move_san": "b4",
                          "caption": "b4 runs into Bxc4."}])
    assert all(r["remedy"].strip() for r in out["summary_table"])


# ── Repair 1.5 — the opener ───────────────────────────────────────────────

def test_1_5_no_opening_name_does_not_say_the_this_game():
    """The symptom: 'You played the this game' on all four lichess games."""
    out = compose_story(_game(), "0-1", "white", "")
    assert "the this game" not in out["opener"]
    assert out["opener"].startswith("In this game you lost as White")
    # The first version of this repair read "In this game you you lost as
    # White", because _result_label already supplies the pronoun and the
    # original assertion (startswith "In this game you") passed anyway.
    assert " you you " not in out["opener"]


def test_1_5_opening_name_still_used_when_present():
    out = compose_story(_game(), "0-1", "white", "Italian Game")
    assert "You played the Italian Game" in out["opener"]


@pytest.mark.parametrize("name", ["", None, "   "])
def test_1_5_blank_opening_variants(name):
    out = compose_story(_game(), "0-1", "white", name)
    assert "the this game" not in out["opener"]
    assert "the  " not in out["opener"]
    assert " you you " not in out["opener"]


@pytest.mark.parametrize("colour,result,expect", [
    ("white", "0-1", "In this game you lost as White."),
    ("black", "0-1", "In this game you won as Black."),
    ("white", "1/2-1/2", "In this game you drew as White."),
])
def test_1_5_opener_reads_as_one_sentence(colour, result, expect):
    out = compose_story(_game(), result, colour, "")
    assert out["opener"].startswith(expect), out["opener"]


# ── Repair 1.6 — the title must match the diagnosis ───────────────────────

def test_1_6_recognised_verb_keeps_its_title():
    assert _title_for_caption("b4 runs into Bxc4.", "Castle early") == \
        "Runs into the reply"


def test_1_6_unrecognised_shape_drops_the_title():
    """The symptom: 'King in the corner = mate' sat above a body reading
    'it runs into Bxg8, taking your bishop'."""
    assert _title_for_caption("Kxg4 walks into Bxg8.",
                              "King in the corner = mate") is None


def test_1_6_no_caption_keeps_the_template_title():
    assert _title_for_caption("", "Castle early") == "Castle early"


def test_1_6_card_has_no_contradictory_title():
    out = compose_story(
        _game(), "0-1", "white", "Italian Game",
        decryption_data=[{"move_number": 8, "move_san": "b4",
                          "caption": "b4 walks into an unrecognised shape."}])
    card = next(p for p in out["principles"] if p["move_number"] == 8)
    assert "title" not in card, "a mismatched title must be dropped, not shown"


# ── Guard: the behaviour the repairs must NOT change ──────────────────────

def test_unchanged_principles_still_rank_by_cp_loss():
    out = compose_story(_game([_row(12, "Nd5", 500)]), "0-1", "white", "Italian")
    assert out["principles"][0]["move_number"] == 12
    assert out["result_arc"]["decided_at_move"] == 12


def test_unchanged_clean_game_still_returns_none():
    out = compose_story([_row(6, "Nf3", 0), _row(7, "Bc4", 0)],
                        "1-0", "white", "Italian")
    assert out is None
