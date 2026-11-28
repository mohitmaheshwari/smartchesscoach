"""Contract tests for the canonical piece_safety.d_live.v1 observation fact."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.move_observation_deriver import (
    DERIVER_SEMANTIC_VERSION,
    D_LIVE_FACT_VERSION,
    SCHEMA_VERSION,
    _derive_d_live_fact,
    current_deriver_identity,
    derive_observations_for_game,
)


HANG_FEN = "4k3/8/4p2p/8/8/5N2/8/4K3 w - - 0 1"
SAFE_EXCHANGE_FEN = "4k3/8/7q/8/7P/5N2/8/4K3 w - - 0 1"


def _move(fen, uci, cp_loss):
    return {
        "fen_before": fen,
        "move_uci": uci,
        "move_number": 1,
        "move": "Ng5",
        "cp_loss": cp_loss,
        "evaluation": "mistake" if cp_loss >= 150 else "good",
        "cognitive_gap": "piece_safety" if cp_loss >= 150 else None,
    }


def test_schema_bumps_for_additive_d_live_fact():
    # v18 adds the separately authorized exact destination-safety fact while
    # retaining D_live unchanged for its original measurement contract.
    # v19 (2026-09-22) adds the per-move positional snapshot -- doubled and
    # isolated pawns, loose pieces, bishop quality, centre, space, mobility.
    # Additive: no existing field changed meaning, and D_live is untouched.
    # v20 (2026-09-26) time flags measured against the player's own pace --
    # a bump because the DERIVATION changed, not the shape.
    # v21 (2026-11-13) tactic_tags on every user move.
    # v22 (2026-11-28) tactic_opportunity on every user move: the first
    # opportunity denominator besides destination_safety_exact.
    # v23 (2026-11-28) fork joins that denominator, its payoff proved off the
    # board by tactic_payoff instead of the engine's stored line.
    # v24 (2026-11-28) skewer joins it, creation proved by
    # verify_created_alignment and payoff by the same tactic_payoff.
    # v25 (2026-11-28) a fork or skewer must be a SUBSTANTIVE shape before
    # its payoff counts. Not additive in meaning for skewer -- 58.0% of v24's
    # proved skewers had a pawn as the rear man and are withdrawn -- so a
    # stored v24 skewer verdict is not comparable with a v25 one. Fork was
    # measured unaffected, 0 of 349 withdrawn.
    # Every one of the others is additive: no existing field changed meaning
    # and D_live is untouched throughout.
    #
    # This assertion is a deliberate pin on the record shape, so it firing
    # is the point -- bump it only alongside a real, described change. It had
    # been left at 19 through five bumps, so it was firing for no one; the
    # descriptions above are the debt it was meant to collect.
    assert SCHEMA_VERSION == 25


def test_legally_capturable_losing_piece_is_miss_when_both_gates_pass():
    fact = _derive_d_live_fact(_move(HANG_FEN, "f3g5", 200))

    assert fact["version"] == D_LIVE_FACT_VERSION
    assert fact["eligible"] is True
    assert fact["legal_destination_captures"] == 1
    assert fact["destination_see_cp"] >= 150
    assert fact["stockfish_cp_loss"] == 200
    assert fact["outcome"] == "miss"


def test_same_exchange_is_handled_when_stockfish_gate_does_not_pass():
    fact = _derive_d_live_fact(_move(HANG_FEN, "f3g5", 100))

    assert fact["eligible"] is True
    assert fact["destination_see_cp"] >= 150
    assert fact["outcome"] == "handled"


def test_legal_capture_with_unfavorable_exchange_is_handled():
    fact = _derive_d_live_fact(_move(SAFE_EXCHANGE_FEN, "f3g5", 200))

    assert fact["eligible"] is True
    assert fact["legal_destination_captures"] == 1
    assert fact["destination_see_cp"] < 150
    assert fact["outcome"] == "handled"


def test_pawn_move_is_not_an_eligible_d_live_decision():
    fact = _derive_d_live_fact(
        _move("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1", "e2e4", 200)
    )

    assert fact["eligible"] is False
    assert fact["reason"] == "piece_not_eligible"
    assert fact["outcome"] == "not_eligible"


def test_invalid_position_is_unavailable_not_handled():
    fact = _derive_d_live_fact(_move("", "f3g5", 200))

    assert fact["derivation_status"] == "unavailable"
    assert fact["eligible"] is False
    assert fact["outcome"] == "not_eligible"


def test_game_derivation_embeds_exact_versioned_fact():
    observations = derive_observations_for_game(
        {"move_evaluations": [_move(HANG_FEN, "f3g5", 200)]},
        game_id="game-1",
        user_id="user-1",
        user_color="white",
    )

    assert len(observations) == 1
    # Was a hard 19, which had been failing since v20 -- and because it is
    # the FIRST assertion here, the three real checks below it never ran at
    # all. The version is pinned once, in the test above; this one asks only
    # that the row carries whatever the current version is.
    assert observations[0]["schema_version"] == SCHEMA_VERSION
    assert observations[0]["deriver_identity"] == current_deriver_identity()
    assert observations[0]["piece_safety_decision"]["version"] == D_LIVE_FACT_VERSION
    assert observations[0]["piece_safety_decision"]["outcome"] == "miss"


def test_deriver_identity_is_deterministic_complete_and_defensively_copied():
    first = current_deriver_identity()
    second = current_deriver_identity()

    assert first == second
    assert first is not second
    assert first["semantic_version"] == DERIVER_SEMANTIC_VERSION
    assert first["schema_version"] == SCHEMA_VERSION
    assert len(first["manifest_sha256"]) == 64
    assert set(first["dependencies"]) == {
        "move_observation_deriver",
        "material_safety",
        "opponent_threat",
        # v21: the tactic tags and the provers they call.
        "tactic_tags",
        # v22-v24: the opportunity denominator and the two engine-free modules
        # its verdict rests on. tactic_payoff DECIDES whether a fork or skewer
        # counted as a chance, and shape_detectors is the fork geometry called
        # straight from fork_candidates, so a change to either moves every
        # chance count. They belong in the manifest or a stored identity
        # cannot be traced to the code that made the row.
        # aligned_tactic_puzzle_proof, which proves a created skewer, is
        # already here as prover_aligned_tactic.
        "tactic_opportunity",
        "tactic_payoff",
        "shape_detectors",
        "prover_forced_mate",
        "prover_back_rank_mate",
        "prover_fork",
        "prover_discovered_attack",
        "prover_aligned_tactic",
        "prover_free_piece",
    }
    assert all(
        len(item["sha256"]) == 64
        for item in first["dependencies"].values()
    )
    first["manifest_sha256"] = "mutated"
    assert current_deriver_identity()["manifest_sha256"] != "mutated"
