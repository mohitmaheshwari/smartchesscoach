"""Exact opponent-caption proof for capture/recapture/pawn-fork ideas."""

from __future__ import annotations

import os
import sys

import chess

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_facts import (  # noqa: E402
    UNSAFE_RECAPTURE_PAWN_FORK_PROOF_VERSION,
    build_unsafe_recapture_pawn_fork_proof,
)
from services.caption_pipeline import inject_opp_side_narration_facts  # noqa: E402
from services.caption_pipeline import (  # noqa: E402
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
)
from services.caption_templates import render_rule  # noqa: E402
from services.narrator_claim_verifier import verify_caption  # noqa: E402
from services.pattern_catalog import detect_opp_move_punishments  # noqa: E402


RE1_PRE_FEN = (
    "r1bq1rk1/pppp1ppp/2n2n2/2b1p3/2B1P3/1P3N2/"
    "P1PP1PPP/RNBQ1RK1 w - - 0 6"
)
RE1_POST_FEN = (
    "r1bq1rk1/pppp1ppp/2n2n2/2b1p3/2B1P3/1P3N2/"
    "P1PP1PPP/RNBQR1K1 b - - 2 6"
)
RE1_REPLY = "Nxe4"
RE1_PV = ["Rxe4", "d5", "Bxd5", "Qxd5"]

NXC4_PRE_FEN = (
    "r1bqkbnr/pp1p1ppp/4p3/2p1n3/2B1P3/2Q4N/"
    "PPPP1PPP/RNB1K2R b KQkq - 3 5"
)
NXC4_REPLY = "Nxc4"
NXC4_PV = ["Qxc4", "d5", "Qe2", "dxe4"]


def _proof(fen: str, reply: str, pv: list[str]):
    return build_unsafe_recapture_pawn_fork_proof(
        post_opp_fen=fen,
        user_best_reply_san=reply,
        pv_after_best=pv,
    )


def test_re1_line_proves_exact_recapture_fork_and_exchange_resolution():
    proof = _proof(RE1_POST_FEN, RE1_REPLY, RE1_PV)

    assert proof is not None
    assert proof.proof_version == UNSAFE_RECAPTURE_PAWN_FORK_PROOF_VERSION
    assert proof.resolution_kind == (
        "fork_target_captures_pawn_then_is_recaptured"
    )
    assert proof.line_evidence.replayed_san == (
        "Nxe4",
        "Rxe4",
        "d5",
        "Bxd5",
        "Qxd5",
    )
    assert proof.setup.moving_piece_id == proof.recapture.target_piece_id
    assert proof.recapturing_target.contract_dict() == {
        "piece": "rook",
        "piece_id": "white:rook:e1",
        "square": "e4",
    }
    assert proof.other_target.contract_dict() == {
        "piece": "bishop",
        "piece_id": "white:bishop:c4",
        "square": "c4",
    }
    assert proof.payoff.target_piece_id == proof.other_target.piece_id


def test_second_real_line_proves_pawn_takes_other_target():
    proof = _proof(NXC4_PRE_FEN, NXC4_REPLY, NXC4_PV)

    assert proof is not None
    assert proof.resolution_kind == "one_target_moves_pawn_captures_other"
    assert proof.recapturing_target.piece == "queen"
    assert proof.recapturing_target.square == "c4"
    assert proof.other_target.piece == "pawn"
    assert proof.other_target.square == "e4"
    assert proof.response.move_san == "Qe2"
    assert proof.payoff.move_san == "dxe4"
    assert proof.payoff.target_piece_id == proof.other_target.piece_id


def test_incomplete_stored_horizon_abstains():
    assert _proof(RE1_POST_FEN, RE1_REPLY, RE1_PV[:2]) is None


def test_illegal_continuation_abstains():
    assert _proof(
        RE1_POST_FEN,
        RE1_REPLY,
        ["Rxe4", "d5", "Qh5", "Qxh5"],
    ) is None


def test_unresolved_double_attack_abstains():
    assert _proof(
        RE1_POST_FEN,
        RE1_REPLY,
        ["Rxe4", "d5", "Bd3", "Be6"],
    ) is None


