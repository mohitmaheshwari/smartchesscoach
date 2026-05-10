"""
Cat 4 / Cat 5 measurement script.

The audit (verify_fixes_against_bug_corpus.py + content_correctness_audit.py)
measures content guards by replaying STORED bug strings through the
guard. That misses two categories whose fixes only fire during fresh
generation:

  - Category 4 (calculation depth / "free capture" claims). The
    threat_verifier runs a live engine search; it can only fire when
    smart_coaching / PwC realtime is generating new text.
  - Category 5 (vacuous coaching). The vacuous_text_detector strips
    filler at emit time; its effect is invisible in stored bug
    strings unless we re-generate.

This script:
  1. Loads the bug corpus.
  2. Filters to bugs from `page` = "lab" (the V5 decryption surface;
     the surface where Cat 5 + Cat 8 + Cat 1 source-fixes are wired).
  3. Groups by game_id; for each unique game, loads its PGN +
     stockfish move_evaluations from MongoDB.
  4. Runs `generate_game_decryption_v5` fresh against each game.
  5. For each bug, locates the matching move (move_number + move_san)
     in the regenerated output, captures the new narrative /
     consequence.
  6. Compares new text vs flagged text and classifies the diff:
       wiped     — new text is empty (guard wiped it)
       changed   — new text is non-empty and different
       same      — new text is identical to flagged
       not_found — couldn't locate the move in regenerated output

Usage:
    python scripts/regen_diff_against_bug_corpus.py \\
        --bug-file /tmp/parth_full_with_fen.json \\
        --out /tmp/regen_diff.json
"""
from __future__ import annotations

import argparse
import asyncio
import json as json_lib
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


def _normalize_san(s: str) -> str:
    return (s or "").rstrip("!?+#").strip()


def _find_move_in_output(
    decryption_data: List[Dict],
    move_number: int,
    move_san: str,
) -> Optional[Dict]:
    """Locate the regenerated move record by (move_number, move_san)."""
    target = _normalize_san(move_san)
    for item in decryption_data:
        if item.get("move_number") != move_number:
            continue
        if _normalize_san(item.get("move_san") or "") == target:
            return item
    # Fallback: SAN match without move_number (some bug entries had
    # off-by-one move_number due to the export wrapping fullmove differently).
    for item in decryption_data:
        if _normalize_san(item.get("move_san") or "") == target:
            return item
    return None


def _classify(new_text: str, flagged: str) -> str:
    new_norm = (new_text or "").strip()
    flag_norm = (flagged or "").strip()
    if not new_norm:
        return "wiped"
    if new_norm == flag_norm:
        return "same"
    return "changed"


