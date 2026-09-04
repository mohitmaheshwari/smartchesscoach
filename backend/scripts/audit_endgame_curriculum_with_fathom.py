#!/usr/bin/env python3
"""Audit routed endgame lesson moves against legal chess and exact Syzygy truth.

This is an offline research tool. It reads the canonical lesson tree, invokes a
pinned Fathom binary for tablebase-eligible positions, and writes content-only
evidence. It never reads MongoDB or changes lesson admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict

import chess

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from research.human_chess_intelligence.fathom_adapter import (  # noqa: E402
    FathomAdapterError,
    FathomEvidence,
    probe_fathom,
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_bucket(evidence: FathomEvidence) -> str:
    if evidence.wdl in {"Win", "CursedWin"}:
        return "winning"
    if evidence.wdl == "Draw":
        return "drawing"
    return "losing"


def _move_bucket(evidence: FathomEvidence, move_uci: str) -> str:
    if move_uci in evidence.winning_moves_uci:
        return "winning"
    if move_uci in evidence.drawing_moves_uci:
        return "drawing"
    if move_uci in evidence.losing_moves_uci:
        return "losing"
    raise AssertionError("validated Fathom partition omitted a legal move")


def audit_tree(
    tree: Dict[str, Any],
    probe: Callable[[str], FathomEvidence],
    *,
    maximum_men: int = 5,
) -> Dict[str, Any]:
    """Return deterministic per-position findings and aggregate counts."""
    findings = []
    counts: Counter[str] = Counter()
    lesson_count = 0

    for category_key, category in tree.items():
        if category_key == "_meta":
            continue
        for lesson_key, lesson in category.get("lessons", {}).items():
            lesson_count += 1
            for position_index, position in enumerate(lesson.get("positions", [])):
                counts["positions"] += 1
                finding: Dict[str, Any] = {
                    "category": category_key,
                    "lesson": lesson_key,
                    "position_index": position_index,
                    "fen": position.get("fen"),
                    "authored_move_san": position.get("correct_move_san"),
                    "authored_move_uci": position.get("correct_move_uci"),
                }
                try:
                    board = chess.Board(str(position.get("fen") or ""))
                except ValueError as exc:
                    finding.update(status="invalid_fen", reason=str(exc))
                    counts["invalid_positions"] += 1
                    findings.append(finding)
                    continue
                finding["piece_count"] = chess.popcount(board.occupied)
                if not board.is_valid():
                    finding.update(
                        status="invalid_board",
                        reason=f"python-chess status={int(board.status())}",
                    )
                    counts["invalid_positions"] += 1
                    findings.append(finding)
                    continue
                try:
                    authored_move = board.parse_san(str(position.get("correct_move_san") or ""))
                except ValueError as exc:
                    finding.update(status="illegal_authored_move", reason=str(exc))
                    counts["invalid_positions"] += 1
                    findings.append(finding)
                    continue
                authored_uci = str(position.get("correct_move_uci") or "")
                if authored_uci and authored_move.uci() != authored_uci:
                    finding.update(
                        status="san_uci_mismatch",
                        parsed_move_uci=authored_move.uci(),
                    )
                    counts["invalid_positions"] += 1
                    findings.append(finding)
                    continue
                if finding["piece_count"] > maximum_men:
                    finding["status"] = "outside_tablebase_coverage"
                    counts["outside_tablebase_coverage"] += 1
                    findings.append(finding)
                    continue
                try:
                    evidence = probe(board.fen())
                except FathomAdapterError as exc:
                    finding.update(status="tablebase_probe_failed", reason=str(exc))
                    counts["tablebase_probe_failed"] += 1
                    findings.append(finding)
                    continue

                expected_bucket = _expected_bucket(evidence)
                actual_bucket = _move_bucket(evidence, authored_move.uci())
                preserving_moves = {
                    "winning": evidence.winning_moves_uci,
                    "drawing": evidence.drawing_moves_uci,
                    "losing": evidence.losing_moves_uci,
                }[expected_bucket]
                preserves = actual_bucket == expected_bucket
                finding.update(
                    status="exact_preserves_result" if preserves else "exact_changes_result",
                    tablebase_wdl=evidence.wdl,
                    tablebase_dtz=evidence.dtz,
                    authored_move_bucket=actual_bucket,
                    result_preserving_move_count=len(preserving_moves),
                    authored_move_is_only_result_preserving=(
                        preserves and len(preserving_moves) == 1
                    ),
                )
                counts["tablebase_probed"] += 1
                counts[
                    "exact_moves_preserving_result" if preserves else "exact_moves_changing_result"
                ] += 1
                if len(preserving_moves) > 1:
                    counts["multiple_result_preserving_moves"] += 1
                findings.append(finding)

    return {
        "counts": {"lessons": lesson_count, **dict(sorted(counts.items()))},
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", required=True, type=Path)
    parser.add_argument("--fathom-binary", required=True, type=Path)
    parser.add_argument("--tablebase-path", required=True, type=Path)
    parser.add_argument("--fathom-commit", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--maximum-men", type=int, default=5)
    args = parser.parse_args()

    content_path = args.content.resolve(strict=True)
    binary_path = args.fathom_binary.resolve(strict=True)
    tablebase_path = args.tablebase_path.resolve(strict=True)
    tree = json.loads(content_path.read_text(encoding="utf-8"))
    audit = audit_tree(
        tree,
        lambda fen: probe_fathom(binary_path, tablebase_path, fen),
        maximum_men=args.maximum_men,
    )
    table_hashes = {
        path.name: _sha256_file(path)
        for path in sorted(tablebase_path.iterdir())
        if path.is_file() and path.suffix in {".rtbw", ".rtbz"}
    }
    result = {
        "schema_version": "human_chess.fathom_curriculum_audit.v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "research_only": True,
        "production_writes": False,
        "source": {
            "content_filename": content_path.name,
            "content_sha256": _sha256_file(content_path),
            "source_revision": args.source_revision,
        },
        "provenance": {
            "fathom_commit": args.fathom_commit,
            "fathom_binary_sha256": _sha256_file(binary_path),
            "maximum_men": args.maximum_men,
            "table_files_sha256": table_hashes,
        },
        **audit,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": result["counts"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
