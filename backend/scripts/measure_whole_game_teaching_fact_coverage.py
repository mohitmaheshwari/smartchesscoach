#!/usr/bin/env python3
"""Compare frozen Codex chess gold with canonical deterministic fact builders.

This is an offline evaluator. It reads the identity-free development packet,
calls only the pure functions in ``services.caption_facts``, and writes no
database state. It deliberately does not invoke Game Decryption V5: a full V5
render can perform optional runtime work that is outside this evidence audit.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.caption_facts import (
    build_legal_material_loss_cause,
    build_verified_hidden_opportunity,
    build_verified_line_cause,
)


SCHEMA_VERSION = "whole_game_teaching_fact_coverage.v1"
BACKEND = Path(__file__).resolve().parents[1]
DEFAULT_PACKET = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_development_packet_v1.json"
)
DEFAULT_WORKSHEET = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_codex_worksheet_v1.json"
)
EXPECTED_PACKET_SHA256 = (
    "b0f44d273b9b597e9aaabcc0fa991a50083aa2909ec701cb625b6267303d4ac2"
)
EXPECTED_WORKSHEET_SHA256 = (
    "6eb3014201940703420057bd72bb9cb6d7eee4f1327c6cc266238afe1968946c"
)
MINIMUM_MATERIAL_GAIN_CP = 80


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_bound(path: Path, expected_sha256: str) -> Any:
    actual = _sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"frozen evidence hash mismatch: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _evidence_index(game: Mapping[str, Any]) -> Dict[tuple[int, str], Mapping[str, Any]]:
    index: Dict[tuple[int, str], Mapping[str, Any]] = {}
    for row in game.get("stored_engine_evidence") or []:
        key = (int(row.get("ply") or 0), str(row.get("actor") or ""))
        if key in index:
            raise ValueError("duplicate engine evidence identity")
        index[key] = row
    return index


def _fact_projection(row: Mapping[str, Any]) -> Dict[str, Any]:
    common = {
        "fen_before": str(row.get("fen_before") or ""),
        "played_san": str(row.get("played_san") or ""),
        "best_move_san": str(row.get("best_move_san") or ""),
        "pv_after_played": list(row.get("pv_after_played") or []),
        "pv_after_best": list(row.get("pv_after_best") or []),
        "cp_loss": int(row.get("cp_loss") or 0),
    }
    material = build_legal_material_loss_cause(
        fen_before=common["fen_before"],
        played_san=common["played_san"],
        best_move_san=common["best_move_san"],
        minimum_gain_cp=MINIMUM_MATERIAL_GAIN_CP,
    )
    line = build_verified_line_cause(
        **common,
        include_branch_evidence=True,
    )
    hidden = build_verified_hidden_opportunity(**common)
    return {
        "legal_material_loss": (
            {
                "fingerprint": material.fingerprint,
                "punishment_san": material.punishment_san,
                "material_loss_cp": material.material_loss_cp,
            }
            if material is not None
            else None
        ),
        "verified_line": (
            {
                "fingerprint": line.fingerprint,
                "lesson_kind": line.lesson_kind,
            }
            if line is not None
            else None
        ),
        "hidden_opportunity": (
            {
                "fingerprint": hidden.fingerprint,
                "family": hidden.family,
                "mechanism": hidden.mechanism,
            }
            if hidden is not None
            else None
        ),
    }


def _match_status(gold_family: str, facts: Mapping[str, Any]) -> str:
    material = facts.get("legal_material_loss")
    line = facts.get("verified_line") or {}
    line_kind = line.get("lesson_kind")
    exact = bool(
        (gold_family == "immediate_material_loss" and material)
        or (
            gold_family == "immediate_material_loss"
            and line_kind == "immediate_material_loss"
        )
        or (
            gold_family in {"allowed_forced_mate", "missed_forced_mate"}
            and line_kind == gold_family
        )
        or (
            gold_family == "safe_missed_capture"
            and line_kind == "missed_material_opportunity"
        )
    )
    if exact:
        return "exact_fact"
    if material or line or facts.get("hidden_opportunity"):
        return "different_fact"
    return "no_typed_fact"


def measure(packet: Mapping[str, Any], worksheet: Mapping[str, Any]) -> Dict[str, Any]:
    packet_games = {
        str(game["anonymous_game_key"]): game for game in packet.get("games") or []
    }
    worksheet_games = worksheet.get("games") or []
    if set(packet_games) != {
        str(game.get("anonymous_game_key") or "") for game in worksheet_games
    }:
        raise ValueError("packet and worksheet memberships differ")

    rows = []
    counts: Counter[str] = Counter()
    family_counts: Counter[tuple[str, str]] = Counter()
    seen = set()
    for reviewed_game in worksheet_games:
        game_key = str(reviewed_game["anonymous_game_key"])
        evidence = _evidence_index(packet_games[game_key])
        for moment in reviewed_game.get("moments") or []:
            identity = (game_key, int(moment["ply"]), str(moment["actor"]))
            if identity in seen:
                raise ValueError("duplicate reviewed moment")
            seen.add(identity)
            row = evidence.get((identity[1], identity[2]))
            if row is None:
                raise ValueError("reviewed moment has no stored evidence row")
            facts = _fact_projection(row)
            family = str(moment["cause_family"])
            status = _match_status(family, facts)
            counts[status] += 1
            family_counts[(family, status)] += 1
            rows.append({
                "anonymous_game_key": game_key,
                "ply": identity[1],
                "actor": identity[2],
                "gold_family": family,
                "status": status,
                "facts": facts,
            })

    total = len(rows)
    exact = counts["exact_fact"]
    families = {}
    for family in sorted({row["gold_family"] for row in rows}):
        family_total = sum(
            family_counts[(family, status)]
            for status in ("exact_fact", "different_fact", "no_typed_fact")
        )
        families[family] = {
            "gold_moments": family_total,
            "exact_fact": family_counts[(family, "exact_fact")],
            "different_fact": family_counts[(family, "different_fact")],
            "no_typed_fact": family_counts[(family, "no_typed_fact")],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "packet_sha256": EXPECTED_PACKET_SHA256,
            "worksheet_sha256": EXPECTED_WORKSHEET_SHA256,
            "games": len(packet_games),
            "holdout_opened": False,
        },
        "execution_contract": {
            "database_reads": 0,
            "database_writes": 0,
            "engine_runs": 0,
            "model_calls": 0,
            "fact_authority": "services.caption_facts",
            "minimum_material_gain_cp": MINIMUM_MATERIAL_GAIN_CP,
        },
        "summary": {
            "gold_moments": total,
            "exact_fact": exact,
            "different_fact": counts["different_fact"],
            "no_typed_fact": counts["no_typed_fact"],
            "exact_coverage_pct": round(100.0 * exact / total, 2) if total else 0.0,
        },
        "by_gold_family": families,
        "moments": sorted(
            rows,
            key=lambda item: (
                item["anonymous_game_key"], item["ply"], item["actor"]
            ),
        ),
    }


def build_report(packet_path: Path, worksheet_path: Path) -> Dict[str, Any]:
    packet = _load_bound(packet_path, EXPECTED_PACKET_SHA256)
    worksheet = _load_bound(worksheet_path, EXPECTED_WORKSHEET_SHA256)
    return measure(packet, worksheet)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--worksheet", type=Path, default=DEFAULT_WORKSHEET)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.packet, args.worksheet)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
