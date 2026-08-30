"""Offline truth gate for player-visible curriculum content.

This module does not own chess content. It reads the three canonical JSON
sources and answers one question for every record: is it safe to promise this
lesson to a player?

The first gate is deliberately deterministic and offline:

* structural completeness;
* valid FENs;
* legal SAN/UCI;
* playable opening trees and lesson lines;
* concrete trap outcomes demonstrated on the board;
* explicit canonical quarantine markers.

Exact tablebase and pinned-engine evidence is layered onto the same report by
the verification snapshot; runtime callers never make network requests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import chess


BACKEND_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_SOURCES = {
    "openings": BACKEND_ROOT / "data" / "opening_curriculum.json",
    "traps": BACKEND_ROOT / "data" / "traps.json",
    "endgames": BACKEND_ROOT / "data" / "coaching" / "endgame_theory_tree.json",
}
ENDGAME_TABLEBASE_SNAPSHOT = (
    BACKEND_ROOT
    / "data"
    / "corpus_snapshots"
    / "curriculum_endgame_tablebase_2026-08-29.json"
)

_NAG_SUFFIX = re.compile(r"[!?]+$")
_SLUG_BREAKS = re.compile(r"[^a-z0-9]+")
_UNEXPLAINED_COACHING_TERMS = {
    "fianchetto": "say which pawn moves and where the bishop goes",
    "tempo": "say that a player gains or spends a move",
    "initiative": "say who can make threats first",
    "counterplay": "say that the other side creates threats of its own",
    "prophylaxis": "say which opposing plan is being stopped",
    "zwischenzug": "say 'in-between move'",
    "hypermodern": "describe letting the opponent take the center, then attacking it",
    "iqp": "say 'isolated queen pawn'",
    "space advantage": "say that one side's pieces have more room",
    "theory cold": "say that the player needs to know the exact reply",
}


@dataclass(frozen=True)
class ContentIssue:
    subject: str
    content_id: str
    code: str
    message: str
    location: str = ""
    severity: str = "error"

    def as_dict(self) -> Dict[str, str]:
        return {
            "subject": self.subject,
            "content_id": self.content_id,
            "code": self.code,
            "message": self.message,
            "location": self.location,
            "severity": self.severity,
        }


@dataclass
class RecordValidation:
    subject: str
    content_id: str
    issues: List[ContentIssue] = field(default_factory=list)

    @property
    def publishable(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def error(
        self,
        code: str,
        message: str,
        location: str = "",
    ) -> None:
        self.issues.append(
            ContentIssue(
                subject=self.subject,
                content_id=self.content_id,
                code=code,
                message=message,
                location=location,
            )
        )

    def warning(
        self,
        code: str,
        message: str,
        location: str = "",
    ) -> None:
        self.issues.append(
            ContentIssue(
                subject=self.subject,
                content_id=self.content_id,
                code=code,
                message=message,
                location=location,
                severity="warning",
            )
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "content_id": self.content_id,
            "publishable": self.publishable,
            "issues": [issue.as_dict() for issue in self.issues],
        }


def trap_content_id(opening_key: str, trap_name: str) -> str:
    """Return the stable identity used by validation and runtime adapters."""
    slug = _SLUG_BREAKS.sub("-", str(trap_name or "").lower()).strip("-")
    return f"{opening_key}/{slug}"


def _iter_text(value: Any, location: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_location = f"{location}.{key}" if location else str(key)
            if key in {"leads_to", "trap_reference"}:
                continue
            yield from _iter_text(child, child_location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_text(child, f"{location}[{index}]")
    elif isinstance(value, str):
        yield location, value


def _validate_player_voice(
    payload: Mapping[str, Any],
    record: RecordValidation,
) -> None:
    """Block the small set of specialist terms we repeatedly exposed unexplained."""
    reported = set()
    for location, text in _iter_text(payload):
        lower = text.lower()
        for term, rewrite in _UNEXPLAINED_COACHING_TERMS.items():
            if term in reported:
                continue
            if re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", lower):
                record.error(
                    "voice.unexplained_term",
                    f"Replace or explain '{term}': {rewrite}.",
                    location,
                )
                reported.add(term)


def _load_json(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _clean_san(san: str) -> str:
    return _NAG_SUFFIX.sub("", str(san or "").strip())


def _apply_san(
    board: chess.Board,
    san: str,
    record: RecordValidation,
    location: str,
) -> bool:
    clean = _clean_san(san)
    if not clean:
        record.error("move.missing", "Move is empty.", location)
        return False
    try:
        move = board.parse_san(clean)
    except (ValueError, AssertionError) as exc:
        record.error(
            "move.illegal_or_ambiguous",
            f"{san!r} cannot be played from {board.fen()}: {exc}",
            location,
        )
        return False
    board.push(move)
    return True


def _validate_sequence(
    moves: Sequence[str],
    record: RecordValidation,
    location: str,
    board: Optional[chess.Board] = None,
) -> Optional[chess.Board]:
    current = board.copy(stack=False) if board is not None else chess.Board()
    for index, san in enumerate(moves):
        if not _apply_san(current, san, record, f"{location}[{index}]"):
            return None
    return current


def _board_from_fen_pattern(fen_pattern: str) -> chess.Board:
    """Accept the repository's legacy four-field FEN patterns."""
    fields = str(fen_pattern or "").split()
    if len(fields) == 4:
        fields.extend(["0", "1"])
    return chess.Board(" ".join(fields))


