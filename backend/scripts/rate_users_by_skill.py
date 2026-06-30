"""
Rate every >20-game user across the 7 chess-coach skill dimensions.

Pulls from the freshly-backfilled player_profiles.top_weaknesses (which
now uses 9 cognitive_gap categories) + average_accuracy + improvement_trend.

For each skill dimension we compute a rate-per-game and map to a 4-tier
label: STRONG / SOLID / WEAK / MISSING. Higher counts of a weakness =
worse in that area.

Output: /tmp/skill_ratings.json + a printed markdown table.
"""
import asyncio, json, os
from collections import Counter
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient


# Each skill dimension is the sum of certain cognitive_gap subcategories.
# Lower = better.
SKILL_MAP = {
    "Basics (piece safety)":     ["one_move_blunders"],
    "Tactics":                   ["fork_misses", "discovered_attack_misses", "removal_of_defender_misses"],
    "King safety":               ["ignoring_king_safety_threats"],
    "Openings":                  ["neglecting_development"],
    "Middlegame":                ["poor_piece_activity", "pawn_structure_damage"],
    "Endgame":                   ["king_activity_neglect"],
    "Calc depth":                ["complex_tactical_miss"],  # legacy bucket if present
}

# rate-per-game thresholds → label
def rate_to_label(per_game: float, threshold: dict) -> str:
    if per_game < threshold["strong"]:   return "STRONG"
    if per_game < threshold["solid"]:    return "SOLID"
    if per_game < threshold["weak"]:     return "WEAK"
    return "MISSING"

# Same thresholds across all skills for simplicity (per-game rate)
THRESH = {"strong": 0.5, "solid": 1.5, "weak": 3.0}

# Accuracy → label
def acc_to_label(a):
    if a is None: return "?"
    if a >= 70: return "STRONG"
    if a >= 60: return "SOLID"
    if a >= 50: return "WEAK"
    return "MISSING"


