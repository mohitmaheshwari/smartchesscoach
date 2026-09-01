"""Fail-closed exact endgame truth from a pinned local Fathom/Syzygy bundle.

This service owns the production contract.  It does not name an endgame
technique and it never falls back to an engine estimate.  A probe is usable
only when Fathom partitions every legal move exactly once and the configured
binary/bundle provenance is present.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import chess


EXACT_ENDGAME_SCHEMA_VERSION = "exact_endgame.fathom.v1"
EXACT_ENDGAME_ENGINE_FLAG = "EXACT_ENDGAME_ENGINE_ENABLED"
EXACT_ENDGAME_REVIEW_FLAG = "EXACT_ENDGAME_REVIEW_ENABLED"
FATHOM_BINARY_ENV = "FATHOM_BINARY_PATH"
FATHOM_BINARY_SHA_ENV = "FATHOM_BINARY_SHA256"
SYZYGY_PATH_ENV = "SYZYGY_TABLEBASE_PATH"
SYZYGY_BUNDLE_ENV = "SYZYGY_TABLEBASE_BUNDLE_ID"
SYZYGY_MANIFEST_SHA_ENV = "SYZYGY_TABLEBASE_MANIFEST_SHA256"
SYZYGY_MAX_MEN_ENV = "SYZYGY_MAX_MEN"
_TRUE = frozenset({"1", "true", "yes", "on"})
_HEADER_RE = re.compile(r'^\[([A-Za-z]+) "(.*)"\]$')
_ALLOWED_WDL = frozenset({"Win", "Draw", "Loss", "CursedWin", "BlessedLoss"})
_VISIBLE_WDL = frozenset({"Win", "Draw", "Loss"})


class ExactEndgameError(ValueError):
    """Raised when exact evidence is absent, stale or internally incomplete."""


def exact_endgame_review_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get(EXACT_ENDGAME_REVIEW_FLAG, "false")).strip().lower() in _TRUE


def exact_endgame_engine_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    """Enable the shared probe without making review captions visible.

    The review flag also implies engine access for backwards-compatible rollout,
    while lesson/puzzle consumers can enable only the truth service.
    """
    source = os.environ if env is None else env
    return (
        str(source.get(EXACT_ENDGAME_ENGINE_FLAG, "false")).strip().lower() in _TRUE
        or exact_endgame_review_enabled(source)
    )


def _position_key(fen: str) -> str:
    board = chess.Board(fen)
    return " ".join(board.fen().split()[:4])


def _fingerprint(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path_text: str) -> str:
    digest = hashlib.sha256()
    with Path(path_text).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=4)
def compute_syzygy_manifest_sha256(table_dir_text: str) -> str:
    """Hash the filename->content-hash map for every configured Syzygy file."""
    table_dir = Path(table_dir_text).resolve(strict=True)
    files = sorted(
        path for path in table_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".rtbw", ".rtbz"}
    )
    if not files:
        raise ExactEndgameError("tablebase directory contains no Syzygy files")
    manifest = {path.name: _sha256_file(str(path)) for path in files}
    return _fingerprint(manifest)


def _parse_headers(stdout: str) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for raw_line in stdout.splitlines():
        match = _HEADER_RE.fullmatch(raw_line.strip())
        if match:
            headers[match.group(1)] = match.group(2)
    return headers


def _parse_bucket(board: chess.Board, raw: str) -> Tuple[str, ...]:
    if not raw.strip():
        return ()
    parsed = []
    for san in raw.split(","):
        try:
            parsed.append(board.parse_san(san.strip()).uci())
        except ValueError as exc:
            raise ExactEndgameError(f"Fathom returned invalid SAN {san!r}") from exc
    return tuple(parsed)


@dataclass(frozen=True)
class ExactEndgameEvidence:
    fen: str
    wdl: str
    dtz: int
    winning_moves_uci: Tuple[str, ...]
    drawing_moves_uci: Tuple[str, ...]
    losing_moves_uci: Tuple[str, ...]
    binary_sha256: str
    tablebase_bundle_id: str
    tablebase_manifest_sha256: str
    provider: str = "fathom_syzygy"
    provider_version: str = EXACT_ENDGAME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        board = chess.Board(self.fen)
        if board.is_game_over():
            raise ExactEndgameError("exact endgame position has no legal move")
        if self.wdl not in _ALLOWED_WDL:
            raise ExactEndgameError("unsupported exact WDL")
        if not re.fullmatch(r"[0-9a-f]{64}", self.binary_sha256):
            raise ExactEndgameError("Fathom binary SHA-256 is required")
        if not self.tablebase_bundle_id.strip():
            raise ExactEndgameError("tablebase bundle identity is required")
        if not re.fullmatch(r"[0-9a-f]{64}", self.tablebase_manifest_sha256):
            raise ExactEndgameError("tablebase manifest SHA-256 is required")
        partition = self.move_partition
        if len(partition) != len(set(partition)):
            raise ExactEndgameError("exact move buckets overlap")
        legal = {move.uci() for move in board.legal_moves}
        if set(partition) != legal:
            raise ExactEndgameError("exact move buckets do not partition legal moves")

    @property
    def move_partition(self) -> Tuple[str, ...]:
        return self.winning_moves_uci + self.drawing_moves_uci + self.losing_moves_uci

    @property
    def root_outcome(self) -> Optional[str]:
        return {"Win": "win", "Draw": "draw", "Loss": "loss"}.get(self.wdl)

    @property
    def result_preserving_moves_uci(self) -> Tuple[str, ...]:
        if self.wdl == "Win":
            return self.winning_moves_uci
        if self.wdl == "Draw":
            return self.drawing_moves_uci
        if self.wdl == "Loss":
            return self.losing_moves_uci
        return ()

    def outcome_for(self, move_uci: str) -> Optional[str]:
        if move_uci in self.winning_moves_uci:
            return "win"
        if move_uci in self.drawing_moves_uci:
            return "draw"
        if move_uci in self.losing_moves_uci:
            return "loss"
        return None

    @property
    def input_fingerprint(self) -> str:
        return _fingerprint({
            "fen": _position_key(self.fen),
            "provider": self.provider,
            "provider_version": self.provider_version,
            "binary_sha256": self.binary_sha256,
            "tablebase_bundle_id": self.tablebase_bundle_id,
            "tablebase_manifest_sha256": self.tablebase_manifest_sha256,
        })

    def contract_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.provider_version,
            "provider": self.provider,
            "fen": _position_key(self.fen),
            "wdl": self.wdl,
            "dtz": self.dtz,
            "root_outcome": self.root_outcome,
            "winning_moves_uci": list(self.winning_moves_uci),
            "drawing_moves_uci": list(self.drawing_moves_uci),
            "losing_moves_uci": list(self.losing_moves_uci),
            "result_preserving_moves_uci": list(self.result_preserving_moves_uci),
            "binary_sha256": self.binary_sha256,
            "tablebase_bundle_id": self.tablebase_bundle_id,
            "tablebase_manifest_sha256": self.tablebase_manifest_sha256,
            "input_fingerprint": self.input_fingerprint,
            "complete_legal_partition": True,
            "visible_outcome_supported": self.wdl in _VISIBLE_WDL,
        }

    @classmethod
    def from_contract(cls, raw: Mapping[str, Any]) -> "ExactEndgameEvidence":
        if raw.get("schema_version") != EXACT_ENDGAME_SCHEMA_VERSION:
            raise ExactEndgameError("unsupported exact endgame schema")
        evidence = cls(
            fen=str(raw.get("fen") or ""),
            wdl=str(raw.get("wdl") or ""),
            dtz=int(raw.get("dtz")),
            winning_moves_uci=tuple(raw.get("winning_moves_uci") or ()),
            drawing_moves_uci=tuple(raw.get("drawing_moves_uci") or ()),
            losing_moves_uci=tuple(raw.get("losing_moves_uci") or ()),
            binary_sha256=str(raw.get("binary_sha256") or ""),
            tablebase_bundle_id=str(raw.get("tablebase_bundle_id") or ""),
            tablebase_manifest_sha256=str(
                raw.get("tablebase_manifest_sha256") or ""
            ),
        )
        if raw.get("input_fingerprint") != evidence.input_fingerprint:
            raise ExactEndgameError("exact endgame fingerprint mismatch")
        return evidence


@dataclass(frozen=True)
class ExactEndgameCause:
    """One exact WDL change; deliberately names no unproved technique."""

    played_move_san: str
    played_move_uci: str
    best_move_san: str
    best_move_uci: str
    outcome_before: str
    outcome_after: str
    preserving_moves_uci: Tuple[str, ...]
    evidence_fingerprint: str
    proof_authority: str = "exact_endgame_service.fathom_syzygy"
    proof_version: str = EXACT_ENDGAME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.outcome_before not in {"win", "draw"}:
            raise ExactEndgameError("only a lost win or draw is teachable")
        if self.outcome_after not in {"draw", "loss"}:
            raise ExactEndgameError("exact cause requires a worse result")
        if self.outcome_before == self.outcome_after:
            raise ExactEndgameError("exact cause requires a result change")
        if not self.played_move_san or not self.best_move_san:
            raise ExactEndgameError("exact cause moves are required")
        if self.best_move_uci not in self.preserving_moves_uci:
            raise ExactEndgameError("best move must preserve the exact result")
        if self.played_move_uci in self.preserving_moves_uci:
            raise ExactEndgameError("played move cannot preserve the exact result")
        if not re.fullmatch(r"[0-9a-f]{64}", self.evidence_fingerprint):
            raise ExactEndgameError("exact evidence fingerprint is invalid")

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.contract_dict(include_fingerprint=False))

    def contract_dict(self, *, include_fingerprint: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "schema_version": self.proof_version,
            "kind": "exact_endgame_result_change",
            "played_move_san": self.played_move_san,
            "played_move_uci": self.played_move_uci,
            "best_move_san": self.best_move_san,
            "best_move_uci": self.best_move_uci,
            "outcome_before": self.outcome_before,
            "outcome_after": self.outcome_after,
            "result_preserving_moves_uci": list(self.preserving_moves_uci),
            "evidence_fingerprint": self.evidence_fingerprint,
            "proof": {"authority": self.proof_authority, "version": self.proof_version},
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


def parse_fathom_output(
    fen: str,
    stdout: str,
    *,
    binary_sha256: str,
    tablebase_bundle_id: str,
    tablebase_manifest_sha256: str,
) -> ExactEndgameEvidence:
    board = chess.Board(fen)
    if board.is_game_over():
        raise ExactEndgameError("probe FEN has no legal move")
    headers = _parse_headers(stdout)
    required = {"FEN", "WDL", "DTZ", "WinningMoves", "DrawingMoves", "LosingMoves"}
    missing = sorted(required.difference(headers))
    if missing:
        raise ExactEndgameError(f"Fathom output is missing headers: {', '.join(missing)}")
    if _position_key(headers["FEN"]) != _position_key(fen):
        raise ExactEndgameError("Fathom output belongs to a different FEN")
    try:
        dtz = int(headers["DTZ"])
    except ValueError as exc:
        raise ExactEndgameError("Fathom DTZ is not an integer") from exc
    return ExactEndgameEvidence(
        fen=_position_key(fen),
        wdl=headers["WDL"],
        dtz=dtz,
        winning_moves_uci=_parse_bucket(board, headers["WinningMoves"]),
        drawing_moves_uci=_parse_bucket(board, headers["DrawingMoves"]),
        losing_moves_uci=_parse_bucket(board, headers["LosingMoves"]),
        binary_sha256=binary_sha256,
        tablebase_bundle_id=tablebase_bundle_id,
        tablebase_manifest_sha256=tablebase_manifest_sha256,
    )


def probe_configured_fathom(
    fen: str,
    env: Optional[Mapping[str, str]] = None,
) -> Tuple[Optional[ExactEndgameEvidence], str]:
    """Return exact evidence or one stable abstention reason; never raise."""
    source = os.environ if env is None else env
    if not exact_endgame_engine_enabled(source):
        return None, "disabled"
    try:
        board = chess.Board(fen)
    except ValueError:
        return None, "invalid_fen"
    try:
        maximum_men = int(source.get(SYZYGY_MAX_MEN_ENV, "0") or 0)
    except ValueError:
        return None, "invalid_maximum_men"
    if maximum_men < 3:
        return None, "coverage_not_configured"
    if chess.popcount(board.occupied) > maximum_men:
        return None, "outside_tablebase_coverage"
    if board.castling_rights:
        return None, "unsupported_castling_rights"
    binary_text = str(source.get(FATHOM_BINARY_ENV, "") or "").strip()
    table_text = str(source.get(SYZYGY_PATH_ENV, "") or "").strip()
    expected_sha = str(source.get(FATHOM_BINARY_SHA_ENV, "") or "").strip().lower()
    bundle_id = str(source.get(SYZYGY_BUNDLE_ENV, "") or "").strip()
    expected_manifest_sha = str(
        source.get(SYZYGY_MANIFEST_SHA_ENV, "") or ""
    ).strip().lower()
    if (
        not binary_text
        or not table_text
        or not expected_sha
        or not bundle_id
        or not expected_manifest_sha
    ):
        return None, "missing_configuration_or_provenance"
    try:
        binary = Path(binary_text).resolve(strict=True)
        table_dir = Path(table_text).resolve(strict=True)
        if not binary.is_file() or not table_dir.is_dir():
            return None, "invalid_configured_path"
        actual_sha = _sha256_file(str(binary))
        if actual_sha != expected_sha:
            return None, "binary_sha256_mismatch"
        actual_manifest_sha = compute_syzygy_manifest_sha256(str(table_dir))
        if actual_manifest_sha != expected_manifest_sha:
            return None, "tablebase_manifest_sha256_mismatch"
        completed = subprocess.run(
            [str(binary), f"--path={table_dir}", _position_key(fen)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            return None, "probe_failed"
        evidence = parse_fathom_output(
            _position_key(fen),
            completed.stdout,
            binary_sha256=actual_sha,
            tablebase_bundle_id=bundle_id,
            tablebase_manifest_sha256=actual_manifest_sha,
        )
        return evidence, "exact"
    except (OSError, subprocess.SubprocessError, ExactEndgameError, ValueError):
        return None, "invalid_or_incomplete_evidence"


def build_exact_endgame_cause(
    evidence: ExactEndgameEvidence,
    *,
    played_san: str,
    preferred_best_san: Optional[str] = None,
) -> Optional[ExactEndgameCause]:
    """Build a cause only when a legal move worsens an exact win or draw."""
    if evidence.root_outcome not in {"win", "draw"}:
        return None
    board = chess.Board(evidence.fen)
    try:
        played = board.parse_san(played_san)
    except ValueError:
        return None
    after = evidence.outcome_for(played.uci())
    before = evidence.root_outcome
    order = {"loss": 0, "draw": 1, "win": 2}
    if after is None or order[after] >= order[before]:
        return None
    preserving = evidence.result_preserving_moves_uci
    if not preserving:
        return None
    best = None
    if preferred_best_san:
        try:
            candidate = board.parse_san(preferred_best_san)
            if candidate.uci() in preserving:
                best = candidate
        except ValueError:
            pass
    if best is None:
        best = chess.Move.from_uci(preserving[0])
    return ExactEndgameCause(
        played_move_san=board.san(played),
        played_move_uci=played.uci(),
        best_move_san=board.san(best),
        best_move_uci=best.uci(),
        outcome_before=before,
        outcome_after=after,
        preserving_moves_uci=preserving,
        evidence_fingerprint=evidence.input_fingerprint,
    )


def render_exact_endgame_cause(cause: ExactEndgameCause) -> Tuple[str, str, str]:
    """Return (headline, caption, transferable instruction) from exact fields."""
    before_label = "won" if cause.outcome_before == "win" else "a draw"
    if cause.outcome_before == "win" and cause.outcome_after == "draw":
        change = "let the win slip into a draw"
        headline = "You let the win slip"
    elif cause.outcome_before == "win" and cause.outcome_after == "loss":
        change = "changed a win into a loss"
        headline = "This move changed the result"
    else:
        change = "changed the draw into a loss"
        headline = "You let the draw slip"
    caption = (
        f"This endgame was still {before_label} before {cause.played_move_san}. "
        f"{cause.played_move_san} {change}. "
        f"{cause.best_move_san} preserved the {cause.outcome_before}."
    )
    instruction = (
        "When only a few pieces are left, check whether your move keeps the win or draw "
        "before choosing the quickest-looking route."
    )
    return headline, caption, instruction
