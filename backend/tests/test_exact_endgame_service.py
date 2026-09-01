from __future__ import annotations

import hashlib
import asyncio
import json
import subprocess
from pathlib import Path

import chess
import pytest

from services.exact_endgame_service import (
    EXACT_ENDGAME_SCHEMA_VERSION,
    ExactEndgameError,
    ExactEndgameCause,
    ExactEndgameEvidence,
    build_exact_endgame_cause,
    compute_syzygy_manifest_sha256,
    parse_fathom_output,
    probe_configured_fathom,
    render_exact_endgame_cause,
)
from services import caption_pipeline
from services.caption_pipeline import CrossMoveState, MoveInputs
from services.game_review_shadow_runtime import adapt_verified_cause_event
from services.teaching_engine import process_endgame_move


FEN = "8/8/8/8/8/8/2P5/K1k5 b - - 0 1"
OUTPUT = f'''[Event ""]
[Result "1/2-1/2"]
[FEN "{FEN}"]
[WDL "Draw"]
[DTZ "0"]
[WinningMoves ""]
[DrawingMoves "Kxc2"]
[LosingMoves "Kd1, Kd2"]

1... Kxc2 2. Ka2 Kc1 1/2-1/2
'''
SHA = "1" * 64
MANIFEST_SHA = "2" * 64


def evidence() -> ExactEndgameEvidence:
    return parse_fathom_output(
        FEN,
        OUTPUT,
        binary_sha256=SHA,
        tablebase_bundle_id="syzygy-3-men-test",
        tablebase_manifest_sha256=MANIFEST_SHA,
    )


def test_committed_tablebase_snapshot_is_legal_complete_and_auditable():
    snapshot_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "corpus_snapshots"
        / "curriculum_endgame_tablebase_2026-08-29.json"
    )
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    entries = snapshot["entries"]

    assert len(entries) == 51
    identities = set()
    for entry in entries:
        board = chess.Board(entry["fen"])
        stored_move = chess.Move.from_uci(entry["stored_move_uci"])
        preserving = {
            item["uci"] for item in entry.get("preserving_moves", [])
        }
        identity = (entry["content_id"], int(entry["position_index"]))

        assert identity not in identities
        identities.add(identity)
        assert chess.popcount(board.occupied) <= 7
        assert stored_move in board.legal_moves
        assert entry["preserves_wdl"] is True
        assert stored_move.uci() in preserving
        assert isinstance(entry["dtz"], int)
        assert "precise_dtz" in entry
        assert entry["precise_dtz"] is None or isinstance(
            entry["precise_dtz"], int
        )
        assert len(entry["response_sha256"]) == 64
        int(entry["response_sha256"], 16)


def test_exact_contract_partitions_every_legal_move_and_round_trips():
    exact = evidence()
    assert exact.root_outcome == "draw"
    assert exact.result_preserving_moves_uci == ("c1c2",)
    assert exact.outcome_for("c1d1") == "loss"
    assert ExactEndgameEvidence.from_contract(exact.contract_dict()) == exact


def test_incomplete_or_overlapping_fathom_output_is_rejected():
    with pytest.raises(ExactEndgameError, match="do not partition"):
        parse_fathom_output(
            FEN,
            OUTPUT.replace('LosingMoves "Kd1, Kd2"', 'LosingMoves "Kd1"'),
            binary_sha256=SHA,
            tablebase_bundle_id="test",
            tablebase_manifest_sha256=MANIFEST_SHA,
        )
    with pytest.raises(ExactEndgameError, match="overlap"):
        parse_fathom_output(
            FEN,
            OUTPUT.replace('WinningMoves ""', 'WinningMoves "Kxc2"'),
            binary_sha256=SHA,
            tablebase_bundle_id="test",
            tablebase_manifest_sha256=MANIFEST_SHA,
        )


def test_result_change_cause_uses_only_result_preserving_alternative():
    cause = build_exact_endgame_cause(
        evidence(),
        played_san="Kd1",
        preferred_best_san="Kxc2",
    )
    assert cause is not None
    assert cause.outcome_before == "draw"
    assert cause.outcome_after == "loss"
    assert cause.best_move_uci == "c1c2"
    headline, caption, instruction = render_exact_endgame_cause(cause)
    assert headline == "You let the draw slip"
    assert "changed the draw into a loss" in caption
    assert "Kxc2 preserved the draw" in caption
    assert "keeps the win or draw" in instruction