async def main():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ.get("DB_NAME", "chess_coach")]

    # Cohort: >= 20 games
    pipeline = [
        {"$match": {"is_analyzed": True}},
        {"$group": {"_id": "$user_id", "n": {"$sum": 1}}},
        {"$match": {"n": {"$gte": 20}}},
        {"$sort": {"n": -1}},
    ]
    uids = [r["_id"] async for r in db.games.aggregate(pipeline)]

    rows = []
    for uid in uids:
        user = await db.users.find_one({"user_id": uid}, {"_id": 0, "name": 1, "email": 1}) or {}
        profile = await db.player_profiles.find_one({"user_id": uid}, {"_id": 0}) or {}
        identity = await db.player_identities.find_one({"user_id": uid}, {"_id": 0}) or {}
        games_analyzed = profile.get("games_analyzed_count") or 0
        if games_analyzed < 20:
            # Fallback to actual analyzed count
            games_analyzed = await db.games.count_documents({"user_id": uid, "is_analyzed": True})
        if games_analyzed == 0: continue

        # Weakness lookup: subcategory → count
        ws = {w["subcategory"]: w.get("occurrence_count", 0) for w in (profile.get("top_weaknesses") or [])}

        # Per-skill rate + label
        ratings = {}
        rates = {}
        for skill, subs in SKILL_MAP.items():
            total = sum(ws.get(s, 0) for s in subs)
            per_game = total / max(games_analyzed, 1)
            rates[skill] = round(per_game, 2)
            ratings[skill] = rate_to_label(per_game, THRESH)

        avg_acc = profile.get("average_accuracy")
        acc_label = acc_to_label(avg_acc)

        # Overall: count STRONG/SOLID vs WEAK/MISSING
        labels = list(ratings.values()) + [acc_label]
        strong = sum(1 for l in labels if l == "STRONG")
        solid = sum(1 for l in labels if l == "SOLID")
        weak = sum(1 for l in labels if l == "WEAK")
        missing = sum(1 for l in labels if l == "MISSING")
        # Map to overall coach grade
        if strong >= 4: overall = "ADVANCED"
        elif strong + solid >= 5: overall = "INTERMEDIATE"
        elif weak + missing >= 4: overall = "BEGINNER"
        else: overall = "DEVELOPING"

        # Style summary
        style = identity.get("style_profile") or {}
        agg = style.get("aggressive_tendency", 0.5)
        pos = style.get("positional_tendency", 0.5)
        style_label = (
            "aggressive" if agg >= 0.65 else
            "balanced" if 0.4 < agg < 0.65 else
            "cautious"
        ) + " · " + (
            "positional" if pos >= 0.6 else
            "tactical" if pos <= 0.4 else
            "mixed"
        )

        rows.append({
            "user_id": uid,
            "name": user.get("name") or "?",
            "email": user.get("email") or "?",
            "games": games_analyzed,
            "accuracy": avg_acc,
            "accuracy_label": acc_label,
            "trend": profile.get("improvement_trend") or "?",
            "ratings": ratings,
            "rates": rates,
            "overall": overall,
            "style": style_label,
        })

    # ----- PERCENTILE-BASED RATINGS (replaces absolute thresholds) -----
    # For each skill, rank users by per-game rate. Top 20% = STRONG (lowest
    # rate of that mistake), 20-50% = SOLID, 50-80% = WEAK, bottom 20% = MISSING.
    # Guarantees differentiation across the cohort instead of everyone clumping
    # into "SOLID" when the absolute thresholds happen to be lax.
    def percentile_label(rank: int, total: int) -> str:
        pct = rank / max(total - 1, 1)
        if pct <= 0.20: return "STRONG"
        if pct <= 0.50: return "SOLID"
        if pct <= 0.80: return "WEAK"
        return "MISSING"

    for skill in SKILL_MAP.keys():
        rates = sorted(((r["rates"][skill], r) for r in rows), key=lambda x: x[0])
        for rank, (_, r) in enumerate(rates):
            r["ratings"][skill] = percentile_label(rank, len(rates))

    # Accuracy: same percentile treatment (high = good, so invert)
    acc_rows = [(r.get("accuracy") or 0.0, r) for r in rows]
    acc_rows.sort(key=lambda x: -x[0])  # highest accuracy first
    for rank, (_, r) in enumerate(acc_rows):
        r["accuracy_label"] = percentile_label(rank, len(acc_rows))

    # Recompute overall (now meaningful)
    for r in rows:
        labels = list(r["ratings"].values()) + [r["accuracy_label"]]
        strong = sum(1 for l in labels if l == "STRONG")
        solid = sum(1 for l in labels if l == "SOLID")
        weak = sum(1 for l in labels if l == "WEAK")
        missing = sum(1 for l in labels if l == "MISSING")
        if strong >= 4: r["overall"] = "ADVANCED"
        elif strong + solid >= 5: r["overall"] = "INTERMEDIATE"
        elif missing >= 3: r["overall"] = "BEGINNER"
        elif weak >= 4: r["overall"] = "DEVELOPING"
        else: r["overall"] = "MIXED"

    # Sort by games desc
    rows.sort(key=lambda r: -r["games"])

    out_path = "/tmp/skill_ratings.json"
    with open(out_path, "w") as f:
        json.dump(rows, f, default=str, indent=2)
    print(f"Wrote {len(rows)} skill profiles to {out_path}")

    # Print markdown table
    print()
    print("| # | Name | Games | Overall | Acc | Basics | Tactics | KingSafe | Openings | Middlegame | Endgame | Trend | Style |")
    print("|--:|------|------:|:--------|----:|:------|:--------|:---------|:---------|:-----------|:--------|:------|:------|")
    for i, r in enumerate(rows, 1):
        rt = r["ratings"]
        print(f"| {i} | {r['name'][:24]} | {r['games']} | **{r['overall']}** | {r['accuracy']}% {r['accuracy_label'][:1]} | {rt['Basics (piece safety)']} | {rt['Tactics']} | {rt['King safety']} | {rt['Openings']} | {rt['Middlegame']} | {rt['Endgame']} | {r['trend']} | {r['style']} |")


if __name__ == "__main__":
    asyncio.run(main())
