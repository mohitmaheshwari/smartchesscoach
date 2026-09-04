#!/usr/bin/env python3
"""Run the authorized target-line population export without leaking stdout.

The remote script performs read-only Mongo queries inside the production
backend container. This local runner supplies content-only exclusions,
captures the base64 payload in memory, validates it, and writes only the
anonymized versioned evidence packets.
"""
from __future__ import annotations

import base64
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

import chess


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
EXPORTER_PATH = Path(__file__).with_name(
    "export_full_game_chess_fact_audit.py"
)
SNAPSHOT_ROOT = BACKEND_ROOT / "data" / "corpus_snapshots"
BANDS = ("600-899", "900-1199", "1200-1499", "1500-1999")
POSITIONS_PER_BAND = 375
PHASE_MINIMUM = 50
ALLOWED_POSITION_KEYS = {
    "rating_band",
    "phase",
    "fen_before",
    "side_to_move",
    "played_san",
    "best_move_san",
    "pv_after_played",
    "pv_after_best",
    "cp_loss",
}
FORBIDDEN_KEYS = {
    "_id",
    "user_id",
    "game_id",
    "email",
    "username",
    "chess_com_username",
    "chesscom_username",
    "lichess_username",
    "profile_id",
    "date_played",
    "date_played_iso",
    "imported_at",
    "analyzed_at",
    "created_at",
    "url",
    "source_url",
    "white_player",
    "black_player",
    "white",
    "black",
    "pgn",
}
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
URL_RE = re.compile(r"https?://|www\.", re.I)

