import copy
from types import SimpleNamespace

import chess
import chess.engine
import pytest

from services.candidate_caption_evidence import (
    CandidateEvidence, candidate_packet_state, collect_candidate_evidence,
    select_candidates,
)
from services.caption_facts import build_legal_material_loss_cause
from services.caption_pipeline import MoveInputs, build_candidate_comparison


ROW = {
    "fen_before": "3rk3/8/8/3p4/8/8/8/3QK3 w - - 0 1",
    "move_uci": "d1d5",
    "move_san": "Qxd5",
    "best_move_uci": "d1a1",
    "best_move_san": "Qa1",
    "cp_loss": 800,
    "move_number": 1,
    "is_opponent_move": False,
    "pv_after_played": ["Qxd5", "Rxd5"],
    "pv_after_best": ["Qa1", "Kf7"],
}


def test_stored_evidence_round_trip_replays_both_ideas():
    packet, summary = collect_candidate_evidence(ROW)
    restored = CandidateEvidence.from_document(packet.document(), ROW)
    assert restored.candidates == ("d1d5", "d1a1")
    assert restored.branch("d1d5").moves_san == ("Qxd5", "Rxd5")
    assert restored.branch("d1a1").moves_san == ("Qa1", "Kf7")
    assert summary == {"candidates": 2, "reused": 2, "missing": 0, "invalid_stored": 0}


def test_played_and_best_are_always_in_candidate_set():
    assert select_candidates(ROW) == ("d1d5", "d1a1")


def _human_policy(*moves):
    return SimpleNamespace(
        fen=ROW["fen_before"],
        probabilities=tuple(
            SimpleNamespace(move_uci=move, probability=probability)
            for move, probability in moves
        ),
        provider="maia2",
        provider_version="0.11.0",
        model_sha256="a" * 64,
        input_fingerprint="b" * 64,
        history_sha256="c" * 64,
    )


def test_human_candidates_stop_at_locked_mass_after_three_move_floor():
    human = _human_policy(
        ("d1d5", 0.40),
        ("d1a1", 0.25),
        ("d1b1", 0.20),
        ("d1c1", 0.10),
        ("d1e2", 0.05),
    )
    # Played and best are always first; the third human-ranked move takes
    # cumulative mass above 80%, so the lower-probability tail is excluded.
    assert select_candidates(ROW, human=human) == (
        "d1d5", "d1a1", "d1b1"
    )


def test_writer_uses_one_restricted_root_search_and_records_human_provenance():
    human = _human_policy(
        ("d1d5", 0.40),
        ("d1a1", 0.25),
        ("d1b1", 0.20),
    )

    class Engine:
        def __init__(self):
            self.calls = []

        def analyse(self, board, limit, *, root_moves, multipv):
            self.calls.append((board.fen(), tuple(root_moves), multipv, limit))
            return [{
                "pv": [chess.Move.from_uci("d1b1"), chess.Move.from_uci("e8f7")],
                "score": chess.engine.PovScore(chess.engine.Cp(50), chess.WHITE),
            }]

    engine = Engine()
    packet, summary = collect_candidate_evidence(
        ROW,
        human=human,
        engine=engine,
        limit=chess.engine.Limit(depth=18),
        engine_identity={"name": "Stockfish", "analysis_depth": 18},
    )
    assert len(engine.calls) == 1
    assert engine.calls[0][1] == (chess.Move.from_uci("d1b1"),)
    assert engine.calls[0][2] == 1
    assert packet.branch("d1b1").source == "candidate_stockfish"
    assert packet.provenance["human"] == {
        "provider": "maia2",
        "provider_version": "0.11.0",
        "model_sha256": "a" * 64,
        "input_fingerprint": "b" * 64,
        "history_sha256": "c" * 64,
    }
    assert summary["missing"] == 0


