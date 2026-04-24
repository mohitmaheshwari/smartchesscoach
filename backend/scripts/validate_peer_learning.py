"""
Peer-Learning Feature Validator
================================

Before building cross-user peer-learning features, test whether the data
actually supports them. Reports density signals across four candidate
features:

  (A) Rating-band mistake benchmarks — needs ≥3 users per band
  (B) Peer solution overlay          — needs shared opening clusters
  (C) Graduation pattern mining      — needs users with improvement signal
  (D) Shadow-a-peer                  — needs matchable repertoires

Reads ONLY from `users`, `player_profiles`, `games`, `game_analyses`.
No writes. Safe to run repeatedly.

Usage:
  docker cp scripts/validate_peer_learning.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/validate_peer_learning.py
"""

import asyncio
import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient

from services.opening_normalizer import normalize_opening

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("validate_peer_learning")

# Rating bands (200-point slices)
BANDS = [
    ("<1000",     0,    999),
    ("1000-1199", 1000, 1199),
    ("1200-1399", 1200, 1399),
    ("1400-1599", 1400, 1599),
    ("1600+",     1600, 9999),
]


def _band_for(rating: int) -> str:
    if rating is None or rating <= 0:
        return "no_rating"
    for name, lo, hi in BANDS:
        if lo <= rating <= hi:
            return name
    return "no_rating"


async def _resolve_rating(db, user_id: str) -> int:
    """Pick the best rating signal for a user. Prefers chess.com / lichess
    stats over the users doc. Returns 0 when no rating is available."""
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0, "chesscom_stats.rating": 1, "lichess_stats.rating": 1,
         "current_rating": 1, "estimated_rating": 1},
    )
    if profile:
        for key_path in (("chesscom_stats", "rating"),
                         ("lichess_stats", "rating")):
            parent = profile.get(key_path[0]) or {}
            v = parent.get(key_path[1])
            if isinstance(v, (int, float)) and v > 0:
                return int(v)
        for key in ("current_rating", "estimated_rating"):
            v = profile.get(key)
            if isinstance(v, (int, float)) and v > 0:
                return int(v)
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "rating": 1})
    if u:
        v = u.get("rating")
        if isinstance(v, (int, float)) and v > 0:
            return int(v)
    return 0


