"""Strict research adapter for the official Fathom Syzygy probe tool.

Fathom is an exact chess-truth source for supported tablebase positions.  This
module only parses and validates its evidence; it does not turn tablebase truth
into a player-facing concept or explanation.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Tuple

import chess


class FathomAdapterError(ValueError):
    """Fathom output or provenance was incomplete or internally inconsistent."""


_HEADER_RE = re.compile(r'^\[([A-Za-z]+) "(.*)"\]$')
_ALLOWED_WDL = {"Win", "Draw", "Loss", "CursedWin", "BlessedLoss"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_headers(stdout: str) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for raw_line in stdout.splitlines():
        match = _HEADER_RE.fullmatch(raw_line.strip())
        if match:
            headers[match.group(1)] = match.group(2)
    return headers


def _parse_move_bucket(board: chess.Board, value: str) -> Tuple[str, ...]:
    if not value.strip():
        return ()
    moves = []
    for san in value.split(","):
        try:
            move = board.parse_san(san.strip())
        except ValueError as exc:
            raise FathomAdapterError(f"Fathom returned invalid SAN {san!r}") from exc
        moves.append(move.uci())
    return tuple(moves)


@dataclass(frozen=True)
class FathomEvidence:
    fen: str
    result: str
    wdl: str
    dtz: int
    winning_moves_uci: Tuple[str, ...]
    drawing_moves_uci: Tuple[str, ...]
    losing_moves_uci: Tuple[str, ...]
    binary_sha256: str | None = None
    table_files_sha256: Mapping[str, str] | None = None

    @property
    def move_partition(self) -> Tuple[str, ...]:
        return self.winning_moves_uci + self.drawing_moves_uci + self.losing_moves_uci


def parse_fathom_output(fen: str, stdout: str) -> FathomEvidence:
    """Parse Fathom PGN headers and prove they partition every legal move."""
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise FathomAdapterError("probe FEN is invalid") from exc
    if board.is_game_over():
        raise FathomAdapterError("probe FEN has no legal move")

    headers = _parse_headers(stdout)
    required = {"FEN", "Result", "WDL", "DTZ", "WinningMoves", "DrawingMoves", "LosingMoves"}
    missing = sorted(required.difference(headers))
    if missing:
        raise FathomAdapterError(f"Fathom output is missing headers: {', '.join(missing)}")
    if headers["FEN"] != fen:
        raise FathomAdapterError("Fathom output belongs to a different FEN")
    if headers["WDL"] not in _ALLOWED_WDL:
        raise FathomAdapterError(f"unsupported WDL value {headers['WDL']!r}")
    if headers["Result"] not in {"1-0", "1/2-1/2", "0-1"}:
        raise FathomAdapterError("Fathom returned an invalid game result")
    try:
        dtz = int(headers["DTZ"])
    except ValueError as exc:
        raise FathomAdapterError("Fathom DTZ is not an integer") from exc

    winning = _parse_move_bucket(board, headers["WinningMoves"])
    drawing = _parse_move_bucket(board, headers["DrawingMoves"])
    losing = _parse_move_bucket(board, headers["LosingMoves"])
    partition = winning + drawing + losing
    if len(set(partition)) != len(partition):
        raise FathomAdapterError("Fathom move buckets overlap")
    legal = {move.uci() for move in board.legal_moves}
    if set(partition) != legal:
        missing_moves = sorted(legal.difference(partition))
        extra_moves = sorted(set(partition).difference(legal))
        raise FathomAdapterError(
            f"Fathom move buckets do not partition legal moves; missing={missing_moves}, extra={extra_moves}"
        )

    return FathomEvidence(
        fen=fen,
        result=headers["Result"],
        wdl=headers["WDL"],
        dtz=dtz,
        winning_moves_uci=winning,
        drawing_moves_uci=drawing,
        losing_moves_uci=losing,
    )


def probe_fathom(binary_path: Path, tablebase_path: Path, fen: str) -> FathomEvidence:
    """Run a pinned local Fathom binary without a shell and validate its output."""
    binary = Path(binary_path).resolve(strict=True)
    table_dir = Path(tablebase_path).resolve(strict=True)
    if not binary.is_file():
        raise FathomAdapterError("Fathom binary path is not a file")
    if not table_dir.is_dir():
        raise FathomAdapterError("tablebase path is not a directory")
    table_files = sorted(
        path for path in table_dir.iterdir()
        if path.is_file() and path.suffix in {".rtbw", ".rtbz"}
    )
    if not table_files:
        raise FathomAdapterError("tablebase path contains no Syzygy files")

    completed = subprocess.run(
        [str(binary), f"--path={table_dir}", fen],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        raise FathomAdapterError(
            f"Fathom failed with exit {completed.returncode}: {completed.stderr.strip()}"
        )
    parsed = parse_fathom_output(fen, completed.stdout)
    return FathomEvidence(
        fen=parsed.fen,
        result=parsed.result,
        wdl=parsed.wdl,
        dtz=parsed.dtz,
        winning_moves_uci=parsed.winning_moves_uci,
        drawing_moves_uci=parsed.drawing_moves_uci,
        losing_moves_uci=parsed.losing_moves_uci,
        binary_sha256=_sha256_file(binary),
        table_files_sha256={path.name: _sha256_file(path) for path in table_files},
    )
