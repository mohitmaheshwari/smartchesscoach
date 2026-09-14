"""The result card gets one shape, whichever scorer ran.

Two scorers describe the same ideas with different field names:

    score_diagnostic    (v1)  per_category / summary_line / growth_areas
    score_diagnostic_v2 (v2)  per_concept  / summary      / headline_gap

The card reads the v2 names only, and every player is currently served v1 --
the v2 pool gate wants `pool_version: 2` with frozen grades and matches 0 of
the 60 pool documents. So after answering twenty positions the player saw the
headline "Here's what I understand about your chess." with nothing underneath
it: no concept rows, no "where we'll start" panel, an empty lede.

Reported from the product on 2026-09-14 with a screenshot of exactly that.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.diagnostic_service import diagnosis_view

V1 = {
    "rating_estimate": {"low": 1000, "high": 1250},
    "per_category": {
        "piece_safety": {"correct": 1, "total": 3, "label": "Needs work",
                         "display_name": "Piece Safety"},
        "missed_tactic": {"correct": 3, "total": 3, "label": "Strong",
                          "display_name": "Missed Tactics"},
        "king_safety": {"correct": 2, "total": 3, "label": "Mixed",
                        "display_name": "King Safety"},
    },
    "strengths": ["Missed Tactics"],
    "growth_areas": ["Piece Safety"],
    "summary_line": "Strong signal in missed tactics. The clearest place to "
                    "grow: piece safety.",
    "total_correct": 6,
    "total_attempted": 9,
}

V2 = {
    "version": 2,
    "rating_estimate": {"low": 1125, "high": 1325},
    "per_concept": {"threat_response": {"level": "developing"}},
    "headline_gap": "threat_response",
    "summary": "Threat response is where we will start.",
}


def test_a_v1_result_renders_as_the_card_expects():
    view = diagnosis_view(V1)
    assert set(view["per_concept"]) == {"piece_safety", "missed_tactic", "king_safety"}
    assert view["summary"] == V1["summary_line"]


def test_labels_become_the_cards_three_levels():
    levels = {k: v["level"] for k, v in diagnosis_view(V1)["per_concept"].items()}
    assert levels == {
        "piece_safety": "missing",
        "missed_tactic": "solid",
        "king_safety": "developing",
    }


def test_the_headline_gap_is_a_key_not_a_display_name():
    # The card routes to /training/pattern/<headline_gap>, so a display name
    # like "Piece Safety" would produce a dead link.
    assert diagnosis_view(V1)["headline_gap"] == "piece_safety"


def test_a_v2_result_is_passed_through_untouched():
    assert diagnosis_view(V2) is V2


def test_the_rating_band_survives_normalising():
    # It is the most concrete thing a player gets, and it was already being
    # computed and thrown away by the card.
    assert diagnosis_view(V1)["rating_estimate"] == {"low": 1000, "high": 1250}


def test_nothing_measured_stays_empty_rather_than_inventing_a_readout():
    empty = {
        "rating_estimate": {"low": 600, "high": 900},
        "per_category": {},
        "summary_line": "Not enough data yet.",
    }
    view = diagnosis_view(empty)
    assert not view.get("per_concept")
    assert not view.get("headline_gap")


def test_junk_is_survived():
    assert diagnosis_view(None) == {}
    assert diagnosis_view("nonsense") == {}
