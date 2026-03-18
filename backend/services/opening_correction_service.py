"""Opening/trap correction intake and live override helpers."""

from __future__ import annotations

import io
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import chess.pgn


def _sanitize_san_tokens(raw_text: str) -> List[str]:
    if not raw_text:
        return []

    text = raw_text.replace("\n", " ").replace(",", " ")
    tokens = []
    for token in text.split():
        cleaned = token.strip()
        if not cleaned:
            continue
        if re.fullmatch(r"\d+\.*", cleaned):
            continue
        if cleaned in {"1-0", "0-1", "1/2-1/2", "*"}:
            continue
        cleaned = re.sub(r"^\d+\.(\.\.)?", "", cleaned)
        if cleaned:
            tokens.append(cleaned)
    return tokens


def parse_moves_from_pgn(pgn_text: str) -> List[str]:
    if not pgn_text:
        return []

    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if not game:
        return []

    board = game.board()
    moves = []
    for move in game.mainline_moves():
        moves.append(board.san(move))
        board.push(move)
    return moves


def parse_corrected_moves(corrected_pgn: Optional[str], corrected_san_text: Optional[str]) -> List[str]:
    pgn_moves = parse_moves_from_pgn(corrected_pgn or "")
    if pgn_moves:
        return pgn_moves
    return _sanitize_san_tokens(corrected_san_text or "")


async def save_opening_correction(db, user_id: str, payload: Dict) -> Dict:
    corrected_moves = parse_corrected_moves(
        payload.get("corrected_pgn"),
        payload.get("corrected_san_text"),
    )

    correction_id = payload.get("correction_id") or f"opening_correction_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    correction_doc = {
        "correction_id": correction_id,
        "user_id": user_id,
        "source_context": payload.get("source_context", "manual"),
        "opening_key": payload.get("opening_key"),
        "opening_name": payload.get("opening_name"),
        "variation_name": payload.get("variation_name"),
        "trap_name": payload.get("trap_name"),
        "correction_type": payload.get("correction_type"),
        "current_moves": payload.get("current_moves", []),
        "current_fen": payload.get("current_fen"),
        "corrected_pgn": payload.get("corrected_pgn"),
        "corrected_san_text": payload.get("corrected_san_text"),
        "corrected_moves": corrected_moves,
        "corrected_name": payload.get("corrected_name"),
        "corrected_explanation": payload.get("corrected_explanation"),
        "notes": payload.get("notes"),
        "status": "applied",
        "applied_directly": True,
        "updated_at": now,
        "created_at": payload.get("created_at") or now,
    }

    match_filter = {
        "opening_key": correction_doc.get("opening_key"),
        "correction_type": correction_doc.get("correction_type"),
        "trap_name": correction_doc.get("trap_name"),
        "variation_name": correction_doc.get("variation_name"),
        "status": "applied",
    }

    await db.opening_corrections.update_one(match_filter, {"$set": correction_doc}, upsert=True)
    return correction_doc


async def get_opening_corrections(db, opening_key: str) -> List[Dict]:
    if not hasattr(db, "opening_corrections"):
        return []
    return await db.opening_corrections.find(
        {"opening_key": opening_key, "status": "applied"},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(50)


async def apply_opening_lesson_corrections(db, opening_key: str, lesson: Dict) -> Dict:
    corrections = await get_opening_corrections(db, opening_key)
    if not corrections or not lesson:
        return lesson

    opening = lesson.get("opening", {})
    traps = opening.get("traps", []) or []

    for correction in corrections:
        correction_type = correction.get("correction_type")
        corrected_moves = correction.get("corrected_moves") or []

        if correction_type == "opening_line_wrong" and corrected_moves:
            opening["main_line"] = [
                {"move": move, "explanation": correction.get("corrected_explanation") or "Corrected line"}
                for move in corrected_moves
            ]

        elif correction_type == "variation_name_wrong" and correction.get("corrected_name"):
            opening["name"] = correction["corrected_name"]

        elif correction_type == "plan_idea_text_wrong" and correction.get("corrected_explanation"):
            opening["description"] = correction["corrected_explanation"]

        elif correction_type == "trap_line_wrong" and correction.get("trap_name"):
            for trap in traps:
                if trap.get("name") == correction.get("trap_name"):
                    if corrected_moves:
                        trap["trap_line"] = [
                            {"move": move, "explanation": correction.get("corrected_explanation") or "Corrected trap line"}
                            for move in corrected_moves
                        ]
                    if correction.get("corrected_explanation"):
                        trap["description"] = correction["corrected_explanation"]
                    if correction.get("corrected_name"):
                        trap["name"] = correction["corrected_name"]
                    break

        elif correction_type == "trap_name_wrong" and correction.get("trap_name") and correction.get("corrected_name"):
            for trap in traps:
                if trap.get("name") == correction.get("trap_name"):
                    trap["name"] = correction["corrected_name"]
                    break

    lesson["opening"] = opening
    lesson["applied_corrections"] = corrections
    return lesson


async def get_trap_override(db, opening_key: str, trap_name: str) -> Optional[Dict]:
    if not opening_key or not trap_name:
        return None
    if not hasattr(db, "opening_corrections"):
        return None
    return await db.opening_corrections.find_one(
        {
            "opening_key": opening_key,
            "trap_name": trap_name,
            "correction_type": {"$in": ["trap_line_wrong", "trap_name_wrong", "plan_idea_text_wrong"]},
            "status": "applied",
        },
        {"_id": 0},
        sort=[("updated_at", -1)],
    )


async def select_corrected_trap_for_current_line(db, opening_key: str, current_moves: List[str]) -> Optional[Dict]:
    if not hasattr(db, "opening_corrections"):
        return None
    corrections = await db.opening_corrections.find(
        {
            "opening_key": opening_key,
            "correction_type": "trap_line_wrong",
            "status": "applied",
        },
        {"_id": 0},
    ).sort("updated_at", -1).to_list(20)

    normalized_current = [move.lower() for move in current_moves or []]
    if not normalized_current:
        return corrections[0] if corrections else None

    for correction in corrections:
        candidate_prefixes = [
            [move.lower() for move in correction.get("current_moves", [])],
            [move.lower() for move in correction.get("corrected_moves", [])],
        ]
        for candidate in candidate_prefixes:
            if candidate[: len(normalized_current)] == normalized_current:
                return correction
    return None


async def get_main_line_override(db, opening_key: str, variation_name: Optional[str] = None) -> Optional[Dict]:
    if not hasattr(db, "opening_corrections"):
        return None
    query = {
        "opening_key": opening_key,
        "correction_type": "opening_line_wrong",
        "status": "applied",
    }
    if variation_name:
        query["variation_name"] = variation_name

    return await db.opening_corrections.find_one(query, {"_id": 0}, sort=[("updated_at", -1)])