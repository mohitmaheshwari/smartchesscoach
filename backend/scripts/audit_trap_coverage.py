"""Audit trap-coverage by opening in the 500-game corpus.

Two questions:
  1. Which opening families appear in the corpus that have NO trap entries
     in `traps.json` at all? Those are candidates for trap authoring.
  2. Of the existing traps, which ones are FIRING in real games? (trap_fires
     field). Low-fire-rate traps may be either rare or mis-configured.

Run inside container:
    python /app/backend/scripts/audit_trap_coverage.py --out /tmp/trap_coverage.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter, defaultdict

from motor.motor_asyncio import AsyncIOMotorClient


_TRAPS_JSON = "/app/backend/data/traps.json"


def _normalize_opening_label(label: str) -> str:
    """Map raw Chess.com/Lichess opening labels to traps.json opening keys
    (lowercase, hyphenated families)."""
    s = (label or "").lower()
    pairs = [
        ("italian", "italian-game"),
        ("giuoco", "italian-game"),
        ("sicilian", "sicilian-defense"),
        ("queen's gambit", "queens-gambit"),
        ("queens gambit", "queens-gambit"),
        ("london", "london-system"),
        ("caro-kann", "caro-kann"),
        ("caro kann", "caro-kann"),
        ("king's indian", "kings-indian-defense"),
        ("kings indian", "kings-indian-defense"),
        ("scandinavian", "scandinavian-defense"),
        ("ruy lopez", "ruy-lopez"),
        ("ruy-lopez", "ruy-lopez"),
        ("spanish", "ruy-lopez"),
        ("philidor", "philidor-defense"),
        ("petrov", "petrov-defense"),
        ("petroff", "petrov-defense"),
        ("budapest", "budapest-gambit"),
        ("dutch", "dutch-defense"),
        ("french", "french-defense"),
        ("slav", "slav-defense"),
        ("nimzo-indian", "nimzo-indian"),
        ("nimzo indian", "nimzo-indian"),
        ("vienna", "vienna-game"),
        ("queen's indian", "queens-indian"),
        ("queens indian", "queens-indian"),
        ("grunfeld", "grunfeld-defense"),
        ("benoni", "benoni-defense"),
        ("blackmar-diemer", "blackmar-diemer-gambit"),
        ("blackmar diemer", "blackmar-diemer-gambit"),
        ("tennison", "tennison-gambit"),
        ("bogo-indian", "bogo-indian"),
        ("bogo indian", "bogo-indian"),
        ("king's gambit", "kings-gambit"),
        ("kings gambit", "kings-gambit"),
        ("scotch", "scotch"),
    ]
    for needle, key in pairs:
        if needle in s:
            return key
    return s.replace(" ", "-")


async def main_async(out_path: str, max_games: int):
    url = os.environ.get(
        "MONGO_URL",
        "mongodb://admin_user_mii_s_c:Mii123$44$@host.docker.internal:27018/?authSource=admin",
    )
    db = AsyncIOMotorClient(url)["chess_coach"]

    with open(_TRAPS_JSON, "r", encoding="utf-8") as f:
        traps = json.load(f)
    covered_families = set(traps.keys())
    print(f"traps.json covers {len(covered_families)} opening families")

    opening_counts: Counter = Counter()
    raw_to_norm: dict[str, str] = {}
    fire_counts: Counter = Counter()
    fire_examples: dict[str, list[str]] = defaultdict(list)

    n = 0
    async for ga in db.game_analyses.find(
        {"decryption_v5_data": {"$exists": True}, "decryption_v5_version": {"$gte": 53}}
    ).sort("created_at", -1).limit(max_games):
        n += 1
        gid = ga.get("game_id", "")
        g = await db.games.find_one({"game_id": gid}, {"_id": 0, "opening": 1})
        if not g:
            continue
        op = g.get("opening") or "Unknown"
        norm = _normalize_opening_label(op)
        raw_to_norm[op] = norm
        opening_counts[op] += 1
        for f in (ga.get("trap_fires") or []):
            if isinstance(f, dict):
                tn = f.get("trap_name", "?")
                fire_counts[tn] += 1
                fire_examples[tn].append(gid[:8])

    # By normalized family
    fam_counts: Counter = Counter()
    fam_raw_labels: dict[str, set[str]] = defaultdict(set)
    for raw, c in opening_counts.items():
        fam = raw_to_norm.get(raw, raw.lower().replace(" ", "-"))
        fam_counts[fam] += c
        fam_raw_labels[fam].add(raw)

    uncovered_families = [(fam, c) for fam, c in fam_counts.most_common()
                          if fam not in covered_families]

    # Build MD
    lines = ["# Trap-coverage audit — 500-game corpus\n"]
    lines.append(f"Scanned {n} games (v53+).\n")
    lines.append(f"`traps.json` currently covers **{len(covered_families)} opening families** "
                 f"with **{sum(len(v) for v in traps.values())} total trap entries**.\n")
    lines.append(f"Corpus contained **{len(opening_counts)} distinct opening labels** "
                 f"(normalized to **{len(fam_counts)} families**).\n")

    # === Section 1: uncovered families that appear frequently ===
    lines.append("## 1. Opening families in corpus with NO trap entries\n")
    lines.append("These are the corpus-frequent families that have zero `traps.json` coverage. "
                 "High-frequency entries here are the most likely candidates for adding traps.\n")
    lines.append("| Family (normalized) | Games in corpus | Raw labels seen |")
    lines.append("|---|---:|---|")
    for fam, c in uncovered_families[:25]:
        raws = list(fam_raw_labels[fam])[:3]
        raws_str = ", ".join(f"`{r}`" for r in raws)
        if len(fam_raw_labels[fam]) > 3:
            raws_str += f" +{len(fam_raw_labels[fam]) - 3} more"
        lines.append(f"| `{fam}` | {c} | {raws_str} |")
    lines.append("")

    # === Section 2: existing trap fire rate ===
    lines.append("## 2. Existing trap fire rate in 500-game corpus\n")
    lines.append("Which existing traps in `traps.json` are actually firing in real games?\n")
    lines.append("| Trap name | Fires in 500 games |")
    lines.append("|---|---:|")
    all_traps = [(t["name"], op) for op, tlist in traps.items() for t in tlist]
    fire_count_map = dict(fire_counts)
    for name, op in all_traps:
        cnt = fire_count_map.get(name, 0)
        lines.append(f"| **{name}** ({op}) | {cnt} |")
    lines.append("")

    lines.append("## 3. Honest assessment\n")
    lines.append("- The pattern-clustering analysis (`find_trap_candidates.py`) "
                 "found only 4 multi-game clusters across 1066 early blunders. On inspection most are "
                 "either single-position calculation errors or false-positive groupings of different blunders. "
                 "The existing 39 traps appear to cover the recurring named-trap patterns in this 500-game "
                 "corpus.")
    lines.append("- Coverage gaps (Section 1 above) are the more actionable list — opening families that "
                 "appear in real games but have zero trap entries. Mohit to judge which deserve authoring.")
    lines.append("- Low-fire traps (Section 2 with 0 fires) may still be valid — just rare in this "
                 "particular corpus. Don't delete on small-sample evidence.")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {out_path}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--max-games", type=int, default=500)
    args = p.parse_args()
    asyncio.run(main_async(args.out, args.max_games))


if __name__ == "__main__":
    main()