async def run(args):
    data = json_lib.loads(Path(args.bug_file).read_text(encoding="utf-8"))
    bugs = data.get("feedback") or []

    # Filter to lab-page bugs that have the data we need.
    lab_bugs = [
        b for b in bugs
        if b.get("page") == "lab"
        and (b.get("context") or {}).get("game_id")
        and (b.get("position") or {}).get("move_san")
    ]
    print(f"Loaded {len(bugs)} bugs total; {len(lab_bugs)} are lab-page with game_id+move.")

    by_game: Dict[str, List[Dict]] = defaultdict(list)
    for b in lab_bugs:
        gid = (b.get("context") or {}).get("game_id")
        by_game[gid].append(b)
    print(f"Spread across {len(by_game)} unique games.")

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Lazy import — service has heavy module-level setup.
    from services.game_decryption_v5_service import generate_game_decryption_v5

    results = []
    counts: Counter = Counter()

    for game_idx, (game_id, bug_list) in enumerate(by_game.items(), start=1):
        print(f"\n[{game_idx}/{len(by_game)}] game_id={game_id}  ({len(bug_list)} bug(s))")

        game = await db.games.find_one({"game_id": game_id}, {"_id": 0})
        if not game:
            print(f"  SKIP: game record not found")
            counts["skip_no_game"] += len(bug_list)
            continue
        analysis = await db.game_analyses.find_one({"game_id": game_id}, {"_id": 0})
        if not analysis:
            print(f"  SKIP: game_analyses record not found")
            counts["skip_no_analysis"] += len(bug_list)
            continue

        pgn = game.get("pgn") or ""
        user_color = (game.get("user_color") or "white").lower()
        user_id = game.get("user_id") or "unknown"
        sf = analysis.get("stockfish_analysis") or {}
        move_evaluations = sf.get("move_evaluations") or []
        if not pgn or not move_evaluations:
            print(f"  SKIP: missing pgn or move_evaluations")
            counts["skip_no_data"] += len(bug_list)
            continue

        print(f"  user_color={user_color}  pgn_len={len(pgn)}  evals={len(move_evaluations)}")
        try:
            decryption = await generate_game_decryption_v5(
                pgn=pgn,
                user_color=user_color,
                move_evaluations=move_evaluations,
                user_id=user_id,
                db=db,
            )
        except Exception as e:
            print(f"  FAIL: regeneration crashed: {e}")
            counts["regen_failed"] += len(bug_list)
            continue
        print(f"  regenerated {len(decryption)} move records")

        for bug in bug_list:
            pos = bug.get("position") or {}
            move_number = pos.get("move_number") or 0
            move_san = pos.get("move_san") or ""
            flagged = (bug.get("coaching_text_flagged") or "").strip()

            match = _find_move_in_output(decryption, move_number, move_san)
            if not match:
                counts["not_found"] += 1
                results.append({
                    "feedback_id": bug.get("feedback_id"),
                    "verdict": "not_found",
                    "move_number": move_number,
                    "move_san": move_san,
                    "flagged": flagged[:120],
                })
                continue

            # Compare against the most likely candidate fields. Lab
            # surface renders narrative + consequence as the main
            # coaching strings.
            new_narrative = (match.get("narrative") or "").strip()
            new_consequence = (match.get("consequence") or "").strip()
            # Pick the field that best matches the flagged text shape:
            # if the flagged starts with "After " it's likely a chain
            # claim — both narrative and consequence may carry it. Try
            # narrative first, then consequence.
            primary = new_narrative or new_consequence
            verdict = _classify(primary, flagged)
            counts[verdict] += 1
            results.append({
                "feedback_id": bug.get("feedback_id"),
                "verdict": verdict,
                "move_number": move_number,
                "move_san": move_san,
                "severity_stored": bug.get("severity"),
                "severity_new": match.get("severity"),
                "flagged": flagged[:200],
                "new_narrative": new_narrative[:200],
                "new_consequence": new_consequence[:200],
                "issue_summary": (bug.get("issue") or "")[:200],
            })

    client.close()

    # ── Report ──
    total_classified = sum(counts.values())
    print()
    print("=" * 70)
    print("REGEN-DIFF RESULTS")
    print("=" * 70)
    print(f"  total lab bugs classified:     {total_classified}")
    for k in ("wiped", "changed", "same", "not_found",
              "skip_no_game", "skip_no_analysis", "skip_no_data",
              "regen_failed"):
        if counts.get(k, 0):
            print(f"    {k:25s} {counts[k]}")
    print()

    # Print first few examples per verdict
    by_verdict: Dict[str, List[Dict]] = defaultdict(list)
    for r in results:
        by_verdict[r["verdict"]].append(r)

    for v in ("wiped", "changed", "same", "not_found"):
        items = by_verdict.get(v, [])
        if not items:
            continue
        print(f"--- {v.upper()} ({len(items)}) ---")
        for r in items[:5]:
            print(f"  {r['feedback_id']}  move {r['move_number']} {r['move_san']}")
            print(f"    flagged   : {r['flagged']}")
            if v != "not_found":
                print(f"    new_narr  : {r.get('new_narrative', '')}")
                if r.get("new_consequence"):
                    print(f"    new_conseq: {r['new_consequence']}")
                if r.get("severity_stored") != r.get("severity_new"):
                    print(f"    severity  : {r['severity_stored']} -> {r['severity_new']}")
        if len(items) > 5:
            print(f"    ... ({len(items) - 5} more)")
        print()

    if args.out:
        Path(args.out).write_text(
            json_lib.dumps(
                {
                    "summary": dict(counts),
                    "results": results,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"Full diff written to: {args.out}")

    print(
        "\nInterpretation:\n"
        "  wiped    = a guard (Cat 5 vacuous / Cat 2-3 hallucination /\n"
        "             Cat 8 chain) erased the field. User would see\n"
        "             empty surface, frontend falls back.\n"
        "  changed  = generation produced different text. Could be\n"
        "             Cat 1 severity reclassification routing to a\n"
        "             different template, or upstream cp_loss recompute\n"
        "             firing. Worth eyeballing for quality improvement.\n"
        "  same     = new generation produced byte-identical text. The\n"
        "             bug is not addressed by source-level fixes — it's\n"
        "             a content-quality complaint that needs a different\n"
        "             intervention.\n"
        "  not_found = couldn't locate the move in regenerated data\n"
        "              (likely because move was not user-side in current\n"
        "              user_color setting, or move_number drift).\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--bug-file", required=True)
    p.add_argument("--out", default="/tmp/regen_diff.json")
    asyncio.run(run(p.parse_args()))
