#!/usr/bin/env python3
"""Create local-only, engine-grounded positional caption candidates.

No position data leaves the machine. Captions are assembled from legal move
geometry and Stockfish PVs, then rechecked from the FEN before they are written.
The resulting records remain admin candidates: runtime and mastery eligibility
are deliberately false.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import re
from typing import Any, Callable

import chess


PIECE_VALUE = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}
CENTRE = (chess.D4, chess.E4, chess.D5, chess.E5)
FORBIDDEN = (
    "centipawn",
    "engine",
    "eval",
    "improves the position",
    "weakens the position",
    "loses tempo",
    "key squares",
    "prophylaxis",
    "fianchetto",
    "zwischenzug",
    "zugzwang",
    "luft",
    "minority attack",
)
SQUARE_RE = re.compile(r"\b[a-h][1-8]\b", re.IGNORECASE)


def norm_fen(fen: str) -> str:
    return " ".join(chess.Board(fen).fen().split()[:4])


def fingerprint(row: dict[str, Any]) -> str:
    identity = f"{norm_fen(row['fen'])}|{row['played_uci']}|{row['best_uci']}"
    return sha256(identity.encode("utf-8")).hexdigest()


def expectation(wdl: dict[str, Any]) -> float:
    total = max(1, int(wdl.get("wins", 0)) + int(wdl.get("draws", 0)) + int(wdl.get("losses", 0)))
    return (float(wdl.get("wins", 0)) + 0.5 * float(wdl.get("draws", 0))) / total


def exclusion_scores(row: dict[str, Any]) -> dict[str, float]:
    evidence = row["engine_evidence"]
    best = evidence["root_top_lines"][0]
    played = evidence["played_line"]
    best_wdl = best["wdl"]
    decisive = max(best_wdl.get("wins", 0), best_wdl.get("losses", 0)) / 1000.0
    outcome_drop = max(0.0, expectation(best_wdl) - expectation(played["wdl"]))
    fresh_loss = max(0.0, float(evidence.get("fresh_loss_cp") or 0))
    margin = max(0.0, float(evidence.get("best_to_second_margin_cp") or 0))
    changed = not bool(evidence.get("stored_best_is_fresh_best"))
    already_decided = 100.0 * (
        0.76 * decisive
        + 0.14 * (1.0 - min(outcome_drop / 0.35, 1.0))
        + 0.10 * (1.0 - min(fresh_loss / 700.0, 1.0))
    )
    not_mistake = 100.0 * (
        0.48 * (1.0 - min(outcome_drop / 0.18, 1.0))
        + 0.30 * (1.0 - min(fresh_loss / 350.0, 1.0))
        + 0.12 * (1.0 if changed else 0.0)
        + 0.10 * (1.0 - min(margin / 180.0, 1.0))
    )
    return {
        "already_decided": round(already_decided, 3),
        "not_mistake": round(not_mistake, 3),
        "outcome_drop": round(outcome_drop, 4),
        "decisiveness": round(decisive, 4),
    }


def parse_line(board: chess.Board, uci_line: list[str]) -> list[tuple[chess.Board, chess.Move, str]]:
    current = board.copy()
    parsed: list[tuple[chess.Board, chess.Move, str]] = []
    for uci in uci_line:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move not in current.legal_moves:
            break
        parsed.append((current.copy(), move, current.san(move)))
        current.push(move)
    return parsed


def color_name(color: chess.Color) -> str:
    return "White" if color == chess.WHITE else "Black"


def piece_name(piece: chess.Piece | None) -> str:
    return chess.piece_name(piece.piece_type) if piece else "piece"


def centre_distance(square: int) -> int:
    return min(chess.square_distance(square, centre) for centre in CENTRE)


def file_state(board: chess.Board, file_index: int, mover: chess.Color) -> str:
    own = any(chess.square_file(square) == file_index for square in board.pieces(chess.PAWN, mover))
    enemy = any(chess.square_file(square) == file_index for square in board.pieces(chess.PAWN, not mover))
    if not own and not enemy:
        return "open"
    if not own:
        return "semi-open"
    return "blocked"


def is_passed_pawn(board: chess.Board, square: int, color: chess.Color) -> bool:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    for enemy_square in board.pieces(chess.PAWN, not color):
        enemy_file = chess.square_file(enemy_square)
        enemy_rank = chess.square_rank(enemy_square)
        if abs(enemy_file - file_index) > 1:
            continue
        if color == chess.WHITE and enemy_rank > rank_index:
            return False
        if color == chess.BLACK and enemy_rank < rank_index:
            return False
    return True


def attacked_own_pieces(board: chess.Board, color: chess.Color) -> list[int]:
    result = []
    for square, piece in board.piece_map().items():
        if piece.color != color or piece.piece_type == chess.KING:
            continue
        if board.is_attacked_by(not color, square):
            result.append(square)
    return result


def undefended_attacked(board: chess.Board, color: chess.Color) -> list[int]:
    return [
        square
        for square in attacked_own_pieces(board, color)
        if not board.attackers(color, square)
    ]


def valuable_attacks(board: chess.Board, from_square: int, enemy: chess.Color) -> list[int]:
    targets = [
        square
        for square in board.attacks(from_square)
        if (board.piece_at(square) is not None and board.piece_at(square).color == enemy)
    ]
    return sorted(targets, key=lambda square: PIECE_VALUE[board.piece_at(square).piece_type], reverse=True)


def has_opposition(board: chess.Board) -> bool:
    white_king = board.king(chess.WHITE)
    black_king = board.king(chess.BLACK)
    if white_king is None or black_king is None:
        return False
    aligned = (
        chess.square_file(white_king) == chess.square_file(black_king)
        or chess.square_rank(white_king) == chess.square_rank(black_king)
    )
    return aligned and chess.square_distance(white_king, black_king) == 2


def useful_rook_squares(board: chess.Board, square: int, mover: chess.Color) -> list[int]:
    return sorted(
        target
        for target in board.attacks(square)
        if board.piece_at(target) is None or board.piece_at(target).color != mover
    )


def reply_fact(board: chess.Board, line_uci: list[str], mover: chess.Color) -> tuple[str, dict[str, Any]]:
    parsed = parse_line(board, line_uci)
    actor = color_name(not mover)
    if len(parsed) < 2:
        if parsed:
            after_first = parsed[0][0].copy()
            after_first.push(parsed[0][1])
            if after_first.is_checkmate():
                return (
                    f"{actor} has no legal reply because {parsed[0][2]} is checkmate",
                    {"kind": "terminal_mate", "move_uci": parsed[0][1].uci()},
                )
            if after_first.is_stalemate():
                return (
                    f"{actor} has no legal move, so {parsed[0][2]} ends the game as a draw",
                    {"kind": "terminal_stalemate", "move_uci": parsed[0][1].uci()},
                )
        return "the line proves only the move itself", {"kind": "move_only", "verified": True}
    reply_board, reply, san = parsed[1]
    landing = chess.square_name(reply.to_square)
    captured = reply_board.piece_at(reply.to_square)
    if reply_board.is_en_passant(reply):
        captured = chess.Piece(chess.PAWN, mover)
    after = reply_board.copy()
    after.push(reply)
    if reply_board.is_capture(reply):
        return (
            f"{actor} answers {san}, taking the {piece_name(captured)} on {landing}",
            {"kind": "reply_capture", "reply_uci": reply.uci(), "target": landing, "captured": piece_name(captured)},
        )
    if after.is_check():
        return (
            f"{actor} answers {san}, checking the king from {landing}",
            {"kind": "reply_check", "reply_uci": reply.uci(), "landing": landing},
        )
    attacks = valuable_attacks(after, reply.to_square, mover)
    if attacks:
        target = attacks[0]
        target_piece = after.piece_at(target)
        return (
            f"{actor} answers {san}, attacking the {piece_name(target_piece)} on {chess.square_name(target)}",
            {"kind": "reply_attack", "reply_uci": reply.uci(), "target": chess.square_name(target)},
        )
    if len(parsed) >= 3:
        return (
            f"{actor} answers {san}, and the continuation reaches {parsed[2][2]}",
            {"kind": "reply_line", "reply_uci": reply.uci(), "next_uci": parsed[2][1].uci()},
        )
    return (
        f"{actor} answers {san}, moving from {chess.square_name(reply.from_square)} to {landing}",
        {"kind": "reply_move", "reply_uci": reply.uci()},
    )


def newly_defended_target(before: chess.Board, after: chess.Board, mover: chess.Color, moved_to: int) -> int | None:
    candidates = []
    for square in attacked_own_pieces(before, mover):
        if square == moved_to:
            continue
        remaining_piece = after.piece_at(square)
        if remaining_piece is None or remaining_piece.color != mover:
            continue
        before_count = len(before.attackers(mover, square))
        after_count = len(after.attackers(mover, square))
        if after_count > before_count and moved_to in after.attackers(mover, square):
            candidates.append(square)
    return max(candidates, key=lambda sq: PIECE_VALUE[after.piece_at(sq).piece_type], default=None)


def geometry_reason(row: dict[str, Any]) -> dict[str, Any]:
    board = chess.Board(row["fen"])
    mover = board.turn
    opponent = not mover
    best = chess.Move.from_uci(row["best_uci"])
    played = chess.Move.from_uci(row["played_uci"])
    best_san = board.san(best)
    played_san = board.san(played)
    best_piece = board.piece_at(best.from_square)
    played_piece = board.piece_at(played.from_square)
    best_capture = board.piece_at(best.to_square)
    played_capture = board.piece_at(played.to_square)
    if board.is_en_passant(best):
        best_capture = chess.Piece(chess.PAWN, opponent)
    if board.is_en_passant(played):
        played_capture = chess.Piece(chess.PAWN, opponent)
    after_best = board.copy()
    after_best.push(best)
    after_played = board.copy()
    after_played.push(played)
    best_line = row["engine_evidence"]["stored_best_line"]["pv_uci"]
    played_line = row["engine_evidence"]["played_line"]["pv_uci"]
    best_parsed = parse_line(board, best_line)
    played_parsed = parse_line(board, played_line)
    best_followup = None
    if len(best_parsed) >= 3:
        follow_board, follow_move, follow_san = best_parsed[2]
        if follow_board.is_capture(follow_move):
            captured = follow_board.piece_at(follow_move.to_square)
            if follow_board.is_en_passant(follow_move):
                captured = chess.Piece(chess.PAWN, not mover)
            best_followup = {
                "reply_san": best_parsed[1][2],
                "reply_uci": best_parsed[1][1].uci(),
                "follow_san": follow_san,
                "follow_uci": follow_move.uci(),
                "captured": piece_name(captured),
                "target": chess.square_name(follow_move.to_square),
            }
    played_reply, played_reply_proof = reply_fact(board, played_line, mover)
    best_reply, best_reply_proof = reply_fact(board, best_line, mover)
    best_to = chess.square_name(best.to_square)
    played_to = chess.square_name(played.to_square)
    best_from = chess.square_name(best.from_square)
    played_from = chess.square_name(played.from_square)

    category = "compare_replies"
    concept_id: str | None = "TAC_CHANGED_AFTER_MOVE"
    concept = "Compare the reply before choosing"
    better = f"{best_san} moves the {piece_name(best_piece)} from {best_from} to {best_to}; {best_reply}."
    played_fact = f"{played_san} moves the {piece_name(played_piece)} from {played_from} to {played_to}; {played_reply}."
    if (
        len(best_parsed) >= 3
        and len(played_parsed) >= 3
        and best_parsed[1][1] == played_parsed[1][1]
    ):
        contrast = f"After the same reply {best_parsed[1][2]}, {played_san} leads to {played_parsed[2][2]}, while {best_san} leads to {best_parsed[2][2]}."
    else:
        contrast = f"The concrete difference is the reply after {played_san} versus the reply after {best_san}."
    lesson = "Before choosing between quiet moves, calculate the opponent's strongest reply to each one."
    proof: list[dict[str, Any]] = [
        {"claim": "best_move_legal", "uci": best.uci()},
        {"claim": "played_move_legal", "uci": played.uci()},
        played_reply_proof,
        best_reply_proof,
    ]

    # A free or higher-value capture is the clearest contrast.
    if board.is_capture(best) and not board.is_capture(played) and best_capture:
        category = "take_available_piece"
        concept_id = "TAC_CHECKS_CAPTURES_THREATS"
        concept = "Take the concrete gain first"
        better = f"{best_san} takes the {piece_name(best_capture)} on {best_to} before moving elsewhere."
        played_fact = f"{played_san} moves the {piece_name(played_piece)} to {played_to} and leaves that capture unused."
        contrast = f"{best_san} changes the material on the board immediately; {played_san} does not."
        lesson = "Check every safe capture before choosing a quiet move; a concrete capture can matter more than slow improvement."
        proof.append({"claim": "best_capture", "uci": best.uci(), "captured": piece_name(best_capture)})
    elif (
        board.is_capture(best)
        and board.is_capture(played)
        and best.to_square == played.to_square
        and best_piece
        and best_piece.piece_type == chess.KING
        and played_piece
        and played_piece.piece_type == chess.PAWN
    ):
        category = "king_recaptures_keep_pawn"
        concept_id = "END_KING_ACTIVE"
        concept = "Use the king and keep the pawn"
        better = f"{best_san} uses the king from {best_from} to recapture on {best_to}."
        played_fact = f"{played_san} uses the pawn from {played_from} for the same capture."
        contrast = f"Both moves capture on {best_to}, but {best_san} keeps the pawn on {played_from}."
        lesson = "When the king can recapture safely in an endgame, compare whether using it preserves your pawn structure."
        proof.append({"claim": "king_recapture_keeps_pawn", "best": best.uci(), "played": played.uci()})
    elif (
        board.is_capture(best)
        and board.is_capture(played)
        and best.to_square == played.to_square
        and best_piece
        and played_piece
        and best_piece.piece_type != chess.KING
        and played_piece.piece_type != chess.KING
        and PIECE_VALUE[best_piece.piece_type] < PIECE_VALUE[played_piece.piece_type]
    ):
        category = "recapture_with_lower_value_piece"
        concept_id = "TAC_DEFENDER_COUNT"
        concept = "Use the cheaper piece to recapture"
        better = f"{best_san} uses the {piece_name(best_piece)} from {best_from} to recapture on {best_to}."
        played_fact = f"{played_san} uses the more valuable {piece_name(played_piece)} from {played_from} for the same capture."
        contrast = f"Both moves capture on {best_to}, but {best_san} keeps the {piece_name(played_piece)} on {played_from}."
        lesson = "When two pieces can recapture, compare which piece you want to keep active afterward."
        proof.append({"claim": "lower_value_recapture", "best": best.uci(), "played": played.uci()})
    elif (
        board.is_capture(best)
        and board.is_capture(played)
        and best_capture
        and played_capture
        and PIECE_VALUE[best_capture.piece_type] > PIECE_VALUE[played_capture.piece_type]
    ):
        category = "choose_more_valuable_capture"
        concept_id = "TAC_CHECKS_CAPTURES_THREATS"
        concept = "Take the more valuable target"
        better = f"{best_san} takes the {piece_name(best_capture)} on {best_to}."
        played_fact = f"{played_san} takes the {piece_name(played_capture)} on {played_to} instead."
        contrast = f"The {piece_name(best_capture)} on {best_to} is the larger immediate target, so {best_san} comes first."
        lesson = "When several captures are legal, compare the value and the reply before choosing one."
        proof.append({"claim": "higher_value_capture", "best": best.uci(), "played": played.uci()})
    elif after_best.is_check() and after_played.is_check() and best_followup:
        category = "forcing_check_sequence"
        concept_id = "TAC_CHECKS_CAPTURES_THREATS"
        concept = "Choose the check with a follow-up"
        better = f"{best_san} checks from {best_to}; after {best_followup['reply_san']}, {best_followup['follow_san']} takes the {best_followup['captured']} on {best_followup['target']}."
        played_fact = f"{played_san} also checks from {played_to}, but {played_reply}."
        contrast = f"{best_san} connects the check to a concrete capture; {played_san} gives check without that same follow-up."
        lesson = "Compare checks by what they force next; a check is useful when the follow-up wins something or improves the result."
        proof.append({"claim": "best_line_followup", **best_followup})
    elif (
        played_reply_proof["kind"] == "reply_capture"
        and best_reply_proof["kind"] == "reply_capture"
        and len(played_parsed) >= 2
        and len(best_parsed) >= 2
        and played_parsed[1][0].piece_at(played_parsed[1][1].to_square)
        and best_parsed[1][0].piece_at(best_parsed[1][1].to_square)
        and PIECE_VALUE[played_parsed[1][0].piece_at(played_parsed[1][1].to_square).piece_type]
        > PIECE_VALUE[best_parsed[1][0].piece_at(best_parsed[1][1].to_square).piece_type]
    ):
        played_lost = played_parsed[1][0].piece_at(played_parsed[1][1].to_square)
        best_lost = best_parsed[1][0].piece_at(best_parsed[1][1].to_square)
        category = "limit_the_reply_capture"
        concept_id = "TAC_CHANGED_AFTER_MOVE"
        concept = "Do not offer the larger target"
        better = f"{best_san} changes what can be taken; {best_reply}."
        played_fact = f"{played_san} allows the larger capture: {played_reply}."
        contrast = f"After {played_san}, the reply takes a {piece_name(played_lost)}; after {best_san}, it takes only a {piece_name(best_lost)}."
        lesson = "When both moves allow a capture, choose the line that keeps the more valuable piece safe."
        proof.append({"claim": "smaller_reply_capture", "played_reply": played_parsed[1][1].uci(), "best_reply": best_parsed[1][1].uci()})
    elif played_reply_proof["kind"] == "reply_capture" and best_reply_proof["kind"] != "reply_capture":
        category = "avoid_reply_capture"
        concept_id = "TAC_CHANGED_AFTER_MOVE"
        concept = "Check what the reply can take"
        better = f"{best_san} changes the position first; after it, {best_reply}."
        played_fact = f"{played_san} allows this concrete reply: {played_reply}."
        contrast = f"Only {played_san} gives the immediate capture on {played_reply_proof['target']}; {best_san} avoids that version."
        lesson = "After choosing a move, scan every opponent capture before judging the move safe."
    elif played_reply_proof["kind"] == "reply_check" and best_reply_proof["kind"] != "reply_check":
        category = "avoid_forcing_check"
        concept_id = "TAC_CHECKS_CAPTURES_THREATS"
        concept = "Answer forcing moves before your plan"
        better = f"{best_san} changes the move order; after it, {best_reply}."
        played_fact = f"{played_san} allows this concrete reply: {played_reply}."
        contrast = f"The check after {played_san} forces a response, while {best_san} avoids that immediate check."
        lesson = "Before starting your plan, look for the opponent's checks and deal with the forcing one first."
    elif played_reply_proof["kind"] == "reply_attack" and best_reply_proof["kind"] != "reply_attack":
        category = "avoid_reply_attack"
        concept_id = "TAC_CHANGED_AFTER_MOVE"
        concept = "Do not give the reply a target"
        better = f"{best_san} changes the setup; after it, {best_reply}."
        played_fact = f"{played_san} allows this reply: {played_reply}."
        contrast = f"Only {played_san} lets the reply attack the piece on {played_reply_proof['target']}; {best_san} avoids that version."
        lesson = "Before settling on a move, check whether the opponent's reply attacks a piece and forces you to respond."
        proof.append({"claim": "avoid_reply_attack", "target": played_reply_proof["target"], "played_reply": played_reply_proof["reply_uci"]})
    elif (
        best_piece
        and best_piece.piece_type == chess.KING
        and len(board.piece_map()) <= 14
        and has_opposition(after_best)
        and not has_opposition(after_played)
    ):
        category = "take_opposition"
        concept_id = "END_OPPOSITION"
        concept = "Make the other king move first"
        enemy_king = chess.square_name(after_best.king(opponent))
        better = f"{best_san} places the king on {best_to}, two squares from the enemy king on {enemy_king}."
        played_fact = f"{played_san} moves the {piece_name(played_piece)} to {played_to} without creating that king standoff."
        contrast = f"After {best_san}, the kings face each other with {color_name(opponent)} to move; after {played_san}, they do not."
        lesson = "In king endgames, try to face the enemy king with one square between them and make it move first."
        proof.append({"claim": "opposition_after_best", "best": best.uci()})
    elif (
        best_piece
        and best_piece.piece_type == chess.KING
        and len(board.piece_map()) <= 14
        and centre_distance(best.to_square)
        < (
            centre_distance(played.to_square)
            if played_piece and played_piece.piece_type == chess.KING
            else centre_distance(best.from_square)
        )
    ):
        category = "active_endgame_king"
        concept_id = "END_KING_ACTIVE"
        concept = "Bring the king into the endgame"
        if centre_distance(best.to_square) < centre_distance(best.from_square):
            better = f"{best_san} brings the king from {best_from} toward the centre on {best_to}."
            king_claim = {"claim": "king_centralizes", "from": best_from, "to": best_to}
        else:
            better = f"{best_san} keeps the king on {best_to}, closer to the centre than {played_to}."
            king_claim = {"claim": "king_more_central_than_played", "best": best_to, "played": played_to}
        played_fact = f"{played_san} puts the {piece_name(played_piece)} on {played_to} while the king stays farther away."
        contrast = f"{best_san} gives the king a direct route to the pawns; {played_san} spends the move elsewhere."
        lesson = "With few pieces left, activate the king before making a move that can wait."
        proof.append(king_claim)
    elif best_piece and best_piece.piece_type == chess.KING and len(board.piece_map()) <= 14:
        current_king_square = played.to_square if played_piece and played_piece.piece_type == chess.KING else best.from_square
        pawn_candidates = []
        for pawn_square in board.pieces(chess.PAWN, chess.WHITE) | board.pieces(chess.PAWN, chess.BLACK):
            improvement = chess.square_distance(current_king_square, pawn_square) - chess.square_distance(best.to_square, pawn_square)
            if improvement > 0:
                pawn_candidates.append((improvement, pawn_square))
        if pawn_candidates:
            _, pawn_square = max(pawn_candidates)
            pawn_square_name = chess.square_name(pawn_square)
            category = "king_approaches_pawn"
            concept_id = "END_KING_ACTIVE"
            concept = "Bring the king toward the pawns"
            better = f"{best_san} moves the king to {best_to}, one step closer to the pawn on {pawn_square_name}."
            played_fact = f"{played_san} puts the {piece_name(played_piece)} on {played_to} and leaves the king farther from that pawn."
            contrast = f"{best_san} shortens the king's route to {pawn_square_name}; {played_san} does not."
            lesson = "In a reduced position, move the king toward the pawn you need to win or stop."
            proof.append({"claim": "king_closer_to_pawn", "pawn": pawn_square_name, "best": best_to, "played_king": chess.square_name(current_king_square)})
        else:
            category = "compare_replies"
    elif best_piece and best_piece.piece_type == chess.PAWN and is_passed_pawn(after_best, best.to_square, mover):
        category = "advance_passed_pawn"
        concept_id = "END_PASSED_PAWN"
        concept = "Push the passed pawn with purpose"
        better = f"{best_san} advances the passed pawn to {best_to}, one rank closer to promotion."
        played_fact = f"{played_san} moves the {piece_name(played_piece)} to {played_to} and leaves that pawn on {best_from}."
        contrast = f"{best_san} makes the opponent answer the passed pawn sooner; {played_san} gives it no progress."
        lesson = "In an endgame, calculate whether a passed pawn can advance safely before making a side move."
        proof.append({"claim": "passed_pawn_after_best", "square": best_to})
    elif (
        best_piece
        and best_piece.piece_type == chess.PAWN
        and len(board.piece_map()) <= 14
        and not board.is_capture(best)
    ):
        category = "advance_endgame_pawn"
        concept_id = None
        concept = "Make progress in the pawn race"
        better = f"{best_san} advances the pawn from {best_from} to {best_to}, one rank closer to promotion."
        played_fact = f"{played_san} moves the {piece_name(played_piece)} to {played_to} while that pawn stays on {best_from}."
        contrast = f"{best_san} gains one step in the pawn race; {played_san} spends the move elsewhere."
        lesson = "In a pawn ending, count both sides' moves to promotion before spending a move on the king or another pawn."
        proof.append({"claim": "endgame_pawn_advance", "from": best_from, "to": best_to})
    elif best_piece and best_piece.piece_type == chess.ROOK and file_state(after_best, chess.square_file(best.to_square), mover) in {"open", "semi-open"}:
        state = file_state(after_best, chess.square_file(best.to_square), mover)
        category = "rook_file"
        concept_id = "MID_ROOK_OPEN_FILE"
        concept = "Put the rook where pawns do not block it"
        file_name = chess.FILE_NAMES[chess.square_file(best.to_square)]
        better = f"{best_san} puts the rook on {best_to}, on the {state} {file_name}-file."
        played_fact = f"{played_san} moves the {piece_name(played_piece)} to {played_to} instead of placing the rook on the {file_name}-file."
        contrast = f"On {best_to} the rook has the file available; {played_san} leaves the rook out of that lane."
        lesson = "When no tactic is urgent, look for an open or semi-open file for a rook."
        proof.append({"claim": "rook_file", "state": state, "file": file_name, "square": best_to})
    elif best_piece and best_piece.piece_type == chess.ROOK:
        before_rook_reach = useful_rook_squares(board, best.from_square, mover)
        after_rook_reach = useful_rook_squares(after_best, best.to_square, mover)
        if len(after_rook_reach) >= len(before_rook_reach) + 2:
            named_squares = [chess.square_name(square) for square in after_rook_reach[:3]]
            category = "activate_rook"
            concept_id = None
            concept = "Give the rook more squares"
            better = f"{best_san} moves the rook to {best_to}, where it can reach {', '.join(named_squares)}."
            played_fact = f"{played_san} moves the {piece_name(played_piece)} to {played_to} and leaves the rook on {best_from}."
            contrast = f"The rook has more usable squares after {best_san}; {played_san} leaves its old limits in place."
            lesson = "For a quiet rook move, count the open squares it gains from the new rank or file."
            proof.append({"claim": "rook_mobility", "from": best_from, "to": best_to, "squares": named_squares})
        else:
            category = "compare_replies"
    else:
        loose_before = set(undefended_attacked(board, mover))
        if (
            best.from_square in loose_before
            and not after_best.is_attacked_by(opponent, best.to_square)
            and (
                played.from_square != best.from_square
                or after_played.is_attacked_by(opponent, played.to_square)
            )
        ):
            category = "save_attacked_piece"
            concept_id = "TAC_HANGING_PIECE"
            concept = "Move the attacked piece to safety"
            better = f"{best_san} moves the attacked {piece_name(best_piece)} from {best_from} to {best_to}, where it is not attacked."
            played_fact = f"{played_san} moves the {piece_name(played_piece)} to {played_to} instead of solving that loose piece."
            contrast = f"{best_san} removes the immediate target; {played_san} leaves the attacked piece available."
            lesson = "Before starting a new plan, find every attacked piece that has no defender."
            proof.append({"claim": "best_saves_loose_piece", "from": best_from, "to": best_to})
        else:
            target = newly_defended_target(board, after_best, mover, best.to_square)
            played_also_adds_defender = bool(
                target is not None
                and len(after_played.attackers(mover, target))
                > len(board.attackers(mover, target))
            )
            if target is not None and not played_also_adds_defender:
                target_name = piece_name(after_best.piece_at(target))
                target_square = chess.square_name(target)
                category = "add_defender"
                concept_id = "DEF_MOST_ATTACKED"
                concept = "Add a defender where it is needed"
                better = f"{best_san} places the {piece_name(best_piece)} on {best_to}, where it adds a defender to the {target_name} on {target_square}."
                played_fact = f"{played_san} moves the {piece_name(played_piece)} to {played_to} without adding that defender."
                contrast = f"After {best_san}, the {target_name} on {target_square} has more support; after {played_san}, it does not."
                lesson = "When one of your pieces is attacked, count its attackers and defenders before moving elsewhere."
                proof.append({"claim": "best_adds_defender", "target": target_square, "defender": best_to})
            else:
                best_targets = valuable_attacks(after_best, best.to_square, opponent)
                played_targets = set(valuable_attacks(after_played, played.to_square, opponent))
                new_targets = [
                    target
                    for target in best_targets
                    if target not in played_targets
                    and len(after_best.attackers(mover, target)) > len(board.attackers(mover, target))
                    and len(after_played.attackers(mover, target)) <= len(board.attackers(mover, target))
                ]
                if new_targets:
                    target = new_targets[0]
                    target_name = piece_name(after_best.piece_at(target))
                    target_square = chess.square_name(target)
                    category = "create_concrete_threat"
                    concept_id = "TAC_CHECKS_CAPTURES_THREATS"
                    concept = "Make a threat with a target"
                    better = f"{best_san} puts the {piece_name(best_piece)} on {best_to}, attacking the {target_name} on {target_square}."
                    played_fact = f"{played_san} puts the {piece_name(played_piece)} on {played_to} without creating that attack."
                    contrast = f"{best_san} gives the opponent a concrete piece to answer on {target_square}; {played_san} does not."
                    lesson = "A useful improving move should attack, defend, or create a clear next threat."
                    proof.append({"claim": "best_attacks_target", "attacker": best_to, "target": target_square})
                elif best_piece and best_piece.piece_type in {chess.KNIGHT, chess.BISHOP, chess.QUEEN} and centre_distance(best.to_square) < centre_distance(best.from_square):
                    category = "centralize_piece"
                    concept_id = "OP_CLAIM_CENTER" if row.get("move_number", 99) <= 12 else None
                    concept = "Move the piece toward the centre"
                    attacks = [chess.square_name(square) for square in after_best.attacks(best.to_square)]
                    named = ", ".join(attacks[:3])
                    better = f"{best_san} moves the {piece_name(best_piece)} from {best_from} toward the centre on {best_to}, where it reaches {named}."
                    played_fact = f"{played_san} puts the {piece_name(played_piece)} on {played_to} instead."
                    contrast = f"The {piece_name(best_piece)} has central work from {best_to}; {played_san} uses the move on {played_to}."
                    lesson = "When moves are quiet, prefer the piece whose new square gives it more concrete jobs."
                    proof.append({"claim": "best_centralizes", "from": best_from, "to": best_to, "attacks": attacks[:3]})

    caption = f"{played_fact} {better} {contrast} {lesson}"
    return {
        "category": category,
        "concept_label": concept,
        "canonical_concept_id": concept_id,
        "better_move_fact": better,
        "played_move_fact": played_fact,
        "contrast": contrast,
        "transferable_lesson": lesson,
        "caption": caption,
        "claim_proof": proof,
    }


def verify_claims(row: dict[str, Any], reason: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    board = chess.Board(row["fen"])
    mover = board.turn
    opponent = not mover
    best = chess.Move.from_uci(row["best_uci"])
    played = chess.Move.from_uci(row["played_uci"])
    if best not in board.legal_moves:
        issues.append("best_move_illegal")
    if played not in board.legal_moves:
        issues.append("played_move_illegal")
    after_best = board.copy()
    after_best.push(best)
    after_played = board.copy()
    after_played.push(played)
    for claim in reason["claim_proof"]:
        kind = claim.get("claim") or claim.get("kind")
        if kind == "best_capture" and not board.is_capture(best):
            issues.append("best_capture_unverified")
        elif kind == "smaller_reply_capture":
            played_line = parse_line(board, row["engine_evidence"]["played_line"]["pv_uci"])
            best_line = parse_line(board, row["engine_evidence"]["stored_best_line"]["pv_uci"])
            if len(played_line) < 2 or len(best_line) < 2:
                issues.append("reply_capture_comparison_unverified")
            else:
                played_target = played_line[1][0].piece_at(played_line[1][1].to_square)
                best_target = best_line[1][0].piece_at(best_line[1][1].to_square)
                if (
                    played_target is None
                    or best_target is None
                    or PIECE_VALUE[played_target.piece_type] <= PIECE_VALUE[best_target.piece_type]
                ):
                    issues.append("reply_capture_comparison_unverified")
        elif kind == "avoid_reply_attack":
            played_line = parse_line(board, row["engine_evidence"]["played_line"]["pv_uci"])
            if len(played_line) < 2:
                issues.append("reply_attack_unverified")
            else:
                reply_board, reply_move, _ = played_line[1]
                reply_after = reply_board.copy()
                reply_after.push(reply_move)
                target = chess.parse_square(claim["target"])
                if target not in reply_after.attacks(reply_move.to_square):
                    issues.append("reply_attack_unverified")
        elif kind == "king_recapture_keeps_pawn":
            best_piece = board.piece_at(best.from_square)
            played_piece = board.piece_at(played.from_square)
            if (
                not board.is_capture(best)
                or not board.is_capture(played)
                or best.to_square != played.to_square
                or best_piece is None
                or best_piece.piece_type != chess.KING
                or played_piece is None
                or played_piece.piece_type != chess.PAWN
            ):
                issues.append("king_recapture_unverified")
        elif kind == "lower_value_recapture":
            best_piece = board.piece_at(best.from_square)
            played_piece = board.piece_at(played.from_square)
            if (
                not board.is_capture(best)
                or not board.is_capture(played)
                or best.to_square != played.to_square
                or best_piece is None
                or played_piece is None
                or PIECE_VALUE[best_piece.piece_type] >= PIECE_VALUE[played_piece.piece_type]
            ):
                issues.append("lower_value_recapture_unverified")
        elif kind == "higher_value_capture":
            best_target = board.piece_at(best.to_square)
            played_target = board.piece_at(played.to_square)
            if (
                best_target is None
                or played_target is None
                or PIECE_VALUE[best_target.piece_type] <= PIECE_VALUE[played_target.piece_type]
            ):
                issues.append("higher_value_capture_unverified")
        elif kind == "best_line_followup":
            parsed = parse_line(board, row["engine_evidence"]["stored_best_line"]["pv_uci"])
            if (
                len(parsed) < 3
                or parsed[1][1].uci() != claim.get("reply_uci")
                or parsed[2][1].uci() != claim.get("follow_uci")
                or not parsed[2][0].is_capture(parsed[2][1])
            ):
                issues.append("best_line_followup_unverified")
        elif kind == "opposition_after_best" and (not has_opposition(after_best) or has_opposition(after_played)):
            issues.append("opposition_unverified")
        elif kind == "king_closer_to_pawn":
            pawn_square = chess.parse_square(claim["pawn"])
            played_king = chess.parse_square(claim["played_king"])
            if chess.square_distance(best.to_square, pawn_square) >= chess.square_distance(played_king, pawn_square):
                issues.append("king_route_unverified")
        elif kind == "endgame_pawn_advance":
            pawn = board.piece_at(best.from_square)
            if pawn is None or pawn.piece_type != chess.PAWN or board.is_capture(best):
                issues.append("endgame_pawn_advance_unverified")
        elif kind == "rook_mobility":
            if len(useful_rook_squares(after_best, best.to_square, mover)) < len(useful_rook_squares(board, best.from_square, mover)) + 2:
                issues.append("rook_mobility_unverified")
        elif kind == "king_centralizes" and centre_distance(best.to_square) >= centre_distance(best.from_square):
            issues.append("king_centralization_unverified")
        elif kind == "king_more_central_than_played" and centre_distance(best.to_square) >= centre_distance(played.to_square):
            issues.append("king_comparison_unverified")
        elif kind == "passed_pawn_after_best" and not is_passed_pawn(after_best, best.to_square, mover):
            issues.append("passed_pawn_unverified")
        elif kind == "rook_file" and file_state(after_best, chess.square_file(best.to_square), mover) != claim.get("state"):
            issues.append("rook_file_unverified")
        elif kind == "best_saves_loose_piece":
            if best.from_square not in undefended_attacked(board, mover) or after_best.is_attacked_by(opponent, best.to_square):
                issues.append("piece_safety_unverified")
        elif kind == "best_adds_defender":
            target = chess.parse_square(claim["target"])
            if best.to_square not in after_best.attackers(mover, target):
                issues.append("defender_unverified")
        elif kind == "best_attacks_target":
            target = chess.parse_square(claim["target"])
            if target not in after_best.attacks(best.to_square):
                issues.append("attack_unverified")
        elif kind == "best_centralizes" and centre_distance(best.to_square) >= centre_distance(best.from_square):
            issues.append("centralization_unverified")
    text = " ".join(str(reason.get(field) or "") for field in (
        "concept_label", "better_move_fact", "played_move_fact", "contrast", "transferable_lesson", "caption"
    ))
    lower = text.lower()
    for phrase in FORBIDDEN:
        if phrase in lower:
            issues.append(f"forbidden_phrase:{phrase}")
    if not SQUARE_RE.search(text):
        issues.append("no_named_square")
    if row["played_san"].replace("+", "").replace("#", "") not in reason["caption"].replace("+", "").replace("#", ""):
        issues.append("caption_missing_played_move")
    if row["best_san"].replace("+", "").replace("#", "") not in reason["caption"].replace("+", "").replace("#", ""):
        issues.append("caption_missing_best_move")
    word_count = len(re.findall(r"\b[\w'-]+\b", reason["caption"]))
    if not 32 <= word_count <= 96:
        issues.append(f"caption_word_count:{word_count}")
    return sorted(set(issues))


def choose_dispositions(rows: list[dict[str, Any]], already_count: int, not_mistake_count: int) -> dict[str, str]:
    by_id = {fingerprint(row): row for row in rows}
    scores = {key: exclusion_scores(row) for key, row in by_id.items()}
    already = sorted(
        by_id,
        key=lambda key: (
            scores[key]["already_decided"],
            scores[key]["decisiveness"],
            -scores[key]["outcome_drop"],
            key,
        ),
        reverse=True,
    )[:already_count]
    already_set = set(already)
    remaining = [key for key in by_id if key not in already_set]
    not_mistake = sorted(
        remaining,
        key=lambda key: (
            scores[key]["not_mistake"],
            -scores[key]["outcome_drop"],
            key,
        ),
        reverse=True,
    )[:not_mistake_count]
    result = {key: "eligible_positional" for key in by_id}
    result.update({key: "already_decided" for key in already})
    result.update({key: "not_mistake" for key in not_mistake})
    return result


def markdown_report(records: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    counts: dict[str, int] = {}
    categories: dict[str, int] = {}
    for record in records:
        counts[record["disposition"]] = counts.get(record["disposition"], 0) + 1
        if record["disposition"] == "eligible_positional":
            category = record["final"]["category"]
            categories[category] = categories.get(category, 0) + 1
    passed = sum(record["verification"]["status"] == "pass" for record in records)
    lines = [
        "# Positional caption candidates",
        "",
        f"Generated locally: {meta['generated_at']}",
        f"Engine evidence: `{meta['engine']}`, {meta['nodes_per_search']:,} nodes per search",
        "",
        "## Result",
        "",
        f"- Caption targets: **{counts.get('eligible_positional', 0)}**",
        f"- Already decided: **{counts.get('already_decided', 0)}**",
        f"- Not a mistake: **{counts.get('not_mistake', 0)}**",
        f"- Captions passing every local claim and voice check: **{passed}**",
        "",
        "The database contained one legacy submission and no saved identities for the stated 17/24 split. The two exclusion sets below are deterministic evidence-ranked reconstructions and remain reviewable candidates.",
        "",
        "## Teaching reason mix",
        "",
    ]
    for category, count in sorted(categories.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## Captions", ""])
    for record in records:
        if record["disposition"] != "eligible_positional":
            continue
        final = record["final"]
        lines.extend(
            [
                f"### {record['candidate_id']} · {record['played_san']} → {record['best_san']}",
                "",
                final["caption"],
                "",
                f"**Lesson:** {final['transferable_lesson']}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--csv-output", required=True)
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--already-decided", type=int, default=17)
    parser.add_argument("--not-mistake", type=int, default=24)
    args = parser.parse_args()

    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows = source["rows"]
    dispositions = choose_dispositions(rows, args.already_decided, args.not_mistake)
    now = datetime.now(timezone.utc).isoformat()
    records: list[dict[str, Any]] = []
    for row in rows:
        full_id = fingerprint(row)
        disposition = dispositions[full_id]
        reason = geometry_reason(row)
        issues = verify_claims(row, reason) if disposition == "eligible_positional" else []
        records.append(
            {
                "candidate_id": full_id[:16],
                "position_fingerprint": full_id,
                "fen": norm_fen(row["fen"]),
                "game_id": row.get("game_id"),
                "move_number": row.get("move_number"),
                "side_to_move": row.get("side_to_move"),
                "bucket": row.get("bucket"),
                "played_san": row.get("played_san"),
                "played_uci": row.get("played_uci"),
                "best_san": row.get("best_san"),
                "best_uci": row.get("best_uci"),
                "disposition": disposition,
                "exclusion_scores": exclusion_scores(row),
                "final": reason,
                "verification": {
                    "status": "pass" if disposition == "eligible_positional" and not issues else "fail" if disposition == "eligible_positional" else "not_applicable",
                    "deterministic_issues": issues,
                    "authority": "local_stockfish_geometry_candidate",
                    "engine": row["engine_evidence"]["engine"],
                    "nodes_per_search": row["engine_evidence"]["nodes_per_search"],
                    "verifier_version": "local_geometry.v1",
                },
                "engine_evidence": row["engine_evidence"],
                "board_evidence": row["board_evidence"],
                "caption_eligible": False,
                "tracker_eligible": False,
                "generated_at": now,
            }
        )

    meta = {
        "schema_version": "positional_caption_candidates.local.v1",
        "generated_at": now,
        "engine": rows[0]["engine_evidence"]["engine"] if rows else None,
        "nodes_per_search": rows[0]["engine_evidence"]["nodes_per_search"] if rows else None,
        "requested_exclusions": {"already_decided": args.already_decided, "not_mistake": args.not_mistake},
        "runtime_authority": False,
        "data_left_machine": False,
    }
    Path(args.output).write_text(json.dumps({"meta": meta, "records": records}, indent=2), encoding="utf-8")

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow([
        "candidate_id", "disposition", "verification_status", "category", "game_id", "move_number",
        "played_san", "best_san", "concept_label", "canonical_concept_id", "caption", "lesson", "issues",
    ])
    for record in records:
        final = record["final"]
        writer.writerow([
            record["candidate_id"], record["disposition"], record["verification"]["status"], final["category"],
            record.get("game_id"), record.get("move_number"), record["played_san"], record["best_san"],
            final["concept_label"], final["canonical_concept_id"], final["caption"], final["transferable_lesson"],
            ";".join(record["verification"]["deterministic_issues"]),
        ])
    Path(args.csv_output).write_text(buffer.getvalue(), encoding="utf-8")
    Path(args.report_output).write_text(markdown_report(records, meta), encoding="utf-8")

    summary = {
        "total": len(records),
        "targets": sum(record["disposition"] == "eligible_positional" for record in records),
        "already_decided": sum(record["disposition"] == "already_decided" for record in records),
        "not_mistake": sum(record["disposition"] == "not_mistake" for record in records),
        "passed": sum(record["verification"]["status"] == "pass" for record in records),
        "failed": sum(record["verification"]["status"] == "fail" for record in records),
    }
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