def test_pattern_projection_contains_only_board_derived_slots():
    facts = detect_opp_move_punishments(
        post_opp_fen=RE1_POST_FEN,
        user_best_reply_san=RE1_REPLY,
        post_opp_pv_after_best=RE1_PV,
        user_color="black",
        post_opp_eval_before_cp=-78,
    )

    assert facts["opp_user_reply_unsafe_recapture_pawn_fork"] is True
    assert facts["opp_unsafe_recapture_san"] == "Rxe4"
    assert facts["opp_unsafe_fork_san"] == "d5"
    assert facts["opp_unsafe_recapturing_piece"] == "rook"
    assert facts["opp_unsafe_recapturing_square"] == "e4"
    assert facts["opp_unsafe_other_piece"] == "bishop"
    assert facts["opp_unsafe_other_square"] == "c4"
    assert facts["opp_unsafe_response_san"] == "Bxd5"
    assert facts["opp_unsafe_payoff_san"] == "Qxd5"
    assert facts["opp_unsafe_setup_piece"] == "knight"
    assert facts["opp_unsafe_payoff_piece"] == "bishop"
    assert facts["opp_unsafe_recapture_pawn_fork_proof"]["fingerprint"]


def test_re1_central_caption_replaces_immediate_capture_fallback():
    board = chess.Board(RE1_PRE_FEN)
    move = board.parse_san("Re1")
    post = board.copy(stack=False)
    post.push(move)
    lookup_key = " ".join(post.fen().split()[:4])
    facts = {
        "mover_is_user": False,
        "played_san": "Re1",
        "cp_loss": 40,
        "best_move_san_differs": True,
    }

    coach_line = inject_opp_side_narration_facts(
        facts,
        fen_before=RE1_PRE_FEN,
        board=board,
        move=move,
        move_san="Re1",
        full_move_number=6,
        is_user=False,
        opp_cp_loss=40,
        eval_lookup={
            lookup_key: {
                "best_move": RE1_REPLY,
                "pv_after_best": RE1_PV,
                "eval_before": -78,
            }
        },
        user_color="black",
    )
    caption = render_rule("R12_blunder", facts)

    assert coach_line == (
        ["Re1", "Nxe4", "Rxe4", "d5", "Bxd5", "Qxd5"],
        6,
    )
    assert caption == (
        "Opponent's Re1 is an inaccuracy. Play Nxe4. If Rxe4, d5 "
        "attacks their rook at e4 and bishop at c4 together. After "
        "Bxd5 Qxd5, your knight and their bishop both come off the "
        "board. Before recapturing, check whether a pawn push can "
        "attack two pieces."
    )
    assert "trades his pawn" not in caption
    assert verify_caption(
        caption,
        {
            "fen_before": RE1_PRE_FEN,
            "move_san": "Re1",
            "is_user_move": False,
            "cp_loss": 40,
            "best_move_san": "d3",
            "pv_after_played": [
                "Nxe4",
                "Rxe4",
                "d5",
                "Bxd5",
            ],
            "pv_after_best": [],
        },
        strict_v2=True,
    ) == []


def test_re1_full_decision_carries_caption_and_interactive_six_move_line():
    post = chess.Board(RE1_PRE_FEN)
    post.push_san("Re1")
    lookup_key = " ".join(post.fen().split()[:4])
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=RE1_PRE_FEN,
            played_san="Re1",
            mover_is_user=False,
            mover_is_white=True,
            user_color="black",
            full_move_number=6,
            move_history_san=[],
            best_move_san="d3",
            # V5 supplies the opponent's loss through both fields before
            # calling the central pipeline (see _cpl in the per-move loop).
            cp_loss=40,
            opp_cp_loss=40,
            opp_eval_before=-38,
            opp_eval_after=-78,
            pv_after_played=["Nxe4", "Rxe4", "d5", "Bxd5"],
            allow_fresh_engine_verification=False,
        ),
        CrossMoveState(),
        eval_lookup={
            lookup_key: {
                "best_move": RE1_REPLY,
                "pv_after_best": RE1_PV,
                "eval_before": -78,
            }
        },
        severity_override="opp_inaccuracy",
    )

    assert decision.should_skip is False
    assert decision.text.caption == (
        "Opponent's Re1 is an inaccuracy. Play Nxe4. If Rxe4, d5 "
        "attacks their rook at e4 and bishop at c4 together. After "
        "Bxd5 Qxd5, your knight and their bishop both come off the "
        "board. Before recapturing, check whether a pawn push can "
        "attack two pieces."
    )
    assert decision.coach_line_moves == [
        "Re1",
        "Nxe4",
        "Rxe4",
        "d5",
        "Bxd5",
        "Qxd5",
    ]
    assert decision.coach_line_length_hint == 6
    assert decision.debug_facts["opp_unsafe_recapture_pawn_fork_proof"]