def _validate_critical_positions(
    critical_positions: Mapping[str, Any],
    record: RecordValidation,
    location: str,
) -> None:
    for position_key, position in critical_positions.items():
        if not isinstance(position, dict):
            record.error(
                "opening.critical_position_type",
                "Critical position must be an object.",
                f"{location}.{position_key}",
            )
            continue
        fen = position.get("fen") or position.get("fen_pattern")
        if not fen:
            # Some legacy entries are narrative-only and are not used as board
            # exercises. Their line legality is checked elsewhere.
            continue
        try:
            board = _board_from_fen_pattern(str(fen))
        except ValueError as exc:
            record.error(
                "opening.critical_fen_invalid",
                f"Critical FEN cannot be parsed: {exc}",
                f"{location}.{position_key}.fen_pattern",
            )
            continue
        if not board.is_valid():
            record.error(
                "opening.critical_fen_invalid",
                f"Critical FEN is not a legal chess position (status={board.status()}).",
                f"{location}.{position_key}.fen_pattern",
            )
            continue
        for move_group in (
            "best_moves",
            "best_moves_white",
            "best_moves_black",
            "mistake_moves",
        ):
            moves = position.get(move_group) or {}
            if not isinstance(moves, dict):
                record.error(
                    "opening.critical_moves_type",
                    f"{move_group} must be an object keyed by SAN move.",
                    f"{location}.{position_key}.{move_group}",
                )
                continue
            for san in moves:
                candidate = board.copy(stack=False)
                _apply_san(
                    candidate,
                    str(san),
                    record,
                    f"{location}.{position_key}.{move_group}[{san}]",
                )


def _is_curriculum_turn(board: chess.Board, color: str) -> bool:
    return board.turn == (chess.WHITE if color == "white" else chess.BLACK)


