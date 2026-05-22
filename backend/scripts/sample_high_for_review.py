"""Sample HIGH-tier captions across major rule files for pedagogical review.

The mechanical verifier confirms 0 hallucinations at v55. But that's the
correctness floor, not the pedagogy ceiling. This script samples HIGH-tier
captions stratified across rule files + caption-prefix clusters so Mohit
can spot-check pedagogical quality (is the lesson well-framed? is the voice
right? does it teach what the player needed to learn?).

Stratification:
- Per rule file: group captions by their first 60 chars (a proxy for the
  template variant that fired).
- Pick the top 4-6 most-common prefix clusters per file.
- Sample 1 representative per cluster.

Default target: ~25-30 total captions for review.

Run inside container:
    python /app/backend/scripts/sample_high_for_review.py \\
        --out /tmp/high_review.md
"""
from __future__ import annotations

import argparse
import asyncio
import os
from collections import Counter, defaultdict
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient


# Rules to sample. Each entry: (rule_substring_match, per_file_samples, label).
# rule_name in mongo can be compound (e.g. "R_FALLBACK_no_primary→R_PROMOTED_principle:OP_X"),
# so we match by substring.
RULE_TARGETS = [
    ("R12_blunder", 8, "Mistake/blunder captions (largest surface)"),
    ("R_PROMOTED_principle", 5, "Opening-principle captions"),
    ("R_PROMOTED_shape", 5, "Board-state shape captions"),
    ("R01_mate", 4, "Mate-threat captions"),
    ("R_PROMOTED_opening", 4, "Curriculum-walker (opening theory) captions"),
    ("R_PROMOTED_trap_defense", 2, "Trap-defense captions"),
    ("R_PROMOTED_basic_mistake", 2, "Basic-mistake fallback captions"),
]


def _rule_matches(actual: str, target: str) -> bool:
    return target in (actual or "")


def _caption_prefix_60(s: str) -> str:
    s = (s or "").strip()
    return s[:60]