def test_result_preserving_move_produces_no_cause():
    assert build_exact_endgame_cause(evidence(), played_san="Kxc2") is None


def test_cursed_wdl_is_stored_but_never_rendered_as_a_simple_win():
    cursed = parse_fathom_output(
        FEN,
        OUTPUT.replace('[WDL "Draw"]', '[WDL "CursedWin"]'),
        binary_sha256=SHA,
        tablebase_bundle_id="test",
        tablebase_manifest_sha256=MANIFEST_SHA,
    )
    assert cursed.root_outcome is None
    assert cursed.result_preserving_moves_uci == ()
    assert build_exact_endgame_cause(cursed, played_san="Kd1") is None


def test_configured_probe_fails_closed_and_checks_binary_provenance(tmp_path, monkeypatch):
    binary = tmp_path / "fathom-probe"
    binary.write_bytes(b"pinned-test-binary")
    tables = tmp_path / "tables"
    tables.mkdir()
    (tables / "KQvK.rtbw").write_bytes(b"pinned-test-table")
    expected_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    env = {
        "EXACT_ENDGAME_REVIEW_ENABLED": "true",
        "FATHOM_BINARY_PATH": str(binary),
        "FATHOM_BINARY_SHA256": expected_sha,
        "SYZYGY_TABLEBASE_PATH": str(tables),
        "SYZYGY_TABLEBASE_BUNDLE_ID": "fixture-bundle",
        "SYZYGY_TABLEBASE_MANIFEST_SHA256": compute_syzygy_manifest_sha256(
            str(tables)
        ),
        "SYZYGY_MAX_MEN": "3",
    }

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=OUTPUT, stderr=""
        ),
    )
    exact, reason = probe_configured_fathom(FEN, env)
    assert reason == "exact"
    assert exact is not None
    assert exact.provider_version == EXACT_ENDGAME_SCHEMA_VERSION
    assert exact.tablebase_manifest_sha256 == env["SYZYGY_TABLEBASE_MANIFEST_SHA256"]

    exact, reason = probe_configured_fathom(
        FEN,
        {**env, "FATHOM_BINARY_SHA256": "0" * 64},
    )
    assert exact is None
    assert reason == "binary_sha256_mismatch"

    compute_syzygy_manifest_sha256.cache_clear()
    (tables / "KQvK.rtbw").write_bytes(b"changed-table")
    exact, reason = probe_configured_fathom(FEN, env)
    assert exact is None
    assert reason == "tablebase_manifest_sha256_mismatch"


def test_disabled_or_out_of_coverage_never_invokes_fathom():
    assert probe_configured_fathom(FEN, {}) == (None, "disabled")
    exact, reason = probe_configured_fathom(
        FEN,
        {"EXACT_ENDGAME_REVIEW_ENABLED": "true", "SYZYGY_MAX_MEN": "2"},
    )
    assert exact is None
    assert reason == "coverage_not_configured"


class _LessonCollection:
    def __init__(self):
        self.document = {
            "session_id": "exact-lesson",
            "lesson_name": "Structural fixture",
            "current_position_index": 0,
            "endgame_data": {
                "rule": "Keep the result.",
                "positions": [{
                    "fen": FEN,
                    # Deliberately stale authored answer: exact truth must win.
                    "correct_move_san": "Kd1",
                    "correct_move_uci": "c1d1",
                    "prompt": "Keep the draw.",
                }],
            },
        }

    async def find_one(self, query):
        return dict(self.document) if query.get("session_id") == "exact-lesson" else None

    async def update_one(self, query, update):
        for key, value in update.get("$set", {}).items():
            self.document[key] = value
        for key, value in update.get("$inc", {}).items():
            self.document[key] = self.document.get(key, 0) + value


class _LessonDB:
    def __init__(self):
        self.coach_sessions = _LessonCollection()


def test_endgame_lesson_exact_truth_overrides_a_stale_authored_answer(monkeypatch):
    monkeypatch.setattr(
        "services.exact_endgame_service.probe_configured_fathom",
        lambda fen: (evidence(), "exact"),
    )
    accepted = asyncio.run(process_endgame_move(_LessonDB(), "exact-lesson", "Kxc2"))
    assert accepted["correct"] is True
    assert accepted["complete"] is True
    assert accepted["result_preserved"] is True
    assert accepted["demonstrated"] is False
    assert accepted["exact_endgame_evidence"]["complete_legal_partition"] is True

    rejected = asyncio.run(process_endgame_move(_LessonDB(), "exact-lesson", "Kd1"))
    assert rejected["correct"] is False
    assert rejected["exact_endgame_probe_reason"] == "exact"


