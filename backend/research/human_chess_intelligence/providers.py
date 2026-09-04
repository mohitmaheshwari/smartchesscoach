"""Offline Maia-2 and Otter adapters for the shared evidence contract.

Dependencies are imported lazily so each candidate can run in its own pinned
research environment.  The product runtime does not need either package.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Mapping, Optional

import chess

from .policy_contract import (
    HumanPolicyEvidence,
    HumanPolicyRequest,
    MoveProbability,
    PolicyContractError,
    validate_evidence,
)


def _ordered_moves(move_probabilities: Mapping[str, float]) -> tuple[MoveProbability, ...]:
    return tuple(
        MoveProbability(move, probability)
        for move, probability in sorted(
            move_probabilities.items(), key=lambda item: (-float(item[1]), item[0])
        )
    )


def history_reaches_fen(request: HumanPolicyRequest) -> bool:
    board = chess.Board()
    try:
        for move_uci in request.history_moves:
            board.push_uci(move_uci)
    except ValueError:
        return False
    expected = chess.Board(request.fen)
    # PGN-derived FENs use python-chess's legal-en-passant convention: after a
    # double pawn push the raw target square is omitted unless a capture is
    # actually legal. Compare that canonical legal state, not the internal raw
    # ep_square retained by replay.
    return (
        board.fen(en_passant="legal").split()[:4]
        == expected.fen(en_passant="legal").split()[:4]
    )


def maia2_inference_each_unrounded(model: Any, prepared: Any, fen: str, elo_self: int, elo_oppo: int):
    """Use Maia-2's own preprocessing/masks but retain raw probabilities.

    The public 0.11.0 helper rounds every legal move to four decimals. That is
    adequate for display and top-1 accuracy but turns low-probability moves
    into zero, making NLL and Brier comparisons invalid. This adapter calls the
    package's own tensor/move-map helpers and changes only that final rounding.
    """
    import torch
    from maia2.inference import _masked_softmax, preprocessing
    from maia2.utils import mirror_move

    all_moves_dict, elo_dict, all_moves_dict_reversed = prepared
    board_input, elo_self_bucket, elo_oppo_bucket, legal_moves = preprocessing(
        fen, elo_self, elo_oppo, elo_dict, all_moves_dict
    )
    device = next(model.parameters()).device
    model.eval()
    with torch.no_grad():
        logits_maia, _, logits_value = model(
            board_input.unsqueeze(0).to(device),
            torch.tensor([elo_self_bucket]).to(device),
            torch.tensor([elo_oppo_bucket]).to(device),
        )
        probs = _masked_softmax(logits_maia, legal_moves.unsqueeze(0).to(device))[0]

    value = (logits_value / 2 + 0.5).clamp(0, 1).item()
    black_to_move = fen.split()[1] == "b"
    if black_to_move:
        value = 1 - value
    ranked = []
    for index in legal_moves.nonzero(as_tuple=True)[0].tolist():
        move = all_moves_dict_reversed[index]
        if black_to_move:
            move = mirror_move(move)
        ranked.append((move, float(probs[index].item())))
    ranked.sort(key=lambda item: (-item[1], item[0]))
    return dict(ranked), value


def predict_maia2(
    request: HumanPolicyRequest,
    *,
    model: Any,
    prepared: Any,
    model_version: str,
    model_sha256: str,
    weight_family: str,
    inference_each_fn: Optional[Callable[..., Any]] = None,
) -> HumanPolicyEvidence:
    """Produce legal Maia-2 behavioral evidence; Maia has no clock/history input."""
    if inference_each_fn is None:
        inference_each_fn = maia2_inference_each_unrounded

    started = time.perf_counter()
    move_probs, win_probability = inference_each_fn(
        model,
        prepared,
        request.fen,
        request.player_elo,
        request.opponent_elo,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    evidence = HumanPolicyEvidence(
        provider="maia2",
        model_version=model_version,
        model_sha256=model_sha256,
        input_fingerprint=request.input_fingerprint,
        moves=_ordered_moves(move_probs),
        latency_ms=elapsed_ms,
        value_estimate=win_probability,
        policy_configuration={
            "clock_mode": "unsupported",
            "history_mode": "unsupported",
            "weight_family": weight_family,
        },
        warnings=("provider_does_not_consume_clock_history_or_time_control",),
    )
    return validate_evidence(request, evidence)


def predict_otter(
    request: HumanPolicyRequest,
    *,
    model: Any,
    model_version: str,
    model_sha256: str,
    mode: str,
) -> HumanPolicyEvidence:
    """Produce Otter evidence under an explicit observed or neutral ablation.

    `observed` rejects missing clocks, time controls, or history inconsistent
    with the supplied FEN. `neutral_ablation` deliberately removes history and
    sets the package's documented neutral clock value, and labels both facts.
    """
    if mode not in {"observed", "history_only", "clock_only", "neutral_ablation"}:
        raise PolicyContractError(
            "Otter mode must be observed, history_only, clock_only, or neutral_ablation"
        )

    warnings = []
    if mode in {"observed", "history_only", "clock_only"}:
        if not request.time_control:
            raise PolicyContractError("contextual Otter evidence requires time_control")
        if mode in {"observed", "clock_only"} and request.clock_fraction is None:
            raise PolicyContractError("clock-conditioned Otter evidence requires validated clock_fraction")
        if mode in {"observed", "history_only"} and not history_reaches_fen(request):
            raise PolicyContractError("observed Otter history does not reconstruct the request FEN")
        history = list(request.history_moves) if mode in {"observed", "history_only"} else []
        clock = request.clock_fraction if mode in {"observed", "clock_only"} else 0.5
        clock_mode = "observed_validated" if mode in {"observed", "clock_only"} else "controlled_neutral_0.5"
        history_mode = "observed_validated" if mode in {"observed", "history_only"} else "controlled_empty"
        if mode != "observed":
            warnings.append(f"{mode}_is_a_controlled_ablation")
    else:
        history = []
        clock = 0.5
        clock_mode = "controlled_neutral_0.5"
        history_mode = "controlled_empty"
        warnings.append("neutral_ablation_is_not_observed_player_evidence")

    legal_move_count = chess.Board(request.fen).legal_moves.count()
    started = time.perf_counter()
    result = model.predict(
        fen=request.fen,
        player_elo=request.player_elo,
        opponent_elo=request.opponent_elo,
        history_moves=history,
        time_control=request.time_control or "600+0",
        clock_fraction=clock,
        top_k=legal_move_count,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    move_probs = {
        str(item["move"]): float(item["probability"])
        for item in result.get("moves", [])
    }
    evidence = HumanPolicyEvidence(
        provider="otter",
        model_version=model_version,
        model_sha256=model_sha256,
        input_fingerprint=request.input_fingerprint,
        moves=_ordered_moves(move_probs),
        latency_ms=elapsed_ms,
        value_estimate=result.get("win_probability"),
        policy_configuration={
            "clock_mode": clock_mode,
            "history_mode": history_mode,
            "time_control_mode": "observed" if request.time_control else "controlled_default_600+0",
        },
        warnings=tuple(warnings),
    )
    return validate_evidence(request, evidence)