async def main_async(out_path: str):
    url = os.environ.get(
        "MONGO_URL",
        "mongodb://admin_user_mii_s_c:Mii123$44$@host.docker.internal:27018/?authSource=admin",
    )
    db = AsyncIOMotorClient(url)["chess_coach"]

    # Group ALL HIGH captions by (rule_name, prefix60), keeping a few examples
    # per cluster.
    clusters: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    n_games = 0
    async for ga in db.game_analyses.find(
        {"decryption_v5_data": {"$exists": True}, "decryption_v5_version": {"$gte": 55}}
    ).sort("created_at", -1).limit(500):
        n_games += 1
        gid = ga.get("game_id", "")
        gd = await db.games.find_one({"game_id": gid}, {"_id": 0, "user_color": 1, "opening": 1})
        user_color = (gd or {}).get("user_color", "")
        opening = (gd or {}).get("opening", "")

        for m in (ga.get("decryption_v5_data") or []):
            if not m.get("is_user_move"):
                continue
            cap = m.get("caption") or ""
            rule = m.get("rule_name") or ""
            if not cap or not rule:
                continue

            # Map actual rule to canonical bucket (first matching target wins)
            bucket = None
            for tgt, _, _ in RULE_TARGETS:
                if _rule_matches(rule, tgt):
                    bucket = tgt
                    break
            if bucket is None:
                continue

            prefix = _caption_prefix_60(cap)
            key = (bucket, prefix)
            # Keep at most 5 examples per cluster to choose a representative from
            if len(clusters[key]) < 5:
                clusters[key].append({
                    "caption": cap,
                    "rule": rule,
                    "fen": m.get("fen_before", ""),
                    "move_san": m.get("move_san", ""),
                    "best_san": m.get("best_move_san", ""),
                    "cp_loss": m.get("cp_loss"),
                    "move_number": m.get("move_number"),
                    "game_id": gid,
                    "user_color": user_color,
                    "opening": opening,
                    "concept_id": m.get("concept_id"),
                    "shape_pattern_name": m.get("shape_pattern_name"),
                })

    print(f"Scanned {n_games} v55 games; {len(clusters)} (rule, prefix) clusters total")

    # Aggregate per-rule prefix counts (need full cluster sizes for sorting,
    # but clusters dict caps examples to 5 — so re-walk briefly for counts).
    rule_prefix_counts: dict[str, Counter] = defaultdict(Counter)
    async for ga in db.game_analyses.find(
        {"decryption_v5_data": {"$exists": True}, "decryption_v5_version": {"$gte": 55}}
    ).sort("created_at", -1).limit(500):
        for m in (ga.get("decryption_v5_data") or []):
            if not m.get("is_user_move"):
                continue
            cap = m.get("caption") or ""
            rule = m.get("rule_name") or ""
            if not cap or not rule:
                continue
            for tgt, _, _ in RULE_TARGETS:
                if _rule_matches(rule, tgt):
                    rule_prefix_counts[tgt][_caption_prefix_60(cap)] += 1
                    break

    # Build MD
    lines: list[str] = []
    lines.append("# HIGH-tier captions — pedagogical review sample\n")
    lines.append(f"Scanned 500 v55 games. Captions sampled stratified by rule file + "
                 f"caption-prefix cluster — one representative per cluster.\n")
    lines.append("**Review legend:**")
    lines.append("- ✅ **Ship** — voice + lesson are right")
    lines.append("- ⚠️  **Borderline** — defensible but could be sharper / note the edit")
    lines.append("- ❌ **Rewrite** — wrong voice OR wrong lesson OR mis-framed (note why)\n")
    lines.append("Use the GitHub task-list checkbox or just edit-in your verdict.\n")
    lines.append("---\n")

    total_selected = 0
    for rule_name, n_clusters_to_pick, label in RULE_TARGETS:
        counts = rule_prefix_counts.get(rule_name, Counter())
        top_prefixes = counts.most_common(n_clusters_to_pick)
        if not top_prefixes:
            continue

        lines.append(f"## {rule_name}.json — {label}\n")
        lines.append(f"Total HIGH captions in 500-game corpus: **{sum(counts.values())}** "
                     f"across **{len(counts)}** distinct prefix clusters. "
                     f"Sampling top {len(top_prefixes)} clusters below.\n")

        for prefix, count in top_prefixes:
            examples = clusters.get((rule_name, prefix), [])
            if not examples:
                continue
            # Pick the example with mid-range cp_loss (avoids extreme outliers)
            examples_sorted = sorted(
                examples, key=lambda e: abs((e.get("cp_loss") or 0) - 250)
            )
            ex = examples_sorted[0]
            total_selected += 1

            gid = ex["game_id"]
            mn = ex["move_number"]
            fen_url = ex["fen"].replace(" ", "_")
            # Lichess analysis viewer with the exact FEN (board side derives
            # from FEN). Works without auth.
            lichess_url = f"https://lichess.org/analysis/standard/{fen_url}"
            # Local app deep link — GameAnalysis.jsx supports ?move=N.
            # Mohit can swap the host prefix when reading.
            app_url = f"/game/{gid}?move={mn}"

            lines.append(f"### #{total_selected} — `{rule_name}` cluster ({count} games hit this prefix)\n")
            lines.append(f"**Game:** `{gid[:12]}` move {mn} "
                         f"({ex['user_color']} in {ex['opening'] or '?'})  ")
            lines.append(f"**Played:** `{ex['move_san']}` (cp_loss `{ex['cp_loss']}`)  ")
            lines.append(f"**Engine best:** `{ex['best_san']}`  ")
            lines.append(f"")
            lines.append(f"**🔍 View board:** [Open in app]({app_url}) · [Open on lichess]({lichess_url})")
            if ex.get("shape_pattern_name"):
                lines.append(f"**Shape pattern:** `{ex['shape_pattern_name']}`")
            if ex.get("concept_id"):
                lines.append(f"**Concept:** `{ex['concept_id']}`")
            lines.append(f"<details><summary>FEN</summary>\n\n`{ex['fen']}`\n\n</details>")
            lines.append("")
            lines.append("**Caption as shipped:**\n")
            lines.append(f"> {ex['caption']}\n")
            lines.append("**Verdict:** `[ ] ✅ ship` `[ ] ⚠️ borderline` `[ ] ❌ rewrite`  ")
            lines.append("**Note (if rewrite):**\n")
            lines.append("---\n")

        lines.append("")

    lines.append(f"\n**Total sampled for review: {total_selected} captions** "
                 f"across {len(RULE_TARGETS)} rule files.\n")
    lines.append("When you're done: drop your verdicts back as a list "
                 "(\"#3 rewrite — too clinical\", etc.) and I'll batch the fixes "
                 "into a single JSON edit pass.")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {out_path} with {total_selected} captions for review")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    args = p.parse_args()
    asyncio.run(main_async(args.out))


if __name__ == "__main__":
    main()