def test_already_lost_tablebase_position_does_not_accept_every_losing_move(monkeypatch):
    lost = parse_fathom_output(
        FEN,
        OUTPUT.replace('[WDL "Draw"]', '[WDL "Loss"]')
        .replace('[DrawingMoves "Kxc2"]', '[DrawingMoves ""]')
        .replace('[LosingMoves "Kd1, Kd2"]', '[LosingMoves "Kxc2, Kd1, Kd2"]'),
        binary_sha256=SHA,
        tablebase_bundle_id="test",
        tablebase_manifest_sha256=MANIFEST_SHA,
    )
    monkeypatch.setattr(
        "services.exact_endgame_service.probe_configured_fathom",
        lambda fen: (lost, "exact"),
    )

    result = asyncio.run(process_endgame_move(_LessonDB(), "exact-lesson", "Kxc2"))

    assert result["correct"] is False
    assert result["exact_endgame_probe_reason"] == "non_teachable_root_outcome"
    assert "exact_endgame_evidence" not in result


def test_central_caption_and_review_event_share_the_exact_cause(monkeypatch):
    monkeypatch.setattr(caption_pipeline, "_EXACT_ENDGAME_REVIEW_ENABLED", True)
    decision = caption_pipeline.build_move_teaching_decision(
        MoveInputs(
            fen_before=FEN,
            played_san="Kd1",
            mover_is_user=True,
            mover_is_white=False,
            user_color="black",
            full_move_number=1,
            move_history_san=[],
            best_move_san="Kxc2",
            cp_loss=500,
            exact_endgame_evidence=evidence().contract_dict(),
        ),
        CrossMoveState(),
    )
    assert decision.cause is not None
    assert decision.cause.contract_dict()["kind"] == "exact_endgame_result_change"
    assert decision.text.rule_name == "R_EXACT_ENDGAME_RESULT"
    assert decision.explanation.final_verified is True
    assert "changed the draw into a loss" in decision.text.caption
    assert decision.exact_endgame_evidence["complete_legal_partition"] is True

    pair = adapt_verified_cause_event(
        decision=decision,
        game_id="exact-endgame-game",
        ply=1,
        move_number=1,
        san="Kd1",
        env={
            "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
            "PERSONALIZED_GAME_REVIEW_QUALITY_V2_ENABLED": "true",
        },
    )
    assert pair is not None
    event, _ = pair
    assert event.evidence.quality_id == "review:exact_endgame_result_change"
    assert event.player_authorized is True
    assert event.teaching.headline == "You let the draw slip"
    assert event.teaching.visual.relationship_arrows == ()


def test_exact_evidence_cannot_create_a_review_cause_when_visibility_flag_is_off(
    monkeypatch,
):
    monkeypatch.setattr(caption_pipeline, "_EXACT_ENDGAME_REVIEW_ENABLED", False)
    decision = caption_pipeline.build_move_teaching_decision(
        MoveInputs(
            fen_before=FEN,
            played_san="Kd1",
            mover_is_user=True,
            mover_is_white=False,
            user_color="black",
            full_move_number=1,
            move_history_san=[],
            best_move_san="Kxc2",
            cp_loss=500,
            exact_endgame_evidence=evidence().contract_dict(),
        ),
        CrossMoveState(),
    )

    assert not isinstance(decision.cause, ExactEndgameCause)
    assert "exact_endgame:" not in " ".join(decision.explanation.provenance)


def test_stale_exact_packet_cannot_change_the_caption(monkeypatch):
    monkeypatch.setattr(caption_pipeline, "_EXACT_ENDGAME_REVIEW_ENABLED", True)
    packet = evidence().contract_dict()
    packet["input_fingerprint"] = "0" * 64
    decision = caption_pipeline.build_move_teaching_decision(
        MoveInputs(
            fen_before=FEN,
            played_san="Kd1",
            mover_is_user=True,
            mover_is_white=False,
            user_color="black",
            full_move_number=1,
            move_history_san=[],
            best_move_san="Kxc2",
            cp_loss=500,
            exact_endgame_evidence=packet,
        ),
        CrossMoveState(),
    )
    assert decision.text.rule_name != "R_EXACT_ENDGAME_RESULT"
    assert decision.exact_endgame_evidence is None