def test_full_decision_does_not_activate_unproved_generic_opponent_line():
    post = chess.Board(RE1_PRE_FEN)
    post.push_san("Re1")
    lookup_key = " ".join(post.fen().split()[:4])
    decision = build_move_teaching_decision(
        MoveInputs(
            fen_before=RE1_PRE_FEN,
            played_san="Re1",
            mover_is_user=False,
            mover_is_white=True,
            user_color="black",
            full_move_number=6,
            move_history_san=[],
            best_move_san="d3",
            cp_loss=40,
            opp_cp_loss=40,
            opp_eval_before=-38,
            opp_eval_after=-78,
            allow_fresh_engine_verification=False,
        ),
        CrossMoveState(),
        eval_lookup={
            lookup_key: {
                "best_move": RE1_REPLY,
                "pv_after_best": [],
                "eval_before": -78,
            }
        },
        severity_override="opp_inaccuracy",
    )

    assert not decision.debug_facts.get(
        "opp_user_reply_unsafe_recapture_pawn_fork"
    )
    assert decision.coach_line_moves == []
    assert decision.coach_line_length_hint is None


def test_second_resolution_renders_the_concrete_pawn_payoff():
    facts = {
        "mover_is_user": False,
        "played_san": "Nf6",
        "cp_loss": 494,
        "user_best_reply_san": NXC4_REPLY,
        **detect_opp_move_punishments(
            post_opp_fen=NXC4_PRE_FEN,
            user_best_reply_san=NXC4_REPLY,
            post_opp_pv_after_best=NXC4_PV,
            user_color="black",
        ),
    }

    caption = render_rule("R12_blunder", facts)

    assert caption is not None
    assert (
        "If Qxc4, d5 attacks their queen at c4 and pawn at e4 together."
        in caption
    )
    assert "After Qe2 dxe4, you also take their pawn." in caption
    assert caption.endswith(
        "Before recapturing, check whether a pawn push can attack two pieces."
    )


def test_atomic_slots_without_typed_proof_cannot_select_the_new_caption():
    facts = {
        "mover_is_user": False,
        "played_san": "Re1",
        "cp_loss": 40,
        "user_best_reply_san": "Nxe4",
        "opp_user_reply_unsafe_recapture_pawn_fork": True,
        "opp_unsafe_recapture_san": "Rxe4",
        "opp_unsafe_fork_san": "d5",
        "opp_unsafe_recapturing_piece": "rook",
        "opp_unsafe_recapturing_square": "e4",
        "opp_unsafe_other_piece": "bishop",
        "opp_unsafe_other_square": "c4",
        "opp_unsafe_response_san": "Bxd5",
        "opp_unsafe_payoff_san": "Qxd5",
        "opp_unsafe_setup_piece": "knight",
        "opp_unsafe_payoff_piece": "bishop",
        "opp_unsafe_resolution_kind": (
            "fork_target_captures_pawn_then_is_recaptured"
        ),
    }

    caption = render_rule("R12_blunder", facts)

    assert caption is not None
    assert "pawn push can attack two pieces" not in caption


def test_ordinary_immediate_capture_keeps_existing_fallback():
    facts = detect_opp_move_punishments(
        post_opp_fen=RE1_POST_FEN,
        user_best_reply_san=RE1_REPLY,
        post_opp_pv_after_best=[],
        user_color="black",
    )

    assert not facts.get("opp_user_reply_unsafe_recapture_pawn_fork")
    assert not facts.get("opp_unsafe_recapture_pawn_fork_proof")