@pytest.mark.parametrize("mutation", ["source", "line", "fingerprint"])
def test_packet_fails_closed_when_join_or_line_is_changed(mutation):
    packet, _ = collect_candidate_evidence(ROW)
    doc = packet.document()
    source = copy.deepcopy(ROW)
    if mutation == "source":
        source["cp_loss"] = 799
    elif mutation == "line":
        doc["branches"][0]["moves_uci"][-1] = "e8f7"
        from services.candidate_caption_evidence import fingerprint
        unsigned = dict(doc)
        unsigned.pop("fingerprint")
        doc["fingerprint"] = fingerprint(unsigned)
    else:
        doc["fingerprint"] = "0" * 64
    with pytest.raises(ValueError):
        CandidateEvidence.from_document(doc, source)


def test_no_engine_means_missing_human_branches_stay_missing():
    changed = {**ROW, "pv_after_best": []}
    packet, summary = collect_candidate_evidence(changed)
    assert packet.branch("d1a1") is None
    assert summary["missing"] == 1


def test_central_caption_builds_compact_replayable_comparison():
    packet, _ = collect_candidate_evidence(ROW)
    cause = build_legal_material_loss_cause(
        fen_before=ROW["fen_before"], played_san="Qxd5", best_move_san="Qa1",
        minimum_gain_cp=150,
    )
    assert cause is not None
    inputs = MoveInputs(
        fen_before=ROW["fen_before"], played_san="Qxd5", mover_is_user=True,
        mover_is_white=True, user_color="white", full_move_number=1,
        move_history_san=[], best_move_san="Qa1", best_move_uci="d1a1",
        cp_loss=800, pv_after_played=ROW["pv_after_played"],
        pv_after_best=ROW["pv_after_best"],
        candidate_caption_evidence=packet.document(),
    )
    comparison = build_candidate_comparison(inputs, cause)
    assert comparison is not None
    assert comparison.headline == "Count both sides of the trade"
    assert comparison.played_line_moves == ("Qxd5", "Rxd5")
    assert comparison.stronger_line_moves == ("Qa1", "Kf7")
    assert len((comparison.played_summary + " " + comparison.stronger_summary).split()) <= 32
    assert len(comparison.memory_cue.split()) <= 18


def test_central_caption_rejects_candidate_packet_from_another_source():
    packet, _ = collect_candidate_evidence(ROW)
    doc = packet.document()
    cause = build_legal_material_loss_cause(
        fen_before=ROW["fen_before"], played_san="Qxd5", best_move_san="Qa1",
        minimum_gain_cp=150,
    )
    inputs = MoveInputs(
        fen_before=ROW["fen_before"], played_san="Qxd5", mover_is_user=True,
        mover_is_white=True, user_color="white", full_move_number=1,
        move_history_san=[], best_move_san="Qa1", best_move_uci="d1a1",
        cp_loss=799, pv_after_played=ROW["pv_after_played"],
        pv_after_best=ROW["pv_after_best"], candidate_caption_evidence=doc,
    )
    assert build_candidate_comparison(inputs, cause) is None


def test_reconciliation_states_distinguish_missing_stale_changed_and_rejected():
    packet, _ = collect_candidate_evidence(ROW)
    current = packet.document()
    assert candidate_packet_state(None, ROW) == "missing"
    assert candidate_packet_state(current, ROW) == "current"

    stale = copy.deepcopy(current)
    stale["policy_version"] = "candidate_budget.old"
    from services.candidate_caption_evidence import fingerprint
    unsigned = dict(stale)
    unsigned.pop("fingerprint")
    stale["fingerprint"] = fingerprint(unsigned)
    assert candidate_packet_state(stale, ROW) == "stale"

    changed_row = {**ROW, "cp_loss": 799}
    assert candidate_packet_state(current, changed_row) == "changed"

    rejected = copy.deepcopy(current)
    rejected["fingerprint"] = "0" * 64
    assert candidate_packet_state(rejected, ROW) == "rejected"
