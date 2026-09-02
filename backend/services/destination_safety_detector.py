"""Exact, deterministic destination-safety evidence for planning.

This detector makes one narrow claim: after a player moves a non-pawn piece,
the stored best reply immediately captures that exact piece and exhaustive
legal exchange analysis says the capture wins at least a minor-piece-equivalent
amount. Stored Stockfish cp_loss remains the independent consequence gate.

No engine or model is called here. The service consumes only the board and
Stockfish evidence already stored with a move evaluation.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

import chess


FACT_VERSION = "piece_safety.destination_safety_exact.v1"
QUALITY_ID = "gap:piece_safety:destination_safety_exact"
REASON_SEMANTIC_VERSION = "destination_safety_reason.v1"
SEE_FLOOR_CP = 150
CP_LOSS_FLOOR = 150
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


def _safe_cp(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _captured_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return PIECE_VALUES[chess.PAWN]
    captured = board.piece_at(move.to_square)
    return PIECE_VALUES[captured.piece_type] if captured else 0


def _promotion_gain(move: chess.Move) -> int:
    if move.promotion is None:
        return 0
    return PIECE_VALUES[move.promotion] - PIECE_VALUES[chess.PAWN]


def _exact_exchange_gain(board: chess.Board, target: int) -> int:
    """Return the best material gain from optional legal captures on target.

    Every legal capturing choice is explored at every ply. Returning zero
    models declining an unfavorable continuation. This deliberately avoids the
    least-valuable-attacker approximation used by the broad D_live census.
    """
    best = 0
    replies = [
        move
        for move in board.legal_moves
        if board.is_capture(move) and move.to_square == target
    ]
    for move in replies:
        captured = _captured_value(board, move) + _promotion_gain(move)
        board.push(move)
        continuation = _exact_exchange_gain(board, target)
        board.pop()
        best = max(best, captured - continuation)
    return max(0, best)


def _optional_exchange_line(
    board: chess.Board,
    target: int,
) -> Tuple[int, Tuple[chess.Move, ...]]:
    """Return optional best gain and one deterministic principal capture line."""
    best_gain = 0
    best_line: Tuple[chess.Move, ...] = ()
    replies = sorted(
        (
            move for move in board.legal_moves
            if board.is_capture(move) and move.to_square == target
        ),
        key=lambda move: move.uci(),
    )
    for move in replies:
        captured = _captured_value(board, move) + _promotion_gain(move)
        after = board.copy(stack=False)
        after.push(move)
        continuation_gain, continuation_line = _optional_exchange_line(after, target)
        gain = captured - continuation_gain
        line = (move,) + continuation_line
        if gain > best_gain or (
            gain == best_gain and line and (
                not best_line
                or tuple(item.uci() for item in line)
                < tuple(item.uci() for item in best_line)
            )
        ):
            best_gain = gain
            best_line = line
    return max(0, best_gain), best_line


def _best_forced_destination_capture(
    board: chess.Board,
    target: int,
) -> Tuple[Optional[int], Tuple[chess.Move, ...]]:
    """Return the opponent's best forced capture line, even when it loses."""
    best_gain: Optional[int] = None
    best_line: Tuple[chess.Move, ...] = ()
    captures = sorted(
        (
            move for move in board.legal_moves
            if board.is_capture(move) and move.to_square == target
        ),
        key=lambda move: move.uci(),
    )
    for move in captures:
        captured = _captured_value(board, move) + _promotion_gain(move)
        after = board.copy(stack=False)
        after.push(move)
        continuation_gain, continuation_line = _optional_exchange_line(after, target)
        gain = captured - continuation_gain
        line = (move,) + continuation_line
        if best_gain is None or gain > best_gain or (
            gain == best_gain
            and tuple(item.uci() for item in line)
            < tuple(item.uci() for item in best_line)
        ):
            best_gain = gain
            best_line = line
    return best_gain, best_line


def _human_list(values: Iterable[str]) -> str:
    items = [str(value) for value in values if value]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _piece_at(board: chess.Board, square: int) -> str:
    piece = board.piece_at(square)
    return chess.piece_name(piece.piece_type) if piece else "piece"