def _validate_tree_node(
    opening_key: str,
    node: Mapping[str, Any],
    board: chess.Board,
    curriculum_color: str,
    record: RecordValidation,
    location: str,
) -> None:
    current = board.copy(stack=False)

    # A node reached after the opponent's response may prescribe the
    # curriculum side's next move. Redundant "next" values on nodes where the
    # opponent is to move are ignored because the runtime ignores them too.
    if _is_curriculum_turn(current, curriculum_color):
        next_move = node.get("next")
        if next_move and not _apply_san(current, next_move, record, f"{location}.next"):
            return

    responses = node.get("responses") or {}
    if not isinstance(responses, dict):
        record.error(
            "opening.tree.responses_type",
            "responses must be an object keyed by SAN move.",
            f"{location}.responses",
        )
        return

    for response_san, child in responses.items():
        response_board = current.copy(stack=False)
        response_location = f"{location}.responses[{response_san}]"
        if not _apply_san(response_board, response_san, record, response_location):
            continue
        if not isinstance(child, dict):
            record.error(
                "opening.tree.node_type",
                "A response node must be an object.",
                response_location,
            )
            continue
        _validate_tree_node(
            opening_key,
            child,
            response_board,
            curriculum_color,
            record,
            response_location,
        )


def validate_opening_record(
    opening_key: str,
    opening: Mapping[str, Any],
) -> RecordValidation:
    record = RecordValidation("openings", opening_key)
    if opening.get("publication_status") == "quarantined":
        record.error(
            "content.quarantined",
            str(opening.get("quarantine_reason") or "Opening is under review."),
            "publication_status",
        )

    if not str(opening.get("name") or "").strip():
        record.error("opening.name_missing", "Opening name is required.", "name")

    color = str(opening.get("color") or "white").lower()
    if color not in {"white", "black"}:
        record.error(
            "opening.color_invalid",
            "Opening color must be white or black.",
            "color",
        )
        color = "white"

    tree = opening.get("tree") or {}
    main_line = opening.get("main_line") or []
    if not tree and not main_line:
        record.error(
            "opening.no_teaching_line",
            "Opening has recognition metadata but no playable lesson line.",
        )
    elif main_line and not tree and not opening.get("move_ideas"):
        record.error(
            "opening.move_teaching_missing",
            (
                "The legal line has no authored move-by-move teaching. Keep "
                "it for recognition, not the lesson catalog."
            ),
            "main_line",
        )

    if main_line:
        if not isinstance(main_line, list):
            record.error(
                "opening.main_line_type",
                "main_line must be a list of SAN moves.",
                "main_line",
            )
        else:
            _validate_sequence(main_line, record, "main_line")

    if tree:
        if not isinstance(tree, dict):
            record.error(
                "opening.tree_type",
                "tree must be an object keyed by the first SAN move.",
                "tree",
            )
        else:
            for first_san, first_node in tree.items():
                board = chess.Board()
                location = f"tree[{first_san}]"
                if not _apply_san(board, first_san, record, location):
                    continue
                if not isinstance(first_node, dict):
                    record.error(
                        "opening.tree.node_type",
                        "The first tree node must be an object.",
                        location,
                    )
                    continue
                _validate_tree_node(
                    opening_key,
                    first_node,
                    board,
                    color,
                    record,
                    location,
                )

    variations = opening.get("variations") or {}
    if variations and not isinstance(variations, dict):
        record.error(
            "opening.variations_type",
            "variations must be an object.",
            "variations",
        )
    elif isinstance(variations, dict):
        for variation_key, variation in variations.items():
            if not isinstance(variation, dict):
                record.error(
                    "opening.variation_type",
                    "Variation must be an object.",
                    f"variations.{variation_key}",
                )
                continue
            full_line = (
                list(main_line)
                + list(variation.get("moves_from_parent") or [])
                + list(variation.get("continuation") or [])
            )
            if full_line:
                _validate_sequence(
                    full_line,
                    record,
                    f"variations.{variation_key}.full_line",
                )
            _validate_critical_positions(
                variation.get("critical_positions") or {},
                record,
                f"variations.{variation_key}.critical_positions",
            )

    _validate_critical_positions(
        opening.get("critical_positions") or {},
        record,
        "critical_positions",
    )

    has_teaching_copy = any(
        (
            str(opening.get("summary") or "").strip(),
            str(opening.get("white_plan") or "").strip(),
            str(opening.get("black_plan") or "").strip(),
            bool(opening.get("move_ideas")),
            bool(opening.get("common_learnings")),
            bool(tree),
        )
    )
    if not has_teaching_copy:
        record.error(
            "opening.teaching_copy_missing",
            "A visible lesson needs authored explanation, plan, or move ideas.",
        )
    _validate_player_voice(opening, record)
    return record


