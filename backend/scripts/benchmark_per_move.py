"""
benchmark_per_move.py — measure latency of the V5 caption brain per
move, broken down by detector block.

Important for the v100 pipeline-extraction work: V5 service is batch
(no time pressure); PWC has a 400-700ms target. If the full V5 brain
exceeds PWC's budget per move, the shared pipeline needs a fast-mode
flag that skips the heavy detectors.

Captures p50/p95/p99 latency for each block, ordered by cost.

Blocks (mirror the order V5 service runs them):
  1. extract_facts (base)
  2. opp-side punishment + positional facts
  3. simulate_* detectors (pawn_kicks, attack_with_tempo, etc.)
  4. shape-pattern detection
  5. trap_recognition
  6. board_state_describer
  7. opening_theory_lookup
  8. severity classification (canonical + practical)
  9. resolve_priority

Output is human-readable + JSON for diff/regression tracking.

Usage:
  python -m scripts.benchmark_per_move --tag baseline_v99
  python -m scripts.benchmark_per_move --tag post_extraction
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

sys.path.insert(0, "/app/backend")

import chess
from motor.motor_asyncio import AsyncIOMotorClient


PINNED_GAMES = [
    "game_85bd0169aa4f", "game_b5d23694a803", "game_f2c022e03856",
    "game_ef9f422a062d", "game_74fdbd74c468", "game_4177951c757f",
    "game_bc41022831e0", "game_4c0f48f6cc0a", "game_8efcc1db5aa4",
    "game_692ab776c5b1",
]


def _percentile(samples: List[float], p: float) -> float:
    """Approximate percentile from sorted samples."""
    if not samples:
        return 0.0
    s = sorted(samples)
    idx = int(round((p / 100.0) * (len(s) - 1)))
    return s[max(0, min(idx, len(s) - 1))]


async def _run() -> List[Dict[str, Any]]:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
    db = client["chess_coach"]

    # Pull move records from the 10 pinned games. Each move record
    # already has fen_before / played_san / best_move / cp_loss /
    # pv_after_played / pv_after_best — everything we need to re-run
    # the pipeline timing.
    move_inputs: List[Dict[str, Any]] = []
    for gid in PINNED_GAMES:
        g = await db.game_analyses.find_one({"game_id": gid})
        if not g:
            continue
        moves = g.get("decryption_v5_data") or []
        for idx, m in enumerate(moves):
            if not isinstance(m, dict):
                continue
            move_inputs.append({
                "game_id": gid,
                "move_idx": idx,
                "fen_before": m.get("fen_before") or "",
                "played_san": m.get("move_san") or "",
                "best_move_san": m.get("best_move_san") or "",
                "eval_before": m.get("eval_before"),
                "eval_after": m.get("eval_after"),
                "cp_loss": m.get("cp_loss") or 0,
                "pv_after_played": m.get("pv_after_played") or [],
                "pv_after_best": m.get("pv_after_best") or [],
                "is_user_move": bool(m.get("is_user_move")),
                "is_white": bool(m.get("is_white")),
                "move_number": m.get("move_number"),
            })

    if not move_inputs:
        print("No move inputs to benchmark.")
        return []

    print(f"Benchmarking on {len(move_inputs)} moves...")

    # Lazy-import the V5 pipeline blocks so the timing is honest
    # (no startup-cost confound).
    from services.caption_facts import extract_facts
    from services.caption_priority_resolver import resolve_priority
    from services.severity import classify_severity, classify_severity_practical
    from services.shape_detectors import (
        detect_all_shapes,
        simulate_pawn_kicks_piece,
        simulate_attack_with_tempo,
        simulate_clearance_for_attack,
        simulate_clearance_then_check,
        simulate_endgame_loose_pawn_grab,
    )
    from services.trap_recognition import detect_trap_setup
    from services.board_state_describer import describe_board_state
    from services.opening_theory_lookup import match_position
    from services.pattern_catalog import detect_opp_positional_mistake

    blocks: Dict[str, List[float]] = {
        "extract_facts": [],
        "opp_positional_mistake": [],
        "simulate_pawn_kicks_piece": [],
        "simulate_attack_with_tempo": [],
        "simulate_clearance_for_attack": [],
        "simulate_clearance_then_check": [],
        "simulate_endgame_loose_pawn_grab": [],
        "detect_all_shapes": [],
        "detect_trap_setup": [],
        "board_state_describer": [],
        "opening_theory_lookup": [],
        "severity_canonical": [],
        "severity_practical": [],
        "resolve_priority": [],
        "TOTAL_PER_MOVE": [],
    }

    for mv in move_inputs:
        t_total_start = time.perf_counter()

        # extract_facts
        t0 = time.perf_counter()
        try:
            facts = extract_facts(
                fen_before=mv["fen_before"],
                played_san=mv["played_san"],
                best_move_san=mv["best_move_san"],
                eval_before_cp=mv["eval_before"],
                eval_after_cp=mv["eval_after"],
                cp_loss=mv["cp_loss"],
                pv_after_played=mv["pv_after_played"],
                pv_after_best=mv["pv_after_best"],
                move_history_san=[],
                full_move_number=mv["move_number"],
                mover_is_user=mv["is_user_move"],
            )
        except Exception:
            continue
        blocks["extract_facts"].append((time.perf_counter() - t0) * 1000)

        # opp positional mistake (cheap)
        t0 = time.perf_counter()
        try:
            detect_opp_positional_mistake(mv["fen_before"], mv["played_san"], mv["move_number"])
        except Exception:
            pass
        blocks["opp_positional_mistake"].append((time.perf_counter() - t0) * 1000)

        # simulate_* detectors — each takes (fen, best_move_san)
        best = mv["best_move_san"]
        for name, fn in [
            ("simulate_pawn_kicks_piece", simulate_pawn_kicks_piece),
            ("simulate_attack_with_tempo", simulate_attack_with_tempo),
            ("simulate_clearance_for_attack", simulate_clearance_for_attack),
            ("simulate_clearance_then_check", simulate_clearance_then_check),
            ("simulate_endgame_loose_pawn_grab", simulate_endgame_loose_pawn_grab),
        ]:
            t0 = time.perf_counter()
            try:
                if best:
                    fn(mv["fen_before"], best)
            except Exception:
                pass
            blocks[name].append((time.perf_counter() - t0) * 1000)

        # shape detection on post-move board
        t0 = time.perf_counter()
        try:
            board = chess.Board(mv["fen_before"])
            mv_obj = board.parse_san(mv["played_san"])
            board.push(mv_obj)
            detect_all_shapes(board)
        except Exception:
            pass
        blocks["detect_all_shapes"].append((time.perf_counter() - t0) * 1000)

        # trap recognition (needs move history — pass empty for now;
        # measures match speed against the trap library)
        t0 = time.perf_counter()
        try:
            detect_trap_setup([])
        except Exception:
            pass
        blocks["detect_trap_setup"].append((time.perf_counter() - t0) * 1000)

        # board state describer (post-move board)
        t0 = time.perf_counter()
        try:
            board = chess.Board(mv["fen_before"])
            mv_obj = board.parse_san(mv["played_san"])
            board.push(mv_obj)
            describe_board_state(board, "white" if mv["is_user_move"] == mv["is_white"] else "black")
        except Exception:
            pass
        blocks["board_state_describer"].append((time.perf_counter() - t0) * 1000)

        # opening theory lookup (post-move FEN)
        t0 = time.perf_counter()
        try:
            board = chess.Board(mv["fen_before"])
            mv_obj = board.parse_san(mv["played_san"])
            board.push(mv_obj)
            match_position(board.fen())
        except Exception:
            pass
        blocks["opening_theory_lookup"].append((time.perf_counter() - t0) * 1000)

        # severity classification (canonical)
        t0 = time.perf_counter()
        try:
            classify_severity(mv["cp_loss"], mover_is_user=mv["is_user_move"])
        except Exception:
            pass
        blocks["severity_canonical"].append((time.perf_counter() - t0) * 1000)

        # severity classification (practical)
        t0 = time.perf_counter()
        try:
            classify_severity_practical(
                mv["cp_loss"],
                mover_is_user=mv["is_user_move"],
                mover_is_white=mv["is_white"],
                eval_before_cp=mv["eval_before"],
                eval_after_cp=mv["eval_after"],
            )
        except Exception:
            pass
        blocks["severity_practical"].append((time.perf_counter() - t0) * 1000)

        # resolve_priority
        t0 = time.perf_counter()
        try:
            resolve_priority({
                "caption_facts_principles_violated": facts.get("principles_violated") or [],
                "shape_pattern_id": facts.get("shape_pattern_id"),
                "shape_pattern_name": facts.get("shape_pattern_name"),
                "move_san": mv["played_san"],
                "best_move_san": best,
                "cp_loss": mv["cp_loss"],
                "phase": facts.get("phase"),
                "is_user_move": mv["is_user_move"],
                "fen_before": mv["fen_before"],
                "caption": "",
                "principle_cue": "",
                "principle_id_used": None,
                "rule_name": None,
            })
        except Exception:
            pass
        blocks["resolve_priority"].append((time.perf_counter() - t0) * 1000)

        blocks["TOTAL_PER_MOVE"].append((time.perf_counter() - t_total_start) * 1000)

    # Build stats per block
    stats = []
    for name, samples in blocks.items():
        if not samples:
            stats.append({"block": name, "n": 0, "mean": 0, "p50": 0, "p95": 0, "p99": 0})
            continue
        mean = sum(samples) / len(samples)
        stats.append({
            "block": name,
            "n": len(samples),
            "mean": round(mean, 2),
            "p50": round(_percentile(samples, 50), 2),
            "p95": round(_percentile(samples, 95), 2),
            "p99": round(_percentile(samples, 99), 2),
        })
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output-dir", default="/app/backend/scripts/_snapshots")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = asyncio.run(_run())
    out_path = output_dir / f"bench_{args.tag}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
        f.write("\n")

    # Print table
    print(f"\n{'block':<35} {'n':>6} {'mean':>8} {'p50':>8} {'p95':>8} {'p99':>8}")
    print("-" * 80)
    for row in stats:
        print(
            f"{row['block']:<35} {row['n']:>6} "
            f"{row['mean']:>7.2f}ms {row['p50']:>7.2f}ms "
            f"{row['p95']:>7.2f}ms {row['p99']:>7.2f}ms"
        )
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
