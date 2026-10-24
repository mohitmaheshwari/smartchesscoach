from __future__ import annotations

from services.exact_endgame_service import ExactEndgameEvidence
from services.human_behavior_engine import MoveDistribution
from services.human_chess_analysis_enrichment import (
    enrich_move_evaluations_with_human_chess,
)
from services.human_policy_runtime import OTTER_PINNED_PACKAGE_VERSION


PGN = '''[Event "fixture"]
[White "Student"]
[Black "Opponent"]
[WhiteElo "1200"]
[BlackElo "1250"]
[TimeControl "600+0"]

1. e4 e5 2. Nf3 Nc6 *
'''


def test_enrichment_never_reanalyses_and_persists_fail_closed_reasons(monkeypatch):
    monkeypatch.setenv("HUMAN_CHESS_ANALYSIS_ENRICHMENT_ENABLED", "true")
    rows = [
        {"fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "cp_loss": 0},
        {"fen_before": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "cp_loss": 120, "cognitive_gap": "piece_safety"},
    ]
    monkeypatch.setattr(
        "services.human_chess_analysis_enrichment.probe_configured_fathom",
        lambda fen: (None, "outside_tablebase_coverage"),
    )
    monkeypatch.setattr(
        "services.human_chess_analysis_enrichment.derive_human_policy_evidence",
        lambda ctx: (None, "no_provider_available"),
    )
    enriched, summary = enrich_move_evaluations_with_human_chess(
        rows, pgn=PGN, user_color="white", user_rating=1200
    )
    assert summary == {
        "rows": 2,
        "position_mismatch": 0,
        "exact_evidence": 0,
        "human_policy_evidence": 0,
    }
    # Row 0 is a clean move (cp_loss 0). It used to be skipped as
    # "not_teaching_candidate"; Mohit asked for Maia2 on EVERY move, and
    # the positions worth the most are precisely the clean ones -- a move
    # a player of this rating would probably have got wrong, and did not.
    # So it is admitted now and carries the provider's own reason.
    assert enriched[0]["human_policy_reason"] == "no_provider_available"
    assert enriched[1]["human_policy_reason"] == "no_provider_available"
    assert enriched[1]["exact_endgame_probe_reason"] == "outside_tablebase_coverage"
    assert rows[0].get("human_policy_reason") is None


def test_position_mismatch_abstains_without_joining_evidence(monkeypatch):
    monkeypatch.setenv("HUMAN_CHESS_ANALYSIS_ENRICHMENT_ENABLED", "true")
    rows = [{"fen_before": "8/8/8/8/8/8/4K3/6k1 w - - 0 1", "cp_loss": 100}]
    enriched, summary = enrich_move_evaluations_with_human_chess(
        rows, pgn=PGN, user_color="white", user_rating=1200
    )
    assert summary["position_mismatch"] == 1
    assert enriched[0]["human_policy_reason"] == "position_mismatch"
    assert "human_policy_evidence" not in enriched[0]


def test_analysis_enrichment_flag_off_is_a_strict_noop(monkeypatch):
    monkeypatch.delenv("HUMAN_CHESS_ANALYSIS_ENRICHMENT_ENABLED", raising=False)
    rows = [{"fen_before": "anything", "cp_loss": 100}]
    enriched, summary = enrich_move_evaluations_with_human_chess(
        rows, pgn="invalid", user_color="white", user_rating=1200
    )
    assert enriched == rows
    assert summary["disabled"] == 1


def test_a_clean_move_is_admitted_not_skipped(monkeypatch):
    """Mohit: "each game analysis should have both stockfish and maia2".

    The gate used to require a cognitive_gap, a bad severity, or ANY
    cp_loss. Measured over 92 games, the rows worth the most -- a move a
    player of that rating would probably have blundered, and did not --
    all have cp_loss under 50 and most have 0, so the gate dropped the
    whole family. It is also the only source this product has for praise
    that is specific and checkable.
    """
    monkeypatch.setenv("HUMAN_CHESS_ANALYSIS_ENRICHMENT_ENABLED", "true")
    seen = []
    monkeypatch.setattr(
        "services.human_chess_analysis_enrichment.probe_configured_fathom",
        lambda fen: (None, "outside_tablebase_coverage"),
    )
    monkeypatch.setattr(
        "services.human_chess_analysis_enrichment.derive_human_policy_evidence",
        lambda ctx: (seen.append(ctx.fen), (None, "no_provider_available"))[1],
    )
    rows = [
        {"fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
         "cp_loss": 0},
        {"fen_before": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
         "cp_loss": 0},
    ]
    enriched, _ = enrich_move_evaluations_with_human_chess(
        rows, pgn=PGN, user_color="white", user_rating=1200
    )
    assert len(seen) == 2, "both clean moves must reach the policy provider"
    for row in enriched:
        assert row["human_policy_reason"] != "not_teaching_candidate"


def test_a_row_without_a_position_is_still_refused(monkeypatch):
    """Widening the gate must not admit a row the board cannot be built
    from -- that would send a junk FEN to the provider."""
    monkeypatch.setenv("HUMAN_CHESS_ANALYSIS_ENRICHMENT_ENABLED", "true")
    called = []
    monkeypatch.setattr(
        "services.human_chess_analysis_enrichment.derive_human_policy_evidence",
        lambda ctx: (called.append(1), (None, "no_provider_available"))[1],
    )
    enriched, _ = enrich_move_evaluations_with_human_chess(
        [{"cp_loss": 0}], pgn=PGN, user_color="white", user_rating=1200
    )
    assert not called
    assert enriched[0]["human_policy_reason"] in (
        "no_position", "missing_pgn_position", "position_mismatch")