_MATERIAL_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


def _material_balance(board: chess.Board, color: chess.Color) -> int:
    own = sum(
        value * len(board.pieces(piece_type, color))
        for piece_type, value in _MATERIAL_VALUES.items()
    )
    opponent = sum(
        value * len(board.pieces(piece_type, not color))
        for piece_type, value in _MATERIAL_VALUES.items()
    )
    return own - opponent


def validate_trap_record(
    opening_key: str,
    trap: Mapping[str, Any],
) -> RecordValidation:
    content_id = trap_content_id(opening_key, str(trap.get("name") or ""))
    record = RecordValidation("traps", content_id)
    if trap.get("publication_status") == "quarantined":
        record.error(
            "content.quarantined",
            str(trap.get("quarantine_reason") or "Trap is under review."),
            "publication_status",
        )

    for field_name in ("name", "description", "success_message", "result_type"):
        if not str(trap.get(field_name) or "").strip():
            record.error(
                f"trap.{field_name}_missing",
                f"{field_name} is required for a player-visible trap.",
                field_name,
            )

    trap_color_name = str(trap.get("trap_color") or "").lower()
    if trap_color_name not in {"white", "black"}:
        record.error(
            "trap.color_invalid",
            "trap_color must be white or black.",
            "trap_color",
        )

    setup_moves = trap.get("setup_moves") or []
    trap_line = trap.get("trap_line") or []
    if not isinstance(setup_moves, list) or not setup_moves:
        record.error(
            "trap.setup_missing",
            "setup_moves must contain a playable setup.",
            "setup_moves",
        )
        return record
    if not isinstance(trap_line, list) or not trap_line:
        record.error(
            "trap.line_missing",
            "trap_line must contain at least one move.",
            "trap_line",
        )
        return record

    line_moves: List[str] = []
    for index, step in enumerate(trap_line):
        if not isinstance(step, dict):
            record.error(
                "trap.step_type",
                "Each trap step must be an object.",
                f"trap_line[{index}]",
            )
            continue
        move = str(step.get("move") or "")
        line_moves.append(move)
        if not str(step.get("explanation") or "").strip():
            record.error(
                "trap.step_explanation_missing",
                "This move has no authored teaching explanation.",
                f"trap_line[{index}].explanation",
            )

    board = _validate_sequence(
        [str(move) for move in setup_moves] + line_moves,
        record,
        "full_line",
    )
    if board is None:
        return record

    result_type = str(trap.get("result_type") or "").lower()
    if result_type in {"mate", "checkmate"}:
        if not board.is_checkmate():
            record.error(
                "trap.outcome_not_demonstrated",
                "The authored line claims mate but does not end in checkmate.",
                "result_type",
            )
    elif result_type in {"wins_material", "wins_piece", "wins_queen"}:
        if trap_color_name in {"white", "black"}:
            winner = chess.WHITE if trap_color_name == "white" else chess.BLACK
            if _material_balance(board, winner) <= 0:
                record.error(
                    "trap.outcome_not_demonstrated",
                    "The authored line claims a material win but does not finish with a material advantage.",
                    "result_type",
                )
    elif result_type == "king_exposed":
        if trap_color_name in {"white", "black"}:
            attacker = chess.WHITE if trap_color_name == "white" else chess.BLACK
            victim = not attacker
            home_square = chess.E8 if victim == chess.BLACK else chess.E1
            victim_king = board.king(victim)
            if victim_king == home_square or board.has_castling_rights(victim):
                record.error(
                    "trap.outcome_not_demonstrated",
                    (
                        "The authored line claims an exposed king but does not "
                        "move that king away from home and remove castling rights."
                    ),
                    "result_type",
                )
    elif result_type in {"equal_with_activity", "positional_advantage"}:
        record.error(
            "trap.outcome_requires_engine",
            "A positional outcome needs pinned engine evidence before publication.",
            "result_type",
        )
    else:
        record.error(
            "trap.result_type_unsupported",
            f"Unsupported result_type {result_type!r}.",
            "result_type",
        )

    defense_line = trap.get("defense_line") or []
    defense_ready = all(
        (
            str(trap.get("danger") or "").strip(),
            str(trap.get("how_to_avoid") or "").strip(),
            isinstance(defense_line, list) and bool(defense_line),
        )
    )
    if not defense_ready:
        record.warning(
            "trap.defense_lesson_missing",
            "Keep this as recognition data until danger, defense, and safe line are authored.",
            "defense_line",
        )
    else:
        defense_moves = [
            str(step.get("move") if isinstance(step, dict) else step)
            for step in defense_line
        ]
        _validate_sequence(
            [str(move) for move in (trap.get("defense_setup_moves") or setup_moves)]
            + defense_moves,
            record,
            "defense_full_line",
        )
    _validate_player_voice(trap, record)
    return record


