"""
Corpus-wide teaching-gold ranker.

Per [[surface-teaching-gold-proactively]] HARD rule: stop turning detector
output into counts and start turning it into ranked teaching moments.

Reads decryption_v5_data already present on game_analyses (no re-runs,
no Stockfish, no LLM — pure aggregation). For each move where a named
principle or shape pattern fired, classifies the fire by teaching role:

  GOLD        — fire on user's move with non-trivial cp_loss = user
                missed the lesson the principle teaches. Highest value.
  CELEBRATION — fire on user's move with cp_loss ≈ 0 = user nailed
                the principle.
  LUCKY       — fire on opponent's move with cp_loss > 0 = opponent
                missed it against user (could have hurt you).
  WARNING     — fire on opponent's move with cp_loss ≈ 0 = opponent
                executed the principle correctly against user (this
                is how they beat you).

Ranks gold entries by teaching value = cp_loss × principle_fame_weight,
where fame_weight favors named principles users can remember.

Usage:
  MONGO_URL=... docker exec -i chess-coach-backend python \
    scripts/rank_teaching_gold.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from pymongo import MongoClient

# Principles that have strong "name recognition" for 1200-1500 players —
# these score higher in the ranker because they're easier to teach back.
NAMED_PRINCIPLE_BOOST = {
    "END_RULE_OF_SQUARE": 2.0,
    "END_OPPOSITION": 1.8,
    "END_ROOK_BEHIND_PASSER": 1.8,
    "END_PASSED_PAWN_KING_ACTIVE": 1.5,
    "END_ACTIVE_KING": 1.3,
    "TAC_PIN_PATTERN": 1.7,
    "TAC_FORK_PATTERN": 1.7,
    "TAC_DISCOVERED_PATTERN": 1.6,
    "TAC_SKEWER_PATTERN": 1.5,
    "OP_BISHOP_TRADE_DOUBLES_PAWN": 1.4,
    "OP_F2_F7_STRIKE": 1.6,
    "OP_TRAPPED_KNIGHT": 1.4,
    "DEF_WALK_KING": 1.0,
}

MIN_USER_MISS_CP_LOSS = 80   # below this, "user missed" is too soft to be teachable
MIN_OPP_MISS_CP_LOSS = 150   # opponent misses need bigger swing to count as lucky
MAX_TEACHABLE_CP_LOSS = 2000  # filter mate-score artifacts (real blunders rarely > ~1500cp)
TOP_N_OVERALL = 30
TOP_N_PER_PRINCIPLE = 5


def fame(principle_id: str | None) -> float:
    if not principle_id:
        return 0.8  # shape pattern only, no named principle
    return NAMED_PRINCIPLE_BOOST.get(principle_id, 1.0)


def main():
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("ERROR: MONGO_URL required", file=sys.stderr)
        sys.exit(1)

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    # Map game_id → user_color + opponent + result for classification
    game_meta = {}
    for g in db.games.find({}, {"_id": 0, "game_id": 1, "user_color": 1, "opponent_username": 1, "result": 1, "user_id": 1}):
        game_meta[g["game_id"]] = g

    print(f"Loaded {len(game_meta)} games. Scanning V5 fires…", file=sys.stderr)

    gold = []        # user missed
    celebration = []  # user nailed
    lucky = []       # opponent missed against user
    warning = []     # opponent landed it on user
    by_principle: dict[str, dict[str, list]] = defaultdict(lambda: {
        "gold": [], "celebration": [], "lucky": [], "warning": []
    })

    total_v5_games = 0
    total_fires = 0

    cursor = db.game_analyses.find(
        {"decryption_v5_data": {"$exists": True, "$ne": None, "$type": "array"}},
        {"_id": 0, "game_id": 1, "user_id": 1, "decryption_v5_data": 1},
    )

    for a in cursor:
        gid = a.get("game_id")
        meta = game_meta.get(gid, {})
        user_color = meta.get("user_color")
        if user_color not in ("white", "black"):
            continue
        total_v5_games += 1

        for m in a.get("decryption_v5_data", []):
            principle_id = m.get("principle_id_used") or m.get("principle_id")
            shape_id = m.get("shape_pattern_id")
            if not principle_id and not shape_id:
                continue

            total_fires += 1
            is_user_move = m.get("is_user_move")
            cp_loss = m.get("cp_loss") or 0
            move_san = m.get("move_san") or ""
            best_move_san = m.get("best_move_san") or ""
            # If the user played the best move, it's celebration regardless of
            # cp_loss (mate-score artifacts produce bogus -19990 values).
            played_best = (move_san == best_move_san) or "#" in move_san
            if cp_loss > MAX_TEACHABLE_CP_LOSS:
                # Mate-score artifact — treat as 0 cp_loss
                cp_loss = 0

            entry = {
                "game_id": gid,
                "user_id": a.get("user_id") or meta.get("user_id"),
                "move_number": m.get("move_number"),
                "move_san": m.get("move_san"),
                "is_user_move": is_user_move,
                "principle_id": principle_id,
                "shape_pattern_id": shape_id,
                "cp_loss": cp_loss,
                "best_move_san": m.get("best_move_san"),
                "fen_before": m.get("fen_before"),
                "narrative": (m.get("narrative") or "")[:200],
                "phase": m.get("phase"),
                "opponent": meta.get("opponent_username"),
                "result": meta.get("result"),
                "user_color": user_color,
                "score": cp_loss * fame(principle_id),
            }

            pkey = principle_id or f"SHAPE:{shape_id}"

            if is_user_move:
                if not played_best and cp_loss >= MIN_USER_MISS_CP_LOSS:
                    gold.append(entry)
                    by_principle[pkey]["gold"].append(entry)
                else:
                    celebration.append(entry)
                    by_principle[pkey]["celebration"].append(entry)
            else:
                if not played_best and cp_loss >= MIN_OPP_MISS_CP_LOSS:
                    lucky.append(entry)
                    by_principle[pkey]["lucky"].append(entry)
                else:
                    warning.append(entry)
                    by_principle[pkey]["warning"].append(entry)

    # Sort gold by teaching score descending
    gold.sort(key=lambda e: e["score"], reverse=True)
    lucky.sort(key=lambda e: e["score"], reverse=True)

    # Per-principle top picks
    per_principle_summary = {}
    for pkey, buckets in by_principle.items():
        per_principle_summary[pkey] = {
            "fire_count": sum(len(v) for v in buckets.values()),
            "gold_count": len(buckets["gold"]),
            "lucky_count": len(buckets["lucky"]),
            "top_gold": sorted(buckets["gold"], key=lambda e: e["score"], reverse=True)[:TOP_N_PER_PRINCIPLE],
            "top_lucky": sorted(buckets["lucky"], key=lambda e: e["score"], reverse=True)[:TOP_N_PER_PRINCIPLE],
        }

    out = {
        "totals": {
            "v5_games_scanned": total_v5_games,
            "total_fires": total_fires,
            "gold": len(gold),
            "celebration": len(celebration),
            "lucky": len(lucky),
            "warning": len(warning),
        },
        "top_overall_gold": gold[:TOP_N_OVERALL],
        "top_overall_lucky": lucky[:TOP_N_OVERALL],
        "per_principle": per_principle_summary,
    }

    out_path = Path(os.environ.get("GOLD_OUTPUT", "/tmp/teaching_gold_ranked.json"))
    out_path.write_text(json.dumps(out, indent=2, default=str))

    # Stdout summary
    print(f"\n=== TEACHING-GOLD CORPUS SCAN ===")
    print(f"V5 games scanned: {total_v5_games}")
    print(f"Total named-rule + shape fires: {total_fires}")
    print(f"  GOLD (user missed):        {len(gold)}")
    print(f"  CELEBRATION (user nailed): {len(celebration)}")
    print(f"  LUCKY (opp missed vs you): {len(lucky)}")
    print(f"  WARNING (opp landed):      {len(warning)}")

    print(f"\n=== TOP 10 GOLD MOMENTS (user missed) ===")
    for i, e in enumerate(gold[:10], 1):
        pid = e["principle_id"] or f"shape:{e['shape_pattern_id']}"
        print(f"  {i:2}. game {e['game_id'][:12]} move {e['move_number']} played {e['move_san']} (best: {e['best_move_san']}, -{e['cp_loss']}cp) [{pid}] score={e['score']:.0f}")

    print(f"\n=== PER-PRINCIPLE FIRE COUNTS ===")
    sorted_principles = sorted(per_principle_summary.items(), key=lambda x: x[1]["fire_count"], reverse=True)
    for pkey, s in sorted_principles[:20]:
        print(f"  {pkey:<35} fires={s['fire_count']:>4}  gold={s['gold_count']:>3}  lucky={s['lucky_count']:>3}")

    print(f"\nFull report: {out_path}")


if __name__ == "__main__":
    main()