def _neutral_choices(
    seed: str,
    correct_label: str,
    false_label: str,
    unsure_label: str,
) -> Tuple[Tuple[Any, ...], Tuple[str, ...]]:
    from services.teaching_reason_contracts import ReasonChoice

    correct_first = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % 2 == 0
    ordered = (
        (("a", correct_label), ("b", false_label))
        if correct_first
        else (("a", false_label), ("b", correct_label))
    )
    accepted = "a" if correct_first else "b"
    return (
        tuple(ReasonChoice(choice_id=key, label=label) for key, label in (
            *ordered,
            ("unsure", unsure_label),
        )),
        (accepted,),
    )


def _component(
    *,
    seed: str,
    kind: str,
    prompt: str,
    correct_label: str,
    false_label: str,
    unsure_label: str,
    facts: Dict[str, Any],
    success_text: str,
    correction_text: str,
):
    from services.teaching_reason_contracts import ReasonComponent

    question_id = hashlib.sha256(f"{seed}|{kind}".encode("utf-8")).hexdigest()[:16]
    choices, accepted = _neutral_choices(
        question_id,
        correct_label,
        false_label,
        unsure_label,
    )
    return ReasonComponent(
        question_id=question_id,
        kind=kind,
        prompt=prompt,
        choices=choices,
        accepted_choice_ids=accepted,
        facts=facts,
        success_text=success_text,
        correction_text=correction_text,
    )