def validate_endgame_lesson(
    category_key: str,
    lesson_key: str,
    lesson: Mapping[str, Any],
    tablebase_evidence: Optional[Mapping[tuple[str, int], Mapping[str, Any]]] = None,
) -> RecordValidation:
    content_id = f"{category_key}/{lesson_key}"
    record = RecordValidation("endgames", content_id)
    if lesson.get("publication_status") == "quarantined":
        record.error(
            "content.quarantined",
            str(lesson.get("quarantine_reason") or "Endgame lesson is under review."),
            "publication_status",
        )

    for field_name in ("name", "rule", "description"):
        if not str(lesson.get(field_name) or "").strip():
            record.error(
                f"endgame.{field_name}_missing",
                f"{field_name} is required for a player-visible lesson.",
                field_name,
            )

    positions = lesson.get("positions") or []
    if not isinstance(positions, list) or not positions:
        record.error(
            "endgame.positions_missing",
            "A lesson needs at least one position.",
            "positions",
        )
        return record

    evidence_index = tablebase_evidence or {}
    for index, position in enumerate(positions):
        location = f"positions[{index}]"
        if not isinstance(position, dict):
            record.error(
                "endgame.position_type",
                "Each position must be an object.",
                location,
            )
            continue
        fen = str(position.get("fen") or "")
        try:
            board = chess.Board(fen)
        except ValueError as exc:
            record.error(
                "endgame.fen_invalid",
                f"FEN cannot be parsed: {exc}",
                f"{location}.fen",
            )
            continue
        if not board.is_valid():
            record.error(
                "endgame.fen_invalid",
                f"FEN is not a legal chess position (status={board.status()}).",
                f"{location}.fen",
            )
            continue

        expected_side = "white" if board.turn == chess.WHITE else "black"
        if position.get("side_to_move") != expected_side:
            record.error(
                "endgame.side_to_move_mismatch",
                f"FEN says {expected_side} to move.",
                f"{location}.side_to_move",
            )

        uci = str(position.get("correct_move_uci") or "").lower()
        san = _clean_san(str(position.get("correct_move_san") or ""))
        try:
            uci_move = chess.Move.from_uci(uci)
        except ValueError:
            record.error(
                "endgame.uci_invalid",
                f"{uci!r} is not valid UCI.",
                f"{location}.correct_move_uci",
            )
            continue
        if uci_move not in board.legal_moves:
            record.error(
                "endgame.move_illegal",
                f"{uci!r} is not legal from the stored FEN.",
                f"{location}.correct_move_uci",
            )
            continue

        canonical_san = board.san(uci_move)
        try:
            san_move = board.parse_san(san)
        except (ValueError, AssertionError):
            record.error(
                "endgame.san_invalid",
                f"{san!r} is not legal from the stored FEN.",
                f"{location}.correct_move_san",
            )
        else:
            if san_move != uci_move:
                record.error(
                    "endgame.san_uci_mismatch",
                    f"SAN {san!r} and UCI {uci!r} describe different moves.",
                    location,
                )
            if san != canonical_san:
                record.error(
                    "endgame.san_not_canonical",
                    f"Stored SAN is {san!r}; the position requires {canonical_san!r}.",
                    f"{location}.correct_move_san",
                )

        if len(board.piece_map()) <= 7:
            evidence = evidence_index.get((content_id, index))
            if evidence is None:
                record.error(
                    "endgame.tablebase_evidence_missing",
                    "This tablebase-eligible position has no committed Syzygy evidence.",
                    location,
                )
            elif (
                evidence.get("fen") != board.fen()
                or evidence.get("stored_move_uci") != uci
            ):
                record.error(
                    "endgame.tablebase_evidence_stale",
                    "Committed Syzygy evidence does not match this position and answer.",
                    location,
                )
            elif not evidence.get("preserves_wdl"):
                record.error(
                    "endgame.tablebase_regression",
                    (
                        "The stored answer throws away the exact tablebase "
                        f"result ({evidence.get('root_category')} -> "
                        f"{evidence.get('move_category_from_opponent_turn')} "
                        "from the opponent's turn)."
                    ),
                    f"{location}.correct_move_uci",
                )
        else:
            verification = position.get("verification") or {}
            if not (
                verification.get("method") == "stockfish"
                and verification.get("status") == "verified"
                and verification.get("fen") == board.fen()
                and verification.get("move_uci") == uci
            ):
                record.error(
                    "endgame.engine_evidence_missing",
                    "This position is outside Syzygy coverage and has no pinned engine verification.",
                    location,
                )

        for field_name in ("prompt", "idea", "on_correct", "on_wrong"):
            if not str(position.get(field_name) or "").strip():
                record.error(
                    f"endgame.{field_name}_missing",
                    f"{field_name} is required.",
                    f"{location}.{field_name}",
                )
    _validate_player_voice(lesson, record)
    return record