ARCHITECTURE_GOLD_PATH = SNAPSHOT_ROOT / (
    "hidden_opportunities_chess_gold_v1_2026-09-02.json"
)
FULL_AUDIT_PATH = SNAPSHOT_ROOT / (
    "full_game_chess_fact_audit_v1_2026-09-03.json"
)
PRIOR_PACKET_PATH = BACKEND_ROOT / (
    "data/detector_gold/verified_single_game_cause_promotion_v1.json"
)
ORIGINAL_POPULATION_PATH = SNAPSHOT_ROOT / (
    "target_line_population_export_v1_2026-09-04.json"
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_record(path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": _sha256_bytes(path.read_bytes()),
    }


def position_signature(row: Mapping[str, Any]) -> str:
    payload = {
        "fen_before": row["fen_before"],
        "played_san": row["played_san"],
        "best_move_san": row["best_move_san"],
    }
    return _sha256_bytes(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )


def prior_evidence_signatures(
    *,
    include_original_population: bool = False,
) -> set[str]:
    signatures: set[str] = set()
    architecture = json.loads(
        ARCHITECTURE_GOLD_PATH.read_text(encoding="utf-8")
    )
    for row in architecture["positions"]:
        signatures.add(position_signature({
            "fen_before": row["fen"],
            "played_san": row["played_move"]["san"],
            "best_move_san": row["best_move"]["san"],
        }))

    full_audit = json.loads(FULL_AUDIT_PATH.read_text(encoding="utf-8"))
    for game in full_audit["games"]:
        for row in game["meaningful_decisions"]:
            signatures.add(position_signature(row))

    prior = json.loads(PRIOR_PACKET_PATH.read_text(encoding="utf-8"))
    for collection_name in ("fires", "negatives"):
        for row in prior[collection_name]:
            signatures.add(position_signature({
                "fen_before": row["fen_before"],
                "played_san": row["move_san"],
                "best_move_san": row["best_move_san"],
            }))
    if include_original_population:
        original = json.loads(
            ORIGINAL_POPULATION_PATH.read_text(encoding="utf-8")
        )
        signatures.update(
            position_signature(row) for row in original["positions"]
        )
    return signatures


def _walk_privacy(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS:
                raise ValueError(f"forbidden output key: {key}")
            _walk_privacy(child)
    elif isinstance(value, list):
        for child in value:
            _walk_privacy(child)


def _replay_branch(fen: str, first_san: str, continuation: list[str]) -> None:
    board = chess.Board(fen)
    board.push_san(first_san)
    for san in continuation:
        board.push_san(san)


def validate_band_packet(
    packet: Mapping[str, Any],
    *,
    rating_band: str,
    exclusions: set[str],
) -> list[str]:
    _walk_privacy(packet)
    serialized = json.dumps(packet, ensure_ascii=True, sort_keys=True)
    if EMAIL_RE.search(serialized) or URL_RE.search(serialized):
        raise ValueError("email or URL pattern in packet")
    if packet.get("schema_version") != "target_line_population_export.v1":
        raise ValueError("unexpected band schema")
    if packet.get("rating_band") != rating_band:
        raise ValueError("rating-band mismatch")
    positions = packet.get("positions")
    if not isinstance(positions, list) or len(positions) != POSITIONS_PER_BAND:
        raise ValueError("wrong position count")
    if packet.get("selected_positions") != POSITIONS_PER_BAND:
        raise ValueError("wrong selected-position count")
    if packet.get("distinct_source_games") != POSITIONS_PER_BAND:
        raise ValueError("one-position-per-game contract failed")
    if packet.get("excluded_position_signatures_supplied") != len(exclusions):
        raise ValueError("remote exclusion count mismatch")

    signatures: list[str] = []
    phases = Counter()
    for row in positions:
        if set(row) != ALLOWED_POSITION_KEYS:
            raise ValueError("unexpected position field set")
        if row["rating_band"] != rating_band:
            raise ValueError("position rating-band mismatch")
        if row["phase"] not in {"opening", "middlegame", "endgame"}:
            raise ValueError("invalid phase")
        expected_side = "white" if chess.Board(row["fen_before"]).turn else "black"
        if row["side_to_move"] != expected_side:
            raise ValueError("side-to-move mismatch")
        _replay_branch(
            row["fen_before"], row["played_san"], row["pv_after_played"]
        )
        _replay_branch(
            row["fen_before"], row["best_move_san"], row["pv_after_best"]
        )
        signature = position_signature(row)
        if signature in exclusions:
            raise ValueError("prior evidence survived exclusion")
        signatures.append(signature)
        phases[row["phase"]] += 1
    if len(set(signatures)) != POSITIONS_PER_BAND:
        raise ValueError("duplicate position in band")
    if any(phases[phase] < PHASE_MINIMUM for phase in phases):
        raise ValueError("phase minimum not met")
    if any(phases[phase] < PHASE_MINIMUM for phase in (
        "opening", "middlegame", "endgame"
    )):
        raise ValueError("phase minimum not met")
    return signatures


def fetch_band(
    rating_band: str,
    *,
    exclusions: set[str],
    host: str,
) -> dict[str, Any]:
    exclusion_json = json.dumps(sorted(exclusions), separators=(",", ":"))
    exclusion_b64 = base64.b64encode(exclusion_json.encode("utf-8")).decode(
        "ascii"
    )
    source = (
        "import os\n"
        f"os.environ['TARGET_LINE_EXCLUDED_SIGNATURES_B64']={exclusion_b64!r}\n"
        + EXPORTER_PATH.read_text(encoding="utf-8")
    )
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        host,
        (
            "docker exec -i chess-coach-backend python - "
            f"{rating_band} target-line-population"
        ),
    ]
    result = subprocess.run(
        command,
        input=source.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"remote read failed for {rating_band} (exit {result.returncode})"
        )
    try:
        decoded = base64.b64decode(result.stdout.strip(), validate=True)
        packet = json.loads(decoded.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"invalid remote payload for {rating_band}"
        ) from exc
    validate_band_packet(
        packet, rating_band=rating_band, exclusions=exclusions
    )
    return packet


def write_packets(*, host: str, generation: str) -> dict[str, Any]:
    if generation not in {"v1", "v2"}:
        raise ValueError("generation must be v1 or v2")
    exclusions = prior_evidence_signatures(
        include_original_population=generation == "v2"
    )
    band_paths = {
        rating_band: SNAPSHOT_ROOT / (
            f"target_line_population_export_{generation}_"
            f"{rating_band}_2026-09-04.json"
        )
        for rating_band in BANDS
    }
    combined_path = SNAPSHOT_ROOT / (
        f"target_line_population_export_{generation}_2026-09-04.json"
    )
    if generation == "v2":
        existing = [
            path
            for path in (*band_paths.values(), combined_path)
            if path.exists()
        ]
        if existing:
            raise FileExistsError(
                f"refusing to overwrite holdout packet: {existing[0]}"
            )
    running_exclusions = set(exclusions)
    band_packets: list[dict[str, Any]] = []
    all_signatures: list[str] = []
    for rating_band in BANDS:
        packet = fetch_band(
            rating_band, exclusions=running_exclusions, host=host
        )
        signatures = validate_band_packet(
            packet, rating_band=rating_band, exclusions=running_exclusions
        )
        all_signatures.extend(signatures)
        running_exclusions.update(signatures)
        band_packets.append(packet)

    if len(set(all_signatures)) != len(all_signatures):
        raise ValueError("cross-band duplicate position")
    positions = [
        row for packet in band_packets for row in packet["positions"]
    ]
    combined = {
        "schema_version": (
            f"target_line_population_export_combined.{generation}"
        ),
        "generated_on": "2026-09-04",
        "read_only_production_export": True,
        "production_writes": 0,
        "stockfish_runs": 0,
        "llm_calls": 0,
        "maia_runs": 0,
        "selection": (
            "1,500 detector-label-blind positions from 1,500 distinct "
            "source games; 375 per rating band; at least 50 per phase "
            "within each band; prior evidence excluded by content hash."
        ),
        "privacy": (
            "FEN, side to move, played/better SAN, two stored SAN "
            "continuations, rating band, phase, and cp_loss only. No user "
            "or game identifiers, names, usernames, emails, dates, URLs, "
            "PGN headers, credentials, captions, labels, or detector output."
        ),
        "prior_evidence_sources": [
            _file_record(ARCHITECTURE_GOLD_PATH),
            _file_record(FULL_AUDIT_PATH),
            _file_record(PRIOR_PACKET_PATH),
        ] + (
            [_file_record(ORIGINAL_POPULATION_PATH)]
            if generation == "v2"
            else []
        ),
        "prior_evidence_signatures_excluded": len(exclusions),
        "cross_band_duplicates_excluded_sequentially": True,
        "band_packet_fingerprints": {
            packet["rating_band"]: packet["selection_fingerprint_sha256"]
            for packet in band_packets
        },
        "band_counts": dict(Counter(row["rating_band"] for row in positions)),
        "phase_counts": dict(Counter(row["phase"] for row in positions)),
        "positions": positions,
    }
    _walk_privacy(combined)
    # Do not leave a partial evidence generation if any remote band fails.
    # All four packets are fetched and validated before the first local write.
    for packet in band_packets:
        band_paths[packet["rating_band"]].write_text(
            json.dumps(packet, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    combined_path.write_text(
        json.dumps(combined, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "combined_path": combined_path.relative_to(REPO_ROOT).as_posix(),
        "positions": len(positions),
        "prior_signatures_excluded": len(exclusions),
        "band_counts": combined["band_counts"],
        "phase_counts": combined["phase_counts"],
        "combined_sha256": _sha256_bytes(combined_path.read_bytes()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generation", choices=("v1", "v2"), required=True)
    parser.add_argument("--host", default="root@72.60.204.176")
    args = parser.parse_args()
    summary = write_packets(host=args.host, generation=args.generation)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