def build_destination_safety_reason_bundle(
    fen: str,
    supplied_move: str,
):
    """Build the canonical typed explanation for the exact submitted move.

    The bundle never infers a mental cause. It states only legal piece/square
    relationships proven by python-chess plus both exchange implementations.
    """
    from services.legal_exchange_verifier import VERIFIER_VERSION
    from services.teaching_reason_contracts import ReasonProof, TeachingReasonBundle

    board = chess.Board(str(fen or ""))
    text = str(supplied_move or "").strip()
    try:
        move = chess.Move.from_uci(text.lower())
        if move not in board.legal_moves:
            raise ValueError("illegal move")
    except ValueError:
        move = board.parse_san(text)
    if move not in board.legal_moves:
        raise ValueError("illegal move")

    grade = grade_destination_safety_candidate(board.fen(), move.uci())
    piece = board.piece_at(move.from_square)
    if piece is None:
        raise ValueError("move has no piece")
    move_san = board.san(move)
    normalized = " ".join(board.fen().split()[:4])
    position_fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    proof_payload = {
        "position": position_fingerprint,
        "move": move.uci(),
        "target": grade,
    }
    proof_fingerprint = hashlib.sha256(
        json.dumps(proof_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    proof = ReasonProof(
        authority="dual_legal_exchange",
        quality_id=QUALITY_ID,
        detector_version=FACT_VERSION,
        verifier_version=VERIFIER_VERSION,
        fingerprint=proof_fingerprint,
    )
    target_result = str(grade.get("status") or "unmeasured")
    if target_result == "unmeasured" or not grade.get("proofs_agree"):
        return TeachingReasonBundle(
            semantic_version=REASON_SEMANTIC_VERSION,
            position_fingerprint=position_fingerprint,
            move_uci=move.uci(),
            move_san=move_san,
            target_result="unmeasured",
            safety_kind=str(grade.get("reason") or "unmeasured"),
            components=(),
            proof=proof,
        )

    mover = board.turn
    opponent = not mover
    origin = chess.square_name(move.from_square)
    destination = chess.square_name(move.to_square)
    moved_piece = chess.piece_name(piece.piece_type)
    seed = f"{position_fingerprint}|{move.uci()}"
    components: List[Any] = []

    origin_attackers = sorted(board.attackers(opponent, move.from_square))
    if origin_attackers:
        attacker_labels = [
            f"the {_piece_at(board, square)} on {chess.square_name(square)}"
            for square in origin_attackers
        ]
        same_type_targets: List[int] = []
        relevant_attacker: Optional[int] = None
        if len(origin_attackers) == 1:
            candidate_attacker = origin_attackers[0]
            same_type_targets = sorted(
                square for square in board.attacks(candidate_attacker)
                if (target_piece := board.piece_at(square)) is not None
                and target_piece.color == mover
                and target_piece.piece_type == piece.piece_type
            )
            if len(same_type_targets) >= 2:
                relevant_attacker = candidate_attacker

        if relevant_attacker is not None:
            attacker_piece = _piece_at(board, relevant_attacker)
            attacker_square = chess.square_name(relevant_attacker)
            target_squares = [chess.square_name(square) for square in same_type_targets]
            plural = f"{moved_piece}s"
            correct = f"My {plural} on {_human_list(target_squares)}."
            false = (
                f"Only the {moved_piece} on {origin}; none of my other "
                f"{plural} was attacked."
            )
            prompt = (
                f"Which of your {plural} did the {attacker_piece} on "
                f"{attacker_square} attack?"
            )
            success = (
                f"The {attacker_piece} on {attacker_square} attacked your "
                f"{plural} on {_human_list(target_squares)}."
            )
            facts = {
                "attackers": [attacker_square],
                "attacked_piece": moved_piece,
                "attacked_squares": target_squares,
                "multi_target": True,
            }
        else:
            correct = f"{_human_list(attacker_labels).capitalize()}."
            false = f"No opponent piece was attacking my {moved_piece} on {origin}."
            prompt = f"Before {move_san}, what attacked your {moved_piece} on {origin}?"
            success = (
                f"{_human_list(attacker_labels).capitalize()} attacked your "
                f"{moved_piece} on {origin}."
            )
            facts = {
                "attackers": [chess.square_name(square) for square in origin_attackers],
                "attacked_piece": moved_piece,
                "attacked_squares": [origin],
                "multi_target": False,
            }
        components.append(_component(
            seed=seed,
            kind="incoming_threat",
            prompt=prompt,
            correct_label=correct,
            false_label=false,
            unsure_label="I did not notice that relationship before moving.",
            facts=facts,
            success_text=success,
            correction_text=(
                f"Before moving the {moved_piece} from {origin}, check which "
                "opponent pieces already attack it."
            ),
        ))

    after = board.copy(stack=False)
    after.push(move)
    opponent_name = "Black" if after.turn == chess.BLACK else "White"
    forced_gain, forced_line = _best_forced_destination_capture(after, move.to_square)
    capture_moves = [
        reply for reply in after.legal_moves
        if after.is_capture(reply) and reply.to_square == move.to_square
    ]
    if target_result == "pass" and not capture_moves:
        safety_kind = "destination_unattacked"
        destination_correct = (
            f"No. {opponent_name} has no legal capture of it on {destination}."
        )
        destination_false = (
            f"Yes. {opponent_name} can take it on {destination}, and I cannot recover it."
        )
        destination_success = (
            f"Your {moved_piece} is safe on {destination}: {opponent_name} has no legal "
            "capture of it there."
        )
    elif target_result == "pass" and len(forced_line) >= 2:
        safety_kind = "safe_by_recapture"
        destination_correct = f"No. The {moved_piece} on {destination} is protected."
        destination_false = (
            f"Yes. {opponent_name} can win the {moved_piece} on {destination} immediately."
        )
        destination_success = (
            f"Your {moved_piece} is safe on {destination} because the capture "
            "can be answered."
        )
    elif target_result == "fail" and forced_line:
        safety_kind = "destination_loses_material"
        destination_correct = (
            f"Yes. {opponent_name} can win the {moved_piece} on {destination}."
        )
        destination_false = f"No. The {moved_piece} on {destination} is protected."
        destination_success = (
            f"The {moved_piece} is not safe on {destination}; {opponent_name} has a legal "
            "capture that wins material."
        )
    else:
        return TeachingReasonBundle(
            semantic_version=REASON_SEMANTIC_VERSION,
            position_fingerprint=position_fingerprint,
            move_uci=move.uci(),
            move_san=move_san,
            target_result="unmeasured",
            safety_kind="incomplete_destination_proof",
            components=(),
            proof=proof,
        )

    components.append(_component(
        seed=seed,
        kind="destination_safety",
        prompt=(
            f"After {move_san}, can {opponent_name} win your {moved_piece} on "
            f"{destination} immediately?"
        ),
        correct_label=destination_correct,
        false_label=destination_false,
        unsure_label="I did not check the destination square.",
        facts={
            "piece": moved_piece,
            "origin": origin,
            "destination": destination,
            "target_result": target_result,
            "safety_kind": safety_kind,
        },
        success_text=destination_success,
        correction_text=(
            f"After choosing {move_san}, check every legal capture on "
            f"{destination} before deciding the {moved_piece} is safe."
        ),
    ))

    attacked_original = [
        square for square in origin_attackers
        if square in after.attacks(move.to_square)
    ]
    if attacked_original:
        attacked_labels = [
            f"the {_piece_at(after, square)} on {chess.square_name(square)}"
            for square in attacked_original
        ]
        components.append(_component(
            seed=seed,
            kind="counterattack",
            prompt=f"What else does {move_san} make your {moved_piece} do?",
            correct_label=f"It attacks {_human_list(attacked_labels)}.",
            false_label="It only moves away; it does not attack the piece that threatened it.",
            unsure_label="I did not notice that my move attacked back.",
            facts={
                "piece": moved_piece,
                "destination": destination,
                "targets": [chess.square_name(square) for square in attacked_original],
            },
            success_text=(
                f"{move_san} also attacks {_human_list(attacked_labels)}."
            ),
            correction_text=(
                f"After placing the {moved_piece} on {destination}, scan every "
                "opponent piece it now attacks."
            ),
        ))

    if target_result == "pass" and safety_kind == "safe_by_recapture":
        line_board = after.copy(stack=False)
        line_san: List[str] = []
        for line_move in forced_line[:2]:
            line_san.append(line_board.san(line_move))
            line_board.push(line_move)
        capture_san, recapture_san = line_san
        components.append(_component(
            seed=seed,
            kind="one_recapture_calculation",
            prompt=f"If {opponent_name} plays {capture_san}, what happens next?",
            correct_label=f"I answer {recapture_san}.",
            false_label=f"I cannot recapture on {destination}.",
            unsure_label="I saw the capture, but I did not calculate my reply.",
            facts={
                "capture_uci": forced_line[0].uci(),
                "capture_san": capture_san,
                "recapture_uci": forced_line[1].uci(),
                "recapture_san": recapture_san,
                "destination": destination,
                "forced_capture_gain_cp": forced_gain,
            },
            success_text=(
                f"After {capture_san}, {recapture_san} answers the capture."
            ),
            correction_text=(
                f"Do not stop at {capture_san}. Calculate one move farther and "
                f"find {recapture_san}."
            ),
        ))

    return TeachingReasonBundle(
        semantic_version=REASON_SEMANTIC_VERSION,
        position_fingerprint=position_fingerprint,
        move_uci=move.uci(),
        move_san=move_san,
        target_result=target_result,
        safety_kind=safety_kind,
        components=tuple(components),
        proof=proof,
    )


def derive_destination_safety_exact(move_evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """Derive the exact planning fact from one stored move evaluation."""
    fact: Dict[str, Any] = {
        "version": FACT_VERSION,
        "quality_id": QUALITY_ID,
        "derivation_status": "ok",
        "eligible": False,
        "outcome": "not_eligible",
        "fires": False,
        "reason": "not_eligible",
        "moved_piece": None,
        "destination": None,
        "opponent_reply_san": None,
        "opponent_reply_uci": None,
        "legal_destination_captures": 0,
        "exact_exchange_gain_cp": 0,
        "stockfish_cp_loss": _safe_cp(move_evaluation.get("cp_loss")),
    }
    fen = move_evaluation.get("fen_before")
    uci = str(move_evaluation.get("move_uci") or "")
    if not fen or len(uci) < 4:
        fact.update(derivation_status="unavailable", reason="missing_position")
        return fact
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            fact.update(derivation_status="unavailable", reason="illegal_move")
            return fact
        moved_piece = board.piece_at(move.from_square)
        if moved_piece is None:
            fact.update(derivation_status="unavailable", reason="missing_piece")
            return fact
        fact["moved_piece"] = chess.piece_name(moved_piece.piece_type)
        fact["destination"] = chess.square_name(move.to_square)
        if moved_piece.piece_type not in (
            chess.KNIGHT,
            chess.BISHOP,
            chess.ROOK,
            chess.QUEEN,
        ):
            fact["reason"] = "piece_not_eligible"
            return fact

        board.push(move)
        captures = [
            reply
            for reply in board.legal_moves
            if board.is_capture(reply) and reply.to_square == move.to_square
        ]
        has_promotion_capture = any(reply.promotion is not None for reply in captures)
        fact["legal_destination_captures"] = len(captures)
        if not captures:
            fact["reason"] = "not_legally_capturable"
            return fact

        fact["eligible"] = True
        exact_gain = _exact_exchange_gain(board, move.to_square)
        fact["exact_exchange_gain_cp"] = exact_gain
        if exact_gain < SEE_FLOOR_CP:
            fact["outcome"] = "handled"
            fact["reason"] = "exchange_is_safe"
            return fact
        if fact["stockfish_cp_loss"] < CP_LOSS_FLOOR:
            fact["outcome"] = "handled"
            fact["reason"] = "move_not_costly"
            return fact
        fact["outcome"] = "miss"

        # Promotion material is counted exactly for honest measurement, but
        # promotion-rank diagnoses were not present in the sealed Plan packet.
        # Keep them measurable and silent until reviewed independently.
        if has_promotion_capture:
            fact["reason"] = "promotion_exchange_not_promoted"
            return fact

        pv = move_evaluation.get("pv_after_played") or []
        if not pv:
            fact["reason"] = "missing_stored_reply"
            return fact
        reply = board.parse_san(str(pv[0]))
        fact["opponent_reply_san"] = board.san(reply)
        fact["opponent_reply_uci"] = reply.uci()
        if not board.is_capture(reply):
            fact["reason"] = "stored_reply_is_not_capture"
            return fact
        if reply.to_square != move.to_square:
            fact["reason"] = "stored_reply_captures_elsewhere"
            return fact

        fact["fires"] = True
        fact["reason"] = "exact_destination_capture"
        return fact
    except (
        AssertionError,
        TypeError,
        ValueError,
        chess.InvalidMoveError,
        chess.IllegalMoveError,
        chess.AmbiguousMoveError,
    ):
        fact.update(derivation_status="unavailable", reason="invalid_position_or_reply")
        return fact


def grade_destination_safety_candidate(fen: str, supplied_move: str) -> Dict[str, Any]:
    """Grade a new move against this detector's narrow concept."""
    result: Dict[str, Any] = {
        "version": FACT_VERSION,
        "quality_id": QUALITY_ID,
        "status": "unmeasured",
        "reason": "invalid_position_or_move",
        "move_uci": None,
        "moved_piece": None,
        "destination": None,
        "exact_exchange_gain_cp": None,
        "independent_exchange_gain_cp": None,
        "proofs_agree": False,
    }
    try:
        board = chess.Board(str(fen or ""))
        text = str(supplied_move or "").strip()
        try:
            move = chess.Move.from_uci(text.lower())
            if move not in board.legal_moves:
                raise ValueError("illegal move")
        except ValueError:
            move = board.parse_san(text)
        if move not in board.legal_moves:
            return result
        piece = board.piece_at(move.from_square)
        if piece is None:
            return result
        result.update({
            "move_uci": move.uci(),
            "moved_piece": chess.piece_name(piece.piece_type),
            "destination": chess.square_name(move.to_square),
        })
        if piece.piece_type not in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            result["reason"] = "piece_not_eligible"
            return result
        after = board.copy(stack=False)
        after.push(move)
        exact_gain = _exact_exchange_gain(after, move.to_square)
        from services.legal_exchange_verifier import independent_exchange_gain
        independent_gain = independent_exchange_gain(after, move.to_square)
        agrees = exact_gain == independent_gain
        result.update({
            "exact_exchange_gain_cp": exact_gain,
            "independent_exchange_gain_cp": independent_gain,
            "proofs_agree": agrees,
        })
        if not agrees:
            result["reason"] = "proof_disagreement"
            return result
        if exact_gain >= SEE_FLOOR_CP:
            result.update(status="fail", reason="destination_loses_material")
        else:
            result.update(status="pass", reason="destination_is_safe")
        return result
    except (AssertionError, TypeError, ValueError, chess.InvalidMoveError,
            chess.IllegalMoveError, chess.AmbiguousMoveError):
        return result


__all__ = [
    "CP_LOSS_FLOOR",
    "FACT_VERSION",
    "QUALITY_ID",
    "REASON_SEMANTIC_VERSION",
    "SEE_FLOOR_CP",
    "build_destination_safety_reason_bundle",
    "derive_destination_safety_exact",
    "grade_destination_safety_candidate",
]