def validate_personalized_lesson_descriptor(
    descriptor: Mapping[str, Any],
) -> RecordValidation:
    """Validate the derived contract consumed by the shared lesson workspace.

    This does not create another curriculum source. It verifies that a derived
    view of canonical content remains safe, playable, answer-private, and
    honest about the level of learning it can prove.
    """
    kind = str(descriptor.get("kind") or "").strip().lower()
    content_id = str(descriptor.get("id") or "").strip()
    record = RecordValidation(
        subject="personalized_lessons",
        content_id=f"{kind}:{content_id}" if kind or content_id else "unknown",
    )

    for field_name in (
        "kind",
        "id",
        "skill_id",
        "title",
        "rule",
        "canonical_source",
        "content_version",
    ):
        if not str(descriptor.get(field_name) or "").strip():
            record.error(
                "personalized.field_missing",
                f"{field_name} is required.",
                field_name,
            )

    if kind not in {"opening", "trap", "endgame", "concept"}:
        record.error(
            "personalized.kind_invalid",
            "kind must be opening, trap, endgame, or concept.",
            "kind",
        )

    capability = str(descriptor.get("mastery_capability") or "")
    if capability not in {"guided", "independent"}:
        record.error(
            "personalized.mastery_capability_invalid",
            "mastery_capability must be guided or independent.",
            "mastery_capability",
        )

    items = descriptor.get("items")
    if not isinstance(items, list) or not items:
        record.error(
            "personalized.items_missing",
            "At least one playable lesson item is required.",
            "items",
        )
        return record

    seen_item_ids: set[str] = set()
    seen_positions: set[str] = set()
    stages: list[str] = []
    transfer_positions: set[str] = set()
    earlier_positions: set[str] = set()

    for index, item in enumerate(items):
        location = f"items[{index}]"
        if not isinstance(item, Mapping):
            record.error(
                "personalized.item_type",
                "Lesson item must be an object.",
                location,
            )
            continue

        item_id = str(item.get("item_id") or "").strip()
        if not item_id:
            record.error(
                "personalized.item_id_missing",
                "item_id is required.",
                f"{location}.item_id",
            )
        elif item_id in seen_item_ids:
            record.error(
                "personalized.item_id_duplicate",
                "item_id must be unique within the lesson.",
                f"{location}.item_id",
            )
        seen_item_ids.add(item_id)

        fen = str(item.get("fen") or "").strip()
        normalized_fen = ""
        if not fen:
            record.error(
                "personalized.fen_missing",
                "A board position is required.",
                f"{location}.fen",
            )
        else:
            try:
                board = chess.Board(fen)
                normalized_fen = " ".join(board.fen().split()[:4])
                if not board.is_valid():
                    record.error(
                        "personalized.fen_invalid",
                        f"Position is not legal (status={board.status()}).",
                        f"{location}.fen",
                    )
            except ValueError as exc:
                record.error(
                    "personalized.fen_invalid",
                    f"Position cannot be parsed: {exc}",
                    f"{location}.fen",
                )
        if normalized_fen:
            if normalized_fen in seen_positions:
                record.error(
                    "personalized.position_duplicate",
                    "Each proof item must use a different board position.",
                    f"{location}.fen",
                )
            seen_positions.add(normalized_fen)

        for field_name in ("prompt", "reason_prompt", "source", "source_ref"):
            if not str(item.get(field_name) or "").strip():
                record.error(
                    "personalized.item_field_missing",
                    f"{field_name} is required.",
                    f"{location}.{field_name}",
                )
        if item.get("board_verified") is not True:
            record.error(
                "personalized.board_unverified",
                "Only board-verified lesson items may be published.",
                f"{location}.board_verified",
            )

        reason_choices = item.get("reason_choices")
        choice_ids = {
            str(choice.get("id") or "").strip()
            for choice in reason_choices or []
            if isinstance(choice, Mapping)
            and str(choice.get("label") or "").strip()
        }
        expected_reason = str(item.get("_expected_reason") or "").strip()
        if len(choice_ids) < 2:
            record.error(
                "personalized.reason_choices_missing",
                "At least two explained reason choices are required.",
                f"{location}.reason_choices",
            )
        if not expected_reason or expected_reason not in choice_ids:
            record.error(
                "personalized.expected_reason_missing",
                "The private expected reason must match a visible choice.",
                f"{location}._expected_reason",
            )

        has_private_answer = bool(
            item.get("_expected_uci")
            or item.get("_endgame_position_index") is not None
            or item.get("_puzzle_evaluator") is True
        )
        if not has_private_answer:
            record.error(
                "personalized.private_answer_missing",
                "A server-owned grading path is required.",
                location,
            )

        stage = str(item.get("stage") or "").strip()
        if stage not in {"guide", "recall", "transfer"}:
            record.error(
                "personalized.stage_invalid",
                "stage must be guide, recall, or transfer.",
                f"{location}.stage",
            )
        stages.append(stage)
        if normalized_fen:
            if stage == "transfer":
                transfer_positions.add(normalized_fen)
            else:
                earlier_positions.add(normalized_fen)

    if capability == "independent":
        if "transfer" not in stages or not ({"guide", "recall"} & set(stages)):
            record.error(
                "personalized.independent_proof_missing",
                "Independent learning needs guided or recalled work plus transfer.",
                "items",
            )
        if transfer_positions & earlier_positions:
            record.error(
                "personalized.transfer_reuses_position",
                "Transfer must use a position not already taught.",
                "items",
            )
    elif "transfer" in stages:
        record.error(
            "personalized.guided_claims_transfer",
            "A guided-only lesson cannot label an item as transfer.",
            "items",
        )

    _validate_player_voice(descriptor, record)
    return record