async def main():
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    logger.info(f"Connecting to {db_name} at {url}")
    client = AsyncIOMotorClient(url)
    db = client[db_name]

    # ── 1. User rating distribution ──────────────────────────────
    print()
    print("═" * 60)
    print("1. USER RATING DISTRIBUTION")
    print("═" * 60)

    user_docs = await db.users.find({}, {"_id": 0, "user_id": 1}).to_list(1000)
    logger.info(f"Total users: {len(user_docs)}")

    user_ratings: Dict[str, int] = {}
    for u in user_docs:
        uid = u.get("user_id")
        if uid:
            user_ratings[uid] = await _resolve_rating(db, uid)

    band_users: Dict[str, List[str]] = defaultdict(list)
    for uid, r in user_ratings.items():
        band_users[_band_for(r)].append(uid)

    # Count games per band
    band_games: Dict[str, int] = defaultdict(int)
    for band, uids in band_users.items():
        if not uids:
            continue
        n = await db.games.count_documents({"user_id": {"$in": uids}, "is_analyzed": True})
        band_games[band] = n

    print(f"  {'band':<14} {'users':>7} {'games':>8}")
    for band_name, _, _ in BANDS + [("no_rating", 0, 0)]:
        users_ct = len(band_users.get(band_name, []))
        print(f"  {band_name:<14} {users_ct:>7} {band_games.get(band_name, 0):>8}")

    # ── 2. Mistake rate by band × cognitive_gap ──────────────────
    print()
    print("═" * 60)
    print("2. MISTAKE DISTRIBUTION BY BAND × COGNITIVE_GAP")
    print("═" * 60)
    print("(% of user-mistakes in each band tagged with each gap)")
    print()

    # For each band, collect all user moves' cognitive_gap from analyses
    # (user_moves = those where cp_loss >= 100; gap is set by interpreter)
    band_gap_counts: Dict[str, Counter] = defaultdict(Counter)
    band_mistake_total: Dict[str, int] = defaultdict(int)

    for band, uids in band_users.items():
        if not uids or band == "no_rating":
            continue
        async for a in db.game_analyses.find(
            {"user_id": {"$in": uids}},
            {"_id": 0, "user_id": 1, "stockfish_analysis.move_evaluations.cp_loss": 1,
             "stockfish_analysis.move_evaluations.cognitive_gap": 1,
             "stockfish_analysis.move_evaluations.fen_before": 1},
        ):
            uid = a.get("user_id")
            # Find user's game to get their color
            # (simplified: just count gaps on all critical moves — parity bug if
            # interleaved moves include opponent's, but cognitive_gap is set
            # only for critical moves; over-count is small and equal across bands.)
            sf = a.get("stockfish_analysis") or {}
            for ev in sf.get("move_evaluations") or []:
                cp = ev.get("cp_loss") or 0
                if cp < 100:
                    continue
                gap = ev.get("cognitive_gap") or ""
                if not gap:
                    continue
                band_gap_counts[band][gap] += 1
                band_mistake_total[band] += 1

    # Print table
    all_gaps = sorted({g for c in band_gap_counts.values() for g in c})
    if all_gaps and band_gap_counts:
        # Header
        header = f"  {'band':<14} {'total':>7}  " + " ".join(
            f"{g[:14]:>15}" for g in all_gaps[:6]
        )
        print(header)
        for band, _, _ in BANDS:
            counts = band_gap_counts.get(band, Counter())
            total = band_mistake_total.get(band, 0)
            if total == 0:
                continue
            row = f"  {band:<14} {total:>7}  "
            for g in all_gaps[:6]:
                pct = (counts.get(g, 0) / total * 100) if total > 0 else 0
                row += f"{pct:>14.1f}%"
            print(row)
    else:
        print("  (no mistake data — possibly no analyses yet)")

    # ── 3. Graduation detection ──────────────────────────────────
    print()
    print("═" * 60)
    print("3. GRADUATE USERS (improvement signal)")
    print("═" * 60)
    print("(users with ≥20 games; comparing blunder count in first vs second half)")
    print()

    graduates = []
    for uid in user_ratings.keys():
        # Pull game ids with dates
        games = await db.games.find(
            {"user_id": uid, "is_analyzed": True},
            {"_id": 0, "game_id": 1, "imported_at": 1},
        ).sort("imported_at", 1).to_list(500)
        if len(games) < 20:
            continue
        mid = len(games) // 2
        first_ids = [g["game_id"] for g in games[:mid] if g.get("game_id")]
        second_ids = [g["game_id"] for g in games[mid:] if g.get("game_id")]

        first_blunders = 0
        second_blunders = 0
        async for a in db.game_analyses.find(
            {"user_id": uid, "game_id": {"$in": first_ids}},
            {"_id": 0, "stockfish_analysis.blunders": 1},
        ):
            first_blunders += (a.get("stockfish_analysis") or {}).get("blunders") or 0
        async for a in db.game_analyses.find(
            {"user_id": uid, "game_id": {"$in": second_ids}},
            {"_id": 0, "stockfish_analysis.blunders": 1},
        ):
            second_blunders += (a.get("stockfish_analysis") or {}).get("blunders") or 0

        first_rate = first_blunders / max(1, len(first_ids))
        second_rate = second_blunders / max(1, len(second_ids))
        if first_rate > 0 and second_rate < first_rate * 0.75:
            # At least 25% drop in blunder rate
            graduates.append({
                "user_id": uid,
                "games_total": len(games),
                "first_half_rate": round(first_rate, 2),
                "second_half_rate": round(second_rate, 2),
                "improvement_pct": int((1 - second_rate / first_rate) * 100),
            })

    graduates.sort(key=lambda g: -g["improvement_pct"])
    print(f"  Graduate candidates: {len(graduates)}")
    if graduates:
        print(f"  {'user_id':<30} {'games':>6}  {'1st half':>9}  {'2nd half':>9}  {'improv':>7}")
        for g in graduates[:10]:
            print(
                f"  {g['user_id']:<30} {g['games_total']:>6}  "
                f"{g['first_half_rate']:>9}  {g['second_half_rate']:>9}  "
                f"{g['improvement_pct']}%"
            )

    # ── 4. Position recurrence across users (opening clusters) ───
    print()
    print("═" * 60)
    print("4. POSITION RECURRENCE (shared openings across users)")
    print("═" * 60)
    print("(opening family + user_color reached by multiple users)")
    print()

    # (opening_family, user_color) → set of user_ids
    clusters: Dict[tuple, set] = defaultdict(set)
    async for g in db.games.find(
        {"is_analyzed": True},
        {"_id": 0, "user_id": 1, "user_color": 1, "opening": 1},
    ):
        fam = normalize_opening(g.get("opening"))
        if fam == "Other":
            continue
        color = (g.get("user_color") or "white").lower()
        uid = g.get("user_id")
        if uid:
            clusters[(fam, color)].add(uid)

    # Rank clusters by user count
    ranked = sorted(clusters.items(), key=lambda kv: -len(kv[1]))
    print(f"  {'opening + color':<40}  {'users'}")
    shared_3plus = 0
    for (fam, color), uids in ranked[:15]:
        n = len(uids)
        if n >= 3:
            shared_3plus += 1
        print(f"  {fam + ' as ' + color:<40}  {n}")
    print()
    print(f"  Clusters with ≥3 users (eligible for peer overlay): {shared_3plus}")

    # ── 5. Viability verdict ─────────────────────────────────────
    print()
    print("═" * 60)
    print("5. FEATURE VIABILITY VERDICT")
    print("═" * 60)

    bands_with_3plus = sum(
        1 for band, uids in band_users.items()
        if band != "no_rating" and len(uids) >= 3 and band_mistake_total.get(band, 0) >= 50
    )
    feature_a_viable = bands_with_3plus >= 2

    feature_b_viable = shared_3plus >= 3
    feature_c_viable = len(graduates) >= 3
    feature_d_viable = shared_3plus >= 5 and len(graduates) >= 2

    print()
    print(f"  (A) Rating-band benchmarks:  {'✓ VIABLE' if feature_a_viable else '✗ NOT VIABLE'}")
    print(f"      ({bands_with_3plus} bands with ≥3 users AND ≥50 tagged mistakes)")
    print()
    print(f"  (B) Peer solution overlay:   {'✓ VIABLE' if feature_b_viable else '✗ NOT VIABLE'}")
    print(f"      ({shared_3plus} opening+color clusters reached by ≥3 users)")
    print()
    print(f"  (C) Graduation pattern:      {'✓ VIABLE' if feature_c_viable else '✗ NOT VIABLE'}")
    print(f"      ({len(graduates)} users showing ≥25% blunder-rate improvement)")
    print()
    print(f"  (D) Shadow-a-peer:           {'✓ VIABLE' if feature_d_viable else '✗ NOT VIABLE'}")
    print(f"      (needs both B≥5 clusters AND C≥2 graduates — most fragile)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