def _subject_summary(records: Iterable[RecordValidation]) -> Dict[str, Any]:
    records = list(records)
    return {
        "total": len(records),
        "publishable": sum(record.publishable for record in records),
        "quarantined": sum(not record.publishable for record in records),
        "records": {
            record.content_id: record.as_dict()
            for record in records
        },
    }


@lru_cache(maxsize=1)
def validate_all_content() -> Dict[str, Any]:
    openings_data = _load_json(CANONICAL_SOURCES["openings"])
    traps_data = _load_json(CANONICAL_SOURCES["traps"])
    endgames_data = _load_json(CANONICAL_SOURCES["endgames"])
    tablebase_snapshot = _load_json(ENDGAME_TABLEBASE_SNAPSHOT)
    tablebase_evidence = {
        (entry["content_id"], int(entry["position_index"])): entry
        for entry in tablebase_snapshot.get("entries", [])
        if isinstance(entry, dict)
    }

    opening_records = [
        validate_opening_record(key, value)
        for key, value in openings_data.items()
        if not key.startswith("_") and isinstance(value, dict)
    ]

    trap_records: List[RecordValidation] = []
    for opening_key, traps in traps_data.items():
        if opening_key.startswith("_") or not isinstance(traps, list):
            continue
        trap_records.extend(
            validate_trap_record(opening_key, trap)
            for trap in traps
            if isinstance(trap, dict)
        )

    endgame_records: List[RecordValidation] = []
    for category_key, category in endgames_data.items():
        if category_key.startswith("_") or not isinstance(category, dict):
            continue
        for lesson_key, lesson in (category.get("lessons") or {}).items():
            if isinstance(lesson, dict):
                endgame_records.append(
                    validate_endgame_lesson(
                        category_key,
                        lesson_key,
                        lesson,
                        tablebase_evidence,
                    )
                )

    subjects = {
        "openings": _subject_summary(opening_records),
        "traps": _subject_summary(trap_records),
        "endgames": _subject_summary(endgame_records),
    }
    all_issues = [
        issue.as_dict()
        for record in opening_records + trap_records + endgame_records
        for issue in record.issues
    ]
    return {
        "canonical_sources": {
            key: str(path.relative_to(BACKEND_ROOT.parent)).replace("\\", "/")
            for key, path in CANONICAL_SOURCES.items()
        }
        | {
            "endgame_tablebase_evidence": str(
                ENDGAME_TABLEBASE_SNAPSHOT.relative_to(BACKEND_ROOT.parent)
            ).replace("\\", "/")
        },
        "subjects": subjects,
        "issue_count": len(all_issues),
        "issues": all_issues,
    }


def reset_validation_cache() -> None:
    validate_all_content.cache_clear()


def is_content_publishable(subject: str, content_id: str) -> bool:
    subject_report = validate_all_content()["subjects"].get(subject, {})
    record = subject_report.get("records", {}).get(content_id)
    return bool(record and record.get("publishable"))


def get_publishable_content_ids(subject: str) -> set[str]:
    subject_report = validate_all_content()["subjects"].get(subject, {})
    return {
        content_id
        for content_id, record in subject_report.get("records", {}).items()
        if record.get("publishable")
    }


def get_defense_ready_trap_ids() -> set[str]:
    """Trap records safe for a defense-first player lesson catalog."""
    records = validate_all_content()["subjects"]["traps"]["records"]
    return {
        content_id
        for content_id, record in records.items()
        if record["publishable"]
        and not any(
            issue["code"] == "trap.defense_lesson_missing"
            for issue in record["issues"]
        )
    }
